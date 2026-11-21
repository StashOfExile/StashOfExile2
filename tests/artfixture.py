"""Test helper (3.1, GGG ToS 7a - no game art ships with the app): poe.ninja's prices for a few items and their
pictures as the downloader would leave them in the art cache. The pictures in tests/fixtures/art are what
web.poecdn.com serves for those items (poe.ninja's image links); tests/ is never part of the built app."""
import hashlib
import json
import os
import shutil

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
CDN = "https://web.poecdn.com"


def parts():
    """poe.ninja's exchange answers for the fixture items (WPRICES.parts' shape)."""
    with open(os.path.join(HERE, "ninja_parts.json"), encoding="utf-8") as f:
        return json.load(f)


def url_of(path):
    return path if path.startswith("https://") else CDN + path


def picture(cid):
    return os.path.join(HERE, "art", cid + ".png")


def download(art_dir, only=None):
    """'Download' the fixture pictures into an art cache folder (the names rates_view.Icons gives them). only: ids."""
    os.makedirs(art_dir, exist_ok=True)
    n = 0
    for p in parts().values():
        for cid, path in (p.get("images") or {}).items():
            if only is not None and cid not in only:
                continue
            u = url_of(path)
            shutil.copy(picture(cid), os.path.join(art_dir, "cur_" + hashlib.sha1(u.encode()).hexdigest()[:20] + ".png"))
            n += 1
    return n


def download_waystone(art_dir):
    from soe2.pricecheck_page import WAYSTONE_ICON
    os.makedirs(art_dir, exist_ok=True)
    shutil.copy(picture("waystone15"),
                os.path.join(art_dir, "cur_" + hashlib.sha1(WAYSTONE_ICON.encode()).hexdigest()[:20] + ".png"))


def install(art=True):
    """WPRICES.parts = the fixture prices; their pictures in this run's art cache (config.P("art")) when art."""
    from soe2.config import P
    from soe2.wealth import WPRICES
    WPRICES.parts = parts()
    if art:
        download(P("art"))
