"""
agent.py — entry point called by server.py
"""

import threading
import queue
import cv2

from tasks.project.packages.agents.lane_serving_agent import LaneServoingAgent
from tasks.project.packages.agents.detection_agent    import ObjectDetectionAgent
from tasks.project.packages.planning  import Navigator
from tasks.project.packages.nav_controller import NavigationController

_frame_queue     = queue.Queue(maxsize=1)
_last_detections = []
_detection_lock  = threading.Lock()


def main(camera, wheels, leds, stop_event):
    """Called by server.py with hardware already initialised."""

    # Boot agents and planner
    lane_agent = LaneServoingAgent()
    det_agent  = ObjectDetectionAgent()
    navigator  = Navigator()          # reads map.yaml, runs Dijkstra
    controller = NavigationController(
        lane_agent = lane_agent,
        det_agent  = det_agent,
        navigator  = navigator,
        led_driver = leds,
    )

    # Detection runs in its own thread — inference is slow
    def detection_loop():
        global _last_detections
        while not stop_event.is_set():
            try:
                frame_rgb = _frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            result = det_agent.detect(frame_rgb)
            if result is not None:
                with _detection_lock:
                    _last_detections = result

    threading.Thread(target=detection_loop, daemon=True).start()

    # Main camera loop
    while not stop_event.is_set():
        success,frame_bgr = camera.read()
        if not success or frame_bgr is None:
            continue

        if frame_bgr.ndim == 3 and frame_bgr.shape[2] == 4:
            frame_bgr = frame_bgr[:, :, :3]

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Push to detection thread (never block steering)
        try:
            _frame_queue.put_nowait(frame_rgb)
        except queue.Full:
            pass

        # Get latest detections (may be 1-2 frames old — fine)
        with _detection_lock:
            detections = list(_last_detections)

        # FSM decides everything — your homework functions run inside step()
        left, right, state = controller.step(
            frame_rgb  = frame_rgb,
            frame_bgr  = frame_bgr,
            detections = detections,
        )

        wheels.set_wheels_speed(left, right)