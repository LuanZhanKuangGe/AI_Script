import os
import re
from pathlib import Path

base_dir = r"D:\Porn-CN\【裸舞】"
keywords = ['#主播', '#福利姬', '#舞团', '#顶级', '#人上人', '#夯', '#NPC']

print("正在检查文件命名格式...\n")

folders = [f for f in Path(base_dir).iterdir() if f.is_dir()]
total_folders = len(folders)

correct_files = []
incorrect_files = []

for idx, folder in enumerate(folders, 1):
    print(f"\r进度: {idx}/{total_folders}", end='')
    
    folder_name = folder.name
    cleaned_folder = folder_name
    for kw in keywords:
        cleaned_folder = cleaned_folder.replace(kw, '')
    cleaned_folder = cleaned_folder.strip()
    
    folder_issues = []
    
    for file in folder.iterdir():
        if not file.is_file():
            continue
        
        name = file.stem
        
        if ' - ' in name:
            parts = name.split(' - ', 1)
            if len(parts) == 2:
                file_part = parts[0].strip()
                md5 = parts[1].strip()
                
                if len(md5) == 32 and re.match(r'^[a-f0-9]+$', md5):
                    if file_part == cleaned_folder or file_part.startswith(cleaned_folder + ' '):
                        correct_files.append(str(file))
                    else:
                        folder_issues.append((file, name, md5))
                else:
                    folder_issues.append((file, name, None))
            else:
                folder_issues.append((file, name, None))
        else:
            folder_issues.append((file, name, None))
    
    if folder_issues:
        incorrect_files.extend([f[0] for f in folder_issues])
        
        print(f"\n\n=== 文件夹: {folder.name} ===")
        print(f"清理后的名称: {cleaned_folder}")
        print(f"问题文件数: {len(folder_issues)}")
        for file, old_name, md5 in folder_issues:
            if md5:
                print(f"  {old_name} -> {cleaned_folder} - {md5}")
            else:
                print(f"  {old_name} [无有效MD5]")
        
        while True:
            resp = input("\n是否修正? (y/n/q): ").strip().lower()
            if resp == 'y':
                for file, old_name, md5 in folder_issues:
                    if md5:
                        new_name = f"{cleaned_folder} - {md5}{file.suffix}"
                        new_path = file.parent / new_name
                        try:
                            file.rename(new_path)
                            print(f"  重命名: {old_name} -> {new_name}")
                        except Exception as e:
                            print(f"  失败: {old_name} - {e}")
                break
            elif resp == 'n':
                break
            elif resp == 'q':
                print("\n用户取消")
                exit()

print(f"\n\n=== 符合格式的文件: {len(correct_files)} 个 ===")
print(f"=== 不符合格式的文件: {len(incorrect_files)} 个 ===")