import re
import sys
from pathlib import Path
from typing import Optional, Dict, List

import requests
from tqdm import tqdm

"""
脚本功能：
1. 遍历 BASE_PATH 下的所有子文件夹，文件夹名视为 Tik.Porn 用户名 user_name
2. 访问 https://tik.porn/{user_name}，从
     <link rel="preload" href="https://image-cdn.tik.porn/user/893/893776/avatar.jpg" ...>
   中提取用户 id（示例中为 893776）
3. 使用接口：
   https://apiv2.tik.porn/getprofilerelatedvideos?type=user&id={id}&offset={offset}
   分页获取视频列表（每次 offset 增加 30）
4. 对于每个视频，如果目标目录中不存在同名文件（filename），
   则使用 download_url 下载并保存为 filename
"""

from all_path import PORN_ONLYFANS as BASE_PATH

# 确保 BASE_PATH 存在
BASE_PATH.mkdir(parents=True, exist_ok=True)

# 通用请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
}

API_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json",
    "Origin": "https://tik.porn",
}


def get_user_id_from_html(session: requests.Session, username: str) -> Optional[int]:
    """
    从 https://tik.porn/{username} 的 HTML 中解析 user id

    目标标签示例：
        <link rel="preload"
              href="https://image-cdn.tik.porn/user/893/893776/avatar.jpg"
              as="image" data-next-head="">

    其中 id 为最后的数字 893776
    """
    if '#' in username:
        username = username.split('#')[0].strip()
    url = f"https://tik.porn/{username}"
    print(f"  获取用户页面: {url}")
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # 匹配 avatar 链接，提取第二段数字（id）
        # 兼容：
        #   https://image-cdn.tik.porn/user/893/893776/avatar.jpg
        #   https://image-cdn.tik.porn/user/1211/1211961/avatar.jpg?ver=1
        pattern = (
            r'href="https://image-cdn\.tik\.porn/user/\d+/(\d+)/avatar\.jpg(?:\?[^"]*)?"'
        )
        m = re.search(pattern, html)
        if not m:
            print("    未找到 avatar 链接，无法解析用户 id")
            return None

        user_id_str = m.group(1)
        try:
            user_id = int(user_id_str)
        except ValueError:
            print(f"    解析 id 失败: {user_id_str}")
            return None

        print(f"    解析到用户 id: {user_id}")
        return user_id
    except Exception as e:
        print(f"    获取用户页面失败: {e}")
        return None


def fetch_videos_page(session: requests.Session, user_id: int, offset: int) -> Optional[Dict]:
    """获取指定用户在给定 offset 的视频列表"""
    url = (
        f"https://apiv2.tik.porn/getprofilerelatedvideos"
        f"?type=user&id={user_id}&offset={offset}"
    )
    print(f"  请求 API: id={user_id}, offset={offset}")
    try:
        resp = session.get(url, headers=API_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as e:
        print(f"    获取视频列表失败: {e}")
        return None


def download_file(session: requests.Session, url: str, filepath: Path, referer: str) -> bool:
    """下载文件到指定路径（带进度条和临时文件）"""
    if filepath.exists():
        return True

    temp_filepath = filepath.with_suffix(filepath.suffix + ".tmp")
    if temp_filepath.exists():
        temp_filepath.unlink()

    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "*/*",
        "Referer": referer,
        "Origin": "https://tik.porn",
    }

    try:
        print(f"    开始下载: {filepath.name}")
        resp = session.get(url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()

        total_size = int(resp.headers.get("Content-Length", 0))
        filepath.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        block_size = 8192

        with open(temp_filepath, "wb") as f:
            with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=filepath.name,
                leave=False,
            ) as pbar:
                for chunk in resp.iter_content(block_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    pbar.update(len(chunk))

        if total_size > 0 and downloaded != total_size:
            print(f"    下载不完整: {downloaded}/{total_size} bytes")
            temp_filepath.unlink()
            return False

        temp_filepath.rename(filepath)
        print(f"    ✓ 下载完成: {filepath.name}")
        return True
    except Exception as e:
        print(f"    下载失败: {filepath.name} - {e}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False


def process_user(session: requests.Session, username: str, folder_name: str, mode: str = "quick") -> None:
    """处理单个用户：先获取全部视频信息，再统一下载未存在的文件"""
    print(f"\n{'=' * 60}")
    print(f"处理用户: {username} (模式: {mode})")
    print(f"{'=' * 60}")

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    # 解析用户 id
    user_id = get_user_id_from_html(session, username)
    if user_id is None:
        print(f"  无法获取用户 id，跳过用户: {username}")
        return

    # ========= 第一阶段：获取视频信息（边取边检查，全存在则停止）=========
    print("\n第一阶段：获取视频信息...")
    pending: List[Dict] = []
    offset = 0
    page_size = 30
    total_fetched = 0

    referer = f"https://tik.porn/{username}"

    while True:
        data = fetch_videos_page(session, user_id, offset)
        if not data or data.get("code") != 200:
            print(
                f"  没有更多数据或请求失败，code="
                f"{data.get('code') if isinstance(data, dict) else 'N/A'}"
            )
            break

        videos = (
            data.get("data", {})
            .get("videos", {})
            .get("content", [])
        )

        if not videos:
            print("  本页无视频内容，结束")
            break

        page_new = 0
        page_existing = 0
        for video in videos:
            filename = video.get("filename")
            download_url = video.get("download_url")
            if not filename or not download_url:
                continue
            total_fetched += 1
            if (user_dir / filename).exists():
                page_existing += 1
            else:
                page_new += 1
                pending.append({"filename": filename, "download_url": download_url})

        print(f"  本页 {len(videos)} 个（新 {page_new}，已存在 {page_existing}）")

        # 本页全部已存在且为 quick 模式 → 停止翻页
        if mode == "quick" and page_new == 0 and page_existing > 0:
            print(f"  本页全部已存在，停止翻页")
            break

        offset += page_size

    print(f"\n  接口共返回 {total_fetched} 个视频，待下载 {len(pending)} 个")

    # ========= 第二阶段：下载未存在的视频 =========
    if not pending:
        print("  无新视频需要下载")
        print(f"\n用户 {username} 处理完成:\n  总视频数(接口返回): {total_fetched}\n  全部已存在")
        return

    print(f"\n第二阶段：开始下载 {len(pending)} 个新视频...")
    downloaded = 0
    failed = 0

    for idx, info in enumerate(pending, 1):
        filename = info["filename"]
        download_url = info["download_url"]
        filepath = user_dir / filename

        print(f"  [{idx}/{len(pending)}] {filename}")
        if download_file(session, download_url, filepath, referer):
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
        if f.is_dir() and f.name.endswith('@tikporn'):
            folder_name = f.name
            username = folder_name[:-len('@tikporn')]
            users.append((username, folder_name))

    if not users:
        print("BASE_PATH 下没有找到 @tikporn 子文件夹")
        return

    print(f"找到 {len(users)} 个 @tikporn 用户: {', '.join(u[0] for u in users)}")

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
