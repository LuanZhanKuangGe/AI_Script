import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

SCRIPTS = [
    'download_tdl.py',
    'fyppt.py',
    'reddclips.py',
    'reelsmunkey.py',
]


def run_script(script_name: str, args: list = None) -> bool:
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"脚本不存在: {script_name}")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    print(f"\n{'='*60}")
    print(f"运行脚本: {script_name}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    print("开始依次运行所有爬虫脚本...")

    for script in SCRIPTS:
        print(f"\n>>> 准备运行: {script}")
        if not run_script(script):
            print(f"  脚本 {script} 执行失败，停止")
            break

    print(f"\n{'='*60}")
    print("全部脚本执行完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()