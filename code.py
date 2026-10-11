"""
Qualidisplay - display environment metrics using Adafruit Qualia
"""

import time
import traceback

import adafruit_logging as logging
import adafruit_ntp
import alarm
import board
import displayio
import dotclockframebuffer
import rainbowio
import socketpool
import supervisor
import terminalio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text import label
from adafruit_ntp import NTP
from adafruit_qualia.graphics import Displays, Graphics
from adafruit_simplemath import map_range

from blinker import Blinker
from confchecks import ConfCheckException, bail, check_tunables
from const import CO2_MAX_VALUE, CO2_MIN_VALUE
from logutil import get_log_level
from metrics import Metrics

# pylint: disable=wildcard-import, unused-wildcard-import
from names import *
from timeutil import get_time

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

TEMP_PREFIX = "Temp: "
HUM_PREFIX = "Hum: "


def get_font(file_name):
    """
    Try to load a bitmap font. If not successful, fall back to terminal font.
    Return font and font and border scale factor.

    :param file_name: file name of the font file
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
    except Exception as exception:  # pylint: disable=broad-exception-caught
        border_scale = 1
        font_scale = 2
        logger.warning(f"Cannot load bitmap font, will use terminal font: {exception}")

    return font, font_scale, border_scale


def hard_reset(exception):
    """
    Sometimes soft reset is not enough. Perform hard reset.
    :param exception: exception to report before resetting
    """
    print(f"Got exception: {exception}")
    reset_time = 15
    print(f"Performing hard reset in {reset_time} seconds")
    time.sleep(reset_time)
    microcontroller.reset()  # pylint: disable=no-member


def deep_sleep(graphics, sleep_period: int):
    """
    Enter deep sleep, powering the display off in the process.
    :param graphics: Graphics object
    :param sleep_period: period to sleep for in seconds
    """
    logger = logging.getLogger(__name__)

    i2c = graphics.i2c_bus

    # Step 1: Send ST7701S Sleep In command
    sleep_in = bytes([0x01, 0x10])
    dotclockframebuffer.ioexpander_send_init_sequence(
        i2c, sleep_in, **dict(board.TFT_IO_EXPANDER)
    )

    # Step 2: Release all display resources (stops dotclock signals)
    displayio.release_displays()

    # Step 3: Reconfigure backlight pin as OUTPUT on TCA9534, then drive all outputs LOW
    while not i2c.try_lock():
        pass
    buf = bytearray(1)
    i2c.writeto_then_readfrom(0x3F, bytes([0x03]), buf)
    i2c.writeto(0x3F, bytes([0x03, buf[0] & ~(1 << board.BACKLIGHT)]))
    i2c.writeto(0x3F, bytes([0x01, 0x00]))
    i2c.unlock()

    # Small delay to let panel settle
    time.sleep(0.05)

    #
    # time.monotonic() will start losing precision rather quickly,
    # however for the deep sleep this is not a problem because the internal
    # clock gets reset on deep sleep.
    #
    now = time.monotonic()
    logger.debug(f"time now: {now}")
    logger.debug(f"alarm time: {now + sleep_period}")
    # Create an alarm that will trigger sleep_period number of seconds from now.
    time_alarm = alarm.time.TimeAlarm(monotonic_time=now + sleep_period)

    # --- ESP32-S3 deep sleep ---
    logger.debug("Entering deep sleep...")
    alarm.exit_and_deep_sleep_until_alarms(time_alarm)


def get_temp_color(value: int):
    """
    Return color according to temperature value.
    :param value: temperature value in degrees of Celsius
    """
    if value > 28:
        return 0xE60000
    if value > 12:
        return 0xFFCC00
    if value <= 0:
        return 0x33CCCC

    return 0x33CC33


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def main():
    """
    Gather metrics from MQTT and display them.
    """
    try:
        check_tunables(secrets)
    except ConfCheckException as exception:
        bail(str(exception))

    log_level = get_log_level(secrets[LOG_LEVEL])
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    logger.info("Running")

    # Connect to Wi-Fi
    logger.info("Connecting to wifi")
    wifi.radio.connect(secrets[SSID], secrets[PASSWORD], timeout=10)
    logger.info(f"Connected to {secrets[SSID]}")
    logger.debug(f"IP: {wifi.radio.ipv4_address}")

    # Create a socket pool
    pool = socketpool.SocketPool(wifi.radio)  # pylint: disable=no-member

    ntp = setup_nfs(pool)

    metrics = Metrics(
        log_level,
        pool,
        secrets.get(BROKER_HOSTNAME),
        secrets.get(BROKER_PORT),
        secrets.get(METRIC_TIMEOUT),
        0.1,
        [
            (secrets.get(MQTT_TEMP_TOPIC), secrets.get(MQTT_TEMP_NAME)),
            (secrets.get(MQTT_CO2_TOPIC), secrets.get(MQTT_CO2_NAME)),
            (secrets.get(MQTT_PRESSURE_TOPIC), secrets.get(MQTT_PRESSURE_NAME)),
        ],
    )

    # By default, the display will auto refresh.
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

    co2_threshold_value = secrets.get(CO2_THRESHOLD)

    start_hr = secrets.get(START_HR)
    end_hr = secrets.get(END_HR)

    def co2_label_blink1(label):
        label.background_color = 0xFFFFFF

    def co2_label_blink2(label):
        label.background_color = 0x000000

    def co2_label_default(label):
        label.background_color = 0x000000

    blinker = Blinker(co2_area, (co2_label_blink1, co2_label_blink2, co2_label_default))

    while True:
        cur_hr, _ = get_time(ntp)
        if start_hr <= cur_hr <= end_hr:
            metric_dict = metrics.get_metrics()

            temperature = metric_dict.get(secrets.get(MQTT_TEMP_NAME))
            if temperature is None:
                temp_area.text = "N/A"
            else:
                temp_area.text = f"{round(temperature)}°C"
                temp_area.color = get_temp_color(temperature)

            co2 = metric_dict.get(secrets.get(MQTT_CO2_NAME))
            co_prefix = "CO₂"
            if co2 is None:
                co2_area.text = f"{co_prefix} : N/A"
            else:
                co2_area.text = f"{co_prefix} : {co2} ppm"
                # restrict the value to the range [CO2_MIN_VALUE, CO2_MAX_VALUE]
                co2_adjusted = max(CO2_MIN_VALUE, co2)
                co2_adjusted = min(co2_adjusted, CO2_MAX_VALUE)
                co2_reversed = CO2_MAX_VALUE - (co2_adjusted - CO2_MIN_VALUE)
                color = map_range(co2_reversed, CO2_MIN_VALUE, CO2_MAX_VALUE, 0, 80)
                #
                # colorwheel() takes values from 0 to 255 with 0 being red, 40 yellow and 80 green,
                # so the adjusted value has to be reversed for the desired effect of green mapped
                # to the low and red mapped to the high values.
                #
                co2_area.color = rainbowio.colorwheel(int(color))
                if co2 > co2_threshold_value:
                    blinker.set_blinking(True)
                else:
                    blinker.set_blinking(False)

            pressure = metric_dict.get(secrets.get(MQTT_PRESSURE_NAME))
            atm_prefix = "atm"
            if pressure is None:
                atm_area.text = f"{atm_prefix} : N/A"
            else:
                atm_area.text = f"{atm_prefix} : {round(pressure)} hPa"
        else:
            logger.info("outside of hours, setting the display off")
            deep_sleep(graphics, 30)


def setup_nfs(pool) -> NTP:
    """
    setup NTP client and return the NTP object
    """
    logger = logging.getLogger(__name__)
    logger.debug("setting NTP up")
    # The code is supposed to be running in specific time zone
    # with NTP server running on the default router.
    # Use minimum socket timeout (its type is int) to allow for tight loop.
    ntp_server = secrets.get(NTP_SERVER)
    if ntp_server is None:
        ntp_server = str(wifi.radio.ipv4_gateway)
    tz_offset = secrets.get(TZ_OFFSET)
    if tz_offset is None:
        tz_offset = 1
    ntp = adafruit_ntp.NTP(
        pool, server=ntp_server, tz_offset=tz_offset, socket_timeout=1
    )
    return ntp


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
