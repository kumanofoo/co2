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
        self.weather = {}

        MY_PLACE = os.environ.get("MY_PLACE")
        if not MY_PLACE:
            raise WeatherError("no environment variable MY_PLACE")
        else:
            self.lat, self.lon = MY_PLACE.split(':')

        self.api_key = os.environ.get("OPENWEATHER_API_KEY")
        if not self.api_key:
            raise WeatherError("no environment variable OPENWEATHER_API_KEY")

        self.weather = {}
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
        try:
            resp = requests.get(url)
        except Exception as e:
            log.warning(f"Requests failure: {e}")
            self.weather = {}
            return False
        
        if resp.status_code == 200:
            self.weather = json.loads(resp.text)
            return True
        else:
            log.error("Connection failure to %s" % url)
            self.weather = {}
            return False

    def lowest_highest(self):
        if not self.weather:
            self.fetch()
        if not self.weather:
            return (None, None), (None, None)
        try:
            lowest_data = min(self.weather['hourly'][0:24], key=lambda x: x['temp'])
            highest_data = max(self.weather['hourly'][0:24], key=lambda x: x['temp'])
            low = lowest_data['temp']
            lowLocalTime = datetime.fromtimestamp(lowest_data['dt'])
            high = highest_data['temp']
            highLocalTime = datetime.fromtimestamp(highest_data['dt'])
        except Exception as e:
            log.warning(f"Failed to get temperature: {e.__class__.__name__}: {e}")
            return (None, None), (None, None)

        return (low, lowLocalTime), (high, highLocalTime)

    def lowest(self):
        low, _ = self.lowest_highest()
        return low[0], low[1]

    def highest(self):
        _, high = self.lowest_highest()
        return high[0], high[1]

    def summary(self, md_type: str = ""):
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
        if md_type == "slack":
            summary = (
                f'*{self.EMOJI[id]} {cur["temp"]}°C*\n'
                f'*Feels like {cur["feels_like"]}°C. {wt["main"]}.*\n'
                f'{self.DIR2ARROW[self.WIND_DIR[wd]]} {cur["wind_speed"]}m/s '
                f'{self.WIND_DIR[wd]}\n'
                f'Humidity: {cur["humidity"]}%    UV: {cur["uvi"]}\n'
                f'Dew point: {cur["dew_point"]}°C    '
                f'Visibility: {cur["visibility"]}m\n'
            )
        elif md_type == "zulip":
            summary = (
                f'**{self.EMOJI[id]} {cur["temp"]}°C**\n'
                f'**Feels like {cur["feels_like"]}°C. {wt["main"]}.**\n'
                f'{self.DIR2ARROW[self.WIND_DIR[wd]]} {cur["wind_speed"]}m/s '
                f'{self.WIND_DIR[wd]}\n'
                f'Humidity: {cur["humidity"]}%    UV: {cur["uvi"]}\n'
                f'Dew point: {cur["dew_point"]}°C    '
                f'Visibility: {cur["visibility"]}m\n'
            )
        else:
            summary = (
                f'{self.EMOJI[id]} {cur["temp"]}°C\n'
                f'Feels like {cur["feels_like"]}°C. {wt["main"]}.\n'
                f'{self.DIR2ARROW[self.WIND_DIR[wd]]} {cur["wind_speed"]}m/s '
                f'{self.WIND_DIR[wd]}\n'
                f'Humidity: {cur["humidity"]}%    UV: {cur["uvi"]}\n'
                f'Dew point: {cur["dew_point"]}°C    '
                f'Visibility: {cur["visibility"]}m\n'
            )

        return summary


if __name__ == '__main__':
    w = Weather()
    if w.fetch() is False:
        print("Can't get weather information.")
        exit(1)
    text = w.summary()
    print(text)
    
    high, highTime = w.highest()
    if high and highTime:
        print("high: ", high)
        print("highTime: ", highTime)
        print('highest temperature: ',
              f'{high}°C', highTime.strftime("at %I:%M %p on %A"))
    else:
        print("No highest data")
        exit(0)

    low, lowTime = w.lowest()
    if low and lowTime:
        print("low: ", low)
        print("lowTime: ", lowTime)
        print('lowest temperature: ',
              f'{low}°C', lowTime.strftime("at %I:%M %p on %A"))
    else:
        print("No lowest data")
        exit(0)

    if high > 35:
        print("so hot!!")
    elif high > 30:
        print("hot!!")

    if low < -3:
        print("so cold!!")
    elif low < 5:
        print("cold!!")
