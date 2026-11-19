"""Two parts of the overlay that got their own place (2.76.0).

  * Map rank - your rank for the map you're in (S A B C D or Avoid; the community's in brackets when you have none)
    was glued onto "where you are". It's its own part now, with its own switch (Overlay › Options › On the overlay).
    Click it to rank the map. "Ask me to rank maps I haven't ranked" (on by default): leaving a map you haven't
    ranked, a small card asks - S A B C D Avoid, Not now, or Never for this map. Feedback: isolate the Map
    Tier / rating piece on the overlay and add an option to prompt a user to rate unrated maps.
  * The lines - League Plan's NOW line, and the Campaign Helper's (2.77.0). 2.124.0: drawn at
    the top of the overlay's own window (they had their own small bar), which grows upward by their height - the bar
    never moves. Feedback: combine it with the bar instead of an isolated separate bar.

GGG ToS: windows and the game's log only - nothing is sent to the game."""
import tkinter as tk
from tkinter import ttk
from . import buglog

RANK_BUTTONS = ("S", "A", "B", "C", "D", "Avoid")


class OverlayParts:
    """Mixed into App."""

    # ================================================================ map rank
    def rank_text(self, where):
        """'★ A', '★ (B)' (the community's), '★ -' (none yet) or '' (not in a map)."""
        if not where or where == "-":
            return ""
        r = self._ov_rank(where).strip()
        if r.startswith("["):
            return "★ " + r.strip("[]").title()
        if r.startswith("("):
            return "★ " + r
        return "★ -"

    def rank_ask_on(self):
        return bool(self.tracker_cfg().get("rank_ask", True))

    def maprank_log(self, kind, data):
        """The session tracker's log events: leaving a map you haven't ranked -> the card (if the option is on)."""
        if kind != "area":
            return None
        from .gamelog import area_kind
        ak = area_kind(data.get("area"), data.get("seed"), data.get("level", 0))
        if ak == "map":
            from .maplib import display_name                 # 2.78.1: its name, not its area id ("MapRugosa")
            self._mr_in = display_name(data.get("area"))
            return None
        left, self._mr_in = getattr(self, "_mr_in", None), None
        if left:
            self._mr_last = left
        if not left or ak not in ("town", "hideout") or not self.rank_ask_on():
            return None
        from .config import SETTINGS
        from .maplib import display_name, ranks
        never = SETTINGS.get("rank_never") or []
        if any(display_name(n) != n for n in never):         # 2.78.1: ids saved by 2.76.0 -> names
            SETTINGS["rank_never"] = never = list(dict.fromkeys(display_name(n) for n in never))
        if left in ranks() or left in never:
            return None
        return self.maprank_prompt(left)

    def maprank_click(self):
        """The rank on the overlay was clicked: rank the map you're in (or were in last)."""
        where = getattr(self, "_mr_in", None) or getattr(self, "_mr_last", None)
        if where:
            return self.maprank_prompt(where)
        self._say("Rank a map from the Map Library (Overlay ↳ Map Library), or click this while you're in one.", 6)
        return None

    def maprank_prompt(self, name):
        """A small card at the top of the game: how was this map? -> the window."""
        from .overlaywin import OverlayWindow, pal
        from .alerts_page import game_rect
        self.maprank_close()
        P = pal()
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        W = self.ov_px(420)                                  # 2.78.3: the game's size
        geo = (r[0] + (r[2] - W) // 2, r[1] + int(r[3] * 0.08), W, None)
        w = OverlayWindow(self.root, "Rank this map", "★", geo, palette=P, lockable=False, follow_game=True,
                          no_activate=True, on_close=self.maprank_close)
        bg = P["bg"]
        body = tk.Frame(w.body, bg=bg, padx=self.ov_px(16), pady=self.ov_px(8))
        body.pack(fill="both", expand=True)
        tk.Label(body, text=f"How was {name}?", bg=bg, fg=P["text"], font=(P["font"], self.ov_font(11), "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text="Your rank shows on the overlay next time, and counts as your vote for the community's.",
                 bg=bg, fg=P["muted"], font=(P.get("body") or P["font"], self.ov_font(9)), anchor="w", justify="left",
                 wraplength=W - self.ov_px(40)).pack(fill="x")
        row = tk.Frame(body, bg=bg)
        row.pack(fill="x", pady=(8, 0))
        self.maprank_btns = {}
        for rk in RANK_BUTTONS:
            b = ttk.Button(row, text=rk, width=6 if rk == "Avoid" else 3, style=self.ov_btn(),
                           command=lambda rk=rk: self.maprank_set(name, rk))
            b.pack(side="left", padx=(0, 4))
            self.maprank_btns[rk] = b
        row2 = tk.Frame(body, bg=bg)
        row2.pack(fill="x", pady=(8, 0))
        from .config import SETTINGS, save_json
        opts = [("later", "Not now"), ("never", "Never for this map")]
        if not SETTINGS.get("rank_card_seen"):              # 2.98.5: the first card you see: a way out of ranking
            SETTINGS["rank_card_seen"] = True
            save_json("settings.json", SETTINGS)
            opts.append(("optout", "Opt out"))
        for key, label in opts:
            b = ttk.Button(row2, text=label, style=self.ov_btn("Quiet.TButton"), command=lambda k=key: self.maprank_skip(name, k))
            b.pack(side="left", padx=(0, 8))
            self.maprank_btns[key] = b
        self.maprank_win, self.maprank_name = w, name
        w.show()
        return w

    def maprank_set(self, name, rank):
        from .maplib import set_rank
        set_rank([name], rank)
        from .tracker_page import TrackerPage
        TrackerPage._ov_cache = None                         # (the overlay shows it at once)
        self.maprank_close()
        self._say(f"{name}: ranked {rank}.", 4)
        try:
            self.tracker_overlay_draw(self.tracker_numbers())
        except Exception:
            buglog.caught()

    def maprank_skip(self, name, how):
        if how == "optout":                                  # 2.98.5: no more rank cards (Map Library brings them back)
            self.tracker_cfg()["rank_ask"] = False
            self.tracker_save()
            v = getattr(self, "ml_rank_ask", None)
            if v is not None:
                v.set(False)
            self.maprank_close()
            self._say("No more map rank cards. Turn them back on: Overlay ↳ Map Library › Ask me to rank.", 8)
            return
        if how == "never":
            from .config import SETTINGS, save_json
            SETTINGS.setdefault("rank_never", [])
            if name not in SETTINGS["rank_never"]:
                SETTINGS["rank_never"].append(name)
            save_json("settings.json", SETTINGS)
        self.maprank_close()

    def maprank_close(self):
        w, self.maprank_win = getattr(self, "maprank_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    # ================================================================ the goal bar
    def goalbar_rows(self):
        """What the goal bar holds, top to bottom: 'campaign' (2.77.0, while you're in the campaign), 'focus'."""
        rows = []
        try:
            if self.camp_on_bar() and not self.camp_in_card():     # (the Panel: the line is in its card)
                rows.append("campaign")
        except Exception:
            self.log_error("the campaign line")
        if self.focus_line()[0]:
            rows.append("focus")
        return rows

    def goalbar_wanted(self):
        return bool(self.goalbar_rows())

    def goalbar_destroy(self, keep_place=True, flush=True):
        """The lines come off the overlay's window; keep_place: the window shrinks back down to its bar (the bar
        itself never moves)."""
        cv, self.gb_cv = getattr(self, "gb_cv", None), None
        h, self._gb_h = getattr(self, "_gb_h", 0), 0
        main = getattr(self, "mg_win", None)
        lw, self.gb_win = getattr(self, "gb_win", None), None
        if lw is not None:                                  # (the lines' own window: the bar never grew for it)
            try:
                lw.destroy()
            except tk.TclError:
                pass
            return
        if cv is None:
            if main is not None:
                self._gb_strays(main)
            return
        geo = self._gb_geo(main, flush) if keep_place and main is not None else None
        try:
            cv.destroy()
        except tk.TclError:
            pass
        if geo and h:
            self._gb_place(main, geo, -h, getattr(self, "_gb_below", False))
            self._gb_fit_later(main)

    ENDS_CLEAR = 0.18                  # the share of the bar's width kept clear at each end, over the game's XP bar

    def _gb_inset(self, main, W):
        """-> px kept clear at each end of the lines over the game's XP bar (0: full width, on the bar's window).
        Round 18: the lines then go in their own window (overlaywin.LinesWindow) as wide as they are - nothing round
        them is see-through, so there is never a color-key (black) box."""
        if not hasattr(main, "companions"):
            return 0
        inset = int(W * self.ENDS_CLEAR)
        if W - 2 * inset < 360:                             # (a narrow bar: the line keeps at least 360 px)
            inset = max(0, (W - 360) // 2)
        return max(0, inset)

    @staticmethod
    def _gb_strays(main):
        """Any set of lines still on the window that isn't the one in use comes off (never two at once)."""
        try:
            for c in main.body.winfo_children():
                if getattr(c, "_goalbar", False):
                    c.destroy()
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def _gb_geo(main, flush=True):
        """(w, h, x, y) of the window before the lines go on or come off. flush=False (2.133.1): called once idle,
        the sizes are already worked out - no forced layout flush."""
        try:
            if flush:
                main.update_idletasks()
            x, y = main.winfo_x(), main.winfo_y()
            if not flush:                                # (where the window was put - winfo_x can lag behind it)
                import re
                m = re.match(r"\d+x\d+([+-]-?\d+)([+-]-?\d+)$", main.geometry())
                if m:
                    x, y = int(m.group(1).lstrip("+")), int(m.group(2).lstrip("+"))
            g = (main.winfo_width(), main.winfo_height(), x, y)
            return g if g[0] > 1 else (main.winfo_reqwidth(), main.winfo_reqheight(), g[2], g[3])
        except tk.TclError:
            return None

    @staticmethod
    def _gb_place(main, geo, dh, below=False):
        """The window dh px taller (the lines added on top) or shorter than it was - its bottom stays put.
        2.130.1: below - the lines sit under the bar (the Bar at the top of the screen): its top stays put."""
        if not geo:
            return
        ww, hh, x, y = geo
        try:
            main.geometry(f"{ww}x{max(1, hh + dh)}+{x}+{y if below else y - dh}")
        except tk.TclError:
            pass

    def goalbar_build(self, settled=False):
        """One build at a time. UI overhaul (feedback: the Campaign helper showed doubled lines): a build flushes
        layout (update_idletasks), which runs waiting idle jobs - one of them was another goal bar build, so two
        sets of lines went on the window and only the last one was known (the other never came off). A build asked
        for during a build now runs once, just after it."""
        if getattr(self, "_gb_busy", False):
            self._gb_again = True
            return getattr(self, "gb_cv", None)
        self._gb_busy, self._gb_again = True, False
        try:
            cv = self._goalbar_build_now(settled)
        finally:
            self._gb_busy = False
        if self._gb_again:
            self._gb_again = False
            try:
                self.root.after_idle(lambda: self.goalbar_build(settled=True))
            except tk.TclError:
                pass
        return cv

    def _goalbar_build_now(self, settled=False):
        """2.124.0 (feedback: combine it with the bar instead of a separate bar): the Campaign
        and NOW lines are drawn at the top of the overlay's own window, as wide as it, and the window grows
        upward by their height - the bar itself never moves. (Was its own small window, docked or dragged.)
        -> the lines' canvas or None."""
        import tkinter.font as tkfont
        self.goalbar_destroy(flush=not settled)
        main = getattr(self, "mg_win", None)
        if main is None or not self.goalbar_wanted():
            self.goal_rows = []
            return None
        cfg = self.tracker_cfg()
        hud = self.merged_layout() == "xpbar"
        light = self.ov_light()
        P = getattr(self, "mg_P", None) or {}
        if "font" not in P:
            from .overlaywin import pal
            P = pal()
        try:
            mcv = next(c for c in main.body.winfo_children() if isinstance(c, tk.Canvas))
            if not settled:                              # (2.133.1: settled = run once idle, sizes known)
                main.update_idletasks()
            W = int(mcv.cget("width")) or mcv.winfo_reqwidth()
            mh = int(mcv.cget("height")) or mcv.winfo_reqheight()
        except (StopIteration, tk.TclError, ValueError, AttributeError):
            return None
        rows = self.goalbar_rows()
        k = getattr(self, "_hud_k", 1.0)
        if light:
            side = self._u(12)
        elif hud:
            from . import hudart
            side = hudart.cap_width(mh) + 14                  # (in line with the bar's well under it)
        else:
            side = int(16 * k)                                # (in line with the Panel's cells)
        f = (P["font"], self._hf(10))
        fm = tkfont.Font(root=self.root, family=P["font"], size=self._hf(10))
        lh = fm.metrics("linespace")
        row_h = lh + max(8, int(10 * k))                      # 2.124.0 (feedback: too tall): one line and a little air
        classic = not light
        if classic and hud:                                   # 2.124.1 (feedback: the added height didn't match the bar):
            row_h = max(row_h, int(mh * 0.85))               # a line about as tall as the bar under it
        pad = int(10 * k) if classic and not hud else 0       # (the Panel's frame round the lines)
        hs = [row_h] * len(rows)
        camp_n = 1
        if "campaign" in rows:                                # 2.123.7: a narrow bar wraps the line instead of cutting it
            camp_n = self.camp_lines(P, W - 2 * side)
            hs[rows.index("campaign")] += (camp_n - 1) * lh
        H = sum(hs) + 2 * pad
        bg = P.get("bg", "#15130f")
        if light and P.get("boxless"):
            from .ovlight import KEY
            bg = KEY
        geo = self._gb_geo(main, not settled)
        self._gb_strays(main)
        # 2.130.1 (feedback: with the overlay at the top, the ritual part of the bar style ran past the edge of the
        # monitor): with the Bar placed at the top, the lines go under it, and the window grows down
        self._gb_below = bool(hud and self.ov_spot() == "top")
        # UI overhaul (feedback: the overlay blocked leveling-up information): over the game's XP bar, the lines
        # leave both ends clear - the game's + passive points / weapon set buttons (left) and its counters (right)
        # show there. Round 18: the lines go in their own window, as wide as they are (nothing see-through round
        # them - no black box); elsewhere: full width, on the bar's own window.
        inset = self._gb_inset(main, W) if hud and not self._gb_below else 0
        if inset and W - 2 * inset != W:
            W = W - 2 * inset
            if "campaign" in rows:                            # (the narrower line can take another row)
                n2 = self.camp_lines(P, W - 2 * side)
                if n2 != camp_n:
                    hs[rows.index("campaign")] += (n2 - camp_n) * lh
                    H += (n2 - camp_n) * lh
                    camp_n = n2
        if inset:                                             # Round 18: their own window, centered over the bar
            from .overlaywin import LinesWindow
            lw = self.gb_win = LinesWindow(main, bg, inset, H)
            cv = tk.Canvas(lw, bg=bg, highlightthickness=0, width=W, height=H)
            cv.pack(fill="both", expand=True)
            self._gb_window_setup(main, lw)
        else:
            cv = tk.Canvas(main.body, bg=bg, highlightthickness=0, width=W, height=H)
            if self._gb_below:
                cv.pack(side="top", fill="x", after=mcv)
            else:
                cv.pack(side="top", fill="x", before=mcv)
        cv._goalbar = True                                    # (so a stray set of lines can always be found)
        if not cfg.get("mlocked"):
            main.draggable(cv)
        lft, rgt = side, W - side
        if classic and hud:                                   # 2.124.1 (feedback: didn't match the bar): the bar's own
            from . import hudart                              # stone plate and end caps
            ends, self._hud_ends = getattr(self, "_hud_ends", None), ("amber", "amber")
            lft, rgt = self._hud_frame(cv, P, W, H, cap=hudart.cap_width(mh))
            self._hud_ends = ends or ("crimson", "sapphire")
        elif classic:                                         # the Panel's stone and frame (2.124.1: as the Bar)
            from . import hudart
            art = hudart.panel(cv, W, H)
            if art is not None:
                cv.create_image(0, 0, image=art, anchor="nw", tags=("hudbg",))
                cv._card_imgs = [art]
        else:
            cv.create_line(lft, H - 1, rgt, H - 1, fill=P.get("accent") if P.get("boxless") else P.get("line", "#4a3f2c"),
                           tags=("mg",))
        mids, edges, top = [], [], pad
        for h in hs:                                          # each row's middle (2.123.7: rows can differ in height)
            mids.append(int(top + h / 2))
            top += h
            edges.append(top)
        self.goal_rows = rows                               # (2.118.0: was gb_rows - the Gear book has a method of that name)
        for e in edges[:-1]:                                  # a thin line between two lines (at the row's edge)
            cv.create_line(lft, e, rgt, e, fill=P["line"], tags=("mg",))
        if "campaign" in rows:
            self.camp_draw_row(cv, P, lft, rgt, mids[rows.index("campaign")], f, n=camp_n, lh=lh)
        if "focus" not in rows:
            return self._goalbar_show(main, cv, H, geo)
        mid = mids[rows.index("focus")]
        ftext, fprog = self.focus_line()
        cv.create_text(lft, mid, text="▸ NOW", anchor="w", fill=P["head"], font=(P["hfont"], self._hf(9), "bold"),
                       tags=("mg",))
        nx = lft + fm.measure("▸ NOW ") + 8
        pw = 0 if fprog is None else self._hf(56)
        from .campaign_ui import FitText
        ft = self._mg_text(cv, P, nx, mid, "focus", f, cls=FitText)
        ft.fnt, ft.px = fm, max(40, rgt - nx - pw - 12)     # 2.123.7: fitted by width, not a count of letters
        ft.config(text=ftext)
        self._focus_click(cv, ft)
        if fprog is not None:
            cv.create_rectangle(rgt - pw, mid - 2, rgt, mid + 2, fill=P["cell_bg"], outline=P["line"], tags=("mg",))
            cv.create_rectangle(rgt - pw, mid - 2, rgt - pw + int(pw * min(1.0, fprog)), mid + 2, fill=P["on"],
                                outline="", tags=("mg",))
        return self._goalbar_show(main, cv, H, geo)

    def _gb_window_setup(self, main, lw):
        """The lines' window takes the bar's click-through and capture setting (overlay_click_through)."""
        try:
            from .merged_page import set_click_through
            from .remnant_page import capture_affinity
            lw.click_through = bool(getattr(main, "click_through", False))
            set_click_through(lw, lw.click_through)
            capture_affinity(lw, bool(getattr(self, "_cap_hidden", False)))
        except Exception:
            buglog.caught()

    def _goalbar_show(self, main, cv, H, geo):
        lw = getattr(self, "gb_win", None)
        if lw is not None:                                    # (its own window: the bar doesn't grow or move)
            self.gb_cv, self._gb_h = cv, 0
            lw.follow()
            return cv
        self.gb_cv, self._gb_h = cv, H
        self._gb_place(main, geo, H, getattr(self, "_gb_below", False))
        self._gb_fit_later(main)
        return cv

    def _gb_fit_later(self, main):
        """UI overhaul (feedback: an empty gap under the overlay bar): growing and shrinking by the lines'
        height drifts when a size was read before the last change landed - the window kept the old height and an
        empty strip showed under the bar. Once idle, the window is set to exactly what it holds (the bar's edge
        stays where it is: the bottom, or the top when the lines are under the bar)."""
        def fit():
            try:
                if not main.winfo_exists():
                    return
                want, have = main.winfo_reqheight(), main.winfo_height()
                if want <= 1 or have <= 1 or abs(want - have) < 2:
                    return
                x, y = main.winfo_x(), main.winfo_y()
                if not getattr(self, "_gb_below", False):
                    y += have - want                            # (the bottom stays put)
                main.geometry(f"{main.winfo_width()}x{want}+{x}+{y}")
            except tk.TclError:
                pass
        try:
            main.after_idle(lambda: main.after(50, fit))
        except tk.TclError:
            pass
