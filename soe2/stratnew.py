"""Farming Strategies › New strat (3.0.6, the approved mockup v2 - it replaces the Add my own form: owner "so hard to
understand"). One page, drawn on a canvas in the Farming Strategies page like an opened strat (stratview.StratCanvas),
in five numbered parts:

  1 What you farm      name, activity (Mapping / Bossing), mechanics (tablet tiles, several: the first is MAIN, the
                       rest ALSO), map type (City adds a tablet slot), map content, bosses, effort, budget, play style
  2 In your map device the waystone and up to 4 tablets as slots: hover one in game, Ctrl+Alt+C - it lands in the next
                       slot; the picked one's mods are toggles; Made for you: a stash regex for the ticked mods, Copy
                       regex and a Trade Site search. A 4th tablet ticks City (only Cities have a 4th slot)
  3 Atlas master       one master a strat (three tabs), up to 4 of its 12 choices in the game's 3 × 4 grid
  4 How it goes        numbered steps (a new one appears when the last is filled), loot to sell as chips
  5 Notes              tips, risks, the source - optional
A side panel shows how it shows in Find, Cost per map (worked out from the copies at today's prices - a sum, one
hover from how) and the parts. Cancel (ghost) and Save strat (the one orange button, grayed until it's ready -
"Needs: ..." says what's missing). An older strat's other fields (requirements, other setup, its stash search ...) are
kept as they are; the opened strat shows them under From the author.

GGG policy: the copies come only through the app's one clipboard read per copy key press (clipread -> clip_read_once
-> mm_new_take_clip, while this page shows). Nothing here reads the clipboard or the screen, and no timer reads."""
import re
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
ALSO = MM.TAG_GROUPS["Also uses"]                 # the mechanics: the first picked is the main one, the rest Also uses
MECH_ORDER = ("Breach", "Delirium", "Ritual", "Expedition", "Abyss", "Essence", "Temple", "Overseer", "Strongbox",
              "Rogue Exiles", "Shrines")              # (the mockup's order: the tablets first)
MAP_TYPES = MM.TAG_GROUPS["Map type"]
BOSS_TAGS = tuple(tag for _w, tag in MM.BOSS_CHIPS)
F9, F10, FB = ("Segoe UI", 9), ("Segoe UI", 10), ("Segoe UI", 8, "bold")  # token-ok (canvas)
URL = re.compile(r"https?://\S+")


def _map_content():
    g = MM.content_groups()
    return tuple(g.get("Map content") or MM.CONTENT["Map content"])


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
        typ = s.get("type") if MM.is_farming(s) else None
        mechs = ([typ] if typ in ALSO else []) + [t for t in tags if t in ALSO and t != typ]
        content = _map_content()
        handled = set(MM.BUDGETS) | set(PLAY) | set(ALSO) | set(MAP_TYPES) | set(BOSS_TAGS) | set(content)
        self.mm_nd = d = {
            "base": s, "new": new, "suggest": bool(suggest), "post": s.get("_post"),
            "cat": s.get("category") if s.get("category") in MM.TAXONOMY else "Mapping",
            "mechs": mechs, "typ_keep": typ if typ and typ not in ALSO else None,
            "bosses": [t for t in tags if t in BOSS_TAGS], "maptype": [t for t in tags if t in MAP_TYPES],
            "content": [t for t in tags if t in content], "city_auto": False,
            "keep_tags": [t for t in tags if t not in handled],
            "effort": "Easy" if new else MM.effort_of(s), "effort0": None if new else MM.effort_of(s),
            "budget": MM.budget_of(s), "play": [t for t in tags if t in PLAY],
            "cards": cards[:MM.TABLETS_MAX], "way": way, "sel": None,
            "others": [it for it in items if it.get("kind") not in ("tablet", "waystone")],
            "masters": {k: list(v) for k, v in (s.get("masters") or {}).items() if v},
            "mtab": MM.master_of(s.get("masters"))[0] or next(iter(MM.MASTERS)),
            "loot": list(s.get("loot") or []),
            "league": s.get("league") or own, "msg": None,
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

    # ------------------------------------------------------------------ the typed fields (real entries on the canvas)
    def _mm_new_entry(self, value="", hint="", lines=0):
        """A field drawn on the page: an Entry, or (lines) a Text that grows with its lines; hint shows while empty."""
        cv = self.mm_new_cv
        kw = dict(bg=C["odd"], fg=C["text"], insertbackground=C["text"], relief="flat", highlightthickness=1,
                  highlightbackground=C["line"], highlightcolor=C["accent"], font=F10)
        if lines:
            w = tk.Text(cv, height=1, wrap="word", padx=8, pady=8, undo=True, bd=0, **kw)
            w.insert("1.0", value)
            w.bind("<<Modified>>", lambda e: (w.edit_modified(False), self._mm_new_typed()))
            w.edit_modified(False)

            def empty():
                return not w.get("1.0", "end-1c")
        else:
            var = tk.StringVar(value=value)
            w = tk.Entry(cv, textvariable=var, bd=7, **kw)          # (the border is the field's inner padding)
            w.var = var
            var.trace_add("write", lambda *_a: self._mm_new_typed())

            def empty():
                return not var.get()
        if hint:
            ph = tk.Label(cv, text=hint, bg=C["odd"], fg=C["muted"], font=F10)
            ph.bind("<Button-1>", lambda e: w.focus_set())

            def show(*_a):
                try:
                    if not empty() or self.root.focus_get() is w:
                        ph.place_forget()
                    else:
                        ph.place(in_=w, x=7 if not lines else 8, rely=0.5, anchor="w")
                except (tk.TclError, KeyError):
                    pass
            for ev in ("<FocusIn>", "<FocusOut>", "<Map>", "<KeyRelease>"):
                w.bind(ev, show, add="+")
            w.hint = ph
        return w

    def _mm_new_widgets(self, s):
        cv = self.mm_new_cv
        for w in list(cv.winfo_children()):
            w.destroy()
        nw = self.mm_nw = {"name": self._mm_new_entry(s.get("name", ""), "e.g. Delirium into Simulacrums")}
        nw["steps"] = [self._mm_new_entry(x) for x in s.get("steps") or []]
        nw["steps"].append(self._mm_new_entry("", "Next step…"))
        nw["loot"] = self._mm_new_entry("", "Add an item…")
        nw["loot"].bind("<Return>", lambda e: self.mm_new_loot_add())
        nw["loot"].bind("<FocusOut>", lambda e: self.mm_new_loot_add(), add="+")
        src = (s.get("sources") or [{}])[0]
        stext = " ".join(x for x in (src.get("url", ""), src.get("title", "") if src.get("title") != src.get("url")
                                     else "") if x)
        nw["tips"] = self._mm_new_entry("\n".join(s.get("tips") or []), "One per line", lines=1)
        nw["risks"] = self._mm_new_entry("\n".join(s.get("risks") or []), "What can go wrong", lines=1)
        nw["source"] = self._mm_new_entry(stext, "Link to the guide or video, and its author")
        nw["hand_q"] = self._mm_new_entry("", "Search mods…")                      # the by-hand picker
        nw["hand_min"] = self._mm_new_entry("", "min")
        nw["hand_props"] = {name: self._mm_new_entry("", "min") for name in MM.hand_props()}

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
            if self.mm_nd.get("hand"):
                self._mm_hand_sync()
        self.mm_new_cv.later(180)

    def _mm_val(self, w):
        try:
            return w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.var.get()
        except tk.TclError:
            return ""

    def mm_new_fields(self):
        """-> {"name", "steps", "tips", "risks", "source"} as typed now."""
        nw = self.mm_nw
        lines = lambda w: [x.strip() for x in self._mm_val(w).split("\n") if x.strip()]     # noqa: E731
        return {"name": self._mm_val(nw["name"]).strip(),
                "steps": [v.strip() for v in (self._mm_val(e) for e in nw["steps"]) if v.strip()],
                "tips": lines(nw["tips"]), "risks": lines(nw["risks"]),
                "source": self._mm_val(nw["source"]).strip()}

    def mm_new_loot_add(self, text=None):
        """Add an item… (Enter): a Loot to sell chip."""
        nw, d = self.mm_nw, self.mm_nd
        text = (self._mm_val(nw["loot"]) if text is None else text).strip()
        if not text:
            return None
        for x in [x.strip() for x in text.replace(";", ",").split(",") if x.strip()]:
            if x not in d["loot"]:
                d["loot"].append(x)
        nw["loot"].var.set("")
        self.mm_new_cv.later(1)
        return d["loot"]

    def mm_new_loot_remove(self, item):
        self.mm_nd["loot"] = [x for x in self.mm_nd["loot"] if x != item]
        self.mm_new_cv.later(1)

    # ------------------------------------------------------------------ what's picked
    def mm_new_pick(self, what, value):
        """A chip or tile: cat (Mapping / Bossing), mech (several - the first is the main one), maptype, content,
        boss, effort, budget, play."""
        d = self.mm_nd
        if what == "cat":
            d["cat"] = value
        elif what == "mech":
            d["mechs"] = [m for m in d["mechs"] if m != value] + ([] if value in d["mechs"] else [value])
        elif what in ("maptype", "content", "bosses"):
            d[what] = [t for t in d[what] if t != value] + ([] if value in d[what] else [value])
            if what == "maptype" and value == "City":
                d["city_auto"] = False                   # (your pick: no longer the app's)
        elif what == "effort":
            d["effort"] = value
        elif what == "budget":
            d["budget"] = None if d["budget"] == value else value
        elif what == "play":
            d["play"] = [] if value is None else [t for t in d["play"] if t != value] + \
                ([] if value in d["play"] else [value])
        d["msg"] = None
        self.mm_new_cv.later(1)

    def mm_new_master(self, master, choice):
        """A choice tile: ticks it for that master. One master a strat - a choice of another master switches the
        strat to it (the old picks are cleared; the page said so above the tiles)."""
        d = self.mm_nd
        old = MM.master_of(d["masters"])
        d["masters"], what = MM.master_pick(d["masters"], master, choice)
        d["mtab"] = master
        if what == "full":
            self._say(f"{master}: {MM.MASTER_PICKS} of {MM.MASTER_PICKS} used - untick one first.", 5)
        elif what == "switch":
            self._say(f"Atlas master: {master} now - your {len(old[1])} {old[0]} pick"
                      f"{'s' if len(old[1]) != 1 else ''} cleared.", 6)
        self.mm_new_cv.later(1)
        return what

    def mm_new_master_tab(self, master):
        self.mm_nd["mtab"] = master
        self.mm_new_cv.later(1)

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

    def mm_new_select(self, which):
        """A slot clicked: its mods show under the slots to tick."""
        self.mm_nd["sel"] = which
        self.mm_new_cv.later(1)

    def _mm_new_selected(self):
        """-> (which, card) the mod card shows: the picked slot, else the last copied tablet, else the waystone."""
        d = self.mm_nd
        sel = d.get("sel")
        if sel == "way" and d["way"]:
            return "way", d["way"]
        if isinstance(sel, int) and 0 <= sel < len(d["cards"]):
            return sel, d["cards"][sel]
        if d["cards"]:
            return len(d["cards"]) - 1, d["cards"][-1]
        return ("way", d["way"]) if d["way"] else (None, None)

    def _mm_new_city(self):
        """A 4th tablet ticks City (only Cities have a 4th slot) - the app's tick (AUTO) goes again below 4."""
        d = self.mm_nd
        if len(d["cards"]) >= MM.TABLETS_MAX and "City" not in d["maptype"]:
            d["maptype"].insert(0, "City")
            d["city_auto"] = True
        elif len(d["cards"]) < MM.TABLETS_MAX and d.get("city_auto"):
            d["maptype"] = [t for t in d["maptype"] if t != "City"]
            d["city_auto"] = False

    def mm_new_remove(self, which):
        d = self.mm_nd
        if which == "way":
            d["way"] = None
        elif isinstance(which, int) and 0 <= which < len(d["cards"]):
            d["cards"].pop(which)
        d["sel"] = None
        self._mm_new_city()
        self._mm_new_cost_later()
        self.mm_new_cv.later(1)

    def mm_new_slot_menu(self, which, x, y):
        """Right-click a slot: remove it."""
        from .style import menu_popup
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        m.add_command(label="Remove it", command=lambda: self.mm_new_remove(which))
        self.mm_last_menu = m
        try:
            menu_popup(m, x, y)
        except tk.TclError:
            pass
        return m

    # ------------------------------------------------------------------ a slot by hand (nothing to copy)
    def mm_new_hand_menu(self, tag=None, x=None, y=None):
        """Pick by hand ▾: the waystone, or the next tablet."""
        from .style import menu_popup
        d = self.mm_nd
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground="#2c4a84")
        m.add_command(label="Waystone" + (" (replaces yours)" if d["way"] else ""),
                      command=lambda: self.mm_new_hand_open("way"))
        m.add_command(label="Tablet", command=lambda: self.mm_new_hand_open(len(d["cards"])),
                      state="normal" if len(d["cards"]) < MM.TABLETS_MAX else "disabled")
        self.mm_last_menu = m
        if x is None and tag:
            x, y = self.mm_new_cv.at_root(tag)
        try:
            menu_popup(m, x or 0, y or 0)
        except tk.TclError:
            pass
        return m

    def mm_new_hand_open(self, which):
        """The picker for a slot: "way", or a tablet slot (an empty one: the next free). A slot filled by hand opens
        with what it has."""
        d = self.mm_nd
        if which != "way":
            which = min(int(which), len(d["cards"]), MM.TABLETS_MAX - 1)
        c = d["way"] if which == "way" else (d["cards"][which] if which < len(d["cards"]) else None)
        st = dict((c or {}).get("hand_state") or {})
        d["hand"] = {"which": which, "kind": "waystone" if which == "way" else "tablet", "tier": st.get("tier"),
                     "ttype": st.get("ttype"), "pick": None, "mods": [list(x) for x in st.get("mods") or []],
                     "props": dict(st.get("props") or {})}
        nw = self.mm_nw
        nw["hand_q"].var.set("")
        nw["hand_min"].var.set("")
        for name, e in nw["hand_props"].items():
            e.var.set(d["hand"]["props"].get(name, ""))
        d["sel"] = which if c is not None else d.get("sel")
        self.mm_new_cv.later(1)
        return d["hand"]

    def mm_new_hand_close(self):
        self.mm_nd["hand"] = None
        self.mm_new_cv.later(1)

    def mm_new_hand_set(self, field, value):
        """The waystone's tier, or the tablet's type."""
        h = self.mm_nd["hand"]
        h[field] = value
        if field == "ttype":
            h["mods"] = [m for m in h["mods"] if m[0] in MM.hand_tablet_types().get(value, [])]
        self._mm_hand_sync()
        self.mm_new_cv.later(1)

    def mm_new_hand_pick(self, template):
        self.mm_nd["hand"]["pick"] = template
        self.mm_new_cv.later(1)

    def mm_new_hand_add(self):
        """Add (grayed until a mod is picked): the mod, with its minimum when one is typed."""
        h, nw = self.mm_nd["hand"], self.mm_nw
        if not h or not h.get("pick"):
            return None
        v = re.sub(r"[^\d.]", "", self._mm_val(nw["hand_min"]))
        h["mods"] = [m for m in h["mods"] if m[0] != h["pick"]] + [[h["pick"], v]]
        h["pick"] = None
        nw["hand_min"].var.set("")
        nw["hand_q"].var.set("")
        self._mm_hand_sync()
        self.mm_new_cv.later(1)
        return h["mods"]

    def mm_new_hand_del(self, i):
        h = self.mm_nd["hand"]
        if 0 <= i < len(h["mods"]):
            h["mods"].pop(i)
        self._mm_hand_sync()
        self.mm_new_cv.later(1)

    def _mm_hand_options(self):
        """The mods the search finds (the waystone's, or the picked tablet type's)."""
        h = self.mm_nd["hand"]
        pool = MM.hand_waystone_mods() if h["kind"] == "waystone" else MM.hand_tablet_types().get(h.get("ttype"), [])
        q = self._mm_val(self.mm_nw["hand_q"]).strip().lower()
        have = {m[0] for m in h["mods"]}
        return [m for m in pool if m not in have and (not q or q in m.lower())]

    def _mm_hand_sync(self):
        """The picker's choices -> the slot's card (once it has a tier / a type)."""
        d = self.mm_nd
        h = d.get("hand")
        if not h:
            return None
        nw = self.mm_nw
        h["props"] = {n: re.sub(r"[^\d.]", "", self._mm_val(e)) for n, e in nw["hand_props"].items()
                      if self._mm_val(e).strip()}
        state = {"tier": h.get("tier"), "ttype": h.get("ttype"), "mods": [list(m) for m in h["mods"]],
                 "props": dict(h["props"])}
        if h["kind"] == "waystone":
            if not h.get("tier"):
                return None
            card = MM.hand_card("waystone", tier=h["tier"], props=h["props"], mods=h["mods"])
            card["hand_state"] = state
            d["way"] = card
        else:
            if not h.get("ttype"):
                return None
            card = MM.hand_card("tablet", base=h["ttype"], mods=h["mods"])
            card["hand_state"] = state
            i = h["which"]
            if i < len(d["cards"]):
                d["cards"][i] = card
            elif len(d["cards"]) < MM.TABLETS_MAX:
                d["cards"].append(card)
                h["which"] = len(d["cards"]) - 1
            self._mm_new_city()
        d["sel"] = h["which"]
        self._mm_new_cost_later()
        return card

    # ------------------------------------------------------------------ copies (whichever copy key, via clip_read_once)
    def mm_new_capturing(self):
        """While New strat is open (Farming Strategies › Find), a copied tablet or waystone goes to it - whichever
        copy key you press: Ctrl+Alt+C, Ctrl+C or the price check key. Attributes only: the key watcher's thread asks
        this too (clip_wanted)."""
        if not getattr(self, "mm_new_on", False):
            return False
        win = (getattr(getattr(self, "shell", None), "windows", None) or {}).get("money")
        if win is not None and getattr(win, "state_", "open") != "open":
            return False                                 # (another page shows)
        return getattr(getattr(self, "mm_page", None), "value", "Find") == "Find"

    def mm_new_wants(self, text):
        """(the window thread) Is this copy one for New strat - open, and a tablet or waystone?"""
        return self.mm_new_capturing() and MM.copied_card(text) is not None

    def mm_new_take_clip(self, text):
        """One copy (the press's one read, done by clipread) -> the waystone slot, or the next tablet slot (up to 4);
        its mods show to tick."""
        d = self.mm_nd
        card = MM.copied_card(text)
        if card is None:
            self._say("New strat takes tablets and waystones - that copy was something else.", 6)
            return None
        card["copied"] = True
        if card["kind"] == "waystone":
            d["way"], d["sel"] = card, "way"
            self._say(f"New strat: your waystone - {card['base']}. Tick what matters.", 5)
        elif len(d["cards"]) >= MM.TABLETS_MAX:
            self._say(f"{MM.TABLETS_MAX} of {MM.TABLETS_MAX} tablets: right-click one to remove it first.", 6)
            return None
        else:
            d["cards"].append(card)
            d["sel"] = len(d["cards"]) - 1
            self._mm_new_city()
            self._say(f"New strat: tablet {len(d['cards'])} of {MM.TABLETS_MAX} - {card['name']}. Tick the mods that "
                      "matter.", 5)
        self._mm_new_cost_later()
        self.mm_new_cv.later(1)
        return card

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
        if c and any(x.get("hand") for x in d["cards"] + [d["way"] or {}]):
            c = dict(c, how=c["how"] + " Picked by hand: priced from the trade search for what you picked.")
        return c, busy and not c

    # ------------------------------------------------------------------ Needs / Save

    # ------------------------------------------------------------------ Needs / Save
    def mm_new_missing(self):
        f, d = self.mm_new_fields(), self.mm_nd
        out = []
        if not f["name"]:
            out.append("a name")
        if d["cat"] == "Mapping" and not d["mechs"] and d["typ_keep"] not in MM.TAXONOMY["Mapping"]:
            out.append("a mechanic")
        if d["cat"] == "Bossing" and not d["bosses"] and d["typ_keep"] not in MM.TAXONOMY["Bossing"]:
            out.append("a boss")
        if not f["steps"]:
            out.append("one step")
        return out

    def mm_new_type(self):
        """The strat's type: Mapping - its main mechanic; Bossing - its first boss (Simulacrum, Map bosses, else
        Pinnacle bosses). An older strat's own type stays when nothing replaces it."""
        d = self.mm_nd
        if d["cat"] == "Mapping":
            if d["mechs"]:
                return d["mechs"][0]
            return d["typ_keep"] if d["typ_keep"] in MM.TAXONOMY["Mapping"] else None
        if d["bosses"]:
            return MM.BOSS_TYPE.get(d["bosses"][0], "Pinnacle bosses")
        return d["typ_keep"] if d["typ_keep"] in MM.TAXONOMY["Bossing"] else None

    def mm_new_build(self):
        """The strat as the page shows it now (not checked)."""
        from . import board as B
        d, f = self.mm_nd, self.mm_new_fields()
        base = d["base"]
        s = {k: v for k, v in base.items() if k not in ("origin", "_post")}
        typ = self.mm_new_type()
        s.update(name=f["name"], category=d["cat"], type=typ, steps=f["steps"], loot=list(d["loot"]),
                 tips=f["tips"], risks=f["risks"])
        if d["effort"] and (d["new"] or d["effort"] != d["effort0"]):
            s["thoughts_per_click"], s["clicks_per_hour"] = MM.EFFORTS[d["effort"]]
        s.setdefault("thoughts_per_click", 3)
        s.setdefault("clicks_per_hour", "Steady")
        also = [m for m in d["mechs"] if m != typ]
        s["tags"] = list(dict.fromkeys(([d["budget"]] if d["budget"] else []) + list(d["play"]) + also +
                                       list(d["maptype"]) + list(d["content"]) + list(d["bosses"]) +
                                       list(d["keep_tags"])))
        s["masters"] = {m: list(v) for m, v in d["masters"].items() if v}
        s["items"] = self.mm_new_items()
        src = f["source"]
        if src:
            m = URL.search(src)
            title = re.sub(r"\s+", " ", URL.sub("", src)).strip(" -·,|") if m else ""
            s["sources"] = [{"title": title or m.group(0), "url": m.group(0)}] + list(base.get("sources") or [])[1:] \
                if m else list(base.get("sources") or [])
        else:
            s["sources"] = list(base.get("sources") or [])[1:]
        s["summary"] = base.get("summary") or (f["steps"][0][:200] if f["steps"] else "")
        tablets_rx = self.mm_new_made("tablet")["regex"] if d["cards"] else ""
        s["regex"] = base.get("regex") or (tablets_rx if len(tablets_rx) <= 250 else "")
        if d["way"] and d["way"].get("tier"):
            s["waystone_tiers"] = {"min": d["way"]["tier"], "max": d["way"]["tier"]}
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
        src = self.mm_new_fields()["source"]
        if src and not URL.search(src):
            d["msg"] = ("✕ Source: paste its link too (https://…)", "bad")
            self.mm_new_cv.later(1)
            return None
        self.mm_new_loot_add()                          # (an item typed, not yet added)
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


    # ================================================================== drawing (the approved mockup v2)
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
        y += 32
        title = "Suggest an edit" if d["suggest"] else "New strat" if d["new"] else "Edit strat"
        cv.text(pad, y, title, ("Segoe UI", 18 if narrow else 20, "bold"), fill=cv.c("text_strong"))
        y += 36
        y = cv.bottom(cv.text(pad, y, "Pick what you farm, copy in your map device, say how it goes.", F10,
                              fill=cv.c("text_muted"), width=W - 2 * pad), y + 16) + 20
        mx0, mx1 = pad, (W - pad - SW - 20) if side else W - pad
        top = y
        card = cv.card(mx0, y, mx1, y + 10, None, lift=False)
        yy = y + 26
        parts = (self._nw_part_what, self._nw_part_device, self._nw_part_masters, self._nw_part_how,
                 self._nw_part_notes)
        for n, part in enumerate(parts, 1):
            if n > 1:
                cv.create_line(mx0 + 24, yy, mx1 - 24, yy, fill=cv.c("border"))
                yy += 24
            yy = part(cv, d, mx0, mx1, yy, n) + 24
        yy = self._nw_bottom(cv, d, mx0, mx1, yy)
        cv.coords(card, *_rr_points(mx0, top, mx1, yy, R))
        if side:
            ys = self._nw_side(cv, d, mx1 + 20, W - pad, top, 1)
            return max(yy, ys) + pad
        ys = self._nw_side(cv, d, mx0, mx1, yy + 16, 2 if W >= 640 else 1)
        return ys + pad

    # ---- pieces
    def _nw_head(self, cv, n, done, title, x0, x1, y, info=None, note=None):
        """A part's number (✓ when it's done) and title (and a muted note) -> x where they end."""
        cx, cy = x0 + 38, y + 12
        if done:
            col = cv.c("good")
            cv.create_oval(cx - 13, cy - 13, cx + 13, cy + 13, fill=TH.mix(cv.c("surface_raised"), col, .2),
                           outline=TH.mix(col, cv.c("surface_raised"), .3))
            cv.text(cx, cy, "✓", ("Segoe UI Symbol", 10, "bold"), fill=col, anchor="center")
        else:
            col = cv.c("accent")
            cv.create_oval(cx - 13, cy - 13, cx + 13, cy + 13, fill=cv.c("surface_high"), outline="")
            cv.text(cx, cy, str(n), ("Segoe UI", 9, "bold"), fill=col, anchor="center")
        t = cv.text(x0 + 72, cy, f"{n} · {title}", ("Segoe UI", 12, "bold"), fill=cv.c("text_strong"), anchor="w")
        x = cv.bbox(t)[2]
        if note:
            x = cv.bbox(cv.text(x + 8, cy + 1, note, F9, fill=cv.c("text_muted"), anchor="w"))[2]
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

    def _nw_chip(self, cv, x, y, text, tag, on, fn, role="accent", h=32, tip=None, badge=None):
        """A pill you click: picked = a ✓, the accent edge and a tint (never the color alone); badge: a small word
        in it (AUTO). -> its right edge."""
        label = ("✓ " if on else "") + text
        bw = cv.tw(label, F10) + 28 + (cv.tw(badge, FB) + 18 if badge else 0)
        col = cv.c(role)
        fill = TH.mix(cv.c("surface_raised"), col, .16) if on else cv.c("surface")
        line = col if on else cv.c("border_light")
        b = TH.round_rect(cv, x, y, x + bw, y + h, h // 2 - 1, fill=fill, outline=line, tags=(tag,))
        ink = cv.c("text_strong") if on else cv.c("text")
        t = cv.text(x + 14, y + h / 2, label, F10, fill=ink, anchor="w", tags=(tag,))
        if badge:
            bx = cv.bbox(t)[2] + 10
            g = cv.c("good")
            TH.round_rect(cv, bx, y + 8, bx + cv.tw(badge, FB) + 10, y + h - 8, 3,
                          fill=TH.mix(cv.c("surface_raised"), g, .15), outline=g, tags=(tag,))
            cv.text(bx + 5, y + h / 2, badge, FB, fill=g, anchor="w", tags=(tag,))
        cv.acts[tag] = fn
        cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on else cv.c("text_muted")})]
        if tip:
            cv.tips[tag] = tip
        return x + bw

    def _nw_chips(self, cv, x0, x1, y, chips, h=32):
        """A row of chips that wraps. chips: (text, tag, on, fn[, tip[, badge]]) -> y under them."""
        x = x0
        for c in chips:
            text, tag, on, fn = c[:4]
            badge = c[5] if len(c) > 5 else None
            w = cv.tw(("✓ " if on else "") + text, F10) + 28 + (cv.tw(badge, FB) + 18 if badge else 0)
            if x > x0 and x + w > x1:
                x, y = x0, y + h + 7
            x = self._nw_chip(cv, x, y, text, tag, on, fn, h=h, tip=c[4] if len(c) > 4 else None, badge=badge) + 7
        return y + h

    def _nw_cols(self, x0, x1):
        """(label x, input x, stacked?) - labels to the left, or above in a narrow card."""
        stacked = x1 - x0 < 480
        return x0, (x0 if stacked else x0 + 132), stacked

    def _nw_row(self, cv, x0, x1, y, label, draw, info=None, tag=None, mid=16):
        """One labeled row: draw(ix, y) -> y under it."""
        lx, ix, stacked = self._nw_cols(x0, x1)
        if stacked:
            self._nw_label(cv, lx, y + 6, label, info, tag)
            return draw(ix, y + 18)
        self._nw_label(cv, lx, y + mid, label, info, tag, width=None if info else ix - lx - 8)
        return draw(ix, y)

    def _nw_place(self, cv, w, x, y, width, height):
        cv.create_window(x, y, window=w, anchor="nw", width=max(40, int(width)), height=int(height))

    def _nw_dashed(self, cv, x0, y0, x1, y1, outline=None, tags=()):
        return TH.round_rect(cv, x0, y0, x1, y1, 8, fill=cv.c("surface_sunken"),
                             outline=outline or cv.c("border_light"), dash=(4, 3), tags=tags)

    # ---- 1 What you farm
    def _nw_part_what(self, cv, d, x0, x1, y, n):
        f = self.mm_new_fields()
        miss = self.mm_new_missing()
        done = bool(f["name"]) and not ({"a mechanic", "a boss"} & set(miss))
        self._nw_head(cv, n, done, "What you farm", x0, x1, y)
        cx, cr = x0 + 72, x1 - 24
        y += 42
        nw = self.mm_nw

        def name(ix, yy):
            self._nw_place(cv, nw["name"], ix, yy, cr - ix, 38)
            return yy + 38
        y = self._nw_row(cv, cx, cr, y, "Name", name, mid=19) + 16

        def acts(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(c, f"nw_cat_{c}", d["cat"] == c,
                                                    lambda c=c: self.mm_new_pick("cat", c)) for c in MM.CATEGORIES])
        y = self._nw_row(cv, cx, cr, y, "Activity", acts) + 16
        y = self._nw_row(cv, cx, cr, y, "Mechanics", lambda ix, yy: self._nw_mechs(cv, d, ix, cr, yy), mid=14,
                         tag="nw_mech_i", info="Pick one or more. The first is the main one.") + 18

        def maptype(ix, yy):
            chips = []
            for word, tag in MM.MAP_TYPE_CHIPS:
                on = tag in d["maptype"]
                chips.append((word, f"nw_mt_{tag}", on, lambda t=tag: self.mm_new_pick("maptype", t),
                              "Ticked for you: 4 tablets (only Cities have a 4th slot)" if on and tag == "City"
                              and d.get("city_auto") else None,
                              "AUTO" if on and tag == "City" and d.get("city_auto") else None))
            return self._nw_chips(cv, ix, cr, yy, chips)
        y = self._nw_row(cv, cx, cr, y, "Map type", maptype) + 16

        def content(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(t, f"nw_mc_{i}", t in d["content"],
                                                    lambda t=t: self.mm_new_pick("content", t))
                                                   for i, t in enumerate(_map_content())])
        y = self._nw_row(cv, cx, cr, y, "Map content", content) + 16

        def bosses(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(w, f"nw_boss_{i}", t in d["bosses"],
                                                    lambda t=t: self.mm_new_pick("bosses", t), t if t != w else None)
                                                   for i, (w, t) in enumerate(MM.BOSS_CHIPS)])
        y = self._nw_row(cv, cx, cr, y, "Bosses", bosses) + 16

        def effort(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(w, f"nw_eff_{w}", d["effort"] == w,
                                                    lambda w=w: self.mm_new_pick("effort", w)) for w in MM.EFFORTS])
        y = self._nw_row(cv, cx, cr, y, "Effort", effort, tag="nw_eff_i",
                         info="How much thinking and clicking a map takes.") + 16

        def budget(ix, yy):
            return self._nw_chips(cv, ix, cr, yy, [(w, f"nw_bud_{i}", d["budget"] == t,
                                                    lambda t=t: self.mm_new_pick("budget", t), t)
                                                   for i, (w, t) in enumerate(MM.BUDGET_CHIPS)])
        y = self._nw_row(cv, cx, cr, y, "Budget", budget) + 16

        def play(ix, yy):
            chips = [("Any", "nw_play_any", not d["play"], lambda: self.mm_new_pick("play", None))]
            chips += [(t, f"nw_play_{i}", t in d["play"], lambda t=t: self.mm_new_pick("play", t))
                      for i, t in enumerate(PLAY)]
            return self._nw_chips(cv, ix, cr, yy, chips)
        return self._nw_row(cv, cx, cr, y, "Play style", play)

    def _nw_mechs(self, cv, d, x0, x1, y):
        """The mechanics as tiles, several can be on: MAIN / ALSO over the tablet's picture (a dashed box when the
        app has none) and its word, ✓ when on."""
        w, h, gap = 94, 95, 6
        x = x0
        for i, t in enumerate(MECH_ORDER):
            if x > x0 and x + w > x1:
                x, y = x0, y + h + gap
            tag = f"nw_typ_{i}"
            on = t in d["mechs"]
            col = cv.c("accent")
            fill = TH.mix(cv.c("surface_raised"), col, .14) if on else cv.c("surface")
            line = col if on else cv.c("border")
            b = TH.round_rect(cv, x, y, x + w, y + h, 6, fill=fill, outline=line, tags=(tag,))
            if on:
                cv.text(x + w / 2, y + 15, "MAIN" if d["mechs"][0] == t else "ALSO", FB, fill=col, anchor="center",
                        tags=(tag,))
            base = MM.MECH_TABLET.get(t)
            got = cv.icon(base, x + w / 2, y + 46, 32, anchor="center", tags=(tag,)) if base else None
            if got is None:
                TH.round_rect(cv, x + w / 2 - 17, y + 30, x + w / 2 + 17, y + 64, 5, fill="",
                              outline=cv.c("border_light"), dash=(3, 3), tags=(tag,))
            cv.text(x + w / 2, y + h - 16, cv.fit(("✓ " if on else "") + t, F9, w - 6), F9,
                    fill=cv.c("text_strong") if on else cv.c("text"), anchor="center", tags=(tag,))
            cv.acts[tag] = lambda t=t: self.mm_new_pick("mech", t)
            cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on else cv.c("text_muted")})]
            cv.tips[tag] = (f"{t}: the main one" if on and d["mechs"][0] == t else f"{t}: also used" if on
                            else t) + ("" if base else " (no tablet picture)")
            x += w + gap
        return y + h

    # ---- 2 In your map device
    def _nw_keys_line(self, cv, x, y, before, after, x1):
        """"Hover ... press [Ctrl] [Alt] [C]. ..." - the keys as key caps."""
        x = cv.bbox(cv.text(x, y, before, F9, fill=cv.c("text_muted"), anchor="w"))[2] + 6
        for k in ("Ctrl", "Alt", "C"):
            kw = cv.tw(k, ("Segoe UI", 9)) + 12
            TH.round_rect(cv, x, y - 10, x + kw, y + 10, 3, fill=cv.c("surface_sunken"), outline=cv.c("border_light"))
            cv.text(x + kw / 2, y, k, ("Segoe UI", 9), fill=cv.c("text"), anchor="center")
            x += kw + 2
        cv.text(x + 2, y, cv.fit(after, F9, max(40, x1 - x - 2)), F9, fill=cv.c("text_muted"), anchor="w")

    def _nw_part_device(self, cv, d, x0, x1, y, n):
        cards, way = d["cards"], d["way"]
        self._nw_head(cv, n, bool(cards or way), "In your map device", x0, x1, y,
                      info="Each copy is read once, from your key press.")
        cx, cr = x0 + 72, x1 - 24
        y += 40
        self._nw_keys_line(cv, cx, y, "Hover a waystone or tablet in game, press",
                           ". It lands in the next slot - or pick by hand.", cr)
        y += 24
        sz, gap = 74, 30 if cr - cx > 520 else 18
        cost = MM.run_cost({"id": d.get("cost_sid"), "items": d.get("cost_items") or []}, self.mm_costs()) \
            if d.get("cost_sid") else None
        prices = ((self.mm_costs() or {}).get(d.get("cost_sid")) or {}).get("prices") or {}
        _ = cost
        next_free = len(cards)
        x = cx
        slots = [("way", way)] + [(i, cards[i] if i < len(cards) else None) for i in range(MM.TABLETS_MAX)]
        for which, c in slots:
            if x + sz > cr:
                x, y = cx, y + sz + 54
            tag = f"nw_slot_{which}"
            kind = "Waystone" if which == "way" else "Tablet"
            if c is None:
                nxt = which == "way" or which == next_free
                self._nw_dashed(cv, x, y, x + sz, y + sz, outline=cv.c("accent") if nxt else None, tags=(tag,))
                cv.text(x + sz / 2, y + sz / 2, "+" if nxt else "", ("Segoe UI", 12), fill=cv.c("text_muted"),
                        anchor="center", tags=(tag,))
                sub = "copy one in" if nxt else "empty"
                if nxt:                                  # (nothing to copy: click it to pick by hand)
                    cv.acts[tag] = lambda w=which: self.mm_new_hand_open(w)
                cv.tips[tag] = f"{kind}: hover it in game and press Ctrl+Alt+C - or click to pick by hand" if nxt else \
                    "Only Cities have a 4th tablet slot" if which == MM.TABLETS_MAX - 1 else f"{kind}: empty"
            else:
                b = TH.round_rect(cv, x, y, x + sz, y + sz, 6, fill=cv.c("surface_sunken"),
                                  outline=cv.c("border_light"), tags=(tag,))
                if cv.icon(c["base"], x + sz / 2, y + sz / 2, 62, anchor="center", tags=(tag,)) is None:
                    cv.text(x + sz / 2, y + sz / 2, cv.fit(c["base"].split()[0], F9, sz - 8), F9,
                            fill=cv.c("text_muted"), anchor="center", tags=(tag,))
                if which == "way":
                    p = prices.get("0") if d.get("cost_sid") and str(d.get("cost_sid")).startswith("_new") else None
                    sub = (f"T{c['tier']}" if c.get("tier") else c["base"]) + (
                        " · by hand" if c.get("hand") else f" · {MM.short_div(p)} div" if p is not None else "")
                else:
                    sub = " · ".join(x_ for x_ in (c["base"].replace(" Tablet", ""), "by hand" if c.get("hand") else
                                                   f"{c['uses']} uses" if c.get("uses") else "") if x_)
                cv.acts[tag] = (lambda w=which: self.mm_new_hand_open(w)) if c.get("hand") else \
                    (lambda w=which: self.mm_new_select(w))
                cv.menus[tag] = lambda X, Y, w=which: self.mm_new_slot_menu(w, X, Y)
                cv.lifts[tag] = [(b, {"outline": cv.c("border_light")}, {"outline": cv.c("text_muted")})]
                cv.tips[tag] = f"{c.get('name') or c['base']} - click: tick its mods · right-click: remove it"
            cv.text(x + sz / 2, y + sz + 14, kind, F9, fill=cv.c("text"), anchor="center", tags=(tag,))
            cv.text(x + sz / 2, y + sz + 33, cv.fit(sub, F9, sz + gap + 10), F9, fill=cv.c("text_muted"),
                    anchor="center", tags=(tag,))
            x += sz + gap
        y += sz + 46
        full = d["way"] is not None and len(cards) >= MM.TABLETS_MAX
        _a, _b = cv.button(cx, y, "Pick by hand ▾", "nw_hand", lambda: self.mm_new_hand_menu("nw_hand"), h=32,
                           enabled=not full, tip="No waystone or tablet to copy? Pick one by hand: its tier or type, "
                                                 "and its mods" if not full else "Every slot is filled")
        y += 44
        if d.get("city_auto") and "City" in d["maptype"]:
            g = cv.c("good")
            t1 = cv.text(cx, y + 8, f"✓ {MM.TABLETS_MAX} tablets: ", F9, fill=g, anchor="w")
            t2 = cv.text(cv.bbox(t1)[2], y + 8, "City", ("Segoe UI", 9, "bold"), fill=g, anchor="w")
            t3 = cv.text(cv.bbox(t2)[2] + 3, y + 8, "map type ticked for you", F9, fill=g, anchor="w")
            cv.text(cv.bbox(t3)[2] + 4, y + 8, "(only Cities have a 4th slot)", F9, fill=cv.c("text_muted"),
                    anchor="w")
            y += 26
        if d.get("hand"):                                # the by-hand picker, under the slots
            y = self._nw_hand_panel(cv, d, cx, cr, y) + 12
        which, c = self._mm_new_selected()
        if c is not None:
            if not d.get("hand"):
                y = self._nw_mods_card(cv, which, c, cx, cr, y) + 12
            y = self._nw_made(cv, "waystone" if which == "way" else "tablet", cx, cr, y)
        else:
            y -= 10
        return y

    def _nw_hand_panel(self, cv, d, x0, x1, y):
        """The by-hand picker, a small card under the slots: the waystone's tier and top numbers, or the tablet's
        type; then Add a mod - its search box first, the matches, a minimum, Add (grayed until one is picked)."""
        h, nw = d["hand"], self.mm_nw
        card = TH.round_rect(cv, x0, y, x1, y + 10, 8, fill=cv.c("surface"), outline=cv.c("border"))
        way = h["kind"] == "waystone"
        t = cv.text(x0 + 16, y + 24, "Waystone by hand" if way else "Tablet by hand", ("Segoe UI", 10, "bold"),
                    fill=cv.c("text_strong"), anchor="w")
        cv.text(cv.bbox(t)[2] + 6, y + 24, "· nothing to copy? pick it here", F9, fill=cv.c("text_muted"), anchor="w")
        cv.button(x1 - 12, y + 8, "✕", "nw_hand_x", self.mm_new_hand_close, anchor="e", h=30, w=32,
                  tip="Close the picker")
        yy = y + 50
        lx, ix = x0 + 16, x0 + 16 + 132 if x1 - x0 > 560 else x0 + 16
        stacked = ix == lx
        cr = x1 - 16

        def label(text, yy_):
            cv.text(lx, yy_ + (6 if stacked else 15), text, FB, fill=cv.c("text_muted"), anchor="w")
            return yy_ + (20 if stacked else 0)
        if way:
            yy = label("TIER", yy)
            yy = self._nw_chips(cv, ix, cr, yy, [(str(n), f"nw_ht_{n}", h.get("tier") == n,
                                                  lambda n=n: self.mm_new_hand_set("tier", n))
                                                 for n in range(1, 17)], h=30) + 14
            yy = label("TOP NUMBERS · MIN", yy)
            cw = max(150, (cr - ix) / 3)
            x, ry = ix, yy
            for name in MM.hand_props():
                if x + cw > cr + 2:
                    x, ry = ix, ry + 40
                cv.text(x, ry + 15, name, F9, fill=cv.c("text"), anchor="w")
                self._nw_place(cv, nw["hand_props"][name], x + cw - 72, ry, 62, 30)
                x += cw
            yy = ry + 30 + 16
        else:
            yy = label("TYPE", yy)
            yy = self._nw_chips(cv, ix, cr, yy, [(b.replace(" Tablet", "") + (" (Precursor)" if b.startswith(
                "Irradiated") else ""), f"nw_htt_{i}", h.get("ttype") == b, lambda b=b: self.mm_new_hand_set("ttype", b))
                for i, b in enumerate(MM.hand_tablet_types())], h=30) + 6
            yy = cv.bottom(cv.text(ix, yy + 4, f"{10} uses - the trade search looks for {MM.TABLET_USES}+", F9,
                                   fill=cv.c("text_muted")), yy + 16) + 12
        ready = way and h.get("tier") or not way and h.get("ttype")
        yy = label("ADD A MOD", yy)
        if not ready:
            yy = cv.bottom(cv.text(ix, yy + 8, "Pick its " + ("tier" if way else "type") + " first.", F9,
                                   fill=cv.c("text_muted")), yy + 16) + 14
        else:
            self._nw_place(cv, nw["hand_q"], ix, yy, min(320, cr - ix), 32)   # (the search box first)
            yy += 38
            opts = self._mm_hand_options()
            for i, m in enumerate(opts[:6]):
                tag = f"nw_ho_{i}"
                on = m == h.get("pick")
                b = TH.round_rect(cv, ix, yy, cr, yy + 28, 4, fill=TH.mix(cv.c("surface_raised"), cv.c("accent"), .16)
                                  if on else cv.c("surface_raised"), outline=cv.c("accent") if on else "", tags=(tag,))
                cv.text(ix + 10, yy + 14, cv.fit(("✓ " if on else "") + m, F9, cr - ix - 20), F9,
                        fill=cv.c("text_strong") if on else cv.c("text"), anchor="w", tags=(tag,))
                cv.acts[tag] = lambda m=m: self.mm_new_hand_pick(m)
                cv.lifts[tag] = [(b, {"outline": cv.c("accent") if on else ""}, {"outline": cv.c("text_muted")})]
                cv.tips[tag] = m
                yy += 31
            if len(opts) > 6:
                yy = cv.bottom(cv.text(ix, yy + 2, f"{len(opts) - 6} more - type to narrow the list", F9,
                                       fill=cv.c("text_muted")), yy + 14) + 6
            elif not opts:
                yy = cv.bottom(cv.text(ix, yy + 2, "No mod matches.", F9, fill=cv.c("text_muted")), yy + 14) + 6
            yy += 4
            pick = h.get("pick")
            cv.text(ix, yy + 16, cv.fit(pick or "Pick a mod above", F9, max(60, cr - ix - 190)), F9,
                    fill=cv.c("text") if pick else cv.c("text_muted"), anchor="w")
            self._nw_place(cv, nw["hand_min"], cr - 170, yy, 70, 32)
            cv.button(cr, yy, "Add", "nw_hand_add", self.mm_new_hand_add, anchor="e", h=32, enabled=bool(pick),
                      tip="Add it (with its minimum, if you typed one)" if pick else "Pick a mod first")
            yy += 44
            for i, (tmpl, v) in enumerate(h["mods"]):
                tag = f"nw_hm_{i}"
                line = MM.hand_line(tmpl, v) + ("" if v else "  (any value)")
                b = TH.round_rect(cv, ix, yy, cr, yy + 28, 4, fill=cv.c("surface_raised"), outline="", tags=(tag,))
                cv.text(ix + 10, yy + 14, cv.fit("✓ " + line, F9, cr - ix - 50), F9, fill=cv.c("text"), anchor="w",
                        tags=(tag,))
                cv.text(cr - 12, yy + 14, "✕", F9, fill=cv.c("text_muted"), anchor="e", tags=(tag,))
                cv.acts[tag] = lambda i=i: self.mm_new_hand_del(i)
                cv.tips[tag] = "Remove it"
                cv.lifts[tag] = [(b, {"outline": ""}, {"outline": cv.c("text_muted")})]
                yy += 31
        yy += 6
        cv.coords(card, *_rr_points(x0, y, x1, yy, 8))
        return yy

    def _nw_mods_card(self, cv, which, c, x0, x1, y):
        """The picked copy: its picture and name, and its mods as toggles - tick the ones that matter."""
        card = TH.round_rect(cv, x0, y, x1, y + 10, 8, fill=cv.c("surface"), outline=cv.c("border"))
        got = cv.icon(c["base"], x0 + 16, y + 26, 26, anchor="w")
        tx = x0 + 16 + (36 if got is not None else 0)
        t = cv.text(tx, y + 26, c.get("name") or c["base"], ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"),
                    anchor="w")
        cv.text(cv.bbox(t)[2] + 4, y + 26, "· tick the mods that matter", F9, fill=cv.c("text_muted"), anchor="w")
        yy = y + 46
        if not c["mods"]:
            yy = cv.bottom(cv.text(x0 + 16, yy, f"No mods - a white {c['kind']}: searched by its base.", F9,
                                   fill=cv.c("text_muted")), yy + 14) + 12
        else:
            chips = [(cv.fit(m, F10, x1 - x0 - 80), f"nw_m_{which}_{i}", m in c["ticked"],
                      lambda m=m: self.mm_new_tick(which, m), m) for i, m in enumerate(c["mods"])]
            yy = self._nw_chips(cv, x0 + 16, x1 - 16, yy, chips) + 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, 8))
        return yy

    def _nw_made(self, cv, kind, x0, x1, y):
        """Made for you: the stash regex (Copy regex) and the Trade Site search for the ticked mods."""
        m = self.mm_new_made(kind)
        box = self._nw_dashed(cv, x0, y, x1, y + 10)
        yy = y + 12
        lab = cv.text(x0 + 12, yy + 18, "MADE FOR YOU", FB, fill=cv.c("text_muted"), anchor="w")
        rx0 = cv.bbox(lab)[2] + 10
        b1 = cv.tw("Copy regex", F10) + 32
        b2 = cv.tw("Trade Site ↗", F10) + 32
        room = x1 - 12 - rx0 - b1 - b2 - 16
        text = m["regex"] or ("tick a mod above" if (self.mm_nd["cards"] if kind == "tablet" else self.mm_nd["way"])
                              else "copy one first")
        font = ("Consolas", 9) if m["regex"] else F9
        rw = min(max(80, room), cv.tw(text, font) + 18)
        if room < 80:                                    # (narrow: the buttons go under it)
            rw = x1 - 12 - rx0
        TH.round_rect(cv, rx0, yy + 4, rx0 + rw, yy + 32, 4, fill=cv.c("surface_raised"), outline="")
        cv.text(rx0 + 9, yy + 18, cv.fit(text, font, rw - 18), font,
                fill=cv.c("text") if m["regex"] else cv.c("text_muted"), anchor="w", tags=(f"nw_rx_{kind}",))
        if m["regex"]:
            cv.tips[f"nw_rx_{kind}"] = m["regex"]
        if room < 80:
            yy += 42
            bx = x0 + 12
        else:
            bx = rx0 + rw + 8
        _a, bx = cv.button(bx, yy, "Copy regex", f"nw_copy_{kind}", lambda: self.mm_new_copy(kind),
                           enabled=bool(m["regex"]), h=36,
                           tip="Copy the stash search. In game: Ctrl+V in the stash search." if m["regex"]
                           else "Tick a mod first")
        cv.button(bx + 8, yy, "Trade Site ↗", f"nw_trade_{kind}", lambda: self.mm_new_trade(kind),
                  enabled=bool(m["url"]), h=36,
                  tip="Opens the trade site in your browser: " + (m["caption"] or "copy one first"))
        yy += 36 + 12
        cv.coords(box, *_rr_points(x0, y, x1, yy, 8))
        return yy

    # ---- 3 Atlas master (one master at a time, its 12 choices in the game's 3 × 4 grid)
    def _nw_part_masters(self, cv, d, x0, x1, y, n):
        cur, picks = MM.master_of(d["masters"])
        self._nw_head(cv, n, bool(picks), "Atlas master", x0, x1, y,
                      note=f"optional · one master, up to {MM.MASTER_PICKS} picks")
        cv.button(x1 - 24, y - 6, "Clear", "nw_mclear", self.mm_new_masters_clear, anchor="e", h=36,
                  enabled=bool(picks), tip="Untick the picks" if picks else "Nothing picked yet")
        cx, cr = x0 + 72, x1 - 24
        y += 46
        tab = d.get("mtab") or cur or next(iter(MM.MASTERS))
        names = list(MM.MASTERS)
        px1 = cx + min(cr - cx, max(420, (cr - cx) * 0.905))
        panel = TH.round_rect(cv, cx, y, px1, y + 10, 8, fill=cv.c("surface"), outline=cv.c("border"))
        ip, gap = 14, 7
        iw = px1 - cx - 2 * ip
        tw = (iw - 2 * gap) / 3
        ty = y + ip
        for i, m in enumerate(names):
            tx0 = cx + ip + i * (tw + gap)
            tag = f"nw_mtab_{i}"
            shown, mine = m == tab, m == cur
            col = cv.c("accent")
            fill = TH.mix(cv.c("surface_raised"), col, .14) if shown else cv.c("surface_raised")
            b = TH.round_rect(cv, tx0, ty, tx0 + tw, ty + 74, 6, fill=fill, outline=col if shown else cv.c("border"),
                              tags=(tag,))
            first, spec = m.split("'s ")[0], m.split(" ", 1)[1] if " " in m else ""
            k = len(picks) if mine else 0
            cv.text(tx0 + tw / 2, ty + 18, first, ("Segoe UI", 10, "bold"), fill=cv.c("text_strong"), anchor="center",
                    tags=(tag,))
            cv.text(tx0 + tw / 2, ty + 37, spec.upper(), FB, fill=cv.c("text_muted"), anchor="center", tags=(tag,))
            cv.text(tx0 + tw / 2, ty + 56, f"{k} of {MM.MASTER_PICKS}" + (" ✓" if k >= MM.MASTER_PICKS else ""), F9,
                    fill=cv.c("text"), anchor="center", tags=(tag,))
            cv.acts[tag] = lambda m=m: self.mm_new_master_tab(m)
            cv.lifts[tag] = [(b, {"outline": col if shown else cv.c("border")},
                              {"outline": col if shown else cv.c("text_muted")})]
            cv.tips[tag] = m + (f" - your strat's master: {k} of {MM.MASTER_PICKS} picked" if mine else "")
        gy = ty + 74 + gap
        if cur and cur != tab and picks:                 # ticking here switches the strat's master: said first
            note = (f"Your strat uses {cur} ({len(picks)} pick{'s' if len(picks) != 1 else ''}). Ticking one here "
                    f"switches it to {tab} and clears those.")
            gy = cv.bottom(cv.text(cx + ip, gy + 4, "! " + note, F9, fill=cv.c("warn", "text"), width=iw,
                                   tags=("nw_mswitch",)), gy + 18) + 10
        cols = MM.MASTER_COLS
        th = max(56, min(112, tw / 1.7))
        full = tab == cur and len(picks) >= MM.MASTER_PICKS
        mine = picks if tab == cur else []
        for i, ch in enumerate(MM.MASTERS[tab]):
            gx = cx + ip + (i % cols) * (tw + gap)
            gy_ = gy + (i // cols) * (th + gap)
            tag = f"nw_ms_{names.index(tab)}_{i}"
            on = ch in mine
            col = cv.c("accent")
            fill = TH.mix(cv.c("surface_raised"), col, .16) if on else cv.c("surface_raised")
            line = col if on else cv.c("border")
            b = TH.round_rect(cv, gx, gy_, gx + tw, gy_ + th, 6, fill=fill, outline=line, tags=(tag,))
            cv.create_text(gx + tw / 2, gy_ + th / 2, text=ch, font=F9, width=tw - 16, justify="center",
                           anchor="center", tags=(tag,),
                           fill=cv.c("text_strong") if on else cv.c("text_muted") if full else cv.c("text"))
            if on:
                cv.text(gx + tw - 14, gy_ + 14, "✓", ("Segoe UI Symbol", 9, "bold"), fill=col, anchor="center",
                        tags=(tag,))
            cv.acts[tag] = lambda m=tab, ch=ch: self.mm_new_master(m, ch)
            cv.lifts[tag] = [(b, {"outline": line}, {"outline": col if on or not full else cv.c("border")})]
            cv.tips[tag] = f"{MM.MASTER_PICKS} of {MM.MASTER_PICKS} used - untick one first" if full and not on \
                else ch + (" - picked" if on else "")
        y2 = gy + 4 * (th + gap) - gap + ip
        cv.coords(panel, *_rr_points(cx, y, px1, y2, 8))
        return y2

    # ---- 4 How it goes
    def _nw_part_how(self, cv, d, x0, x1, y, n):
        f = self.mm_new_fields()
        self._nw_head(cv, n, bool(f["steps"]), "How it goes", x0, x1, y)
        cx, cr = x0 + 72, x1 - 24
        y += 42
        steps = self.mm_nw["steps"]
        for i, e in enumerate(steps, 1):
            ccx = cx + 10
            if i < len(steps):
                cv.create_line(ccx, y + 18, ccx, y + 54, fill=cv.c("border"))
            cv.create_oval(ccx - 9, y + 1, ccx + 9, y + 19, fill=cv.c("surface_high"), outline="")
            cv.text(ccx, y + 10, str(i), ("Segoe UI", 8), fill=cv.c("text_muted"), anchor="center")  # token-ok
            self._nw_place(cv, e, cx + 30, y, cr - cx - 30, 38)
            y += 54
        y += 10

        def loot(ix, yy):
            x, h = ix, 38
            for i, item in enumerate(d["loot"]):
                w = 34 + cv.tw(item + " ✕", F10) + 14
                if x > ix and x + w > cr:
                    x, yy = ix, yy + h + 7
                tag = f"nw_loot_{i}"
                b = TH.round_rect(cv, x, yy, x + w, yy + h, h // 2 - 1, fill=cv.c("surface"),
                                  outline=cv.c("border_light"), tags=(tag,))
                if cv.icon(item, x + 8, yy + h / 2, 20, anchor="w", tags=(tag,)) is None:
                    cv.create_oval(x + 7, yy + 9, x + 27, yy + 29, fill=cv.c("surface_high"), outline="", tags=(tag,))
                cv.text(x + 34, yy + h / 2, item + " ✕", F10, fill=cv.c("text"), anchor="w", tags=(tag,))
                cv.acts[tag] = lambda it=item: self.mm_new_loot_remove(it)
                cv.lifts[tag] = [(b, {"outline": cv.c("border_light")}, {"outline": cv.c("text_muted")})]
                cv.tips[tag] = f"Remove {item}"
                x += w + 7
            if x > ix and x + 200 > cr:
                x, yy = ix, yy + h + 7
            self._nw_place(cv, self.mm_nw["loot"], x, yy, min(200, cr - x), h)
            return yy + h
        return self._nw_row(cv, cx, cr, y, "Loot to sell", loot, mid=19)

    # ---- 5 Notes
    def _nw_part_notes(self, cv, d, x0, x1, y, n):
        f = self.mm_new_fields()
        self._nw_head(cv, n, bool(f["tips"] or f["risks"] or f["source"]), "Notes", x0, x1, y, note="optional")
        cx, cr = x0 + 72, x1 - 24
        y += 42
        nw = self.mm_nw
        for key, label in (("tips", "Tips"), ("risks", "Risks"), ("source", "Source")):
            w = nw[key]
            rows = max(1, min(4, len(self._mm_val(w).split("\n")))) if isinstance(w, tk.Text) else 1
            h = 38 if rows == 1 else 20 * rows + 18
            if isinstance(w, tk.Text):
                try:
                    w.configure(height=rows)
                except tk.TclError:
                    pass

            def put(ix, yy, w=w, h=h):
                self._nw_place(cv, w, ix, yy, cr - ix, h)
                return yy + h
            y = self._nw_row(cv, cx, cr, y, label, put, mid=19) + 16
        return y - 16

    # ---- the bottom: Cancel · Needs · Save strat
    def _nw_bottom(self, cv, d, x0, x1, y):
        cv.create_line(x0 + 24, y, x1 - 24, y, fill=cv.c("border"))
        y += 20
        miss = self.mm_new_missing()
        label = "Send suggestion" if d["suggest"] else "Save strat"
        cv.button(x0 + 24, y + 4, "Cancel", "nw_cancel", self.mm_new_close, h=38, tip="Back without saving")
        sx0, _sx1 = cv.button(x1 - 24, y, label, "nw_save", self.mm_new_save, kind="primary", enabled=not miss,
                              anchor="e", h=44,
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
        cv.text(sx0 - 12, y + 22, cv.fit(text, F9, max(60, sx0 - x0 - 140)), F9, fill=cv.c(role), anchor="e",
                tags=("nw_needs",))
        return y + 44 + 22

    # ---- the side panel: How it shows in Find, Cost per map, Parts
    def _nw_side(self, cv, d, x0, x1, y, cols=1):
        parts = (self._nw_side_find, self._nw_side_cost, self._nw_side_check)
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
        t = cv.text(x0 + 16, y + 22, title.upper(), FB, fill=cv.c("text_muted"), anchor="w")
        if info:
            cv.info(cv.bbox(t)[2] + 6, y + 22, tag, info)
        return card, y + 40

    def _nw_side_find(self, cv, d, x0, x1, y):
        card, yy = self._nw_side_box(cv, x0, x1, y, "How it shows in Find")
        f = self.mm_new_fields()
        typ = self.mm_new_type()
        s = {"type": typ or "", "category": d["cat"], "tags": ([d["budget"]] if d["budget"] else []) + d["mechs"]}
        TH.round_rect(cv, x0 + 12, yy, x1 - 12, yy + 62, 6, fill=cv.c("surface_raised"), outline="")
        got = cv.icon(MM.tablet_of(s), x0 + 24, yy + 31, 34, anchor="w")
        tx = x0 + 24 + (44 if got is not None else 0)
        room = x1 - 22 - tx
        cv.text(tx, yy + 19, cv.fit(f["name"] or "Your strat's name", ("Segoe UI", 10, "bold"), room),
                ("Segoe UI", 10, "bold"), fill=cv.c("text_strong") if f["name"] else cv.c("text_muted"), anchor="w")
        x = tx
        main = d["mechs"][0] if d["mechs"] else (typ if typ else None)
        if main:
            x = self._mm_mech_chip(cv, tx, yy + 31, {"type": main, "category": d["cat"], "tags": d["mechs"]}) \
                if cv.tw(main, F9) + 40 < room else x
        b = d["budget"]
        if b and x + cv.tw(b, F9) + 24 < tx + room:
            cv.chip(x + 6, yy + 31, b)
        yy += 62 + 14
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _nw_side_cost(self, cv, d, x0, x1, y):
        cost, busy = self.mm_new_cost()
        how = cost["how"] if cost else ("What goes in your map device each map, at today's prices on the trade site "
                                        "(the cheapest real offer of each): the waystone, plus each tablet's price ÷ "
                                        "its uses. Checked a moment after you copy or tick.")
        card, yy = self._nw_side_box(cv, x0, x1, y, "Cost per map", how, "nw_cost_i")
        num = (TH.head_font(None, "num"), 20)
        cv.text(x0 + 16, yy - 2, f"{MM.short_div(cost['value'])} div" if cost else "—", num, fill=cv.c("text_strong"),
                tags=("nw_cost",))
        yy += 38
        if cost:
            line = cost["sum"]
            cv.tips["nw_cost"] = cost["how"]
        elif busy:
            line = "checking the trade site…"
        elif d["cards"] or d["way"]:
            line = ("needs your league in Settings to check the trade site" if not SETTINGS.get("league") else
                    "no price found yet")
        else:
            line = "Copy your waystone and tablets: their prices today add up here."
        yy = cv.bottom(cv.text(x0 + 16, yy, line, F9, fill=cv.c("text_muted"), width=x1 - x0 - 32), yy + 14) + 16
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy

    def _nw_side_check(self, cv, d, x0, x1, y):
        card, yy = self._nw_side_box(cv, x0, x1, y, "Parts")
        f = self.mm_new_fields()
        miss = self.mm_new_missing()
        n_t = len(d["cards"])
        cur, picks = MM.master_of(d["masters"])
        rows = ((bool(f["name"]) and not ({"a mechanic", "a boss"} & set(miss)), "What you farm"),
                (bool(d["cards"] or d["way"]), f"Map device · {n_t} tablet{'s' if n_t != 1 else ''}"),
                (bool(picks), f"Atlas master · {len(picks)} of {MM.MASTER_PICKS}"),
                (bool(f["steps"]), f"How it goes · {len(f['steps'])} step{'s' if len(f['steps']) != 1 else ''}"),
                (bool(f["tips"] or f["risks"] or f["source"]), "Notes (optional)"))
        for ok, word in rows:
            cv.text(x0 + 16, yy + 6, ("✓ " if ok else "○ ") + word, F9,
                    fill=cv.c("good") if ok else cv.c("text") if "optional" not in word else cv.c("text_muted"),
                    anchor="w")
            yy += 24
        yy += 6
        cv.coords(card, *_rr_points(x0, y, x1, yy, R))
        return yy
