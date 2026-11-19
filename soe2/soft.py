"""UI rule 24 (the softer look): about 6 px round corners on cards, panels, buttons, fields, chips and dropdowns, and a
thin round scroll bar that stays quiet until the mouse is on it. Tk has no border radius, so the corners are pictures:

- Drawn 4x bigger with Pillow, then made small (LANCZOS): smooth (anti-aliased) edges on every system - a smoothed
  canvas polygon (the old themes.round_rect) is jagged on Windows. Kept per Tk (a picture belongs to the Tk that made
  it - gearicon.py's 3.0.6 fix) and per size and colors, so nothing is drawn twice.
- A round box on a canvas (round_rect) is 9-slice: 4 corner pictures + plain rectangles for the middle and the edges.
  A resize moves the parts and never draws a new big picture, and the theme walk re-colors the plain parts by itself.
  It acts as ONE item: Canvas calls on the id it returns (coords, itemconfigure, tag_lower, delete, move, bbox ...)
  act on all of its parts.
- ttk buttons, fields, dropdowns and scroll bars: image elements made of the same pictures (style.setup_style, again
  for every theme). Their see-through corners blend into the color behind each widget (a style per background,
  picked again after a theme change).
- tk frames with a border or their own color (cards, sections, empty states, the search boxes, SegBar): 4 small corner
  caps placed over the frame's corners - opaque pictures, so nothing is blended while the page moves.
- Windows over the app (tooltips, toasts): Windows 11 rounds them itself (DWM); elsewhere they stay square.
Without Pillow everything stays as it was (polygons, square faces)."""
import os
import sys
import tkinter as tk
import weakref
from tkinter import ttk

from . import buglog
from . import themes as TH

RADIUS = 6                 # rule 24: buttons, fields, chips, cards (the Dashboard's big cards keep their own)
K = 4                      # drawn this many times bigger, then made small
SB_W = 10                  # the scroll bar: this wide; its thumb 6 px, 8 px with the mouse on it
MID = 48                   # a ttk picture's middle (stretched by tiling it): wide, so a wide widget takes few tiles
_PIL = []


def pil():
    """(Image, ImageDraw, ImageTk) or None."""
    if not _PIL:
        if os.environ.get("SOE2_NO_SOFT"):               # (to measure / rule out: the square look as before)
            _PIL.append(None)
            return None
        try:
            from PIL import Image, ImageDraw, ImageTk
            _PIL.append((Image, ImageDraw, ImageTk))
        except Exception:
            _PIL.append(None)
    return _PIL[0]


def tk_cache(w):
    """This Tk's pictures and made elements - kept on its root window, so a new Tk starts with none."""
    root = w._root()
    d = root.__dict__.get("_soe2_soft")
    if d is None:
        d = root.__dict__["_soe2_soft"] = {}
    return d


_RGB = {}


def rgb(w, color):
    """'#rrggbb' / a Tk color name -> (r, g, b), or None for no color."""
    if not color:
        return None
    c = str(color)
    got = _RGB.get(c)
    if got is not None:
        return got
    if TH.is_hex(c):
        v = tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
    else:
        try:
            v = tuple(x >> 8 for x in w.winfo_rgb(c))
        except (tk.TclError, AttributeError):
            return None
    _RGB[c] = v
    return v


def hexc(v):
    return "#%02x%02x%02x" % tuple(v[:3])


# ------------------------------------------------------------------ the pictures (Pillow, no Tk)
_MASKS = {}
_SHAPES = {}


def _mask(w, h, r, inset=0):
    """A w x h 'L' mask: a round box (radius r) inset by `inset` px, smooth edges (drawn K times bigger)."""
    key = (w, h, r, inset)
    got = _MASKS.get(key)
    if got is not None:
        return got
    Image, ImageDraw, _ = pil()
    big = Image.new("L", (w * K, h * K), 0)
    x0 = y0 = inset * K
    x1, y1 = w * K - 1 - inset * K, h * K - 1 - inset * K
    if x1 > x0 and y1 > y0:
        ImageDraw.Draw(big).rounded_rectangle((x0, y0, x1, y1), radius=max(0, r - inset) * K, fill=255)
    m = big.resize((w, h), Image.LANCZOS).point(lambda v: 0 if v < 6 else 255 if v > 249 else v)
    if len(_MASKS) > 600:
        _MASKS.clear()
    _MASKS[key] = m
    return m


def shape(w, h, r, fill=None, outline=None, ow=1, rows=None, alpha=1.0, under=None, clear=False):
    """A Pillow RGBA picture w x h: a round box. fill / outline: (r, g, b) or None (none); rows: [(r, g, b)] one per
    row (a gradient) in place of fill; alpha: how solid; under: (r, g, b) - laid on that color, opaque (clear: what
    is wholly outside stays see-through). Tk blends a half see-through picture by reading the screen back - slow
    (a page of them took seconds on X11) - so every picture shown is laid on the color behind it."""
    key = (w, h, r, fill, outline, ow, tuple(rows) if rows else None, alpha, under, clear)
    got = _SHAPES.get(key)
    if got is not None:
        return got
    Image = pil()[0]
    from PIL import ImageChops
    r = max(0, min(r, (w - 1) // 2, (h - 1) // 2))
    outer = _mask(w, h, r)
    ow = ow if outline else 0
    inner = _mask(w, h, r, ow) if ow else outer
    if rows:
        col = Image.new("RGB", (1, h))
        col.putdata([tuple(rows[min(len(rows) - 1, y)]) for y in range(h)])
        body = col.resize((w, h), Image.NEAREST)
    else:
        body = Image.new("RGB", (w, h), fill or (0, 0, 0))
    has_fill = bool(rows or fill)
    if ow:
        edge = Image.new("RGB", (w, h), outline)
        pic = Image.composite(body, edge, inner) if has_fill else edge
        a = outer if has_fill else ImageChops.subtract(outer, inner)
    else:
        pic, a = body, outer if has_fill else Image.new("L", (w, h), 0)
    if alpha < 1.0:
        a = a.point(lambda v: int(v * alpha + 0.5))
    if under is not None:
        out = Image.composite(pic, Image.new("RGB", (w, h), under), a).convert("RGBA")
        if clear:
            out.putalpha(a.point(lambda v: 255 if v else 0))
    else:
        out = pic.convert("RGBA")
        out.putalpha(a)
    if len(_SHAPES) > 800:
        _SHAPES.clear()
    _SHAPES[key] = out
    return out


def photo(w, key, make):
    """A PhotoImage for this Tk, made once by make() (a Pillow picture) - or None without Pillow."""
    c = tk_cache(w)
    got = c.get(key)
    if got is not None:
        return got
    if pil() is None:
        return None
    try:
        img = pil()[2].PhotoImage(make(), master=w._root())
    except Exception:
        buglog.caught()
        return None
    c[key] = img
    return img


def corners(w, r, fill, outline, ow, under=None):
    """(top left, top right, bottom left, bottom right) PhotoImages, r x r - a round box's corners, their smooth
    edge laid on `under` (the color behind them; outside the curve: see-through)."""
    key = ("corners", r, fill, outline, ow, under)
    c = tk_cache(w)
    got = c.get(key)
    if got is not None:
        return got
    S = 2 * r + 1
    st = shape(S, S, r, fill, outline, ow, under=under, clear=under is not None)
    ImageTk = pil()[2]
    boxes = ((0, 0, r, r), (r + 1, 0, S, r), (0, r + 1, r, S), (r + 1, r + 1, S, S))
    got = c[key] = tuple(ImageTk.PhotoImage(st.crop(b), master=w._root()) for b in boxes)
    return got


# ------------------------------------------------------------------ a round box on a canvas (9-slice)
_KNOWN = {"fill", "outline", "width", "tags", "tag", "state"}


def canvas_round_rect(cv, x0, y0, x1, y1, r, **kw):
    """themes.round_rect with Pillow: -> the id of its first part (an image item), or None (the caller falls back to
    the polygon) without Pillow or with an option this can't draw (dash, stipple ...)."""
    if pil() is None or not set(kw) <= _KNOWN:
        return None
    _install()
    fill = kw.get("fill", "black")                       # (a canvas polygon's own defaults)
    outline = kw.get("outline", "")
    tags = kw.get("tags", kw.get("tag", ()))
    if isinstance(tags, str):
        tags = tuple(cv.tk.splitlist(tags))
    tags = tuple(tags or ())
    try:
        ow = max(1, int(round(float(kw.get("width", 1) or 1))))
    except (TypeError, ValueError):
        ow = 1
    rec = {"box": (x0, y0, x1, y1), "r": max(0, int(round(r))), "fill": TH.tone(fill) if fill else "",
           "outline": TH.tone(outline) if outline else "", "ow": ow}
    state = kw.get("state")
    extra = ("-state", state) if state else ()
    call = cv.tk.call
    w = cv._w
    with TH.raw():
        first = int(call(w, "create", "image", 0, 0, "-anchor", "nw", *extra))
        g = "soe2rr%d" % first
        tg = tags + (g,)
        call(w, "itemconfigure", first, "-tags", tg)
        parts = [first]
        for _i in range(3):
            parts.append(int(call(w, "create", "image", 0, 0, "-anchor", "nw", "-tags", tg, *extra)))
        for _i in range(6):
            parts.append(int(call(w, "create", "rectangle", 0, 0, 0, 0, "-outline", "", "-width", 0, "-tags", tg,
                                  *extra)))
    rec["parts"], rec["g"] = parts, g
    m = cv.__dict__.get("_soe2_rr")
    if m is None:
        m = cv.__dict__["_soe2_rr"] = {}
        cv.__dict__["_soe2_rr_n"] = 64
    m[first] = rec
    pm = cv.__dict__.setdefault("_soe2_rrpart", {})
    for pid in parts[4:]:
        pm[pid] = rec
    if len(m) > cv.__dict__["_soe2_rr_n"]:              # forget boxes deleted by a tag (a tip, a row ...)
        for k in [k for k, v in m.items() if not call(w, "find", "withtag", k)]:
            for pid in m.pop(k)["parts"][4:]:
                pm.pop(pid, None)
        cv.__dict__["_soe2_rr_n"] = max(64, 2 * len(m))
    _layout(cv, rec)
    return first


def _layout(cv, rec):
    """Put a round box's parts where its box is, in its colors."""
    call, w = cv.tk.call, cv._w
    x0, y0, x1, y1 = rec["box"]
    fill, outline = rec["fill"], rec["outline"]
    ow = rec["ow"] if outline else 0
    X0, X1 = int(round(min(x0, x1))), int(round(max(x0, x1)))
    Y0, Y1 = int(round(min(y0, y1))), int(round(max(y0, y1)))
    if ow:                                               # (as a canvas draws its outline: on the edge, inside out)
        X0, Y0, X1, Y1 = X0 - ow // 2, Y0 - ow // 2, X1 + (ow - 1) // 2, Y1 + (ow - 1) // 2
    else:
        X1, Y1 = X1 - 1, Y1 - 1
    W, H = X1 - X0 + 1, Y1 - Y0 + 1
    c = max(0, min(rec["r"], (W - 1) // 2, (H - 1) // 2))
    p = rec["parts"]
    if c > 0 and (fill or outline):
        imgs = corners(cv, c, rgb(cv, fill), rgb(cv, outline), ow, _under(cv, rec, X0, Y0, c))
    else:
        imgs = ("", "", "", "")
    rec["imgs"] = imgs                                   # (kept: a picture in use is never let go)
    for i, (x, y) in enumerate(((X0, Y0), (X1 - c + 1, Y0), (X0, Y1 - c + 1), (X1 - c + 1, Y1 - c + 1))):
        call(w, "coords", p[i], x, y)
        call(w, "itemconfigure", p[i], "-image", imgs[i])
    f, o = fill or "", outline or ""
    for pid, box, col in (
            (p[4], (X0 + c, Y0 + ow, X1 - c + 1, Y1 - ow + 1), f),
            (p[5], (X0 + ow, Y0 + c, X1 - ow + 1, Y1 - c + 1), f),
            (p[6], (X0 + c, Y0, X1 - c + 1, Y0 + ow), o if ow else ""),
            (p[7], (X0 + c, Y1 - ow + 1, X1 - c + 1, Y1 + 1), o if ow else ""),
            (p[8], (X0, Y0 + c, X0 + ow, Y1 - c + 1), o if ow else ""),
            (p[9], (X1 - ow + 1, Y0 + c, X1 + 1, Y1 - c + 1), o if ow else "")):
        call(w, "coords", pid, *box)
        call(w, "itemconfigure", pid, "-fill", col)


def _under(cv, rec, x, y, c):
    """The color behind a round box's top left corner: the topmost filled item under it (a card it sits on), else
    the canvas's background."""
    call, w = cv.tk.call, cv._w
    first = rec["parts"][0]
    pm = cv.__dict__.get("_soe2_rrpart") or {}
    try:
        items = [int(i) for i in cv.tk.splitlist(call(w, "find", "overlapping", x + c / 2, y + c / 2, x + c / 2,
                                                       y + c / 2))]
        below = items[:items.index(first)] if first in items else items
        for i in reversed(below):
            other = pm.get(i)
            if other is not None:
                if other["fill"]:
                    return rgb(cv, other["fill"])
                continue
            kind = str(call(w, "type", i))
            if kind in ("rectangle", "oval", "polygon", "arc"):
                f = str(call(w, "itemcget", i, "-fill"))
                if f and str(call(w, "itemcget", i, "-state")) != "hidden":
                    return rgb(cv, f)
        return rgb(cv, str(call(w, "cget", "-background")))
    except (tk.TclError, ValueError):
        return None


def round_rect_rec(cv, item):
    """The round box an id stands for (its first part's id), or None."""
    m = cv.__dict__.get("_soe2_rr")
    if not m:
        return None
    try:
        return m.get(int(item)) if not isinstance(item, str) or item.isdigit() else None
    except (TypeError, ValueError):
        return None


def retone(cv):
    """After the theme walk re-colored a canvas's plain parts: the corners follow them."""
    m = cv.__dict__.get("_soe2_rr")
    if not m:
        return
    call, w = cv.tk.call, cv._w
    for k, rec in list(m.items()):
        try:
            if not call(w, "find", "withtag", k):
                m.pop(k, None)
                continue
            p = rec["parts"]
            f = str(call(w, "itemcget", p[4], "-fill"))
            o = str(call(w, "itemcget", p[6], "-fill")) if rec["outline"] else ""
            rec["fill"], rec["outline"] = f, o
            _layout(cv, rec)                            # (the color behind it changed too)
        except tk.TclError:
            m.pop(k, None)


def _install():
    """Canvas calls on a round box's id act on all its parts (once, for every canvas)."""
    C = tk.Canvas
    if getattr(C, "_soe2_rr", False):
        return
    o_coords, o_conf, o_cget = C.coords, C.itemconfigure, C.itemcget
    o_lower, o_raise, o_delete, o_move = C.tag_lower, C.tag_raise, C.delete, C.move
    o_bbox, o_bind, o_moveto = C.bbox, C.tag_bind, getattr(C, "moveto", None)
    rec_of = round_rect_rec

    def coords(self, *args):
        rec = rec_of(self, args[0]) if args and self.__dict__.get("_soe2_rr") else None
        if rec is None:
            return o_coords(self, *args)
        x0, y0, x1, y1 = rec["box"]
        if len(args) == 1:
            return [float(min(x0, x1)), float(min(y0, y1)), float(max(x0, x1)), float(max(y0, y1))]
        pts = list(args[1]) if len(args) == 2 and isinstance(args[1], (list, tuple)) else list(args[1:])
        xs, ys = [float(v) for v in pts[0::2]], [float(v) for v in pts[1::2]]
        rec["box"] = (min(xs), min(ys), max(xs), max(ys))
        _layout(self, rec)
        return None

    def itemconfigure(self, tagOrId, cnf=None, **kw):
        rec = rec_of(self, tagOrId) if self.__dict__.get("_soe2_rr") else None
        if rec is None:
            return o_conf(self, tagOrId, cnf, **kw)
        kw = dict(cnf or {}, **kw)
        if not kw:
            return o_conf(self, tagOrId)
        relay = False
        for k in ("fill", "outline"):
            if k in kw:
                v = kw.pop(k)
                rec[k] = TH.tone(v) if v else ""
                relay = True
        if "width" in kw:
            try:
                rec["ow"] = max(1, int(round(float(kw.pop("width") or 1))))
            except (TypeError, ValueError):
                pass
            relay = True
        for k in [k for k in kw if k not in ("tags", "state")]:
            kw.pop(k)
        if "tags" in kw:
            t = kw["tags"]
            t = tuple(self.tk.splitlist(t)) if isinstance(t, str) else tuple(t or ())
            kw["tags"] = t + (rec["g"],)
        if kw:
            o_conf(self, rec["g"], **kw)
        if relay:
            _layout(self, rec)
        return None

    def itemcget(self, tagOrId, option):
        rec = rec_of(self, tagOrId) if self.__dict__.get("_soe2_rr") else None
        if rec is not None and option in ("fill", "outline", "width"):
            return str(rec["ow"]) if option == "width" else rec[option]
        return o_cget(self, tagOrId, option)

    def _g(self, a):
        rec = rec_of(self, a)
        return rec["g"] if rec is not None else a

    def tag_lower(self, *args):
        if self.__dict__.get("_soe2_rr") and args:
            args = (_g(self, args[0]),) + tuple(args[1:])      # (below a box: below its first part, as it is)
        return o_lower(self, *args)

    def tag_raise(self, *args):
        if self.__dict__.get("_soe2_rr") and args:
            a = [_g(self, args[0])]
            if len(args) > 1:                                  # above a box: above its last part
                rec = rec_of(self, args[1])
                a.append(rec["parts"][-1] if rec is not None else args[1])
            args = tuple(a) + tuple(args[2:])
        return o_raise(self, *args)

    def delete(self, *args):
        m = self.__dict__.get("_soe2_rr")
        if m:
            if "all" in args:
                m.clear()
                self.__dict__.get("_soe2_rrpart", {}).clear()
            else:
                args = tuple(_g(self, a) for a in args)
        return o_delete(self, *args)

    def move(self, *args):
        rec = rec_of(self, args[0]) if args and self.__dict__.get("_soe2_rr") else None
        if rec is None:
            return o_move(self, *args)
        dx, dy = float(args[1]), float(args[2])
        x0, y0, x1, y1 = rec["box"]
        rec["box"] = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        return o_move(self, rec["g"], dx, dy)

    def moveto(self, tagOrId, x="", y=""):
        rec = rec_of(self, tagOrId) if self.__dict__.get("_soe2_rr") else None
        if rec is None:
            return o_moveto(self, tagOrId, x, y)
        b = o_bbox(self, rec["g"])
        if not b:
            return None
        return move(self, tagOrId, (float(x) - b[0]) if x != "" else 0, (float(y) - b[1]) if y != "" else 0)

    def bbox(self, *args):
        if self.__dict__.get("_soe2_rr"):
            args = tuple(_g(self, a) for a in args)
        return o_bbox(self, *args)

    def tag_bind(self, tagOrId, sequence=None, func=None, add=None):
        if self.__dict__.get("_soe2_rr"):
            tagOrId = _g(self, tagOrId)
        return o_bind(self, tagOrId, sequence, func, add)

    C.coords = coords
    C.itemconfigure = C.itemconfig = itemconfigure
    C.itemcget = itemcget
    C.tag_lower = C.lower = tag_lower
    C.tag_raise = C.lift = C.tkraise = tag_raise
    C.delete = delete
    C.move = move
    if o_moveto is not None:
        C.moveto = moveto
    C.bbox = bbox
    C.tag_bind = tag_bind
    C._soe2_rr = True


# ------------------------------------------------------------------ ttk: buttons, fields, dropdowns, scroll bars
# Each ttk look is a builder: make(under) -> a layout whose pictures are laid on `under`, the color behind the widget
# (opaque - see shape()). A widget gets the style Bg<rrggbb>.<its style>: that layout, made once per color and theme.
def face_image(root, w, h, rows, border, radius, inner=None, top_line=None, bottom_shade=None, under=None):
    """A ttk button face: rows = its color per row (a gradient), a 1 px border, round corners - smooth."""
    def make():
        rr = list(rows)
        if inner and h > 2:
            rr[1] = inner
        if top_line:
            for y in (1, 2):
                if y < h - 1:
                    rr[y] = top_line
        if bottom_shade and h > 3:
            rr[h - 2] = bottom_shade
        return shape(w, h, radius, outline=border, ow=1, rows=rr, under=under)
    key = ("face", w, h, tuple(rows), border, radius, inner, top_line, bottom_shade, under)
    return photo(root, key, make)


def _el(root, s, name, *args, **kw):
    """element_create once per Tk (an element can't be made again)."""
    made = tk_cache(root).setdefault("elements", set())
    if name in made:
        return name
    s.element_create(name, "image", *args, **kw)
    made.add(name)
    return name


def register(root, base, make):
    """make(under (r, g, b)) -> the layout of ttk style `base` on that color (its elements made as needed)."""
    tk_cache(root).setdefault("builders", {})[base] = make


def _builder(w, base):
    """The builder for a style: its own, or the one of the style it is made from (Big.Primary.TButton ->
    Primary.TButton's) - unless it has a layout of its own (the overlay's buttons: a plain frame on purpose)."""
    c = tk_cache(w)
    b = c.get("builders") or {}
    parts = base.split(".")
    for i in range(len(parts)):
        key = ".".join(parts[i:])
        got = b.get(key)
        if got is not None:
            if i:
                own = c.setdefault("ownlay", {})
                k = (c.get("ns"), base, key)
                if k not in own:
                    try:
                        lay = lambda n: str(w.tk.call("ttk::style", "layout", n))   # noqa: E731
                        own[k] = lay(base) != lay(key)
                    except tk.TclError:
                        own[k] = True
                if own[k]:
                    return None
            return got
    return None


def variant(w, base, under):
    """The style for `base` on the color `under` -> its name (made now if this theme hasn't yet), or None."""
    make = _builder(w, base)
    if make is None:
        return None
    c = tk_cache(w)
    name = "Bg%s.%s" % (hexc(under)[1:], base)
    made = c.setdefault("variants", {})
    if made.get(name) != c.get("ns"):
        try:
            ttk.Style(w).layout(name, make(under))
            w.tk.call("ttk::style", "configure", name, "-background", hexc(under))
        except tk.TclError:
            buglog.caught()
            return None
        made[name] = c.get("ns")
    return name


def _hx(v):
    return hexc(v)[1:]


def _box_images(root, w, h, r, looks, under):
    """{state key: PhotoImage} for looks {key: (fill rgb, edge rgb)}, laid on under."""
    return {k: photo(root, ("box", w, h, r, f, e, under), lambda f=f, e=e: shape(w, h, r, f, e, 1, under=under))
            for k, (f, e) in looks.items()}


def _chevron(root, w, h, col, on, up=False):
    """A small chevron (the dropdown's / spin box's arrow) in col, laid on the field's color `on`."""
    def make():
        Image, ImageDraw, _ = pil()
        big = Image.new("L", (w * K, h * K), 0)
        d = ImageDraw.Draw(big)
        cx, cy, a = w * K / 2, h * K / 2, 3.2 * K
        pts = [(cx - a, cy - a / 2), (cx, cy + a / 2), (cx + a, cy - a / 2)]
        if up:
            pts = [(x, h * K - y) for x, y in pts]
        d.line(pts, fill=255, width=int(1.6 * K), joint="curve")
        m = big.resize((w, h), Image.LANCZOS)
        return Image.composite(Image.new("RGB", (w, h), col), Image.new("RGB", (w, h), on), m).convert("RGBA")
    return photo(root, ("chev", w, h, col, on, up), make)


def setup_ttk(root, s, ns, C):
    """Round fields (entry, dropdown, spin box), a thin round scroll bar and the round Quiet / Strip buttons, in
    the running theme's colors (C). Called by style.setup_style - again after every theme change, under new element
    names (ns: the theme + accent), so every picture is made again in the new colors. -> False without Pillow."""
    if pil() is None:
        return False
    tk_cache(root)["ns"] = ns
    clam = tk_cache(root).setdefault("clam", {})
    for cls in ("TEntry", "TCombobox", "TSpinbox"):     # (the old square ones, kept for the overlay)
        if cls not in clam:
            clam[cls] = s.layout(cls)
    with TH.raw():
        _fields(root, s, ns, C)
        for o in ("vertical", "horizontal"):
            scrollbar_style(root, s, o.title() + ".TScrollbar", rgb(root, C["text"]), ns=ns, orient=o,
                            under=rgb(root, C["panel"]))
        _flat_buttons(root, s, ns, C)
    _wrap_ttk()
    return True


def _fields(root, s, ns, C):
    r = RADIUS - 2                                   # (fields: a little less round than buttons - the mockup's 4 px)
    n, nh = 2 * (r + 2) + MID, 2 * (r + 2) + 18
    field, line, acc = rgb(root, C["odd"]), rgb(root, C["line"]), rgb(root, C["accent"])
    panel, text, muted = rgb(root, C["panel"]), rgb(root, C["text"]), rgb(root, C["muted"])
    mix = lambda a, b, t: tuple(int(x + (y - x) * t) for x, y in zip(a, b))   # noqa: E731
    looks = {"n": (field, line), "h": (field, mix(line, text, .3)), "f": (field, acc),
             "d": (mix(field, panel, .5), mix(line, panel, .5))}
    dfield = looks["d"][0]
    arrow = _el(root, s, "%s.soft.Combobox.downarrow" % ns, _chevron(root, 20, 16, text, field),
                ("disabled", _chevron(root, 20, 16, muted, dfield)), sticky="")
    up = _el(root, s, "%s.soft.Spinbox.uparrow" % ns, _chevron(root, 18, 11, text, field, up=True),
             ("disabled", _chevron(root, 18, 11, muted, dfield, up=True)), sticky="")
    dn = _el(root, s, "%s.soft.Spinbox.downarrow" % ns, _chevron(root, 18, 11, text, field),
             ("disabled", _chevron(root, 18, 11, muted, dfield)), sticky="")

    def build(cls, under):
        im = _box_images(root, n, nh, r, looks, under)
        name = _el(root, s, "%s.soft.%s.field.%s" % (ns, cls, _hx(under)), im["n"], ("disabled", im["d"]),
                   ("focus", im["f"]), ("hover", im["h"]), border=r + 2, padding=(4, 2), sticky="nsew",
                   width=2 * (r + 2) + 2, height=2 * (r + 2) + 2)   # (asks no more room than the old field)
        if cls == "Entry":
            return [(name, {"sticky": "nswe", "children": [("Entry.padding", {"sticky": "nswe", "children": [
                ("Entry.textarea", {"sticky": "nswe"})]})]})]
        if cls == "Combobox":
            return [(name, {"sticky": "nswe", "children": [
                (arrow, {"side": "right", "sticky": "ns"}),
                ("Combobox.padding", {"expand": "1", "sticky": "nswe", "children": [
                    ("Combobox.textarea", {"sticky": "nswe"})]})]})]
        return [(name, {"sticky": "nswe", "children": [
            ("null", {"side": "right", "sticky": "", "children": [(up, {"side": "top", "sticky": "e"}),
                                                                   (dn, {"side": "bottom", "sticky": "e"})]}),
            ("Spinbox.padding", {"sticky": "nswe", "children": [("Spinbox.textarea", {"sticky": "nswe"})]})]})]
    base = rgb(root, C["bg"])
    for cls in ("Entry", "Combobox", "Spinbox"):
        register(root, "T" + cls, lambda under, cls=cls: build(cls, under))
        s.layout("T" + cls, build(cls, base))


def scrollbar_style(root, s, name, color, ns="", orient="vertical", strong=None, under=None):
    """A thin, round scroll bar for ttk style `name`: no arrows, a faint round track and a round thumb in `color`
    ((r, g, b)), 6 px, 8 px and brighter with the mouse on it; laid on the color behind each bar. The overlay's price
    check popup uses it with its own colors (strong: the thumb with the mouse on it)."""
    if pil() is None:
        return False
    v = orient == "vertical"
    w, h = (SB_W, 10 + MID) if v else (10 + MID, SB_W)
    o = "Vertical" if v else "Horizontal"
    strong = strong or color
    tag = "%s.%s.%s" % (ns or "x", name.replace(".", "_"), "%02x%02x%02x%02x%02x%02x" % (color + strong))

    def track(bg):
        """The faint round track (6 px of color at 7 %) on bg."""
        Image = pil()[0]
        out = Image.new("RGBA", (w, h), bg + (255,))
        lane = shape(6, h, 3, fill=color, alpha=.07) if v else shape(w, 6, 3, fill=color, alpha=.07)
        out.alpha_composite(lane, ((w - 6) // 2, 0) if v else (0, (h - 6) // 2))
        return out

    def pic(thick, col, a, bg):
        """The track on bg, with a round thumb (thick px of col at alpha a) on it - or none (thick 0)."""
        def make():
            out = track(bg)
            if thick:
                th = shape(thick, h, thick // 2, fill=col, alpha=a) if v else shape(w, thick, thick // 2, fill=col,
                                                                                      alpha=a)
                out.alpha_composite(th, ((w - thick) // 2, 0) if v else (0, (h - thick) // 2))
            return out
        return photo(root, ("sb", o, w, h, thick, col, a, bg, color), make)

    def build(under):
        trk = pic(0, color, 0, under)                     # (the thumb is drawn on the track it slides in)
        thumb, hover, press = pic(6, color, .26, under), pic(8, strong, .5, under), pic(8, strong, .65, under)
        bd = (0, 5, 0, 5) if v else (5, 0, 5, 0)
        sub = "%s.%s" % (tag, _hx(under))
        size = {"height": 12} if v else {"width": 12}
        trough = _el(root, s, "%s.soft.%s.Scrollbar.trough" % (sub, o), trk, border=bd,
                     sticky="ns" if v else "ew", **size)
        th = _el(root, s, "%s.soft.%s.Scrollbar.thumb" % (sub, o), thumb, ("pressed", press), ("active", hover),
                 ("hover", hover), border=bd, sticky="nswe", **size)
        return [(trough, {"sticky": "ns" if v else "we", "children": [(th, {"expand": "1", "sticky": "nswe"})]})]
    register(root, name, build)
    s.layout(name, build(under or rgb(root, TH.ST.C["panel"] if TH.ST.C else "#000000")))
    return True


def _flat_buttons(root, s, ns, C):
    """Quiet (no face until the mouse is on it) and Strip (a thin outline, in a header strip) buttons, round."""
    r = RADIUS
    n = 2 * (r + 3) + MID
    g = lambda k: rgb(root, C[k])                        # noqa: E731
    for name, h, looks in (
            ("Quiet.TButton", 34, {"n": (g("panel"), g("panel")), "h": (g("panel2"), g("line")),
                                   "p": (g("odd"), g("line")), "d": (g("panel"), g("panel"))}),
            ("Strip.TButton", 24, {"n": (g("panel"), g("line")), "h": (g("panel2"), g("steel")),
                                   "p": (g("odd"), g("steel")), "d": (g("panel"), g("line"))}),
            ("StripDanger.TButton", 24, {"n": (g("panel"), g("line")), "h": (g("panel2"), g("steel")),
                                         "p": (g("odd"), g("steel")), "d": (g("panel"), g("line"))})):
        def build(under, name=name, h=h, looks=looks):
            im = _box_images(root, n, h, r, looks, under)
            el = _el(root, s, "%s.soft.%s.face.%s" % (ns, name.split(".")[0], _hx(under)), im["n"],
                     ("disabled", im["d"]), ("pressed", im["p"]), ("active", im["h"]),
                     border=(r + 3, h // 2 - 1, r + 3, h // 2 - 1), padding=(2, 1), sticky="nsew",
                     width=2 * (r + 3) + 2)
            return button_layout(el)
        register(root, name, build)
        s.layout(name, build(g("panel")))


def button_layout(el):
    return [(el, {"sticky": "nswe", "children": [("Button.focus", {"sticky": "nswe", "children": [
        ("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]})]})]


# ---- which style each widget gets: Bg<rrggbb>.<its own>, for the color behind it
_DEFAULT = {"TButton": "TButton", "TEntry": "TEntry", "TCombobox": "TCombobox", "TSpinbox": "TSpinbox"}
_FITTED = weakref.WeakSet()


def _class_style(w):
    cls = w.winfo_class()
    if cls == "TScrollbar":
        try:
            o = str(w.tk.call(w._w, "cget", "-orient"))
        except tk.TclError:
            o = "vertical"
        return ("Horizontal" if o.startswith("h") else "Vertical") + ".TScrollbar"
    return _DEFAULT.get(cls, cls)


def behind(w):
    """The color behind a widget: its parent's background (a ttk parent: its style's)."""
    m = w.master
    if m is None:
        return None
    try:
        return str(m.tk.call(m._w, "cget", "-background"))
    except tk.TclError:
        pass
    try:
        st = str(m.tk.call(m._w, "cget", "-style")) or m.winfo_class()
        return str(m.tk.call("ttk::style", "lookup", st, "-background")) or None
    except tk.TclError:
        return None


def _over_game(w):
    try:
        from .overlaywin import OverlayWindow
        return isinstance(w.winfo_toplevel(), OverlayWindow)
    except Exception:
        return False


def _square(w, base):
    """Over the game the fields keep their old square look (the overlay's styles are left alone; rule 24 gives
    them only the thin scroll bar): Sq.<style>, with the clam theme's own layout."""
    cls = w.winfo_class()
    lay = (tk_cache(w).get("clam") or {}).get(cls)
    if not lay:
        return None
    name = "Sq." + base
    made = tk_cache(w).setdefault("square", set())
    if name not in made:
        ttk.Style(w).layout(name, lay)
        made.add(name)
    return name


def fit(w):
    """Give a ttk button / field / scroll bar the style for the color behind it (its round corners laid on it)."""
    if pil() is None:
        return
    try:
        own = w.__dict__.get("_soe2_style")
        base = own or _class_style(w)
        if w.winfo_class() in ("TEntry", "TCombobox", "TSpinbox") and _over_game(w):
            want = _square(w, base) or own or ""
        else:
            bg = rgb(w, behind(w))
            want = (variant(w, base, bg) if bg is not None else None) or own or ""
        if str(w.tk.call(w._w, "cget", "-style")) != want:
            w.tk.call(w._w, "configure", "-style", want)
        _FITTED.add(w)
    except tk.TclError:
        pass
    except Exception:
        buglog.caught()


def refit_all(root=None):
    """After a theme change (new pictures, and new colors behind every widget): each one fitted again."""
    for w in list(_FITTED):
        try:
            if w.winfo_exists():
                fit(w)
        except tk.TclError:
            pass


def _wrap_ttk():
    """ttk.Button / Entry / Combobox / Spinbox / Scrollbar: fitted when made, when their style changes and when shown
    (cget('style') still says the style the code gave)."""
    for cls in (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Spinbox, ttk.Scrollbar):
        if cls.__dict__.get("_soe2_fit"):
            continue
        _wrap_one(cls)


def _wrap_one(cls):
    o_init = cls.__init__
    o_conf = cls.configure
    o_cget = cls.cget

    def __init__(self, master=None, *a, **kw):
        o_init(self, master, *a, **kw)
        self.__dict__["_soe2_style"] = kw.get("style") or ""
        fit(self)
        try:
            self.bind("<Map>", lambda e, s=self: fit(s) if e.widget is s else None, add="+")
        except tk.TclError:
            pass

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict) and "style" in cnf:
            cnf = dict(cnf)
            kw["style"] = cnf.pop("style")
        if "style" in kw:
            self.__dict__["_soe2_style"] = kw["style"] or ""
            res = o_conf(self, cnf, **kw)
            fit(self)
            return res
        return o_conf(self, cnf, **kw)

    def cget(self, key):
        if key in ("style", "-style") and "_soe2_style" in self.__dict__:
            return self.__dict__["_soe2_style"]
        return o_cget(self, key)

    cls.__init__ = __init__
    cls.configure = cls.config = configure
    cls.cget = cls.__getitem__ = cget
    cls._soe2_fit = True


# ------------------------------------------------------------------ tk frames: corner caps
CAP_MIN_PAD = RADIUS            # a frame padded at least this much has its corners free: they can be capped
_CAPPED = weakref.WeakSet()


def _cap_pic(root, r, outside, inside, edge, which):
    """One opaque corner (r x r): outside the curve = outside; the curve = edge (or none); inside = inside (one color
    or a color per row from the top)."""
    rows = inside if isinstance(inside, (list, tuple)) and inside and isinstance(inside[0], tuple) else None
    S = 2 * r + 1

    def make():
        rr = None
        if rows:
            rr = list(rows[:r]) + [rows[min(len(rows) - 1, r)]] * (S - r)
        st = shape(S, S, r, fill=None if rows else inside, outline=edge, ow=1 if edge else 0, rows=rr, under=outside)
        box = {"tl": (0, 0, r, r), "tr": (r + 1, 0, S, r), "bl": (0, r + 1, r, S), "br": (r + 1, r + 1, S, S)}[which]
        return st.crop(box)
    key = ("cap", r, outside, tuple(rows) if rows else inside, edge, which)
    return photo(root, key, make)


def round_frame(f, r=RADIUS, inside=None, top=None, edge=None, outside=None, corners=("tl", "tr", "bl", "br")):
    """Round a tk frame's corners with small caps (placed, so a resize costs nothing). inside / top / edge /
    outside: colors or functions giving them (None: the frame's own bg / its bg / its border if it has one / the
    color behind it). top: the inside of the two top corners (a header strip there). corners: which ones. -> f."""
    if pil() is None or f.__dict__.get("_soe2_caps"):
        return f
    caps = {}
    for which in corners:
        lab = tk.Label(f, bd=0, highlightthickness=0, padx=0, pady=0, width=r, height=r, takefocus=0)
        lab.__dict__["_soe2_cap"] = True                 # (not one of the page's children: winfo_children skips it)
        caps[which] = lab
    f.__dict__["_soe2_caps"] = caps
    f.__dict__["_soe2_capspec"] = (r, inside, top, edge, outside)
    _place_caps(f)
    _CAPPED.add(f)
    paint_caps(f)
    f.bind("<Map>", lambda e: _lift_caps(f) if e.widget is f else None, add="+")
    return f


def _place_caps(f):
    """The caps on the frame's outer corners (place counts from inside its border and padding: step back out)."""
    caps = f.__dict__.get("_soe2_caps")
    if not caps:
        return
    try:
        g = lambda o: int(float(f.tk.call(f._w, "cget", o)))      # noqa: E731
        bd, ht = g("-bd"), g("-highlightthickness")
        L, T = bd + ht + g("-padx"), bd + ht + g("-pady")
    except (tk.TclError, ValueError):
        return
    r = f.__dict__["_soe2_capspec"][0]
    want = {"tl": dict(x=-L, y=-T), "tr": dict(relx=1, x=L - r, y=-T), "bl": dict(x=-L, rely=1, y=T - r),
            "br": dict(relx=1, x=L - r, rely=1, y=T - r)}
    if f.__dict__.get("_soe2_capsat") == (L, T):
        return
    f.__dict__["_soe2_capsat"] = (L, T)
    for which, lab in caps.items():
        try:
            lab.place(**dict({"relx": 0, "rely": 0}, **want[which]))
            lab.lift()
        except tk.TclError:
            pass


def _lift_caps(f):
    for lab in (f.__dict__.get("_soe2_caps") or {}).values():
        try:
            lab.lift()
        except tk.TclError:
            pass
    paint_caps(f)


def _val(v):
    return v() if callable(v) else v


def paint_caps(f, inside=None):
    """Paint a frame's corner caps again from its colors now (inside: {'tl': color ...} for this time)."""
    caps = f.__dict__.get("_soe2_caps")
    if not caps:
        return
    if inside is not None:
        f.__dict__["_soe2_capinside"] = inside
    else:
        inside = f.__dict__.get("_soe2_capinside")
    try:
        r, ins, top, edge, outside = f.__dict__["_soe2_capspec"]
        bg = str(f.tk.call(f._w, "cget", "-background"))
        try:
            ht = int(f.tk.call(f._w, "cget", "-highlightthickness"))
        except (tk.TclError, ValueError):
            ht = 0
        e = _val(edge) if edge is not None else (str(f.tk.call(f._w, "cget", "-highlightbackground")) if ht else None)
        out = _val(outside) or behind(f) or bg
        base = _val(ins) or bg
        tp = _val(top)
        for which, lab in caps.items():
            i = (inside or {}).get(which) or (tp if (tp and which in ("tl", "tr")) else base)
            irgb = [rgb(f, c) for c in i] if isinstance(i, (list, tuple)) else rgb(f, i)
            img = _cap_pic(f, r, rgb(f, out), irgb, rgb(f, e) if e else None, which)
            if img is not None and lab.__dict__.get("_img") is not img:
                lab.configure(image=img, bg=hexc(rgb(f, out)))
                lab.__dict__["_img"] = img
    except tk.TclError:
        pass
    except Exception:
        buglog.caught()


def _auto_caps():
    """Frames made as cards - a 1 px border or their own color, and padding that keeps the corners free - get round
    corners by themselves (every page, no page code changed). A frame's later bg / border change repaints them."""
    F = tk.Frame
    if F.__dict__.get("_soe2_caps_auto"):
        return
    o_init, o_conf = F.__init__, F.configure

    def __init__(self, master=None, cnf={}, **kw):          # noqa: B006 (tkinter's own signature)
        o_init(self, master, cnf, **kw)
        try:
            k = dict(cnf or {}, **kw)
            ht = int(k.get("highlightthickness", 0) or 0)
            px, py = k.get("padx", 0), k.get("pady", 0)
            px = min(px) if isinstance(px, (tuple, list)) else int(px or 0)
            py = min(py) if isinstance(py, (tuple, list)) else int(py or 0)
            padded = px >= CAP_MIN_PAD and py >= CAP_MIN_PAD
            if ht == 1 and "highlightbackground" in k:      # a bordered card / a search box
                want = True
            else:                                           # a card in its own color, on another
                bg = behind(self) if master is not None else None
                want = px >= 12 and py >= 8 and "bg" in k and bg and rgb(self, bg) != rgb(self, k["bg"])
            if want:                                        # (decided once it is shown: see _maybe_caps)
                self.bind("<Map>", lambda e, s=self, p=padded: _maybe_caps(s, p) if e.widget is s else None,
                          add="+")
        except Exception:
            buglog.caught()

    def configure(self, cnf=None, **kw):
        res = o_conf(self, cnf, **kw)
        if self.__dict__.get("_soe2_caps") and (cnf or kw):
            k = dict(cnf or {}, **kw) if isinstance(cnf, dict) or cnf is None else kw
            if {"padx", "pady", "bd", "borderwidth", "highlightthickness"} & set(k):
                _place_caps(self)
            if {"bg", "background", "highlightbackground", "highlightthickness"} & set(k):
                paint_caps(self)
        return res
    F.__init__ = __init__
    F.configure = F.config = configure
    F._soe2_caps_auto = True


def _maybe_caps(f, padded=False):
    """A card frame, once shown: capped if what is behind it shows round its corners (it sits inside its parent,
    not flush with an edge - a toast's body fills its colored frame) and no part of it sits in a corner (a padded
    frame keeps them free)."""
    if f.__dict__.get("_soe2_caps") or f.__dict__.get("_soe2_nocaps"):
        return
    try:
        W, H = f.winfo_width(), f.winfo_height()
        r = RADIUS + 1                                      # (the border, then the corner)
        m = f.master
        x, y = f.winfo_x(), f.winfo_y()
        inset = (m is not None and not isinstance(m, (tk.Tk, tk.Toplevel)) and (
            (x > 0 and y > 0 and x + W < m.winfo_width() and y + H < m.winfo_height())
            or rgb(m, behind(f)) == rgb(m, behind(m))))     # (flush, in a plain row: its color goes on round it)
        if W < 4 * r or H < 2 * r + 4 or not inset:
            f.__dict__["_soe2_nocaps"] = True
            return
        if padded:
            round_frame(f)
            return
        bg = rgb(f, f.cget("bg"))
        for ch in f.winfo_children():
            if not ch.winfo_ismapped():
                continue
            x, y, w, h = ch.winfo_x(), ch.winfo_y(), ch.winfo_width(), ch.winfo_height()
            for cx, cy in ((0, 0), (W - r, 0), (0, H - r), (W - r, H - r)):
                if x < cx + r and x + w > cx and y < cy + r and y + h > cy:
                    try:                                # (a plain part in the frame's own color may sit there)
                        same = rgb(ch, ch.cget("bg")) == bg and ch.winfo_class() in ("Frame", "Label")
                    except tk.TclError:
                        same = False
                    if not same:
                        f.__dict__["_soe2_nocaps"] = True
                        return
        round_frame(f)
    except tk.TclError:
        pass


def repaint_all():
    """After a theme change: every capped frame's corners in the new colors."""
    for f in list(_CAPPED):
        try:
            if f.winfo_exists():
                paint_caps(f)
        except tk.TclError:
            pass


def after_relook(root):
    """style.relook calls this after the theme walk: the canvases' corners, the per-background styles, the caps."""
    refit_all(root)
    repaint_all()


# ------------------------------------------------------------------ windows over the app (tooltips, toasts)
def round_window(win):
    """Windows 11: round a popup's corners (DWM, small radius). Elsewhere: nothing (Tk can't shape a window)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        pref = ctypes.c_int(3)                               # DWMWCP_ROUNDSMALL
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref)) == 0
    except Exception:
        return False


def _hide_caps():
    """winfo_children leaves the corner caps out: code that rebuilds a frame's content (destroy every child) or
    counts its parts sees only its own."""
    M = tk.Misc
    if M.__dict__.get("_soe2_caps_hidden"):
        return
    o_children = M.winfo_children

    def winfo_children(self):
        res = o_children(self)
        if _CAPPED:
            res = [w for w in res if not w.__dict__.get("_soe2_cap")]
        return res
    M.winfo_children = winfo_children
    M._soe2_caps_hidden = True


def install():
    """At start-up (style.setup_style): the canvas calls and the frame caps."""
    if pil() is None:
        return False
    _install()
    _hide_caps()
    _auto_caps()
    return True
