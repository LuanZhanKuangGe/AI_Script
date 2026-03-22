import os
import shutil
import subprocess

def has_audio(file_path):
    """
    使用 ffprobe 检查视频文件是否包含音频流
    """
    command = [
        'ffprobe', 
        '-i', file_path, 
        '-show_streams', 
        '-select_streams', 'a', 
        '-loglevel', 'error'
    ]
    try:
        # 如果没有音频流，ffprobe 的输出会是空的
        output = subprocess.check_output(command).decode('utf-8')
        return len(output) > 0
    except subprocess.CalledProcessError:
        return False

def move_silent_videos(source_dir):
    # 定义目标文件夹
    target_dir = os.path.join(source_dir, 'no_sound')
    
    # 如果不存在则创建
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"已创建目录: {target_dir}")

    # 遍历当前目录下的文件
    for filename in os.listdir(source_dir):
        if filename.lower().endswith('.mp4'):
            file_path = os.path.join(source_dir, filename)
            
            # 检查是否没有声音
            if not has_audio(file_path):
                print(f"发现无声视频: {filename} -> 移动中...")
                shutil.move(file_path, os.path.join(target_dir, filename))
            else:
                print(f"有声视频: {filename} - 跳过")

if __name__ == "__main__":
    # 使用当前脚本所在目录，你也可以指定绝对路径
    current_directory = os.getcwd()
    move_silent_videos(current_directory)
    print("\n任务完成！")