# BOT
<img alt="Example" src="./img/co2command.png" width="447">

## Prerequisites
### Slack
Slack platform access tokens are required.
1. Bot token strings begin with 'xoxb-'
2. App-level token strings begin with 'xapp-'
3. Incoming Webhook URL

### Zulip
1. Register A bot user on the Zulip server's web interface.
2. Download 'zuliprc' configuration file.
3. Zulip stream for monibot.

## Installation
```Shell
$ pip install .
```
You can use 'monibot', 'monibotz' and 'co2plot' command.

## Monibot

### Configure the bot
Set environment variables.
```Shell
# Slack
SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
REPORT_WEBHOOK='https://hooks.slack.com/services/TXXXXXXXX/BYYYYYYYYYY/ZZZZZZZZZZZZZZZZZZZZZZZZZZ'

# Zulip
ZULIP_EMAIL=xxxx-bot@yyyyyyyy.zulipchat.com
ZULIP_API_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz012455
ZULIP_SITE=https://yyyyyyyy.zulipchat.com
ZULIP_MONIBOT_STEAM="general:swimming turtles"

# search book
CALIL_APPKEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BOOK_CONFIG=/opt/monibot/monibot.conf

# OpenWeatherMap
OPENWEATHER_API_KEY=1111222233334444aaaabbbbccccdddd
# latitude:longitude
MY_PLACE=xx.xxxxxxx:yyy.yyyyyyy

# monitor
MONITOR_CONFIG=/opt/monibot/monibot.conf

# plot measurement data
CO2PLOT=co2plot.json

# fetch IP address
GETIP_CONFIG=/opt/monibot/etc/monibot.conf

#TZ=Asia/Tokyo
#PYTHONDONTWRITEBYTECODE=1
#MONIBOT_LOGGING_LEVEL=debug
```

Create configuration file 'monibot.conf' and 'co2plot.json'.

monibot.conf
```JSON
{
  "book": {
    "Tokyo_NDL": "国立国会図書館",
    "Tokyo_Pref": "東京都立図書館"
  },
  "monitor": {
    "temperature": {
      "outside_hot_alert_threshold": 30.0,
      "pipe_alert_threshold": -5.0,
      "forecast_interval_hours": 4
    },
    "servers": {
      "ping_interval_sec": 60,
      "alert_delay": 1,
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
  },
  "getip": {
    "urls":  [
      "https://api.ipify.org",
      "https://v4.ident.me"
    ]
  }
}
```

co2plot.json
```JSON
{
  "database": "measurement.db",
  "table": "measurement",
  "axes": [
    {
      "name": "Temperature",
      "unit": "degree celsius",
      "max": 50.0,
      "min": 0.0,
      "data": [
        {
          "topic": "living/SCD30",
          "column": 0
        },
        {
          "topic": "living/DS11B20",
          "column": 0
        }
      ]
    },
    {
      "name": "Humidity",
      "unit": "parcentage",
      "max": 100.0,
      "min": 0.0,
      "data": [
        {
          "topic": "living/SCD30",
          "column": 1  
        }
      ]
    },
    {
      "name": "Carbon Dioxide",
      "unit": "ppm",
      "max": 3000,
      "min": 0,
      "data": [
        {
          "topic": "living/SCD30",
          "column": 2  
        }
      ]
    }
  ]
}
```

## CO2Plot
## Usage
```Shell
$ co2plot -h
usage: co2plot [-h] [-p PNG] [-c CONFIG] [-d DAYS] [-n]

CO2 plot from SQLite

optional arguments:
  -h, --help            show this help message and exit
  -p PNG, --png PNG     Output PNG filename
  -c CONFIG, --config CONFIG
                        Axes configuration
  -d DAYS, --days DAYS  Plot data from "days" to today
  -n, --now             Display latest value
$
```

<img alt="Example" src="./img/example.png" width="800">

## SQLite3 schema
```SQL
CREATE TABLE IF NOT EXISTS measurement (
    timestamp INTEGER PRIMARY KEY,
    topic TEXT,
    payload TEXT
);
```
Unix time nanoseconds is used as *timestamp*. 
The following is an example of the table.
```SQL
sqlite> select timestamp, topic, payload from measurement;
1615949110073652477|living/SCD30|25.2 24.9 582
1615949170137723196|living/SCD30|25.1 25.1 579
1615949230202348740|living/SCD30|25.1 25.0 578
1615949290265383071|living/SCD30|25.1 25.1 583
1615949350346302793|living/SCD30|24.7 25.6 584
1615898516178925437|living/DS11B20|18.0
1615898576244004264|living/DS11B20|18.0
1615898636302554140|living/DS11B20|18.0
1615898696363437214|living/DS11B20|18.0
1615898756427165960|living/DS11B20|18.0
```
In the example *payload* contains temperature(℃), humidity(%) and CO2(ppm).


## Test

### Install extra packages
```Shell
pip install -e .[dev]
```

### Run tests
```Shell
$ pytest
```

## References
- [Python3でSlack APIを使用してBotを作成](https://qiita.com/YoheiHayamizu/items/a385f59d90e2a9c4d1a1)
  
- [SlackのtokenとAPI、botの種類をまとめた](https://qiita.com/tkit/items/2536ea6971754f9a75d1)

- [Slack Bolt for Pythonを使ってのbot構築。ローカル開発からHerokuデプロイまで](https://qiita.com/geeorgey/items/c1e147eda40f6d652446)
