"""Game pictures at runtime - the app ships no game art (GGG ToS 7a: no redistributing game content).

Every item picture the app shows or reads the screen with comes from the image links poe.ninja and the trade site
already send with their prices (the game's own image server, web.poecdn.com). Each is downloaded once into the art
cache in your data folder (art/, like a browser's cache: rates_view.Icons does the downloading) and kept only on
this PC. Nothing here downloads: it only looks in the cache.

Reading the screen: the references are built here, on this PC, from those pictures - each drawn the way the game
draws a 1-cell item (its art at SCALE of the cell, centered on the cell's dark backing). Measured on 18 of the
owner's 1440p inventory screenshots (every stackable they held, 105 cells of 11 items, plus 22 cells of 10 more
items the shipped crops never named): the right item scored 0.87 - 0.96 and was first every time; gear with no
stack number 0.53 at most. Stash slots (the Ritual tab's omens) and a Favours cell are drawn the same (0.92 - 0.96).
No picture in the cache yet: nothing is named from it (never a guess) - the item's name stands in on screen."""
import hashlib
import os

CDN = "https://web.poecdn.com"
CELL = 70                       # a cell at 1440p (inventory, stash slot, Favours window)
SCALE = 0.975                   # the game draws a 1-cell item's art at this share of its cell, centered
BACKING = (41, 5, 5)            # an inventory cell's dark blue (BGR) - under the art's clear parts
SIDE = 40                       # cells are compared at SIDE x SIDE
EDGE = 0.07                     # the cell's frame (and a hover's orange ring) left out: this share of each side
CORNER = (0.50, 0.36)           # the stack number's corner (width, height shares) - left out
SHIFT = (-1.0, -0.5, 0.0, 0.5, 1.0)   # px (at SIDE) a cell is moved each way when compared (cells never line up
#                                       exactly: a Favours cell 1 px off at 1440p scored 0.72 instead of 0.87 unmoved)
MIN, BY = 0.80, 0.03            # sure: this score, and this far ahead of the next item with other art
#                                 (owner's screenshots: right items 0.87 - 0.96, by 0.05 or more; gear under 0.55)


def url(path):
    """poe.ninja's / the trade site's picture path -> its https URL, or None."""
    if not path:
        return None
    path = str(path)
    return path if path.startswith("https://") else (CDN + path if path.startswith("/") else None)


def cache_file(u):
    """The art cache's file for this picture URL (Exchange Rates' or Price Checks' name for it), or None when it
    isn't downloaded yet. Only looks."""
    from .config import P
    if not u:
        return None
    h = hashlib.sha1(str(u).encode()).hexdigest()[:20]
    for fn in ("cur_" + h + ".png", h + ".png"):
        p = os.path.join(P("art"), fn)
        if os.path.exists(p):
            return p
    return None


def _np():
    import cv2
    import numpy as np
    return cv2, np


def load(pic):
    """A cache file (or BGR / BGRA pixels) -> BGRA pixels, or None."""
    cv2, np = _np()
    im = cv2.imread(pic, cv2.IMREAD_UNCHANGED) if isinstance(pic, (str, os.PathLike)) else pic
    if im is None or not hasattr(im, "ndim") or im.ndim != 3 or not im.size:
        return None
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    return im


def drawn(pic, w=CELL, h=None, scale=SCALE, backing=BACKING):
    """An item's picture -> the cell (w x h) as the game draws it: the art scaled to fit SCALE of the cell, centered,
    on the backing. None when there's no picture."""
    cv2, np = _np()
    im = load(pic)
    if im is None:
        return None
    h = h or w
    ih, iw = im.shape[:2]
    k = scale * min(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * k))), max(1, int(round(ih * k)))
    im = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    out = np.empty((h, w, 3), np.float32)
    out[:] = backing
    x0, y0 = (w - nw) // 2, (h - nh) // 2
    xs, ys, xe, ye = max(0, x0), max(0, y0), min(w, x0 + nw), min(h, y0 + nh)
    sub = im[ys - y0:ye - y0, xs - x0:xe - x0].astype(np.float32)
    a = sub[..., 3:4] / 255.0
    out[ys:ye, xs:xe] = sub[..., :3] * a + out[ys:ye, xs:xe] * (1 - a)
    return np.clip(out, 0, 255).astype(np.uint8)


def mask(side=SIDE, top=1.0, corner=True):
    """Which pixels of a SIDE x SIDE cell are compared: the frame, the stack number's corner and (top < 1) the part
    under `top` (a Favours cell's price tag) left out."""
    _cv2, np = _np()
    m = np.ones((side, side), bool)
    e = max(1, int(round(EDGE * side)))
    m[:e] = m[-e:] = False
    m[:, :e] = m[:, -e:] = False
    if corner:
        m[:int(round(side * CORNER[1])), :int(round(side * CORNER[0]))] = False
    if top < 1.0:
        m[int(round(side * top)):] = False
    return m


class Looks:
    """References built on this PC from the art cache: {key: the cell as the game draws it}, compared with a cell
    of the screen by correlation (colors included) over mask(). keys: one per picture; names[key] = every item
    that picture stands for (one art, many levels or grades)."""

    def __init__(self, side=SIDE, top=1.0):
        _cv2, np = _np()
        self.side, self.top, self.keys, self.names, self.pictures = side, top, [], {}, {}
        self.m = mask(side, top)
        self._rows, self._mat = [], None

    def __len__(self):
        return len(self.keys)

    def _vec(self, bgr):
        cv2, np = _np()
        a = cv2.resize(bgr, (self.side, self.side), interpolation=cv2.INTER_AREA).astype(np.float32)[self.m].ravel()
        a = a - a.mean()
        n = float(np.linalg.norm(a))
        return a / n if n else None

    def add(self, key, cell, names=None):
        """cell: drawn() (or a learned picture of a whole cell)."""
        if cell is None:
            return False
        v = self._vec(cell)
        if v is None:
            return False
        self.keys.append(key)
        self.names[key] = sorted(names or [key])
        self.pictures[key] = cell
        self._rows.append(v)
        self._mat = None
        return True

    def rank(self, cell, n=3, only=None):
        """A cell of the screen (BGR, its whole inside) -> [(score, key)] best first, each key's best over small
        shifts. only: the keys that may compete."""
        cv2, np = _np()
        if not self.keys or cell is None or not cell.size:
            return []
        if self._mat is None:
            self._mat = np.stack(self._rows)
        c = cv2.resize(cell, (self.side, self.side), interpolation=cv2.INTER_AREA).astype(np.float32)
        best = None
        for dx in SHIFT:
            for dy in SHIFT:
                if dx or dy:
                    t = cv2.warpAffine(c, np.float32([[1, 0, dx], [0, 1, dy]]), (self.side, self.side),
                                       borderMode=cv2.BORDER_REPLICATE)
                else:
                    t = c
                v = t[self.m].ravel()
                v = v - v.mean()
                nv = float(np.linalg.norm(v))
                if not nv:
                    continue
                s = self._mat @ (v / nv)
                best = s if best is None else np.maximum(best, s)
        if best is None:
            return []
        idx = [i for i, k in enumerate(self.keys) if only is None or k in only]
        idx.sort(key=lambda i: -best[i])
        return [(float(best[i]), self.keys[i]) for i in idx[:n]]

    def best(self, cell, least=MIN, by=BY, only=None):
        """-> (key, score, lead) when it's sure (least, and by ahead of the next key), else (None, score, lead)."""
        got = self.rank(cell, 2, only)
        if not got:
            return None, 0.0, 0.0
        top, key = got[0]
        lead = top - (got[1][0] if len(got) > 1 else -1.0)
        return (key if top >= least and lead >= by else None), top, lead


def looks(items, key_of=None, top=1.0, pic=None):
    """{id: (name, picture path)} -> Looks of every picture already in the art cache. key_of(names) -> the key the
    names sharing one picture are matched under, or None (never told apart: left out). pic: url -> a file or pixels
    (tests). Missing pictures are simply not there yet (the pages download them)."""
    out = Looks(top=top)
    by_url = {}
    for name, path in (items or {}).values():
        u = url(path)
        if u and name:
            by_url.setdefault(u, set()).add(name)
    for u, names in sorted(by_url.items(), key=lambda kv: sorted(kv[1])):
        key = key_of(names) if key_of else (sorted(names)[0] if len(names) == 1 else None)
        if key is None:
            continue
        src = pic(u) if pic else cache_file(u)
        if src is None:
            continue
        im = load(src)
        if im is None or abs(im.shape[0] - im.shape[1]) > 0.1 * max(im.shape[:2]):
            continue                                    # (a big item's picture: not a 1-cell item)
        out.add(key, drawn(im), names)
    return out


def missing(items):
    """{id: (name, path)} -> the picture URLs not in the art cache yet (for the downloader)."""
    return sorted({u for _n, p in (items or {}).values() for u in [url(p)] if u and cache_file(u) is None})


# ---------------------------------------------------------------- the game's own frames, learned on this PC
# A window's title (the inventory's "Inventory", the Favours window's "Favours") has no picture on the image server.
# The first time a Read Key press shows it, the word is found by OCR in the press's picture and that piece of YOUR
# screen is kept (screen_looks.json in your data folder, gray, only on this PC); later presses match it like a
# template. Nothing of the game ships with the app.
LOOKS_FILE = "screen_looks.json"
_LOOKS = {}


def _ck(key):
    from .config import P
    return (P(LOOKS_FILE), key)                 # (another data folder: another cache)


def screen_look(key):
    """-> (gray picture, the game height it was taken at) learned on this PC, or None."""
    if _ck(key) in _LOOKS:
        return _LOOKS[_ck(key)]
    import base64
    from .config import load_json
    _cv2, np = _np()
    got = None
    try:
        d = (load_json(LOOKS_FILE, {}) or {}).get(key)
        if d:
            h, w, gh, b = int(d["h"]), int(d["w"]), int(d["game_h"]), d["px"]
            got = (np.frombuffer(base64.b64decode(b), np.uint8).reshape(h, w).copy(), gh)
    except Exception:
        got = None
    _LOOKS[_ck(key)] = got
    return got


def keep_screen_look(key, gray, game_h, extra=None):
    """Remember a piece of the player's own screen (gray, uint8) for key - taken at this game height."""
    import base64
    from .config import load_json, save_json
    _cv2, np = _np()
    if gray is None or not gray.size:
        return False
    gray = np.ascontiguousarray(gray, dtype=np.uint8)
    d = load_json(LOOKS_FILE, {}) or {}
    d[key] = dict({"h": int(gray.shape[0]), "w": int(gray.shape[1]), "game_h": int(game_h),
                   "px": base64.b64encode(gray.tobytes()).decode()}, **(extra or {}))
    save_json(LOOKS_FILE, d)
    _LOOKS[_ck(key)] = (gray, int(game_h))
    return True


def look_extra(key):
    """The extra numbers kept with a learned look (an anchor's offset ...), or {}."""
    from .config import load_json
    d = (load_json(LOOKS_FILE, {}) or {}).get(key) or {}
    return {k: v for k, v in d.items() if k not in ("h", "w", "game_h", "px")}


def forget_screen_look(key):
    from .config import load_json, save_json
    d = load_json(LOOKS_FILE, {}) or {}
    if d.pop(key, None) is not None:
        save_json(LOOKS_FILE, d)
    _LOOKS.pop(_ck(key), None)


def match_look(gray, key, game_h):
    """How well the learned look matches anywhere in gray (0 .. 1) and where: (score, (x, y), scale) - (0.0, None,
    1.0) when nothing is learned yet."""
    cv2, np = _np()
    lk = screen_look(key)
    if lk is None or gray is None:
        return 0.0, None, 1.0
    tpl, gh = lk
    s = float(game_h) / float(gh or game_h)
    t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR) \
        if abs(s - 1) > 0.01 else tpl
    if gray.shape[0] < t.shape[0] or gray.shape[1] < t.shape[1] or t.size == 0:
        return 0.0, None, s
    _mn, mx, _l, loc = cv2.minMaxLoc(cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED))
    return float(mx), loc, s


OCR = [None]                    # tests: fn(PIL picture) -> [(text, (x0, y0, x1, y1))]


def _read_text(pic):
    """OCR lines of a (prepared) picture: Windows' reader, or Tesseract as it is (no second preparing)."""
    import sys
    if OCR[0] is not None:
        return OCR[0](pic)
    if sys.platform == "win32":
        from . import remnant as RM
        return RM.ocr(pic.convert("RGB"))
    from . import ocrengine
    if ocrengine.problem():
        return []
    return ocrengine.tesseract(pic.convert("L"), prepped=True, psm="11")


LAST_READ = []                  # find_word's last read: every line's words - the log says them when nothing matched


def find_word(img, words, biggest=False):
    """A picture (PIL) -> the box (x0, y0, x1, y1, in its pixels) of the first word that is one of `words` (lower
    case, spaces ignored), or None. Read twice if needed - as it is and light-on-dark turned around - each made
    twice as big (a small area) with full contrast - a title's dark letters on a light plate read best that way.
    biggest: of every line that matches, the tallest - a panel's title over a tab with the same word."""
    from PIL import ImageOps
    want = {w.replace(" ", "").lower() for w in words}
    g = ImageOps.autocontrast(img.convert("L"))
    k = 2 if g.width * g.height <= 400_000 else 1          # (a big area is read as it is: quick enough)
    if k != 1:
        g = g.resize((g.width * k, g.height * k))
    seen = []
    for pic in (g, ImageOps.invert(g)):
        try:
            lines = _read_text(pic)
        except Exception as e:
            seen.append(f"<the text reader failed: {e.__class__.__name__}>")
            continue
        hits = []
        for text, box in lines or []:
            seen.append(str(text))
            t = str(text).replace(" ", "").lower()
            if any(w in t for w in want):
                hits.append(tuple(int(round(v / k)) for v in box))
                if not biggest:
                    break
        if hits:
            LAST_READ[:] = seen
            return max(hits, key=lambda b: b[3] - b[1])
    LAST_READ[:] = seen
    return None
