import json
import requests
from pathlib import Path
from tqdm import tqdm
import platform


def download_video(url, ref, filename):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': ref,
            'Origin': ref
        }

        print(f"开始下载: {url}")
        response = requests.get(url, stream=True, headers=headers, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('Content-Length', 0))
        print(f"文件大小: {total_size} bytes")

        block_size = 1024
        progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True)
        custom_string = f"{filename.name}"
        progress_bar.set_description(custom_string)

        with open(filename, 'wb') as f:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                f.write(data)

        progress_bar.close()
        
        if total_size != 0 and progress_bar.n != total_size:
            print(f"下载不完整: {progress_bar.n}/{total_size}")
            return 0
        
        print(f"下载完成: {filename.name}")
        return 1
        
    except requests.exceptions.Timeout:
        print(f"下载超时: {url}")
        return 0
    except requests.exceptions.ConnectionError:
        print(f"连接错误: {url}")
        return 0
    except Exception as e:
        print(f"下载失败: {url}, 错误: {e}")
        return 0

if platform.system() == "Windows":
    DOWNLOAD_PATH = Path(r"D:\Porn-Web\onlytik")
else:
    DOWNLOAD_PATH = Path(r"/data/Porn-Web/onlytik")

# API 基础 URL
BASE_API_URL = "https://onlytik.com/api/user"
# 用户 ID
USER_ID = "onlytik"
# 初始 offset
INITIAL_OFFSET = 0
# offset 增量
OFFSET_INCREMENT = 10

def fetch_user_data(user_id: str, offset: int) -> dict:
    """
    获取用户数据
    
    参数:
    user_id: 用户 ID
    offset: 偏移量
    
    返回:
    包含用户数据的字典，如果请求失败或数据为空则返回 None
    """
    url = f"{BASE_API_URL}?id={user_id}&offset={offset}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # 检查是否有视频数据
        if 'videos' in data and len(data.get('videos', [])) > 0:
            return data
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求失败 (offset={offset}): {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败 (offset={offset}): {e}")
        return None

def download_all_videos(user_id: str):
    """
    下载指定用户的所有视频
    
    参数:
    user_id: 用户 ID
    """
    # 创建下载目录
    DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
    
    offset = INITIAL_OFFSET
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0
    
    print(f"开始爬取用户 {user_id} 的视频...")
    print(f"下载目录: {DOWNLOAD_PATH}")
    print("-" * 50)
    
    while True:
        print(f"\n正在获取 offset={offset} 的数据...")
        data = fetch_user_data(user_id, offset)
        
        if data is None:
            print(f"offset={offset} 没有更多数据，爬取结束")
            break
        
        videos = data.get('videos', [])
        if not videos:
            print(f"offset={offset} 视频列表为空，爬取结束")
            break
        
        print(f"找到 {len(videos)} 个视频")
        
        # 下载每个视频
        for idx, video in enumerate(videos, 1):
            video_id = video.get('video_id', '')
            video_url = video.get('url', '')
            username = video.get('username', user_id)
            
            if not video_url:
                print(f"  跳过: video_id={video_id} (无视频URL)")
                continue
            
            # 生成文件名：使用 video_id 作为文件名
            filename = DOWNLOAD_PATH / f"{video_id}.mp4"
            
            # 检查文件是否已存在
            if filename.exists():
                print(f"  跳过 [{idx}/{len(videos)}]: {video_id}.mp4 (已存在)")
                total_skipped += 1
                continue
            
            # 下载视频
            print(f"  下载 [{idx}/{len(videos)}]: {video_id}.mp4")
            try:
                # 使用视频 URL 的域名作为 referer
                referer = "https://onlytik.com"
                if download_video(video_url, referer, filename):
                    print(f"  ✓ 下载成功: {video_id}.mp4")
                    total_downloaded += 1
                else:
                    print(f"  ✗ 下载失败: {video_id}.mp4")
                    # 删除不完整的文件
                    if filename.exists():
                        filename.unlink()
                    total_failed += 1
            except Exception as e:
                print(f"  ✗ 下载异常: {video_id}.mp4 - {e}")
                # 删除不完整的文件
                if filename.exists():
                    filename.unlink()
                total_failed += 1
        
        # 增加 offset
        offset += OFFSET_INCREMENT
    
    # 输出统计信息
    print("\n" + "=" * 50)
    print("爬取完成！")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  已跳过: {total_skipped} 个")
    print(f"  下载失败: {total_failed} 个")
    print(f"  总计处理: {total_downloaded + total_skipped + total_failed} 个")

if __name__ == "__main__":
    download_all_videos(USER_ID)

