import colorsys
from typing import List


def set_turning_leds(direction: str) -> dict:
    """Set LEDs to indicate turning direction."""
    off = [0.0,0.0,0.0]
    yellow = [1.0,1.0,0.0]
    red = [1.0,0.0,0.0]
    white = [1.0,1.0,1.0]

    leds = {}

    if direction == "left":
        leds = {0:yellow, 2:off, 4:yellow,3:off}

    elif direction == "right":
        leds = {0:off, 2:yellow, 4:off, 3:yellow}

    elif direction == "forward":
        leds = {0:white, 2:white, 4:off, 3:off}

    elif direction == "stop":
        leds = {0:off, 2:off, 4:red, 3:red}

    else:
        leds = {0:off, 2:off, 4:off, 3:off}

        return leds