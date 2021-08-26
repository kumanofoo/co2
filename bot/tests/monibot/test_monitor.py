#!/usr/bin/env python3

import os
import datetime as dt
from datetime import datetime
import pytest
import monibot.monitor as moni

testdir = 'tests/monibot'


@pytest.mark.parametrize(('lowest', 'highest', 'days', 'expected'), [
    (20, 30, 0, '===='),
    (20, 35, 0, '===='),
    (-0.5, 30, 0, '===='),
    (-10, 30, 0, '===='),
    (20, 30, 1, '===='),
    (20, 35, 1, '====It will be too hot!!'),
    (31, 20, 1, '====You become butter...'),
    (-4, -0.5, 1, '====It will be too cold!!'),
    (-10, 30, 1, '====keep your pipes!!'),
])
def test_outsidetemperature(mocker, lowest, highest, days, expected):
    os.environ['MONITOR_CONFIG'] = f'{testdir}/monitor-test.conf'

    mocker.patch('monibot.monitor.Weather.__init__', return_value=None)
    mocker.patch('monibot.monitor.Weather.fetch')

    date = datetime.today() + dt.timedelta(days=days)
    mocker.patch('monibot.monitor.Weather.lowest',
                 return_value=(lowest, date))
    mocker.patch('monibot.monitor.Weather.highest',
                 return_value=(highest, date))

    outside = moni.OutsideTemperature()
    mes = '===='
    mes += outside.check_temperature()
    assert mes.startswith(expected)

    mes = outside.fetch_temperature()
    assert mes.startswith('A low of')


if __name__ == '__main__':
    pytest.main(['-v', __file__])
