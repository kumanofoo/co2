#! /usr/bin/env python3

import logging
import os
import re
import signal
import queue
import threading
import time
import tempfile
import random
from typing import Any, Tuple, Dict, List
import requests
import zulip
from co2 import co2plot, dateparser
from monibot.book import BookStatus, BookStatusError
from monibot.getip import GetIP, GetIPError
from monibot.cron import Cron
from monibot.monitor import OutsideTemperature, Server, MonitorError


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
log = logging.getLogger('monibotz')


# Check Zulip Environmet Variable
_ = zulip.Client()
stream_topic = os.environ["ZULIP_MONIBOT_STREAM"]
zulip_stream, zulip_topic = stream_topic.split(":")
zulip_email = os.environ["ZULIP_EMAIL"]
log.debug(f"ZULIP_MONIBOT_STREAM:  #{zulip_stream}>{zulip_topic}")

# Initialize Global Variable
finish_bot = False

# co2plot figure directory
tmpdir = tempfile.TemporaryDirectory()
co2plot_fig = tmpdir.name


class Parameter:
    def __init__(
            self,
            arguments: str = "",
            tag: Dict[str, Any] = {}):
        self.arguments = arguments
        self.tag = tag

    def respond(self, message: str = "",
                files: List[str] = [],
                filenames: List[str] = []):
        if message:
            self.tag["content"] = message
        client = zulip.Client()
        for i, file in enumerate(files):
            log.debug(f"upload file: {file}")
            with open(file, "rb") as fp:
                result = client.upload_file(fp)
            if result["result"] == "success":
                if message and i == 0:
                    self.tag["content"] += "\n"
                if i > 0:
                    self.tag["content"] += "\n"
                if len(filenames) > i:
                    self.tag["content"] += f"[{filenames[i]}]({result['uri']})"
                else:
                    self.tag["content"] += f"[file{i}]({result['uri']})"
            else:
                log.warning(result["msg"])
            log.debug(result)
        result = client.send_message(self.tag)
        if result["result"] != "success":
            log.warning(result["msg"])
        log.debug(result)


def signal_handler(signum, frame):
    global finish_bot
    finish_bot = True
    log.info('Signal handler called with signal %d' % signum)


def thread(func):
    def _wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        log.debug(f"start {func.__name__} thread...")
        thread.start()
        return thread
    return _wrapper


@thread
def co2_command(param: Parameter) -> None:
    figure_png = None
    if param.arguments == "now":
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
        param.respond(mes)
    else:
        dates = dateparser.parse(param.arguments)
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
            param.respond(message="", files=[figure_png], filenames=[title])
        else:
            param.respond(message="no data")
    if figure_png:
        if os.path.exists(figure_png):
            log.debug(f"remove {figure_png}")
            os.remove(figure_png)
    log.debug("finish co2 thread")


def book_event(param: Parameter) -> None:
    @thread
    def run_search_book(param: Parameter) -> None:
        result, text_ = book.search(param.arguments)
        text = result_by_string(result)
        if text:
            param.respond(message=text)

    def result_by_string(result: Dict[str, Any]) -> str:
        if not result:
            return ""
        if not result['data']:
            emoji = [
                ':collision:',
                ':moyai:',
                ':sandal:',
                ':ramen:',
                ':jack-o-lantern:'
            ]
            return emoji[random.randrange(0, len(emoji))]

        string = f"[{result['book']}]"
        for title in result['data']:
            string += f"\n{title}\n"
            for systemid in result['data'][title]:
                library = result['data'][title][systemid]
                if library['status']:
                    for place in library['status']:
                        string += '- %s(%s): [%s](%s)\n' % (
                            library['name'], place,
                            library['status'][place], library['url'])
                else:
                    string += f"- {library['name']}: 蔵書なし\n"
        return string

    if not book:
        param.respond(message="Sorry, the book command is out of service.")
    else:
        param.respond(message=f'"{param.arguments}"...')
        run_search_book(param)


def air_event(param: Parameter) -> None:
    if not CO2PLOT:
        param.respond(message="Sorry, the command is out of service.")
    else:
        co2_command(param)


def weather_event(param: Parameter) -> None:
    @thread
    def fetch_summary(param: Parameter) -> None:
        summary = forecast.fetch_summary(md_type="zulip")
        if summary:
            param.respond(message=summary)
        else:
            m = "Sorry, weather forecast is temporarily unavailable."
            param.respond(message=m)
    if not forecast:
        param.respond(message="Sorry, the weather comand is out of service.")
    else:
        fetch_summary(param)


def ip_event(param: Parameter) -> None:
    @thread
    def fetch_ip(param: Parameter):
        message = ip.get()
        if message is None:
            message = "Failed to fetch IP address."
        param.respond(message=message)
    if not ip:
        message = "Sorry, the ip command is out of service."
        param.respond(message=message)
    else:
        fetch_ip(param)


def ping_event(param: Parameter) -> None:
    @thread
    def ping_to_server(param: Parameter) -> None:
        up_down = {True: "UP", False: "DOWN"}
        message = ""
        targets = servers.get_status()
        for target in targets:
            message += f"{target} is {up_down[targets[target]]}.\n"
        if message:
            param.respond(message=message)
        else:
            param.respond(message="no servers")

    if not servers:
        message = "Sorry, the ping command is out of service."
        param.respond(message=message)
    else:
        ping_to_server(param)


def help_event(param: Parameter) -> None:
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
    message = "Usage: " + '|'.join(cmd)
    param.respond(message=message)


commands = {
    "air": air_event,
    "book": book_event,
    "ip": ip_event,
    "weather": weather_event,
    "ping": ping_event,
    "help": help_event,
    "?": help_event,
}


def parse_command(text: str) -> Tuple[str, str]:
    text = text.strip()
    result = re.match(r"(@\*\*\S+\*\*\s)*\s*((\S*)\s*(.*))", text)
    if result is None:
        return ("help", "")
    user_id_, title, command, arg = result.groups()
    if command == "":
        return ("help", "")
    cmd = [c for c in commands.keys() if c.startswith(command)]
    if len(cmd) != 1:
        return ("book", title)
    return (cmd[0], arg)


def message_handler(msg: Dict[str, Any]) -> None:
    if msg["sender_email"] == zulip_email:
        return
    content = msg["content"]
    if content is None:
        return
    cmd, arg = parse_command(content)
    if msg["type"] == "private":
        tag = dict(
            type="private",
            to=[x["id"] for x in msg["display_recipient"]],
            content="",
        )
    else:
        tag = dict(
            type="stream",
            to=msg["display_recipient"],
            subject=msg["subject"],
            content="",
        )
    param = Parameter(arguments=arg, tag=tag)
    log.debug(f"cmd: {cmd}, arguments: {param.arguments}, tag: {tag}")
    commands[cmd](param)


@thread
def call_on_message() -> None:
    client = zulip.Client()

    def do_register() -> Tuple[str, int]:
        while True:
            res = client.register(event_types=["message"])
            if "error" in res["result"]:
                log.warning(f"Server returned error:\n{res['msg']}")
                time.sleep(1)
            else:
                return (res["queue_id"], res["last_event_id"])
    queue_id = None
    while not finish_bot:
        if queue_id is None:
            (queue_id, last_event_id) = do_register()
        try:
            res = client.get_events(
                queue_id=queue_id,
                last_event_id=last_event_id)
        except (
            requests.exceptions.Timeout,
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
        ) as e:
            log.warning(f"Connection error fetching events:\n {e}")
            time.sleep(1)
            continue
        except Exception as e:
            log.warning(f"Unexpected error:\n {e}")
            time.sleep(1)
            continue
        if "error" in res["result"]:
            if res["result"] == "http-error":
                log.warning("HTTP error fetching events --"
                            "probably a server restart")
            else:
                log.warning(f"Server returned error:\n{res['msg']}")
                if (res.get("code") == "BAD_EVENT_QUEUE_ID" or
                        res["msg"].startswith("Bad event queue id:")):
                    queue_id = None
                time.sleep(1)
                continue
        for event in res["events"]:
            last_event_id = max(last_event_id, int(event["id"]))
            if event["type"] == "message":
                log.debug(event["message"])
                message_handler(event["message"])
    log.info("call_on_message is done.")


q = queue.Queue()
crons = []

CO2PLOT = os.environ.get("CO2PLOT", None)
if CO2PLOT:
    if not os.path.exists(CO2PLOT):
        log.info(f"co2plot configration file '{CO2PLOT}' not found")
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
        queue=q,
    )
    crons.append(c)
except MonitorError as e:
    log.warning(f"Weather forecast: {e}")
    log.info("Disable outside temperature message")
    forecast = None

try:
    servers = Server()

    def check_servers():
        targets = servers.is_changed()
        message = ""
        states = {True: "UP", False: "DOWN"}
        for target in targets:
            message += f"{target} is {states[targets[target]]}\n"
        return message

    c = Cron(
        check_servers,
        interval_sec=servers.ping_interval,
        queue=q,
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
    log.info("Disable IP")
    ip = None


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    for c in crons:
        c.start()
    client = zulip.Client()
    log.info('running.')
    th = call_on_message()
    while not finish_bot:
        try:
            mes = q.get(timeout=5)
        except queue.Empty:
            continue
        log.debug(f'dequeue message: {mes}')
        client.send_message(dict(
            type="stream",
            to=zulip_stream,
            subject=zulip_topic,
            content=mes,
        ))
    log.info("Wait stopping bot...")
    th.join()
    for c in crons:
        c.abort()
        c.join()
    log.info("done.")


if __name__ == "__main__":
    main()
