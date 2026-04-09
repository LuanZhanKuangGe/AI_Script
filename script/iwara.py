import argparse
import json
from pathlib import Path
from tqdm import tqdm

TARGET = Path(r"/data/Hentai-MMD")


def update():
    database = {"mmd_data": [], "mmd_artist": [], "mmd_new": []}
    
    with open("iwara.txt", "w", encoding="utf8") as f:
        for folder in tqdm(TARGET.iterdir(), desc="update MMD"):
            if not folder.is_dir() or folder.name.startswith('[Del]') or folder.name.startswith('#未整理'):
                continue
            
            for video in folder.rglob("*.mp4"):
                video_id = video.stem.replace('[Source]', '').split('[')[-1].split(']')[0].lower()
                if video_id in database["mmd_data"]:
                    if video_id != 'deleted':
                        print("发现重复文件：", video)
                    continue
                
                database["mmd_data"].append(video_id)
                if video.parent.name == '#Download':
                    database["mmd_new"].append(video_id)
                    f.write(video_id + "\n")
            
            if folder.name.startswith('['):
                artist = folder.name.split(']')[0].split('[')[1]
                if artist in database["mmd_artist"]:
                    print("发现重复作者：", artist)
                else:
                    database["mmd_artist"].append(artist)

    with open("data-iwara.json", "w", encoding="utf8") as fp:
        json.dump(database, fp, ensure_ascii=False)


def new():
    folder_names = {
        folder.name.split('[')[1].split(']')[0]: folder
        for folder in TARGET.iterdir()
        if folder.is_dir() and folder.name.startswith('[') and not folder.name.startswith('[Del]')
    }
    
    files = [f for f in (TARGET / "#Download").iterdir() if f.is_file()]
    
    with open("iwara_videos.json", "r", encoding="utf8") as fp:
        new_iwara_data = json.load(fp)
    
    for index, file in enumerate(files):
        if '[' not in file.name or ']' not in file.name:
            print(f"在文件名 {file.name} 中未找到ID")
            continue
        
        video_id = file.name.replace('[Source]', '').split('[')[-1].split(']')[0]
        print(f"正在处理[{index+1}/{len(files)}]: {file.name}, 视频ID: {video_id}")
        
        for data in new_iwara_data:
            if data['id'].lower() == video_id.lower() and data.get('user'):
                user_id = data['user']['username']
                user_name = data['user']['name']
                folder_path = folder_names.get(user_id, TARGET / f"[{user_id}] {user_name}")
                folder_path.mkdir(parents=True, exist_ok=True)
                file.rename(folder_path / file.name)
                print(f"已移动到 {folder_path}")
                break
        else:
            print(f"获取视频信息失败")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--update', action='store_true')
    parser.add_argument('-n', '--new', action='store_true')
    args = parser.parse_args()

    if args.update:
        update()
    if args.new:
        new()
