"""The overlay windows' see-through color and opacity on Windows, in one place (a boxless overlay Style, the Vaal Lens
marks and other windows that draw on a see-through background).

Windows keeps a layered window's color key (the see-through color, Tk's -transparentcolor) and its opacity (-alpha)
as one setting, SetLayeredWindowAttributes(colorref, alpha, LWA_COLORKEY | LWA_ALPHA). Anything else that touches the
window's extended style afterwards - click-through (WS_EX_TRANSPARENT), no-activate, leaving it out of captures, a
new opacity - can leave it without its color key, and the see-through color (#010101, near black) then shows as a
black box. So every such change goes through here and puts both back together, and the key is read back from Windows
(GetLayeredWindowAttributes). Round 18: the overlay's lines over the XP bar no longer use a see-through color at all
(their own window, overlaywin.LinesWindow).

GGG ToS: the app's own window's style - nothing is read from the screen and nothing is sent to the game."""
import sys

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
LWA_COLORKEY = 0x1
LWA_ALPHA = 0x2
_U = [None]


def user32():
    """user32 with its own function objects (argtypes set here never clash with ctypes.windll.user32's)."""
    if _U[0] is None:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")
        u.GetParent.restype = wintypes.HWND
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.SetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        u.SetLayeredWindowAttributes.restype = wintypes.BOOL
        u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
        u.GetLayeredWindowAttributes.restype = wintypes.BOOL
        u.GetLayeredWindowAttributes.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
                                                 ctypes.POINTER(wintypes.BYTE), ctypes.POINTER(wintypes.DWORD)]
        _U[0] = u
    return _U[0]


def _lib(u):
    if u is not None:
        return u
    return user32() if sys.platform == "win32" else None


def colorref(w, color):
    """A Tk color -> Windows' COLORREF (0x00BBGGRR)."""
    r, g, b = (v >> 8 for v in w.winfo_rgb(color))
    return r | (g << 8) | (b << 16)


def key_of(w):
    """The window's see-through color (Tk's -transparentcolor), or "" (none, or not Windows)."""
    try:
        return str(w.attributes("-transparentcolor") or "")
    except Exception:
        return ""


def alpha_of(w):
    try:
        return max(0.0, min(1.0, float(w.attributes("-alpha"))))
    except Exception:
        return 1.0


def frame_of(w, u):
    """The window's own frame (Tk's wrapper - what the styles belong to), or 0 before it's on screen."""
    try:
        return u.GetParent(w.winfo_id()) or 0
    except Exception:
        return 0


def holds(w, u=None, h=None):
    """Is the window's color key in force right now, as Windows has it? -> True / False; None: can't tell (not
    Windows, no frame yet, or no color key wanted)."""
    u = _lib(u)
    key = key_of(w)
    if u is None or not key:
        return None
    h = h or frame_of(w, u)
    if not h:
        return None
    import ctypes
    from ctypes import wintypes
    cr, a, fl = wintypes.DWORD(), wintypes.BYTE(), wintypes.DWORD()
    if not u.GetLayeredWindowAttributes(h, ctypes.byref(cr), ctypes.byref(a), ctypes.byref(fl)):
        return False
    return bool(fl.value & LWA_COLORKEY) and cr.value == colorref(w, key)


def apply(w, click_through=None, u=None):
    """Set the window's style and its layered attributes together: layered, click-through on / off (None: as it is),
    then its color key (if it has one) and opacity, both at once. -> True when they're in force (the color key read
    back from Windows), False when Windows didn't keep the key, None when there's nothing to do here (not Windows,
    or the window isn't on screen yet)."""
    u = _lib(u)
    if u is None:
        return None
    h = frame_of(w, u)
    if not h:
        return None
    ex = u.GetWindowLongW(h, GWL_EXSTYLE)
    new = ex | WS_EX_LAYERED                    # (layered: what click-through and the color key both need)
    if click_through is not None:
        new = (new | WS_EX_TRANSPARENT) if click_through else (new & ~WS_EX_TRANSPARENT)
    if new != ex:
        u.SetWindowLongW(h, GWL_EXSTYLE, new)
    key = key_of(w)
    flags = LWA_ALPHA | (LWA_COLORKEY if key else 0)
    u.SetLayeredWindowAttributes(h, colorref(w, key) if key else 0, int(round(alpha_of(w) * 255)), flags)
    return holds(w, u, h) if key else True


def keep(w, u=None):
    """After anything that changed a window's style or opacity: its color key (if it has one) is put back with its
    opacity. -> as apply(); None when the window has no color key."""
    if not key_of(w):
        return None
    return apply(w, None, u)
