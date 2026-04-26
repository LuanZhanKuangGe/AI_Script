import sys
import subprocess
import re
from pathlib import Path


def get_bitrate(video_path: Path) -> int:
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
           '-show_entries', 'stream=bit_rate', '-of', 'default=noprint_wrappers=1:nokey=1',
           str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode == 0 and result.stdout.strip():
        try:
            return int(result.stdout.strip())
        except ValueError:
            pass
    return 0


def format_bitrate(bitrate: int) -> str:
    if bitrate >= 1_000_000:
        return f"{bitrate // 1_000_000}M"
    elif bitrate >= 1_000:
        return f"{bitrate // 1_000}K"
    return "10M"


def rotate_video(video_path: Path, output_dir: Path):
    original_bitrate = get_bitrate(video_path)
    bitrate_mbps = original_bitrate / 1_000_000 if original_bitrate > 0 else 10
    bitrate_str = f"{int(round(bitrate_mbps))}M"
    maxrate = f"{int(round(bitrate_mbps * 1.2))}M"
    bufsize = f"{int(round(bitrate_mbps * 2))}M"

    output_path = output_dir / f"rotated_{video_path.name}"

    cmd = [
        'ffmpeg', '-hwaccel', 'cuda', '-i', str(video_path),
        '-vf', 'transpose=1',
        '-c:v', 'av1_nvenc', '-preset', 'p6',
        '-b:v', bitrate_str, '-maxrate', maxrate, '-bufsize', bufsize,
        '-c:a', 'copy',
        str(output_path)
    ]

    print(f"  处理: {video_path.name}")
    print(f"    原始位率: {format_bitrate(original_bitrate)}, 使用: {bitrate_str}")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

    if result.returncode != 0:
        print(f"    失败: {result.stderr[:200] if result.stderr else '未知错误'}")
        return False

    print(f"    完成: {output_path.name}")
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python rotate_videos.py <文件夹路径>")
        return

    folder = Path(sys.argv[1])
    if not folder.exists() or not folder.is_dir():
        print(f"文件夹不存在: {folder}")
        return

    mp4_files = list(folder.rglob('*.mp4'))
    if not mp4_files:
        print(f"没有找到mp4文件: {folder}")
        return

    print(f"找到 {len(mp4_files)} 个mp4文件")

    success = 0
    failed = 0

    total = len(mp4_files)
    for i, video in enumerate(mp4_files, 1):
        print(f"[{i}/{total}]")
        if rotate_video(video, video.parent):
            success += 1
        else:
            failed += 1

    print(f"\n完成: 成功 {success}, 失败 {failed}")


if __name__ == "__main__":
    main()