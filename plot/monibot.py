#!/usr/bin/env python3

import logging
import os
import signal
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import dateparser
from co2plot import co2plot, co2now

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


def signal_handler(signum, frame):
    log.info('Signal handler called with signal %d' % signum)
    exit(0)


signal.signal(signal.SIGTERM, signal_handler)


@app.command("/co2")
def say_about_co2(ack, say, command, client):
    ack()
    if command['text'] == "now":
        now = co2now()
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
        say(mes)
        return
    dates = dateparser.parse(command['text'])
    co2plot(days=dates)
    date_format = "%Y-%m-%d"
    title = ""
    if dates[0]:
        title += "from " + dates[0].strftime(date_format) + " "
    if dates[1]:
        title += "to " + dates[1].strftime(date_format)
    channel_id = command["channel_id"]
    client.files_upload(
        channels=channel_id,
        file="plot.png",
        title=title,
    )


if __name__ == "__main__":
    try:
        log.info('running.')
        handler.start()
    finally:
        handler.close()
        log.info('stopped.')
