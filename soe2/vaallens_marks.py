"""2.141.0 Vaal Lens (BETA): the marks over the Temple Console - when a card is picked and the game lights the tiles
it can go on, 1 (best) and 2 on two of them with a callout, a dashed ✕ on every lit tile that touches a reward
room, and + where the room it wants goes (2.142.0). A see-through window over the game: clicks go to the game, left out of captures (the board under it is read
too). It only draws; nothing is sent to the game."""
import tkinter as tk

from . import buglog

KEY = "#010203"                 # the see-through color (Windows)
RED = "#ff4d3d"


class Marks:
    def __init__(self, root):
        self.root = root
        self.win = None
        self.drawn = None
        self.layered = None             # UI overhaul: the smooth drawing (vaallens_draw), Windows

    def _make(self):
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=KEY)
        try:
            w.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.cv = tk.Canvas(w, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        w.withdraw()
        self.win = w
        return w

    def shown(self):
        try:
            lw = self.layered.win if self.layered is not None else None
            if lw is not None and lw.winfo_exists() and lw.winfo_ismapped():
                return True
            return self.win is not None and self.win.winfo_exists() and self.win.winfo_ismapped()
        except tk.TclError:
            return False

    def hide(self):
        self.drawn = None
        if self.layered is not None:
            self.layered.hide()
        if self.win is not None:
            try:
                self.win.withdraw()
            except tk.TclError:
                pass

    def destroy(self):
        if self.layered is not None:
            self.layered.destroy()
            self.layered = None
        w, self.win = self.win, None
        self.drawn = None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _smooth(self, game, marks, P, icons, chain):
        """UI overhaul (feedback: janky): one smooth picture in a layered window. -> True when shown."""
        import sys
        if sys.platform != "win32":
            return False
        try:
            from . import vaallens_draw as VD
            if self.layered is None:
                self.layered = VD.Layered(self.root)
            if not self.layered.ok:
                return False
            img, xy = VD.render(game, marks, P, icons, chain)
            if img is None:
                self.layered.hide()
                return True
            if self.layered.show(img, xy):
                if self.win is not None:                    # (the old canvas window, if it was up)
                    try:
                        self.win.withdraw()
                    except tk.TclError:
                        pass
                return True
        except Exception:
            buglog.caught()
        return False

    def show(self, game, marks, P, icons=None, chain=None):
        """game: (left, top, width, height); marks: {tile: (kind, what)} - "p" (step, room): a planned room, its own
        picture and its step; "now" (step or None, room or card): where the picked card goes, framed solid; "x": a
        tile that touches a reward room. icons: {room or card name: its picture (PIL)}. P: the overlay palette.
        2.142.2 (feedback: no lines on screen - self-explanatory what goes where): no callouts, no lines - each
        room's own picture on its tile,
        with its step."""
        if not marks:
            return self.hide()
        icons = icons or {}
        key = (tuple(game), tuple(sorted((repr(t), repr(v)) for t, v in marks.items())), tuple(sorted(icons)),
               tuple(chain or ()))
        if key == self.drawn and self.shown():
            return
        if self._smooth(game, marks, P, icons, chain):         # UI overhaul: smooth, see-through (Windows)
            self.drawn = key
            return
        from . import vaallens as V
        w = self.win if self.win is not None else self._make()
        gx, gy, gw, gh = (int(v) for v in game)
        w.geometry(f"{gw}x{gh}+{gx}+{gy}")
        cv = self.cv
        cv.delete("all")
        self.photos = []
        s, left, top = V.placing(game)
        ox, oy = left - gx, top - gy
        hw, hh = 69.3 * s * 0.9, 59.4 * s * 0.9
        # (the ✕ is always red - a theme's warn color can be the accent's orange - and dashed, with a ✕: not color alone)
        accent, warn = P.get("head") or "#f0a04a", RED
        bg = P.get("bg") or "#15120f"
        fam = P.get("font") or "Segoe UI"
        big = -max(14, int(40 * s))
        small = -max(10, int(20 * s))
        side = max(16, int(hh * 1.15))
        # 2.143.0: the path to the Architect - a gold lane from your tiles through its tiles to him, like the game's
        # own paths (chain: [your tile, the path's tiles..., the Architect])
        if chain and len(chain) >= 2:
            c_ = [(ox + V.xy(*t)[0] * s, oy + V.xy(*t)[1] * s) for t in chain]
            mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            pts_ = [mid(c_[0], c_[1])] + c_[1:-1] + [mid(c_[-2], c_[-1])]
            cv.create_line(*[v for pt in pts_ for v in pt], fill=P.get("gold") or "#d9b13a",
                           width=max(4, int(14 * s)), capstyle="round", joinstyle="round")
        for t, (m, what) in marks.items():
            if m == "lbl":                                  # 3.0.6: a card's / medallion's step, at a screen point
                x, y, r = t[1] - gx, t[2] - gy, max(9, int(17 * s))
                cv.create_oval(x - r, y - r, x + r, y + r, fill=bg, outline=accent, width=2)
                cv.create_text(x, y, text=str(what), fill=accent, font=(fam, small, "bold"))
                continue
            x, y = V.xy(*t)
            x, y = ox + x * s, oy + y * s
            pts = (x, y - hh, x + hw, y, x, y + hh, x - hw, y)
            if m == "x":
                cv.create_polygon(*pts, fill="", outline=warn, width=max(2, int(4 * s)), dash=(8, 6))
                d = max(7, int(16 * s))                    # 3.0.6 (the x turned into a square): drawn as
                for a, b in ((-d, -d), (-d, d)):            # two lines - a theme's font may have no ✕ in it
                    cv.create_line(x + a, y + b, x - a, y - b, fill=warn, width=max(3, int(6 * s)), capstyle="round")
                continue
            step, room = what
            if m == "now":
                cv.create_polygon(*pts, fill="", outline=accent, width=max(3, int(7 * s)))
            else:
                cv.create_polygon(*pts, fill="", outline=accent, width=max(2, int(3 * s)), dash=(5, 4))
            # 3.0.6 (owner): no room pictures - the step's number (as on its card / medallion); an arrow / a padlock
            # for an Upgrade / Lock medallion's room (drawn: a theme's font may not have the symbol)
            if m == "do":
                u = hh * 0.42
                if step == "Upgrade":
                    cv.create_polygon(x, y - u, x + u * 0.8, y, x + u * 0.32, y, x + u * 0.32, y + u, x - u * 0.32,
                                      y + u, x - u * 0.32, y, x - u * 0.8, y, fill=accent, outline=bg)
                else:
                    bw = u * 0.85
                    cv.create_arc(x - bw * 0.62, y - u * 1.05, x + bw * 0.62, y + u * 0.25, start=0, extent=180,
                                  style="arc", outline=accent, width=max(3, int(u * 0.22)))
                    cv.create_rectangle(x - bw, y - u * 0.1, x + bw, y + u * 0.9, fill=accent, outline=accent)
                    cv.create_oval(x - u * 0.12, y + u * 0.3, x + u * 0.12, y + u * 0.54, fill=bg, outline=bg)
                cv.create_text(x, y + hh * 0.66, text=step, fill=accent, font=(fam, small, "bold"))
                continue
            if step:
                r = max(11, int(22 * s))
                cv.create_oval(x - r, y - r, x + r, y + r, fill=bg, outline=accent, width=2)
                cv.create_text(x, y, text=str(step), fill=accent, font=(fam, small, "bold"))
        self.drawn = key
        w.deiconify()
        w.update_idletasks()
        try:
            from .alerts_page import click_through
            click_through(w)            # 2.142.2 (feedback): seen in screen shares too - not left out of captures
        except Exception:
            buglog.caught()
