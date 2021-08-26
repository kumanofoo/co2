""" Plot co2 from sqlite3 """

import os
import json
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import sqlite3
from datetime import datetime, timedelta, time, timezone
plt.switch_backend('Agg')


DEFAULT_DATABASE = 'measurement.db'
DEFAULT_TABLE = 'measurement'


def read_database(database, table, tz='UTC'):
    """
    Read co2 from database and create DataFrame

    Parameters
    ----------
    database : str
        SQLite3 database filename
    table : str
        table name in database
    tz : str
        timezone

    Returns
    -------
    df : DataFrame
         Set DataFrame index using timestamp(UNIX time ns) column
    """
    conn = sqlite3.connect(database)
    try:
        df = pd.read_sql_query('SELECT * FROM %s' % table, conn)
    except Exception as e:
        print(e)
        exit(0)
    df.timestamp = pd.to_timedelta(df.timestamp, unit='ns') \
        + pd.to_datetime('1970/1/1', utc=True)
    df = df.set_index('timestamp')
    df.index = df.index.tz_convert(tz)

    return df


def guess_xsv(data):
    """
    Convert CSV, TSV, SSV and JSON into dict

    Parameters
    ----------
    data : str
        CSV, TSV, SSV or JSON

    Returns
    -------
    dict :
        Converted data into dict not into list
    """
    for delimiter in [',', None]:
        try:
            res = list(map(lambda x: float(x), data.split(delimiter)))
            res_dict = {k: v for k, v in enumerate(res)}
            return res_dict
        except ValueError:
            continue

    try:
        res = json.loads(data)
        if isinstance(res, list):
            res_dict = {k: v for k, v in enumerate(res)}
            return res_dict
        return res
    except json.decoder.JSONDecodeError:
        return None

    return None


def extract_plot_data(df, topic, column):
    """
    Extract plot data from DataFrame

    Parameters
    ----------
    df : DataFrame
        timestamp as index, topic and payload
    topic : str
        topic
    column : str or int
        column in payload

    Returns
    -------
    ser : pandas.Series
        extracted series from DataFrame
    """
    topic_df = df[df.topic == topic]
    ser = topic_df.payload.map(lambda x: guess_xsv(x).get(column))
    ser = ser[ser.notna()]
    ser.name = column

    return ser


def plot(df, axes, filename="figure.png"):
    """
    Plot time series data and Save to PNG file

    Parameters
    ----------
    df : DataFrame
        timestamp as index, topic and payload
    axes : list
        axes infromation for plot
    filename : str
        png filename
    """
    fig = plt.figure(figsize=(15, 4*len(axes)))
    for i, axis in enumerate(axes):
        ax = fig.add_subplot(len(axes), 1, i+1)
        if axis.get('name'):
            ax.set_title(axis.get('name'))
        data = axis.get('data')
        if data is None:
            print("data not found in config")
            exit(0)

        for d in data:
            topic = d.get('topic')
            column = d.get('column')
            ser = extract_plot_data(df, topic, column)
            if len(ser) > 0:
                ax.plot(ser.index, ser, label=topic)

        ymin = axis.get('min')
        ymax = axis.get('max')
        if ymin is None:
            (ymin, _) = ax.get_ylim()
        if ymax is None:
            (_, ymax) = ax.get_ylim()
        ax.set_ylim(ymin, ymax)
        unit = axis.get('unit')
        ax.set_ylabel(unit)
        ax.legend()
        ax.xaxis.set_major_formatter(
            mdates.DateFormatter('%b %d\n%H:%M', df.index[0].tzinfo)
        )
        ax.grid()
        ax.tick_params(left=False, bottom=False)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)

    fig.tight_layout()
    plt.savefig(filename)


def get_latest(config="co2plot.json"):
    """
    Get latest payloads of each topic

    Parameters
    ----------
    config : str
        axes configuration

    Returns
    -------
    values : dict
        including payloads and its metadata from 'co2plot.json'
    """

    f = open(config, 'r', encoding='utf-8')
    config = json.load(f)
    database = config.get('database', DEFAULT_DATABASE)
    if not os.path.exists(database):
        print("cannot read '%s'" % database)
        exit(0)
    table = config.get('table', DEFAULT_TABLE)
    tz = config.get('timezone', 'UTC')
    df = read_database(database, table, tz=tz)
    latest = df.sort_values("timestamp").groupby("topic").tail(1)

    measurement = {}
    for index, row in latest.iterrows():
        measurement[row.topic] = {
            "payload": guess_xsv(row.payload),
            "timestamp": index.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    for axis in config["axes"]:
        for d in axis["data"]:
            topic = measurement.get(d["topic"])
            if not topic:
                continue
            if not topic.get("metadata"):
                topic["metadata"] = {}
            if not topic["payload"].get(d["column"]):
                continue
            topic["metadata"][d["column"]] = {
                "name": axis["name"],
                "unit": axis["unit"],
            }

    return measurement


def figure(days=None, config="co2plot.json", filename="figure.png"):
    """
    Plot time series data and Save to PNG file

    Parameters
    ----------
    days : int or list(begin, end) or None
        plot from 'days' to now or from begin to end or all
    config : str
        axes configuration
    filename : str
        output PNG filename

    Returns
    -------
    values : str
        plotted filename or None
    """

    f = open(config, 'r', encoding='utf-8')
    plot_config = json.load(f)
    database = plot_config.get('database', DEFAULT_DATABASE)
    if not os.path.exists(database):
        print("cannot read '%s'" % database)
        exit(0)
    table = plot_config.get('table', DEFAULT_TABLE)
    tz = plot_config.get('timezone', 'UTC')
    df = read_database(database, table, tz=tz)
    begin = None
    end = None
    if days:
        if type(days) == int:
            now = datetime.now(timezone.utc)
            begin = now - timedelta(days=days)
        elif type(days) == tuple and len(days) == 2:
            start_of_day = time(0, 0, 0)
            if days[0]:
                begin = datetime.combine(days[0], start_of_day).astimezone(
                    timezone.utc)
            if days[1]:
                end = datetime.combine(days[1], start_of_day).astimezone(
                    timezone.utc)
    df = df[begin:end]
    if len(df.index) == 0:
        return None
    axes = plot_config.get('axes')
    if not axes:
        print("axes not found in config")
        exit(0)

    plot(df, axes, filename)
    return filename


def main():
    parser = argparse.ArgumentParser(description='CO2 plot from SQLite')
    parser.add_argument(
        '-p',
        '--png',
        default='figure.png',
        help='Output PNG filename'
    )
    parser.add_argument(
        '-c',
        '--config',
        default='co2plot.json',
        help='Axes configuration'
    )
    parser.add_argument(
        '-d',
        '--days',
        type=int,
        help='Plot data from "days" to today'
    )
    parser.add_argument(
        '-n',
        '--now',
        action="store_true",
        help='Display latest value'
    )
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"config file '{args.config}' not found")
        exit(1)

    if args.now:
        abrvs = {
            "degree celsius": "°",
            "parcentage": "%",
            "Temperature": ("🌡", "%.1f"),
            "Humidity": ("💧", "%.1f"),
            "Carbon Dioxide": ("💨", "%d"),
        }
        now = get_latest(config=args.config)
        mes = ""
        for topic in now:
            mes += f"{topic} ({now[topic]['timestamp']})\n"
            for n in now[topic]["metadata"]:
                meta = now[topic]["metadata"][n]
                (name, fmt) = abrvs.get(meta['name'], (meta['name'], "%f"))
                unit = abrvs.get(meta['unit'], meta['unit'])
                val = now[topic]["payload"][n]
                mes += "%6s " % name
                mes += fmt % val
                mes += "%s" % unit
                mes += "\n"
        print(mes, end="")
    else:
        figure(days=args.days, config=args.config, filename=args.png)


if __name__ == '__main__':
    main()
