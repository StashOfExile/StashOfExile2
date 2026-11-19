"""The settings gear (UI overhaul: the ⚙ glyph rendered like a flower). Windows draws U+2699 from its emoji
font, a petalled shape at small sizes - so the gear is drawn here instead: eight flat teeth round a ring, smoothed
(drawn four times bigger, then made small), in the color it's given - the theme's text color (C["text"] / the
overlay's muted text), so it follows every theme and overlay style. Used by the sidebar's Settings row, the overlay's
Quick settings button, the price check card's Card settings and Price Checks' settings button; each keeps its
tooltip (an icon-only button always has one).

image(master, size, color) -> a PhotoImage (transparent around the gear), cached per size and color.
draw(canvas, x, y, size, color, anchor, tags) -> the canvas item (its picture is kept on the canvas)."""
import math

GEAR = "gear"                       # (the title bar's extra buttons: this icon is drawn, not written)
TEETH = 8
_CACHE = {}


def outline(cx, cy, r, teeth=TEETH):
    """The gear's edge as [(x, y)]: flat-topped teeth (r) on a body (0.74 r)."""
    root, p = r * 0.74, 2 * math.pi / teeth
    top, base = p * 0.17, p * 0.27              # half-widths of a tooth at its top and at the body
    pts = []
    for i in range(teeth):
        a = i * p - math.pi / 2
        for ang, rad in ((a - base, root), (a - top, r), (a + top, r), (a + base, root), (a + p / 2, root * 0.98)):
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def hole(r):
    return r * 0.34


def _rgb(master, color):
    try:
        r, g, b = (v >> 8 for v in master.winfo_rgb(color))
        return r, g, b
    except Exception:
        c = str(color).lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if len(c) == 6 else (200, 200, 200)


def image(master, size, color):
    """A size x size picture of the gear in color (transparent around it), or None without Pillow."""
    size = max(8, int(size))
    rgb = _rgb(master, color)
    key = (id(getattr(master, "tk", None)), str(master.winfo_toplevel()) if hasattr(master, "winfo_toplevel") else "",
           size, rgb)                         # (3.0.6: and its Tk - a picture belongs to the Tk that made it)
    got = _CACHE.get(key)
    if got is not None:
        return got
    try:
        from PIL import Image, ImageDraw, ImageTk
    except Exception:
        return None
    k = 4
    big = size * k
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    c, r = big / 2, big / 2 - k * 0.5
    d.polygon(outline(c, c, r), fill=255)
    h = hole(r)
    d.ellipse((c - h, c - h, c + h, c + h), fill=0)
    mask = mask.resize((size, size), Image.LANCZOS)
    pic = Image.new("RGBA", (size, size), rgb + (0,))
    pic.putalpha(mask)
    try:
        img = ImageTk.PhotoImage(pic, master=master)
    except Exception:
        return None
    _CACHE[key] = img
    return img


def draw(cv, x, y, size, color, anchor="center", tags=()):
    """The gear on a canvas at (x, y). -> its item. Without Pillow: the same shape as a polygon and a ring."""
    img = image(cv, size, color)
    if img is not None:
        keep = getattr(cv, "_gear_imgs", None)
        if keep is None:
            keep = cv._gear_imgs = []
        if img not in keep:
            keep.append(img)
        return cv.create_image(x, y, image=img, anchor=anchor, tags=tags)
    r = size / 2
    dx = {"e": -r, "w": r}.get(anchor[-1:] if anchor in ("e", "w", "ne", "nw", "se", "sw") else "", 0)
    cx, cy = x + dx, y
    item = cv.create_polygon([v for pt in outline(cx, cy, r) for v in pt], fill=color, outline=color, tags=tags)
    h = hole(r)
    cv.create_oval(cx - h, cy - h, cx + h, cy + h, fill=cv.cget("bg"), outline="", tags=tags)
    return item


def label(parent, size=14, color=None, **kw):
    """A tk.Label showing the gear in the theme's text color (C["text"], or color() when given) - painted again after
    a theme change. kw: the Label's other options (bg, cursor ...). The caller adds its tooltip."""
    import tkinter as tk
    from .style import C

    def col():
        return color() if callable(color) else (color or C["text"])
    img = image(parent, size, col())
    lbl = tk.Label(parent, image=img, **kw) if img is not None else tk.Label(parent, text="Settings", **kw)
    lbl._gear_img = img

    def repaint(_theme=None):
        new = image(lbl, size, col())
        if new is not None:
            lbl.configure(image=new)
            lbl._gear_img = new
    try:
        from . import themes
        themes.subscribe(repaint, lbl)
    except Exception:
        pass
    return lbl
