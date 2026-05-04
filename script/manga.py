from pathlib import Path
from tqdm import tqdm
import json

database = {"manga": {}}

def add_manga(manga):
    if "] " not in manga.stem:
        print(manga)
        return
    manga_artist = manga.stem.split("] ", 1)[0] + "]"
    name = manga.stem.split("] ", 1)[1]
    if manga_artist not in database['manga']:
        database['manga'][manga_artist] = []
    database['manga'][manga_artist].append(name)


from all_path import HENTAI_PICTURE_MANGA

for item in tqdm(list(HENTAI_PICTURE_MANGA.iterdir()), desc="update Manga"):
    if item.is_dir():
        for file in item.iterdir():
            add_manga(file)
    if item.is_file():
        add_manga(item)

with open("data-manga.json", "w", encoding="utf8") as fp:
    json.dump(database, fp, ensure_ascii=False)