import re
import json
import requests
from pathlib import Path
from typing import Optional, Dict, List
from tqdm import tqdm
import cloudscraper

try:
    from lxml import html
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
    print("警告: 未安装 lxml，将使用正则表达式解析 HTML")

from all_path import PORN_WEB_XFREE as BASE_PATH

BASE_PATH.mkdir(parents=True, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'apiversion': '1.0',
    'app-version': 'xf1.39.6',
    'country': 'US',
    'language': 'en-US',
    'Referer': 'https://www.xfree.com/',
    'Origin': 'https://www.xfree.com',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=1, i',
}


def validate_title(title: str) -> str:
    invalid_chars = r'[<>:"/\\|?*]'
    title = re.sub(invalid_chars, "", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip(".")
    return title


def _split_js_args(s: str) -> List[str]:
    args = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    in_string = False
    string_char = None
    current = ""

    for c in s:
        if in_string:
            current += c
            if c == "\\":
                pass
            elif c == string_char:
                in_string = False
            continue

        if c in ('"', "'", "`"):
            in_string = True
            string_char = c
            current += c
            continue

        if c == "(":
            depth_paren += 1
            current += c
        elif c == ")":
            if depth_paren == 0:
                if current.strip():
                    args.append(current.strip())
                break
            depth_paren -= 1
            current += c
        elif c == "[":
            depth_bracket += 1
            current += c
        elif c == "]":
            depth_bracket -= 1
            current += c
        elif c == "{":
            depth_brace += 1
            current += c
        elif c == "}":
            depth_brace -= 1
            current += c
        elif c == "," and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
            args.append(current.strip())
            current = ""
        else:
            current += c

    return args


def get_user_id_from_html(session: requests.Session, actor_name: str) -> Optional[int]:
    url = f"https://www.xfree.com/{actor_name}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  获取演员页面失败: {e}")
        return None

    html_text = resp.text

    script_match = re.search(r'<script>window\.__NUXT__=\(function\(([^)]+)\)', html_text)
    if not script_match:
        print(f"  未找到 __NUXT__ 数据")
        return None

    param_names = [p.strip() for p in script_match.group(1).split(',')]

    script_start = script_match.start()
    script_content = html_text[script_start:script_start + 200000]

    id_param = None
    id_index = -1
    for idx, name in enumerate(param_names):
        pattern = rf'\.id\s*=\s*{re.escape(name)}\b'
        if re.search(pattern, script_content):
            id_param = name
            id_index = idx
            break

    if id_param is None:
        print(f"  未找到用户 ID 参数")
        return None

    args_match = re.search(r'\}\}\}\(', html_text)
    if not args_match:
        print(f"  未找到函数调用参数")
        return None

    call_start = args_match.end() - 1
    args = _split_js_args(html_text[call_start + 1:])

    if id_index >= len(args):
        print(f"  参数索引越界: {id_index} >= {len(args)}")
        return None

    try:
        return int(args[id_index])
    except (ValueError, TypeError):
        print(f"  无法解析用户 ID: {args[id_index]}")
        return None


def fetch_videos(session: requests.Session, user_id: int, actor_name: str = "", limit: int = 20) -> List[Dict]:
    all_videos = []
    offset = 0
    api_headers = {**API_HEADERS}
    if actor_name:
        api_headers['Referer'] = f'https://www.xfree.com/{actor_name}'

    while True:
        url = f"https://www.xfree.com/api/post/?limit={limit}&offset={offset}&userId={user_id}"
        try:
            resp = session.get(url, headers=api_headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            print(f"  获取API数据失败 (offset={offset}): HTTP {e.response.status_code}")
            if e.response.status_code == 404:
                print(f"    响应内容: {e.response.text[:500]}")
            break
        except Exception as e:
            print(f"  获取API数据失败 (offset={offset}): {e}")
            break

        items = data.get('body', [])
        if not items:
            break

        for item in items:
            video_id = item.get('id')
            video_name = item.get('title', '')
            if video_id:
                all_videos.append({
                    'video_id': video_id,
                    'video_name': video_name,
                })

        print(f"    获取 {len(items)} 个视频 (offset={offset})")
        offset += limit
        if len(items) < limit:
            break

    return all_videos


def get_video_download_url(session: requests.Session, video_id: int, actor_name: str) -> Optional[str]:
    url = f"https://www.xfree.com/video?id={video_id}&user={actor_name}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"    视频页面 HTTP {e.response.status_code}: {e}")
        return None
    except Exception as e:
        print(f"    获取视频页面失败: {e}")
        return None

    html_text = resp.text

    if HAS_LXML:
        doc = html.fromstring(html_text)
        video_elem = doc.xpath('//*[@id="feed-video-element"]')
        if video_elem:
            src = video_elem[0].get('src')
            if src:
                return src
            source = video_elem[0].find('.//source')
            if source is not None:
                src = source.get('src')
                if src:
                    return src
        print(f"    页面中未找到 id=feed-video-element 或其 src 为空")
    else:
        patterns = [
            r'<[^>]*id="feed-video-element"[^>]*src="([^"]+)"',
            r'<video[^>]*id="feed-video-element"[^>]*>.*?<source[^>]*src="([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, re.DOTALL)
            if match:
                return match.group(1)
        print(f"    页面中未找到 feed-video-element 的 src 属性")

    return None


def download_file(session: requests.Session, url: str, filepath: Path, referer: str = "https://www.xfree.com/") -> bool:
    if filepath.exists():
        return True

    temp_filepath = filepath.with_suffix(filepath.suffix + '.tmp')

    if temp_filepath.exists():
        temp_filepath.unlink()

    try:
        download_headers = {
            'User-Agent': HEADERS['User-Agent'],
            'Referer': referer,
            'Origin': referer.rstrip('/'),
        }

        print(f"    开始下载: {filepath.name}")
        response = session.get(url, stream=True, headers=download_headers, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('Content-Length', 0))

        filepath.parent.mkdir(parents=True, exist_ok=True)

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


def warmup_session(session: requests.Session) -> None:
    """访问首页获取初始 cookies（如 have18）"""
    try:
        session.get("https://www.xfree.com/", headers=HEADERS, timeout=30)
    except Exception:
        pass


def process_actor(session: requests.Session, actor_name: str) -> None:
    print(f"\n{'='*60}")
    print(f"处理演员: {actor_name}")
    print(f"{'='*60}")

    user_id = get_user_id_from_html(session, actor_name)
    if not user_id:
        print(f"  无法获取用户 ID，跳过: {actor_name}")
        return

    print(f"  用户 ID: {user_id}")

    actor_dir = BASE_PATH / actor_name
    actor_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n第一阶段：获取所有视频信息...")
    videos = fetch_videos(session, user_id, actor_name)
    print(f"  共获取到 {len(videos)} 个视频")

    print(f"\n第二阶段：开始批量下载...")
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    referer = f"https://www.xfree.com/{actor_name}"

    for idx, video in enumerate(videos, 1):
        video_id = video['video_id']
        video_name = validate_title(video['video_name'])
        filename = f"{video_id}_{video_name}.mp4"
        filepath = actor_dir / filename

        if filepath.exists():
            total_skipped += 1
            continue

        print(f"  [{idx}/{len(videos)}] {filename}")

        download_url = get_video_download_url(session, video_id, actor_name)
        if not download_url:
            total_failed += 1
            continue

        if download_file(session, download_url, filepath, referer):
            total_downloaded += 1
        else:
            total_failed += 1

    print(f"\n演员 {actor_name} 处理完成:")
    print(f"  总视频数: {len(videos)} 个")
    print(f"  下载成功: {total_downloaded} 个")
    print(f"  已跳过: {total_skipped} 个")
    print(f"  下载失败: {total_failed} 个")


def main():
    print(f"BASE_PATH: {BASE_PATH}")

    if not BASE_PATH.exists():
        print(f"BASE_PATH 不存在: {BASE_PATH}")
        return

    actors = [f.name for f in BASE_PATH.iterdir() if f.is_dir()]

    if not actors:
        print(f"BASE_PATH 下没有找到子文件夹")
        return

    print(f"找到 {len(actors)} 个演员: {', '.join(actors)}")

    session = cloudscraper.create_scraper()
    session.headers.update(HEADERS)
    warmup_session(session)

    for actor_name in actors:
        try:
            process_actor(session, actor_name)
        except Exception as e:
            print(f"处理演员 {actor_name} 时发生错误: {e}")
            continue

    print(f"\n{'='*60}")
    print("所有演员处理完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
