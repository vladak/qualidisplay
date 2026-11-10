"""
DST utilities
"""

import adafruit_logging as logging


def dst_offset_eu(time_struct) -> int:
    """
    Checks if the supplied time struct matches DST in EU.
    Assumes the input time is non-UTC time.
    Using formula from https://www.webexhibits.org/daylightsaving/i.html
    Since 1996, valid through 2099.
    Code adapted from
    https://forum.arduino.cc/t/daylight-saving-time-adjust-with-ethernet-ntp/192602
    :return: time offset in hours (either 0 or 1)
    """
    hour = time_struct.tm_hour
    day = time_struct.tm_mday
    month = time_struct.tm_mon
    year = time_struct.tm_year

    begin_dst_month = 3  # March
    begin_dst_day = 31 - (5 * year // 4 + 4) % 7
    end_dst_month = 10  # October
    end_dst_day = 31 - (5 * year // 4 + 1) % 7

    # pylint: disable=too-many-boolean-expressions,chained-comparison
    if (
        ((month > begin_dst_month) and (month < end_dst_month))
        or ((month == begin_dst_month) and (day > begin_dst_day))
        or ((month == begin_dst_month) and (day == begin_dst_day) and (hour >= 2))
        or ((month == end_dst_month) and (day < end_dst_day))
        or ((month == end_dst_month) and (day == end_dst_day) and (hour < 1))
    ):
        return 1

    return 0


def get_time(ntp):
    """
    return current time (with DST computed in) from NTP as tuple (hour, minute)
    """
    logger = logging.getLogger(__name__)

    current_time = None  # to silence a warning in IDEA
    attempts = 3
    for i in range(attempts):
        try:
            current_time = ntp.datetime
            break
        except OSError as os_error:
            logger.warning(f"got OSError when getting NTP time: {os_error}")
            if i == attempts - 1:
                raise os_error
            continue

    #
    # NTP returns time with the time offset it was setup with.
    # Add DST offset, if any.
    #
    current_hour = current_time.tm_hour + dst_offset_eu(current_time)
    if current_hour > 23:
        current_hour = 0
    current_minute = current_time.tm_min
    logger.debug(f"time: {current_hour:2}:{current_minute:02}")

    return current_hour, current_minute


def get_time_to_sleep(cur_hr, cur_min, start_hr, end_hr):
    """
    compute time to sleep based on current time
    start_hr/end_hr value of 0 means midnight
    :return: time in seconds
    """
    logger = logging.getLogger(__name__)
    # XXX debug
    logger.setLevel(logging.DEBUG)

    logger.debug(f"{cur_hr:2}:{cur_min:02} start_hr = {start_hr} end_hr = {end_hr}")

    if start_hr == 0:
        start_hr = 24

    assert cur_hr < start_hr or cur_hr >= end_hr

    # TODO: what if the DST transition happens on the next day ?
    if cur_hr < start_hr:
        hrs = start_hr - cur_hr
    else:
        hrs = 24 - cur_hr + start_hr

    mins = 0
    if cur_min > 0:
        mins = 60 - cur_min
        assert hrs >= 1
        hrs -= 1

    logger.debug(f"time to sleep = {hrs}:{mins}")
    return hrs * 3600 + mins * 60
