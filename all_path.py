import platform
from pathlib import Path


def _make_path(windows_path: str, linux_path: str) -> Path:
    if platform.system() == "Windows":
        return Path(windows_path)
    return Path(linux_path)


def make_data_path(name: str) -> Path:
    if platform.system() == "Windows":
        return Path(rf"D:\{name}")
    return Path(f"/data/{name}")


# Hentai
HENTAI_RULE34 = _make_path(r"D:\Hentai-Rule34", "/data/Hentai-Rule34")
HENTAI_VIDEO_HANIME = _make_path(r"D:\Hentai-Video\hanime.tv", "/data/Hentai-Video/hanime.tv")
HENTAI_PICTURE_MANGA = _make_path(r"D:\Hentai-Picture\Manga", "/data/Hentai-Picture/Manga")
HENTAI_MMD = _make_path(r"D:\Hentai-MMD", "/data/Hentai-MMD")

# JAV
JAV = _make_path(r"D:\JAV", "/data/JAV")

# Porn-Web
PORN_WEB_REELSMUNKEY = _make_path(r"D:\Porn-Web\reelsmunkey", "/data/Porn-Web/reelsmunkey")
PORN_WEB_REDDCLIPS = _make_path(r"D:\Porn-Web\reddclips", "/data/Porn-Web/reddclips")
PORN_WEB_FYPTT = _make_path(r"D:\Porn-Web\fyptt", "/data/Porn-Web/fyptt")
PORN_WEB_XXXFOLLOW = _make_path(r"D:\Porn-Web\xxxfollow", "/data/Porn-Web/xxxfollow")
PORN_WEB_WAPTAP = _make_path(r"D:\Porn-Web\waptap", "/data/Porn-Web/waptap")
PORN_WEB_TIKPORN = _make_path(r"D:\Porn-Web\tikporn", "/data/Porn-Web/tikporn")
PORN_WEB_SHARESOME = _make_path(r"D:\Porn-Web\sharesome", "/data/Porn-Web/sharesome")
PORN_WEB_ONLYTIK = _make_path(r"D:\Porn-Web\onlytik", "/data/Porn-Web/onlytik")
PORN_WEB_OGFAP = _make_path(r"D:\Porn-Web\ogfap", "/data/Porn-Web/ogfap")
PORN_WEB_HOTSCOPE = _make_path(r"D:\Porn-Web\hotscope", "/data/Porn-Web/hotscope")
PORN_WEB_FIKFAP = _make_path(r"D:\Porn-Web\fikfap", "/data/Porn-Web/fikfap")

# Porn-CN
PORN_CN_LUOWU = _make_path(r"D:\Hentai-Dance", "/data/Hentai-Dance")

# Porn-CN-Short
PORN_CN_SHORT_XIAOPYIXIA1 = _make_path(r"D:\Hentai-AI\xiaoPyixia1", "/data/Hentai-AI/xiaoPyixia1")
PORN_CN_SHORT_MISTRALAIAI = _make_path(r"D:\Hentai-AI\Mistralaiai", "/data/Hentai-AI/Mistralaiai")

# Porn-VR
PORN_VR = _make_path(r"D:\Porn-VR", "/data/Porn-VR")
