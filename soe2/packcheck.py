"""The data packs (Craft Helper, Campaign guide) look for a newer copy on GitHub by themselves: a little after the app
starts, then at most once every 24 hours (the time is kept in settings: "packs_checked"). One small public download per
pack, nothing about you is sent (the same GitHub rules as before: the app's User-Agent, no account, no extra requests).
There is no button for it. Pure helpers here; the window side is App.packs_autocheck (app.py)."""
import time

from .config import SETTINGS

EVERY = 24 * 3600                 # at most one check a day
FIRST_DELAY_MS = 25_000           # after start, so the first screen is never waiting on the network
LOOK_MS = 30 * 60_000             # a long-running app looks at the clock this often; it only fetches when a day is up


CRAFT_TIP = ("The Craft Helper's data: types, steps and how the market picks a letter, for the game patch shown. "
             "One small public download from GitHub, nothing about you is sent.")
CAMP_TIP = ("The Campaign guide's data: acts, zones and rewards. One small public download from GitHub, nothing about "
            "you is sent.")


def due(now=None):
    """True when it's a day since the last check (or there never was one)."""
    now = now or time.time()
    last = float(SETTINGS.get("packs_checked", 0) or 0)
    return last <= 0 or now - last >= EVERY or last > now + 3600     # (a clock that went back: look again)


def mark(now=None):
    SETTINGS["packs_checked"] = now or time.time()


def ago(now=None):
    """'checked 3 h ago' / 'not checked yet'."""
    last = float(SETTINGS.get("packs_checked", 0) or 0)
    if last <= 0:
        return "not checked yet"
    s = max(0, int((now or time.time()) - last))
    return "checked " + ("just now" if s < 60 else f"{s // 60} min ago" if s < 3600 else f"{s // 3600} h ago"
                         if s < 86400 else f"{s // 86400} d ago")


def state(now=None):
    """'up to date' once a check has answered in the last two days, else ''."""
    last = float(SETTINGS.get("packs_checked", 0) or 0)
    return "up to date" if last > 0 and (now or time.time()) - last < 2 * EVERY else ""


def tip(base):
    """A pack line's tooltip: what it is, when it last looked, and that it looks on its own."""
    return f"{base} It looks for a newer copy on its own, once a day ({ago()})."


def run(ch_fetch, camp_fetch):
    """The check itself (on a background thread). -> {"craft": (what, info), "campaign": (what, info)}.
    One request per pack; an error in one doesn't stop the other. The day is only counted when GitHub answered."""
    out = {}
    for key, fn in (("craft", ch_fetch), ("campaign", camp_fetch)):
        try:
            out[key] = fn()
        except Exception:
            out[key] = ("error", "")
    if any(v[0] in ("new", "same") for v in out.values()):
        mark()
    return out
