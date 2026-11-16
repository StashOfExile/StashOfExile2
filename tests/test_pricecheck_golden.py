"""The price checker's golden test: every copied item in tests/fixtures/pricecheck_items.txt, read and priced the way
the app does it today, must come out exactly as recorded in tests/fixtures/pricecheck_golden.json.

For each item it records: where a copy goes (the bulk exchange, the tablet / jewel reader, waystones, gear: gems,
type-only items, white / blue bases, uniques, the rest - or "not priced" with the line the app shows), the item as
read (name, base, flags, every mod with its kind, tier, trade ids), each mod's tick (★ high / ☑ normal / ignored, from
the tier and rating rules and the gear checker's own picks) with its Min / Max, and every trade search the pricing
would send (offline: each search answers "0 found", so every step of the ladder is recorded).

    python3.12 -m unittest tests.test_pricecheck_golden           (or tests/runall.sh)
    python3.12 tests/test_pricecheck_golden.py --regen            rewrite the golden file (only after a deliberate
                                                                   change - say which in the commit)"""
import json
import os
import queue
import re
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-golden-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIX = os.path.join(ROOT, "tests", "fixtures")
ITEMS = os.path.join(FIX, "pricecheck_items.txt")
GOLDEN = os.path.join(FIX, "pricecheck_golden.json")

from soe2 import engine as EN, gamedata as GD, gear as G, mods as M, trade as T, waystone as W   # noqa: E402
from soe2.config import SETTINGS                                                                # noqa: E402
from soe2.wealth import parse_currency_item                                                     # noqa: E402


def load_items():
    out, name, buf = {}, None, []
    with open(ITEMS, encoding="utf-8") as f:
        for line in f.read().split("\n"):
            if line.startswith("=== "):
                if name:
                    out[name] = "\n".join(buf).strip("\n")
                name, buf = line[4:].strip(), []
            elif name is not None:
                buf.append(line)
            # (lines before the first "===" are the file's own notes)
    if name:
        out[name] = "\n".join(buf).strip("\n")
    return out


def stat_table():
    """The trade site's stat list as the engine keeps it (wording -> {group: id}), made offline from the game data's
    own wordings - so tablets and jewels resolve the same every run."""
    table = {}
    for s in GD.load()["stats"]:
        words = {s["ref"]} | {m["string"] for m in s.get("matchers") or [] if not m.get("negate")}
        for w in words:
            k = M.norm(w)
            for grp, ids in (s.get("trade") or {}).items():
                if ids:
                    table.setdefault(k, {}).setdefault(grp, ids[0])
    return table


class _Market:
    def lower_bound(self, *a, **k): return None
    def mod_median(self, *a, **k): return None
    def record(self, *a, **k): pass
    def pool(self, *a, **k): pass
    def comparables(self, *a, **k): return []
    def my_listed(self, *a, **k): return []
    def log_prediction(self, *a, **k): pass
    def accuracy(self, *a, **k): return 0, 0, 0


def _plain(x):
    """JSON-safe, stable."""
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (set, frozenset)):
        return sorted(_plain(v) for v in x)
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, float):
        return round(x, 4)
    return x


class _Fake:
    """Just enough of the app window for App.not_priceable_yet / App.read_any."""
    def __init__(self):
        self.status_text, self.cards = "", []

    def info_card(self, text, actions=(), secs=25):
        self.cards.append(text)

    def stack_price(self, *a, **k):
        pass


def route_of(text):
    """Where the app sends this copy - Price Checks' own order (pricecheck_page.pc_take, app.read_any)."""
    if not text.lstrip().startswith("Item Class:"):
        return "not an item", None
    cur = parse_currency_item(text)
    if cur and cur[2] == "Wombgifts":
        cur = None
    if cur:
        return "exchange", list(cur)
    it = M.parse_item(text)
    if it:
        return "tablet/jewel reader", it
    it = W.parse_waystone(text)
    if it:
        return "waystone", it
    it = G.parse_gear(text)
    if it is None:
        return "not priced", None
    s = it.get("search") or {}
    if s.get("gem"):
        kind = "gem"
    elif it.get("rarity") == "Currency":
        kind = "type only"
    elif s.get("base_exact"):
        kind = "white/magic base"
    elif it.get("rarity") == "Unique":
        kind = "unique"
    elif s.get("type"):
        kind = "by base type"
    else:
        kind = "by category and totals"
    return "gear: " + kind, it


MOD_KEYS = ("kind", "text", "shown", "tier", "sid", "ids", "flags", "value", "lo", "hi", "covered", "auto", "option",
            "novalue", "typed_only", "group", "source", "affix", "note", "header")


def snapshot(text, rules=None, tiers=None):
    from soe2.app import App
    out = {"advanced": bool(App.ADVANCED.search(text or "")), "item_copy": (text or "").lstrip().startswith("Item Class:")}
    out["copy_problem"] = GD.copy_problem(text)          # the line a copy that isn't an English item gets
    g = GD.read_item(text)
    out["read"] = None if g is None else {
        k: g.get(k) for k in ("class_text", "rarity", "name", "base", "class", "flags", "props", "stack", "sockets",
                              "socket_types", "corrupted", "unknown", "flavour")}
    if g is not None:
        out["read"]["mods"] = [{k: m.get(k) for k in ("text", "kind", "source", "tier", "affix", "values", "range",
                                                        "stat", "trade", "header") if k in m} for m in g["mods"]]
    route, it = route_of(text or "")
    out["route"] = route
    if route == "exchange":
        out["exchange"] = it
        return _plain(out)
    if route in ("not an item", "not priced"):
        fake = _Fake()
        if route == "not priced":
            App.not_priceable_yet(fake, text)
        out["unpriced"] = fake.status_text
        if route == "not priced":                         # Price Checks' line for it (pc_take)
            out["pc_line"] = GD.unpriced_line(g)
        return _plain(out)
    out["item"] = {k: it.get(k) for k in ("class", "gclass", "rarity", "name", "base", "tier", "uses", "corrupted",
                                          "quality", "sockets", "socket_types", "ilvl", "search", "notes", "waystone",
                                          "gear", "group_id")}
    out["item"].update({k: it[k] for k in ("area_level", "top_other") if it.get(k) is not None})
    rec = {"id": 1, "item": it, "src": "manual", "ov": {}, "opts": None, "raw": text}
    eng = EN.Engine({1: rec}, queue.Queue())
    eng.table = TABLE
    queries = []

    def gear_search(league, q):
        queries.append(json.loads(json.dumps(q)))
        return 0, [], None

    def item_search(league, base, filters, count_min, corrupted=None):
        queries.append({"base": base, "filters": json.loads(json.dumps(filters)), "count_min": count_min})
        return 0, [], None
    with mock.patch.dict(M.RULES, rules or {}, clear=True), mock.patch.dict(M.TIERS, tiers or {}, clear=True), \
            mock.patch.object(EN, "MARKET", _Market()), mock.patch.object(G, "run_search", gear_search), \
            mock.patch.object(EN, "search_ids", item_search):
        eng.resolve_rec(rec)
        rows = []
        for m in it["mods"]:
            row = {k: m.get(k) for k in MOD_KEYS if m.get(k) not in (None, "", [], set(), False)}
            row["impact"] = T.mod_impact(rec, m)
            row["min_max"] = M.vfilter(m)
            if not it.get("gear"):
                row["rating_tier"] = M.tier_key(M.norm(m["text"]))
            rows.append(row)
        out["mods"] = rows
        eng._price_rec(rec, lambda: None)
    out["queries"] = queries
    out["label"] = rec.get("label")
    return _plain(out)


# a second look at two items, with your own ratings (Rate Mods): they must still decide what is searched
def rated_rules(items):
    from soe2.ratemods import key_for
    rules, tiers = {}, {}
    it = G.parse_gear(items["rare_ring"])
    rec = {"item": it}
    for m in it["mods"]:
        k = key_for(rec, m)
        if k and "dexterity" in k:
            rules[k] = "high"
        elif k and "maximum life" in k:
            rules[k] = "ignore"
    tab = M.parse_item(items["rare_tablet_breach"])
    for m in tab["mods"]:
        if "waystones" in m["text"].lower():
            tiers[M.norm(m["text"])] = "D"
        elif "rarity" in m["text"].lower():
            rules[M.norm(m["text"])] = "high"
    return rules, tiers


TABLE = None


def build_all():
    global TABLE
    SETTINGS.update(league="Standard", min_results=3, range_factor=0.9, status="Instant Buyout", age="2 days",
                    spread_warn=20, memory_hours=24)
    if TABLE is None:
        TABLE = stat_table()
        M.DUPS.clear()
        M.OPTS.clear()
        T.build_sidtext(TABLE)
    items = load_items()
    out = {name: snapshot(text) for name, text in items.items()}
    rules, tiers = rated_rules(items)
    for name in ("rare_ring", "rare_tablet_breach"):
        out[name + " (rated)"] = snapshot(items[name], rules, tiers)
    return out


def diff(a, b, path=""):
    """[(path, golden, now)] for every place two snapshots differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k, "<missing>"), b.get(k, "<missing>"), f"{path}.{k}" if path else k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [(path, a, b)]


class PriceCheckGolden(unittest.TestCase):
    maxDiff = None

    def test_every_item_prices_as_recorded(self):
        with open(GOLDEN, encoding="utf-8") as f:
            golden = json.load(f)
        now = build_all()
        self.assertEqual(sorted(golden), sorted(now), "the corpus and the golden file list different items")
        bad = []
        for name in golden:
            for p, was, is_ in diff(golden[name], now[name]):
                bad.append(f"{name}: {p}\n    golden: {json.dumps(was, ensure_ascii=False)[:300]}\n"
                           f"    now:    {json.dumps(is_, ensure_ascii=False)[:300]}")
        self.assertFalse(bad, "price check changed:\n" + "\n".join(bad[:40]) + (f"\n... {len(bad) - 40} more" if len(bad) > 40 else ""))

    def test_corpus_covers_every_route(self):
        with open(GOLDEN, encoding="utf-8") as f:
            golden = json.load(f)
        routes = {v["route"] for v in golden.values()}
        for r in ("exchange", "tablet/jewel reader", "waystone", "gear: gem", "gear: type only", "gear: white/magic base",
                  "gear: unique", "gear: by base type", "gear: by category and totals", "not priced", "not an item"):
            self.assertIn(r, routes)


class FlagMarks(unittest.TestCase):
    """Corrupted, Mirrored, Fractured, Desecrated, Sanctified: a mark and a word, on listings and on your item; the
    searches don't change (the golden test above)."""

    def test_listing_flags(self):
        from soe2.pricecheck_page import flag_text, listing_facts
        e = {"id": "x", "listing": {"price": {"amount": 1, "currency": "divine"}},
             "item": {"name": "A", "typeLine": "Sapphire Ring", "corrupted": True, "duplicated": True,
                      "fracturedMods": ["+1 to Strength"], "sanctified": True,
                      "explicitMods": [{"description": "+5 to Dexterity", "flags": {"desecrated": True}}]}}
        f = listing_facts(e)
        self.assertEqual(set(f["flags"]), {"corrupted", "mirrored", "fractured", "desecrated", "sanctified"})
        self.assertEqual(flag_text(f["flags"]), "⊘ Corrupted   ◈ Mirrored   ◆ Fractured   ✚ Desecrated   ✦ Sanctified")
        plain = listing_facts({"id": "y", "item": {"typeLine": "Sapphire Ring"}, "listing": {}})
        self.assertEqual(plain["flags"], [])
        self.assertEqual(flag_text(plain["flags"]), "")

    def test_own_flags(self):
        from soe2.pricecheck_page import own_flags
        items = load_items()
        for name, want in (("rare_ring_mirrored", {"mirrored"}), ("rare_ring_sanctified", {"sanctified"}),
                           ("rare_amulet_fractured", {"fractured"}), ("rare_belt_desecrated", {"desecrated"}),
                           ("rare_gloves_corrupted_enchant", {"corrupted"}), ("rare_ring", set())):
            text = items[name]
            self.assertEqual(own_flags({"item": G.parse_gear(text), "raw": text}), want, name)


if __name__ == "__main__":
    if "--regen" in sys.argv:
        data = build_all()
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        print(f"wrote {GOLDEN} ({len(data)} items)")
    else:
        unittest.main()
