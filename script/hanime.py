import json
import sys
import time
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from all_path import HENTAI_VIDEO_HANIME, QINGLONG_SCRIPTS

MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("quick", "full") else "full"

DATA_FILE = Path(__file__).parent / "data-hanime.json"
DATA_FILE_REMOTE = QINGLONG_SCRIPTS / "data-hanime.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def save_data(data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    DATA_FILE.write_text(content, encoding="utf-8")
    try:
        DATA_FILE_REMOTE.write_text(content, encoding="utf-8")
        print(f"  已保存 -> {DATA_FILE.name} + 远程")
    except Exception:
        print(f"  已保存 -> {DATA_FILE.name} (远程失败)")


def parse_release_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str.strip(), "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def fetch_video_info(video_id: str, video_file: Path) -> dict | None:
    url = f"https://hanime.tv/videos/hentai/{video_id}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15, headers=HEADERS)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                brand = release_date = None
                alt_titles = []

                flex_div = soup.find("div", class_="flex wrap")
                if flex_div:
                    for item in flex_div.find_all("div", class_="hvpimbc-item"):
                        header = item.find("div", class_="hvpimbc-header")
                        if not header:
                            continue
                        header_text = header.get_text().strip()
                        if header_text == "Brand":
                            link = item.find("a", class_="hvpimbc-text")
                            if link:
                                brand = link.get_text().strip()
                        elif header_text == "Release Date":
                            text_div = item.find("div", class_="hvpimbc-text")
                            if text_div:
                                release_date = text_div.get_text().strip()

                    for item in flex_div.find_all("div", class_="hvpimbc-item full"):
                        header = item.find("div", class_="hvpimbc-header")
                        if header and header.get_text().strip() == "Alternate Titles":
                            h2 = item.find("h2")
                            if h2:
                                for span in h2.find_all("span", class_="mr-3"):
                                    alt_titles.append(span.get_text().strip())

                japanese_title = None
                for title in alt_titles:
                    if any("\u3040" <= c <= "\u309f" or "\u30a0" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in title):
                        japanese_title = title
                        break
                if not japanese_title and alt_titles:
                    japanese_title = alt_titles[0]

                return {
                    "brand": brand,
                    "release_date": parse_release_date(release_date) if release_date else None,
                    "title": japanese_title,
                    "alt_titles": alt_titles,
                }
        except Exception as e:
            print(f"  获取视频信息失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def create_nfo(video_info: dict, video_file: Path, video_id: str):
    nfo_path = video_file.with_suffix(".nfo")
    if nfo_path.exists():
        return
    brand = video_info.get("brand")
    release_date = video_info.get("release_date")
    title = video_info.get("title")
    if not brand or not release_date or not title:
        print(f"  信息不完整，跳过: id={video_id}")
        return
    parts = video_id.split("-")
    if len(parts) >= 2 and parts[-1].isdigit():
        title = f"{title} EP{int(parts[-1])}"
    nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>{title}</title>
  <studio>{brand}</studio>
  <releasedate>{release_date}</releasedate>
</movie>
"""
    nfo_path.write_text(nfo_content, encoding="utf-8")
    print(f"  已创建NFO: {nfo_path.name}")


def fetch_video_cover(video_file: Path) -> tuple[str | None, str | None]:
    parts = video_file.stem.split("-")
    if len(parts) < 2 or parts[-2].strip() != "720p":
        print(f"  无法解析文件名: {video_file.stem}")
        return None, None
    video_id = "-".join(parts[:-2])
    url = f"https://hanime.tv/videos/hentai/{video_id}"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15, headers=HEADERS)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                img_div = soup.find("div", class_="hvpi-cover-container")
                if img_div:
                    img_tag = img_div.find("img")
                    if img_tag and img_tag.get("src"):
                        cover_url = img_tag["src"]
                        ext = Path(cover_url).suffix or ".jpg"
                        save_path = video_file.with_suffix(ext)
                        return cover_url, str(save_path)
        except Exception as e:
            print(f"  获取封面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None, None


def download_cover(cover_url: str, save_path: str):
    dl_headers = {**HEADERS, "Referer": "https://hanime.tv/"}
    for attempt in range(3):
        try:
            resp = requests.get(cover_url, timeout=30, headers=dl_headers)
            if resp.status_code == 200:
                Path(save_path).write_bytes(resp.content)
                print(f"  已保存封面: {Path(save_path).name}")
                return
            print(f"  下载失败，状态码: {resp.status_code}")
        except Exception as e:
            print(f"  下载封面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)


def check_cover_exists(video: Path) -> bool:
    return any(
        video.with_suffix(ext).exists() or video.with_name(video.stem + f"-poster{ext}").exists()
        for ext in (".jpg", ".png", ".webp")
    )


def scan_full(base_path: Path) -> None:
    print("[Hanime] 完整模式启动")

    if not base_path.exists():
        print(f"[Hanime] 路径不存在：{base_path}")
        return

    videos = list(base_path.rglob("*.mp4"))
    print(f"  找到 {len(videos)} 个视频文件")

    database = {"hanime_data": []}
    new_covers = 0
    new_nfos = 0

    for i, video in enumerate(videos, 1):
        if i % 100 == 0 or i == len(videos):
            print(f"  {i}/{len(videos)} (封面+{new_covers}, NFO+{new_nfos})")

        parts = video.stem.split("-")
        if len(parts) >= 2 and parts[-2].strip() == "720p":
            video_id = "-".join(parts[:-2])
            database["hanime_data"].append(video_id)

            if not check_cover_exists(video):
                cover_url, save_path = fetch_video_cover(video)
                if cover_url:
                    download_cover(cover_url, save_path)
                    new_covers += 1

            nfo_path = video.with_suffix(".nfo")
            if not nfo_path.exists():
                video_info = fetch_video_info(video_id, video)
                if video_info:
                    create_nfo(video_info, video, video_id)
                    new_nfos += 1

    save_data(database)
    print(f"  {len(database['hanime_data'])} 个视频，+{new_covers} 封面，+{new_nfos} NFO")
    print("[Hanime] 完整模式完成")


def scan_quick(base_path: Path) -> None:
    print("[Hanime] 快速模式暂不支持，执行完整模式")
    scan_full(base_path)


if __name__ == "__main__":
    print(f"[Hanime] 模式={MODE}")
    if MODE == "quick":
        scan_quick(HENTAI_VIDEO_HANIME)
    else:
        scan_full(HENTAI_VIDEO_HANIME)