import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(r"D:\Hentai-MMD-new")
MIN_LIKES = 500

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


def crawl_artist(artist: str, folder: Path):
    existing_ids = get_existing_ids(folder)

    profile_data = request_with_retry(f"https://api.iwara.tv/profile/{artist}")
    if not profile_data:
        print(f"获取用户 {artist} 的资料失败")
        return []

    user_id = profile_data["user"]["id"]
    username = profile_data["user"]["username"]
    print(f"\n=== {username} ({artist}) 已有 {len(existing_ids)} 个视频，查找新视频 ===")

    all_videos = []
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
            all_videos.append({"id": video_id, "slug": slug, "title": title})

        count = data.get("count", 0)
        limit = data.get("limit", 50)
        if (page + 1) * limit >= count:
            break

        page += 1
        time.sleep(0.5)

    print(f"  跳过: 私有={skipped_private}, 非R18={skipped_non_r18}, 已有={skipped_existing}, 收藏<{MIN_LIKES}={skipped_likes}")

    if not all_videos:
        print("  无新视频")
        print(f"=== {artist}: 0 个新视频 ===")
        return []

    print(f"  发现 {len(all_videos)} 个新视频，解析下载地址...")

    download_list = []
    no_source = 0
    fail_info = 0
    for i, video in enumerate(all_videos, 1):
        vid = video["id"]
        title = video["title"]
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

        filename = sanitize_filename(f"Iwara - {title} [{vid}] [Source].mp4")
        download_list.append({"title": title, "id": vid, "filename": filename, "url": dl_info["url"]})

    print(f"\n=== {artist}: 可下载 {len(download_list)}, 无Source {no_source}, 解析失败 {fail_info} ===")

    return download_list


if __name__ == "__main__":
    if not login():
        sys.exit(1)

    artists = get_artist_folders()
    if not artists:
        print(f"在 {BASE_DIR} 下未找到 [artist] 格式的文件夹")
        sys.exit(1)

    print(f"找到 {len(artists)} 个 artist 文件夹")

    all_downloads = []
    for artist, folder in artists:
        result = crawl_artist(artist, folder)
        if result:
            all_downloads.extend(result)

    if all_downloads:
        output_file = Path(__file__).parent / "download_list.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            for item in all_downloads:
                f.write(f"{item['url']}/{item['filename']}\n")
        print(f"\n下载列表已保存到: {output_file}")
        print(f"共 {len(all_downloads)} 个视频")