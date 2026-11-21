"""Wealth tracker: what you counted or scanned, poe.ninja prices, snapshots.

Part of StashOfExile2. Split out of the single-file app in 1.37 (see the launcher's VERSION HISTORY)."""

import json
import os
import re
import requests
import threading
import time
from .config import load_json, save_json, SETTINGS
from . import buglog
from .rates import Rates
from . import gamedata


# ------------------------------------------------------------------ wealth: net worth of what you hold (1.33)
# 3.0.7 (GGG policy audit): Wealth no longer reads stash tabs through the trade site (it searched your account's
# listings at a marker price) - Scan stash and Count by hand fill it, poe.ninja prices it.

NINJA_ECON = (os.environ.get("SOE2_NINJA") or "https://poe.ninja") + "/poe2/api/economy"


NINJA_EXCHANGE_TYPES = ["Currency", "Fragments", "Abyss", "UncutGems", "LineageSupportGems", "Essences", "SoulCores",
                        "Idols", "Runes", "Ritual", "Expedition", "Delirium", "Breach", "Verisium"]


NINJA_ITEM_TYPES = ["UniqueWeapons", "UniqueArmours", "UniqueAccessories", "UniqueFlasks", "UniqueCharms", "UniqueJewels",
                    "UniqueSanctumRelics", "UniqueTablets", "PrecursorTablets"]


from .config import APP_UA as WEALTH_UA                    # 2.92.0: one honest name for the app


def wealth_trade_url(league, qid):
    return f"https://www.pathofexile.com/trade2/search/poe2/{requests.utils.quote(league)}/{qid}"


COUNTED_TAB = "counted"               # the "tab" of everything counted by hand
COUNTED_LABEL = "Counted by hand"
SRC_LABEL = {"counted": "Counted by hand", "scanned": "Scanned", "hand": "Counted by hand"}   # (UI overhaul: one name)   # 2.105.1: where a stack came from
CLASS_CAT = {"stackable currency": "currency", "map fragments": "fragment", "omen": "currency", "socketable": "currency",
             "delirium instill": "currency", "essence": "currency", "splinter": "fragment", "catalyst": "currency",
             "divination card": "card", "uncut gem": "gem"}


def holding_item(name, h):
    """A counted stack as a Wealth item (same shape as one read from a tab)."""
    cls = (h.get("cls") or "").lower()
    return {"lid": "held:" + name, "tab": COUNTED_TAB, "stash": SRC_LABEL.get(h.get("src"), COUNTED_LABEL), "name": "",
            "type": name, "base": name,
            "frame": 5, "qty": int(h.get("qty") or 0), "ilvl": None, "corrupted": False,
            "cat": CLASS_CAT.get(cls, "currency" if not cls else cls.split()[0]), "level": None, "mods": [], "text": None,
            "held": True}


def parse_stack(text):
    """A copied stack (Ctrl+C on currency, fragments, essences, omens ...) -> (name, quantity, item class) or None."""
    if not text or "Stack Size:" not in text:
        return None
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
    cls, name, qty = "", None, None
    for i, l in enumerate(lines):
        if l.startswith("Item Class:"):
            cls = l.split(":", 1)[1].strip()
        elif l.startswith("Rarity:"):
            name = next((x for x in lines[i + 1:] if x and not x.startswith("--")), None)
        elif l.startswith("Stack Size:"):
            m = re.match(r"Stack Size:\s*([\d,.\s]+)", l)
            if m:
                try:
                    qty = int(re.sub(r"[^\d]", "", m.group(1)))
                except ValueError:
                    qty = None
    if not name or not qty:
        return None
    return name, qty, cls


def is_lineage(lines):
    """A gem copy's lines -> True when its tags line says Lineage ("Support, Lineage, Spell, Fire")."""
    return any("Lineage" in [t.strip() for t in l.split(",")] for l in lines[3:8] if "," in l or l == "Lineage")


def parse_currency_item(text):
    """2.114.0 (feedback: a Signet Wombgift copied with the price check key did nothing): any "Rarity: Currency" item
    -> (name, quantity, item class), a stack or a single one (no Stack Size line = 1). None for anything else."""
    hit = parse_stack(text)
    if hit:
        return hit
    lines = [l.strip() for l in (text or "").replace("\r", "").split("\n")]
    cls = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Item Class:")), "")
    if "Rarity: Gem" in lines and is_lineage(lines):           # 2.129.0 (feedback): lineage gems are traded on the
        i = lines.index("Rarity: Gem")                         # currency exchange - poe.ninja prices them
        name = next((x for x in lines[i + 1:] if x and not x.startswith("--")), None)
        return (name, 1, cls) if name else None
    if "Rarity: Currency" not in lines:
        return None
    i = lines.index("Rarity: Currency")
    name = next((x for x in lines[i + 1:] if x and not x.startswith("--")), None)
    return (name, 1, cls) if name else None


def wealth_display_name(it):
    base = it["type"] or it["base"]
    return f"{it['name']} {base}".strip() if it["name"] else base


class WealthStore:
    """wealth.json: what you counted or scanned (holdings) and the net worth history. tabs / items / results /
    rare_prices held the stash tabs read through the trade site before 2.105.1 - emptied on load."""

    def __init__(self):
        d = load_json("wealth.json", {})
        self.lock = threading.RLock()
        self.tabs = d.get("tabs", [])              # {id, label, amount, currency, enabled}
        self.items = d.get("items", {})            # tab id -> [wealth_item]
        self.snapshots = d.get("snapshots", [])    # {ts, league, total, by_tab, by_cat, n, priced}
        self.results = d.get("results", {})        # tab id -> {total, fetched, warnings, error, qid, ts}
        self.last_sync = d.get("last_sync", 0)
        self.rare_prices = d.get("rare_prices", {})  # 2.0: listing id -> {est, sig, ts, label, conf, qid, league}
        self.holdings = d.get("holdings", {})      # 2.0 beta 7: counted by hand: name -> {qty, cls, ts, src}
        # 2.105.1 (feedback: synced stash tabs are gone - a clean start): what tabs read is dropped once - the tabs,
        # their items, results and rare prices, and the history they were part of. Counted currency stays.
        if self.tabs or self.items or self.results or self.rare_prices:
            self.tabs, self.items, self.results, self.rare_prices, self.snapshots = [], {}, {}, {}, []
            self.last_sync = 0
            self.save()

    def save(self):
        with self.lock:
            known = {str(i["lid"]) for lst in self.items.values() for i in lst}
            self.rare_prices = {k: v for k, v in self.rare_prices.items() if k in known}   # gone from your tabs: forget
            data = {"tabs": self.tabs, "items": self.items, "snapshots": self.snapshots[-3000:],
                    "results": self.results, "last_sync": self.last_sync, "rare_prices": self.rare_prices,
                    "holdings": self.holdings}
        save_json("wealth.json", data)

    def tab(self, tab_id):
        return next((t for t in self.tabs if t["id"] == tab_id), None)

    def all_items(self):
        with self.lock:
            known = {t["id"] for t in self.tabs}
            out = [i for tid, lst in self.items.items() if tid in known for i in lst]
            return out + [holding_item(n, h) for n, h in sorted(self.holdings.items())]

    # ---- counted by hand (2.0 beta 7): currency and other stacks you copy (Ctrl+C) or type in
    def set_holding(self, name, qty, cls="", src=None):
        """src (2.105.1): counted (Ctrl+C) / scanned (Scan stash) / hand (typed in) - the Items list's From."""
        name = name.strip()
        with self.lock:
            if qty is None or qty <= 0:
                self.holdings.pop(name, None)
            else:
                old = self.holdings.get(name) or {}
                self.holdings[name] = {"qty": int(qty), "cls": cls or old.get("cls", ""), "ts": time.time(),
                                       "src": src or old.get("src") or "counted"}
        self.save()

    def holding(self, name):
        h = self.holdings.get(name.strip())
        return h["qty"] if h else 0

    def snapshot(self, league, prices, why="", replace=False):
        rows, total, priced = wealth_rows(self.all_items(), prices)
        if not rows:
            return None
        by_tab, by_cat = {}, {}
        for it, each, tot, _src in rows:
            if tot is None:
                continue
            by_tab[it["stash"]] = by_tab.get(it["stash"], 0) + tot
            cat = (it["cat"] or "other").split(".")[0]
            by_cat[cat] = by_cat.get(cat, 0) + tot
        snap = {"ts": time.time(), "league": league, "total": total, "by_tab": by_tab, "by_cat": by_cat,
                "n": len(rows), "priced": priced, "why": why}     # why (2.3.0): counted / synced / prices / ...
        with self.lock:
            if self.snapshots and self.snapshots[-1].get("league") == league and (
                    replace or snap["ts"] - self.snapshots[-1]["ts"] < 300):
                self.snapshots[-1] = snap           # a price update right after a sync: replace, don't add a twin
            else:
                self.snapshots.append(snap)
        self.save()
        return snap


PRICES_VERSION = 3          # 3.0.4: each line's 7-day price line (sparkline) is kept too


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _spark(sp):
    """poe.ninja's sparkline {"totalChange": -6.2, "data": [0, -1.1, ... 7 points, % against the first]} ->
    (total %, [points]) or None. A missing point (null) takes the one before."""
    if not isinstance(sp, dict):
        return None
    data, out, last = sp.get("data"), [], 0.0
    if not isinstance(data, list) or not data:
        tc = _num(sp.get("totalChange"))
        return (tc, [0.0, tc]) if tc is not None else None
    for p in data:
        v = _num(p)
        last = v if v is not None else last
        out.append(last)
    tc = _num(sp.get("totalChange"))
    return (tc if tc is not None else out[-1]), out


def _combine(pts, base):
    """An item's points (% against the first) in its pair currency + the pair's points in divines -> the item's
    points in divines. The two lists are lined up from their ends (both end now)."""
    n = min(len(pts), len(base))
    if not n:
        return None
    a, b = pts[-n:], base[-n:]
    out = []
    for x, y in zip(a, b):
        out.append(None if x is None or y is None else ((1 + x / 100.0) * (1 + y / 100.0) - 1) * 100.0)
    return out


def slug(name):
    """'Hinekora's Lock' -> 'hinekoras-lock' (how poe.ninja writes its ids)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


class WealthPrices:
    """poe.ninja's PoE 2 prices for stackables (exchange overview) and uniques (item overview), all in divines.
    Refreshed at most hourly (PoE 2 data only updates about hourly), one request at a time, with ETags so an unchanged
    category costs poe.ninja almost nothing. Cached in wealth_prices.json."""

    def __init__(self):
        c = load_json("wealth_prices.json", {})
        if c.get("v") != PRICES_VERSION:            # 2.0 beta 7: older caches lack item names: fetch everything again
            c = {}
        self.league = c.get("league")          # the trade-site league these prices are for
        self.src = c.get("src")                # how poe.ninja spells it
        self.ts = c.get("ts", 0)
        self.parts = c.get("parts", {})        # type -> parsed response (values in poe.ninja's primary currency)
        self.etags = c.get("etags", {})
        self.lock = threading.Lock()
        self.errors = []
        self._index()

    def age(self):
        return time.time() - self.ts if self.ts else None

    def _get(self, typ, league):
        """One poe.ninja overview. -> parsed JSON, or None when it hasn't changed since last time (HTTP 304)."""
        path = "exchange/current/overview" if typ in NINJA_EXCHANGE_TYPES else "stash/current/item/overview"
        hdr = {"User-Agent": WEALTH_UA, "Accept": "application/json"}
        if self.src == league and self.etags.get(typ) and typ in self.parts and \
                (typ not in NINJA_ITEM_TYPES or "icons" in self.parts[typ]):   # (3.0.6: a part from before icons)
            hdr["If-None-Match"] = self.etags[typ]
        r = requests.get(f"{NINJA_ECON}/{path}", params={"league": league, "type": typ}, headers=hdr, timeout=20)
        if r.status_code == 304:
            return None
        r.raise_for_status()
        self.etags[typ] = r.headers.get("ETag")
        return r.json()

    def _learn_icons(self):
        """3.0.6: the uniques' pictures poe.ninja sends with its prices go to the app's picture list (Price Checks'
        icons.json) - so every unique (each unique tablet too) has its picture. No request of its own."""
        got = {}
        for typ in NINJA_ITEM_TYPES:
            got.update((self.parts.get(typ) or {}).get("icons") or {})
        if got:
            try:
                from .pricecheck_page import icons_learn
                icons_learn(got)
            except Exception:
                buglog.caught()

    def ensure(self, league, force=False):
        """Refresh if older than an hour (or `force`). `league` is the trade-site name; poe.ninja may spell it
        differently, so the same alternatives as the exchange rates are tried (Rates.names_for)."""
        if not league or (not force and self.league == league and self.age() is not None and self.age() < 3600):
            return
        with self.lock:
            errors, parts = [], {}
            for name in Rates.names_for(league):
                errors, parts = [], dict(self.parts) if self.league == league else {}
                for typ in NINJA_EXCHANGE_TYPES + NINJA_ITEM_TYPES:
                    try:
                        body = self._get(typ, name)
                    except Exception as e:
                        errors.append(f"{typ}: {str(e)[:80]}")
                        continue
                    if body is not None:                       # None = 304, what we have is still current
                        parts[typ] = self._parse(typ, body)
                    if typ == "Currency" and not (parts.get("Currency") or {}).get("lines"):
                        break                                  # this spelling has no data: don't ask for the rest
                if (parts.get("Currency") or {}).get("lines"):
                    self.parts, self.league, self.src, self.ts = parts, league, name, time.time()
                    break                                      # this spelling of the league worked
            self.errors = errors
            save_json("wealth_prices.json", {"v": PRICES_VERSION, "league": self.league, "src": self.src, "ts": self.ts,
                                             "parts": self.parts, "etags": self.etags})
            self._index()

    def ensure_types(self, league, types=("Delirium",)):
        """2.17.0: just these categories (plus Currency, for the divine rate) when they're over an hour old - Game
        search > Anoints only needs the Liquid Emotions, not all twenty categories."""
        if not league:
            return
        tts = self.__dict__.setdefault("tts", {})
        need = [t for t in ("Currency",) + tuple(types)
                if not (self.league == league and t in self.parts and time.time() - tts.get(t, self.ts) < 3600)]
        if not need:
            return
        with self.lock:
            for name in ([self.src] if self.league == league and self.src else []) + Rates.names_for(league):
                parts = dict(self.parts) if self.league == league else {}
                errors = []
                for typ in need:
                    try:
                        body = self._get(typ, name)
                    except Exception as e:
                        errors.append(f"{typ}: {str(e)[:80]}")
                        continue
                    if body is not None:
                        parts[typ] = self._parse(typ, body)
                    tts[typ] = time.time()
                if (parts.get("Currency") or {}).get("lines"):
                    if self.league != league:
                        self.ts = 0                            # only some categories: Wealth still fetches the rest
                    self.parts, self.league, self.src = parts, league, name
                    break
            self.errors = errors
            save_json("wealth_prices.json", {"v": PRICES_VERSION, "league": self.league, "src": self.src, "ts": self.ts,
                                             "parts": self.parts, "etags": self.etags})
            self._index()

    def for_league(self, league=None):
        """2.73.4: are these prices for your league (Settings' league, or `league`)? Prices from another league are
        never shown as yours - a league switch waits for the next refresh."""
        want = league if league is not None else (SETTINGS.get("league") or "")
        return not want or not self.league or self.league == want

    def named(self, name, league=None):
        """divines for one stackable by its name (or poe.ninja id), or None (also when the prices held are for
        another league than yours)."""
        if not self.for_league(league):
            return None
        hit = self.by_name.get(name.lower()) or getattr(self, "by_slug", {}).get(slug(name))
        return hit[0] if hit else None

    @staticmethod
    def _parse(typ, body):
        if typ in NINJA_EXCHANGE_TYPES:
            core = body.get("core") or {}
            names, images = {}, {}
            # 2.0 beta 7: every item's name is in the top-level "items" list; "core.items" only holds the few core
            # currencies (Divine / Chaos / Exalted). Reading only core.items left everything else nameless, so only
            # those three were found. (Layout: ApiExchangeOverview.Items.)
            for items in (core.get("items"), body.get("items")):
                if isinstance(items, list):
                    for i in items:
                        if isinstance(i, dict) and i.get("id"):
                            names[i["id"]] = i.get("name") or names.get(i["id"]) or i["id"]
                            if i.get("image"):
                                images[i["id"]] = i["image"]
                elif isinstance(items, dict):
                    for k, v in items.items():
                        names[k] = (v or {}).get("name") or names.get(k) or k
            lines, spark = [], {}
            for ln in body.get("lines") or []:
                try:
                    lines.append([ln["id"], names.get(ln["id"]) or ln["id"], float(ln["primaryValue"]),
                                  float(ln.get("volumePrimaryValue") or 0)])
                except (KeyError, TypeError, ValueError):
                    continue
                sp = _spark(ln.get("sparkline") or ln.get("sparkLine"))     # 3.0.4: the week, for Wealth
                if sp:
                    spark[ln["id"]] = [sp[0], sp[1], ln.get("maxVolumeCurrency"), _num(ln.get("maxVolumeRate"))]
            return {"primary": core.get("primary"), "names": names, "lines": lines, "images": images, "spark": spark}
        lines, spark, icons = [], {}, {}
        for ln in body.get("lines") or []:
            icon = str(ln.get("icon") or "") if isinstance(ln, dict) else ""
            if ln.get("name") and icon.startswith("https://"):            # 3.0.6: each unique's picture (kept)
                icons.setdefault(str(ln["name"]), icon)
            try:
                lines.append([ln["name"], ln.get("baseType") or "", float(ln["primaryValue"]),
                              int(ln.get("listingCount") or 0), bool(ln.get("corrupted"))])
            except (KeyError, TypeError, ValueError):
                continue
            sp = _spark(ln.get("sparkLine") or ln.get("sparkline"))         # 3.0.4: in the league's primary currency
            k = ln["name"].lower()
            if sp and (k not in spark or lines[-1][3] > spark[k][2]):
                spark[k] = [sp[0], sp[1], lines[-1][3]]
        return {"lines": lines, "spark": spark, "icons": icons}

    def _index(self):
        """Build the lookup tables in divines."""
        self._learn_icons()
        cur = self.parts.get("Currency") or {}
        primary = cur.get("primary") or "divine"
        per_div = 1.0
        if primary != "divine":                                # values are in e.g. exalted: divide by exalted-per-divine
            per_div = next((v for cid, _n, v, _vol in cur.get("lines", []) if cid == "divine"), None) or 0
        self.ok = per_div > 0
        self.primary = primary
        self.by_name, self.uniques = {}, {}
        if not self.ok:
            return
        prim_name = (cur.get("names") or {}).get(primary) or {"exalted": "Exalted Orb", "divine": "Divine Orb",
                                                               "chaos": "Chaos Orb"}.get(primary)
        if prim_name:
            self.by_name[prim_name.lower()] = (1.0 / per_div, "poe.ninja Currency")
        self.by_slug = {}
        for typ in NINJA_EXCHANGE_TYPES:
            for cid, name, v, _vol in (self.parts.get(typ) or {}).get("lines", []):
                self.by_name[str(name).lower()] = (v / per_div, f"poe.ninja {typ}")
                self.by_slug[str(cid).lower()] = (v / per_div, f"poe.ninja {typ}")
        for typ in NINJA_ITEM_TYPES:
            for name, base, v, count, corrupted in (self.parts.get(typ) or {}).get("lines", []):
                self.uniques.setdefault(name.lower(), []).append((base.lower(), v / per_div, count, corrupted, f"poe.ninja {typ}"))
        self.by_name.setdefault("divine orb", (1.0, "poe.ninja Currency"))
        try:
            self._index_trends(primary, per_div)
        except Exception:                                      # (a new answer shape never breaks the prices)
            buglog.caught()
            self.trend_by_name, self.trend_by_slug = {}, {}

    def _index_trends(self, primary, per_div):
        """3.0.4: each item's price change over the last 7 days, in divines -> trend_by_name / trend_by_slug:
        (change %, [7 points: % against the first]). poe.ninja's line is for the pair the item trades most against
        (maxVolumeCurrency): the rate is turned the right way round by checking it against the price, then the pair's
        own change in divines is added on (divines: none)."""
        value = {}                                             # id -> value in the primary currency
        spark = {}
        for typ in NINJA_EXCHANGE_TYPES:
            part = self.parts.get(typ) or {}
            for cid, _n, v, _vol in part.get("lines", []):
                value[cid] = v
            spark.update(part.get("spark") or {})
        value.setdefault(primary, 1.0)
        memo = {}

        def in_div(cid, depth=0):
            """-> [points] (% against the first) of cid's price in divines, or None."""
            if cid == "divine":
                return [0.0] * 7
            if cid in memo:
                return memo[cid]
            memo[cid] = None                                   # (a loop: unknown)
            sp = spark.get(cid)
            if not sp or depth > 3:
                return None
            _tc, pts, pair, rate = sp
            pair = pair or primary
            v, vp = value.get(cid), value.get(pair)
            if pts and v and vp and rate:
                import math
                direct = abs(math.log(v / (rate * vp)))       # rate = pair per item: same way as the price
                inverse = abs(math.log(v * rate / vp))        # rate = items per pair: the other way
                if inverse < direct:
                    pts = [(100.0 / (1 + p / 100.0) - 100.0) if p > -100 else None for p in pts]
            elif not pts:
                return None
            base = in_div(pair, depth + 1) if pair != cid else [0.0] * 7
            if base is None:
                return None
            out = _combine(pts, base)
            memo[cid] = out
            return out

        self.trend_by_name, self.trend_by_slug = {}, {}
        names = {}
        for typ in NINJA_EXCHANGE_TYPES:
            for cid, name, _v, _vol in (self.parts.get(typ) or {}).get("lines", []):
                names[cid] = name
        for cid in spark:
            pts = in_div(cid)
            if pts and pts[-1] is not None:
                t = (pts[-1], pts)
                self.trend_by_slug[str(cid).lower()] = t
                if cid in names:
                    self.trend_by_name[str(names[cid]).lower()] = t
        prim = in_div(primary) if primary != "divine" else [0.0] * 7
        for typ in NINJA_ITEM_TYPES:
            for k, (_tc, pts, _n) in ((self.parts.get(typ) or {}).get("spark") or {}).items():
                if prim is not None and pts:
                    out = _combine(pts, prim)
                    if out and out[-1] is not None:
                        self.trend_by_name.setdefault(k, (out[-1], out))

    def trend(self, it):
        """3.0.4: (change % over 7 days, [points]) in divines for this item, or None (no poe.ninja line for it,
        or another league's prices)."""
        if not self.for_league() or it["frame"] in (1, 2):
            return None
        tn, ts = getattr(self, "trend_by_name", {}), getattr(self, "trend_by_slug", {})
        if it["frame"] == 3:
            return tn.get(it["name"].lower())
        names = [n for n in (it["type"], it["base"]) if n]
        for n in names:
            if n.lower() in tn:
                return tn[n.lower()]
        for n in names:
            if slug(n) in ts:
                return ts[slug(n)]
        if any(n.lower() == "divine orb" for n in names):
            return 0.0, [0.0] * 7
        return None

    def value(self, it):
        """-> (divines per unit, source) or (None, None)."""
        if it["frame"] not in (1, 2) and not self.for_league():       # 2.73.4: another league's prices: not yours
            return None, None
        if it["frame"] == 3:
            cands = self.uniques.get(it["name"].lower()) or []
            if not cands:
                return None, None
            base = (it["base"] or it["type"]).lower()
            pool = [c for c in cands if c[0] == base] or cands
            pool = [c for c in pool if c[3] == it["corrupted"]] or pool
            best = max(pool, key=lambda c: c[2])
            return best[1], best[4]
        if it["frame"] in (1, 2):                               # magic / rare: not priced here (3.0.7: they came
            return None, None                                   # from stash tabs read through the trade site)
        names = [n for n in (it["type"], it["base"]) if n]
        if it.get("level"):
            names = [f"{n} (Level {it['level']})" for n in names] + names
        for n in names:
            hit = self.by_name.get(n.lower())
            if hit:
                return hit
        for n in names:                                         # poe.ninja's id is often the name as a slug
            hit = getattr(self, "by_slug", {}).get(slug(n))
            if hit:
                return hit
        return None, None                                       # 3.0.6: not on poe.ninja - no price (owner: no guessing)

    def why_unpriced(self, it):
        """Why a stackable has no price (3.0.6: poe.ninja is the only source)."""
        return "not found on poe.ninja"


def wealth_rows(items, prices):
    """-> ([(item, divines each or None, divines total or None, source)], total, priced count). 3.0.4 (owner):
    never a price typed by hand - poe.ninja, else no price (not found on poe.ninja)."""
    rows, total, priced = [], 0.0, 0
    for it in items:
        each, src = prices.value(it)
        tot = each * it["qty"] if each is not None else None
        if tot is not None:
            total += tot
            priced += 1
        rows.append((it, each, tot, src))
    return rows, total, priced


WEALTH = WealthStore()


WPRICES = WealthPrices()
