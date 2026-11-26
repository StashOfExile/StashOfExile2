"""The Exchange Rates overlay's currencies: the player picks which ones show and drags them into order.

DragList is the drag to reorder used by the picker and by the overlay itself: hold a row's ⋮⋮ grip and drag it; a
line shows where the row will land; letting go puts it there. The picker lists every currency poe.ninja has a rate
for, with its picture, a search box first. Picks and their order are saved in settings, so they survive a restart.
Only numbers the app already has are shown: no reads, no requests beyond the pictures poe.ninja serves."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from .config import SETTINGS, save_json

GRIP = "⋮⋮"
HELP = "Pick up to 10 currencies to watch. Drag ⋮⋮ to change the order."
MAX_PICKS = 10
FULL = "That's 10. Take one off first."


def picked(cfg=None):
    """The picked currency ids, in order. Never set yet: the overlay's old list, so nothing changes until you pick."""
    from .ovrates import COMMON
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    p = c.get("picked")
    if not isinstance(p, list):
        p = c["picked"] = list(COMMON)[:MAX_PICKS]
    return p


def against(cfg=None):
    """The currency the overlay's rates are shown in: Divine Orb until you pick another."""
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    return c.get("against") or "divine"


def set_against(cid, cfg=None):
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    c["against"] = cid or "divine"
    save_json("settings.json", SETTINGS)


def first_use_due(cfg=None):
    """Has the picker never opened by itself yet? It opens once for everyone who has Rates on the overlay,
    installs from before it existed too."""
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    return bool(c.get("on")) and not c.get("pick_shown")


def mark_first_use(cfg=None):
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    c["pick_shown"] = True
    save_json("settings.json", SETTINGS)


def set_picked(ids, cfg=None):
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    c["picked"] = out
    save_json("settings.json", SETTINGS)
    return out


def moved(ids, src, dst):
    """ids with the one at src moved so it lands before the row that was at dst; dst may be len(ids), the end."""
    ids = list(ids)
    if not 0 <= src < len(ids):
        return ids
    dst = max(0, min(dst, len(ids)))
    item = ids.pop(src)
    if dst > src:
        dst -= 1
    ids.insert(dst, item)
    return ids


class DragList:
    """Rows a player reorders by dragging their ⋮⋮ grip. rows: [(key, row frame, grip widget)] in order, packed in
    `host` top to bottom. on_drop(new_keys) runs after a drop that changed the order."""

    def __init__(self, host, rows, on_drop, line="#d4af5f"):
        self.host, self.rows, self.on_drop = host, list(rows), on_drop
        self.mark = tk.Frame(host, bg=line, height=2)
        self.src = self.dst = None
        for k, _row, grip in self.rows:
            grip.configure(cursor="sb_v_double_arrow")
            grip.bind("<ButtonPress-1>", lambda e, k=k: self._press(self.keys().index(k)), add="+")
            grip.bind("<B1-Motion>", self._motion, add="+")
            grip.bind("<ButtonRelease-1>", self._release, add="+")

    def set_order(self, keys):
        """The same rows in a new order: they are moved, not made again."""
        by = {k: (k, r, g) for k, r, g in self.rows}
        self.rows = [by[k] for k in keys if k in by]

    def keys(self):
        return [k for k, _r, _g in self.rows]

    def target(self, y_root):
        """The row slot, 0 to len, a pointer at y_root would drop into."""
        for i, (_k, row, _g) in enumerate(self.rows):
            try:
                top, h = row.winfo_rooty(), row.winfo_height()
            except tk.TclError:
                continue
            if y_root < top + h / 2:
                return i
        return len(self.rows)

    def _press(self, i):
        self.src, self.dst = i, i
        return "break"

    def _motion(self, e):
        if self.src is None:
            return None
        self.dst = self.target(e.y_root)
        try:
            if self.dst < len(self.rows):
                y = self.rows[self.dst][1].winfo_y()
            else:
                last = self.rows[-1][1]
                y = last.winfo_y() + last.winfo_height()
            self.mark.place(x=0, y=max(0, y - 1), relwidth=1)
            self.mark.lift()
        except tk.TclError:
            pass
        return "break"

    def _release(self, _e):
        src, dst, self.src, self.dst = self.src, self.dst, None, None
        try:
            self.mark.place_forget()
        except tk.TclError:
            pass
        if src is None or dst is None or dst in (src, src + 1):
            return "break"
        new = moved(self.keys(), src, dst)
        try:
            self.on_drop(new)
        except Exception:
            buglog.caught()
        return "break"


class RatesPicker:
    """The Pick currencies window: every currency with a rate on the left, a search box first; your picks on the right
    with their ⋮⋮ grips; which currency the rates are shown in; one line of help; Done. Built hidden and shown once,
    ready. A tick, a search or a drag changes only the rows it touches - nothing is destroyed and built again."""

    def __init__(self, app):
        from .rates import RATES
        from .rates_view import Icons, picture_paths, url_for
        from .style import C, over_app
        self.app, self.C = app, C
        self.names = dict(getattr(RATES, "names", {}) or {})
        self.ids = sorted((c for c, v in (RATES.table or {}).items() if v), key=lambda c: self.name(c).lower())
        self.paths, self.url_for = picture_paths(), url_for
        self.icons = Icons(app.root, self.pictures_in, size=20)
        self.all_rows, self.pick_rows, self.pic_labels = {}, {}, {}
        w = self.win = tk.Toplevel(app.root)
        w.withdraw()
        w.title("Pick currencies")
        w.configure(bg=C["panel"])
        w.minsize(560, 460)
        top = tk.Frame(w, bg=C["panel"], padx=16, pady=12)
        top.pack(fill="x")
        tk.Label(top, text=HELP, bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x")
        cols = tk.Frame(w, bg=C["panel"], padx=16)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="pick")
        cols.columnconfigure(1, weight=1, uniform="pick")
        cols.rowconfigure(1, weight=1)
        sbox = tk.Frame(cols, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        sbox.grid(row=0, column=0, sticky="ew", padx=(0, 12), pady=(0, 8))
        tk.Label(sbox, text="⌕", bg=C["odd"], fg=C["muted"]).pack(side="left", padx=(8, 0))
        self.q = tk.StringVar()
        self.search = tk.Entry(sbox, textvariable=self.q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                               relief="flat", highlightthickness=0, bd=0)
        self.search.pack(side="left", fill="x", expand=True, padx=8, ipady=8)
        self.q.trace_add("write", lambda *a: self.filter())
        self.count = tk.Label(cols, text="", bg=C["panel"], fg=C["muted"], anchor="w")
        self.count.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self.all_cv, self.all_box = self._scroller(cols, 0)
        self.pick_cv, self.pick_box = self._scroller(cols, 1)
        self.empty_all = tk.Label(self.all_box, text="", bg=C["odd"], fg=C["muted"], anchor="w", padx=8, pady=8)
        self.empty_pick = tk.Label(self.pick_box, text="Nothing picked yet. Turn a currency on at the left.",
                                   bg=C["odd"], fg=C["muted"], anchor="w", padx=8, pady=8)
        self.mark = tk.Frame(self.pick_box, bg=C["accent"], height=2)
        bot = tk.Frame(w, bg=C["panel"], padx=16, pady=12)
        bot.pack(fill="x")
        tk.Label(bot, text="Show rates in", bg=C["panel"], fg=C["text"]).pack(side="left")
        self.vs = tk.StringVar(value=self.name(against(app.ovr_cfg())))
        names = [self.name(c) for c in self._against_ids()]
        self.vs_box = ttk.Combobox(bot, textvariable=self.vs, values=names, state="readonly", width=24)
        self.vs_box.pack(side="left", padx=8)
        self.vs_box.bind("<<ComboboxSelected>>", lambda e: self.pick_against(), add="+")
        self.note = tk.Label(bot, text="", bg=C["panel"], fg=C["orange"])
        self.note.pack(side="left", padx=8)
        ttk.Button(bot, text="Done", style="Primary.TButton", command=self.close).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", self.close)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            w.bind(ev, self._wheel, add="+")
        self._build_all()
        self._build_picked()
        self.filter()
        self.relayout_picked()
        w.update_idletasks()
        try:
            over_app(w, app.root)
        except Exception:
            buglog.caught()
        w.deiconify()
        self.search.focus_set()

    # ---- parts
    def name(self, cid):
        from .ovrates import cur_name
        return cur_name(cid, self.names)

    def _against_ids(self):
        first = [c for c in ("divine", "exalted", "chaos") if c in self.ids or c == "divine"]
        return first + [c for c in self.ids if c not in first]

    def _scroller(self, parent, col):
        C = self.C
        outer = tk.Frame(parent, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        outer.grid(row=1, column=col, sticky="nsew", padx=(0, 12) if col == 0 else 0)
        cv = tk.Canvas(outer, bg=C["odd"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=C["odd"])
        wid = cv.create_window(0, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")), add="+")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(wid, width=e.width), add="+")
        return cv, inner

    def _wheel(self, e):
        """The mouse wheel scrolls whichever list the pointer is over."""
        try:
            w = self.win.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, KeyError):
            return None
        while w is not None:
            for cv, box in ((self.all_cv, self.all_box), (self.pick_cv, self.pick_box)):
                if w is cv or w is box:
                    if getattr(e, "num", None) in (4, 5):
                        step = -1 if e.num == 4 else 1
                    else:
                        step = -1 if e.delta > 0 else 1
                    cv.yview_scroll(step * 2, "units")
                    return "break"
            w = w.master
        return None

    def _pic(self, cid):
        try:
            return self.icons.get(self.url_for(cid, self.paths))
        except Exception:
            return None

    def pictures_in(self):
        """New pictures came: they go into their own labels - nothing else is touched."""
        for cid, labs in self.pic_labels.items():
            img = self._pic(cid)
            if img is None:
                continue
            for lab in labs:
                try:
                    if str(lab.cget("image")) != str(img):
                        lab.configure(image=img, width=20)
                except tk.TclError:
                    pass

    def _pic_label(self, parent, cid):
        C = self.C
        img = self._pic(cid)
        lab = tk.Label(parent, bg=C["odd"], width=20 if img is not None else 2)
        if img is not None:
            lab.configure(image=img)
        lab.pack(side="left", padx=(0, 8))
        self.pic_labels.setdefault(cid, []).append(lab)
        return lab

    def _build_all(self):
        """One row per currency, made once."""
        C = self.C
        mine = set(picked(self.app.ovr_cfg()))
        for cid in self.ids:
            row = tk.Frame(self.all_box, bg=C["odd"])
            v = tk.BooleanVar(value=cid in mine)
            cb = ttk.Checkbutton(row, variable=v, command=lambda c=cid, v=v: self.tick(c, v.get()))
            cb.pack(side="left", padx=(8, 4), pady=2)
            self._pic_label(row, cid)
            lab = tk.Label(row, text=self.name(cid), bg=C["odd"], fg=C["text"], anchor="w")
            lab.pack(side="left", fill="x", expand=True)
            lab.bind("<Button-1>", lambda e, c=cid, v=v: (v.set(not v.get()), self.tick(c, v.get())), add="+")
            self.all_rows[cid] = (row, v)

    def _pick_row(self, cid):
        from .style import Tooltip
        C = self.C
        row = tk.Frame(self.pick_box, bg=C["odd"])
        grip = tk.Label(row, text=GRIP, bg=C["odd"], fg=C["muted"], padx=8)
        grip.pack(side="left")
        Tooltip(grip, "Drag to change the order")
        self._pic_label(row, cid)
        tk.Label(row, text=self.name(cid), bg=C["odd"], fg=C["text"], anchor="w").pack(side="left", fill="x",
                                                                                     expand=True, pady=4)
        x = tk.Label(row, text="✕", bg=C["odd"], fg=C["muted"], padx=8, cursor="hand2")
        x.pack(side="right")
        Tooltip(x, "Take it off the overlay")
        x.bind("<Button-1>", lambda e, c=cid: self.tick(c, False), add="+")
        grip.configure(cursor="sb_v_double_arrow")
        grip.bind("<ButtonPress-1>", lambda e, c=cid: self._press(c), add="+")
        grip.bind("<B1-Motion>", self._motion, add="+")
        grip.bind("<ButtonRelease-1>", self._release, add="+")
        self.pick_rows[cid] = row
        return row

    def _build_picked(self):
        for cid in picked(self.app.ovr_cfg()):
            self._pick_row(cid)

    # ---- what shows
    def filter(self):
        """The search shows and hides rows; they are packed again only in their own order."""
        q = self.q.get().strip().lower()
        shown = [c for c in self.ids if not q or q in self.name(c).lower()]
        for cid, (row, _v) in self.all_rows.items():
            row.pack_forget()
        for cid in shown:
            self.all_rows[cid][0].pack(fill="x")
        if shown:
            self.empty_all.pack_forget()
        else:
            self.empty_all.configure(text="No currency matches. Try fewer letters." if self.ids else
                                     "No rates yet: set your league.")
            self.empty_all.pack(fill="x")
        self.all_cv.yview_moveto(0)

    def relayout_picked(self):
        """Your picks in your order: rows are moved, not made again."""
        ids = picked(self.app.ovr_cfg())
        for cid, row in list(self.pick_rows.items()):
            if cid not in ids:
                row.destroy()
                del self.pick_rows[cid]
                self.pic_labels[cid] = [lab for lab in self.pic_labels.get(cid, []) if lab.winfo_exists()]
        for row in self.pick_rows.values():
            row.pack_forget()
        for cid in ids:
            row = self.pick_rows.get(cid) or self._pick_row(cid)
            row.pack(fill="x")
        if ids:
            self.empty_pick.pack_forget()
        else:
            self.empty_pick.pack(fill="x")
        self.count.configure(text=f"Your currencies, in overlay order · {len(ids)} of {MAX_PICKS}")

    # ---- drag
    def _target(self, y_root):
        ids = picked(self.app.ovr_cfg())
        for i, cid in enumerate(ids):
            row = self.pick_rows[cid]
            if y_root < row.winfo_rooty() + row.winfo_height() / 2:
                return i
        return len(ids)

    def _press(self, cid):
        self._drag = [picked(self.app.ovr_cfg()).index(cid), None]
        return "break"

    def _motion(self, e):
        d = getattr(self, "_drag", None)
        if not d:
            return None
        ids = picked(self.app.ovr_cfg())
        d[1] = self._target(e.y_root)
        try:
            if d[1] < len(ids):
                y = self.pick_rows[ids[d[1]]].winfo_y()
            else:
                last = self.pick_rows[ids[-1]]
                y = last.winfo_y() + last.winfo_height()
            self.mark.place(x=0, y=max(0, y - 1), relwidth=1)
            self.mark.lift()
        except (tk.TclError, KeyError):
            pass
        return "break"

    def _release(self, _e):
        d, self._drag = getattr(self, "_drag", None), None
        try:
            self.mark.place_forget()
        except tk.TclError:
            pass
        if not d or d[1] is None or d[1] in (d[0], d[0] + 1):
            return "break"
        self.reorder(moved(picked(self.app.ovr_cfg()), d[0], d[1]))
        return "break"

    # ---- changes
    def tick(self, cid, on):
        ids = list(picked(self.app.ovr_cfg()))
        if on and cid not in ids and len(ids) >= MAX_PICKS:
            row = self.all_rows.get(cid)
            if row:
                row[1].set(False)
            self.note.configure(text=FULL)
            return False
        self.note.configure(text="")
        ids = ids + [cid] if on and cid not in ids else [i for i in ids if not (i == cid and not on)]
        set_picked(ids, self.app.ovr_cfg())
        row = self.all_rows.get(cid)
        if row:
            row[1].set(cid in ids)
        self.relayout_picked()
        self.app.ovr_refresh()
        return True

    def reorder(self, ids):
        set_picked(ids, self.app.ovr_cfg())
        self.relayout_picked()
        self.app.ovr_refresh()

    def pick_against(self):
        by_name = {self.name(c): c for c in self._against_ids()}
        set_against(by_name.get(self.vs.get(), "divine"), self.app.ovr_cfg())
        self.app.ovr_refresh()

    def paint_all(self):
        """Picks changed somewhere else, on the overlay: the ticks and the list follow, in place."""
        try:
            ids = set(picked(self.app.ovr_cfg()))
            for cid, (_row, v) in self.all_rows.items():
                if v.get() != (cid in ids):
                    v.set(cid in ids)
            self.relayout_picked()
        except tk.TclError:
            pass

    def after_idle(self, fn):
        try:
            self.win.after_idle(fn)
        except tk.TclError:
            pass

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.app.ovr_picker = None
