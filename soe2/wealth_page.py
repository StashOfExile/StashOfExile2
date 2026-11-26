"""The Wealth page of the window.

Part of StashOfExile2. Split out of the single-file app in 1.37 (see the launcher's VERSION HISTORY)."""

import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from tkinter import ttk
from . import buglog
from .config import save_json, SETTINGS
from .chrome import SectionBar, Viewport, section as chrome_section
from .util import _amt, _num
from .net import fmt_stamp
from .rates import RATES
from .trade import ago
from .pricefmt import fmt_div
from .inplace import set_cfg, tv_sync
from .wealth import WEALTH, wealth_display_name, wealth_rows, WPRICES, parse_stack
from .style import C, SegBar, Tooltip, autowrap
from . import cleanguard as _cleanguard
from .listkit import _menu as menu_theme   # 3.3.0 owner: one menu look across the app


class _MenuItem:
    """A menu entry that answers .config(state=...) like the button it replaced (2.0 beta 7)."""

    def __init__(self, menu, index):
        self.menu, self.index = menu, index

    def config(self, state="normal", **_kw):
        try:
            self.menu.entryconfigure(self.index, state=state)
        except Exception:
            buglog.caught()
    configure = config


# ------------------------------------------------------------------ the app
class WealthPage:
    """The Wealth page (mixed into App): net worth, history and every item with its value."""

    W_COLS = [("item", "Name", 320, "w"), ("tab", "From", 150, "w"), ("qty", "Quantity", 90, "e"),
              ("each", "Price", 100, "e"), ("total", "Total", 110, "e"), ("chg", "7 days", 90, "e"),
              ("wchg", "Worth change", 110, "e"), ("src", "Priced by", 190, "w")]
    CAT_INFO = {"currency": ("💰", "Currency"), "fragment": ("🧩", "Fragments"), "gem": ("💎", "Gems"),
                "jewel": ("🔷", "Jewels"), "map": ("🗺", "Waystones"), "armour": ("🛡", "Armor"),
                "weapon": ("⚔", "Weapons"), "accessory": ("💍", "Jewelry"), "card": ("🃏", "Cards"),
                "flask": ("🧪", "Flasks"), "sanctum": ("🏺", "Relics"), "relic": ("🏺", "Relics"), "other": ("📦", "Other")}
    RANGES = {"24 hours": 86400, "7 days": 7 * 86400, "30 days": 30 * 86400, "Lifetime": None}

    def build_wealth_page(self, tab):
        """2.75.0 (feedback: this page needs a major pass to improve UX): two pages, listed in the sidebar -
        Wealth ↳ Overview (the total, what moved it, every item) and ↳ Snapshots (look back, compare two). Scan stash
        and More ▾ sit on top of every page. The first time, the setup steps are cards on the Overview (no pop-up);
        once done they fold into one status line."""
        P1, P2 = C["panel"], C["panel2"]
        lab = dict(bg=P1, fg=C["muted"])
        self.w_tabfilter, self.w_snap_sel, self.w_mv_item = None, None, None
        self.w_counting, self.w_session = False, []         # Count by hand: Ctrl+C on each stack, in game

        # ---- on top of every page: what was done when, and the actions
        abar = tk.Frame(tab, bg=P1)
        abar.pack(fill="x", padx=8, pady=(8, 0))
        self.w_synced = tk.Label(abar, text="", anchor="w", **lab)
        self.w_synced.pack(side="left", fill="x", expand=True)
        more = tk.Menubutton(abar, text="More ▾", bg="#1b2a48", fg=C["text"], activebackground="#2c4a84",
                             activeforeground="#ffffff", relief="flat", padx=8, pady=4, cursor="hand2")
        mm = menu_theme(more)
        mm.add_command(label="Update prices from poe.ninja", command=self.wealth_update_prices)
        # UI overhaul (feedback: drop the duplicate - Count by hand stays as a fallback): Scan stash is the
        # way; Count by hand is for a currency it can't read
        mm.add_command(label="Count by hand…", command=self.wealth_count_toggle)
        mm.add_separator()
        mm.add_command(label="Export history as CSV…", command=self.wealth_export_history)    # 2.2.0
        mm.add_command(label="Export items as CSV…", command=self.wealth_export_items)
        mm.add_separator()
        mm.add_command(label="How Wealth works", command=self.wealth_guide)
        more.config(menu=mm)
        more.pack(side="right")
        self.w_price_btn = _MenuItem(mm, 0)
        # P3 (2.105.1): no synced stash tabs - Scan stash is the main button
        self.w_scan_btn = ttk.Button(abar, text="Scan stash…", command=self.stash_scan_start,    # 2.102.0
                                     style="Primary.TButton")                                    # (2.135.0: the main one)
        self.w_scan_btn.pack(side="right", padx=(0, 8))
        Tooltip(self.w_scan_btn, "Reads your Currency, Abyss, Delirium, Breach, Expedition, Ritual, Essence, "
                                  "Fragments and Socketables tabs from the screen. You check the numbers before they're saved. Only "
                                  "looks: no keys, no clicks; the picture is never saved.")
        self.w_msg = tk.Label(tab, text="", anchor="w", justify="left", bg=P1, fg=C["muted"], padx=12,
                              font=("Segoe UI", 10, "bold"))
        self.w_msg.pack(fill="x", pady=(4, 0))
        self.w_msg.bind("<Configure>", lambda e: self.w_msg.config(wraplength=max(300, e.width - 30)))

        # ---- the pages (their names are in the sidebar, under Wealth)
        self.w_side_mode = SegBar(tab, list(self.W_PAGES), command=lambda v: self.wealth_show_page(), size=10,
                                  pad=(16, 4))
        self.w_side_mode.pack(anchor="w", padx=8, pady=(8, 0))
        if getattr(self, "shell", None) is not None:
            self.shell.register_tabs("wealth", self.w_side_mode)
        from .style import ScrollArea
        self.w_pages = {n: tk.Frame(tab, bg=P1) for n in self.W_PAGES}
        self.w_ov_area = ScrollArea(tab, bg=P1, min_height=640)    # a short window scrolls the page (the thin bar)
        self.w_pages["Overview"] = self.w_ov_area
        ov = self.w_ov_area.inner

        # ---- Overview: the setup steps (first time) or one status line
        self.w_steps = tk.Frame(ov, bg=P1)
        self.w_status = tk.Frame(ov, bg=P1)
        self.w_steps_top = tk.Frame(ov, bg=P1)
        self.w_steps_top.pack(fill="x", padx=8, pady=(8, 0))
        from .cards import StatTiles                        # UI overhaul: the numbers first, each with its ⓘ
        self.w_tiles = StatTiles(ov, bg_role="surface", pad=(8, 12), h=92)
        self.w_tiles.pack(fill="x")

        cards = tk.Frame(ov, bg=P1)
        cards.pack(fill="x", padx=8, pady=(8, 8))
        cards.columnconfigure(0, weight=3, uniform="c")
        cards.columnconfigure(1, weight=2, uniform="c")

        def card(col, title):                               # 2.69.0: header strip + sunken frame, like Price checks
            outer, f = chrome_section(cards, title, padx=12, pady=8)
            outer.grid(row=0, column=col, sticky="nsew", padx=(0, 4) if col == 0 else (4, 0))
            return f
        c1 = card(0, "Wealth")
        head = tk.Frame(c1, bg=P2)
        head.pack(fill="x")
        self.w_mode = SegBar(head, ["Total", "Daily"], command=lambda v: self.wealth_draw_chart(), size=9, pad=(8, 4))
        self.w_mode.pack(side="left", padx=(0, 8))
        self.w_range = tk.StringVar(value=SETTINGS.get("wealth_range", "7 days"))
        rb = ttk.Combobox(head, textvariable=self.w_range, values=list(self.RANGES), state="readonly", width=10)
        rb.pack(side="left")
        rb.bind("<<ComboboxSelected>>", lambda e: (SETTINGS.__setitem__("wealth_range", self.w_range.get()),
                                                    save_json("settings.json", SETTINGS), self.wealth_draw_chart(),
                                                    self.root.after(20, self.root.focus_set)))
        # (UI overhaul: the total, the change and the Exalted / Chaos line are the number cards above - kept for their
        # callers, not shown twice)
        self.w_total = tk.Label(head, text="-", bg=P2, fg=C["good"], font=("Segoe UI", 22, "bold"))
        self.w_delta = tk.Label(head, text="", bg=P2, fg=C["green"], font=("Segoe UI", 12, "bold"))
        self.w_equiv = tk.Label(c1, text="", bg=P2, fg=C["steel"], anchor="e")
        self.w_chart = tk.Canvas(c1, height=120, bg=P2, highlightthickness=0)
        self.w_chart.pack(fill="both", expand=True, pady=(2, 0))
        self.w_chart.bind("<Configure>", lambda e: self.wealth_draw_chart())
        self.w_facts = tk.Label(c1, text="", bg=P2, fg=C["muted"], anchor="w", justify="left", font=("Segoe UI", 9))
        self.w_facts.pack(fill="x")
        autowrap(self.w_facts)                              # D3: wraps at Drawer width

        # 3.0.4 (the "Where it is" card told nothing): What moved it - the week's change split into prices and
        # amounts, the biggest price moves, and one item's week when it's picked
        c2 = card(1, "What moved it")
        head2 = tk.Frame(c2, bg=P2)
        head2.pack(fill="x")
        tk.Label(head2, text="Last 7 days", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        mi = tk.Label(head2, text="ⓘ", bg=P2, fg=C["muted"], font=("Segoe UI", 10))
        mi.pack(side="right")
        Tooltip(mi, "Prices: what you hold now times how much each price changed this week - poe.ninja's 7-day line. "
                    "Amounts: the rest of the change since your snapshot from about 7 days ago. Click an item for its week.")
        self.w_mv = tk.Frame(c2, bg=P2)
        self.w_mv.pack(fill="both", expand=True, pady=(4, 0))

        right = tk.Frame(ov, bg=P1)
        right.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.w_right = right
        ibar = tk.Frame(right, bg=P1)
        ibar.pack(fill="x", pady=(0, 8))
        # P3 (2.105.1): where a stack came from - Counted / Scanned / Added by hand (was the stash tab picker)
        self.w_from = SegBar(ibar, ["All", "Scanned", "Counted by hand"], size=9, pad=(8, 4),
                             command=lambda v: self.wealth_pick_tab(None if v == "All" else v))
        self.w_from.pack(side="left", padx=(0, 12))
        self.w_filter = tk.StringVar()
        self.w_filter.trace_add("write", lambda *a: self.wealth_fill_items())
        se = tk.Entry(ibar, textvariable=self.w_filter, width=24, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                      relief="flat", highlightthickness=1, highlightbackground=C["line"], font=("Segoe UI", 10))
        _cleanguard.free(se)        # 3.3.0: a search
        se.pack(side="left", ipady=4, before=self.w_from)        # UI overhaul: the search box first
        self.w_from.pack_configure(padx=(12, 12))
        ph = tk.Label(se, text="🔍  Search items", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 10))
        ph.bind("<Button-1>", lambda e: se.focus_set())

        def placeholder(*_a):
            if self.w_filter.get() or self.root.focus_get() is se:
                ph.place_forget()
            else:
                ph.place(x=4, rely=0.5, anchor="w")
        se.bind("<FocusIn>", placeholder, add="+")
        se.bind("<FocusOut>", placeholder, add="+")
        self.w_filter.trace_add("write", placeholder)
        self.root.after(200, placeholder)
        # 3.0.4 (owner): no No price found / Combine stacks switches - stacks of one item are always one row, and an
        # item with no price says so in its row
        self.w_filter_chip = tk.Label(ibar, text="", bg="#2c4a84", fg="#ffffff", padx=8, pady=2, cursor="hand2",
                                      font=("Segoe UI", 9, "bold"))
        self.w_filter_chip.bind("<Button-1>", lambda e: self.wealth_clear_filters())

        # counting / "copied a stack" strip (hidden until used)
        self.w_cstrip = tk.Frame(right, bg=C["warn_bg"], padx=12, pady=8, highlightthickness=1, highlightbackground=C["accent"])
        self.w_cstrip_lbl = tk.Label(self.w_cstrip, text="", bg=C["warn_bg"], fg=C["text"], anchor="w", justify="left",
                                     font=("Segoe UI", 10))
        self.w_cstrip_lbl.pack(side="left", fill="x", expand=True)
        self.w_cstrip_btns = tk.Frame(self.w_cstrip, bg=C["panel2"])
        self.w_cstrip_btns.pack(side="right")
        self.w_cstrip_lbl.bind("<Configure>", lambda e: self.w_cstrip_lbl.config(wraplength=max(260, e.width - 10)))
        # add by hand (hidden until used)

        # ---- every item (2.69.0: under its header strip, in a sunken frame)
        self.w_items_head = SectionBar(right, "Items")
        self.w_items_head.pack(fill="x")
        ivp = Viewport(right, bg_key="panel")
        ivp.pack(fill="both", expand=True)
        itf = ivp.body
        self.w_itf = itf
        # UI overhaul: each item with its picture (poe.ninja's, when it has one), in taller rows
        self.w_items = ttk.Treeview(itf, columns=[c[0] for c in self.W_COLS], show="tree headings",
                                    selectmode="extended", height=3, style="Items.Treeview")
        self.w_items.column("#0", width=48, minwidth=48, stretch=False, anchor="center")
        self.w_items.heading("#0", text="")
        from .rates_view import Icons, LocalIcons
        self.w_icons = Icons(self.root, lambda: self.wealth_fill_items(), size=28)
        self.w_local = LocalIcons(self.root, size=28)          # (the game's exchange pictures, shipped)
        for cid, title, w, anchor in self.W_COLS:
            self.w_items.heading(cid, text=title, command=lambda c=cid: self.wealth_sort(c))
            self.w_items.column(cid, width=w, anchor=anchor, stretch=(cid in ("item", "src")))
        isb = ttk.Scrollbar(itf, orient="vertical", command=self.w_items.yview)
        self.w_items.configure(yscrollcommand=isb.set)
        isb.pack(side="right", fill="y")
        self.w_items.pack(side="left", fill="both", expand=True)
        for tg, col in (("unique", C["orange"]), ("rare", C["rare"]), ("magic", C["magic"]), ("gem", C["green"]),
                        ("none", C["muted"]), ("held", "#ffe2a8")):
            self.w_items.tag_configure(tg, foreground=col)
        self.w_items.tag_configure("odd", background=C["odd"])
        self.w_items.tag_configure("own", foreground="#7cc7ff")
        self.w_items.bind("<Button-3>", self.wealth_item_menu)
        self.w_items.bind("<Double-1>", self.wealth_amount_click)
        self.w_items.bind("<<TreeviewSelect>>", lambda e: self.wealth_pick_moved_row(), add="+")
        self.list_register("wealth", self.w_items, delete=lambda rows: self.wealth_remove_rows(rows))   # 2.4.0
        crow = tk.Frame(right, bg=P1)                    # 2.4.0: under the list - what's in it, Clear and Undo
        crow.pack(fill="x", pady=(4, 0), side="bottom", before=self.w_items_head)   # (first in line: never squeezed out)
        self.undo_button(crow, "wealth").pack(side="right")
        ttk.Button(crow, text="Clear…", command=self.wealth_clear_items, style="Danger.TButton").pack(side="right", padx=(0, 8))
        self.w_count = tk.Label(crow, text="", bg=P1, fg=C["muted"], anchor="w", font=("Segoe UI", 9),
                                justify="left")
        self.w_count.pack(side="left", fill="x", expand=True)
        self.w_count.bind("<Configure>", lambda e: self.w_count.config(wraplength=max(200, e.width - 6)))
        self.w_empty = tk.Label(itf, bg=P1, fg=C["muted"], font=("Segoe UI", 10), justify="center",
                                text="Nothing counted yet.\nPress Scan stash to read your stash tabs.")

        # ---- Snapshots: look back, compare two
        sp = self.w_pages["Snapshots"]
        spl = tk.Frame(sp, bg=P1)                          # P3 (2.105.1): the list, and the picked one beside it
        spl.pack(fill="both", expand=True, padx=8, pady=8)
        so2, sf2 = chrome_section(spl, "Picked", padx=12, pady=8)
        so2.pack(side="right", fill="y", padx=(8, 0))
        so2.configure(width=360)
        so2.pack_propagate(False)
        po, pf = chrome_section(spl, "Snapshots", "Each count, scan or price update saves your total. Pick one to see "
                                                  "it; Ctrl+click a second to compare. Delete removes.", padx=12, pady=8)
        po.pack(side="left", fill="both", expand=True)
        self.w_side_snaps = pf
        sv = ttk.Treeview(pf, columns=("when", "why", "total", "change"), show="headings", selectmode="extended",
                          height=10)
        for cid, title, w, a in (("when", "When", 140, "w"), ("why", "What happened", 200, "w"),
                                 ("total", "Total", 100, "e"), ("change", "Change", 100, "e")):
            sv.heading(cid, text=title)
            sv.column(cid, width=w, anchor=a, stretch=cid == "why")
        sv.tag_configure("up", foreground=C["green"])
        sv.tag_configure("down", foreground=C["red"])
        sv.pack(fill="both", expand=True)
        sv.bind("<<TreeviewSelect>>", lambda e: self.wealth_pick_snapshot())
        self.w_snaps = sv
        self.list_register("wealth", sv, delete=lambda rows: self.wealth_remove_snaps(rows))
        self.w_snap_info = tk.Label(sf2, text="Pick a snapshot to see what it held.", bg=P2, fg=C["muted"], anchor="nw",
                                    justify="left", wraplength=320, font=("Segoe UI", 10))
        self.w_snap_info.pack(fill="x")
        self.w_snap_cats = tk.Frame(sf2, bg=P2)
        self.w_snap_cats.pack(fill="x", pady=(8, 0))
        ttk.Button(sf2, text="Remove", style="Quiet.TButton",
                   command=lambda: self.wealth_remove_snaps(self.w_snaps.selection())).pack(side="bottom", fill="x")

        self.w_rowmap, self.w_sort_col, self.w_sort_rev = {}, "total", True
        self.wealth_show_page()
        self.refresh_wealth(force=True)

    W_PAGES = ("Overview", "Snapshots")          # P3 (2.105.1): no Stash tabs page
    SNAP_WHY = {"counted": "Counted currency", "scanned": "Scanned stash", "prices updated": "Prices updated",
                "synced": "Old synced tabs", "rares priced": "Old rares priced", "session start": "Session start",
                "session end": "Session end"}

    def wealth_show_page(self, name=None):
        """One of Wealth's pages (the sidebar picks them too)."""
        if name:
            self.w_side_mode.pick(name, notify=False)
        cur = self.w_side_mode.get()
        for n, f in self.w_pages.items():
            if n == cur:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()
        if cur == "Snapshots":
            self.wealth_side()

    WEALTH_GUIDE = [
        ("What Wealth is", "Tracks and logs your overall net worth, converts all currency items to Divine values."),
        ("Scan stash", "Reads your Currency, Abyss, Delirium, Breach, Expedition, Ritual, Essence, Fragments and "
                       "Socketables tabs from the screen. You check the numbers before they're saved. Only looks: no keys, no clicks; the "
                       "picture is never kept."),
        ("Count by hand", "For a currency Scan stash can't read, under More ▾: press it, then hover each stack in game "
                         "and press Ctrl+C - stacks of the same currency add up. Double-click a quantity to change "
                         "it; select rows (Ctrl+A for all) and press Delete to remove them."),
        ("Prices", "Currency, fragments and other stackables come from poe.ninja. An item "
                   "poe.ninja doesn't list says not found on poe.ninja and isn't in the total."),
        ("Total and What moved it", "Total is everything added up; the chart shows it over time (Daily shows the change "
                                    "per day). What moved it splits the week's change into prices and amounts, and "
                                    "shows each item's week. Click it."),
        ("Snapshots", "Each count, scan or price update saves your total, so the chart and the Session timer can "
                      "show how much you made. Wealth ↳ Snapshots: pick one to look back, a second to compare."),
    ]

    def wealth_guide(self):
        """2.0 beta 21: what each part of Wealth does, in one place."""
        old = getattr(self, "_w_guide", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        from .overlaywin import OverlayWindow
        w = self.shell.windows.get("wealth")
        x = (w.winfo_rootx() + 60) if w is not None else self.root.winfo_rootx() + 200
        y = (w.winfo_rooty() + 60) if w is not None else self.root.winfo_rooty() + 120
        g = OverlayWindow(self.root, "How Wealth works", "💰", (x, y, 560, 520), opacity=255, body_bg=C["panel"],
                          app_colours=True, lockable=False, on_close=lambda: g.destroy())
        t = tk.Text(g.body, bg=C["panel"], fg=C["text"], relief="flat", wrap="word", padx=16, pady=8,
                    highlightthickness=0, font=("Segoe UI", 10), cursor="arrow")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", foreground=C["accent"], font=("Segoe UI", 12, "bold"), spacing1=8, spacing3=3)
        for head, body in self.WEALTH_GUIDE:
            t.insert("end", head + "\n", "h")
            t.insert("end", body + "\n")
        t.config(state="disabled")
        self._w_guide = g

    # ---------------- Count by hand (2.0 beta 7's Count currency; UI overhaul: its one name, and the only way to add
    # by hand - the typed form is gone): Ctrl+C on each stack while counting; Scan stash reads whole tabs
    def wealth_takes(self, text):
        """Does this copy belong to the Wealth window? A copied stack (currency, fragments, essences ...) does while you
        are counting, or while the Wealth window is the one in front."""
        from . import features as FEAT
        if not FEAT.on("wealth") or not parse_stack(text):          # Wealth is a beta feature (2.131.0: its own switch)
            return False
        return bool(self.w_counting)                 # (UI overhaul: only while you count - one way to add by hand)

    def wealth_clip(self, text):
        got = parse_stack(text)
        if not got:
            return
        name, qty, cls = got
        if self.w_counting:
            self.w_session.append((name, qty, cls))
            self.wealth_count_strip()
            self._say(f"Counted {name} x{qty:,}", 4)
            return
        have = WEALTH.holding(name)
        if not have:
            WEALTH.set_holding(name, qty, cls, src="counted")
            self._w_strip(f"Added {name} x{qty:,} to Counted.", [("Undo", lambda: (WEALTH.set_holding(name, 0),
                                                                                            self._w_strip_close(),
                                                                                            self.refresh_wealth(force=True)))])
            self.refresh_wealth(force=True)
            return
        self._w_strip(f"{name} x{qty:,} copied. You already have {have:,} counted.",
                      [(f"Add ({have + qty:,})", lambda: self._w_held_set(name, have + qty, cls)),
                       (f"Replace ({qty:,})", lambda: self._w_held_set(name, qty, cls)),
                       ("Type an amount…", lambda: self._w_held_ask(name, cls)),
                       ("Cancel", self._w_strip_close)], accent=0)

    def _w_strip(self, text, actions=(), accent=None):
        for w in self.w_cstrip_btns.winfo_children():
            w.destroy()
        self.w_cstrip_lbl.config(text=text)
        for i, (label, fn) in enumerate(actions):
            ttk.Button(self.w_cstrip_btns, text=label, command=fn,
                       style="Primary.TButton" if i == accent else "TButton").pack(side="left", padx=(8, 0))
        if not self.w_cstrip.winfo_ismapped():
            self.w_cstrip.pack(fill="x", pady=(0, 8), before=self.w_items_head)

    def _w_strip_close(self):
        self.w_cstrip.pack_forget()

    def wealth_count_toggle(self):
        if self.w_counting:
            return self.wealth_count_finish()
        self.w_counting, self.w_session = True, []
        self.wealth_show_page("Overview")
        self.wealth_count_strip()
        self.wealth_steps_refresh()

    def wealth_count_strip(self):
        tot, stacks = {}, {}
        for name, qty, _cls in self.w_session:
            tot[name] = tot.get(name, 0) + qty
            stacks[name] = stacks.get(name, 0) + 1
        if tot:
            parts = [f"{n} {q:,}" + (f" ({stacks[n]} stacks)" if stacks[n] > 1 else "") for n, q in tot.items()]
            body = "   ·   ".join(parts)
        else:
            body = "nothing yet"
        text = ("● Count by hand: hover each stack in game and press Ctrl+C. Stacks of the same currency add up. Finish "
                "replaces the amounts for everything you copied; the rest is kept.\n"
                + body)
        self._w_strip(text, [("Finish", self.wealth_count_finish), ("Undo last", self.wealth_count_undo),
                             ("Cancel", self.wealth_count_cancel)], accent=0)

    def wealth_count_undo(self):
        if self.w_session:
            name, qty, _c = self.w_session.pop()
            self._say(f"Took back {name} x{qty:,}", 4)
        self.wealth_count_strip()

    def wealth_count_cancel(self):
        self.w_counting, self.w_session = False, []
        self.wealth_steps_refresh()
        self._w_strip_close()

    def wealth_count_finish(self):
        tot, cls = {}, {}
        for name, qty, c in self.w_session:
            tot[name] = tot.get(name, 0) + qty
            cls[name] = c
        for name, q in tot.items():
            WEALTH.set_holding(name, q, cls[name], src="hand")
        self.wealth_count_cancel()
        if tot:
            self._w_tell(f"Counted {len(tot)} kind{'s' if len(tot) != 1 else ''} of currency: "
                         + ", ".join(f"{n} {q:,}" for n, q in tot.items()) + ".", "ok")
            lg = SETTINGS.get("league")
            if lg:
                threading.Thread(target=self._w_prices_then_snapshot, args=(lg,), daemon=True).start()
        self.refresh_wealth(force=True)
        if hasattr(self, "tracker_after_count"):           # 2.0 beta 9: the session tracker was waiting for this count
            self.tracker_after_count()

    def _w_held_set(self, name, qty, cls=""):
        WEALTH.set_holding(name, qty, cls, src="hand")
        self._w_strip_close()
        self.refresh_wealth(force=True)
        self._say(f"{name}: {qty:,} counted.", 6)

    def _w_held_ask(self, name, cls=""):
        from tkinter import simpledialog
        n = simpledialog.askinteger("How many?", f"How many {name} do you have in all?", parent=self.root,
                                    initialvalue=WEALTH.holding(name) or None, minvalue=0)
        if n is not None:
            self._w_held_set(name, n, cls)

    def _w_prices_then_snapshot(self, lg, why="counted"):
        try:
            WPRICES.ensure(lg)
            WEALTH.snapshot(lg, WPRICES, why)
        except Exception:
            buglog.caught()
        self.ui_q.put(("wealth", "prices"))

    def wealth_export_history(self):
        from .csvexport import write_wealth_history
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="wealth_history.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            n = write_wealth_history(path, WEALTH.snapshots, SETTINGS.get("league"))
            self._w_tell(f"Saved {n} snapshots to {path}.", "ok")

    def wealth_export_items(self):
        from .csvexport import write_wealth_items
        from .wealth import wealth_rows
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="wealth_items.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            rows, _total, _priced = wealth_rows(WEALTH.all_items(), WPRICES)
            n = write_wealth_items(path, rows)
            self._w_tell(f"Saved {n} items to {path}.", "ok")

    def wealth_remove_held(self):
        """(Older callers.) Delete removes the selected rows."""
        self.wealth_remove_rows(self.w_items.selection())

    def wealth_remove_rows(self, rows):
        """2.4.0: Delete removes the selected rows - one, several (Ctrl / Shift+click) or all (Ctrl+A). Counted stacks
        are gone until you count or scan them again. Ctrl+Z / Undo puts them back."""
        items = [it for r in rows for it in (self.w_rowitems.get(r) or [])]
        if not items:
            return
        held = [it for it in items if it.get("held")]
        synced = [it for it in items if not it.get("held")]
        with WEALTH.lock:
            old_hold = {it["type"]: dict(WEALTH.holdings[it["type"]]) for it in held if it["type"] in WEALTH.holdings}
            lids = {str(it["lid"]) for it in synced}
            old_items = {tid: list(lst) for tid, lst in WEALTH.items.items() if any(str(i["lid"]) in lids for i in lst)}
            for name in old_hold:
                WEALTH.holdings.pop(name, None)
            for tid in old_items:
                WEALTH.items[tid] = [i for i in WEALTH.items[tid] if str(i["lid"]) not in lids]
        WEALTH.save()
        n = len(held) + len(synced)
        label = f"{n} item{'s' if n != 1 else ''}"

        def restore():
            with WEALTH.lock:
                WEALTH.holdings.update(old_hold)
                WEALTH.items.update(old_items)
            WEALTH.save()
            self.refresh_wealth(force=True)
        self.push_undo("wealth", label, restore)
        self._w_tell(f"Removed {label}. Ctrl+Z or Undo puts them back.", "ok")
        self.refresh_wealth(force=True)

    def wealth_clear_items(self):
        """2.4.0: empty the item list (what you counted, scanned or added). History stays."""
        n = len(WEALTH.holdings) + sum(len(v) for v in WEALTH.items.values())
        if not n:
            return self._w_tell("The list is already empty.", "note")
        if not messagebox.askyesno("Clear Wealth items",
                                   f"Clear all {n:,} items from the list?\n\nYour history - the chart and snapshots - "
                                   "stays. Scan stash fills it again.\n\n"
                                   "You can undo this with Ctrl+Z or the Undo button.", parent=self.dlg_parent()):
            return
        with WEALTH.lock:
            old_hold, old_items = dict(WEALTH.holdings), dict(WEALTH.items)
            WEALTH.holdings.clear()
            WEALTH.items = {}
        WEALTH.save()

        def restore():
            with WEALTH.lock:
                WEALTH.holdings.update(old_hold)
                WEALTH.items.update(old_items)
            WEALTH.save()
            self.refresh_wealth(force=True)
        self.push_undo("wealth", f"{n:,} items", restore)
        self._w_tell(f"Cleared {n:,} items. Ctrl+Z or Undo puts them back.", "ok")
        self.refresh_wealth(force=True)

    def wealth_remove_snaps(self, rows):
        """2.4.0: Delete removes the selected snapshots (points on the chart)."""
        idx = sorted({int(r) for r in rows if str(r).isdigit()}, reverse=True)
        with WEALTH.lock:
            gone = [(i, WEALTH.snapshots[i]) for i in idx if i < len(WEALTH.snapshots)]
            for i, _sn in gone:
                del WEALTH.snapshots[i]
        if not gone:
            return
        WEALTH.save()
        label = f"{len(gone)} snapshot{'s' if len(gone) != 1 else ''}"

        def restore():
            with WEALTH.lock:
                for i, sn in sorted(gone):
                    WEALTH.snapshots.insert(min(i, len(WEALTH.snapshots)), sn)
            WEALTH.save()
            self.refresh_wealth(force=True)
            self.wealth_side()
        self.push_undo("wealth", label, restore)
        self._w_tell(f"Removed {label}. Ctrl+Z or Undo puts them back.", "ok")
        self.refresh_wealth(force=True)
        self.wealth_side()

    # ---------------- 2.0 beta 7: side list, breakdown, filters
    def wealth_side(self):
        """The Snapshots page (P3, 2.105.1: what happened, the change since the one before)."""
        lg = SETTINGS.get("league", "")
        mine = [(i, sn) for i, sn in enumerate(WEALTH.snapshots) if sn.get("league") == lg]
        rows = []
        for k in range(len(mine) - 1, -1, -1):
            i, sn = mine[k]
            prev = mine[k - 1][1] if k else None
            d = sn["total"] - prev["total"] if prev else None
            rows.append((str(i), dict(values=(datetime.fromtimestamp(sn["ts"]).strftime("%b %d %H:%M"),
                                              self.SNAP_WHY.get(sn.get("why", ""), (sn.get("why") or "").capitalize()),
                                              fmt_div(sn["total"]),
                                              "" if d is None else f"{'▲ +' if d >= 0 else '▼ -'}{fmt_div(abs(d))}"))))
        tv_sync(self.w_snaps, rows)                        # (UI rule 22: the picked row and the scroll stay)

    def wealth_pick_tab(self, tid):
        self.w_tabfilter = tid
        self.wealth_side()
        self.wealth_fill_items()

    def wealth_clear_filters(self):
        self.w_tabfilter = None
        self.w_from.pick("All", notify=False)
        self.wealth_side()
        self.wealth_fill_items()

    def wealth_pick_snapshot(self):
        """P3 (2.105.1): the picked snapshot beside the list - its total and each kind, against the one before (or
        against a second one, Ctrl+click)."""
        sel = self.w_snaps.selection()
        lg = SETTINGS.get("league", "")
        if len(sel) == 2:
            a, b = sorted((WEALTH.snapshots[int(i)] for i in sel), key=lambda s: s["ts"])
            txt = self.wealth_compare(a, b)
            self.w_snap_info.config(text=txt, fg=C["text"])
            self._snap_cats(b, a)
            return
        self.w_snap_sel = int(sel[0]) if sel else None
        if self.w_snap_sel is None:
            self.w_snap_info.config(text="Pick a snapshot to see what it held.", fg=C["muted"])
            self._snap_cats(None, clear=True)
        else:
            sn = WEALTH.snapshots[self.w_snap_sel]
            before = [x for x in WEALTH.snapshots[:self.w_snap_sel] if x.get("league") == lg]
            prev = before[-1] if before else None
            self.w_snap_info.config(fg=C["text"], text=(
                f"{datetime.fromtimestamp(sn['ts']).strftime('%b %d %H:%M')}  ·  "
                f"{self.SNAP_WHY.get(sn.get('why', ''), sn.get('why', ''))}\n{fmt_div(sn['total'])}"
                + ("   vs the one before" if prev else "")))
            self._snap_cats(sn, prev)

    def _snap_cats(self, sn, prev=None, clear=False):
        """The kinds of one snapshot, one row each. UI rule 22: the three labels of a row are made once and re-worded
        for the next snapshot picked (more rows are added; fewer rows are hidden)."""
        P2 = C["panel2"]
        cats = [] if clear else [x for x in sorted((sn.get("by_cat") or {}).items(), key=lambda kv: -kv[1]) if x[1]]
        box = self.w_snap_cats
        rows = box.__dict__.setdefault("_snap_rows", [])
        if any(not l1.winfo_exists() for l1, _l2, _l3 in rows):
            rows.clear()
        while len(rows) < len(cats):
            r = len(rows)
            rows.append((tk.Label(box, bg=P2, fg=C["muted"], anchor="w"),
                         tk.Label(box, bg=P2, fg=C["text"], anchor="e"), tk.Label(box, bg=P2, anchor="e")))
            rows[r][0].grid(row=r, column=0, sticky="w")
            rows[r][1].grid(row=r, column=1, sticky="e", padx=(12, 0))
            rows[r][2].grid(row=r, column=2, sticky="e", padx=(12, 0))
        for r, (l1, l2, l3) in enumerate(rows):
            if r >= len(cats):
                for lab in (l1, l2, l3):
                    lab.grid_remove()
                continue
            c, v = cats[r]
            d = v - (prev.get("by_cat") or {}).get(c, 0) if prev else None
            set_cfg(l1, text=self.CAT_INFO.get(c, ("", c.title()))[1])
            set_cfg(l2, text=fmt_div(v))
            l1.grid()
            l2.grid()
            if d is None:
                l3.grid_remove()
            else:
                set_cfg(l3, text=f"{'+' if d >= 0 else '-'}{fmt_div(abs(d))}",
                        fg=C["green"] if d > 0 else C["red"] if d < 0 else C["muted"])
                l3.grid()
        box.columnconfigure(0, weight=1)

    def wealth_compare(self, a, b):
        """A line saying what changed between two snapshots, biggest changes first."""
        d = b["total"] - a["total"]
        when = (f"From {datetime.fromtimestamp(a['ts']).strftime('%b %d %H:%M')} to "
                f"{datetime.fromtimestamp(b['ts']).strftime('%b %d %H:%M')}")
        cats = set(a.get("by_cat") or {}) | set(b.get("by_cat") or {})
        ch = sorted(((c, (b.get("by_cat") or {}).get(c, 0) - (a.get("by_cat") or {}).get(c, 0)) for c in cats),
                    key=lambda x: -abs(x[1]))
        parts = [f"{self.CAT_INFO.get(c, ('', c))[1]} {'+' if v >= 0 else '-'}{fmt_div(abs(v))}"
                 for c, v in ch if abs(v) >= 0.01][:5]
        return (f"{when}: {'+' if d >= 0 else '-'}{fmt_div(abs(d))} in total"
                + (" (" + ", ".join(parts) + ")" if parts else "") + ".")

    @staticmethod
    def _w_cat(it):
        c = (it.get("cat") or "other").split(".")[0].lower()
        return c if c in WealthPage.CAT_INFO else "other"

    # ---------------- 2.75.0: the setup steps on the Overview (were a pop-up guide), then one status line
    def wealth_step_state(self):
        """P3 (2.105.1): -> (counted or scanned anything)."""
        return bool(WEALTH.holdings)

    def wealth_steps_done(self):
        return self.wealth_step_state()

    def wealth_steps_again(self):
        SETTINGS["wealth_steps_hidden"] = False
        SETTINGS["wealth_steps_force"] = True
        save_json("settings.json", SETTINGS)
        self.wealth_show_page("Overview")
        self.wealth_steps_refresh()

    def wealth_steps_hide(self):
        SETTINGS["wealth_steps_hidden"] = True
        SETTINGS["wealth_steps_force"] = False
        save_json("settings.json", SETTINGS)
        self.wealth_steps_refresh()

    def wealth_steps_refresh(self):
        top = self.w_steps_top
        for w in top.winfo_children():
            w.destroy()
        steps = (SETTINGS.get("wealth_steps_force") or not self.wealth_steps_done()) and \
            not SETTINGS.get("wealth_steps_hidden")
        self.w_steps_shown = bool(steps)
        if steps:
            self._wealth_steps(top)
        else:
            self._wealth_status(top)

    def _wealth_steps(self, top):
        """P3 (2.105.1): the first time - two ways to fill it, side by side (use either or both)."""
        P1, P2 = C["panel"], C["panel2"]
        box = tk.Frame(top, bg=P2, padx=16, pady=12, highlightthickness=1, highlightbackground=C["line"])
        box.pack(fill="x")
        self.w_steps = box
        tk.Label(box, text="See everything you own, in divines", bg=P2, fg=C["text"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(box, text="Two ways to fill it - use either or both. Everything stays on your PC.", bg=P2,
                 fg=C["muted"], anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(2, 8))
        row = tk.Frame(box, bg=P2)
        row.pack(fill="x")
        row.columnconfigure(0, weight=1, uniform="w")
        row.columnconfigure(1, weight=1, uniform="w")
        self.w_step_btns = {}

        def card(col, title, text, label, fn, main):
            f = tk.Frame(row, bg=P1, padx=12, pady=8, highlightthickness=1,
                         highlightbackground=C["accent"] if main else C["line"])
            f.grid(row=0, column=col, sticky="nsew", padx=(0, 8) if col == 0 else (6, 0))
            mid = tk.Frame(f, bg=P1)
            mid.pack(side="left", fill="x", expand=True)
            tk.Label(mid, text=title, bg=P1, fg=C["text"], font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            tk.Label(mid, text=text, bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=300).pack(fill="x")
            b = ttk.Button(f, text=label, command=fn, style="Primary.TButton" if main else "TButton")
            b.pack(side="right", padx=(8, 0))
            self.w_step_btns[(col + 1, label)] = b
        card(0, "Scan stash", "Reads your Currency, Abyss, Delirium, Breach, Expedition, Ritual, Essence and Fragments "
                              "tabs from the screen. You check the numbers before they're saved.", "Scan stash…",
             self.stash_scan_start, True)
        card(1, "Count by hand", "For a currency Scan stash can't read: press it, then Ctrl+C each stack in game.",
             "Finish counting" if self.w_counting else "Count by hand…", self.wealth_count_toggle, False)
        try:                                     # 2.120.0 (UX pass 2: one orange button a page): the card's Scan
            self.w_scan_btn.config(style="TButton")    # stash is the one while the setup cards show
        except (AttributeError, tk.TclError):
            pass

    def _wealth_status(self, top):
        """After the first count: one line - items with no price found; clickable."""
        try:                                     # 2.135.0: no setup cards - Scan stash is the page's orange button
            self.w_scan_btn.config(style="Primary.TButton")
        except (AttributeError, tk.TclError):
            pass
        if not WEALTH.holdings:
            return
        P1 = C["panel"]
        rows = getattr(self, "w_rows", [])
        self.w_status = tk.Frame(top, bg=P1)
        self.w_status.pack(fill="x")
        self.w_status_chips = {}

        def chip(key, mark, col, text, sub, link, fn):
            f = tk.Frame(self.w_status, bg=C["panel2"], padx=12, pady=8, highlightthickness=1,
                         highlightbackground=C["line"], cursor="hand2")
            f.pack(fill="x", pady=(0, 8))               # (the full row: its edges line up with the number cards)
            from . import soft
            soft.round_frame(f, outside=lambda: P1)     # a soft card like Stash worth, not a square box
            parts = [tk.Label(f, text=mark, bg=C["panel2"], fg=col, font=("Segoe UI", 10, "bold")),
                     tk.Label(f, text=text, bg=C["panel2"], fg=C["text"], font=("Segoe UI", 10)),
                     tk.Label(f, text=sub, bg=C["panel2"], fg=C["muted"], font=("Segoe UI", 9))]
            if link:
                parts.append(tk.Label(f, text=link, bg=C["panel2"], fg=C["accent"], font=("Segoe UI", 9, "bold")))
            for w in parts:
                w.pack(side="left", padx=(0, 8))
            for w in [f] + parts:
                w.bind("<Button-1>", lambda e: fn())
            self.w_status_chips[key] = f
        counted = sum(tot or 0 for it, _e, tot, _s in rows if it.get("held"))
        last_count = max((sn["ts"] for sn in WEALTH.snapshots if sn.get("why") in ("counted", "scanned")), default=None)
        _ = counted, last_count                  # (UI overhaul: when you scanned and the total are the number cards)
        need = sum(1 for _it, each, _t, _s in rows if each is None)
        if need:
            chip("price", "●", C["orange"], f"{need} item{'s' if need != 1 else ''}: no price found", "", "Show ›",
                 self.wealth_show_unpriced)

    def wealth_show_unpriced(self):
        """The items with no price found: selected in the list, the first one scrolled into view."""
        self.wealth_show_page("Overview")
        rows = [iid for iid in self.w_items.get_children()
                if (self.w_items.item(iid, "values") or ("",) * 4)[3] == "—"]
        if rows:
            self.w_items.selection_set(rows)
            self.w_items.see(rows[0])

    def _w_tell(self, text, kind="error"):
        """Say something on the Wealth page itself (and in the status line)."""
        if not hasattr(self, "w_msg"):
            return self._say(text, 15)
        self.w_msg.config(text=text, fg={"error": C["red"], "ok": C["green"], "note": C["good"]}.get(kind, C["muted"]))
        self._say(text, 15)

    def wealth_update_prices(self):
        lg = SETTINGS.get("league")
        if not lg:
            return self._say("Pick a league first.", 8)
        self.w_price_btn.config(state="disabled")
        self.w_msg.config(text="Updating prices from poe.ninja…", fg=C["muted"])

        def work():
            try:
                WPRICES.ensure(lg, force=True)
                WEALTH.snapshot(lg, WPRICES, "prices updated")
            except Exception as e:
                WPRICES.errors = [str(e)[:120]]
            self.ui_q.put(("wealth", "prices"))
        threading.Thread(target=work, daemon=True).start()

    def wealth_amount_click(self, e):
        """Double-click a counted stack's From or Quantity: change the amount. (3.0.4, owner: prices are never typed
        by hand.)"""
        iid = self.w_items.identify_row(e.y)
        it = self.w_rowmap.get(iid)
        if it and it.get("held") and self.w_items.identify_column(e.x) in ("#2", "#3"):
            self._w_held_ask(it["type"])

    def wealth_item_menu(self, e):
        """Right-click a counted stack: change the amount."""
        iid = self.w_items.identify_row(e.y)
        it = self.w_rowmap.get(iid)
        if not it or not it.get("held"):
            return
        self.w_items.selection_set(iid)
        m = menu_theme(self.root)
        m.add_command(label="Change the amount…", command=lambda: self._w_held_ask(it["type"]))
        m.tk_popup(e.x_root, e.y_root)

    def wealth_sort(self, col):
        self.w_sort_rev = not self.w_sort_rev if self.w_sort_col == col else col in ("qty", "each", "total")
        self.w_sort_col = col
        self.wealth_fill_items()

    # ---------------- events from the price update's thread
    def ev_wealth(self, kind):
        if kind == "prices":
            self.w_price_btn.config(state="normal")
            msg = "Prices updated." if not WPRICES.errors else "Prices updated, but some poe.ninja categories failed."
            self.w_msg.config(text=msg, fg=C["green"] if not WPRICES.errors else C["good"])
            self.refresh_wealth(force=True)

    # ---------------- drawing
    def refresh_wealth(self, force=False):
        if not force and not self.page_open("Wealth"):
            return
        rows, total, priced = wealth_rows(WEALTH.all_items(), WPRICES)
        self.w_rows = rows
        self.wealth_steps_refresh()                          # (P3: after the rows - the status line adds them up)

        lg = SETTINGS.get("league", "")
        self.w_total.config(text=fmt_div(total) if rows else "No items yet", fg=C["good"] if rows else C["muted"],
                            font=("Segoe UI", 22 if rows else 13, "bold"))
        bits = []                                            # 2.75.0: what was done when, on every page
        last_count = max((sn["ts"] for sn in WEALTH.snapshots if sn.get("why") in ("counted", "scanned")), default=None)
        if last_count:
            bits.append(f"Counted {self._w_ago(last_count)}")
        if WPRICES.ts:
            bits.append(f"prices {self._w_ago(WPRICES.ts)}")
        self.w_synced.config(text="  ·  ".join(bits))
        eq = []
        for cid, name in (("exalted", "Exalted"), ("chaos", "Chaos")):
            r = RATES.value(cid) or (WPRICES.by_name.get(f"{name.lower()} orb") or (None,))[0]
            if r and rows:
                eq.append(f"{_amt(total / r)} {name}")
        self.w_equiv.config(text=("or about " + " or ".join(eq)) if eq else "")
        snaps = [s for s in WEALTH.snapshots if s.get("league") == lg]
        delta = ""
        if snaps and rows:
            prev = self.wealth_compare_point(snaps)
            if prev:
                d = total - prev["total"]
                delta = f"{'+' if d >= 0 else '-'}{fmt_div(abs(d))}"
                self.w_delta_since = self.wealth_since_words(prev["ts"])
                self.w_delta.config(fg=C["green"] if d >= 0 else C["red"])
        self.w_delta.config(text=delta)
        facts = []
        if rows:
            facts.append(f"{priced} of {len(rows)} items priced all in divines."
                         + (f" {len(rows) - priced} without a price aren't in the total." if priced < len(rows) else ""))
        if WPRICES.ts:
            facts.append(f"Prices from poe.ninja, {self._w_ago(WPRICES.ts)}.")
        if WPRICES.errors:
            facts.append(f"{len(WPRICES.errors)} poe.ninja categories failed last time.")
        if delta:
            word = "Up" if not delta.startswith("-") else "Down"
            facts.insert(0, f"{word} {delta.lstrip('+-')} {getattr(self, 'w_delta_since', '')}.")
        self.w_facts.config(text="  ".join(facts))
        self.wealth_tiles(rows, total, priced, delta, eq, last_count)
        self.wealth_side()
        self.wealth_moved()
        self.wealth_draw_chart()
        self.wealth_fill_items()

    def wealth_tiles(self, rows, total, priced, delta, eq, last_count):
        """UI overhaul: Stash worth, the change, the same in Exalted, and when you last counted - with how each was
        worked out."""
        tiles = getattr(self, "w_tiles", None)
        if tiles is None:
            return
        from .cards import Tile
        up = delta and not delta.startswith("-")
        since = getattr(self, "w_delta_since", "")
        tiles.set([
            Tile("Stash worth", fmt_div(total) if rows else "—",
                 f"{priced:,} of {len(rows):,} items priced" if rows else "Press Scan stash to start", "text_muted",
                 "Each item's price from poe.ninja times how many you hold, added up. "
                 "Items without a price aren't in it."),
            Tile("Change", delta or "—", (f"▲ Up {since}" if up else f"▼ Down {since}") if delta else
                 "Shows from your second scan", ("good" if up else "bad") if delta else "text_muted",
                 "Stash worth now, minus your snapshot from about a day ago, or the last one at least 30 minutes old."),
            Tile("In Exalted", eq[0].split(" ")[0] if eq else "—", "at poe.ninja's rate" if eq else "No rate yet",
                 "text_muted", "Stash worth divided by what one Exalted Orb is worth in divines, from poe.ninja."),
            Tile("Last stash scan", self._w_ago(last_count) if last_count else "—",
                 f"prices updated {self._w_ago(WPRICES.ts)}" if WPRICES.ts else "No prices yet", "text_muted",
                 "When you last pressed Scan stash. Prices update by themselves from poe.ninja about "
                 "hourly - that doesn't count your stash again."),
        ])

    @staticmethod
    def wealth_compare_point(snaps, now=None):
        """The snapshot to compare today's total with (2.3.0): one from about a day ago if there is one, else the
        last one at least 30 minutes old."""
        now = now or time.time()
        day = [s for s in snaps if 18 * 3600 <= now - s["ts"] <= 48 * 3600]
        if day:
            return min(day, key=lambda s: abs((now - s["ts"]) - 86400))
        return next((s for s in reversed(snaps) if now - s["ts"] >= 1800), None)

    @staticmethod
    def wealth_since_words(ts, now=None):
        now = now or time.time()
        age = now - ts
        if 18 * 3600 <= age <= 48 * 3600:
            return "since yesterday"
        if age < 18 * 3600:
            h = max(1, round(age / 3600))
            return f"in the last {h} hour{'s' if h != 1 else ''}"
        return f"since {datetime.fromtimestamp(ts).strftime('%b %d')}"

    @staticmethod
    def _w_ago(ts):
        return "just now" if time.time() - ts < 60 else ago(ts)

    def wealth_fill_items(self):
        rows = getattr(self, "w_rows", [])
        needle = self.w_filter.get().strip().lower()
        shown = []
        for it, each, tot, src in rows:
            if self.w_tabfilter is not None and it["stash"] != self.w_tabfilter:
                continue
            name = wealth_display_name(it)
            if needle and needle not in name.lower() and not any(needle in m.lower() for m in it["mods"]):
                continue
            shown.append([it, name, it["qty"], each, tot, src, 1, [it]])
        merged = {}                                      # 3.0.4: stacks of one item are always one row
        for r in shown:
            it = r[0]
            k = it["lid"] if it["frame"] in (1, 2) else (it["stash"], r[1], it["corrupted"], r[3])
            if k in merged:
                m = merged[k]
                m[2] += r[2]
                m[4] = (m[4] or 0) + (r[4] or 0) if m[4] is not None else None
                m[6] += 1
                m[7] = m[7] + r[7]
            else:
                merged[k] = list(r)
        shown = list(merged.values())
        col = self.w_sort_col
        trend = {id(r): self._w_trend(r[0], r[4]) for r in shown}
        keyf = {"item": lambda r: r[1].lower(), "tab": lambda r: r[0]["stash"].lower(), "qty": lambda r: r[2],
                "each": lambda r: r[3] if r[3] is not None else -1, "total": lambda r: r[4] if r[4] is not None else -1,
                "chg": lambda r: trend[id(r)][0] if trend[id(r)] else -1e9,
                "wchg": lambda r: trend[id(r)][1] if trend[id(r)] and trend[id(r)][1] is not None else -1e9,
                "src": lambda r: r[5] or ""}[col]
        shown.sort(key=keyf, reverse=self.w_sort_rev)
        self.w_rowmap, self.w_rowitems = {}, {}
        rarity_tag = {1: "magic", 2: "rare", 3: "unique", 4: "gem"}
        from .rates_view import picture_paths, url_for
        paths = picture_paths()
        out = []
        for n, (it, name, qty, each, tot, src, stacks, parts) in enumerate(shown):
            tags = (["held"] if it.get("held") else [rarity_tag.get(it["frame"], "")]) if each is not None else ["none"]
            tr = trend.get(id(shown[n]))
            if n % 2:
                tags.append("odd")
            label = name + (f"   ({stacks} stacks)" if stacks > 1 else "") + ("   corrupted" if it["corrupted"] else "")
            base_name = name.split("   ")[0]
            pic = ((self.w_icons.get(url_for(base_name, paths)) or self.w_local.get(base_name))
                   if hasattr(self, "w_icons") else None)
            k = it["lid"] if it["frame"] in (1, 2) else (it["stash"], name, it["corrupted"], each)
            iid = "w" + str(abs(hash(k)))                    # (UI rule 22: a row keeps its id, so a typed filter or a
            out.append((iid, dict(tags=[t for t in tags if t], image=pic or "",          # new price changes cells)
                                  values=(label, it["stash"], f"{qty:,}", fmt_div(each) if each is not None else "—",
                                          fmt_div(tot) if tot is not None else "",
                                          self._w_pct(tr[0]) if tr else "",
                                          self._w_signed(tr[1]) if tr and tr[1] is not None else "",
                                          src or "No price found: " + self._w_why_unpriced(it)))))
            self.w_rowmap[iid] = it
            self.w_rowitems[iid] = parts
        tv_sync(self.w_items, out)
        filt = []
        if self.w_tabfilter is not None:
            filt.append(self.w_tabfilter)
        if filt:
            self.w_filter_chip.config(text="Showing: " + " · ".join(filt) + "   ✕")
            if not self.w_filter_chip.winfo_ismapped():
                self.w_filter_chip.pack(side="left", padx=(8, 0))
        else:
            self.w_filter_chip.pack_forget()
        shown_total = sum(r[4] or 0 for r in shown)
        self.w_count.config(text=f"{len(shown)} shown, worth {fmt_div(shown_total)}.   Click an item for its week; "
                                 f"double-click a quantity to change it. Select rows and press Delete to remove them. "
                                 f"Ctrl+Z undoes.")
        if rows or getattr(self, "w_steps_shown", False):
            self.w_empty.place_forget()
        else:
            self.w_empty.place(relx=0.5, y=40, anchor="n")

    # ---------------- 3.0.4: What moved it (the week's change: prices vs amounts, each item's week)
    @staticmethod
    def _w_trend(it, tot):
        """-> (price change % over 7 days, your worth change in divines or None, [points]) or None."""
        t = WPRICES.trend(it)
        if not t:
            return None
        pct, pts = t
        eff = tot - tot / (1 + pct / 100.0) if tot is not None and pct > -100 else None
        return pct, eff, pts

    @staticmethod
    def _w_pct(p):
        if abs(p) < 0.05:
            return "• 0%"
        return f"{'▲ +' if p > 0 else '▼ −'}{abs(p):.1f}%"

    @staticmethod
    def _w_each(v):
        return fmt_div(v) if v >= 0.1 else f"{v:.3g} div"

    @staticmethod
    def _w_signed(d):
        if abs(d) < 0.005:
            return "0 div"
        return f"{'+' if d > 0 else '−'}{fmt_div(abs(d))}"

    def _w_week_snapshot(self, now=None):
        """The snapshot from about 7 days ago (5 to 9 days), closest to 7, or None."""
        now = now or time.time()
        lg = SETTINGS.get("league", "")
        near = [s for s in WEALTH.snapshots if s.get("league") == lg and 5 * 86400 <= now - s["ts"] <= 9 * 86400]
        return min(near, key=lambda s: abs((now - s["ts"]) - 7 * 86400)) if near else None

    def _w_moved_rows(self):
        """Every priced row with a 7-day price, combined by name -> {name: [qty, total, pct, effect, pts]}."""
        out = {}
        for it, _each, tot, _src in getattr(self, "w_rows", []):
            tr = self._w_trend(it, tot)
            if not tr or tr[1] is None:
                continue
            name = wealth_display_name(it)
            r = out.setdefault(name, [0, 0.0, tr[0], 0.0, tr[2]])
            r[0] += it["qty"]
            r[1] += tot
            r[3] += tr[1]
        return out

    def wealth_pick_moved_row(self):
        sel = self.w_items.selection()
        if len(sel) != 1:
            return
        it = self.w_rowmap.get(sel[0])
        if it is not None:
            self.wealth_pick_moved(wealth_display_name(it))

    def wealth_pick_moved(self, name):
        self.w_mv_item = name
        self.wealth_moved()

    def _w_spark(self, parent, pts, w=80, h=22, bg=None):
        """A small line of the week (no axes). Up / down also says it in words beside it."""
        cv = tk.Canvas(parent, width=w, height=h, bg=bg or C["panel2"], highlightthickness=0)
        vals = [p for p in pts if p is not None]
        if len(vals) >= 2:
            lo, hi = min(vals), max(vals)
            span = (hi - lo) or 1.0
            xy = []
            for i, p in enumerate(pts):
                if p is None:
                    continue
                xy += [2 + i * (w - 4) / max(1, len(pts) - 1), h - 3 - (p - lo) / span * (h - 6)]
            col = C["green"] if vals[-1] > vals[0] else C["red"] if vals[-1] < vals[0] else C["muted"]
            cv.create_line(*xy, fill=col, width=2, smooth=False)
        return cv

    def wealth_moved(self):
        box = getattr(self, "w_mv", None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        P2 = C["panel2"]
        moved = self._w_moved_rows()
        if self.w_mv_item and self.w_mv_item not in moved:
            self.w_mv_item = None
        if self.w_mv_item:
            return self._w_moved_item(box, self.w_mv_item, moved[self.w_mv_item])
        if not moved:
            tk.Label(box, text="No 7-day prices yet.\nThey come with the next price update from poe.ninja.",
                     bg=P2, fg=C["muted"], justify="left", anchor="w").pack(fill="x", pady=8)
            return
        prices = sum(r[3] for r in moved.values())
        unpriced = sum(1 for _it, e, _t, _s in getattr(self, "w_rows", []) if e is not None) - sum(
            1 for _it, e, t, _s in getattr(self, "w_rows", []) if e is not None and self._w_trend(_it, t))

        def line(mark_word, value, tip, col):
            f = tk.Frame(box, bg=C["odd"], padx=8, pady=2)      # (compact: the price moves stay in view)
            f.pack(fill="x", pady=(0, 4))
            a = tk.Label(f, text=mark_word, bg=C["odd"], fg=C["text"], font=("Segoe UI", 10), anchor="w")
            a.pack(side="left")
            b = tk.Label(f, text=value, bg=C["odd"], fg=col, font=("Segoe UI", 12, "bold"), anchor="e")
            b.pack(side="right")
            for x in (f, a, b):
                Tooltip(x, tip)
        up = prices >= 0
        line(("▲ Prices went up" if up else "▼ Prices went down") if abs(prices) >= 0.005 else "• Prices held",
             self._w_signed(prices),
             f"Your {len(moved)} item{'s' if len(moved) != 1 else ''} with a 7-day price: amount × (price now − price "
             f"7 days ago), added up = {self._w_signed(prices)}."
             + (f" {unpriced} priced item{'s' if unpriced != 1 else ''} have no 7-day price and aren't in it."
                if unpriced > 0 else ""),
             C["green"] if up else C["red"])
        wk = self._w_week_snapshot()
        total_now = sum(t or 0 for _i, _e, t, _s in getattr(self, "w_rows", []))
        if wk:
            amounts = (total_now - wk["total"]) - prices
            more = amounts >= 0
            line(("▲ You hold more" if more else "▼ You hold less") if abs(amounts) >= 0.005 else "• Same amounts",
                 self._w_signed(amounts),
                 f"Change since {datetime.fromtimestamp(wk['ts']).strftime('%b %d')}: now {fmt_div(total_now)} − then "
                 f"{fmt_div(wk['total'])} = {self._w_signed(total_now - wk['total'])}; minus the price part "
                 f"{self._w_signed(prices)} = {self._w_signed(amounts)}.",
                 C["green"] if more else C["red"])
        else:
            tk.Label(box, text="You hold more / less: needs a snapshot from about 7 days ago.", bg=P2, fg=C["muted"],
                     anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(0, 8))
        tk.Label(box, text="BIGGEST PRICE MOVES", bg=P2, fg=C["muted"], anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(2, 2))
        for name, (qty, tot, pct, eff, pts) in sorted(moved.items(), key=lambda kv: -abs(kv[1][3]))[:3]:
            f = tk.Frame(box, bg=P2, cursor="hand2")
            f.pack(fill="x", pady=1)
            parts = [tk.Label(f, text=name, bg=P2, fg=C["text"], anchor="w")]
            parts[0].pack(side="left", fill="x", expand=True)
            e = tk.Label(f, text=self._w_signed(eff), bg=P2, fg=C["green"] if eff > 0 else C["red"] if eff < 0 else
                         C["muted"], width=10, anchor="e")
            e.pack(side="right")
            pc = tk.Label(f, text=self._w_pct(pct), bg=P2, fg=C["text"], width=9, anchor="e")
            pc.pack(side="right")
            sp = self._w_spark(f, pts)
            sp.pack(side="right", padx=8)
            for x in [f, sp, pc, e] + parts:
                x.bind("<Button-1>", lambda ev, n=name: self.wealth_pick_moved(n))
                Tooltip(x, f"{qty:,} × price change {self._w_pct(pct)} = {self._w_signed(eff)}. Click for its week.")

    def _w_moved_item(self, box, name, r):
        """One item's week: its price line in divines, then and now, and what it did to your worth."""
        qty, tot, pct, eff, pts = r
        P2 = C["panel2"]
        top = tk.Frame(box, bg=P2)
        top.pack(fill="x")
        back = tk.Label(top, text="‹ All items", bg=P2, fg=C["accent"], cursor="hand2", font=("Segoe UI", 9, "bold"))
        back.pack(side="left")
        back.bind("<Button-1>", lambda e: self.wealth_pick_moved(None))
        tk.Label(top, text=name, bg=P2, fg=C["text"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left",
                                                                                                    padx=(12, 0))
        now_each = tot / qty if qty else 0
        then_each = now_each / (1 + pct / 100.0) if pct > -100 else None
        cv = tk.Canvas(box, height=84, bg=P2, highlightthickness=0)
        cv.pack(fill="x", pady=4)

        def draw(_e=None):
            cv.delete("all")
            W, H = max(cv.winfo_width(), 200), 84
            vals = [(i, (1 + p / 100.0) * (then_each or 0)) for i, p in enumerate(pts) if p is not None]
            if len(vals) < 2 or not then_each:
                return
            lo, hi = min(v for _i, v in vals), max(v for _i, v in vals)
            span = (hi - lo) or (hi or 1) * 0.01
            n = max(1, len(pts) - 1)
            xy = []
            for i, v in vals:
                x = 62 + i * (W - 74) / n
                y = H - 18 - (v - lo) / span * (H - 30)
                xy.append((x, y))
            for y, v in ((12, hi), (H - 18, lo)):
                cv.create_line(62, y, W - 8, y, fill=C["line"], dash=(2, 3))
                cv.create_text(58, y, text=f"{v:.3g}", fill=C["muted"], anchor="e", font=("Segoe UI", 8))
            col = C["green"] if pct > 0 else C["red"] if pct < 0 else C["muted"]
            cv.create_line(*[c for p in xy for c in p], fill=col, width=2)
            for x, y in xy:
                cv.create_oval(x - 3, y - 3, x + 3, y + 3, fill=col, outline="")
            cv.create_text(62, H - 2, text="7 days ago", fill=C["muted"], anchor="sw", font=("Segoe UI", 8))
            cv.create_text(W - 8, H - 2, text="now", fill=C["muted"], anchor="se", font=("Segoe UI", 8))
        cv.bind("<Configure>", draw)
        self.root.after(30, draw)
        facts = tk.Frame(box, bg=P2)
        facts.pack(fill="x")
        for k, (lab, val, tip) in enumerate((
                ("Price now", self._w_each(now_each), "poe.ninja's price now, in divines."),
                ("7 days ago", self._w_each(then_each) if then_each else "—",
                 f"Price now ÷ (1 {'+' if pct >= 0 else '−'} {abs(pct):.1f}%), from poe.ninja's 7-day line."),
                ("Change", self._w_pct(pct), "Price now against 7 days ago."),
                ("Your worth", self._w_signed(eff),
                 f"You hold {qty:,}: {qty:,} × (price now − 7 days ago) = {self._w_signed(eff)}."))):
            c = tk.Frame(facts, bg=P2)
            c.grid(row=0, column=k, sticky="w", padx=(0, 16))
            a = tk.Label(c, text=lab.upper(), bg=P2, fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w")
            a.pack(anchor="w")
            b = tk.Label(c, text=val, bg=P2, fg=C["text"], font=("Segoe UI", 12, "bold"), anchor="w")
            b.pack(anchor="w")
            for x in (c, a, b):
                Tooltip(x, tip)

    @staticmethod
    def _w_why_unpriced(it):
        return WPRICES.why_unpriced(it)

    def _w_chart_hover(self, e):
        """UI overhaul: the point under the mouse - its day, its total and the change from the one before."""
        cv = self.w_chart
        cv.delete("hov")
        pts = getattr(self, "_w_chart_pts", None)
        if not pts or self.w_mode.get() == "Daily":
            return
        i = min(range(len(pts)), key=lambda k: abs(pts[k][0] - e.x))
        x, y, t, v = pts[i]
        from . import themes as _th
        th = _th.ST.theme
        with _th.raw():
            brass, surf, edge, txt, mut = (th.c("accent_2"), th.c("surface_high"), th.c("border_light"),
                                           th.c("text_strong"), th.c("text_muted"))
            cv.create_line(x, 6, x, cv.winfo_height() - 20, fill=edge, dash=(3, 3), tags="hov")
            cv.create_oval(x - 5, y - 5, x + 5, y + 5, outline=brass, width=2, fill=surf, tags="hov")
            d = v - pts[i - 1][3] if i else None
            lines = [datetime.fromtimestamp(t).strftime("%b %d, %H:%M").replace(" 0", " "), fmt_div(v)]
            if d is not None:
                lines.append(("▲ +" if d >= 0 else "▼ −") + fmt_div(abs(d)) + " from the one before")
            tid = cv.create_text(0, 0, text="\n".join(lines), anchor="nw", font=("Segoe UI", 9), fill=txt, tags="hov")
            bx = cv.bbox(tid)
            bw, bh = bx[2] - bx[0] + 16, bx[3] - bx[1] + 12
            tx = min(max(4, x + 12), cv.winfo_width() - bw - 4)
            ty = max(4, min(y - bh - 8, cv.winfo_height() - bh - 24))
            _th.round_rect(cv, tx, ty, tx + bw, ty + bh, 6, fill=surf, outline=edge, tags="hov")
            cv.coords(tid, tx + 8, ty + 6)
            cv.tag_raise(tid)

    def wealth_draw_chart(self):
        """Total: your net worth over the picked range. Daily: how much it went up or down each day."""
        cv = self.w_chart
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60 or h < 40:
            return
        lg = SETTINGS.get("league", "")
        span_s = self.RANGES.get(self.w_range.get())
        now = time.time()
        allpts = [(s["ts"], s["total"]) for s in WEALTH.snapshots if s.get("league") == lg]
        pts = [p for p in allpts if span_s is None or p[0] >= now - span_s]
        daily = self.w_mode.get() == "Daily"
        day = lambda t: datetime.fromtimestamp(t).strftime("%b %d").replace(" 0", " ")
        pad_l, pad_r, pad_t, pad_b = 54, 10, 8, 20
        if daily:
            last = {}
            for t, v in allpts:
                last[datetime.fromtimestamp(t).date()] = (t, v)
            days = sorted(last.items())
            bars = [(days[i][1][0], days[i][1][1] - days[i - 1][1][1]) for i in range(1, len(days))]
            bars = [b for b in bars if span_s is None or b[0] >= now - span_s]
            if not bars:
                cv.create_text(4, h // 2, anchor="w", fill=C["muted"], font=("Segoe UI", 9),
                               text="No daily change yet.")
                return
            m = max(abs(v) for _, v in bars) or 1
            mid = pad_t + (h - pad_t - pad_b) / 2
            cv.create_line(pad_l, mid, w - pad_r, mid, fill=C["line"])
            cv.create_text(pad_l - 6, pad_t + 4, anchor="e", fill=C["muted"], font=("Segoe UI", 8), text="+" + fmt_div(m))
            cv.create_text(pad_l - 6, h - pad_b - 4, anchor="e", fill=C["muted"], font=("Segoe UI", 8), text="-" + fmt_div(m))
            bw = max(3, (w - pad_l - pad_r) / len(bars) - 4)
            for i, (t, v) in enumerate(bars):
                x0 = pad_l + i * (w - pad_l - pad_r) / len(bars) + 2
                y = mid - v / m * (h - pad_t - pad_b) / 2
                cv.create_rectangle(x0, min(mid, y), x0 + bw, max(mid, y), outline="", fill=C["green"] if v >= 0 else C["red"])
            cv.create_text(pad_l, h - 4, anchor="sw", fill=C["muted"], font=("Segoe UI", 8), text=day(bars[0][0]))
            cv.create_text(w - pad_r, h - 4, anchor="se", fill=C["muted"], font=("Segoe UI", 8), text=day(bars[-1][0]))
            return
        if len(pts) < 2:
            cv.create_text(4, h // 2, anchor="w", fill=C["muted"], font=("Segoe UI", 9),
                           text="Each count or scan adds a point. The line starts with the second one"
                                + (" in this range." if len(allpts) >= 2 else "."))
            return
        t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
        hi_, lo_ = max(v for _, v in pts), min(v for _, v in pts)      # P3: the line uses the height (was from 0)
        pad_v = max((hi_ - lo_) * 0.15, hi_ * 0.02, 0.01)
        vmax, vmin = hi_ + pad_v, max(0.0, lo_ - pad_v)
        span = max(vmax - vmin, 1e-9)
        X = lambda t: pad_l + (t - t0) / (t1 - t0) * (w - pad_l - pad_r)
        Y = lambda v: pad_t + (1 - (v - vmin) / span) * (h - pad_t - pad_b)
        from . import themes as _th                    # UI overhaul: soft grid, brass line, a hover per point
        th = _th.ST.theme
        with _th.raw():
            brass = th.c("accent_2") if th else "#e8a65a"
            area = _th.mix(brass, th.c("surface_raised") if th else C["panel2"], .86)
            grid = th.c("border") if th else C["line"]
        for i in range(4):
            gy = pad_t + i * (h - pad_t - pad_b) / 3
            cv.create_line(pad_l, gy, w - pad_r, gy, fill=grid, dash=(2, 4) if i < 3 else ())
        cv.create_text(pad_l - 6, Y(vmax), anchor="e", fill=C["muted"], font=("Segoe UI", 8), text=fmt_div(vmax))
        cv.create_text(pad_l - 6, Y(vmin), anchor="e", fill=C["muted"], font=("Segoe UI", 8), text=fmt_div(vmin))
        xy = [c for t, v in pts for c in (X(t), Y(v))]
        cv.create_polygon(*xy, X(t1), h - pad_b, X(t0), h - pad_b, fill=area, outline="")
        cv.create_line(*xy, fill=brass, width=2, smooth=True)
        cv.create_oval(X(pts[-1][0]) - 4, Y(pts[-1][1]) - 4, X(pts[-1][0]) + 4, Y(pts[-1][1]) + 4, fill=brass,
                       outline="")
        self._w_chart_pts = [(X(t), Y(v), t, v) for t, v in pts]
        if not getattr(cv, "_hover_bound", False):
            cv.bind("<Motion>", self._w_chart_hover, add="+")
            cv.bind("<Leave>", lambda e: cv.delete("hov"), add="+")
            cv._hover_bound = True
        n = 4 if w > 420 else 2
        for i in range(n + 1):
            t = t0 + (t1 - t0) * i / n
            cv.create_text(X(t), h - 4, anchor="s" if 0 < i < n else ("sw" if i == 0 else "se"), fill=C["muted"],
                           font=("Segoe UI", 9), text=day(t))
