import re
import requests
from pathlib import Path
from tqdm import tqdm

# Iwara API 认证令牌
auth_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjI1MmYyMjYyLWVjNjctNGU4Yi04OWI2LTdkOThjMDM4NmNhOSIsInR5cGUiOiJhY2Nlc3NfdG9rZW4iLCJyb2xlIjoidXNlciIsInByZW1pdW0iOmZhbHNlLCJpc3MiOiJpd2FyYSIsImlhdCI6MTc1MjM3NjIwNywiZXhwIjoxNzUyMzc5ODA3fQ.obXYAHprNJWLNd9druA_ZEc6aLAWOdYkkybKQy7TngM'

# 设置请求头
iwara_headers = {
    'authority': 'api.iwara.tv',
    'accept': 'application/json',
    'content-type': 'application/json',
    'if-none-match': 'W/"ae0-mMYjE6WtBi0TCbA/345u8jstS6Y"',
    'origin': 'https://www.iwara.tv',
    'referer': 'https://www.iwara.tv/',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
}

scrapy_settings = {
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'REQUEST_FINGERPRINTER_IMPLEMENTATION': '2.7'
}

def validateTitle(title):
    """
    验证并清理标题,移除不合法的文件名字符
    """
    return re.sub(r'[\\/:*?"<>|.]', '-', title)


def download_video(url, ref, filename):
    """
    下载视频并显示进度条
    
    参数:
    url: 视频下载链接
    ref: 引用页面
    filename: 保存的文件名
    
    返回:
    1: 下载成功
    0: 下载失败
    """
    try:
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': ref,
            'Origin': ref
        }

        print(f"开始下载: {url}")
        # 发送GET请求，设置超时时间
        response = requests.get(url, stream=True, headers=headers, timeout=60)
        response.raise_for_status()

        # 获取文件总大小
        total_size = int(response.headers.get('Content-Length', 0))
        print(f"文件大小: {total_size} bytes")

        # 设置下载块大小和进度条
        block_size = 1024
        progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True)
        custom_string = f"{filename.name}"
        progress_bar.set_description(custom_string)

        # 写入文件并更新进度条
        with open(filename, 'wb') as f:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                f.write(data)

        progress_bar.close()
        
        # 检查是否下载完整
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

def list_files(directory):
    """列出指定目录下的所有文件"""
    path = Path(directory)
    files  = [f for f in path.iterdir() if f.is_file()]
    return files

def list_folders(directory):
    """列出指定目录下的所有文件夹,并按名称排序"""
    path = Path(directory)
    folders = [f for f in path.iterdir() if f.is_dir()]
    folders.sort(key=lambda x: x.name)
    return folders