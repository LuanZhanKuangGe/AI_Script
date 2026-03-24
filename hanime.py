from pathlib import Path
from tqdm import tqdm
import json


database = {"hanime_data": []}

for video in tqdm(list(Path(r"/data/Hentai-Video/hanime.tv").rglob("*.mp4")), desc="update hanime"):
    title = ('-').join(video.stem.split('-')[0:-2])
    database["hanime_data"].append(title)

with open("data-hanime.json", "w", encoding="utf8") as fp:
    json.dump(database, fp, ensure_ascii=False)