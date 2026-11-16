"""The ONE place the app may use your clipboard (GGG policy, Nov 2026 - see TOS.md: "Reading from the screen or
clipboard may only be performed once per manual key press").

The strictest reading (owner): any clipboard call on a timer counts as reading, and a click is not a key press. So
nothing here runs by itself, nothing else in the app touches the clipboard's API (tools/check_tos.py), and:
  * grant(key_name, hold, kind) - the key watcher (KeyWatch -> App.on_any_key, on its own thread) calls this on a
                 copy key's real key-down while the game is in front: your Ctrl+C / Ctrl+Alt+C, the price check key,
                 the Top Up key ("copy"), or a chat command key ("chat"). One grant per physical press: a held key's
                 auto-repeat doesn't grant again. A mouse button never grants (a click is not a key press). -> its id.
  * take(gid)  - a copy key's ONE read: READ_DELAY after the press (the game needs a moment to put the copy there)
                 the window thread reads the text once (App.clip_granted waits for it). No retry: a copy that wasn't
                 there yet - or another program holding the clipboard - says "The copy didn't land - press the key
                 again." Nothing is ever read twice for one press, and nothing without one.
  * take_now(gid) - a chat command key's ONE read, at once: your text, so it can be put back after the paste.
  * app_paste(widget, event) / app_paste_image(event) - Ctrl+V (or Shift+Insert) in one of the app's own boxes: a
                 key press in the app. Without a key event (a click, a menu) nothing is read: "" / None.
  * write_text / clear - putting text on the clipboard (a chat command, your text back) or emptying it just before
                 the app presses the game's copy for you - writing, never reading.
Each read writes one line in the app's log ("Ctrl+C pressed: read the clipboard once for Price Checks") and tells
SAID (the app shows the read mark - readmark.py). Windows' copy counter is never asked (it was polled every 150 ms
before; that timer is gone)."""
import sys
import threading
import time

READ_DELAY = 0.2                   # seconds from the key press to its one read (the game's copy lands in ~50 ms)
GRANT_SECS = 2.0                   # a press too old to read for (a stuck window thread): nothing is read
MOUSE = frozenset((0x01, 0x02, 0x04, 0x05, 0x06))   # mouse buttons: never a read (a click is not a key press)
KEY_EVENTS = ("2", "KeyPress")     # Tk's event type of a key press (str(event.type) is "2" or "KeyPress")

_LOCK = threading.RLock()
_HELD = set()
_STATE = {"grant": None, "next": 0}    # grant: {"id", "key", "kind", "t", "read"}
READER = [None]                    # tests: fn() -> text ('' none, None = another program holds the clipboard)
IMAGE_READER = [None]              # tests: fn() -> an image / list of files / None
LOGGER = [None]                    # tests: fn(line); the app's log otherwise
SAID = [None]                      # the app: fn("clipboard", key, [purposes]) after each read (the read mark)
COUNT = {"grants": 0, "reads": 0}


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


def _said(key, purposes):
    fn = SAID[0]
    if fn is not None:
        try:
            fn("clipboard", key, list(purposes))
        except Exception:
            pass


def grant(key_name, hold=None, kind="copy", now=None):
    """A copy key's real key-down in the game (the key watcher only). -> the grant's id (> 0) for a new press, 0 for a
    key that's still held (Windows repeats a held key's key-down: not a press) or a mouse button."""
    now = time.time() if now is None else now
    hold = key_name if hold is None else hold
    if hold in MOUSE:
        return 0
    with _LOCK:
        if hold in _HELD:
            return 0
        _HELD.add(hold)
        _STATE["next"] += 1
        gid = _STATE["next"]
        _STATE["grant"] = {"id": gid, "key": key_name, "kind": kind, "t": now, "read": False}
        COUNT["grants"] += 1
        return gid


def release(hold):
    """The key went up: its next key-down is a new press."""
    with _LOCK:
        _HELD.discard(hold)


def due(gid, now=None):
    """Seconds until this copy key press's one read (0: now), or None when there's nothing to read for it."""
    now = time.time() if now is None else now
    with _LOCK:
        g = _STATE["grant"]
        if not g or g["id"] != gid or g["read"] or g["kind"] != "copy":
            return None
        return max(0.0, g["t"] + READ_DELAY - now)


def _one(gid, kind, now):
    """Use up the grant (if it's this one, still unread and young enough) -> its key name, or None."""
    with _LOCK:
        g = _STATE["grant"]
        if not g or g["id"] != gid or g["read"] or g["kind"] != kind or now - g["t"] > GRANT_SECS:
            return None
        g["read"] = True
        COUNT["reads"] += 1
        return g["key"]


def take(gid, purpose=None, now=None):
    """A copy key's one read -> the clipboard's text ('' when there's none, or another program held it: the read is
    used up all the same), or None when nothing may be read (no such press, read already, too old). With purpose the
    log line is written now; else say(gid, purpose) writes it once the app knows what the copy was for."""
    now = time.time() if now is None else now
    key = _one(gid, "copy", now)
    if key is None:
        return None
    text = _raw()
    if purpose:
        _note(key, purpose)
    return text or ""


def take_now(gid, purpose="Chat command", now=None):
    """A chat command key's one read, at once (your text, to put back after the command is pasted) -> text, '' or
    None (nothing may be read)."""
    now = time.time() if now is None else now
    key = _one(gid, "chat", now)
    if key is None:
        return None
    text = _raw()
    _note(key, purpose)
    return text or ""


def say(gid, purpose):
    """The log line and the read mark for a copy key's read (after take(gid) without a purpose)."""
    with _LOCK:
        g = _STATE["grant"]
        key = g["key"] if g and g["id"] == gid and g["read"] else None
    if key:
        _note(key, purpose)


def _note(key, purpose):
    _log(f"{key} pressed: read the clipboard once for {purpose}")
    _said(key, [purpose])


def _is_key(event):
    return event is not None and str(getattr(event, "type", "")) in KEY_EVENTS


def app_paste(widget, event):
    """Ctrl+V in the app itself (a key press in one of its boxes or lists) -> the clipboard's text, or ''. A click,
    a menu or no event: '' and nothing is read."""
    if not _is_key(event):
        return ""
    COUNT["reads"] += 1
    _log(f"{_key_of(event)} pressed: read the clipboard once to paste it in the app")
    if READER[0] is None and widget is not None:
        try:
            return widget.clipboard_get()
        except Exception:
            return ""
    return _raw() or ""


def app_paste_image(event):
    """Ctrl+V on the Strat Tracker's Atlas step: the clipboard's picture (or a list of copied files), or None. Without
    a key event nothing is read."""
    if not _is_key(event):
        return None
    COUNT["reads"] += 1
    _log(f"{_key_of(event)} pressed: read the clipboard's picture once")
    fn = IMAGE_READER[0]
    if fn is not None:
        return fn()
    try:
        from PIL import ImageGrab
        return ImageGrab.grabclipboard()
    except Exception:
        return None


def _key_of(event):
    k = str(getattr(event, "keysym", "") or "V")
    return "Shift+Insert" if k == "Insert" else f"Ctrl+{k.upper()}" if len(k) == 1 else k


def _raw():
    fn = READER[0]
    if fn is not None:
        return fn()
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        u.OpenClipboard.argtypes, u.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
        u.GetClipboardData.argtypes, u.GetClipboardData.restype = [wintypes.UINT], wintypes.HANDLE
        k.GlobalLock.argtypes, k.GlobalLock.restype = [wintypes.HANDLE], ctypes.c_void_p
        k.GlobalUnlock.argtypes = [wintypes.HANDLE]
        if not u.OpenClipboard(None):
            return None
        try:
            h = u.GetClipboardData(13)                 # CF_UNICODETEXT
            if not h:
                return ""
            p = k.GlobalLock(h)
            if not p:
                return ""
            try:
                return ctypes.wstring_at(p)
            finally:
                k.GlobalUnlock(h)
        finally:
            u.CloseClipboard()
    except Exception:
        return None


# ---------------------------------------------------------------- writing (never a read)
WRITER = [None]                    # tests: fn(text or None) -> True ("None": emptied)


def _open_for_write(u):
    for _ in range(10):                                # another program may hold the clipboard for a moment
        if u.OpenClipboard(None):
            return True
        time.sleep(0.01)
    return False


def write_text(text):
    """Put text on the Windows clipboard (a chat command, or your text back after it). -> True if done."""
    fn = WRITER[0]
    if fn is not None:
        return fn(text or "")
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        u.OpenClipboard.argtypes, u.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
        u.SetClipboardData.argtypes, u.SetClipboardData.restype = [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE
        k.GlobalAlloc.argtypes, k.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL
        k.GlobalLock.argtypes, k.GlobalLock.restype = [wintypes.HGLOBAL], ctypes.c_void_p
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        data = (text or "").encode("utf-16-le") + b"\0\0"
        if not _open_for_write(u):
            return False
        try:
            u.EmptyClipboard()
            h = k.GlobalAlloc(0x0002, len(data))       # GMEM_MOVEABLE
            p = k.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            k.GlobalUnlock(h)
            return bool(u.SetClipboardData(13, h))     # CF_UNICODETEXT (Windows owns the memory now)
        finally:
            u.CloseClipboard()
    except Exception:
        return False


def clear():
    """Empty the clipboard - just before the app presses the game's copy for you (the price check key, the Top Up key),
    so the one read after it finds the new copy or nothing, never the one before. -> True if done."""
    fn = WRITER[0]
    if fn is not None:
        return fn(None)
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.OpenClipboard.argtypes, u.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
        if not _open_for_write(u):
            return False
        try:
            return bool(u.EmptyClipboard())
        finally:
            u.CloseClipboard()
    except Exception:
        return False


def reset():
    """(tests) No grant, no key held."""
    with _LOCK:
        _HELD.clear()
        _STATE["grant"] = None
        COUNT["grants"] = COUNT["reads"] = 0
