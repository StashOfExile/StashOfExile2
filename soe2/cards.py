"""Stat tiles (UI overhaul): a row of number cards - a label, a big number, one line under it and an ⓘ that says how
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
    def __init__(self, parent, bg_role="surface", pad=(16, 16), h=H):
        super().__init__(parent, height=h + pad[1] * 2 - 8, highlightthickness=0, bd=0)
        self.tiles, self.bg_role, self.pad, self.hover, self.h = [], bg_role, pad, None, h
        TH.self_painted(self)
        TH.subscribe(lambda t: self.redraw(), owner=self)
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._tip(None))

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
            y = 40
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
        cw = (W - 2 * px - (n - 1) * GAP) / n
        with TH.raw():
            self.configure(bg=t.c(self.bg_role))
            num = TH.head_font(t, "num")
            mut, strong = t.c("text_muted"), t.c("text_strong")
            for i, tl in enumerate(self.tiles):
                x0, y0 = px + i * (cw + GAP), py - 4
                TH.round_rect(self, x0, y0, x0 + cw, y0 + self.h, R, fill=t.c("surface_raised"), outline=t.c("border"))
                self.create_text(x0 + 18, y0 + 16, text=tl.label, anchor="nw", font=("Segoe UI", 10), fill=mut)
                if tl.how:
                    iid = self.create_text(x0 + cw - 18, y0 + 16, text="ⓘ", anchor="ne", font=("Segoe UI Symbol", 10),
                                           fill=mut)
                    self._info.append(self.bbox(iid))
                else:
                    self._info.append((-99, -99, -99, -99))
                big = tl.big if len(str(tl.big)) < 14 else str(tl.big)[:13] + "…"
                self.create_text(x0 + 18, y0 + (30 if self.h < H else 38), text=big, anchor="nw", font=(num, 18 if self.h < H else (22 if cw > 180 else 18)),
                                 fill=strong if tl.big not in ("—", "") else mut)
                self.create_text(x0 + 18, y0 + self.h - 12, text=tl.foot, anchor="sw", font=("Segoe UI", 9),
                                 fill=t.c(tl.foot_role or "text_muted", mut), width=cw - 36)
