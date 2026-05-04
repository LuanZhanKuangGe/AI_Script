from pathlib import Path
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from tqdm import tqdm
except Exception:
    tqdm = lambda x, **kwargs: x


def parse_release_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str.strip(), "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return date_str


def fetch_video_info(video_id: str, video_file: Path) -> dict | None:
    url = f"https://hanime.tv/videos/hentai/{video_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                brand = None
                release_date = None
                alt_titles = []

                flex_div = soup.find('div', class_='flex wrap')
                if flex_div:
                    for item in flex_div.find_all('div', class_='hvpimbc-item'):
                        header = item.find('div', class_='hvpimbc-header')
                        if header and header.get_text().strip() == 'Brand':
                            brand_link = item.find('a', class_='hvpimbc-text')
                            if brand_link:
                                brand = brand_link.get_text().strip()
                        elif header and header.get_text().strip() == 'Release Date':
                            text_div = item.find('div', class_='hvpimbc-text')
                            if text_div:
                                release_date = text_div.get_text().strip()

                    for item in flex_div.find_all('div', class_='hvpimbc-item full'):
                        header = item.find('div', class_='hvpimbc-header')
                        if header and header.get_text().strip() == 'Alternate Titles':
                            h2 = item.find('h2')
                            if h2:
                                for span in h2.find_all('span', class_='mr-3'):
                                    alt_titles.append(span.get_text().strip())

                japanese_title = None
                for title in alt_titles:
                    if any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in title):
                        japanese_title = title
                        break
                if not japanese_title and alt_titles:
                    japanese_title = alt_titles[0]

                return {
                    'brand': brand,
                    'release_date': parse_release_date(release_date) if release_date else None,
                    'title': japanese_title,
                    'alt_titles': alt_titles
                }
        except Exception as e:
            print(f"获取视频信息失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def create_nfo(video_info: dict, video_file: Path, video_id: str):
    nfo_path = video_file.with_suffix('.nfo')
    if nfo_path.exists():
        return

    brand = video_info.get('brand')
    release_date = video_info.get('release_date')
    title = video_info.get('title')

    if not brand or not release_date or not title:
        print(f"信息不完整，跳过创建NFO: id={video_id}, brand={brand}, release_date={release_date}, title={title}")
        return

    parts = video_id.split('-')
    if len(parts) >= 2 and parts[-1].isdigit():
        episode = int(parts[-1])
        title = f"{title} EP{episode}"

    nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>{title}</title>
  <studio>{brand}</studio>
  <releasedate>{release_date}</releasedate>
</movie>
"""

    with open(nfo_path, 'w', encoding='utf-8') as f:
        f.write(nfo_content)
    print(f"已创建NFO: {nfo_path}")


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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://hanime.tv/'
    }
    for attempt in range(3):
        try:
            resp = requests.get(cover_url, timeout=30, headers=headers)
            if resp.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                print(f"已保存封面: {save_path}")
                return
            else:
                print(f"下载失败状态码: {resp.status_code}")
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
                if cover_url:
                    download_cover(cover_url, save_path)

    print(f"需要获取封面: {checked} 个")
    return missing_covers


if __name__ == "__main__":
    from all_path import HENTAI_VIDEO_HANIME as BASE_PATH

    videos = list(BASE_PATH.rglob("*.mp4"))
    print(f"找到 {len(videos)} 个视频文件")

    database = {"hanime_data": []}

    for video in tqdm(videos, desc="扫描视频"):
        parts = video.stem.split('-')
        if len(parts) >= 2 and parts[-2].strip() == '720p':
            video_id = '-'.join(parts[:-2])
            database["hanime_data"].append(video_id)

            possible_covers = [
                video.with_suffix('.jpg'),
                video.with_suffix('.png'),
                video.with_suffix('.webp'),
                video.with_name(video.stem + '-poster.jpg'),
                video.with_name(video.stem + '-poster.png'),
            ]
            has_cover = any(c.exists() for c in possible_covers)
            if not has_cover:
                cover_url, save_path = fetch_video_cover(video)
                if cover_url:
                    download_cover(cover_url, save_path)

            nfo_path = video.with_suffix('.nfo')
            if not nfo_path.exists():
                video_info = fetch_video_info(video_id, video)
                if video_info:
                    create_nfo(video_info, video, video_id)

    with open("data-hanime.json", "w", encoding="utf8") as fp:
        json.dump(database, fp, ensure_ascii=False, indent=2)
    print("数据库已保存")