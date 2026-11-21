"""Click to close (universal for anything drawn on screen like that): every card or panel the app
draws over the game that only shows something closes on a click anywhere on it, as the alert card does - the Trial
of the Sekhemas legend, Island rumors, the Desecration Helper's notice (the read mark, Back from a
map, Top Up and every helper alert are alert cards already). Overlays with their own controls are left alone.

    python3.12 -m unittest tests.test_click_close          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-click-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import alertcard                                # noqa: E402

SHOWS_ONLY = {"sekhemas_page.py": "click_to_close(win, close)", "rumours_page.py": "click_to_close(w, self.ru_hide)",
              "wellsouls_page.py": "click_to_close(w, lambda: w.winfo_exists() and w.destroy())"}


def source(name):
    with open(os.path.join(ROOT, "soe2", name), encoding="utf-8") as f:
        return f.read()


class ClickToClose(unittest.TestCase):
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

    def test_anywhere_once(self):
        w = tk.Toplevel(self.root)
        f = tk.Frame(w)
        f.pack()
        lab = tk.Label(f, text="deep inside")
        lab.pack()
        got = []
        alertcard.click_to_close(w, lambda: (got.append(1), w.destroy()))
        self.root.update()
        self.assertEqual(lab.cget("cursor"), "hand2")
        lab.event_generate("<Button-1>")
        self.root.update()
        self.assertEqual(got, [1])
        self.assertFalse(w.winfo_exists())

    def test_rumours_panel(self):
        from soe2.rumours_page import RumoursPage

        class App(RumoursPage):
            pass
        a = App()
        a.root = self.root
        a.ru_show([("A strange light", "Isle of Kin", (100, 100, 300, 120))], (320, 100, 320, 120))
        self.root.update()
        w = a.ru_wins[0]
        self.assertTrue(getattr(w, "click_closes", False))
        w.winfo_children()[0].event_generate("<Button-1>")
        self.root.update()
        self.assertFalse(w.winfo_exists())
        self.assertIsNone(a.ru_wins)

    def test_desecration_notice(self):
        from soe2.wellsouls_page import WellSoulsPage

        class App(WellSoulsPage):
            def look_key_text(self):
                return "your Read Key (Ctrl+Shift+R)"

            def log_error(self, where):
                raise AssertionError(where)
        a = App()
        a.root = self.root
        a.ws_notice()
        self.root.update()
        w = a.ws_note_win
        self.assertTrue(getattr(w, "click_closes", False))
        w.winfo_children()[0].event_generate("<Button-1>")
        self.root.update()
        self.assertFalse(w.winfo_exists())

    def test_where_it_applies(self):
        for f, call in SHOWS_ONLY.items():
            self.assertIn(call, source(f), f)
        # overlays with their own controls (or tags on the game's own items) keep their clicks / let them through
        self.assertNotIn("click_to_close", source("pcpop.py"))
        self.assertNotIn("click_to_close", source("stashscan_page.py"))
        self.assertNotIn("click_to_close", source("campaign_ui.py"))
        self.assertIn("click_through(t)", source("favours_page.py"))       # (price tags on the window's cells)


if __name__ == "__main__":
    unittest.main()
