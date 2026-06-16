import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

VRCOVER_DIR = Path("G:/VR/vrcosplayx")
BASE_URL = "https://vrcosplayx.com/cosplaypornvideos?order=newest"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def fetch_page(url: str) -> BeautifulSoup | None:
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15, headers=HEADERS)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  获取页面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def download_cover(cover_url: str, save_path: Path) -> bool:
    dl_headers = {**HEADERS, "Referer": "https://vrcosplayx.com/"}
    for attempt in range(3):
        try:
            resp = requests.get(cover_url, timeout=30, headers=dl_headers)
            if resp.status_code == 200:
                save_path.write_bytes(resp.content)
                print(f"  已保存: {save_path.name}")
                return True
        except Exception as e:
            print(f"  下载封面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return False


def scan():
    print("[VRCosplayX] 开始下载视频封面")
    VRCOVER_DIR.mkdir(parents=True, exist_ok=True)

    page = 1
    new_covers = 0
    skipped = 0

    while True:
        if page == 1:
            url = BASE_URL
        else:
            url = f"https://vrcosplayx.com/cosplaypornvideos/{page}?order=newest"

        print(f"\n[第{page}页] {url}")
        soup = fetch_page(url)
        if not soup:
            print(f"  无法获取第{page}页，停止")
            break

        cards = soup.select("div.video-card")
        if not cards:
            print(f"  第{page}页没有视频，停止")
            break

        print(f"  找到 {len(cards)} 个视频")

        for card in cards:
            img_tag = card.select_one(".video-card-image")
            if not img_tag or not img_tag.get("data-src"):
                continue
            cover_url = img_tag["data-src"].split("?")[0]

            title_tag = card.select_one(".video-card-title")
            if not title_tag:
                continue
            title = title_tag.get("title", "").strip() or title_tag.get_text(strip=True)
            if not title:
                continue

            date_tag = card.select_one(".video-card-upload-date")
            release_date = ""
            if date_tag and date_tag.get("content"):
                release_date = date_tag["content"][:10]

            safe_title = sanitize_filename(title)
            ext = Path(cover_url).suffix or ".jpg"
            filename = f"[{release_date}] {safe_title}{ext}" if release_date else f"{safe_title}{ext}"
            save_path = VRCOVER_DIR / filename

            if save_path.exists():
                skipped += 1
                continue

            if download_cover(cover_url, save_path):
                new_covers += 1

        next_link = soup.find("link", rel="next")
        if not next_link:
            print(f"  没有下一页，共{page}页")
            break

        page += 1
        if page > 100:
            print("  达到最大页数限制(100)")
            break

    print(f"\n[VRCosplayX] 完成: +{new_covers}封面, 跳过{skipped}个")


if __name__ == "__main__":
    scan()
