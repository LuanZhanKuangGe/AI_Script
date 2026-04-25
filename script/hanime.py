from pathlib import Path
import platform
import json

try:
    from tqdm import tqdm
except Exception:
    tqdm = lambda x, **kwargs: x


def fetch_video_cover(video_file: str):
    pass


def scan_videos(base_path: Path, check_cover: bool = True):
    videos = list(base_path.rglob("*.mp4"))
    print(f"找到 {len(videos)} 个视频文件")

    checked = 0
    missing_covers = []

    for video in tqdm(videos, desc="扫描视频"):
        if check_cover:
            possible_covers = [
                video.with_suffix('.jpg'),
                video.with_suffix('.png'),
                video.with_suffix('.webp'),
                video.with_name(video.stem + '-poster.jpg'),
                video.with_name(video.stem + '-poster.png'),
            ]
            has_cover = any(c.exists() for c in possible_covers)
            if not has_cover:
                checked += 1
                missing_covers.append(video.name)
                fetch_video_cover(str(video))

    print(f"需要获取封面: {checked} 个")
    return missing_covers


if __name__ == "__main__":
    if platform.system() == "Windows":
        BASE_PATH = Path(r"D:\Hentai-Video\hanime.tv")
    else:
        BASE_PATH = Path(r"/data/Hentai-Video/hanime.tv")

    database = {"hanime_data": []}

    for video in tqdm(list(BASE_PATH.rglob("*.mp4")), desc="update hanime"):
        title = ('-').join(video.stem.split('-')[0:-2])
        database["hanime_data"].append(title)

    with open("data-hanime.json", "w", encoding="utf8") as fp:
        json.dump(database, fp, ensure_ascii=False, indent=2)

    print("\n开始检查视频封面...")
    scan_videos(BASE_PATH)