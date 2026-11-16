"""Usage count (UI overhaul): how many people use Stash of Exile 2 - on by default, one switch in Settings ›
Privacy & community.

What it sends: a random id made on this PC the first time - not your account, character, name or PC - to the
community board, every 10 minutes while the app runs. The board keeps only that id (hashed) and when it
was last seen, and answers with two counts: online now (seen in the last 15 minutes) and this week. Off: nothing is
sent, and the counts the app last got are kept. Network work runs on a background thread; the window reads the
cached numbers."""
import threading
import time
import uuid

from . import buglog
from .config import SETTINGS, load_json, save_json

FILE = "usage_count.json"          # {online, week, ts}
EVERY = 600                        # seconds between pings
_lock = threading.Lock()


def on():
    return bool(SETTINGS.get("usage_ping", True))


def set_on(value):
    SETTINGS["usage_ping"] = bool(value)
    save_json("settings.json", SETTINGS)


def install_id():
    pid = SETTINGS.get("usage_id")
    if not isinstance(pid, str) or len(pid) != 32:
        pid = uuid.uuid4().hex
        SETTINGS["usage_id"] = pid
        save_json("settings.json", SETTINGS)
    return pid


def counts():
    """(online now, this week) from the last answer, or None before one."""
    d = load_json(FILE, {})
    if not isinstance(d, dict) or not d.get("ts"):
        return None
    num = lambda x: int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < 1e8 else 0  # noqa
    return num(d.get("online")), num(d.get("week"))


def ping(call=None):
    """One ping (if on) and one count. Never raises. -> True when the board answered."""
    if not _lock.acquire(blocking=False):
        return False
    try:
        from . import board as B
        if not B.configured():
            return False
        if on():
            ok, r = (call or B.call)("POST", "/usage/ping", body={"id": install_id()})
        else:
            ok, r = (call or B.call)("GET", "/usage/count")
        if ok and isinstance(r, dict):
            save_json(FILE, {"online": r.get("online"), "week": r.get("week"), "ts": time.time()})
            return True
        return False
    except Exception:
        buglog.caught()
        return False
    finally:
        _lock.release()


def start(root):
    """Ping now and every 10 minutes (on a background thread; the window is only used for the timer)."""
    def tick():
        threading.Thread(target=ping, daemon=True).start()
        try:
            root.after(EVERY * 1000, tick)
        except Exception:
            pass
    try:
        root.after(5000, tick)
    except Exception:
        buglog.caught()
