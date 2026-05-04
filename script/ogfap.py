from pathlib import Path
import sys
import subprocess
from typing import Optional, List, Dict

import requests

try:
    from tqdm import tqdm
except Exception:
    tqdm = None


def _progress_bar(total: Optional[int], desc: str, unit: str):
    if tqdm:
        return tqdm(total=total, desc=desc, unit=unit, unit_scale=True, unit_divisor=1024, leave=False)
    return SimpleBar(total=total, desc=desc, unit=unit)


class ProgressProtocol:
    def update(self, value: int) -> None: ...
    def close(self) -> None: ...


class SimpleBar:
    def __init__(self, total: Optional[int], desc: str, unit: str) -> None:
        self.total = total
        self.desc = desc
        self.unit = unit
        self.current = 0

    def update(self, value: int) -> None:
        self.current += value
        if self.total:
            pct = (self.current / self.total) * 100
            sys.stdout.write(f"\r{self.desc}: {self.current}/{self.total} {self.unit} ({pct:.1f}%)")
        else:
            sys.stdout.write(f"\r{self.desc}: {self.current} {self.unit}")
        sys.stdout.flush()

    def close(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()


def fetch_posts(session: requests.Session, cursor: int = 0, limit: int = 8) -> Optional[Dict]:
    """获取帖子列表"""
    api_url = f"https://apin.ogfap.com/v2/post/feed-by-key?cursor={cursor}&limit={limit}"
    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as exc:
        print(f"获取帖子列表失败 (cursor={cursor}): {exc}")
        return None


def iter_posts(session: requests.Session, max_iterations: int = 2) -> List[Dict]:
    """迭代获取所有帖子"""
    all_posts = []
    cursor = 0
    
    for iteration in range(max_iterations):
        print(f"正在获取第 {iteration + 1}/{max_iterations} 批数据 (cursor={cursor})...")
        data = fetch_posts(session, cursor, limit=8)
        if not data or "posts" not in data:
            break
        
        posts = data["posts"]
        if not posts:
            break
        
        all_posts.extend(posts)
        print(f"获取到 {len(posts)} 个帖子")
        
        # 使用最后一个帖子的 id 作为下一个 cursor
        if posts:
            cursor = posts[-1].get("id", 0)
            if cursor == 0:
                break
    
    return all_posts


def download_m3u8_to_mp4(session: requests.Session, m3u8_url: str, output_path: Path, 
                          overall_bar: ProgressProtocol, max_retries: int = 3) -> bool:
    """使用 ffmpeg 下载 m3u8 并转换为 mp4"""
    if output_path.exists():
        overall_bar.update(1)
        return True
    
    # 使用临时文件
    tmp_path = output_path.with_suffix('.tmp.mp4')
    
    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(1, max_retries + 1):
        try:
            # 使用 ffmpeg 下载并转换
            # -y: 覆盖输出文件
            # -i: 输入 URL
            # -c copy: 直接复制流，不重新编码（更快）
            # -bsf:a aac_adtstoasc: 修复 AAC 音频流
            # -loglevel error: 只显示错误信息
            cmd = [
                'ffmpeg',
                '-y',
                '-i', m3u8_url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-loglevel', 'error',
                str(tmp_path)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600  # 10分钟超时
            )
            
            if result.returncode == 0 and tmp_path.exists():
                # 下载成功，重命名为最终文件
                tmp_path.rename(output_path)
                print(f"完成: {output_path.name}")
                overall_bar.update(1)
                return True
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "未知错误"
                print(f"ffmpeg 转换失败({attempt}/{max_retries}): {output_path.name} - {error_msg[:100]}")
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            print(f"下载超时({attempt}/{max_retries}): {output_path.name}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except FileNotFoundError:
            print(f"错误: 未找到 ffmpeg，请确保已安装 ffmpeg 并添加到 PATH")
            overall_bar.update(1)
            return False
        except Exception as exc:
            print(f"下载异常({attempt}/{max_retries}): {output_path.name} - {exc}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
    
    overall_bar.update(1)
    return False


from all_path import PORN_WEB_OGFAP as BASE_PATH

# 常量
SALT = "0312"  # URL 中的常量字符串
MAX_ITERATIONS = int(sys.argv[1])  # 默认循环次数

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

print(f"开始获取帖子列表 (最多 {MAX_ITERATIONS} 次迭代)...")
posts = iter_posts(session, max_iterations=MAX_ITERATIONS)

if not posts:
    print("未获取到任何帖子")
    sys.exit(0)

print(f"\n总共获取到 {len(posts)} 个帖子")
print("开始处理视频下载...")

# 收集需要下载的视频任务
video_tasks = []
for post in posts:
    post_id = post.get("id")
    uid = post.get("uid")
    
    if not post_id or not uid:
        continue
    
    # 检查文件是否已存在
    filename = f"{post_id}-{uid}.mp4"
    file_path = BASE_PATH / filename
    
    if file_path.exists():
        continue
    
    # 构建 m3u8 URL
    m3u8_url = f"https://xcdn.tv/cdn/production/media/{SALT}/{uid}/master.m3u8"
    video_tasks.append((m3u8_url, file_path))

total_files = len(video_tasks)
if not total_files:
    print("所有视频文件已存在，无需下载")
    sys.exit(0)

print(f"找到 {total_files} 个视频需要下载")
overall = _progress_bar(total_files, desc="总进度", unit="file")

for m3u8_url, file_path in video_tasks:
    download_m3u8_to_mp4(session, m3u8_url, file_path, overall)

overall.close()
print("处理完成！")
