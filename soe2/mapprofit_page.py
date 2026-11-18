"""2.132.0 Map profit - the watcher's side (mapprofit.py has the counting and the log), the bar's profit part with
its breakdown one hover away, the Map profit window (every map, searchable) and its row in Overlay ›
Helpers. Off until you turn it on. Everything stays on your PC (map_profit.jsonl) - never sent anywhere."""
import os
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import mapprofit as MP
from .config import SETTINGS, save_json
from .style import C, SegBar, Tooltip, autowrap

REFS_SECS = 600                     # Scan stash's pictures are built again at most this often
ART_GAP = 0.5                       # 3.0.6: seconds between two of poe.ninja's pictures downloaded for Map Profit


VIEWS = ("All Time", "Daily", "Hourly")    # 2.132.6 the page's views


class MapProfitPage:
    """Mixed into App."""

    # ---------------------------------------------------------------- on / off
    def mp_on(self):
        from . import features as FEAT
        return bool(MP.cfg().get("on")) and FEAT.on("overlay")      # (its one switch: Overlay › Helpers)

    def mp_set(self, on):
        MP.cfg()["on"] = bool(on)
        save_json("settings.json", SETTINGS)
        if on:                                              # (Top Up's Read Key reads of the inventory count)
            if getattr(self, "br_reader", None) is None:    # (the game's log says when you're in a map)
                try:
                    self.breach_start()
                except Exception:
                    buglog.caught()
            self.mp_refs(force=True)
            try:
                from .wealth import WPRICES
                lg = SETTINGS.get("league") or ""
                self.run_bg(lambda: WPRICES.ensure(lg), lambda _r: None)
            except Exception:
                buglog.caught()
        try:
            self.merged_build()                             # (the overlay's profit part comes / goes)
            self.shell.features_changed()                   # (2.132.6: its page under Overlay comes / goes)
        except Exception:
            buglog.caught()

    def mp_price(self, name):
        from .wealth import WPRICES
        return WPRICES.named(name)

    def mp_refs(self, force=False):
        """Scan stash's pictures of exchange items (built on a background thread; None until then)."""
        at = getattr(self, "mp_refs_at", 0)
        if not force and (getattr(self, "mp_refs_v", None) is not None or getattr(self, "_mp_refs_busy", False)) \
                and time.time() - at < REFS_SECS:
            return getattr(self, "mp_refs_v", None)
        if getattr(self, "_mp_refs_busy", False):
            return getattr(self, "mp_refs_v", None)
        self._mp_refs_busy = True

        def work():
            from .wealth import WPRICES
            return MP.build_refs(getattr(WPRICES, "parts", None))

        def done(r):
            self._mp_refs_busy = False
            self.mp_refs_v, self.mp_refs_at = r, time.time()
            self.mp_art_fetch()
        try:
            self.run_bg(work, done)
        except Exception:
            self._mp_refs_busy = False
            buglog.caught()
        return getattr(self, "mp_refs_v", None)

    def mp_art_fetch(self):
        """3.0.6 (every item poe.ninja's exchange lists, nothing taught): poe.ninja's pictures of the exchange items
        not in the art cache yet, for Map Profit's last fallback (MP.art_match) - asked once per session, through
        Exchange Rates' downloader (rates_view.Icons: the game's image server, the app's User-Agent, one at a time
        with ART_GAP between, it stops after a few failures). Cached for good; the pictures are built again on the
        next Read Key press once some arrive. No screen read: only downloads."""
        if getattr(self, "_mp_art", None) is not None or getattr(self, "root", None) is None:
            return
        try:
            from . import favours as FV
            from .rates_view import Icons
            from .wealth import WPRICES
            urls = sorted({u for _n, p in FV.ninja_items(getattr(WPRICES, "parts", None)).values()
                           for u in [FV.art_url(p)] if u and FV.art_cache_file(u) is None})
            self._mp_art = Icons(self.root, self._mp_art_ready)
            self._mp_art.gap = ART_GAP
            for u in urls:
                self._mp_art.get(u)
        except Exception:
            buglog.caught()

    def _mp_art_ready(self):
        self.mp_refs_at = 0                 # (stale: the next Read Key press builds the pictures again)

    # ---------------------------------------------------------------- reading (from Top Up's clear looks)
    def mp_seen(self, res):
        """A look at the open inventory (topup_seen) in your hideout or a town.

        2.132.2 (feedback: account for inventory dumps when a player empties the inventory and goes back into
        the map): a map is counted visit by visit. What you came back with is the most of each item seen while
        you're home in your first looks (MP.ARRIVE_SECS from the first: stashing or selling only lowers it, and a
        covered look only hides cells - so a covered look counts here too; taking more from your stash later doesn't
        count); what you went back in with is the last clear look before the map. Each visit's loot = came back with
        - went in with, so emptying your inventory between visits isn't a loss."""
        if not self.mp_on() or getattr(self, "br_area", None) not in ("hideout", "town"):
            return None
        self.mp_restore()
        try:
            return self._mp_seen(res)
        finally:
            self.mp_save()

    def _mp_seen(self, res):
        from . import topup as TU
        refs = self.mp_refs()
        if refs is None:
            # 3.0.6 (a map showed 2 not known and +0 div): the pictures weren't built yet on the first read after the
            # app started - built now, once, so this read counts
            try:
                from .wealth import WPRICES
                refs = self.mp_refs_v = MP.build_refs(getattr(WPRICES, "parts", None))
                self.mp_refs_at = time.time()
            except Exception:
                buglog.caught()
        info = {}
        counts, unknown = MP.identify(res.get("cells") or [], TU.learned(), refs, price=self.mp_price, info=info)
        self._mp_unknown = info.get("unknown_cells") or []          # (pictures for the check window - not saved)
        buglog.debug("Map profit", "read: " + (", ".join(f"{n} {k}" for n, k in sorted(counts.items())) or "nothing")
                     + f" · {unknown} not known · {info.get('skipped', 0)} without a stack number"
                     + "".join(f" · can't tell apart: {' / '.join(v)}" for v in (info.get("alike") or {}).values()))
        ways = {k: n for k, n in counts.items() if MP.is_waystone(k)}    # 3.0.6: shown by tier, no price
        counts = dict(MP.exchange_only(counts, self.mp_price), **ways)
        # 3.0.6 (exclude the persistent Top Up supplies): what you keep in your
        # inventory for Top Up Reminders isn't loot - topping it up from your stash would count as profit
        # 3.0.6 (picked-up supplies weren't counted): only what you keep is left out - a
        # supply counts above its Top Up amount (20 Vaal Orbs kept, 22 back: +2), the same before and after
        keep = {}
        for i in TU.cfg().get("items") or []:
            try:
                k = i.get("keep")
                keep[str(i.get("name") or "").lower()] = 10 ** 9 if k is None else max(0, int(k))
            except (TypeError, ValueError):
                keep[str(i.get("name") or "").lower()] = 10 ** 9      # (no amount: all of it is a supply)
        counts = {k: n - keep.get(str(k).lower(), 0) for k, n in counts.items()
                  if n - keep.get(str(k).lower(), 0) > 0}
        snap = {"t": time.time(), "counts": counts, "unknown": unknown}
        pend = getattr(self, "mp_pending", None)
        if pend is not None:
            snap["after_map"] = True          # (the read that counts a map - you stash after it: see mp_area)
        if pend is not None:
            t0 = pend.setdefault("visit_t0", snap["t"])
            vis = pend.setdefault("visit", {})
            if snap["t"] - t0 <= MP.ARRIVE_SECS:
                for k, n in counts.items():
                    vis[k] = max(vis.get(k, 0), n)
            pend["unknown"] = max(pend.get("unknown", 0), unknown)
            self.mp_check_done()
            self.mp_paint()
            self.mp_read_card(pend)
        if not res.get("covered") or pend is not None:
            # (what you'd go into the next map with. 3.0.6: the read that counts a map is that too, covered or not -
            # the owner's reads are mostly with the mouse over the inventory, so no clear one came, and covered looks
            # from maps ago (a Scrap since stashed) were still counted as "went in with")
            self.mp_home = snap
            self.mp_home_cov = {}
        else:
            # 2.132.6 (feedback: an Omen of Answered Prayers brought from the stash was counted as profit):
            # moving an item in from the stash puts the mouse over the inventory - a covered
            # look. What a covered look sees after the last clear one counts toward what you went in with.
            cov = getattr(self, "mp_home_cov", None)
            if cov is None:
                cov = self.mp_home_cov = {}
            for k, n in counts.items():
                cov[k] = max(cov.get(k, 0), n)
        return snap

    def mp_read_card(self, pend):
        """3.0.6 (no way to tell whether the profit was counted - it needs a verification): the read back from a map
        says what it counted - its total and its items, over the game."""
        if pend is None or getattr(self, "mp_pending", None) is not pend:
            return None
        try:
            from .pricefmt import fmt_div
            e = self._mp_entry(pend)
            rows = sorted(e.get("rows") or [], key=lambda r: -(r[2] - r[1]) * r[3])
            parts = [f"{n} +{a - b}" for n, b, a, _each in rows[:4]]
            if len(rows) > 4:
                parts.append(f"+{len(rows) - 4} more")
            ways = sorted((k, n) for k, n in self._mp_gain(pend).items() if MP.is_waystone(k) and n > 0)
            if ways:                                        # 3.0.6: read and understood - no price
                parts.append("Waystones " + ", ".join((f"T{k.split()[-1].rstrip(')')}" if "Tier" in k else "?")
                                                      + f" +{n}" for k, n in ways) + " (no price)")
            if e.get("unknown"):
                parts.append(f"{e['unknown']} not known")
            title = ("≈ " if pend.get("est") else "") + f"Map counted: {MP.signed(e['div'], fmt_div)}"
            # 3.0.6 (a confirmation box for the currency and inventory items read, like Scan stash on Wealth): what
            # it read, to check and fix - not a card that goes away
            self.mp_review(pend)
            return title
        except Exception:
            buglog.caught()
            return None

    def mp_review(self, pend):
        """The check window (like Scan stash's): every item this map gave you - how many, each, worth - and the
        cells it didn't know, with their pictures. Double-click to fix a number or name a picture (it's known by
        that picture from then on); Delete drops a row. Save keeps it as this map's count; Close leaves it as read.
        It stays up (over the game, never taking the keyboard from it) until you close it; a later read on the same
        visit fills it again, unless you've changed something."""
        from tkinter import simpledialog
        from .pricefmt import fmt_div
        old = getattr(self, "mp_rev", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    if getattr(old, "mp_edited", False):
                        return old
                    old.destroy()
            except tk.TclError:
                pass
        gain = {k: n for k, n in self._mp_gain(pend).items() if n > 0}
        unknown = []                  # 3.0.6: only currency it knows is listed - no "? not known" rows to name
        par = self.root
        dlg = tk.Toplevel(par)
        dlg.title("Map Profit - check what it counted")
        dlg.configure(bg=C["panel2"], padx=16, pady=12)
        dlg.mp_edited = False
        head = tk.Label(dlg, bg=C["panel2"], fg=C["text"], anchor="w", justify="left", font=("Segoe UI", 12, "bold"))
        head.pack(fill="x")
        tk.Label(dlg, text="What this map gave you. Double-click a number to fix it. Delete drops "
                           "a row.", bg=C["panel2"], fg=C["muted"], justify="left", anchor="w",
                 wraplength=520).pack(fill="x", pady=(2, 0))
        f = tk.Frame(dlg, bg=C["panel2"])
        f.pack(fill="both", expand=True, pady=(8, 0))
        try:
            ttk.Style(dlg).configure("MPCheck.Treeview", rowheight=32)   # (room for a cell's picture)
        except tk.TclError:
            pass
        tv = ttk.Treeview(f, columns=("qty", "each", "worth"), show="tree headings", style="MPCheck.Treeview",
                          height=min(12, max(5, len(gain) + len(unknown))), selectmode="extended")
        tv.heading("#0", text="Item")
        tv.column("#0", width=300, anchor="w", stretch=True)
        for cid, title, wd in (("qty", "Got", 60), ("each", "Each", 90), ("worth", "Worth", 90)):
            tv.heading(cid, text=title)
            tv.column(cid, width=wd, anchor="e", stretch=False)
        sb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        tv.tag_configure("unknown", foreground=C.get("muted", "#9a9a9a"))
        pics, cells = [], {}

        def each_of(name):
            return None if MP.is_waystone(name) else self.mp_price(name)

        def put(iid, name, n):
            ea = each_of(name)
            tv.item(iid, text=name, values=(f"+{n:,}", "no price" if ea is None else fmt_div(ea),
                                            "-" if ea is None else fmt_div(ea * n)))

        def total():
            div, n_items = 0.0, 0
            for iid in tv.get_children():
                if iid in cells and not tv.item(iid, "text").strip("? ").strip():
                    continue
                name, q = tv.item(iid, "text"), str(tv.item(iid, "values")[0]).lstrip("+").replace(",", "")
                ea = each_of(name) if q.isdigit() else None
                if ea is not None:
                    div += ea * int(q)
                    n_items += 1
            head.config(text=("≈ " if pend.get("est") else "") + f"This map: {MP.signed(div, fmt_div)}  "
                             f"({n_items} item{'s' if n_items != 1 else ''} × poe.ninja's price)")

        for name, n in sorted(gain.items(), key=lambda kv: -((each_of(kv[0]) or 0) * kv[1])):
            put(tv.insert("", "end", text=name), name, n)
        for img, n in unknown:
            try:
                from PIL import ImageTk
                ph = ImageTk.PhotoImage(img.resize((28, 28)))
                pics.append(ph)
                iid = tv.insert("", "end", text="? not known", image=ph, values=(f"+{n or 1:,}", "", ""),
                                tags=("unknown",))
            except Exception:
                iid = tv.insert("", "end", text="? not known", values=(f"+{n or 1:,}", "", ""), tags=("unknown",))
            cells[iid] = img
        dlg.mp_pics = pics                                   # (Tk forgets a picture nobody holds)
        total()
        if (pend.get("before") or {}).get("stashed") and not pend.get("est"):
            tk.Label(dlg, text="Counted from your Top Up supplies: you stashed the rest after the last map's read.",
                     bg=C["panel2"], fg=C["muted"], justify="left", anchor="w", wraplength=520).pack(fill="x",
                                                                                                    pady=(8, 0))
        if pend.get("est"):
            tk.Label(dlg, text="≈ No read before this map: everything but your Top Up supplies counts as its loot.",
                     bg=C["panel2"], fg=C["muted"], justify="left", anchor="w", wraplength=520).pack(fill="x",
                                                                                                    pady=(8, 0))

        def edit(_e=None):
            iid = tv.focus()
            if not iid:
                return
            name = tv.item(iid, "text")
            if iid in cells and name.startswith("?"):
                nm = simpledialog.askstring("Name this item", "What is it? (its name, as the game shows it)",
                                            parent=dlg)
                if not nm or not nm.strip():
                    return
                name = nm.strip()
                tv.item(iid, tags=())
            q = str(tv.item(iid, "values")[0]).lstrip("+").replace(",", "")
            n = simpledialog.askinteger("How many", f"How many {name} did this map give you?", parent=dlg,
                                        initialvalue=int(q) if q.isdigit() else 1, minvalue=0)
            if n is None:
                return
            put(iid, name, n)
            dlg.mp_edited = True
            total()

        def drop(_e=None):
            for iid in tv.selection():
                tv.delete(iid)
            dlg.mp_edited = True
            total()

        def save():
            fix, learn = {}, {}
            for iid in tv.get_children():
                name = tv.item(iid, "text")
                q = str(tv.item(iid, "values")[0]).lstrip("+").replace(",", "")
                if name.startswith("?") or not q.isdigit() or int(q) <= 0:
                    continue
                fix[name] = fix.get(name, 0) + int(q)
                if iid in cells:
                    learn[name] = cells[iid]
            if learn:
                try:
                    import numpy as np
                    from . import favours as FV
                    FV.learn_many({n: np.asarray(im.convert("RGB"))[:, :, ::-1].copy() for n, im in learn.items()})
                    self.mp_refs_at = 0                          # (built again with them)
                except Exception:
                    buglog.caught()
            pend["fix"] = fix
            self.mp_save()
            dlg.destroy()
            self.mp_paint()

        tv.bind("<Double-1>", edit)
        tv.bind("<Delete>", drop)
        btns = tk.Frame(dlg, bg=C["panel2"])
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(side="right", padx=(0, 8))
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        try:
            dlg.attributes("-topmost", True)                 # (over the game; the keyboard stays with the game)
            from .alerts_page import game_rect
            gx, gy, gw, gh = game_rect()
            dlg.update_idletasks()
            dlg.geometry(f"+{int(gx + gw * 0.28)}+{int(gy + gh * 0.18)}")
        except Exception:
            buglog.caught()
        self.mp_rev = dlg
        return dlg

    def mp_home_base(self, stashed=False):
        """What you went into the map with: the last clear look, plus anything a later covered look saw more of.

        stashed (a new map): 3.0.6 (owner: yes - the next map counts from your Top Up supplies only - when the
        last read was the one that counted the map before - the Back card says to stash all but supplies after it):
        that read's items are taken as stashed, so a Scrap picked up again counts."""
        home = getattr(self, "mp_home", None)
        cov = getattr(self, "mp_home_cov", None) or {}
        if home is None and not cov:
            return None
        if stashed and home is not None and home.get("after_map"):
            home = dict(home, counts={}, stashed=True)
        counts = dict((home or {}).get("counts") or {})
        for k, n in cov.items():
            counts[k] = max(counts.get(k, 0), n)
        return dict(home or {"t": time.time(), "unknown": 0}, counts=counts)

    @staticmethod
    def _mp_visit_in(run):
        """Add the last visit home's loot (came back with - went in with) to the run's gain."""
        vis = run.pop("visit", None)
        run.pop("visit_t0", None)
        if vis is None:
            return
        went = run.get("seg_before") or {}
        g = run.setdefault("gain", {})
        for k in set(vis) | set(went):
            d = vis.get(k, 0) - went.get(k, 0)
            if d > 0:                                       # (2.132.2: what it gained - fewer is never a loss: it was
                g[k] = g.get(k, 0) + d                      # used, stashed or not seen - "I didn't actually lose
                #                                             anything")

    @staticmethod
    def _mp_gain(run):
        """What the map gained so far: {name: how many more} - what you saved in the check window, if you did."""
        if isinstance(run.get("fix"), dict):
            return dict(run["fix"])
        gain = dict(run.get("gain") or {})
        vis = run.get("visit")
        if vis is not None:                                 # (the visit you're on now, so far)
            went = run.get("seg_before") or {}
            for k in set(vis) | set(went):
                gain[k] = gain.get(k, 0) + max(0, vis.get(k, 0) - went.get(k, 0))
        return gain

    def _mp_entry(self, run):
        base = run["before"]["counts"]
        gain = self._mp_gain(run)
        after = {k: base.get(k, 0) + gain.get(k, 0) for k in set(base) | set(gain)}
        e = MP.entry(run["map"], run["secs"], base, after, self.mp_price,
                     unknown=max(run["before"].get("unknown", 0), run.get("unknown", 0)))
        if run.get("est"):
            e["est"] = True                                 # (no read before it: see mp_area)
        return e

    # ---------------------------------------------------------------- 3.0.6: a restart keeps the map going
    STATE_FILE = "map_profit_state.json"
    STATE_KEYS = ("mp_run", "mp_pending", "mp_home", "mp_home_cov")

    def mp_save(self):
        """(restarting the program mid-run broke the profit count for that map): the
        map you're on, the one you're between visits of, and what you went in with - kept on disk at every change."""
        try:
            from .config import save_json
            d = {k: getattr(self, k, None) for k in self.STATE_KEYS}
            d["n"], d["saved"] = getattr(self, "_mp_n", 0), time.time()
            save_json(self.STATE_FILE, d)
        except Exception:
            buglog.caught()

    def mp_restore(self):
        """Once, on the first look or area change after the app starts: what mp_save kept, if recent (MP.BEFORE_SECS)."""
        if getattr(self, "_mp_restored", False):
            return False
        self._mp_restored = True
        try:
            from .config import load_json
            d = load_json(self.STATE_FILE, {}) or {}
            if not d or time.time() - float(d.get("saved") or 0) > MP.BEFORE_SECS:
                return False
            for k in self.STATE_KEYS:
                v = d.get(k)
                if isinstance(v, dict):
                    if isinstance(v.get("where"), list):
                        v["where"] = tuple(v["where"])          # (JSON keeps a tuple as a list)
                    if getattr(self, k, None) is None:
                        setattr(self, k, v)
            self._mp_n = max(getattr(self, "_mp_n", 0), int(d.get("n") or 0))
            run = getattr(self, "mp_run", None)
            if run is not None:
                run["saved"] = float(d.get("saved") or time.time())
            buglog.debug("Map profit", "restored the map in progress after a restart")
            return True
        except Exception:
            buglog.caught()
            return False

    def mp_done(self):
        """The map you came back from is done: its line goes in the log (if you looked at your inventory after it)."""
        pend, self.mp_pending = getattr(self, "mp_pending", None), None
        if pend is None or (pend.get("visit") is None and not pend.get("gain")):
            return None
        e = self._mp_entry(pend)
        e["run"] = pend["run"]
        MP.log_add(e)
        self.mp_save()
        self.mp_last = e
        buglog.debug("Map profit", f"a map: {len(e['rows'])} items changed")      # (no names, no amounts)
        self.mp_paint()
        return e

    def mp_check_done(self, now=None):
        """Not back into it for DONE_SECS: it's done."""
        pend = getattr(self, "mp_pending", None)
        if pend is not None and (now or time.time()) - pend.get("left", 0) >= MP.DONE_SECS:
            return self.mp_done()
        return None

    def mp_so_far(self):
        """The map you're between visits of (a town trip): its profit so far, or None."""
        if self.mp_on():
            self.mp_restore()
        pend = getattr(self, "mp_pending", None)
        if pend is None or (pend.get("visit") is None and not pend.get("gain")):
            return None
        return self._mp_entry(pend)

    def mp_area(self, kind, before, where, left):
        """breach_area: into a map from home - its "before" is the last clear look at home; out of it - each visit
        home adds its loot until it's done. Back into the same map (its portal, a town trip): the same run."""
        if not self.mp_on():
            return
        self.mp_restore()
        try:
            self._mp_area(kind, before, where, left)
        finally:
            self.mp_save()

    def _mp_area(self, kind, before, where, left):
        now = time.time()
        self.mp_check_done(now)
        run = getattr(self, "mp_run", None)
        if kind == "map" and before is None and run is not None:
            # 3.0.6: the app restarted - Client.txt's first line says where you are. The same map: it goes on (its
            # time counts on). Another place: the map you were in ended while the app was off.
            if run.get("where") == where:
                return
            run["secs"] += max(0.0, run.get("saved", now) - run["start"])
            run["left"] = run.get("saved", now)
            self.mp_pending, self.mp_run = run, None
            self.mp_done()
            run = None
        elif kind in ("hideout", "town") and before is None and run is not None:
            run["secs"] += max(0.0, run.get("saved", now) - run["start"])     # (out of it while the app was off)
            run["left"] = run.get("saved", now)
            self.mp_pending, self.mp_run = run, None
            return
        if kind == "map" and before != "map":
            pend = getattr(self, "mp_pending", None)
            if pend is not None and pend.get("where") == where:
                self._mp_visit_in(pend)                     # (back through its portal: the same map goes on, from
                home = self.mp_home_base()                  # what you went back in with)
                if home is not None and home["t"] >= pend.get("left", 0):
                    pend["seg_before"] = dict(home["counts"])
                pend["start"] = now
                self.mp_run, self.mp_pending = pend, None
                return
            self.mp_done()                                  # (another map: the last one is done)
            home = self.mp_home_base(stashed=True)
            self.mp_home_cov = {}                           # (used up: a later map starts from its own looks)
            if home is not None and now - home["t"] < MP.BEFORE_SECS:
                self._mp_n = getattr(self, "_mp_n", 0) + 1
                self.mp_run = {"before": home, "seg_before": dict(home["counts"]), "gain": {}, "start": now,
                               "secs": 0, "where": where, "map": self.mp_map_name(where),
                               "run": f"{now:.3f}-{self._mp_n}"}
            else:
                # 3.0.6 (most players forget to read the inventory before a run, especially the first of the day):
                # no read before it - it still counts. What you went in with is taken as your
                # Top Up supplies only (they're left out of the loot), so everything else you come back with is
                # this map's. Marked ≈ with how it was worked out.
                self._mp_n = getattr(self, "_mp_n", 0) + 1
                self.mp_run = {"before": {"t": now, "counts": {}, "unknown": 0}, "seg_before": {}, "gain": {},
                               "start": now, "secs": 0, "where": where, "map": self.mp_map_name(where),
                               "run": f"{now:.3f}-{self._mp_n}", "est": True}
        elif left and run is not None:
            run["secs"] += now - run["start"]
            run["left"] = now
            self.mp_pending, self.mp_run = run, None

    @staticmethod
    def mp_map_name(where):
        try:
            from . import maplib
            return maplib.display_name(where[0]) if where else ""
        except Exception:
            return ""

    # ---------------------------------------------------------------- what it says
    def mp_totals(self):
        s = getattr(self, "tk_session", None)
        start = getattr(s, "started", None) if s is not None else None
        if not isinstance(start, (int, float)):
            start = time.time() - 12 * 3600
        return MP.totals(MP.log_read(time.time() - 2 * 86400), session_start=start)

    def mp_bar_text(self):
        """The bar's part: the last map's profit, "+3.8 div" - or "Profit –" before one is counted. (2.132.2,
        feedback: nothing lost was marked as -div, and the arrows can go - a total of the profit per map is
        enough: no arrows, and a map's profit is what it gained.)"""
        if not self.mp_on():
            return ""
        from .pricefmt import fmt_div
        try:
            self.mp_check_done()                            # (the bar redraws each second: a map can be done now)
        except Exception:
            buglog.caught()
        # 3.0.6 (someone done running still needs the last map's profit, without opening another map): the map you
        # just read your inventory after shows at once - it
        # still adds a second visit (a town trip) and is written down when you start another map or after a while
        e = self.mp_so_far() or getattr(self, "mp_last", None)
        if e is None:
            last = MP.log_read(time.time() - 12 * 3600)
            e = self.mp_last = last[-1] if last else None
        if e is None:
            return "Profit –"
        if abs(e.get("div") or 0) < 0.0005:               # 2.139.1 (feedback: a +0.000 div showed): nothing gained
            return "0 div"
        return ("≈" if e.get("est") else "") + MP.signed(e["div"], fmt_div)   # (2.139.0: LAST MAP'S PROFIT)

    def mp_breakdown(self, e=None):
        """How the bar's number was worked out: [line, ...] (the hover)."""
        from .pricefmt import fmt_div
        so_far = None if e is not None else self.mp_so_far()
        e = e or getattr(self, "mp_last", None)
        if e is None and so_far is None:
            return ["No map counted yet.",
                    f"Back from a map, open your inventory and press {self.look_key_text()} when the card asks."]
        out = []
        if so_far is not None:                              # 2.132.1: a town trip - it counts when you're done
            out.append(f"This map so far: {MP.signed(so_far['div'], fmt_div)}" +
                       (f"  ·  {so_far['map']}" if so_far.get("map") else "") + f"  (final when you start another map, or in {MP.DONE_SECS // 60} min)")
            if e is None:
                e = so_far
        mins = e.get("secs", 0) // 60
        out.append(f"Last map: {MP.signed(e['div'], fmt_div)}" + (f"  ·  {e['map']}" if e.get("map") else "")
                   + (f"  ·  {mins} min" if mins else ""))
        if so_far is not None and e is so_far:
            out.pop()
        for name, b, a, each in e.get("rows", [])[:8]:
            out.append(f"{name}: +{a - b}  ({MP.signed((a - b) * each, fmt_div)})")
        if len(e.get("rows", [])) > 8:
            out.append(f"+{len(e['rows']) - 8} more - Maps… has them all")
        t = self.mp_totals()
        sd, sn = t["session"]
        out.append(f"Session: {MP.signed(sd, fmt_div)} · {sn} map{'s' if sn != 1 else ''}"
                   + (f" · {MP.signed(t['per_hour'], fmt_div)} / hour" if t["per_hour"] is not None else ""))
        if e.get("est"):
            out.append("≈ No read before this map: all you came back with counts, except Top Up supplies")
        if e.get("unknown"):
            # 3.0.6 (the "teach me a currency with ctrl+c" line is removed): Scan stash teaches them by picture
            out.append(f"{e['unknown']} item{'s' if e['unknown'] != 1 else ''} not known yet - Scan stash on Wealth "
                       f"learns them")
        out.append("Currency Exchange items only, not your Top Up supplies · Exchange Rates prices · on your PC only")
        return out

    def mp_paint(self):
        try:
            self.tracker_overlay_draw(self.tracker_numbers())
        except Exception:
            buglog.caught()
        try:
            self.mp_list_refresh()
        except Exception:
            buglog.caught()

    # ---------------------------------------------------------------- the bar's hover
    def mp_hover_show(self, x, y):
        self.mp_hover_hide()
        from .overlaywin import pal
        P = pal()
        w = self.mp_tip = tk.Toplevel(self.root)
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        box = tk.Frame(w, bg=P.get("bg", "#151311"), highlightthickness=1,
                       highlightbackground=P.get("rim") or P.get("line", "#3a3226"), padx=8, pady=8)
        box.pack()
        for i, line in enumerate(self.mp_breakdown()):
            tk.Label(box, text=line, bg=P.get("bg", "#151311"), anchor="w", justify="left",
                     fg=(P.get("big") or P.get("text", "#efe6d2")) if i == 0 else
                     (P.get("muted", "#a3957e") if i >= len(self.mp_breakdown()) - 1 else P.get("text", "#efe6d2")),
                     font=(P.get("font") or "Segoe UI", 10, "bold" if i == 0 else "normal")).pack(fill="x")
        w.update_idletasks()
        w.geometry(f"+{int(x - w.winfo_reqwidth() // 2)}+{int(y - w.winfo_reqheight() - 8)}")

    def mp_hover_hide(self, _e=None):
        w, self.mp_tip = getattr(self, "mp_tip", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def mp_bar_bind(self, cv, item):
        """The bar's profit part: hover = how it was worked out, click = Maps…"""
        cv.addtag_withtag("mg_profit", item)
        cv.tag_bind("mg_profit", "<Enter>", lambda e: self.mp_hover_show(e.x_root, e.y_root - 6))
        cv.tag_bind("mg_profit", "<Leave>", self.mp_hover_hide)
        cv.tag_bind("mg_profit", "<Button-1>", lambda _e: (self.mp_hover_hide(), self.mp_list_open()))

    # ---------------------------------------------------------------- 2.132.6 Overlay ↳ Map Profit (a page, was a window)
    def mp_list_open(self):
        """The Map Profit page (feedback: it belongs under Overlay when Map Profit is enabled, not in a new window)."""
        self.shell.open("mapprofit")
        return getattr(self, "mp_tv", None)

    def build_map_profit(self, body):
        P1, P2 = C["panel"], C["panel2"]
        bar = tk.Frame(body, bg=P1, padx=8, pady=8)
        bar.pack(fill="x")
        self.mp_q = tk.StringVar()
        tk.Label(bar, text="🔍", bg=P1, fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(0, 4))
        ent = ttk.Entry(bar, textvariable=self.mp_q, width=22)
        ent.pack(side="left")
        Tooltip(ent, "Find a map, or every map an item dropped in (Divine Orb, Omen of ...).")
        self.mp_q.trace_add("write", lambda *_a: self.mp_list_refresh())
        self.mp_view = SegBar(bar, list(VIEWS), command=lambda v: self.mp_list_refresh(), size=10, pad=(12, 4))
        self.mp_view.pack(side="left", padx=(12, 0))
        self.mp_clear_btn = ttk.Button(bar, text="Clear all…", command=self.mp_clear_all)
        self.mp_clear_btn.pack(side="right")
        Tooltip(self.mp_clear_btn, "Hide every map from the list, or delete them - asks first, and offers a CSV")
        # 2.138.0 (feedback: an Export CSV option on Map profit)
        self.mp_export_btn = ttk.Button(bar, text="Export CSV…", command=self.mp_export)
        self.mp_export_btn.pack(side="right", padx=(0, 8))
        Tooltip(self.mp_export_btn, "Every map in the list, one row per item: before, after, change and value")
        self.mp_del_btn = ttk.Button(bar, text="Delete", command=self.mp_delete_sel)
        self.mp_del_btn.pack(side="right", padx=(0, 8))
        Tooltip(self.mp_del_btn, "Delete the picked rows (Undo puts them back)")
        self.undo_button(bar, "mapprofit", side="right", padx=(0, 8))
        self.mp_sum = tk.Label(body, text="", bg=P1, fg=C["text"], font=("Segoe UI", 10, "bold"), anchor="w", padx=12)
        self.mp_sum.pack(fill="x")
        self.look_needed(body, P1, "Map profit counts a map only when you press your Read Key - a key just for "
                                   "that. None is set yet.").pack(fill="x", padx=12)
        # 2.138.0: maps hidden by Clear all › Hide from the list - still kept; one click shows them again
        self.mp_hidden_lbl = tk.Label(body, text="", bg=P1, fg=C["accent"], cursor="hand2", anchor="w", padx=12,
                                      font=("Segoe UI", 9))
        self.mp_hidden_lbl.bind("<Button-1>", lambda _e: self.mp_unhide())
        # 2.132.6 (feedback: the most recently completed map was not counted): items it doesn't know yet
        # can't be counted - say so, and how to teach them
        self.mp_hint = tk.Label(body, text="", bg=P1, fg=C["warn"] if "warn" in C else C["muted"], anchor="w", padx=12,
                                justify="left")
        self.mp_chart = tk.Canvas(body, bg=P2, height=150, highlightthickness=0)
        self.mp_chart.pack(fill="x", padx=8, pady=(8, 8))
        self.mp_chart.bind("<Configure>", lambda e: self.mp_chart_draw())
        self.mp_chart.bind("<Leave>", lambda e: self.mp_hover_hide())
        box = tk.Frame(body, bg=P1)
        box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tv = self.mp_tv = ttk.Treeview(box, columns=("a", "b", "c", "d", "e"), show="headings", selectmode="extended")
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        tv.bind("<Motion>", self._mp_row_hover)
        tv.bind("<Leave>", lambda _e: self.mp_hover_hide())
        tv.bind("<<TreeviewSelect>>", lambda _e: self.mp_greys())
        tv.bind("<Delete>", lambda _e: self.mp_delete_sel())
        self.mp_empty = tk.Frame(box, bg=P1)
        self.mp_how = tk.Label(body, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w", padx=12,
                               justify="left")
        self.mp_how.pack(fill="x", pady=(0, 8))
        autowrap(self.mp_how, pad=24)                     # (D3: wraps at Drawer width)
        self.mp_list_refresh()

    def mp_greys(self):
        for b, ok in ((getattr(self, "mp_del_btn", None), bool(self.mp_tv.selection())),
                      (getattr(self, "mp_clear_btn", None), bool(getattr(self, "mp_rows", None))),
                      (getattr(self, "mp_export_btn", None), bool(getattr(self, "mp_rows", None)))):
            if b is not None:
                b.state(["!disabled"] if ok else ["disabled"])

    def _mp_runs_of(self, iids):
        out = set()
        for i in iids:
            r = (getattr(self, "mp_rows", None) or {}).get(i)
            if r is None:
                continue
            for run in r.get("runs") or [r]:
                out.add(run["id"])
        return out

    def mp_delete_sel(self):
        ids = self._mp_runs_of(self.mp_tv.selection())
        if not ids:
            return None
        gone = MP.log_delete(ids)
        n = len(ids)
        self.push_undo("mapprofit", f"{n} map{'s' if n != 1 else ''}", lambda: (MP.log_restore(gone),
                                                                          self.mp_after_change()))
        self.mp_after_change()
        self._say(f"Deleted {n} map{'s' if n != 1 else ''}. Undo puts them back.", 6)
        return gone

    # ---------------------------------------------------------------- 2.138.0: Export CSV, and Clear all asks first
    def mp_export(self, path=None):
        """Every map shown (search and hidden maps respected) to a CSV - one row per item."""
        from .csvexport import write_map_profit
        runs = self.mp_runs(self.mp_q.get() if getattr(self, "mp_q", None) else "")
        if not runs:
            return None
        if path is None:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(parent=self.dlg_parent(), defaultextension=".csv",
                                                initialfile=f"map_profit_{time.strftime('%Y-%m-%d')}.csv",
                                                filetypes=[("CSV", "*.csv")])
        if not path:
            return None
        try:
            n = write_map_profit(path, runs)
        except OSError as e:
            self._say(f"Couldn't save the CSV ({e.__class__.__name__}).", 8)
            return None
        self._say(f"Saved {n} map{'s' if n != 1 else ''} to {os.path.basename(path)}.", 8)
        return path

    def mp_hidden_before(self):
        return float(SETTINGS.get("mp_hidden_before") or 0)

    def mp_unhide(self):
        SETTINGS["mp_hidden_before"] = 0
        save_json("settings.json", SETTINGS)
        self.mp_after_change()

    def mp_clear_all(self, ask=True, how=None):
        """2.138.0 (feedback: Clear all should ask whether to export the data first, and whether to clear the list or
        the
        data itself): a small question - Export CSV first, Hide from the list (kept,
        one click brings them back), or Delete for good (Undo works until the app closes). how= "hide" / "delete"
        answers it without asking (tests)."""
        runs = self.mp_runs()
        if not runs:
            return None
        if how is None and ask:
            return self.mp_clear_ask(runs)
        return self._mp_clear_do(runs, how or "delete")

    def _mp_clear_do(self, runs, how):
        n = len(runs)
        if how == "hide":
            before = self.mp_hidden_before()
            SETTINGS["mp_hidden_before"] = max(r["t"] for r in runs) + 0.001
            save_json("settings.json", SETTINGS)

            def back():
                SETTINGS["mp_hidden_before"] = before
                save_json("settings.json", SETTINGS)
                self.mp_after_change()
            self.push_undo("mapprofit", f"hiding {n} maps", back)
            self.mp_after_change()
            self._say(f"Hid {n} map{'s' if n != 1 else ''}. They're kept - \"Show hidden maps\" brings them back.", 8)
            return "hidden"
        gone = MP.log_delete({r["id"] for r in runs})
        self.push_undo("mapprofit", f"{n} maps", lambda: (MP.log_restore(gone), self.mp_after_change()))
        self.mp_after_change()
        self._say(f"Deleted {n} map{'s' if n != 1 else ''}. Undo puts them back until you close the app.", 8)
        return gone

    def mp_clear_ask(self, runs):
        P2 = C["panel2"]
        old = getattr(self, "mp_clear_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.destroy()
        except tk.TclError:
            pass
        w = self.mp_clear_win = tk.Toplevel(self.root, bg=P2)
        w.title("Clear all maps")
        w.transient(self.root)
        w.resizable(False, False)
        box = tk.Frame(w, bg=P2, padx=16, pady=16)
        box.pack(fill="both", expand=True)
        n = len(runs)
        tk.Label(box, text=f"Clear all {n} map{'s' if n != 1 else ''}?", bg=P2, fg=C["text"],
                 font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(box, text="Save a copy first if you might want the numbers later.", bg=P2, fg=C["muted"],
                 justify="left", wraplength=440, anchor="w").pack(fill="x", pady=(4, 12))
        self.mp_clear_note = tk.Label(box, text="", bg=P2, fg=C["muted"], anchor="w", font=("Segoe UI", 9))
        exp = ttk.Button(box, text="Export CSV first…", style="Primary.TButton")

        def do_export():
            p = self.mp_export()
            if p:
                exp.config(text="✓ Exported", style="TButton")
                exp.state(["disabled"])
                self.mp_clear_note.config(text=f"✓ Saved {os.path.basename(p)}")
                self.mp_clear_note.pack(fill="x", pady=(0, 8))
        exp.config(command=do_export)
        exp.pack(anchor="w", pady=(0, 12))
        for how, label, what in (("hide", "Hide from the list", "Kept on your PC. \"Show hidden maps\" brings them back."),
                                 ("delete", "Delete for good", "Gone from your PC. Undo works until you close the app.")):
            row = tk.Frame(box, bg=P2)
            row.pack(fill="x", pady=2)
            ttk.Button(row, text=label, width=18,
                       command=lambda h=how: (w.destroy(), setattr(self, "mp_clear_win", None),
                                              self._mp_clear_do(runs, h))).pack(side="left")
            tk.Label(row, text=what, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(side="left", padx=(8, 0))
        foot = tk.Frame(box, bg=P2)
        foot.pack(fill="x", pady=(12, 0))
        ttk.Button(foot, text="Cancel", command=lambda: (w.destroy(), setattr(self, "mp_clear_win", None))).pack(
            side="right")
        w.protocol("WM_DELETE_WINDOW", lambda: (w.destroy(), setattr(self, "mp_clear_win", None)))
        try:
            from .style import center_over
            center_over(w, self.root)
            self.popup_over_app(w)
        except Exception:
            buglog.caught()
        return w

    def mp_after_change(self):
        self.mp_last = None
        self.mp_list_refresh()
        try:
            self.tracker_overlay_tick() if hasattr(self, "tracker_overlay_tick") else None
        except Exception:
            buglog.caught()

    def mp_runs(self, q="", all_maps=False):
        """The log as maps (a map you went back into through your portal is one), newest first."""
        runs = {}
        for e in MP.log_read(time.time() - MP.KEEP_DAYS * 86400):
            rid = e.get("run") or str(e.get("t"))
            r = runs.setdefault(rid, {"id": rid, "map": e.get("map", ""), "t": e["t"], "secs": 0, "div": 0.0,
                                      "rows": {}, "unknown": 0, "n": len(runs)})
            r["t"] = max(r["t"], e["t"])
            r["secs"] += e.get("secs", 0)
            r["div"] += e.get("div", 0)
            r["unknown"] = max(r["unknown"], e.get("unknown", 0))
            for name, b, a, each in e.get("rows", []):
                was = r["rows"].get(name)
                r["rows"][name] = [was[0] if was else b, a, each]
        out = sorted(runs.values(), key=lambda r: (-r["t"], -r["n"]))
        cut = self.mp_hidden_before()                     # 2.138.0: hidden by Clear all › Hide from the list
        if cut and not all_maps:
            self.mp_n_hidden = sum(1 for r in out if r["t"] < cut)
            out = [r for r in out if r["t"] >= cut]
        else:
            self.mp_n_hidden = 0
        q = (q or "").strip().lower()
        if q:
            out = [r for r in out if q in r["map"].lower() or any(q in n.lower() for n in r["rows"])]
        return out

    def mp_list_refresh(self):
        tv = getattr(self, "mp_tv", None)
        if tv is None or not tv.winfo_exists():
            return
        from .pricefmt import fmt_div
        view = self.mp_view.get() if getattr(self, "mp_view", None) is not None else "All Time"
        runs = self.mp_runs(self.mp_q.get() if getattr(self, "mp_q", None) else "")
        tv.delete(*tv.get_children())
        self.mp_rows = {}
        if view == "All Time":
            cols = (("Map", 260, "w"), ("Time", 70, "e"), ("Profit", 110, "e"), ("When", 160, "w"), ("", 10, "w"))
        else:
            cols = (("Day" if view == "Daily" else "Hour", 160, "w"), ("Maps", 60, "e"), ("Profit", 110, "e"),
                    ("Per map", 100, "e"), ("Per hour", 100, "e"))
        for c, (title, wd, anc) in zip(("a", "b", "c", "d", "e"), cols):
            tv.heading(c, text=title)
            tv.column(c, width=wd, anchor=anc, stretch=c == "a")
        if view == "All Time":
            for i, r in enumerate(runs):
                iid = f"r{i}"
                self.mp_rows[iid] = r
                m, s = divmod(int(r["secs"]), 60)
                tv.insert("", "end", iid=iid, values=(r["map"] or "a map", f"{m}:{s:02d}" if r["secs"] else "–",
                                                      MP.signed(r["div"], fmt_div),
                                                      time.strftime("%a %d %b, %H:%M", time.localtime(r["t"])), ""))
            self.mp_buckets = MP.buckets(runs, "day")
        else:
            kind = "day" if view == "Daily" else "hour"
            self.mp_buckets = MP.buckets(runs, kind)
            for i, (label, start, n, div, secs) in enumerate(reversed(self.mp_buckets)):
                iid = f"b{i}"
                end = start + (86400 if kind == "day" else 3600)
                self.mp_rows[iid] = {"runs": [r for r in runs if start <= r["t"] < end], "label": label, "div": div}
                tv.insert("", "end", iid=iid, values=(label, n, MP.signed(div, fmt_div), MP.signed(div / n, fmt_div),
                                                      MP.signed(div * 3600 / secs, fmt_div) if secs >= 60 else "–"))
        total = sum(r["div"] for r in runs)
        secs = sum(r["secs"] for r in runs)
        t = self.mp_totals()
        sd, sn = t["session"]
        self.mp_how.config(text=self.mp_how_text())
        self.mp_sum.config(text=(f"{len(runs)} map{'s' if len(runs) != 1 else ''} · {MP.signed(total, fmt_div)}"
                                 + (f" · {MP.signed(total / len(runs), fmt_div)} / map" if runs else "")
                                 + (f" · {MP.signed(total * 3600 / secs, fmt_div)} / hour" if secs >= 60 else "")
                                 + (f"     Session: {MP.signed(sd, fmt_div)} ({sn})" if sn else "")) if runs else "")
        nh = getattr(self, "mp_n_hidden", 0)
        if nh:
            self.mp_hidden_lbl.config(text=f"Show hidden maps ({nh}) ›")
            if not self.mp_hidden_lbl.winfo_manager():
                self.mp_hidden_lbl.pack(fill="x", after=self.mp_sum)
        elif self.mp_hidden_lbl.winfo_manager():
            self.mp_hidden_lbl.pack_forget()
        last = runs[0] if runs else None
        if last and last["unknown"] >= 5 and not last["rows"]:
            self.mp_hint.config(text=f"⚠ Last map: {last['unknown']} items not recognized, so nothing was counted. "
                                     f"Scan stash on Wealth learns them by picture.")
            if not self.mp_hint.winfo_manager():
                self.mp_hint.pack(fill="x", after=self.mp_sum)
        elif self.mp_hint.winfo_manager():
            self.mp_hint.pack_forget()
        self.mp_chart_draw()
        for ch in self.mp_empty.winfo_children():
            ch.destroy()
        self.mp_greys()
        if runs:
            self.mp_empty.place_forget()
            return
        P1 = C["panel"]                                     # (UX: empty - what it is + one button)
        self.mp_empty.place(relx=0.5, rely=0.35, anchor="center")
        if nh and not (self.mp_q.get() if getattr(self, "mp_q", None) else ""):
            tk.Label(self.mp_empty, text=f"Your {nh} map{'s are' if nh != 1 else ' is'} hidden (kept on your PC).",
                     bg=P1, fg=C["muted"]).pack()
            ttk.Button(self.mp_empty, text="Show hidden maps", style="Primary.TButton", command=self.mp_unhide).pack(
                pady=(8, 0))
            return
        tk.Label(self.mp_empty, text=f"No maps counted yet. Back from a map, open your inventory and press "
                                     f"{self.look_key_text()} when the card asks.\nA map you skip has no entry.",
                 bg=P1, fg=C["muted"], justify="center").pack()
        if not self.mp_on():
            ttk.Button(self.mp_empty, text="Turn on Map profit", style="Primary.TButton",
                       command=lambda: (self.mp_set(True), self.mp_sync_switch(), self.mp_list_refresh())
                       ).pack(pady=(8, 0))

    def mp_how_text(self):
        """The line under the list: which maps are in it, how a map's number is worked out, and where it's kept."""
        return (f"Back from a map, press {self.look_key_text()} with your inventory open. A map's loot = what your "
                f"inventory gained since your last read at home. No read before a map? It still counts: all you came "
                f"back with except Top Up supplies (marked ≈). On your PC only - never uploaded or shared.")

    def mp_chart_draw(self):
        """Bars: profit per day (All Time, Daily) or per hour (Hourly). Hover a bar for its numbers."""
        cv = getattr(self, "mp_chart", None)
        if cv is None or not cv.winfo_exists():
            return
        from .pricefmt import fmt_div
        cv.delete("all")
        bs = list(getattr(self, "mp_buckets", []) or [])
        w, h = max(200, cv.winfo_width()), max(100, cv.winfo_height())
        if getattr(self, "mp_view", None) is not None and self.mp_view.get() == "Daily":
            bs = bs[-30:]
        if not bs:
            cv.create_text(w // 2, h // 2, text="No profit to chart yet", fill=C["muted"], font=("Segoe UI", 9))
            return
        top = max(max(b[3] for b in bs), 1e-9)
        pad, base = 12, h - 22
        bw = max(4, min(40, (w - 2 * pad) // len(bs) - 4))
        for i, (label, _start, n, div, _secs) in enumerate(bs):
            x0 = pad + i * (bw + 4)
            y0 = base - int((base - 18) * max(div, 0) / top)
            item = cv.create_rectangle(x0, y0, x0 + bw, base, fill=C["good"], outline="")
            cv.tag_bind(item, "<Enter>", lambda e, t=f"{label}: {MP.signed(div, fmt_div)} from {n} map"
                        f"{'s' if n != 1 else ''}": self.mp_chart_tip(e, t))
            cv.tag_bind(item, "<Leave>", lambda e: self.mp_hover_hide())
        cv.create_line(pad, base, w - pad, base, fill=C["line"])
        cv.create_text(pad, h - 10, text=bs[0][0], anchor="w", fill=C["muted"], font=("Segoe UI", 8))
        cv.create_text(w - pad, h - 10, text=bs[-1][0], anchor="e", fill=C["muted"], font=("Segoe UI", 8))
        cv.create_text(pad, 8, text=f"best {MP.signed(top, fmt_div)}", anchor="w", fill=C["muted"],
                       font=("Segoe UI", 9))

    def mp_chart_tip(self, e, text):
        self.mp_hover_hide()
        w = self.mp_tip = tk.Toplevel(self.root, bg=C["panel"])
        w.overrideredirect(True)
        tk.Label(w, text=text, bg=C["panel"], fg=C["text"], font=("Segoe UI", 9), padx=8, pady=4,
                 highlightthickness=1, highlightbackground=C["line"]).pack()
        w.geometry(f"+{e.x_root + 14}+{e.y_root + 10}")

    def _mp_row_hover(self, e):
        tv = self.mp_tv
        iid = tv.identify_row(e.y)
        r = (getattr(self, "mp_rows", None) or {}).get(iid)
        if r is None or "runs" in r:
            return self.mp_hover_hide()
        if getattr(self, "_mp_hover_iid", None) == iid and getattr(self, "mp_tip", None) is not None:
            return None
        self._mp_hover_iid = iid
        rows = sorted(([n, v[0], v[1], v[2]] for n, v in r["rows"].items()),
                      key=lambda x: -abs((x[2] - x[1]) * x[3]))
        e2 = {"div": r["div"], "map": r["map"], "secs": r["secs"], "rows": rows, "unknown": r["unknown"]}
        lines = self.mp_breakdown(e2)
        self.mp_hover_hide()
        w = self.mp_tip = tk.Toplevel(self.root, bg=C["panel"])
        w.overrideredirect(True)
        box = tk.Frame(w, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"], padx=8, pady=8)
        box.pack()
        for i, line in enumerate(lines):
            tk.Label(box, text=line, bg=C["panel"], fg=C["muted"] if i == len(lines) - 1 else C["text"],
                     font=("Segoe UI", 9, "bold" if i == 0 else "normal"), anchor="w").pack(fill="x")
        w.geometry(f"+{e.x_root + 16}+{e.y_root + 12}")
        return None

    # (nav phase 2: its row is in the one Helpers table - alerts_page.build_alerts_panel)

    def mp_sync_switch(self):
        v = getattr(self, "al_mp", None)
        if v is not None and bool(v.get()) != bool(MP.cfg()["on"]):
            v.set(bool(MP.cfg()["on"]))
