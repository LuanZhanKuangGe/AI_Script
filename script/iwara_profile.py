import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(r"D:\Hentai-MMD-new")
MIN_LIKES = 500
CACHE_INTERVAL = timedelta(hours=3)
CACHE_FILE = Path(__file__).parent / "crawl_cache.json"

IWARA_EMAIL = "lianyeshi"
IWARA_PASSWORD = "6210445yezhise"
IWARA_KEY = "mSvL05GfEmeEmsEYfGCnVpEjYgTJraJN"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    "Accept": "application/json",
    "Origin": "https://www.iwara.tv",
    "Referer": "https://www.iwara.tv/",
}

session = requests.Session()
_access_token = None
_refresh_token = None


def login():
    global _refresh_token, _access_token
    resp = session.post(
        "https://api.iwara.tv/user/login",
        json={"email": IWARA_EMAIL, "password": IWARA_PASSWORD},
        headers=API_HEADERS, timeout=15,
    )
    if resp.status_code != 200:
        print(f"登录失败: HTTP {resp.status_code}")
        return False
    _refresh_token = resp.json()["token"]

    resp2 = session.post(
        "https://api.iwara.tv/user/token",
        json={"refreshToken": _refresh_token},
        headers={**API_HEADERS, "Authorization": f"Bearer {_refresh_token}"},
        timeout=15,
    )
    if resp2.status_code != 200:
        print(f"获取 access token 失败: HTTP {resp2.status_code}")
        return False
    _access_token = resp2.json()["accessToken"]
    print("登录成功")
    return True


def refresh_access_token():
    global _access_token
    if not _refresh_token:
        return False
    try:
        resp = session.post(
            "https://api.iwara.tv/user/token",
            json={"refreshToken": _refresh_token},
            headers={**API_HEADERS, "Authorization": f"Bearer {_refresh_token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            _access_token = resp.json()["accessToken"]
            return True
    except Exception:
        pass
    return False


def get_auth_headers():
    headers = {**API_HEADERS}
    if _access_token:
        headers["Authorization"] = f"Bearer {_access_token}"
    return headers


def get_x_version(url_str):
    parsed = urlparse(url_str)
    filename = parsed.path.split("/")[-1]
    expires = ""
    qs = parse_qs(parsed.query)
    if "expires" in qs:
        expires = qs["expires"][0]
    data = f"{filename}_{expires}_{IWARA_KEY}".encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def request_with_retry(url, max_retries=3, use_auth=False, use_xversion=False):
    for attempt in range(max_retries):
        headers = get_auth_headers() if use_auth else API_HEADERS.copy()
        if use_xversion:
            headers["X-Version"] = get_x_version(url)
            headers["X-Site"] = "www.iwara.tv"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401 and use_auth and attempt == 0:
                if refresh_access_token():
                    continue
            print(f"  HTTP {resp.status_code} (尝试 {attempt + 1}/{max_retries})")
        except requests.RequestException as e:
            print(f"  请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        time.sleep(2)
    return None


def get_existing_ids(folder: Path):
    ids = set()
    quality_tags = {"Source", "540", "360"}
    for mp4 in folder.rglob("*.mp4"):
        brackets = re.findall(r'\[([^\]]+)\]', mp4.stem)
        if not brackets:
            continue
        if len(brackets) >= 2 and brackets[-1] in quality_tags:
            ids.add(brackets[-2].lower())
        else:
            ids.add(brackets[-1].lower())
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


def sanitize_filename(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, '')
    return name.strip()


MAX_PATH_LEN = 240


def build_video_filename(date: str, title: str, vid: str, folder: Path) -> str:
    folder_len = len(str(folder))
    suffix = f" [{vid}] [Source].mp4"
    max_title_len = MAX_PATH_LEN - folder_len - 1 - len(f"[{date}] ") - len(suffix)
    if max_title_len < 10:
        max_title_len = 10
    truncated = title
    if len(truncated) > max_title_len:
        truncated = title[:max_title_len - 1] + "\u2026"
    return sanitize_filename(f"[{date}] {truncated} [{vid}] [Source].mp4")


def get_source_download(video_id: str):
    data = request_with_retry(f"https://api.iwara.tv/video/{video_id}", use_auth=True)
    if not data:
        return None

    file_url = data.get("fileUrl")
    if not file_url:
        return None

    qualities = request_with_retry(file_url, use_auth=True, use_xversion=True)
    if not qualities:
        return None

    source = None
    available = []
    for q in qualities:
        name = q.get("name", "")
        if name == "Source":
            source = q
            break
        if name != "preview":
            available.append(name)

    if not source:
        return {"has_source": False, "available": available}

    dl_path = source["src"]["download"]
    dl_url = ("https:" + dl_path) if dl_path.startswith("//") else dl_path

    return {"has_source": True, "url": dl_url}


from datetime import datetime, timedelta
OUTPUT_DIR = Path(r"C:\Users\zhoub\Downloads")
OUTPUT_FILE = OUTPUT_DIR / f"download_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def append_to_output(url_line):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(url_line + "\n")


def rename_existing_videos(folder: Path, video_info: dict):
    renamed = 0
    skipped = 0
    for mp4 in sorted(folder.glob("*.mp4")):
        if re.match(r'^\[\d{4}-\d{2}-\d{2}\]', mp4.stem):
            continue

        brackets = re.findall(r'\[([^\]]+)\]', mp4.stem)
        quality_tags = {"Source", "540", "360"}
        vid = None
        if len(brackets) >= 2 and brackets[-1] in quality_tags:
            vid = brackets[-2]
        elif brackets:
            vid = brackets[-1]

        if not vid:
            skipped += 1
            continue

        info = video_info.get(vid.lower())
        if not info:
            skipped += 1
            continue

        date = info["date"]
        title = info["title"]
        new_name = build_video_filename(date, title, vid, mp4.parent)
        new_path = mp4.parent / new_name
        if new_path.exists():
            skipped += 1
            continue
        mp4.rename(new_path)
        print(f"    重命名: {mp4.name} -> {new_name}")
        renamed += 1

    if renamed or skipped:
        print(f"  重命名 {renamed} 个现有视频" + (f"，跳过 {skipped} 个" if skipped else ""))


def crawl_artist(artist: str, folder: Path, cache: dict):
    now = datetime.now()
    last_time = cache.get(artist)
    if last_time:
        try:
            elapsed = now - datetime.fromisoformat(last_time)
            if elapsed < CACHE_INTERVAL:
                print(f"\n=== {artist}: 跳过（{elapsed.seconds // 60} 分钟前已处理） ===")
                return
        except Exception:
            pass

    existing_ids = get_existing_ids(folder)

    profile_data = request_with_retry(f"https://api.iwara.tv/profile/{artist}")
    if not profile_data:
        print(f"获取用户 {artist} 的资料失败")
        return

    user_id = profile_data["user"]["id"]
    username = profile_data["user"]["username"]
    user_name = profile_data["user"].get("name", username)
    updated_at = profile_data["user"].get("updatedAt", "")
    updated_date = updated_at[:10] if updated_at else ""

    all_videos = []
    video_info = {}
    total_likes = 0
    total_videos = 0
    skipped_private = 0
    skipped_non_r18 = 0
    skipped_existing = 0
    skipped_likes = 0
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
            total_videos += 1
            total_likes += video.get("numLikes", 0)
            created_at = video.get("createdAt", "")
            video_date = created_at[:10] if created_at else ""
            video_info[video["id"].lower()] = {"date": video_date, "title": video["title"]}
            if video.get("private", False):
                skipped_private += 1
                continue
            rating = video.get("rating", "")
            if rating != "ecchi":
                skipped_non_r18 += 1
                continue
            if video.get("numLikes", 0) < MIN_LIKES:
                skipped_likes += 1
                continue
            video_id = video["id"]
            if video_id.lower() in existing_ids:
                skipped_existing += 1
                continue
            slug = video.get("slug", "")
            title = video["title"]
            all_videos.append({"id": video_id, "slug": slug, "title": title, "date": video_date})

        count = data.get("count", 0)
        limit = data.get("limit", 50)
        if (page + 1) * limit >= count:
            break

        page += 1
        time.sleep(0.5)

    avg_likes_k = ""
    if total_videos > 0:
        avg_likes = total_likes / total_videos
        avg_likes_k = f"#{avg_likes / 1000:.1f}k"

    parts = [f"[{username}]", user_name]
    if updated_date:
        parts.append(f"#{updated_date}")
    if avg_likes_k:
        parts.append(avg_likes_k)
    new_folder_name = sanitize_filename(" ".join(parts))
    new_folder = folder.parent / new_folder_name
    if folder != new_folder and not new_folder.exists():
        folder.rename(new_folder)
        print(f"  文件夹重命名: {folder.name} -> {new_folder_name}")
        folder = new_folder
    elif folder != new_folder and new_folder.exists():
        print(f"  目标文件夹已存在: {new_folder_name}，跳过重命名")
    existing_ids = get_existing_ids(folder)

    rename_existing_videos(folder, video_info)

    print(f"\n=== {username} ({artist}) 已有 {len(existing_ids)} 个视频，查找新视频 ===")
    print(f"  跳过: 私有={skipped_private}, 非R18={skipped_non_r18}, 已有={skipped_existing}, 收藏<{MIN_LIKES}={skipped_likes}")

    if not all_videos:
        print("  无新视频")
        return

    print(f"  发现 {len(all_videos)} 个新视频，解析下载地址...")

    found = 0
    no_source = 0
    fail_info = 0
    for i, video in enumerate(all_videos, 1):
        vid = video["id"]
        title = video["title"]
        vdate = video["date"]
        print(f"  [{i}/{len(all_videos)}] {title} ({vid})")

        dl_info = get_source_download(vid)
        if not dl_info:
            print(f"    获取下载信息失败，跳过")
            fail_info += 1
            time.sleep(0.5)
            continue

        if not dl_info["has_source"]:
            avail = ", ".join(dl_info["available"]) if dl_info["available"] else "无"
            print(f"    无 Source 品质 (可用: {avail})，跳过")
            no_source += 1
            time.sleep(0.5)
            continue

        filename = build_video_filename(vdate, title, vid, folder)
        url_line = f"{dl_info['url']}&artist={artist}&name={quote(filename)}"
        append_to_output(url_line)
        found += 1

    print(f"\n=== {artist}: 写入 {found}, 无Source {no_source}, 解析失败 {fail_info} ===")
    cache[artist] = datetime.now().isoformat()


if __name__ == "__main__":
    if not login():
        sys.exit(1)

    artists = get_artist_folders()
    if not artists:
        print(f"在 {BASE_DIR} 下未找到 [artist] 格式的文件夹")
        sys.exit(1)

    print(f"找到 {len(artists)} 个 artist 文件夹")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass

    cache = load_cache()
    for artist, folder in artists:
        crawl_artist(artist, folder, cache)
        save_cache(cache)

    count = sum(1 for _ in open(OUTPUT_FILE, encoding="utf-8"))
    print(f"\n下载列表已保存到: {OUTPUT_FILE}")
    print(f"共 {count} 个视频")