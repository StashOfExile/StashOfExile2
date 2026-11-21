import json, os, unittest
from soe2 import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRYSTAL = "#% chance to gain an additional Crystal from Vaal Beacons in Map"


class TabletCrystalHigh(unittest.TestCase):
    def test_crystal_mod_ships_as_high(self):
        d = json.load(open(os.path.join(ROOT, "default_rules.json"), encoding="utf-8"))
        self.assertIn(CRYSTAL, d["tablet"]["high"])
        self.assertNotIn(CRYSTAL, d["tablet"]["ignore"])

    def test_bundled_version_bumped(self):
        self.assertGreaterEqual(config.BUNDLED_DATA["default_rules.json"], 5)


if __name__ == "__main__":
    unittest.main()
