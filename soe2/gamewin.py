"""3.3.0 owner: Settings › Advanced › Over the game had a box to type the game window's title. Detect finds it.

titles()  - the titles of the windows open now, the game's first when it is open.
detect()  - the game's window title, or "" when the game is not open. The game is told by its window class, so a
            window renamed by a translation or a launcher is still found.

Only window titles and classes are read, the same as the overlay does to know the game is in front. Nothing is
read from the game itself and nothing is sent to it."""
import sys

GAME_CLASS = "POEWindowClass"
MAX_TITLES = 60


def _windows_list():
    """(title, class) of every visible window with a title. Windows only."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hwnd, cls, 64)
        if buf.value.strip():
            out.append((buf.value.strip(), cls.value))
        return len(out) < MAX_TITLES * 4
    u.EnumWindows(cb, 0)
    return out


def _linux_list():
    from . import linsys as L
    wins = []
    try:
        if L.hypr_socket() is not None:
            wins = L.hypr("j/clients") or []
        elif L.sway_available():
            wins = L.sway_windows()
        elif L.x_can_tell():
            wins = L.x_clients()
    except Exception:
        wins = []
    out = []
    for w in wins if isinstance(wins, list) else []:
        if isinstance(w, dict) and str(w.get("title") or "").strip():
            game = L.is_game(w, "")
            out.append((str(w["title"]).strip(), GAME_CLASS if game else str(w.get("class") or "")))
    return out


def windows(lister=None):
    """[(title, class)] of the open windows, or [] when this PC cannot tell."""
    try:
        if lister is not None:
            return list(lister())
        if sys.platform == "win32":
            return _windows_list()
        if sys.platform.startswith("linux"):
            return _linux_list()
    except Exception:
        from . import buglog
        buglog.caught()
    return []


def detect(lister=None):
    """The game's window title, or ""."""
    return next((t for t, cls in windows(lister) if cls == GAME_CLASS), "")


def titles(lister=None, own="Stash"):
    """Open windows' titles for the picker: the game's first, the app's own left out, each once."""
    seen, game, rest = set(), [], []
    for t, cls in windows(lister):
        if t in seen or (own and t.startswith(own)):
            continue
        seen.add(t)
        (game if cls == GAME_CLASS else rest).append(t)
    return (game + sorted(rest, key=str.lower))[:MAX_TITLES]
