import re
import json
import requests
from pathlib import Path
from typing import Optional, Dict, List
from tqdm import tqdm
import platform
from urllib.parse import urlparse

try:
    from lxml import html
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
    print("警告: 未安装 lxml，将使用正则表达式解析 HTML")

# 设置 BASE_PATH
if platform.system() == "Windows":
    BASE_PATH = Path(r"D:\Porn-Web\waptap")
else:
    BASE_PATH = Path(r"/data/Porn-Web/waptap")

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


def process_user(session: requests.Session, username: str) -> None:
    """处理单个用户的所有媒体
    
    分为两个阶段：
    1. 获取用户所有视频信息
    2. 统一批量下载所有视频
    """
    print(f"\n{'='*60}")
    print(f"处理用户: {username}")
    print(f"{'='*60}")
    
    # 获取用户 ID
    user_id = get_user_id_from_html(session, username)
    if not user_id:
        print(f"  无法获取用户 ID，跳过用户: {username}")
        return
    
    # 创建用户目录
    user_dir = BASE_PATH / username
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # ========== 第一阶段：获取所有视频信息 ==========
    print(f"\n第一阶段：获取所有视频信息...")
    all_videos = []
    page = 1
    
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
        
        # 过滤并收集视频信息
        for item in items:
            # 只处理 is_adult 为 true 的项
            if not item.get('is_adult', False):
                continue
            
            # 获取文件 URL
            file_url = item.get('file')
            if not file_url:
                continue
            
            # 生成文件名（使用 _id 或 hash）
            file_id = item.get('_id', '')
            file_hash = item.get('hash', '')
            
            # 从 URL 中提取文件扩展名（去除查询参数）
            parsed_url = urlparse(file_url)
            file_extension = Path(parsed_url.path).suffix or '.mp4'
            
            if file_id:
                filename = f"{file_id}{file_extension}"
            elif file_hash:
                filename = f"{file_hash}{file_extension}"
            else:
                # 从 URL 路径中提取文件名
                filename = Path(parsed_url.path).name
                if not filename:
                    # 如果还是提取不到，使用 _id 或 hash 作为备用
                    filename = f"{file_id or file_hash or 'unknown'}{file_extension}"
            
            filepath = user_dir / filename
            
            # 保存视频信息（包含文件路径、URL等）
            all_videos.append({
                'file_url': file_url,
                'filepath': filepath,
                'filename': filename,
            })
        
        print(f"获取到 {len(items)} 个媒体项")
        page += 1
    
    print(f"\n  共获取到 {len(all_videos)} 个视频")
    
    # ========== 第二阶段：统一批量下载 ==========
    print(f"\n第二阶段：开始批量下载...")
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0
    
    referer = f"https://waptap.com/{username}"
    
    for idx, video_info in enumerate(all_videos, 1):
        file_url = video_info['file_url']
        filepath = video_info['filepath']
        filename = video_info['filename']
        
        # 检查文件是否已存在
        if filepath.exists():
            total_skipped += 1
            continue
        
        print(f"  [{idx}/{len(all_videos)}] {filename}")
        if download_file(session, file_url, filepath, referer):
            total_downloaded += 1
        else:
            total_failed += 1
    
    # 输出统计信息
    print(f"\n用户 {username} 处理完成:")
    print(f"  总视频数: {len(all_videos)} 个")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  已跳过: {total_skipped} 个")
    print(f"  下载失败: {total_failed} 个")


def main():
    """主函数"""
    print(f"BASE_PATH: {BASE_PATH}")
    
    # 获取所有子文件夹名作为用户名
    if not BASE_PATH.exists():
        print(f"BASE_PATH 不存在: {BASE_PATH}")
        return
    
    # 获取所有子文件夹
    users = [f.name for f in BASE_PATH.iterdir() if f.is_dir()]
    
    if not users:
        print(f"BASE_PATH 下没有找到子文件夹")
        return
    
    print(f"找到 {len(users)} 个用户文件夹: {', '.join(users)}")
    
    # 创建会话
    session = requests.Session()
    
    # 处理每个用户
    for username in users:
        try:
            process_user(session, username)
        except Exception as e:
            print(f"处理用户 {username} 时发生错误: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("所有用户处理完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
