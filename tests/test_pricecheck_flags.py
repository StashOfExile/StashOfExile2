"""Price check flags and the item card's extra filters (owner decisions A, B, C):
  A  a flagged item (corrupted, mirrored, fractured ...) is searched with that same flag; its toggle switches it off
  B  the Corrupted / Crafted toggles change the search; the item's own default stays (the golden test)
  C  the trade site's other filters (attacks per second, gem level, area level ...) are searched only when ticked
  Round 18: the flags live in Miscellaneous only (Any / Yes / No); an item's own flag starts at Yes - no flag rows
  in Properties, no "or not" wording, on the app's card and the card over the game

    python3.12 -m unittest tests.test_pricecheck_flags          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-flags-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from soe2 import gamedata as GD, gear as G, trade as T     # noqa: E402
from soe2.searchopts_page import default_opts, item_props   # noqa: E402
from test_pricecheck_golden import load_items               # noqa: E402

ITEMS = load_items()


def misc(q):
    return (q.get("filters", {}).get("misc_filters") or {}).get("filters") or {}


class Flags(unittest.TestCase):
    def test_copy_flags(self):
        for name, want in (("rare_ring_mirrored", {"mirrored"}), ("rare_amulet_fractured", {"fractured"}),
                           ("rare_belt_desecrated", {"desecrated"}), ("rare_ring_sanctified", {"sanctified"}),
                           ("rare_boots_twice_corrupted", {"corrupted", "twice_corrupted"}),
                           ("rare_ring_unrevealed_header", {"desecrated", "unrevealed"}),
                           ("unique_kaoms_heart_unidentified", {"unidentified"}), ("rare_ring", set()),
                           ("rare_ring_mutated_header", set())):           # (Mutated on a rare: not a Cultivated unique)
            self.assertEqual(GD.copy_flags(ITEMS[name]), want, name)
        self.assertEqual(GD.copy_flags("Rarity: Unique\n{ Mutated Prefix Modifier }\n+5 to Strength"), {"cultivated"})
        self.assertEqual(GD.copy_flags("Rarity: Rare\n+5 to Strength (crafted)"), {"crafted"})

    def query(self, name, opts=None):
        it = G.parse_gear(ITEMS[name])
        with mock.patch.object(T, "current_opts", lambda: opts):
            return it, G.build_query(it, [], [], 0, {})

    def test_flag_searched_and_toggle_off(self):
        it, q = self.query("rare_ring_mirrored")
        self.assertEqual(misc(q)["mirrored"], {"option": "true"})
        self.assertEqual(default_opts(it)["mirrored"], "yes")
        _it, q = self.query("rare_ring_mirrored", {"mirrored": "any"})
        self.assertNotIn("mirrored", misc(q))
        _it, q = self.query("unique_kaoms_heart_unidentified")
        self.assertEqual(misc(q)["identified"], {"option": "false"})

    def test_corrupted_and_crafted_toggles(self):
        _it, q = self.query("rare_ring")
        self.assertEqual(misc(q)["corrupted"], {"option": "false"})          # today's default: uncorrupted only
        self.assertNotIn("crafted", misc(q))
        _it, q = self.query("rare_ring", {"corrupted": "any", "crafted": "no"})
        self.assertNotIn("corrupted", misc(q))
        self.assertEqual(misc(q)["crafted"], {"option": "false"})
        _it, q = self.query("rare_ring", {"foreseeing": "yes", "cultivated": "no", "unrevealed": "yes"})
        self.assertEqual((misc(q)["foreseeing"], misc(q)["mutated"], misc(q)["veiled"]),
                         ({"option": "true"}, {"option": "false"}, {"option": "true"}))

    def test_jewel_flags(self):
        sent = []
        with mock.patch.object(T, "call", lambda m, u, json=None: sent.append(json["query"]) or {"result": []}), \
                mock.patch.object(T, "current_opts", lambda: None):
            T.search_ids("Standard", "Ruby", [], None, {"corrupted", "fractured"})
            T.search_ids("Standard", "Ruby", [], None, None)
        self.assertEqual(misc(sent[0]), {"corrupted": {"option": "true"}, "fractured_item": {"option": "true"}})
        self.assertEqual(misc(sent[1]), {})                                  # unflagged: either, as before

    def test_flags_in_miscellaneous_only(self):
        from soe2.app import App
        for name, text in ITEMS.items():
            it = G.parse_gear(text)
            if it is None or it.get("rarity") == "Currency":
                continue
            keys = [k for k, _l in App._card_misc_keys(it)]
            self.assertIn("corrupted", keys, name)                         # every route
            self.assertIn("crafted", keys, name)
            own = set(it.get("flags") or ()) | ({"corrupted"} if it.get("corrupted") else set())
            self.assertEqual(set(keys[:len(own)]), own, name)              # its own flags first ...
            d = default_opts(it)
            for k in own:
                self.assertEqual(d[k], "yes", f"{name}: {k}")              # ... at Yes
        it = G.parse_gear(ITEMS["rare_ring"])
        self.assertIsNone(default_opts(it).get("crafted"))                 # Crafted: Any
        labels = dict(App._card_misc_keys(G.parse_gear(ITEMS["rare_amulet_fractured"])))
        self.assertEqual(labels["fractured"], "Fractured")                  # the word only - no icons (owner)
        from soe2.pricecheck_page import FLAG_MARKS
        marks = {m for _k, m, _w in FLAG_MARKS}
        for name, text in ITEMS.items():
            it = G.parse_gear(text)
            if it is None or it.get("rarity") == "Currency":
                continue
            for _k, lab in App._card_misc_keys(it):
                self.assertFalse(any(m in lab for m in marks), f"{name}: {lab}")
        for f in ("soe2/app.py", "soe2/pcpop.py"):
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotIn("or not\"", src, f)
            self.assertNotIn("listings only\"", src, f)
            self.assertNotIn("_card_flag_row", src, f)

    def test_extra_numbers(self):
        p = item_props("Physical Damage: 10-20\nAttacks per Second: 1.50\nCritical Hit Chance: 5.00%\n"
                       "Reload Time: 0.80\nBlock chance: 25%\nSpirit: 100\nStack Size: 1,234/5,000")
        self.assertEqual(p, {"aps": 1.5, "crit": 5.0, "reload": 0.8, "block": 25, "spirit": 100, "stack": 1234,
                             "dps": 22})
        it, q = self.query("rare_bow_dps")
        self.assertNotIn("aps", (q["filters"].get("equipment_filters") or {}).get("filters", {}))   # off until ticked
        _it, q = self.query("rare_bow_dps", {"aps": {"min": 1.2}, "reload": {"max": 0.9}})
        eq = q["filters"]["equipment_filters"]["filters"]
        self.assertEqual((eq["aps"], eq["reload_time"]), ({"min": 1.2}, {"max": 0.9}))
        gem = G.parse_gear(ITEMS["skill_gem"])
        self.assertEqual(default_opts(gem)["gem_level"], {"min": gem["search"]["gem"]["level"]})

    def test_site_filter_list(self):
        T.set_trade_filters({"result": [{"id": "misc_filters", "filters": [{"id": "foreseeing", "text": "Foreseeing"}]}]})
        try:
            self.assertTrue(T.site_has("misc_filters", "foreseeing"))
            self.assertFalse(T.site_has("misc_filters", "gone"))
        finally:
            T.FILTERS.clear()
        self.assertTrue(T.site_has("misc_filters", "gone"))                 # not loaded: every filter offered


if __name__ == "__main__":
    unittest.main()
