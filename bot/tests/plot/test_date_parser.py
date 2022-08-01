import pytest
import datetime
from freezegun import freeze_time
from co2 import dateparser

TODAY = datetime.date(2020, 3, 1)

parse_date_patterns = [
    ("", (datetime.date(1970, 1, 1), datetime.date(2020, 3, 1))),
    ("xxx", None),
    ("0", None),
    ("1", (datetime.date(2020, 3, 1), datetime.date(2020, 3, 2))),
    ("28", (datetime.date(2020, 2, 28), datetime.date(2020, 2, 29))),
    ("32", None),
    ("0000", None),
    ("1969", None),
    ("1970", (datetime.date(1970, 1, 1), datetime.date(1971, 1, 1))),
    ("2020", (datetime.date(2020, 1, 1), datetime.date(2021, 1, 1))),
    ("2099", None),
    ("1d", (TODAY-datetime.timedelta(days=1), TODAY)),
    ("2w", (TODAY-datetime.timedelta(days=7*2), TODAY)),
    ("3m", (TODAY-datetime.timedelta(days=30*3), TODAY)),
    ("4y", (TODAY-datetime.timedelta(days=365*4), TODAY)),
    ("5D", (TODAY-datetime.timedelta(days=5), TODAY)),
    ("6W", (TODAY-datetime.timedelta(days=7*6), TODAY)),
    ("7M", (TODAY-datetime.timedelta(days=30*7), TODAY)),
    ("8Y", (TODAY-datetime.timedelta(days=365*8), TODAY)),
    ("1z", None),
    ("12/31", (datetime.date(2019, 12, 31), datetime.date(2020, 1, 1))),
    ("12-31", (datetime.date(2019, 12, 31), datetime.date(2020, 1, 1))),
    ("01/31", (datetime.date(2020, 1, 31), datetime.date(2020, 2, 1))),
    ("11-09", (datetime.date(2019, 11, 9), datetime.date(2019, 11, 10))),
    ("02/29", (datetime.date(2020, 2, 29), datetime.date(2020, 3, 1))),
    ("21/31", None),
    ("2020/02/29", (datetime.date(2020, 2, 29), datetime.date(2020, 3, 1))),
    ("2020-02-29", (datetime.date(2020, 2, 29), datetime.date(2020, 3, 1))),
    ("wed", (datetime.date(2020, 2, 26), datetime.date(2020, 2, 27))),
    ("wednesday", (datetime.date(2020, 2, 26), datetime.date(2020, 2, 27))),
    ("feb", (datetime.date(2020, 2, 1), datetime.date(2020, 3, 1))),
    ("february", (datetime.date(2020, 2, 1), datetime.date(2020, 3, 1))),
    ("dec", (datetime.date(2019, 12, 1), datetime.date(2020, 1, 1))),
    ("december", (datetime.date(2019, 12, 1), datetime.date(2020, 1, 1))),
    ("today", (datetime.date(2020, 3, 1), datetime.date(2020, 3, 2))),
]


@pytest.mark.parametrize("date, expected", parse_date_patterns)
@freeze_time("2020-03-01")
def test_dateparser(date, expected, monkeypatch):
    assert datetime.date.today() == TODAY
    actual = dateparser.parse(date)
    assert expected == actual
