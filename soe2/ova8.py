"""2.139.0 The overlay's Map First layout (the mockup the user picked - "I like a8 yeah, make sure it works for all
themes"), in every style, Bar and Panel:

  [● IN MAP]  📍 THIS MAP · ★ A          | SESSION ⓘ | LAST MAP'S PROFIT ⓘ    ...  tools  clock  🔒 ⚙
              Penitentiary   3:41        | 17:04:33  | +5.5 chaos

The chip says where you are with a mark and a word (In map, Paused, Hideout, Town, Campaign, Start) and pauses /
resumes the session; the map you're in leads; maps run and the average are one hover away on SESSION; the profit's hover shows
how it was worked out. Each style keeps its own frame, colors, fonts and dividers - this draws the parts.

In the campaign (the Campaign Bar, pack 4) the parts after the chip are the campaign's:

  [● CAMPAIGN]  ZONE ⓘ          | YOU ⓘ         | GOT SO FAR ⓘ                          | ACT TIME ⓘ   ...  tools  clock
                Clearfell · lvl 2 | ✓ Lvl 4 · OK | Points 0/24 · Spirit 0/100 · Res 0/30% | 0:05:45

each worked out on hover; the Panel shows them in its card under the campaign's line (act · zone, step, what to do
now, then → where next) - the step is never shown twice.

GGG ToS: the app's own windows only; nothing here touches the game."""
import tkinter as tk

from . import buglog
from .overlaywin import CanvasText

CHIPS = {"map": ("●", "IN MAP"), "paused": ("❚❚", "PAUSED"), "hideout": ("⌂", "HIDEOUT"), "town": ("⌂", "TOWN"),
         "idle": ("▶", "START SESSION"), "zone": ("●", "CAMPAIGN"), "other": ("●", "TRACKING")}
CHIP_TIPS = {"paused": "Resume the session", "idle": "Start a session"}
LONGEST_CHIP = "● TRACKING"           # (a running session's longest; START SESSION has the bar to itself)


def chip_key(session, camp=False):
    """The chip's state from the session: idle (none running), paused, campaign, or where you are."""
    if session is None or getattr(session, "ended", None) is not None:
        return "idle"
    if getattr(session, "paused_at", None):
        return "paused"
    if camp:
        return "zone"
    kind = (getattr(session, "where", None) or {}).get("kind")
    return kind if kind in ("map", "hideout", "town") else "other"


def chip_text(key):
    mark, word = CHIPS.get(key, CHIPS["other"])
    return f"{mark} {word}"


def place_texts(n, session, live, camp=False, zone_time=None):
    """-> (label, place, timer): what the map part says. In a map: THIS MAP / its name / its time; out of one: NOW /
    Hideout, Town or Between maps; the campaign: ZONE / the zone / its time."""
    if camp:
        return "ZONE", "", zone_time or ""
    kind = (getattr(session, "where", None) or {}).get("kind") if live else None
    t = n.get("map")
    t = "" if t in (None, "-") else str(t)
    if live and kind == "map":
        where = n.get("where")
        return "THIS MAP", ("" if where in (None, "-") else str(where)), t
    if not live:
        return "NOW", "Not tracking", ""
    # 2.139.1 (feedback: "TOWN" in the chip and "NOW · Town" beside it said the same twice): out of a map the chip
    # says where you are,
    # and the map part shows your last map
    last = None
    for m in reversed(getattr(session, "maps", None) or []):
        if m.get("name"):
            last = m
            break
    if last is None:
        return "LAST MAP", "None yet", ""
    from .tracker import fmt_time
    return "LAST MAP", str(last["name"]), fmt_time(last.get("time") or 0)


class _Chip(CanvasText):
    """The state chip: one width (the longest state's), its text centered - the parts after it never move."""
    configure = CanvasText.config


class _Fit(CanvasText):
    """Text cut to a width in pixels (a map's long name); the map's time (follow) sits right after it."""
    width, font, follow, gap = 200, None, None, 8

    def config(self, **kw):
        if "text" in kw and self.font is not None:
            from tkinter import font as tkfont
            t = " ".join(str(kw["text"] or "").split())
            try:
                f = tkfont.Font(root=self.canvas, font=self.font)
                while len(t) > 2 and f.measure(t) > self.width:
                    t = t[:-2].rstrip() + "…"
            except tk.TclError:
                pass
            kw["text"] = t
        super().config(**kw)
        if self.follow is not None and "text" in kw:
            try:
                bb = self.canvas.bbox(self.item)
                x, y = self.canvas.coords(self.follow.item)
                nx = (bb[2] if bb and kw["text"] else self.canvas.coords(self.item)[0]) + self.gap
                self.follow.canvas.move(self.follow.item, nx - x, 0)
                for h, _dx, _dy in getattr(self.follow, "halos", []):
                    self.follow.canvas.move(h, nx - x, 0)
            except (tk.TclError, ValueError, TypeError):
                pass
    configure = config


class _Mark(CanvasText):
    """You: a text starting with '!' takes the warning color too (its mark and its words say it; color only adds)."""
    ok, warn = None, None

    def config(self, **kw):
        if "text" in kw and self.ok:
            kw["fg"] = self.warn if str(kw["text"]).startswith("!") else self.ok
        super().config(**kw)
    configure = config


# the Campaign Bar's parts after the chip: (key, label, widest value)
CAMP_PARTS = (("c_zone", "ZONE ⓘ", "Cemetery of the Eternals · lvl 99"), ("c_you", "YOU ⓘ", "! Lvl 99 · 9 under"),
              ("c_got", "GOT SO FAR ⓘ", "Points 24/24 · Spirit 100/100 · Res 30/30%"),
              ("c_act", "ACT TIME ⓘ", "0:00:00"))
CAMP_GAP = 12                      # a divider's slot between the Campaign Bar's parts (the map parts' is 20)
GOT_WIDE = {"full": "Points 24/24 · Spirit 100/100 · Res 30/30%", "mid": "Points 24/24 · Spirit 100/100",
            "short": "Points 24/24"}


class OverlayA8:
    """Mixed into App."""

    # ---------------------------------------------------------------- what it says (tracker_overlay_draw)
    def a8_texts(self, n, live, camp=False):
        s = getattr(self, "tk_session", None)
        zt = None
        if camp:
            try:
                from . import campaign as CP
                from .tracker import fmt_time
                z = CP.zone_time()
                zt = fmt_time(z) if z is not None else ""
            except Exception:
                buglog.caught()
        label, place, timer = place_texts(n, s, live, camp, zt)
        if camp:
            try:
                from . import campaign as CP
                # UI overhaul (feedback: the campaign step was shown twice): the step is on the campaign line above
                # the bar - this part says where you are
                place = CP.char().get("zone") or "Campaign"
            except Exception:
                place = "Campaign"
        rank = ""
        try:
            rank = self.rank_text(n.get("where") if live and getattr(self, "_mr_in", None) else None) or ""
        except Exception:
            buglog.caught()
        if rank and label == "THIS MAP":
            label = f"THIS MAP · {rank}"
        out = {"a8_chip": chip_text(chip_key(s, camp)), "a8_label": label, "a8_place": place, "a8_timer": timer}
        if camp:                                            # the Campaign Bar's parts
            try:
                out.update(c_zone=self.camp_zone_text(), c_you=self.camp_you_text(), c_got=self.camp_got_text(),
                           c_act=self.camp_act_text(), c_lvl=self.camp_zone_text().rpartition(" · ")[2].capitalize())
            except Exception:
                buglog.caught()
        return out

    def a8_session_tip(self):
        """SESSION's hover: maps run and the average - each as its switch (Overlay options' Maps / Average) says."""
        n = self.tracker_numbers() or {}
        ln = self.ov_lines()
        maps, avg = n.get("maps", "0"), n.get("avg", "-")
        parts = []
        if ln.get("maps", True):
            parts.append(f"{maps} maps this session")
        if ln.get("avg", True) and avg not in (None, "-", ""):
            parts.append(f"{avg} on average")
        return ", ".join(parts) or "This session's time"

    def a8_chip_tip(self):
        return CHIP_TIPS.get(chip_key(getattr(self, "tk_session", None)), "Pause the session")

    # ---------------------------------------------------------------- the parts
    def _a8_label(self, cv, P, x, y, text, key=None, anchor="w"):
        """A part's small label (SESSION ⓘ ...) above its value."""
        return self._lt_text(cv, P, x, y, text, 8, P["muted"], anchor=anchor, bold=True, key=key)

    def _a8_chip(self, cv, P, x, mid, h, longest=LONGEST_CHIP):
        """The state chip at x (left edge). -> its width."""
        u = self._u
        f = (P["font"], self._hf(8), "bold")
        fm = self._lt_fm(cv, P, 8, True)
        w = fm.measure(longest) + 2 * u(8)
        y0, y1 = mid - h // 2, mid + h // 2
        cv.create_rectangle(x, y0, x + w, y1, outline=P.get("line", P["muted"]),
                            fill=P.get("cell_bg") or P.get("field") or P["bg"], tags=("mg", "mg_a8chip"))
        it = cv.create_text(x + w // 2, mid, text="● IN MAP", anchor="center", fill=P.get("accent") or P["text"],
                            font=f, tags=("mg", "mg_a8chip"))
        t = _Chip(cv, it, P["bg"], halo=P.get("halo"))
        self.tk_ov_lbls["a8_chip"] = t
        cv.tag_bind("mg_a8chip", "<Button-1>", lambda e: (self.ov_tip_hide(), self.tracker_play_click()))
        self.ov_tip(cv, "mg_a8chip", self.a8_chip_tip)
        return w

    def _a8_pin(self, cv, P, x, y):
        """A map pin, drawn (fonts' pins differ from PC to PC): a round head on a point, a hole in it - y is the head's
        middle. 2.139.1 (feedback: the GPS pin looked like a flower): a filled teardrop, not a ring on a stick.
        -> its width."""
        u = self._u
        r = max(4, u(5))
        cx, cy = x + r, y - r * 0.3
        col = P.get("accent") or P["text"]
        tip = cy + r * 1.7
        pts = [cx, tip, cx - r * 0.75, cy + r * 0.6, cx - r, cy - r * 0.1, cx - r * 0.75, cy - r * 0.8, cx, cy - r * 1.05,
               cx + r * 0.75, cy - r * 0.8, cx + r, cy - r * 0.1, cx + r * 0.75, cy + r * 0.6]
        cv.create_polygon(pts, smooth=True, fill=col, outline=col, tags=("mg",))
        h = r * 0.38
        cv.create_oval(cx - h, cy - h, cx + h, cy + h, fill=P.get("cell_bg") or P.get("field") or P["bg"], outline="",
                       tags=("mg",))
        return 2 * r

    def a8_bar(self, w, cv, P, want, x0, right, mid, sep, map_w=None, spread=None):
        """The Bar's left side from x0: chip, the map part, SESSION, LAST MAP'S PROFIT - up to `right` (the map part
        takes the room left), or as wide as it needs when right is None (map_w for the map part). sep(x) draws the
        style's divider. -> the x it ended at."""
        u = self._u
        ln = self.ov_lines()
        if not want["timer"]:                               # no session: the chip alone - ▶ START SESSION starts one
            cw = self._a8_chip(cv, P, x0, mid, u(20), longest=chip_text("idle"))
            self.tk_ov_lbls.pop("a8_chip").config(text=chip_text("idle"))
            return x0 + cw + u(12)
        ly, vy = (mid - spread[0], mid + spread[1]) if spread else (mid - u(7), mid + u(6))     # label / value lines
        if self.ov_camp_mode():                             # the Campaign Bar
            return self.a8_camp_bar(cv, P, x0, right, mid, ly, vy, sep)
        x = x0 + self._a8_chip(cv, P, x0, mid, u(18)) + u(10)
        fl, fv = self._lt_fm(cv, P, 8, True), self._lt_fm(cv, P, 10, True)
        ses_w = max(fl.measure("SESSION ⓘ"), fv.measure("00:00:00")) if ln.get("session", True) else 0
        prof = False
        try:
            prof = bool(self.mp_on())
        except Exception:
            buglog.caught()
        prof_w = max(fl.measure("LAST MAP'S PROFIT ⓘ"), fv.measure("+00.0 chaos")) if prof else 0
        gap = u(20)                                          # a divider's slot
        fixed = (ses_w + gap if ses_w else 0) + (prof_w + gap if prof_w else 0)
        show_map = ln.get("map", True) or ln.get("where", True)
        if right is None:
            room = map_w or u(240)
        else:
            room = right - x - fixed - u(6)
            if room < u(150) and ses_w:                     # narrow: the session leaves first (the profit stays)
                fixed -= ses_w + gap
                ses_w = 0
                room = right - x - fixed - u(6)
            room = min(room, u(210))                        # (wide: the rest is space before the tools)
        if show_map and room > u(60):
            px = x + self._a8_pin(cv, P, x, mid) + u(8)
            self._a8_label(cv, P, px, ly, "THIS MAP", key="a8_label")
            tf = self._lt_fm(cv, P, 11, True)
            tw = tf.measure("00:00") + u(4)
            tm = self._lt_text(cv, P, px, vy, "", 11, P.get("accent") or P["big"], bold=True, key="a8_timer")
            t = self._lt_text(cv, P, px, vy, "", 11, P["big"], bold=True, key="a8_place", cls=_Fit)
            t.width, t.font = max(u(40), x + room - px - tw - u(8)), (P["font"], self._hf(11), "bold")
            t.follow, t.gap = tm, u(10)
            x += room
        if ses_w:
            sep(x + gap // 2)
            x += gap
            from .merged_page import _Time
            lab = self._a8_label(cv, P, x, ly, "SESSION ⓘ")
            t = self._lt_text(cv, P, x, vy, "", 10, P["big"], bold=True, key="session", cls=_Time)
            t.num, t.dim = True, (P["big"], P["muted"])
            cv.addtag_withtag("mg_a8ses", t.item)
            cv.addtag_withtag("mg_a8ses", lab.item)
            self.ov_tip(cv, "mg_a8ses", self.a8_session_tip, hand=False)
            x += ses_w
        if prof_w:
            sep(x + gap // 2)
            x += gap
            lab = self._a8_label(cv, P, x, ly, "LAST MAP'S PROFIT ⓘ")
            t = self._lt_text(cv, P, x, vy, "", 10, P.get("accent") or P["big"], bold=True, key="profit")
            try:
                self.mp_bar_bind(cv, t.item)
                self.mp_bar_bind(cv, lab.item)
            except Exception:
                buglog.caught()
            x += prof_w
        if self.tk_ov_cv is None:
            self.tk_ov_cv = cv
        return x

    # ---------------------------------------------------------------- the Campaign Bar
    def _a8_camp_part(self, cv, P, x, ly, vy, key, label, width, tip, size=10):
        """One of the Campaign Bar's parts: its label (ⓘ: hover for how it was worked out) over its value."""
        tag = "mg_" + key
        lab = self._a8_label(cv, P, x, ly, label)
        cls = _Mark if key == "c_you" else _Fit
        t = self._lt_text(cv, P, x, vy, "", size, P["big"], bold=True, key=key, cls=cls)
        if cls is _Fit:
            t.width, t.font = width, (P["font"], self._hf(size), "bold")
        else:
            t.ok, t.warn = P["big"], P.get("accent") or P["head"]
        for it in (lab.item, t.item):
            cv.addtag_withtag(tag, it)
        self.ov_tip(cv, tag, tip, hand=False)
        return t

    def a8_camp_plan(self, cv, P, room):
        """Which of the Campaign Bar's parts fit in room px. A narrow bar leaves out, in turn: Res, Act time,
        Spirit, then shortens the zone and You to their words - what's left out stays one hover away (Got so far's
        and You's hovers have it all). -> ({key: width}, Got so far's mode, You's mode)."""
        u = self._u
        fl, fv = self._lt_fm(cv, P, 8, True), self._lt_fm(cv, P, 10, True)
        gap = u(CAMP_GAP)

        def w(label, value):
            return max(fl.measure(label), fv.measure(value))
        act = w("ACT TIME ⓘ", "0:00:00")
        zone_need = self._camp_zone_need = w("ZONE ⓘ", self.camp_zone_text()) + u(4)
        for cap, mode, show_act, you_mode in ((u(220), "full", True, "full"), (u(220), "mid", True, "full"),
                                              (u(220), "mid", False, "full"), (u(220), "short", False, "full"),
                                              (u(220), "short", False, "short"), (u(120), "short", False, "short"),
                                              (u(80), "short", False, "short")):
            zone = min(zone_need, cap)
            you = w("YOU ⓘ", "! Lvl 99 · 9 under" if you_mode == "full" else "! 9 under")
            got = w("GOT SO FAR ⓘ", GOT_WIDE[mode])
            need = zone + gap + you + gap + got + ((gap + act) if show_act else 0)
            if room is None or need <= room:
                break
        plan = {"c_zone": zone, "c_you": you, "c_got": got}
        if show_act:
            plan["c_act"] = act
        return plan, mode, you_mode

    def a8_camp_bar(self, cv, P, x0, right, mid, ly, vy, sep):
        """The Campaign Bar after the chip: ZONE | YOU | GOT SO FAR | ACT TIME, up to `right` (or as wide as they
        need when right is None). -> the x it ended at."""
        u = self._u
        x = x0 + self._a8_chip(cv, P, x0, mid, u(18)) + u(10)
        plan, mode, you_mode = self.a8_camp_plan(cv, P, None if right is None else right - x - u(6))
        self._camp_got_mode, self._camp_you_mode = mode, you_mode
        gap = u(CAMP_GAP)
        tips = {"c_zone": self.camp_zone_tip, "c_you": self.camp_you_tip, "c_got": self.camp_got_tip,
                "c_act": self.camp_act_tip}
        first = True
        for key, label, _wide in CAMP_PARTS:
            if key not in plan:
                continue
            if not first:
                sep(x + gap // 2)
                x += gap
            first = False
            self._a8_camp_part(cv, P, x, ly, vy, key, label, plan[key], tips[key])
            x += plan[key]
        if self.tk_ov_cv is None:
            self.tk_ov_cv = cv
        return x

    def a8_camp_card(self, cv, P, pad, R, y):
        """The Panel's campaign card under its chip: the line (act · zone, step, what to do now, then → next), a
        rule, ZONE | YOU | ACT TIME, then GOT SO FAR. -> the y under it."""
        u = self._u
        fh, fd, _fi, _fb = self._camp_fonts(P, cv)
        lh = fd.metrics("linespace") + u(2)
        rows = self.camp_rows(P, R - pad)
        top = y + u(8) + lh // 2
        self.camp_draw_lines(cv, P, rows, pad, R, top, lh, ("mg", "camp"))
        self._camp_card_was = self.camp_line_text_now()
        y = top + (len(rows) - 1) * lh + lh // 2 + u(6)
        cv.create_line(pad, y, R, y, fill=P["line"], tags=("mg",))
        ly, vy = y + u(12), y + u(28)
        colw = (R - pad) // 3
        tips = {"c_lvl": self.camp_zone_tip, "c_you": self.camp_you_tip, "c_act": self.camp_act_tip,
                "c_got": self.camp_got_tip}
        for i, (key, label) in enumerate((("c_lvl", "ZONE ⓘ"), ("c_you", "YOU ⓘ"), ("c_act", "ACT TIME ⓘ"))):
            self._a8_camp_part(cv, P, pad + i * colw, ly, vy, key, label, colw - u(8), tips[key], size=10)
        y += u(40)
        self._camp_got_mode, self._camp_you_mode = "full", "full"
        self._a8_camp_part(cv, P, pad, y + u(12), y + u(28), "c_got", "GOT SO FAR ⓘ", R - pad, tips["c_got"], size=10)
        return y + u(40)

    def camp_bar_replan(self):
        """A new zone on the Bar: True when its name needs another plan of the parts (longer than the room it has,
        or much shorter - the parts left out can come back)."""
        was = getattr(self, "_camp_zone_need", None)
        if was is None:
            return False
        cv = getattr(self, "tk_ov_cv", None)
        if cv is None:
            return False
        P = getattr(self, "mg_P", None) or {}
        if "font" not in P:
            return False
        fl, fv = self._lt_fm(cv, P, 8, True), self._lt_fm(cv, P, 10, True)
        now = max(fl.measure("ZONE ⓘ"), fv.measure(self.camp_zone_text())) + self._u(4)
        return abs(now - was) > self._u(6)

    @staticmethod
    def camp_line_text_now():
        from . import campaign as CP
        return CP.line_text()

    def a8_panel(self, w, cv, P, want, PW):
        """The Panel: the chip and the clock, the map part, SESSION | LAST MAP'S PROFIT, the tools. -> its height."""
        u = self._u
        cfg, ln = self.tracker_cfg(), self.ov_lines()
        pad = u(10)
        R = PW - pad
        hh = u(30)
        self._a8_chip(cv, P, pad, hh // 2, u(20))
        if not want["timer"]:                               # no session: ▶ START SESSION starts one
            self.tk_ov_lbls.pop("a8_chip").config(text=chip_text("idle"))
        x = self._lt_glyphs(w, cv, P, R, hh // 2)
        if want["timer"] and cfg.get("clock", True):
            self._lt_clock(cv, P, x, hh // 2)
        cv.create_line(0, hh, PW, hh, fill=P["line"], tags=("mg",))
        y = hh
        if want["timer"] and self.ov_camp_mode():           # the Campaign Bar as one card (the step once)
            y = self.a8_camp_card(cv, P, pad, R, y)
            self.tk_ov_cv = cv
        elif want["timer"]:
            if ln.get("map", True) or ln.get("where", True):
                ly, vy = y + u(12), y + u(30)
                px = pad + self._a8_pin(cv, P, pad, (ly + vy) // 2) + u(8)
                self._a8_label(cv, P, px, ly, "THIS MAP", key="a8_label")
                self._lt_text(cv, P, R, vy, "", 13, P.get("accent") or P["big"], anchor="e", bold=True,
                              key="a8_timer")
                tw = self._lt_fm(cv, P, 13, True).measure("00:00") + u(8)
                t = self._lt_text(cv, P, px, vy, "", 13, P["big"], bold=True, key="a8_place", cls=_Fit)
                t.width, t.font = R - px - tw, (P["font"], self._hf(13), "bold")
                y += u(44)
                cv.create_line(pad, y, R, y, fill=P["line"], tags=("mg",))
            ly, vy = y + u(12), y + u(28)
            colw = (PW - 2 * pad) // 2
            if ln.get("session", True):
                from .merged_page import _Time
                lab = self._a8_label(cv, P, pad, ly, "SESSION ⓘ")
                t = self._lt_text(cv, P, pad, vy, "", 11, P["big"], bold=True, key="session", cls=_Time)
                t.num, t.dim = True, (P["big"], P["muted"])
                cv.addtag_withtag("mg_a8ses", t.item)
                cv.addtag_withtag("mg_a8ses", lab.item)
                self.ov_tip(cv, "mg_a8ses", self.a8_session_tip, hand=False)
            try:
                prof = bool(self.mp_on())
            except Exception:
                prof = False
            if prof:
                lab = self._a8_label(cv, P, pad + colw, ly, "LAST MAP'S PROFIT ⓘ")
                t = self._lt_text(cv, P, pad + colw, vy, "", 11, P.get("accent") or P["big"], bold=True, key="profit")
                try:
                    self.mp_bar_bind(cv, t.item)
                    self.mp_bar_bind(cv, lab.item)
                except Exception:
                    buglog.caught()
            y += u(40)
            self.tk_ov_cv = cv
        if self.bar_buttons_on():
            cv.create_line(0, y, PW, y, fill=P["line"], tags=("mg",))
            self._lt_menus(w, cv, P, pad, y + u(14), anchor="w", right=PW - pad, step=u(22))
            y += u(28) + (getattr(self, "_mg_menu_rows", 1) - 1) * u(22)
        else:
            y += u(4)
        return y
