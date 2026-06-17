"""
agent.py — entry point called by server.py
"""

import threading
import queue
import cv2
import time

from tasks.project.packages.agents.lane_serving_agent import LaneServoingAgent
from tasks.project.packages.agents.detection_agent import ObjectDetectionAgent, CLASS_NAMES, CLASS_COLORS
from tasks.project.packages.perception import lane_serving as lane_perception
from tasks.project.packages.planning  import Navigator
from tasks.project.packages.nav_controller import NavigationController

_frame_queue     = queue.Queue(maxsize=1)
_last_detections = []
_detection_lock  = threading.Lock()


class ProjectRuntime:
    """Thread-safe bridge between the project agent loop and Flask UI."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._raw_frame = None
        self._debug_frame = None
        self._mask_frame = None
        self._pending_hsv = None
        self._pending_detection = None
        self._pending_lane = None
        self._commands = []
        self._status = {
            'running': False,
            'agent_ready': False,
            'nav_state': 'initializing',
            'nav_route': 'not ready',
            'model_loaded': False,
            'load_error': None,
            'detections': [],
            'stopped_by_detection': False,
            'stop_reason': '',
            'red_line_detected': False,
            'left_pwm': 0.0,
            'right_pwm': 0.0,
            'frame_count': 0,
        }

    def start(self):
        with self._lock:
            self._running = True
            self._status['running'] = True

    def stop(self):
        with self._lock:
            self._running = False
            self._status['running'] = False

    def is_running(self):
        with self._lock:
            return self._running

    def set_frames(self, raw_frame, debug_frame, mask_frame=None):
        with self._lock:
            self._raw_frame = raw_frame.copy() if raw_frame is not None else None
            self._debug_frame = debug_frame.copy() if debug_frame is not None else None
            self._mask_frame = mask_frame.copy() if mask_frame is not None else None

    def get_frame(self, kind='debug'):
        with self._lock:
            if kind == 'raw':
                frame = self._raw_frame
            elif kind == 'mask':
                frame = self._mask_frame
            else:
                frame = self._debug_frame
            return frame.copy() if frame is not None else None

    def update_status(self, **kwargs):
        with self._lock:
            self._status.update(kwargs)
            self._status['running'] = self._running

    def get_status(self):
        with self._lock:
            status = dict(self._status)
            status['running'] = self._running
            return status

    def queue_hsv_update(self, values):
        with self._lock:
            self._pending_hsv = dict(values)

    def queue_detection_update(self, values):
        with self._lock:
            self._pending_detection = dict(values)

    def queue_lane_update(self, values):
        with self._lock:
            self._pending_lane = dict(values)

    def consume_updates(self):
        with self._lock:
            updates = self._pending_hsv, self._pending_detection, self._pending_lane
            self._pending_hsv = None
            self._pending_detection = None
            self._pending_lane = None
            return updates

    def push_command(self, key, value):
        with self._lock:
            self._commands.append({'key': str(key), 'value': str(value), 'ts': time.time()})
            self._commands = self._commands[-20:]


def _detections_for_status(detections):
    return [
        {
            'class': CLASS_NAMES.get(class_id, str(class_id)),
            'score': round(float(score), 3),
            'bbox': [int(v) for v in bbox],
        }
        for bbox, score, class_id in detections
    ]


def _apply_runtime_updates(runtime, lane_agent, det_agent):
    if runtime is None:
        return

    hsv_update, detection_update, lane_update = runtime.consume_updates()

    if hsv_update:
        lane_perception.apply_hsv_config(hsv_update)

    if detection_update:
        if 'conf_threshold' in detection_update:
            det_agent.conf_threshold = float(detection_update['conf_threshold'])
        if 'nms_threshold' in detection_update:
            det_agent.nms_threshold = float(detection_update['nms_threshold'])

    if lane_update:
        for key in (
            'p_gain', 'd_gain', 'max_steer', 'base_speed', 'curve_speed',
            'curve_threshold', 'steering_threshold', 'curve_boost',
            'detection_threshold',
        ):
            if key in lane_update and hasattr(lane_agent, key):
                setattr(lane_agent, key, float(lane_update[key]))


def _draw_overlay(frame_bgr, detections, controller, det_agent, left, right, running):
    out = frame_bgr.copy()
    h, w = out.shape[:2]

    for bbox, score, class_id in detections:
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(w - 1, int(x1)))
        x2 = max(0, min(w - 1, int(x2)))
        y1 = max(0, min(h - 1, int(y1)))
        y2 = max(0, min(h - 1, int(y2)))
        color = CLASS_COLORS.get(class_id, (255, 255, 255))
        label = f"{CLASS_NAMES.get(class_id, class_id)} {float(score):.2f}"
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        ly = max(0, y1 - th - baseline - 4)
        cv2.rectangle(out, (x1, ly), (x1 + tw + 6, ly + th + baseline + 4), color, -1)
        cv2.putText(out, label, (x1 + 3, ly + th + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    nav = controller.status() if controller is not None else {}
    status_lines = [
        f"{'RUNNING' if running else 'STOPPED'}",
        f"state: {nav.get('nav_state', 'unknown')}",
        f"route: {nav.get('nav_route', 'unknown')}",
        f"pwm: L {left:+.2f}  R {right:+.2f}",
        f"model: {'loaded' if det_agent.model_loaded else 'missing'}",
    ]
    if nav.get('stop_reason'):
        status_lines.append(f"stop: {nav['stop_reason']}")
    if nav.get('red_line_detected'):
        status_lines.append("red line detected")

    y = 24
    for line in status_lines:
        cv2.putText(out, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 255, 0) if running else (0, 180, 255), 2, cv2.LINE_AA)
        y += 22

    return out


def _draw_mask_view(frame_bgr):
    """Create a visual-servoing-style mask dashboard for project HSV perception."""
    try:
        mask_yellow, mask_white = lane_perception.detect_lane_markings(frame_bgr)
        mask_red = lane_perception.detect_red_line(frame_bgr)
    except Exception as e:
        out = frame_bgr.copy()
        cv2.putText(out, f"Mask error: {e}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 255), 2, cv2.LINE_AA)
        return out

    roi = frame_bgr[160:, :, :]
    h, w = roi.shape[:2]
    display_w = 320
    display_h = int(h * display_w / w)

    cam = cv2.resize(roi, (display_w, display_h))

    combined = cv2.bitwise_or(mask_yellow, mask_white)
    combined = cv2.bitwise_or(combined, mask_red)
    combined_vis = cv2.resize(cv2.applyColorMap(combined, cv2.COLORMAP_HOT),
                              (display_w, display_h))

    lane_color = np.zeros((*mask_yellow.shape, 3), dtype=np.uint8)
    lane_color[:, :, 0] = mask_white
    lane_color[:, :, 1] = np.maximum(mask_white, mask_yellow)
    lane_color[:, :, 2] = mask_yellow
    lane_vis = cv2.resize(lane_color, (display_w, display_h))

    red_color = np.zeros((*mask_red.shape, 3), dtype=np.uint8)
    red_color[:, :, 2] = mask_red
    red_vis = cv2.resize(red_color, (display_w, display_h))

    grid = np.vstack([
        np.hstack([cam, combined_vis]),
        np.hstack([lane_vis, red_vis]),
    ])

    font = cv2.FONT_HERSHEY_SIMPLEX
    green = (0, 255, 0)
    cv2.putText(grid, "Camera ROI", (10, 22), font, 0.55, green, 1)
    cv2.putText(grid, "Combined HSV Mask", (display_w + 10, 22), font, 0.55, green, 1)
    cv2.putText(grid, "White + Yellow Lanes", (10, display_h + 22), font, 0.55, green, 1)
    cv2.putText(grid, "Red Stop-Line Mask", (display_w + 10, display_h + 22), font, 0.55, green, 1)

    counts = (
        f"yellow={int(np.count_nonzero(mask_yellow))}  "
        f"white={int(np.count_nonzero(mask_white))}  "
        f"red={int(np.count_nonzero(mask_red))}"
    )
    cv2.putText(grid, counts, (10, grid.shape[0] - 12), font, 0.5, (255, 255, 255), 1)
    return grid


def main(camera, wheels, leds, stop_event, runtime=None):
    """Called by server.py with hardware already initialised."""
    global _last_detections

    if runtime is None:
        runtime = ProjectRuntime()
        runtime.start()

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
    runtime.update_status(
        agent_ready=True,
        model_loaded=det_agent.model_loaded,
        load_error=det_agent.load_error,
        conf_threshold=det_agent.conf_threshold,
        nms_threshold=det_agent.nms_threshold,
        nav_state=controller.state.name,
        nav_route=navigator.progress() if navigator.has_route() else 'no route',
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
        success, frame_bgr = camera.read()
        if not success or frame_bgr is None:
            continue

        if frame_bgr.ndim == 3 and frame_bgr.shape[2] == 4:
            frame_bgr = frame_bgr[:, :, :3]

        _apply_runtime_updates(runtime, lane_agent, det_agent)

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Push to detection thread (never block steering)
        try:
            _frame_queue.put_nowait(frame_rgb)
        except queue.Full:
            pass

        # Get latest detections (may be 1-2 frames old — fine)
        with _detection_lock:
            detections = list(_last_detections)

        if runtime.is_running():
            # FSM decides everything — your homework functions run inside step()
            left, right, state = controller.step(
                frame_rgb=frame_rgb,
                frame_bgr=frame_bgr,
                detections=detections,
            )
        else:
            left, right, state = 0.0, 0.0, controller.state.name

        wheels.set_wheels_speed(left, right)
        nav_status = controller.status()
        debug_frame = _draw_overlay(
            frame_bgr, detections, controller, det_agent, left, right, runtime.is_running()
        )
        mask_frame = _draw_mask_view(frame_bgr)
        runtime.set_frames(frame_bgr, debug_frame, mask_frame)
        runtime.update_status(
            agent_ready=True,
            nav_state=state,
            nav_route=nav_status.get('nav_route', ''),
            next_action=nav_status.get('next_action', ''),
            stopped_by_detection=nav_status.get('stopped_by_detection', False),
            stop_reason=nav_status.get('stop_reason', ''),
            red_line_detected=nav_status.get('red_line_detected', False),
            detections=_detections_for_status(detections),
            detection_count=len(detections),
            model_loaded=det_agent.model_loaded,
            load_error=det_agent.load_error,
            conf_threshold=det_agent.conf_threshold,
            nms_threshold=det_agent.nms_threshold,
            left_pwm=float(left),
            right_pwm=float(right),
            frame_count=int(camera.frame_count),
            lane_p_gain=float(lane_agent.p_gain),
            lane_d_gain=float(lane_agent.d_gain),
            lane_base_speed=float(lane_agent.base_speed),
            lane_detection_threshold=float(lane_agent.detection_threshold),
        )

    wheels.set_wheels_speed(0.0, 0.0)
    runtime.stop()