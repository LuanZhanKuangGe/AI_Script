import argparse
import sys
import time

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.iwara.tv/",
}


def crawl_artist_videos(artist: str):
    page = 0
    total = 0
    while True:
        url = f"https://www.iwara.tv/profile/{artist}/videos?sort=date&page={page}"
        print(f"正在爬取第 {page} 页: {url}")

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                break
            except requests.RequestException as e:
                print(f"  请求失败 (尝试 {attempt + 1}/3): {e}")
                if attempt == 2:
                    print("多次请求失败，停止爬取")
                    return
                time.sleep(2)

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}，停止爬取")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        teasers = soup.find_all("div", class_="videoTeaser")

        if not teasers:
            print("没有更多视频，爬取结束")
            break

        for teaser in teasers:
            title_tag = teaser.find("a", class_="videoTeaser__title")
            if not title_tag:
                continue

            title = title_tag.get("title") or title_tag.get_text(strip=True)
            href = title_tag.get("href", "")

            video_id = href.split("/video/")[1].split("/")[0] if "/video/" in href else ""
            video_url = href

            print(f"{title}\t{video_id}\t{video_url}")
            total += 1

        page += 1
        time.sleep(1)

    print(f"共获取 {total} 个视频")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="爬取 iwara 用户视频列表")
    parser.add_argument("artist", help="iwara 用户名")
    args = parser.parse_args()
    crawl_artist_videos(args.artist)