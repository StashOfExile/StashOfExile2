"""3.0.6 (owner): on the Price Checks card in the app, hold the left button on a box and drag across others - every
box crossed (mods, base type, item level, quality, sockets, Fractured only) takes the first box's new state, as on
the card over the game.

    python3.12 -m unittest tests.test_card_drag          (or tests/runall.sh)"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import app as A                                  # noqa: E402

TAGS = ["cardbase", "cardopt_ilvl", "cardrow0", "cardonly0", "cardrow1"]


class Canvas:
    """One box every 20 px down: the box under (x, y) is TAGS[y // 20]."""
    def __init__(self):
        self.binds = {}

    def canvasx(self, x):
        return x

    def canvasy(self, y):
        return y

    def find_overlapping(self, x0, y0, x1, y1):
        return (int(y0) // 20,)

    def gettags(self, item):
        return (TAGS[item], "cardmod") if item < len(TAGS) else ()

    def tag_bind(self, tag, ev, fn):
        self.binds[(tag, ev)] = fn

    def bind(self, ev, fn, add=None):
        self.binds[ev] = fn

    def configure(self, **k):
        pass


class Drag(unittest.TestCase):
    def setUp(self):
        self.on = {t: False for t in TAGS}
        self.on["cardrow0"] = True
        self.calls = []
        self.me = types.SimpleNamespace()
        for name in ("_card_tick_box", "_card_drag_start", "_card_drag_over"):
            setattr(self.me, name, getattr(A.App, name).__get__(self.me))
        self.cv = Canvas()
        for t in TAGS:
            self.me._card_tick_box(self.cv, {}, t, lambda t=t: self.on[t],
                                   lambda v, t=t: (self.calls.append((t, v)), self.on.__setitem__(t, v)))

    def press(self, tag):
        self.cv.binds[(tag, "<Button-1>")](None)

    def move(self, y):
        self.cv.binds["<B1-Motion>"](types.SimpleNamespace(x=5, y=y))

    def test_drag_down_ticks_every_kind_of_box(self):
        self.press("cardbase")
        for y in (5, 25, 45, 65, 85, 65, 25):
            self.move(y)
        self.assertTrue(all(self.on.values()))
        self.assertEqual([t for t, _v in self.calls], ["cardbase", "cardopt_ilvl", "cardonly0", "cardrow1"])

    def test_drag_from_a_ticked_box_unticks(self):
        self.on = {t: True for t in TAGS}
        self.press("cardrow1")
        for y in (85, 65, 45, 25, 5):
            self.move(y)
        self.assertFalse(any(self.on.values()))

    def test_no_drag_after_release(self):
        self.press("cardbase")
        self.cv.binds["<ButtonRelease-1>"](None)
        self.move(25)
        self.assertFalse(self.on["cardopt_ilvl"])


if __name__ == "__main__":
    unittest.main()
