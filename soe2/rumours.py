"""2.83.0: Island Rumors helper (Expedition) - the world map's "Uncharted Waters" card lists up to three rumors;
each gets a tag with the island it leads to and your Map library rank for it (feedback: use our Map library to build
an add-on that operates the rumor helper).

Which rumor leads where: epoe.io's Expedition guide, reviewed for 0.5.5e (3.0.6: an RMT site that was once a
second check is no longer a source - owner: RMT sites are never used). Ranks are yours - set them in the Map library (the suggested ones are in the 2.83.0 notes).
On screen: the card is the one large light parchment patch (found on a small copy of the screen), then only that
part is read (Windows' text reader). Only while you're in your hideout (Client.txt). GGG ToS: it looks and shows."""
import difflib
import re

# rumor as the card words it -> the island (its name in the Map library)
RUMOURS = [
    ("Fallen stars...", "Moor of Fallen Skies"),
    ("Crazed Chieftain...", "The Jade Isles"),
    ("Nothin' to drink...", "Stagnant Basin"),
    ("Cold as ice...", "Frigid Bluffs"),
    ("Stardrinker...", "Secluded Temple"),
    ("Sulphite!", "Scorched Cay"),
    ("Endless cliffs...", "Craggy Peninsula"),
    ("All that glitters...", "Castaway"),
    ("Almost paradise.", "Untainted Paradise"),
    ("Reflective waters...", "The Fractured Lake"),
    ("A good fellow...", "Moment of Zen"),
    ("It's dry at least...", "Sloughed Gully"),
    ("Wild roaming free...", "Lush Isle"),
    ("Origin of the fall...", "Obscure Island"),
    ("Unknown ruins...", "Exhumed Ruins"),
    ("Warm but risky...", "Grazed Prairie"),
    ("Somethin' fishy...", "Barren Atoll"),
    ("Bleak and awful...", "Bleached Shoals"),
    ("End of the circle...", "Sprawling Jungle"),
    ("The last to fall...", "Mournful Cliffside"),
]
MATCH = 0.72
LEAD = 0.12                    # 3.0.6: "Somethin' fishy..." read as "Somedtviw' Osho..." scored 0.77, the next rumor
#                                0.62 - just under the old 0.15 lead; other lines stay under 0.56 (see SHAPE)
WHOLE_MATCH = 0.8              # 2.113.1: in the card's whole text (stricter - more to match against)
SCALE = 8                       # the screen is searched at 1/8 size
MIN_AREA = 0.02                 # the card's parchment, as a share of (game height)^2


def squash(text):
    """Lower case, letters only (the card's handwriting reads as "Endless clif fs..." - spaces can't be trusted)."""
    return re.sub(r"[^a-z]", "", str(text or "").lower())


# 2.113.2 (rumours_read.txt: "Nothin' to drink..." read as "Wodviw' to c(riwkv.."): Windows' reader swaps letters
# that look alike in the card's handwriting - n / w / u / v / h / m, t / d / c / l, o / a. Compared by shape too:
# rumors score 0.88+ that way, the card's other lines 0.56 or less, two rumors never above 0.64.
SHAPE = str.maketrans({**{c: "n" for c in "nwuvhm"}, **{c: "t" for c in "tdcl"}, **{c: "i" for c in "ij"},
                       **{c: "o" for c in "oaq"}})


def shape(text):
    return squash(text).translate(SHAPE)


_KEYS = [(squash(r), r, i) for r, i in RUMOURS]
_SHAPES = {i: shape(r) for r, i in RUMOURS}


def _score(s, k):
    """How well line s holds rumor k: the whole line, or (2.113.0) its best stretch of about k's length - a rumor
    read on one line with the "Island Rumors" heading above it ("islandrumourswarmbutrisky") didn't match."""
    best = difflib.SequenceMatcher(None, s, k).ratio()
    if len(s) > len(k) + 3:
        for n in (len(k) - 2, len(k), len(k) + 2):
            if n < 4:
                continue
            for a in range(0, len(s) - n + 1):
                sc = difflib.SequenceMatcher(None, s[a:a + n], k).ratio()
                if sc > best:
                    best = sc
    return best


def match(line):
    """An OCR'd line -> (rumor, island) or None: by its letters, or (2.113.2) by their shapes - the best of the two,
    with a clear lead over the next rumor."""
    s, sh = squash(line), shape(line)
    if len(s) < 4:
        return None
    scores = []
    for k, r, i in _KEYS:
        scores.append((max(_score(s, k), _score(sh, _SHAPES[i])), r, i))
    scores.sort(reverse=True)
    best = scores[0]
    lead = best[0] - (scores[1][0] if len(scores) > 1 else 0.0)
    return (best[1], best[2]) if best[0] >= MATCH and lead >= LEAD else None


# 2.123.5 (feedback: the panel showed in a hideout with a lit tan floor - the floor passed the parchment color test and
# its misread scraps loosely matched a rumor): rumors count only when the card's own fixed words are read too - its
# heading, the logbook line or the Requires line (each fuzzy: the handwriting misreads, "ISLAND RUMOUÅSü&")
ANCHORS = ("islandrumours", "islandrumors", "usealogbooktocharttheare", "expeditionlogbook", "unchartedwaters")
ANCHOR_MATCH = 0.8


def is_card(lines):
    """OCR lines -> True when they're the Uncharted Waters card: one of its fixed lines is there."""
    full = "".join(squash(t) for t, _b in lines)
    for k in ANCHORS:
        n = len(k)
        if k in full:
            return True
        for a in range(0, max(1, len(full) - n + 1)):
            if difflib.SequenceMatcher(None, full[a:a + n], k).ratio() >= ANCHOR_MATCH:
                return True
    return False


def find_card(img, game_h):
    """A picture of the game window -> the card's box (x0, y0, x1, y1) in its pixels, or None: the largest connected
    patch of the card's light parchment, when it's big enough."""
    import numpy as np
    w, h = img.size
    sw, sh = max(1, w // SCALE), max(1, h // SCALE)
    a = np.asarray(img.convert("RGB").resize((sw, sh), 4)).astype(np.int16)        # 4 = BOX: fast
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = ((r > 140) & (g > 130) & (b > 105) & (r - b >= 5) & (r - b <= 50) & (r - g <= 20)).ravel()
    seen = np.zeros(sw * sh, dtype=bool)
    best = (0, None)
    for start in np.flatnonzero(m):
        if seen[start]:
            continue
        seen[start] = True
        stack, n = [int(start)], 0
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        while stack:
            i = stack.pop()
            n += 1
            y, x = divmod(i, sw)
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for j in ((i - 1) if x > 0 else -1, (i + 1) if x < sw - 1 else -1, i - sw, i + sw):
                if 0 <= j < sw * sh and m[j] and not seen[j]:
                    seen[j] = True
                    stack.append(j)
        if n > best[0]:
            best = (n, (x0, y0, x1, y1))
    n, box = best
    if box is None or n * SCALE * SCALE / max(1, game_h * game_h) < MIN_AREA:
        return None
    x0, y0, x1, y1 = box
    return (x0 * SCALE, y0 * SCALE, (x1 + 1) * SCALE, (y1 + 1) * SCALE)


BANNER_SHARE = 0.15            # 3.0.6: a row of the card that is the "Island Rumours" banner's blue-gray (its share)


def card_lines(img, card):
    """3.0.6 (reader.py): the card's box (find_card) -> (the "Use a logbook" strip's box, the banner's box, the 3
    rumor rows' boxes), in the picture's pixels. The rows are fixed: the parchment below the banner, in three. The
    banner is found by its blue-gray (measured on two cards: rows 0.43-0.60 of it, the parchment none); not found,
    it is where it sits on those cards (0.2-0.35 of the card's height)."""
    import numpy as np
    x0, y0, x1, y1 = card
    h, w = y1 - y0, x1 - x0
    a = np.asarray(img.convert("RGB").crop(card)).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    teal = ((b - r > 8) & (g > 120)).mean(axis=1) if a.size else np.zeros(0)
    ys = np.flatnonzero(teal > BANNER_SHARE)
    ys = ys[ys < h * 0.6]
    if len(ys) >= max(3, h * 0.05):
        top, bottom = y0 + int(ys[0]) - 4, y0 + int(ys[-1]) + 4
    else:
        top, bottom = y0 + int(0.2 * h), y0 + int(0.35 * h)
    xa, xb = x0 + int(0.05 * w), x1 - int(0.05 * w)
    end = min(img.height, y1 + int(0.03 * h))
    rows = _ink_rows(img, (xa, bottom, xb, end), (bottom - top) or int(0.15 * h))
    if not rows:                                  # (no ink found: the parchment below the banner, in three)
        step = (end - bottom) / 3.0
        rows = [(xa, int(bottom + i * step), xb, int(bottom + (i + 1) * step)) for i in range(3)]
    return (xa, y0, xb, max(y0 + 4, top)), (xa, top, xb, bottom), rows


def _ink_rows(img, box, banner_h):
    """The parchment below the banner -> a box per handwritten line in it (1 to 3), top to bottom: the bands of rows
    holding dark ink (a card with fewer rumors is shorter - the rows are found, not counted). Each band is padded to
    about a row's height (the banner's height x 1.4)."""
    import numpy as np
    x0, y0, x1, y1 = box
    if y1 - y0 < 8 or x1 - x0 < 20:
        return []
    g = np.asarray(img.convert("L").crop(box)).astype(np.float32)
    med = float(np.median(g))
    ink = g < med * 0.55
    ink[:, ink.mean(axis=0) > 0.7] = False         # (a dark edge)
    share = ink.mean(axis=1)
    share[share > 0.6] = 0                         # (the dark lines between the rows)
    on = np.flatnonzero(share >= 0.03)
    bands, gap = [], max(2, int(banner_h * 0.25))
    for y in on:
        if bands and y - bands[-1][1] <= gap:
            bands[-1][1] = int(y)
        else:
            bands.append([int(y), int(y)])
    bands = [b for b in bands if b[1] - b[0] >= banner_h * 0.25]
    bands = sorted(sorted(bands, key=lambda b: -float(share[b[0]:b[1] + 1].sum()))[:3])
    out = []
    row_h = banner_h * 1.4
    for a, b in bands:
        mid = y0 + (a + b) / 2.0
        half = max((b - a) / 2.0 + banner_h * 0.2, row_h / 2.0)
        out.append((x0, int(max(y0 - banner_h * 0.1, mid - half)), x1, int(min(img.height, mid + half))))
    return out


def read_card(img, card, ocr=None):
    """3.0.6 (reader.py): the card's rows read one by one -> (is the card, [(rumor, island, box)] top to bottom).
    The "Use a logbook" strip (then the banner) says it is the card; each row is matched by its picture (rows matched
    for sure before) or its text - never a guess between two rumors."""
    from . import reader as R
    anchor, banner, rows = card_lines(img, card)
    card_ok = False
    for box, kind in ((anchor, "rumor-anchor"), (banner, "rumor-anchor")):
        t, _b, _how = R.read_one(img, box, kind=kind, want=lambda s: is_card([(s, None)]), ocr=ocr)
        if is_card([(t, None)]):
            card_ok = True
            break
    out, seen = [], set()
    for box in rows:
        hit = R.read_closed(img, box, _VOCAB, kind="rumor-row", match=_closed, ocr=ocr, learn=card_ok,
                            among=None)
        if hit and hit.entry[1] not in seen:
            seen.add(hit.entry[1])
            out.append((hit.entry[0], hit.entry[1], box))
    return card_ok, out


def merge_rows(first, more):
    """The rows read one by one (first) and those of the whole card's read (more) -> one list, top to bottom: a row
    of `more` counts only for an island not found yet and a place on the card no row of `first` holds."""
    out = list(first)
    for r, i, b in more:
        mid = (b[1] + b[3]) / 2.0
        if any(i == o[1] for o in out) or any(o[2][1] <= mid <= o[2][3] for o in first):
            continue
        out.append((r, i, b))
    out.sort(key=lambda x: (x[2][1], x[2][0]))
    return out


_VOCAB = {r: (r, i) for r, i in RUMOURS}


def _closed(text):
    """A row's text -> reader.Hit of (rumor, island), sure (MATCH, LEAD - the same rule as match()), or None."""
    from . import reader as R
    hit = R.match_closed(text, _VOCAB, min_score=MATCH, min_lead=LEAD, parts=False, detail=True)
    if hit is None:
        p = part_match(text)
        if p and not any(a in squash(text) for a in ("rumour", "rumor", "logbook", "requires", "chart")):
            return R.Hit(p, 0.0, 0.0, "part")
    return hit


PART_MIN = 5                   # 3.0.6: a line the reader cut short ("least..." for "It's dry at least...")


def part_match(line, taken=()):
    """A cut-short line -> (rumor, island) when its letters (PART_MIN or more, or by shape) are the start or the end
    of exactly one rumor not found yet - never a guess between two."""
    s, sh = squash(line), shape(line)
    if len(s) < PART_MIN:
        return None
    hits = [(r, i) for k, r, i in _KEYS if i not in taken and
            (k.endswith(s) or k.startswith(s) or _SHAPES[i].endswith(sh) or _SHAPES[i].startswith(sh))]
    return hits[0] if len(hits) == 1 else None


def rows(lines):
    """OCR lines of the card -> [(rumor, island, line box)] for the lines that are rumors (the header and the
    Requires line aren't). 2.113.1 (feedback: the middle one of three was missed): a rumor no single line matches is
    looked for in the card's whole text (Windows' reader can split a rumor over two lines or join it to the next),
    a little stricter there; its box is the line it starts on."""
    out, seen = [], set()
    for text, box in lines:
        hit = match(text)
        if hit and hit[1] not in seen:
            seen.add(hit[1])
            out.append((hit[0], hit[1], box))
    if len(out) < 3:
        for text, box in lines:                             # (3.0.6: a line read only in part)
            hit = None if match(text) else part_match(text, seen)
            if hit and not any(a in squash(text) for a in ("rumour", "rumor", "logbook", "requires", "chart")):
                seen.add(hit[1])
                out.append((hit[0], hit[1], box))
        out.sort(key=lambda x: (x[2][1], x[2][0]))
    if len(out) < 3 and lines:
        parts = [(shape(t), b) for t, b in lines]           # (2.113.2: by shape - see SHAPE)
        full = "".join(p for p, _b in parts)
        starts, pos = [], 0
        for p, b in parts:
            starts.append((pos, b))
            pos += len(p)
        for _k, r, i in _KEYS:
            k = _SHAPES[i]
            if i in seen or len(k) < 6:
                continue
            best, at = 0.0, 0
            n = len(k)
            for a in range(0, max(1, len(full) - n + 1)):
                sc = difflib.SequenceMatcher(None, full[a:a + n], k).ratio()
                if sc > best:
                    best, at = sc, a
            if best >= WHOLE_MATCH:
                box = next((b for s, b in reversed(starts) if s <= at), lines[0][1])
                seen.add(i)
                out.append((r, i, box))
        out.sort(key=lambda x: (x[2][1], x[2][0]))
    return out
