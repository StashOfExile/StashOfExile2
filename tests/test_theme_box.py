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
    def test_defaults_are_todays_look(self):
        self.assertEqual(TH.box_look(theme()), {"shape": "round", "head": "plain", "mark": "none", "caps": False})

    def test_unknown_values_fall_back(self):
        k = TH.box_look(theme(shape="blob", head="nope", mark=3, caps=1))
        self.assertEqual((k["shape"], k["head"], k["mark"], k["caps"]), ("round", "plain", "none", True))

    def test_subject_is_a_color_and_unknown_falls_back(self):
        t = theme()
        self.assertEqual(TH.subject(t, "wealth"), t.c("money"))
        self.assertEqual(TH.subject(t, "no such subject"), t.c("accent_2"))

    def test_every_subject_names_a_real_color(self):
        t = theme()
        for name in TH.DEFAULTS["subjects"]:
            self.assertNotEqual(TH.subject(t, name), "#ff00ff", name)

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
                    for mark in TH.BOX["mark"]:
                        t = theme(shape=shape, head=head, mark=mark, caps=True)
                        cv.delete("all")
                        TH.box(cv, t, 10, 10, 390, 190, 8, sub="wealth")
                        tid, up = TH.box_head(cv, t, 10, 10, 390, 8, "Top Movers", "market")
                        self.assertEqual(cv.type(tid), "text")
                        self.assertEqual(up, 0 if head == "plain" else 8)
                        self.assertEqual(cv.itemcget(tid, "text"), "Top Movers" if head == "plain" else "TOP MOVERS")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
