import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from all_path import JAV, make_data_path

MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("quick", "full") else "quick"

DATA_FILE = Path(__file__).parent / "data-jav.json"

OTHER_PATHS = [
    (make_data_path("JAV-Other/FC2"), "*.mp4", "FC2"),
    (make_data_path("JAV-Other/東京熱"), "*.nfo", "東京熱"),
    (make_data_path("JAV-VR"), "*.nfo", "JAV-VR"),
]


def normalize_jav_id(raw_id: str) -> str:
    vid = raw_id.split(" ")[0].upper()
    if vid.endswith("Z"):
        vid = vid[:-1]
    return vid


def collect_ids(path: Path, pattern: str, label: str, processor) -> set:
    ids = set()
    if not path.exists():
        print(f"  [{label}] 路径不存在: {path}")
        return ids
    files = list(path.rglob(pattern))
    print(f"  [{label}] 扫描 {len(files)} 个文件")
    for i, f in enumerate(files, 1):
        if i % 500 == 0 or i == len(files):
            print(f"  [{label}] {i}/{len(files)}")
        ids |= processor(f)
    print(f"  [{label}] 完成, {len(ids)} 个ID")
    return ids


def jav_processor(f: Path) -> set:
    vid = normalize_jav_id(f.stem)
    return {vid}


def fc2_processor(f: Path) -> set:
    vid = f.stem.split(" ")[0]
    return {vid, vid.replace("-", "-PPV-")}


def tokyo_hot_processor(f: Path) -> set:
    vid = f.stem.split(" ")[0].replace("[无码]", "")
    return {vid, vid.replace("n", "N")}


def vr_processor(f: Path) -> set:
    vid = f.stem.split(" ")[0].upper()
    result = {vid}
    if "DSVR-" in vid:
        result.add(vid.replace("DSVR-", "DSVR-0"))
        result.add(vid.replace("DSVR-", "3DSVR-"))
    return result


PROCESSORS = [jav_processor, fc2_processor, tokyo_hot_processor, vr_processor]


def scan_quick(jav_path: Path) -> None:
    print("=== quick mode: 只更新 jav_id ===")
    all_ids = set()

    all_ids |= collect_ids(jav_path, "*.nfo", "JAV", jav_processor)
    for path, pattern, label, proc in zip(
        [p for p, _, _ in OTHER_PATHS],
        [p for _, p, _ in OTHER_PATHS],
        [p for _, _, p in OTHER_PATHS],
        PROCESSORS[1:],
    ):
        all_ids |= collect_ids(path, pattern, label, proc)

    data = {"jav_id": sorted(all_ids)}
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存 {len(all_ids)} 个ID到 {DATA_FILE}")


def scan_full(jav_path: Path) -> None:
    print("=== full mode: 完整扫描 ===")

    if not jav_path.exists():
        print(f"路径不存在: {jav_path}")
        return

    print("[1/5] 检查文件夹...")
    empty_folders = []
    short_names = []
    for folder in jav_path.iterdir():
        if folder.is_dir() and len(list(folder.iterdir())) == 0:
            empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))

    print("[2/5] 扫描 JAV nfo...")
    jav_id = set()
    folder_dict = {}
    actor_count = {}
    missing_images = []

    nfo_files = list(jav_path.rglob("*.nfo"))
    print(f"  共 {len(nfo_files)} 个nfo文件")
    for i, nfo in enumerate(nfo_files, 1):
        if i % 500 == 0 or i == len(nfo_files):
            print(f"  处理 {i}/{len(nfo_files)}")
        vid = normalize_jav_id(nfo.stem)
        jav_id.add(vid)
        serial_id = nfo.stem.split("-")[0]
        if serial_id not in folder_dict:
            folder_dict[serial_id] = nfo.parent.name

        fanart = nfo.parent / f"{nfo.stem}-fanart.jpg"
        poster = nfo.parent / f"{nfo.stem}-poster.jpg"
        if not fanart.exists() or not poster.exists():
            missing_images.append(vid)

        try:
            content = nfo.read_text(encoding="utf-8", errors="ignore")
            if "<tag>单体作品</tag>" in content:
                m = re.search(r"<actor>\s*<name>([^<]+)</name>", content)
                if m:
                    name = m.group(1).strip()
                    actor_count[name] = actor_count.get(name, 0) + 1
        except Exception:
            pass

    print("[3/5] 扫描其他目录...")
    for path, pattern, label, proc in zip(
        [p for p, _, _ in OTHER_PATHS],
        [p for _, p, _ in OTHER_PATHS],
        [p for _, _, p in OTHER_PATHS],
        PROCESSORS[1:],
    ):
        jav_id |= collect_ids(path, pattern, label, proc)

    print("[4/5] 保存数据库...")
    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    DATA_FILE.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  保存 {len(jav_id)} 个ID, {len(folder_dict)} 个系列, {len(actor_count)} 个演员")

    print("[5/5] 统计...")
    if empty_folders:
        print(f"\n空文件夹: {len(empty_folders)} 个")
        for f in empty_folders:
            print(f"  {f}")
    if short_names:
        print(f"\n文件夹名缺少空格: {len(short_names)} 个")
        for f in short_names:
            print(f"  {f}")

    folder_stats = defaultdict(int)
    for folder in jav_path.iterdir():
        if folder.is_dir():
            nfo_count = len(list(folder.glob("*.nfo")))
            if nfo_count > 0:
                folder_stats[folder.name.split(" ")[0]] += nfo_count

    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1], reverse=True)
    print(f"\n总共发现 {len(sorted_folders)} 个文件夹")
    print(f"总共包含 {sum(folder_stats.values())} 个nfo文件")
    print("-" * 60)
    for i, (name, cnt) in enumerate(sorted_folders, 1):
        print(f"{i:3d}. {name:<40} {cnt:>5d} 个文件")

    if missing_images:
        print(f"\n缺少 fanart/poster 的 nfo: {len(missing_images)} 个")
        for vid in missing_images:
            print(vid)

    print("\n完成!")


if __name__ == "__main__":
    print(f"mode: {MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)