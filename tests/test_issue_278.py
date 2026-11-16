"""Issue #278 (3.0.3): What's new reopened after Got it, and Exchange Rates froze the app.

  * A version after 3.0.0 has no lead of its own: the card brings 3.0.0's lead along, and closing any What's new card
    marks the lead seen (app.close_whatsnew), so Got it closes it for good.
  * Exchange Rates' pictures: one downloader thread, one poll timer, and it stops after Icons.GIVE_UP failures in a row.

    python3.12 -m unittest tests.test_issue_278          (or tests/runall.sh)"""
import os
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-278-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import config, whatsnew as W                     # noqa: E402


def source(name):
    with open(os.path.join(ROOT, "soe2", name), encoding="utf-8") as f:
        return f.read()


class WhatsNewCloses(unittest.TestCase):
    def test_lead_reachable(self):
        v = config.APP_VERSION
        lv = W.lead_version(v)
        self.assertEqual(lv, "3.0.0")
        self.assertEqual(W.lead_of(W.notes_between(None, v)) != [], v == lv)   # (3.0.1 on: no lead of its own)
        self.assertTrue(W.lead_of([(lv, W.NOTES.get(lv))]))                   # ... so the card takes 3.0.0's

    def test_close_marks_the_lead(self):
        app = source("app.py")
        self.assertIn("lead = lead_of([(lead_version(APP_VERSION)", app)
        self.assertIn('getattr(self, "_wn_lead_shown", False) or notes_card', app)


class RatesPictures(unittest.TestCase):
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

    def test_one_worker_gives_up(self):
        import requests
        from soe2 import rates_view as RV
        tries = []

        def fail(*a, **k):
            tries.append(1)
            raise requests.exceptions.SSLError("blocked")
        real, requests.get = requests.get, fail
        try:
            ready = []
            ic = RV.Icons(self.root, lambda: ready.append(1))
            n0 = threading.active_count()
            for i in range(300):
                self.assertIsNone(ic.get(f"https://web.poecdn.com/x{i}.png"))
            self.assertLessEqual(threading.active_count() - n0, 1)
            end = time.time() + 5
            while time.time() < end and (ic.wait or ic.polling):
                self.root.update()
                time.sleep(0.05)
            self.assertEqual(ic.misses, RV.Icons.GIVE_UP)
            self.assertEqual(len(tries), RV.Icons.GIVE_UP)
            self.assertFalse(ic.wait)
            self.assertIsNone(ic.get("https://web.poecdn.com/another.png"))      # (gave up: no new tries)
            self.assertEqual(len(tries), RV.Icons.GIVE_UP)
            self.assertEqual(ready, [])                                       # (nothing new: no repaint)
        finally:
            requests.get = real


if __name__ == "__main__":
    unittest.main()
