import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from all_path import JAV, make_data_path, QINGLONG_SCRIPTS

MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("quick", "full") else "quick"

DATA_FILE = Path(__file__).parent / "data-jav.json"
DATA_FILE_REMOTE = QINGLONG_SCRIPTS / "data-jav.json"

OTHER_PATHS = [
    (make_data_path("JAV-Other/FC2"), "*.mp4", "FC2"),
    (make_data_path("JAV-Other/東京熱"), "*.nfo", "東京熱"),
    (make_data_path("JAV-VR"), "*.nfo", "JAV-VR"),
]


def save_data(data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    DATA_FILE.write_text(content, encoding="utf-8")
    try:
        DATA_FILE_REMOTE.write_text(content, encoding="utf-8")
        print(f"  saved -> {DATA_FILE.name} + remote")
    except Exception:
        print(f"  saved -> {DATA_FILE.name} (remote failed)")


def normalize_jav_id(raw_id: str) -> str:
    vid = raw_id.split(" ")[0].upper()
    if vid.endswith("Z"):
        vid = vid[:-1]
    return vid


def collect_ids(path: Path, pattern: str, label: str, processor) -> set:
    ids = set()
    if not path.exists():
        print(f"  {label}: skip (path not found)")
        return ids
    files = list(path.rglob(pattern))
    if not files:
        print(f"  {label}: 0 files")
        return ids
    print(f"  {label}: scanning {len(files)} files...")
    for i, f in enumerate(files, 1):
        if i % 500 == 0 or i == len(files):
            print(f"  {label}: {i}/{len(files)} ({len(ids)} IDs)")
        ids |= processor(f)
    print(f"  {label}: done, {len(ids)} IDs")
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
    print("[JAV] quick mode start")
    print("[1/4] scanning JAV")
    all_ids = collect_ids(jav_path, "*.nfo", "JAV", jav_processor)
    for idx, (path, pattern, label, proc) in enumerate(zip(
        [p for p, _, _ in OTHER_PATHS],
        [p for _, p, _ in OTHER_PATHS],
        [p for _, _, p in OTHER_PATHS],
        PROCESSORS[1:],
    ), 2):
        print(f"[{idx}/4] scanning {label}")
        all_ids |= collect_ids(path, pattern, label, proc)
    print(f"[4/4] saving {len(all_ids)} IDs")
    save_data({"jav_id": sorted(all_ids)})
    print(f"[JAV] quick done")


def scan_full(jav_path: Path) -> None:
    print("[JAV] full mode start")

    if not jav_path.exists():
        print(f"[JAV] path not found: {jav_path}")
        return

    print("[1/6] scanning folders")
    empty_folders = []
    short_names = []
    for folder in jav_path.iterdir():
        if folder.is_dir() and len(list(folder.iterdir())) == 0:
            empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))
    print(f"[1/6] {len(empty_folders)} empty, {len(short_names)} short-named folders")

    print("[2/6] scanning JAV nfo")
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

    print("[3/6] scanning FC2")
    jav_id |= collect_ids(OTHER_PATHS[0][0], OTHER_PATHS[0][1], "FC2", fc2_processor)
    print("[4/6] scanning 東京熱")
    jav_id |= collect_ids(OTHER_PATHS[1][0], OTHER_PATHS[1][1], "東京熱", tokyo_hot_processor)
    print("[5/6] scanning JAV-VR")
    jav_id |= collect_ids(OTHER_PATHS[2][0], OTHER_PATHS[2][1], "JAV-VR", vr_processor)

    print("[6/6] saving database")
    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    save_data(database)
    print(f"  {len(jav_id)} IDs, {len(folder_dict)} series, {len(actor_count)} actors")

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

    print("[JAV] full done")


if __name__ == "__main__":
    print(f"[JAV] mode={MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)