"""Trial of the Sekhemas helper (BETA) - the legend over the game beside the trial map, from sekhemas.json (shipped):
three groups - Rooms, Boons, Afflictions - each with what to take and what to avoid. Design: a legend of bad
afflictions and good picks that pops up on a Ctrl+Shift+R press on the trial room map screen, in the empty space left
and
right of the map window (Afflictions on the left; Rooms and Boons on the right).

GGG policy (Nov 2026: one screen read per manual key press): nothing here reads the screen. sekhemas_page.py asks
screenread.py for the press's one picture of the game, and this file only looks at that picture:
  * map_check()   is the trial map open? Its frame - the scroll's four roller knobs, the title bar's ends and its
                  info / close buttons, the arch button - is found by shape (a small search round each spot, so a
                  windowed game's border is fine), at any resolution: parts of the game's height from its middle.
  * hover_names() the affliction and boon names in a tooltip's text (Windows' text reader reads it, hover_page.py).
The game's log (Client.txt) says when you're in a trial and on which floor (areas "Sanctum_<floor>_..."): Trial keeps
that - nothing is saved. Keys aren't counted: the game shows them under the map. Rooms marked as afflicted (their
purple border) are not marked: the border alone can't be told apart from the rooms you can enter next, so the legend
only lists."""
import json
import os
import re
import sys

from .config import SETTINGS

NAME = "Trial of the Sekhemas"           # (names.py)
DEFAULTS = {"on": True}
TAKE, AVOID, MILD = "take", "avoid", "mild"
MARK = {TAKE: "✓", AVOID: "✕", MILD: "!"}   # never a state by color alone: a mark and a word
WORD = {TAKE: "Take", AVOID: "Avoid", MILD: "Mild"}
NOTE = {MILD: "if you must take one"}   # (after the word, muted)
ROOMS, BOONS, AFFLICTIONS = "rooms", "boons", "afflictions"
GROUP_WORD = {ROOMS: "Rooms", BOONS: "Boons", AFFLICTIONS: "Afflictions"}
# owner: Rooms red, Boons gold, Afflictions purple - an accent only (the header, its side bar, the marks); every line
# keeps its mark and its group's word
GROUP_COLOR = {ROOMS: "#e0675a", BOONS: "#e3b65a", AFFLICTIONS: "#b58cf0"}
LEFT, RIGHT = "left", "right"
SIDES = {LEFT: (AFFLICTIONS,), RIGHT: (ROOMS, BOONS)}   # (both sides used: ~10 lines each)
MAX_LINES = 8                            # a group's most lines (owner: about 6-8 lines per side)
FLOORS = 4


def cfg():
    c = SETTINGS.setdefault("sekhemas", {})
    for k, v in DEFAULTS.items():
        c.setdefault(k, v)
    return c


_DATA = {}


def data_path():
    base = getattr(sys, "_MEIPASS", None)
    return os.path.join(base, "soe2", "sekhemas.json") if base else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "sekhemas.json")


def data():
    """sekhemas.json (shipped with the app), read once."""
    if "d" not in _DATA:
        with open(data_path(), encoding="utf-8") as f:
            _DATA["d"] = json.load(f)
    return _DATA["d"]


# ================================================================ the legend
def legend(group, d=None, most=MAX_LINES):
    """ROOMS, BOONS or AFFLICTIONS -> [(verdict, [(mark, name, line)])]: its blocks (Take, Avoid, Mild) in the order
    sekhemas.json has them, best / worst first, at most `most` lines in each."""
    d = d or data()
    out = []
    for r in (d.get("legend") or {}).get(group) or []:
        v = r.get("verdict")
        if v not in MARK:
            continue
        block = next((b for b in out if b[0] == v), None)
        if block is None:
            block = (v, [])
            out.append(block)
        if len(block[1]) < most:
            block[1].append((MARK[v], r["name"], r["line"]))
    return out


def side_groups(side):
    """LEFT / RIGHT -> [(group, its blocks)] shown on that side of the map."""
    return [(g, legend(g)) for g in SIDES[side]]


# ================================================================ the game's log: where you are in the trial
AREA = re.compile(r"^Sanctum_(?:(\d+)_)?", re.I)


def floor_of(area_id):
    """A Client.txt area id -> None (not in the trial), the floor 1-4, or 0 (in the trial, floor unknown)."""
    m = AREA.match(str(area_id or ""))
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else 0
    return n if 1 <= n <= FLOORS else 0


class Trial:
    """What the log says about the trial you're in: the floor. Leaving it ends it."""

    def __init__(self):
        self.floor = None                  # None = not in a trial

    @property
    def inside(self):
        return self.floor is not None

    def area(self, area_id):
        """Every area change. -> True when you just left the trial."""
        f = floor_of(area_id)
        was = self.inside
        if f is None:
            self.floor = None
            return was
        if f or not was:
            self.floor = f if f else (self.floor or 0)
        return False

    def text(self):
        """"Floor 2 of 4" - or "" outside a trial."""
        if not self.inside:
            return ""
        return f"Floor {self.floor} of {FLOORS}" if self.floor else "In the trial"


# ================================================================ is the trial map open? (the press's picture)
SCALE_H = 480                            # the picture is looked at this tall
SEARCH = 0.035                           # each part is looked for this far round its spot (x the game's height)
MATCH = 0.6                              # a part is there at this likeness (-1 .. 1)
AGREE = 3                                # ... and where the others are, give or take this many pixels (at SCALE_H)
NEED = 6                                 # parts that must be there (of the ones not under our own windows)
LEAST = 4                                # ... never fewer


def _gray(img):
    import numpy as np
    from PIL import Image
    w, h = img.size
    k = SCALE_H / float(h)
    small = img.convert("L").resize((max(1, int(round(w * k))), SCALE_H), Image.BILINEAR)
    return np.asarray(small, dtype=np.float32)


def part_box(rel, w, h):
    """A part's spot (dx0, y0, dx1, y1 - parts of the height, x from the middle) -> (l, t, r, b) in a w x h picture."""
    cx = w / 2.0
    return (int(round(cx + rel[0] * h)), int(round(rel[1] * h)), int(round(cx + rel[2] * h)), int(round(rel[3] * h)))


def _best(area, tpl):
    """The best match of a template in an area -> (likeness, x, y)."""
    import numpy as np
    th, tw = tpl.shape
    if area.shape[0] < th or area.shape[1] < tw:
        return -1.0, 0, 0
    win = np.lib.stride_tricks.sliding_window_view(area, (th, tw))
    m = win.mean(axis=(2, 3), keepdims=True)
    z = win - m
    n = np.sqrt((z * z).sum(axis=(2, 3)))
    t = tpl - tpl.mean()
    tn = float(np.sqrt((t * t).sum())) or 1.0
    s = (z * t).sum(axis=(2, 3)) / (n * tn + 1e-6)
    i = int(np.argmax(s))
    y, x = divmod(i, s.shape[1])
    return float(s[y, x]), int(x), int(y)


def map_check(img, skip=(), d=None):
    """The press's picture of the game window (PIL, real pixels) -> {"open": bool, "parts": n there, "of": n looked
    at, "seen": {part: likeness}}. skip: (l, t, r, b) boxes in the picture under our own windows - parts there aren't
    asked for."""
    import numpy as np
    frame = (d or data()).get("frame") or {}
    parts = frame.get("parts") or {}
    out = {"open": False, "parts": 0, "of": 0, "seen": {}}
    if not parts or img is None:
        return out
    w, h = img.size
    gray = _gray(img)
    k = SCALE_H / float(h)
    gw = gray.shape[1]
    m = int(round(SEARCH * SCALE_H))
    found = []
    for name, p in parts.items():
        l_, t, r, b = part_box(p["box"], w, h)
        if any(l_ < sr and sl < r and t < sb and st < b for sl, st, sr, sb in skip):
            continue                          # (under our own legend: not asked for)
        out["of"] += 1
        tpl = np.asarray(p["tpl"], dtype=np.float32).reshape(p["size"][1], p["size"][0])
        L, T = int(round(l_ * k)), int(round(t * k))
        x0, y0 = max(0, L - m), max(0, T - m)
        x1, y1 = min(gw, L + tpl.shape[1] + m), min(SCALE_H, T + tpl.shape[0] + m)
        s, x, y = _best(gray[y0:y1, x0:x1], tpl)
        out["seen"][name] = round(s, 2)
        if s >= MATCH:
            found.append((x0 + x - L, y0 + y - T))
    if found:
        mx = sorted(f[0] for f in found)[len(found) // 2]
        my = sorted(f[1] for f in found)[len(found) // 2]
        out["parts"] = sum(1 for fx, fy in found if abs(fx - mx) <= AGREE and abs(fy - my) <= AGREE)
    need = max(LEAST, min(NEED, out["of"] - 1))
    out["open"] = out["of"] >= LEAST and out["parts"] >= need
    return out


def make_part(img, rel):
    """(tools/build_sekhemas_frame.py) A part of a picture of the open trial map -> its template, as kept in
    sekhemas.json."""
    w, h = img.size
    l_, t, r, b = part_box(rel, w, h)
    k = SCALE_H / float(h)
    from PIL import Image
    cut = img.convert("L").crop((l_, t, r, b))
    size = (max(4, int(round((r - l_) * k))), max(4, int(round((b - t) * k))))
    small = cut.resize(size, Image.BOX)
    return {"box": [round(v, 4) for v in rel], "size": list(size), "tpl": list(small.getdata())}


# ================================================================ a hovered tooltip: which affliction or boon
def _norm(text):
    return re.sub(r"[^a-z]", "", str(text or "").lower().replace("’", "'"))


def hover_names(lines, d=None):
    """OCR lines of a tooltip -> [(kind, entry)] for each affliction or boon named in them, in the order they're
    read (each once). kind: "affliction" / "boon"."""
    d = d or data()
    names = [("affliction", e) for e in d.get("afflictions") or []] + [("boon", e) for e in d.get("boons") or []]
    out, seen = [], set()
    for text, _box in lines or []:
        t = _norm(text)
        if len(t) < 5:
            continue
        for kind, e in names:
            n = _norm(e["name"])
            if n and e["name"] not in seen and (t == n or (n in t and len(n) >= 8)):
                seen.add(e["name"])
                out.append((kind, e))
    return out


def verdict(kind, e):
    """An affliction or a boon -> (mark, word, why, bad): "Bad" / "Mild" for afflictions, "Good" / "Weak" for boons."""
    r = e.get("rating")
    if kind == "affliction":
        if r in ("run-ending", "bad"):
            return "✕", "Bad", e.get("why", ""), r == "run-ending"
        return "!", "Mild", e.get("why", ""), False
    if r in ("great", "good"):
        return "✓", "Good", e.get("why", ""), False
    return "–", "Weak", e.get("why", ""), False


# ================================================================ where the legend goes
MAP_HALF = 0.52                          # the map window's half width (x the game's height), from the middle
GAP = 0.02                               # between the map window and the legend, and from the game's edge
WIDTH = 0.34                             # the legend's widest (x the game's height)
NARROW = 0.16                            # less room than this beside the map: the legend overlaps its edge
TOP = 0.2                                # never higher: under the quest tracker (top right) and the skills (left)
MIDDLE = 0.45                            # both panels sit round the map's middle, their tops level


def columns(game):
    """The game (x, y, w, h) -> {LEFT: (x, width), RIGHT: (x, width)}: the empty space left and right of the map."""
    gx, gy, gw, gh = game
    cx = gx + gw / 2.0
    gap = GAP * gh
    room = cx - MAP_HALF * gh - gx - 2 * gap
    if room >= NARROW * gh:
        wd = min(WIDTH * gh, room)
        return {LEFT: (int(cx - MAP_HALF * gh - gap - wd), int(wd)), RIGHT: (int(cx + MAP_HALF * gh + gap), int(wd))}
    wd = max(NARROW * gh, min(WIDTH * gh, gw / 4.0))
    return {LEFT: (int(gx + gap), int(wd)), RIGHT: (int(gx + gw - gap - wd), int(wd))}


def top_of(game, h):
    """Both panels' top, the taller one's height h: round the map's middle, never above TOP of the game."""
    gx, gy, gw, gh = game
    return int(gy + max(TOP * gh, MIDDLE * gh - h / 2.0))


def place_y(game, x, w, h, avoid=(), top=None):
    """A panel's top: `top` (or top_of), moved off any of our windows in `avoid` ((l, t, r, b)) - below it, or
    above when there's no room below."""
    gx, gy, gw, gh = game
    y = int(top) if top is not None else top_of(game, h)
    gap = int(GAP * gh / 2)
    for _ in range(4):
        hit = [r for r in avoid if r[0] < x + w and x < r[2] and r[1] < y + h and y < r[3]]
        if not hit:
            return y
        below = max(r[3] for r in hit) + gap
        if below + h <= gy + gh - gap:
            y = below
            continue
        y = max(int(gy + gap), min(r[1] for r in hit) - gap - h)
    return y
