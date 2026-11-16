"""Wealth, 3.0.4: What moved it (each item's 7-day price, in divines) and no prices typed by hand.

  * poe.ninja's sparkline is for the pair an item trades most against; the rate is turned the right way round by
    checking it against the price, and the pair's own change in divines is added on.
  * The trade site's exchange: "too few offers" is kept (bulk_prices.json), so a restart doesn't keep saying
    "asking…" and doesn't ask again at once.
  * Wealth has no typed prices: wealth_rows takes no overrides.

    python3.12 -m unittest tests.test_wealth_trend          (or tests/runall.sh)"""
import inspect
import os
import sys
import tempfile
import time
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-trend-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import bulk, wealth as W                 # noqa: E402
from soe2.config import SETTINGS                  # noqa: E402


def item(name, frame=5):
    return {"frame": frame, "type": name, "base": name, "name": "", "qty": 1, "lid": 1, "corrupted": False}


def prices(lines, spark, primary="divine", uniques=None):
    p = W.WealthPrices.__new__(W.WealthPrices)
    p.league, p.src, p.ts, p.etags, p.errors = "", "", time.time(), {}, []
    p.parts = {"Currency": {"primary": primary, "names": {}, "lines": lines, "images": {}, "spark": spark}}
    if uniques:
        p.parts["UniqueJewels"] = uniques
    p._index()
    return p


class Spark(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(W._spark({"totalChange": -6.2, "data": [0, -1, None, -6.2]}), (-6.2, [0.0, -1.0, -1.0, -6.2]))
        self.assertEqual(W._spark({"totalChange": 3, "data": []}), (3.0, [0.0, 3.0]))
        self.assertIsNone(W._spark(None))
        self.assertIsNone(W._spark({"data": "x"}))

    def test_combine(self):
        out = W._combine([0, 10], [0, 10])          # +10% in a pair that rose 10%: +21% in divines
        self.assertAlmostEqual(out[-1], 21.0)
        self.assertEqual(len(W._combine([0, 1, 2, 3], [0, 5])), 2)


class Trend(unittest.TestCase):
    def setUp(self):
        SETTINGS["league"] = ""

    def test_direct_pair_divine(self):
        # Exalted priced 0.0025 div; rate 0.0025 divine per exalted (same way as the price); -6% over the week
        p = prices([["divine", "Divine Orb", 1.0, 1], ["exalted", "Exalted Orb", 0.0025, 1]],
                   {"exalted": [-6.0, [0, -2, -6.0], "divine", 0.0025]})
        pct, pts = p.trend(item("Exalted Orb"))
        self.assertAlmostEqual(pct, -6.0)

    def test_inverse_rate(self):
        # rate 400 exalted per divine: the line is the rate, so +5% in it is the price going down
        p = prices([["divine", "Divine Orb", 1.0, 1], ["exalted", "Exalted Orb", 0.0025, 1]],
                   {"exalted": [5.0, [0, 5.0], "divine", 400.0]})
        pct, _pts = p.trend(item("Exalted Orb"))
        self.assertAlmostEqual(pct, 100 / 1.05 - 100, places=4)

    def test_pair_not_divine(self):
        # Chaos trades most against Exalted (+10% there); Exalted fell 10% in divines: about -1% in divines
        p = prices([["divine", "Divine Orb", 1.0, 1], ["exalted", "Exalted Orb", 0.0025, 1],
                    ["chaos", "Chaos Orb", 0.0075, 1]],
                   {"exalted": [-10.0, [0, -10.0], "divine", 0.0025], "chaos": [10.0, [0, 10.0], "exalted", 3.0]})
        pct, _pts = p.trend(item("Chaos Orb"))
        self.assertAlmostEqual(pct, (1.1 * 0.9 - 1) * 100)

    def test_unknown_and_divine(self):
        p = prices([["divine", "Divine Orb", 1.0, 1], ["exalted", "Exalted Orb", 0.0025, 1]], {})
        self.assertIsNone(p.trend(item("Exalted Orb")))
        self.assertEqual(p.trend(item("Divine Orb"))[0], 0.0)

    def test_loop_is_unknown(self):
        p = prices([["divine", "Divine Orb", 1.0, 1], ["a", "A", 1.0, 1], ["b", "B", 1.0, 1]],
                   {"a": [1.0, [0, 1.0], "b", 1.0], "b": [1.0, [0, 1.0], "a", 1.0]})
        self.assertIsNone(p.trend(item("A")))

    def test_unique(self):
        u = {"lines": [["Megalomaniac", "Diamond", 2.0, 30, False]], "spark": {"megalomaniac": [-20.0, [0, -20.0], 30]}}
        p = prices([["divine", "Divine Orb", 1.0, 1]], {}, uniques=u)
        it = item("Diamond", frame=3)
        it["name"] = "Megalomaniac"
        self.assertAlmostEqual(p.trend(it)[0], -20.0)

    def test_bad_shape_never_breaks_prices(self):
        p = prices([["divine", "Divine Orb", 1.0, 1], ["exalted", "Exalted Orb", 0.0025, 1]],
                   {"exalted": ["x", None, None, None]})
        self.assertAlmostEqual(p.value(item("Exalted Orb"))[0], 0.0025)


class NoTypedPrices(unittest.TestCase):
    def test_rows_take_no_overrides(self):
        self.assertEqual(list(inspect.signature(W.wealth_rows).parameters), ["items", "prices"])
        self.assertFalse(hasattr(W, "wealth_key"))
        with open(os.path.join(ROOT, "soe2", "wealth_page.py"), encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("Set my own price", page)
        self.assertNotIn('"set price"', page)
        self.assertIn("No price found", page)


class ExchangeMiss(unittest.TestCase):
    def test_miss_is_kept(self):
        calls = []
        old = bulk.search
        bulk.search = lambda league, xid, have, call_=None: calls.append(have) or []
        self.addCleanup(setattr, bulk, "search", old)
        self.assertIsNone(bulk.price("L", "the-runefathers-alloy", lambda a, c: a))
        self.assertTrue(bulk.missed("L", "the-runefathers-alloy"))
        self.assertIsNone(bulk.cached("L", "the-runefathers-alloy"))
        n = len(calls)
        self.assertIsNone(bulk.price("L", "the-runefathers-alloy", lambda a, c: a))
        self.assertEqual(len(calls), n)                      # (asked within the hour: not again)


if __name__ == "__main__":
    unittest.main()
