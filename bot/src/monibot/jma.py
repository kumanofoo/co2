import contextlib
import json
import logging
import math
import os
from datetime import datetime, time, timedelta, timezone

import requests
from astral import LocationInfo
from astral.sun import sun

from monibot.ameoffice import AMEDAS_OFFICES

log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
UTC = timezone.utc


class WeatherError(Exception):
    pass


class NoEnvironmetVariableError(WeatherError):
    def __init__(self) -> None:
        super().__init__("no environment variable MY_PLACE")


AMEDAS_DEVICE_URL = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"
resp = requests.get(AMEDAS_DEVICE_URL, timeout=(3.0, 10.0))
resp.raise_for_status()
AMEDAS_DEVICES: dict[str, dict] = json.loads(resp.text)


def amedas_latlon60to10(point: dict) -> tuple[float, float]:
    lat10 = float(point["lat"][0]) + float(point["lat"][1]) / 60.0
    lon10 = float(point["lon"][0]) + float(point["lon"][1]) / 60.0
    return (lat10, lon10)


def nearest_amedas_device_id(lat: float, lon: float, devices: list[str] | None = None) -> str:
    if devices is None:
        devices = list(AMEDAS_DEVICES.keys())
    return min(devices, key=lambda p: math.dist(amedas_latlon60to10(AMEDAS_DEVICES[p]), (float(lat), float(lon))))


def nearest_temperature_point(lat: float, lon: float) -> str:
    key = nearest_amedas_device_id(lat, lon)[:2]
    offices = AMEDAS_OFFICES[key]["offices"]
    temp_points = []
    for office in offices:
        forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{office}.json"
        forecast = None
        try:
            resp = requests.get(forecast_url, timeout=(3.0, 10.0))
            resp.raise_for_status()
            forecast = json.loads(resp.text)
        except (requests.exceptions.RequestException, ValueError):
            log.exception("failed to download a freacast of %s due to exceptions.", office)
            continue
        if forecast is None:
            log.error("no freacast data of %s", office)
            continue
        areas = forecast[0]["timeSeries"][2]["areas"]
        temp_points.extend([(office, area["area"]["code"]) for area in areas])
    point = nearest_amedas_device_id(lat, lon, [t[1] for t in temp_points])
    return next(t for t in temp_points if t[1] == point)


_amedas_example = {
    "pressure": [1020.7, 0],  # station pressure [hPa]
    "normalPressure": [1021.2, 0],  # sea level pressure [hPa]
    "temp": [20.0, 0],  # [degree celsius]
    "humidity": [61, 0],  # [%]
    "visibility": [20000.0, 0],  # [m]
    "snow": [None, 5],  # [cm]
    "weather": [0, 0],
    "snow1h": [0, 6],
    "snow6h": [0, 6],
    "snow12h": [0, 6],
    "snow24h": [0, 6],
    "sun10m": [10, 0],
    "sun1h": [1.0, 0],
    "precipitation10m": [0.0, 0],
    "precipitation1h": [0.0, 0],
    "precipitation3h": [0.0, 0],
    "precipitation24h": [0.0, 0],
    "windDirection": [15, 0],
    "wind": [1.2, 0],
}


#
# |------------------|---------|-------|-------|-------------|-------|-------------|-------|-------------|
# |           sun10m |      no |   yes |    no |         yes |    no |         yes |    no |         yes |
# | precipitation10m |      no |    no |   yes |         yes |    no |          no |   yes |         yes |
# |           snow1h |      no |    no |    no |          no |   yes |         yes |   yes |         yes |
# |       visibility |     yes |    no |    no |          no |    no |          no |    no |          no |
# |------------------|---------|-------|-------|-------------|-------|-------------|-------|-------------|
# |          weather | cloudly | sunny | rainy | light rainy | snowy | light snowy | snowy | light snowy |
# |------------------|---------|-------|-------|-------------|-------|-------------|-------|-------------|
#
# foggy:
#   visibility < 1000
#   precipitation10m is no
#   snow1h is no
#


def amedas_weather(*, sunshine: bool | None, precipitation: bool | None, snow: bool, visibility: bool, night: bool) -> int:
    weather_tab = {
        False: {
            False: {
                False: 1,  # Cloudly
                True: 10,  # Snowy
            },
            True: {
                False: 7,  # Rainy
                True: 10,  # Snowy
            },
        },
        True: {
            False: {
                False: 0,  # Sunny
                True: 10,  # Snowy
            },
            True: {
                False: 13,  # Rain shower
                True: 14,  # Snow shower
            },
        },
    }
    night_weather_tab = {
        False: {
            False: 100,  # Moon light
            True: 10,  # Snowy
        },
        True: {
            False: 7,  # Rainy
            True: 10,  # Snowy
        },
    }
    if sunshine is None or precipitation is None:
        return 999  # Something weird is huppening
    if not visibility and not precipitation and not snow:
        return 3  # Foggy
    if night:
        return night_weather_tab[precipitation][snow]
    return weather_tab[sunshine][precipitation][snow]


class Amedas:
    def __init__(self, amedas_device_id: str) -> None:
        self.amedas_device_id = amedas_device_id
        self.amedas_device = AMEDAS_DEVICES[amedas_device_id]
        self.latest_time = 0
        self.amedas = {}
        lat, lon = amedas_latlon60to10(self.amedas_device)
        self.device = LocationInfo(self.amedas_device["enName"], "Japan", timezone="Asia/Tokyo", latitude=lat, longitude=lon)
        self.AMEDAS_EMOJI = {
            0: ":sunny:",
            1: ":cloud:",
            2: ":fog:",
            3: ":fogggy:",
            4: ":umbrella_with_rain_drops:",
            5: ":umbrella_with_rain_drops:",
            6: ":fog:",
            7: ":umbrella_with_rain_drops:",
            8: ":umbrella_with_rain_drops:",
            9: ":snowflake:",
            10: ":snowman:",
            11: ":snow_cloud:",
            12: ":snow_cloud:",
            13: ":partry_sunny_rain:",
            14: ":partry_sunny_rain:",
            15: ":snowflake:",
            16: ":lightning:",
            100: ":night_with_stars:",
            999: ":construction:",
        }
        self.AMEDAS_WIND_DIR = {
            0: "--",
            1: "NNE",
            2: "NE",
            3: "ENE",
            4: "E",
            5: "ESE",
            6: "SE",
            7: "SSE",
            8: "S",
            9: "SSW",
            10: "SW",
            11: "WSW",
            12: "W",
            13: "WNW",
            14: "NW",
            15: "NNW",
            16: "N",
        }
        self.DIR2ARROW = {
            "--": "・",
            "NNE": "⇙",
            "NE": "⇙",
            "ENE": "⇐",
            "E": "⇐",
            "ESE": "⇖",
            "SE": "⇖",
            "SSE": "⇑",
            "S": "⇑",
            "SSW": "⇗",
            "SW": "⇗",
            "WSW": "⇒",
            "W": "⇒",
            "WNW": "⇘",
            "NW": "⇘",
            "NNW": "⇓",
            "N": "⇓",
        }

    def value(self, key: str) -> float | None:
        value_length = 2
        amedas = self.amedas[self.amedas_device_id]
        v = amedas.get(key)
        return v[0] if v is not None and len(v) == value_length and v[1] == 0 else None

    def summary_param(self) -> None:
        params = [
            "windDirection",
            "visibility",
            "temp",
            "humidity",
            "wind",
            "sun10m",
            "precipitation10m",
            "snow1h",
        ]
        values = {}
        for key in params:
            values[key] = self.value(key)
        return values

    def fetch(self) -> None:
        latest_time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        resp = requests.get(latest_time_url, timeout=(3.0, 10.0))
        resp.raise_for_status()
        # latest_time.txt: 2024-10-27T10:20:00+09:00
        dt = datetime.fromisoformat(resp.text)
        latest_time = int(dt.strftime("%Y%m%d%H%M%S"))
        if self.latest_time >= latest_time and self.amedas:
            return
        amedas_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{latest_time}.json"
        resp = requests.get(amedas_url, timeout=(3.0, 10.0))
        resp.raise_for_status()
        self.amedas = json.loads(resp.text)
        self.latest_time = latest_time

    def summary(self, md_type: str = "") -> str | None:
        self.fetch()
        if not self.amedas:
            return None
        p = self.summary_param()
        wd: float | None = p["windDirection"] if p["windDirection"] is not None else 0
        sunshine: bool | None = p["sun10m"] > 0.0 if p["sun10m"] is not None else None
        precipitation: bool | None = p["precipitation10m"] > 0.0 if p["precipitation10m"] is not None else None
        snow: bool = p["snow1h"] > 0.0 if p["snow1h"] is not None else False
        visibility: float = p["visibility"] if p["visibility"] is not None else 20000
        temp: str = p["temp"] if p["temp"] is not None else "- "
        humidity: str = p["humidity"] if p["humidity"] is not None else "- "
        wind: str = p["wind"] if p["wind"] is not None else "- "
        minimum_visibility = 1000.0
        emoji_id = amedas_weather(sunshine=sunshine, precipitation=precipitation, snow=snow, visibility=visibility > minimum_visibility, night=self.is_night())
        if md_type == "slack":
            summary = f"*{self.AMEDAS_EMOJI[emoji_id]} {temp}℃*\n"
        elif md_type == "zulip":
            summary = f"**{self.AMEDAS_EMOJI[emoji_id]} {temp}℃**\n"
        else:
            summary = f"{self.AMEDAS_EMOJI[emoji_id]} {temp}℃\n"
        summary += f"{self.DIR2ARROW[self.AMEDAS_WIND_DIR[wd]]} {wind}m/s "
        summary += f"{self.AMEDAS_WIND_DIR[wd]}\n"
        summary += f"Humidity: {humidity}%\n"
        summary += f"Visibility: {visibility}\n"
        latest_time = datetime.strptime(str(self.latest_time), "%Y%m%d%H%M%S").replace(tzinfo=JST)
        with contextlib.suppress(Exception):
            summary += f"{self.amedas_device.get('enName')} {latest_time}\n"
        return summary

    def is_night(self) -> bool:
        now = datetime.now(JST)
        today_start_date = datetime.combine(now.date(), time.min, tzinfo=JST).astimezone(UTC).date()
        today_noon_date = datetime.combine(now.date(), time(12, 0, 0), tzinfo=JST).astimezone(UTC).date()
        dawn = sun(self.device.observer, date=today_start_date)["dawn"]
        dusk = sun(self.device.observer, date=today_noon_date)["dusk"]
        return dawn > now or dusk < now


class JMAForecast:
    def __init__(self, offices: str = "016000", area_code: str = "14163") -> None:
        self.offices: str = offices
        self.area_code: str = area_code
        self.reportDatetime: datetime = datetime.fromtimestamp(0, tz=UTC)
        self.lowest: tuple[float | None, datetime | None] = (None, None)
        self.highest: tuple[float | None, datetime | None] = (None, None)
        self.lowest_reference_hour = 5
        self.highest_reference_hour = 11

    def fetch(self) -> None:
        self.lowest = (None, None)
        self.highest = (None, None)
        forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{self.offices}.json"
        resp = requests.get(forecast_url, timeout=(3.0, 10.0))
        resp.raise_for_status()
        forecast = json.loads(resp.text)
        self.reportDatetime = datetime.fromisoformat(forecast[0]["reportDatetime"])
        areas = forecast[0]["timeSeries"][2]["areas"]
        self.area_name = None
        temps_json = None
        for area in areas:
            log.debug(area)
            if area["area"]["code"] == self.area_code:
                self.area_name = area["area"]["name"]
                temps_json = area["temps"]
                break
        if self.area_name and temps_json:
            try:
                time_defines = forecast[0]["timeSeries"][2]["timeDefines"]
            except KeyError:
                return
        else:
            return

        log.debug(self.area_name)
        log.debug(temps_json)
        log.debug(time_defines)
        now = datetime.now(JST)
        lowest_target = now.date()
        highest_target = now.date()
        if now.hour > self.lowest_reference_hour:
            lowest_target = now.date() + timedelta(days=1)
        if now.hour > self.highest_reference_hour:
            highest_target = now.date() + timedelta(days=1)

        lowests = []
        lowests_dt = []
        highests = []
        highests_dt = []
        for temp, time_define in zip(temps_json, time_defines):
            t = datetime.fromisoformat(time_define)
            if lowest_target == t.date():
                lowests.append(float(temp))
                lowests_dt.append(t)
            if highest_target == t.date():
                highests.append(float(temp))
                highests_dt.append(t)
        self.lowest = (lowests[0], datetime.combine(lowests_dt[0].date(), time(5, 0, 0)).replace(tzinfo=JST))
        self.highest = (highests[-1], datetime.combine(highests_dt[-1].date(), time(14, 0, 0)).replace(tzinfo=JST))


class Weather:
    """
    fetch weather forecast from JMA
    """

    def __init__(self) -> None:
        my_place = os.environ.get("MY_PLACE")
        if not my_place:
            raise NoEnvironmetVariableError

        lat, lon = my_place.split(":")
        self.lat, self.lon = float(lat), float(lon)
        self.amedas = Amedas(nearest_amedas_device_id(self.lat, self.lon))
        self.offices, self.area_code = nearest_temperature_point(self.lat, self.lon)
        self.forecast = JMAForecast(self.offices, self.area_code)

    def fetch(self) -> None:
        self.amedas.fetch()
        self.forecast.fetch()

    def lowest_highest(self) -> tuple[tuple[float | None, datetime | None], tuple[float | None, datetime | None]]:
        self.forecast.fetch()
        return self.forecast.lowest, self.forecast.highest

    def lowest(self) -> tuple[float | None, datetime | None]:
        self.forecast.fetch()
        return self.forecast.lowest

    def highest(self) -> tuple[float | None, datetime | None]:
        self.forecast.fetch()
        return self.forecast.highest

    def summary(self, md_type: str = "") -> str | None:
        return self.amedas.summary(md_type)


def amedas_example() -> None:
    print()
    print("AMEDAS EXAMPLE")
    lat, lon = 35.02487516235576, 135.7633583655347
    a = Amedas(nearest_amedas_device_id(lat, lon))
    print(a.summary())
    print("---------")


def forecast_example() -> None:
    offices, area_code = "390000", "74372"  # Cape Muroto, Kochi
    print()
    print("FORECAST EXAMPLE")
    f = JMAForecast(offices, area_code)
    f.fetch()
    print(f"lowest: {f.lowest[0]}℃  ({f.lowest[1]})")
    print(f"highest: {f.highest[0]}℃  ({f.highest[1]})")
    print("---------")


def weather_example() -> None:
    print()
    print("WEATHER EXAMPLE")
    w = Weather()
    print("---------")
    print(w.summary())
    lowest, highest = w.lowest_highest()
    print(f"lowest: {lowest[0]}℃  ({lowest[1]})")
    print(f"highest: {highest[0]}℃  ({highest[1]})")

    location = [
        (43.14639284285612, 140.99053459943423),  # Otaru, Hokkaido
        (42.924099483986915, 143.19602599700715),  # Obihiro, Hokkaido
        (43.775245297823226, 143.0172641696748),  # Engaru, Hokkaido
        (38.32646496882242, 140.8816908753437),  # Izumi-ku, Sendai
        (38.269147475058865, 140.87048836795663),  # Aoba-ku, Sendai
        (35.68541904732207, 139.75278177143505),  # Imperial Palace
        (31.58883500714792, 130.64999657232707),  # Sakurajima, Kagoshima
        (30.357831681487646, 130.55970268707986),  # Yakushima, Kagoshima
    ]
    for lat, lon in location:
        os.environ["MY_PLACE"] = f"{lat}:{lon}"
        w = Weather()
        print("---------")
        print(w.summary())
        lowest, highest = w.lowest_highest()
        print(f"lowest: {lowest[0]}℃  ({lowest[1]})")
        print(f"highest: {highest[0]}℃  ({highest[1]})")


if __name__ == "__main__":
    amedas_example()
    forecast_example()
    weather_example()
    w = Weather()
    w.fetch()
    text = w.summary()
    print(text)

    high, high_time = w.highest()
    if high_time is not None:
        print("highest temperature: ", f"{high}°C", high_time.strftime("at %I:%M %p on %A"))

    low, low_time = w.lowest()
    if low_time is not None:
        print("lowest temperature: ", f"{low}°C", low_time.strftime("at %I:%M %p on %A"))

    HIGH_THRESHOLD = (35, 30)
    LOW_THRESHOLD = (-3, 5)
    if high is not None:
        if high > HIGH_THRESHOLD[0]:
            print("so hot!!")
        elif high > HIGH_THRESHOLD[1]:
            print("hot!!")

    if low is not None:
        if low < LOW_THRESHOLD[0]:
            print("so cold!!")
        elif low < LOW_THRESHOLD[1]:
            print("cold!!")
