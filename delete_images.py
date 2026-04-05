import sys
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg', '.ico'}


def delete_images(folder: Path):
    count = 0
    for img in folder.rglob('*'):
        if img.is_file() and img.suffix.lower() in IMAGE_EXTENSIONS:
            img.unlink()
            count += 1
    return count


def main():
    if len(sys.argv) < 2:
        print("用法: python delete_images.py <文件夹路径>")
        return

    folder = Path(sys.argv[1])
    if not folder.exists() or not folder.is_dir():
        print(f"文件夹不存在: {folder}")
        return

    print(f"删除文件夹中的图片: {folder}")
    count = delete_images(folder)
    print(f"已删除 {count} 个图片文件")


if __name__ == "__main__":
    main()