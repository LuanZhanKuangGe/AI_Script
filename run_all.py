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
    {"id": "download_tdl", "name": "Download TDL",   "path": "download_tdl.py"},
    {"id": "fyppt",        "name": "FYPPT",           "path": "fyppt.py"},
    {"id": "reddclips",    "name": "ReddClips",       "path": "reddclips.py"},
    {"id": "reelsmunkey",  "name": "ReelsMunkey",     "path": "reelsmunkey.py"},
]

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

ROOT_PATH = Path(__file__).parent

app = Flask(__name__)

script_state = {}
script_queues = {}


def get_log_path(script_id):
    return LOG_DIR / f"{script_id}.log"


def run_script(script_id):
    info = next((s for s in SCRIPTS if s["id"] == script_id), None)
    if not info:
        return
    script_path = ROOT_PATH / info["path"]
    if not script_path.exists():
        script_state[script_id] = "error:not_found"
        return

    q = Queue()
    script_queues[script_id] = q
    script_state[script_id] = "running"

    log_file = get_log_path(script_id)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n--- {datetime.now():%H:%M:%S} START ---\n")
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
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
            q.put(line)
        proc.wait()
        lf.write(f"--- {datetime.now():%H:%M:%S} EXIT code={proc.returncode} ---\n")
        q.put(None)

    script_state[script_id] = f"done:{proc.returncode}"


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/api/scripts")
def api_scripts():
    result = []
    for s in SCRIPTS:
        script_path = ROOT_PATH / s["path"]
        state = script_state.get(s["id"], "idle")
        result.append({
            "id": s["id"],
            "name": s["name"],
            "exists": script_path.exists(),
            "state": state,
        })
    return json.dumps(result)


@app.route("/api/start_all", methods=["POST"])
def api_start_all():
    if any(script_state.get(s["id"]) == "running" for s in SCRIPTS):
        return json.dumps({"error": "already running"}), 400
    for s in SCRIPTS:
        script_path = ROOT_PATH / s["path"]
        if not script_path.exists():
            continue
        if script_state.get(s["id"]) == "running":
            continue
        t = threading.Thread(target=run_script, args=(s["id"],), daemon=True)
        t.start()
    return json.dumps({"ok": True})


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json()
    script_id = data.get("id")
    if script_state.get(script_id) == "running":
        return json.dumps({"error": "already running"}), 400
    t = threading.Thread(target=run_script, args=(script_id,), daemon=True)
    t.start()
    return json.dumps({"ok": True})


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
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
                return json.dumps({"lines": lines, "done": True})
            lines.append(msg)
        except Exception:
            break
    return json.dumps({"lines": lines, "done": False})


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
<title>Crawler Runner</title>
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
  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow: hidden;
}
.app { display: flex; height: 100vh; }

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
  background: linear-gradient(135deg, var(--green), var(--blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
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
.script-item.active { background: var(--surface2); border: 1px solid var(--green); }
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
.script-item .status-dot.error { background: var(--red); }
.script-item .status-dot.cancelled { background: var(--text2); }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.script-item .info { flex: 1; min-width: 0; }
.script-item .name { font-size: 14px; font-weight: 600; }
.script-item .path { font-size: 11px; color: var(--text2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.script-item .order-badge {
  font-size: 11px;
  color: var(--text2);
  background: var(--surface2);
  padding: 2px 8px;
  border-radius: 10px;
}

.bottom-bar {
  padding: 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.btn {
  padding: 10px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.btn-start-all {
  background: linear-gradient(135deg, var(--green), var(--blue));
  color: #fff;
}
.btn-start-all:hover { opacity: 0.85; transform: translateY(-1px); }
.btn-start-all:disabled { opacity: 0.5; cursor: default; transform: none; }
.btn-cancel {
  background: var(--surface2);
  color: var(--red);
  border: 1px solid var(--red);
}
.btn-cancel:hover { background: rgba(239,68,68,0.15); }

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

.btn-sm {
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-primary { background: var(--green); color: #fff; }
.btn-primary:hover { background: #16a34a; }
.btn-primary:disabled { opacity: 0.4; cursor: default; }

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
.auto-scroll-toggle input { accent-color: var(--green); }
</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <div class="sidebar-header">&#9654; Crawler Runner</div>
    <div class="script-list" id="scriptList"></div>
    <div class="bottom-bar">
      <button class="btn btn-start-all" id="btnStartAll" onclick="startAll()">&#9654; Run All</button>
    </div>
  </div>
  <div class="main">
    <div class="main-header">
      <div class="title" id="mainTitle">Crawler Runner</div>
      <div class="actions" id="mainActions"></div>
    </div>
    <div class="log-area" id="logArea" style="display:none;">
      <div class="log-header">
        <span id="logStatus"></span>
        <div style="display:flex;gap:12px;align-items:center;">
          <label class="auto-scroll-toggle">
            <input type="checkbox" id="autoScroll" checked> Auto-scroll
          </label>
          <button class="btn-sm" onclick="clearLog()" style="padding:4px 12px;font-size:11px;border:1px solid var(--border);background:transparent;color:var(--text2);">Clear</button>
        </div>
      </div>
      <div class="log-content" id="logContent"></div>
    </div>
    <div class="empty-state" id="emptyState">
      <div class="icon">&#9654;</div>
      <div class="text">Select a script or Run All</div>
    </div>
  </div>
</div>
<script>
const scripts = {};
let currentScript = null;
let pollTimers = {};
let isRunningAll = false;

async function loadScripts() {
  const resp = await fetch('/api/scripts');
  const data = await resp.json();
  const list = document.getElementById('scriptList');
  list.innerHTML = '';
  data.forEach((s, i) => {
    scripts[s.id] = s;
    const div = document.createElement('div');
    div.className = 'script-item' + (currentScript === s.id ? ' active' : '');
    div.dataset.id = s.id;
    const stateClass = s.state.replace(':', '\\:');
    let stateIcon = '';
    if (s.state === 'idle') stateIcon = '';
    else if (s.state === 'running') stateIcon = '';
    else if (s.state.startsWith('done:')) {
      stateIcon = s.state === 'done:0' ? ' &#10003;' : ' &#10007;';
    }
    div.innerHTML = `
      <div class="status-dot ${stateClass}"></div>
      <div class="info">
        <div class="name">${s.name}${stateIcon}</div>
        <div class="path" style="font-size:11px;color:#888;">${s.path}</div>
      </div>
      <span class="order-badge">#${i + 1}</span>
    `;
    div.addEventListener('click', () => selectScript(s.id));
    list.appendChild(div);
  });

  const anyRunning = data.some(s => s.state === 'running');
  document.getElementById('btnStartAll').disabled = anyRunning;
  document.getElementById('btnCancel').style.display = anyRunning ? 'block' : 'none';
  isRunningAll = anyRunning;
}

async function selectScript(id) {
  currentScript = id;
  document.querySelectorAll('.script-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });
  const s = scripts[id];
  document.getElementById('mainTitle').textContent = s ? s.name : 'Crawler Runner';
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('logArea').style.display = 'flex';

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
  } else if (state === 'error:not_found') {
    badge = '<span class="status-badge error">Not Found</span>';
  } else if (state === 'cancelled') {
    badge = '<span class="status-badge idle">Cancelled</span>';
  }

  let startBtn = '';
  if (s && s.exists && state !== 'running') {
    startBtn = '<button class="btn-sm btn-primary" onclick="startSingle(\'' + id + '\')">&#9654; Start</button>';
  }
  actions.innerHTML = badge + ' ' + startBtn;

  const resp = await fetch('/api/recent_log/' + id);
  const data = await resp.json();
  const el = document.getElementById('logContent');
  el.textContent = data.lines.join('');
  if (document.getElementById('autoScroll').checked) el.scrollTop = el.scrollHeight;
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
          data.lines.forEach(l => { el.textContent += l; });
          if (document.getElementById('autoScroll').checked) el.scrollTop = el.scrollHeight;
        }
        if (data.done) {
          loadScripts();
          if (currentScript === id) selectScript(id);
          return;
        }
        pollTimers[id] = setTimeout(poll, 300);
      })
      .catch(() => { pollTimers[id] = setTimeout(poll, 1000); });
  }
  poll();
}

async function startSingle(id) {
  await fetch('/api/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id}),
  });
  loadScripts();
  setTimeout(() => { if (currentScript === id) selectScript(id); }, 500);
}

async function startAll() {
  await fetch('/api/start_all', {method: 'POST'});
  loadScripts();
  // Auto-select first script
  if (SCRIPTS_DATA) {
    const firstId = SCRIPTS_DATA[0].id;
    selectScript(firstId);
  }
}

async function cancelAll() {
  await fetch('/api/cancel', {method: 'POST'});
  loadScripts();
}

var SCRIPTS_DATA = null;
async function init() {
  const resp = await fetch('/api/scripts');
  SCRIPTS_DATA = await resp.json();
  loadScripts();
}

function clearLog() { document.getElementById('logContent').textContent = ''; }

init();
setInterval(loadScripts, 2000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import webbrowser
    import socket

    port = 8788

    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}/")

    threading.Timer(1, open_browser).start()
    print(f"Crawler Runner: http://127.0.0.1:{port}/")
    app.run(host="127.0.0.1", port=port, debug=False)