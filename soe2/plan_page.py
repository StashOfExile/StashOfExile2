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
from .style import C, FONT_TITLE, ScrollArea, SegBar, Tooltip, autowrap


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
    VIEWS = ("Goals", "Reminders")

    def build_game_plan(self, body):
        P1, P2 = C["panel"], C["panel2"]
        f = F.cfg()
        page = tk.Frame(body, bg=P1)
        top = tk.Frame(page, bg=P1)
        top.pack(fill="x", padx=16, pady=(8, 8))
        self.gp_tabs = SegBar(top, list(self.VIEWS), command=self.gp_tab, size=10, pad=(16, 4), bg=P1)
        self.gp_tabs.pack(side="left")
        self.gp_on = tk.BooleanVar(value=bool(f["on"]))
        ttk.Checkbutton(top, text="Next up on the overlay, and reminders", variable=self.gp_on,
                        command=self.gp_switch).pack(side="right")
        sa = ScrollArea(page, bg=P1)
        sa.pack(fill="both", expand=True)
        hold = tk.Frame(sa.inner, bg=P1, padx=16)
        hold.pack(fill="both", expand=True)
        self.gp_tab_frames = {n: tk.Frame(hold, bg=P1) for n in self.VIEWS}
        goals = self.gp_tab_frames["Goals"]
        self.gp_list = tk.Frame(goals, bg=P1)               # the plan: Next up and your goals, or the first-open card
        self.gp_adder = tk.Frame(goals, bg=P1)              # Add a goal, in its place while it is open
        o, self.gp_next_box = chrome_section(self.gp_list, "Next up")
        self.gp_next_sec = o
        o2, box = chrome_section(self.gp_list, "Your plan")
        self.gp_plan_sec = o2
        head = tk.Frame(box, bg=P2)
        head.pack(fill="x", pady=(0, 4))
        self._gp_done_lbl = tk.Label(head, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9))
        self._gp_done_lbl.pack(side="left")
        ttk.Button(head, text="+ Add a goal", style="Primary.TButton", command=self.gp_add_open).pack(side="right")
        self.gp_goal_box = tk.Frame(box, bg=P2)
        self.gp_goal_box.pack(fill="x")
        o3, self.gp_start_box = chrome_section(self.gp_list, "No plan yet")
        self.gp_start_sec = o3
        self._gp_start(self.gp_start_box)
        self._gp_adder(self.gp_adder)
        self.gp_list.pack(fill="x")
        self._gp_pokes(self.gp_tab_frames["Reminders"])
        self.gp_tab(self.VIEWS[0])
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

    def gp_open(self, page, tab=None):
        """A goal's link to the tool its count comes from."""
        try:
            if tab:
                self.shell.open_tab(page, tab)
            else:
                self.shell.open(page)
        except Exception:
            buglog.caught()

    def _gp_link(self, parent, g):
        """ "Wealth ›" after a goal's count - one click to where the number is from."""
        src = F.SOURCE.get(F.goal_target(g)[0] or "")
        if not src:
            return None
        lk = tk.Label(parent, text=src[0] + " ›", bg=parent["bg"], fg=C["accent"], font=("Segoe UI", 9, "underline"),
                      cursor="hand2")
        lk.bind("<Button-1>", lambda e, p=src[1], k=F.goal_target(g)[0]: self.gp_open(p, "Stockpile" if k == "stock"
                                                                                      else None))
        Tooltip(lk, f"Open {src[0]}")
        return lk

    # ---------------- first open: no plan yet
    def _gp_start(self, box):
        P2 = C["panel2"]
        tk.Label(box, text="The league start plan has these goals. Change or remove any after.", bg=P2, fg=C["muted"],
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        for i, t in enumerate(F.start_plan_words(), 1):
            tk.Label(box, text=f"{i}.  {t}", bg=P2, fg=C["text"], font=("Segoe UI", 10), anchor="w").pack(
                fill="x", pady=(4, 0))
        row = tk.Frame(box, bg=P2)
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Use the league start plan", style="Primary.TButton",
                   command=self.gp_use_start).pack(side="left")
        own = tk.Label(row, text="Or add your own goal", bg=P2, fg=C["accent"], font=("Segoe UI", 9, "underline"),
                       cursor="hand2")
        own.pack(side="left", padx=(16, 0))
        own.bind("<Button-1>", lambda e: self.gp_add_open())

    def gp_use_start(self):
        F.use_start_plan()
        F.check_goals()
        self.gp_fill()
        self.gp_overlay()

    # ---------------- Next up
    def _gp_next(self):
        P2 = C["panel2"]
        box = self.gp_next_box
        for w in box.winfo_children():
            w.destroy()
        g = F.current()
        done, n = F.counts()
        if g is None:
            tk.Label(box, text=f"✓ All {n} goals done." if n else "", bg=P2, fg=C["good"],
                     font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
            return
        gs = F.cfg()["goals"]
        tk.Label(box, text=f"{gs.index(g) + 1} of {n}", bg=P2, fg=C["muted"], font=("Segoe UI", 9),
                 anchor="w").pack(fill="x")
        tk.Label(box, text=g["text"], bg=P2, fg=C["text"], font=(FONT_TITLE, 16), anchor="w", justify="left").pack(
            fill="x", pady=(2, 4))
        autowrap(box.pack_slaves()[-1])
        meta = tk.Frame(box, bg=P2)
        meta.pack(fill="x")
        fr = F.frac(g)
        if fr is not None:
            self._gp_bar(meta, fr, w=120).pack(side="left", padx=(0, 8))
        pt = F.progress_text(g)
        tk.Label(meta, text=pt or "You tick this one", bg=P2, fg=C["text"] if pt else C["muted"],
                 font=("Segoe UI", 10)).pack(side="left")
        src = F.source_text(g)
        if src:
            tk.Label(meta, text=" · " + src, bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        lk = self._gp_link(meta, g)
        if lk is not None:
            lk.pack(side="left", padx=(8, 0))
        row = tk.Frame(box, bg=P2)
        row.pack(fill="x", pady=(8, 0))
        if not F.goal_target(g)[0] or F.goal_target(g) == ("farm", 0.0):
            ttk.Button(row, text="✓ Done", command=lambda gid=g["id"]: self.gp_goal_done(gid, True)).pack(
                side="left", padx=(0, 8))
        more = sum(1 for x in gs if not x["done"]) > 1
        sk = ttk.Button(row, text="Skip for now", style="Quiet.TButton", command=lambda gid=g["id"]: self.gp_skip(gid))
        sk.pack(side="left")
        if not more:
            sk.state(["disabled"])
        Tooltip(sk, "The goal after it is Next up until tomorrow" if more else "This is your only open goal")

    def gp_skip(self, gid):
        F.skip(gid)
        self.gp_fill()
        self.gp_overlay()

    # ---------------- your plan
    def _gp_goal_rows(self):
        P2 = C["panel2"]
        box = self.gp_goal_box
        for w in box.winfo_children():
            w.destroy()
        gs = F.cfg()["goals"]
        cur = F.current()
        done, n = F.counts()
        self._gp_done_lbl.config(text=f"{done} of {n} done")
        for i, g in enumerate(gs):
            r = tk.Frame(box, bg=P2)
            r.pack(fill="x", pady=(8, 0))
            tk.Label(r, text="✓" if g["done"] else str(i + 1), bg=P2, fg=C["good"] if g["done"] else C["muted"],
                     font=("Segoe UI", 10, "bold"), width=3).pack(side="left")
            tk.Label(r, text=g["text"], bg=P2, fg=C["muted"] if g["done"] else C["text"],
                     font=("Segoe UI", 10, "bold" if g is cur else "normal")).pack(side="left")
            if g is cur:
                tk.Label(r, text=" NEXT UP ", bg=C["accent"], fg=C["bg"], font=("Segoe UI", 9, "bold")).pack(
                    side="left", padx=(8, 0))
            for txt, fn, tip, off in (
                    ("✕", lambda gid=g["id"]: F.remove_goal(gid), "Remove this goal", False),
                    ("▼", lambda gid=g["id"]: F.move_goal(gid, 1), "Move down", i == len(gs) - 1),
                    ("▲", lambda gid=g["id"]: F.move_goal(gid, -1), "Move up", i == 0)):
                b = tk.Label(r, text=txt, bg=P2, fg=C["line"] if off else C["muted"], cursor="arrow" if off else "hand2",
                             padx=4)
                b.pack(side="right")
                if not off:
                    b.bind("<Button-1>", lambda e, fn=fn: (fn(), self.gp_fill(), self.gp_overlay()))
                Tooltip(b, "Already first" if off and txt == "▲" else "Already last" if off else tip)
            kind = F.goal_target(g)[0]
            if not kind or g["done"] or F.goal_target(g) == ("farm", 0.0):
                tick = tk.Label(r, bg=P2, cursor="hand2", font=("Segoe UI", 9), padx=8)
                tick.pack(side="right")
                self._gp_tick_paint(tick, g["done"])
                tick.bind("<Button-1>", lambda e, gid=g["id"], d=g["done"]: self.gp_goal_done(gid, not d))
                Tooltip(tick, "Not done after all" if g["done"] else "Tick it when the goal is done")
            meta = tk.Frame(box, bg=P2)
            meta.pack(fill="x", padx=(24, 0))
            if g["done"]:
                why = "you ticked it" if not g.get("auto_done") else (F.source_text(g).split(" · ")[0] or "counted")
                tk.Label(meta, text="✓ Done · " + why, bg=P2, fg=C["good"], font=("Segoe UI", 9)).pack(side="left")
                continue
            pt = F.progress_text(g)
            if kind:
                fr = F.frac(g)
                if fr is not None:
                    self._gp_bar(meta, fr).pack(side="left", padx=(0, 8))
                bits = " · ".join(x for x in (pt, F.source_text(g)) if x)
                tk.Label(meta, text=bits, bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
                lk = self._gp_link(meta, g)
                if lk is not None:
                    lk.pack(side="left", padx=(8, 0))
            else:
                tk.Label(meta, text="You tick this one", bg=P2, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")

    @staticmethod
    def _gp_tick_paint(lbl, done):
        lbl.config(text="☑ Done" if done else "☐ Done", fg=C["good"] if done else C["muted"])

    def gp_goal_done(self, gid, done):
        F.set_done(gid, done)
        self.gp_fill()
        self.gp_overlay()

    # ---------------- Add a goal
    MAP_MODES = (("reach_maps", "Reach maps"), ("tier", "Reach a tier"), ("maps", "Run a number of maps"))
    WHOLE = "The whole campaign"

    def _gp_adder(self, parent):
        P2 = C["panel2"]
        o, box = chrome_section(parent, "Add a goal")
        o.pack(fill="x")
        cols = tk.Frame(box, bg=P2)
        cols.pack(fill="x")
        cols.columnconfigure(1, weight=1)
        left = tk.Frame(cols, bg=P2)
        left.grid(row=0, column=0, sticky="nw", padx=(0, 24))
        self.gp_kind = tk.StringVar(value=F.GOAL_KINDS[0][0])
        self.gp_kind_rows = {}
        for key, name, where in F.GOAL_KINDS:
            r = tk.Frame(left, bg=P2, cursor="hand2", padx=8, pady=4, highlightthickness=1,
                         highlightbackground=P2)
            r.pack(fill="x", pady=1)
            a = tk.Label(r, text=name, bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold"), anchor="w")
            a.pack(fill="x")
            b = tk.Label(r, text=where, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w")
            b.pack(fill="x")
            for w in (r, a, b):
                w.bind("<Button-1>", lambda e, k=key: self.gp_kind_pick(k))
            self.gp_kind_rows[key] = (r, a)
        right = tk.Frame(cols, bg=P2)
        right.grid(row=0, column=1, sticky="new")
        self.gp_form = tk.Frame(right, bg=P2)
        self.gp_form.pack(fill="x")
        self.gp_form.columnconfigure(1, weight=1)
        self.gp_new, self.gp_num, self.gp_pick, self.gp_mode = (tk.StringVar(), tk.StringVar(), tk.StringVar(),
                                                              tk.StringVar())
        for v in (self.gp_new, self.gp_num, self.gp_pick, self.gp_mode):
            v.trace_add("write", lambda *a: self.gp_add_paint())
        self.gp_note = tk.Label(right, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left")
        self.gp_note.pack(fill="x", pady=(8, 0))
        autowrap(self.gp_note)
        self._gp_head(right, "IT READS", top=16)
        self.gp_reads = tk.Label(right, text="", bg=P2, fg=C["text"], font=(FONT_TITLE, 16), anchor="w",
                                 justify="left")
        self.gp_reads.pack(fill="x")
        autowrap(self.gp_reads)
        row = tk.Frame(box, bg=P2)
        row.pack(fill="x", pady=(16, 0))
        self.gp_add_btn = ttk.Button(row, text="Add", style="Primary.TButton", command=self.gp_add_goal)
        self.gp_add_btn.pack(side="right")
        ttk.Button(row, text="Cancel", style="Quiet.TButton", command=self.gp_add_close).pack(side="right", padx=8)
        self.gp_add_tip = Tooltip(self.gp_add_btn, "")
        self.gp_kind_pick(self.gp_kind.get())

    def gp_add_open(self):
        self.gp_tab("Goals")
        self.gp_list.pack_forget()
        self.gp_adder.pack(fill="x")
        self.gp_kind_pick(self.gp_kind.get())

    def gp_add_close(self):
        self.gp_adder.pack_forget()
        self.gp_list.pack(fill="x")

    def _gp_digits_ok(self, text):
        """The number box takes digits only, up to the top of the picked kind's range."""
        if text == "":
            return True
        if not text.isdigit():
            return False
        rng = F.TARGET_RANGE.get(self.gp_add_spec()[0] or "")
        return rng is None or int(text) <= rng[1]

    def _gp_field(self, row, label, widget):
        self._gp_label(self.gp_form, row, label)
        widget.grid(row=row, column=1, sticky="w", pady=2)
        return widget

    def _gp_numbox(self):
        ok = (self.root.register(self._gp_digits_ok), "%P")
        e = ttk.Entry(self.gp_form, textvariable=self.gp_num, width=8, validate="key", validatecommand=ok)
        e.bind("<Return>", lambda ev: self.gp_add_goal())
        return e

    def gp_boss_names(self):
        """{what the list shows: arena}"""
        out = {}
        for arena in F.bosses():
            who = F.BOSS_OF.get(arena)
            out[f"{who[0].upper() + who[1:]} · {arena}" if who else arena] = arena
        return out

    def gp_strat_names(self):
        """{ "name · where it's from": (id, name) } - yours, the community's, the official ones."""
        from . import moneymakers as MM
        board = list(getattr(self, "mm_board", None) or [])
        if not board and hasattr(self, "mm_board_fetch") and not getattr(self, "_gp_board_asked", False):
            self._gp_board_asked = True
            try:
                self.mm_board_fetch()
            except Exception:
                buglog.caught()
        off = getattr(self, "mm_official", None) or {}
        extra = [dict(x, origin="official") for x in (off.get("strats") or []) if isinstance(x, dict)]
        words = {"mine": "Mine", "board": "Community"}
        rows, seen = [], set()
        for x in list(MM.all_strats()) + board + extra:
            if not isinstance(x, dict) or not x.get("id") or not x.get("name") or x["id"] in seen:
                continue
            seen.add(x["id"])
            w = words.get(x.get("origin"), "Official")
            rows.append((list(words.values()).index(w) if w in words.values() else 2, x["name"].lower(),
                         f"{x['name']}  ·  {w}", (x["id"], x["name"])))
        return {lab: hit for _o, _n, lab, hit in sorted(rows)}

    def gp_kind_pick(self, key):
        """A kind picked on the left: its fields on the right."""
        P2 = C["panel2"]
        self.gp_kind.set(key)
        for k, (r, a) in self.gp_kind_rows.items():
            on = k == key
            r.config(highlightbackground=C["accent"] if on else P2)
            a.config(text=("✓ " if on else "") + dict((kk, n) for kk, n, _w in F.GOAL_KINDS)[k])
        for w in self.gp_form.winfo_children():
            w.destroy()
        for v in (self.gp_new, self.gp_num, self.gp_pick, self.gp_mode):
            v.set("")
        note = ""
        if key == "level":
            self._gp_field(0, "Level", self._gp_numbox())
            note = "1 to 100. It ticks itself."
        elif key == "act":
            from . import campaign as CP
            n = sum(1 for a in CP.acts() if str(a.get("key") or "").isdigit()) or 4
            self._gp_field(0, "Done when", ttk.Combobox(self.gp_form, textvariable=self.gp_pick, state="readonly",
                                                        width=24, values=[self.WHOLE] + [f"Act {i}" for i in
                                                                                         range(1, n + 1)]))
            self.gp_pick.set(self.WHOLE)
            note = "An act is done when the log shows you in the one after it."
        elif key == "maps":
            self._gp_field(0, "Done when", ttk.Combobox(self.gp_form, textvariable=self.gp_mode, state="readonly",
                                                        width=24, values=[n for _k, n in self.MAP_MODES]))
            self._gp_field(1, "Number", self._gp_numbox())
            self.gp_mode.set(self.MAP_MODES[0][1])
            note = "Maps run are counted from the day you add the goal. A tier is the highest the log has shown."
        elif key == "boss":
            self.gp_bosses = self.gp_boss_names()
            self._gp_field(0, "Boss", ttk.Combobox(self.gp_form, textvariable=self.gp_pick, state="readonly", width=38,
                                                   values=list(self.gp_bosses)))
            self._gp_field(1, "Kills", self._gp_numbox())
            self.gp_num.set("1")
            note = ("The list is the bosses Leaderboards knows. The log shows a run of the arena, not the kill: "
                    "untick the goal if the boss won.")
        elif key == "networth":
            self._gp_field(0, "Divine", self._gp_numbox())
            note = "Read from Wealth each time you count or scan there."
        elif key == "divhour":
            self._gp_field(0, "Div an hour", self._gp_numbox())
            note = f"Worked out over your last {F.DIVHOUR_MAPS} maps in Map Profit."
        elif key == "farm":
            self.gp_strats = self.gp_strat_names()
            self._gp_field(0, "Strat", ttk.Combobox(self.gp_form, textvariable=self.gp_pick, state="readonly", width=38,
                                                    values=list(self.gp_strats)))
            self._gp_field(1, "Hours", self._gp_numbox())
            note = ("Hours of play while it is Next up. Leave Hours empty to tick it yourself."
                    if self.gp_strats else "No strats yet. Make one in Farming Strategies.")
        elif key == "stock":
            b, n = F.stock_counts()
            note = (f"Your Stockpile has {n} items with a quantity, {b} bought. It ticks itself when all are bought."
                    if n else "Your Stockpile is empty. Add items on Exchange Rates, under Stockpile.")
        else:
            e = ttk.Entry(self.gp_form, textvariable=self.gp_new, width=44)
            self._gp_field(0, "Goal", e)
            e.bind("<Return>", lambda ev: self.gp_add_goal())
            note = "For anything the app can't see, like a craft."
        self.gp_note.config(text=note)
        self.gp_add_paint()

    def gp_add_spec(self):
        """What the form holds -> (kind, target, ref, ref_name, text, what's missing)."""
        key = self.gp_kind.get()
        n = _num(self.gp_num.get()) if self.gp_num.get().strip() else None
        if key == "level":
            return "level", n, None, None, "", "" if n else "Type a level first."
        if key == "act":
            p = self.gp_pick.get()
            if p == self.WHOLE or not p:
                return "campaign", 1, None, None, "", ""
            return "act_done", _num(p.split()[-1]), None, None, "", ""
        if key == "maps":
            k = next((k for k, lab in self.MAP_MODES if lab == self.gp_mode.get()), "reach_maps")
            if k == "reach_maps":
                return k, 1, None, None, "", ""
            return k, n, None, None, "", "" if n else "Type a number first."
        if key == "boss":
            arena = (getattr(self, "gp_bosses", None) or {}).get(self.gp_pick.get())
            return "boss", n or 1, None, arena, "", "" if arena else "Pick a boss first."
        if key in ("networth", "divhour"):
            return key, n, None, None, "", "" if n else "Type a number first."
        if key == "farm":
            hit = (getattr(self, "gp_strats", None) or {}).get(self.gp_pick.get())
            return "farm", n, hit and hit[0], hit and hit[1], "", "" if hit else "Pick a strat first."
        if key == "stock":
            have = any(g.get("target_kind") == "stock" for g in F.cfg()["goals"])
            return "stock", 1, None, None, "", "Stock up is already on your plan." if have else ""
        t = self.gp_new.get().strip()
        return None, None, None, None, t, "" if t else "Type the goal first."

    def gp_add_paint(self):
        """IT READS, and Add grayed out until the goal is whole."""
        if not hasattr(self, "gp_add_btn"):
            return
        kind, target, _ref, name, text, missing = self.gp_add_spec()
        words = (F.goal_words(kind, target, name) if kind and not missing else text) or "…"
        self.gp_reads.config(text=words)
        self.gp_add_btn.state(["disabled"] if missing else ["!disabled"])
        self.gp_add_tip.text = missing

    def gp_add_goal(self):
        kind, target, ref, name, text, missing = self.gp_add_spec()
        if missing:
            return None
        g = F.add_goal(text, kind, target, ref=ref, ref_name=name)
        F.check_goals()
        self.gp_add_close()
        self.gp_fill()
        self.gp_overlay()
        return g

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

    # ---------------- the Stockpile: on Exchange Rates since 3.3.0
    def _gp_stock(self, parent):
        P2 = C["panel2"]
        o, box = chrome_section(parent, "Stockpile", "What to buy and sit on. Have is what you type, "
                                                                       "and Enter keeps it. Now is poe.ninja's price for your "
                                                                       "league.", wrap=True)
        o.pack(fill="x", pady=(0, 12))
        self.gp_stock_plan = tk.Label(box, text="", bg=P2, fg=C["accent"], font=("Segoe UI", 9, "underline"),
                                      cursor="hand2", anchor="w")
        self.gp_stock_plan.bind("<Button-1>", lambda e: self.gp_open("plan"))
        Tooltip(self.gp_stock_plan, "Open League Plan")
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
        g = next((x for x in F.cfg()["goals"] if x.get("target_kind") == "stock"), None)
        lbl = getattr(self, "gp_stock_plan", None)
        if lbl is not None:                                 # the way back: this list is a goal on your plan
            lbl.pack_forget()
            if g is not None:
                lbl.config(text=f"On your plan · {g['text']}, {F.progress_text(g)} ›")
                lbl.pack(fill="x", pady=(0, 8), before=box)
        if not rows:
            self._gp_empty(box, "Nothing yet. Add what's cheap at league start and worth more later.")
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
            now = (f"{F.num(each)} div" if each is not None else "no price") + \
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
        """The plan, drawn from what is saved. The Stockpile on Exchange Rates follows too, when it is built."""
        if getattr(self, "gp_stock_box", None) is not None and self.gp_stock_box.winfo_exists():
            self._gp_stock_rows()
        if not hasattr(self, "gp_goal_box"):
            return
        F.check_goals()
        has = bool(F.cfg()["goals"])
        cur = F.current()
        sig = (bool(F.cfg()["on"]), cur and cur["id"],
               tuple((g["id"], g["text"], g["done"], F.progress_text(g), F.source_text(g)) for g in F.cfg()["goals"]))
        if sig == getattr(self, "_gp_sig", None) and self.gp_goal_box.winfo_exists():
            return                                          # no flicker: the same plan is not drawn again
        self._gp_sig = sig
        for sec, show in ((self.gp_start_sec, not has), (self.gp_next_sec, has), (self.gp_plan_sec, has)):
            sec.pack_forget()
        for sec, show in ((self.gp_start_sec, not has), (self.gp_next_sec, has), (self.gp_plan_sec, has)):
            if show:
                sec.pack(fill="x", pady=(0, 12))
        if has:
            self._gp_next()
            self._gp_goal_rows()
        self.gp_on.set(bool(F.cfg()["on"]))


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
