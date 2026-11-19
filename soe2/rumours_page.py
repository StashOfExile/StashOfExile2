"""2.83.0: Island Rumors in the app (part of the Expedition helper, Remnant's row in Overlay › Helpers) and the
Remnant watcher's places: it watches only where remnants can be (feedback: it popped up in random areas).
  * Island Rumors: only in your hideout (Client.txt; feedback: watch only in the hideout). GGG policy (Nov 2026): on a
    Read Key press, the press's one picture is checked for the Uncharted Waters card's parchment; only then its part
    is read. Each rumor gets a tag: the island and your Map library rank.
  * Remnant: in a Grand Expedition island (Client.txt: ExpeditionLogBook_...) and maps, never in hideouts, towns and
    the campaign.
GGG ToS: it looks at your screen and draws on top - nothing is sent to the game."""
import time
import tkinter as tk

from . import buglog
from . import remnant as RM
from . import rumours as RU
from .config import save_json, SETTINGS

GRAND = "ExpeditionLogBook_"


class RumoursPage:
    # ---------------------------------------------------------------- where you are (Client.txt)
    def expedition_area(self, area_id, kind):
        """Every area change: the Remnant watcher's zone and the rumors watcher (hideout only)."""
        a = str(area_id or "")
        self.rm_zone = "grand" if a.startswith(GRAND) else kind
        self.rm_map_exp = False                   # a map: no full reward book read here yet
        self.remnant_hide()                           # a new area: no leftover tags (GGG policy: they stay until then)
        self.favours_hide()
        self.rm_kept, self.rm_lines = {}, None
        if self.rm_zone_ok() and self.remnant_cfg().get("on"):
            try:                                      # 2.129.2: prices ready before a book is read
                self.remnant_prefetch(SETTINGS.get("league", ""))
            except Exception:
                buglog.caught()
        self.ru_here = kind == "hideout"
        self.ru_hide()

    def rm_zone_ok(self):
        """The Remnant watcher looks only where remnants can be: not in a hideout, town or the campaign.
        2.98.6 (feedback: the helper stopped working): maps always - a map is "unsure" (rm_unsure) until a book with
        several rewards is read there. (Owner decision: Map Content's Expedition mark is never read.)"""
        z = getattr(self, "rm_zone", None)
        return z not in ("hideout", "town", "other")

    def rm_unsure(self):
        return getattr(self, "rm_zone", None) == "map" and not getattr(self, "rm_map_exp", False)

    # ---------------------------------------------------------------- Island Rumors
    def ru_on(self):
        c = self.remnant_cfg()
        return bool(c.get("on") and c.get("rumours", True))

    def ru_changed(self, on):
        self.remnant_cfg()["rumours"] = bool(on)
        save_json("settings.json", SETTINGS)
        if not on:
            self.ru_hide()

    def ru_look_job(self, ctx):
        """A Read Key press in your hideout with the Uncharted Waters card open: its rumors are read once and tagged.
        The tags stay until your next press or a new area."""
        from . import features as FEAT
        if not (getattr(self, "ru_here", False) and self.ru_on() and FEAT.on("overlay")) or RM.ocr_available():
            return None
        from . import screenread as SR
        rect = ctx["rect"]

        def work():
            pic = SR.capture(rect, "Island Rumors")
            if pic is None:
                return None
            img = RM.mask_own(pic, rect[:2], ("rumours",))            # (2.128.1: our card shows in it)
            if RU.find_card(img, rect[3] - rect[1]) is None:
                return [], None
            return self.ru_read(rect, img)
        work.found = lambda res: bool(res and res[0])     # (the read mark: the card's rumors read)

        def done(res):
            if res is None:
                return
            rows, edge = res                               # (read in real pixels; the panel goes in the app's)
            self.ev_ru_tags([(r, i, SR.to_ui(b)) for r, i, b in rows], SR.to_ui(edge) if edge else edge)
        return "Island Rumors", work, done

    def ru_read(self, rect, img):
        """The game window's picture -> [(rumor, island, box on screen)] (blocking: OCR), [] when no card."""
        card = RU.find_card(img, rect[3] - rect[1])
        if card is None:
            return [], None
        x0, y0, x1, y1 = card
        # 3.0.6 (reader.py): the card's 3 rows read one by one, below its banner; the whole card's read (before)
        # only when that didn't find all three - what it adds fills the rows still empty
        try:
            sure, rows = RU.read_card(img, card)
        except (RM.OcrUnavailable, RM.OcrStuck):
            raise
        except Exception:
            buglog.caught()
            sure, rows = False, []
        lines = []
        if len(rows) < 3:
            pad = int((y1 - y0) * 0.1)
            cut = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
            crop = img.crop(cut)
            k = 2 if crop.height < 700 else 1         # 2.113.1: the card's handwriting reads better at twice the size
            if k > 1:
                crop = crop.resize((crop.width * k, crop.height * k), 3)        # 3 = BICUBIC
            lines = [(t, tuple(int(v / k) + cut[i % 2] for i, v in enumerate(b))) for t, b in RM.ocr(crop)]
            sure = sure or RU.is_card(lines)
            rows = RU.merge_rows(rows, RU.rows(lines) if sure else [])
        self._ru_note(lines, rows, sure)
        self.ru_not_card = not sure
        if self.ru_not_card:                          # 2.123.5: a tan patch that isn't the card (a lit floor): nothing
            return [], None
        ox, oy = rect[0], rect[1]
        out = [(r, i, (b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy)) for r, i, b in rows]
        return out, (rect[0] + x1, rect[1] + y0, rect[0] + x1, rect[1] + y1)

    def _ru_note(self, lines, rows=None, sure=None):
        """2.113.1: what the reader saw on the last card -> rumours_read.txt in the data folder (the card's own words
        only - nothing about you; never sent). When a rumor is missed, it shows why. 3.0.6: the rows read one by
        one, then the whole card's lines when it was read too."""
        try:
            from .config import P
            if sure is None:
                sure = RU.is_card(lines)
            if rows is None:
                rows = RU.rows(lines) if sure else []
            with open(P("rumours_read.txt"), "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " - the Uncharted Waters card, as read:\n")
                for t, _b in lines:
                    hit = RU.match(t)
                    f.write(f"  {t!r}" + (f"  -> {hit[1]}" if hit else "") + "\n")
                if sure:
                    f.write("Found: " + ", ".join(i for _r, i, _b in rows) + "\n")
                else:
                    f.write("Not the card (none of its own lines were read) - nothing shown.\n")
        except Exception:
            buglog.caught()

    def ev_ru_tags(self, rows, edge):
        if not rows:
            self.ru_hide()
            self.ru_sig = None
            return
        sig = tuple(r[1] for r in rows)
        if sig == getattr(self, "ru_sig", None) and getattr(self, "ru_wins", None):
            return
        self.ru_sig = sig
        self.ru_show(rows, edge)

    def ru_show(self, rows, edge):
        """One small panel beside the Uncharted Waters card (2.113.0, feedback: too big and clunky - more like the
        rune card helper): a title, then one tight row per rumor - your Map library rank as a badge, the island,
        and the rumor in small muted text - in the card's order. A click on it closes it (owner: as the alert card -
        alertcard.click_to_close; clicks beside it go to the game); in captures (2.128.1), painted over before a read."""
        self.ru_hide()
        from . import maplib
        from .overlaywin import pal
        from .alerts_page import force_topmost
        from .alertcard import click_to_close
        from .remnant_page import no_capture
        P = pal()
        mine = maplib.ranks()
        line_h = (rows[0][2][3] - rows[0][2][1]) if rows else 20
        size = -max(10, min(int(line_h * 0.5), 15))       # (the game's text size, a touch smaller - like the tips)
        body = P.get("body") or P["font"]
        w = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        edge_col = P.get("leather") or P.get("edge") or P["line"]
        box = tk.Frame(w, bg=P["bg"], highlightthickness=max(1, int(P.get("border") or 1)),
                       highlightbackground=edge_col, padx=8, pady=4)
        box.pack()
        tk.Label(box, text="Island rumors", bg=P["bg"], fg=P["head"], font=(body, size, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=3, sticky="w")
        for i, (rumour, island, _b) in enumerate(rows, 1):
            rank = mine.get(island)
            bg, fg = RM.TIER_LOOK.get(rank, ("#2a1012", "#ff8a80") if rank == "Avoid" else (P["bg"], P["muted"]))
            tk.Label(box, text=(rank or "-") if rank != "Avoid" else "✕", bg=bg, fg=fg, font=(body, size, "bold"),
                     width=2).grid(row=i, column=0, sticky="w", pady=1)
            tk.Label(box, text=island, bg=P["bg"], fg=P["text"], font=(body, size), anchor="w").grid(
                row=i, column=1, sticky="w", padx=(8, 0))
            tk.Label(box, text=str(rumour or "").rstrip(".!"), bg=P["bg"], fg=P["muted"], font=(body, size), anchor="w").grid(
                row=i, column=2, sticky="w", padx=(8, 0))
        if any(not mine.get(i) for _r, i, _b in rows):
            tk.Label(box, text="- = not ranked yet (Map Library)", bg=P["bg"], fg=P["muted"], font=(body, size),
                     anchor="w").grid(row=len(rows) + 1, column=0, columnspan=3, sticky="w", pady=(2, 0))
        w.update_idletasks()
        x = (edge[0] if edge else max(b[2] for _r, _i, b in rows)) + 12
        y = edge[1] if edge else min(b[1] for _r, _i, b in rows)
        try:
            from .style import monitor_rect
            _ml, _mt, mr, _mb = monitor_rect(self.root, int(x), int(y))
            x = min(x, mr - w.winfo_reqwidth())
        except Exception:
            buglog.caught()
        w.geometry(f"+{int(x)}+{int(y)}")
        w.deiconify()
        try:
            click_to_close(w, self.ru_hide)
            force_topmost(w)
        except Exception:
            buglog.caught()
        # (2.128.1, feedback: shows in screenshots and streams - the watcher paints over it before reading)
        RM.OWN["rumours"] = [(int(x), int(y), int(x) + w.winfo_reqwidth(), int(y) + w.winfo_reqheight())]
        self.ru_wins = [w]

    def ru_hide(self):
        RM.OWN["rumours"] = []
        wins, self.ru_wins = getattr(self, "ru_wins", None), None
        for w in wins or ():
            try:
                w.destroy()
            except tk.TclError:
                pass
