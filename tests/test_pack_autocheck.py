"""The data packs check for a newer copy by themselves, once a day - there is no button for it.

    python3.12 -m unittest tests.test_pack_autocheck          (or tests/runall.sh)"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import packcheck                     # noqa: E402
from soe2.config import SETTINGS               # noqa: E402


def src(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


class Schedule(unittest.TestCase):
    def setUp(self):
        self.old = SETTINGS.pop("packs_checked", None)

    def tearDown(self):
        SETTINGS.pop("packs_checked", None)
        if self.old is not None:
            SETTINGS["packs_checked"] = self.old

    def test_due_once_a_day(self):
        self.assertTrue(packcheck.due(1_000_000))                         # never checked
        packcheck.mark(1_000_000)
        self.assertFalse(packcheck.due(1_000_000 + 3600))
        self.assertFalse(packcheck.due(1_000_000 + 24 * 3600 - 5))
        self.assertTrue(packcheck.due(1_000_000 + 24 * 3600))
        self.assertTrue(packcheck.due(900_000 - 10_000))                  # (the clock went back)

    def test_run_asks_each_pack_once_and_counts_the_day(self):
        calls = []
        res = packcheck.run(lambda: calls.append("craft") or ("same", "x"), lambda: calls.append("camp") or ("new", "y"))
        self.assertEqual(calls, ["craft", "camp"])
        self.assertEqual(res["craft"][0], "same")
        self.assertFalse(packcheck.due())
        SETTINGS.pop("packs_checked")
        packcheck.run(lambda: ("error", "x"), lambda: ("error", "y"))      # GitHub unreachable: try again soon
        self.assertTrue(packcheck.due())

    def test_one_failing_pack_does_not_stop_the_other(self):
        def boom():
            raise OSError("down")
        res = packcheck.run(boom, lambda: ("same", "ok"))
        self.assertEqual(res["craft"][0], "error")
        self.assertEqual(res["campaign"][0], "same")

    def test_status_words(self):
        self.assertEqual(packcheck.state(), "")
        self.assertEqual(packcheck.ago(), "not checked yet")
        packcheck.mark(1_000_000)
        self.assertEqual(packcheck.state(1_000_000 + 60), "up to date")
        self.assertEqual(packcheck.ago(1_000_000 + 3 * 3600), "checked 3 h ago")
        self.assertIn("once a day", packcheck.tip("x"))


class NoButton(unittest.TestCase):
    def test_buttons_are_gone(self):
        for f in ("moneymakers_page.py", "campaign_ui.py", "app.py"):
            s = src("soe2", f)
            self.assertNotIn("Check for a newer", s, f)
            self.assertNotIn("camp_check_pack", s, f)
            self.assertNotIn("mm_ch_pack_check", s, f)

    def test_app_checks_after_start_and_pages_show_the_line(self):
        a = src("soe2", "app.py")
        self.assertIn("packcheck.FIRST_DELAY_MS, self.packs_autocheck", a)
        self.assertIn("packcheck.due()", a)
        from soe2 import crafthelper as CH
        self.assertEqual(CH.LIVE_EVERY, 24 * 3600)
        self.assertTrue(CH.pack_line("up to date").endswith("(up to date)"))
        self.assertTrue(CH.pack_line().startswith("Data pack: game patch"))


if __name__ == "__main__":
    unittest.main()
