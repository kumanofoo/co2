#! /usr/bin/env python3

import os
from datetime import datetime
import json
import requests

import logging
log = logging.getLogger(__name__)


class WeatherError(Exception):
    pass


class Weather:
    """
    fetch weather forecast from OpenWeather
    """
    def __init__(self):
        self.weather = ''

        MY_PLACE = os.environ.get("MY_PLACE")
        if not MY_PLACE:
            raise WeatherError("no environment variable MY_PLACE")
        else:
            self.lat, self.lon = MY_PLACE.split(':')

        self.api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not self.api_key:
            raise WeatherError("no environment variable OPENWEATHER_API_KEY")

        self.weather = ''
        self.EMOJI = {
            2: ":thunder_cloud_and_rain:",
            3: ":umbrella_with_rain_drops:",
            5: ":umbrella_with_rain_drops:",
            6: ":snowman:",
            7: ":foggy:",
            800: ":sunny:",
            801: ":mostly_sunny:",
            8: ":cloud:",
            "x": ":japanese_goblin:",
        }
        self.WIND_DIR = {
            0: "N",
            1: "NE",
            2: "NE",
            3: "E",
            4: "E",
            5: "SE",
            6: "SE",
            7: "S",
            8: "S",
            9: "SW",
            10: "SW",
            11: "W",
            12: "W",
            13: "NW",
            14: "NW",
            15: "N",
        }
        self.DIR2ARROW = {
            "N": "⇓",
            "NE": "⇙",
            "E": "⇐",
            "SE": "⇖",
            "S": "⇑",
            "SW": "⇗",
            "W": "⇒",
            "NW": "⇘",
        }

    def fetch(self):
        url = (
            'https://api.openweathermap.org/data/2.5/onecall?'
            'exclude=minutely&units=metric&'
            f'appid={self.api_key}&lat={self.lat}&lon={self.lon}'
        )
        resp = requests.get(url)
        if resp.status_code == 200:
            self.weather = json.loads(resp.text)
        else:
            log.error("Connection failure to %s" % url)
            self.weather = ''

    def lowest(self):
        if self.weather == '':
            self.fetch()
        if self.weather == '':
            return None, None

        low = float('inf')
        lowTime = None
        for h in range(0, 24):
            if low > self.weather['hourly'][h]['temp']:
                low = self.weather['hourly'][h]['temp']
                lowTime = self.weather['hourly'][h]['dt']
        lowLocalTime = datetime.fromtimestamp(lowTime)

        return float(low), lowLocalTime

    def highest(self):
        if self.weather == '':
            self.fetch()
        if self.weather == '':
            return None, None

        high = -float('inf')
        highTime = None
        for h in range(0, 24):
            if high < self.weather['hourly'][h]['temp']:
                high = self.weather['hourly'][h]['temp']
                highTime = self.weather['hourly'][h]['dt']
        highLocalTime = datetime.fromtimestamp(highTime)

        return float(high), highLocalTime

    def summary(self):
        if self.weather == '':
            self.fetch()
        if self.weather == '':
            return None

        cur = self.weather['current']
        wt = cur['weather'][0]
        wid = wt['id']
        if wid in self.EMOJI:
            id = wid
        else:
            id = wid // 100
        if id not in self.EMOJI:
            id = 'x'

        wd_degree = 360.0/16
        offset = wd_degree/2.0
        wd = int((cur["wind_deg"] + offset)/wd_degree) % 16
        summary = f'*{self.EMOJI[id]} {cur["temp"]}°C*\n' \
            f'*Feels like {cur["feels_like"]}°C. {wt["main"]}.*\n' \
            f'{self.DIR2ARROW[self.WIND_DIR[wd]]} {cur["wind_speed"]}m/s ' \
            f'{self.WIND_DIR[wd]}\n' \
            f'Humidity: {cur["humidity"]}%    UV: {cur["uvi"]}\n' \
            f'Dew point: {cur["dew_point"]}°C    ' \
            f'Visibility: {cur["visibility"]}m\n'
        return summary


if __name__ == '__main__':
    w = Weather()
    w.fetch()
    text = w.summary()
    print(text)

    high, highTime = w.highest()
    print('highest temperature: ',
          f'{high}°C', highTime.strftime("at %I:%M %p on %A"))

    low, lowTime = w.lowest()
    print('lowest temperature: ',
          f'{low}°C', lowTime.strftime("at %I:%M %p on %A"))

    if high > 35:
        print("so hot!!")
    elif high > 30:
        print("hot!!")

    if low < -3:
        print("so cold!!")
    elif low < 5:
        print("cold!!")
