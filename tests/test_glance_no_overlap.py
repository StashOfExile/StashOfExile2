"""3.3.0 owner: in At a Glance the line under a number never sits on the number, in every theme."""
import os
import sys
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from soe2 import themes as TH  # noqa: E402


def overlaps(cv):
    """Pairs of text items in one column whose boxes overlap in height."""
    items = [(i, cv.bbox(i)) for i in cv.find_all() if cv.type(i) == "text" and cv.itemcget(i, "text").strip()]
    bad = []
    for a, ba in items:
        for b, bb in items:
            if a < b and ba and bb and abs(ba[0] - bb[0]) < 3 and ba[1] < bb[3] - 1 and bb[1] < ba[3] - 1:
                bad.append((cv.itemcget(a, "text"), cv.itemcget(b, "text")))
    return bad


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Glance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.geometry("1000x900")
        from soe2 import style
        style.apply_look()
        TH.load_packs()
        cls.was = TH.ST.theme

    @classmethod
    def tearDownClass(cls):
        if cls.was is not None:
            TH.set_theme(cls.was)
        cls.root.destroy()

    def each_theme(self):
        packs = TH.packs()
        self.assertGreater(len(packs), 3)
        for tid, t in packs.items():
            TH.set_theme(t)
            yield tid

    def test_wealth_tiles_every_theme(self):
        from soe2.cards import StatTiles, Tile
        for tid in self.each_theme():
            w = StatTiles(self.root)
            w.pack(fill="x")
            self.root.update()
            w.set([Tile("Stash worth", "9636 div", "from 125 items · 1 h ago", None, "how"),
                   Tile("Today", "+710 div", "▲ Up", None, "how")])
            self.root.update()
            self.assertEqual(overlaps(w), [], tid)
            texts = [w.bbox(i) for i in w.find_all() if w.type(i) == "text"]
            self.assertLessEqual(max(b[3] for b in texts), int(w.cget("height")), tid)
            w.destroy()

    def test_dashboard_tiles_every_theme(self):
        import test_dashboard_parts as P
        from soe2 import dashboard_page as D
        was = D.wealth_numbers, D.map_numbers
        try:
            for tid in self.each_theme():
                d = D.Dashboard(P.FakeApp(()), self.root)
                d.pack(fill="both", expand=True)
                self.root.update()
                d.redraw()
                foot = [i for i in d.find_all() if d.type(i) == "text" and "tile" in "".join(d.gettags(i))]
                self.assertTrue(foot, tid)
                tiles = {}
                for i in foot:
                    tiles.setdefault([g for g in d.gettags(i) if g.startswith("tile")][0], []).append(d.bbox(i))
                for tag, boxes in tiles.items():
                    boxes.sort(key=lambda b: b[1])
                    for up, down in zip(boxes, boxes[1:]):
                        self.assertLessEqual(up[3], down[1] + 1, f"{tid} {tag}")
                d.destroy()
        finally:
            D.wealth_numbers, D.map_numbers = was


if __name__ == "__main__":
    unittest.main()
