"""3.3.0 owner: today's game data is frozen in snapshots/, so a patch can be shown before and after."""
import gzip
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from soe2 import gamecards, gamesnap  # noqa: E402
import build_snapshot as BS  # noqa: E402

ANVIL = """
The Anvil
Bloodstone Amulet
Variant: Pre 0.2.0
Variant: Pre 0.4.0
Variant: Current
Implicits: 1
+(30-40) to maximum Life
{variant:1}20% increased Block chance
{variant:2,3}25% increased Block chance
{variant:1,2}+(3-5)% to maximum Block chance
{variant:3}+(5-10)% to maximum Block chance
"""


class Builder(unittest.TestCase):
    def test_every_kept_version_of_a_unique(self):
        v = BS.unique_versions(ANVIL)
        self.assertEqual(list(v), ["Pre 0.2.0", "Pre 0.4.0", "Current"])
        self.assertEqual(v["Pre 0.4.0"], ["+(30-40) to maximum Life", "25% increased Block chance",
                                          "+(3-5)% to maximum Block chance"])
        self.assertEqual(v["Current"][-1], "+(5-10)% to maximum Block chance")
        self.assertEqual(BS.unique_versions("Mageblood\\nUtility Belt\\nVariant: Legacy of Ruby\\n{variant:1}Legacy of Ruby"), {},
                         "choices are not versions")

    def test_the_shipped_snapshot(self):
        vs = gamesnap.versions(os.path.join(ROOT, "snapshots"))
        self.assertIn("0.5.5.10", vs)
        s = gamesnap.load("0.5.5.10", os.path.join(ROOT, "snapshots"))
        self.assertEqual(s["game_version"], "0.5.5.10")
        self.assertTrue(s["sources"]["repoe"] and s["sources"]["pob"], "which commits it came from")
        self.assertGreater(len(s["uniques"]), 400)
        self.assertGreater(sum(1 for g in s["gems"].values() if g["type"] == "support"), 500)
        self.assertGreater(len(s["mods"]), 3000)
        self.assertIn("versions", s["uniques"]["The Anvil"])


class Compare(unittest.TestCase):
    def setUp(self):
        gamesnap.reset()
        self.addCleanup(gamesnap.reset)

    def test_history_and_the_card_line(self):
        snap = {"uniques": {"The Anvil": {"explicit": [], "versions": BS.unique_versions(ANVIL)}}}
        self.assertEqual(gamesnap.history("The Anvil", snap), ("0.4.0", ["+(3-5)% to maximum Block chance"]))
        self.assertIsNone(gamesnap.history("Nothing", snap))

    def test_before_and_after_two_snapshots(self):
        old = {"uniques": {"A": {"implicit": ["+10 Life"], "explicit": ["5% x"]}, "Gone": {}},
               "gems": {"Hex": {"text": "old words", "first_level": ["1"], "last_level": ["9"]}, "Same": {"text": "t"}}}
        new = {"uniques": {"A": {"implicit": ["+10 Life"], "explicit": ["8% x"]}, "New": {}},
               "gems": {"Hex": {"text": "new words", "first_level": ["1"], "last_level": ["12"]}, "Same": {"text": "t"}}}
        d = gamesnap.compare(old, new)
        self.assertEqual(d["uniques"], {"A": {"added": ["8% x"], "removed": ["5% x"]}})
        self.assertEqual(d["gems"]["Hex"]["text"], {"before": "old words", "after": "new words"})
        self.assertEqual(d["gems"]["Hex"]["last_level"], {"added": ["12"], "removed": ["9"]})
        self.assertNotIn("first_level", d["gems"]["Hex"])
        self.assertNotIn("Same", d["gems"])
        self.assertEqual((d["new_uniques"], d["gone_uniques"]), (["New"], ["Gone"]))

    def test_versions_sort_by_number(self):
        with tempfile.TemporaryDirectory() as t:
            for v in ("0.5.5.10", "0.5.5.9", "1.0.0.1"):
                with gzip.open(os.path.join(t, f"poe2-{v}.json.gz"), "wt") as f:
                    json.dump({"game_version": v}, f)
            self.assertEqual(gamesnap.versions(t), ["0.5.5.9", "0.5.5.10", "1.0.0.1"])
            self.assertEqual(gamesnap.load(path=t)["game_version"], "1.0.0.1", "the newest by default")

    def test_a_unique_card_in_game_search(self):
        r = {"n": "The Anvil", "g": "Unique Items", "c": "Amulet", "k": "", "t": "Unique Amulet",
             "ul": ["+(30-40) to maximum Life"]}
        snap = {"uniques": {"The Anvil": {"explicit": [], "versions": BS.unique_versions(ANVIL)}}}
        orig = gamesnap.load
        gamesnap.load = lambda *a, **k: snap
        try:
            c = gamecards.card(r)
        finally:
            gamesnap.load = orig
        self.assertEqual(c["lines"], ["+(30-40) to maximum Life"])
        self.assertEqual(c["muted"], ["Before 0.4.0: +(3-5)% to maximum Block chance"])


if __name__ == "__main__":
    unittest.main()
