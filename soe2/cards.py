"""Stat tiles (UI overhaul; 3.3.0: one titled panel, a column each): a row of numbers - a label, a big number, one line under it and an ⓘ that says how
the number was worked out (UX rule: "show how a number was worked out, one hover away at most"). Drawn on one canvas
from the theme pack, so they look the same on Dashboard, Wealth and anywhere else.

    tiles = StatTiles(parent); tiles.pack(fill="x")
    tiles.set([Tile("Stash worth", "412 div", "from 1,284 items", "muted", "How it was worked out")])

GGG ToS: looks only - nothing here touches the game."""
import tkinter as tk
from collections import namedtuple

from . import themes as TH

Tile = namedtuple("Tile", "label big foot foot_role how")
H, GAP, R = 112, 16, 12


class StatTiles(tk.Canvas):
    def __init__(self, parent, bg_role="surface", pad=(16, 16), h=H, title="At a Glance"):
        self.title = title                              # 3.3.0 look pass: one titled panel, a column for each number
        super().__init__(parent, height=h + pad[1] * 2 - 8 + self._top(), highlightthickness=0, bd=0)
        self.tiles, self.bg_role, self.pad, self.hover, self.h = [], bg_role, pad, None, h
        TH.self_painted(self)
        TH.subscribe(lambda t: self.redraw(), owner=self)
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._tip(None))

    def _top(self):
        """How far the numbers start under the panel's top edge: under its title."""
        t = TH.ST.theme
        if not self.title:
            return 0
        return TH.BOX_HEAD if t is None or TH.headed(t) else 44

    def set(self, tiles):
        tiles = list(tiles)
        if tiles != self.tiles:
            self.tiles = tiles
            self.redraw()

    def _motion(self, e):
        hit = None
        for i, (x0, y0, x1, y1) in enumerate(getattr(self, "_info", [])):
            if x0 - 6 <= e.x <= x1 + 6 and y0 - 6 <= e.y <= y1 + 6:
                hit = i
        self._tip(hit, e.x)

    def _tip(self, i, x=0):
        if i == self.hover:
            return
        self.hover = i
        self.delete("tip")
        if i is None or i >= len(self.tiles) or not self.tiles[i].how:
            return
        t = TH.ST.theme
        with TH.raw():
            tid = self.create_text(0, 0, text=self.tiles[i].how, anchor="nw", font=("Segoe UI", 9), fill=t.c("text"),
                                   width=260, tags="tip")
            bx = self.bbox(tid)
            w, h = bx[2] - bx[0] + 20, bx[3] - bx[1] + 14
            x = min(max(4, x - w // 2), self.winfo_width() - w - 4)
            y = 40 + self._top()
            TH.round_rect(self, x, y, x + w, y + h, 8, fill=t.c("surface_high"), outline=t.c("border_light"), tags="tip")
            self.coords(tid, x + 10, y + 7)
            self.tag_raise(tid)

    def redraw(self):
        t = TH.ST.theme
        if t is None:
            return
        self.delete("all")
        self._info, self.hover = [], None
        n = len(self.tiles)
        if not n:
            return
        W = max(self.winfo_width(), 200)
        px, py = self.pad
        top = self._top()
        cw = (W - 2 * px) / n
        with TH.raw():
            num = TH.head_font(t, "num")
            # 3.3.0 owner: the panel is as tall as the theme's number font needs, so the line under a number
            # never sits on it
            import tkinter.font as tkfont
            nfont = (num, 18 if self.h < H else (22 if cw > 180 else 18))
            ny = 28 if self.h < H else 36
            lines = tkfont.Font(root=self, font=nfont).metrics("linespace") + 1 + \
                tkfont.Font(root=self, font=("Segoe UI", 9)).metrics("linespace")
            h = max(self.h, ny + lines + 10)
            self.configure(bg=t.c(self.bg_role), height=h + py * 2 - 8 + top)
            mut, strong = t.c("text_muted"), t.c("text_strong")
            x0, y0 = px, py - 4
            TH.box(self, t, x0, y0, W - px, y0 + top + h, R)
            if self.title:
                TH.box_head(self, t, x0, y0, W - px, R, self.title)
            y0 += top
            for i, tl in enumerate(self.tiles):
                x0 = px + i * cw
                if i:
                    self.create_line(x0, y0 + 12, x0, y0 + h - 12, fill=t.c("border"))
                self.create_text(x0 + 18, y0 + 12, text=tl.label, anchor="nw", font=("Segoe UI", 10), fill=mut)
                if tl.how:
                    iid = self.create_text(x0 + cw - 18, y0 + 12, text="ⓘ", anchor="ne", font=("Segoe UI Symbol", 10),
                                           fill=mut)
                    self._info.append(self.bbox(iid))
                else:
                    self._info.append((-99, -99, -99, -99))
                big = tl.big if len(str(tl.big)) < 14 else str(tl.big)[:13] + "…"
                nid = self.create_text(x0 + 18, y0 + ny, text=big, anchor="nw", font=nfont,
                                       fill=strong if tl.big not in ("—", "") else mut)
                # 3.3.0 owner: the line under a number never sits on it, whatever the theme's font
                fid = self.create_text(x0 + 18, y0 + h - 10, text=tl.foot, anchor="sw", font=("Segoe UI", 9),
                                       fill=t.c(tl.foot_role or "text_muted", mut), width=cw - 36)
                nb, fb = self.bbox(nid), self.bbox(fid)
                if nb and fb and fb[1] < nb[3] + 1:
                    self.move(fid, 0, nb[3] + 1 - fb[1])
