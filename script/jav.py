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
        print(f"  已保存 -> {DATA_FILE.name} + 远程")
    except Exception:
        print(f"  已保存 -> {DATA_FILE.name} (远程失败)")


def normalize_jav_id(raw_id: str) -> str:
    vid = raw_id.split(" ")[0].upper()
    if vid.endswith("Z"):
        vid = vid[:-1]
    return vid


def collect_ids(path: Path, pattern: str, label: str, processor) -> set:
    ids = set()
    if not path.exists():
        print(f"  {label}：跳过 (路径不存在)")
        return ids
    files = list(path.rglob(pattern))
    if not files:
        print(f"  {label}：0 个文件")
        return ids
    print(f"  {label}：扫描 {len(files)} 个文件...")
    for i, f in enumerate(files, 1):
        if i % 500 == 0 or i == len(files):
            print(f"  {label}：{i}/{len(files)} ({len(ids)} 个ID)")
        ids |= processor(f)
    print(f"  {label}：完成，{len(ids)} 个ID")
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


def print_stats(jav_path: Path, empty_folders, short_names, missing_images=None):
    if empty_folders:
        print(f"  空文件夹 ({len(empty_folders)} 个)：")
        for f in empty_folders:
            print(f"    {f}")
    if short_names:
        print(f"  名称缺少空格 ({len(short_names)} 个)：")
        for f in short_names:
            print(f"    {f}")

    folder_stats = defaultdict(int)
    for folder in jav_path.iterdir():
        if folder.is_dir():
            nfo_count = len(list(folder.glob("*.nfo")))
            if nfo_count > 0:
                folder_stats[folder.name.split(" ")[0]] += nfo_count

    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1], reverse=True)
    print(f"  {len(sorted_folders)} 个系列，{sum(folder_stats.values())} 个nfo")
    for i, (name, cnt) in enumerate(sorted_folders, 1):
        print(f"    {i:3d}. {name:<40} {cnt:>5d}")

    if missing_images:
        print(f"  缺少 fanart/poster ({len(missing_images)} 个)")
        if isinstance(missing_images, list):
            for vid in missing_images:
                print(f"    {vid}")


def scan_quick(jav_path: Path) -> None:
    print("[JAV] 快速模式启动")

    if not jav_path.exists():
        print(f"[JAV] 路径不存在：{jav_path}")
        return

    print("[1/6] 检查文件夹")
    empty_folders = []
    short_names = []
    for folder in jav_path.iterdir():
        if folder.is_dir() and len(list(folder.iterdir())) == 0:
            empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))
    print(f"[1/6] {len(empty_folders)} 个空文件夹，{len(short_names)} 个名称缺少空格")

    print("[2/6] 扫描 JAV nfo (仅文件名)")
    jav_id = set()
    folder_dict = {}
    missing_images = set()
    nfo_files = list(jav_path.rglob("*.nfo"))
    print(f"  共 {len(nfo_files)} 个nfo文件")
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
            missing_images.add(vid)
    print(f"  {len(jav_id)} 个ID，{len(missing_images)} 个缺少图片，{len(folder_dict)} 个系列")

    print("[3/6] 扫描 FC2")
    jav_id |= collect_ids(OTHER_PATHS[0][0], OTHER_PATHS[0][1], "FC2", fc2_processor)
    print("[4/6] 扫描 東京熱")
    jav_id |= collect_ids(OTHER_PATHS[1][0], OTHER_PATHS[1][1], "東京熱", tokyo_hot_processor)
    print("[5/6] 扫描 JAV-VR")
    jav_id |= collect_ids(OTHER_PATHS[2][0], OTHER_PATHS[2][1], "JAV-VR", vr_processor)

    print("[6/6] 保存数据")
    save_data({"jav_id": list(jav_id), "jav_folder": folder_dict})
    print(f"  {len(jav_id)} 个ID，{len(folder_dict)} 个系列")
    print_stats(jav_path, empty_folders, short_names, missing_images)
    print("[JAV] 快速模式完成")


def scan_full(jav_path: Path) -> None:
    print("[JAV] 完整模式启动")

    if not jav_path.exists():
        print(f"[JAV] 路径不存在：{jav_path}")
        return

    print("[1/6] 检查文件夹")
    empty_folders = []
    short_names = []
    for folder in jav_path.iterdir():
        if folder.is_dir() and len(list(folder.iterdir())) == 0:
            empty_folders.append(str(folder))
        if len(folder.name.split()) < 2:
            short_names.append(str(folder))
    print(f"[1/6] {len(empty_folders)} 个空文件夹，{len(short_names)} 个名称缺少空格")

    print("[2/6] 扫描 JAV nfo (含文件内容)")
    jav_id = set()
    folder_dict = {}
    actor_count = {}
    missing_images = []

    nfo_files = list(jav_path.rglob("*.nfo"))
    print(f"  共 {len(nfo_files)} 个nfo文件")
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
    print(f"  {len(jav_id)} 个ID，{len(missing_images)} 个缺少图片")

    print("[3/6] 扫描 FC2")
    jav_id |= collect_ids(OTHER_PATHS[0][0], OTHER_PATHS[0][1], "FC2", fc2_processor)
    print("[4/6] 扫描 東京熱")
    jav_id |= collect_ids(OTHER_PATHS[1][0], OTHER_PATHS[1][1], "東京熱", tokyo_hot_processor)
    print("[5/6] 扫描 JAV-VR")
    jav_id |= collect_ids(OTHER_PATHS[2][0], OTHER_PATHS[2][1], "JAV-VR", vr_processor)

    print("[6/6] 保存数据库")
    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    save_data(database)
    print(f"  {len(jav_id)} 个ID，{len(folder_dict)} 个系列，{len(actor_count)} 个演员")
    print_stats(jav_path, empty_folders, short_names, missing_images)
    print("[JAV] 完整模式完成")


if __name__ == "__main__":
    print(f"[JAV] 模式={MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)