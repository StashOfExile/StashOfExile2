"""Dashboard (UI overhaul): the first page. Where you stand at a glance - stash worth, today's change, your last map,
today's price checks - three ways in for a new player, your last checks and which helpers are on.

Drawn on one canvas (cards, hairlines, one orange button) so it follows the theme pack exactly. Every number has
an ⓘ hover that says how it was worked out. GGG ToS: looks only - nothing here touches the game."""
import time
import tkinter as tk

from . import buglog
from . import themes as TH
from .config import SETTINGS

PAD, GAP, R = 32, 16, 12          # page margin, gap between cards, card corner
TILE_H, START_H, LIST_H = 116, 150, 252


def day_start(now=None):
    lt = time.localtime(now or time.time())
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))


def ago(t, now=None):
    s = max(0, int((now or time.time()) - t))
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60} min ago"
    if s < 86400:
        return f"{s // 3600} h ago"
    return f"{s // 86400} d ago"


def greeting(now=None):
    h = time.localtime(now or time.time()).tm_hour
    return "Good morning" if 5 <= h < 12 else "Good afternoon" if 12 <= h < 18 else "Good evening"


# ---------------------------------------------------------------- the numbers (each guarded: a page never breaks)
def wealth_numbers(now=None):
    """-> {total, today, n, series[(ts, total)]} for this league, or None before the first scan."""
    from .wealth import WEALTH
    lg = SETTINGS.get("league")
    snaps = [s for s in WEALTH.snapshots if not lg or s.get("league") == lg]
    if not snaps:
        return None
    last = snaps[-1]
    before = [s for s in snaps if s.get("ts", 0) < day_start(now)]
    base = before[-1]["total"] if before else snaps[0]["total"]
    cut = (now or time.time()) - 30 * 86400
    return {"total": last.get("total") or 0, "today": (last.get("total") or 0) - (base or 0), "n": last.get("n", 0),
            "ts": last.get("ts", 0), "series": [(s["ts"], s.get("total") or 0) for s in snaps if s.get("ts", 0) >= cut]}


def map_numbers(now=None):
    from . import mapprofit as MP
    es = MP.log_read(since=(now or time.time()) - 7 * 86400)
    if not es:
        return None
    t = MP.totals(es, now)
    last = max(es, key=lambda e: e.get("t", 0))
    return {"map": t["map"], "name": last.get("map") or "Map", "secs": last.get("secs", 0), "day": t["day"]}


def helper_rows():
    """The helpers you switch on yourself: (name, on)."""
    from . import features as FEAT
    out = []
    for key, (_d, _k, name) in FEAT.HELPER_SWITCHES.items():
        out.append((name, FEAT.helper_on(key)))
    return out


class Dashboard(tk.Canvas):
    def __init__(self, app, parent):
        super().__init__(parent, highlightthickness=0, bd=0)
        self.app = app
        self.acts, self.tips = {}, {}          # canvas tag -> what a click does / what its hover says
        self.hover, self._job, self._hooked, self._h = None, None, None, 0
        TH.self_painted(self)
        TH.subscribe(lambda t: self.redraw(), owner=self)
        self.bind("<Configure>", lambda e: self.later())
        app._drawer_look_hooks = getattr(app, "_drawer_look_hooks", []) + [lambda on: self.later()]
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)
        self.bind("<Map>", lambda e: self._hook(), add="+")

    # ---- scrolling (the wheel is caught on the window, as style.ScrollArea does)
    def _hook(self):
        top = self.winfo_toplevel()
        if self._hooked is top:
            return
        self._hooked = top
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(ev, self._wheel, add="+")

    def _wheel(self, e):
        try:
            if not self.winfo_ismapped() or self.winfo_containing(e.x_root, e.y_root) is not self:
                return
        except (tk.TclError, KeyError):
            return
        if self._h <= self.winfo_height():
            return
        step = (-1 if e.num == 4 else 1) if getattr(e, "num", None) in (4, 5) else (-1 if e.delta > 0 else 1)
        self.yview_scroll(step * 3, "units")

    # ---- mouse
    def _tag_at(self, e):
        x, y = self.canvasx(e.x), self.canvasy(e.y)
        for i in reversed(self.find_overlapping(x, y, x, y)):
            for tag in self.gettags(i):
                if tag in self.acts or tag in self.tips:
                    return tag
        return None

    def _motion(self, e):
        self._set_hover(self._tag_at(e), e)

    def _set_hover(self, tag, e=None):
        if tag == self.hover:
            return
        self.hover = tag
        self.configure(cursor="hand2" if tag in self.acts else "")
        self.redraw()
        if tag in self.tips and e is not None:
            self._tip(self.tips[tag], self.canvasx(e.x), self.canvasy(e.y))

    def _click(self, e):
        tag = self._tag_at(e)
        fn = self.acts.get(tag)
        if fn:
            try:
                fn()
            except Exception:
                buglog.caught()

    def _tip(self, text, x, y):
        t = TH.ST.theme
        f = ("Segoe UI", 9)
        tid = self.create_text(0, 0, text=text, anchor="nw", font=f, fill=t.c("text"), width=280, tags="tip")
        x0, y0, x1, y1 = self.bbox(tid)
        w, h = x1 - x0 + 20, y1 - y0 + 14
        x = min(max(8, x - w // 2), self.winfo_width() - w - 8)
        y = y + 18
        TH.round_rect(self, x, y, x + w, y + h, 8, fill=t.c("surface_high"), outline=t.c("border_light"), tags="tip")
        self.coords(tid, x + 10, y + 7)
        self.tag_raise(tid)

    # ---- drawing
    def later(self):
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        self._job = self.after(40, self.redraw)

    def redraw(self):
        self._job = None
        with TH.raw():
            try:
                self._draw()
            except Exception:
                buglog.caught()

    def _card(self, x0, y0, x1, y1, tag=None, lit=False):
        t = TH.ST.theme
        TH.round_rect(self, x0, y0, x1, y1, R, fill=t.c("hover", t.c("surface_high")) if lit else t.c("surface_raised"),
                      outline=t.c("border_light") if lit else t.c("border"), tags=(tag,) if tag else ())

    def _button(self, x1, y, text, tag, fn, primary=False, tip=None):
        """A button drawn right-aligned at x1. -> its left edge."""
        from .style import text_on
        t = TH.ST.theme
        f = ("Segoe UI", 10, "bold")
        probe = self.create_text(0, 0, text=text, font=f)
        tw = self.bbox(probe)[2] - self.bbox(probe)[0]
        self.delete(probe)
        x0, h = x1 - tw - 40, 44
        lit = self.hover == tag
        acc = t.c("accent")
        if primary:
            fill, line, ink = (TH.mix(acc, "#ffffff", .15) if lit else acc), acc, text_on(acc)
        else:
            fill, line, ink = (t.c("hover", t.c("surface_high")) if lit else t.c("surface")), t.c("border_light"), t.c("text")
        TH.round_rect(self, x0, y, x1, y + h, 10, fill=fill, outline=line, tags=(tag,))
        self.create_text((x0 + x1) // 2, y + h // 2, text=text, font=f, fill=ink, tags=(tag,))
        self.acts[tag] = fn
        if tip:
            self.tips[tag] = tip
        return x0

    def _draw(self):
        t = TH.ST.theme
        if t is None:
            return
        look = getattr(self.app, "drawer_look_on", None)
        PAD = 24 if look and look() else globals()["PAD"]     # drawer build: the Drawer's page margin (mockups.html)
        self.delete("all")
        self.acts, self.tips = {}, {}
        W = max(self.winfo_width(), 600)
        bg, head, num = t.c("surface"), TH.head_font(t), TH.head_font(t, "num")
        txt, mut, strong, acc, brass = t.c("text"), t.c("text_muted"), t.c("text_strong"), t.c("accent"), t.c("accent_2")
        good, bad = t.c("good"), t.c("bad")
        self.configure(bg=bg)
        from .pricefmt import fmt_div
        now = time.time()
        sh = getattr(self.app, "shell", None)

        def go(key):
            return lambda: sh.open(key) if sh else None

        try:
            wn = wealth_numbers(now)
        except Exception:
            buglog.caught()
            wn = None
        try:
            mn = map_numbers(now)
        except Exception:
            buglog.caught()
            mn = None
        try:
            recs = self.app.pc_recs() if hasattr(self.app, "pc_recs") else []
        except Exception:
            buglog.caught()
            recs = []
        today = [r for r in recs if r.get("time", 0) >= day_start(now)]

        # -- header: greeting, one line, the buttons
        y = PAD
        try:                                                 # your community name, if you gave one
            from . import board as B
            who = ((B.session().get("user") or {}).get("name") or "").strip() or "Exile"
        except Exception:
            who = "Exile"
        self.create_text(PAD, y, text=f"{greeting(now)}, {who}", anchor="nw", font=(head, 28), fill=strong)
        if wn:
            sub = f"Your stash is worth {fmt_div(wn['total'])}"
            sub += (f"  ·  ▲ up {fmt_div(wn['today'])} today" if wn["today"] > 0 else
                    f"  ·  ▼ down {fmt_div(-wn['today'])} today" if wn["today"] < 0 else "  ·  no change today")
        else:
            sub = "Where you stand, at a glance."
        sid = self.create_text(PAD, y + 50, text=sub, anchor="nw", font=("Segoe UI", 12), fill=mut)
        try:                                                 # UI overhaul: the usage count (usage.py), else
            from . import usage as US                        # the community count (About shows it too)
            uc = US.counts()
            if uc is None:
                from .communitymods import installs
                got = installs()
                uc = (None, got[1] if got and got[1] is not None else (got[0] if got else None)) if got else None
        except Exception:
            uc = None
        if uc and (uc[0] or uc[1]):
            online, week = uc
            label = f"{online:,} online now" if online else f"{week:,} this week"
            sx = self.bbox(sid)[2] + 20
            cy = y + 50 + 11
            tag = "community"
            lid = self.create_text(sx + 30, cy, text=label, anchor="w", font=("Segoe UI", 10), fill=txt, tags=(tag,))
            bx = self.bbox(lid)
            TH.round_rect(self, sx, cy - 14, bx[2] + 14, cy + 14, 14, fill=t.c("surface_raised"),
                          outline=t.c("border_light") if self.hover == tag else t.c("border"), tags=(tag,))
            hx = sx + 16                                     # a small person: head and shoulders
            self.create_oval(hx - 4, cy - 9, hx + 4, cy - 1, fill=brass, outline="", tags=(tag,))
            self.create_arc(hx - 8, cy + 1, hx + 8, cy + 15, start=0, extent=180, style="chord", fill=brass,
                            outline="", tags=(tag,))
            self.tag_raise(lid)
            others = max(0, (online or 0) - 1)
            self.tips[tag] = (f"{others:,} other people use Stash of Exile 2 right now" if online else
                              f"{week:,} people used Stash of Exile 2 this week") + \
                             (f" ({week:,} this week)." if online and week else ".")
        pc_key = SETTINGS.get("pc_key") or "Ctrl+D"
        x = self._button(W - PAD, y + 6, "Price Checks", "b_pc", go("pricecheck"), primary=True,
                         tip=f"In game: hover an item and press {pc_key}. Its price and listings show on Price Checks.")
        self._button(x - 12, y + 6, "Overlay", "b_ov", go("tracker"), tip="Over the game: the session timer and the helpers.")

        # -- four numbers
        y += 96
        look = getattr(self.app, "drawer_look_on", None)
        narrow = W < 900 or bool(look and look())            # D3: in the Drawer the tiles and Start cards wrap, 2 a row
        tcols = 2 if narrow else 4
        cw = (W - 2 * PAD - (tcols - 1) * GAP) / tcols
        y_tiles = y

        def tile(i, label, big, unit, foot, foot_col, how, key=None):
            x0 = PAD + (i % tcols) * (cw + GAP)
            ty = y_tiles + (i // tcols) * (TILE_H + GAP)
            tag = f"tile{i}"
            self._card(x0, ty, x0 + cw, ty + TILE_H, tag if key else None, lit=bool(key) and self.hover == tag)
            self.create_text(x0 + 18, ty + 16, text=label, anchor="nw", font=("Segoe UI", 10), fill=mut, tags=(tag,),
                             width=cw - 56)
            info = f"info{i}"
            self.create_text(x0 + cw - 18, ty + 16, text="ⓘ", anchor="ne", font=("Segoe UI Symbol", 10),
                             fill=brass if self.hover == info else mut, tags=(info,))
            self.tips[info] = how
            nid = self.create_text(x0 + 18, ty + 40, text=big, anchor="nw", font=(num, 28), fill=strong, tags=(tag,))
            if unit:
                bx = self.bbox(nid)
                self.create_text(bx[2] + 8, bx[3] - 8, text=unit, anchor="sw", font=("Segoe UI", 10), fill=brass, tags=(tag,))
            self.create_text(x0 + 18, ty + TILE_H - 14, text=foot, anchor="sw", font=("Segoe UI", 9), fill=foot_col,
                             tags=(tag,), width=cw - 36)
            if key:
                self.acts[tag] = go(key)

        if wn:
            tile(0, "Stash worth", fmt_div(wn["total"]), "", f"from {wn['n']:,} items · {ago(wn['ts'], now)}", mut,
                 "Every item from your last stash scan, each at the Middle of its listings, added up.", "wealth")
            d = wn["today"]
            tile(1, "Today", ("+" if d >= 0 else "−") + fmt_div(abs(d)), "",
                 "▲ Up" if d > 0 else "▼ Down" if d < 0 else "— No change", good if d > 0 else bad if d < 0 else mut,
                 "Stash worth now, minus your last scan before midnight (or your first scan today).", "wealth")
        else:
            tile(0, "Stash worth", "—", "", "Scan your stash on Wealth", mut,
                 "Shows after your first stash scan on the Wealth page.", "wealth")
            tile(1, "Today", "—", "", "After your first scan", mut, "Stash worth now, minus your last scan before "
                 "midnight.", "wealth")
        if mn and mn["map"] is not None:
            tile(2, "Last map", fmt_div(mn["map"]), "", f"{mn['name']} · {max(1, mn['secs'] // 60)} min", mut,
                 "Map profit: your inventory after the map, minus before - Currency Exchange items, priced by "
                 "poe.ninja.", "mapprofit")
        else:
            tile(2, "Last map", "—", "", "Shows after your next map", mut,
                 "Map profit: your inventory after a map, minus before. Its switch: Overlay › Helpers.", "mapprofit")
        priced = [r for r in today if r.get("est") is not None and not r.get("skip")]
        tile(3, "Items price checked today", str(len(today)), "", f"{len(priced)} with a price", mut,
             f"Items you priced with {pc_key} since midnight.", "pricecheck")

        # -- start here
        trows = -(-4 // tcols)
        y += trows * TILE_H + (trows - 1) * GAP + 36
        hid = self.create_text(PAD, y, text="Start here", anchor="nw", font=(head, 16), fill=strong)
        self.create_text(self.bbox(hid)[2] + 12, y + 4, text="Three things most players do first.", anchor="nw",
                         font=("Segoe UI", 10), fill=mut)
        y += 34
        # Round 18 (feedback: the three wrapped to 2 + 1 under the tiles): one row of three at Drawer and Full widths -
        # smaller text and padding when a card is narrow; two a row only on a truly narrow page
        scols = 3 if (W - 2 * PAD - 2 * GAP) / 3 >= 190 else 2 if W - 2 * PAD >= 380 else 1
        sw = (W - 2 * PAD - (scols - 1) * GAP) / scols
        tight = sw < 300                                     # (the Drawer's widths)
        ip, ic = (14, 28) if tight else (18, 34)             # inner padding, icon box
        sh = (150 if sw < 230 else 132) if tight else START_H
        tf, lf = (("Segoe UI", 10, "bold"), ("Segoe UI", 9)) if tight else (("Segoe UI", 12, "bold"), ("Segoe UI", 10))
        y_starts = y
        starts = (("Know what an item is worth", f"Hover an item in game and press {pc_key}.", "Price Checks →", "pricecheck"),
                  ("See what you have earned", "Press Scan stash. Each scan adds a point to your worth over time.", "Wealth →", "wealth"),
                  ("Get help while you play", "Helpers over the game: Ritual, Temple, Map profit.", "Overlay →", "tracker"))
        for i, (title, line, link, key) in enumerate(starts):
            x0 = PAD + (i % scols) * (sw + GAP)
            sy = y_starts + (i // scols) * (sh + GAP)
            tag = f"start{i}"
            lit = self.hover == tag
            self._card(x0, sy, x0 + sw, sy + sh, tag, lit)
            TH.round_rect(self, x0 + ip, sy + ip, x0 + ip + ic, sy + ip + ic, 8, fill=t.c("surface_sunken"),
                          outline=TH.mix(brass, t.c("surface_raised"), .6), tags=(tag,))
            self.create_text(x0 + ip + ic / 2, sy + ip + ic / 2, text=("◇", "◈", "◆")[i],
                             font=("Segoe UI Symbol", 10 if tight else 12), fill=brass, tags=(tag,))
            tid = self.create_text(x0 + ip + ic + 12, sy + ip + ic / 2, text=title, anchor="w", font=tf, fill=strong,
                                   width=sw - (ip + ic + 12) - ip, tags=(tag,))
            ly = max(sy + ip + ic, (self.bbox(tid) or (0, 0, 0, sy))[3]) + (10 if tight else 14)
            self.create_text(x0 + ip, ly, text=line, anchor="nw", font=lf, fill=mut, width=sw - 2 * ip, tags=(tag,))
            self.create_text(x0 + ip, sy + sh - (12 if tight else 16), text=link, anchor="sw",
                             font=(lf[0], lf[1], "bold"), fill=acc if lit else brass, tags=(tag,))
            self.acts[tag] = go(key)

        # -- your last checks / helpers
        srows = -(-3 // scols)
        y += srows * sh + (srows - 1) * GAP + GAP
        stack = bool(look and look())                       # the Drawer: one column - Pick up, then Helpers under it
        lw = (W - 2 * PAD) if stack else (W - 2 * PAD - GAP) * 0.62
        self._card(PAD, y, PAD + lw, y + LIST_H)
        self.create_text(PAD + 20, y + 18, text="Pick up where you left off", anchor="nw", font=(head, 16), fill=strong)
        self.create_text(PAD + lw - 20, y + 22, text="All Price Checks", anchor="ne", font=("Segoe UI", 10),
                         fill=acc if self.hover == "allpc" else brass, tags=("allpc",))
        self.acts["allpc"] = go("pricecheck")
        rows = recs[:4]
        ry = y + 56
        if not rows:
            self.create_text(PAD + 20, ry + 8, text=f"Your price checks show here. In game: hover an item, press {pc_key}.",
                             anchor="nw", font=("Segoe UI", 10), fill=mut, width=lw - 40)
        rar = {"Unique": t.c("unique", "#af6025"), "Rare": t.c("rare", "#ffff77"), "Magic": t.c("magic", "#8f9bff")}
        for i, r in enumerate(rows):
            it = r.get("item") or {}
            tag = f"rec{i}"
            self.create_line(PAD + 20, ry, PAD + lw - 20, ry, fill=t.c("border"))
            name = (it.get("name") or it.get("base") or "item")[:40]
            self.create_text(PAD + 20, ry + 10, text=name, anchor="nw", font=("Segoe UI", 10, "bold"),
                             fill=rar.get(it.get("rarity"), txt), tags=(tag,))
            kind = " ".join(v for v in (it.get("rarity"), it.get("base") if it.get("name") else "") if v)
            self.create_text(PAD + 20, ry + 28, text=f"{kind + ' · ' if kind else ''}{ago(r.get('time', now), now)}",
                             anchor="nw", font=("Segoe UI", 9), fill=mut, tags=(tag,))
            n = len(r.get("prices") or [])
            if r.get("est") is not None and not r.get("skip"):
                price = fmt_div(r["est"])
                self.tips[tag] = f"{n} listings · the Middle of them is {price}"
            else:
                price = "…" if r.get("state") in ("queued", "pricing") else "No price"
                self.tips[tag] = "Still pricing" if price == "…" else "No listings found"
            self.create_text(PAD + lw - 20, ry + 12, text=price, anchor="ne", font=("Segoe UI", 10, "bold"), fill=txt,
                             tags=(tag,))
            self.create_text(PAD + lw - 20, ry + 30, text=f"{n} listings" if n else "", anchor="ne",
                             font=("Segoe UI", 9), fill=mut, tags=(tag,))
            rid = r.get("id")
            self.acts[tag] = (lambda rid=rid: (sh.open("pricecheck") if sh else None,
                                               self.app.records.get(rid) and self.app.pc_show(self.app.records[rid])))
            ry += 48

        if stack:
            y += LIST_H + GAP
            hx0 = PAD
        else:
            hx0 = PAD + lw + GAP
        self._card(hx0, y, W - PAD, y + LIST_H)
        self.create_text(hx0 + 20, y + 18, text="Helpers", anchor="nw", font=(head, 16), fill=strong)
        # nav phase 2: every helper is on Overlay › Helpers (was the Overlay Settings page)
        self.create_text(W - PAD - 20, y + 22, text="All helpers", anchor="ne", font=("Segoe UI", 10),
                         fill=acc if self.hover == "ovhelpers" else brass, tags=("ovhelpers",))
        self.acts["ovhelpers"] = (lambda: sh.open_tab("tracker", "Helpers") if sh else None)
        try:
            hs = helper_rows()
        except Exception:
            buglog.caught()
            hs = []
        hy = y + 56
        for name, on in hs[:4]:
            self.create_line(hx0 + 20, hy, W - PAD - 20, hy, fill=t.c("border"))
            self.create_text(hx0 + 20, hy + 24, text=name, anchor="w", font=("Segoe UI", 10), fill=txt if on else mut)
            chip = "✓ On" if on else "– Off"
            col = good if on else mut
            cid = self.create_text(W - PAD - 32, hy + 24, text=chip, anchor="e", font=("Segoe UI", 9, "bold"), fill=col)
            bx = self.bbox(cid)
            TH.round_rect(self, bx[0] - 10, bx[1] - 4, bx[2] + 10, bx[3] + 4, 10, fill="",
                          outline=TH.mix(col, t.c("surface_raised"), .55))
            hy += 48

        self._h = y + LIST_H + PAD
        self.configure(scrollregion=(0, 0, W, self._h))
