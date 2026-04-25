if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--artist', type=str, help='指定 artist 名称下载全部页面')
    args = parser.parse_args()

    crawler = Rule34Crawler()

    if args.artist:
        artist = args.artist
        if not (crawler.target / artist).exists():
            (crawler.target / artist).mkdir()

        print(f'=== 下载 {artist} 全部页面和视频 ===')

        url = 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+' + artist

        time.sleep(random.uniform(1, 5))

        try:
            response = crawler.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            urls = []
            paginator = soup.find("div", {"id": "paginator"})
            if paginator:
                for link in paginator.find_all("a"):
                    if not link.get("alt"):
                        href = link.get("href")
                        if href:
                            full_url = requests.compat.urljoin(url, href)
                            urls.append(full_url)
            else:
                urls.append(url + "&pid=0")

            print(f'{artist} 获取到 {len(urls)} 个页面')

            for page_url in urls:
                time.sleep(random.uniform(1, 5))
                try:
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
        print(f'{artist} 完成！')
        exit(0)

    # 默认模式：遍历所有 artist
    artists = [artist.name for artist in crawler.target.iterdir() 
              if artist.is_dir() and not artist.name.startswith('#')]
    
    for index, artist in enumerate(artists):
        if not (crawler.target/artist).exists():
            (crawler.target/artist).mkdir()
        
        last_run = crawler.artist_last_run.get(artist)
        if last_run:
            elapsed = time.time() - last_run
            if elapsed < 3600:
                print(f'{artist} 上次处理未满1小时，跳过')
                continue
        
        url = 'https://rule34.xxx/index.php?page=post&s=list&tags=video+sound+' + artist
        
        time.sleep(random.uniform(1, 5))
        
        downloaded = False
        
        try:
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
                time.sleep(random.uniform(1, 5))
                try:
                    response = crawler.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    thumb_links = soup.find_all("span", class_="thumb")
                    new_count = 0
                    for thumb in thumb_links:
                        link = thumb.find("a")
                        if link and link.get("href"):
                            video_url = requests.compat.urljoin(page_url, link.get("href"))
                            
                            try:
                                video_id = video_url.split("id=")[1].split("&")[0]
                                if video_id in crawler.existing_ids:
                                    continue
                                new_count += 1
                            except (IndexError, ValueError):
                                pass
                            
                            crawler.download_one(video_url, video_id, artist)
                            downloaded = True
                    
                    if new_count == 0:
                        print(f'{artist} {page_url} 无新视频，跳过剩余页面')
                        break
                    
                    print(f'{artist} {page_url}')
                    
                except Exception as e:
                    print(f'{artist} {page_url} 获取视频链接失败: {e}')
            
            if not downloaded:
                crawler.artist_last_run[artist] = time.time()
                crawler.save_artist_last_run()
        
        except Exception as e:
            print(f'{artist} 获取页面失败: {e}')
    
    crawler.save_existing_ids()
    print("完成！")