#!/usr/bin/env python3
import re
import datetime
import time
from dateutil.relativedelta import relativedelta

DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


def parse(date):
    today = datetime.date.today()
    from_date = None
    to_date = None

    if date == "":
        from_date = datetime.date(1970, 1, 1)
        to_date = today

    # last day or year
    result = re.match(r"^\s*([0123]?\d)\s*$", date)
    if result:
        day = int(result.group(1))
        if day < 1 or day > 31:
            return None

        first_day = datetime.date(today.year, today.month, 1)
        if today.day >= day:
            from_date = first_day + relativedelta(day=day)
        else:
            from_date = first_day + relativedelta(months=-1, day=day)
        to_date = from_date + relativedelta(days=1)

    # year
    result = re.match(r"^\s*([12]\d\d\d)\s*$", date)
    if result:
        year = int(result.group(1))
        if year < 1970 or year > today.year:
            return None

        from_date = datetime.date(year, 1, 1)
        to_date = from_date + relativedelta(years=1)

    # last N days, weeks, months, years
    result = re.match(r"^\s*(\d+)([dDwWmMyY])\s*$", date)
    if result:
        num = int(result.group(1))
        days = DAYS[result.group(2).lower()]
        lastdays = datetime.timedelta(days=num*days)
        from_date = today - lastdays
        to_date = today

    # date mm/dd or mm-dd
    result = re.match(r"^\s*([10]*\d)[-/]([0123]*\d)\s*$", date)
    if result:
        month = int(result.group(1))
        day = int(result.group(2))
        if today.month > month:
            from_date = today + relativedelta(month=month, day=day)
        elif today.month == month:
            if today.day >= day:
                from_date = today + relativedelta(month=month, day=day)
            else:
                from_date = today + relativedelta(months=-1, day=day)
        else:
            from_date = today + relativedelta(years=-1, month=month, day=day)

        to_date = from_date + relativedelta(days=1)

    # date yyyy/mm/dd or yyyy-mm-dd
    result = re.match(r"^\s*(20\d\d)[-/]([10]*\d)[-/]([0123]*\d)\s*$", date)
    if result:
        year = int(result.group(1))
        month = int(result.group(2))
        day = int(result.group(3))
        d = datetime.date(year, month, day)
        if today < d:
            return None
        from_date = d
        to_date = from_date + relativedelta(days=1)

    # month or weekday
    result = re.match(r"^\s*(\w+)\s*$", date)
    if result:
        letter = result.group(1)
        n_month = None
        for fmt in ("%b", "%B"):
            try:
                n_month = time.strptime(letter, fmt).tm_mon
                if today.month >= n_month:
                    from_date = today + relativedelta(
                        month=n_month,
                        day=1
                    )
                else:
                    from_date = today + relativedelta(
                        years=-1,
                        month=n_month,
                        day=1
                    )
                to_date = from_date + relativedelta(months=1)
                break
            except ValueError:
                continue

        n_wday = None
        for fmt in ("%a", "%A"):
            try:
                n_wday = time.strptime(letter, fmt).tm_wday
                from_date = today + relativedelta(days=-6, weekday=n_wday)
                to_date = from_date + relativedelta(days=1)
            except ValueError:
                continue

    # today
    result = re.match(r"^\s*today\s*$", date)
    if result:
        from_date = today
        to_date = today + relativedelta(days=1)

    if from_date is None or to_date is None:
        return None

    return (from_date, to_date)


if __name__ == "__main__":
    dates = (
        "1", "29", "2020",
        "1d", "2w", "3m", "4y",
        "1/2", "12/31", "02-03",
        "wed", "Sunday", "Feb", "December", "today",
        ""
    )
    print("today:", datetime.date.today().strftime("%Y-%m-%d"))

    for date in dates:
        print(f"'{date}'")
        res = parse(date)
        if res:
            print("  from:", res[0].strftime("%Y-%m-%d"))
            print("    to:", res[1].strftime("%Y-%m-%d"))
