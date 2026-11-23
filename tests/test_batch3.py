"""3.3.0 batch 3 (owner): the honest online count on the status bar, Top Movers, Worth a look and the one-time
sharing question on the Dashboard.

    DISPLAY=:99 python3.12 -m unittest tests.test_batch3          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-b3-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import dashboard_page as DP     # noqa: E402
from soe2 import movers as MV             # noqa: E402
from soe2 import usage as US              # noqa: E402
from soe2.config import SETTINGS          # noqa: E402

LINES = [("a", "Alpha Orb", 2.0, 900), ("b", "Beta Orb", 0.5, 800), ("c", "Gamma Orb", 0.1, 700),
         ("d", "Delta Orb", 0.02, 600), ("thin", "Thin Orb", 5.0, 1), ("none", "Unsold Orb", 5.0, 0)]


def prices(now=None):
    p = types.SimpleNamespace(league="L", ts=now or time.time(), ok=True)
    p.parts = {"Currency": {"lines": [list(x) for x in LINES]}}
    p.by_slug = {c: (v, "poe.ninja Currency") for c, _n, v, _vol in LINES}
    p.trend_by_slug = {"a": (0, [0, 0, 0, 0, 0, 0, 10.0]), "b": (0, [0, 0, 0, 0, 0, 20.0, 8.0]),
                       "c": (0, [0, 0, 0, 0, 0, 0, 0.1]), "thin": (0, [0, 0, 0, 0, 0, 0, 300.0])}
    return p


class Movers(unittest.TestCase):
    def test_daily_is_yesterday_against_today(self):
        d = MV.daily(prices())
        self.assertEqual([r["name"] for r in d["up"]], ["Alpha Orb"])
        self.assertAlmostEqual(d["up"][0]["pct"], 10.0)
        self.assertEqual([r["name"] for r in d["down"]], ["Beta Orb"])
        self.assertAlmostEqual(d["down"][0]["pct"], -10.0)
        self.assertEqual(d["up"][0]["how"], "poe.ninja's price yesterday against today: 1.82 to 2 div.")
        names = [r["name"] for r in d["up"] + d["down"]]
        self.assertNotIn("Thin Orb", names, "a thin market is left out")
        self.assertNotIn("Gamma Orb", names, "under half a percent is no move")

    def test_hourly_needs_a_read_an_hour_old(self):
        now = 2_000_000.0
        p = prices(now)
        with mock.patch.object(MV, "load_json", lambda f, d: []):
            self.assertIn("open for an hour", MV.hourly(p, now)["empty"])
        old = [{"ts": now - 3700, "league": "L", "v": {"a": 1.6, "b": 0.5, "c": 0.2, "d": 0.04}},
               {"ts": now - 600, "league": "L", "v": {"a": 99}}]
        with mock.patch.object(MV, "load_json", lambda f, d: old):
            h = MV.hourly(p, now)
        self.assertEqual([(r["name"], round(r["pct"])) for r in h["up"]], [("Alpha Orb", 25)])
        self.assertEqual([(r["name"], round(r["pct"])) for r in h["down"]], [("Gamma Orb", -50)], "Delta is in the thin half")
        self.assertEqual(h["up"][0]["how"], "The app's read 61 min ago against now: 1.6 to 2 div.")

    def test_note_keeps_reads_apart(self):
        saved = []
        with mock.patch.object(MV, "load_json", lambda f, d: list(saved[-1]) if saved else []), \
                mock.patch.object(MV, "save_json", lambda f, v: saved.append(v)):
            MV.note(prices(), now=1000.0)
            MV.note(prices(), now=1300.0)
            self.assertEqual(len(saved), 1, "two reads close together are one")
            MV.note(prices(), now=5000.0)
            self.assertEqual([h["ts"] for h in saved[-1]], [1000.0, 5000.0])
            MV.note(prices(), now=1000.0 + MV.KEEP + 4100)
            self.assertNotIn(1000.0, [h["ts"] for h in saved[-1]], "old reads are dropped")


class Online(unittest.TestCase):
    def test_the_line_and_what_it_counts(self):
        with mock.patch.object(US, "counts", lambda: None):
            self.assertEqual(US.line(), ("", ""))
        with mock.patch.object(US, "counts", lambda: (0, 340)):
            self.assertEqual(US.line(), ("", "340 this week"))
        with mock.patch.object(US, "counts", lambda: (1, 5)):
            self.assertEqual(US.line(), ("1 exile online", " · 5 this week"))
        with mock.patch.object(US, "counts", lambda: (1234, 5000)), mock.patch.object(US, "on", lambda: False):
            self.assertEqual(US.line(), ("1,234 exiles online", " · 5,000 this week"))
            tip = US.tip()
            self.assertIn("last 15 minutes", tip)
            self.assertIn("version 3.1 or newer", tip)
            self.assertIn("You are not counted", tip)
            self.assertNotIn("(", tip)
        with mock.patch.object(US, "counts", lambda: (2, 5)), mock.patch.object(US, "on", lambda: True):
            self.assertIn("You are counted.", US.tip())


class StashLine(unittest.TestCase):
    def test_it_says_when_and_invites_a_new_scan(self):
        now = 2_000_000.0
        self.assertEqual(DP.stash_line(None, now), ("", ""))
        fresh = {"total": 10.0, "today": 2.0, "ts": now - 1800}
        text, nudge = DP.stash_line(fresh, now)
        self.assertIn("on your last scan, 30 min ago", text)
        self.assertIn("▲ up", text)
        self.assertEqual(nudge, "", "just scanned: nothing to ask")
        text, nudge = DP.stash_line({"total": 10.0, "today": 0, "ts": now - 8 * 3600}, now)
        self.assertTrue(text.endswith("8 hours ago."))
        self.assertEqual(nudge, "Scan again to see today's gains")
        text, nudge = DP.stash_line({"total": 10.0, "today": 0, "ts": now - 2 * 86400}, now)
        self.assertIn("2 days ago", text)
        self.assertEqual(nudge, "Scan again to see what you've earned since")
        self.assertNotIn("no change", text)
        for w in ("haven't", "missed", "overdue", "should"):
            self.assertNotIn(w, text + nudge)


class Sharing(unittest.TestCase):
    def setUp(self):
        self.old = {k: SETTINGS.get(k) for k in ("share_prices", "dash_share_asked")}

    def tearDown(self):
        for k, v in self.old.items():
            SETTINGS.pop(k, None) if v is None else SETTINGS.__setitem__(k, v)

    def test_asked_once_while_sharing_is_off(self):
        SETTINGS["share_prices"] = False
        SETTINGS.pop("dash_share_asked", None)
        self.assertTrue(DP.share_prompt_due())
        app = mock.Mock()
        with mock.patch("soe2.config.save_json"):
            DP.share_prompt_answer(app, False)
        app.cm_set_sharing.assert_not_called()
        self.assertFalse(DP.share_prompt_due(), "No thanks is never asked again")
        SETTINGS.pop("dash_share_asked", None)
        DP.share_prompt_answer(app, True)
        app.cm_set_sharing.assert_called_once_with(True)
        SETTINGS["share_prices"] = True
        SETTINGS.pop("dash_share_asked", None)
        self.assertFalse(DP.share_prompt_due(), "not asked while you share")


class Worth(unittest.TestCase):
    def test_cards_then_what_is_off(self):
        from soe2 import features as FEAT
        with mock.patch.object(FEAT, "on", lambda k: True), mock.patch.object(FEAT, "helper_on", lambda k: True):
            items = DP.worth_items()
        self.assertEqual(len(items), len(DP.WORTH))
        self.assertEqual(items[0]["button"], "Open Leaderboards")
        plan = next(i for i in items if i["name"] == "League Plan")
        self.assertEqual(plan["head"], "Got ADHD? Lose track of your goals?")
        self.assertIn("one list", plan["body"])
        for it in items:
            text = " ".join((it["head"], it["body"], it["punch"], it["button"]))
            self.assertNotIn("(", text)
            for w in ("powerful", "unlock", "seamless", "you should", "must"):
                self.assertNotIn(w, text.lower())
        key = FEAT.ALL[0]["key"]
        with mock.patch.object(FEAT, "on", lambda k: k != key), mock.patch.object(FEAT, "helper_on", lambda k: False):
            more = DP.worth_items()
        heads = [i["head"] for i in more[len(DP.WORTH):]]
        self.assertIn(f"{FEAT.ALL[0]['name']} is switched off.", heads)

    def test_a_card_stays_long_enough_to_read(self):
        for it in DP.worth_items():
            secs = DP.worth_secs(it)
            self.assertGreaterEqual(secs, 14)
            self.assertLessEqual(secs, 30)
        long_one = max(DP.worth_items(), key=lambda i: len(i["body"]))
        short_one = min(DP.worth_items(), key=lambda i: len(i["body"] + i["head"] + i["punch"]))
        self.assertGreater(DP.worth_secs(long_one), DP.worth_secs(short_one))

    def test_it_turns_by_itself_but_not_while_paused(self):
        d = DP.Dashboard.__new__(DP.Dashboard)
        d.winfo_exists = lambda: True
        d.after = lambda ms, fn: "job"
        d.later = mock.Mock()
        d._worth_bar = mock.Mock()
        d._wl_box, d._wl_secs, d._wl_n, d._wl_i, d._wl_t, d._wl_job = (0, 0, 9, 9), 1.0, 8, 3, 0.0, None
        old = SETTINGS.get("dash_worth_off")
        SETTINGS["dash_worth_off"] = False
        try:
            d._worth_paused = lambda: True                  # the mouse is on it, or the app is in the background
            for _ in range(10):
                d._worth_tick()
            self.assertEqual((d._wl_i, d._wl_t), (3, 0.0))
            d.later.assert_not_called()
            d._worth_paused = lambda: False
            d._worth_tick()
            self.assertEqual(d._wl_i, 3)
            d._worth_bar.assert_called()
            d._worth_tick()
            self.assertEqual((d._wl_i, d._wl_t), (4, 0.0), "after its time, the next card")
            d.later.assert_called_once()
            d._worth_step(2)
            self.assertEqual(d._wl_i, 6, "a click on Up next jumps there")
            SETTINGS["dash_worth_off"] = True
            d._wl_job = None
            d._worth_tick()
            self.assertIsNone(d._wl_job, "hidden: nothing keeps running")
        finally:
            SETTINGS["dash_worth_off"] = old


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class TitleBar(unittest.TestCase):
    def test_the_chest_has_a_badge_that_only_changes_with_the_count(self):
        import tkinter as tk
        from soe2 import lineicons
        from soe2.drawer_page import DrawerStrip
        root = tk.Tk()
        root.withdraw()
        try:
            self.assertIn("M4 11v8.5h16V11", lineicons.ICONS["mark"], "the app's chest, not a diamond")
            s = DrawerStrip.__new__(DrawerStrip)
            s.mark, s._mark, s.online = tk.Canvas(root), None, None
            s.mark_tip = types.SimpleNamespace(text="")
            s.mark_paint = mock.Mock()
            s.set_online(12, "what it counts")
            self.assertEqual((s.online, s.mark_tip.text), (12, "what it counts"))
            s.mark_paint.assert_called_once()
            s.set_online(12, "what it counts")
            s.mark_paint.assert_called_once()
            s.set_online(0)
            self.assertIsNone(s.online)
            self.assertEqual([DrawerStrip.badge_text(n) for n in (None, 7, 999, 1000, 1540)],
                             ["", "7", "999", "1k", "1.5k"])
        finally:
            root.destroy()

    def test_the_status_bar_has_no_count(self):
        import inspect
        from soe2.app import App
        self.assertNotIn("online_chip", inspect.getsource(App))


if __name__ == "__main__":
    unittest.main()
