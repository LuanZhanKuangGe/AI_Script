import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

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

lock = threading.Lock()


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def print_log(script_name: str, line: str):
    ts = timestamp()
    with lock:
        sys.stdout.write(f"[{ts}] [{script_name}] {line}")
        sys.stdout.flush()


def run_script(script_name: str, script_path: Path, mode: str):
    log_file = LOG_DIR / f"{script_name}.log"
    log_path = str(log_file)

    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"\n--- {timestamp()} START script={script_name} mode={mode} ---\n")

        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            [sys.executable, str(script_path), mode],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env,
        )

        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            lf.write(line)
            lf.flush()
            print_log(script_name, line)

        proc.wait()
        lf.write(f"--- {timestamp()} EXIT code={proc.returncode} ---\n")

    print_log(script_name, f"  退出代码: {proc.returncode}\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick") else "quick"
    print(f"[{timestamp()}] 启动模式: {mode}")
    print(f"[{timestamp()}] 日志目录: {LOG_DIR}")
    print(f"[{timestamp()}] 启动 {len(SCRIPTS)} 个脚本...\n")

    threads = []
    for name, rel_path in SCRIPTS:
        path = Path(__file__).parent.parent / rel_path
        if not path.exists():
            print(f"[{timestamp()}] [!] 脚本不存在: {path}")
            continue
        t = threading.Thread(target=run_script, args=(name, path, mode), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print(f"\n[{timestamp()}] 所有脚本处理完成！")


if __name__ == "__main__":
    main()
