"""2.131.0 Top Up Reminders - the read, the reminder card and the Items list (topup.py reads the pictures; an item's
picture is the app's own Currency Exchange picture - nothing is taught). Overlay › Helpers has its switch. GGG policy (Nov 2026): it reads once when you press your Read Key with
your inventory open in a hideout or town - it used to look every 1.5 s by itself.
Owner decision: Top Up and Map profit share one flow - back from a map (the game's log says so), one card asks you to
open your inventory and press the Read Key (back_card). That one press is Map profit's count for the map and Top
Up's check, from the same picture. Nothing reads by itself; skip the card and that map has no profit entry."""
import math
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import topup as TU
from .config import SETTINGS, save_json
from .style import C, Tooltip

ROW_ICON = 40                       # the list rows' picture (px)
CARD_COLOR = "#8ec5ff"
BACK_SECS = 30                      # the Back from a map card waits this long (a click on it closes it: not now)
PC_CARD_SECS = 8                    # 2.131.5: a price check's card may cover the inventory this long


class TopUpPage:
    """Mixed into App."""

    # ---------------------------------------------------------------- on / off
    def topup_on(self):
        from . import features as FEAT
        return bool(TU.cfg().get("on")) and FEAT.on("overlay")      # (its one switch: Overlay › Helpers)

    def topup_set(self, on):
        TU.cfg()["on"] = bool(on)
        save_json("settings.json", SETTINGS)
        if on:
            if getattr(self, "br_reader", None) is None:        # (the log says when you're in a hideout / town)
                try:
                    self.breach_start()
                except Exception:
                    buglog.caught()

    def topup_looking(self):
        """2.132.0: the inventory looks run for Top Up Reminders or Map profit."""
        try:
            return self.topup_on() or self.mp_on()
        except Exception:
            return self.topup_on()

    def topup_look_job(self, ctx):
        """A Read Key press in a hideout or town (Top Up Reminders or Map profit on): is the inventory open, and if so
        what's in it - from the press's one picture."""
        if not self.topup_looking() or ctx["area"] not in ("hideout", "town"):
            return None
        from . import screenread as SR
        g = ctx["g"]
        prev = getattr(self, "tu_last", None)
        p0 = ctx.get("ptr")                                # (2.131.2: where the mouse was at the press)
        name = "Top Up" if self.topup_on() else "Map profit"

        def work():
            gx, gy, gw, gh = g
            game = (gx, gy, gw, gh)
            ban = SR.capture(TU.banner_rect(game), name)
            if ban is None:
                return None
            if not TU.is_open(ban, gh):
                return {"open": False}
            rect = TU.grid_rect(game)
            img = SR.capture(rect, name)
            if img is None:
                return None
            if prev and prev.get("open") and prev.get("thumb") == _thumb(img):
                cells = prev["cells"]                      # (nothing moved: no need to read it again)
            else:
                cells = TU.scan(img)
            return {"open": True, "cells": cells, "img": img, "rect": rect, "game": game, "thumb": _thumb(img)}
        work.found = lambda res: bool(res and res.get("open"))      # (the read mark: the inventory open)

        def done(res):
            if res is not None:
                res["p0"] = p0
            self.topup_seen(res)
        return name, work, done

    def topup_seen(self, res):
        if res is None:
            return
        was = bool((getattr(self, "tu_last", None) or {}).get("open"))
        res["t"] = time.time()
        self.tu_last = res
        if res.get("open"):
            # 2.131.5 (feedback: when the game's text box covers the currency item, Seen dropped to 0): a look
            # with the mouse over the inventory (the game's item box may cover cells) or one of the app's own
            # windows over it (a price card) doesn't count - Seen keeps the last clear look, and the reminder
            # waits for one
            res["covered"] = self._tu_covered(res) or self._tu_hidden(res)
            if not was:
                self.tu_open_reminded = False
            if not res["covered"]:
                self.tu_good = res
            else:
                good = getattr(self, "tu_good", None)
                if good is not None and good.get("cells") is not None:
                    res["cells_use"] = good["cells"]
            self.topup_paint_seen()
            self.back_card_close()                           # (the card's press: done)
            try:
                self.mp_seen(res)                            # 2.132.0: Map profit reads the same look (2.132.2: a
            except Exception:                                # covered one too - see mp_seen)
                self.log_error("Map profit")
            if not getattr(self, "tu_open_reminded", False) and self.topup_on():
                # 3.0.6 (most reads are taken with the mouse over the inventory, so the reminder never came): a
                # covered look reminds too - only about stacks it saw (a stack under the game's item box reads 0)
                if self.topup_remind(seen_only=res["covered"]) is not None or not res["covered"]:
                    self.tu_open_reminded = True

    def _tu_covered(self, res):
        """2.131.5: True when this look may not show the inventory as it is - the mouse over the inventory panel
        (the game's item box shows by it), or a price check just made (its card may be over the grid)."""
        l_, t, r, b = res["rect"]
        cs = (r - l_) / TU.COLS
        gy = (res.get("game") or (0, t, 0, 0))[1]
        try:
            from . import screenread as SR
            px, py = SR.to_screen(self.root.winfo_pointerxy())      # (the look is in real pixels)
        except tk.TclError:
            return True
        if l_ - cs <= px <= r + cs and gy <= py <= b + cs:
            return True
        keys = getattr(self, "keys", None)                   # the price check key (Ctrl+D): its card shows over
        try:                                                 # the game for a while
            if keys is not None and keys.pc_recent(PC_CARD_SECS):
                return True
        except Exception:
            buglog.caught()
        return False

    def _tu_hidden(self, res):
        """2.132.2 (feedback: the chat window covered currency and prompted a restock of everything):
        an item you had is gone, but the cells it was in still hold something this look can't name - something is
        over them (the chat box, another window). Not a clear look."""
        good = getattr(self, "tu_good", None)
        if not good or not good.get("cells") or not res.get("cells"):
            return False
        was = {}
        for c in good["cells"]:
            name = self.tu_name(c)
            if name is not None:
                was.setdefault(name, []).append(c["cell"])
        now = {c["cell"]: c for c in res["cells"]}
        have = {self.tu_name(c) for c in res["cells"]}
        for name, cells in was.items():
            if name in have:
                continue
            if any(rc in now and self.tu_name(now[rc]) is None for rc in cells):
                return True
        return False

    def tu_refs(self):
        """The pictures that name a cell (Map profit's, once built; else built here on a background thread from the
        pictures learned on this PC and poe.ninja's in the art cache - 3.1: none ship; missing ones are downloaded
        once, mp_art_fetch). None until ready."""
        try:
            self.mp_art_fetch()
        except Exception:
            buglog.caught()
        r = getattr(self, "mp_refs_v", None) or getattr(self, "tu_refs_v", None)
        if r is not None or getattr(self, "_tu_refs_busy", False):
            return r
        self._tu_refs_busy = True

        def work():
            from . import mapprofit as MP
            from .wealth import WPRICES
            return MP.build_refs(getattr(WPRICES, "parts", None))

        def done(res):
            self._tu_refs_busy = False
            if res is not None:
                self.tu_refs_v = res
        try:
            self.run_bg(work, done)
        except Exception:
            self._tu_refs_busy = False
            buglog.caught()
        return None

    def tu_name(self, c):
        """The item a cell of the inventory holds: a picture taught by an older version first, else Map profit's
        matcher (poe.ninja's pictures). None: not known. Kept on the cell once pictures are ready."""
        if "name" in c:
            return c["name"]
        name = TU.which(c["sig"], TU.learned()) if TU.learned() else None
        if name is None:
            refs = self.tu_refs()
            if refs is None:
                return None
            from . import mapprofit as MP
            got = MP.identify([c], {}, refs)[0]
            name = next(iter(got), None)
        c["name"] = name
        return name

    def tu_readable(self, name):
        """True when this item can be named by its picture (so a read can count it): taught here, or poe.ninja sends a
        picture of it (downloaded into the art cache - 3.1: no pictures ship with the app)."""
        return name in TU.learned() or self.tu_icons_local().has(name)

    def tu_icons_local(self, size=ROW_ICON):
        """Every item poe.ninja sends a picture for, by name, from the art cache (rates_view.LocalIcons) at a size."""
        from .rates_view import LocalIcons
        box = self.__dict__.setdefault("_tu_local", {})
        if size not in box:
            box[size] = LocalIcons(self.root, size=size)
        return box[size]

    def tu_display(self, size=ROW_ICON):
        """The pictures this window DRAWS: poe.ninja's currency icons from the art cache Exchange Rates fills (the
        same downloads and rules as there) - none yet: the name stands in. -> get(name) -> PhotoImage or None.
        Recognition reads cells with tu_refs() (Map Profit's matcher pictures)."""
        from .rates_view import Icons, picture_paths, url_for
        box = self.__dict__.setdefault("_tu_disp", {})
        if size not in box:
            icons = Icons(self.root, lambda: self._tu_icons_ready(), size=size)
            st = {"paths": None, "at": 0.0}

            def get(name):
                import time as _t
                if st["paths"] is None or _t.time() - st["at"] > 60:
                    st["paths"], st["at"] = picture_paths(), _t.time()
                url = url_for(name, st["paths"])
                return icons.get(url) if url else None
            box[size] = get
        return box[size]

    def _tu_icons_ready(self):
        """New poe.ninja pictures arrived: the window's rows and the picker draw again (once)."""
        win = getattr(self, "tu_items_win", None)
        try:
            if win is None or not win.winfo_exists():
                return
        except tk.TclError:
            return
        pick = getattr(self, "tu_add_pick", None)
        if pick is not None:
            try:
                pick.refresh_pictures()
            except tk.TclError:
                pass
        if not getattr(self, "_tu_repaint", False):
            self._tu_repaint = True

            def again():
                self._tu_repaint = False
                try:
                    self.topup_paint_list()
                except tk.TclError:
                    pass
            self.root.after(200, again)

    def topup_totals(self):
        last = getattr(self, "tu_last", None) or {}
        if not last.get("open"):
            return {}
        want = [it["name"] for it in TU.cfg()["items"] if self.tu_readable(it["name"])]
        return TU.totals(last.get("cells_use") or last.get("cells") or [], self.tu_name, want)

    # ---------------------------------------------------------------- the reminder
    def topup_visit(self):
        """Back from a map in a hideout or town (alerts_page.breach_area; 2.131.5: not any new area): the next
        inventory look may remind again."""
        self.tu_visit = getattr(self, "tu_visit", 0) + 1

    # ---------------------------------------------------------------- Back from a map (Top Up + Map profit, one card)
    def back_card_text(self, map_name=""):
        """-> (title, line) of the Back from a map card, or None when neither helper is on or no Read Key is set.
        Round 18 (feedback: too much text to read): the title and one short line - "Back from <map>" / "Open
        inventory, press Ctrl+Shift+R" (the key from the setting). The stash tip is on Map Profit's page line."""
        tu, mp = self.topup_on(), self.mp_on()
        key = self.look_key_label()
        if not (tu or mp) or not key:
            return None
        title = f"Back from {map_name}" if map_name else "Back from your map"
        if not mp:
            return title, f"Open inventory, press {key}"
        # 3.0.6 (after each map, encourage reading the inventory and emptying it of everything but mapping supplies)
        # - then the next map counts from an empty inventory
        return title, f"Open inventory, press {key}, then stash all but map supplies"

    def back_card(self, map_name=""):
        """Back in your hideout or a town after a map (alerts_page.breach_area): the one card. It closes when that
        press reads your open inventory, when you leave, or on a click (not now). It reads nothing itself."""
        self.topup_visit()
        got = self.back_card_text(map_name)
        if got is None:
            return None
        self.back_card_close()
        from . import alertcard
        from .alerts_page import game_rect
        self.back_win = alertcard.show(self.root, got[0], got[1], color=CARD_COLOR, mark="▲", secs=BACK_SECS,
                                       game=game_rect(), tag="Back from a map", rank=4)
        buglog.debug("Back from a map", "card shown")
        return self.back_win

    def back_card_close(self):
        w, self.back_win = getattr(self, "back_win", None), None
        if w is not None:
            try:
                if w.winfo_exists():
                    w.destroy()
            except tk.TclError:
                pass

    def topup_remind(self, force=False, seen_only=False):
        """The inventory just opened: in your hideout or a town, once a visit, a card if something's under its
        keep. force (Test): now, wherever you are (a sample if nothing is low). seen_only: a covered look - only
        stacks it saw count as low."""
        items = TU.cfg()["items"]
        lows = TU.low(self.topup_totals(), items)
        if seen_only:
            lows = [lw for lw in lows if lw[1]]
        if not force:
            if not lows or getattr(self, "br_area", None) not in ("hideout", "town"):
                return None
            if getattr(self, "tu_reminded", None) == getattr(self, "tu_visit", 0):
                return None
            self.tu_reminded = getattr(self, "tu_visit", 0)
        sub = TU.card_text(lows) if lows else ("Nothing is low" if items else "A sample - add items first")
        from . import alertcard
        from .alerts_page import game_rect
        self.tu_win = alertcard.show(self.root, "Top up before your next map", sub, color=CARD_COLOR, mark="▼",
                                     secs=10, game=game_rect(), tag="Top Up", rank=3)
        buglog.debug("Top Up", f"reminded: {len(lows)} low")
        return lows

    def topup_take_supplies(self):
        """2.131.2 (request: move League Plan's map supplies into Top Up): the supplies you listed there join your
        Top Up items (Keep 0 until you set it). Once; League Plan's list goes.
        -> the names added."""
        try:
            from . import focus as F
            names = F.supplies_out()
        except Exception:
            buglog.caught()
            return []
        items = TU.cfg()["items"]
        have = {str(it.get("name") or "").lower() for it in items}
        added = []
        for n in names:
            if n.lower() not in have:
                items.append({"name": n, "keep": 0})
                have.add(n.lower())
                added.append(n)
        if names:
            save_json("settings.json", SETTINGS)
            self.status_text, self.status_until = (f"League Plan's map supplies are in Top Up Reminders now "
                                                   f"({len(names)}) - Overlay › Helpers › Items…"), \
                time.time() + 12
            self.topup_paint_list()
        return added

    # (nav phase 2: its row is in the one Helpers table - alerts_page.build_alerts_panel)

    # ---------------------------------------------------------------- the Items list
    def topup_add_open(self):
        """+ Add more: a row to pick an item from the list (with its picture) and set how many to keep."""
        box = getattr(self, "tu_add", None)
        if box is None:
            return None
        for ch in box.winfo_children():
            ch.destroy()
        from .imagepick import ImagePick
        P2 = C["panel2"]
        tk.Label(box, text="Item", bg=P2, fg=C["text"]).pack(side="left")
        have = {it["name"].lower() for it in TU.cfg()["items"]}
        small = self.tu_icons_local(24)
        self.tu_add_var = tk.StringVar()
        pick = ImagePick(box, [n for n in small.names() if n.lower() not in have], self.tu_display(24),
                         textvariable=self.tu_add_var, width=22)
        pick.pack(side="left", padx=8)
        self.tu_add_pick = pick
        tk.Label(box, text="Keep", bg=P2, fg=C["text"]).pack(side="left")
        self.tu_add_keep = tk.StringVar(value="10")
        ttk.Spinbox(box, from_=0, to=9999, textvariable=self.tu_add_keep, width=5).pack(side="left", padx=(8, 8))
        ok = ttk.Button(box, text="Add", state="disabled", command=self.topup_add_picked)
        ok.pack(side="left")
        Tooltip(ok, "Add the item you picked to your list.")
        self.tu_add_var.trace_add("write", lambda *_a: ok.config(state="normal" if pick.exact() else "disabled"))
        pick.entry.bind("<Return>", lambda _e: self.topup_add_picked() if pick.pop is None else None, add="+")
        pick.entry.focus_set()
        return box

    def topup_add_picked(self):
        pick = getattr(self, "tu_add_pick", None)
        name = pick.exact() if pick is not None else None
        if name:
            return self.topup_add(name, self.tu_add_keep.get())
        return False

    def topup_add(self, name, keep):
        """Add one item by name -> True (already there: its Keep changes)."""
        name = str(name or "").strip()
        if not name:
            return False
        try:
            k = max(0, int(str(keep).strip() or 0))
        except ValueError:
            k = 0
        items = TU.cfg()["items"]
        old = next((it for it in items if it["name"].lower() == name.lower()), None)
        if old is not None:
            old["keep"] = k
        else:
            items.append({"name": name, "keep": k})
        save_json("settings.json", SETTINGS)
        self.topup_paint_list()
        self.topup_below_paint()
        if getattr(self, "tu_add", None) is not None and self.tu_add.winfo_children():
            self.topup_add_open()                        # (the picked item leaves the list; the field is clear)
        return True

    def topup_below_set(self, text):
        for b in TU.BELOW_STEPS:
            if TU.below_text(b) == text:
                TU.cfg()["below"] = b
                save_json("settings.json", SETTINGS)
        self.topup_below_paint()
        self.topup_paint_list()

    def topup_below_paint(self):
        """The ⓘ beside Remind me: how the number is worked out, with Keep 20."""
        tip = getattr(self, "tu_below_tip", None)
        if tip is None:
            return
        b = TU.cfg().get("below", 0.3)
        most = math.ceil(round(TU.remind_at(20, b), 6)) - 1
        how = f"keep 20 at {TU.below_text(b)} below" if b else "keep 20"
        tip.text = (f"A reminder card shows when you have fewer than this - for example, {how}: the card shows at "
                    f"{most} or fewer.")

    def topup_items(self):
        old = getattr(self, "tu_items_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                return old
        except tk.TclError:
            pass
        P2 = C["panel2"]
        w = tk.Toplevel(self.root, bg=C["accent"], padx=1, pady=1)
        w.title("Top Up Reminders")
        try:
            w.transient(self.root)
        except tk.TclError:
            pass
        w.bind("<Escape>", lambda _e: w.destroy())
        self.tu_items_win = w
        inner = tk.Frame(w, bg=P2, padx=16, pady=12)
        inner.pack(fill="both", expand=True)
        top = tk.Frame(inner, bg=P2)
        top.pack(fill="x")
        tk.Label(top, text="Your items", bg=P2, fg=C["text"], font=("Segoe UI", 12, "bold")).pack(side="left")
        tip = tk.Label(top, text="ⓘ", bg=P2, fg=C["muted"], cursor="question_arrow")
        tip.pack(side="left", padx=8)
        Tooltip(tip, f"In your hideout or a town, open your inventory and press {self.look_key_text()}. If you "
                     "have fewer of an item than you keep, one card tells you. In inventory is how many your "
                     "inventory held at that read, all stacks added up.")
        tk.Label(inner, text="Keep at least this many of each in your inventory.", bg=P2, fg=C["muted"],
                 anchor="w").pack(fill="x", pady=(2, 8))
        # 2.131.2: the share below Keep a reminder waits for, like the price checks' "10% below"
        rw = tk.Frame(inner, bg=P2)
        rw.pack(fill="x", pady=(0, 8))
        tk.Label(rw, text="Remind me when I'm", bg=P2, fg=C["text"]).pack(side="left")
        self.tu_below_var = tk.StringVar(value=TU.below_text(TU.cfg().get("below", 0.3)))
        bcb = ttk.Combobox(rw, textvariable=self.tu_below_var, state="readonly", width=10,
                           values=[TU.below_text(b) for b in TU.BELOW_STEPS])
        bcb.pack(side="left", padx=8)
        bcb.bind("<<ComboboxSelected>>", lambda _e: self.topup_below_set(self.tu_below_var.get()))
        tk.Label(rw, text="below what I keep", bg=P2, fg=C["text"]).pack(side="left")
        btip = tk.Label(rw, text="ⓘ", bg=P2, fg=C["muted"], cursor="question_arrow")
        btip.pack(side="left", padx=8)
        self.tu_below_tip = Tooltip(btip, "")
        self.topup_below_paint()
        self.tu_list = tk.Frame(inner, bg=P2)
        self.tu_list.pack(fill="both", expand=True)
        self.tu_add = tk.Frame(inner, bg=P2)
        self.tu_add.pack(fill="x", pady=(8, 0))
        foot = tk.Frame(inner, bg=P2)
        foot.pack(fill="x", pady=(8, 0))
        ttk.Button(foot, text="Done", style="Primary.TButton", command=w.destroy).pack(side="right")
        ab = ttk.Button(foot, text="+ Add more", command=self.topup_add_open)
        ab.pack(side="left")
        Tooltip(ab, "Pick an item from the list and set how many to keep.")
        self.topup_paint_list()
        if not TU.cfg()["items"]:
            self.topup_add_open()                          # (nothing yet: the picker is already open)
        try:
            from .style import center_over
            center_over(w, self.root)
        except Exception:
            buglog.caught()
        return w

    def topup_paint_list(self):
        box = getattr(self, "tu_list", None)
        try:
            if box is None or not box.winfo_exists():
                return
        except tk.TclError:
            return
        for ch in box.winfo_children():
            ch.destroy()
        P2 = C["panel2"]
        items = TU.cfg()["items"]
        self.tu_keep_vars, self.tu_seen_labels, self.tu_icons = {}, {}, []
        if not items:
            tk.Label(box, text="No items yet. Pick one below and set how many to keep.", bg=P2, fg=C["text"],
                     wraplength=420, justify="left", anchor="w").pack(fill="x")
            return
        head = tk.Frame(box, bg=P2)
        head.pack(fill="x")
        for txt, wd in (("", 5), ("Item", 26), ("Keep", 8), ("In inventory", 12), ("", 3)):
            h = tk.Label(head, text=txt, bg=P2, fg=C["muted"], font=("Segoe UI", 9, "bold"), width=wd, anchor="w")
            h.pack(side="left")
            if txt == "In inventory":
                Tooltip(h, "How many your inventory held at your last read, all stacks added up.")
        tot = self.topup_totals()
        local = self.tu_display()
        self.tu_seen_tips = {}
        for it in items:
            name = it["name"]
            r = tk.Frame(box, bg=P2)
            r.pack(fill="x", pady=2)
            img = local(name)                               # poe.ninja's icon, else a taught one
            if img is None and TU.icon_b64(name):
                try:
                    img = tk.PhotoImage(data=TU.icon_b64(name))
                except tk.TclError:
                    img = None
            if img is not None:
                self.tu_icons.append(img)
            tk.Label(r, image=img, bg=P2, width=ROW_ICON, height=ROW_ICON).pack(side="left", padx=(0, 8)) if img else \
                tk.Label(r, text="", bg=P2, width=5).pack(side="left")
            tk.Label(r, text=name, bg=P2, fg=C["text"], width=26, anchor="w").pack(side="left")
            v = tk.StringVar(value=str(it.get("keep", 1)))
            sp = ttk.Spinbox(r, from_=0, to=9999, textvariable=v, width=6,
                             command=lambda n=name, v=v: self.topup_keep(n, v.get()))
            sp.pack(side="left", padx=(0, 16))
            sp.bind("<FocusOut>", lambda _e, n=name, v=v: self.topup_keep(n, v.get()))
            sp.bind("<Return>", lambda _e, n=name, v=v: self.topup_keep(n, v.get()))
            self.tu_keep_vars[name] = v
            seen = tk.Label(r, text="", bg=P2, fg=C["text"], width=12, anchor="w")
            seen.pack(side="left")
            self.tu_seen_tips[name] = Tooltip(seen, "")
            self.tu_seen_labels[name] = seen
            self._tu_seen_paint(name, seen, tot)
            x = ttk.Button(r, text="✕", width=3, command=lambda n=name: self.topup_forget(n))
            x.pack(side="left")
            Tooltip(x, f"Remove {name}")

    def _tu_seen_paint(self, name, lab, tot):
        text, tip = self._seen(tot, name)
        lab.config(text=text)
        t = getattr(self, "tu_seen_tips", {}).get(name)
        if t is not None:
            t.text = tip

    def _seen(self, tot, name):
        """-> (the In inventory cell, its tooltip)."""
        if not self.tu_readable(name):
            return "No picture", "The app has no picture of this item, so it can't count it."
        if name not in tot:
            return "-", f"Not read yet: open your inventory and press {self.look_key_text()}."
        n, sure = tot[name]
        if sure:
            return f"{n}", f"{n} in your inventory at the last read."
        return f"{n}+", "Some stacks couldn't be read, so you may have more."

    def topup_paint_seen(self):
        labels = getattr(self, "tu_seen_labels", None) or {}
        if not labels:
            return
        tot = self.topup_totals()
        for name, lab in labels.items():
            try:
                self._tu_seen_paint(name, lab, tot)
            except tk.TclError:
                pass

    def topup_keep(self, name, value):
        try:
            n = max(0, int(str(value).strip() or 0))
        except ValueError:
            return
        for it in TU.cfg()["items"]:
            if it.get("name") == name:
                it["keep"] = n
        save_json("settings.json", SETTINGS)
        self.topup_below_paint()

    def topup_forget(self, name):
        TU.cfg()["items"] = [it for it in TU.cfg()["items"] if it.get("name") != name]
        save_json("settings.json", SETTINGS)
        TU.forget(name)
        self.topup_paint_list()


def _thumb(img):
    return img.convert("L").resize((48, 20)).tobytes()
