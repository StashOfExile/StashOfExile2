"""The Drawer's host (drawer build, D1 / D2): mixed into App. app_show() is THE one way to bring the app forward;
drawer_put_away() the one way to put it away. The states are drawer.DrawerState; the window work is drawer's adapter.

  Drawer      - the app shown as a side panel over the game (topmost while shown; the native frame is kept)
  Full window - the app as a normal window, where you left it (SETTINGS["main_window"], written in this shape only)
  Put away    - off screen: minimized (its taskbar button stays) or in the tray ("Put away to the system tray")
  Drawer key  - shows the app and puts it away (Settings › Keybinds; Ctrl+Shift+Space)

Threads: drawer_hotkey / drawer_esc_hotkey run on KeyWatch's hook thread - cached flags and ui_q only, no Tk, no
EnumWindows (check_threads). Everything else runs on the window's thread.
GGG ToS: only our own window is moved, shown or hidden; nothing is sent to the game (TOS.md)."""
import contextlib
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import drawer as D
from .config import save_json, SETTINGS
from .style import bind_own_configure



SHAPE_WORD = {"drawer": "Drawer", "full": "Full window"}      # 3.0.6: the Window toggle's two words (names.py)

class DrawerHost:
    """Mixed into App."""

    # ---------------------------------------------------------------- set-up
    def drawer_cfg(self):
        return D.cfg(SETTINGS)

    def drawer_boot(self):
        """Before the window is placed (app.py): the state, the adapter, and the shape the app starts in. Something
        to ask this start (Setup, What's new, a crash report, the league notice) or no Drawer key: a Full window for
        this session, shown until it's put away. -> "drawer" | "full"."""
        c = self.drawer_cfg()
        SETTINGS.setdefault("drawer_key", D.DEFAULT_KEY)
        st = self.drawer_st = D.DrawerState(c["shape"], c["side"], c["click_away"])
        self.drawer_ad = D.adapter(self.root, self._hwnd)
        self._drawer_geom = None                     # the shape the window's rect is in now ("drawer" / "full")
        self._drawer_rect_now, self._drawer_side_now = None, st.side
        self._drawer_showing_until = 0.0
        self._drawer_user_shown = False              # app_show() was called (startup leaves it shown then)
        self._drawer_started = False
        self._drawer_dock_miss = 0
        self._drawer_btn = False
        self._drawer_key = None
        self._drawer_t0 = time.time()
        try:                                          # drawer-look (owner: Scan stash's check window went behind the
            self.root.bind_class("Toplevel", "<Map>", self._drawer_dialog_mapped, add="+")    # Drawer): see below
        except tk.TclError:
            pass
        self._asking = 0                              # questions open right now (a messagebox, What's new, Setup)
        self._asks_wait = []                          # questions that came due while the app was put away
        self._asks_job = None                         # the next look at them (drawer_asks_soon)
        # first start of this build: What's new and Setup show for everyone, whatever they chose before; then the
        # Drawer takes over (after_asks)
        self._drawer_first = not c.get("first_run_done")
        self._drawer_wn_due = self._drawer_first and bool(SETTINGS.get("seen_version"))
        self._drawer_setup_due = self._drawer_first
        if st.shape == "drawer" and (not (SETTINGS.get("drawer_key") or "").strip() or self._drawer_first
                                     or self._drawer_asks_now()):
            st.session_full = True
        return st.eff

    def _drawer_asks_now(self):
        """Will the app ask something at this start? (Then it starts as a Full window, so the question is seen.)"""
        try:
            from . import __version__
            from . import features as FEAT
            if SETTINGS.get("seen_version") != __version__:        # What's new / the quick start
                return True
            from .whatsnew import lead_due                         # 3.0.0: "Why 3.0", once for everyone
            if lead_due(SETTINGS.get("whatsnew_lead"), __version__):
                return True
            if FEAT.asked() not in ("done", "never"):              # Setup
                return True
            from . import app as _app
            if _app.CRASHED[0]:                                    # the crash report toast
                return True
            import datetime as _dt
            start, until, key = _app.App.LEAGUE_NOTICE
            if not SETTINGS.get(key) and _dt.date.fromisoformat(start) <= _dt.date.today() <= _dt.date.fromisoformat(until):
                return True
        except Exception:
            buglog.caught()
        return False

    def drawer_place_start(self):
        """The window's first place in the Drawer shape (it's put away once the start-up screen closes)."""
        self.root.minsize(*D.DRAWER_MIN)
        rect = self.drawer_target()
        if rect:
            x, y, w, h = rect
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._drawer_rect_now = rect
        self._drawer_geom = "drawer"

    def drawer_init(self):
        """After the window is built (app.py, once the tray and the window's binds exist)."""
        self.drawer_key_cache()
        D.SHOWN_DRAWER[0] = self.drawer_st.as_drawer()
        if self._drawer_geom is None:
            self._drawer_geom = "full"
        bind_own_configure(self.root, self.drawer_configured)
        self.root.bind_all("<ButtonPress-1>", lambda e: setattr(self, "_drawer_btn", True), add="+")
        self.root.bind_all("<ButtonRelease-1>", lambda e: setattr(self, "_drawer_btn", False), add="+")
        self.root.after(300, self.drawer_ad.disable_transitions)
        self.root.after(D.TICK_MS, self.drawer_tick)
        self.root.after(9000, self.drawer_startup)               # (if the start-up screen never says it closed)

    def drawer_startup(self):
        """Once the start-up screen has closed: the Drawer shape starts put away, with one toast saying how to
        open it. A Full window (or a Full window for this session) stays where it is."""
        if self._drawer_started:
            return
        self._drawer_started = True
        st = self.drawer_st
        if st.session_full or self._drawer_first:       # something to ask: a Full window until it has all been
            self.after_asks(self._drawer_asks_done)     # answered, then the Drawer takes over
        if st.eff != "drawer":
            return
        if self._drawer_user_shown:                   # (already shown on purpose - a price check, a test)
            return self.drawer_redock(force=True)
        self.drawer_put_away("start")
        k = self.drawer_key_label()
        self.root.after(400, lambda: self.app_toast(f"Stash of Exile 2 is running: {k} shows it.", "Drawer"))

    # ---------------------------------------------------------------- questions: when they may be asked
    def asks_open(self):
        """Is the app asking something right now? (What's new, Setup, a question box, or one still due.)"""
        if self._asking > 0 or self._drawer_wn_due or self._drawer_setup_due:
            return True
        for name in ("_whatsnew", "feat_win", "rm_ask_win", "cm_ask_win", "cm_name_win", "er_ask_win", "bn_win"):
            w = getattr(self, name, None)
            try:
                if w is not None and w.winfo_exists():
                    return True
            except tk.TclError:
                pass
        return False

    @contextlib.contextmanager
    def asking(self):
        """Around a modal question: the Drawer isn't taken over / put away until it is answered."""
        self._asking += 1
        try:
            yield
        finally:
            self._asking -= 1

    def after_asks(self, fn, settle=6.0):
        """Run fn once nothing is asking (two quiet looks in a row, and at least `settle` s after the start): What's
        new, Setup, the league notice and the crash report show before the Drawer takes over."""
        quiet = [0]

        def poll():
            try:
                busy = self.asks_open() or time.time() - self._drawer_t0 < settle
                quiet[0] = 0 if busy else quiet[0] + 1
                if quiet[0] >= 2:
                    return fn()
            except Exception:
                buglog.caught()
            try:
                self.root.after(1500, poll)
            except tk.TclError:
                pass
        self.root.after(1500, poll)

    def _drawer_asks_done(self):
        """Everything that had to be asked at this start has been: the first run is over, and a Drawer that started
        as a Full window for it takes over now (put away - the key shows it)."""
        c = self.drawer_cfg()
        if not c.get("first_run_done"):
            c["first_run_done"] = True
            save_json("settings.json", SETTINGS)
        self._drawer_first = False
        st = self.drawer_st
        if st.session_full and st.shape == "drawer" and self.drawer_key_label():
            st.session_full = False
            self.drawer_put_away("start")
            k = self.drawer_key_label()
            self.root.after(400, lambda: self.app_toast(f"This is the Drawer. {k} or Esc puts it away; the same "
                                                        "key brings it back.", "Drawer"))

    def drawer_setup_pick(self, shape):
        """Setup's last screen: Done with Drawer -> the app is the Drawer at once (shown, with a toast); Full window
        -> it stays a Full window. Either way the shape is remembered."""
        st, k = self.drawer_st, self.drawer_key_label()
        c = self.drawer_cfg()
        c["first_run_done"] = True
        self._drawer_first = False
        if shape == "drawer" and k:
            act = st.dock()
            self._drawer_save_shape()
            if act:
                self._drawer_do(act)
            else:
                self.app_show(focus=True, why="key")
            self.drawer_strip_paint()
            self.root.after(500, lambda: self.app_toast(
                f"This is the Drawer. {k} or Esc puts it away; the same key brings it back.", "Drawer"))
        else:
            st.full()
            self._drawer_save_shape()
            self._drawer_compact()
            self.drawer_strip_paint()

    def drawer_defer(self, fn):
        """Timed questions wait while the app is put away (a question box over the game, or one under a minimized
        owner, is the wrong thing). -> True when fn was held back; it runs at the next show with the keyboard."""
        try:
            away = self.drawer_is_away() and self._drawer_started
        except Exception:
            away = False
        if away:
            if fn not in self._asks_wait:
                self._asks_wait.append(fn)
            return True
        return False

    def drawer_asks_soon(self, ms=1500):
        """Look at the held questions in `ms` (one look pending at a time)."""
        if not self._asks_wait or getattr(self, "_asks_job", None):
            return
        def run():
            self._asks_job = None
            self.drawer_flush_asks()
        try:
            self._asks_job = self.root.after(ms, run)
        except tk.TclError:
            self._asks_job = None

    def drawer_flush_asks(self):
        """The app is shown: ask what came due, one at a time - only while the app has the keyboard and nothing else
        is asking; otherwise it looks again a moment later. Put away: it stops, and the next show starts it again
        (so a held question is never lost, and never shows over the game)."""
        if not self._asks_wait or self.drawer_is_away():
            return
        if self.asks_open() or not self.drawer_app_front():
            return self.drawer_asks_soon(1500)
        fn = self._asks_wait.pop(0)
        try:
            fn()
        except Exception:
            buglog.caught()
        self.drawer_asks_soon(2500)

    # ---------------------------------------------------------------- the app's own windows stay above it
    def _drawer_ours(self, w):
        """One of the app's pop-up windows (a dialog, a picker, a tooltip, Go to anything) - not a page, not the
        Overlay's windows over the game (they have their own rules)."""
        if not isinstance(w, tk.Toplevel) or w is self.root:
            return False
        from .overlaywin import OverlayWindow
        from .shell import DeskWindow
        if isinstance(w, (OverlayWindow, DeskWindow)) or getattr(w, "_over_game", False):
            return False
        try:                                          # (a window without a title bar is over the game - marks, cards -
            return getattr(w, "_app_popup", False) or not w.overrideredirect()    # unless it's a tooltip / Go to)
        except tk.TclError:
            return False

    def _drawer_dialog_mapped(self, e):
        """A pop-up window of the app is shown: while the app's window is topmost (the Drawer always is; a Full
        window with Keep on top), the pop-up is too and goes over it, so it can't go behind it - Scan stash's check
        window, pickers, tooltips. (Its owner isn't changed here: on Windows that would make the window again.)"""
        w = e.widget
        try:
            if not self._drawer_ours(w) or not self.drawer_topmost_wanted():
                return
            w.attributes("-topmost", True)
            w._drawer_on_top = True
            w.lift()
        except (tk.TclError, ValueError):
            pass

    def drawer_topmost_wanted(self):
        """Is the app's window on top now? (apply_topmost's rule - Windows' own answer isn't read back: on Linux
        it depends on the window manager.) The Drawer always; a Full window with Keep on top."""
        return bool(SETTINGS.get("on_top", True)) or self.drawer_shown_as_drawer()

    def drawer_lift_dialogs(self):
        """After the app's window was put on top again (shown, re-docked): its open pop-ups go over it."""
        on = self.drawer_topmost_wanted()

        def walk(p):
            for c in p.winfo_children():
                if isinstance(c, tk.Toplevel) and self._drawer_ours(c):
                    yield c
                yield from walk(c)
        for w in list(walk(self.root)):
            try:
                if w.winfo_ismapped():
                    w.attributes("-topmost", on)
                    w._drawer_on_top = on
                    if on:
                        w.lift()
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- what the window is now
    def drawer_eff(self):
        st = getattr(self, "drawer_st", None)
        return st.eff if st is not None else "full"

    def drawer_is_away(self):
        try:
            return bool(getattr(self, "in_tray", False)) or self.root.state() in ("iconic", "withdrawn")
        except tk.TclError:
            return False

    def drawer_shown_as_drawer(self):
        st = getattr(self, "drawer_st", None)
        return st is not None and st.as_drawer()

    def drawer_full_geom(self):
        """May the window's place be written to SETTINGS["main_window"]? Only as a Full window in its own rect."""
        st = getattr(self, "drawer_st", None)
        return st is None or (st.eff == "full" and getattr(self, "_drawer_geom", "full") == "full")

    def drawer_title(self):
        from .overlay import POE_TITLE
        return (getattr(self, "overlay", None) and self.overlay.cfg.get("poe_title")) or POE_TITLE

    def drawer_game_rect(self):
        if D.GAME_RECT_HOOK is not None:
            return D.GAME_RECT_HOOK()
        try:
            from .alerts_page import game_rect
            return game_rect(self.drawer_title(), dpi_hwnd=self.drawer_ad.hwnd())
        except Exception:
            buglog.caught()
            return None

    def drawer_work_area(self):
        """The work area of the monitor under the mouse (no game) - (left, top, right, bottom)."""
        from .style import monitor_rect
        pt = D.cursor_pos(self.root, self.drawer_ad.hwnd()) or (0, 0)
        with D.root_dpi(self.drawer_ad.hwnd()):
            return monitor_rect(self.root, pt[0], pt[1])

    def drawer_target(self, side=None):
        st = self.drawer_st
        g = self.drawer_game_rect()
        c = self.drawer_cfg()
        return D.drawer_rect(g, None if g else self.drawer_work_area(), side or st.side, c["share"],
                             cap=not c.get("share_set"))

    def drawer_key_label(self):
        from .overlay import key_label
        k = (SETTINGS.get("drawer_key") or "").strip()
        return key_label(k) if k else ""

    def drawer_key_cache(self):
        from .overlay import parse_key
        self._drawer_key = parse_key(SETTINGS.get("drawer_key") or "") or None

    # ---------------------------------------------------------------- THE one way to bring the app forward
    def app_show(self, page=None, focus=True, why=""):
        """Bring the app forward in its shape, on `page` if given. focus=False (a price check): shown quietly, the
        game keeps the keyboard. why: "price" (the side flips away from the mouse), "key", "restore", ..."""
        st = self.drawer_st
        self._drawer_user_shown = True
        if why == "key" and st.eff == "drawer":            # 3.0.0: the Drawer shown by its key - used: no NEW chip
            from . import newchip
            newchip.used("Drawer")
        if self.drawer_is_away() and st.visible == D.SHOWN:
            st.gone()
        by = {"price": "price", "restore": "restore"}.get(why, "key")
        act = st.show(by, focus, page)
        self._drawer_do(act, why)

    def _drawer_do(self, act, why=""):
        if not act:
            return
        if act[0] == "away":
            return self._drawer_away_now(why)
        if act[0] == "front":
            self._drawer_showing_until = time.time() + 0.6
            return self.drawer_ad.front()
        _show, shape, focus, page = act
        st = self.drawer_st
        self._drawer_showing_until = time.time() + 0.6
        self._drawer_dock_miss = 0
        if getattr(self, "in_tray", False):
            self.in_tray = False
            try:
                self.tray.hide_icon()
            except Exception:
                buglog.caught()
        rect = None
        if shape == "drawer":
            side = st.side
            if why == "price":                      # the item just copied is under the mouse: the other side, once
                side = self.drawer_price_side(side)
            rect = self.drawer_target(side)
            self._drawer_rect_now, self._drawer_side_now = rect, side
            self.root.minsize(*D.DRAWER_MIN)
            self._drawer_geom = "drawer"
        D.SHOWN_DRAWER[0] = shape == "drawer"
        topmost = shape == "drawer" or bool(SETTINGS.get("on_top", True))
        fg = None
        if focus:
            self.drawer_ad.show_focused(rect)
        else:
            fg = self.drawer_ad.show_quiet(rect, topmost)
        if shape == "full" and self._drawer_geom not in ("full", "max"):    # (a maximized Drawer stays maximized)
            self._drawer_full_rect(focus)
        try:
            self.apply_topmost()
            self.drawer_lift_dialogs()               # (its pop-ups stay over it)
        except Exception:
            buglog.caught()
        if not focus and fg and D.foreground() != fg:
            D.set_foreground(fg)                    # (the keyboard stays with the game)
        self._drawer_compact()
        self.drawer_strip_paint()
        if page:
            try:
                self.shell.open(page)
            except Exception:
                self.log_error(f"opening {page}")
        if hasattr(self, "shell"):
            self.root.after(30, self.shell.show_all)
        self.root.after(300, lambda: self._drawer_check_shown(focus, fg))
        self.drawer_asks_soon(1500)                 # (held questions: once the app has the keyboard)

    def drawer_price_side(self, side):
        """A price check: the side the Drawer opens on (the other one, once, if the mouse - on the item just copied -
        is inside the would-be Drawer). Windows: the mouse and the game are read together in real pixels and the
        Drawer's rect is mapped onto them, so a monitor with other scaling can't flip it the wrong way (D5)."""
        game = self.drawer_game_rect()
        try:
            hw = self.drawer_ad.game_hwnd(self.drawer_title()) if game and D.GAME_RECT_HOOK is None \
                and D.CURSOR_HOOK is None else None
            phys = D.pointer_and_rect_physical(hw) if hw else None
            if phys and abs(phys[1][2] * game[3] - phys[1][3] * game[2]) <= 0.02 * phys[1][2] * game[3]:
                cur, gp = phys                       # (the same window: the same shape in both readings)
                return D.flip_for_cursor(side, cur, lambda s: D.map_rect(self.drawer_target(s), game, gp), gp)
        except Exception:
            buglog.caught()
        return D.flip_for_cursor(side, D.cursor_pos(self.root, self.drawer_ad.hwnd()), self.drawer_target, game)

    def _drawer_check_shown(self, focus, fg):
        """Risk 1 (PLAN): Tk must think the window is shown 300 ms later."""
        try:
            if self.drawer_st.visible != D.SHOWN:
                return
            if focus:
                if self.root.state() in ("iconic", "withdrawn"):
                    self.root.deiconify()
            else:
                self.drawer_ad.quiet_check(fg)
        except tk.TclError:
            pass

    def _drawer_full_rect(self, focus=True):
        """The Full window back in its own place, monitor and maximized state (main_window; set_placement + wp)."""
        import sys
        self.root.minsize(*D.FULL_MIN)
        g = SETTINGS.get("main_window") or {}
        done = False
        if sys.platform == "win32" and g.get("wp"):
            try:
                from .app import set_placement
                zoomed = bool(g.get("zoomed"))
                set_placement(self._hwnd(), g["wp"], zoomed, show=None if focus else (4 if not zoomed else None))
                done = True
            except Exception:
                buglog.caught()
        if not done:
            geo = self.saved_geometry() or "1280x800"
            if "+" not in geo:                       # (no place of its own yet: the middle of the monitor it's on)
                try:
                    from .style import monitor_rect
                    w, h = (int(v) for v in geo.split("x"))
                    cx = self.root.winfo_rootx() + self.root.winfo_width() // 2
                    cy = self.root.winfo_rooty() + self.root.winfo_height() // 2
                    with D.root_dpi(self.drawer_ad.hwnd()):
                        left, top, right, bottom = monitor_rect(self.root, cx, cy)
                    w, h = min(w, right - left), min(h, bottom - top)
                    geo = f"{w}x{h}+{left + (right - left - w) // 2}+{top + (bottom - top - h) // 2}"
                except Exception:
                    buglog.caught()
            self.drawer_ad.set_geometry(geo)
        self._drawer_geom = "full"
        self._drawer_rect_now = None
        self.root.after(600, lambda: setattr(self, "_win_restored", True))

    def _drawer_compact(self):
        sb = getattr(getattr(self, "shell", None), "sidebar", None)
        if sb is None:
            return
        try:
            if self.drawer_look_on():                          # the Drawer: ALWAYS the icon rail, whatever the width
                sb.set_compact(True)
            else:
                self.root.after_idle(lambda: sb.set_compact(self.root.winfo_width() < 1100))
            self.drawer_look()
        except Exception:
            buglog.caught()

    def drawer_look_on(self):
        """Is the app laid out as the Drawer (the narrow column, the rail)? The shape, not the width."""
        st = getattr(self, "drawer_st", None)
        return st is not None and st.eff == "drawer"

    def drawer_look(self):
        """The Drawer's look (mockups.html): the rail, a tighter page header. The Full window keeps its own."""
        on = self.drawer_look_on()
        sh = getattr(self, "shell", None)
        if sh is None:
            return
        try:                                               # the switches: ✓ On | Off in the Drawer (Round 18: the
            from .style import switch_look                 # theme's accent on the lit half; the segmented choices
            switch_look(self.root, "seg" if on else "onoff")   # and section heads keep the theme's own look)
        except Exception:
            buglog.caught()
        for w in list(getattr(sh, "windows", {}).values()):
            bar = getattr(w, "bar", None)
            try:
                if bar is not None and hasattr(bar, "height_now") and bar.winfo_exists():
                    bar.paint()
            except tk.TclError:
                pass
        sb = getattr(sh, "sidebar", None)
        try:
            if sb is not None and sb.winfo_exists():
                sb.redraw()                                # (the rail's own look)
        except tk.TclError:
            pass
        self.drawer_tabs()                                 # (Price Checks lays itself out by its width: pc_layout)
        for fn in getattr(self, "_drawer_look_hooks", []):
            try:
                fn(on)
            except Exception:
                buglog.caught()

    def drawer_tabs(self):
        """The Drawer's tab row (mockups.html .tabs): the rail lists pages only, so a page with tabs shows them under
        its header - the open one in the text color with a line under it (a mark, not color alone). The Full window
        keeps them in its sidebar."""
        sh = getattr(self, "shell", None)
        if sh is None:
            return
        on = self.drawer_look_on()
        for key, w in list(getattr(sh, "windows", {}).items()):
            row = getattr(w, "_dtabs", None)
            want = on and key in getattr(sh, "tabs", {}) and len(self._drawer_tab_list(key)) > 1
            try:
                if not want:
                    if row is not None and row.winfo_manager():
                        row.pack_forget()
                    continue
                if row is None:
                    row = w._dtabs = DrawerTabs(w.inner, self, key)
                if not row.winfo_manager():
                    row.pack(fill="x", after=w.bar)
                row.paint()
            except (tk.TclError, AttributeError):
                buglog.caught()

    def _drawer_tab_list(self, key):
        sh = self.shell
        home = sh.tab_home(key)
        return ([home] if home else []) + list(sh.tab_titles(key))

    # ---------------------------------------------------------------- put away
    def drawer_put_away(self, why=""):
        """THE one way to put the app away (the Drawer key, Esc, the strip's — Put away, a click on the game)."""
        st = self.drawer_st
        if st.eff == "full" and why in ("esc", "min", "minimise"):
            st.gone()
            return self.hk_min()                     # (a Full window: today's minimize, unchanged)
        st.away()
        return self._drawer_away_now(why)

    def _drawer_away_now(self, why=""):
        D.SHOWN_DRAWER[0] = False
        self.min_ok_until = time.time() + 3          # YOU asked for it: on_unmap lets it go through
        had_kb = why not in ("start",) and self.drawer_ad.has_keyboard()
        game = self.drawer_ad.game_hwnd(self.drawer_title()) if had_kb and D.GAME_OPEN[0] else None
        if game:
            self.drawer_ad.give_back(game)           # (while we still have the keyboard to give)
        try:
            if D.PUT_AWAY == "withdraw":
                if hasattr(self, "shell"):
                    self.shell.hide_all()
                self.drawer_ad.put_away("withdraw")
                if not SETTINGS.get("drawer_withdraw_told") and not (SETTINGS.get("tray") and self.tray.available):
                    SETTINGS["drawer_withdraw_told"] = True
                    k = self.drawer_key_label()
                    self.root.after(300, lambda: self.app_toast(
                        f"The app is put away - it has no taskbar button now. {k} shows it again.", "Drawer"))
            else:
                self.drawer_ad.put_away("minimize")      # (the tray takes it from here when that's on: on_unmap)
        except tk.TclError:
            pass
        if game:
            self.drawer_ad.give_back(game)
        self.drawer_strip_paint()

    # ---------------------------------------------------------------- the shape
    def drawer_full(self):
        """⤢ Full window: the shape is remembered."""
        st = self.drawer_st
        act = st.full()
        self._drawer_save_shape()
        if act:
            self._drawer_do(act)
        self.drawer_strip_paint()

    def drawer_dock(self):
        """⇤ Drawer: the shape is remembered (needs a Drawer key)."""
        if not self.drawer_key_label():
            self.app_toast("Set a Drawer key first (Settings › Keybinds).", "Drawer", kind="warning")
            self.drawer_strip_paint()
            return
        st = self.drawer_st
        act = st.dock()
        self._drawer_save_shape()
        if act:
            self._drawer_do(act)
        self.drawer_strip_paint()

    def drawer_flip_side(self):
        """⇄ Move to the other side - remembered."""
        c = self.drawer_cfg()
        c["side"] = D.other_side(self._drawer_side_now or c["side"])     # (from where it is: a price check may
                                                                          # have opened it on the other side)
        self.drawer_st.side = c["side"]
        save_json("settings.json", SETTINGS)
        self._drawer_side_now = c["side"]
        self.drawer_redock(force=True)
        self.drawer_strip_paint()

    def _drawer_save_shape(self):
        self.drawer_cfg()["shape"] = self.drawer_st.shape
        save_json("settings.json", SETTINGS)

    def drawer_redock(self, force=False):
        """The shown Drawer back on the game's edge (the game moved / resized, or the Drawer was dragged)."""
        st = self.drawer_st
        if not st.as_drawer():
            return
        if self.drawer_wm_state() == "zoomed":            # (maximized: the Full window now - _drawer_maximized)
            return
        if not force:
            self._drawer_note_width()                     # Round 18: the width you set is the latest - kept
        rect = self.drawer_target(self._drawer_side_now or st.side)
        if not rect:
            return
        cur = self.drawer_ad.outer_rect()
        if not force and cur and self.drawer_cfg().get("share_set") and abs(cur[2] - rect[2]) < 8:
            g = self.drawer_game_rect()                   # (the edge and place only - never the width you set)
            area = g or (lambda w: (w[0], w[1], w[2] - w[0], w[3] - w[1]))(self.drawer_work_area())
            right = (self._drawer_side_now or st.side) != "left"
            rect = (area[0] + area[2] - cur[2] if right else rect[0], rect[1], cur[2], rect[3])
        if not force and D.near(cur, rect, 4):
            self._drawer_dock_miss = 0
            return
        if not force:
            self._drawer_dock_miss += 1
            if self._drawer_dock_miss > 3:                 # (the window manager won't have it: stop trying)
                return
        self._drawer_showing_until = time.time() + 0.6
        self._drawer_rect_now = rect
        try:
            self.drawer_ad.place(rect)
        except tk.TclError:
            pass
        self._drawer_compact()

    def drawer_wm_state(self):
        """The window's state as the window manager has it ("normal", "zoomed", "iconic" ...)."""
        if D.WM_STATE_HOOK is not None:
            return D.WM_STATE_HOOK()
        try:
            return self.root.state()
        except tk.TclError:
            return "normal"

    def drawer_configured(self, e):
        """The window was resized / moved (<Configure>): 400 ms after the last one, a new width is remembered
        (share) and the Drawer goes back on the game's edge. Round 18: maximized (its button, a double-click on its
        title, Aero snap to the top) = the Full window, never put back; restored = the Drawer again."""
        if e.widget is not self.root:
            return
        st = getattr(self, "drawer_st", None)
        if st is None:
            return
        wm = self.drawer_wm_state()
        if wm == "zoomed" and st.as_drawer():
            return self._drawer_maximized()
        if wm == "normal" and st.max_full:
            return self._drawer_do(st.unmaximized(), "restore")
        if not self.drawer_shown_as_drawer() or time.time() < self._drawer_showing_until:
            return
        # 3.0.6 (dragging and resizing it was very laggy): while the mouse is down nothing is looked
        # up (the game's window, its size) - each pixel of a drag was a window search; the width is taken once, when
        # you let go (_drawer_resized). Nothing re-docks meanwhile: the watcher waits for the release and this job.
        if not self._drawer_mouse_down():
            self._drawer_note_width()
        elif (e.width, e.height) != getattr(self, "_drawer_last_wh", (e.width, e.height)):
            self._drawer_drag_profile(True)               # (a resize, not a move: Debug mode measures it)
        self._drawer_last_wh = (e.width, e.height)
        job = getattr(self, "_drawer_cfg_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._drawer_cfg_job = self.root.after(400, self._drawer_resized)

    def _drawer_drag_profile(self, on):
        """3.0.6 (owner: the Drawer still lags while its edge is dragged - not seen here, only on Windows): with Debug
        mode on, one drag is measured - the app's own work (Python, by function) against the time the drag took -
        and written to drawer_drag.txt in the app's data folder. Function names and times only, nothing personal."""
        if not SETTINGS.get("debug_mode") or getattr(self, "_drawer_prof_done", False):
            return                                        # (the first drag of a run only - measuring slows it)
        try:
            import cProfile
            if on:
                if getattr(self, "_drawer_prof", None) is None:
                    import collections
                    seen = collections.Counter()           # which parts still change size while you drag

                    def count(e):
                        try:
                            parts = str(e.widget).split(".")
                            seen[".".join(parts[:4])] += 1
                        except Exception:
                            pass
                    self._drawer_cfg_count = (seen, self.root.bind_all("<Configure>", count, add="+"))
                    self._drawer_prof = (cProfile.Profile(), time.perf_counter(), [0])
                    self._drawer_prof[0].enable()
                self._drawer_prof[2][0] += 1
                return
            got, self._drawer_prof = getattr(self, "_drawer_prof", None), None
            if got is None:
                return
            prof, t0, n = got
            prof.disable()
            import io
            import os
            import pstats
            from .config import DATA_DIR
            out = io.StringIO()
            st = pstats.Stats(prof, stream=out)
            secs = time.perf_counter() - t0
            tot = sum(v[2] for v in st.stats.values())      # (the time spent in the app's own Python)
            out.write(f"Drawer drag: {secs:.2f} s, {n[0]} resize events, app's own Python {tot:.2f} s "
                      f"({tot / secs * 100 if secs else 0:.0f}% - the rest is Tk drawing and Windows)\n"
                      f"page open: {getattr(getattr(self, 'shell', None), 'active', '?')}\n\n")
            seen, fid = getattr(self, "_drawer_cfg_count", (None, None))
            self._drawer_cfg_count = (None, None)
            if fid:
                try:
                    self.root.unbind_all("<Configure>")       # (only the counter's; the app's own are put back)
                    from .style import _layout_watch
                    self.root.bind_all("<Configure>", _layout_watch, add="+")
                except Exception:
                    buglog.caught()
            if seen:
                out.write(f"Parts that changed size while dragging: {sum(seen.values())}\n")
                for k, v in seen.most_common(25):
                    out.write(f"  {v:6d}  {k}\n")
            sh = getattr(self, "shell", None)
            if sh is not None:
                out.write("Pages: " + ", ".join(f"{k}={'shown' if getattr(w, '_shown', False) else 'hidden'}"
                                                 for k, w in getattr(sh, "windows", {}).items()) + "\n")
            n_map = [0]

            def walk(w):
                for c in w.winfo_children():
                    try:
                        if c.winfo_ismapped():
                            n_map[0] += 1
                            walk(c)
                    except tk.TclError:
                        pass
            walk(self.root)
            out.write(f"Parts on screen while dragging: {n_map[0]}\n\n")
            st.sort_stats("cumulative").print_stats(30)
            st.sort_stats("tottime").print_stats(20)
            with open(os.path.join(DATA_DIR, "drawer_drag.txt"), "w", encoding="utf-8") as f:
                f.write(out.getvalue())
            self._drawer_prof_done = True
        except Exception:
            self._drawer_prof = None
            buglog.caught()

    def _drawer_maximized(self):
        """The Drawer was maximized: the Full window, as it is (maximized) - nothing re-docks it or puts its size
        back. main_window isn't written from it (it isn't the Full window's own place)."""
        job, self._drawer_cfg_job = getattr(self, "_drawer_cfg_job", None), None
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        if not self.drawer_st.maximized():
            return
        D.SHOWN_DRAWER[0] = False
        self._drawer_geom = "max"
        self._drawer_rect_now = None
        try:
            self.root.minsize(*D.FULL_MIN)
            self.apply_topmost()
        except Exception:
            buglog.caught()
        self._drawer_compact()
        self.drawer_strip_paint()

    def _drawer_note_width(self):
        """The user's drag wins: a width that is 8 px or more away from the docked one becomes the share AT ONCE (in
        memory), so no re-dock - the 2 s timer or the debounce - can put the old width back. It's saved when the
        drag settles (_drawer_resized)."""
        try:
            cur, exp = self.drawer_ad.outer_rect(), self._drawer_rect_now
            if not (cur and exp) or abs(cur[2] - exp[2]) < 8:
                return
            g = self.drawer_game_rect()
            area = g[2] if g else (lambda w: w[2] - w[0])(self.drawer_work_area())
            if area > 0:
                c = self.drawer_cfg()
                c["share"], c["share_set"] = D.share_from_drag(cur[2], area), True
                self._drawer_share_dirty = True
                self._drawer_rect_now = (exp[0], exp[1], cur[2], exp[3])    # (the docked width is the dragged one)
        except Exception:
            buglog.caught()

    def _drawer_mouse_down(self):
        if D.WIN:
            try:
                import ctypes
                u = ctypes.windll.user32                  # (GetAsyncKeyState reads the PHYSICAL button: with the
                vk = 0x02 if u.GetSystemMetrics(23) else 0x01   # buttons swapped, the primary is VK_RBUTTON)
                return bool(u.GetAsyncKeyState(vk) & 0x8000)
            except Exception:
                return False
        return bool(self._drawer_btn)

    def _drawer_resized(self):
        self._drawer_cfg_job = None
        if not self.drawer_shown_as_drawer():
            return self._drawer_drag_profile(False)
        if self._drawer_mouse_down():                     # still dragging: wait for the release
            self._drawer_cfg_job = self.root.after(400, self._drawer_resized)
            return
        self._drawer_drag_profile(False)
        self._drawer_note_width()
        if getattr(self, "_drawer_share_dirty", False):
            self._drawer_share_dirty = False
            save_json("settings.json", SETTINGS)
            self._drawer_dock_miss = 0
            self._drawer_settings_paint()
        self.drawer_redock()

    # ---------------------------------------------------------------- the window's own events (app.py)
    def drawer_on_map(self):
        """<Map>: a restore we didn't start (its taskbar button) - shown in the remembered shape; a Drawer re-docks."""
        if time.time() < getattr(self, "_drawer_showing_until", 0):
            return
        st = getattr(self, "drawer_st", None)
        if st is None or st.visible != D.AWAY:
            return
        st.restored()
        D.SHOWN_DRAWER[0] = st.as_drawer()
        if st.eff == "drawer":
            self._drawer_dock_miss = 0
            self.drawer_redock(force=True)
        try:
            self.apply_topmost()
        except Exception:
            buglog.caught()
        self.drawer_strip_paint()
        self.drawer_asks_soon(1500)                 # (held questions: a taskbar restore counts as a show)

    def drawer_on_unmap(self):
        """<Unmap> as the window goes away (iconic / withdrawn). -> True in the Drawer shape: no auto-restore."""
        st = getattr(self, "drawer_st", None)
        if st is None:
            return False
        drawer = st.eff == "drawer"
        if st.visible == D.SHOWN:
            st.gone()
        D.SHOWN_DRAWER[0] = False
        return drawer

    # ---------------------------------------------------------------- the watcher (350 ms, the window's thread)
    def drawer_tick(self):
        try:
            self._drawer_n = n = getattr(self, "_drawer_n", 0) + 1
            if n % 3 == 1:
                D.GAME_OPEN[0] = D.game_open_now(self.drawer_title())
            st = self.drawer_st
            if st.as_drawer():
                self._drawer_click_away()
                if n % max(1, D.REDOCK_MS // D.TICK_MS) == 0 and not self._drawer_mouse_down() \
                        and not getattr(self, "_drawer_cfg_job", None) \
                        and time.time() >= self._drawer_showing_until and self.drawer_st.as_drawer():
                    self.drawer_redock()
        except Exception:
            buglog.caught()
        finally:
            try:
                self.root.after(D.TICK_MS, self.drawer_tick)
            except tk.TclError:
                pass

    def _drawer_click_away(self):
        """The app had the keyboard, then the game got it (a click on the game) -> put away ("Put the Drawer away
        when I click the game"). Never while a key box waits, a grab is held or it was just shown / put away."""
        st = self.drawer_st
        st.click_away = bool(self.drawer_cfg().get("click_away", True))
        if not st.click_away or not D.can_watch():
            return
        from .style import CAPTURING
        now = time.time()
        if CAPTURING[0] is not None or now < getattr(self, "min_ok_until", 0) or now < self._drawer_showing_until:
            return
        try:
            if self.root.grab_current() is not None:
                return
        except tk.TclError:
            return
        ours, game = D.fg_state(self.drawer_title())
        if st.fg(ours, game):
            self._drawer_away_now("click")

    # ---------------------------------------------------------------- keys
    def ev_drawer(self, what):
        """ui_q: ("drawer", "key" | "esc_game" | "app")."""
        st = self.drawer_st
        if what == "key":
            if self.drawer_is_away() and st.visible == D.SHOWN:
                st.gone()
            if st.visible == D.AWAY:                             # (app_show does the show itself)
                return self.app_show(focus=True, why="key")
            return self._drawer_do(st.key(app_front=self.drawer_app_front()), "key")
        if what == "esc_game":
            if st.as_drawer():
                st.away()
                return self._drawer_away_now("esc_game")
            return None
        if what == "app":
            return self.app_show(focus=True, why="app")
        return None

    def drawer_app_front(self):
        """Is one of the app's windows in front? (the window's thread)"""
        if D.FG_HOOK is not None:
            return bool(D.FG_HOOK()[0])
        if D.WIN:
            return self.drawer_ad.has_keyboard()
        try:
            return self.root.focus_displayof() is not None
        except Exception:
            return False

    def drawer_hotkey(self, vk, ctrl, alt, shift):
        """Hook thread: the Drawer key - while the game or the app is in front, or anywhere while the game isn't
        running (GAME_OPEN: cached by the watcher). Cached flags and ui_q only."""
        k = getattr(self, "_drawer_key", None)
        if not k or k != (vk, ctrl, alt, shift):
            return False
        ours, game = D.fg_state(self.drawer_title())
        if not (game or ours or self._app_in_front() or not D.GAME_OPEN[0]):
            return False
        self.ui_q.put(("drawer", "key"))
        return True

    def drawer_esc_hotkey(self, vk, ctrl, alt, shift):
        """Hook thread: your close key (Esc) while the Drawer is shown and the game is in front -> put away; that
        press is used up (the game's menu doesn't open). A Full window is never put away by it."""
        if not D.SHOWN_DRAWER[0]:
            return False
        from .overlay import parse_key
        k = parse_key(SETTINGS.get("pc_close_key", "Esc") or "")
        if not k or k != (vk, ctrl, alt, shift):
            return False
        if not D.fg_state(self.drawer_title())[1]:
            return False
        self.ui_q.put(("drawer", "esc_game"))
        return True

    def _drawer_key_text(self):
        """Settings › Keybinds changed a key (save_hotkeys): the Drawer key's cache, its words; no key -> Full."""
        self.drawer_key_cache()
        if not self.drawer_key_label() and self.drawer_st.shape == "drawer":
            self.drawer_full()
            self.app_toast("The Drawer needs a key, so the app is a Full window now. Set a Drawer key in "
                           "Settings › Keybinds to use the Drawer.", "Drawer", kind="warning")
        self.drawer_strip_paint()

    # ---------------------------------------------------------------- the strip (top of the window, both shapes)
    def drawer_strip_build(self, parent):
        """Shell.__init__: packed side=top before the sidebar (the pages and the dim layer aren't affected)."""
        self.drawer_strip = DrawerStrip(parent, self)
        self.drawer_strip.pack(side="top", fill="x")
        return self.drawer_strip

    def drawer_strip_paint(self):
        s = getattr(self, "drawer_strip", None)
        if s is not None:
            try:
                s.paint()
            except tk.TclError:
                pass
        self._drawer_settings_paint()

    # ---------------------------------------------------------------- Settings › General › Window
    def drawer_settings_rows(self, row, P2):
        """The Window section's Drawer rows (settings_page). Each setting in this one place."""
        from .style import C, Tooltip
        c = self.drawer_cfg()
        lab = dict(bg=P2, fg=C["text"])
        v = self._drawer_vars = {"shape": tk.StringVar(value=self.drawer_st.shape),
                                 "side": tk.StringVar(value=c["side"]),
                                 "click": tk.BooleanVar(value=bool(c.get("click_away", True)))}
        r1 = tk.Frame(row, bg=P2)
        r1.pack(fill="x")
        tk.Label(r1, text="Window", **lab).pack(side="left", padx=(0, 8))
        from . import newchip as _NEW                      # 3.0.0: the Drawer is NEW until opened or used
        _NEW.chip(r1, "Drawer").pack(side="left", padx=(0, 8))
        # 3.0.6 (a toggle like the bar / panel one): Drawer | Full window, the same
        # toggle as the overlay's Layout; one gray line says when each suits
        from .style import SegBar
        self._drawer_seg = SegBar(r1, list(SHAPE_WORD.values()), value=SHAPE_WORD.get(v["shape"].get(), "Full window"),
                                  command=self._drawer_seg_pick, size=10, pad=(16, 4))
        self._drawer_seg.pack(side="left")
        tk.Label(r1, text="Suggested: Drawer for one monitor, Full window for two or more", bg=P2, fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        tip = tk.Label(r1, text="ⓘ", bg=P2, fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow")
        tip.pack(side="left", padx=(8, 0), anchor="n")
        Tooltip(tip, "Drawer: the app over the game's side, from the top of the game to just above the skill bar. "
                     "The Drawer key (Settings › Keybinds) shows it and puts it away; so do Esc and a click on the "
                     "game. If Ctrl+Shift+Space switches your keyboard layout, set F3 instead. Full window: a normal "
                     "window, where you left it.")
        self._drawer_rb_tip = Tooltip(self._drawer_seg.btns["Drawer"][0], "")
        self._drawer_note = tk.Label(row, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w")
        self._drawer_note.pack(fill="x", pady=(0, 8))
        r2 = tk.Frame(row, bg=P2)
        r2.pack(fill="x")
        tk.Label(r2, text="Side", **lab).pack(side="left", padx=(0, 8))
        self._drawer_side_seg = SegBar(r2, ["Left", "Right"], value=v["side"].get().title(), size=10, pad=(16, 4),
                                       command=lambda o: (v["side"].set(o.lower()), self._drawer_side_pick()))
        self._drawer_side_seg.pack(side="left", padx=(0, 12))
        # (3.0.6: no width input box - drag the Drawer's inner edge)
        r3 = tk.Frame(row, bg=P2)
        r3.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(r3, text="Put the Drawer away when I click the game", variable=v["click"],
                        command=self._drawer_click_pick).pack(side="left")
        tk.Label(r3, text="once you've used the Drawer - a price check's quiet show stays", bg=P2, fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        from .style import flowify
        for r_ in (r1, r2, r3):                          # D3: each row wraps at Drawer width
            flowify(r_)
        self._drawer_settings_paint()

    def _drawer_settings_paint(self):
        v = getattr(self, "_drawer_vars", None)
        if not v:
            return
        try:
            v["shape"].set(self.drawer_st.shape)
            v["side"].set(self.drawer_cfg()["side"])
            self._drawer_seg.pick(SHAPE_WORD.get(self.drawer_st.shape, "Full window"), notify=False)
            self._drawer_side_seg.pick(str(self.drawer_cfg()["side"]).title(), notify=False)
            has_key = bool(self.drawer_key_label())
            self._drawer_rb_tip.text = "" if has_key else "Set a Drawer key first (Settings › Keybinds)"
            k = self.drawer_key_label()
            self._drawer_note.config(text=(f"{k} shows the app and puts it away (Settings › Keybinds)." if k else
                                           "No Drawer key: set one in Settings › Keybinds to use the Drawer."))
        except (tk.TclError, AttributeError):
            pass

    def _drawer_seg_pick(self, word):
        """The Window toggle: Drawer | Full window. The Drawer needs its key (Settings › Keybinds) - without one the
        toggle stays on Full window and the line under it says so."""
        want = next((k for k, w in SHAPE_WORD.items() if w == word), "full")
        if want == "drawer" and not self.drawer_key_label():
            self._drawer_seg.pick(SHAPE_WORD["full"], notify=False)
            return
        self._drawer_vars["shape"].set(want)
        self._drawer_shape_pick()

    def _drawer_shape_pick(self):
        want = self._drawer_vars["shape"].get()
        from . import newchip
        newchip.used("Drawer")                            # 3.0.0: its NEW chip goes (a Window choice made)
        if want == "drawer":
            self.drawer_dock()
        else:
            self.drawer_full()

    def _drawer_side_pick(self):
        if self._drawer_vars["side"].get() != self.drawer_cfg()["side"]:
            self.drawer_flip_side()

    def _drawer_click_pick(self):
        on = bool(self._drawer_vars["click"].get())
        self.drawer_cfg()["click_away"] = on
        self.drawer_st.click_away = on
        save_json("settings.json", SETTINGS)


class DrawerTabs(tk.Canvas):
    """A page's tabs in the Drawer (mockups.html .tabs): words in a row on the page, the open one in the text color
    with a line under it; a click opens that tab (Shell.open_tab, as the sidebar does)."""

    H = 40

    def __init__(self, parent, app, key):
        from . import themes as TH
        super().__init__(parent, height=self.H, highlightthickness=0, bd=0)
        self.app, self.key, self.hover, self.hits = app, key, None, []
        TH.self_painted(self)
        TH.subscribe(lambda t: self.paint(), owner=self)
        self.bind("<Configure>", lambda e: self.paint())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)

    def _at(self, x):
        return next((t for x0, x1, t in self.hits if x0 <= x < x1), None)

    def _motion(self, e):
        self._set_hover(self._at(e.x))

    def _set_hover(self, t):
        if t != self.hover:
            self.hover = t
            self.configure(cursor="hand2" if t else "")
            self.paint()

    def _click(self, e):
        t = self._at(e.x)
        if t:
            try:
                self.app.shell.open_tab(self.key, t)
            except Exception:
                buglog.caught()

    def paint(self):
        from . import themes as TH
        t = TH.ST.theme
        if t is None:
            return
        sh = self.app.shell
        self.delete("all")
        self.hits = []
        w = max(self.winfo_width(), 2)
        cur = sh.tab_current(self.key)
        with TH.raw():
            bg = t.c("surface")
            self.configure(bg=bg)
            self.create_line(24, self.H - 1, w - 24, self.H - 1, fill=t.c("border"))
            x = 24
            for title in self.app._drawer_tab_list(self.key):
                on = title == cur
                tid = self.create_text(x + 12, self.H // 2, text=title, anchor="w",
                                       font=("Segoe UI", 10, "bold" if on else "normal"),
                                       fill=t.c("text_strong") if on else t.c("text") if title == self.hover else
                                       t.c("text_muted"))
                bb = self.bbox(tid) or (x, 0, x + 60, self.H)
                x1 = bb[2] + 12
                if on:                                     # (the open tab: bold, and the theme's accent under it)
                    self.create_rectangle(x, self.H - 3, x1, self.H - 1, fill=t.c("accent"), outline="")
                self.hits.append((x, x1, title))
                x = x1 + 2


class IconButton(tk.Label):
    """The Drawer look's flat icon button (mockups.html .ib): a line icon in the muted color, a thin border and the text
    color under the mouse, grayed out while it can't be used. Always with a tooltip (the caller adds it)."""

    def __init__(self, parent, icon, command, bg_role="chassis", size=18, w=32, h=30):
        super().__init__(parent, width=w, height=h, bd=0, highlightthickness=1, cursor="hand2", padx=0, pady=0)
        self.icon, self.command, self.bg_role, self.size = icon, command, bg_role, size
        self._off, self._hover = False, False
        self.bind("<Enter>", lambda e: self._set_hover(True), add="+")
        self.bind("<Leave>", lambda e: self._set_hover(False), add="+")
        self.bind("<ButtonRelease-1>", self._click, add="+")
        self.paint()

    def state(self, spec=None):
        """ttk-like: state(["disabled"]) / state(["!disabled"]); state() -> ("disabled",) or ()."""
        if spec:
            for s in spec:
                if s == "disabled":
                    self._off = True
                elif s == "!disabled":
                    self._off = False
            self.paint()
        return ("disabled",) if self._off else ()

    def _set_hover(self, on):
        self._hover = on
        self.paint()

    def _click(self, e=None):
        if self._off or not self._hover:
            return
        try:
            self.command()
        except Exception:
            buglog.caught()

    def paint(self):
        from . import lineicons
        from . import themes as TH
        t = TH.ST.theme
        if t is None:
            return
        with TH.raw():
            bg = t.c(self.bg_role)
            col = t.c("text_disabled", TH.mix(t.c("text_muted"), bg, .5)) if self._off else \
                t.c("text") if self._hover else t.c("text_muted")
            img = lineicons.icon(self, self.icon, self.size, col)
            try:
                self.configure(image=img or "", bg=bg, highlightbackground=t.c("border") if self._hover and not
                               self._off else bg, highlightcolor=bg, cursor="" if self._off else "hand2")
            except tk.TclError:
                pass
            self._img = img


class DrawerStrip(tk.Frame):
    """The Drawer strip (mockups.html .dstrip): the app's mark and name, where it is in words ("Drawer · right"), the
    keys that put it away as key caps, then flat icon buttons - each with a tooltip. Not orange. Both shapes."""

    HEIGHT = 40
    ICONS = {"full": "expand", "dock": "dock", "side": "side", "away": "away"}

    def __init__(self, parent, app):
        from .style import Tooltip
        from . import themes as TH
        super().__init__(parent, height=self.HEIGHT)
        self.app = app
        self.pack_propagate(False)
        self.line = tk.Frame(self, height=1)
        self.line.pack(side="bottom", fill="x")
        self.mark = tk.Label(self, bd=0)
        self.mark.pack(side="left", padx=(12, 8))
        self.name = tk.Label(self, text="Stash of Exile 2", bd=0)
        self.name.pack(side="left")
        self.sep = tk.Frame(self, width=1, height=16)
        self.sep.pack(side="left", padx=12)
        self.say = tk.Label(self, text="", anchor="w", bd=0)
        self.say.pack(side="left", padx=(0, 12))
        self.keys = tk.Frame(self, bd=0)                      # the key caps: Ctrl Shift Space or Esc puts it away
        self.keys.pack(side="left", fill="x", expand=True)
        self.btns = {}
        for key, cmd, tip in (("away", lambda: app.drawer_put_away("strip"), "Put the app away - the Drawer key brings "
                                                                              "it back)"),
                              ("side", app.drawer_flip_side, "The Drawer on the other side of the game"),
                              ("full", app.drawer_full, "A normal window, where you left it - remembered"),
                              ("dock", app.drawer_dock, "The Drawer: the app over the game's side - remembered")):
            b = IconButton(self, self.ICONS[key], cmd)
            self.btns[key] = (b, Tooltip(b, tip))
        TH.subscribe(lambda t: self.paint(), owner=self)
        self.paint()

    def fit_height(self):
        """Tall enough for its buttons and key caps (their size follows the display scale)."""
        try:
            need = max([b.winfo_reqheight() for b, _t in self.btns.values()] +
                       [self.name.winfo_reqheight(), self.keys.winfo_reqheight()]) + 8
            h = max(self.HEIGHT, need)
            if int(float(str(self.cget("height")))) != h:
                self.configure(height=h)
        except tk.TclError:
            pass

    @staticmethod
    def key_parts(k):
        """"Ctrl+Shift+Space" -> ["Ctrl", "Shift", "Space"] (a key that is "+" itself stays one cap)."""
        parts, cur = [], ""
        for ch in str(k or ""):
            if ch == "+" and cur:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        if cur:
            parts.append(cur)
        return parts

    def _caps(self, t, bg, k, tail):
        """The key caps (mockups.html kbd): each key in a small box, then the words."""
        from . import themes as TH
        for w in self.keys.winfo_children():
            w.destroy()
        mut, txt = t.c("text_muted"), t.c("text")

        def cap(text):
            tk.Label(self.keys, text=text, bg=t.c("surface_raised"), fg=txt, font=("Segoe UI", 9), bd=0, padx=4,
                     pady=0, highlightthickness=1, highlightbackground=t.c("border"),
                     highlightcolor=t.c("border")).pack(side="left", padx=(0, 4))

        def word(text):
            tk.Label(self.keys, text=text, bg=bg, fg=mut, font=("Segoe UI", 9), bd=0).pack(side="left", padx=(0, 4))
        with TH.raw():
            for p in self.key_parts(k):
                cap(p)
            if tail == "away":
                if k:
                    word("or")
                cap("Esc")
                word("puts it away")
            elif k:
                word("puts it away")

    def paint(self):
        from . import lineicons
        from . import themes as TH
        app = self.app
        st = app.drawer_st
        c = app.drawer_cfg()
        k = app.drawer_key_label()
        side = getattr(app, "_drawer_side_now", None) or c["side"]
        t = TH.ST.theme
        if t is None:
            return
        with TH.raw():
            bg = t.c("chassis")
            self.configure(bg=bg)
            self.line.configure(bg=t.c("border"))
            self.sep.configure(bg=t.c("border"))
            self.keys.configure(bg=bg)
            self._mark = lineicons.icon(self, "mark", 16, t.c("text"))
            self.mark.configure(image=self._mark or "", bg=bg)
            self.name.configure(bg=bg, fg=t.c("text"), font=(TH.head_font(t), 12))
            self.say.configure(bg=bg, fg=t.c("text_muted"), font=("Segoe UI", 9))
        if st.eff == "drawer":
            text = f"Drawer \u00b7 {side}"
            show = ("full", "side", "away")
            self._caps(t, bg, k, "away")
        else:
            text = "Full window"
            show = ("dock", "away")
            self._caps(t, bg, k, "full")
        self.say.config(text=text)
        tips = {"full": "Full window: a normal window, where you left it - remembered",
                "dock": "Drawer: the app over the game's side - remembered" if k else
                        "Set a Drawer key first (Settings \u203a Keybinds)",
                "away": "Put away" + (f" ({k} or Esc)" if k else " (Esc)") + ": the app is off screen",
                "side": "Move to the " + ("right" if side == "left" else "left") + " side of the game"}
        for key, (b, tip) in self.btns.items():
            b.pack_forget()
            tip.text = tips[key]
            b.icon = "side_r" if key == "side" and side == "left" else self.ICONS[key]
            b.paint()
        for key in reversed(show):
            b, tip = self.btns[key]
            b.pack(side="right", padx=(0, 4 if key != show[-1] else 8), pady=4)
        b, tip = self.btns["dock"]
        b.state(["!disabled"] if k else ["disabled"])
        self.after_idle(self.fit_height)
