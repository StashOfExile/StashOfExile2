"""Exchange Rates › Exchange Helper: Compare a currency replaces Check a flip. Pick one currency, see one of it in every
other currency, worked out from the poe.ninja divine prices the app already has; how it was worked out is one hover
away; no flip or profit wording is left.

    python3.12 -m unittest tests.test_compare_currency"""
import os
import re
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import exchange_page as X  # noqa: E402

TBL = {"divine": 1.0, "chaos": 0.0025, "exalted": 0.01, "perfect-exalted-orb": 0.52}
NAMES = {"divine": "Divine Orb", "chaos": "Chaos Orb", "exalted": "Exalted Orb",
         "perfect-exalted-orb": "Perfect Exalted Orb"}


class Rows(unittest.TestCase):
    def test_every_other_currency(self):
        rows = X.compare_rows("perfect-exalted-orb", TBL, NAMES, {"chaos": 9, "exalted": 5, "divine": 1})
        self.assertEqual([r[0] for r in rows], ["chaos", "exalted", "divine"], "most traded first, not itself")
        got = {r[0]: r[1] for r in rows}
        self.assertAlmostEqual(got["chaos"], 0.52 / 0.0025)
        self.assertAlmostEqual(got["exalted"], 52)
        self.assertAlmostEqual(got["divine"], 0.52)

    def test_how_it_was_worked_out(self):
        how = dict((r[0], r[2]) for r in X.compare_rows("perfect-exalted-orb", TBL, NAMES))["chaos"]
        self.assertIn("Perfect Exalted Orb is worth 0.52 div", how)
        self.assertIn("Chaos Orb is worth 0.0025 div", how)
        self.assertIn("0.52 ÷ 0.0025 = 208", how)
        self.assertIn("poe.ninja", how)

    def test_unknown_currency(self):
        self.assertEqual(X.compare_rows("mirror", TBL, NAMES), [])


class NoFlip(unittest.TestCase):
    def test_no_flip_wording(self):
        src = open(os.path.join(ROOT, "soe2", "exchange_page.py"), encoding="utf-8").read()
        self.assertIsNone(re.search(r"(?i)\\bflip|arbitrage|profit|gain", src))
        from soe2 import cxnames
        self.assertFalse(hasattr(cxnames, "flip"), "the flip sum is gone")


if __name__ == "__main__":
    unittest.main()
