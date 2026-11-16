"""Runtime test of the base rule (GGG policy, Nov 2026: "Reading from the screen or clipboard may only be performed once
per manual key press" - the owner's strictest reading) - see TOS.md. No game, no Windows needed: the picture taker
and the clipboard are stand-ins.

  py tools/check_screenread.py      exit 1 (and says what) if a check fails

It proves:
  * no reads without a key press - screen or clipboard, for any key that isn't a read key;
  * no reads on clicks - a mouse button never grants, Scan stash's Start reading only arms, the app's Ctrl+V paths
    read nothing without a key event, the right-click menu has no Paste;
  * one read per press - one picture shared by every helper, one clipboard read per copy key press (READ_DELAY after
    it, no retry), a held key's auto-repeat reads nothing more, a chat key reads once;
  * no clipboard timer exists - the app has no clipboard watcher, nothing asks Windows' copy counter, nothing that reads
    the clipboard runs again on a timer;
  * Read Key unset -> no reads at all; Tab / a mouse button / another app key can't be the Read Key;
  * every read writes its log line and shows the read mark;
  * tools/check_tos.py catches each of these if it came back."""
import ast
import os
import queue
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from soe2 import clipread as CR      # noqa: E402
from soe2 import screenread as SR    # noqa: E402

FAILS = []
PASSED = [0]
VKS = [v for v in range(0x07, 0xFF) if v not in (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5)]


def ok(cond, what):
    if cond:
        PASSED[0] += 1
    else:
        FAILS.append(what)


class Pic:
    """A stand-in picture: crop / copy say what they cut."""
    def __init__(self, box):
        self.box = box

    def crop(self, b):
        return ("crop", self.box, b)

    def copy(self):
        return ("copy", self.box)


class Ev:
    """A stand-in Tk event."""
    def __init__(self, kind, keysym="v"):
        self.type, self.keysym = kind, keysym


def setup():
    SR.reset()
    shots, lines, said = [], [], []
    SR.GRABBER[0] = lambda box: (shots.append(box), Pic(box))[1]
    SR.AREA[0] = lambda: (100, 50, 1920, 1080)
    SR.LOGGER[0] = lines.append
    SR.SAID[0] = lambda *a: said.append(a)
    return shots, lines, said


def setup_clip(text="Item Class: Rings"):
    CR.reset()
    reads, lines, said = [], [], []
    CR.READER[0] = lambda: (reads.append(1), text)[1]
    CR.IMAGE_READER[0] = lambda: (reads.append("img"), "picture")[1]
    CR.LOGGER[0] = lines.append
    CR.SAID[0] = lambda *a: said.append(a)
    return reads, lines, said


def test_gate():
    shots, lines, said = setup()
    T = 1000.0
    ok(SR.capture((0, 0, 10, 10), "Ritual", now=T) is None, "no press: capture must give nothing")
    ok(not shots, "no press: no picture may be taken")
    ok(SR.grant("F9", hold=0x78, now=T), "a first press opens a read")
    a = SR.capture((200, 100, 300, 200), "Ritual", now=T + 0.1)
    b = SR.capture((150, 60, 400, 300), "Temple", now=T + 0.2)
    ok(a is not None and b is not None, "one press: every helper gets its part")
    ok(len(shots) == 1, f"one press: exactly one picture (took {len(shots)})")
    ok(shots == [(100, 50, 2020, 1130)], "the picture is the game window")
    ok(SR.capture((5000, 5000, 5100, 5100), "X", now=T + 0.3) is None, "a part outside the game: nothing")
    for _ in range(20):                                     # Windows' auto-repeat while the key is held
        ok(not SR.grant("F9", hold=0x78, now=T + 0.4), "a held key's repeat must not grant again")
    SR.finish()
    ok(lines == ["F9 pressed: read the screen once for Ritual, Temple, X"], f"the log line: {lines}")
    ok(said == [("screen", "F9", ["Ritual", "Temple", "X"])], f"the read mark is told: {said}")
    ok(SR.capture((200, 100, 300, 200), "Ritual", now=T + 0.5) is None, "after finish: no more reads this press")
    ok(len(shots) == 1, "held key / repeats: still one picture")
    ok(not SR.grant("F9", hold=0x78, now=T + 2), "still held (no release): no new press")
    SR.release(0x78)
    ok(SR.grant("F9", hold=0x78, now=T + 3), "released, pressed again: a new read")
    ok(SR.capture((0, 0, 10, 10), "Ritual", now=T + 3 + SR.GRANT_SECS + 0.1) is None, "a press runs out")
    ok(len(shots) == 1, "an old press takes no picture")
    SR.release(0x78)
    ok(SR.grant("F9", hold=0x78, now=T + 10), "another press")
    SR.capture((200, 100, 300, 200), "Ritual", now=T + 10.1)
    ok(len(shots) == 2, "two presses: two pictures")
    ok(SR.capture((200, 100, 300, 200), "Expedition", now=T + 14) is not None and len(shots) == 2,
       "a slow helper still cuts from the press's picture - no new one")
    SR.finish()
    ok(not hasattr(SR, "click"), "no click() in the screen reader: a click is not a key press")
    for vk in (0x01, 0x02, 0x04, 0x05, 0x06):               # mouse buttons
        ok(not SR.grant("Mouse", hold=vk, now=T + 20), f"a mouse button (vk {vk}) never grants a screen read")
    ok(SR.capture((200, 100, 300, 200), "Ritual", now=T + 20.1) is None and len(shots) == 2,
       "a click takes no picture")
    SR.ONLY_KEY[0] = lambda: 0x78                            # the app's gate: only the Read Key (F9 here) opens a read
    SR.release(0x41)
    ok(not SR.grant("A", hold=0x41, now=T + 30) and SR.COUNT["refused"] >= 1, "a key that isn't the Read Key can't open a read")
    SR.ONLY_KEY[0] = lambda: None
    SR.release(0x78)
    ok(not SR.grant("F9", hold=0x78, now=T + 31), "no Read Key: no key opens a read")
    SR.ONLY_KEY[0] = None
    SR.release(0x78)
    ok("ONLY_KEY[0] = self.look_key_vk" in open(os.path.join(ROOT, "soe2", "utilities_page.py"), encoding="utf-8").read(),
       "the app wires the gate: only the Read Key's code opens a read")
    ok(SR.DEFAULT_KEY == "Ctrl+Shift+R", "the Read Key is Ctrl+Shift+R as the app comes")


class FakeApp:
    """Just enough of the app for the Read Key and Scan stash: the key watcher's listener, the window thread's queue,
    the jobs."""
    def __init__(self, jobs=None):
        from soe2.look_page import LookPage
        from soe2.stashscan_page import StashScanPage
        self.__class__ = type("App", (FakeApp, LookPage, StashScanPage), {})
        self.ui_q = queue.Queue()
        self._jobs = jobs
        self.br_area = "map"
        self.mm_sync = True
        self.ss = None
        self.root = type("R", (), {"winfo_pointerxy": staticmethod(lambda: (500, 500))})()

    def look_jobs(self, ctx):
        if self._jobs is None:
            from soe2.look_page import LookPage
            return LookPage.look_jobs(self, ctx)
        return [j(ctx) for j in self._jobs]

    def stash_scan_card(self):
        pass

    def all_hotkeys(self):
        return [("Price check", "Ctrl+D", "Price Checks", "checks:pc_key"), ("Go to hideout", "F1", "Chat", "x"),
                ("Read Key", "", "Overlay", "checks:look_key")]

    def run_bg(self, work, done):
        return done(work())

    def log_error(self, where):
        FAILS.append(f"error in {where}")


def _with_game(fn):
    from soe2 import alerts_page, overlay
    from soe2.config import SETTINGS
    old = (overlay.game_active, alerts_page.game_rect, SETTINGS.get("look_key"))
    overlay.game_active = lambda *_a: True
    alerts_page.game_rect = lambda *_a: (0, 0, 1920, 1080)
    SR.AREA[0] = lambda: (0, 0, 1920, 1080)
    try:
        fn(SETTINGS, overlay)
    finally:
        overlay.game_active, alerts_page.game_rect = old[0], old[1]
        if old[2] is None:
            SETTINGS.pop("look_key", None)
        else:
            SETTINGS["look_key"] = old[2]


def test_look_key():
    shots, lines, said = setup()

    def run(SETTINGS, overlay):
        got = []

        def helper(name, box):
            return lambda ctx: (name, lambda: SR.capture(box, name), lambda res: got.append((name, res)))
        app = FakeApp([helper("Ritual", (10, 10, 50, 50)), helper("Temple", (100, 100, 200, 200))])
        # ---- no Read Key: nothing reads, whatever is pressed
        SETTINGS["look_key"] = ""
        ok(not app.look_key_set() and app.look_key_text() == "your Read Key", "unset: the text says 'your Read Key'")
        for vk in VKS:
            for mods in ((False, False, False), (True, False, False), (False, False, True)):
                if app.look_on_key(vk, *mods):
                    FAILS.append(f"Read Key unset: key {vk} was taken")
                SR.release(vk)
        ok(app.ui_q.empty() and SR.COUNT["grants"] == 0, "Read Key unset: no key press grants a read")
        app.ev_look()
        ok(not shots and all(r is None for _n, r in got), "Read Key unset: no picture at all")
        got.clear()
        # ---- set: F9 reads once per press
        SETTINGS["look_key"] = "F9"
        ok(app.look_key_text() == "your Read Key (F9)", f"set: the text names it ({app.look_key_text()})")
        for _ in range(8):                                  # F9 held: one key-down, then repeats
            ok(app.look_on_key(0x78, False, False, False), "the Read Key in the game opens a read")
        ok(app.ui_q.qsize() == 1, f"F9 held: one press for the helpers (got {app.ui_q.qsize()})")
        ok(not app.look_on_key(0x09, False, False, False), "Tab is not the Read Key any more")
        ok(not app.look_on_key(0x41, False, False, False), "another key reads nothing")
        ok(app.ui_q.qsize() == 1, "other keys add no read")
        while not app.ui_q.empty():
            app.ev_look(*app.ui_q.get()[1:])
        ok(len(shots) == 1, f"one press, two helpers: one picture (took {len(shots)})")
        ok([n for n, _r in got] == ["Ritual", "Temple"] and all(r is not None for _n, r in got),
           "both helpers read from the one picture")
        ok(lines == ["F9 pressed: read the screen once for Ritual, Temple"], f"the log line: {lines}")
        ok(said and said[-1] == ("screen", "F9", ["Ritual", "Temple"]), "the read mark is told what was read")
        app.ev_look()                                       # a second dispatch for the same press: no picture
        ok(len(shots) == 1, "the same press can't read twice")
        SR.release(0x78)
        app.look_on_key(0x78, False, False, False)
        ok(app.ui_q.qsize() == 1, "let go and pressed again: a new press")
        overlay.game_active = lambda *_a: False
        SR.release(0x78)
        app.ui_q = queue.Queue()
        ok(not app.look_on_key(0x78, False, False, False) and app.ui_q.empty(),
           "the Read Key outside the game reads nothing (and is yours)")
        overlay.game_active = lambda *_a: True
        SETTINGS["look_key"] = "Mouse4"
        ok(not app.look_on_key(0x05, False, False, False), "a mouse-button Read Key (an old setting) never reads")
        from soe2.look_page import look_key_problem
        # ---- the default: Ctrl+Shift+R (never set = the default; cleared = no key)
        SETTINGS.pop("look_key", None)
        ok(app.look_key() == "Ctrl+Shift+R" and app.look_key_set(), "never set: the Read Key is Ctrl+Shift+R")
        SR.release(0x52)
        app.ui_q = queue.Queue()
        ok(not app.look_on_key(0x52, False, False, False) and not app.look_on_key(0x52, True, False, False)
           and app.ui_q.empty(), "R alone and Ctrl+R are not the Read Key")
        ok(app.look_on_key(0x52, True, False, True) and app.ui_q.qsize() == 1, "Ctrl+Shift+R reads once")
        SETTINGS["look_key"] = ""
        ok(not app.look_key_set() and app.look_key_text() == "your Read Key", "cleared: no Read Key (stays cleared)")
        SETTINGS["look_key"] = "F9"
        # ---- passed through: the key watcher's listener never swallows the Read Key (the game still gets it)
        from soe2.utilities_page import UtilitiesPage
        from soe2 import features as FEAT_
        no = lambda *_a, **_k: False                       # noqa: E731
        listener = type("L", (), {"__getattr__": lambda s, n: no})()
        listener.ui_q = queue.Queue()
        listener.look_on_key = app.look_on_key
        listener.overlay = type("O", (), {"on_key": staticmethod(no)})()
        listener._app_in_front = no
        for key in ((0x78, False, False, False), (0x52, True, False, True)):
            for look in ("F9", "Ctrl+Shift+R"):
                SETTINGS["look_key"] = look
                SR.release(key[0])
                ok(not UtilitiesPage.on_any_key(listener, *key), f"the key watcher never swallows the Read Key "
                                                                  f"({look}) - the game still gets it")
        SETTINGS["look_key"] = "F9"
        # ---- the default clashes with no other key of the app
        from soe2.overlay import parse_key
        from soe2.tracker_page import DEFAULT_HOTKEYS
        for kid, key in DEFAULT_HOTKEYS.items():
            if kid != "checks:look_key" and key:
                ok(parse_key(key) != parse_key(SR.DEFAULT_KEY), f"the default Read Key isn't {key} ({kid})")
        ok(DEFAULT_HOTKEYS["checks:look_key"] == SR.DEFAULT_KEY, "Keybinds' defaults put the Read Key back to the default")
        for taken, what in (((0x4B, True, False, False), "Ctrl+K (Go to anything)"),
                            ((0x20, True, False, True), "Ctrl+Shift+Space (the drawer)"),
                            ((0x43, True, False, False), "Ctrl+C"), ((0x43, True, True, False), "Ctrl+Alt+C")):
            ok(parse_key(SR.DEFAULT_KEY) != taken, f"the default Read Key isn't {what}")
        ok(look_key_problem(SR.DEFAULT_KEY, [(w, k) for w, k, _x, _i in app.all_hotkeys()]) is None,
           "the default Read Key passes the same test as one you pick")
        # ---- what may be the Read Key
        others = app.look_key_others()
        for bad_key in ("Tab", "Enter", "Space", "Esc", "Mouse4", "Middle", "Ctrl+C", "Ctrl+D", "F1"):
            ok(look_key_problem(bad_key, others), f"{bad_key} can't be the Read Key")
        for good in ("F9", "Ctrl+F9", "Numpad5", ""):
            ok(look_key_problem(good, others) is None, f"{good or 'no key'} can be the Read Key")
    _with_game(run)


def test_scan_stash_click():
    shots, lines, said = setup()

    def run(SETTINGS, overlay):
        SETTINGS["look_key"] = "F9"
        app = FakeApp()
        app.ss = {"i": 0, "got": {}, "unread": {}, "busy": False, "note": "", "kind": ""}
        n0 = SR.COUNT["grants"]
        ok(app.stash_scan_read(), "Start reading arms the scan")
        ok(not shots and SR.COUNT["grants"] == n0, "a click on Start reading reads nothing (it only arms)")
        ok(app.ss.get("armed"), "the scan is armed")
        jobs = app.look_jobs({"rect": (0, 0, 1920, 1080)})
        ok(len(jobs) == 1 and jobs[0][0] == "Scan stash", "armed: the Read Key press goes to Scan stash alone")
        app.ss = {"i": 0, "got": {}, "unread": {}, "busy": False, "note": "", "kind": ""}
        ok(app.stash_scan_job({"rect": (0, 0, 10, 10)}) is None, "not armed: the card alone reads nothing")
        SETTINGS["look_key"] = ""
        ok(not app.stash_scan_read() and not app.ss.get("armed"), "no Read Key: Start reading can't arm")
    _with_game(run)


def test_clipboard():
    reads, lines, said = setup_clip()
    T = 2000.0
    ok(CR.take(1, now=T) is None and not reads, "no copy key: the clipboard isn't read")
    gid = CR.grant("Ctrl+C", hold=0x43, now=T)
    ok(gid, "Ctrl+C in the game: one read granted")
    ok(abs(CR.due(gid, now=T) - CR.READ_DELAY) < 1e-9, "the read is due READ_DELAY after the press")
    ok(0.1 <= CR.READ_DELAY <= 0.3, f"READ_DELAY is a short fixed delay ({CR.READ_DELAY})")
    ok(not reads, "granting reads nothing")
    ok(CR.take(gid, now=T + 0.2) == "Item Class: Rings", "the copy is read")
    CR.say(gid, "Price Checks")
    ok(lines == ["Ctrl+C pressed: read the clipboard once for Price Checks"], f"the log line: {lines}")
    ok(said == [("clipboard", "Ctrl+C", ["Price Checks"])], f"the read mark is told: {said}")
    ok(CR.take(gid, now=T + 0.3) is None and CR.due(gid, now=T + 0.3) is None, "only once per press")
    ok(not CR.grant("Ctrl+C", hold=0x43, now=T + 0.4), "a held Ctrl+C isn't a new press")
    ok(CR.take(gid, now=T + 0.5) is None and len(reads) == 1, "held key: no extra read")
    CR.release(0x43)
    g2 = CR.grant("Ctrl+C", hold=0x43, now=T + 1)
    ok(g2 and g2 != gid, "released, pressed again: a new press")
    ok(CR.take(gid, now=T + 1.2) is None, "an old press's id reads nothing")
    ok(CR.take(g2, now=T + 1 + CR.GRANT_SECS + 0.5) is None, "a press runs out")
    CR.READER[0] = lambda: (reads.append(1), None)[1]      # another program holds the clipboard
    CR.release(0x43)
    g3 = CR.grant("Ctrl+C", hold=0x43, now=T + 10)
    n = len(reads)
    ok(CR.take(g3, now=T + 10.2) == "", "clipboard busy: '' (the copy didn't land)")
    ok(CR.take(g3, now=T + 10.4) is None and len(reads) == n + 1, "no retry: the press is used up")
    for vk in (0x01, 0x02, 0x04, 0x05, 0x06):
        ok(not CR.grant("Mouse", hold=vk, now=T + 20), f"a mouse button (vk {vk}) never grants a clipboard read")
    # chat command key: one read at once, to put your clipboard back
    reads, lines, said = setup_clip("my text")
    gc = CR.grant("F1", hold=0x70, kind="chat", now=T)
    ok(CR.due(gc, now=T) is None and CR.take(gc, now=T + 0.3) is None, "a chat key's grant isn't a copy read")
    ok(CR.take_now(gc, now=T) == "my text" and len(reads) == 1, "the chat key reads once")
    ok(CR.take_now(gc, now=T) is None and len(reads) == 1, "and only once")
    from soe2 import overlay
    sent, wrote = [], []
    CR.release(0x70)
    gc = CR.grant("F1", hold=0x70, kind="chat", now=None)
    overlay.type_chat("/hideout", sender=sent.append, sleep=lambda s: None,
                      clip=(lambda: CR.take_now(gc) or "", lambda t: (wrote.append(t), True)[1]))
    ok(len(reads) == 2 and wrote == ["/hideout", "my text"], f"type_chat: one read, your text put back ({wrote})")
    n = len(reads)
    overlay.type_chat("/hideout", sender=sent.append, sleep=lambda s: None, gid=0,
                      clip=(lambda: CR.take_now(0) or "", lambda t: True))
    ok(len(reads) == n, "type_chat with no grant (a mouse button) reads nothing")
    CR.READER[0] = CR.IMAGE_READER[0] = None


def test_no_click_reads():
    reads, lines, said = setup_clip()
    n = CR.COUNT["reads"]
    for ev in (None, Ev("4"), Ev("ButtonPress"), Ev("5"), Ev("ButtonRelease"), Ev("35", "")):
        ok(CR.app_paste(None, ev) == "" and CR.app_paste_image(ev) is None, f"no key event ({getattr(ev, 'type', None)}): "
                                                                            "app_paste reads nothing")
    ok(not reads and CR.COUNT["reads"] == n, "clicks / menus never read the clipboard")
    ok(CR.app_paste(None, Ev("2")) == "Item Class: Rings" and len(reads) == 1, "Ctrl+V (a key press) reads once")
    ok(CR.app_paste_image(Ev("KeyPress")) == "picture" and len(reads) == 2, "Ctrl+V on the Atlas step reads once")
    from soe2 import stratimg
    ok(stratimg.from_clipboard(event=Ev("ButtonPress")) is None and len(reads) == 2,
       "a click can't paste a strat picture")
    src = open(os.path.join(ROOT, "soe2", "listkit.py"), encoding="utf-8").read()
    ok(not re.search(r'label="Paste"', src), "the right-click menu has no Paste (a click would read)")
    ok("<<PasteSelection>>" in src and "event_delete" in src, "Tk's middle-click paste is off")
    for f in ("library_page.py", "feed_page.py", "favorites_page.py", "regex_page.py", "moneymakers_page.py",
              "ledger_page.py"):
        tree = ast.parse(open(os.path.join(ROOT, "soe2", f), encoding="utf-8").read())
        for n_ in ast.walk(tree):
            if isinstance(n_, ast.Call) and getattr(n_.func, "attr", "") in ("Button", "add_command"):
                for k in n_.keywords:
                    if k.arg == "command" and _refs(k.value) & {"fav_paste", "fl_ed_paste", "mm_tab_check",
                                                                "rx_paste_test", "fl_ed_shot_paste", "lib_paste",
                                                                "fd_paste"}:
                        FAILS.append(f"{f}:{n_.lineno}: a button / menu item reads the clipboard on a click")
        ok(True, f"{f}: no button reads the clipboard")
    CR.READER[0] = CR.IMAGE_READER[0] = None


def _refs(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
    return out


def test_no_clipboard_timer():
    from soe2.app import App
    for name in ("poll_clipboard", "restart_watcher"):
        ok(not hasattr(App, name), f"no clipboard watcher: App.{name} is gone")
    ok(hasattr(App, "clip_read_once") and hasattr(App, "ev_clipread"), "a copy key press reads through clip_read_once")
    import check_tos as C
    trees = []
    for path in C.files():
        src = open(path, encoding="utf-8").read()
        ok(not re.search(C.CLIP_WATCH, "\n".join(C.code_lines(src))), f"{os.path.relpath(path, ROOT)}: nothing "
                                                                        "watches the clipboard")
        trees.append((os.path.relpath(path, ROOT), ast.parse(src)))
    ok(not C.timer_readers(trees), "nothing that reads the clipboard runs again on a timer")
    ok(not C.screenread_rules(ast.parse(open(os.path.join(ROOT, "soe2", "clipread.py")).read()),
                              os.path.join("soe2", "clipread.py")), "clipread.py has no timer, thread or loop")
    # the read runs once, READ_DELAY after the press (a one-shot), and a second ask for the same press reads nothing
    reads, lines, said = setup_clip()

    class Root:
        def __init__(self):
            self.timers = []

        def after(self, ms, fn):
            self.timers.append((ms, fn))
    fake = App.__new__(App)
    fake.root, fake.ui_q = Root(), queue.Queue()
    gid = CR.grant("Ctrl+C", hold=0x43)
    fake.clip_granted(gid)
    ok(fake.ui_q.get_nowait() == ("clipread", gid), "a granted press is handed to the window thread")
    fake.ev_clipread(gid)
    ok(len(fake.root.timers) == 1 and 100 <= fake.root.timers[0][0] <= 301, "one one-shot read, ~READ_DELAY later")
    fake.ev_clipread(gid)
    ok(len(fake.root.timers) == 2, "(asked twice: two one-shots - the grant decides)")
    calls = []
    fake._clip_ignored = lambda t: False
    fake.topup_wants = fake.wealth_takes = lambda t: False
    fake.pc_wants = lambda t: True
    fake.pc_take = lambda t: calls.append(t)
    fake.status_text = ""
    for _ms, fn in fake.root.timers:
        fn()
    ok(calls == ["Item Class: Rings"] and len(reads) == 1, "two one-shots for one press: one read")
    ok(not any(fn for ms, fn in fake.root.timers if ms <= 0), "no read is scheduled without a delay")
    # not an item: one line, no retry
    reads, lines, said = setup_clip("hello")
    CR.release(0x43)
    gid = CR.grant("Ctrl+C", hold=0x43)
    fake.root.timers = []
    fake.ev_clipread(gid)
    for _ms, fn in fake.root.timers:
        fn()
    from soe2 import gamedata as GD
    ok(App.CLIP_MISSED == "The copy didn't land - press the key again.", "the missed-copy line")
    ok(fake.status_text == GD.COPY_NOT_ITEM, f"not an item: says so ({fake.status_text})")
    ok(len(reads) == 1 and len(fake.root.timers) == 1, "not an item: no retry")
    ok(said and "isn't an item" in said[-1][2][0], "the read mark says it isn't an item")
    for text, line in (("", GD.COPY_MISSED), ("Gegenstandsklasse: Ringe\nSeltenheit: Selten\nSaphirring\n--------\n"
                                                "Gegenstandsstufe: 82", GD.COPY_NOT_ENGLISH)):
        reads, lines, said = setup_clip(text)
        CR.release(0x43)
        gid = CR.grant("Ctrl+C", hold=0x43)
        fake.root.timers = []
        fake.ev_clipread(gid)
        for _ms, fn in fake.root.timers:
            fn()
        ok(fake.status_text == line and len(reads) == 1, f"{line[:30]}...: one read, one line ({fake.status_text})")
    CR.READER[0] = None


def test_key_watcher():
    """grant is called only from the key watcher's functions, and each of them is reached from App.on_any_key."""
    import check_tos as C
    trees = [(os.path.relpath(p, ROOT), ast.parse(open(p, encoding="utf-8").read())) for p in C.files()]
    ok(not C.grant_callers(trees), "nothing but the key watcher grants a read")
    src = open(os.path.join(ROOT, "soe2", "utilities_page.py"), encoding="utf-8").read()
    body = src[src.index("def on_any_key"):src.index("def on_any_key_up")]
    for _f, name in C.KEY_WATCHER:
        ok(name in body, f"the key watcher (on_any_key) reaches {name}")
    ok("self.keys.listener = self.on_any_key" in src, "the keyboard hook calls on_any_key")


def test_mark():
    from soe2.readmark import mark_text
    ok(mark_text("screen", ["Ritual", "Temple"]) == "👁 Screen read once: Ritual, Temple", "the screen mark's words")
    ok(mark_text("clipboard", ["Price Checks"]) == "👁 Clipboard read once: Price Checks", "the clipboard mark's words")
    ok("didn't land" in mark_text("clipboard", ["nothing - The copy didn't land - press the key again."]),
       "the missed-copy status line")
    from soe2 import gamedata as GD
    from soe2.readmark import card_text
    ok(card_text("screen", ["Ritual", "Temple"]) == "Reading the screen", "the card over the game: a few words")
    ok(card_text("clipboard", ["Price Checks"]) == "Reading the item", "the clipboard card")
    ok(card_text("clipboard", ["nothing - " + GD.COPY_NOT_ITEM]) == "Not an item", "not an item: two words")
    ok(card_text("clipboard", ["nothing - " + GD.COPY_MISSED]) is None, "nothing copied: no card")


def test_migration():
    from soe2 import migrations as M
    S = {"look_key": "Tab", "seen_version": "2.143.0"}
    M._look_key_dedicated(S)
    ok(S["look_key"] == "" and S.get("look_key_notice"), "an old Tab Read Key is cleared, with a notice")
    S = {"seen_version": "2.143.0", "migrations_done": ["look_key_policy"]}
    M._look_key_dedicated(S)
    ok(S["look_key"] == "" and S.get("look_key_notice"), "unset meant Tab: cleared, with a notice")
    S = {"seen_version": "2.143.0"}
    M._look_key_dedicated(S)
    ok(S["look_key"] == "" and not S.get("look_key_notice"), "from a build before the Read Key: no Tab notice")
    S = {"look_key": "F9", "seen_version": "2.143.0"}
    M._look_key_dedicated(S)
    ok(S["look_key"] == "F9" and not S.get("look_key_notice"), "a key you picked stays")
    S = {}
    M._look_key_dedicated(S)
    ok(S["look_key"] == "" and not S.get("look_key_notice"), "a new install: not set, nothing to tell")
    for before, notice, after, why in (("", True, "Ctrl+Shift+R", "unset (an old install)"), ("Tab", True, "Ctrl+Shift+R", "Tab"),
                                       ("F9", False, "F9", "a key you picked")):
        S = {"look_key": before, "seen_version": "2.143.0"}
        M._look_key_default(S)
        ok(S["look_key"] == after and bool(S.get("look_key_notice")) == notice,
           f"migration: {why} -> {after}{' with the notice' if notice else ''}")
    S = {}
    M._look_key_default(S)
    ok(S["look_key"] == "Ctrl+Shift+R" and not S.get("look_key_notice"), "a new install: Ctrl+Shift+R, no notice")
    S = {"delirium": {"on": True, "sound": True}, "util_delirium_autostart": True,
         "tracker": {"bar": {"delirium": True, "breach": True}, "delirium": 1}}
    M._delirium_gone(S)
    ok("delirium" not in S and "util_delirium_autostart" not in S and S["tracker"]["bar"] == {"breach": True}
       and "delirium" not in S["tracker"], "the removed Delirium helper's settings are cleared")


def test_checker():
    import check_tos as C
    ok(re.search(C.CAPTURE, "    import mss"), "the checker sees mss")
    ok(re.search(C.CAPTURE, "    from PIL import Image, ImageGrab"), "the checker sees PIL's ImageGrab")
    ok(re.search(C.CAPTURE, "x = ImageGrab.grab(bbox)"), "the checker sees ImageGrab.grab")
    ok(re.search(C.CAPTURE, "hdc.BitBlt(0, 0)") and re.search(C.CAPTURE, "import dxcam"), "BitBlt / dxcam")
    ok(not re.search(C.CAPTURE, "got = ImageGrab.grabclipboard()"), "grabclipboard is a clipboard read, not a capture")
    for api in ("t = self.root.clipboard_get()", "u.OpenClipboard(None)", "u.GetClipboardData(13)", "import pyperclip",
                "import win32clipboard", "n = u.GetClipboardSequenceNumber()", "u.SetClipboardData(13, h)"):
        ok(re.search(C.CLIPBOARD, api), f"the checker sees a clipboard API: {api}")
    for api in ("n = u.GetClipboardSequenceNumber()", "u.AddClipboardFormatListener(h)", "u.SetClipboardViewer(h)"):
        ok(re.search(C.CLIP_WATCH, api), f"the checker sees a clipboard watcher: {api}")
    for rel in (C.SCREEN_FILE, C.CLIP_FILE):
        ok(C.screenread_rules(ast.parse("def f(root):\n    root.after(100, f)\n"), rel), f"a timer in {rel} fails")
        ok(C.screenread_rules(ast.parse("import threading\nthreading.Thread(target=f).start()\n"), rel),
           f"a thread in {rel} fails")
        ok(C.screenread_rules(ast.parse("def f():\n    while True:\n        pass\n"), rel), f"a while loop in {rel} fails")
    ok(C.screenread_rules(ast.parse("def f():\n    for i in range(3):\n        capture((0,0,1,1), 'x')\n"), "x"),
       "a loop that captures fails")
    ok(C.screenread_rules(ast.parse("def f():\n    for i in range(3):\n        _raw()\n"), C.CLIP_FILE),
       "a loop that reads the clipboard fails")
    for rel in (C.SCREEN_FILE, C.CLIP_FILE):
        ok(not C.screenread_rules(ast.parse(open(os.path.join(ROOT, rel)).read()), rel), f"the real {rel} passes")
    src = "class A:\n    def on_click(self):\n        screenread.grant('x')\n"
    ok(C.grant_callers([("soe2/x.py", ast.parse(src))]), "a grant from a click handler fails the check")
    src = "class A:\n    def tick(self):\n        clipread.grant('x')\n"
    ok(C.grant_callers([(os.path.join("soe2", "utilities_page.py"), ast.parse(src))]),
       "a grant from a timer function fails the check")
    src = "class A:\n    def look_on_key(self):\n        SR.grant('x')\n"
    ok(not C.grant_callers([(os.path.join("soe2", "look_page.py"), ast.parse(src))]), "the key watcher may grant")
    src = "class A:\n    def poll(self):\n        clipread.take(1)\n        self.root.after(150, self.poll)\n"
    ok(C.timer_readers([("x.py", ast.parse(src))]), "a clipboard watcher (read + after itself) fails the check")
    src = "class A:\n    def go(self, gid):\n        self.root.after(200, lambda: self.once(gid))\n" \
          "    def once(self, gid):\n        clipread.take(gid)\n"
    ok(not C.timer_readers([("x.py", ast.parse(src))]), "a one-shot read after a press passes")
    src = ("class A:\n    def tick(self):\n        self.fire()\n        self.root.after(500, self.tick)\n"
           "    def fire(self):\n        send_copy()\n")
    ok(C.timer_senders([("x.py", ast.parse(src))]), "a key sender reachable from a timer fails the check")
    src = "class A:\n    def key(self):\n        send_copy()\n    def tick(self):\n        self.root.after(5, self.tick)\n"
    ok(not C.timer_senders([("x.py", ast.parse(src))]), "a key handler next to an unrelated timer passes")
    ok(not C.check(), "the app passes check_tos")


def main():
    for t in (test_gate, test_look_key, test_scan_stash_click, test_clipboard, test_no_click_reads,
              test_no_clipboard_timer, test_key_watcher, test_mark, test_migration, test_checker):
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            FAILS.append(f"{t.__name__}: {e.__class__.__name__}: {e}")
    SR.reset()
    CR.reset()
    for f in FAILS:
        print("FAIL:", f)
    print(f"check_screenread: {PASSED[0]} passed, {len(FAILS)} failed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
