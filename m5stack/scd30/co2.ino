#include <M5Stack.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>

#include "SparkFun_SCD30_Arduino_Library.h"
SCD30 airSensor;

const char *CONFIG_FILE = "/config.json";
#define MAX_SSID (32+1)
#define MAX_PASS (63+1)
#define MAX_WEBHOOK (128)
char ssid[MAX_SSID];
char password[MAX_PASS];
char webhook[MAX_WEBHOOK];
StaticJsonDocument<1024> config;


#define CO2_PPM_MIN 400
#define CO2_PPM_MAX 3200
#define CO2_PPM_CAUTION_THRESHOLD 1000
#define CO2_PPM_WARNING_THRESHOLD 3000
#define CO2_PPM_DANGER_THRESHOLD 10000
#define COLOR_GOOD "#007060"
#define COLOR_CAUTION "#FFD000"
#define COLOR_WARNING "#FF8000"
#define COLOR_DANGER "#D01030"

// Display
#define TFT_WIDTH 320
#define TFT_HEIGHT 240
#define GRAPH_AREA_WIDTH TFT_WIDTH
#define GRAPH_AREA_HEIGHT 160
#define TEXT_AREA_WIDTH TFT_WIDTH
#define TEXT_AREA_HEIGHT TFT_HEIGHT-GRAPH_AREA_HEIGHT

TFT_eSprite graph_area = TFT_eSprite(&M5.Lcd);
TFT_eSprite text_area = TFT_eSprite(&M5.Lcd);

// measured values
uint16_t co2_ppm = 400;
float temperature_c = 20.0;
float humidity_p = 30.0;
int sampling_interval_s = 30; // seconds

// Slack
bool use_slack = true;
#define ALART_SENSITIVITY 3

const char *caCert = "-----BEGIN CERTIFICATE-----\n"
"MIIDrzCCApegAwIBAgIQCDvgVpBCRrGhdWrJWZHHSjANBgkqhkiG9w0BAQUFADBh\n"
"MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3\n"
"d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBD\n"
"QTAeFw0wNjExMTAwMDAwMDBaFw0zMTExMTAwMDAwMDBaMGExCzAJBgNVBAYTAlVT\n"
"MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j\n"
"b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IENBMIIBIjANBgkqhkiG\n"
"9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4jvhEXLeqKTTo1eqUKKPC3eQyaKl7hLOllsB\n"
"CSDMAZOnTjC3U/dDxGkAV53ijSLdhwZAAIEJzs4bg7/fzTtxRuLWZscFs3YnFo97\n"
"nh6Vfe63SKMI2tavegw5BmV/Sl0fvBf4q77uKNd0f3p4mVmFaG5cIzJLv07A6Fpt\n"
"43C/dxC//AH2hdmoRBBYMql1GNXRor5H4idq9Joz+EkIYIvUX7Q6hL+hqkpMfT7P\n"
"T19sdl6gSzeRntwi5m3OFBqOasv+zbMUZBfHWymeMr/y7vrTC0LUq7dBMtoM1O/4\n"
"gdW7jVg/tRvoSSiicNoxBN33shbyTApOB6jtSj1etX+jkMOvJwIDAQABo2MwYTAO\n"
"BgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUA95QNVbR\n"
"TLtm8KPiGxvDl7I90VUwHwYDVR0jBBgwFoAUA95QNVbRTLtm8KPiGxvDl7I90VUw\n"
"DQYJKoZIhvcNAQEFBQADggEBAMucN6pIExIK+t1EnE9SsPTfrgT1eXkIoyQY/Esr\n"
"hMAtudXH/vTBH1jLuG2cenTnmCmrEbXjcKChzUyImZOMkXDiqw8cvpOp/2PV5Adg\n"
"06O/nVsJ8dWO41P0jmP6P6fbtGbfYmbW0W5BjfIttep3Sp+dWOIrWcBAI+0tKIJF\n"
"PnlUkiaY4IBIqDfv8NZ5YBberOgOzW6sRBc4L0na4UU+Krk2U886UAb3LujEV0ls\n"
"YSEY1QSteDwsOoBrp+uvFRTp2InBuThs4pFsiv9kuXclVzDAGySj4dzp30d8tbQk\n"
"CAUw7C29C79Fv1C5qfPrmAESrciIxpg0X40KPMbp1ZWVbd4=\n"
"-----END CERTIFICATE-----\n";
#define MAX_WEBHOOK_HOST 32
#define MAX_WEBHOOK_PATH 64
char webhook_host[MAX_WEBHOOK_HOST];
char webhook_path[MAX_WEBHOOK_PATH];

// MQTT
bool use_mqtt = true;
#define MAX_MQTT_BROKER 64
#define MAX_MQTT_DEVICE_ID 64
#define MAX_MQTT_TOPIC 64
uint16_t mqtt_port=1883;
char mqtt_broker[MAX_MQTT_BROKER];
char mqtt_device_id[MAX_MQTT_DEVICE_ID];
char mqtt_topic[MAX_MQTT_TOPIC];
WiFiClient tcp_client;
PubSubClient mqtt_client(tcp_client);


void readConfig(const char *filename)
{
    File f = SD.open(filename, FILE_READ);

    DeserializationError error = deserializeJson(config, f);
    if (error) {
        M5.Lcd.println(F("Failed to read file."));
        M5.Lcd.println(error.c_str());
        for (;;);
    }

    if (!config["ssid"]) {
        M5.Lcd.println(F("no SSID"));
        for (;;);
    }
    strlcpy(ssid, config["ssid"], sizeof(ssid));
    if (!config["password"]) {
        M5.Lcd.println(F("no Wi-Fi password"));
        for (;;);
    }
    strlcpy(password, config["password"], sizeof(password));
    if (config["interval_sec"]) {
        sampling_interval_s = (int)config["interval_sec"];
    }
    if (config["slack"]) {
        strlcpy(webhook, config["slack"], sizeof(webhook));

        char *token;
        char uri[sizeof(webhook)];
        strlcpy(uri, webhook, sizeof(uri));
        token = strtok(uri, "/"); // https:
        if (token == NULL) {
            M5.Lcd.println(F("cannot parse webhook protocol"));
            Serial.println(F("cannot parse webhook protocol"));
            use_slack = false;
        }
        else {
            token = strtok(NULL, "/"); // hostname
            if (token == NULL) {
                M5.Lcd.println(F("cannot parse webhook host"));
                Serial.println(F("cannot parse webhook host"));
                use_slack = false;
            }
            else {
                strlcpy(webhook_host, token, sizeof(webhook_host));
                token = strtok(NULL, ""); // path
                if (token == NULL) {
                    M5.Lcd.println(F("cannot parse webhook path"));
                    Serial.println(F("cannot parse webhook path"));
                    use_slack = false;
                }
                else {
                    strlcpy(webhook_path, token, sizeof(webhook_path));
                }
            }
        }
    }
    else {
        M5.Lcd.println(F("no Webhook URL"));
        Serial.println(F("no Webhook URL"));
        use_slack = false;
    }
    if (!use_slack) {
        M5.Lcd.println(F("don't use slack"));
        Serial.println(F("don't use slack"));
    }

    // MQTT
    if (config["mqtt"]) {
        if (config["mqtt"]["broker"]) {
            strlcpy(mqtt_broker, config["mqtt"]["broker"], sizeof(mqtt_broker));
        }
        else {
            M5.Lcd.println(F("no MQTT broker"));
            Serial.println(F("no MQTT broker"));
            use_mqtt = false;
        }
        if (config["mqtt"]["port"]) {
            mqtt_port = (uint16_t)config["mqtt"]["port"];
        }
        else {
            M5.Lcd.println(F("no MQTT port"));
            Serial.println(F("no MQTT port"));
            mqtt_port = 1883;
        }
        if (config["mqtt"]["device_id"]) {
            strlcpy(mqtt_device_id, config["mqtt"]["device_id"], sizeof(mqtt_device_id));
        }
        else {
            M5.Lcd.println(F("no MQTT device ID"));
            Serial.println(F("no MQTT device ID"));
            use_mqtt = false;
        }
        if (config["mqtt"]["topic"]) {
            strlcpy(mqtt_topic, config["mqtt"]["topic"], sizeof(mqtt_topic));
        }
        else {
            M5.Lcd.println(F("no MQTT topic"));
            Serial.println(F("no MQTT topic"));
            use_mqtt = false;
        }
    }
    else {
        M5.Lcd.println(F("no MQTT configuration"));
        Serial.println(F("no MQTT configuration"));
        use_mqtt = false;
    }
}

void showConfig() {
    Serial.printf("SSID: %s\n", ssid);
    Serial.printf("interval: %d\n", sampling_interval_s);
    Serial.printf("webhook_host: %s\n", webhook_host);
    Serial.print("use_mqtt: "); Serial.println(use_mqtt);
    Serial.printf("broker: %s\n", mqtt_broker);
    Serial.printf("port: %d\n", mqtt_port);
    Serial.printf("device_id: %s\n", mqtt_device_id);
    Serial.printf("topic: %s\n", mqtt_topic);
}

void setup()
{
    M5.begin();
    M5.Power.begin();
    M5.Lcd.fillScreen(TFT_BLACK);
    M5.Lcd.setTextColor(TFT_WHITE);
    M5.Lcd.setTextSize(2);

    graph_area.setColorDepth(8);
    graph_area.createSprite(GRAPH_AREA_WIDTH, GRAPH_AREA_HEIGHT);
    graph_area.fillSprite(TFT_BLACK);

    text_area.setColorDepth(8);
    text_area.createSprite(TEXT_AREA_WIDTH, TEXT_AREA_HEIGHT);
    text_area.fillSprite(TFT_BLACK);
    text_area.setTextColor(TFT_WHITE);
    text_area.setTextSize(3);

    Serial.begin(115200);
    Serial.println("co2");

    if (airSensor.begin() == false) {
        Serial.print("Air sensor not detected. Please check wiring. Freezing...");
        for (;;);
    }

    readConfig(CONFIG_FILE);
    Serial.printf("connecting to %s ...", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        Serial.printf(".");
        delay(500);
    }
    Serial.println(" ok");

    /*bool ret = postMessage("I am here!", COLOR_GOOD);
    if (!ret) {
        Serial.println("post failed");
    }*/

    if (use_mqtt) {
        mqtt_client.setServer(mqtt_broker, mqtt_port);
    }
    showConfig();
}

// color: good/warning/danger
bool postMessage(String message, String color)
{
    if (!use_slack) {
        Serial.println("cannot use slack");
        return false;
    }

    WiFiClientSecure client;
    String payload = R"({"attachments": [{"color": ")" + color + R"(", "text": ")" + message + R"("}]})";
    String post = "POST /" + String(webhook_path) + " HTTP/1.1\r\n";
    post += "Host: " + String(webhook_host) + "\r\n";
    post += "User-Agent: M5Stack\r\n";
    post += "Connection: close\r\n";
    post += "Content-Type: application/json;\r\n";
    post += "Content-Length: " + String(payload.length()) + "\r\n\r\n";
    post += payload + "\r\n";

    client.setCACert(caCert);
    if (!client.connect(webhook_host, 443)) {
        Serial.printf("failed to connect to %s", webhook_host);
        return false;
    }
    Serial.printf("connected to %s\n", webhook_host);
    Serial.print(post);

    client.print(post);

    bool ret = false;
    while (client.connected()) {
        String line = client.readStringUntil('\r');
        if (line.startsWith(String("HTTP/1.1 200 OK"))) {
            ret = true;
        }
        break;
    }
    client.stop();

    return ret;
}


void mqttPublish(String payload)
{
    if (!use_mqtt) return;

    while (!mqtt_client.connected()) {
        if (mqtt_client.connect(mqtt_device_id)) break;

        Serial.print("Failed to connect to MQTT broker: ");
        Serial.println(mqtt_client.state());
        delay(5000);
    }
    mqtt_client.publish(mqtt_topic, payload.c_str());
}


uint16_t getCO2Y(uint16_t y)
{
    if (y > CO2_PPM_MAX) {
        y = CO2_PPM_MAX;
    }
    uint16_t Y = (uint16_t)((float)(GRAPH_AREA_HEIGHT-2)/(float)(CO2_PPM_MAX-CO2_PPM_MIN)*(y-CO2_PPM_MIN));
    return GRAPH_AREA_HEIGHT-1 - Y;
}


void plotCO2(uint16_t co2_ppm) {
    static int c = 60;
    uint16_t color = TFT_GREEN;

    if (co2_ppm > CO2_PPM_DANGER_THRESHOLD) {
        color = TFT_RED;
    }
    else if (co2_ppm > CO2_PPM_WARNING_THRESHOLD) {
        color = TFT_ORANGE;
    }
    else if (co2_ppm > CO2_PPM_CAUTION_THRESHOLD) {
        color = TFT_YELLOW;
    }

    // axis
    c--;
    if (c == 0) {
        graph_area.drawFastVLine(GRAPH_AREA_WIDTH-1, 0, GRAPH_AREA_HEIGHT-1, TFT_DARKGREY);
        c = 60;
    }
    graph_area.drawFastVLine(GRAPH_AREA_WIDTH-1, 0, 1, TFT_DARKGREY);
    graph_area.drawFastVLine(GRAPH_AREA_WIDTH-1, GRAPH_AREA_HEIGHT-1, 1, TFT_DARKGREY);

    // plot
    graph_area.drawFastVLine(GRAPH_AREA_WIDTH-1, getCO2Y(co2_ppm), GRAPH_AREA_HEIGHT-1-getCO2Y(co2_ppm), color);

    text_area.setCursor(0, 0);
    text_area.fillSprite(TFT_BLACK);
    text_area.setTextColor(color);
    text_area.printf("CO2:  %4d ppm\n", co2_ppm);
    text_area.setTextColor(TFT_WHITE);
    text_area.printf("Temp: %4.1f degC\n", temperature_c);
    text_area.printf("Humid:%4.1f %%\n", humidity_p);

    graph_area.pushSprite(0, TEXT_AREA_HEIGHT);
    text_area.pushSprite(0, 0);

    graph_area.scroll(-1, 0);
}


void loop()
{
    static int level = 0;
    static int sensitivity = -1;

    if (!airSensor.dataAvailable()) {
        delay(1000);
        return;
    }

    co2_ppm = airSensor.getCO2();
    temperature_c = airSensor.getTemperature();
    humidity_p = airSensor.getHumidity();

    if (co2_ppm > CO2_PPM_DANGER_THRESHOLD) {
        if (level != 3) {
            sensitivity = ALART_SENSITIVITY;
        }
        if (sensitivity == 0) {
            postMessage(String(co2_ppm) + String(" ppm"), COLOR_DANGER);
        }
        level = 3;
        if (sensitivity >= 0) {
            sensitivity--;
        }
    }
    else if (co2_ppm > CO2_PPM_WARNING_THRESHOLD) {
        if (level != 2) {
            sensitivity = ALART_SENSITIVITY;
        }
        if (sensitivity == 0) {
            postMessage(String(co2_ppm) + String(" ppm"), COLOR_WARNING);
        }        
        level = 2;
        if (sensitivity >= 0) {
            sensitivity--;
        }
    }
    else if (co2_ppm > CO2_PPM_CAUTION_THRESHOLD) {
        if (level != 1) {
            sensitivity = ALART_SENSITIVITY;
        }
        if (sensitivity == 0) {
            postMessage(String(co2_ppm) + String(" ppm"), COLOR_CAUTION);
        }
        level = 1;
        if (sensitivity >= 0) {
            sensitivity--;
        }
    }
    else {
        if (level != 0) {
            sensitivity = ALART_SENSITIVITY;
        }
        if (sensitivity == 0) {
            postMessage(String(co2_ppm) + String(" ppm"), COLOR_GOOD);
        }
        level = 0;
        if (sensitivity >= 0) {
            sensitivity--;
        }
    }

    plotCO2(co2_ppm);
    String payload = String(temperature_c, 1) + String(' ')
                + String(humidity_p, 1) + String(' ')
                + String(co2_ppm);
    Serial.println(payload); 
    mqttPublish(payload);

    delay(1000*sampling_interval_s);
}