import os
import re
import time

import cv2
import requests

from all_path import PORN_VR as target_dir


def get_video_width(filepath):
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()
    return width


def width_to_k(width):
    if width is None:
        return None
    k = round(width / 1000)
    return f"{k}k"


MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SUPPORTED_STUDIOS = {"darkroomvr", "18vr", "babevr", "badoinkvr", "czechvr", "czechvrfetish", "deepinsex"}

FILENAME_RE = re.compile(
    r'^\[(.+?)\]\s*(?:\[(\d{8})\]\s*)?(?:\[(\d+k)\]\s*)?(.+?)\.mp4$', re.IGNORECASE)


def _fetch(url):
    headers = {"User-Agent": UA, "Cookie": "age_check=1"}
    for attempt in range(3):
        try:
            return requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        except Exception as e:
            print(f"  获取页面失败 ({attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(3)
    return None


def _darkroomvr_info(slug):
    resp = _fetch(f"https://darkroomvr.com/video/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'/video/([^/?]+)$', resp.url)
    final_slug = m.group(1) if m else slug
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+),\s+(\d{4})', resp.text)
    if not m:
        return final_slug, None
    day = int(m.group(1))
    mon = MONTH_MAP.get(m.group(2).lower())
    year = int(m.group(3))
    if mon is None:
        return final_slug, None
    return final_slug, f"{year:04d}{mon:02d}{day:02d}"


def _badoink_info(slug, base_url):
    resp = _fetch(f"{base_url}/vrpornvideo/{slug.replace('-', '_')}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'/vrpornvideo/([^/?]+?)/?$', resp.url)
    final_slug = m.group(1).replace('_', '-') if m else slug
    m = re.search(r'"uploadDate":\s*"(\d{4})-(\d{2})-(\d{2})', resp.text)
    if not m:
        m = re.search(r'content="(\d{4})-(\d{2})-(\d{2})T', resp.text)
    if not m:
        return final_slug, None
    return final_slug, f"{m.group(1)}{m.group(2)}{m.group(3)}"


def _czechvr_info(slug, base_url="https://www.czechvr.com"):
    mid = re.match(r'^(?:detail-)?(\d+)-(.+)$', slug)
    if not mid:
        print(f"  czechvr 文件名缺少视频ID: {slug}")
        return None, None
    resp = _fetch(f"{base_url}/detail-{mid.group(1)}-{mid.group(2)}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'<div class="datum">\s*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})\s*</div>', resp.text)
    if not m:
        m = re.search(r'>\s*([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})\s*<', resp.text)
    final_slug = f"detail-{mid.group(1)}-{mid.group(2)}"
    if not m:
        return final_slug, None
    mon = MONTH_MAP.get(m.group(1).lower())
    if mon is None:
        return final_slug, None
    day = int(m.group(2))
    year = int(m.group(3))
    return final_slug, f"{year:04d}{mon:02d}{day:02d}"


def _deepinsex_info(slug):
    resp = _fetch(f"https://deepinsex.com/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s*\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(1).split()[0].lower())
    day = int(m.group(1).split()[1].rstrip(','))
    year = int(m.group(1).split()[2])
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


STUDIO_FETCHERS = {
    "darkroomvr": _darkroomvr_info,
    "18vr": lambda slug: _badoink_info(slug, "https://18vr.com"),
    "babevr": lambda slug: _badoink_info(slug, "https://babevr.com"),
    "badoinkvr": lambda slug: _badoink_info(slug, "https://badoinkvr.com"),
    "czechvr": _czechvr_info,
    "czechvrfetish": lambda slug: _czechvr_info(slug, "https://www.czechvrfetish.com"),
    "deepinsex": _deepinsex_info,
}


def rename_videos_with_resolution():
    if not target_dir.exists():
        print(f"目录不存在: {target_dir}")
        return

    for filename in sorted(os.listdir(target_dir)):
        if not filename.lower().endswith('.mp4'):
            continue
        m = FILENAME_RE.match(filename)
        if not m:
            continue
        studio = m.group(1).lower()
        date_str = m.group(2)
        res = m.group(3)
        slug = m.group(4)

        if studio not in SUPPORTED_STUDIOS:
            continue

        filepath = target_dir / filename
        new_name = filename

        if res is None:
            res = width_to_k(get_video_width(str(filepath)))
            if res is None:
                print(f"无法获取分辨率: {filename}")
                continue

        if date_str is not None:
            if res == m.group(3):
                continue
            new_name = f"[{studio}] [{date_str}] [{res}] {slug}.mp4"
        else:
            print(f"处理: {filename}")
            fetcher = STUDIO_FETCHERS[studio]
            final_slug, date_str = fetcher(slug)
            if date_str is None:
                print(f"  无法获取日期: {filename}")
                continue
            new_name = f"[{studio}] [{date_str}] [{res}] {final_slug}.mp4"

        if new_name == filename:
            continue
        new_path = target_dir / new_name
        if new_path.exists():
            print(f"文件已存在，跳过: {new_name}")
            continue
        print(f"重命名: {filename} -> {new_name}")
        os.rename(filepath, new_path)


if __name__ == "__main__":
    rename_videos_with_resolution()