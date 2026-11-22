"""3.2.0 League Plan rework (owner's mockups, 2026-11-22): Done when instead of Target, the build lock gone, a Farm plan
with a Goal the game's log can see, reminders cut down, Snooze a real button.

    DISPLAY=:99 python3.12 -m unittest tests.test_league_plan          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-plan-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import focus as F                       # noqa: E402
from soe2.config import SETTINGS                  # noqa: E402


class Fresh(unittest.TestCase):
    def setUp(self):
        self._old = SETTINGS.get("focus")
        SETTINGS["focus"] = {}
        self.p = mock.patch.object(F, "save", lambda: None)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        if self._old is None:
            SETTINGS.pop("focus", None)
        else:
            SETTINGS["focus"] = self._old


class Migration(Fresh):
    def test_lock_tone_and_always_on_switches_are_gone(self):
        SETTINGS["focus"] = {"lock": {"on": True, "character": "Me"},
                             "pokes": {"tone": "Drill sergeant", "town_only": False, "session_only": False,
                                       "why": False, "quieter": False, "per_hour": 3},
                             "goals": [{"id": "a", "text": "Have 10 div", "phase": "start", "done": False,
                                        "trigger": "weekly", "target_kind": "div", "target": 10.0},
                                       {"id": "b", "text": "Old div goal", "phase": "start", "done": False,
                                        "trigger": "town", "target_div": 5.0}],
                             "farms": [{"strat": None, "name": "Breach", "until": "level 90"}]}
        f = F.cfg()
        self.assertNotIn("lock", f)
        for k in F.GONE_POKES:
            self.assertNotIn(k, f["pokes"])
        self.assertEqual(f["pokes"]["per_hour"], 3, "your own limits stay")
        self.assertTrue(f["pokes"]["alert"] and f["pokes"]["farms"])
        a, b = f["goals"]
        self.assertEqual(a["trigger"], "town", "once a week is gone")
        self.assertEqual(F.goal_target(a), (None, None), "the app can't see your divines: you tick it")
        self.assertEqual(F.goal_target(b), (None, None))
        self.assertEqual(f["farms"][0]["kind"], "none")
        self.assertIn("level 90", F.farm_text(f["farms"][0]), "its old words still show")


class DoneWhen(Fresh):
    def test_only_what_the_log_can_see(self):
        self.assertEqual([k for k, _n, _u in F.DONE_WHEN], ["tick", "level", "act", "reach_maps", "maps"])
        self.assertEqual([k for k, _n in F.TRIGGERS], ["town", "phase", "never"])

    def test_level_goal_ticks_itself_and_says_so(self):
        F.cfg()
        g = F.add_goal("Level my Witch to 90", "start", "town", target_kind="level", target=90)
        F.log_event("level", {"who": "Witchy", "level": 74})
        self.assertEqual(F.progress_text(g), "Level 74 of 90")
        self.assertFalse(g["done"])
        F.log_event("level", {"who": "Witchy", "level": 90})
        self.assertTrue(g["done"] and g["auto_done"])
        self.assertEqual(F.state()["pending"][-1]["kind"], "reached")
        title, text, why, _b = F.poke_text(F.state()["pending"][-1])
        self.assertEqual(title, "GOAL REACHED")
        self.assertIn("log", why)

    def test_reach_maps_and_maps_run(self):
        F.cfg()
        g = F.add_goal("Get to maps", "start", "town", target_kind="reach_maps")
        m = F.add_goal("Run 2 maps", "maps", "town", target_kind="maps", target=2)
        self.assertEqual(F.progress_text(g), "Not in maps yet")
        F.log_event("area", {"area": "MapA", "seed": 1}, "map")
        self.assertTrue(g["done"])
        self.assertEqual(F.progress_text(m), "1 of 2 maps")
        F.log_event("area", {"area": "Hideout", "seed": 2}, "hideout")
        F.log_event("area", {"area": "MapB", "seed": 3}, "map")
        self.assertTrue(m["done"])

    def test_act_from_the_campaign_helper(self):
        F.cfg()
        g = F.add_goal("Finish act 2", "start", "town", target_kind="act", target=3)
        with mock.patch.object(F, "act_now", lambda: 2):
            self.assertEqual(F.progress_text(g), "Act 2 of 3")
        with mock.patch.object(F, "act_now", lambda: 3):
            F.check_goals()
        self.assertTrue(g["done"])

    def test_tick_it_myself_never_ticks_itself(self):
        F.cfg()
        g = F.add_goal("Buy a Grand Spectrum", "start", "town")
        F.log_event("level", {"who": "Witchy", "level": 99})
        self.assertFalse(g["done"])
        self.assertEqual(F.progress_text(g), "")


class FarmGoal(Fresh):
    def test_hours_count_from_the_log_and_move_you_on(self):
        F.cfg()
        a = F.add_farm("s1", "Breach", "hours", 1, src="Community")
        b = F.add_farm("s2", "Ritual", "none", src="Official")
        self.assertIs(F.farm_now(), a)
        t = 1_800_000_000.0
        for i in range(8):                               # 8 log events 8 minutes apart: 56 minutes of play
            F.log_event("area", {"area": "X", "seed": i}, "other", now=t + i * 480)
        self.assertLess(a["secs"], 3600)
        self.assertFalse(a.get("done"))
        F.log_event("area", {"area": "X", "seed": 9}, "other", now=t + 8 * 480)
        self.assertTrue(a["done"], "an hour of play")
        self.assertIs(F.farm_now(), b)
        pk = F.state()["pending"][-1]
        self.assertEqual((pk["kind"], pk["next"]), ("farm", "Ritual"))
        self.assertIn("Next on your plan: Ritual", F.poke_text(pk)[1])

    def test_a_gap_isnt_play(self):
        F.cfg()
        a = F.add_farm("s1", "Breach", "hours", 1)
        F.log_event("area", {"area": "X", "seed": 1}, "other", now=1000.0)
        F.log_event("area", {"area": "X", "seed": 2}, "other", now=1000.0 + 3 * 3600)     # the game was closed
        self.assertEqual(a["secs"], 0.0)

    def test_level_maps_and_words(self):
        F.cfg()
        a = F.add_farm("s1", "Breach", "level", 95)
        F.log_event("level", {"who": "Witchy", "level": 93})
        self.assertEqual(F.farm_text(a), "Goal: level 95 · now 93 · from the game's log")
        F.add_farm("s2", "Maps", "maps", 3)
        self.assertEqual(F.farm_text(F.cfg()["farms"][1]), "Goal: 3 maps · counted once it's NOW")

    def test_farm_on_the_overlay_line(self):
        F.cfg()
        F.add_goal("Level to 90", "start", "town")
        F.add_farm("s1", "Breach", "none")
        self.assertEqual(F.line_text()[0], "Level to 90 · farm: Breach")


class Reminders(Fresh):
    def test_always_in_town_while_playing_and_why(self):
        F.cfg()
        F.add_goal("Level to 90", "start", "town")
        now = 1_800_000_000.0
        F.log_event("area", {"area": "Map", "seed": 1}, "map", now=now)
        self.assertIsNone(F.due(now + 5, in_town=True, session=False), "in a map: never")
        F.log_event("area", {"area": "Town", "seed": 2}, "town", now=now + 10)
        poke = F.due(now + 20, in_town=False, session=False)
        self.assertEqual(poke["kind"], "milestone")                          # (the first map's)
        self.assertIsNone(F.due(now + 20 + 2 * F.PLAYING, in_town=True, session=False), "not playing: never")

    def test_snooze_button_and_gentle(self):
        F.cfg()
        g = F.add_goal("Level to 90", "start", "town")
        title, _text, why, buttons = F.poke_text({"kind": "nudge", "goal": g["id"]})
        self.assertEqual(title, "A NUDGE FROM YOUR PLAN")
        self.assertTrue(why.startswith("Why now:"))
        self.assertEqual([k for k, _l in buttons], ["done", "snooze", "nottoday"])
        self.assertEqual(dict(buttons)["snooze"], "Snooze · 60 min")
        F.answer({"kind": "nudge", "goal": g["id"]}, "snooze", now=1000.0)
        self.assertEqual(g["snooze"], 1000.0 + 3600)

    def test_quiet_hours_are_yours(self):
        pk = {"quiet_on": True, "quiet": [1, 5]}
        at = time.mktime((2026, 11, 22, 3, 0, 0, 0, 0, -1))
        self.assertTrue(F._quiet(pk, at))
        self.assertFalse(F._quiet(dict(pk, quiet=[22, 1]), at))


class PageWords(unittest.TestCase):
    def test_no_lock_no_tone_and_the_words(self):
        src = open(os.path.join(ROOT, "soe2", "plan_page.py"), encoding="utf-8").read()
        for gone in ("_gp_lock", "Build lock", "Drill sergeant", "Target", "Or your own", "Until"):
            self.assertNotIn(gone, src.split('"""', 2)[2], gone)
        for word in ("Done when", "Snooze lasts", "An alert in-game", "No reminders from", "+ Add goal",
                     "Make one in Farming Strategies ›", "Show on overlay", "✓ On the overlay"):
            self.assertIn(word, src)


@unittest.skipIf(os.environ.get("DISPLAY") is None and sys.platform != "win32", "no display")
class Page(Fresh):
    def setUp(self):
        super().setUp()
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, self.root)
        S.setup_style(self.root)
        from soe2.plan_page import GamePlanPage, FocusPokes

        class Host(GamePlanPage, FocusPokes):
            pass
        h = Host.__new__(Host)
        h.root = self.root
        h.gp_overlay = lambda: None
        h.focus_test = lambda: None
        h.mm_board, h.mm_official = [], {}
        self.h = h
        self.page = h.build_game_plan(self.root)
        self.page.pack()
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def test_done_when_shows_a_number_only_when_it_needs_one(self):
        h = self.h
        self.assertFalse(h.gp_new_target_e.winfo_manager())
        h.gp_new_tkind.set("My character reaches level")
        h.gp_target_hint()
        self.assertEqual(h.gp_new_target_e.winfo_manager(), "pack")
        self.assertEqual(h.gp_new_target_lbl.cget("text"), "Level")
        h.gp_new.set("Level to 90")
        h.gp_new_target.set("90")
        g = h.gp_add_goal()
        self.assertEqual(F.goal_target(g), ("level", 90.0))

    def test_overlay_button_is_real_and_the_shown_one_isnt_a_button(self):
        h = self.h
        a, b = F.add_goal("One", "start", "town"), F.add_goal("Two", "start", "town")
        h.gp_fill()
        self.root.update()
        self.assertEqual(h._gp_now_btns[a["id"]].cget("text"), "✓ On the overlay")
        self.assertTrue(h._gp_now_btns[a["id"]].instate(["disabled"]))
        self.assertEqual(h._gp_now_btns[b["id"]].cget("text"), "Show on overlay")
        h._gp_now_btns[b["id"]].invoke()
        self.assertEqual(F.cfg()["now"], b["id"])
        self.assertEqual(h._gp_now_btns[b["id"]].cget("text"), "✓ On the overlay")

    def test_strat_picker_lists_mine_community_official(self):
        h = self.h
        from soe2 import moneymakers as MM
        h.mm_board = [{"id": "c1", "name": "Abyss lineage", "origin": "board"}]
        h.mm_official = {"strats": [{"id": "o1", "name": "Abyss T15"}]}
        with mock.patch.object(MM, "all_strats", lambda: [{"id": "m1", "name": "My Breach", "origin": "mine"}]):
            vals = h.gp_farm_choices()
        self.assertEqual(vals, ["My Breach  ·  Mine", "Abyss lineage  ·  Community", "Abyss T15  ·  Official"])
        self.assertFalse(h.gp_f_none.winfo_manager(), "you have one: no pointer")
        with mock.patch.object(MM, "all_strats", lambda: []):
            h.gp_farm_choices()
        self.assertEqual(h.gp_f_none.winfo_manager(), "grid", "none of your own: Make one in Farming Strategies")
        h.gp_f_kind.set("My character reaches level")
        h.gp_farm_hint()
        h.gp_f_target.set("95")
        row = h.gp_add_farm("Abyss lineage  ·  Community")
        self.assertEqual((row["name"], row["src"], row["kind"], row["target"]),
                         ("Abyss lineage", "Community", "level", 95.0))

    def test_reminder_settings(self):
        h = self.h
        h.gp_quiet[0].set("01:00")
        h.gp_quiet[1].set("06:00")
        self.assertEqual(F.cfg()["pokes"]["quiet"], [1, 6])
        h.gp_poke_vars["alert"].set(False)
        h.gp_pokes_save()
        self.assertFalse(F.cfg()["pokes"]["alert"])
        shown = h.focus_show({"kind": "checkin", "goal": None})
        self.assertIsNone(shown, "An alert in-game off: no window")


if __name__ == "__main__":
    unittest.main()
