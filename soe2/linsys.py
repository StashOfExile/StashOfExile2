"""Linux: the game window, the session, the tools the app can use, and where Client.txt is. Not used on Windows:
every caller checks sys.platform first. See linux/README.md.

- the game window: Hyprland's own IPC socket when it runs ($XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/
  .socket.sock, "j/activewindow" / "j/clients" - no `hyprctl` per poll), else X11's window manager hints (EWMH:
  _NET_ACTIVE_WINDOW, _NET_CLIENT_LIST - python-xlib, one shared connection). Under Wayland the game (Steam / Proton)
  is an XWayland window, so the X11 hints work there too on GNOME and KDE while the game is in front.
- Path of Exile 2 is found by its Proton window class (steam_app_2694490) or a window named exactly
  "Path of Exile 2" - window names and classes only, nothing in the game is looked at.
- the session (X11 / Wayland), the desktop, the distro (for the one-line install hint) and which helper tools are
  on PATH (tesseract, xclip / xsel / wl-paste, xdotool / ydotool). Screen capture tools are picked in screenread.py
  only (tools/check_tos.py).
- where Steam keeps Client.txt (native, ~/.steam, Flatpak, every library in libraryfolders.vdf) and the usual Wine /
  Lutris prefixes for the standalone client.

When nothing can tell: game_active() is False, game_open() is True (don't block anything) and game_rect() is None."""
import json
import os
import re
import shutil
import socket
import threading
import time

GAME_CLASS = "steam_app_2694490"
GAME_TITLE = "Path of Exile 2"
STEAM_ROOTS = ["~/.local/share/Steam", "~/.steam/steam", "~/.steam/root", "~/.steam/debian-installation",
               "~/.var/app/com.valvesoftware.Steam/.local/share/Steam",
               "~/.var/app/com.valvesoftware.Steam/data/Steam", "~/snap/steam/common/.local/share/Steam"]
LOG_REL = os.path.join("steamapps", "common", "Path of Exile 2", "logs", "Client.txt")
# the standalone client under Wine / Lutris / Bottles (drive_c of a prefix)
PREFIXES = ["~/.wine", "~/Games/path-of-exile-2", "~/Games/path-of-exile", "~/Games/Path of Exile 2",
            "~/.local/share/lutris/prefixes/path-of-exile-2",
            "~/.var/app/com.usebottles.bottles/data/bottles/bottles/Path-of-Exile-2"]
PREFIX_REL = [os.path.join("drive_c", "Program Files (x86)", "Grinding Gear Games", "Path of Exile 2", "logs",
                           "Client.txt"),
              os.path.join("drive_c", "Program Files", "Grinding Gear Games", "Path of Exile 2", "logs", "Client.txt")]


# ================================================================ the session
def session_type(env=None):
    """-> "x11", "wayland" or "unknown" (no desktop: a terminal or a test)."""
    env = os.environ if env is None else env
    t = str(env.get("XDG_SESSION_TYPE") or "").strip().lower()
    if t in ("x11", "wayland"):
        return t
    if env.get("WAYLAND_DISPLAY"):
        return "wayland"
    if env.get("DISPLAY"):
        return "x11"
    return "unknown"


def has_x(env=None):
    """An X server to talk to: X11 itself, or XWayland under Wayland (the game runs there through Proton)."""
    env = os.environ if env is None else env
    return bool(env.get("DISPLAY"))


def desktop(env=None):
    """'GNOME', 'KDE', 'Hyprland', 'sway' ... or ''."""
    env = os.environ if env is None else env
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    if env.get("SWAYSOCK"):
        return "sway"
    return str(env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or "").split(":")[0]


def which(name, path=None):
    """The tool's full path when it's on PATH, else None."""
    try:
        return shutil.which(name, path=path)
    except Exception:
        return None


def first_tool(names, path=None):
    """The first of names on PATH -> its name, or None."""
    return next((n for n in names if which(n, path)), None)


def clipboard_tool(env=None, path=None):
    """The tool clipread.py reads / writes the clipboard with: "wl-paste" (Wayland), "xclip", "xsel", or None (then
    Tk's own clipboard, X11 / XWayland only)."""
    order = ("wl-paste", "xclip", "xsel") if session_type(env) == "wayland" else ("xclip", "xsel", "wl-paste")
    for n in order:
        if n == "wl-paste" and not (which("wl-paste", path) and which("wl-copy", path)):
            continue
        if which(n, path):
            return n
    return None


def key_tool(env=None, path=None):
    """The tool overlay.py presses the game's keys with: "xdotool" (X11, and XWayland - the game under Proton),
    "ydotool" (any session; needs its ydotoold service), or None."""
    if has_x(env) and which("xdotool", path):
        return "xdotool"
    if which("ydotool", path):
        return "ydotool"
    return None


# ================================================================ the distro (for one-line install hints)
PKGS = {"tesseract": {"debian": "tesseract-ocr", "fedora": "tesseract tesseract-langpack-eng",
                      "arch": "tesseract tesseract-data-eng", "suse": "tesseract-ocr tesseract-ocr-traineddata-english"},
        "xclip": {"debian": "xclip", "fedora": "xclip", "arch": "xclip", "suse": "xclip"},
        "wl-clipboard": {"debian": "wl-clipboard", "fedora": "wl-clipboard", "arch": "wl-clipboard",
                         "suse": "wl-clipboard"},
        "xdotool": {"debian": "xdotool", "fedora": "xdotool", "arch": "xdotool", "suse": "xdotool"},
        "ydotool": {"debian": "ydotool", "fedora": "ydotool", "arch": "ydotool", "suse": "ydotool"},
        "python3-xlib": {"debian": "python3-xlib", "fedora": "python3-xlib", "arch": "python-xlib",
                         "suse": "python3-python-xlib"}}
INSTALL = {"debian": "sudo apt install", "fedora": "sudo dnf install", "arch": "sudo pacman -S",
           "suse": "sudo zypper install"}
FAMILIES = (("debian", ("debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "kali", "neon")),
            ("fedora", ("fedora", "rhel", "centos", "nobara", "bazzite", "rocky", "almalinux")),
            ("arch", ("arch", "manjaro", "endeavouros", "cachyos", "garuda", "steamos")),
            ("suse", ("suse", "opensuse", "opensuse-tumbleweed", "opensuse-leap")))


def distro(path="/etc/os-release"):
    """-> "debian", "fedora", "arch", "suse" or None, from /etc/os-release (ID and ID_LIKE)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    ids = []
    for key in ("ID", "ID_LIKE"):
        m = re.search(rf'^{key}="?([^"\n]*)"?$', text, re.M)
        if m:
            ids += m.group(1).lower().split()
    for fam, names in FAMILIES:
        if any(i in names or i.startswith(fam) for i in ids):
            return fam
    return None


def install_cmd(pkg, fam=None):
    """'tesseract' -> "sudo apt install tesseract-ocr" for this distro (fam=None: read it), or the three usual ones
    joined with " / " when the distro isn't known."""
    names = PKGS.get(pkg, {})
    fam = distro() if fam is None else fam
    if fam in INSTALL:
        return f"{INSTALL[fam]} {names.get(fam, pkg)}"
    return install_all(pkg)


def install_all(pkg):
    """Every distro's line: "sudo apt install tesseract-ocr / sudo dnf install tesseract / sudo pacman -S tesseract"."""
    names = PKGS.get(pkg, {})
    return " / ".join(f"{INSTALL[f]} {names.get(f, pkg)}" for f in ("debian", "fedora", "arch"))


# ================================================================ Hyprland
def hypr_socket():
    """-> path of Hyprland's command socket, or None when not running under Hyprland."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        return None
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    for p in (os.path.join(base, "hypr", sig, ".socket.sock"), os.path.join("/tmp", "hypr", sig, ".socket.sock")):
        if os.path.exists(p):
            return p
    return None


def hypr(cmd, timeout=0.3):
    """Send one IPC command ("j/activewindow") -> parsed JSON, or None."""
    path = hypr_socket()
    if not path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            s.sendall(cmd.encode())
            chunks = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                chunks.append(b)
        return json.loads(b"".join(chunks).decode("utf-8", "replace") or "null")
    except (OSError, ValueError):
        return None


# ================================================================ X11 / XWayland (EWMH)
_X = {"d": None, "tried": False, "atoms": {}}
_XLOCK = threading.RLock()
XLIB = [None]                       # tests: a stand-in for the X calls - an object with active(), clients(),
#                                     info(wid) and rect(wid)


class _XReal:
    """The window manager's hints over one shared python-xlib connection (calls are serialized by _XLOCK)."""

    def __init__(self, d):
        self.d = d
        self.root = d.screen().root

    def atom(self, name):
        a = _X["atoms"].get(name)
        if a is None:
            a = _X["atoms"][name] = self.d.intern_atom(name)
        return a

    def prop(self, win, name):
        from Xlib import X
        p = win.get_full_property(self.atom(name), X.AnyPropertyType)
        return None if p is None else p.value

    def supported(self):
        return self.prop(self.root, "_NET_SUPPORTING_WM_CHECK") is not None or \
            self.prop(self.root, "_NET_ACTIVE_WINDOW") is not None

    def active(self):
        v = self.prop(self.root, "_NET_ACTIVE_WINDOW")
        return int(v[0]) if v is not None and len(v) and int(v[0]) else None

    def clients(self):
        v = self.prop(self.root, "_NET_CLIENT_LIST")
        return [int(w) for w in v] if v is not None else []

    def info(self, wid):
        w = self.d.create_resource_object("window", wid)
        cls = w.get_wm_class() or ("", "")
        title = self.prop(w, "_NET_WM_NAME")
        if title is None:
            title = self.prop(w, "WM_NAME")
        if isinstance(title, bytes):
            title = title.decode("utf-8", "replace")
        pid = self.prop(w, "_NET_WM_PID")
        return {"id": wid, "initialClass": cls[0] or "", "class": cls[1] or "", "title": str(title or ""),
                "pid": int(pid[0]) if pid is not None and len(pid) else None}

    def rect(self, wid):
        w = self.d.create_resource_object("window", wid)
        g = w.get_geometry()
        t = self.root.translate_coords(w, 0, 0)
        return int(t.x), int(t.y), int(g.width), int(g.height)


def _x():
    """The X calls (python-xlib), or None: no DISPLAY, no python-xlib, or the server refused."""
    if XLIB[0] is not None:
        return XLIB[0]
    with _XLOCK:
        if not _X["tried"]:
            _X["tried"] = True
            if has_x():
                try:
                    from Xlib import display
                    _X["d"] = _XReal(display.Display())
                except Exception:
                    _X["d"] = None
        return _X["d"]


def _xcall(fn, default=None):
    x = _x()
    if x is None:
        return default
    with _XLOCK:
        try:
            return fn(x)
        except Exception:
            return default


def x_can_tell():
    """Does the window manager say which window is in front (EWMH)? (No: Xvfb without one, or no X at all.)"""
    now = time.time()
    if XLIB[0] is None and _X.get("sup_t") and now - _X["sup_t"] < 5:
        return _X["sup"]
    ok = bool(_xcall(lambda x: x.supported(), False))
    if XLIB[0] is None:                                 # (a test's stand-in never fills the real cache)
        _X["sup"], _X["sup_t"] = ok, now
    return ok


def can_tell():
    """Can the app tell which window is in front - Hyprland's socket, or the X11 hints?"""
    return hypr_socket() is not None or x_can_tell()


def x_systray():
    """Is there a system tray to put an icon in (X11's _NET_SYSTEM_TRAY_S0 has an owner)? GNOME has none without its
    AppIndicator extension - then the app never hides itself in a tray that isn't there."""
    def get(x):
        from Xlib import X
        return x.d.get_selection_owner(x.atom(f"_NET_SYSTEM_TRAY_S{x.d.get_default_screen()}")) != X.NONE
    return bool(_xcall(get, False))


def x_active_window():
    def get(x):
        wid = x.active()
        return x.info(wid) if wid else None
    return _xcall(get)


def x_clients():
    def get(x):
        out = []
        for wid in x.clients():
            try:
                out.append(x.info(wid))
            except Exception:
                continue
        return out
    return _xcall(get, [])


def x_rect(wid):
    return _xcall(lambda x: x.rect(wid))


# ================================================================ the game window (either)
def is_game(win, title=GAME_TITLE):
    """A window (Hyprland's or X11's dict) is Path of Exile 2: Proton's class, or named exactly the game's title."""
    if not isinstance(win, dict):
        return False
    if win.get("class") == GAME_CLASS or win.get("initialClass") == GAME_CLASS:
        return True
    want = (title or GAME_TITLE).strip().lower()
    return str(win.get("title") or "").strip().lower() == want


def active_window():
    if hypr_socket() is not None:
        w = hypr("j/activewindow")
        return w if isinstance(w, dict) and w else None
    if x_can_tell():
        return x_active_window()
    return None


def game_window(title=GAME_TITLE):
    if hypr_socket() is not None:
        clients = hypr("j/clients")
        if not isinstance(clients, list):
            return None
        return next((c for c in clients if is_game(c, title)), None)
    if x_can_tell():
        return next((c for c in x_clients() if is_game(c, title)), None)
    return None


def game_active(title=GAME_TITLE):
    """Is the game the window in front? False when nothing can tell."""
    return is_game(active_window(), title)


def game_open(title=GAME_TITLE):
    """Is the game running? True when we can't tell (don't block anything)."""
    if not can_tell():
        return True
    return game_window(title) is not None


def game_rect(title=GAME_TITLE):
    """-> (left, top, width, height) of the game window, or None."""
    w = game_window(title)
    if not w:
        return None
    if "at" in w:                                       # Hyprland
        try:
            (x, y), (ww, hh) = w["at"], w["size"]
            return int(x), int(y), int(ww), int(hh)
        except (TypeError, KeyError, ValueError):
            return None
    r = x_rect(w.get("id")) if w.get("id") else None
    return r if r and r[2] > 0 and r[3] > 0 else None


def app_in_front(pid=None):
    """Is one of this app's own windows in front? None when we can't tell."""
    w = active_window()
    if w is None:
        return None
    return w.get("pid") == (pid or os.getpid())


# ================================================================ Client.txt
def steam_libraries(roots=None):
    """Every Steam library folder: the Steam roots plus the paths in steamapps/libraryfolders.vdf."""
    out = []
    for r in roots or STEAM_ROOTS:
        r = os.path.expanduser(r)
        if not os.path.isdir(r):
            continue
        out.append(r)
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="replace") as f:
                out += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        except OSError:
            pass
    seen, uniq = set(), []
    for p in out:
        k = os.path.realpath(p)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def log_candidates(roots=None, prefixes=None):
    """Where Client.txt may be on Linux: every Steam library (Proton), then the usual Wine / Lutris prefixes."""
    out = [os.path.join(lib, LOG_REL) for lib in steam_libraries(roots)]
    for p in (PREFIXES if prefixes is None else prefixes):
        out += [os.path.join(os.path.expanduser(p), rel) for rel in PREFIX_REL]
    return out


def find_log(roots=None, prefixes=None):
    """The first Client.txt that exists, or None."""
    return next((p for p in log_candidates(roots, prefixes) if os.path.isfile(p)), None)
