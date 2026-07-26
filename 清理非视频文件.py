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

    folder_path = Path(folder).resolve()
    total_deleted = 0
    total_moved = 0
    video_files = []

    for f in folder_path.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(f)
        else:
            f.unlink()
            total_deleted += 1
            print(f"已删除: {f}")

    for f in video_files:
        rel = f.relative_to(folder_path)
        if len(rel.parts) <= 2:
            continue
        top_sub = rel.parts[0]
        dest = folder_path / top_sub / f.name
        if dest == f:
            continue
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            counter = 1
            while True:
                new_name = f"{stem} ({counter}){suffix}"
                candidate = dest.with_name(new_name)
                if not candidate.exists():
                    dest = candidate
                    break
                counter += 1
        f.rename(dest)
        total_moved += 1
        print(f"已移动: {f} -> {dest}")

    dirs = [d for d in folder_path.rglob('*') if d.is_dir()]
    dirs.sort(key=lambda p: len(p.parts), reverse=True)
    deleted_dirs = 0
    for d in dirs:
        if not d.exists():
            continue
        if not any(d.iterdir()):
            d.rmdir()
            deleted_dirs += 1
            print(f"已删除空文件夹: {d}")

    if not any(folder_path.iterdir()):
        folder_path.rmdir()
        deleted_dirs += 1
        print(f"已删除空文件夹: {folder_path}")

    msg = (
        f"清理完成！\n"
        f"目录: {folder}\n"
        f"已删除: {total_deleted} 个非视频文件\n"
        f"已移动: {total_moved} 个视频文件\n"
        f"已删除: {deleted_dirs} 个空文件夹"
    )
    print(msg)
    messagebox.showinfo("清理完成", msg)


if __name__ == "__main__":
    main()
