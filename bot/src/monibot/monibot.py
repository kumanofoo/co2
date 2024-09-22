#!/usr/bin/env python3

import logging
import os
import re
import signal
import queue
import threading
import time
import tempfile
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from slack_sdk import WebhookClient
from co2 import co2plot, dateparser
import monibot
from monibot.book import BookStatus, BookStatusError
from monibot.command import Command
from monibot.cron import Cron
from monibot.monitor import OutsideTemperature, Server, MonitorError
from monibot.getip import GetIP, GetIPError


# global logging settings
MONIBOT_LOGGING_LEVEL = os.environ.get("MONIBOT_LOGGING_LEVEL")
if MONIBOT_LOGGING_LEVEL == "info":
    log_level = logging.INFO
    formatter = '%(name)s: %(message)s'
elif MONIBOT_LOGGING_LEVEL == "debug":
    log_level = logging.DEBUG
    formatter = '%(asctime)s %(name)s[%(lineno)s] %(levelname)s: %(message)s'
else:
    log_level = logging.WARNING  # default debug level
    formatter = '%(name)s: %(message)s'
logging.basicConfig(level=log_level, format=formatter)
log = logging.getLogger('monibot')

# slack token and app settings
if os.environ.get("SLACK_BOT_TOKEN"):
    try:
        app = App(token=os.environ["SLACK_BOT_TOKEN"])
    except Exception as e:
        log.critical(f"failed to connect to Slack: {e}")
        exit(1)
else:
    log.critical("Environment value 'SLACK_BOT_TOTKEN' is not difined")
    exit(1)
if not os.environ.get("SLACK_APP_TOKEN"):
    log.critical("environment value 'SLACK_APP_TOTKEN' is not difined")
    exit(1)

my_user_id = None
try:
    result = app.client.auth_test()
    if result["ok"]:
        my_user_id = result["user_id"]
except SlackApiError as e:
    log.critical(f"I don't know who I am: {e}")
    exit(1)

handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])

# incoming webhook for reports
REPORT_WEBHOOK = os.environ.get("REPORT_WEBHOOK")
if not REPORT_WEBHOOK:
    log.critical("Environment value 'REPORT_WEBHOOK' is not defined")
    exit(1)
else:
    webhook = WebhookClient(REPORT_WEBHOOK)

# co2plot figure directory
tmpdir = tempfile.TemporaryDirectory()
co2plot_fig = tmpdir.name
finish_monibot = False


def signal_handler(signum, frame):
    global finish_monibot
    finish_monibot = True
    log.info('Signal handler called with signal %d' % signum)
    exit(0)


def thread(func):
    def _wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        log.debug(f"start {func.__name__} thread...")
        thread.start()
        return thread
    return _wrapper


@thread
def co2_command(param):
    if CO2PLOT is None:
        return
    figure_png = None
    if param.command == "now":
        now = co2plot.get_latest(config=CO2PLOT)
        abrvs = {
            "degree celsius": "°",
            "parcentage": "%",
            "Temperature": ("🌡", "%.1f"),
            "Humidity": ("💧", "%.1f"),
            "Carbon Dioxide": ("💨", "%d"),
        }
        mes = ""
        for topic in now:
            mes += f"{topic} ({now[topic]['timestamp']})\n"
            for n in now[topic]["metadata"]:
                meta = now[topic]["metadata"][n]
                (name, fmt) = abrvs.get(meta['name'], (meta['name'], "%f"))
                unit = abrvs.get(meta['unit'], meta['unit'])
                val = now[topic]["payload"][n]
                mes += "%6s " % name
                mes += fmt % val
                mes += "%s" % unit
                mes += "\n"
        param.message = mes
    else:
        dates = dateparser.parse(param.command)
        figure_png = f"{co2plot_fig}/co2plot{time.time()}.png"
        log.debug(f"plot to {figure_png}")
        res = co2plot.figure(days=dates, config=CO2PLOT, filename=figure_png)
        if res:
            date_format = "%Y-%m-%d"
            title = "Measurements "
            if dates:
                if dates[0]:
                    title += "from " + dates[0].strftime(date_format) + " "
                if dates[1]:
                    title += "to " + dates[1].strftime(date_format)
            param.files = [figure_png]
            param.message = title
        else:
            param.message = "no data"
    log.debug(f"command: {param.command}")
    log.debug(f"channel: {param.channel}")
    param.respond()
    if figure_png:
        if os.path.exists(figure_png):
            log.debug(f"remove {figure_png}")
            os.remove(figure_png)
    log.debug("finish co2 thread")


def book_event(param):
    @thread
    def run_search_book(param):
        if book is None:
            return
        result_, text = book.search(param.command)
        param.message = text
        param.respond()

    if not book:
        param.message = "Sorry, the book command is out of service."
        param.respond()
    else:
        run_search_book(param)


def air_event(param):
    if not CO2PLOT:
        param.message = "Sorry, the command is out of service."
        param.respond()
    else:
        co2_command(param)


def weather_event(param):
    @thread
    def fetch_summary(param):
        if forecast is None:
            return
        summary = forecast.fetch_summary()
        if summary:
            param.message = summary
        else:
            param.message = (
                "Sorry, weather forecast is temporarily unavailable."
            )
        param.respond()

    if not forecast:
        param.message = "Sorry, the weather command is out of service."
        param.respond()
    else:
        fetch_summary(param)


def ip_event(param):
    @thread
    def fetch_ip(param):
        if ip is None:
            return
        param.message = ip.get()
        if param.message is None:
            param.message = "Failed to fetch IP address."
        param.respond()

    if not ip:
        param.message = "Sorry, the ip command is out of service."
        param.respond()
    else:
        fetch_ip(param)


def ping_event(param):
    @thread
    def ping_to_server(param):
        if servers is None:
            return
        up_down = {True: "UP", False: "DOWN"}
        message = ""
        targets = servers.get_status()
        for target in targets:
            message += f"{target} is {up_down[targets[target]]}.\n"
        if message:
            param.message = message
        else:
            param.message = "no servers"
        param.respond()

    if not servers:
        param.message = "Sorry, the ping command is out of service."
        param.respond()
    else:
        ping_to_server(param)


def help_event(param):
    cmd = []
    if CO2PLOT:
        cmd.append("air [now|DATE]")
    if book:
        cmd.append("book|TITLE|ISBN-10")
    if ip:
        cmd.append("ip")
    if forecast:
        cmd.append("weather")
    if servers:
        cmd.append("ping")
    cmd.append("help|?")

    param.message = f"Usage: {param.command} [" + '|'.join(cmd) + "]"
    param.respond()


commands = {
    "air": air_event,
    "book": book_event,
    "ip": ip_event,
    "ping": ping_event,
    "weather": weather_event,
    "help": help_event,
    "?": help_event,
}


def parse_command(text):
    text = text.strip()
    result = re.match(r"\s*((\S*)\s*(.*))", text)
    if result is None:
        return ("help", "")
    title, command, arg = result.groups()
    if command == "":
        return ("help", "")
    cmd = [c for c in commands.keys() if c.startswith(command)]
    if len(cmd) != 1:
        return ("book", title)
    return (cmd[0], arg)


@app.event("message")
def reply_direct_message(say, event, client):
    if event['channel_type'] != 'im':
        return
    text = event.get("text")
    if text is None:
        return
    cmd, arg = parse_command(text)
    if cmd == "book":
        say(f'"{arg}"...')
    param = Command(channel=event["channel"])
    param.command = arg
    commands[cmd](param)
    return


def get_user_id(text):
    text = text.strip()
    result = re.match(r"^<@(\w+?)>\s*(.*)", text)
    if result:
        return result.groups()
    return None, None


@app.event("app_mention")
def reply_mention(say, event, client):
    text = event.get("text")
    if text is None:
        return
    user_id, command = get_user_id(text)
    if user_id != my_user_id:
        return
    cmd, arg = parse_command(command)
    if cmd == "book":
        say(f'"{arg}"...')
    param = Command(channel=event["channel"])
    param.command = arg
    commands[cmd](param)
    return


@app.event("app_home_opened")
def home_opened(client, event):
    view = {
        "type": "home",
        "blocks": [],
    }
    view["blocks"].append({
        "type": "section",
        "text": {
                "type": "mrkdwn",
                "text": "*Welcome :house:, <@" + event["user"] + ">*",
        }
    })
    fields = []
    if CO2PLOT:
        now = co2plot.get_latest(config=CO2PLOT)
        if now:
            abrvs = {
                "degree celsius": "°",
                "parcentage": "%",
                "Temperature": ("🌡", "%.1f"),
                "Humidity": ("💧", "%.1f"),
                "Carbon Dioxide": ("💨", "%d"),
            }
            air_quality = ""
            for topic in now:
                air_quality += f"{topic} ({now[topic]['timestamp']})\n"
                for n in now[topic]["metadata"]:
                    meta = now[topic]["metadata"][n]
                    (name, fmt) = abrvs.get(meta['name'], (meta['name'], "%f"))
                    unit = abrvs.get(meta['unit'], meta['unit'])
                    val = now[topic]["payload"][n]
                    air_quality += "%s " % name
                    air_quality += fmt % val
                    air_quality += "%s" % unit
                    air_quality += " "
                air_quality += "\n"
            fields.append({
                "type": "mrkdwn",
                "text": air_quality,
            })
    if forecast:
        summary = forecast.fetch_summary()
        if summary is None:
            summary = (
                "Sorry, weather forecast is temporarily unavailable."
            )
        fields.append({
            "type": "mrkdwn",
            "text": summary,
        })
    if fields:
        view["blocks"].append({
            "type": "section",
            "fields": fields
        })
    else:
        view["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No Air Information",
            }
        })
    view["blocks"].append({
        "type": "divider"
    })
    footer = ""
    if ip:
        ip_address = ip.get()
        if ip_address:
            footer = f"IP Adderss: {ip_address}\n"
    footer += f"Version: {monibot.__version__}"
    view["blocks"].append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": footer
        }
    })
    try:
        client.views_publish(
            user_id=event["user"],
            view=view
        )
    except Exception as e:
        log.error(f"Error publishing home tab: {e}")


q = queue.Queue()
crons = []

CO2PLOT = os.environ.get("CO2PLOT")
if CO2PLOT:
    if not os.path.exists(CO2PLOT):
        log.info(f"co2plot configration file '{CO2PLOT}' not found")
        CO2PLOT = None
else:
    log.info("Environment value 'CO2PLOT' is not defined")

try:
    book = BookStatus()
except BookStatusError as e:
    log.warning(f"Book search: {e}")
    log.info("Disable book search")
    book = None

try:
    forecast = OutsideTemperature()
    c = Cron(
        forecast.check_temperature,
        interval_sec=forecast.interval_hours*60*60,
        queue=q
    )
    crons.append(c)
except MonitorError as e:
    log.warning(f"Weather forecast: {e}")
    log.info("Disable outside temperature message")
    forecast = None

try:
    servers = Server()

    def check_servers():
        if servers is None:
            return ""
        targets = servers.is_changed(
            classes={
                0.9: ":large_yellow_circle:",
                0.0: ":large_orange_circle:"
            },
            class1=":large_green_circle:",
            class0=":red_circle:",
        )
        message = ""
        for target in targets:
            message += f"{targets[target]} {target}\n"
        return message

    if servers:
        c = Cron(
            check_servers,
            interval_sec=servers.ping_interval_sec,
            queue=q
        )
        crons.append(c)
except MonitorError as e:
    log.warning(f"Server monitor: {e}")
    log.info("Disable server monitor message")
    servers = None

try:
    ip = GetIP()
except GetIPError as e:
    log.warning(f"Get IP: {e}")
    log.info("Disable ip")
    ip = None


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        handler.connect()
    except Exception as e:
        log.error(f'failed to connect Slack: {e}')
        exit(1)

    for c in crons:
        c.start()
    log.info('running.')

    retry_interval_sec = 60
    while not finish_monibot:
        mes = q.get()
        log.debug(f"dequeue message: {mes}")
        if mes == "":
            log.warning(f"message was empty")
            continue
        try:
            webhook.send(text=mes)
            retry_interval_sec = 60
        except Exception as e:
            log.warning(f"caught an exception in webhook.send: {e}")
            log.warning(f"retry to send after {retry_interval_sec} seconds")
            q.put(mes)
            time.sleep(retry_interval_sec)
            retry_interval_sec *= 2

    for c in crons:
        c.abort()
        c.join()
    handler.close()
    log.info('stopped.')


if __name__ == "__main__":
    main()
