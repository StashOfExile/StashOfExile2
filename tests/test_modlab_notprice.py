"""3.3.0 owner, Mod Lab: a unique's fixed line - no number, on every copy - leaves the list; Doesn't affect price takes any
mod out, with Undo; the uniques you've checked fold.

    DISPLAY=:99 python3.12 -m unittest tests.test_modlab_notprice          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-np-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import ratemods as RM          # noqa: E402
from soe2.config import SETTINGS         # noqa: E402

S = "unique:runeseeker's call"
MODS = [("u:a", "Only Runes can be Socketed in this item"), ("u:b", "# to maximum Runic Ward"),
        ("u:c", "Grants Skill: Level # The Stars Answer")]


class NotPrice(unittest.TestCase):
    def setUp(self):
        SETTINGS.pop("rm_not_price", None)
        self.p = mock.patch("soe2.config.save_json")
        self.p.start()

    def tearDown(self):
        self.p.stop()
        SETTINGS.pop("rm_not_price", None)

    def texts(self):
        return [t for _k, t in RM.queue(S, MODS)]

    def test_a_fixed_unique_line_never_shows(self):
        self.assertNotIn("Only Runes can be Socketed in this item", self.texts())
        self.assertEqual(len(self.texts()), 2)
        gear = [(k, t) for k, t in RM.queue("gear:ring", MODS)]
        self.assertEqual(len(gear), 3, "gear keeps every line: a rare's wording can be the one that matters")

    def test_marked_and_undone(self):
        RM.mark_not_price(["u:b"])
        self.assertEqual(self.texts(), ["Grants Skill: Level # The Stars Answer"])
        RM.mark_not_price(["u:b"], on=False)
        self.assertEqual(len(self.texts()), 2)


class Fold(unittest.TestCase):
    def test_uniques_fold_and_remember(self):
        from soe2.ratemods_page import RateModsPage
        h = RateModsPage.__new__(RateModsPage)
        h.rm_setcv = mock.Mock()
        SETTINGS.pop("rm_uniq_folded", None)
        with mock.patch("soe2.config.save_json"):
            self.assertFalse(h.rm_uniq_folded())
            h.rm_uniq_flip()
            self.assertTrue(h.rm_uniq_folded())
            h.rm_uniq_flip()
        self.assertFalse(h.rm_uniq_folded())


if __name__ == "__main__":
    unittest.main()
