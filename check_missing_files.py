import os
import re
from pathlib import Path

BASE_DIR = Path(r"D:\JAV")
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.m4v', '.wmv'}
REQUIRED_FILES = ['.nfo', '-fanart.jpg', '-poster.jpg']

def check_project(folder_path):
    folder_name = folder_path.name
    files = list(folder_path.iterdir())
    file_names = [f.name for f in files]
    
    video_files = [f for f in file_names if f.startswith(folder_name) and Path(f).suffix.lower() in VIDEO_EXTENSIONS]
    missing = []
    
    for req in REQUIRED_FILES:
        pattern = folder_name + req
        if pattern not in file_names:
            missing.append(pattern)
    
    if missing or not video_files:
        return {
            'folder': str(folder_path),
            'name': folder_name,
            'has_video': bool(video_files),
            'videos': video_files,
            'missing': missing
        }
    return None

def main():
    missing_projects = []
    
    for subdir in sorted(BASE_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        
        for project_folder in sorted(subdir.iterdir()):
            if not project_folder.is_dir():
                continue
            
            result = check_project(project_folder)
            if result:
                missing_projects.append(result)
    
    if missing_projects:
        print(f"找到 {len(missing_projects)} 个项目缺少文件:\n")
        for p in missing_projects:
            print(f"文件夹: {p['folder']}")
            print(f"  项目名: {p['name']}")
            if not p['has_video']:
                print(f"  缺少: 视频文件")
            if p['missing']:
                print(f"  缺少: {', '.join(p['missing'])}")
            print()
    else:
        print("所有项目都完整！")

if __name__ == '__main__':
    main()
