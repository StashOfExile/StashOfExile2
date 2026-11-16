"""Alerts while you play (2.10.0): the helpers' alerts, switched on and watched from one panel (Overlay › Helpers).

Breach: the game writes its Hiveblood warnings to its own log, Client.txt (seen in real PoE 2 logs, Oct 2026):
    : <brequelwarning>{Stored Hiveblood is almost at the maximum!}
    : <brequelwarning>{Cannot store any more Hiveblood! Go to the Genesis Tree to consume it.}
Both are easy to miss in the middle of a Breach. This follows Client.txt (only new lines, about once a second - the
same way the Session tracker does) and shows a banner over the game: an "almost full" one, and a stronger "full"
one. Nothing is read from the game itself and no keys are sent. 2.131.0: every alert is the alert card (alertcard.py) - before, a banner was big flashing text over the game,
no box; clicks go through it. It goes after a few seconds, or as soon as you open the Genesis Tree.

Remnant (2.37.0): the Expedition Remnant Price Checker (remnant.py / remnant_page.py).

GGG policy (Nov 2026): Ritual, Temple, Expedition, Favours prices and every other helper that reads the screen
reads it once per press of the Read Key (look_page.py, screenread.py) - none of them watches by itself any more.
(The Delirium helper is gone: its End Delirium check was a screen read of its own.)"""
import os
import sys
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from .config import P, save_json, SETTINGS
from .gamelog import area_kind as gl_area_kind, find_log, LogReader
from .style import C, Tooltip

REPEAT_SECS = 45          # the game repeats a warning (twice in 2 s, then every ~15 s when full): one banner per level
RETRY_TICKS = 15          # Client.txt not found: look again every this many seconds
LEVELS = {
    # 2.131.0 (feedback: "a more elegant solution than just giant bold flashing letters"): the alert card's title,
    # its detail line, its mark and its color (alertcard.py)
    "almost": ("Hiveblood almost full", "Spend it at the Genesis Tree", "!", "#d86bd0"),
    "full": ("Hiveblood is full", "Go to the Genesis Tree to consume it", "!", "#ff5a5a"),
    # 2.11.0: you left a map after the game warned and haven't opened the Genesis Tree since
    "ritual": ("Rituals not done", "Go back through your portal", "!", "#ff6a5a"),      # 2.14.0
    "leave": ("Spend your Hiveblood", "It was almost full when you left the map: visit the Genesis Tree", "!",
              "#ffb347"),
}
DOT = {"on": "#5ee08a", "off": "#6b7690", "warn": "#ffb347"}
TRANSPARENT = "#010203"
# 2.12.1: then it goes by itself (like END DELIRIUM). 2.129.1 (feedback: the tribute one stayed too long): 4 s
BANNER_SECS = {"almost": 8, "full": 10, "leave": 8, "ritual": 8}


def _hwnd(win):
    import ctypes
    u = ctypes.windll.user32
    u.GetParent.restype = ctypes.c_void_p
    u.GetParent.argtypes = [ctypes.c_void_p]
    return u.GetParent(win.winfo_id()) or win.winfo_id()


def click_through(win):
    """Clicks go through to the game and it never takes the keyboard (Windows) - as the Delirium alert does."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        h = _hwnd(win)
        u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)
    except Exception:
        buglog.caught()


def force_topmost(win):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_uint]
        u.SetWindowPos(_hwnd(win), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x1 | 0x2 | 0x10)
    except Exception:
        buglog.caught()


def game_rect(title="Path of Exile 2", dpi_hwnd=None):
    """-> (left, top, width, height) of the game window, or None (then the main screen is used). dpi_hwnd (the
    Drawer): read in that window's DPI awareness (drawer.root_dpi); other callers don't pass it."""
    if dpi_hwnd:
        from .drawer import root_dpi
        with root_dpi(dpi_hwnd):
            return game_rect(title)
    if sys.platform.startswith("linux"):
        from .linsys import game_rect as _gr
        return _gr(title)
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            if u.IsWindowVisible(hwnd):
                n = u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    if buf.value.strip().lower() == title.lower():
                        r = wintypes.RECT()
                        u.GetWindowRect(hwnd, ctypes.byref(r))
                        found.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                        return False
            return True
        u.EnumWindows(cb, 0)
        return found[0] if found and found[0][2] > 200 and found[0][3] > 200 else None
    except Exception:
        return None


def breach_level(text):
    """The game's warning text -> "full" or "almost"."""
    t = (text or "").lower()
    return "full" if "cannot store" in t or "any more" in t else "almost"


# 2.119.0 (UX pass): what each helper does, in one line - under its name on Helpers, and (2.124.0) the tip on its
# Quick settings chip
HELPERS_LABEL = "HELPERS"           # 2.132.6 (feedback: "Instead of saying Ritual: or Temple: it should say Helpers:")
LOOK = "{look}"                     # GGG policy (Nov 2026): the Read Key's name goes here (look_page.LookPage)
HELPER_BLURBS = {"breach": "An alert card when your Hiveblood is almost full, and when it's full.",
                 "ritual": f"Press {LOOK} in a map: reads the Ritual counter once. Reminds you if you leave with rituals "
                           f"left.",
                 "remnant": f"Press {LOOK} with an Expedition remnant's book open: prices each reward once, beside its "
                            f"line.",
                 "focus": "Your League Plan over the game: the goal you're on, and pokes when it matters.",
                 "campaign": "Where you are in the campaign, what's next and rewards you missed - from the game's log.",
                 "whispers": "A card over the game when someone whispers to buy your item: what, for how much, where.",
                 "desecrate": f"Press {LOOK} at The Well of Souls: reads the tier of each Desecration option once.",
                 "topup": f"Back from a map, open your inventory and press {LOOK}: says what's running low.",
                 "breaks": "An alert card after a long stretch of play, in a hideout or town.",
                 "mapprofit": f"What each map earned: back from a map, open your inventory and press {LOOK}.",
                 "temple": f"Press {LOOK} with the Temple Console open in Vaal Ruins: reads your crystals once.",
                 "music": "Previous, play / pause and next for any music player, in a small window.",   # 2.134.0
                 "sekhemas": f"Press {LOOK} on the trial map: shows what to avoid and what to take."}


from .look_page import UNSET_STATUS  # noqa: E402  (the helpers' status line while no Read Key is set)
LOOK_HELPERS = tuple(k for k, v in HELPER_BLURBS.items() if LOOK in v)   # the helpers that need the Read Key


def helper_blurb(key, look="your Read Key"):
    """A helper's one line, with the Read Key's name in it."""
    return HELPER_BLURBS[key].replace(LOOK, look)


class AlertsPage:
    """Mixed into App."""

    # ================================================================ settings
    def breach_cfg(self):
        c = SETTINGS.setdefault("breach_alert", {})
        c.setdefault("on", True)     # 2.118.0: on by default (a new install; yours is kept)
        c.setdefault("sound", True)
        c.setdefault("leave_reminder", True)       # 2.11.0
        c.setdefault("pending", None)              # 2.11.0: "almost" / "full" since the last warning, until the tree
        return c

    def ritual_cfg(self):
        """2.14.0: the Ritual helper (ritual_alert.py reads the counter on a Read Key press)."""
        c = SETTINGS.setdefault("ritual_alert", {})
        c.setdefault("on", True)     # 2.118.0: on by default (a new install; yours is kept)
        c.setdefault("sound", True)
        c.setdefault("leave_reminder", True)
        c.setdefault("readout", True)               # 2.118.0: the Ritual line above the overlay's bar (On screen)
        return c

    def ritual_readout(self):
        """2.118.0 (feedback: show the Ritual count and your tribute on screen, with a switch): the text of the Ritual
        line over the game - "2 of 4 rituals done · 1,240 tribute" - while a map's Ritual counter has been seen, or
        "" (no line). The count used to ride on the bar's Ritual switch, which is gone.
        2.132.2 (feedback: "overlay text overlap ... we're cramming too much into the bar"): the line holds the map's
        mechanics - Ritual's part (owner decision: the Temple Helper's crystals are on Vaal Lens only)."""
        return self._ritual_part()

    def ritual_line_label(self):
        """The line's tag: HELPERS (2.132.6 - was RITUAL / TEMPLE / IN MAP)."""
        return HELPERS_LABEL

    def _ritual_part(self):
        c = self.ritual_cfg()
        if not (c.get("on") and c.get("readout", True)):
            return ""
        from .ritual_alert import STATE as RITUAL
        count = getattr(self, "rt_map", None) if getattr(self, "br_area", None) in ("map", None) else None
        count = self.ritual_estimate(count)
        if count and count[0] < 1:
            # 2.132.2 (feedback: "if a player doesn't interact with the first ritual, it should not enable ... it
            # should only appear when you start the ritual mechanics, same way the alerts only tell you to go back
            # ... if you do (1/#)"): no line until the first ritual is done
            return ""
        if count:
            d, t = count
            txt = f"{d} of {t} rituals done" + (" ✔" if d >= t else "")
        elif getattr(self, "br_area", None) == "map" and self.ritual_log_counts()[0]:
            n = self.ritual_log_counts()[0]                    # (the game's log: a ritual started - no count read yet)
            txt = f"{n} ritual{'s' if n != 1 else ''} started · press {self.look_key_text()} to read the counter"
        else:
            return ""
        tribute = getattr(RITUAL, "tribute", None)                 # 2.131.5: from the game's counter
        if tribute is not None:
            txt += f"  ·  {int(tribute):,} tribute"
        return txt

    def ritual_readout_sync(self):
        """The line comes and goes with the count; while it shows, its text follows."""
        try:
            txt = self.ritual_readout()
            shown = "ritual" in (getattr(self, "goal_rows", None) or []) and getattr(self, "gb_cv", None) is not None
            if bool(txt) != shown:
                if getattr(self, "mg_win", None) is not None:
                    self.goalbar_build()
            elif txt:
                lab = (getattr(self, "tk_ov_lbls", None) or {}).get("ritual")
                if lab is not None and lab.cget("text") != txt:
                    lab.config(text=txt)
        except Exception:
            buglog.caught()

    def ritual_readout_changed(self, on):
        self.ritual_cfg()["readout"] = bool(on)
        save_json("settings.json", SETTINGS)
        self.ritual_readout_sync()

    def log_wanted(self):
        """Client.txt is followed while Breach or Ritual needs it (Ritual: to know when you leave a map)."""
        from . import whispers as _W
        return bool(self.breach_cfg().get("on") or self.ritual_cfg().get("on") or self.ws_cfg().get("on")
                    or self.remnant_cfg().get("on") or _W.cfg()["on"]
                    or (hasattr(self, "fl_counting") and self.fl_counting())      # 2.45.0: the Strat Tracker's runs
                    or bool(SETTINGS.get("topup", {}).get("on"))                  # 2.131.0: Top Up (hideout / town)
                    or bool(SETTINGS.get("map_profit", {}).get("on"))             # 2.132.0: Map profit (maps)
                    or bool(SETTINGS.get("temple", {}).get("on"))                 # 2.132.1: the Temple Helper (areas)
                    or bool(SETTINGS.get("sekhemas", {}).get("on")))              # Trial of the Sekhemas (the trial)

    def alerts_init(self):
        """At start-up (start_utilities): the Breach watcher runs whether or not the tracker window was opened."""
        if getattr(self, "_alerts_ready", False):
            return
        self._alerts_ready = True
        self.br_reader, self.br_last, self.br_win, self.br_level = None, {}, None, None
        self.br_ticks, self._br_ticking, self.br_note = 0, False, ""
        self.br_area = None                        # 2.11.0: "map" / "hideout" / "town" / "other" - where you are
        self.rt_map = None                         # 2.14.0: the last Ritual count seen in this map (done, total)
        self.rt_log = {"starts": 0, "disrupted": 0, "last": 0.0}   # GGG policy: the game's log - rituals started
        self.rt_base = (0, 0)                      # ... and disrupted this map; (starts, disrupted) at the last read
        if self.log_wanted():
            self.root.after(1500, self.breach_start)
        # (GGG policy, Nov 2026: Ritual, Expedition, Top Up, Temple ... read on a Read Key press - nothing starts here)
        self.root.after(3000, self.topup_take_supplies)  # 2.131.2: League Plan's Map supplies move here (once)

    # ================================================================ the panel (Overlay › Helpers)
    # nav phase 2: every helper in ONE table - Break reminders, Top Up Reminders and Map profit were rows below it.
    # (key, row label) per group; a BETA helper (features.BETA_HELPERS) is said in its gray line, not a chip
    # (owner: Map profit is Play; Music is in a last group, Misc. Quick settings and Setup use these groups too.)
    HELPER_GROUPS = (("In maps", ("breach", "ritual", "remnant", "temple", "sekhemas")),
                     ("Play", ("desecrate", "campaign", "focus", "topup", "breaks", "mapprofit")),
                     ("Trading", ("whispers",)),
                     ("Misc", ("music",)))
    HELPER_NAMES = {"breach": "Breach", "ritual": "Ritual", "remnant": "Expedition",
                    "focus": "League Plan", "campaign": "Campaign", "whispers": "Trade whispers",
                    "desecrate": "Desecration", "temple": "Temple", "music": "Music",
                    "topup": "Top Up Reminders", "breaks": "Break reminders", "mapprofit": "Map profit",
                    "sekhemas": "Trial of the Sekhemas"}

    def build_alerts_panel(self, parent):
        """2.112.0 (rework): one row per helper, the same columns for all - on / off, the name with what it does and
        what it's doing now, its own options (chips), Remind, and Test / Open. Grouped: In maps, Play, Trading, Misc. A
        search box first, then the groups as chips; one Sound switch for every helper's alert sits above the table."""
        self.alerts_init()
        P2 = C["panel2"]
        box = tk.Frame(parent, bg=P2)
        CB = "Card.TCheckbutton"
        self.al_rows = {}
        sm = ("Segoe UI", 9)
        # ---- nav phase 2 (list page: search first): the search box, then the groups
        find = tk.Frame(box, bg=P2)
        find.pack(fill="x", pady=(0, 8))
        self.al_q = tk.StringVar()
        sbox = tk.Frame(find, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        sbox.pack(side="left")
        tk.Label(sbox, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        ent = tk.Entry(sbox, textvariable=self.al_q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                       relief="flat", font=("Segoe UI", 10), highlightthickness=0, bd=0, width=28)
        ent.pack(side="left", padx=8, ipady=4)
        ph = tk.Label(sbox, text="Search helpers", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 10))
        ph.bind("<Button-1>", lambda e: ent.focus_set())

        def placeholder(_e=None):
            try:
                if self.al_q.get() or ent.focus_get() is ent:
                    ph.place_forget()
                else:
                    ph.place(in_=ent, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            ent.bind(ev, placeholder, add="+")
        ent.bind("<Escape>", lambda e: self.al_q.set(""))
        box.after(200, placeholder)
        self.al_search = ent
        from .style import SegBar, flowify
        self.al_group = SegBar(find, ["All"] + [g for g, _k in self.HELPER_GROUPS], command=lambda v: self.al_filter(),
                               size=9, pad=(12, 4))
        self.al_group.pack(side="left", padx=(12, 0))
        # (owner: one control that sets every helper's switch)
        aoff = ttk.Button(find, text="Turn all off", style="Quiet.TButton", command=lambda: self.helpers_all(False))
        aoff.pack(side="right")
        Tooltip(aoff, "Switches every helper below off.")
        aon = ttk.Button(find, text="Turn all on", style="Quiet.TButton", command=lambda: self.helpers_all(True))
        aon.pack(side="right", padx=(0, 8))
        Tooltip(aon, "Switches every helper below on.")
        flowify(find)                                          # D3: search stays first; the rest wraps at Drawer width
        self.al_q.trace_add("write", lambda *_: (placeholder(), self.al_filter()))
        top = tk.Frame(box, bg=P2)
        top.pack(fill="x")
        # (2.119.0: "They only watch and show..." is the section's own intro - it was said twice)
        self.al_sound_all = tk.BooleanVar(value=bool(SETTINGS.get("helpers_sound", True)))
        snd = ttk.Checkbutton(top, text="Sound", variable=self.al_sound_all, style=CB, command=self.alerts_sound_all)
        snd.pack(side="right")
        Tooltip(snd, "Every helper's alert sound, on or off.")
        # 2.131.0: where the alert card shows and how big - one place for every helper's alert
        from . import alertcard as _AC
        acf = _AC.cfg()
        tk.Label(top, text="Alerts show:", bg=P2, fg=C["text"], font=sm).pack(side="left")
        wv = tk.StringVar(value=_AC.WHERE[acf["where"]])
        wcb = ttk.Combobox(top, textvariable=wv, values=list(_AC.WHERE.values()), state="readonly", width=14)
        wcb.pack(side="left", padx=(8, 0))
        wcb.bind("<<ComboboxSelected>>", lambda _e: self.alert_card_set(
            "where", next(k for k, v in _AC.WHERE.items() if v == wv.get())))
        sv = tk.StringVar(value=_AC.SIZES[acf["size"]][0])
        scb = ttk.Combobox(top, textvariable=sv, values=[v[0] for v in _AC.SIZES.values()], state="readonly", width=8)
        scb.pack(side="left", padx=(8, 0))
        scb.bind("<<ComboboxSelected>>", lambda _e: self.alert_card_set(
            "size", next(k for k, v in _AC.SIZES.items() if v[0] == sv.get())))
        tb = ttk.Button(top, text="Test", command=self.alert_card_test, width=6)
        tb.pack(side="left", padx=(8, 0))
        flowify(top)                                           # D3: wraps at Drawer width
        Tooltip(wcb, "Where every helper's alert card shows over the game.")
        Tooltip(scb, "How big the alert card is.")
        Tooltip(tb, "Shows a sample alert card over the game.")
        self.al_card_where, self.al_card_size = wcb, scb
        # 2.119.0 (UX pass): Client.txt not found - one banner here (it was the same red line on every helper)
        ban = tk.Frame(box, bg=C["warn_bg"], padx=8, pady=8, highlightthickness=1, highlightbackground=C["red"])
        tk.Label(ban, text="⚠ The game's log (Client.txt) wasn't found. Breach, Ritual, Campaign, Trade whispers and "
                           "more need it.", bg=C["warn_bg"], fg=C["text"], font=sm, anchor="w", justify="left",
                 wraplength=520).pack(side="left", fill="x", expand=True)
        find_it = ttk.Button(ban, text="Find it…", command=self.tracker_pick_log)
        find_it.pack(side="right", padx=(8, 0))
        self.al_log_banner, self.al_log_after = ban, top
        tbl = tk.Frame(box, bg=P2)
        tbl.pack(fill="x", pady=(8, 0))
        self.al_table = tbl
        tbl.grid_columnconfigure(1, minsize=300)
        tbl.grid_columnconfigure(2, weight=1)
        heads_ = {}
        for c, t in ((0, "On / off"), (1, "Helper"), (2, "Options"), (3, "Remind")):
            heads_[c] = tk.Label(tbl, text=t, bg=P2, fg=C["muted"], font=sm)
            heads_[c].grid(row=0, column=c, sticky="w" if c < 3 else "", padx=(0, 12), pady=(0, 4))
        r_ = [1]
        self.al_find, self.al_heads, opt_cells = [], {}, []

        def rule():
            f = tk.Frame(tbl, bg=C["line"], height=1)
            f.grid(row=r_[0], column=0, columnspan=5, sticky="ew")
            r_[0] += 1
            return f

        def chip(parent, text, var, cmd, tip=None):
            """An option of a helper: a small button, filled when on (as Money Makers' filters)."""
            b = tk.Label(parent, text=text, font=sm, padx=8, pady=2, cursor="hand2", highlightthickness=1)

            def paint(dim=None):
                """Filled when on; while its helper is off, an outline only (it still switches)."""
                if dim is not None:
                    b.dim = dim
                on, dim = bool(var.get()), getattr(b, "dim", False)
                b.config(text=("\u2713 " if on else "\u25cb ") + text)       # D3: a mark with the word, never color alone
                if on and not dim:                      # (Round 18: the theme's accent in the Drawer too)
                    b.config(bg=C["accent"], fg=C["bg"], highlightbackground=C["accent"])
                else:
                    b.config(bg=P2, fg=C["muted"] if dim else (C["accent"] if on else C["text"]),
                             highlightbackground=C["accent"] if on else C["line"])

            def flip(_e=None):
                var.set(not var.get())
                paint()
                cmd()
            b.bind("<Button-1>", flip)
            b.paint = paint
            b.var = var
            paint()
            if tip:                                 # (a tip naming the Read Key follows the setting: alerts_refresh)
                b.tip_tpl = tip
                Tooltip(b, tip.replace(LOOK, self.look_key_text()))
            return b

        def info(parent, tip):
            i = tk.Label(parent, text="ⓘ", bg=P2, fg=C["muted"], font=sm, cursor="question_arrow")
            Tooltip(i, tip)
            return i

        self.al_chips = {}
        self.al_blurbs = {}                                    # {helper: (its gray line, "Beta · " or "")}
        what = {k: helper_blurb(k, self.look_key_text()) for k in self.HELPER_NAMES}   # 2.132.5: one line each (its
        #                                                                                     tooltip too)
        tests = {"breach": lambda: self.breach_alert(test=True),
                 "ritual": self.alerts_test_ritual, "remnant": self.alerts_test_remnant,
                 "focus": lambda: self.ov_intro_setup("focus"), "campaign": lambda: self.camp_route_show(),
                 "whispers": lambda: self.ww_show_test(), "desecrate": self.alerts_test_desecrate,
                 "temple": self.temple_pad_test, "music": lambda: self.music_set(True),
                 "breaks": lambda: self.break_check(force=True), "topup": lambda: self.topup_remind(force=True),
                 "mapprofit": self.mp_list_open, "sekhemas": self.sek_test}
        test_tips = {"breaks": "Shows the next reminder now.", "topup": "Shows the reminder now, with what it last saw.",
                     "temple": "Shows the Vaal Lens card now, with your last crystal count.",
                     "mapprofit": "The Map Profit page: every map counted, with how each number was worked out.",
                     "sekhemas": "Shows the legend over the game now: Afflictions left, Rooms and Boons right."}
        names = self.HELPER_NAMES
        from . import features as _FEAT
        from . import newchip as _NEW
        beta = set(_FEAT.BETA_HELPERS)
        # 2.119.0 (UX pass): what each one does, in one gray line under its name (it was only a tooltip)
        blurb = {k: ("Beta · " if k in beta else "") + what[k] for k in names}
        self.al_leave = tk.BooleanVar(value=bool(self.breach_cfg().get("leave_reminder", True)))
        self.al_rleave = tk.BooleanVar(value=bool(self.ritual_cfg().get("leave_reminder", True)))
        self.al_rshow = tk.BooleanVar(value=bool(self.ritual_cfg().get("readout", True)))
        self.al_rfav = tk.BooleanVar(value=bool(self.ritual_cfg().setdefault("favours", True)))
        self.al_rid = tk.BooleanVar(value=bool(self.ritual_cfg().setdefault("identify", True)))
        self.al_rru = tk.BooleanVar(value=bool(self.remnant_cfg().get("rumours", True)))
        self.al_rtips = tk.BooleanVar(value=bool(self.remnant_cfg().get("tips", True)))
        from .temple import cfg as _TMc
        self.al_tpad = tk.BooleanVar(value=bool(_TMc().get("notepad", True)))
        from . import breaks as _BR, topup as _TU, mapprofit as _MP
        self.al_break = tk.BooleanVar(value=bool(_BR.cfg()["on"]))           # 2.131.0: off until turned on
        self.al_topup = tk.BooleanVar(value=bool(_TU.cfg()["on"]))
        self.al_mp = tk.BooleanVar(value=bool(_MP.cfg()["on"]))
        own = {"breaks": self.al_break, "topup": self.al_topup, "mapprofit": self.al_mp}
        opts = {
            "temple": [("Vaal Lens", self.al_tpad, lambda: self.temple_pad_set(self.al_tpad.get()),
                        f"A card in Vaal Ruins and the temple: your crystals, what's on the board, your notes. Press "
                        f"{LOOK} with the Temple Console open: reads the board once.")],
            "remnant": [("Island rumors", self.al_rru, lambda: self.ru_changed(self.al_rru.get()),
                         f"Press {LOOK} in your hideout with the Uncharted Waters card open: each rumor "
                         f"gets the island it leads to and your Map Library rank for it."),
                        ("Runeshape tips", self.al_rtips, lambda: self.remnant_tips_changed(self.al_rtips.get()),
                         "A small list next to the prices: the runeshapes players rate best for loot (S and A tier).")],
            "ritual": [("On screen", self.al_rshow, lambda: self.ritual_readout_changed(self.al_rshow.get()),
                        "On the overlay in Ritual maps: rituals done and your tribute."),
                       ("Favours prices", self.al_rfav, lambda: self.favours_changed(self.al_rfav.get()),
                        f"Press {LOOK} with the Ritual Favours window open: prices its rewards once. "
                        f"The tags stay until your next press or a new area."),
                       # 2.132.4 (feedback: "Ritual Identifier should be part of the Ritual Helper")
                       ("Ritual Identifier", self.al_rid, lambda: self.ritid_changed(self.al_rid.get()),
                        f"Hover a Ritual Altar and press {LOOK}: its type, loot and danger, read once.")]}
        remind = {"breach": (self.al_leave, self.alerts_leave_changed),
                  "ritual": (self.al_rleave, self.alerts_ritual_leave_changed)}

        def more_opts(key, oc):
            """The options that aren't on / off chips: a list, a choice, a link. -> [(words, widget)]"""
            out = []
            if key == "breaks":                                   # 2.131.0: break reminders, every N minutes
                tk.Label(oc, text="every", bg=P2, fg=C["text"], font=sm).pack(side="left", padx=(0, 4))
                ev = tk.StringVar(value=f"{_BR.cfg()['every']} min")
                # (owner: more choices, and your own - pick one, or type minutes and press Enter)
                ecb = ttk.Combobox(oc, textvariable=ev, values=[f"{m} min" for m in _BR.EVERY], width=8)
                ecb.pack(side="left")

                def every_set(_e=None):
                    m = _BR.minutes(ev.get())
                    if m is None:
                        m = _BR.cfg()["every"]                    # (not a number: back to what it was)
                    ev.set(f"{m} min")
                    if m != _BR.cfg()["every"]:
                        self.break_set("every", m)
                ecb.bind("<<ComboboxSelected>>", every_set)
                ecb.bind("<Return>", every_set)
                ecb.bind("<FocusOut>", every_set)
                Tooltip(ecb, f"How often a reminder comes while you play. Pick one, or type your own minutes "
                             f"({_BR.LOWEST}-{_BR.HIGHEST}) and press Enter.")
                self.al_break_every = ecb
                info(oc, "Reminders to keep up with your basic needs during long sessions: water, stretch, food, "
                         "sleep. Never in a map.").pack(side="left", padx=(8, 0))
            elif key == "topup":                                  # 2.131.0: Top Up Reminders
                ib = ttk.Button(oc, text="Items…", command=self.topup_items)
                ib.pack(side="left")
                Tooltip(ib, "Your items and how many of each to keep.")
                info(oc, f"Back from a map, a card asks you to open your inventory and press "
                         f"{self.look_key_text()}: that one read checks your top ups (and counts the map's loot when "
                         f"Map profit is on). Hover an item in your inventory and press {self.topup_key_text()} to "
                         f"track it.").pack(side="left", padx=(8, 0))
                out.append("Items")
            elif key == "mapprofit":                              # 2.132.0: Map profit
                info(oc, f"Back from a map, a card asks you to open your inventory and press "
                         f"{self.look_key_text()}: that one read counts the map's loot - what your inventory gained "
                         f"since your last count at home. Skip it and that map has no entry. Only tracks Currency "
                         f"Exchange based items.").pack(side="left")
            elif key == "campaign":                               # (its options are a card on Overlay › Options)
                cb_ = ttk.Button(oc, text="Options…", command=self.ov_campaign_options_open)
                cb_.pack(side="left")
                Tooltip(cb_, "The Campaign Helper's options (route, optional zones, tips…): Overlay › Options.")
                out.append("Options route")
            return out

        # (2.132.2, feedback: "desecration needs moved up under 'play' settings to be above campaign")
        # (2.132.6, feedback: "Temple in the settings should be listed under Helpers, below Expedition")
        for group, keys in self.HELPER_GROUPS:
            hr = rule()
            hl = tk.Label(tbl, text=group.upper(), bg=P2, fg=C["muted"], font=("Segoe UI", 9, "bold"))
            hl.grid(row=r_[0], column=0, columnspan=5, sticky="w", pady=(8, 2))
            self.al_heads[group] = (hr, hl)
            r_[0] += 1
            for key in keys:
                rl = rule()
                r = r_[0]
                on = own.get(key) or tk.BooleanVar(value=False)
                sw = ttk.Checkbutton(tbl, variable=on, style=CB, command=lambda k=key: self.alerts_toggle(k))
                sw.grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
                Tooltip(sw, f"{names[key]}: on or off")
                cell = tk.Frame(tbl, bg=P2)
                cell.grid(row=r, column=1, sticky="w", padx=(0, 12), pady=4)
                head = tk.Frame(cell, bg=P2)
                head.pack(anchor="w")
                nl = tk.Label(head, text=names[key], bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold"), anchor="w")
                nl.pack(side="left")
                Tooltip(nl, what[key])
                if names[key] in _NEW.FEATURES:                 # 3.0.0: NEW until opened or used (newchip.py)
                    _NEW.chip(head, names[key]).pack(side="left", padx=(8, 0))
                bl = tk.Label(cell, text=blurb[key], bg=P2, fg=C["muted"], font=sm, anchor="w", justify="left",
                              wraplength=320)
                bl.pack(anchor="w")
                self.al_blurbs[key] = (bl, "Beta · " if key in beta else "")
                st = tk.Label(cell, text="", bg=P2, fg=C["muted"], font=sm, anchor="w", justify="left",
                              wraplength=320)
                st.pack(anchor="w")                 # (✓ On / – Off, and what it's doing now)
                dot = tk.Label(cell, text="●", bg=P2, fg=DOT["off"])          # (kept for alerts_refresh; not shown)
                oc = tk.Frame(tbl, bg=P2)
                oc.grid(row=r, column=2, sticky="w", padx=(0, 12))
                mine, words = [], [names[key], blurb[key]]
                for text, var, cmd, tip in opts.get(key, ()):
                    c = chip(oc, text, var, cmd, tip)
                    c.pack(side="left", padx=(0, 8), pady=2)
                    self.al_chips[text] = c
                    mine.append(c)
                    words.append(text)
                words += more_opts(key, oc)
                if oc.pack_slaves():                    # nav phase 2: the options wrap in a narrow window (Ritual's
                    oc.grid_configure(sticky="ew")      # four chips were cut off)
                    flowify(oc, vgap=4)
                    opt_cells.append((oc, r))
                if key in remind:
                    rv, rcmd = remind[key]
                    rs = ttk.Checkbutton(tbl, variable=rv, style=CB, command=rcmd)
                    Tooltip(rs, "Remind me when I leave the map with it unfinished")
                else:
                    rs = tk.Label(tbl, text="-", bg=P2, fg=C["muted"])
                rs.grid(row=r, column=3, padx=(0, 12))
                tbt = ttk.Button(tbl, text="Open" if key in ("focus", "campaign", "music", "mapprofit") else "Test",
                                 command=tests[key], width=6)
                tbt.grid(row=r, column=4, sticky="e")
                if key in test_tips:
                    Tooltip(tbt, test_tips[key])
                r_[0] += 2                              # (D3: the row after is where the options go when it's narrow)
                snd = tk.BooleanVar(value=True)
                self.al_rows[key] = {"dot": dot, "on": on, "sound": snd, "status": st, "what": what[key], "note": "",
                                     "row": cell, "switch": sw, "grid": True, "chips": mine}
                self.al_find.append((key, group, " ".join(words).lower(), (rl, sw, cell, oc, rs, tbt)))
        def narrow_table(_e=None, state={"narrow": None}):
            """D3: under 900 px each helper's options go on the row under its description (as in the mockup); the
            Options column heading goes with them."""
            look = getattr(self, "drawer_look_on", None)
            narrow = tbl.winfo_width() < 900 or bool(look and look())
            if narrow == state["narrow"] or tbl.winfo_width() < 2:
                return
            state["narrow"] = narrow
            for oc_, r0 in opt_cells:
                vis = bool(oc_.grid_info())
                if narrow:
                    oc_.grid(row=r0 + 1, column=1, columnspan=3, sticky="ew", padx=(0, 12), pady=(0, 8))
                else:
                    oc_.grid(row=r0, column=2, columnspan=1, sticky="ew", padx=(0, 12), pady=0)
                if not vis:
                    oc_.grid_remove()
            tbl.grid_columnconfigure(1, weight=1 if narrow else 0)
            tbl.grid_columnconfigure(2, weight=0 if narrow else 1)
            heads_[2].grid_remove() if narrow else heads_[2].grid()
        tbl.bind("<Configure>", narrow_table, add="+")
        def look_chips(on):
            """drawer build: the option chips repainted for the look; in the Drawer "Find it…" is the orange button
            (mockups.html: the thing to do first)."""
            for row in self.al_rows.values():
                for c in row.get("chips") or []:
                    try:
                        c.paint()
                    except (tk.TclError, AttributeError):
                        pass
            try:
                find_it.configure(style="Primary.TButton" if on else "TButton")
            except tk.TclError:
                pass
        self._drawer_look_hooks = getattr(self, "_drawer_look_hooks", []) + [lambda on: narrow_table(), look_chips]
        self.al_rows["breach"]["on"].set(bool(self.breach_cfg().get("on")))
        self.al_rows["breach"]["sound"].set(bool(self.breach_cfg().get("sound", True)))
        self.al_rows["ritual"]["on"].set(bool(self.ritual_cfg().get("on")))
        self.al_rows["ritual"]["sound"].set(bool(self.ritual_cfg().get("sound", True)))
        # 2.130.0 (feedback): the game's hidden setting that applies your item filter to the Favours window
        # 2.130.4 (feedback: "the text for opening the filter in ritual window is a bad UI+UX design choice"): a
        # plain button with the setting's state beside it (a mark and a word), not orange link text
        frow = tk.Frame(self.al_rows["ritual"]["row"], bg=P2)
        frow.pack(anchor="w", pady=(4, 0))
        fl = ttk.Button(frow, text="Filter in the Ritual window…", command=self.ritual_filter_open)
        fl.pack(side="left")
        Tooltip(fl, "Enables your loot filter in the Ritual Favours window.")
        fst = tk.Label(frow, text="", bg=P2, fg=C["muted"], font=sm, anchor="w")
        fst.pack(side="left", padx=(8, 0))
        self.al_rfilter_link, self.al_rfilter_state = fl, fst
        self.ritual_filter_state()
        self.al_rows["remnant"]["on"].set(bool(self.remnant_cfg().get("on")))          # 2.37.0
        self.al_rows["temple"]["on"].set(bool(self.temple_on()))                       # 2.132.6
        self.al_temple = self.al_rows["temple"]["on"]
        self.al_rows["sekhemas"]["on"].set(bool(self.sek_on()))                       # Trial of the Sekhemas
        self.al_sek = self.al_rows["sekhemas"]["on"]
        self.al_rows["music"]["on"].set(bool(self.music_wanted()))                     # 2.134.0
        self.al_music = self.al_rows["music"]["on"]
        self.al_rows["desecrate"]["on"].set(bool(self.ws_cfg().get("on")))            # 2.81.0
        from . import campaign as _CP, focus as _F
        self.al_rows["focus"]["on"].set(bool(_F.cfg()["on"]))                          # 2.90.0
        self.al_rows["campaign"]["on"].set(bool(_CP.cfg()["on"]))
        from . import whispers as _W                                                    # 2.98.1
        self.al_rows["whispers"]["on"].set(bool(_W.cfg()["on"]))
        self.al_rows["whispers"]["sound"].set(bool(_W.cfg()["sound"]))
        from .chrome import EmptyState                     # (nav phase 2: the search found nothing)
        self.al_empty = EmptyState(box, "⌕", "No helper matches\nTry another word, or pick All.",
                                   button=("Clear search", lambda: (self.al_q.set(""), self.al_group.pick("All"))),
                                   bg_key="panel2")
        self.alerts_refresh()
        return box

    def al_filter(self):
        """Search helpers + In maps / Play / Trading / Misc: the rows that match stay, every word you type has to be there."""
        rows = getattr(self, "al_find", None)
        if not rows:
            return
        q = (self.al_q.get() or "").lower().split()
        grp = self.al_group.value
        shown = set()
        for key, group, words, ws in rows:
            ok = (grp == "All" or grp == group) and all(p in words for p in q)
            for w in ws:
                try:
                    w.grid() if ok else w.grid_remove()
                except tk.TclError:
                    pass
            if ok:
                shown.add(group)
        for group, ws in self.al_heads.items():
            for w in ws:
                try:
                    w.grid() if group in shown else w.grid_remove()
                except tk.TclError:
                    pass
        try:
            if shown:
                self.al_empty.pack_forget()
            elif not self.al_empty.winfo_manager():
                self.al_empty.pack(pady=(16, 8), after=self.al_table)
        except tk.TclError:
            pass

    def helper_switch_on(self, key):
        """One helper's own switch (the setting its Overlay › Helpers row switches) - not whether it runs now. (Setup and
        Turn all on / off read it.)"""
        from . import features as _FEAT
        if key in _FEAT.HELPER_SWITCHES:
            return _FEAT.helper_on(key)
        if key == "breach":
            return bool(self.breach_cfg().get("on"))
        if key == "ritual":
            return bool(self.ritual_cfg().get("on"))
        if key == "remnant":
            return bool(self.remnant_cfg().get("on"))
        if key == "desecrate":
            return bool(self.ws_cfg().get("on"))
        from . import campaign as _CP, focus as _F, whispers as _W
        return bool({"focus": _F, "campaign": _CP, "whispers": _W}[key].cfg().get("on"))

    def helpers_all(self, on):
        """Overlay › Helpers' Turn all on / Turn all off: every helper's own switch (only the ones that change)."""
        for _g, keys in self.HELPER_GROUPS:
            for k in keys:
                try:
                    if self.helper_switch_on(k) != bool(on):
                        self.alerts_toggle(k, bool(on))
                except Exception:
                    buglog.caught()
        self._say("Every helper is on." if on else "Every helper is off.", 4)

    def alerts_toggle(self, key, want=None):
        """On / off for one helper. want=None: what its box in the Alerts panel says. 2.26.0: the timer's Helpers bar
        switches them too (the panel may not even be built then)."""
        rows = getattr(self, "al_rows", None) or {}

        class _Box:                                           # the panel's box, or a stand-in when it isn't built
            def __init__(self, v):
                self.v = v

            def get(self):
                return self.v

            def set(self, v):
                self.v = v
        r = rows.get(key) or {"on": _Box(bool(want)), "note": ""}
        if want is None:
            want = bool(r["on"].get())
        else:
            r["on"].set(bool(want))
        if key == "breach":
            self.breach_cfg()["on"] = want
            save_json("settings.json", SETTINGS)
            if want:
                self.breach_start()
            else:
                self.breach_stop()
        elif key == "ritual":
            self.ritual_cfg()["on"] = want
            save_json("settings.json", SETTINGS)
            self.ritual_start() if want else self.ritual_stop()
        elif key == "remnant":                                # 2.37.0
            err = self.remnant_toggle(want)
            r["note"] = err or ""
        elif key == "desecrate":                              # 2.81.0
            err = self.ws_toggle(want)
            r["note"] = err or ""
        elif key == "focus":                                  # 2.90.0
            self.focus_set_on(bool(want))
            self._helper_needs_overlay(want, "League Plan")
        elif key == "campaign":
            self.camp_set_on(bool(want))
            self._helper_needs_overlay(want, "The Campaign Helper")
        elif key == "topup":                                  # 2.131.1: Quick settings switch it too
            self.topup_set(bool(want))
            v = getattr(self, "al_topup", None)
            if v is not None and bool(v.get()) != bool(want):
                v.set(bool(want))
        elif key in ("mapprofit", "temple"):                  # 2.132.1: Quick settings switch them too
            (self.mp_set if key == "mapprofit" else self.temple_set)(bool(want))
            v = getattr(self, "al_mp" if key == "mapprofit" else "al_temple", None)
            if v is not None and bool(v.get()) != bool(want):
                v.set(bool(want))
        elif key == "music":                                  # 2.134.0
            self.music_set(bool(want))
        elif key == "sekhemas":                               # Trial of the Sekhemas (Quick settings too)
            self.sek_set(bool(want))
            v = getattr(self, "al_sek", None)
            if v is not None and bool(v.get()) != bool(want):
                v.set(bool(want))
        elif key == "breaks":
            self.break_set("on", bool(want))
            v = getattr(self, "al_break", None)
            if v is not None and bool(v.get()) != bool(want):
                v.set(bool(want))
        elif key == "whispers":                               # 2.98.1
            from . import whispers as _W
            _W.cfg()["on"] = bool(want)
            _W.save()
            if want:
                self.breach_start()                           # (the helpers' Client.txt reader)
            else:
                self.breach_stop()
            self._helper_needs_overlay(want, "The Trade Whisper Watcher")
        if rows:
            self.alerts_refresh()
        self.alerts_overlay_redraw()

    def _helper_needs_overlay(self, want, name):
        """2.97.0: Focus and Campaign live on the overlay's bar - switching one on turns the overlay on too."""
        try:
            if want and not self.ov_enabled():
                self.ov_enable(True)
                self._say(f"{name} shows on the overlay, so the overlay is on now.", 6)
        except Exception:
            self.log_error("the overlay")

    # ================================================================ 2.98.1: Trade Whisper Watcher
    def ww_whisper(self, data):
        """A whisper to you (from the log). A trade request while the watcher is active -> the card."""
        from . import whispers as W
        if not W.active():
            return None
        trade = W.parse_trade(data.get("msg"))
        if trade is None:
            return None
        self.ww_last = time.strftime("%H:%M")
        return self.ww_show(data.get("who") or "", trade)

    def ww_show_test(self):
        return self.ww_show("ExampleBuyer", {"item": "Havoc Visage Ancestral Tiara", "price": "90 divine",
                                             "league": "", "tab": "~b/o 90 divine", "left": 3, "top": 5}, test=True)

    def ww_show(self, who, trade, test=False):
        """A card at the top of the game: who wants what, for how much, where it is in your tab. It stays until you
        close it or for its time (Settings: 20 s), several stack; the overlay's own look. Nothing is saved."""
        from . import whispers as W
        from .overlaywin import OverlayWindow, pal
        if not test and not self.ov_enabled():
            return None
        P = pal()
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        Wd = self.ov_px(420)
        cards = [c for c in getattr(self, "ww_cards", []) if c.winfo_exists()]
        while len(cards) >= 3:                                   # at most 3 at once - the oldest goes
            old = cards.pop(0)
            try:
                old.destroy()
            except tk.TclError:
                pass
        y = r[1] + int(r[3] * 0.08) + sum(c.winfo_height() + 8 for c in cards)
        w = OverlayWindow(self.root, "Trade whisper", "💬", (r[0] + (r[2] - Wd) // 2, y, Wd, None), palette=P,
                          lockable=False, follow_game=True, no_activate=True, on_close=None)
        bg = P["bg"]
        body = tk.Frame(w.body, bg=bg, padx=16, pady=8)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=trade.get("item") or "Someone wants to buy an item", bg=bg, fg=P["head"],
                 font=(P["font"], self.ov_font(12), "bold"), anchor="w", justify="left",
                 wraplength=Wd - 40).pack(fill="x")
        if trade.get("price"):
            tk.Label(body, text=f"for {trade['price']}", bg=bg, fg=P["text"], font=(P["font"], self.ov_font(11)),
                     anchor="w").pack(fill="x")
        spot = W.where(trade)
        if spot:
            tk.Label(body, text=spot, bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9)), anchor="w").pack(fill="x")
        if who:
            tk.Label(body, text=f"from {who}" + ("   (a test)" if test else ""), bg=bg, fg=P["muted"],
                     font=(P["font"], self.ov_font(9)), anchor="w").pack(fill="x", pady=(4, 0))
        w.show()
        cards.append(w)
        self.ww_cards = cards
        secs = int(W.cfg().get("secs") or 20)
        self.root.after(secs * 1000, lambda: w.winfo_exists() and w.destroy())
        if W.cfg().get("sound") and not test:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                buglog.caught()
        self.alerts_refresh()
        return w

    def alerts_sound_all(self):
        """P2.5: the one Sound switch - every helper's alert sound on or off."""
        self.helpers_sound_set(bool(self.al_sound_all.get()))     # (P4: shared with Quick settings)

    def alerts_sound(self, key):
        r = self.al_rows[key]
        if key == "whispers":
            from . import whispers as _W
            _W.cfg()["sound"] = bool(r["sound"].get())
            _W.save()
            return
        cfg = {"breach": self.breach_cfg, "ritual": self.ritual_cfg}[key]()
        cfg["sound"] = bool(r["sound"].get())
        save_json("settings.json", SETTINGS)

    def alerts_leave_changed(self):
        self.breach_cfg()["leave_reminder"] = bool(self.al_leave.get())
        save_json("settings.json", SETTINGS)

    def ritual_filter_state(self):
        """The state beside the button: ✓ On / ✗ Off / ? Not found (read from the game's file - that line only)."""
        from . import ritual_filter as RF
        lbl = getattr(self, "al_rfilter_state", None)
        if lbl is None:
            return None
        st, _path = RF.state()
        text, col = {"on": ("✓ On", C.get("good", C["text"])), "off": ("✗ Off", C.get("warn", C["text"])),
                     "missing": ("? Not set", C["muted"]), "nofile": ("? Not found", C["muted"])}[st]
        try:
            lbl.config(text=text, fg=col)
        except tk.TclError:
            pass
        return st

    def ritual_filter_open(self):
        """2.130.0 Filter in the Ritual window: where the game's setting is, whether it's on, and how to turn it on
        (one line to change). 2.130.4: Turn it on changes it for you while the game is closed."""
        from . import ritual_filter as RF
        old = getattr(self, "rf_dlg", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.destroy()
            except tk.TclError:
                pass
        P2 = C["panel2"]
        dlg = tk.Toplevel(self.root)
        dlg.title("Filter in the Ritual window")
        dlg.configure(bg=P2, padx=16, pady=16)
        dlg.transient(self.dlg_parent())
        dlg.resizable(False, False)
        self.rf_dlg = dlg
        top = tk.Frame(dlg, bg=P2)
        top.pack(fill="x")
        tk.Label(top, text="Make your item filter hide junk in the Ritual altar's Favours window.", bg=P2,
                 fg=C["text"], font=("Segoe UI", 10), anchor="w").pack(side="left")
        tip = tk.Label(top, text="ⓘ", bg=P2, fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow")
        tip.pack(side="left", padx=(8, 0))
        Tooltip(tip, f"Game Setting: Automatically turn it on, or configure it manually. {RF.CREDIT}.")
        status = tk.Label(dlg, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 10, "bold"), anchor="w",
                          justify="left", wraplength=460)
        status.pack(fill="x", pady=(8, 2))
        where = tk.Label(dlg, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                         wraplength=460)
        where.pack(fill="x")
        steps = ("1.  Close the game (it rewrites this file when it closes).",
                 f"2.  Open folder (where your item filters are), then open {RF.FILE} in Notepad.",
                 "3.  Use Edit › Find in Notepad and paste (Copy line puts it on your clipboard).",
                 "4.  Change false to true, then save.",
                 "5.  Start the game and open a Ritual altar's Favours window.")
        box = tk.Frame(dlg, bg=P2)
        box.pack(fill="x", pady=(8, 4))
        for s_ in steps:
            tk.Label(box, text=s_, bg=P2, fg=C["text"], font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=1)
        said = tk.Label(dlg, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w")
        said.pack(fill="x", pady=(4, 0))

        def check():
            st, path = RF.state()
            text, col = {"on": ("✓ On - your filter applies in the Favours window.", C.get("good", C["text"])),
                         "off": ("✗ Off - follow the steps below.", C.get("warn", C["text"])),
                         "missing": ("? The line isn't in your file - start the game once, close it, check again.",
                                     C["muted"]),
                         "nofile": ("? The file isn't there yet - start the game once, close it, check again.",
                                    C["muted"])}[st]
            status.config(text=text, fg=col)
            where.config(text=RF.shown(path))          # (no Windows user name on screen)
            self.ritual_filter_state()
            try:                                       # (grayed out unless it's off - nothing to turn on)
                if wait.get("job") is None:
                    on_btn.state(["!disabled"] if st == "off" else ["disabled"])
            except (NameError, tk.TclError):
                pass
            return st, path

        def open_folder():
            _st, path = RF.state()
            try:
                if sys.platform == "win32":
                    import subprocess
                    if os.path.isfile(path):
                        subprocess.Popen(["explorer", "/select,", path])
                    else:
                        os.startfile(os.path.dirname(path) if os.path.isdir(os.path.dirname(path))
                                     else RF.documents())
                    said.config(text="Opened the folder.")
                else:
                    said.config(text="Opening folders works on Windows.")
            except Exception:
                buglog.caught()
                said.config(text="Couldn't open the folder - it's shown above.")

        def copy_line():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(f"{RF.KEY}=false")
                self.own_clip = f"{RF.KEY}=false"
                said.config(text=f"Copied: {RF.KEY}=false - paste it into Notepad's Find.")
            except tk.TclError:
                said.config(text="Couldn't copy - type it: " + RF.KEY)
        wait = {"job": None, "gone": None, "mt": None}

        def file_mtime(path):
            try:
                return os.path.getmtime(path)
            except OSError:
                return None

        def turn_on():
            """2.130.4 (feedback): the game must be fully closed (it saves this file as it closes) - then the one
            line is changed, and you're told when to start the game again."""
            if not dlg.winfo_exists():
                return
            _st, path = RF.state()
            if game_rect() is not None:
                wait["gone"], wait["mt"] = None, None
                said.config(text="Close the game fully (not just to the character screen) - waiting for it…",
                            fg=C.get("warn", C["text"]))
                on_btn.state(["disabled"])
                wait["job"] = dlg.after(1000, turn_on)
                return
            now, mt = time.time(), file_mtime(path)
            if wait["gone"] is None or mt != wait["mt"]:          # just closed (or still saving): wait 4 s quiet
                wait["gone"], wait["mt"] = now, mt
            if now - wait["gone"] < 4:
                said.config(text="The game is closing - one moment…", fg=C["muted"])
                wait["job"] = dlg.after(1000, turn_on)
                return
            ok, note = RF.turn_on(path, P("backups"))
            wait["job"] = None
            said.config(text=(note + " You can start the game again.") if ok else note,
                        fg=C.get("good", C["text"]) if ok else C.get("warn", C["text"]))
            check()
        btns = tk.Frame(dlg, bg=P2)
        btns.pack(fill="x", pady=(12, 0))
        on_btn = ttk.Button(btns, text="Turn it on", style="Primary.TButton", command=turn_on)
        on_btn.pack(side="left")
        Tooltip(on_btn, "Game must be closed to edit config file.")
        ttk.Button(btns, text="Open folder", command=open_folder).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Copy line", command=copy_line).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Check again", command=check).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="right")
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        check()
        try:
            from .style import center_over
            center_over(dlg, self.dlg_parent())
        except Exception:
            buglog.caught()
        dlg.rf_check, dlg.rf_open, dlg.rf_copy, dlg.rf_said, dlg.rf_status = check, open_folder, copy_line, said, status
        dlg.rf_on, dlg.rf_on_btn = turn_on, on_btn
        return dlg

    def alerts_ritual_leave_changed(self):
        self.ritual_cfg()["leave_reminder"] = bool(self.al_rleave.get())
        save_json("settings.json", SETTINGS)

    def alerts_test_desecrate(self):
        r = self.al_rows["desecrate"]
        r["note"] = self.ws_test()
        self.alerts_refresh()

    def alerts_test_remnant(self):
        r = self.al_rows["remnant"]
        r["note"] = self.remnant_test()
        self.alerts_refresh()

    def alerts_test_ritual(self):
        self.breach_alert(test=True, level="ritual", sub="1 of 3 done (a test)")

    # ---- Ritual helper (GGG policy: reads on a Read Key press - ritual_look_job; the game's log says the rest)
    def ritual_start(self):
        if self.br_reader is None:
            self.breach_start()                         # to see you leave a map, and rituals start
        self.root.after(1500, self.alerts_refresh)
        return None

    def ritual_stop(self):
        from .ritual_alert import STATE
        STATE.clear()
        self.rt_map = None
        self.favours_hide()
        if not self.log_wanted():
            self.br_reader = None
        self.ritual_readout_sync()
        self.alerts_refresh()
        return None

    def ritual_status(self):
        if not self.ritual_cfg().get("on"):
            return "off"
        return "warn" if getattr(self, "rt_problem", None) else "on"

    def ritual_look_job(self, ctx):
        """A Read Key press in a map or the campaign: the Ritual counter and the tribute, from the press's one
        picture (never Map Content - owner decision)."""
        from . import features as FEAT
        if not (self.ritual_cfg().get("on") and FEAT.on("overlay")) or ctx["area"] not in ("map", "other", None):
            return None
        from . import ritual_alert as RA
        try:
            ready = RA.template() is not None
        except Exception:
            ready = False
        if not ready:                                     # (no icon to look for: nothing to read - decided before
            return None                                   #  any picture, so no read mark for a read that didn't happen)
        g = ctx["g"]

        def work():
            return RA.look(g, tribute=ctx["area"] in ("map", None))
        work.found = lambda res: bool(res) and (res.get("kind") != "none" or res.get("tribute") is not None)
        return "Ritual", work, self.ritual_look_done

    def ritual_look_done(self, res):
        from .ritual_alert import STATE
        if res is None:
            return
        self.rt_problem = None
        STATE.read_at = time.time()
        STATE.seen = res["kind"]
        STATE.count = res["val"] if res["kind"] == "ok" else None
        t = res.get("tribute")
        if t == 0:
            STATE.tribute = None                          # (offered - 0 left)
        elif t is not None:
            STATE.tribute = t
        buglog.debug("Ritual", f"read: counter {res['kind']}" + (f" {res['val'][0]}/{res['val'][1]}" if res["val"] else "")
                     + f", tribute {t}")
        self.ritual_seen()

    # ---- the game's log (no per-press limit): a ritual started / was disrupted
    def ritual_log(self, what, ts=None):
        """Client.txt's Ritual lines in a map: its monsters' debug lines when a ritual starts (many at once - one ritual
        each 20 s at most), and "The ritual has been disrupted!"."""
        if getattr(self, "br_area", None) != "map" or not self.ritual_cfg().get("on"):
            return
        lg = self.__dict__.setdefault("rt_log", {"starts": 0, "disrupted": 0, "last": 0.0})
        ts = time.time() if ts is None else ts
        if what == "start":
            if ts - lg["last"] > 20:
                lg["starts"] += 1
                buglog.debug("Ritual", f"log: a ritual started ({lg['starts']} this map)")
            lg["last"] = ts
        elif what == "disrupted":
            lg["disrupted"] += 1
            buglog.debug("Ritual", f"log: a ritual was disrupted ({lg['disrupted']} this map)")
        try:
            self.overlay_capture_sync()                  # (a Ritual map now: a press sees the counter under the bar)
        except Exception:
            buglog.caught()
        self.ritual_readout_sync()

    def ritual_log_counts(self):
        lg = getattr(self, "rt_log", None) or {}
        return lg.get("starts", 0), lg.get("disrupted", 0)

    def ritual_estimate(self, count):
        """The last read (done, total) plus the rituals the log says started since then, less any disrupted."""
        if not count:
            return count
        s, d = self.ritual_log_counts()
        bs, bd = getattr(self, "rt_base", (0, 0))
        more = max(0, (s - bs) - (d - bd))
        return (min(count[1], count[0] + more), count[1]) if more else count


    def alert_states(self):
        """{"breach": "on" | "off" | "warn", ...}: the panel's dots and the timer's bar.
        warn = switched on but not working (Client.txt not found)."""
        b = self.breach_status()
        return {"breach": "off" if b is False else "warn" if b == "warn" and self.br_reader is None
                else "on", "ritual": self.ritual_status(), "remnant": self.remnant_status(),
                "desecrate": self.ws_status()} | self._alert_states_more()

    def _alert_states_more(self):
        from . import campaign as _CP, focus as _F                                # 2.90.0
        from . import whispers as _W
        w = "off" if not _W.cfg()["on"] else ("on" if _W.active() and getattr(self, "br_reader", None) is not None
                                              else "warn" if getattr(self, "br_reader", None) is None else "off")
        from . import topup as _TU, breaks as _BR                                   # 2.131.1
        from . import mapprofit as _MP, temple as _TM                               # 2.132.1
        return {"focus": "on" if _F.cfg()["on"] else "off", "campaign": "on" if _CP.cfg()["on"] else "off",
                "whispers": w, "topup": "on" if _TU.cfg().get("on") else "off",
                "breaks": "on" if _BR.cfg().get("on") else "off",
                "mapprofit": "on" if _MP.cfg().get("on") else "off", "temple": "on" if _TM.cfg().get("on") else "off",
                "music": "on" if self.music_wanted() else "off",
                "sekhemas": "on" if self.sek_on() else "off"}

    def alerts_refresh(self):
        """Every 2 s (util_refresh) and after a change: dots, checkboxes and status lines."""
        rows = getattr(self, "al_rows", None)
        if not rows:
            return
        states = self.alert_states()
        for k, (bl, pre) in getattr(self, "al_blurbs", {}).items():     # (the Read Key's name follows the setting)
            rows[k]["what"] = helper_blurb(k, self.look_key_text())
            try:
                bl.config(text=pre + rows[k]["what"])
            except tk.TclError:
                pass
        for c in getattr(self, "al_chips", {}).values():                # (and the option tips that name it)
            if getattr(c, "tip_tpl", None) and getattr(c, "_tip", None) is not None:
                c._tip.text = c.tip_tpl.replace(LOOK, self.look_key_text())
        if not self.breach_cfg().get("on"):
            btxt = rows["breach"]["what"]
        elif self.br_reader is None:
            btxt = self.br_note or "On - looking for Client.txt…"
        elif self.br_win is not None:
            btxt = f"Warned at {time.strftime('%H:%M', time.localtime(max(self.br_last.values() or [time.time()])))}"
        elif self.breach_cfg().get("pending"):
            btxt = ("On - Hiveblood is waiting to be spent" + (": you'll be reminded when you leave the map"
                                                              if self.breach_cfg().get("leave_reminder", True) else ""))
        else:
            btxt = "On - Watching for Hiveblood messages."
        rtxt = self.ritual_text(rows["ritual"])
        mtxt = rows["remnant"]["note"] or self.remnant_text(rows["remnant"])
        rows["remnant"]["note"] = ""
        rows["remnant"]["on"].set(bool(self.remnant_cfg().get("on")))
        wtxt = rows["desecrate"]["note"] or self.ws_text(rows["desecrate"])         # 2.81.0
        rows["desecrate"]["note"] = ""
        rows["desecrate"]["on"].set(bool(self.ws_cfg().get("on")))
        from . import campaign as _CP, focus as _F                                # 2.90.0
        rows["focus"]["on"].set(bool(_F.cfg()["on"]))
        rows["campaign"]["on"].set(bool(_CP.cfg()["on"]))
        ftxt = ("On - " + (self.focus_line()[0] or "pick a goal on League Plan")) if _F.cfg()["on"] else rows["focus"]["what"]
        ctxt = ("On - " + (_CP.line_text() or "Waiting for a campaign zone.")) if _CP.cfg()["on"] else rows["campaign"]["what"]
        from . import whispers as _W                                              # 2.98.1
        rows["whispers"]["on"].set(bool(_W.cfg()["on"]))
        if not _W.cfg()["on"]:
            vtxt = rows["whispers"]["what"]
        elif getattr(self, "br_reader", None) is None:
            vtxt = self.br_note or "On - looking for Client.txt…"
        else:
            last = getattr(self, "ww_last", None)
            vtxt = "On - watching your whispers" + (f" (last trade whisper {last})" if last else "")
        from . import temple as _TMs                                                    # 2.132.6: Temple's row
        rows["temple"]["on"].set(bool(self.temple_on()))
        _st = _TMs.state()
        ttxt = (("On - " + _TMs.count_text(_st)) if _st else
                self.look_status(f"On - press {self.look_key_text()} with the Temple Console open.")) \
            if self.temple_on() \
            else rows["temple"]["what"]
        rows["sekhemas"]["on"].set(bool(self.sek_on()))                                 # Trial of the Sekhemas
        stxt = self.sek_status() if self.sek_on() else rows["sekhemas"]["what"]
        self.music_sync()                                                               # 2.134.0
        rows["music"]["on"].set(bool(self.music_wanted()))
        utxt = (("On - drag it where you want it." if self.music_on() else "On - shows while the overlay is on.")
                if self.music_wanted() else rows["music"]["what"])
        from . import breaks as _BRs, topup as _TUs, mapprofit as _MPs                # nav phase 2: in the table
        more = []
        for k, on, txt in (("breaks", _BRs.cfg().get("on"), f"On - every {_BRs.cfg().get('every')} min, in your "
                                                             "hideout or a town."),
                           ("topup", _TUs.cfg().get("on"), self.look_status(
                               f"On - back from a map, a card asks you to press {self.look_key_text()}.")),
                           ("mapprofit", _MPs.cfg().get("on"), self.look_status(
                               f"On - back from a map, a card asks you to press {self.look_key_text()}."))):
            if k in rows:
                if bool(rows[k]["on"].get()) != bool(on):
                    rows[k]["on"].set(bool(on))
                more.append((k, txt if on else rows[k]["what"]))
        for k, txt in [("breach", btxt), ("ritual", rtxt), ("remnant", mtxt), ("desecrate", wtxt),
                       ("focus", ftxt), ("campaign", ctxt), ("whispers", vtxt), ("temple", ttxt),
                       ("music", utxt), ("sekhemas", stxt)] + more:
            st = states[k]
            if st == "on" and txt == UNSET_STATUS:  # GGG policy: on, but nothing reads without a Read Key
                st = "warn"
            lbl = rows[k]["status"]
            if rows[k].get("grid"):                 # 2.112.0: one short line under the name
                # nav phase 2 (never a state by color alone): a mark and a word - ✓ On / – Off / ⚠ - then what it's
                # doing now (2.119.0: the gray line above it says what it does)
                if txt.startswith("On - "):
                    txt = txt[5:6].upper() + txt[6:]
                if st == "off":
                    txt = "– Off" + (f" · {txt}" if txt and txt != rows[k]["what"] else "")
                elif st == "warn":
                    txt = "⚠ " + txt
                else:
                    txt = "✓ On" + (f" · {txt}" if txt and txt != rows[k]["what"] else "")
                try:
                    if txt and not lbl.winfo_manager():
                        lbl.pack(anchor="w")
                    elif not txt and lbl.winfo_manager():
                        lbl.pack_forget()
                except tk.TclError:
                    pass
            else:
                show = st != "off" or txt != rows[k]["what"]
                try:
                    if show and not lbl.winfo_manager():
                        lbl.pack(fill="x", padx=(24, 8), after=rows[k]["row"])
                    elif not show and lbl.winfo_manager():
                        lbl.pack_forget()
                except tk.TclError:
                    pass
            rows[k]["dot"].config(fg=DOT[st])
            for c in rows[k].get("chips", ()):
                try:
                    c.paint(dim=st == "off")
                except tk.TclError:
                    pass
            rows[k]["status"].config(text=txt, fg=C["red"] if st == "warn" else C["green"] if st == "on" else C["muted"])
        ban = getattr(self, "al_log_banner", None)            # 2.119.0: Client.txt not found - one banner
        if ban is not None:
            want = getattr(self, "br_reader", None) is None and bool(self.br_note)
            try:
                if want and not ban.winfo_manager():
                    ban.pack(fill="x", pady=(8, 0), after=self.al_log_after)
                elif not want and ban.winfo_manager():
                    ban.pack_forget()
            except tk.TclError:
                pass

    def ritual_text(self, row):
        from .ritual_alert import STATE as RITUAL
        if row["note"]:
            txt, row["note"] = row["note"], ""
            return txt
        if not self.ritual_cfg().get("on"):
            return row["what"]
        if getattr(self, "rt_problem", None):
            return "Screen read problem: " + self.rt_problem
        count = self.ritual_estimate(getattr(self, "rt_map", None))
        if count and getattr(self, "br_area", None) == "map":
            d, t = count
            return f"On - this map: {d} of {t} rituals done" + (" ✔" if d >= t else "")
        if RITUAL.seen == "unread":
            return ("On - the Ritual counter was on screen but couldn't be read. Report a bug (Settings › "
                    "Advanced › Problems) so it can be fixed.")
        return self.look_status(f"On - press {self.look_key_text()} in a map to read the Ritual counter.")

    def ritual_seen(self):
        """After a Read Key press: remember the counter while you're in a map."""
        from .ritual_alert import STATE as RITUAL
        if RITUAL.seen == "ok" and RITUAL.count and self.br_area in ("map", None):
            self.rt_map = RITUAL.count
            self.rt_base = self.ritual_log_counts()        # (the log's rituals after this read add to it)
        try:                                                 # 2.129.4: a Ritual map - the bar out of captures while
            self.overlay_capture_sync()                      # its rituals are left (a press sees the counter)
        except Exception:
            buglog.caught()
        self.ritual_readout_sync()

    def alerts_overlay_redraw(self):
        try:
            self.tracker_helpers_paint()                           # 2.49.0: the bar stands on its own
        except Exception:
            buglog.caught()
        if getattr(self, "tk_overlay", None) is not None:
            try:
                self.tracker_overlay_draw(self.tracker_numbers())
            except Exception:
                buglog.caught()

    # ================================================================ Breach: following Client.txt
    def breach_start(self):
        """Follow Client.txt from its end (the Session tracker's file, or the one picked there)."""
        self.alerts_init()
        tc = getattr(self, "tracker_cfg", None)
        path = find_log(tc().get("log_path") if tc else None)
        if not path:
            self.br_reader = None
            self.br_note = "On - waiting for Client.txt (see the note above)"     # 2.119.0: the banner says why
        else:
            self.br_reader = LogReader(path)
            tail = self.br_reader.start()             # only what the game writes from now on
            self.br_note = ""
            last = next((d for k, _t, d in reversed(tail or []) if k == "area"), None)
            if last is not None:                      # 2.104.1 (feedback: Island Rumors never showed): started in
                try:                                  # your hideout, the helpers knew only after the next area
                    kind0 = gl_area_kind(last.get("area"), last.get("seed"), last.get("level", 0))
                    self.br_area_start = kind0        # (the Read Key: where you are until the next area change -
                    at = next((n for n, (_k, _t, _d) in enumerate(tail) if _d is last), len(tail))   # not "anywhere";
                    self.look_at_login = any(k_ == "login" for k_, _t, _d in tail[at + 1:])         # look_area)
                    self.expedition_area(last.get("area"), kind0)
                    # 2.125.7 (feedback: turned on while at the Well, nothing showed): the Desecration Helper too
                    self.ws_area(last.get("area"))
                    self.temple_area(last.get("area"))             # 2.136.0: Vaal Lens
                    self.campaign_where(last)                      # Round 18: a hideout - no Campaign Bar
                    i = next((n for n, (k, _t, _d) in enumerate(tail) if _d is last), None)
                    self.sek_area(last.get("area"))                # Trial of the Sekhemas: the floor
                    scene = next((d for k, _t, d in (tail[i:] if i is not None else []) if k == "scene"), None)
                    if scene is not None:
                        self.ws_scene(scene.get("name"))
                except Exception:
                    self.log_error("the area helpers")
        if not self._br_ticking:
            self._br_ticking = True
            self.root.after(1000, self.breach_tick)
        self.alerts_refresh()

    def breach_stop(self):
        if not self.log_wanted():
            self.br_reader = None
        self.breach_dismiss()
        self.alerts_refresh()

    def breach_tick(self):
        try:
            if self.log_wanted():
                if self.br_reader is None:
                    self.br_ticks += 1
                    if self.br_ticks % RETRY_TICKS == 0:
                        self.breach_start()
                else:
                    for kind, _ts, data in self.br_reader.poll():   # (_ts: the line's time)
                        if kind == "breach" and "hiveblood" in data["text"].lower() and \
                                self.breach_cfg().get("on"):
                            self.breach_set_pending(breach_level(data["text"]))
                            self.breach_alert(text=data["text"])
                        elif kind == "whisper":
                            self.ww_whisper(data)                  # 2.98.1: Trade Whisper Watcher
                        elif kind == "ritual":
                            self.ritual_log(data.get("what"), _ts)    # GGG policy: the log, not the screen
                        elif kind == "brequel_tree":
                            self.breach_set_pending(None)          # spent (the tree was opened)
                            self.breach_dismiss()
                        elif kind == "login":
                            self.br_relog = True             # 2.130.2: the character screen (any character)
                            self.look_at_login = True        # (the Read Key: nothing of the game's to read there)
                            try:                             # 2.142.2 (feedback: Vaal Lens on the login screen):
                                self.temple_area(None)       # out of the temple until an area says otherwise
                                self.sek_area(None)          # (and out of the trial: its legend goes)
                            except Exception:
                                self.log_error("Vaal Lens")
                        elif kind == "scene":
                            try:
                                self.ws_scene(data.get("name"))      # 2.125.7: the Well by its name too
                            except Exception:
                                self.log_error("the Desecration Helper")
                        elif kind == "area":
                            self.look_at_login = False                # (in the game again)
                            try:
                                self.ws_area(data.get("area"))        # 2.81.0: the Desecration Helper
                                self.temple_area(data.get("area"))    # 2.136.0: Vaal Lens
                                self.sek_area(data.get("area"))       # Trial of the Sekhemas
                                self.expedition_area(data.get("area"), gl_area_kind(      # 2.83.0: Remnant's places,
                                    data.get("area"), data.get("seed"), data.get("level", 0)))  # Island Rumors
                            except Exception:
                                self.log_error("the area helpers")
                            self.breach_area(gl_area_kind(data.get("area"), data.get("seed"), data.get("level", 0)),
                                             (data.get("area"), data.get("seed")))
        except Exception:
            self.log_error("breach alert")
        if self.log_wanted():
            self.root.after(1000, self.breach_tick)
        else:
            self._br_ticking = False

    def breach_set_pending(self, level):
        cfg = self.breach_cfg()
        if level == "almost" and cfg.get("pending") == "full":
            return
        if cfg.get("pending") != level:
            cfg["pending"] = level
            save_json("settings.json", SETTINGS)

    def breach_area(self, kind, where=None):
        """2.11.0: leaving a map (to your hideout or a town) with Hiveblood still waiting -> one reminder per exit,
        every exit, until the Genesis Tree has been opened."""
        before, self.br_area = self.br_area, kind
        if before != kind:
            buglog.debug("area", f"{before} -> {kind}")     # 2.129.3: kinds only (map, hideout, town), no names
        try:
            self.fl_area(kind, where, before)                # 2.45.0: the Strat Tracker counts its runs
        except Exception:
            self.log_error("Strat Tracker run counting")
        cfg = self.breach_cfg()
        left = before == "map" and kind in ("hideout", "town")
        relog, self.br_relog = getattr(self, "br_relog", False), False
        if left and relog:          # 2.130.2 (feedback): out through the character screen (died, switched character,
            buglog.debug("leave check", "skipped: came back through the character screen")   # logged out) - the
            left = False            # map is still there to go back to; no reminder for leaving it
        if left and cfg.get("on") and cfg.get("pending") and cfg.get("leave_reminder", True):
            self.breach_alert(level="leave")
        rc, got = self.ritual_cfg(), self.ritual_estimate(self.rt_map)   # 2.14.0: rituals left undone in the map you
        #                                                     just left (the last Read Key read, and the log since)
        if left and rc.get("on"):                           # 2.129.3 (feedback: 2 of 3 and no reminder): the log says
            buglog.debug("Ritual leave check", f"count {got}, "                                          # why
                                               f"reminder {'on' if rc.get('leave_reminder', True) else 'off'}")
        # only when you started them (2.15.0: 0 done = you chose to skip Ritual in this map)
        if left and rc.get("on") and rc.get("leave_reminder", True) and got and 0 < got[0] < got[1]:
            self.root.after(9000 if cfg.get("on") and cfg.get("pending") else 0,
                            lambda g=got: self.breach_alert(level="ritual", sub=f"{g[0]} of {g[1]} done - go back "
                                                                                 f"through your portal"))
        try:
            self.mp_area(kind, before, where, left)          # 2.132.0: Map profit - a map's before / after
        except Exception:
            self.log_error("Map profit")
        if left:                                             # Owner decision: back from a map - one card for Top Up
            try:                                             # and Map profit (one Read Key press counts the map's
                self.back_card(self.mp_map_name(getattr(self, "rt_where", None)))    # loot and checks your top ups)
            except Exception:
                self.log_error("the Back from a map card")
        elif kind != before:
            self.back_card_close()                           # (you moved on: the card goes)
        if kind in ("hideout", "town") and before != kind:
            self.break_check()                               # 2.131.0: break reminders - in hideout / town only
        if kind == "map" and before != "map":
            # a new map: its own count. 2.40.0: back into the SAME map (same area and seed - through your portal)
            # keeps it, so a quick in-and-out still reminds you
            if where is None or where != getattr(self, "rt_where", None):
                self.rt_map = None
                self.rt_log = {"starts": 0, "disrupted": 0, "last": 0.0}   # (GGG policy: the log's rituals, this map)
                self.rt_base = (0, 0)
                self.rid_told = None                   # 2.132.6: a new map's altars get their cards again
                from .ritual_alert import STATE as RITUAL
                RITUAL.tribute = None                  # 2.131.6: a new map - its own tribute
            self.rt_where = where
        try:
            self.overlay_capture_sync()                  # (in / out of captures follows where you are now)
        except Exception:
            buglog.caught()

    # ================================================================ Breach: the banner
    def breach_alert(self, text="Stored Hiveblood is almost at the maximum!", test=False, level=None, sub=None):
        self.alerts_init()
        from . import features as FEAT
        if not test and not FEAT.on("overlay"):           # 2.131.0: the Game Overlay is off (Features)
            return
        level = level or breach_level(text)
        now = time.time()
        if not test:
            if level not in ("leave", "ritual") and now - self.br_last.get(level, 0) < REPEAT_SECS:
                return
            try:
                from .overlaywin import foreground_ok        # only over the game (Settings: "only while it's in front")
                if not foreground_ok():
                    # 2.129.3 (feedback: left a map at 2 of 3, no reminder): a reminder waits (up to a minute) for
                    # the game to be in front again - a screenshot tool or another window had it
                    tries = getattr(self, "_alert_wait", {}).get(level, 0)
                    if level in ("leave", "ritual") and tries < 60:
                        self.__dict__.setdefault("_alert_wait", {})[level] = tries + 1
                        self.root.after(1000, lambda: self.breach_alert(text, level=level, sub=sub))
                    else:
                        getattr(self, "_alert_wait", {}).pop(level, None)
                        buglog.debug("alert not shown", f"{level}: the game wasn't the window in front")
                    return
                getattr(self, "_alert_wait", {}).pop(level, None)
            except Exception:
                buglog.caught()
        self.br_last[level] = now
        if level == "full":
            self.br_last["almost"] = now                     # "almost" right after "full" adds nothing
        self.breach_dismiss()
        title, small_txt, mark, color = LEVELS[level]
        small_txt = sub or small_txt
        from . import alertcard
        win = alertcard.show(self.root, title, small_txt, color=color, mark=mark,
                             secs=5 if test else BANNER_SECS.get(level, 8), game=game_rect(),
                             tag="Ritual" if level == "ritual" else "Breach",
                             rank=0 if level == "ritual" else 1, vital=True, on_close=lambda: self.br_win is win and self.breach_dismiss())
        self.br_win, self.br_level = win, level
        if (self.ritual_cfg() if level == "ritual" else self.breach_cfg()).get("sound", True):
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND if level == "full" else winsound.MB_ICONEXCLAMATION)
            except Exception:
                self.root.bell()
        self.alerts_refresh()
        self.alerts_overlay_redraw()

    # ---------------------------------------------------------------- 2.131.0 break reminders
    def break_played(self):
        """Seconds played: the Session timer's when it runs, otherwise since this app run's first area."""
        s = getattr(self, "tk_session", None)
        if s is not None and not getattr(s, "ended", False):
            try:
                return float(s.elapsed())
            except Exception:
                buglog.caught()
        start = self.__dict__.setdefault("_play_start", time.time())
        return time.time() - start

    def break_check(self, force=False):
        from . import breaks as BR
        c = BR.cfg()
        if not force and not c.get("on"):                     # (its one switch: Overlay › Helpers)
            return None
        played = self.break_played()
        st = self.__dict__.setdefault("_break", {"last": 0.0, "n": 0})
        if not force and not BR.due(played, st["last"], c["every"]):
            return None
        line, st["n"] = BR.next_line(played / 3600.0, st["n"])
        st["last"] = played
        from . import alertcard
        try:
            from .overlaywin import foreground_ok
            if not force and not foreground_ok():
                st["last"] = played - c["every"] * 60     # (not in front: the next hideout / town visit)
                return None
        except Exception:
            buglog.caught()
        self.break_win = alertcard.show(self.root, line, BR.played_text(played), color="#7fd9a0", mark="♥", secs=10,
                                        game=game_rect(), tag="Breaks", rank=4)
        return line

    def break_set(self, key, value):
        from . import breaks as BR
        BR.cfg()[key] = value
        save_json("settings.json", SETTINGS)
        if key == "on" and value:
            self.__dict__["_break"] = {"last": self.break_played(), "n": 0}     # (counted from now)

    def alert_card_test(self):
        """Settings: a sample card where and how big alerts will show."""
        self.breach_alert(test=True, level="ritual", sub="A sample - this is where alerts show")

    def alert_card_set(self, key, value):
        from . import alertcard
        alertcard.cfg()[key] = value
        save_json("settings.json", SETTINGS)
        self.alert_card_test()

    def breach_dismiss(self):
        w, self.br_win = getattr(self, "br_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass
            self.alerts_refresh()

    def breach_status(self):
        """False = off, True = watching, "warn" = a banner is up or Client.txt isn't found."""
        if not self.breach_cfg().get("on"):
            return False
        if getattr(self, "br_win", None) is not None or getattr(self, "br_reader", None) is None:
            return "warn"
        return True
