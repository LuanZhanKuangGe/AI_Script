import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(r"D:\Hentai-MMD-new")
DOWNLOAD_DIR = Path(r"C:\Users\zhoub\Downloads")
LIST_FILE = Path(__file__).parent / "download_list.txt"


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


def main():
    if not LIST_FILE.exists():
        print(f"下载列表不存在: {LIST_FILE}")
        return

    lines = open(LIST_FILE, encoding="utf-8").readlines()
    print(f"读取到 {len(lines)} 条记录")

    moved = 0
    skipped = 0
    not_found = 0

    for i, line in enumerate(lines, 1):
        info = parse_line(line)
        if not info or not info["artist"] or not info["name"]:
            print(f"  [{i}] 跳过无效行: {line.strip()[:80]}")
            skipped += 1
            continue

        artist = info["artist"]
        name = info["name"]
        filename = info["filename"]

        src = DOWNLOAD_DIR / filename
        if not src.exists():
            print(f"  [{i}] 文件不存在: {src}")
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

        src.rename(dst)
        print(f"  [{i}] {src.name} -> {dst.parent.name}\\{dst.name}")
        moved += 1

    print(f"\n完成: 移动 {moved}, 跳过 {skipped}, 未找到 {not_found}")


if __name__ == "__main__":
    main()