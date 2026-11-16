"""2.132.1 Temple Helper (feedback: "show how many crystals I am currently at"): your crystals, as the Temple
Console prints them ("18/60" under its Run Temple button) in Vaal Ruins. GGG policy (Nov 2026: one screen read per
manual key press): it reads that one line when you press your Read Key with the console open (temple_page.
temple_console_job) and keeps the two numbers; Vaal Lens shows them. (The Vaal Beacon tooltip read in maps, the
crystals on the overlay's line and the "crystals full" alert are gone - owner decision: the Temple Console only.)

Nothing else on screen is kept - only the two numbers. ToS: it only looks at the screen and shows something."""
import re
import time

from .config import SETTINGS, load_json, save_json

STATE_FILE = "temple.json"
DEFAULTS = {"on": True, "notepad": True, "notes": "", "pad_x": None, "pad_y": None}


# 2.136.0: Atziri's Temple, as Client.txt names the area. 2.137.0 (feedback: "should open in Vaal Ruins as well as
# inside Atziri's Temple"): the endgame Vaal Ruins (IncursionHubEndgame, not the campaign's IncursionHub) and Atziri's
# own area too.
TEMPLE_AREAS = ("IncursionHubEndgame", "IncursionTemple", "IncursionTemplePresent")
RUN_AREA = "IncursionTemple"            # entering it = a temple run started, so its crystals are spent


def cfg():
    c = SETTINGS.setdefault("temple", {})
    for k, v in DEFAULTS.items():
        c.setdefault(k, v)
    return c


# 2.136.1 (feedback: "when I'm in the Vaal ruins, it should be able to see through the overlay (the same way ritual
# does) and read the crystal count at the bottom of the screen"): the Temple Console prints "18/60" under its Run
# Temple button. Read there (parts of the game; measured on 1080p and 1440p shots) on a Read Key press in a temple area.
CONSOLE_BOX = (0.465, 0.942, 0.555, 0.978)
CONSOLE_LINE = re.compile(r"(?<!\d)(\d{1,3})\s*[/|l]\s*(\d{2,3})(?!\d)")


def console_box(game):
    gx, gy, gw, gh = game
    a = CONSOLE_BOX
    return gx + int(gw * a[0]), gy + int(gh * a[1]), gx + int(gw * a[2]), gy + int(gh * a[3])


def parse_console(lines, most=None):
    """OCR lines of the console's count -> (have, most) from "18/60", or None. The most must make sense (10-200,
    and the same as the last read when there is one) and have <= most."""
    for text, _box in lines or []:
        m = CONSOLE_LINE.search(" ".join(str(text).split()).replace(" / ", "/"))
        if not m:
            continue
        have, top = int(m.group(1)), int(m.group(2))
        if 10 <= top <= 200 and 0 <= have <= top and (most is None or top == most):
            return have, top
    return None


def state():
    d = load_json(STATE_FILE, {}) or {}
    try:
        return {"have": int(d["have"]), "most": int(d["most"]), "t": float(d.get("t", 0)), "old": bool(d.get("old"))}
    except (KeyError, TypeError, ValueError):
        return None


def state_set(have, most, t=None):
    d = {"have": int(have), "most": int(most), "t": t if t is not None else time.time(), "old": False}
    save_json(STATE_FILE, d)
    return d


def mark_old():
    """2.137.0 (feedback: "I have 54/60 it says 58/60"): a temple run spends crystals, and the number is only read
    from the Temple Console. So once a run starts the kept number is marked as from before it, until the next read."""
    st = state()
    if st and not st["old"]:
        d = dict(st, old=True)
        save_json(STATE_FILE, d)
        return d
    return st


RUN = 6                 # 2.135.0: crystals one temple run uses (the console takes 6, you get 6 room cards)


def runs(st):
    return (st["have"] // RUN) if st else 0


def count_text(st):
    """Vaal Lens' head line: "Crystals 55/60 (9 runs)" (2.135.0: how many runs that is - 6 crystals each), or
    "Crystals ?" before the first read."""
    if not st:
        return "Crystals ?"
    if st.get("old"):
        return f"Crystals {st['have']}/{st['most']}? (before your last run)"
    n = runs(st)
    return f"Crystals {st['have']}/{st['most']} ({n} run{'' if n == 1 else 's'})"
