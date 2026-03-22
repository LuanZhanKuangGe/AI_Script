import os
import json
import shutil
import subprocess
from pathlib import Path

TDL_DIR = Path(r"C:\Softwares\tdl_Windows_64bit")
CHAT_URL = "https://t.me/xiaoPyixia1"
TARGET_DIR = Path(r"D:\Porn-CN\【AI生成】\xiaoPyixia1")
SCRIPT_DIR = Path(__file__).parent
EXPORT_FILE = TDL_DIR / "tdl-export.json"

def run_command(cmd, cwd=None, show_output=True):
    process = subprocess.Popen(
        cmd, shell=True, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, encoding='utf-8', errors='replace'
    )
    for line in process.stdout:
        if show_output:
            print(line, end='')
    process.wait()
    return process.returncode == 0

def export_chat():
    print("1. 导出聊天记录...")
    return run_command(r".\tdl.exe chat export -c " + CHAT_URL, cwd=TDL_DIR)

def parse_exported_files():
    print("2. 解析导出文件...")
    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chat_id = str(data['id'])
    messages = data['messages']
    
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v'}
    all_videos = []
    
    for msg in messages:
        if msg.get('type') == 'message' and 'file' in msg:
            file_name = msg['file']
            ext = Path(file_name).suffix.lower()
            if ext in video_extensions:
                new_name = f"{chat_id}_{msg['id']}_{file_name}"
                all_videos.append({
                    'msg_id': msg['id'],
                    'original': file_name,
                    'new_name': new_name
                })
    
    print(f"   总共找到 {len(all_videos)} 个视频文件")
    return chat_id, all_videos

def filter_existing_files(chat_id, all_videos):
    print("3. 过滤已存在的文件...")
    existing_files = set()
    for f in TARGET_DIR.iterdir():
        if f.is_file():
            existing_files.add(f.name)
    no_sound_dir = TARGET_DIR / "no_sound"
    if no_sound_dir.exists():
        for f in no_sound_dir.iterdir():
            if f.is_file():
                existing_files.add(f.name)
    
    remaining = []
    for file_info in all_videos:
        if file_info['new_name'] not in existing_files:
            remaining.append(file_info)
    
    print(f"   需要下载: {len(remaining)} 个视频文件")
    print(f"   已存在: {len(all_videos) - len(remaining)} 个视频文件")
    return remaining

def update_json_and_download(chat_id, files_to_download):
    print("4. 更新JSON并下载...")
    if not files_to_download:
        print("   没有需要下载的文件")
        return True
    
    messages_to_keep = []
    for file_info in files_to_download:
        messages_to_keep.append({
            'id': file_info['msg_id'],
            'type': 'message',
            'file': file_info['original']
        })
    
    new_data = {'id': int(chat_id), 'messages': messages_to_keep}
    
    with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
        verify = json.load(f)
    print(f"   JSON已更新，包含 {len(verify['messages'])} 个文件")
    
    return run_command(r".\tdl.exe dl -f .\tdl-export.json", cwd=TDL_DIR)

def move_downloaded_files(chat_id):
    print("5. 移动下载的文件...")
    download_dir = TDL_DIR / "downloads"
    moved_count = 0
    
    if download_dir.exists():
        for f in download_dir.iterdir():
            if f.is_file() and f.suffix.lower() in {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v'}:
                shutil.move(str(f), TARGET_DIR / f.name)
                moved_count += 1
    
    print(f"   移动了 {moved_count} 个文件到 {TARGET_DIR}")
    return moved_count > 0

def check_sound():
    print("6. 检查无声视频...")
    original_dir = os.getcwd()
    os.chdir(TARGET_DIR)
    result = subprocess.run(['python', str(SCRIPT_DIR / 'check_sound.py')], capture_output=True)
    os.chdir(original_dir)
    if result.stdout:
        print(result.stdout.decode('utf-8', errors='replace'))

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    if not export_chat():
        print("导出失败，退出")
        return
    
    chat_id, all_videos = parse_exported_files()
    if not all_videos:
        print("没有找到视频文件")
        return
    
    remaining = filter_existing_files(chat_id, all_videos)
    if not update_json_and_download(chat_id, remaining):
        print("下载失败，退出")
        return
    
    move_downloaded_files(chat_id)
    check_sound()
    print("\n全部完成！")

if __name__ == "__main__":
    main()
