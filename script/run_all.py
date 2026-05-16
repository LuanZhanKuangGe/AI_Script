import subprocess
import sys
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

CREATE_NEW_CONSOLE = 0x00000010


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick") else "quick"
    root = Path(__file__).parent.parent

    print(f"[{timestamp()}] 启动模式: {mode}")
    print(f"[{timestamp()}] 正在为每个脚本打开独立窗口...\n")

    for name, rel_path in SCRIPTS:
        script_path = root / rel_path
        if not script_path.exists():
            print(f"[{timestamp()}] [!] 脚本不存在: {script_path}")
            continue

        subprocess.Popen(
            [sys.executable, str(script_path), mode],
            creationflags=CREATE_NEW_CONSOLE,
        )
        print(f"[{timestamp()}] 已启动 [{name}]")

    print(f"\n[{timestamp()}] 所有脚本已启动，请查看各个独立窗口。")
    print(f"[{timestamp()}] 本窗口可随时关闭，不影响子进程。")


if __name__ == "__main__":
    main()
