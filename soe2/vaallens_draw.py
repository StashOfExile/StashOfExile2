"""UI overhaul (feedback: a better method of drawing the suggested paths on screen is needed, the old one was
janky): Vaal Lens's marks drawn as one smooth picture with real see-through edges.

Why it looked rough: the marks were Tk canvas shapes on a window with one see-through color. Tk draws lines and
dashes without smoothing, and a picture's soft edges can't fade into the game - they turn into a dark fringe.

Now: render() draws everything with PIL at twice the size and shrinks it (smooth edges), with real transparency
(soft fills, a glow under the Architect path, shadows under the step numbers). Layered shows it in a Windows
layered window (UpdateLayeredWindow: per-pixel alpha), click-through and never focused. Anywhere else (or if
Windows says no), vaallens_marks falls back to the old canvas drawing.

It only draws; nothing is sent to the game."""
import sys

from . import buglog

SS = 2                          # drawn at this many times the size, then shrunk: smooth edges
RED = (255, 77, 61)


def _rgb(h, default=(240, 160, 74)):
    try:
        h = str(h).lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return default


def _font(px, bold=True):
    from PIL import ImageFont
    names = (["segoeuib.ttf", "seguisb.ttf"] if bold else ["segoeui.ttf"]) + ["DejaVuSans-Bold.ttf", "arialbd.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(px)
    except TypeError:
        return ImageFont.load_default()


def render(game, marks, P, icons=None, chain=None):
    """-> (PIL RGBA image, (left, top) on screen) holding every mark, or (None, None). Same marks as
    vaallens_marks.Marks.show: {tile: (kind, what)} - "p" a planned room, "now" where the picked card goes, "x" a
    tile that touches a reward room; chain: the path to the Architect."""
    from PIL import Image, ImageDraw, ImageFilter
    from . import vaallens as V
    if not marks and not chain:
        return None, None
    icons = icons or {}
    s, left, top = V.placing(game)
    hw, hh = 69.3 * s * 0.92, 59.4 * s * 0.92
    gold = _rgb(P.get("gold") or "#d9b13a", (217, 177, 58))
    accent = _rgb(P.get("head") or "#f0a04a")
    bg = _rgb(P.get("bg") or "#15120f", (21, 18, 15))

    def at(t):
        if isinstance(t[0], str):                       # ("@", x, y): a screen point (3.0.6: a card's step number)
            return t[1], t[2]
        x, y = V.xy(*t)
        return left + x * s, top + y * s

    # what's drawn, in screen pixels: its box (with room for glows and badges)
    pts = [at(t) for t in marks] + [at(t) for t in (chain or ())]
    if not pts:
        return None, None
    pad = int(hw + 40 * s)
    x0, y0 = int(min(p[0] for p in pts) - pad), int(min(p[1] for p in pts) - pad)
    x1, y1 = int(max(p[0] for p in pts) + pad), int(max(p[1] for p in pts) + pad)
    W, H = max(1, x1 - x0), max(1, y1 - y0)
    k = SS

    def L(p):                                           # screen -> this picture (at SS)
        return ((p[0] - x0) * k, (p[1] - y0) * k)

    def diamond(c, f=1.0):
        x, y = L(c)
        return [(x, y - hh * k * f), (x + hw * k * f, y), (x, y + hh * k * f), (x - hw * k * f, y)]

    img = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))

    # the path to the Architect: a soft glow, then a clean gold band with a lighter core
    if chain and len(chain) >= 2:
        c_ = [at(t) for t in chain]
        mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)        # noqa: E731
        line = [L(p) for p in [mid(c_[0], c_[1])] + c_[1:-1] + [mid(c_[-2], c_[-1])]]
        width = max(6, int(12 * s * k))
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.line(line, fill=gold + (150,), width=width * 3, joint="curve")
        for p in line:
            r = width * 1.5
            gd.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=gold + (150,))
        glow = glow.filter(ImageFilter.GaussianBlur(width * 1.2))
        img = Image.alpha_composite(img, glow)
        d = ImageDraw.Draw(img)
        d.line(line, fill=gold + (235,), width=width, joint="curve")
        for p in line:
            r = width / 2
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=gold + (235,))
        core = tuple(min(255, int(v * 0.4 + 255 * 0.6)) for v in gold)
        d.line(line, fill=core + (200,), width=max(2, width // 3), joint="curve")

    d = ImageDraw.Draw(img)
    small = _font(max(10, int(18 * s * k)))
    side = max(16, int(hh * 1.1 * k))
    badges, wbadges = [], []
    for t, (m, what) in marks.items():
        c = at(t)
        if m == "lbl":                                  # a card's / medallion's step: the same badge as its tile's
            x, y = L(c)
            badges.append((x, y, str(what)))
            continue
        if m == "x":                                    # touches a reward room: red, dashed edge and a ✕ (not color
            poly = diamond(c, 0.94)                     # alone)
            d.polygon(poly, fill=RED + (46,))
            n = len(poly)
            for i in range(n):                          # a dashed edge, drawn smooth
                a, b = poly[i], poly[(i + 1) % n]
                steps = 7
                for j in range(steps):
                    if j % 2:
                        continue
                    f0, f1 = j / steps, (j + 1) / steps
                    d.line([(a[0] + (b[0] - a[0]) * f0, a[1] + (b[1] - a[1]) * f0),
                            (a[0] + (b[0] - a[0]) * f1, a[1] + (b[1] - a[1]) * f1)],
                           fill=RED + (235,), width=max(3, int(4 * s * k)))
            x, y = L(c)
            dd = max(8, int(16 * s * k))                # 3.0.6 (the x turned into a square): two lines, not
            for a_, b_ in ((-dd, -dd), (-dd, dd)):      # a ✕ in a font that may not have it
                d.line([(x + a_, y + b_), (x - a_, y - b_)], fill=RED + (255,), width=max(4, int(6 * s * k)))
            continue
        step, room = what
        now = m == "now"
        poly = diamond(c, 0.94)
        d.polygon(poly, fill=accent + (70 if now else 34,))
        d.line(poly + [poly[0]], fill=accent + (255 if now else 200,), width=max(3, int((6 if now else 3) * s * k)),
               joint="curve")
        x, y = L(c)
        # 3.0.6 (the drawn icons looked wrong - remove them and overlay a number): no room
        # pictures - the step's number in the middle, the same number as on its card / medallion
        if m == "do":                                   # an Upgrade / Lock medallion's room: an arrow / a padlock
            u = hh * k * 0.42
            if step == "Upgrade":
                d.polygon([(x, y - u), (x + u * 0.8, y), (x + u * 0.32, y), (x + u * 0.32, y + u),
                           (x - u * 0.32, y + u), (x - u * 0.32, y), (x - u * 0.8, y)], fill=accent + (255,),
                          outline=bg + (255,))
            else:
                bw, bh = u * 0.85, u * 0.7
                d.arc((x - bw * 0.62, y - u * 1.05, x + bw * 0.62, y + u * 0.25), 180, 360, fill=accent + (255,),
                      width=max(3, int(u * 0.22)))
                d.line([(x - bw * 0.62 + u * 0.11, y - u * 0.4), (x - bw * 0.62 + u * 0.11, y - u * 0.05)],
                       fill=accent + (255,), width=max(3, int(u * 0.22)))
                d.line([(x + bw * 0.62 - u * 0.11, y - u * 0.4), (x + bw * 0.62 - u * 0.11, y - u * 0.05)],
                       fill=accent + (255,), width=max(3, int(u * 0.22)))
                d.rounded_rectangle((x - bw, y - u * 0.1, x + bw, y - u * 0.1 + bh * 1.4), radius=max(2, int(u * 0.15)),
                                    fill=accent + (255,))
                d.ellipse((x - u * 0.12, y + u * 0.35, x + u * 0.12, y + u * 0.59), fill=bg + (255,))
            wbadges.append((x, y + hh * k * 0.66, step))
        elif step:
            badges.append((x, y, str(step)))

    # step numbers last, on top: a dark disc with a soft shadow and the accent ring
    if badges:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        r = max(10, int(17 * s * k))
        for bx, by, _n in badges:
            sd.ellipse((bx - r, by - r + r * 0.25, bx + r, by + r + r * 0.25), fill=(0, 0, 0, 170))
        sh = sh.filter(ImageFilter.GaussianBlur(r * 0.35))
        img = Image.alpha_composite(img, sh)
        d = ImageDraw.Draw(img)
        for bx, by, n in badges:
            d.ellipse((bx - r, by - r, bx + r, by + r), fill=bg + (240,), outline=accent + (255,),
                      width=max(2, int(2.5 * k)))
            d.text((bx, by), n, fill=accent + (255,), font=small, anchor="mm")

    if wbadges:                                         # the medallion words: a dark pill with the accent ring
        d = ImageDraw.Draw(img)
        f = _font(max(10, int(16 * s * k)))
        for bx, by, w_ in wbadges:
            tw = d.textlength(w_, font=f)
            ph, pw = max(10, int(14 * s * k)), tw / 2 + max(8, int(10 * s * k))
            d.rounded_rectangle((bx - pw, by - ph, bx + pw, by + ph), radius=ph, fill=bg + (240,),
                                outline=accent + (255,), width=max(2, int(2.5 * k)))
            d.text((bx, by), w_, fill=accent + (255,), font=f, anchor="mm")
    return img.resize((W, H), Image.LANCZOS), (x0, y0)


class Layered:
    """A click-through Windows layered window that shows one RGBA picture with real transparency.
    .ok is False when it can't (not Windows, or Windows refused) - use the canvas drawing then."""

    def __init__(self, root):
        import tkinter as tk
        self.ok = sys.platform == "win32"
        self.win = None
        if not self.ok:
            return
        try:
            w = tk.Toplevel(root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.geometry("1x1+0+0")
            w.withdraw()
            self.win = w
        except tk.TclError:
            self.ok = False

    def _hwnd(self):
        from .alerts_page import _hwnd
        return _hwnd(self.win)

    def show(self, img, xy):
        """Put the picture at screen point xy. -> True when shown."""
        if not self.ok or self.win is None or img is None:
            return False
        try:
            import ctypes
            from ctypes import wintypes
            import numpy as np
            self.win.geometry(f"{img.width}x{img.height}+{int(xy[0])}+{int(xy[1])}")
            self.win.deiconify()
            self.win.update_idletasks()
            u, g = ctypes.windll.user32, ctypes.windll.gdi32
            u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            h = self._hwnd()
            # layered + click-through + no taskbar button + never takes focus
            u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)

            a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
            al = a[..., 3:4]
            bgra = np.empty(a.shape, dtype=np.uint8)            # premultiplied BGRA, as Windows wants it
            bgra[..., 0] = (a[..., 2] * al[..., 0] // 255)
            bgra[..., 1] = (a[..., 1] * al[..., 0] // 255)
            bgra[..., 2] = (a[..., 0] * al[..., 0] // 255)
            bgra[..., 3] = a[..., 3]
            data = bgra.tobytes()

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                            ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                            ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                            ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

            class BLENDFUNCTION(ctypes.Structure):
                _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                            ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

            bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), img.width, -img.height, 1, 32, 0, 0, 0, 0, 0, 0)
            u.GetDC.restype = ctypes.c_void_p
            g.CreateCompatibleDC.restype = ctypes.c_void_p
            g.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
            g.CreateDIBSection.restype = ctypes.c_void_p
            g.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
            g.SelectObject.restype = ctypes.c_void_p
            g.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            g.DeleteObject.argtypes = [ctypes.c_void_p]
            g.DeleteDC.argtypes = [ctypes.c_void_p]
            u.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            u.UpdateLayeredWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.POINT),
                                              ctypes.POINTER(wintypes.SIZE), ctypes.c_void_p,
                                              ctypes.POINTER(wintypes.POINT), wintypes.DWORD,
                                              ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
            screen = u.GetDC(None)
            mem = g.CreateCompatibleDC(screen)
            bits = ctypes.c_void_p()
            bmp = g.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
            ok = False
            if bmp and bits.value:
                ctypes.memmove(bits, data, len(data))
                old = g.SelectObject(mem, bmp)
                dst = wintypes.POINT(int(xy[0]), int(xy[1]))
                size = wintypes.SIZE(img.width, img.height)
                src = wintypes.POINT(0, 0)
                blend = BLENDFUNCTION(0, 0, 255, 1)              # AC_SRC_OVER, per-pixel alpha
                ok = bool(u.UpdateLayeredWindow(h, screen, ctypes.byref(dst), ctypes.byref(size), mem,
                                                ctypes.byref(src), 0, ctypes.byref(blend), 2))   # ULW_ALPHA
                g.SelectObject(mem, old)
                g.DeleteObject(bmp)
            g.DeleteDC(mem)
            u.ReleaseDC(None, screen)
            if not ok:
                self.ok = False
                self.hide()
            return ok
        except Exception:
            buglog.caught()
            self.ok = False
            self.hide()
            return False

    def hide(self):
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                pass

    def destroy(self):
        w, self.win = self.win, None
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
