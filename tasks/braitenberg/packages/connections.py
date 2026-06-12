from typing import Tuple
import numpy as np


def get_motor_left_matrix(shape: Tuple[int, int]) -> np.ndarray:
    """Left motor weight matrix: highest at bottom-left, decreasing toward top-right."""
    rows, cols = shape

    # Create a 2D grid of coordinates
    # r goes from 0 (top) to 1 (bottom)
    # c goes from 0 (left) to 1 (right)
    r, c = np.indices(shape)
    r = r / rows
    c = c / cols

    # Logic: High at bottom (r is big), High at left (c is small)
    # (1-c) makes it high on the left
    res = r * (1 - c)
    return res

def get_motor_right_matrix(shape: Tuple[int, int]) -> np.ndarray:
    """Right motor weight matrix: highest at bottom-right, decreasing toward top-left."""
    rows, cols = shape
    r, c = np.indices(shape)
    r = r / rows
    c = c / cols

    # Logic: High at bottom (r is big), High at right (c is big)
    res = r * c
    return res
