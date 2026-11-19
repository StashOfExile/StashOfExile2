"""3.0.6 (owner: the box under a fractured / desecrated mod was missing on the card over the game - Price Checks
had it): right under such a mod, "└ ☐ Fractured only" / "Desecrated only"; a click searches it only as that and
ticks the mod too.

    python3.12 -m unittest tests.test_pcpop_only          (or tests/runall.sh)"""
import os
import sys
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_pcpop_typing as TY                            # noqa: E402  (sets HOME first)
from soe2.mods import norm                                 # noqa: E402


class Only(unittest.TestCase):
    setUpClass = classmethod(TY.Typing.setUpClass.__func__)
    tearDownClass = classmethod(TY.Typing.tearDownClass.__func__)
    card = TY.Typing.card

    def labels(self, p):
        out = []

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Label):
                    out.append(c)
                walk(c)
        walk(p.pp_win)
        return out

    def test_box_under_fractured_and_desecrated_mods(self):
        for name, word in (("rare_amulet_fractured", "Fractured only"), ("rare_belt_desecrated", "Desecrated only")):
            p, rec, _took = self.card(name)
            got = [w for w in self.labels(p) if w.cget("text") == word]
            self.assertEqual(len(got), 1, name)
            calls = []
            p.card_only = lambda r, m, on: (calls.append((norm(m["text"]), on)),
                                            r.setdefault("only", {}).__setitem__(norm(m["text"]), True))
            got[0].event_generate("<Button-1>", x=2, y=2)
            self.root.update()
            self.assertEqual(len(calls), 1, name)
            self.assertTrue(calls[0][1])
            box = [w for w in self.labels(p) if w.cget("text") == "☑"]
            self.assertTrue(box, f"{name}: the box shows ticked after the click")
            p.pcpop_close()

    def test_no_box_on_plain_mods(self):
        p, _rec, _took = self.card("rare_ring")
        self.assertFalse([w for w in self.labels(p) if str(w.cget("text")).endswith(" only")])
        p.pcpop_close()

    def test_drag_across_mods(self):
        """3.0.6 (owner): hold the left button on a mod and drag across others - each one crossed takes the first
        one's new state; the search changes once, when the button comes up."""
        p, rec, _took = self.card("rare_ring")
        ticks = list(p.pp_ticks)
        self.assertGreaterEqual(len(ticks), 3)
        fills = []
        real_fill = p.pcpop_fill
        p.pcpop_fill = lambda r: (fills.append(1), real_fill(r))[-1]
        first = ticks[0]
        to = not first[3]
        p._pcpop_drag_start(first)
        for t in ticks[1:3]:
            self.root.update()
            x, y = t[1].winfo_rootx() + 3, t[1].winfo_rooty() + 3
            p.root.winfo_containing = lambda _x, _y, w=t[1]: w      # (no real mouse under Xvfb)
            p._pcpop_drag_over(x, y)
            self.assertEqual(t[0].cget("text"), "☑" if to else "☐")
        self.assertEqual(fills, [])                                 # nothing searched while dragging
        p._pcpop_drag_end(rec)
        self.assertEqual(fills, [1])                                # one redraw on release
        on = {id(m) for m in p.pc_ticked(rec)}
        for t in ticks[:3]:
            self.assertEqual(id(t[2]) in on, to)
        p.pcpop_close()


if __name__ == "__main__":
    unittest.main()
