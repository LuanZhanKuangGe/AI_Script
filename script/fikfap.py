import re
import sys
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict

import requests
from tqdm import tqdm
from all_path import PORN_ONLYFANS as BASE_PATH

BASE_PATH.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.fikfap.com"
POSTS_PATH_TEMPLATE = "/profile/username/{username}/posts"

AUTHORIZATION_ANONYMOUS = "8231027f-abbf-44bf-9cc4-87acd6b445e1"
FIKFAP_COOKIE = (
    "cf_clearance=iPjESyBlsi2ze.aLdBwwWal9yOcDCIjC9AIsikMZf78-1737809279-1.2.1.1-"
    "IqCPo5X9zMleM_UqGIU5N7ORt3GDLdCpj.Y1IrYV_YszX.buzB9dldwigInUE1UGFxPS1EVeHG4DtyV1j.8.7isl."
    "OX3ntUWBE_MzYdwlMQ8q876h9J0Ua7WumNBTw0HH9IXMG4uho9wTSPh9P0q92a.G9sl27Pt5CrOoGlHJiEZGERqkzSGr1AuaIglxWi91X2_EQypO4sA6w7."
    "03cQ01bTw2IBQTYaoEtfo9uNm6FQFTipocV6Dyq3Uyp0cG01MtLiAxZ2kSd6cpDVmJS6Y7FwOXWxHp7NjN0pGmxIWoA"
)

BASE_API_HEADERS = {
    "authority": "api.fikfap.com",
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "isloggedin": "false",
    "ispwa": "false",
    "origin": "https://fikfap.com",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
}


def build_api_headers(username: str) -> Dict[str, str]:
    headers = BASE_API_HEADERS.copy()
    headers["origin"] = "https://fikfap.com"
    headers["referer"] = f"https://fikfap.com/user/{username}"
    if AUTHORIZATION_ANONYMOUS:
        headers["authorization-anonymous"] = AUTHORIZATION_ANONYMOUS
    if FIKFAP_COOKIE:
        headers["cookie"] = FIKFAP_COOKIE
    return headers


def fetch_posts(session: requests.Session, username: str, after_id: Optional[int] = None,
                amount: int = 21) -> List[Dict]:
    params = {"amount": amount}
    if after_id is not None:
        params["afterId"] = after_id
    url = f"{API_BASE}{POSTS_PATH_TEMPLATE.format(username=username)}"
    try:
        resp = session.get(url, headers=build_api_headers(username), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            print(f"  警告: 返回数据不是列表，实际类型: {type(data)}")
            return []
        return data
    except Exception as e:
        print(f"  获取用户 {username} 帖子失败: {e}")
        return []


def _parse_map_uri(playlist: str) -> Optional[str]:
    m = re.search(r'#EXT-X-MAP:URI="([^"]+)"', playlist)
    return m.group(1) if m else None


def download_m3u8_video(session: requests.Session, m3u8_url: str, output_path: Path, referer: str,
                        max_retries: int = 3) -> bool:
    if output_path.exists():
        return True

    # 通过 ffmpeg 直接对 master playlist 复用（支持音频轨 + EXT-X-MAP）
    if _mux_with_ffmpeg(session, m3u8_url, output_path, referer, max_retries):
        print(f"    ✓ 下载完成(ffmpeg): {output_path.name}")
        return True

    # 回退到原有片段拼接逻辑
    tmp = output_path.with_suffix(output_path.suffix + '.tmp')
    if tmp.exists():
        tmp.unlink()

    dl_headers = {
        'User-Agent': BASE_API_HEADERS['user-agent'],
        'Referer': referer,
        'Origin': 'https://fikfap.com',
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(m3u8_url, headers=dl_headers, timeout=30)
            resp.raise_for_status()
            playlist = resp.text
        except Exception as e:
            print(f"    下载 m3u8 playlist 失败({attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                return False
            continue

        base_url = m3u8_url.rsplit('/', 1)[0] + '/'

        # Master playlist → 选最高码率
        if '#EXT-X-STREAM-INF' in playlist:
            best_url = None
            best_bw = -1
            for line in playlist.splitlines():
                if line.startswith('#EXT-X-STREAM-INF:'):
                    m = re.search(r'BANDWIDTH=(\d+)', line)
                    bw = int(m.group(1)) if m else 0
                elif line.strip() and not line.startswith('#'):
                    if bw > best_bw:
                        seg = line.strip()
                        best_bw = bw
                        best_url = seg if seg.startswith('http') else urllib.parse.urljoin(base_url, seg)
            if best_url:
                return download_m3u8_video(session, best_url, output_path, referer, max_retries)
            return False

        # EXT-X-MAP init 分片（必须写入头部，否则播放器无法解析）
        init_uri = _parse_map_uri(playlist)
        segments = []
        for line in playlist.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                seg_url = line if line.startswith('http') else urllib.parse.urljoin(base_url, line)
                segments.append(seg_url)

        if not segments and not init_uri:
            print(f"    未找到视频片段")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(tmp, 'wb') as f, tqdm(total=len(segments) + (1 if init_uri else 0), unit='seg',
                                             desc=output_path.name, leave=False) as pbar:
                if init_uri:
                    init_url = init_uri if init_uri.startswith('http') else urllib.parse.urljoin(base_url, init_uri)
                    init_resp = session.get(init_url, headers=dl_headers, timeout=60)
                    init_resp.raise_for_status()
                    f.write(init_resp.content)
                    pbar.update(1)
                for seg_url in segments:
                    seg_resp = session.get(seg_url, headers=dl_headers, timeout=60)
                    seg_resp.raise_for_status()
                    f.write(seg_resp.content)
                    pbar.update(1)
            tmp.rename(output_path)
            print(f"    ✓ 下载完成: {output_path.name}")
            return True
        except Exception as e:
            print(f"    下载片段失败({attempt}/{max_retries}): {e}")
            if tmp.exists():
                tmp.unlink()
            if attempt == max_retries:
                return False
    return False


def _mux_with_ffmpeg(session: requests.Session, m3u8_url: str, output_path: Path, referer: str,
                     max_retries: int = 3) -> bool:
    """优先用 ffmpeg 合成完整 mp4(含音频)。成功返回 True，失败回退原逻辑。"""
    import shutil
    import subprocess
    if not shutil.which('ffmpeg'):
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + '.tmp')
    if tmp.exists():
        tmp.unlink()

    # 构造 master playlist 的过滤副本：最佳视频变体 + 音频组(URI 已绝对化)
    try:
        resp = session.get(m3u8_url, timeout=30,
                            headers={'User-Agent': BASE_API_HEADERS['user-agent'],
                                     'Referer': referer, 'Origin': 'https://fikfap.com'})
        resp.raise_for_status()
    except Exception:
        return False
    master = resp.text
    base_url = m3u8_url.rsplit('/', 1)[0] + '/'

    if '#EXT-X-STREAM-INF' not in master:
        return False  # 仅在 master playlist 时使用 ffmpeg 方案

    filtered = ["#EXTM3U", "#EXT-X-VERSION:6"]
    best_bw, best_inf, best_uri, audio_line = -1, None, None, None
    cur_bw, cur_inf = 0, None
    for ln in master.splitlines():
        if ln.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in ln and audio_line is None:
            m = re.search(r'URI="([^"]+)"', ln)
            if m:
                abs_uri = urllib.parse.urljoin(base_url, m.group(1))
                ln = ln[:m.start()] + 'URI="' + abs_uri + '"' + ln[m.end():]
            audio_line = ln
        elif ln.startswith("#EXT-X-STREAM-INF:"):
            m = re.search(r"BANDWIDTH=(\d+)", ln)
            cur_bw = int(m.group(1)) if m else 0
            cur_inf = ln
        elif ln.strip() and not ln.startswith("#"):
            if cur_bw > best_bw:
                best_bw, best_inf, best_uri = cur_bw, cur_inf, ln.strip()
            cur_bw, cur_inf = 0, None
    if not best_uri:
        return False
    if audio_line:
        filtered.append(audio_line)
    filtered.append(best_inf)
    filtered.append(best_uri if best_uri.startswith("http") else urllib.parse.urljoin(base_url, best_uri))
    filtered.append("#EXT-X-ENDLIST")

    import tempfile
    filt_path = Path(tempfile.gettempdir()) / f"fikfap_master_{output_path.stem}.m3u8"
    filt_path.write_text("\n".join(filtered), encoding="utf-8")

    headers_str = f"Referer: {referer}\r\nOrigin: https://fikfap.com\r\n"
    cmd = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
           "-protocol_whitelist", "file,http,https,tcp,tls,crypto,data",
           "-user_agent", BASE_API_HEADERS["user-agent"], "-headers", headers_str,
           "-i", str(filt_path),
           "-map", "0:a:0", "-map", "0:v:0", "-c", "copy", "-movflags", "+faststart",
           str(tmp)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        tmp.replace(output_path)
        return True
    except Exception as e:
        print(f"    ffmpeg 合成失败，回退传统模式: {e}")
        return False
    finally:
        try:
            filt_path.unlink(missing_ok=True)
        except Exception:
            pass
        if tmp.exists() and not output_path.exists():
            tmp.unlink(missing_ok=True)


def process_user(session: requests.Session, username: str, folder_name: str, mode: str = "quick") -> None:
    print(f"\n{'=' * 60}")
    print(f"处理用户: {username} (模式: {mode})")
    print(f"{'=' * 60}")

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n第一阶段：获取所有视频信息...")
    pending: List[Dict] = []
    total_fetched = 0
    last_post_id: Optional[int] = None

    while True:
        print(f"\n获取用户 {username} 帖子，afterId={last_post_id} ...")
        posts = fetch_posts(session, username, after_id=last_post_id, amount=21)

        if not posts:
            print("  没有更多帖子")
            break

        page_new = 0
        page_existing = 0
        for post in posts:
            post_id = post.get("postId")
            video_url = post.get("videoStreamUrl")

            if not post_id or not video_url:
                continue

            mp4_path = user_dir / f"{post_id}.mp4"
            total_fetched += 1

            if mp4_path.exists():
                page_existing += 1
            else:
                page_new += 1
                pending.append({'post_id': post_id, 'video_url': video_url, 'mp4_path': mp4_path})

            last_post_id = post_id

        print(f"  本页 {len(posts)} 个（新 {page_new}，已存在 {page_existing}）")

        if last_post_id is None:
            break

        if mode == "quick" and page_new == 0 and page_existing > 0:
            print(f"  本页全部已存在，停止翻页")
            break

    print(f"\n  共获取到 {total_fetched} 个帖子，待下载 {len(pending)} 个")

    if not pending:
        print("  无新视频需要下载")
        return

    print(f"\n第二阶段：开始下载 {len(pending)} 个新视频...")
    total_downloaded = 0
    total_failed = 0
    referer = f"https://fikfap.com/user/{username}"

    for idx, info in enumerate(pending, 1):
        print(f"  [{idx}/{len(pending)}] postId={info['post_id']}")
        if download_m3u8_video(session, info['video_url'], info['mp4_path'], referer):
            total_downloaded += 1
        else:
            total_failed += 1

    print(f"\n用户 {username} 处理完成:")
    print(f"  总帖子数(接口返回): {total_fetched}")
    print(f"  下载成功: {total_downloaded}")
    print(f"  下载失败: {total_failed}")


def main():
    print(f"BASE_PATH: {BASE_PATH}")

    if not BASE_PATH.exists():
        print(f"BASE_PATH 不存在: {BASE_PATH}")
        return

    users = []
    for f in BASE_PATH.iterdir():
        if f.is_dir() and f.name.endswith('@fikfap'):
            folder_name = f.name
            username = folder_name[:-len('@fikfap')]
            users.append((username, folder_name))

    if not users:
        print("BASE_PATH 下没有找到 @fikfap 子文件夹")
        return

    print(f"找到 {len(users)} 个 @fikfap 用户: {', '.join(u[0] for u in users)}")

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
