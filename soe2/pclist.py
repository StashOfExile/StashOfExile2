"""Price Checks › the list of your checks (UI overhaul): every item you priced, newest first, down the left of the
page - a search box first, then All / Rare / Unique / Other, then one row per check (its name in its rarity's color,
what it is and when, its price and how many listings it came from). Click a row to see it on the right.

Drawn on one canvas so it follows the theme pack. GGG ToS: looks only - nothing here touches the game."""
import time
import tkinter as tk

from . import buglog
from . import themes as TH
from .style import C

ROW_H = 58
KINDS = ("All", "Rare", "Unique", "Other")


def ago(t, now=None):
    s = max(0, int((now or time.time()) - (t or 0)))
    return "just now" if s < 60 else f"{s // 60} min ago" if s < 3600 else f"{s // 3600} h ago" if s < 86400 \
        else f"{s // 86400} d ago"


def kind_of(rec):
    r = ((rec.get("item") or {}).get("rarity") or "").title()
    return r if r in ("Rare", "Unique") else "Other"


def matches(rec, q, kind):
    if kind != "All" and kind_of(rec) != kind:
        return False
    if not q:
        return True
    it = rec.get("item") or {}
    words = f"{it.get('name') or ''} {it.get('base') or ''} {it.get('rarity') or ''}".lower()
    return all(p in words for p in q.lower().split())


class PCList(tk.Frame):
    """PCList(parent, app). .paint() after the checks or the shown one change."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["panel"])
        self.app, self.kind, self.hover, self._rows = app, "All", None, []
        top = tk.Frame(self, bg=C["panel"], padx=12, pady=12)
        top.pack(fill="x")
        self.q = tk.StringVar()
        box = tk.Frame(top, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        box.pack(fill="x")
        tk.Label(box, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        self.entry = tk.Entry(box, textvariable=self.q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                              relief="flat", font=("Segoe UI", 10), highlightthickness=0, bd=0)
        self.entry.pack(side="left", fill="x", expand=True, padx=8, ipady=8)
        self.ph = tk.Label(box, text="Search your checks", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 10))
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        for ev in ("<FocusIn>", "<FocusOut>"):
            self.entry.bind(ev, lambda e: self._ph(), add="+")
        self.q.trace_add("write", lambda *_: (self._ph(), self.paint()))
        self.entry.bind("<Escape>", lambda e: self.q.set(""))
        self.after(200, self._ph)
        self.chips = tk.Canvas(self, height=36, bg=C["panel"], highlightthickness=0, bd=0)
        self.chips.pack(fill="x", padx=12)
        self.chips.bind("<Button-1>", self._chip_click)
        self.chips.bind("<Configure>", lambda e: self._paint_chips())
        TH.self_painted(self.chips)
        self.cv = tk.Canvas(self, bg=C["panel"], highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True, pady=(4, 0))
        TH.self_painted(self.cv)
        from .style import overflow_scrollbar          # the thin round bar, only while the list is longer than the page
        self.sb = overflow_scrollbar(self.cv, inside=True)
        TH.subscribe(lambda t: self.paint(), owner=self)
        self.cv.bind("<Configure>", lambda e: self.paint())
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(None))
        self.cv.bind("<Button-1>", self._click)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(ev, self._wheel)
        self.count = tk.Label(self, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9), anchor="w", padx=12,
                              pady=8)
        self.count.pack(fill="x", side="bottom")

    def _ph(self):
        try:
            if self.q.get() or self.focus_get() is self.entry:
                self.ph.place_forget()
            else:
                self.ph.place(in_=self.entry, x=0, rely=0.5, anchor="w")
        except (tk.TclError, KeyError):
            pass

    # ---- All / Rare / Unique / Other
    def _paint_chips(self):
        t = TH.ST.theme
        cv = self.chips
        cv.delete("all")
        if t is None:
            return
        self._chip_hit = []
        x = 0
        from . import soft
        with TH.raw():
            chip = soft.chip_colors(t.c("surface"), t.c("text_muted"), t.c("text_strong"))
            for k in KINDS:
                on = k == self.kind
                tid = cv.create_text(0, 0, text=k, font=("Segoe UI", 9, "bold" if on else "normal"))
                w = cv.bbox(tid)[2] - cv.bbox(tid)[0] + 24
                cv.delete(tid)
                TH.round_rect(cv, x, 6, x + w, 30, 10, fill=chip["on" if on else "off"][0],
                              outline=t.c("accent") if on else chip["off"][1])
                cv.create_text(x + w / 2, 18, text=k, font=("Segoe UI", 9, "bold" if on else "normal"),
                               fill=t.c("text_strong") if on else t.c("text_muted"))
                self._chip_hit.append((x, x + w, k))
                x += w + 6

    def _chip_click(self, e):
        for x0, x1, k in getattr(self, "_chip_hit", []):
            if x0 <= e.x <= x1:
                self.kind = k
                self._paint_chips()
                self.paint()
                return

    # ---- rows
    def recs(self):
        try:
            return [r for r in self.app.pc_recs() if matches(r, self.q.get().strip(), self.kind)]
        except Exception:
            buglog.caught()
            return []

    def _wheel(self, e):
        step = (-1 if e.num == 4 else 1) if getattr(e, "num", None) in (4, 5) else (-1 if e.delta > 0 else 1)
        if len(self._rows) * ROW_H > self.cv.winfo_height():
            self.cv.yview_scroll(step * 2, "units")

    def _hit(self, e):
        y = self.cv.canvasy(e.y)
        i = int(y // ROW_H)
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def _motion(self, e):
        r = self._hit(e)
        self._set_hover(r["id"] if r else None)

    def _set_hover(self, rid):
        if rid != self.hover:
            self.hover = rid
            self.cv.configure(cursor="hand2" if rid is not None else "")
            self.paint()

    def _click(self, e):
        r = self._hit(e)
        if r is not None:
            try:
                (getattr(self.app, "pc_hist_open", None) or self.app.pc_show)(r)
            except Exception:
                buglog.caught()

    def paint(self):
        t = TH.ST.theme
        if t is None:
            return
        try:
            self._paint(t)
        except tk.TclError:
            pass

    def _paint(self, t):
        from .pricefmt import fmt_div
        cv = self.cv
        cv.delete("all")
        rows = self._rows = self.recs()
        w = max(cv.winfo_width(), 120)
        now = time.time()
        sel = getattr(self.app, "pc_rid", None)
        with TH.raw():
            bg = t.c("surface")
            cv.configure(bg=bg)
            rar = {"Unique": t.c("unique", "#af6025"), "Rare": t.c("rare", "#ffff77"), "Magic": t.c("magic", "#8f9bff")}
            txt, mut, strong = t.c("text"), t.c("text_muted"), t.c("text_strong")
            if not rows:
                total = len(self.app.pc_recs()) if hasattr(self.app, "pc_recs") else 0
                msg = ("Nothing matches. Clear the search or pick All." if total else
                       "Every item you price shows here, newest first.\nIn game: hover an item and press your price check key.")
                cv.create_text(12, 16, text=msg, anchor="nw", font=("Segoe UI", 9), fill=mut, width=w - 24)
            for i, r in enumerate(rows):
                y0 = i * ROW_H
                it = r.get("item") or {}
                on, hov = r.get("id") == sel, r.get("id") == self.hover
                if on or hov:
                    TH.round_rect(cv, 8, y0 + 2, w - 8, y0 + ROW_H - 2, 8,
                                  fill=t.c("selection") if on else t.c("hover", t.c("surface_high")), outline="")
                if on:
                    cv.create_rectangle(8, y0 + 12, 11, y0 + ROW_H - 12, fill=t.c("accent"), outline="")
                name = it.get("name") or it.get("base") or "item"
                price = (fmt_div(r["est"]) if r.get("est") is not None and not r.get("skip") else
                         "…" if r.get("state") in ("queued", "pricing") else "No price")
                pid = cv.create_text(w - 20, y0 + 18, text=price, anchor="e", font=("Segoe UI", 10, "bold"),
                                     fill=strong if price not in ("…", "No price") else mut)
                px = cv.bbox(pid)[0] - 12
                cv.create_text(24, y0 + 18, text=name, anchor="w", font=("Segoe UI", 10, "bold"),
                               fill=rar.get((it.get("rarity") or "").title(), txt), width=max(40, px - 24))
                sub = " ".join(v for v in ((it.get("rarity") or "").title(), it.get("base") if it.get("name") else "")
                               if v)
                cv.create_text(24, y0 + 40, text=f"{sub + ' · ' if sub else ''}{ago(r.get('time'), now)}", anchor="w",
                               font=("Segoe UI", 9), fill=mut)
                n = r.get("total") if r.get("total") is not None else len(r.get("prices") or [])
                if n:
                    cv.create_text(w - 20, y0 + 40, text=f"{n:,} listings", anchor="e", font=("Segoe UI", 9), fill=mut)
            cv.configure(scrollregion=(0, 0, w, max(len(rows) * ROW_H, cv.winfo_height())))
        allr = len(self.app.pc_recs()) if hasattr(self.app, "pc_recs") else 0
        self.count.config(text=f"{len(rows)} of {allr} checks" if len(rows) != allr else f"{allr} checks")
