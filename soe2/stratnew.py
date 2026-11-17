"""Farming Strategies › New strat (3.0.6, the approved mockup - it replaces the Add my own form, a popup of labels and
switches: owner "so hard to understand"). One page, drawn on a canvas in the Farming Strategies page like an opened
strat (stratview.StratCanvas), in five numbered parts:

  1 What it is      name, league (from Settings, read only), category, mechanic (its tablet's picture; none: the
                    word alone), effort, budget, play style - chips, not switches
  2 Your tablets    hover a tablet in game, Ctrl+Alt+C: it drops in as a card (up to 4); tick the mods that matter.
                    Made for you: a stash regex for the ticked mods and a Trade Site search (their base, 10+ uses)
  3 Your waystone   the same for the waystone (its tier and ticked numbers)
  4 Atlas masters   optional: up to 4 of each master's 12 choices
  5 How it goes     numbered steps (a new one appears when the last is filled), loot to sell; More details keeps
                    every older field (summary, requirements, tips, risks, sources ...) so nothing is lost
A side panel shows the row it will have in Find, Cost per map (worked out from the copies at today's prices - a sum,
one hover from how), that profit an hour comes from runs, and a checklist. Cancel (ghost) and Save strat (the one
orange button, grayed until a name, a mechanic and one step are there - "Needs: ..." says what's missing).

GGG policy: the copies come only through the app's one clipboard read per copy key press (clipread -> app.accept_clip
-> mm_new_take_clip, while this page shows). Nothing here reads the clipboard or the screen, and no timer reads."""
import time
import tkinter as tk
import webbrowser

from . import buglog
from . import moneymakers as MM
from . import themes as TH
from .config import SETTINGS
from .style import C
from .stratview import R, _rr_points

PLAY = MM.TAG_GROUPS["Play style"]
MORE_LISTS = (("requirements", "Requirements", 2), ("craft_steps", "Craft steps", 3), ("setup", "Other setup", 2),
              ("tips", "Tips", 2), ("risks", "Risks", 2), ("_sources", "Sources (links)", 2))
OLD_LISTS = (("tablets", "Tablets (notes)"), ("waystones", "Waystones (notes)"), ("atlas", "Atlas notes"))
F9, F10, FB = ("Segoe UI", 9), ("Segoe UI", 10), ("Segoe UI", 8, "bold")  # token-ok (canvas)


class StratNewPage:
    """Mixed into the Farming Strategies page (MoneyMakersPage)."""

    # ------------------------------------------------------------------ open / close
    def mm_new_open(self, s=None, suggest=False):
        """New strat (s None), or one of yours to edit (s), or someone else's Community strat to suggest an edit to
        (suggest=True): the same page, filled in."""
        s = dict(s or {})
        s.pop("origin", None)
        new = not s.get("name")
        tags = list(s.get("tags") or [])
        items = s.get("items") or []
        cards = [c for c in (MM.item_card(it) for it in items if it.get("kind") == "tablet") if c]
        way = next((c for c in (MM.item_card(it) for it in items if it.get("kind") == "waystone") if c), None)
        own = MM.league_base(SETTINGS.get("league")) if new else ""
        self.mm_nd = d = {
            "base": s, "new": new, "suggest": bool(suggest), "post": s.get("_post"),
            "cat": s.get("category") if s.get("category") in MM.TAXONOMY else "Mapping",
            "typ": None if new else s.get("type"),
            "effort": "Moderate" if new else MM.effort_of(s), "effort0": None if new else MM.effort_of(s),
            "budget": MM.budget_of(s), "play": [t for t in tags if t in PLAY],
            "tags": [t for t in tags if t not in MM.BUDGETS and t not in PLAY],
            "cards": cards[:MM.TABLETS_MAX],
            "way": way, "others": [it for it in items if it.get("kind") not in ("tablet", "waystone")],
            "masters": {k: list(v) for k, v in (s.get("masters") or {}).items()},
            "league": s.get("league") or own, "more": False, "msg": None,
            "cost_sid": s.get("id") if items and not new else None, "cost_items": [dict(i) for i in items],
            "gen": 0, "job": None,
        }
        if len(cards) > MM.TABLETS_MAX:                     # (an older strat with more: kept as they were)
            d["others"] += [it for it in items if it.get("kind") == "tablet"][MM.TABLETS_MAX:]
        self._mm_new_widgets(s)
        self.mm_new_on = True
        self._mm_frames()
        cv = self.mm_new_cv
        cv.yview_moveto(0)
        cv.later(10)
        return d

    def mm_new_close(self):
        """Cancel (or after Save): back to where you were - Find, or the opened strat."""
        d = getattr(self, "mm_nd", None) or {}
        if d.get("job"):
            try:
                self.root.after_cancel(d["job"])
            except (tk.TclError, ValueError):
                pass
        for k in [k for k in self.mm_costs() if str(k).startswith("_new")]:
            self.mm_costs().pop(k, None)
        self.mm_new_on = False
        self._mm_frames()

    def _mm_frames(self):
        """Exactly one of Find, an opened strat and New strat shows."""
        new, det = getattr(self, "mm_new_on", False), getattr(self, "mm_detail_on", False)
        want = self.mm_new_f if new else self.mm_open_f if det else self.mm_find_f
        for f in (self.mm_find_f, self.mm_open_f, self.mm_new_f):
            if f is not want and f.winfo_manager():
                f.pack_forget()
        if not want.winfo_manager():
            want.pack(fill="both", expand=True)
        for cv in (self.mm_find_cv, self.mm_detail_cv, self.mm_new_cv):
            cv.later(10)

    # ------------------------------------------------------------------ the typed fields (real entries on the canvas)
    def _mm_new_entry(self, value="", hint="", lines=0):
        cv = self.mm_new_cv
        kw = dict(bg=C["odd"], fg=C["text"], insertbackground=C["text"], relief="flat", highlightthickness=1,
                  highlightbackground=C["line"], highlightcolor=C["accent"], font=F10)
        if lines:
            w = tk.Text(cv, height=lines, wrap="word", padx=8, pady=8, undo=True, bd=0, **kw)
            w.insert("1.0", value)
            w.bind("<<Modified>>", lambda e: (w.edit_modified(False), self._mm_new_typed()))
            w.edit_modified(False)
            return w
        var = tk.StringVar(value=value)
        w = tk.Entry(cv, textvariable=var, bd=7, **kw)          # (the border is the field's inner padding)
        w.var = var
        if hint:
            ph = tk.Label(cv, text=hint, bg=C["odd"], fg=C["muted"], font=F10)
            ph.bind("<Button-1>", lambda e: w.focus_set())

            def show(*_a):
                try:
                    if var.get() or self.root.focus_get() is w:
                        ph.place_forget()
                    else:
                        ph.place(in_=w, x=7, rely=0.5, anchor="w")
                except (tk.TclError, KeyError):
                    pass
            for ev in ("<FocusIn>", "<FocusOut>", "<Map>"):
                w.bind(ev, show, add="+")
            var.trace_add("write", show)
            w.hint = ph
        var.trace_add("write", lambda *_a: self._mm_new_typed())
        return w

    def _mm_new_widgets(self, s):
        cv = self.mm_new_cv
        for w in list(cv.winfo_children()):
            w.destroy()
        nw = self.mm_nw = {"name": self._mm_new_entry(s.get("name", ""), "e.g. Breach in juiced T15 maps")}
        nw["steps"] = [self._mm_new_entry(x) for x in s.get("steps") or []]
        nw["steps"].append(self._mm_new_entry("", "Next step…"))
        nw["loot"] = self._mm_new_entry(", ".join(s.get("loot") or []), "e.g. Breach splinters, Catalysts")
        wt = s.get("waystone_tiers")
        more = {"summary": self._mm_new_entry(s.get("summary", ""), "one line - empty: your first step"),
                "regex": self._mm_new_entry(s.get("regex", ""), "empty: the tablets' Made for you search"),
                "tiers": self._mm_new_entry(MM.tiers_text(wt).replace("T", "") if isinstance(wt, dict) else "",
                                            "e.g. 14-16 - empty: your waystone's tier")}
        for key, _label, h in MORE_LISTS:
            val = [x.get("url", "") for x in s.get("sources") or []] if key == "_sources" else s.get(key) or []
            more[key] = self._mm_new_entry("\n".join(val), lines=h)
        for key, _label in OLD_LISTS:
            if s.get(key):
                more[key] = self._mm_new_entry("\n".join(s[key]), lines=2)
        nw["more"] = more

    def _mm_new_typed(self):
        """A key typed in a field: a new empty step when the last is filled; the side panel and Needs follow."""
        nw = getattr(self, "mm_nw", None)
        if not nw:
            return
        steps = nw["steps"]
        if steps and steps[-1].var.get().strip():
            for e in steps[:-1]:
                if getattr(e, "hint", None) is not None:
                    e.hint.place_forget()
            steps.append(self._mm_new_entry("", "Next step…"))
        if getattr(self, "mm_nd", None):
            self.mm_nd["msg"] = None
        self.mm_new_cv.later(180)

    def _mm_val(self, w):
        try:
            return w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.var.get()
        except tk.TclError:
            return ""

    def mm_new_fields(self):
        """-> {"name", "steps", "loot"} as typed now."""
        nw = self.mm_nw
        return {"name": self._mm_val(nw["name"]).strip(),
                "steps": [v.strip() for v in (self._mm_val(e) for e in nw["steps"]) if v.strip()],
                "loot": [x.strip() for x in self._mm_val(nw["loot"]).replace(";", ",").split(",") if x.strip()]}

    # ------------------------------------------------------------------ what's picked
    def mm_new_pick(self, what, value):
        """A chip: category, type (mechanic), effort, budget, play, tag."""
        d = self.mm_nd
        if what == "cat":
            d["cat"] = value
            if d["typ"] not in MM.TAXONOMY.get(value, ()):
                d["typ"] = None
        elif what == "typ":
            d["typ"] = None if d["typ"] == value else value
        elif what == "effort":
            d["effort"] = value
        elif what == "budget":
            d["budget"] = None if d["budget"] == value else value
        elif what == "play":
            d["play"] = [] if value is None else [t for t in d["play"] if t != value] + \
                ([] if value in d["play"] else [value])
        elif what == "tag":
            d["tags"] = [t for t in d["tags"] if t != value] + ([] if value in d["tags"] else [value])
        d["msg"] = None
        self.mm_new_cv.later(1)

    def mm_new_master(self, master, choice):
        d = self.mm_nd
        d["masters"], what = MM.master_pick(d["masters"], master, choice)
        if what == "full":
            self._say(f"{master}: {MM.MASTER_PICKS} of {MM.MASTER_PICKS} used - untick one first.", 5)
        self.mm_new_cv.later(1)
        return what

    def mm_new_masters_clear(self):
        self.mm_nd["masters"] = {}
        self.mm_new_cv.later(1)

    def mm_new_tick(self, which, line):
        """Tick / untick a copied item's mod (which: a tablet's index, or "way")."""
        d = self.mm_nd
        card = d["way"] if which == "way" else d["cards"][which]
        card["ticked"] = [m for m in card["ticked"] if m != line] + ([] if line in card["ticked"] else [line])
        self._mm_new_cost_later()
        self.mm_new_cv.later(1)

    def mm_new_remove(self, which):
        d = self.mm_nd
        if which == "way":
            d["way"] = None
        elif 0 <= which < len(d["cards"]):
            d["cards"].pop(which)
        self._mm_new_cost_later()
        self.mm_new_cv.later(1)

    # ------------------------------------------------------------------ copies (Ctrl+Alt+C, through app.accept_clip)
    def mm_new_capturing(self):
        """While New strat shows, a copied tablet or waystone goes to it."""
        if not getattr(self, "mm_new_on", False):
            return False
        try:
            return bool(self.mm_new_cv.winfo_ismapped())
        except (AttributeError, tk.TclError):
            return False

    def mm_new_take_clip(self, text):
        """One copy (the press's one read, done by clipread) -> a tablet card (up to 4) or the waystone."""
        d = self.mm_nd
        card = MM.copied_card(text)
        if card is None:
            self._say("New strat takes tablets and waystones - that copy was something else.", 6)
            return None
        card["copied"] = True
        if card["kind"] == "waystone":
            d["way"] = card
            self._say(f"New strat: your waystone - {card['base']}. Tick what matters.", 5)
        elif len(d["cards"]) >= MM.TABLETS_MAX:
            self._say(f"{MM.TABLETS_MAX} of {MM.TABLETS_MAX} tablets: remove one (✕) to add another.", 6)
            return None
        else:
            d["cards"].append(card)
            self._say(f"New strat: tablet {len(d['cards'])} of {MM.TABLETS_MAX} - {card['name']}. Tick the mods that "
                      "matter.", 5)
        self._mm_new_cost_later()
        self.mm_new_cv.later(1)
        return card

    # ------------------------------------------------------------------ Made for you
    def mm_new_items(self):
        d = self.mm_nd
        return ([MM.card_item(d["way"])] if d["way"] else []) + [MM.card_item(c) for c in d["cards"]] + \
            [dict(i) for i in d["others"]]

    def mm_new_made(self, kind):
        """Made for you for the tablets / the waystone -> {"regex", "url", "caption", "ticked"}."""
        d = self.mm_nd
        cards = d["cards"] if kind == "tablet" else [d["way"]] if d["way"] else []
        table = getattr(getattr(self, "engine", None), "table", None)
        sid_of, uses = None, None
        if table:
            from .mods import find_stat
            from .trade import uses_stat_id

            def sid_of(line):
                return find_stat(line, (), table)[0] or MM.stat_id(line)
            uses = uses_stat_id(table)
        return MM.made_for_you(kind, cards, SETTINGS.get("league"), sid_of, uses)

    def mm_new_copy(self, kind):
        rx = self.mm_new_made(kind)["regex"]
        return self.mm_item_copy(rx, "your " + ("tablets" if kind == "tablet" else "waystone")) if rx else None

    def mm_new_trade(self, kind):
        url = self.mm_new_made(kind)["url"]
        if url:
            webbrowser.open(url)
        return url

    # ------------------------------------------------------------------ Cost per map (the trade site, today)
    def _mm_new_sig(self, items):
        return [(i.get("kind"), i.get("base"), tuple(i.get("key_mods") or ()), i.get("count"), i.get("lasts"))
                for i in items]

    def _mm_new_cost_later(self):
        """The copies changed: check their prices a moment after the last change (one search per item, behind your
        own price checks). No league or no engine (a test): nothing."""
        d = self.mm_nd
        if d.get("job"):
            try:
                self.root.after_cancel(d["job"])
            except (tk.TclError, ValueError):
                pass
            d["job"] = None
        if getattr(self, "engine", None) is None or not SETTINGS.get("league"):
            return
        d["job"] = self.root.after(2500, self._mm_new_cost_go)

    def _mm_new_cost_go(self):
        d = getattr(self, "mm_nd", None)
        if not d or not getattr(self, "mm_new_on", False):
            return None
        d["job"] = None
        items = [i for i in self.mm_new_items() if i.get("kind") in ("tablet", "waystone")]
        if not items or (self._mm_new_sig(items) == self._mm_new_sig(d["cost_items"]) and d.get("cost_sid")):
            return None
        d["gen"] += 1
        sid = f"_new{d['gen']}"
        d["cost_sid"], d["cost_items"] = sid, items
        self.mm_costs()[sid] = {}
        self._mm_cost_busy = getattr(self, "_mm_cost_busy", set()) | {sid}
        self.engine.strat_cost_start({"id": sid, "items": items}, SETTINGS.get("league"))
        return sid

    def mm_new_cost(self):
        """-> (run_cost dict or None, busy?) for the copies as they are now."""
        d = self.mm_nd
        items = [i for i in self.mm_new_items() if i.get("kind") in ("tablet", "waystone")]
        if not items:
            return None, False
        same = d.get("cost_sid") and self._mm_new_sig(items) == self._mm_new_sig(d["cost_items"])
        busy = bool(d.get("job")) or not same or d.get("cost_sid") in getattr(self, "_mm_cost_busy", set())
        if not same:
            return None, busy
        c = MM.run_cost({"id": d["cost_sid"], "items": d["cost_items"]}, self.mm_costs())
        if c and c["sum"] == "the author's estimate":
            c = None
        return c, busy and not c

    # ------------------------------------------------------------------ Needs / Save
    def mm_new_missing(self):
        f, d = self.mm_new_fields(), self.mm_nd
        out = []
        if not f["name"]:
            out.append("a name")
        if not d["typ"]:
            out.append("a mechanic" if d["cat"] == "Mapping" else "a type")
        if not f["steps"]:
            out.append("one step")
        return out

    def mm_new_build(self):
        """The strat as the page shows it now (not checked)."""
        from . import board as B
        d, f, nw = self.mm_nd, self.mm_new_fields(), self.mm_nw
        base = d["base"]
        s = {k: v for k, v in base.items() if k not in ("origin", "_post")}
        s.update(name=f["name"], category=d["cat"], type=d["typ"], steps=f["steps"], loot=f["loot"])
        if d["effort"] and (d["new"] or d["effort"] != d["effort0"]):
            s["thoughts_per_click"], s["clicks_per_hour"] = MM.EFFORTS[d["effort"]]
        s.setdefault("thoughts_per_click", 3)
        s.setdefault("clicks_per_hour", "Steady")
        handled = set(MM.BUDGETS) | set(PLAY) | {t for g in MM.tag_groups().values() for t in g}
        s["tags"] = ([d["budget"]] if d["budget"] else []) + list(d["play"]) + \
            [t for t in d["tags"] if t in handled] + [t for t in base.get("tags") or [] if t not in handled]
        s["masters"] = {m: list(v) for m, v in d["masters"].items() if v}
        s["items"] = self.mm_new_items()
        more = nw["more"]
        for key, _label, _h in MORE_LISTS + tuple((k, lab, 2) for k, lab in OLD_LISTS):
            if key in more:
                lines = [x.strip() for x in self._mm_val(more[key]).split("\n") if x.strip()]
                if key == "_sources":
                    titles = {x.get("url"): x.get("title") or x.get("url") for x in base.get("sources") or []}
                    s["sources"] = [{"title": titles.get(u, u), "url": u} for u in lines]
                else:
                    s[key] = lines
        s["summary"] = self._mm_val(more["summary"]).strip() or base.get("summary") or (f["steps"][0][:200]
                                                                                        if f["steps"] else "")
        tablets_rx = self.mm_new_made("tablet")["regex"] if d["cards"] else ""
        s["regex"] = self._mm_val(more["regex"]).strip() or (tablets_rx if len(tablets_rx) <= 250 else "")
        tiers = self._mm_val(more["tiers"]).strip()
        if tiers:
            try:
                lo, hi = MM._num_range(tiers.lower().replace("t", ""))
                s["waystone_tiers"] = {"min": int(lo), "max": int(hi)}
            except (TypeError, ValueError):
                s["waystone_tiers"] = tiers                  # (validate says what's wrong)
        elif d["way"] and d["way"].get("tier"):
            s["waystone_tiers"] = {"min": d["way"]["tier"], "max": d["way"]["tier"]}
        else:
            s.pop("waystone_tiers", None)
        if d["league"]:
            s["league"] = MM.league_base(d["league"])
        s["patch"] = (MM.league_version(s.get("league")) if d["new"] else None) or base.get("patch") or \
            MM.league_version(s.get("league")) or "?"
        s["updated"] = time.strftime("%Y-%m-%d")
        if d["new"]:
            s["author"] = (B.signed_in() or {}).get("name") or "me"
            sid = MM.slug("my-" + f["name"])
            have = {m["id"] for m in MM.mine()}
            n = 2
            while sid in have:
                sid, n = MM.slug(f"my-{f['name']}-{n}"), n + 1
            s["id"] = sid
        return MM.tidy(s)

    def mm_new_save(self):
        """Save strat: to Mine (yours), to the board (your Community post), or as a suggestion to its author."""
        from . import board as B
        d = self.mm_nd
        miss = self.mm_new_missing()
        if miss:
            d["msg"] = ("Needs: " + ", ".join(miss), "bad")
            self.mm_new_cv.later(1)
            return None
        out = self.mm_new_build()
        probs = MM.validate(out)
        if probs:
            d["msg"] = ("✕ Not saved: " + probs[0], "bad")
            self.mm_new_cv.later(1)
            return None
        post, base = d.get("post"), d["base"]
        data = {k: v for k, v in out.items() if k not in ("id", "author")}
        if post and d["suggest"]:                        # 2.85.0: someone else's: a suggestion for its author
            from tkinter import simpledialog
            note = getattr(self, "mm_new_note", None) or simpledialog.askstring(
                "Suggest an edit", "What did you change, and why? (the author reads this)", parent=self.root)
            if not note or len(note.strip()) < 3:
                d["msg"] = ("✕ Not sent: say in a few words what you changed and why.", "bad")
                self.mm_new_cv.later(1)
                return None
            ok, res = self.mm_board_send(lambda x: self.bm_send_suggestion(post, x, note.strip()), data)
            if not ok:
                d["msg"] = ("✕ Not sent: " + str(res), "bad")
                self.mm_new_cv.later(1)
                return None
            self.mm_new_close()
            return out
        if post:                                         # your Community post: saved on the board
            ok, res = self.mm_board_send(lambda x: B.update(post["id"], x), data)
            if not ok:
                d["msg"] = ("✕ Not saved: " + str(res), "bad")
                self.mm_new_cv.later(1)
                return None
            self.mm_new_close()
            if isinstance(res, dict) and res.get("pending"):
                self._say("Saved - it's an Official strat, so the change goes live once 2 reviewers approve it "
                          "(History shows it waiting).", 12)
            self.mm_board_fetch(keep=base.get("id", "") + "|board")
            return out
        cost, _busy = self.mm_new_cost()                 # Cost per map: the new strat starts with it
        if cost and str(d.get("cost_sid", "")).startswith("_new"):
            from .stratcost import save_costs
            costs = self.mm_costs()
            costs[out["id"]] = dict(costs.get(d["cost_sid"]) or {}, at=time.time(), league=SETTINGS.get("league"))
            save_costs({k: v for k, v in costs.items() if not str(k).startswith("_new")})
        MM.save_mine([m for m in MM.mine() if m["id"] not in (base.get("id"), out["id"])] + [out])
        self.mm_new_close()
        self.mm_show_mine(out["id"])
        return out

    # ================================================================== drawing
    def _mm_draw_new(self, cv):
        d = getattr(self, "mm_nd", None)
        if not d or not getattr(self, "mm_nw", None):
            return 40
        W = max(cv.winfo_width(), 300)
        narrow = self.mm_narrow(cv)
        pad = 16 if narrow else 24
        side = not narrow and W >= 1100
        SW = 320
        y = 14
        i = cv.text(pad, y, "‹ All strats", F10, fill=cv.c("link"), tags=("back",))
        cv.acts["back"] = self.mm_new_close
        cv.lifts["back"] = [(i, {"fill": cv.c("link")}, {"fill": cv.c("accent")})]
        y += 30
        title = "Suggest an edit" if d["suggest"] else "New strat" if d["new"] else "Edit strat"
        cv.text(pad, y, title, (TH.head_font(None), 18 if narrow else 20), fill=cv.c("text_strong"))
        y += 36 if narrow else 40
        intro = ("Pick what it is, copy in your tablets and waystone, say how it goes. The app makes the regex and "
                 "trade links.")
        y = cv.bottom(cv.text(pad, y, intro, F9, fill=cv.c("text_muted"), width=W - 2 * pad), y + 16) + 16
        mx0, mx1 = pad, (W - pad - SW - 16) if side else W - pad
        top = y
        card = cv.card(mx0, y, mx1, y + 10, None, lift=False)
        yy = y + 24
        parts = (self._nw_part_what, self._nw_part_tablets, self._nw_part_way, self._nw_part_masters,
                 self._nw_part_how)
        for n, part in enumerate(parts, 1):
            if n > 1:
                cv.create_line(mx0 + 24, yy, mx1 - 24, yy, fill=cv.c("border"))
                yy += 24
            yy = part(cv, d, mx0, mx1, yy, n) + 24
        if side:
            yy = self._nw_bottom(cv, d, mx0, mx1, yy)
            cv.coords(card, *_rr_points(mx0, top, mx1, yy, R))
            ys = self._nw_side(cv, d, mx1 + 16, W - pad, top, 1)
            return max(yy, ys) + pad
        cv.coords(card, *_rr_points(mx0, top, mx1, yy, R))
        ys = self._nw_side(cv, d, mx0, mx1, yy + 16, 2 if W >= 640 else 1)
        bot = cv.card(mx0, ys + 16, mx1, ys + 26, None, lift=False)
        yb = self._nw_bottom(cv, d, mx0, mx1, ys + 16 + 8, line=False)
        cv.coords(bot, *_rr_points(mx0, ys + 16, mx1, yb, R))
        return yb + pad

    # ---- pieces
    def _nw_head(self, cv, n, done, title, x0, x1, y, info=None, optional=False):
        """A part's number (✓ when it's done) and title -> x where the title ends."""
        cx, cy = x0 + 30, y + 12
        if done:
            col = cv.c("good")
            cv.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill=TH.mix(cv.c("surface_raised"), col, .2),
                           outline=TH.mix(col, cv.c("surface_raised"), .3))
            cv.text(cx, cy, "✓", ("Segoe UI Symbol", 10, "bold"), fill=col, anchor="center")
        else:
            col = cv.c("accent")
            cv.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill=TH.mix(cv.c("surface_raised"), col, .14),
                           outline=TH.mix(col, cv.c("surface_raised"), .5))
            cv.text(cx, cy, str(n), ("Segoe UI", 9, "bold"), fill=col, anchor="center")
        t = cv.text(x0 + 54, cy, f"{n} · {title}", ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w")
        x = cv.bbox(t)[2]
        if optional:
            x = cv.bbox(cv.text(x + 8, cy + 1, "optional", F9, fill=cv.c("text_muted"), anchor="w"))[2]
        if info:
            x = cv.info(x + 8, cy, f"nw_i{n}", info)
        return x

    def _nw_label(self, cv, x, y, text, info=None, tag=None, width=None):
        """A row's name (small capitals); a long one wraps onto a second line inside its column."""
        if width and cv.tw(text.upper(), FB) > width:
            t = cv.create_text(x, y + 6, text=text.upper(), font=FB, fill=cv.c("text_muted"), anchor="w",
                               width=width)
        else:
            t = cv.text(x, y, text.upper(), FB, fill=cv.c("text_muted"), anchor="w")
        if info:
            cv.info(cv.bbox(t)[2] + 5, y, tag, info)

    def _nw_chip(self, cv, x, y, text, tag, on, fn, role="accent", h=28, tip=None, dim=False):
        """A pill you click: picked = a ✓, the accent edge and a tint (never the color alone). -> its right edge."""
        label = ("✓ " if on else "") + text
        bw = cv.tw(label, F9) + 26
        col = cv.c(role)
        fill = TH.mix(cv.c("surface_raised"), col, .16) if on else cv.c("surface")
        line = col if on else cv.c("border_light")
        b = TH.round_rect(cv, x, y, x + bw, y + h, h // 2 - 1, fill=fill, outline=line, tags=(tag,))
        ink = cv.c("text_strong") if on else cv.c("text_muted") if dim else cv.c("text")
        cv.text(x + bw / 2, y + h / 2, label, F9, fill=ink, anchor="center", tags=(tag,))
        cv.acts[tag] = fn
        cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on else cv.c("text_muted")})]
        if tip:
            cv.tips[tag] = tip
        return x + bw

    def _nw_chips(self, cv, x0, x1, y, chips, h=28):
        """A row of chips that wraps. chips: (text, tag, on, fn[, tip]) -> y under them."""
        x = x0
        for c in chips:
            text, tag, on, fn = c[:4]
            w = cv.tw(("✓ " if on else "") + text, F9) + 26
            if x > x0 and x + w > x1:
                x, y = x0, y + h + 8
            x = self._nw_chip(cv, x, y, text, tag, on, fn, h=h, tip=c[4] if len(c) > 4 else None) + 8
        return y + h

    def _nw_cols(self, x0, x1):
        """(label x, input x, stacked?) - labels to the left, or above in a narrow card."""
        stacked = x1 - x0 < 480
        return x0, (x0 if stacked else x0 + 100), stacked

    def _nw_row(self, cv, x0, x1, y, label, draw, info=None, tag=None, mid=14):
        """One labeled row: draw(ix, y) -> y under it."""
        lx, ix, stacked = self._nw_cols(x0, x1)
        if stacked:
            self._nw_label(cv, lx, y + 6, label, info, tag)
            return draw(ix, y + 18)
        self._nw_label(cv, lx, y + mid, label, info, tag, width=None if info else ix - lx - 8)
        return draw(ix, y)

    def _nw_place(self, cv, w, x, y, width, height):
        cv.create_window(x, y, window=w, anchor="nw", width=max(40, int(width)), height=int(height))

    def _nw_check(self, cv, x, y, on, tags):
        """A tick box: ✓ in it when on."""
        col = cv.c("accent")
        TH.round_rect(cv, x, y, x + 16, y + 16, 3, fill=col if on else cv.c("surface"),
                      outline=col if on else cv.c("border_light"), tags=tags)
        if on:
            from .style import text_on
            cv.text(x + 8, y + 8, "✓", ("Segoe UI Symbol", 9, "bold"), fill=text_on(col), anchor="center", tags=tags)

    def _nw_dashed(self, cv, x0, y0, x1, y1):
        return TH.round_rect(cv, x0, y0, x1, y1, 8, fill=cv.c("surface"), outline=cv.c("border_light"), dash=(4, 3))

    # ---- 1 What it is
    def _nw_part_what(self, cv, d, x0, x1, y, n):
        f = self.mm_new_fields()
        done = bool(f["name"] and d["typ"])
        self._nw_head(cv, n, done, "What it is", x0, x1, y)
        cx, cr = x0 + 54, x1 - 24
        y += 40
        nw = self.mm_nw

        def name(ix, yy):
            self._nw_place(cv, nw["name"], ix, yy, cr - ix, 34)
            return yy + 34
        y = self._nw_row(cv, cx, cr, y, "Name", name, mid=17) + 14

        def league(ix, yy):
            lg = d["league"] or (MM.league_of(d["base"]) if not d["new"] else "")
            text = MM.league_text(lg) if lg else "No league set"
            where = ("from your league setting" if d["new"] and lg else "from the strat" if d["base"].get("league")
                     else "from its game version" if lg else "Settings › General › League")
            bw = cv.tw(text, F10) + 24
            TH.round_rect(cv, ix, yy, ix + bw, yy + 30, 6, fill=cv.c("surface_sunken"), outline=cv.c("border"))
            cv.text(ix + 12, yy + 15, text, F10, fill=cv.c("text") if lg else cv.c("text_muted"), anchor="w")
            cv.text(ix + bw + 10, yy + 15, cv.fit(where, F9, max(40, cr - ix - bw - 10)), F9,
                    fill=cv.c("text_muted"), anchor="w")
            return yy + 30
        y = self._nw_row(cv, cx, cr, y, "League", league, mid=15, tag="nw_league_i",
                         info="Your league from Settings, with its game version when the app knows it. Find shows "
                              "your league's strats first (League ▾ › All leagues shows every one).") + 14

        def cats(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(c, f"nw_cat_{c}", d["cat"] == c,
                                                    lambda c=c: self.mm_new_pick("cat", c)) for c in MM.CATEGORIES])
        y = self._nw_row(cv, cx, cr, y, "Category", cats) + 14
        y = self._nw_row(cv, cx, cr, y, "Mechanic" if d["cat"] == "Mapping" else "Type",
                         lambda ix, yy: self._nw_mechs(cv, d, ix, cr, yy), mid=14) + 14

        def effort(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(w, f"nw_eff_{w}", d["effort"] == w,
                                                    lambda w=w: self.mm_new_pick("effort", w)) for w in MM.EFFORTS])
        y = self._nw_row(cv, cx, cr, y, "Effort", effort, tag="nw_eff_i",
                         info="How much thinking and clicking a run takes: Easy, Moderate or Hard. Find's Effort "
                              "filter uses it.") + 14

        def budget(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(w, f"nw_bud_{i}", d["budget"] == t,
                                                    lambda t=t: self.mm_new_pick("budget", t), t)
                                                   for i, (w, t) in enumerate(MM.BUDGET_CHIPS)])
        y = self._nw_row(cv, cx, cr, y, "Budget", budget) + 14

        def play(ix, yy):
            chips = [("Any", "nw_play_any", not d["play"], lambda: self.mm_new_pick("play", None))]
            chips += [(t, f"nw_play_{i}", t in d["play"], lambda t=t: self.mm_new_pick("play", t))
                      for i, t in enumerate(PLAY)]
            return self._nw_chips(cv, ix, cr, yy, chips)
        return self._nw_row(cv, cx, cr, y, "Play style", play)

    def _nw_mechs(self, cv, d, x0, x1, y):
        """The category's types as cards: the mechanic's tablet picture over its word (no picture: the word)."""
        types = list(MM.TAXONOMY.get(d["cat"], ()))
        types.sort(key=lambda t: t not in MM.MECH_TABLET)
        mapping = d["cat"] == "Mapping"
        w, h, gap = (86, 66, 8) if mapping else (0, 30, 8)
        if not mapping:
            return self._nw_chips(cv, x0, x1, y, [(t, f"nw_typ_{i}", d["typ"] == t,
                                                   lambda t=t: self.mm_new_pick("typ", t)) for i, t in enumerate(types)])
        x = x0
        for i, t in enumerate(types):
            if x > x0 and x + w > x1:
                x, y = x0, y + h + gap
            tag = f"nw_typ_{i}"
            on = d["typ"] == t
            col = cv.c("accent")
            fill = TH.mix(cv.c("surface_raised"), col, .14) if on else cv.c("surface")
            line = col if on else cv.c("border_light")
            b = TH.round_rect(cv, x, y, x + w, y + h, 6, fill=fill, outline=line, tags=(tag,))
            word = ("✓ " if on else "") + t
            base = MM.MECH_TABLET.get(t)
            got = cv.icon(base, x + w / 2, y + 22, 30, anchor="center", tags=(tag,)) if base else None
            ty = y + h - 13 if got is not None else y + h / 2
            if got is not None:
                cv.text(x + w / 2, ty, cv.fit(word, F9, w - 8), F9,
                        fill=cv.c("text_strong") if on else cv.c("text"), anchor="center", tags=(tag,))
            else:                                       # (no picture: the word alone, on two lines if it needs)
                cv.create_text(x + w / 2, ty, text=word, font=F9, width=w - 10, justify="center", anchor="center",
                               fill=cv.c("text_strong") if on else cv.c("text"), tags=(tag,))
            cv.acts[tag] = lambda t=t: self.mm_new_pick("typ", t)
            cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on else cv.c("text_muted")})]
            if got is not None and cv.tw(word, F9) > w - 8:
                cv.tips[tag] = t
            x += w + gap
        return y + h

    # ---- 2 / 3 your tablets, your waystone
    def _nw_keys_line(self, cv, x, y, before, after, x1):
        """"Hover ... press [Ctrl] [Alt] [C]. Then ..." - the keys as key caps."""
        x = cv.bbox(cv.text(x, y, before, F9, fill=cv.c("text_muted"), anchor="w"))[2] + 6
        for k in ("Ctrl", "Alt", "C"):
            kw = cv.tw(k, ("Segoe UI", 8)) + 10  # token-ok (canvas)
            TH.round_rect(cv, x, y - 9, x + kw, y + 9, 3, fill=cv.c("surface_sunken"), outline=cv.c("border_light"))
            cv.text(x + kw / 2, y, k, ("Segoe UI", 8), fill=cv.c("text"), anchor="center")  # token-ok (canvas)
            x += kw + 3
        cv.text(x + 2, y, cv.fit(after, F9, max(40, x1 - x - 2)), F9, fill=cv.c("text_muted"), anchor="w")

    def _nw_card(self, cv, which, c, x0, x1, y, h=None):
        """A copied item: its picture, name and uses, ✕, and a row per mod with a tick box. -> its height."""
        kind = c["kind"]
        cv.card(x0, y, x1, y + (h or 10), None, lift=False)
        card_id = cv.find_all()[-1]
        got = cv.icon(c["base"], x0 + 12, y + 12, 32)
        tx = x0 + 12 + (40 if got is not None else 0)
        rm = f"nw_rm_{which}"
        cv.button(x1 - 10, y + 10, "✕", rm, lambda: self.mm_new_remove(which), anchor="e", h=28, w=30,
                  tip=f"Remove this {kind}")
        title = c.get("name") or c["base"]
        if c.get("count", 1) > 1:
            title += f" ×{c['count']}"
        cv.text(tx, y + 18, cv.fit(title, ("Segoe UI", 10, "bold"), x1 - 48 - tx), ("Segoe UI", 10, "bold"),
                fill=cv.c("text_strong"), anchor="w")
        bits = ([f"{c['uses']} uses"] if kind == "tablet" and c.get("uses") else []) + \
            ([c["rarity"]] if kind == "waystone" and c.get("rarity") else []) + \
            (["copied from the game"] if c.get("copied") else ["from the strat"])
        cv.text(tx, y + 36, cv.fit(" · ".join(bits), F9, x1 - 48 - tx), F9, fill=cv.c("text_muted"), anchor="w")
        yy = y + 54
        if not c["mods"]:
            yy = cv.bottom(cv.text(x0 + 12, yy, "No mods - a white " + kind + ": searched by its base.", F9,
                                   fill=cv.c("text_muted"), width=x1 - x0 - 24), yy + 14) + 10
        for i, line in enumerate(c["mods"]):
            tag = f"nw_m_{which}_{i}"
            on = line in c["ticked"]
            tid = cv.text(x0 + 38, yy + 4, line, F9, fill=cv.c("text") if on else cv.c("text_soft", "text"),
                          width=x1 - x0 - 50, tags=(tag,))
            b = cv.bottom(tid, yy + 18) + 4
            bg = TH.round_rect(cv, x0 + 6, yy - 2, x1 - 6, b, 4,
                               fill=TH.mix(cv.c("surface_raised"), cv.c("accent"), .10) if on else cv.c("surface_raised"),
                               outline="", tags=(tag,))
            cv.tag_lower(bg, tid)
            self._nw_check(cv, x0 + 14, yy + 2, on, (tag,))
            cv.acts[tag] = lambda line=line: self.mm_new_tick(which, line)
            cv.lifts[tag] = [(bg, {"fill": cv.itemcget(bg, "fill")},
                              {"fill": TH.mix(cv.c("surface_raised"), cv.c("accent"), .16 if on else .06)})]
            yy = b + 4
        yy += 8
        cv.coords(card_id, *_rr_points(x0, y, x1, y + max(h or 0, yy - y), R))
        return yy - y, card_id

    def _nw_waiting(self, cv, x0, x1, y, text, base=None):
        self._nw_dashed(cv, x0, y, x1, y + 44)
        x = x0 + 14
        if base and cv.icon(base, x, y + 22, 22, anchor="w") is not None:
            x += 30
        cv.text(x, y + 22, cv.fit(text, F9, x1 - x - 14), F9, fill=cv.c("text_muted"), anchor="w")
        return y + 44

    def _nw_made(self, cv, kind, x0, x1, y):
        """Made for you: the stash regex (Copy regex) and the Trade Site search, with what they hold."""
        m = self.mm_new_made(kind)
        box = self._nw_dashed(cv, x0, y, x1, y + 10)
        yy = y + 14
        lab = cv.text(x0 + 14, yy + 15, "MADE FOR YOU", FB, fill=cv.c("text_muted"), anchor="w")
        rx0 = cv.bbox(lab)[2] + 12
        bw = cv.tw("Copy regex", F10) + 32
        narrow = x1 - rx0 - bw - 30 < 160
        rx1 = (x1 - 14) if narrow else (x1 - 14 - bw - 8)
        TH.round_rect(cv, rx0, yy, rx1, yy + 30, 4, fill=cv.c("surface_sunken"), outline=cv.c("border"))
        if m["regex"]:
            cv.text(rx0 + 8, yy + 15, cv.fit(m["regex"], ("Consolas", 9), rx1 - rx0 - 16), ("Consolas", 9),
                    fill=cv.c("good"), anchor="w", tags=(f"nw_rx_{kind}",))
            cv.tips[f"nw_rx_{kind}"] = m["regex"]
        else:
            cv.text(rx0 + 8, yy + 15, "tick a mod above" if (self.mm_nd["cards"] if kind == "tablet" else
                                                              self.mm_nd["way"]) else "copy one first",
                    F9, fill=cv.c("text_muted"), anchor="w")
        tip_rx = ("Copy the stash search. In game: Ctrl+V in the stash search." if m["regex"]
                  else "Tick a mod first")
        yy += 38
        bx = x0 + 14
        if not narrow:
            cv.button(rx1 + 8, yy - 38, "Copy regex", f"nw_copy_{kind}", lambda: self.mm_new_copy(kind),
                      enabled=bool(m["regex"]), h=30, tip=tip_rx)
        else:
            _a, bx = cv.button(bx, yy, "Copy regex", f"nw_copy_{kind}", lambda: self.mm_new_copy(kind),
                               enabled=bool(m["regex"]), h=30, tip=tip_rx)
            bx += 8
        _a, tx1 = cv.button(bx, yy, "Trade Site ↗", f"nw_trade_{kind}", lambda: self.mm_new_trade(kind),
                            enabled=bool(m["url"]), h=30,
                            tip="Opens the trade site in your browser: " + (m["caption"] or "copy one first"))
        cv.text(tx1 + 10, yy + 15, cv.fit(m["caption"], F9, max(40, x1 - tx1 - 24)), F9, fill=cv.c("text_muted"),
                anchor="w")
        yy += 30 + 14
        cv.coords(box, *_rr_points(x0, y, x1, yy, 8))
        return yy

    def _nw_part_tablets(self, cv, d, x0, x1, y, n):
        cards = d["cards"]
        done = bool(cards) and all(c["ticked"] or not c["mods"] for c in cards)
        self._nw_head(cv, n, done, "Your tablets", x0, x1, y,
                      info="Copy each tablet you put in your map device. Tick the mods that matter: the regex and "
                           "the trade search use those. The app reads the copy once, when you press the key.")
        cv.text(x1 - 24, y + 12, f"{len(cards)} of {MM.TABLETS_MAX}", F9, fill=cv.c("text_muted"), anchor="e",
                tags=("nw_tcount",))
        cv.tips["nw_tcount"] = f"In your map device: up to {MM.TABLETS_MAX} tablets a map."
        cx, cr = x0 + 54, x1 - 24
        y += 40
        self._nw_keys_line(cv, cx, y, "Hover a tablet in game and press", ". Then tick the mods that matter.", cr)
        y += 22
        cols = 2 if cr - cx >= 520 else 1
        gap = 12
        cw = (cr - cx - (cols - 1) * gap) / cols
        for r0 in range(0, len(cards), cols):
            drawn = []
            for j, i in enumerate(range(r0, min(r0 + cols, len(cards)))):
                cx0 = cx + j * (cw + gap)
                drawn.append((cx0,) + self._nw_card(cv, i, cards[i], cx0, cx0 + cw, y))
            hmax = max(h for _x, h, _id in drawn)
            for cx0, h, cid in drawn:                   # (a row's cards share its height)
                if h < hmax:
                    cv.coords(cid, *_rr_points(cx0, y, cx0 + cw, y + hmax, R))
            y += hmax + gap
        if len(cards) < MM.TABLETS_MAX:
            y = self._nw_waiting(cv, cx, cr, y, ("Waiting for your next tablet… " if cards else
                                                 "Waiting for your first tablet… ") + f"(up to {MM.TABLETS_MAX})",
                                 MM.GENERIC_TABLET) + gap
        else:
            cv.text(cx, y + 8, f"{MM.TABLETS_MAX} of {MM.TABLETS_MAX}: remove one (✕) to copy another.", F9,
                    fill=cv.c("text_muted"), anchor="w")
            y += 26
        if cards:
            y = self._nw_made(cv, "tablet", cx, cr, y)
        return y

    def _nw_part_way(self, cv, d, x0, x1, y, n):
        c = d["way"]
        self._nw_head(cv, n, bool(c), "Your waystone", x0, x1, y)
        cx, cr = x0 + 54, x1 - 24
        y += 40
        if not c:
            self._nw_keys_line(cv, cx, y, "Hover your waystone in game and press", ". Then tick what matters.", cr)
            y += 22
            return self._nw_waiting(cv, cx, cr, y, "Waiting for your waystone…")
        wx1 = cr if cr - cx < 560 else cx + (cr - cx) * 0.72
        y += self._nw_card(cv, "way", c, cx, wx1, y)[0] + 12
        return self._nw_made(cv, "waystone", cx, cr, y)

    # ---- 4 Atlas masters
    def _nw_part_masters(self, cv, d, x0, x1, y, n):
        picked = MM.masters_count(d["masters"])
        total = MM.MASTER_PICKS * len(MM.MASTERS)
        self._nw_head(cv, n, picked > 0, "Atlas masters", x0, x1, y, optional=True,
                      info=f"Up to {MM.MASTER_PICKS} choices of each master's 12 - the ones you run this strat with. "
                           "They show on the strat.")
        cv.button(x1 - 24, y - 3, "Clear", "nw_mclear", self.mm_new_masters_clear, anchor="e", h=30,
                  enabled=picked > 0, tip="Untick every master's choices" if picked else "Nothing picked yet")
        cx, cr = x0 + 54, x1 - 24
        y += 40
        cols = 6 if cr - cx >= 620 else 4 if cr - cx >= 420 else 3
        gap = 6
        for m, md in MM.MASTERS.items():
            col = cv.c(md["role"])
            mine = d["masters"].get(m) or []
            full = len(mine) >= MM.MASTER_PICKS
            top = y
            box = cv.card(cx, y, cr, y + 10, None, lift=False)
            cv.create_rectangle(cx, y + 2, cx + 3, y + 10, fill=col, outline="", tags=("edge",))
            edge = cv.find_all()[-1]
            cv.create_oval(cx + 14, y + 16, cx + 22, y + 24, fill=col, outline="")
            cv.text(cx + 30, y + 20, m, ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="w")
            cnt = f"✓ {len(mine)} of {MM.MASTER_PICKS}" if full else f"{len(mine)} of {MM.MASTER_PICKS}"
            cv.text(cr - 14, y + 20, cnt, F9, fill=cv.c("good") if full else cv.c("text_muted"), anchor="e")
            yy = y + 38
            cw = (cr - cx - 24 - (cols - 1) * gap) / cols
            for i, ch in enumerate(md["choices"]):
                gx = cx + 12 + (i % cols) * (cw + gap)
                gy = yy + (i // cols) * (40 + gap)
                tag = f"nw_ms_{list(MM.MASTERS).index(m)}_{i}"
                on = ch in mine
                fill = TH.mix(cv.c("surface_raised"), col, .2) if on else cv.c("surface")
                line = col if on else cv.c("border")
                b = TH.round_rect(cv, gx, gy, gx + cw, gy + 40, 4, fill=fill, outline=line, tags=(tag,))
                cv.create_text(gx + cw / 2, gy + 20, text=("✓ " if on else "") + ch, font=("Segoe UI", 8 if cw < 96 else 9),
                               fill=cv.c("text_strong") if on else cv.c("text_muted") if full else cv.c("text"),
                               anchor="center", justify="center", width=cw - 8, tags=(tag,))
                cv.acts[tag] = lambda m=m, ch=ch: self.mm_new_master(m, ch)
                cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on or not full else cv.c("border")})]
                if full and not on:
                    cv.tips[tag] = f"{MM.MASTER_PICKS} of {MM.MASTER_PICKS} used - untick one first"
            rows = -(-len(md["choices"]) // cols)
            y = yy + rows * (40 + gap) + 6
            cv.coords(box, *_rr_points(cx, top, cr, y, 6))
            cv.coords(edge, cx, top + 3, cx + 3, y - 3)
            cv.tag_raise(edge)
            y += 10
        return y - 10

    # ---- 5 How it goes
    def _nw_part_how(self, cv, d, x0, x1, y, n):
        f = self.mm_new_fields()
        self._nw_head(cv, n, bool(f["steps"]), "How it goes", x0, x1, y)
        cx, cr = x0 + 54, x1 - 24
        y += 40
        steps = self.mm_nw["steps"]
        for i, e in enumerate(steps, 1):
            ccx = cx + 10
            if i < len(steps):
                cv.create_line(ccx, y + 26, ccx, y + 34 + 8 + 8, fill=cv.c("border"))
            cv.create_oval(ccx - 9, y + 8, ccx + 9, y + 26, fill=cv.c("surface_sunken"), outline=cv.c("border"))
            cv.text(ccx, y + 17, str(i), ("Segoe UI", 8, "bold"), fill=cv.c("text_muted"), anchor="center")  # token-ok
            self._nw_place(cv, e, cx + 30, y, cr - cx - 30, 34)
            y += 42
        y += 8

        def loot(ix, yy):
            self._nw_place(cv, self.mm_nw["loot"], ix, yy, cr - ix, 34)
            return yy + 34
        y = self._nw_row(cv, cx, cr, y, "Loot to sell", loot, mid=17) + 18
        tag = "nw_more"
        on = d["more"]
        t = cv.text(cx, y + 8, ("▾ " if on else "▸ ") + "More details", ("Segoe UI", 10, "bold"), fill=cv.c("text"),
                    anchor="w", tags=(tag,))
        cv.text(cv.bbox(t)[2] + 10, y + 8, cv.fit("summary, requirements, tips, risks, sources, regex, tags",
                                                  F9, max(40, cr - cv.bbox(t)[2] - 10)),
                F9, fill=cv.c("text_muted"), anchor="w", tags=(tag,))
        cv.acts[tag] = self.mm_new_more
        cv.lifts[tag] = [(t, {"fill": cv.c("text")}, {"fill": cv.c("accent")})]
        y += 22
        if not on:
            return y
        y += 10
        more = self.mm_nw["more"]
        rows = [("summary", "Summary", 1), ("regex", "Stash regex", 1), ("tiers", "Waystone tiers", 1)] + \
            [(k, lab, h) for k, lab, h in MORE_LISTS] + [(k, lab, 2) for k, lab in OLD_LISTS if k in more]
        for key, label, h in rows:
            hh = 34 if h == 1 else 14 + 19 * h

            def put(ix, yy, key=key, hh=hh):
                self._nw_place(cv, more[key], ix, yy, cr - ix, hh)
                return yy + hh
            y = self._nw_row(cv, cx, cr, y, label, put, mid=17) + 10
        groups = [(g, t) for g, t in MM.tag_groups().items() if g not in ("Budget", "Play style")]
        for g, tags in groups:
            def chips(ix, yy, tags=tags, g=g):
                return self._nw_chips(cv, ix, cr, yy, [(t, f"nw_tag_{g}_{i}", t in d["tags"],
                                                        lambda t=t: self.mm_new_pick("tag", t))
                                                       for i, t in enumerate(tags)], h=26)
            y = self._nw_row(cv, cx, cr, y, g, chips, mid=13) + 10
        return y

    def mm_new_more(self):
        self.mm_nd["more"] = not self.mm_nd["more"]
        self.mm_new_cv.later(1)

    # ---- the bottom: Cancel · Needs · Save strat
    def _nw_bottom(self, cv, d, x0, x1, y, line=True):
        if line:
            cv.create_line(x0 + 24, y, x1 - 24, y, fill=cv.c("border"))
            y += 16
        miss = self.mm_new_missing()
        label = "Send suggestion" if d["suggest"] else "Save strat"
        cv.button(x0 + 24, y, "Cancel", "nw_cancel", self.mm_new_close, h=36,
                  tip="Back without saving")
        sx0, _sx1 = cv.button(x1 - 24, y, label, "nw_save", self.mm_new_save, kind="primary", enabled=not miss,
                              anchor="e", h=36,
                              tip=("Needs: " + ", ".join(miss)) if miss else
                              ("Saves it to Mine (on this PC until you post it)" if not d.get("post") else
                               "Saves it on the community board"))
        msg = d.get("msg")
        if msg:
            text, role = msg
        elif miss:
            text, role = "Needs: " + ", ".join(miss), "text_muted"
        else:
            text, role = "✓ Ready", "good"
        cv.text(sx0 - 14, y + 18, cv.fit(text, F9, max(60, sx0 - x0 - 140)), F9, fill=cv.c(role), anchor="e",
                tags=("nw_needs",))
        return y + 36 + 20

    # ---- the side panel: how it will look in Find, Cost per map, Profit per hour, Checklist
    def _nw_side(self, cv, d, x0, x1, y, cols=1):
        parts = (self._nw_side_find, self._nw_side_cost, self._nw_side_profit, self._nw_side_check)
        if cols == 1:
            for p in parts:
                y = p(cv, d, x0, x1, y) + 12
            return y - 12
        gap = 12
        cw = (x1 - x0 - gap) / 2
        for r in range(0, len(parts), 2):
            ys = [p(cv, d, x0 + j * (cw + gap), x0 + j * (cw + gap) + cw, y) for j, p in enumerate(parts[r:r + 2])]
            y = max(ys) + gap
        return y - gap

    def _nw_side_box(self, cv, x0, x1, y, title, info=None, tag=None):
        card = cv.card(x0, y, x1, y + 10, None, lift=False)
        t = cv.text(x0 + 16, y + 20, title.upper(), FB, fill=cv.c("text_muted"), anchor="w")
        if info:
            cv.info(cv.bbox(t)[2] + 6, y + 20, tag, info)
        return card, y + 36

    def _nw_side_find(self, cv, d, x0, x1, y):
        card, yy = self._nw_side_box(cv, x0, x1, y, "How it will look in Find")
        f = self.mm_new_fields()
        s = {"type": d["typ"] or "", "category": d["cat"], "tags": [d["budget"]] if d["budget"] else []}
        TH.round_rect(cv, x0 + 12, yy, x1 - 12, yy + 58, 6, fill=cv.c("surface"), outline=cv.c("border"))
        got = cv.icon(MM.tablet_of(s), x0 + 22, yy + 29, 30, anchor="w")
        tx = x0 + 22 + (38 if got is not None else 0)
        cost, _b = self.mm_new_cost()
        val = f"{MM.short_div(cost['value'])} div" if cost else "-"
        vx = x1 - 22
        cv.text(vx, yy + 20, val, ("Segoe UI", 10, "bold"), fill=cv.c("money"), anchor="e")
        cv.text(vx, yy + 38, "a map", F9, fill=cv.c("text_muted"), anchor="e")
        room = vx - max(cv.tw(val, ("Segoe UI", 10, "bold")), 40) - 10 - tx
        cv.text(tx, yy + 18, cv.fit(f["name"] or "Your strat's name", ("Segoe UI", 9, "bold"), room),
                ("Segoe UI", 9, "bold"), fill=cv.c("text_strong") if f["name"] else cv.c("text_muted"), anchor="w")
        x = tx
        if d["typ"]:
            x = self._mm_mech_chip(cv, tx, yy + 30, s) if x + 60 < tx + room else x
        b = d["budget"]
        if b and x + cv.tw(b, F9) + 24 < tx + room:
            cv.chip(x + 6, yy + 30, b)
        yy += 58 + 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _nw_side_cost(self, cv, d, x0, x1, y):
        how = ("What goes in your map device each map, at today's prices on the trade site (the cheapest real "
               "offer of each item): the waystone, plus each tablet's price ÷ its uses. Checked a moment after you "
               "copy or tick.")
        card, yy = self._nw_side_box(cv, x0, x1, y, "Cost per map", how, "nw_cost_i")
        cost, busy = self.mm_new_cost()
        num = (TH.head_font(None, "num"), 20)
        cv.text(x0 + 16, yy, f"{MM.short_div(cost['value'])} div" if cost else "-", num, fill=cv.c("text_strong"),
                tags=("nw_cost",))
        yy += 36
        if cost:
            line = f"{cost['sum']} (worked out from your copies)"
            cv.tips["nw_cost"] = f"{cost['sum']}. {cost['how']}"
        elif busy:
            line = "checking the trade site…"
        elif d["cards"] or d["way"]:
            line = ("needs your league in Settings to check the trade site" if not SETTINGS.get("league") else
                    "no price found yet")
        else:
            line = "Copy your waystone and tablets: their prices today add up here."
        yy = cv.bottom(cv.text(x0 + 16, yy, line, F9, fill=cv.c("text_muted"), width=x1 - x0 - 32), yy + 14) + 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _nw_side_profit(self, cv, d, x0, x1, y):
        card, yy = self._nw_side_box(cv, x0, x1, y, "Profit per hour")
        text = "Comes from runs, not a guess: run it with Run this strat and it fills in."
        old = d["base"].get("est_profit")
        if old and MM.money_edit(old):
            text += f" Its older estimate stays: {MM.money_edit(old)} an hour."
        yy = cv.bottom(cv.text(x0 + 16, yy, text, F9, fill=cv.c("text"), width=x1 - x0 - 32), yy + 14) + 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _nw_side_check(self, cv, d, x0, x1, y):
        card, yy = self._nw_side_box(cv, x0, x1, y, "Checklist")
        f = self.mm_new_fields()
        n_t = len(d["cards"])
        pts = MM.masters_count(d["masters"])
        rows = ((bool(f["name"] and d["typ"]), "What it is"),
                (bool(d["cards"]) and all(c["ticked"] or not c["mods"] for c in d["cards"]),
                 f"Tablets · {n_t} copied"),
                (bool(d["way"]), "Waystone"),
                (pts > 0, f"Atlas masters · {pts} of {MM.MASTER_PICKS * len(MM.MASTERS)} points"),
                (bool(f["steps"]), f"How it goes · {len(f['steps'])} step{'s' if len(f['steps']) != 1 else ''}"))
        for ok, word in rows:
            cv.text(x0 + 16, yy + 8, ("✓ " if ok else "○ ") + word, F9, fill=cv.c("good") if ok else cv.c("text"),
                    anchor="w")
            yy += 22
        yy += 8
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy
