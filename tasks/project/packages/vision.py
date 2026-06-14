import os
import numpy as np
import cv2
import yaml
from typing import Tuple
# file for detecting lanes and red stopping lines
# Essentiatlly the same code as the visual_lane_servoing activity with the added ability to detect red lines

# getting the hsv bounds from the project_config folder
_HSV_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'project_config.yaml')

try:
    with open(_HSV_FILE) as _f:
        _h = yaml.safe_load(_f) or {}
except FileNotFoundError:
    print(f"WARNING: Vision config not found at {_HSV_FILE}")
    _h = {}

# Helper to get values with safe defaults so the bot isn't "blind" if the file is missing
def g(key, default): return _h.get(key, default)




_yellow_lower = np.array([_h.get('yellow_lower_h', 0),  _h.get('yellow_lower_s', 0),  _h.get('yellow_lower_v', 0)])
_yellow_upper = np.array([_h.get('yellow_upper_h', 0),  _h.get('yellow_upper_s', 0), _h.get('yellow_upper_v', 0)])

_white_lower = np.array([_h.get('white_lower_h', 0),   _h.get('white_lower_s', 0), _h.get('white_lower_v', 0)])
_white_upper = np.array([_h.get('white_upper_h', 0), _h.get('white_upper_s', 0), _h.get('white_upper_v', 0)])

#adding hsv values to detect red stop lines

_red_lower1 = np.array([_h.get('red_lower_h', 0),   _h.get('red_lower_s', 0), _h.get('red_lower_v', 0)])
_red_upper1 = np.array([_h.get('red_upper_h', 0),  _h.get('red_upper_s', 0), _h.get('red_upper_v', 0)])

_red_lower2 = np.array([_h.get('red_lower_h2', 0), _h.get('red_lower_s', 0), _h.get('red_lower_v', 0)])
_red_upper2 = np.array([_h.get('red_upper_h2', 0), _h.get('red_upper_s', 0), _h.get('red_upper_v', 0)])




#this function works just the same as the detect_lane_markings function
# The reason for defining two masks is the property of hsv wheel
# red color in hsv wraps around the wheel so we need to define two hsv bounds
# meaning we need to return two masks
# the differnce between the hsv bounds is only the hue values see project config file for more
def detect_red_line(image: np.ndarray) -> np.ndarray:
    # seperate function for red masking red lanes
    image = image[160:, :, :]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, _red_lower1, _red_upper1)
    mask2 = cv2.inRange(hsv, _red_lower2, _red_upper2)

    return cv2.bitwise_or(mask1, mask2)


 # we are using this function from visual lane servoing
def detect_lane_markings(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    "cropping bottom half of the image to not get confused with the wall "
    image = image[160:,:,:]

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

   # find yellow lanes based on pixels falling in range of hsv
    mask_yellow = cv2.inRange(hsv, _yellow_lower, _yellow_upper)


    # find white lanes based on pixels falling in range of hsv
    mask_white = cv2.inRange(hsv, _white_lower, _white_upper)

    # Return both masks as a tuple
    return mask_yellow, mask_white
