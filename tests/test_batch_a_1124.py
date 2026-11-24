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



class BatchB(unittest.TestCase):
    """3.3.0 owner, wording: helper lines say what, the Stockpile reminds by itself, Regex option renamed."""

    def test_helper_lines_are_short_and_say_what(self):
        from soe2 import alerts_page as AP
        for k, line in AP.HELPER_BLURBS.items():
            self.assertLessEqual(len(line), 60, k)
            self.assertNotIn("Press", line, k)
            self.assertNotIn("(", line, k)
        self.assertEqual(AP.HELPER_BLURBS["breach"], "Better alerts for full Hiveblood.")

    def test_reading_helpers_still_say_where_to_press(self):
        from soe2 import alerts_page as AP
        for k in ("ritual", "remnant", "desecrate", "topup", "mapprofit", "temple", "sekhemas"):
            self.assertIn(k, AP.LOOK_HELPERS)
            self.assertIn("Ctrl+Shift+R", AP.helper_tip(k, "Ctrl+Shift+R"), k)

    def test_no_helper_word_on_the_helpers_list(self):
        from soe2 import alerts_page as AP
        self.assertEqual(AP.helper_short("Temple Helper"), "Temple")
        self.assertEqual(AP.helper_short("Campaign Helper"), "Campaign")
        self.assertEqual(AP.helper_short("Trial of the Sekhemas"), "Trial of the Sekhemas")
        self.assertIn("text=helper_short(names[key])", inspect.getsource(AP))

    def test_regex_option_is_named_for_what_it_gives(self):
        from soe2 import regex_page, regex
        src = inspect.getsource(regex_page)
        self.assertNotIn('"round10", "Round down to 10"', src)
        self.assertIn("so 37 becomes 30", src)
        self.assertIn("Shorter search", inspect.getsource(regex))

    def test_stockpile_switch_lives_on_the_stockpile(self):
        src = inspect.getsource(plan_page)
        self.assertIn('text="Tell me when an item drops under my price"', src)
        self.assertNotIn('"Stockpile items under your price"', src)


class StockpileRemindsAlone(unittest.TestCase):
    def setUp(self):
        from soe2 import focus as F
        import copy
        self.F = F
        self.was = copy.deepcopy(F.cfg()), copy.deepcopy(F.state())

    def tearDown(self):
        self.F.cfg().clear()
        self.F.cfg().update(self.was[0])
        self.F.state().clear()
        self.F.state().update(self.was[1])

    def go(self, on, prices_on, each=1.0):
        import time
        F = self.F
        f, st = F.cfg(), F.state()
        f["on"] = on
        f["pokes"].update(prices=prices_on, per_hour=2, quiet_on=False)
        f["stockpile"] = [{"name": "Cryptic Key", "goal": 100, "under": 10}]
        st.update(sent=[], pending=[], price_day={}, notoday_streak=0, where="town", seen=time.time())
        return F.due(time.time(), in_town=True, session=True, prices=lambda n: each, have=lambda n: 0)

    def test_with_league_plan_off(self):
        p = self.go(False, True)
        self.assertEqual((p or {}).get("kind"), "price")

    def test_switch_off_means_no_reminder(self):
        self.assertIsNone(self.go(False, False))

    def test_not_cheap_no_reminder_and_no_plan_nudges_while_off(self):
        self.assertIsNone(self.go(False, True, each=50.0))


if __name__ == "__main__":
    unittest.main()
