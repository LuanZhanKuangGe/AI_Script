import subprocess
from flask import Flask, request, jsonify, Response, stream_with_context

TDL_COMMAND = r"C:\Softwares\tdl_Windows_64bit\tdl.exe dl"
DEFAULT_DOWNLOAD_DIR = r"C:\Users\zhoub\Downloads\Telegram Desktop\【视频】"

app = Flask(__name__)

tasks = []


def stream_command(command):
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    for line in process.stdout:
        yield line
    process.stdout.close()
    process.wait()


def download_all(tasks_to_download, download_dir):
    if not tasks_to_download:
        yield "没有未下载的任务"
        return
    if not download_dir:
        download_dir = DEFAULT_DOWNLOAD_DIR

    for task in tasks_to_download:
        url = task["url"]
        count = task["count"]
        task["status"] = "下载中"
        if 'comment=' in url:
            url_base = url.split("comment=")[0]
            start = int(url.split("comment=")[1])
            stop = start + count
            for i in range(start, stop):
                full_url = f"{url_base}comment={i}"
                yield f"[{full_url}]\n"
                yield from stream_command(f'{TDL_COMMAND} -u "{full_url}"')
                yield "\n" + "-" * 50 + "\n"
        else:
            base_url = url.split("?")[0]
            sub_url = ("/").join(base_url.split("/")[0:-1])
            sub_index = int(base_url.split("/")[-1])
            command = f'{TDL_COMMAND} --continue -d "{download_dir}"'
            for i in range(count):
                command += f' -u "{sub_url}/{sub_index + i}"'
            yield f"[{base_url} x{count}]\n"
            yield from stream_command(command)
            yield "\n" + "-" * 50 + "\n"
        task["status"] = "已下载"


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

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="flex flex-col gap-6">
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

      <section class="bg-slate-800 rounded-xl p-5 space-y-4 shadow-lg flex-1 flex flex-col">
        <h2 class="text-lg font-semibold text-slate-200">下载任务列表</h2>
        <div class="overflow-auto rounded-lg border border-slate-700 flex-1">
          <table class="w-full text-sm">
            <thead class="bg-slate-700 text-slate-300 sticky top-0">
              <tr>
                <th class="px-4 py-2 text-left">URL</th>
                <th class="px-4 py-2 text-center w-20">数量</th>
                <th class="px-4 py-2 text-center w-24">状态</th>
                <th class="px-4 py-2 text-center w-20">操作</th>
              </tr>
            </thead>
            <tbody id="taskBody" class="divide-y divide-slate-700"></tbody>
          </table>
        </div>
        <div class="flex gap-3">
          <button onclick="downloadAll()"
            class="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 transition font-medium">开始下载</button>
          <button onclick="clearTasks()"
            class="px-5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 transition font-medium">清空列表</button>
        </div>
      </section>
    </div>

    <section class="bg-slate-800 rounded-xl p-5 space-y-3 shadow-lg flex flex-col">
      <h2 class="text-lg font-semibold text-slate-200">下载状态</h2>
      <pre id="output" class="bg-slate-900 rounded-lg p-4 flex-1 min-h-[60vh] overflow-auto text-xs font-mono text-emerald-300 whitespace-pre-wrap border border-slate-700"></pre>
    </section>
  </div>
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
  '已下载': 'bg-emerald-600 text-emerald-100'
};

function renderTasks(list) {
  const body = document.getElementById('taskBody');
  if (!list.length) {
    body.innerHTML = '<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500">暂无任务</td></tr>';
    return;
  }
  body.innerHTML = list.map((t, i) => `
    <tr class="hover:bg-slate-750">
      <td class="px-4 py-2 font-mono text-xs break-all">${escapeHtml(t.url)}</td>
      <td class="px-4 py-2 text-center">${t.count}</td>
      <td class="px-4 py-2 text-center">
        <span class="px-2 py-1 rounded text-xs ${statusColors[t.status] || statusColors['未下载']}">${t.status || '未下载'}</span>
      </td>
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
  document.getElementById('output').textContent = '';
}

let downloading = false;

async function downloadAll() {
  if (downloading) return;
  downloading = true;
  const out = document.getElementById('output');
  out.textContent = '';
  const downloadDir = document.getElementById('downloadDir').value;
  const poller = setInterval(refreshTasks, 1000);
  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({download_dir: downloadDir})
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      out.textContent += decoder.decode(value, {stream: true});
      out.scrollTop = out.scrollHeight;
    }
    if (!out.textContent.trim()) out.textContent = '(无输出)';
  } catch (e) {
    out.textContent = '请求失败: ' + e.message;
  } finally {
    clearInterval(poller);
    downloading = false;
    await refreshTasks();
  }
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
    return [{"url": t["url"], "count": t["count"], "status": t.get("status", "未下载")} for t in tasks]


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    return jsonify(serialize_tasks())


@app.route("/api/add", methods=["POST"])
def add_task():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    count = max(1, int(data.get("count") or 1))
    if url:
        tasks.append({"url": url, "count": count, "status": "未下载"})
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
    data = request.get_json(force=True)
    download_dir = (data.get("download_dir") or "").strip() or DEFAULT_DOWNLOAD_DIR
    pending = [t for t in tasks if t.get("status", "未下载") == "未下载"]
    return Response(
        stream_with_context(download_all(pending, download_dir)),
        content_type="text/plain; charset=utf-8",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True, threaded=True)
