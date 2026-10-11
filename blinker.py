"""
module that contains the Blinker class
"""

import adafruit_logging as logging

from binarystate import BinaryState


# pylint: disable=too-few-public-methods
class Blinker:
    """
    Encapsulates a method to change binary state of an object from within a tight loop.

    The class is not ready to be used in multiple instances for the same neopixel.
    Assumes that set_blinking() will be called more frequently than the value
    of the duration parameter.

    Not thread safe.
    """

    def __init__(self, subject, change_state, duration: float | int = 0.5):
        """
        initialize the Blinker object
        :param subject: subject object
        :param change_state: triplet of functions (first two for blinking state,
        the third for normal state)
        :param duration: duration of the blinking state in seconds
        """
        self._subject = subject
        self._change_state = change_state
        self.duration = duration

        self._binary_state = BinaryState()
        self._is_on = False

        self.is_blinking = False

    def set_blinking(self, is_blinking: bool):
        """
        :param is_blinking: whether the subject is in blinking state
        """
        logger = logging.getLogger(__name__)

        logger.debug(f"blinking -> {is_blinking}")
        self.is_blinking = is_blinking

        if self.is_blinking:
            duration = self._binary_state.update(self._is_on)
            logger.debug(f"state {self._is_on} duration {duration}")
            if duration > self.duration:
                logger.debug(
                    f"duration {duration} exceeded {self.duration}, switching state"
                )
                self._is_on = not self._is_on
                if self._is_on:
                    self._change_state[0](self._subject)
                else:
                    self._change_state[1](self._subject)
        else:
            self._change_state[2](self._subject)
            self._is_on = False
            self._binary_state.reset()
