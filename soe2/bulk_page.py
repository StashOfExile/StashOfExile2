"""Bulk Pricing (owner pick: mockup A in a wide window, C in the Drawer). Top to bottom: your stash tabs (when you read
one) with what the list is worth and how many items it has; the toolbar - a search box first, Filters · n ▾,
Columns ▾, then Manually Add | Add from stash tab, Re-price all and Pause; the stash tab's own row; the list; the key bar.
The picked item is shown as Price Checks shows one - the price card, the item card (Base and Properties, Mods,
Augments, Item Flags), the cheapest listings, then Search again | Trade Site | Add to favorites - beside the list in a
wide window, under it in a narrow one, about 10% smaller than Price Checks' card in the Drawer (cardscale.BULK; text
never below the app's normal small size; a long card scrolls). It is always there: the first row is picked by itself; with no row picked it says what it
is, with one button. Your account name is never on the page (it could show on a stream). UI rule 22: a new price
paints the price card and the listings only."""
import tkinter as tk
import types
from tkinter import ttk

from . import buglog
from .config import save_json, SETTINGS
from .cardscale import BULK
from .names import BULK_MANUAL, BULK_STASH
from .pricecheck_page import CONF_CHIP, WIDE_PX, search_tip
from .style import C, Splitter, Tooltip, flowify, flow_show, trade_icon

ITEM_W = 480            # the picked item's side in a wide window, at first (drag the grip; remembered: panel_w) -
                        # owner: about 10% narrower than Price Checks' card side
STACK_ROWS = 7          # a narrow window: the list's rows over the picked item


def conf_words(conf):
    """Confidence in the list (its column is headed Confidence): Price Checks' mark and level word, "✓ High"."""
    c = str(conf or "").lower()
    if c in CONF_CHIP:
        mark, word, _k = CONF_CHIP[c]
        return f"{mark} {word.replace(' confidence', '')}"
    return ""


def bk_flow(row):
    """A flowify'd row lays itself out again once its widgets' words changed (their size isn't followed by itself)."""
    lay = getattr(row, "_flow_layout", None)
    if lay is None:
        return

    def go(n):
        """(the sizes inside settle over a few idle passes: laid out again while one is placed narrower or wider
        than it asks)"""
        try:
            if not row.winfo_exists():
                return
            off = any(not k["hidden"] and k["w"].winfo_ismapped() and
                      k["w"].winfo_reqwidth() != k["w"].winfo_width() for k in row._flow_kids)
            if off:
                lay()
            if n:
                row.after(80, lambda: go(n - 1))
        except tk.TclError:
            pass
    try:
        row.after(20, lambda: go(3))
    except tk.TclError:
        pass


class BulkPage:
    """Mixed into App."""

    # ---------------------------------------------------------------- the page
    def build_checks(self, body):
        self.checks_body = body
        self.pc_vars()
        self._bk_sel_ids, self._bk_sig, self._bk_list_sig, self._bk_how = set(), None, None, None
        self._bk_layout_job, self._bk_empty_on = None, False
        P1 = C["panel"]
        # ---- the key bar, at the bottom (claims its space first)
        kbf = tk.Frame(body, bg=P1)
        kbf.pack(fill="x", side="bottom")
        self.build_keybar(kbf)
        self._bk_summary(body)                          # your tabs (Add from stash tab) | worth · items
        self._bk_toolbar(body)                          # search, Filters · n ▾, Columns ▾ | the source, Re-price all
        self.bk_stash = tk.Frame(body, bg=P1)           # (shown with Add from stash tab: pctab_mode)
        self.view_var = tk.StringVar(value=SETTINGS["view"])
        self.build_tab_reader(self.bk_stash)
        self.banner = tk.Label(body, text="", anchor="w", padx=12, pady=2, font=("Segoe UI", 9), justify="left")
        # ---- the list (left) and the picked item (right; under the list in a narrow window)
        main = tk.Frame(body, bg=P1)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.checks_area = self.bk_main = main          # (banners go just above it)
        if not SETTINGS.get("bk_side_k2"):              # (once, owner round 2: the card is 0.9 now, not 0.8 - a side
            pw = int(SETTINGS.get("panel_w") or ITEM_W)  # made 0.8 narrower gets that back, and is ITEM_W at least)
            SETTINGS["panel_w"] = max(ITEM_W, int(pw * (BULK / 0.8) if SETTINGS.get("bk_side_k") else pw))
            SETTINGS["bk_side_k"] = SETTINGS["bk_side_k2"] = True
        pw = int(SETTINGS.get("panel_w") or ITEM_W)
        split = self.bk_split = Splitter(main, width=max(320, min(pw, 900)), lo=320, keep=420,
                                         on_set=self._bk_side_saved, bg=P1, fixed="right")
        split.pack(fill="both", expand=True)
        split.left.config(bg=P1)
        split.right.config(bg=P1)
        self.pane = split                               # (older callers: the list and the item side)
        self._bk_list_col(split.left)
        self.outer = split.right
        self._bk_item_col(split.right)
        self.bulkv = types.SimpleNamespace(card_rows={}, card_paint=None, card_vals={}, rid=None, search_btn=None,
                                           lst=self.bk_list, count=self.bk_count, rcanvas=self.dcanvas,
                                           lcanvas=self.dcanvas, cards=[], table=True, keep_scroll=True,
                                           open_btn=self.bk_trade_btn)
        split.set_layout("side")                        # (the picked item's side is always there: bk_layout)
        body.bind("<Configure>", self._bk_page_cfg, add="+")
        self.pctab_mode(save=False)
        self.show_detail(None)
        self.bk_filters_paint()

    def bk_rules_tip(self):
        """The header's ⓘ: the real settings the prices are made from, and where to change them."""
        status, age = SETTINGS.get("status") or "Instant Buyout", SETTINGS.get("age") or "2 days"
        when = "listed any time" if age == "Any time" else f"from the last {age}"
        return (f"Pricing uses {status} listings {when}.\nChange it in Settings › Price checking "
                "(click ⓘ to go there).")

    # ---------------------------------------------------------------- your tabs | worth · items
    def _bk_summary(self, body):
        P1 = C["panel"]
        row = self.bk_sum = tk.Frame(body, bg=P1)
        row.pack(fill="x", padx=12, pady=(8, 8))
        self.pc_tabsrow = tk.Frame(row, bg=P1)          # (the chips: pctab_bar)
        self.pc_tabsrow.pack(side="left")
        stats = tk.Frame(row, bg=P1)
        stats.pack(side="right")
        worth = tk.Frame(stats, bg=P1)
        worth.pack(side="left", padx=(0, 24))
        self.bk_worth_lbl = tk.Label(worth, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w")
        self.bk_worth_lbl.pack(anchor="w")
        wl = tk.Frame(worth, bg=P1)
        wl.pack(anchor="w")
        self.bk_worth_val = tk.Label(wl, text="", bg=P1, fg=C["text"], font=("Segoe UI", 16, "bold"))
        self.bk_worth_val.pack(side="left")
        self.bk_worth_how = tk.Label(wl, text="ⓘ", bg=P1, fg=C["muted"], font=("Segoe UI", 9),
                                     cursor="question_arrow")
        self.bk_worth_how.pack(side="left", padx=(4, 0))
        self.bk_worth_tip = Tooltip(self.bk_worth_how, "")
        items = tk.Frame(stats, bg=P1)
        items.pack(side="left")
        tk.Label(items, text="Items", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
        il = tk.Frame(items, bg=P1)
        il.pack(anchor="w")
        self.bk_items_val = tk.Label(il, text="0", bg=P1, fg=C["text"], font=("Segoe UI", 16, "bold"))
        self.bk_items_val.pack(side="left")
        self.bk_items_sub = tk.Label(il, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9))
        self.bk_items_sub.pack(side="left", padx=(4, 0))
        self.bk_items_tip = Tooltip(items, "")
        for w in (self.bk_items_val, self.bk_items_sub):
            w.bind("<Enter>", self.bk_items_tip._enter, add="+")
            w.bind("<Leave>", self.bk_items_tip._leave, add="+")
        flowify(row)

    # ---------------------------------------------------------------- the toolbar
    def _bk_toolbar(self, body):
        from .tabreader_page import MODES, MODE_LABELS
        from .style import SegBar
        P1 = C["panel"]
        tb = self.price_tb = tk.Frame(body, bg=P1)
        tb.pack(fill="x", padx=12, pady=(0, 8))
        self.bk_tb = tb
        # the search box, first, top left
        self.search_var = tk.StringVar()                    # 2.63.0: find by name, base, type or mod text
        box = tk.Frame(tb, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        box.pack(side="left", padx=(0, 8))
        tk.Label(box, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        ent = self.search_box = tk.Entry(box, textvariable=self.search_var, width=26, bg=C["odd"], fg=C["text"],
                                         insertbackground=C["text"], relief="flat", font=("Segoe UI", 9),
                                         highlightthickness=0, bd=0)
        ent.pack(side="left", padx=(4, 8), ipady=4)
        ph = tk.Label(box, text="Search items", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 9))
        ph.bind("<Button-1>", lambda e: ent.focus_set())

        def placeholder(_e=None):
            try:
                if self.search_var.get() or ent.focus_get() is ent:
                    ph.place_forget()
                else:
                    ph.place(in_=ent, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            ent.bind(ev, placeholder, add="+")
        ent.after(200, placeholder)
        Tooltip(box, "Search by name, base, type or mod")
        self.search_var.trace_add("write", lambda *a: (placeholder(), self.on_filter_text(soon=True)))
        ent.bind("<Escape>", lambda e: (self.search_var.set(""), "break")[1])
        # Filters · n ▾ (Category, Rarity, Type, Clear filters) and Columns ▾
        self.bk_filt_btn = ttk.Button(tb, text="Filters · 0 ▾", style="Quiet.TButton", command=self.bk_filters_toggle)
        self.bk_filt_btn.pack(side="left", padx=(0, 8))
        Tooltip(self.bk_filt_btn, "Category, rarity and type - the number says how many are set")
        self.cols_btn = ttk.Button(tb, text="Columns ▾", style="Quiet.TButton", command=self.cols_menu)
        self.cols_btn.pack(side="left")
        Tooltip(self.cols_btn, "The list's columns, its order, and Export CSV")
        self._bk_filters_build(body)
        # right: Pause (far right), Re-price all, the source switch
        self.pause_btn = ttk.Button(tb, text="⏸ Pause", command=self.toggle_pause)
        self.pause_btn.pack(side="right", padx=(8, 0))
        Tooltip(self.pause_btn, "Pause the searches (F2). Items you copy still join the list.")
        self.reprice_all_btn = ttk.Button(tb, text="↻ Re-price all", command=self.reprice_all)
        self.reprice_all_btn.pack(side="right", padx=(8, 0))
        Tooltip(self.reprice_all_btn, "Searches every item in this list again")
        cfg = SETTINGS.setdefault("pctab", {})
        if cfg.get("mode") not in MODES:
            cfg["mode"] = MODES[0]
        # owner (mockup A): a plain switch - the picked one says "✓" and its word, never orange; BETA on its button
        self.pc_mode = SegBar(tb, [MODE_LABELS[m] for m in MODES], value=MODE_LABELS[cfg["mode"]], size=9,
                              pad=(12, 4), plain=True, badges={MODE_LABELS["Stash tab"]: "BETA"},
                              command=lambda v: self.pctab_mode())
        self.pc_mode.pack(side="right", padx=(8, 0))
        Tooltip(self.pc_mode, f"{BULK_MANUAL}: Ctrl+Alt+C on each item in game. {BULK_STASH}: every item on one of "
                              "your public stash tabs, through the trade site (BETA). Each has its own list.")
        flowify(tb)

    def _bk_filters_build(self, body):
        """The Filters ▾ box: Category, Rarity, Type and Clear filters, under its button (over the list)."""
        P2 = C["panel2"]
        pop = self.bk_filt_pop = tk.Frame(body, bg=P2, padx=12, pady=12, highlightthickness=1,
                                          highlightbackground=C["line"])
        self.cat_var, self.rar_var, self.type_var = tk.StringVar(value=self.ALL_CATS), tk.StringVar(value="All"), \
            tk.StringVar(value="All")
        self.cat_box = ttk.Combobox(pop, textvariable=self.cat_var, state="readonly", width=18)
        self.rar_box = ttk.Combobox(pop, textvariable=self.rar_var, state="readonly", width=18)
        self.type_box = ttk.Combobox(pop, textvariable=self.type_var, state="readonly", width=18)
        for r, (label, box) in enumerate((("Category", self.cat_box), ("Rarity", self.rar_box), ("Type", self.type_box))):
            tk.Label(pop, text=label, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
            box.grid(row=r, column=1, sticky="ew", pady=(0, 8))
        self.cat_box.bind("<<ComboboxSelected>>", lambda e: self.on_cat(changed="cat"))
        self.rar_box.bind("<<ComboboxSelected>>", lambda e: self.on_cat(changed="rar"))
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self.on_cat(changed="type"))
        self.star_var = tk.BooleanVar(value=False)          # 2.74.5: the "Only ★" switch is gone (kept off)
        foot = tk.Frame(pop, bg=P2)
        foot.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.clear_btn = ttk.Button(foot, text="✕ Clear filters", command=self.cat_reset, state="disabled",
                                    style="Quiet.TButton")
        self.clear_btn.pack(side="left")
        Tooltip(self.clear_btn, "Clears the search box and shows every item again")
        done = tk.Label(foot, text="Done", bg=P2, fg=C["muted"], font=("Segoe UI", 9), cursor="hand2")
        done.pack(side="right")
        done.bind("<Button-1>", lambda e: self.bk_filters_toggle(False))
        for w in (pop, self.cat_box, self.rar_box, self.type_box):
            w.bind("<Escape>", lambda e: self.bk_filters_toggle(False), add="+")

    def bk_filters_toggle(self, on=None):
        pop = getattr(self, "bk_filt_pop", None)
        if pop is None:
            return
        shown = bool(pop.winfo_manager())
        on = not shown if on is None else bool(on)
        try:
            if on:
                b = self.bk_filt_btn
                pop.place(in_=b, relx=0, rely=1, y=4, anchor="nw")
                pop.lift()
                self.cat_refresh()
            else:
                pop.place_forget()
        except tk.TclError:
            pass

    def bk_filters_count(self):
        try:
            return sum(1 for v, d in ((self.cat_var, self.ALL_CATS), (self.rar_var, "All"), (self.type_var, "All"))
                       if self._cat_name(v.get()) != d)
        except AttributeError:
            return 0

    def bk_filters_paint(self):
        b = getattr(self, "bk_filt_btn", None)
        if b is None:
            return
        txt = f"Filters · {self.bk_filters_count()} ▾"
        if b.cget("text") != txt:
            b.config(text=txt)
            bk_flow(self.bk_tb)

    def cols_menu(self):
        """Columns ▾: the extra columns, the list's order (as added, or as the tab holds it) and Export CSV."""
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground=C["accent"])
        off = set(self.bulk_cols_off())
        self._cols_vars = {}
        for cid, label in self.EXTRA_COLS:
            v = tk.BooleanVar(value=cid not in off)
            self._cols_vars[cid] = v
            m.add_checkbutton(label=label, variable=v, command=lambda c=cid, vv=v: self.cols_set(c, bool(vv.get())))
        m.add_separator()
        m.add_command(label="Order added", command=self.sort_added)
        if self.pctab_on():                              # 2.87.0: the list follows the tab
            self._order_var = tk.StringVar(value=SETTINGS.get("stash_order", "columns"))
            sub = tk.Menu(m, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground=C["accent"])
            for key, name in (("columns", "Down columns"), ("rows", "Across rows")):
                sub.add_radiobutton(label=name, value=key, variable=self._order_var,
                                    command=lambda k=key: self.stash_order_set(k))
            m.add_cascade(label="List order", menu=sub)
        m.add_separator()
        m.add_command(label="Export CSV…", command=self.export)
        b = self.cols_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    # ---------------------------------------------------------------- the list
    def _bk_list_col(self, lcol):
        from .chrome import EmptyState, SectionBar, Viewport
        P1 = C["panel"]
        self.list_head = SectionBar(lcol, "Items")
        self.list_head.pack(fill="x")
        self.cat_count = tk.Label(lcol, text="")             # (not shown - its text is the strip's note)
        # 2.126.0 (feedback): Undo, Delete and Clear All sit in the Items strip as small strip buttons, together
        acts = tk.Frame(lcol, bg=P1, pady=4)                 # (not shown: holds the retired mark buttons)
        self.delete_btn = ttk.Button(lcol, text="🗑 Delete", command=self.remove_selected, style="StripDanger.TButton",
                                     state="disabled")      # 2.0 beta 19
        self.clear_all_btn = ttk.Button(lcol, text="Clear All…", command=self.clear, style="StripDanger.TButton",
                                        state="disabled")
        self.remove_btn = ttk.Button(acts, text="✖ Mark removed", command=lambda: self.mark_selected("removed"),
                                     state="disabled")
        self.mark_btn = ttk.Button(acts, text="✔ Mark listed", command=lambda: self.mark_selected("listed"),
                                   state="disabled")
        self.undo_btn = ttk.Button(lcol, text="↺ Undo", command=self.undo_mark, state="disabled", style="Strip.TButton")
        Tooltip(self.undo_btn, "Bring back what you last deleted (Ctrl+Z)")
        Tooltip(self.delete_btn, "Delete the picked items from the list (Del)")
        Tooltip(self.clear_all_btn, "Remove every item from this list. It asks first.")
        for b in (self.undo_btn, self.delete_btn, self.clear_all_btn):
            self.list_head.add_right(b)
        self.undo = []                                   # [(record id, previous mark, previous listed-at)] of the last mark
        vp = Viewport(lcol)
        vp.pack(fill="both", expand=True)
        left = self.bk_list_area = vp.body
        self.tree = ttk.Treeview(left, columns=[c[0] for c in self.COLS], show="headings", selectmode="extended")
        self.tree.menu_actions = self.checks_menu_actions          # 2.36.0: right-click / Menu key
        for cid, title, w, anchor in self.COLS:
            self.tree.heading(cid, text=title, command=lambda c=cid: self.sort_by(c))
            keep = w if cid == "name" else min(self.COL_MAX_W, int(SETTINGS.get("col_widths", {}).get(cid, w)))
            self.tree.column(cid, width=max(keep, {"conf": 120, "ilvl": 80, "mark": 104}.get(cid, 0)), minwidth=36,
                             anchor=anchor, stretch=(cid == "name"))
        self.cols_apply()
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=lambda a, b: (hsb.pack_forget() if float(a) <= 0 and float(b) >= 1
                                                         else hsb.pack(side="bottom", fill="x", before=self.tree),
                                                         hsb.set(a, b)))
        self.tree_hsb = hsb
        self.tree.pack(side="left", fill="both", expand=True)
        from . import themes as _th
        t = _th.ST.theme
        uniq = t.c("unique", "#af6025") if t is not None else "#af6025"
        # the Item's rarity color for the row (the Status column says where its pricing is, with a mark and a word)
        for tag, fg in (("pending", C["muted"]), ("error", C["red"]), ("rar_rare", C["rare"]),
                        ("rar_magic", C["magic"]), ("rar_unique", uniq), ("rar_normal", C["text"]),
                        ("listed", C["green"]), ("removed", C["muted"]), ("sold", "#7fe0c0")):
            self.tree.tag_configure(tag, foreground=fg)
        self.tree.tag_configure("even", background=P1)
        self.tree.tag_configure("odd", background=C["odd"])
        self.tree.bind("<<TreeviewSelect>>", self._on_select_soon)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_mark_buttons(), add="+")   # 2.103.1: lit at once
        self.tree.bind("<Double-1>", lambda e: self.open_trade())
        self.tree.bind("<Button-1>", lambda e: self.bk_filters_toggle(False), add="+")
        # the empty list: what it is, and one button (Read tab with Add from stash tab)
        self.empty_lbl = EmptyState(left, "⚖", "", button=("Read tab", self.pctab_read))
        self.bk_empty_more = tk.Label(self.empty_lbl, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9),
                                      justify="center")
        self.bk_empty_more.pack(pady=(12, 0))

    def bk_empty_paint(self):
        """The list's empty state, when it has no rows: a stash tab with nothing read yet - its name, one line and
        Read tab (the stash row's own Read tab hides meanwhile: one orange button); your own list - how to add items;
        filters that hide everything - Clear filters."""
        e = getattr(self, "empty_lbl", None)
        if e is None:
            return
        try:
            shown = bool(self.tree.get_children())
        except tk.TclError:
            return
        stash = self.pctab_on()
        mine = any(self.in_list(r) for r in self.records.values())
        btn, more = e.btn, ""
        if shown:
            e.place_forget()
        else:
            if mine:
                e.set_text("Nothing in this view\nNo item matches the search or the filters.")
                btn.config(text="✕ Clear filters", command=self.cat_reset, style="TButton")
            elif stash:
                t = self.pctab_current()
                e.set_text(f"{t['name'] if t else 'This tab'} is empty\nPress Read tab to list and price everything "
                           "in it.")
                btn.config(text="Read tab", command=self.pctab_read, style="Primary.TButton")
                more = "Or hover an item in game and press Ctrl+Alt+C."
            else:
                e.set_text("Your list is empty\nHow to add items: hover an item in game and press Ctrl+Alt+C. It "
                           "shows up here and gets priced - tablets, jewels, waystones and gear.")
            if mine or stash:
                if not btn.winfo_manager():
                    btn.pack(pady=(12, 0), before=self.bk_empty_more)
            elif btn.winfo_manager():
                btn.pack_forget()
            self.bk_empty_more.config(text=more)
            e.place(relx=0.5, rely=0.45, anchor="center")
        on = not shown and stash and not mine           # (the empty state's Read tab is the one shown)
        if on != self._bk_empty_on:
            self._bk_empty_on = on
            self.pctab_read_shown(not on)

    # ---------------------------------------------------------------- the picked item
    def _bk_item_col(self, col):
        P1, P2 = C["panel"], C["panel2"]
        self.bk_price = self.price_card_build(col, BULK)    # the price, how sure, how it was worked out
        # Search again | Trade Site | Add to favorites - at the bottom, always in view
        foot = self.bk_foot = tk.Frame(col, bg=P2, highlightthickness=1, highlightbackground=C["line"])
        foot.pack(side="bottom", fill="x", pady=(8, 0))
        f = self.bk_foot_row = tk.Frame(foot, bg=P2)
        f.pack(fill="x", padx=12, pady=8)
        btn = self.bk_search_btn = ttk.Button(f, text="Search again", style="Primary.TButton",
                                              command=lambda: self.shown_rec and self.pc_search_go(self.shown_rec))
        btn._search_tip = Tooltip(btn, "Searches the trade site again for this item, with these filters.")
        btn.pack(side="left")
        self.detail_search_btn = btn
        self.bk_trade_btn = self.detail_open_btn = trade_icon(ttk.Button(f, text="Trade Site", command=self.open_trade,
                                                                         state="disabled"))
        self.bk_trade_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.bk_trade_btn, "Opens this search on the trade site (O)")
        self.bk_fav_btn = ttk.Button(f, text="☆ Add to favorites", state="disabled",
                                     command=lambda: self.shown_rec and self.pc_add_fav(self.shown_rec, self.bk_fav_btn))
        self.bk_fav_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.bk_fav_btn, "Keeps this item and its filters in Trade › Favorites")
        self.item_trade_btn, self.item_mark_btn = self.bk_trade_btn, self.mark_btn     # (older callers)
        flowify(f)
        # no row picked: what this side is, and one button (it picks the first row)
        from .chrome import EmptyState
        self.bk_none = EmptyState(col, "⚖", "No item picked\nPick an item in the list: its price, its filters and "
                                  "the cheapest listings show here.", button=("Show the first item", self.bk_autopick))
        Tooltip(self.bk_none.btn, "Picks the first item in the list")
        # the item card, its listings and Advanced, scrolling
        box = self.bk_scroll = tk.Frame(col, bg=P1)
        box.pack(fill="both", expand=True)
        dsb = ttk.Scrollbar(box, orient="vertical")
        dsb.pack(side="right", fill="y")
        self.dcanvas = tk.Canvas(box, bg=P1, highlightthickness=0, yscrollcommand=dsb.set)
        self.dcanvas.pack(side="left", fill="both", expand=True)
        dsb.config(command=self.dcanvas.yview)
        self._bk_price_padx = (0, dsb.winfo_reqwidth())  # owner: the price box ends where the card ends (not over
        self.bk_price.frame.pack(fill="x", pady=(0, 8), padx=self._bk_price_padx, before=box)    # the scroll bar)
        self.detail = tk.Frame(self.dcanvas, bg=P1)
        self._dwin = self.dcanvas.create_window((0, 0), window=self.detail, anchor="nw")
        self.dcanvas.bind("<Configure>", self._canvas_resized)
        self.detail.bind("<Configure>", lambda e: self.dcanvas.configure(scrollregion=self.dcanvas.bbox("all")))
        self.bk_cardbox = tk.Frame(self.detail, bg=P2, padx=12, pady=8, highlightthickness=1,
                                   highlightbackground=C["line"])
        self.bk_cardbox.pack(fill="x")
        lbox = tk.Frame(self.detail, bg=P1)
        lbox.pack(fill="x", pady=(16, 0))
        self.bk_count = tk.Label(lbox, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w")
        self.bk_count.pack(fill="x", pady=(0, 8))
        self.bk_list = tk.Frame(lbox, bg=P1)
        self.bk_list.pack(fill="x")
        self.bk_advbox = tk.Frame(self.detail, bg=P1)
        self.bk_advbox.pack(fill="x", pady=(4, 8))
        self.detail_adv_head = tk.Label(self.bk_advbox, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold"),
                                        anchor="w", cursor="hand2")
        self.detail_adv_head.pack(fill="x")
        self.detail_adv_head.bind("<Button-1>", lambda e: self.bk_adv_toggle())
        Tooltip(self.detail_adv_head, "If you list it, how it's priced, each mod's roll and the raw text")
        self.bk_adv = tk.Frame(self.bk_advbox, bg=P1)

        def wheel(e):
            d = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            if self.detail.winfo_reqheight() > self.dcanvas.winfo_height():
                self.dcanvas.yview_scroll(d * 2, "units")
        box.bind("<Enter>", lambda e: (box.bind_all("<MouseWheel>", wheel), box.bind_all("<Button-4>", wheel),
                                       box.bind_all("<Button-5>", wheel)))
        box.bind("<Leave>", lambda e: (box.unbind_all("<MouseWheel>"), box.unbind_all("<Button-4>"),
                                       box.unbind_all("<Button-5>")))

    def _bk_wrap(self):
        """The item card's width: what its side has (16 px inside its box, a line)."""
        try:
            cw = self.dcanvas.winfo_width()
        except tk.TclError:
            cw = 0
        return max(260, cw - 2 * 12 - 2 - 12) if cw > 50 else 340

    def bk_card_room(self):
        """The px the picked item's card has beside the list (the scroller's height, less its box's padding); 0 under
        the list (a narrow window: the listings follow the card, as on Price Checks' Drawer)."""
        if not self.bk_layout_wide():
            return 0
        try:
            h = self.dcanvas.winfo_height()
        except tk.TclError:
            return 0
        return max(0, h - 2 * 8 - 2) if h > 50 else 0

    def bk_scale_off(self):
        """Does the picked item's card need another scale for the room it has now?"""
        from . import cardscale
        v = self.bulkv
        if getattr(self, "shown_rec", None) is None or v.card_paint is None:
            return False
        k, h, was = getattr(v, "card_k", BULK), getattr(v, "card_h", 0), getattr(v, "card_avail", 0)
        room = self.bk_card_room()
        if abs(room - was) < 8:
            return False
        if room <= 0:
            return k != BULK
        if h > room and k > cardscale.KMIN:
            return True
        return k < BULK and room > was

    def bk_autopick(self, force=False):
        """Owner: the picked item's side is never empty while the list has rows - nothing picked, the first row is.
        -> True when a row was picked."""
        tree = getattr(self, "tree", None)
        if tree is None:
            return False
        try:
            if tree.selection() and not force:
                return False
            kids = tree.get_children()
            if not kids:
                return False
            tree.selection_set(kids[0])
            tree.focus(kids[0])
            tree.see(kids[0])
            return True
        except tk.TclError:
            return False

    def bk_none_paint(self, on):
        """No row picked: the side says what it is (one button: Show the first item - grayed out while the list is
        empty), the price card and the card wait; the footer's buttons are grayed out (they need a pick)."""
        e = getattr(self, "bk_none", None)
        if e is None:
            return
        try:
            if on:
                self.bk_price.frame.pack_forget()
                self.bk_scroll.pack_forget()
                if not e.winfo_manager():
                    e.pack(expand=True)                 # (in the middle of the side)
                e.btn.config(state="normal" if self.tree.get_children() else "disabled")
                for b in (self.bk_search_btn, self.bk_trade_btn, self.bk_fav_btn):
                    b.config(state="disabled")
            elif e.winfo_manager():
                e.pack_forget()
                self.bk_scroll.pack(fill="both", expand=True)
                self.bk_price.frame.pack(fill="x", pady=(0, 8), padx=self._bk_price_padx, before=self.bk_scroll)
                self.bk_search_btn.config(state="normal")
        except tk.TclError:
            pass

    def _bk_side_saved(self, w=None):
        try:
            SETTINGS["panel_w"] = int(self.bk_split.sashpos(0) if w is None else w)
            save_json("settings.json", SETTINGS)
        except (tk.TclError, AttributeError, ValueError):
            pass

    # ---------------------------------------------------------------- the layout for the width
    def bk_layout_for(self, width):
        """Owner: the picked item's side is always there - beside the list (WIDE_PX and up) or under it."""
        return "side" if width >= WIDE_PX else "stack"

    def bk_layout(self, width=None):
        """Wide (WIDE_PX of page and up): the picked item beside the list; narrow (the Drawer): under it - picked or
        not (its empty state). Only packing changes - the list is never built again. -> changed?"""
        sp = getattr(self, "bk_split", None)
        if sp is None:
            return False
        try:
            w = int(width if width is not None else self.checks_body.winfo_width())
        except tk.TclError:
            return False
        if w <= 1:
            w = WIDE_PX
        narrow = w < WIDE_PX
        if narrow != getattr(self, "_bk_narrow", False):  # (a narrow list shows the columns that fit)
            self._bk_narrow = narrow
            self.cols_apply()
        how = self.bk_layout_for(w)
        if how == getattr(sp, "_how", "side") and self._bk_how is not None:
            return False
        self._bk_how = how
        try:
            self.tree.configure(height=STACK_ROWS if how == "stack" else 10)
        except tk.TclError:
            pass
        return sp.set_layout(how)

    def bk_layout_wide(self):
        """True: the picked item is beside the list."""
        return getattr(self, "_bk_how", None) == "side"

    def _bk_page_cfg(self, e):
        """Once per resize (after a pause; while the Drawer is dragged, when it's let go) - and only when the width
        crosses WIDE_PX."""
        if e.widget is not self.checks_body or (self.bk_layout_for(e.width) == self._bk_how and
                                                 (e.width < WIDE_PX) == getattr(self, "_bk_narrow", False)):
            return
        job = self._bk_layout_job
        if job is not None:
            try:
                self.root.after_cancel(job)
            except Exception:
                buglog.caught()

        def go():
            self._bk_layout_job = None
            try:
                held = self._drawer_mouse_down()
            except Exception:
                held = False
            if held:
                self._bk_layout_job = self.root.after(150, go)
                return
            self.bk_layout()
        self._bk_layout_job = self.root.after(150, go)

    def bulk_pane(self, on):
        """(older callers) The item side follows the pick: bk_layout."""
        self.bk_layout()

    # ---------------------------------------------------------------- showing the picked item
    def bk_mark_sel(self):
        """The picked row says so: ▸ before its name (its background is the selection's) - only the rows that
        change are painted."""
        try:
            now = set(self.tree.selection())
        except tk.TclError:
            return
        was = self._bk_sel_ids
        self._bk_sel_ids = now
        for iid in (was ^ now):
            if iid.isdigit() and int(iid) in self.records and self.tree.exists(iid):
                self.update_row(int(iid))

    def show_detail(self, rec, card_only=False):
        """The picked item as Price Checks shows one: the price card, the item card with every filter, the cheapest
        listings, Advanced; Search again | Trade Site | Add to favorites at the bottom. UI rule 22: the same item with
        the same card (a new price, its search starting) paints the price card and the listings only; another card is
        built beside the old one and swapped in at once, keeping the scroll for the same item."""
        if rec is not None and rec.get("src") == "pc":          # 2.80.0: the card on Price Checks
            return self.pc_show(rec)
        if rec is not None and rec.get("src") == "fav":         # 2.84.0: the card on Favorites
            return self.fav_rec_changed(rec)
        if not hasattr(self, "bk_cardbox"):
            return
        prev = getattr(self, "shown_rec", None)
        self.shown_rec = rec
        self.price_var, self.detail_vars = None, []
        self.bk_mark_sel()
        self.bk_layout()
        v = self.bulkv
        self.bk_none_paint(rec is None)
        if rec is None:
            v.card_paint, v.rid, self._bk_sig, self._bk_list_sig = None, None, None, None
            return
        wrap = self._bk_wrap()
        kids = list(self.bk_cardbox.winfo_children())
        if prev is rec and kids and self._bk_sig is not None and self.card_sig(rec, wrap) == self._bk_sig:
            return self._bk_side_paint(rec)
        top = self.dcanvas.yview()[0] if prev is rec else 0
        holder = tk.Frame(self.bk_cardbox, bg=C["panel2"])
        self._card_no_price = True                      # (the price card says the price: Price Checks' look)
        try:                                            # (10% smaller than Price Checks'; never smaller)
            self.card_fit_draw(v, holder, rec, wrap, BULK, self.bk_card_room())
        finally:
            self._card_no_price = False
            for w in kids:
                w.destroy()
        holder.pack(fill="x")
        v.card_rows, v.card_paint, v.card_vals, v.rid = self.card_rows, self.card_paint, self.card_vals, rec["id"]
        v.search_btn = self.bk_search_btn
        self._bk_sig = self.card_sig(rec, wrap)
        if prev is not rec:
            self._bk_list_sig = None
            self._bk_adv_rid = None
        self._bk_side_paint(rec)
        self.root.after_idle(lambda: self.dcanvas.winfo_exists() and self.dcanvas.yview_moveto(top))

    def _bk_side_paint(self, rec):
        """The picked item's price card, buttons, listings and Advanced - in place (the card stays)."""
        self.price_card_paint(self.bk_price, rec)
        try:
            self.bk_search_btn.config(text=self._bulk_search_text(rec))
            self.bk_search_btn._search_tip.text = search_tip(rec)
            self.bk_trade_btn.config(state="normal" if rec.get("qid") else "disabled")
        except tk.TclError:
            pass
        self.pc_fav_state(rec, self.bk_fav_btn)
        entries_sig = (rec["id"], rec.get("state"), rec.get("qid"), rec.get("total"),
                       tuple(tuple(s.get("ids") or ()) for s in rec.get("stages") or []), self._pc_list_w(self.bulkv))
        if entries_sig != self._bk_list_sig:             # (only when the listings changed)
            self._bk_list_sig = entries_sig
            self.pcv_list(self.bulkv, rec)
        self._bk_adv_paint(rec)

    def bk_adv_toggle(self):
        SETTINGS["detail_adv"] = not SETTINGS.get("detail_adv")
        self._bk_adv_rid = None
        rec = getattr(self, "shown_rec", None)
        if rec is not None:
            self._bk_adv_paint(rec)

    def _bk_adv_paint(self, rec):
        """▸ Advanced (folded): if you list it, how it's priced, each mod's roll, the raw text - a muted link."""
        adv = bool(SETTINGS.get("detail_adv"))
        txt = ("▾ " if adv else "▸ ") + "Advanced · how it's priced, raw text"
        if self.detail_adv_head.cget("text") != txt:
            self.detail_adv_head.config(text=txt)
        key = (rec["id"], rec.get("state"), rec.get("priced_at"), rec.get("qid")) if adv else None
        if key == getattr(self, "_bk_adv_rid", None):
            return
        self._bk_adv_rid = key
        for w in self.bk_adv.winfo_children():
            w.destroy()
        if not adv:
            self.bk_adv.pack_forget()
            return
        self.bk_adv.pack(fill="x")
        try:
            self._detail_advanced(self.bk_adv, rec, rec["item"], self._bk_wrap())
        except Exception:
            self.log_error("the item's Advanced part")

    def _show_detail_into(self, d, rec, wrap):
        """(older callers) The picked item: show_detail."""
        self.show_detail(rec)

    # ---------------------------------------------------------------- the totals
    def update_total(self):
        """What the list is worth (the sum of its priced items - unpriced ones left out; how, on hover) and how many
        items it has, how many still pricing. Only the words that changed are set."""
        self.cat_refresh()                                                    # category counts follow every change
        if getattr(self, "clear_all_btn", None) is not None:                 # 2.126.0: lit while this list has items
            self.clear_all_btn.config(state="normal" if any(self.in_list(r) for r in self.records.values()) else
                                      "disabled")
        if not hasattr(self, "bk_worth_val"):
            return
        from .pricefmt import fmt_div
        from .rates import RATES
        shown = [r for r in self.records.values() if self.visible(r)]       # totals follow the search and filters
        done = [r for r in shown if r["state"] == "done"]
        priced = [r for r in done if r["est"] is not None and not self.price_manually(r) and not r.get("nomatch")
                  and not r.get("skip")]
        tot = sum(r["est"] for r in priced)
        busy = sum(1 for r in shown if r["state"] in ("queued", "pricing"))
        t = self.pctab_current() if self.pctab_on() else None
        filt = self.bk_filters_count() or bool(self.search_var.get().strip())
        who = "These items are" if filt else (f"{t['name']} is" if t else "Your list is")
        val = ("≈ " + (fmt_div(tot) if tot else "0 div")) if shown else "-"
        c = RATES.value("chaos")
        how = (f"How it was worked out: the sum of each priced item's price - {len(priced)} item"
               f"{'s' if len(priced) != 1 else ''}." + (f" ≈ {tot / c:,.0f} chaos." if c and tot >= 1 else ""))
        left = len(shown) - len(priced)
        if left:
            how += (f"\nLeft out: {left} without a price (still pricing, no listings, an error, or Check by hand - "
                    "their rough guess is on the item).")
        sub = f"· {busy} still pricing" if busy else ""
        changed = False
        for w, text in ((self.bk_worth_lbl, f"{who} worth"), (self.bk_worth_val, val),
                        (self.bk_items_val, f"{len(shown):,}"), (self.bk_items_sub, sub)):
            if w.cget("text") != text:
                w.config(text=text)
                changed = True
        if changed:
            bk_flow(self.bk_sum)
        self.bk_worth_tip.text = how
        self.pctab_counts_paint()
        n_all = sum(1 for r in self.records.values() if self.in_list(r))
        self._bk_items_base = (f"{len(shown):,} shown of {n_all:,} in this list" if len(shown) != n_all else
                               f"{n_all:,} in this list") + (f"; {busy} still pricing" if busy else "")
        self.bk_items_tip.text = self._bk_items_base + (getattr(self, "_bk_eta", "") or "")
        self.bk_filters_paint()

    def bk_add_fav(self):
        rec = getattr(self, "shown_rec", None)
        if rec is not None:
            self.pc_add_fav(rec, self.bk_fav_btn)


__all__ = ["BulkPage", "bk_flow", "conf_words"]
