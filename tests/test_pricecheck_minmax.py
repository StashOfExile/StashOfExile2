"""Round 18 (feedback: a Flowing Raiment with Item level Min 80 / Max 80 found ilvl 81 and 83 - the search sent only
{"min": 80}): every Min / Max box the card shows with a number (the default's or yours) is in every trade search
the price check sends - item level, quality, sockets, tier, requirements and each mod's Min / Max. A white / blue
base's price check is its exact search; Widening (below): ↔ Broaden Search widens it, one step a click.

    python3.12 -m unittest tests.test_pricecheck_minmax          (or tests/runall.sh)"""
import json
import os
import queue
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-minmax-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from soe2 import engine as EN, gear as G, mods as M, net as N, trade as T    # noqa: E402
import test_pricecheck_golden as GOLD                                 # noqa: E402
from soe2.searchopts_page import default_opts                         # noqa: E402
from soe2.pricecheck_page import (PriceCheckPage, broaden_offer, search_tip, search_word,   # noqa: E402
                                  widened_line)

RAIMENT = """Item Class: Body Armours
Rarity: Normal
Exceptional Flowing Raiment
--------
Quality: +22% (augmented)
Energy Shield: 187 (augmented)
--------
Requires: Level 70, 121 Int
--------
Sockets: S S S
--------
Item Level: 80"""

# opts key -> where the trade site keeps it
WHERE = {"ilvl": ("type_filters", "ilvl"), "quality": ("type_filters", "quality"),
         "sockets": ("equipment_filters", "rune_sockets"), "tier": ("map_filters", "map_tier"),
         "req_lvl": ("req_filters", "lvl")}


def run(it, opts=None, src="pc"):
    """Price one item offline, the app's way -> every query it sends."""
    rec = {"id": 1, "item": it, "src": src, "ov": {}, "opts": opts, "raw": ""}
    eng = EN.Engine({1: rec}, queue.Queue())
    eng.table = GOLD.TABLE
    sent = []

    def gear_search(league, q):
        sent.append(json.loads(json.dumps(q)))
        return 0, [], None
    with mock.patch.object(EN, "MARKET", GOLD._Market()), mock.patch.object(G, "run_search", gear_search), \
            mock.patch.object(EN, "search_ids", lambda *a, **k: (0, [], None)):
        eng.resolve_rec(rec)
        eng.price_rec(rec, lambda: None)             # (with rec["opts"], and the any-age retry)
    return sent


def got(q, key, it=None):
    grp, name = WHERE[key]
    if key == "sockets" and ((it or {}).get("search") or {}).get("gem"):
        grp, name = "misc_filters", "gem_sockets"             # (a gem's sockets: the trade site's Gem Sockets)
    return ((q.get("filters") or {}).get(grp) or {}).get("filters", {}).get(name)


class MinMax(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        GOLD.build_all()                    # (the settings and the offline stat table the golden test uses)
        cls.items = GOLD.load_items()

    def test_base_ilvl_min_and_max(self):
        it = G.parse_gear(RAIMENT)
        self.assertEqual(default_opts(it)["ilvl"], {"min": 80, "max": 80})
        for opts in (None, {"ilvl": {"min": 80, "max": 80}}):
            for src in ("pc", "manual"):                       # Price Checks / the overlay card, Bulk Pricing
                qs = run(G.parse_gear(RAIMENT), opts, src)
                self.assertTrue(qs)
                self.assertEqual(got(qs[0], "ilvl"), {"min": 80, "max": 80}, (opts, src))   # the exact search
                for q in qs:                                   # (widening: only ever Min - 1 / Max + 1)
                    self.assertIn(got(q, "ilvl"), ({"min": 80, "max": 80}, {"min": 79, "max": 81}), (opts, src))

    def test_every_default_max_is_searched(self):
        n = 0
        for name, text in self.items.items():
            route, it = GOLD.route_of(text)
            if not route.startswith(("gear", "waystone")):
                continue
            shown = {k: v for k, v in default_opts(it).items() if k in WHERE and isinstance(v, dict) and "max" in v}
            if not shown:
                continue
            for q in run(it):
                for k, v in shown.items():
                    self.assertEqual((got(q, k, it) or {}).get("max"), v["max"], f"{name}: {k}")
                    n += 1
        self.assertGreater(n, 5)

    def test_every_typed_max_is_searched(self):
        n = 0
        for name, text in self.items.items():
            route, it = GOLD.route_of(text)
            if not route.startswith(("gear", "waystone")):
                continue
            boxes = {k: v for k, v in (("ilvl", it.get("ilvl")), ("quality", it.get("quality")),
                                       ("sockets", it.get("sockets")), ("tier", it.get("tier"))) if v}
            for k, v in boxes.items():
                want = {"min": max(1, v - 1), "max": v + 1}
                qs = run(it, {k: want})
                for q in qs:
                    self.assertEqual(got(q, k, it), want, f"{name}: {k}")
                    n += 1
        self.assertGreater(n, 10)

    def test_mod_max_is_searched(self):
        it = G.parse_gear(self.items["rare_ring"])
        rec = {"item": it}
        m = next(m for m in it["mods"] if m.get("sid") and T.mod_impact(rec, m) != "ignore" and not m.get("option")
                 and m.get("group") not in ("total", "pseudo"))
        m["uval"] = {"min": 1, "max": 99}
        self.assertEqual(M.vfilter(m), {"min": 1, "max": 99})
        qs = run(it)
        flat = json.dumps(qs)
        self.assertIn('"max": 99', flat)


# ---- owner (base widening): a quality below 28% drops to 25% and tries again, then 22%, then 0-20% for exceptional
# bases; never widen an exceptional item by removing sockets (a non-exceptional one with the standard maximum of
# sockets excludes them anyway); item level range +/-1; listings up to 1 week old.
# Owner: all of the white base rules apply to magic bases also. Owner: widening never runs on its own - a price
# check is the exact search; while too few are found the card's orange button is ↔ Broaden Search, one step a click.

MAGIC_CROWN = """Item Class: Helmets
Rarity: Magic
Exceptional Zealot Crown of the Lynx
--------
Quality: +29% (augmented)
Armour: 184 (augmented)
Energy Shield: 53 (augmented)
--------
Sockets: S S
--------
Item Level: 81
--------
{ Suffix Modifier "of the Lynx" (Tier: 3) — Attribute }
+20(17-20) to Dexterity"""

MAGIC_ROBE = """Item Class: Body Armours
Rarity: Magic
Flowing Raiment of the Lynx
--------
Quality: +20% (augmented)
Energy Shield: 187 (augmented)
--------
Sockets: S S
--------
Item Level: 79
--------
{ Suffix Modifier "of the Lynx" (Tier: 3) — Attribute }
+20(17-20) to Dexterity"""


def base(text, **kw):
    """A base's copy with its Quality / Sockets / Item Level lines changed."""
    lines = []
    for l in text.split("\n"):
        if l.startswith("Quality:") and "quality" in kw:
            l = f"Quality: +{kw['quality']}% (augmented)"
        elif l.startswith("Sockets:") and "sockets" in kw:
            l = "Sockets: " + " ".join("S" * kw["sockets"])
        elif l.startswith("Item Level:") and "ilvl" in kw:
            l = f"Item Level: {kw['ilvl']}"
        lines.append(l)
    return "\n".join(lines)


def priced(it, at=None, opts=None, src="pc", n=5):
    """Price one item with a fake trade site that finds n listings only at search number `at` (0 = the first; "each":
    every search; None: never). -> (every query sent, the record, the hours each fetch kept listings for)."""
    rec = {"id": 1, "item": it, "src": src, "ov": {}, "opts": opts, "raw": ""}
    eng = EN.Engine({1: rec}, queue.Queue())
    eng.table = GOLD.TABLE
    sent, hours = [], []

    def gear_search(league, q):
        sent.append(json.loads(json.dumps(q)))
        k = len(sent) - 1
        return (n, [f"id{k}-{i}" for i in range(n)], f"q{k}") if at in (k, "each") else (0, [], None)

    def fetch_rich(qid, ids, max_hours=None):
        hours.append(max_hours)
        return [{"id": i, "price": (1, "divine"), "ts": time.time(), "mods": None, "seller": i, "hsids": []}
                for i in ids]
    with mock.patch.object(EN, "MARKET", GOLD._Market()), mock.patch.object(G, "run_search", gear_search), \
            mock.patch.object(EN, "search_ids", lambda *a, **k: (0, [], None)), \
            mock.patch.object(EN, "fetch_rich", fetch_rich), \
            mock.patch.object(EN, "estimate", lambda prices, league: 1.0 if prices else None), \
            mock.patch.object(EN, "unconvertible", lambda prices, league: []), \
            mock.patch.object(EN, "spread_of", lambda stages, league: (None, None, None)):
        eng.resolve_rec(rec)
        eng.price_rec(rec, lambda: None)
    return sent, rec, hours


def press(rec):
    """The card's orange button (PriceCheckPage.pc_search_go) on a copy of the record: -> the item's boxes it
    searches with (the record itself is left as it was priced)."""
    ran, rec = [], dict(rec)
    PriceCheckPage.pc_search_go(types.SimpleNamespace(reprice=ran.append), rec)
    assert ran == [[rec["id"]]]
    return rec.get("opts")


def walk(it, at=None, n=5):
    """Price it, then press ↔ Broaden Search while the card offers it -> [(queries, record)] per price check.
    at: the price check (0 = the first, 1 = the first click ...) that finds n listings; "each": every one."""
    def one(k, opts=None):
        return priced(it, at=0 if at in (k, "each") else None, n=n, opts=opts)[:2]
    out = [one(0)]
    while broaden_offer(out[-1][1]):
        out.append(one(len(out), press(out[-1][1])))
        assert len(out) < 12
    return out


def steps(qs, it=None):
    """Each query -> (item level, quality, sockets, listed within)."""
    return [(got(q, "ilvl"), got(q, "quality"), got(q, "sockets", it),
             (((q.get("filters") or {}).get("trade_filters") or {}).get("filters", {}).get("indexed") or {}).get("option"))
            for q in qs]


def walked(it, at=None, n=5):
    w = walk(it, at, n)
    for qs, _rec in w:
        assert len(qs) == 1, qs                                # one search per price check / click
    return [steps(qs, it)[0] for qs, _rec in w], w


HELMET_LADDER = [({"min": 81, "max": 81}, {"min": 29}, {"min": 2}, "3days"),
                 ({"min": 81, "max": 81}, {"min": 25}, {"min": 2}, "3days"),
                 ({"min": 81, "max": 81}, {"min": 22}, {"min": 2}, "3days"),
                 ({"min": 81, "max": 81}, {"max": 20}, {"min": 2}, "3days"),
                 ({"min": 80, "max": 82}, {"max": 20}, {"min": 2}, "3days"),
                 ({"min": 80, "max": 82}, {"max": 20}, {"min": 2}, "1week")]


class Widening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        GOLD.build_all()                    # (Listed within: 2 days - the trade site's "3days")
        cls.items = GOLD.load_items()

    def test_first_check_is_the_exact_search_only(self):
        for text in (RAIMENT, self.items["normal_helmet_exceptional"], MAGIC_CROWN, self.items["magic_flask"],
                     self.items["normal_body_armour_base"], MAGIC_ROBE):
            it = G.parse_gear(text)
            self.assertTrue(G.widens(it), it["name"])
            qs, rec, _h = priced(it)
            self.assertEqual(len(qs), 1, it["name"])                    # never widened on its own
            self.assertTrue(rec["nomatch"])
            self.assertNotIn("widened", rec["label"])
            self.assertIsNone(rec.get("opts"))                           # (the boxes stay as they were)
            self.assertTrue(broaden_offer(rec), it["name"])
            self.assertEqual(search_word(rec), "↔ Broaden Search")

    def test_exceptional_quality_and_sockets(self):
        it = G.parse_gear(RAIMENT)                             # 22% quality, 3 sockets: exceptional
        self.assertTrue(G.is_exceptional(it["gclass"], it["quality"], it["sockets"], it["name"]))
        e, s3 = {"min": 80, "max": 80}, {"min": 3}
        got_, w = walked(it)
        self.assertEqual(got_, [
            (e, {"min": 22}, s3, "3days"),                             # the card's boxes
            (e, {"max": 20}, s3, "3days"),                             # (25% and 22%: not under its 22%) 0-20%
            ({"min": 79, "max": 81}, {"max": 20}, s3, "3days"),         # item level +/-1
            ({"min": 79, "max": 81}, {"max": 20}, s3, "1week")])        # listed within 1 week
        self.assertEqual(search_tip(w[0][1]), "Next: quality 0–20% - one more search")
        last = w[-1][1]
        self.assertTrue(last["nomatch"])
        self.assertIsNone(widened_line(last))                          # (nothing found: no Widened line)
        self.assertIsNone(broaden_offer(last))                         # no step left: Search again
        self.assertEqual(search_word(last), "Search again")

    def test_ladder_one_step_a_click(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):     # white and magic: the same ladder
            got_, w = walked(G.parse_gear(text))
            self.assertEqual(got_, HELMET_LADDER, text[:40])
            self.assertEqual([b["next"] for b in (r.get("broaden") for _q, r in w[:-1])],
                             ["quality 25%+", "quality 22%+", "quality 0–20%", "ilvl 80–82", "listed within 1 week"])
            self.assertIsNone(w[-1][1]["broaden"])

    def test_ladder_starts_under_the_quality(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            for q, want in ((27, [27, 25, 22, "band"]), (25, [25, 22, "band"]), (23, [23, 22, "band"]),
                            (22, [22, "band"]), (21, [21, "band"])):
                got_, _w = walked(G.parse_gear(base(text, quality=q)))
                seen = []
                for _lv, qual, _s, _a in got_:
                    v = "band" if qual == {"max": 20} else qual["min"]
                    if v not in seen:
                        seen.append(v)
                self.assertEqual(seen, want, (q, text[:30]))

    def test_exceptional_sockets_low_quality(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):   # exceptional by sockets only
            got_, _w = walked(G.parse_gear(base(text, quality=10)))
            e, w, s2 = {"min": 81, "max": 81}, {"min": 80, "max": 82}, {"min": 2}
            self.assertEqual(got_, [(e, {"min": 10}, s2, "3days"), (w, {"min": 10}, s2, "3days"),
                                    (w, {"min": 10}, s2, "1week")])

    def test_usual_sockets_not_searched(self):
        for text, lv in ((self.items["normal_body_armour_base"], 79), (MAGIC_ROBE, 79)):
            it = G.parse_gear(text)                      # 20% quality, 2 sockets (not exceptional for a body)
            self.assertFalse(G.is_exceptional(it["gclass"], it["quality"], it["sockets"], it["name"]))
            self.assertIsNone(it["search"]["sockets_min"])
            self.assertIsNone(default_opts(it)["sockets"])             # (the card's Sockets box: unticked)
            e, w = {"min": lv, "max": lv}, {"min": lv - 1, "max": lv + 1}
            got_, _w = walked(it)
            self.assertEqual(got_, [(e, {"min": 20}, None, "3days"), (w, {"min": 20}, None, "3days"),
                                    (w, {"min": 20}, None, "1week")])
            one = G.parse_gear(base(text, sockets=1))                  # owner: not exceptional - not searched
            self.assertTrue(all(s is None for _l, _q, s, _a in walked(one)[0]))

    def test_magic_sockets_rule(self):
        it = G.parse_gear(MAGIC_CROWN)                                 # 2 sockets on a helmet: exceptional
        self.assertEqual(it["search"]["sockets_min"], 2)
        self.assertEqual(default_opts(it)["sockets"], {"min": 2})
        robe3 = G.parse_gear(base(MAGIC_ROBE, sockets=3))              # 3 on a body armour: exceptional
        self.assertEqual(robe3["search"]["sockets_min"], 3)
        cor = G.parse_gear(MAGIC_ROBE.replace("Item Level: 79", "Item Level: 79\n--------\nCorrupted"))
        self.assertTrue(cor["corrupted"])                              # (a corrupted base keeps what it has)
        self.assertEqual(cor["search"]["sockets_min"], 2)
        self.assertFalse(G.is_exceptional(cor["gclass"], cor["quality"], cor["sockets"], cor["name"]))

    def test_magic_mods_on_every_step(self):
        it = G.parse_gear(MAGIC_CROWN)
        w = walk(it)
        stats = [json.dumps(qs[0].get("query", qs[0]).get("stats"), sort_keys=True) for qs, _r in w]
        self.assertEqual(len(w), 6)
        self.assertEqual(len(set(stats)), 1)                           # its own mods: searched as before, each step
        self.assertIn("stat", stats[0])

    def test_stops_offering_with_enough(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            qs, rec, _h = priced(G.parse_gear(text), at=0)             # enough at once: nothing to broaden
            self.assertEqual(len(qs), 1)
            self.assertIsNone(broaden_offer(rec))
            self.assertEqual(search_word(rec), "Search again")
            self.assertIsNone(widened_line(rec))
            got_, w = walked(G.parse_gear(text), at="each", n=2)       # always too few: every step offered
            self.assertEqual(got_, HELMET_LADDER)
            got_, w = walked(G.parse_gear(text), at=2)                 # found at the second click: no more offered
            self.assertEqual(len(w), 3)
            rec = w[-1][1]
            self.assertEqual(rec["est"], 1.0)
            self.assertIsNone(broaden_offer(rec))
            self.assertEqual(rec["widened"], "quality 22%+")
            self.assertEqual(widened_line(rec), "↔ Widened: quality 22%+")
            self.assertEqual(rec["opts"]["quality"], {"min": 22})      # the card's boxes: what was searched

    def test_card_line_each_click(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            _g, w = walked(G.parse_gear(text), at="each", n=2)          # some listings, too few: the line shows
            self.assertEqual([widened_line(r) for _q, r in w], [
                None, "↔ Widened: quality 25%+", "↔ Widened: quality 22%+", "↔ Widened: quality 0–20%",
                "↔ Widened: quality 0–20%, ilvl 80–82", "↔ Widened: quality 0–20%, ilvl 80–82, listed within 1 week"])
            self.assertEqual([search_word(r) for _q, r in w], ["↔ Broaden Search"] * 5 + ["Search again"])

    def test_search_again_repeats_it(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            it = G.parse_gear(text)
            _g, w = walked(it, at="each", n=2)
            qs, rec = w[-1]
            self.assertEqual(rec["widened"], "quality 0–20%, ilvl 80–82, listed within 1 week")
            _q, _r, hours = priced(it, at=0, opts=rec["opts"])
            self.assertEqual(hours[-1], 168)                           # (its listings: up to a week old)
            self.assertIsNone(broaden_offer(rec))
            o = press(rec)                                             # Search again: no step left
            self.assertEqual((o["quality"], o["ilvl"], o["age"]), ({"max": 20}, {"min": 80, "max": 82}, "1 week"))
            cur = {**default_opts(it), **o}                            # the boxes the card shows
            self.assertEqual((cur["quality"], cur["ilvl"], cur["sockets"]),
                             ({"max": 20}, {"min": 80, "max": 82}, {"min": 2}))
            qs2, rec2, _h = priced(it, at=0, opts=o)
            self.assertEqual(steps(qs2), [({"min": 80, "max": 82}, {"max": 20}, {"min": 2}, "1week")])
            self.assertEqual(widened_line(rec2), "↔ Widened: quality 0–20%, ilvl 80–82, listed within 1 week")
            qs4, rec4, _h = priced(it, opts=o)                         # nothing found: no wider (never ilvl +/-2,
            self.assertEqual(len(qs4), 1)                              # never older than a week)
            self.assertTrue(rec4["nomatch"])
            self.assertIsNone(broaden_offer(rec4))
            mid = w[1][1]                                              # mid-ladder (quality 25%+): Search again
            qs5, rec5, _h = priced(it, at=0, n=2, opts=mid["opts"])         # repeats it and offers the same next
            self.assertEqual(steps(qs5), [HELMET_LADDER[1]])
            self.assertEqual(widened_line(rec5), "↔ Widened: quality 25%+")
            self.assertEqual(broaden_offer(rec5)["next"], "quality 22%+")

    def test_hand_edit_resets(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            it = G.parse_gear(text)
            _g, w = walked(it, at="each", n=2)
            rec = w[2][1]                                              # broadened twice (quality 22%+)
            self.assertTrue(broaden_offer(rec))
            rec["changed"] = True                                      # a box changed by hand: Search again
            self.assertIsNone(broaden_offer(rec))
            self.assertEqual(search_word(rec), "Search  •  filters changed")
            self.assertEqual(press(rec)["quality"], {"min": 22})       # (the boxes as typed - nothing added)
            typed = dict(rec["opts"], ilvl={"min": 70})
            qs3, rec3, _h = priced(it, at=0, n=2, opts=typed)
            self.assertEqual(len(qs3), 1)
            self.assertIsNone(widened_line(rec3))                      # no Widened line, no Broaden Search
            self.assertIsNone(broaden_offer(rec3))
            self.assertEqual(search_word(rec3), "Search again")
            first = priced(it, at=0, n=2, opts={"quality": {"min": 27}})[1]   # typed before any broadening
            self.assertIsNone(broaden_offer(first))

    def test_week_setting_no_week_step(self):
        from soe2.config import SETTINGS
        old = SETTINGS["age"]
        SETTINGS["age"] = "1 week"
        try:
            for text in (self.items["normal_body_armour_base"], MAGIC_ROBE):
                got_, _w = walked(G.parse_gear(text))
                self.assertEqual([a for _l, _q, _s, a in got_], ["1week", "1week"])   # exact, ilvl +/-1 - no more
        finally:
            SETTINGS["age"] = old

    def test_other_routes_unchanged(self):
        for name in ("rare_ring", "unique_headhunter", "magic_waystone", "magic_jewel_emerald"):
            route, it = GOLD.route_of(self.items[name])
            self.assertFalse(G.widens(it), name)
            self.assertEqual(G.base_widen(it, default_opts(it), 48), [], name)
            self.assertEqual(G.widen_state(it, None, default_opts(it), 48, True), ("", None), name)
            if not it.get("gear"):
                continue
            qs, rec, _h = priced(it)
            self.assertFalse(rec.get("widened"), name)
            b = rec.get("broaden")                       # 3.0.6 (owner): any other item - values looser, then a mod out
            self.assertTrue(b is None or b.get("loosen") == 10 or
                            (b.get("drop") and str(b["next"]).startswith("without ")), name)
            self.assertNotIn("widened", rec["label"], name)
            self.assertNotIn("1week", json.dumps(qs), name)

    def test_magic_bases_on_the_base_route_widen(self):
        for name in ("magic_charm_quality", "magic_flask", "magic_ring_base", "rare_spear_exceptional_base"):
            route, it = GOLD.route_of(self.items[name])
            self.assertTrue(it["search"]["base_exact"], name)
            self.assertTrue(G.widens(it), name)
            qs, rec, _h = priced(it)
            self.assertEqual(len(qs), 1, name)
            self.assertTrue(broaden_offer(rec), name)

    def test_each_click_goes_through_the_rate_limiter(self):
        for text in (self.items["normal_helmet_exceptional"], MAGIC_CROWN):
            it = G.parse_gear(text)
            took, posts = [], []

            class R:
                status_code, headers, text, elapsed = 200, {}, "", None

                def json(self):
                    return {"total": 0, "result": [], "id": None}

            def request(method, url, **kw):
                posts.append(url)
                return R()
            opts, clicks = None, 0
            T._search_cache.clear()
            with mock.patch.object(EN, "MARKET", GOLD._Market()), mock.patch.object(N.requests, "request", request), \
                    mock.patch.object(N.LIMITER, "acquire", lambda cls: took.append(cls)), \
                    mock.patch.object(N.LIMITER, "update", lambda cls, h: None):
                while True:
                    rec = {"id": 1, "item": it, "src": "pc", "ov": {}, "opts": opts, "raw": ""}
                    eng = EN.Engine({1: rec}, queue.Queue())
                    eng.table = GOLD.TABLE
                    before = len(posts)
                    eng.resolve_rec(rec)
                    eng.price_rec(rec, lambda: None)
                    self.assertEqual(len(posts) - before, 1)           # one search a check / click (no any-age retry)
                    if not broaden_offer(rec):
                        break
                    opts, clicks = press(rec), clicks + 1
            T._search_cache.clear()
            self.assertEqual(clicks, 5)
            self.assertEqual(len(took), len(posts))                    # each one waited its turn


if __name__ == "__main__":
    unittest.main()
