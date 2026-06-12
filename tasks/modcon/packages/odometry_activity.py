from typing import Tuple
import numpy as np


def delta_phi(ticks: int, prev_ticks: int, resolution: int) -> Tuple[float, float]:
    delta_ticks = ticks - prev_ticks

    d_phi = delta_ticks * (2 * np.pi / resolution)

    return float(d_phi), ticks


def pose_estimation(
    R: float,
    baseline: float,
    x_prev: float,
    y_prev: float,
    theta_prev: float,
    delta_phi_left: float,
    delta_phi_right: float,
) -> Tuple[float, float, float]:
    # calculate the distance covered by each wheel

    d_l = R * delta_phi_left
    d_r = R * delta_phi_right

    # calculate distance covered by the bot

    d_a = (d_l + d_r) / 2.0

    # calculate delta theta using d_l and d_r

    delta_theta = (d_r - d_l) / baseline

    # calculate delta of x and y coordinates

    d_x = d_a * np.cos(theta_prev)
    d_y = d_a * np.sin(theta_prev)

    # calculate new theta new x and y coordinates

    x = x_prev + d_x
    y = y_prev + d_y
    theta = theta_prev + delta_theta

    return float(x), float(y), float(theta)