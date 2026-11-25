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
