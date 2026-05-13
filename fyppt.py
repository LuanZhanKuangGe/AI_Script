import sys
import re
import requests
from pathlib import Path
from typing import Optional, List, Tuple
from tqdm import tqdm
from urllib.parse import urlparse, urljoin, unquote
import subprocess
import shutil
import hashlib

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    try:
        from lxml import html
        HAS_LXML = True
    except ImportError:
        HAS_LXML = False
        print("警告: 未安装 BeautifulSoup 或 lxml，无法解析 HTML")

from all_path import PORN_WEB_FYPTT as BASE_PATH

# 确保 BASE_PATH 存在
BASE_PATH.mkdir(parents=True, exist_ok=True)

# 爬取页数常量
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


def validate_title(title: str) -> str:
    """清理文件名，移除非法字符"""
    # Windows 文件名非法字符: < > : " / \ | ? *
    invalid_chars = r'[<>:"/\\|?*]'
    title = re.sub(invalid_chars, '', title)
    # 移除多余的空格和点
    title = re.sub(r'\s+', ' ', title).strip()
    title = title.strip('.')
    return title


def parse_page_urls(session: requests.Session, page_url: str) -> List[str]:
    """解析页面，获取所有视频链接"""
    try:
        response = session.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        video_urls = []
        
        if HAS_BS4:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 使用CSS选择器获取所有链接
            # 选择器：#fl-post-18 > div > div > div > div > div > div > div > div > div.fl-module.fl-module-post-grid.fl-node-5f75ad241a937 > div > div.fl-post-grid.fl-paged-scroll-to > div > div > div.fl-post-grid-image > a
            # 简化选择器，查找所有包含视频链接的元素
            links = soup.select('div.fl-post-grid-image > a')
            for link in links:
                href = link.get('href')
                if href and href.startswith('https://fyptt.to/'):
                    video_urls.append(href)
        elif HAS_LXML:
            doc = html.fromstring(response.text)
            # 使用XPath或CSS选择器
            links = doc.cssselect('div.fl-post-grid-image > a')
            for link in links:
                href = link.get('href')
                if href and href.startswith('https://fyptt.to/'):
                    video_urls.append(href)
        else:
            # 使用正则表达式作为备选
            pattern = r'href="(https://fyptt\.to/\d+/[^"]+)"'
            video_urls = re.findall(pattern, response.text)
        
        return video_urls
    
    except Exception as e:
        print(f"  解析页面失败: {e}")
        return []


def extract_video_info(url: str) -> Optional[tuple]:
    """从URL中提取ID和title"""
    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) >= 2:
            video_id = path_parts[0]
            title = path_parts[1]
            return video_id, title
        return None
    except Exception as e:
        print(f"  解析URL失败: {url}, 错误: {e}")
        return None


def get_video_url(session: requests.Session, page_url: str) -> Optional[Tuple[str, str]]:
    """从视频页面获取视频URL和类型
    步骤：
    1. 从页面中找到 iframe 的 data-src-no-ap (arve-iframe 类)
    2. 访问 iframe URL
    3. 从 iframe 页面中提取 source 标签的 src
    返回: (video_url, video_type) 元组，video_type 可能是 'mp4' 或 'm3u8'
    """
    try:
        # 第一步：获取视频页面并找到 iframe
        response = session.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        iframe_url = None
        
        if HAS_BS4:
            soup = BeautifulSoup(response.text, 'html.parser')
            iframe_tag = soup.select_one('iframe.arve-iframe')
            if iframe_tag:
                iframe_url = iframe_tag.get('data-src-no-ap') or iframe_tag.get('src')
            if not iframe_tag or not iframe_url:
                iframe_tag = soup.select_one('iframe[src*="fypttstr.php"], iframe[src*="fypttjwstrhls.php"]')
                if iframe_tag:
                    iframe_url = iframe_tag.get('data-src-no-ap') or iframe_tag.get('src')
        elif HAS_LXML:
            doc = html.fromstring(response.text)
            iframe_elements = doc.cssselect('iframe.arve-iframe')
            if not iframe_elements:
                iframe_elements = doc.cssselect('iframe[src*="fypttstr.php"], iframe[src*="fypttjwstrhls.php"]')
            if iframe_elements:
                iframe_url = iframe_elements[0].get('data-src-no-ap') or iframe_elements[0].get('src')
        else:
            pattern = r'<iframe[^>]*class="[^"]*arve-iframe[^"]*"[^>]*data-src-no-ap="([^"]+)"'
            match = re.search(pattern, response.text)
            if match:
                iframe_url = match.group(1)
            else:
                pattern = r'<iframe[^>]*data-src-no-ap="([^"]*fyptt(?:jw)?str(?:hls)?\.php[^"]*)"'
                match = re.search(pattern, response.text)
                if match:
                    iframe_url = match.group(1)
                else:
                    pattern = r'<iframe[^>]*src="([^"]*fyptt(?:jw)?str(?:hls)?\.php[^"]*)"'
                    match = re.search(pattern, response.text)
                    if match:
                        iframe_url = match.group(1)
        
        if not iframe_url:
            print(f"    未找到 iframe URL")
            return None
        
        iframe_url = iframe_url.replace('&#038;', '&').replace('&amp;', '&')
        
        if iframe_url.startswith('//'):
            iframe_url = 'https:' + iframe_url
        elif iframe_url.startswith('/'):
            iframe_url = 'https://fyptt.to' + iframe_url
        
        print(f"    找到 iframe URL: {iframe_url}")
        
        # 第二步：访问 iframe URL
        iframe_response = session.get(iframe_url, headers=HEADERS, timeout=30)
        iframe_response.raise_for_status()
        
        content_type = iframe_response.headers.get('Content-Type', '')
        if 'image/' in content_type:
            print(f"    检测到图片格式 ({content_type})，直接下载")
            return (iframe_url, 'mp4')
        
        iframe_text = iframe_response.text
        
        # 第三步：查找 source 标签（mp4 或 m3u8）
        video_download_url = None
        video_type = None
        
        if HAS_BS4:
            iframe_soup = BeautifulSoup(iframe_text, 'html.parser')
            source_tag = iframe_soup.select_one('source[type="video/mp4"], source[src*=".m3u8"], source[src*=".mp4"]')
            if source_tag:
                video_download_url = source_tag.get('src')
                video_type = 'm3u8' if '.m3u8' in (video_download_url or '') else 'mp4'
            if not video_download_url:
                video_tag = iframe_soup.select_one('video[src*=".mp4"], video[src*=".m3u8"]')
                if video_tag:
                    video_download_url = video_tag.get('src')
                    video_type = 'm3u8' if '.m3u8' in (video_download_url or '') else 'mp4'
        elif HAS_LXML:
            iframe_doc = html.fromstring(iframe_text)
            source_elements = iframe_doc.cssselect('source')
            for src_el in source_elements:
                src = src_el.get('src', '')
                if '.m3u8' in src:
                    video_download_url = src
                    video_type = 'm3u8'
                    break
                elif '.mp4' in src or src_el.get('type') == 'video/mp4':
                    video_download_url = src
                    video_type = 'mp4'
                    break
            if not video_download_url:
                video_elements = iframe_doc.cssselect('video')
                for v_el in video_elements:
                    src = v_el.get('src', '')
                    if '.mp4' in src or '.m3u8' in src:
                        video_download_url = src
                        video_type = 'm3u8' if '.m3u8' in src else 'mp4'
                        break
        else:
            pattern = r'<source[^>]*src="([^"]+\.(?:mp4|m3u8)[^"]*)"'
            match = re.search(pattern, iframe_text)
            if match:
                video_download_url = match.group(1)
                video_type = 'm3u8' if '.m3u8' in video_download_url else 'mp4'
            if not video_download_url:
                pattern = r'<video[^>]*src="([^"]+\.(?:mp4|m3u8)[^"]*)"'
                match = re.search(pattern, iframe_text)
                if match:
                    video_download_url = match.group(1)
                    video_type = 'm3u8' if '.m3u8' in video_download_url else 'mp4'
        
        if video_download_url:
            video_download_url = video_download_url.replace('&#038;', '&').replace('&amp;', '&')
            if video_download_url.startswith('//'):
                video_download_url = 'https:' + video_download_url
            elif video_download_url.startswith('/'):
                video_download_url = 'https://fyptt.to' + video_download_url
            print(f"    找到视频下载地址 ({video_type}): {video_download_url}")
            return (video_download_url, video_type)
        
        print(f"    未找到视频下载地址")
        
        poster_match = re.search(r'poster=([^&]+)', iframe_url)
        if poster_match:
            poster_url = unquote(poster_match.group(1))
            if poster_url.endswith('.webp'):
                poster_full_url = urljoin('https://fyptt.to/', poster_url)
                print(f"    尝试下载 poster webp: {poster_full_url}")
                return (poster_full_url, 'mp4')
        
        return None
    
    except Exception as e:
        print(f"  获取视频URL失败: {e}")
        return None


def download_m3u8_to_mp4(session: requests.Session, m3u8_url: str, filepath: Path, referer: str = "https://fyptt.to/") -> bool:
    """下载 m3u8 并转换为 mp4
    使用 ffmpeg 将 m3u8 转换为 mp4
    """
    # 检查 ffmpeg 是否可用
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        print(f"    错误: 未找到 ffmpeg，无法下载 m3u8 视频")
        print(f"    请安装 ffmpeg: https://ffmpeg.org/download.html")
        return False
    
    # 如果文件已存在，跳过
    if filepath.exists():
        return True
    
    # 使用简短的临时文件名，避免路径过长
    # 使用文件名的hash作为临时文件名
    file_hash = hashlib.md5(str(filepath).encode()).hexdigest()[:8]
    temp_filename = f"temp_{file_hash}.mp4"
    temp_filepath = filepath.parent / temp_filename
    
    # 如果临时文件存在，删除它
    if temp_filepath.exists():
        temp_filepath.unlink()
    
    try:
        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"    开始下载并转换 m3u8: {filepath.name}")
        
        # 设置下载请求头
        download_headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': referer,
            'Origin': referer.rstrip('/'),
        }
        
        # 使用 ffmpeg 下载并转换
        cmd = [
            ffmpeg_path,
            '-i', m3u8_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-headers', f'User-Agent: {download_headers["User-Agent"]}',
            '-headers', f'Referer: {referer}',
            '-y',
            str(temp_filepath)
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        last_time = None
        for line in process.stderr:
            line = line.strip()
            m = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
            if m and m.group(1) != last_time:
                last_time = m.group(1)
                print(f"    \r    进度: {last_time}", end='', flush=True)
        
        process.wait()
        print()
        
        if process.returncode != 0:
            print(f"    ffmpeg 转换失败")
            if temp_filepath.exists():
                temp_filepath.unlink()
            return False
        
        # 检查文件是否成功创建
        if not temp_filepath.exists() or temp_filepath.stat().st_size == 0:
            print(f"    转换失败: 输出文件为空")
            if temp_filepath.exists():
                temp_filepath.unlink()
            return False
        
        # 转换成功，重命名为最终文件
        temp_filepath.rename(filepath)
        print(f"    ✓ 下载完成: {filepath.name}")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"    转换超时: {filepath.name}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False
    except Exception as e:
        print(f"    转换异常: {filepath.name} - {e}")
        if temp_filepath.exists():
            temp_filepath.unlink()
        return False


def download_file(session: requests.Session, url: str, filepath: Path, referer: str = "https://fyptt.to/") -> bool:
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


def process_video(session: requests.Session, video_url: str) -> tuple:
    """处理单个视频：检查文件是否存在，不存在则下载
    返回: (是否成功, 是否跳过)
    """
    # 提取ID和title
    info = extract_video_info(video_url)
    if not info:
        print(f"  无法解析URL: {video_url}")
        return (False, False)
    
    video_id, title = info
    clean_title = validate_title(title)
    
    # 文件扩展名统一为 mp4（m3u8 也会转换为 mp4）
    filename = f"[{video_id}]{clean_title}.mp4"
    filepath = BASE_PATH / filename
    
    # 先检查文件是否已存在，如果存在则不需要访问页面获取URL
    if filepath.exists():
        print(f"  文件已存在: {filename}")
        return (True, True)
    
    # 文件不存在，需要获取视频URL和类型
    print(f"  处理视频: {filename}")
    video_info = get_video_url(session, video_url)
    if not video_info:
        print(f"    无法获取视频下载URL")
        return (False, False)
    
    video_download_url, video_type = video_info
    
    # 根据视频类型选择下载方式
    if video_type == 'm3u8':
        # 使用 ffmpeg 下载并转换 m3u8
        if download_m3u8_to_mp4(session, video_download_url, filepath, video_url):
            return (True, False)
        else:
            return (False, False)
    else:
        # 直接下载 mp4
        if download_file(session, video_download_url, filepath, video_url):
            return (True, False)
        else:
            return (False, False)


def main():
    """主函数"""
    print(f"BASE_PATH: {BASE_PATH}")
    print(f"爬取页数: {N}")
    
    if not HAS_BS4 and not HAS_LXML:
        print("错误: 需要安装 BeautifulSoup4 或 lxml 才能解析HTML")
        print("安装命令: pip install beautifulsoup4 或 pip install lxml")
        return
    
    # 创建会话
    session = requests.Session()
    
    all_video_urls = []
    
    # 第一阶段：获取所有视频URL
    print(f"\n第一阶段：获取所有视频链接...")
    for page_num in range(N):
        page_url = f"https://fyptt.to/page/{page_num}/"
        print(f"  爬取第 {page_num} 页: {page_url}")
        urls = parse_page_urls(session, page_url)
        print(f"    找到 {len(urls)} 个视频链接")
        all_video_urls.extend(urls)
    
    print(f"\n  共获取到 {len(all_video_urls)} 个视频链接")
    
    # 过滤已存在的视频
    print(f"\n第二阶段：过滤已存在的视频...")
    pending = []
    for video_url in all_video_urls:
        info = extract_video_info(video_url)
        if not info:
            continue
        video_id, title = info
        clean_title = validate_title(title)
        filename = f"[{video_id}]{clean_title}.mp4"
        filepath = BASE_PATH / filename
        if filepath.exists():
            print(f"  跳过已存在: {filename}")
        else:
            pending.append((video_url, filename))
    
    print(f"\n  需要下载: {len(pending)}/{len(all_video_urls)} 个")
    
    # 第三阶段：下载视频
    if not pending:
        print(f"\n所有视频已存在，无需下载")
        return
    
    print(f"\n第三阶段：开始下载视频...")
    total_downloaded = 0
    total_failed = 0
    
    for idx, (video_url, filename) in enumerate(pending, 1):
        print(f"  [{idx}/{len(pending)}]")
        print(f"  处理视频: {filename}")
        video_info = get_video_url(session, video_url)
        if not video_info:
            print(f"    无法获取视频下载URL")
            total_failed += 1
            continue
        
        video_download_url, video_type = video_info
        filepath = BASE_PATH / filename
        
        if video_type == 'm3u8':
            if download_m3u8_to_mp4(session, video_download_url, filepath, video_url):
                total_downloaded += 1
            else:
                total_failed += 1
        else:
            if download_file(session, video_download_url, filepath, video_url):
                total_downloaded += 1
            else:
                total_failed += 1
    
    # 输出统计信息
    print(f"\n{'='*60}")
    print("爬取完成！")
    print(f"  总视频数: {len(all_video_urls)} 个")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  已跳过: {len(all_video_urls) - len(pending)} 个")
    print(f"  下载失败: {total_failed} 个")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
