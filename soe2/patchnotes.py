"""3.3.0 owner: Patch Notes on the Dashboard. Grinding Gear Games posts every patch's notes as a Steam news post, so
the notes come from Steam's public news feed for Path of Exile 2. Not from the forum: its layout changes at 1.0, and
Steam's feed stays the same. Checked once every 6 hours, in the background; the last list is kept on this PC."""
import re
import threading
import time

from . import buglog
from .config import APP_UA, load_json, save_json

APP_ID = 2694490                                         # Path of Exile 2 on Steam
FEED = "steam_community_announcements"                   # the developer's own posts, never the press feeds
URL = (f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={APP_ID}&count=40&maxlength=1"
       f"&feeds={FEED}")
EVERY = 6 * 3600
FILE = "patchnotes.json"
# A patch post: "0.5.5d Patch Notes", "Hotfix 1.0.0b", "Content Update 1.0.0 Patch Notes"
IS_PATCH = re.compile(r"\b(patch notes?|hotfix(es)?)\b|\b\d+\.\d+\.\d+[a-z]?\b", re.I)
NOT = re.compile(r"\b(sale|mystery box|microtransactions?|supporter packs?|twitch drops|race|teaser|trailer)\b", re.I)
_busy = {"on": False}


def is_patch(title):
    t = str(title or "")
    return bool(IS_PATCH.search(t)) and not NOT.search(t)


def version_of(title):
    m = re.search(r"\b(\d+\.\d+\.\d+[a-z]?)\b", str(title or ""))
    return m.group(1) if m else ""


def pick(items):
    """[{title, version, date, url}] of the patch posts in Steam's answer, newest first."""
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not is_patch(it.get("title")):
            continue
        url = str(it.get("url") or "")
        if not url.startswith("https://"):
            continue
        out.append({"title": str(it["title"]).strip(), "version": version_of(it["title"]),
                    "date": int(it.get("date") or 0), "url": url})
    out.sort(key=lambda r: -r["date"])
    return out


def cached():
    return load_json(FILE, {}) or {}


def latest(n=3):
    return list(cached().get("notes") or [])[:n]


def refresh(done=None, force=False):
    """Fetch in the background when the last check is older than 6 hours. done(): called after a change."""
    have = cached()
    if _busy["on"] or (not force and time.time() - float(have.get("at") or 0) < EVERY):
        return False
    _busy["on"] = True

    def run():
        try:
            import requests
            r = requests.get(URL, headers={"User-Agent": APP_UA}, timeout=10)
            items = (r.json().get("appnews") or {}).get("newsitems") if r.status_code == 200 else None
            notes = pick(items) if items is not None else None
            if notes is None:                                # keep the last list, try again in 6 hours
                save_json(FILE, dict(have, at=time.time()))
                return
            changed = [n["url"] for n in notes] != [n["url"] for n in have.get("notes") or []]
            save_json(FILE, {"at": time.time(), "notes": notes[:20]})
            if changed and done:
                done()
        except Exception:
            buglog.caught()
        finally:
            _busy["on"] = False
    threading.Thread(target=run, daemon=True).start()
    return True
