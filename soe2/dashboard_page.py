"""Dashboard (UI overhaul): the first page. Where you stand at a glance - stash worth, today's change, your last map,
today's price checks - three ways in for a new player, your last checks and which helpers are on.

Drawn on one canvas (cards, hairlines, one orange button) so it follows the theme pack exactly. Every number has
an ⓘ hover that says how it was worked out. GGG ToS: looks only - nothing here touches the game."""
import time
import tkinter as tk

from . import buglog
from . import themes as TH
from .config import SETTINGS

PAD, GAP, R = 32, 16, 8           # page margin, gap between cards, card corner (rule 24: soft, smooth)
TILE_H, START_H, LIST_H = 116, 150, 252
MOVERS_H, WORTH_H = 252, 196


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


def visible_parts(wealth_done, price_done, helper_done):
    """Which parts of the Dashboard show: a part is hidden when its feature is off (nothing grayed out), and a Start
    here card is hidden once it is done. -> dict of bools."""
    from . import features as FEAT
    w, p, o = FEAT.on("wealth"), FEAT.on("price"), FEAT.on("overlay")
    try:
        mp = o and FEAT.helper_on("mapprofit")
    except Exception:
        mp = False
    return {"wealth": w, "price": p, "overlay": o, "map": mp,
            "start_price": p and not price_done, "start_wealth": w and not wealth_done,
            "start_overlay": o and not helper_done, "empty": not (w or p or o)}


def share_prompt_due():
    """The Dashboard asks once about Community data sharing: while it is off, and until you answer."""
    return not SETTINGS.get("share_prices") and not SETTINGS.get("dash_share_asked")


def share_prompt_answer(app, yes):
    SETTINGS["dash_share_asked"] = True
    if yes and hasattr(app, "cm_set_sharing"):
        app.cm_set_sharing(True)                             # (saves the settings itself)
    else:
        from .config import save_json
        save_json("settings.json", SETTINGS)


WORTH = (   # things players miss: (page key, tab or None, name, one line)
    ("regex", None, "Regex", "Build a stash search for the mods you want, and paste it in game."),
    ("pricecheck", "Favorites", "Favorites", "Star an item on Price Checks to keep its search one click away."),
    ("rates", "Stockpile", "Stockpile", "List what to buy early in a league, and what to pay for it."),
    ("rates", "Exchange Helper", "Compare a currency", "See what one currency is worth in every other."),
    ("plan", None, "League Plan", "Your league goals in one list, with the next one on the overlay."),
    ("maps", None, "Map Library", "Rank maps by layout and boss, and see the community's ranks."),
    ("leaderboards", None, "Leaderboards", "Your best map, boss and campaign times, against everyone's."),
    ("ratemods", None, "Mod Lab", "Rate mods to make price checks more accurate."),
    ("search", None, "Game Search", "Look up any skill, item or mod in the game's own data."),
)


def worth_items():
    """Worth a look: what you have off first, then what players often miss. -> [(title, line, button, page, tab)]"""
    from . import features as FEAT
    out = []
    for g in FEAT.ALL:
        if not FEAT.on(g["key"]):
            out.append((f"{g['name']} is off", g["what"], "Turn on in Settings", "settings", "General"))
    if FEAT.on("overlay"):
        for key, (_d, _k, name) in FEAT.HELPER_SWITCHES.items():
            try:
                if not FEAT.helper_on(key):
                    out.append((f"{name} is off", "A helper over the game. Its switch is in Overlay › Helpers.",
                                "Open Helpers", "tracker", "Helpers"))
            except Exception:
                buglog.caught()
    mods = {m for g in FEAT.ALL if FEAT.on(g["key"]) for m in g.get("modules", ())}
    for page, tab, name, line in WORTH:
        if page in mods or page in ("rates", "plan", "maps", "leaderboards", "ratemods", "pricecheck"):
            out.append((name, line, f"Open {name}", page, tab))
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
        TH.round_rect(self, x0, y, x1, y + h, 6, fill=fill, outline=line, tags=(tag,))
        self.create_text((x0 + x1) // 2, y + h // 2, text=text, font=f, fill=ink, tags=(tag,))
        self.acts[tag] = fn
        if tip:
            self.tips[tag] = tip
        return x0

    # ---- 3.3.0 owner: the one-time sharing question
    def _share_prompt(self, x0, y, x1, narrow):
        t = TH.ST.theme
        h = 132 if narrow else 84
        self._card(x0, y, x1, y + h)
        self.create_text(x0 + 20, y + 16, text="Share anonymous data with the community?", anchor="nw",
                         font=("Segoe UI", 12, "bold"), fill=t.c("text_strong"))
        self.create_text(x0 + 20, y + 44, text="Mod prices and map ranks. No account or character names.", anchor="nw",
                         font=("Segoe UI", 10), fill=t.c("text_muted"), width=(x1 - x0 - 40) if narrow else 0)
        by = y + h - 44 - 20 if narrow else y + 20
        bx = x1 - 20
        lid = self.create_text(bx, by + 22, text="Learn more", anchor="e", font=("Segoe UI", 10, "underline"),
                               fill=t.c("accent") if self.hover == "sh_more" else t.c("accent_2"), tags=("sh_more",))
        self.acts["sh_more"] = lambda: self.app.cm_ask(info=True) if hasattr(self.app, "cm_ask") else None
        self.tips["sh_more"] = "What is shared, and why"
        bx = self.bbox(lid)[0] - 16
        bx = self._button(bx, by, "No thanks", "sh_no", lambda: (share_prompt_answer(self.app, False), self.later()),
                          tip="Nothing is shared. This is not asked again") - 12
        self._button(bx, by, "Yes, share", "sh_yes", lambda: (share_prompt_answer(self.app, True), self.later()),
                     tip="Turns on Share anonymous data with the community. Its switch is in Settings")
        return y + h

    # ---- 3.3.0 owner: Top Movers and Worth a look
    def _pill(self, x, y, text, tag, on, fn, tip):
        """A small choice: ✓ and a lit edge on the picked one. -> its right edge."""
        t = TH.ST.theme
        lab = ("✓ " if on else "") + text
        tid = self.create_text(x + 12, y + 14, text=lab, anchor="w", font=("Segoe UI", 9, "bold" if on else "normal"),
                               fill=t.c("text_strong") if on else t.c("text_muted"), tags=(tag,))
        bx = self.bbox(tid)
        TH.round_rect(self, x, y, bx[2] + 12, y + 28, 14, fill=t.c("surface_high") if on or self.hover == tag else "",
                      outline=t.c("accent") if on else t.c("border"), tags=(tag,))
        self.tag_raise(tid)
        self.acts[tag], self.tips[tag] = fn, tip
        return bx[2] + 12

    def _extras(self, x0, y, x1, stack):
        from . import features as FEAT
        show_mv = FEAT.on("rates") if "rates" in FEAT.cfg() else True
        show_tips = not SETTINGS.get("dash_worth_off")
        if not (show_mv or show_tips):
            return y
        full = x1 - x0
        both = show_mv and show_tips
        mw = full if (stack or not both) else (full - GAP) * 0.62
        if show_mv:
            self._movers(x0, y, x0 + mw)
            if stack and both:
                y += MOVERS_H + GAP
        if show_tips:
            tx0 = x0 if (stack or not both) else x0 + mw + GAP
            self._worth(tx0, y, x1, MOVERS_H if (both and not stack) else WORTH_H)
            return y + (MOVERS_H if (both and not stack) else WORTH_H) + GAP
        return y + MOVERS_H + GAP

    def _movers(self, x0, y, x1):
        from . import movers as MV
        from .pricefmt import fmt_div
        from .wealth import WPRICES
        t = TH.ST.theme
        head = TH.head_font(t)
        mut, strong, txt = t.c("text_muted"), t.c("text_strong"), t.c("text")
        self._card(x0, y, x1, y + MOVERS_H)
        hid = self.create_text(x0 + 20, y + 18, text="Top Movers", anchor="nw", font=(head, 16), fill=strong)
        iid = self.create_text(self.bbox(hid)[2] + 8, y + 24, text="ⓘ", anchor="nw", font=("Segoe UI Symbol", 10),
                               fill=t.c("accent_2") if self.hover == "mv_info" else mut, tags=("mv_info",))
        del iid
        self.tips["mv_info"] = ("What went up and down the most on the Currency Exchange, from poe.ninja. Daily is "
                                "yesterday against today. Hourly is the app's read an hour ago against now. Thinly "
                                "traded items are left out.")
        mode = SETTINGS.get("dash_movers") if SETTINGS.get("dash_movers") in ("daily", "hourly") else "daily"
        px = x1 - 20
        for key, lab, tip in (("hourly", "Hourly", "The last hour"), ("daily", "Daily", "Yesterday against today")):
            probe = self.create_text(0, 0, text=("✓ " if key == mode else "") + lab,
                                     font=("Segoe UI", 9, "bold" if key == mode else "normal"))
            w = self.bbox(probe)[2] - self.bbox(probe)[0] + 24
            self.delete(probe)
            self._pill(px - w, y + 16, lab, "mv_" + key, key == mode, lambda k=key: self._movers_pick(k), tip)
            px -= w + 8
        league = SETTINGS.get("league")
        age = WPRICES.age() if WPRICES.league == league else None
        if league and (age is None or age > 3600) and time.time() - getattr(self, "_mv_asked", 0) > 600 \
                and hasattr(self.app, "run_bg"):
            self._mv_asked = time.time()                     # poe.ninja, at most hourly, off the window's thread
            self.app.run_bg(lambda: WPRICES.ensure(league), lambda _r: self.later())
        try:
            data = (MV.hourly if mode == "hourly" else MV.daily)(WPRICES) if WPRICES.league == league else None
        except Exception:
            buglog.caught()
            data = None
        if not data or data["empty"]:
            self.create_text(x0 + 20, y + 64, text=(data or {}).get("empty") or "Reading prices from poe.ninja…",
                             anchor="nw", font=("Segoe UI", 10), fill=mut, width=x1 - x0 - 40)
            return
        cw = (x1 - x0 - 40 - GAP) / 2
        for ci, (title, rows, col, mark) in enumerate((("Up", data["up"], t.c("good"), "▲"),
                                                       ("Down", data["down"], t.c("bad"), "▼"))):
            cx = x0 + 20 + ci * (cw + GAP)
            self.create_text(cx, y + 56, text=f"{mark} {title}", anchor="nw", font=("Segoe UI", 9, "bold"), fill=col)
            ry = y + 80
            if not rows:
                self.create_text(cx, ry + 8, text=f"Nothing went {title.lower()}.", anchor="nw", font=("Segoe UI", 10),
                                 fill=mut)
            for i, r in enumerate(rows):
                tag = f"mv{ci}_{i}"
                self.create_line(cx, ry, cx + cw, ry, fill=t.c("border"))
                pid = self.create_text(cx + cw, ry + 16, text=f"{mark} {abs(r['pct']):.0f}%" if abs(r["pct"]) >= 10 else
                                       f"{mark} {abs(r['pct']):.1f}%", anchor="e", font=("Segoe UI", 10, "bold"),
                                       fill=col, tags=(tag,))
                vid = self.create_text(self.bbox(pid)[0] - 12, ry + 16, text=fmt_div(r["div"]), anchor="e",
                                       font=("Segoe UI", 9), fill=mut, tags=(tag,))
                self.create_text(cx, ry + 16, text=r["name"], anchor="w", font=("Segoe UI", 10), fill=txt, tags=(tag,),
                                 width=max(60, self.bbox(vid)[0] - cx - 8))
                self.tips[tag] = r["how"]
                ry += 32

    def _movers_pick(self, key):
        from .config import save_json
        SETTINGS["dash_movers"] = key
        save_json("settings.json", SETTINGS)
        self.later()

    def _worth(self, x0, y, x1, h):
        t = TH.ST.theme
        head = TH.head_font(t)
        mut, strong = t.c("text_muted"), t.c("text_strong")
        self._card(x0, y, x1, y + h)
        self.create_text(x0 + 20, y + 18, text="Worth a look", anchor="nw", font=(head, 16), fill=strong)
        hid = self.create_text(x1 - 20, y + 22, text="✕", anchor="ne", font=("Segoe UI", 10),
                               fill=t.c("text") if self.hover == "wl_hide" else mut, tags=("wl_hide",))
        del hid
        self.acts["wl_hide"] = self._worth_hide
        self.tips["wl_hide"] = "Hide Worth a look. Its switch is in Settings › General › Window"
        try:
            items = worth_items()
        except Exception:
            buglog.caught()
            items = []
        if not items:
            self.create_text(x0 + 20, y + 60, text="Nothing new to show.", anchor="nw", font=("Segoe UI", 10), fill=mut)
            return
        i = self._wl_i = getattr(self, "_wl_i", int(time.time() // 86400)) % len(items)
        title, line, btn, page, tab = items[i]
        self.create_text(x0 + 20, y + 58, text=title, anchor="nw", font=("Segoe UI", 12, "bold"), fill=strong,
                         width=x1 - x0 - 40)
        self.create_text(x0 + 20, y + 86, text=line, anchor="nw", font=("Segoe UI", 10), fill=mut, width=x1 - x0 - 40)
        sh = getattr(self.app, "shell", None)
        by = y + h - 44 - 20
        self._button(x1 - 20, by, btn, "wl_go",
                     (lambda: (sh.open_tab(page, tab) if tab else sh.open(page)) if sh else None))
        px = x0 + 20
        for tag, glyph, step, tip in (("wl_prev", "‹", -1, "The one before"), ("wl_next", "›", 1, "The next one")):
            lit = self.hover == tag
            TH.round_rect(self, px, by + 6, px + 32, by + 38, 6, fill=t.c("surface_high") if lit else "",
                          outline=t.c("border_light") if lit else t.c("border"), tags=(tag,))
            self.create_text(px + 16, by + 21, text=glyph, font=("Segoe UI", 12, "bold"), fill=t.c("text"), tags=(tag,))
            self.acts[tag] = lambda s=step, n=len(items): self._worth_step(s, n)
            self.tips[tag] = tip
            px += 40
        self.create_text(px + 4, by + 22, text=f"{i + 1} of {len(items)}", anchor="w", font=("Segoe UI", 9), fill=mut)

    def _worth_step(self, step, n):
        self._wl_i = (getattr(self, "_wl_i", 0) + step) % max(1, n)
        self.later()

    def _worth_hide(self):
        from .config import save_json
        SETTINGS["dash_worth_off"] = True
        save_json("settings.json", SETTINGS)
        v = getattr(self.app, "dash_worth_var", None)
        if v is not None:
            v.set(False)
        self.later()

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
        try:
            hs = helper_rows()
        except Exception:
            buglog.caught()
            hs = []
        vis = visible_parts(wn is not None, bool(recs), any(on for _n, on in hs))

        # -- header: greeting, one line, the buttons
        y = PAD
        try:                                                 # your community name, if you gave one
            from . import board as B
            who = ((B.session().get("user") or {}).get("name") or "").strip() or "Exile"
        except Exception:
            who = "Exile"
        self.create_text(PAD, y, text=f"{greeting(now)}, {who}", anchor="nw", font=(head, 28), fill=strong)
        if wn and vis["wealth"]:
            sub = f"Your stash is worth {fmt_div(wn['total'])}"
            sub += (f"  ·  ▲ up {fmt_div(wn['today'])} today" if wn["today"] > 0 else
                    f"  ·  ▼ down {fmt_div(-wn['today'])} today" if wn["today"] < 0 else "  ·  no change today")
        else:
            sub = "Where you stand, at a glance."
        sid = self.create_text(PAD, y + 50, text=sub, anchor="nw", font=("Segoe UI", 12), fill=mut)
        # 3.3.0 owner: the online count is on the status bar (app.online_paint), not here
        del sid
        pc_key = SETTINGS.get("pc_key") or "Ctrl+D"
        x = W - PAD
        if vis["price"]:
            x = self._button(x, y + 6, "Price Checks", "b_pc", go("pricecheck"), primary=True,
                             tip=f"In game: hover an item and press {pc_key}. Its price and listings show on Price Checks.") - 12
        if vis["overlay"]:
            self._button(x, y + 6, "Overlay", "b_ov", go("tracker"), tip="Over the game: the session timer and the helpers.")

        y += 96
        look = getattr(self.app, "drawer_look_on", None)
        narrow = W < 900 or bool(look and look())            # D3: in the Drawer the tiles and Start cards wrap, 2 a row
        if share_prompt_due():                               # 3.3.0 owner: asked once, here, while sharing is off
            y = self._share_prompt(PAD, y, W - PAD, narrow) + GAP

        if vis["empty"]:                                     # every part is off: one line, one button
            self._card(PAD, y, W - PAD, y + 150)
            self.create_text(PAD + 24, y + 30, text="Your Dashboard shows the parts you turn on.", anchor="nw",
                             font=(head, 16), fill=strong)
            self._button(W - PAD - 24, y + 80, "Choose features", "b_feat",
                         (lambda: sh.open_tab("settings", "General") if sh else None), primary=True,
                         tip="Opens Settings › General › Features.")
            self._h = y + 150 + PAD
            self.configure(scrollregion=(0, 0, W, self._h))
            return

        # -- the numbers: only the parts whose feature is on; the rest move up and widen
        tiles = []
        if vis["wealth"]:
            if wn:
                tiles.append(("Stash worth", fmt_div(wn["total"]), f"from {wn['n']:,} items · {ago(wn['ts'], now)}", mut,
                              "Every item from your last stash scan, each at the Middle of its listings, added up.", "wealth"))
                d = wn["today"]
                tiles.append(("Today", ("+" if d >= 0 else "−") + fmt_div(abs(d)),
                              "▲ Up" if d > 0 else "▼ Down" if d < 0 else "— No change",
                              good if d > 0 else bad if d < 0 else mut,
                              "Stash worth now, minus your last scan before midnight, or your first scan today.", "wealth"))
            else:
                tiles.append(("Stash worth", "—", "Scan your stash on Wealth", mut,
                              "Shows after your first stash scan on the Wealth page.", "wealth"))
                tiles.append(("Today", "—", "After your first scan", mut, "Stash worth now, minus your last scan before "
                              "midnight.", "wealth"))
        if vis["map"]:
            if mn and mn["map"] is not None:
                tiles.append(("Last map", fmt_div(mn["map"]), f"{mn['name']} · {max(1, mn['secs'] // 60)} min", mut,
                              "Map profit: your inventory after the map, minus before - Currency Exchange items, priced "
                              "by poe.ninja.", "mapprofit"))
            else:
                tiles.append(("Last map", "—", "Shows after your next map", mut,
                              "Map profit: your inventory after a map, minus before. Its switch: Overlay › Helpers.",
                              "mapprofit"))
        if vis["price"]:
            priced = [r for r in today if r.get("est") is not None and not r.get("skip")]
            tiles.append(("Items price checked today", str(len(today)), f"{len(priced)} with a price", mut,
                          f"Items you priced with {pc_key} since midnight.", "pricecheck"))
        tcols = max(1, min(2 if narrow else 4, len(tiles)))
        cw = (W - 2 * PAD - (tcols - 1) * GAP) / tcols

        for i, (label, big, foot, foot_col, how, key) in enumerate(tiles):
            x0 = PAD + (i % tcols) * (cw + GAP)
            ty = y + (i // tcols) * (TILE_H + GAP)
            tag = f"tile{i}"
            self._card(x0, ty, x0 + cw, ty + TILE_H, tag, lit=self.hover == tag)
            self.create_text(x0 + 18, ty + 16, text=label, anchor="nw", font=("Segoe UI", 10), fill=mut, tags=(tag,),
                             width=cw - 56)
            info = f"info{i}"
            self.create_text(x0 + cw - 18, ty + 16, text="ⓘ", anchor="ne", font=("Segoe UI Symbol", 10),
                             fill=brass if self.hover == info else mut, tags=(info,))
            self.tips[info] = how
            self.create_text(x0 + 18, ty + 40, text=big, anchor="nw", font=(num, 28), fill=strong, tags=(tag,))
            self.create_text(x0 + 18, ty + TILE_H - 14, text=foot, anchor="sw", font=("Segoe UI", 9), fill=foot_col,
                             tags=(tag,), width=cw - 36)
            self.acts[tag] = go(key)
        if tiles:
            trows = -(-len(tiles) // tcols)
            y += trows * TILE_H + (trows - 1) * GAP + 36

        # -- start here: the things not done yet (each card goes once it's done)
        starts = [c for c in (
            ("price", "◇", "Know what an item is worth", f"Hover an item in game and press {pc_key}.", "Price Checks →", "pricecheck"),
            ("wealth", "◈", "See what you have earned", "Press Scan stash. Each scan adds a point to your worth over time.", "Wealth →", "wealth"),
            ("overlay", "◆", "Get help while you play", "Helpers over the game: Ritual, Temple, Map profit.", "Overlay →", "tracker"))
            if vis["start_" + c[0]]]
        if starts:
            hid = self.create_text(PAD, y, text="Start here", anchor="nw", font=(head, 16), fill=strong)
            self.create_text(self.bbox(hid)[2] + 12, y + 4, text="Things most players do first.", anchor="nw",
                             font=("Segoe UI", 10), fill=mut)
            y += 34
            # one row at Drawer and Full widths - smaller text and padding when a card is narrow; two a row only on a
            # truly narrow page; fewer cards widen to fill
            base = 3 if (W - 2 * PAD - 2 * GAP) / 3 >= 190 else 2 if W - 2 * PAD >= 380 else 1
            scols = min(base, len(starts))
            sw = (W - 2 * PAD - (scols - 1) * GAP) / scols
            tight = sw < 300                                 # (the Drawer's widths)
            ip, ic = (14, 28) if tight else (18, 34)         # inner padding, icon box
            sh_ = (150 if sw < 230 else 132) if tight else START_H
            tf, lf = (("Segoe UI", 10, "bold"), ("Segoe UI", 9)) if tight else (("Segoe UI", 12, "bold"), ("Segoe UI", 10))
            for i, (_k, glyph, title, line, link, key) in enumerate(starts):
                x0 = PAD + (i % scols) * (sw + GAP)
                sy = y + (i // scols) * (sh_ + GAP)
                tag = f"start{i}"
                lit = self.hover == tag
                self._card(x0, sy, x0 + sw, sy + sh_, tag, lit)
                TH.round_rect(self, x0 + ip, sy + ip, x0 + ip + ic, sy + ip + ic, 6, fill=t.c("surface_sunken"),
                              outline=TH.mix(brass, t.c("surface_raised"), .6), tags=(tag,))
                self.create_text(x0 + ip + ic / 2, sy + ip + ic / 2, text=glyph,
                                 font=("Segoe UI Symbol", 10 if tight else 12), fill=brass, tags=(tag,))
                tid = self.create_text(x0 + ip + ic + 12, sy + ip + ic / 2, text=title, anchor="w", font=tf, fill=strong,
                                       width=sw - (ip + ic + 12) - ip, tags=(tag,))
                ly = max(sy + ip + ic, (self.bbox(tid) or (0, 0, 0, sy))[3]) + (10 if tight else 14)
                self.create_text(x0 + ip, ly, text=line, anchor="nw", font=lf, fill=mut, width=sw - 2 * ip, tags=(tag,))
                self.create_text(x0 + ip, sy + sh_ - (12 if tight else 16), text=link, anchor="sw",
                                 font=(lf[0], lf[1], "bold"), fill=acc if lit else brass, tags=(tag,))
                self.acts[tag] = go(key)
            srows = -(-len(starts) // scols)
            y += srows * sh_ + (srows - 1) * GAP + GAP

        # -- 3.3.0 owner: Top Movers, and Worth a look beside it (under it when the page is narrow)
        try:
            y = self._extras(PAD, y, W - PAD, narrow or bool(look and look()))
        except Exception:
            buglog.caught()

        # -- your last checks / helpers: one alone takes the full width
        stack = bool(look and look())                       # the Drawer: one column - Pick up, then Helpers under it
        both = vis["price"] and vis["overlay"]
        full = W - 2 * PAD
        lw = full if (stack or not both) else (W - 2 * PAD - GAP) * 0.62
        if vis["price"]:
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
            if stack and vis["overlay"]:
                y += LIST_H + GAP
            hx0 = PAD + lw + GAP
        else:
            hx0 = PAD
        if stack and vis["price"] and vis["overlay"]:
            hx0 = PAD
        hw = full if (stack or not both) else W - PAD - hx0
        if vis["overlay"]:
            self._card(hx0, y, hx0 + hw, y + LIST_H)
            self.create_text(hx0 + 20, y + 18, text="Helpers", anchor="nw", font=(head, 16), fill=strong)
            # nav phase 2: every helper is on Overlay › Helpers (was the Overlay Settings page)
            self.create_text(hx0 + hw - 20, y + 22, text="All helpers", anchor="ne", font=("Segoe UI", 10),
                             fill=acc if self.hover == "ovhelpers" else brass, tags=("ovhelpers",))
            self.acts["ovhelpers"] = (lambda: sh.open_tab("tracker", "Helpers") if sh else None)
            hy = y + 56
            for name, on in hs[:4]:
                self.create_line(hx0 + 20, hy, hx0 + hw - 20, hy, fill=t.c("border"))
                self.create_text(hx0 + 20, hy + 24, text=name, anchor="w", font=("Segoe UI", 10), fill=txt if on else mut)
                chip = "✓ On" if on else "– Off"
                col = good if on else mut
                cid = self.create_text(hx0 + hw - 32, hy + 24, text=chip, anchor="e", font=("Segoe UI", 9, "bold"), fill=col)
                bx = self.bbox(cid)
                TH.round_rect(self, bx[0] - 10, bx[1] - 4, bx[2] + 10, bx[3] + 4, 10, fill="",
                              outline=TH.mix(col, t.c("surface_raised"), .55))
                hy += 48

        self._h = y + (LIST_H if (vis["price"] or vis["overlay"]) else -GAP) + PAD
        self.configure(scrollregion=(0, 0, W, self._h))
