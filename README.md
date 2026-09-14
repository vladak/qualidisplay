[![Python checks](https://github.com/vladak/qualidisplay/actions/workflows/python-checks.yml/badge.svg)](https://github.com/vladak/qualidisplay/actions/workflows/python-checks.yml)

# qualidisplay

## Hardware

- [Adafruit Qualia ESP32-S3 for TTL RGB-666 Displays](https://www.adafruit.com/product/5800)
- [Rectangle RGB TTL TFT Display - 3.2" 320x820 No Touchscreen](https://www.adafruit.com/product/5828)

## Install

With [`circup`](https://github.com/adafruit/circup/) installed and the Qualia connected over USB (assuming Linux distro):
```
circup install -r requirements.txt
cp -R images/ fonts/ *.py settings.toml /media/$USER/CIRCUITPY/
```

Finish by populating the `secrets.py`:
```python
secrets = {
    "SSID": "wifi",
    "password": "changeme",
    "log_level": "debug",
    "broker": "172.40.0.3",
    "broker_port": 1883,
    "metric_timeout": 900,
    "temp_sensor_topic": "devices/terasa/shield",
    "temp_sensor_name": "temperature",
    "co2_sensor_topic": "devices/kuchyne/pi",
    "co2_sensor_name": "co2_ppm",
    "pressure_sensor_topic": "devices/kuchyne/pi",
    "pressure_sensor_name": "pressure_hpa",
    "co2_threshold": 1200,
    "temp_font_file": "fonts/InterDisplay-Bold-208-reduced_glyphs.pcf",
    "co2_font_file": "fonts/InterDisplay-SemiBold-52-reduced_glyphs.pcf",
}
```

### Generating bitmap fonts

Using bitmap fonts makes the display more readable and nicer. Also, some of the glyps like the circle in °C can be actually displayed.
The font however has to be converted to fit onto the flash and then it has to be used in a special way for quick display.

1. grab the fonts from https://rsms.me/inter/
2. convert the `extras/ttf/Inter-Regular.ttf` into BDF (use 25 pixels size) using https://fontforge.github.io/
3. convert the BDF into PCF for smaller size using https://adafruit.github.io/web-bdftopcf/ , optionally reduce the glyphs
4. copy the resulting file to the `CIRCUITPY` directory

## Guides

- [font conversion](https://learn.adafruit.com/custom-fonts-for-pyportal-circuitpython-display/conversion)

## Lessons learned

- it is not possible to reduce the brightness of the RGB TTL display, in fact it is only possible to increase it by shorting the pins on the Qualia board

