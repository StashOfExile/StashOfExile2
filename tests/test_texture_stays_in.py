"""3.3.0 owner: Hollow Deep's veins ran out of the header strips and sat at the same spot on every header."""
import os
import sys
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import themes as TH  # noqa: E402


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Veins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        from soe2 import style
        style.apply_look()
        TH.load_packs()
        cls.was = TH.ST.theme
        cls.t = TH.packs()["hollow"]
        TH.set_theme(cls.t)

    @classmethod
    def tearDownClass(cls):
        if cls.was is not None:
            TH.set_theme(cls.was)
        cls.root.destroy()

    def strips(self, tops):
        cv = tk.Canvas(self.root, width=1400, height=900)
        out = []
        with TH.raw():
            for i, y in enumerate(tops):
                TH.box_strip(cv, self.t, 20, y, 1320, 0, tags=("s%d" % i,))
                out.append(cv.bbox("s%d" % i))
        return cv, out

    def test_nothing_leaves_the_strip(self):
        tops = [40, 300, 560]
        cv, boxes = self.strips(tops)
        for y, b in zip(tops, boxes):
            self.assertGreaterEqual(b[1], y - 1)
            self.assertLessEqual(b[3], y + TH.BOX_HEAD + 2)
            self.assertGreaterEqual(b[0], 19)
            self.assertLessEqual(b[2], 1322)

    def veins(self, cv, tag, top):
        """Every multi-point line of one strip, moved to the strip's own top."""
        got = []
        for i in cv.find_withtag(tag):
            c = cv.coords(i)
            if cv.type(i) == "line" and len(c) > 4:
                got.append(tuple(round(v - (top if n % 2 else 0)) for n, v in enumerate(c)))
        return got

    def test_headers_differ_and_one_header_repeats(self):
        tops = [40, 300, 560]
        cv, _ = self.strips(tops)
        a, b, c = (self.veins(cv, "s%d" % i, y) for i, y in enumerate(tops))
        self.assertTrue(a and b and c)
        self.assertEqual(len({tuple(a), tuple(b), tuple(c)}), 3)
        cv2, _ = self.strips(tops)
        self.assertEqual(self.veins(cv2, "s0", 40), a, "the same place draws the same: no flicker on redraw")


if __name__ == "__main__":
    unittest.main()
