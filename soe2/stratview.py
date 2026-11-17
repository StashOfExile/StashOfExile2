"""Farming Strategies (3.0.6): Find (the list) and an opened strat, each drawn on one canvas - cards, chips, the
tablet pictures, one orange button - so the page follows the theme pack and stays light in the Drawer (a few hundred
canvas items instead of hundreds of frames and labels: the Drawer's resize lag).

Every number has an ⓘ (or its own hover) saying how it was worked out. State is never color alone: a mark and a word
(▲ / ▼, ✓ Picked, ◆ you). Data: moneymakers.py (per_hour, run_cost, run_profit, run_time); the pictures:
pricecheck_page.icons() / pc_art (the game's tablet for each strat's mechanic; none -> the word alone).
GGG ToS: looks only - nothing here reads the screen or the clipboard."""
import re
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import themes as TH
from . import moneymakers as MM
from .config import SETTINGS

R = 10                                  # card corner
NARROW = 760                            # below this width (or in the Drawer): the compact rows
MECH_COL = {"Breach": "purple", "Ritual": "bad", "Expedition": "link", "Delirium": "text_soft", "Abyss": "good",
            "Temple": "orange", "Overseer": "warn"}
MARKS = ("▲", "●", "■", "◆", "✦")       # Where your money came from: a mark and a word for each part


class StratCanvas(tk.Canvas):
    """A canvas page: draw(cv) paints it; tags carry what a click (acts), a double-click (dbl), a right-click (menus)
    and a hover (tips, lifts) do. The wheel scrolls it; a scroll bar shows only when it is taller than the view."""

    def __init__(self, parent, app, draw):
        super().__init__(parent, highlightthickness=0, bd=0)
        self.app, self.draw_fn = app, draw
        self.acts, self.dbl, self.menus, self.tips, self.lifts = {}, {}, {}, {}, {}
        self.primaries = []                     # the orange buttons drawn (one a screen - tests check it)
        self.hover, self._job, self._hooked, self._h, self._width = (), None, None, 0, 0
        self.want = set()                       # picture URLs this page waits for
        self.sb = None
        self._probe = {}
        TH.self_painted(self)
        TH.subscribe(lambda t: self.later(), owner=self)
        self.bind("<Configure>", self._cfg)
        self.bind("<Motion>", lambda e: self._set_hover(self._tags_at(e), e))
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", lambda e: self._fire(self.acts, e))
        self.bind("<Double-Button-1>", lambda e: self._fire(self.dbl, e))
        self.bind("<Button-3>", self._rclick)
        self.bind("<Map>", lambda e: self._hook(), add="+")

    # ---- scrolling
    def attach_scrollbar(self, sb):
        self.sb = sb
        self.configure(yscrollcommand=self._sb_set)

    def _sb_set(self, a, b):
        sb = self.sb
        if sb is None:
            return
        try:
            sb.set(a, b)
            need = float(a) > 0.0 or float(b) < 1.0
            if need and not sb.winfo_manager():
                sb.pack(side="right", fill="y", before=self)
            elif not need and sb.winfo_manager():
                sb.pack_forget()
        except tk.TclError:
            pass

    def _hook(self):
        top = self.winfo_toplevel()
        if self._hooked is top:
            return
        self._hooked = top
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            top.bind(ev, self._wheel, add="+")

    def _wheel(self, e):
        try:
            under = self.winfo_containing(e.x_root, e.y_root)
            if not self.winfo_ismapped() or (under is not self and getattr(under, "master", None) is not self):
                return                                  # (a field drawn on the page - New strat - scrolls it too)
        except (tk.TclError, KeyError):
            return
        if self._h <= self.winfo_height():
            return
        step = (-1 if e.num == 4 else 1) if getattr(e, "num", None) in (4, 5) else (-1 if e.delta > 0 else 1)
        self.delete("tip")
        self.yview_scroll(step * 3, "units")

    # ---- the mouse
    def _tags_at(self, e):
        """The tags that do something on the topmost item under the mouse (a row and its number: both)."""
        x, y = self.canvasx(e.x), self.canvasy(e.y)
        for i in reversed(self.find_overlapping(x, y, x, y)):
            tags = tuple(t for t in self.gettags(i) if t in self.acts or t in self.tips or t in self.menus
                         or t in self.dbl or t in self.lifts)
            if tags:
                return tags
        return ()

    def _set_hover(self, tags, e=None):
        tags = tuple(tags or ())
        if tags == self.hover:
            return
        old, self.hover = self.hover or (), tags
        for t in old:
            if t not in tags:
                self._light(t, False)
        for t in tags:
            self._light(t, True)
        self.configure(cursor="hand2" if any(t in self.acts for t in tags) else "")
        self.delete("tip")
        tip = next((self.tips[t] for t in tags if self.tips.get(t)), None)
        if tip and e is not None:
            self._tip(tip, self.canvasx(e.x), self.canvasy(e.y))

    def _light(self, tag, on):
        for item, normal, lit in self.lifts.get(tag, ()):
            try:
                self.itemconfigure(item, **(lit if on else normal))
            except tk.TclError:
                pass

    def _fire(self, table, e):
        fn = next((table[t] for t in self._tags_at(e) if t in table), None)
        if fn:
            self.delete("tip")
            try:
                fn()
            except Exception:
                buglog.caught()

    def _rclick(self, e):
        fn = next((self.menus[t] for t in self._tags_at(e) if t in self.menus), None)
        if fn:
            try:
                fn(e.x_root, e.y_root)
            except Exception:
                buglog.caught()

    def at_root(self, tag):
        """Where a drawn thing is on the screen: (x, y under it) - for a menu that drops from it."""
        b = self.bbox(tag)
        if not b:
            return self.winfo_rootx(), self.winfo_rooty()
        return (int(self.winfo_rootx() + b[0] - self.canvasx(0)), int(self.winfo_rooty() + b[3] - self.canvasy(0)))

    def _tip(self, text, x, y):
        t = TH.ST.theme
        with TH.raw():
            tid = self.create_text(0, 0, text=text, anchor="nw", font=("Segoe UI", 9), fill=t.c("text"), width=300,
                                   tags="tip")
            x0, y0, x1, y1 = self.bbox(tid)
            w, h = x1 - x0 + 20, y1 - y0 + 14
            x = min(max(8, x - w // 2), max(8, self.winfo_width() - w - 8))
            top = self.canvasy(0)
            y = y + 18 if y + 18 + h < top + self.winfo_height() else y - h - 12
            TH.round_rect(self, x, y, x + w, y + h, 8, fill=t.c("surface_high"), outline=t.c("border_light"),
                          tags="tip")
            self.coords(tid, x + 10, y + 7)
            self.tag_raise(tid)

    # ---- drawing
    def _cfg(self, e):
        if e.width != self._width:
            self._width = e.width
            self.later()

    def later(self, ms=40):
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        try:
            self._job = self.after(ms, self.redraw)
        except tk.TclError:
            self._job = None

    def redraw(self):
        self._job = None
        try:
            if TH.ST.theme is None or not self.winfo_exists():
                return
        except tk.TclError:
            return                                  # (gone with its page)
        keep = self.hover or ()
        self.delete("all")
        self.acts, self.dbl, self.menus, self.tips, self.lifts = {}, {}, {}, {}, {}
        self.primaries = []
        self.hover = ()
        with TH.raw():
            try:
                self.configure(bg=self.c("surface"))
                self._h = int(self.draw_fn(self) or 0)
            except Exception:
                buglog.caught()
        self.configure(scrollregion=(0, 0, max(1, self.winfo_width()), max(self._h, 1)))
        self.hover = tuple(t for t in keep if t in self.lifts)
        for t in self.hover:
            self._light(t, True)

    # ---- pieces
    def c(self, role, fallback=None):
        t = TH.ST.theme
        return t.c(role, t.c(fallback) if fallback else "#ff00ff")

    def tw(self, text, font):
        """How wide a text is in this font (px)."""
        key = (text, font)
        if key not in self._probe:
            i = self.create_text(-999, -999, text=text, font=font, anchor="nw")
            b = self.bbox(i)
            self.delete(i)
            self._probe[key] = (b[2] - b[0]) if b else 0
            if len(self._probe) > 4000:
                self._probe.clear()
        return self._probe[key]

    def fit(self, text, font, w):
        """The text cut to w px (with …)."""
        if self.tw(text, font) <= w:
            return text
        while text and self.tw(text + "…", font) > w:
            text = text[:-1]
        return text.rstrip() + "…"

    def text(self, x, y, text, font=("Segoe UI", 10), fill=None, anchor="nw", width=None, tags=()):
        kw = {"width": width} if width else {}
        return self.create_text(x, y, text=text, font=font, fill=fill or self.c("text"), anchor=anchor,
                                tags=tags, **kw)

    def bottom(self, item, default=0):
        b = self.bbox(item)
        return b[3] if b else default

    def card(self, x0, y0, x1, y1, tag=None, fill=None, outline=None, lift=True, r=R, width=1):
        fill = fill or self.c("surface_raised")
        outline = outline or self.c("border")
        i = TH.round_rect(self, x0, y0, x1, y1, r, fill=fill, outline=outline, width=width,
                          tags=(tag,) if tag else ())
        if tag and lift:
            lit = {"fill": TH.mix(fill, self.c("text_strong"), .04), "outline": self.c("border_light")}
            self.lifts.setdefault(tag, []).append((i, {"fill": fill, "outline": outline}, lit))
        return i

    def icon(self, base, x, y, px, anchor="nw", tags=()):
        """The trade site's picture of an item (base) at x, y - or None when there is none (yet): the caller shows
        the word alone."""
        try:
            from .pricecheck_page import art_url
            url = art_url(base)
            img = self.app.pc_art(url, px) if url and hasattr(self.app, "pc_art") else None
        except Exception:
            buglog.caught()
            return None
        if url and img is None:
            self.want.add(url)
        if img is None:
            return None
        return self.create_image(x, y, image=img, anchor=anchor, tags=tags)

    def chip(self, x, y, text, role="text_muted", base=None, tags=(), h=22):
        """A tag: [picture] word, in a thin box. -> its right edge."""
        f = ("Segoe UI", 9)
        col = self.c(role, "text_muted")
        box = TH.round_rect(self, x, y, x + 1, y + h, 4, fill=TH.mix(self.c("surface_raised"), col, .08),
                            outline=TH.mix(col, self.c("surface_raised"), .45), tags=tags)
        ix = x + 8
        if base and self.icon(base, ix - 2, y + h // 2, 16, anchor="w", tags=tags) is not None:
            ix += 18
        tid = self.text(ix, y + h // 2, text, f, fill=col if role != "text_muted" else self.c("text"), anchor="w",
                        tags=tags)
        x1 = (self.bbox(tid) or (0, 0, ix, 0))[2] + 8
        self.coords(box, *_rr_points(x, y, x1, y + h, 4))
        return x1

    def pips(self, x, y, n, total=5, tags=()):
        """Effort as filled bars (a mark) - the word goes beside it. -> right edge."""
        on, off = self.c("text"), self.c("border_light")
        for i in range(total):
            x0 = x + i * 6
            self.create_rectangle(x0, y, x0 + 4, y + 11, fill=on if i < n else "", outline=on if i < n else off,
                                  tags=tags)
        return x + total * 6

    def info(self, x, y, tag, how, anchor="w", tags=()):
        """An ⓘ that says how a number was worked out. -> right edge."""
        i = self.text(x, y, "ⓘ", ("Segoe UI Symbol", 9), fill=self.c("text_muted"), anchor=anchor,
                      tags=(tag,) + tuple(tags))
        self.tips[tag] = how
        self.lifts.setdefault(tag, []).append((i, {"fill": self.c("text_muted")}, {"fill": self.c("accent_2")}))
        return (self.bbox(i) or (0, 0, x, 0))[2]

    def button(self, x, y, text, tag, fn, kind="ghost", enabled=True, tip=None, h=34, anchor="w", w=None):
        """A button drawn on the canvas: kind primary (the one orange button) or ghost (outlined). anchor "e": x is
        its right edge. -> (x0, x1)."""
        from .style import text_on
        f = ("Segoe UI", 10, "bold" if kind == "primary" else "normal")
        bw = w or self.tw(text, f) + 32
        x0 = x - bw if anchor == "e" else x
        x1 = x0 + bw
        acc = self.c("accent")
        if kind == "primary" and enabled:
            self.primaries.append(text)
            fill, line, ink = acc, acc, text_on(acc)
            lit = {"fill": TH.mix(acc, "#ffffff", .15)}
        else:
            fill, line = self.c("surface"), self.c("border_light")
            ink = self.c("text") if enabled else self.c("text_muted")
            lit = {"fill": self.c("surface_high"), "outline": self.c("text_muted")}
        b = TH.round_rect(self, x0, y, x1, y + h, 8, fill=fill, outline=line if enabled else self.c("border"),
                          tags=(tag,))
        self.text((x0 + x1) / 2, y + h / 2, text, f, fill=ink, anchor="center", tags=(tag,))
        if enabled:
            self.acts[tag] = fn
            self.lifts.setdefault(tag, []).append((b, {"fill": fill, "outline": line}, dict(lit, outline=lit.get(
                "outline", line))))
        if tip:
            self.tips[tag] = tip
        return x0, x1

    def range_bar(self, x0, x1, y, ph, tags=()):
        """low - high of the estimate, its middle (|) and you (◆): marks, never color alone."""
        lo, hi, mid, you = ph["low"], ph["high"], ph["value"], ph.get("you")
        vals = [v for v in (lo, hi, mid, you) if v is not None]
        a, b = min(vals), max(vals)
        span = (b - a) or max(abs(b), 1) * 0.5
        a, b = a - span * 0.15, b + span * 0.15

        def X(v):
            return x0 + (x1 - x0) * (v - a) / (b - a)
        money, mute = self.c("money"), self.c("surface_high")
        self.create_line(x0, y, x1, y, fill=mute, width=3, tags=tags)
        if hi > lo:
            self.create_line(X(lo), y, X(hi), y, fill=TH.mix(money, self.c("surface_raised"), .45), width=3, tags=tags)
        self.create_line(X(mid), y - 7, X(mid), y + 7, fill=money, width=2, tags=tags)
        if you is not None:
            cx = X(you)
            self.create_polygon(cx, y - 7, cx + 7, y, cx, y + 7, cx - 7, y, fill=self.c("link"),
                                outline=self.c("surface_raised"), tags=tags)


# ======================================================================== the page's drawings (mixed into App)
class StratViews:
    def mm_narrow(self, cv=None):
        look = getattr(self, "drawer_look_on", None)
        try:
            on = bool(look and look())
        except Exception:
            on = False
        try:
            w = (cv or self.mm_find_cv).winfo_width()
        except (AttributeError, tk.TclError):
            w = 1000
        return on or 1 < w < NARROW

    # ------------------------------------------------------------------ Find
    def _mm_draw_find(self, cv):
        W = max(cv.winfo_width(), 300)
        narrow = self.mm_narrow(cv)
        pad = 16 if narrow else 24
        rows = getattr(self, "mm_find_rows", [])
        total = sum(1 for s in getattr(self, "mm_strats", []) if MM.is_farming(s))      # (farming only - 3.0.6)
        y = 12
        if not rows:
            y = self._mm_empty_card(cv, pad, y, W, bool(total))
        else:
            more = rows                                  # (owner: no "Best for you right now" card - one list)
            on = self.mm_filters_on()
            words = self.mm_filter_words().upper()      # 3.0.6: FORBIDDEN RITES · MID BUDGET · 5 OF 8
            line = (f"{words} · " if words else "STRATS · ") + f"{len(more)} OF {total}"
            room = W - 2 * pad - (90 if on else 0)
            cv.text(pad, y, cv.fit(line, ("Segoe UI", 9, "bold"), room), ("Segoe UI", 9, "bold"),
                    fill=cv.c("text_muted"), anchor="w")
            if on:
                i = cv.text(W - pad, y, "Clear filters", ("Segoe UI", 9), fill=cv.c("link"), anchor="e",
                            tags=("clear",))
                cv.acts["clear"] = self.mm_clear_filters
                cv.lifts["clear"] = [(i, {"fill": cv.c("link")}, {"fill": cv.c("accent")})]
            y += 16
            vmax = max([r["ph"]["value"] for r in rows if r["ph"]] or [1]) or 1
            if not more:
                cv.text(pad, y + 8, "No strats match.", ("Segoe UI", 9), fill=cv.c("text_muted"))
                y += 28
            for i, r in enumerate(more):
                y = (self._mm_row_narrow if narrow else self._mm_row)(cv, r, i, pad, y, W, vmax) + 8
        y = self._mm_tips_draw(cv, pad, y + 16, W, narrow)
        return y + pad

    def _mm_empty_card(self, cv, pad, y, W, filtered):
        """Empty state: what it is, and one button."""
        view = self.mm_view.get()
        from . import board as B
        lg = self.mm_league.get() if hasattr(self, "mm_league") else MM.ALL_LEAGUES
        only_league = filtered and lg != MM.ALL_LEAGUES and not self.mm_filters_on_but_league()
        if only_league:                                  # 3.0.6: nothing for your league yet
            head, body, btn, fn = (f"No strats for {lg} yet", "Strats for other leagues show under All leagues.",
                                   MM.ALL_LEAGUES, lambda: self.mm_league_set(MM.ALL_LEAGUES))
        elif filtered:
            head, body, btn, fn = ("No strats match", "Nothing here fits the search and filters.", "Clear filters",
                                   self.mm_clear_filters)
        elif view == "Mine":
            head, body, btn, fn = ("No strats of your own yet", "Write down how you farm - it stays on this PC until "
                                   "you post it.", "＋ New strat", self.mm_add)
        elif view == "Community":
            if B.configured():
                head, body, btn, fn = ("No community strats yet", "Strats other players posted show here.",
                                       "↻ Refresh", self.mm_refresh)
            else:
                head, body, btn, fn = ("The community board isn't set up yet", "Official strats come with the app.",
                                       "Show Official strats", lambda: self.mm_view_set("Official"))
        else:
            head, body, btn, fn = ("No strats yet", "Farming strats come from the shared list on GitHub.",
                                   "↻ Check for strats", self.mm_refresh)
        h = 150
        cv.card(pad, y, W - pad, y + h, lift=False)
        cv.text(W / 2, y + 34, head, ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="center")
        cv.text(W / 2, y + 60, body, ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="center", width=W - 2 * pad - 40)
        bw = cv.tw(btn, ("Segoe UI", 10)) + 32
        cv.button(W / 2 - bw / 2, y + 90, btn, "empty_btn", fn)
        return y + h

    def _mm_mech_chip(self, cv, x, y, s, tags=()):
        mech = MM.mechanic(s)
        return cv.chip(x, y, s.get("type") or s.get("category", ""), MECH_COL.get(mech, "money"), MM.tablet_of(s),
                       tags=tags)

    def _mm_effort(self, cv, x, y, s, tags=()):
        n = s.get("thoughts_per_click") or 0
        x = cv.pips(x, y - 5, n, tags=tags)
        word, why = MM.THINKING.get(n, ("?", ""))
        cv.text(x + 6, y, word, ("Segoe UI", 9), fill=cv.c("text"), anchor="w", tags=tags)
        return x + 6 + cv.tw(word, ("Segoe UI", 9))

    def _mm_row(self, cv, r, i, pad, y, W, vmax):
        s, ph, key = r["s"], r["ph"], r["key"]
        tag = f"row{i}"
        x0, x1, h = pad, W - pad, 76
        cv.card(x0, y, x1, y + h, tag)
        cv.acts[tag] = lambda k=key: self.mm_open(k)
        cv.menus[tag] = lambda X, Y, k=key: self.mm_row_menu(k, X, Y)
        cv.icon(MM.tablet_of(s), x0 + 16, y + h / 2, 44, anchor="w", tags=(tag,))
        tx = x0 + 74
        # right to left: chevron, per hour, cost a run, effort
        cv.text(x1 - 18, y + h / 2, "›", ("Segoe UI", 16), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
        bw = 220 if W > 1100 else 170
        px1 = x1 - 40
        px0 = px1 - bw
        lab = cv.text(px0, y + 18, "PER HOUR", ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="w",
                      tags=(tag,))
        how = ph["how"] if ph else "No estimate given."
        cv.info(cv.bbox(lab)[2] + 5, y + 18, f"{tag}_i", how, tags=(tag,))
        if ph:
            cv.text(px1, y + 18, MM.short_div(ph["value"]) + " div", (TH.head_font(None, "num"), 16),
                    fill=cv.c("money"), anchor="e", tags=(tag, f"{tag}_v"))
            cv.tips[f"{tag}_v"] = how
            frac = max(0.02, min(1.0, ph["value"] / vmax))
            cv.create_rectangle(px0, y + 38, px1, y + 42, fill=cv.c("surface_high"), outline="", tags=(tag,))
            cv.create_rectangle(px0, y + 38, px0 + (px1 - px0) * frac, y + 42, fill=cv.c("money"), outline="",
                                tags=(tag,))
        else:
            cv.text(px1, y + 18, "no estimate", ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
        mine = r.get("mine")
        if mine and mine.get("per_hour") is not None:
            cv.text(px0, y + 56, f"◆ you {MM.short_div(mine['per_hour'])} div", ("Segoe UI", 9), fill=cv.c("link"),
                    anchor="w", tags=(tag,))
        if ph:
            cv.text(px1, y + 56, ph["count"], ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
        cx1 = px0 - 28
        cost = r.get("cost")
        cv.text(cx1, y + 26, "COST / MAP", ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
        cv.text(cx1, y + 48, f"{MM.short_div(cost['value'])} div" if cost else "-", ("Segoe UI", 10),
                fill=cv.c("text"), anchor="e", tags=(tag, f"{tag}_c"))
        if cost:
            cv.tips[f"{tag}_c"] = f"{cost['sum']}. {cost['how']}"
        left_end = cx1 - 90
        if W > 980:
            ex1 = cx1 - 104
            cv.text(ex1, y + 26, "EFFORT", ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
            word = MM.thinking_word(s.get("thoughts_per_click"))
            ew = 30 + 6 + cv.tw(word, ("Segoe UI", 9))
            self._mm_effort(cv, ex1 - ew, y + 48, s, tags=(tag, f"{tag}_e"))
            cv.tips[f"{tag}_e"] = "Effort: " + MM.THINKING.get(s.get("thoughts_per_click"), ("", "?"))[1]
            left_end = ex1 - max(ew, 50) - 20
        name = ("✔ " if (s.get("_post") or {}).get("voted") else "") + s["name"]
        cv.text(tx, y + 24, cv.fit(name, ("Segoe UI", 12, "bold"), left_end - tx), ("Segoe UI", 12, "bold"),
                fill=cv.c("text_strong"), anchor="w", tags=(tag,))
        cy = y + 40
        x = self._mm_mech_chip(cv, tx, cy, s, tags=(tag,))
        for word, chip in ((s.get("category") if s.get("category") != s.get("type") else None, False),
                           (MM.budget_of(s), True), (self._mm_from_word(s), False)):
            if not word or x + 16 + cv.tw(word, ("Segoe UI", 9)) > left_end:
                continue
            if chip:
                x = cv.chip(x + 8, cy, word, tags=(tag,))
            else:
                x = cv.bbox(cv.text(x + 8, cy + 11, word, ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="w",
                                    tags=(tag,)))[2]
        if (s.get("_post") or {}).get("hidden"):
            cv.text(x + 8, cy + 11, "⊘ HIDDEN", ("Segoe UI", 9, "bold"), fill=cv.c("bad"), anchor="w", tags=(tag,))
        return y + h

    def _mm_from_word(self, s):
        """Where a row comes from, in a word (From: All mixes them - 3.0.6)."""
        post = s.get("_post") or {}
        return "Mine" if s.get("origin") == "mine" or post.get("mine") else \
            "Official" if s.get("origin") in ("community", "example") or post.get("promoted") else "Community"

    def _mm_row_narrow(self, cv, r, i, pad, y, W, vmax):
        s, ph, key = r["s"], r["ph"], r["key"]
        tag = f"row{i}"
        x0, x1, h = pad, W - pad, 80
        cv.card(x0, y, x1, y + h, tag)
        cv.acts[tag] = lambda k=key: self.mm_open(k)
        cv.menus[tag] = lambda X, Y, k=key: self.mm_row_menu(k, X, Y)
        cv.icon(MM.tablet_of(s), x0 + 14, y + h / 2, 40, anchor="w", tags=(tag,))
        tx, rx = x0 + 66, x1 - 16
        if ph:
            cv.text(rx, y + 16, MM.short_div(ph["value"]), (TH.head_font(None, "num"), 15), fill=cv.c("money"),
                    anchor="ne", tags=(tag, f"{tag}_v"))
            cv.tips[f"{tag}_v"] = ph["how"]
        cv.text(rx, y + 46, "div / hour", ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="ne", tags=(tag,))
        room = rx - 80 - tx
        cv.text(tx, y + 20, cv.fit(s["name"], ("Segoe UI", 12, "bold"), room), ("Segoe UI", 12, "bold"),
                fill=cv.c("text_strong"), anchor="w", tags=(tag,))
        x = self._mm_mech_chip(cv, tx, y + 34, s, tags=(tag,))
        if x + 50 < rx - 70:
            x = self._mm_effort(cv, x + 10, y + 45, s, tags=(tag,)) if x + 120 < rx - 70 else \
                cv.pips(x + 10, y + 40, s.get("thoughts_per_click") or 0, tags=(tag,))
        word = self._mm_from_word(s)                     # (where it comes from - From: All mixes them)
        if x + 16 + cv.tw(word, ("Segoe UI", 9)) < rx - 70:
            cv.text(x + 12, y + 45, word, ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="w", tags=(tag,))
        if ph:
            bx1 = min(tx + 220, rx - 80)
            frac = max(0.02, min(1.0, ph["value"] / vmax))
            cv.create_rectangle(tx, y + 64, bx1, y + 68, fill=cv.c("surface_high"), outline="", tags=(tag,))
            cv.create_rectangle(tx, y + 64, tx + (bx1 - tx) * frac, y + 68, fill=cv.c("money"), outline="",
                                tags=(tag,))
        return y + h

    # ------------------------------------------------------------------ Quick tips (folded at the bottom of Find)
    def _mm_tips_draw(self, cv, pad, y, W, narrow):
        items = self.mm_one_shown()
        total = len(self.mm_one_view_items())
        on = getattr(self, "mm_tips_open", False)
        x0, x1 = pad, W - pad
        tag = "tips_head"
        top = y
        cv.card(x0, y, x1, y + 48, tag, lift=not on)           # (grown below when open)
        card_id = cv.find_withtag(tag)[0]
        cv.acts[tag] = lambda: self.mm_tips_toggle(not getattr(self, "mm_tips_open", False))
        cv.text(x0 + 18, y + 24, "▾" if on else "▸", ("Segoe UI", 10), fill=cv.c("text"), anchor="w", tags=(tag,))
        hd = cv.text(x0 + 36, y + 24, "Quick tips", ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w",
                     tags=(tag,))
        count = f"{len(items)} of {total}" if len(items) != total else str(total)
        cv.text(x1 - 18, y + 24, count, ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
        if not narrow:
            cv.text(cv.bbox(hd)[2] + 12, y + 25, "one-line ways to make currency, from the community",
                    ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="w", tags=(tag,))
        y += 48
        if not on:
            return y
        # the buttons: Add is always on; the rest act on the picked tip (grayed until one is picked)
        o = self.mm_one_current()
        mine, post = bool(o and o["origin"] == "mine"), (o or {}).get("_post")
        bx = x0 + 18
        for text, tg, fn, ok, tip in (
                ("＋ Add a tip", "t_add", self.mm_one_add, True, "Write your own quick tip (it stays on this PC until "
                                                                 "you post it)."),
                ("Copy", "t_copy", self.mm_one_copy, bool(o), "Copy the picked tip's text" if o else "Pick a tip first"),
                ("▲ Upvote", "t_vote", self.mm_one_vote, bool(post),
                 "Upvote the picked community tip" if post else "Pick a community tip to upvote it"),
                ("📤 Post", "t_post", self.mm_one_post, mine, "Share your picked tip on the community board" if mine
                 else "Pick one of your own tips (From: Mine) to post it"),
                ("🏷 Tags…", "t_tags", self.mm_one_tags, mine, "Set the picked tip's type and tags" if mine
                 else "Pick one of your own tips (From: Mine) to tag it")):
            f = ("Segoe UI", 10)
            if bx + cv.tw(text, f) + 32 > x1 - 18:
                y += 42
                bx = x0 + 18
            _a, bx = cv.button(bx, y, text, tg, fn, enabled=ok, tip=tip, h=32)
            bx += 8
        y += 44
        if not items:
            cv.text(x0 + 18, y + 4, "No tips here yet - press ＋ Add a tip." if not total else "No tips match the search.",
                    ("Segoe UI", 9), fill=cv.c("text_muted"))
            y += 28
        cols = 1 if narrow or W < 700 else 3 if W >= 1000 else 2
        gap = 10
        cw = (x1 - x0 - 36 - (cols - 1) * gap) / cols
        f, ff = ("Segoe UI", 10, "bold"), ("Segoe UI", 9)
        sel = getattr(self, "mm_one_sel", None)
        for row0 in range(0, len(items), cols):
            chunk = items[row0:row0 + cols]
            ids = []
            hmax = 0
            for j, o in enumerate(chunk):
                cx = x0 + 18 + j * (cw + gap)
                k = o["id"] + "|" + o["origin"]
                tg = f"tip{row0 + j}"
                tid = cv.text(cx + 14, y + 12, o.get("text", ""), f, fill=cv.c("text_strong"), width=cw - 28, tags=(tg,))
                post = o.get("_post") or {}
                by = post.get("author", {}).get("name") or o.get("author", "")
                bits = ([f"by {by}"] if by else []) + ([f"▲ {post.get('score', 0)}"] if post else []) + \
                    [{"community": "Official", "mine": "Mine", "board": "Community"}.get(o["origin"], "")] + \
                    (["⊘ HIDDEN"] if post.get("hidden") else [])
                if k == sel:
                    bits = ["✓ Picked"] + bits
                fid = cv.text(cx + 14, cv.bottom(tid, y + 30) + 6, " · ".join(b for b in bits if b), ff,
                              fill=cv.c("accent") if k == sel else cv.c("text_muted"), width=cw - 28, tags=(tg,))
                hmax = max(hmax, cv.bottom(fid, y + 50) - y + 12)
                ids.append((cx, tg, k, o))
            for cx, tg, k, o in ids:
                picked = k == sel
                bg = cv.card(cx, y, cx + cw, y + hmax, tg, fill=cv.c("surface"),
                             outline=cv.c("accent") if picked else cv.c("border"), width=2 if picked else 1)
                cv.tag_lower(bg, cv.find_withtag(tg)[0])
                cv.acts[tg] = lambda k=k: self.mm_one_pick(k)
                cv.dbl[tg] = lambda k=k: (self.mm_one_pick(k), self.mm_one_copy())
                cv.menus[tg] = lambda X, Y, k=k: (self.mm_one_pick(k), self.mm_one_menu(None, X, Y))
            y += hmax + gap
        y += 8
        cv.coords(card_id, *_rr_points(x0, top, x1, y, R))
        cv.tag_lower(card_id)
        return y

    # ------------------------------------------------------------------ an opened strat (3.0.6: the approved mockup v2)
    # The hero card (its tablet, BOSSING › SIMULACRUM + league, name, one line, tags, Run this strat), four tiles (Per
    # hour, Cost per map, Waystone, Atlas master), then two columns: In your map device and How it goes | Atlas master,
    # Content, Loot to sell, Tips, Risks, Sources. Older free text only in "From the author", folded, at the bottom.
    def _mm_draw_detail(self, cv):
        s = self.mm_current()
        W = max(cv.winfo_width(), 300)
        narrow = self.mm_narrow(cv)
        pad = 16 if narrow else 24
        y = 14
        i = cv.text(pad, y, "‹ All strats", ("Segoe UI", 10), fill=cv.c("link"), tags=("back",))
        cv.acts["back"] = self.mm_close
        cv.lifts["back"] = [(i, {"fill": cv.c("link")}, {"fill": cv.c("accent")})]
        y += 32
        if not s:
            cv.text(pad, y, "This strat isn't in the list any more.", ("Segoe UI", 10), fill=cv.c("text_muted"))
            return y + 40
        mine = self._mm_my_numbers_all().get(s["id"])
        y = self._mm_head_card(cv, s, pad, y, W, narrow) + 16
        y = self._mm_tiles(cv, s, mine, pad, y, W, narrow) + 16
        left = (self._mm_device_card, self._mm_steps_card, self._mm_money_card)
        right = (self._mm_master_card, self._mm_content_card, self._mm_loot_card, self._mm_tips_card,
                 self._mm_risks_card, self._mm_sources_card, self._mm_author_card)
        if narrow or W < 900:
            for part in left + right:
                y2 = part(cv, s, mine, pad, W - pad, y)
                y = y2 + 16 if y2 > y else y
            return y
        mid = pad + (W - 2 * pad - 16) * 0.55
        yl = yr = y
        for part in left:
            y2 = part(cv, s, mine, pad, mid, yl)
            yl = y2 + 16 if y2 > yl else yl
        for part in right:
            y2 = part(cv, s, mine, mid + 16, W - pad, yr)
            yr = y2 + 16 if y2 > yr else yr
        return max(yl, yr)

    def _mm_head_card(self, cv, s, pad, y, W, narrow):
        """The hero: the main mechanic's tablet, BOSSING › SIMULACRUM and the league, the name, one line, its tags
        (mechanics with their pictures, budget, effort, by whom), More ▾ and Run this strat (the one orange button)."""
        x0, x1 = pad, W - pad
        acc = cv.c("accent")
        post = s.get("_post") or {}
        ip = 16 if narrow else 24
        isz = 48 if narrow else 64
        top = y
        card = cv.card(x0, y, x1, y + 10, None, fill=TH.mix(cv.c("surface_raised"), acc, .06),
                       outline=TH.mix(acc, cv.c("border"), .45), lift=False)
        tx = x0 + ip + isz + (14 if narrow else 20)
        btns = self._mm_head_buttons(s, post)
        bw_all = sum(cv.tw(b[0], ("Segoe UI", 10, "bold" if b[3] == "primary" else "normal")) + 32 + 8 for b in btns)
        side = not narrow and W - tx - bw_all > 460
        wr = (x1 - ip - bw_all - 16) if side else (x1 - ip)
        f9 = ("Segoe UI", 9)
        ty = y + 22
        kick = f"{s.get('category', '')} › {s.get('type', '')}".upper() if s.get("type") else s.get("category", "").upper()
        k = cv.text(tx, ty + 6, kick, ("Segoe UI", 9, "bold"), fill=acc, anchor="w")
        lg = MM.league_of(s)
        lt = MM.league_text(lg) if not lg.startswith(("Game ", "Unknown")) else lg
        lx = cv.bbox(k)[2] + 8
        lw = cv.tw(lt, f9) + 12
        TH.round_rect(cv, lx, ty - 4, lx + lw, ty + 16, 3, fill=cv.c("surface_sunken"), outline=cv.c("border_light"))
        cv.text(lx + 6, ty + 6, lt, f9, fill=cv.c("text_muted"), anchor="w")
        ty += 22
        tt = cv.text(tx, ty, ("✔ " if post.get("voted") else "") + s["name"], ("Segoe UI", 16 if narrow else 18, "bold"),
                     fill=cv.c("text_strong"), width=wr - tx)
        ty = cv.bottom(tt, ty + 28) + 6
        if s.get("summary"):
            ty = cv.bottom(cv.text(tx, ty, s["summary"], ("Segoe UI", 10), fill=cv.c("text"), width=wr - tx), ty) + 8
        x = tx
        for m in self._mm_mechs_of(s):
            if x + 70 > wr:
                break
            x = cv.chip(x, ty, m, MECH_COL.get(m, "money"), MM.MECH_TABLET.get(m)) + 6
        b = MM.budget_of(s)
        if b and x + cv.tw(b, f9) + 20 < wr:
            x = cv.chip(x, ty, b) + 8
        if x + 90 < wr:
            x = self._mm_effort(cv, x + 4, ty + 11, s, tags=("h_eff",))
            cv.tips["h_eff"] = "Effort: " + MM.THINKING.get(s.get("thoughts_per_click"), ("", "?"))[1]
        by = post.get("author", {}).get("name") or s.get("author") or "?"
        src = next((x_["title"] for x_ in MM.sources_of(s) if x_["title"] and x_["title"] != x_["url"]), None)
        meta = " · ".join(m for m in ([f"By {by}", src] + ([f"▲ {post.get('score', 0)}"] if post else [])
                                       + (["⊘ HIDDEN"] if post.get("hidden") else [])) if m)
        if x + 60 < wr:
            cv.text(x + 8, ty + 11, cv.fit("· " + meta, f9, wr - x - 8), f9, fill=cv.c("text_muted"), anchor="w",
                    tags=("h_meta",))
            cv.tips["h_meta"] = meta
        ty += 22
        if post.get("pending") or (post.get("mine") and post.get("suggestions")):
            extra = [f"{post['pending']} change waiting for reviewers"] if post.get("pending") else []
            if post.get("mine") and post.get("suggestions"):
                extra.append(f"{post['suggestions']} suggested edit(s) for you (More ▾ › Suggestions)")
            ty = cv.bottom(cv.text(tx, ty + 4, " · ".join(extra), f9, fill=cv.c("text_muted"), width=wr - tx), ty) + 4
        bottom = max(ty + ip - 8, y + ip + isz + ip)
        got = cv.icon(MM.tablet_of(s), x0 + ip, (y + bottom) / 2, isz, anchor="w")
        if got is not None:
            bb = cv.bbox(got)
            cv.tag_lower(TH.round_rect(cv, bb[0] - 3, bb[1] - 3, bb[2] + 3, bb[3] + 3, 6, fill=cv.c("surface_sunken"),
                                       outline=cv.c("border_light")), got)
        if side:
            by0 = (y + bottom) / 2 - 22
            bx = x1 - ip
            for text, tg, fn, kind, tip in reversed(btns):
                bx0, _ = cv.button(bx, by0, text, tg, fn, kind, anchor="e", h=44 if kind == "primary" else 44, tip=tip)
                bx = bx0 - 8
        else:
            bx, by0 = x0 + ip, bottom
            for text, tg, fn, kind, tip in btns:
                bwid = cv.tw(text, ("Segoe UI", 10, "bold" if kind == "primary" else "normal")) + 32
                if bx + bwid > x1 - ip:
                    bx, by0 = x0 + ip, by0 + 46
                _, bx = cv.button(bx, by0, text, tg, fn, kind, h=38, tip=tip)
                bx += 8
            bottom = by0 + 38 + ip
        cv.coords(card, *_rr_points(x0, top, x1, bottom, R))
        cv.tag_lower(card)
        return bottom

    def _mm_mechs_of(self, s):
        """The mechanics a strat farms: its type when it is one, then the ones it also uses."""
        out = [s["type"]] if s.get("type") in MM.MECH_TABLET else []
        return out + [t for t in s.get("tags") or [] if t in MM.TAG_GROUPS["Also uses"] and t not in out]

    def _mm_head_buttons(self, s, post):
        """(text, tag, command, kind, tip) - More ▾ (every action: edit, export, post, upvote ...), then the one
        orange button."""
        return [("More ▾", "h_more", lambda: self.mm_more_at("h_more"), "ghost",
                 "Everything you can do with this strat: edit, export, post, upvote, suggest an edit, report…"),
                ("Run this strat", "h_run", lambda: self.mm_run(self.mm_sel), "primary",
                 "Opens the Strat Tracker on this strat: log your runs, see what it really made.")]

    def _mm_tiles(self, cv, s, mine, pad, y, W, narrow):
        """Per hour, Cost per map, Waystone, Atlas master - each says how its number came (ⓘ). A tile with nothing
        to say isn't drawn (no waystone, no master)."""
        ph = MM.per_hour(s, mine)
        cost = MM.run_cost(s, self.mm_costs())
        busy = s["id"] in getattr(self, "_mm_cost_busy", set())
        slots = MM.device_slots(s)
        way = next((x for x in slots if x["kind"] == "waystone"), None)
        master, picks = MM.master_of(s.get("masters"))
        tiles = ["ph"]
        if cost or s.get("items"):
            tiles.append("cost")
        if way:
            tiles.append("way")
        if master:
            tiles.append("master")
        cols = 2 if (narrow or W < 900) and len(tiles) > 2 else len(tiles)
        gap = 16
        tw = (W - 2 * pad - (cols - 1) * gap) / cols
        th = 120
        rows_n = -(-len(tiles) // cols)
        num = (TH.head_font(None, "num"), 20 if narrow else 22)
        f9, lab = ("Segoe UI", 9), ("Segoe UI", 9, "bold")
        for i, kind in enumerate(tiles):
            row = i // cols
            in_row = len(tiles) - row * cols if row == rows_n - 1 else cols     # (a short last row fills it evenly)
            tw = (W - 2 * pad - (in_row - 1) * gap) / in_row
            x0 = pad + (i % cols) * (tw + gap)
            ty = y + row * (th + gap)
            tag = f"tile_{kind}"
            cv.tile_boxes = (getattr(cv, "tile_boxes", {}) if i else {}) | {kind: (x0, ty, x0 + tw, ty + th)}
            cv.card(x0, ty, x0 + tw, ty + th, None, lift=False)
            if kind == "ph":
                l_ = cv.text(x0 + 20, ty + 26, "PER HOUR", lab, fill=cv.c("text_muted"), anchor="w")
                you = (mine or {}).get("per_hour")
                if you is not None:
                    big, line = f"{MM.short_div(you)} div", f"from your {mine.get('runs', 0)} runs"
                    how = f"Your Strat Tracker: {MM.short_div(you)} div an hour over {mine.get('runs', 0)} runs."
                elif ph:
                    big, line, how = f"{MM.short_div(ph['value'])} div", "the author's estimate", ph["how"]
                else:
                    big, line = "—", "fills in from your runs"
                    how = "Comes from your counted maps once you run it."
                cv.info(cv.bbox(l_)[2] + 6, ty + 26, f"{tag}_i", how)
                cv.text(x0 + 20, ty + 42, big, num, fill=cv.c("money") if big != "—" else cv.c("text_muted"),
                        tags=(tag,))
                cv.tips[tag] = how
                cv.text(x0 + 20, ty + 86, line, f9, fill=cv.c("text_muted"), width=tw - 40)
            elif kind == "cost":
                l_ = cv.text(x0 + 20, ty + 26, "COST PER MAP", lab, fill=cv.c("text_muted"), anchor="w")
                how = cost["how"] if cost else "The trade site's price of what goes in your map device - checked " \
                                               "once a day while Farming Strategies is open."
                cv.info(cv.bbox(l_)[2] + 6, ty + 26, f"{tag}_i", how)
                cv.text(x0 + 20, ty + 42, f"{MM.short_div(cost['value'])} div" if cost else "—", num,
                        fill=cv.c("text_strong"), tags=(tag,))
                cv.tips[tag] = how
                line = cost["sum"] if cost else ("checking the trade site…" if busy else "not checked yet")
                cv.text(x0 + 20, ty + 86, cv.fit(line, f9, tw - 40), f9, fill=cv.c("text_muted"))
            elif kind == "way":
                cv.text(x0 + 20, ty + 26, "WAYSTONE", lab, fill=cv.c("text_muted"), anchor="w")
                got = cv.icon(way["base"], x0 + 20, ty + 46, 36, tags=(tag,))
                wx = x0 + 20 + (46 if got is not None else 0)
                cv.text(wx, ty + 50, way["sub"], ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w")
                it = way.get("item") or {}
                n = len(it.get("mods") or it.get("key_mods") or [])
                line = (f"{n} mod{'s' if n != 1 else ''}" + (f", {it['rarity'].lower()}" if it.get("rarity") else "")
                        if n else ("" if not it else "no mods"))
                cv.text(wx, ty + 70, cv.fit(line, f9, x0 + tw - wx - 16), f9, fill=cv.c("text_muted"), anchor="w")
                cv.tips[tag] = (it.get("name") or way["base"]) + "".join("\n★ " + m for m in it.get("key_mods") or [])
            else:
                cv.text(x0 + 20, ty + 26, "ATLAS MASTER", lab, fill=cv.c("text_muted"), anchor="w")
                gx, gy, cs = x0 + 20, ty + 42, 22
                for c_i, ch in enumerate(MM.MASTERS[master]):
                    cx_ = gx + (c_i % MM.MASTER_COLS) * (cs + 3)
                    cy_ = gy + (c_i // MM.MASTER_COLS) * (16 + 3)
                    on = ch in picks
                    cv.create_rectangle(cx_, cy_, cx_ + cs, cy_ + 16, outline=cv.c("border") if not on else "",
                                        fill=cv.c("accent") if on else cv.c("surface_sunken"), tags=(tag,))
                mx = gx + MM.MASTER_COLS * (cs + 3) + 10
                cv.text(mx, ty + 66, cv.fit(master, ("Segoe UI", 10, "bold"), x0 + tw - mx - 12),
                        ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="w")
                cv.text(mx, ty + 86, f"{len(picks)} of {MM.MASTER_PICKS} picked", f9, fill=cv.c("text_muted"),
                        anchor="w")
                cv.tips[tag] = master + ": " + ", ".join(picks)
        rows = -(-len(tiles) // cols)
        return y + rows * th + (rows - 1) * gap

    def _mm_box(self, cv, x0, x1, y, title, tag=None, how=None, note=None, fold=None):
        """A card with a title (and a muted note beside it; fold: (open?, command) - a ▾ / ▸ to fold it) ->
        (card item, y under the title)."""
        card = cv.card(x0, y, x1, y + 10, None, lift=False)
        tx = x0 + 20
        tags = ()
        if fold is not None:                             # (Tips / Risks: the title folds it - the mockup's look;
            ftag = f"fold_{title}"                       # From the author shows its ▸ / ▾)
            tags = (ftag,)
            cv.acts[ftag] = fold[1]
            cv.tips[ftag] = "Click to fold" if fold[0] else "Click to open"
            if title == "From the author":
                cv.text(tx, y + 28, "▾" if fold[0] else "▸", ("Segoe UI", 10), fill=cv.c("text_muted"), anchor="w",
                        tags=tags)
                tx += 16
        t = cv.text(tx, y + 28, title, ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w", tags=tags)
        x = cv.bbox(t)[2]
        if note:
            x = cv.bbox(cv.text(x + 8, y + 29, note, ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="w",
                                tags=tags))[2]
        if how:
            cv.info(x + 8, y + 28, tag or "box_i", how)
        return card, y + 52

    def _mm_device_card(self, cv, s, mine, x0, x1, y):
        """In your map device: the waystone and tablet slots (their pictures, ×N, what they are), a free slot, the
        tablet mods that matter, and Copy regex / Trade Site ↗ for them."""
        slots = MM.device_slots(s)
        if not slots:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "In your map device")
        tabs = [it for it in s.get("items") or [] if it.get("kind") == "tablet"]
        cards = [MM.item_card(it) for it in tabs if it.get("key_mods")]
        rx = s.get("regex") or (MM.item_regex([MM.card_item(c) for c in cards]) if cards else "")
        made = MM.made_for_you("tablet", cards, SETTINGS.get("league")) if cards else {"url": None}
        bx = x1 - 20
        bx0, _ = cv.button(bx, y + 12, "Trade Site ↗", "dev_trade",
                           lambda: (__import__("webbrowser").open(made["url"]) if made.get("url") else None),
                           enabled=bool(made.get("url")), anchor="e", h=34,
                           tip=("Opens the trade site in your browser: " + made["caption"]) if made.get("url")
                           else "No tablet mods to search")
        cv.button(bx0 - 8, y + 12, "Copy regex", "dev_regex", lambda: self.mm_item_copy(rx, "the tablets"),
                  enabled=bool(rx), anchor="e", h=34,
                  tip="Copy the stash search. In game: Ctrl+V in the stash search." if rx else "No stash search")
        yy += 6
        sz, gap, x = 74, 32, x0 + 30
        n_tabs = sum(sl["count"] for sl in slots if sl["kind"] == "tablet")
        cap = MM.DEVICE_TABLETS + (1 if "City" in (s.get("tags") or []) else 0)
        shown = slots + ([{"kind": "free"}] if n_tabs < max(cap, 4) else [])     # (a slot nothing is in yet)
        c = (self.mm_costs() or {}).get(s.get("id")) or {}
        prices = c.get("prices") or {}
        for i, sl in enumerate(shown):
            if x + sz > x1 - 10:
                x, yy = x0 + 30, yy + sz + 58
            tag = f"need{i}"
            if sl["kind"] == "free":
                TH.round_rect(cv, x, yy, x + sz, yy + sz, 6, fill=cv.c("surface_sunken"), outline=cv.c("border_light"),
                              dash=(3, 3), tags=(tag,))
                cv.text(x + sz / 2, yy + sz / 2, "·", ("Segoe UI", 10), fill=cv.c("text_muted"), anchor="center")
                cv.text(x + sz / 2, yy + sz + 14, "Free slot", ("Segoe UI", 9), fill=cv.c("text"), anchor="center")
                cv.text(x + sz / 2, yy + sz + 34, "any tablet", ("Segoe UI", 9), fill=cv.c("text_muted"),
                        anchor="center")
                cv.tips[tag] = "Any tablet"
                x += sz + gap
                continue
            sl_ = TH.round_rect(cv, x, yy, x + sz, yy + sz, 6, fill=cv.c("surface_sunken"), outline=cv.c("border_light"),
                                tags=(tag,))
            cv.lifts[tag] = [(sl_, {"outline": cv.c("border_light")}, {"outline": cv.c("text_muted")})]
            if cv.icon(sl["base"], x + sz / 2, yy + sz / 2, 60, anchor="center", tags=(tag,)) is None and not (
                    sl.get("fallback") and cv.icon(sl["fallback"], x + sz / 2, yy + sz / 2, 60, anchor="center",
                                                   tags=(tag,)) is not None):
                cv.text(x + sz / 2, yy + sz / 2, cv.fit(sl["word"], ("Segoe UI", 9), sz - 8), ("Segoe UI", 9),
                        fill=cv.c("text_muted"), anchor="center", tags=(tag,))
            if sl["count"] > 1:
                bi = cv.text(x + sz - 4, yy + sz - 3, f"×{sl['count']}", ("Segoe UI", 9, "bold"), fill=cv.c("text"),
                             anchor="se", tags=(tag,))
                bb = cv.bbox(bi)
                cv.tag_lower(TH.round_rect(cv, bb[0] - 4, bb[1] - 1, bb[2] + 3, bb[3] + 1, 3,
                                           fill=cv.c("surface_raised"), outline=cv.c("border"), tags=(tag,)), bi)
            cv.text(x + sz / 2, yy + sz + 14, cv.fit(sl["word"], ("Segoe UI", 9), sz + gap - 6), ("Segoe UI", 9),
                    fill=cv.c("text"), anchor="center", tags=(tag,))
            cv.text(x + sz / 2, yy + sz + 34, sl["sub"], ("Segoe UI", 9), fill=cv.c("text_muted"), anchor="center",
                    tags=(tag,))
            it = sl.get("item")
            if it is not None:
                idx = (s.get("items") or []).index(it)
                p = prices.get(str(idx))
                cv.tips[tag] = (f"{it.get('name') or sl['base']} ×{sl['count']}" +
                                ("".join("\n★ " + km for km in it.get("key_mods") or [])) +
                                (f"\n~{p:.2f} div today (trade site)" if p is not None else "\nno price checked yet") +
                                "\nClick: copy its stash search, or open the Trade Site")
                cv.acts[tag] = lambda it=it, tg=tag: self.mm_item_menu(it, tg)
            else:
                cv.tips[tag] = f"{sl['word']}: {sl['sub']} (from the author's text)"
            x += sz + gap
        yy += sz + 52
        keys = list(dict.fromkeys(m for it in tabs for m in it.get("key_mods") or []))
        if keys:
            lab = cv.text(x0 + 20, yy + 10, "TABLET MODS THAT MATTER", ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"),
                          anchor="w")
            kx, ky = cv.bbox(lab)[2] + 12, yy
            for m in keys:
                w = cv.tw(m, ("Segoe UI", 9)) + 16
                if kx + w > x1 - 20 and kx > x0 + 20:
                    kx, ky = x0 + 20, ky + 28
                kx = cv.chip(kx, ky, cv.fit(m, ("Segoe UI", 9), x1 - x0 - 60), "text", h=20) + 6
            yy = ky + 32
        yy += 8
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_steps_card(self, cv, s, mine, x0, x1, y):
        steps = s.get("steps") or []
        if not steps:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "How it goes", note=f"{len(steps)} step{'s' if len(steps) != 1 else ''}")
        for i, line in enumerate(steps, 1):
            cx = x0 + 30
            tid = cv.text(cx + 20, yy, line, ("Segoe UI", 10), fill=cv.c("text"), width=x1 - cx - 40)
            b = cv.bottom(tid, yy + 18)
            cv.create_oval(cx - 9, yy - 1, cx + 9, yy + 17, fill=cv.c("surface_sunken"), outline=cv.c("border"))
            cv.text(cx, yy + 8, str(i), ("Segoe UI", 8), fill=cv.c("text_muted"), anchor="center")  # token-ok
            if i < len(steps):
                cv.create_line(cx, yy + 19, cx, b + 12, fill=cv.c("border"))
            yy = b + 14
        yy += 8
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_master_card(self, cv, s, mine, x0, x1, y):
        """Atlas master (read only): the master list, its 12 choices as in the game (3 × 4 squares), the picks."""
        master, picks = MM.master_of(s.get("masters"))
        if not master:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Atlas master", note=f"{master} · {len(picks)} of {MM.MASTER_PICKS}")
        yy = self._mm_atlas_panel(cv, x0 + 20, x1 - 20, yy - 6, master, picks, master, None) + 20
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_atlas_panel(self, cv, x0, x1, y, cur, picks, tab, act):
        """Atlas master as the approved mockup (v3): the master list (name, SPECIALTY, 4 pips, "N of 4"; the shown
        one with the accent), the shown master's 12 choices as square tiles in the game's 3 × 4 grid (picked: a 2 px
        accent edge, a warm fill, ✓), and the details (its picks numbered, the hovered choice, Clear picks).
        act: None (read only) or {"tab": fn(master), "pick": fn(master, choice), "clear": fn} -> y under it."""
        acc = cv.c("accent")
        warm = TH.mix(cv.c("surface_raised"), acc, .18)
        f9, fb = ("Segoe UI", 9), ("Segoe UI", 8, "bold")  # token-ok (canvas)
        W = x1 - x0
        names = list(MM.MASTERS)
        pad = 16
        frame = TH.round_rect(cv, x0, y, x1, y + 10, 8, fill=cv.c("surface"), outline=cv.c("border"))
        ix0, ix1 = x0 + pad, x1 - pad
        iw = ix1 - ix0
        tile, gap, side = 92, 8, 190                     # side: the details column at least
        # list | grid | details when they fit (the list narrows first, then the tiles to 86 - a choice's longest
        # word still fits); else the details under the grid; narrow: the masters as a row too
        list_w = next((w for w in (190, 150) if iw >= w + 16 + 3 * tile + 2 * gap + 16 + side + 60), 130)
        fit = (iw - list_w - 16 - 16 - side - 2 * gap) / 3
        if fit >= 86:
            tile = min(92, fit)
        stacked = iw < list_w + 16 + 3 * 76 + 2 * gap
        if stacked:
            tile = max(70, min(92, (iw - 2 * gap) / 3))
        grid_w = 3 * tile + 2 * gap
        yy = y + pad
        # -- the masters
        cv.text(ix0, yy + 6, "MASTER", fb, fill=cv.c("text_muted"), anchor="w")
        yy += 18
        if stacked:
            mw, mh, mgap = (iw - 2 * gap) / 3, 88, gap
        else:
            mw, mh, mgap = list_w, 92, 6
        for i, m in enumerate(names):
            mx = ix0 + (i * (mw + mgap) if stacked else 0)
            my = yy + (0 if stacked else i * (mh + mgap))
            shown, mine = m == tab, m == cur
            k = len(picks) if mine else 0
            tag = f"am_tab_{i}"
            b = TH.round_rect(cv, mx, my, mx + mw, my + mh, 6, fill=warm if shown else cv.c("surface_raised"),
                              outline=acc if shown else cv.c("border"), width=1, tags=(tag,))
            first, spec = m.split("'s ")[0], (m.split(" ", 1)[1] if " " in m else "")
            cv.text(mx + 12, my + 20, first, ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="w",
                    tags=(tag,))
            cv.text(mx + 12, my + 41, spec.upper(), fb, fill=cv.c("text_muted"), anchor="w", tags=(tag,))
            for p_ in range(MM.MASTER_PICKS):
                px = mx + 12 + p_ * 17
                cv.create_rectangle(px, my + 54, px + 13, my + 57, outline="",
                                    fill=acc if p_ < k else cv.c("surface_high"), tags=(tag,))
            cv.text(mx + 12, my + 72, f"{k} of {MM.MASTER_PICKS}" +
                    (" ✓" if k >= MM.MASTER_PICKS else ""), f9, fill=cv.c("text"), anchor="w", tags=(tag,))
            if act:
                cv.acts[tag] = lambda m=m: act["tab"](m)
                cv.lifts[tag] = [(b, {"outline": acc if shown else cv.c("border")},
                                  {"outline": acc if shown else cv.c("text_muted")})]
            cv.tips[tag] = m + (f" - the strat's master: {k} of {MM.MASTER_PICKS}" if mine else "")
        if stacked:
            gy0 = yy + mh + 14
            note_y = None
        else:
            gy0 = y + pad
            note_y = yy + 3 * (mh + mgap) + 6
            cv.text(ix0, note_y + 8, "One master per strat.", f9, fill=cv.c("text_muted"), anchor="w")
        # -- the 12 choices
        gx0 = ix0 if stacked else ix0 + list_w + 16
        mine = picks if tab == cur else []
        full = tab == cur and len(picks) >= MM.MASTER_PICKS
        dx0 = gx0 + grid_w + 16                          # the details column (stacked: under the grid)
        dw = ix1 - dx0
        under = dw < side - 20                           # (no room on the right: the details go under the grid)
        if under:
            dx0, dw = gx0, ix1 - gx0
        detail_y = gy0 + 4 * (tile + gap) + 6 if under else gy0
        hover_name = None
        for i, ch in enumerate(MM.MASTERS[tab]):
            gx = gx0 + (i % 3) * (tile + gap)
            gy = gy0 + (i // 3) * (tile + gap)
            tag = f"am_{names.index(tab)}_{i}"
            on = ch in mine
            b = TH.round_rect(cv, gx, gy, gx + tile, gy + tile, 6, fill=warm if on else cv.c("surface_raised"),
                              outline=acc if on else cv.c("border"), width=2 if on else 1, tags=(tag,))
            cv.create_text(gx + tile / 2, gy + tile / 2, text=ch, width=tile - 12, justify="center", anchor="center",
                           font=("Segoe UI", 9, "bold") if on else f9, tags=(tag,),
                           fill=cv.c("text_strong") if on else cv.c("text_muted") if full else cv.c("text"))
            if on:
                cv.text(gx + tile - 12, gy + 12, "✓", ("Segoe UI Symbol", 9, "bold"), fill=acc, anchor="center",
                        tags=(tag,))
            lift = [(b, {"outline": acc if on else cv.c("border")}, {"outline": acc if on else cv.c("text_muted")})]
            cv.lifts[tag] = lift
            if act:
                cv.acts[tag] = lambda m=tab, ch=ch: act["pick"](m, ch)
            cv.tips[tag] = (f"{MM.MASTER_PICKS} of {MM.MASTER_PICKS} used - untick one first" if full and not on
                            else ch + (" - picked" if on else ""))
        # -- the details
        yy2 = detail_y
        tm = cv.text(dx0, yy2, f"{tab} · {len(mine)} of {MM.MASTER_PICKS} points".upper(), fb,
                     fill=cv.c("text_muted"), anchor="nw", width=dw)
        yy2 = cv.bottom(tm, yy2 + 12) + 8
        for n in range(MM.MASTER_PICKS):
            have = n < len(mine)
            cv.create_oval(dx0, yy2 + 2, dx0 + 18, yy2 + 20, outline="",
                           fill=acc if have else cv.c("surface_high"))
            from .style import text_on
            cv.text(dx0 + 9, yy2 + 11, str(n + 1), fb, fill=text_on(acc) if have else cv.c("text_muted"),
                    anchor="center")
            cv.text(dx0 + 28, yy2 + 11, cv.fit(mine[n] if have else ("one more point" if n == len(mine) else ""),
                                               ("Segoe UI", 10), dw - 30), ("Segoe UI", 10),
                    fill=cv.c("text") if have else cv.c("text_muted"), anchor="w")
            yy2 += 26
        yy2 += 6
        cv.create_line(dx0, yy2, dx0 + dw, yy2, fill=cv.c("border"))
        yy2 += 12
        hn = cv.text(dx0, yy2 + 8, "Hover a choice", ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="w")
        wd = cv.text(dx0, yy2 + 20, "What it does shows here when the game data has it.", f9,
                     fill=cv.c("text_muted"), anchor="nw", width=dw)
        for i, ch in enumerate(MM.MASTERS[tab]):           # (the hovered choice's name, without a redraw)
            cv.lifts[f"am_{names.index(tab)}_{i}"].append((hn, {"text": "Hover a choice"}, {"text": ch}))
        yy2 = cv.bottom(wd, yy2 + 36) + 12
        if act:
            cv.button(dx0, yy2, "Clear picks", "am_clear", act["clear"], h=36, enabled=bool(picks),
                      tip="Untick the picks" if picks else "Nothing picked yet")
            yy2 += 48
        _ = hover_name
        bottom = max(gy0 + 4 * (tile + gap) - gap, yy2, (note_y or 0) + 20) + pad
        cv.coords(frame, *_rr_points(x0, y, x1, bottom, 8))
        return bottom

    def _mm_content_card(self, cv, s, mine, x0, x1, y):
        """Content: the mechanics (with their pictures), bosses, map content and map type it farms."""
        mechs = self._mm_mechs_of(s)
        tags = s.get("tags") or []
        groups = MM.content_groups()
        rest = [MM.short_tag(t) for g in groups.values() for t in g if t in tags] + \
               [t for t in MM.TAG_GROUPS["Map type"] if t in tags]
        if s.get("category") == "Bossing" and s.get("type") and MM.short_tag(s["type"]) not in rest:
            rest.insert(0, s["type"])
        if not mechs and not rest:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Content")
        x = x0 + 20
        for word, base, role in [(m, MM.MECH_TABLET.get(m), MECH_COL.get(m, "money")) for m in mechs] + \
                                [(r, None, "text_muted") for r in rest]:
            w = cv.tw(word, ("Segoe UI", 9)) + 16 + (18 if base else 0)
            if x + w > x1 - 20 and x > x0 + 20:
                x, yy = x0 + 20, yy + 28
            x = cv.chip(x, yy, word, role, base) + 6
        yy += 22 + 20
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_loot_card(self, cv, s, mine, x0, x1, y):
        """Loot to sell: a pill per item with its picture from the trade site (when known), else a dot."""
        loot = s.get("loot") or []
        if not loot:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Loot to sell")
        x, h = x0 + 20, 30
        for i, line in enumerate(loot):
            name, note = _loot_parts(line)
            f, fn = ("Segoe UI", 10), ("Segoe UI", 9)
            w = 34 + cv.tw(name, f) + (cv.tw(note, fn) + 8 if note else 0) + 14
            if x + w > x1 - 20 and x > x0 + 20:
                x, yy = x0 + 20, yy + h + 6
            tag = f"loot_{i}"
            TH.round_rect(cv, x, yy, x + w, yy + h, h // 2 - 1, fill=cv.c("surface"), outline=cv.c("border_light"),
                          tags=(tag,))
            if cv.icon(name, x + 6, yy + h / 2, 20, anchor="w", tags=(tag,)) is None:
                cv.create_oval(x + 6, yy + 5, x + 26, yy + 25, fill=cv.c("surface_high"), outline="", tags=(tag,))
            t_ = cv.text(x + 34, yy + h / 2, name, f, fill=cv.c("text"), anchor="w", tags=(tag,))
            if note:
                cv.text(cv.bbox(t_)[2] + 8, yy + h / 2 + 1, note, fn, fill=cv.c("text_muted"), anchor="w", tags=(tag,))
            cv.tips[tag] = line
            x += w + 6
        yy += h + 16
        yy = cv.bottom(cv.text(x0 + 20, yy, "Item pictures come from the trade site, like Price Checks.",
                               ("Segoe UI", 9), fill=cv.c("text_muted")), yy + 14) + 18
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_fold_toggle(self, key):
        st = self.__dict__.setdefault("mm_folds", {})
        st[key] = not st.get(key, key != "author")
        self.mm_detail_cv.later(1)

    def _mm_list_card(self, cv, x0, x1, y, title, lines, key):
        if not lines:
            return y
        on = getattr(self, "mm_folds", {}).get(key, key != "author")
        card, yy = self._mm_box(cv, x0, x1, y, title, note=str(len(lines)),
                                fold=(on, lambda k=key: self._mm_fold_toggle(k)))
        if on:
            for line in lines:
                yy = cv.bottom(cv.text(x0 + 20, yy, "• " + line, ("Segoe UI", 9), fill=cv.c("text"),
                                       width=x1 - x0 - 40), yy + 14) + 4
            yy += 14
        else:
            yy -= 8
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_tips_card(self, cv, s, mine, x0, x1, y):
        return self._mm_list_card(cv, x0, x1, y, "Tips", s.get("tips") or [], "tips")

    def _mm_risks_card(self, cv, s, mine, x0, x1, y):
        return self._mm_list_card(cv, x0, x1, y, "Risks", s.get("risks") or [], "risks")

    def _mm_sources_card(self, cv, s, mine, x0, x1, y):
        srcs = MM.sources_of(s)                          # (an older file's plain lines read too)
        if not srcs:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Sources")
        import webbrowser
        for i, src in enumerate(srcs):
            tg = f"src{i}"
            link = bool(src["url"])
            si = cv.text(x0 + 20, yy, src["title"] + ("  ↗" if link else ""), ("Segoe UI", 9),
                         fill=cv.c("link") if link else cv.c("text"), width=x1 - x0 - 40, tags=(tg,))
            if link:
                cv.acts[tg] = lambda u=src["url"]: webbrowser.open(u)
                cv.lifts[tg] = [(si, {"fill": cv.c("link")}, {"fill": cv.c("accent")})]
                cv.tips[tg] = src["url"]
            yy = cv.bottom(si, yy + 14) + 6
        yy += 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_author_card(self, cv, s, mine, x0, x1, y):
        """From the author (folded): the older free text only - what nothing above already shows."""
        lines = []
        for key, title in (("requirements", "Requirements"), ("setup", "Other setup"), ("craft_steps", "Craft steps")):
            lines += [f"{title}: {x}" for x in s.get(key) or []]
        if not s.get("items"):
            lines += [f"Tablets: {x}" for x in s.get("tablets") or []]
            lines += [f"Waystones: {x}" for x in s.get("waystones") or []]
        if not MM.master_of(s.get("masters"))[0]:
            lines += [f"Atlas: {x}" for x in s.get("atlas") or []]
        if isinstance(s.get("ledger"), dict) and MM.ledger_text(s["ledger"]):
            lines.append("Their Strat Tracker: " + MM.ledger_text(s["ledger"]))
        if s.get("regex"):
            lines.append("Stash search: " + s["regex"])
        y2 = self._mm_list_card(cv, x0, x1, y, "From the author", lines, "author")
        ref = s.get("atlas_image")
        if ref and getattr(self, "mm_folds", {}).get("author"):
            from . import stratimg
            path = stratimg.path_of(ref) if ref.startswith("l:") else self.mm_board_image(ref, s) if \
                ref.startswith("b:") else None
            img = self.strat_thumb(path, min(320, int(x1 - x0 - 40)), 180) if path and hasattr(self, "strat_thumb") \
                else None
            if img is not None:
                self.mm_atlas_img = img
                cv.create_image(x0 + 20, y2 + 8, image=img, anchor="nw", tags=("atlas",))
                cv.acts["atlas"] = lambda p=path: self.mm_atlas_big(p)
                cv.tips["atlas"] = "The author's atlas. Click to see it big."
                y2 += img.height() + 16
        return y2

    def _mm_money_card(self, cv, s, mine, x0, x1, y):
        """Where your money came from: your logs' loot for this strat, each part with a mark and a word."""
        rows = self._mm_my_loot(s["id"])
        if not rows:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Where your money came from", "money_i",
                                "From your Strat Tracker logs for this strat: each drop's share of the loot's value.")
        top = rows[:4]
        rest = sum(g["share"] for g in rows[4:])
        parts = [(g["name"], g["share"]) for g in top] + ([("Other", rest)] if rest > 0.005 else [])
        cols = ("purple", "link", "money", "text_muted", "border_light")
        bx0, bx1 = x0 + 18, x1 - 18
        x = bx0
        for i, (name, share) in enumerate(parts):
            w = (bx1 - bx0) * share
            col = cv.c(cols[i % len(cols)])
            tg = f"loot{i}"
            cv.create_rectangle(x, yy, x + w, yy + 28, fill=col, outline=cv.c("surface_raised"), tags=(tg,))
            label = f"{MARKS[i % len(MARKS)]} {name} {share * 100:.0f}%"
            from .style import text_on
            if cv.tw(label, ("Segoe UI", 9, "bold")) < w - 8:
                cv.text(x + 6, yy + 14, label, ("Segoe UI", 9, "bold"), fill=text_on(col), anchor="w", tags=(tg,))
            cv.tips[tg] = label
            x += w
        yy += 38
        legend = "   ".join(f"{MARKS[i % len(MARKS)]} {n} {sh * 100:.0f}%" for i, (n, sh) in enumerate(parts))
        yy = cv.bottom(cv.text(bx0, yy, legend, ("Segoe UI", 9), fill=cv.c("text_muted"), width=bx1 - bx0),
                       yy + 16) + 16
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

def _rr_points(x0, y0, x1, y1, r):
    """The points of TH.round_rect (to resize a card drawn before its height was known)."""
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
            x0, y1 - r, x0, y0 + r, x0, y0]


def _loot_parts(line):
    """"Voices (keep unidentified)" / "Voices - keep unidentified" -> ("Voices", "keep unidentified")."""
    line = str(line).strip()
    m = re.match(r"^(.+?)\s*\((.+)\)$", line) or re.match(r"^(.+?)\s+[-–]\s+(.+)$", line)
    return (m.group(1).strip(), m.group(2).strip()) if m else (line, "")


def _ago_day(day):
    """"2026-11-14" -> "3 days ago" / "today"."""
    try:
        t = time.mktime(time.strptime(str(day), "%Y-%m-%d"))
    except (TypeError, ValueError):
        return str(day or "?")
    d = int((time.time() - t) // 86400)
    return "today" if d <= 0 else "yesterday" if d == 1 else f"{d} days ago"


def scroller(parent, app, draw, bg):
    """A frame with a StratCanvas and its own scroll bar (shown only when needed) -> (frame, canvas)."""
    f = tk.Frame(parent, bg=bg)
    cv = StratCanvas(f, app, draw)
    sb = ttk.Scrollbar(f, orient="vertical", command=cv.yview)
    cv.pack(side="left", fill="both", expand=True)
    cv.attach_scrollbar(sb)
    return f, cv
