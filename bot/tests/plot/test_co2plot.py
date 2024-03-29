import os
import tempfile
from datetime import date
import json
import hashlib
import pytest
from freezegun import freeze_time
from co2.co2plot import guess_xsv, extract_plot_data
from co2.co2plot import read_database, plot, get_latest, figure


testdir = "tests/plot"
tmpdir = tempfile.TemporaryDirectory()
png_path = tmpdir.name
with open(f"{testdir}/test_png_hash.json", "r") as png_hash_json:
    png_hash = json.load(png_hash_json)


expected_dict = {0: 0.0, 1: 10.0, 2: 20.02, 3: -1.0, 4: -2.2}
guess_xsv_patterns = [
    ("0.0,10, 20.02,   -1,          -2.2", expected_dict),
    ("0.0\t10\t 20.02\t   -1\t          -2.2", expected_dict),
    ("0.0 10 20.02   -1          -2.2", expected_dict),
    ("0.0,10 20.02,   -1          -2.2", {}),
    ('{"Temperature": 20.0, "Humidity": 22.5, "Carbon Dioxide": 450}',
        {"Temperature": 20.0, "Humidity": 22.5, "Carbon Dioxide": 450.0}),
    ('{"Switch": "On", "Light": "Off", "Carbon Dioxide": 450}',
        {"Switch": "On", "Light": "Off",  "Carbon Dioxide": 450}),
    ('[0.0, 10, 20.02, -1, -2.2]', expected_dict),
    ('{"Temperature": 20.0 "Humidity": 22.5, "Carbon Dioxide": 450}', {}),
]


@pytest.mark.parametrize("data, expected", guess_xsv_patterns)
def test_guess_xsv(data, expected):
    actual = guess_xsv(data)
    assert expected == actual


plot_data_patterns = [
    ("test_2_topic.db", "measurement", "living/SCD30", 0, 847),
    ("test_2_topic.db", "measurement", "living/SCD30", 1, 847),
    ("test_2_topic.db", "measurement", "living/SCD30", 2, 847),
    ("test_2_topic.db", "measurement", "living/SCD30", 3, 0),
    ("test_2_topic.db", "measurement", "living/DS11B20", 0, 847),
    ("test_2_topic.db", "measurement", "living/DS11B20", 1, 0),
    ("test_2_topic.db", "measurement", "xxxxxx", 0, 0),
]


@pytest.mark.parametrize(
    "database, table, topic, column, expected",
    plot_data_patterns
)
def test_plot_data(database, table, topic, column, expected):
    df = read_database(f"{testdir}/{database}", table)
    ser = extract_plot_data(df, topic, column)
    assert expected == len(ser)
    assert column == ser.name


plot_patterns = [
    ("test_config1.json", "test_plot1.png"),
    ("test_config2.json", "test_plot2.png"),
    ("test_config3.json", "test_plot3.png"),
    ("test_config4.json", "test_plot4.png"),
    ("test_config5.json", "test_plot5.png"),
]


@pytest.mark.parametrize("config, filename", plot_patterns)
def test_plot(config, filename):
    import json

    f = open(f"{testdir}/{config}", 'r', encoding='utf-8')
    plot_config = json.load(f)
    database = plot_config.get('database')
    table = plot_config.get('table')
    df = read_database(database, table)
    axes = plot_config.get('axes')

    pngfile = f"{png_path}/{filename}"
    if os.path.exists(pngfile):
        os.remove(pngfile)
    plot(df, axes, pngfile)

    assert os.path.exists(pngfile)
    pnghash = png_hash_without_text(pngfile)
    assert pnghash in png_hash[filename]
    os.remove(pngfile)


get_latest_patterns = [
    ("test_config1.json", "test_config1_expected.pkl"),
    ("test_config4.json", "test_config4_expected.pkl"),
    ("test_config5.json", "test_config5_expected.pkl"),
    ("test_config5_paris.json", "test_config5_paris_expected.pkl"),
    ("test_config5_without_tz.json", "test_config5_without_tz_expected.pkl"),
]


@pytest.mark.parametrize("config, expected", get_latest_patterns)
def test_get_latest(config, expected):
    import pickle
    f = open(f"{testdir}/{expected}", 'rb')
    expected_dict = pickle.load(f)

    actual = get_latest(f"{testdir}/{config}")
    assert expected_dict == actual


co2plot_patterns = [
    (None, "test_config5.json", "test_co2plot0.png"),
    (1, "test_config5.json", "test_co2plot1.png"),
    (3, "test_config5.json", "test_co2plot3.png"),
    (5, "test_config5.json", "test_co2plot5.png"),
    ((date(2021, 3, 18), date(2021, 3, 19)),
     "test_config5.json", "test_co2plot_18_19.png"),
    ((date(2021, 3, 19), date(2021, 3, 21)),
     "test_config5.json", "test_co2plot_19_21.png"),
    ((date(2021, 3, 29), date(2021, 3, 31)),
     "test_config5.json", "test_co2plot_29_31.png"),
    ((None, date(2021, 3, 31)),
     "test_config5.json", "test_co2plot_None_31.png"),
    ((date(2021, 3, 29), None),
     "test_config5.json", "test_co2plot_29_None.png"),
]


@pytest.mark.parametrize("days, config, filename", co2plot_patterns)
@freeze_time("2021-03-29 10:20:57", tz_offset=-9)
def test_co2plot(days, config, filename):
    pngfile = f"{png_path}/{filename}"
    if os.path.exists(pngfile):
        os.remove(pngfile)

    figure(days=days, config=f"{testdir}/{config}", filename=pngfile)

    assert os.path.exists(pngfile)
    pnghash = png_hash_without_text(pngfile)
    assert pnghash in png_hash[filename]
    os.remove(pngfile)


def png_hash_without_text(filename):
    hash_without_text = None
    with open(filename, 'rb') as f:
        png_signature = f.read(8)
        if png_signature != b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A':
            return None
        chunk_type = None
        while chunk_type != 'IEND':
            chunk_size = int.from_bytes(f.read(4), byteorder='big')
            chunk_type = f.read(4).decode('utf-8')
            f.read(chunk_size)  # read chunk !!DO NOT REMOVE THIS LINE!!
            f.read(4)  # read crc !!DO NOT REMOVE THIS LINE!!
            if chunk_type == 'tEXt':
                hash_without_text = hashlib.sha256(f.read()).hexdigest()
                break
    return hash_without_text
