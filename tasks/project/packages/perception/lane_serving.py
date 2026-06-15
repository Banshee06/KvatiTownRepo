from typing import Tuple
import os
import numpy as np
import cv2
import yaml
# we are using the same code from the lane_servoing task
# config file is different
_HSV_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'project_config.yaml')
try:
    with open(_HSV_FILE) as _f:
        _h = yaml.safe_load(_f) or {}
except FileNotFoundError:
    _h = {}

_yellow_lower = np.array([_h.get('yellow_lower_h', 0),  _h.get('yellow_lower_s', 0),  _h.get('yellow_lower_v', 0)])
_yellow_upper = np.array([_h.get('yellow_upper_h', 0),  _h.get('yellow_upper_s', 0), _h.get('yellow_upper_v', 0)])

_white_lower = np.array([_h.get('white_lower_h', 0),   _h.get('white_lower_s', 0), _h.get('white_lower_v', 0)])
_white_upper = np.array([_h.get('white_upper_h', 0), _h.get('white_upper_s', 0), _h.get('white_upper_v', 0)])

#adding hsv values to detect red stop lines
#see lane servoing hsv file for details about the numbers of bounds for color red
_red_lower1 = np.array([_h.get('red_lower_h', 0),   _h.get('red_lower_s', 0), _h.get('red_lower_v', 0)])
_red_upper1 = np.array([_h.get('red_upper_h', 0),  _h.get('red_upper_s', 0), _h.get('red_upper_v', 0)])

_red_lower2 = np.array([_h.get('red_lower_h2', 0), _h.get('red_lower_s', 0), _h.get('red_lower_v', 0)])
_red_upper2 = np.array([_h.get('red_upper_h2', 0), _h.get('red_upper_s', 0), _h.get('red_upper_v', 0)])





def detect_red_line(image: np.ndarray) -> np.ndarray:
    # seperate function for red masking red lanes
    image = image[160:, :, :]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, _red_lower1, _red_upper1)
    mask2 = cv2.inRange(hsv, _red_lower2, _red_upper2)

    return cv2.bitwise_or(mask1, mask2)


def detect_lane_markings(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    "cropping bottom half of the image to not get confused with the wall "
    image = image[160:,:,:]

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

   # find yellow lanes based on pixels falling in range of hsv
    mask_yellow = cv2.inRange(hsv, _yellow_lower, _yellow_upper)


    # find white lanes based on pixels falling in range of hsv
    mask_white = cv2.inRange(hsv, _white_lower, _white_upper)

    # 4. Return both masks as a tuple
    return mask_yellow, mask_white




def set_hsv_bounds(yellow_lower, yellow_upper, white_lower, white_upper):
    global _yellow_lower, _yellow_upper, _white_lower, _white_upper
    _yellow_lower    = np.array(yellow_lower)
    _yellow_upper    = np.array(yellow_upper)
    _white_lower = np.array(white_lower)
    _white_upper = np.array(white_upper)

def get_hsv_bounds():
    return {
        'yellow_lower_h': int(_yellow_lower[0]),    'yellow_upper_h': int(_yellow_upper[0]),
        'yellow_lower_s': int(_yellow_lower[1]),    'yellow_upper_s': int(_yellow_upper[1]),
        'yellow_lower_v': int(_yellow_lower[2]),    'yellow_upper_v': int(_yellow_upper[2]),
        'white_lower_h':  int(_white_lower[0]), 'white_upper_h':  int(_white_upper[0]),
        'white_lower_s':  int(_white_lower[1]), 'white_upper_s':  int(_white_upper[1]),
        'white_lower_v':  int(_white_lower[2]), 'white_upper_v':  int(_white_upper[2]),
    }