"""
navigation_controller.py  — FSM state machine for Duckiebot navigation
"""

import time
from enum import Enum, auto
from typing import Tuple
import numpy as np

# importing the functions from
from tasks.project.packages.detection.stop_logic   import should_stop
from tasks.project.packages.perception.lane_serving import detect_red_line

# Tuneable constants
RED_LINE_SCAN_ROWS       = 30
RED_LINE_MIN_PIXELS      = 400
STOP_WAIT_SEC            = 2.0
TURN_DURATION_SEC        = {'left': 1.8, 'right': 1.8, 'straight': 1.0}
TURN_COMMANDS            = {'left': (0.0, 0.30), 'right': (0.30, 0.0), 'straight': (0.25, 0.25)}
RED_LINE_COOLDOWN_SEC    = 4.0
DUCKIE_RESUME_COOLDOWN_SEC = 1.5
LED_FLASH_HZ             = 2.0

# LED colors (R, G, B)
LED_OFF         = (0,   0,   0)
LED_DRIVING     = (0,   200, 0)
LED_DUCKIE_STOP = (255, 100, 0)
LED_STOP_LINE   = (255, 255, 0)
LED_TURNING     = (0,   0,  255)
LED_GOAL        = (255, 0,   0)


# States
class State(Enum):
    LANE_FOLLOWING = auto()
    DUCKIE_STOP    = auto()
    AT_STOP_LINE   = auto()
    TURNING        = auto()
    GOAL_REACHED   = auto()


#  Red line helper function
def _is_red_line_close(red_mask: np.ndarray) -> bool:
    if red_mask is None or red_mask.size == 0:
        return False
    h          = red_mask.shape[0]
    scan_start = max(0, h - RED_LINE_SCAN_ROWS)
    band       = red_mask[scan_start:, :]
    return int(np.count_nonzero(band)) >= RED_LINE_MIN_PIXELS


#  LED wrapper
class LEDController:
    def __init__(self, driver=None):
        self._driver   = driver
        self._flash_on = False
        self._flash_t  = 0.0

    def solid(self, color):
        self._apply(color)

    def flash_update(self, color, now):
        if now - self._flash_t >= 1.0 / LED_FLASH_HZ:
            self._flash_t  = now
            self._flash_on = not self._flash_on
        self._apply(color if self._flash_on else LED_OFF)

    def off(self):
        self._apply(LED_OFF)

    def _apply(self, color):
        if self._driver is None:
            return
        try:
            rgb = [float(c) / 255.0 if max(color) > 1 else float(c) for c in color]
            if hasattr(self._driver, 'set_all'):
                self._driver.set_all(rgb)
            else:
                for led in (0, 2, 3, 4):
                    self._driver.set_rgb(led, rgb)
        except Exception as e:
            print(f"[LED] {e}")



class NavigationController:


    def __init__(self, lane_agent, det_agent, navigator, led_driver=None):
        self.lane_agent = lane_agent
        self.det_agent  = det_agent
        self.navigator  = navigator
        self.led        = LEDController(led_driver)

        self.state          = State.LANE_FOLLOWING
        self._turn_action   = 'straight'
        self._stop_line_t   = 0.0
        self._turn_t        = 0.0
        self._red_cooldown  = 0.0
        self._duckie_resume = 0.0
        self._last_stop_flag = False
        self._last_stop_reason = ''
        self._last_red_close = False
        self._last_lane_command = (0.0, 0.0)
        self._last_output = (0.0, 0.0)

        print("[NavCtrl] Ready — LANE_FOLLOWING")
        self.led.solid(LED_DRIVING)

    def step(self, frame_rgb, frame_bgr, detections) -> Tuple[float, float, str]:
        now = time.time()


        img_size            = self.det_agent.img_size if self.det_agent else 416
        stop_flag, reason   = should_stop(detections, img_size)
        red_mask            = detect_red_line(frame_bgr)
        red_close           = _is_red_line_close(red_mask) and now > self._red_cooldown
        lane_l, lane_r      = self.lane_agent.compute_commands(frame_rgb)

        self._last_stop_flag = stop_flag
        self._last_stop_reason = reason
        self._last_red_close = red_close
        self._last_lane_command = (lane_l, lane_r)

        left, right = self._fsm(now, stop_flag, reason, red_close, lane_l, lane_r)
        self._last_output = (left, right)


        if self.state == State.GOAL_REACHED:
            self.led.flash_update(LED_GOAL, now)

        return left, right, self.state.name

        # FSM
    def _fsm(self, now, stop_flag, stop_reason, red_close, lane_l, lane_r):

        if self.state == State.LANE_FOLLOWING:
            if stop_flag and now > self._duckie_resume:
                print(f"[NavCtrl] → DUCKIE_STOP ({stop_reason})")
                self._enter(State.DUCKIE_STOP, LED_DUCKIE_STOP)
                return 0.0, 0.0
            if red_close and self.navigator.has_route():
                print("[NavCtrl] → AT_STOP_LINE")
                self._stop_line_t  = now
                self._red_cooldown = now + RED_LINE_COOLDOWN_SEC
                self._enter(State.AT_STOP_LINE, LED_STOP_LINE)
                return 0.0, 0.0
            return lane_l, lane_r

        elif self.state == State.DUCKIE_STOP:
            if not stop_flag:
                print("[NavCtrl] → LANE_FOLLOWING (duckie cleared)")
                self._duckie_resume = now + DUCKIE_RESUME_COOLDOWN_SEC
                self._enter(State.LANE_FOLLOWING, LED_DRIVING)
            return 0.0, 0.0

        elif self.state == State.AT_STOP_LINE:
            if now - self._stop_line_t < STOP_WAIT_SEC:
                return 0.0, 0.0

            action = self.navigator.next_action()
            print(f"[NavCtrl] Stop-line action: {action!r}")

            if action == 'GOAL':
                print("[NavCtrl] ★ GOAL REACHED ★")
                self._enter(State.GOAL_REACHED, LED_GOAL)
                return 0.0, 0.0

            if action in ('follow', 'straight'):
                self._enter(State.LANE_FOLLOWING, LED_DRIVING)
                return lane_l, lane_r

            self._turn_action = action
            self._turn_t      = now
            self._enter(State.TURNING, LED_TURNING)
            l, r = TURN_COMMANDS.get(action, (0.25, 0.25))
            return l, r

        elif self.state == State.TURNING:
            duration = TURN_DURATION_SEC.get(self._turn_action, 1.8)
            if now - self._turn_t >= duration:
                print("[NavCtrl] → LANE_FOLLOWING (turn done)")
                self._enter(State.LANE_FOLLOWING, LED_DRIVING)
                return lane_l, lane_r
            l, r = TURN_COMMANDS.get(self._turn_action, (0.25, 0.25))
            return l, r

        elif self.state == State.GOAL_REACHED:
            return 0.0, 0.0

        return 0.0, 0.0

    def _enter(self, new_state, led_color):
        self.state = new_state
        self.led.solid(led_color)

    def status(self):
        return {
            'nav_state': self.state.name,
            'nav_route': self.navigator.progress() if self.navigator.has_route() else 'no route',
            'next_action': self.navigator.peek_action() if self.navigator.has_route() else '',
            'stopped_by_detection': self._last_stop_flag,
            'stop_reason': self._last_stop_reason,
            'red_line_detected': self._last_red_close,
            'turn_action': self._turn_action,
            'lane_command': {
                'left': float(self._last_lane_command[0]),
                'right': float(self._last_lane_command[1]),
            },
            'output_command': {
                'left': float(self._last_output[0]),
                'right': float(self._last_output[1]),
            },
        }