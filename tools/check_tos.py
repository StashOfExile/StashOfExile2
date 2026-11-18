"""GGG Terms of Service and third-party policy check for the code (see TOS.md). Runs on every pull request and in the
test suite.

  py tools/check_tos.py      exit 1 (and says where) if anything breaks a rule

What it looks for, in soe2/ and stashofexile2.py:
  - touching the game client: process memory / injection APIs
  - moving or clicking the mouse for the player
  - packet capture / traffic tools
  - input-automation libraries
  - key input (SendInput) anywhere but soe2/overlay.py, the one place that sends the game's own copy key or one chat
    command - and only keyboard input there (INPUT type 1), never mouse (type 0)
  - a screen watcher (a file that captures the screen) that can send keys
GGG policy (Nov 2026): "Reading from the screen or clipboard may only be performed once per manual key press." - the
base rule for the whole program:
  - screen capture (mss, ImageGrab, BitBlt, PrintWindow, grim, d3dshot, dxcam, win32ui) anywhere but soe2/screenread.py
  - any clipboard API (OpenClipboard, GetClipboardData, SetClipboardData, EmptyClipboard, clipboard_get, grabclipboard,
    win32clipboard, pyperclip ...) anywhere but soe2/clipread.py; and nowhere at all an API that watches the clipboard
    (GetClipboardSequenceNumber, AddClipboardFormatListener, SetClipboardViewer, WM_CLIPBOARDUPDATE): the strictest
    reading - any clipboard call on a timer is a read
  - in soe2/screenread.py and soe2/clipread.py: a timer (.after, after_idle, threading.Timer), a thread, a while loop,
    or a loop that reads (they may only answer a press)
  - screenread.grant / clipread.grant called from anything but the key watcher (KEY_WATCHER below)
  - a function that reads the clipboard (clipread take / take_now / app_paste) and puts itself back on a timer
  - a key sender (SendInput, send_copy, type_chat ...) reachable from a timer (.after, after_idle, threading.Timer)
GGG's developer guidelines (https://www.pathofexile.com/developer/docs/index#guidelines):
  - the exact notice NOTICE in README.md and on Settings › About (soe2/about_page.py)
  - the User-Agent (config.APP_UA) says how to reach the project: "(contact: ...)"."""
import ast
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBIDDEN = {
    "game memory / injection": r"\b(ReadProcessMemory|WriteProcessMemory|OpenProcess|VirtualAllocEx|VirtualProtectEx|"
                               r"CreateRemoteThread|NtReadVirtualMemory|pymem|ReadWriteMemory|frida|SetWindowsHookEx)\b",
    "mouse automation": r"\b(SetCursorPos|mouse_event|SendMouseInput|pyautogui|mouse\.Controller|pydirectinput)\b",
    "packet tools": r"\b(pydivert|scapy|pcap|WinDivert|npcap)\b",
    "input automation libraries": r"^\s*(import|from)\s+(pynput|keyboard|ahk|autohotkey|pyautogui|pydirectinput)\b",
    "old key API": r"\bkeybd_event\b",
}
SENDERS = {os.path.join("soe2", "overlay.py")}               # the only file allowed to send keys
SCREEN_FILE = os.path.join("soe2", "screenread.py")         # the only file allowed to capture the screen
CLIP_FILE = os.path.join("soe2", "clipread.py")             # the only file allowed to read the clipboard
# a screen capture library or call (ImageGrab.grabclipboard is a clipboard read - the clipboard rule below)
CAPTURE = (r"\b(mss|BitBlt|PrintWindow|grim|d3dshot|dxcam|win32ui|CreateCompatibleBitmap|"
           r"ImageGrab\.grab(?!clipboard)\w*)\b|^\s*from\s+PIL\s+import\s+.*\bImageGrab\b|\bimport\s+ImageGrab\b")
CAPTURE_CALL = r"\bImageGrab\.grab(?!clipboard)\w*"
CLIPBOARD = (r"\b(read_clipboard_text|clipboard_get|GetClipboardData|SetClipboardData|OpenClipboard|EmptyClipboard|"
             r"CloseClipboard|IsClipboardFormatAvailable|EnumClipboardFormats|CountClipboardFormats|"
             r"GetClipboardOwner|win32clipboard|pyperclip|grabclipboard|GetClipboardSequenceNumber)\b")
# watching the clipboard - never, anywhere (not even clipread.py): a copy key press reads once, that's all
CLIP_WATCH = (r"\b(GetClipboardSequenceNumber|AddClipboardFormatListener|SetClipboardViewer|ChangeClipboardChain|"
              r"WM_CLIPBOARDUPDATE|WM_DRAWCLIPBOARD|0x031D)\b")
# the key watcher: the only code that may grant a read (App.on_any_key calls each; KeyWatch calls on_any_key)
KEY_WATCHER = {(os.path.join("soe2", "look_page.py"), "look_on_key"),
               (os.path.join("soe2", "utilities_page.py"), "clip_on_key"),
               (os.path.join("soe2", "utilities_page.py"), "pc_hotkey"),
               (os.path.join("soe2", "utilities_page.py"), "topup_hotkey"),
               (os.path.join("soe2", "overlay.py"), "on_key")}
SCREEN_GRANT = {"screenread", "SR", "_sr"}
LOOK_WATCHER = (os.path.join("soe2", "look_page.py"), "look_on_key")     # the only caller of screenread.grant
GRANT_MODULES = {"screenread", "SR", "clipread", "CR", "_sr"}
CLIP_READS = {"take", "take_now", "app_paste", "app_paste_image", "from_clipboard"}
SEND = r"\b(SendInput|_send_keys|type_chat|send_copy)\b"
SEND_NAMES = {"SendInput", "_send_keys", "type_chat", "send_copy"}
TIMERS = {"after", "after_idle", "Timer"}
NOTICE = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."
NOTICE_FILES = ("README.md", os.path.join("soe2", "about_page.py"))


def files():
    out = sorted(glob.glob(os.path.join(ROOT, "soe2", "**", "*.py"), recursive=True))
    return out + [os.path.join(ROOT, "stashofexile2.py")]


def code_lines(text):
    """Lines without comments and docstrings (they may *mention* these words)."""
    text = re.sub(r'"""[\s\S]*?"""', lambda m: "\n" * m.group(0).count("\n"), text)
    return [re.sub(r"#.*$", "", ln) for ln in text.split("\n")]


def _called(node):
    """The names a node calls (f(), x.f())."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            out.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None))
    return out - {None}


def _refs(node):
    """Names a callback argument refers to (self.f, f, lambda: ... f() ...)."""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


READ_CALLS = {"_grab", "grab", "capture", "shot", "BitBlt", "_raw", "GetClipboardData", "clipboard_get",
              "grabclipboard", "take", "take_now", "app_paste", "app_paste_image"}


def screenread_rules(tree, rel):
    """screenread.py and clipread.py answer a press and nothing else: no timer, no thread, no while loop, no loop that
    reads."""
    what = "the clipboard reader" if rel.endswith("clipread.py") else "the screen reader"
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in TIMERS or name == "Thread":
                bad.append(f"{rel}:{n.lineno}: a timer or thread in {what} ({name})")
        if isinstance(n, (ast.For, ast.While, ast.AsyncFor)):
            if _called(n) & READ_CALLS:
                bad.append(f"{rel}:{n.lineno}: a loop that reads in {what}")
        if isinstance(n, ast.While):
            bad.append(f"{rel}:{n.lineno}: a while loop in {what}")
    return bad


def grant_callers(trees):
    """screenread.grant / clipread.grant called anywhere but the key watcher: [(file, line, what)]."""
    bad = []
    fn = (ast.FunctionDef, ast.AsyncFunctionDef)
    for rel, tree in trees:
        if rel in (SCREEN_FILE, CLIP_FILE):
            continue
        for d in [n for n in ast.walk(tree) if isinstance(n, fn)]:
            for n in ast.walk(d):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "grant" and \
                        getattr(n.func.value, "id", "") in GRANT_MODULES and (rel, d.name) not in KEY_WATCHER:
                    bad.append((rel, n.lineno, f"a read is granted outside the key watcher ({d.name}) - only a key "
                                               f"press may grant a screen / clipboard read"))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "grant" and \
                        getattr(n.func.value, "id", "") in SCREEN_GRANT and (rel, d.name) != LOOK_WATCHER:
                    bad.append((rel, n.lineno, f"a screen read is granted by {d.name} - the Read Key (look_on_key) is "
                                               f"the one key that opens a screen read: no second key, no per-helper "
                                               f"keys, no clicks"))
        for n in ast.walk(tree):                 # (from .screenread import grant: a bare grant() call)
            if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[-1] in ("screenread", "clipread") and \
                    any(a.name == "grant" for a in n.names):
                bad.append((rel, n.lineno, "grant imported by name - call it as screenread.grant / clipread.grant from "
                                           "the key watcher"))
    return bad


def timer_readers(trees):
    """A function that reads the clipboard and puts itself back on a timer (a watcher): [(file, line, what)]."""
    bad = []
    fn = (ast.FunctionDef, ast.AsyncFunctionDef)
    for rel, tree in trees:
        for d in [n for n in ast.walk(tree) if isinstance(n, fn)]:
            if not (_called(d) & CLIP_READS):
                continue
            for n in ast.walk(d):
                if isinstance(n, ast.Call):
                    f = n.func
                    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    refs = set()
                    for a in list(n.args) + [k.value for k in n.keywords]:
                        refs |= _refs(a)
                    if name in TIMERS and d.name in refs:
                        bad.append((rel, n.lineno, f"{d.name} reads the clipboard and runs again on a timer ({name})"))
    return bad


def timer_senders(trees):
    """Every key sender reachable from a timer: [(file, line, what)]."""
    senders = set()                              # module / class level function names that (in the end) send keys
    defs, tops = [], []
    fn = (ast.FunctionDef, ast.AsyncFunctionDef)
    for rel, tree in trees:
        for n in ast.walk(tree):
            if isinstance(n, fn):
                defs.append((rel, n))
        for n in tree.body:                      # (a nested def's calls count for the function around it)
            if isinstance(n, fn):
                tops.append(n)
            elif isinstance(n, ast.ClassDef):
                tops += [m for m in n.body if isinstance(m, fn)]
    changed = True
    while changed:
        changed = False
        for d in tops:
            if d.name in senders:
                continue
            calls = _called(d) | {r for r in _refs(d) if r in SEND_NAMES}
            if calls & (SEND_NAMES | senders):
                senders.add(d.name)
                changed = True
    bad = []
    for rel, d in defs:
        nested = {}
        for n in ast.walk(d):
            if n is not d and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if isinstance(n, ast.Lambda):
                    continue
                if (_called(n) | _refs(n)) & (SEND_NAMES | senders):
                    nested[n.name] = n
        for n in ast.walk(d):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name not in TIMERS:
                continue
            refs = set()
            for a in list(n.args) + [k.value for k in n.keywords]:
                refs |= _refs(a)
            hit = refs & (SEND_NAMES | senders | set(nested))
            if hit:
                bad.append((rel, n.lineno, f"a key sender ({', '.join(sorted(hit))}) runs from a timer ({name})"))
    return bad


LISTENER_FILE = os.path.join("soe2", "utilities_page.py")
LISTENER_OK = re.compile(r"CAPTURING|0x4B|pc_hotkey|pc_close_hotkey|rx_key_hit|topup_hotkey|poe2db_key|tracker_on_key|"
                         r"overlay\.on_key|drawer_hotkey|drawer_esc_hotkey")
# (what the key watcher swallowed before the compliance work; drawer build: the Drawer key and, while the Drawer
# shows, your close key - both the app's own keys, never the Read Key: Settings › Keybinds keeps them apart)
READ_KEYS = re.compile(r"look_on_key|clip_on_key|look_key|screenread|clipread|\bSR\.|grant")


def key_blocking(trees, src_of):
    """The Read Key is only heard - the game still gets it (owner: it must NOT be swallowed). In the key watcher's
    listener (UtilitiesPage.on_any_key): look_on_key / clip_on_key are called as plain statements (their answer is
    never returned or tested), and every statement that can swallow a key (return True or return of a call) belongs
    to a key the app already took before: the hotkey box, Ctrl+K, the price check / its close key, Regex keys, the Top
    Up key, the poe2db key, the tracker's keys, the overlay's keys, the Drawer key. [(file, line, what)]"""
    bad = []
    for rel, tree in trees:
        if rel != LISTENER_FILE:
            continue
        fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "on_any_key"]
        if not fn:
            bad.append((rel, 1, "the key watcher's listener on_any_key is gone (this check reads it)"))
            continue
        f = fn[0]
        bare = {id(n.value) for n in ast.walk(f) if isinstance(n, ast.Expr)}
        for n in ast.walk(f):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", "") in ("look_on_key", "clip_on_key") \
                    and id(n) not in bare:
                bad.append((rel, n.lineno, f"{n.func.attr}'s answer is used - the Read Key and copy keys must pass "
                                           f"through to the game (call it as a plain statement)"))
        for st in f.body:
            seg = ast.get_source_segment(src_of[rel], st) or ""
            swallows = any(isinstance(n, ast.Return) and not (isinstance(n.value, ast.Constant) and
                                                              n.value.value is False) for n in ast.walk(st))
            if swallows and (READ_KEYS.search(seg) or not LISTENER_OK.search(seg)):
                bad.append((rel, st.lineno, "a key is swallowed here that isn't one of the app's own hotkeys "
                                            "(the Read Key and copy keys are never blocked)"))
    return bad


def guidelines():
    """GGG's developer guidelines: the notice, and the User-Agent's contact."""
    bad = []
    for rel in NOTICE_FILES:
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except OSError:
            bad.append(f"{rel}: missing")
            continue
        if NOTICE not in text:
            bad.append(f"{rel}: the notice must read exactly: {NOTICE}")
    cfg = open(os.path.join(ROOT, "soe2", "config.py"), encoding="utf-8").read()
    m = re.search(r"^APP_UA\s*=\s*(.+)$", cfg, re.M)
    if not m or "(contact: " not in m.group(1):
        bad.append("soe2/config.py: APP_UA must say how to reach the project: \"(contact: ...)\"")
    return bad


def check():
    bad, trees, srcs = [], [], {}
    for path in files():
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        lines = code_lines(src)
        joined = "\n".join(lines)
        try:
            tree = ast.parse(src)
            trees.append((rel, tree))
            srcs[rel] = src
        except SyntaxError as e:
            bad.append(f"{rel}: doesn't parse ({e})")
            tree = None
        for what, pat in FORBIDDEN.items():
            for no, ln in enumerate(lines, 1):
                if re.search(pat, ln):
                    bad.append(f"{rel}:{no}: {what}: {ln.strip()[:90]}")
        for no, ln in enumerate(lines, 1):
            if "SendInput" in ln and rel not in SENDERS:
                bad.append(f"{rel}:{no}: SendInput outside soe2/overlay.py")
            if rel in SENDERS and re.search(r"\bINPUT\(\s*0\s*,", ln):
                bad.append(f"{rel}:{no}: mouse input (INPUT type 0)")
            if rel == CLIP_FILE and re.search(r"\bimport\s+ImageGrab\b", ln) and not re.search(CAPTURE_CALL, ln):
                pass                                     # (clipread: ImageGrab.grabclipboard - Ctrl+V's one read)
            elif rel != SCREEN_FILE and re.search(CAPTURE, ln):
                bad.append(f"{rel}:{no}: screen capture outside soe2/screenread.py (one read per key press): "
                           f"{ln.strip()[:80]}")
            if rel != CLIP_FILE and re.search(CLIPBOARD, ln):
                bad.append(f"{rel}:{no}: clipboard API outside soe2/clipread.py (one read per key press): "
                           f"{ln.strip()[:80]}")
            if re.search(CLIP_WATCH, ln):
                bad.append(f"{rel}:{no}: watching the clipboard (never - a copy key press reads once): "
                           f"{ln.strip()[:80]}")
        if re.search(CAPTURE, joined) and re.search(SEND, joined) and rel not in SENDERS:
            bad.append(f"{rel}: a screen watcher must never send keys (it captures the screen and can send input)")
        if rel in (SCREEN_FILE, CLIP_FILE) and tree is not None:
            bad += screenread_rules(tree, rel)
    bad += [f"{rel}:{ln}: {what}" for rel, ln, what in timer_senders(trees)]
    bad += [f"{rel}:{ln}: {what}" for rel, ln, what in grant_callers(trees)]
    bad += [f"{rel}:{ln}: {what}" for rel, ln, what in timer_readers(trees)]
    bad += [f"{rel}:{ln}: {what}" for rel, ln, what in key_blocking(trees, srcs)]
    bad += guidelines()
    return bad


def main():
    bad = check()
    for b in bad:
        print(b)
    print("OK - GGG ToS check passed (see TOS.md)" if not bad else f"{len(bad)} ToS problem(s) - see TOS.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
