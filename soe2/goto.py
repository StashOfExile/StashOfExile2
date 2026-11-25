"""Go to anything (UI overhaul, Ctrl+K): one box that finds any page, any tab of a page, any part of a page and any
setting - and says where it lives, so you learn the way there. Enter opens it.

Built from what is already in the app: the pages (names.PAGES and each page's blurb), their tabs (the sidebar's),
every page part made with chrome.section (title and note) and Settings' own search index. Nothing is kept on disk.
GGG ToS: looks only - nothing here touches the game."""
import time
import tkinter as tk

from .inplace import set_cfg
from . import buglog
from . import themes as TH

MAX_ROWS = 9
KIND_ORDER = {"Page": 0, "Feature": 1, "Tab": 2, "Part": 3, "Setting": 4}
OV = ("tracker", "Helpers")          # nav phase 2: Overlay › Helpers (was the Overlay Settings page)
# where each named feature (names.FEATURES) lives: (page key, its tab or None) - a "settings" key means a Settings tab
FEATURE_AT = {
    "Alert card": OV, "Temple Helper": OV, "Music Controls": OV, "Vaal Lens": OV,
    "Map profit": OV, "Alerts show": OV, "Top Up Reminders": OV, "Break reminders": OV,
    "Campaign Helper": OV, "Desecration Helper": OV, "Exchange Helper": ("rates", "Exchange Helper"), "Mechanic Helper": OV,
    "Favours prices": OV, "Filter in the Ritual window": OV,
    "Session timer": ("tracker", "Sessions"),
    "Trade Whisper Watcher": OV, "Quick settings": OV, "Reset position": ("tracker", "Options"),
    "Layout": ("tracker", "Appearance"), "Style": ("tracker", "Appearance"), "Theme": ("settings", "Appearance"),
    "Regex keys": ("regex", None), "Data pack": ("crafthelper", None),
    "Scan stash": ("wealth", None), "Clear All": ("checks", None), "Manually Add": ("checks", None),
    "Keybinds": ("settings", "Keybinds"), "Read Key": ("settings", "Keybinds"), "Features": ("settings", "General"), "Setup": ("settings", "General"),
    "Data folder": ("settings", "Advanced"), "Search Options": ("settings", "Price checking"),
    "Error reports": ("settings", None), "Community data sharing": ("settings", None),
    "Drawer": ("settings", "General"), "Full window": ("settings", "General"), "Put away": ("settings", "General"),
    "Drawer key": ("settings", "Keybinds"), "Price check overlay": ("settings", "Price checking"),
}


def score(q, title, words):
    """Higher is better; 0 = no match. Every word you type has to be there."""
    q = q.lower().split()
    t, w = title.lower(), words.lower()
    if not q:
        return 1
    if not all(p in w or p in t for p in q):
        return 0
    s = 1
    for p in q:
        if t.startswith(p):
            s += 6
        elif any(x.startswith(p) for x in t.split()):
            s += 4
        elif p in t:
            s += 2
    return s


def tab_of(frames, w):
    """The tab a widget sits on, for a page that says which frame is which tab (Shell.tab_frames[key]: {tab: frame})
    - or None."""
    mine = {str(f): t for t, f in (frames or {}).items()}
    while w is not None and mine:
        t = mine.get(str(w))
        if t:
            return t
        w = getattr(w, "master", None)
    return None


def owner_key(w):
    """The page (its module key) a widget sits on."""
    while w is not None:
        k = getattr(w, "key", None)
        if isinstance(k, str) and hasattr(w, "shell"):
            return k
        w = getattr(w, "master", None)
    return None


class GoTo:
    """The Ctrl+K box. GoTo(app).show()"""

    def __init__(self, app):
        self.app, self.win, self.rows, self.sel = app, None, [], 0

    # ---- what can be found
    def entries(self):
        """[(kind, title, where, words, open)]"""
        sh = self.app.shell
        out = []
        from . import sidebar as SB

        def where_of(key):
            m = sh.modules.get(key)
            p = getattr(m, "parent", None)
            if p and p in sh.modules:
                return f"{where_of(p)} › {sh.modules[p].title}".lstrip(" ›")
            return SB.group_of(key)            # nav phase 1: no group for Dashboard / Overlay (was "Tools")

        for key, m in sh.modules.items():
            if not sh.visible(m) or getattr(m, "hidden", False):
                continue
            from .names import OLD                 # (an old name still finds the page: Rate Mods -> Mod Lab)
            olds = " ".join(o for o, new in OLD.items() if new == m.title)
            out.append(("Page", m.title, where_of(key), f"{m.title} {olds} {getattr(m, 'blurb', '')}",
                        lambda k=key: sh.open(k)))
            for tab in sh.tab_titles(key):
                out.append(("Tab", tab, f"{where_of(key)} › {m.title}".lstrip(" ›"), f"{tab} {m.title}",
                            lambda k=key, t=tab: sh.open_tab(k, t)))
        from .names import FEATURES
        for name in FEATURES:
            key, tab = FEATURE_AT.get(name, (None, None))
            if key == "settings":
                out.append(("Feature", name, f"Settings › {tab}" if tab else "Settings", name,
                            lambda t=tab: self.app.open_settings_tab(t) if t else sh.open("settings")))
            elif key in sh.modules and sh.visible(sh.modules[key]):
                m = sh.modules[key]
                place = f"{where_of(key)} › {m.title}".lstrip(" ›") + (f" › {tab}" if tab else "")
                out.append(("Feature", name, place, f"{name} {m.title}",
                            lambda k=key, t=tab: sh.open_tab(k, t) if t and t in sh.tab_titles(k) else sh.open(k)))
        from . import chrome
        seen = set()
        for title, note, w in list(chrome.INDEX):
            try:
                if not w.winfo_exists():
                    continue
            except tk.TclError:
                continue
            key = owner_key(w)
            if not key or key == "settings" or key not in sh.modules or not sh.visible(sh.modules[key]):
                continue
            m = sh.modules[key]
            if (key, title) in seen:
                continue
            seen.add((key, title))
            tab = tab_of(getattr(sh, "tab_frames", {}).get(key), w)     # nav phase 2: a part on a page's tab opens that tab
            out.append(("Part", title, f"{where_of(key)} › {m.title}".lstrip(" ›") + (f" › {tab}" if tab else ""),
                        f"{title} {note} {m.title}",
                        lambda k=key, t=tab: sh.open_tab(k, t) if t else sh.open(k)))
        try:
            for page, frame, title, words in self.app.settings_index():
                out.append(("Setting", title, f"Settings › {page}", words,
                            lambda p=page, f=frame: self.app.settings_open(p, f)))
        except Exception:
            buglog.caught()
        return out

    # ---- the box
    def show(self):
        if self.win is not None:
            try:
                self.win.lift()
                self.entry.focus_set()
                return
            except tk.TclError:
                self.win = None
        try:
            self._all = self.entries()
        except Exception:
            buglog.caught()
            self._all = []
        t = TH.ST.theme
        with TH.raw():
            surf, line, txt, mut = t.c("surface_raised"), t.c("border_light"), t.c("text_strong"), t.c("text_muted")
        root = self.app.root
        self.scrim = None              # (round 4: the dim layer covered the box on Windows - gone; see _lost)
        self.win = w = tk.Toplevel(root, bg=line, padx=1, pady=1)
        w._app_popup = True                          # (drawer-look: over the Drawer while it's topmost)
        w.overrideredirect(True)
        try:
            w.transient(root)
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        box = tk.Frame(w, bg=surf)
        box.pack(fill="both", expand=True)
        top = tk.Frame(box, bg=surf, padx=16, pady=12)
        top.pack(fill="x")
        tk.Label(top, text="⌕", bg=surf, fg=t.c("accent_2") if t else mut, font=("Segoe UI Symbol", 16)).pack(side="left")
        self.q = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.q, bg=surf, fg=txt, insertbackground=txt, relief="flat",
                              font=("Segoe UI", 12), width=48, highlightthickness=0, bd=0)
        self.entry.pack(side="left", fill="x", expand=True, padx=(12, 12))
        tk.Label(top, text="Esc", bg=surf, fg=mut, font=("Segoe UI", 9), padx=4,
                 highlightthickness=1, highlightbackground=line).pack(side="right")
        tk.Frame(box, bg=line, height=1).pack(fill="x")
        self.list = tk.Frame(box, bg=surf, padx=8, pady=8)
        self.list.pack(fill="both", expand=True)
        tk.Frame(box, bg=line, height=1).pack(fill="x")
        tk.Label(box, text="↑ ↓ Move     Enter Open     Esc Close", bg=surf, fg=mut, font=("Segoe UI", 9),
                 anchor="w", padx=16, pady=8).pack(fill="x")
        self.q.trace_add("write", lambda *_: self.refresh())
        for seq, fn in (("<Escape>", self.close), ("<Return>", self.go), ("<KP_Enter>", self.go),
                        ("<Down>", lambda: self.move(1)), ("<Up>", lambda: self.move(-1))):
            self.entry.bind(seq, lambda e, f=fn: (f(), "break")[1])
        w.bind("<Escape>", lambda e: self.close())          # (Esc works wherever the focus is in the box)
        w.bind("<FocusOut>", lambda e: w.after(150, self._lost))
        if not getattr(self, "_click_hooked", False):          # a click anywhere else in the app closes it
            self.app.root.bind_all("<ButtonPress>", self._outside, add="+")
            self._click_hooked = True
        self._shown = time.time()          # (round 7b: set BEFORE the first poll - the last opening's time made the
        self._poll_focus()                 # second opening close itself at once)
        self.refresh()
        self._place()
        self._front()
        for ms in (30, 150, 400):                     # over the page windows (they lift themselves as they settle)
            w.after(ms, self._front)

    def _front(self):
        try:
            if self.win is not None:
                sc = getattr(self, "scrim", None)
                if sc is not None:                          # (the box above the dim layer, always)
                    self.win.tk.call("raise", self.win._w, sc._w)
                self.win.attributes("-topmost", True)
                self.win.lift()
                self.win.focus_force()
                self.entry.focus_set()
        except tk.TclError:
            pass

    def _place(self):
        root, w = self.app.root, self.win
        w.update_idletasks()
        try:
            x = root.winfo_rootx() + (root.winfo_width() - w.winfo_reqwidth()) // 2
            y = root.winfo_rooty() + 90
            w.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def _outside(self, e):
        if self.win is None:
            return
        try:
            if str(e.widget).startswith(str(self.win)):
                return
        except (tk.TclError, AttributeError):
            pass
        self.close()

    def _poll_focus(self):
        """A click outside the app (the game, the desktop) closes it too: the app has no focus any more."""
        import sys
        if self.win is None or sys.platform != "win32":     # (no window manager focus to read elsewhere)
            return
        try:
            if time.time() - getattr(self, "_shown", time.time()) > 0.8 and self.app.root.focus_displayof() is None:
                self.close()
                return
            if self._clicked_outside():                     # (round 7: pages are inside the app's window now - a
                self.close()                                 # click on them doesn't take the focus, and a widget's
                return                                       # own click binding can stop bind_all - so ask Windows)
            self.win.after(100, self._poll_focus)
        except (tk.TclError, KeyError):
            self.close()

    def _clicked_outside(self):
        """Windows: a mouse button is down and the pointer isn't over the box -> True."""
        if time.time() - getattr(self, "_shown", time.time()) < 0.3:
            return False
        try:
            import ctypes
            u = ctypes.windll.user32
            down = any(u.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))
            if not down:
                return False
            px, py = self.win.winfo_pointerxy()
            x, y = self.win.winfo_rootx(), self.win.winfo_rooty()
            return not (x <= px < x + self.win.winfo_width() and y <= py < y + self.win.winfo_height())
        except Exception:
            return False

    def _lost(self):
        if time.time() - getattr(self, "_shown", 0) < 0.6:       # (the focus settling as it opens)
            return
        try:                                                # focus anywhere but the box (another window of the
            f = self.win.focus_displayof() if self.win is not None else None      # app, the game): it closes
            if self.win is not None and (f is None or not str(f).startswith(str(self.win))):
                self.close()
        except (tk.TclError, KeyError):
            self.close()

    def close(self):
        sc, self.scrim = getattr(self, "scrim", None), None
        if sc is not None:
            try:
                sc.destroy()
            except tk.TclError:
                pass
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None

    def move(self, d):
        if self.rows:
            self.sel = (self.sel + d) % len(self.rows)
            self.paint()

    def go(self, i=None):
        if not self.rows:
            return
        fn = self.rows[self.sel if i is None else i][4]
        self.close()
        try:
            fn()
        except Exception:
            buglog.caught()

    def refresh(self):
        q = self.q.get().strip()
        hits = []
        for e in self._all:
            s = score(q, e[1], e[3])
            if s:
                hits.append((-s, KIND_ORDER.get(e[0], 9), e[1].lower(), e))
        if not q:
            hits = [h for h in hits if h[3][0] == "Page"]
        hits.sort(key=lambda h: h[:3])
        self.rows = [h[3] for h in hits[:MAX_ROWS]]
        self.sel = 0
        self.paint()

    def paint(self):
        t = TH.ST.theme
        with TH.raw():
            surf, hov, txt, mut, acc = (t.c("surface_raised"), t.c("hover", t.c("surface_high")), t.c("text_strong"),
                                        t.c("text_muted"), t.c("accent"))
        # UI rule 22: typing or moving the pick re-words and re-colors the rows that are there; rows are added or
        # removed only at the end, when there are more or fewer hits
        ws = self.__dict__.setdefault("_row_ws", [])
        if ws and not ws[0][0].winfo_exists():
            ws.clear()
        none = getattr(self, "_none_lbl", None)
        if none is not None and not none.winfo_exists():
            none = self._none_lbl = None
        if not self.rows:
            if none is None:
                none = self._none_lbl = tk.Label(self.list, text="Nothing found. Try another word.", bg=surf, fg=mut,
                                                 font=("Segoe UI", 10), anchor="w", padx=12, pady=12)
            if not none.winfo_manager():
                none.pack(fill="x", before=ws[0][0] if ws else None)
        elif none is not None and none.winfo_manager():
            none.pack_forget()
        while len(ws) > len(self.rows):
            ws.pop()[0].destroy()
        for i, (kind, title, where, _w, _fn) in enumerate(self.rows):
            on = i == self.sel
            bg = hov if on else surf
            if i >= len(ws):
                row = tk.Frame(self.list, bg=bg, padx=12, pady=8, cursor="hand2")
                row.pack(fill="x")
                bar = tk.Frame(row, bg=acc if on else bg, width=2)
                bar.pack(side="left", fill="y", padx=(0, 12))
                k = tk.Label(row, bg=bg, fg=mut, font=("Segoe UI", 9), width=8, anchor="w")
                k.pack(side="left")
                t_ = tk.Label(row, bg=bg, fg=txt, font=("Segoe UI", 10, "bold"), anchor="w")
                t_.pack(side="left")
                w_ = tk.Label(row, bg=bg, fg=mut, font=("Segoe UI", 9), anchor="e")
                w_.pack(side="right")
                for wdg in (row, *row.winfo_children()):
                    wdg.bind("<Button-1>", lambda e, n=i: self.go(n))
                ws.append((row, bar, k, t_, w_))
            row, bar, k, t_, w_ = ws[i]
            set_cfg(row, bg=bg)
            set_cfg(bar, bg=acc if on else bg)
            set_cfg(k, text=kind, bg=bg, fg=mut)
            set_cfg(t_, text=title, bg=bg, fg=txt)
            set_cfg(w_, text=where, bg=bg, fg=mut)
        try:
            self._place()
        except tk.TclError:
            pass
