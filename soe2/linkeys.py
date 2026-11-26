"""Linux key watchers for KeyWatch (winsys.py) - they only listen, like Windows' hook, and never block a key:

  * Hyprland (the main, player-tested setup - issue #235, found and tested by a player on Hyprland 0.56 / Proton):
    for every key in Settings › Keybinds (the Read Key, the price check and copy keys, chat keys ...) the app adds a
    pass-through bind (non-consuming: the key isn't blocked) that writes the key to the app's socket. Added with
    `hyprctl eval 'hl.bind(...)'` (Lua configs), else `hyprctl keyword bindnd` (classic configs), each described
    "SoE2 <key>" so only missing ones are added - your config is never edited. The check is one IPC request
    ("j/binds") every RESYNC_SECS; hyprctl only runs for a bind that's missing. It never reads the screen.

  * X11 / XWayland: the X server's RECORD extension (python-xlib) hears your key presses and releases - on X11 every
    key, under Wayland the keys that go to X windows (the game runs as one under Proton, so the keys you press in it).
    Each press goes to KeyWatch.feed as Windows' key code. Key presses this app sends itself (overlay.py, a chat
    command) are not yours: they're ignored while SENDING says so.
  * The desktop-shortcut socket ($XDG_RUNTIME_DIR/stashofexile2.sock): on a Wayland desktop that keeps keys from
    X windows, bind a key in your desktop's settings to  StashOfExile2 --key "Ctrl+Shift+R"  (Hyprland: bindn, so the
    key isn't blocked). One message = one key press (down, then up) - it only ever comes from a key you pressed.

GGG policy: a key press opens at most one read (screenread / clipread decide that); a held key's auto-repeat is not a
press - X11 sends a repeat as a release and a press with the same time stamp, and those are dropped here."""
import os
import socket
import threading
import time

from . import buglog

HOLD = "0.01"                       # seconds xdotool holds a key it presses
SENDING = [0.0]                     # overlay.py: until when key events are the app's own (xdotool / ydotool)
SOCK_NAME = "stashofexile2.sock"
STATE = {"x11": None, "socket": None, "hypr": None}   # what runs: True / an error text / None (not tried)

# X keysym names -> Windows' key codes (overlay.VK uses those)
_NAMED = {"Return": 0x0D, "KP_Enter": 0x0D, "space": 0x20, "Tab": 0x09, "ISO_Left_Tab": 0x09, "Escape": 0x1B,
          "BackSpace": 0x08, "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x23, "Prior": 0x21,
          "Next": 0x22, "Up": 0x26, "Down": 0x28, "Left": 0x25, "Right": 0x27, "grave": 0xC0, "Pause": 0x13,
          "Break": 0x13, "minus": 0xBD, "equal": 0xBB, "bracketleft": 0xDB, "bracketright": 0xDD,
          "semicolon": 0xBA, "apostrophe": 0xDE, "comma": 0xBC, "period": 0xBE, "slash": 0xBF, "backslash": 0xDC,
          "Shift_L": 0xA0, "Shift_R": 0xA1, "Control_L": 0xA2, "Control_R": 0xA3, "Alt_L": 0xA4, "Alt_R": 0xA5,
          "ISO_Level3_Shift": 0xA5, "Meta_L": 0xA4, "Meta_R": 0xA5,
          "KP_Insert": 0x60, "KP_End": 0x61, "KP_Down": 0x62, "KP_Next": 0x63, "KP_Left": 0x64, "KP_Begin": 0x65,
          "KP_Right": 0x66, "KP_Home": 0x67, "KP_Up": 0x68, "KP_Prior": 0x69}
MOUSE_BUTTONS = {2: 0x04, 8: 0x05, 9: 0x06}     # X buttons: middle, back (Mouse 4), forward (Mouse 5)


def vk_of_keysym(name):
    """An X keysym name ('a', 'F9', 'Control_L', 'KP_5') -> Windows' key code, or None."""
    if not name:
        return None
    if len(name) == 1 and name.isalpha() and name.isascii():
        return ord(name.upper())
    if len(name) == 1 and name.isdigit():
        return ord(name)
    if name[0] == "F" and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x6F + int(name[1:])
    if name.startswith("KP_") and name[3:].isdigit():
        return 0x60 + int(name[3:])
    return _NAMED.get(name)


# keysym names the other way (sending keys with xdotool), and Linux input codes (ydotool)
XNAME = {0x10: "Shift_L", 0x11: "Control_L", 0x12: "Alt_L", 0x0D: "Return", 0x08: "BackSpace", 0x1B: "Escape",
         0x09: "Tab", 0x20: "space"}
EVDEV = {0x10: 42, 0x11: 29, 0x12: 56, 0x0D: 28, 0x08: 14, 0x1B: 1, 0x09: 15, 0x20: 57,
         **{0x41 + i: c for i, c in enumerate((30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50, 49, 24, 25, 16,
                                                19, 31, 20, 22, 47, 17, 45, 21, 44))},
         **{0x31 + i: 2 + i for i in range(9)}, 0x30: 11}


def x_name(vk):
    if vk in XNAME:
        return XNAME[vk]
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return None


def xdotool_args(events):
    """overlay.py's key events [(vk or None, char or None, up)] -> the xdotool runs that press them, in order:
    [["xdotool", "keydown", "Control_L", ...], ["xdotool", "type", "--delay", "0", "--", "text"], ...]."""
    runs, keys, text = [], [], ""
    for vk, ch, up in events:
        if ch:
            if keys:
                runs.append(["xdotool"] + keys)
                keys = []
            if not up:
                text += ch
            continue
        if text:
            runs.append(["xdotool", "type", "--delay", "0", "--", text])
            text = ""
        name = x_name(vk)
        if name:
            if up and vk not in (0x10, 0x11, 0x12) and keys[-1:] == [name]:
                keys += ["sleep", HOLD]                 # (held ~10 ms, like the player-tested build: the game hears it)
            keys += ["keyup" if up else "keydown", name]
    if keys:
        runs.append(["xdotool"] + keys)
    if text:
        runs.append(["xdotool", "type", "--delay", "0", "--", text])
    return runs


def ydotool_args(events):
    """The same for ydotool (Linux input codes: "29:1" down, "29:0" up)."""
    runs, keys, text = [], [], ""
    for vk, ch, up in events:
        if ch:
            if keys:
                runs.append(["ydotool", "key"] + keys)
                keys = []
            if not up:
                text += ch
            continue
        if text:
            runs.append(["ydotool", "type", "--", text])
            text = ""
        if vk in EVDEV:
            keys.append(f"{EVDEV[vk]}:{0 if up else 1}")
    if keys:
        runs.append(["ydotool", "key"] + keys)
    if text:
        runs.append(["ydotool", "type", "--", text])
    return runs


def ours(now=None):
    """Are key events right now the app's own (it is pressing keys for a chat command or a copy)?"""
    return (time.time() if now is None else now) < SENDING[0]


# ================================================================ X11 / XWayland: RECORD
class Repeats:
    """X11 auto-repeat comes as a release + a press with the same time stamp: hold each release until the next event,
    drop the pair when it's a repeat. -> feed(kind, code, t) gives the events to pass on [(kind, code)]."""

    def __init__(self):
        self.pending = None                         # (code, t) of a release not passed on yet

    def feed(self, kind, code, t):
        out = []
        p = self.pending
        if p is not None:
            self.pending = None
            if kind == "down" and code == p[0] and abs(t - p[1]) <= 1:
                return out                          # a repeat: the key never went up (and this isn't a new press)
            out.append(("up", p[0]))
        if kind == "up":
            self.pending = (code, t)
            return out
        out.append((kind, code))
        return out

    def flush(self):
        p, self.pending = self.pending, None
        return [("up", p[0])] if p else []


class XRecordWatch:
    def __init__(self, kw):
        self.kw = kw
        self.ctl = self.data = self.ctx = None
        self.rep = Repeats()

    def open(self):
        """-> '' when listening can start, else why not."""
        if not os.environ.get("DISPLAY"):
            return "no X server (DISPLAY isn't set)"
        try:
            from Xlib import display
        except Exception:
            return "python-xlib is missing"
        try:
            self.ctl, self.data = display.Display(), display.Display()
        except Exception as e:
            return f"can't open the X display ({e.__class__.__name__})"
        if not self.data.has_extension("RECORD"):
            return "the X server has no RECORD extension"
        from Xlib import X
        from Xlib.ext import record
        try:
            self.ctx = self.data.record_create_context(0, [record.AllClients], [{
                "core_requests": (0, 0), "core_replies": (0, 0), "ext_requests": (0, 0, 0, 0),
                "ext_replies": (0, 0, 0, 0), "delivered_events": (0, 0),
                "device_events": (X.KeyPress, X.ButtonRelease), "errors": (0, 0),
                "client_started": False, "client_died": False}])
        except Exception as e:
            return f"the X server refused to listen ({e.__class__.__name__})"
        return ""

    def run(self):
        try:
            self.data.record_enable_context(self.ctx, self._got)
        except Exception as e:
            self.kw.err = f"the X key watcher stopped ({e.__class__.__name__})"
            STATE["x11"] = self.kw.err
        finally:
            try:
                self.data.record_free_context(self.ctx)
            except Exception:
                pass

    def vk(self, keycode):
        name = _keysym_name(self.ctl.keycode_to_keysym(keycode, 0))
        if name and name.startswith("KP_"):          # the keypad: its digit (NumLock on or off)
            n1 = _keysym_name(self.ctl.keycode_to_keysym(keycode, 1))
            if n1 and n1.startswith("KP_") and n1[3:].isdigit():
                name = n1
        return vk_of_keysym(name)

    def _got(self, reply):
        from Xlib import X
        from Xlib.ext import record
        from Xlib.protocol import rq
        if reply.category != record.FromServer or reply.client_swapped or not len(reply.data) or \
                reply.data[0] < 2:
            return
        data = reply.data
        while len(data):
            ev, data = rq.EventField(None).parse_binary_value(data, self.ctl.display, None, None)
            try:
                if ours():
                    continue
                if ev.type in (X.KeyPress, X.KeyRelease):
                    for kind, code in self.rep.feed("down" if ev.type == X.KeyPress else "up", ev.detail, ev.time):
                        vk = self.vk(code)
                        if vk is not None:
                            self.kw.feed(vk, kind == "down", kind == "up")
                elif ev.type in (X.ButtonPress, X.ButtonRelease) and self.kw.mouse_on:
                    vk = MOUSE_BUTTONS.get(ev.detail)
                    if vk is not None:
                        for kind, code in self.rep.flush():
                            v2 = self.vk(code)
                            if v2 is not None:
                                self.kw.feed(v2, False, True)
                        self.kw.feed(vk, ev.type == X.ButtonPress, ev.type == X.ButtonRelease)
            except Exception:
                buglog.caught()


def _keysym_name(ks):
    if not ks:
        return None
    return _keysym_table().get(ks)


_KS = {}


def _keysym_table():
    """keysym value -> its name, for the keys this file knows (letters, digits, F keys, keypad, the named keys)."""
    if not _KS:
        from Xlib import XK
        names = list(_NAMED) + [chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(d) for d in range(10)] + \
            [f"F{i}" for i in range(1, 25)] + [f"KP_{d}" for d in range(10)]
        for n in names:
            v = XK.string_to_keysym(n)
            if v and v not in _KS:
                _KS[v] = n
    return _KS


# ================================================================ the desktop-shortcut socket
def sock_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.join("/tmp", f"stashofexile2-{os.getuid()}")
    return os.path.join(base, SOCK_NAME)


class SocketKeys:
    """One line per key press ("Ctrl+Shift+R") from  StashOfExile2 --key ...  -> KeyWatch.feed: down, then up."""

    def __init__(self, kw, path=None):
        self.kw, self.path, self.srv = kw, path or sock_path(), None

    def open(self):
        try:
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
            if os.path.exists(self.path):
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
                        c.settimeout(0.3)
                        c.connect(self.path)
                    return "another StashOfExile2 is listening"
                except OSError:
                    os.remove(self.path)                    # (left behind by an app that didn't close)
            self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.srv.bind(self.path)
            os.chmod(self.path, 0o600)
            self.srv.listen(4)
            return ""
        except OSError as e:
            return f"can't open {self.path} ({e.__class__.__name__})"

    def run(self):
        while True:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            try:
                with conn:
                    conn.settimeout(0.5)
                    line = conn.recv(64).decode("utf-8", "replace").strip()
                    conn.sendall(b"ok\n" if self.press(line) else b"unknown key\n")
            except OSError:
                continue

    def press(self, text):
        """One key press from the socket: its modifiers down, the key down and up, the modifiers up."""
        from .overlay import parse_key
        if ours():
            return True                                 # (the app's own key presses - not yours)
        k = parse_key(text) or line_key(text)
        if not k:
            return False
        vk, ctrl, alt, shift = k
        mods = [m for m, on in ((0xA2, ctrl), (0xA4, alt), (0xA0, shift)) if on]
        for m in mods:
            self.kw.feed(m, True, False)
        self.kw.feed(vk, True, False)
        self.kw.feed(vk, False, True)
        for m in reversed(mods):
            self.kw.feed(m, False, True)
        return True

    def close(self):
        try:
            if self.srv:
                self.srv.close()
            os.remove(self.path)
        except OSError:
            pass


def send(text, path=None):
    """StashOfExile2 --key "Ctrl+Shift+R": tell the running app you pressed that key. -> 0 done, 1 not understood,
    2 the app isn't running."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
            c.settimeout(1.0)
            c.connect(path or sock_path())
            c.sendall(str(text).encode("utf-8")[:63])
            return 0 if c.recv(32).startswith(b"ok") else 1
    except OSError:
        return 2


# ================================================================ Hyprland: pass-through binds -> the socket
TAG = "SoE2 "                       # every bind the app adds is described "SoE2 <key>"
RESYNC_SECS = 20                    # binds are checked again this often (a config reload drops them)
ALWAYS = ("Ctrl+Alt+C", "Ctrl+C")   # the copy keys: the app must know you pressed them, like on Windows
# our key names (overlay.VK) -> xkb names (what Hyprland and xdotool call them)
XKB = {"esc": "Escape", "escape": "Escape", "enter": "Return", "space": "space", "tab": "Tab",
       "backspace": "BackSpace", "insert": "Insert", "ins": "Insert", "delete": "Delete", "del": "Delete",
       "home": "Home", "end": "End", "pgup": "Prior", "pageup": "Prior", "pgdn": "Next", "pagedown": "Next",
       "up": "Up", "down": "Down", "left": "Left", "right": "Right", "pause": "Pause", "break": "Pause",
       "`": "grave", "-": "minus", "=": "equal", "[": "bracketleft", "]": "bracketright", ";": "semicolon",
       "'": "apostrophe", ",": "comma", ".": "period", "/": "slash", "\\": "backslash"}
HYPR = {"keys": None, "added": [], "have": 0, "want": 0, "err": None, "writer": None}   # the last check (Linux check)
RUN = [None]                        # tests: fn(args) -> (returncode, stdout) instead of running hyprctl


def xkb_name(name):
    """Our key name ("d", "f6", "esc", "numpad3") -> the xkb one ("D", "F6", "Escape", "KP_3")."""
    if name in XKB:
        return XKB[name]
    if name.startswith("numpad"):
        return "KP_" + name[6:]
    if len(name) == 1 or (name[0] == "f" and name[1:].isdigit()):
        return name.upper()
    return name


def key_line(text):
    """A key as Settings › Keybinds shows it ("Ctrl+Shift+R", "F6", "Esc", "Ctrl+;") -> the line its bind writes
    ("ctrl+shift+r", "f6", "escape", "ctrl+semicolon": letters, digits, + and _ only - safe in a shell), or None
    (a mouse button, or not understood)."""
    from .overlay import parse_key, MOUSE_VKS, VK
    k = parse_key(text)
    if not k or k[0] in MOUSE_VKS:
        return None
    name = next((n for n, v in VK.items() if v == k[0]), None)
    if name is None:
        return None
    return "+".join([m for m, on in zip(("ctrl", "alt", "shift"), k[1:]) if on] + [xkb_name(name).lower()])


def line_key(line):
    """The other way: "ctrl+semicolon" -> (vk, ctrl, alt, shift), or None."""
    from .overlay import parse_key
    parts = str(line or "").strip().lower().split("+")
    back = {v.lower(): k for k, v in XKB.items()}
    name = parts[-1]
    name = back.get(name) or ("numpad" + name[3:] if name.startswith("kp_") else name)
    return parse_key("+".join(parts[:-1] + [name]))


def bind_parts(line):
    """"ctrl+shift+r" -> (["CTRL", "SHIFT"], "R"); "escape" -> ([], "Escape")."""
    from .overlay import VK
    parts = line.split("+")
    k = line_key(line)
    name = next((n for n, v in VK.items() if k and v == k[0]), parts[-1])
    return [m.upper() for m in parts[:-1]], xkb_name(name)


def writer(path=None):
    """How a bind tells the app: socat (fast, player-tested), else this app's own  --key  (slower: it starts a
    process each press). -> a shell command with {line} left in, or None."""
    import shlex
    import shutil
    import sys
    path = path or sock_path()
    if shutil.which("socat"):
        return f"echo {{line}} | socat - UNIX-CONNECT:{path}"
    me = [sys.executable] if getattr(sys, "frozen", False) else \
        [sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stashofexile2.py")]
    if not all(os.path.exists(p) for p in me):
        return None
    return " ".join(shlex.quote(p) for p in me) + " --key {line}"


def lua_bind(line, cmd):
    mods, key = bind_parts(line)
    return (f'hl.bind("{"+".join(mods + [key])}", hl.dsp.exec_cmd("{cmd.format(line=line)}"), '
            f'{{ non_consuming = true, description = "{TAG}{line}" }})')


def keyword_bind(line, cmd):
    mods, key = bind_parts(line)
    return f"{' '.join(mods)}, {key}, {TAG}{line}, exec, {cmd.format(line=line)}"


def wanted_lines(keys):
    """Key texts (Settings › Keybinds) -> the lines to bind, no repeats; the copy keys always."""
    out = []
    for t in list(keys) + list(ALWAYS):
        ln = key_line(t) if t else None
        if ln and ln not in out:
            out.append(ln)
    return out


def bound_lines(binds):
    """Hyprland's j/binds -> the lines this app already bound."""
    return {str(b.get("description"))[len(TAG):] for b in binds or [] if isinstance(b, dict)
            and str(b.get("description") or "").startswith(TAG)}


def hyprctl(*args):
    """One hyprctl call -> True when Hyprland took it."""
    import subprocess
    try:
        if RUN[0] is not None:
            code, out = RUN[0](["hyprctl", *args])
        else:
            r = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=3)
            code, out = r.returncode, r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return False
    low = str(out).lower()
    return code == 0 and "error" not in low and "invalid" not in low


def sync_binds(keys, binds=None, path=None):
    """Add the missing pass-through binds (one IPC request to see which are there) -> the lines added."""
    from .linsys import hypr
    if binds is None:
        binds = hypr("j/binds")
    want = wanted_lines(keys)
    HYPR.update(keys=list(keys), want=len(want))
    if not isinstance(binds, list):
        HYPR["err"] = "Hyprland's IPC didn't answer"
        return []
    cmd = writer(path)
    HYPR["writer"] = "socat" if cmd and "socat" in cmd else ("--key" if cmd else None)
    if cmd is None:
        HYPR["err"] = "no socat"
        return []
    have = bound_lines(binds)
    added = []
    for ln in want:
        if ln in have:
            continue
        if hyprctl("eval", lua_bind(ln, cmd)) or hyprctl("keyword", "bindnd", keyword_bind(ln, cmd)):
            added.append(ln)
        else:
            buglog.debug("Keys", f"Hyprland didn't take the bind for {ln}")
    HYPR.update(added=added, have=len([ln for ln in want if ln in have]) + len(added),
                err=None if len(have & set(want)) + len(added) == len(want) else "some binds were refused")
    return added


class HyprBinds:
    """Keeps the binds in place: a check every RESYNC_SECS (a config reload drops them). keys_source: the app's
    keybinds (KeyWatch.keys_source); the first check waits until the app has set it."""

    def __init__(self, kw):
        self.kw = kw

    def run(self):
        while True:
            try:
                src = getattr(self.kw, "keys_source", None)
                if src is not None:
                    added = sync_binds([k for k in src() if k])
                    if added:
                        buglog.debug("Keys", f"Hyprland binds added: {len(added)}")
            except Exception:
                buglog.caught()
            time.sleep(RESYNC_SECS if getattr(self.kw, "keys_source", None) is not None else 1)


# ================================================================ start
def start(kw):
    """KeyWatch.start on Linux. Hyprland: the socket + the pass-through binds (no X11 watcher - it would hear the
    same press twice). Elsewhere: the X key watcher (when there's an X server) and the socket (for desktop
    shortcuts). kw.active when one runs; kw.err says why the X one couldn't."""
    from .linsys import hypr_socket
    if hypr_socket():
        STATE["x11"] = "not used on Hyprland: its pass-through binds tell the app"
        threading.Thread(target=HyprBinds(kw).run, daemon=True, name="soe2-hyprbinds").start()
        STATE["hypr"] = True
    else:
        xw = XRecordWatch(kw)
        why = xw.open()
        if not why:
            threading.Thread(target=xw.run, daemon=True, name="soe2-xrecord").start()
            STATE["x11"] = True
        else:
            STATE["x11"] = why
            kw.err = why
    sk = SocketKeys(kw)
    why2 = sk.open()
    if not why2:
        threading.Thread(target=sk.run, daemon=True, name="soe2-keysock").start()
        STATE["socket"] = True
        import atexit
        atexit.register(sk.close)
    else:
        STATE["socket"] = why2
    kw.active = STATE["x11"] is True or STATE["socket"] is True
    if kw.active and STATE["x11"] is not True:
        kw.err = None
    return kw.active
