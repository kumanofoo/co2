#!/usr/bin/env python3

import time
import queue
from datetime import datetime
import monibot.cron as cron
import monibot.command as cmd


def test_cron_queue():
    def sensor(where, what, unit=''):
        dt = datetime.now()
        res = (f"{what} in {where} is 10.0 {unit}")
        return (res, dt)

    where = "living"
    what = "temperature"
    unit = "°C"
    interval_sec = 3
    q = queue.Queue()
    c = cron.Cron(
             sensor,
             args=(where, what),
             kwargs={"unit": unit},
             interval_sec=interval_sec,
             queue=q
        )
    c.start()
    (mes, dt) = q.get()
    assert mes == f"{what} in {where} is 10.0 {unit}"
    previous_dt = dt
    for i in range(2):
        (mes, dt) = q.get()
        assert mes == f"{what} in {where} is 10.0 {unit}"
        assert int((dt-previous_dt).total_seconds()) == interval_sec
        previous_dt = dt
    c.abort()
    c.join()


def test_cron_command(mocker):
    cron_command_mock = mocker.patch.object(cmd.Command, 'respond')

    def sensor(where, what, unit=''):
        res = (f"{what} in {where} is 10.0 {unit}")
        return res

    where = "living"
    what = "temperature"
    unit = "°C"
    interval_sec = 3
    command = cmd.Command()
    c = cron.Cron(
             sensor,
             args=(where, what),
             kwargs={"unit": unit},
             interval_sec=interval_sec,
             command=command
        )
    c.start()
    time.sleep(5)
    c.abort()
    c.join()
    assert command.message == f"{what} in {where} is 10.0 {unit}"
    assert cron_command_mock.call_count == 2
