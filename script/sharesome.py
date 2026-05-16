from pathlib import Path
import sys
from typing import Optional, List, Tuple

import requests

try:
    from tqdm import tqdm
except Exception:
    tqdm = None




def get_user_id(session: requests.Session, username: str) -> Optional[int]:
    """获取用户的 id"""
    if '#' in username:
        username = username.split('#')[0].strip()
    api_url = f"https://sharesome.com/api/users/{username}"
    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") == "true" and "data" in data:
            return data["data"].get("id")
    except Exception as exc:
        print(f"[{username}] 获取用户信息失败: {exc}")
    return None


def fetch_videos_page(session: requests.Session, user_id: int, page: int = 1) -> Tuple[list, Optional[str]]:
    """获取一页视频数据，返回 (videos列表, next_page_url)"""
    api_url = f"https://sharesome.com/api/videos?user={user_id}&limit=12&page={page}"
    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") != "true" or "data" not in data:
            return [], None
        videos = data["data"]
        paginator = data.get("paginator", {})
        next_url = paginator.get("next_page_url")
        return videos, next_url
    except Exception as exc:
        print(f"[user_id={user_id}] 获取第 {page} 页视频失败: {exc}")
        return [], None


def download_file(session: requests.Session, url: str, filepath: Path, referer: str = "",
                  max_retries: int = 3) -> bool:
    if filepath.exists():
        return True
    tmp = filepath.with_suffix(filepath.suffix + '.tmp')
    if tmp.exists():
        tmp.unlink()

    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http"):
        url = "https://" + url

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get('Content-Length', 0))
            filepath.parent.mkdir(parents=True, exist_ok=True)
            downloaded = 0
            with open(tmp, 'wb') as f:
                with tqdm(total=total, unit='B', unit_scale=True, desc=filepath.name, leave=False) as pbar:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pbar.update(len(chunk))
            if total > 0 and downloaded != total:
                print(f"    下载不完整: {downloaded}/{total}")
                tmp.unlink()
                if attempt == max_retries:
                    return False
                continue
            tmp.rename(filepath)
            print(f"    ✓ 下载完成: {filepath.name}")
            return True
        except Exception as e:
            print(f"    下载失败({attempt}/{max_retries}): {filepath.name} - {e}")
            if tmp.exists():
                tmp.unlink()
            if attempt == max_retries:
                return False


from all_path import PORN_ONLYFANS as BASE_PATH


def process_user(session: requests.Session, username: str, folder_name: str, mode: str = "quick") -> None:
    print(f"\n{'=' * 60}")
    print(f"处理用户: {username} (模式: {mode})")
    print(f"{'=' * 60}")

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    user_id = get_user_id(session, username)
    if not user_id:
        print(f"[{username}] 无法获取用户 id，跳过")
        return

    print(f"\n获取视频信息...")
    pending: List[Tuple[str, Path]] = []
    page = 1
    total_fetched = 0

    while True:
        videos, next_url = fetch_videos_page(session, user_id, page)
        if not videos:
            print(f"  完成（共 {page - 1} 页）")
            break

        page_new = 0
        page_existing = 0
        for video in videos:
            if video.get("sound") != 1:
                continue
            mp4_url = video.get("mp4_url")
            if not mp4_url:
                continue
            video_id = video.get("obj_id") or video.get("id", "unknown")
            filename = f"{video_id}.MP4"
            filepath = user_dir / filename
            total_fetched += 1
            if filepath.exists():
                page_existing += 1
            else:
                page_new += 1
                pending.append((mp4_url, filepath))

        print(f"  第 {page} 页: {len(videos)} 个（新 {page_new}，已存在 {page_existing}）")

        if mode == "quick" and page_new == 0 and page_existing > 0:
            print(f"  本页全部已存在，停止翻页")
            break

        if not next_url:
            break
        page += 1

    print(f"\n  共获取到 {total_fetched} 个视频，待下载 {len(pending)} 个")

    if not pending:
        print("  无新视频需要下载")
        return

    print(f"\n开始下载 {len(pending)} 个新视频...")
    downloaded = 0
    failed = 0

    for idx, (mp4_url, filepath) in enumerate(pending, 1):
        print(f"  [{idx}/{len(pending)}] {filepath.name}")
        if download_file(session, mp4_url, filepath):
            downloaded += 1
        else:
            failed += 1

    print(f"\n用户 {username} 处理完成:")
    print(f"  总视频数(接口返回): {total_fetched}")
    print(f"  下载成功: {downloaded}")
    print(f"  下载失败: {failed}")


def main():
    print(f"BASE_PATH: {BASE_PATH}")

    if not BASE_PATH.exists():
        print(f"BASE_PATH 不存在: {BASE_PATH}")
        return

    users = []
    for f in BASE_PATH.iterdir():
        if f.is_dir() and f.name.endswith('@sharesome'):
            folder_name = f.name
            username = folder_name[:-len('@sharesome')]
            users.append((username, folder_name))

    if not users:
        print("BASE_PATH 下没有找到 @sharesome 子文件夹")
        return

    print(f"找到 {len(users)} 个 @sharesome 用户: {', '.join(u[0] for u in users)}")

    download_mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick") else "quick"

    session = requests.Session()

    for username, folder_name in users:
        try:
            process_user(session, username, folder_name, download_mode)
        except Exception as e:
            print(f"处理用户 {username} 时发生错误: {e}")
            continue

    print(f"\n{'=' * 60}")
    print("所有用户处理完成！")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
