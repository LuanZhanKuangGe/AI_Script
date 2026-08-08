import json
import os
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


def scan_jav(jav_path: Path, with_content: bool = False) -> dict:
    jav_id = set()
    folder_dict = {}
    missing_images = {}
    nfo_count = defaultdict(int)
    empty_folders = []
    short_names = []
    actor_count = {}

    jav_root = os.fspath(jav_path)
    for dirpath, dirnames, filenames in os.walk(jav_path):
        rel = os.path.relpath(dirpath, jav_root)
        if rel == ".":
            top_name = jav_path.name
        else:
            parts = rel.split(os.sep)
            top_name = parts[0].split(" ")[0]
            if len(parts) == 1:
                if not dirnames and not filenames:
                    empty_folders.append(dirpath)
                if len(parts[0].split()) < 2:
                    short_names.append(dirpath)
        names = set(filenames)
        for fn in filenames:
            if fn.lower().endswith(".nfo"):
                stem = Path(fn).stem
                vid = normalize_jav_id(stem)
                jav_id.add(vid)
                serial_id = stem.split("-")[0]
                if serial_id not in folder_dict:
                    folder_dict[serial_id] = Path(dirpath).name
                nfo_count[top_name] += 1
                if f"{stem}-fanart.jpg" not in names or f"{stem}-poster.jpg" not in names:
                    missing_images[vid] = Path(dirpath) / fn
                if with_content:
                    try:
                        content = (Path(dirpath) / fn).read_text(encoding="utf-8", errors="ignore")
                        if "<tag>单体作品</tag>" in content:
                            m = re.search(r"<actor>\s*<name>([^<]+)</name>", content)
                            if m:
                                name = m.group(1).strip()
                                actor_count[name] = actor_count.get(name, 0) + 1
                    except Exception:
                        pass
    return {
        "jav_id": jav_id,
        "folder_dict": folder_dict,
        "missing_images": missing_images,
        "nfo_count": nfo_count,
        "empty_folders": empty_folders,
        "short_names": short_names,
        "actor_count": actor_count,
    }


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


def print_stats(empty_folders, short_names, missing_images=None, nfo_count=None):
    if empty_folders:
        print(f"  空文件夹 ({len(empty_folders)} 个)：")
        for f in empty_folders:
            print(f"    {f}")
    if short_names:
        print(f"  名称缺少空格 ({len(short_names)} 个)：")
        for f in short_names:
            print(f"    {f}")

    if nfo_count:
        sorted_folders = sorted(nfo_count.items(), key=lambda x: x[1], reverse=True)
        print(f"  {len(sorted_folders)} 个系列，{sum(nfo_count.values())} 个nfo")
        for i, (name, cnt) in enumerate(sorted_folders, 1):
            print(f"    {i:3d}. {name:<40} {cnt:>5d}")

    if missing_images:
        print(f"  缺少 fanart/poster ({len(missing_images)} 个)")
        for nfo in missing_images.values():
            print(f"    {nfo}")


def scan_quick(jav_path: Path) -> None:
    print("[JAV] 快速模式启动")

    if not jav_path.exists():
        print(f"[JAV] 路径不存在：{jav_path}")
        return

    print("[1/6] 单次扫描文件夹与 nfo")
    result = scan_jav(jav_path)
    jav_id, folder_dict = result["jav_id"], result["folder_dict"]
    missing_images, nfo_count = result["missing_images"], result["nfo_count"]
    empty_folders, short_names = result["empty_folders"], result["short_names"]
    print(f"[1/6] {len(empty_folders)} 个空文件夹，{len(short_names)} 个名称缺少空格，"
          f"{len(jav_id)} 个ID，{len(missing_images)} 个缺少图片，{len(folder_dict)} 个系列")

    print("[2/6] 扫描 FC2")
    jav_id |= collect_ids(OTHER_PATHS[0][0], OTHER_PATHS[0][1], "FC2", fc2_processor)
    print("[3/6] 扫描 東京熱")
    jav_id |= collect_ids(OTHER_PATHS[1][0], OTHER_PATHS[1][1], "東京熱", tokyo_hot_processor)
    print("[4/6] 扫描 JAV-VR")
    jav_id |= collect_ids(OTHER_PATHS[2][0], OTHER_PATHS[2][1], "JAV-VR", vr_processor)

    print("[5/6] 保存数据")
    save_data({"jav_id": list(jav_id), "jav_folder": folder_dict})
    print(f"[5/6] {len(jav_id)} 个ID，{len(folder_dict)} 个系列")
    print_stats(empty_folders, short_names, missing_images, nfo_count)
    print("[JAV] 快速模式完成")


def scan_full(jav_path: Path) -> None:
    print("[JAV] 完整模式启动")

    if not jav_path.exists():
        print(f"[JAV] 路径不存在：{jav_path}")
        return

    print("[1/6] 单次扫描文件夹与 nfo")
    result = scan_jav(jav_path, with_content=True)
    jav_id, folder_dict = result["jav_id"], result["folder_dict"]
    missing_images, nfo_count = result["missing_images"], result["nfo_count"]
    empty_folders, short_names = result["empty_folders"], result["short_names"]
    actor_count = result["actor_count"]
    print(f"[1/6] {len(empty_folders)} 个空文件夹，{len(short_names)} 个名称缺少空格，"
          f"{len(jav_id)} 个ID，{len(missing_images)} 个缺少图片")

    print("[2/6] 扫描 FC2")
    jav_id |= collect_ids(OTHER_PATHS[0][0], OTHER_PATHS[0][1], "FC2", fc2_processor)
    print("[3/6] 扫描 東京熱")
    jav_id |= collect_ids(OTHER_PATHS[1][0], OTHER_PATHS[1][1], "東京熱", tokyo_hot_processor)
    print("[4/6] 扫描 JAV-VR")
    jav_id |= collect_ids(OTHER_PATHS[2][0], OTHER_PATHS[2][1], "JAV-VR", vr_processor)

    print("[5/6] 保存数据库")
    database = {
        "jav_id": list(jav_id),
        "jav_folder": folder_dict,
        "actor_count": actor_count,
    }
    save_data(database)
    print(f"[5/6] {len(jav_id)} 个ID，{len(folder_dict)} 个系列，{len(actor_count)} 个演员")
    print_stats(empty_folders, short_names, missing_images, nfo_count)
    print("[JAV] 完整模式完成")


if __name__ == "__main__":
    print(f"[JAV] 模式={MODE}")
    if MODE == "quick":
        scan_quick(JAV)
    else:
        scan_full(JAV)