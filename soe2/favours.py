"""2.128.0 Favours prices (the Ritual helper): poe.ninja's price over each reward in the Ritual altar's Favours window,
like the Expedition helper's tags on a remnant's book. Idea and approach looked at in poe2pricer by saxe78 (MIT): the
window is found by a piece of its own art, items by their pictures - this is our own code.

How it reads (pure functions here; the watcher and the tags are in favours_page.py):
  1. The window: the word FAVOURS on its title plate. The first time, OCR finds the word in the press's picture and
     that piece of YOUR screen is kept (gameart.screen_look, only on this PC); later presses match it. Not there =
     the window isn't open. Nothing of the game ships with the app.
  2. The grid: 12 x 10 cells of 70 px (at 1440p), at a fixed offset from the title. A cell holds an item when its
     blue (or red) backing shows.
  3. Each 1-cell item is compared with the pictures learned on this PC of what poe.ninja's exchange prices (omens,
     currency, runes ...): Scan stash keeps each slot's picture of your Ritual, Currency ... tabs, and your price
     check key on a reward while the window is open keeps that one. Picture, outline and colors are compared, the
     stack number's corner left out (the game dims rewards you can't afford yet); the best one counts only when
     it's sure and clearly better than the next. Each picture is compared two ways: the cell's top part as it is,
     and cropped to the item's art (so a stash slot and a Favours cell, which draw it at different sizes, line up).
     3.1 (GGG ToS 7a - no game art ships): then poe.ninja's own picture of every exchange item, from the art cache
     on this PC, drawn the way the game draws a cell (gameart.Looks; the price tag's part left out). Mageblood,
     Headhunter and Rite of Passage get a ★ by poe.ninja's pictures of them (its unique lists).
Only looks at the screen: no keys, no clicks, nothing sent to the game. Nothing about you is saved: the pictures are
of items, and the log (ritual/favours_log.txt) says which item was found where and how sure."""
import base64
import os
from . import buglog

BASE_H = 1440
TITLE_SEARCH = (0.0, 0.0, 0.62, 0.42)      # where the title can be: x0, y0, x1, y1 as parts of the game's size
TITLE_MIN = 0.62                           # template score that counts as "the window is open" (other screens ~0.3)
GRID_DX, GRID_DY = -330, 169               # the grid's top-left from the title word's top-left (1440p px)
CELL = 70
COLS, ROWS = 12, 10
EDGE = 5                                   # px left off each side of a cell when comparing (the cell's frame)
SIDE = 48                                  # cells are compared at this size
MATCH_MIN = {"learned": 0.72, "shipped": 0.72, "icon": 0.72, "exchange": 0.60}  # 2.129.0 (feedback: a junk unique, Sacred Bloom and an omen all priced
MATCH_BY = 0.10                            # 4.6d): a picture must score this and beat the next-best item by this.
MATCH_BY_KIND = {"exchange": 0.12}         # 2.142.2: the Currency Exchange's icons (map profit only): the right item
#                                            0.64-0.90 on the user's inventory, by 0.15-0.27; gear under 0.45
MATCH_SURE, MATCH_BY_SURE = 0.80, 0.06      # (a very close match may beat the next by less: Greater Exaltation and
                                           # Refreshment are the same hand in gold / teal)
CLEAR = (0.50, 0.25)                       # 2.129.1: or far ahead of every other item (a gray, sealed reward - the
                                           # log: Sanctification 0.51, next 0.23; wrong ones were never 0.15 ahead)
def maybe_names(top):
    """3.0.6: Refs.ranked() of a cell best() couldn't name -> the items it could be: close to the top (VETO_BY) and
    above MAYBE_MIN - [] when nothing came close (a big item's corner, an item never learned)."""
    if not top or top[0][0] < MAYBE_MIN:
        return []
    return [n for s_, n, _k in top if s_ >= MAYBE_MIN and s_ >= top[0][0] - VETO_BY]


def has_stack_number(img, grid, r, c):
    """3.0.6: a Favours cell (BGR picture) shows a stack number ("1") - omens, currency; a unique, a ring or a big
    item's piece shows none."""
    try:
        from PIL import Image
        from . import topup as TU
        x, y, w, h = cell_rect(grid, r, c)
        cell = img[max(0, y):y + h, max(0, x):x + w]
        if not cell.size:
            return False
        return bool(TU._read(Image.fromarray(cell[:, :, ::-1].copy()))[2])
    except Exception:
        buglog.caught()
        return True


MAYBE_MIN = 0.68                           # 3.0.6: the vetoed Sinistral Erasure 0.82 / 0.71; gear corners under 0.65
VETO_BY = 0.15                             # 3.0.6: how close a better-colored item must score to veto (0.82 / 0.71)
HUE_BY = 0.25                              # 2.129.3: or close, but its colors match far better (Refreshment's teal
#                                            hand 0.54, Whittling's purple one 0.20)
CLEAR_ITEMS = 10                           # (only among many items - with two, "far ahead" says nothing)
#                                            Tried on the user's own windows with his Ritual tab's pictures (Scan
#                                            stash): the right omen 0.74-0.88 (by 0.14-0.34), items it doesn't know up
#                                            to 0.70 (by 0.06); official art reached 0.64 for the wrong item
PER_NAME = 6                               # pictures kept per item (a stash slot gives 3: its size varies a little)
BELTS = ("Mageblood", "Headhunter")       # 2.129.0: a ★, no price (3.1: poe.ninja's pictures of them, 2 x 1 belts)
BELT_MIN = 0.70
STARS = ("Rite of Passage",)              # 2.129.3 (feedback): one-cell uniques worth a ★ (poe.ninja's picture; your
STAR_MIN = 0.70                            # Ctrl+C on one in the window teaches it too)
LEARN_FILE = "favour_icons_v2.json"
BOX_FILE = "favour_boxes.json"             # 2.129.0: the same items cropped to their art (art_box)
ART_DIFF = 40                              # a pixel this far from the cell's own backing color is the item's art           # (2.128.1: the cell's top part - v1 held whole cells)
TOP = 0.64                                 # 2.128.1: only a cell's top part is read - the price tag sits at its
#                                            foot and shows in screenshots and streams (the watcher sees it too)


def _cv():
    import cv2
    import numpy as np
    return cv2, np


TITLE_KEY = "favours_title"                # gameart.screen_look: the title as this PC's screen showed it
TITLE_WORDS = ("favours",)
OCR_GRID = (-350, 163)                     # the grid's top-left from the OCR'd word's top-left (1440p px, about:
GRID_REACH = 20                            # the grid's own lines then place it - px each way at 1440p)


def title_template():
    """The Favours window's title as YOUR screen showed it (learned the first time OCR read the word - 3.1: no picture
    of it ships), "ocr" when not learned yet but a text reader can look for it, None when neither (nothing to look
    for)."""
    from . import gameart as GA
    lk = GA.screen_look(TITLE_KEY)
    if lk is not None:
        return lk[0]
    try:
        import sys
        if sys.platform != "win32":
            from . import ocrengine
            if ocrengine.problem() and GA.OCR[0] is None:
                return None
    except Exception:
        return None
    return "ocr"


def _lattice(gray, x0, y0, cs):
    """How strongly the grid's cell borders show with its top-left at (x0, y0): edges on the lines minus edges half a
    cell off them."""
    cv2, np = _cv()
    h, w = gray.shape[:2]
    xs = [int(round(x0 + c * cs)) for c in range(COLS + 1)]
    ys = [int(round(y0 + r * cs)) for r in range(ROWS + 1)]
    if xs[0] < 1 or ys[0] < 1 or xs[-1] >= w - 1 or ys[-1] >= h - 1:
        return -1e9
    g = gray.astype(np.float32)
    on = np.mean([np.abs(g[ys[0]:ys[-1], x + 1] - g[ys[0]:ys[-1], x - 1]).mean() for x in xs]) + \
        np.mean([np.abs(g[y + 1, xs[0]:xs[-1]] - g[y - 1, xs[0]:xs[-1]]).mean() for y in ys])
    hc = int(cs / 2)
    off = np.mean([np.abs(g[ys[0]:ys[-1], x + hc + 1] - g[ys[0]:ys[-1], x + hc - 1]).mean() for x in xs[:-1]]) + \
        np.mean([np.abs(g[y + hc + 1, xs[0]:xs[-1]] - g[y + hc - 1, xs[0]:xs[-1]]).mean() for y in ys[:-1]])
    return float(on - off)


def place_grid(gray, x, y, s, reach=GRID_REACH):
    """About where the grid starts -> where its cell borders are (px of gray), searched reach px (1440p) each way."""
    r = max(1, int(round(reach * s)))
    best = max((_lattice(gray, x + dx, y + dy, CELL * s), dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1))
    return x + best[1], y + best[2]


def find_window(gray, tpl, game_h=None, game_w=None):
    """The game's picture (grayscale; its top-left part will do - give the whole game's size then) -> (x, y, scale,
    score): where the title's anchor is (grid_box() places the grid from it), or None. tpl: title_template() - the
    title learned on this PC, or "ocr": read the word and learn it now."""
    cv2, np = _cv()
    from . import gameart as GA
    h, w = game_h or gray.shape[0], game_w or gray.shape[1]
    s = h / BASE_H
    x0, y0 = int(w * TITLE_SEARCH[0]), int(h * TITLE_SEARCH[1])
    x1 = min(int(w * TITLE_SEARCH[2]), int(h * 16 / 9 * TITLE_SEARCH[2]))   # 3.0.6: the window is left-anchored -
    area = gray[y0:min(gray.shape[0], int(h * TITLE_SEARCH[3])), x0:min(gray.shape[1], x1)]   # ultrawide: same reach
    if tpl is None or not area.size:
        return None
    if isinstance(tpl, str):                       # 3.1: not learned yet - OCR finds the word, its look is kept
        from PIL import Image
        box = GA.find_word(Image.fromarray(np.ascontiguousarray(area)), TITLE_WORDS)
        if box is None:
            return None
        gx, gy = place_grid(gray, x0 + box[0] + OCR_GRID[0] * s, y0 + box[1] + OCR_GRID[1] * s, s)
        p = max(2, int(round(4 * s)))
        cx0, cy0 = max(0, box[0] - p), max(0, box[1] - p)
        crop = area[cy0:box[3] + p, cx0:box[2] + p]
        GA.keep_screen_look(TITLE_KEY, crop, h, {"gdx": (gx - (x0 + cx0)) / s, "gdy": (gy - (y0 + cy0)) / s})
        return gx - GRID_DX * s, gy - GRID_DY * s, s, 1.0
    lk = GA.screen_look(TITLE_KEY)
    learned = lk is not None and tpl is lk[0]
    k = h / float(lk[1]) if learned else s
    t = cv2.resize(tpl, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if abs(k - 1) > 0.01 else tpl
    if area.shape[0] < t.shape[0] or area.shape[1] < t.shape[1]:
        return None
    r = cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED)
    _mn, mx, _l, loc = cv2.minMaxLoc(r)
    if mx < TITLE_MIN:
        return None
    ex = GA.look_extra(TITLE_KEY) if learned else {}
    if "gdx" in ex:                                # (the grid, where it was from the learned title)
        gx, gy = loc[0] + x0 + ex["gdx"] * s, loc[1] + y0 + ex["gdy"] * s
        return gx - GRID_DX * s, gy - GRID_DY * s, s, float(mx)
    return loc[0] + x0, loc[1] + y0, s, float(mx)


def grid_box(win):
    """-> (x, y, cell) of the grid's top-left in the game's pixels."""
    x, y, s, _sc = win
    return int(round(x + GRID_DX * s)), int(round(y + GRID_DY * s)), CELL * s


def cell_rect(grid, r, c):
    gx, gy, cs = grid
    return int(round(gx + c * cs)), int(round(gy + r * cs)), int(round(cs)), int(round(cs))


def backing(img_bgr):
    """'blue' / 'red' / None: a cell's backing (an item is there) - the share of bluish or reddish pixels."""
    _cv2, np = _cv()
    a = img_bgr.astype(np.int16)
    b, g, r = a[..., 0], a[..., 1], a[..., 2]
    if ((b > g + 12) & (b > r + 8)).mean() > 0.25:
        return "blue"
    if ((r > g + 25) & (r > b + 15)).mean() > 0.25:
        return "red"
    return None


def occupied(img, grid):
    """-> {(r, c): 'blue' / 'red'} for every cell of the grid that holds (part of) an item."""
    out = {}
    for r in range(ROWS):
        for c in range(COLS):
            x, y, w, h = cell_rect(grid, r, c)
            m = max(2, int(w * 0.09))
            cut = img[y + m:y + int(h * TOP), x + m:x + w - m]
            if cut.size:
                k = backing(cut)
                if k:
                    out[(r, c)] = k
    return out


def feats(bgr):
    """A cell's picture -> (gray, outline, color) at SIDE x SIDE, each with mean 0 and length 1 (so a dot product =
    the normalized correlation). 2.129.0: the stack number's corner (top-left) is left out - "1" here, "30" in a
    stash slot - and the colors count too (omens differ most by color)."""
    cv2, np = _cv()
    im = cv2.resize(bgr, (SIDE, SIDE), interpolation=cv2.INTER_AREA).copy()
    im[:int(SIDE * 0.42), :int(SIDE * 0.5)] = im[int(SIDE * 0.42):, :].reshape(-1, 3).mean(0)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    col = cv2.resize(im, (12, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
    col = col - col.reshape(-1, 3).mean(0)
    out = []
    for a in (g, np.sqrt(gx * gx + gy * gy), col):
        a = a - a.mean() if a is not col else a
        n = float(np.sqrt((a * a).sum())) or 1.0
        out.append((a / n).ravel())
    out.append(hue(im))
    out.append(tint(im))
    return tuple(out)


def tint(bgr):
    """3.0.6: the art's own average color (Lab), or None - the colors above take the overall tint out, so look-alike
    items in other tints (the Perfect Essences: one crystal, many colors) scored the same."""
    cv2, np = _cv()
    a = bgr.astype(np.float32)
    ring = np.concatenate([a[:2].reshape(-1, 3), a[-2:].reshape(-1, 3), a[:, :2].reshape(-1, 3), a[:, -2:].reshape(-1, 3)])
    m = np.sqrt(((a - np.median(ring, 0)) ** 2).sum(-1)) > 25
    h, w = m.shape
    m[:int(h * 0.42), :int(w * 0.5)] = False                     # (the stack number's corner)
    if m.sum() < 20:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)[m].mean(0)


def tint_gap(fa, fb):
    """How far apart two cells' tints are (Lab), or None."""
    _cv2, np = _cv()
    a, b = (fa[4] if len(fa) > 4 else None), (fb[4] if len(fb) > 4 else None)
    return float(np.linalg.norm(a - b)) if a is not None and b is not None else None


def hue(bgr):
    """2.129.3: which colors the item's art has (12 hue bins of its saturated pixels, summing to 1), or None (too few)
    - the colors above take out the overall tint, so the same hand in teal (Refreshment) and purple (Whittling) looked
    alike. Only pixels unlike the backing count; the stack number's corner is left out."""
    cv2, np = _cv()
    a = bgr.astype(np.float32)
    ring = np.concatenate([a[:2].reshape(-1, 3), a[-2:].reshape(-1, 3), a[:, :2].reshape(-1, 3), a[:, -2:].reshape(-1, 3)])
    d = np.sqrt(((a - np.median(ring, 0)) ** 2).sum(-1))
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s_, v_ = hsv[..., 1].astype(np.float32), hsv[..., 2].astype(np.float32)
    m = (d > 25) & (s_ > 60) & (v_ > 25)
    m[:int(m.shape[0] * 0.35), :int(m.shape[1] * 0.45)] = False
    if int(m.sum()) <= 15:
        return None
    h = np.bincount((hsv[..., 0][m] // 15).astype(int).ravel(), weights=(s_ * v_)[m], minlength=12)[:12]
    t = float(h.sum())
    return h / t if t else None


def hue_sim(fa, fb):
    """How alike two cells' colors are (0 .. 1), or None when either has too few colored pixels."""
    _cv2, np = _cv()
    a, b = (fa[3] if len(fa) > 3 else None), (fb[3] if len(fb) > 3 else None)
    return float(np.minimum(a, b).sum()) if a is not None and b is not None else None


def score(fa, fb):
    """How alike two cells are (-1 .. 1): half the better of picture and outline (outline survives the dimming),
    half the colors."""
    shape = max(float((fa[0] * fb[0]).sum()), float((fa[1] * fb[1]).sum()))
    return 0.5 * shape + 0.5 * float((fa[2] * fb[2]).sum())


def scaled(bgr, k):
    """A picture zoomed by k about its middle, the same size (a stash slot draws an item a little bigger or smaller
    than a Favours cell)."""
    cv2, np = _cv()
    h, w = bgr.shape[:2]
    nb = cv2.resize(bgr, None, fx=k, fy=k, interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    H, W = nb.shape[:2]
    if k >= 1:
        y, x = (H - h) // 2, (W - w) // 2
        return nb[y:y + h, x:x + w]
    out = np.empty_like(bgr)
    out[:] = bgr.reshape(-1, 3).mean(0)
    y, x = (h - H) // 2, (w - W) // 2
    out[y:y + H, x:x + W] = nb
    return out


def cell_crop(img, grid, r, c):
    """A cell's picture without its frame - its top part only (TOP: under it, a price tag may be showing)."""
    x, y, w, h = cell_rect(grid, r, c)
    e = max(1, int(round(EDGE * w / CELL)))
    return img[y + e:y + int(h * TOP), x + e:x + w - e]


def art_box(bgr, corner=True):
    """2.129.0: a cell's (or stash slot's) inside -> a square around the item's art: the pixels unlike the backing
    (its color = the median of the edge), the stack number's corner left out. A stash slot draws an item bigger or
    smaller than a Favours cell - cropped to the art, both line up."""
    cv2, np = _cv()
    h, w = bgr.shape[:2]
    if h < 12 or w < 12:
        return bgr
    a = bgr.astype(np.float32)
    ring = np.concatenate([a[:2].reshape(-1, 3), a[-2:].reshape(-1, 3), a[:, :2].reshape(-1, 3), a[:, -2:].reshape(-1, 3)])
    d = np.sqrt(((a - np.median(ring, 0)) ** 2).sum(-1))
    m = (d > ART_DIFF).astype(np.uint8)
    if corner:
        m[:int(h * 0.35), :int(w * 0.45)] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(m)
    if len(xs) < 30:
        return bgr
    x0, x1 = np.percentile(xs, [3, 97]).astype(int)
    y0, y1 = np.percentile(ys, [3, 97]).astype(int)
    s = max(10, int(x1 - x0), int(y1 - y0))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    x0, y0 = max(0, cx - s // 2), max(0, cy - s // 2)
    return bgr[y0:min(h, y0 + s), x0:min(w, x0 + s)]


def cell_inside(img, grid, r, c):
    """A whole cell without its frame (for art_box)."""
    x, y, w, h = cell_rect(grid, r, c)
    e = max(1, int(round(EDGE * w / CELL)))
    return img[y + e:y + h - e, x + e:x + w - e]


def cell_feats(img, grid, r, c):
    """-> {"top": feats of the cell's top part, "box": feats of its art} (None if the cell is off the picture)."""
    cv2, _np = _cv()
    top = cell_crop(img, grid, r, c)
    if not top.size:
        return None
    return {"top": feats(top), "box": feats(art_box(cell_inside(img, grid, r, c)))}


def slot_sides(bgr):
    """A stash slot's inside (a whole cell) -> [(mode, SIDE x SIDE picture)]: its top part at 3 sizes, and its art."""
    cv2, _np = _cv()
    out = [("top", cv2.resize(top_part(scaled(bgr, k)), (SIDE, SIDE), interpolation=cv2.INTER_AREA))
           for k in (0.88, 1.0, 1.12)]
    e = max(1, int(round(4 * bgr.shape[1] / CELL)))
    out.append(("box", cv2.resize(art_box(bgr[e:-e, e:-e]), (SIDE, SIDE), interpolation=cv2.INTER_AREA)))
    return out


def top_part(bgr):
    """A whole cell's picture (official art laid on the backing) -> the same part cell_crop takes."""
    h, w = bgr.shape[:2]
    e = max(1, int(round(EDGE * w / CELL)))
    return bgr[e:int(h * TOP), e:w - e]


class Refs:
    """The pictures to compare with: {name: [feats, ...]} - official art (normal and dimmed) and learned ones."""

    def __init__(self):
        self.items = {}
        # 3.0.6 Map Profit's fallbacks (mapprofit.build_refs fills them): the gem items' names (lineage / uncut gems
        # show no stack number), Scan stash's wildcard pictures {name: 26 x 40}, poe.ninja's art (Refs, or None)
        # and the names each art entry stands for ({entry: [names]} - one picture, many levels or grades)
        self.gems, self.stash, self.art, self.groups = set(), {}, None, {}
        self.looks = None          # 3.1: poe.ninja's pictures drawn as the game draws a cell (gameart.Looks)

    def add(self, name, bgr, src="art", mode="top"):
        self.items.setdefault(name, []).append((feats(bgr), src, mode))

    def ranked(self, f, n=3, refs=False):
        """f: cell_feats() (both ways) or feats() (the top part only) -> [(score, name, kind of picture)] best first:
        each item's best picture, each compared the same way it was taken. refs=True: (score, name, kind, the cell's
        feats, the picture's feats) - for the colors."""
        both = f if isinstance(f, dict) else {"top": f}
        out = []
        for name, lst in self.items.items():
            got = [(score(both[m], rf), s, both[m], rf) for rf, s, m in lst if both.get(m) is not None]
            if got:
                sc, src, cf, rf = max(got, key=lambda x: x[0])
                out.append((sc, name, src, cf, rf) if refs else (sc, name, src))
        out.sort(key=lambda t: -t[0])
        return out[:n]

    def best(self, f):
        """-> (name, score, margin over the next item) or (None, best score, margin)."""
        top3 = self.ranked(f, 2, refs=True)
        if not top3:
            return None, 0.0, 0.0
        top, name, src = top3[0][:3]
        nxt = top3[1][0] if len(top3) > 1 else -1.0
        by = MATCH_BY_SURE if top >= MATCH_SURE else MATCH_BY_KIND.get(src, MATCH_BY)
        sure = top >= MATCH_MIN.get(src, 0.72) and top - nxt >= by
        if top >= CLEAR[0] and top - nxt < CLEAR[1]:      # ("far ahead" of the items whose pictures are of the
            same = [s_ for s_, _n, k in self.ranked(f, len(self.items))[1:] if k == src]    # same kind: an idol's
            nxt_same = same[0] if same else -1.0                                             # exchange icon isn't
        else:                                                                                # one of an omen's)
            nxt_same = nxt
        kinds = sum(1 for lst in self.items.values() if any(s_ == src for _f, s_, _m in lst))
        clear = top >= CLEAR[0] and top - nxt_same >= CLEAR[1] and kinds >= CLEAR_ITEMS
        if not (sure or clear) and len(top3) > 1 and top >= MATCH_MIN.get(src, 0.72):
            h1, h2 = hue_sim(top3[0][3], top3[0][4]), hue_sim(top3[1][3], top3[1][4])
            sure = h1 is not None and h2 is not None and h1 - h2 >= HUE_BY       # 2.129.3: same shape, other color
        if (sure or clear) and self.hue_veto(f, top):
            sure = clear = False
        if sure or clear:
            return name, top, top - nxt
        return None, top, top - nxt

    def hue_veto(self, f, top=None):
        """3.0.6 (owner: an Omen of Sinistral Erasure, 22 div, tagged as a 3.4ex Omen of Resurgence - a costly
        miss): the same horn ring, purple specks vs teal ones. Not sure when another item scores close
        (VETO_BY) but its colors match far better (HUE_BY)."""
        got = self.ranked(f, 4, refs=True)
        if len(got) < 2:
            return False
        top = got[0][0] if top is None else top
        h1 = hue_sim(got[0][3], got[0][4])
        if h1 is None:
            return False
        for sc, _n, _s, cf, rf in got[1:]:
            h = hue_sim(cf, rf)
            if sc >= max(top - VETO_BY, MAYBE_MIN) and h is not None and h - h1 >= HUE_BY:
                return True
        return False


    def alike(self, f):
        """3.0.6 (things already learned for Scan stash were missing): when best() can't pick, the items this
        could be - learned pictures only, each very close (MATCH_SURE, within MATCH_BY of the top) and in the same
        tint (TINT_MAX). -> [names], best first: one = that item; more = look-alikes (Perfect Essence of Abrasion /
        Enhancement - the same white crystal)."""
        got = self.ranked(f, 8, refs=True)
        if not got or got[0][0] < MATCH_SURE:
            return []
        top = got[0][0]
        out = []
        for sc, name, src, cf, rf in got:
            if sc < top - MATCH_BY or src not in ("learned", "shipped") or sc < MATCH_SURE:
                continue
            gap = tint_gap(cf, rf)
            if gap is None or gap <= TINT_MAX:
                out.append(name)
        return out


TINT_MAX = 15.0                   # 3.0.6: the right item's tint was 0.1-6.5 away on the owner's inventory, the wrong
#                                   Perfect Essences 17-84 (two white ones 9 and 11: both kept, counted at the lower)
TWIN = 0.86                       # 2.130.4: an unknown cell this like a known one in the same window is the same item


def twins(known, unknown):
    """2.130.4 (feedback: some items were not shown when duplicated - price all, even the same one):
    known [(feats, name)], unknown [(key, feats)] -> {key: (name, score)} - a reward the pictures didn't name, but that
    looks just like one named in this same window (same art, same light, same frame), is that item too."""
    out = {}
    for key, f in unknown:
        best = None
        for kf, name in known:
            sc = max(score(f[m], kf[m]) for m in ("top", "box") if f.get(m) is not None and kf.get(m) is not None) \
                if any(f.get(m) is not None and kf.get(m) is not None for m in ("top", "box")) else -1.0
            if best is None or sc > best[1]:
                best = (name, sc)
        if best and best[1] >= TWIN:
            out[key] = best
    return out


def single_cells(occ):
    """Cells that could be a 1-cell item. The grid fills column by column from the top-left, so a big item's cells
    can't be told apart from small ones here - every occupied cell is tried; a big item's pieces match nothing."""
    return sorted(occ)


def read(img, refs, tpl):
    """The game's picture (BGR) -> (window found, [(r, c, name or None, score, (x, y, w, h))]) for every occupied cell."""
    cv2, _np = _cv()
    win = find_window(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), tpl)
    if win is None:
        return None, []
    grid = grid_box(win)
    occ = occupied(img, grid)
    out = []
    for r, c in single_cells(occ):
        f = cell_feats(img, grid, r, c)
        if f is None:
            continue
        name, sc, _m = refs.best(f)
        out.append((r, c, name, sc, cell_rect(grid, r, c)))
    return win, out


# ---- pictures learned on this PC (you price checked a reward while the window was open)
def learned(file=LEARN_FILE):
    """{name: [SIDE x SIDE pictures]} - LEARN_FILE: top parts, BOX_FILE: cropped to the art."""
    _cv2, np = _cv()
    from .config import load_json
    out = {}
    for name, pics in (load_json(file, {}) or {}).items():
        for b in pics if isinstance(pics, list) else [pics]:
            try:
                out.setdefault(name, []).append(np.frombuffer(base64.b64decode(b), np.uint8).reshape(SIDE, SIDE, 3))
            except Exception:
                continue
    return out


def learn_many(pics):
    """{name: a stash slot's picture (its inside, a whole cell)} -> remembered like learn() (the top part, as a
    Favours cell is read), in one write. -> how many."""
    cv2, np = _cv()
    from .config import load_json, save_json
    d = load_json(LEARN_FILE, {}) or {}
    bx = load_json(BOX_FILE, {}) or {}
    n = 0
    for name, bgr in (pics or {}).items():
        if bgr is None or not bgr.size or not name:
            continue
        sides = slot_sides(bgr)
        new = [_b64(p) for m, p in sides if m == "top"]
        lst = [x for x in (d.get(name) or []) if isinstance(x, str) and x not in new]
        d[name] = (lst + new)[-PER_NAME:]
        _keep(bx, name, [_b64(p) for m, p in sides if m == "box"])
        n += 1
    if n:
        save_json(LEARN_FILE, d)
        save_json(BOX_FILE, bx)
    return n


def _b64(small):
    _cv2, np = _cv()
    return base64.b64encode(np.ascontiguousarray(small).tobytes()).decode()


def _keep(d, name, new, most=3):
    lst = [x for x in (d.get(name) or []) if isinstance(x, str) and x not in new]
    d[name] = (lst + new)[-most:]


def learn(name, bgr, inside=None):
    """Remember what this reward looks like in the Favours window: bgr = its cell's top part (cell_crop), inside = the
    whole cell without its frame (cell_inside: kept cropped to its art too)."""
    cv2, np = _cv()
    from .config import load_json, save_json
    if bgr is None or not bgr.size or not name:
        return False
    small = cv2.resize(bgr, (SIDE, SIDE), interpolation=cv2.INTER_AREA)
    d = load_json(LEARN_FILE, {}) or {}
    lst = [x for x in (d.get(name) or []) if isinstance(x, str)]
    d[name] = (lst + [_b64(small)])[-PER_NAME:]
    save_json(LEARN_FILE, d)
    if inside is not None and inside.size:
        bx = load_json(BOX_FILE, {}) or {}
        _keep(bx, name, [_b64(cv2.resize(art_box(inside), (SIDE, SIDE), interpolation=cv2.INTER_AREA))])
        save_json(BOX_FILE, bx)
    return True


# ---- what poe.ninja's exchange prices (only those are priced here)
def ninja_items(parts):
    """poe.ninja's exchange answers (WPRICES.parts) -> {id: (name, picture path)} for every exchange item - never a
    unique."""
    out = {}
    for typ, p in (parts or {}).items():
        if str(typ).startswith("Unique"):
            continue
        names = (p or {}).get("names") or {}
        for nid, name in names.items():
            out[nid] = (name or nid, ((p or {}).get("images") or {}).get(nid))
    return out


def build_refs(items, exchange=False, pic=None):
    """{id: (name, path)} -> Refs from the pictures learned on this PC: Scan stash (each slot of your Ritual,
    Currency ... tabs) and your price check key on a reward. 3.1 (GGG ToS 7a: no game art ships): and poe.ninja's
    picture of every exchange item already in the art cache, drawn as the game draws a cell (refs.looks) - a whole
    inventory cell (exchange=True, Map Profit / Top Up) or a Favours cell's top part (its price tag left out).
    pic: url -> a file or pixels (tests)."""
    from . import gameart as GA
    refs = Refs()
    known = {name for name, _p in items.values()}
    for name, pics in learned().items():
        if known and name not in known:                   # 2.129.0: an exchange item only (a learned unique
            continue                                      # - Coat of Red - is never priced)
        for p in pics:
            refs.add(name, p, "learned")
    for name, pics in learned(BOX_FILE).items():
        if known and name not in known:
            continue
        for p in pics:
            refs.add(name, p, "learned", "box")
    try:
        refs.looks = GA.looks(items, art_key, top=1.0 if exchange else TOP, pic=pic)
    except Exception:
        buglog.caught()
    return refs


LOOK_HUE_BY = 0.25                # 3.1: two pictures alike in shape (Omen of Sinistral Erasure / Resurgence: the same
#                                   horn ring) - the one whose colors match this much better (owner's window: 0.33
#                                   vs 0.02); closer than that, neither (never a guess)


def look_name(cell, refs, only=None):
    """3.1: a whole cell of the screen (BGR, its frame included) -> the key of poe.ninja's picture it is (refs.looks:
    gameart.MIN, gameart.BY ahead of the next picture; within BY, the one whose colors match LOOK_HUE_BY better),
    or None. only: the keys that may compete."""
    from . import gameart as GA
    lk = getattr(refs, "looks", None)
    if lk is None or not len(lk) or cell is None or not getattr(cell, "size", 0):
        return None
    key, top, lead = lk.best(cell, only=only)
    if key is not None:
        return key
    if top < GA.MIN:
        return None
    got = [g for g in lk.rank(cell, 4, only) if g[0] >= top - GA.BY]
    if len(got) < 2:
        return None
    cv2, np = _cv()
    h, w = cell.shape[:2]
    e = max(1, int(round(GA.EDGE * w)))

    def part(bgr):
        return hue(bgr[e:int(h * lk.top) if lk.top < 1 else h - e, e:w - e])
    hc = part(cell)
    if hc is None:
        return None
    sims = []
    for sc, k in got:
        ref = lk.pictures.get(k)
        hr = part(cv2.resize(ref, (w, h), interpolation=cv2.INTER_AREA)) if ref is not None else None
        sims.append((float(np.minimum(hc, hr).sum()) if hr is not None else -1.0, k, sc))
    sims.sort(reverse=True)
    if sims[0][2] >= GA.MIN and sims[0][0] - sims[1][0] >= LOOK_HUE_BY:
        return sims[0][1]
    return None


ART_MIN, ART_BY = 0.80, 0.10       # 3.0.6: poe.ninja's art, Map Profit's last fallback (official art scored up to
#                                    0.64 for the wrong item on Favours cells): this sure and this far ahead, or nothing
ART_SOFT, ART_LEAD = 0.70, 0.20   # 3.0.6 (owner's scan: Vaal Catalysing Infuser 0.77, Orb of Extraction 0.71 - each
#                                   0.24+ ahead of the next): a clear lead counts under ART_MIN too
ART_BACKING = (41, 5, 5)           # an inventory cell's dark blue (BGR): the art is laid on it, as the game draws it
CDN = "https://web.poecdn.com"     # (poe.ninja's picture paths are on the game's image server)
_LEVEL = r"^(.*) \(Level (\d+)\)$"
GRADE_WORDS = ("Greater ", "Perfect ")


def art_url(path):
    """poe.ninja's picture path -> its https URL, or None (gameart.url)."""
    from . import gameart as GA
    return GA.url(path)


def art_cache_file(url):
    """The art cache's file for this picture, or None when it isn't downloaded yet (gameart.cache_file)."""
    from . import gameart as GA
    return GA.cache_file(url)


def art_cell(pic):
    """poe.ninja's picture (a file, or BGR / BGRA pixels) of a 1-cell item -> a cell's inside as the inventory draws
    it (on the cell's dark blue, the frame left off), or None (not square: a big item)."""
    cv2, np = _cv()
    im = cv2.imread(pic, cv2.IMREAD_UNCHANGED) if isinstance(pic, str) else pic
    if im is None or im.ndim != 3 or not im.size:
        return None
    h, w = im.shape[:2]
    if abs(h - w) > 0.1 * max(h, w):
        return None
    im = cv2.resize(im, (CELL, CELL), interpolation=cv2.INTER_AREA if w > CELL else cv2.INTER_LINEAR)
    out = np.empty((CELL, CELL, 3), np.float32)
    out[:] = ART_BACKING
    if im.shape[2] == 4:
        a = im[..., 3:4].astype(np.float32) / 255.0
        out = im[..., :3].astype(np.float32) * a + out * (1 - a)
    else:
        out = im[..., :3].astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)[EDGE:CELL - EDGE, EDGE:CELL - EDGE]


def art_key(names):
    """The names that share one picture -> the one entry they're matched under, or None: one name; the levels of
    one item ("Uncut Skill Gem (Level 5)" ... -> "Uncut Skill Gem": the cell's level tells them apart); the grades
    of one orb (Regal / Greater / Perfect Regal Orb -> "Regal Orb": its II / III tells them apart). Other items
    that share a picture are never told apart (None)."""
    import re
    names = sorted(set(names))
    if len(names) == 1:
        return names[0]
    bases = {(re.match(_LEVEL, n) or [None, None])[1] for n in names}
    if len(bases) == 1 and None not in bases:
        return bases.pop()
    plain = {ungraded(n) for n in names}
    if len(plain) == 1 and plain <= set(names):
        return plain.pop()
    return None


def ungraded(name):
    """'Greater Regal Orb' -> 'Regal Orb' (the same orb's picture)."""
    for g in GRADE_WORDS:
        if name.startswith(g):
            return name[len(g):]
    return name


def art_refs(items, pic=None):
    """{id: (name, picture path)} -> Refs of poe.ninja's art (src "art") from the art cache - never downloaded
    here; Map Profit's page fills the cache. One entry per picture (art_key), its names in .groups. pic: url ->
    a file or pixels (tests)."""
    refs = Refs()
    by_url = {}
    for name, path in (items or {}).values():
        u = art_url(path)
        if u and name:
            by_url.setdefault(u, set()).add(name)
    for u, names in by_url.items():
        key = art_key(names)
        if key is None:
            continue
        src = pic(u) if pic else art_cache_file(u)
        if src is None:
            continue
        try:
            inside = art_cell(src)
        except Exception:
            buglog.caught()
            continue
        if inside is None:
            continue
        refs.add(key, art_box(inside, corner=False), "art", "box")
        refs.groups[key] = sorted(names)
    return refs


def unique_icons(parts=None):
    """{unique's name: poe.ninja's picture URL} from its unique lists (WPRICES.parts' "icons")."""
    if parts is None:
        try:
            from .wealth import WPRICES
            parts = getattr(WPRICES, "parts", None)
        except Exception:
            parts = None
    out = {}
    for typ, p in (parts or {}).items():
        if str(typ).startswith("Unique") and isinstance((p or {}).get("icons"), dict):
            out.update(p["icons"])
    return out


def belt_refs(parts=None, pic=None):
    """{name: feats} of Mageblood and Headhunter (2 x 1 belts): poe.ninja's pictures from the art cache, drawn on two
    cells as the game draws them (3.1: none ship). Not downloaded yet: not looked for."""
    from . import gameart as GA
    icons = unique_icons(parts)
    out = {}
    for name in BELTS:
        u = GA.url(icons.get(name))
        src = (pic(u) if pic else GA.cache_file(u)) if u else None
        if src is None:
            continue
        im = GA.drawn(src, 2 * CELL, CELL)
        if im is not None:
            e = EDGE
            out[name] = feats(im[e:int(CELL * TOP), e:2 * CELL - e])
    return out


def star_refs(parts=None, pic=None):
    """Refs of the one-cell uniques that get a ★ (STARS): poe.ninja's picture of each (art cache), and pictures
    learned on this PC."""
    from . import gameart as GA
    refs = Refs()
    icons = unique_icons(parts)
    for name in STARS:
        u = GA.url(icons.get(name))
        src = (pic(u) if pic else GA.cache_file(u)) if u else None
        im = GA.drawn(src) if src is not None else None
        if im is None:
            continue
        e = EDGE
        refs.add(name, im[e:int(CELL * TOP), e:CELL - e], "star", "top")
        refs.add(name, art_box(im[e:CELL - e, e:CELL - e]), "star", "box")
    for name, pics in learned().items():
        if name in STARS:
            for p in pics:
                refs.add(name, p, "star", "top")
    for name, pics in learned(BOX_FILE).items():
        if name in STARS:
            for p in pics:
                refs.add(name, p, "star", "box")
    return refs


def art_urls(parts=None):
    """3.1: every picture the Favours reader compares with - poe.ninja's exchange items and the ★ uniques (for the
    downloader: the art cache)."""
    from . import gameart as GA
    if parts is None:
        try:
            from .wealth import WPRICES
            parts = getattr(WPRICES, "parts", None)
        except Exception:
            parts = None
    icons = unique_icons(parts)
    urls = set(GA.missing(ninja_items(parts)))
    for n in BELTS + STARS:
        u = GA.url(icons.get(n))
        if u and GA.cache_file(u) is None:
            urls.add(u)
    return sorted(urls)


def find_stars(img, grid, cells, refs):
    """One-cell uniques worth a ★ among `cells` (the ones no exchange item matched) -> [(name, score, box)]."""
    out = []
    if not refs.items:
        return out
    for r, c in cells:
        f = cell_feats(img, grid, r, c)
        if f is None:
            continue
        top = refs.ranked(f, 1)
        if top and top[0][0] >= STAR_MIN:
            out.append((top[0][1], top[0][0], cell_rect(grid, r, c)))
    return out


def find_belts(img, grid, occ, refs):
    """2.129.0 (feedback: a star over a Headhunter or Mageblood that appears in the favour window):
    every two side-by-side cells that hold an item, compared with the belts -> [(name, score, (x, y, w, h))]."""
    out = []
    for r, c in sorted(occ):
        if (r, c + 1) not in occ:
            continue
        x, y, w, h = cell_rect(grid, r, c)
        x2, _y, w2, _h = cell_rect(grid, r, c + 1)
        e = max(1, int(round(EDGE * w / CELL)))
        cut = img[y + e:y + int(h * TOP), x + e:x2 + w2 - e]
        if not cut.size:
            continue
        f = feats(cut)
        for name, rf in refs.items():
            sc = score(f, rf)
            if sc >= BELT_MIN:
                out.append((name, sc, (x, y, x2 + w2 - x, h)))
    out.sort(key=lambda t: -t[1])
    seen, keep = set(), []
    for name, sc, box in out:
        if name not in seen:
            seen.add(name)
            keep.append((name, sc, box))
    return keep
