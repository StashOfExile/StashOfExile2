"""Colors, fonts and widget styles.

Part of StashOfExile2. Split out of the single-file app in 1.37 (see the launcher's VERSION HISTORY)."""

import sys
import re
import tkinter as tk
from tkinter import ttk

from . import buglog


# ------------------------------------------------------------------ look and feel
C = {   # Xfire-style steel blue and navy, with orange for actions and gold for money (a nod to the game's UI)
    "bg": "#090e17", "panel": "#0e1522", "panel2": "#131c2e", "line": "#2b3d5f", "gold_dim": "#3d5582",
    "steel": "#8fa3c7", "text": "#dbe4f2", "muted": "#7d8da8", "accent": "#ffa63d", "good": "#ffd25a",
    "green": "#5fd38a", "red": "#ff6b5e", "blue": "#6aa6ff", "purple": "#b794f6", "orange": "#ff9d3a",
    "rare": "#ffff77", "magic": "#8f9bff", "sel": "#1b4a96", "odd": "#0b111c", "stripe": "#16213a", "key": "#26354f",
    "warn_bg": "#2a2110", "bad_bg": "#34171a", "ok_bg": "#10281c",
}

# 2.97.2 (feedback: visual hierarchy, as the game and the trade site show them): a mod's color says where it comes from.
MOD_COL = {"explicit": "#8f9bff", "rune": "#9fd8ff", "implicit": "#9fd8ff", "enchant": "#b8daf2",
           "fractured": "#d9b871", "desecrated": "#a8d65c", "pseudo": "#e07ce0"}
_BASE = dict(C)                       # (as shipped - tools/check_contrast.py starts each theme from it)


# ------------------------------------------------------------------ design tokens (2.34.0, Polish 1)
# Every new widget uses these. tools/check_tokens.py (CI + test) keeps the code on them.
SPACE = (4, 8, 12, 16, 24)            # padding / gaps; 0-2 are allowed too, for hairlines and joined edges
XS, S_, M, L, XL = SPACE
SMALL, BODY, HEAD, TITLE = 9, 10, 12, 16     # the four text sizes: notes / chips, normal, section heads, window titles
DISPLAY = (18, 20, 22, 28)            # not text: icon glyphs and the big numbers (timer, totals)
ROLE = {                              # color roles -> which C color plays them
    "surface": "bg", "surface_raised": "panel", "surface_high": "panel2", "border": "line",
    "text": "text", "text_muted": "muted", "primary": "accent", "money": "good",
    "success": "green", "danger": "red", "info": "blue", "selected": "sel",
}


TRADE_SITE = "Trade Site"      # 3.0.6 (owner): every Trade Site button carries the same browser (globe) icon


def trade_icon(btn, color=None, size=16):
    """A Trade Site button (ttk.Button or tk.Label) -> the same button with the globe icon after its words. 3.0.6
    (owner: on the right side, centered alongside the text): the icon is drawn 2 px lower in its picture, so its
    middle sits on the words' middle, not above it."""
    try:
        from . import lineicons
        from PIL import Image, ImageTk
        key = ("trade", int(size), str(color or C["text"]).lower())
        img = _TRADE_IMG.get(key)
        if img is None:
            im = lineicons.image("globe", int(size), str(color or C["text"]))
            pad = Image.new("RGBA", (im.width, im.height + 3), (0, 0, 0, 0))
            pad.alpha_composite(im, (0, 3))
            img = _TRADE_IMG[key] = ImageTk.PhotoImage(pad, master=btn)
        btn.configure(image=img, compound="right")
    except Exception:
        buglog.caught()
    return btn


_TRADE_IMG = {}


def role(name):
    """The color for a role (follows the theme and accent)."""
    return C[ROLE[name]]


FONT_TITLE = "Palatino Linotype"      # a serif close to the game's Fontin; falls back automatically if missing


FLAG_COLORS = {"crafted": C["blue"], "desecrated": C["purple"], "fractured": C["orange"], "essence": C["green"]}


MONO = "Consolas"


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    """Color between a and b ('#rrggbb'), t from 0 (a) to 1 (b)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * max(0, min(1, t))) for x, y in zip(ra, rb))


def contrast(a, b):
    """WCAG contrast ratio of two '#rrggbb' colors (1 to 21)."""
    def lum(c):
        r, g, b_ = (v / 255 for v in _rgb(c))
        f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b_)
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(bg, light="#fff7ea", dark="#1a1206"):
    """2.34.0: light or dark text, whichever reads better on bg (WCAG AA)."""
    return light if contrast(light, bg) >= contrast(dark, bg) else dark


# Rate Mods (owner): one letter palette, here only - S gold, A orange, B / C / D cool to neutral, F muted. Each letter
# is a theme role (so it follows every theme pack), nudged toward the theme's text until it stands out 3 : 1 from the
# surface it sits on (tools/check_contrast.py checks it). Always shown with its letter and its word, never alone.
LETTER_ROLES = {"S": "money", "A": "orange", "B": "link", "C": ("link", "text_muted"), "D": ("text", "text_muted"),
                "F": "text_muted"}
LETTER_EDGE = 3.0


def letter_color(g, under=None):
    """The color strip of a letter (S A B C D F; "ignore" = F) on `under` (default: the theme's raised surface)."""
    from . import themes as TH
    t = TH.ST.theme
    g = "F" if g == "ignore" else g
    role = LETTER_ROLES.get(g, "text_muted")
    with TH.raw():
        base = mix(t.c(role[0]), t.c(role[1]), 0.5) if isinstance(role, tuple) else t.c(role)
        under = under or t.c("surface_raised")
        ink = t.c("text")
    c = base
    for i in range(1, 11):
        if contrast(c, under) >= LETTER_EDGE:
            break
        c = mix(base, ink, i / 10)
    return c


def hotkey_blocked(state, platform=None):
    """True when Ctrl or Alt is held. On Windows bit 0x8 is NUM LOCK, not Alt (Alt is 0x20000): treating it as Alt made every
    shortcut key dead whenever Num Lock was on. On Linux/Mac bit 0x8 is Alt."""
    win = (platform or sys.platform) == "win32"
    return bool(state & 0x4 or state & (0x20000 if win else 0x8))


class Plate(tk.Canvas):
    """A glossy steel bar (like Xfire's window frame): a gradient with a bright top edge and a darker lower half.
    Things are drawn on it with create_text / create_window, so they sit on the gradient without a box around them."""

    def __init__(self, master, height, top="#3f64a0", mid="#2a4a7c", low="#1c3360", bottom="#13233f", edge="#86a9de", **kw):
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=bottom, **kw)
        self.colors, self.on_resize = (top, mid, low, bottom, edge), None
        self.bind("<Configure>", self._redraw)

    def _redraw(self, e=None):
        w, h = self.winfo_width(), int(float(self.cget("height")))
        top, mid, low, bottom, edge = self.colors
        self.delete("plate")
        half = h // 2
        for y in range(h):
            col = mix(top, mid, y / max(1, half)) if y < half else mix(low, bottom, (y - half) / max(1, h - half))
            self.create_line(0, y, w, y, fill=col, tags="plate")
        self.create_line(0, 0, w, 0, fill=edge, tags="plate")                      # bright top edge
        self.create_line(0, h - 1, w, h - 1, fill="#070b13", tags="plate")         # dark bottom edge
        self.tag_lower("plate")
        if self.on_resize:
            self.on_resize(w, h)


_SWITCH = {}
SWITCH_LOOK = ["onoff"]           # drawer build: "seg" = the Drawer's switch (mockups.html .sw: ✓ On | Off, no orange)


_MONO = {}
_SANS = {}


def _sans_font(size):
    """The UI font for the Drawer's switch words (Segoe UI on Windows, DejaVu Sans on Linux), else Pillow's own."""
    if size in _SANS:
        return _SANS[size]
    from PIL import ImageFont
    f = None
    for name in ("segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            f = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    _SANS[size] = f or _mono_font(size)
    return _SANS[size]


def _lum(c):
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4    # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ink_on(fill):
    """The darker or lighter of the theme's own background / text that reads best on this fill."""
    try:
        a, b = C["bg"], C["text"]
        la, lb, lf = _lum(a), _lum(b), _lum(fill)
        ca = (max(la, lf) + .05) / (min(la, lf) + .05)
        cb = (max(lb, lf) + .05) / (min(lb, lf) + .05)
        return a if ca >= cb else b
    except Exception:
        return "#000000"


def _seg_switch_img(root, on, hover=False, disabled=False, w=68, h=24, gap=8):
    """drawer build (mockups.html .sw): the switch in the Drawer - a box split in two, "✓ On | Off"; the chosen half
    is lifted and says it with a mark (✓ / ○) and a word, the other half is dim. Round 18 (feedback: the themes lost
    their flair): a lit On is the theme's accent, as the Full window's switch - the mark and the word say it too."""
    from PIL import Image, ImageDraw, ImageTk
    from . import lineicons
    lift = C.get("key") or C["panel2"]
    face = C.get("odd") or C["panel2"]
    edge = C["line"] if not hover or disabled else C["muted"]
    dim = mix(C["muted"], face, 0.35)
    alpha = 110 if disabled else 255

    def rgba(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)
    k = 2                                                   # drawn twice the size, then scaled down (smooth text)
    im = Image.new("RGBA", ((w + gap) * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    half = w * k // 2
    f = _sans_font(10 * k)
    for i, (word, lit) in enumerate((("On", on), ("Off", not on))):
        x0 = i * half
        hot = lit and i == 0
        d.rectangle((x0, 0, x0 + half - 1, h * k - 1), fill=rgba(C["accent"] if hot else lift if lit else face))
        fg = _ink_on(C["accent"]) if hot else C["text"] if lit else dim
        mark = ("check" if i == 0 else "circle") if lit else None
        l, t_, r, b = d.textbbox((0, 0), word, font=f)
        tw, th = r - l, b - t_
        mw = 9 * k if mark else 0
        x = x0 + (half - tw - mw - (3 * k if mark else 0)) // 2
        if mark:
            ic = lineicons.image(mark, mw, fg, stroke=2.4)
            if alpha != 255:
                ic.putalpha(ic.getchannel("A").point(lambda a: a * alpha // 255))
            im.alpha_composite(ic, (int(x), (h * k - mw) // 2))
            x += mw + 3 * k
        d.text((x - l, (h * k - th) // 2 - t_), word, font=f, fill=rgba(fg))
    d.line((half, 0, half, h * k), fill=rgba(C["line"]), width=k)
    d.rectangle((0, 0, w * k - 1, h * k - 1), outline=rgba(edge), width=k)
    return ImageTk.PhotoImage(im.resize((w + gap, h), Image.LANCZOS), master=root)


def _mono_font(size):
    """A bold monospace font for ON / OFF (Consolas on Windows, DejaVu Sans Mono on Linux), else Pillow's own."""
    if size in _MONO:
        return _MONO[size]
    from PIL import ImageFont
    f = None
    for name in ("consolab.ttf", "consola.ttf", "DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"):
        try:
            f = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except Exception:
            f = ImageFont.load_default()
    _MONO[size] = f
    return f


def _switch_img(root, on, hover=False, disabled=False, w=68, h=24, gap=8):
    """P2.5 (2.107.0, picked: B - segmented): one picture of the switch - a 68 x 24 box split in two, ON | OFF; the
    chosen half is lit (ON: the accent; OFF: a raised face). Straight edges, drawn 1:1 so they stay crisp; the
    words in a monospace font. Pillow; without it a plain Tk drawing."""
    if SWITCH_LOOK[0] == "seg":
        try:
            return _seg_switch_img(root, on, hover, disabled)
        except Exception:
            buglog.caught()
    acc, sunk = C["accent"], C.get("odd") or C["panel2"]
    edge = mix(C["line"], C["text"], 0.18) if not hover or disabled else acc
    off_face = mix(sunk, C["text"], 0.28)
    on_text = text_on(acc)
    words = (("ON", acc if on else sunk, on_text if on else C["muted"]),
             ("OFF", sunk if on else off_face, C["muted"] if on else C["text"]))
    alpha = 110 if disabled else 255
    try:
        from PIL import Image, ImageDraw, ImageTk

        def rgba(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)
        im = Image.new("RGBA", (w + gap, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        half = w // 2
        f = _mono_font(10)
        for i, (word, bg, fg) in enumerate(words):
            x0 = i * half
            d.rectangle((x0, 0, x0 + half - (0 if i else 1), h - 1), fill=rgba(bg))
            try:
                l, t_, r, b = d.textbbox((0, 0), word, font=f)
                tw, th = r - l, b - t_
                d.text((x0 + (half - tw) // 2 - l, (h - th) // 2 - t_), word, font=f, fill=rgba(fg))
            except Exception:
                d.text((x0 + 6, 6), word, fill=rgba(fg))
        d.rectangle((0, 0, w - 1, h - 1), outline=rgba(edge))
        return ImageTk.PhotoImage(im, master=root)
    except Exception:
        img = tk.PhotoImage(master=root, width=w + gap, height=h)
        img.put(words[0][1], to=(0, 0, w // 2, h))
        img.put(words[1][1], to=(w // 2, 0, w, h))
        return img


def switch_look(root, look):
    """drawer build: the switches' look - "onoff" (ON | OFF, the accent) or "seg" (the Drawer's ✓ On | Off). Every
    switch in the app follows at once (the same ttk element, laid out again)."""
    if SWITCH_LOOK[0] == look:
        return
    SWITCH_LOOK[0] = look
    try:
        from tkinter import ttk as _ttk
        switches(root, _ttk.Style(root))
    except Exception:
        buglog.caught()


def switches(root, s):
    """2.49.0 (feedback: a modern slider in place of every checkbox): every ttk.Checkbutton
    (TCheckbutton and its Bar. / Mod. styles) shows a switch instead of a tick box. Same widgets, same variables."""
    name = "Switch2.indicator.%s%s" % ((C["accent"] + C["line"] + C["text"] + C["panel2"]).replace("#", ""),
                                       "" if SWITCH_LOOK[0] == "onoff" else SWITCH_LOOK[0])
    if (id(root), name) in _SWITCH:           # 2.62.0: this look's switch exists - keep ITS pictures (making new
        imgs = None                           # ones here freed the old ones: switches went blank after a swap back)
    else:
        imgs = {(on, hv, ds): _switch_img(root, on, hv, ds) for on in (0, 1) for hv in (0, 1) for ds in (0, 1)}
        _SWITCH[(id(root), name)] = imgs      # (kept, or Tk drops the pictures)
    try:
        if imgs is None:
            raise tk.TclError("exists")
        s.element_create(name, "image", imgs[(0, 0, 0)],
                         ("disabled", "selected", imgs[(1, 0, 1)]), ("disabled", imgs[(0, 0, 1)]),
                         ("active", "selected", imgs[(1, 1, 0)]), ("selected", imgs[(1, 0, 0)]),
                         ("active", imgs[(0, 1, 0)]), sticky="w")
    except tk.TclError:
        pass                                  # (already made for this look - 2.60.0: still lay it out again)
    layout = [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (name, {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]})]})]
    for name in ("TCheckbutton", "Bar.TCheckbutton", "Mod.TCheckbutton", "Card.TCheckbutton"):
        s.layout(name, layout)
        s.configure(name, padding=(0, 2))


# ---------------------------------------------------------------- 2.98.0: responsive (decided 2026-11-05: everything
# drawn to a width redraws when the window changes size - the default for the whole app)
def _fills_x(w):
    """Does this widget get the width its parent gives it (pack fill x / both, grid sticky e+w, place relwidth)?"""
    try:
        mgr = w.winfo_manager()
        if mgr == "pack":
            return w.pack_info().get("fill") in ("x", "both")
        if mgr == "grid":
            st = str(w.grid_info().get("sticky", ""))
            return "e" in st and "w" in st
        if mgr == "place":
            return bool(w.place_info().get("relwidth"))
    except Exception:
        buglog.caught()
    return False


def _rewrap(e):
    """A wrapped label that fills its row re-wraps to the width it has (was a fixed wraplength, cut off or
    leaving a gap when the window changed size). Labels with their own <Configure> rule keep it."""
    w = e.widget
    try:
        wl = int(float(str(w.cget("wraplength")) or 0))
    except Exception:
        return
    if wl <= 0 or w.bind("<Configure>") or not _fills_x(w):
        return
    try:
        pad = int(float(str(w.cget("padx")) or 0)) * 2
    except Exception:
        pad = 0
    new = max(120, e.width - pad - 4)
    squeezed = e.width < w.winfo_reqwidth() - 1          # its parent gives it less than it asks for
    if (new > wl + 6) or (squeezed and new < wl - 6):     # (a window that sizes to its text never shrinks it)
        try:
            w.configure(wraplength=new)
        except Exception:
            buglog.caught()


def center_over(win, parent):
    """2.98.3: put a dialog in the middle of `parent` (the app), kept on the monitor the app is on - never pushed to
    the main monitor (feedback: Privacy & community's questions opened on the other screen)."""
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    try:
        px, py, pw, ph = parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height()
    except tk.TclError:
        px, py, pw, ph = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()
    cx, cy = px + pw // 2, py + ph // 2
    l, t, r, b = monitor_rect(parent, cx, cy)
    x = max(l, min(cx - w // 2, r - w))
    y = max(t, min(cy - h // 2, b - h))
    win.geometry(f"+{x}+{y}")
    return x, y


def over_app(win, parent):
    """2.114.3 (feedback: the Scan stash check window came up on the wrong screen - it should always appear over the
    app): center a window over `parent` (the app window in front) on its monitor once its content is built."""
    def go():
        try:
            if win.winfo_exists():
                center_over(win, parent)
        except tk.TclError:
            pass
    win.after_idle(go)
    return win


def _place_dialog(w, parent=None):
    """tkinter.simpledialog's own placement kept dialogs inside the MAIN monitor (it clamps to winfo_vroot*, which
    on Windows is the main monitor) - so on two screens they opened on the other one. Over the app instead."""
    w.wm_withdraw()
    w.update_idletasks()
    par = parent if parent is not None and parent.winfo_ismapped() else w._root()
    center_over(w, par)
    w.wm_deiconify()


def bind_own_configure(root, fn):
    """3.0.6 (owner: dragging the Drawer lagged on every page except Dashboard ): a handler
    for the app window's own size / place. root.bind("<Configure>") runs for EVERY part inside the window too (each
    part's events pass its window's tag) - five such handlers meant five Python calls for each of the ~1,800 parts
    of a page, on every step of a drag. Dashboard is one drawing, so it never had that cost. This tag is the root's
    alone: the handler runs once a step."""
    tag = "SoE2Root"
    tags = root.bindtags()
    if tag not in tags:
        root.bindtags((tag,) + tuple(tags))
    root.bind_class(tag, "<Configure>", fn, add="+")


LOOP_LIMIT = 150                  # one widget resized this many times within a second = stuck in a layout loop
_LW = {"t": 0.0, "n": {}, "told": False, "size": {}}


def _layout_watch(e):
    """2.117.1: a widget resized LOOP_LIMIT times within a second is stuck laying itself out again and again (two
    parts that each resize when the other does - how a theme's font sizes can freeze the app). The first one is
    written to the app's log once a run: the widget's place in the window and its kind - no text from it."""
    if _LW["told"]:
        return
    try:
        import time as _t
        now = _t.monotonic()
        if now - _LW["t"] > 1.0:
            _LW["t"], _LW["n"] = now, {}
        k = str(e.widget)
        size = (e.width, e.height)                   # 2.124.1: a size change only - dragging a window moves it on
        if _LW["size"].get(k) == size:               # every mouse step, and that isn't a loop
            return
        _LW["size"][k] = size
        n = _LW["n"][k] = _LW["n"].get(k, 0) + 1
        if n < LOOP_LIMIT:
            return
        _LW["told"] = True
        kinds, w = [], e.widget
        while isinstance(w, tk.Misc) and len(kinds) < 8:
            try:
                kinds.append(w.winfo_class())
            except tk.TclError:
                break
            w = w.master
        buglog.record("freeze", "layout loop: a part of a window keeps resizing",
                      detail=f"{k}\n  kinds: {' < '.join(kinds)}\n  size now: {e.width}x{e.height}\n"
                             f"  theme: {getattr(getattr(_themes.ST, 'theme', None), 'id', '?')}")
    except Exception:
        buglog.caught()


def responsive(root):
    """Once, at start: every wrapped Label / ttk Label in the app re-wraps to its width (see _rewrap); 2.98.3: the
    simple question dialogs (askstring / askinteger) open over the app, on its monitor. 2.117.1: a layout loop is
    logged (_layout_watch)."""
    for cls in ("Label", "TLabel"):
        root.bind_class(cls, "<Configure>", _rewrap, add="+")
    root.bind_all("<Configure>", _layout_watch, add="+")
    try:
        import tkinter.simpledialog as _sd
        _sd._place_window = _place_dialog
    except Exception:
        buglog.caught()


def fit(widget, fn, min_delta=12, delay=150):
    """Call fn() again (debounced) whenever widget's width changes by min_delta or more - for anything drawn to a
    width (a canvas card, a chart, a list of cards). The first size it gets doesn't count (it was drawn for it)."""
    st = {"w": 0, "after": None}

    def cfg(e):
        if abs(e.width - st["w"]) < min_delta:
            return
        first = not st["w"]
        st["w"] = e.width
        if first:
            return
        if st["after"] is not None:
            try:
                widget.after_cancel(st["after"])
            except Exception:
                buglog.caught()

        def go():
            st["after"] = None
            try:
                fn()
            except Exception:
                buglog.caught()
        st["after"] = widget.after(delay, go)
    widget.bind("<Configure>", cfg, add="+")
    return st


def _pads(v):
    """pack's padx -> (left, right). 2.103.2: Tk hands a pair back as a tuple, (12, 0) - it was read as no padding,
    so every row made with flowify lost its gaps (Clear filters touched Order added)."""
    if isinstance(v, (tuple, list)):
        parts = [int(float(str(x))) for x in v]
    else:
        parts = [int(float(x)) for x in re.findall(r"-?\d+(?:\.\d+)?", str(v))]
    return (parts[0], parts[-1]) if parts else (0, 0)


def autowrap(label, pad=0, minw=160):
    """D3: a label that wraps to the width it is given (fill="x", or a grid cell that stretches) instead of being cut
    off at Drawer width. Returns the label."""
    def cfg(e):
        w = max(minw, e.width - pad)
        try:
            if abs(int(str(label.cget("wraplength")) or 0) - w) >= 8:
                label.config(wraplength=w, justify="left")
        except tk.TclError:
            pass
    label.bind("<Configure>", cfg, add="+")
    return label


def flowify(row, vgap=6):
    """2.98.0: turn a row of side-by-side widgets (pack side=left / right) into one that wraps when the window is
    too narrow - each child keeps its order, padding, right-alignment and stretch (expand=True takes the rest of
    its line). Call it once, after the row is built. Children added later are packed as usual (not wrapped)."""
    kids = []
    for w in row.pack_slaves():
        info = w.pack_info()
        l, r = _pads(info.get("padx", 0))
        kids.append({"w": w, "right": info.get("side") == "right", "l": l, "r": r, "hidden": False,
                     "grow": bool(int(info.get("expand", 0) or 0)) and info.get("fill") in ("x", "both")})
    if not kids:
        return row
    try:
        row.pack_propagate(False)
    except tk.TclError:
        pass
    lefts = [k for k in kids if not k["right"]]
    rights = list(reversed([k for k in kids if k["right"]]))      # (pack draws right-side ones outside in)
    for k in kids:
        k["w"].pack_forget()
    state = {"w": 0, "busy": False}

    def width(k):
        return k["l"] + k["w"].winfo_reqwidth() + k["r"]

    def layout(_e=None):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            try:
                px = int(float(str(row.cget("padx") or 0)))
                py = int(float(str(row.cget("pady") or 0)))
            except Exception:
                px = py = 0
            W = row.winfo_width() - 2 * px
            if W <= 1 - 2 * px:
                W = sum(width(k) for k in kids)
            lines, cur, x = [], [], 0
            for k in kids:
                if k["hidden"]:
                    k["w"].place_forget()
            seq = [k for k in lefts + rights if not k["hidden"]]
            rw = sum(width(k) for k in rights if not k["hidden"])
            for k in seq:
                kw = width(k)
                room = W - (rw if (not lines and k in lefts) else 0)
                if cur and x + kw > room and not (k in rights and not lines and x + rw <= W):
                    lines.append(cur)
                    cur, x = [], 0
                cur.append(k)
                x += kw - (k["l"] if lines and len(cur) == 1 else 0)    # (a wrapped line starts at the edge)
            if cur:
                lines.append(cur)
            y = 0
            for li, line in enumerate(lines):
                h = max(k["w"].winfo_reqheight() for k in line)
                ls = [k for k in line if k in lefts]
                rs = [k for k in line if k in rights]
                used = sum(width(k) for k in line)
                grow = [k for k in ls if k["grow"]]
                extra = max(0, W - used) // len(grow) if grow else 0
                x = 0
                for i, k in enumerate(ls):
                    ww = k["w"].winfo_reqwidth() + (extra if k in grow else 0)
                    lp = 0 if li and not i else k["l"]  # 3.0.7 (owner): a wrapped line lines up with the first
                    k["w"].place(x=px + x + lp, y=py + y + (h - k["w"].winfo_reqheight()) // 2, width=ww)
                    x += lp + ww + k["r"]
                rx = max(x, W - sum(width(k) for k in rs))      # right-aligned, in their on-screen order
                for k in rs:
                    ww = k["w"].winfo_reqwidth()
                    k["w"].place(x=px + rx + k["l"], y=py + y + (h - k["w"].winfo_reqheight()) // 2, width=ww)
                    rx += k["l"] + ww + k["r"]
                y += h + (vgap if li < len(lines) - 1 else 0)
            if int(row.cget("height") or 0) != y + 2 * py:
                row.configure(height=y + 2 * py)
        finally:
            state["busy"] = False

    def cfg(e):
        if e.widget is row and e.width != state["w"]:
            state["w"] = e.width
            layout()
    row.bind("<Configure>", cfg, add="+")
    for k in kids:
        k["w"].bind("<Configure>", lambda e: row.after_idle(layout), add="+")
    row.after_idle(layout)
    row._flow_layout = layout
    row._flow_kids = kids
    row._flow_lefts = lefts
    return row


def flow_add(row, w, padx=(0, 0), shown=True):
    """Add a widget to a flowify'd row, after its other left-side widgets (e.g. one that shows only sometimes)."""
    l, r = (padx, padx) if isinstance(padx, int) else padx
    k = {"w": w, "right": False, "l": l, "r": r, "hidden": not shown, "grow": False}
    row._flow_kids.append(k)
    row._flow_lefts.append(k)
    w.bind("<Configure>", lambda e: row.after_idle(row._flow_layout), add="+")
    row.after_idle(row._flow_layout)
    return w


def flow_show(row, w, on):
    """Show / hide one widget of a flowify'd row (instead of pack / pack_forget)."""
    for k in getattr(row, "_flow_kids", ()):
        if k["w"] is w:
            k["hidden"] = not on
    lay = getattr(row, "_flow_layout", None)
    if lay is not None:
        lay()


def _combo_on_top():
    """2.112.0: every dropdown's list opens above "always on top" windows (Quick settings over the game was one):
    without it the list opened behind the box and the click picked an item blind. Wraps ttk.Combobox once."""
    if getattr(ttk.Combobox, "_soe2_top", False):
        return
    orig = ttk.Combobox.__init__

    oconf = ttk.Combobox.configure

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict) and "postcommand" in cnf:
            cnf = dict(cnf)
            kw["postcommand"] = cnf.pop("postcommand")
        if "postcommand" in kw:                       # the page's own list refresh runs after ours
            self._soe2_user = kw.pop("postcommand")
            kw["postcommand"] = self._soe2_post
        return oconf(self, cnf, **kw)

    def _post(self):
        try:
            pd = self.tk.call("ttk::combobox::PopdownWindow", self)
            self.tk.call("wm", "attributes", pd, "-topmost", 1)
        except tk.TclError:
            pass
        user = getattr(self, "_soe2_user", None)
        if callable(user):
            user()
        elif user:
            self.tk.eval(user)

    def __init__(self, master=None, **kw):
        user = kw.pop("postcommand", None)
        orig(self, master, **kw)
        self._soe2_post = self.register(lambda: _post(self))
        self._soe2_user = user
        oconf(self, postcommand=self._soe2_post)
    ttk.Combobox.__init__ = __init__
    ttk.Combobox.configure = configure
    ttk.Combobox.config = configure
    ttk.Combobox._soe2_top = True


_combo_on_top()


def _check_on_card():
    """2.112.1: a switch on a card (panel2) takes the card's color - plain ttk.Checkbuttons there showed the page's
    darker color as a box behind their text (Settings › General › Updates was one). Wraps ttk.Checkbutton once."""
    if getattr(ttk.Checkbutton, "_soe2_card", False):
        return
    orig = ttk.Checkbutton.__init__

    def __init__(self, master=None, **kw):
        if "style" not in kw and master is not None:
            try:
                if str(master.cget("bg")).lower() == str(C["panel2"]).lower():
                    kw["style"] = "Card.TCheckbutton"
            except (tk.TclError, AttributeError):
                pass
        orig(self, master, **kw)
    ttk.Checkbutton.__init__ = __init__
    ttk.Checkbutton._soe2_card = True


_check_on_card()


def setup_style(root):
    """The ttk styles, from the running theme pack (2.60.0). Called at start and again after a live theme swap."""
    from . import themes as TH
    _STYLE_LOG["quiet"] = True
    try:
        with TH.raw():                  # every color here is the running pack's already
            _setup_style(root, TH)
    finally:
        _STYLE_LOG["quiet"] = False


def _setup_style(root, TH):
    root.configure(bg=C["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")
    t = TH.ST.theme
    ns = "%s_%s" % (t.id, C["accent"].lstrip("#"))          # element names: per pack + accent (ttk can't remake one)
    s.configure(".", background=C["bg"], foreground=C["text"], fieldbackground=C["odd"],
                bordercolor=C["line"], lightcolor=C["bg"], darkcolor=C["bg"], troughcolor=C["odd"],
                focuscolor=C["accent"], focusthickness=1)       # 2.100.0: a visible focus ring (Tab) everywhere
    # ---- list headings: a bevelled face from the pack
    hh = 34
    head = ns + ".Treeheading.face"
    TH.make_element(root, s, head, t, "heading", hh, [("pressed", "p"), ("active", "h")])
    s.layout("Treeview.Heading", [(head, {"sticky": "nswe", "children": [("Treeheading.padding", {
        "sticky": "nswe", "children": [("Treeheading.image", {"side": "right", "sticky": ""}),
                                       ("Treeheading.text", {"sticky": "we"})]})]})])
    s.configure("Treeview", background=C["panel"], fieldbackground=C["panel"], foreground=C["text"],
                rowheight=30, borderwidth=0, font=("Segoe UI", 10))
    s.configure("Items.Treeview", rowheight=38)           # UI overhaul: a list with a picture per row (Wealth)
    s.map("Items.Treeview", background=[("selected", C["sel"])], foreground=[("selected", t.c("selection_text", "#ffffff"))])
    s.configure("Treeview.Heading", foreground=TH.text_of(t, "heading", "text", C["text"]),
                font=("Segoe UI", 9, "bold"), padding=(8, 8))
    sel_fg = t.c("selection_text", "#ffffff")
    s.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", sel_fg)],
          bordercolor=[("focus", C["accent"])])                  # 2.100.0: a list you Tab to shows it
    s.map("Treeview.Heading", foreground=[("active", TH.text_of(t, "heading", "text_hover", t.c("text_strong")))])
    s.configure("TNotebook", background=C["bg"], borderwidth=1, bordercolor=C["line"], lightcolor=C["bg"],
                darkcolor=C["bg"], tabmargins=(0, 8, 0, 0))
    s.configure("TNotebook.Tab", background=C["bg"], foreground=C["muted"], padding=(24, 8),
                font=("Segoe UI", 10, "bold"), borderwidth=1, bordercolor=C["bg"], lightcolor=C["bg"],
                darkcolor=C["bg"], focuscolor=C["bg"])
    s.map("TNotebook.Tab",
          background=[("selected", C["panel"]), ("active", C["panel2"])],
          foreground=[("selected", C["accent"]), ("active", C["text"])],
          bordercolor=[("selected", C["gold_dim"]), ("active", C["bg"])],
          lightcolor=[("selected", C["accent"]), ("active", C["panel2"])],
          darkcolor=[("selected", C["panel"]), ("active", C["panel2"])],
          expand=[("selected", (0, 0, 0, 0))])
    s.layout("Plain.TNotebook.Tab", [])                       # no tab strip at all - the Page dropdown replaces it
    s.configure("Plain.TNotebook", background=C["bg"], borderwidth=1, bordercolor=C["gold_dim"], lightcolor=C["bg"],
                darkcolor=C["bg"], tabmargins=(0, 0, 0, 0))
    s.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])         # same as default minus the focus ring
    nb = TH.button_spec(t, "normal")
    face_mid = TH.grad_at(t.grad(nb["fill"]), 0.5)
    field = dict(fieldbackground=C["odd"], foreground=C["text"], bordercolor=C["line"],
                 lightcolor=mix(C["odd"], "#000000", 0.4), darkcolor=C["gold_dim"], insertcolor=C["text"])
    s.configure("TCombobox", background=face_mid, arrowcolor=C["text"], padding=4, **field)
    s.map("TCombobox", fieldbackground=[("readonly", C["odd"])], foreground=[("readonly", C["text"])],
          background=[("active", TH.grad_at(t.grad(nb["hover"]), 0.5))], bordercolor=[("focus", C["accent"])])
    root.option_add("*TCombobox*Listbox.background", C["panel2"])
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["sel"])
    root.option_add("*TCombobox*Listbox.selectForeground", sel_fg)
    s.configure("TCheckbutton", background=C["bg"], foreground=C["text"], font=("Segoe UI", 10))
    s.map("TCheckbutton", background=[("active", C["bg"])])
    s.configure("Bar.TCheckbutton", background=C["panel"], foreground=C["text"], font=("Segoe UI", 10))
    s.map("Bar.TCheckbutton", background=[("active", C["panel"])])
    s.configure("Card.TCheckbutton", background=C["panel2"], foreground=C["text"], font=("Segoe UI", 10))
    s.map("Card.TCheckbutton", background=[("active", C["panel2"])])     # 2.70.1: a switch on a section's panel
    s.configure("Card.TRadiobutton", background=C["panel2"], foreground=C["text"], font=("Segoe UI", 10),
                indicatorbackground=C["panel"], indicatorforeground=C["accent"])   # 2.70.0: on a section's panel
    s.map("Card.TRadiobutton", background=[("active", C["panel2"])])
    s.configure("Mod.TCheckbutton", background=C["panel"], foreground=C["text"])
    s.map("Mod.TCheckbutton", background=[("active", C["panel"])])
    switches(root, s)                         # 2.49.0: every on / off box is a modern switch
    s.configure("TSpinbox", background=face_mid, arrowcolor=C["text"], **field)
    s.map("TSpinbox", bordercolor=[("focus", C["accent"])])
    # ---- buttons: bevelled faces drawn from the pack (gradient, light inner edge, round corners on some packs)
    bh = 34
    from . import soft                  # rule 24: round faces, laid on the color behind each button (soft.variant)
    soft.install()
    soft.tk_cache(root)["ns"] = ns
    for style_name, spec, states in (
            ("TButton", "normal", [("disabled", "d"), ("pressed", "p"), ("active", "h")]),
            ("Primary.TButton", "primary", [("disabled", "d"), ("pressed", "p"), ("active", "h")]),
            ("Danger.TButton", "danger", [("disabled", "d"), ("pressed", "p"), ("active", "h")])):
        el = "%s.%s.face" % (ns, style_name.split(".")[0] if "." in style_name else "Button")

        def face(under, el=el, spec=spec, states=states):
            name = "%s.%s" % (el, soft.hexc(under)[1:]) if under else el
            TH.make_element(root, s, name, t, spec, bh, states, under=under)
            return soft.button_layout(name)
        soft.register(root, style_name, face)
        if style_name == "Primary.TButton":
            soft.register(root, "Accent.TButton", face)
        s.layout(style_name, face(soft.rgb(root, C["bg"])))
        s.configure(style_name, focuscolor=C["accent"], focusthickness=1)     # 2.100.0: the focus ring (Tab)
    face = TH.grad_at(t.grad(TH.button_spec(t, "primary")["fill"]), 0.5)
    pri_text = TH.text_of(t, "primary", "text", text_on(face))
    s.configure("TButton", foreground=TH.text_of(t, "normal", "text", C["text"]), padding=(12, 8),
                font=("Segoe UI", 10), anchor="center")
    s.map("TButton", foreground=[("disabled", C["muted"]), ("active", TH.text_of(t, "normal", "text_hover", t.c("text_strong")))])
    s.configure("Primary.TButton", foreground=pri_text, padding=(12, 8), font=("Segoe UI", 10, "bold"), anchor="center")
    s.map("Primary.TButton", foreground=[("disabled", C["muted"]), ("active", TH.text_of(t, "primary", "text_hover", pri_text))])
    s.layout("Accent.TButton", s.layout("Primary.TButton"))   # (Accent.TButton = the old name of Primary)
    s.configure("Accent.TButton", foreground=pri_text, padding=(12, 8), font=("Segoe UI", 10, "bold"), anchor="center")
    s.map("Accent.TButton", foreground=[("disabled", C["muted"])])
    dface = TH.grad_at(t.grad(TH.button_spec(t, "danger")["fill"]), 0.5)
    s.configure("Danger.TButton", foreground=TH.text_of(t, "danger", "text", text_on(dface, "#ffe9e6")), padding=(12, 8),
                font=("Segoe UI", BODY), anchor="center")
    s.map("Danger.TButton", foreground=[("disabled", C["muted"])])
    # 2.34.0 button hierarchy: Primary (one per area), TButton = secondary, Quiet (no bevel), Danger (deletes)
    s.configure("Quiet.TButton", background=C["panel"], foreground=C["steel"], relief="flat", borderwidth=1,
                bordercolor=C["panel"], lightcolor=C["panel"], darkcolor=C["panel"], focuscolor=C["accent"],
                padding=(12, 8), font=("Segoe UI", BODY), focusthickness=1)
    s.map("Quiet.TButton", background=[("pressed", C["odd"]), ("active", C["panel2"])],
          bordercolor=[("active", C["line"])], lightcolor=[("active", C["panel2"])], darkcolor=[("active", C["panel2"])],
          foreground=[("active", C["text"]), ("disabled", C["muted"])])
    # 2.126.0: small flat buttons for a header strip (Bulk Pricing's Items strip: Undo, Delete, Clear All) - they fit
    # inside the strip; the delete ones have red words (and a word or icon, never the color alone)
    for name, fg in (("Strip.TButton", C["steel"]), ("StripDanger.TButton", C["red"]), ("StripOn.TButton", C["text"])):
        s.layout(name, [("Button.border", {"sticky": "nswe", "border": "1", "children": [("Button.focus", {
            "sticky": "nswe", "children": [("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"})]})]})]})])
        s.configure(name, background=C["panel"], foreground=fg, relief="solid", borderwidth=1, bordercolor=C["line"],
                    lightcolor=C["panel"], darkcolor=C["panel"], focuscolor=C["accent"], focusthickness=1,
                    padding=(8, 1), font=("Segoe UI", 9, "bold" if name == "StripOn.TButton" else "normal"),
                    anchor="center", width=0)   # (as wide as its words)
        s.map(name, background=[("pressed", C["odd"]), ("active", C["panel2"])],
              bordercolor=[("active", C["steel"])], lightcolor=[("active", C["panel2"])], darkcolor=[("active", C["panel2"])],
              foreground=[("disabled", C["muted"]), ("active", C["text"] if fg == C["steel"] else fg)])
    s.configure("TEntry", padding=4, **field)
    s.map("TEntry", bordercolor=[("focus", C["accent"])])
    for o in ("Vertical", "Horizontal"):
        s.configure(o + ".TScrollbar", background=face_mid, troughcolor=C["odd"], borderwidth=1,
                    bordercolor=t.c("border_dark"), arrowcolor=C["steel"], lightcolor=C["gold_dim"],
                    darkcolor=t.c("border_dark"))
        s.map(o + ".TScrollbar", background=[("active", TH.grad_at(t.grad(nb["hover"]), 0.5))])
    s.configure("Sash", sashthickness=7, gripcount=0, background=C["line"])
    # rule 24 (the softer look): round fields and dropdowns, a thin round scroll bar, round Quiet / Strip buttons -
    # made again for every theme (new element names: ns); corners blend into the color behind each widget
    soft.setup_ttk(root, s, ns, C)


def monitor_rect(root, x, y, full=False):
    """2.25.2: (left, top, right, bottom) of the monitor holding the point (x, y) - its work area, without the
    taskbar. Popups are kept on THAT monitor; winfo_screenwidth() is only the main monitor, which pushed popups over
    to it when the app was on another one."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]
            u = ctypes.windll.user32
            u.MonitorFromPoint.restype = ctypes.c_void_p
            u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
            h = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)        # MONITOR_DEFAULTTONEAREST
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if h and u.GetMonitorInfoW(h, ctypes.byref(mi)):
                r = mi.rcMonitor if full else mi.rcWork     # 2.50.0: full = the whole screen (the game is
                return r.left, r.top, r.right, r.bottom         # full screen: windows over it may sit on the taskbar)
        except Exception:
            buglog.caught()
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def place_near(root, win, x, y):
    """Put `win` with its corner at (x, y), kept inside the monitor that point is on."""
    win.update_idletasks()
    l, t, r, b = monitor_rect(root, x, y)
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = max(l, min(int(x), r - w - 8))
    y = max(t, min(int(y), b - h - 8))
    win.geometry(f"+{x}+{y}")
    return x, y


class Toast:
    """Small always-on-top popup near the mouse that never takes keyboard focus."""

    def __init__(self, root):
        self.root, self.win, self.job = root, None, None

    def hide(self):
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                buglog.caught()
            self.win = None

    def show(self, title, lines, color, secs):
        self.hide()
        w = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", 0.97)
        except Exception:
            buglog.caught()
        outer = tk.Frame(w, bg=color, padx=2, pady=2)
        outer.pack()
        card = tk.Frame(outer, bg=C["panel"], padx=16, pady=8)
        card.pack()
        tk.Label(card, text=title, bg=C["panel"], fg=color, font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        for ln in lines:
            tk.Label(card, text=ln, bg=C["panel"], fg=C["text"], font=("Segoe UI", 10), anchor="w",
                     justify="left").pack(fill="x")
        w.update_idletasks()
        place_near(self.root, w, self.root.winfo_pointerx() + 26, self.root.winfo_pointery() + 26)
        if sys.platform == "win32":      # do not steal focus from the game
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
                st = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, st | 0x08000000 | 0x00000080)
            except Exception:
                buglog.caught()
        w.deiconify()
        from . import soft
        soft.round_window(w)                            # rule 24: Windows 11 rounds it (elsewhere: square)
        w.bind("<Button-1>", lambda e: self.hide())
        self.win = w
        self.job = self.root.after(int(secs * 1000), self.hide)


MENU_OPEN = [False]                 # 3.0.6: a dropdown menu is open (menu_popup) - no tooltip then


def menu_popup(menu, x, y):
    """A dropdown's menu at x, y, with no tooltip while it's open (and the one showing hides). Windows: tk_popup
    returns when the menu closes; elsewhere the menu's <Unmap> says so."""
    import sys
    Tooltip.hide_all()
    MENU_OPEN[0] = True
    if sys.platform != "win32":
        menu.bind("<Unmap>", lambda e: MENU_OPEN.__setitem__(0, False), add="+")
    try:
        menu.tk_popup(x, y)
    finally:
        if sys.platform == "win32":
            MENU_OPEN[0] = False
    return menu


class Tooltip:
    """2.37.0: a small tip under a widget while the mouse rests on it (also the text a screen reader can't get from
    an icon). Tooltip(widget, text); .text can be changed later. 3.0.6: one at a time - a new one hides the last -
    and none while a dropdown menu is open."""
    SHOWN = []

    @classmethod
    def hide_all(cls):
        for tip in list(cls.SHOWN):
            tip._leave()

    def __init__(self, widget, text, delay=450):
        self.w, self.text, self.delay, self.win, self.job = widget, text, delay, None, None
        self.at = None                                      # D3: (x, y) on screen, for one widget that has many spots
        widget._tip = self                                  # (tools/check_ux.py: this button has a tip)
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")
        widget.bind("<Unmap>", self._leave, add="+")       # P4 (2.108.0): a tip stayed up when its page was left
        widget.bind("<Destroy>", self._leave, add="+")

    def _enter(self, _e=None):
        self._cancel()
        self.job = self.w.after(self.delay, self.show)

    def _cancel(self):
        if self.job:
            try:
                self.w.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def _leave(self, _e=None):
        self._cancel()
        self.hide()

    def _where(self):
        return self.w.winfo_rootx() + 8, self.w.winfo_rooty() + self.w.winfo_height() + 4

    def show(self):
        self.job = None
        if not self.text or self.win is not None or MENU_OPEN[0]:
            return
        try:                                                # (the mouse must still be on it)
            px, py = self.w.winfo_pointerxy()
            wx, wy = self.w.winfo_rootx(), self.w.winfo_rooty()
            if self.at is None and not (wx <= px < wx + self.w.winfo_width() and wy <= py < wy + self.w.winfo_height()):
                return
        except tk.TclError:
            return
        Tooltip.hide_all()
        try:
            x, y = self.at or self._where()         # (D3: a spot given for one of many - else as master)
        except tk.TclError:
            return
        self.win = tk.Toplevel(self.w)
        self.win._app_popup = True                          # (drawer-look: over the Drawer while it's topmost)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        bg, fg, edge = self._colors()                   # 2.100.0: over the game, the overlay's own look
        tk.Label(self.win, text=self.text, bg=bg, fg=fg, font=("Segoe UI", SMALL), justify="left",
                 wraplength=420, padx=8, pady=4, highlightthickness=1, highlightbackground=edge).pack()
        place_near(self.w.winfo_toplevel(), self.win, x, y)
        from . import soft
        soft.round_window(self.win)                    # rule 24: Windows 11 rounds it (elsewhere: square)
        Tooltip.SHOWN.append(self)
        self.w.after(400, self._watch)

    def _watch(self):
        """P4: gone as soon as its widget isn't on screen (a page change doesn't send a Leave)."""
        if self.win is None:
            return
        try:
            gone = not self.w.winfo_viewable()
        except tk.TclError:
            gone = True
        if gone:
            return self.hide()
        try:
            self.w.after(400, self._watch)
        except tk.TclError:
            self.hide()

    def _colors(self):
        """(bg, fg, edge): the app's colors - or, on a window over the game, the overlay's (its theme and look)."""
        try:
            from .overlaywin import OverlayWindow, pal
            if isinstance(self.w.winfo_toplevel(), OverlayWindow):
                P = pal()
                return P["bg"], P["text"], P.get("edge") or P.get("leather") or C["line"]
        except Exception:
            buglog.caught()
        return C["panel2"], C["text"], C["line"]

    def hide(self):
        if self in Tooltip.SHOWN:
            Tooltip.SHOWN.remove(self)
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


class TagTip(Tooltip):
    """The same tip for a part of a canvas (its tag) - the item card's filter rows. TagTip(canvas, tag, text)."""

    def __init__(self, canvas, tag, text, delay=450):
        self.w, self.text, self.delay, self.win, self.job = canvas, text, delay, None, None
        self.at = None                                  # (3.0.6, error log: Tooltip.show reads it)
        canvas.tag_bind(tag, "<Enter>", self._enter, add="+")
        canvas.tag_bind(tag, "<Leave>", self._leave, add="+")
        canvas.tag_bind(tag, "<ButtonPress>", self._leave, add="+")

    def _where(self):
        return self.w.winfo_pointerx() + 12, self.w.winfo_pointery() + 18


class Splitter(tk.Frame):
    """2.123.4 (feedback: the divider was janky and slow, with no visible indicator): a left side you can widen or
    narrow by dragging a grip you can see (a line with dots that lights up under the mouse). While dragging only a
    thin guide line moves; the sides are laid out once, when you let go. Splitter(parent, width, lo, keep, on_set);
    .left and .right are the two sides; sashpos(0[, x]) reads or sets the left width."""

    GRIP = 9

    def __init__(self, parent, width=420, lo=330, keep=300, on_set=None, bg=None, fixed="left", **kw):
        super().__init__(parent, bg=bg or C["bg"], **kw)
        self.lo, self.keep, self.on_set, self._want = lo, keep, on_set, int(width)
        self.fixed_right = fixed == "right"         # Bulk Pricing: the right side (the item) has the width, the
        self.left = tk.Frame(self, bg=C["panel2"], width=self._want)          # left (the list) takes the rest
        self.grip = tk.Frame(self, bg=C["panel"], width=self.GRIP, cursor="sb_h_double_arrow")
        self.grip.pack_propagate(False)
        self._bar = tk.Frame(self.grip, bg=C["gold_dim"], width=1)
        self._bar.place(relx=0.5, rely=0, relheight=1, anchor="n")
        self._dots = tk.Label(self.grip, text="⋮\n⋮", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9),
                              cursor="sb_h_double_arrow", bd=0, padx=0, pady=0)
        self._dots.place(relx=0.5, rely=0.5, anchor="center")
        self.right = tk.Frame(self, bg=C["panel"])
        if self.fixed_right:
            self.left.config(width=1)
            self.right.config(width=self._want)
        self.fixed = self.right if self.fixed_right else self.left
        self.fixed.pack_propagate(False)
        self._pack_sides()
        self._guide = tk.Frame(self, bg=C["orange"], width=2)
        self._x0 = None
        for w in (self.grip, self._dots, self._bar):
            w.bind("<Enter>", lambda e: self._lit(True), add="+")
            w.bind("<Leave>", lambda e: self._lit(self._x0 is not None), add="+")
            w.bind("<ButtonPress-1>", self._press, add="+")
            w.bind("<B1-Motion>", self._drag, add="+")
            w.bind("<ButtonRelease-1>", self._release, add="+")
        Tooltip(self.grip, "Drag to make the item side wider or narrower")
        Tooltip(self._dots, "Drag to make the item side wider or narrower")
        self.bind("<Configure>", lambda e: self._clamp_now(), add="+")

    def _lit(self, on):
        try:
            self._bar.config(bg=C["orange"] if on else C["gold_dim"])
            self._dots.config(fg=C["orange"] if on else C["muted"])
        except tk.TclError:
            pass

    def clamp(self, x):
        pw = self.winfo_width()
        lo = min(self.lo, 300) if 1 < pw < 900 else self.lo           # D3: a little less room at Drawer width
        hi = pw - self.keep - self.GRIP if pw > lo + self.keep + self.GRIP else max(lo, x)
        return int(max(lo, min(x, hi)))

    def _pack_sides(self):
        """Side by side: the fixed side at its width, the grip, the other side taking the rest."""
        if self.fixed_right:
            self.right.pack(side="right", fill="y")
            self.grip.pack(side="right", fill="y")
            self.left.pack(side="left", fill="both", expand=True)
        else:
            self.left.pack(side="left", fill="y")
            self.grip.pack(side="left", fill="y")
            self.right.pack(side="left", fill="both", expand=True)

    def _clamp_now(self):
        x = self.clamp(self._want)
        if x != int(self.fixed.cget("width")):
            self.fixed.config(width=x)

    def _at(self, x_root):
        """The fixed side's width for a mouse at x_root."""
        if self.fixed_right:
            return self.clamp(self._x0 + self.winfo_width() - x_root)
        return self.clamp(x_root - self._x0)

    def _guide_x(self, want):
        return (self.winfo_width() - want - self.GRIP + self.GRIP // 2) if self.fixed_right else want + self.GRIP // 2

    def _press(self, e):
        self._x0 = self.winfo_rootx()
        self._lit(True)
        self._guide.place(x=self._guide_x(self._want), y=0, relheight=1)
        self._guide.lift()

    def _drag(self, e):
        if self._x0 is None:
            return
        self._guide.place_configure(x=self._guide_x(self._at(e.x_root)))

    def _release(self, e):
        if self._x0 is None:
            return
        x = self._at(e.x_root)
        self._x0 = None
        self._guide.place_forget()
        self._lit(False)
        self.sashpos(0, x)
        if self.on_set:
            self.on_set(self._want)

    def sashpos(self, _i=0, x=None):
        if x is None:
            return int(self.fixed.cget("width"))
        self._want = self.clamp(int(x))
        self.fixed.config(width=self._want)
        return self._want

    def set_solo(self, on):
        """Price Checks in a narrow window: .left takes the whole width (one column), .right and the grip are hidden.
        Off: side by side again (the divider's own place is kept). Nothing is drawn again here."""
        on = bool(on)
        if on == getattr(self, "_solo", False):
            return
        self._solo = on
        for w in (self.left, self.grip, self.right):
            w.pack_forget()
        if on:
            self.left.pack(side="left", fill="both", expand=True)
        else:
            self._pack_sides()
            self.fixed.config(width=self.clamp(self._want))

    def set_layout(self, how):
        """Bulk Pricing: "side" (side by side, the grip between), "solo" (.left alone, the whole width) or "stack"
        (.left on top at the height it asks for, .right under it taking the rest - a narrow window). Only packing
        changes: nothing inside is drawn again. -> True when it changed."""
        if how == getattr(self, "_how", "side"):
            return False
        self._how = how
        self._solo = how == "solo"
        for w in (self.left, self.grip, self.right):
            w.pack_forget()
        if how == "solo":
            self.left.pack(side="top", fill="both", expand=True)
        elif how == "stack":
            self.left.pack(side="top", fill="x")
            self.right.pack(side="top", fill="both", expand=True)
        else:
            self._pack_sides()
            self.fixed.config(width=self.clamp(self._want))
        return True


class VSplitter(tk.Frame):
    """2.125.6 (feedback: the Craft Helper's pairs were crammed at the bottom): Splitter's grip turned on its side -
    a top part you make taller or shorter by dragging a grip you can see (a line with dots that lights up under the
    mouse); a thin guide moves while you drag, the parts are laid out once you let go. .top and .bottom are the two
    parts; sashpos(0[, y]) reads or sets the top's height; on_set(height) when you let go."""

    GRIP = 9

    def __init__(self, parent, height=360, lo=120, keep=110, on_set=None, bg=None, **kw):
        super().__init__(parent, bg=bg or C["panel"], **kw)
        self.lo, self.keep, self.on_set, self._want = lo, keep, on_set, int(height)
        self.top = tk.Frame(self, bg=bg or C["panel"], height=self._want)
        self.top.pack_propagate(False)
        self.top.pack(side="top", fill="x")
        self.grip = tk.Frame(self, bg=bg or C["panel"], height=self.GRIP, cursor="sb_v_double_arrow")
        self.grip.pack_propagate(False)
        self.grip.pack(side="top", fill="x")
        self._bar = tk.Frame(self.grip, bg=C["gold_dim"], height=1)
        self._bar.place(relx=0, rely=0.5, relwidth=1, anchor="w")
        self._dots = tk.Label(self.grip, text="⋯⋯", bg=bg or C["panel"], fg=C["muted"], font=("Segoe UI", 9),
                              cursor="sb_v_double_arrow", bd=0, padx=4, pady=0)
        self._dots.place(relx=0.5, rely=0.5, anchor="center")
        self.bottom = tk.Frame(self, bg=bg or C["panel"])
        self.bottom.pack(side="top", fill="both", expand=True)
        self._guide = tk.Frame(self, bg=C["orange"], height=2)
        self._y0 = None
        for w in (self.grip, self._dots, self._bar):
            w.bind("<Enter>", lambda e: self._lit(True), add="+")
            w.bind("<Leave>", lambda e: self._lit(self._y0 is not None), add="+")
            w.bind("<ButtonPress-1>", self._press, add="+")
            w.bind("<B1-Motion>", self._drag, add="+")
            w.bind("<ButtonRelease-1>", self._release, add="+")
        Tooltip(self._dots, "Drag to make the top part taller or shorter")
        self.bind("<Configure>", lambda e: self._clamp_now(), add="+")

    def _lit(self, on):
        try:
            self._bar.config(bg=C["orange"] if on else C["gold_dim"])
            self._dots.config(fg=C["orange"] if on else C["muted"])
        except tk.TclError:
            pass

    def clamp(self, y):
        ph = self.winfo_height()
        hi = ph - self.keep - self.GRIP if ph > self.lo + self.keep + self.GRIP else max(self.lo, y)
        return int(max(self.lo, min(y, hi)))

    def _clamp_now(self):
        y = self.clamp(self._want)
        if y != int(self.top.cget("height")):
            self.top.config(height=y)

    def _press(self, e):
        self._y0 = self.winfo_rooty()
        self._lit(True)
        self._guide.place(x=0, y=self._want + self.GRIP // 2, relwidth=1)
        self._guide.lift()

    def _drag(self, e):
        if self._y0 is None:
            return
        self._guide.place_configure(y=self.clamp(e.y_root - self._y0) + self.GRIP // 2)

    def _release(self, e):
        if self._y0 is None:
            return
        y = self.clamp(e.y_root - self._y0)
        self._y0 = None
        self._guide.place_forget()
        self._lit(False)
        self.sashpos(0, y)
        if self.on_set:
            self.on_set(self._want)

    def sashpos(self, _i=0, y=None):
        if y is None:
            return int(self.top.cget("height"))
        self._want = self.clamp(int(y))
        self.top.config(height=self._want)
        return self._want


class SegBar(tk.Frame):
    """A row of joined toggle buttons (2.0 beta 7), like  [ Total | Daily ].  One is picked at a time; the picked one is
    lit with an orange line under it. command(value) is called when you pick another."""

    def __init__(self, parent, options, value=None, command=None, bg=None, size=10, pad=(16, 4), badges=None,
                 plain=False):
        super().__init__(parent, bg=C["line"], padx=1, pady=1)
        self.command, self.value, self.btns = command, value if value is not None else options[0], {}
        self.size, self.pad = size, pad
        self.plain = bool(plain)                    # Price Checks: no accent - the picked one says "✓" and its word
        self.badges = dict(badges or {})            # 2.38.0: {"Stash tab": "BETA"} - a small tag inside that button
        for i, opt in enumerate(options):
            self._add(opt, i)
        from . import soft                          # rule 24: round ends (caps over its 4 corners)
        soft.round_frame(self, edge=lambda: self.cget("bg"))
        self.paint()
        from . import themes as _th
        _th.subscribe(lambda t: self.paint(), owner=self)    # (its colors are the theme's own: painted again)

    def _add(self, opt, i):
        f = tk.Frame(self, bg=C["line"])
        f.pack(side="left", padx=(1 if i else 0, 0))
        top = tk.Frame(f, bg=C["line"])
        top.pack(fill="x")
        badge = self.badges.get(opt)
        lab = tk.Label(top, text=opt, font=("Segoe UI", self.size, "bold"), padx=self.pad[0], pady=self.pad[1],
                       cursor="hand2")
        lab.pack(side="left", fill="both", expand=True)
        tag = None
        if badge:                                   # inside the button, so it reads as "this option is BETA"
            lab.config(padx=0)
            lab.pack_configure(padx=(self.pad[0], 4))
            tag = tk.Label(top, text=badge, bg="#3a2a10", fg="#ffcf40", font=("Segoe UI", SMALL - 2, "bold"), padx=4,
                           pady=0, cursor="hand2", highlightthickness=1, highlightbackground=C["accent"])
            tag.pack(side="left", padx=(0, self.pad[0]))
            tag.bind("<Enter>", lambda e, o=opt: self.paint(hover=o))
        line = tk.Frame(f, height=2)
        line.pack(fill="x")
        for w in (lab, line, top) + ((tag,) if tag else ()):
            w.bind("<Button-1>", lambda e, o=opt: self.pick(o))
        lab.bind("<Enter>", lambda e, o=opt: self.paint(hover=o))
        lab.bind("<Leave>", lambda e: self.paint())
        self.btns[opt] = (lab, line)

    def looks(self):
        """{"edge", "off", "off_hover", "off_ink", "on", "on_ink"} as hex: the segments' colors on the page color behind
        the bar. The outline is at least 3 : 1 against the page, the unpicked ones have a visible fill, the picked one
        is the theme's selection (a different fill, bold, and its mark - never color alone)."""
        from . import soft, themes as _th
        t = _th.ST.theme
        with _th.raw():
            try:
                under = soft.rgb(self, soft.behind(self) or C["bg"])
            except Exception:
                under = soft.rgb(self, C["bg"])
            text = soft.rgb(self, t.c("text_muted"))
            ink = soft.rgb(self, t.c("text"))
            lk = soft.secondary_looks(text, under, ink, ink=ink)
            on, on_ink = soft.segment_picked(soft.rgb(self, t.c("selection")), soft.rgb(self, t.c("selection_text")),
                                             lk["n"][0])
            hx = soft.hexc
            return {"edge": hx(lk["n"][1]), "off": hx(lk["n"][0]), "off_hover": hx(lk["h"][0]),
                    "off_ink": t.c("text"), "on": hx(on), "on_ink": hx(on_ink)}

    def paint(self, hover=None):
        from . import themes as _th
        t = _th.ST.theme
        if t is None:
            return
        k = self.looks()
        with _th.raw():                             # Round 18: the theme's own tokens (a light theme's picked one
            if self.cget("bg") != k["edge"]:        # read white on light blue), in the Drawer and the Full
                self.config(bg=k["edge"])           # window alike. The outline is the bar's own 1 px frame.
            for opt, (lab, line) in self.btns.items():
                on = opt == self.value
                bg = k["on"] if on else (k["off_hover"] if opt == hover else k["off"])
                fg = k["on_ink"] if on else k["off_ink"]
                if self.plain:                      # (a plain toggle: a mark and a word, never the accent)
                    lab.config(bg=bg, fg=fg, text=("\u2713 " if on else "") + opt)
                    lab.master.config(bg=bg)
                    line.config(bg=t.c("text") if on else bg)
                    continue
                lab.config(bg=bg, fg=fg)
                lab.master.config(bg=bg)            # (the row that also holds a badge)
                line.config(bg=t.c("accent") if on else bg)
        self._paint_ends()

    def _paint_ends(self):
        """Rule 24: the round ends take the first / last button's color."""
        labs = [lab for lab, _l in self.btns.values()]
        if not labs:
            return
        from . import soft
        try:
            a, b = labs[0].cget("bg"), labs[-1].cget("bg")
        except tk.TclError:
            return
        soft.paint_caps(self, inside={"tl": a, "bl": a, "tr": b, "br": b})

    def pick(self, opt, notify=True):
        if opt not in self.btns:
            return
        changed = opt != self.value
        self.value = opt
        self.paint()
        if notify and changed and self.command:
            self.command(opt)

    def get(self):
        return self.value


class SegBook(tk.Frame):
    """Pages switched by a SegBar instead of notebook tabs (real buttons, 2.0 beta 7). Same calls as ttk.Notebook for
    what the app uses: add, select, index, tab(i, 'text'); fires <<NotebookTabChanged>>."""

    def __init__(self, parent, bg=None, **kw):
        super().__init__(parent, bg=bg or C["panel"], **kw)
        self.top = tk.Frame(self, bg=bg or C["panel"])
        self.top.pack(fill="x", pady=(0, 8))
        self.bar = SegBar(self.top, ["-"], command=self._picked, size=10, pad=(16, 8))
        self.bar.pack(side="left")
        for w in self.bar.winfo_children():
            w.destroy()
        self.bar.btns = {}
        self.pages, self.titles, self.cur = [], [], None

    def add(self, frame, text=""):
        self.pages.append(frame)
        self.titles.append(text)
        self.bar._add(text, len(self.titles) - 1)
        if self.cur is None:
            self.select(0)
        else:
            self.bar.paint()

    def _picked(self, text):
        self.select(self.titles.index(text))

    def select(self, which=None):
        if which is None:
            return str(self.pages[self.cur]) if self.cur is not None else ""
        i = which if isinstance(which, int) else self.pages.index(which)
        if i == self.cur:
            return
        if self.cur is not None:
            self.pages[self.cur].pack_forget()
        self.cur = i
        self.pages[i].pack(fill="both", expand=True)
        self.bar.pick(self.titles[i], notify=False)
        self.event_generate("<<NotebookTabChanged>>")

    def index(self, what):
        if what == "end":
            return len(self.pages)
        if isinstance(what, int):
            return what
        return next((i for i, p in enumerate(self.pages) if str(p) == str(what)), self.cur or 0)

    def tab(self, i, option="text"):
        return self.titles[i]


class SbGuard:
    """2.112.2: a scroll bar that shows only when needed can loop forever: shown -> the page is narrower -> its
    wrapped text is taller / shorter -> hidden -> wider -> shown ... Tk's idle queue never empties and the app stops
    responding (it hung Windows on a theme change: its scroll bar and text measure differently). Count the flips:
    after 3 within a second the bar stays shown until the page settles (2 s quiet)."""

    def __init__(self):
        self.flips = []
        self.hold = 0.0

    def may_hide(self):
        import time as _t
        return _t.time() >= self.hold

    def flipped(self):
        import time as _t
        now = _t.time()
        self.flips = [t for t in self.flips if now - t < 1.0] + [now]
        if len(self.flips) > 3:
            self.hold = now + 2.0
            self.flips = []


def overflow_scrollbar(cv, command=None, gap=2, inside=False):
    """The app's thin round scroll bar for a canvas list (rows drawn by hand): it sits just outside the canvas's right
    edge (placed, so it never changes the layout; inside: over the canvas's last 12 px, when there is no room outside) and shows only while there is more than fits. command(*args): what
    a drag does (default: the canvas scrolls); a list that draws only the rows in view repaints there. -> the bar."""
    sb = ttk.Scrollbar(cv.master, orient="vertical")
    sb.configure(command=command or cv.yview)

    def set_(a, b):
        full = float(a) <= 0.0 and float(b) >= 1.0
        try:
            if full:
                if sb.winfo_manager():
                    sb.place_forget()
            elif not sb.winfo_manager():
                sb.place(in_=cv, relx=1.0, x=-gap if inside else gap, rely=0.0, relheight=1.0,
                         anchor="ne" if inside else "nw")
                sb.lift()
            sb.set(a, b)
        except tk.TclError:
            pass
    cv.configure(yscrollcommand=set_)
    sb.__dict__["_soe2_overflow"] = True
    return sb


WHEEL_EVENTS = ("<MouseWheel>", "<Button-4>", "<Button-5>")


def wheel_scrolls(target, host):
    """3.0.1 (owner: the What's new card only scrolled with the mouse over its text, not over its cards): the mouse
    wheel anywhere over host scrolls target - a Text whose cards are windows in it (window_create), or a Canvas. A
    Toplevel host takes it for every widget in it (its binding is on all of them); any other host gets it on itself and
    everything in it, as it is now. target itself scrolls by its own binding (not twice). -> host."""
    def wheel(e):
        if e.widget is target:
            return None
        try:
            if not target.winfo_exists():
                return None
            if getattr(e, "num", None) in (4, 5):
                step = -1 if e.num == 4 else 1
                px = 50 * step                               # (X11: Tk's own Text step)
            else:
                d = int(getattr(e, "delta", 0) or 0)
                if not d:
                    return "break"
                step = -1 if d > 0 else 1
                px = -d // 3 if abs(d) >= 30 else 40 * step  # (Windows: 120 a notch = 40 px; macOS: small deltas)
            if isinstance(target, tk.Text):
                target.yview_scroll(px, "pixels")
            else:
                target.yview_scroll(step * 2, "units")
        except tk.TclError:
            return None
        return "break"

    def hook(w):
        for ev in WHEEL_EVENTS:
            w.bind(ev, wheel, add="+")
        if not isinstance(w, tk.Toplevel):
            for ch in w.winfo_children():
                if ch is not target:
                    hook(ch)
    hook(host)
    host._wheel_to = target                          # (tests)
    return host


class ScrollArea(tk.Frame):
    """A frame whose content scrolls up and down (scroll bar + mouse wheel) when it is taller than the window
    (2.0 beta 14: Settings). Put the content in .inner; it is always as wide as the area.
    The wheel is caught on the area's own window, so it works over every widget inside and doesn't get in the way of
    other windows' scrolling."""

    def __init__(self, parent, bg, min_height=0, **kw):
        """min_height: the content is at least this tall and fills a taller window (its expanding lists grow with it);
        a shorter window scrolls it. 0: the content is as tall as it asks for."""
        super().__init__(parent, bg=bg, **kw)
        self.min_height = int(min_height)
        self.sb = ttk.Scrollbar(self, orient="vertical")
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, yscrollcommand=self._sb_set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.config(command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._canvas_cfg)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=(0, 0, e.width, e.height)))
        self._hooked = None
        self._guard = SbGuard()
        self.bind("<Map>", lambda e: self._hook(), add="+")
        self.after_idle(self._hook)

    def _canvas_cfg(self, e):
        opts = {"width": e.width}
        if self.min_height:
            opts["height"] = max(e.height, self.min_height)
        self.canvas.itemconfigure(self._win, **opts)

    def _sb_set(self, a, b):
        """Show the scroll bar only when there is something to scroll (never flipping back and forth - SbGuard)."""
        shown = self.sb.winfo_ismapped()
        if float(a) <= 0.0 and float(b) >= 1.0:
            if shown and self._guard.may_hide():
                self.sb.pack_forget()
                self._guard.flipped()
        elif not shown:
            self.sb.pack(side="right", fill="y", before=self.canvas)
            self._guard.flipped()
        self.sb.set(a, b)

    def _hook(self):
        top = self.winfo_toplevel()
        if self._hooked is top:
            return
        self._hooked = top
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(ev, self._wheel, add="+")

    def _over_me(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, KeyError):
            return False
        while w is not None:
            if w is self:
                return True
            w = w.master
        return False

    def _wheel(self, e):
        if not self.winfo_exists() or not self._over_me(e):
            return
        if isinstance(e.widget, (tk.Text, tk.Listbox, ttk.Treeview)):      # those scroll themselves
            return
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return
        if getattr(e, "num", None) in (4, 5):
            step = -1 if e.num == 4 else 1
        else:
            step = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(step * 2, "units")


# ---------------------------------------------------------------- choosing a key by pressing it (2.0 beta 16)
CAPTURING = [None]           # the key box waiting for a key: the app's keyboard / mouse watcher hands it the key
CAPTURE_HOOK = [None]        # the app sets this: f(waiting) - e.g. watch the mouse buttons while a box waits
_KEYSYMS = {"Return": "enter", "KP_Enter": "enter", "space": "space", "Tab": "tab", "Insert": "insert",
            "Delete": "delete", "Home": "home", "End": "end", "Prior": "pgup", "Next": "pgdn", "Up": "up",
            "Down": "down", "Left": "left", "Right": "right", "grave": "`", "minus": "-", "equal": "=",
            "bracketleft": "[", "bracketright": "]", "semicolon": ";", "apostrophe": "'", "comma": ",",
            "period": ".", "slash": "/", "backslash": "\\"}
_MODS = {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Super_L", "Super_R",
         "Win_L", "Win_R", "Caps_Lock", "Num_Lock", "ISO_Level3_Shift"}


def key_from_event(keysym, ctrl, alt, shift):
    """A key you pressed -> the text the app stores ('F3', 'Ctrl+Shift+H', 'Numpad5'), or None for a key it can't use."""
    k = None
    if keysym.startswith("F") and keysym[1:].isdigit() and 1 <= int(keysym[1:]) <= 24:
        k = keysym
    elif keysym.startswith("KP_") and keysym[3:].isdigit():
        k = "Numpad" + keysym[3:]
    elif len(keysym) == 1 and keysym.isalnum():
        k = keysym.upper()
    elif keysym in _KEYSYMS:
        k = _KEYSYMS[keysym]
        k = k.capitalize() if len(k) > 1 else k
    if k is None:
        return None
    return "+".join([m for m, on in (("Ctrl", ctrl), ("Alt", alt), ("Shift", shift)) if on] + [k])


def key_from_vk(vk, ctrl, alt, shift):
    """Windows key code -> stored text, using the same key names the hotkeys understand."""
    from .overlay import VK
    mouse = {0x04: "MButton", 0x05: "XButton1", 0x06: "XButton2"}
    names = [n for n, v in VK.items() if v == vk and n not in ("ins", "del", "escape", "pageup", "pagedown")]
    if vk in mouse:
        n = mouse[vk]
    elif not names:
        return None
    else:
        n = names[0]
        n = n.upper() if len(n) == 1 or (n[0] == "f" and n[1:].isdigit()) else n.capitalize()
    return "+".join([m for m, on in (("Ctrl", ctrl), ("Alt", alt), ("Shift", shift)) if on] + [n])


class KeyCapture(tk.Label):
    """A hotkey box like most apps have: click it and press the key (with Ctrl / Alt / Shift if you like).
    Esc = keep the old key, Backspace / Delete / right-click = no key. Holds its value in a StringVar."""

    TIMEOUT_MS = 15000

    def __init__(self, parent, variable, width=12, on_change=None, allow_esc=False, **kw):
        super().__init__(parent, width=width, anchor="w", padx=8, cursor="hand2", takefocus=1,
                         bg=C["odd"], fg=C["text"], font=("Consolas", 9), highlightthickness=1,
                         highlightbackground=C["line"], highlightcolor=C["accent"], **kw)
        self.var, self.on_change, self.waiting, self._alt = variable, on_change, False, False
        self.allow_esc = allow_esc          # 2.121.1: a close key may be Esc itself (a click elsewhere gives up)
        self.var.trace_add("write", lambda *a: self.show())
        self.bind("<Button-1>", lambda e: self.start())
        self.bind("<Button-3>", lambda e: self.set(""))
        self.bind("<KeyPress>", self._press)
        self.bind("<KeyRelease>", self._release)
        self.bind("<Button-2>", lambda e: self.waiting and self.set("MButton"))
        self._job = None
        self.show()

    def show(self):
        from .overlay import key_label
        if self.waiting:
            self.config(text="Press a key…", fg=C["accent"], highlightbackground=C["accent"])
        else:
            v = self.var.get().strip()
            self.config(text=key_label(v) if v else "click to set", fg=C["text"] if v else C["muted"],
                        highlightbackground=C["line"])

    def start(self):
        other = CAPTURING[0]
        if other is not None and other is not self:
            try:
                other.stop()                       # only one box waits at a time
            except tk.TclError:
                pass
        self.waiting, self._alt = True, False
        CAPTURING[0] = self
        top = self.winfo_toplevel()
        if not getattr(top, "_kc_click", False):   # a click anywhere else in the window gives up waiting
            top._kc_click = True
            top.bind("<ButtonPress>", lambda e: CAPTURING[0] is not None and e.widget is not CAPTURING[0]
                     and CAPTURING[0].stop(), add="+")
        try:
            self.focus_force()                     # the app's windows may not have the keyboard yet
        except tk.TclError:
            pass
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(self.TIMEOUT_MS, self.stop)
        if CAPTURE_HOOK[0]:
            CAPTURE_HOOK[0](True)
        self.show()

    def stop(self):
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self.waiting:
            self.waiting = False
            if CAPTURING[0] is self:
                CAPTURING[0] = None
            if CAPTURE_HOOK[0]:
                CAPTURE_HOOK[0](False)
            self.show()

    def take(self, vk, ctrl, alt, shift):
        """A key (or mouse button) from the app's keyboard / mouse watcher, while this box waits (Windows)."""
        if not self.waiting:
            return
        if vk == 0x1B and self.allow_esc and not (ctrl or alt or shift):
            self.set("Esc")
        elif vk == 0x1B:
            self.stop()
        elif vk in (0x08, 0x2E) and not (ctrl or alt or shift):
            self.set("")
        else:
            k = key_from_vk(vk, ctrl, alt, shift)
            if k:
                self.set(k)

    def set(self, text):
        self.var.set(text)
        self.stop()
        if self.on_change:
            self.on_change(text)

    def _release(self, e):
        if e.keysym in ("Alt_L", "Alt_R"):
            self._alt = False

    def _press(self, e):
        if not self.waiting:
            if e.keysym in ("Return", "space"):
                self.start()
                return "break"
            return None
        if e.keysym in ("Alt_L", "Alt_R"):
            self._alt = True
            return "break"
        if e.keysym in _MODS:
            return "break"
        if e.keysym == "Escape":
            if self.allow_esc and not (e.state & 0x5):
                self.set("Esc")
            else:
                self.stop()
            return "break"
        if e.keysym in ("BackSpace", "Delete") and not (e.state & 0x5):
            self.set("")
            return "break"
        alt = self._alt or bool(e.state & 0x20000) or (sys.platform != "win32" and bool(e.state & 0x8))
        k = None
        if sys.platform == "win32":               # on Windows the key code IS the key (tells numpad 5 from 5 etc.)
            k = key_from_vk(e.keycode, bool(e.state & 0x4), alt, bool(e.state & 0x1))
        k = k or key_from_event(e.keysym, bool(e.state & 0x4), alt, bool(e.state & 0x1))
        if k:
            self.set(k)
        return "break"


# ---------------------------------------------------------------- the app's look (2.0.0: Settings > Appearance)
# A theme recolours the whole app in one place: every color handed to Tk passes through theme_color(), which moves the
# app's steel-blue / navy tones to the theme's hue (lightness kept, so contrast stays the same). Colors that mean
# something (item rarities, green / red, gold for money, the accent) are left alone. Applied at start-up.
import re as _re

# ------------------------------------------------------------------ 2.60.0: theme packs (soe2/themes.py, themes/*.json)
from . import themes as _themes

THEMES = {t.id: (t.name, None, 1.0) for t in _themes.ordered()}     # id: (label, -, -) - the old shape, kept
_STYLE_LOG = {"quiet": False, "calls": {}}     # ttk style calls made outside setup_style - replayed after a swap
_THEME = {"keep": set()}               # (old name, kept for code that adds to it)


def theme_color(c):
    """A color as the running theme shows it (every color given to Tk passes here)."""
    return _themes.tone(c)


def apply_look(theme=None, root=None):
    """Call once at start-up, before any window is built. relook() swaps it later, live. (2.119.0: a theme keeps its
    own accent and the text size is fixed - Settings › Appearance had both.)"""
    import tkinter.ttk as _ttk
    if not _themes.ST.base:
        _themes.init(C, _BASE)
    _themes.set_theme(_themes.packs()[_themes.pick_id(theme)], None)
    if not getattr(tk.Misc, "_soe2_themed", False):          # every color given to Tk goes through theme_color
        orig = tk.Misc._options

        def _options(self, cnf, kw=None):
            res = orig(self, cnf, kw)
            return tuple(theme_color(v) if isinstance(v, str) else v for v in res)
        tk.Misc._options = _options
        oa = tk.Misc.option_add

        def _option_add(self, pattern, value, priority=None):
            return oa(self, pattern, theme_color(value) if isinstance(value, str) else value, priority)
        tk.Misc.option_add = _option_add
        fo, fm = _ttk._format_optdict, _ttk._format_mapdict

        def _fo(*a, **k):
            return tuple(theme_color(v) if isinstance(v, str) else v for v in fo(*a, **k))

        hexes = _re.compile(r"#[0-9a-fA-F]{6}\b")

        def _fm(*a, **k):                                      # state maps: "readonly #0b111c" -> recolour inside
            return tuple(hexes.sub(lambda m_: theme_color(m_.group(0)), v) if isinstance(v, str) else v
                         for v in fm(*a, **k))
        _ttk._format_optdict, _ttk._format_mapdict = _fo, _fm
        sc, sm = _ttk.Style.configure, _ttk.Style.map

        def _sc(self, style, query_opt=None, **kw):            # 2.60.0: remember style calls made outside
            if kw and query_opt is None and not _STYLE_LOG["quiet"]:   # setup_style, to make them again after a swap
                _STYLE_LOG["calls"].setdefault(("configure", style), {}).update(kw)
            return sc(self, style, query_opt, **kw)

        def _sm(self, style, query_opt=None, **kw):
            if kw and query_opt is None and not _STYLE_LOG["quiet"]:
                _STYLE_LOG["calls"].setdefault(("map", style), {}).update(kw)
            return sm(self, style, query_opt, **kw)
        _ttk.Style.configure, _ttk.Style.map = _sc, _sm
        tk.Misc._soe2_themed = True
    return _themes.ST.theme


def relook(root, theme):
    """2.60.0: swap the theme while the app runs - every window, list, canvas and menu is re-colored in place."""
    import time as _t
    t0 = _t.time()
    old = _themes.snapshot()
    _themes.set_theme(_themes.packs()[_themes.pick_id(theme)], None)
    tr = _themes._translator(old)
    from .hangwatch import step                 # 2.114.3: where a theme change was, if the app closes on one
    step(f"theme change to {theme}: windows")
    n = _themes.walk(root, tr)
    step(f"theme change to {theme}: styles")
    setup_style(root)
    s = ttk.Style(root)
    _STYLE_LOG["quiet"] = True
    try:
        for (how, style), kw in list(_STYLE_LOG["calls"].items()):
            kw = ({k: (tr(("style", style, k), v) if _themes.is_hex(v) else v) for k, v in kw.items()}
                  if how == "configure" else kw)
            try:
                (s.configure if how == "configure" else s.map)(style, **kw)
            except Exception:
                buglog.caught()
    finally:
        _STYLE_LOG["quiet"] = False
    step(f"theme change to {theme}: self-painted parts")
    _themes.notify()
    from . import soft                          # rule 24: round corners blend into the new colors behind them
    soft.after_relook(root)
    step(f"theme change to {theme}: done")
    return n, _t.time() - t0
