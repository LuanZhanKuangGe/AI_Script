from pathlib import Path
import platform
import json
import time
import requests
from bs4 import BeautifulSoup

try:
    from tqdm import tqdm
except Exception:
    tqdm = lambda x, **kwargs: x


def fetch_video_cover(video_file: Path) -> tuple[str | None, str | None]:
    parts = video_file.stem.split('-')
    if len(parts) >= 2 and parts[-2].strip() == '720p':
        video_id = '-'.join(parts[:-2])
        url = f"https://hanime.tv/videos/hentai/{video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=15, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    img = soup.find('div', class_='hvpi-cover-container')
                    if img:
                        img_tag = img.find('img')
                        if img_tag and img_tag.get('src'):
                            cover_url = img_tag['src']
                            ext = Path(cover_url).suffix or '.jpg'
                            save_path = video_file.with_suffix(ext)
                            return cover_url, str(save_path)
                    print(f"未找到封面元素，当前页面: {resp.text[:500]}")
            except Exception as e:
                print(f"获取封面失败 ({attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)
    else:
        print(f"无法解析文件名格式: {video_file.stem}")
    return None, None


def download_cover(cover_url: str, save_path: str):
    for attempt in range(3):
        try:
            resp = requests.get(cover_url, timeout=30)
            if resp.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                print(f"已保存封面: {save_path}")
                return
        except Exception as e:
            print(f"下载封面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)


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
                cover_url, save_path = fetch_video_cover(video)
                if cover_url and save_path:
                    download_cover(cover_url, save_path)

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