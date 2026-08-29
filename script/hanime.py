import json
import sys
import time
from pathlib import Path
from datetime import datetime
import re
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
                resp.encoding = "utf-8"
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

                if not alt_titles:
                    alt_titles = _extract_alternate_names(soup)

                if not brand or not release_date or not alt_titles:
                    brand, release_date, alt_titles = _extract_info_fallback(soup, brand, release_date, alt_titles)

                japanese_title = next((t for t in alt_titles if _has_kana(t)), None)
                if not japanese_title:
                    japanese_title = next((t for t in alt_titles if _has_cjk(t)), None)
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


def _has_kana(s: str) -> bool:
    return any(("\u3040" <= c <= "\u309f") or ("\u30a0" <= c <= "\u30ff") or ("\u31f0" <= c <= "\u31ff") for c in s)


def _has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def _extract_alternate_names(soup: BeautifulSoup) -> list:
    h2 = soup.find("h2", string=lambda s: s and "Alternate Names" in s)
    if not h2:
        return []
    content = h2.find_next("div", attrs={"data-expand-content": True})
    if not content:
        return []
    names = []
    for el in content.find_all(["span", "div", "a", "button", "p"]):
        txt = el.get_text(" ", strip=True)
        if txt and txt not in names:
            names.append(txt)
    return names


def _extract_info_fallback(soup: BeautifulSoup, brand: str | None, release_date: str | None, alt_titles: list) -> tuple:
    if not brand:
        brand_link = soup.find("a", href=re.compile(r"/browse/brands/"))
        if brand_link:
            b = brand_link.get("title") or brand_link.get_text(strip=True) or ""
            b = re.sub(r"^Browse more\s+", "", b)
            b = re.sub(r"\s+videos$", "", b)
            brand = b.strip() or None
    if not release_date:
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.get_text())
            except Exception:
                continue
            upload = data.get("uploadDate")
            if upload:
                release_date = upload[:10]
                break
    if not release_date:
        m = re.search(
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
            soup.get_text(),
        )
        release_date = m.group(0) if m else None
    if not alt_titles:
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.get_text())
            except Exception:
                continue
            name = data.get("name")
            if name:
                alt_titles = [name]
                break
    return brand, release_date, alt_titles


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
                cover_url = _extract_cover(resp.text)
                if cover_url:
                    ext = Path(cover_url).suffix or ".jpg"
                    save_path = video_file.with_suffix(ext)
                    return cover_url, str(save_path)
        except Exception as e:
            print(f"  获取封面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return None, None


def _extract_cover(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]
    text = html.replace("&quot;", '"')
    for key in ("cover_url", "poster_url"):
        m = re.search(r'"%s"\s*:\s*\[\s*\d+\s*,\s*"([^"]+)"' % re.escape(key), text)
        if m:
            return m.group(1)
    m = re.search(r'https://hanime-cdn\.com/images/(?:covers|posters)/[^\s"\'<>]+\.(?:jpg|png|webp)', text)
    if m:
        return m.group(0)
    img_div = soup.find("div", class_="hvpi-cover-container")
    if img_div:
        img_tag = img_div.find("img")
        if img_tag and img_tag.get("src"):
            return img_tag["src"]
    return None


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


def scan(base_path: Path, do_nfo: bool) -> None:
    mode = "完整" if do_nfo else "快速"
    print(f"[Hanime] {mode}模式启动")

    if not base_path.exists():
        print(f"[Hanime] 路径不存在：{base_path}")
        return

    videos = list(base_path.rglob("*.mp4"))
    print(f"  找到 {len(videos)} 个视频文件")

    database = {"hanime_data": []}
    missing_covers: list[Path] = []
    missing_nfos: list[tuple[Path, str]] = []

    print("  [1/3] 扫描视频，统计缺失项...")
    for i, video in enumerate(videos, 1):
        if i % 100 == 0 or i == len(videos):
            print(f"  扫描 {i}/{len(videos)} (缺失封面 {len(missing_covers)}, 缺失NFO {len(missing_nfos)})")

        parts = video.stem.split("-")
        if len(parts) >= 2 and parts[-2].strip() == "720p":
            video_id = "-".join(parts[:-2])
            database["hanime_data"].append(video_id)

            if not check_cover_exists(video):
                missing_covers.append(video)

            if do_nfo and not video.with_suffix(".nfo").exists():
                missing_nfos.append((video, video_id))

    print(f"  扫描完成：{len(database['hanime_data'])} 个视频，缺失封面 {len(missing_covers)} 个，缺失NFO {len(missing_nfos)} 个")

    new_covers = 0
    print(f"  [2/3] 开始补全封面（{len(missing_covers)} 个）...")
    for i, video in enumerate(missing_covers, 1):
        if i % 50 == 0 or i == len(missing_covers):
            print(f"  封面 {i}/{len(missing_covers)} (+{new_covers})")
        cover_url, save_path = fetch_video_cover(video)
        if cover_url:
            download_cover(cover_url, save_path)
            new_covers += 1

    new_nfos = 0
    if do_nfo:
        print(f"  [3/3] 开始补全NFO（{len(missing_nfos)} 个）...")
        for i, (video, video_id) in enumerate(missing_nfos, 1):
            if i % 50 == 0 or i == len(missing_nfos):
                print(f"  NFO {i}/{len(missing_nfos)} (+{new_nfos})")
            video_info = fetch_video_info(video_id, video)
            if video_info:
                create_nfo(video_info, video, video_id)
                new_nfos += 1

    save_data(database)
    print(f"  {len(database['hanime_data'])} 个视频，+{new_covers} 封面，+{new_nfos} NFO")
    print(f"[Hanime] {mode}模式完成")


def scan_full(base_path: Path) -> None:
    scan(base_path, do_nfo=True)


def scan_quick(base_path: Path) -> None:
    scan(base_path, do_nfo=False)


if __name__ == "__main__":
    print(f"[Hanime] 模式={MODE}")
    if MODE == "quick":
        scan_quick(HENTAI_VIDEO_HANIME)
    else:
        scan_full(HENTAI_VIDEO_HANIME)