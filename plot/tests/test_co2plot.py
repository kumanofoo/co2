import pytest
from co2plot import guess_xsv, extract_plot_data, read_database, plot, co2now, co2plot
from datetime import date
import os

png_path = "results"
if not os.path.isdir(png_path):
    os.mkdir(png_path)


expected_dict = {0: 0.0, 1: 10.0, 2: 20.02, 3: -1.0, 4: -2.2}
guess_xsv_patterns = [
    ("0.0,10, 20.02,   -1,          -2.2", expected_dict),
    ("0.0\t10\t 20.02\t   -1\t          -2.2", expected_dict),
    ("0.0 10 20.02   -1          -2.2", expected_dict),
    ("0.0,10 20.02,   -1          -2.2", None),
    ('{"Temperature": 20.0, "Humidity": 22.5, "Carbon Dioxide": 450}',
        {"Temperature": 20.0, "Humidity": 22.5, "Carbon Dioxide": 450.0}),
    ('{"Switch": "On", "Light": "Off", "Carbon Dioxide": 450}',
        {"Switch": "On", "Light": "Off",  "Carbon Dioxide": 450}),
    ('[0.0, 10, 20.02, -1, -2.2]', expected_dict),
    ('{"Temperature": 20.0 "Humidity": 22.5, "Carbon Dioxide": 450}', None),
]
@pytest.mark.parametrize("data, expected", guess_xsv_patterns)
def test_guess_xsv(data, expected):
    actual = guess_xsv(data)
    assert expected == actual


plot_data_patterns = [
    ("tests/test_2_topic.db", "measurement", "living/SCD30", 0, 847),
    ("tests/test_2_topic.db", "measurement", "living/SCD30", 1, 847),
    ("tests/test_2_topic.db", "measurement", "living/SCD30", 2, 847),
    ("tests/test_2_topic.db", "measurement", "living/SCD30", 3, 0),
    ("tests/test_2_topic.db", "measurement", "living/DS11B20", 0, 847),
    ("tests/test_2_topic.db", "measurement", "living/DS11B20", 1, 0),
    ("tests/test_2_topic.db", "measurement", "xxxxxx", 0, 0),
]
@pytest.mark.parametrize("database, table, topic, column, expected", plot_data_patterns)
def test_plot_data(database, table, topic, column, expected):
    df = read_database(database, table)
    ser = extract_plot_data(df, topic, column)
    assert expected == len(ser)
    assert column == ser.name


plot_patterns = [
    ("tests/test_config1.json", f"{png_path}/test_plot1.png"),
    ("tests/test_config2.json", f"{png_path}/test_plot2.png"),
    ("tests/test_config3.json", f"{png_path}/test_plot3.png"),
    ("tests/test_config4.json", f"{png_path}/test_plot4.png"),
    ("tests/test_config5.json", f"{png_path}/test_plot5.png"),
]
@pytest.mark.parametrize("config, filename", plot_patterns)
def test_plot(config, filename):
    import json
    import matplotlib.pyplot as plt

    f = open(config, 'r')
    plot_config = json.load(f)
    database = plot_config.get('database')
    table = plot_config.get('table')
    df = read_database(database, table)
    axes = plot_config.get('axes')

    if os.path.exists(filename):
        os.remove(filename)
    plot(df, axes, filename)

    assert os.path.exists(filename)

co2now_patterns = [
    ("tests/test_config1.json", "tests/test_config1_expected.pkl"),
    ("tests/test_config4.json", "tests/test_config4_expected.pkl"),
    ("tests/test_config5.json", "tests/test_config5_expected.pkl"),
]
@pytest.mark.parametrize("config, expected", co2now_patterns)
def test_co2now(config, expected):
    import pickle
    f = open(expected, 'rb')
    expected_dict = pickle.load(f)
    
    actual = co2now(config)
    assert expected_dict == actual

co2plot_patterns = [
    (None, "tests/test_config5.json", f"{png_path}/test_co2plot0.png"),
    (1, "tests/test_config5.json", f"{png_path}/test_co2plot1.png"),
    (3, "tests/test_config5.json", f"{png_path}/test_co2plot3.png"),
    (5, "tests/test_config5.json", f"{png_path}/test_co2plot5.png"),
    ((date(2021, 3, 18), date(2021, 3, 19)), "tests/test_config5.json", f"{png_path}/test_co2plot_18_19.png"),
    ((date(2021, 3, 19), date(2021, 3, 21)), "tests/test_config5.json", f"{png_path}/test_co2plot_19_21.png"),
    ((date(2021, 3, 29), date(2021, 3, 31)), "tests/test_config5.json", f"{png_path}/test_co2plot_29_31.png"),
    ((None, date(2021, 3, 31)), "tests/test_config5.json", f"{png_path}/test_co2plot_None_31.png"),
    ((date(2021, 3, 29), None), "tests/test_config5.json", f"{png_path}/test_co2plot_29_None.png"),
]
@pytest.mark.parametrize("days, config, filename", co2plot_patterns)
def test_co2plot(days, config, filename):
    from datetime import datetime, timedelta

    if os.path.exists(filename):
        os.remove(filename)

    if type(days) == int:
        d = timedelta(days=days) + (datetime.now() - datetime.fromisoformat("2021-03-29T10:20:57"))
        co2plot(days=d.days, config=config, filename=filename)
    else:
        co2plot(days=days, config=config, filename=filename)


    assert os.path.exists(filename)
