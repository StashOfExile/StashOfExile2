"""Rate Mods (owner: Mods › Rate Mods) - one page, two views of the same mods:

  * One at a Time: the sets on the left (Map Items, Jewels, Gear folded into Armour / Weapons / Jewelry, each with
    its progress), one mod on a card on the right - in the game's words with its range, where it rolls, what the
    app has seen of it (Seen in listings, Players, Your rating), S A B C D F grouped High | Normal | Ignore, and
    for a mod that rolls in tiers "How much is each kind of roll worth?" (MIX B: By roll - Top / Middle / Low
    rolls, each with its own letter; "Same for every roll" is the default).
    In the Drawer the set list is a drop-down next to the search box. Owner (more life, calmly): the item's
    picture on the set rows and the card (only pictures already on this PC), each letter its own color strip
    (style.letter_color - always with its letter and its word), a progress line at the card's top right, and under
    the card Next up (the next 3) and Just rated (the last 5).
  * Table: many mods at once - tick rows (drag across the boxes, as on the price check card) and Rate selected.
Both are drawn on canvases (StratCanvas) - a few hundred items, light in the Drawer. The data side is ratemods.py.
Also here: the (once, gentle) ask. GGG ToS: your own settings only; nothing touches the game."""
import random
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import ratemods as RM
from . import themes as TH
from .inplace import set_cfg
from .mods import F_TIP
from .style import C, SegBar, Tooltip, letter_color, text_on

SETS = RM.MAP_SETS + (RM.JEWEL_SET,)
# Owner, after 3.1.0: Mod Lab's intro stands out - bigger, in the heading font, key words bold in the accent color
# (bold too, so color is never the only change). The page header draws INTRO_RICH; INTRO is the same words plain.
INTRO_RICH = (("Bored, have ", False), ("a few minutes", True), (" to kill? ", False), ("Rate some mods", True),
              (": it builds community mod data so ", False), ("everyone's price checks", True),
              (" get more accurate.", False))
INTRO = "".join(t for t, _ in INTRO_RICH)
INTRO_TIP = ("S and A count as High, B, C and D as Normal, F is left out of searches. Your ratings change your price "
             "checks at once. With Community data sharing on, they're your vote too.")
VIEWS = ("One at a Time", "Table")
GROUPS = (("High", ("S", "A")), ("Normal", ("B", "C", "D")), ("Ignore", ("ignore",)))
SHOWN = (("S", "S"), ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("ignore", "F"))
KEYS_LINE = "S A B C D F rate · ← → move"
FILTERS = ("Not rated", "Rated", "All")
QUESTION = "How valuable is each roll?"
SAME = "Same for every roll"
SEARCH_HINT = "Search mods or items"
NARROW = 720                     # below this page width (the Drawer): the set list is a drop-down
LEFT_W = 290
F_HEAD = ("Segoe UI", 12, "bold")
F_MOD = ("Segoe UI", 20)
F_MOD_S = ("Segoe UI", 16)
F_BODY = ("Segoe UI", 10)
F_BOLD = ("Segoe UI", 10, "bold")
F_SMALL = ("Segoe UI", 9)
F_CAP = ("Segoe UI", 9, "bold")
F_LETTER = ("Segoe UI", 18, "bold")


def grade_label(g):
    return "F (ignore)" if g == "ignore" else g


def on_top(w, keep=None):
    """2.97.0 (feedback: it opened behind the app): in front, with focus, once - then as on top as the window it
    belongs to. 3.0.6 (the scan check window showed, went behind, showed and went behind again): it was put back to
    "not on top" while the app stayed on top, so the app covered it. keep: -> whether it stays on top (the app's own answer,
    when it has one)."""
    try:
        w.deiconify()
        w.lift()
        w.attributes("-topmost", True)
        w.after(400, lambda: w.winfo_exists() and w.attributes(
            "-topmost", owner_on_top(w) if keep is None else bool(keep())))
        w.focus_force()
    except tk.TclError:
        pass


def owner_on_top(w):
    """-> True when the window w belongs to (its transient owner, else its parent's window) is always on top."""
    try:
        own = w.transient() or w.master
        own = w.nametowidget(str(own)).winfo_toplevel() if own else None
        return bool(own is not None and own is not w and int(own.attributes("-topmost")))
    except (tk.TclError, KeyError, ValueError, TypeError):
        return False


def _letter(g):
    return "F" if g == "ignore" else g


class RateModsPage:
    """Mixed into App."""

    # ---------------------------------------------------------------- the sets
    def rm_sets(self):
        """[(set, label)]: the map item sets, Jewels, every gear class (from the game data), then each unique you've
        price checked."""
        from . import gearbook as GB
        out = list(SETS) + [(f"gear:{c}", n) for c, n in GB.classes()]
        uniq = sorted(GB.store(), key=str.lower)
        return out + [(f"unique:{n.lower()}", n) for n in uniq]

    def rm_gear_mods(self, set_name):
        from . import gearbook as GB
        if set_name.startswith("gear:"):                     # 2.99.0: every line that rolls on the class
            out = [(r["key"], r["text"]) for r in GB.class_mods(set_name[5:])]
        else:
            name = next((n for n in GB.store() if f"unique:{n.lower()}" == set_name), None)
            out = [(r["key"], r["text"]) for r in GB.unique_rows(name)] if name else []
        for rec in self.records.values():
            if RM.set_of(rec) != set_name:
                continue
            for m in (rec.get("item") or {}).get("mods") or []:
                k = RM.key_for(rec, m)
                if k:
                    out.append((k, m.get("shown") or m["text"]))
        return out

    def rm_queue(self, s):
        return RM.queue(s, self.rm_gear_mods(s) if s.startswith(("gear:", "unique:")) else None)

    def rm_entries(self, s):
        """The set's mods as the page shows them (kept while the page is up; again on each show)."""
        cache = self.__dict__.setdefault("_rm_ent", {})
        if s not in cache:
            cache[s] = RM.entries(s, self.rm_gear_mods(s) if s.startswith(("gear:", "unique:")) else None)
        return cache[s]

    def rm_count(self, s):
        """(rated by you, mods) in a set."""
        q = self.rm_queue(s)
        return sum(1 for keys, _t in q if RM.current(keys) is not None), len(q)

    def rm_groups(self):
        """[(group title, [(set, label)] or [(kind, title, [(set, label)])])] - Map Items, Jewels, Gear, Uniques."""
        sets = self.rm_sets()
        gear = [(s, lab) for s, lab in sets if s.startswith("gear:")]
        kinds = [(k, t, [(s, lab) for s, lab in gear if RM.gear_kind(s[5:]) == k]) for k, t in RM.GEAR_KINDS]
        out = [("MAP ITEMS", list(RM.MAP_SETS)), ("JEWELS", [RM.JEWEL_SET]), ("GEAR", [k for k in kinds if k[2]])]
        uniq = [(s, lab) for s, lab in sets if s.startswith("unique:")]
        if uniq:
            out.append(("UNIQUES YOU'VE CHECKED", uniq))
        return out

    # ---------------------------------------------------------------- the page
    def build_ratemods_page(self, body):
        from .stratview import StratCanvas
        P1, P2 = C["panel"], C["panel2"]
        page = self.rm_page = tk.Frame(body, bg=P1, takefocus=1, highlightthickness=0)
        page.pack(fill="both", expand=True)
        self.rm_qv = tk.StringVar()
        self.rm_q, self.rm_i, self.rm_set, self.rm_set_label = [], 0, None, ""
        self.rm_ticked, self.rm_narrow = set(), None
        self.rm_tfilter = "Not rated"
        self.rm_view = _saved_view() if _saved_view() in VIEWS else VIEWS[0]
        self.rm_fold = set()
        # (the one intro line is the page header's, under the title - INTRO, with its ⓘ: the module's blurb_tip)
        top = tk.Frame(page, bg=P1)
        top.pack(fill="x", padx=12, pady=(8, 8))
        self.rm_seg = SegBar(top, list(VIEWS), value=self.rm_view, command=self.rm_view_pick, size=9, pad=(16, 4),
                             plain=True)
        self.rm_seg.pack(side="left")
        Tooltip(self.rm_seg, "Two ways to rate the same mods: one card at a time, or many rows at once")
        self.rm_note = tk.Label(top, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="e")
        self.rm_note.pack(side="right")
        self.rm_body = tk.Frame(page, bg=P1)
        self.rm_body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        # ---- One at a Time
        one = self.rm_one = tk.Frame(self.rm_body, bg=P1)
        nrow = self.rm_nrow = tk.Frame(one, bg=P1)          # the Drawer: search, then the set as a drop-down
        self._rm_search(nrow).pack(side="left", fill="x", expand=True)
        self.rm_pick_btn = ttk.Button(nrow, text="", style="Quiet.TButton", command=lambda: self.rm_set_menu(
            self.rm_pick_btn))
        self.rm_pick_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.rm_pick_btn, "Which items to rate: a set, and how many of its mods you've rated")
        left = self.rm_left = tk.Frame(one, bg=P2, width=LEFT_W, highlightthickness=1, highlightbackground=C["line"])
        left.pack_propagate(False)
        self._rm_search(left).pack(fill="x", padx=8, pady=8)
        lsb = ttk.Scrollbar(left, orient="vertical")
        self.rm_setcv = StratCanvas(left, self, self._rm_draw_sets)
        self.rm_setcv.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        lsb.config(command=self.rm_setcv.yview)
        self.rm_setcv.attach_scrollbar(lsb)
        right = self.rm_right = tk.Frame(one, bg=P1)
        csb = ttk.Scrollbar(right, orient="vertical")
        self.rm_cardcv = StratCanvas(right, self, self._rm_draw_card)
        self.rm_cardcv.pack(side="left", fill="both", expand=True)
        csb.config(command=self.rm_cardcv.yview)
        self.rm_cardcv.attach_scrollbar(csb)
        # ---- Table (the Map Library's browse layout: search, chips, rows grouped, a side panel for the picked mod)
        tab = self.rm_tab = tk.Frame(self.rm_body, bg=P1)
        tools = tk.Frame(tab, bg=P1)
        tools.pack(fill="x", pady=(0, 8))
        self._rm_search(tools).pack(side="left")
        self.rm_one_btn = ttk.Button(tools, text="Rate mods one at a time", style="Primary.TButton",
                                     command=lambda: self.rm_view_pick("One at a Time"))
        self.rm_one_btn.pack(side="right")
        Tooltip(self.rm_one_btn, "Goes through the mods you haven't rated, one at a time")
        chips = tk.Frame(tab, bg=P1)
        chips.pack(fill="x", pady=(0, 8))
        tk.Label(chips, text="SHOW", bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self.rm_chips = {}
        for f in FILTERS:
            b = tk.Label(chips, text=f, font=("Segoe UI", 9), padx=12, pady=4, cursor="hand2", highlightthickness=1)
            b.pack(side="left", padx=(8, 0))
            b.bind("<Button-1>", lambda e, f=f: self.rm_filter_pick(f))
            Tooltip(b, {"Not rated": "Mods you haven't rated yet", "Rated": "Mods you've rated",
                        "All": "Every mod shown here"}[f])
            self.rm_chips[f] = b
        tk.Label(chips, text="ITEMS", bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(side="left",
                                                                                           padx=(16, 0))
        self.rm_tset = ttk.Button(chips, text="", style="Quiet.TButton", command=lambda: self.rm_set_menu(self.rm_tset))
        self.rm_tset.pack(side="left", padx=(8, 0))
        Tooltip(self.rm_tset, "Which items to rate: a set, and how many of its mods you've rated")
        from .style import flowify
        flowify(tools)
        flowify(chips)
        bulk = tk.Frame(tab, bg=P2, highlightthickness=1, highlightbackground=C["line"], padx=12, pady=8)
        bulk.pack(fill="x", pady=(0, 8))
        tk.Label(bulk, text="Rate selected:", bg=P2, fg=C["text"], font=("Segoe UI", 9)).pack(side="left",
                                                                                            padx=(0, 4))
        self.rm_bulk = {}
        for gi, (word, grades) in enumerate(GROUPS):
            for g in grades:
                b = ttk.Button(bulk, text=_letter(g), width=3, command=lambda g=g: self.rm_bulk_rate(g))
                b.pack(side="left", padx=(12 if gi and g == grades[0] else 4, 0))
                Tooltip(b, F_TIP if g == "ignore" else f"{g}: {RM.MEANING[word]} ({word})")
                self.rm_bulk[g] = b
        self.rm_bulk_n = tk.Label(bulk, text="none selected", bg=P2, fg=C["muted"], font=("Segoe UI", 9))
        self.rm_bulk_n.pack(side="right")
        holder = self.rm_tholder = tk.Frame(tab, bg=P1)
        holder.pack(fill="both", expand=True)
        self.rm_side = tk.Frame(holder, bg=P1, width=330)
        self.rm_side.pack_propagate(False)
        ssb = ttk.Scrollbar(self.rm_side, orient="vertical")
        self.rm_sidecv = StratCanvas(self.rm_side, self, self._rm_draw_side)
        self.rm_sidecv.pack(side="left", fill="both", expand=True)
        ssb.config(command=self.rm_sidecv.yview)
        self.rm_sidecv.attach_scrollbar(ssb)
        tsb = ttk.Scrollbar(holder, orient="vertical")
        self.rm_tablecv = StratCanvas(holder, self, self._rm_draw_table)
        self.rm_tablecv.pack(side="left", fill="both", expand=True)
        tsb.config(command=self.rm_tablecv.yview)
        self.rm_tablecv.attach_scrollbar(tsb)
        self.rm_tpick, self.rm_tgo, self.rm_cat = None, {}, None
        # ---- keys (on the page and the card, never in a search box)
        for k, g in (("s", "S"), ("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"), ("f", "ignore"), ("i", "ignore")):
            for w in (page, self.rm_cardcv):
                w.bind(k, lambda e=None, g=g: self.rm_key_rate(g))
        for w in (page, self.rm_cardcv):
            w.bind("<Right>", lambda e=None: self.rm_step(1))
            w.bind("<Left>", lambda e=None: self.rm_step(-1))
        page.bind("<Button-1>", lambda e: page.focus_set(), add="+")
        self.rm_cardcv.bind("<Button-1>", lambda e: self.rm_cardcv.focus_set(), add="+")
        self.rm_qv.trace_add("write", lambda *a: self._rm_query_soon())
        page.bind("<Configure>", self._rm_resized, add="+")
        self.rm_rated, self.rm_rated_keys = 0, set()
        self._rm_layout(False)
        self._rm_show_view()
        self._rm_paint_chips()
        self._rm_paint_bulk()
        return page

    def _rm_search(self, parent):
        """A search box (all three share the one search): ⌕, the words, a hint while empty; Esc clears it."""
        bg = C["odd"]
        box = tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=C["line"])
        tk.Label(box, text="⌕", bg=bg, fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        ent = tk.Entry(box, textvariable=self.rm_qv, bg=bg, fg=C["text"], insertbackground=C["text"], relief="flat",
                       font=("Segoe UI", 9), highlightthickness=0, bd=0, width=26)
        ent.pack(side="left", fill="x", expand=True, padx=(4, 8), ipady=4)
        ph = tk.Label(box, text=SEARCH_HINT, bg=bg, fg=C["muted"], font=("Segoe UI", 9))
        ph.bind("<Button-1>", lambda e: ent.focus_set())

        def hint(_e=None):
            try:
                if self.rm_qv.get() or ent.focus_get() is ent:
                    ph.place_forget()
                else:
                    ph.place(in_=ent, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            ent.bind(ev, hint, add="+")
        self.rm_qv.trace_add("write", lambda *a: hint())
        ent.bind("<Escape>", lambda e: (self.rm_qv.set(""), "break")[1])
        ent.after(200, hint)
        Tooltip(box, "Find a mod by its words, or a set by its name")
        box.entry = ent
        self.__dict__.setdefault("rm_searches", []).append(ent)
        return box

    # ---- shape: the Drawer's narrow page puts the set list in a drop-down
    def _rm_resized(self, e):
        if e.widget is not self.rm_page:
            return
        narrow = e.width < NARROW
        if narrow != self.rm_narrow:
            self._rm_layout(narrow)

    def _rm_layout(self, narrow):
        self.rm_narrow = narrow
        for w in (self.rm_nrow, self.rm_left, self.rm_right):
            w.pack_forget()
        if narrow:
            self.rm_nrow.pack(fill="x", pady=(0, 8))
        else:
            self.rm_left.pack(side="left", fill="y")
        self.rm_right.pack(side="left", fill="both", expand=True, padx=(0 if narrow else 16, 0))
        side = getattr(self, "rm_side", None)
        if side is not None:                                  # (the Drawer: no side panel - a row opens its card)
            side.pack_forget()
            if not narrow:
                side.pack(side="right", fill="y", padx=(16, 0), before=self.rm_tablecv)

    def rm_view_pick(self, view):
        self.rm_view = view
        from .config import SETTINGS
        SETTINGS["rate_view"] = view
        if self.rm_seg.get() != view:
            self.rm_seg.pick(view, notify=False)
        self._rm_show_view()
        self._rm_redraw()

    def _rm_show_view(self):
        if self.rm_view == "Table":
            self.rm_one.pack_forget()
            self.rm_tab.pack(fill="both", expand=True)
        else:
            self.rm_tab.pack_forget()
            self.rm_one.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- showing it
    def rm_on_show(self):
        """The page came up: counts again (they change as you price check), the last set picked."""
        self.__dict__["_rm_ent"] = {}
        self._rm_recount_all()
        if not getattr(self, "rm_set", None):
            from .config import SETTINGS
            sets = dict(self.rm_sets())
            last = SETTINGS.get("rate_set")
            self.rm_pick(last if last in sets else next(iter(sets)))
        else:
            self.rm_load(keep=True)
        try:
            self.rm_page.focus_set()
        except (AttributeError, tk.TclError):
            pass

    def rm_open(self, set_name=None):
        """Mods › Rate Mods (set_name: straight to that set - the Mod Book's button)."""
        if getattr(self, "rm_page", None) is None:
            return None
        self.shell.open("ratemods")
        if set_name:
            self.rm_pick(set_name)
        return self.rm_page

    def _rm_recount_all(self):
        self.rm_counts, self.rm_texts = {}, {}
        for s, _l in self.rm_sets():
            self._rm_recount(s)

    def _rm_recount(self, s):
        """A set's (rated, mods) and its mods' words (what the search looks in)."""
        if not s:
            return
        q = self.rm_queue(s)
        self.__dict__.setdefault("rm_counts", {})[s] = (sum(1 for keys, _t in q if RM.current(keys) is not None),
                                                        len(q))
        self.__dict__.setdefault("rm_texts", {})[s] = " | ".join(t for _k, t in q).lower()

    def rm_fill_list(self):
        """(the set list is drawn on its canvas - kept for callers from before)"""
        self._rm_recount_all()
        self.rm_setcv.later()

    def rm_pick(self, set_name, cat=None):
        from .config import SETTINGS
        self.rm_cat = cat
        SETTINGS["rate_set"] = set_name
        self.rm_set = set_name
        self.rm_set_label = RM.set_label(set_name)
        if set_name.startswith("gear:"):
            self.rm_fold.add(RM.gear_kind(set_name[5:]))
        self.rm_ticked.clear()
        self.rm_tpick = None
        self.rm_load()

    def _rm_match(self, e, q):
        return q in e["text"].lower() or q in e["game"].lower()

    def rm_visible(self, s, label):
        """Does a set show for the search? (its name, or one of its mods)"""
        q = self.rm_qv.get().strip().lower()
        if not q or q in label.lower():
            return True
        return q in self.__dict__.get("rm_texts", {}).get(s, "")

    def rm_load(self, keep=False):
        """The picked set's mods for the search (the ones you haven't rated first); the card at the first unrated."""
        s = self.rm_set
        if not s:
            return
        q = self.rm_qv.get().strip().lower()
        ents = self.rm_entries(s)
        cat = getattr(self, "rm_cat", None)
        if cat:                                                # (a category picked in the set list)
            ents = [e for e in ents if e.get("cat") == cat]
        self.rm_q = ents if not q or q in self.rm_set_label.lower() else [e for e in ents if self._rm_match(e, q)]
        if not keep:
            cur = [i for i, e in enumerate(self.rm_q) if RM.current(e["keys"]) is None]
            self.rm_i = cur[0] if cur else 0
        self.rm_i = max(0, min(self.rm_i, len(self.rm_q) - 1)) if self.rm_q else 0
        self.rm_ticked &= {tuple(e["keys"]) for e in self.rm_q}
        self._rm_redraw()

    def _rm_query_soon(self):
        job = getattr(self, "_rm_qjob", None)
        if job:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._rm_qjob = self.root.after(150, self._rm_query)

    def _rm_query(self):
        self._rm_qjob = None
        vis = [s for s, lab in self.rm_sets() if self.rm_visible(s, lab)]
        if vis and self.rm_set not in vis:
            self.rm_set = None
            self.rm_pick(vis[0])
            return
        self.rm_load()

    def _rm_redraw(self):
        for cv in ("rm_setcv", "rm_cardcv", "rm_tablecv", "rm_sidecv"):
            w = getattr(self, cv, None)
            if w is not None:
                w.later()
        self._rm_paint_note()
        self._rm_paint_chips()
        self._rm_paint_bulk()

    def _rm_paint_note(self):
        s = self.rm_set
        if not s:
            return
        rated, n = self.rm_counts.get(s, (0, 0)) if hasattr(self, "rm_counts") else (0, 0)
        lab = self.rm_set_label
        set_cfg(self.rm_note, text=f"{rated} of {n} {lab} mods rated" if self.rm_view != "Table"
                else f"Set: {lab} · {n} mods")
        pick = f"{lab} · {rated} of {n} ▾"
        set_cfg(self.rm_pick_btn, text=pick)
        set_cfg(self.rm_tset, text=pick)

    def rm_set_menu(self, btn):
        """The sets as a drop-down (the Drawer, and the Table view): grouped, each with how many you've rated."""
        menu = tk.Menu(self.root, tearoff=0)
        for title, items in self.rm_groups():
            menu.add_command(label=title, state="disabled")
            for it in items:
                if len(it) == 3:
                    for s, lab in it[2]:
                        self._rm_menu_row(menu, s, f"{it[1]} › {lab}")
                else:
                    self._rm_menu_row(menu, *it)
        self.rm_menu_open = menu
        try:
            menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        except tk.TclError:
            pass
        finally:
            menu.grab_release()
        return menu

    def _rm_menu_row(self, menu, s, lab):
        if not self.rm_visible(s, lab):
            return
        r, n = self.rm_counts.get(s, (0, 0))
        mark = "▸ " if s == self.rm_set else "    "
        menu.add_command(label=f"{mark}{lab}    {r} of {n} rated" + (" ✓" if n and r == n else ""),
                         command=lambda s=s: self.rm_pick(s))

    # ---------------------------------------------------------------- the set list (One at a Time, left)
    def _rm_draw_sets(self, cv):
        w = max(cv.winfo_width(), 120)
        y = 0
        for title, items in self.rm_groups():
            shown = []
            for it in items:
                if len(it) == 3:
                    kids = [(s, lab) for s, lab in it[2] if self.rm_visible(s, lab)]
                    if kids:
                        shown.append((it[0], it[1], kids))
                elif self.rm_visible(*it):
                    shown.append(it)
            if not shown:
                continue
            cv.text(8, y + 8, title, F_CAP, fill=cv.c("text_muted"))
            y += 28
            for it in shown:
                if len(it) == 3:
                    y = self._rm_draw_kind(cv, it, y, w)
                else:
                    y = self._rm_set_row(cv, it[0], it[1], 0, y, w)
        if y == 0:
            cv.text(8, 8, "No set or mod matches the search.", F_SMALL, fill=cv.c("text_muted"), width=w - 16)
            y = 40
        return y + 8

    def _rm_draw_kind(self, cv, it, y, w):
        kind, title, kids = it
        q = bool(self.rm_qv.get().strip())
        opened = kind in self.rm_fold or q
        r = sum(self.rm_counts.get(s, (0, 0))[0] for s, _l in kids)
        n = sum(self.rm_counts.get(s, (0, 0))[1] for s, _l in kids)
        tag = f"kind:{kind}"
        cv.card(2, y, w - 4, y + 32, tag=tag, fill=cv.c("surface_raised"), outline=cv.c("border"), r=8)
        cv.text(12, y + 16, ("▾ " if opened else "▸ ") + title, F_BODY, anchor="w", tags=(tag,))
        cv.text(w - 12, y + 16, f"{len(kids)} sets · {r} of {n} rated", F_SMALL, fill=cv.c("text_muted"), anchor="e",
                tags=(tag,))
        cv.acts[tag] = lambda k=kind: self.rm_fold_flip(k)
        cv.tips[tag] = f"{'Fold' if opened else 'Open'} the {title} sets"
        y += 36
        if not opened:
            return y
        top = y
        for s, lab in kids:
            y = self._rm_set_row(cv, s, lab, 16, y, w)
        cv.create_line(10, top, 10, y - 4, fill=cv.c("border"))
        return y + 4

    def rm_fold_flip(self, kind):
        self.rm_fold.symmetric_difference_update({kind})
        self.rm_setcv.later(0)

    def _rm_set_row(self, cv, s, lab, ind, y, w):
        r, n = self.rm_counts.get(s, (0, 0))
        on = s == self.rm_set
        tag = f"set:{s}"
        x0, x1 = 2 + ind, w - 4
        fill = cv.c("selection") if on else cv.c("surface")
        cv.card(x0, y, x1, y + 40, tag=tag, fill=fill, outline=cv.c("accent") if on else fill, r=8)
        ink = cv.c("text_strong") if on else cv.c("text")
        pic = self.rm_pic(s, None, 24)
        nx = x0 + 10
        if pic is not None:                                   # the item's picture, before its name
            cv.create_image(nx, y + 15, image=pic, anchor="w", tags=(tag,))
            nx += 30
        cv.text(nx, y + 7, ("▸ " if on else "") + lab, F_BOLD if on else F_BODY, fill=ink, tags=(tag,))
        cv.text(x1 - 10, y + 8, f"{r} of {n} rated" + (" ✓" if n and r == n else ""), F_SMALL,
                fill=cv.c("text_muted"), anchor="ne", tags=(tag,))
        bx0, bx1, by = nx, x1 - 10, y + 30
        cv.create_rectangle(bx0, by, bx1, by + 3, fill=cv.c("surface_high"), outline="", tags=(tag,))
        if n and r:
            cv.create_rectangle(bx0, by, bx0 + max(2, int((bx1 - bx0) * r / n)), by + 3, outline="", tags=(tag,),
                                fill=cv.c("accent") if on else cv.c("text_muted"))
        cv.acts[tag] = lambda s=s: self.rm_pick(s)
        cv.tips[tag] = f"{r} of {n} {lab} mods rated by you"
        y += 42
        if on and not s.startswith(("gear:", "unique:")):     # its categories, each with its progress
            y = self._rm_cat_rows(cv, s, x0 + 14, x1, y)
        return y

    def _rm_cat_rows(self, cv, s, x0, x1, y):
        cats = {}
        for e in self.rm_entries(s):
            c = cats.setdefault(e.get("cat") or "", [0, 0])
            c[1] += 1
            c[0] += RM.current(e["keys"]) is not None
        names = sorted(cats, key=lambda g: (g.startswith("All "), g.lower()))
        if len(names) < 2:
            return y
        top = y
        for name in names:
            r, n = cats[name]
            on = name == self.rm_cat
            tag = f"cat:{s}:{name}"
            cv.card(x0, y, x1, y + 30, tag=tag, fill=cv.c("surface_high") if on else cv.c("surface"),
                    outline=cv.c("surface_high") if on else cv.c("surface"), r=6)
            cv.text(x0 + 10, y + 6, ("▸ " if on else "") + name, F_BOLD if on else F_SMALL, tags=(tag,),
                    fill=cv.c("text_strong") if on else cv.c("text"))
            cv.text(x1 - 8, y + 6, f"{r} of {n}" + (" ✓" if n and r == n else ""), F_SMALL, anchor="ne",
                    fill=cv.c("text_muted"), tags=(tag,))
            cv.create_rectangle(x0 + 10, y + 24, x1 - 8, y + 26, fill=cv.c("surface_high"), outline="", tags=(tag,))
            if r:
                cv.create_rectangle(x0 + 10, y + 24, x0 + 10 + max(2, int((x1 - x0 - 18) * r / n)), y + 26,
                                    fill=cv.c("accent") if on else cv.c("text_muted"), outline="", tags=(tag,))
            cv.acts[tag] = lambda s=s, name=name: self.rm_pick_cat(s, name)
            cv.tips[tag] = f"{r} of {n} {name} mods rated by you" + (" - click again for the whole set" if on else "")
            y += 32
        cv.create_line(x0 - 6, top, x0 - 6, y - 2, fill=cv.c("border"))
        return y + 6

    def rm_pick_cat(self, s, name):
        """A category in the set list: only its mods on the card (again: the whole set)."""
        self.rm_pick(s, None if (s == self.rm_set and self.rm_cat == name) else name)

    # ---------------------------------------------------------------- the card (One at a Time, right)
    def rm_current(self):
        """The mod on the card: its entry, or None."""
        if not self.rm_q:
            return None
        return self.rm_q[max(0, min(self.rm_i, len(self.rm_q) - 1))]

    def rm_roll_key(self, e=None):
        """The rule key By roll is about on this card (a mod with three tier groups here), or None."""
        e = e or self.rm_current()
        if not e or len(e["keys"]) != 1 or not self.rm_set:
            return None
        return e["keys"][0] if RM.roll_groups(self.rm_set, e["keys"][0]) else None

    def rm_roll_state(self, key):
        """"same" (every group takes the mod's letter - the default) or "differs"."""
        return "same" if RM.same_for_every_roll(key) else "differs"

    def _rm_btn(self, cv, x, y, w, h, label, tag, fn, on=False, off=False, font=F_BODY, tip=None, r=8):
        """A canvas button: off = grayed out (no click); on = picked (a ✓ and a stronger edge, not color alone)."""
        if off:
            fill, line, ink = cv.c("surface"), cv.c("border"), cv.c("text_muted")
        elif on:
            fill, line, ink = cv.c("selection"), cv.c("text_strong"), cv.c("text_strong")
        else:
            fill, line, ink = cv.c("surface_raised"), cv.c("border_light"), cv.c("text")
        cv.card(x, y, x + w, y + h, tag=tag, fill=fill, outline=line, r=r, width=2 if on else 1, lift=not off)
        cv.text(x + w / 2, y + h / 2, label, font, fill=ink, anchor="center", tags=(tag,))
        if on:
            cv.text(x + w - 6, y + 4, "✓", F_SMALL, fill=ink, anchor="ne", tags=(tag,))
        if not off:
            cv.acts[tag] = fn
        if tip:
            cv.tips[tag] = tip
        return x + w

    def _rm_draw_card(self, cv):
        W = max(cv.winfo_width(), 320)
        narrow = W < 560
        pad = 16 if narrow else 24
        x0, x1 = 1, W - 2
        e = self.rm_current()
        y = 16 if narrow else 20
        lab = self.rm_set_label or ""
        n = len(self.rm_q)
        pic = self.rm_pic(self.rm_set, e, 40)
        tx = x0 + pad
        if pic is not None:                                   # the item's picture, left of the set name
            cv.create_image(tx, y + 12, image=pic, anchor="w")
            tx += 48
        cv.text(tx, y + 12, lab + (f" · {self.rm_cat}" if getattr(self, "rm_cat", None) else ""), F_HEAD,
                fill=cv.c("text_strong"), anchor="w")
        if e:
            y = self._rm_progress(cv, x1 - pad, y, n, narrow)
        y += 40
        if not e:
            return self._rm_card_empty(cv, x0, x1, y, pad)
        keys = e["keys"]
        cur = RM.current(keys)
        # the mod, as the game words it
        tw = x1 - x0 - 2 * pad - 32
        t = cv.text((x0 + x1) / 2, y + 20, e["game"], F_MOD if not narrow else F_MOD_S, fill=cv.c("magic"),
                    anchor="n", width=tw)
        cv.itemconfigure(t, justify="center")
        th = cv.bottom(t, y + 40) - (y + 20)
        box = cv.card(x0 + pad, y, x1 - pad, y + th + 40, fill=cv.c("surface_sunken"), outline=cv.c("border"),
                      lift=False, r=12)
        cv.tag_lower(box, t)
        y += th + 40 + 12
        y = self._rm_rolls(cv, e, (x0 + x1) / 2, y, x1 - x0 - 2 * pad)
        y = self._rm_facts(cv, e, cur, x0 + pad, x1 - pad, y, narrow)
        key = self.rm_roll_key(e)
        if key:
            y = self._rm_byroll(cv, key, cur, x0 + pad, x1 - pad, y, narrow)
        y = self._rm_rate_row(cv, cur, (x0 + x1) / 2, y, narrow)
        # Back · Skip
        bw, gap = 96, 12
        bx = (x0 + x1) / 2 - bw - gap / 2
        last = self.rm_i >= n - 1
        self._rm_btn(cv, bx, y, bw, 32, "‹ Back", "nav:back", lambda: self.rm_step(-1), off=self.rm_i <= 0,
                     tip="The mod before this one (←)")
        self._rm_btn(cv, bx + bw + gap, y, bw, 32, "Skip", "nav:skip", lambda: self.rm_step(1), off=last,
                     tip="The next mod, without rating this one (→)")
        y += 32 + 16
        rated, total = self.rm_counts.get(self.rm_set, (0, 0))
        if total and rated == total:
            cv.text((x0 + x1) / 2, y + 4, f"✓ All {total} rated - thanks!", F_SMALL, fill=cv.c("good"), anchor="n")
            y += 24
        y += 8
        self._rm_under(cv, x0, x1, y)
        cv.text(x0 + 4, y + 8, KEYS_LINE, F_SMALL, fill=cv.c("text_muted"))
        return self._rm_below(cv, x0, x1, y + 36, narrow)

    def _rm_progress(self, cv, xr, y, n, narrow):
        """Top right of the card: "13 of 86 · 15%" over a thin warm bar, "12 rated today" beside it."""
        i = self.rm_i + 1
        txt = f"{i} of {n} · {round(100 * i / max(1, n))}%"
        cv.text(xr, y + 4, txt, F_SMALL, fill=cv.c("text"), anchor="ne", tags=("prog",))
        bw = max(96, cv.tw(txt, F_SMALL))
        cv.create_rectangle(xr - bw, y + 22, xr, y + 25, fill=cv.c("surface_high"), outline="", tags=("prog",))
        cv.create_rectangle(xr - bw, y + 22, xr - bw + max(2, int(bw * i / max(1, n))), y + 25,
                            fill=cv.c("money"), outline="", tags=("prog",))
        cv.tips["prog"] = f"Mod {i} of the {n} shown here"
        today = RM.rated_today()
        if today:
            tt = f"{today} rated today"
            if narrow:
                cv.text(xr, y + 30, tt, F_SMALL, fill=cv.c("text_muted"), anchor="ne", tags=("today",))
            else:
                cv.text(xr - bw - 16, y + 4, tt, F_SMALL, fill=cv.c("text_muted"), anchor="ne", tags=("today",))
            cv.tips["today"] = "Mods you rated today, in every set"
        return y

    def rm_pic(self, s, e=None, px=28):
        """The item's picture for a set (a mod's own tablet type when it rolls on one only) - only one the app
        already has on this PC (the price checks' picture cache): nothing is downloaded for it. None: no picture."""
        url = self.rm_pic_url(s, e)
        if not url:
            return None
        try:
            import os
            if not os.path.exists(self._pc_art_path(url)):
                return None
            return self.pc_art(url, px)
        except Exception:
            buglog.caught()
            return None

    def rm_pic_url(self, s, e=None):
        try:
            from .pricecheck_page import art_url, icons
        except Exception:
            return None
        rolls = [r for r in (e or {}).get("rolls") or [] if r != "All types"]
        if s == "tablet":
            return art_url(f"{rolls[0]} Tablet" if len(rolls) == 1 else "Irradiated Tablet")
        if s == "waystone":
            return art_url("Waystone")
        ic = icons()
        if s.startswith("unique:"):
            return ic.get(RM.set_label(s))
        if s == "jewel" and rolls and ic.get(rolls[0]):
            return ic[rolls[0]]
        by = self.__dict__.get("_rm_pics")
        if by is None or by[0] != len(ic):                    # a picture per set: the lowest base of that class the
            from .gearbook import base_cat                    # app has a picture of - never a unique's own art
            from .pricecheck_page import unique_art
            lv = base_levels()
            best = {}
            for base, url in ic.items():
                if not str(url).startswith("https://") or unique_art(url):
                    continue
                try:
                    c = base_cat(base)
                except Exception:
                    c = None
                if not c:
                    continue
                rank = (lv.get(base, 999), base.startswith("Runeforged"), base)
                if c not in best or rank < best[c][0]:
                    best[c] = (rank, url)
            by = self.__dict__["_rm_pics"] = (len(ic), {c: u for c, (_r, u) in best.items()})
        return by[1].get(s)

    def _rm_below(self, cv, x0, x1, y, narrow):
        """Under the card: Next up (the next 3 mods - click one to go there) and Just rated (the last 5 - click one to
        change its letter)."""
        gap = 16
        cols = 1 if narrow else 2
        w = (x1 - x0 - gap * (cols - 1)) / cols
        nxt = self.rm_q[self.rm_i + 1:self.rm_i + 4]
        recent = list(self.__dict__.get("rm_recent", []))[:5]
        top, bottoms = y, []
        for ci, (title, rows) in enumerate((("NEXT UP", nxt), ("JUST RATED", recent))):
            bx0 = x0 + (ci % cols) * (w + gap)
            by0 = top if cols == 2 else (bottoms[-1] + 12 if bottoms else top)
            cv.text(bx0 + 12, by0 + 12, title, F_CAP, fill=cv.c("text_muted"))
            yy = by0 + 34
            if not rows:
                cv.text(bx0 + 12, yy, "That's the last one here." if ci == 0 else "The mods you rate show here.",
                        F_SMALL, fill=cv.c("text_muted"))
                yy += 22
            for ri, r in enumerate(rows):
                tag = f"{'next' if ci == 0 else 'recent'}:{ri}"
                tx = bx0 + 12
                if ci == 1:
                    g = RM.current(r["keys"])
                    tx = self._rm_pill(cv, tx, yy + 9, g, tag) + 8
                cv.text(tx, yy + 9, cv.fit(r["game"], F_SMALL, bx0 + w - tx - 12), F_SMALL, anchor="w", tags=(tag,),
                        fill=cv.c("text_muted") if ci == 0 else cv.c("text"))
                hit = cv.create_rectangle(bx0 + 4, yy - 2, bx0 + w - 4, yy + 20, fill=cv.c("surface"), outline="",
                                          tags=(tag,))
                cv.tag_lower(hit)
                if ci == 0:
                    cv.acts[tag] = lambda i=self.rm_i + 1 + ri: self.rm_jump(i)
                    cv.tips[tag] = "Go to this mod"
                else:
                    cv.acts[tag] = lambda r=r, tag=tag: self.rm_row_menu(r, *cv.at_root(tag))
                    cv.tips[tag] = f"{RM.set_label(r.get('set') or '')}: click to change your letter"
                yy += 26
            bottoms.append(yy + 6)
            cv.tag_lower(cv.card(bx0, by0, bx0 + w, yy + 6, fill=cv.c("surface"), outline=cv.c("border"), r=10,
                                 lift=False))
        return max(bottoms) + 12

    def _rm_pill(self, cv, x, cy, g, tag):
        """A letter pill: the letter's color with its letter (a dashed outline: not rated). -> its right edge."""
        if g is None:
            cv.create_rectangle(x, cy - 9, x + 26, cy + 9, outline=cv.c("border_light"), dash=(3, 2), fill="",
                                tags=(tag,))
            cv.text(x + 13, cy, "–", F_SMALL, anchor="center", fill=cv.c("text_muted"), tags=(tag,))
            return x + 26
        col = letter_color(g)
        cv.card(x, cy - 9, x + 26, cy + 9, fill=col, outline=col, r=8, lift=False, tag=tag)
        cv.text(x + 13, cy, _letter(g), F_CAP, anchor="center", fill=text_on(col), tags=(tag,))
        return x + 26

    def rm_jump(self, i):
        self.rm_i = max(0, min(i, len(self.rm_q) - 1))
        self.rm_cardcv.later(0)

    @staticmethod
    def _rm_under(cv, x0, x1, y):
        """The card behind what was drawn (drawn last, once its height is known, and put at the bottom)."""
        bg = cv.card(x0, 1, x1, y, fill=cv.c("surface_raised"), outline=cv.c("border"), lift=False, r=12)
        cv.tag_lower(bg)
        return bg

    def _rm_card_empty(self, cv, x0, x1, y, pad):
        """What it is + one button."""
        q = self.rm_qv.get().strip()
        msg = f"No mod in this set matches “{q}”." if q else "Nothing to rate here yet: price check one of these first."
        t = cv.text((x0 + x1) / 2, y + 16, msg, F_BODY, fill=cv.c("text_muted"), anchor="n", width=x1 - x0 - 2 * pad)
        y = cv.bottom(t, y + 32) + 16
        bw = 140
        if q:
            self._rm_btn(cv, (x0 + x1 - bw) / 2, y, bw, 32, "Clear search", "empty:clear", lambda: self.rm_qv.set(""))
        else:
            self._rm_btn(cv, (x0 + x1 - bw) / 2, y, bw, 32, "Price Checks", "empty:pc",
                         lambda: self.shell.open("pricecheck"))
        y += 48
        self._rm_under(cv, x0, x1, y)
        return y + 8

    def _rm_rolls(self, cv, e, cx, y, width):
        rolls = list(e.get("rolls") or [])
        if not rolls:
            return y
        shown, more = rolls[:4], rolls[4:]
        chips = shown + ([f"+{len(more)} more"] if more else [])
        lab = "Rolls on:"
        ws = [cv.tw(c, F_SMALL) + 22 for c in chips]
        total = cv.tw(lab, F_SMALL) + 8 + sum(ws) + 6 * (len(ws) - 1)
        while total > width and len(chips) > 2:                 # (the Drawer: fewer chips, the rest on hover)
            more = shown[-1:] + more
            shown = shown[:-1]
            chips = shown + [f"+{len(more)} more"]
            ws = [cv.tw(c, F_SMALL) + 22 for c in chips]
            total = cv.tw(lab, F_SMALL) + 8 + sum(ws) + 6 * (len(ws) - 1)
        x = cx - total / 2
        cv.text(x, y + 11, lab, F_SMALL, fill=cv.c("text_muted"), anchor="w")
        x += cv.tw(lab, F_SMALL) + 8
        tip = {"tablet": "A tablet type that can roll this mod", "jewel": "A jewel that can roll this mod",
               "waystone": "Waystone tiers that can roll this mod", "relic": "A relic size that can roll this mod"}
        for i, (c, w) in enumerate(zip(chips, ws)):
            tag = f"roll:{i}"
            cv.card(x, y, x + w, y + 22, tag=tag, fill=cv.c("surface_high"), outline=cv.c("border_light"), r=10,
                    lift=False)
            cv.text(x + w / 2, y + 11, c, F_SMALL, anchor="center", tags=(tag,))
            if c.startswith("+") and more:
                cv.tips[tag] = "Also rolls on: " + ", ".join(more)
            else:
                cv.tips[tag] = tip.get(self.rm_set, "An item class that can roll this mod")
            x += w + 6
        return y + 22 + 16

    def _rm_facts(self, cv, e, cur, x0, x1, y, narrow):
        """Seen in listings · Players · Your rating - each says how it was worked out on hover."""
        s = RM.seen(self.rm_set, e["keys"])
        p = RM.players(e["keys"])
        facts = (("SEEN IN LISTINGS", f"{RM.div_text(s[0])} div middle · {s[1]} listing{'s' if s[1] != 1 else ''}"
                  if s else "–", RM.seen_tip(self.rm_set, s)),
                 ("PLAYERS", RM.players_text(p), RM.players_tip(p)),
                 ("YOUR RATING", RM.grade_text(cur),
                  f"You rated it {RM.grade_text(cur)}: {RM.MEANING[RM.GRADE_WORD[cur]]}." if cur else
                  "You haven't rated this mod. Press S A B C D or F."))
        gap = 8
        if narrow:
            for i, (lab, val, tip) in enumerate(facts):
                tag = f"fact:{i}"
                cv.card(x0, y, x1, y + 30, tag=tag, fill=cv.c("surface"), outline=cv.c("border"), r=8, lift=False)
                cv.text(x0 + 10, y + 15, lab, F_CAP, fill=cv.c("text_muted"), anchor="w", tags=(tag,))
                cv.text(x1 - 10, y + 15, val, F_BODY, anchor="e", tags=(tag,))
                cv.tips[tag] = tip
                y += 30 + 6
            return y + 10
        fw = (x1 - x0 - 2 * gap) / 3
        for i, (lab, val, tip) in enumerate(facts):
            tag = f"fact:{i}"
            fx = x0 + i * (fw + gap)
            cv.card(fx, y, fx + fw, y + 52, tag=tag, fill=cv.c("surface"), outline=cv.c("border"), r=8, lift=False)
            cv.text(fx + 12, y + 9, lab, F_CAP, fill=cv.c("text_muted"), tags=(tag,))
            cv.text(fx + 12, y + 27, cv.fit(val, F_BODY, fw - 24), F_BODY, tags=(tag,))
            cv.tips[tag] = tip
        return y + 52 + 18

    def _rm_byroll(self, cv, key, cur, x0, x1, y, narrow):
        """MIX B: Top / Middle / Low rolls side by side (stacked in the Drawer) - each its tiers and values, its own
        S A B C D F and what that letter means; Same for every roll. A letter for each of the three rates the mod
        and moves on to the next one."""
        cx = (x0 + x1) / 2
        cv.text(cx, y, QUESTION, F_BODY, fill=cv.c("text_muted"), anchor="n")
        y += 26
        groups = RM.roll_groups(self.rm_set, key)
        gap = 10
        cols = 3 if (x1 - x0 - 2 * gap) / 3 >= 140 else 1          # (stacked in a very narrow Drawer)
        bw = (x1 - x0 - gap * (cols - 1)) / cols
        lgap = 4 if bw >= 180 else 3
        lw = max(18, min(24, int((bw - 16 - 5 * lgap) / 6)))
        top = y
        for i, g in enumerate(groups):
            gx = x0 + (i % cols) * (bw + gap)
            gy = top if cols == 3 else y
            grade = g["grade"] or cur
            h = 108
            cv.card(gx, gy, gx + bw, gy + h, fill=cv.c("surface"), outline=cv.c("border"), r=8, lift=False)
            cv.text(gx + bw / 2, gy + 8, g["name"], F_BOLD, anchor="n")
            cv.text(gx + bw / 2, gy + 28, RM.group_range(g, key), F_SMALL, fill=cv.c("text_muted"), anchor="n")
            lx = gx + (bw - (6 * lw + 5 * lgap)) / 2
            for gg, lab in SHOWN:
                tag = f"grp:{i}:{gg}"
                on = gg == grade
                col = letter_color(gg)
                cv.card(lx, gy + 48, lx + lw, gy + 48 + lw, tag=tag, r=5, width=2 if on else 1,
                        fill=col if on else cv.c("surface_raised"),
                        outline=cv.c("text_strong") if on else cv.c("border_light"))
                cv.text(lx + lw / 2, gy + 48 + lw / 2, lab, F_CAP, anchor="center", tags=(tag,),
                        fill=text_on(col) if on else cv.c("text_muted"))
                cv.acts[tag] = lambda i=i, gg=gg: self.rm_group_pick(key, i, gg)
                cv.tips[tag] = f"{g['name']}: {lab} - " + ("left out of searches" if gg == "ignore" else
                                                             RM.MEANING[RM.GRADE_WORD[gg]])
                lx += lw + lgap
            pick = ("– not rated yet" if grade is None else
                    "F · not searched" if grade == "ignore" else f"{grade} · {RM.MEANING[RM.GRADE_WORD[grade]]}")
            cv.text(gx + bw / 2, gy + 82, ("✓ " if grade else "") + pick, F_SMALL, anchor="n",
                    fill=cv.c("text") if grade else cv.c("text_muted"))
            if cols == 1:
                y += h + 6
        y = (top + 108 + 10) if cols == 3 else y + 4
        same = RM.same_for_every_roll(key)
        w = cv.tw("✓ " + SAME, F_SMALL) + 28
        if same:
            cv.card(cx - w / 2, y, cx + w / 2, y + 26, tag="same", fill=cv.c("surface_high"),
                    outline=cv.c("border_light"), r=12, lift=False)
            cv.text(cx, y + 13, "✓ " + SAME, F_SMALL, anchor="center", tags=("same",))
            cv.tips["same"] = "Every roll takes the mod's letter. Pick a letter in a group to make that group differ"
        else:
            self._rm_btn(cv, cx - w / 2, y, w, 26, SAME, "same", lambda: self.rm_same(key), font=F_SMALL, r=12,
                         tip="Every group takes the mod's letter again")
        return y + 26 + 18

    def rm_group_pick(self, key, i, grade):
        """A group's own letter (the same as the mod's: it follows the mod again). Once Top, Middle and Low each have
        a letter, the mod is rated - its letter is the Top rolls' - and the next mod comes up (feedback: three
        letters picked and nothing moved on)."""
        mod = RM.current([key])
        RM.set_group_grade(key, i, grade, mod_grade=mod)
        self._rm_roll_changed(key)
        groups = RM.roll_groups(self.rm_set, key) or []
        if len(groups) == 3 and all(g["grade"] or mod for g in groups) and mod is None:
            e = self.rm_current()
            if e is not None and key in (e.get("keys") or [key]):
                tops = [g["grade"] for g in groups]
                self._rm_apply([e["keys"]], tops[0])
                for j, gg in enumerate(tops):                  # each group keeps its own letter
                    RM.set_group_grade(key, j, gg, mod_grade=tops[0])
                self.rm_note_recent([e])
                if self.rm_i < len(self.rm_q) - 1:
                    self.root.after(450, lambda: (setattr(self, "rm_i", min(self.rm_i + 1, len(self.rm_q) - 1)),
                                                  self._rm_redraw()))

    def rm_same(self, key):
        RM.same_again(key)
        self._rm_roll_changed(key)

    def _rm_roll_changed(self, key):
        """By roll changed: the items you priced are marked Rating changed (Bulk Pricing prices them again on Re-price)."""
        affected = []
        for rid, rec in self.records.items():
            hit = False
            for m in (rec.get("item") or {}).get("mods") or []:
                if m.get("roll_key") == key:
                    RM.apply_roll(m)
                    hit = True
            if hit and rec.get("mark", "new") == "new" and rec.get("src") not in ("pc", "fav"):
                affected.append(rid)
        if affected:
            try:
                self.rating_changed(affected)          # (marked Rating changed - Re-price N items searches them)
            except Exception:
                buglog.caught()
        self.rm_cardcv.later(0)
        self.rm_tablecv.later()

    def _rm_rate_row(self, cv, cur, cx, y, narrow):
        """S A | B C D | F, grouped High | Normal | Ignore, with one meaning line under each group."""
        bw, bh, gap, ggap = (48, 42, 6, 12) if narrow else (64, 48, 8, 18)
        widths = [len(gs) * bw + (len(gs) - 1) * gap for _w, gs in GROUPS]
        x = cx - (sum(widths) + ggap * (len(GROUPS) - 1)) / 2
        for (word, grades), gw in zip(GROUPS, widths):
            cv.text(x + gw / 2, y, word.upper(), F_CAP, fill=cv.c("text_muted"), anchor="n")
            cv.create_line(x, y + 20, x + gw, y + 20, fill=cv.c("border_light"))
            bx = x
            for g in grades:
                tip = F_TIP if g == "ignore" else f"{g}: {RM.MEANING[word]} ({word})"
                self._rm_letter(cv, bx, y + 28, bw, bh, g, g == cur, F_LETTER if not narrow else F_HEAD, tip)
                bx += bw + gap
            cv.text(x + gw / 2, y + 28 + bh + 6, RM.MEANING[word], F_SMALL, fill=cv.c("text_muted"), anchor="n")
            x += gw + ggap
        return y + 28 + bh + 6 + 20 + 16

    def _rm_letter(self, cv, x, y, w, h, g, on, font, tip, fn=None, tag=None):
        """A letter button: the letter's own color strip along its top (filled with that color when it's yours, with a
        ✓) - the group's word stays under it, so the color is never alone."""
        col = letter_color(g)
        tag = tag or f"rate:{g}"
        if on:
            cv.card(x, y, x + w, y + h, tag=tag, fill=col, outline=cv.c("text_strong"), r=8, width=2, lift=False)
            ink = text_on(col)
        else:
            cv.card(x, y, x + w, y + h, tag=tag, fill=cv.c("surface_raised"), outline=cv.c("border_light"), r=8)
            cv.create_rectangle(x + 6, y + 3, x + w - 6, y + 6, fill=col, outline="", tags=(tag,))
            ink = cv.c("text")
        cv.text(x + w / 2, y + h / 2 + 1, _letter(g), font, fill=ink, anchor="center", tags=(tag,))
        if on:
            cv.text(x + w - 6, y + 4, "✓", F_SMALL, fill=ink, anchor="ne", tags=(tag,))
        cv.acts[tag] = fn or (lambda g=g: self.rm_rate(g))
        cv.tips[tag] = tip

    # ---------------------------------------------------------------- rating
    def _rm_apply(self, keys_list, grade):
        """Rate these mods (each a list of rule keys): your price checks follow at once."""
        done = self.rm_rated_keys = getattr(self, "rm_rated_keys", set())
        allk = []
        RM.note_rated(len(keys_list))                           # (saved with the ratings: "12 rated today")
        for keys in keys_list:
            RM.apply(keys, grade)
            done.add(tuple(keys))
            allk += list(keys)
            for k in keys:
                if RM.follow(k, grade):                    # (a group with the mod's new letter follows it again)
                    self._rm_roll_changed(k)
        self.rm_rated = len(done)
        ks = set(allk)
        affected = [rid for rid, rec in self.records.items() if rec.get("mark", "new") == "new" and rec.get("src") not in
                    ("pc", "fav") and any(RM.key_for(rec, m) in ks for m in rec["item"]["mods"])]
        if affected:
            self.rating_changed(affected)
        self._rm_recount(self.rm_set)
        self._rm_rules_later()

    def rm_note_recent(self, entries):
        """Just rated: the last five, newest first (one row a mod)."""
        rec = self.__dict__.setdefault("rm_recent", [])
        for e in entries:
            e = dict(e, set=e.get("set") or self.rm_set)
            rec[:] = [r for r in rec if r["keys"] != e["keys"]]
            rec.insert(0, e)
        del rec[5:]

    def rm_key_rate(self, grade):
        if self.rm_view == "Table":                           # (the Table: the picked row)
            e = self.rm_picked()
            if e is not None:
                self.rm_rate_one(e, grade)
            return grade if e is not None else None
        return self.rm_rate(grade)

    def rm_rate(self, grade):
        e = self.rm_current()
        if e is None:
            return None
        self._rm_apply([e["keys"]], grade)
        self.rm_note_recent([e])
        if self.rm_i < len(self.rm_q) - 1:
            self.rm_i += 1
        self._rm_redraw()
        return grade

    def rm_step(self, d):
        if self.rm_view == "Table":
            return
        self.rm_i = max(0, min(getattr(self, "rm_i", 0) + d, len(self.rm_q) - 1)) if self.rm_q else 0
        self.rm_cardcv.later(0)

    def rm_show(self):
        self._rm_redraw()

    def _rm_rules_later(self):
        """The Mod Book's lists follow your ratings - once you pause."""
        job = getattr(self, "_rm_rules_job", None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass

        def go():
            self._rm_rules_job = None
            try:
                self.refresh_rules()
            except Exception:
                buglog.caught()
        self._rm_rules_job = self.root.after(1500, go)

    # ---------------------------------------------------------------- the Table (the Map Library's browse layout)
    def rm_scope(self):
        """The sets the Table shows: a gear class's whole kind (Armour, Weapons, Jewelry - grouped by item class),
        else the picked set (grouped by tablet type, jewel type, waystone tiers or relic size)."""
        s = self.rm_set
        if not s:
            return []
        if s.startswith("gear:"):
            kind = RM.gear_kind(s[5:])
            return [x for x, _l in self.rm_sets() if x.startswith("gear:") and RM.gear_kind(x[5:]) == kind]
        return [s]

    def rm_scope_entries(self):
        """Every mod in the Table's sets that the search lets through."""
        q = self.rm_qv.get().strip().lower()
        out = []
        for s in self.rm_scope():
            ents = self.rm_entries(s)
            if q and q not in RM.set_label(s).lower():
                ents = [e for e in ents if self._rm_match(e, q)]
            out += ents
        return out

    def rm_rows(self):
        """The rows the Table shows (every group, open or folded): the search, then the Show chip."""
        f = self.rm_tfilter
        rows = self.rm_scope_entries()
        if f == "All":
            return rows
        want = f == "Rated"
        return [e for e in rows if (RM.current(e["keys"]) is not None) == want]

    def rm_tgroups(self, rows=None):
        """[(group, [rows])]: gear by item class (in the game's order), the rest by category - the shared ones
        ("All tablets") last."""
        rows = self.rm_rows() if rows is None else rows
        groups = {}
        for e in rows:
            groups.setdefault(e.get("cat") or "", []).append(e)
        if self.rm_set and self.rm_set.startswith("gear:"):
            order = [RM.set_label(s) for s in self.rm_scope()]
            names = sorted(groups, key=lambda g: order.index(g) if g in order else 99)
        else:
            names = sorted(groups, key=lambda g: (g.startswith("All "), g.lower()))
        return [(g, groups[g]) for g in names]

    def rm_group_open(self, name):
        """A group's rows show? Gear: the picked class's group opens (the rest fold, to stay light); else all open.
        A click on a group row flips it."""
        if name in self.rm_tgo:
            return self.rm_tgo[name]
        if self.rm_set and self.rm_set.startswith("gear:"):
            return name == self.rm_set_label or bool(self.rm_qv.get().strip())
        return True

    def rm_group_flip(self, name):
        self.rm_tgo[name] = not self.rm_group_open(name)
        self.rm_tablecv.later(0)

    def rm_shown_rows(self):
        return [e for g, rows in self.rm_tgroups() if self.rm_group_open(g) for e in rows]

    def rm_filter_pick(self, f):
        self.rm_tfilter = f
        self.rm_ticked.clear()
        self._rm_paint_chips()
        self._rm_paint_bulk()
        self.rm_tablecv.later(0)

    def _rm_paint_chips(self):
        rows = self.rm_scope_entries() if hasattr(self, "rm_tgo") else list(self.rm_q)
        rated = sum(1 for e in rows if RM.current(e["keys"]) is not None)
        n = {"Not rated": len(rows) - rated, "Rated": rated, "All": len(rows)}
        for f, b in getattr(self, "rm_chips", {}).items():
            on = f == self.rm_tfilter
            set_cfg(b, text=("✓ " if on else "") + f"{f} · {n[f]}", bg=C["sel"] if on else C["panel2"],
                    fg=C["text"], highlightbackground=C["accent"] if on else C["line"])

    def _rm_paint_bulk(self):
        n = len(self.rm_ticked)
        for b in getattr(self, "rm_bulk", {}).values():
            b.state(["!disabled"] if n else ["disabled"])
        if hasattr(self, "rm_bulk_n"):
            set_cfg(self.rm_bulk_n, text=f"{n} selected" if n else "none selected")

    def rm_bulk_rate(self, grade):
        """Rate selected: every ticked row gets this rating; the ticks clear."""
        rows = [e for e in self.rm_rows() if tuple(e["keys"]) in self.rm_ticked]
        if not rows:
            return None
        self._rm_apply([e["keys"] for e in rows], grade)
        for s in {e["set"] for e in rows}:
            self._rm_recount(s)
        self.rm_note_recent(rows[::-1])
        self.rm_ticked.clear()
        self._rm_redraw()
        return len(rows)

    def rm_tick(self, keys, on):
        k = tuple(keys)
        (self.rm_ticked.add if on else self.rm_ticked.discard)(k)
        ids = getattr(self, "_rm_trow", {}).get(k)
        cv = self.rm_tablecv
        if ids:
            row, box, mark, fill = ids
            try:
                cv.itemconfigure(row, fill=cv.c("selection") if on else fill)
                cv.itemconfigure(box, fill=cv.c("surface_high") if on else cv.c("surface_sunken"))
                cv.itemconfigure(mark, text="✓" if on else "")
            except tk.TclError:
                pass
        self._rm_paint_head_box()
        self._rm_paint_bulk()

    def _rm_paint_head_box(self):
        cv = self.rm_tablecv
        rows = self.rm_shown_rows()
        n = sum(1 for e in rows if tuple(e["keys"]) in self.rm_ticked)
        try:
            cv.itemconfigure("headmark", text="✓" if rows and n == len(rows) else "–" if n else "")
        except tk.TclError:
            pass

    def rm_tick_all(self):
        rows = self.rm_shown_rows()
        on = not (rows and all(tuple(e["keys"]) in self.rm_ticked for e in rows))
        for e in rows:
            self.rm_tick(e["keys"], on)

    def rm_row_menu(self, e, x, y):
        cur = RM.current(e["keys"])
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Rate this mod:", state="disabled")
        for g, label in SHOWN:
            word = RM.GRADE_WORD[g]
            menu.add_command(label=("● " if g == cur else "    ") + f"{label} - {word}, {RM.MEANING[word]}",
                             command=lambda g=g: self.rm_rate_one(e, g))
        if cur:
            menu.add_separator()
            menu.add_command(label="Clear my rating", command=lambda: self.rm_rate_one(e, None))
        self.rm_menu_open = menu
        try:
            menu.tk_popup(x, y)
        except tk.TclError:
            pass
        finally:
            menu.grab_release()
        return menu

    def rm_rate_one(self, e, grade):
        """Rate one mod from a row, the side panel or Just rated (None: clear yours)."""
        self._rm_apply([e["keys"]], grade)
        self._rm_recount(e.get("set"))
        if grade is not None:
            self.rm_note_recent([e])
        self._rm_redraw()

    def rm_tpick_row(self, e):
        """A row picked: the side panel shows it (the Drawer has none: its card opens)."""
        if self.rm_narrow:
            return self.rm_open_card(e)
        self.rm_tpick = tuple(e["keys"])
        self.rm_tablecv.later(0)
        self.rm_sidecv.later(0)

    def rm_picked(self):
        k = self.rm_tpick
        if not k:
            return None
        return next((e for e in self.rm_scope_entries() if tuple(e["keys"]) == k), None)

    def rm_open_card(self, e):
        """A row's mod on the card (One at a Time) - where By roll is set."""
        if e.get("set") and e["set"] != self.rm_set:
            self.rm_pick(e["set"])
        self.rm_cat = None
        self.rm_load(keep=True)
        if e in self.rm_q:
            self.rm_i = self.rm_q.index(e)
        self.rm_view_pick("One at a Time")

    def _rm_cols(self, w):
        """(key, title, width) - the Mod column takes what is left. The Drawer: the narrow set."""
        if w < 760:
            cols = (("box", "", 34), ("mod", "MOD", 0), ("rate", "YOUR RATING", 112), ("by", "BY ROLL", 88))
        elif w < 1100:
            cols = (("box", "", 34), ("mod", "MOD", 0), ("rate", "YOUR RATING", 116), ("by", "BY ROLL", 92),
                    ("players", "PLAYERS", 190))
        else:
            cols = (("box", "", 34), ("mod", "MOD", 0), ("rolls", "ROLLS ON", 120), ("rate", "YOUR RATING", 116),
                    ("by", "BY ROLL", 92), ("players", "PLAYERS", 200), ("seen", "SEEN IN LISTINGS", 140))
        fixed = sum(c[2] for c in cols)
        return [(k, t, wd or max(160, w - fixed)) for k, t, wd in cols]

    def _rm_draw_table(self, cv):
        W = max(cv.winfo_width(), 320)
        cols = self._rm_cols(W - 2)
        groups = self.rm_tgroups()
        self._rm_trow = {}
        x0, x1 = 1, W - 2
        head_h = 32
        cv.create_rectangle(x0 + 1, 2, x1 - 1, head_h, fill=cv.c("surface_high"), outline="")
        xs, x = {}, x0
        for k, t, wd in cols:
            xs[k] = (x, x + wd)
            if t:
                cv.text(x + 12, head_h / 2 + 1, t, F_CAP, fill=cv.c("text_muted"), anchor="w")
            x += wd
        bx = xs["box"][0] + 10
        cv.create_rectangle(bx, head_h / 2 - 8, bx + 16, head_h / 2 + 8, fill=cv.c("surface_sunken"),
                            outline=cv.c("border_light"), tags=("headbox",))
        cv.text(bx + 8, head_h / 2, "", F_SMALL, anchor="center", tags=("headbox", "headmark"))
        cv.acts["headbox"] = self.rm_tick_all
        cv.tips["headbox"] = "Tick every row shown (again: none)"
        y = head_h
        if not groups:
            q = self.rm_qv.get().strip()
            msg = (f"No mod matches “{q}”." if q else
                   "Every mod here is rated - see them under Rated." if self.rm_tfilter == "Not rated" else
                   "No mod here is rated yet.")
            t = cv.text((x0 + x1) / 2, y + 24, msg, F_BODY, fill=cv.c("text_muted"), anchor="n")
            y = cv.bottom(t, y + 40) + 12
            bw = 140
            if q:
                self._rm_btn(cv, (x0 + x1 - bw) / 2, y, bw, 32, "Clear search", "empty:clear",
                             lambda: self.rm_qv.set(""))
            else:
                other = "Rated" if self.rm_tfilter == "Not rated" else "All"
                self._rm_btn(cv, (x0 + x1 - bw) / 2, y, bw, 32, f"Show {other}", "empty:filter",
                             lambda: self.rm_filter_pick(other))
            y += 48
            self._rm_under(cv, x0, x1, y)
            return y + 8
        narrow = "seen" not in xs
        idx = RM.seen_index()
        every = {}                                             # (the group row counts every mod the search lets in)
        for e in self.rm_scope_entries():
            every.setdefault(e.get("cat") or "", []).append(e)
        i = 0
        for gi, (name, rows) in enumerate(groups):
            allg = every.get(name, rows)
            rated = sum(1 for e in allg if RM.current(e["keys"]) is not None)
            y = self._rm_group_row(cv, gi, name, len(allg), rated, x0, x1, y)
            if not self.rm_group_open(name):
                continue
            for e in rows:
                y = self._rm_table_row(cv, e, i, xs, y, x0, x1, narrow, idx)
                i += 1
        self._rm_under(cv, x0, x1, y + 4)
        self._rm_paint_head_box()
        return y + 12

    def _rm_group_row(self, cv, gi, name, n, rated, x0, x1, y):
        """"BREACH  29 mods · 12 rated by you" - a click folds it or opens it."""
        tag = f"grp:{gi}"
        h = 32
        cv.create_rectangle(x0 + 1, y, x1 - 1, y + h, fill=cv.c("surface_sunken"), outline="", tags=(tag,))
        opened = self.rm_group_open(name)
        t = cv.text(x0 + 12, y + h / 2, ("▾ " if opened else "▸ ") + name.upper(), F_CAP, fill=cv.c("link"),
                    anchor="w", tags=(tag,))
        bx = (cv.bbox(t) or (0, 0, x0 + 120, 0))[2] + 10
        cv.text(bx, y + h / 2, f"{n} mod{'s' if n != 1 else ''} · {rated} rated by you", F_SMALL,
                fill=cv.c("text_muted"), anchor="w", tags=(tag,))
        cv.create_line(x0 + 1, y + h, x1 - 1, y + h, fill=cv.c("border"))
        cv.acts[tag] = lambda name=name: self.rm_group_flip(name)
        cv.tips[tag] = f"{'Fold' if opened else 'Open'} {name}"
        return y + h

    def _rm_table_row(self, cv, e, i, xs, y, x0, x1, narrow, idx):
        keys = tuple(e["keys"])
        st = e.get("set") or self.rm_set
        cur = RM.current(e["keys"])
        s = RM.seen(st, e["keys"], idx)
        p = RM.players(e["keys"])
        ticked = keys in self.rm_ticked
        picked = keys == self.rm_tpick
        fill = cv.c("surface_high") if picked else cv.c("surface_raised") if i % 2 == 0 else cv.c("surface")
        tag = f"tick:{i}"
        row = cv.create_rectangle(x0 + 1, y, x1 - 1, y + 2, fill=cv.c("selection") if ticked else fill, outline="",
                                  tags=(tag,))
        mx0, mx1 = xs["mod"]
        t = cv.text(mx0 + 12, y + 10, ("▸ " if picked else "") + e["game"], F_BOLD if picked else F_BODY,
                    fill=cv.c("magic"), width=mx1 - mx0 - 24, tags=(f"mod:{i}",))
        bottom = cv.bottom(t, y + 26)
        cv.acts[f"mod:{i}"] = lambda e=e: self.rm_tpick_row(e)
        cv.tips[f"mod:{i}"] = "Open it on the card (One at a Time)" if self.rm_narrow else "Show it in the side panel"
        if narrow:
            bits = []
            if e.get("rolls"):
                bits.append("Rolls on " + ", ".join(e["rolls"][:2]) + (f" +{len(e['rolls']) - 2}" if
                                                                        len(e["rolls"]) > 2 else ""))
            if "players" not in xs:
                bits.append("Players " + RM.players_text(p))
            bits.append("Seen " + (f"{RM.div_text(s[0])} div · {s[1]}" if s else "–"))
            t2 = cv.text(mx0 + 12, bottom + 4, " · ".join(bits), F_SMALL, fill=cv.c("text_muted"),
                         width=mx1 - mx0 - 24, tags=(f"sub:{i}",))
            cv.tips[f"sub:{i}"] = RM.seen_tip(st, s) + "\n" + RM.players_tip(p)
            bottom = cv.bottom(t2, bottom + 18)
        h = max(bottom - y + 10, 40)
        cv.coords(row, x0 + 1, y, x1 - 1, y + h)
        if picked:
            cv.create_rectangle(x0 + 1, y, x0 + 4, y + h, fill=cv.c("accent"), outline="")
        cv.create_line(x0 + 1, y + h, x1 - 1, y + h, fill=cv.c("border"))
        cy = y + min(h / 2, 20)
        # the box: drag across the boxes to tick many (as on the price check card)
        bx0, _bx1 = xs["box"]
        box = cv.create_rectangle(bx0 + 10, cy - 8, bx0 + 26, cy + 8, outline=cv.c("border_light"),
                                  fill=cv.c("surface_high") if ticked else cv.c("surface_sunken"),
                                  tags=(tag, f"tbox:{i}"))
        mark = cv.text(bx0 + 18, cy, "✓" if ticked else "", F_SMALL, anchor="center", fill=cv.c("text_strong"),
                       tags=(tag, f"tbox:{i}"))
        self._rm_trow[keys] = (row, box, mark, fill)
        cv.tips[f"tbox:{i}"] = "Tick it - hold the button and drag across the boxes to tick more"
        self._card_tick_box(cv, None, tag, lambda k=keys: k in self.rm_ticked,
                            lambda on, k=keys: self.rm_tick(k, on))
        if "rolls" in xs:
            rx0, rx1 = xs["rolls"]
            r = e.get("rolls") or []
            txt = ", ".join(r[:2]) + (f" +{len(r) - 2}" if len(r) > 2 else "") if r else "–"
            cv.text(rx0 + 12, cy, cv.fit(txt, F_SMALL, rx1 - rx0 - 16), F_SMALL, anchor="w", tags=(f"rolls:{i}",))
            cv.tips[f"rolls:{i}"] = ("Rolls on: " + ", ".join(r)) if r else "Where it rolls isn't known"
        # Your rating: the letter's pill with its word (dashed: not yet) - click to rate this row
        px0, _px1 = xs["rate"]
        ptag = f"pill:{i}"
        self._rm_pill(cv, px0 + 10, cy, cur, ptag)
        cv.text(px0 + 42, cy, RM.GRADE_WORD.get(cur, "not yet") if cur else "not yet", F_SMALL, anchor="w",
                fill=cv.c("text") if cur else cv.c("text_muted"), tags=(ptag,))
        cv.acts[ptag] = lambda e=e, tag=ptag: self.rm_row_menu(e, *cv.at_root(tag))
        cv.tips[ptag] = (f"You rated it {RM.grade_text(cur)}: {RM.MEANING[RM.GRADE_WORD[cur]]}. Click to change it"
                         if cur else "Not rated yet. Click to rate it")
        # By roll: "same", or the three groups' letters
        fx0, _fx1 = xs["by"]
        key = e["keys"][0] if len(e["keys"]) == 1 else None
        groups = RM.roll_groups(st, key) if key else None
        ftxt = RM.by_roll_text(st, key, cur) if groups else "–"
        ftag = f"by:{i}"
        cv.text(fx0 + 12, cy, ftxt, F_SMALL, anchor="w", fill=cv.c("text") if groups else cv.c("text_muted"),
                tags=(ftag,))
        if groups:
            cv.tips[ftag] = ("; ".join(f"{g['name']} {RM.group_range(g, key)}: "
                                       f"{RM.grade_text(g['grade'] or cur)}" for g in groups) +
                             ". Click to change it on the card")
            cv.acts[ftag] = lambda e=e: self.rm_open_card(e)
        else:
            cv.tips[ftag] = "This mod has no tiers here: every roll takes the mod's letter"
        if "players" in xs:
            qx0, qx1 = xs["players"]
            cv.text(qx0 + 12, cy, cv.fit(RM.players_text(p), F_SMALL, qx1 - qx0 - 16), F_SMALL, anchor="w",
                    fill=cv.c("text") if p else cv.c("text_muted"), tags=(f"pl:{i}",))
            cv.tips[f"pl:{i}"] = RM.players_tip(p)
        if "seen" in xs:
            sx0, sx1 = xs["seen"]
            cv.text(sx0 + 12, cy, f"{RM.div_text(s[0])} div · {s[1]}" if s else "–", F_SMALL, anchor="w",
                    tags=(f"seen:{i}",))
            cv.tips[f"seen:{i}"] = RM.seen_tip(st, s)
        return y + h

    # ---- the side panel: the picked row
    def _rm_draw_side(self, cv):
        W = max(cv.winfo_width(), 200)
        x0, x1 = 1, W - 2
        pad = 16
        e = self.rm_picked()
        y = 16
        if e is None:
            t = cv.text(x0 + pad, y, "Pick a row to see its votes, its listings and your roll groups here.",
                        F_SMALL, fill=cv.c("text_muted"), width=x1 - x0 - 2 * pad)
            y = cv.bottom(t, y + 20) + 16
            self._rm_under(cv, x0, x1, y)
            return y + 8
        st = e.get("set") or self.rm_set
        cur = RM.current(e["keys"])
        pic = self.rm_pic(st, e, 48)
        tx = x0 + pad
        if pic is not None:
            cv.create_image(tx, y, image=pic, anchor="nw")
            tx += 58
        t = cv.text(tx, y, e["game"], F_HEAD, fill=cv.c("magic"), width=x1 - tx - pad)
        y = cv.bottom(t, y + 20) + 4
        lab, cat = RM.set_label(st), e.get("cat") or ""
        cv.text(tx, y, lab + (f" · {cat}" if cat and cat != lab else ""), F_SMALL, fill=cv.c("text_muted"))
        y = max(y + 22, 16 + (52 if pic is not None else 0))

        def label(text, y):
            cv.text(x0 + pad, y + 10, text, F_CAP, fill=cv.c("text_muted"))
            return y + 30

        def kv(k, v, y, tip=None, tag=None):
            cv.text(x0 + pad, y + 2, k, F_SMALL, fill=cv.c("text_muted"))
            cv.text(x1 - pad, y + 2, v, F_SMALL, anchor="ne", tags=(tag,) if tag else ())
            if tip and tag:
                cv.tips[tag] = tip
            cv.create_line(x0 + pad, y + 24, x1 - pad, y + 24, fill=cv.c("border"))
            return y + 30
        y = label("RATINGS", y)
        cv.text(x0 + pad, y + 2, "You", F_SMALL, fill=cv.c("text_muted"))
        px = x1 - pad - 26 - 8 - cv.tw(RM.GRADE_WORD.get(cur, "not yet") if cur else "not yet", F_SMALL)
        self._rm_pill(cv, px, y + 10, cur, "side:you")
        cv.text(x1 - pad, y + 10, RM.GRADE_WORD.get(cur, "not yet") if cur else "not yet", F_SMALL, anchor="e",
                tags=("side:you",))
        cv.tips["side:you"] = (f"You rated it {RM.grade_text(cur)}" if cur else "You haven't rated it yet")
        cv.create_line(x0 + pad, y + 24, x1 - pad, y + 24, fill=cv.c("border"))
        y += 30
        p = RM.players(e["keys"])
        y = kv("Players", RM.players_text(p) if not p else f"{p[0]} · {p[1]} votes", y, RM.players_tip(p), "side:pl")
        if p:                                                  # a bar per answer, with its count
            n = max(1, p[1])
            for word, c in zip(("High", "Normal", "Ignore"), p[2]):
                tag = f"side:v:{word}"
                cv.text(x0 + pad, y + 8, word, F_SMALL, anchor="w", tags=(tag,))
                bx0, bx1 = x0 + pad + 64, x1 - pad - 32
                cv.create_rectangle(bx0, y + 4, bx1, y + 12, fill=cv.c("surface_high"), outline="", tags=(tag,))
                if c:
                    cv.create_rectangle(bx0, y + 4, bx0 + max(3, int((bx1 - bx0) * c / n)), y + 12, outline="",
                                        fill=cv.c("text") if word == p[0] else cv.c("text_muted"), tags=(tag,))
                cv.text(x1 - pad, y + 8, str(c), F_SMALL, anchor="e", fill=cv.c("text_muted"), tags=(tag,))
                cv.tips[tag] = f"{c} of {p[1]} installs voted {word}. " + RM.players_tip(p)
                y += 22
            y += 6
        s = RM.seen(st, e["keys"])
        y = label("SEEN IN LISTINGS", y)
        y = kv("Middle price", f"{RM.div_text(s[0])} div" if s else "–", y, RM.seen_tip(st, s), "side:seen")
        y = kv("Listings", str(s[1]) if s else "–", y, RM.seen_tip(st, s), "side:seen2")
        key = e["keys"][0] if len(e["keys"]) == 1 else None
        groups = RM.roll_groups(st, key) if key else None
        if groups:
            y = label("YOUR ROLL GROUPS", y)
            for gi, g in enumerate(groups):
                tag = f"side:g:{gi}"
                grade = g["grade"] or cur
                self._rm_pill(cv, x0 + pad, y + 10, grade, tag)
                cv.text(x0 + pad + 34, y + 10, f"{g['name']} · {RM.group_range(g, key)}", F_SMALL, anchor="w",
                        tags=(tag,))
                cv.tips[tag] = ("Same as the mod's letter" if g["grade"] is None else "Its own letter") + \
                    " - change it on the card"
                cv.acts[tag] = lambda e=e: self.rm_open_card(e)
                y += 26
            y += 4
        y = label("RATE IT", y)
        bw, gap = 38, 6
        bx = x0 + pad
        for g, lab in SHOWN:
            if bx + bw > x1 - pad:
                bx, y = x0 + pad, y + 38
            tip = F_TIP if g == "ignore" else f"{g}: {RM.MEANING[RM.GRADE_WORD[g]]} ({RM.GRADE_WORD[g]})"
            self._rm_letter(cv, bx, y, bw, 32, g, g == cur, F_BOLD, tip, fn=lambda g=g, e=e: self.rm_rate_one(e, g),
                            tag=f"side:rate:{g}")
            bx += bw + gap
        y += 32 + 8
        t = cv.text(x0 + pad, y, "High is S A. Normal is B C D. F is left out of searches.", F_SMALL,
                    fill=cv.c("text_muted"), width=x1 - x0 - 2 * pad)
        y = cv.bottom(t, y + 16) + 12
        bw2 = 150
        self._rm_btn(cv, x0 + pad, y, bw2, 30, "Open on the card", "side:card", lambda e=e: self.rm_open_card(e),
                     font=F_SMALL, tip="This mod in One at a Time - where its roll groups are set")
        y += 30 + 16
        self._rm_under(cv, x0, x1, y)
        return y + 8

    # ---------------------------------------------------------------- the ask (once; Not now = once more, later)
    def rm_ask_tick(self):
        """Every 10 minutes: enough items priced (or a snooze over) and the app in front - ask, gently. (Drawer
        build: never while put away - it needs the app in front - and the 10-minute look goes on.)"""
        try:
            priced = sum(1 for r in self.records.values() if r.get("state") == "done")
            if RM.should_ask(priced) and getattr(self, "rm_ask_win", None) is None and self.root.focus_displayof():
                self.rm_ask()
        except Exception:
            buglog.caught()
        self.root.after(10 * 60 * 1000, self.rm_ask_tick)

    def rm_ask(self):
        """2.97.0 (feedback): what it is, how long, and that it ends when you say - no "a few" that never stops."""
        P2 = C["panel2"]
        w = self.rm_ask_win = tk.Toplevel(self.root, bg=P2)
        w.title("Help rate mods?")
        w.transient(self.root)
        w.resizable(False, False)
        box = tk.Frame(w, bg=P2, padx=16, pady=16)
        box.pack(fill="both", expand=True)
        tk.Label(box, text="Help rate mods?", bg=P2, fg=C["text"], font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(box, text="You pick the items you know best, then rate their mods one at a time. S is best and the price hangs "
                           "on it. F is ignore. Rate as many or as few as you like. Done ends it.",
                 bg=P2, fg=C["text"], wraplength=440, justify="left", anchor="w").pack(fill="x", pady=(8, 4))
        tk.Label(box, text="Your ratings tune your own price checks right away. With Community data sharing on, "
                           "they're your vote too.",
                 bg=P2, fg=C["muted"], wraplength=440, justify="left", anchor="w").pack(fill="x", pady=(0, 12))
        row = tk.Frame(box, bg=P2)
        row.pack()

        def pick(what):
            RM.answer(what, random)
            self.rm_ask_close()
            if what == "yes":
                self.rm_open()
        self.rm_ask_btns = {}
        for k, label, style in (("yes", "Count me in!", "Primary.TButton"), ("not_now", "Not now", "TButton"),
                                ("no", "Never ask again", "Quiet.TButton")):
            b = ttk.Button(row, text=label, style=style, command=lambda k=k: pick(k))
            b.pack(side="left", padx=4)
            self.rm_ask_btns[k] = b
        tk.Label(box, text="Not now asks once more in a few days. Either way, it's always in Mods › Mod Lab.",
                 bg=P2, fg=C["muted"], font=("Segoe UI", 9), wraplength=440, justify="center").pack(pady=(12, 0))
        w.protocol("WM_DELETE_WINDOW", lambda: pick("not_now"))
        self.rm_ask_pick = pick
        try:
            from .style import center_over                # 2.114.0: centered over the app (2.114.3: on its monitor)
            center_over(w, self.dlg_parent())
        except tk.TclError:
            pass
        on_top(w)
        return w

    def rm_ask_close(self):
        w, self.rm_ask_win = getattr(self, "rm_ask_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass


def _saved_view():
    from .config import SETTINGS
    return SETTINGS.get("rate_view")


_LEVELS = {}


def base_levels():
    """Each base's level to wear it, from Game Search's data: {base: level}. Read once."""
    if not _LEVELS:
        import re
        try:
            from . import gamesearch
            for r in gamesearch.load()["rows"] or []:
                m = re.search(r"Requires level (\d+)", r.get("t") or "")
                if m:
                    _LEVELS.setdefault(r["n"], int(m.group(1)))
        except Exception:
            buglog.caught()
    return _LEVELS
