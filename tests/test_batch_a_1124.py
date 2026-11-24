"""3.3.0 owner, 24 Nov small fixes: League Plan order and limits, Overlay tab name, Leaderboards toolbar."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import plan_page, tracker_page, leaderboard_page, bulk_page  # noqa: E402


class BatchA(unittest.TestCase):
    def test_overlay_tab_is_appearance_and_old_links_still_land(self):
        T = tracker_page.TrackerPage if hasattr(tracker_page, "TrackerPage") else None
        src = inspect.getsource(tracker_page)
        self.assertIn('"Appearance", "Options", "Sessions")', src)
        self.assertIn('"Look": "Appearance"', src)
        self.assertNotIn('ovh_areas["Look"]', src)
        del T

    def test_plan_comes_before_next_up(self):
        src = inspect.getsource(plan_page)
        self.assertIn("want = [self.gp_plan_sec, self.gp_next_sec] if has", src)

    def test_reminder_numbers_have_limits(self):
        src = inspect.getsource(plan_page)
        self.assertIn('"per_hour", "At most", "reminders an hour", "0 turns them off, 12 at most", 0, 12', src)
        self.assertIn("480 at most", src)
        self.assertIn("max(lo, min(hi, int(n)))", src)

    def test_switch_words_and_background(self):
        src = inspect.getsource(plan_page)
        self.assertNotIn("Next up on the overlay, and reminders", src)
        self.assertIn('text="Overlay and reminders", variable=self.gp_on, style="Bar.TCheckbutton"', src)

    def test_export_is_not_beside_refresh(self):
        src = inspect.getsource(leaderboard_page)
        self.assertIn('ttk.Button(top3, text="Export my times…"', src)
        self.assertNotIn('ttk.Button(top2, text="Export my times…"', src)

    def test_empty_box_sits_on_the_list(self):
        self.assertIn("e.place(in_=self.tree, relx=0.5, rely=0.5", inspect.getsource(bulk_page))


if __name__ == "__main__":
    unittest.main()
