#!/usr/bin/env python3
"""裁剪fanart图片为poster"""

import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image

def crop_and_save(input_path):
    output_path = input_path.replace('-fanart.jpg', '-poster.jpg')
    
    with Image.open(input_path) as img:
        width, height = img.size
        print(f"  原图尺寸: {width}x{height}")
        
        left = width - 379
        right = width
        top = 0
        bottom = height
        
        cropped = img.crop((left, top, right, bottom))
        cropped.save(output_path, quality=95)
        print(f"  已保存: {output_path}")

def main():
    root = tk.Tk()
    root.withdraw()
    
    folder = filedialog.askdirectory(title="选择包含fanart图片的文件夹")
    if not folder:
        print("未选择文件夹")
        return
    
    print(f"\n扫描文件夹: {folder}\n")
    
    files = os.listdir(folder)
    fanart_files = [f for f in files if f.endswith('-fanart.jpg')]
    
    if not fanart_files:
        print("未找到-fanart.jpg文件")
        return
    
    print(f"找到 {len(fanart_files)} 个文件:\n")
    
    for filename in fanart_files:
        input_path = os.path.join(folder, filename)
        print(f"处理: {filename}")
        try:
            crop_and_save(input_path)
        except Exception as e:
            print(f"  错误: {e}")
    
    print(f"\n完成! 共处理 {len(fanart_files)} 个文件")

if __name__ == "__main__":
    main()
