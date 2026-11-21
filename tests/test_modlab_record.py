"""3.0.6 (owner: Mod Lab): price-check listings kept whole for the owner's Mod Lab, from what the fetch already
returned - only with modlab_record on, no seller, the listing id hashed."""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from soe2 import config, market, trade


class ModLabRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_p = market.P
        market.P = lambda name: os.path.join(self.tmp, name)
        self.m = market.Market()
        self.old_flag = config.SETTINGS.get("modlab_record")
        self.old_rate = market.RATES.to_div
        market.RATES.to_div = lambda a, c, league=None: float(a)
        trade.RAW_LISTINGS["abc"] = {"id": "abc", "listing": {"price": {"amount": 60, "currency": "divine"},
                                                                 "account": {"name": "Someone#1234"}},
                                     "item": {"baseType": "Ruby Ring", "name": "Doom Loop", "rarity": "Rare",
                                              "ilvl": 82, "corrupted": True,
                                              "explicitMods": ["+95 to maximum Life", "12% increased Cast Speed"],
                                              "implicitMods": ["+25% to Fire Resistance"]}}

    def tearDown(self):
        market.P = self.old_p
        market.RATES.to_div = self.old_rate
        trade.RAW_LISTINGS.pop("abc", None)
        if self.old_flag is None:
            config.SETTINGS.pop("modlab_record", None)
        else:
            config.SETTINGS["modlab_record"] = self.old_flag
        try:
            self.m.db.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_off_by_default(self):
        config.SETTINGS.pop("modlab_record", None)
        self.assertEqual(self.m.lab([{"id": "abc"}]), 0)

    def test_switch_file(self):
        config.SETTINGS.pop("modlab_record", None)
        open(os.path.join(self.tmp, "modlab.on"), "w").close()
        self.assertEqual(self.m.lab([{"id": "abc"}]), 1)

    def test_on_keeps_the_whole_item_without_the_seller(self):
        config.SETTINGS["modlab_record"] = True
        self.assertEqual(self.m.lab([{"id": "abc"}]), 1)
        row = self.m.db.execute("SELECT id, base, rarity, ilvl, flags, mods, price_div FROM lab").fetchone()
        self.assertNotEqual(row[0], "abc")
        self.assertEqual(row[1:4], ("Ruby Ring", "Rare", 82))
        self.assertIn("corrupted", json.loads(row[4]))
        kinds = [m[0] for m in json.loads(row[5])]
        self.assertIn("implicit", kinds)
        self.assertIn("explicit", kinds)
        self.assertEqual(row[6], 60.0)
        dump = json.dumps(self.m.db.execute("SELECT * FROM lab").fetchall())
        self.assertNotIn("Someone", dump)


if __name__ == "__main__":
    unittest.main()
