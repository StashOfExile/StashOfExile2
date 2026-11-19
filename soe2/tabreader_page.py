"""Price checks > "Add items from: Manual Add | Stash tab" (2.8.0). The Stash tab row; the reading is tabreader.py.
Ctrl+Alt+C keeps working in both modes: the choice only shows or hides the tab row."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from .config import save_json, SETTINGS
from .style import C, Tooltip, flow_show, flowify
from .tabreader import PCTAB
from .wealth import parse_price_text, parse_trade_link, WEALTH_CURRENCIES

# 2.40.0: names for trade-site currency ids that aren't in the built-in list (it is replaced by the site's own list a
# moment after start; until then the box still shows the right name)
KNOWN_CURRENCY_NAMES = {"mirror": "Mirror of Kalandra", "divine": "Divine Orb", "exalted": "Exalted Orb",
                        "chaos": "Chaos Orb", "vaal": "Vaal Orb", "regal": "Regal Orb", "annul": "Orb of Annulment",
                        "alch": "Orb of Alchemy", "transmute": "Orb of Transmutation", "aug": "Orb of Augmentation",
                        "chance": "Orb of Chance", "artificers": "Artificer's Orb", "wisdom": "Scroll of Wisdom"}

MODES = ["Manual Add", "Stash tab"]          # (as saved) 2.8.1: "Manual Add" was called "Ctrl+Alt+C"
# Bulk Pricing's source switch, as it reads (owner pick, mockup A): Copy items | Read a stash tab (names.py)
MODE_LABELS = {"Manual Add": "Copy items", "Stash tab": "Read a stash tab"}
READ_HINT = "Make the tab public with one price nobody would pay, then:"


class TabReaderPage:
    """Mixed into App."""

    def build_tab_reader(self, parent):
        """The Read a stash tab row (shown with that source): the tab's price in game, the account (never its name),
        the hint and Read tab; Stop and ⓘ How, muted. The BETA note and the reading's messages under it. The switch
        itself is in Bulk Pricing's toolbar (pc_mode), the tabs' chips over it (pc_tabsrow)."""
        P1 = C["panel"]
        cfg = SETTINGS.setdefault("pctab", {})
        if cfg.get("mode") not in MODES:
            cfg["mode"] = MODES[0]
        self.pc_mode_hint = tk.Label(parent, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9))   # (not shown)
        if not hasattr(self, "pc_tabsrow"):
            self.pc_tabsrow = tk.Frame(parent, bg=P1)
        self.pctab_tabs()                                # (moves an older single tab into the list)
        box = tk.Frame(parent, bg=P1, highlightthickness=1, highlightbackground=C["line"])
        row = self.pc_tabrow_row = tk.Frame(box, bg=P1)       # (the row wraps in a narrow window: flowify)
        row.pack(fill="x", padx=12, pady=8)
        self.pc_tabrow = box
        self.pc_tabrow_after = None
        tk.Label(row, text="Tab's price in game", bg=P1, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        self.pc_amt = tk.StringVar(value=str(cfg.get("amount") or ""))
        amt = ttk.Entry(row, textvariable=self.pc_amt, width=9)
        amt.pack(side="left", padx=(8, 4))
        Tooltip(amt, "The one price the whole tab has in game (or paste the trade site's link to your tab)")
        # 2.40.0: the box is built before the trade site's full currency list arrives, so a saved Mirror of Kalandra
        # isn't in the list yet - it showed "Divine Orb", and Read tab then searched in divines. Show the saved name.
        cid = cfg.get("currency") or "divine"
        self.pc_cur = tk.StringVar(value=dict(WEALTH_CURRENCIES).get(cid) or cfg.get("currency_name")
                                   or KNOWN_CURRENCY_NAMES.get(cid) or "Divine Orb")
        cb = ttk.Combobox(row, textvariable=self.pc_cur, values=[n for _c, n in WEALTH_CURRENCIES], state="readonly",
                          width=18)
        cb.config(postcommand=lambda c=cb: c.config(values=[n for _c, n in WEALTH_CURRENCIES]))   # 2.16.0: full list
        cb.pack(side="left", padx=(0, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.pctab_cur_picked(), add="+")
        self.pc_cur_box = cb
        self.pc_acc_lbl = self.acc_mark(row, P1)          # "✓ Account set" - never the name (streams)
        self.pc_acc_lbl.pack(side="left")
        # right, as it reads: the hint, Read tab (the screen's orange button), Stop, ⓘ How
        how = self.pc_how_lbl = tk.Label(row, text="ⓘ How", bg=P1, fg=C["muted"], cursor="hand2", font=("Segoe UI", 9))
        how.pack(side="right", padx=(12, 0))
        how.bind("<Button-1>", lambda e: self.pctab_explain())
        Tooltip(how, "How reading a stash tab works (shown under this row)")
        self.pc_stop = tk.Label(row, text="■ Stop", bg=P1, fg=C["muted"], disabledforeground=C["muted"],
                                font=("Segoe UI", 9), state="disabled", cursor="hand2")      # (shown while reading)
        self.pc_stop.bind("<Button-1>", lambda e: str(self.pc_stop.cget("state")) == "normal" and self.pctab_stop())
        self.pc_stop.pack(side="right", padx=(12, 0))
        Tooltip(self.pc_stop, "Stops reading the tab (what was added stays)")
        self.pc_read_btn = ttk.Button(row, text="Read tab", style="Primary.TButton", command=self.pctab_read)
        self.pc_read_btn.pack(side="right", padx=(8, 0))
        Tooltip(self.pc_read_btn, "Finds the tab by its price and adds every item on it to this list")
        self.pc_read_hint = tk.Label(row, text=READ_HINT, bg=P1, fg=C["muted"], font=("Segoe UI", 9))
        self.pc_read_hint.pack(side="right", padx=(12, 0))
        self.pc_to_wealth = tk.Label(row, text="＋ Count it in Wealth", bg=P1, fg=C["muted"], cursor="hand2",
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
        """Is Read a stash tab the source (its list shows)?"""
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
        """3.0.6 (owner's rule: one orange button a screen): Read a stash tab - Read tab is the orange one; Copy
        items - the picked item's Search again. Re-price all is never orange."""
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
        if mode == "Stash tab":
            self.pctab_bar()
            if stash is not None and not stash.winfo_manager():
                stash.pack(fill="x", padx=12, pady=(0, 8), after=self.bk_tb)
            self.pc_tabrow.pack(fill="x")
            self.pc_beta.show(fill="x", after=self.pc_tabrow, pady=(4, 0))
            self.pc_msg.pack(fill="x", after=self.pc_tabrow if self.pc_beta.closed() else self.pc_beta)
            self.pc_mode_hint.config(text="reads a public stash tab and adds what it can (Ctrl+Alt+C still works)")
            if not self.pc_msg.cget("text"):
                self.pc_msg.config(text="Make a Premium stash tab public and give the whole tab one price nobody would "
                                        "pay (like 37882 Divine Orbs). Type that price here and press Read tab.",
                                   fg=C["muted"])
        else:
            if stash is not None:
                stash.pack_forget()
            self.pc_mode_hint.config(text="hover an item in game and press Ctrl+Alt+C")
        sm = getattr(self, "bk_sum", None)
        if sm is not None:
            flow_show(sm, self.pc_tabsrow, mode == "Stash tab")
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
        """[{id, name, amount, currency, currency_name}] - your stash tabs. An older single tab becomes "Tab 1"."""
        cfg = SETTINGS.setdefault("pctab", {})
        tabs = cfg.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            tabs = [{"id": "t1", "name": "Tab 1", "amount": cfg.get("amount"), "currency": cfg.get("currency") or "divine",
                     "currency_name": cfg.get("currency_name")}]
            cfg["tabs"], cfg["current"] = tabs, "t1"
        if cfg.get("current") not in [t["id"] for t in tabs]:
            cfg["current"] = tabs[0]["id"]
        return tabs

    def pctab_current(self):
        cfg = SETTINGS.get("pctab") or {}
        return next((t for t in self.pctab_tabs() if t["id"] == cfg.get("current")), None)

    def pctab_bar(self):
        """Your tabs as chips - "Tab 1 · 12" (the one shown outlined and marked ▸), then ＋ Tab. A click shows a tab's
        list and price; right-click renames / deletes it."""
        for w in self.pc_tabsrow.winfo_children():
            w.destroy()
        P1 = C["panel"]
        tabs = self.pctab_tabs()
        counts = {}
        for r in getattr(self, "records", {}).values():
            counts[r.get("src", "manual")] = counts.get(r.get("src", "manual"), 0) + 1
        cur = self.pctab_current()
        self.pc_tabs = {}
        for t in tabs:
            on = cur is not None and t["id"] == cur["id"]
            chip = tk.Label(self.pc_tabsrow, text=("▸ " if on else "") + f"{t['name']} · {counts.get('tab:' + t['id'], 0)}",
                            bg=C["panel2"], fg=C["text"] if on else C["muted"], font=("Segoe UI", 9), padx=12, pady=4,
                            cursor="hand2", highlightthickness=1, highlightbackground=C["text"] if on else C["line"])
            chip.pack(side="left", padx=(0, 8))
            chip.bind("<Button-1>", lambda e, n=t["name"]: self.pctab_pick(n))
            chip.bind("<Button-3>", lambda e, tid=t["id"]: self.pctab_tab_menu(e, tid))
            Tooltip(chip, f"{t['name']}: priced {t.get('amount') or '?'} {t.get('currency_name') or t.get('currency')}"
                          " in game · right-click to rename or delete")
            self.pc_tabs[t["id"]] = chip
        add = tk.Label(self.pc_tabsrow, text="＋ Tab", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9), padx=12,
                       pady=4, cursor="hand2", highlightthickness=1, highlightbackground=C["line"])   # 2.47.0
        add.pack(side="left")
        add.bind("<Button-1>", lambda e: self.pctab_new())
        Tooltip(add, "Add a tab: another stash tab, with its own price and its own list")
        if getattr(self, "bk_sum", None) is not None:
            from .bulk_page import bk_flow
            bk_flow(self.bk_sum)

    def pctab_counts_paint(self):
        """The chips' counts follow the lists, in place (only a chip whose words changed)."""
        chips = getattr(self, "pc_tabs", None)
        if not isinstance(chips, dict) or not chips:
            return
        counts = {}
        for r in self.records.values():
            counts[r.get("src", "manual")] = counts.get(r.get("src", "manual"), 0) + 1
        cur = self.pctab_current()
        for t in self.pctab_tabs():
            chip = chips.get(t["id"])
            if chip is None:
                continue
            on = cur is not None and t["id"] == cur["id"]
            text = ("▸ " if on else "") + f"{t['name']} · {counts.get('tab:' + t['id'], 0)}"
            try:
                if chip.cget("text") != text:
                    chip.config(text=text)
                    from .bulk_page import bk_flow
                    bk_flow(self.bk_sum)
            except (tk.TclError, AttributeError):
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
        return f"{t['name'] if t else 'This tab'} is empty\nRead a stash tab to list and price everything in it."

    def pctab_pick(self, label):
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if label.startswith(t["name"] + " (") or label == t["name"]), None)
        if not t:
            return
        cfg = SETTINGS.setdefault("pctab", {})
        cfg["current"] = t["id"]
        save_json("settings.json", SETTINGS)
        self.pc_amt.set(str(t.get("amount") or ""))
        self.pc_cur.set(dict(WEALTH_CURRENCIES).get(t.get("currency")) or t.get("currency_name")
                        or KNOWN_CURRENCY_NAMES.get(t.get("currency"), "Divine Orb"))
        self.pc_msg.config(text="", fg=C["muted"])
        self.pctab_bar()
        self.list_switched()

    def pctab_new(self):
        tabs = self.pctab_tabs()
        n = len(tabs) + 1
        while any(t["name"] == f"Tab {n}" for t in tabs):
            n += 1
        tid = f"t{max([int(t['id'][1:]) for t in tabs if t['id'][1:].isdigit()] + [0]) + 1}"
        tabs.append({"id": tid, "name": f"Tab {n}", "amount": None, "currency": "divine", "currency_name": "Divine Orb"})
        SETTINGS["pctab"]["current"] = tid
        save_json("settings.json", SETTINGS)
        self.pc_amt.set("")
        self.pc_cur.set("Divine Orb")
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
            t["name"] = name
            save_json("settings.json", SETTINGS)
            self.pctab_bar()

    def pctab_delete(self, tid):
        from tkinter import messagebox
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if t["id"] == tid), None)
        if not t or len(tabs) < 2:
            return
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
        cfg = SETTINGS.get("pctab") or {}
        if not hasattr(self, "_wealth_add"):
            return
        if cfg.get("amount") and self._wealth_add(cfg["amount"], cfg.get("currency") or "divine", "Price Checks tab"):
            self.pc_msg.config(text="Added to Wealth. Sync there to count it (it's read the same way).", fg=C["green"])
        self.pctab_wealth_link()

    def pctab_explain(self):
        self.pc_msg.config(fg=C["text"], text=(
            "How it works: Path of Exile 2 has no stash access for tools, so the app reads your tab through the trade "
            "site. In game: pick a Premium stash tab, make it public, and give the whole tab one price nobody would pay "
            "(e.g. 37882 Divine Orbs) - that odd price is how the app finds your tab, and a price that high keeps "
            "whispers away (your own listings never count when items are priced). Any currency works. Don't use a "
            "Merchant's tab: those "
            "sell instantly. Press Read tab: every item on it is added here and priced. Items already in the list are "
            "skipped. A new tab listing can take a minute to show on the trade site. The same tab works for Wealth."))

    def pctab_cur_picked(self):
        """2.38.0: keep the tab's currency as soon as it's picked (not only on Read tab), and give the keyboard back
        so nothing else can change it."""
        cur = self.pctab_cur_id()
        if cur:
            cfg = SETTINGS.setdefault("pctab", {})
            cfg.update(currency=cur, currency_name=self.pc_cur.get())     # 2.40.0: the name too (see the box)
            save_json("settings.json", SETTINGS)
        cb = getattr(self, "pc_cur_box", None)

        def done():                                    # 2.40.0: no lingering highlight; the keyboard leaves the box
            try:
                cb.selection_clear()
                cb.winfo_toplevel().focus_set()
            except (tk.TclError, AttributeError):
                self.root.focus_set()
        self.root.after(20, done)

    def ev_currencies_loaded(self):
        """2.40.0: the trade site's full currency list arrived - show the saved currency by its name."""
        cfg = SETTINGS.get("pctab") or {}
        name = dict(WEALTH_CURRENCIES).get(cfg.get("currency"))
        if name and getattr(self, "pc_cur", None) is not None and self.pc_cur.get() != name:
            self.pc_cur.set(name)
            cfg["currency_name"] = name

    def pctab_cur_id(self):
        """The currency id for what the box shows - from the trade site's list, or the saved one when the box shows
        the saved name (the list may not be loaded yet)."""
        name = self.pc_cur.get()
        cur = next((c for c, n in WEALTH_CURRENCIES if n == name), None)
        cfg = SETTINGS.get("pctab") or {}
        if cur is None and name and name == cfg.get("currency_name"):
            cur = cfg.get("currency")
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
            self.pc_amt.set(str(amount))
            self.pc_cur.set(dict(WEALTH_CURRENCIES).get(cur, cur))
            SETTINGS.setdefault("pctab", {})["currency_name"] = self.pc_cur.get()
        else:
            amount, cur = parse_price_text(txt)
            cur = cur or self.pctab_cur_id() or "divine"
        cfg = SETTINGS.setdefault("pctab", {})
        cfg.update(amount=amount, currency=cur)
        t = self.pctab_current()                       # 2.42.0: this tab's price
        if t is not None:
            t.update(amount=amount, currency=cur, currency_name=self.pc_cur.get())
            PCTAB["src"] = f"tab:{t['id']}"
        if dict(WEALTH_CURRENCIES).get(cur):
            cfg["currency_name"] = dict(WEALTH_CURRENCIES)[cur]
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
                "has the trade site had a minute to show it? Check the account name too (with its #number)."))
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
