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


def get_source_download(video_id: str):
    data = request_with_retry(f"https://api.iwara.tv/video/{video_id}")
    if not data:
        return None

    file_url = data.get("fileUrl")
    if not file_url:
        return None

    qualities = request_with_retry(file_url)
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


def sanitize_filename(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, '')
    return name.strip()


def download_video(dl_url: str, save_path: Path):
    save_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = save_path.with_suffix(save_path.suffix + '.tmp')

    dl_headers = {
        "User-Agent": API_HEADERS["User-Agent"],
        "Referer": "https://www.iwara.tv/",
    }

    try:
        resp = requests.get(dl_url, headers=dl_headers, stream=True, timeout=300)
        resp.raise_for_status()
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        last_print = 0
        with open(tmp_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total and (downloaded - last_print) >= 1024 * 1024:
                    print(f"\r  下载中: {downloaded / (1024*1024):.1f}/{total / (1024*1024):.1f} MB", end='', flush=True)
                    last_print = downloaded
        tmp_path.rename(save_path)
        print(f"\r  下载完成: {save_path.name} ({downloaded / (1024*1024):.1f} MB)")
        return True
    except Exception as e:
        print(f"\n  下载失败: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def crawl_artist(artist: str, folder: Path):
    existing_ids = get_existing_ids(folder)

    profile_data = request_with_retry(f"https://api.iwara.tv/profile/{artist}")
    if not profile_data:
        print(f"获取用户 {artist} 的资料失败")
        return

    user_id = profile_data["user"]["id"]
    username = profile_data["user"]["username"]
    print(f"\n=== {username} ({artist}) 已有 {len(existing_ids)} 个视频，查找新视频 ===")

    all_videos = []
    skipped_private = 0
    skipped_non_r18 = 0
    skipped_existing = 0
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

    print(f"  跳过: 私有={skipped_private}, 非R18={skipped_non_r18}, 已有={skipped_existing}")

    if not all_videos:
        print("  无新视频")
        print(f"=== {artist}: 0 个新视频 ===")
        return

    print(f"  发现 {len(all_videos)} 个新视频，开始下载...")

    success = 0
    no_source = 0
    for i, video in enumerate(all_videos, 1):
        vid = video["id"]
        title = video["title"]
        print(f"\n[{i}/{len(all_videos)}] {title} ({vid})")

        dl_info = get_source_download(vid)
        if not dl_info:
            print(f"  获取下载信息失败，跳过")
            time.sleep(0.5)
            continue

        if not dl_info["has_source"]:
            avail = ", ".join(dl_info["available"]) if dl_info["available"] else "无"
            print(f"  无 Source 品质 (可用: {avail})，跳过")
            no_source += 1
            time.sleep(0.5)
            continue

        filename = f"Iwara - {title} [{vid}] [Source].mp4"
        filename = sanitize_filename(filename)
        save_path = folder / filename

        if save_path.exists():
            print(f"  文件已存在，跳过")
            existing_ids.add(vid.lower())
            continue

        print(f"  下载 Source 品质: {filename}")
        if download_video(dl_info["url"], save_path):
            success += 1
        else:
            print(f"  下载失败: {title}")

        time.sleep(1)

    print(f"\n=== {artist}: 下载 {success}/{len(all_videos)}, 无Source {no_source} ===")


if __name__ == "__main__":
    artists = get_artist_folders()
    if not artists:
        print(f"在 {BASE_DIR} 下未找到 [artist] 格式的文件夹")
        sys.exit(1)

    print(f"找到 {len(artists)} 个 artist 文件夹")
    for artist, folder in artists:
        crawl_artist(artist, folder)