"""3.2.0 League Plan rework (owner's mockups, 2026-11-22): Done when instead of Target, the build lock gone, a Farm plan,
reminders cut down, Snooze a real button. 3.2.1 (owner's checklist): in town only, numbers in range, a Done box, the
overlay mark in words, two strat lists and Done, next instead of a farm Goal, quiet hours of an hour or more.

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
        self.assertTrue(f["pokes"]["alert"])
        self.assertNotIn("farms", f["pokes"], "3.2.1: a farm has no Goal to remind you of")
        a, b = f["goals"]
        self.assertEqual(a["trigger"], "town", "once a week is gone")
        self.assertEqual(F.goal_target(a), (None, None), "the app can't see your divines: you tick it")
        self.assertEqual(F.goal_target(b), (None, None))
        self.assertEqual(f["farms"][0]["kind"], "none")
        self.assertIn("level 90", F.farm_text(f["farms"][0]), "its old words still show")


class DoneWhen(Fresh):
    def test_only_what_the_log_can_see(self):
        self.assertEqual([k for k, _n, _u in F.DONE_WHEN], ["tick", "level", "act", "reach_maps", "maps"])
        self.assertEqual([k for k, _n in F.TRIGGERS], ["town"], "3.2.1 owner: in town only")

    def test_old_triggers_become_town(self):
        SETTINGS["focus"] = {"lp_320": True, "pokes": {"farms": True},
                             "goals": [{"id": "a", "text": "x", "phase": "maps", "done": False, "trigger": "never"}],
                             "farms": [{"strat": "s", "name": "Breach", "kind": "level", "target": 95.0}]}
        f = F.cfg()
        self.assertEqual(f["goals"][0]["trigger"], "town")
        self.assertEqual((f["farms"][0]["kind"], f["farms"][0]["target"]), ("none", None))
        self.assertNotIn("farms", f["pokes"])

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


class Farms(Fresh):
    """3.2.1 owner: no Goal - Done, next moves you on; the one you're on shows its time and maps."""
    def test_done_next_moves_you_on(self):
        F.cfg()
        a = F.add_farm("s1", "Breach", src="Community")
        b = F.add_farm("s2", "Ritual", src="Official")
        self.assertIs(F.farm_now(), a)
        self.assertIs(F.farm_done(), b)
        self.assertTrue(a["done"])
        self.assertIs(F.farm_now(), b)
        self.assertIsNone(F.farm_done())
        self.assertIsNone(F.farm_now())

    def test_hours_and_maps_on_the_one_youre_on(self):
        F.cfg()
        a = F.add_farm("s1", "Breach")
        b = F.add_farm("s2", "Ritual")
        t = 1_800_000_000.0
        for i in range(8):                               # 8 log events 8 minutes apart: 56 minutes of play
            F.log_event("area", {"area": "X", "seed": i}, "other", now=t + i * 480)
        F.log_event("area", {"area": "MapA", "seed": 20}, "map", now=t + 8 * 480)
        self.assertFalse(a.get("done"), "no Goal: nothing moves you on by itself")
        self.assertEqual(F.farm_text(a), "1.1 hours · 1 maps on it so far · from the game's log")
        self.assertEqual(F.farm_text(b), "", "not the one you're on")

    def test_a_gap_isnt_play(self):
        F.cfg()
        a = F.add_farm("s1", "Breach")
        F.log_event("area", {"area": "X", "seed": 1}, "other", now=1000.0)
        F.log_event("area", {"area": "X", "seed": 2}, "other", now=1000.0 + 3 * 3600)     # the game was closed
        self.assertEqual(a["secs"], 0.0)

    def test_farm_on_the_overlay_line(self):
        F.cfg()
        F.add_goal("Level to 90", "start", "town")
        F.add_farm("s1", "Breach")
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
        for gone in ("_gp_lock", "Build lock", "Drill sergeant", "Target", "Or your own", "Until", "Remind me",
                     "gp_f_kind", "Reminds you"):
            self.assertNotIn(gone, src.split('"""', 2)[2], gone)
        for word in ("Done when", "Snooze lasts", "An alert in-game", "No reminders from", "+ Add goal",
                     "Make one in Farming Strategies ›", "Show on overlay", "✓ On the overlay", "My own strat",
                     "Done, next ›", "☐ Done"):
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
        self.assertIn("1 to 100", h.gp_target_note.cget("text"))
        h.gp_new.set("Level to 90")
        h.gp_new_target.set("90")
        g = h.gp_add_goal()
        self.assertEqual(F.goal_target(g), ("level", 90.0))
        self.assertEqual(g["trigger"], "town", "no Remind me: always in town")

    def test_numbers_only_and_in_range(self):
        h = self.h
        h.gp_new_tkind.set("My character reaches level")
        h.gp_target_hint()
        self.assertTrue(h._gp_digits_ok("95"))
        self.assertFalse(h._gp_digits_ok("101"))
        self.assertFalse(h._gp_digits_ok("9a"))
        self.assertTrue(h._gp_digits_ok(""))
        h.gp_new_tkind.set("I've run maps")
        h.gp_target_hint()
        self.assertTrue(h._gp_digits_ok("1000"))
        self.assertFalse(h._gp_digits_ok("1001"))
        h.gp_new_tkind.set("I reach act")
        h.gp_target_hint()
        self.assertEqual(h.gp_new_act.winfo_manager(), "pack", "acts are a list")
        self.assertFalse(h.gp_new_target_e.winfo_manager())
        self.assertEqual(list(h.gp_new_act.cget("values")), ["1", "2", "3", "4", "5", "6"])
        h.gp_new.set("Finish the campaign")
        h.gp_new_target.set("6")
        self.assertEqual(F.goal_target(h.gp_add_goal()), ("act", 6.0))

    def test_done_box_and_overlay_mark(self):
        h = self.h
        a, b = F.add_goal("One", "start", "town"), F.add_goal("Two", "start", "town")
        h.gp_fill()
        self.root.update()
        self.assertTrue(h._gp_on_lbls[a["id"]].winfo_ismapped(), "the shown one: orange words, no button")
        self.assertEqual(h._gp_on_lbls[a["id"]].cget("text"), "✓ On the overlay")
        self.assertFalse(h._gp_now_btns[a["id"]].winfo_ismapped())
        self.assertEqual(h._gp_now_btns[b["id"]].cget("text"), "Show on overlay")
        F.cfg()["on"] = False
        seen = []
        h.focus_set_on = lambda on: (seen.append(on), F.cfg().update(on=on))
        h._gp_now_btns[b["id"]].invoke()
        self.root.update()
        self.assertEqual(F.cfg()["now"], b["id"])
        self.assertEqual(seen, [True], "Show on overlay turns the plan's overlay line on")
        self.assertTrue(h._gp_on_lbls[b["id"]].winfo_ismapped())
        self.assertFalse(h._gp_on_lbls[a["id"]].winfo_ismapped())
        self.assertTrue(h._gp_now_btns[a["id"]].winfo_ismapped())

    def test_strat_lists_and_done_next(self):
        h = self.h
        from soe2 import moneymakers as MM
        h.mm_board = [{"id": "c1", "name": "Abyss lineage", "origin": "board"}]
        h.mm_official = {"strats": [{"id": "o1", "name": "Abyss T15"}]}
        with mock.patch.object(MM, "all_strats", lambda: [{"id": "m1", "name": "My Breach", "origin": "mine"}]):
            h.gp_farm_choices()
        self.assertEqual(list(h.gp_f_box.cget("values")), ["Abyss lineage  ·  Community", "Abyss T15  ·  Official"])
        self.assertEqual(list(h.gp_f_mine_box.cget("values")), ["My Breach  ·  Mine"])
        self.assertFalse(h.gp_f_none.winfo_manager(), "you have one: a list, no pointer")
        with mock.patch.object(MM, "all_strats", lambda: []):
            h.gp_farm_choices()
        self.assertEqual(h.gp_f_none.winfo_manager(), "grid", "none of your own: Make one in Farming Strategies")
        self.assertFalse(h.gp_f_mine_box.winfo_manager())
        a = h.gp_add_farm("Abyss lineage  ·  Community")
        h.gp_f_pick.set("Abyss T15  ·  Official")
        b = h.gp_add_farm()
        self.assertEqual((a["name"], a["src"], a["kind"]), ("Abyss lineage", "Community", "none"))
        h.gp_farm_next()
        self.assertTrue(a["done"])
        self.assertIs(F.farm_now(), b)

    def test_reminder_settings(self):
        h = self.h
        h.gp_quiet[0].set("01:00")
        h.gp_quiet[1].set("06:00")
        self.assertEqual(F.cfg()["pokes"]["quiet"], [1, 6])
        h.gp_quiet[1].set("01:00")
        self.assertEqual(F.cfg()["pokes"]["quiet"], [1, 2], "the same hour: the end moves on one - at least an hour")
        self.assertNotIn("01:00", list(h.gp_quiet_to.cget("values")))
        self.assertNotIn("farms", h.gp_poke_vars, "no farm Goal to remind you of")
        h.gp_poke_vars["alert"].set(False)
        h.gp_pokes_save()
        self.assertFalse(F.cfg()["pokes"]["alert"])
        shown = h.focus_show({"kind": "checkin", "goal": None})
        self.assertIsNone(shown, "An alert in-game off: no window")


if __name__ == "__main__":
    unittest.main()
