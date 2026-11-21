"""2.131.0 Top Up Reminders (plan: "tells you what's running low in your inventory - reads only while your inventory is
open"): you pick an item from the Item list and set how many to keep; the app knows its picture already (poe.ninja's
picture of it, downloaded once into the art cache - 3.1: no game pictures ship with the app). When you read your
inventory in your hideout or a town and you have fewer, one alert card says so ("Exalted Orb 7 / 20").

How it reads (pixels of your screen, like any capture tool):
- the inventory is open when its "Inventory" title is at the top right. The first time, OCR reads the word there and
  that piece of YOUR screen is kept (gameart.screen_look, only on this PC); later reads match it (other screens
  score under 0.4; owner's 126 screenshots: 18 of 18 inventories found, no other screen),
- the 12 x 5 grid sits at a fixed place for the game's height (GRID, measured on 1440p),
- each cell is compared by its picture (a small color thumbnail, the stack count's corner left out, the cell's own
  backing subtracted so a hover's glow doesn't matter) - the same item scores under SAME, others over 25,
- a stack's count is read from its top-left digits: shapes learned on this PC - each time OCR reads a count no learned
  shape knows, its digits' shapes are kept (topup.json), so OCR is needed less and less.
Nothing is sent anywhere. GGG ToS: one screenshot per Read Key press - nothing is sent to the game."""
import base64
import re
import sys

from . import buglog
from .config import SETTINGS, load_json, save_json

ROWS, COLS = 5, 12
GRID = (0.04875, 0.016, 0.5465)         # cell size, right margin, top - in game heights (1440p: 70.2, 23, 787 px)
BANNER = (0.45, 0.0, 0.12)              # where the title is looked for: width from the right, top, bottom (heights)
BANNER_MIN = 0.60
SIG = 20                                # cells are compared as SIG x SIG color thumbnails
COUNT_BOX = (0.55, 0.36)                # the stack count's corner (width, height) - left out of the picture
SAME = 14.0                             # mean color difference that is still the same item
DIGIT_MIN = 0.62
DIGIT_BAND = (0.0, 0.0, 0.62, 0.36)   # x0, y0, x1, y1 of a cell where its count's digits are
LEARN_FILE = "topup.json"
PICS = 4                                # pictures kept per item
DEFAULTS = {"on": True, "items": [], "below": 0.3}   # items: [{"name", "keep"}] - their pictures are in topup.json
# 2.131.2 (feedback: it asked on every map - ask only when below a 70% threshold, handled like the % variances
# on price checks): a reminder only once you hold less than Keep minus this share
BELOW_STEPS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
def below_text(b):
    p = int(round(float(b) * 100))
    return "any amount" if p == 0 else f"{p}%"


def remind_at(keep, below=None):
    """Keep 40, 30% -> remind under 28 (always at least 1 below Keep's rounding: never at 0 needed)."""
    b = cfg().get("below", DEFAULTS["below"]) if below is None else below
    return max(0.0, float(keep) * (1 - float(b)))


def cfg():
    c = SETTINGS.setdefault("topup", {})
    for k, v in DEFAULTS.items():
        c.setdefault(k, list(v) if isinstance(v, list) else v)
    return c


def _cv():
    import cv2
    import numpy as np
    return cv2, np


# ---------------------------------------------------------------- where things are
def grid_rect(game):
    """Game (x, y, w, h) on screen -> the inventory grid's (left, top, right, bottom) on screen."""
    x, y, w, h = game
    cell, right, top = (v * h for v in GRID)
    gx1 = x + w - right
    return (int(round(gx1 - COLS * cell)), int(round(y + top)), int(round(gx1)), int(round(y + top + ROWS * cell)))


def banner_rect(game):
    x, y, w, h = game
    return (int(x + w - BANNER[0] * h), int(y + BANNER[1] * h), int(x + w), int(y + BANNER[2] * h))


BANNER_KEY = "inventory_title"          # gameart.screen_look: the inventory's title as this PC's screen showed it
BANNER_WORDS = ("inventory",)


def is_open(img, game_h):
    """The banner area (PIL) -> the inventory's title is there."""
    return open_score(img, game_h) >= BANNER_MIN


def open_score(img, game_h):
    """How well the inventory's title learned on this PC matches (0 .. 1). Not learned yet: OCR looks for the word
    and, found, keeps that piece of the picture (1.0) - 3.1, no picture of the game ships with the app."""
    try:
        cv2, np = _cv()
        from . import gameart as GA
        a = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        if GA.screen_look(BANNER_KEY) is not None:
            return GA.match_look(a, BANNER_KEY, game_h)[0]
        box = GA.find_word(img, BANNER_WORDS)
        if box is None:
            return 0.0
        p = max(2, int(round(4 * game_h / 1440.0)))
        crop = a[max(0, box[1] - p):box[3] + p, max(0, box[0] - p):box[2] + p]
        GA.keep_screen_look(BANNER_KEY, crop, game_h)
        return 1.0
    except Exception:
        buglog.caught()
        return 0.0


def split(grid_img):
    """The grid (PIL) -> {(row, col): cell (PIL)}."""
    cw, ch = grid_img.width / COLS, grid_img.height / ROWS
    return {(r, c): grid_img.crop((int(round(c * cw)), int(round(r * ch)), int(round((c + 1) * cw)),
                                   int(round((r + 1) * ch))))
            for r in range(ROWS) for c in range(COLS)}


def empty(cell):
    _cv2, np = _cv()
    a = np.asarray(cell.convert("RGB").resize((24, 24))).astype(float)[3:21, 3:21]
    return a.mean() < 18 and a.std() < 8


# ---------------------------------------------------------------- what a cell holds
def _mask():
    _cv2, np = _cv()
    m = np.ones((SIG, SIG), bool)
    m[:int(SIG * COUNT_BOX[1]), :int(SIG * COUNT_BOX[0])] = False
    m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = False
    return m


def sig(cell):
    """A cell (PIL) -> its picture: SIG x SIG x 3 floats, the cell's backing (its edge ring's median) subtracted."""
    _cv2, np = _cv()
    from PIL import Image
    a = np.asarray(cell.convert("RGB").resize((SIG, SIG), Image.BILINEAR)).astype(float)
    ring = np.concatenate([a[1, 1:-1], a[-2, 1:-1], a[1:-1, 1], a[1:-1, -2]])
    return a - np.median(ring, axis=0)


def dist(a, b):
    _cv2, np = _cv()
    m = _mask()
    return float(np.abs(a - b)[m].mean())


def sig_b64(s):
    _cv2, np = _cv()
    return base64.b64encode(np.clip(s + 128, 0, 255).astype(np.uint8).tobytes()).decode()


def sig_from(b):
    _cv2, np = _cv()
    return np.frombuffer(base64.b64decode(b), np.uint8).reshape(SIG, SIG, 3).astype(float) - 128


# ---------------------------------------------------------------- the stack count
def _white(cell):
    _cv2, np = _cv()
    a = np.asarray(cell.convert("RGB")).astype(int)
    return (((a.min(2) > 165) & ((a.max(2) - a.min(2)) < 50)) * 255).astype(np.uint8)


DIGITS_KEPT = 3                         # learned shapes kept per digit


def digit_templates():
    """{digit: [binary picture at 1440p]} learned on this PC (3.1: none ship - OCR teaches them, keep_digits)."""
    _cv2, np = _cv()
    out = {}
    for d, pics in ((load_json(LEARN_FILE, {}) or {}).get("digits") or {}).items():
        for p in pics:
            try:
                h, w, b = p
                out.setdefault(d, []).append(np.frombuffer(base64.b64decode(b), np.uint8).reshape(h, w))
            except Exception:
                continue
    return out


def keep_digits(cell, count):
    """A cell whose count OCR read -> its digits' shapes kept (topup.json "digits", at 1440p, DIGITS_KEPT each), so the
    next read knows them without OCR. Only when the count's digits stand apart (one shape a digit). -> how many."""
    cv2, np = _cv()
    text = str(int(count)) if count is not None and int(count) > 0 else ""
    if not text or len(text) > 4:
        return 0
    n = cell.width
    run, m = digit_run(cell)
    if len(run) != len(text):
        return 0
    band = (m * 255).astype(np.uint8)
    k = 70.2 / n
    d = load_json(LEARN_FILE, {}) or {}
    digs = d.setdefault("digits", {})
    added = 0
    for ch, (x, y, w, h) in zip(text, run):
        pic = np.zeros((h + 2, w + 2), np.uint8)
        pic[1:-1, 1:-1] = band[y:y + h, x:x + w]
        if abs(k - 1) > 0.02:
            pic = ((cv2.resize(pic, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) > 127) * 255).astype(np.uint8)
        b = base64.b64encode(np.ascontiguousarray(pic).tobytes()).decode()
        lst = [x_ for x_ in digs.get(ch, []) if x_[2] != b]
        digs[ch] = (lst + [[int(pic.shape[0]), int(pic.shape[1]), b]])[-DIGITS_KEPT:]
        added += 1
    if added:
        save_json(LEARN_FILE, d)
    return added


def _band(cell):
    n = cell.width
    x0, y0, x1, y1 = (int(v * n) for v in DIGIT_BAND)
    return _white(cell)[y0:y1, x0:x1], x0, y0


def _blobs(band, n, maxx=0.22, maxw=0.2):
    """Digit-sized white shapes near the count's place (a count the templates don't know). maxx: how far right (cell
    widths) one may start - the first digit starts near the left; a digit after it (rest) may start anywhere."""
    cv2, np = _cv()
    k, _lab, st, _c = cv2.connectedComponentsWithStats((band > 0).astype(np.uint8), 8)
    return [tuple(int(v) for v in st[i][:4]) for i in range(1, k)
            if 0.15 * n <= st[i][3] <= 0.27 * n and st[i][0] <= maxx * n and 0.04 * n <= st[i][1] <= 0.16 * n
            and 0.04 * n <= st[i][2] <= maxw * n]


def read_count(cell, tpls=None):
    """A cell -> (count, sure). No count shown: (1, True). A count it can't read: (None, False)."""
    return _read(cell, tpls)[:2]


def _read(cell, tpls=None):
    """-> (count, sure, shown): shown = a stack number is drawn (3.0.6: gear, jewels and waystones show none - so
    they're never taken for currency)."""
    cv2, np = _cv()
    band, _x0, _y0 = _band(cell)
    n = cell.width
    tpls = digit_templates() if tpls is None else tpls
    k = n / 70.2
    hits = []                                      # (score, x, y, w, digit)
    # away from 1440p the game's digits are a little thinner than 1440p ones scaled (1080p: a 7 scores 0.58 at
    # the plain scale, 0.68 at 0.9 of it): a second, slightly smaller size is tried there too
    for f in ((1.0,) if abs(k - 1) <= 0.02 else (1.0, 0.9)):
        for d, pics in tpls.items():
            for t in pics:
                tt = cv2.resize(t, None, fx=k * f, fy=k * f, interpolation=cv2.INTER_AREA) \
                    if abs(k * f - 1) > 0.02 else t
                if tt.shape[0] > band.shape[0] or tt.shape[1] > band.shape[1]:
                    continue
                res = cv2.matchTemplate(band, tt, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(res >= DIGIT_MIN)
                for yy, xx in zip(ys, xs):
                    hits.append((float(res[yy, xx]), int(xx), int(yy), tt.shape[1], d))
    hits.sort(reverse=True)
    picked = []
    for h in hits:                                 # best first; no two digits overlap much (a 1 inside a 0's side)
        if all(min(h[1] + h[3], p[1] + p[3]) - max(h[1], p[1]) <= 0.3 * min(h[3], p[3]) for p in picked):
            picked.append(h)
    picked.sort(key=lambda p: p[1])
    if not picked or picked[0][1] > 0.16 * n:      # nothing that starts where a count does
        return (None, False, True) if _blobs(band, n) else (1, True, False)
    run = [picked[0]]
    for p in picked[1:]:                           # side by side, on one line - a hit further on is the icon
        last = run[-1]
        if p[1] - (last[1] + last[3]) <= 0.04 * n and abs(p[2] - run[0][2]) <= max(2, 0.04 * n):
            run.append(p)
        else:
            break
    end = run[-1][1] + run[-1][3]
    rest = [b for b in _blobs(band, n, 1.0, 0.15) if b[0] >= end - 1 and b[0] - end <= 0.04 * n
            and abs(b[1] - run[0][2]) <= 0.06 * n]      # (on the digits' line: art next to the count isn't a digit)
    if rest:                                       # a digit right after them the templates don't know: unsure
        return None, False, True
    return int("".join(p[4] for p in run)), True, True


def digit_run(cell):
    """The count's digits alone: the digit-sized white shapes on one line from the count's place (the item's own
    white highlights left out) -> [(x, y, w, h)] left to right, and the band's mask of only them."""
    cv2, np = _cv()
    band, _x0, _y0 = _band(cell)
    n = cell.width
    k, lab, st, _c = cv2.connectedComponentsWithStats((band > 0).astype(np.uint8), 8)
    keep = sorted((i for i in range(1, k) if 0.15 * n <= st[i][3] <= 0.27 * n and 0.02 * n <= st[i][2] <= 0.2 * n),
                  key=lambda i: st[i][0])
    if not keep or st[keep[0]][0] > 0.22 * n:
        return [], None
    run = [keep[0]]
    for i in keep[1:]:
        if abs(st[i][1] - st[run[0]][1]) <= max(2, 0.06 * n) and \
                st[i][0] - (st[run[-1]][0] + st[run[-1]][2]) <= 0.06 * n:
            run.append(i)
    return [tuple(int(v) for v in st[i][:4]) for i in run], np.isin(lab, run)


def ocr_count(cell):
    """OCR on the count's digits alone (a digit no learned shape knows) -> count, or None. 3.1: only when it reads as
    many digits as there are shapes (a "17" read as "7" is no count - and never teaches a wrong shape)."""
    try:
        import sys
        from PIL import Image
        _cv2, np = _cv()
        run, m = digit_run(cell)
        if not run:
            return None
        img = Image.fromarray(np.where(m, 0, 255).astype(np.uint8))
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
        canvas = Image.new("L", (img.width + 40, img.height + 40), 255)
        canvas.paste(img, (20, 20))
        if sys.platform == "win32":
            from . import remnant as _R
            lines = _R.ocr(canvas.convert("RGB"))
        else:
            from . import ocrengine
            if ocrengine.problem():
                return None
            lines = ocrengine.tesseract(canvas, prepped=True, psm="7")
        for text, _box in lines:
            t = text.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1")
            mm = re.fullmatch(r"\s*(\d{1,4})\s*", t)
            if mm and len(mm.group(1)) == len(run):
                return int(mm.group(1))
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- reading the whole grid
def scan(grid_img, tpls=None, ocr=None):
    """The grid (PIL) -> [{"cell": (r, c), "sig", "count", "sure", "shown"}] for every cell that holds something
    (shown: a stack number is drawn on it)."""
    tpls = digit_templates() if tpls is None else tpls
    out = []
    for rc, cell in split(grid_img).items():
        if empty(cell):
            continue
        n, sure, shown = _read(cell, tpls)
        if not sure and ocr is not False:
            n2 = (ocr or ocr_count)(cell)
            if n2 is not None:
                n, sure = n2, True
                try:
                    if keep_digits(cell, n2):
                        tpls = digit_templates()           # (the next cells know these digits)
                except Exception:
                    buglog.caught()
        out.append({"cell": rc, "sig": sig(cell), "count": n, "sure": sure, "shown": shown, "img": cell})
    return out


def learned():
    """{name: [picture, ...]} taught on this PC."""
    out = {}
    for name, pics in ((load_json(LEARN_FILE, {}) or {}).get("items") or {}).items():
        for p in pics:
            try:
                out.setdefault(name, []).append(sig_from(p))
            except Exception:
                continue
    return out


def icon_b64(name):
    """An item's small picture (base64 PNG) taught on this PC by an older version, or None."""
    return ((load_json(LEARN_FILE, {}) or {}).get("icons") or {}).get(name)


def forget(name):
    d = load_json(LEARN_FILE, {}) or {}
    for k in ("items", "icons"):
        (d.get(k) or {}).pop(name, None)
    save_json(LEARN_FILE, d)


def which(s, refs):
    """A cell's picture -> the taught item it is (or None)."""
    best, bd = None, SAME
    for name, pics in refs.items():
        for p in pics:
            dd = dist(s, p)
            if dd < bd:
                best, bd = name, dd
    return best


def totals(cells, name_of, wanted):
    """-> {name: (count, sure)} for each wanted item (0 when none is in the inventory); name_of(cell) -> the item a
    cell holds, or None."""
    out = {name: [0, True] for name in wanted}
    for c in cells:
        name = name_of(c)
        if name not in out:
            continue
        if c["count"] is None:
            out[name][1] = False
        else:
            out[name][0] += c["count"]
    return {k: (v[0], v[1]) for k, v in out.items()}


def low(tot, items, below=None):
    """Totals and your list ([{"name", "keep"}]) -> [(name, have, keep)] under their keep less `below` (2.131.2: the
    Remind when setting, 30% below by default; sure counts only)."""
    out = []
    for it in items:
        name, keep = it.get("name"), int(it.get("keep") or 0)
        if name not in tot:
            continue                                  # (no picture of it, or no read: nothing to compare)
        have, sure = tot[name]
        if keep > 0 and sure and have < remind_at(keep, below):
            out.append((name, have, keep))
    return out


def card_text(lows, most=3):
    parts = [f"{n} {h} / {k}" for n, h, k in lows[:most]]
    more = f" · +{len(lows) - most} more" if len(lows) > most else ""
    return " · ".join(parts) + more
