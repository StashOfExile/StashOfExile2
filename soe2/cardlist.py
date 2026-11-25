"""A list of item cards drawn on ONE canvas (3.0.6, Game Search). Only the cards in view are drawn - never one widget
per row - so thousands of rows stay fast. Each card: the item's picture when the app has one, the name (bold) with its
kind under it, the properties as label / value pairs, a muted "Requires Level N", the mods or effects one per line
(numbers highlighted and bold), and tag chips in plain words. Data: gamecards.card(row)."""
import bisect
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import gamecards
from .style import C

PAD = 14
ICON = 44
LABEL_W = 150
CLOSED_LINES = 3


class CardList(tk.Frame):
    def __init__(self, parent, bg, art=None, on_toggle=None, on_wiki=None, on_more=None, on_report=None):
        super().__init__(parent, bg=bg)
        self.bg, self.art, self.on_toggle, self.on_wiki, self.on_more = bg, art, on_toggle, on_wiki, on_more
        self.on_report = on_report                           # 3.3.0 owner: Report a Problem on a result
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self._yview)
        self.sb.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollcommand=self._sb_set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.fonts = {
            "name": tkfont.Font(family="Segoe UI", size=12, weight="bold"),
            "kind": tkfont.Font(family="Segoe UI", size=9),
            "prop": tkfont.Font(family="Segoe UI", size=10),
            "propb": tkfont.Font(family="Segoe UI", size=10, weight="bold"),
            "line": tkfont.Font(family="Segoe UI", size=10),
            "num": tkfont.Font(family="Segoe UI", size=10, weight="bold"),
            "chip": tkfont.Font(family="Segoe UI", size=8),
            "link": tkfont.Font(family="Segoe UI", size=9, underline=True),
            "mono": tkfont.Font(family="Consolas", size=9),
        }
        self.rows, self.opened, self.more, self.terms = [], set(), 0, []
        self.tops, self.layouts, self.total, self.width = [], {}, 0, 0
        self.drawn = False
        self._hits = []
        self.canvas.bind("<Configure>", self._configure)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Motion>", self._motion)
        for ev in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):       # right click (Windows / Linux, macOS)
            self.canvas.bind(ev, self._menu)
        self._hooked = None
        self.bind("<Map>", lambda e: self._hook(), add="+")
        self.after_idle(self._hook)

    # ---------------------------------------------------------------- data
    def set_rows(self, rows, opened, more=0, terms=(), keep_scroll=False):
        y = self.canvas.yview()[0]
        self.rows, self.opened, self.more, self.terms = rows, opened, more, list(terms)
        self.layouts.clear()
        self._layout_all()
        self._redraw()
        self.canvas.yview_moveto(y if keep_scroll else 0)
        self._redraw()

    def refresh_art(self):
        """A picture arrived: lay out again (a card gets room for it) and redraw."""
        y = self.canvas.yview()[0]
        self.layouts.clear()
        self._layout_all()
        self.canvas.yview_moveto(y)
        self._redraw()

    def texts(self):
        """The words of every card (tests): name, kind, props, lines."""
        out = []
        for r in self.rows:
            c = gamecards.card(r)
            out += [r["n"], c["kind"], c["req"]] + [f"{a} {b}" for a, b in c["props"]] + c["lines"] + c["muted"] + c["chips"]
        return "\n".join(x for x in out if x)

    # ---------------------------------------------------------------- scrolling
    def _hook(self):
        top = self.winfo_toplevel()
        if self._hooked is top:
            return
        self._hooked = top
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(ev, self._wheel, add="+")

    def _over_me(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, KeyError):
            return False
        while w is not None:
            if w is self:
                return True
            w = w.master
        return False

    def _wheel(self, e):
        if not self.winfo_exists() or not self._over_me(e) or self.total <= self.canvas.winfo_height():
            return
        step = (-1 if e.num == 4 else 1) if getattr(e, "num", None) in (4, 5) else (-1 if e.delta > 0 else 1)
        self.canvas.yview_scroll(step * 3, "units")
        self._redraw()

    def _yview(self, *a):
        self.canvas.yview(*a)
        self._redraw()

    def _sb_set(self, a, b):
        self.sb.set(a, b)

    def _configure(self, e):
        if abs(e.width - self.width) > 2:
            self.width = e.width
            self.layouts.clear()
            self._layout_all()
        self._redraw()

    # ---------------------------------------------------------------- layout
    def _wrap(self, text, font, width, numbers=False):
        """-> [[(piece, is_number)]] lines that fit width."""
        segs = gamecards.segments(text) if numbers else [(text, False)]
        words = []
        for piece, isnum in segs:
            for i, w in enumerate(piece.split(" ")):
                words.append((w, isnum, i > 0 or (words and piece.startswith(" "))))
        lines, cur, x = [], [], 0
        space = font.measure(" ")
        for w, isnum, _sp in words:
            if w == "":
                continue
            f = self.fonts["num"] if isnum else font
            ww = f.measure(w)
            if cur and x + space + ww > width:
                lines.append(cur)
                cur, x = [], 0
            if cur:
                x += space
            cur.append((w, isnum, x))
            x += ww
        if cur:
            lines.append(cur)
        return lines

    def _layout_all(self):
        self.tops, y = [], 0
        for r in self.rows:
            self.tops.append(y)
            y += self._layout(r)["h"]
        self.more_y = y
        self.total = y + (36 if self.more else 0) + 8
        self.canvas.configure(scrollregion=(0, 0, max(self.width, 1), self.total))

    def _key(self, r):
        return r["n"] + "|" + r["g"] + "|" + r.get("id", "")

    def _layout(self, r):
        key = self._key(r)
        lay = self.layouts.get(key)
        if lay:
            return lay
        c = gamecards.card(r)
        opened = (r["n"] + "|" + r["g"]) in self.opened
        W = max(self.width, 400)
        img = self.art(r) if self.art else None
        x0 = PAD + (ICON + 10 if img else 0)
        right = W - PAD
        ops, hits, y = [], [], 10
        F = self.fonts
        ops.append(("text", x0, y, r["n"], F["name"], "text", "nw", {"hl": True}))
        # right side: the group, and the wiki link
        rx = right
        if not r.get("db") and r.get("n"):
            ww = F["link"].measure("wiki ›")
            ops.append(("text", rx, y + 3, "wiki ›", F["link"], "accent", "ne", {}))
            hits.append((rx - ww, y, rx, y + 20, ("wiki", r["n"])))
            rx -= ww + 12
        ops.append(("text", rx, y + 3, r["g"], F["kind"], "muted", "ne", {}))
        y += F["name"].metrics("linespace") + 2
        ops.append(("text", x0, y, c["kind"], F["kind"], "muted", "nw", {}))
        y += F["kind"].metrics("linespace") + 6
        state = {"y": y, "cut": False}

        def block_props():
            y = state["y"]
            vx = x0 + LABEL_W
            for lab, val in c["props"]:
                vl = self._wrap(val, F["prop"], max(80, right - vx))
                ops.append(("text", x0, y, lab, F["prop"], "muted", "nw", {}))
                for ln in vl or [[]]:
                    for w, _n, px in ln:
                        ops.append(("text", vx + px, y, w, F["propb"] if _n else F["prop"], "text", "nw", {}))
                    y += F["prop"].metrics("linespace") + 1
            if c["req"]:
                ops.append(("text", x0, y + 2, c["req"], F["kind"], "muted", "nw", {}))
                y += F["kind"].metrics("linespace") + 4
            state["y"] = y

        def block_lines():
            y = state["y"]
            if c["props"] or c["req"]:
                y += 2
            shown_lines, cut = 0, False
            all_lines = [(t, "text") for t in c["lines"]] + [(t, "muted") for t in c["muted"]]
            for t, col in all_lines:
                for ln in self._wrap(t, F["line"], right - x0, numbers=True):
                    if not opened and shown_lines >= CLOSED_LINES:
                        cut = True
                        break
                    for w, isnum, px in ln:
                        ops.append(("text", x0 + px, y, w, F["num"] if isnum else F["line"],
                                    "steel" if isnum and col == "text" else col, "nw", {}))
                    y += F["line"].metrics("linespace") + 1
                    shown_lines += 1
                if cut:
                    break
                y += 3
            state["y"], state["cut"] = y, cut

        for fn in ((block_lines, block_props) if c["db"] else (block_props, block_lines)):
            fn()
        y, cut = state["y"], state["cut"]
        # tags as chips
        chips = c["chips"] if opened else ([] if r.get("db") else c["chips"][:6])    # (a database row: its tags on open)
        if chips:
            y += 4
            cx, cy = x0, y
            for ch in chips:
                cw = F["chip"].measure(ch) + 14
                if cx + cw > right and cx > x0:
                    cx, cy = x0, cy + 22
                ops.append(("chip", cx, cy, cx + cw, cy + 18, ch, F["chip"], {}))
                cx += cw + 6
            y = cy + 22
        if opened and r.get("db"):
            y += 2
            v = r.get("v")
            ops.append(("text", x0, y, f"Source: {r['src']} · " + (f"Game {v}" if v and v != "none" else "no game version in the file"),
                        F["kind"], "muted", "nw", {}))
            y += F["kind"].metrics("linespace") + 1
            y += 2                                            # (the row id is in the right-click menu, not on the card)
        expandable = cut or opened or len(c["chips"]) > 6 or (r.get("db") and bool(c["chips"]))
        if expandable:
            label = "less ‹" if opened else "more ›"
            ww = F["link"].measure(label)
            ops.append(("text", x0, y + 2, label, F["link"], "accent", "nw", {}))
            hits.append((x0, y, x0 + ww + 6, y + 20, ("toggle", r["n"] + "|" + r["g"])))
            y += 24
        y = max(y, 10 + ICON + 6 if img else y) + 8
        if img:
            ops.append(("image", PAD, 12, img))
        ops.append(("rule", 0, y - 1, W, y - 1))
        lay = {"h": y, "ops": ops, "hits": hits}
        self.layouts[key] = lay
        return lay

    # ---------------------------------------------------------------- drawing
    def _redraw(self):
        cv = self.canvas
        cv.delete("all")
        self._hits = []
        if not self.rows and not self.more:
            return
        top = cv.canvasy(0)
        bottom = top + max(cv.winfo_height(), 200)
        i = max(0, bisect.bisect_right(self.tops, top) - 1)
        col = {"text": C["text"], "muted": C["muted"], "accent": C["accent"], "steel": C["steel"]}
        self._imgs = []
        while i < len(self.rows) and self.tops[i] <= bottom:
            r, ty = self.rows[i], self.tops[i]
            lay = self._layout(r)
            for op in lay["ops"]:
                k = op[0]
                if k == "text":
                    _k, x, y, s, f, c, anchor, _o = op
                    self._text(cv, x, ty + y, s, f, col[c], anchor, c in ("text", "steel"))
                elif k == "chip":
                    _k, x1, y1, x2, y2, s, f, _o = op
                    cv.create_rectangle(x1, ty + y1, x2, ty + y2, fill=C["panel"], outline=C["line"])
                    cv.create_text((x1 + x2) / 2, ty + (y1 + y2) / 2, text=s, font=f, fill=C["muted"])
                elif k == "image":
                    _k, x, y, im = op
                    cv.create_image(x, ty + y, image=im, anchor="nw")
                    self._imgs.append(im)
                elif k == "rule":
                    _k, x1, y1, x2, y2 = op
                    cv.create_line(x1, ty + y1, x2, ty + y2, fill=C["line"])
            for x1, y1, x2, y2, act in lay["hits"]:
                self._hits.append((x1, ty + y1, x2, ty + y2, act))
            i += 1
        if self.more:
            n = min(60, self.more)
            s = f"Show {n} more"
            w = self.fonts["link"].measure(s)
            y = self.more_y + 8
            cv.create_text(PAD, y, text=s, font=self.fonts["link"], fill=C["accent"], anchor="nw")
            self._hits.append((PAD, y, PAD + w, y + 20, ("more", None)))

    def _text(self, cv, x, y, s, f, fill, anchor, mark):
        """One piece of text; a search word in it gets a filled box behind just those letters."""
        low = s.lower()
        hit = min([(low.find(t), t) for t in self.terms if mark and t in low] or [(-1, "")])
        if hit[0] < 0 or anchor != "nw":
            cv.create_text(x, y, text=s, font=f, fill=fill, anchor=anchor)
            return
        i, t = hit
        pre, mid = s[:i], s[i:i + len(t)]
        x1 = x + f.measure(pre)
        x2 = x1 + f.measure(mid)
        cv.create_rectangle(x1, y, x2, y + f.metrics("linespace"), fill=C["accent"], outline="")
        if pre:
            cv.create_text(x, y, text=pre, font=f, fill=fill, anchor="nw")
        cv.create_text(x1, y, text=mid, font=f, fill=C["bg"], anchor="nw")
        if s[i + len(t):]:
            cv.create_text(x2, y, text=s[i + len(t):], font=f, fill=fill, anchor="nw")

    def _at(self, e):
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        for x1, y1, x2, y2, act in self._hits:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return act
        return None

    def row_at(self, e):
        """The row under a mouse event (canvas coordinates), or None."""
        y = self.canvas.canvasy(e.y)
        i = bisect.bisect_right(self.tops, y) - 1
        if 0 <= i < len(self.rows) and y < self.tops[i] + self._layout(self.rows[i])["h"]:
            return self.rows[i]
        return None

    def _menu(self, e):
        """Right click on a card: Report a Problem; on a database card also copy its row id (for gamedb_hide.json)."""
        r = self.row_at(e)
        if not r or not (self.on_report or (r.get("db") and r.get("id"))):
            return
        from .listkit import _menu
        m = _menu(self.canvas)
        if self.on_report:
            m.add_command(label="Report a Problem…", command=lambda: self.on_report(r))
        if r.get("db") and r.get("id"):
            m.add_command(label="Copy id for the hide list", command=lambda: self.copy_id(r["id"]))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def copy_id(self, rid):
        self.clipboard_clear()
        self.clipboard_append(rid)

    def _click(self, e):
        act = self._at(e)
        if not act:
            return
        kind, arg = act
        if kind == "toggle" and self.on_toggle:
            self.on_toggle(arg)
        elif kind == "wiki" and self.on_wiki:
            self.on_wiki(arg)
        elif kind == "more" and self.on_more:
            self.on_more()

    def _motion(self, e):
        self.canvas.config(cursor="hand2" if self._at(e) else "")
