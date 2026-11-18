"""2.142.0 Vaal Lens (BETA): medallions - what each one does, how good it is, the ones in your hand (the Medallions
panel, V) and whether one on the ground is worth a slot.

Names and effects are the game's (9 medallions). How good each is: lock and upgrade first, Zantipi's last (told by
the player); a capacity medallion is worth nothing once that capacity is full. Uromoti's adds a room - worth more
when that room pays at tier 3 (Corruption Chamber, Sacrificial Chamber, Thaumaturge, Alchemy Lab, Smithy).

The hand is learned, not guessed: hover a medallion in the panel and its tooltip's name is read with the slot under
the mouse; that slot's picture is kept (medallion_icons.json in your data folder: pictures of icons, nothing else),
so the next time the panel opens each slot is known by its picture. Two are known from the start (the lock and the
upgrade arrow)."""
import json
import os
import re

import numpy as np

# name -> (short name, what it does, worth 0-10)
MEDALLIONS = {
    "Juatalotli's Medallion": ("Lock", "Keeps a room through the next destabilization", 10),
    "Quipolatl's Medallion": ("Upgrade", "Raises a room's tier", 9),
    "Estazunti's Medallion": ("Extra restricted room", "One more restricted room card after the Architect", 8),
    "Uromoti's Medallion": ("Add room", "Adds a room card", 5),
    # 3.0.6 (owner: "it should be telling me next to delete hayoxi's medallion to pick up the reroll medallion
    # (puhuarte's)"): rerolling the cards on offer is worth more than rerolling a restricted room
    "Hayoxi's Medallion": ("Reroll restricted", "Rerolls a restricted room", 4),
    "Puhuarte's Medallion": ("Reroll cards", "Rerolls the room cards on offer", 5),
    "Xopec's Medallion": ("Crystal capacity", "Crystal capacity +6 (up to 60)", 6),
    "Azcapa's Medallion": ("Medallion slot", "Medallion capacity +1 (up to 6)", 7),
    "Zantipi's Medallion": ("Waystone modifier", "Adds a random waystone modifier to the temple", 1),
}
HIGH_ROOMS = ("Corruption Chamber", "Sacrificial Chamber", "Thaumaturge", "Alchemy Lab", "Smithy")
LOW_ROOMS = ("Armoury", "Garrison", "Spymaster")       # rooms that mostly raise others - the first to let go
_KEYS = {re.sub(r"[^A-Z]", "", n.upper()): n for n in MEDALLIONS}
_ROOM = re.compile(r"ADD\s*ROOM\s*[:;]?\s*(.+)", re.I)
_COUNT = re.compile(r"MEDALLIONS?\s*\(?\s*(\d)\s*[/|l]\s*(\d)\s*\)?", re.I)


def letters(t):
    return re.sub(r"[^A-Z]", "", str(t).upper())


def name_of(text):
    """An OCR line -> the medallion's name in it, or None (letters only, so "Zantipi's Medallion" and
    "ZANTIPIS MEDALLION" both match; a near miss of one letter too)."""
    L = letters(text)
    if "MEDALLION" not in L:
        return None
    for k, n in _KEYS.items():
        if k in L:
            return n
    import difflib
    m = difflib.get_close_matches(L[:len(L)], list(_KEYS), 1, 0.88)
    return _KEYS[m[0]] if m else None


def parse(lines):
    """OCR lines -> {"names": [(name, box)], "count": (have, most) or None, "head": box of "Medallions (n/m)",
    "room": the room an Uromoti's adds (its tooltip) or None}."""
    out = {"names": [], "count": None, "head": None, "room": None}
    for text, box in lines or []:
        t = " ".join(str(text).split())
        m = _COUNT.search(t)
        if m and "MEDALLIONS" in letters(t) and len(letters(t)) <= 12:
            have, most = int(m.group(1)), int(m.group(2))
            if 0 <= have <= most <= 6:
                out["count"], out["head"] = (have, most), box
            continue
        n = name_of(t)
        if n:
            out["names"].append((n, box))
            continue
        r = _ROOM.search(t)
        if r:
            out["room"] = room_family(r.group(1))
    return out


def room_family(text):
    from . import vaallens_plan as VP
    what = VP.card(text)
    if what and what[0] == "room":
        return what[1]
    low = " ".join(str(text).lower().split())
    for fam in VP.ROOMS:
        if fam.lower() in low:
            return fam
    return None


def base(name):
    """ "Uromoti's Medallion: Corruption Chamber" -> ("Uromoti's Medallion", "Corruption Chamber")."""
    n, _, room = str(name or "").partition(": ")
    return n, (room or None)


def short(name):
    """A medallion -> the word players use: its room (Armoury) or what it does (Lock, Upgrade)."""
    n, r = base(name)
    return r or MEDALLIONS.get(n, (n,))[0]


def worth(name, room=None, crystals_most=None, slots_most=None):
    """-> (0-10, why). Capacity ones are 0 once full; Uromoti's follows its room."""
    name, r = base(name)
    room = room or r
    short, _what, w = MEDALLIONS[name]
    if name == "Xopec's Medallion" and crystals_most is not None and crystals_most >= 60:
        return 0, "crystals already at 60"
    if name == "Azcapa's Medallion" and slots_most is not None and slots_most >= 6:
        return 0, "already 6 slots"
    if name == "Uromoti's Medallion" and room:
        if room in HIGH_ROOMS:
            return 8, f"adds {room} (pays at tier 3)"
        if room in LOW_ROOMS:                         # (3.0.6, owner's pick: the Armoury went to make room for a Lock)
            return 4, f"adds {room}"
        return 5, f"adds {room}"
    return w, short.lower()


def advice(new, hand, have, most, room=None, crystals_most=None):
    """A medallion seen on the ground -> (verdict, line) or None.
    verdict: "take" (room for it, or better than your weakest), "skip" (weaker than all you hold), "learn" (full, and
    not every slot is known yet). hand: names (None = not learned) of the slots you hold."""
    w, why = worth(new, room, crystals_most, most)
    if w == 0:
        return "skip", f"{new}: {why}."
    if have is None or most is None:
        return None
    if have < most:
        return "take", f"{new}: {why}. {most - have} slot{'s' if most - have != 1 else ''} free."
    known = [h for h in (hand or [])[:have] if h]
    if not known:
        return "learn", f"{new}: {why}. Medallions full: open them (V) and press the Read Key to see which to drop."
    # 3.0.6 (owner: "nobody is going to manually read their medallions"): a slot not known yet doesn't stop the
    # advice - the weakest one known is the one to let go
    worst = min(known, key=lambda h: worth(h, None, crystals_most, most)[0])
    ww, wwhy = worth(worst, None, crystals_most, most)
    if w > ww:
        return "take", f"{new}: {why}. Use or destroy your {short(worst)} medallion to make room."
    return "skip", f"{new}: {why}. Weaker than all you hold."


# ---------------------------------------------------------------- the panel (V): where the slots are
# measured on a 2560x1440 game: the "Medallions (6/6)" title's right end, then 2 columns x 3 rows of 120x125 slots
SLOT = (120, 125)
STEP = (144, 144)
ICON = (32, 22, 88, 82)          # the picture inside the slot's gold diamond (frame and pedestal left out)


HEAD_LEFT_TO_COLS = (-63, 81)    # 3.0.6 (owner's 4/6, 5/6, 6/6 panels at 2560x1440): each column's left from the
HEAD_MID_TO_ROW = 44             # title text's LEFT edge (its right edge moves: OCR may take the > arrow in), and the
#                                  first row's top from the title's middle


def slots(head_screen, scale, n=6):
    """The title's box on screen (l, t, r, b) and the game's scale (height / 1440) -> the n filled slots' boxes.
    3.0.6: the game fills the right column top to bottom first, then the left one (4/6: right 1-3 + left 1)."""
    l, mid = head_screen[0], (head_screen[1] + head_screen[3]) / 2
    y0 = mid + HEAD_MID_TO_ROW * scale
    cells = [(1, 0), (1, 1), (1, 2), (0, 0), (0, 1), (0, 2)]
    out = []
    for c, row in sorted(cells[:n], key=lambda cr: (cr[1], cr[0])):        # (read in rows, left to right)
        x, y = l + HEAD_LEFT_TO_COLS[c] * scale, y0 + row * STEP[1] * scale
        out.append((int(x), int(y), int(x + SLOT[0] * scale), int(y + SLOT[1] * scale)))
    return out


def slot_filled(pic):
    """A slot's icon crop -> True when a medallion is in it (3.0.6: an empty slot is near black: mean ~6, spread ~4;
    a filled one 65+ / 44+ on the owner's 3/6, 4/6 and 6/6 panels)."""
    from PIL import ImageStat
    st = ImageStat.Stat(pic.convert("L"))
    return st.mean[0] > 25 or st.stddev[0] > 15


def icon_box(slot):
    l, t, r, b = slot
    sx, sy = (r - l) / SLOT[0], (b - t) / SLOT[1]
    return int(l + ICON[0] * sx), int(t + ICON[1] * sy), int(l + ICON[2] * sx), int(t + ICON[3] * sy)


INNER = (0.25, 0.22)             # 3.0.6: the part of the icon box matched - the room's picture, not the gold diamond


def feat(img, inner=True):
    """A slot's icon (PIL) -> a unit vector: a 20x20 z-scored gray picture plus a coarse color share.
    3.0.6 (owner: a Garrison medallion was named as another room): only the middle of the icon is compared - every
    room medallion has the same gold diamond, which made two of them look 86% alike; the middle alone, 67% at most."""
    from PIL import Image
    if inner:
        w, h = img.size
        img = img.crop((int(w * INNER[0]), int(h * INNER[1]), w - int(w * INNER[0]), h - int(h * INNER[1])))
    a = np.asarray(img.convert("RGB").resize((20, 20), Image.BILINEAR)).astype(np.float32)
    g = a.mean(axis=2)
    gx, gy = np.abs(np.diff(g, axis=1))[:-1, :], np.abs(np.diff(g, axis=0))[:, :-1]
    g = np.concatenate([g.ravel(), (gx + gy).ravel()])
    g = (g - g.mean()) / (g.std() + 1e-6)
    tot = a.sum(axis=2) + 1e-6
    col = np.array([(a[..., 0] / tot).mean(), (a[..., 1] / tot).mean(), (a[..., 2] / tot).mean()]) * 40
    v = np.concatenate([g, col])
    return v / (np.linalg.norm(v) + 1e-9)


SEEDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "medallion_icons.json")
MATCH = 0.86
MARGIN = 0.04


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return {k: [np.array(v, dtype=np.float32) for v in vs] for k, vs in json.load(f).items()
                    if base(k)[0] in MEDALLIONS}
    except (OSError, ValueError):
        return {}


def known_icons(user_path=None):
    out = _load(SEEDS)
    for k, vs in (_load(user_path) if user_path else {}).items():
        out.setdefault(k, []).extend(vs)
    return out


def learn(user_path, name, vec, keep=4):
    """A hovered slot's icon -> kept for that name (the newest few). An Uromoti's is kept with its room."""
    if base(name)[0] not in MEDALLIONS:
        return
    try:
        with open(user_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    vs = data.get(name) or []
    vs = (vs + [[round(float(x), 4) for x in vec]])[-keep:]
    data[name] = vs
    os.makedirs(os.path.dirname(user_path) or ".", exist_ok=True)
    with open(user_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


SHIFT = 10                       # 3.0.6: how far (px at 1440p) a slot's picture is looked for round where it should be
SHIFT_STEP = 2


def identify_at(crop, box, icons, scale=1.0):
    """3.0.6 (owner: "it's still telling me medallions not known, how the hell is that possible, we have so much
    data"): a slot's picture matched only where the slot was worked out to be - 4 px off (the title read a little
    wider) and nothing matched. Now looked for round that spot: crop(box) -> PIL picture; the best name over every
    small shift, or None."""
    best = (None, -1.0)
    r = max(1, int(round(SHIFT * scale)))
    st = max(1, int(round(SHIFT_STEP * scale)))
    for dy in range(-r, r + 1, st):
        for dx in range(-r, r + 1, st):
            b = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
            name, score = identify(feat(crop(b)), icons, scored=True)
            if name is not None and score > best[1]:
                best = (name, score)
    return best[0]


ALIGN_REACH, ALIGN_STEP = 40, 6   # 3.0.6: px at 1440p


def align(crop, head, icons, scale=1.0, n=6):
    """3.0.6 (owner: "failure to identify medallions still, unacceptable"): the title's box as OCR gave it can be a
    good way off (a 6/6 panel read 1 of 6), and the slots are placed from it. -> (dx, dy): the shift of the slot grid
    whose pictures match the known medallions best (summed over the slots), or (0, 0)."""
    if not icons:
        return 0, 0
    vecs = [v for vs in icons.values() for v in vs]
    if not vecs:
        return 0, 0
    mat = np.stack(vecs)
    r, st = int(round(ALIGN_REACH * scale)), max(1, int(round(ALIGN_STEP * scale)))
    best, at = None, (0, 0)
    for dy in range(-r, r + 1, st):
        for dx in range(-r, r + 1, st):
            h = (head[0] + dx, head[1] + dy, head[2] + dx, head[3] + dy)
            tot = 0.0
            for sl in slots(h, scale, n):
                try:
                    tot += float((mat @ feat(crop(icon_box(sl)))).max())
                except Exception:
                    continue
            if best is None or tot > best + 1e-6 or (abs(tot - best) <= 1e-6 and abs(dx) + abs(dy) < sum(map(abs, at))):
                best, at = tot, (dx, dy)
    return at


def identify(vec, icons, scored=False):
    """-> the name whose icon matches best (MATCH or closer, and clearly ahead of any other name), or None.
    3.0.6 (owner's panel: a slot learned while hovered - it glows - matched its plain self at 0.90, under the old
    0.93, so it fell back to "not known"): MATCH 0.86 with a lead of MARGIN over the next name."""
    best = {}
    for name, vs in icons.items():
        for v in vs:
            s = float(np.dot(vec, v))
            if s > best.get(name, -1.0):
                best[name] = s
    order = sorted(best.items(), key=lambda x: -x[1])
    if not order or order[0][1] < MATCH:
        return (None, 0.0) if scored else None
    if len(order) > 1 and order[0][1] - order[1][1] < MARGIN and base(order[0][0])[0] != base(order[1][0])[0]:
        return (None, 0.0) if scored else None
    return (order[0][0], order[0][1]) if scored else order[0][0]


# 2.142.1 (feedback: "the room card medallions have matching icons to the regular cards and room tiles"): a slot not
# known by its own picture is matched against the board's room icons - an Uromoti's shows the room it adds
ROOM_MIN = 0.90


def room_from_icon(full, slot, scale=1.0, origin=(0, 0)):
    """The game's picture (PIL), a slot box on screen -> the room family its icon shows, or None. Searches a few
    sizes and spots round the slot's middle (the room icon sits a little above it)."""
    from PIL import Image
    from . import vaallens as V
    icons = V.load_icons()
    a = np.asarray(full.convert("RGB")).astype(np.float32)
    ox, oy = origin
    sw = (slot[2] - slot[0]) / SLOT[0]
    best = (0.0, None)
    for sc in (1.0, 1.05, 1.1, 1.15):
        r = V.IR / sc * sw
        for dy in range(44, 64, 4):
            cx, cy = (slot[0] + slot[2]) / 2 - ox, slot[1] + dy * sw - oy
            crop = a[int(cy - r):int(cy + r), int(cx - r):int(cx + r)]
            if crop.shape[0] < 10 or crop.shape[1] < 10:
                continue
            q = np.asarray(Image.fromarray(crop.astype(np.uint8)).resize((2 * V.IR, 2 * V.IR), Image.BILINEAR))
            m, sim, sure = V.match_icon(V.icon_feat(q.astype(np.float32)), icons)
            if m and sure and m.get("kind") == "room" and m.get("name") and sim > best[0]:
                best = (sim, m["name"])
    return best[1] if best[0] >= ROOM_MIN else None
