"""3.3.0 owner: Dashboard ↳ Calendar. A month of leagues, Twitch Drops, events and races from the community board,
plus reminders of your own. Left: the month, or the same events as a list. Right: the day you clicked.

Row 1: search first, then Month | List, the month's arrows, Today, a tick box for each kind, and the page's one
orange button, Add Reminder. Every kind is told by its mark and its word, never by color alone.
GGG policy: nothing is read from the game and no keys are sent. A reminder is an alert card, like the helpers."""
import datetime as _dt
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

from . import buglog
from . import calendar_data as CD
from .config import SETTINGS, save_json
from .style import C, over_app

KEY = "calendar"
TICK_MS = 20000
SMALLEST = 140                     # a grid narrower or shorter than this has not been laid out yet
PULL_SECS = 1800                   # the board's events are asked for when the app starts and every 30 minutes
DEFAULT_LEADS = (86400, 0)
VIEWS = ("Month", "List")


def kind_color(kind):
    return C.get(CD.KINDS.get(kind, CD.KINDS["event"])[2], C["text"])


class CalendarPage:
    # ---------------------------------------------------------------- the page
    def build_calendar(self, body):
        from .chrome import EmptyState, PanelHead
        from .style import SegBar, Tooltip
        from . import cleanguard
        P1, P2 = C["panel"], C["panel2"]
        today = _dt.date.today()
        self.cal_ym, self.cal_day, self.cal_pick = (today.year, today.month), today, None
        self.cal_day2 = None                                # the other end of a Shift-clicked range of days
        self.cal_cells = []
        bar = tk.Frame(body, bg=P1, padx=8)
        bar.pack(fill="x", pady=(8, 8))
        tk.Label(bar, text="🔍", bg=P1, fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(0, 4))
        self.cal_q = tk.StringVar()
        self.cal_q.trace_add("write", lambda *_a: self.root.after_idle(self.cal_refresh))
        q = ttk.Entry(bar, textvariable=self.cal_q, width=22)
        q.pack(side="left")
        cleanguard.free(q)                                  # a search
        Tooltip(q, "Search event names and kinds")
        self.cal_view = SegBar(bar, list(VIEWS), value=SETTINGS.get("cal_view") if SETTINGS.get("cal_view") in VIEWS
                               else "Month", command=lambda v: self.cal_view_changed(), size=10, pad=(12, 4))
        self.cal_view.pack(side="left", padx=(12, 12))
        b = ttk.Button(bar, text="‹", width=3, command=lambda: self.cal_step(-1))
        b.pack(side="left")
        Tooltip(b, "The month before")
        self.cal_month_lbl = tk.Label(bar, text="", bg=P1, fg=C["text"], font=("Segoe UI", 10, "bold"), width=16)
        self.cal_month_lbl.pack(side="left")
        b = ttk.Button(bar, text="›", width=3, command=lambda: self.cal_step(1))
        b.pack(side="left")
        Tooltip(b, "The month after")
        b = ttk.Button(bar, text="Today", width=0, command=self.cal_today)
        b.pack(side="left", padx=(8, 12))
        Tooltip(b, "Back to this month, with today picked")
        off = set(SETTINGS.get("cal_hide") or ())
        self.cal_kind_vars, self.cal_kind_lbls = {}, {}
        for kind in CD.ORDER:                               # a tick and the kind's mark and word; a dash when hidden
            self.cal_kind_vars[kind] = tk.BooleanVar(value=kind not in off)
            lab = self.cal_kind_lbls[kind] = tk.Label(bar, bg=P1, font=("Segoe UI", 9, "bold"), cursor="hand2", padx=4)
            lab.pack(side="left", padx=(0, 4))
            lab.bind("<Button-1>", lambda _e, k=kind: self.cal_kind_flip(k))
            Tooltip(lab, f"Click to show or hide {CD.FILTER_WORDS[kind]}")
        self.cal_kind_paint()
        self.cal_ov_var = tk.BooleanVar(value=bool(SETTINGS.get("cal_overlay")))
        sw = ttk.Checkbutton(bar, text="Next event on the overlay", variable=self.cal_ov_var, style="Bar.TCheckbutton",
                             command=self.cal_overlay_switch)
        sw.pack(side="left", padx=(8, 0))
        Tooltip(sw, "One line on the overlay for the next event: from a week before it starts until it is over.")
        add = ttk.Button(bar, text="Add Reminder", style="Primary.TButton", width=0, command=self.cal_add)
        add.pack(side="right")
        Tooltip(add, "A reminder of your own on the picked day. It stays on this PC.")
        self.undo_button(bar, KEY, side="right", padx=(0, 8))
        self.cal_post_btn = ttk.Button(bar, text="Post Event", width=0, command=self.cal_post)
        Tooltip(self.cal_post_btn, "Admin: posts an event to the board. Every user's Calendar shows it.")
        self.cal_drafts_btn = ttk.Button(bar, text=self.cal_drafts_words(), width=0, command=self.cal_drafts)
        Tooltip(self.cal_drafts_btn, "Admin: events the board drafted from Steam news. None reaches a user until "
                                     "you post it.")
        if self.cal_is_admin():
            self.cal_post_btn.pack(side="right", padx=(0, 8))
            self.cal_drafts_btn.pack(side="right", padx=(0, 8))
        try:
            from .style import flowify
            flowify(bar)                                    # too narrow: the row wraps, nothing is cut off
        except Exception:
            buglog.caught()
        wrap = tk.Frame(body, bg=P2)
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=3, uniform="cal")
        wrap.columnconfigure(1, weight=1, uniform="cal")
        wrap.rowconfigure(0, weight=1)
        # ---- the month, or the list
        lf = tk.Frame(wrap, bg=P1)
        lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.cal_head = PanelHead(lf, "Calendar")
        self.cal_head.pack(fill="x")
        self.cal_grid = tk.Canvas(lf, bg=P1, highlightthickness=0, bd=0)
        self.cal_grid.bind("<Configure>", lambda e: self.cal_draw())
        self.cal_grid.bind("<Map>", lambda e: self.cal_draw_soon())
        self.cal_grid.bind("<Button-1>", self.cal_grid_click)
        self.cal_grid.bind("<Double-Button-1>", lambda e: (self.cal_grid_click(e), self.cal_add()))
        self.cal_grid.bind("<Button-3>", self.cal_grid_menu)
        lst = self.cal_list_frame = tk.Frame(lf, bg=P1)
        tv = ttk.Treeview(lst, columns=("kind", "starts", "away", "remind"), show="tree headings", selectmode="browse")
        for cid, text, weight in (("#0", "Name", 5), ("kind", "Kind", 3), ("starts", "Starts", 4), ("away", "When", 3),
                                  ("remind", "Reminder", 4)):
            tv.heading(cid, text=text)
            tv.column(cid, width=weight * 40, minwidth=60, stretch=True, anchor="w")
        sb = ttk.Scrollbar(lst, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        self.cal_tv = tv
        self.list_register(KEY, tv, delete=lambda _rows=None: self.cal_delete(), multi=False)
        tv.menu_actions = self.cal_menu_actions
        tv.bind("<<TreeviewSelect>>", lambda e: self.cal_list_picked())
        # ---- the picked day
        rf = tk.Frame(wrap, bg=P1)
        rf.grid(row=0, column=1, sticky="nsew")
        self.cal_day_head = PanelHead(rf, "Day")
        self.cal_day_head.pack(fill="x")
        self.cal_day_box = tk.Frame(rf, bg=P1, padx=12, pady=8)
        self.cal_day_box.pack(fill="both", expand=True)
        self.cal_empty = EmptyState(rf, "", "Nothing on this day\nAdd Reminder puts one of your own here.",
                                    button=("Add Reminder", self.cal_add))
        self.cal_view_changed(save=False)
        self.cal_pulled_at = 0.0
        self.root.after(TICK_MS, self.cal_tick)
        self.root.after(8000, self.cal_pull)

    def cal_is_admin(self):
        try:
            return bool(self.share_is_admin())
        except Exception:
            return False

    def cal_drafts_count(self):
        """How many drafts wait for an admin; 0 for everyone else."""
        return int(getattr(self, "cal_drafts_n", 0) or 0) if self.cal_is_admin() else 0

    def cal_drafts_words(self):
        """What the Drafts button says: the number is in the words, with a mark, never a color alone."""
        n = self.cal_drafts_count()
        return f"● Drafts: {n} to review" if n else "Drafts"

    def cal_drafts_set(self, n):
        self.cal_drafts_n = max(0, int(n or 0))
        btn = getattr(self, "cal_drafts_btn", None)
        try:
            if btn is not None and btn.winfo_exists():
                btn.config(text=self.cal_drafts_words())
        except tk.TclError:
            pass
        dash = getattr(getattr(self, "shell", None), "modules", {}).get("dashboard")
        page = getattr(dash, "page", None)
        if page is not None:
            page.later()

    def cal_drafts_pull(self):
        """Admins only: ask the board how many drafts wait. Everyone else never asks."""
        if not self.cal_is_admin():
            return
        from . import board as B

        def done(res):
            ok, data = res if isinstance(res, tuple) and len(res) == 2 else (False, None)
            if ok and isinstance(data, dict):
                self.cal_drafts_set(len(CD.clean_board_rows(data.get("events"))))
        try:
            self.run_bg(B.event_drafts, done)
        except Exception:
            buglog.caught()

    def cal_pull(self, then=None):
        """The board's events, asked for off the window's thread and put in place on it."""
        self.cal_pulled_at = time.time()
        self.cal_drafts_pull()

        def done(rows):
            if rows is not None:
                CD.set_board(rows)
                self.cal_changed()
            if then:
                then(rows)
        try:
            self.run_bg(CD.pull, done)
        except Exception:
            buglog.caught()

    def cal_kinds(self):
        return {k for k, v in self.cal_kind_vars.items() if v.get()}

    def cal_events(self):
        return CD.shown(CD.events(), self.cal_q.get(), self.cal_kinds())

    def cal_kind_flip(self, kind):
        v = self.cal_kind_vars[kind]
        v.set(not v.get())
        self.cal_kinds_changed()

    def cal_kind_paint(self):
        for kind, lab in self.cal_kind_lbls.items():
            on = self.cal_kind_vars[kind].get()
            lab.config(text=f"{'✓' if on else '–'} {CD.mark(kind)} {CD.FILTER_WORDS[kind]}",
                       fg=kind_color(kind) if on else C["muted"])

    def cal_kinds_changed(self):
        self.cal_kind_paint()
        SETTINGS["cal_hide"] = sorted(k for k, v in self.cal_kind_vars.items() if not v.get())
        save_json("settings.json", SETTINGS)
        self.cal_refresh()

    def cal_view_changed(self, save=True):
        month = self.cal_view.get() == "Month"
        if save:
            SETTINGS["cal_view"] = self.cal_view.get()
            save_json("settings.json", SETTINGS)
        self.cal_list_frame.pack_forget()
        self.cal_grid.pack_forget()
        (self.cal_grid if month else self.cal_list_frame).pack(fill="both", expand=True)
        self.cal_refresh()

    def cal_step(self, by):
        self.cal_ym = CD.step_month(*self.cal_ym, by)
        self.cal_refresh()

    def cal_today(self):
        today = _dt.date.today()
        self.cal_ym, self.cal_day, self.cal_pick = (today.year, today.month), today, None
        self.cal_day2 = None
        self.cal_refresh()

    # ---------------------------------------------------------------- drawing
    def cal_refresh(self):
        if getattr(self, "cal_grid", None) is None:
            return
        try:
            evs = self.cal_events()
            y, m = self.cal_ym
            self.cal_month_lbl.config(text=CD.month_name(y, m))
            in_month = [e for e in evs if any(d.month == m and d.year == y for d in CD.span(e))
                        or CD.span(e)[0] < _dt.date(y, m, 1) <= CD.span(e)[1]]
            board = sum(1 for e in in_month if not CD.is_mine(e))
            if self.cal_view.get() == "Month":
                self.cal_head.set_title(CD.month_name(y, m))
                self.cal_head.note(f"{board} from the board · {len(in_month) - board} mine")
            else:
                self.cal_head.set_title("Every Event")
                self.cal_head.note(f"{len(evs)} shown")
            self.cal_draw(evs)
            self.cal_fill_list(evs)
            self.cal_show_day(evs)
        except Exception:
            buglog.caught()

    def cal_draw_soon(self, tries=0):
        """Draw once the grid has its real size."""
        try:
            self.root.after(60, lambda: self.cal_draw(tries=tries))
        except tk.TclError:
            pass

    def cal_draw(self, evs=None, tries=0):
        """3.3.0 owner: the month came up as one tiny square on the first open. A page that was never shown has
        no size yet, so the grid waits for its real size and draws then."""
        cv = self.cal_grid
        try:
            if not cv.winfo_exists():
                return
        except tk.TclError:
            return
        if cv.winfo_width() < SMALLEST or cv.winfo_height() < SMALLEST:
            cv.delete("all")
            self.cal_cells = []
            if cv.winfo_manager() and tries < 40:
                self.cal_draw_soon(tries + 1)
            return
        evs = self.cal_events() if evs is None else evs
        import tkinter.font as tkfont
        cv.delete("all")
        self.cal_cells = []
        W, H = max(cv.winfo_width(), 7), max(cv.winfo_height(), 7)
        small, bold = tkfont.Font(root=cv, font=("Segoe UI", 9)), tkfont.Font(root=cv, font=("Segoe UI", 9, "bold"))
        lh = small.metrics("linespace") + 2
        head = lh + 8
        y, m = self.cal_ym
        rows = CD.weeks(y, m)
        cw, ch = W / 7, (H - head) / len(rows)
        for i, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            cv.create_text(i * cw + 8, head / 2, text=name, anchor="w", font=bold, fill=C["muted"])
        cv.create_line(0, head, W, head, fill=C["line"])
        today = _dt.date.today()
        for r, week in enumerate(rows):
            for c, day in enumerate(week):
                x0, y0, x1, y1 = c * cw, head + r * ch, (c + 1) * cw, head + (r + 1) * ch
                self.cal_cells.append((x0, y0, x1, y1, day))
                first, last = self.cal_range()
                picked, out = first <= day <= last, day.month != m
                if picked:
                    cv.create_rectangle(x0 + 1, y0 + 1, x1, y1, fill=C["sel"],
                                        outline=C["accent"] if day in (first, last) else "")
                elif day == today:
                    cv.create_rectangle(x0 + 1, y0 + 1, x1, y1, fill=C["odd"], outline="")
                if c:
                    cv.create_line(x0, y0, x0, y1, fill=C["line"])
                if r:
                    cv.create_line(x0, y0, x1, y0, fill=C["line"])
                num = f"{day.day} · Today" if day == today else str(day.day)
                cv.create_text(x0 + 8, y0 + 4, text=num, anchor="nw", font=bold if day == today else small,
                               fill=C["line"] if out else C["text"] if day == today else C["muted"])
                if out:
                    continue
                todays = CD.on_day(evs, day)
                room = max(1, int((ch - lh - 8) // lh))
                show = todays if len(todays) <= room else todays[:max(1, room - 1)]
                ty = y0 + 4 + lh
                for ev in show:
                    words = f"{CD.mark(ev['kind'])} {ev['name']}" if CD.is_mine(ev) else \
                        f"{CD.label(ev)}: {ev['name']}"
                    words = self._cal_fit(words, bold, cw - 12)
                    cv.create_text(x0 + 8, ty, text=words, anchor="nw", font=bold, fill=kind_color(ev["kind"]))
                    ty += lh
                if len(show) < len(todays):
                    cv.create_text(x0 + 8, ty, text=f"+ {len(todays) - len(show)} more", anchor="nw", font=small,
                                   fill=C["muted"])

    @staticmethod
    def _cal_fit(text, font, width):
        if font.measure(text) <= width:
            return text
        while len(text) > 2 and font.measure(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def cal_range(self):
        """The picked days, first and last. One day picked: both are that day."""
        a, b = self.cal_day, getattr(self, "cal_day2", None) or self.cal_day
        return (a, b) if a <= b else (b, a)

    def cal_range_words(self):
        first, last = self.cal_range()
        if first == last:
            return CD.day_words(first)
        return f"{CD.day_words(first)} to {CD.day_words(last)}"

    def cal_grid_click(self, e, keep_range=False):
        """A click picks a day. Shift and a click picks every day from the picked one to this one. keep_range:
        a right-click inside the picked range leaves it as it is."""
        for x0, y0, x1, y1, day in self.cal_cells:
            if x0 <= e.x < x1 and y0 <= e.y < y1:
                first, last = self.cal_range()
                if keep_range and first != last and first <= day <= last:
                    return
                if int(getattr(e, "state", 0) or 0) & 0x0001 and not keep_range:
                    self.cal_day2 = day                      # the first day picked stays the range's other end
                else:
                    self.cal_day, self.cal_day2 = day, None
                    if (day.year, day.month) != self.cal_ym:
                        self.cal_ym = (day.year, day.month)
                self.cal_pick = None
                self.cal_refresh()
                return

    def cal_grid_menu(self, e):
        """Right-click a day: it is picked, and a menu offers Add Reminder first, then what the day's event takes."""
        from .listkit import _menu
        self.cal_grid_click(e, keep_range=True)
        ev = self.cal_picked()
        m = _menu(self.cal_grid)
        m.add_command(label="Add Reminder…", command=self.cal_add)
        try:
            import tkinter.font as tkfont
            bold = tkfont.nametofont("TkMenuFont").copy()
            bold.configure(weight="bold")
            m._soe2_bold = bold
            m.entryconfigure(0, font=bold)
        except tk.TclError:
            pass
        st = lambda on: "normal" if on else "disabled"       # noqa: E731
        m.add_separator()
        m.add_command(label="Change Reminder…", state=st(ev), command=self.cal_change_reminder)
        m.add_command(label="Open Link", state=st(ev and ev.get("link")), command=self.cal_open_link)
        m.add_separator()
        m.add_command(label="Delete", state=st(CD.is_mine(ev)), accelerator="Del", command=self.cal_delete)
        if self.cal_is_admin():
            board = bool(ev) and not CD.is_mine(ev)
            m.add_separator()
            m.add_command(label="Admin: Post Event…", command=self.cal_post)
            m.add_command(label="Admin: Edit Event…", state=st(board), command=self.cal_edit_event)
            m.add_command(label="Admin: Delete Event", state=st(board), command=self.cal_delete_event)
        self.cal_day_menu = m
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    def cal_fill_list(self, evs):
        tv = self.cal_tv
        keep = self.cal_pick
        tv.delete(*tv.get_children())
        now = time.time()
        for ev in evs:
            tv.insert("", "end", iid=str(ev["id"]), text=ev["name"],
                      values=(CD.label(ev), f"{CD.day_words(CD.local_day(ev['start']))}, {CD.clock(ev['start'])}",
                              "Live" if CD.live(ev, now) else CD.away(ev["start"], now), CD.remind_line(ev)))
        if keep is not None and tv.exists(str(keep)):
            tv.selection_set(str(keep))

    def cal_list_picked(self):
        sel = self.cal_tv.selection()
        if not sel or sel[0] == str(self.cal_pick):
            return
        ev = next((e for e in CD.events() if str(e["id"]) == sel[0]), None)
        if ev:
            self.cal_pick, self.cal_day, self.cal_day2 = ev["id"], CD.local_day(ev["start"]), None
            self.cal_show_day(self.cal_events())

    def cal_picked(self, evs=None):
        """The event the right side is about: the one clicked, else the day's first."""
        evs = self.cal_events() if evs is None else evs
        first, last = self.cal_range()
        todays = [e for e in evs if CD.span(e)[0] <= last and CD.span(e)[1] >= first]
        return next((e for e in todays if e["id"] == self.cal_pick), todays[0] if todays else None)

    def cal_show_day(self, evs):
        from .style import Tooltip
        box, P1 = self.cal_day_box, C["panel"]
        for w in box.winfo_children():
            w.destroy()
        first, last = self.cal_range()
        todays = [e for e in evs if CD.span(e)[0] <= last and CD.span(e)[1] >= first]
        self.cal_day_head.set_title(self.cal_range_words())
        self.cal_day_head.note("1 event" if len(todays) == 1 else f"{len(todays)} events")
        if not todays:
            self.cal_empty.set_text("Nothing on this day\nAdd Reminder puts one of your own here." if first == last
                                    else "Nothing on these days\nAdd Reminder puts one of your own across them.")
            self.cal_empty.place(relx=0.5, rely=0.4, anchor="center")
            return
        self.cal_empty.place_forget()
        ev = self.cal_picked(evs)
        self.cal_pick = ev["id"]
        if len(todays) > 1:                                  # more than one that day: a line each, the open one marked
            for e in todays:
                on = e["id"] == ev["id"]
                lab = tk.Label(box, text=("▶ " if on else "   ") + f"{CD.label(e)}: {e['name']}", bg=P1, anchor="w",
                               fg=kind_color(e["kind"]), font=("Segoe UI", 9, "bold" if on else "normal"),
                               cursor="hand2")
                lab.pack(fill="x")
                lab.bind("<Button-1>", lambda _e, i=e["id"]: self.cal_pick_event(i))
            tk.Frame(box, bg=C["line"], height=1).pack(fill="x", pady=8)
        kv = tk.Frame(box, bg=P1)
        kv.pack(fill="x")
        kv.columnconfigure(1, weight=1)
        rows = [("What", CD.label(ev), kind_color(ev["kind"])), ("Name", ev["name"], C["text"]),
                ("Starts", CD.starts_line(ev), C["text"]), ("Ends", CD.ends_line(ev), C["text"]),
                ("Posted by", ev.get("by") or "Official", C["text"]), ("Reminder", CD.remind_line(ev), C["text"])]
        if ev.get("note"):
            rows.append(("Note", ev["note"], C["text"]))
        vals = []
        for i, (k, v, col) in enumerate(rows):
            tk.Label(kv, text=k, bg=P1, fg=C["muted"], anchor="nw", font=("Segoe UI", 9)).grid(
                row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
            lab = tk.Label(kv, text=v, bg=P1, fg=col, anchor="w", justify="left",
                           font=("Segoe UI", 9, "bold" if k == "What" else "normal"))
            lab.grid(row=i, column=1, sticky="we", pady=2)
            vals.append(lab)
        kv.bind("<Configure>", lambda e: [v.config(wraplength=max(60, e.width - 110)) for v in vals
                                          if v.winfo_exists()])
        btns = tk.Frame(box, bg=P1)
        btns.pack(fill="x", pady=(12, 0))
        b = ttk.Button(btns, text="Change Reminder", width=0, command=self.cal_change_reminder)
        b.pack(side="left", padx=(0, 8))
        Tooltip(b, "When this PC tells you about it")
        b = ttk.Button(btns, text="Open Link", width=0, command=self.cal_open_link)
        b.pack(side="left", padx=(0, 8))
        Tooltip(b, "Opens its announcement in your browser" if ev.get("link") else "This event has no link")
        if not ev.get("link"):
            b.state(["disabled"])
        b = ttk.Button(btns, text="Delete", width=0, command=self.cal_delete)
        b.pack(side="left")
        Tooltip(b, "Deletes this reminder of yours. Undo brings it back." if CD.is_mine(ev)
                else "Only your own reminders can be deleted here")
        if not CD.is_mine(ev):
            b.state(["disabled"])
        try:
            from .style import flowify
            flowify(btns)
        except Exception:
            buglog.caught()
        if self.cal_plan_shown():                            # one click: this event as a goal in League Plan
            tk.Frame(box, bg=C["line"], height=1).pack(fill="x", pady=(12, 8))
            has = self.cal_in_plan(ev)
            b = ttk.Button(box, text="✓ In League Plan" if has else "Add to League Plan", width=0,
                           command=self.cal_to_plan)
            b.pack(anchor="w")
            Tooltip(b, "Already a goal in League Plan" if has else
                    "Adds a goal to League Plan: Be ready for this, with its day. You tick it when you are.")
            if has:
                b.state(["disabled"])
        if self.cal_is_admin():                              # admins: change or delete a board event
            tk.Frame(box, bg=C["line"], height=1).pack(fill="x", pady=(12, 8))
            tk.Label(box, text="Admins only", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(fill="x")
            arow = tk.Frame(box, bg=P1)
            arow.pack(fill="x", pady=(4, 0))
            for text, fn, tip in (("Edit Event", self.cal_edit_event, "Changes it for every user"),
                                  ("Delete Event", self.cal_delete_event,
                                   "Deletes it from the board for every user. It cannot be brought back.")):
                b = ttk.Button(arow, text=text, width=0, command=fn)
                b.pack(side="left", padx=(0, 8))
                Tooltip(b, tip if not CD.is_mine(ev) else "This one is yours, not a board event")
                if CD.is_mine(ev):
                    b.state(["disabled"])

    def cal_pick_event(self, eid):
        self.cal_pick = eid
        self.cal_refresh()

    # ---------------------------------------------------------------- acting
    def cal_menu_actions(self, _sel=None):
        ev = self.cal_picked()
        acts = [("Change Reminder…", self.cal_change_reminder, bool(ev)),
                ("Open Link", self.cal_open_link, bool(ev and ev.get("link"))), None,
                ("Delete", self.cal_delete, CD.is_mine(ev), "Del")]
        if self.cal_is_admin():
            board = bool(ev) and not CD.is_mine(ev)
            acts += [("Admin: Post Event…", self.cal_post, True), ("Admin: Edit Event…", self.cal_edit_event, board),
                     ("Admin: Delete Event", self.cal_delete_event, board)]
        return acts

    def cal_open_link(self):
        ev = self.cal_picked()
        link = (ev or {}).get("link") or ""
        if link.startswith("https://"):
            webbrowser.open(link)

    def cal_delete(self):
        ev = self.cal_picked()
        if not CD.is_mine(ev):
            return
        gone = CD.remove_mine(ev["id"])
        if gone:
            self.push_undo(KEY, f"the reminder {gone['name']}", lambda g=gone: (CD.restore_mine(g), self.cal_changed()))
        self.cal_pick = None
        self.cal_changed()

    def cal_changed(self):
        self.cal_refresh()
        self.cal_overlay_sync()
        dash = getattr(getattr(self, "shell", None), "modules", {}).get("dashboard")
        page = getattr(dash, "page", None)
        if page is not None:
            page.later()

    def _cal_dialog(self, title):
        dlg = tk.Toplevel(self.root)
        over_app(dlg, self.dlg_parent())
        dlg.title(title)
        dlg.configure(bg=C["panel2"], padx=16, pady=12)
        dlg.transient(self.root)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        return dlg

    @staticmethod
    def _cal_time(parent, hour=20, minute=0):
        """3.3.0 owner: the time was a box that took any typing. Three pickers that cannot hold a wrong time:
        hour, minute, and AM or PM when the app clock is a 12 hour one. -> (the frame, read) where read() gives
        (hour, minute)."""
        P2 = C["panel2"]
        hours, mins, halves = CD.clock_choices()
        h, m, half = CD.clock_parts(hour, minute)
        if m not in mins:                                   # an event at 9:17 keeps its minute
            mins = sorted(set(mins) | {m})
        row = tk.Frame(parent, bg=P2)
        hv, mv, av = tk.StringVar(value=h), tk.StringVar(value=m), tk.StringVar(value=half)
        ttk.Combobox(row, textvariable=hv, values=hours, state="readonly", width=3).pack(side="left")
        tk.Label(row, text=":", bg=P2, fg=C["text"]).pack(side="left", padx=2)
        ttk.Combobox(row, textvariable=mv, values=mins, state="readonly", width=3).pack(side="left")
        if halves:
            ttk.Combobox(row, textvariable=av, values=halves, state="readonly", width=4).pack(side="left", padx=(8, 0))
        row.cal_vars = (hv, mv, av)
        return row, lambda: CD.clock_from_parts(hv.get(), mv.get(), av.get())

    def _cal_lead_boxes(self, dlg, leads):
        P2 = C["panel2"]
        tk.Label(dlg, text="Tell me", bg=P2, fg=C["text"]).pack(anchor="w")
        vars_ = {}
        for words, secs in CD.LEADS:
            v = vars_[secs] = tk.BooleanVar(value=secs in leads)
            ttk.Checkbutton(dlg, text=words, variable=v, style="Card.TCheckbutton").pack(anchor="w")
        return vars_

    def cal_change_reminder(self):
        ev = self.cal_picked()
        if not ev:
            return
        dlg = self._cal_dialog("Change Reminder")
        P2 = C["panel2"]
        tk.Label(dlg, text=f"{CD.label(ev)}: {ev['name']}", bg=P2, fg=kind_color(ev["kind"]),
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(dlg, text=CD.starts_line(ev), bg=P2, fg=C["muted"]).pack(anchor="w", pady=(0, 8))
        vars_ = self._cal_lead_boxes(dlg, CD.reminders(ev))
        tk.Label(dlg, text="No box ticked means no reminder.", bg=P2, fg=C["muted"]).pack(anchor="w", pady=(4, 8))

        def save():
            CD.set_reminders(ev["id"], [s for s, v in vars_.items() if v.get()])
            dlg.destroy()
            self.cal_changed()
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x")
        ttk.Button(row, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(row, text="Cancel", command=dlg.destroy).pack(side="right", padx=(0, 8))
        dlg.bind("<Return>", lambda e: save())
        self._cal_grab(dlg)

    def cal_add(self):
        from . import cleanguard
        dlg = self._cal_dialog("Add Reminder")
        P2 = C["panel2"]
        first, last = self.cal_range()
        day, day2 = [first], [last]
        tk.Label(dlg, text="Name", bg=P2, fg=C["text"]).pack(anchor="w")
        name = tk.StringVar()
        ent = ttk.Entry(dlg, textvariable=name, width=44)
        ent.pack(fill="x", pady=(2, 8))

        def day_row(title, hold):
            tk.Label(dlg, text=title, bg=P2, fg=C["text"]).pack(anchor="w")
            drow = tk.Frame(dlg, bg=P2)
            drow.pack(fill="x", pady=(2, 8))
            dlab = tk.Label(drow, text="", bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold"), width=18)

            def step(by):
                hold[0] = hold[0] + _dt.timedelta(days=by)
                dlab.config(text=f"{CD.day_words(hold[0])} {hold[0].year}")
            ttk.Button(drow, text="‹", width=3, command=lambda: step(-1)).pack(side="left")
            dlab.pack(side="left")
            ttk.Button(drow, text="›", width=3, command=lambda: step(1)).pack(side="left")
            step(0)
        day_row("Day", day)
        many = tk.BooleanVar(value=first != last)            # a Shift-clicked range comes filled in
        ttk.Checkbutton(dlg, text="It runs for more than one day", variable=many, style="Card.TCheckbutton").pack(anchor="w")
        day_row("Last day", day2)
        tk.Label(dlg, text="Time, on this PC's clock", bg=P2, fg=C["text"]).pack(anchor="w")
        trow, clock = self._cal_time(dlg)
        trow.pack(anchor="w", pady=(2, 8))
        vars_ = self._cal_lead_boxes(dlg, (0,))
        tk.Label(dlg, text="Note", bg=P2, fg=C["text"]).pack(anchor="w", pady=(8, 0))
        note = tk.StringVar()
        ne = ttk.Entry(dlg, textvariable=note, width=44)
        ne.pack(fill="x", pady=(2, 8))
        cleanguard.free(ne)                                 # a note: a person can write what they want
        msg = tk.Label(dlg, text="", bg=P2, fg=C["red"], anchor="w")
        msg.pack(fill="x")

        def save():
            hm = clock()
            if hm is None:
                return msg.config(text="Pick a time.")
            end = CD.at(day2[0], 23, 59) if many.get() else 0
            got = CD.add_mine(name.get(), CD.at(day[0], *hm), end=end, note=note.get(),
                              leads=[s for s, v in vars_.items() if v.get()])
            if isinstance(got, str):
                return msg.config(text=got)
            dlg.destroy()
            self.cal_day, self.cal_day2, self.cal_pick = day[0], None, got["id"]
            self.cal_ym = (day[0].year, day[0].month)
            if not self.cal_kind_vars["mine"].get():        # it would be hidden the moment it is made
                self.cal_kind_vars["mine"].set(True)
                self.cal_kinds_changed()
            self.cal_changed()
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x")
        ttk.Button(row, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(row, text="Cancel", command=dlg.destroy).pack(side="right", padx=(0, 8))
        dlg.bind("<Return>", lambda e: save())
        ent.focus_set()
        self._cal_grab(dlg)
        dlg.cal_save, dlg.cal_vars = save, {"name": name, "many": many, "day": day, "day2": day2, "msg": msg,
                                            "clock": clock}
        return dlg

    # ---------------------------------------------------------------- the overlay's line
    def cal_overlay_text(self):
        """What the overlay's Calendar line says now, or "" when its switch is off or nothing is near."""
        if not SETTINGS.get("cal_overlay"):
            return ""
        try:
            return CD.overlay_text()
        except Exception:
            buglog.caught()
            return ""

    def cal_overlay_switch(self):
        SETTINGS["cal_overlay"] = bool(self.cal_ov_var.get())
        save_json("settings.json", SETTINGS)
        self.cal_overlay_sync()

    def cal_overlay_sync(self):
        """The overlay's lines are built again only when the Calendar line comes or goes, never for a change of
        words: those change in place."""
        try:
            if getattr(self, "mg_win", None) is None:
                return False
            if self.goalbar_rows() != (getattr(self, "goal_rows", None) or []):
                self.goalbar_build()
                return True
            lab = (getattr(self, "tk_ov_lbls", None) or {}).get("calendar")
            if lab is not None:
                lab.config(text=self.cal_overlay_text())
        except Exception:
            buglog.caught()
        return False

    # ---------------------------------------------------------------- League Plan
    def cal_plan_shown(self):
        """True while League Plan is a page this install shows."""
        sh = getattr(self, "shell", None)
        mod = getattr(sh, "modules", {}).get("plan") if sh else None
        try:
            return mod is not None and bool(sh.visible(mod))
        except Exception:
            return False

    def cal_in_plan(self, ev):
        from . import focus as F
        want = CD.plan_goal_text(ev)
        return any(g.get("text") == want and not g.get("done") for g in F.cfg()["goals"])

    def cal_to_plan(self):
        """The picked event becomes a League Plan goal you tick. Once: a second click adds nothing."""
        from . import focus as F
        ev = self.cal_picked()
        if not ev or self.cal_in_plan(ev):
            return None
        g = F.add_goal(CD.plan_goal_text(ev))
        try:
            self.gp_fill()
            self.gp_overlay()
        except Exception:
            pass                                             # League Plan's page is not built in this window
        self.cal_refresh()
        return g

    # ---------------------------------------------------------------- admins: the board's events
    def cal_edit_event(self):
        ev = self.cal_picked()
        if ev and not CD.is_mine(ev):
            self.cal_post(ev)

    def cal_delete_event(self):
        ev = self.cal_picked()
        if not ev or CD.is_mine(ev) or not self.cal_is_admin():
            return None
        from tkinter import messagebox
        if not messagebox.askyesno("Delete from the board", f"Delete \"{ev['name']}\" from the Calendar?\n\n"
                                   "It is removed for everyone and cannot be brought back.", parent=self.dlg_parent()):
            return False
        from . import board as B
        self.run_bg(lambda: B.event_delete(CD.board_number(ev)), lambda res: self._cal_board_done(res))
        return True

    def _cal_board_done(self, res, dlg=None, msg=None):
        """After an admin's post, change or delete: the list is asked for again, or the board's reason is shown."""
        ok, why = res if isinstance(res, tuple) and len(res) == 2 else (False, "The board did not answer.")
        if not ok:
            if "404" in str(why) or str(why).strip().lower() == "not found":   # an older board: no Calendar part yet
                why = "The board does not have the Calendar yet. It arrives with the next board update."
            if msg is not None and msg.winfo_exists():
                msg.config(text=str(why))
            else:
                from tkinter import messagebox
                messagebox.showwarning("Calendar", str(why), parent=self.dlg_parent())
            return False
        if dlg is not None and dlg.winfo_exists():
            dlg.destroy()
        self.cal_pick = None
        self.cal_pull()
        return True

    def cal_drafts(self):
        """Admin: what the board drafted from Steam news. Review opens the draft in the Post Event box; posting it
        there is what makes it live. Dismiss drops it for good."""
        from . import board as B
        from .style import Tooltip
        if not self.cal_is_admin():
            return None
        dlg = self._cal_dialog("Drafts")
        P2 = C["panel2"]
        tk.Label(dlg, text="The board reads Steam news for Path of Exile 1 and 2 every 6 hours. A draft reaches no "
                           "user until you post it.", bg=P2, fg=C["muted"], justify="left", wraplength=560).pack(
            anchor="w", pady=(0, 8))
        tv = ttk.Treeview(dlg, columns=("kind", "starts"), show="tree headings", selectmode="browse", height=8)
        for cid, text, w in (("#0", "Name", 340), ("kind", "Kind", 120), ("starts", "Its guess for the start", 180)):
            tv.heading(cid, text=text)
            tv.column(cid, width=w, anchor="w", stretch=cid == "#0")
        tv.pack(fill="both", expand=True)
        msg = tk.Label(dlg, text="Loading…", bg=P2, fg=C["muted"], anchor="w", justify="left", wraplength=560)
        msg.pack(fill="x", pady=(8, 8))
        rows = {}

        def picked():
            sel = tv.selection()
            return rows.get(sel[0]) if sel else None

        def greys(_e=None):
            for b in (review, dismiss):
                b.state(["!disabled"] if picked() else ["disabled"])

        def fill(res):
            if not dlg.winfo_exists():
                return
            ok, data = res if isinstance(res, tuple) and len(res) == 2 else (False, "The board did not answer.")
            tv.delete(*tv.get_children())
            rows.clear()
            if not ok:
                if "404" in str(data) or str(data).strip().lower() == "not found":
                    data = "The board does not have the Calendar yet. It arrives with the next board update."
                msg.config(text=str(data), fg=C["red"])
                return greys()
            for ev in CD.clean_board_rows((data or {}).get("events")):
                rows[ev["id"]] = ev
                tv.insert("", "end", iid=ev["id"], text=ev["name"], values=(
                    CD.label(ev), f"{CD.day_words(CD.local_day(ev['start']))}, {CD.clock(ev['start'])}"))
            msg.config(fg=C["muted"], text=f"{len(rows)} waiting. Pick one, then Review." if rows else
                       "No drafts. Nothing new on Steam since the last check.")
            self.cal_drafts_set(len(rows))
            greys()

        def load():
            msg.config(text="Loading…", fg=C["muted"])
            self.run_bg(B.event_drafts, fill)

        def do_review():
            ev = picked()
            if ev:
                self.cal_post(ev, draft=True, then=load)

        def do_dismiss():
            ev = picked()
            if ev:
                self.run_bg(lambda: B.event_delete(CD.board_number(ev)), lambda _r: load())

        def do_check():
            def after(res):
                if not dlg.winfo_exists():
                    return
                ok, data = res if isinstance(res, tuple) and len(res) == 2 else (False, "")
                if not ok:
                    return fill(res)
                self.run_bg(B.event_drafts, lambda r: (fill(r), msg.winfo_exists() and msg.config(
                    text=f"Checked Steam: {int((data or {}).get('added') or 0)} new. " + msg.cget("text"))))
            msg.config(text="Checking Steam…", fg=C["muted"])
            self.run_bg(B.event_check, after)
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x")
        review = ttk.Button(row, text="Review", style="Primary.TButton", width=0, command=do_review)
        review.pack(side="left", padx=(0, 8))
        Tooltip(review, "Opens it in the Post Event box. Check the day and time, then Post makes it live.")
        dismiss = ttk.Button(row, text="Dismiss", width=0, command=do_dismiss)
        dismiss.pack(side="left", padx=(0, 8))
        Tooltip(dismiss, "Drops this draft. The board will not draft the same post again.")
        chk = ttk.Button(row, text="Check Steam Now", width=0, command=do_check)
        chk.pack(side="left")
        Tooltip(chk, "The board reads Steam news now, not at its next 6 hours")
        ttk.Button(row, text="Close", width=0, command=dlg.destroy).pack(side="right")
        tv.bind("<<TreeviewSelect>>", greys)
        tv.bind("<Double-1>", lambda e: do_review())
        greys()
        load()
        dlg.cal_parts = {"tv": tv, "msg": msg, "review": review, "dismiss": dismiss, "check": do_check,
                         "do_review": do_review, "do_dismiss": do_dismiss, "rows": rows}
        return dlg

    def cal_post(self, ev=None, draft=False, then=None):
        """Admin: post an event to the board, or change one, or review a draft. One box for all three."""
        from . import cleanguard
        if not self.cal_is_admin():
            return None
        dlg = self._cal_dialog("Review Draft" if draft else "Edit Event" if ev else "Post Event")
        P2 = C["panel2"]
        words = {f"{CD.mark(k)} {CD.word(k)}": k for k in CD.BOARD_KINDS}
        tk.Label(dlg, text="Kind", bg=P2, fg=C["text"]).pack(anchor="w")
        kind = tk.StringVar(value=next((w for w, k in words.items() if ev and k == ev["kind"]), ""))
        ttk.Combobox(dlg, textvariable=kind, values=list(words), state="readonly", width=24).pack(anchor="w", pady=(2, 8))
        tk.Label(dlg, text="Name", bg=P2, fg=C["text"]).pack(anchor="w")
        name = tk.StringVar(value=ev["name"] if ev else "")
        ent = ttk.Entry(dlg, textvariable=name, width=48)
        ent.pack(fill="x", pady=(2, 8))

        def when(title, ts, day0):
            """A day with arrows and a time box. -> (the day holder, the time's text)"""
            tk.Label(dlg, text=title, bg=P2, fg=C["text"]).pack(anchor="w")
            row = tk.Frame(dlg, bg=P2)
            row.pack(fill="x", pady=(2, 0))
            day = [CD.local_day(ts) if ts else day0]
            lab = tk.Label(row, text="", bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold"), width=18)

            def step(by):
                day[0] = day[0] + _dt.timedelta(days=by)
                lab.config(text=f"{CD.day_words(day[0])} {day[0].year}")
            ttk.Button(row, text="‹", width=3, command=lambda: step(-1)).pack(side="left")
            lab.pack(side="left")
            ttk.Button(row, text="›", width=3, command=lambda: step(1)).pack(side="left")
            step(0)
            t = _dt.datetime.fromtimestamp(ts) if ts else None
            trow, clock = self._cal_time(row, t.hour if t else 20, t.minute if t else 0)
            trow.pack(side="left", padx=(12, 0))
            return day, clock
        first, last = self.cal_range()
        sday, sclock = when("Starts, on this PC's clock", ev["start"] if ev else 0, first)
        tk.Label(dlg, text="Every user sees it in their own time.", bg=P2, fg=C["muted"]).pack(
            anchor="w", pady=(0, 8))
        has_end = tk.BooleanVar(value=bool(ev and ev.get("end")) or (not ev and first != last))
        ttk.Checkbutton(dlg, text="It has an end", variable=has_end, style="Card.TCheckbutton").pack(anchor="w")
        eday, eclock = when("Ends", ev["end"] if ev and ev.get("end") else 0, last)
        tk.Label(dlg, text="Link to its announcement", bg=P2, fg=C["text"]).pack(anchor="w", pady=(8, 0))
        link = tk.StringVar(value=ev.get("link", "") if ev else "")
        le = ttk.Entry(dlg, textvariable=link, width=48)
        le.pack(fill="x", pady=(2, 0))
        cleanguard.free(le)                                 # a web address, checked when it is saved
        tk.Label(dlg, text="Starts with https://  Leave it empty for none.", bg=P2, fg=C["muted"]).pack(anchor="w",
                                                                                                   pady=(0, 8))
        tk.Label(dlg, text="Note", bg=P2, fg=C["text"]).pack(anchor="w")
        note = tk.StringVar(value=ev.get("note", "") if ev else "")
        ttk.Entry(dlg, textvariable=note, width=48).pack(fill="x", pady=(2, 8))
        msg = tk.Label(dlg, text="", bg=P2, fg=C["red"], anchor="w", justify="left", wraplength=360)
        msg.pack(fill="x")

        def save():
            s, e = sclock(), eclock()
            if s is None or (has_end.get() and e is None):
                return msg.config(text="Pick a time.")
            body = CD.event_body(words.get(kind.get()), name.get(), CD.at(sday[0], *s),
                                 CD.at(eday[0], *e) if has_end.get() else 0, link.get(), note.get())
            if isinstance(body, str):
                return msg.config(text=body)
            from . import board as B
            msg.config(text="Sending…", fg=C["muted"])
            num = CD.board_number(ev) if ev else None
            self.run_bg(lambda: B.event_save(body, num),
                        lambda res: (msg.winfo_exists() and msg.config(fg=C["red"]),
                                     self._cal_board_done(res, dlg, msg) and then and then()))
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x")
        ttk.Button(row, text="Save" if ev and not draft else "Post", style="Primary.TButton", command=save).pack(
            side="right")
        ttk.Button(row, text="Cancel", command=dlg.destroy).pack(side="right", padx=(0, 8))
        dlg.bind("<Return>", lambda e: save())
        ent.focus_set()
        self._cal_grab(dlg)
        dlg.cal_save, dlg.cal_vars = save, {"kind": kind, "name": name, "link": link, "note": note, "msg": msg,
                                            "has_end": has_end, "sclock": sclock, "eclock": eclock}
        return dlg

    @staticmethod
    def _cal_grab(dlg):
        try:
            dlg.grab_set()
        except tk.TclError:
            pass

    def cal_remind_me(self, eid):
        """Dashboard, Upcoming: one click sets the usual reminder; a second click takes it off."""
        ev = next((e for e in CD.events() if e["id"] == eid), None)
        if not ev:
            return
        CD.set_reminders(eid, () if CD.reminders(ev) else DEFAULT_LEADS)
        self.cal_changed()

    # ---------------------------------------------------------------- reminders
    def cal_tick(self):
        try:
            self.cal_fire()
            self.cal_overlay_sync()
            if time.time() - getattr(self, "cal_pulled_at", 0) >= PULL_SECS:
                self.cal_pull()
        except Exception:
            buglog.caught()
        try:
            self.root.after(TICK_MS, self.cal_tick)
        except tk.TclError:
            pass

    def cal_fire(self, now=None):
        """-> the reminders said just now."""
        got = CD.due(now)
        for ev, lead in got:
            title, line = CD.remind_words(ev, lead, now)
            try:
                from . import alertcard
                from .alerts_page import game_rect
                alertcard.show(self.root, title, line, color=kind_color(ev["kind"]), mark=CD.mark(ev["kind"]), secs=12,
                               game=game_rect(), tag="Calendar")
            except Exception:
                buglog.caught()
        if got:
            self.cal_changed()
        return got
