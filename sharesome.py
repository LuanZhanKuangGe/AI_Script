from pathlib import Path
import platform
import sys
from typing import Optional

import requests

try:
    from tqdm import tqdm
except Exception:
    tqdm = None


def _progress_bar(total: Optional[int], desc: str, unit: str):
    if tqdm:
        return tqdm(total=total, desc=desc, unit=unit, unit_scale=True, unit_divisor=1024, leave=False)
    return SimpleBar(total=total, desc=desc, unit=unit)


class ProgressProtocol:
    def update(self, value: int) -> None: ...
    def close(self) -> None: ...


class SimpleBar:
    def __init__(self, total: Optional[int], desc: str, unit: str) -> None:
        self.total = total
        self.desc = desc
        self.unit = unit
        self.current = 0

    def update(self, value: int) -> None:
        self.current += value
        if self.total:
            pct = (self.current / self.total) * 100
            sys.stdout.write(f"\r{self.desc}: {self.current}/{self.total} {self.unit} ({pct:.1f}%)")
        else:
            sys.stdout.write(f"\r{self.desc}: {self.current} {self.unit}")
        sys.stdout.flush()

    def close(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()


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


def iter_videos(session: requests.Session, user_id: int):
    """迭代获取用户的所有视频"""
    page = 1
    while True:
        api_url = f"https://sharesome.com/api/videos?user={user_id}&limit=12&page={page}"
        try:
            resp = session.get(api_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") != "true" or "data" not in data:
                break
            videos = data["data"]
            if not videos:
                break
            yield from videos
            # 检查是否有下一页
            paginator = data.get("paginator", {})
            if not paginator.get("next_page_url"):
                break
            page += 1
        except Exception as exc:
            print(f"[user_id={user_id}] 获取第 {page} 页视频失败: {exc}")
            break


def download_video(session: requests.Session, mp4_url: str, file_path: Path, overall_bar: ProgressProtocol,
                   max_retries: int = 3) -> None:
    """下载视频，使用临时文件确保下载中断时不会创建文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(file_path.name + ".part")

    if file_path.exists():
        overall_bar.update(1)
        return

    # 确保 mp4_url 是完整的 URL
    if mp4_url.startswith("//"):
        mp4_url = "https:" + mp4_url
    elif not mp4_url.startswith("http"):
        mp4_url = "https://" + mp4_url

    for attempt in range(1, max_retries + 1):
        resume_pos = tmp_path.stat().st_size if tmp_path.exists() else 0
        headers = {"Range": f"bytes={resume_pos}-"} if resume_pos else None
        try:
            with session.get(mp4_url, stream=True, timeout=30, headers=headers) as resp:
                if resp.status_code == 416:
                    tmp_path.rename(file_path)
                    print(f"完成: {file_path.name}")
                    overall_bar.update(1)
                    return
                resp.raise_for_status()
                total = resp.headers.get("Content-Length")
                if total is not None:
                    total_size = int(total) + resume_pos
                else:
                    total_size = None
                bar = _progress_bar(total_size, desc=file_path.name, unit="B")
                mode = "ab" if resume_pos else "wb"
                written = resume_pos
                with open(tmp_path, mode) as fh:
                    if resume_pos:
                        bar.update(resume_pos)
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        written += len(chunk)
                        bar.update(len(chunk))
                bar.close()
                tmp_path.rename(file_path)
                print(f"完成: {file_path.name}")
                overall_bar.update(1)
                return
        except Exception as exc:
            print(f"下载失败({attempt}/{max_retries}): {file_path.name} - {exc}")
            if attempt == max_retries:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
    overall_bar.update(1)


if platform.system() == "Windows":
    BASE_PATH = Path(r"D:\Porn-Web\sharesome")
else:
    BASE_PATH = Path(r"/data/Porn-Web/sharesome")

session = requests.Session()

for folder in BASE_PATH.iterdir():
    if not folder.is_dir():
        continue
    username = folder.name
    print(f"开始处理: {username}")
    
    # 获取用户 id
    user_id = get_user_id(session, username)
    if not user_id:
        print(f"[{username}] 无法获取用户 id，跳过")
        continue
    
    # 收集需要下载的视频
    video_tasks = []
    for video in iter_videos(session, user_id):
        if video.get("sound") == 1:
            mp4_url = video.get("mp4_url")
            if not mp4_url:
                continue
            # 使用 obj_id 或 id 作为文件名
            video_id = video.get("obj_id") or video.get("id", "unknown")
            filename = f"{video_id}.MP4"
            file_path = folder / filename
            video_tasks.append((mp4_url, file_path))
    
    total_files = len(video_tasks)
    if not total_files:
        print(f"[{username}] 无可下载视频")
        continue
    
    print(f"[{username}] 找到 {total_files} 个视频需要下载")
    overall = _progress_bar(total_files, desc=f"{username} 总进度", unit="file")
    for mp4_url, file_path in video_tasks:
        download_video(session, mp4_url, file_path, overall)
    overall.close()
