import json
import sys
from pathlib import Path
from all_path import HENTAI_PICTURE_MANGA, QINGLONG_SCRIPTS

MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("quick", "full") else "full"

DATA_FILE = Path(__file__).parent / "data-manga.json"
DATA_FILE_REMOTE = QINGLONG_SCRIPTS / "data-manga.json"


def save_data(data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    DATA_FILE.write_text(content, encoding="utf-8")
    try:
        DATA_FILE_REMOTE.write_text(content, encoding="utf-8")
        print(f"  已保存 -> {DATA_FILE.name} + 远程")
    except Exception:
        print(f"  已保存 -> {DATA_FILE.name} (远程失败)")


def add_manga(database, manga):
    if "] " not in manga.stem:
        return False
    manga_artist = manga.stem.split("] ", 1)[0] + "]"
    name = manga.stem.split("] ", 1)[1]
    if manga_artist not in database["manga"]:
        database["manga"][manga_artist] = []
    database["manga"][manga_artist].append(name)
    return True


def scan_full(manga_path: Path) -> None:
    print("[Manga] 完整模式启动")

    if not manga_path.exists():
        print(f"[Manga] 路径不存在：{manga_path}")
        return

    database = {"manga": {}}
    items = [item for item in manga_path.iterdir() if item.is_dir() or item.is_file()]
    print(f"  扫描 {len(items)} 个项目")
    skipped = 0
    for i, item in enumerate(items, 1):
        if i % 200 == 0 or i == len(items):
            print(f"  {i}/{len(items)}")
        if item.is_dir():
            for file in item.iterdir():
                if not add_manga(database, file):
                    skipped += 1
        elif item.is_file():
            if not add_manga(database, item):
                skipped += 1

    total = sum(len(v) for v in database["manga"].values())
    print(f"  {len(database['manga'])} 个作者，{total} 个漫画，{skipped} 个跳过")
    save_data(database)
    print("[Manga] 完整模式完成")


def scan_quick(manga_path: Path) -> None:
    print("[Manga] 快速模式暂不支持，执行完整模式")
    scan_full(manga_path)


if __name__ == "__main__":
    print(f"[Manga] 模式={MODE}")
    if MODE == "quick":
        scan_quick(HENTAI_PICTURE_MANGA)
    else:
        scan_full(HENTAI_PICTURE_MANGA)