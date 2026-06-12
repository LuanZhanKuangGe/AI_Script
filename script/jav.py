import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm
from all_path import JAV, make_data_path

MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("quick", "full") else "quick"

DATA_FILE = Path(__file__).parent / "data-jav.json"

OTHER_PATHS = [
    (make_data_path("JAV-Other/FC2"), "*.mp4", "update FC2"),
    (make_data_path("JAV-Other/東京熱"), "*.nfo", "update other"),
    (make_data_path("JAV-VR"), "*.nfo", "update JAV-VR"),
]


def normalize_jav_id(raw_id: str) -> str:
    vid = raw_id.split(" ")[0].upper()
    if vid.endswith("Z"):
        vid = vid[:-1]
    return vid


def collect_jav_ids(jav_path: Path) -> set:
    ids = set()
    if not jav_path.exists():
        print(f"路径不存在: {jav_path}")
        return ids
    for nfo in tqdm(list(jav_path.rglob("*.nfo")), desc="update JAV"):
        vid = normalize_jav_id(nfo.stem)
        ids.add(vid)
    return ids


def collect_fc2_ids(fc2_path: Path) -> set:
    ids = set()
    if not fc2_path.exists():
        return ids
    for mp4 in tqdm(list(fc2_path.rglob("*.mp4")), desc="update FC2"):
        vid = mp4.stem.split(" ")[0]
        ids.add(vid)
        ids.add(vid.replace("-", "-PPV-"))
    return ids


def collect_tokyo_hot_ids(path: Path) -> set:
    ids = set()
    if not path.exists():
        return ids
    for nfo in tqdm(list(path.rglob("*.nfo")), desc="update other"):
        vid = nfo.stem.split(" ")[0].replace("[无码]", "")
        ids.add(vid)
        ids.add(vid.replace("n", "N"))
    return ids


def collect_vr_ids(path: Path) -> set:
    ids = set()
    if not path.exists():
        return ids
    for nfo in tqdm(list(path.rglob("*.nfo")), desc="update JAV-VR"):
        vid = nfo.stem.split(" ")[0].upper()
        ids.add(vid)
        ids.add(vid.replace("DSVR-", "DSVR-0"))
        ids.add(vid.replace("DSVR-", "3DSVR-"))
    return ids


def scan_quick(jav_path: Path) -> None:
    jav_id = collect_jav_ids(jav_path)
    fc2, tokyo, vr = [p for p, _, _ in OTHER_PATHS], OTHER_PATHS[0][0], OTHER_PATHS[1][0]
    jav_id |= collect_fc2_ids(OTHER_PATHS[0][0])
    jav_id |= collect_tokyo_hot_ids(OTHER_PATHS[1][0])
    jav_id |= collect_vr_ids(OTHER_PATHS[2][0])

    data = {"jav_id": sorted(jav_id)}
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"quick mode: saved {len(jav_id)} IDs to {DATA_FILE}")


def scan_full(jav_path: Path) -> None:
    jav_id = set()
    folder_dict = {}
    actor_count = {}
    missing_images = []
    empty_folders = []
    short_names = []

    if not jav_path.exists():
        print(f"路径不存在: {jav_path}")
        return

    for folder in jav_path.iterdir():
        if folder.is_dir():
            files = list(folder.iterdir())
            if len(files) == 0:
                empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))

    for nfo in tqdm(list(jav_path.rglob("*.nfo")), desc="update JAV"):
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
                    actor_count[m.group(1).strip()] = actor_count.get(m.group(1).strip(), 0) + 1
        except Exception:
            pass

    jav_id |= collect_fc2_ids(OTHER_PATHS[0][0])
    jav_id |= collect_tokyo_hot_ids(OTHER_PATHS[1][0])
    jav_id |= collect_vr_ids(OTHER_PATHS[2][0])

    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    DATA_FILE.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")

    if empty_folders:
        print("\n空文件夹:")
        for f in empty_folders:
            print(f"  {f}")
    if short_names:
        print("\n文件夹名缺少空格:")
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


if __name__ == "__main__":
    print(f"mode: {MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)