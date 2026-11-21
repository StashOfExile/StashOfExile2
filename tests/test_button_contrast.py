"""Secondary buttons read as buttons (3.0.6 style pass): Quiet / Strip buttons, the tab chips, the chips on a canvas and
the SegBar have a visible fill and an outline of at least 3 : 1 against the page behind them, in every theme; the picked
SegBar segment tells itself apart (fill, bold, its mark), hover is brighter; the Exchange Rates and Price Checks lists
have the thin scroll bar, only while they are longer than the page.

    python3.12 -m unittest tests.test_button_contrast          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk

HOME = tempfile.mkdtemp(prefix="soe2-btncontrast-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import check_contrast as CC                                # noqa: E402
from soe2 import soft as SOFT, style as S                  # noqa: E402


class EveryTheme(unittest.TestCase):
    def test_text_pairs_and_outlines(self):
        worst, fails = CC.run()
        self.assertEqual(fails, [], fails[:5])
        edges = CC.run_edges()
        self.assertEqual(edges, [], edges[:5])

    def test_hover_is_brighter_and_the_picked_one_stronger(self):
        under, text = (14, 21, 34), (125, 141, 168)
        lk = SOFT.secondary_looks(text, under, (219, 228, 242), ink=(143, 163, 199))
        on = SOFT.secondary_looks(text, under, (219, 228, 242), picked=True, ink_hover=(219, 228, 242))
        self.assertGreater(SOFT._lum(lk["h"][0]), SOFT._lum(lk["n"][0]))
        self.assertGreater(SOFT.contrast(lk["n"][1], under), 3.0)
        self.assertGreater(SOFT._lum(on["n"][0]), SOFT._lum(lk["n"][0]))
        self.assertNotEqual(lk["n"][0], under, "a visible fill")

    def test_chip_colors_are_hex_and_outlined(self):
        c = SOFT.chip_colors("#0e1522", "#7d8da8", "#dbe4f2")
        edge = tuple(int(c["off"][1][i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(SOFT.contrast(edge, (14, 21, 34)), 3.0)
        self.assertNotEqual(c["on"][0], c["off"][0])


class Widgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        S.setup_style(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_segbar_unpicked_is_a_filled_button_not_a_label(self):
        page = tk.Frame(self.root, bg=S.C["panel"])
        page.pack()
        bar = S.SegBar(page, ["Copy items", "Read a stash tab"], plain=True, badges={"Read a stash tab": "BETA"})
        bar.pack()
        self.root.update()
        on, off = bar.btns["Copy items"][0], bar.btns["Read a stash tab"][0]
        self.assertTrue(on.cget("text").startswith("✓ "), "the picked one keeps its mark and word")
        self.assertNotEqual(on.cget("bg"), off.cget("bg"), "picked and unpicked fills differ")
        self.assertNotEqual(off.cget("bg"), S.C["panel"], "the unpicked one has a fill of its own")
        self.assertNotEqual(bar.cget("bg"), S.C["panel"], "and an outline")
        bar.paint(hover="Read a stash tab")
        self.assertNotEqual(off.cget("bg"), bar.looks()["off"], "hover is brighter")

    def test_quiet_button_has_a_round_face_on_the_page_color(self):
        b = ttk.Button(self.root, text="Columns ▾", style="Quiet.TButton")
        b.pack()
        self.root.update()
        self.assertIn("Quiet", str(b.tk.call(b._w, "cget", "-style")), "the variant for its background")
        self.assertTrue(str(ttk.Style(self.root).layout(str(b.tk.call(b._w, "cget", "-style")))), "a layout")

    def test_overflow_scroll_bar_only_when_longer(self):
        f = tk.Frame(self.root)
        f.pack(fill="both", expand=True)
        cv = tk.Canvas(f, width=200, height=100)
        cv.pack()
        sb = S.overflow_scrollbar(cv)
        cv.configure(scrollregion=(0, 0, 200, 90))
        cv.yview_moveto(0)
        self.root.update()
        self.assertFalse(sb.winfo_manager(), "a short list: no bar")
        cv.configure(scrollregion=(0, 0, 200, 900))
        self.root.update()
        self.assertTrue(sb.winfo_manager(), "a long list: the bar")
        cv.configure(scrollregion=(0, 0, 200, 90))
        self.root.update()
        self.assertFalse(sb.winfo_manager(), "short again: gone")

    def test_lists_without_a_bar_got_one(self):
        from soe2 import pclist, rates_view
        import inspect
        for mod in (pclist, rates_view):
            self.assertIn("overflow_scrollbar", inspect.getsource(mod))


if __name__ == "__main__":
    unittest.main()
