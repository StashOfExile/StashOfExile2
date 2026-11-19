"""2.132.0 Map profit (feedback: read the inventory for currency and omens with the same data as Scan stash on
Wealth, track the profit
per map with the same mechanism as Top Up Reminders; keep it local, never published or sent to the database; count
currency exchange items, not waystones; track per session, map, hour and day in a local log only the user sees).

How: Top Up's quick inventory read (the inventory panel only, never the stash side) is taken in your hideout or a
town, only when you press your Read Key there. Owner decision: back from a map, one card (topup_page.back_card) asks
for that press - it counts the map's loot and checks your top ups from the same read; skip it and that map has no
entry. The last clear read at home before a map is "before"; the first clear read after it is "after". What changed is that
map's loot. Each cell is named by its picture - the ones you taught with Ctrl+C (Top Up) or the ones Scan stash
learned - and only items with a Currency Exchange price (poe.ninja's exchange: currency, omens, runes, ...) count;
waystones and gear never do. Prices: Exchange Rates (poe.ninja, in divines).
3.0.6 (every item poe.ninja's exchange lists, nothing taught): after those, Scan stash's wildcard pictures, the
Currency Exchange's icons and last poe.ninja's own art (from the art cache; Map Profit's page downloads what's
missing once, like Exchange Rates does) - each only when sure. A cell with no stack number is still tried as a
lineage or uncut gem (an uncut gem by its white roman level); anything else without one is skipped.

Privacy: map_profit.jsonl in your data folder, on your PC only - never uploaded, shared or sent to the board."""
import re
import json
import os
import time

from . import buglog
from .config import SETTINGS, P

LOG_FILE = "map_profit.jsonl"
DEFAULTS = {"on": True}
KEEP_DAYS = 90                      # the log keeps this many days (older lines are dropped when it's tidied)
BEFORE_SECS = 3 * 3600              # a "before" older than this isn't this map's (you left the game in between)
ARRIVE_SECS = 8                     # 2.132.2: back home, what you came back with = the most seen in this long
DONE_SECS = 15 * 60                 # 2.132.1: out of a map this long (not back through its portal): it's done


def cfg():
    c = SETTINGS.setdefault("map_profit", {})
    for k, v in DEFAULTS.items():
        c.setdefault(k, v)
    return c


# ---------------------------------------------------------------- naming what the inventory holds
GEM_TYPES = ("LineageSupportGems", "UncutGems")
GEM_MIN, GEM_BY = 0.75, 0.10        # 3.0.6: a cell with no stack number (a lineage or uncut gem - or gear): the gem
#                                     this sure and this far ahead of the next gem (Uhtred's Constellation 0.78 by
#                                     0.11 on the owner's inventory; gear and other gems' cells under 0.63)
STASH_MIN, STASH_BY = 0.80, 0.10    # 3.0.6: Scan stash's wildcard pictures (stashread: 0.75 / 0.05 among one tab's
#                                     slots) - stricter here, with every exchange item to choose from
EXCH_TINT_MAX = 25.0                # 3.0.6: an exchange icon's tint this far from the cell's: not that item (with
#                                     nothing learned, on the owner's inventory: right items 6.8-20.7, a white
#                                     Perfect Essence named the red one 32.5, an Omen named another 54.5)
LEVEL = re.compile(r"^(.*) \(Level (\d+)\)$")


def gem_names(parts):
    """poe.ninja's exchange answers -> the names of its gems (lineage support gems, uncut gems) - the names every
    type lists (Divine, Exalted, Chaos Orb) left out."""
    gems, other = set(), set()
    for typ, p in (parts or {}).items():
        names = set(((p or {}).get("names") or {}).values())
        (gems if typ in GEM_TYPES else other).update(names)
    return gems - other


LOOSE_TYPES = ("Fragments",)
LOOSE_NAMES = ("Expedition Logbook",)
LOOSE_MIN = 0.72                    # 3.0.6: fragments that don't stack show no number (crisis fragments 0.74-0.77, the
#                                     next item 0.63 or less on the owner's inventory; gear corners under 0.65)


def loose_names(parts):
    """3.0.6: exchange items that may show no stack number - fragments (Crisis Fragments), Expedition Logbooks."""
    out = set(LOOSE_NAMES)
    for typ, p in (parts or {}).items():
        if typ in LOOSE_TYPES:
            out.update(((p or {}).get("names") or {}).values())
    return out


def build_refs(parts):
    """3.0.6: the pictures Map Profit names cells with, best trusted first: learned and shipped pictures (Scan
    stash's slots among them), Scan stash's wildcard pictures (refs.stash), the Currency Exchange's icons, and last
    poe.ninja's art from the art cache (refs.art). Nothing is downloaded here."""
    from . import favours as FV
    items = FV.ninja_items(parts)
    refs = FV.build_refs(items, exchange=True)
    known = {n for n, _p in items.values()}
    refs.gems = gem_names(parts)
    refs.loose = loose_names(parts)
    try:
        from . import stashread as SR
        refs.stash = {n: ic for n, ic in SR.learned_icons().items() if n in known}
    except Exception:
        buglog.caught()
    try:
        refs.art = FV.art_refs(items)
    except Exception:
        buglog.caught()
    return refs


def _base(name):
    m = LEVEL.match(str(name))
    return m.group(1) if m else name


def _collapsed(got):
    """refs.ranked(..., refs=True) -> the same, an item's levels as one ("Uncut Support Gem (Level 3)" and
    "(Level 4)" are one picture): [(score, base name, kind, cell feats, picture feats)], best first."""
    out, seen = [], set()
    for sc, name, src, cf, rf in got:
        b = _base(name)
        if b not in seen:
            seen.add(b)
            out.append((sc, b, src, cf, rf))
    return out


def _other_close(refs, f, names, top=None):
    """3.0.6: a learned or shipped picture of another item scores close (MAYBE_MIN, or within MATCH_BY of the
    top), or another item's exchange icon is sure (MATCH_SURE) - then a fallback names nothing."""
    from . import favours as FV
    bases = {_base(n) for n in names}
    for sc, name, src in refs.ranked(f, 8):
        if name in names or _base(name) in bases:
            continue
        if src in ("learned", "shipped", "icon") and sc >= min(FV.MAYBE_MIN, (top if top is not None else 1.0)
                                                              - FV.MATCH_BY):
            return True
        if src == "exchange" and sc >= FV.MATCH_SURE:
            return True
    return False


def _by_level(base, names, bgr):
    """One picture, many levels (uncut gems, Thaumaturgic Flux): the white roman level at the cell's bottom right
    picks one ("V" -> "Uncut Support Gem (Level 5)") - None when it isn't read or isn't one of them."""
    lv = roman(tier_letters(bgr, white=True))
    want = f"{base} (Level {lv})" if lv else None
    return want if want in names else None


def _resolve(key, names, bgr):
    """An entry (one picture) -> the item's name: itself, its level, or (grades) the plain orb - grade() moves it
    to Greater / Perfect by its II / III. None when the level isn't read."""
    names = list(names or [key])
    if len(names) == 1:
        return names[0]
    if all(LEVEL.match(n) for n in names):
        return _by_level(key, names, bgr)
    return key if key in names else None


def stash_match(bgr, f, refs, veto=True):
    """3.0.6 (owner: reuse what Scan stash knows): a cell (BGR, a whole cell) -> the item one of Scan stash's
    wildcard pictures (stashread.learned_icons: shipped ones and the ones you named) says it is, or None. Its own
    picture match (the cell's lower part slid over the slot's), STASH_MIN and STASH_BY ahead; never when another
    item's learned or shipped picture is close (veto=False: what the picture alone says)."""
    icons = getattr(refs, "stash", None) or {}
    if not icons:
        return None
    import cv2
    from . import stashread as SR
    cell = cv2.resize(bgr, (70, 70), interpolation=cv2.INTER_AREA)
    ic = SR._icon(cell, (0, 0, 70, 70))
    if ic is None:
        return None
    got = sorted(((float(cv2.matchTemplate(ic, v[3:-3, 4:-4], cv2.TM_CCOEFF_NORMED).max()), n)
                  for n, v in icons.items() if v is not None), reverse=True)
    if not got:
        return None
    top, name = got[0]
    nxt = got[1][0] if len(got) > 1 else 0.0
    if top < STASH_MIN or top - nxt < STASH_BY or (veto and _other_close(refs, f, {name})):
        return None
    return name


def art_disagrees(f, refs, name):
    """3.0.6 (on the owner's inventory with nothing learned, an Omen of Putrefaction was named Omen of Light by
    its exchange icon - 0.68, alone ahead): poe.ninja's art of the item an exchange icon named scores ART_BY or
    more under another item's art -> True (not known). The right items' own art was the top every time; the wrong
    one 0.26 under. No art cached for it: False."""
    from . import favours as FV
    art = getattr(refs, "art", None)
    if art is None or not art.items:
        return False
    got = art.ranked(f, len(art.items))
    own = [sc for sc, key, _s in got if name in art.groups.get(key, [key]) or key == name]
    if not got or not own:
        return False
    return got[0][0] - own[0] >= FV.ART_BY


def art_match(bgr, f, refs, only=None):
    """3.0.6 (owner: every item poe.ninja's exchange lists, nothing taught): the last fallback - poe.ninja's art
    from the art cache (refs.art), compared like the exchange icons (cropped to the art). Only when it's sure
    (ART_MIN), far ahead of the next picture (ART_BY), its colors aren't beaten (hue_veto) and no learned or
    shipped picture of another item is close. only: the names it may give (the gems, for a cell with no stack
    number). -> name or None."""
    from . import favours as FV
    art = getattr(refs, "art", None)
    if art is None or not art.items:
        return None
    if only is not None:
        view = FV.Refs()
        view.items = {k: v for k, v in art.items.items() if any(n in only for n in art.groups.get(k, [k]))}
    else:
        view = art
    got = view.ranked(f, 2)
    if not got or got[0][0] < FV.ART_MIN:
        return None
    top, key = got[0][0], got[0][1]
    nxt = got[1][0] if len(got) > 1 else -1.0
    if top - nxt < FV.ART_BY or view.hue_veto(f, top):
        return None
    names = art.groups.get(key, [key])
    if _other_close(refs, f, set(names), top):
        return None
    return _resolve(key, names, bgr)


def unlettered(bgr):
    """A cell (BGR) with its white level letters (bottom right) painted over from around them - the gem's
    pictures have none, and the letters change what the art looks like."""
    import cv2
    import numpy as np
    h, w = bgr.shape[:2]
    b, g, r = (bgr[..., i].astype(int) for i in range(3))
    lo = np.minimum(np.minimum(r, g), b)
    m = ((lo > 165) & (np.maximum(np.maximum(r, g), b) - lo < 50)).astype(np.uint8)
    m[:int(h * 0.55)] = 0
    m[:, :int(w * 0.6)] = 0
    if not m.any():
        return bgr
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    return cv2.inpaint(np.ascontiguousarray(bgr), m * 255, 3, cv2.INPAINT_TELEA)


def gem_match(cell, refs, pool=None, least=None):
    """3.0.6 (a lineage support gem was missed): a cell with no stack number (PIL) -> the lineage or uncut gem it
    is, or None (gear, a jewel, an item poe.ninja doesn't list). Only gems' pictures compete: GEM_MIN and GEM_BY
    ahead of the next gem, the colors not beaten, no other item's learned or shipped picture close; an uncut gem by
    its level (the white roman number). Then poe.ninja's art (art_match), gems only."""
    gems = pool if pool is not None else (getattr(refs, "gems", None) or set())
    least = GEM_MIN if least is None else least
    if not gems or cell is None or not hasattr(cell, "convert"):
        return None
    try:
        import numpy as np
        from . import favours as FV
        bgr = np.asarray(cell.convert("RGB"))[:, :, ::-1].copy()
        f = {"box": _box_feats(unlettered(bgr) if roman(tier_letters(bgr, white=True)) else bgr)}
        view = FV.Refs()
        view.items = {n: v for n, v in refs.items.items() if n in gems}
        got = _collapsed(view.ranked(f, len(view.items), refs=True)) if view.items else []
        if got and got[0][0] >= least and got[0][0] - (got[1][0] if len(got) > 1 else -1.0) >= GEM_BY \
                and not view.hue_veto(f, got[0][0]):
            key = got[0][1]
            names = [n for n in view.items if _base(n) == key]
            if not _other_close(refs, f, set(names), got[0][0]):
                name = _resolve(key, names, bgr)
                if name:
                    return name
        return art_match(bgr, f, refs, only=gems)
    except Exception:
        buglog.caught()
        return None


def fv_match(cell, refs, alike=False):
    """A Top Up cell (PIL) -> the exchange item Scan stash learned it to be, or None (the Favours pictures, cut to
    the item's art so a stash slot and an inventory cell line up). alike=True: [names] - the one item, or the
    look-alikes it could be (Refs.alike), [] for none. 3.0.6: trust in this order - learned and shipped pictures,
    Scan stash's wildcard pictures (stash_match), the exchange icons, poe.ninja's art (art_match); when Scan
    stash's picture says another item than an exchange icon, it's not known (never a guess)."""
    try:
        import numpy as np
        from . import favours as FV
        bgr = np.asarray(cell.convert("RGB"))[:, :, ::-1].copy()
        h, w = bgr.shape[:2]
        e = max(1, int(round(FV.EDGE * w / FV.CELL)))
        f = {"box": FV.feats(FV.art_box(bgr[e:h - e, e:w - e]))}
        name, _score, _margin = refs.best(f)
        clash = False
        if name:
            top = refs.ranked(f, 1, refs=True)
            if top and top[0][2] == "exchange":
                st = stash_match(bgr, f, refs, veto=False) if getattr(refs, "stash", None) else None
                gap = FV.tint_gap(top[0][3], top[0][4])
                if (st and st != name) or art_disagrees(f, refs, name) or (gap is not None and gap > EXCH_TINT_MAX):
                    name, clash = None, True
        else:
            name = stash_match(bgr, f, refs)
        names = [name] if name else ([] if not alike or clash else refs.alike(f))
        if not name and not clash and len(names) != 1:
            hit = by_color(f, refs)
            if hit:
                names = [hit]
        if not names and not clash:
            hit = art_match(bgr, f, refs)
            if hit:
                names = [hit]
        if names:
            names = grade(names, tier_letters(bgr, white=True), refs.items)
        if not alike:
            return names[0] if names else None
        return names
    except Exception:
        buglog.caught()
        return [] if alike else None


WAYSTONE_MIN = 0.70        # 3.0.6: T15 waystones 0.77-1.00 to the shipped picture (red or blue backing),
#                            other items under 0.35
_WAY = []


def _waystone_ref():
    if not _WAY:
        try:
            import cv2
            from . import favours as FV
            from .topup import _templates
            img = cv2.imread(str(_templates() / "waystone_cell.png"))
            _WAY.append(_box_feats(img) if img is not None else None)
        except Exception:
            buglog.caught()
            _WAY.append(None)
    return _WAY[0]


def _box_feats(bgr):
    from . import favours as FV
    h, w = bgr.shape[:2]
    e = max(1, int(round(FV.EDGE * w / FV.CELL)))
    return FV.feats(FV.art_box(bgr[e:h - e, e:w - e]))


def roman(letters):
    """'XV' -> 15, None when it isn't a roman number."""
    vals = {"I": 1, "V": 5, "X": 10}
    if not letters or any(ch not in vals for ch in letters):
        return None
    n = 0
    for i, ch in enumerate(letters):
        v = vals[ch]
        n += -v if i + 1 < len(letters) and vals[letters[i + 1]] > v else v
    return n if 1 <= n <= 30 else None


def family(name):
    """'Perfect Essence of Flames' -> 'Perfect Essence of' (the same crystal in another color), or None."""
    m = re.match(r"^((?:Lesser |Greater |Perfect )?Essence of)\b", str(name))
    return m.group(1) if m else None


FAMILY_TINT, FAMILY_HUE, FAMILY_BY = 10.0, 0.70, 0.15     # 3.0.6: a red Perfect Essence: the Body 7.6 / 0.82, the
#                                                            next 18.4 / 0.63 (two white ones stay not known)


def by_color(f, refs):
    """3.0.6 (an essence wasn't counted: its learned look-alikes are other colors): when the closest pictures are
    all one family (an essence tier), the member whose colors match far better than the rest - any picture of
    it, the exchange icon too. -> name or None."""
    from . import favours as FV
    got = refs.ranked(f, 12, refs=True)
    if not got or got[0][0] < FV.MATCH_SURE:
        return None
    fam = family(got[0][1])
    if not fam:
        return None
    best = {}
    for sc, name, _src, cf, rf in refs.ranked(f, len(refs.items), refs=True):
        if family(name) != fam:
            continue
        t, h = FV.tint_gap(cf, rf), FV.hue_sim(cf, rf)
        if t is None or h is None:
            continue
        if name not in best or (t, -h) < (best[name][0], -best[name][1]):
            best[name] = (t, h)
    order = sorted(best.items(), key=lambda kv: kv[1][0])
    if not order:
        return None
    name, (t, h) = order[0]
    nxt = order[1][1] if len(order) > 1 else (99.0, 0.0)
    if t <= FAMILY_TINT and h >= FAMILY_HUE and h - max(v[1] for k, v in best.items() if k != name or len(best) == 1) \
            >= (FAMILY_BY if len(best) > 1 else 0) and nxt[0] - t >= 8.0:
        return name
    return None


def tier_letters(bgr, white=False):
    """A waystone cell (BGR) -> its red tier letters ('XV'), or '' - the red roman number at its bottom right. Each
    letter by shape: I is thin; V narrows to a point at its foot; X is as wide at its foot as at its top."""
    import cv2
    import numpy as np
    h, w = bgr.shape[:2]
    b, g, r = (bgr[..., i].astype(int) for i in range(3))
    if white:                                     # (Greater / Perfect currency: a white II / III)
        lo = np.minimum(np.minimum(r, g), b)
        m = ((lo > 165) & (np.maximum(np.maximum(r, g), b) - lo < 50)).astype(np.uint8)
    else:
        m = ((r > 150) & (g < 90) & (b < 90)).astype(np.uint8)
    m[:int(h * 0.55)] = 0
    m[:, :int(w * (0.3 if white else 0.45))] = 0         # (3.0.6: an uncut gem's XVIII starts at 0.37)
    n, lab, st, _c = cv2.connectedComponentsWithStats(m, 8)
    out = []
    keep = [i for i in range(1, n) if 0.12 * w <= st[i][3] <= 0.30 * w and st[i][4] >= 6]
    if white:                                     # (3.0.6: only the run of letters at the right edge, on one line -
        keep.sort(key=lambda k: -st[k][0])        # a gem's art has white highlights too)
        run = []
        for i in keep:
            x, y, bw, bh = (int(v) for v in st[i][:4])
            if not run:
                if x + bw < 0.85 * w:
                    break
                run.append(i)
                continue
            if abs((y + bh) - int(st[run[0]][1] + st[run[0]][3])) > 0.05 * w:
                continue                          # (a highlight above the line)
            if int(st[run[-1]][0]) - (x + bw) <= 0.09 * w:
                run.append(i)
            else:
                break
        keep = run
    for i in sorted(keep, key=lambda k: st[k][0]):
        x, y, bw, bh, area = (int(v) for v in st[i])
        if bw < 0.45 * bh:
            out.append("I")
            continue
        g_ = lab[y:y + bh, x:x + bw] == i
        q = max(1, bh // 4)
        top = np.ptp(np.where(g_[:q].any(0))[0]) + 1 if g_[:q].any() else 0
        foot = np.ptp(np.where(g_[-q:].any(0))[0]) + 1 if g_[-q:].any() else 0
        out.append("V" if foot < 0.6 * top else "X")
    return "".join(out)


GRADES = {"II": "Greater ", "III": "Perfect "}


def grade(names, letters, known):
    """3.0.6 (a Greater Exalted Orb was not read): the white II / III on a currency picture says
    Greater / Perfect - the same orb otherwise. -> names with that grade (the matched one moved to it when known),
    or as they were."""
    def base(n):
        for g in GRADES.values():
            if n.startswith(g):
                return n[len(g):]
        return n
    want = GRADES.get(letters)
    if want is None:                                      # (no mark read: as matched - a missed mark never
        return names                                      # demotes a Greater one)
    same = [n for n in names if n.startswith(want)]
    if same:                                              # (a III: only the Perfect ones it looked like)
        return same
    out = []
    for n in names:
        cand = want + base(n)
        out.append(cand if cand in known else n)
    return list(dict.fromkeys(out))


def waystone_tier(cell):
    """3.0.6 (show waystones by tier without a price, to show they were read): a cell
    (PIL) -> its tier (0 = a waystone, tier not read) or None (not a waystone)."""
    try:
        import numpy as np
        from . import favours as FV
        ref = _waystone_ref()
        if ref is None:
            return None
        bgr = np.asarray(cell.convert("RGB"))[:, :, ::-1].copy()
        if FV.score(_box_feats(bgr), ref) < WAYSTONE_MIN:
            return None
        return roman(tier_letters(bgr)) or 0
    except Exception:
        buglog.caught()
        return None


def waystone_name(tier):
    return f"Waystone (Tier {tier})" if tier else "Waystone"


def is_waystone(name):
    return str(name).startswith("Waystone")


def identify(cells, taught, refs=None, price=None, info=None):
    """Top Up's cells -> ({name: count}, how many cells it couldn't name). Taught pictures first, then Scan stash's.

    3.0.6 (things already learned for Scan stash were missing): a cell with no stack number (gear, a jewel,
    a waystone) is never currency - skipped, not "not known" (a sword's corner was counted as an Idol). Look-alikes
    it can't tell apart (two Perfect Essences in one white) are not known - never a guess. price: unused (kept for
    callers). info: a dict that gets "skipped" (no stack number) and "alike" {key: [the look-alikes]}."""
    from . import topup as TU
    out, unknown, skipped, alike, unknown_cells = {}, 0, 0, {}, []
    for c in cells or []:
        name = TU.which(c["sig"], taught) if taught else None
        if name is None and c.get("shown") is False:
            t = waystone_tier(c["img"]) if c.get("img") is not None else None
            if t is None:
                gem = gem_match(c.get("img"), refs) if refs is not None else None     # 3.0.6: lineage / uncut
                if gem is None and refs is not None and getattr(refs, "loose", None):  # gems, crisis fragments,
                    gem = gem_match(c.get("img"), refs, pool=refs.loose, least=LOOSE_MIN)   # logbooks: no number
                if gem is None:
                    skipped += 1
                    continue
                out[gem] = out.get(gem, 0) + 1
                continue
            name = waystone_name(t)
        if name is None and refs is not None and c.get("img") is not None:
            names = fv_match(c["img"], refs, alike=True)
            if len(names) > 1:                            # (owner: never a guess - two it can't tell apart are
                alike["/".join(names[:3])] = names        # "not known", and the log says which)
            elif names:
                name = names[0]
        if name is None:
            unknown += 1
            if c.get("img") is not None:
                unknown_cells.append((c["img"], c.get("count")))
            continue
        out[name] = out.get(name, 0) + (c["count"] if c.get("count") is not None else 1)
    if info is not None:
        info.update(skipped=skipped, alike=alike, unknown_cells=unknown_cells)
    return out, unknown


def exchange_only(counts, price):
    """Only Currency Exchange items (price(name) -> divines each, or None: not on the exchange - never counted)."""
    return {n: k for n, k in counts.items() if price(n) is not None}


# ---------------------------------------------------------------- one map
def rows(before, after, price):
    """-> [(name, before, after, divines each, worth)] for what a map gained, most worth first. 2.132.2 (feedback:
    nothing lost was marked as -div): fewer of an item is never counted - it was used,
    stashed or covered, not lost to the map."""
    out = []
    for name in set(before) | set(after):
        b, a = before.get(name, 0), after.get(name, 0)
        if a <= b:
            continue
        each = price(name)
        if each is None:
            continue
        out.append((name, b, a, each, (a - b) * each))
    out.sort(key=lambda r: -r[4])
    return out


def entry(map_name, secs, before, after, price, t=None, unknown=0):
    """One map's line for the log."""
    rs = rows(before, after, price)
    return {"t": round(t if t is not None else time.time()), "map": map_name or "", "secs": int(secs or 0),
            "div": round(sum(r[4] for r in rs), 4), "unknown": int(unknown),
            "rows": [[r[0], r[1], r[2], round(r[3], 6)] for r in rs]}


# ---------------------------------------------------------------- the log (your PC only)
def log_add(e):
    try:
        with open(P(LOG_FILE), "a", encoding="utf-8") as f:
            f.write(json.dumps(e) + "\n")
        return True
    except OSError:
        buglog.caught()
        return False


def log_read(since=0):
    out = []
    try:
        with open(P(LOG_FILE), encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and e.get("t", 0) >= since:
                    out.append(e)
    except FileNotFoundError:
        pass
    except OSError:
        buglog.caught()
    return out


def log_tidy(now=None):
    """Drop lines older than KEEP_DAYS (once a day is plenty)."""
    now = now or time.time()
    keep = log_read(now - KEEP_DAYS * 86400)
    try:
        if os.path.exists(P(LOG_FILE)) and len(keep) < sum(1 for _ in open(P(LOG_FILE), encoding="utf-8")):
            tmp = P(LOG_FILE) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(json.dumps(e) + "\n" for e in keep)
            os.replace(tmp, P(LOG_FILE))
    except OSError:
        buglog.caught()


def log_write(entries):
    """Rewrite the log with these lines (2.132.6: deleting maps)."""
    try:
        tmp = P(LOG_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(e) + "\n" for e in entries)
        os.replace(tmp, P(LOG_FILE))
        return True
    except OSError:
        buglog.caught()
        return False


def log_delete(run_ids):
    """Drop every line of these maps (their run ids). -> the dropped lines (for Undo)."""
    ids = set(run_ids)
    keep, gone = [], []
    for e in log_read():
        (gone if (e.get("run") or str(e.get("t"))) in ids else keep).append(e)
    if gone:
        log_write(keep)
    return gone


def log_restore(lines):
    """Undo a delete: the lines back, in time order."""
    log_write(sorted(log_read() + list(lines), key=lambda e: e.get("t", 0)))


def buckets(runs, kind, now=None):
    """2.132.6 (feedback: a log by date with graphs and bars - All Time, Daily, Hourly): maps -> [(label,
    start time, maps, div, secs)], oldest first. kind: "day" (each day with maps) or "hour" (the last 48 hours, each
    hour)."""
    now = now or time.time()
    out = {}
    for r in runs:
        lt = time.localtime(r["t"])
        if kind == "hour":
            if r["t"] < now - 48 * 3600:
                continue
            start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, 0, 0, 0, 0, -1))
            label = time.strftime("%a %H:00", lt)
        else:
            start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            label = time.strftime("%a %d %b", lt)
        b = out.setdefault(start, [label, start, 0, 0.0, 0])
        b[2] += 1
        b[3] += r["div"]
        b[4] += r["secs"]
    return [tuple(b) for _s, b in sorted(out.items())]


def day_start(now=None):
    lt = time.localtime(now or time.time())
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


def totals(entries, now=None, session_start=None):
    """-> {"map": last map's div, "session": (div, maps), "hour": div in the last hour, "day": (div, maps) today,
    "per_map": session average, "per_hour": session div per hour of maps}."""
    now = now or time.time()
    es = sorted(entries, key=lambda e: e.get("t", 0))
    ses = [e for e in es if session_start is None or e.get("t", 0) >= session_start]
    today = [e for e in es if e.get("t", 0) >= day_start(now)]
    s_div = sum(e.get("div", 0) for e in ses)
    s_secs = sum(e.get("secs", 0) for e in ses)
    return {"map": es[-1].get("div") if es else None,
            "session": (s_div, len(ses)),
            "hour": sum(e.get("div", 0) for e in es if e.get("t", 0) >= now - 3600),
            "day": (sum(e.get("div", 0) for e in today), len(today)),
            "per_map": s_div / len(ses) if ses else None,
            "per_hour": s_div * 3600 / s_secs if s_secs >= 60 else None}


def signed(v, fmt):
    """+3.8 div / −0.4 div (fmt: pricefmt.fmt_div)."""
    if v is None:
        return "–"
    return ("+" if v >= 0 else "−") + fmt(abs(v))
