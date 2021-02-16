#include <M5Stack.h>
#include <Wire.h>

#include "SparkFun_SCD30_Arduino_Library.h"
SCD30 airSensor;

#define CO2_PPM_MIN 400
#define CO2_PPM_MAX 9000
#define CO2_PPM_CAUTION_THRESHOLD 1000
#define CO2_PPM_WARNING_THRESHOLD 3000
#define CO2_PPM_DANGER_THRESHOLD 10000

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


void setup()
{
    M5.begin();
    M5.Power.begin();
    M5.Lcd.fillScreen(TFT_BLACK);

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
}


uint16_t getCO2Y(uint16_t y)
{
    if (y > CO2_PPM_MAX) {
        y = CO2_PPM_MAX;
    }
    uint16_t Y = (uint16_t)((float)(GRAPH_AREA_HEIGHT-2)/(float)(CO2_PPM_MAX-CO2_PPM_MIN)*(y-CO2_PPM_MIN));
    return GRAPH_AREA_HEIGHT-1 - Y;
}


void loop()
{
    if (!airSensor.dataAvailable()) {
        delay(1000);
        return;
    }

    co2_ppm = airSensor.getCO2();
    temperature_c = airSensor.getTemperature();
    humidity_p = airSensor.getHumidity();

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
    graph_area.drawFastVLine(GRAPH_AREA_WIDTH-1, getCO2Y(co2_ppm), 1, color);

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

    delay(1000);
}