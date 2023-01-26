# CO2DB

## Requirements
### crate
- chrono(0.4.19)
- env_logger(0.8.3)
- log(0.4.14)
- paho-mqtt(0.9.1)
- rustqlite(0.24.2)
- clap(2.33.3)
- serde(1.0.125)
- serde_json(1.0.64)
- signal-hook(0.3.8)

### library
- libsqlite3-dev(3.31.1-4ubuntu0.2)

## Configurations
### JSON and Environment variables
Default configuration file is 'co2db.json' in current directory.
Or you can use environment variable 'CO2DB_CONFIG' to specify its path.

```Shell
export CO2DB_CONFIG='/opt/co2/co2db.json'
export RUST_LOG=info
```

#### co2db.json for *co2db*
```Json
{
  "broker_uri": "tcp://my.broker.address:1883",
  "topics": ["location1/sensor", "location2/sensor"],
  "qos": [1, 2],
  "client_id": "logger01",
  "database": "/opt/co2/co2.db",
  "table": "measurement"
}
```

#### co2db.json for *mqtt2rest* (rest client)
```Json
{
  "broker_uri": "tcp://my.broker.address:1883",
  "topics": ["location1/sensor", "location2/sensor"],
  "qos": [1, 2],
  "client_id": "logger01",
  "url": "http://my.restserver.address:10101/co2db"
}
```

#### co2db.json for *rest2co2db* (rest server)
```Json
{
  "port": 10101,
  "path": "/co2db",
  "database": "/opt/co2/co2.db",
  "table": "measurement"
}
```

#### co2db.json for *dbrot*
```Json
{
  "database": "/opt/co2/co2.db",
  "table": "measurement"
}
```
NOTE: 'database', 'table' and 'qos' are optional. 'qos' list match 'topics'.
Default value of 'qos' is 1.

## SQLite
### Table
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
1614833824948172320|living/SCD30|28.0 18.5 784
1614833834997209718|living/SCD30|28.0 18.7 783
1614833845047854154|living/SCD30|28.0 18.6 784
1614833855098967565|living/SCD30|28.0 18.6 785
1614833865150192135|living/SCD30|28.0 18.6 785
1614833875201011818|living/SCD30|28.0 18.7 785
1614833885250033241|living/SCD30|27.9 18.6 785
1614833895298687851|living/SCD30|28.0 18.6 786
1614833905348466558|living/SCD30|27.9 18.6 785
1614833915396885617|living/SCD30|27.8 18.8 786
```
In the example *payload* contains temperature(℃), humidity(%) and CO2(ppm).

## Tests
```SHELL
$ cargo test
$ bats tests
```

## References
- [dyn_subscribe.rs - paho.mqtt.rust](https://github.com/eclipse/paho.mqtt.rust/blob/master/examples/dyn_subscribe.rs "dyn_subscribe.rs - paho.mqtt.rust")
- [InfluxDB key concepts](https://docs.influxdata.com/influxdb/v1.8/concepts/key_concepts/ "InfluxDB key concepts")
- [SQLite - Rust Cookbook](https://rust-lang-nursery.github.io/rust-cookbook/database/sqlite.html "SQLite - Rust Cookbook")
- [Handling Unix Kill Signals in Rust](https://dev.to/talzvon/handling-unix-kill-signals-in-rust-55g6 "Handling Unix Kill Signals in Rust")
