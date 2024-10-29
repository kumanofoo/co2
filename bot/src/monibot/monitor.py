from typing import Any, Dict
import os
from datetime import datetime, timezone
import json
from monibot.jma import Weather, WeatherError
from monibot.ping import ICMP, Web, DNS
import logging

log = logging.getLogger(__name__)


class MonitorError(Exception):
    pass


def get_value(json, key, valuetype) -> Any:
    ret = None

    value = json.get(key)
    if value is None:
        raise MonitorError("'%s' not found" % key)
    try:
        ret = valuetype(value)
    except ValueError as e:
        log.warning(e)
        raise MonitorError("'%s' is not '%s'" % (key, valuetype.__name__))

    return ret


def read_config(key: str) -> dict:
    monitor_config = os.environ.get("MONITOR_CONFIG")
    if not monitor_config:
        raise MonitorError("no environment variable MONITOR_CONFIG")

    try:
        f = open(monitor_config, encoding="utf-8")
    except (IOError, FileNotFoundError):
        raise MonitorError(f"cannot open configuration file '{monitor_config}'")

    conf = json.load(f)
    monitor_configuration = conf.get("monitor")
    if not monitor_configuration:
        raise MonitorError(f"'monitor' key not found in {monitor_config}")

    key_configuration = monitor_configuration.get(key)
    if not key_configuration:
        raise MonitorError(f"'{key}' key not found in {monitor_config}:'[monitor]'")

    return key_configuration


class OutsideTemperature:
    def __init__(self):
        self.configuration = read_config("temperature")
        key = "outside_hot_alert_threshold"
        self.outside_hot_alert_threshold = get_value(self.configuration, key, float)
        log.debug("%s: %f degrees Celsius" % (key, self.outside_hot_alert_threshold))

        key = "pipe_alert_threshold"
        self.pipe_alert_threshold = get_value(self.configuration, key, float)
        log.debug("%s: %f degrees Celsius" % (key, self.pipe_alert_threshold))

        key = "forecast_interval_hours"
        self.interval_hours = get_value(self.configuration, key, int)
        log.debug("%s: %d hours" % (key, self.interval_hours))

        try:
            self.wt = Weather()
        except WeatherError as e:
            raise MonitorError(e)

        self.datetime_format = "at %I:%M %p on %A"
        self.degree = "°C"

    def fetch_summary(self, md_type="slack"):
        self.wt.fetch()
        return self.wt.summary(md_type=md_type)

    def fetch_temperature(self):
        self.wt.fetch()
        low, low_t = self.wt.lowest()
        high, high_t = self.wt.highest()
        mes = None
        if low and low_t and high and high_t:
            low_t_str = low_t.strftime(self.datetime_format)
            high_t_str = high_t.strftime(self.datetime_format)
            mes = "A low of %.1f%s %s\n" % (low, self.degree, low_t_str)
            mes += "A high of %.1f%s %s" % (high, self.degree, high_t_str)

        return mes

    def check_temperature(self):
        min = self.pipe_alert_threshold
        max = self.outside_hot_alert_threshold
        now = datetime.now(timezone.utc)

        log.debug("min=%d, max=%d" % (min, max))
        self.wt.fetch()
        low, low_t = self.wt.lowest()
        high, high_t = self.wt.highest()
        mes = ""
        if low and low_t and high and high_t:
            low_t_str = low_t.strftime(self.datetime_format)
            high_t_str = high_t.strftime(self.datetime_format)
            log.debug("low=%d, low_t=%s" % (low, low_t_str))
            log.debug("high=%d, high_t=%s" % (high, high_t_str))
            if low_t > now and low <= min:
                if mes != "":
                    mes += "\n"
                mes += "keep your pipes!!\n"
                mes += "A low of %.1f%s %s" % (low, self.degree, low_t_str)
            if high_t > now and high < 0:
                if mes != "":
                    mes += "\n"
                mes += "It will be too cold!!\n"
                mes += "A high of %.1f%s %s" % (high, self.degree, high_t_str)
            if high_t > now and high > max:
                if mes != "":
                    mes += "\n"
                mes += "It will be too hot!!\n"
                mes += "A high of %.1f%s %s" % (high, self.degree, high_t_str)
            if low_t > now and low > max:
                if mes != "":
                    mes += "\n"
                mes += "You become butter...\n"
                mes += "A low of %.1f%s %s" % (low, self.degree, low_t_str)
        else:
            mes = "Umm, The network seems to be having issues."

        log.debug("message: %s" % (mes))
        return mes


class Server:
    ping = {"ICMP": ICMP, "Web": Web, "DNS": DNS}

    def __init__(self):
        self.configuration = read_config("servers")
        key = "ping_interval_sec"
        self.ping_interval_sec = get_value(self.configuration, key, int)

        key = "previous_data_points"
        self.previous_data_points = get_value(self.configuration, key, int)

        servers = self.configuration.get("ping_servers")
        if servers is None:
            raise MonitorError("'ping_servers' key not found")

        self.servers = []
        for s in servers:
            sv = Server.ping[servers[s]["type"]](s)
            sv.monitor_latest = [1] * self.previous_data_points
            sv.monitor_previous_state = None
            sv.same_state_times = 0
            self.servers.append(sv)
        if len(self.servers) == 0:
            raise MonitorError("no servers")

    def get_status(self) -> Dict[str, bool]:
        status = {}
        for s in self.servers:
            alive, _res = s.is_alive()
            status[s.target] = alive
        return status

    def is_changed(
        self,
        classes: Dict[float, Any] = {},
        class0: Any = False,
        class1: Any = True,
    ) -> Dict[str, Any]:
        status = {}
        for s in self.servers:
            alive, _res = s.is_alive()
            if alive:
                s.monitor_latest.append(1)
            else:
                s.monitor_latest.append(0)
            s.monitor_latest.pop(0)

            latest_alive_average = sum(s.monitor_latest) / len(s.monitor_latest)

            state = None
            if latest_alive_average == 1.0:
                state = class1
            elif latest_alive_average == 0.0:
                state = class0
            else:
                for minimum in sorted(classes.keys(), reverse=True):
                    if latest_alive_average >= minimum:
                        state = classes[minimum]
                        break

            if state is None or s.monitor_previous_state == state:
                pass
            else:
                status[s.target] = state
                s.monitor_previous_state = state

            log.debug(f"{s.target}: {alive}, {state}")
        return status
