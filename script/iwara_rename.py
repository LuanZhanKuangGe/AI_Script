import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(r"D:\Hentai-MMD-new")
DOWNLOAD_DIR = Path(r"D:\Hentai-MMD\#Download")
DOWNLOAD_LISTS_DIR = Path(r"C:\Users\zhoub\Downloads")


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    parsed = urlparse(line)
    qs = parse_qs(parsed.query)
    artist = qs.get("artist", [""])[0]
    name = qs.get("name", [""])[0]
    if name:
        name = unquote(name)
    filename = qs.get("filename", [""])[0]
    return {"url": line, "artist": artist, "name": name, "filename": filename}


def get_artist_folder(artist):
    for folder in BASE_DIR.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.startswith(f"[{artist}]"):
            return folder
    return None


def process_list(list_file: Path):
    lines = open(list_file, encoding="utf-8").readlines()
    print(f"  读取到 {len(lines)} 条记录")

    moved = 0
    skipped = 0
    not_found = 0

    for i, line in enumerate(lines, 1):
        info = parse_line(line)
        if not info or not info["artist"] or not info["name"]:
            skipped += 1
            continue

        artist = info["artist"]
        name = info["name"]
        filename = info["filename"]

        src = DOWNLOAD_DIR / filename
        if not src.exists():
            src_by_name = DOWNLOAD_DIR / name
            if src_by_name.exists():
                src = src_by_name
            else:
                not_found += 1
                continue

        folder = get_artist_folder(artist)
        if not folder:
            print(f"  [{i}] 未找到artist文件夹 [{artist}]")
            not_found += 1
            continue

        dst = folder / name
        if dst.exists():
            print(f"  [{i}] 已存在: {dst.name}")
            src.unlink()
            skipped += 1
            continue

        shutil.move(str(src), str(dst))
        print(f"  [{i}] {src.name} -> {dst.parent.name}\\{dst.name}")
        moved += 1

    print(f"  结果: 移动 {moved}, 跳过 {skipped}, 未找到 {not_found}")
    return moved


def main():
    list_files = sorted(
        DOWNLOAD_LISTS_DIR.glob("download_list_*.txt"),
        key=lambda f: f.stem,
        reverse=True,
    )

    if not list_files:
        print(f"在 {DOWNLOAD_LISTS_DIR} 下未找到 download_list_*.txt 文件")
        return

    print(f"找到 {len(list_files)} 个下载列表文件（从新到旧处理）")

    total_moved = 0
    for lf in list_files:
        print(f"\n=== {lf.name} ===")
        total_moved += process_list(lf)

    print(f"\n全部完成: 共移动 {total_moved} 个文件")


if __name__ == "__main__":
    main()