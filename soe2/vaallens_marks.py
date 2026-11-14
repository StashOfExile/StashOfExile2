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
            return self.win is not None and self.win.winfo_exists() and self.win.winfo_ismapped()
        except tk.TclError:
            return False

    def hide(self):
        self.drawn = None
        if self.win is not None:
            try:
                self.win.withdraw()
            except tk.TclError:
                pass

    def destroy(self):
        w, self.win = self.win, None
        self.drawn = None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def show(self, game, marks, P, icons=None):
        """game: (left, top, width, height); marks: {tile: (kind, what)} - "p" (step, room): a planned room, its own
        picture and its step; "now" (step or None, room or card): where the picked card goes, framed solid; "x": a
        tile that touches a reward room. icons: {room or card name: its picture (PIL)}. P: the overlay palette.
        2.142.2 (feedback: "I don't want the lines on screen ... I want it to be self-explanatory of what to place
        where"): no callouts, no lines - each room's own picture on its tile, with its step."""
        if not marks:
            return self.hide()
        icons = icons or {}
        key = (tuple(game), tuple(sorted((t, repr(v)) for t, v in marks.items())), tuple(sorted(icons)))
        if key == self.drawn and self.shown():
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
        for t, (m, what) in marks.items():
            x, y = V.xy(*t)
            x, y = ox + x * s, oy + y * s
            pts = (x, y - hh, x + hw, y, x, y + hh, x - hw, y)
            if m == "x":
                cv.create_polygon(*pts, fill="", outline=warn, width=max(2, int(4 * s)), dash=(8, 6))
                cv.create_text(x, y, text="✕", fill=warn, font=(fam, big, "bold"))
                continue
            step, room = what
            if m == "now":
                cv.create_polygon(*pts, fill="", outline=accent, width=max(3, int(7 * s)))
            else:
                cv.create_polygon(*pts, fill="", outline=accent, width=max(2, int(3 * s)), dash=(5, 4))
            pic = icons.get(room)
            if pic is not None:
                try:
                    from PIL import ImageTk
                    ph = ImageTk.PhotoImage(pic.convert("RGB").resize((side, side)))
                    self.photos.append(ph)
                    cv.create_image(x, y, image=ph)
                except Exception:
                    buglog.caught()
                    pic = None
            if pic is None:                                 # (no picture yet: the room's name, short)
                cv.create_text(x, y, text=str(room or "")[:12], fill=accent, font=(fam, small, "bold"),
                               width=int(hw * 1.6), justify="center")
            if step:
                r = max(9, int(17 * s))
                bx, by = x, y - hh + r * 0.4
                cv.create_oval(bx - r, by - r, bx + r, by + r, fill=bg, outline=accent, width=2)
                cv.create_text(bx, by, text=str(step), fill=accent, font=(fam, small, "bold"))
        self.drawn = key
        w.deiconify()
        w.update_idletasks()
        try:
            from .alerts_page import click_through
            click_through(w)            # 2.142.2 (feedback): seen in screen shares too - not left out of captures
        except Exception:
            buglog.caught()
