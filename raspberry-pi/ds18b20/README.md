# DS18B20 Driver with Raspberry Pi

This is DS18B20 driver and MQTT publisher with Raspberry Pi.

## Configurations of MQTT Publisher 

Default configuration file is 'ds18b20.json' in current directory.
Or you can use environment variable 'DS18B20_CONFIG' to specify its path.

```Json
{
  "broker_uri": "tcp://my.broker.address:1883",
  "topics": "location1/sensor",
  "client_id": "logger02"
}
```

```Shell
export DS18B20_CONFIG='path/to/config.json'
export RUST_LOG=info
```

## References
- [RPI DS18B20 Temp Sensor](https://github.com/awendland/rpi-ds18b20-rust) (GitHub)
- [How to use MQTT in Rust](https://www.codetd.com/en/article/13805961) (CodeTD)

