"""3.3.0 owner: Patch Notes on the Dashboard. GGG posts every patch and hotfix on its forum, not on Steam. The
community board reads the Path of Exile 2 patch-notes forum once an hour and keeps the list; this app asks the
board, never the forum. Path of Exile 1 posts are left out by the board. The forum's address is an admin setting on
the board, so a forum move at 1.0 needs no app update. Asked once every 30 minutes; the last list is kept here."""
import threading
import time

from . import buglog
from .config import load_json, save_json

EVERY = 30 * 60
FILE = "patchnotes.json"
_busy = {"on": False}


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
