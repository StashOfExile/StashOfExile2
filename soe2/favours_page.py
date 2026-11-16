"""2.128.0 Favours prices in the app (the Ritual helper's option): the read on a Read Key press (GGG policy, Nov 2026 -
it was a watcher thread), the price tags over the game, and learning a reward's picture when you price check it. The
reading itself is in favours.py. (The tribute reminder needed the window watched until it closed: it's gone.)
Switch: Overlay › Helpers › Ritual › Favours prices (on with the Ritual helper)."""
import os
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from . import buglog
from . import favours as FV
from .config import P, SETTINGS, save_json
from .pricefmt import fmt_short

LEARN_SECS = 120               # a price check this soon after the last read teaches a reward's picture
GRAB = (0.62, 0.80)            # the part of the game that is looked at (from its top-left): the window is there


def fv_log(line):
    try:
        d = P("ritual")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "favours_log.txt")
        if os.path.exists(f) and os.path.getsize(f) > 300_000:
            os.replace(f, os.path.join(d, "favours_log.old.txt"))
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {line}\n")
    except Exception:
        buglog.caught()


class FavoursPage:
    def favours_on(self):
        c = self.ritual_cfg()
        from . import features as FEAT
        return bool(c.get("on") and c.setdefault("favours", True) and FEAT.on("overlay"))

    def favours_changed(self, on):
        self.ritual_cfg()["favours"] = bool(on)
        save_json("settings.json", SETTINGS)
        if not on:
            self.favours_hide()

    # ---------------------------------------------------------------- the pictures to compare with
    def favours_refs(self, fetch=False):
        """Build them (a background thread): the Ritual tab's omens that ship with the app, and the pictures learned
        on this PC - poe.ninja's exchange items only."""
        from .wealth import WPRICES
        items = FV.ninja_items(getattr(WPRICES, "parts", None))
        self.fv_refs = FV.build_refs(items)
        self.fv_stars = FV.star_refs()
        return self.fv_refs

    # ---------------------------------------------------------------- a Read Key press (GGG policy, Nov 2026)
    def favours_look_job(self, ctx):
        """A Read Key press with the Ritual Favours window open: its rewards, read once from the press's one picture,
        get their price tags. The tags stay until your next press (the window may be closed by then - only a read
        could tell) or a new area."""
        if not self.favours_on() or ctx["area"] not in ("map", "other", None):
            return None
        try:
            ready = FV.title_template() is not None
        except Exception:
            ready = False
        if not ready:                                     # (no window title to look for: nothing to read - decided
            fv_log("favours_title.png is missing from the app")    # before any picture)
            return None
        from . import screenread as SR
        g = ctx["g"]
        gx, gy, gw, gh = g
        w, h = int(gw * GRAB[0]), int(gh * GRAB[1])

        def work():
            import cv2
            import numpy as np
            tpl = FV.title_template()
            if tpl is None:
                fv_log("favours_title.png is missing from the app")
                return None
            if getattr(self, "fv_refs", None) is None:
                try:
                    self.favours_refs()
                except Exception as e:
                    fv_log(f"pictures: {e.__class__.__name__}: {e}")
            pic = SR.capture((gx, gy, gx + w, gy + h), "Favours prices")
            if pic is None:
                return None
            img = np.ascontiguousarray(np.asarray(pic.convert("RGB"))[:, :, ::-1])     # (BGR, as the reader wants)
            win = FV.find_window(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), tpl, gh, gw)
            if win is None:
                return {"rows": []}
            grid = FV.grid_box(win)
            occ = FV.occupied(img, grid)
            refs = getattr(self, "fv_refs", None) or FV.Refs()
            rows, left, known_f, unknown_f, seen = [], [], [], [], []
            for r, c in FV.single_cells(occ):
                f = FV.cell_feats(img, grid, r, c)
                if f is None:
                    continue
                name, sc, _m = refs.best(f)
                if name:
                    rows.append({"r": r, "c": c, "name": name, "score": sc, "box": FV.cell_rect(grid, r, c)})
                    known_f.append((f, name))
                    continue
                unknown_f.append(((r, c), f))
            tw = FV.twins(known_f, unknown_f)                 # 2.130.4: a copy of a named reward
            for (r, c), f in unknown_f:
                if (r, c) in tw:
                    rows.append({"r": r, "c": c, "name": tw[(r, c)][0], "score": tw[(r, c)][1],
                                 "box": FV.cell_rect(grid, r, c), "twin": True})
                    continue
                left.append((r, c))
                top = refs.ranked(f, 2)
                if top and top[0][0] > 0.45:                  # (2.129.0: the log says how close it came)
                    seen.append(f"{r},{c}: " + " / ".join(f"{n} {s_:.2f} {k}" for s_, n, k in top))
            for name, sc, box in FV.find_belts(img, grid, occ, FV.belt_refs()):   # ★ Mageblood / Headhunter
                rows.append({"name": name, "score": sc, "box": box, "belt": True})
            for name, sc, box in FV.find_stars(img, grid, left, getattr(self, "fv_stars", None) or FV.star_refs()):
                rows.append({"name": name, "score": sc, "box": box, "belt": True})
            fv_log(f"window read: {len(occ)} cells hold items, {len(rows)} known ({len(tw)} as a copy of another) - "
                   + ", ".join(f"{x['name']} ({x['score']:.2f})" for x in rows[:16])
                   + (f"; not sure: {'; '.join(seen[:8])}" if seen else ""))
            return {"rows": rows, "last": (time.time(), g, grid, img)}
        work.found = lambda res: bool(res and "last" in res)        # (the read mark: the Favours window seen)

        def done(res):
            if res is None:
                return
            self.fv_last = res.get("last")                    # (price checking a reward teaches its picture)
            kx, ky = SR.ui_scale()                            # (read in real pixels; the tags go in the app's)
            gl, gt, gr, gb = SR.to_ui((gx, gy, gx + gw, gy + gh))
            self.ev_favours((gl, gt, gr - gl, gb - gt),
                            [dict(r, box=tuple(int(round(v * k)) for v, k in zip(r["box"], (kx, ky, kx, ky))))
                             for r in res["rows"]])
        return "Favours prices", work, done

    # ---------------------------------------------------------------- the tags
    def ev_favours(self, g, rows):
        if not rows:
            return self.favours_hide()
        from .wealth import WPRICES
        priced = []
        for row in rows:
            each = None if row.get("belt") else WPRICES.named(row["name"])     # (a belt: a ★ and its name only)
            priced.append(dict(row, each=each))
        best = max((x for x in priced if x["each"] is not None), key=lambda x: x["each"], default=None)
        self.favours_show(g, priced, best)

    def favours_show(self, g, rows, best=None):
        """One small click-through tag per known reward, at the foot of its cell, in the overlay style's colors (like
        the Expedition helper's); the most valuable one in the warm color with a ★."""
        self.favours_hide()
        from .overlaywin import pal, skinned
        P_ = pal()
        gx, gy, _gw, gh = g
        ui = max(0.7, gh / 1440.0)
        size = -max(10, int(12 * ui))
        BG, TXT, MUT = P_["bg"], P_["text"], P_["muted"]
        WARM = P_["warn"] if skinned() else "#ffd25a"
        EDGE = P_["line"] if skinned() else "#3d5582"
        wins = []
        for row in rows:
            x, y, w, h = row["box"]
            if row.get("belt"):                           # 2.129.0: Mageblood / Headhunter - worth a look, no price
                txt, fg, edge = "★ " + row["name"], WARM, WARM
            elif row["each"] is None:
                txt, fg, edge = "no price", MUT, EDGE
            else:
                txt, fg, edge = fmt_short(row["each"]), TXT, EDGE
            if row is best:
                txt, fg, edge = "★ " + txt, WARM, WARM
            t = tk.Toplevel(self.root)
            t.withdraw()
            t.overrideredirect(True)
            try:
                t.attributes("-topmost", True)
            except tk.TclError:
                pass
            bold = row is best
            f = tkfont.Font(root=t, family="Segoe UI", size=size, weight="bold" if bold else "normal")
            tk.Label(t, text=txt, fg=fg, bg=BG, font=f, padx=4, pady=0, highlightthickness=1,
                     highlightbackground=edge).pack()
            t.update_idletasks()
            tw, th = t.winfo_reqwidth(), t.winfo_reqheight()
            t.geometry(f"+{int(gx + x + (w - tw) / 2)}+{int(gy + y + h - th - 2)}")
            t.deiconify()
            try:
                from .alerts_page import click_through, force_topmost
                click_through(t)
                force_topmost(t)
            except Exception:
                buglog.caught()
            # (2.128.1, feedback: "show up on screenshots / screen share / streaming": not left out of captures)
            wins.append(t)
        self.fv_wins = wins or None

    def favours_hide(self):
        wins, self.fv_wins = getattr(self, "fv_wins", None), None
        for w in wins or ():
            try:
                w.destroy()
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- learning a reward's picture
    def favours_copy_learn(self, text):
        """2.129.3 (feedback: omens, idols and Sacred Bloom went unpriced): any copy of a reward's text (Ctrl+C or
        your price check key) while the Favours window is open teaches its picture - exchange items (priced), and the
        uniques that get a ★ (FV.STARS). -> True if learned."""
        if not getattr(self, "fv_last", None) or time.time() - self.fv_last[0] > LEARN_SECS:
            return False
        lines = [ln.strip() for ln in str(text or "").splitlines()]
        i = next((k for k, ln in enumerate(lines) if ln.startswith("Rarity:")), None)
        if i is None or i + 1 >= len(lines):
            return False
        rarity, name = lines[i][7:].strip(), lines[i + 1]
        if rarity == "Unique" and name not in FV.STARS:
            return False
        if rarity not in ("Currency", "Unique", "Gem"):
            return False
        return self.favours_learn(name)

    def favours_learn(self, name):
        """Your price check key on a reward while the Favours window is open: remember what it looks like (the cell
        under the mouse, from the last look). -> True if learned."""
        last = getattr(self, "fv_last", None)
        if not name or not last or time.time() - last[0] > LEARN_SECS:
            return False
        _t, g, grid, img = last
        try:
            from . import screenread as SR
            mx, my = SR.to_screen(self.root.winfo_pointerxy())     # (the picture is in real pixels)
        except tk.TclError:
            return False
        cs = grid[2]
        c, r = int((mx - g[0] - grid[0]) // cs), int((my - g[1] - grid[1]) // cs)
        if not (0 <= r < FV.ROWS and 0 <= c < FV.COLS):
            return False
        x, y, w, h = FV.cell_rect(grid, r, c)
        if FV.backing(img[y + 6:y + int(h * FV.TOP), x + 6:x + w - 6]) is None:
            return False
        if not FV.learn(name, FV.cell_crop(img, grid, r, c), FV.cell_inside(img, grid, r, c)):
            return False
        fv_log(f"learned the picture of {name} (cell {r},{c})")
        threading.Thread(target=lambda: self.favours_refs(fetch=False), daemon=True).start()
        return True
