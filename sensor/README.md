# co2

## Reference
- [SparkFun_SCD30_Arduino_Library](https://github.com/sparkfun/SparkFun_SCD30_Arduino_Library)
- [換気のすゝめ　～M5StackでCO2濃度モニタを作る～](https://westgate-lab.hatenablog.com/entry/2020/04/01/224511)
- [M5Stack CO2 Monitor](https://github.com/kmizta/m5stack-co2-monitor)
- [Sprite_scroll.ino](https://github.com/m5stack/M5Stack/blob/master/examples/Advanced/Display/Sprite/Sprite_scroll/Sprite_scroll.ino)
- [Arduinoリファレンス](https://garretlab.web.fc2.com/arduino_reference/)

## Setting Slack
You add Incomming WebHooks via slack app directory and get Webhook URL.
and then you save the URL to setting JSON file. 

```JSON
{
    "slack": "https://hooks.slack.com/services/XXXXXXXXX/YYYYYYYYYYY/ZZZZZZZZZZZZZZZZZZZZZZZZ"
}
```

Example for posting JSON:
```JSON
payload={
    "channel": "#general",
    "username": "webhookbot",
    "text": "This is posted to #general and comes from a bot name webhookbot",
    "icon_emoji": ":ghost:"
}
```
This will be displayed in the channel as:

![posting message](https://a.slack-edge.com/80588/img/integrations/incoming_webhook_example3.png)

## Configuration
Save "config.json" to SD card
```JSON
{
    "ssid": "wifissid",
    "password": "wifipass",
    "slack": "https://hooks.slack.com/services/XXXXXXXXX/YYYYYYYYYYY/ZZZZZZZZZZZZZZZZZZZZZZZZ",
    "mqtt": {
        "broker": "your.broker.address",
        "port": "1883",
        "device_id": "uniqueDeviceID",
        "topic": "your/topic"
    },
    "interval": 1000
}
```
