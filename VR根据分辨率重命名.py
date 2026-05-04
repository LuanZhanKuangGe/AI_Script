import os
import cv2
from pathlib import Path


def get_video_width(filepath):
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()
    return width


def width_to_k(width):
    if width is None:
        return None
    k = round(width / 1000)
    return f"{k}k"


def rename_videos_with_resolution():
    from all_path import PORN_VR as target_dir
    if not target_dir.exists():
        print(f"目录不存在: {target_dir}")
        return

    for filename in os.listdir(target_dir):
        if filename.lower().endswith('.mp4') and '] [' not in filename:
            print(filename)
            filepath = target_dir / filename
            width = get_video_width(str(filepath))
            k_str = width_to_k(width)
            parts = filename.split(' ')
            company = parts[0].strip() if len(parts) > 0 else ""
            title = parts[1].strip() if len(parts) > 1 else ""
            if k_str and company and title:
                new_name = f"{company} [{k_str}] {title}"
                new_path = target_dir / new_name
                if not new_path.exists():
                    print(f"重命名 {filename} 为 {new_name}")
                    os.rename(filepath, new_path)
                else:
                    print(f"文件 {new_name} 已存在，跳过重命名。")


if __name__ == "__main__":
    rename_videos_with_resolution()