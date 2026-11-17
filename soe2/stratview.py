"""Farming Strategies (3.0.6): Find (the list) and an opened strat, each drawn on one canvas - cards, chips, the
tablet pictures, one orange button - so the page follows the theme pack and stays light in the Drawer (a few hundred
canvas items instead of hundreds of frames and labels: the Drawer's resize lag).

Every number has an ⓘ (or its own hover) saying how it was worked out. State is never color alone: a mark and a word
(▲ / ▼, ✓ Picked, ◆ you). Data: moneymakers.py (per_hour, run_cost, run_profit, run_time); the pictures:
pricecheck_page.icons() / pc_art (the game's tablet for each strat's mechanic; none -> the word alone).
GGG ToS: looks only - nothing here reads the screen or the clipboard."""
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import themes as TH
from . import moneymakers as MM

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
            from .pricecheck_page import icons
            url = icons().get(base)
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
        cv.text(cx1, y + 26, "COST / RUN", ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="e", tags=(tag,))
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

    # ------------------------------------------------------------------ an opened strat
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
        if narrow or W < 900:
            for part in (self._mm_need_card, self._mm_steps_card, self._mm_masters_card, self._mm_yours_card,
                         self._mm_money_card, self._mm_guide_card):
                y2 = part(cv, s, mine, pad, W - pad, y)
                y = y2 + 16 if y2 > y else y
            return y
        mid = pad + (W - 2 * pad - 16) * 0.55
        yl = yr = y
        for part in (self._mm_yours_card, self._mm_money_card, self._mm_guide_card):
            y2 = part(cv, s, mine, pad, mid, yl)
            yl = y2 + 16 if y2 > yl else yl
        for part in (self._mm_need_card, self._mm_steps_card, self._mm_masters_card):
            y2 = part(cv, s, mine, mid + 16, W - pad, yr)
            yr = y2 + 16 if y2 > yr else yr
        return max(yl, yr)

    def _mm_head_card(self, cv, s, pad, y, W, narrow):
        x0, x1 = pad, W - pad
        acc = cv.c("accent")
        post = s.get("_post") or {}
        ip = 16 if narrow else 24
        isz = 48 if narrow else 64
        top = y
        card = cv.card(x0, y, x1, y + 10, None, fill=TH.mix(cv.c("surface_raised"), acc, .05),
                       outline=TH.mix(acc, cv.c("border"), .55), lift=False)
        got = cv.icon(MM.tablet_of(s), x0 + ip, y + ip + 6, isz)
        tx = x0 + ip + (isz + (14 if narrow else 20) if got is not None else 0)
        # the buttons (right; in the Drawer: under the words)
        btns = self._mm_head_buttons(s, post)
        bw_all = sum(cv.tw(b[0], ("Segoe UI", 10, "bold" if b[3] == "primary" else "normal")) + 32 + 8 for b in btns)
        side = not narrow and W - tx - bw_all > 420
        wr = (x1 - ip - bw_all - 16) if side else (x1 - ip)
        cy = y + ip + 4
        x = self._mm_mech_chip(cv, tx, cy, s)
        f9 = ("Segoe UI", 9)
        if s.get("category") and s.get("category") != s.get("type") and x + 70 < wr:
            x = cv.bbox(cv.text(x + 8, cy + 11, s["category"], f9, fill=cv.c("text_muted"), anchor="w"))[2]
        b = MM.budget_of(s)
        if b and x + 90 < wr:
            x = cv.chip(x + 8, cy, b)
        if x + 120 < wr:
            self._mm_effort(cv, x + 12, cy + 11, s, tags=("h_eff",))
            cv.tips["h_eff"] = "Effort: " + MM.THINKING.get(s.get("thoughts_per_click"), ("", "?"))[1]
        ty = cy + 34
        tt = cv.text(tx, ty, ("✔ " if post.get("voted") else "") + s["name"],
                     ("Segoe UI", 16 if narrow else 18, "bold"), fill=cv.c("text_strong"), width=wr - tx)
        ty = cv.bottom(tt, ty + 28) + 6
        if s.get("summary"):
            ty = cv.bottom(cv.text(tx, ty, s["summary"], ("Segoe UI", 10), fill=cv.c("text"), width=wr - tx), ty) + 6
        by = post.get("author", {}).get("name") or s.get("author") or "?"
        lg = MM.league_of(s)
        meta = [f"By {by}", f"updated {_ago_day(s.get('updated'))}",
                lg if lg.startswith(("Game ", "Unknown")) else f"{lg} · game {s.get('patch', '?')}",
                {"community": "Official", "mine": "Mine", "example": "Example", "board": "Community"}.get(s["origin"], "")]
        if post:
            meta.append(f"▲ {post.get('score', 0)} found it useful")
        if post.get("hidden"):
            meta.append("⊘ HIDDEN")
        if (post.get("based_on") or {}).get("id"):
            meta.append(f"based on “{post['based_on'].get('name') or 'another strat'}”")
        if post.get("pending"):
            meta.append(f"{post['pending']} change waiting for reviewers")
        if post.get("mine") and post.get("suggestions"):
            n = post["suggestions"]
            meta.append(f"{n} suggested edit{'s' if n != 1 else ''} for you (More ▾ › Suggestions)")
        ty = cv.bottom(cv.text(tx, ty, " · ".join(m for m in meta if m), f9, fill=cv.c("text_muted"),
                               width=wr - tx), ty) + 4
        bottom = max(ty, y + ip + isz + 12)
        if side:
            by0 = y + (bottom - y) / 2 - 18 + 4
            bx = x1 - ip
            for text, tg, fn, kind, tip in reversed(btns):
                bx0, _ = cv.button(bx, by0, text, tg, fn, kind, anchor="e", h=38, tip=tip)
                bx = bx0 - 8
        else:
            bx, by0 = tx if not narrow else x0 + ip, bottom + 8
            for text, tg, fn, kind, tip in btns:
                bwid = cv.tw(text, ("Segoe UI", 10, "bold" if kind == "primary" else "normal")) + 32
                if bx + bwid > x1 - ip:
                    bx, by0 = (tx if not narrow else x0 + ip), by0 + 46
                _, bx = cv.button(bx, by0, text, tg, fn, kind, h=38, tip=tip)
                bx += 8
            bottom = by0 + 38 + 4
        bottom += ip - 4
        cv.coords(card, *_rr_points(x0, top, x1, bottom, R))
        return bottom

    def _mm_head_buttons(self, s, post):
        """(text, tag, command, kind, tip) - the one orange button last (rightmost)."""
        out = [("More ▾", "h_more", lambda: self.mm_more_at("h_more"), "ghost",
                "Everything you can do with this strat: copy it, export it, suggest an edit, report it…")]
        if post:
            out.insert(0, (f"{'▲ Upvoted' if post.get('voted') else '▲ Upvote'} ({post.get('score', 0)})", "h_vote",
                           self.mm_vote, "ghost", "Remove your upvote" if post.get("voted") else
                           "Upvote it: the best rise to the top"))
        if s["origin"] == "mine":
            out.insert(0, ("📤 Post to Community", "h_post", self.mm_post, "ghost", "Share it on the community board"))
        if s.get("regex"):
            out.insert(0, ("Copy regex", "h_regex", self.mm_copy_regex, "ghost",
                           "Copy the strat's stash search. In game: Ctrl+V in the stash search."))
        out.append(("Run this strat", "h_run", lambda: self.mm_run(self.mm_sel), "primary",
                    "Opens the Strat Tracker on this strat: log your runs, see what it really made."))
        return out

    def _mm_tiles(self, cv, s, mine, pad, y, W, narrow):
        ph = MM.per_hour(s, mine)
        cost = MM.run_cost(s, self.mm_costs())
        prof, rt = MM.run_profit(s), MM.run_time(s)
        busy = s["id"] in getattr(self, "_mm_cost_busy", set())
        tiles = [("PER HOUR", ph, "ph")]
        tiles.append(("COST PER RUN", cost or {"value": None, "sum": "checking the trade site…" if busy else
                                               "not given", "how": "The author gave no cost."}, "cost"))
        if prof:
            tiles.append(("PROFIT PER RUN", prof, "prof"))
        if rt:
            tiles.append(("RUN TIME", rt, "time"))
        cols = 2 if narrow or W < 900 else len(tiles)
        gap = 12
        tw = (W - 2 * pad - (cols - 1) * gap) / cols
        th = 128 if any(k == "ph" and v and (v["high"] > v["low"] or v.get("you") is not None) for _l, v, k in tiles) \
            else 104
        num = (TH.head_font(None, "num"), 20 if narrow else 24)
        if ph and th == 128:
            legend = " · ".join([f"lowest {MM.short_div(ph['low'])}", f"middle {MM.short_div(ph['value'])}",
                                 f"highest {MM.short_div(ph['high'])}"] + ([f"◆ you {MM.short_div(ph['you'])}"]
                                                                          if ph.get("you") is not None else []))
            if cv.tw(legend, ("Segoe UI", 9)) > tw - 32:
                th += 18                                      # (it wraps onto a second line)
        for i, (label, v, kind) in enumerate(tiles):
            x0 = pad + (i % cols) * (tw + gap)
            ty = y + (i // cols) * (th + gap)
            tag = f"tile_{kind}"
            cv.card(x0, ty, x0 + tw, ty + th, None, lift=False)
            lab = cv.text(x0 + 16, ty + 22, label, ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="w")
            how = (v or {}).get("how") or "No estimate given."
            cv.info(cv.bbox(lab)[2] + 6, ty + 22, f"{tag}_i", how)
            if kind == "ph":
                big = (MM.short_div(v["value"]) + " div") if v else "-"
                cv.text(x0 + 16, ty + 36, big, num, fill=cv.c("money"), tags=(tag,))
                if not v:                                # 3.0.6 (New strat): it comes from runs, not a guess
                    how = ("Comes from runs, not a guess: Run this strat and log your runs in the Strat Tracker - "
                           "Your numbers show what it made an hour.")
                    cv.tips[f"{tag}_i"] = how
                    cv.text(x0 + 16, ty + 78, "comes from runs: Run this strat", ("Segoe UI", 9),
                            fill=cv.c("text_muted"), width=tw - 32)
                cv.tips[tag] = how
                if v and (v["high"] > v["low"] or v.get("you") is not None) and tw > 180:
                    cv.range_bar(x0 + 24, x0 + tw - 24, ty + 84, v)
                    bits = [f"lowest {MM.short_div(v['low'])}", f"middle {MM.short_div(v['value'])}",
                            f"highest {MM.short_div(v['high'])}"] + ([f"◆ you {MM.short_div(v['you'])}"]
                                                                    if v.get("you") is not None else [])
                    cv.text(x0 + 16, ty + 104, " · ".join(bits), ("Segoe UI", 9), fill=cv.c("text_muted"),
                            width=tw - 32)
                elif v:
                    cv.text(x0 + 16, ty + 78, v["count"], ("Segoe UI", 9), fill=cv.c("text_muted"), width=tw - 32)
            elif kind == "prof":
                val = v["value"]
                up = val >= 0
                cv.text(x0 + 16, ty + 36, f"{'▲' if up else '▼'} {MM.short_div(abs(val))} div", num,
                        fill=cv.c("good") if up else cv.c("bad"), tags=(tag,))
                cv.text(x0 + 16, ty + 78, ("profit · " if up else "loss · ") + v["sum"], ("Segoe UI", 9),
                        fill=cv.c("text_muted"), width=tw - 32)
                cv.tips[tag] = how
            elif kind == "time":
                cv.text(x0 + 16, ty + 36, MM.mins_text(v["secs"]), num, fill=cv.c("text_strong"), tags=(tag,))
                cv.text(x0 + 16, ty + 78, v["sum"], ("Segoe UI", 9), fill=cv.c("text_muted"), width=tw - 32)
                cv.tips[tag] = how
            else:
                cv.text(x0 + 16, ty + 36, f"{MM.short_div(v['value'])} div" if v.get("value") is not None else "-",
                        num, fill=cv.c("text_strong"), tags=(tag,))
                cv.text(x0 + 16, ty + 78, v["sum"], ("Segoe UI", 9), fill=cv.c("text_muted"), width=tw - 32)
                cv.tips[tag] = how
        rows = -(-len(tiles) // cols)
        return y + rows * th + (rows - 1) * gap

    def _mm_box(self, cv, x0, x1, y, title, tag=None, how=None):
        """A card with a title -> (card item, y under the title)."""
        card = cv.card(x0, y, x1, y + 10, None, lift=False)
        t = cv.text(x0 + 18, y + 26, title, ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w")
        if how:
            cv.info(cv.bbox(t)[2] + 8, y + 26, tag or "box_i", how)
        return card, y + 50

    def _mm_need_card(self, cv, s, mine, x0, x1, y):
        """You need: the items a run takes, as slots (the tablet's picture; no picture - its word). Hover: what it
        is and its price today; click: copy its stash search or open the Trade Site."""
        items = s.get("items") or []
        if not items:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "You need")
        c = (self.mm_costs() or {}).get(s.get("id")) or {}
        prices = c.get("prices") or {}
        sz, gap = 64, 10
        x = x0 + 18
        for i, it in enumerate(items):
            if x + sz > x1 - 18:
                x, yy = x0 + 18, yy + sz + gap
            tag = f"need{i}"
            sl = TH.round_rect(cv, x, yy, x + sz, yy + sz, 6, fill=cv.c("surface_sunken"), outline=cv.c("border"),
                               tags=(tag,))
            cv.lifts[tag] = [(sl, {"outline": cv.c("border")}, {"outline": cv.c("border_light")})]
            base = it.get("base") or ""
            if cv.icon(base, x + sz / 2, yy + sz / 2 - 4, 40, anchor="center", tags=(tag,)) is None:
                word = "Waystone" if it.get("kind") == "waystone" else (base.split()[0] if base else "Item")
                cv.text(x + sz / 2, yy + sz / 2 - 6, cv.fit(word, ("Segoe UI", 9), sz - 6), ("Segoe UI", 9),
                        fill=cv.c("text_muted"), anchor="center", tags=(tag,))
            m = MM.waystone_props(it)
            badge = f"T{m[0]}" if m and m[0] else f"×{it.get('count', 1)}"
            bi = cv.text(x + sz - 5, yy + sz - 4, badge, ("Segoe UI", 9, "bold"), fill=cv.c("text"), anchor="se",
                         tags=(tag,))
            bb = cv.bbox(bi)
            cv.tag_lower(TH.round_rect(cv, bb[0] - 4, bb[1] - 1, bb[2] + 4, bb[3] + 1, 3, fill=cv.c("surface_raised"),
                                       outline=cv.c("border"), tags=(tag,)), bi)
            p = prices.get(str(i))
            last = f" · lasts {it.get('lasts')} runs" if int(it.get("lasts") or 1) > 1 else ""
            tip = (f"{it.get('name') or base} ×{it.get('count', 1)}{last}" +
                   ("".join("\n★ " + km for km in it.get("key_mods") or [])) +
                   (f"\n~{p:.2f} div today (trade site)" if p is not None else "\nno price checked yet") +
                   "\nClick: copy its stash search, or open the Trade Site")
            cv.tips[tag] = tip
            cv.acts[tag] = lambda it=it, tg=tag: self.mm_item_menu(it, tg)
            x += sz + gap
        yy += sz + 12
        names = [f"{it.get('count', 1)} × {it.get('name') or it.get('base')}" for it in items]
        cost = MM.run_cost(s, self.mm_costs())
        line = ", ".join(names) + (f" · {MM.short_div(cost['value'])} div" if cost else "")
        yy = cv.bottom(cv.text(x0 + 18, yy, line, ("Segoe UI", 9), fill=cv.c("text_muted"), width=x1 - x0 - 36),
                       yy + 16) + 10
        tabs = [it for it in items if it.get("kind") != "waystone" and it.get("key_mods")]
        if len(tabs) > 1:
            rx = MM.item_regex(tabs)
            self.mm_all_tabs_rx = rx
            cv.button(x0 + 18, yy, "Copy one search for all the tablets", "need_all",
                      lambda: self.mm_item_copy(rx, "all the tablets"), enabled=bool(rx), h=32,
                      tip="Stash or vendor: Ctrl+V in the search. Trade: the ★ mods, cheapest first.")
            yy += 40
        yy += 8
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_steps_card(self, cv, s, mine, x0, x1, y):
        steps = s.get("steps") or []
        if not steps:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "How it goes")
        for i, line in enumerate(steps, 1):
            cx = x0 + 28
            tid = cv.text(cx + 22, yy, line, ("Segoe UI", 10), fill=cv.c("text"), width=x1 - cx - 40)
            b = cv.bottom(tid, yy + 18)
            cv.create_oval(cx - 10, yy - 2, cx + 10, yy + 18, fill=cv.c("surface_sunken"), outline=cv.c("border"))
            cv.text(cx, yy + 8, str(i), ("Segoe UI", 9, "bold"), fill=cv.c("text_muted"), anchor="center")
            if i < len(steps):
                cv.create_line(cx, yy + 20, cx, b + 10, fill=cv.c("border"))
            yy = b + 14
        yy += 6
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_masters_card(self, cv, s, mine, x0, x1, y):
        """Atlas masters: the strat's master - its name, "N of 4" and the picks."""
        ms = {m: v for m, v in (s.get("masters") or {}).items() if v and m in MM.MASTERS}
        if not ms:
            return y
        card, yy = self._mm_box(cv, x0, x1, y, "Atlas masters", "masters_i",
                                f"The author's master and up to {MM.MASTER_PICKS} of its choices.")
        for m, picks in ms.items():
            t = cv.text(x0 + 18, yy + 7, m, ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="w")
            full = len(picks) >= MM.MASTER_PICKS
            cv.text(cv.bbox(t)[2] + 8, yy + 7, f"{'✓ ' if full else ''}{len(picks)} of {MM.MASTER_PICKS}",
                    ("Segoe UI", 9), fill=cv.c("good") if full else cv.c("text_muted"), anchor="w")
            yy += 20
            x = x0 + 18
            for p in picks:
                w = cv.tw(p, ("Segoe UI", 9)) + 16
                if x > x0 + 18 and x + w > x1 - 18:
                    x, yy = x0 + 18, yy + 28
                x = cv.chip(x, yy, p) + 6
            yy += 22 + 12
        yy += 4
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _mm_yours_card(self, cv, s, mine, x0, x1, y):
        """Your numbers: what your Strat Tracker logged for this strat, or how to start."""
        card, yy = self._mm_box(cv, x0, x1, y, "Your numbers", "yours_i",
                                "From your own Strat Tracker logs for this strat (every setup that follows it).")
        if not mine or not mine.get("runs"):
            yy = cv.bottom(cv.text(x0 + 18, yy, "Not run yet. Run this strat makes a setup for it in the Strat "
                                   "Tracker - your real cost, loot and profit an hour show here.", ("Segoe UI", 9),
                                   fill=cv.c("text_muted"), width=x1 - x0 - 36), yy + 16) + 16
        else:
            from .moneymakers_page import _hms
            parts = ((f"{mine['runs']}", "runs"),
                     (MM.short_div(mine["per_hour"]) if mine.get("per_hour") is not None else "-", "div / hour"),
                     (f"{mine['profit_run']:+.2f}" if mine.get("profit_run") is not None else "-", "div a run"),
                     (_hms(mine["avg_run"]) if mine.get("avg_run") else "-", "a run"))
            cw = (x1 - x0 - 36) / 4
            for i, (big, small) in enumerate(parts):
                x = x0 + 18 + i * cw
                cv.text(x, yy, big, (TH.head_font(None, "num"), 16), fill=cv.c("link") if i == 1 else cv.c("text_strong"))
                cv.text(x, yy + 30, small, ("Segoe UI", 9), fill=cv.c("text_muted"))
            yy += 58
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

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

    def _mm_guide_card(self, cv, s, mine, x0, x1, y):
        """Everything else the guide says: requirements, tablets, atlas (with the author's picture), tips, risks,
        the stash regex, tags, sources."""
        card, yy = self._mm_box(cv, x0, x1, y, "The guide")
        w = x1 - x0 - 36
        tx = x0 + 18
        f, fh, fm = ("Segoe UI", 10), ("Segoe UI", 10, "bold"), ("Segoe UI", 9)

        def head(text):
            nonlocal yy
            yy = cv.bottom(cv.text(tx, yy, text, fh, fill=cv.c("accent_2")), yy + 16) + 4

        def lines(items, num=False):
            nonlocal yy
            for i, line in enumerate(items, 1):
                yy = cv.bottom(cv.text(tx + 4, yy, (f"{i}. " if num else "• ") + line, f, fill=cv.c("text"),
                                       width=w - 4), yy + 16) + 3
            yy += 8
        word, why = MM.THINKING.get(s.get("thoughts_per_click"), ("?", ""))
        cph = s.get("clicks_per_hour", "")
        head("Effort")
        lines([f"{word} - {why}", f"Clicks per hour: {cph} - {MM.CLICKS.get(cph, '')}"])
        if s.get("waystone_tiers"):
            head("Waystone tiers")
            lines([MM.tiers_text(s["waystone_tiers"])])
        tags = s.get("tags") or []
        got = [(g, [x for x in opts if x in tags]) for g, opts in MM.tag_groups().items()]
        got = [(g, xs) for g, xs in got if xs]
        if got:
            head("Tags")
            lines([f"{g}: {' · '.join(xs)}" for g, xs in got])
        if isinstance(s.get("ledger"), dict):
            head("Author's Strat Tracker")
            lines([MM.ledger_text(s["ledger"])])
        if s.get("atlas") or s.get("atlas_image"):
            head("Atlas / master setup")
            ref = s.get("atlas_image")
            if ref:
                from . import stratimg
                path = stratimg.path_of(ref) if ref.startswith("l:") else None
                if ref.startswith("b:"):
                    path = self.mm_board_image(ref, s)
                img = self.strat_thumb(path, min(320, int(w)), 180) if path and hasattr(self, "strat_thumb") else None
                if img is not None:
                    self.mm_atlas_img = img
                    cv.create_image(tx, yy, image=img, anchor="nw", tags=("atlas",))
                    cv.acts["atlas"] = lambda p=path: self.mm_atlas_big(p)
                    cv.tips["atlas"] = "Click to see it big."
                    yy += img.height() + 8
                else:
                    yy = cv.bottom(cv.text(tx, yy, "loading the author's atlas screenshot…" if ref.startswith("b:")
                                           else "The atlas screenshot is missing from this PC.", fm,
                                           fill=cv.c("text_muted")), yy + 14) + 6
            lines(s.get("atlas") or [])
        for key, title in (("requirements", "Requirements"), ("tablets", "Tablets"), ("waystones", "Waystones"),
                           ("craft_steps", "Craft steps"), ("setup", "Other setup"), ("loot", "Loot to sell"),
                           ("tips", "Tips"), ("risks", "Risks")):
            if key in ("tablets", "waystones") and s.get("items"):
                continue                                    # (You need has them)
            if s.get(key):
                head(title)
                lines(s[key])
        if s.get("regex"):
            head("Stash regex")
            rid = cv.text(tx + 4, yy, s["regex"], ("Consolas", 9), fill=cv.c("good"), width=w - 4)
            yy = cv.bottom(rid, yy + 16) + 8
        if s.get("sources"):
            head("Sources")
            import webbrowser
            for i, src in enumerate(s["sources"]):
                tg = f"src{i}"
                si = cv.text(tx + 4, yy, "• " + (src.get("title") or src["url"]), f, fill=cv.c("link"), width=w - 4,
                             tags=(tg,))
                cv.acts[tg] = lambda u=src["url"]: webbrowser.open(u)
                cv.lifts[tg] = [(si, {"fill": cv.c("link")}, {"fill": cv.c("accent")})]
                yy = cv.bottom(si, yy + 16) + 3
            yy += 8
        yy += 4
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy


def _rr_points(x0, y0, x1, y1, r):
    """The points of TH.round_rect (to resize a card drawn before its height was known)."""
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
            x0, y1 - r, x0, y0 + r, x0, y0]


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
