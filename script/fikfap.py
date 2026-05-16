import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict

import requests
from all_path import PORN_ONLYFANS as BASE_PATH

# 确保 BASE_PATH 存在
BASE_PATH.mkdir(parents=True, exist_ok=True)

# API 基础配置
API_BASE = "https://api.fikfap.com"
POSTS_PATH_TEMPLATE = "/profile/username/{username}/posts"

# 抓包得到的关键头信息（可按需修改）
# 注意：authorization-anonymous 和 cookie（cf_clearance）会过期，失效后需要重新抓包替换
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
    """根据抓包结果构造尽量一致的请求头"""
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
    """获取指定用户的一页帖子列表

    对应接口：
    - 第一页: https://api.fikfap.com/profile/username/{username}/posts?amount=21
    - 后续页: https://api.fikfap.com/profile/username/{username}/posts?amount=21&afterId={lastPostId}
    """
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


def download_m3u8_video(session: requests.Session, m3u8_url: str, output_path: Path, referer: str) -> bool:
    """用 requests session 下载 m3u8 视频（解析 playlist + 逐片段下载）"""
    dl_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        'Referer': referer,
        'Origin': 'https://fikfap.com',
    }

    try:
        resp = session.get(m3u8_url, headers=dl_headers, timeout=30)
        resp.raise_for_status()
        playlist = resp.text
    except Exception as e:
        print(f"    下载 m3u8 playlist 失败: {e}")
        return False

    base_url = m3u8_url.rsplit('/', 1)[0] + '/'

    # 如果是自适应流（master playlist），选择最高码率
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
            return download_m3u8_video(session, best_url, output_path, referer)
        return False

    # 解析媒体 playlist 中的 .ts 片段
    segments = []
    for line in playlist.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            seg_url = line if line.startswith('http') else urllib.parse.urljoin(base_url, line)
            segments.append(seg_url)

    if not segments:
        print(f"    未找到视频片段")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + '.tmp')

    try:
        with open(temp_path, 'wb') as f:
            for seg_url in segments:
                seg_resp = session.get(seg_url, headers=dl_headers, timeout=60)
                seg_resp.raise_for_status()
                f.write(seg_resp.content)

        temp_path.rename(output_path)
        print(f"    ✓ 下载完成: {output_path.name}")
        return True
    except Exception as e:
        print(f"    下载片段失败: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False


def process_user(session: requests.Session, username: str, folder_name: str) -> None:
    """处理单个用户：分页获取所有帖子，并为每个 postId 下载对应 mp4"""
    print(f"\n{'=' * 60}")
    print(f"处理用户: {username}")
    print(f"{'=' * 60}")

    user_dir = BASE_PATH / folder_name
    user_dir.mkdir(parents=True, exist_ok=True)

    total_posts = 0
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    last_post_id: Optional[int] = None
    referer = f"https://fikfap.com/user/{username}"

    while True:
        print(f"\n获取用户 {username} 帖子，afterId={last_post_id} ...")
        posts = fetch_posts(session, username, after_id=last_post_id, amount=21)

        if not posts:
            print("  没有更多帖子")
            break

        print(f"  本页帖子数: {len(posts)}")
        total_posts += len(posts)

        page_new = 0
        for post in posts:
            post_id = post.get("postId")
            video_url = post.get("videoStreamUrl")

            if not post_id or not video_url:
                continue

            mp4_path = user_dir / f"{post_id}.mp4"

            if mp4_path.exists():
                total_skipped += 1
                last_post_id = post_id
                continue

            page_new += 1
            print(f"  处理 postId={post_id}")
            if download_m3u8_video(session, video_url, mp4_path, referer):
                total_downloaded += 1
            else:
                total_failed += 1

            last_post_id = post_id

        if last_post_id is None:
            break

        # 本页全部已存在 -> 后续只会更旧，停止翻页
        if page_new == 0:
            print(f"  本页全部已存在，停止翻页")
            break

    print(f"\n用户 {username} 处理完成:")
    print(f"  总帖子数(请求到的): {total_posts}")
    print(f"  下载成功: {total_downloaded}")
    print(f"  已存在(跳过): {total_skipped}")
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

    session = requests.Session()

    for username, folder_name in users:
        try:
            process_user(session, username, folder_name)
        except Exception as e:
            print(f"处理用户 {username} 时发生错误: {e}")
            continue

    print(f"\n{'=' * 60}")
    print("所有用户处理完成！")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()