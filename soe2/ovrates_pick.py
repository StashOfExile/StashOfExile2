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
HELP = "Pick the currencies to watch. Drag ⋮⋮ to change the order."


def picked(cfg=None):
    """The picked currency ids, in order. Never set yet: the overlay's old list, so nothing changes until you pick."""
    from .ovrates import COMMON
    c = cfg if cfg is not None else SETTINGS.setdefault("rates_ov", {})
    p = c.get("picked")
    if not isinstance(p, list):
        p = c["picked"] = list(COMMON)
    return p


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
        for i, (_k, _row, grip) in enumerate(self.rows):
            grip.configure(cursor="sb_v_double_arrow")
            grip.bind("<ButtonPress-1>", lambda e, i=i: self._press(i), add="+")
            grip.bind("<B1-Motion>", self._motion, add="+")
            grip.bind("<ButtonRelease-1>", self._release, add="+")

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
    with their ⋮⋮ grips; one line of help; Done."""

    def __init__(self, app):
        from .rates import RATES
        from .rates_view import Icons, picture_paths, url_for
        from .style import C, over_app
        self.app, self.C = app, C
        self.names = dict(getattr(RATES, "names", {}) or {})
        self.ids = sorted((c for c, v in (RATES.table or {}).items() if v), key=lambda c: self.name(c).lower())
        self.paths, self.url_for = picture_paths(), url_for
        self.icons = Icons(app.root, lambda: self.paint_all(), size=20)
        w = self.win = tk.Toplevel(app.root)
        w.title("Pick currencies")
        w.configure(bg=C["panel"])
        w.minsize(560, 420)
        top = tk.Frame(w, bg=C["panel"], padx=16, pady=12)
        top.pack(fill="x")
        tk.Label(top, text=HELP, bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x")
        cols = tk.Frame(w, bg=C["panel"], padx=16)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="pick")
        cols.columnconfigure(1, weight=1, uniform="pick")
        cols.rowconfigure(1, weight=1)
        # left: search first, then every currency
        sbox = tk.Frame(cols, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        sbox.grid(row=0, column=0, sticky="ew", padx=(0, 12), pady=(0, 8))
        tk.Label(sbox, text="⌕", bg=C["odd"], fg=C["muted"]).pack(side="left", padx=(8, 0))
        self.q = tk.StringVar()
        self.search = tk.Entry(sbox, textvariable=self.q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                               relief="flat", highlightthickness=0, bd=0)
        self.search.pack(side="left", fill="x", expand=True, padx=8, ipady=8)
        self.q.trace_add("write", lambda *a: self.paint_all())
        tk.Label(cols, text="Your currencies, in overlay order", bg=C["panel"], fg=C["muted"],
                 anchor="w").grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self.all_box = self._scroller(cols, 0)
        self.pick_box = self._scroller(cols, 1)
        bot = tk.Frame(w, bg=C["panel"], padx=16, pady=12)
        bot.pack(fill="x")
        ttk.Button(bot, text="Done", style="Primary.TButton", command=self.close).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", self.close)
        self.paint_all()
        try:
            over_app(w, app.root)
        except Exception:
            buglog.caught()
        self.search.focus_set()

    def name(self, cid):
        from .ovrates import cur_name
        return cur_name(cid, self.names)

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

        def wheel(e):
            n = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            cv.yview_scroll(n, "units")
        outer.bind("<Enter>", lambda e: [cv.bind_all(k, wheel) for k in ("<MouseWheel>", "<Button-4>", "<Button-5>")],
                   add="+")
        outer.bind("<Leave>", lambda e: [cv.unbind_all(k) for k in ("<MouseWheel>", "<Button-4>", "<Button-5>")],
                   add="+")
        return inner

    def _pic(self, cid):
        try:
            return self.icons.get(self.url_for(cid, self.paths))
        except Exception:
            return None

    def paint_all(self):
        try:
            self._paint_all()
            self._paint_picked()
        except tk.TclError:
            pass

    def _paint_all(self):
        C = self.C
        for c in self.all_box.winfo_children():
            c.destroy()
        mine = set(picked(self.app.ovr_cfg()))
        q = self.q.get().strip().lower()
        shown = [c for c in self.ids if not q or q in self.name(c).lower()]
        if not shown:
            tk.Label(self.all_box, text="No currency matches. Try fewer letters." if self.ids else
                     "No rates yet. They load from poe.ninja once your league is set.",
                     bg=C["odd"], fg=C["muted"], anchor="w", padx=8, pady=8).pack(fill="x")
        for cid in shown:
            row = tk.Frame(self.all_box, bg=C["odd"])
            row.pack(fill="x")
            v = tk.BooleanVar(value=cid in mine)
            cb = ttk.Checkbutton(row, variable=v, command=lambda c=cid, v=v: self.tick(c, v.get()))
            cb.pack(side="left", padx=(8, 4), pady=2)
            img = self._pic(cid)
            if img is not None:
                tk.Label(row, image=img, bg=C["odd"]).pack(side="left", padx=(0, 8))
            lab = tk.Label(row, text=self.name(cid), bg=C["odd"], fg=C["text"], anchor="w")
            lab.pack(side="left", fill="x", expand=True)
            lab.bind("<Button-1>", lambda e, c=cid, v=v: (v.set(not v.get()), self.tick(c, v.get())), add="+")

    def _paint_picked(self):
        C = self.C
        for c in self.pick_box.winfo_children():
            c.destroy()
        ids = picked(self.app.ovr_cfg())
        if not ids:
            tk.Label(self.pick_box, text="Nothing picked yet. Tick a currency on the left.", bg=C["odd"],
                     fg=C["muted"], anchor="w", padx=8, pady=8).pack(fill="x")
            return
        rows = []
        for cid in ids:
            row = tk.Frame(self.pick_box, bg=C["odd"])
            row.pack(fill="x")
            grip = tk.Label(row, text=GRIP, bg=C["odd"], fg=C["muted"], padx=8)
            grip.pack(side="left")
            from .style import Tooltip
            Tooltip(grip, "Drag to change the order")
            img = self._pic(cid)
            if img is not None:
                tk.Label(row, image=img, bg=C["odd"]).pack(side="left", padx=(0, 8))
            tk.Label(row, text=self.name(cid), bg=C["odd"], fg=C["text"], anchor="w").pack(side="left", fill="x",
                                                                                         expand=True, pady=4)
            x = tk.Label(row, text="✕", bg=C["odd"], fg=C["muted"], padx=8, cursor="hand2")
            x.pack(side="right")
            Tooltip(x, "Take it off the overlay")
            x.bind("<Button-1>", lambda e, c=cid: self.tick(c, False), add="+")
            rows.append((cid, row, grip))
        self.drag = DragList(self.pick_box, rows, self.reorder, line=C["accent"])

    def tick(self, cid, on):
        ids = picked(self.app.ovr_cfg())
        ids = ids + [cid] if on and cid not in ids else [i for i in ids if not (i == cid and not on)]
        set_picked(ids, self.app.ovr_cfg())
        self.app.ovr_refresh()
        self.paint_all()

    def reorder(self, ids):
        set_picked(ids, self.app.ovr_cfg())
        self.app.ovr_refresh()
        self.after_idle(self._paint_picked)

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
