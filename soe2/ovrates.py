"""2.91.0: Exchange rates over the game - a small window in the overlay's own look with the rates of the currencies
you pick, in your order: how many of each per Divine Orb for cheap ones, or how many divines each is worth for dear
ones. Pick currencies, in Overlay settings or the window's empty state, opens the picker; unlocked, drag a row's ⋮⋮
grip to change the order (ovrates_pick.py). Off until
you turn it on (Overlay › On the Overlay); drag it where you like (the overlay's lock locks it too). The numbers
are the Exchange rates table the app already keeps (poe.ninja, once an hour) - nothing extra is fetched.
GGG ToS: a window on top that only shows numbers; nothing is sent to the game."""
import tkinter as tk

from . import buglog
from .config import SETTINGS, save_json

# what most players watch, in this order (poe.ninja ids); the ones the table has are shown
COMMON = ("exalted", "chaos", "annul", "vaal", "regal", "gcp", "alch", "greater-exalted-orb", "perfect-exalted-orb",
          "hinekoras-lock", "mirror")
NAMES = {"exalted": "Exalted Orb", "chaos": "Chaos Orb", "annul": "Orb of Annulment", "vaal": "Vaal Orb",
         "regal": "Regal Orb", "gcp": "Gemcutter's Prism", "alch": "Orb of Alchemy", "greater-exalted-orb":
         "Greater Exalted Orb", "perfect-exalted-orb": "Perfect Exalted Orb", "hinekoras-lock": "Hinekora's Lock",
         "mirror": "Mirror of Kalandra", "divine": "Divine Orb", "chance": "Orb of Chance",
         "transmute": "Orb of Transmutation", "aug": "Orb of Augmentation", "artificers": "Artificer's Orb",
         "jewellers": "Jeweller's Orb", "bauble": "Glassblower's Bauble", "wisdom": "Scroll of Wisdom"}


def cur_name(cid, names=None):
    """2.114.0 (P9: the Rates table showed poe.ninja's ids - "hinekoras-lock", "gcp"): a currency's name. names: the
    names poe.ninja sent with its prices, when there are any."""
    return (names or {}).get(cid) or NAMES.get(cid) or str(cid).replace("-", " ").title()


def fmt_worth(v):
    """2.114.0: a worth in divines as a plain number ("0.000048", never "4.762e-05")."""
    if v >= 0.001:
        return f"{v:.4g}"
    import math
    places = min(10, 1 - int(math.floor(math.log10(v))))       # two significant digits
    return f"{v:.{places}f}"
REFRESH_MS = 60 * 1000


SHORT = {"divine": "div", "exalted": "ex", "chaos": "chaos"}


def rate_text(v, base=1.0, unit="div"):
    """A worth in divines -> the overlay's words in the currency you show rates in (base: its worth in divines):
    cheap items "N : 1 div", dear ones "N div each"."""
    if not v or v <= 0 or not base or base <= 0:
        return "no rate yet"
    v = v / base
    if v < 1:
        per = 1 / v
        return f"{per:,.0f} : 1 {unit}" if per >= 10 else f"{per:.2f} : 1 {unit}"
    return f"{v:,.0f} {unit} each" if v >= 10 else f"{v:.2f} {unit} each"


def rate_rows(table, ids, names=None, against="divine"):
    """The picked currencies, in your order, in the currency you show rates in -> [(id, name, text)]."""
    base = 1.0 if against == "divine" else table.get(against)
    unit = SHORT.get(against) or cur_name(against, names)
    return [(cid, cur_name(cid, names), rate_text(table.get(cid), base, unit)) for cid in ids]


class OverlayRates:
    """Mixed into App."""

    def ovr_cfg(self):
        c = SETTINGS.setdefault("rates_ov", {})
        c.setdefault("on", False)                 # off until you turn it on
        c.setdefault("shown", bool(c["on"]))      # 2.104.1: Rates ▾ on the bar opens / closes it
        c.setdefault("x", None)
        c.setdefault("y", None)
        from .ovrates_pick import picked
        picked(c)                                 # the currencies you picked, in order; the old list until you pick
        return c

    def ovr_pick(self):
        """Pick currencies: the picker window, or the open one in front."""
        from .ovrates_pick import RatesPicker
        p = getattr(self, "ovr_picker", None)
        try:
            if p is not None and p.win.winfo_exists():
                p.win.deiconify()
                p.win.lift()
                return p
        except tk.TclError:
            pass
        self.ovr_picker = RatesPicker(self)
        return self.ovr_picker

    def ovr_refresh(self):
        """New picks or a new order: the overlay window draws its rows again, if it's open."""
        job, self._ovr_job = getattr(self, "_ovr_job", None), None
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                buglog.caught()
        self.ovr_fill()

    def ovr_switch(self, on):
        """2.104.1 (feedback: it didn't work like Notes / Calc / Regex): the switch puts Rates ▾ on the bar; the
        button opens / closes the window."""
        c = self.ovr_cfg()
        c["on"] = bool(on)
        if not on:
            c["shown"] = False
        save_json("settings.json", SETTINGS)
        if not on:
            self.ovr_close()
        self._ovr_bar()
        self.ovr_first_pick()

    def ovr_first_pick(self):
        """The first time Rates is on the overlay, the picker opens by itself, once - for installs from before it
        existed too."""
        from .ovrates_pick import first_use_due, mark_first_use
        if first_use_due(self.ovr_cfg()):
            mark_first_use(self.ovr_cfg())
            try:
                self.root.after(600, self.ovr_pick)
            except Exception:
                buglog.caught()

    def ovr_shown(self):
        return getattr(self, "ovr_win", None) is not None

    def ovr_toggle(self, show=None):
        show = (not self.ovr_shown()) if show is None else bool(show)
        c = self.ovr_cfg()
        c["shown"] = bool(show and c["on"])
        save_json("settings.json", SETTINGS)
        if c["shown"] and self.ov_enabled():
            self.ovr_build()
        else:
            self.ovr_close()
        self._ovr_bar()
        return c["shown"]

    def _ovr_bar(self):
        if getattr(self, "mg_win", None) is not None:
            try:
                self.merged_build()                      # (Rates ▾ / ▴ on the bar)
            except Exception:
                buglog.caught()

    def ovr_restore(self):
        if self.ovr_cfg()["on"] and self.ovr_cfg()["shown"] and self.ov_enabled():   # 2.92.2: not while disabled
            try:
                self.ovr_build()
            except Exception:
                self.log_error("showing the exchange rates over the game")
        self.ovr_first_pick()

    def ovr_close(self):
        job, self._ovr_job = getattr(self, "_ovr_job", None), None
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                buglog.caught()
        w, self.ovr_win = getattr(self, "ovr_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _ovr_spot(self):
        c = self.ovr_cfg()
        if c["x"] is not None and c["y"] is not None:
            return int(c["x"]), int(c["y"])
        from .alerts_page import game_rect                # first time: top right of the game, under its own icons
        r = game_rect() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        return r[0] + int(r[2] * 0.80), r[1] + int(r[3] * 0.18)

    def ovr_palette(self):
        """The overlay's own look: the Bar's colors over the Bar layout, the Panel's card colors otherwise."""
        from .overlaywin import pal
        return pal()                                     # 2.109.0: the overlay's chosen style

    def ovr_build(self):
        from .overlaywin import OverlayWindow
        self.ovr_close()
        P = self.ovr_palette()
        locked = bool(self.tracker_cfg().get("mlocked"))

        def moved(x, y, _w, _h):
            self.ovr_cfg().update(x=int(x), y=int(y))
            save_json("settings.json", SETTINGS)
        x, y = self._ovr_spot()
        w = OverlayWindow(self.root, "Exchange Rates", "⇄", (x, y, None, None), palette=P, locked=locked,
                          on_lock=self.overlay_lock, on_close=lambda: self.ovr_toggle(False), on_moved=moved,
                          follow_game=True, resizable=False, no_activate=True)
        w.withdraw()
        body = tk.Frame(w.body, bg=P["bg"], padx=8, pady=8)
        body.pack(fill="both", expand=True)
        self.ovr_body, self.ovr_P, self.ovr_win = body, P, w
        self.ovr_fill()
        w.show()
        return w

    def _ovr_reorder(self, ids):
        """The overlay's rows packed again in your new order; the same widgets."""
        rowmap = getattr(self, "_ovr_rowmap", {})
        cells = self._ovr_cells
        age_lab = cells[1]
        for row, _a, _b in rowmap.values():
            row.pack_forget()
        if age_lab is not None:
            age_lab.pack_forget()
        for cid in ids:
            rowmap[cid][0].pack(fill="x")
        if age_lab is not None:
            age_lab.pack(anchor="w", pady=(4, 0))
        self._ovr_cells = ([(rowmap[c][1], rowmap[c][2]) for c in ids], age_lab)
        d = getattr(self, "ovr_drag", None)
        if d is not None:
            d.set_order(ids)

    def ovr_fill(self):
        from .ovrates_pick import GRIP, DragList, against, picked, set_picked
        from .rates import RATES
        body, P = getattr(self, "ovr_body", None), getattr(self, "ovr_P", None)
        if body is None:
            return
        ids = list(picked())
        vs = against()
        rows = rate_rows(RATES.table or {}, ids, getattr(RATES, "names", None), vs)
        age = RATES.age()
        w = getattr(self, "ovr_win", None)
        unlocked = w is not None and not w.locked
        # UI rule 22: the hourly refresh re-words the numbers in place - the rows are built again only when the
        # picks, their order or the lock change
        key = (body, tuple(ids), age is not None, unlocked, vs)
        cells = getattr(self, "_ovr_cells", None)
        built = getattr(self, "_ovr_built", None)
        try:
            alive = cells is not None and rows and all(b.winfo_exists() for _a, b in cells[0])
        except tk.TclError:
            alive = False
        same = alive and built == key
        if alive and not same and built and built[0] is body and built[2:] == key[2:] and \
                sorted(built[1]) == sorted(key[1]):
            self._ovr_reorder(ids)                        # a new order only: the rows move, nothing is made again
            cells = self._ovr_cells
            self._ovr_built = key
            same = True
        if same:
            from .inplace import set_cfg
            self.ovr_rows = [(n, t) for _c, n, t in rows]
            for (_a, b), (_c, _name, txt) in zip(cells[0], rows):
                set_cfg(b, text=txt)
            if cells[1] is not None:
                set_cfg(cells[1], text=f"poe.ninja · {int(age // 60)} min ago")
            self._ovr_job = self.root.after(REFRESH_MS, self.ovr_fill)
            return
        try:
            for c in body.winfo_children():
                c.destroy()
        except tk.TclError:
            return
        self.ovr_rows = [(n, t) for _c, n, t in rows]
        font = P.get("body") or P["font"]
        pairs, age_lab, grips, drag_rows, rowmap = [], None, [], [], {}
        if not ids:                                       # the empty state: what it is, and one button
            tk.Label(body, text="No currencies picked", bg=P["bg"], fg=P["text"],
                     font=(font, self.ov_font(10))).pack(anchor="w")
            b = tk.Label(body, text="Pick currencies", bg=P.get("head", P["text"]), fg=P["bg"], padx=8, pady=4,
                         cursor="hand2", font=(font, self.ov_font(9), "bold"))
            b.pack(anchor="w", pady=(8, 0))
            b.bind("<Button-1>", lambda e: self.ovr_pick(), add="+")
        elif not RATES.table:
            tk.Label(body, text="No rates yet - they load once the league is set.", bg=P["bg"], fg=P["muted"],
                     font=(font, self.ov_font(9))).pack(anchor="w")
        else:
            for cid, name, txt in rows:
                row = tk.Frame(body, bg=P["bg"])
                row.pack(fill="x")
                if unlocked:                              # unlocked: drag a row's grip to change the order
                    g = tk.Label(row, text=GRIP, bg=P["bg"], fg=P["muted"], font=(font, self.ov_font(9)), padx=2)
                    g.pack(side="left", padx=(0, 8))
                    grips.append(g)
                    drag_rows.append((cid, row, g))
                a = tk.Label(row, text=name, bg=P["bg"], fg=P["text"], font=(font, self.ov_font(10)), anchor="w")
                a.pack(side="left", padx=(0, 12))
                b = tk.Label(row, text=txt, bg=P["bg"], fg=P.get("head", P["text"]),
                             font=(font, self.ov_font(10), "bold"), anchor="e")
                b.pack(side="right")
                pairs.append((a, b))
                rowmap[cid] = (row, a, b)
            if age is not None:
                age_lab = tk.Label(body, text=f"poe.ninja · {int(age // 60)} min ago", bg=P["bg"], fg=P["muted"],
                                   font=(font, self.ov_font(8)))
                age_lab.pack(anchor="w", pady=(4, 0))
        if drag_rows:
            def drop(new):
                set_picked(new)
                self.root.after_idle(self.ovr_refresh)
                p = getattr(self, "ovr_picker", None)
                if p is not None:
                    p.after_idle(p.paint_all)
            self.ovr_drag = DragList(body, drag_rows, drop, line=P.get("head", P["text"]))
        self._ovr_cells, self._ovr_built, self._ovr_rowmap = (pairs, age_lab), key, rowmap
        if unlocked:                                      # 2.96.1: unlocked, any spot on it drags the window -
            for c in [body] + list(body.winfo_children()):   # except a row's grip, which moves the row
                for x in [c] + list(c.winfo_children()):
                    if x not in grips:
                        w.draggable(x)
        self._ovr_job = self.root.after(REFRESH_MS, self.ovr_fill)
