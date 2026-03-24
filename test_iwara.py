import json

new_iwara_data = []
with open("iwara_videos.json", "r", encoding="utf8") as fp:
    new_iwara_data = json.load(fp)
print(new_iwara_data[0]['id'])
print(new_iwara_data[0]['user']['username'])
print(new_iwara_data[0]['user']['name'])