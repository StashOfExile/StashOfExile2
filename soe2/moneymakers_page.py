"""Farming Strategies (2.28.0 Money Makers): community strats in one standard layout and the Strat Tracker.
3.0.6 (the approved mockups): Find - a search box, one-line filters (League first), a row per strat, Quick tips
folded at the bottom - an opened strat (its numbers, what you need, how it goes) and New strat (stratnew.py); all
drawn on canvases (stratview.py). Data and the layout check live in moneymakers.py."""
import json
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

from . import buglog
from . import board as B
from . import moneymakers as MM
from .config import SETTINGS, save_json
from .style import over_app
from .style import C, SegBar, Tooltip, menu_popup
from .chrome import section as chrome_section
from .stratview import StratViews, scroller
from .stratnew import StratNewPage

ORIGIN = {"community": "Official", "mine": "Mine", "example": "Example", "board": "Community"}
VIEWS = ("All", "Official", "Community", "Mine")             # 3.0.6: All by default (yours show with the rest)
CARD_SORT = {"Most profit per hour": ("profit", True), "Most upvoted": ("score", True),
             "Easiest first": ("thoughts_per_click", False), "Name, A to Z": ("name", False)}
# 2.71.0: the Sort. 3.0.6 (the sort names were unclear): each choice says what it orders by,
# and the button reads "Sort by: <choice>"
SORT_OLD = {"Per hour": "Most profit per hour", "Profit": "Most profit per hour", "Upvotes": "Most upvoted",
            "Easiest": "Easiest first", "Name": "Name, A to Z"}
TABS = ("Find", "Strat Tracker")                              # 3.0.6: Find (was Strats); Quick tips fold into it


def _hms(secs):
    secs = int(max(0, secs))
    h, rest = divmod(secs, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class MoneyMakersPage(StratViews, StratNewPage):
    """Mixed into App."""

    def build_money_window(self, body):
        P1 = C["panel"]
        self.mm_strats, self.mm_sel, self.mm_sort = [], None, ("profit", True)     # 2.71.0: best first
        self.mm_page = SegBar(body, list(TABS), command=lambda v: self.mm_show_page(), size=10, pad=(16, 4))
        self.mm_page.pack(anchor="w", padx=8, pady=(8, 0))
        if getattr(self, "shell", None) is not None:          # 2.64.0: its tabs are listed in the sidebar
            self.shell.register_tabs("money", self.mm_page)
        self.mm_pages = {name: tk.Frame(body, bg=P1) for name in self.mm_page.btns}
        self.mm_strat_page, self.mm_run_page = self.mm_pages["Find"], self.mm_pages["Strat Tracker"]
        self.mm_build_strats(self.mm_strat_page)
        self.build_ledger(self.mm_run_page)                  # 2.45.0: Strat Tracker (was Run tracker: ledger_page.py)
        self.mm_strat_page.pack(fill="both", expand=True)
        self.mm_reload()

    def mm_show_page(self):
        cur = self.mm_page.value
        for name, f in self.mm_pages.items():
            if name != cur:
                f.pack_forget()
        self.mm_pages[cur].pack(fill="both", expand=True)
        if cur == "Strat Tracker":
            self.fl_refresh()

    # ---------------- Find: the toolbar (real widgets: the search box first), the list on a canvas
    def mm_build_strats(self, page):
        P1 = C["panel"]
        self.mm_find_f = tk.Frame(page, bg=P1)
        self.mm_find_f.pack(fill="both", expand=True)
        bar = tk.Frame(self.mm_find_f, bg=P1, pady=12)
        bar.pack(fill="x", padx=24)
        self.mm_bar = bar
        # the filters (what they hold is unchanged: 2.71.0 / 2.78.0); 3.0.6: each is one dropdown on one line
        self.mm_q = tk.StringVar()
        self.mm_q.trace_add("write", lambda *_a: self.root.after_idle(self.mm_fill))
        self.mm_view = tk.StringVar(value="All")             # where the strats come from (2.30.0; 3.0.6: All)
        self.mm_league = tk.StringVar(value=self.mm_league_default())    # 3.0.6: your league first
        self._mm_league_touched = False
        self.mm_budget = tk.StringVar(value="Any")
        self.mm_tag, self.mm_tier = tk.StringVar(value="Any"), tk.StringVar(value="Any")
        self.mm_max, self.mm_cmax = tk.StringVar(value="Any"), tk.StringVar(value="Any")
        self.mm_cat, self.mm_type = tk.StringVar(value=""), tk.StringVar(value="")        # "" = all
        self.mm_content = set()                              # 2.78.0: the Content tags (pinnacles, map content)
        self.mm_csort = tk.StringVar(value="Most profit per hour")
        self.mm_bsort = tk.StringVar(value="Top")            # the community board's order
        self.mm_board, self.mm_board_ones, self.mm_official = [], [], self._mm_official_cache()
        self.mm_tips_open, self.mm_one_sel = False, None
        sbox = tk.Frame(bar, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        sbox.pack(side="left", padx=(0, 8), fill="x", expand=True)
        self.mm_sbox = sbox
        tk.Label(sbox, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        se = tk.Entry(sbox, textvariable=self.mm_q, width=38, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                      relief="flat", highlightthickness=0, bd=0, font=("Segoe UI", 10))
        se.pack(side="left", padx=8, ipady=8, fill="x", expand=True)
        self.mm_search = se
        ph = tk.Label(sbox, text="Search strats, e.g. breach", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 10))
        ph.bind("<Button-1>", lambda e: se.focus_set())

        def placeholder(*_a):
            try:
                if self.mm_q.get() or self.root.focus_get() is se:
                    ph.place_forget()
                else:
                    ph.place(in_=se, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            se.bind(ev, placeholder, add="+")
        self.mm_q.trace_add("write", placeholder)
        se.after(300, placeholder)                           # (gone with the box)
        self.mm_drops = {}
        for key, tip in (("league", "Your league's strats, or All leagues."),       # 3.0.6: short (owner)
                         ("budget", "What a strat costs to start."),
                         ("effort", "How much thinking a strat needs."),
                         ("type", "Mapping or Bossing, and its mechanic."),
                         ("from", "Official, Community, Mine - or All."),
                         ("more", "Clicks per hour, content, waystone tier, tag."),
                         ("filters", "Every filter and the sort.")):
            self.mm_drops[key] = self._mm_drop(bar, key, tip)
        self.mm_live_lbl = tk.Label(bar, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9))
        dots = tk.Label(bar, text="⋯", bg=P1, fg=C["text"], font=("Segoe UI", 12, "bold"), padx=8, pady=8,
                        cursor="hand2", highlightthickness=1, highlightbackground=C["line"])
        dots.bind("<Button-1>", lambda e: self.mm_more_menu(dots))
        Tooltip(dots, "Refresh, Import file…, community name")
        self.mm_dots = dots
        self.mm_add_btn = self._mm_ghost(bar, "＋ New strat", self.mm_add)
        Tooltip(self.mm_add_btn, "Write down how you farm.")
        self.mm_drops["sort"] = self._mm_drop(bar, "sort", "The order of the list.")
        for w, side, padx in ((self.mm_drops["league"], "left", (0, 8)),
                              (self.mm_drops["budget"], "left", (0, 8)), (self.mm_drops["effort"], "left", (0, 8)),
                              (self.mm_drops["type"], "left", (0, 8)), (self.mm_drops["from"], "left", (0, 8)),
                              (self.mm_drops["more"], "left", (0, 8)), (self.mm_drops["filters"], "left", (0, 0)),
                              (dots, "right", (8, 0)), (self.mm_add_btn, "right", (8, 0)),
                              (self.mm_drops["sort"], "right", (8, 0)), (self.mm_live_lbl, "right", (8, 0))):
            w.pack(side=side, padx=padx)
        from .style import flowify
        flowify(bar)                                         # (wraps in a narrow window, search stays first)
        cf, self.mm_find_cv = scroller(self.mm_find_f, self, self._mm_draw_find, P1)
        cf.pack(fill="both", expand=True)
        # an opened strat: its own canvas (‹ All strats goes back)
        self.mm_open_f, self.mm_detail_cv = scroller(page, self, self._mm_draw_detail, P1)
        self.mm_detail_cv.bind("<Escape>", lambda e: self.mm_close())
        self.mm_detail_on = False
        # 3.0.6: New strat (stratnew.py) - its own canvas too (‹ All strats / Cancel go back)
        self.mm_new_f, self.mm_new_cv = scroller(page, self, self._mm_draw_new, P1)
        self.mm_new_on = False
        self._art_hooks = getattr(self, "_art_hooks", []) + [self._mm_art_came]
        self._drawer_look_hooks = getattr(self, "_drawer_look_hooks", []) + [self.mm_drawer_look]
        self.mm_drawer_look(None)
        self.mm_account_paint()

    def _mm_ghost(self, parent, text, cmd):
        """A secondary (outlined) button for the toolbar. (Its hover edge goes back to b._edge - the dropdowns set it -
        and its bindings are added, never replaced: replacing <Leave> took the tooltip's away, and every tip stayed.)"""
        b = tk.Label(parent, text=text, bg=C["panel"], fg=C["text"], font=("Segoe UI", 10), padx=12, pady=8,
                     cursor="hand2", highlightthickness=1, highlightbackground=C["line"])
        b._edge = C["line"]
        b.bind("<Button-1>", lambda e: cmd(), add="+")
        b.bind("<Enter>", lambda e: b.config(highlightbackground=C["muted"]), add="+")
        b.bind("<Leave>", lambda e: b.config(highlightbackground=getattr(b, "_edge", C["line"])), add="+")
        return b

    def _mm_drop(self, parent, key, tip):
        b = self._mm_ghost(parent, "", lambda: self.mm_drop_menu(key))
        b._key = key
        Tooltip(b, tip)
        return b

    def _mm_art_came(self, done):
        for cv in (getattr(self, "mm_find_cv", None), getattr(self, "mm_detail_cv", None),
                   getattr(self, "mm_new_cv", None)):
            if cv is not None and cv.want & set(done):
                cv.want -= set(done)
                cv.later()

    def mm_drawer_look(self, _on):
        """The Drawer (or a narrow window): the search box and Filters ▾ only; the Full window: every dropdown."""
        bar = getattr(self, "mm_bar", None)
        if bar is None:
            return
        narrow = self.mm_narrow()
        from .style import flow_show
        for key, w in self.mm_drops.items():
            flow_show(bar, w, (key == "filters") == narrow)
        for w in (self.mm_dots, self.mm_live_lbl):
            flow_show(bar, w, not narrow)
        flow_show(bar, self.mm_add_btn, True)            # 3.0.6 (owner): New strat stays its own button in the Drawer
        for k in getattr(bar, "_flow_kids", ()):
            if k["w"] is self.mm_sbox:
                k["grow"] = narrow                       # the Drawer: the search takes the line
        try:
            bar.pack_configure(padx=16 if narrow else 24)
        except tk.TclError:
            pass
        self.mm_drops_paint()
        for cv in (getattr(self, "mm_find_cv", None), getattr(self, "mm_detail_cv", None),
                   getattr(self, "mm_new_cv", None)):
            if cv is not None:
                cv.later()

    # ---------------- the dropdowns
    def mm_type_word(self):
        return self.mm_type.get() or self.mm_cat.get() or "All"

    def mm_more_count(self):
        return (self.mm_cmax.get() != "Any") + len(self.mm_content) + (self.mm_tier.get() != "Any") + \
            (self.mm_tag.get() != "Any")

    # ---------------- 3.0.6: the League filter (first): your league from Settings, or All leagues
    def mm_league_default(self):
        """Your league (its trade, hardcore and SSF sides are one), or All leagues when none is set."""
        return MM.league_base(SETTINGS.get("league")) or MM.ALL_LEAGUES

    def mm_league_set(self, value):
        self._mm_league_touched = True
        self.mm_league.set(value)
        self.mm_filters_changed()

    def mm_filters_on_but_league(self):
        return bool(self.mm_budget.get() != "Any" or self.mm_max.get() != "Any" or self.mm_cat.get()
                    or self.mm_more_count() or self.mm_q.get().strip())

    def mm_league_off(self):
        """The League filter is set away from your league (Clear filters puts it back)."""
        return self.mm_league.get() != self.mm_league_default()

    def mm_filters_on(self):
        return bool(self.mm_budget.get() != "Any" or self.mm_max.get() != "Any" or self.mm_cat.get()
                    or self.mm_more_count() or self.mm_q.get().strip() or self.mm_league_off())

    def mm_filter_words(self):
        """What the filters show, in a few words (FORBIDDEN RITES · MID BUDGET)."""
        out = [w for w in (self.mm_league.get(), self.mm_budget.get(), self.mm_max.get(),
                           self.mm_type.get() or self.mm_cat.get()) if w and w not in ("Any", MM.ALL_LEAGUES)]
        n = self.mm_more_count()
        if n:
            out.append(f"{n} more")
        if self.mm_q.get().strip():
            out.append(f"“{self.mm_q.get().strip()}”")
        return " · ".join(out)

    def mm_drops_paint(self):
        """Each dropdown says what it is set to; one that filters has the accent edge and its value in bold."""
        d = getattr(self, "mm_drops", None)
        if not d:
            return
        lg = self.mm_league.get()
        n_on = sum((self.mm_budget.get() != "Any", self.mm_max.get() != "Any", bool(self.mm_cat.get()),
                    self.mm_view.get() != "All", lg != MM.ALL_LEAGUES)) + self.mm_more_count()
        n_more = self.mm_more_count()
        texts = {"league": ("League", lg, lg != MM.ALL_LEAGUES),
                 "budget": ("Budget", self.mm_budget.get(), self.mm_budget.get() != "Any"),
                 "effort": ("Effort", self.mm_max.get(), self.mm_max.get() != "Any"),
                 "type": ("Type", self.mm_type_word(), bool(self.mm_cat.get())),
                 "from": ("From", self.mm_view.get(), self.mm_view.get() != "All"),
                 "more": ("More", f"{n_more} on" if n_more else "", bool(n_more)),
                 "filters": ("Filters", f"· {n_on}" if n_on else "", bool(n_on)),
                 "sort": ("Sort by", self.mm_csort.get(), False)}
        for key, (name, val, on) in texts.items():
            b = d.get(key)
            if b is None:
                continue
            try:
                b._edge = C["accent"] if on else C["line"]
                b.config(text=f"{name}{':' if val and not val.startswith('·') and key not in ('more',) else ''}"
                              f"{' ' + val if val else ''}  ▾",
                         font=("Segoe UI", 10, "bold" if on else "normal"), highlightbackground=b._edge,
                         fg=C["text"])
            except tk.TclError:
                pass

    def _mm_menu(self):
        return tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84",
                       selectcolor=C["accent"])

    def mm_drop_menu(self, key, at=None):
        """A dropdown's menu (radio items: the picked one has its mark). No tooltip while it's open."""
        m = self._mm_menu()
        self._mm_fill_menu(m, key)
        b = at or self.mm_drops.get(key)
        self.mm_last_menu = m
        try:
            menu_popup(m, b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        except (AttributeError, tk.TclError):
            pass
        return m

    def _mm_count(self, pred):
        return sum(1 for s in self.mm_strats if pred(s))

    def _mm_fill_menu(self, m, key):
        go = self.mm_filters_changed
        if key == "league":                              # (the counts: what each choice would show, other filters on)
            rows = self.mm_rows(league=MM.ALL_LEAGUES)
            have = {}
            for s in rows:
                have[MM.league_of(s)] = have.get(MM.league_of(s), 0) + 1
            mine = self.mm_league_default()
            m.add_radiobutton(label=f"{MM.ALL_LEAGUES}  ({len(rows)})", variable=self.mm_league,
                              value=MM.ALL_LEAGUES, command=lambda: self.mm_league_set(MM.ALL_LEAGUES))
            m.add_separator()
            names = ([mine] if mine != MM.ALL_LEAGUES else []) + sorted(x for x in have if x != mine)
            for lg in names:
                label = MM.league_text(lg) + ("  (yours)" if lg == mine else "") + f"  ({have.get(lg, 0)})"
                m.add_radiobutton(label=label, variable=self.mm_league, value=lg,
                                  command=lambda lg=lg: self.mm_league_set(lg))
        elif key == "budget":
            m.add_radiobutton(label="Any", variable=self.mm_budget, value="Any", command=go)
            for b in MM.BUDGETS:
                n = self._mm_count(lambda s, b=b: b in (s.get("tags") or []))
                m.add_radiobutton(label=f"{b}  ({n})", variable=self.mm_budget, value=b, command=go)
        elif key == "effort":
            m.add_radiobutton(label="Any", variable=self.mm_max, value="Any", command=go)
            for k, (w, d) in MM.THINKING.items():
                m.add_radiobutton(label=f"{w} or easier - {d}", variable=self.mm_max, value=w, command=go)
        elif key == "type":
            m.add_command(label=("✓ " if not self.mm_cat.get() else "    ") + f"All  ({len(self.mm_strats)})",
                          command=lambda: self.mm_filter(""))
            m.add_separator()
            for c in MM.CATEGORIES:
                sub = self._mm_menu()
                n = self._mm_count(lambda s, c=c: s.get("category") == c)
                on = self.mm_cat.get() == c and not self.mm_type.get()
                sub.add_command(label=("✓ " if on else "    ") + f"All {c}  ({n})", command=lambda c=c: self.mm_filter(c))
                sub.add_separator()
                for t in MM.TAXONOMY.get(c, ()):
                    k = self._mm_count(lambda s, c=c, t=t: s.get("category") == c and s.get("type") == t)
                    sub.add_command(label=("✓ " if self.mm_type.get() == t and self.mm_cat.get() == c else "    ")
                                    + (f"{t}  ({k})" if k else t), command=lambda c=c, t=t: self.mm_filter(c, t))
                m.add_cascade(label=("✓ " if self.mm_cat.get() == c else "    ") + (f"{c}  ({n})" if n else c), menu=sub)
        elif key == "from":
            for v in VIEWS:
                m.add_radiobutton(label=v, variable=self.mm_view, value=v, command=self.mm_view_changed)
            if self.mm_view.get() == "Community":
                m.add_separator()
                for v in ("Top", "New"):
                    m.add_radiobutton(label=f"Board order: {v}", variable=self.mm_bsort, value=v,
                                      command=self.mm_board_fetch)
        elif key == "sort":
            for v in CARD_SORT:
                m.add_radiobutton(label=v, variable=self.mm_csort, value=v, command=self.mm_sort_card)
        elif key == "more":
            cl = self._mm_menu()
            cl.add_radiobutton(label="Any", variable=self.mm_cmax, value="Any", command=go)
            for w, d in MM.CLICKS.items():
                cl.add_radiobutton(label=f"{w} or calmer - {d}", variable=self.mm_cmax, value=w, command=go)
            m.add_cascade(label="Clicks per hour" + (f": {self.mm_cmax.get()}" if self.mm_cmax.get() != "Any" else ""),
                          menu=cl)
            self.mm_content_vars = {}
            for group, tags in MM.content_groups().items():
                sub = self._mm_menu()
                sub.add_command(label="Any (clear)", command=lambda: self.mm_content_pick(None))
                for t in tags:
                    v = tk.BooleanVar(value=t in self.mm_content)
                    self.mm_content_vars[t] = v
                    sub.add_checkbutton(label=t, variable=v, command=lambda t=t: self.mm_content_pick(t))
                n = len(self.mm_content & set(tags))
                m.add_cascade(label=group + (f": {n} picked" if n else ""), menu=sub)
            ti = self._mm_menu()
            for v in ("Any",) + tuple(str(i) for i in range(1, 17)):
                ti.add_radiobutton(label=v if v == "Any" else f"T{v}", variable=self.mm_tier, value=v, command=go)
            m.add_cascade(label="Waystone tier" + (f": T{self.mm_tier.get()}" if self.mm_tier.get() != "Any" else ""),
                          menu=ti)
            tg = self._mm_menu()
            tg.add_radiobutton(label="Any", variable=self.mm_tag, value="Any", command=go)
            for group, tags in MM.TAG_GROUPS.items():
                if group == "Budget":
                    continue                                 # (Budget is its own dropdown)
                sub = self._mm_menu()
                for t in tags:
                    sub.add_radiobutton(label=t, variable=self.mm_tag, value=t, command=go)
                tg.add_cascade(label=group, menu=sub)
            m.add_cascade(label="Tag" + (f": {self.mm_tag.get()}" if self.mm_tag.get() != "Any" else ""), menu=tg)
        elif key == "filters":                               # the Drawer: everything in one menu
            for k, name in (("league", f"League: {self.mm_league.get()}"),
                            ("budget", f"Budget: {self.mm_budget.get()}"), ("effort", f"Effort: {self.mm_max.get()}"),
                            ("type", f"Type: {self.mm_type_word()}"), ("from", f"From: {self.mm_view.get()}"),
                            ("more", "More" + (f": {self.mm_more_count()} on" if self.mm_more_count() else "")),
                            ("sort", f"Sort by: {self.mm_csort.get()}")):
                sub = self._mm_menu()
                self._mm_fill_menu(sub, k)
                m.add_cascade(label=name, menu=sub)
            m.add_separator()
            if self.mm_filters_on():
                m.add_command(label="Clear filters", command=self.mm_clear_filters)
            m.add_command(label="↻ Refresh", command=self.mm_refresh)
            m.add_command(label="Import file…", command=self.mm_import)
        return m

    def mm_filters_changed(self):
        self.mm_drops_paint()
        self.mm_fill()

    def mm_clear_filters(self):
        for v in (self.mm_budget, self.mm_max, self.mm_cmax, self.mm_tier, self.mm_tag):
            v.set("Any")
        self.mm_cat.set("")
        self.mm_type.set("")
        self.mm_content = set()
        self.mm_q.set("")
        self.mm_league.set(self.mm_league_default())
        self._mm_league_touched = False
        self.mm_filters_changed()

    def mm_content_pick(self, tag):
        """A Content tag: on / off (None: Any - all off)."""
        if tag is None:
            self.mm_content = set()
        else:
            self.mm_content ^= {tag}
        self.mm_filters_changed()

    def mm_filter(self, cat, typ=""):
        """The Type dropdown: a category (and a type in it); "" = all."""
        self.mm_cat.set(cat)
        self.mm_type.set(typ if cat else "")
        self.mm_filters_changed()

    def mm_sort_card(self):
        key, rev = CARD_SORT.get(SORT_OLD.get(self.mm_csort.get(), self.mm_csort.get()), ("profit", True))
        self.mm_sort = (key, rev)
        self.mm_filters_changed()

    def mm_view_set(self, view):
        self.mm_view.set(view)
        self.mm_view_changed()

    # ---------------- your Strat Tracker numbers for a strat
    def _mm_setups_by_strat(self):
        try:
            d = self.fl_data()
        except Exception:
            return {}, {"logs": []}
        by = {}
        for x in d.get("setups", []):
            if x.get("strat"):
                by.setdefault(x["strat"], set()).add(x["id"])
        return by, d

    def _mm_my_numbers_all(self):
        """strat id -> your Strat Tracker figures for it (every setup that follows it)."""
        from . import ledger as L
        by, d = self._mm_setups_by_strat()
        return {sid: L.figures([l for l in d["logs"] if l["setup"] in ids]) for sid, ids in by.items()}

    def _mm_my_loot(self, sid):
        """What your logs for this strat dropped, by item, with each one's share (ledger.loot_table)."""
        from . import ledger as L
        by, d = self._mm_setups_by_strat()
        ids = by.get(sid)
        if not ids:
            return []
        try:
            rows = L.loot_table([l for l in d["logs"] if l["setup"] in ids])
        except Exception:
            buglog.caught()
            return []
        return [g for g in rows if g.get("total", 0) > 0]

    # ---------------- 2.30.0: Official / Community / Mine
    def _mm_official_cache(self):
        from .config import load_json
        d = load_json("board_official.json", {})
        return d if isinstance(d, dict) else {}

    def mm_view_list(self):
        """The strats of From: Official (with the app and promoted), Community (the board), Mine - or All of them
        (3.0.6, the default: each row says where it comes from)."""
        view = self.mm_view.get()
        board = list(self.mm_board) if B.configured() else []
        if view == "Community":
            return board
        local = MM.all_strats()
        if view == "Mine":
            return [s for s in local if s["origin"] == "mine"]
        have = {s["id"] for s in local}
        promoted = [dict(MM.migrate(s), origin="community") for s in self.mm_official.get("strats") or []
                    if not MM.validate(MM.migrate(s)) and s.get("id") not in have]
        official = [s for s in local if s["origin"] != "mine"] + promoted
        if view != "All":
            return official
        seen = {s["id"] for s in official}
        mine = [s for s in local if s["origin"] == "mine"]
        return official + [p for p in board if p.get("id") not in seen and not (p.get("_post") or {}).get("promoted")] \
            + mine

    def mm_view_changed(self):
        if self.mm_view.get() in ("Community", "All"):
            self.mm_board_fetch()
        self.mm_sel = None
        self.mm_one_sel = None
        self.mm_drops_paint()
        self.mm_reload()

    def mm_reload(self, keep=None):
        self.mm_strats = self.mm_view_list()
        self.mm_fill(keep)

    def mm_rows(self, league=None):
        """The strats the search and filters show (league: count for that League choice instead). 3.0.6: farming
        strats only - one of a dropped category stays on disk, out of Find."""
        q = self.mm_q.get().strip().lower()
        cat, typ, tag, tier = self.mm_cat.get(), self.mm_type.get(), self.mm_tag.get(), self.mm_tier.get()
        budget = self.mm_budget.get()
        league = league or self.mm_league.get()
        words = {w: k for k, (w, _d) in MM.THINKING.items()}
        mx = words.get(self.mm_max.get(), 5)
        bands = list(MM.CLICKS)
        cmax = bands.index(self.mm_cmax.get()) if self.mm_cmax.get() in bands else len(bands)
        out = []
        for s in self.mm_strats:
            if not MM.is_farming(s):
                continue
            if league != MM.ALL_LEAGUES and MM.league_of(s) != league:
                continue
            if cat and s.get("category") != cat:
                continue
            if typ and s.get("type") != typ:
                continue
            if budget != "Any" and budget not in (s.get("tags") or []):
                continue
            if tag != "Any" and tag not in (s.get("tags") or []) and tag != s.get("type"):
                continue
            if self.mm_content and not self.mm_content & set(s.get("tags") or []):
                continue
            wt = s.get("waystone_tiers")
            if tier != "Any" and wt and not wt["min"] <= int(tier) <= wt["max"]:
                continue
            if s.get("thoughts_per_click", 5) > mx:
                continue
            if s.get("clicks_per_hour") in bands and bands.index(s["clicks_per_hour"]) > cmax:
                continue
            if q and q not in json.dumps(s, ensure_ascii=False).lower():
                continue
            out.append(s)
        key, rev = self.mm_sort
        num = key in ("thoughts_per_click", "profit", "score")

        def k(s):
            if key == "score":
                return (s.get("_post") or {}).get("score", -1)
            if key == "profit":                             # 2.85.0: in divines (ex / chaos converted); 0 is 0
                v = MM.div_value(s.get("est_profit"))
                return v if v is not None else float("-inf")
            return s.get(key, 0) if num else str(s.get(key, "")).lower()
        return sorted(out, key=k, reverse=rev)

    def mm_fill(self, keep=None):
        """The strats the search and filters show: the best for you first (the most an hour), then the rest in the
        Sort's order. An opened strat stays open (redrawn) while it is still in the list."""
        mine = self._mm_my_numbers_all()
        costs = self.mm_costs()
        rows = []
        for s in self.mm_rows():
            m = mine.get(s["id"])
            rows.append({"key": s["id"] + "|" + s["origin"], "s": s, "mine": m, "ph": MM.per_hour(s, m),
                         "cost": MM.run_cost(s, costs)})
        if rows:
            best = max(rows, key=lambda r: r["ph"]["value"] if r["ph"] else float("-inf"))
            rows.remove(best)
            rows.insert(0, best)
        self.mm_find_rows = rows
        keys = {r["key"] for r in rows} | {s["id"] + "|" + s["origin"] for s in self.mm_strats}
        keep = keep or (self.mm_sel if getattr(self, "mm_detail_on", False) else None)
        self.mm_drops_paint()
        if keep and keep in keys:
            self.mm_open(keep)
        elif getattr(self, "mm_detail_on", False):
            self.mm_close()
        cv = getattr(self, "mm_find_cv", None)
        if cv is not None:
            cv.later(10)

    def mm_current(self):
        if not self.mm_sel:
            return None
        return next((s for s in self.mm_strats if s["id"] + "|" + s["origin"] == self.mm_sel), None)

    # ---------------- an opened strat
    def mm_open(self, key):
        """Open a strat (Find hides; ‹ All strats comes back)."""
        if not key:
            return None
        self.mm_sel = key
        if not self.mm_detail_on:
            self.mm_detail_on = True
            self.mm_detail_cv.yview_moveto(0)
            self._mm_frames()                            # (New strat stays in front while it's open)
        self.mm_detail_cv.later(10)
        try:
            self.mm_detail_cv.focus_set()
        except tk.TclError:
            pass
        return self.mm_current()

    def mm_close(self):
        """‹ All strats."""
        self.mm_detail_on = False
        self.mm_sel = None
        self._mm_frames()

    def mm_select(self, key):
        return self.mm_open(key)

    def mm_show_detail(self, s=None):
        """Redraw the opened strat (its cost was checked, its picture came...)."""
        if getattr(self, "mm_detail_on", False):
            self.mm_detail_cv.later(10)
        cv = getattr(self, "mm_find_cv", None)
        if cv is not None:
            cv.later(40)

    def mm_run(self, key):
        """Run this strat (the one orange button): the Strat Tracker on it (a setup is made if there's none)."""
        if key:
            self.mm_sel = key
        return self.mm_track()

    def mm_row_menu(self, key, x, y):
        """Right-click a strat: everything you can do with it (the same menu as More ▾)."""
        self.mm_sel = key                                    # (Find: not opened - mm_detail_on says what is)
        return self.mm_menu(None, x, y)

    def mm_more_at(self, tag):
        x, y = self.mm_detail_cv.at_root(tag)
        return self.mm_menu(None, x, y)

    def mm_item_menu(self, it, tag):
        """An In your map device slot: copy its stash search, or open the Trade Site on it."""
        rx = MM.item_regex([it])
        m = self._mm_menu()
        name = it.get("name") or it.get("base")
        m.add_command(label="Copy its stash search (regex)", command=lambda: self.mm_item_copy(rx, name),
                      state="normal" if rx else "disabled")
        m.add_command(label="Trade Site ↗ (cheapest first)", command=lambda: self.mm_item_trade(it))
        x, y = self.mm_detail_cv.at_root(tag)
        try:
            m.tk_popup(x, y)
        except tk.TclError:
            pass
        self.mm_last_menu = m
        return m

    # ---------------- 2.78.0: W - what a strat needs (You need), a regex and a trade search for each item
    def mm_item_copy(self, rx, what):
        if not rx:
            return None
        self.root.clipboard_clear()
        self.root.clipboard_append(rx)
        self.own_clip = rx
        self._say(f"Copied the search for {what}. In game: Ctrl+V in the stash search.", 6)
        return rx

    def mm_item_trade(self, it):
        url = MM.item_trade_link(SETTINGS.get("league"), it)
        webbrowser.open(url)
        return url

    # ---------------- 2.78.0: the atlas - the author's screenshot (click: see it big)
    def mm_board_image(self, ref, s):
        """A board image: kept on this PC after the first download (in the background; the panel redraws)."""
        from . import stratimg
        import os
        p = os.path.join(stratimg.folder(), f"board_{ref[2:]}.jpg")
        if os.path.isfile(p):
            return p
        busy = getattr(self, "_mm_img_busy", set())
        if ref not in busy:
            self._mm_img_busy = busy | {ref}

            def done(path):
                self._mm_img_busy = getattr(self, "_mm_img_busy", set()) - {ref}
                cur = self.mm_current()
                if path and cur and cur.get("atlas_image") == ref:
                    self.mm_show_detail(cur)
            self._mm_bg(lambda: stratimg.path_of(ref), done)
        return None

    def mm_atlas_big(self, path):
        """The screenshot in its own window, as big as the screen allows."""
        try:
            from PIL import Image, ImageTk
            im = Image.open(path)
        except Exception:
            return None
        w = tk.Toplevel(self.root)
        over_app(w, self.dlg_parent())               # 2.114.3: over the app, on its monitor
        w.title("Atlas")
        w.configure(bg=C["bg"])
        sw, sh = int(self.root.winfo_screenwidth() * 0.9), int(self.root.winfo_screenheight() * 0.85)
        im.thumbnail((sw, sh))
        img = ImageTk.PhotoImage(im, master=self.root)
        lbl = tk.Label(w, image=img, bg=C["bg"])
        lbl.image = img
        lbl.pack()
        w.bind("<Escape>", lambda e: w.destroy())
        lbl.bind("<Button-1>", lambda e: w.destroy())
        self.mm_atlas_win = w
        return w

    def mm_menu(self, e=None, x=None, y=None):
        """More ▾ on an opened strat, or a right-click on one: everything you can do with it."""
        if e is not None:
            x, y = e.x_root, e.y_root
        s = self.mm_current()
        if not s:
            return None
        post, me = s.get("_post") or {}, B.signed_in() or {}
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        if not getattr(self, "mm_detail_on", False):
            m.add_command(label="Open", command=lambda k=self.mm_sel: self.mm_open(k))
        m.add_command(label="Run this strat", command=self.mm_track)
        if s.get("regex"):
            m.add_command(label="Copy regex", command=self.mm_copy_regex)
        if post:
            m.add_command(label="▲ Remove my upvote" if post.get("voted") else "▲ Upvote", command=self.mm_vote)
        if s["origin"] == "mine":
            m.add_command(label="📤 Post to Community", command=self.mm_post)
        else:
            m.add_command(label="Copy to Mine (to change it)", command=self.mm_copy_mine)
        if post and not post.get("mine"):                          # 2.85.0
            m.add_command(label="✎ Suggest an edit…", command=self.mm_suggest)
        if post:
            m.add_command(label="History…", command=self.bm_history)
        if post.get("mine") and post.get("suggestions"):
            m.add_command(label=f"Suggestions waiting ({post['suggestions']})…", command=self.bm_inbox)
        m.add_command(label="Export…", command=self.mm_export)
        if s.get("items"):                                         # 2.46.0
            m.add_command(label="Check what it costs now", command=lambda: (self.mm_cost_check(True, s["id"]),
                                                                             self.mm_show_detail(s)))
        if s["origin"] == "mine" or post.get("mine"):
            m.add_separator()
            m.add_command(label="Edit", command=self.mm_edit)
            m.add_command(label="Delete", command=self.mm_delete)
        if post and not post.get("mine"):
            m.add_separator()
            m.add_command(label="⚑ Report…", command=self.mm_report)
        if post and me.get("admin"):
            m.add_separator()
            m.add_command(label="Admin: " + ("Un-hide" if post.get("hidden") else "Hide"),
                          command=lambda: self.mm_admin("unhide" if post.get("hidden") else "hide"))
            m.add_command(label="Admin: " + ("Remove from Official" if post.get("promoted") else "Promote to Official"),
                          command=lambda: self.mm_admin("unpromote" if post.get("promoted") else "promote"))
            m.add_command(label="Admin: Delete", command=lambda: self.mm_admin("delete"))
            m.add_command(label=f"Admin: Ban {post.get('author', {}).get('name', '')}",
                          command=lambda: self.mm_admin("ban"))
        try:
            m.tk_popup(x, y)
        except tk.TclError:
            pass
        self.mm_last_menu = m
        return m

    # ---------------- the board (network work off the main thread; mm_sync = do it now, for tests)
    def _mm_bg(self, work, done):
        self.run_bg(work, done)                     # (2.117.0: done runs on the window's thread via the queue)

    def mm_refresh(self):
        self.mm_check_live(force=True)
        self.mm_board_fetch()
        self._mm_bg(B.official, self._mm_official_done)

    def _mm_official_done(self, res):
        ok, d = res
        if ok and isinstance(d, dict):
            self.mm_official = d
            save_json("board_official.json", d)
            if self.mm_view.get() in ("Official", "All"):
                self.mm_reload()
            self.mm_one_fill()

    def mm_board_fetch(self, keep=None):
        if not B.configured():
            self.mm_live_lbl.config(text="The community board isn't set up yet.", fg=C["muted"])
            return
        sort = "new" if self.mm_bsort.get() == "New" else "top"
        admin = (B.signed_in() or {}).get("admin")
        self._mm_bg(lambda: (B.posts("strat", sort, limit=100, hidden=admin), B.posts("one", sort, limit=100, hidden=admin)),
                    lambda r: self._mm_board_done(r, keep))

    def _mm_board_done(self, res, keep=None):
        (ok, d), (ok1, d1) = res
        if not ok:
            self.mm_live_lbl.config(text=d, fg=C["red"])
            return
        # 2.85.0: a post that doesn't follow the layout (an older board let odd numbers in) isn't shown
        self.mm_board = [dict(MM.migrate(dict(p["data"])), origin="board", _post=p) for p in d["posts"]
                         if p["kind"] == "strat" and not MM.validate(MM.migrate(dict(p["data"])))]
        self.mm_board_ones = [dict(p["data"], origin="board", _post=p) for p in (d1 or {}).get("posts", [])] if ok1 else []
        self.mm_live_lbl.config(text=f"Community: {d['total']} strat{'s' if d['total'] != 1 else ''}", fg=C["muted"])
        if self.mm_view.get() in ("Community", "All"):
            self.mm_reload(keep=keep)
        self.mm_one_fill()

    def mm_need_login(self, why):
        """No login: the first time you post / vote / report, pick a name and the board gives this install a key."""
        if B.signed_in():
            return False
        if not B.configured():
            self.app_toast("The community board isn't set up yet.", "Community")
            return True
        return not self.mm_join(why)

    def mm_join(self, why="use the Community board", name=None):
        from tkinter import simpledialog
        if name is None:
            from .privacy import NAME_RULE                    # 2.131.1: a made-up name, never yours in game
            name = simpledialog.askstring("Your community name", f"To {why}, pick a community name.\n\n{NAME_RULE}\n\n"
                                          "It can change once every 7 days (2-24 letters or numbers). No password - "
                                          "this PC keeps a key. More: Settings › Privacy & community.",
                                          parent=self.root)
        if not name:
            return False
        ok, d = B.join(name.strip())
        self.mm_account_paint()
        if not ok:
            self.app_toast(d, "Community")
            return False
        self._say(f"You're on the board as {d.get('name', name)}.", 6)
        return True

    def mm_board_result(self, res, done_text=None, keep=None):
        ok, d = res
        if not ok:
            self.app_toast(d, "Community")
            return False
        if done_text:
            self._say(done_text, 6)
        self.mm_board_fetch(keep=keep)
        return True

    def mm_vote(self):
        s = self.mm_current()
        post = (s or {}).get("_post")
        if not post or self.mm_need_login("upvote"):
            return None
        keep = self.mm_sel if getattr(self, "mm_detail_on", False) else None
        self._mm_bg(lambda: B.vote(post["id"], not post.get("voted")), lambda r: self.mm_board_result(r, keep=keep))

    def mm_post(self):
        s = self.mm_current()
        if not s or s["origin"] != "mine" or not self.cm_need_sharing(self.mm_post) or self.mm_need_login("post"):
            return None
        data = {k: v for k, v in MM.tidy(s).items() if k not in ("id", "author")}
        if not self.mm_atlas_check(data):                         # 2.89.3: a public picture - look first
            return None

        def work():                                               # 2.78.0: the atlas screenshot goes up first
            from . import stratimg
            if str(data.get("atlas_image", "")).startswith("l:"):
                ok, ref = stratimg.upload(data["atlas_image"])
                if not ok:
                    return False, f"The atlas screenshot didn't upload ({ref})."
                data["atlas_image"] = ref
            meta = (SETTINGS.get("mm_meta") or {}).get(s["id"]) or {}
            if meta.get("post"):                               # 2.85.0: posted before - update it, no duplicate
                res = self.mm_board_send(lambda x: B.update(meta["post"], x), data)
                if res[0] or "only its author" not in str(res[1]) and "not found" not in str(res[1]):
                    return res
            res = self.mm_board_send(lambda x: B.post("strat", x, based_on=meta.get("based_on")), data)
            if res[0]:
                SETTINGS.setdefault("mm_meta", {}).setdefault(s["id"], {})["post"] = res[1]["post"]["id"]
                save_json("settings.json", SETTINGS)
            return res
        self._mm_bg(work, lambda r: self.mm_board_result(r, f"Posted \"{s['name']}\" to the Community board."))

    def mm_atlas_check(self, data):
        """2.89.3: a screenshot becomes public. Before it goes up: check it shows no character, account or guild
        names, chat or party. Yes = upload it, No = post without it, Cancel = stop. -> False when stopped."""
        if not str(data.get("atlas_image", "")).startswith("l:"):
            return True
        from tkinter import messagebox
        if hasattr(self, "mm_atlas_answer"):                      # (tests answer for you)
            a = self.mm_atlas_answer
        else:
            a = messagebox.askyesnocancel(
                "Your atlas screenshot will be public",
                "Anyone can see it. Check it shows NO character, account or guild names, no chat and no party - "
                "crop it to the atlas if it does.\n\nYes: upload it.  No: post without it.  Cancel: stop.",
                parent=self.root)
        if a is None:
            return False
        if not a:
            data.pop("atlas_image", None)
        return True

    def mm_report(self):
        s = self.mm_current()
        post = (s or {}).get("_post")
        if not post:
            return None
        return self._mm_report_post(post)

    def mm_admin(self, action):
        s = self.mm_current()
        post = (s or {}).get("_post")
        if not post:
            return None
        if action == "delete":
            work = lambda: B.delete(post["id"])  # noqa: E731
        elif action == "ban":
            work = lambda: B.ban(post["author"]["id"])  # noqa: E731
        else:
            work = lambda: B.admin(post["id"], action)  # noqa: E731
        self._mm_bg(work, lambda r: (self.mm_board_result(r, f"Done: {action}."),
                                     action in ("promote", "unpromote") and self._mm_bg(B.official, self._mm_official_done)))

    def mm_copy_mine(self):
        s = self.mm_current()
        if not s:
            return None
        c = {k: v for k, v in MM.tidy(s).items()}
        c["id"] = MM.slug("my-" + c["name"])
        for k in ("ledger", "atlas_image"):                  # 2.85.0: their numbers and screenshot aren't yours
            c.pop(k, None)
        c["author"] = (B.signed_in() or {}).get("name") or "me"
        post = s.get("_post") or {}
        meta = SETTINGS.setdefault("mm_meta", {})
        meta[c["id"]] = {"based_on": post.get("id")} if post.get("id") else {}
        save_json("settings.json", SETTINGS)
        MM.save_mine([m for m in MM.mine() if m["id"] != c["id"]] + [c])
        self.mm_show_mine(c["id"])
        return c

    def mm_show_mine(self, sid=None):
        """From: Mine, with this strat of yours opened (none: the list)."""
        if self.mm_view.get() != "Mine":
            self.mm_view.set("Mine")
            self.mm_view_changed()
        self.mm_reload(keep=(sid + "|mine") if sid else None)

    # ---------------- your board name (no login)
    def mm_account_paint(self):
        """The 👤 chips here and on Leaderboards, and Settings › Privacy & community (2.94.0)."""
        self.cy_paint()

    def mm_account_click(self):
        """2.94.0: the 👤 chip opens Settings › Privacy & community (the name's menu moved there)."""
        return self.community_open()

    def mm_rename(self, name=None):
        from tkinter import simpledialog
        from .privacy import NAME_RULE                        # 2.131.1
        name = name or simpledialog.askstring("Community board", f"Your new name (it can change again in 7 days).\n\n"
                                              f"{NAME_RULE}", parent=self.root)
        if name:
            ok, d = B.rename(name.strip())
            self.app_toast("Done." if ok else d, "Community") if not ok else self._say("Name changed.", 4)
            self.mm_account_paint()
            self.mm_board_fetch()

    def mm_admin_key(self, key=None):
        from tkinter import simpledialog
        key = key or simpledialog.askstring("Community board", "Admin key:",
                                            parent=self.root, show="•")
        if key:
            ok, d = B.become_admin(key)
            self.mm_account_paint()
            if ok:
                self._say("You're an admin on the board now (right-click a post for the admin tools).", 8)
                self.mm_board_fetch()
                try:                                         # 2.88.0: admin-only tools show (none since 2.114.0)
                    self.shell.set_advanced(self.shell.advanced_on())
                except Exception:
                    buglog.caught()
            else:
                self.app_toast(d, "Community")
            return ok

    def mm_leave(self):
        from tkinter import messagebox
        # 2.89.3: leaving can take everything with you
        a = messagebox.askyesnocancel("Community board", "Leave the board and DELETE everything of yours on it - your "
                                      "name, strats, pictures, votes, suggestions and leaderboard times?\n\nYes: delete "
                                      "it all.  No: just forget this account on this PC (your posts stay).",
                                      parent=self.root)
        if a is None:
            return
        if a:
            ok, d = B.delete_me()
            self._say("Done - nothing of yours is on the board any more." if ok else f"Couldn't delete it ({d}).", 8)
        else:
            B.sign_out()
        self.mm_account_paint()
        self.mm_board_fetch()

    # ---------------- 2.46.0: what a strat costs today (stratcost.py: one search per item, once a day)
    def mm_costs(self):
        if getattr(self, "_mm_costs", None) is None:
            from .stratcost import costs
            self._mm_costs = costs()
        return self._mm_costs

    def mm_cost_check(self, force=False, only=None):
        """Queue the strats whose cost wasn't checked today (or one strat now: force=True, only=its id)."""
        from .stratcost import due
        league = SETTINGS.get("league") or ""
        if not league:
            return 0
        n = 0
        for s in self.fl_all_strats():                         # 2.85.0: Community and Official too
            if only and s["id"] != only:
                continue
            if s.get("items") and (force or due(s, self.mm_costs(), league)):
                if s["id"] in getattr(self, "_mm_cost_busy", set()):
                    continue
                self._mm_cost_busy = getattr(self, "_mm_cost_busy", set()) | {s["id"]}
                self.engine.strat_cost_start(s, league)
                n += 1
        return n

    def ev_strat_cost(self, sid, i, price, info):
        c = self.mm_costs().setdefault(sid, {})
        c.setdefault("prices", {})[str(i)] = price
        c.setdefault("info", {})[str(i)] = info

    def ev_strat_cost_finished(self, sid, league):
        from .stratcost import save_costs
        c = self.mm_costs().setdefault(sid, {})
        c.update(at=time.time(), league=league)
        self._mm_cost_busy = getattr(self, "_mm_cost_busy", set()) - {sid}
        if str(sid).startswith("_new"):                           # 3.0.6: New strat's copies (not saved yet)
            if getattr(self, "mm_new_on", False):
                self.mm_new_cv.later(10)
            return
        save_costs({k: v for k, v in self.mm_costs().items() if not str(k).startswith("_new")})
        self.mm_fill()                                            # (Cost per run: the rows and the opened strat)

    def mm_on_show(self):
        if not getattr(self, "_mm_league_touched", True) and self.mm_league.get() != self.mm_league_default():
            self.mm_league.set(self.mm_league_default())          # (your league changed in Settings)
            self.mm_filters_changed()
        self.mm_check_live(force=False)
        try:
            self.mm_cost_check()                                  # 2.46.0: once a day, strats that list their items
        except Exception:
            self.log_error("checking what strats cost")
        self.mm_account_paint()
        if B.configured() and not getattr(self, "_mm_official_asked", False):
            self._mm_official_asked = True
            self._mm_bg(B.official, self._mm_official_done)
            if self.mm_view.get() == "All":                       # (All: the board's strats too)
                self.mm_board_fetch()

    def mm_check_live(self, force=False):
        if getattr(self, "_mm_checking", False):
            return
        self._mm_checking = True
        if force:
            self.mm_live_lbl.config(text="Checking GitHub…", fg=C["muted"])

        self.run_bg(lambda: MM.fetch_live(force=force), lambda res: self.mm_live_done(res, force))

    def mm_live_done(self, res, force):
        self._mm_checking = False
        what, info = res
        if what != "skip":
            save_json("settings.json", SETTINGS)
        if what == "new":
            self.mm_reload()
            self.mm_live_lbl.config(text=f"New strats: {info} in the shared list.", fg=C["green"])
        elif what == "same" and force:
            self.mm_live_lbl.config(text="Up to date.", fg=C["muted"])
        elif what == "error" and force:
            self.mm_live_lbl.config(text=info, fg=C["red"])

    # ---------------- actions
    def mm_copy_regex(self):
        s = self.mm_current()
        if s and s.get("regex"):
            self.root.clipboard_clear()
            self.root.clipboard_append(s["regex"])
            self.own_clip = s["regex"]
            self._say("Copied the strat's stash search. In game: Ctrl+V in the stash search.", 6)

    def mm_export(self):
        s = self.mm_current()
        if not s:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv", initialfile=s["id"] + ".csv",
                                            filetypes=[("Strat guide (CSV - Excel, Google Sheets)", "*.csv"),
                                                       ("Strat (JSON)", "*.json")])
        return self.mm_write_strat(s, path)

    def mm_write_strat(self, s, path):
        """2.46.0: a strat guide is a CSV file (the same layout as the Strat Tracker's numbers); JSON for the repo."""
        if not path:
            return None
        from . import board as _B
        from .privacy import known_names
        mine = s.get("origin") == "mine"
        s = MM.tidy(s)                                       # 2.89.3: a file you might share - your board name or "me",
        if mine or str(s.get("author") or "") in known_names():   # never an account / character name
            s["author"] = (_B.signed_in() or {}).get("name") or "me"
        if path.lower().endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
        elif path.lower().endswith(".txt"):
            with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(MM.to_text(s))
        else:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:      # (Excel reads UTF-8 with the BOM)
                f.write(MM.to_csv(s))
        self._say(f"Saved {path}", 6)
        return path

    def mm_more_menu(self, btn):
        """The toolbar's ⋯: Refresh, Import file… (P6), your community name (2.94.0: Settings › Privacy & community)."""
        from .community_page import chip_text
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        m.add_command(label="↻ Refresh", command=self.mm_refresh)
        m.add_command(label="Import file…", command=self.mm_import)
        m.add_separator()
        name = chip_text()
        m.add_command(label=name + ("…" if name.endswith("Community name") else " - community name…"),
                      command=self.mm_account_click)
        self.mm_last_menu = m
        try:
            menu_popup(m, btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        except tk.TclError:
            pass
        return m

    def mm_import(self, path=None):
        path = path or filedialog.askopenfilename(parent=self.root, filetypes=[("Strat", "*.csv *.txt *.json")])
        if not path:
            return None
        try:
            with open(path, encoding="utf-8-sig") as f:
                raw = f.read()
            d = MM.read_any(raw)                                     # 2.46.0: CSV, the older .txt, or JSON
        except Exception as e:
            self.app_toast(f"Couldn't read that file ({e.__class__.__name__}).", "Import strat")
            return None
        items = d.get("strats") if isinstance(d, dict) and "strats" in d else d if isinstance(d, list) else [d]
        mine = MM.mine()
        added, bad = 0, []
        for s in items:
            if isinstance(s, dict):
                s = MM.migrate({k: v for k, v in s.items() if k != "origin"})
            probs = MM.validate(s)
            if probs:
                bad.append(f"{(s or {}).get('name', '?') if isinstance(s, dict) else '?'}: {probs[0]}")
                continue
            mine = [m for m in mine if m["id"] != s["id"]] + [s]
            added += 1
        MM.save_mine(mine)
        self.mm_show_mine()
        msg = f"Added {added} strat{'s' if added != 1 else ''} to Mine."
        if bad:
            msg += "\nLeft out (not in the standard layout): " + "; ".join(bad[:3])
        self.app_toast(msg, "Import strat")
        return added

    def mm_delete(self):
        s = self.mm_current()
        post = (s or {}).get("_post")
        if post and post.get("mine"):
            return self._mm_bg(lambda: B.delete(post["id"]), lambda r: self.mm_board_result(r, "Deleted."))
        if s and s["origin"] == "mine":
            MM.save_mine([m for m in MM.mine() if m["id"] != s["id"]])
            self.mm_sel = None
            self.mm_reload()

    def mm_add(self):
        """＋ New strat (stratnew.py)."""
        return self.mm_new_open(None)

    def mm_edit(self):
        s = self.mm_current()
        if s and (s["origin"] == "mine" or (s.get("_post") or {}).get("mine")):
            return self.mm_new_open(dict(s))
        return None

    def mm_board_send(self, send, data):
        """Post / update / suggest on the board. 3.0.6: a board from before New strat answers "unknown field" for
        the league, Atlas masters and the copies' every line - then it is sent without them (they stay on this PC).
        -> (ok, answer)."""
        res = send(data)
        if not res[0] and ("unknown field" in str(res[1]) or "items must be" in str(res[1])):
            res = send(MM.board_compat(data))
        return res

    # ---------------- the run tracker (its own, simple)
    def mm_track(self):
        """Run this strat: its setup in the Strat Tracker (made if there's none yet)."""
        s = self.mm_current()
        self.mm_page.pick("Strat Tracker", notify=False)
        self.mm_show_page()
        if s:
            self.fl_for_strat(s["id"])

    # ---------------- Quick tips (3.0.6: was the Lucrative Strats tab): one-liners, folded at the bottom of Find
    def mm_tips_toggle(self, on):
        self.mm_tips_open = bool(on)
        self.mm_find_cv.later(1)

    def mm_one_items(self):
        have = {o["id"] for o in MM.oneliners()}
        promoted = [dict(o, origin="community") for o in self.mm_official.get("oneliners") or []
                    if o.get("id") not in have]
        return MM.oneliners() + promoted + list(getattr(self, "mm_board_ones", []))

    def mm_one_view_items(self, view=None):
        """2.132.6: one view at a time, each copy once. Official: the app's own and promoted posts. Community: other
        posts. Mine: yours (the one on this PC first, then what you posted)."""
        view = view or self.mm_view.get()
        items = self.mm_one_items()
        post = lambda o: o.get("_post") or {}                                   # noqa: E731
        if view == "All":                                                      # 3.0.6: every tip, once
            pool = [o for o in items if o["origin"] == "mine"] + [o for o in items if o["origin"] != "mine"]
        elif view == "Official":
            pool = [o for o in items if o["origin"] == "board" and post(o).get("promoted")] + \
                   [o for o in items if o["origin"] == "community"]
        elif view == "Community":
            pool = [o for o in items if o["origin"] == "board" and not post(o).get("promoted")]
        else:
            pool = [o for o in items if o["origin"] == "mine"] + \
                   [o for o in items if o["origin"] == "board" and post(o).get("mine")]
        seen, out = set(), []
        for o in pool:
            k = " ".join(str(o.get("text", "")).lower().split())
            if k and k not in seen:
                seen.add(k)
                out.append(o)
        return out

    def mm_one_shown(self):
        """The tips of the view picked in From (Official / Community / Mine) that match the search."""
        q = self.mm_q.get().strip().lower() if hasattr(self, "mm_q") else ""
        return [o for o in self.mm_one_view_items()
                if not q or q in (o.get("text", "") + " " + " ".join(o.get("tags") or [])).lower()]

    def mm_one_pick(self, key):
        self.mm_one_sel = key
        self.mm_one_fill()

    def mm_one_tags(self):
        """2.132.6: set a one-liner's type and tags (the strats' lists)."""
        o = self.mm_one_current()
        if not o or o["origin"] != "mine":
            self._say("Pick one of your own one-liners (Mine) to tag it.", 5)
            return None
        w = tk.Toplevel(self.root)
        w.title("Type & tags")
        w.configure(bg=C["panel"])
        w.transient(self.root)
        P1 = C["panel"]
        tk.Label(w, text=o["text"][:90], bg=P1, fg=C["text"], wraplength=420, justify="left",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 8))
        row = tk.Frame(w, bg=P1)
        row.pack(fill="x", padx=12)
        cat = tk.StringVar(value=o.get("category", ""))
        typ = tk.StringVar(value=o.get("type", ""))
        tk.Label(row, text="Type", bg=P1, fg=C["muted"]).pack(side="left")
        cb1 = ttk.Combobox(row, textvariable=cat, values=("",) + MM.CATEGORIES, state="readonly", width=12)
        cb1.pack(side="left", padx=(8, 4))
        cb2 = ttk.Combobox(row, textvariable=typ, state="readonly", width=20)
        cb2.pack(side="left")

        def types(*_a):
            vals = ("",) + MM.TAXONOMY.get(cat.get(), ())
            cb2.config(values=vals)
            if typ.get() not in vals:
                typ.set("")
        cat.trace_add("write", types)
        types()
        have = set(o.get("tags") or [])
        picks = {}
        groups = MM.tag_groups()
        box = tk.Frame(w, bg=P1)
        box.pack(fill="both", padx=12, pady=8)
        for col, (g, tags) in enumerate(groups.items()):
            f = tk.Frame(box, bg=P1)
            f.grid(row=0, column=col, sticky="nw", padx=(0, 16))
            tk.Label(f, text=g.upper(), bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            for t in tags:
                v = tk.BooleanVar(value=t in have)
                picks[t] = v
                ttk.Checkbutton(f, text=t, variable=v).pack(anchor="w")

        def save():
            mine = MM.mine_one()
            for x in mine:
                if x["id"] == o["id"]:
                    for k, val in (("category", cat.get()), ("type", typ.get() if cat.get() else "")):
                        if val:
                            x[k] = val
                        else:
                            x.pop(k, None)
                    x["tags"] = [t for t, v in picks.items() if v.get()]
            MM.save_mine_one(mine)
            w.destroy()
            self.mm_one_fill()
        btns = tk.Frame(w, bg=P1)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right", padx=(0, 8))
        self.mm_tags_win = w
        return w

    def mm_one_fill(self):
        """Draw Find again (the Quick tips are on it)."""
        cv = getattr(self, "mm_find_cv", None)
        if cv is not None:
            cv.later(10)

    def mm_one_current(self):
        sel = getattr(self, "mm_one_sel", None)
        if not sel:
            return None
        return next((o for o in self.mm_one_view_items() if o["id"] + "|" + o["origin"] == sel), None)

    def mm_one_add(self, text=None):
        from tkinter import simpledialog
        text = text if text is not None else simpledialog.askstring(
            "Quick tip", "Your way to make currency, in one line:", parent=self.root)
        text = (text or "").strip()
        if not text:
            return None
        o = {"id": MM.slug("my-" + text[:40]), "text": text[:300], "author": "me",
             "updated": time.strftime("%Y-%m-%d")}
        mine = [x for x in MM.mine_one() if x["id"] != o["id"]] + [o]
        MM.save_mine_one(mine)
        self.mm_tips_open = True
        if self.mm_view.get() != "Mine":
            self.mm_view_set("Mine")
        self.mm_one_sel = o["id"] + "|mine"
        self.mm_one_fill()
        return o

    def mm_one_copy(self):
        o = self.mm_one_current()
        if o:
            self.root.clipboard_clear()
            self.root.clipboard_append(o["text"])
            self.own_clip = o["text"]
            self._say("Copied.", 4)

    def mm_one_post(self):
        o = self.mm_one_current()
        if not o or o["origin"] != "mine":
            self._say("Pick one of your own tips (From: Mine) to post it.", 6)
            return None
        if not self.cm_need_sharing(self.mm_one_post) or self.mm_need_login("post"):
            return None
        data = {k: v for k, v in MM.tidy_one(o).items() if k not in ("id", "author")}
        self._mm_bg(lambda: B.post("one", data), lambda r: self.mm_board_result(r, "Posted to the Community board."))

    def mm_one_vote(self):
        o = self.mm_one_current()
        post = (o or {}).get("_post")
        if not post:
            self._say("Upvotes are for community tips.", 5)
            return None
        if self.mm_need_login("upvote"):
            return None
        self._mm_bg(lambda: B.vote(post["id"], not post.get("voted")), lambda r: self.mm_board_result(r))

    def mm_one_delete(self):
        o = self.mm_one_current()
        post = (o or {}).get("_post")
        if post and (post.get("mine") or (B.signed_in() or {}).get("admin")):
            return self._mm_bg(lambda: B.delete(post["id"]), lambda r: self.mm_board_result(r, "Deleted."))
        if o and o["origin"] == "mine":
            MM.save_mine_one([x for x in MM.mine_one() if x["id"] != o["id"]])
            self.mm_one_fill()

    def mm_one_menu(self, e=None, x=None, y=None):
        """Right-click a tip: copy, upvote, tag, post, delete, report (and the admin's tools)."""
        if e is not None:
            x, y = e.x_root, e.y_root
        o = self.mm_one_current()
        if not o:
            return None
        post, me = (o or {}).get("_post") or {}, B.signed_in() or {}
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        m.add_command(label="Copy text", command=self.mm_one_copy)
        if post:
            m.add_command(label="▲ Remove my upvote" if post.get("voted") else "▲ Upvote", command=self.mm_one_vote)
        if o and o["origin"] == "mine":
            m.add_command(label="🏷 Tags…", command=self.mm_one_tags)
            m.add_command(label="📤 Post to Community", command=self.mm_one_post)
        if (o and o["origin"] == "mine") or post.get("mine"):
            m.add_separator()
            m.add_command(label="Delete", command=self.mm_one_delete)
        if post and not post.get("mine"):
            m.add_command(label="⚑ Report…", command=lambda: self._mm_report_post(post))
        if post and me.get("admin"):
            m.add_separator()
            for label, act in (("Un-hide" if post.get("hidden") else "Hide", "unhide" if post.get("hidden") else "hide"),
                               ("Remove from Official" if post.get("promoted") else "Promote to Official",
                                "unpromote" if post.get("promoted") else "promote")):
                m.add_command(label="Admin: " + label, command=lambda a=act: self._mm_bg(
                    lambda: B.admin(post["id"], a), lambda r: (self.mm_board_result(r, f"Done: {a}."),
                                                              self._mm_bg(B.official, self._mm_official_done))))
            m.add_command(label="Admin: Delete", command=lambda: self._mm_bg(lambda: B.delete(post["id"]),
                                                                             lambda r: self.mm_board_result(r, "Deleted.")))
        try:
            m.tk_popup(x, y)
        except tk.TclError:
            pass
        self.mm_last_menu = m
        return m

    def _mm_report_post(self, post):
        from tkinter import simpledialog
        if self.mm_need_login("report"):
            return None
        why = simpledialog.askstring("Report", "What's wrong with it? (spam, wrong, offensive ...)", parent=self.root)
        if why is not None:
            self._mm_bg(lambda: B.report(post["id"], why), lambda r: self.mm_board_result(r, "Reported - thanks."))

    # ---------------- Craft Helper (2.123.0: tablets and jewels; was Tablet Craft Helper - crafthelper.py)
    def mm_build_tablets(self, page):
        from . import crafthelper as CH
        P1, P2 = C["panel"], C["panel2"]
        self.mm_ch_kind = "tablet"
        bar = tk.Frame(page, bg=P1, padx=8, pady=8)
        bar.pack(fill="x")
        self.mm_tab_q = tk.StringVar()                       # (every list page: its search first, top left)
        tk.Label(bar, text="🔍", bg=P1, fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(0, 4))
        q = ttk.Entry(bar, textvariable=self.mm_tab_q, width=24)
        q.pack(side="left")
        Tooltip(q, "Search the mods")
        self.mm_tab_q.trace_add("write", lambda *_a: self.mm_tab_fill())
        self.mm_ch_seg = SegBar(bar, [k["label"] for k in CH.KINDS.values()], size=9, pad=(12, 4),
                                command=lambda v: self.mm_ch_pick(v))
        self.mm_ch_seg.pack(side="left", padx=(12, 0))
        tk.Label(bar, text="Type", bg=P1, fg=C["muted"]).pack(side="left", padx=(12, 8))
        self.mm_tab_type = tk.StringVar(value="All")
        self.mm_tab_type_cb = cb = ttk.Combobox(bar, textvariable=self.mm_tab_type, values=CH.KINDS["tablet"]["types"],
                                                state="readonly", width=11)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: (self.mm_tab_fill(), self.root.after(20, self.root.focus_set)))
        self.mm_tab_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Only S and A", variable=self.mm_tab_only, command=self.mm_tab_fill).pack(
            side="left", padx=(12, 0))
        pane = ttk.PanedWindow(page, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.mm_ch_lfo, left = chrome_section(pane, "How to craft a tablet")
        pane.add(self.mm_ch_lfo, weight=2)
        self.mm_ch_steps = tk.Frame(left, bg=P2)
        self.mm_ch_steps.pack(fill="x")
        tk.Frame(left, bg=C["line"], height=1).pack(fill="x", pady=12)
        self.mm_ch_check_lbl = tk.Label(left, text="", bg=P2, fg=C["steel"], font=("Segoe UI", 9, "bold"), anchor="w")
        self.mm_ch_check_lbl.pack(fill="x")
        self.mm_ch_hint = tk.Label(left, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w")
        self.mm_ch_hint.pack(fill="x", pady=(2, 8))
        # (GGG policy: no Check button - a click never reads the clipboard. Click the box, press Ctrl+V: one read)
        self.mm_ch_btn = tk.Label(left, text="Click here and press Ctrl+V to check your tablet", bg=C["panel"],
                                  fg=C["muted"], font=("Segoe UI", 9), pady=8, cursor="xterm", highlightthickness=1,
                                  highlightbackground=C["gold_dim"], highlightcolor=C["accent"], takefocus=1)
        self.mm_ch_btn.pack(fill="x")
        self.mm_ch_btn.bind("<Button-1>", lambda e: e.widget.focus_set())
        for seq in ("<Control-v>", "<Shift-Insert>"):
            self.mm_ch_btn.bind(seq, lambda e: (self.mm_tab_check(event=e), "break")[-1])
        # 2.123.4 (Craft Helper phase 2): the verdict - one word with a mark, the next step, the mods, why
        self.mm_ch_vbox = vb = tk.Frame(left, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"],
                                        padx=8, pady=8)
        self.mm_ch_vword = tk.Label(vb, text="", bg=C["panel"], fg=C["text"], font=("Segoe UI", 12, "bold"), anchor="w")
        self.mm_ch_vword.pack(fill="x")
        self.mm_tab_advice = tk.Label(vb, text="", bg=C["panel"], fg=C["text"], font=("Segoe UI", 10, "bold"),
                                      anchor="w", justify="left")
        self.mm_tab_advice.pack(fill="x", pady=(4, 0))
        self.mm_ch_vwhy = tk.Label(vb, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9), anchor="w",
                                   justify="left")
        self.mm_ch_vwhy.pack(fill="x", pady=(4, 0))
        self.mm_ch_vwhy.bind("<Configure>", lambda e: self.mm_ch_vwhy.config(wraplength=max(150, e.width - 4)))
        self.mm_ch_price_btn = ttk.Button(vb, text="Price it", command=self.mm_ch_price)
        self.mm_ch_price_btn.pack(anchor="w", pady=(8, 0))
        Tooltip(self.mm_ch_price_btn, "Run your price check on this item (one trade-site search) and open Price Checks")
        self.mm_ch_text = ""
        self.mm_tab_advice.bind("<Configure>", lambda e: self.mm_tab_advice.config(wraplength=max(150, e.width - 4)))

        right = tk.Frame(pane, bg=P1)
        pane.add(right, weight=3)
        intro = tk.Frame(right, bg=P1)
        intro.pack(fill="x", pady=(0, 8))
        tk.Label(intro, text="Each mod's rating, S (best) to F (ignored), and where it came from.  ⓘ", bg=P1,
                 fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(side="left")
        Tooltip(intro.winfo_children()[0],
                "From: you (your Mod Book rating) > players (3+ votes on the community board) > market (items with "
                "the mod sell clearly above that kind's middle price, across 12+ listings; this league). No prices "
                "are shown here - they change too fast. To know what an item is worth, press your price check key "
                "on it. Right-click a mod to rate it; double-click to search the trade site for it.")
        # 2.125.6 (feedback: the pairs that sell together were crammed at the bottom): the mods and the pairs share the
        # height on a divider you drag (remembered)
        from .style import VSplitter
        vp = self.mm_ch_vpane = VSplitter(right, height=360, lo=120, keep=110, bg=P1,
                                          on_set=lambda _h: self.mm_ch_split_save())
        vp.pack(fill="both", expand=True)
        box, low = vp.top, vp.bottom
        self.root.after(300, self.mm_ch_split_put)
        cols = (("tier", "Rating", 56, "center"), ("mod", "Mod", 360, "w"), ("where", "Type", 90, "w"),
                ("side", "Prefix / suffix", 90, "center"), ("from", "From", 130, "w"))
        self.mm_tab_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", selectmode="extended")
        for cid, title, w, anchor in cols:
            self.mm_tab_tree.heading(cid, text=title)
            self.mm_tab_tree.column(cid, width=w, minwidth=30, anchor=anchor, stretch=cid == "mod")
        self.mm_tab_tree.tag_configure("good", foreground="#ffd9a8")
        self.mm_tab_tree.tag_configure("plain", foreground=C["muted"])
        sb = ttk.Scrollbar(box, orient="vertical", command=self.mm_tab_tree.yview)
        self.mm_tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.mm_tab_tree.pack(side="left", fill="both", expand=True)
        self.mm_tab_tree.bind("<Double-1>", lambda e: self.mm_tab_trade())
        self.mm_tab_tree.bind("<Button-3>", self.mm_tab_menu)
        self.mm_tab_rows = {}
        # 2.125.5 (Craft Helper phase 3): learned mod pairs - two mods that sell well together
        ph = tk.Frame(low, bg=P1)
        ph.pack(fill="x", pady=(8, 4))
        tk.Label(ph, text="PAIRS THAT SELL TOGETHER", bg=P1, fg=C["steel"], font=("Segoe UI", 9, "bold")).pack(side="left")
        pi = tk.Label(ph, text="  Learned from your price checks.  ⓘ", bg=P1, fg=C["muted"], font=("Segoe UI", 9))
        pi.pack(side="left")
        Tooltip(pi, "Two mods whose listings ask clearly more together than the better mod alone (at least "
                    f"{CH.PAIR_MIN_N} listings with both, {CH.PAIR_GAIN:g}x or more), from the listings your own "
                    "price checks fetched this league. The letter comes from how far above that kind's middle price "
                    "they ask - no prices are shown. Hover a pair for how it was worked out. A checked item with a "
                    "pair rated S or A counts both mods as good.")
        pbox = tk.Frame(low, bg=P1)
        pbox.pack(fill="both", expand=True)
        pcols = (("tier", "Rating", 56, "center"), ("mods", "Mods", 450, "w"), ("from", "From", 170, "w"))
        self.mm_ch_ptree = pt = ttk.Treeview(pbox, columns=[c[0] for c in pcols], show="headings", height=5,
                                             selectmode="browse")
        for cid, title, w, anchor in pcols:
            pt.heading(cid, text=title)
            pt.column(cid, width=w, minwidth=w if cid == "from" else 30, anchor=anchor, stretch=cid == "mods")
        pt.tag_configure("good", foreground="#ffd9a8")
        pt.tag_configure("plain", foreground=C["muted"])
        psb = ttk.Scrollbar(pbox, orient="vertical", command=pt.yview)
        pt.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        pt.pack(side="left", fill="both", expand=True)
        self.mm_ch_ptip = Tooltip(pt, "")
        self.mm_ch_prow = None
        pt.bind("<Motion>", self.mm_ch_pair_hover, add="+")
        self.mm_ch_pempty = tk.Frame(low, bg=P1)
        self.mm_ch_pempty_lbl = tk.Label(self.mm_ch_pempty, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9),
                                         anchor="w", justify="left", wraplength=380)       # (D3: wraps)
        self.mm_ch_pempty_lbl.pack(side="left")
        ttk.Button(self.mm_ch_pempty, text="Open Price Checks", style="Quiet.TButton",
                   command=lambda: self.shell.open("pricecheck")).pack(side="left", padx=(8, 0))
        self.mm_ch_pairs = {}
        # 2.125.5: the data pack (kinds, steps, market numbers) - shipped, and kept up to date from GitHub
        pk = tk.Frame(left, bg=C["panel2"])
        pk.pack(fill="x", side="bottom", pady=(12, 0))
        self.mm_ch_pack_lbl = tk.Label(pk, text=CH.pack_line(), bg=C["panel2"], fg=C["muted"], font=("Segoe UI", 9),
                                       anchor="w")
        self.mm_ch_pack_lbl.pack(side="left")
        Tooltip(self.mm_ch_pack_lbl, "The Craft Helper's data (types, steps, how the market picks a letter) for the "
                                     "game patch shown. It updates from GitHub on its own - one small public "
                                     "download, nothing about you is sent.")
        cb_ = ttk.Button(pk, text="Check for a newer one", style="Quiet.TButton",
                         command=lambda: self.mm_ch_pack_check(True))
        cb_.pack(side="right")
        self.mm_ch_paint()
        self.root.after(1500, lambda: self.mm_ch_pack_check(False))

    def mm_ch_split_put(self):
        """2.125.6: the mods / pairs divider where you left it (a share of the height)."""
        vp = getattr(self, "mm_ch_vpane", None)
        try:
            h = vp.winfo_height()
            if h < 100:
                return self.root.after(500, self.mm_ch_split_put)
            share = float(SETTINGS.get("ch_split", 0.62))
            vp.sashpos(0, int(h * min(0.9, max(0.2, share))))
        except (tk.TclError, AttributeError, ValueError):
            pass
        return None

    def mm_ch_split_save(self):
        vp = getattr(self, "mm_ch_vpane", None)
        try:
            h = vp.winfo_height()
            if h >= 100:
                SETTINGS["ch_split"] = round(vp.sashpos(0) / h, 3)
                save_json("settings.json", SETTINGS)
        except (tk.TclError, AttributeError):
            pass

    def mm_ch_pack_check(self, force):
        """2.125.5: a newer Craft Helper data pack on GitHub? (at most twice a day unless asked)"""
        from . import crafthelper as CH
        if getattr(self, "_mm_ch_checking", False):
            return
        self._mm_ch_checking = True
        if force:
            self.mm_ch_pack_lbl.config(text="Checking GitHub…")
        self.run_bg(lambda: CH.fetch_live(force=force), lambda res: self.mm_ch_pack_done(res, force))

    def mm_ch_pack_done(self, res, force):
        from . import crafthelper as CH
        self._mm_ch_checking = False
        what, info = res
        if what != "skip":
            save_json("settings.json", SETTINGS)
        try:
            if what == "new":
                self.mm_ch_pack_lbl.config(text=f"Updated - {info}")
                self.mm_ch_pick(CH.KINDS[self.mm_ch_kind]["label"])
            elif what == "error" and force:
                self.mm_ch_pack_lbl.config(text=info)
            else:
                self.mm_ch_pack_lbl.config(text=CH.pack_line() + ("  (up to date)" if force else ""))
        except tk.TclError:
            pass

    def mm_ch_pair_hover(self, e):
        pt = self.mm_ch_ptree
        row = pt.identify_row(e.y)
        if row == self.mm_ch_prow:
            return
        self.mm_ch_prow = row
        self.mm_ch_ptip._leave()
        pr = self.mm_ch_pairs.get(row)
        if pr:
            from . import crafthelper as CH
            self.mm_ch_ptip.text = CH.pair_how(pr)
            self.mm_ch_ptip._enter()

    def mm_ch_pairs_fill(self, kind, ttype, q):
        from . import crafthelper as CH
        pt = self.mm_ch_ptree
        pt.delete(*pt.get_children())
        self.mm_ch_pairs = {}
        names = CH.sid_names(kind)
        for i, pr in enumerate(CH.pairs(kind)):
            if ttype not in ("All", "") and pr["base"] not in (ttype, kind):
                continue
            txt = CH.pair_text(kind, pr, names)
            if q and q not in txt.lower():
                continue
            iid = f"p{i}"
            pt.insert("", "end", iid=iid, tags=("good" if pr["letter"] in CH.GOOD else "plain",),
                      values=(pr["letter"], txt[:1].upper() + txt[1:], f"price checks · {pr['n']} listings"))
            self.mm_ch_pairs[iid] = pr
        if self.mm_ch_pairs:
            self.mm_ch_pempty.pack_forget()
        else:
            one = CH.KINDS[kind]["one"]
            self.mm_ch_pempty_lbl.config(
                text=("No pairs match the search." if q else
                      f"No pairs yet: they're learned from the {one}s your price checks look up "
                      f"({CH.PAIR_MIN_N}+ listings with both mods)."))
            self.mm_ch_pempty.pack(fill="x", pady=(4, 0), after=pt.master)

    def mm_ch_pick(self, label):
        from . import crafthelper as CH
        self.mm_ch_kind = next(k for k, v in CH.KINDS.items() if v["label"] == label)
        self.mm_tab_type.set("All")
        self.mm_tab_type_cb.config(values=CH.KINDS[self.mm_ch_kind]["types"])
        self.mm_tab_advice.config(text="")
        self.mm_ch_vbox.pack_forget()
        self.mm_ch_paint()
        self.mm_tab_fill()

    def mm_ch_paint(self):
        """The left side for the kind shown: its craft steps and its Check button."""
        from . import crafthelper as CH
        K, P2 = CH.KINDS[self.mm_ch_kind], C["panel2"]
        self.mm_ch_lfo.section_bar.set_title(f"How to craft a {K['one']}")
        for w in self.mm_ch_steps.winfo_children():
            w.destroy()
        for i, (when, what) in enumerate(K["flow"], 1):
            row = tk.Frame(self.mm_ch_steps, bg=P2)
            row.pack(fill="x", pady=(8, 0))
            tk.Label(row, text=str(i), bg=C["accent"], fg="#10141c", font=("Segoe UI", 10, "bold"), width=2).pack(
                side="left", anchor="n")
            col = tk.Frame(row, bg=P2)
            col.pack(side="left", fill="x", expand=True, padx=(8, 0))
            tk.Label(col, text=when, bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            lab = tk.Label(col, text=what, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left")
            lab.pack(fill="x")
            lab.bind("<Configure>", lambda e, w=lab: w.config(wraplength=max(150, e.width - 4)))
        self.mm_ch_check_lbl.config(text=f"CHECK YOUR {K['one'].upper()}")
        self.mm_ch_hint.config(text=f"Hover a {K['one']} in game, press Ctrl+C, then:")
        self.mm_ch_btn.config(text=f"Click here and press Ctrl+V to check your {K['one']}")
        if self.mm_ch_seg.get() != K["label"]:
            self.mm_ch_seg.pick(K["label"], notify=False)

    def mm_tab_data(self, kind=None, ttype="All"):
        """Every mod of the kind -> (mod, good (S / A)?, (letter, source, count), stat id)."""
        from . import regex as R
        from . import crafthelper as CH
        kind = kind or getattr(self, "mm_ch_kind", "tablet")
        R.load()
        pooled = CH._pooled()
        out = []
        for m in R.mods(kind):
            sid = MM.stat_id(m["line"])
            r = CH.rating(kind, m, ttype, pooled)
            out.append((m, r[0] in CH.GOOD, r, sid))
        out.sort(key=lambda r: (CH._rank(r[2][0]), r[0]["text"]))
        return out

    def mm_tab_fill(self):
        from . import crafthelper as CH
        tv = self.mm_tab_tree
        tv.delete(*tv.get_children())
        kind, ttype, only = self.mm_ch_kind, self.mm_tab_type.get(), self.mm_tab_only.get()
        q = self.mm_tab_q.get().strip().lower()
        self.mm_tab_rows = {}
        for m, good, r, sid in self.mm_tab_data(kind, ttype):
            if ttype != "All" and ttype not in m["tags"] and "Any" not in m["tags"]:
                continue
            if only and not good:
                continue
            if q and q not in m["text"].lower():
                continue
            txt = m["text"]
            where = ", ".join(t for t in m["tags"] if t != "Any") or "Any"
            tv.insert("", "end", iid=m["id"], tags=("good" if good else "plain",),
                      values=(r[0], txt[:1].upper() + txt[1:], where, m.get("side", ""), CH.source_text(r[1], r[2])))
            self.mm_tab_rows[m["id"]] = (m, good, r, sid)
        try:
            self.mm_ch_pairs_fill(kind, ttype, q)
        except Exception:
            self.log_error("the Craft Helper's pairs")
        if not self.mm_tab_rows:
            msg = (f"No {CH.KINDS[kind]['one']} mods rated S or A yet: right-click a mod to rate it, or turn off Only "
                   "S and A." if only and not q else "No mods match the search.")
            tv.insert("", "end", iid="_none", values=("", msg, "", "", ""), tags=("plain",))

    def mm_tab_trade(self, mid=None):
        """Double-click: the trade site's search for items with this mod - you start it, in your browser."""
        sel = [mid] if mid else [i for i in self.mm_tab_tree.selection() if i in self.mm_tab_rows]
        if not sel:
            return None
        m, _g, _r, sid = self.mm_tab_rows[sel[0]]
        if not sid:
            self._say("The trade site's name for this mod isn't known yet (it loads with the first price check).", 8)
            return None
        url = MM.trade_link(SETTINGS.get("league"), sid, None)
        webbrowser.open(url)
        return url

    def mm_tab_rate(self, ids, tier):
        """Rate mods from here: the same rating as the Mod Book (yours wins over players and the market)."""
        from . import ratemods as RM
        from .mods import norm, rule_key, TIER_F
        keys = sorted({rule_key(self.mm_ch_kind, norm(l)) for i in ids for l in
                       (self.mm_tab_rows[i][0].get("lines") or [self.mm_tab_rows[i][0]["line"]])})
        RM.apply(keys, None if tier is None else "ignore" if tier == TIER_F else tier)
        try:
            self.refresh_rules()
        except Exception:
            buglog.caught()
        self.mm_tab_fill()
        return keys

    def mm_tab_menu(self, e):
        from .mods import SHOWN_TIERS
        row = self.mm_tab_tree.identify_row(e.y)
        if row not in self.mm_tab_rows:
            return
        if row not in self.mm_tab_tree.selection():
            self.mm_tab_tree.selection_set(row)
        sel = [i for i in self.mm_tab_tree.selection() if i in self.mm_tab_rows]
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        for t in SHOWN_TIERS:
            m.add_command(label=f"Rate {t}" + ("  (ignore)" if t == "F" else ""), command=lambda t_=t: self.mm_tab_rate(sel, t_))
        m.add_command(label="Clear my rating", command=lambda: self.mm_tab_rate(sel, None))
        m.add_separator()
        m.add_command(label="Search the trade site for it", command=lambda: self.mm_tab_trade(row))
        m.tk_popup(e.x_root, e.y_root)

    def mm_tab_check(self, text=None, event=None):
        """Read the copied tablet / jewel and say what to do next (the steps on the left). Good = rated S or A.
        text None: Ctrl+V on the check box - the clipboard, read once for that key press."""
        from . import regex as R
        from . import crafthelper as CH
        from .clipread import app_paste
        if text is None:
            text = app_paste(self.root, event)
        kind = self.mm_ch_kind
        for k, K in CH.KINDS.items():                      # (a jewel copied while Tablets shows: switch to Jewels)
            if f"Item Class: {K['item_class']}" in text or (k == "jewel" and "Item Class: Jewels" in text):
                if k != kind:
                    self.mm_ch_pick(K["label"])
                kind = k
                break
        else:
            one = CH.KINDS[kind]["one"]
            self.mm_ch_vbox.pack(fill="x", pady=(8, 0))
            self.mm_ch_vword.config(text="✕ No " + one + " copied", fg=C["red"])
            self.mm_tab_advice.config(text=f"The clipboard has no {one}: hover one in game, press Ctrl+C, then try "
                                           "again.", fg=C["text"])
            self.mm_ch_vwhy.config(text="")
            self.mm_ch_price_btn.pack_forget()
            self.mm_ch_text = ""
            return None
        R.load()
        names = {m["id"]: m["text"] for m in R.mods(kind)}
        found = CH.item_mods(kind, text)                # (whole lines - the stash-search tokens over-matched)
        rated = {m["id"]: r for m, _g, r, _s in self.mm_tab_data(kind)}
        letters = [rated.get(i, ("-",))[0] for i in found]
        # 2.125.5: a learned pair rated better than its mods lifts both to the pair's letter
        by = R.by_id(kind)
        sid_of = {i: CH._sid(by[i]["line"]) for i in found if i in by}
        pl = CH.item_pairs(kind, found)
        for pr in pl:
            for n_, i in enumerate(found):
                if sid_of.get(i) in (pr["a"], pr["b"]) and CH._rank(pr["letter"]) < CH._rank(letters[n_]):
                    letters[n_] = pr["letter"]
        pnames = CH.sid_names(kind)
        v = CH.verdict(kind, text, letters,
                       pair_lines=[f"{CH.pair_text(kind, pr, pnames)} sell as a pair (rated {pr['letter']})"
                                   for pr in pl[:2]])
        advice = v["next"]
        lines = [advice, ""] + [f"{l}  " + names.get(i, i) for l, i in zip(letters, found)]
        self.mm_ch_vbox.pack(fill="x", pady=(8, 0))
        self.mm_ch_vword.config(text=f"{v['mark']} {v['word']}", fg=C[v["tone"]])
        self.mm_tab_advice.config(text="\n".join(lines), fg=C["text"])
        self.mm_ch_vwhy.config(text=v["why"])
        self.mm_ch_text, self.mm_ch_verdict = text, v["key"]
        self.mm_ch_price_btn.pack(anchor="w", pady=(8, 0))
        return advice

    def mm_ch_price(self):
        """Price it: your own price check on the item just checked (the helper never searches by itself)."""
        if not self.mm_ch_text:
            return None
        rid = self.pc_take(self.mm_ch_text)
        self.shell.open("pricecheck")
        return rid
