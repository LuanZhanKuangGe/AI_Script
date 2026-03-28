import sys
import requests
import re
from pathlib import Path
from tqdm import tqdm

BASE_URL = "https://api.reddclips.com"
BASE_PATH = Path(r"D:\Porn-Web\reddclips")
MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BASE_PATH.mkdir(parents=True, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.5',
}


def validate_title(title: str) -> str:
    invalid_chars = r'[<>:"/\\|?*]'
    title = re.sub(invalid_chars, '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = title.strip('.')
    return title


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
    cursor = None

    for page in range(MAX_PAGES):
        if page == 0:
            url = f"{BASE_URL}/categories/20/posts?limit=25&sort=top&seed=ave64kt8podmnagnndy"
        else:
            if not cursor:
                print(f"  第 {page + 1} 页: 无更多数据")
                break
            url = f"{BASE_URL}/categories/20/posts?limit=25&cursors=%7B%22after%22%3A%22{cursor}%22%7D&sort=top&seed=ave64kt8podmnagnndy"

        print(f"\n获取第 {page + 1} 页数据...")
        response = session.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()

        posts = data.get('posts', [])
        print(f"  获取到 {len(posts)} 个posts")

        videos = [p for p in posts if p.get('mediaType') == 'video' and p.get('over18') is True]
        print(f"  其中 {len(videos)} 个是NSFW视频")
        all_videos.extend(videos)

        cursors = data.get('cursors', {})
        cursor = cursors.get('after', None)

    print(f"\n共获取 {len(all_videos)} 个NSFW视频")

    print(f"\n开始下载视频...")
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    for idx, video in enumerate(all_videos, 1):
        video_id = video.get('id', '')
        title = video.get('title', 'untitled')
        media_url = video.get('mediaUrl', '')

        if not media_url:
            print(f"  [{idx}/{len(all_videos)}] 跳过: 无mediaUrl")
            total_failed += 1
            continue

        full_url = BASE_URL + media_url
        clean_title = validate_title(title)
        filename = f"[{video_id}] {clean_title}.mp4"
        filepath = BASE_PATH / filename

        print(f"  [{idx}/{len(all_videos)}] {filename}")

        if filepath.exists():
            total_skipped += 1
            continue

        if download_file(session, full_url, filepath):
            total_downloaded += 1
        else:
            total_failed += 1

    print(f"\n{'='*60}")
    print("下载完成！")
    print(f"  总视频数: {len(all_videos)} 个")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  已跳过: {total_skipped} 个")
    print(f"  下载失败: {total_failed} 个")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
