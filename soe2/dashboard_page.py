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
TILE_H, START_H, LIST_H = 100, 150, 252
MOVERS_H, WORTH_H, WORTH_H_NARROW = 252, 196, 236
UPNEXT_H = 48                     # Up next as a row along the bottom of Feature Spotlight on a narrow page


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


def greeting(now=None, name=""):
    """The hello on top: greetings.py has the lines (3.3.0)."""
    from . import greetings as GR
    return GR.greeting(name, now)


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


def stash_line(wn, now=None):
    """The Dashboard's line about your stash -> (what it was worth at your last scan, a nudge to scan again or "").
    3.3.0 owner: the worth is as old as the scan, so it says when - and an older one invites a new scan by what you
    gain from it, never by what you missed."""
    if not wn:
        return "", ""
    from . import focus as F
    from .pricefmt import fmt_div
    now = now or time.time()
    age = max(0, now - (wn.get("ts") or now))
    text = f"Your stash was worth {fmt_div(wn['total'])} on your last scan, {F.ago(wn.get('ts') or now, now)}"
    if age < 6 * 3600:
        if wn["today"] > 0:
            text += f"  ·  ▲ up {fmt_div(wn['today'])} today"
        elif wn["today"] < 0:
            text += f"  ·  ▼ down {fmt_div(-wn['today'])} today"
        return text, ""
    return text + ".", ("Scan again to see what you've earned since" if age >= 86400 else
                        "Scan again to see today's gains")


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


def usage_prompt_due():
    """3.3.0 owner: Count me as a user is asked once on the Dashboard too, beside data sharing."""
    from . import usage as US
    return not US.on() and not SETTINGS.get("dash_usage_asked")


def usage_prompt_answer(yes):
    from . import usage as US
    SETTINGS["dash_usage_asked"] = True
    US.set_on(bool(yes))                                     # saves the settings itself


def share_prompt_answer(app, yes):
    SETTINGS["dash_share_asked"] = True
    if yes and hasattr(app, "cm_set_sharing"):
        app.cm_set_sharing(True)                             # (saves the settings itself)
    else:
        from .config import save_json
        save_json("settings.json", SETTINGS)


# 3.3.0 owner: Feature Spotlight as a carousel. Each card: the surprising part first, then how it works, then the best
# bit - told the way you'd show a friend something cool. No sales words, nothing telling you what to do.
# (page, tab, line icon, name, headline, how it works, the best bit)
WORTH = (
    ("leaderboards", None, "trophy", "Leaderboards", "You already have a *best time*. You haven't seen it yet.",
     "The game writes down every zone you enter. So the app already knows how long each *map*, *boss* and *act* took "
     "you, without you pressing anything.", "Your best sits next to everyone else's."),
    ("regex", None, "regex", "Regex", "Stop reading *60 items* one by one.",
     "Tick the mods you care about and Regex *writes the stash search* for you. Paste it into the game's search box.",
     "Every item that matches lights up. One paste, whole tab."),
    ("plan", None, "flag", "League Plan", "Got ADHD? *Lose track* of your goals?",
     "League Plan keeps your league goals in one list and puts the *next one on the overlay*, so it's always in the "
     "corner of your eye. It reads levels, maps and boss runs from the game's log, and your net worth from Wealth.",
     "Type \"Level 90\" once. The bars fill themselves."),
    ("rates", "Stockpile", "coins", "Stockpile", "It *watches the price* so you don't have to.",
     "Put an item on your Stockpile with *the most you'd pay*. The app checks poe.ninja for you.",
     "When the price drops under your number, it tells you next time you're back in town."),
    ("pricecheck", "Favorites", "star", "Favorites", "Checking the same item every day? *Star it*.",
     "A starred item keeps its whole trade search, filters and all. *One click* runs it again at today's prices.",
     "No retyping anything."),
    ("maps", None, "map", "Map Library", "Not every map is *worth your waystone*.",
     "Map Library *ranks every map* from S to Avoid. Add your own ranks, and see how everyone else ranked them.",
     "Know before you slot it."),
    ("ratemods", None, "rate", "Mod Lab", "You know which mods are good. *Tell the price checker*.",
     "Rate mods from *S to F*. Your ratings join everyone else's, and price checks learn which mods buyers pay for.",
     "A few minutes makes every price check sharper."),
    ("search", None, "search", "Game Search", "*Every skill, item and mod* in the game, one search box.",
     "Game Search looks through the game's own data, *thousands of entries*, as fast as you type.",
     "No wiki tab needed."),
)


def marked(text):
    """A line with *key words* -> [(word, is a key word, joined to the word before it)], for drawing the key words
    in the accent color. A full stop right after a key word stays against it."""
    out = []
    for i, part in enumerate(text.split("*")):
        words = part.split()
        for j, w in enumerate(words):
            glued = j == 0 and bool(out) and not part[:1].isspace() and not text.split("*")[i - 1][-1:].isspace()
            out.append((w, bool(i % 2), glued))
    return out


def plain(text):
    return text.replace("*", "")


def worth_items():
    """Feature Spotlight's cards: what players often miss, then what you have switched off.
    -> [{page, tab, icon, name, head, body, punch, button}]"""
    from . import features as FEAT
    out = [{"page": p, "tab": tab, "icon": ic, "name": name, "head": head, "body": body, "punch": punch,
            "button": f"Open {name}"} for p, tab, ic, name, head, body, punch in WORTH]
    for g in FEAT.ALL:
        if not FEAT.on(g["key"]):
            out.append({"page": "settings", "tab": "General", "icon": "layers", "name": g["name"],
                        "head": f"{g['name']} is switched off.", "body": g["what"], "punch": "",
                        "button": "Turn on in Settings"})
    if FEAT.on("overlay"):
        for key, (_d, _k, name) in FEAT.HELPER_SWITCHES.items():
            try:
                if not FEAT.helper_on(key):
                    out.append({"page": "tracker", "tab": "Helpers", "icon": "layers", "name": name,
                                "head": f"{name} is switched off.", "body": "A helper that sits over the game.",
                                "punch": "Its switch is in Overlay › Helpers.", "button": "Open Helpers"})
            except Exception:
                buglog.caught()
    return out


def worth_secs(item):
    """How long a card stays up: long enough to read all of it at an easy pace, never under 14 seconds."""
    words = len(plain(" ".join((item["head"], item["body"], item["punch"]))).split())
    return max(14.0, 6.0 + words / 2.6)


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
        """A box in the theme's shape."""
        TH.box(self, TH.ST.theme, x0, y0, x1, y1, R, lit=lit, tags=(tag,) if tag else ())

    def _rich(self, x, y, text, font, fill, hi, width, hi_font=None):
        """A wrapped line whose *key words* are drawn in the accent color. -> its bottom."""
        import tkinter.font as tkfont
        fonts = self.__dict__.setdefault("_fonts", {})
        f = fonts.get(font) or fonts.setdefault(font, tkfont.Font(root=self, font=font))
        hf_key = hi_font or font
        hf = fonts.get(hf_key) or fonts.setdefault(hf_key, tkfont.Font(root=self, font=hf_key))
        space, lh = f.measure(" "), f.metrics("linespace") + 3
        cx, cy = x, y
        for word, key, glued in marked(text):
            w = (hf if key else f).measure(word)
            if glued:
                cx -= space
            elif cx > x and cx + w > x + width:
                cx, cy = x, cy + lh
            self.create_text(cx, cy, text=word, anchor="nw", font=hf_key if key else font, fill=hi if key else fill)
            cx += w + space
        return cy + lh

    def _r(self, r):
        """A corner for a button or a chip: round only in a theme whose boxes are round."""
        return r if TH.box_look(TH.ST.theme)["shape"] == "round" else 0

    def _line_h(self, font):
        """One line's height in this font, as this screen draws it."""
        import tkinter.font as tkfont
        fonts = self.__dict__.setdefault("_line_fonts", {})
        f = fonts.get(font) or fonts.setdefault(font, tkfont.Font(root=self, font=font))
        return f.metrics("linespace")

    def _top(self):
        """How far a box's content starts under its top edge: under its title."""
        return TH.BOX_HEAD + 4 if TH.headed(TH.ST.theme) else 52

    def _patch_notes(self, x0, y, x1):
        """The 3 newest patch posts. Click one: Steam's page with the full notes, in the browser."""
        from . import patchnotes as PN
        PN.refresh(done=lambda: self.after(0, self.redraw) if hasattr(self, "redraw") else None)
        rows = PN.latest(3)
        t = TH.ST.theme
        mut, acc, brass = t.c("text_muted"), t.c("accent"), t.c("accent_2")
        plain_f, bold = ("Segoe UI", 10), ("Segoe UI", 10, "bold")
        rh = self._line_h(bold) + 20
        top = self._top()
        h = top + max(1, len(rows)) * rh + 8
        self._card(x0, y, x1, y + h)
        _hid, up = self._head(x0, y, x1, "Patch Notes")
        feed, quiet = PN.admin_state()
        if quiet and self._is_admin():                       # admins: the board read nothing for a week
            self.create_text(x1 - 20, y + 22 - up, anchor="ne", tags=("pn_feed",), fill=acc,
                             text="● Feed needs a look" if feed else "● Set the forum address",
                             font=("Segoe UI", 10, "underline" if self.hover == "pn_feed" else "bold"))
            self.acts["pn_feed"] = self._pn_set_feed
            self.tips["pn_feed"] = ("Admin: the board read no patch notes from the forum for a week. Paste the "
                                    "address of GGG's Path of Exile 2 patch-notes forum.")
        if not rows:
            self.create_text(x0 + 20, y + top + rh / 2, anchor="w", font=plain_f, fill=mut, width=x1 - x0 - 40,
                             text="No patch notes yet.")
            return y + h + GAP
        import webbrowser
        from . import newchip
        for i, n in enumerate(rows):
            ry = y + top + i * rh
            if i:
                self.create_line(x0 + 20, ry, x1 - 20, ry, fill=t.c("border"))
            tag = f"pn_{i}"
            lit = self.hover == tag
            tx = x0 + 20
            if PN.is_new(n):                                 # 3.3.0 owner: NEW until you open it
                from .sidebar import ink_on                  # the same chip as the rail's
                from .style import C
                tx = newchip.draw(self, tx, ry + rh / 2, C["accent"], ink_on(C["accent"]), anchor="w", size=8) + 8
            # 3.3.0 owner: "<title> - Steam - Wed, September 2, 2026"
            tail = " - ".join(p for p in (PN.source_of(n), PN.day_of(n)) if p)
            tid = self.create_text(tx, ry + rh / 2, anchor="w", text=n["title"], tags=(tag,),
                                   font=("Segoe UI", 10, "bold underline") if lit else bold, fill=acc if lit else brass)
            if tail:
                self.create_text(self.bbox(tid)[2], ry + rh / 2, anchor="w", text=" - " + tail, font=plain_f,
                                 fill=mut, tags=(tag,))

            def go(u=n["url"]):
                PN.mark_seen(u)
                webbrowser.open(u)
                self.later()
            self.acts[tag] = go
        return y + h + GAP

    def _is_admin(self):
        try:
            return bool(self.app.share_is_admin())
        except Exception:
            return False

    def _pn_set_feed(self):
        from tkinter import simpledialog, messagebox
        from . import patchnotes as PN
        feed, _q = PN.admin_state()
        url = simpledialog.askstring("Patch Notes", "Address of GGG's Path of Exile 2 patch-notes forum:",
                                     initialvalue=feed or "https://www.pathofexile.com/forum/", parent=self)
        if not url:
            return
        ok, data = PN.set_feed(url)
        if not ok:
            messagebox.showerror("Patch Notes", str(data), parent=self)
            return
        PN.refresh(done=lambda: self.after(0, self.redraw), force=True)

    def _head(self, x0, y, x1, title):
        """A box's title in the theme's style. -> (the title's id, how far the controls beside it move up)."""
        return TH.box_head(self, TH.ST.theme, x0, y, x1, R, title)

    def _button(self, x1, y, text, tag, fn, primary=False, tip=None, strong=False):
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
            if strong:                                       # a second button that asks to be pressed: the accent edge
                line, ink = acc, t.c("text_strong")
        TH.round_rect(self, x0, y, x1, y + h, self._r(6), fill=fill, outline=line, tags=(tag,))
        self.create_text((x0 + x1) // 2, y + h // 2, text=text, font=f, fill=ink, tags=(tag,))
        self.acts[tag] = fn
        if tip:
            self.tips[tag] = tip
        return x0

    # ---- 3.3.0 owner: the one-time Count me as a user question
    def _usage_prompt(self, x0, y, x1, narrow):
        t = TH.ST.theme
        h = 132 if narrow else 84
        self._card(x0, y, x1, y + h)
        self.create_text(x0 + 20, y + 16, text="Count me as a user?", anchor="nw",
                         font=("Segoe UI", 12, "bold"), fill=t.c("text_strong"))
        self.create_text(x0 + 20, y + 44, text="A random id every 10 minutes, so we know how many people play. "
                         "Nothing else.", anchor="nw", font=("Segoe UI", 10), fill=t.c("text_muted"),
                         width=(x1 - x0 - 40) if narrow else 0)
        by = y + h - 44 - 20 if narrow else y + 20
        bx = self._button(x1 - 20, by, "No thanks", "us_no", lambda: (usage_prompt_answer(False), self.later())) - 12
        self._button(bx, by, "Yes, count me", "us_yes", lambda: (usage_prompt_answer(True), self.later()))
        return y + h

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

    # ---- 3.3.0 owner: Top Movers and Feature Spotlight
    def _pill(self, x, y, text, tag, on, fn, tip):
        """A small choice: ✓ and a lit edge on the picked one. -> its right edge."""
        t = TH.ST.theme
        lab = ("✓ " if on else "") + text
        tid = self.create_text(x + 12, y + 14, text=lab, anchor="w", font=("Segoe UI", 9, "bold" if on else "normal"),
                               fill=t.c("text_strong") if on else t.c("text_muted"), tags=(tag,))
        bx = self.bbox(tid)
        TH.round_rect(self, x, y, bx[2] + 12, y + 28, self._r(14), fill=t.c("surface_high") if on or self.hover == tag else "",
                      outline=t.c("accent") if on else t.c("border"), tags=(tag,))
        self.tag_raise(tid)
        self.acts[tag], self.tips[tag] = fn, tip
        return bx[2] + 12

    def _extras(self, x0, y, x1, stack):
        from . import features as FEAT
        if not SETTINGS.get("dash_worth_off"):
            h = (WORTH_H_NARROW + UPNEXT_H if stack else WORTH_H) + (TH.BOX_HEAD - 12 if TH.headed(TH.ST.theme) else 0)
            self._worth(x0, y, x1, h, stack)
            y += h + GAP
        else:
            self._wl_box = None
        if FEAT.on("rates") if "rates" in FEAT.cfg() else True:
            self._movers(x0, y, x1)
            y += MOVERS_H + GAP
        return y

    def _upcoming(self, x0, y, x1, narrow):
        """The next 3 events, a row each: what it is, its name, when, and its reminder. -> the y under it."""
        from . import calendar_data as CD
        from .calendar_page import kind_color
        sh = getattr(self.app, "shell", None)
        mod = getattr(sh, "modules", {}).get("calendar") if sh else None
        if mod is None or not sh.visible(mod):
            return y
        t = TH.ST.theme
        mut, txt, acc, brass = t.c("text_muted"), t.c("text"), t.c("accent"), t.c("accent_2")
        now = time.time()
        rows = CD.upcoming(now=now, n=3)
        bold, plain_f = ("Segoe UI", 10, "bold"), ("Segoe UI", 10)
        lh = max(self._line_h(bold), self._line_h(plain_f))
        rh = (2 * lh + 20) if narrow else (lh + 24)
        top = self._top()
        h = top + max(1, len(rows)) * rh + 8
        self._card(x0, y, x1, y + h)
        _hid, up = self._head(x0, y, x1, "Upcoming")
        self.create_text(x1 - 20, y + 22 - up, text="Open Calendar", anchor="ne", font=plain_f,
                         fill=acc if self.hover == "cal_open" else brass, tags=("cal_open",))
        self.acts["cal_open"] = lambda: sh.open("calendar")
        self.tips["cal_open"] = "Every league, Twitch Drops campaign, event and race, by month."
        try:                                                 # admins: drafts from Steam news that wait for a review
            waiting = self.app.cal_drafts_count()
        except Exception:
            waiting = 0
        if waiting:
            ox = self.bbox(self.find_withtag("cal_open")[0])[0]
            self.create_text(ox - 20, y + 22 - up, anchor="ne", tags=("cal_drafts",),
                             text=f"● {waiting} draft{'s' if waiting != 1 else ''} to review",
                             font=("Segoe UI", 10, "underline" if self.hover == "cal_drafts" else "bold"), fill=acc)
            self.acts["cal_drafts"] = lambda: (sh.open("calendar"), self.app.cal_drafts())
            self.tips["cal_drafts"] = "Admin: events the board drafted from Steam news. None reaches a user until you post it."
        if not rows:
            self.create_text(x0 + 20, y + top + rh / 2, anchor="w", font=plain_f, fill=mut, width=x1 - x0 - 40,
                             text="Nothing coming up yet.")
            return y + h + GAP
        fonts = self._line_fonts
        col = max(fonts[bold].measure(CD.label(e)) for e in rows) + 24
        for i, ev in enumerate(rows):
            ry = y + top + i * rh
            if i:
                self.create_line(x0 + 20, ry, x1 - 20, ry, fill=t.c("border"))
            tag = f"cal_r{i}"
            has = bool(CD.reminders(ev))
            lit = self.hover == tag
            rid = self.create_text(x1 - 20, ry + rh / 2, anchor="e", tags=(tag,),
                                   text="✓ Reminder set" if has else "Remind me",
                                   font=("Segoe UI", 10, "underline") if lit else plain_f,
                                   fill=txt if has else (acc if lit else brass))
            self.acts[tag] = lambda i=ev["id"]: self.app.cal_remind_me(i)
            self.tips[tag] = ("Click to take the reminder off." if has else
                              "One click: this PC tells you 1 day before, and at the start.")
            room = self.bbox(rid)[0] - 16
            y1 = ry + (10 if narrow else rh / 2)
            anchor = "nw" if narrow else "w"
            self.create_text(x0 + 20, y1, text=CD.label(ev), anchor=anchor, font=bold, fill=kind_color(ev["kind"]))
            when = CD.when_line(ev, now)
            wtag = f"cal_w{i}"
            self.tips[wtag] = f"Starts {CD.starts_line(ev, now)}. Ends: {CD.ends_line(ev)}. Shown in this PC's time."
            if narrow:
                self.create_text(x0 + 20 + col, y1, text=ev["name"], anchor="nw", font=plain_f, fill=txt,
                                 width=max(60, room - x0 - 20 - col))
                self.create_text(x0 + 20 + col, y1 + lh + 2, text=when, anchor="nw", font=plain_f, fill=mut,
                                 tags=(wtag,))
            else:
                wid = self.create_text(room, y1, text=when, anchor="e", font=plain_f, fill=mut, tags=(wtag,))
                name_room = self.bbox(wid)[0] - 16 - (x0 + 20 + col)
                name = ev["name"]
                while len(name) > 4 and fonts[plain_f].measure(name) > name_room:
                    name = name[:-2].rstrip() + "…"
                self.create_text(x0 + 20 + col, y1, text=name, anchor="w", font=plain_f, fill=txt)
        return y + h + GAP

    def _movers(self, x0, y, x1):
        from . import movers as MV
        from .pricefmt import fmt_div
        from .wealth import WPRICES
        t = TH.ST.theme
        head = TH.head_font(t)
        mut, strong, txt = t.c("text_muted"), t.c("text_strong"), t.c("text")
        self._card(x0, y, x1, y + MOVERS_H)
        hid, up = self._head(x0, y, x1, "Top Movers")
        hb = self.bbox(hid)
        iid = self.create_text(hb[2] + 8, (hb[1] + hb[3]) // 2, text="ⓘ", anchor="w", font=("Segoe UI Symbol", 10),
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
            self._pill(px - w, y + 16 - up, lab, "mv_" + key, key == mode, lambda k=key: self._movers_pick(k), tip)
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

    def _worth(self, x0, y, x1, h, stack=False):
        """Feature Spotlight (owner's pick D): one card featured, the next two beside it. It moves on by itself."""
        from . import lineicons
        t = TH.ST.theme
        head = TH.head_font(t)
        mut, strong, txt, acc = t.c("text_muted"), t.c("text_strong"), t.c("text"), t.c("accent")
        self._wl_box = (x0, y, x1, y + h)
        try:
            items = worth_items()
        except Exception:
            buglog.caught()
            items = []
        if not items:
            return
        n = len(items)
        i = self._wl_i = getattr(self, "_wl_i", int(time.time() // 86400)) % n
        it = items[i]
        self._wl_n, self._wl_secs = n, worth_secs(it)
        side = 0 if stack else min(300, (x1 - x0) * 0.3)
        fx1 = x1 - side                                       # 3.3.0 owner: one box - Up next is its right column
        hd_on = TH.headed(t)
        top = TH.BOX_HEAD if hd_on else 0
        self._card(x0, y, x1, y + h)
        if hd_on:
            self._head(x0, y, x1, "Feature Spotlight")
        xy = y + (TH.BOX_HEAD // 2 if hd_on else 24)
        hid = self.create_text((x1 if hd_on else fx1) - 20, xy, text="✕", anchor="e", font=("Segoe UI", 10),
                               fill=txt if self.hover == "wl_hide" else mut, tags=("wl_hide",))
        # 3.3.0 owner: a way through the cards at every width - an arrow each side of the count
        nid = self.create_text(self.bbox(hid)[0] - 16, xy, text="›", anchor="e", font=("Segoe UI", 14, "bold"),
                               fill=acc if self.hover == "wl_fwd" else txt, tags=("wl_fwd",))
        cid = self.create_text(self.bbox(nid)[0] - 10, xy, text=f"{i + 1} of {n}", anchor="e", font=("Segoe UI", 9),
                               fill=mut)
        self.create_text(self.bbox(cid)[0] - 10, xy, text="‹", anchor="e", font=("Segoe UI", 14, "bold"),
                         fill=acc if self.hover == "wl_back" else txt, tags=("wl_back",))
        self.acts["wl_fwd"], self.tips["wl_fwd"] = (lambda: self._worth_step(1)), "The next feature"
        self.acts["wl_back"], self.tips["wl_back"] = (lambda: self._worth_step(-1)), "The feature before"
        self.acts["wl_hide"] = self._worth_hide
        self.tips["wl_hide"] = "Hide Feature Spotlight. Its switch is in Settings › General › Window"
        cy = y + top
        img = lineicons.icon(self, it["icon"], 28, acc)
        self._wl_imgs = []
        if img:
            self._wl_imgs.append(img)
            self.create_image(x0 + 40, cy + 40, image=img)
        tw = fx1 - x0 - 76 - 24
        kick = it["name"].upper() if hd_on else f"FEATURE SPOTLIGHT  ·  {it['name'].upper()}"
        self.create_text(x0 + 76, cy + 16, text=kick, anchor="nw", font=("Segoe UI", 9, "bold"), fill=acc)
        by = self._rich(x0 + 76, cy + 36, it["head"], (head, 18), strong, acc, tw) + 6
        by = self._rich(x0 + 76, by, it["body"], ("Segoe UI", 10), txt, acc, tw, ("Segoe UI", 10, "bold")) + 4
        if it["punch"]:
            self.create_text(x0 + 76, by, text=it["punch"], anchor="nw", font=("Segoe UI", 10, "bold"), fill=strong,
                             width=tw)
        sh = getattr(self.app, "shell", None)
        foot = UPNEXT_H if stack else 0                       # (a narrow page: Up next is a row along the bottom)
        self._button(fx1 - 20, y + h - foot - 44 - 16, it["button"], "wl_go", strong=True, fn=
                     (lambda p=it["page"], tab=it["tab"]: (sh.open_tab(p, tab) if tab else sh.open(p)) if sh else None))
        # the time left: a thin line along the bottom, moved by _worth_tick - nothing else is redrawn for it
        self._wl_bar = self.create_line(x0 + 12, y + h - 2, x0 + 12, y + h - 2, fill=acc, width=2)
        self._wl_span = (x0 + 12, fx1 - 12, y + h - 2)
        self._worth_bar()
        if stack:
            uy = y + h - foot
            self.create_line(x0 + 1, uy, x1 - 1, uy, fill=t.c("border"))
            lid = self.create_text(x0 + 20, uy + foot / 2, text="UP NEXT", anchor="w", font=("Segoe UI", 9, "bold"),
                                   fill=mut)
            ux = self.bbox(lid)[2] + 12
            cwid = (x1 - 1 - ux) / 2
            for k in (1, 2):
                nx = items[(i + k) % n]
                tag = f"wl_n{k}"
                cx0 = ux + (k - 1) * cwid
                lit = self.hover == tag
                self.create_rectangle(cx0, uy + 1, cx0 + cwid, y + h - 3, outline="", tags=(tag,),
                                      fill=t.c("hover", t.c("surface_high")) if lit else
                                      t.c("surface" if TH.box_look(t)["shape"] == "flat" else "surface_raised"))
                self.create_line(cx0, uy + 10, cx0, y + h - 12, fill=t.c("border"))
                im = lineicons.icon(self, nx["icon"], 18, acc)
                if im:
                    self._wl_imgs.append(im)
                    self.create_image(cx0 + 24, uy + foot / 2, image=im, tags=(tag,))
                self.create_text(cx0 + 44, uy + foot / 2, text=nx["name"], anchor="w", font=("Segoe UI", 10, "bold"),
                                 fill=txt, width=max(40, cwid - 70), tags=(tag,))
                self.create_text(cx0 + cwid - 14, uy + foot / 2, text="›", anchor="e", font=("Segoe UI", 12), fill=mut,
                                 tags=(tag,))
                self.acts[tag] = lambda s=k: self._worth_step(s)
                self.tips[tag] = "Show this one now"
        if side:                                             # up next: the two after it; a click jumps there
            self.create_line(fx1, cy + (1 if hd_on else 16), fx1, y + h - (1 if hd_on else 16), fill=t.c("border"))
            self.create_text(fx1 + 20, cy + 18, text="UP NEXT", anchor="nw", font=("Segoe UI", 9, "bold"), fill=mut)
            ry0 = cy + 44
            rh = (y + h - 2 - ry0) / 2
            for k in (1, 2):
                nx = items[(i + k) % n]
                tag = f"wl_n{k}"
                ry = ry0 + (k - 1) * rh
                lit = self.hover == tag
                self.create_rectangle(fx1 + 1, ry, x1 - 1, ry + rh, outline="", tags=(tag,),
                                      fill=t.c("hover", t.c("surface_high")) if lit else
                                      t.c("surface" if TH.box_look(t)["shape"] == "flat" else "surface_raised"))
                self.create_line(fx1 + 20, ry, x1 - 20, ry, fill=t.c("border"))
                im = lineicons.icon(self, nx["icon"], 20, acc)
                if im:
                    self._wl_imgs.append(im)
                    self.create_image(fx1 + 30, ry + rh / 2, image=im, tags=(tag,))
                self.create_text(fx1 + 54, ry + rh / 2, text=nx["name"], anchor="w", font=("Segoe UI", 10, "bold"),
                                 fill=txt, width=x1 - fx1 - 90, tags=(tag,))
                self.create_text(x1 - 20, ry + rh / 2, text="›", anchor="e", font=("Segoe UI", 12), fill=mut, tags=(tag,))
                self.acts[tag] = lambda s=k: self._worth_step(s)
                self.tips[tag] = "Show this one now"
        self._worth_arm()

    def _worth_bar(self):
        try:
            a, b, yy = self._wl_span
            f = min(1.0, getattr(self, "_wl_t", 0.0) / max(1.0, self._wl_secs))
            self.coords(self._wl_bar, a, yy, a + (b - a) * f, yy)
        except (tk.TclError, AttributeError):
            pass

    def _worth_paused(self):
        """No turning while you're reading it (the mouse is on it), while the Dashboard isn't on screen, or while
        the app is in the background - nothing runs then but this one check."""
        box = getattr(self, "_wl_box", None)
        if not box or not self.winfo_viewable():
            return True
        try:
            if self.app.root.focus_displayof() is None:
                return True
            px = self.canvasx(self.winfo_pointerx() - self.winfo_rootx())
            py = self.canvasy(self.winfo_pointery() - self.winfo_rooty())
        except (tk.TclError, AttributeError, KeyError):
            return True
        return box[0] <= px <= box[2] and box[1] <= py <= box[3]

    WL_TICK = 0.5

    def _worth_arm(self):
        if getattr(self, "_wl_job", None) is None:
            self._wl_job = self.after(int(self.WL_TICK * 1000), self._worth_tick)

    def _worth_tick(self):
        self._wl_job = None
        if not self.winfo_exists() or SETTINGS.get("dash_worth_off") or not getattr(self, "_wl_box", None):
            return                                           # (armed again by the next draw that shows the card)
        if not self._worth_paused():
            self._wl_t = getattr(self, "_wl_t", 0.0) + self.WL_TICK
            if self._wl_t >= self._wl_secs:
                self._worth_step(1)
            else:
                self._worth_bar()
        self._worth_arm()

    def _worth_step(self, step, n=None):
        self._wl_i = (getattr(self, "_wl_i", 0) + step) % max(1, n or getattr(self, "_wl_n", 1))
        self._wl_t = 0.0
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
            who = ((B.session().get("user") or {}).get("name") or "").strip()
        except Exception:
            who = ""
        try:
            hello = greeting(now, who)
        except Exception:
            buglog.caught()
            hello = f"Good day, {who or 'Exile'}"
        room = max(240, W - 2 * PAD - 300)                   # (the two buttons sit at the right)
        gid = self.create_text(PAD, y, text=hello, anchor="nw", font=(head, 28 if len(hello) <= 34 else 20),
                               fill=strong, width=room)
        hello_bottom = self.bbox(gid)[3]
        sub, nudge = stash_line(wn, now) if vis["wealth"] else ("", "")
        # 3.3.0 owner: "12 exiles online · 340 this week" under the greeting; its hover says what it counts
        from . import usage as US
        try:
            on_now, on_week = US.line()
        except Exception:
            buglog.caught()
            on_now = on_week = ""
        ly = max(y + 50, hello_bottom + 6)
        if on_now or on_week:
            oid = self.create_text(PAD, ly, text=on_now, anchor="nw", font=("Segoe UI", 12), fill=t.c("accent_2"),
                                   tags=("online",))
            ox = self.bbox(oid)[2] if on_now else PAD
            self.create_text(ox, ly, text=on_week, anchor="nw", font=("Segoe UI", 12), fill=mut, tags=("online",))
            self.tips["online"] = US.tip()
            ly += 24
        if sub:
            wid = self.create_text(PAD, ly, text=sub, anchor="nw", font=("Segoe UI", 12), fill=mut)
            if nudge:                                        # 3.3.0 owner: a reason to scan again, said kindly
                self.create_text(self.bbox(wid)[2] + 8, ly, text=nudge + " ›", anchor="nw",
                                 font=("Segoe UI", 12, "underline" if self.hover == "scan_go" else "normal"),
                                 fill=t.c("accent"), tags=("scan_go",))
                self.acts["scan_go"] = go("wealth")
                self.tips["scan_go"] = "Open Wealth to scan your stash"
            ly += 24
        pc_key = SETTINGS.get("pc_key") or "Ctrl+D"
        x = W - PAD
        if vis["price"]:
            x = self._button(x, y + 6, "Price Checks", "b_pc", go("pricecheck"), primary=True,
                             tip=f"In game: hover an item and press {pc_key}. Its price and listings show on Price Checks.") - 12
        if vis["overlay"]:
            self._button(x, y + 6, "Overlay", "b_ov", go("tracker"), tip="Over the game: the session timer and the helpers.")

        y += max(96, ly - y + 16)
        look = getattr(self.app, "drawer_look_on", None)
        narrow = W < 900 or bool(look and look())            # D3: in the Drawer the tiles and Start cards wrap, 2 a row
        if share_prompt_due():                               # 3.3.0 owner: asked once, here, while sharing is off
            y = self._share_prompt(PAD, y, W - PAD, narrow) + GAP
        if usage_prompt_due():                               # and Count me as a user, beside it
            y = self._usage_prompt(PAD, y, W - PAD, narrow) + GAP

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
        cw = (W - 2 * PAD) / tcols
        # 3.3.0 owner: the line under a number sat on the number in tall theme fonts. The row is as tall as the
        # font needs: label, number, line under it.
        lab = ("Segoe UI", 10)
        wide = max([self._line_fonts[lab].measure(tl[0]) for tl in tiles if self._line_h(lab)] or [0])
        lab_lines = 2 if wide > cw - 60 else 1               # a long name on a narrow column takes two lines
        num_y, num_h = max(36, 14 + lab_lines * self._line_h(lab) + 2), self._line_h((num, 26))
        tile_h = max(TILE_H, num_y + num_h + 2 + self._line_h(("Segoe UI", 9)) + 12)
        if tiles:                                            # 3.3.0 owner: one titled box, a column for each number
            trows = -(-len(tiles) // tcols)
            top = self._top()
            self._card(PAD, y, W - PAD, y + top + trows * tile_h)
            self._head(PAD, y, W - PAD, "At a Glance")
        for i, (label, big, foot, foot_col, how, key) in enumerate(tiles):
            x0 = PAD + (i % tcols) * cw
            ty = y + top + (i // tcols) * tile_h
            tag = f"tile{i}"
            if self.hover == tag:
                self.create_rectangle(x0 + 1, ty + 1, x0 + cw - 1, ty + tile_h - 1, outline="", tags=(tag,),
                                      fill=t.c("hover", t.c("surface_high")))
            if i % tcols:
                self.create_line(x0, ty + 14, x0, ty + tile_h - 14, fill=t.c("border"))
            if i // tcols:
                self.create_line(x0 + 20, ty, x0 + cw - 20, ty, fill=t.c("border"))
            self.create_text(x0 + 20, ty + 14, text=label, anchor="nw", font=("Segoe UI", 10), fill=mut, tags=(tag,),
                             width=cw - 60)
            info = f"info{i}"
            self.create_text(x0 + cw - 20, ty + 14, text="ⓘ", anchor="ne", font=("Segoe UI Symbol", 10),
                             fill=brass if self.hover == info else mut, tags=(info,))
            self.tips[info] = how
            self.create_text(x0 + 20, ty + num_y, text=big, anchor="nw", font=(num, 26), fill=strong, tags=(tag,))
            self.create_text(x0 + 20, ty + num_y + num_h + 2, text=foot, anchor="nw", font=("Segoe UI", 9), fill=foot_col,
                             tags=(tag,), width=cw - 40)
            self.acts[tag] = go(key)
        if tiles:
            y += top + trows * tile_h + GAP

        # -- 3.3.0 owner: Upcoming, the next 3 events from the Calendar
        try:
            y = self._upcoming(PAD, y, W - PAD, narrow)
        except Exception:
            buglog.caught()

        # -- 3.3.0 owner: Patch Notes, the newest posts from Steam news
        try:
            y = self._patch_notes(PAD, y, W - PAD)
        except Exception:
            buglog.caught()

        # -- start here: the things not done yet (each card goes once it's done)
        starts = [c for c in (
            ("price", "◇", "Know what an item is worth", f"Hover an item in game and press {pc_key}.", "Price Checks →", "pricecheck"),
            ("wealth", "◈", "See what you have earned", "Press Scan stash. Each scan adds a point to your worth over time.", "Wealth →", "wealth"),
            ("overlay", "◆", "Get help while you play", "Helpers over the game: Ritual, Temple, Map profit.", "Overlay →", "tracker"))
            if vis["start_" + c[0]]]
        if starts:                                           # 3.3.0 owner: one titled box, a row for each
            top, rh = self._top(), 60 if W - 2 * PAD >= 520 else 84
            x0, x1 = PAD, W - PAD
            self._card(x0, y, x1, y + top + len(starts) * rh)
            _hid, up = self._head(x0, y, x1, "Start here")
            self.create_text(x1 - 20, y + 22 - up, text="Things most players do first.", anchor="ne",
                             font=("Segoe UI", 10), fill=mut)
            for i, (_k, _glyph, title, line, link, key) in enumerate(starts):
                ry = y + top + i * rh
                tag = f"start{i}"
                lit = self.hover == tag
                self.create_rectangle(x0 + 1, ry + 1, x1 - 1, ry + rh - 1, outline="", tags=(tag,),
                                      fill=t.c("hover", t.c("surface_high")) if lit else
                                      t.c("surface" if TH.box_look(t)["shape"] == "flat" else "surface_raised"))
                if i:
                    self.create_line(x0 + 20, ry, x1 - 20, ry, fill=t.c("border"))
                lid = self.create_text(x1 - 20, ry + rh / 2, text=link, anchor="e", font=("Segoe UI", 10, "bold"),
                                       fill=acc if lit else brass, tags=(tag,))
                room = self.bbox(lid)[0] - x0 - 20 - 16
                self.create_text(x0 + 20, ry + 12, text=title, anchor="nw", font=("Segoe UI", 11, "bold"), fill=strong,
                                 width=room, tags=(tag,))
                self.create_text(x0 + 20, ry + 34, text=line, anchor="nw", font=("Segoe UI", 10), fill=mut, width=room,
                                 tags=(tag,))
                self.acts[tag] = go(key)
            y += top + len(starts) * rh + GAP

        # -- 3.3.0 owner: Top Movers, and Feature Spotlight beside it (under it when the page is narrow)
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
            _hid, up = self._head(PAD, y, PAD + lw, "Pick up where you left off")
            self.create_text(PAD + lw - 20, y + 22 - up, text="All Price Checks", anchor="ne", font=("Segoe UI", 10),
                             fill=acc if self.hover == "allpc" else brass, tags=("allpc",))
            self.acts["allpc"] = go("pricecheck")
            rows = recs[:4]
            ry = y + 56
            if not rows:
                self.create_text(PAD + 20, ry + 8, text=f"No price checks yet: hover an item in game, press {pc_key}.",
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
            _hid, up = self._head(hx0, y, hx0 + hw, "Helpers")
            # nav phase 2: every helper is on Overlay › Helpers (was the Overlay Settings page)
            self.create_text(hx0 + hw - 20, y + 22 - up, text="All helpers", anchor="ne", font=("Segoe UI", 10),
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
                if self._r(10):
                    TH.round_rect(self, bx[0] - 10, bx[1] - 4, bx[2] + 10, bx[3] + 4, 10, fill="",
                                  outline=TH.mix(col, t.c("surface_raised"), .55))
                hy += 48

        self._h = y + (LIST_H if (vis["price"] or vis["overlay"]) else -GAP) + PAD
        self.configure(scrollregion=(0, 0, W, self._h))
