"""2.132.3 One read round the mouse for the helper that reads a tooltip: in the temple, Vaal Lens (a medallion's name
on the ground). (3.0.6: the Ritual Identifier is gone - it couldn't be automated under GGG policy.)
GGG policy (Nov 2026: "Reading from the screen ... may only be performed once per manual key press"): it reads when
you press your Read Key with the tooltip on screen - the part round the mouse, from the press's one picture
(screenread.py). It never reads by itself. (Owner decision: the Temple Helper's Vaal Beacon tooltip read and Map
Content's Temple icon are gone - the Temple Console gives the crystals.)"""

from . import buglog

AROUND = (0.25, 0.38, 0.06)        # the part looked at: half its width, up and down from the mouse (parts of the game)
# A tooltip is found by its long straight edges (a cheap check), then only it is read, made bigger.
EDGE_LONG = 0.20                    # a tooltip edge: a straight line at least this long (x the game's height) ...
EDGE_FILL = 0.85                    # ... unbroken for this much of it ...
EDGE_STEP = 14                      # ... where brightness steps by this much from the row above to the row below
EDGE_ROWS = 6                       # this many such rows close together = a tooltip


def region(pointer, game):
    """The mouse (x, y) and the game (x, y, w, h) -> (left, top, right, bottom) round the mouse, inside the game."""
    gx, gy, gw, gh = game
    px, py = pointer
    hw = int(AROUND[0] * gw)
    left, right = max(gx, px - hw), min(gx + gw, px + hw)
    top, bottom = max(gy, py - int(AROUND[1] * gh)), min(gy + gh, py + int(AROUND[2] * gh))
    return left, top, right, bottom


def find_tooltip(rgb, game_h, xstep=2):
    """A picture (H x W x 3) -> (x0, y0, x1, y1) of a tooltip in it, or None. A tooltip's frame is made of long,
    straight, level edges - a map seen from above has almost none (lightning can make one or two)."""
    import numpy as np
    a = np.asarray(rgb)[:, ::xstep].astype(np.int16)
    if a.ndim != 3 or a.shape[0] < 4:
        return None
    lum = (a[..., 0] * 3 + a[..., 1] * 6 + a[..., 2]) // 10
    dy = lum[2:] - lum[:-2]
    w = max(8, int(game_h * EDGE_LONG / xstep))
    if dy.shape[1] <= w:
        return None
    hits = []
    for sign in (1, -1):
        c = np.cumsum((dy * sign) > EDGE_STEP, axis=1, dtype=np.int32)
        ok = (c[:, w:] - c[:, :-w]) >= int(w * EDGE_FILL)
        for r in np.flatnonzero(ok.any(axis=1)):
            cols = np.flatnonzero(ok[r])
            hits.append((int(r) + 1, int(cols[0]), int(cols[-1]) + w))
    if len(hits) < EDGE_ROWS:
        return None
    hits.sort()
    span = int(game_h * 0.16)                    # a tooltip is about 0.12 of the game's height
    best = None
    for i in range(len(hits)):
        grp = [h for h in hits[i:] if h[0] - hits[i][0] <= span]
        if len(grp) >= EDGE_ROWS and (best is None or len(grp) > len(best)):
            best = grp
    if best is None:
        return None
    pad = int(game_h * 0.012)
    hgt, wid = lum.shape[0], a.shape[1] * xstep
    x0 = min(h[1] for h in best) * xstep - pad
    x1 = max(h[2] for h in best) * xstep + pad
    return max(0, x0), max(0, best[0][0] - pad), min(wid, x1), min(hgt, best[-1][0] + int(game_h * 0.05))


def read_lines(img, game_h, ocr, want=lambda lines: True):
    """The part round the mouse (one cut of the press's picture) -> its text lines: the tooltip's frame found and read
    on its own, bigger; Round 18: when that isn't what's wanted (no tooltip found, or the frame found was another
    box), the whole part is read too (the same picture - no second screen read)."""
    import numpy as np
    lines = []
    tip = find_tooltip(np.asarray(img), game_h)
    if tip:
        cut = img.crop(tip)
        k = 2 if cut.height < game_h * 0.25 else 1
        if k > 1:
            cut = cut.resize((cut.width * 2, cut.height * 2))
        lines = [(t, tuple(int(v / k) for v in b)) for t, b in ocr(cut)]
    if not lines or not want(lines):
        lines = lines + list(ocr(img))
    return lines


def text_by_color(img, ocr):
    """3.0.6 (owner: "I got no read for this medallion" - a label over lava read as noise): the picture's gold text
    (a medallion's name) and white text (what it does) read on their own, black on white -> more lines."""
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    gold = (a[..., 0] - a[..., 2] > 40) & (a[..., 0] > 120) & (a[..., 1] > 90)
    white = a.min(axis=-1) > 150
    out = []
    for m in (gold, white):
        g = Image.fromarray(np.where(m, 0, 255).astype("uint8"))
        out += list(ocr(g.resize((g.width * 2, g.height * 2))))
    return [(t, tuple(int(v / 2) for v in b) if b else b) for t, b in out]


# what a medallion's label says it does -> the medallion (when its name doesn't read)
DOES = (("PREVENT THE NEXT DESTABIL", "Juatalotli's Medallion"), ("ADD ROOM", "Uromoti's Medallion"))


def medal_names(lines):
    """-> [(name, room)] read on a medallion's label: by its name, else by what it says it does."""
    from . import medallions as M
    med = M.parse(lines or [])
    names = list(dict.fromkeys(n for n, _b in med["names"]))
    if not names:
        text = " ".join(" ".join(str(t).upper().split()) for t, _b in lines or [])
        names = [n for k, n in DOES if k in text][:1]
    return [(n, med["room"]) for n in names], med


class HoverPage:
    """Mixed into App."""

    def hover_medals(self):
        """Vaal Lens in the temple (and Vaal Ruins): a medallion's name under the mouse -> take it or leave it."""
        return bool(getattr(self, "tm_in_temple", False) and self.temple_pad_on())

    def hover_look_job(self, ctx):
        """A Read Key press in the temple (or Vaal Ruins): the tooltip round the mouse -> a medallion's name (Vaal
        Lens)."""
        # 3.0.6 audit: Vaal Ruins is a town to the app (a hub) - a medallion there is read too
        if not self.hover_medals():
            return None
        if ctx.get("area") in ("hideout", "town"):
            # 3.0.6 (owner: "screen reading after a run takes so long"): medallions drop in the temple itself - a
            # press in Vaal Ruins or your hideout (reading your inventory) doesn't read round the mouse too
            return None
        from . import screenread as SR, vaallens as V
        g, ptr = ctx["g"], ctx["ptr"]
        mb = V.side_box(g, V.MEDAL_BOX, right=True)
        if ptr and mb[0] <= ptr[0] <= mb[2] and mb[1] <= ptr[1] <= mb[3]:
            return None          # 3.0.6 (owner): a medallion in your panel at the console - no take it / leave it
        box = region(ptr, g)
        if box[2] <= box[0] or box[3] <= box[1]:
            return None

        def work():
            from . import remnant as RM
            img = SR.capture(box, "Vaal Lens")
            if img is None:
                return []
            lines = read_lines(img, g[3], RM.ocr)
            from . import medallions as M
            text = " ".join(str(t).upper() for t, _b in lines)
            if not M.parse(lines)["names"] and any(w in text for w in ("MEDALL", "ROOM:", "SUMMON")):
                lines = lines + text_by_color(img, RM.ocr)      # (the same picture, gold and white text alone)
            return lines

        def found(lines):
            """(the read mark) A medallion's name."""
            if not lines:
                return False
            got, med = medal_names(lines)
            return bool(med["count"] or got)
        work.found = found

        def done(lines):
            # 2.142.0 Vaal Lens: a medallion's name on screen in the temple (its label or tooltip), the
            # Medallions panel closed -> take it or leave it
            got, med = medal_names(lines)
            buglog.debug("Vaal Lens", "under the mouse: " + (", ".join(n for n, _r in got) or
                                                             f"no medallion name ({len(lines or [])} lines)")
                         + (f" · room {med['room']}" if med.get("room") else ""))    # (game text only)
            if not med["count"]:
                for name, room in got:
                    self.temple_medal_drop(name, room)
        return "Vaal Lens", work, done
