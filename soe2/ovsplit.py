"""The Split layout (owner decision): the overlay in two small halves beside the game's orbs - the middle of the
screen stays clear. Layout (Bar | Panel | Split) and Style are separate choices: every style draws both halves in its
own frame, colors, fonts and trim (the window frame comes from overlaywin, the parts from the Bar's own code).

  run half    row 1: the state chip (⌂ HIDEOUT, ● IN MAP ...) · LAST MAP / THIS MAP, the map and its time
              row 2: SESSION 14:47:43 ⓘ | LAST MAP'S PROFIT +3 div ⓘ   (the campaign: YOU ⓘ | ACT TIME ⓘ)
  tools half  row 1: Notes Calc Regex Rates (Vendor in the campaign)
              row 2: App ▸, the clock, the lock and ⚙ (Quick settings)

By default the run half sits right of the life orb (bottom left) and the tools half left of the mana orb (bottom
right); Quick settings › ⇄ Swap sides puts them the other way round (shown only while the Layout is Split - the one
place this setting lives). Each half is at most 384 x 72 px on a 1440p game (frame included) and scales with the
game's height like the rest of the overlay. Each half can be dragged while unlocked; picking Split again, or Reset
position, puts them back.

Split replaces the old "flanks" style (a saved one becomes Layout Split, Style Hairline - the same box-less look:
ovlight.RETIRED_LOOKS / retire_look).
GGG ToS: the app's own windows only; nothing here reads or touches the game."""
import tkinter as tk
from tkinter import font as tkfont

from . import buglog
from .overlaywin import CanvasText, OverlayWindow

HALF = (288, 54)               # the most a half takes, frame included, at 1080p (384 x 72 at 1440p)
# where the halves go, as parts of the game window's height: (from that side's edge, its bottom edge up from the
# game's bottom) - measured on the owner's 1440p screenshot: left x 288-678 / y 1158-1230, right x 1870-2255 / y
# 1143-1228. The orbs are anchored to the game's edges, so an ultrawide game keeps them by the orbs.
SPOTS = {"left": (0.200, 0.146), "right": (0.212, 0.147)}
RIVETS = ("hellfire",)         # skins with rivets along their top band
BAND = {"warbanner": 5, "hellfire": 5}       # a skin's top band height (u px; the rest 3)
SWAP = "⇄ Swap sides"          # (names.py: one name)
SWAP_TIP = "Swap sides: the session's half goes by the mana orb, the tools' half by the life orb"


def frame_px(P, locked=True):
    """How many px the window's frame adds on each side of its canvas (overlaywin.OverlayWindow / skin_inner)."""
    edge = max(int(P.get("border") or 0), 0 if locked else 1)
    return 1 + edge + (1 if P.get("frame2") else 0)


def place(side, ww, wh, rect, top=False):
    """A half's top-left corner on the game window rect (x, y, w, h): side "left" / "right", its size ww x wh."""
    gx, gy, gw, gh = rect
    a, bottom = SPOTS[side]
    x = gx + a * gh if side == "left" else gx + gw - a * gh - ww
    y = gy + gh * 0.012 if top else gy + gh - bottom * gh - wh
    return int(x), int(y)


class _Chain:
    """Row 1 of the run half: a small label, the map's name (cut to fit) and its time, one after the other between
    x0 and x1 - whatever each says, the three never overlap."""

    def __init__(self, cv, y, x0, x1, gap, parts):
        self.cv, self.y, self.x0, self.x1, self.gap = cv, y, x0, x1, gap
        self.parts = parts                         # {"label" | "place" | "timer": CanvasText}
        self.texts = {k: "" for k in parts}
        self.fonts = {k: tkfont.Font(root=cv, font=cv.itemcget(t.item, "font")) for k, t in parts.items()}

    def set(self, which, text):
        self.texts[which] = " ".join(str(text or "").split())
        self.layout()

    def layout(self):
        try:
            lab, pl, tm = (self.parts[k] for k in ("label", "place", "timer"))
            CanvasText.config(lab, text=self.texts["label"])
            lab.place(self.x0, self.y)
            bb = self.cv.bbox(lab.item) if self.texts["label"] else None
            x = (bb[2] + self.gap) if bb else self.x0
            tw = self.fonts["timer"].measure(self.texts["timer"]) if self.texts["timer"] else 0
            room = self.x1 - x - (tw + self.gap if tw else 0)
            t, f = self.texts["place"], self.fonts["place"]
            while len(t) > 2 and f.measure(t) > room:
                t = t[:-2].rstrip() + "…"
            CanvasText.config(pl, text=t)
            pl.place(x, self.y)
            bb = self.cv.bbox(pl.item) if t else None
            CanvasText.config(tm, text=self.texts["timer"])
            tm.place((bb[2] + self.gap) if bb else x, self.y)
        except (tk.TclError, ValueError, TypeError):
            pass


class _Link:
    """One of _Chain's parts, answering like a label (config(text=...), cget)."""

    def __init__(self, chain, which):
        self.chain, self.which = chain, which

    @property
    def item(self):
        return self.chain.parts[self.which].item

    @property
    def canvas(self):
        return self.chain.cv

    def config(self, **kw):
        if "fg" in kw:
            CanvasText.config(self.chain.parts[self.which], fg=kw["fg"])
        if "text" in kw:
            self.chain.set(self.which, kw["text"])
    configure = config

    def cget(self, key):
        return self.chain.texts[self.which] if key == "text" else self.chain.parts[self.which].cget(key)

    def winfo_exists(self):
        return self.chain.parts[self.which].winfo_exists()


class _After(CanvasText):
    """A value whose ⓘ (follow) sits right after it, cut to `width` px when set."""
    follow, gap, width, font = None, 4, None, None

    def config(self, **kw):
        if "text" in kw and self.width and self.font is not None:
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
                x0 = self.canvas.coords(self.item)[0]
                y = self.canvas.coords(self.follow.item)[1]
                self.follow.place((bb[2] if bb and kw["text"] else x0) + self.gap, y)
            except (tk.TclError, ValueError, TypeError, IndexError):
                pass
    configure = config


class SplitOverlay:
    """Mixed into App (MergedOverlay builds the Split layout here, in any style)."""

    # ---------------------------------------------------------------- settings
    def split_swapped(self):
        return bool(self.tracker_cfg().get("split_swap", False))

    def split_swap_set(self, on):
        """⇄ Swap sides (Quick settings, Split only): the run half by the mana orb, the tools by the life orb."""
        cfg = self.tracker_cfg()
        cfg["split_swap"] = bool(on)
        cfg.pop("sp_pos", None)                          # (each half goes to its new side's own place)
        self.tracker_save()
        self.merged_set()

    def split_side(self, half):
        """-> "left" / "right": where a half ("run" / "tools") goes."""
        left = "tools" if self.split_swapped() else "run"
        return "left" if half == left else "right"

    def split_palette(self, style=None):
        """The style's colors for the halves: Classic takes its Panel's (the Bar's colors on its stone), the others
        their own (ovlight.palette; a box-less one is see-through on Windows)."""
        from . import hudart
        from .ovlight import palette
        from .overlaywin import theme_palette
        style = style or self.ov_look()
        if style == "classic":
            return hudart.panel_palette(theme_palette())
        return palette(style, self.ov_look_colors())

    # ---------------------------------------------------------------- the windows
    def _sp_build(self, want):
        """The two halves, each its own small window, fitted beside the orbs (or where you dragged them)."""
        from . import themes as TH
        from .overlaywin import _seed
        from .ovlight import KEY
        from .alerts_page import game_rect
        cfg = self.tracker_cfg()
        P = self.split_palette()
        _seed(TH, P)
        self.mg_P = P
        self.hud_spots("xpbar")                              # (sizes follow the game window's height)
        self.tk_ov_lbls, self.tk_ov_alerts, self.tk_ov_clock, self.tk_ov_cv = {}, {}, None, None
        locked = bool(cfg.get("mlocked"))
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        saved = cfg.get("sp_pos") or {}
        if saved and cfg.get("sp_res") != [int(r[2]), int(r[3])]:
            saved = {}                                       # (another game size: fitted again)
        wins = {}
        for half in ("run", "tools"):
            def moved(nx, ny, _w, _h, half=half):
                cfg.setdefault("sp_pos", {})[half] = [int(nx), int(ny) + (getattr(self, "_gb_h", 0)
                                                                            if half == "run" else 0)]
                rr = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
                cfg["sp_res"] = [int(rr[2]), int(rr[3])]
                self.tracker_save()
            w = OverlayWindow(self.root, "Session", "⏱", (0, 0, None, None), opacity=int(cfg.get("opacity", 225)),
                              locked=locked, min_size=(40, 16), on_close=self.merged_close,
                              on_lock=lambda on: self.overlay_lock(on), on_moved=moved, follow_game=True,
                              no_activate=True, resizable=False, titlebar=False, palette=P)
            w.withdraw()
            if P.get("boxless"):
                try:
                    w.attributes("-transparentcolor", KEY)
                except tk.TclError:
                    pass
            cv = w.canvas_body()
            if not locked:
                w.draggable(cv)
            W, H = self.split_half(w, cv, P, want, half)
            cv.configure(width=W, height=H)
            fr = frame_px(P, locked)
            x, y = place(self.split_side(half), W + 2 * fr, H + 2 * fr, r, top=self.ov_spot() == "top")
            xy = saved.get(half)
            if isinstance(xy, (list, tuple)) and len(xy) == 2:
                x, y = int(xy[0]), int(xy[1])
            w.geometry(f"+{x}+{y}")
            wins[half] = w
        self.mg_win, self.mg_win2 = wins["run"], wins["tools"]
        self.mg_notes_host = wins["tools"]
        self.tk_overlay = self.mg_win if want["timer"] else None
        self.tk_helpers = None
        self.tracker_overlay_draw(self.tracker_numbers())
        self.tracker_helpers_paint()
        for w in wins.values():
            if getattr(self, "mg_hidden", False):
                w.hide()
            else:
                w.show()
        return self.mg_win

    def _split_preview(self, row, style, scene):
        """Overlay › Look's preview of the Split layout: both halves in `style`, at their places' sides (swapped as
        set), drawn by the code that draws them over the game. -> [canvas]"""
        from . import themes as TH
        from .overlaywin import OverlayFrame, _seed
        from .ovlight import KEY
        P = self.split_palette(style)
        if P.get("boxless"):                                 # (Windows' see-through key: the game shows there)
            P = {k: (scene if v == KEY else v) for k, v in P.items()}
        _seed(TH, P)
        self.mg_P = P
        want = {"bar": True, "timer": True, "helpers": False, "notes": False}
        out = []
        for half in ("run", "tools"):
            f = OverlayFrame(row, P)
            cv = f.canvas_body()
            W, H = self.split_half(f, cv, P, want, half)
            cv.configure(width=W, height=H)
            f.pack(side=self.split_side(half), anchor="s")
            out.append(cv)
        return out

    # ---------------------------------------------------------------- one half
    def split_half(self, w, cv, P, want, half):
        """Draw a half ("run" / "tools") in P's style on cv. -> (W, H), the canvas size (with the window's frame,
        at most HALF scaled to the game's height)."""
        k = getattr(self, "_hud_k", 1.0)
        fr = frame_px(P, getattr(w, "locked", True))
        maxw, H = int(HALF[0] * k) - 2 * fr, int(HALF[1] * k) - 2 * fr
        top, pad = self._sp_insets(P)
        r1 = top + int((H - top) * 0.30)
        r2 = top + int((H - top) * 0.74)
        if half == "run":
            W = maxw
            self._sp_run(w, cv, P, want, pad, W - pad, r1, r2)
        else:
            W = min(maxw, self._sp_tools(w, cv, P, want, pad, r1, r2) + pad)
            R = W - pad                                    # (drawn right-aligned: moved now the width is known)
            cv.move("sp_right", R, 0)
        self._sp_trim(cv, P, W, H, self.split_side(half))
        return W, H

    def _sp_style(self, P):
        return P.get("skin") or P.get("look") or "slate"

    def _sp_insets(self, P):
        """-> (top, side) px kept clear of the style's trim: its top band, the hairline's rule, Classic's stone."""
        u, st = self._u, self._sp_style(P)
        if st == "classic":
            return u(3), u(10)
        if P.get("band_grad"):
            return u(BAND.get(st, 3)) + 1, u(8)
        if st == "hairline":
            return u(4), u(6)
        return 0, u(8)

    def _sp_trim(self, cv, P, W, H, side):
        """The style's decoration on a half: Classic's stone and pewter (hudart), an ornate skin's top band (Herald
        crimson, Warbanner royal blue, Psionic deep blue under a cyan line ...) and Hellfire's rivets, the box-less
        look's thin accent rule. The frame, inner line and corner marks come from the window (overlaywin)."""
        u, st = self._u, self._sp_style(P)
        if st == "classic":
            from . import hudart
            art = hudart.panel(cv, W, H)
            if art is not None:
                cv.create_image(0, 0, image=art, anchor="nw", tags=("hudbg",))
                cv.tag_lower("hudbg")
                cv._card_imgs = [art]
            return
        grad = P.get("band_grad") or ()
        if grad:
            bh = u(BAND.get(st, 3))
            n = len(grad)
            for i, col in enumerate(grad):
                cv.create_rectangle(0, bh * i / n, W, bh * (i + 1) / n + 1, fill=col, outline="", tags=("mg", "sp_trim"))
            cv.create_line(0, bh, W, bh, fill=P.get("frame2") or P["line"], tags=("mg", "sp_trim"))
            if st in RIVETS:
                rr = max(1, u(1.5))
                for x in (u(6), W // 2, W - u(6)):
                    cv.create_oval(x - rr, bh / 2 - rr, x + rr, bh / 2 + rr, fill=P.get("corners") or P["accent"],
                                   outline=P.get("edge") or "#000000", tags=("mg", "sp_trim"))
            cv.tag_lower("sp_trim")
        elif st == "hairline":                              # the old box-less look: one thin rule from the outer end
            rl = min(W - 2 * u(6), u(150))
            if side == "left":
                self._lt_rule(cv, P, u(6), u(6) + rl, u(2), strong="l")
            else:
                self._lt_rule(cv, P, W - u(6) - rl, W - u(6), u(2), strong="r")

    def _sp_sep(self, cv, P, x, y):
        """The style's divider between two parts (as on its Bar)."""
        u, st = self._u, self._sp_style(P)
        if st == "classic":
            self._hud_sep(cv, P, x, 0, cy=y, h=u(14))
        elif st == "hairline":
            self._lt_text(cv, P, x, y, "·", 10, P["muted"], anchor="center")
        else:
            cv.create_line(x, y - u(7), x, y + u(7), fill=P["line"], tags=("mg",))

    def _sp_info(self, cv, P, x, y, tag):
        """The ⓘ after a value (its hover says how the number was worked out)."""
        t = self._lt_text(cv, P, x, y, "ⓘ", 8, P["muted"])
        cv.addtag_withtag(tag, t.item)
        return t

    def _sp_part(self, cv, P, x, y, label, key, size, fill, tag, cls=CanvasText, value_w=None, width=None, lab=8):
        """An inline part: LABEL value ⓘ, one hover (tag); the ⓘ follows the value. -> (value, the x after the ⓘ,
        with value_w kept for the value)."""
        u = self._u
        lb = self._lt_text(cv, P, x, y, label, lab, P["muted"], bold=True)
        x = cv.bbox(lb.item)[2] + u(4)
        kind = _After if cls is CanvasText else type("_After" + cls.__name__, (_After, cls), {})
        t = self._lt_text(cv, P, x, y, "", size, fill, bold=True, key=key, cls=kind)
        vw = value_w if value_w is not None else self._lt_fm(cv, P, size, True).measure("0:00:00")
        info = self._sp_info(cv, P, x, y, tag)
        t.follow, t.gap = info, u(4)
        t.width, t.font = width, cv.itemcget(t.item, "font")
        for it in (lb.item, t.item):
            cv.addtag_withtag(tag, it)
        return t, x + vw + u(4) + self._lt_fm(cv, P, 8).measure("ⓘ")

    def _sp_sizes(self, cv, P, room, parts, gap):
        """The largest (label, value) font sizes at which the parts [(label, widest value)] fit in room px, one gap
        between each. -> (label size, value size)."""
        u = self._u
        info = self._lt_fm(cv, P, 8).measure("ⓘ") + 2 * u(4)
        for lab, val in ((8, 10), (8, 9), (7, 9), (7, 8), (7, 7)):
            fl, fv = self._lt_fm(cv, P, lab, True), self._lt_fm(cv, P, val, True)
            need = sum(fl.measure(a) + fv.measure(b) + info for a, b in parts) + gap * (len(parts) - 1)
            if need <= room:
                break
        return lab, val

    def _sp_run(self, w, cv, P, want, x0, x1, r1, r2):
        """The run half: the chip and the map (row 1), SESSION and LAST MAP'S PROFIT (row 2)."""
        from .ova8 import chip_text
        u = self._u
        ln = self.ov_lines()
        if not want["timer"]:                               # no session: the chip alone - ▶ START SESSION starts one
            cw = self._a8_chip(cv, P, x0, (r1 + r2) // 2, u(18), longest=chip_text("idle"))
            self.tk_ov_lbls.pop("a8_chip").config(text=chip_text("idle"))
            self.tk_ov_cv = cv
            return x0 + cw
        cw = self._a8_chip(cv, P, x0, r1, u(16))
        x = x0 + cw + u(8)
        camp = self.ov_camp_mode()
        gap = u(14)                                         # a divider's slot
        try:
            prof = bool(self.mp_on())
        except Exception:
            prof = False
        ses = bool(ln.get("session", True))
        parts = ([("YOU", "! Lvl 99 · 9 under"), ("ACT TIME", "0:00:00")] if camp else
                 ([("SESSION", "00:00:00")] if ses else []) + ([("LAST MAP'S PROFIT", "+0.0 div")] if prof else []))
        ls, vs = self._sp_sizes(cv, P, x1 - x0, parts, gap)        # (row 2's sizes; row 1's label matches them)
        if ln.get("map", True) or ln.get("where", True) or camp:
            fl = self._lt_fm(cv, P, ls, True)
            size = 10                                       # (a wide display font: one size smaller - its body font)
            for size in (10, 9):
                fv = self._lt_fm(cv, P, size, True)
                if fl.measure("LAST MAP") + fv.measure("Vaults of Kamasa") + fv.measure("0:00") + u(12) <= x1 - x:
                    break
            lab = self._lt_text(cv, P, x, r1, "", ls, P["muted"], bold=True)
            pl = self._lt_text(cv, P, x, r1, "", size, P["big"], bold=True)
            tm = self._lt_text(cv, P, x, r1, "", size, P.get("accent") or P["big"], bold=True)
            ch = _Chain(cv, r1, x, x1, u(6), {"label": lab, "place": pl, "timer": tm})
            for key, which in (("a8_label", "label"), ("a8_place", "place"), ("a8_timer", "timer")):
                self.tk_ov_lbls[key] = _Link(ch, which)
            cv.addtag_withtag("sp_place", pl.item)       # (a name cut to fit: the whole name on hover)
            self.ov_tip(cv, "sp_place", lambda c=ch: c.texts["place"], hand=False)
        # row 2
        if camp:
            from .ova8 import _Mark
            fl, fv = self._lt_fm(cv, P, ls, True), self._lt_fm(cv, P, vs, True)
            info = self._lt_fm(cv, P, 8).measure("ⓘ") + 2 * u(4)
            act_w = fv.measure("0:00:00")
            you_w = x1 - x0 - fl.measure("YOU") - fl.measure("ACT TIME") - act_w - 2 * info - gap
            t, x = self._sp_part(cv, P, x0, r2, "YOU", "c_you", vs, P["big"], "mg_c_you", cls=_Mark, value_w=you_w,
                                 width=you_w, lab=ls)
            t.ok, t.warn = P["big"], P.get("accent") or P["head"]
            self.ov_tip(cv, "mg_c_you", self.camp_you_tip, hand=False)
            self._sp_sep(cv, P, x + gap // 2, r2)
            self._sp_part(cv, P, x + gap, r2, "ACT TIME", "c_act", vs, P["big"], "mg_c_act", value_w=act_w, lab=ls)
            self.ov_tip(cv, "mg_c_act", self.camp_act_tip, hand=False)
            self.tk_ov_cv = cv
            return x1
        x = x0
        if ses:
            from .merged_page import _Time
            vw = self._lt_fm(cv, P, vs, True).measure("00:00:00")
            t, x = self._sp_part(cv, P, x, r2, "SESSION", "session", vs, P["big"], "mg_a8ses", cls=_Time,
                                 value_w=vw, lab=ls)
            t.num, t.dim = True, (P["big"], P["muted"])
            self.ov_tip(cv, "mg_a8ses", self.a8_session_tip, hand=False)
        if prof:
            if ses:
                self._sp_sep(cv, P, x + gap // 2, r2)
                x += gap
            lw = self._lt_fm(cv, P, ls, True).measure("LAST MAP'S PROFIT") + u(4)
            room = x1 - x - lw - self._lt_fm(cv, P, 8).measure("ⓘ") - u(4)
            self._sp_part(cv, P, x, r2, "LAST MAP'S PROFIT", "profit", vs, P.get("accent") or P["big"],
                          "mg_sp_profit", value_w=room, width=room, lab=ls)
            try:
                for it in cv.find_withtag("mg_sp_profit"):
                    self.mp_bar_bind(cv, it)
            except Exception:
                buglog.caught()
        self.tk_ov_cv = cv
        return x1

    def _sp_tool(self, w, cv, P, what, x, y):
        """One tool, left-anchored at x. -> the x after it."""
        tag = "mg_notes" if what == "notes" else "mg_" + what
        if what == "notes":
            self._mg_notes_button(w, cv, P, x, y, anchor="w")
        else:
            self._mg_menu_button(cv, P, x, y, what, anchor="w")
        bb = cv.bbox(tag)
        return (bb[2] if bb else x) + self._u(12)

    def _sp_tools(self, w, cv, P, want, x0, r1, r2):
        """The tools half: Notes Calc Regex Rates (row 1), App ▸ · the clock · lock and ⚙ (row 2). The right-hand
        items are drawn from x = 0 leftwards and tagged sp_right (split_half moves them to the right edge).
        -> the content's right edge, from x0."""
        u = self._u
        cfg = self.tracker_cfg()
        tools = self.bar_buttons()
        x = x0
        for what in [t for t in tools if t != "app"]:
            x = self._sp_tool(w, cv, P, what, x, r1)
        row1 = x - u(12)
        self._lt_halo_tags(cv, P, ("mg_notes", "mg_calc", "mg_regex", "mg_rates", "mg_vendor", "mg_app"))
        x = x0
        if "app" in tools:
            x = self._sp_tool(w, cv, P, "app", x0, r2)
            self._lt_halo_tags(cv, P, ("mg_app",))
        before = set(cv.find_all())
        gx = self._lt_glyphs(w, cv, P, 0, r2)
        if want["timer"] and cfg.get("clock", True):
            gx -= self._lt_clock(cv, P, gx, r2) + u(4)
        for it in set(cv.find_all()) - before:
            cv.addtag_withtag("sp_right", it)
        right_w = -gx
        return max(row1, x + right_w)
