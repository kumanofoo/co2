#!/usr/bin/env python3

import logging
import os
import signal
import queue
import threading
import time
import tempfile
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from co2 import co2plot, dateparser
from monibot.book import BookStatus, BookStatusError
from monibot.command import Command
from monibot.cron import Cron
from monibot.monitor import OutsideTemperature, MonitorError


# global logging settings
MONIBOT_DEBUG = os.environ.get("MONIBOT_DEBUG")
if MONIBOT_DEBUG == "info":
    log_level = logging.INFO
    formatter = '%(name)s: %(message)s'
elif MONIBOT_DEBUG == "debug":
    log_level = logging.DEBUG
    formatter = '%(asctime)s %(name)s[%(lineno)s] %(levelname)s: %(message)s'
else:
    log_level = logging.WARNING  # default debug level
    formatter = '%(name)s: %(message)s'
logging.basicConfig(level=log_level, format=formatter)
log = logging.getLogger('monibot')

# slack token and app settings
if os.environ.get("SLACK_BOT_TOKEN"):
    app = App(token=os.environ["SLACK_BOT_TOKEN"])
else:
    log.critical("Environment value 'SLACK_BOT_TOTKEN' is not difined")
    exit(1)
if not os.environ.get("SLACK_APP_TOKEN"):
    log.critical("environment value 'SLACK_APP_TOTKEN' is not difined")
    exit(1)
handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])

# report channel
REPORT_CHANNEL = os.environ.get("REPORT_CHANNEL")
if not REPORT_CHANNEL:
    log.critical("Environment value 'REPORT_CHANNEL' is not defined")
    exit(1)

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


@app.command("/book")
def say_about_book(ack, say, command):
    if not book:
        ack("Sorry, the command is out of service.")
        return
    ack()

    @thread
    def run_search_book(param):
        res = book.search(param.command)
        param.message = res[1]
        param.respond()

    param = Command(channel=command["channel_id"])
    param.command = command["text"]
    say(f"'{param.command}'...")
    run_search_book(param)


@app.command("/co2")
def say_about_co2(ack, say, command):
    if not CO2PLOT:
        ack("Sorry, the command is out of service.")
        return
    ack()
    param = Command(channel=command["channel_id"])
    param.command = command["text"]
    say("now searching...")
    co2_command(param)


@app.command("/weather")
def say_about_weather(ack, say, command):
    if not forecast:
        ack("Sorry, the command is out of service.")
        return
    ack()

    @thread
    def fetch_summary(param):
        text = forecast.fetch_summary()
        param.message = text
        param.respond()

    param = Command(channel=command["channel_id"])
    param.command = "weather"
    say("weather...")
    fetch_summary(param)


@app.event("message")
def handle_message_events(body, logger):
    log.info(body)


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
    cmd = Command(
        command="forcast",
        channel=REPORT_CHANNEL
    )
    c = Cron(
        forecast.check_temperature,
        interval_sec=forecast.interval_hours*60*60,
        command=cmd
    )
    crons.append(c)
except MonitorError as e:
    log.warning(f"Weather forecast: {e}")
    log.info("Disable outside temperature message")
    forecast = None


def main():
    signal.signal(signal.SIGTERM, signal_handler)
    for c in crons:
        c.start()
    log.info('running.')
    try:
        handler.connect()
        while not finish_monibot:
            mes = q.get()
            log.debug(f'dequeue message: {mes}')
            param = Command(channel=REPORT_CHANNEL)
            param.message = mes
            param.respond()
    finally:
        handler.close()
        for c in crons:
            c.abort()
            c.join()
        log.info('stopped.')


if __name__ == "__main__":
    main()