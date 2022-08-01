import os
from datetime import datetime
import json
from monibot.openweathermap import Weather, WeatherError
import logging
log = logging.getLogger(__name__)


class MonitorError(Exception):
    pass


def get_value(json, key, valuetype):
    ret = None

    value = json.get(key)
    if not value:
        raise MonitorError("'%s' not found" % key)
    try:
        ret = valuetype(value)
    except ValueError as e:
        log.warning(e)
        raise MonitorError("'%s' is not '%s'" % (key, valuetype.__name__))

    return ret


class OutsideTemperature():
    def __init__(self):
        self.MONITOR_CONFIG = os.environ.get("MONITOR_CONFIG")
        if not self.MONITOR_CONFIG:
            raise MonitorError(
                            'no environment variable MONITOR_CONFIG')

        try:
            f = open(self.MONITOR_CONFIG, encoding='utf-8')
        except (IOError, FileNotFoundError):
            raise MonitorError(
                "cannot open configuration file '{0}'".format(
                    self.MONITOR_CONFIG))

        try:
            conf = json.load(f)
        except ValueError as e:
            log.warning(e)
            raise MonitorError("cannot parse configuration")

        self.configuration = conf.get('monitor')
        if not self.configuration:
            raise MonitorError("'monitor' key not found in %s" %
                               {self.MONITOR_CONFIG})

        key = 'outside_hot_alert_threshold'
        self.outside_hot_alert_threshold = get_value(self.configuration,
                                                     key, float)
        log.debug('%s: %f degrees Celsius' %
                  (key, self.outside_hot_alert_threshold))

        key = 'pipe_alert_threshold'
        self.pipe_alert_threshold = get_value(self.configuration, key, float)
        log.debug('%s: %f degrees Celsius' %
                  (key, self.pipe_alert_threshold))

        key = 'forecast_interval_hours'
        self.interval_hours = get_value(self.configuration, key, int)
        log.debug('%s: %d hours' %
                  (key, self.interval_hours))

        try:
            self.wt = Weather()
        except WeatherError as e:
            raise MonitorError(e)

        self.datetime_format = 'at %I:%M %p on %A'
        self.degree = '°C'

    def fetch_summary(self):
        self.wt.fetch()
        return self.wt.summary()

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
        now = datetime.now()

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

        log.debug("message: %s" % (mes))
        return mes
