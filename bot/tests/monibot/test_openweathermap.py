#!/usr/bin/env python3

import pytest
import os
import datetime
import monibot.openweathermap as weather

testdir = 'tests/monibot'


def requests_mock(*args, **kwargs):
    class MockResponse:
        def __init__(self, text, status_code):
            self.status_code = status_code
            self.text = text

    try:
        f = open(f'{testdir}/test_openweathermap_response_mock.txt',
                 encoding='utf-8')
    except IOError as e:
        print(e)
        raise(e)

    return MockResponse(f.read(), 200)


def test_weather_init_raise_my_place():
    os.environ['MY_PLACE'] = ''
    os.environ['OPENWEATHER_API_KEY'] = 'xxxx'
    with pytest.raises(weather.WeatherError):
        weather.Weather()


def test_weather_init_raise_dark_sky_key():
    os.environ['MY_PLACE'] = 'xxxx:yyyy'
    os.environ['OPENWEATHER_API_KEY'] = ''
    with pytest.raises(weather.WeatherError):
        weather.Weather()


def test_weather_lowest(mocker):
    mocker.patch('monibot.openweathermap.requests.get',
                 side_effect=requests_mock)
    os.environ['MY_PLACE'] = 'xxxx:yyyy'
    os.environ['OPENWEATHER_API_KEY'] = 'xxxx'

    w = weather.Weather()

    low, lowTime = w.lowest()
    assert type(low) == float
    assert low == 0.96
    assert type(lowTime) == datetime.datetime


def test_weather_highest(mocker):
    mocker.patch('monibot.openweathermap.requests.get',
                 side_effect=requests_mock)
    os.environ['MY_PLACE'] = 'xxxx:yyyy'
    os.environ['OPENWEATHER_API_KEY'] = 'xxxx'

    w = weather.Weather()
    high, highTime = w.highest()
    assert type(high) == float
    assert high == 8.56
    assert type(highTime) == datetime.datetime


if __name__ == '__main__':
    pytest.main(['-v', __file__])
