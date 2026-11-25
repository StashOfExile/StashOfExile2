"""3.3.0 owner fixes: every league in Game Search, jewel pictures, the Diamond group, pictures fit their square."""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LeagueRows(unittest.TestCase):
    def test_every_league_with_its_version(self):
        with open(os.path.join(ROOT, "gamedb.json"), encoding="utf-8") as f:
            rows = json.load(f)["rows"]
        got = {r["name"]: r["text"] for r in rows if r["group"] == "Leagues"}
        for name, ver in (("Dawn of the Hunt", "0.2.0"), ("Rise of the Abyssal", "0.3.0"),
                          ("Fate of the Vaal", "0.4.0"), ("Runes of Aldur", "0.5.0"), ("Forbidden Rites", "0.5.5")):
            self.assertIn(name, got)
            self.assertIn(ver, got[name])


class JewelArt(unittest.TestCase):
    def test_eight_jewels_have_pictures(self):
        from soe2.pricecheck_page import JEWEL_ART
        self.assertEqual(len(JEWEL_ART), 8)
        self.assertTrue(all(u.startswith("https://web.poecdn.com/") for u in JEWEL_ART.values()))

    def test_diamond_rolls_every_regular_jewel_mod(self):
        from soe2 import ratemods as RM
        es = RM.entries("jewel")
        dia = [e for e in es if RM.on_diamond(e)]
        self.assertTrue(dia)
        self.assertTrue(all(any(t in ("Ruby", "Emerald", "Sapphire") for t in e["info"]["tags"]) for e in dia))
        self.assertLess(len(dia), len(es))           # the Time-Lost only ones are not on a Diamond


class PictureFits(unittest.TestCase):
    def test_tall_picture_fits_the_square(self):
        src = open(os.path.join(ROOT, "soe2", "pricecheck_page.py"), encoding="utf-8").read()
        self.assertIn("k = px / max(1, im.width, im.height)", src)


if __name__ == "__main__":
    unittest.main()


class ModLabGroups(unittest.TestCase):
    def test_waystone_tiers_in_order(self):
        from soe2 import ratemods as RM
        self.assertEqual(RM.waystone_group(["T1-5", "T11-15", "T16", "T6-10"]), "All waystones")
        self.assertEqual(RM.waystone_group(["T16", "T11-15"]), "Tier 11-16")
        self.assertEqual(RM.waystone_group(["Any"]), "All waystones")

    def test_relic_sizes_in_words(self):
        from soe2 import ratemods as RM
        self.assertEqual(RM.category("relic", ["Large", "Medium"]), "Large and Medium Relics")
        self.assertEqual(RM.category("relic", ["Small"]), "Small Relics")

    def test_a_learned_base_is_not_a_unique(self):
        from soe2.ratemods_page import _is_base
        self.assertTrue(_is_base("Utility Belt"))
        self.assertTrue(_is_base("Ritual Tablet"))
        self.assertFalse(_is_base("Headhunter"))


class RollsOnChips(unittest.TestCase):
    def test_waystone_chip_is_one_in_order(self):
        from soe2 import ratemods as RM
        self.assertEqual(RM.rolls_on("waystone", "k", {"tags": ["T1-5", "T11-15", "T16", "T6-10"]}), ["All tiers"])
        self.assertEqual(RM.rolls_on("waystone", "k", {"tags": ["T16", "T11-15"]}), ["Tier 11-16"])


class BaseGroups(unittest.TestCase):
    def test_groups_are_bases_never_mixes(self):
        from soe2 import ratemods as RM
        for s in ("jewel", "tablet", "relic"):
            for e in RM.entries(s):
                self.assertTrue(e["cats"])
                self.assertTrue(all(" / " not in c for c in e["cats"]))
                self.assertTrue(set(e["cats"]) <= set(RM.base_order(s)))

    def test_waystones_have_one_pool(self):
        from soe2 import ratemods as RM
        self.assertTrue(all(not e["cats"] and not e["cat"] for e in RM.entries("waystone")))

    def test_unique_tablet_has_a_group(self):
        from soe2 import uniquedata as UD
        self.assertEqual(UD.group_of("Freedom of Faith"), "Tablets")
