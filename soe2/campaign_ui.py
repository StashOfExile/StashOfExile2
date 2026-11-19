"""The Campaign Helper over the game (2.77.0) - the logic is campaign.py.

  * L  The Campaign Bar (pack 4): the line over the bar - the act and zone, step n / N, the one thing to do now
       with what it gives, and (dimmed) where next; on the bar itself the zone, You (your level against it), Got
       so far and Act time, each worked out on hover. The Panel shows the same as one card. Click the line for the
       act's route. Pop-ups (the Alert card): a boss is down, you left during a boss fight, too low for a zone.
  * M  The act's route: every step - ✓ done, ▸ here, ○ to do, "passed" (gone past without entering). Click a step:
       "I'm here" (a character that's partway through: pick the act, click its step). ◀ ▶ (and their keys).
  * N  Rewards: points, spirit and resistances earned on this character; tick or untick any by hand.
  * O  Vendor search - in town, "Vendor ▾" on the campaign line: this act's searches and your Regex favorites. A click
       copies one; you paste it in the shop's search box (the app never types into the game).
  * P  A zone the guide doesn't know: added to your route where you went, with a note, Mark optional, or a newer guide.
  * Q  Act splits - this run against your best (per league).
  * R  Its settings (Overlay › Options › Campaign); S, T: its switches in "On the overlay" and "On the bar".

Mixed into App. GGG ToS: windows, the clipboard and the game's log only."""
import re
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import campaign as CP
from .overlaywin import CanvasText

PAGES = ("Route", "Rewards", "Act times")
# the pop-ups' edge colors (the Alert card): done, left a fight, too low - each also has its mark and its words
POP_GOOD, POP_BAD, POP_WARN = "#7fd9a0", "#e05a4f", "#ffb347"
# The Campaign Helper's switches (Overlay › Options › Campaign Helper and the route card's Options ▾ - one setting each)
CAMP_OPTS = (("ask_route", "Ask which route when a campaign starts"),          # 2.89.0
             ("optional", "Optional zones"), ("tips", "Tips (bosses, vendor checks)"),
             ("warn", "Ask about rewards in town (Got it / Not yet)"),
             ("popups", "Pop-ups: boss down, left a fight, too low"),
             ("off_at_maps", "Hide it in maps (back in campaign zones)"))   # 2.89.2: "Splits" said nothing to most players


_MEASURE = {}


def _measure(fnt, text):
    """2.125.4: a font's text width, remembered (fit_lines asked the same widths again on every redraw)."""
    k = (getattr(fnt, "_mk", None) or str(fnt), text)
    v = _MEASURE.get(k)
    if v is None:
        if len(_MEASURE) > 4000:
            _MEASURE.clear()
        v = _MEASURE[k] = fnt.measure(text)
    return v


def fit_lines(fnt, text, px, lines):
    """2.123.7: text word-wrapped to px pixels (measured, not counted in letters) on at most `lines` lines; what's
    left over is cut with "…" at the end of the last line."""
    text = " ".join(str(text or "").split())
    out, cur = [], ""
    words = text.split(" ")
    for i, wd in enumerate(words):
        t = f"{cur} {wd}" if cur else wd
        if not cur or _measure(fnt, t) <= px:
            cur = t
            continue
        out.append(cur)
        cur = wd
        if len(out) == lines:                          # no room for more: the rest goes on the last line, then cut
            out[-1] = " ".join([out[-1]] + words[i:])
            cur = ""
            break
    if cur:
        out.append(cur)
    for i, ln in enumerate(out):
        if _measure(fnt, ln) > px:
            while len(ln) > 1 and _measure(fnt, ln + "…") > px:
                ln = ln[:-1]
            out[i] = ln.rstrip(" ,.") + "…"
    return "\n".join(out)


def _wrap(words, px):
    """[(word, font, role)] -> lines of at most px pixels (measured); a word longer than a line gets a line of its
    own. Nothing is cut."""
    lines, cur, w = [], [], 0
    for wd, f, role in words:
        ww = _measure(f, wd)
        gap = _measure(f, " ") if cur else 0
        if cur and w + gap + ww > px:
            lines.append(cur)
            cur, w, gap = [], 0, 0
        cur.append((wd, f, role))
        w += gap + ww
    if cur:
        lines.append(cur)
    return lines


class FitText(CanvasText):
    """A canvas text that fits itself into px pixels on at most `lines` lines (the campaign line - its text is set
    again on every overlay refresh)."""
    fnt, px, lines = None, 200, 1

    def config(self, **kw):
        if "text" in kw and self.fnt is not None:
            kw["text"] = fit_lines(self.fnt, kw["text"], self.px, self.lines)
        super().config(**kw)
    configure = config


class CampaignUI:
    """Mixed into App."""

    # ================================================================ the log
    def campaign_log(self, kind, ts, data):
        """Every game-log event (the session tracker's reader). -> what campaign.log_event said."""
        if kind not in ("area", "scene", "afk", "level", "say"):
            return None
        if kind == "say":                                          # (most lines are no cue: nothing to redraw)
            try:
                out = CP.log_event(kind, ts, data)
            except Exception:
                self.log_error("the campaign helper")
                return None
            if out:
                self.camp_events()
                self.camp_refresh()
            return out
        ak = None
        if kind == "area":
            from .gamelog import area_kind
            ak = area_kind(data.get("area"), data.get("seed"), data.get("level", 0))
            self._camp_town = ak == "town"
        before, was_shown = CP.line_text(), CP.shown()
        try:
            out = CP.log_event(kind, ts, data, ak)
        except Exception:
            self.log_error("the campaign helper")
            return None
        if CP.shown() != was_shown:                                # Round 18: into / out of a hideout - the line
            self.camp_refresh()                                    # hides / shows (and the bar's parts with it)
        if kind == "area":                                         # 2.92.2: Vendor ▾ on the bar - in town only
            try:
                v = self.vendor_on_bar()
                if v != getattr(self, "_vendor_was", None):
                    self._vendor_was = v
                    if not v:
                        self.camp_vendor_close()
                    if getattr(self, "mg_win", None) is not None:
                        self.merged_build()
            except Exception:
                self.log_error("the Vendor menu")
        if kind == "scene" and getattr(self, "_camp_town", False) and CP.cfg()["warn"] and CP.asks():
            self.camp_ask_show()                                   # in town: the rewards to answer
        if out == "maps" and CP.cfg()["off_at_maps"]:
            self._say("Maps! The campaign line hides in maps and comes back in campaign zones (Overlay › Options › "
                      "Campaign Helper).", 6)
        self.camp_events()
        if out or CP.line_text() != before:
            self.camp_refresh()
        if CP.needs_route() and getattr(self, "camp_rq_win", None) is None:
            self.camp_route_ask_show()                             # 2.89.0: a new campaign - which guide?
        return out

    def campaign_where(self, ev):
        """Round 18: at start, the log's last area (an ("area", ts, data) event, or its data): in a hideout the
        Campaign Bar stays hidden until you're in a campaign area."""
        data = ev[2] if isinstance(ev, tuple) else ev
        if not data:
            return False
        try:
            from .gamelog import area_kind
            ak = area_kind(data.get("area"), data.get("seed"), data.get("level", 0))
            if CP.where_now(data.get("area"), ak):
                self.camp_refresh()
                return True
        except Exception:
            self.log_error("the campaign helper")
        return False

    # ---------------------------------------------------------------- pack 4: pop-ups from the log (Alert card)
    def camp_events(self):
        """What the log just told the Campaign Helper -> short pop-ups over the game (Options: Pop-ups)."""
        evs = CP.take_events()
        if not evs or not CP.cfg().get("popups", True):
            return []
        shown = []
        for ev in evs:
            t = self.camp_popup_text(ev)
            if not t:
                continue
            title, sub, mark, color = t
            try:
                from . import alertcard
                from .alerts_page import game_rect
                alertcard.show(self.root, title, sub, color=color, mark=mark, secs=7, game=game_rect(),
                               tag="Campaign", rank=4, vital=ev["kind"] == "left")
                shown.append(title)
            except Exception:
                self.log_error("a campaign pop-up")
        return shown

    @staticmethod
    def camp_popup_text(ev):
        """An event -> (title, line under it, mark, color): every pop-up says what happened with a mark and words."""
        k = ev.get("kind")
        if k == "boss":
            boss = ev.get("boss") or "The boss"
            title = f"{boss[0].upper() + boss[1:]} is down" + (f" {ev['gives']}" if ev.get("gives") else "")
            return title, (f"Next → {ev['next']}" if ev.get("next") else "Step done"), "✓", POP_GOOD
        if k == "left":
            gives = f"That's {ev['gives']}. " if ev.get("gives") else ""
            return (f"You left before {ev.get('boss') or 'the boss'} died", f"{gives}Go back → {ev.get('zone')}",
                    "✕", POP_BAD)
        if k == "low":
            n = ev.get("under", 0)
            return (f"Too low: {n} levels under this zone", f"You {ev.get('you')}, zone {ev.get('zone_level')}. "
                    "Bosses hit harder - kill a few packs before the boss.", "!", POP_WARN)
        if k == "act":
            best = ev.get("best")
            return (f"{ev.get('act')} done in {CP.fmt(ev.get('secs'))}",
                    f"Best this league: {CP.fmt(best)}" if best else "Your first time for it this league", "✓",
                    POP_GOOD)
        return None

    # ---------------------------------------------------------------- 2.89.0: which guide, when a campaign starts
    def camp_route_ask_show(self):
        self.camp_route_ask_close()
        w, body, P = self._camp_card("New campaign", "🗺", 460, top=0.16,
                                     on_close=lambda: self.camp_route_pick_new(CP.cfg()["route"]))
        bg = P["bg"]
        tk.Label(body, text="Which guide should I follow?", bg=bg, fg=P["head"],
                 font=(P["font"], self.ov_font(11), "bold"), anchor="w").pack(fill="x")
        self.camp_rq_btns = {}
        for k, title, txt, style in (
                ("speed", "Speedrun", CP.ROUTE_LINES["speed"], "Primary.TButton"),
                ("full", "Full", CP.ROUTE_LINES["full"], "TButton"),
                ("rush", "Rush (carry)", CP.ROUTE_LINES["rush"], "TButton")):
            f = tk.Frame(body, bg=bg, pady=4)
            f.pack(fill="x")
            b = ttk.Button(f, text=title, style=self.ov_btn(style), width=14,
                           command=lambda k=k: self.camp_route_pick_new(k))
            b.pack(side="left", anchor="n")
            tk.Label(f, text=txt, bg=bg, fg=P["text"], font=(P["font"], self.ov_font(9)), anchor="w", justify="left",
                     wraplength=self.ov_px(290)).pack(side="left", fill="x", padx=(8, 0))
            self.camp_rq_btns[k] = b
        self.camp_rq_keep = tk.BooleanVar(value=False)
        tk.Checkbutton(body, text="Use this every time (don't ask again)", variable=self.camp_rq_keep, bg=bg,
                       fg=P["text"], activebackground=bg, activeforeground=P["text"], selectcolor=P["bg"],
                       font=(P["font"], self.ov_font(9)), anchor="w", highlightthickness=0).pack(anchor="w", pady=(8, 0))
        tk.Label(body, text="Change it any time: Overlay › Options › Campaign › Route.", bg=bg, fg=P["muted"],
                 font=(P["font"], self.ov_font(8)), anchor="w").pack(fill="x", pady=(2, 0))
        self.camp_rq_win = w
        w.show()
        return w

    def camp_route_pick_new(self, route):
        CP.set_route(route, remember=bool(getattr(self, "camp_rq_keep", None) and self.camp_rq_keep.get()))
        if getattr(self, "tk_camp_route", None) is not None:
            try:
                self.tk_camp_route.pick(dict(CP.ROUTES).get(CP.cfg()["route"]), notify=False)
            except Exception:
                buglog.caught()
        if getattr(self, "tk_camp_vars", None) and "ask_route" in self.tk_camp_vars:
            self.tk_camp_vars["ask_route"].set(bool(CP.cfg()["ask_route"]))
        self.camp_route_ask_close()
        self.camp_refresh()

    def camp_route_ask_close(self):
        w, self.camp_rq_win = getattr(self, "camp_rq_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def camp_refresh(self, card=True, line_later=False):
        """The line changed: redraw it on the overlay (in place when it still fits the same rows) and the open
        route card's pages (card=False: a click on the card already changed its own line).
        2.125.4 (feedback: the whole campaign card was laggy): the card's pages are built again only as each
        is shown (never the whole card), and a click on the card redraws the overlay's line just after, once for a
        quick run of clicks."""
        if card and not line_later:
            self._camp_line_now()
        elif getattr(self, "_camp_line_job", None) is None:  # (once, after the card has drawn its change)
            self._camp_line_job = self.root.after_idle(self._camp_line_now)
        if card and getattr(self, "camp_win", None) is not None:
            act = CP.char().get("act")
            if act and act != getattr(self, "_camp_act", None):      # a new act: the card follows you there
                self.camp_view = act
            self._camp_act = act
            self.camp_pages_refresh()

    def _camp_line_now(self):
        self._camp_line_job = None
        try:
            if self.camp_in_card() and self.camp_on_bar():     # the Panel: the line is part of its card
                if getattr(self, "mg_win", None) is not None and CP.line_text() != getattr(self, "_camp_card_was", None):
                    self.merged_build()
                return
            if self.camp_on_bar() and getattr(self, "mg_win", None) is not None and self.camp_bar_replan():
                return self.merged_build()                  # (a zone name of another length: the bar's parts again)
            if not self.camp_line_redraw():
                self.goalbar_build()
        except Exception:
            self.log_error("the goal bar")

    def camp_pages_refresh(self):
        """The card's pages are out of date: the one shown is built again now, the others when they're shown."""
        if not getattr(self, "camp_pages", None):
            return
        try:
            if getattr(self, "camp_act_var", None) is not None:
                self.camp_act_var.set(CP.act_name(self.camp_view))
        except tk.TclError:
            pass
        self._camp_dirty = set(PAGES)
        self._camp_build_page(self.camp_page)

    def _camp_build_page(self, name):
        dirty = getattr(self, "_camp_dirty", set())
        if name not in dirty:
            return
        dirty.discard(name)
        pg = self.camp_pages[name]
        for c in pg.winfo_children():
            c.destroy()
        fn = {"Route": self._camp_route_page, "Rewards": self._camp_rewards_page, "Act times": self._camp_splits_page}
        fn[name](pg, self.camp_P)

    def camp_line_redraw(self):
        """2.124.0: the campaign line redrawn where it is, when it still takes as many lines - no rebuild of the
        overlay's lines (the window kept jumping). -> False when the lines must be built again."""
        cv, spot = getattr(self, "gb_cv", None), getattr(self, "_gb_camp", None)
        if cv is None or spot is None or "campaign" not in (getattr(self, "goal_rows", None) or []) \
                or not self.camp_on_bar() or self.goalbar_rows() != self.goal_rows:
            return False
        P, lft, rgt, mid, f, n, lh = spot
        if self.camp_lines(P, rgt - lft) != n:
            return False
        try:
            for tag in ("camp", "campline", "campinfo"):
                cv.delete(tag)
            self.camp_draw_row(cv, P, lft, rgt, mid, f, n=n, lh=lh)
        except tk.TclError:
            return False
        return True

    def camp_on_bar(self):
        return CP.shown()                                   # 2.97.0: on = its line shows (Round 18: not in a hideout)

    def camp_in_card(self):
        """The Panel layout: the Campaign Bar's line is one card with the rest (never twice); the Bar: over it."""
        try:
            return self.merged_layout() == "panel"          # (Split: over its run half, as over the Bar)
        except Exception:
            return False

    def camp_set_on(self, on):
        CP.cfg()["on"] = bool(on)
        CP.save()
        if getattr(self, "tk_camp_var", None) is not None and bool(self.tk_camp_var.get()) != bool(on):
            self.tk_camp_var.set(bool(on))
        r = (getattr(self, "al_rows", None) or {}).get("campaign")        # 2.90.0: Helpers › Campaign follows
        if r is not None and bool(r["on"].get()) != bool(on):
            r["on"].set(bool(on))
        if not on:
            self.camp_close_all()
        self.merged_build()

    def camp_close_all(self):
        for name in ("camp_win", "camp_vendor_win", "camp_ask_win", "camp_rq_win"):
            w = getattr(self, name, None)
            setattr(self, name, None)
            if w is not None:
                try:
                    w.destroy()
                except tk.TclError:
                    pass

    # ================================================================ L: the line (drawn on the goal bar)
    def _camp_fonts(self, P, root=None):
        """-> (head, do, small, small bold) fonts of the Campaign Bar's line (made once per look)."""
        import tkinter.font as tkfont
        root = root or self.root
        spec = ((P["hfont"], self._hf(9), "bold"), (P["font"], self._hf(10), "bold"), (P["font"], self._hf(9), "normal"),
                (P["font"], self._hf(9), "bold"))
        cache = self.__dict__.setdefault("_camp_font_cache", {})   # 2.125.4: made once per look (not per redraw)
        k = (str(root), spec)
        if k not in cache:
            fs = []
            for fam, size, weight in spec:
                f = tkfont.Font(root=root, family=fam, size=size, weight=weight)
                f._mk = (fam, size, weight)                  # (the key its remembered widths go by)
                fs.append(f)
            if len(cache) > 8:
                cache.clear()
            cache[k] = tuple(fs)
        return cache[k]

    def camp_rows(self, P, width, d=None):
        """The Campaign Bar's line laid out in width px -> [[(text, font, role)], ...] one list per line:
          the head (act · zone, and the step n / N with ⓘ when the step has a tip, at the right: role "step"),
          what to do now (its gain in the gain role), wrapped - never cut,
          then → where next (dimmed).
        role: head / step / do / gain / then / to."""
        d = d or CP.line()
        if not d:
            return []
        fh, fd, fi, fb = self._camp_fonts(P)
        step = d["step"] + ("  ⓘ" if d.get("tip") else "")
        out = [[(fit_lines(fh, d["head"], max(40, width - (_measure(fi, step) + 16 if step else 0)), 1), fh, "head")]
               + ([(step, fi, "step")] if step else [])]
        words = []                                            # (a gain stays in one piece: never "(+10% cold" / "res)")
        for part in re.split(r"(\((?:their )?\+[^)]*\))", d["do"]):
            if not part.strip():
                continue
            if part.startswith("(") and "+" in part:
                words.append((part, fd, "gain"))
                continue
            for wd in part.split():
                words.append((wd, fd, "gain" if wd == "✓" else "do"))
        out += _wrap(words, width)
        if d.get("then"):
            out += _wrap([("then →", fi, "then")] + [(w, fb, "to") for w in d["then"].split(" ")], width)
        return out

    def camp_lines(self, P, avail):
        """How many text lines the Campaign Bar's line needs in avail px (2.123.7: wraps, never cut)."""
        return max(1, len(self.camp_rows(P, avail)))

    def camp_draw_row(self, cv, P, lft, rgt, mid, font, n=1, lh=0):
        """Draw the Campaign Bar's line between lft and rgt: n lines of lh px, centered on mid. -> the items clicked
        for the route card."""
        rows = self.camp_rows(P, rgt - lft)
        if not rows:
            return None
        lh = lh or self._camp_fonts(P)[1].metrics("linespace")
        y = mid - (len(rows) - 1) * lh / 2
        items = self.camp_draw_lines(cv, P, rows, lft, rgt, y, lh, ("mg", "camp"))
        if cv is getattr(self, "gb_cv", None) or getattr(self, "gb_cv", None) is None:
            self._gb_camp = (P, lft, rgt, mid, font, n, lh)
        return items

    def camp_draw_lines(self, cv, P, rows, lft, rgt, y, lh, tags):
        """Draw laid-out rows (camp_rows) from y (the first line's middle). -> the items."""
        from .merged_page import click_not_drag
        col = {"head": P["head"], "step": P["muted"], "do": P.get("big") or P["text"],
               "gain": P.get("on") or P.get("accent") or P["head"], "then": P["muted"], "to": P["text"]}
        items = []
        for row in rows:
            x = lft
            runs = []                                         # (same font and role: one text)
            for text, f, role in row:
                if role == "step":
                    continue
                if runs and runs[-1][1] is f and runs[-1][2] == role:
                    runs[-1][0].append(text)
                else:
                    runs.append(([text], f, role))
            for words, f, role in runs:
                t = " ".join(words)
                items.append(self._camp_text(cv, P, x, y, t, f, col[role], "w", tags))
                x += _measure(f, t + " ")
            for text, f, role in row:
                if role == "step":                            # (the step: at the right of the head's line)
                    it = self._camp_text(cv, P, rgt, y, text, f, col["step"], "e", tags + ("campstep",))
                    if "ⓘ" in text:
                        cv.addtag_withtag("campstep", it)
                        self.ov_tip(cv, "campstep", lambda: (CP.line() or {}).get("tip") or "", hand=False)
            y += lh
        for item in items:
            click_not_drag(cv, item, self.camp_route_show)      # (2.112.5: a drag moves the line, no card)
            cv.tag_bind(item, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(item, "<Leave>", lambda e: cv.configure(cursor=""))
        return items

    @staticmethod
    def _camp_text(cv, P, x, y, text, f, fill, anchor, tags):
        """A text of the line, with the look's outline when it has one (box-less looks, over the game)."""
        halo = P.get("halo")
        if halo:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                cv.create_text(x + dx, y + dy, text=text, font=f, fill=halo, anchor=anchor, tags=tags)
        return cv.create_text(x, y, text=text, font=f, fill=fill, anchor=anchor, tags=tags)

    # ---------------------------------------------------------------- the Campaign Bar's parts: how each was worked out
    def camp_zone_text(self):
        run = CP.char()
        z = run.get("hub") or run.get("zone") or "-"
        zl = run.get("zone_level") or 0
        return f"{z} · lvl {zl}" if zl else z

    def camp_zone_tip(self):
        run = CP.char()
        z, zl, aid = run.get("zone") or "-", run.get("zone_level") or 0, run.get("area") or "?"
        zt = CP.zone_time(run)
        return (f"{z}, level {zl} - from the game's log ('Generating level {zl} area \"{aid}\"').\n"
                + (f"Here for {CP.fmt(zt)}." if zt is not None else "Time here: from the next zone you enter."))

    def camp_you_text(self):
        d = CP.line() or {}
        you, zl = d.get("level") or (CP.char_level(), 0)
        t = CP.level_text(you, zl)
        if getattr(self, "_camp_you_mode", "full") == "short" and " · " in t:   # (a narrow bar: the words, the
            mark = t.split(" ", 1)[0]                                            # level is on the hover)
            return f"{mark} {t.rsplit(' · ', 1)[1]}"
        return t

    @staticmethod
    def camp_you_tip():
        d = CP.line() or {}
        you, zl = d.get("level") or (CP.char_level(), 0)
        return CP.level_how(you, zl) + "\nYour level: from the game's log ('is now level ...')."

    def camp_got_text(self, mode=None):
        g = CP.got_so_far()
        mode = mode or getattr(self, "_camp_got_mode", "full")
        p, sp = g["points"], g["spirit"]
        if mode == "short":
            return f"Points {p[0]}/{p[1]}"
        if mode == "mid":
            return f"Points {p[0]}/{p[1]} · Spirit {sp[0]}/{sp[1]}"
        return CP.got_text(g)

    @staticmethod
    def camp_got_tip():
        return CP.got_how(CP.got_so_far())

    @staticmethod
    def camp_act_text():
        t = CP.act_time()
        return CP.fmt(t) if t is not None else "-"

    @staticmethod
    def camp_act_tip():
        run = CP.char()
        key = run.get("act")
        best = CP.cfg()["best"].get(CP.SETTINGS.get("league") or "", {}).get(key)
        done = key in run.get("closed", [])
        return (f"{CP.act_name(key)}: {CP.fmt(CP.act_time(run))}" + (" (done)" if done else " so far")
                + (f" - your best this league {CP.fmt(best)}" if best else "") + ".\n"
                "From the zone changes in the game's log; AFK and gaps over 15 minutes don't count. "
                "The act ends on its last boss.")

    # ================================================================ cards over the game
    def _camp_card(self, title, icon, W, top=0.10, on_close=None, on_moved=None):
        from .overlaywin import OverlayWindow, pal
        from .alerts_page import game_rect
        P = pal()
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        W = self.ov_px(W)                                    # 2.78.3: the game's size
        geo = (r[0] + (r[2] - W) // 2, r[1] + int(r[3] * top), W, None)
        w = OverlayWindow(self.root, title, icon, geo, palette=P, lockable=False, follow_game=True,
                          no_activate=True, on_close=on_close, on_moved=on_moved)
        body = tk.Frame(w.body, bg=P["bg"], padx=16, pady=8)
        body.pack(fill="both", expand=True)
        return w, body, P

    # ---------------------------------------------------------------- M, N, Q: the route card
    def camp_route_show(self, page=None, act_key=None):
        if getattr(self, "camp_win", None) is not None:
            if act_key and act_key != self.camp_view:         # another act: its pages again (2.125.4: not the card)
                self.camp_view = act_key
                if page:
                    self.camp_tab(page)
                self.camp_pages_refresh()
            elif page:
                self.camp_tab(page)                           # 2.124.0: a tab only swaps the page shown
            return self.camp_win
        self.camp_page = page or "Route"
        self.camp_view = act_key or CP.char().get("act") or (CP.acts()[0]["key"] if CP.acts() else None)
        self._camp_act = CP.char().get("act")
        w, body, P = self._camp_card("Campaign", "🗺", 560, on_close=lambda: self.camp_route_close(),
                                     on_moved=self._camp_card_moved)
        self.camp_win, self.camp_body, self.camp_P = w, body, P
        self.camp_size = (0, 0)
        self.camp_route_fill()
        w.show()
        return w

    def _camp_card_moved(self, _x, _y, w, h):
        """2.125.4 (feedback: the size was not remembered after resizing): a size you give the card is kept (Campaign
        card_size) and used from then on - a longer page scrolls instead of growing it."""
        if (w, h) != tuple(getattr(self, "camp_size", (0, 0))):
            self.camp_size = (w, h)
            CP.cfg()["card_size"] = [int(w), int(h)]
            CP.save()

    def camp_route_close(self):
        w, self.camp_win = getattr(self, "camp_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def camp_route_fill(self):
        """Build the card: the tabs, the act list and all three pages at once (2.124.0, feedback: clicking Rewards
        made the window resize over and over) - a tab then only swaps the page shown, and the card keeps one size,
        the biggest page's."""
        body, P = self.camp_body, self.camp_P
        keep = getattr(getattr(self, "camp_pop", None), "kind", None)     # (a switch in Options ▾ keeps it open)
        for c in body.winfo_children():
            c.destroy()
        try:
            if self.camp_pop is not None:
                self.camp_pop.destroy()
        except (AttributeError, tk.TclError):
            pass
        self.camp_pop = None
        bg = P["bg"]
        top = tk.Frame(body, bg=bg)
        top.pack(fill="x")
        self.camp_page_btns = {}
        for p in PAGES:
            b = ttk.Button(top, text=p, style=self.ov_btn("Primary.TButton" if p == self.camp_page else "Quiet.TButton"),
                           command=lambda p=p: self.camp_route_show(page=p), width=len(p) + 1)   # (2.125.4: snug)
            b.pack(side="left", padx=(0, 4))
            self.camp_page_btns[p] = b
        names = [a["name"] for a in CP.acts()]
        self.camp_act_cb = None
        if names:
            self.camp_act_var = tk.StringVar(value=CP.act_name(self.camp_view))
            cb = self.ov_combo(ttk.Combobox(top, values=names, textvariable=self.camp_act_var, state="readonly",
                                            width=12))
            # 2.124.0: after the list has closed - the card is built again, and the list went with it while its
            # own dropdown still held the mouse
            cb.bind("<<ComboboxSelected>>", lambda e: self.root.after(1, lambda: self.camp_route_show(
                act_key=next((a["key"] for a in CP.acts() if a["name"] == self.camp_act_var.get()), None))))
            self.camp_act_cb = cb
        # 2.125.3 (feedback: pick the route and the options from that screen itself): Routes ▾
        # and Options ▾, each a small panel inside the card (a window of its own sent the card behind the game)
        for key, label, tip in (("options", "Options ▾", "The Campaign Helper's options (as on Overlay › Options)"),
                                ("routes", "Routes ▾", "Pick the route: Full, Speedrun or Rush (carry)")):
            b = ttk.Button(top, text=label, style=self.ov_btn("Quiet.TButton"),
                           command=lambda k=key: self.camp_pop_toggle(k), width=len(label) + 1)
            b.pack(side="right", padx=(4, 0))
            from .style import Tooltip
            Tooltip(b, tip)
            setattr(self, f"camp_{key}_btn", b)
        # 2.125.3 (feedback: the full list did not scroll when the window was resized): the pages scroll
        from .style import ScrollArea
        self.camp_scroll = ScrollArea(body, bg=bg)
        self.camp_scroll.pack(fill="both", expand=True, pady=(8, 0))
        self.camp_pages = {}
        for name, fn in (("Route", self._camp_route_page), ("Rewards", self._camp_rewards_page),
                         ("Act times", self._camp_splits_page)):
            page = tk.Frame(self.camp_scroll.inner, bg=bg)
            fn(page, P)
            self.camp_pages[name] = page
        w = self.camp_win
        self._camp_dirty = set()
        need_w, need_h = getattr(self, "camp_size", (0, 0))
        saved = CP.cfg().get("card_size")
        for name in (() if saved else PAGES):                 # (each page shown once to measure it)
            self._camp_show_page(name)
            try:
                w.update_idletasks()
                pg = self.camp_pages[name]
                need_w = max(need_w, top.winfo_reqwidth() + 40, pg.winfo_reqwidth() + 40)
                need_h = max(need_h, top.winfo_reqheight() + pg.winfo_reqheight() + 64)
            except tk.TclError:
                pass
        self._camp_show_page(self.camp_page)
        try:                                                  # 2.125.4: never narrower than its toolbar (Routes ▾
            w.update_idletasks()                              # and Options ▾ went out of sight)
            w.min_size = (top.winfo_reqwidth() + 40, 200)
            need_w = max(need_w, w.min_size[0])
        except (tk.TclError, AttributeError):
            pass
        if keep == "options":
            self.root.after(1, lambda: self.camp_pop is None and self.camp_pop_toggle("options"))
        try:                                                  # one size (the biggest page's), at most most of the
            from .style import monitor_rect                   # screen - the rest scrolls
            _l, t, _r, b = monitor_rect(self.root, w.winfo_x() + 20, w.winfo_y() + 20)
            if saved:
                need_w, need_h = max(need_w, int(saved[0])), max(200, int(saved[1]))
                need_h = min(need_h, b - t - 40)
            else:
                need_h = min(need_h, int((b - t) * 0.85))
            self.camp_size = (need_w, need_h)
            w.geometry(f"{need_w}x{need_h}+{w.winfo_x()}+{w.winfo_y()}")
        except tk.TclError:
            pass

    def camp_pop_toggle(self, kind):
        """Routes ▾ / Options ▾: a small panel under its button, inside the card; again closes it."""
        old = getattr(self, "camp_pop", None)
        self.camp_pop = None
        if old is not None:
            kind_was = getattr(old, "kind", None)
            try:
                old.destroy()
            except tk.TclError:
                pass
            if kind_was == kind:
                return
        P, w = self.camp_P, self.camp_win
        bg = P.get("cell_bg") or P["bg"]
        pop = tk.Frame(w.body, bg=bg, highlightthickness=1, highlightbackground=P.get("accent") or P["line"],
                       padx=8, pady=8)
        pop.kind = kind
        if kind == "routes":
            # 2.125.4 (feedback: a visual hierarchy to divide the selectable options): each route its own row -
            # a line between them, the one in use on a lighter ground with a bar and "✓ In use", a row lights on hover
            pop.configure(padx=0, pady=0)
            cur = CP.route_of(CP.char())
            from .style import mix
            hi = mix(bg, P["text"], 0.10)                    # (a ground you can see on every look)
            sel = mix(bg, P.get("accent") or P["head"], 0.16)
            acc = P.get("accent") or P["head"]
            for i, (k, name) in enumerate(CP.ROUTES):
                on = k == cur
                if i:
                    tk.Frame(pop, bg=P["line"], height=1).pack(fill="x")
                rbg = sel if on else bg
                row = tk.Frame(pop, bg=rbg, cursor="hand2")
                row.pack(fill="x")
                bar = tk.Frame(row, bg=acc if on else rbg, width=3)
                bar.pack(side="left", fill="y")
                box = tk.Frame(row, bg=rbg, padx=12, pady=8)
                box.pack(side="left", fill="both", expand=True)
                tl = tk.Frame(box, bg=rbg)
                tl.pack(fill="x")
                t = tk.Label(tl, text=name, bg=rbg, fg=P["head"] if on else P["text"],
                             font=(P["font"], self.ov_font(10), "bold"), anchor="w")
                t.pack(side="left")
                parts = [row, box, tl, t]
                if on:
                    u = tk.Label(tl, text="✓ In use", bg=rbg, fg=acc, font=(P["font"], self.ov_font(8), "bold"))
                    u.pack(side="right")
                    parts.append(u)
                d = tk.Label(box, text=CP.ROUTE_LINES.get(k, ""), bg=rbg, fg=P["muted"],
                             font=(P["font"], self.ov_font(8)), anchor="w", justify="left", wraplength=320)
                d.pack(fill="x", pady=(2, 0))
                d.bind("<Configure>", lambda _e: None)        # (keeps its own wrap - no style._rewrap)
                parts.append(d)
                row.route_name, row.parts, row.base = name, parts, rbg
                for wdg in parts:
                    wdg.bind("<Button-1>", lambda _e, n=name: (self.camp_pop_toggle("routes"),
                                                               self.camp_route_pick(n)))
                    if not on:
                        wdg.bind("<Enter>", lambda _e, r=row: [x.configure(bg=hi) for x in r.parts])
                        wdg.bind("<Leave>", lambda _e, r=row: [x.configure(bg=r.base) for x in r.parts])
        else:
            c = CP.cfg()
            for k, label in CAMP_OPTS:
                v = tk.BooleanVar(value=bool(c[k]))
                cb = tk.Checkbutton(pop, text=label, variable=v, bg=bg, fg=P["text"], activebackground=bg,
                                    activeforeground=P["text"], selectcolor=P.get("field") or bg,
                                    font=(P["font"], self.ov_font(9)), anchor="w", highlightthickness=0, bd=0,
                                    command=lambda k=k, v=v: self.camp_opt(k, bool(v.get())))
                cb.pack(fill="x", anchor="w", pady=1)
        btn = getattr(self, f"camp_{kind}_btn")
        try:
            w.update_idletasks()
            x = btn.winfo_rootx() - w.body.winfo_rootx() + btn.winfo_width()
            y = btn.winfo_rooty() - w.body.winfo_rooty() + btn.winfo_height() + 2
            pop.place(x=x, y=y, anchor="ne")
            pop.lift()
        except tk.TclError:
            pass
        self.camp_pop = pop

    def _camp_show_page(self, name):
        for n, pg in self.camp_pages.items():
            if n != name:
                pg.pack_forget()
        self.camp_pages[name].pack(fill="both", expand=True)
        try:
            self.camp_scroll.canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass
        cb = getattr(self, "camp_act_cb", None)
        if cb is not None:
            if name == "Act times":
                cb.pack_forget()
            elif not cb.winfo_ismapped():                     # 2.125.4 (feedback): on the far right
                cb.pack(side="right", padx=(8, 0), before=self.camp_options_btn)

    def camp_tab(self, page):
        if page not in getattr(self, "camp_pages", {}):
            return
        self.camp_page = page
        self._camp_build_page(page)
        for p, b in self.camp_page_btns.items():
            b.configure(style=self.ov_btn("Primary.TButton" if p == page else "Quiet.TButton"))
        self._camp_show_page(page)

    def _camp_route_page(self, page, P):
        bg, c, run = P["bg"], CP.cfg(), CP.char()
        key = self.camp_view
        head = tk.Frame(page, bg=bg)
        head.pack(fill="x")
        town = (CP.act(key) or {}).get("town") or ""
        tk.Label(head, text=(CP.act_name(key) + (f" · {town}" if town else "")).upper(), bg=bg, fg=P["head"],
                 font=(P["hfont"] or P["font"], self.ov_font(10), "bold"), anchor="w").pack(side="left")
        tk.Label(head, text="route: " + dict(CP.ROUTES).get(CP.route_of(), ""), bg=bg, fg=P["muted"],
                 font=(P["font"], self.ov_font(9))).pack(side="right")
        rows = CP.steps(key, run)
        self.camp_rows = []
        self.camp_marks = marks = {"done": ("✓", P["on"]), "here": ("▸", P["head"]), "todo": ("○", P["muted"]),
                 "passed": ("–", P["muted"])}
        state = {}                                             # pack 4: the line has the reward in it - the
        for r in CP.rewards(key):                              # right side only says got / missed (never twice)
            st = run["rewards"].get(r["id"])
            state.setdefault(CP.norm(r["zone"]), []).append(st)
        patch = CP.pack().get("patch", "?")
        for i, s in enumerate(rows):
            here = s["state"] == "here"
            rbg = P.get("cell_bg", bg) if here else bg
            f = tk.Frame(page, bg=rbg, cursor="hand2")
            f.pack(fill="x", pady=1)
            mk, col = marks[s["state"]]
            ml = tk.Label(f, text=mk, bg=rbg, fg=col, width=2, font=(P["font"], self.ov_font(10)))
            ml.pack(side="left")
            txt = s["zone"] + (f" - {s['do']}" if s.get("do") else "")
            fg = P["text"] if s["state"] in ("here", "todo") else P["muted"]
            tl = tk.Label(f, text=txt, bg=rbg, fg=fg, font=(P["font"], self.ov_font(10), "bold" if here else "normal"),
                          anchor="w", wraplength=380, justify="left")
            tl.pack(side="left", fill="x", expand=True)
            f.parts = (ml, tl)
            sts = state.get(CP.norm(s["zone"]), [])
            side, good = "", False
            if s.get("learned"):
                side = f"not in the {patch} guide"
            elif sts and all(x == "got" for x in sts):
                side, good = "✓ got", True
            elif "missed" in sts:
                side = "✕ missed"
            elif s["state"] == "passed":
                side = "passed"
            elif s.get("note"):
                side = s["note"]
            if side:
                tk.Label(f, text=side, bg=rbg, fg=P["on"] if good else P["muted"],
                         font=(P["font"], self.ov_font(9))).pack(side="right")
            for wdg in [f] + list(f.winfo_children()):
                wdg.bind("<Button-1>", lambda e, i=i: self.camp_here(i))
            self.camp_rows.append(f)
            if here and s.get("tip") and c["tips"]:
                tk.Label(page, text="ⓘ " + s["tip"], bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9)),
                         anchor="w", justify="left", wraplength=self.ov_px(480)).pack(fill="x", padx=(24, 0))
            if here and s.get("learned"):
                self._camp_unknown_row(page, P, s)
        if not rows:
            tk.Label(page, text="The guide has no steps for this act yet - they're added as you go.", bg=bg,
                     fg=P["muted"], font=(P["font"], self.ov_font(10))).pack(anchor="w")
        nav = tk.Frame(page, bg=bg)
        nav.pack(fill="x", pady=(8, 0))
        ttk.Button(nav, text="◀", width=3, style=self.ov_btn(), command=lambda: self.camp_step(-1)).pack(side="left")
        ttk.Button(nav, text="▶", width=3, style=self.ov_btn(), command=lambda: self.camp_step(1)).pack(side="left", padx=(4, 0))
        tk.Label(nav, text="Click a step: I'm here", bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9))).pack(side="left",
                                                                                                 padx=(8, 0))
        tip = (CP.act(key) or {}).get("tip")
        if tip and c["tips"]:
            tk.Label(page, text="Tip: " + tip, bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9)), anchor="w",
                     justify="left", wraplength=self.ov_px(520)).pack(fill="x", pady=(8, 0))

    def _camp_unknown_row(self, page, P, s):
        """P: a zone the guide doesn't know - a note for it, Mark optional, or check for a newer guide."""
        bg = P["bg"]
        f = tk.Frame(page, bg=bg)
        f.pack(fill="x", pady=(2, 8), padx=(24, 0))
        tk.Label(f, text="The guide doesn't have this zone yet. It's on your route where you went, with its level, "
                         "so it's there next time.", bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9)), anchor="w",
                 justify="left", wraplength=self.ov_px(480)).pack(fill="x")
        row = tk.Frame(f, bg=bg)
        row.pack(fill="x", pady=(4, 0))
        self.camp_note_var = tk.StringVar(value=s.get("note", ""))
        e = ttk.Entry(row, textvariable=self.camp_note_var, width=22)
        e.pack(side="left")
        ttk.Button(row, text="Add a note", style=self.ov_btn("Primary.TButton"),
                   command=lambda: self.camp_note(s["zone"])).pack(side="left", padx=(4, 0))
        ttk.Button(row, text="Mark optional", style=self.ov_btn("Quiet.TButton"),
                   command=lambda: self.camp_optional(s["zone"])).pack(side="left", padx=(4, 0))
        ttk.Button(row, text="Check for a newer guide", style=self.ov_btn("Quiet.TButton"),
                   command=self.camp_check_pack).pack(side="left", padx=(4, 0))

    def _camp_rewards_page(self, page, P):
        bg, run = P["bg"], CP.char()
        tot = CP.totals(run)
        self.camp_total_labs = {}
        grid = tk.Frame(page, bg=bg)
        grid.pack(fill="x")
        cells = (("POINTS", "points"), ("SPIRIT", "spirit"))
        for i, (lab, k) in enumerate(cells):
            have, of = tot.get(k, (0, 0))
            f = tk.Frame(grid, bg=bg)
            f.grid(row=0, column=i, sticky="w", padx=(0, 24))
            tk.Label(f, text=lab, bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(8), "bold")).pack(anchor="w")
            self.camp_total_labs[k] = tk.Label(f, text=f"{have} / {of}", bg=bg, fg=P["text"],
                                               font=(P["font"], self.ov_font(15), "bold"))
            self.camp_total_labs[k].pack(anchor="w")
        f = tk.Frame(grid, bg=bg)
        f.grid(row=0, column=2, sticky="w")
        tk.Label(f, text="RESISTANCES", bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(8), "bold")).pack(anchor="w")
        self.camp_total_labs["res"] = tk.Label(f, text=self._camp_res_text(tot), bg=bg, fg=P["text"],
                                               font=(P["font"], self.ov_font(10), "bold"))
        self.camp_total_labs["res"].pack(anchor="w", pady=(4, 0))
        tk.Label(page, text=CP.act_name(self.camp_view).upper(), bg=bg, fg=P["head"],
                 font=(P["hfont"] or P["font"], self.ov_font(9), "bold"), anchor="w").pack(fill="x", pady=(8, 2))
        self.camp_reward_vars = {}
        for r in CP.rewards(self.camp_view):
            st = run["rewards"].get(r["id"])
            v = tk.BooleanVar(value=st == "got")
            self.camp_reward_vars[r["id"]] = v
            row = tk.Frame(page, bg=bg)
            row.pack(fill="x")
            cb = tk.Checkbutton(row, text=f"{r['zone']} - {r['what']}: {r['gives']}", variable=v, bg=bg,
                                fg=P["text"], selectcolor=bg, activebackground=bg, activeforeground=P["text"],
                                font=(P["font"], self.ov_font(10)), anchor="w", highlightthickness=0, bd=0,
                                command=lambda r=r, v=v: self.camp_tick(r["id"], v.get()))
            cb.pack(side="left")
            if st in ("missed", "skip", "remind"):
                tk.Label(row, text={"missed": "✕ missed", "skip": "– skipped", "remind": "○ not yet"}[st], bg=bg,
                         fg=P.get("off", P["muted"]) if st == "missed" else P["muted"],
                         font=(P["font"], self.ov_font(9))).pack(side="right")
        tk.Label(page, text=f"The list comes from the guide pack ({CP.pack().get('name', '')}). A boss's line in the "
                            "game's log ticks its reward; the rest are asked in town. Tick or untick any by hand.",
                 bg=bg, fg=P["muted"],
                 font=(P["font"], self.ov_font(9)), anchor="w", justify="left", wraplength=self.ov_px(520)).pack(fill="x", pady=(8, 0))

    def _camp_splits_page(self, page, P):
        bg = P["bg"]
        g = tk.Frame(page, bg=bg)
        g.pack(fill="x")
        for c, h in enumerate(("ACT", "THIS RUN", "BEST", "+/-")):
            tk.Label(g, text=h, bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(8), "bold")).grid(row=0, column=c, sticky="w",
                                                                                     padx=(0, 24))
        self.camp_split_rows = []
        for i, (name, mine, best, here) in enumerate(CP.splits(), start=1):
            diff, dcol = "", P["muted"]
            if mine is not None and best is not None and not here:
                d = round(mine - best)
                diff, dcol = (("+" if d > 0 else "-") + CP.fmt(abs(d)), P.get("off", P["muted"]) if d > 0 else P["on"])
                if d == 0:
                    diff, dcol = "even", P["muted"]
            elif mine is not None and best is not None and here and mine < best:
                diff, dcol = "ahead", P["on"]
            vals = (name, CP.fmt(mine) + (" ▸" if here else ""), CP.fmt(best), diff)
            for c, v in enumerate(vals):
                tk.Label(g, text=v, bg=bg, fg=dcol if c == 3 else (P["text"] if mine is not None else P["muted"]),
                         font=(P["font"], self.ov_font(10))).grid(row=i, column=c, sticky="w", padx=(0, 24))
            self.camp_split_rows.append(vals)
        tk.Label(page, text="From the game log's zone changes, with pauses for AFK. Each league keeps its own best.",
                 bg=bg, fg=P["muted"], font=(P["font"], self.ov_font(9)), anchor="w").pack(fill="x", pady=(8, 0))

    # ---------------------------------------------------------------- actions
    def camp_here(self, i):
        run = CP.char()
        same = run.get("act") == self.camp_view
        if same:
            CP.set_here(i, run)
        else:
            CP.start_here(self.camp_view, i, run)                  # "Start from here" (partway through)
        if same and self._camp_rows_restyle():                     # 2.124.0: only the rows whose mark changed
            return self.camp_refresh(card=False)
        self.camp_refresh()

    def _camp_rows_restyle(self):
        """The route page's rows take their new state (✓ ▸ ○ –) in place. -> False when the steps changed."""
        rows, P = CP.steps(self.camp_view, CP.char()), self.camp_P
        frames = getattr(self, "camp_rows", None) or []
        if len(rows) != len(frames) or any(s.get("learned") for s in rows):
            return False
        bg = P["bg"]
        try:
            for s, f in zip(rows, frames):
                here = s["state"] == "here"
                rbg = P.get("cell_bg", bg) if here else bg
                mk, col = self.camp_marks[s["state"]]
                ml, tl = f.parts
                if ml.cget("text") == mk and f.cget("bg") == rbg:
                    continue
                for wdg in f.winfo_children() + [f]:
                    wdg.configure(bg=rbg)
                ml.configure(text=mk, fg=col)
                tl.configure(fg=P["text"] if s["state"] in ("here", "todo") else P["muted"],
                             font=(P["font"], self.ov_font(10), "bold" if here else "normal"))
        except (tk.TclError, AttributeError, KeyError):
            return False
        return True

    def camp_step(self, delta):
        """◀ ▶ on the route card: a step back or on (2.124.0: within the act, only the rows that changed)."""
        CP.step_by(delta)
        act = CP.char().get("act") or self.camp_view
        if act == self.camp_view and getattr(self, "camp_win", None) is not None and self._camp_rows_restyle():
            return self.camp_refresh(card=False)
        self.camp_view = act
        self.camp_refresh()

    def camp_tick(self, rid, on):
        """A reward ticked on the card: its box already shows it - the totals and the overlay's line follow
        (2.124.0: the card isn't built again)."""
        CP.set_reward(rid, "got" if on else None)
        self._camp_totals_paint()
        self._camp_dirty = getattr(self, "_camp_dirty", set()) | {"Route"}   # (its "worth" notes: when it's shown)
        self.camp_refresh(card=False)

    def _camp_totals_paint(self):
        tot, labs = CP.totals(CP.char()), getattr(self, "camp_total_labs", None) or {}
        try:
            for k, lab in labs.items():
                have, of = tot.get(k, (0, 0))
                if k == "res":
                    continue
                lab.configure(text=f"{have} / {of}")
            if "res" in labs:
                labs["res"].configure(text=self._camp_res_text(tot))
        except tk.TclError:
            pass

    @staticmethod
    def _camp_res_text(tot):
        res = []
        for k, name in (("res_cold", "Cold"), ("res_lightning", "Lightning"), ("res_fire", "Fire")):
            have, of = tot.get(k, (0, 0))
            res.append(f"{name} {'✓' if of and have >= of else '○'}")
        return " · ".join(res)

    def camp_note(self, zone):
        CP.set_note(zone, self.camp_note_var.get())
        self.camp_refresh()

    def camp_optional(self, zone):
        CP.mark_optional(zone)
        self.camp_refresh()

    def camp_check_pack(self):
        st, msg = CP.fetch_live()
        txt = {"new": f"New guide pack: {msg}.", "same": f"You have the newest guide pack ({msg})."}.get(st, msg)
        self._say(txt, 6)
        if getattr(self, "tk_camp_pack", None) is not None:
            try:
                self.tk_camp_pack.config(text=self.camp_pack_text())
            except tk.TclError:
                pass
        if st == "new":
            self.camp_refresh()
        return st

    def camp_pack_text(self):
        p = CP.pack()
        return f"Guide pack: {p.get('name', '?')} (revision {p.get('revision', 0)})"

    # ---------------------------------------------------------------- the rewards to answer (N)
    def camp_ask_show(self):
        """In town: a reward the log can't see - Got it / Not yet (asks once more next town). One at a time (one
        main button on the card); the rest follow as you answer."""
        self.camp_ask_close()
        items = CP.asks()
        if not items:
            return None
        r, st = items[0]
        w, body, P = self._camp_card("Campaign rewards", "★", 460, top=0.16, on_close=lambda: self.camp_ask_close())
        bg = P["bg"]
        self.camp_ask_btns = {}
        if st == "missed":
            head, txt = "Missed one:", f"{r['what']} in {r['zone']} ({r['gives']}). It's still there."
        elif r.get("town"):
            head = "In town: " + r["town"][0].lower() + r["town"][1:]
            txt = f"{r['what']} ({r['gives']}). Did you get it?"
        else:
            head, txt = "Did you get it?", f"{r['what']} in {r['zone']} ({r['gives']})."
        tk.Label(body, text=head, bg=bg, fg=P["head"], font=(P["font"], self.ov_font(10), "bold"), anchor="w",
                 justify="left", wraplength=self.ov_px(420)).pack(fill="x")
        tk.Label(body, text=txt, bg=bg, fg=P["text"], font=(P["font"], self.ov_font(10)), anchor="w", justify="left",
                 wraplength=self.ov_px(420)).pack(fill="x")
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", pady=(8, 0))
        from .style import Tooltip
        for k, label, style, tip in (("got", "Got it", "Primary.TButton", "Ticks it in Got so far"),
                                     ("not_yet", "Not yet", "TButton", "Leaves it open - asks once more next town")):
            b = ttk.Button(row, text=label, style=self.ov_btn(style), command=lambda k=k: self.camp_answer(r["id"], k))
            b.pack(side="left", padx=(0, 8))
            Tooltip(b, tip)
            self.camp_ask_btns[(r["id"], k)] = b
        if len(items) > 1:
            tk.Label(body, text=f"{len(items) - 1} more after this one", bg=bg, fg=P["muted"],
                     font=(P["font"], self.ov_font(9))).pack(anchor="w", pady=(8, 0))
        self.camp_ask_win = w
        w.show()
        return w

    def camp_answer(self, rid, how):
        """Got it / Not yet (asks once more at the next town)."""
        CP.set_reward(rid, how)
        if not self.camp_ask_show():
            self.camp_ask_close()
        self.camp_refresh()

    def camp_ask_close(self):
        w, self.camp_ask_win = getattr(self, "camp_ask_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- O: vendor search
    def camp_vendor_show(self):
        self.camp_vendor_close()
        w, body, P = self._camp_card("Vendor search", "🔎", 420, top=0.14, on_close=lambda: self.camp_vendor_close())
        bg = P["bg"]
        tk.Label(body, text="Click one = copied · Ctrl+V in the shop search", bg=bg, fg=P["muted"],
                 font=(P["font"], self.ov_font(9)), anchor="w").pack(fill="x")
        self.camp_vendor_btns = {}

        def group(title, rows):
            if not rows:
                return
            tk.Label(body, text=title, bg=bg, fg=P["head"], font=(P["hfont"] or P["font"], self.ov_font(8), "bold"),
                     anchor="w").pack(fill="x", pady=(8, 2))
            for name, rx in rows:
                b = ttk.Button(body, text=name, style=self.ov_btn(), command=lambda n=name, rx=rx: self.camp_copy(n, rx))
                b.pack(fill="x", pady=1)
                self.camp_vendor_btns[name] = b
        group("FOR THIS ACT", CP.vendor_searches())      # (2.92.2: your favorites: Regex ▾ on the bar)
        if not CP.vendor_searches():
            tk.Label(body, text="No vendor searches for this act.", bg=bg, fg=P["muted"],
                     font=(P["font"], self.ov_font(9)), anchor="w").pack(fill="x", pady=(8, 0))
        # 2.124.0 (feedback: a click made the card wider to fit the "Copied: ..." line): two lines kept for it,
        # wrapped to the
        # card's width, and the card keeps its size
        self.camp_vendor_msg = tk.Label(body, text="", bg=bg, fg=P["on"], font=(P["font"], self.ov_font(9)), anchor="nw",
                                        justify="left", height=2)
        self.camp_vendor_msg.pack(fill="x", pady=(8, 0))
        self.camp_vendor_win = w
        w.show()
        try:
            w.update_idletasks()
            self.camp_vendor_msg.configure(wraplength=max(120, body.winfo_width() - 8))
            w.geometry(f"{w.winfo_width()}x{w.winfo_height()}+{w.winfo_x()}+{w.winfo_y()}")
        except tk.TclError:
            pass
        return w

    def camp_copy(self, name, rx):
        self.root.clipboard_clear()
        self.root.clipboard_append(rx)
        if getattr(self, "camp_vendor_msg", None) is not None:
            try:
                self.camp_vendor_msg.config(text=f"✓ Copied: {name} - paste it in the shop's search box.")
            except tk.TclError:
                pass
        return rx

    def camp_vendor_close(self):
        w, self.camp_vendor_win = getattr(self, "camp_vendor_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    # ================================================================ R: its settings (Overlay › Options)
    def camp_options(self, po, into=None):
        """Its options (route, splits ...). 2.82.0: into = the Campaign Helper card on Overlay › Options."""
        from .chrome import section as chrome_section
        from .style import C, SegBar
        c = CP.cfg()
        P2 = C["panel2"]
        if into is not None:
            box = tk.Frame(into, bg=P2)
            box.pack(fill="x", pady=(8, 0))
        else:
            so, box = chrome_section(po, "Campaign", "The Campaign Helper: where you are, what's next and what it's "
                                                      "worth - from the game's log. Click its line on the overlay for "
                                                      "the act's route, rewards and splits.")
            so.pack(fill="x", pady=(8, 0))
        row = tk.Frame(box, bg=P2)
        row.pack(fill="x")
        tk.Label(row, text="Route", bg=P2, fg=C["text"]).pack(side="left", padx=(0, 8))
        names = [n for _k, n in CP.ROUTES]
        self.tk_camp_route = SegBar(row, names, value=dict(CP.ROUTES).get(c["route"], names[0]), size=9, pad=(12, 4),
                                    command=self.camp_route_pick)
        self.tk_camp_route.pack(side="left")
        self.tk_camp_route_line = tk.Label(box, text=CP.ROUTE_LINES.get(c["route"], ""), bg=P2, fg=C["muted"],
                                           font=("Segoe UI", 9), anchor="w", justify="left", wraplength=520)
        self.tk_camp_route_line.pack(fill="x", pady=(2, 0))    # 2.125.0: what the route picked does, in one line
        grid = tk.Frame(box, bg=P2)
        grid.pack(fill="x", pady=(8, 0))
        self.tk_camp_vars = {}
        opts = CAMP_OPTS
        # (2.96.1: no Act timer switch - act times are always kept; the Leaderboards get them only if you share data)
        for i, (k, label) in enumerate(opts):
            v = tk.BooleanVar(value=bool(c[k]))
            self.tk_camp_vars[k] = v
            cb = ttk.Checkbutton(grid, text=label, variable=v, style="Card.TCheckbutton",
                                 command=lambda k=k: self.camp_opt(k))
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 24), pady=2)
        # (2.90.0: Dock is in On the bar › Lines above the bar, with the lines themselves)
        for col in range(2):
            grid.columnconfigure(col, uniform="cs")
        pk = tk.Frame(box, bg=P2)
        pk.pack(fill="x", pady=(8, 0))
        self.tk_camp_pack = tk.Label(pk, text=self.camp_pack_text(), bg=P2, fg=C["muted"], font=("Segoe UI", 9))
        self.tk_camp_pack.pack(side="top" if into is not None else "left", anchor="w")   # 2.82.0: in a card, own line
        ttk.Button(pk, text="Check for a newer one", style="Quiet.TButton", command=self.camp_check_pack).pack(
            side="left", padx=(0 if into is not None else 8, 0), pady=(4 if into is not None else 0, 0))

    def camp_route_pick(self, name):
        CP.cfg()["route"] = next((k for k, n in CP.ROUTES if n == name), "full")
        seg = getattr(self, "tk_camp_route", None)               # 2.125.3: picked on the card - Settings follows
        if seg is not None and getattr(seg, "value", name) != name:
            try:
                seg.pick(name, notify=False)
            except Exception:
                buglog.caught()
        lab = getattr(self, "tk_camp_route_line", None)
        if lab is not None:
            try:
                lab.config(text=CP.ROUTE_LINES.get(CP.cfg()["route"], ""))
            except tk.TclError:
                pass
        run = CP.char()
        if run.get("act") is not None:              # 2.89.0: the run you're on follows too (2.125.0: a finished one
            run["route"] = CP.cfg()["route"]         # too - a carrier's character is past the campaign)
        CP.save()
        self.camp_route_ask_close()
        self.camp_refresh(line_later=True)

    def camp_opt(self, k, value=None):
        """One Campaign option (Overlay › Options or the card's Options ▾ - the same setting, kept in step)."""
        if value is None:
            value = bool(self.tk_camp_vars[k].get())
        CP.cfg()[k] = bool(value)
        v = (getattr(self, "tk_camp_vars", None) or {}).get(k)
        try:
            if v is not None and bool(v.get()) != bool(value):
                v.set(bool(value))
        except tk.TclError:
            pass
        CP.save()
        self.camp_refresh(line_later=True)

    def camp_line_switch(self, var=None):
        CP.cfg()["line"] = bool((var or self.tk_cline_var).get())    # 2.90.0: the box you clicked, not a stale copy
        CP.save()
        self.merged_build()

    def camp_vendor_toggle(self):
        """2.92.2: Vendor ▾ on the bar opens / closes the card."""
        if getattr(self, "camp_vendor_win", None) is not None:
            self.camp_vendor_close()
        else:
            self.camp_vendor_show()
        if getattr(self, "mg_win", None) is not None:
            self.merged_build()

    def camp_vendor_switch(self, var=None):
        on = bool((var or self.tk_cvendor_var).get())
        CP.cfg()["vendor"] = on
        self.bar_cfg()["vendor"] = on                 # 2.92.2: one switch (it was two that had to agree)
        self.tracker_save()
        bv = (getattr(self, "tk_bar_vars", None) or {}).get("vendor")
        if bv is not None and bv is not var and bool(bv.get()) != on:
            bv.set(on)
        CP.save()
        if not CP.cfg()["vendor"]:
            self.camp_vendor_close()
        self.merged_build()
