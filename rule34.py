import platform
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from tqdm import tqdm
import json
import time
import threading
import logging


def download_video(url, ref, filename):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': ref,
            'Origin': ref
        }

        print(f"开始下载: {url}")
        response = requests.get(url, stream=True, headers=headers, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('Content-Length', 0))
        print(f"文件大小: {total_size} bytes")

        block_size = 1024
        progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True)
        progress_bar.set_description(filename.name)

        with open(filename, 'wb') as f:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                f.write(data)

        progress_bar.close()
        
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


logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)


def get_data_path():
    if platform.system() == "Windows":
        return r"D:\Hentai-Rule34"
    else:
        return "/data/Hentai-Rule34"


class Rule34Crawler:
    def __init__(self):
        self.target = Path(get_data_path())
        self.existing_ids = set()
        
        cookie_file = Path(__file__).parent / "rule34-cookie.txt"
        if cookie_file.exists():
            cookie = cookie_file.read_text(encoding="utf8").strip()
        else:
            raise FileNotFoundError(f"未找到 cookie 文件: {cookie_file}")

        self.session = requests.Session()
        self.session.headers.update({
            'Host': 'rule34.xxx',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Cookie': cookie,
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
        
        self.scan_existing_files()

    def scan_existing_files(self):
        print("正在扫描现有文件...")
        
        for mp4_file in self.target.rglob("*.mp4"):
            filename = mp4_file.stem
            video_id = None
            
            if not video_id and "_" in filename:
                parts = filename.split("_")
                if len(parts) >= 2:
                    potential_id = parts[-1]
                    if potential_id.isdigit():
                        video_id = potential_id
            
            if video_id:
                self.existing_ids.add(video_id)
        
        print(f"扫描完成，找到 {len(self.existing_ids)} 个已存在的视频ID")
        self.save_existing_ids()

    def save_existing_ids(self):
        data = {
            "rule34_data": list(self.existing_ids),
            "rule34_artist": []
        }
        
        with open("data-rule34.json", "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已保存 {len(self.existing_ids)} 个ID到 data-rule34.json")

    def download_one(self, video_url, video_id, artist):
        print(f"{artist} {video_url} 开始处理") 
        try:
            response = self.session.get(video_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            source = soup.find("source")
            if source and source.get("src"):
                url = source.get("src")
                url = requests.compat.urljoin(video_url, url)
                name = f"{artist}_{url.split('?')[-1]}.mp4"
                path = self.target / artist
                url = url.split('?')[0]
                
                if not path.exists():
                    path.mkdir()

                tmp_name = name + ".part"
                tmp_file = path / tmp_name
                final_file = path / name

                try:
                    if tmp_file.exists():
                        tmp_file.unlink()
                    
                    download_result = [None]
                    download_exception = [None]

                    def download_worker():
                        try:
                            download_result[0] = download_video(url, url, tmp_file)
                        except Exception as e:
                            download_exception[0] = e

                    download_thread = threading.Thread(target=download_worker)
                    download_thread.daemon = True
                    download_thread.start()
                    download_thread.join(timeout=300)
                    
                    if download_thread.is_alive():
                        print(f"{artist} {final_file} 下载超时")
                        if tmp_file.exists():
                            tmp_file.unlink()
                    elif download_exception[0]:
                        print(f"{artist} {final_file} 下载出错: {download_exception[0]}")
                        if tmp_file.exists():
                            tmp_file.unlink()
                    elif download_result[0]:
                        tmp_file.rename(final_file)
                        self.existing_ids.add(video_id)
                        print(f"{artist} {final_file} 下载成功")
                    else:
                        print(f"{artist} {final_file} 下载失败")
                        if tmp_file.exists():
                            tmp_file.unlink()
                except Exception as e:
                    print(f"{artist} {final_file} 下载出错: {e}")
            else:
                print(f"{artist} {video_url} 未找到视频源")
            
        except requests.exceptions.Timeout:
            print(f'{artist} {video_url} 请求超时')
        except requests.exceptions.ConnectionError:
            print(f'{artist} {video_url} 连接错误')
        except Exception as e:
            print(f'{artist} {video_url} 处理失败: {e}')


if __name__ == "__main__":
    crawler = Rule34Crawler()
    
    artists = [artist.name for artist in crawler.target.iterdir() 
              if artist.is_dir() and not artist.name.startswith('#')]
    
    for index, artist in enumerate(artists):
        if not (crawler.target/artist).exists():
            (crawler.target/artist).mkdir()
        
        url = 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+' + artist
        
        try:
            response = crawler.session.get(url, timeout=30)
            if response.status_code == 403:
                print(f'{artist} 遇到 403，暂停 20s 后重试')
                time.sleep(20)
                response = crawler.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
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
            
            print(f'{index} {artist} 获取到 {len(urls)} 个页面')
            
            for page_url in urls:
                try:
                    response = crawler.session.get(page_url, timeout=30)
                    if response.status_code == 403:
                        print(f'{artist} 遇到 403，暂停 20s 后重试')
                        time.sleep(20)
                        response = crawler.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    thumb_links = soup.find_all("span", class_="thumb")
                    for thumb in thumb_links:
                        link = thumb.find("a")
                        if link and link.get("href"):
                            video_url = requests.compat.urljoin(page_url, link.get("href"))
                            
                            try:
                                video_id = video_url.split("id=")[1].split("&")[0]
                                if video_id in crawler.existing_ids:
                                    continue
                            except (IndexError, ValueError):
                                pass
                            
                            crawler.download_one(video_url, video_id, artist)
                    
                    print(f'{artist} {page_url}')
                    
                except Exception as e:
                    print(f'{artist} {page_url} 获取视频链接失败: {e}')
        
        except Exception as e:
            print(f'{artist} 获取页面失败: {e}')
    
    crawler.save_existing_ids()
    print("完成！")