"""3.0.6: the one reader every helper that reads text from the game's picture calls - better reads in one place help
every helper at once, and a misread never seen before is still handled.

  read_lines(picture, box, lines=..., kind=...)  the text in a part of the picture. When the caller knows where each
      line is (a card with fixed rows, a panel's title, the crystal counter), each line is cut out, enlarged and made
      clean on its own, and read as one line; otherwise the whole box is read once. Each kind of text has its own
      ways to make it clean (KINDS: measured on real game pictures), tried in order until the caller's want() says
      the text is right.
  match_closed(text, vocabulary)  the one entry of a closed list (rumors, medallions, rooms ...) a line holds: by its
      letters and by the shapes of its letters (the OCR swaps n / w / u / v, t / d / l ...), or by its start or end
      when the line was cut short. Never a guess between two: the best must lead the next by min_lead.
  Memory(kind)  once a line was matched for sure, a small picture of it (a gray thumbnail of the text, no colors)
      is kept in the data folder (reader/<kind>.json, capped); the next time that line is known by its picture first,
      then by its text. An unsure match never teaches it.

GGG policy: it only reads the picture the Read Key press already took (screenread.py) - it never takes one, and runs
no timers. Only game text is read here; nothing is logged."""
import base64
import difflib
import json
import os
import re
import sys
import threading
from collections import namedtuple

from . import buglog

# ================================================================ making a line clean
# kind -> the ways to read it, in order: (prep, scale, layout). layout "line": read as one line; "block": a few lines.
# Measured with Tesseract 5.3 on the owner's 2560x1440 pictures, and those made 0.75 the size (1080p):
#   rumor-row      the card's 3 handwritten rows: gray 2x read 6/6 (3x 6/6; dark-text 2x 6/6); whole card 5/6
#   rumor-anchor   the card's "Use a logbook ..." strip: 2/2 at 2x and 3x (the whole card read: 0/2)
#   console        "36/60": white-text 2x 19/20 at both sizes, bright 3x (block) 20/20 at 1440p; whole read 13/20
#                  (none of the 7 counts)
#   medallion-title  "Medallions (5/6)": 89/90 right, 0 wrong at every prep, 2x and 3x, both sizes; whole panel
#                  read 69 right, 8 wrong (5/6 and 3/6 read as 1/6), 13 missed
#   card-name      a Room Cards row's gold name (see vaallens.card_rows_read)
#   tooltip-title  a medallion tooltip's title bar
KINDS = {
    "rumor-row": (("gray", 2, "line"), ("dark-text", 2, "line"), ("gray", 3, "line")),
    "rumor-anchor": (("gray", 2, "line"), ("dark-text", 2, "line")),
    "console": (("white-text", 2, "line"), ("bright", 3, "block"), ("otsu", 3, "block")),
    "medallion-title": (("gray", 2, "line"), ("white-text", 2, "line")),
    "card-name": (("gold-text", 3, "line"), ("gray", 2, "line"), ("bright", 3, "line")),
    "tooltip-title": (("gray", 2, "line"), ("bright", 2, "line")),
    "book-line": (("gray", 2, "line"), ("dark-text", 3, "line")),
}
DEFAULT = (("gray", 2, "line"),)
# kind -> the line's least height once enlarged (its height at 1440p times the scale measured best): a smaller game
# window's line is enlarged more, to the same size
MIN_H = {"console": 100, "rumor-row": 100, "rumor-anchor": 90, "medallion-title": 90}
MAX_SIDE = 2600                  # a prepared picture is never bigger than this (Windows' reader's own limit)


def prep(img, how="gray", scale=2):
    """A PIL picture -> the same, ready to read: dark text on white, `scale` times the size.
      gray        gray, light text turned dark, the contrast stretched (the default: game text on any plain backing)
      white-text  only near-white text kept (a counter or a title over a busy backing)
      bright      light text of any color (gold, blue, white) on dark
      gold-text   the game's gold names alone (white numbers drawn over them are dropped)
      dark-text   dark ink on light parchment (the parchment's grain dropped)
      otsu        black and white at the picture's own split
    "+sharp" after a name sharpens it after enlarging."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps, ImageStat
    base, _, extra = str(how or "gray").partition("+")
    w, h = img.size
    scale = max(0.5, min(float(scale or 1), MAX_SIDE / float(max(1, w, h))))
    size = (max(1, int(w * scale)), max(1, int(h * scale)))
    if base in ("white-text", "bright", "gold-text"):
        a = np.asarray(img.convert("RGB")).astype(np.int16)
        if base == "white-text":
            g = Image.fromarray(np.clip(255 - (a.min(axis=-1) - 60) * 2, 0, 255).astype("uint8"))
        elif base == "gold-text":
            gold = (a[..., 0] - a[..., 2] > 45) & (a[..., 0] > 110)
            g = Image.fromarray(np.where(gold, 0, 255).astype("uint8"))
        else:
            g = ImageOps.autocontrast(ImageOps.invert(Image.fromarray(a.max(axis=-1).astype("uint8"))), cutoff=1)
        g = g.resize(size, Image.LANCZOS)
    else:
        g = img.convert("L").resize(size, Image.LANCZOS)
        if base == "dark-text":
            a = np.asarray(g).astype(np.float32)
            g = Image.fromarray(np.where(a < float(np.median(a)) * 0.6, 0, 255).astype("uint8"))
        elif base == "otsu":
            a = np.asarray(g)
            hist = np.bincount(a.ravel(), minlength=256).astype(np.float64)
            cut = _otsu(hist)
            t = np.where(a > cut, 255, 0).astype("uint8")
            if t.mean() < 128:
                t = 255 - t
            g = Image.fromarray(t)
        else:
            if ImageStat.Stat(g).mean[0] < 128:
                g = ImageOps.invert(g)
            g = ImageOps.autocontrast(g, cutoff=1)
    if extra == "sharp":
        g = g.filter(ImageFilter.UnsharpMask(2, 150, 3))
    return g, scale


def _otsu(hist):
    total = hist.sum()
    if total <= 0:
        return 127
    import numpy as np
    w = np.cumsum(hist)
    m = np.cumsum(hist * np.arange(256))
    mt = m[-1]
    w1 = total - w
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mt * w - m * total) ** 2 / (w * w1)
    between[~np.isfinite(between)] = 0
    return int(between.argmax())


# ================================================================ the OCR engine
def _engine(img, layout):
    """A prepared picture -> [(text, box)] in its pixels: Tesseract (one line / a block, read as it is) on Linux,
    Windows' own reader on Windows (it has no layout setting)."""
    from . import remnant as RM
    if sys.platform == "win32":
        return RM.ocr(img)
    from . import ocrengine
    why = ocrengine.problem()
    if why:
        raise RM.OcrUnavailable(why)
    if not RM._OCR_LOCK.acquire(timeout=RM.WAIT_SECS):
        raise RM.OcrStuck("busy")
    try:
        return ocrengine.tesseract(img, timeout=RM.READ_SECS, psm="7" if layout == "line" else "6", prepped=True)
    except ocrengine.Slow:
        raise RM.OcrStuck("slow")
    except OSError:
        return []
    finally:
        RM._OCR_LOCK.release()


def _reader(ocr):
    """The caller's OCR (tests: a stand-in fn(picture) -> lines) or the engine; remnant.ocr means the engine."""
    if ocr is None:
        return _engine
    try:
        from . import remnant as RM
        if ocr is RM.ocr:
            return _engine
    except Exception:
        buglog.caught()
    return lambda img, _layout: ocr(img)


def _clip(box, size):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    w, h = size
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def read_one(picture, box, *, kind=None, ways=None, want=None, ocr=None):
    """One line of the picture, read on its own -> (text, box of the text in the picture's pixels, how it was made
    ready). Each of the kind's ways is tried in order until want(text) is true (no want: the first text read); none
    is: the first text read. ("", line box, None) when nothing was read."""
    run = _reader(ocr)
    cut_box = _clip(box, picture.size)
    if cut_box[2] - cut_box[0] < 2 or cut_box[3] - cut_box[1] < 2:
        return "", tuple(box), None
    cut = picture.crop(cut_box)
    first = None
    least = MIN_H.get(kind, 0) / float(max(1, cut.height))
    for how, scale, layout in ways or KINDS.get(kind, DEFAULT):
        pic, k = prep(cut, how, max(scale, min(scale * 2, least)))
        got = [(t, b) for t, b in (run(pic, layout) or []) if str(t).strip()]
        if not got:
            continue
        text = " ".join(" ".join(str(t).split()) for t, _b in got)
        bs = [b for _t, b in got if b]
        tb = cut_box
        if bs:
            tb = (cut_box[0] + int(min(b[0] for b in bs) / k), cut_box[1] + int(min(b[1] for b in bs) / k),
                  cut_box[0] + int(max(b[2] for b in bs) / k), cut_box[1] + int(max(b[3] for b in bs) / k))
        res = (text, tb, how)
        if first is None:
            first = res
        if want is None or want(text):
            return res
    return first or ("", cut_box, None)


def read_lines(picture, box=None, *, lines=None, kind=None, ways=None, want=None, ocr=None):
    """Text in a part of the picture -> [(text, (x0, y0, x1, y1) in the picture's pixels)].
    lines (boxes in the picture's pixels): each is read on its own (read_one) - one entry per line, in their order,
    "" when nothing was read there. No lines: the whole box (default: the picture) is read once, made ready the
    kind's first way."""
    if lines is not None:
        return [read_one(picture, b, kind=kind, ways=ways, want=want, ocr=ocr)[:2] for b in lines]
    run = _reader(ocr)
    cut_box = _clip(box or (0, 0, picture.width, picture.height), picture.size)
    if cut_box[2] - cut_box[0] < 2 or cut_box[3] - cut_box[1] < 2:
        return []
    how, scale, _layout = (ways or KINDS.get(kind, DEFAULT))[0]
    pic, k = prep(picture.crop(cut_box), how, scale)
    out = []
    for t, b in run(pic, "block") or []:
        if not str(t).strip():
            continue
        out.append((t, (cut_box[0] + int(b[0] / k), cut_box[1] + int(b[1] / k), cut_box[0] + int(b[2] / k),
                        cut_box[1] + int(b[3] / k)) if b else cut_box))
    return out


# ================================================================ matching a closed list
# letters that look alike in the game's fonts (and in the rumors' handwriting): n / w / u / v / h / m, t / d / c / l,
# i / j, o / a / q (rumours.py measured them); digits OCR reads for letters first become those letters
SHAPE = str.maketrans({**{c: "n" for c in "nwuvhm"}, **{c: "t" for c in "tdcl"}, **{c: "i" for c in "ij"},
                       **{c: "o" for c in "oaq"}})
_DIGITS = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b", "|": "l"})
PART_MIN = 5
Hit = namedtuple("Hit", "entry score lead how key", defaults=(None,))
#   how: "text" | "part" | "picture"; key: the list's text it matched (what Memory keeps)


def squash(text):
    """Lower case, letters only (spaces and marks can't be trusted)."""
    return re.sub(r"[^a-z]", "", str(text or "").lower().translate(_DIGITS))


def shape(text):
    return squash(text).translate(SHAPE)


def _score(s, k):
    """How well line s holds key k: the whole line, or its best stretch about k's long (stray letters around it)."""
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


_VOCAB = {}


def _keys(vocabulary):
    """vocabulary (a list of entries, or {text to match: entry}) -> [(letters, shapes, entry)] (kept)."""
    sig = id(vocabulary), len(vocabulary)
    got = _VOCAB.get(sig)
    if got is not None and got[0] is vocabulary:
        return got[1]
    items = vocabulary.items() if isinstance(vocabulary, dict) else ((v, v) for v in vocabulary)
    keys = [(squash(k), shape(k), e, k) for k, e in items if squash(k)]
    if len(_VOCAB) > 64:
        _VOCAB.clear()
    _VOCAB[sig] = (vocabulary, keys)
    return keys


def match_closed(text, vocabulary, *, shapes=True, min_score=0.8, min_lead=0.1, parts=True, taken=(), detail=False):
    """An OCR'd line -> the entry of the closed list it holds, or None.
    By letters, and (shapes) by the shapes of its letters - the best of the two; the best entry must score min_score
    and lead the next one by min_lead. Else (parts) a cut-short line: its letters (PART_MIN or more) are the start or
    the end of exactly one entry not in `taken`. detail: a Hit(entry, score, lead, how) instead of the entry."""
    s = squash(text)
    if len(s) < 4:
        return None
    sh = shape(text) if shapes else None
    keys = _keys(vocabulary)
    scores = {}
    for k, ks, e, name in keys:
        sc = _score(s, k)
        if shapes:
            sc = max(sc, _score(sh, ks))
        if sc > scores.get(id(e), (0.0,))[0]:
            scores[id(e)] = (sc, e, name)
    ranked = sorted(scores.values(), key=lambda t: -t[0])
    if ranked:
        best = ranked[0]
        lead = best[0] - (ranked[1][0] if len(ranked) > 1 else 0.0)
        if best[0] >= min_score and lead >= min_lead:
            return Hit(best[1], best[0], lead, "text", best[2]) if detail else best[1]
    if parts and len(s) >= PART_MIN:
        hits = []
        for k, ks, e, name in keys:
            if e in taken or any(e is h[0] for h in hits):
                continue
            if k.startswith(s) or k.endswith(s) or (shapes and (ks.startswith(sh) or ks.endswith(sh))):
                hits.append((e, name))
        if len(hits) == 1:
            return Hit(hits[0][0], 0.0, 0.0, "part", hits[0][1]) if detail else hits[0][0]
    return None


# ================================================================ picture memory
FP_SIZE = (48, 10)               # a line's text, shrunk to this (gray)
RECALL = 0.86                    # measured on the card's rows: the same rumor 0.93-0.97 (0.73 once, at 0.75 size),
RECALL_LEAD = 0.15               # two different rumors 0.44 at most
PER_ENTRY = 6
PER_KIND = 300
_MEM_LOCK = threading.Lock()


def _runs(idx, gap):
    out = []
    if not len(idx):
        return out
    s = p = int(idx[0])
    for x in idx[1:]:
        x = int(x)
        if x - p > gap:
            out.append((s, p))
            s = x
        p = x
    out.append((s, p))
    return out


def ink_box(crop):
    """A line's crop -> the box of its text (x0, y0, x1, y1) in the crop, or None: the rows and columns with ink,
    without the frame lines and dark edges around it."""
    import numpy as np
    from PIL import ImageOps
    g = np.asarray(ImageOps.autocontrast(crop.convert("L"), cutoff=1)).astype(np.float32)
    if float(np.median(g)) < 128:
        g = 255 - g
    ink = g < float(np.median(g)) * 0.55
    h, w = ink.shape
    if h < 3 or w < 6:
        return None
    ink[:, ink.mean(axis=0) > 0.7] = False         # (a dark edge)
    ink[ink.mean(axis=1) > 0.6] = False            # (a frame line)
    per_row = ink.sum(axis=1)
    rows = _runs(np.flatnonzero(per_row >= max(2, 0.08 * float(per_row.max()))), 2)
    if not rows:
        return None
    r0, r1 = max(rows, key=lambda r: ink[r[0]:r[1] + 1].sum())
    cols = _runs(np.flatnonzero(ink[r0:r1 + 1].sum(axis=0) >= 1), max(3, int(0.8 * (r1 - r0 + 1))))
    if not cols:
        return None
    c0, c1 = max(cols, key=lambda c: ink[r0:r1 + 1, c[0]:c[1] + 1].sum())
    if c1 - c0 < 6 or r1 - r0 < 3:
        return None
    return c0, r0, c1 + 1, r1 + 1


def fingerprint(crop):
    """A line's crop -> a unit vector of its text's picture (48 x 10 gray, z-scored), or None (no text found)."""
    import numpy as np
    from PIL import Image, ImageOps
    b = ink_box(crop)
    if b is None:
        return None
    g = ImageOps.autocontrast(crop.convert("L"), cutoff=1)
    a = np.asarray(g).astype(np.float32)
    if float(np.median(a)) < 128:
        a = 255 - a
    a = a[b[1]:b[3], b[0]:b[2]]
    v = np.asarray(Image.fromarray(a.astype("uint8")).resize(FP_SIZE, Image.BOX)).astype(np.float32).ravel()
    v = (v - v.mean()) / (v.std() + 1e-6)
    n = float(np.linalg.norm(v))
    return v / n if n else None


def _pack(v):
    import numpy as np
    return base64.b64encode(np.clip(v * 127 / max(1e-6, float(abs(v).max())) + 128, 0, 255).astype("uint8").tobytes()).decode()


def _unpack(s):
    import numpy as np
    v = np.frombuffer(base64.b64decode(s), np.uint8).astype(np.float32) - 128
    v = v - v.mean()
    n = float(np.linalg.norm(v))
    return v / n if n else v


class Memory:
    """Pictures of lines matched for sure, by kind: {entry: [fingerprints]} in reader/<kind>.json (data folder).
    Only game text is kept, as small gray pictures - nothing about you."""
    DIR = [None]                 # tests: a folder of their own

    def __init__(self, kind):
        self.kind = re.sub(r"[^a-z0-9-]", "", str(kind).lower()) or "lines"
        self._data = None

    def _path(self):
        d = Memory.DIR[0]
        if d is None:
            from .config import P
            d = P("reader")
        return os.path.join(d, self.kind + ".json")

    def _load(self):
        if self._data is None:
            try:
                with open(self._path(), encoding="utf-8") as f:
                    raw = json.load(f)
                self._data = {str(k): [_unpack(s) for s in v][-PER_ENTRY:] for k, v in dict(raw).items()}
            except (OSError, ValueError, TypeError):
                self._data = {}
        return self._data

    def _save(self):
        try:
            p = self._path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({k: [_pack(v) for v in vs] for k, vs in self._data.items()}, f)
            os.replace(tmp, p)
        except OSError:
            buglog.caught()

    def recall(self, crop, among=None):
        """A line's crop -> the entry whose kept pictures it matches (RECALL, leading every other entry by
        RECALL_LEAD), or None. among: only these entries count."""
        v = fingerprint(crop)
        if v is None:
            return None
        with _MEM_LOCK:
            data = self._load()
            best = {}
            for e, vs in data.items():
                if among is not None and e not in among:
                    continue
                best[e] = max((float(v @ u) for u in vs if u.shape == v.shape), default=-1.0)
        if not best:
            return None
        ranked = sorted(best.items(), key=lambda t: -t[1])
        top = ranked[0]
        lead = top[1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
        return top[0] if top[1] >= RECALL and lead >= RECALL_LEAD else None

    def teach(self, crop, entry, hit=None):
        """Keep the picture of a line matched for sure (entry: the list's text for it; hit: its Hit - a part match
        or an unsure one never teaches)."""
        if hit is not None and getattr(hit, "how", "text") != "text":
            return False
        v = fingerprint(crop)
        if v is None:
            return False
        entry = str(entry)
        with _MEM_LOCK:
            data = self._load()
            for e, vs in data.items():                 # (a picture that looks like another entry's: kept by neither)
                if e != entry and any(float(v @ u) >= RECALL for u in vs if u.shape == v.shape):
                    return False
            vs = data.setdefault(entry, [])
            if any(float(v @ u) >= 0.995 for u in vs if u.shape == v.shape):
                return True                            # (the same picture again)
            vs.append(v)
            del vs[:-PER_ENTRY]
            while sum(len(x) for x in data.values()) > PER_KIND:
                big = max(data, key=lambda k: len(data[k]))
                data[big].pop(0)
                if not data[big]:
                    del data[big]
            self._save()
        return True


_MEMS = {}


def memory(kind):
    m = _MEMS.get(kind)
    if m is None:
        m = _MEMS[kind] = Memory(kind)
    return m


def read_closed(picture, box, vocabulary, *, kind, match=None, ocr=None, learn=True, among=None):
    """One line of a closed list -> Hit(entry, score, lead, how) or None: by its picture first (Memory), then by its
    text (each of the kind's ways, until match(text) is sure). match: fn(text) -> Hit or None (default:
    match_closed(..., detail=True)). A sure text match teaches the line's picture."""
    if match is None:
        def match(t):
            return match_closed(t, vocabulary, detail=True)
    cut_box = _clip(box, picture.size)
    if cut_box[2] - cut_box[0] < 2 or cut_box[3] - cut_box[1] < 2:
        return None
    crop = picture.crop(cut_box)
    mem = memory(kind) if learn else None
    if mem is not None:
        try:
            e = mem.recall(crop, among)
        except Exception:
            buglog.caught()
            e = None
        if e is not None:
            entry = vocabulary.get(e) if isinstance(vocabulary, dict) else (e if e in vocabulary else None)
            if entry is not None:
                return Hit(entry, 1.0, 1.0, "picture", e)
    got = {}

    def want(t):
        h = match(t)
        if h:
            got["hit"] = h
        return bool(h)
    read_one(picture, cut_box, kind=kind, want=want, ocr=ocr)
    hit = got.get("hit")
    if hit and mem is not None and getattr(hit, "how", "text") == "text" and getattr(hit, "key", None):
        try:
            mem.teach(crop, hit.key, hit)
        except Exception:
            buglog.caught()
    return hit
