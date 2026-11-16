"""Price check, 3.0.4: a unique tablet (Freedom of Faith).

  * "Adds Ritual Altars to a Map" + "5 uses remaining" are one stat on the trade site ("... # use remaining"): one
    mod with that id, value = the uses, searched (when ticked) at least that many.
  * Freedom of Faith is priced by the exact tribute %: Min and Max both at the item's value (10% -> 10 to 10).

    python3.12 -m unittest tests.test_tablet_unique          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-tab-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import gear, mods, trade              # noqa: E402

TEXT = """Item Class: Tablet
Rarity: Unique
Freedom of Faith
Ritual Tablet
--------
Item Level: 81
--------
Adds Ritual Altars to a Map (implicit)
{n} uses remaining (implicit)
--------
Favours at Ritual Altars in Area costs {pct}% increased Tribute
Can Reroll Favours at Ritual Altars in your Maps twice as many times
--------
When darkness comes, we pray for light.
--------
Can be used in a personal Map Device to add modifiers to a Map.
"""


class FreedomOfFaith(unittest.TestCase):
    def setUp(self):
        self.old = dict(trade.TEXT2SID)
        trade.TEXT2SID.update({
            "adds ritual altars to a map # use remaining": "implicit.stat_3166002380",
            "favours at ritual altars in area costs #% increased tribute": "explicit.stat_1228222525",
            "can reroll favours at ritual altars in your maps twice as many times": "explicit.stat_2500154144"})
        self.addCleanup(lambda: (trade.TEXT2SID.clear(), trade.TEXT2SID.update(self.old)))

    def item(self, n=5, pct=10):
        it = gear.parse_gear(TEXT.format(n=n, pct=pct))
        self.assertIsNotNone(it)
        return it

    def test_uses_are_one_stat(self):
        it = self.item(n=5)
        imp = [m for m in it["mods"] if m["kind"] == "Implicit"]
        self.assertEqual(len(imp), 1)
        self.assertEqual(imp[0]["sid"], "implicit.stat_3166002380")
        self.assertEqual(mods.vfilter(imp[0]), {"min": 5.0})
        self.assertFalse(any("not found" in (m.get("note") or "") for m in it["mods"]))

    def test_one_use(self):
        imp = [m for m in self.item(n=1)["mods"] if m["kind"] == "Implicit"]
        self.assertEqual(imp[0]["sid"], "implicit.stat_3166002380")

    def test_tribute_exact(self):
        for pct in (10, 13):
            m = next(m for m in self.item(pct=pct)["mods"] if "Tribute" in m["text"])
            self.assertTrue(m.get("exact"))
            self.assertEqual(m.get("auto"), "high")
            self.assertEqual(mods.vfilter(m), {"min": float(pct), "max": float(pct)})

    def test_other_uniques_unchanged(self):
        it = gear.parse_gear(TEXT.format(n=5, pct=10).replace("Freedom of Faith", "Some Other Tablet"))
        m = next(m for m in it["mods"] if "Tribute" in m["text"])
        self.assertFalse(m.get("exact"))


if __name__ == "__main__":
    unittest.main()
