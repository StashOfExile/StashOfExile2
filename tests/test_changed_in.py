"""Game Search's Changed in <patch>: built from the two newest snapshots."""
import gzip
import json
import os
import shutil
import tempfile
import unittest

from soe2 import gamecards, gamesnap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "snapshots", "poe2-0.5.5.10.json.gz")


class ChangedIn(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        shutil.copy(SNAP, self.d)
        with gzip.open(SNAP, "rt", encoding="utf-8") as f:
            s = json.load(f)
        self.name = next(iter(s["uniques"]))
        u = s["uniques"][self.name]
        u["explicit"] = ["+(50-70) to maximum Life"] + list(u.get("explicit") or [])[1:] + ["10% increased Movement Speed"]
        s["uniques"]["Brand New Unique"] = {"group": "Belts", "explicit": ["+1 to everything"]}
        gem = next(iter(s["gems"]))
        s["gems"][gem]["text"] = "changed text"
        s["snapshot"] = s["game_version"] = "1.0.0.1"
        with gzip.open(os.path.join(self.d, "poe2-1.0.0.1.json.gz"), "wt", encoding="utf-8") as f:
            json.dump(s, f)
        gamesnap.reset()

    def tearDown(self):
        shutil.rmtree(self.d)
        gamesnap.reset()

    def test_rows_and_cards(self):
        rows = gamesnap.change_rows(self.d)
        self.assertTrue(rows)
        self.assertTrue(all(r["g"] == "Changed in 1.0" for r in rows))
        by = {r["n"]: r for r in rows}
        self.assertEqual(by["Brand New Unique"]["chg_status"], "New")
        c = gamecards.card(by[self.name])
        self.assertTrue(any(x.startswith(("~ Changed:", "+ New:", "− Removed:")) for x in c["lines"]))
        self.assertIn("Changed in 1.0.0.1", c["kind"])

    def test_one_snapshot_means_no_rows(self):
        os.remove(os.path.join(self.d, "poe2-1.0.0.1.json.gz"))
        gamesnap.reset()
        self.assertEqual(gamesnap.change_rows(self.d), [])

    def test_a_number_change_is_one_line(self):
        got = gamesnap.pair(["+(50-70) to maximum Life"], ["+(40-60) to maximum Life"])
        self.assertEqual(got, [("changed", "+(50-70) to maximum Life", "+(40-60) to maximum Life")])


if __name__ == "__main__":
    unittest.main()
