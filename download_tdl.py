import os
import json
import shutil
import subprocess
from pathlib import Path

TDL_DIR = Path(r"C:\Softwares\tdl_Windows_64bit")
SCRIPT_DIR = Path(__file__).parent
EXPORT_FILE = TDL_DIR / "tdl-export.json"

BLOCK_FILES = {(2462403115, '121212.mp4')}

CHANNELS = [
    {
        'url': 'https://t.me/xiaoPyixia1',
        'dir': Path(r"D:\Porn-CN\【AI生成】\xiaoPyixia1"),
        'check_sound': True
    },
    {
        'url': 'https://t.me/Mistralaiai',
        'dir': Path(r"D:\Porn-CN\【AI生成】\Mistralaiai"),
        'check_sound': False
    },
    {
        'url': 'https://t.me/tiktok825',
        'dir': Path(r"D:\Porn-Web\Telegram-tiktok825"),
        'check_sound': False
    },
]

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

def process_channel(channel):
    url = channel['url']
    target_dir = channel['dir']
    check_sound = channel['check_sound']
    
    print(f"\n{'='*60}")
    print(f"处理频道: {url}")
    print(f"目标目录: {target_dir}")
    print('='*60)
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    print("1. 导出聊天记录...")
    if not run_command(r".\tdl.exe chat export -c " + url, cwd=TDL_DIR):
        print("   导出失败，跳过")
        return False
    
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
                new_name = f"{chat_id}_{msg['id']}_{file_name.replace(' ', '_')}"
                all_videos.append({
                    'msg_id': msg['id'],
                    'original': file_name,
                    'new_name': new_name
                })
    
    print(f"   总共找到 {len(all_videos)} 个视频文件")
    
    if not all_videos:
        print("   没有视频文件，跳过")
        return True
    
    print("3. 过滤屏蔽文件...")
    def is_blocked(v):
        return (int(chat_id), v['original']) in BLOCK_FILES
    
    all_videos = [v for v in all_videos if not is_blocked(v)]
    print(f"   屏蔽后剩余: {len(all_videos)} 个视频文件")
    
    print("4. 过滤已存在的文件...")
    existing_files = set()
    for f in target_dir.iterdir():
        if f.is_file():
            existing_files.add(f.name)
    if check_sound:
        no_sound_dir = target_dir.parent / (target_dir.name + ' - no_sound')
        if no_sound_dir.exists():
            for f in no_sound_dir.iterdir():
                if f.is_file():
                    existing_files.add(f.name)
    
    remaining = [v for v in all_videos if v['new_name'] not in existing_files]
    print(f"   需要下载: {len(remaining)} 个视频文件")
    print(f"   已存在: {len(all_videos) - len(remaining)} 个视频文件")
    
    if not remaining:
        print("5. 没有需要下载的文件")
        return True
    
    print("5. 更新JSON并下载...")
    messages_to_keep = [{'id': v['msg_id'], 'type': 'message', 'file': v['original']} for v in remaining]
    new_data = {'id': int(chat_id), 'messages': messages_to_keep}
    
    with open(EXPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    print(f"   JSON已更新，包含 {len(messages_to_keep)} 个文件")
    
    if not run_command(rf".\tdl.exe dl -f .\tdl-export.json -d {target_dir}", cwd=TDL_DIR):
        print("   下载失败")
        return False
    
    print("6. 下载完成")
    
    if check_sound:
        print("7. 检查无声视频...")
        new_files = ','.join(v['new_name'] for v in remaining)
        original_dir = os.getcwd()
        os.chdir(target_dir)
        result = subprocess.run(['python', str(SCRIPT_DIR / 'check_sound.py'), new_files], capture_output=True)
        os.chdir(original_dir)
        if result.stdout:
            print(result.stdout.decode('utf-8', errors='replace'))
    else:
        print("7. 跳过音轨检查")
    
    return True

def main():
    for i, channel in enumerate(CHANNELS):
        process_channel(channel)
    print("\n全部完成！")

if __name__ == "__main__":
    main()
