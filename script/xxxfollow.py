from pathlib import Path
import platform
import sys
from typing import Iterable, List, Optional, Tuple

import requests

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - tqdm may not exist in env
    tqdm = None


def iter_posts(target: str) -> Iterable[dict]:
    page = 1
    while True:
        if '#' in target:
            target = target.split('#')[0].strip()
        api_url = f"https://www.xxxfollow.com/api/v1/user/{target}/post/public?limit=20&sort_by=likes&page={page}"
        try:
            resp = requests.get(api_url, timeout=15)
        except Exception as exc:
            print(f"[{target}] 请求第 {page} 页失败: {exc}")
            return
        if resp.status_code != 200:
            print(f"[{target}] 第 {page} 页返回 {resp.status_code}")
            return
        try:
            data = resp.json()
        except Exception as exc:
            print(f"[{target}] 第 {page} 页 JSON 解析失败: {exc}")
            return
        if not data:
            return
        yield from data
        page += 1


def collect_media(target: str, base_path: Path) -> List[Tuple[str, Path]]:
    url_pairs: List[Tuple[str, Path]] = []
    for entry in iter_posts(target):
        media_list = entry.get("post", {}).get("media") or []
        if not media_list:
            continue
        media = media_list[0]
        url = media.get("fhd_url") or media.get("sd_url")
        if not url:
            continue
        filename = url.split("/")[-1]
        file_path = base_path / target / filename
        url_pairs.append((url, file_path))
    return url_pairs


def _progress_bar(total: Optional[int], desc: str, unit: str) -> "ProgressProtocol":
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


def download_with_resume(session: requests.Session, url: str, file_path: Path, overall_bar: ProgressProtocol,
                         max_retries: int = 3) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_name(file_path.name + ".part")

    if file_path.exists():
        # print(f"已存在: {file_path}")
        overall_bar.update(1)
        return

    for attempt in range(1, max_retries + 1):
        resume_pos = tmp_path.stat().st_size if tmp_path.exists() else 0
        headers = {"Range": f"bytes={resume_pos}-"} if resume_pos else None
        try:
            with session.get(url, stream=True, timeout=30, headers=headers) as resp:
                if resp.status_code == 416:
                    tmp_path.rename(file_path)
                    print(f"完成: {file_path}")
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
                print(f"完成: {file_path}")
                overall_bar.update(1)
                return
        except Exception as exc:
            print(f"下载失败({attempt}/{max_retries}): {url} - {exc}")
            if attempt == max_retries:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
    overall_bar.update(1)


if platform.system() == "Windows":
    BASE_PATH = Path(r"D:\Porn-Web\xxxfollow")
else:
    BASE_PATH = Path(r"/data/Porn-Web/xxxfollow")

session = requests.Session()

for folder in BASE_PATH.iterdir():
    if not folder.is_dir():
        continue
    target_name = folder.name
    print(f"开始处理: {target_name}")
    media_tasks = collect_media(target_name, BASE_PATH)
    total_files = len(media_tasks)
    if not total_files:
        print(f"[{target_name}] 无可下载媒体")
        continue

    overall = _progress_bar(total_files, desc=f"{target_name} 总进度", unit="file")
    for media_url, media_path in media_tasks:
        download_with_resume(session, media_url, media_path, overall)
    overall.close()