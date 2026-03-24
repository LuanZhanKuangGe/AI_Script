import argparse
import json
import requests
from tqdm import tqdm
from pathlib import Path


def list_files(directory):
    path = Path(directory)
    files = [f for f in path.iterdir() if f.is_file()]
    return files


def list_folders(directory):
    path = Path(directory)
    folders = [f for f in path.iterdir() if f.is_dir()]
    folders.sort(key=lambda x: x.name)
    return folders


class Iwara():

    target = Path(r"/data/Hentai-MMD")
    database={}
    database["mmd_data"] = []
    database["mmd_artist"] = []
    database["mmd_new"] = []

    def update(self):
        # 更新mmd数据
        # 新建iwara.txt
        with open("iwara.txt", "w", encoding="utf8") as f:
            for folder in tqdm(list(self.target.iterdir()), desc="update MMD"):
                if folder.is_dir() and not folder.name.startswith('[Del]') and not folder.name.startswith('#未整理'):
                    for video in folder.rglob("*.mp4"):
                        video_id = video.stem.replace('[Source]', '')
                        video_id = video_id.split('[')[-1].split(']')[0].lower()
                        if video_id not in self.database["mmd_data"]:
                            self.database["mmd_data"].append(video_id)
                            if video.parent.name == '#Download':
                                self.database["mmd_new"].append(video_id)
                                f.write(video_id + "\n")
                        else:
                            if video_id != 'deleted':
                                print("发现重复文件：", video)
                    if folder.name.startswith('['):
                        artist = folder.name.split(']')[0].split('[')[1]
                        if artist not in self.database["mmd_artist"]:
                            self.database["mmd_artist"].append(artist)
                        else:
                            print("发现重复作者：", artist)

        with open("data-iwara.json", "w", encoding="utf8") as fp:
            json.dump(self.database, fp, ensure_ascii=False)

    def new(self):
        folder_names = {}
        folders = list_folders(self.target)
        for folder in folders:
            if folder.is_dir() and not folder.name.startswith('[Del]') and folder.name.startswith('['):
                user_name = folder.name.split('[')[1].split(']')[0]
                folder_names[user_name] = folder

        files = list_files(self.target/"#Download")

        new_iwara_data = []
        with open("iwara_videos.json", "r", encoding="utf8") as fp:
            new_iwara_data = json.load(fp)

        for index, file in enumerate(files):
            print(f"正在处理[{index+1}/{len(files)}]: {file.name}")

            if '[' in file.name and ']' in file.name:
                video_id = file.name.replace('[Source]','').split('[')[-1].split(']')[0]
                print(f"视频ID: {video_id}")

                found_data = False
                for dict in new_iwara_data:
                    if dict['id'].lower() == video_id.lower():
                        if not dict.get('user'):
                            break
                        user_id = dict['user']['username']
                        user_name = dict['user']['name']
                        
                        if folder_names.get(user_id) is not None:
                            folder_path = folder_names[user_id]
                        else:
                            folder_path = self.target/f"[{user_id}] {user_name}"
                        
                        Path(folder_path).mkdir(parents=True, exist_ok=True)
                        file.rename(Path(folder_path, file.name))
                        print(f"已移动到 {folder_path}")
                        found_data = True
                        break
                if not found_data:
                    print(f"获取视频信息失败")
            else:
                print(f"在文件名 {file.name} 中未找到ID")

if __name__ == "__main__":
    iwara_instance = Iwara()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--update', action='store_true')
    parser.add_argument('-n', '--new', action='store_true')
    args = parser.parse_args()

    iwara = Iwara()
    if args.update:
        iwara.update()
    if args.new:
        iwara.new()