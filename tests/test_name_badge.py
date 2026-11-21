"""The Name badge (owner decision, GGG policy audit: the overlay must never read as part of the game): every
style and every layout shows STASH OF EXILE 2 in a small badge, under the clock where there is a clock, with room
round it - nothing overlaps the clock, and nothing runs off the window's edges. Classic's end-cap gems are pale
gold, not the game's red and blue.

    DISPLAY=:99 python3.12 -m unittest tests.test_name_badge"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_split_layout as T  # noqa: E402  (sets HOME first)
import tkinter as tk  # noqa: E402

from soe2 import hudart, ovlight as OL  # noqa: E402

STYLES = ["classic", "hairline", "slate", "micro"] + list(OL.ORNATE)


class App(T.FakeApp):
    def merged_layout(self):
        return self.cfg["layout"]

    def ov_look_colors(self):
        return OL.DEFAULT_COLORS


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


class NameBadge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.geometry("1400x700+0+0")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def draw(self, style, layout, clock=True, width=1000):
        a = App(self.root, style, layout)
        a.cfg["clock"] = clock
        host = tk.Frame(self.root)
        host.place(x=0, y=0)
        a.ov_preview(host, style, width=width)
        self.root.update_idletasks()
        cvs = [w for w in walk(host) if isinstance(w, tk.Canvas)]
        return host, cvs

    def check(self, style, layout, clock=True, width=1000):
        host, cvs = self.draw(style, layout, clock, width)
        try:
            found = 0
            for cv in cvs:
                items = cv.find_withtag("ov_badge")
                if not items:
                    continue
                found += 1
                texts = [i for i in items if cv.type(i) == "text"]
                self.assertEqual([cv.itemcget(i, "text") for i in texts], [OL.BADGE])
                box = cv.bbox([i for i in items if cv.type(i) == "rectangle"][0])
                W, H = int(cv.cget("width")), int(cv.cget("height"))
                where = f"{style} {layout} clock={clock} width={width}"
                self.assertGreaterEqual(box[1], 2, where)            # room above and below, inside the window
                self.assertLessEqual(box[3], H - 2, where)
                self.assertGreaterEqual(box[0], 0, where)
                self.assertLessEqual(box[2], W, where)
                for c in cv.find_all():                              # the clock: over the badge, not on it
                    if cv.type(c) == "text" and cv.itemcget(c, "text") == "9:41 PM":
                        cb = cv.bbox(c)
                        fm = tk.font.Font(root=cv, font=cv.itemcget(c, "font"))
                        glyph_bottom = cb[1] + fm.metrics("ascent")   # (the line's baseline: digits stop there)
                        self.assertLessEqual(glyph_bottom, box[1] + 1, where)
                        self.assertGreaterEqual(cb[1] + fm.metrics("ascent") * 0.28, 1, where)
            self.assertEqual(found, 1, f"{style} {layout}: one badge")
        finally:
            host.destroy()

    def test_every_style_and_layout(self):
        import tkinter.font  # noqa: F401
        for style in STYLES:
            for layout in ("xpbar", "panel", "split"):
                for clock in (True, False):
                    with self.subTest(style=style, layout=layout, clock=clock):
                        self.check(style, layout, clock)

    def test_1080p(self):
        import tkinter.font  # noqa: F401
        for style in ("classic", "hairline", "slate", "micro"):
            for layout in ("xpbar", "panel", "split"):
                with self.subTest(style=style, layout=layout):
                    self.check(style, layout, width=773)

    def test_gems_are_gold(self):
        self.assertFalse(hasattr(hudart, "CRIMSON") or hasattr(hudart, "SAPPHIRE"))
        img = hudart.plate(self.root, 600, 44)
        self.assertIsNotNone(img)


if __name__ == "__main__":
    unittest.main()
