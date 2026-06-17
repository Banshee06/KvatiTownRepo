import sys
import os
import signal
import threading
import argparse
import time

script_dir   = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(script_dir, '..', '..')
sys.path.insert(0, project_root)

from flask import Flask, Response, render_template_string, request, jsonify
import numpy as np
import cv2
import yaml

from duckiebot.camera_driver import CameraDriver
from duckiebot.wheel_driver import DaguWheelsDriver
from duckiebot.wheel_driver.wheels_driver_abs import WheelPWMConfiguration
from duckiebot.led_driver import LEDDriver
from launcher.ports import find_available_port
from servers.common import shutdown_cleanup, suppress_http_logs
from servers.templates.project import get_template

import tasks.project.packages.agent as agent

app        = Flask(__name__)
camera     = None
wheels     = None
leds       = None
stop_event = threading.Event()
runtime    = agent.ProjectRuntime()

PROJECT_CONFIG_FILE = os.path.join(project_root, 'config', 'project_config.yaml')
PROJECT_DETECTION_FILE = os.path.join(project_root, 'config', 'project_detection.yaml')


def _load_yaml(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _save_yaml(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _placeholder(text):
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, text, (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    return blank


def _stream_runtime_frame(kind):
    while True:
        frame = runtime.get_frame(kind)
        if frame is None:
            frame = _placeholder('Waiting for project agent...')
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n'
                   + jpeg.tobytes() + b'\r\n')
        time.sleep(0.03)


def _project_config_with_defaults():
    cfg = _load_yaml(PROJECT_CONFIG_FILE)
    defaults = {
        'p_gain': 0.1,
        'd_gain': 0.35,
        'max_steer': 0.4,
        'base_speed': 0.2,
        'curve_speed': 0.2,
        'curve_threshold': 350,
        'steering_threshold': 0.2,
        'curve_boost': 1.3,
        'detection_threshold': 500,
    }
    merged = dict(defaults)
    merged.update(cfg)
    return merged


def _detection_config_with_defaults():
    cfg = _load_yaml(PROJECT_DETECTION_FILE)
    defaults = {'img_size': 416, 'conf_threshold': 0.46, 'nms_threshold': 0.45}
    merged = dict(defaults)
    merged.update(cfg)
    return merged


@app.route('/')
def index():
    return render_template_string(
        get_template(title='Project Dashboard', subtitle='Real Duckiebot — Navigation, Detection & Tuning')
    )


@app.route('/video')
def video():
    return Response(_stream_runtime_frame('debug'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/raw')
def video_raw():
    return Response(_stream_runtime_frame('raw'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/debug')
def video_debug():
    return Response(_stream_runtime_frame('debug'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video/mask')
def video_mask():
    return Response(_stream_runtime_frame('mask'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    return jsonify(runtime.get_status())


@app.route('/config')
def get_config():
    project_cfg = _project_config_with_defaults()
    detection_cfg = _detection_config_with_defaults()
    hsv_keys = [
        'white_lower_h', 'white_lower_s', 'white_lower_v',
        'white_upper_h', 'white_upper_s', 'white_upper_v',
        'yellow_lower_h', 'yellow_lower_s', 'yellow_lower_v',
        'yellow_upper_h', 'yellow_upper_s', 'yellow_upper_v',
        'red_lower_h', 'red_upper_h', 'red_lower_s', 'red_upper_s',
        'red_lower_v', 'red_upper_v', 'red_lower_h2', 'red_upper_h2',
    ]
    lane_keys = [
        'p_gain', 'd_gain', 'max_steer', 'base_speed', 'curve_speed',
        'curve_threshold', 'steering_threshold', 'curve_boost',
        'detection_threshold',
    ]
    return jsonify({
        'hsv': {k: project_cfg.get(k) for k in hsv_keys if k in project_cfg},
        'lane': {k: project_cfg.get(k) for k in lane_keys if k in project_cfg},
        'detection': detection_cfg,
    })


@app.route('/get_hsv')
def get_hsv_compat():
    """Compatibility for stale cached pages from older dashboards."""
    project_cfg = _project_config_with_defaults()
    hsv_keys = (
        'white_lower_h', 'white_lower_s', 'white_lower_v',
        'white_upper_h', 'white_upper_s', 'white_upper_v',
        'yellow_lower_h', 'yellow_lower_s', 'yellow_lower_v',
        'yellow_upper_h', 'yellow_upper_s', 'yellow_upper_v',
        'red_lower_h', 'red_upper_h', 'red_lower_s', 'red_upper_s',
        'red_lower_v', 'red_upper_v', 'red_lower_h2', 'red_upper_h2',
    )
    return jsonify({k: project_cfg.get(k) for k in hsv_keys if k in project_cfg})


@app.route('/start', methods=['POST'])
def start():
    runtime.start()
    return jsonify({'status': 'running'})


@app.route('/stop', methods=['POST'])
def stop():
    runtime.stop()
    if wheels:
        wheels.set_wheels_speed(0.0, 0.0)
    return jsonify({'status': 'stopped'})


@app.route('/keys', methods=['POST'])
def keys_compat():
    """No-op compatibility for stale cached manual-drive UI scripts."""
    return jsonify({'status': 'ignored'})


@app.route('/update_detection_config', methods=['POST'])
def update_detection_config():
    data = request.json or {}
    cfg = _detection_config_with_defaults()
    for key in ('conf_threshold', 'nms_threshold'):
        if key in data:
            cfg[key] = float(data[key])
    if 'img_size' in data:
        cfg['img_size'] = int(data['img_size'])
    _save_yaml(PROJECT_DETECTION_FILE, cfg)
    runtime.queue_detection_update(cfg)
    return jsonify({'status': 'ok', 'detection': cfg})


@app.route('/update_lane_config', methods=['POST'])
def update_lane_config():
    data = request.json or {}
    cfg = _project_config_with_defaults()
    lane_keys = (
        'p_gain', 'd_gain', 'max_steer', 'base_speed', 'curve_speed',
        'curve_threshold', 'steering_threshold', 'curve_boost',
        'detection_threshold',
    )
    update = {}
    for key in lane_keys:
        if key in data:
            value = float(data[key])
            cfg[key] = value
            update[key] = value
    _save_yaml(PROJECT_CONFIG_FILE, cfg)
    runtime.queue_lane_update(update)
    return jsonify({'status': 'ok', 'lane': update})


@app.route('/update_hsv', methods=['POST'])
def update_hsv():
    data = request.json or {}
    cfg = _project_config_with_defaults()
    hsv_keys = (
        'white_lower_h', 'white_lower_s', 'white_lower_v',
        'white_upper_h', 'white_upper_s', 'white_upper_v',
        'yellow_lower_h', 'yellow_lower_s', 'yellow_lower_v',
        'yellow_upper_h', 'yellow_upper_s', 'yellow_upper_v',
        'red_lower_h', 'red_upper_h', 'red_lower_s', 'red_upper_s',
        'red_lower_v', 'red_upper_v', 'red_lower_h2', 'red_upper_h2',
    )
    update = {}
    for key in hsv_keys:
        if key in data:
            value = int(data[key])
            cfg[key] = value
            update[key] = value
    _save_yaml(PROJECT_CONFIG_FILE, cfg)
    runtime.queue_hsv_update(update)
    return jsonify({'status': 'ok', 'hsv': update})


@app.route('/command', methods=['POST'])
def command():
    data = request.json or {}
    key = str(data.get('key', '')).strip()
    value = str(data.get('value', '')).strip()
    if not key:
        return jsonify({'status': 'error', 'message': 'key required'}), 400
    if key == 'start':
        runtime.start()
    elif key == 'stop':
        runtime.stop()
        if wheels:
            wheels.set_wheels_speed(0.0, 0.0)
    runtime.push_command(key, value)
    return jsonify({'status': 'ok'})


@app.route('/shutdown')
def shutdown():
    shutdown_cleanup(wheels, camera, stop_event)
    return jsonify({'status': 'ok'})


def main():
    global camera, wheels, leds, stop_event, runtime

    ap = argparse.ArgumentParser(description='Project Server — Real Hardware')
    ap.add_argument('--port', type=int, default=5000)
    args = ap.parse_args()

    suppress_http_logs()
    print('=' * 60)
    print('PROJECT SERVER — REAL HARDWARE')
    print('=' * 60)

    print('\n[1/4] Initializing LED driver...')
    try:
        leds = LEDDriver()
        leds.all_off()
        print('  LEDs: ok')
    except Exception as e:
        print(f'  LEDs: not available ({e})')
        leds = None

    print('\n[2/4] Initializing wheels driver...')
    wheels = DaguWheelsDriver(WheelPWMConfiguration(), WheelPWMConfiguration())
    print('  Wheels: ok')

    print('\n[3/4] Initializing camera driver...')
    camera = CameraDriver()
    camera.start()
    print('  Camera: ok')

    print('\n[4/4] Starting agent...')
    stop_event.clear()
    runtime = agent.ProjectRuntime()
    threading.Thread(
        target=agent.main,
        args=(camera, wheels, leds, stop_event, runtime),
        daemon=True,
        name='AgentThread',
    ).start()
    print('  agent.main() running')

    def _shutdown(signum, frame):
        print('\nShutting down...')
        if leds:
            try:
                leds.all_off()
                leds.release()
            except Exception:
                pass
        shutdown_cleanup(wheels, camera, stop_event)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    web_port = find_available_port(args.port)
    print(f'\nProject dashboard: http://localhost:{web_port}')
    print('Press Ctrl+C to stop\n')

    try:
        app.run(host='0.0.0.0', port=web_port, debug=False, threaded=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if leds:
            try:
                leds.all_off()
                leds.release()
            except Exception:
                pass
        shutdown_cleanup(wheels, camera, stop_event)


if __name__ == '__main__':
    sys.exit(main())
