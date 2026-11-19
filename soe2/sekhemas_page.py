"""Trial of the Sekhemas helper (BETA) - the legend over the game and its row in Overlay › Helpers (sekhemas.py has
the data, the map check and the log's trial status).

On a Read Key press in the trial (the game's log says "Sanctum_..."), the press's one picture of the game is looked
at (sekhemas_look_job): the trial map open -> the legend shows beside it in the empty space either side of the map
window - Afflictions on the left, Rooms and Boons on the right, each group's lines marked ✓ Take / ✕ Avoid / ! Mild.
The map closed on a press -> the legend goes (and the read mark says nothing was found). With Windows' text reader, a
tooltip under the mouse that names an affliction or a boon gets a one-line card ("Bad: ..." / "Good: ...").
Nothing reads without a press (GGG policy, Nov 2026). A click anywhere on the legend closes it (alertcard.
click_to_close - clicks beside it go to the game); Esc in the game or leaving the trial (the log) does too."""
import tkinter as tk

from . import buglog
from . import sekhemas as SK
from .alertcard import CLICK_TIP as CLOSE_WORDS
from .config import SETTINGS, save_json

CARD_SECS = 10


class SekhemasPage:
    """Mixed into App."""

    def sek_on(self):
        from . import features as FEAT
        return bool(SK.cfg().get("on")) and FEAT.on("overlay")       # (its one switch: Overlay › Helpers)

    def sek_set(self, on):
        SK.cfg()["on"] = bool(on)
        save_json("settings.json", SETTINGS)
        if not on:
            self.sek_hide()
        elif getattr(self, "br_reader", None) is None:               # (the game's log says when you're in a trial)
            try:
                self.breach_start()
            except Exception:
                buglog.caught()

    def sek_state(self):
        t = getattr(self, "sek_trial", None)
        if t is None:
            t = self.sek_trial = SK.Trial()
        return t

    def sek_status(self):
        """Its row's line in Overlay › Helpers: where you are in the trial, or what to press."""
        t = self.sek_state().text()
        if t:
            return "On - " + t
        return self.look_status(f"On - press {self.look_key_text()} on the trial map.")

    # ---------------------------------------------------------------- the game's log
    def sek_area(self, area_id):
        """Every area change: leaving the trial takes the legend and its cards away."""
        left = self.sek_state().area(area_id)
        if left or not self.sek_state().inside:
            self.sek_hide()
        if left:
            buglog.debug("Sekhemas", "left the trial")

    # ---------------------------------------------------------------- a Read Key press
    def sekhemas_look_job(self, ctx):
        """A press in the trial: is the trial map open (the frame round it) -> the legend; a tooltip under the mouse
        naming an affliction or a boon -> its card. All from the press's one picture."""
        if not self.sek_on() or not self.sek_state().inside:
            return None
        from . import screenread as SR, remnant as RM
        g, ptr = ctx["g"], ctx.get("ptr")
        gx, gy, gw, gh = g
        if getattr(self, "sek_ocr", None) is None:
            try:
                self.sek_ocr = RM.ocr_available() == ""
            except Exception:
                self.sek_ocr = False
        ocr_ok = bool(self.sek_ocr) and ptr is not None
        own = [SR.to_screen(r) for r in list(RM.OWN.get("sekhemas") or ())]     # (our own windows, real pixels)

        def work():
            pic = SR.capture((gx, gy, gx + gw, gy + gh), SK.NAME)
            if pic is None:
                return None
            skip = [(l_ - gx, t - gy, r - gx, b - gy) for l_, t, r, b in own]
            seen = SK.map_check(pic, skip)
            names = []
            if seen["open"] and ocr_ok:
                from . import hover_page as HP
                box = HP.region(ptr, g)
                if box[2] > box[0] and box[3] > box[1]:
                    cut = RM.mask_own(pic.crop((box[0] - gx, box[1] - gy, box[2] - gx, box[3] - gy)), box[:2],
                                      keys=("sekhemas",))
                    try:
                        lines = HP.read_lines(cut, gh, RM.ocr, want=lambda ls: bool(SK.hover_names(ls)))
                    except Exception:
                        lines = []
                    names = SK.hover_names(lines)
            return seen, names

        def found(res):
            """(the read mark) Something this helper could use: the trial map, or a name in the tooltip."""
            return bool(res and (res[0]["open"] or res[1]))
        work.found = found

        def done(res):
            if res is None:
                return
            seen, names = res
            buglog.debug("Sekhemas", f"trial map {'open' if seen['open'] else 'not open'} "
                                     f"({seen['parts']} of {seen['of']} frame parts)")
            if not seen["open"]:
                self.sek_hide()                       # (the map closed: the legend goes)
                return
            self.sek_show()
            for kind, e in names[:3]:
                self.sek_card(kind, e)
        return SK.NAME, work, done

    # ---------------------------------------------------------------- the legend
    def sek_shown(self):
        return bool(getattr(self, "sek_wins", None))

    def sek_test(self):
        """Overlay › Helpers › Test: the legend over the game now."""
        return self.sek_show()

    def sek_avoid_rects(self):
        """Our own windows the legend keeps off: the overlay (Bar, Panel or both Split halves) and the Drawer -
        (l, t, r, b) each."""
        out = []
        wins = [getattr(self, "mg_win", None), getattr(self, "mg_win2", None)]
        try:
            if self.drawer_shown_as_drawer() and not self.drawer_is_away():
                wins.append(self.root)
        except Exception:
            pass
        for w in wins:
            try:
                if w is not None and w.winfo_ismapped():
                    x, y = w.winfo_rootx(), w.winfo_rooty()
                    out.append((x, y, x + w.winfo_width(), y + w.winfo_height()))
            except (tk.TclError, AttributeError):
                pass
        return out

    def sek_show(self, game=None):
        """The legend beside the trial map: Afflictions on the left, Rooms and Boons on the right, tops level. ->
        its windows."""
        from .alerts_page import game_rect
        from . import newchip
        newchip.used("Trial of the Sekhemas")             # 3.0.0: its NEW chip goes (used)
        self.sek_hide(cards=False)
        if game is None:
            game = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        cols = SK.columns(game)
        avoid = self.sek_avoid_rects()
        floor = self.sek_state().text()
        panels = []
        for side in (SK.LEFT, SK.RIGHT):
            x, w = cols[side]
            foot = " · ".join(p for p in ((floor if side == SK.LEFT else ""), CLOSE_WORDS) if p)
            panels.append((x, _Panel(self.root, SK.side_groups(side), foot, w, game[3],
                                     close=lambda: self.sek_hide(cards=False))))
        top = SK.top_of(game, max(p.h for _x, p in panels))
        own = []
        for x, panel in panels:
            panel.place(x, SK.place_y(game, x, panel.w, panel.h, avoid, top=top))
            own += panel.rects()
        self.sek_wins = [p for _x, p in panels]
        from . import remnant as RM
        RM.OWN["sekhemas"] = own                          # (a later press doesn't read our own words)
        return self.sek_wins

    def sek_hide(self, cards=True):
        """The legend (and its cards) go: Esc in the game, a click on it, the map closed on a press, leaving the
        trial."""
        wins, self.sek_wins = getattr(self, "sek_wins", None), None
        for p in wins or []:
            p.destroy()
        try:
            from . import remnant as RM
            RM.OWN.pop("sekhemas", None)
        except Exception:
            buglog.caught()
        if cards:
            for r in getattr(self, "sek_cards", None) or []:
                try:
                    r.destroy()
                except Exception:
                    pass
            self.sek_cards = []

    def sek_card(self, kind, e):
        """One line on the alert card for a hovered affliction or boon: "Bad: Any Honour lost ends the run"."""
        from . import alertcard
        from .alerts_page import game_rect
        mark, word, why, vital = SK.verdict(kind, e)
        color = {"Bad": "#e05a4f", "Mild": "#e0a352", "Good": "#5fbf6a"}.get(word, "#9a9a9a")
        row = alertcard.show(self.root, f"{word}: {why}", "", color=color, mark=mark, secs=CARD_SECS,
                             game=game_rect(), tag=e["name"], rank=2 if vital else 4, vital=vital)
        self.sek_cards = [r for r in getattr(self, "sek_cards", None) or [] if r.winfo_exists()] + [row]
        return row


class _Panel:
    """One side of the legend: a dark card with a group or two (a header in the group's color, a bar of it down the
    side; under it Take / Avoid / Mild, a mark and a word, then a line each) and a footer. A click anywhere on it
    closes the legend."""

    def __init__(self, root, groups, foot, width, game_h, close):
        import tkinter.font as tkfont
        from .overlaywin import pal
        P = pal()
        self.root = root
        ui = max(0.6, game_h / 1440.0)
        self.ui = ui
        bg, rim = P.get("bg", "#15111c"), P.get("rim") or P.get("line", "#3a3048")
        text, muted = P.get("big") or P.get("text", "#ece6f5"), P.get("muted", "#b3a9c6")
        hfont, font = P.get("hfont") or "Segoe UI", P.get("font") or "Segoe UI"

        def px(n, least):
            return -max(least, int(round(n * ui)))
        self.fonts = {"head": tkfont.Font(root=root, family=hfont, size=px(23, 16), weight="bold"),
                      "sub": tkfont.Font(root=root, family=font, size=px(15, 12), weight="bold"),
                      "note": tkfont.Font(root=root, family=font, size=px(15, 12)),
                      "name": tkfont.Font(root=root, family=font, size=px(17, 13), weight="bold"),
                      "line": tkfont.Font(root=root, family=font, size=px(16, 12)),
                      "small": tkfont.Font(root=root, family=font, size=px(13, 11))}
        F = self.fonts
        pad, bar = int(16 * ui), max(3, int(4 * ui))
        self.w = int(width)
        win = self.win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.95)
        except tk.TclError:
            pass
        box = tk.Frame(win, bg=bg, highlightthickness=1, highlightbackground=rim)
        box.pack(fill="both", expand=True)
        inner = self.w - 2 - 2 * pad - bar - int(10 * ui)        # (a row's room: the card less its edges and bar)
        self.texts = []
        for i, (group, blocks) in enumerate(groups):
            accent = SK.GROUP_COLOR[group]
            g = tk.Frame(box, bg=bg)
            g.pack(fill="x", padx=pad, pady=(int(14 * ui) if i == 0 else int(18 * ui), 0))
            tk.Frame(g, bg=accent, width=bar).pack(side="left", fill="y")
            body = tk.Frame(g, bg=bg)
            body.pack(side="left", fill="x", expand=True, padx=(int(10 * ui), 0))
            tk.Label(body, text=SK.GROUP_WORD[group], bg=bg, fg=accent, font=F["head"], anchor="w", padx=0,
                     pady=0).pack(fill="x")
            tf = tk.Frame(body, bg=bg, width=inner, height=1)
            tf.pack_propagate(False)                              # (the rows' height, worked out below)
            tf.pack(fill="x")
            t = tk.Text(tf, bg=bg, fg=text, relief="flat", bd=0, highlightthickness=0, wrap="word",
                        cursor="hand2", font=F["line"], padx=0, pady=0, takefocus=0)
            gap, sub_gap = int(4 * ui), int(9 * ui)
            indent = max(F["name"].measure(m) for m in SK.MARK.values()) + int(10 * ui)   # (a mark column)
            t.tag_configure("sub", foreground=accent, font=F["sub"], spacing1=sub_gap, spacing3=int(2 * ui))
            t.tag_configure("note", foreground=muted, font=F["note"])
            t.tag_configure("mark", foreground=accent, font=F["name"])
            t.tag_configure("name", foreground=text, font=F["name"])
            t.tag_configure("line", foreground=muted, font=F["line"])
            t.tag_configure("row", lmargin1=0, lmargin2=indent, spacing1=gap)
            t.configure(tabs=(indent,))
            h, first = 0, True
            for verdict, rows in blocks:
                if not first:
                    t.insert("end", "\n")
                first = False
                head = f"{SK.MARK[verdict]}\t{SK.WORD[verdict]}"
                t.insert("end", head, ("sub",))
                note = SK.NOTE.get(verdict)
                if note:
                    t.insert("end", "  " + note, ("note", "sub"))
                h += sub_gap + int(2 * ui) + _wrapped([(SK.WORD[verdict], F["sub"]), ("  " + (note or ""), F["note"])],
                                                      inner - indent, 0) * F["sub"].metrics("linespace")
                for mark, name, why in rows:
                    t.insert("end", "\n")
                    t.insert("end", mark + "\t", ("mark", "row"))
                    t.insert("end", name, ("name", "row"))
                    t.insert("end", " – " + why, ("line", "row"))
                    ls = max(F["name"].metrics("linespace"), F["line"].metrics("linespace"))
                    h += gap + ls * _wrapped([(name, F["name"]), (" – " + why, F["line"])], inner - indent, 0)
            t.configure(state="disabled", height=1)
            tf.configure(height=h + int(2 * ui))
            t.pack(fill="both", expand=True)
            self.texts.append(t)
        tk.Frame(box, bg=rim, height=1).pack(fill="x", padx=pad, pady=(int(14 * ui), 0))
        self.foot = tk.Label(box, text=foot or "", bg=bg, fg=muted, font=F["small"], anchor="w", padx=pad,
                             wraplength=self.w - 2 * pad)
        self.foot.pack(fill="x", pady=(int(6 * ui), int(10 * ui)))
        win.update_idletasks()
        self.h = win.winfo_reqheight()
        from .alertcard import click_to_close
        click_to_close(win, close)                                # (a click anywhere on it: the legend goes)

    def place(self, x, y):
        self.x, self.y = int(x), int(y)
        self.win.geometry(f"{self.w}x{int(self.h)}+{self.x}+{self.y}")
        self.win.deiconify()
        try:
            from .alerts_page import force_topmost
            force_topmost(self.win)
        except Exception:
            buglog.caught()

    def rects(self):
        return [(self.x, self.y, self.x + self.w, self.y + int(self.h))]

    def destroy(self):
        try:
            if self.win.winfo_exists():
                self.win.destroy()
        except tk.TclError:
            pass


def _wrapped(parts, width, indent):
    """How many lines a run of (text, font) parts takes at this width (word wrap, as the Text box does it; the lines
    after the first start at `indent`)."""
    words = []
    for txt, f in parts:
        for j, w in enumerate(txt.split(" ")):
            if j:
                words.append((" ", f))
            if w:
                words.append((w, f))
    lines, x = 1, 0
    for word, f in words:
        wd = f.measure(word)
        if word != " " and x and x + wd > width:
            lines += 1
            x = indent
        x += wd
    return lines
