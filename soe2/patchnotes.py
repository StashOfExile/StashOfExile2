"""3.3.0 owner: Patch Notes on the Dashboard. GGG posts every patch and hotfix on its forum, not on Steam. The
community board reads the Path of Exile 2 patch-notes forum once an hour and keeps the list; this app asks the
board, never the forum. Path of Exile 1 posts are left out by the board. The forum's address is an admin setting on
the board, so a forum move at 1.0 needs no app update. Asked once every 30 minutes; the last list is kept here."""
import threading
import time

from . import buglog
from .config import SETTINGS, load_json, save_json

EVERY = 30 * 60
FILE = "patchnotes.json"
_busy = {"on": False}


def source_of(n):
    """Where a post came from, by its address."""
    u = str(n.get("url") or "")
    if "steampowered.com" in u or "steamcommunity.com" in u:
        return "Steam"
    if "pathofexile.com" in u:
        return "GGG Forum"
    return ""


def day_of(n):
    """"Wed, September 2, 2026": the post's own date, else the day the board found it."""
    at = n.get("at") or n.get("date") or n.get("seen")
    if not at:
        return ""
    tm = time.localtime(float(at))
    return f"{time.strftime('%a', tm)}, {time.strftime('%B', tm)} {tm.tm_mday}, {tm.tm_year}"


def is_new(n):
    """A post that came in since the list was first shown here, until you open it."""
    return n.get("url") in set(SETTINGS.get("patch_new") or [])


def mark_seen(url):
    new = [u for u in SETTINGS.get("patch_new") or [] if u != url]
    SETTINGS["patch_new"] = new
    save_json("settings.json", SETTINGS)


def _note_new(notes):
    """The first list is the starting point; any post after that is NEW."""
    known = SETTINGS.get("patch_known")
    urls = [n["url"] for n in notes]
    if known is None:
        SETTINGS["patch_known"] = urls[:60]
    else:
        fresh = [u for u in urls if u not in known]
        if fresh:
            SETTINGS["patch_new"] = list(dict.fromkeys((SETTINGS.get("patch_new") or []) + fresh))[-20:]
            SETTINGS["patch_known"] = (known + fresh)[-120:]
    save_json("settings.json", SETTINGS)


def cached():
    return load_json(FILE, {}) or {}


def latest(n=3):
    return list(cached().get("notes") or [])[:n]


def admin_state():
    """(feed address, quiet) for admins: quiet means the board read nothing from the forum for a week."""
    c = cached()
    return c.get("feed"), bool(c.get("quiet"))


def refresh(done=None, force=False):
    """Ask the board in the background when the last ask is older than 30 minutes. done(): after a change."""
    have = cached()
    if _busy["on"] or (not force and time.time() - float(have.get("at") or 0) < EVERY):
        return False
    _busy["on"] = True

    def run():
        try:
            from . import board
            ok, data = board.call("GET", "/patchnotes")
            if not ok or not isinstance(data, dict):
                save_json(FILE, dict(have, at=time.time()))      # keep the last list, ask again later
                return
            notes = [n for n in data.get("notes") or [] if isinstance(n, dict) and str(n.get("url", "")).startswith("https://")]
            new = {"at": time.time(), "notes": notes[:20], "feed": data.get("feed"), "quiet": data.get("quiet")}
            changed = [n["url"] for n in notes] != [n.get("url") for n in have.get("notes") or []] or \
                new["quiet"] != have.get("quiet")
            save_json(FILE, new)
            _note_new(notes)
            if changed and done:
                done()
        except Exception:
            buglog.caught()
        finally:
            _busy["on"] = False
    threading.Thread(target=run, daemon=True).start()
    return True


def set_feed(url):
    """Admins: the forum page the board reads. -> (True, result) or (False, why)."""
    from . import board
    ok, data = board.call("POST", "/admin/patchfeed", body={"url": url.strip()})
    if ok:
        save_json(FILE, dict(cached(), at=0))                 # ask again at once
    return ok, data
