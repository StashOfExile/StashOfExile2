"""The Drawer (drawer build, D1): the app shown as a side panel over the game, put away with one key.

Pure parts (no Tk; tools/test_drawer.py T1 / T2): drawer_rect, flip_for_cursor, to_workspace, clamp_share and the
state machine DrawerState (drawer/PLAN.md section 1.2). Window parts: the adapters TkOnly (any platform) and Win32
(Windows). They only move, show and hide OUR window: ShowWindow, SetWindowPos, SetWindowPlacement and
DwmSetWindowAttribute; SetForegroundWindow(game) hands the keyboard back, as overlaywin does. Nothing is ever sent to
the game and no other program is read (GGG ToS: TOS.md).

Threads: KeyWatch's hook thread may read GAME_OPEN, SHOWN_DRAWER and FG_HOOK and call fg_state(); everything else
here runs on the window's thread (game_rect / EnumWindows included)."""
import contextlib
import os
import sys

BOTTOM = 0.118              # the part of the game's height kept clear at the bottom (skill bar, globes): 1270 / 1440
SHARE = 0.40                # the Drawer's width, as a share of the game's width
SHARE_LO, SHARE_HI = 0.25, 0.70
MIN_W, MAX_W = 900, 1200
SIDE_ROOM = 200             # px of the game always left beside the Drawer
TICK_MS = 350               # the click-away watcher
REDOCK_MS = 2000            # how often a shown Drawer follows the game window
PUT_AWAY = "minimize"       # "minimize" (taskbar button stays) | "withdraw" (the proposal's way; the owner's A/B test)
DRAWER_MIN = (900, 400)     # root.minsize per shape
FULL_MIN = (1000, 560)
DEFAULT_KEY = "Ctrl+Shift+Space"
SHAPES = ("drawer", "full")
AWAY, SHOWN = "away", "shown"

# test hooks (tools/test_drawer.py, tools/smoke_pages.py) - like overlaywin's GAME_ONLY
GAME_RECT_HOOK = None       # () -> (x, y, w, h) of "the game", or None
WM_STATE_HOOK = None        # () -> "normal" | "zoomed" | ...: the window's state as the window manager has it
FG_HOOK = None              # () -> (ours, game): who has the keyboard
CURSOR_HOOK = None          # () -> (x, y): the mouse
# caches the hook thread reads (written on the window's thread)
GAME_OPEN = [False]         # the game is running (drawer_tick, every ~1 s)
SHOWN_DRAWER = [False]      # the app is shown in the Drawer shape


def cfg(settings):
    """SETTINGS["drawer"], with its defaults (all setdefault: nothing is renamed or removed)."""
    d = settings.get("drawer")
    if not isinstance(d, dict):
        d = settings["drawer"] = {}
    d.setdefault("shape", "drawer")
    d.setdefault("side", "right")
    d.setdefault("share", SHARE)
    d.setdefault("click_away", True)
    if d["shape"] not in SHAPES:
        d["shape"] = "drawer"
    if d["side"] not in ("right", "left"):
        d["side"] = "right"
    return d


# ============================================================================ pure functions
def clamp_share(share, area=None):
    """The Drawer's width share, kept between 25% and 70% (anything not a number: the default). area (the game's
    width): the low end goes down to the narrowest Drawer (MIN_W) - on a 4K game 900 px is 23%, and a Drawer dragged
    that narrow must stay that narrow (drawer-look, T14: it snapped back to 25%)."""
    try:
        s = float(share)
    except (TypeError, ValueError):
        return SHARE
    if s != s:                                            # NaN
        return SHARE
    lo = min(SHARE_LO, MIN_W / float(area)) if area and area > 0 else SHARE_LO
    hi = max(SHARE_HI, 1 - SIDE_ROOM / float(area)) if area and area > SIDE_ROOM else SHARE_HI    # (Round 18: a
    return max(lo, min(hi, s))                                       # width you drag wider stays - up to SIDE_ROOM)


def drawer_rect(game=None, work=None, side="right", share=SHARE, cap=True):
    """The Drawer's outer window rect (x, y, w, h), title bar included.
    game: (x, y, w, h) of the game window - top = the game's top, height = its height x (1 - BOTTOM);
    else work: (left, top, right, bottom) of the monitor's work area - its whole height.
    Width = clamp(round(area x share), MIN_W, MAX_W), at most area - SIDE_ROOM; at the right or left edge.
    cap=False (a width YOU set - dragged or Settings' Width %): no MAX_W, so a wider Drawer stays wider (D5)."""
    if game:
        ax, ay, aw, ah = (int(v) for v in game)
        h = int(round(ah * (1 - BOTTOM)))
    elif work:
        left, top, right, bottom = (int(v) for v in work)
        ax, ay, aw, ah = left, top, right - left, bottom - top
        h = ah
    else:
        return None
    w = int(round(aw * clamp_share(share, None if cap else aw)))
    w = max(MIN_W, min(MAX_W, w) if cap else w)
    w = max(300, min(w, aw - SIDE_ROOM))
    x = ax + aw - w if side != "left" else ax
    return x, ay, w, h


def other_side(side):
    return "left" if side == "right" else "right"


def inside(pt, rect):
    if not pt or not rect:
        return False
    x, y, w, h = rect
    return x <= pt[0] < x + w and y <= pt[1] < y + h


def flip_for_cursor(side, cursor, rect_for, game=None):
    """A price check: the item you just copied is under the mouse. If the mouse is inside the Drawer's rect on
    `side`, this one opening uses the other side (not saved). rect_for(side) -> rect. game: the game's rect - a mouse
    outside it is in another coordinate space or on another screen, so it can't be over the Drawer: no flip."""
    if game and not inside(cursor, game):
        return side
    return other_side(side) if inside(cursor, rect_for(side)) else side


def map_rect(rect, src, dst):
    """rect, given inside src (x, y, w, h), at the same place inside dst - one window's rect read in two DPI
    awarenesses (the mapping is linear on one monitor)."""
    x, y, w, h = rect
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dst
    if sw <= 0 or sh <= 0:
        return rect
    fx, fy = dw / float(sw), dh / float(sh)
    return (int(round(dx + (x - sx) * fx)), int(round(dy + (y - sy) * fy)), int(round(w * fx)),
            int(round(h * fy)))


def to_workspace(rect, origin=(0, 0)):
    """SetWindowPlacement wants workspace coordinates: (left, top, right, bottom) less the work area's offset
    (the taskbar at the top or left moves it)."""
    x, y, w, h = rect
    ox, oy = origin
    return x - ox, y - oy, x + w - ox, y + h - oy


def near(a, b, tol=4):
    return a is not None and b is not None and all(abs(int(p) - int(q)) <= tol for p, q in zip(a, b))


# ============================================================================ the states (section 1.2)
class DrawerState:
    """Shape ("drawer" | "full", remembered) and visibility (AWAY | SHOWN). Each event returns what to do:
    ("show", shape, focus, page) | ("away",) | ("front",) | None. No Tk, no Win32 - the host does the window work."""

    def __init__(self, shape="drawer", side="right", click_away=True):
        self.shape = shape if shape in SHAPES else "drawer"
        self.side = side if side in ("right", "left") else "right"
        self.click_away = bool(click_away)
        self.visible = SHOWN                        # the window is on screen while the app starts
        self.opened_by = "restore"                  # "key" | "price" | "restore"
        self.had_focus = False                      # the app was in front since it was shown
        self.session_full = False                   # start-up with something to ask: Full until put away
        self.max_full = False                       # Round 18: maximized from the Drawer - Full until restored
        self._ours = False                          # the app had the keyboard at the last watcher tick

    @property
    def eff(self):
        """The shape the app shows in now."""
        return "full" if self.session_full else self.shape

    def as_drawer(self):
        return self.visible == SHOWN and self.eff == "drawer"

    def show(self, by="key", focus=True, page=None):
        if self.visible == AWAY:
            self.opened_by, self.had_focus, self._ours = by, False, False
        self.visible = SHOWN
        return "show", self.eff, bool(focus), page

    def key(self, app_front=True):
        """The Drawer key."""
        if self.visible == AWAY:
            return self.show("key", True, None)
        if self.eff == "drawer" or app_front:
            return self.away()
        return ("front",)                           # a Full window behind something: to the front

    def price(self):
        """The price check key with "In the app": quietly, on Price Checks (shown: stays, shows the new check)."""
        return self.show("price", False, "pricecheck")

    def esc_in_game(self):
        """Your close key while the game is in front: puts a shown Drawer away (never a Full window)."""
        return self.away() if self.as_drawer() else None

    def esc(self):
        """Esc in the app, when nothing else used it."""
        return self.away()

    def full(self):
        """Full window (the strip's ⤢, Settings)."""
        self.shape, self.session_full, self.max_full = "full", False, False
        return ("show", "full", True, None) if self.visible == SHOWN else None

    def dock(self):
        """Drawer (the strip's ⇤, Settings)."""
        self.shape, self.session_full, self.max_full = "drawer", False, False
        return ("show", "drawer", True, None) if self.visible == SHOWN else None

    def maximized(self):
        """Round 18 (owner: maximize made it maximize, then go back to the small size): the shown Drawer was
        maximized - its button, a double-click on its title, Aero snap to the top. It is the Full window now, for as
        long as it stays maximized (not remembered: the next start is the Drawer). -> ("max",) or None."""
        if self.visible != SHOWN or self.eff != "drawer":
            return None
        self.shape, self.max_full = "full", True
        return ("max",)

    def unmaximized(self):
        """A Full window that came from a maximized Drawer was restored (its button, dragged off the top): the Drawer
        again. -> ("show", "drawer", True, None) when shown, else None."""
        if not self.max_full:
            return None
        self.shape, self.max_full = "drawer", False
        return ("show", "drawer", True, None) if self.visible == SHOWN else None

    def fg(self, ours, game):
        """The click-away watcher's tick: who has the keyboard. The app had it, then the game got it -> away (only
        once the app has been in front since it was shown, so a price check's quiet show never puts it away)."""
        if not self.as_drawer() or not self.click_away:
            self._ours = bool(ours)
            return None
        if ours:
            self.had_focus = True
        fire = self._ours and bool(game) and self.had_focus
        self._ours = bool(ours)
        return self.away() if fire else None

    def restored(self):
        """The window came back without us (its taskbar button): shown in the remembered shape."""
        if self.visible == AWAY:
            return self.show("restore", True, None)
        return None

    def away(self):
        self.visible, self.session_full, self._ours = AWAY, False, False
        return ("away",)

    def gone(self):
        """The window went away by itself (minimized by Windows / its own button): note it, nothing to do."""
        self.visible, self._ours = AWAY, False


# ============================================================================ Win32 helpers (no-ops elsewhere)
WIN = sys.platform == "win32"
_U = [None]


def _user32():
    """A private user32 handle: the restypes / argtypes set here don't change anyone else's."""
    if _U[0] is None:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        vp, i, ui = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint
        for name, res, args in (
                ("GetForegroundWindow", vp, []), ("SetForegroundWindow", wintypes.BOOL, [vp]),
                ("ShowWindow", wintypes.BOOL, [vp, i]), ("IsWindow", wintypes.BOOL, [vp]),
                ("SetWindowPos", wintypes.BOOL, [vp, vp, i, i, i, i, ui]),
                ("GetWindowRect", wintypes.BOOL, [vp, ctypes.POINTER(wintypes.RECT)]),
                ("GetWindowThreadProcessId", wintypes.DWORD, [vp, ctypes.POINTER(wintypes.DWORD)]),
                ("GetClassNameW", i, [vp, wintypes.LPWSTR, i]), ("GetWindowTextW", i, [vp, wintypes.LPWSTR, i]),
                ("GetCursorPos", wintypes.BOOL, [ctypes.POINTER(wintypes.POINT)]),
                ("IsWindowVisible", wintypes.BOOL, [vp]), ("IsIconic", wintypes.BOOL, [vp]),
                ("MonitorFromPoint", vp, [wintypes.POINT, wintypes.DWORD])):
            f = getattr(u, name)
            f.restype, f.argtypes = res, args
        for name in ("GetWindowDpiAwarenessContext", "SetThreadDpiAwarenessContext"):     # Win10 1607+
            f = getattr(u, name, None)
            if f is not None:
                f.restype, f.argtypes = vp, [vp]
        _U[0] = u
    return _U[0]


UI_DPI = "gdiscaled"         # the window thread's DPI: "gdiscaled" (Windows scales every window, crisp text) |
                            # "unaware" | "off" (as master). ON (owner-approved): a Read Key press reads the game and
                            # takes its picture in real pixels itself (screenread.game_real / real_pixels)
UI_DPI_SET = [None]         # what pin_ui_dpi did (for the owner's checklist / bug reports)


def pin_ui_dpi():
    """drawer-look (owner: "everything is now scaled strangely"): the window thread's DPI awareness, fixed BEFORE
    Tk makes its first window, so every window of the app - the main one, Settings, dialogs, tooltips, Go to anything,
    Scan stash's review - is scaled by Windows the same way at 100 / 125 / 150 %.
    Why: the process starts DPI-unaware, then the first screen read's mss call (SetProcessDpiAwareness(2)) switched
    the whole process to per-monitor mid-run; every window made after that was drawn 1:1 (smaller) beside a main
    window Windows was scaling - and the Drawer's sizes were read in one space and written in the other.
    A thread's own awareness wins over the process default, so the switch no longer reaches this thread; other
    threads (the Read Key's one-picture thread) keep the process default exactly as before. Windows 10 1607+; a
    no-op elsewhere. -> the context set, or None.
    Screen reading doesn't depend on this thread's DPI: look_page.ev_look reads the game window and the mouse in real
    pixels (screenread.game_real - this thread per-monitor for the two reads, then back), the picture is taken the
    same way (screenread._grab), and a helper's tags are placed in the app's pixels (screenread.to_ui)."""
    if not WIN or UI_DPI == "off":
        return None
    try:
        import ctypes
        u = ctypes.windll.user32
        put = getattr(u, "SetThreadDpiAwarenessContext", None)
        if put is None:
            return None
        put.restype, put.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
        for name, ctx in ((("gdiscaled", -5), ("unaware", -1)) if UI_DPI == "gdiscaled" else (("unaware", -1),)):
            if put(ctypes.c_void_p(ctx)):              # -5 DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED (1809+), -1 UNAWARE
                UI_DPI_SET[0] = name
                return name
    except Exception:
        pass
    return None


def logical(rect, scale):
    """A rect read in real pixels -> the same rect in the app's (Windows-scaled) pixels at `scale` (1.25 = 125 %)."""
    return tuple(int(round(v / float(scale))) for v in rect)


def physical(rect, scale):
    return tuple(int(round(v * float(scale))) for v in rect)


def share_from_drag(width, area):
    """The share a dragged width becomes (_drawer_note_width): width and area are read in the same pixels."""
    return round(clamp_share(width / float(area), area), 4) if area > 0 else SHARE


@contextlib.contextmanager
def root_dpi(hwnd):
    """Every Drawer rect read / write runs in the app window's own DPI awareness (the process may switch to
    per-monitor mid-run - mss does on the first screen read). Restored afterwards; a no-op where unavailable."""
    u, old = None, None
    if WIN and hwnd:
        try:
            u = _user32()
            get = getattr(u, "GetWindowDpiAwarenessContext", None)
            put = getattr(u, "SetThreadDpiAwarenessContext", None)
            if get is not None and put is not None:
                ctx = get(hwnd)
                if ctx:
                    old = put(ctx)
        except Exception:
            old = None
    try:
        yield
    finally:
        if old:
            try:
                u.SetThreadDpiAwarenessContext(old)
            except Exception:
                pass


def pointer_and_rect_physical(hwnd):
    """((x, y) of the mouse, (x, y, w, h) of window hwnd), both read in real pixels (this thread per-monitor-v2 for
    the two reads, then back) - or None where that can't be done. D5 (owner: a STASH item opened the Drawer on the
    LEFT): a DPI-unaware window's GetCursorPos and GetWindowRect needn't agree on a monitor whose scaling differs
    from the main one's; read together in real pixels they always do."""
    if not WIN or not hwnd:
        return None
    try:
        from ctypes import byref, c_void_p, wintypes
        u = _user32()
        put = getattr(u, "SetThreadDpiAwarenessContext", None)
        if put is None:
            return None
        old = put(c_void_p(-4)) or put(c_void_p(-3))                # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, else v1
        if not old:
            return None
        try:
            pt, r = wintypes.POINT(), wintypes.RECT()
            ok = u.GetCursorPos(byref(pt)) and u.GetWindowRect(hwnd, byref(r))
        finally:
            put(old)
        if ok and r.right - r.left > 200 and r.bottom - r.top > 200:
            return (pt.x, pt.y), (r.left, r.top, r.right - r.left, r.bottom - r.top)
    except Exception:
        pass
    return None


_MI = [None]


def _monitor_info(x, y):
    """((work l, t, r, b), (monitor l, t, r, b)) of the monitor holding (x, y) - Windows only, else None."""
    if not WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        if _MI[0] is None:
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]
            u.GetMonitorInfoW.restype = wintypes.BOOL           # (our own handle: style.monitor_rect's argtypes,
            u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]   # with its own struct,
            _MI[0] = MONITORINFO                                 # are on the shared one)
        MONITORINFO = _MI[0]
        h = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)          # MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if h and u.GetMonitorInfoW(h, ctypes.byref(mi)):
            w, m = mi.rcWork, mi.rcMonitor
            return (w.left, w.top, w.right, w.bottom), (m.left, m.top, m.right, m.bottom)
    except Exception:
        pass
    return None


def workspace_origin(rect):
    """The offset SetWindowPlacement's workspace coordinates have on the monitor the rect is on."""
    mi = _monitor_info(rect[0] + rect[2] // 2, rect[1] + 10) if rect else None
    if not mi:
        return 0, 0
    (wl, wt, _r, _b), (ml, mt, _r2, _b2) = mi
    return wl - ml, wt - mt


def cursor_pos(root=None, hwnd=None):
    """The mouse, in the same coordinates as the window rects (hwnd: our window - its DPI awareness, root_dpi)."""
    if CURSOR_HOOK is not None:
        return CURSOR_HOOK()
    if WIN:
        try:
            from ctypes import byref, wintypes
            pt = wintypes.POINT()
            with root_dpi(hwnd):
                ok = _user32().GetCursorPos(byref(pt))
            if ok:
                return pt.x, pt.y
        except Exception:
            pass
    try:
        return root.winfo_pointerxy() if root is not None else None
    except Exception:
        return None


def foreground():
    if not WIN:
        return None
    try:
        return _user32().GetForegroundWindow()
    except Exception:
        return None


def set_foreground(hwnd):
    """Hand the keyboard to a window (the game, or back to whoever had it) - the same call as overlaywin's."""
    if WIN and hwnd:
        try:
            _user32().SetForegroundWindow(hwnd)
        except Exception:
            pass


def _pid_of(hwnd):
    from ctypes import byref, wintypes
    pid = wintypes.DWORD()
    _user32().GetWindowThreadProcessId(hwnd, byref(pid))
    return pid.value


def is_game_window(hwnd, title="Path of Exile 2"):
    """The game's own window class, or a window named exactly the game's title (window names only - ToS)."""
    if not WIN or not hwnd:
        return False
    try:
        import ctypes
        u = _user32()
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if cls.value == "POEWindowClass":
            return True
        buf = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, buf, 256)
        return buf.value.strip().lower() == str(title).strip().lower()
    except Exception:
        return False


def find_game(title="Path of Exile 2"):
    """The game's window handle, or None. EnumWindows: the window's thread only (never the key hook)."""
    if not WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _user32()
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            if u.IsWindowVisible(hwnd) and is_game_window(hwnd, title):
                found.append(hwnd)
                return False
            return True
        u.EnumWindows(cb, 0)
        return found[0] if found else None
    except Exception:
        return None


def fg_state(title="Path of Exile 2"):
    """(ours, game): one of the app's own windows has the keyboard (by process: Go to anything, dialogs and
    dropdowns count) / the game has it. Safe on the hook thread (no EnumWindows, no Tk)."""
    if FG_HOOK is not None:
        ours, game = FG_HOOK()
        return bool(ours), bool(game)
    from .overlay import game_active
    ours = False
    if WIN:
        try:
            h = _user32().GetForegroundWindow()
            ours = bool(h) and _pid_of(h) == os.getpid()
        except Exception:
            ours = False
    elif sys.platform.startswith("linux"):
        try:
            from .linsys import app_in_front
            ours = bool(app_in_front())
        except Exception:
            ours = False
    if ours:                        # (D5: one of ours is in front, so it isn't the game - and game_active's
        return True, False          # GetWindowText on our own window would wait on the window's thread)
    try:
        game = bool(game_active(title))
    except Exception:
        game = False
    return ours, game


_WATCH = [None, 0.0]


def can_watch():
    """Can the foreground be read? Windows: yes. Linux: only on Hyprland (Wayland elsewhere can't tell) - then the
    click-away watcher stays off. (Cached for 5 s: the window's thread asks every tick.)"""
    if FG_HOOK is not None or WIN:
        return True
    import time
    if _WATCH[0] is None or time.time() - _WATCH[1] > 5:
        try:
            from .linsys import app_in_front
            _WATCH[0] = app_in_front() is not None
        except Exception:
            _WATCH[0] = False
        _WATCH[1] = time.time()
    return bool(_WATCH[0])


def game_open_now(title="Path of Exile 2"):
    """Is the game running? (for GAME_OPEN; the window's thread). On Linux only Hyprland can tell - elsewhere it
    counts as not running, so the Drawer key works everywhere."""
    if FG_HOOK is not None:                               # (tests: "the game" is whatever FG_HOOK says)
        return bool(FG_HOOK()[1])
    try:
        if WIN:
            from .overlay import game_open
            return bool(game_open(title))
        if sys.platform.startswith("linux"):
            from .linsys import hypr_socket, game_open as _go
            return hypr_socket() is not None and bool(_go(title))
    except Exception:
        pass
    return False


# ============================================================================ adapters: OUR window only
class TkOnly:
    """Any platform: Tk calls only. A quiet show can't be promised to leave the keyboard where it is."""
    win = False

    def __init__(self, root, hwnd_fn):
        self.root, self.hwnd_fn = root, hwnd_fn

    def hwnd(self):
        return None

    def place(self, rect):
        x, y, w, h = rect
        self.set_geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")

    def set_geometry(self, geo):
        """root.geometry, checked once 150 ms later (X11 with no window manager can drop the move of a move + resize
        - then it's asked again)."""
        self.root.geometry(geo)
        want = geo[geo.find("+"):] if "+" in geo else ""
        if not want:
            return

        def again():
            try:
                g = self.root.wm_geometry()
                if g[g.find("+"):] != want and self.root.state() == "normal":
                    self.root.geometry(geo)
            except Exception:
                pass
        self.root.after(150, again)

    def outer_rect(self):
        r = self.root
        return r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height()

    def show_focused(self, rect):
        if rect and self.root.state() == "zoomed":
            self.root.state("normal")
        if rect:
            self.place(rect)
        if self.root.state() in ("iconic", "withdrawn"):
            self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def show_quiet(self, rect, topmost):
        if rect:
            self.place(rect)
        if self.root.state() in ("iconic", "withdrawn"):
            self.root.deiconify()
        if topmost:
            self.root.attributes("-topmost", True)
        self.root.lift()
        return None

    def quiet_check(self, fg):
        if self.root.state() in ("iconic", "withdrawn"):
            self.root.deiconify()

    def put_away(self, how):
        if how == "withdraw":
            self.root.withdraw()
            return
        self.root.iconify()
        if not WIN:
            try:                                    # (no window manager, or one without minimize - Hyprland: Tk's
                self.root.update_idletasks()        # iconify does nothing there - so it's withdrawn instead)
                if self.root.state() == "normal":
                    self.root.withdraw()
            except Exception:
                pass

    def has_keyboard(self):
        try:
            return self.root.focus_displayof() is not None
        except Exception:
            return False

    def game_hwnd(self, title):
        return None

    def give_back(self, hwnd):
        pass

    def disable_transitions(self):
        pass

    def front(self):
        self.show_focused(None)


class Win32(TkOnly):
    """Windows: the field-tested calls ("Here", unminimize, overlaywin._win_style), each in the window's own DPI."""
    win = True

    def hwnd(self):
        try:
            return self.hwnd_fn()
        except Exception:
            return None

    def _placement(self, h, rect, show_cmd):
        from .app import set_placement                     # (lazy: app imports this module's host)
        set_placement(h, to_workspace(rect, workspace_origin(rect)), False, show=show_cmd)

    def _pos(self, h, rect, flags=0x0010 | 0x0004):          # SWP_NOACTIVATE | SWP_NOZORDER
        x, y, w, hh = (int(v) for v in rect)
        _user32().SetWindowPos(h, None, x, y, w, hh, flags)

    def place(self, rect):
        h = self.hwnd()
        if not h:
            return super().place(rect)
        try:
            with root_dpi(h):
                self._pos(h, rect)
        except Exception:
            super().place(rect)

    def outer_rect(self):
        h = self.hwnd()
        if not h:
            return super().outer_rect()
        try:
            from ctypes import byref, wintypes
            r = wintypes.RECT()
            with root_dpi(h):
                _user32().GetWindowRect(h, byref(r))
            return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:
            return super().outer_rect()

    def show_focused(self, rect):
        """Place it, then Tk's own deiconify / lift / focus_force (the "Here" path, pricecheck_page.py)."""
        h = self.hwnd()
        st = self.root.state()
        if st == "zoomed" and rect:                       # (the Drawer has one size: never maximized)
            self.root.state("normal")
            st = "normal"
        try:
            if rect and h:
                with root_dpi(h):
                    if st in ("iconic", "withdrawn"):
                        self._placement(h, rect, 7 if st == "iconic" else 0)   # SW_SHOWMINNOACTIVE / SW_HIDE: its
                    else:                                                       # normal rect, still put away
                        self._pos(h, rect)
        except Exception:
            pass
        if st in ("iconic", "withdrawn"):
            self.root.deiconify()
        try:
            if rect and h:
                with root_dpi(h):
                    self._pos(h, rect)                    # (exact, whatever the restore did)
        except Exception:
            pass
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def show_quiet(self, rect, topmost):
        """Shown without taking the keyboard: SW_SHOWNOACTIVATE (as unminimize), topmost with SWP_NOACTIVATE, and
        the keyboard handed back if anything took it. -> the window that had the keyboard."""
        h = self.hwnd()
        if not h:
            return super().show_quiet(rect, topmost)
        u = _user32()
        fg = u.GetForegroundWindow()
        try:
            with root_dpi(h):
                if self.root.state() == "withdrawn":
                    u.ShowWindow(h, 7)                     # SW_SHOWMINNOACTIVE (from the tray)
                if rect:
                    self._placement(h, rect, 4)            # SW_SHOWNOACTIVATE
                    self._pos(h, rect)
                elif u.IsIconic(h) or not u.IsWindowVisible(h):
                    u.ShowWindow(h, 4)                     # (as unminimize; D5: a Full window that's already
                                                           # shown is left as it is - SW_SHOWNOACTIVATE would
                                                           # un-maximize it)
                u.SetWindowPos(h, -1 if topmost else 0, 0, 0, 0, 0, 0x0010 | 0x0002 | 0x0001)  # TOPMOST / TOP,
        except Exception:                                                                    # NOACTIVATE|NOMOVE|NOSIZE
            pass
        if fg and u.GetForegroundWindow() != fg:
            u.SetForegroundWindow(fg)                      # (safety net: the overlaywin._win_style pattern)
        return fg

    def quiet_check(self, fg):
        """Risk 1: Tk still thinks it's put away after the Win32 restore -> Tk's deiconify, keyboard back to fg."""
        if self.root.state() in ("iconic", "withdrawn"):
            self.root.deiconify()
            if fg:
                set_foreground(fg)

    def has_keyboard(self):
        try:
            h = _user32().GetForegroundWindow()
            return bool(h) and _pid_of(h) == os.getpid()
        except Exception:
            return False

    def game_hwnd(self, title):
        return find_game(title)

    def give_back(self, hwnd):
        set_foreground(hwnd)

    def disable_transitions(self):
        """No minimize / restore animation (DWMWA_TRANSITIONS_FORCEDISABLED): put away and shown at once. A runtime
        attribute of this window - nothing is saved."""
        h = self.hwnd()
        if not h:
            return
        try:
            import ctypes
            on = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(h), 3, ctypes.byref(on), ctypes.sizeof(on))
        except Exception:
            pass


def adapter(root, hwnd_fn):
    return Win32(root, hwnd_fn) if WIN else TkOnly(root, hwnd_fn)
