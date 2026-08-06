import re
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify

TDL_COMMAND = r"C:\Softwares\tdl_Windows_64bit\tdl.exe dl"
DEFAULT_DOWNLOAD_DIR = r"C:\Users\zhoub\Downloads\Telegram Desktop\【视频】"
LOG_DIR = Path(__file__).resolve().parent / "logs"

app = Flask(__name__)

tasks = []

MONITOR_INTERVAL = 10
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)%\s*\[")

_lock = threading.Lock()
active_task = None
active_log = None
_worker = None


def expand_url(url, count):
    urls = []
    if 'comment=' in url:
        url_base = url.split("comment=")[0]
        start = int(url.split("comment=")[1])
        for i in range(start, start + count):
            urls.append(f"{url_base}comment={i}")
    else:
        base_url = url.split("?")[0]
        sub_url = ("/").join(base_url.split("/")[0:-1])
        sub_index = int(base_url.split("/")[-1])
        for i in range(count):
            urls.append(f"{sub_url}/{sub_index + i}")
    return urls


def read_progress(log_path):
    if log_path is None or not Path(log_path).exists():
        return 0
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(max(0, f.seek(0, 2) - 65536))
            text = f.read()
    except OSError:
        return 0
    if "done!" in text:
        return 100
    matches = list(PERCENT_RE.finditer(text))
    if not matches:
        return 0
    return float(matches[-1].group(1))


def monitor_loop():
    while True:
        time.sleep(MONITOR_INTERVAL)
        with _lock:
            task, log_path = active_task, active_log
        if task is not None and task.get("status") == "下载中":
            task["progress"] = read_progress(log_path)


def download_task(task, download_dir, log_path):
    global active_task, active_log
    with _lock:
        active_task = task
        active_log = log_path
    task["status"] = "下载中"
    task["progress"] = 0
    url = task["url"]
    if 'comment=' in url:
        cmd = f'{TDL_COMMAND} -u "{url}"'
    else:
        cmd = f'{TDL_COMMAND} --continue -d "{download_dir}" -u "{url}"'
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT)
    except Exception:
        pass
    progress = read_progress(log_path)
    if progress == 100:
        task["status"] = "已下载"
    else:
        task["status"] = "失败"
    task["progress"] = progress
    with _lock:
        active_task = None
        active_log = None


def download_all_worker(tasks_to_download, download_dir):
    for task in tasks_to_download:
        log_path = LOG_DIR / f"tdl_{id(task)}.log"
        download_task(task, download_dir, log_path)


HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TDL Downloader</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
<div class="max-w-7xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-3xl font-bold text-sky-400">TDL Downloader</h1>
    <p class="text-slate-400 text-sm">添加多个 Telegram URL 批量下载</p>
  </header>

  <section class="bg-slate-800 rounded-xl p-5 space-y-4 shadow-lg">
    <h2 class="text-lg font-semibold text-slate-200">添加任务</h2>
    <div class="flex flex-col sm:flex-row gap-3">
      <input id="url" type="text" placeholder="输入 Telegram 链接"
        class="flex-1 px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400 placeholder-slate-500">
      <input id="count" type="number" value="1" min="1" step="1"
        class="w-24 px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400 text-center">
      <button onclick="addTask()"
        class="px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 transition font-medium whitespace-nowrap">添加任务</button>
    </div>

    <div class="flex flex-col sm:flex-row gap-3 items-center">
      <label class="text-slate-400 text-sm whitespace-nowrap">下载目录</label>
      <input id="downloadDir" type="text"
        class="flex-1 px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400 font-mono text-sm">
    </div>
  </section>

  <section class="bg-slate-800 rounded-xl p-5 space-y-4 shadow-lg">
    <h2 class="text-lg font-semibold text-slate-200">下载任务列表</h2>
    <div class="overflow-auto rounded-lg border border-slate-700">
      <table class="w-full text-sm">
        <thead class="bg-slate-700 text-slate-300 sticky top-0">
          <tr>
            <th class="px-4 py-2 text-left">URL</th>
            <th class="px-4 py-2 text-center w-24">状态</th>
            <th class="px-4 py-2 text-center w-56">进度</th>
            <th class="px-4 py-2 text-center w-20">操作</th>
          </tr>
        </thead>
        <tbody id="taskBody" class="divide-y divide-slate-700"></tbody>
      </table>
    </div>
    <div class="flex gap-3">
      <button id="downloadBtn" onclick="downloadAll()"
        class="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 transition font-medium">开始下载</button>
      <button onclick="clearTasks()"
        class="px-5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 transition font-medium">清空列表</button>
    </div>
  </section>
</div>

<script>
const DEFAULT_DIR = __DEFAULT_DIR__;

document.getElementById('downloadDir').value = DEFAULT_DIR;

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const statusColors = {
  '未下载': 'bg-slate-600 text-slate-200',
  '下载中': 'bg-amber-600 text-amber-100',
  '已下载': 'bg-emerald-600 text-emerald-100',
  '失败': 'bg-rose-600 text-rose-100'
};

function progressCell(p) {
  p = Math.max(0, Math.min(100, Number(p) || 0));
  return `
    <div class="flex items-center gap-2">
      <div class="flex-1 bg-slate-700 rounded-full h-2 overflow-hidden">
        <div class="h-full bg-sky-500 transition-all duration-500" style="width:${p}%"></div>
      </div>
      <span class="text-xs text-slate-400 w-10 text-right">${p.toFixed(0)}%</span>
    </div>`;
}

function renderTasks(list) {
  const body = document.getElementById('taskBody');
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500">暂无任务</td></tr>';
    return;
  }
  body.innerHTML = list.map((t, i) => `
    <tr class="hover:bg-slate-750">
      <td class="px-4 py-2 font-mono text-xs break-all">${escapeHtml(t.url)}</td>
      <td class="px-4 py-2 text-center">
        <span class="px-2 py-1 rounded text-xs ${statusColors[t.status] || statusColors['未下载']}">${t.status || '未下载'}</span>
      </td>
      <td class="px-4 py-2">${progressCell(t.progress)}</td>
      <td class="px-4 py-2 text-center">
        <button onclick="removeTask(${i})" class="text-rose-400 hover:text-rose-300 text-xs">删除</button>
      </td>
    </tr>`).join('');
}

async function refreshTasks() {
  const res = await fetch('/api/tasks');
  renderTasks(await res.json());
}

async function addTask() {
  const url = document.getElementById('url').value.trim();
  const count = Math.max(1, parseInt(document.getElementById('count').value) || 1);
  if (!url) return;
  const res = await fetch('/api/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url, count})
  });
  renderTasks(await res.json());
  document.getElementById('url').value = '';
}

async function removeTask(index) {
  const res = await fetch('/api/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({index})
  });
  renderTasks(await res.json());
}

async function clearTasks() {
  const res = await fetch('/api/clear', {method: 'POST'});
  renderTasks(await res.json());
}

let downloading = false;

async function downloadAll() {
  if (downloading) return;
  const btn = document.getElementById('downloadBtn');
  const downloadDir = document.getElementById('downloadDir').value;
  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({download_dir: downloadDir})
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
  } catch (e) {
    alert('请求失败: ' + e.message);
    return;
  }
  downloading = true;
  btn.disabled = true;
  btn.classList.add('opacity-50', 'cursor-not-allowed');
  const poller = setInterval(async () => {
    const list = await (await fetch('/api/tasks')).json();
    renderTasks(list);
    if (!list.some(t => t.status === '下载中')) {
      clearInterval(poller);
      downloading = false;
      btn.disabled = false;
      btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }, 10000);
}

refreshTasks();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return HTML_PAGE.replace("__DEFAULT_DIR__", repr(DEFAULT_DOWNLOAD_DIR))


def serialize_tasks():
    return [{"url": t["url"], "count": t["count"], "status": t.get("status", "未下载"), "progress": t.get("progress", 0)} for t in tasks]


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    return jsonify(serialize_tasks())


@app.route("/api/add", methods=["POST"])
def add_task():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    count = max(1, int(data.get("count") or 1))
    if url:
        for expanded in expand_url(url, count):
            tasks.append({"url": expanded, "count": 1, "status": "未下载", "progress": 0})
    return jsonify(serialize_tasks())


@app.route("/api/remove", methods=["POST"])
def remove_task():
    data = request.get_json(force=True)
    index = int(data.get("index") or 0)
    if 0 <= index < len(tasks):
        tasks.pop(index)
    return jsonify(serialize_tasks())


@app.route("/api/clear", methods=["POST"])
def clear_tasks():
    tasks.clear()
    return jsonify([])


@app.route("/api/download", methods=["POST"])
def download():
    global _worker
    if _worker and _worker.is_alive():
        return jsonify({"error": "已有下载正在进行中"}), 400
    data = request.get_json(force=True)
    download_dir = (data.get("download_dir") or "").strip() or DEFAULT_DOWNLOAD_DIR
    pending = [t for t in tasks if t.get("status", "未下载") in ("未下载", "失败")]
    if not pending:
        return jsonify({"error": "没有未下载的任务"}), 400
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _worker = threading.Thread(target=download_all_worker, args=(pending, download_dir), daemon=True)
    _worker.start()
    return jsonify({"message": "开始下载"})


if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=7860, debug=True, threaded=True)
