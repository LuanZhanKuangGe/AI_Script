import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue

from flask import Flask, Response, request

SCRIPTS = [
    {"id": "tikporn",   "name": "TikPorn",   "path": "script/tikporn.py",   "modes": ["quick", "full"]},
    {"id": "sharesome", "name": "ShareSome",  "path": "script/sharesome.py", "modes": ["quick", "full"]},
    {"id": "xxxfollow", "name": "XXXFollow",  "path": "script/xxxfollow.py", "modes": ["quick", "full"]},
    {"id": "waptap",    "name": "WapTap",     "path": "script/waptap.py",    "modes": ["quick", "full"]},
    {"id": "fikfap",    "name": "FikFap",     "path": "script/fikfap.py",    "modes": ["quick", "full"]},
    {"id": "xfree",     "name": "XFree",      "path": "script/xfree.py",     "modes": ["quick", "full"]},
]

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

ROOT_PATH = Path(__file__).parent.parent

app = Flask(__name__)

script_state = {}
script_queues = {}
script_threads = {}


def get_log_path(script_id):
    return LOG_DIR / f"{script_id}.log"


def run_script(script_id, mode):
    info = next((s for s in SCRIPTS if s["id"] == script_id), None)
    if not info:
        return

    script_path = ROOT_PATH / info["path"]
    q = script_queues.get(script_id)
    log_file = get_log_path(script_id)

    script_state[script_id] = "running"

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n--- {datetime.now():%H:%M:%S} START mode={mode} ---\n")
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            [sys.executable, str(script_path), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        for line in iter(proc.stdout.readline, ""):
            lf.write(line)
            lf.flush()
            if q:
                q.put(line)
        proc.wait()
        lf.write(f"--- {datetime.now():%H:%M:%S} EXIT code={proc.returncode} ---\n")

    script_state[script_id] = f"done:{proc.returncode}"
    if q:
        q.put(None)


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/scripts")
def api_scripts():
    result = []
    for s in SCRIPTS:
        script_path = ROOT_PATH / s["path"]
        result.append({
            "id": s["id"],
            "name": s["name"],
            "modes": s["modes"],
            "exists": script_path.exists(),
            "state": script_state.get(s["id"], "idle"),
        })
    return json.dumps(result)


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json()
    script_id = data.get("id")
    mode = data.get("mode", "quick")

    info = next((s for s in SCRIPTS if s["id"] == script_id), None)
    if not info:
        return json.dumps({"error": "unknown script"}), 400

    if script_state.get(script_id) == "running":
        return json.dumps({"error": "already running"}), 400

    q = Queue()
    script_queues[script_id] = q

    t = threading.Thread(target=run_script, args=(script_id, mode), daemon=True)
    script_threads[script_id] = t
    t.start()

    return json.dumps({"ok": True})


@app.route("/api/start_all", methods=["POST"])
def api_start_all():
    mode = request.get_json().get("mode", "quick")
    for s in SCRIPTS:
        script_path = ROOT_PATH / s["path"]
        if not script_path.exists():
            continue
        if script_state.get(s["id"]) == "running":
            continue
        q = Queue()
        script_queues[s["id"]] = q
        t = threading.Thread(target=run_script, args=(s["id"], mode), daemon=True)
        script_threads[s["id"]] = t
        t.start()
    return json.dumps({"ok": True})


@app.route("/api/log/<script_id>")
def api_log(script_id):
    q = script_queues.get(script_id)
    if not q:
        log_file = get_log_path(script_id)
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8", errors="replace")
            return json.dumps({"lines": content.splitlines(keepends=True)[-50:], "done": True})
        return json.dumps({"lines": [], "done": True})

    lines = []
    while True:
        try:
            msg = q.get_nowait()
            if msg is None:
                script_state[script_id] = script_state.get(script_id, "done:0")
                return json.dumps({"lines": lines, "done": True})
            lines.append(msg)
        except Exception:
            break
    return json.dumps({"lines": lines, "done": False})


@app.route("/api/stream/<script_id>")
def api_stream(script_id):
    def generate():
        q = Queue()
        script_queues[script_id] = q
        while True:
            try:
                msg = q.get(timeout=1)
                if msg is None:
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                yield f"data: {json.dumps({'line': msg})}\n\n"
            except Exception:
                yield f"data: {json.dumps({'ping': True})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/recent_log/<script_id>")
def api_recent_log(script_id):
    log_file = get_log_path(script_id)
    if not log_file.exists():
        return json.dumps({"lines": []})
    content = log_file.read_text(encoding="utf-8", errors="replace")
    all_lines = content.splitlines(keepends=True)
    recent = all_lines[-200:]
    return json.dumps({"lines": recent})


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Script Runner</title>
<style>
:root {
  --bg: #0f0f0f;
  --surface: #1a1a1a;
  --surface2: #242424;
  --border: #333;
  --text: #e0e0e0;
  --text2: #888;
  --accent: #7c3aed;
  --accent2: #5b21b6;
  --green: #22c55e;
  --yellow: #eab308;
  --red: #ef4444;
  --blue: #3b82f6;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow: hidden;
}
.app { display: flex; height: 100vh; }

/* Sidebar */
.sidebar {
  width: 260px;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid var(--border);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, var(--accent), var(--blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.mode-bar {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}
.mode-bar label { font-size: 13px; color: var(--text2); }
.mode-toggle {
  display: flex;
  background: var(--surface2);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.mode-btn {
  padding: 6px 16px;
  font-size: 13px;
  border: none;
  background: transparent;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn.active {
  background: var(--accent);
  color: #fff;
}
.mode-btn:hover:not(.active) { color: var(--text); }

.script-list { flex: 1; overflow-y: auto; padding: 8px; }
.script-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 4px;
}
.script-item:hover { background: var(--surface2); }
.script-item.active { background: var(--surface2); border: 1px solid var(--accent); }
.script-item .status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--text2);
  flex-shrink: 0;
}
.script-item .status-dot.idle { background: var(--text2); }
.script-item .status-dot.running { background: var(--yellow); animation: pulse 1.5s infinite; }
.script-item .status-dot.done\:0 { background: var(--green); }
.script-item .status-dot.done { background: var(--green); }
.script-item .status-dot.done\:1 { background: var(--red); }
.script-item .status-dot.done\:2 { background: var(--red); }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.script-item .info { flex: 1; min-width: 0; }
.script-item .name { font-size: 14px; font-weight: 600; }
.script-item .path { font-size: 11px; color: var(--text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.start-all-bar {
  padding: 16px;
  border-top: 1px solid var(--border);
}
.btn-start-all {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), var(--blue));
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-start-all:hover { opacity: 0.85; transform: translateY(-1px); }
.btn-start-all:active { transform: translateY(0); }
.btn-start-all:disabled { opacity: 0.5; cursor: default; transform: none; }

/* Main */
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.main-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface);
}
.main-header .title { font-size: 20px; font-weight: 700; }
.main-header .actions { display: flex; gap: 8px; align-items: center; }

.btn {
  padding: 8px 18px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent2); }
.btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text2); }
.btn-outline:hover { border-color: var(--text2); color: var(--text); }
.btn:disabled { opacity: 0.4; cursor: default; }

.log-area {
  flex: 1;
  margin: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.log-header {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text2);
}
.log-content {
  flex: 1;
  padding: 12px 16px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
.log-content::-webkit-scrollbar { width: 6px; }
.log-content::-webkit-scrollbar-track { background: transparent; }
.log-content::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text2);
  gap: 12px;
}
.empty-state .icon { font-size: 48px; opacity: 0.3; }
.empty-state .text { font-size: 15px; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.idle { background: var(--surface2); color: var(--text2); }
.status-badge.running { background: rgba(234,179,8,0.15); color: var(--yellow); }
.status-badge.success { background: rgba(34,197,94,0.15); color: var(--green); }
.status-badge.error { background: rgba(239,68,68,0.15); color: var(--red); }

.auto-scroll-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text2);
  cursor: pointer;
  user-select: none;
}
.auto-scroll-toggle input { accent-color: var(--accent); }
</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <div class="sidebar-header">&#9654; Script Runner</div>
    <div class="mode-bar">
      <label>Mode</label>
      <div class="mode-toggle">
        <button class="mode-btn active" data-mode="quick">Quick</button>
        <button class="mode-btn" data-mode="full">Full</button>
      </div>
    </div>
    <div class="script-list" id="scriptList"></div>
    <div class="start-all-bar">
      <button class="btn-start-all" id="btnStartAll">&#9654; Start All</button>
    </div>
  </div>
  <div class="main">
    <div class="main-header">
      <div class="title" id="mainTitle">Script Runner</div>
      <div class="actions" id="mainActions"></div>
    </div>
    <div class="log-area" id="logArea" style="display:none;">
      <div class="log-header">
        <span id="logStatus"></span>
        <div style="display:flex;gap:12px;align-items:center;">
          <label class="auto-scroll-toggle">
            <input type="checkbox" id="autoScroll" checked> Auto-scroll
          </label>
          <button class="btn btn-outline" onclick="clearLog()" style="padding:4px 12px;font-size:11px;">Clear</button>
        </div>
      </div>
      <div class="log-content" id="logContent"></div>
    </div>
    <div class="empty-state" id="emptyState">
      <div class="icon">&#9654;</div>
      <div class="text">Select a script to view logs</div>
    </div>
  </div>
</div>

<script>
const scripts = [];
let currentScript = null;
let currentMode = 'quick';
let pollTimers = {};

// Mode toggle
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMode = btn.dataset.mode;
  });
});

// Load scripts
async function loadScripts() {
  const resp = await fetch('/api/scripts');
  const data = await resp.json();
  const list = document.getElementById('scriptList');
  list.innerHTML = '';
  data.forEach(s => {
    scripts[s.id] = s;
    const div = document.createElement('div');
    div.className = 'script-item' + (currentScript === s.id ? ' active' : '');
    div.dataset.id = s.id;
    const stateClass = s.state.includes('done') ? 'done' : s.state;
    div.innerHTML = `
      <div class="status-dot ${s.state.replace(':', '\\:')}"></div>
      <div class="info">
        <div class="name">${s.name}</div>
        <div class="path">${s.path}</div>
      </div>
    `;
    div.addEventListener('click', () => selectScript(s.id));
    list.appendChild(div);
  });
}

async function selectScript(id) {
  currentScript = id;
  document.querySelectorAll('.script-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });
  const s = scripts[id];
  document.getElementById('mainTitle').textContent = s ? s.name : 'Script Runner';

  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('logArea').style.display = 'flex';

  // Update actions
  const actions = document.getElementById('mainActions');
  const state = s ? s.state : 'idle';
  let badge = '';
  if (state === 'idle') badge = '<span class="status-badge idle">Idle</span>';
  else if (state === 'running') badge = '<span class="status-badge running">&#9679; Running</span>';
  else if (state.startsWith('done:')) {
    const code = state.split(':')[1];
    badge = code === '0'
      ? '<span class="status-badge success">&#10003; Done</span>'
      : '<span class="status-badge error">&#10007; Exit ' + code + '</span>';
  }

  let startBtn = '';
  if (s && s.exists && state !== 'running') {
    startBtn = `<button class="btn btn-primary" onclick="startScript('${id}')">&#9654; Start</button>`;
  } else if (state === 'running') {
    startBtn = '<span class="status-badge running">&#9679; Running</span>';
  }
  actions.innerHTML = badge + ' ' + startBtn;

  // Load log
  const resp = await fetch('/api/recent_log/' + id);
  const data = await resp.json();
  const el = document.getElementById('logContent');
  el.textContent = data.lines.join('');
  if (document.getElementById('autoScroll').checked) {
    el.scrollTop = el.scrollHeight;
  }

  // Start polling
  startPolling(id);
}

function startPolling(id) {
  Object.values(pollTimers).forEach(t => clearTimeout(t));
  pollTimers = {};

  function poll() {
    fetch('/api/log/' + id)
      .then(r => r.json())
      .then(data => {
        const el = document.getElementById('logContent');
        if (data.lines && data.lines.length) {
          data.lines.forEach(l => {
            el.textContent += l;
          });
          if (document.getElementById('autoScroll').checked) {
            el.scrollTop = el.scrollHeight;
          }
        }
        if (data.done) {
          loadScripts();
          if (currentScript === id) selectScript(id);
          return;
        }
        pollTimers[id] = setTimeout(poll, 300);
      })
      .catch(() => {
        pollTimers[id] = setTimeout(poll, 1000);
      });
  }
  poll();
}

async function startScript(id) {
  const s = scripts[id];
  if (!s) return;
  await fetch('/api/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: id, mode: currentMode}),
  });
  if (currentScript === id) selectScript(id);
  loadScripts();
}

document.getElementById('btnStartAll').addEventListener('click', async () => {
  await fetch('/api/start_all', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode: currentMode}),
  });
  loadScripts();
  if (currentScript) selectScript(currentScript);
});

function clearLog() {
  document.getElementById('logContent').textContent = '';
}

// Init
loadScripts();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import webbrowser
    import socket

    port = 8787

    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}/")

    threading.Timer(1, open_browser).start()
    print(f"Server running at http://127.0.0.1:{port}/")
    app.run(host="127.0.0.1", port=port, debug=False)