"""Favorites scales to fit the window (3.0.6 style pass): the list is about a quarter of the page (300 to 460 px) and
the card takes the rest - the whole width after the list while nothing is picked, the listings beside it when a
favorite is - at any window width, in the full window and in the Drawer's narrow shape.

    python3.12 -m unittest tests.test_favorites_fit          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-favfit-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_bulk_layout as BL                              # noqa: E402
from soe2.config import SETTINGS                           # noqa: E402


class Fit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        S.setup_style(cls.root)
        SETTINGS.update(league="Standard", pc_fold={}, pc_art=False)
        cls.app = BL.make_app(cls.root)
        cls.app.favs = lambda: cls.app.__class__.favs(cls.app)
        cls.body = tk.Frame(cls.root)
        cls.body.pack(fill="both", expand=True)
        cls.app.build_favorites(cls.body)

    @classmethod
    def tearDownClass(cls):
        for job in cls.root.tk.splitlist(cls.root.tk.call("after", "info")):
            cls.root.tk.call("after", "cancel", job)
        cls.root.destroy()

    def size(self, w, h=900):
        self.root.geometry(f"{w}x{h}+0+0")
        for _ in range(3):
            for _ in range(8):
                self.root.update()
            time.sleep(0.2)

    def test_list_share_is_a_quarter_between_300_and_460(self):
        a = self.app
        self.assertEqual(a.fav_list_width(900), 300)
        self.assertEqual(a.fav_list_width(1400), 364)
        self.assertEqual(a.fav_list_width(2400), 460)

    def test_nothing_picked_the_card_fills_the_width(self):
        for w in (1000, 1400, 1900):
            self.size(w)
            lf, mid, wrap = self.app.fav_lf, self.app.fav_mid, self.app.fav_wrap
            self.assertFalse(self.app.fav_right.winfo_ismapped(), "no listings pane while nothing is picked")
            self.assertAlmostEqual(lf.winfo_width(), self.app.fav_list_width(wrap.winfo_width()), delta=6)
            self.assertAlmostEqual(lf.winfo_width() + mid.winfo_width(), wrap.winfo_width(), delta=4,
                                   msg=f"list + card fill the page at {w}")
            self.assertGreaterEqual(mid.winfo_height(), wrap.winfo_height() - 4, "and the whole height")

    def test_picked_the_listings_sit_beside_the_card(self):
        self.size(1700)
        self.app.fav_layout(True)
        self.size(1700)
        a = self.app
        self.assertTrue(a.fav_right.winfo_ismapped())
        total = a.fav_lf.winfo_width() + a.fav_mid.winfo_width() + a.fav_right.winfo_width()
        self.assertAlmostEqual(total, a.fav_wrap.winfo_width(), delta=4, msg="the three panes fill the page")
        self.assertGreater(a.fav_right.winfo_width(), 300)
        self.assertGreater(a.fav_mid.winfo_width(), 440)
        a.fav_layout(False)
        self.size(1700)
        self.assertFalse(a.fav_right.winfo_ismapped())


if __name__ == "__main__":
    unittest.main()
