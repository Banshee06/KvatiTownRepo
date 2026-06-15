from typing import List, Tuple
import numpy as np


def detect_curve(yellow_xs: List[int],white_xs:  List[int],curve_threshold: int = 350,
    ) -> Tuple[bool, int]:
    if len(yellow_xs) < 2:
        return False, 0

    close_pixel = yellow_xs[0]
    far_pixel = yellow_xs[-1]

    shift = far_pixel - close_pixel

    if abs(shift) > curve_threshold:

        return True, shift

    else:
        return False, 0
