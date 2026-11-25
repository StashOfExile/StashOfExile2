"""Dashboard: a part is hidden when its feature is off (nothing greyed out; the rest moves up and widens), and a
Start here card is hidden once it is done.

    python3.12 -m unittest tests.test_dashboard_parts          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-dash-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import dashboard_page as D            # noqa: E402
from soe2 import features as FEAT               # noqa: E402
from soe2.config import SETTINGS                # noqa: E402


class FakeApp:
    def __init__(self, recs=()):
        self.recs, self.records, self.shell = list(recs), {}, None

    def pc_recs(self):
        return self.recs


REC = {"id": 1, "src": "pc", "time": time.time(), "item": {"name": "Tabula Rasa"}, "est": 1.0, "prices": [1]}
WEALTH = {"total": 5.0, "today": 1.0, "n": 3, "ts": time.time(), "series": []}


class Parts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.geometry("1200x900")
        from soe2 import style
        style.apply_look()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        for k in ("wealth", "price", "overlay"):
            FEAT.set_on(k, True)
        self._feat = dict(FEAT.cfg())
        self._wn, self._mp = D.wealth_numbers, D.map_numbers
        D.wealth_numbers = lambda now=None: None
        D.map_numbers = lambda now=None: None
        self._hr = D.helper_rows
        D.helper_rows = lambda: [("Map profit", False), ("Temple Helper", False)]

    def tearDown(self):
        D.wealth_numbers, D.map_numbers, D.helper_rows = self._wn, self._mp, self._hr
        FEAT.cfg().update(self._feat)

    def page(self, recs=()):
        d = D.Dashboard(FakeApp(recs), self.root)
        d.pack(fill="both", expand=True)
        self.root.update()
        d.redraw()
        return d

    @staticmethod
    def texts(d):
        # a theme may draw box titles in capitals: read them back as written
        got = [d.itemcget(i, "text") for i in d.find_all() if d.type(i) == "text"]
        return [t.capitalize() if len(t) > 3 and t.isupper() else t for t in got]

    @staticmethod
    def edges(d, text):
        for i in d.find_all():
            if d.type(i) == "text" and d.itemcget(i, "text") in (text, text.upper()):
                return d.bbox(i)

    def test_wealth_off_no_wealth_tiles(self):
        d = self.page()
        self.assertIn("Stash worth", self.texts(d))
        self.assertIn("Today", self.texts(d))
        self.assertIn("At a glance", [t.capitalize() for t in self.texts(d)])    # the numbers share one titled box
        FEAT.set_on("wealth", False)
        d.redraw()
        t = self.texts(d)
        self.assertNotIn("Stash worth", t)
        self.assertNotIn("Today", t)
        self.assertNotIn("See what you have earned", t)
        self.assertIn("Items price checked today", t)

    def test_price_off_no_pickup_helpers_full_width(self):
        d = self.page()
        before = d.bbox(self.find(d, "All helpers"))
        FEAT.set_on("price", False)
        d.redraw()
        t = self.texts(d)
        self.assertNotIn("Pick up where you left off", t)
        self.assertNotIn("Items price checked today", t)
        self.assertNotIn("Know what an item is worth", t)
        self.assertIn("Helpers", t)
        after = d.bbox(self.find(d, "All helpers"))
        self.assertGreater(after[2], before[2] - 1)              # the right edge stays
        self.assertLess(d.bbox(self.find(d, "Helpers"))[0], 60)  # ... and it starts at the page margin

    @staticmethod
    def find(d, text):
        for i in d.find_all():
            if d.type(i) == "text" and d.itemcget(i, "text") in (text, text.upper()):
                return i

    def test_all_off_empty_state_one_button(self):
        for k in ("wealth", "price", "overlay"):
            FEAT.set_on(k, False)
        d = self.page()
        t = self.texts(d)
        self.assertIn("Your Dashboard shows the parts you turn on.", t)
        self.assertEqual(sorted(a for a in d.acts if a.startswith("b_")), ["b_feat"])
        for gone in ("Start here", "Helpers", "Pick up where you left off", "Stash worth"):
            self.assertNotIn(gone, t)

    def test_done_card_hidden(self):
        d = self.page()
        self.assertIn("Know what an item is worth", self.texts(d))
        self.assertIn("Start here", self.texts(d))
        d = self.page([REC])
        self.assertNotIn("Know what an item is worth", self.texts(d))
        self.assertIn("See what you have earned", self.texts(d))
        D.wealth_numbers = lambda now=None: WEALTH
        D.helper_rows = lambda: [("Map profit", True)]
        d = self.page([REC])
        self.assertNotIn("Start here", self.texts(d))            # all three done: the section goes

    def test_visible_parts(self):
        v = D.visible_parts(False, False, False)
        self.assertTrue(v["start_price"] and v["start_wealth"] and v["start_overlay"] and not v["empty"])
        FEAT.set_on("overlay", False)
        v = D.visible_parts(False, False, False)
        self.assertFalse(v["start_overlay"] or v["map"])


if __name__ == "__main__":
    unittest.main()
