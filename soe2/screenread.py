"""The ONE place the app may read your screen (GGG policy, Nov 2026 - see TOS.md).

GGG's rule for tools that use the screen, the clipboard or the game's log: "You may only read this information as long
as the user is aware of what you are doing with that data." and "Reading from the screen or clipboard may only be
performed once per manual key press." The owner's reading is the strictest one, so:
  * grant(key_name)  - the key watcher (App.on_any_key -> look_on_key, on its own thread) calls this when YOU press
                       the Read Key: Ctrl+Shift+R as the app comes, or a key you pick only for this (Settings ›
                       Keybinds; cleared - no Read Key, no reads at all - and never a key the game or the app uses for something else, never
                       a mouse button: a click is not a key press). One grant per physical press: a held key's
                       auto-repeat doesn't grant again - the key has to be let go (release) first.
  * capture(region, purpose) - one screenshot of the game window per grant, taken the first time it's asked for (the
                       Read Key's dispatcher asks at once), and only within GRANT_SECS of the press. Every helper
                       that applies (Ritual, Temple ...) cuts its part out of that same picture - it's never taken
                       twice; a slow helper may still cut from it until finish(). No grant, a press too old to take
                       its picture, or a second picture: None.
  * finish(found)    - after the helpers are done: one plain line in the app's log - "F9 pressed: read the screen
                       once for Ritual, Temple" - SAID is told (the app shows the read mark over the game, readmark.py)
                       and the picture is dropped (it's only ever kept in memory). found=False (no helper could use
                       anything in the picture): the line ends "- nothing found" and the purposes end with NOTHING, so
                       the read mark says "Read the screen · nothing here" - the read still shows.
  * nothing(why)     - a press where no helper applies (decided before any picture): no picture, no read mark, one
                       log line "F9 pressed: nothing to read here (...)".
Nothing here runs by itself: no timer, no loop, no thread of its own (tools/check_tos.py fails the build if one appears,
if any other file uses a capture library, or if anything but the key watcher calls grant).

Real pixels (drawer build, owner-approved DPI fix): the app's windows are drawn in Windows-scaled pixels (the window
thread's DPI is pinned - drawer.pin_ui_dpi), but a press reads in REAL pixels whatever the process's DPI awareness:
game_real() reads the game window and the mouse with this thread set per-monitor for the two reads, and the picture
is taken the same way (_grab). So the capture regions are the same at 100 / 125 / 150 / 175 %. What a helper reads
(boxes on screen) is in real pixels; to_ui() turns them into the app's pixels to place a tag, to_screen() the other
way (the mouse, our own windows) - from the press's game window in both (MAP; identical where they agree)."""
import contextlib
import sys
import threading
import time

GRANT_SECS = 1.5                    # a press lets the helpers read for this long (then the picture is dropped)
DEFAULT_KEY = "Ctrl+Shift+R"        # the Read Key as the app comes (owner); "" in the settings = you cleared it: no key
MOUSE = frozenset((0x01, 0x02, 0x04, 0x05, 0x06))   # mouse buttons: never a read (a click is not a key press)

_LOCK = threading.RLock()
_HELD = set()                       # keys down right now (a held key / auto-repeat grants nothing more)
_STATE = {"grant": None}            # the open grant: {"key", "t", "shot", "box", "tried", "for", "said"}
GRABBER = [None]                    # tests: fn((l, t, r, b)) -> a PIL image of that part of the screen
AREA = [None]                       # the app: fn() -> the game window (x, y, w, h) or None (alerts_page.game_rect)
LOGGER = [None]                     # tests: fn(line); the app's log otherwise
SAID = [None]                       # the app: fn("screen", key, [purposes]) after each read (the read mark)
NOTHING = "nothing found"           # finish(found=False): the last of the purposes (the read mark's words)
ONLY_KEY = [None]                   # the app: fn() -> the Read Key's key code (None = no key). grant() refuses any other key
COUNT = {"grants": 0, "shots": 0, "refused": 0}   # (the runtime test reads these)


def _log(line):
    fn = LOGGER[0]
    if fn is not None:
        fn(line)
        return
    try:
        from . import buglog
        buglog.record("read", line)
    except Exception:
        pass


def grant(key_name, hold=None, now=None):
    """A real key-down of the Read Key (the key watcher only). key_name: the words for the log ("F9"); hold: what the
    key's release is told by (the key watcher's key code; key_name when not given). -> True if it opened a new grant,
    False for a key that's still held (Windows repeats a held key's key-down: those are not presses) or a mouse
    button."""
    now = time.time() if now is None else now
    hold = key_name if hold is None else hold
    if hold in MOUSE:
        return False
    fn = ONLY_KEY[0]
    if fn is not None:                              # the one key: nothing but the Read Key opens a read (runtime gate)
        try:
            only = fn()
        except Exception:
            only = None
        if only is None or hold != only:
            COUNT["refused"] += 1
            return False
    with _LOCK:
        if hold in _HELD:
            return False
        _HELD.add(hold)
        finish()                                    # (the last press's line, if a helper didn't finish it)
        _STATE["grant"] = {"key": key_name, "t": now, "shot": None, "box": None, "tried": False, "for": [],
                           "said": False}
        COUNT["grants"] += 1
        return True


def release(hold):
    """The key went up (its key code, or the name it was granted with): its next key-down is a new press."""
    with _LOCK:
        _HELD.discard(hold)


def active(now=None):
    """A press is open (and young enough) to read the screen once."""
    now = time.time() if now is None else now
    with _LOCK:
        g = _STATE["grant"]
        return bool(g) and now - g["t"] <= GRANT_SECS and not g["said"]


def pressed_key():
    with _LOCK:
        g = _STATE["grant"]
        return g["key"] if g else None


# ---------------------------------------------------------------- real pixels (the DPI fix)
USER32 = [None]                     # tests: a stand-in for Windows' user32 (None: the real one on Windows)
MAP = [None]                        # the last press: (game window in real pixels, the same in the app's) - (x, y, w, h)
REAL_CTX = (-4, -3)                 # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, else PER_MONITOR_AWARE (Win10 1607+)
_REAL_U = [None]


def _user32():
    if USER32[0] is not None:
        return USER32[0]
    if sys.platform != "win32":
        return None
    if _REAL_U[0] is None:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")                 # (its own handle: other files set other argtypes on windll's)
        vp = ctypes.c_void_p
        for name, res, args in (("FindWindowW", vp, [wintypes.LPCWSTR, wintypes.LPCWSTR]),
                                ("IsWindowVisible", wintypes.BOOL, [vp]),
                                ("GetWindowRect", wintypes.BOOL, [vp, ctypes.POINTER(wintypes.RECT)]),
                                ("GetCursorPos", wintypes.BOOL, [ctypes.POINTER(wintypes.POINT)])):
            f = getattr(u, name)
            f.restype, f.argtypes = res, args
        f = getattr(u, "SetThreadDpiAwarenessContext", None)
        if f is not None:
            f.restype, f.argtypes = vp, [vp]
        _REAL_U[0] = u
    return _REAL_U[0]


@contextlib.contextmanager
def real_pixels():
    """This thread reads in real pixels for the block (per-monitor DPI awareness), then goes back to what it was.
    Yields True when it could (Windows 10 1607+), False otherwise (then nothing changed)."""
    u, old = _user32(), None
    put = getattr(u, "SetThreadDpiAwarenessContext", None) if u is not None else None
    if put is not None:
        import ctypes
        for ctx in REAL_CTX:
            try:
                old = put(ctypes.c_void_p(ctx))
            except Exception:
                old = None
            if old:
                break
    try:
        yield bool(old)
    finally:
        if old:
            try:
                import ctypes
                put(ctypes.c_void_p(old))
            except Exception:
                pass


def game_real(title="Path of Exile 2"):
    """-> ((x, y) of the mouse, (x, y, w, h) of the game window), both read in real pixels, or None (not Windows,
    no such window, or a Windows too old to read them so)."""
    u = _user32()
    if u is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = u.FindWindowW(None, title)
        if not hwnd or not u.IsWindowVisible(hwnd):
            return None
        pt, r = wintypes.POINT(), wintypes.RECT()
        with real_pixels() as ok:
            if not ok:
                return None
            if not (u.GetCursorPos(ctypes.byref(pt)) and u.GetWindowRect(hwnd, ctypes.byref(r))):
                return None
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 200 or h <= 200:
            return None
        return (pt.x, pt.y), (r.left, r.top, w, h)
    except Exception:
        return None


def set_map(real, app):
    """The press's game window in real pixels and in the app's (x, y, w, h each) - what to_ui / to_screen go by."""
    MAP[0] = (tuple(int(v) for v in real), tuple(int(v) for v in app)) if real and app and real[2] > 0 and \
        real[3] > 0 and app[2] > 0 and app[3] > 0 else None


def ui_scale():
    """(x, y): how many of the app's pixels one real pixel is (1.0 at 100 %, 0.8 at 125 % ...)."""
    m = MAP[0]
    if not m:
        return 1.0, 1.0
    (_rx, _ry, rw, rh), (_ax, _ay, aw, ah) = m
    return aw / float(rw), ah / float(rh)


def _conv(v, frm, to):
    fx, fy, fw, fh = frm
    tx, ty, tw, th = to
    kx, ky = tw / float(fw), th / float(fh)
    v = tuple(v)
    pts = [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
    return tuple(int(round(c)) for x, y in pts for c in (tx + (x - fx) * kx, ty + (y - fy) * ky))


def to_ui(v):
    """A point (x, y) or a box (left, top, right, bottom) on screen in real pixels -> the same in the app's pixels."""
    m = MAP[0]
    return tuple(int(c) for c in v) if not m or m[0] == m[1] else _conv(v, m[0], m[1])


def to_screen(v):
    """A point or box in the app's pixels (the mouse, our own windows) -> the same in real pixels."""
    m = MAP[0]
    return tuple(int(c) for c in v) if not m or m[0] == m[1] else _conv(v, m[1], m[0])


def _game_box(region):
    """The press's one picture: the whole game window, in real pixels (game_real; AREA where that can't be read)."""
    real = game_real()
    g = real[1] if real else None
    fn = AREA[0]
    try:
        g = g or (fn() if fn is not None else None)
    except Exception:
        g = None
    if g:
        x, y, w, h = g
        return int(x), int(y), int(x + w), int(y + h)
    return tuple(int(v) for v in region)


# ---------------------------------------------------------------- Linux: which tool takes the press's one picture
CAPTURE_TOOLS = ("mss", "grim", "spectacle", "gnome-screenshot")
CAPTURE_PKG = {"grim": "grim", "spectacle": "spectacle (KDE)", "gnome-screenshot": "gnome-screenshot"}


def capture_tool(env=None, path=None):
    """Linux: the one way this app takes a picture - decided from the session, never by trying (nothing is read here):
      X11 (and anything with an X server): "mss" (X11's own XGetImage);
      Wayland: "grim" (wlroots: Hyprland, sway ...), "spectacle" (KDE), "gnome-screenshot" (GNOME), else "mss"
      through XWayland (the game runs there under Proton - it may come out black on some desktops).
    SOE2_CAPTURE=<one of CAPTURE_TOOLS> picks one by hand. -> (tool, why) or (None, why)."""
    import os
    from . import linsys as L
    env = os.environ if env is None else env
    forced = str(env.get("SOE2_CAPTURE") or "").strip()
    if forced in CAPTURE_TOOLS:
        return (forced, "picked with SOE2_CAPTURE") if forced == "mss" or L.which(forced, path) else \
            (None, f"SOE2_CAPTURE={forced}, but {forced} isn't installed")
    sess, desk = L.session_type(env), L.desktop(env).lower()
    if sess == "wayland":
        if desk in ("gnome", "ubuntu", "pop") and L.which("gnome-screenshot", path):
            return "gnome-screenshot", "GNOME on Wayland"
        if desk in ("kde", "plasma") and L.which("spectacle", path):
            return "spectacle", "KDE on Wayland"
        if L.which("grim", path) and desk not in ("gnome", "ubuntu", "pop", "kde", "plasma"):
            return "grim", "Wayland (wlroots)"
        if L.has_x(env):
            return "mss", "Wayland through XWayland (may be black - see linux/README.md)"
        return None, "Wayland with no capture tool (install grim, or use an X11 session)"
    if L.has_x(env):
        return "mss", "X11"
    return None, "no desktop session"


def capture_check(env=None, path=None):
    """The Linux check's line for the press's one picture: (state "ok" / "warn" / "fix", what, how to fix). It says
    which tool would be used - it takes no picture."""
    tool, why = capture_tool(env, path)
    if tool is None:
        return "fix", why, ("install grim (Hyprland, sway), spectacle (KDE) or gnome-screenshot (GNOME) - or log in "
                            "with an X11 session")
    if tool == "mss":
        import importlib.util
        if importlib.util.find_spec("mss") is None:
            return "fix", "the mss module is missing", "pip install mss (the release build has it)"
        if "XWayland" in why:
            return "warn", f"mss - {why}", ("if the helpers read nothing: install grim / spectacle / "
                                            "gnome-screenshot, or log in with an X11 session")
        return "ok", f"mss ({why})", ""
    return "ok", f"{tool} ({why})", ""


def _grab_linux(box):
    """One picture of box (real pixels) on Linux, with capture_tool()'s one tool. -> PIL image or None."""
    import io
    import os
    import subprocess
    import tempfile
    from PIL import Image
    tool, _why = capture_tool()
    l_, t, r, b = (int(v) for v in box)
    if tool in (None, "mss"):
        return None if tool is None else _grab_mss(box)
    if tool == "grim":
        out = subprocess.run(["grim", "-g", f"{l_},{t} {r - l_}x{b - t}", "-"], capture_output=True, timeout=5)
        return Image.open(io.BytesIO(out.stdout)).convert("RGB") if out.returncode == 0 and out.stdout else None
    fd, tmp = tempfile.mkstemp(suffix=".png", dir=os.environ.get("XDG_RUNTIME_DIR") or None)
    os.close(fd)
    try:                                            # (the whole screen to a private file, cut, file deleted at once)
        args = ["spectacle", "-b", "-n", "-f", "-o", tmp] if tool == "spectacle" else ["gnome-screenshot", "-f", tmp]
        subprocess.run(args, capture_output=True, timeout=8)
        with Image.open(tmp) as im:
            return im.convert("RGB").crop((l_, t, r, b))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _grab_mss(box):
    import mss
    from PIL import Image
    l_, t, r, b = box
    with (getattr(mss, "MSS", None) or mss.mss)() as one:
        shot = one.grab({"left": int(l_), "top": int(t), "width": int(r - l_), "height": int(b - t)})
    return Image.frombytes("RGB", shot.size, shot.rgb)


def _grab(box):
    with real_pixels():                             # (real pixels, whatever the process's DPI awareness)
        fn = GRABBER[0]
        if fn is not None:
            return fn(box)
        if sys.platform.startswith("linux"):
            try:
                return _grab_linux(box)
            except Exception:
                return None
        import mss
        from PIL import Image
        l_, t, r, b = box
        with mss.mss() as one:
            shot = one.grab({"left": int(l_), "top": int(t), "width": int(r - l_), "height": int(b - t)})
        return Image.frombytes("RGB", shot.size, shot.rgb)


def capture(region, purpose, now=None):
    """(left, top, right, bottom) of the screen -> that part of this press's one picture (a PIL image), or None (no
    press, too late, or the part isn't in the picture). The first call of a press takes the picture - of the whole
    game window - every later call cuts from it."""
    now = time.time() if now is None else now
    with _LOCK:
        g = _STATE["grant"]
        if not g or g["said"]:
            return None
        if g["shot"] is None:
            if g["tried"] or now - g["t"] > GRANT_SECS:
                return None                         # one picture per press, even when it failed
            g["tried"] = True
            box = _game_box(region)
            if box[2] <= box[0] or box[3] <= box[1]:
                return None
            g["shot"], g["box"] = _grab(box), box
            COUNT["shots"] += 1
            if g["shot"] is None:                   # (Linux: the capture tool gave nothing - no retry)
                return None
        for p in str(purpose or "").split(", "):        # ("Temple, Ritual Identifier": two helpers, one part)
            if p and p not in g["for"]:
                g["for"].append(p)
        bx, by, br, bb = g["box"]
        l_, t, r, b = (int(v) for v in region)
        l_, t, r, b = max(l_, bx), max(t, by), min(r, br), min(b, bb)
        if r <= l_ or b <= t:
            return None
        shot = g["shot"]
        if (l_, t, r, b) == (bx, by, br, bb):
            return shot.copy()
        return shot.crop((l_ - bx, t - by, r - bx, b - by))


def finish(found=True):
    """The helpers are done with this press: one line in the app's log, and the picture goes. found=False: none of
    them could use anything in it (still said: the screen was read)."""
    with _LOCK:
        g = _STATE["grant"]
        if not g or g["said"]:
            return None
        g["said"] = True
        line = None
        if g["shot"] is not None:
            line = f"{g['key']} pressed: read the screen once for {', '.join(g['for']) or 'the helpers'}"
            if not found:
                line += " - " + NOTHING
        g["shot"] = None
        key, what = g["key"], list(g["for"]) or ["the helpers"]
        if not found:
            what.append(NOTHING)
    if line:
        _log(line)
        fn = SAID[0]
        if fn is not None:
            try:
                fn("screen", key, what)
            except Exception:
                pass
    return line


def nothing(why="no helper applies here"):
    """A press where nothing applies (decided BEFORE any picture - look_page.ev_look): the press is closed with no
    picture, one plain line goes in the app's log ("Ctrl+Shift+R pressed: nothing to read here ...") and the read mark
    isn't told - nothing was read. A press whose picture was taken is never hidden: finish() says so as usual."""
    with _LOCK:
        g = _STATE["grant"]
        if not g or g["said"]:
            return None
        shot = g["shot"] is not None
        if not shot:
            g["said"] = True
            line = f"{g['key']} pressed: nothing to read here ({why}) - the screen wasn't read"
    if shot:
        return finish()
    _log(line)
    return line


def reset():
    """(tests) No grant, no key held."""
    with _LOCK:
        _HELD.clear()
        _STATE["grant"] = None
        COUNT["grants"] = COUNT["shots"] = 0
