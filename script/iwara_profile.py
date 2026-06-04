import argparse
import sys
import time

import requests

sys.stdout.reconfigure(encoding='utf-8')


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


def crawl_artist_videos(artist: str):
    profile_data = request_with_retry(f"https://api.iwara.tv/profile/{artist}")
    if not profile_data:
        print(f"获取用户 {artist} 的资料失败")
        return

    user_id = profile_data["user"]["id"]
    username = profile_data["user"]["username"]
    print(f"用户: {username} (ID: {user_id})")

    page = 0
    total = 0
    while True:
        url = f"https://api.iwara.tv/videos?user={user_id}&sort=date&page={page}&limit=50"
        print(f"正在爬取第 {page} 页...")

        data = request_with_retry(url)
        if not data:
            print("请求失败，停止爬取")
            return

        results = data.get("results", [])
        if not results:
            print("没有更多视频，爬取结束")
            break

        for video in results:
            video_id = video["id"]
            slug = video.get("slug", "")
            title = video["title"]
            video_url = f"/video/{video_id}/{slug}" if slug else f"/video/{video_id}"

            print(f"{title}\t{video_id}\t{video_url}")
            total += 1

        count = data.get("count", 0)
        limit = data.get("limit", 50)
        if (page + 1) * limit >= count:
            print("已爬取所有视频")
            break

        page += 1
        time.sleep(0.5)

    print(f"共获取 {total} 个视频")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="爬取 iwara 用户视频列表")
    parser.add_argument("artist", help="iwara 用户名")
    args = parser.parse_args()
    crawl_artist_videos(args.artist)