"""Overlay ↳ League Plan (2.73.0 as Game Plan / League Focus; one name from 2.119.0): goals by phase, a stockpile to buy while it's cheap, the farm
plan and the reminder settings - set once at league start, then forget it. 3.2.0 rework (owner's mockups): Done when
instead of Target, a real Show on overlay button, a Farm plan with a working strat picker and a Goal the log can see,
Reminders cut to what matters, the build lock gone. focus.py keeps the plan; the overlay's goal line and the
reminders bring it back when it matters. Every switch is a toggle; everything is
drawn with the app's theme (chrome sections, Card.* styles), so a theme swap repaints it like every other page."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import focus as F
from .chrome import section as chrome_section
from .config import SETTINGS
from .style import C, ScrollArea, SegBar, Tooltip, autowrap


def _num(text):
    try:
        return float(str(text).replace(",", ".").strip())
    except ValueError:
        return None


class GamePlanPage:
    """Mixed into App. 2.73.4 (feedback: it all blends together): one look for every part - what's in it
    first, then a hairline and a small ADD heading over its form, labels in one column, the same + Add button
    everywhere; phase headings with counts, goal details on a quieter second line, a summary strip on top."""

    # ---------------- the parts every section uses
    @staticmethod
    def _gp_head(parent, text, color=None, top=12, count=None):
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", pady=(top, 4))
        tk.Label(row, text=text, bg=parent["bg"], fg=color or C["steel"], font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(side="left")
        if count is not None:
            tk.Label(row, text=f"  {count}", bg=parent["bg"], fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        return row

    @staticmethod
    def _gp_empty(parent, text):
        tk.Label(parent, text=text, bg=parent["bg"], fg=C["muted"], font=("Segoe UI", 9, "italic"), anchor="w",
                 justify="left").pack(fill="x", pady=(0, 2))
        autowrap(parent.pack_slaves()[-1])                  # D3: wraps at Drawer width

    def _gp_add_area(self, box, title):
        """A hairline, a small heading, and the form under it (a grid: labels in column 0)."""
        tk.Frame(box, bg=C["line"], height=1).pack(fill="x", pady=(12, 0))
        self._gp_head(box, title, top=8)
        form = tk.Frame(box, bg=box["bg"])
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        return form

    @staticmethod
    def _gp_label(form, row, text):
        tk.Label(form, text=text, bg=form["bg"], fg=C["muted"], font=("Segoe UI", 9), anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=2)

    @staticmethod
    def _gp_table_head(box, cols, weights=None):
        for c, h in enumerate(cols):
            tk.Label(box, text=h, bg=box["bg"], fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w").grid(
                row=0, column=c, sticky="w", padx=(0, 12))
        tk.Frame(box, bg=C["line"], height=1).grid(row=1, column=0, columnspan=len(cols) + 1, sticky="ew",
                                                    pady=(2, 4))

    @staticmethod
    def _gp_bar(parent, frac, w=64):
        cv = tk.Canvas(parent, width=w, height=6, bg=parent["bg"], highlightthickness=0)
        cv.create_rectangle(0, 1, w - 1, 5, fill=C["panel"], outline=C["line"])
        if frac:
            cv.create_rectangle(0, 1, int((w - 1) * min(1.0, frac)), 5, fill=C["green"] if frac >= 1 else C["accent"],
                                outline="")
        return cv

    # ---------------- the page
    def build_game_plan(self, body):
        P1, P2 = C["panel"], C["panel2"]
        f = F.cfg()
        page = tk.Frame(body, bg=P1)
        top = tk.Frame(page, bg=P2, padx=12, pady=8, highlightthickness=1, highlightbackground=C["line"])
        top.pack(fill="x", padx=8, pady=(8, 8))
        self.gp_on = tk.BooleanVar(value=bool(f["on"]))
        ttk.Checkbutton(top, text="Goal on the overlay + reminders", variable=self.gp_on, command=self.gp_switch,
                        style="Card.TCheckbutton").pack(side="left")
        self.gp_summary = tk.Label(top, text="", bg=P2, fg=C["text"], font=("Segoe UI", 9), anchor="e")
        self.gp_summary.pack(side="right")
        sa = ScrollArea(page, bg=P1)
        sa.pack(fill="both", expand=True)
        grid = tk.Frame(sa.inner, bg=P1, padx=8)
        grid.pack(fill="both", expand=True)
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform="gp")
        left, right = tk.Frame(grid, bg=P1), tk.Frame(grid, bg=P1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._gp_goals(left)
        # P5 (2.108.0): the right side is tabs - one part at a time
        tabs = ("Stockpile", "Farm plan", "Reminders")        # (2.131.2: Map supplies moved to Top Up Reminders)
        self.gp_tabs = SegBar(right, list(tabs), command=self.gp_tab, size=10, pad=(12, 4), bg=P1)
        self.gp_tabs.pack(anchor="w", pady=(0, 8))
        self.gp_tab_frames = {}
        for name, fn in zip(tabs, ((self._gp_stock,), (self._gp_farms,), (self._gp_pokes,))):
            fr = tk.Frame(right, bg=P1)
            for build in fn:
                build(fr)
            self.gp_tab_frames[name] = fr
        self.gp_tab(tabs[0])
        self.gp_fill()
        return page

    def gp_tab(self, name):
        for n, fr in self.gp_tab_frames.items():
            if n == name:
                fr.pack(fill="x")
            else:
                fr.pack_forget()
        if self.gp_tabs.get() != name:
            self.gp_tabs.pick(name, notify=False)

    def gp_view_pick(self, name):
        """P5 (2.108.0): the Goals tabs show one phase; + Add adds to the phase on show."""
        self.gp_new_phase.set(name)
        if self.gp_view.get() != name:
            self.gp_view.pick(name, notify=False)
        self._gp_goal_rows()

    def gp_summary_text(self):
        f = F.cfg()
        open_ = sum(1 for g in f["goals"] if not g["done"])
        bits = [f"{open_} goal{'s' if open_ != 1 else ''} open"]
        if f["stockpile"]:
            bits.append(f"{len(f['stockpile'])} to stockpile")
        if f["farms"]:
            bits.append(f"{len(f['farms'])} farm{'s' if len(f['farms']) != 1 else ''}")
        bits.append(("reminders on" if int(f["pokes"].get("per_hour") or 0) else "reminders off") if f["on"] else "not on the overlay")
        return "  ·  ".join(bits)

    # ---------------- A: goals by phase
    def _gp_goals(self, parent):
        P2 = C["panel2"]
        o, box = chrome_section(parent, "Goals", "One phase at a time. The phase moves to maps by itself when the "
                                                 "log shows you in a waystone map.", wrap=True)
        o.pack(fill="x", pady=(0, 12))
        f = F.cfg()
        self.gp_new_phase = tk.StringVar(value=F.phase_name(f["phase"]))
        self.gp_view = SegBar(box, [n for _k, n in F.PHASES], command=self.gp_view_pick, size=9, pad=(8, 4), bg=P2)
        self.gp_view.pack(anchor="w", pady=(0, 8))
        self.gp_view.pick(self.gp_new_phase.get(), notify=False)
        self.gp_now_row = tk.Frame(box, bg=P2)
        self.gp_now_row.pack(fill="x", pady=(0, 4))
        self.gp_goal_box = tk.Frame(box, bg=P2)
        self.gp_goal_box.pack(fill="x")
        form = self._gp_add_area(box, "ADD A GOAL TO THIS PHASE")
        self._gp_label(form, 0, "Goal")
        self.gp_new = tk.StringVar()
        e = ttk.Entry(form, textvariable=self.gp_new)
        e.grid(row=0, column=1, sticky="ew", pady=2)
        e.bind("<Return>", lambda ev: self.gp_add_goal())
        self._gp_label(form, 1, "Done when")
        r1 = tk.Frame(form, bg=P2)
        r1.grid(row=1, column=1, sticky="ew", pady=2)
        self.gp_new_tkind = tk.StringVar(value=F.DONE_WHEN[0][1])
        cb = ttk.Combobox(r1, textvariable=self.gp_new_tkind, state="readonly", width=26,
                          values=[n for _k, n, _u in F.DONE_WHEN])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.gp_target_hint())
        self.gp_new_target_lbl = tk.Label(r1, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9))
        self.gp_new_target = tk.StringVar()
        ok = (self.root.register(self._gp_digits_ok), "%P")       # 3.2.1 owner: digits only, in its range
        self.gp_new_target_e = ttk.Entry(r1, textvariable=self.gp_new_target, width=6, validate="key",
                                         validatecommand=ok)
        self.gp_new_target_e.bind("<Return>", lambda ev: self.gp_add_goal())
        self.gp_new_act = ttk.Combobox(r1, textvariable=self.gp_new_target, state="readonly", width=4,
                                       values=[str(n) for n in range(1, F.TARGET_RANGE["act"][1] + 1)])
        self.gp_target_note = tk.Label(form, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w",
                                       justify="left")
        self.gp_target_note.grid(row=2, column=1, sticky="ew")
        autowrap(self.gp_target_note)
        ttk.Button(form, text="+ Add goal", style="Primary.TButton", command=self.gp_add_goal).grid(
            row=3, column=1, sticky="e", pady=(8, 0))
        self.gp_target_hint()

    def gp_target_kind(self):
        """The Done when picked -> its kind; "tick" (I tick it myself) -> None."""
        lab = self.gp_new_tkind.get()
        k = next((k for k, n, _u in F.DONE_WHEN if n == lab), "tick")
        return None if k == "tick" else k

    def _gp_digits_ok(self, text):
        """The number box takes digits only, up to the top of the picked Done when's range."""
        if text == "":
            return True
        if not text.isdigit():
            return False
        lo_hi = F.TARGET_RANGE.get(self.gp_target_kind() or "")
        return lo_hi is None or int(text) <= lo_hi[1]

    def gp_target_hint(self):
        """What the Done when does, in one line, with its range; a number box for a level or maps, a list of acts."""
        k = self.gp_target_kind() or "tick"
        note = F.DONE_HINT.get(k, "")
        rng = F.TARGET_RANGE.get(k)
        if rng and k != "act":
            note += f" {rng[0]} to {rng[1]}."
        self.gp_target_note.config(text=note)
        unit = dict((kk, u) for kk, _n, u in F.DONE_WHEN).get(k, "")
        self.gp_new_target.set("1" if k == "act" else "")
        self.gp_new_target_e.pack_forget()
        self.gp_new_act.pack_forget()
        if unit:
            self.gp_new_target_lbl.config(text=unit)
            self.gp_new_target_lbl.pack(side="left", padx=(12, 8))
            (self.gp_new_act if k == "act" else self.gp_new_target_e).pack(side="left")
        else:
            self.gp_new_target_lbl.pack_forget()

    def gp_add_goal(self):
        text = self.gp_new.get().strip()
        if not text:
            return None
        phase = next((k for k, n in F.PHASES if n == self.gp_new_phase.get()), "start")
        trig = "town"                                      # 3.2.1 owner: in town only, no choice
        kind = self.gp_target_kind() if hasattr(self, "gp_new_tkind") else None
        n = _num(self.gp_new_target.get()) if self.gp_new_target.get().strip() else None
        if kind == "reach_maps":
            n = 1
        rng = F.TARGET_RANGE.get(kind or "")
        if rng and n is not None:
            n = min(max(n, rng[0]), rng[1])
        if kind and not n:                                 # (a number Done when with no number: you tick it)
            kind = None
        g = F.add_goal(text, phase, trig, target_kind=kind, target=n)
        self.gp_new.set("")
        self.gp_target_hint()
        self.gp_fill()
        self.gp_overlay()
        return g

    def _gp_goal_rows(self):
        P2 = C["panel2"]
        box = self.gp_goal_box
        for w in box.winfo_children():
            w.destroy()
        f = F.cfg()
        self.gp_goal_vars = {}
        name = self.gp_new_phase.get() if hasattr(self, "gp_new_phase") else F.phase_name(f["phase"])
        key = next((k for k, n in F.PHASES if n == name), f["phase"])
        nr = getattr(self, "gp_now_row", None)
        if nr is not None:                                 # P5 (2.108.0): which phase you're in, one click to move
            for w in nr.winfo_children():
                w.destroy()
            if f["phase"] == key:
                tk.Label(nr, text=" NOW ", bg=C["good"], fg=C["bg"], font=("Segoe UI", 9, "bold")).pack(side="left")
                tk.Label(nr, text="  the phase you're in", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
            else:
                tk.Label(nr, text="You're in " + F.phase_name(f["phase"]), bg=P2, fg=C["muted"],
                         font=("Segoe UI", 9)).pack(side="left")
                ttk.Button(nr, text="I'm here now", style="Quiet.TButton",
                           command=lambda n=name: self.gp_phase_pick(n)).pack(side="left", padx=(8, 0))
        gs = F.goals_of(key)
        self._gp_done_lbl, self._gp_now_btns, self._gp_on_lbls, self._gp_key = None, {}, {}, key
        if gs:
            self._gp_done_lbl = self._gp_head(box, f"{sum(1 for g in gs if g['done'])} / {len(gs)} done",
                                              top=0).winfo_children()[0]
        if not gs:
            self._gp_empty(box, "No goals for this phase yet. Add one below.")
        for g in gs:
            r = tk.Frame(box, bg=P2)
            r.pack(fill="x", pady=(4, 0))
            v = tk.BooleanVar(value=bool(g["done"]))
            self.gp_goal_vars[g["id"]] = v
            # 3.2.1 owner: the On / Off switch read as "show it" - a Done box: a mark and a word, never color alone
            tick = tk.Label(r, bg=P2, cursor="hand2", font=("Segoe UI", 10), padx=2)
            tick.pack(side="left")
            self._gp_tick_paint(tick, v.get())
            tick.bind("<Button-1>", lambda e, gid=g["id"], v=v, t=tick: (v.set(not v.get()),
                                                                          self._gp_tick_paint(t, v.get()),
                                                                          self.gp_goal_tick(gid, v)))
            Tooltip(tick, "Tick it when the goal is done")
            tk.Label(r, text=g["text"], bg=P2, fg=C["muted"] if g["done"] else C["text"],
                     font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))
            x = tk.Label(r, text="✕", bg=P2, fg=C["muted"], cursor="hand2", padx=4)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, gid=g["id"]: (F.remove_goal(gid), self.gp_fill(), self.gp_overlay()))
            Tooltip(x, "Remove this goal")
            # 3.2.0 (owner: the ▸ looked clickable and did nothing): a real button that puts it on the overlay,
            # and on the one shown, a mark and a word that is no button at all
            b = ttk.Button(r, text=self.SHOW_ON, style="Quiet.TButton", command=lambda gid=g["id"]: self.gp_set_now(gid))
            self._gp_now_btns[g["id"]] = b
            self._gp_on_lbls[g["id"]] = tk.Label(r, text=self.ON_OVERLAY, bg=P2, fg=C["accent"],
                                                 font=("Segoe UI", 9, "bold"))
            meta = tk.Frame(box, bg=P2)                # the quieter second line: progress, then when it reminds
            meta.pack(fill="x", padx=(24, 0), pady=(0, 4))
            kind, target = F.goal_target(g)
            if g["done"]:
                tk.Label(meta, text="✓ Done · " + ("the game's log ticked it" if g.get("auto_done") else "you ticked it"),
                         bg=P2, fg=C["good"], font=("Segoe UI", 9)).pack(side="left")
            elif kind:
                have, _t = F.progress(g)
                self._gp_bar(meta, have / target if target else 0).pack(side="left", padx=(0, 8))
                tk.Label(meta, text=F.progress_text(g) + " · from the game's log", bg=P2, fg=C["text"],
                         font=("Segoe UI", 9)).pack(side="left")
        self._gp_goal_paint()

    @staticmethod
    def _gp_tick_paint(lbl, done):
        lbl.config(text="☑ Done" if done else "☐ Done", fg=C["good"] if done else C["muted"])

    def gp_goal_tick(self, gid, v):
        """A goal ticked. UI rule 22: only the "x / y done" line, the overlay buttons and the summary change - the goal
        rows are not built again (nor the stockpile and farm rows)."""
        F.set_done(gid, v.get())
        if not self._gp_goal_paint():
            self.gp_fill()
        elif hasattr(self, "gp_summary"):
            self.gp_summary.config(text=self.gp_summary_text())
        self.gp_overlay()

    ON_OVERLAY, SHOW_ON = "✓ On the overlay", "Show on overlay"

    def _gp_goal_paint(self):
        """The done count and each goal's overlay mark, in place: the one shown says ✓ On the overlay in orange text,
        no button; an open one has a Show on overlay button; a done one has neither."""
        lbl, btns, key = getattr(self, "_gp_done_lbl", None), getattr(self, "_gp_now_btns", None), \
            getattr(self, "_gp_key", None)
        gs = F.goals_of(key) if key else []
        try:
            if btns is None or sorted(btns) != sorted(g["id"] for g in gs) or \
                    not all(b.winfo_exists() for b in btns.values()):
                return False
            if lbl is not None and lbl.winfo_exists():
                lbl.config(text=f"{sum(1 for g in gs if g['done'])} / {len(gs)} done")
            cur = F.current()
            lbls = getattr(self, "_gp_on_lbls", {})
            for g in gs:
                b, lab = btns[g["id"]], lbls.get(g["id"])
                now = not g["done"] and cur is not None and cur["id"] == g["id"]
                show, hide = (lab, b) if now else (b, lab)
                if hide is not None:
                    hide.pack_forget()
                if g["done"]:
                    if show is not None:
                        show.pack_forget()
                    continue
                if show is not None and not show.winfo_ismapped():
                    show.pack(side="right", padx=8)
        except tk.TclError:
            return False
        return True

    def gp_set_now(self, gid):
        """Show on overlay - 3.2.1 owner: with the plan's overlay line off, this turns it on too."""
        F.cfg()["now"] = gid
        F.save()
        if not F.cfg().get("on"):
            self.focus_set_on(True)
        if getattr(self, "mg_hidden", False) and hasattr(self, "overlay_hide_toggle"):
            self.overlay_hide_toggle()                      # hidden with F6: shown again
        if not self._gp_goal_paint():                       # (UI rule 22: only the ▸ marks change)
            self.gp_fill()
        self.gp_overlay()

    def gp_phase_pick(self, name):
        F.set_phase(next((k for k, n in F.PHASES if n == name), "start"))
        if hasattr(self, "gp_view"):
            self.gp_new_phase.set(name)
            self.gp_view.pick(name, notify=False)
        self.gp_fill()
        self.gp_overlay()

    def gp_switch(self):
        self.focus_set_on(bool(self.gp_on.get()))

    def focus_set_on(self, on):
        """League Focus on / off - the page's switch, the overlay's Focus switch and Options › On the overlay."""
        F.cfg()["on"] = bool(on)
        F.save()
        rows = getattr(self, "al_rows", None) or {}                # 2.90.0: Helpers › Focus follows too
        for var in (getattr(self, "gp_on", None), getattr(self, "tk_focus_var", None),
                    (rows.get("focus") or {}).get("on")):
            if var is not None and bool(var.get()) != bool(on):
                var.set(bool(on))
        self.gp_overlay()
        if hasattr(self, "gp_summary"):
            self.gp_summary.config(text=self.gp_summary_text())

    def gp_overlay(self):
        """Redraw the overlay (its focus line and Focus switch follow the plan). UI rule 22: when only the goal's
        words or progress changed, the NOW line changes where it is."""
        try:
            if self.focus_redraw():
                return
            self.merged_build()
        except Exception:
            buglog.caught()

    def gp_worth(self):
        """2.73.2: not used any more (Wealth doesn't track live) - goals carry the progress you type."""
        return None

    # ---------------- B: stockpile
    def _gp_stock(self, parent):
        P2 = C["panel2"]
        o, box = chrome_section(parent, "Stockpile", "What to buy and sit on. Have is what you type, "
                                                                       "and Enter keeps it. Now is poe.ninja's price for your "
                                                                       "league.", wrap=True)
        o.pack(fill="x", pady=(0, 12))
        self.gp_stock_box = tk.Frame(box, bg=P2)
        self.gp_stock_box.pack(fill="x")
        form = self._gp_add_area(box, "ADD TO STOCKPILE")
        self.gp_s_name, self.gp_s_goal, self.gp_s_under = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.gp_s_cat, self.gp_s_pick = tk.StringVar(value="All"), tk.StringVar()
        self._gp_label(form, 0, "Item")
        r0 = tk.Frame(form, bg=P2)
        r0.grid(row=0, column=1, sticky="ew", pady=2)
        self.gp_s_catbox = ttk.Combobox(r0, textvariable=self.gp_s_cat, state="readonly", width=14,
                                        postcommand=self.gp_stock_catalog)
        self.gp_s_catbox.pack(side="left")
        self.gp_s_catbox.bind("<<ComboboxSelected>>", lambda e: self.gp_stock_filter())
        # 2.98.5 (feedback): the item box is pick-only - typing goes in the name box below, which also narrows it
        self.gp_s_pickbox = ttk.Combobox(r0, textvariable=self.gp_s_pick, state="readonly",
                                         postcommand=lambda: self.gp_stock_filter(typed=True))
        self.gp_s_pickbox.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.gp_s_pickbox.bind("<<ComboboxSelected>>", lambda e: self.gp_s_name.set(""))
        Tooltip(self.gp_s_pickbox, "Pick an item. Type in the box below to narrow this list.")
        self._gp_label(form, 1, "Or any name")
        ne = ttk.Entry(form, textvariable=self.gp_s_name)
        ne.grid(row=1, column=1, sticky="ew", pady=2)
        ne.bind("<KeyRelease>", lambda e: self.gp_stock_filter(typed=True))
        Tooltip(ne, "Any item by name. What you type here also narrows the list above.")
        self._gp_label(form, 2, "How many")
        r2 = tk.Frame(form, bg=P2)
        r2.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Entry(r2, textvariable=self.gp_s_goal, width=7).pack(side="left")
        bu = tk.Frame(r2, bg=P2)                             # (2.98.0: "Buy under [ ] div each" stays together)
        bu.pack(side="left", padx=(12, 0))
        tk.Label(bu, text="Buy under (div)", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        ttk.Entry(bu, textvariable=self.gp_s_under, width=7).pack(side="left")
        ttk.Button(r2, text="+ Add", command=self.gp_add_stock).pack(side="right")
        from .style import flowify
        flowify(r2)                                          # 2.98.0: wraps in a narrow window

    def gp_stock_catalog(self):
        """The Currency Exchange's groups (Currency, Omens, Essences ...) for the first box."""
        from . import bulk
        self.gp_s_groups = dict(bulk.catalog())
        cats = ["All"] + list(self.gp_s_groups)
        self.gp_s_catbox.configure(values=cats)
        if not self.gp_s_cat.get():
            self.gp_s_cat.set("All")
        return cats

    def gp_stock_filter(self, typed=False):
        """The items of the picked group, narrowed to what you've typed."""
        if not getattr(self, "gp_s_groups", None):
            self.gp_stock_catalog()
        g = self.gp_s_cat.get() or "All"
        names = ([n for ns in self.gp_s_groups.values() for n in ns] if g == "All"
                 else list(self.gp_s_groups.get(g, [])))
        q = self.gp_s_name.get().strip().lower() if typed else ""
        if q:
            names = [n for n in names if q in n.lower()]
        self.gp_s_pickbox.configure(values=names[:400])
        return names

    def gp_add_stock(self):
        typed, pick = self.gp_s_name.get().strip(), self.gp_s_pick.get().strip()
        # typed by hand wins - unless it only narrowed the list to the item you then picked (2.98.5)
        name = pick if pick and (not typed or typed.lower() in pick.lower()) else typed
        if not name:
            return None
        row = F.add_stock(name, int(_num(self.gp_s_goal.get()) or 0), _num(self.gp_s_under.get()))
        for v in (self.gp_s_name, self.gp_s_goal, self.gp_s_under, self.gp_s_pick):
            v.set("")
        self.gp_fill()
        return row

    def gp_have(self, name):
        """2.73.2: what you typed for it (Wealth isn't used - it doesn't track live)."""
        return F.stock_have(name)

    def gp_each(self, name):
        """Its price in divines - always your league's (2.73.4), or None."""
        try:
            from .wealth import WPRICES
            return WPRICES.named(name)
        except Exception:
            return None

    def gp_stock_have(self, name, text):
        n = _num(text)
        if n is not None and F.stock_have(name) != int(n):
            F.set_stock_have(name, n)
            self.gp_fill()

    def _gp_stock_rows(self):
        P2 = C["panel2"]
        box = self.gp_stock_box
        for w in box.winfo_children():
            w.destroy()
        rows = F.cfg()["stockpile"]
        if not rows:
            self._gp_empty(box, "Nothing yet - add what's cheap at league start and worth more later.")
            return
        self._gp_table_head(box, ("Item", "Have / qty", "Buy under", "Now"))
        self.gp_stock_state = {}
        for i, r in enumerate(rows, 2):
            have, each = self.gp_have(r["name"]), self.gp_each(r["name"])
            st = F.stock_status(r, have, each)
            self.gp_stock_state[r["name"]] = st
            tk.Label(box, text=r["name"], bg=P2, fg=C["text"], font=("Segoe UI", 10), anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=1)
            hf = tk.Frame(box, bg=P2)
            hf.grid(row=i, column=1, sticky="w", padx=(0, 12), pady=1)
            hv = tk.StringVar(value=str(have or 0))
            he = ttk.Entry(hf, textvariable=hv, width=5)
            he.pack(side="left")
            he.bind("<Return>", lambda e, n=r["name"], hv=hv: self.gp_stock_have(n, hv.get()))
            he.bind("<FocusOut>", lambda e, n=r["name"], hv=hv: self.gp_stock_have(n, hv.get()))
            tk.Label(hf, text=f" / {r['goal'] or '-'}", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
            tk.Label(box, text=f"{r['under']:g} div" if r.get("under") is not None else "-", bg=P2, fg=C["muted"],
                     font=("Segoe UI", 9), anchor="w").grid(row=i, column=2, sticky="w", padx=(0, 12), pady=1)
            now = (f"{each:.3g} div" if each is not None else "no price") + \
                  ("  · cheap" if st == "cheap" else "  · done" if st == "done" else "")
            tk.Label(box, text=now, bg=P2, fg=C["green"] if st in ("cheap", "done") else
                     (C["text"] if each is not None else C["muted"]),
                     font=("Segoe UI", 9, "bold" if st == "cheap" else "normal"), anchor="w").grid(
                row=i, column=3, sticky="w", padx=(0, 12), pady=1)
            x = tk.Label(box, text="✕", bg=P2, fg=C["muted"], cursor="hand2")
            x.grid(row=i, column=4, sticky="e")
            x.bind("<Button-1>", lambda e, n=r["name"]: (F.remove_stock(n), self.gp_fill()))
            Tooltip(x, "Remove")
        box.columnconfigure(4, weight=1)

    # ---------------- C: farm plan
    def _gp_farms(self, parent):
        """3.2.1 owner: no Goal - two lists, the strats out there and your own, and Done, next on the farm you're on."""
        P2 = C["panel2"]
        o, box = chrome_section(parent, "Farm plan", "The strats you mean to run, in order.", wrap=True)
        o.pack(fill="x", pady=(0, 12))
        self.gp_farm_box = tk.Frame(box, bg=P2)
        self.gp_farm_box.pack(fill="x")
        form = self._gp_add_area(box, "ADD A FARM")
        self.gp_f_pick, self.gp_f_mine = tk.StringVar(), tk.StringVar()
        self._gp_label(form, 0, "Strat")
        self.gp_f_box = ttk.Combobox(form, textvariable=self.gp_f_pick, state="readonly",
                                     postcommand=self.gp_farm_choices)
        self.gp_f_box.grid(row=0, column=1, sticky="ew", pady=2)
        self.gp_f_box.bind("<<ComboboxSelected>>", lambda e: self.gp_f_mine.set(""))
        Tooltip(self.gp_f_box, "The community's strats, then the official ones")
        self._gp_label(form, 1, "My own strat")
        self.gp_f_mine_box = ttk.Combobox(form, textvariable=self.gp_f_mine, state="readonly",
                                          postcommand=self.gp_farm_choices)
        self.gp_f_mine_box.grid(row=1, column=1, sticky="ew", pady=2)
        self.gp_f_mine_box.bind("<<ComboboxSelected>>", lambda e: self.gp_f_pick.set(""))
        self.gp_f_none = tk.Frame(form, bg=P2)              # none of your own: where to make one
        self.gp_f_none.grid(row=1, column=1, sticky="ew", pady=2)
        tk.Label(self.gp_f_none, text="You haven't made a strat yet.", bg=P2, fg=C["muted"],
                 font=("Segoe UI", 9)).pack(side="left")
        go = tk.Label(self.gp_f_none, text="Make one in Farming Strategies ›", bg=P2, fg=C["accent"],
                      font=("Segoe UI", 9, "underline"), cursor="hand2")
        go.pack(side="left", padx=(8, 0))
        go.bind("<Button-1>", lambda e: self.gp_farm_make())
        ttk.Button(form, text="+ Add farm", command=self.gp_add_farm).grid(row=2, column=1, sticky="e", pady=(8, 0))
        self.gp_farm_choices()

    ORIGIN_WORD = (("mine", "Mine"), ("board", "Community"), ("official", "Official"))

    def gp_farm_choices(self):
        """Every strat you can plan: yours, the community's (the board's posts) and the official ones - each as
        "name · where it's from", in that order. 3.2.0 (owner: the list showed nothing from the community)."""
        from . import moneymakers as MM
        strats, seen = [], set()
        board = list(getattr(self, "mm_board", None) or [])
        if not board and hasattr(self, "mm_board_fetch") and not getattr(self, "_gp_board_asked", False):
            self._gp_board_asked = True
            try:
                self.mm_board_fetch()                       # (the board's list, read once - no trade site)
            except Exception:
                buglog.caught()
        off = getattr(self, "mm_official", None) or {}
        extra = [dict(x, origin="official") for x in (off.get("strats") or []) if isinstance(x, dict)]
        for x in list(MM.all_strats()) + board + extra:
            if not isinstance(x, dict) or not x.get("id") or not x.get("name") or x["id"] in seen:
                continue
            seen.add(x["id"])
            o = x.get("origin")
            src = "mine" if o == "mine" else "board" if o == "board" else "official"
            strats.append((src, x))
        order = [k for k, _w in self.ORIGIN_WORD]
        strats.sort(key=lambda p: (order.index(p[0]), p[1]["name"].lower()))
        words = dict(self.ORIGIN_WORD)
        self.gp_f_strats = {f"{x['name']}  ·  {words[src]}": (x["id"], x["name"], words[src]) for src, x in strats}
        out = [k for k, v in self.gp_f_strats.items() if v[2] != words["mine"]]
        mine = [k for k, v in self.gp_f_strats.items() if v[2] == words["mine"]]
        self.gp_f_box.configure(values=out)
        self.gp_f_mine_box.configure(values=mine)
        if mine:
            self.gp_f_none.grid_remove()
            self.gp_f_mine_box.grid()
        else:
            self.gp_f_mine_box.grid_remove()
            self.gp_f_none.grid()
        return list(self.gp_f_strats)

    def gp_farm_make(self):
        """Make one in Farming Strategies ›: that page, at New strat."""
        try:
            self.shell.open("money")
            if hasattr(self, "mm_add"):
                self.mm_add()
        except Exception:
            buglog.caught()

    def gp_add_farm(self, name=None, until=None):
        """The strat picked in either list. name: a strat's "name · where" - older callers: its plain name."""
        strats = getattr(self, "gp_f_strats", None) or {}
        if not strats:
            self.gp_farm_choices()
            strats = self.gp_f_strats
        name = name or self.gp_f_pick.get() or self.gp_f_mine.get()
        hit = strats.get(name) or next((v for v in strats.values() if v[1] == name), None)
        if not hit:
            return None
        row = F.add_farm(hit[0], hit[1], src=hit[2], until=until)
        self.gp_f_pick.set("")
        self.gp_f_mine.set("")
        self.gp_fill()
        self.gp_overlay()
        return row

    def gp_farm_next(self):
        """Done, next ›: the farm you're on is moved on from."""
        F.farm_done()
        self.gp_fill()
        self.gp_overlay()

    def _gp_farm_rows(self):
        P2 = C["panel2"]
        box = self.gp_farm_box
        for w in box.winfo_children():
            w.destroy()
        farms = F.cfg()["farms"]
        if not farms:
            self._gp_empty(box, "No farms on your plan yet. Pick strats to run in order, from the community, the "
                                "official list or your own.")
            return
        now = F.farm_now()
        n = 0
        for i, r in enumerate(farms):
            row = tk.Frame(box, bg=P2)
            row.pack(fill="x", pady=(4, 0))
            if r is now:
                tk.Label(row, text=" NOW ", bg=C["good"], fg=C["bg"], font=("Segoe UI", 9, "bold")).pack(side="left")
            elif r.get("done"):
                tk.Label(row, text="✓", bg=P2, fg=C["good"], font=("Segoe UI", 10), width=3).pack(side="left")
            else:
                n += 1
                tk.Label(row, text=f"{n + 1 if now else n}.", bg=P2, fg=C["muted"], font=("Segoe UI", 10), width=3,
                         anchor="w").pack(side="left")
            tk.Label(row, text=r["name"], bg=P2, fg=C["muted"] if r.get("done") else C["text"], anchor="w",
                     font=("Segoe UI", 10, "bold" if r is now else "normal")).pack(side="left", padx=(8, 0))
            if r.get("src"):
                tk.Label(row, text=f"  {r['src']}", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
            if r is now:
                ttk.Button(row, text="Done, next ›", style="Quiet.TButton",
                           command=self.gp_farm_next).pack(side="right", padx=(8, 0))
            for txt, fn, tip in (("✕", lambda i=i: F.remove_farm(i), "Take it off the plan"),
                                 ("▼", lambda i=i: F.move_farm(i, 1), "Move down"),
                                 ("▲", lambda i=i: F.move_farm(i, -1), "Move up")):
                b = tk.Label(row, text=txt, bg=P2, fg=C["muted"], cursor="hand2", padx=4)
                b.pack(side="right")
                b.bind("<Button-1>", lambda e, fn=fn: (fn(), self.gp_fill(), self.gp_overlay()))
                Tooltip(b, tip)
            meta = tk.Frame(box, bg=P2)
            meta.pack(fill="x", padx=(24, 0), pady=(0, 2))
            if r.get("done"):
                tk.Label(meta, text="✓ Moved on", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
                continue
            t = F.farm_text(r)
            if t:
                tk.Label(meta, text=t, bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")

    # ---------------- K: reminder settings
    def _gp_pokes(self, parent):
        """3.2.0 (owner: too many settings): 13 down to 10. Always on, no switch: only in town or your hideout,
        only while you play, always says why, always gentle, quieter after 3 Not today."""
        P2 = C["panel2"]
        pk = F.cfg()["pokes"]
        o, box = chrome_section(parent, "Reminders", "Your plan reminds you only in town or your hideout, only while "
                                                     "you play, and always says why.", wrap=True)
        o.pack(fill="x", pady=(0, 12))
        self.gp_poke_vars = {}
        self._gp_head(box, "HOW OFTEN", top=0)
        for key, before, after, note, lo, hi in (
                ("per_hour", "At most", "reminders an hour", "0 turns them off", 0, 12),
                ("checkin_min", "A check-in every", "minutes of play", "", 0, 240),
                ("snooze_min", "Snooze lasts", "minutes", "the Snooze button on a reminder", 5, 480)):
            row = tk.Frame(box, bg=P2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=before, bg=P2, fg=C["text"]).pack(side="left")
            v = tk.StringVar(value=str(pk[key]))
            ttk.Spinbox(row, from_=lo, to=hi, textvariable=v, width=5).pack(side="left", padx=8)
            tk.Label(row, text=after, bg=P2, fg=C["text"]).pack(side="left")
            if note:
                tk.Label(row, text=" · " + note, bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
            v.trace_add("write", lambda *a: self.gp_pokes_save())
            self.gp_poke_vars[key] = v
        for head, keys in (("REMIND ME ABOUT", (("milestones", "Goals the game's log ticks off, like a level"),
                                                ("prices", "Stockpile items under your price"))),
                           ("HOW", (("alert", "An alert in-game"), ("sound", "A soft sound"),
                                    ("windows", "A Windows notification when the game isn't in front")))):
            self._gp_head(box, head)
            for key, lab in keys:
                v = tk.BooleanVar(value=bool(pk.get(key)))
                ttk.Checkbutton(box, text=lab, variable=v, style="Card.TCheckbutton",
                                command=self.gp_pokes_save).pack(anchor="w", pady=1)
                self.gp_poke_vars[key] = v
        self._gp_head(box, "QUIET HOURS")
        qr = tk.Frame(box, bg=P2)
        qr.pack(fill="x")
        v = tk.BooleanVar(value=bool(pk.get("quiet_on")))
        ttk.Checkbutton(qr, text="No reminders from", variable=v, style="Card.TCheckbutton",
                        command=self.gp_pokes_save).pack(side="left")
        self.gp_poke_vars["quiet_on"] = v
        a, b = (pk.get("quiet") or [23, 8])[:2]
        self.gp_quiet = (tk.StringVar(value=f"{int(a):02d}:00"), tk.StringVar(value=f"{int(b):02d}:00"))
        hours = [f"{h:02d}:00" for h in range(24)]
        ttk.Combobox(qr, textvariable=self.gp_quiet[0], values=hours, state="readonly", width=6).pack(
            side="left", padx=8)
        tk.Label(qr, text="to", bg=P2, fg=C["text"]).pack(side="left")
        ttk.Combobox(qr, textvariable=self.gp_quiet[1], values=hours, state="readonly", width=6).pack(
            side="left", padx=8)
        self.gp_quiet_to = qr.winfo_children()[-1]
        tk.Label(qr, text=" · at least an hour", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        self._gp_quiet_fit()
        for q in self.gp_quiet:
            q.trace_add("write", lambda *a: (self._gp_quiet_fit(), self.gp_pokes_save()))
        tr = tk.Frame(box, bg=P2)
        tr.pack(fill="x", pady=(12, 0))
        ttk.Button(tr, text="Test a reminder", command=self.focus_test).pack(side="right")
        ttk.Button(tr, text="History", command=self.focus_history, style="Quiet.TButton").pack(side="right", padx=8)

    def _gp_quiet_fit(self):
        """3.2.1 owner: quiet hours need a range - the end can't be the start; the same hour moves the end on one."""
        q = getattr(self, "gp_quiet", None)
        if not q:
            return
        try:
            a = int(q[0].get()[:2])
        except ValueError:
            return
        self.gp_quiet_to.configure(values=[f"{h:02d}:00" for h in range(24) if h != a])
        if q[1].get()[:2] == q[0].get()[:2]:
            q[1].set(f"{(a + 1) % 24:02d}:00")

    def focus_history(self):
        """The last pokes and what you answered."""
        import time as _t
        from tkinter import messagebox
        h = F.cfg()["history"][-15:]
        lines = [f"{_t.strftime('%b %d %H:%M', _t.localtime(x['ts']))}  {x['kind']}: {x['text'].splitlines()[0][:60]}"
                 f"  ->  {x.get('answer') or '-'}" for x in reversed(h)] or ["No reminders yet."]
        messagebox.showinfo("Reminder history", "\n".join(lines), parent=self.root)
        return lines

    def gp_pokes_save(self):
        pk = F.cfg()["pokes"]
        for k, v in self.gp_poke_vars.items():
            if isinstance(v, tk.BooleanVar):
                pk[k] = bool(v.get())
            else:
                n = _num(v.get())
                if n is not None:
                    pk[k] = int(n)
        q = getattr(self, "gp_quiet", None)
        if q:
            try:
                pk["quiet"] = [int(q[0].get()[:2]), int(q[1].get()[:2])]
            except ValueError:
                pass
        F.save()

    # ---------------- all of it
    def gp_fill(self):
        if not hasattr(self, "gp_goal_box"):
            return
        self._gp_goal_rows()
        self._gp_stock_rows()
        self._gp_farm_rows()
        f = F.cfg()
        if hasattr(self, "gp_phase"):
            self.gp_phase.pick(F.phase_name(f["phase"]), notify=False)
        self.gp_on.set(bool(f["on"]))
        if hasattr(self, "gp_summary"):
            self.gp_summary.config(text=self.gp_summary_text())


class FocusPokes:
    """2.73.1: League Focus's pokes over the game - mixed into App. The session tracker's tick hands it the log's
    events (focus_log) and asks every 10 s whether a poke is due (focus_tick); a poke is a small window at the top
    middle of the game, in the overlay's look (the app's theme), that says why it showed up. A click answers it."""

    def focus_log(self, kind, data):
        from . import focus as F
        ak = None
        if kind == "area":
            from .gamelog import area_kind
            ak = area_kind(data.get("area"), data.get("seed"), data.get("level", 0))
        try:
            F.log_event(kind, data, ak)
        except Exception:
            self.log_error("League Plan (log)")

    def focus_tick(self, now=None):
        """-> the poke shown, or None."""
        from . import focus as F
        import time as _t
        now = now or _t.time()
        last = getattr(self, "_focus_last", None)
        if last is not None and now - last < 10 and now >= last:
            return None
        s = self.tk_session
        running = s is not None and s.ended is None and s.paused_at is None
        played = (now - last) if (last is not None and running) else 0.0
        self._focus_last = now
        if getattr(self, "focus_win", None) is not None:
            return None                                    # one at a time
        where = (getattr(s, "where", None) or {}) if s is not None else {}
        in_town = where.get("kind") in ("town", "hideout") if where else True
        poke = F.due(now, in_town=in_town, session=s is not None and s.ended is None, played=played,
                     prices=self.gp_each, have=self.gp_have)
        if poke:
            self.focus_show(poke)
        return poke

    def focus_show(self, poke):
        from . import focus as F
        from .overlaywin import OverlayWindow, pal
        from .alerts_page import game_rect
        title, text, why, buttons = F.poke_text(poke)
        F.sent(poke)
        pk = F.cfg()["pokes"]
        if not pk.get("alert", True):                       # 3.2.0: An alert in-game off - the sound and the
            self._focus_ping(pk, title, text)              # Windows notification only
            return None
        P = pal()
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        W = 460
        geo = (r[0] + (r[2] - W) // 2, r[1] + int(r[3] * 0.08), W, None)
        w = OverlayWindow(self.root, title.title(), "🎯", geo, palette=P, lockable=False, follow_game=True,
                          no_activate=True, on_close=lambda: self.focus_answer(poke, "ok"))
        bg, fg = P["bg"], P["text"]
        body = tk.Frame(w.body, bg=bg, padx=16, pady=8)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=text, bg=bg, fg=fg, font=(P["font"], 11), justify="left", anchor="w",
                 wraplength=W - 40).pack(fill="x")
        if why:                                             # (3.2.0: always says why)
            tk.Label(body, text=why, bg=bg, fg=P["muted"], font=(P["font"], 9), justify="left", anchor="w",
                     wraplength=W - 40).pack(fill="x", pady=(8, 0))
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", pady=(8, 0))
        self.focus_btns = {}
        for i, (key, label) in enumerate(buttons):
            b = ttk.Button(row, text=label, style="Primary.TButton" if i == 0 else "TButton",
                           command=lambda k=key: self.focus_answer(poke, k))
            b.pack(side="left", padx=(0, 8))
            self.focus_btns[key] = b
        self.focus_win, self.focus_poke = w, poke
        w.show()
        self._focus_ping(pk, title, text)
        return w

    def _focus_ping(self, pk, title, text):
        """The soft sound and the Windows notification of a reminder, each when it's on."""
        if pk.get("sound"):
            try:
                self.root.bell()
            except tk.TclError:
                pass
        if pk.get("windows") and getattr(self, "tray", None) is not None:
            try:
                from .overlay import game_active
                if not game_active():
                    self.tray.notify(f"{title.title()}: {text.splitlines()[0]}")
            except Exception:
                buglog.caught()

    def focus_answer(self, poke, what):
        from . import focus as F
        w, self.focus_win = getattr(self, "focus_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass
        F.answer(poke, what)
        if what in ("plan", "sidetracked"):
            try:
                self.shell.open("plan")
                self.gp_fill()
            except Exception:
                buglog.caught()
        elif what == "exchange":
            import webbrowser
            from urllib.parse import quote
            from .config import SETTINGS
            webbrowser.open("https://www.pathofexile.com/trade2/exchange/poe2/" + quote(SETTINGS.get("league") or ""))
        elif what == "done":
            self.gp_fill()
            self.gp_overlay()
        return what

    def focus_test(self):
        """Reminders › Test a reminder: a nudge, or a check-in when the plan has no goal yet."""
        from . import focus as F
        g = F.current()
        poke = {"kind": "nudge", "goal": g["id"]} if g else {"kind": "checkin", "goal": None}
        if getattr(self, "focus_win", None) is not None:
            self.focus_answer(self.focus_poke, "ok")
        return self.focus_show(poke)
