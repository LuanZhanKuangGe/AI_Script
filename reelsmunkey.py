import sys
import re
import json
import requests
from pathlib import Path
from tqdm import tqdm
import platform

if platform.system() == "Windows":
    BASE_PATH = Path(r"D:\Porn-Web\reelsmunkey")
else:
    BASE_PATH = Path(r"/data/Porn-Web/reelsmunkey")

BASE_PATH.mkdir(parents=True, exist_ok=True)

MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 3

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


def validate_title(title: str) -> str:
    invalid_chars = r'[<>:"/\\|?*]'
    title = re.sub(invalid_chars, '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = title.strip('.')
    return title


def parse_list_page(session: requests.Session, page_url: str) -> list:
    try:
        response = session.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        videos = []

        pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        match = re.search(pattern, response.text, re.DOTALL)
        if not match:
            print(f"  未找到JSON-LD数据")
            return []

        json_text = match.group(1)
        data = json.loads(json_text)

        main_entity = data.get('mainEntity', {})
        item_list = main_entity.get('itemListElement', [])

        for item in item_list:
            video_obj = item.get('item', {})
            name = video_obj.get('name', 'untitled')
            embed_url = video_obj.get('embedUrl', '')
            content_url = video_obj.get('contentUrl', '')

            if content_url:
                video_id = content_url.split('/')[-1].replace('.mp4', '')
                videos.append({
                    'id': video_id,
                    'title': name,
                    'url': content_url
                })

        return videos

    except Exception as e:
        print(f"  解析列表页失败: {e}")
        return []


def download_file(session: requests.Session, url: str, filepath: Path) -> bool:
    if filepath.exists():
        return True

    temp_filepath = filepath.with_suffix(filepath.suffix + '.tmp')
    if temp_filepath.exists():
        temp_filepath.unlink()

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        print(f"    开始下载: {filepath.name}")
        response = session.get(url, stream=True, headers=HEADERS, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('Content-Length', 0))

        downloaded_size = 0
        block_size = 8192

        with open(temp_filepath, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=filepath.name, leave=False) as pbar:
                for chunk in response.iter_content(block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        pbar.update(len(chunk))

        if total_size > 0 and downloaded_size != total_size:
            print(f"    下载不完整: {downloaded_size}/{total_size} bytes")
            temp_filepath.unlink()
            return False

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


def main():
    print(f"BASE_PATH: {BASE_PATH}")
    print(f"最大页数: {MAX_PAGES}")

    session = requests.Session()

    all_videos = []

    for page in range(1, MAX_PAGES + 1):
        page_url = f"https://reelsmunkey.com/page/{page}"
        print(f"\n获取第 {page} 页: {page_url}")
        videos = parse_list_page(session, page_url)
        print(f"  获取到 {len(videos)} 个视频")
        all_videos.extend(videos)

    print(f"\n共获取 {len(all_videos)} 个视频")

    existing_files = {f.name for f in BASE_PATH.glob("*.mp4")}
    print(f"  已存在 {len(existing_files)} 个文件")

    filtered_videos = []
    for video in all_videos:
        video_id = video['id']
        title = video['title']
        clean_title = validate_title(title)
        filename = f"[{video_id}] {clean_title}.mp4"
        if filename not in existing_files:
            video['filename'] = filename
            filtered_videos.append(video)

    to_download = len(filtered_videos)
    print(f"  需要下载 {to_download} 个视频")

    print(f"\n开始下载视频...")
    total_downloaded = 0
    total_failed = 0

    for idx, video in enumerate(filtered_videos, 1):
        video_url = video['url']
        filename = video['filename']
        filepath = BASE_PATH / filename

        print(f"  [{idx}/{to_download}] {filename}")

        if download_file(session, video_url, filepath):
            total_downloaded += 1
        else:
            total_failed += 1

    print(f"\n{'='*60}")
    print("下载完成！")
    print(f"  总视频数: {len(all_videos)} 个")
    print(f"  已跳过: {len(existing_files)} 个")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  下载失败: {total_failed} 个")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
