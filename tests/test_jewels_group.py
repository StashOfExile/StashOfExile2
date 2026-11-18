"""3.0.6 (owner): jewels are their own Game Search category, with no picture."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import gamesearch as G, gamecards as C


class Jewels(unittest.TestCase):
    def test_own_category_after_rings_and_belts(self):
        d = G.load()
        rows = {r["n"]: r for r in d["rows"] if r["c"] == "Jewel"}
        self.assertEqual(rows["Ruby"]["g"], "Jewels")
        self.assertEqual(rows["Time-Lost Diamond"]["g"], "Jewels")
        self.assertEqual(d["order"].index("Jewels"), d["order"].index("Jewellery & Belts") + 1)  # game text
        self.assertNotIn("Jewel", {r["c"] for r in d["rows"] if r["g"] == "Jewellery & Belts"})  # game text

    def test_card_words(self):
        d = {r["n"]: r for r in G.load()["rows"]}
        self.assertEqual(C.card(d["Diamond"])["kind"], "Jewel · Strength/Dexterity/Intelligence")
        self.assertEqual(C.card(d["Time-Lost Ruby"])["kind"], "Radius Jewel · Strength")
        self.assertEqual(C.card(d["Time-Lost Ruby"])["chips"], [])


if __name__ == "__main__":
    unittest.main()
