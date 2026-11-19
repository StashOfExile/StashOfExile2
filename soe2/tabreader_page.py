"""Price checks > "Add items from: Manual Add | Stash tab" (2.8.0). The Stash tab row; the reading is tabreader.py.
Ctrl+Alt+C keeps working in both modes: the choice only shows or hides the tab row."""
import re
import tkinter as tk
from tkinter import ttk

from . import buglog
from .config import save_json, SETTINGS
from .names import BULK_MANUAL, BULK_STASH
from .style import C, Tooltip, flow_show, flowify
from .tabreader import PCTAB
from .wealth import parse_price_text, parse_trade_link, WEALTH_CURRENCIES

# 2.40.0: names for trade-site currency ids that aren't in the built-in list (it is replaced by the site's own list a
# moment after start; until then the box still shows the right name)
CURRENCY_SHORT = {"divine": "div", "exalted": "ex", "chaos": "c"}     # (a tab's chip: "37,882 div")
KNOWN_CURRENCY_NAMES = {"mirror": "Mirror of Kalandra", "divine": "Divine Orb", "exalted": "Exalted Orb",
                        "chaos": "Chaos Orb", "vaal": "Vaal Orb", "regal": "Regal Orb", "annul": "Orb of Annulment",
                        "alch": "Orb of Alchemy", "transmute": "Orb of Transmutation", "aug": "Orb of Augmentation",
                        "chance": "Orb of Chance", "artificers": "Artificer's Orb", "wisdom": "Scroll of Wisdom"}

MODES = ["Manual Add", "Stash tab"]          # (as saved) 2.8.1: "Manual Add" was called "Ctrl+Alt+C"
# Bulk Pricing's source switch, as it reads (owner pick, mockup A): Manually Add | Add from stash tab (names.py)
MODE_LABELS = {"Manual Add": BULK_MANUAL, "Stash tab": BULK_STASH}
READ_HINT = "Make the tab public with one price nobody would pay, then:"
# owner: a tab you never renamed is named by its place - "Tab 1", "Tab 2" ... (close Tab 1 and Tab 2 becomes Tab 1);
# a name of the form "Tab <n>" is kept for that, so a tab renamed to one goes back to its place's name
TAB_AUTO = re.compile(r"Tab \d+")


class TabReaderPage:
    """Mixed into App."""

    def build_tab_reader(self, parent):
        """The Add from stash tab block (shown with that source): the tabs' strip (chips, then the account mark at its
        right end: pc_tabsrow) with the selected tab's box joined under it (pc_tabrow): that tab's price in game,
        the hint and Read tab; Stop and ⓘ How, muted. The BETA note and the reading's messages under it. Each tab owns
        its price. The switch itself is in Bulk Pricing's toolbar (pc_mode)."""
        P1 = C["panel"]
        BX = self.pc_box_bg = C["panel2"]            # (the selected tab and its box: one fill)
        cfg = SETTINGS.setdefault("pctab", {})
        if cfg.get("mode") not in MODES:
            cfg["mode"] = MODES[0]
        self.pc_mode_hint = tk.Label(parent, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9))   # (not shown)
        self.pctab_tabs()                                # (moves an older single tab into the list)
        cur_tab = self.pctab_current() or {}
        strip = self.pc_tabsrow = tk.Frame(self.pc_tabblock, bg=P1, height=24)
        strip.pack_propagate(False)
        strip.pack(fill="x")
        self.pc_add_btn = ttk.Button(strip, text="＋ Tab", style="Strip.TButton", cursor="hand2", command=self.pctab_new)
        Tooltip(self.pc_add_btn, "Add a tab: another stash tab, with its own price and its own list")
        self.pc_acc_lbl = self.acc_mark(strip, P1)        # "✓ Account set" - one for every tab, never the name
        self.pc_tab_widgets, self.pc_tab_wrap, self.pc_tab_tips, self._pc_bar_sig = [], {}, {}, None
        strip.bind("<Configure>", lambda e: self.pctab_strip_layout(), add="+")
        outer = self.pc_tabrow = tk.Frame(parent, bg=C["line"])       # (a 1 px outline round the box)
        inner = tk.Frame(outer, bg=BX)
        inner.pack(fill="x", padx=1, pady=1)
        self.pc_join = tk.Frame(outer, bg=BX)             # (covers the outline under the selected chip: no gap)
        outer.bind("<Configure>", lambda e: self.pctab_join(), add="+")
        row = self.pc_tabrow_row = tk.Frame(inner, bg=BX)       # (the row wraps in a narrow window: flowify)
        row.pack(fill="x", padx=12, pady=8)
        self.pc_tabrow_after = None
        tk.Label(row, text="Tab's price in game", bg=BX, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        self.pc_amt = tk.StringVar(value=str(cur_tab.get("amount") or ""))
        self._pc_busy, self._pc_save_job = False, None
        amt = self.pc_amt_box = ttk.Entry(row, textvariable=self.pc_amt, width=9)
        amt.pack(side="left", padx=(8, 4))
        Tooltip(amt, "The one price you gave this tab in game or paste the trade site's link to your tab")
        self.pc_amt.trace_add("write", lambda *a: self.pctab_price_soon())
        amt.bind("<FocusOut>", lambda e: self.pctab_price_flush(), add="+")
        amt.bind("<Return>", lambda e: self.pctab_price_flush(), add="+")
        # 2.40.0: the box is built before the trade site's full currency list arrives, so a saved Mirror of Kalandra
        # isn't in the list yet - it showed "Divine Orb", and Read tab then searched in divines. Show the saved name.
        cid = cur_tab.get("currency") or "divine"
        self.pc_cur = tk.StringVar(value=dict(WEALTH_CURRENCIES).get(cid) or cur_tab.get("currency_name")
                                   or KNOWN_CURRENCY_NAMES.get(cid) or "Divine Orb")
        cb = ttk.Combobox(row, textvariable=self.pc_cur, values=[n for _c, n in WEALTH_CURRENCIES], state="readonly",
                          width=18)
        cb.config(postcommand=lambda c=cb: c.config(values=[n for _c, n in WEALTH_CURRENCIES]))   # 2.16.0: full list
        cb.pack(side="left", padx=(0, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.pctab_cur_picked(), add="+")
        self.pc_cur_box = cb
        # right, as it reads: the hint, Read tab (the screen's orange button), Stop, ⓘ How
        how = self.pc_how_lbl = tk.Label(row, text="ⓘ How", bg=BX, fg=C["muted"], cursor="hand2", font=("Segoe UI", 9))
        how.pack(side="right", padx=(12, 0))
        how.bind("<Button-1>", lambda e: self.pctab_explain())
        Tooltip(how, "How reading a stash tab works shown under this row")
        self.pc_stop = tk.Label(row, text="■ Stop", bg=BX, fg=C["muted"], disabledforeground=C["muted"],
                                font=("Segoe UI", 9), state="disabled", cursor="hand2")      # (shown while reading)
        self.pc_stop.bind("<Button-1>", lambda e: str(self.pc_stop.cget("state")) == "normal" and self.pctab_stop())
        self.pc_stop.pack(side="right", padx=(12, 0))
        Tooltip(self.pc_stop, "Stops reading the tab - what was added stays")
        self.pc_read_btn = ttk.Button(row, text="Read tab", style="Primary.TButton", command=self.pctab_read)
        self.pc_read_btn.pack(side="right", padx=(8, 0))
        Tooltip(self.pc_read_btn, "Finds the tab by its price and adds every item on it to this list")
        self.pc_read_hint = tk.Label(row, text=READ_HINT, bg=BX, fg=C["muted"], font=("Segoe UI", 9))
        self.pc_read_hint.pack(side="right", padx=(12, 0))
        self.pc_to_wealth = tk.Label(row, text="＋ Count it in Wealth", bg=BX, fg=C["muted"], cursor="hand2",
                                     font=("Segoe UI", 9, "underline"))          # 2.18.0: the same tab in Wealth
        self.pc_to_wealth.bind("<Button-1>", lambda e: self.pctab_to_wealth())
        flowify(row)
        flow_show(row, self.pc_stop, False)
        from .chrome import Notice                       # 2.74.5: closable (× at the right), stays closed
        self.pc_beta = Notice(parent, "pctab_beta", "⚠ BETA: reading a stash tab may not work as intended and is of "
                                                    "limited use - many tabs read only partly. Ctrl+Alt+C on each "
                                                    "item is the reliable way.")
        self.pc_msg = tk.Label(parent, text="", bg=P1, fg=C["muted"], anchor="w", justify="left", padx=12,
                               font=("Segoe UI", 9))
        self.pc_msg.bind("<Configure>", lambda e: self.pc_msg.config(wraplength=max(300, e.width - 24)))

    def pctab_on(self):
        """Is Add from stash tab the source (its list shows)?"""
        return (SETTINGS.get("pctab") or {}).get("mode") == "Stash tab"

    def pctab_read_shown(self, on):
        """The stash row's Read tab and its hint - hidden while the empty list shows its own Read tab (one orange
        button)."""
        row = getattr(self, "pc_tabrow_row", None)
        if row is None:
            return
        try:
            flow_show(row, self.pc_read_btn, on)
            self.pc_read_hint.config(text=READ_HINT if on else READ_HINT.replace(", then:", "."))
        except tk.TclError:
            pass

    def pctab_primary(self):
        """3.0.6 (owner's rule: one orange button a screen): Add from stash tab - Read tab is the orange one;
        Manually Add - the picked item's Search again. Re-price all is never orange."""
        tab = self.pctab_on()
        for name, on in (("reprice_all_btn", False), ("pc_read_btn", tab), ("bk_search_btn", not tab)):
            b = getattr(self, name, None)
            if b is not None:
                try:
                    b.config(style="Primary.TButton" if on else "TButton")
                except tk.TclError:
                    pass

    def pctab_mode(self, save=True):
        label = self.pc_mode.get()
        mode = next((m for m, lab in MODE_LABELS.items() if lab == label), label if label in MODES else MODES[0])
        cfg = SETTINGS.setdefault("pctab", {})
        cfg["mode"] = mode
        self.pctab_primary()
        if save:
            save_json("settings.json", SETTINGS)
        stash = getattr(self, "bk_stash", None)
        block = getattr(self, "pc_tabblock", None)
        if mode == "Stash tab":
            self.pctab_bar()
            if block is not None and not block.winfo_manager():
                block.pack(fill="x", padx=12, pady=(0, 8), before=self.bk_tb)
            if stash is not None and not stash.winfo_manager():
                stash.pack(fill="x")
            self.pc_tabrow.pack(fill="x")
            self.pc_beta.show(fill="x", after=self.pc_tabrow, pady=(4, 0))
            self.pc_msg.pack(fill="x", after=self.pc_tabrow if self.pc_beta.closed() else self.pc_beta)
            self.pc_mode_hint.config(text="reads a public stash tab and adds what it can. Ctrl+Alt+C still works.")
            if not self.pc_msg.cget("text"):
                self.pc_msg.config(text="Make a Premium stash tab public and give the whole tab one price nobody would "
                                        "pay, like 37882 Divine Orbs. Type that price here and press Read tab.",
                                   fg=C["muted"])
        else:
            if block is not None:
                block.pack_forget()
            self.pc_mode_hint.config(text="hover an item in game and press Ctrl+Alt+C")
        if hasattr(self, "tree") and save:                # 2.42.0: each source has its own list
            self.list_switched()
        elif hasattr(self, "tree"):
            self.bk_empty_paint()
            self.update_total()

    # ---------------- 2.42.0: separate lists - Manual Add, and one per stash tab
    def list_src(self):
        """Which list the Price checks window shows: "manual", or "tab:<id>" for a stash tab."""
        cfg = SETTINGS.get("pctab") or {}
        if cfg.get("mode") != "Stash tab":
            return "manual"
        t = self.pctab_current()
        return f"tab:{t['id']}" if t else "manual"

    def list_switched(self):
        try:
            self.cat_var.set(self.ALL_CATS)
            self.rar_var.set("All")
            self.type_var.set("All")
            self.rebuild_tree()
            self.cat_refresh()
            self.clear_btn_state()
        except Exception:
            buglog.caught()

    def pctab_tabs(self):
        """[{id, name, renamed, amount, currency, currency_name}] - your stash tabs. An older single tab becomes
        "Tab 1". A tab you never renamed is named by its place ("Tab 2"); one you renamed keeps its name. (Saved before
        3.0.7, without "renamed": a name other than "Tab <n>" was yours.)"""
        cfg = SETTINGS.setdefault("pctab", {})
        tabs = cfg.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            tabs = [{"id": "t1", "name": "Tab 1", "amount": cfg.get("amount"), "currency": cfg.get("currency") or "divine",
                     "currency_name": cfg.get("currency_name")}]
            cfg["tabs"], cfg["current"] = tabs, "t1"
        for i, t in enumerate(tabs, 1):
            if "renamed" not in t:
                t["renamed"] = not TAB_AUTO.fullmatch(str(t.get("name") or "").strip())
            if not t["renamed"]:
                t["name"] = f"Tab {i}"
        if cfg.get("current") not in [t["id"] for t in tabs]:
            cfg["current"] = tabs[0]["id"]
        return tabs

    def pctab_current(self):
        cfg = SETTINGS.get("pctab") or {}
        return next((t for t in self.pctab_tabs() if t["id"] == cfg.get("current")), None)

    @staticmethod
    def pctab_price_short(t):
        """A tab's price, short, for its chip: "37,882 div" (nothing while the tab has no price)."""
        amt = t.get("amount")
        if not amt:
            return ""
        cur = t.get("currency") or "divine"
        n = f"{amt:,}" if isinstance(amt, int) else f"{amt:,.2f}".rstrip("0").rstrip(".")
        return f"{n} {CURRENCY_SHORT.get(cur, cur)}"

    def pctab_chip_text(self, t, counts, on):
        price = self.pctab_price_short(t)
        return ("▸ " if on else "") + f"{t['name']} · {counts.get('tab:' + t['id'], 0)}" + (f" · {price}" if price else "")

    def pctab_chip_tip(self, t):
        cur = t.get("currency_name") or dict(WEALTH_CURRENCIES).get(t.get("currency")) or t.get("currency")
        price = f"priced {t['amount']} {cur} in game" if t.get("amount") else "no price yet"
        return f"{t['name']}: {price} · right-click to rename or delete"

    def pctab_counts(self):
        counts = {}
        for r in getattr(self, "records", {}).values():
            counts[r.get("src", "manual")] = counts.get(r.get("src", "manual"), 0) + 1
        return counts

    def pctab_bar(self):
        """Your tabs as chips - "Tab 1 · 12 · 37,882 div" (the one shown is the folder tab joined to its box, bold and
        marked ▸), then ＋ Tab, and the account mark at the right end. A click shows a tab's list and price;
        right-click renames / deletes it. Built again only when the tabs or the shown one changed; else painted in
        place."""
        tabs = self.pctab_tabs()
        cur = self.pctab_current()
        sig = tuple((t["id"], cur is not None and t["id"] == cur["id"]) for t in tabs)
        if sig == self._pc_bar_sig and all(w.winfo_exists() for w in self.pc_tab_widgets):
            return self.pctab_counts_paint()
        for w in self.pc_tab_widgets:
            w.destroy()
        P1 = C["panel"]
        counts = self.pctab_counts()
        self.pc_tabs, self.pc_tab_wrap, self.pc_tab_tips, self.pc_tab_widgets = {}, {}, {}, []
        self.pc_sel_wrap = None
        for t in tabs:
            on = cur is not None and t["id"] == cur["id"]
            text = self.pctab_chip_text(t, counts, on)
            if on:                                       # the folder tab: same fill as its box, outline open below
                wrap = tk.Frame(self.pc_tabsrow, bg=C["line"])
                chip = tk.Label(wrap, text=text, bg=self.pc_box_bg, fg=C["text"], font=("Segoe UI", 9, "bold"),
                                padx=8, pady=4)
                chip.pack(padx=1, pady=(1, 0))
                self.pc_sel_wrap = wrap
            else:
                wrap = chip = ttk.Button(self.pc_tabsrow, text=text, style="Strip.TButton", cursor="hand2",
                                         command=lambda n=t["name"]: self.pctab_pick(n))   # (round, outlined)
            for w in (wrap, chip):
                w.bind("<Button-3>", lambda e, tid=t["id"]: self.pctab_tab_menu(e, tid), add="+")
            self.pc_tab_tips[t["id"]] = Tooltip(chip, self.pctab_chip_tip(t))
            if on:
                wrap.bind("<Enter>", self.pc_tab_tips[t["id"]]._enter, add="+")
                wrap.bind("<Leave>", self.pc_tab_tips[t["id"]]._leave, add="+")
            self.pc_tabs[t["id"]], self.pc_tab_wrap[t["id"]] = chip, wrap
            self.pc_tab_widgets.append(wrap)
        self._pc_bar_sig = sig
        self.pctab_strip_layout()

    def pctab_counts_paint(self):
        """The chips' counts and prices follow the lists and the boxes, in place (only a chip whose words changed)."""
        chips = getattr(self, "pc_tabs", None)
        if not isinstance(chips, dict) or not chips:
            return
        counts = self.pctab_counts()
        cur = self.pctab_current()
        changed = False
        for t in self.pctab_tabs():
            chip = chips.get(t["id"])
            if chip is None:
                continue
            on = cur is not None and t["id"] == cur["id"]
            text = self.pctab_chip_text(t, counts, on)
            try:
                if chip.cget("text") != text:
                    chip.config(text=text)
                    changed = True
                tip = self.pc_tab_tips.get(t["id"])
                if tip is not None:
                    tip.text = self.pctab_chip_tip(t)
            except (tk.TclError, AttributeError):
                pass
        if changed:
            self.pctab_strip_layout()

    def pctab_strip_layout(self):
        """The tabs' strip: the chips and ＋ Tab in order, wrapping when the window is narrow; the account mark at the
        right end of the last line. The shown tab sits on the strip's bottom edge so it joins its box."""
        strip = getattr(self, "pc_tabsrow", None)
        if strip is None or not self.pc_tab_widgets:
            return
        try:
            kids = self.pc_tab_widgets + [self.pc_add_btn]
            acc = self.pc_acc_lbl
            W = strip.winfo_width()
            if W <= 1:
                W = 10 ** 6
            lines, cur, x = [], [], 0
            for w in kids:
                need = w.winfo_reqwidth() + (8 if cur else 0)
                if cur and x + need > W:
                    lines.append(cur)
                    cur, x, need = [], 0, w.winfo_reqwidth()
                cur.append(w)
                x += need
            lines.append(cur)
            top = x + 16 + acc.winfo_reqwidth() > W      # (no room beside the last chip: its own line above, so the
            y = 0                                         # shown tab stays on the last line, right over its box)
            if top:
                acc.place(x=max(0, W - acc.winfo_reqwidth()), y=0)
                y = acc.winfo_reqheight() + 4
            for li, line in enumerate(lines):
                last = li == len(lines) - 1
                h = max([w.winfo_reqheight() for w in line] + ([acc.winfo_reqheight()] if last and not top else [0]))
                x = 0
                for w in line:
                    wy = y + h - w.winfo_reqheight() if w is self.pc_sel_wrap else y + (h - w.winfo_reqheight()) // 2
                    w.place(x=x, y=wy)
                    x += w.winfo_reqwidth() + 8
                if last and not top:
                    acc.place(x=max(x, W - acc.winfo_reqwidth()) if W < 10 ** 6 else x + 8,
                              y=y + (h - acc.winfo_reqheight()) // 2)
                y += h + (4 if not last else 0)
            if int(strip.cget("height")) != y:
                strip.configure(height=y)
            strip.after_idle(self.pctab_join)
        except tk.TclError:
            pass

    def pctab_join(self):
        """The box's outline is hidden under the shown tab (one shape, no gap) - when that tab is on the strip's last
        line, right above the box."""
        join, wrap, strip, box = (getattr(self, n, None) for n in ("pc_join", "pc_sel_wrap", "pc_tabsrow", "pc_tabrow"))
        try:
            if join is None or wrap is None or not wrap.winfo_exists() or not box.winfo_ismapped():
                if join is not None:
                    join.place_forget()
                return
            on_last = wrap.winfo_y() + wrap.winfo_height() >= strip.winfo_height()
            x = wrap.winfo_rootx() - box.winfo_rootx() + 1
            if on_last and wrap.winfo_ismapped():
                join.place(x=x, y=0, width=max(1, wrap.winfo_width() - 2), height=1)
            else:
                join.place_forget()
        except tk.TclError:
            pass

    def pctab_stop_shown(self, on):
        """Stop shows while a tab is being read (muted, beside ⓘ How)."""
        row = getattr(self, "pc_tabrow_row", None)
        try:
            self.pc_stop.config(state="normal" if on else "disabled")
            if row is not None:
                flow_show(row, self.pc_stop, on)
        except (tk.TclError, AttributeError):
            pass

    def pctab_empty_text(self):
        t = self.pctab_current()
        return f"{t['name'] if t else 'This tab'} is empty\nPress Read tab to list and price everything in it."

    def pctab_pick(self, label):
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if label.startswith(t["name"] + " (") or label == t["name"]), None)
        if not t:
            return
        self.pctab_price_flush()                         # (what was typed goes to the tab it was typed for)
        cfg = SETTINGS.setdefault("pctab", {})
        cfg["current"] = t["id"]
        save_json("settings.json", SETTINGS)
        self.pctab_show_price(t)
        self.pc_msg.config(text="", fg=C["muted"])
        self.pctab_bar()
        self.list_switched()

    def pctab_new(self):
        self.pctab_price_flush()
        tabs = self.pctab_tabs()
        n = len(tabs) + 1                                # (named by its place: the last)
        tid = f"t{max([int(t['id'][1:]) for t in tabs if t['id'][1:].isdigit()] + [0]) + 1}"
        tabs.append({"id": tid, "name": f"Tab {n}", "renamed": False, "amount": None, "currency": "divine",
                     "currency_name": "Divine Orb"})
        SETTINGS["pctab"]["current"] = tid
        save_json("settings.json", SETTINGS)
        self.pctab_show_price(tabs[-1])
        self.pctab_bar()
        self.list_switched()
        self.pc_msg.config(text=f"Tab {n}: give that stash tab its own price in game, type it here and press Read tab.",
                           fg=C["muted"])

    def pctab_tab_menu(self, e, tid):
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84",
                    activeforeground="#ffffff")
        m.add_command(label="Rename…", command=lambda: self.pctab_rename(tid))
        m.add_command(label="Delete this tab and its list", command=lambda: self.pctab_delete(tid),
                      state="normal" if len(self.pctab_tabs()) > 1 else "disabled")
        m.tk_popup(e.x_root, e.y_root)

    def pctab_rename(self, tid):
        from tkinter import simpledialog
        t = next((t for t in self.pctab_tabs() if t["id"] == tid), None)
        if not t:
            return
        name = simpledialog.askstring("Rename tab", "Name:", initialvalue=t["name"], parent=self.dlg_parent())
        name = (name or "").strip()[:24]
        if name and not any(o["name"] == name for o in self.pctab_tabs() if o is not t):
            t["name"], t["renamed"] = name, not TAB_AUTO.fullmatch(name)     # ("Tab 3": its place's name again)
            self.pctab_tabs()
            save_json("settings.json", SETTINGS)
            self.pctab_bar()

    def pctab_delete(self, tid):
        from tkinter import messagebox
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if t["id"] == tid), None)
        if not t or len(tabs) < 2:
            return
        self.pctab_price_flush()
        n = sum(1 for r in self.records.values() if r.get("src") == f"tab:{tid}")
        if n and not messagebox.askyesno("Delete tab", f"Delete {t['name']} and its {n} item(s) from the list?",
                                         parent=self.dlg_parent()):
            return
        for rid in [rid for rid, r in self.records.items() if r.get("src") == f"tab:{tid}"]:
            del self.records[rid]
        tabs.remove(t)
        cfg = SETTINGS["pctab"]
        if cfg.get("current") == tid:
            cfg["current"] = tabs[0]["id"]
        self.pctab_tabs()                                # (the tabs after it move up: Tab 2 is Tab 1 now)
        self.dirty = True
        save_json("settings.json", SETTINGS)
        self.pctab_pick(tabs[0]["name"])
        self.pctab_bar()

    def pctab_wealth_link(self):
        """Show "Count it in Wealth" once a tab was read and Wealth doesn't have it yet."""
        from .wealth import WEALTH
        _ = WEALTH                                    # 2.105.1: Wealth has no stash tabs any more - never shown
        self.pc_to_wealth.pack_forget()

    def pctab_to_wealth(self):
        t = self.pctab_current() or {}                   # (this tab's price)
        if not hasattr(self, "_wealth_add"):
            return
        if t.get("amount") and self._wealth_add(t["amount"], t.get("currency") or "divine", "Price Checks tab"):
            self.pc_msg.config(text="Added to Wealth. Sync there to count it. It's read the same way.", fg=C["green"])
        self.pctab_wealth_link()

    def pctab_explain(self):
        self.pc_msg.config(fg=C["text"], text=(
            "How it works: Path of Exile 2 has no stash access for tools, so the app reads your tab through the trade "
            "site. In game: pick a Premium stash tab, make it public, and give the whole tab one price nobody would pay, "
            "like 37882 Divine Orbs. That odd price is how the app finds your tab, and a price that high keeps "
            "whispers away. Your own listings never count when items are priced. Any currency works. Don't use a "
            "Merchant's tab: those "
            "sell instantly. Press Read tab: every item on it is added here and priced. Items already in the list are "
            "skipped. A new tab listing can take a minute to show on the trade site. The same tab works for Wealth."))

    def pctab_show_price(self, t):
        """Show a tab's own price in the box (a new tab: empty), without saving it back."""
        self._pc_busy = True
        try:
            self.pc_amt.set(str(t.get("amount") or ""))
            self.pc_cur.set(dict(WEALTH_CURRENCIES).get(t.get("currency")) or t.get("currency_name")
                            or KNOWN_CURRENCY_NAMES.get(t.get("currency"), "Divine Orb"))
        finally:
            self._pc_busy = False

    def pctab_price_soon(self):
        """The amount was typed: saved to the shown tab a moment after the last key."""
        if self._pc_busy:
            return
        if self._pc_save_job is not None:
            self.root.after_cancel(self._pc_save_job)
        self._pc_save_job = self.root.after(400, self.pctab_price_flush)

    def pctab_price_flush(self):
        """Save the typed amount to the shown tab now (on a pause, leaving the box, Enter, or before another tab shows)."""
        if self._pc_save_job is not None:
            try:
                self.root.after_cancel(self._pc_save_job)
            except tk.TclError:
                pass
            self._pc_save_job = None
        t = self.pctab_current()
        txt = self.pc_amt.get().strip()
        if t is None or "trade2/search" in txt:           # (a pasted link is read by Read tab)
            return
        amount, cur = parse_price_text(txt)
        if cur:                                           # ("10 chaos": the box follows)
            self._pc_busy = True
            try:
                self.pc_cur.set(dict(WEALTH_CURRENCIES).get(cur) or KNOWN_CURRENCY_NAMES.get(cur) or self.pc_cur.get())
            finally:
                self._pc_busy = False
        cur = cur or self.pctab_cur_id() or t.get("currency") or "divine"
        if (t.get("amount"), t.get("currency")) != (amount, cur) or t.get("currency_name") != self.pc_cur.get():
            t.update(amount=amount, currency=cur, currency_name=self.pc_cur.get())
            save_json("settings.json", SETTINGS)
            self.pctab_counts_paint()

    def pctab_cur_picked(self):
        """2.38.0: keep the tab's currency as soon as it's picked (not only on Read tab), and give the keyboard back
        so nothing else can change it. Each tab keeps its own."""
        cur = self.pctab_cur_id()
        t = self.pctab_current()
        if cur and t is not None:
            t.update(currency=cur, currency_name=self.pc_cur.get())     # 2.40.0: the name too (see the box)
            save_json("settings.json", SETTINGS)
            self.pctab_counts_paint()
        cb = getattr(self, "pc_cur_box", None)

        def done():                                    # 2.40.0: no lingering highlight; the keyboard leaves the box
            try:
                cb.selection_clear()
                cb.winfo_toplevel().focus_set()
            except (tk.TclError, AttributeError):
                self.root.focus_set()
        self.root.after(20, done)

    def ev_currencies_loaded(self):
        """2.40.0: the trade site's full currency list arrived - show the shown tab's currency by its name."""
        t = self.pctab_current() or {}
        name = dict(WEALTH_CURRENCIES).get(t.get("currency"))
        if name and getattr(self, "pc_cur", None) is not None and self.pc_cur.get() != name:
            self._pc_busy = True
            self.pc_cur.set(name)
            self._pc_busy = False
            t["currency_name"] = name

    def pctab_cur_id(self):
        """The currency id for what the box shows - from the trade site's list, or the saved one when the box shows
        the saved name (the list may not be loaded yet)."""
        name = self.pc_cur.get()
        cur = next((c for c, n in WEALTH_CURRENCIES if n == name), None)
        t = self.pctab_current() or {}
        if cur is None and name and name == t.get("currency_name"):
            cur = t.get("currency")
        if cur is None:
            cur = next((c for c, n in KNOWN_CURRENCY_NAMES.items() if n == name), None)
        return cur

    def pctab_read(self):
        acc = self.pc_acc.get().strip()
        txt = self.pc_amt.get().strip()
        if "trade2/search" in txt:                     # a pasted trade-site link: read account and price from it
            info, err = parse_trade_link(txt)
            if err:
                return self.pc_msg.config(text=err, fg=C["red"])
            acc = info["account"] or acc
            self.pc_acc.set(acc)
            amount, cur = info["amount"], info["currency"]
            self._pc_busy = True
            self.pc_amt.set(str(amount))
            self.pc_cur.set(dict(WEALTH_CURRENCIES).get(cur, cur))
            self._pc_busy = False
        else:
            amount, cur = parse_price_text(txt)
            cur = cur or self.pctab_cur_id() or "divine"
        t = self.pctab_current()                       # 2.42.0: this tab's price (the only one)
        if t is not None:
            name = dict(WEALTH_CURRENCIES).get(cur) or self.pc_cur.get()
            t.update(amount=amount, currency=cur, currency_name=name)
            PCTAB["src"] = f"tab:{t['id']}"
            self.pctab_counts_paint()
        from .market import remember_marker
        remember_marker(amount, cur)                   # 2.18.0: never counted as someone's price
        if acc:
            SETTINGS["wealth_account"] = acc           # one account name for Wealth and this
        save_json("settings.json", SETTINGS)
        err = self.engine.pctab_start(acc, amount, cur)
        if err:
            return self.pc_msg.config(text=err, fg=C["red"])
        self._pctab = {"added": 0, "already": 0, "unreadable": 0, "failed": 0}
        self.pc_read_btn.config(state="disabled")
        self.pctab_stop_shown(True)
        self.pc_msg.config(text="Searching your tab…", fg=C["muted"])

    def pctab_stop(self):
        PCTAB["cancel"] = True
        PCTAB["running"] = False
        self.pctab_finished(stopped=True)

    def ev_pctab(self, what, *args):
        if what == "item":
            self.pctab_add(args[0], args[1] if len(args) > 1 else None)
        elif what == "progress":
            st = getattr(self, "_pctab", {})
            self.pc_msg.config(fg=C["muted"], text=f"{PCTAB['msg']}  ·  added {st.get('added', 0)}"
                               + (f", {st['already']} already in the list" if st.get("already") else ""))
        elif what == "done":
            self.pctab_finished()

    def pctab_add(self, text, pos=None):
        """One item from the tab -> a row (unless it's already in the list, or isn't something the app can price).
        2.8.1: what happens to each one goes in tab_reader_log.txt, and an error on one item doesn't hide the rest."""
        st = self.__dict__.setdefault("_pctab", {"added": 0, "already": 0, "unreadable": 0, "failed": 0})
        st.setdefault("failed", 0)
        first = " / ".join(l for l in text.splitlines()[2:4] if l and not l.startswith("--"))
        try:
            src = PCTAB.get("src") or self.list_src()     # 2.42.0: into this tab's own list
            item = self.read_any(text)
            if not item:
                st["unreadable"] += 1
                return PCTAB["log"].append(f"the price checker can't read it: {first}\n    " +
                                          text.replace("\n", "\n    "))
            if any(self.item_sig(r["item"]) == self.item_sig(item) for r in self.records.values()
                   if r.get("src", "manual") == src):
                st["already"] += 1
                return PCTAB["log"].append(f"already in this tab's list: {first}")
            rid = self.add_item_text(text, src=src)
            if rid:
                if pos and rid in self.records:          # 2.87.0: its place in the tab - the list follows the tab
                    self.records[rid]["pos"] = list(pos)
                    self.update_row(rid)
                    self.stash_order_soon()
                st["added"] += 1
                PCTAB["log"].append(f"added: {first}")
            else:
                st["unreadable"] += 1
                PCTAB["log"].append(f"couldn't be added: {first}")
        except Exception:
            import traceback
            st["failed"] += 1
            PCTAB["log"].append(f"error on {first}:\n{traceback.format_exc()}")
            self.log_error("adding an item from the stash tab")

    def pctab_finished(self, stopped=False):
        try:
            self.root.after(50, self.pctab_bar)        # 2.42.0: the tab's count on its button
        except Exception:
            buglog.caught()
        self._pctab_finished(stopped)

    def _pctab_finished(self, stopped=False):
        st = getattr(self, "_pctab", {"added": 0, "already": 0, "unreadable": 0})
        self.pc_read_btn.config(state="normal")
        self.pctab_stop_shown(False)
        from .tabreader import write_log
        PCTAB["log"].append(f"result: added {st.get('added', 0)}, already {st.get('already', 0)}, can't read "
                            f"{st.get('unreadable', 0)}, errors {st.get('failed', 0)}"
                            + ("; stopped" if stopped else "") + (f"; error: {PCTAB['error']}" if PCTAB["error"] else ""))
        write_log(PCTAB["log"])
        if PCTAB["error"]:
            return self.pc_msg.config(text=PCTAB["error"], fg=C["red"])
        if stopped:
            return self.pc_msg.config(text=f"Stopped. Added {st['added']} item{'s' if st['added'] != 1 else ''}.",
                                      fg=C["good"])
        if not PCTAB["found"]:
            return self.pc_msg.config(fg=C["good"], text=(
                "No listings found at that price. Is the tab public, priced at exactly this amount and currency, and "
                "has the trade site had a minute to show it? Check the account name too, including the #number."))
        parts = [f"Found {PCTAB['found']} listing{'s' if PCTAB['found'] != 1 else ''} at that price, read "
                 f"{PCTAB['read']}: added {st['added']} to the list"]
        if st["already"]:
            parts.append(f"{st['already']} already in it")
        if st["unreadable"]:
            parts.append(f"{st['unreadable']} the price checker can't read")
        if st.get("failed"):
            parts.append(f"{st['failed']} hit an error")
        msg = ", ".join(parts) + "."
        if PCTAB["skipped"]:
            msg += " Left out: " + ", ".join(f"{n} {why}" for why, n in PCTAB["skipped"].items()) + "."
        if PCTAB["found"] and PCTAB["found"] < 10 and not st["added"]:
            msg += (" Only a few found? Items with their own price note keep that price - they aren't found by the "
                    "tab's price.")
        msg += (" They're being priced now." if st["added"] else "") + "  (Every item: tab_reader_log.txt)"
        SETTINGS.setdefault("pctab", {})["read_ok"] = True
        self.pctab_wealth_link()
        if PCTAB["warnings"]:
            msg += " " + " ".join(PCTAB["warnings"]) + " Move some items to another tab with its own price."
        self.pc_msg.config(text=msg, fg=C["green"] if st["added"] else C["good"])
