import os
import socketpool
import supervisor
import time
import displayio
import terminalio
import traceback

from logutil import get_log_level
# from mqtt import mqtt_client_setup, mqtt_publish_robust
from metrics import Metrics

import adafruit_logging as logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label

from adafruit_qualia.graphics import Displays, Graphics

try:
    import wifi
except MemoryError as e:
    # Let this fall through to main() so that appropriate reset can be performed.
    IMPORT_EXCEPTION = e  # pylint: disable=invalid-name

try:
    from secrets import secrets
except ImportError:
    print("WiFi credentials are kept in secrets.py, please add them there!")
    raise


CO2 = "co2"
TEMPERATURE = "temp"
HUMIDITY = "humidity"
LAST_UPDATE = "time"

BROKER_HOSTNAME = "broker"
BROKER_PORT = "broker_port"

SSID = "SSID"
PASSWORD = "password"
LOG_LEVEL = "log_level"

TEMP_PREFIX = "Temp: "
HUM_PREFIX = "Hum: "

RED = (255, 0, 0)  # CO2 alert
GREEN = (0, 255, 0)  # break alert
BLUE = (0, 0, 255)  # table alert

METRIC_TIMEOUT = "metric_timeout"
MQTT_TEMP_TOPIC = "temp_sensor_topic"
MQTT_TEMP_NAME = "temp_sensor_name"
MQTT_CO2_TOPIC = "co2_sensor_topic"
MQTT_CO2_NAME = "co2_sensor_name"
MQTT_PRESSURE_TOPIC = "pressure_sensor_topic"
MQTT_PRESSURE_NAME = "pressure_sensor_name"

CO2_THRESHOLD = "co2_threshold"

TEMP_FONT_FILE = "temp_font_file"
CO2_FONT_FILE = "co2_font_file"

MANDATORY_SECRETS = [
    BROKER_HOSTNAME,
    BROKER_PORT,
    PASSWORD,
    SSID,
    LOG_LEVEL,
    MQTT_TEMP_TOPIC,
    MQTT_CO2_TOPIC,
    MQTT_PRESSURE_TOPIC,
    CO2_THRESHOLD,
    TEMP_FONT_FILE,
    CO2_FONT_FILE,
]


def get_font(file_name):
    """
    Try to load a bitmap font. If not successful, fall back to terminal font.
    Return font and font and border scale factor.
    """

    logger = logging.getLogger(__name__)

    font = terminalio.FONT
    try:
        font_scale = 1
        border_scale = 2
        font_file = file_name
        logger.debug(f"loading font from {font_file}")
        font = bitmap_font.load_font(font_file)
        font.load_glyphs(
            # pylint: disable=line-too-long
            code_points="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890- ().,:!?/\\%+@~"
        )
        font.load_glyphs("°³µ₂")  # preload glyphs for fast printing
    # pylint: disable=broad-exception-caught
    except Exception as exception:
        border_scale = 1
        font_scale = 2
        logger.warning(f"Cannot load bitmap font, will use terminal font: {exception}")

    return font, font_scale, border_scale


def main():
    """
    XXX
    """
    log_level = get_log_level(secrets[LOG_LEVEL])
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    logger.info("Running")

    # Check all mandatory secrets are present.
    for secret in MANDATORY_SECRETS:
        if secrets.get(secret) is None:
            logger.error(f"secret {secret} is missing")
            return

    # Connect to Wi-Fi
    logger.info("Connecting to wifi")
    wifi.radio.connect(secrets[SSID], secrets[PASSWORD], timeout=10)
    logger.info(f"Connected to {secrets[SSID]}")
    logger.debug(f"IP: {wifi.radio.ipv4_address}")

    # Create a socket pool
    pool = socketpool.SocketPool(wifi.radio)  # pylint: disable=no-member

    metrics = Metrics(
        log_level,
        pool,
        secrets.get(BROKER_HOSTNAME),
        secrets.get(BROKER_PORT),
        secrets.get(METRIC_TIMEOUT),
        0.1,
        [ (secrets.get(MQTT_TEMP_TOPIC), secrets.get(MQTT_TEMP_NAME)),
          (secrets.get(MQTT_CO2_TOPIC), secrets.get(MQTT_CO2_NAME)),
          (secrets.get(MQTT_PRESSURE_TOPIC), secrets.get(MQTT_PRESSURE_NAME)),
        ]
    )
    data = ()

    # By default the display will auto refresh.
    graphics = Graphics(Displays.BAR320X820, default_bg=None, rotation=270)

    logger.debug("setting display elements")
    grp = displayio.Group()
    graphics.root_group.append(grp)

    splash = displayio.Group(scale=1)
    grp.append(splash)

    text = "N/A"
    temp_font, font_scale, border_scale = get_font(secrets.get(TEMP_FONT_FILE))
    color = 0x0000FF
    temp_area = label.Label(temp_font, text=text, color=color)
    temp_area.x = 10
    temp_area.y = 90
    splash.append(temp_area)

    co2_color_default = 0x00FF00
    co2_font, font_scale, border_scale = get_font(secrets.get(CO2_FONT_FILE))
    co2_area = label.Label(co2_font, text="", color=co2_color_default)
    co2_area.x = 10
    co2_area.y = 230
    splash.append(co2_area)

    atm_font, font_scale, border_scale = get_font(secrets.get(CO2_FONT_FILE))
    atm_area = label.Label(atm_font, text="", color=color)
    atm_area.x = 10
    atm_area.y = 290
    splash.append(atm_area)

    # Add the Group to the Display
    graphics.display.root_group = graphics.root_group

    # Store last metric values to avoid unnecessary redraws.
    temp_value_last = -65535
    co2_value_last = -1
    atm_value_last = -1

    co2_threshold_value = secrets.get(CO2_THRESHOLD)

    while True:
        metric_dict = metrics.get_metrics()

        temperature = metric_dict.get(secrets.get(MQTT_TEMP_NAME))
        if temperature != temp_value_last:
            if temperature is None:
                temp_area.text = "N/A"
                temp_value_last = None
            else:
                temp_area.text = f"{round(temperature)}°C"
                temp_value_last = temperature

        co2 = metric_dict.get(secrets.get(MQTT_CO2_NAME))
        if co2 != co2_value_last:
            co_prefix = "CO₂"
            if co2 is None:
                co2_area.text = f"{co_prefix} : N/A"
                co2_value_last = None
            else:
                co2_area.text = f"{co_prefix} : {co2} ppm"
                co2_value_last = co2
                if co2 > co2_threshold_value:
                    co2_area.color = 0xFF0000
                else:
                    co2_area.color = co2_color_default

        pressure = metric_dict.get(secrets.get(MQTT_PRESSURE_NAME))
        if pressure != atm_value_last:
            atm_prefix = "atm"
            if pressure is None:
                atm_area.text = f"{atm_prefix} : N/A"
                atm_value_last = None
            else:
                atm_area.text = f"{atm_prefix} : {round(pressure)} hPa"
                atm_value_last = pressure

        # time.sleep(1)
        pass


try:
    main()
except ConnectionError as conn_error:
    # When this happens, it usually means that the microcontroller's wifi/networking is botched.
    # The only way to recover is to perform hard reset.
    hard_reset(conn_error)
except MemoryError as memory_error:
    # This is usually the case of delayed exception from the 'import wifi' statement,
    # possibly caused by a bug (resource leak) in CircuitPython that manifests
    # after a sequence of ConnectionError exceptions thrown from withing the wifi module.
    # Should not happen given the above 'except ConnectionError',
    # however adding that here just in case.
    hard_reset(memory_error)
except Exception as generic_exception:  # pylint: disable=broad-except
    # This assumes that such exceptions are quite rare.
    # Otherwise, this would drain the battery quickly by restarting
    # over and over in a quick succession.
    print("Code stopped by unhandled exception:")
    print(
        traceback.format_exception(
            None, generic_exception, generic_exception.__traceback__
        )
    )
    RELOAD_TIME = 10
    print(f"Performing a supervisor reload in {RELOAD_TIME} seconds")
    time.sleep(RELOAD_TIME)
    supervisor.reload()
