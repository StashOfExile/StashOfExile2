"""Bulk Pricing's tabs: plain named lists of the items you add with Ctrl+Alt+C (Manually Add) - Tab 1, Tab 2, ＋ Tab.
Ctrl+Alt+C adds to the tab shown. A tab you never renamed is named by its place ("Tab 2"; close Tab 1 and Tab 2 is
Tab 1); right-click renames or closes one. 3.0.7 (GGG policy audit): tabs no longer read a stash tab, and have no price.
The first tab's items are saved as src "manual" (the one list before tabs); the others as "tab:<id>"."""
import re
import tkinter as tk
from tkinter import ttk

from . import buglog
from .config import save_json, SETTINGS
from .style import C, Tooltip

FIRST = "manual"                 # the first tab's id (its items keep src "manual")
# owner: a tab you never renamed is named by its place - "Tab 1", "Tab 2" ... (close Tab 1 and Tab 2 becomes Tab 1);
# a name of the form "Tab <n>" is kept for that, so a tab renamed to one goes back to its place's name
TAB_AUTO = re.compile(r"Tab \d+")


def tab_src(t):
    """A tab's records are saved with this src."""
    return "manual" if t["id"] == FIRST else f"tab:{t['id']}"


class BulkTabsPage:
    """Mixed into App."""

    def build_bulk_tabs(self, parent):
        """The tabs' strip: a chip per tab ("▸ Tab 1 · 12" is the one shown), then ＋ Tab; it wraps in a narrow
        window."""
        P1 = C["panel"]
        self.pc_box_bg = C["panel2"]                 # (the shown tab's fill)
        self.pctab_tabs()
        strip = self.pc_tabsrow = tk.Frame(parent, bg=P1, height=24)
        strip.pack_propagate(False)
        strip.pack(fill="x")
        self.pc_add_btn = ttk.Button(strip, text="＋ Tab", style="Strip.TButton", cursor="hand2", command=self.pctab_new)
        Tooltip(self.pc_add_btn, "Add a tab: another list of its own")
        self.pc_tab_widgets, self.pc_tab_wrap, self.pc_tab_tips, self._pc_bar_sig = [], {}, {}, None
        self.pc_tabs, self.pc_sel_wrap = {}, None
        strip.bind("<Configure>", lambda e: self.pctab_strip_layout(), add="+")
        self.pctab_bar()

    # ---------------- which list shows
    def list_src(self):
        """Which list Bulk Pricing shows: the shown tab's src ("manual" for the first tab, "tab:<id>" for another)."""
        t = self.pctab_current()
        return tab_src(t) if t else "manual"

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
        """[{id, name, renamed}] - the tabs, in order (at least one: Tab 1). A tab you never renamed is named by its
        place ("Tab 2"); one you renamed keeps its name."""
        cfg = SETTINGS.setdefault("pctab", {})
        tabs = cfg.get("tabs")
        if not isinstance(tabs, list) or not tabs:
            tabs = [{"id": FIRST, "name": "Tab 1", "renamed": False}]
            cfg["tabs"], cfg["current"] = tabs, FIRST
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

    def pctab_many(self):
        """More than one tab (the page then says which one shows)."""
        return len(self.pctab_tabs()) > 1

    # ---------------- the strip
    def pctab_chip_text(self, t, counts, on):
        return ("▸ " if on else "") + f"{t['name']} · {counts.get(tab_src(t), 0)}"

    def pctab_chip_tip(self, t, counts=None):
        n = (counts if counts is not None else self.pctab_counts()).get(tab_src(t), 0)
        return f"{t['name']}: {n} item{'s' if n != 1 else ''} · right-click to rename or close it"

    def pctab_counts(self):
        counts = {}
        for r in getattr(self, "records", {}).values():
            counts[r.get("src", "manual")] = counts.get(r.get("src", "manual"), 0) + 1
        return counts

    def pctab_bar(self):
        """The tabs as chips - "Tab 1 · 12" (the one shown is bold and marked ▸), then ＋ Tab. A click shows a tab's
        list; right-click renames / closes it. Built again only when the tabs or the shown one changed; else painted in
        place."""
        if getattr(self, "pc_tabsrow", None) is None:
            return
        tabs = self.pctab_tabs()
        cur = self.pctab_current()
        sig = tuple((t["id"], cur is not None and t["id"] == cur["id"]) for t in tabs)
        if sig == self._pc_bar_sig and all(w.winfo_exists() for w in self.pc_tab_widgets):
            return self.pctab_counts_paint()
        for w in self.pc_tab_widgets:
            w.destroy()
        counts = self.pctab_counts()
        self.pc_tabs, self.pc_tab_wrap, self.pc_tab_tips, self.pc_tab_widgets = {}, {}, {}, []
        self.pc_sel_wrap = None
        for t in tabs:
            on = cur is not None and t["id"] == cur["id"]
            text = self.pctab_chip_text(t, counts, on)
            if on:                                       # the shown tab: its own fill and outline, bold
                wrap = tk.Frame(self.pc_tabsrow, bg=C["line"])
                chip = tk.Label(wrap, text=text, bg=self.pc_box_bg, fg=C["text"], font=("Segoe UI", 9, "bold"),
                                padx=8, pady=4)
                chip.pack(padx=1, pady=1)
                self.pc_sel_wrap = wrap
            else:
                wrap = chip = ttk.Button(self.pc_tabsrow, text=text, style="Strip.TButton", cursor="hand2",
                                         command=lambda n=t["name"]: self.pctab_pick(n))   # (round, outlined)
            for w in (wrap, chip):
                w.bind("<Button-3>", lambda e, tid=t["id"]: self.pctab_tab_menu(e, tid), add="+")
            self.pc_tab_tips[t["id"]] = Tooltip(chip, self.pctab_chip_tip(t, counts))
            if on:
                wrap.bind("<Enter>", self.pc_tab_tips[t["id"]]._enter, add="+")
                wrap.bind("<Leave>", self.pc_tab_tips[t["id"]]._leave, add="+")
            self.pc_tabs[t["id"]], self.pc_tab_wrap[t["id"]] = chip, wrap
            self.pc_tab_widgets.append(wrap)
        self._pc_bar_sig = sig
        self.pctab_strip_layout()

    def pctab_counts_paint(self):
        """The chips' counts follow the lists, in place (only a chip whose words changed)."""
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
                    tip.text = self.pctab_chip_tip(t, counts)
            except (tk.TclError, AttributeError):
                pass
        if changed:
            self.pctab_strip_layout()

    def pctab_strip_layout(self):
        """The chips and ＋ Tab in order, wrapping when the window is narrow."""
        strip = getattr(self, "pc_tabsrow", None)
        if strip is None or not self.pc_tab_widgets:
            return
        try:
            kids = self.pc_tab_widgets + [self.pc_add_btn]
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
            y = 0
            for li, line in enumerate(lines):
                h = max(w.winfo_reqheight() for w in line)
                x = 0
                for w in line:
                    w.place(x=x, y=y + (h - w.winfo_reqheight()) // 2)
                    x += w.winfo_reqwidth() + 8
                y += h + (4 if li < len(lines) - 1 else 0)
            if int(strip.cget("height")) != y:
                strip.configure(height=y)
        except tk.TclError:
            pass

    # ---------------- picking, adding, renaming, closing
    def pctab_pick(self, label):
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if label.startswith(t["name"] + " (") or label == t["name"]), None)
        if not t:
            return
        SETTINGS.setdefault("pctab", {})["current"] = t["id"]
        save_json("settings.json", SETTINGS)
        self.pctab_bar()
        self.list_switched()

    def pctab_new(self):
        tabs = self.pctab_tabs()
        n = len(tabs) + 1                                # (named by its place: the last)
        tid = f"t{max([int(t['id'][1:]) for t in tabs if t['id'][1:].isdigit()] + [0]) + 1}"
        tabs.append({"id": tid, "name": f"Tab {n}", "renamed": False})
        SETTINGS["pctab"]["current"] = tid
        save_json("settings.json", SETTINGS)
        self.pctab_bar()
        self.list_switched()

    def pctab_tab_menu(self, e, tid):
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84",
                    activeforeground="#ffffff")
        m.add_command(label="Rename…", command=lambda: self.pctab_rename(tid))
        m.add_command(label="Close this tab and its list", command=lambda: self.pctab_delete(tid),
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
            self._pc_bar_sig = None                      # (the words changed: built again)
            self.pctab_bar()
            self.list_note()

    def pctab_delete(self, tid):
        from tkinter import messagebox
        tabs = self.pctab_tabs()
        t = next((t for t in tabs if t["id"] == tid), None)
        if not t or len(tabs) < 2:
            return
        src = tab_src(t)
        n = sum(1 for r in self.records.values() if r.get("src", "manual") == src)
        if n and not messagebox.askyesno("Close tab", f"Close {t['name']} and remove its {n} item(s) from the list?",
                                         parent=self.dlg_parent()):
            return
        for rid in [rid for rid, r in self.records.items() if r.get("src", "manual") == src]:
            del self.records[rid]
        tabs.remove(t)
        cfg = SETTINGS["pctab"]
        if cfg.get("current") == tid:
            cfg["current"] = tabs[0]["id"]
        self.pctab_tabs()                                # (the tabs after it move up: Tab 2 is Tab 1 now)
        self.dirty = True
        save_json("settings.json", SETTINGS)
        self._pc_bar_sig = None
        cur = self.pctab_current()
        self.pctab_pick(cur["name"] if cur else tabs[0]["name"])


__all__ = ["BulkTabsPage", "FIRST", "TAB_AUTO", "tab_src"]
