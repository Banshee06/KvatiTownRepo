from .base import render_template

_CONTENT = '''
    <div class="container">
        <div class="video-section">
            <div class="dual-video">
                <div class="video-card">
                    <div class="video-title">Detection / Navigation Overlay</div>
                    <img src="/video/debug" class="stream project-stream" id="debugStream">
                </div>
                <div class="video-card">
                    <div class="video-title">Lane / Red HSV Mask View</div>
                    <img src="/video/mask" class="stream project-stream" id="maskStream">
                </div>
                <div class="video-card">
                    <div class="video-title">Raw Bot Camera</div>
                    <img src="/video/raw" class="stream project-stream" id="rawStream">
                </div>
            </div>
        </div>

        <div class="controls-section">

            <div class="card">
                <div class="card-header">
                    Drive Control
                    <span id="statusDot" style="width:8px;height:8px;border-radius:50%;
                        background:var(--accent-red);display:inline-block;"></span>
                </div>
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
                    <span id="run-indicator" class="run-indicator"></span>
                    <span id="run-label" class="run-label">STOPPED</span>
                </div>
                <div style="display:flex;gap:8px">
                    <button onclick="driveStart()" class="button success" style="flex:1">Start</button>
                    <button onclick="driveStop()" class="button danger" style="flex:1">Stop</button>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Navigation Status</div>
                <div class="stats-grid" style="grid-template-columns:1fr 1fr">
                    <div class="stat-box"><div class="stat-value" id="nav-state">--</div><div class="stat-label">State</div></div>
                    <div class="stat-box"><div class="stat-value" id="next-action">--</div><div class="stat-label">Next action</div></div>
                </div>
                <div id="statusTable" class="status-table"></div>
            </div>

            <div class="card">
                <div class="card-header">
                    Detection
                    <span id="det-count" style="font-size:11px;font-weight:400;color:var(--text-muted)"></span>
                </div>
                <div id="model-status" class="model-status">Loading...</div>
                <div id="detections" class="detections-list">
                    <div class="empty-state">Waiting for detections...</div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Detection Configuration</div>
                <div id="detection-controls"></div>
                <button onclick="applyDetectionConfig()" class="button success">Apply Detection Configuration</button>
                <div id="detection-status" class="status"></div>
            </div>

            <div class="card">
                <div class="card-header">Lane Controller</div>
                <div id="lane-controls"></div>
                <button onclick="applyLaneConfig()" class="button success">Apply Lane Configuration</button>
                <div id="lane-status" class="status"></div>
            </div>

            <div class="card">
                <div class="card-header">HSV Configuration</div>
                <div id="hsv-controls"></div>
                <button onclick="applyHSVConfig()" class="button success">Apply HSV Configuration</button>
                <div id="hsv-status" class="status"></div>
            </div>

        </div>
    </div>
'''

_EXTRA_CSS = '''
.dual-video {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    width: 100%;
    height: 100%;
}
.video-card {
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.video-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
}
.project-stream {
    background: #000;
    border: 1px solid var(--border-color);
    min-height: 0;
}
.run-indicator {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent-red);
    display: inline-block;
}
.run-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
}
.status-table .row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid var(--border-color);
    align-items: baseline;
    gap: 8px;
}
.status-table .row:last-child { border-bottom: none; }
.status-table .key  { color: var(--text-secondary); font-size: 12px; }
.status-table .val  { color: var(--text-primary); font-weight: 500; font-size: 12px; font-family: monospace; text-align:right; overflow-wrap:anywhere; }
.detections-list { display:flex; flex-direction:column; gap:6px; max-height:180px; overflow-y:auto; }
.det-row { display:grid; grid-template-columns:1fr auto; gap:6px; padding:6px 8px; background:var(--bg-sidebar); border:1px solid var(--border-color); border-radius:4px; font-size:12px; }
.det-meta { color:var(--text-muted); grid-column:1 / span 2; font-size:11px; font-family:monospace; }
.empty-state { color:var(--text-muted); text-align:center; padding:10px; font-size:12px; }
.model-status { padding:6px 10px; border-radius:4px; font-size:12px; margin-bottom:10px; background:rgba(210,153,34,0.1); border:1px solid rgba(210,153,34,0.3); color:var(--accent-orange); }
.model-status.ok { background:rgba(63,185,80,0.1); border-color:rgba(63,185,80,0.3); color:var(--accent-green); }
.model-status.err { background:rgba(248,81,73,0.1); border-color:rgba(248,81,73,0.3); color:var(--accent-red); }
.compact-slider { margin-bottom:10px; }
.compact-slider .slider-label { margin-bottom:4px; }
.hsv-section { margin: 8px 0 14px; padding-top:8px; border-top:1px solid var(--border-color); }
.hsv-title { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:8px; }
.hsv-title.white { color:#ecf0f1; }
.hsv-title.yellow { color:#f1c40f; }
.hsv-title.red { color:#f85149; }
@media (max-width: 1200px) {
    .dual-video { grid-template-columns: 1fr; }
}
'''

_EXTRA_JS = '''
let detectionConfig = {};
let laneConfig = {};
let hsvConfig = {};

function setRunningUI(isRunning) {
    document.getElementById('run-indicator').style.background = isRunning ? '#2ecc71' : '#f85149';
    document.getElementById('statusDot').style.background = isRunning ? '#2ecc71' : '#f85149';
    const label = document.getElementById('run-label');
    label.textContent = isRunning ? 'RUNNING' : 'STOPPED';
    label.style.color = isRunning ? '#2ecc71' : 'var(--text-secondary)';
}

function driveStart() {
    postJSON('/start', {}).then(() => setRunningUI(true));
}

function driveStop() {
    postJSON('/stop', {}).then(() => setRunningUI(false));
}

function makeSlider(container, state, id, label, min, max, step, value) {
    state[id] = Number(value);
    const el = document.createElement('div');
    el.className = 'compact-slider';
    el.innerHTML = `
        <div class="slider-label"><span>${label}</span><span>${min}-${max}</span></div>
        <div class="slider-controls">
            <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${value}" class="slider">
            <input type="number" id="${id}-input" min="${min}" max="${max}" step="${step}" value="${value}" class="input-box">
        </div>`;
    container.appendChild(el);
    const slider = document.getElementById(id);
    const input = document.getElementById(id + '-input');
    const update = value => {
        state[id] = Number(value);
        slider.value = value;
        input.value = value;
    };
    slider.addEventListener('input', () => update(slider.value));
    input.addEventListener('input', () => update(input.value));
}

function buildControls(config) {
    detectionConfig = {};
    laneConfig = {};
    hsvConfig = {};

    const det = document.getElementById('detection-controls');
    det.innerHTML = '';
    makeSlider(det, detectionConfig, 'conf_threshold', 'Confidence threshold', 0, 1, 0.01, config.detection.conf_threshold ?? 0.46);
    makeSlider(det, detectionConfig, 'nms_threshold', 'NMS threshold', 0, 1, 0.01, config.detection.nms_threshold ?? 0.45);

    const lane = document.getElementById('lane-controls');
    lane.innerHTML = '';
    makeSlider(lane, laneConfig, 'p_gain', 'Lateral gain', 0, 2, 0.01, config.lane.p_gain ?? 0.1);
    makeSlider(lane, laneConfig, 'd_gain', 'Derivative gain', 0, 2, 0.01, config.lane.d_gain ?? 0.35);
    makeSlider(lane, laneConfig, 'base_speed', 'Base speed', 0, 1, 0.01, config.lane.base_speed ?? 0.2);
    makeSlider(lane, laneConfig, 'curve_speed', 'Curve speed', 0, 1, 0.01, config.lane.curve_speed ?? 0.2);
    makeSlider(lane, laneConfig, 'detection_threshold', 'Lane pixel threshold', 0, 5000, 10, config.lane.detection_threshold ?? 500);

    const hsv = document.getElementById('hsv-controls');
    hsv.innerHTML = '';
    const sections = [
        ['white', 'White Lane', [
            ['white_lower_h', 'Hue low', 0, 179], ['white_upper_h', 'Hue high', 0, 179],
            ['white_lower_s', 'Sat low', 0, 255], ['white_upper_s', 'Sat high', 0, 255],
            ['white_lower_v', 'Val low', 0, 255], ['white_upper_v', 'Val high', 0, 255],
        ]],
        ['yellow', 'Yellow Lane', [
            ['yellow_lower_h', 'Hue low', 0, 179], ['yellow_upper_h', 'Hue high', 0, 179],
            ['yellow_lower_s', 'Sat low', 0, 255], ['yellow_upper_s', 'Sat high', 0, 255],
            ['yellow_lower_v', 'Val low', 0, 255], ['yellow_upper_v', 'Val high', 0, 255],
        ]],
        ['red', 'Red Stop Line', [
            ['red_lower_h', 'Hue low 1', 0, 179], ['red_upper_h', 'Hue high 1', 0, 179],
            ['red_lower_h2', 'Hue low 2', 0, 179], ['red_upper_h2', 'Hue high 2', 0, 179],
            ['red_lower_s', 'Sat low', 0, 255], ['red_upper_s', 'Sat high', 0, 255],
            ['red_lower_v', 'Val low', 0, 255], ['red_upper_v', 'Val high', 0, 255],
        ]],
    ];
    sections.forEach(([klass, title, controls]) => {
        const section = document.createElement('div');
        section.className = 'hsv-section';
        section.innerHTML = `<div class="hsv-title ${klass}">${title}</div>`;
        hsv.appendChild(section);
        controls.forEach(([key, label, min, max]) => {
            makeSlider(section, hsvConfig, key, label, min, max, 1, config.hsv[key] ?? 0);
        });
    });
}

function applyDetectionConfig() {
    postJSON('/update_detection_config', detectionConfig)
        .then(() => showStatus('detection-status', 'Detection config applied', 'success'))
        .catch(() => showStatus('detection-status', 'Apply failed', 'error'));
}

function applyLaneConfig() {
    postJSON('/update_lane_config', laneConfig)
        .then(() => showStatus('lane-status', 'Lane config applied', 'success'))
        .catch(() => showStatus('lane-status', 'Apply failed', 'error'));
}

function applyHSVConfig() {
    postJSON('/update_hsv', hsvConfig)
        .then(() => showStatus('hsv-status', 'HSV config applied', 'success'))
        .catch(() => showStatus('hsv-status', 'Apply failed', 'error'));
}

function refreshStatus() {
    fetch('/status')
        .then(r => r.json())
        .then(data => {
            setRunningUI(!!data.running);
            document.getElementById('nav-state').textContent = data.nav_state || '--';
            document.getElementById('next-action').textContent = data.next_action || '--';

            const modelStatus = document.getElementById('model-status');
            if (data.model_loaded) {
                modelStatus.className = 'model-status ok';
                modelStatus.textContent = 'Model loaded';
            } else {
                modelStatus.className = 'model-status err';
                modelStatus.textContent = data.load_error || 'Model not loaded';
            }

            const fields = {
                Route: data.nav_route,
                'Stop reason': data.stop_reason || '',
                'Red line': data.red_line_detected ? 'yes' : 'no',
                'Left PWM': data.left_pwm,
                'Right PWM': data.right_pwm,
                Frames: data.frame_count,
                'Confidence': data.conf_threshold,
                'NMS': data.nms_threshold,
            };
            document.getElementById('statusTable').innerHTML = Object.entries(fields).map(([k, v]) =>
                `<div class="row"><span class="key">${k}</span><span class="val">${JSON.stringify(v ?? '')}</span></div>`
            ).join('');

            const dets = data.detections || [];
            document.getElementById('det-count').textContent = dets.length ? dets.length + ' found' : '';
            const list = document.getElementById('detections');
            list.innerHTML = dets.length === 0
                ? '<div class="empty-state">No detections</div>'
                : dets.map(d => `
                    <div class="det-row">
                        <span>${d.class}</span><span>${Number(d.score).toFixed(2)}</span>
                        <span class="det-meta">[${d.bbox.join(', ')}]</span>
                    </div>`).join('');
        })
        .catch(() => {
            document.getElementById('statusDot').style.background = 'var(--accent-red)';
        });
}

fetch('/config').then(r => r.json()).then(buildControls);
refreshStatus();
setInterval(refreshStatus, 500);
'''


def get_template(title='Project', subtitle='Real Duckiebot'):
    return render_template(
        title=title,
        subtitle=subtitle,
        content_html=_CONTENT,
        extra_css=_EXTRA_CSS,
        extra_js=_EXTRA_JS,
    )
