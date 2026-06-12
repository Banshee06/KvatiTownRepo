from typing import Dict, Tuple
import logging
logger = logging.getLogger(__name__)

SPEED = 1
TURN = 0.5


def get_motor_speeds(keys_pressed: Dict[str, bool]) -> Tuple[float, float]:

    left = 0.0
    right = 0.0

    # 2. Handle Forward and Backward
    if keys_pressed.get('up', False):
        left += SPEED
        right += SPEED

    if keys_pressed.get('down', False):
        left -= SPEED
        right -= SPEED

    # 3. Handle Turning (Differential Drive logic)
    if keys_pressed.get('left', False):
        # To turn left: slow down the left wheel, speed up the right
        left -= TURN
        right += TURN

    if keys_pressed.get('right', False):
        # To turn right: speed up the left wheel, slow down the right
        left += TURN
        right -= TURN

    return float(left), float(right)