"""3.0.1 (owner: the What's new card scrolled only with the mouse over its text - over one of its cards the wheel did
nothing): cards placed in a Text (window_create) pass the wheel on to it (style.wheel_scrolls) - the What's new card
(the whole card window). 3.0.6: Farming Strategies draws an opened strat on one canvas (stratview.py) - nothing
is placed in a Text there any more, and a card placed in one later must pass the wheel on too.

    python3.12 -m unittest tests.test_wheel_cards          (or tests/runall.sh)"""
import os
import re
import sys
import tempfile
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-wheel-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2.style import wheel_scrolls                      # noqa: E402


def source(name):
    with open(os.path.join(ROOT, "soe2", name), encoding="utf-8") as f:
        return f.read()


class WheelOverCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def text_with_cards(self, host_is_window):
        top = tk.Toplevel(self.root)
        top.geometry("300x200+0+0")
        self.addCleanup(top.destroy)
        t = tk.Text(top, height=8)
        t.pack(fill="both", expand=True)
        cards = []
        for i in range(12):
            card = tk.Frame(t, height=60, width=200, bg="#222222")
            deep = tk.Label(tk.Frame(card), text=f"card {i}")
            deep.master.pack()
            deep.pack()
            t.window_create("end", window=card)
            t.insert("end", "\n")
            cards.append((card, deep))
            if not host_is_window:
                wheel_scrolls(t, card)
        if host_is_window:
            wheel_scrolls(t, top)
        top.update()
        return t, cards

    def spin(self, w, t, down=True):
        before = t.yview()[0]
        w.event_generate("<MouseWheel>", delta=-120 if down else 120)
        w.event_generate("<Button-5>" if down else "<Button-4>")
        self.root.update()
        return before, t.yview()[0]

    def test_over_a_card_in_the_window(self):          # (the What's new card: the whole window)
        t, cards = self.text_with_cards(True)
        before, after = self.spin(cards[0][1], t)
        self.assertGreater(after, before, "the wheel over a card scrolls the text")
        before, after = self.spin(cards[0][1], t, down=False)
        self.assertLess(after, before, "and back up")

    def test_over_a_card_bound_itself(self):           # (Farming Strategies: each card and what's in it)
        t, cards = self.text_with_cards(False)
        before, after = self.spin(cards[0][1], t)
        self.assertGreater(after, before)

    def test_text_itself_not_twice(self):
        t, _cards = self.text_with_cards(True)
        fired = []
        t.bind("<MouseWheel>", lambda e: fired.append(1), add="+")
        t.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertEqual(fired, [1])                    # (its own binding; the card's skips the text)

    def test_the_places_use_it(self):
        app = source("app.py")
        self.assertIn("wheel_scrolls(t, card)", app, "What's new: the whole card")
        for name in ("moneymakers_page.py", "stratview.py"):
            mm = source(name)
            for w in re.findall(r't\.window_create\("end", window=(\w+)', mm):
                self.assertIn(f"wheel_scrolls(t, {w})", mm, f"Farming Strategies: {w} passes the wheel on")


if __name__ == "__main__":
    unittest.main()
