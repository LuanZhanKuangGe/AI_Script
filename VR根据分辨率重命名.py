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

SUPPORTED_STUDIOS = {"darkroomvr", "18vr", "babevr", "badoinkvr", "czechvr", "czechvrfetish", "deepinsex", "fuckpassvr", "hamezo", "jimmydraws", "kinky-girls-berlin", "lethalhardcorevr", "littlecapricevr", "lustreality", "migotovr", "milfvr", "no2studiovr", "porncornvr"}

FILENAME_RE = re.compile(
    r'^\[(.+?)\]\s*(?:\[(\d{8})\]\s*)?(?:\[(\d+k)\]\s*)?(.+?)\.(mp4|mov)$', re.IGNORECASE)


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


def _dated_slug_by_short_month(slug, base_url, path_template="{slug}"):
    resp = _fetch(f"{base_url}/{path_template.format(slug=slug)}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s*\d{4})', resp.text)
    if not m:
        return slug, None
    parts = m.group(1).split()
    mon = MONTH_MAP.get(parts[0].lower())
    day = int(parts[1].rstrip(','))
    year = int(parts[2])
    if mon is None:
        return slug, None
    m2 = re.search(r'/video/([^/?]+)', resp.url)
    final_slug = m2.group(1) if m2 else slug
    return final_slug, f"{year:04d}{mon:02d}{day:02d}"


def _hamezo_info(slug):
    resp = _fetch(f"https://hamezo.com/{slug}/")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(1).lower())
    day = int(m.group(2))
    year = int(m.group(3))
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


def _jimmydraws_info(slug):
    headers = {"User-Agent": UA}
    url = f"https://jimmydrawsvr.com/{slug}"
    s = requests.Session()
    s.headers.update(headers)
    s.post(url, data={"confirm": "yes"}, timeout=30, allow_redirects=True)
    resp = s.get(url, timeout=30)
    m = re.search(r'Date:</span></td><td>(\d{2})/(\d{2})/(\d{4})', resp.text)
    if not m:
        return slug, None
    return slug, f"{m.group(3)}{m.group(2)}{m.group(1)}"


def _vrporn_info(slug):
    resp = _fetch(f"https://vrporn.com/{slug}/")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'"uploadDate":\s*"(\d{4})-(\d{2})-(\d{2})', resp.text)
    if not m:
        return slug, None
    return slug, f"{m.group(1)}{m.group(2)}{m.group(3)}"


def _milfvr_info(slug):
    resp = _fetch(f"https://www.milfvr.com/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+),\s+(\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(2).lower())
    day = int(m.group(1))
    year = int(m.group(3))
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


def _porncornvr_info(slug):
    resp = _fetch(f"https://porncornvr.com/scene/{slug}/")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(1).lower())
    day = int(m.group(2))
    year = int(m.group(3))
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


def _lustreality_info(slug):
    resp = _fetch(f"https://lustreality.com/en/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'"uploadDate":\s*"(\d{4})-(\d{2})-(\d{2})', resp.text)
    if not m:
        return slug, None
    return slug, f"{m.group(1)}{m.group(2)}{m.group(3)}"


def _littlecapricevr_info(slug):
    resp = _fetch(f"https://www.littlecaprice-dreams.com/project/{slug}/")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'Release:</b>\s*[A-Za-z]+,\s*(\d{1,2})\.\s*([A-Za-z]+)\s+(\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(2).lower())
    day = int(m.group(1))
    year = int(m.group(3))
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


def _slr_info(slug):
    resp = _fetch(f"https://www.sexlikereal.com/scenes/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    m = re.search(r'([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})', resp.text)
    if not m:
        return slug, None
    mon = MONTH_MAP.get(m.group(1).lower())
    day = int(m.group(2))
    year = int(m.group(3))
    if mon is None:
        return slug, None
    return slug, f"{year:04d}{mon:02d}{day:02d}"


def _kinky_girls_berlin_info(slug):
    resp = _fetch(f"https://kinkygirlsberlin.com/{slug}")
    if resp is None or resp.status_code != 200:
        return None, None
    if "Not found" in resp.text[:500]:
        return slug, None
    m = re.search(r'publish_date\\?":\s*\\?"(\d{4})-(\d{2})-(\d{2})', resp.text)
    if not m:
        return slug, None
    return slug, f"{m.group(1)}{m.group(2)}{m.group(3)}"


STUDIO_FETCHERS = {
    "darkroomvr": _darkroomvr_info,
    "18vr": lambda slug: _badoink_info(slug, "https://18vr.com"),
    "babevr": lambda slug: _badoink_info(slug, "https://babevr.com"),
    "badoinkvr": lambda slug: _badoink_info(slug, "https://badoinkvr.com"),
    "czechvr": _czechvr_info,
    "czechvrfetish": lambda slug: _czechvr_info(slug, "https://www.czechvrfetish.com"),
    "deepinsex": lambda slug: _dated_slug_by_short_month(slug, "https://deepinsex.com"),
    "fuckpassvr": lambda slug: _dated_slug_by_short_month(slug, "https://www.fuckpassvr.com", "video/{slug}"),
    "hamezo": _hamezo_info,
    "jimmydraws": _jimmydraws_info,
    "kinky-girls-berlin": _kinky_girls_berlin_info,
    "lethalhardcorevr": _slr_info,
    "littlecapricevr": _littlecapricevr_info,
    "lustreality": _lustreality_info,
    "migotovr": _vrporn_info,
    "milfvr": _milfvr_info,
    "no2studiovr": _slr_info,
    "porncornvr": _porncornvr_info,
}


def rename_videos_with_resolution():
    if not target_dir.exists():
        print(f"目录不存在: {target_dir}")
        return

    for filename in sorted(os.listdir(target_dir)):
        if not (filename.lower().endswith('.mp4') or filename.lower().endswith('.mov')):
            continue
        m = FILENAME_RE.match(filename)
        if not m:
            continue
        studio = m.group(1).lower()
        date_str = m.group(2)
        res = m.group(3)
        slug = m.group(4)
        ext = m.group(5)

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
            new_name = f"[{studio}] [{date_str}] [{res}] {slug}.{ext}"
        else:
            print(f"处理: {filename}")
            fetcher = STUDIO_FETCHERS[studio]
            final_slug, date_str = fetcher(slug)
            if date_str is None:
                print(f"  无法获取日期: {filename}")
                continue
            new_name = f"[{studio}] [{date_str}] [{res}] {final_slug}.{ext}"

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