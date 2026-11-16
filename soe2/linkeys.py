"""Linux key watchers for KeyWatch (winsys.py) - they only listen, like Windows' hook, and never block a key:

  * X11 / XWayland: the X server's RECORD extension (python-xlib) hears your key presses and releases - on X11 every
    key, under Wayland the keys that go to X windows (the game runs as one under Proton, so the keys you press in it).
    Each press goes to KeyWatch.feed as Windows' key code. Key presses this app sends itself (overlay.py, a chat
    command) are not yours: they're ignored while SENDING says so.
  * The desktop-shortcut socket ($XDG_RUNTIME_DIR/stashofexile2.sock): on a Wayland desktop that keeps keys from
    X windows, bind a key in your desktop's settings to  StashOfExile2 --key "Ctrl+Shift+R"  (Hyprland: bindn, so the
    game still gets it). One message = one key press (down, then up) - it only ever comes from a key you pressed.

GGG policy: a key press opens at most one read (screenread / clipread decide that); a held key's auto-repeat is not a
press - X11 sends a repeat as a release and a press with the same time stamp, and those are dropped here."""
import os
import socket
import threading
import time

from . import buglog

SENDING = [0.0]                     # overlay.py: until when key events are the app's own (xdotool / ydotool)
SOCK_NAME = "stashofexile2.sock"
STATE = {"x11": None, "socket": None}   # what runs: True / an error text / None (not tried)

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
        k = parse_key(text)
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


# ================================================================ start both
def start(kw):
    """KeyWatch.start on Linux: the X key watcher (when there's an X server) and the socket. kw.active when either
    runs; kw.err says why the X one couldn't."""
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
