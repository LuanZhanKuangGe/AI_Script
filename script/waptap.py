import re
import json
import sys
import requests
from pathlib import Path
from typing import Optional, Dict, List
from tqdm import tqdm
from urllib.parse import urlparse

try:
    from lxml import html
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
    print("警告: 未安装 lxml，将使用正则表达式解析 HTML")

from all_path import PORN_ONLYFANS as BASE_PATH

# 确保 BASE_PATH 存在
BASE_PATH.mkdir(parents=True, exist_ok=True)

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
    'Accept': 'application/json',
    'Referer': 'https://waptap.com/',
    'Origin': 'https://waptap.com',
}


def get_user_id_from_html(session: requests.Session, username: str) -> Optional[str]:
    """通过官方 API 获取用户 ID

    使用接口:
        https://api.waptap.com/v1/user/share/{username}

    返回 JSON 示例:
        {
          "code": 200,
          "status": "OK",
          "uuid": "...",
          "data": {
            "_id": "68a6a080d28960fc4e0ede35",
            ...
          }
        }

    成功时返回字符串形式的用户 _id，失败时返回 None
    """
    if '#' in username:
        username = username.split('#')[0].strip()
    url = f"https://api.waptap.com/v1/user/share/{username}"
    try:
        print(f"正在通过 API 获取用户 ID: {username}")
        response = session.get(url, headers=API_HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 200:
            print(f"  API 返回异常 code: {data.get('code')}, status: {data.get('status')}")
            return None

        user_data = data.get("data") or {}
        user_id = user_data.get("_id")

        if user_id:
            print(f"  获取到用户 ID: {user_id}")
            return user_id

        print("  API 返回中未找到 _id 字段")
        return None

    except Exception as e:
        print(f"  通过 API 获取用户 ID 失败: {e}")
        return None


def fetch_media_page(session: requests.Session, user_id: str, page: int = 1) -> Optional[Dict]:
    """获取指定页面的媒体数据"""
    url = f"https://api.waptap.com/v1/user/{user_id}/media?page={page}"
    try:
        response = session.get(url, headers=API_HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"  获取第 {page} 页数据失败: {e}")
        return None


def download_file(session: requests.Session, url: str, filepath: Path, referer: str = "https://waptap.com/") -> bool:
    """下载文件，使用临时文件确保中断时不会保存不完整文件"""
    # 如果文件已存在，跳过
    if filepath.exists():
        return True
    
    # 使用临时文件名
    temp_filepath = filepath.with_suffix(filepath.suffix + '.tmp')
    
    # 如果临时文件存在，删除它（可能是之前中断的下载）
    if temp_filepath.exists():
        temp_filepath.unlink()
    
    try:
        # 设置下载请求头
        download_headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': referer,
            'Origin': referer.rstrip('/'),
        }
        
        print(f"    开始下载: {filepath.name}")
        response = session.get(url, stream=True, headers=download_headers, timeout=60)
        response.raise_for_status()
        
        # 获取文件总大小
        total_size = int(response.headers.get('Content-Length', 0))
        
        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 下载到临时文件
        downloaded_size = 0
        block_size = 8192  # 8KB 块大小
        
        with open(temp_filepath, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=filepath.name, leave=False) as pbar:
                for chunk in response.iter_content(block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        pbar.update(len(chunk))
        
        # 验证下载完整性
        if total_size > 0 and downloaded_size != total_size:
            print(f"    下载不完整: {downloaded_size}/{total_size} bytes")
            temp_filepath.unlink()
            return False
        
        # 下载成功，重命名为最终文件
        temp_filepath.rename(filepath)
        print(f"    ✓ 下载完成: {filepath.name}")
        return True
        
    except requests.exceptions.Timeout:
        print(f"    下载超时: {filepath.name}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False
    except requests.exceptions.RequestException as e:
        print(f"    下载失败: {filepath.name} - {e}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False
    except Exception as e:
        print(f"    下载异常: {filepath.name} - {e}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False


def process_user(session: requests.Session, username: str, folder_name: str, mode: str = "quick") -> None:
    print(f"\n{'='*60}")
    print(f"处理用户: {username} (模式: {mode})")
    print(f"{'='*60}")

    user_id = get_user_id_from_html(session, username)
    if not user_id:
        print(f"  无法获取用户 ID，跳过用户: {username}")
        return

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n获取视频信息...")
    pending: List[Dict] = []
    page = 1
    total_fetched = 0
    referer = f"https://waptap.com/{username}"

    while True:
        print(f"  获取第 {page} 页数据...", end=' ')
        data = fetch_media_page(session, user_id, page)

        if not data or data.get('code') != 200:
            print(f"完成（共 {page - 1} 页）")
            break

        items = data.get('data', {}).get('items', [])
        if not items:
            print(f"完成（共 {page - 1} 页）")
            break

        page_new = 0
        page_existing = 0
        for item in items:
            if not item.get('is_adult', False):
                page_existing += 1
                continue

            file_url = item.get('file')
            if not file_url:
                continue

            file_id = item.get('_id', '')
            file_hash = item.get('hash', '')
            parsed = urlparse(file_url)
            ext = Path(parsed.path).suffix or '.mp4'

            if file_id:
                filename = f"{file_id}{ext}"
            elif file_hash:
                filename = f"{file_hash}{ext}"
            else:
                filename = Path(parsed.path).name
                if not filename:
                    filename = f"{file_id or file_hash or 'unknown'}{ext}"

            filepath = user_dir / filename
            total_fetched += 1
            if filepath.exists():
                page_existing += 1
            else:
                page_new += 1
                pending.append({'file_url': file_url, 'filepath': filepath})

        print(f"{len(items)} 个（新 {page_new}，已存在 {page_existing}）")

        if mode == "quick" and page_new == 0 and page_existing > 0:
            print(f"  本页全部已存在，停止翻页")
            break

        page += 1

    print(f"\n  共获取到 {total_fetched} 个视频，待下载 {len(pending)} 个")

    if not pending:
        print("  无新视频需要下载")
        return

    print(f"\n开始下载 {len(pending)} 个新视频...")
    downloaded = 0
    failed = 0

    for idx, info in enumerate(pending, 1):
        print(f"  [{idx}/{len(pending)}] {info['filepath'].name}")
        if download_file(session, info['file_url'], info['filepath'], referer):
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
        if f.is_dir() and f.name.endswith('@waptap'):
            folder_name = f.name
            username = folder_name[:-len('@waptap')]
            users.append((username, folder_name))

    if not users:
        print(f"BASE_PATH 下没有找到 @waptap 子文件夹")
        return

    print(f"找到 {len(users)} 个 @waptap 用户: {', '.join(u[0] for u in users)}")

    download_mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("full", "quick") else "quick"

    session = requests.Session()

    for username, folder_name in users:
        try:
            process_user(session, username, folder_name, download_mode)
        except Exception as e:
            print(f"处理用户 {username} 时发生错误: {e}")
            continue

    print(f"\n{'='*60}")
    print("所有用户处理完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
