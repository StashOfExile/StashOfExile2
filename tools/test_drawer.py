"""Drawer tests (T1-T10 of drawer/PLAN.md). Harness only in D0: it skips cleanly while soe2/drawer.py doesn't exist.

Run (Linux, needs Xvfb; starts its own Xvfb on :12 at 2560x1440):
  python3.12 tools/test_drawer.py                 all tests
  python3.12 tools/test_drawer.py T1 T3           only these
  python3.12 tools/test_drawer.py --list          the tests and which phase adds them
  SOE2_DRAWER_FORCE=1 python3.12 tools/test_drawer.py   run the rig (H0) even without soe2/drawer.py (rig check)

Exit code: 0 all pass or skipped; 1 a test failed. A test that is only a TODO stub is reported TODO, never a failure.

Structure:
  UNIT tests  - pure functions / fakes, run in this process, no Tk, no display.   def t_T1(): ... ; raise AssertionError
  APP tests   - run INSIDE a real App on the Xvfb (a child process, like tools/smoke_pages.py): a generator that gets
                the Ctx, yields milliseconds to wait (the Tk loop keeps running) and asserts with ctx.check().
Add a test: write the function, put it in UNIT / APP with its id, and remove it from TODO. D1 adds T1 T2 T3, D2 adds
T4-T8, D4 adds T9 T10 (see TODO below). RESTART tests run in a second child on the same HOME (T3f = T3's restart)."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPLAY = ":12"
SCREEN = (2560, 1440)
DATA = "/tmp/h2/.stashofexile2"
OFFLINE = "http://127.0.0.1:9"


def drawer_exists():
    return os.path.exists(os.path.join(ROOT, "soe2", "drawer.py")) or bool(os.environ.get("SOE2_DRAWER_FORCE"))


# ============================================================================ the tests
def _eq(got, want, what):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


# ---- unit (no Tk) ---------------------------------------------------------------------------------------------
def t_T1():
    """T1 (D1): drawer_rect table of section 1.3, to_workspace, clamp_share."""
    from soe2 import drawer as D
    R = D.drawer_rect
    _eq(R((0, 0, 2560, 1440), side="right"), (1536, 0, 1024, 1270), "2560x1440 right")
    _eq(R((0, 0, 2560, 1440), side="left"), (0, 0, 1024, 1270), "2560x1440 left")
    _eq(R((0, 0, 1920, 1080)), (1020, 0, 900, 953), "1920x1080")
    # (PLAN's table says 1906: 2160 x (1 - 0.118) = 1905.12 -> 1905, the same rounding as every other row)
    _eq(R((0, 0, 3840, 2160)), (2640, 0, 1200, 1905), "3840x2160")
    _eq(R((0, 0, 1280, 720)), (380, 0, 900, 635), "1280x720")
    _eq(R((2560, 0, 2560, 1440))[0], 4096, "game on monitor 2: x")
    _eq(R((-1920, 0, 1920, 1080))[0], -900, "monitor left of the primary: x")
    _eq(R(None, (0, 0, 1920, 1040)), (1020, 0, 900, 1040), "no game, work area")
    _eq(R(None, (0, 0, 1920, 1040), side="left"), (0, 0, 900, 1040), "no game, left")
    _eq(R(None, None), None, "nothing known")
    _eq(R((0, 0, 1000, 700))[2], 800, "a small game: at most its width - 200")
    _eq(R((0, 0, 2560, 1440), share=0.30)[2], 900, "share 0.30 -> clamped to 900")
    _eq(R((0, 0, 2560, 1440), share=0.45)[2], 1152, "share 0.45")
    # to_workspace: workspace = screen less the work area's offset (the taskbar at the top / left)
    _eq(D.to_workspace((1536, 0, 1024, 1270)), (1536, 0, 2560, 1270), "to_workspace, no offset")
    _eq(D.to_workspace((1536, 40, 1024, 1270), (0, 40)), (1536, 0, 2560, 1270), "to_workspace, taskbar on top")
    _eq(D.to_workspace((60, 0, 900, 1040), (60, 0)), (0, 0, 900, 1040), "to_workspace, taskbar on the left")
    _eq(D.to_workspace((-900, 0, 900, 1080), (0, 0)), (-900, 0, 0, 1080), "to_workspace, left monitor")
    # clamp_share
    for v, want in ((0.1, 0.25), (0.9, 0.70), (0.5, 0.5), (0.40, 0.40), ("x", 0.40), (None, 0.40),
                    (float("nan"), 0.40), ("0.33", 0.33)):
        _eq(D.clamp_share(v), want, f"clamp_share({v!r})")
    # the side flip (a price check with the mouse inside the would-be Drawer)
    rf = lambda side: R((0, 0, 2560, 1440), side=side)
    _eq(D.flip_for_cursor("right", (2000, 600), rf), "left", "mouse in the right Drawer -> left")
    _eq(D.flip_for_cursor("right", (500, 600), rf), "right", "mouse elsewhere -> stays right")
    _eq(D.flip_for_cursor("left", (500, 600), rf), "right", "mouse in the left Drawer -> right")
    _eq(D.flip_for_cursor("right", None, rf), "right", "no mouse -> stays")
    # cfg: every key setdefault (nothing renamed or removed)
    s = {"drawer": {"shape": "full", "extra": 1}}
    c = D.cfg(s)
    _eq((c["shape"], c["side"], c["share"], c["click_away"], c["extra"]), ("full", "right", 0.40, True, 1), "cfg")
    _eq(D.cfg({})["shape"], "drawer", "cfg default shape")


def t_T2():
    """T2 (D1): DrawerState, every row of section 1.2, with fakes."""
    from soe2.drawer import DrawerState, AWAY, SHOWN
    s = DrawerState("drawer")
    _eq(s.visible, SHOWN, "starts shown (the window is built on screen)")
    _eq(s.away(), ("away",), "start-up: put away")
    # AWAY + Drawer key / tray / taskbar / App ▸ -> SHOWN in the remembered shape, focused
    _eq(s.key(), ("show", "drawer", True, None), "AWAY key")
    _eq((s.visible, s.opened_by, s.had_focus), (SHOWN, "key", False), "after the key")
    # SHOWN (Drawer) + Drawer key -> AWAY
    _eq(s.key(app_front=False), ("away",), "SHOWN drawer key (game in front)")
    s.show("key")
    _eq(s.key(app_front=True), ("away",), "SHOWN drawer key (app in front)")
    # AWAY + Ctrl+D (In the app) -> SHOWN on Price Checks, quiet
    _eq(s.price(), ("show", "drawer", False, "pricecheck"), "AWAY price")
    _eq(s.opened_by, "price", "opened_by price")
    # SHOWN (Drawer) + Ctrl+D -> stays, shows the new check (opened_by kept)
    s.had_focus = True
    _eq(s.price(), ("show", "drawer", False, "pricecheck"), "SHOWN price")
    _eq((s.opened_by, s.had_focus), ("price", True), "SHOWN price keeps opened_by / had_focus")
    # SHOWN (Drawer) + Esc in the app -> AWAY; + the close key in game -> AWAY
    _eq(s.esc(), ("away",), "Esc in the app")
    _eq(s.esc_in_game(), None, "close key in game while away: not ours")
    s.show("key")
    _eq(s.esc_in_game(), ("away",), "close key in game, Drawer shown")
    # restored by the taskbar -> SHOWN in the remembered shape
    _eq(s.restored(), ("show", "drawer", True, None), "taskbar restore")
    _eq(s.opened_by, "restore", "opened_by restore")
    _eq(s.restored(), None, "restore while shown: nothing")
    # SHOWN (Drawer) + ⤢ Full window -> SHOWN (Full); shape := full
    _eq(s.full(), ("show", "full", True, None), "⤢ Full window")
    _eq((s.shape, s.eff, s.as_drawer()), ("full", "full", False), "shape full")
    # SHOWN (Full) + Drawer key: app in front -> AWAY; not in front -> to the front
    _eq(s.key(app_front=False), ("front",), "Full, key, app not in front")
    _eq(s.key(app_front=True), ("away",), "Full, key, app in front")
    _eq(s.key(), ("show", "full", True, None), "AWAY Full: key -> shown Full")
    # SHOWN (Full): a close key in game never puts it away; a click on the game does nothing
    _eq(s.esc_in_game(), None, "Full: close key in game")
    _eq((s.fg(True, False), s.fg(False, True)), (None, None), "Full: click on the game")
    _eq(s.visible, SHOWN, "Full stays shown")
    # SHOWN (Full) + Esc -> AWAY (today's minimize)
    _eq(s.esc(), ("away",), "Full Esc")
    _eq(s.full(), None, "⤢ while away: shape only")
    s.show("key")
    # SHOWN (Full) + ⇤ Drawer -> SHOWN (Drawer); shape := drawer
    _eq(s.dock(), ("show", "drawer", True, None), "⇤ Drawer")
    _eq(s.shape, "drawer", "shape drawer")
    # a Full window for this session (something to ask at start): until put away
    t = DrawerState("drawer")
    t.session_full = True
    _eq((t.eff, t.as_drawer()), ("full", False), "session full")
    _eq(t.key(app_front=True), ("away",), "session full: key")
    _eq((t.eff, t.shape), ("drawer", "drawer"), "after put away: the Drawer again")
    _eq(t.key(), ("show", "drawer", True, None), "next show: the Drawer")
    t.gone()
    _eq(t.visible, AWAY, "gone (minimized by itself)")
    # a bad shape name -> the default
    _eq(DrawerState("compact").shape, "drawer", "unknown shape")


def t_T5():
    """T5 (D2): FG_HOOK sequences: ours->game puts away; game->game stays; ours->other stays; price-opened + game ticks stays."""
    from soe2.drawer import DrawerState
    s = DrawerState("drawer")
    s.away()
    s.key()                                               # shown by the key: the app takes the keyboard
    _eq(s.fg(True, False), None, "ours")
    _eq(s.fg(False, True), ("away",), "ours -> game: put away")
    s.key()
    _eq([s.fg(False, True) for _ in range(5)], [None] * 5, "game -> game (never ours since shown): stays")
    s.away()
    s.key()
    _eq((s.fg(True, False), s.fg(False, False), s.fg(False, False)), (None, None, None), "ours -> other: stays")
    _eq(s.fg(False, True), None, "other -> game: stays (it wasn't ours on the last tick)")
    s.away()
    s.price()                                             # quiet: the game keeps the keyboard
    _eq([s.fg(False, True) for _ in range(6)], [None] * 6, "price-opened, game ticks: stays")
    _eq((s.fg(True, False), s.fg(False, True)), (None, ("away",)), "price-opened, then used, then the game: away")
    s.away()
    s.key()
    s.click_away = False
    _eq((s.fg(True, False), s.fg(False, True)), (None, None), "click-away off: stays")
    s.click_away = True
    s.full()
    _eq((s.fg(True, False), s.fg(False, True)), (None, None), "Full window: never put away by a click")


def t_T7():
    """T7 (D2): grep: no root.deiconify() / root.focus_force() outside drawer_page.py and the tray / unminimize code in app.py."""
    import glob
    import re
    rx = re.compile(r"\broot\.(deiconify|focus_force)\(\)")
    allowed_app = ("def unminimize", "def ev_tray", "def go_tray")
    bad = []
    for path in sorted(glob.glob(os.path.join(ROOT, "soe2", "**", "*.py"), recursive=True)):
        rel = os.path.relpath(path, ROOT)
        if rel in (os.path.join("soe2", "drawer_page.py"), os.path.join("soe2", "drawer.py")):
            continue
        func = None
        for no, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            m = re.match(r"\s*def (\w+)", line)
            if m:
                func = "def " + m.group(1)
            code = line.split("#", 1)[0]
            if rx.search(code):
                if rel == os.path.join("soe2", "app.py") and func in allowed_app:
                    continue
                bad.append(f"{rel}:{no} ({func}): {line.strip()[:80]}")
    if bad:
        raise AssertionError("bring-forward calls outside app_show: " + "; ".join(bad))


# ---- app (inside a real App; generators) ------------------------------------------------------------------------
def a_H0(ctx):
    """H0 (rig): the app starts on the Xvfb and the Tk loop answers. Always on; proves the harness works."""
    yield 300
    ctx.check(ctx.root.winfo_exists(), "root exists")
    from soe2.config import TAGLINE
    ctx.check(ctx.root.title().endswith(TAGLINE), f"title ends with the tagline: {ctx.root.title()!r}")
    yield 1


def _until(cond, ms=6000, step=100):
    """yield-wait until cond() (or ms run out)."""
    t = 0
    while t < ms:
        try:
            if cond():
                return
        except Exception:
            pass
        yield step
        t += step


def _away(root):
    return root.state() in ("iconic", "withdrawn")


def _rect(root):
    return root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()


def _near(a, b, tol=40):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def a_T3(ctx):
    """T3 (D1): (a) shape drawer starts put away; (b) ev_drawer("key") -> normal, rect (1536,0,1024,1270) +-40,
    topmost, sidebar.compact; (c) hk_esc -> put away; (d) key then Full -> main_window geometry, Drawer left it alone;
    (e) SETTINGS["on_top"] unchanged; (f) restart: shape remembered, Full starts shown; (g) Keybinds row + Defaults;
    (h) on_any_key(0x20, True, False, True) True and queues the event; (i) on_unmap after our put-away: no unminimize."""
    from soe2.config import SETTINGS
    from soe2 import drawer as D
    app, root = ctx.app, ctx.root
    on_top0 = SETTINGS.get("on_top")
    mw0 = json.dumps(SETTINGS.get("main_window"), sort_keys=True)
    # (a)
    yield from _until(lambda: app._drawer_started, 12000)
    yield 500
    ctx.check(app._drawer_started, "(a) drawer_startup ran")
    ctx.check(_away(root), f"(a) starts put away: state {root.state()!r}")
    ctx.check(app.drawer_st.visible == D.AWAY, "(a) state AWAY")
    # (b)
    app.ev_drawer("key")
    yield from _until(lambda: root.state() == "normal", 3000)
    yield 600
    ctx.check(root.state() == "normal", f"(b) shown: state {root.state()!r}")
    ctx.check(_near(_rect(root), (1536, 0, 1024, 1270)), f"(b) rect {_rect(root)} ~ (1536, 0, 1024, 1270)")
    ctx.check(ctx.topmost() == 1, "(b) topmost")
    ctx.check(app.shell.sidebar.compact, "(b) sidebar compact")
    ctx.check(app.drawer_st.opened_by == "key" and D.SHOWN_DRAWER[0], "(b) opened_by key, SHOWN_DRAWER")
    ctx.check(app.drawer_strip.say.cget("text").startswith("Drawer · right"),
              f"(b) the strip says it: {app.drawer_strip.say.cget('text')!r}")
    # (c) + (i): Esc puts it away; on_unmap doesn't bring it back
    calls = []
    orig_un, orig_um = app.unminimize, app.user_minimized
    app.unminimize = lambda: calls.append(1)
    app.user_minimized = lambda: False                     # (as if something else minimized it)
    app.hk_esc()
    yield from _until(lambda: _away(root), 3000)
    yield 800
    ctx.check(_away(root), f"(c) hk_esc puts it away: state {root.state()!r}")
    ctx.check(not calls, "(i) on_unmap after our put-away didn't call unminimize")
    app.unminimize, app.user_minimized = orig_un, orig_um
    # (h): the Drawer key through the key watcher's listener
    put = []
    orig_put = app.ui_q.put
    app.ui_q.put = lambda ev, *a, **k: (put.append(ev), orig_put(ev, *a, **k))[1]
    used = app.on_any_key(0x20, True, False, True)
    app.ui_q.put = orig_put
    ctx.check(used is True, f"(h) on_any_key(Ctrl+Shift+Space) -> {used!r}")
    ctx.check(("drawer", "key") in put, f"(h) queued: {put}")
    ctx.check(app.on_any_key(0x20, False, False, True) is not True, "(h) Shift+Space isn't the Drawer key")
    yield from _until(lambda: root.state() == "normal", 3000)
    yield 600
    ctx.check(root.state() == "normal", "(h) the queued key showed the Drawer")
    ctx.check(json.dumps(SETTINGS.get("main_window"), sort_keys=True) == mw0, "(d) the Drawer didn't write main_window")
    # (d): ⤢ Full window -> the Full window's own place
    SETTINGS["main_window"] = {"w": 1300, "h": 900, "x": 100, "y": 50, "zoomed": False}
    app.drawer_full()
    yield 1200
    ctx.check(SETTINGS["drawer"]["shape"] == "full", "(d) shape := full")
    r = (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height())
    ctx.check(_near(r, (100, 50, 1300, 900)), f"(d) Full rect {r} ~ main_window (100, 50, 1300, 900)")
    ctx.check(ctx.topmost() == int(bool(SETTINGS.get("on_top"))), "(d) topmost = on_top")
    ctx.check(app.drawer_strip.say.cget("text").startswith("Full window"), "(d) the strip says Full window")
    # the Drawer key in Full with the app in front -> put away; again -> Full shown
    D.FG_HOOK = lambda: (True, False)
    app.ev_drawer("key")
    yield from _until(lambda: _away(root), 2000)
    ctx.check(_away(root), "(d) Full + key (app in front) -> put away")
    app.ev_drawer("key")
    yield from _until(lambda: root.state() == "normal", 2000)
    yield 600
    D.FG_HOOK = None
    r = (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height())
    ctx.check(root.state() == "normal" and _near(r, (100, 50, 1300, 900)), f"(d) key again -> Full where it was {r}")
    # (g): Keybinds - the Drawer row, and Defaults puts Ctrl+Shift+Space back
    rows = [r for r in app.all_hotkeys() if r[3] == "checks:drawer_key"]
    ctx.check(len(rows) == 1 and rows[0][2] == "App", f"(g) Keybinds row: {rows}")
    ctx.check(app.all_hotkeys()[0][3] == "checks:drawer_key", "(g) first row")
    from soe2 import settings_page
    v = app.hk_vars.get("checks:drawer_key")
    ctx.check(v is not None, "(g) Keybinds shows the Drawer key box")
    if v is not None:
        v.set("F3")
        app.save_hotkeys()
        ctx.check(SETTINGS.get("drawer_key") == "F3" and app._drawer_key == (0x72, False, False, False),
                  "(g) set to F3: saved and cached")
        v = app.hk_vars.get("checks:drawer_key")
        v.set("")
        app.save_hotkeys()
        ctx.check(SETTINGS.get("drawer_key") == "", "(g) cleared")
        ctx.check(str(app.drawer_strip.btns["dock"][0].state()).find("disabled") >= 0, "(g) ⇤ Drawer grayed out")
        orig_ask = settings_page.messagebox.askyesno
        settings_page.messagebox.askyesno = lambda *a, **k: True
        try:
            app.hotkeys_defaults()
        finally:
            settings_page.messagebox.askyesno = orig_ask
        ctx.check(SETTINGS.get("drawer_key") == "Ctrl+Shift+Space", f"(g) Defaults: {SETTINGS.get('drawer_key')!r}")
        ctx.check(app._drawer_key == (0x20, True, False, True), "(g) the cache follows")
    # (e)
    ctx.check(SETTINGS.get("on_top") == on_top0, f"(e) on_top unchanged: {SETTINGS.get('on_top')!r}")
    yield 1


def a_T3f(ctx):
    """T3 (f) (D1, a restart of the T3 child): the shape is remembered, and the Full shape starts shown."""
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    yield 800
    ctx.check(SETTINGS.get("drawer", {}).get("shape") == "full", f"(f) shape remembered: {SETTINGS.get('drawer')}")
    ctx.check(app.drawer_st.eff == "full", "(f) the app is a Full window")
    ctx.check(root.state() == "normal", f"(f) Full starts shown: {root.state()!r}")
    app.drawer_dock()                                    # (back to the Drawer for the tests after this one)
    yield 600


SAMPLE_RARE = """Item Class: Rings
Rarity: Rare
Doom Loop
Sapphire Ring
--------
Requires: Level 40
--------
Item Level: 75
--------
+18% to Cold Resistance (implicit)
--------
+45 to maximum Life
+30% to Fire Resistance
+25% to Lightning Resistance
"""


def _shown_drawer(ctx, why="key"):
    """Show the Drawer (shape drawer) and wait for it."""
    app, root = ctx.app, ctx.root
    if app.drawer_st.shape != "drawer":
        app.drawer_dock()
    app.app_show(focus=True, why=why)
    yield from _until(lambda: root.state() == "normal", 3000)
    yield 500


def _put_away(ctx):
    app, root = ctx.app, ctx.root
    app.drawer_put_away("test")
    yield from _until(lambda: _away(root), 3000)
    yield 600


def a_T4(ctx):
    """T4 (D2): pc_take with a sample rare item (offline): pc_popup False -> shown on pricecheck, focus_force spy 0,
    opened_by "price"; pc_popup True -> root untouched, pcpop shown."""
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    if app.drawer_st.shape != "drawer":
        app.drawer_dock()
        yield 300
    if not _away(root):
        yield from _put_away(ctx)
    pop0 = SETTINGS.get("pc_popup")
    SETTINGS["pc_popup"] = False
    calls = []
    orig_ff = root.focus_force
    root.focus_force = lambda *a: calls.append(1)
    rid = app.pc_take(SAMPLE_RARE)
    yield from _until(lambda: root.state() == "normal", 3000)
    yield 600
    root.focus_force = orig_ff
    ctx.check(rid is not None, "the sample item was taken")
    ctx.check(root.state() == "normal", f"In the app: shown ({root.state()!r})")
    ctx.check(app.shell.active == "pricecheck", f"In the app: on Price Checks ({app.shell.active!r})")
    ctx.check(not calls, f"In the app: focus_force called {len(calls)} times")
    ctx.check(app.drawer_st.opened_by == "price", f"opened_by {app.drawer_st.opened_by!r}")
    ctx.check(app.drawer_st.as_drawer(), "shown as the Drawer")
    # Price check overlay: the app isn't touched
    yield from _put_away(ctx)
    SETTINGS["pc_popup"] = True
    rid = app.pc_take(SAMPLE_RARE)
    yield 1200
    ctx.check(_away(root), f"Price check overlay: the app stays put away ({root.state()!r})")
    ctx.check(getattr(app, "pp_win", None) is not None or getattr(app, "pp_up", False), "Price check overlay: shown")
    try:
        app.pcpop_close()
    except Exception:
        pass
    SETTINGS["pc_popup"] = pop0
    # the side flip: a price check with the mouse inside the would-be Drawer opens it on the other side
    from soe2 import drawer as D
    SETTINGS["pc_popup"] = False
    D.CURSOR_HOOK = lambda: (2200, 600)
    app.pc_take(SAMPLE_RARE)
    yield from _until(lambda: root.state() == "normal", 3000)
    yield 600
    D.CURSOR_HOOK = None
    ctx.check(_near(_rect(root), (0, 0, 1024, 1270)), f"side flip: opened on the left {_rect(root)}")
    ctx.check(app.drawer_cfg()["side"] == "right", "side flip: not saved")
    SETTINGS["pc_popup"] = pop0
    yield from _put_away(ctx)


def a_T6(ctx):
    """T6 (D2): on_any_key(Esc) with FG_HOOK=game, Drawer shown -> True and put away; Drawer away -> False."""
    from soe2 import drawer as D
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    yield from _shown_drawer(ctx)
    D.FG_HOOK = lambda: (False, True)                   # the game has the keyboard
    try:
        used = app.on_any_key(0x1B, False, False, False)
        ctx.check(used is True, f"Esc in game, Drawer shown -> {used!r}")
        yield from _until(lambda: _away(root), 3000)
        yield 400
        ctx.check(_away(root), f"put away ({root.state()!r})")
        used = app.on_any_key(0x1B, False, False, False)
        ctx.check(used is not True, f"Esc in game, Drawer away -> {used!r} (the key goes to the game)")
        # a Full window is never put away by Esc in game
        app.drawer_full()
        yield 300
        app.app_show(focus=True, why="key")
        yield from _until(lambda: root.state() == "normal", 3000)
        yield 400
        used = app.on_any_key(0x1B, False, False, False)
        ctx.check(used is not True, f"Esc in game, Full window -> {used!r}")
        yield 400
        ctx.check(root.state() == "normal", "Full window stays")
        app.drawer_dock()
        yield 300
        # click-away, in the app: the app had the keyboard, then the game got it
        D.FG_HOOK = lambda: (True, False)
        yield 800
        ctx.check(root.state() == "normal" and app.drawer_st.had_focus, "click-away: ours -> stays")
        D.FG_HOOK = lambda: (False, True)
        yield from _until(lambda: _away(root), 3000)
        ctx.check(_away(root), "click-away: ours -> game -> put away")
    finally:
        D.FG_HOOK = None


def a_T8(ctx):
    """T8 (D2, changed in D4): bar_buttons has "app" by default and never "goto" (the ⌕ button is gone); the setting
    off removes "app"."""
    app = ctx.app
    yield 100
    b = app.bar_buttons()
    ctx.check("app" in b and "goto" not in b, f"default: {b}")
    ctx.check("goto" not in app.TOOL_TIPS and "goto" not in app.TOOL_NAMES, "no ⌕ tool left")
    app.quick_bar_set("app", False)
    yield 300
    b = app.bar_buttons()
    ctx.check("app" not in b and "goto" not in b, f"off: {b}")
    ctx.check(app.bar_cfg().get("app") is False, "stored in tracker.bar.app")
    v = (getattr(app, "tk_bar_vars", None) or {}).get("app")
    ctx.check(v is None or v.get() is False or v.get() == 0, "Overlay › On the Overlay shows the same switch")
    app.quick_bar_set("app", True)
    yield 300
    b = app.bar_buttons()
    ctx.check("app" in b and "goto" not in b, f"on again: {b}")
    ctx.check(app.TOOL_TIPS.get("app"), "App ▸ has a tooltip")


def _closeall(app):
    for n in ("_whatsnew", "feat_win"):
        w = getattr(app, n, None)
        try:
            if w is not None and w.winfo_exists():
                w.destroy()
        except Exception:
            pass
    app._whatsnew = None
    app.feat_win = None


def a_T9(ctx):
    """T9 (D4): Setup has 4 steps with the Overlay, 3 without; the last screen asks Drawer / Full window and shows
    the key; Done with Drawer -> shape drawer, shown as the Drawer (and Full -> shape full)."""
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    yield 500
    _closeall(app)
    w = app.features_picker()
    yield 300
    st = w.setup_state
    st["overlay"].set("yes")
    w.setup_go(0)
    yield 100
    ctx.check(_label_text(w, "Step 1 of 4"), "with the Overlay: Step 1 of 4")
    st["overlay"].set("no")
    w.setup_go(0)
    yield 100
    ctx.check(_label_text(w, "Step 1 of 3"), "without the Overlay: Step 1 of 3")
    w.setup_go(3)
    yield 100
    ctx.check(_label_text(w, "How should the app sit with the game?"), "the last screen asks how the app sits")
    ctx.check(_label_text(w, "Ctrl+Shift+Space"), "the last screen shows the key")
    ctx.check(_label_text(w, "Step 3 of 3"), "the last screen is Step 3 of 3 (no Overlay)")
    st["overlay"].set("yes")
    w.setup_go(3)
    yield 100
    ctx.check(_label_text(w, "Step 4 of 4"), "the last screen is Step 4 of 4 (with the Overlay)")
    st["shape"].set("full")
    w.setup_done()
    yield 800
    ctx.check(SETTINGS["drawer"]["shape"] == "full" and app.drawer_st.eff == "full", "Done with Full window: shape full")
    w = app.features_picker()
    yield 300
    w.setup_go(3)
    w.setup_state["shape"].set("drawer")
    w.setup_done()
    yield from _until(lambda: root.state() == "normal" and app.drawer_st.as_drawer(), 4000)
    yield 600
    ctx.check(SETTINGS["drawer"]["shape"] == "drawer", "Done with Drawer: shape drawer")
    ctx.check(root.state() == "normal" and app.drawer_st.as_drawer(), "Done with Drawer: shown as the Drawer")
    ctx.check(SETTINGS["drawer"].get("first_run_done"), "first_run_done")
    yield from _put_away(ctx)


def _label_text(w, needle):
    """Is there a label in the window whose text has `needle`?"""
    import tkinter as tk

    def walk(x):
        for c in x.winfo_children():
            if isinstance(c, tk.Label) and needle in str(c.cget("text")):
                return True
            if walk(c):
                return True
        return False
    return walk(w)


def a_T9b(ctx):
    """T9b (D4, own HOME: an existing install on its first start of this build): What's new and Setup show (whatever
    was chosen before), as a Full window; closing Setup with x -> after_asks -> the Drawer takes over (put away) and
    first_run_done is set."""
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    ctx.check(app.drawer_st.eff == "full" and not _away(root), "first run: a Full window while it asks")
    yield from _until(lambda: getattr(app, "_whatsnew", None) is not None, 8000)
    ctx.check(getattr(app, "_whatsnew", None) is not None, "What's new shows on the first start")
    yield 800
    app.close_whatsnew()
    yield from _until(lambda: getattr(app, "feat_win", None) is not None, 8000)
    ctx.check(getattr(app, "feat_win", None) is not None, "Setup shows on the first start")
    yield 3500
    ctx.check(not _away(root) and not SETTINGS["drawer"].get("first_run_done"), "still asking: not put away yet")
    app.features_close(app.feat_win)
    yield from _until(lambda: _away(root), 14000)
    ctx.check(_away(root), f"the Drawer took over: put away ({root.state()!r})")
    ctx.check(SETTINGS["drawer"].get("first_run_done"), "first_run_done set")
    ctx.check(app.drawer_st.eff == "drawer", "the shape is the Drawer")


def a_T10(ctx):
    """T10 (D4): app put away, fire league_notice -> no messagebox while away; after app_show, it asks."""
    import datetime
    from soe2.config import SETTINGS
    from soe2 import app as A
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    yield 500
    if not _away(root):
        yield from _put_away(ctx)
    start, until, key = app.LEAGUE_NOTICE
    SETTINGS[key] = False
    calls = []
    orig = A.messagebox.showinfo
    A.messagebox.showinfo = lambda *a, **k: calls.append(a[:1])
    try:
        today = datetime.date.today()                     # (the notice's days, moved so that today is one of them)
        A.App.LEAGUE_NOTICE = ((today - datetime.timedelta(days=1)).isoformat(),
                               (today + datetime.timedelta(days=5)).isoformat(), key)
        shown = app.league_notice()
        yield 500
        ctx.check(not calls and shown is False, f"away: no messagebox ({calls})")
        ctx.check(not SETTINGS.get(key), "away: not marked as shown")
        ctx.check(app.league_notice in app._asks_wait, "away: held for the next show")
        ctx.check(app.er_start not in app._asks_wait and app.cm_start not in app._asks_wait,
                  "only questions are held (the hourly work isn't)")
        app._asking += 1                                  # (D5: another question is open when the app shows)
        app.app_show(focus=True, why="key")
        yield 2500
        ctx.check(not calls, "never two questions at once")
        app._asking -= 1                                  # (...answered: the held one comes next, not lost)
        yield from _until(lambda: calls, 6000)
        ctx.check(len(calls) == 1, f"after app_show it asks once ({calls}; wait={app._asks_wait} open={app.asks_open()} "
                                   f"away={app.drawer_is_away()} state={root.state()})")
        ctx.check(SETTINGS.get(key), "asked: marked as shown")
    finally:
        A.messagebox.showinfo = orig
        A.App.LEAGUE_NOTICE = (start, until, key)
        SETTINGS[key] = False
    yield from _put_away(ctx)


def a_T11(ctx):
    """T11 (D3 + D4): the Drawer's look - the sidebar is the icon rail whatever the width, with a real tooltip text
    ("Trade > Price Checks"); the strip's buttons are icons with tooltips and fit their height; the page header is
    tighter; the price check is stacked."""
    from soe2.config import SETTINGS
    from soe2 import drawer as D
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    app.drawer_cfg()["share"] = 0.47                       # 1203 -> 1200 wide: above the old 1100 threshold
    yield from _shown_drawer(ctx)
    yield 1500
    ctx.check(root.winfo_width() >= 1150, f"the Drawer is wide: {root.winfo_width()}")
    sb = app.shell.sidebar
    ctx.check(sb.compact, "the sidebar is the rail at 1200 px")
    ctx.check(sb.rail_text("pricecheck") == "Trade \u203a Price Checks", f"rail text {sb.rail_text('pricecheck')!r}")
    ctx.check(sb.rail_text("_goto").startswith("Go to anything"), "rail text for Go to anything")
    strip = app.drawer_strip
    for k, (b, tip) in strip.btns.items():
        ctx.check(bool(tip.text), f"strip button {k} has a tooltip")
        ctx.check(len(str(b.cget("text"))) <= 2, f"strip button {k} is an icon ({b.cget('text')!r})")
    h = int(float(str(strip.cget("height"))))
    need = max(b.winfo_reqheight() for b, _t in strip.btns.values())
    ctx.check(h >= need, f"the strip ({h}) is as tall as its buttons ({need})")
    app.shell.open("pricecheck")
    yield 800
    bar = app.shell.windows["pricecheck"].bar
    ctx.check(bar.height_now() == 108 and int(float(str(bar.cget("height")))) == 108,
              f"the mockup's page header (group, name, line): {bar.height_now()}")
    tabs = getattr(app.shell.windows["pricecheck"], "_dtabs", None)
    ctx.check(tabs is not None and tabs.winfo_ismapped(), "the Drawer shows the page's tabs (Check, History)")
    from soe2.sidebar import RAIL
    ctx.check(int(float(str(sb.cget("width")))) == RAIL, f"the rail is the Drawer's wide one: {sb.cget('width')}")
    ctx.check(sb.rail_label("rates") == "Rates" and sb.rail_label("pricecheck") == "Price Checks",
              f"rail labels: {sb.rail_label('rates')!r} {sb.rail_label('pricecheck')!r}")
    ctx.check(getattr(app, "_pc_dl", False) and app.pc_side.winfo_manager() == "pack", "the price card is shown")
    ctx.check(getattr(app.pc_pane, "_stacked", False), "Price Checks is stacked in the Drawer")
    app.drawer_cfg()["share"] = D.SHARE
    app.drawer_full()
    yield 1200
    ctx.check(int(float(str(bar.cget("height")))) == bar.H, "Full window: the normal header")
    ctx.check(not getattr(app.pc_pane, "_stacked", True), "Full window: side by side")
    ctx.check(tabs is None or not tabs.winfo_ismapped(), "Full window: the tabs are in the sidebar again")
    ctx.check(not app.pc_side.winfo_manager(), "Full window: the price strip, not the card")
    app.drawer_dock()
    yield 600
    yield from _put_away(ctx)


def a_T12(ctx):
    """T12 (owner test 1): dragging the inner edge ~300 px wider (past the default's 1200 px) keeps the width - saved as the share, and neither the
    debounce nor the 2 s re-dock puts the old width back."""
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    app.drawer_cfg()["share"] = 0.40
    yield from _shown_drawer(ctx)
    yield 1500
    x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
    root.geometry(f"{w + 300}x{h}+{x - 300}+{y}")             # (the user drags the inner edge)
    yield 900
    ctx.check(abs(app.drawer_cfg()["share"] - (w + 300) / 2560.0) < 0.01, f"share in memory at once: {app.drawer_cfg()['share']}")
    yield 3500                                                # (past the debounce and the 2 s re-dock)
    ctx.check(abs(root.winfo_width() - (w + 300)) <= 8, f"width kept: {root.winfo_width()} vs {w + 300}")
    ctx.check(abs(SETTINGS["drawer"]["share"] - (w + 300) / 2560.0) < 0.01, "share saved")
    app.drawer_put_away("test")
    yield 800
    app.app_show(focus=True, why="key")
    yield 1200
    ctx.check(abs(root.winfo_width() - (w + 300)) <= 8, f"shown again with the saved width: {root.winfo_width()}")
    app.drawer_cfg()["share"] = 0.40
    yield from _put_away(ctx)


def a_T16(ctx):
    """T16 (Round 18, owner: dragging wider snapped back, and maximize reverted to the small size): a width you drag
    - even past 70% of the game - is never put back by the 2 s re-dock (only its edge / place); the window manager
    maximizing it (button, double-click on the title, Aero snap: simulated with drawer.WM_STATE_HOOK) makes it the
    Full window and nothing re-docks it; restored, it is the Drawer again with the width you set; the shape isn't
    saved as Full."""
    from soe2 import drawer as D
    from soe2.config import SETTINGS
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    app.drawer_cfg()["share"] = 0.40
    yield from _shown_drawer(ctx)
    yield 1500
    x, y, w, h = root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height()
    want = int(2560 * 0.80)                                   # (past the old 70% cap)
    root.geometry(f"{want}x{h}+{x + w - want}+{y}")           # (the user drags the inner edge far)
    yield 900
    yield 4500                                                # (two 2 s re-docks)
    ctx.check(abs(root.winfo_width() - want) <= 8, f"a width past 70% kept: {root.winfo_width()} vs {want}")
    ctx.check(abs(root.winfo_x() + root.winfo_width() - 2560) <= 8, f"still on the game's edge: x {root.winfo_x()}")
    root.geometry(f"{want}x{h}+{x - 400}+{y}")                # (dragged off the edge: the place is put back)
    yield 4500
    ctx.check(abs(root.winfo_x() + root.winfo_width() - 2560) <= 8 and abs(root.winfo_width() - want) <= 8,
              f"moved back to the edge, the width kept: {root.winfo_x()} {root.winfo_width()}")
    # maximize (the WM says zoomed)
    D.WM_STATE_HOOK = lambda: "zoomed"
    try:
        root.geometry("2560x1400+0+0")
        yield 400
        root.event_generate("<Configure>")
        yield 600
        ctx.check(app.drawer_st.eff == "full" and app.drawer_st.max_full, "maximized: the Full window")
        ctx.check(not app.drawer_look_on(), "maximized: the Full window's look")
        ctx.check(app.drawer_cfg()["shape"] == "drawer", "maximized: the Drawer is still the saved shape")
        yield 4500                                            # (the re-dock ticks: nothing puts it back)
        ctx.check(root.winfo_width() >= 2500, f"maximized: stays maximized ({root.winfo_width()})")
    finally:
        D.WM_STATE_HOOK = None
    root.geometry(f"{want}x{h}+{x + w - want}+{y}")            # (restored: Windows gives the old rect back)
    yield 300
    root.event_generate("<Configure>")
    yield 1500
    ctx.check(app.drawer_st.eff == "drawer" and not app.drawer_st.max_full, "restored: the Drawer again")
    ctx.check(abs(root.winfo_width() - want) <= 8, f"restored: the width you set ({root.winfo_width()} vs {want})")
    app.drawer_cfg()["share"] = 0.40
    app.drawer_cfg().pop("share_set", None)
    SETTINGS["drawer"]["share"] = 0.40
    yield from _put_away(ctx)


def t_T17():
    """T17 (Round 18): the states - maximized from a shown Drawer = Full (not remembered), restored = the Drawer; a
    Full window you chose isn't touched by either; the strip's buttons end it; a width you drag past 70% is a share
    that stays (clamp_share up to SIDE_ROOM)."""
    from soe2 import drawer as D
    st = D.DrawerState("drawer")
    _eq(st.maximized(), ("max",), "maximized from the Drawer")
    _eq((st.eff, st.max_full), ("full", True), "the Full window")
    _eq(st.maximized(), None, "maximized again: nothing")
    _eq(st.unmaximized(), ("show", "drawer", True, None), "restored: the Drawer")
    _eq(st.eff, "drawer", "the Drawer")
    _eq(st.unmaximized(), None, "restored twice: nothing")
    full = D.DrawerState("full")
    _eq(full.maximized(), None, "a Full window maximized: stays a Full window")
    st.maximized()
    st.full()
    _eq((st.shape, st.max_full), ("full", False), "the strip's Full window ends it")
    _eq(st.unmaximized(), None, "...so restoring it keeps the Full window")
    st.away()
    st2 = D.DrawerState("drawer")
    st2.away()
    _eq(st2.maximized(), None, "put away: no maximize")
    _eq(round(D.clamp_share(0.80, 2560), 3), 0.80, "80% of a 1440p game stays")
    _eq(round(D.clamp_share(0.99, 2560), 4), round(1 - D.SIDE_ROOM / 2560, 4), "at most all but SIDE_ROOM")
    _eq(D.clamp_share(0.80), D.SHARE_HI, "no area known: the old cap")


def t_T14():
    """T14 (drawer-look, owner: resizing still snapped back to a different size): a width you drag stays - read and
    written in the same pixels at 100 / 125 / 150 / 175 % (Windows scales the app: its pixels = real / scale), on
    both sides, on 1080p / 1440p / 4K games; reading the docked rect again never counts as a new drag (< 8 px)."""
    from soe2 import drawer as D
    for scale in (1.0, 1.25, 1.5, 1.75):
        for pw, ph in ((1920, 1080), (2560, 1440), (3840, 2160)):
            game = D.logical((0, 0, pw, ph), scale)
            for drag in (D.MIN_W, 950, 1100, 1250, 1500):
                if drag > min(game[2] - D.SIDE_ROOM, game[2] * D.SHARE_HI):
                    continue
                share = D.share_from_drag(drag, game[2])
                for side in ("right", "left"):
                    r = D.drawer_rect(game, side=side, share=share, cap=False)
                    if abs(r[2] - drag) > 1:
                        raise AssertionError(f"{scale} {pw}: dragged {drag}, docked {r[2]}")
                    if (side == "right" and r[0] + r[2] != game[0] + game[2]) or (side == "left" and r[0] != game[0]):
                        raise AssertionError(f"{scale} {pw} {side}: not on the game's edge {r}")
                    again = D.drawer_rect(game, side=side, share=D.share_from_drag(r[2], game[2]), cap=False)
                    if abs(again[2] - r[2]) >= 8:
                        raise AssertionError(f"{scale} {pw}: re-reading it moves it {r[2]} -> {again[2]}")
                # the same drag read in real pixels gives the same share (no space mixed)
                if abs(D.share_from_drag(D.physical((drag,), scale)[0], pw) - share) > 0.002:
                    raise AssertionError(f"{scale} {pw}: share differs between real and scaled pixels")
            # the Drawer's own rect and the game's, read in two spaces, map onto each other
            r = D.drawer_rect(game, share=0.45, cap=False)
            m = D.map_rect(r, game, (0, 0, pw, ph))
            if any(abs(a - b) > 2 for a, b in zip(m, D.physical(r, scale))):
                raise AssertionError(f"{scale} {pw}: map_rect {m} vs {D.physical(r, scale)}")
    if not D.WIN:
        _eq(D.pin_ui_dpi(), None, "pin_ui_dpi: a no-op off Windows")


def a_T15(ctx):
    """T15 (drawer-look, owner: Scan stash's check window kept going behind the app): while the app is topmost (the
    Drawer) a pop-up window it opens is topmost too; a Full window that isn't kept on top leaves it as it is."""
    from soe2.config import SETTINGS
    import tkinter as tk
    app, root = ctx.app, ctx.root
    yield from _until(lambda: app._drawer_started, 12000)
    yield from _shown_drawer(ctx)
    ctx.check(app.drawer_topmost_wanted(), "the Drawer is on top")     # (Linux reads -topmost back from the WM)
    d = tk.Toplevel(root)
    d.title("Scan stash - check the numbers")
    tk.Label(d, text="test").pack()
    yield 600
    ctx.check(getattr(d, "_drawer_on_top", False), "a dialog opened over the Drawer is put on top too")
    t = tk.Toplevel(root)
    t.overrideredirect(True)                             # (a window over the game, not one of the app's pop-ups)
    yield 400
    ctx.check(not getattr(t, "_drawer_on_top", False), "a window over the game is left to its own rules")
    t.destroy()
    d.destroy()
    on0 = SETTINGS.get("on_top")
    SETTINGS["on_top"] = False
    app.drawer_full()
    yield 1000
    ctx.check(not app.drawer_topmost_wanted(), "Full window, not kept on top: not on top")
    d = tk.Toplevel(root)
    yield 600
    ctx.check(not getattr(d, "_drawer_on_top", False), "...and its dialog isn't either")
    d.destroy()
    SETTINGS["on_top"] = on0
    app.drawer_dock()
    yield 600
    yield from _put_away(ctx)


def t_T13():
    """T13 (owner test 6): the price check side flip - only when the mouse is inside the would-be Drawer (and inside
    the game's own rect: a mouse in another coordinate space or on another screen never flips)."""
    from soe2 import drawer as D
    game = (0, 0, 2560, 1440)
    rf = lambda side: D.drawer_rect(game, side=side)
    _eq(D.flip_for_cursor("right", (400, 600), rf, game), "right", "stash item (left side): stays right")
    _eq(D.flip_for_cursor("right", (2200, 600), rf, game), "left", "inventory item (right side): flips")
    _eq(D.flip_for_cursor("right", (1535, 600), rf, game), "right", "just left of the Drawer: stays")
    _eq(D.flip_for_cursor("right", (1536, 600), rf, game), "left", "on the Drawer's edge: flips")
    _eq(D.flip_for_cursor("right", (2200, 1400), rf, game), "right", "below the Drawer (the skill bar): stays")
    g2 = (2560, 0, 2560, 1440)                                  # the game on monitor 2
    rf2 = lambda side: D.drawer_rect(g2, side=side)
    _eq(D.flip_for_cursor("right", (3000, 600), rf2, g2), "right", "monitor 2, stash item: stays")
    _eq(D.flip_for_cursor("right", (4800, 600), rf2, g2), "left", "monitor 2, inventory item: flips")
    _eq(D.flip_for_cursor("right", (2200, 600), rf2, g2), "right", "a mouse outside the game's rect: stays")
    _eq(D.flip_for_cursor("right", None, rf, game), "right", "no mouse: stays")
    _eq(D.flip_for_cursor("left", (400, 600), rf, game), "right", "Drawer on the left, mouse in it: flips")
    _eq(D.flip_for_cursor("left", (2200, 600), rf, game), "left", "Drawer on the left, mouse right: stays")
    # D5: mixed DPI - the Drawer's rect read DPI-unaware (logical), the mouse and the game in real pixels. The game
    # on monitor 2 (100%) right of a 150% 4K main monitor: logical (2560, 0, 2560, 1440), real (3840, 0, 2560, 1440)
    gl, gr = (2560, 0, 2560, 1440), (3840, 0, 2560, 1440)
    rfm = lambda side: D.map_rect(D.drawer_rect(gl, side=side), gl, gr)
    _eq(rfm("right"), (5376, 0, 1024, 1270), "map_rect: the Drawer's rect in real pixels")
    _eq(D.flip_for_cursor("right", (3840 + 300, 600), rfm, gr), "right", "mixed DPI, stash item: stays right")
    _eq(D.flip_for_cursor("right", (3840 + 2200, 600), rfm, gr), "left", "mixed DPI, inventory item: flips")
    _eq(D.map_rect((1536, 0, 1024, 1270), (0, 0, 2560, 1440), (0, 0, 3840, 2160)), (2304, 0, 1536, 1905),
        "map_rect: 150%")
    # D5: a width you set isn't held to 1200 (4K at 100%: the default is 1200, dragged wider it stays wider)
    _eq(D.drawer_rect((0, 0, 3840, 2160), share=0.45), (2640, 0, 1200, 1905), "4K default share: 1200")
    _eq(D.drawer_rect((0, 0, 3840, 2160), share=0.45, cap=False), (2112, 0, 1728, 1905), "4K, your share: wider")


UNIT = {"T1": t_T1, "T2": t_T2, "T5": t_T5, "T7": t_T7, "T13": t_T13, "T14": t_T14, "T17": t_T17}
APP = {"H0": a_H0, "T3": a_T3, "T3f": a_T3f, "T4": a_T4, "T6": a_T6, "T8": a_T8, "T9": a_T9, "T9b": a_T9b, "T10": a_T10,
       "T11": a_T11, "T12": a_T12, "T15": a_T15, "T16": a_T16}
RESTART = {"T3f"}                 # run in a second child on the same HOME (a restart of the app)
OWN_HOME = {"T9b"}                # run in a child with its own HOME: an existing install on its first start of this build
ORDER = ["H0", "T1", "T2", "T3", "T3f", "T4", "T5", "T6", "T7", "T8", "T9", "T9b", "T10", "T11", "T12", "T13", "T14",
         "T15", "T16", "T17"]


def is_todo(exc):
    return isinstance(exc, NotImplementedError) and str(exc).startswith("TODO")


# ============================================================================ parent
def ensure_x():
    if subprocess.run(["xdpyinfo", "-display", DISPLAY], capture_output=True).returncode == 0:
        return None
    p = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", f"{SCREEN[0]}x{SCREEN[1]}x24", "-nolisten", "tcp"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        time.sleep(0.1)
        if subprocess.run(["xdpyinfo", "-display", DISPLAY], capture_output=True).returncode == 0:
            return p
    p.kill()
    sys.exit(f"Xvfb {DISPLAY} didn't start")


def make_home(shape="drawer"):
    """A throwaway HOME with the smoke test's settings (every feature on, nothing to ask), shape as given."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import smoke_pages
    return smoke_pages.make_home(DATA, shape)


def run_unit(ids):
    res = {}
    sys.path.insert(0, ROOT)
    for i in ids:
        if i not in UNIT:
            continue
        try:
            UNIT[i]()
            res[i] = ("PASS", "")
        except Exception as ex:
            res[i] = ("TODO", str(ex)) if is_todo(ex) else ("FAIL", "".join(traceback.format_exception_only(type(ex), ex)).strip())
    return res


def run_app(ids, out, timeout=300):
    ids = [i for i in ids if i in APP]
    if "T3f" in ids and "T3" not in ids:
        ids.insert(ids.index("T3f"), "T3")                 # (T3f is T3's restart)
    if not ids:
        return {}
    own = [i for i in ids if i in OWN_HOME]
    ids = [i for i in ids if i not in OWN_HOME]
    res = {}
    xv = ensure_x()
    for n_, i in enumerate(own):                           # a first start of this build: its own HOME, no first_run_done
        h = make_home("drawer")
        sp = os.path.join(h, ".stashofexile2", "settings.json")
        sj = json.load(open(sp, encoding="utf-8"))
        sj["drawer"].pop("first_run_done", None)
        sj["drawer"].pop("intro_done", None)
        json.dump(sj, open(sp, "w", encoding="utf-8"))
        rp = os.path.join(out, f"results_own{n_}.json".replace("n_", str(n_)))
        e = dict(os.environ, HOME=h, APPDATA=h, USERPROFILE=h, DISPLAY=DISPLAY, PYTHONDONTWRITEBYTECODE="1",
                 SOE2_TRADE_API=OFFLINE + "/api/trade2", SOE2_NINJA=OFFLINE)
        cmd = [sys.executable, os.path.abspath(__file__), "--child", out, "--ids", i, "--res", rp]
        try:
            subprocess.run(cmd, cwd=ROOT, env=e, timeout=timeout,
                           stdout=open(os.path.join(out, f"app_output_{i}.txt"), "w"), stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            pass
        try:
            res.update({k: tuple(v) for k, v in json.load(open(rp)).items()})
        except Exception:
            res[i] = ("FAIL", f"no results - see {out}/app_output_{i}.txt")
        shutil.rmtree(h, ignore_errors=True)
    if not ids:
        if xv is not None:
            xv.terminate()
        return res
    home = make_home("drawer")
    env = dict(os.environ, HOME=home, APPDATA=home, USERPROFILE=home, DISPLAY=DISPLAY, PYTHONDONTWRITEBYTECODE="1",
               SOE2_TRADE_API=OFFLINE + "/api/trade2", SOE2_NINJA=OFFLINE)
    batches = [[]]
    for i in ids:                                          # a RESTART test starts a new child (same HOME)
        if i in RESTART and batches[-1]:
            batches.append([])
        batches[-1].append(i)
    for n, batch in enumerate(batches):
        rp = os.path.join(out, f"results{n}.json")
        cmd = [sys.executable, os.path.abspath(__file__), "--child", out, "--ids", ",".join(batch), "--res", rp]
        try:
            subprocess.run(cmd, cwd=ROOT, env=env, timeout=timeout,
                           stdout=open(os.path.join(out, f"app_output{n}.txt"), "w"), stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            pass
        try:
            res.update({k: tuple(v) for k, v in json.load(open(rp)).items()})
        except Exception:
            res.update({i: ("FAIL", f"no results (child crashed or timed out) - see {out}/app_output{n}.txt")
                        for i in batch})
    shutil.rmtree(home, ignore_errors=True)
    if xv is not None:
        xv.terminate()
    t3, t3f = res.get("T3"), res.get("T3f")                # (T3f restarts T3's app: it can't pass if T3 didn't end)
    if t3 and t3[0] == "FAIL" and t3[1].startswith("no results") and t3f and t3f[0] == "FAIL":
        res["T3f"] = ("FAIL", "T3 didn't finish, so its restart can't be checked - " + t3f[1])
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tests", nargs="*", help="test ids (default: all)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    ap.add_argument("--ids", help=argparse.SUPPRESS)
    ap.add_argument("--res", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        return child(a.child, a.ids.split(","), a.res)
    if a.list:
        for i in ORDER:
            f = UNIT.get(i) or APP[i]
            print(f"{i:4} {'unit' if i in UNIT else 'app ':4} {(f.__doc__ or '').strip().splitlines()[0]}")
        return 0
    if not drawer_exists():
        print("test_drawer: SKIP - soe2/drawer.py doesn't exist yet (D1 adds it)")
        return 0
    ids = [i for i in ORDER if not a.tests or i in a.tests]
    out = tempfile.mkdtemp(prefix="soe2-drawer-test-")
    res = {**run_unit(ids), **run_app(ids, out)}
    bad = 0
    for i in ids:
        st, why = res.get(i, ("FAIL", "not run"))
        bad += st == "FAIL"
        print(f"{st:4}  {i:4} {why}"[:300])
    n = lambda s: sum(1 for v in res.values() if v[0] == s)
    print(f"\ntest_drawer: {n('PASS')} pass, {n('TODO')} todo, {n('FAIL')} fail")
    if not bad:
        shutil.rmtree(out, ignore_errors=True)
    else:
        print(f"details: {out}")
    return 1 if bad else 0


# ============================================================================ child: inside the app
class Ctx:
    def __init__(self, app):
        self.app, self.root, self.fails = app, app.root, []
        self._top = None
        self.spy_topmost()

    def check(self, ok, what):
        if not ok:
            self.fails.append(what)

    def topmost(self):
        """root's -topmost: the last value the app set, else Tk's own answer (Xvfb has no window manager, and X11's
        -topmost is _NET_WM_STATE_ABOVE - only a window manager confirms it, so Tk's answer can't be trusted here)."""
        if self._top and self._top[0] is not None:
            return int(self._top[0])
        try:
            return int(self.root.attributes("-topmost"))
        except Exception:
            return 0

    def spy_topmost(self):
        """Record what the app sets -topmost to (see topmost)."""
        self._top = [None]
        orig = self.root.attributes

        def attributes(*a, **k):
            if len(a) >= 2 and a[0] == "-topmost":
                self._top[0] = bool(a[1])
            return orig(*a, **k)
        self.root.attributes = attributes

    def drawer_shape_hooks(self):
        """The same hooks tools/smoke_pages.py uses: the game is the whole screen."""
        from soe2 import drawer
        drawer.GAME_RECT_HOOK = lambda: (0, 0, SCREEN[0], SCREEN[1])
        return drawer


def child(out, ids, res_path=None):
    import faulthandler                                    # D5: a child that hangs (a modal box inside a step...)
    faulthandler.dump_traceback_later(285, exit=True)      # says where, in its app_output, before the 300 s kill
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    sys.argv = ["stashofexile2.py"]
    res = {}
    import soe2.app as A
    orig_init = A.App.__init__

    def finish():
        json.dump(res, open(res_path or os.path.join(out, "results.json"), "w"))
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    def init(self, *a, **k):
        orig_init(self, *a, **k)
        ctx = Ctx(self)
        if drawer_exists() and os.path.exists(os.path.join(ROOT, "soe2", "drawer.py")):
            ctx.drawer_shape_hooks()
        queue = list(ids)
        cur = [None, None]

        def step():
            if cur[0] is None:
                if not queue:
                    finish()
                cur[0] = queue.pop(0)
                ctx.fails = []
                cur[1] = APP[cur[0]](ctx)
            try:
                wait = next(cur[1])
            except StopIteration:
                res[cur[0]] = ("FAIL", "; ".join(ctx.fails)) if ctx.fails else ("PASS", "")
                cur[0] = None
                wait = 1
            except Exception as ex:
                res[cur[0]] = ("TODO", str(ex)) if is_todo(ex) else ("FAIL", traceback.format_exc()[-600:])
                cur[0] = None
                wait = 1
            self.root.after(max(1, int(wait or 1)), step)
        self.root.after(4000, step)
    A.App.__init__ = init
    import runpy
    try:
        runpy.run_path(os.path.join(ROOT, "stashofexile2.py"), run_name="__main__")
    except SystemExit:
        pass
    finish()


if __name__ == "__main__":
    sys.exit(main())
