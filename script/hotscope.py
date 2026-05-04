from pathlib import Path
import sys
import subprocess
from typing import Optional, List

import requests
from bs4 import BeautifulSoup

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


def fetch_trending_page(session: requests.Session, page: int) -> Optional[BeautifulSoup]:
    """获取 trending 页面的 HTML"""
    url = f"https://hotscope.tv/trending?page={page}"
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        return soup
    except Exception as exc:
        print(f"获取页面失败 (page={page}): {exc}")
        return None


def extract_video_ids(soup: BeautifulSoup) -> List[str]:
    """从页面中提取所有视频 ID"""
    video_ids = []
    
    # 查找包含视频链接的容器
    # 选择器: body > div.relative.container.mx-auto.p-0.touch-pan-y > div > main > div.grid.grid-cols-3.md\:grid-cols-6.gap-1
    main_grid = soup.select_one('body > div.relative.container.mx-auto.p-0.touch-pan-y > div > main > div.grid.grid-cols-3.md\\:grid-cols-6.gap-1')
    
    if not main_grid:
        # 尝试更宽松的选择器
        main_grid = soup.select_one('main div.grid')
    
    if main_grid:
        # 查找所有符合条件的 a 标签
        # 选择器: div > div.flex.grow > a
        links = main_grid.select('div > div.flex.grow > a')
        
        for link in links:
            href = link.get('href', '')
            if not href:
                continue
            
            # 从 href 中提取 id
            # 例如: https://hotscope.tv/video/4QT7b -> 4QT7b
            if '/video/' in href:
                video_id = href.split('/video/')[-1].split('?')[0].split('#')[0]
                if video_id:
                    video_ids.append(video_id)
    
    return video_ids


def get_all_video_ids(session: requests.Session, start_page: int, end_page: int) -> List[str]:
    """获取所有页面的视频 ID"""
    all_ids = []
    
    for page in range(start_page, end_page + 1):
        print(f"正在获取第 {page} 页...")
        soup = fetch_trending_page(session, page)
        if not soup:
            continue
        
        ids = extract_video_ids(soup)
        print(f"第 {page} 页找到 {len(ids)} 个视频")
        all_ids.extend(ids)
    
    # 去重
    return list(dict.fromkeys(all_ids))


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


from all_path import PORN_WEB_HOTSCOPE as BASE_PATH

# 常量
START_PAGE = int(sys.argv[1])  # 开始页
END_PAGE = int(sys.argv[2])    # 结束页

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

print(f"开始获取视频列表 (页面 {START_PAGE} 到 {END_PAGE})...")
video_ids = get_all_video_ids(session, START_PAGE, END_PAGE)

if not video_ids:
    print("未获取到任何视频 ID")
    sys.exit(0)

print(f"\n总共获取到 {len(video_ids)} 个视频 ID")
print("开始处理视频下载...")

# 收集需要下载的视频任务
video_tasks = []
for video_id in video_ids:
    # 检查文件是否已存在
    filename = f"{video_id}.mp4"
    file_path = BASE_PATH / filename
    
    if file_path.exists():
        continue
    
    # 构建 m3u8 URL
    m3u8_url = f"https://cdn.hotscope.tv/videos/{video_id}/video_1.m3u8"
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
