#!/usr/bin/env python3

import os
import datetime as dt
from datetime import datetime
import json
from tempfile import TemporaryDirectory
from pathlib import Path
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
    assert mes is not None
    assert mes.startswith('A low of')


def test_read_config():
    from tempfile import TemporaryDirectory
    from pathlib import Path

    with TemporaryDirectory() as dname:
        config_path = Path(dname) / "test_read_config.json"
        os.environ["MONITOR_CONFIG"] = str(config_path)

        normal_config = """
            {
                "book": {
                    "hello": "world"
                },
                "monitor": {
                    "temperature": {
                        "//": "//sampling_interval seconds",
                        "sampling_interval": 2,
                        "//": "//plot_interval seconds",
                        "plot_interval": 60,
                        "plot_buffer_size": 3000,
                        "sensor_path": "/tmp/w1_slave",
                        "room_hot_alert_threshold": 35.0,
                        "outside_hot_alert_threshold": 30.0,
                        "//pipe_alert_threshold": -5.0,
                        "pipe_alert_threshold": 1.0,
                        "forecast_interval_hours": 4
                    },
                    "servers": {
                        "ping_interval_sec": 60,
                        "previous_data_points": 10,
                        "ping_servers": {
                            "https://www.example.com/": {
                                "type": "Web"
                            },
                            "example.com": {
                                "type": "DNS"
                            },
                            "www.example.com": {
                                "type": "ICMP"
                            }
                        }
                    }
                }
            }
        """
        config_path.write_text(normal_config)
        conf = moni.read_config("servers")
        assert conf["ping_interval_sec"] == 60
        assert conf["previous_data_points"] == 10
        ping_servers = conf["ping_servers"]
        assert ping_servers["https://www.example.com/"]["type"] == "Web"
        assert ping_servers["example.com"]["type"] == "DNS"
        assert ping_servers["www.example.com"]["type"] == "ICMP"

        with pytest.raises(moni.MonitorError) as excinfo:
            _ = moni.read_config("no_key")
        assert "'no_key' key not found in" in str(excinfo.value)

        normal_config = """
            {
                "book": {
                    "hello": "world"
                }
            }
        """
        config_path.write_text(normal_config)
        with pytest.raises(moni.MonitorError) as excinfo:
            moni.read_config("no_key")
        assert "'monitor' key not found in" in str(excinfo.value)

        normal_config = """
            {
                "book": {
                    "hello": "world"
                },
            }
        """
        config_path.write_text(normal_config)
        with pytest.raises(json.decoder.JSONDecodeError) as excinfo:
            moni.read_config("no_key")

        os.environ["MONITOR_CONFIG"] = str(config_path) + "xxx"
        with pytest.raises(moni.MonitorError) as excinfo:
            moni.read_config("no_key")
        assert "cannot open configuration file" in str(excinfo.value)

        os.environ.pop("MONITOR_CONFIG")
        with pytest.raises(moni.MonitorError) as excinfo:
            moni.read_config("no_key")
        assert "no environment variable" in str(excinfo.value)


class TestServer:
    def test_get_status(self):
        with TemporaryDirectory() as dname:
            config_path = Path(dname) / "test_read_config.json"
            os.environ["MONITOR_CONFIG"] = str(config_path)

            normal_config = """
                {
                    "monitor": {
                        "servers": {
                            "ping_interval_sec": 60,
                            "previous_data_points": 10,
                            "ping_servers": {
                                "https://www.example.com/": {
                                    "type": "Web"
                                },
                                "example.com": {
                                    "type": "DNS"
                                },
                                "www.example.com": {
                                    "type": "ICMP"
                                },
                                "example.invalid": {
                                    "type": "ICMP"
                                },
                                "www.example.invalid": {
                                    "type": "DNS"
                                }
                            }
                        }
                    }
                }
            """
            config_path.write_text(normal_config)
            servers = moni.Server()

        status = servers.get_status()
        for s in status:
            if "invalid" in s:
                assert status[s] is False
            else:
                assert status[s] is True

    delay_and_return = {
        "good": (
            {
                "localhost_icmp": {
                    "alive": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                    "expected": [True, None, None, None, None,
                                 None, None, None, None, None, None],
                },
                "localhost_web": {
                    "alive": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
                    "expected": [True, "good", None, "noisy", None,
                                 None, None, None, None, None, None],
                },
                "localhost_dns": {
                    "alive": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    "expected": ["good", "noisy", None, None, None,
                                 None, None, None, None, False, None],
                },
            },
            {
                0.9: "good",
                0.0: "noisy"
            },
            None,
            '''{
                "monitor": {
                    "servers": {
                        "ping_interval_sec": 60,
                        "previous_data_points": 10,
                        "ping_servers": {
                            "localhost_icmp": {
                                "type": "ICMP"
                            },
                            "localhost_web": {
                                "type": "Web"
                            },
                            "localhost_dns": {
                                "type": "DNS"
                            }
                        }
                    }
                }
            }''',
        ),
        "noisy": (
            {
                "localhost_icmp": {
                    "alive": [1, 0, 1, 0, 1,
                              1, 1, 1, 1, 1,
                              1, 1, 1, 1, 1],
                    "expected": [True, "good", None, "noisy", None,
                                 None, None, None, None, None,
                                 None, "good", None, True, None],
                },
                "localhost_web": {
                    "alive": [0, 0, 0, 0, 0,
                              0, 0, 0, 0, 0,
                              1, 1, 1, 1, 1],
                    "expected": ["good", "noisy", None, None, None,
                                 None, None, None, None, False,
                                 "noisy", None, None, None, None],
                },
                "localhost_dns": {
                    "alive": [1, 0, 1, 0, 1,
                              1, 1, 1, 1, 1,
                              1, 1, 1, 0, 1],
                    "expected": [True, "good", None, "noisy", None,
                                 None, None, None, None, None,
                                 None, "good", None, None, None],
                }
            },
            {
                0.9: "good",
                0.0: "noisy"
            },
            (False, True),
            '''{
                "monitor": {
                    "servers": {
                        "ping_interval_sec": 60,
                        "previous_data_points": 10,
                        "ping_servers": {
                            "localhost_icmp": {
                                "type": "ICMP"
                            },
                            "localhost_web": {
                                "type": "Web"
                            },
                            "localhost_dns": {
                                "type": "DNS"
                            }
                        }
                    }
                }
            }''',
        ),
        "bad": (
            {
                "localhost_icmp": {
                    "alive": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                    "expected": ["up", "good", "noisy",
                                 None, None, None, None, None, None, None,
                                 "down"]
                },
                "localhost_web": {
                    "alive": [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                    "expected": ["good", None, None, None, None,
                                 None, None, None, None, None,
                                 "up"]
                },
                "localhost_dns": {
                    "alive": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                    "expected": ["up", "good", "noisy", None, None,
                                 None, None, None, None, None,
                                 None]
                },
            },
            {
                0.9: "good",
                0.0: "noisy"
            },
            ("down", "up"),
            '''{
                "monitor": {
                    "servers": {
                        "ping_interval_sec": 60,
                        "alert_delay": 0,
                        "previous_data_points": 10,
                        "ping_servers": {
                            "localhost_icmp": {
                                "type": "ICMP"
                            },
                            "localhost_web": {
                                "type": "Web"
                            },
                            "localhost_dns": {
                                "type": "DNS"
                            }
                        }
                    }
                }
            }''',
        ),
    }

    @pytest.mark.parametrize(
        "targets, classes, class10, config",
        list(delay_and_return.values()),
        ids=list(delay_and_return.keys()))
    def test_is_changed(self, mocker, targets, classes, class10, config):
        for t in targets:
            assert len(targets[t]["alive"]) == len(targets[t]["expected"])

        return_values_icmp = [
            [(False, "ICMP mocker"), (True, "ICMP mocker")][x]
            for x in targets["localhost_icmp"]["alive"]
        ]
        mocker.patch(
            "monibot.ping.ICMP.is_alive",
            side_effect=return_values_icmp)
        return_values_web = [
            [(False, "Web mocker"), (True, "Web mocker")][x]
            for x in targets["localhost_web"]["alive"]
        ]
        mocker.patch(
            "monibot.ping.Web.is_alive",
            side_effect=return_values_web)
        return_values_dns = [
            [(False, "DNS mocker"), (True, "DNS mocker")][x]
            for x in targets["localhost_dns"]["alive"]
        ]
        mocker.patch(
            "monibot.ping.DNS.is_alive",
            side_effect=return_values_dns)

        with TemporaryDirectory() as dname:
            config_path = Path(dname) / "test_read_config.json"
            os.environ["MONITOR_CONFIG"] = str(config_path)
            config_path.write_text(config)
            servers = moni.Server()
            for i, _ in enumerate(return_values_dns):
                if class10 is None:
                    changes = servers.is_changed(classes=classes)
                else:
                    changes = servers.is_changed(
                        classes=classes,
                        class1=class10[1],
                        class0=class10[0])

                for target in targets:
                    exp = targets[target]["expected"][i]
                    state = changes.get(target)
                    assert state == exp, f"{i}: {target}\n{changes}"


if __name__ == '__main__':
    pytest.main(['-v', __file__])
