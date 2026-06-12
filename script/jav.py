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
        print(f"  {label}: skip ({path} not found)")
        return ids
    files = list(path.rglob(pattern))
    print(f"  {label}: {len(files)} files")
    for i, f in enumerate(files, 1):
        if i % 1000 == 0 or i == len(files):
            print(f"  {label}: {i}/{len(files)}")
        ids |= processor(f)
    print(f"  {label}: {len(ids)} IDs collected")
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
    print(f"[JAV] quick mode start")
    all_ids = collect_ids(jav_path, "*.nfo", "JAV", jav_processor)
    for path, pattern, label, proc in zip(
        [p for p, _, _ in OTHER_PATHS],
        [p for _, p, _ in OTHER_PATHS],
        [p for _, _, p in OTHER_PATHS],
        PROCESSORS[1:],
    ):
        all_ids |= collect_ids(path, pattern, label, proc)

    data = {"jav_id": sorted(all_ids)}
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[JAV] quick done: {len(all_ids)} IDs -> {DATA_FILE.name}")


def scan_full(jav_path: Path) -> None:
    print(f"[JAV] full mode start")

    if not jav_path.exists():
        print(f"[JAV] path not found: {jav_path}")
        return

    print("[1/5] scanning folders")
    empty_folders = []
    short_names = []
    for folder in jav_path.iterdir():
        if folder.is_dir() and len(list(folder.iterdir())) == 0:
            empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))
    print(f"[1/5] {len(empty_folders)} empty, {len(short_names)} short-named folders")

    print("[2/5] scanning JAV nfo")
    jav_id = set()
    folder_dict = {}
    actor_count = {}
    missing_images = []

    nfo_files = list(jav_path.rglob("*.nfo"))
    print(f"  {len(nfo_files)} nfo files found")
    for i, nfo in enumerate(nfo_files, 1):
        if i % 1000 == 0 or i == len(nfo_files):
            print(f"  {i}/{len(nfo_files)}")
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
    print(f"  {len(jav_id)} IDs, {len(missing_images)} missing images")

    print("[3/5] scanning other dirs")
    for path, pattern, label, proc in zip(
        [p for p, _, _ in OTHER_PATHS],
        [p for _, p, _ in OTHER_PATHS],
        [p for _, _, p in OTHER_PATHS],
        PROCESSORS[1:],
    ):
        jav_id |= collect_ids(path, pattern, label, proc)

    print("[4/5] saving database")
    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    DATA_FILE.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {len(jav_id)} IDs, {len(folder_dict)} series, {len(actor_count)} actors -> {DATA_FILE.name}")

    print("[5/5] statistics")
    if empty_folders:
        print(f"  empty folders ({len(empty_folders)}):")
        for f in empty_folders:
            print(f"    {f}")
    if short_names:
        print(f"  short-named ({len(short_names)}):")
        for f in short_names:
            print(f"    {f}")

    folder_stats = defaultdict(int)
    for folder in jav_path.iterdir():
        if folder.is_dir():
            nfo_count = len(list(folder.glob("*.nfo")))
            if nfo_count > 0:
                folder_stats[folder.name.split(" ")[0]] += nfo_count

    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1], reverse=True)
    print(f"  {len(sorted_folders)} series, {sum(folder_stats.values())} nfo total")
    for i, (name, cnt) in enumerate(sorted_folders[:20], 1):
        print(f"    {i:2d}. {name:<40} {cnt:>5d}")
    if len(sorted_folders) > 20:
        print(f"    ... and {len(sorted_folders) - 20} more")

    if missing_images:
        print(f"  missing fanart/poster ({len(missing_images)}):")
        for vid in missing_images:
            print(f"    {vid}")

    print(f"[JAV] full done")


if __name__ == "__main__":
    print(f"[JAV] mode={MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)