"""The Game search window (2.0 beta 10, a Labs tool): the PoE2 Keyword Search page rebuilt as a window of the app.
Mixed into App. Data and matching are in gamesearch.py."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import gamesearch
from .config import SETTINGS, save_json
from .style import C, FONT_TITLE, ScrollArea, SegBar
from .chrome import SectionBar, Viewport
from .cardlist import CardList, ICON

PAGE = 60


class SearchPage:
    def build_search_window(self, body):
        P1, P2 = C["panel"], C["panel2"]
        self.gs_active, self.gs_shown, self.gs_job, self.gs_last = None, PAGE, None, []
        # UI overhaul: one big search box first (what to type is under it), the categories down the left with their
        # counts, the results on the right
        from .style import Tooltip
        top = tk.Frame(body, bg=P1, padx=16, pady=12)
        top.pack(fill="x")
        d = gamesearch.load()
        row = tk.Frame(top, bg=P1)
        row.pack(fill="x")
        box = tk.Frame(row, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 12)).pack(side="left", padx=(12, 0))
        self.gs_q = tk.StringVar()
        self.gs_entry = tk.Entry(box, textvariable=self.gs_q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                                 relief="flat", highlightthickness=0, bd=0, font=("Segoe UI", 12))
        self.gs_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(8, 8))
        ph = tk.Label(box, text="Search skills, supports, uniques, bases, currency, runes, mods and keywords",
                      bg=C["odd"], fg=C["muted"], font=("Segoe UI", 12))
        ph.bind("<Button-1>", lambda e: self.gs_entry.focus_set())

        def placeholder(*_a):
            try:
                if self.gs_q.get() or self.root.focus_get() is self.gs_entry:
                    ph.place_forget()
                else:
                    ph.place(in_=self.gs_entry, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            self.gs_entry.bind(ev, placeholder, add="+")
        self.gs_q.trace_add("write", placeholder)
        self.root.after(300, placeholder)
        clr = tk.Label(box, text="✕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10), cursor="hand2", padx=12)
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self.gs_clear())
        Tooltip(clr, "Clear the search (Esc)")
        help_row = tk.Frame(top, bg=P1)
        help_row.pack(fill="x", pady=(8, 0))
        tk.Label(help_row, text="Every word must match   ·   -word leaves it out   ·   \"quotes\" for a phrase",
                 bg=P1, fg=C["muted"], font=("Segoe UI", 9)).pack(side="left")
        info = tk.Label(help_row, text="ⓘ", bg=P1, fg=C["muted"], font=("Segoe UI", 9), cursor="question_arrow")
        info.pack(side="left", padx=(8, 0))
        Tooltip(info, f"The game's own data ({d['version']}, {len(d['rows']):,} entries), searched on your PC. Click a "
                      "result's wiki › to open its page on poe2wiki.net.")
        mid = tk.Frame(body, bg=P1)
        mid.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.gs_side = tk.Frame(mid, bg=P1, width=240)
        self.gs_side.pack(side="left", fill="y", padx=(0, 12))
        self.gs_side.pack_propagate(False)
        tk.Label(self.gs_side, text="CATEGORIES", bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w"
                 ).pack(fill="x", pady=(4, 4))
        # (3.0.6: 25 categories with the game database's - the column scrolls when the window is short)
        self.gs_scroll = ScrollArea(self.gs_side, bg=P1)
        self.gs_scroll.pack(fill="both", expand=True)
        self.gs_chips = self.gs_scroll.inner
        resw = tk.Frame(mid, bg=P1)
        resw.pack(side="left", fill="both", expand=True)
        self.gs_summary = tk.Label(resw, text="", bg=P1, fg=C["muted"], anchor="w")
        self.gs_summary.pack(fill="x", pady=(0, 4))
        self.gs_head = SectionBar(resw, "Results")
        self.gs_head.pack(fill="x")
        rvp = Viewport(resw, bg_key="panel2")
        rvp.pack(fill="both", expand=True)
        res = rvp.body
        sb = ttk.Scrollbar(res, orient="vertical")
        sb.pack(side="right", fill="y")
        t = tk.Text(res, bg=P2, fg=C["text"], relief="flat", wrap="word", padx=16, pady=8, cursor="arrow",
                    highlightthickness=0, yscrollcommand=sb.set, font=("Segoe UI", 10))
        t.pack(side="left", fill="both", expand=True)
        sb.config(command=t.yview)
        t.tag_configure("name", font=("Segoe UI", 12, "bold"), foreground=C["text"], spacing1=8)
        t.tag_configure("tag", font=("Consolas", 9), foreground=C["muted"])
        t.tag_configure("link", foreground=C["accent"], underline=True)
        t.tag_configure("txt", lmargin1=0, lmargin2=0, spacing1=2)
        t.tag_configure("kw", foreground=C["steel"], font=("Segoe UI", 9, "italic"))
        t.tag_configure("mark", background=C["accent"], foreground=C["bg"])
        t.tag_configure("sep", font=("Segoe UI", 9))
        t.tag_configure("more", foreground=C["accent"], font=("Segoe UI", 10, "bold"), underline=True)
        t.tag_configure("empty", foreground=C["muted"], font=("Segoe UI", 10), justify="center")
        t.tag_configure("emo", foreground="#d9b8ff", font=("Segoe UI", 10, "bold"))       # 2.17.0: Anoints
        t.tag_configure("price", foreground=C["good"], font=("Segoe UI", 10))
        t.tag_configure("total", foreground=C["good"], font=("Segoe UI", 10, "bold"))
        t.tag_bind("link", "<Enter>", lambda e: t.config(cursor="hand2"))
        t.tag_bind("link", "<Leave>", lambda e: t.config(cursor="arrow"))
        t.tag_bind("more", "<Button-1>", lambda e: self.gs_more())
        t.tag_bind("more", "<Enter>", lambda e: t.config(cursor="hand2"))
        t.tag_bind("more", "<Leave>", lambda e: t.config(cursor="arrow"))
        t.tag_configure("h2", font=(FONT_TITLE, 12, "bold"), foreground=C["accent"], spacing1=10, spacing3=4)
        t.tag_configure("try", font=("Consolas", 10, "bold"), foreground=C["text"], background=C["panel"])
        t.tag_configure("why", foreground=C["muted"])
        t.tag_configure("clear", foreground=C["accent"], font=("Segoe UI", 9), underline=True)
        for tg in ("try", "clear"):
            t.tag_bind(tg, "<Enter>", lambda e: t.config(cursor="hand2"))
            t.tag_bind(tg, "<Leave>", lambda e: t.config(cursor="arrow"))
        t.tag_bind("clear", "<Button-1>", lambda e: self.gs_recent_clear())
        t.config(state="disabled")
        self.gs_text, self.gs_sb = t, sb
        # 3.0.6: the results are item cards on one canvas (cardlist.py); the text above is kept for the pages that are
        # words (the empty page, nothing matched, Anoints with their prices)
        self.gs_cards = CardList(res, bg=P2, art=self._gs_art, on_toggle=self.gs_toggle, on_wiki=self.gs_wiki,
                                 on_more=self.gs_more)
        self._art_hooks = getattr(self, "_art_hooks", []) + [lambda done: self.gs_cards.refresh_art()]
        self.gs_save_job = None
        # (UI overhaul: Anoints is a category again, in the column on the left - not a page of its own)
        self.gs_q.trace_add("write", lambda *a: self._gs_later())
        self.gs_entry.bind("<Escape>", lambda e: self.gs_clear())
        self.gs_render()

    def _gs_art(self, row):
        """The card's picture when the app knows one (the trade site's art: a tablet, a waystone, an item you priced)."""
        if not SETTINGS.get("pc_art", True) or not hasattr(self, "pc_art"):
            return None
        if row.get("c") == "Jewel" and row.get("g") == "Jewels":
            return None                          # 3.0.6 (owner): a base jewel's name matched other art - no picture
        from .pricecheck_page import art_url
        try:
            return self.pc_art(art_url(row["n"]), px=ICON)
        except Exception:
            buglog.caught()
            return None

    def _gs_mode(self, cards):
        """Cards (one canvas) or text (the pages that are words)."""
        if cards:
            self.gs_text.pack_forget()
            self.gs_sb.pack_forget()
            if not self.gs_cards.winfo_ismapped():
                self.gs_cards.pack(fill="both", expand=True)
        else:
            self.gs_cards.pack_forget()
            if not self.gs_sb.winfo_ismapped():
                self.gs_sb.pack(side="right", fill="y")
                self.gs_text.pack(side="left", fill="both", expand=True)

    # ---------------- searching
    def _gs_later(self):
        if self.gs_job:
            self.root.after_cancel(self.gs_job)
        self.gs_job = self.root.after(140, self._gs_go)

    def _gs_go(self):
        self.gs_job = None
        self.gs_shown = PAGE
        self.gs_render()
        if getattr(self, "gs_save_job", None):
            self.root.after_cancel(self.gs_save_job)
        self.gs_save_job = self.root.after(2000, self.gs_recent_add)

    # ---- P7 (2.108.0): Try examples and your recent searches on the empty page
    TRY = (("spirit", "every word must match"), ("cold -support", "-word leaves things out"),
           ('"cast speed"', "quotes for a phrase"), ("omen", "one word finds every Omen - or pick a category on the left"))

    def gs_recent(self):
        r = SETTINGS.get("gs_recent")
        return [x for x in r if isinstance(x, str)][:8] if isinstance(r, list) else []

    def gs_recent_add(self, q=None):
        self.gs_save_job = None
        q = " ".join((q if q is not None else self.gs_q.get()).split())
        if len(q) < 2:
            return
        r = [x for x in self.gs_recent() if x.lower() != q.lower()]
        if r and (q.lower().startswith(r[0].lower()) or r[0].lower().startswith(q.lower())):
            r = r[1:]                                      # (the same search, typed on)
        SETTINGS["gs_recent"] = [q] + r[:7]
        save_json("settings.json", SETTINGS)

    def gs_recent_clear(self):
        SETTINGS["gs_recent"] = []
        save_json("settings.json", SETTINGS)
        self.gs_render()

    def gs_try(self, q):
        self.gs_q.set(q)
        self._gs_go()

    def _gs_empty_page(self):
        t = self.gs_text
        t.insert("end", "What are you looking for?\n", "h2")
        t.insert("end", "Type in the box above, or click one of these to see how searching works:\n", ("why",))
        for i, (q, why) in enumerate(self.TRY):
            tg = f"try{i}"
            t.insert("end", f" {q} ", ("try", tg))
            t.insert("end", f"   {why}\n", ("why",))
            t.tag_bind(tg, "<Button-1>", lambda e, q=q: self.gs_try(q))
        rec = self.gs_recent()
        if rec:
            t.insert("end", "Your recent searches   ", "h2")
            t.insert("end", "Clear", ("clear",))
            t.insert("end", "\n")
            for i, q in enumerate(rec):
                tg = f"rec{i}"
                t.insert("end", f" {q} ", ("try", tg))
                t.insert("end", "\n")
                t.tag_bind(tg, "<Button-1>", lambda e, q=q: self.gs_try(q))

    def gs_clear(self):
        self.gs_q.set("")
        self.gs_active = None
        self.gs_shown = PAGE
        self.gs_render()
        self.gs_entry.focus_set()

    def gs_lookup(self, text):
        """Open Game search with this already typed (from other windows: 'Look up')."""
        self.shell.open("search")
        self.gs_active = None
        self.gs_q.set(text.strip())
        self._gs_go()
        self.gs_entry.focus_set()

    def gs_pick(self, group):
        self.gs_active = group
        self.gs_shown = PAGE
        self.gs_render()

    def gs_more(self):
        self.gs_shown += PAGE
        self.gs_render(keep_scroll=True)

    def gs_on_anoints(self):
        return self.gs_active == gamesearch.ANOINTS

    def gs_render(self, keep_scroll=False):
        d = gamesearch.load()
        q = self.gs_q.get()
        terms, neg = gamesearch.parse(q)
        has = bool(terms or neg)
        allr = gamesearch.search(q) if has else d["rows"]
        # UI overhaul (feedback: categories in alphabetical order to ease navigation): A-Z, All on top
        order = sorted(set(d["order"]) | {gamesearch.ANOINTS}, key=str.lower)
        counts = {}
        for it in allr:
            counts[it["g"]] = counts.get(it["g"], 0) + 1
        everything = [it for it in allr if it["g"] != gamesearch.ANOINTS]     # (All: anoints have their own list)
        self._gs_chips(counts, len(everything), order)
        lst = [it for it in allr if it["g"] == self.gs_active] if self.gs_active else everything
        self.gs_last = lst
        t = self.gs_text
        y = t.yview()[0]
        t.config(state="normal")
        t.delete("1.0", "end")
        use_cards = bool(not d.get("error") and (has or self.gs_active) and lst and self.gs_active != gamesearch.ANOINTS)
        self._gs_mode(use_cards)
        if use_cards:
            self._gs_summary(terms, has, lst)
            self.gs_cards.set_rows(lst[:self.gs_shown], getattr(self, "gs_open", set()),
                                   more=max(0, len(lst) - self.gs_shown), terms=terms, keep_scroll=keep_scroll)
        elif d.get("error"):
            t.insert("end", "\n" + d["error"], "empty")
        elif not has and not self.gs_active:
            self.gs_summary.config(text="")
            self._gs_empty_page()
        else:
            self._gs_summary(terms, has, lst)
            if not lst:
                t.insert("end", "\nNothing matched. Try fewer words, or a different spelling.", "empty")
            for n, it in enumerate(lst[:self.gs_shown]):
                self._gs_insert(it, terms, n)
            if len(lst) > self.gs_shown:
                t.insert("end", f"\nShow {min(PAGE, len(lst) - self.gs_shown)} more", "more")
        t.config(state="disabled")
        if keep_scroll:
            t.yview_moveto(y)

    def _gs_summary(self, terms, has, lst):
        if has:
            self.gs_summary.config(text=f"{len(lst):,} result{'s' if len(lst) != 1 else ''}"
                                        + (f" in {self.gs_active}" if self.gs_active else " across all categories"))
        else:                                              # 2.0 beta 21: a category on its own lists all of it
            self.gs_summary.config(text=f"All {len(lst):,} in {self.gs_active}. Type to narrow it down."
                                   + ("  Type an emotion (e.g. Isolation) to see every anoint that uses it. "
                                      "Prices: poe.ninja." if self.gs_active == gamesearch.ANOINTS else ""))

    @staticmethod
    def _gs_cut(text, terms, size):
        low = text.lower()
        pos = min([p for p in (low.find(x) for x in terms) if p >= 0] or [-1])
        start = pos - 90 if pos > 120 else 0
        end = min(len(text), start + size)
        return ("… " if start > 0 else "") + text[start:end] + (" …" if end < len(text) else "")

    def _gs_put(self, text, terms, base_tags):
        """Insert text with every search word highlighted."""
        t = self.gs_text
        low = text.lower()
        marks = []
        for w in terms:
            i = low.find(w)
            while i >= 0:
                marks.append((i, i + len(w)))
                i = low.find(w, i + len(w))
        marks.sort()
        pos = 0
        for a, b in marks:
            if a < pos:
                continue
            if a > pos:
                t.insert("end", text[pos:a], base_tags)
            t.insert("end", text[a:b], base_tags + ("mark",))
            pos = b
        t.insert("end", text[pos:], base_tags)

    def _gs_insert(self, it, terms, n):
        t = self.gs_text
        if n:
            t.insert("end", "\n", "sep")
        self._gs_put(it["n"], terms, ("name",))
        t.insert("end", f"   {it['g']} · {it['c']}", ("tag",))
        if it.get("n") and not it.get("db"):              # 2.14.2: its wiki page (the inspector link is gone)
            tag = f"lnk{n}"
            t.insert("end", "   ")
            t.insert("end", "wiki ›", ("link", tag))
            t.tag_bind(tag, "<Button-1>", lambda e, nm=it["n"]: self.gs_wiki(nm))
        t.insert("end", "\n")
        opened = it["n"] + "|" + it["g"] in getattr(self, "gs_open", set())
        if it.get("db"):                                  # 3.0.6: the offline game database - one line, the rest on open
            return self._gs_db(it, terms, n, opened)
        if it["t"]:
            if opened:                                    # 2.23.0: the whole text, one line per part
                self._gs_put(it["t"].replace(" | ", "\n"), terms, ("txt",))
            else:
                self._gs_put(self._gs_cut(it["t"], terms, 300), terms, ("txt",))
            if len(it["t"]) > 300 or " | " in it["t"] or (it["k"] and len(it["k"]) > 160):
                tag = f"det{n}"
                t.insert("end", "   ")
                t.insert("end", "less ‹" if opened else "more ›", ("link", tag))
                t.tag_bind(tag, "<Button-1>", lambda e, key=it["n"] + "|" + it["g"]: self.gs_toggle(key))
            t.insert("end", "\n")
        if it.get("a"):                                   # 2.17.0: an anoint - its emotions and what they cost
            return self._gs_anoint(it, terms)
        if it["k"]:
            self._gs_put(it["k"] if opened else self._gs_cut(it["k"], terms, 160), terms, ("kw",))
            t.insert("end", "\n")

    def _gs_db(self, it, terms, n, opened):
        """A gamedb.json row: its first line; opened, every line, its tags, and where it comes from."""
        t = self.gs_text
        parts = it["t"].split(" | ")
        self._gs_put(parts[0] if opened else self._gs_cut(parts[0], terms, 300), terms, ("txt",))
        if len(parts) > 1 or it["k"]:
            tag = f"det{n}"
            t.insert("end", "   ")
            t.insert("end", "less ‹" if opened else "more ›", ("link", tag))
            t.tag_bind(tag, "<Button-1>", lambda e, key=it["n"] + "|" + it["g"]: self.gs_toggle(key))
        t.insert("end", "\n")
        if opened:
            if len(parts) > 1:
                self._gs_put("\n".join(parts[1:]), terms, ("txt",))
                t.insert("end", "\n")
            if it["k"]:
                self._gs_put(it["k"], terms, ("kw",))
                t.insert("end", "\n")
            v = it.get("v")
            t.insert("end", f"Source: {it['src']} · " + (f"Game {v}" if v and v != "none" else "no game version in the file")
                     + "\n", ("tag",))

    def _gs_anoint(self, it, terms):
        """The three Liquid Emotions, each with its poe.ninja price, and the total."""
        from .pricefmt import fmt_div
        from .wealth import WPRICES
        t = self.gs_text
        self.gs_prices_wanted()
        total, missing = 0.0, False
        for i, (name, n) in enumerate(gamesearch.emotion_counts(it["a"])):
            t.insert("end", "   +   " if i else "", ("tag",))
            if n > 1:
                t.insert("end", f"{n}× ", ("emo",))
            self._gs_put(name, terms, ("emo",))
            v = WPRICES.named(name) if self.gs_prices_ok() else None
            if v is None:
                missing = True
                t.insert("end", "  (no price)" if self.gs_prices_ok() else "", ("tag",))
            else:
                total += v * n
                t.insert("end", f"  {fmt_div(v)}" + (" each" if n > 1 else ""), ("price",))
        if self.gs_prices_ok() and total:
            t.insert("end", f"   =  {fmt_div(total)}" + (" + the unpriced one" if missing else ""), ("total",))
        elif getattr(self, "gs_price_state", "") == "loading":
            t.insert("end", "   prices loading from poe.ninja…", ("tag",))
        elif getattr(self, "gs_price_state", "") == "none":
            t.insert("end", "   (no prices: pick your league in Settings)" if not self.gs_league() else
                     "   (poe.ninja prices unavailable right now)", ("tag",))
        t.insert("end", "\n")

    @staticmethod
    def gs_league():
        from .config import SETTINGS
        return SETTINGS.get("league") or ""

    def gs_prices_ok(self):
        from .wealth import WPRICES
        return (getattr(self, "gs_price_state", "") == "ok" and WPRICES.ok
                and bool((WPRICES.parts.get("Delirium") or {}).get("lines")))

    def gs_prices_wanted(self):
        """Liquid Emotion prices from poe.ninja: fetched in the background the first time an anoint is shown, and
        again when they're over an hour old (WealthPrices.ensure_types)."""
        import threading
        import time
        lg = self.gs_league()
        st = getattr(self, "gs_price_state", "")
        if st == "loading" or (st in ("ok", "none") and lg == getattr(self, "gs_price_league", None)
                               and time.time() - getattr(self, "gs_price_ts", 0) < 3600):
            return
        if not lg:
            self.gs_price_state, self.gs_price_league, self.gs_price_ts = "none", lg, time.time()
            return
        self.gs_price_state, self.gs_price_league = "loading", lg

        def work():
            from .wealth import WPRICES
            try:
                WPRICES.ensure_types(lg, ("Delirium",))
            except Exception:
                buglog.caught()
            self.ui_q.put(("search_prices",))
        threading.Thread(target=work, daemon=True).start()

    def ev_search_prices(self):
        import time
        from .wealth import WPRICES
        self.gs_price_ts = time.time()
        self.gs_price_state = "ok" if WPRICES.ok and (WPRICES.parts.get("Delirium") or {}).get("lines") else "none"
        if getattr(self, "gs_text", None) is not None and self.gs_text.winfo_exists():
            self.gs_render(keep_scroll=True)

    def gs_toggle(self, key):
        """2.23.0: open / close one result's full details (the whole text and every keyword)."""
        s = self.__dict__.setdefault("gs_open", set())
        s.symmetric_difference_update({key})
        self.gs_render(keep_scroll=True)

    def gs_wiki(self, name):
        import urllib.parse
        import webbrowser
        webbrowser.open("https://www.poe2wiki.net/wiki/" + urllib.parse.quote(name.replace(" ", "_")))

    # ---------------- category buttons (wrap onto more rows when the window is narrow)
    def _gs_chips(self, counts, total, order):
        """UI overhaul: the categories down the left, each with how many results it has; the one picked has a bar,
        bold text and a filled row (never color alone)."""
        f = self.gs_chips
        cats = [(None, "All")] + [(g, g) for g in order]
        # UI rule 22: picking a category or typing a search re-counts and re-marks the rows that are there - they are
        # built again only when the list of categories changes
        have = getattr(self, "_gs_chip_rows", None)
        if have is None or [h[0] for h in have] != [g for g, _l in cats] or \
                not all(h[1].winfo_exists() for h in have) or have[0][1].master is not f:
            for w in f.winfo_children():
                w.destroy()
            have = self._gs_chip_rows = []
            for g, label in cats:
                row = tk.Frame(f, bg=C["panel"], cursor="hand2")
                row.pack(fill="x", pady=1)
                bar = tk.Frame(row, width=3)
                bar.pack(side="left", fill="y")
                name = tk.Label(row, text=label, anchor="w", padx=8, pady=4)
                cnt = tk.Label(row, padx=8, font=("Segoe UI", 9))
                cnt.pack(side="right")                      # (D3: the count claims its room first, then the name)
                name.pack(side="left", fill="x", expand=True)
                for w in (row, name, cnt):
                    w.bind("<Button-1>", lambda e, gg=g: self.gs_pick(gg))
                have.append((g, row, bar, name, cnt))
        from .inplace import set_cfg
        for g, row, bar, name, cnt in have:
            n = total if g is None else counts.get(g, 0)
            on = self.gs_active == g
            bg = C["panel2"] if on else C["panel"]
            set_cfg(row, bg=bg)
            set_cfg(bar, bg=C["accent"] if on else bg)
            set_cfg(name, bg=bg, fg=C["text"] if (n or on) else C["muted"], font=("Segoe UI", 10, "bold" if on else "normal"))
            set_cfg(cnt, text=f"{n:,}", bg=bg, fg=C["muted"])

    def _gs_flow(self):
        """(2.0 beta 21's wrapping chips: the categories are a column now)"""
        return
