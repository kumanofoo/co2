# TEST JMA MODULE
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import freezegun
import monibot.jma
import pytest
import requests
from pytest_mock import MockerFixture

HTTP_200_OK = 200


class MockResponse:
    def __init__(self, text: str, status_code: int) -> None:
        self.status_code = status_code
        self.text = text
        if status_code == HTTP_200_OK:
            self.raise_for_status = Mock()
        else:
            self.raise_for_status = self.mock_raise_for_status

    def mock_raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError


def test_nearest_temperature_point(mocker: MockerFixture) -> None:
    expected = ("260000", "61286")

    def requests_mock(*_args: tuple, **_kwargs: dict) -> MockResponse:
        with Path(Path(__file__).parent, "jma/260000.json").open("r", encoding="utf-8") as f:
            text = f.read()
        return MockResponse(text, HTTP_200_OK)

    mocker.patch("monibot.jma.requests.get", side_effect=requests_mock)
    p = monibot.jma.nearest_temperature_point(35.02308200312201, 135.76355916763444)
    assert p == expected


@pytest.mark.parametrize(
    ("expected", "params"),
    [
        pytest.param(
            999,  # Unknown
            {
                "sunshine": None,
                "precipitation": None,
                "snow": False,
                "visibility": False,
                "night": False,
            },
        ),
        pytest.param(
            3,  # Foggy
            {
                "sunshine": False,
                "precipitation": False,
                "snow": False,
                "visibility": False,
                "night": False,
            },
        ),
        pytest.param(
            1,  # Cloudly
            {
                "sunshine": False,
                "precipitation": False,
                "snow": False,
                "visibility": True,
                "night": False,
            },
        ),
        pytest.param(
            0,  # Sunny
            {
                "sunshine": True,
                "precipitation": False,
                "snow": False,
                "visibility": True,
                "night": False,
            },
        ),
        pytest.param(
            13,  # Rain shower
            {
                "sunshine": True,
                "precipitation": True,
                "snow": False,
                "visibility": True,
                "night": False,
            },
        ),
        pytest.param(
            7,  # Rain shower
            {
                "sunshine": False,
                "precipitation": True,
                "snow": False,
                "visibility": True,
                "night": False,
            },
        ),
        pytest.param(
            100,  # Moon light
            {
                "sunshine": False,
                "precipitation": False,
                "snow": False,
                "visibility": True,
                "night": True,
            },
        ),
    ],
)
def test_amedas_weather(expected: int, params: dict) -> None:
    code = monibot.jma.amedas_weather(**params)
    assert code == expected


@pytest.mark.parametrize(
    ("expected", "md_type"),
    [
        pytest.param(
            ":night_with_stars: 10.5℃\n⇖ 0.8m/s ESE\nHumidity: 67%\nVisibility: 20000.0\nSapporo 2024-10-27 10:30:00+09:00\n",
            "",
        ),
        pytest.param(
            "*:night_with_stars: 10.5℃*\n⇖ 0.8m/s ESE\nHumidity: 67%\nVisibility: 20000.0\nSapporo 2024-10-27 10:30:00+09:00\n",
            "slack",
        ),
        pytest.param(
            "**:night_with_stars: 10.5℃**\n⇖ 0.8m/s ESE\nHumidity: 67%\nVisibility: 20000.0\nSapporo 2024-10-27 10:30:00+09:00\n",
            "zulip",
        ),
    ],
)
@freezegun.freeze_time("2024-10-27 10:40:00", tz_offset=9)
def test_amedas_summary(mocker: MockerFixture, expected: str, md_type: str) -> None:
    latest_time_txt = "2024-10-27T10:30:00+09:00"
    latest_time = "20241027103000"
    sapporo = "14163"

    def requests_mock(*args: tuple, **_kwargs: dict) -> MockResponse:
        if args[0] == "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt":
            return MockResponse(latest_time_txt, 200)
        if args[0] == f"https://www.jma.go.jp/bosai/amedas/data/map/{latest_time}.json":
            with Path(Path(__file__).parent, f"jma/{latest_time}.json").open("r", encoding="utf-8") as f:
                text = f.read()
            return MockResponse(text, 200)
        return MockResponse(None, 404)

    mocker.patch("monibot.jma.requests.get", side_effect=requests_mock)
    a = monibot.jma.Amedas(sapporo)
    summary = a.summary(md_type)
    assert summary == expected


@freezegun.freeze_time("2024-10-27 10:40:00", tz_offset=9)
def test_jmaforecast(mocker: MockerFixture) -> None:
    offices, area_code = "390000", "74372"  # Cape Muroto, Kochi
    jst = timezone(timedelta(hours=9))
    lowest_datetime = datetime(2024, 10, 28, 5, 0, tzinfo=jst)
    highest_datetime = datetime(2024, 10, 28, 14, 0, tzinfo=jst)
    expected_lowest = (20.0, lowest_datetime)
    expected_highest = (23.0, highest_datetime)

    def request_mock(*_args: tuple, **_kwargs: dict) -> MockResponse:
        with Path(Path(__file__).parent, f"jma/{offices}.json").open("r", encoding="utf-8") as f:
            text = f.read()
            return MockResponse(text, 200)
        return MockResponse(None, 404)

    mocker.patch("monibot.jma.requests.get", side_effect=request_mock)
    f = monibot.jma.JMAForecast(offices, area_code)
    f.fetch()
    assert f.lowest == expected_lowest
    assert f.highest == expected_highest
