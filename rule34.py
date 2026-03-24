import argparse
from pathlib import Path
from tqdm import tqdm
import json
import platform
import requests
from bs4 import BeautifulSoup
import time
import random

from func import download_video

import logging
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)


def get_data_path():
    """根据操作系统返回正确的数据路径"""
    if platform.system() == "Windows":
        return r"D:\Hentai-Rule34"
    else:
        return "/data/Hentai-Rule34"



class Rule34Crawler:
    def __init__(self, start_stage=0):
        self.target = Path(get_data_path())
        self.start_stage = start_stage
        
        # 存储各阶段的结果
        self.page_results = []  # get_page 的结果
        self.video_results = []  # get_video 的结果
        
        # 存储已存在的视频ID
        self.existing_ids = set()
        
        # 创建会话以保持连接
        self.session = requests.Session()
        
        # 设置默认请求头（与抓包一致，避免 403；cookie 会过期需重新抓包替换）
        self.session.headers.update({
            'Host': 'rule34.xxx',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Cookie': 'filter_ai=1; gdpr=1; gdpr-consent=1; _cfuvid=Yxz_oqf_3XqDhacIhVY0Lsdltf_TY_C1RqR1pAaJ2DA-1772375882317-0.0.1.1-604800000; cf_clearance=1BXQ4RPSvB9GxnBjTB0IvdYxFEoDNcFM0Lzizx8ATGo-1772375905-1.2.1.1-ojlNxrN10uy5lyWCA8wADwqFomGIgFVgz38vzOmx.iy6Mt5JfsuGdGvVwcDQqq4EoVQA1pBwTM4TTvKYVVKqOVjQQvnzJ03AWGmY4KY9SRhrzceA0mWW92IlqXTR5Mw_TCoZXcRmlnhIByx84M20dFq8RT._7NmW3yvi.QXcf_h73x3qP7FAnX5EItYvMsPf9pRuwp4wbCFUia6nUGSxq3H5N_bgTm60eLnN7LlJkMXeSUD2479V_kgFIEOjh8Co; webmad_tl=1772375944',
            'Pragma': 'no-cache',
            'Priority': 'u=0, i',
            'Referer': 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+3d&pid=252',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"145.0.3800.82"',
            'sec-ch-ua-full-version-list': '"Not:A-Brand";v="99.0.0.0", "Microsoft Edge";v="145.0.3800.82", "Chromium";v="145.0.7632.117"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"19.0.0"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        })
        
        # 初始化时扫描现有文件并提取ID
        self.scan_existing_files()

    def scan_existing_files(self):
        """扫描现有MP4文件并提取ID"""
        print("正在扫描现有文件...")
        
        for mp4_file in self.target.rglob("*.mp4"):
            filename = mp4_file.stem  # 不包含扩展名
            
            # 尝试两种格式：artist - S06E01 - id.mp4 或 artist_id.mp4
            video_id = None
            
            # 格式2: artist_id.mp4
            if not video_id and "_" in filename:
                parts = filename.split("_")
                if len(parts) >= 2:
                    potential_id = parts[-1]
                    if potential_id.isdigit():
                        video_id = potential_id
            
            if video_id:
                self.existing_ids.add(video_id)
        
        print(f"扫描完成，找到 {len(self.existing_ids)} 个已存在的视频ID")
        
        # 保存到data-rule34.json
        self.save_existing_ids()

    def save_existing_ids(self):
        """保存已存在的ID到data-rule34.json"""
        data = {
            "rule34_data": list(self.existing_ids),
            "rule34_artist": []
        }
        
        with open("data-rule34.json", "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已保存 {len(self.existing_ids)} 个ID到 data-rule34.json")

    def load_existing_ids(self):
        """从data-rule34.json加载已存在的ID"""
        try:
            with open("data-rule34.json", "r", encoding="utf8") as f:
                data = json.load(f)
                self.existing_ids = set(data.get("rule34_data", []))
                print(f"从 data-rule34.json 加载了 {len(self.existing_ids)} 个已存在的ID")
        except FileNotFoundError:
            print("未找到 data-rule34.json 文件，将重新扫描")
            self.scan_existing_files()
        except Exception as e:
            print(f"加载 data-rule34.json 失败: {e}，将重新扫描")
            self.scan_existing_files()

    def get_page(self, artist):
        """获取页面URL列表"""
        url = 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+' + artist
        
        # 添加随机延时避免被检测
        time.sleep(random.uniform(1, 3))
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 获取所有页面URL
            urls = [url + "&pid=0"]
            paginator = soup.find("div", {"id": "paginator"})
            if paginator:
                for link in paginator.find_all("a"):
                    if not link.get("alt"):
                        href = link.get("href")
                        if href:
                            full_url = requests.compat.urljoin(url, href)
                            urls.append(full_url)
                            break
            
            print(f'{artist} 获取到 {len(urls)} 个页面')
            return {
                'artist': artist,
                'folder': artist,
                'urls': urls
            }
        except Exception as e:
            print(f'{artist} 获取页面失败: {e}')
            return None

    def get_page_and_video(self, artist, index):
        """合并第一阶段和第二阶段：获取页面URL并直接获取视频URL列表"""
        # 第一阶段：获取页面URL列表
        url = 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+' + artist
        
        # 添加随机延时避免被检测
        time.sleep(random.uniform(1, 3))
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 获取所有页面URL
            urls = [url + "&pid=0"]
            paginator = soup.find("div", {"id": "paginator"})
            if paginator:
                for link in paginator.find_all("a"):
                    if not link.get("alt"):
                        href = link.get("href")
                        if href:
                            full_url = requests.compat.urljoin(url, href)
                            urls.append(full_url)
            
            print(f'{index} {artist} 获取到 {len(urls)} 个页面')
            
            # 第二阶段：获取视频URL列表
            video_urls = []
            for page_url in urls:
                # 添加随机延时避免被检测
                time.sleep(random.uniform(1, 3))
                
                try:
                    response = self.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 获取视频链接
                    thumb_links = soup.find_all("span", class_="thumb")
                    for thumb in thumb_links:
                        link = thumb.find("a")
                        if link and link.get("href"):
                            full_url = requests.compat.urljoin(page_url, link.get("href"))
                            # 从URL中提取ID并检查是否已存在
                            try:
                                video_id = full_url.split("id=")[1].split("&")[0]
                                
                                if video_id in self.existing_ids:
                                    continue
                            except (IndexError, ValueError):
                                # 如果无法提取ID，继续处理
                                pass
                            
                            video_urls.append(full_url)
                    
                    print(f'{artist} {page_url}')
                    
                    
                except Exception as e:
                    print(f'{artist} {page_url} 获取视频链接失败: {e}')
            
            print(f'{artist} 获取到视频链接 {len(video_urls)} 条')
            return {
                'artist': artist,
                'folder': artist,
                'video_urls': video_urls
            }
            
        except Exception as e:
            print(f'{artist} 获取页面失败: {e}')
            return None

    def get_url(self, video_result, atag):
        """下载视频"""
        artist = video_result['artist']
        folder = video_result['folder']
        video_urls = video_result['video_urls']
        
        for index, video_url in enumerate(video_urls):
            tag = f"{atag} [{index}/{len(video_urls)}]"
            # 从URL中提取ID
            try:
                video_id = video_url.split("id=")[1].split("&")[0]
            except (IndexError, ValueError):
                print(f"{tag} {artist} {video_url} 无法提取ID，跳过")
                continue
            
            # 检查ID是否已存在
            if video_id in self.existing_ids:
                print(f"{tag} {artist} ID {video_id} 已存在，跳过")
                continue
            
            # 添加随机延时避免被检测
            time.sleep(random.uniform(1, 3))
            print(f"{tag} {artist} {video_url} 开始处理") 
            try:
                # print(f"正在请求页面: {video_url}")
                response = self.session.get(video_url, timeout=30)
                # print(f"页面响应状态: {response.status_code}")
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 获取视频源URL
                source = soup.find("source")
                if source and source.get("src"):
                    url = source.get("src")
                    url = requests.compat.urljoin(video_url, url)
                    name = f"{artist}_{url.split('?')[-1]}.mp4"
                    path = self.target / folder
                    url = url.split('?')[0]
                        

                    if not path.exists():
                        path.mkdir()

                    tmp_name = name + ".part"
                    tmp_file = path / tmp_name
                    final_file = path / name

                    try:
                        if tmp_file.exists():
                                tmp_file.unlink()
                        
                        # print(f"开始下载视频: {url}")
                        # 使用线程超时机制（跨平台）
                        import threading
                        
                        download_result = [None]
                        download_exception = [None]
                        
                        def download_worker():
                            try:
                                download_result[0] = download_video(url, url, tmp_file)
                            except Exception as e:
                                download_exception[0] = e
                        
                        # 启动下载线程
                        download_thread = threading.Thread(target=download_worker)
                        download_thread.daemon = True
                        download_thread.start()
                        
                        # 等待5分钟或线程完成
                        download_thread.join(timeout=300)
                        
                        if download_thread.is_alive():
                            print(f"{tag} {artist} {final_file} 下载超时")
                            if tmp_file.exists():
                                tmp_file.unlink()
                        elif download_exception[0]:
                            print(f"{tag} {artist} {final_file} 下载过程中出错: {download_exception[0]}")
                            if tmp_file.exists():
                                tmp_file.unlink()
                        elif download_result[0]:
                            tmp_file.rename(final_file)
                            # 下载成功后，将ID添加到已存在列表中
                            self.existing_ids.add(video_id)
                            print(f"{tag} {artist} {final_file} 下载成功")
                        else:
                            print(f"{tag} {artist} {final_file} 下载失败")
                            if tmp_file.exists():
                                tmp_file.unlink()
                    except Exception as e:
                        print(f"{tag} {artist} {final_file} 下载过程中出错: {e}")
                else:
                    print(f"{tag} {artist} {video_url} 未找到视频源")
                
            except requests.exceptions.Timeout:
                print(f'{tag} {artist} {video_url} 请求超时')
            except requests.exceptions.ConnectionError:
                print(f'{tag} {artist} {video_url} 连接错误')
            except Exception as e:
                print(f'{tag} {artist} {video_url} 处理失败: {e}')

    def load_stage_data(self, stage):
        """从JSON文件加载指定阶段的数据"""
        if stage == 1:
            file_path = "video_urls.json"
        else:
            return []
        
        try:
            with open(file_path, "r", encoding="utf8") as f:
                data = json.load(f)
                print(f"从 {file_path} 加载了 {len(data)} 条数据")
                return data
        except FileNotFoundError:
            print(f"未找到 {file_path} 文件")
            return []
        except Exception as e:
            print(f"加载 {file_path} 失败: {e}")
            return []

    def save_stage_data(self, stage, data):
        """保存指定阶段的数据到JSON文件"""
        if stage == 1:
            file_path = "video_urls.json"
            with open(file_path, "w", encoding="utf8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"阶段 {stage} 完成，保存了 {len(data)} 个结果到 {file_path}")

    def run(self):
        """执行分阶段爬取"""
        # 第一阶段：执行合并的 get_page_and_video
        if self.start_stage <= 1:
            print("=== 第一阶段：执行 get_page_and_video ===")
            artists = [artist.name for artist in self.target.iterdir() 
                      if artist.is_dir() and not artist.name.startswith('#')]
            
            # artists = artists[30:]

            for index, artist in enumerate(artists):
                if not (self.target/artist).exists():
                    (self.target/artist).mkdir()
                
                video_result = self.get_page_and_video(artist, index)
                if video_result:
                    self.video_results.append(video_result)
            
            # 保存第一阶段结果
            self.save_stage_data(1, self.video_results)
        else:
            # 从JSON文件加载第一阶段结果
            print("=== 跳过第一阶段，从JSON加载数据 ===")
            self.video_results = self.load_stage_data(1)
        
        # 第二阶段：执行所有 get_url
        print("=== 第二阶段：执行 get_url ===")
        for index, video_result in enumerate(self.video_results):
            self.get_url(video_result, f"[{index}/{len(self.video_results)}]")
        print("第二阶段完成，所有视频下载完成！")
        
        # 保存更新后的ID列表
        self.save_existing_ids()
        print("所有阶段执行完成！")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--stage', type=int, default=0, 
                       help='执行阶段: 0=全部执行, 1=跳过第一阶段')
    args = parser.parse_args()

    crawler = Rule34Crawler(start_stage=args.stage)
    crawler.run()