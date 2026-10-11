"""
Various functions for checking configuration.
"""

import sys

# pylint: disable=unused-wildcard-import, wildcard-import
from names import *


class ConfCheckException(Exception):
    """
    designated exception for configuration check failure
    """


def check_string(secrets: dict, name: str, mandatory: bool = True) -> None:
    """
    Check is string with given name is present in secrets.
    """
    value = secrets.get(name)
    if value is None:
        if mandatory:
            raise ConfCheckException(f"{name} is missing")
        return

    if value and not isinstance(value, str):
        raise ConfCheckException(f"not a string value for {name}: {value}")


def check_int(
    secrets: dict, name: str, mandatory: bool = True, min_val=None, max_val=None
) -> None:
    """
    Check is integer with given name is present in secrets.
    """
    value = secrets.get(name)
    if value is None:
        if mandatory:
            raise ConfCheckException(f"{name} is missing")
        return

    if not isinstance(value, int):
        raise ConfCheckException(f"not a integer value for {name}: {value}")

    if min_val is not None and value < min_val:
        raise ConfCheckException(f"{name} value {value} smaller than minimum {min_val}")

    if max_val is not None and value > max_val:
        raise ConfCheckException(f"{name} value {value} higher than maximum {max_val}")


def check_list(secrets: dict, name: str, subtype, mandatory: bool = True) -> None:
    """
    Check whether list with given name is present in secrets.
    """
    value = secrets.get(name)
    if value is None:
        if mandatory:
            raise ConfCheckException(f"{name} is missing")
        return

    if value and not isinstance(value, list):
        raise ConfCheckException(f"not a integer value for {name}: {value}")

    for item in value:
        if item and not isinstance(item, subtype):
            raise ConfCheckException(f"not a {subtype}: {item}")


def check_bytes(secrets: dict, name: str, length: int, mandatory: bool = True) -> None:
    """
    Check is bytes with given name is present in secrets.
    """
    value = secrets.get(name)
    if value is None:
        if mandatory:
            raise ConfCheckException(f"{name} is missing")
        return

    if value and not isinstance(value, bytes):
        raise ConfCheckException(f"not a byte value for {name}: {value}")

    if value and len(value) != length:
        raise ConfCheckException(
            f"not correct length for {name}: {len(value)} should be {length}"
        )


def bail(message: str) -> None:
    """
    Print message and exit with code 1.
    """
    print(message)
    sys.exit(1)


def check_tunables(secrets: dict) -> None:
    """
    Check that tunables are present and of correct type.
    Will throw ConfCheckException on error.
    """
    check_string(secrets, LOG_LEVEL)

    check_string(secrets, SSID)
    check_string(secrets, PASSWORD)

    check_string(secrets, BROKER_HOSTNAME)
    check_int(secrets, BROKER_PORT, min_val=0, max_val=65535)

    check_string(secrets, MQTT_TEMP_TOPIC)
    check_string(secrets, MQTT_CO2_TOPIC)
    check_string(secrets, MQTT_PRESSURE_TOPIC)

    check_int(secrets, START_HR)
    check_int(secrets, END_HR)

    check_int(secrets, CO2_THRESHOLD)

    check_string(secrets, TEMP_FONT_FILE)
    check_string(secrets, CO2_FONT_FILE)
