"""3.3.0 look pass: a theme sets how a page draws its boxes, and the color each subject keeps."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import themes as TH


def theme(**box):
    data = TH._merge(TH.DEFAULTS, {"id": "t", "box": box})
    return TH.Theme(data)


class BoxLook(unittest.TestCase):
    def test_defaults_are_square_titled_boxes(self):
        self.assertEqual(TH.box_look(theme()), {"shape": "square", "head": "strip", "caps": False})

    def test_unknown_values_fall_back(self):
        k = TH.box_look(theme(shape="blob", head="tint", caps=1))
        self.assertEqual((k["shape"], k["head"], k["caps"]), ("square", "strip", True))

    def test_inset_follows_the_corner(self):
        self.assertEqual(TH._inset(0, 0), 0)
        self.assertGreater(TH._inset(8, 0), TH._inset(8, 4))
        self.assertEqual(TH._inset(8, 8), 0)

    def test_shipped_themes_use_known_values(self):
        TH.load_packs()
        for tid, t in TH.packs().items():
            got = t.part("box") or {}
            for key, allowed in TH.BOX.items():
                self.assertIn(got.get(key, allowed[0]), allowed, f"{tid}: box.{key}")


class BoxDraws(unittest.TestCase):
    def test_each_style_draws_and_gives_a_title(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            cv = tk.Canvas(root, width=400, height=200)
            for shape in TH.BOX["shape"]:
                for head in TH.BOX["head"]:
                    t = theme(shape=shape, head=head, caps=True)
                    cv.delete("all")
                    TH.box(cv, t, 10, 10, 390, 190, 8)
                    tid, up = TH.box_head(cv, t, 10, 10, 390, 8, "Top Movers")
                    self.assertEqual(cv.type(tid), "text")
                    self.assertEqual(up, 0 if head == "plain" else 15)
                    self.assertEqual(cv.itemcget(tid, "text"), "Top Movers" if head == "plain" else "TOP MOVERS")
        finally:
            root.destroy()

    def test_no_color_stripe_on_a_box(self):
        """Owner, 2026-11-23: no colored line along a box's edge or beside its title."""
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            cv = tk.Canvas(root, width=400, height=200)
            t = theme(shape="square", head="strip")
            TH.box(cv, t, 10, 10, 390, 190, 8)
            TH.box_head(cv, t, 10, 10, 390, 8, "Top Movers")
            loud = {t.c(k) for k in ("accent", "accent_2", "good", "bad", "money", "link", "purple", "orange")}
            for i in cv.find_all():
                if cv.type(i) in ("rectangle", "line"):
                    self.assertNotIn(cv.itemcget(i, "fill"), loud)
        finally:
            root.destroy()


class PanelHeadTakesALabelsCalls(unittest.TestCase):
    """3.3.0 look pass: Price Checks' headings are header strips that the old label code still writes to."""

    def test_text_splits_into_title_and_count(self):
        import tkinter as tk
        from soe2 import chrome
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            h = chrome.PanelHead(root, "")
            h.config(text="CHEAPEST LISTINGS · 4 of 5")
            self.assertEqual((h.title, h.note()), ("Cheapest Listings", "4 of 5"))
            self.assertEqual(h.cget("text"), "CHEAPEST LISTINGS · 4 of 5")
            h.configure(text="No listings found")
            self.assertEqual((h.title, h.note()), ("No listings found", ""))
            h.config(bg="#000000")                      # (a canvas option still goes to the canvas)
            self.assertEqual(h.cget("bg"), "#000000")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
