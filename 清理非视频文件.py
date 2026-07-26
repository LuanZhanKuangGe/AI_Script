import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

VIDEO_EXTENSIONS = {
    # 常见格式
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.3g2', '.ogv', '.ogm',
    # 高清/蓝光
    '.ts', '.mts', '.m2ts', '.vob', '.evo', '.m2v', '.m2p', '.m1v',
    # 专业/广播
    '.mxf', '.dv', '.dav', '.wtv', '.dvr-ms',
    # 游戏视频
    '.bik', '.smk', '.roq',
    # 流媒体
    '.f4v', '.asf', '.nsv', '.ivf',
    # 其他格式
    '.divx', '.xvid', '.rm', '.rmvb', '.h264', '.hevc',
    '.264', '.265', '.vp6', '.vp8', '.vp9', '.av1',
    '.y4m', '.yuv', '.gifv', '.mpv', '.mpe', '.mpeg4',
    '.qt', '.hdmov', '.avchd', '.svi', '.mod', '.tod',
    '.3gpp', '.amv', '.mtv', '.pva', '.wvx', '.wm',
    '.k3g', '.skm', '.vid', '.mlv', '.m1v',
}


def main():
    root = tk.Tk()
    root.withdraw()
    root.lift()
    root.focus_force()

    folder = filedialog.askdirectory(title="选择要清理的目录")
    if not folder:
        print("未选择目录")
        return

    folder_path = Path(folder)
    total_deleted = 0
    total_skipped = 0

    for f in folder_path.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() in VIDEO_EXTENSIONS:
            total_skipped += 1
        else:
            f.unlink()
            total_deleted += 1
            print(f"已删除: {f}")

    msg = f"清理完成！\n目录: {folder}\n已删除: {total_deleted} 个非视频文件\n已保留: {total_skipped} 个视频文件"
    print(msg)
    messagebox.showinfo("清理完成", msg)


if __name__ == "__main__":
    main()
