import json
import sys
from tqdm import tqdm
from pathlib import Path
from collections import defaultdict


def get_base_path():
    if sys.platform == "win32":
        return Path(r"D:\JAV")
    return Path(r"/data/JAV")


def get_other_path(name: str) -> Path:
    base = get_base_path()
    if sys.platform == "win32":
        return base.parent / name
    return Path(f"/data/{name}")


def scan_videos(target: Path, pattern: str, desc: str, processor=None) -> list:
    if not target.exists():
        print(f"路径不存在: {target}")
        return []
    videos = list(target.rglob(pattern))
    results = []
    for video in tqdm(videos, desc=desc):
        if processor:
            result = processor(video)
            if result:
                results.extend(result)
    return results


def process_nfo(video: Path, formats: list = None) -> list:
    video_id = video.stem.split(" ")[0].upper()
    if video_id.endswith('z'):
        video_id = video_id[:-1]
    return [video_id]


def process_mp4(video: Path) -> list:
    video_id = video.stem.split(" ")[0]
    result = [video_id, video_id.replace('-', '-PPV-')]
    return result


def process_tokyo_hot(video: Path) -> list:
    video_id = video.stem.split(" ")[0].replace('[无码]', '')
    return [video_id, video_id.replace('n', 'N')]


def process_vr(video: Path) -> list:
    video_id = video.stem.split(" ")[0].upper()
    video_id2 = video_id.replace('DSVR-', 'DSVR-0')
    video_id3 = video_id.replace('DSVR-', '3DSVR-')
    return [video_id, video_id2, video_id3]


def collect_folder_stats(target: Path) -> dict:
    folder_stats = defaultdict(int)
    for folder in target.iterdir():
        if folder.is_dir():
            nfo_count = len(list(folder.glob("*.nfo")))
            if nfo_count > 0:
                folder_name = folder.name.split(" ")[0]
                folder_stats[folder_name] += nfo_count
    return folder_stats


def print_folder_stats(folder_stats: dict):
    sorted_folders = sorted(folder_stats.items(), key=lambda x: x[1], reverse=True)
    print(f"\n总共发现 {len(sorted_folders)} 个文件夹")
    print(f"总共包含 {sum(folder_stats.values())} 个nfo文件")
    print("\n文件夹排序结果（按nfo文件数量从高到低）：")
    print("-" * 60)
    for i, (folder_name, nfo_count) in enumerate(sorted_folders, 1):
        print(f"{i:3d}. {folder_name:<40} {nfo_count:>5d} 个文件")


def main():
    database = {'jav_id': set(), 'jav_folder': {}, 'actor_count': {}}
    folder_dict = database['jav_folder']
    actor_count = database['actor_count']
    missing_images = []

    jav_path = get_base_path()
    if not jav_path.exists():
        print(f"路径不存在: {jav_path}")
        return

    for folder in jav_path.iterdir():
        if folder.is_dir():
            files = list(folder.iterdir())
            if len(files) == 0:
                print("empty folder", folder)
        if len(folder.name.split()) < 2:
            print(folder)

    for video in tqdm(list(jav_path.rglob("*.nfo")), desc="update JAV"):
        video_id = video.stem.split(" ")[0].upper()
        if video_id[-1] == 'z':
            video_id = video_id[0:-1]
        database['jav_id'].add(video_id)
        serial_id = video.stem.split("-")[0]
        if serial_id not in folder_dict:
            folder_dict[serial_id] = video.parent.name
        
        nfo_name = video.stem
        fanart_file = video.parent / f"{nfo_name}-fanart.jpg"
        poster_file = video.parent / f"{nfo_name}-poster.jpg"
        
        if not fanart_file.exists() or not poster_file.exists():
            missing_images.append(video_id)
        
        try:
            content = video.read_text(encoding='utf-8', errors='ignore')
            if '<tag>单体作品</tag>' in content:
                import re
                actor_match = re.search(r'<actor>\s*<name>([^<]+)</name>', content)
                if actor_match:
                    actor_name = actor_match.group(1).strip()
                    actor_count[actor_name] = actor_count.get(actor_name, 0) + 1
        except Exception:
            pass

    fc2_path = get_other_path("JAV-Other/FC2")
    if fc2_path.exists():
        for video in tqdm(list(fc2_path.rglob("*.mp4")), desc="update AVFC2"):
            video_id = video.stem.split(" ")[0]
            database['jav_id'].add(video_id)
            database['jav_id'].add(video_id.replace('-', '-PPV-'))

    tokyo_hot_path = get_other_path("JAV-Other/東京熱")
    if tokyo_hot_path.exists():
        for video in tqdm(list(tokyo_hot_path.rglob("*.nfo")), desc="update other"):
            video_id = video.stem.split(" ")[0].replace('[无码]', '')
            database['jav_id'].add(video_id)
            database['jav_id'].add(video_id.replace('n', 'N'))

    vr_path = get_other_path("JAV-VR")
    if vr_path.exists():
        for video in tqdm(list(vr_path.rglob("*.nfo")), desc="update JAV-VR"):
            video_id = video.stem.split(" ")[0].upper()
            database['jav_id'].add(video_id)
            database['jav_id'].add(video_id.replace('DSVR-', 'DSVR-0'))
            database['jav_id'].add(video_id.replace('DSVR-', '3DSVR-'))

    database['jav_id'] = list(database['jav_id'])

    with open("data-jav.json", "w", encoding="utf8") as fp:
        json.dump(database, fp, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("文件夹统计和排序")
    print("=" * 60)

    folder_stats = collect_folder_stats(jav_path)
    print_folder_stats(folder_stats)
    
    if missing_images:
        print("\n" + "=" * 60)
        print("缺少fanart.jpg或poster.jpg的nfo文件")
        print("=" * 60)
        for vid in missing_images:
            print(vid)


if __name__ == "__main__":
    main()