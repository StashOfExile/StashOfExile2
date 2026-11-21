"""Exchange Rates › Rates (UI overhaul): every currency as a row with its picture - what one is worth in divines,
what one divine buys, and how much of it traded (a short bar, with "Thin market" when there's too little to trust).
Search first; sort by Most traded, Most valuable or A–Z.

The pictures are poe.ninja's (the paths it sends with its prices), loaded once from the game's image server into
the data folder's art cache and drawn small. GGG ToS: looks only - nothing here touches the game."""
import hashlib
import os
import threading
import time
import tkinter as tk

from . import buglog
from . import themes as TH
from .config import APP_UA, P, SETTINGS
from .style import C

ROW_H, ICON = 52, 32
SORTS = ("Most traded", "Most valuable", "A–Z")
THIN = 5                     # divines traded: under this, the price is shaky
CDN = "https://web.poecdn.com"


def image_url(path):
    if not path:
        return None
    return path if path.startswith("https://") else (CDN + path if path.startswith("/") else None)


KIND_LABEL = {"Currency": "Currency", "Fragments": "Fragments", "Abyss": "Abyss", "UncutGems": "Uncut Gems",
              "LineageSupportGems": "Lineage Gems", "Essences": "Essences", "SoulCores": "Soul Cores",
              "Idols": "Idols", "Runes": "Runes", "Ritual": "Omens", "Expedition": "Expedition",
              "Delirium": "Delirium", "Breach": "Breach", "Verisium": "Verisium"}


class LocalIcons:
    """Pictures already in the art cache, by item name (3.1, GGG ToS 7a: no game art ships with the app): poe.ninja's
    pictures - the image links it sends with its prices, from the game's own image server - downloaded once by
    Icons (Exchange Rates, Top Up, Map Profit ...) and kept only on this PC. Nothing is downloaded here: no picture
    yet = None, and the item's name stands in. {name: PhotoImage}, made on first use."""

    REFRESH = 60                                 # seconds: the names poe.ninja sent pictures for are looked at again

    def __init__(self, root, size=ICON):
        self.root, self.size, self.cache, self._map, self._at = root, size, {}, None, 0.0

    def _names(self):
        """{lower-case name: (name, picture URL)} - every item poe.ninja sent a picture link for."""
        if self._map is None or time.time() - self._at > self.REFRESH:
            out = {}
            try:
                from .rates import RATES
                from .wealth import WPRICES
                for part in (WPRICES.parts or {}).values():
                    if not isinstance(part, dict):
                        continue
                    imgs, names = part.get("images") or {}, part.get("names") or {}
                    for cid, path in imgs.items():
                        n, u = names.get(cid), image_url(path)
                        if n and u:
                            out.setdefault(str(n).lower(), (str(n), u))
                rn = getattr(RATES, "names", {}) or {}
                for cid, path in (getattr(RATES, "images", {}) or {}).items():
                    n, u = rn.get(cid), image_url(path)
                    if n and u:
                        out.setdefault(str(n).lower(), (str(n), u))
            except Exception:
                buglog.caught()
            self._map, self._at = out, time.time()
        return self._map

    def names(self):
        """Every item poe.ninja sends a picture for, in the game's spelling."""
        return sorted(n for n, _u in self._names().values())

    def has(self, name):
        return str(name or "").lower() in self._names()

    def get(self, name):
        got = self._names().get(str(name or "").lower())
        if not got:
            return None
        url = got[1]
        if url in self.cache:
            return self.cache[url]
        from . import gameart as GA
        p = GA.cache_file(url)
        if p is None:
            return None                          # (not downloaded yet: looked for again next time)
        try:
            from PIL import Image, ImageTk
            im = Image.open(p).convert("RGBA")
            im.thumbnail((self.size, self.size))
            if im.size != (self.size, self.size):
                sq = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
                sq.paste(im, ((self.size - im.size[0]) // 2, (self.size - im.size[1]) // 2), im)
                im = sq
            ph = ImageTk.PhotoImage(im, master=self.root)
        except Exception:
            ph = None
        self.cache[url] = ph
        return ph


def exchange_rows():
    """Every item poe.ninja prices on the Currency Exchange, in divines: [(kind, id, name, divines, traded divines,
    picture path)] - Currency, Fragments, Essences, Runes, Omens, Soul Cores ... (Wealth's price list)."""
    from .wealth import WPRICES, NINJA_EXCHANGE_TYPES
    parts = WPRICES.parts or {}
    cur = parts.get("Currency") or {}
    primary = cur.get("primary") or "divine"
    per_div = 1.0
    if primary != "divine":
        per_div = next((v for cid, _n, v, _vol in cur.get("lines", []) if cid == "divine"), None) or 0
    if not per_div:
        return []
    out = []
    for typ in NINJA_EXCHANGE_TYPES:
        part = parts.get(typ) or {}
        imgs = part.get("images") or {}
        for cid, name, v, vol in part.get("lines", []):
            if v:
                out.append((typ, cid, name, v / per_div, (vol or 0) / per_div, imgs.get(cid)))
    return out


class Icons:
    """Small currency pictures: from the art cache, else fetched in the background by ONE worker, one at a time;
    on_ready() runs (on the window's thread, at most once a second) once new ones arrive. 3.0.3: it was a thread and
    a timer per picture - hundreds at once froze the app; after a few failures in a row (no internet, a blocked
    certificate) it stops asking until the app restarts, and the items' names stand in (3.1: no pictures ship)."""

    GIVE_UP = 5                                  # failures in a row before the downloads stop

    def __init__(self, root, on_ready, size=ICON):
        import queue
        self.root, self.on_ready, self.size = root, on_ready, size
        self.cache, self.wait, self.done, self.failed = {}, set(), set(), {}
        self.q, self.worker, self.polling, self.misses = queue.Queue(), None, False, 0
        self.gap = 0.0                           # 3.0.6: seconds between two downloads (Map Profit asks for many)

    @staticmethod
    def path(url):
        d = P("art")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "cur_" + hashlib.sha1(url.encode()).hexdigest()[:20] + ".png")

    def get(self, url):
        if not url:
            return None
        if url in self.cache:
            return self.cache[url]
        p = self.path(url)
        if os.path.exists(p):
            try:
                from PIL import Image, ImageTk
                im = Image.open(p).convert("RGBA")
                im.thumbnail((self.size, self.size))
                if im.size != (self.size, self.size):          # (centered on a clear square: rows line up)
                    sq = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
                    sq.paste(im, ((self.size - im.size[0]) // 2, (self.size - im.size[1]) // 2), im)
                    im = sq
                ph = ImageTk.PhotoImage(im, master=self.root)
                self.cache[url] = ph
                return ph
            except Exception:
                self.cache[url] = None
                return None
        if self.misses >= self.GIVE_UP:
            return None
        if url not in self.wait and time.time() - self.failed.get(url, 0) > 600:
            self.wait.add(url)
            self.q.put((url, p))
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._work, daemon=True)
                self.worker.start()
            if not self.polling:
                self.polling = True
                self.root.after(1000, self._poll)
        return None

    def _work(self):
        import queue
        while True:
            try:
                url, path = self.q.get(timeout=5)
            except queue.Empty:
                return
            ok = False
            if self.misses < self.GIVE_UP:
                ok = self._fetch(url, path)
                self.misses = 0 if ok else self.misses + 1
            self.done = self.done | {url}           # (a new set: read on the window's thread)
            if self.gap and ok:
                time.sleep(self.gap)

    def _fetch(self, url, path):
        try:
            import requests
            r = requests.get(url, headers={"User-Agent": APP_UA}, timeout=10)
            if r.status_code == 200 and r.content:
                tmp = path + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(r.content)
                os.replace(tmp, path)
                return True
        except Exception:
            if self.misses == 0:                     # (logged once, not once per picture)
                buglog.caught()
        return False

    def _poll(self):
        done, self.done = self.done, set()
        self.wait -= done
        for u in done:
            if not os.path.exists(self.path(u)):
                self.failed[u] = time.time()
        if self.misses >= self.GIVE_UP:
            self.wait.clear()
        self.polling = bool(self.wait)
        if self.polling:
            self.root.after(1000, self._poll)
        if any(os.path.exists(self.path(u)) for u in done):
            try:
                self.on_ready()
            except Exception:
                buglog.caught()


def picture_paths():
    """{currency id or lower-case name: poe.ninja's picture path} - everything poe.ninja sent pictures for (the
    exchange categories Wealth reads, and the Currency list Exchange Rates reads)."""
    from .rates import RATES
    from .wealth import WPRICES
    out = {}
    for part in (WPRICES.parts or {}).values():
        if not isinstance(part, dict):
            continue
        imgs, names = part.get("images") or {}, part.get("names") or {}
        for cid, path in imgs.items():
            out[cid] = path
            if names.get(cid):
                out[names[cid].lower()] = path
    names = getattr(RATES, "names", {})
    for cid, path in getattr(RATES, "images", {}).items():
        out[cid] = path
        if names.get(cid):
            out[names[cid].lower()] = path
    return out


def url_for(key, paths=None):
    """The picture of a currency or stackable, by its poe.ninja id or its name (None if poe.ninja has none)."""
    paths = picture_paths() if paths is None else paths
    return image_url(paths.get(key) or paths.get(str(key).lower()))


class RatesList(tk.Frame):
    """The Rates tab's body. .paint() after new rates."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["panel"])
        self.app, self.sort, self.hover, self.kind = app, SORTS[0], None, "All"
        self.icons = Icons(app.root, lambda: self.paint())
        app._drawer_look_hooks = getattr(app, "_drawer_look_hooks", []) + [lambda on: self.paint()]
        self._loading = False
        bar = tk.Frame(self, bg=C["panel"], padx=16, pady=12)
        bar.pack(fill="x")
        box = tk.Frame(bar, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        box.pack(side="left")
        tk.Label(box, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        self.q = tk.StringVar()
        self.entry = tk.Entry(box, textvariable=self.q, bg=C["odd"], fg=C["text"], insertbackground=C["text"],
                              relief="flat", font=("Segoe UI", 10), width=26, highlightthickness=0, bd=0)
        self.entry.pack(side="left", padx=8, ipady=8)
        self.ph = tk.Label(box, text="Search the exchange", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 10))
        self.ph.bind("<Button-1>", lambda e: self.entry.focus_set())
        for ev in ("<FocusIn>", "<FocusOut>"):
            self.entry.bind(ev, lambda e: self._ph(), add="+")
        self.q.trace_add("write", lambda *_: (self._ph(), self.paint()))
        self.entry.bind("<Escape>", lambda e: self.q.set(""))
        self.after(200, self._ph)
        self.sorts = tk.Canvas(bar, height=36, width=330, bg=C["panel"], highlightthickness=0, bd=0)
        self.sorts.pack(side="left", padx=(16, 0))
        self.sorts.bind("<Button-1>", self._sort_click)
        TH.self_painted(self.sorts)
        self.right = tk.Frame(bar, bg=C["panel"])
        self.right.pack(side="right")
        from .style import flowify
        flowify(bar)                                       # D3: the sort chips and Refresh wrap at Drawer width
        self.kinds = tk.Canvas(self, height=34, bg=C["panel"], highlightthickness=0, bd=0)  # All, Currency, Runes ...
        self.kinds.pack(fill="x", padx=16)
        self.kinds.bind("<Button-1>", self._kind_click)
        TH.self_painted(self.kinds)
        self.status = tk.Label(self, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9), anchor="w", padx=16)
        self.status.pack(fill="x")
        self.status.bind("<Configure>", self._status_wrap, add="+")     # D3: a long line wraps, it isn't cut off
        head = tk.Canvas(self, height=28, bg=C["panel"], highlightthickness=0, bd=0)
        head.pack(fill="x", padx=(16, 24), pady=(8, 0))
        self.head = head
        TH.self_painted(head)
        self.cv = tk.Canvas(self, bg=C["panel"], highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True, padx=(16, 24), pady=(0, 12))
        TH.self_painted(self.cv)
        from .style import overflow_scrollbar          # the thin round bar, only while the list is longer than the page
        self.sb = overflow_scrollbar(self.cv, lambda *a: (self.cv.yview(*a), self.paint()))
        TH.subscribe(lambda t: self.paint(), owner=self)
        self.cv.bind("<Configure>", lambda e: self.paint())
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._set_hover(None))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.cv.bind(ev, self._wheel)
        self._rows = []

    def _status_wrap(self, e):
        w = max(200, e.width - 32)
        if abs(int(self.status.cget("wraplength") or 0) - w) >= 8:
            self.status.config(wraplength=w, justify="left")

    def _ph(self):
        try:
            if self.q.get() or self.focus_get() is self.entry:
                self.ph.place_forget()
            else:
                self.ph.place(in_=self.entry, x=0, rely=0.5, anchor="w")
        except (tk.TclError, KeyError):
            pass

    def _sort_click(self, e):
        for x0, x1, k in getattr(self, "_sort_hit", []):
            if x0 <= e.x <= x1:
                self.sort = k
                self.paint()

    def _kind_click(self, e):
        for x0, x1, y0, y1, k in getattr(self, "_kind_hit", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.kind = k
                self.cv.yview_moveto(0)
                self.paint()

    def _ensure_prices(self):
        """Every exchange category comes from Wealth's price list (poe.ninja, hourly): fetch it once if it's missing
        or old, in the background."""
        from .wealth import WPRICES
        lg = SETTINGS.get("league")
        if self._loading or not lg or (WPRICES.parts and WPRICES.league == lg and (WPRICES.age() or 9e9) < 3600):
            return
        self._loading = True

        def work():
            try:
                WPRICES.ensure(lg)
            except Exception:
                buglog.caught()
            finally:
                self._loading = False
        threading.Thread(target=work, daemon=True).start()
        self._poll_loading()

    def _poll_loading(self):
        if self._loading:
            self.after(800, self._poll_loading)
        else:
            self.paint()

    def _wheel(self, e):
        step = (-1 if e.num == 4 else 1) if getattr(e, "num", None) in (4, 5) else (-1 if e.delta > 0 else 1)
        if len(self._rows) * ROW_H > self.cv.winfo_height():
            self.cv.yview_scroll(step * 2, "units")
            self.paint()                                # (the rows now in view)

    def _motion(self, e):
        i = int(self.cv.canvasy(e.y) // ROW_H)
        self._set_hover(i if 0 <= i < len(self._rows) else None)

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.paint()

    def rows(self):
        """[(kind, id, name, divines, traded, url)] matching the search and the picked kind, sorted."""
        from .rates import RATES
        from .ovrates import cur_name
        allr = exchange_rows()
        if not allr:                                  # (Wealth's list not fetched yet: the Currency rates)
            names = getattr(RATES, "names", {})
            allr = [("Currency", cid, cur_name(cid, names), v, RATES.vol.get(cid, 0),
                     getattr(RATES, "images", {}).get(cid)) for cid, v in RATES.table.items() if v]
        self._kinds = ["All"] + [k for k in KIND_LABEL if any(r[0] == k for r in allr)]
        q = self.q.get().strip().lower()
        out = []
        for typ, cid, name, v, vol, path in allr:
            if self.kind != "All" and typ != self.kind:
                continue
            if q and not all(p in name.lower() for p in q.split()):
                continue
            out.append((typ, cid, name, v, vol, image_url(path)))
        key = {"Most traded": lambda r: -r[4], "Most valuable": lambda r: -r[3],
               "A–Z": lambda r: r[2].lower()}[self.sort]
        return sorted(out, key=key)

    def paint(self):
        t = TH.ST.theme
        if t is None:
            return
        try:
            self._paint(t)
        except tk.TclError:
            pass

    def _paint(self, t):
        from .ovrates import fmt_worth
        from .rates import RATES
        with TH.raw():
            bg, raised, line = t.c("surface"), t.c("surface_raised"), t.c("border")
            txt, mut, strong, brass, acc = (t.c("text"), t.c("text_muted"), t.c("text_strong"), t.c("accent_2"),
                                            t.c("accent"))
            warn = t.c("warn")
            look = getattr(self.app, "drawer_look_on", None)
            dl = bool(look and look())                    # drawer build: the Drawer's look (mockups.html: a table,
            mark = acc                                    # rows split by a line); Round 18: the picked chip in the
            for c in (self.sorts, self.head, self.cv):     # theme's accent, the names in its strong text
                c.configure(bg=bg)
            from . import soft
            chip = soft.chip_colors(bg, mut, strong)          # (a soft fill and an outline you can see, on any theme)
            # sort chips
            sc = self.sorts
            sc.delete("all")
            self._sort_hit, x = [], 0
            for k in SORTS:
                on = k == self.sort
                tid = sc.create_text(0, 0, text=k, font=("Segoe UI", 9, "bold" if on else "normal"))
                w = sc.bbox(tid)[2] - sc.bbox(tid)[0] + 24
                sc.delete(tid)
                TH.round_rect(sc, x, 6, x + w, 30, 10, fill=chip["on" if on else "off"][0],
                              outline=mark if on else chip["off"][1], width=2 if on else 1)
                sc.create_text(x + w / 2, 18, text=k, font=("Segoe UI", 9, "bold" if on else "normal"),
                               fill=strong if on else mut)
                self._sort_hit.append((x, x + w, k))
                x += w + 6
            if int(sc.cget("width")) != max(x - 6, 1):
                sc.configure(width=max(x - 6, 1))         # D3: as wide as its chips ask (it was fixed at 330)
            self._ensure_prices()
            rows = self._rows = self.rows()
            kc = self.kinds
            kc.configure(bg=bg)
            kc.delete("all")
            self._kind_hit, x, y = [], 0, 4
            W0 = max(kc.winfo_width(), 300)
            for k in self._kinds:
                on = k == self.kind
                label = KIND_LABEL.get(k, k)
                tid = kc.create_text(0, 0, text=label, font=("Segoe UI", 9, "bold" if on else "normal"))
                w = kc.bbox(tid)[2] - kc.bbox(tid)[0] + 22
                kc.delete(tid)
                if x + w > W0:
                    x, y = 0, y + 30
                TH.round_rect(kc, x, y, x + w, y + 24, 10, fill=chip["on" if on else "off"][0],
                              outline=mark if on else chip["off"][1], width=2 if on else 1)
                kc.create_text(x + w / 2, y + 12, text=label, font=("Segoe UI", 9, "bold" if on else "normal"),
                               fill=strong if on else mut)
                self._kind_hit.append((x, x + w, y, y + 24, k))
                x += w + 6
            kc.configure(height=y + 30)
            W = max(self.cv.winfo_width(), 400)
            cols = (56, W * 0.34, W * 0.48, W * 0.76, W * 0.64)   # name, worth, 1 div buys, traded; 7 days (3.0.4)
            from .wealth import WPRICES
            trends = getattr(WPRICES, "trend_by_slug", {}) if WPRICES.for_league() else {}
            hd = self.head
            hd.delete("all")
            for x0, label, anchor in ((cols[0], "Item", "w"), (cols[2] - 16, "1 is worth", "e"),
                                      (cols[4] - 16, "7 days", "e"),
                                      (cols[3] - 16, "1 divine buys", "e"), (W - 8, "Traded (div)", "e")):
                hd.create_text(x0, 14, text=label.upper(), anchor=anchor, font=("Segoe UI", 8, "bold"), fill=mut)
            cv = self.cv
            cv.delete("all")
            if not rows:
                cv.create_text(8, 16, anchor="nw", font=("Segoe UI", 10), fill=mut, width=W - 16,
                               text="Nothing matches. Clear the search or pick All." if RATES.table or exchange_rows()
                               else ("Loading prices from poe.ninja…" if self._loading else
                                     "No rates yet. Pick a league in Settings, then press Refresh now."))
            top_vol = max((r[4] for r in rows), default=1) or 1
            cv.configure(scrollregion=(0, 0, W, max(len(rows) * ROW_H, cv.winfo_height())))
            vy = cv.canvasy(0)                         # 3.0.3: only the rows in view (and a few either side) are
            first = max(0, int(vy // ROW_H) - 3)       # drawn - all of them, pictures included, froze the app
            last = min(len(rows), int((vy + max(cv.winfo_height(), ROW_H)) // ROW_H) + 4)
            for i in range(first, last):
                typ, cid, name, v, vol, url = rows[i]
                y0 = i * ROW_H
                if dl:
                    if i == self.hover:
                        cv.create_rectangle(0, y0, W, y0 + ROW_H - 1, fill=t.c("hover", t.c("surface_high")),
                                            outline="")
                    cv.create_line(0, y0 + ROW_H - 1, W, y0 + ROW_H - 1, fill=line)
                else:
                    TH.round_rect(cv, 0, y0 + 3, W, y0 + ROW_H - 3, 10,
                                  fill=t.c("hover", t.c("surface_high")) if i == self.hover else raised, outline=line)
                cy = y0 + ROW_H // 2
                img = self.icons.get(url)                  # poe.ninja's picture (art cache); its first letter until
                #                                            it's downloaded (3.1: no pictures ship with the app)
                if img is not None:
                    cv.create_image(14 + ICON // 2, cy, image=img)
                else:
                    TH.round_rect(cv, 14, cy - ICON // 2, 14 + ICON, cy + ICON // 2, 8, fill=t.c("surface_sunken"),
                                  outline=line)
                    cv.create_text(14 + ICON // 2, cy, text=name[:1], font=("Segoe UI", 10, "bold"), fill=brass)
                cv.create_text(cols[0], cy, text=name, anchor="w", font=("Segoe UI", 10, "bold"),
                               fill=strong, width=cols[1] - cols[0])
                cv.create_text(cols[2] - 16, cy, text=f"{fmt_worth(v)} div", anchor="e", font=("Segoe UI", 10), fill=txt)
                tr = trends.get(str(cid).lower()) if cid != "divine" else (0.0, [0.0] * 7)
                if tr:                                     # 3.0.4: the week in divines - a small line, then ▲/▼ and %
                    pct, pts = tr
                    good, bad = t.c("good", txt), t.c("bad", warn)
                    col = good if pct > 0.05 else bad if pct < -0.05 else mut
                    word = "• 0%" if abs(pct) < 0.05 else f"{'▲ +' if pct > 0 else '▼ −'}{abs(pct):.1f}%"
                    cv.create_text(cols[4] - 16, cy, text=word, anchor="e", font=("Segoe UI", 10), fill=col)
                    vals = [p for p in pts if p is not None]
                    sx0, sx1 = cols[2] + 8, cols[4] - 86
                    if len(vals) >= 2 and sx1 - sx0 > 30:
                        lo, hi = min(vals), max(vals)
                        span = (hi - lo) or 1.0
                        xy = []
                        for j, p in enumerate(pts):
                            if p is not None:
                                xy += [sx0 + j * (sx1 - sx0) / max(1, len(pts) - 1), cy + 8 - (p - lo) / span * 16]
                        cv.create_line(*xy, fill=col, width=2)
                per = 1 / v
                cv.create_text(cols[3] - 16, cy, text=f"{per:,.0f}" if per >= 10 else f"{per:.2g}", anchor="e",
                               font=("Segoe UI", 10), fill=txt)
                bx0, bx1 = cols[3], W - 70
                if bx1 - bx0 > 30:
                    cv.create_rectangle(bx0, cy - 3, bx1, cy + 3, fill=t.c("surface_sunken"), outline="")
                    cv.create_rectangle(bx0, cy - 3, bx0 + (bx1 - bx0) * min(1, vol / top_vol) ** 0.5, cy + 3,
                                        fill=brass, outline="")
                if vol < THIN:
                    cv.create_text(W - 12, cy, text="! Thin", anchor="e", font=("Segoe UI", 9, "bold"), fill=warn)
                else:
                    cv.create_text(W - 12, cy, text=f"{vol:,.0f}", anchor="e", font=("Segoe UI", 9), fill=mut)
        self.status.config(text=RATES.status_text() + (f"  ·  last problem: {RATES.error}" if RATES.error else "")
                           + f"  ·  {len(rows)} items. 7 days: the price change in divines over the last week, "
                             f"from poe.ninja. Traded: how much poe.ninja saw change hands, in divines. "
                             f"Under {THIN} is marked ! Thin, its price is shaky.")
