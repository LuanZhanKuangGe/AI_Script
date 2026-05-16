from pathlib import Path
import sys
import time
from typing import Iterable, List, Optional, Tuple

import requests

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - tqdm may not exist in env
    tqdm = None


def iter_posts(target: str, mode: str = "full", base_path: Path = None, target_dir: Optional[Path] = None) -> Iterable[dict]:
    if mode == "quick":
        yield from iter_posts_quick(target, base_path, target_dir)
    else:
        yield from iter_posts_full(target)


def iter_posts_full(target: str) -> Iterable[dict]:
    api_target = target.split('#')[0].strip() if '#' in target else target
    page = 1
    while True:
        api_url = f"https://www.xxxfollow.com/api/v1/user/{api_target}/post/public?limit=20&sort_by=recent&page={page}"
        try:
            resp = requests.get(api_url, timeout=15)
        except Exception as exc:
            print(f"[{api_target}] 请求第 {page} 页失败: {exc}，跳过")
            return
        if resp.status_code != 200:
            print(f"[{api_target}] 第 {page} 页返回 {resp.status_code}，跳过")
            return
        try:
            data = resp.json()
        except Exception as exc:
            print(f"[{api_target}] 第 {page} 页 JSON 解析失败: {exc}")
            return
        if not data:
            return
        yield from data
        page += 1


def iter_posts_quick(target: str, base_path: Path, target_dir: Optional[Path] = None) -> Iterable[dict]:
    api_target = target.split('#')[0].strip() if '#' in target else target
    page = 1
    while True:
        api_url = f"https://www.xxxfollow.com/api/v1/user/{api_target}/post/public?limit=20&sort_by=recent&page={page}"
        try:
            resp = requests.get(api_url, timeout=15)
        except Exception as exc:
            print(f"[{api_target}] 请求第 {page} 页失败: {exc}，跳过")
            return
        if resp.status_code != 200:
            print(f"[{api_target}] 第 {page} 页返回 {resp.status_code}，跳过")
            return
        try:
            data = resp.json()
        except Exception as exc:
            print(f"[{api_target}] 第 {page} 页 JSON 解析失败: {exc}")
            return
        if not data:
            return

        if target_dir is None:
            target_dir = base_path / target
        target_dir.mkdir(parents=True, exist_ok=True)
        has_new = False
        for entry in data:
            media_list = entry.get("post", {}).get("media") or []
            if not media_list:
                continue
            media = media_list[0]
            url = media.get("fhd_url") or media.get("sd_url")
            if not url:
                continue
            filename = url.split("/")[-1]
            file_path = target_dir / filename
            if not file_path.exists():
                has_new = True
                yield entry
        if not has_new:
            print(f"[{api_target}] 第 {page} 页没有新视频，停止")
            return
        page += 1


def collect_media(target: str, base_path: Path, mode: str = "full", target_dir: Optional[Path] = None) -> List[Tuple[str, Path]]:
    url_pairs: List[Tuple[str, Path]] = []
    if target_dir is None:
        target_dir = base_path / target
    for entry in iter_posts(target, mode, base_path, target_dir):
        media_list = entry.get("post", {}).get("media") or []
        if not media_list:
            continue
        media = media_list[0]
        url = media.get("fhd_url") or media.get("sd_url")
        if not url:
            continue
        filename = url.split("/")[-1]
        file_path = target_dir / filename
        if not file_path.exists():
            url_pairs.append((url, file_path))
    return url_pairs



def download_file(session: requests.Session, url: str, filepath: Path) -> bool:
    if filepath.exists():
        return True
    tmp = filepath.with_suffix(filepath.suffix + '.tmp')
    if tmp.exists():
        tmp.unlink()

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
            return False
        tmp.rename(filepath)
        print(f"    ✓ 下载完成: {filepath.name}")
        return True
    except Exception as e:
        print(f"    下载失败: {filepath.name} - {e}")
        if tmp.exists():
            tmp.unlink()
        return False


from all_path import PORN_ONLYFANS as BASE_PATH


def process_user(session: requests.Session, username: str, folder_name: str, mode: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"处理用户: {username} (模式: {mode})")
    print(f"{'=' * 60}")

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    media_tasks = collect_media(username, BASE_PATH, mode, target_dir=user_dir)

    if not media_tasks:
        print(f"[{username}] 无可下载媒体")
        return

    print(f"\n开始下载 {len(media_tasks)} 个新视频...")
    downloaded = 0
    failed = 0
    for idx, (media_url, media_path) in enumerate(media_tasks, 1):
        print(f"  [{idx}/{len(media_tasks)}] {media_path.name}")
        if download_file(session, media_url, media_path):
            downloaded += 1
        else:
            failed += 1

    print(f"用户 {username} 处理完成: 成功 {downloaded}, 失败 {failed}")


def main():
    print(f"BASE_PATH: {BASE_PATH}")

    if not BASE_PATH.exists():
        print(f"BASE_PATH 不存在: {BASE_PATH}")
        return

    users = []
    for f in BASE_PATH.iterdir():
        if f.is_dir() and f.name.endswith('@xxxfollow'):
            folder_name = f.name
            username = folder_name[:-len('@xxxfollow')]
            users.append((username, folder_name))

    if not users:
        print("BASE_PATH 下没有找到 @xxxfollow 子文件夹")
        return

    print(f"找到 {len(users)} 个 @xxxfollow 用户: {', '.join(u[0] for u in users)}")

    download_mode = "quick"
    if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick"):
        download_mode = sys.argv[1]

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