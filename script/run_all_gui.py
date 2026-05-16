import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import sys
import threading
import os
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

SCRIPTS = [
    ("tikporn",   "script/tikporn.py"),
    ("sharesome", "script/sharesome.py"),
    ("xxxfollow", "script/xxxfollow.py"),
    ("waptap",    "script/waptap.py"),
    ("fikfap",    "script/fikfap.py"),
    ("xfree",     "script/xfree.py"),
]

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class ScriptRunner:
    def __init__(self, script_name: str, script_path: Path, mode: str, log_queue: Queue):
        self.name = script_name
        self.path = script_path
        self.mode = mode
        self.queue = log_queue
        self.log_file = LOG_DIR / f"{script_name}.log"
        self.proc: subprocess.Popen = None

    def run(self):
        with open(self.log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- {self._ts()} START ---\n")
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            self.proc = subprocess.Popen(
                [sys.executable, str(self.path), self.mode],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                env=env,
            )
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace")
                lf.write(line)
                lf.flush()
                self.queue.put(line)
            self.proc.wait()
            lf.write(f"--- {self._ts()} EXIT code={self.proc.returncode} ---\n")
        self.queue.put(f"\n--- 退出代码: {self.proc.returncode} ---\n")

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%H:%M:%S")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("脚本并行调度器")
        self.root.geometry("900x600")

        mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick") else "quick"
        root_path = Path(__file__).parent.parent

        # 顶部信息栏
        top_frame = ttk.Frame(self.root, padding=6)
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text=f"模式: {mode}").pack(side=tk.LEFT, padx=4)
        self.status_label = ttk.Label(top_frame, text="就绪")
        self.status_label.pack(side=tk.RIGHT, padx=4)
        start_btn = ttk.Button(top_frame, text="启动全部", command=lambda: self.start_all(root_path, mode))
        start_btn.pack(side=tk.RIGHT, padx=4)

        # 笔记本（标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.text_widgets = {}  # name -> (text, queue, thread, runner)
        self.queues = {}
        self.running = False

        for name, rel_path in SCRIPTS:
            script_path = root_path / rel_path
            exists = script_path.exists()

            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=name)

            if not exists:
                ttk.Label(frame, text=f"脚本不存在: {script_path}", foreground="red").pack(expand=True)
                continue

            text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 10))
            text.pack(fill=tk.BOTH, expand=True)

            q = Queue()
            runner = ScriptRunner(name, script_path, mode, q)
            self.text_widgets[name] = (text, q, None, runner)
            self.queues[name] = q

    def start_all(self, root_path: Path, mode: str):
        if self.running:
            return
        self.running = True
        self.status_label.config(text="运行中...")

        threads = []
        for name, (text, q, _, runner) in self.text_widgets.items():
            text.config(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            text.config(state=tk.DISABLED)

            t = threading.Thread(target=runner.run, daemon=True)
            t.start()
            threads.append(t)
            self.text_widgets[name] = (text, q, t, runner)

        # 启动轮询
        self.root.after(100, self.poll_queues)

    def poll_queues(self):
        any_alive = False
        for name, (text, q, thread, runner) in self.text_widgets.items():
            # 排出当前队列的所有消息
            while True:
                try:
                    line = q.get_nowait()
                except Empty:
                    break
                text.config(state=tk.NORMAL)
                text.insert(tk.END, line)
                text.see(tk.END)
                text.config(state=tk.DISABLED)

            if thread and thread.is_alive():
                any_alive = True

        if any_alive:
            self.root.after(100, self.poll_queues)
        else:
            self.status_label.config(text="全部完成 ✓")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = App()
    app.run()
