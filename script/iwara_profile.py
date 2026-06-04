import re
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(r"D:\Hentai-MMD-new")

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    "Accept": "application/json",
    "Origin": "https://www.iwara.tv",
    "Referer": "https://www.iwara.tv/",
}


def request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            print(f"  HTTP {resp.status_code} (尝试 {attempt + 1}/{max_retries})")
        except requests.RequestException as e:
            print(f"  请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        time.sleep(2)
    return None


def get_existing_ids(folder: Path):
    ids = set()
    for mp4 in folder.rglob("*.mp4"):
        m = re.search(r'\[([A-Za-z0-9]+)\]', mp4.name)
        if m:
            ids.add(m.group(1).lower())
    return ids


def get_artist_folders():
    artists = []
    for folder in BASE_DIR.iterdir():
        if not folder.is_dir():
            continue
        m = re.match(r'^\[(.+?)\]', folder.name)
        if m:
            artists.append((m.group(1), folder))
    return artists


def crawl_artist(artist: str, folder: Path):
    existing_ids = get_existing_ids(folder)

    profile_data = request_with_retry(f"https://api.iwara.tv/profile/{artist}")
    if not profile_data:
        print(f"获取用户 {artist} 的资料失败")
        return

    user_id = profile_data["user"]["id"]
    username = profile_data["user"]["username"]
    print(f"\n=== {username} ({artist}) 已有 {len(existing_ids)} 个视频，查找新视频 ===")

    new_videos = []
    page = 0

    while True:
        url = f"https://api.iwara.tv/videos?user={user_id}&sort=date&page={page}&limit=50"
        data = request_with_retry(url)
        if not data:
            print("  请求失败，停止")
            break

        results = data.get("results", [])
        if not results:
            break

        for video in results:
            video_id = video["id"]
            if video_id.lower() in existing_ids:
                continue
            slug = video.get("slug", "")
            title = video["title"]
            video_url = f"/video/{video_id}/{slug}" if slug else f"/video/{video_id}"
            new_videos.append((title, video_id, video_url))

        count = data.get("count", 0)
        limit = data.get("limit", 50)
        if (page + 1) * limit >= count:
            break

        page += 1
        time.sleep(0.5)

    if new_videos:
        for title, vid, vurl in new_videos:
            print(f"{title}\t{vid}\t{vurl}")
    else:
        print("  无新视频")
    print(f"=== {artist}: 发现 {len(new_videos)} 个新视频 ===")


if __name__ == "__main__":
    artists = get_artist_folders()
    if not artists:
        print(f"在 {BASE_DIR} 下未找到 [artist] 格式的文件夹")
        sys.exit(1)

    print(f"找到 {len(artists)} 个 artist 文件夹")
    for artist, folder in artists:
        crawl_artist(artist, folder)