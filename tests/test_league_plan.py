"""3.3.0 League Plan redraw (owner's mockups, 2026-11-23): one ordered list, Next up, goals counted from the game's
log, Wealth, Map Profit and the Stockpile; no phases, no Farm plan; the Stockpile on Exchange Rates; the campaign
route card's count and filter.

    DISPLAY=:99 python3.12 -m unittest tests.test_league_plan          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
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
    def test_phases_and_farms_become_one_list(self):
        SETTINGS["focus"] = {"phase": "maps", "now": "c",
                             "goals": [{"id": "a", "text": "Long one", "phase": "long", "done": False},
                                       {"id": "b", "text": "Start one", "phase": "start", "done": False},
                                       {"id": "c", "text": "On the overlay", "phase": "maps", "done": False}],
                             "farms": [{"strat": "s1", "name": "Breach", "secs": 7200},
                                       {"strat": "s2", "name": "Old", "done": True}],
                             "stockpile": [{"name": "Divine Orb", "goal": 5, "have": 0}]}
        f = F.cfg()
        self.assertEqual([g["text"] for g in f["goals"]],
                         ["On the overlay", "Start one", "Long one", "Farm Breach", F.STOCK_TEXT])
        for k in ("phase", "now", "farms"):
            self.assertNotIn(k, f)
        farm = f["goals"][3]
        self.assertEqual(F.progress_text(farm), "2 hours so far", "the time on it is kept")
        self.assertEqual(F.current()["id"], "c")
        again = [g["id"] for g in F.cfg()["goals"]]
        self.assertEqual(again, [g["id"] for g in f["goals"]], "once only")

    def test_old_3_2_goals_still_count(self):
        SETTINGS["focus"] = {"goals": [{"id": "a", "text": "Hit 90", "phase": "start", "done": False,
                                        "target_kind": "level", "target": 90.0}]}
        F.state()["levels"], F.state()["last_char"] = {"Me": 74}, "Me"
        self.assertEqual(F.progress_text(F.goal("a")), "Level 74 of 90")


class Goals(Fresh):
    def test_words(self):
        for kind, n, ref, words in (("level", 90, None, "Level 90"), ("campaign", 1, None, "Finish the campaign"),
                                    ("act_done", 2, None, "Finish act 2"), ("reach_maps", 1, None, "Reach maps"),
                                    ("maps", 100, None, "Run 100 maps"), ("tier", 15, None, "Reach tier 15 maps"),
                                    ("boss", 1, "The Burning Monolith", "Kill the Arbiter of Ash"),
                                    ("boss", 3, "Dark Domain", "Beat Dark Domain 3 times"),
                                    ("networth", 10, None, "Reach a net worth of 10 divine"),
                                    ("divhour", 3, None, "Make 3 div an hour"),
                                    ("farm", 10, "Delirium T15", "Farm Delirium T15 for 10 hours"),
                                    ("farm", None, "Delirium T15", "Farm Delirium T15")):
            self.assertEqual(F.goal_words(kind, n, ref), words)
            self.assertNotIn("(", words)

    def test_start_plan_and_next_up(self):
        gs = F.use_start_plan()
        self.assertEqual([g["text"] for g in gs], F.start_plan_words())
        self.assertEqual(len(gs), 6)
        self.assertEqual(F.current()["text"], "Finish the campaign")
        self.assertEqual(F.counts(), (0, 6))
        self.assertEqual(F.line_text(), ("Finish the campaign", 0.0))

    def test_order_skip_and_remove(self):
        a, b, c = F.add_goal("One"), F.add_goal("Two"), F.add_goal("Three")
        self.assertTrue(F.move_goal(c["id"], -1))
        self.assertEqual([g["text"] for g in F.cfg()["goals"]], ["One", "Three", "Two"])
        self.assertFalse(F.move_goal(a["id"], -1), "already first")
        self.assertEqual(F.skip(a["id"])["text"], "Three", "the goal after it is Next up")
        self.assertEqual(F.current(time.time() + 2 * 86400)["text"], "One", "until tomorrow")
        F.skip(c["id"]), F.skip(b["id"])
        self.assertEqual(F.current()["text"], "One", "all skipped: the first again")
        F.remove_goal(a["id"])
        self.assertEqual(len(F.cfg()["goals"]), 2)
        self.assertIsNone(F.add_goal("   "), "an empty goal is not added")

    def test_log_ticks_levels_maps_tiers_and_bosses(self):
        lvl, maps = F.add_goal(kind="level", target=20), F.add_goal(kind="reach_maps")
        tier = F.add_goal(kind="tier", target=15)
        boss = F.add_goal(kind="boss", target=1, ref_name="The Burning Monolith")
        run = F.add_goal(kind="maps", target=2)
        F.log_event("level", {"who": "Me", "level": 20}, None)
        self.assertTrue(lvl["done"] and lvl["auto_done"])
        F.log_event("area", {"area": "MapRugosa", "seed": 5, "level": 70}, "map")
        self.assertTrue(maps["done"])
        self.assertEqual(F.progress_text(tier), "Tier 6 of 15")
        self.assertEqual(F.progress_text(boss), "Not yet")
        F.log_event("area", {"area": "MapRugosa", "seed": 5, "level": 70}, "map")
        self.assertEqual(F.progress_text(run), "1 of 2 maps", "back through the portal is the same map")
        F.log_event("area", {"area": "MapUberBoss_Monolith", "seed": 9, "level": 79}, "map")
        self.assertTrue(boss["done"], "a run of its arena")
        self.assertTrue(tier["done"] and run["done"])
        kinds = [p["kind"] for p in F.state()["pending"]]
        self.assertIn("reached", kinds)

    def test_an_unticked_goal_stays_unticked(self):
        boss = F.add_goal(kind="boss", target=1, ref_name="The Burning Monolith")
        F.log_event("area", {"area": "MapUberBoss_Monolith", "seed": 9, "level": 79}, "map")
        self.assertTrue(boss["done"])
        F.set_done(boss["id"], False)
        F.check_goals()
        self.assertFalse(boss["done"], "the boss won: the app doesn't tick it again")

    def test_net_worth_from_wealth(self):
        g = F.add_goal(kind="networth", target=10)
        with mock.patch.object(F, "net_worth", lambda: (None, None)):
            self.assertEqual(F.progress_text(g), "Nothing counted in Wealth yet")
            self.assertEqual(F.source_text(g), "")
        with mock.patch.object(F, "net_worth", lambda: (6.2, time.time() - 2 * 3600)):
            self.assertEqual(F.progress_text(g), "6.2 of 10 div")
            self.assertEqual(F.source_text(g), "from Wealth · last read 2 hours ago")
            self.assertAlmostEqual(F.frac(g), 0.62)
        with mock.patch.object(F, "net_worth", lambda: (8930.4, time.time())):
            self.assertEqual(F.progress_text(g), "8,930 of 10 div", "never 8.93e+03")
        self.assertEqual([F.num(x) for x in (0.35, 2.1, 50, 1234567)], ["0.35", "2.1", "50", "1,234,567"])
        with mock.patch.object(F, "net_worth", lambda: (12.0, time.time())):
            self.assertEqual(F.check_goals(), [g])

    def test_div_an_hour_from_map_profit(self):
        g = F.add_goal(kind="divhour", target=3)
        from soe2 import mapprofit as MP
        runs = [{"t": i, "secs": 600, "div": 0.35} for i in range(14)]
        with mock.patch.object(MP, "log_read", lambda since=0: runs):
            self.assertAlmostEqual(F.div_hour()[0], 2.1)
            self.assertEqual(F.progress_text(g), "2.1 div an hour over your last 10 maps")
        with mock.patch.object(MP, "log_read", lambda since=0: []):
            self.assertEqual(F.progress_text(g), "No maps in Map Profit yet")

    def test_farm_counts_hours_while_next_up(self):
        g = F.add_goal(kind="farm", target=1, ref="s1", ref_name="Delirium T15")
        t = 1_000_000.0
        F.log_event("area", {"area": "MapRugosa", "seed": 1, "level": 70}, "map", now=t)
        F.log_event("area", {"area": "MapRugosa", "seed": 2, "level": 70}, "map", now=t + 540)
        self.assertEqual(g["secs"], 540)
        F.log_event("area", {"area": "x", "seed": 1}, "town", now=t + 9000)
        self.assertEqual(g["secs"], 540, "a long gap is not play")
        g["secs"] = 3600
        self.assertEqual(F.check_goals(), [g])

    def test_stock_up_follows_the_stockpile(self):
        F.add_stock("Divine Orb", 5)
        g = next(x for x in F.cfg()["goals"] if x["target_kind"] == "stock")
        self.assertEqual(g["text"], F.STOCK_TEXT, "the first Stockpile item puts the goal on your plan")
        F.add_stock("Chaos Orb", 100)
        self.assertEqual(sum(1 for x in F.cfg()["goals"] if x["target_kind"] == "stock"), 1)
        self.assertEqual(F.progress_text(g), "0 of 2 bought")
        F.set_stock_have("Divine Orb", 5)
        self.assertEqual(F.progress_text(g), "1 of 2 bought")
        F.set_stock_have("Chaos Orb", 100)
        self.assertEqual(F.check_goals(), [g])


class Reminders(Fresh):
    def test_only_next_up_is_brought_back(self):
        a, b = F.add_goal("One"), F.add_goal(kind="level", target=90)
        now = time.time()
        F.state()["seen"], F.state()["where"] = now, "town"
        p = F.due(now, in_town=True, session=True)
        self.assertEqual(p, {"kind": "nudge", "goal": a["id"]})
        title, text, why, btns = F.poke_text(p)
        self.assertEqual((title, text), ("NEXT UP", "One"))
        self.assertEqual([k for k, _l in btns], ["ok", "snooze", "done"], "a goal you tick can be ticked from it")
        self.assertIn("back in town", why)
        self.assertIsNone(F.due(now + 60, in_town=True, session=True), "not again within 3 hours")
        F.set_done(a["id"])
        p = F.due(now + 4 * 3600, in_town=True, session=True)
        self.assertEqual(p["goal"], b["id"])
        self.assertEqual([k for k, _l in F.poke_text(p)[3]], ["ok", "snooze"])

    def test_not_in_a_map(self):
        F.add_goal("One")
        self.assertIsNone(F.due(time.time(), in_town=False, session=True))


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Page(Fresh):
    def setUp(self):
        super().setUp()
        import tkinter as tk
        from soe2.plan_page import GamePlanPage
        self.root = tk.Tk()
        self.root.withdraw()

        class Host(GamePlanPage):
            pass
        h = self.h = Host()
        h.root = self.root
        h.gp_overlay = mock.Mock()
        h.focus_test = h.focus_history = lambda: None
        h.shell = mock.Mock()
        self.page = h.build_game_plan(self.root)
        self.page.pack()

    def tearDown(self):
        self.root.destroy()
        super().tearDown()

    def test_first_open_then_the_start_plan(self):
        h = self.h
        self.assertEqual(h.gp_start_sec.winfo_manager(), "pack")
        self.assertEqual(h.gp_plan_sec.winfo_manager(), "")
        h.gp_use_start()
        self.assertEqual(h.gp_start_sec.winfo_manager(), "")
        self.assertEqual(h.gp_next_sec.winfo_manager(), "pack")
        self.assertEqual(h._gp_done_lbl.cget("text"), "0 of 6 done")

    def test_add_is_greyed_until_the_goal_is_whole(self):
        h = self.h
        h.gp_add_open()
        self.assertEqual(h.gp_adder.winfo_manager(), "pack")
        h.gp_kind_pick("level")
        self.assertTrue(h.gp_add_btn.instate(["disabled"]))
        self.assertEqual(h.gp_add_tip.text, "Type a level first.")
        h.gp_num.set("90")
        self.assertFalse(h.gp_add_btn.instate(["disabled"]))
        self.assertEqual(h.gp_reads.cget("text"), "Level 90")
        self.assertFalse(h._gp_digits_ok("101"), "a level stops at 100")
        self.assertFalse(h._gp_digits_ok("9a"))
        g = h.gp_add_goal()
        self.assertEqual(g["text"], "Level 90")
        self.assertEqual(h.gp_adder.winfo_manager(), "", "back on the plan")

    def test_every_kind_can_be_added(self):
        h = self.h
        h.gp_kind_pick("act")
        self.assertEqual(h.gp_add_goal()["text"], "Finish the campaign")
        h.gp_kind_pick("act"), h.gp_pick.set("Act 2")
        self.assertEqual(h.gp_add_goal()["text"], "Finish act 2")
        h.gp_kind_pick("maps")
        self.assertEqual(h.gp_add_goal()["text"], "Reach maps")
        h.gp_kind_pick("maps"), h.gp_mode.set("Reach a tier"), h.gp_num.set("15")
        self.assertEqual(h.gp_add_goal()["text"], "Reach tier 15 maps")
        h.gp_kind_pick("boss")
        self.assertTrue(h.gp_add_btn.instate(["disabled"]))
        h.gp_pick.set(next(k for k, v in h.gp_bosses.items() if v == "The Burning Monolith"))
        self.assertEqual(h.gp_add_goal()["text"], "Kill the Arbiter of Ash")
        h.gp_kind_pick("networth"), h.gp_num.set("10")
        self.assertEqual(h.gp_add_goal()["text"], "Reach a net worth of 10 divine")
        h.gp_kind_pick("divhour"), h.gp_num.set("3")
        self.assertEqual(h.gp_add_goal()["text"], "Make 3 div an hour")
        h.gp_kind_pick("tick"), h.gp_new.set("Craft a staff")
        self.assertEqual(h.gp_add_goal()["text"], "Craft a staff")
        h.gp_kind_pick("stock")
        self.assertEqual(h.gp_add_goal()["text"], F.STOCK_TEXT)
        h.gp_kind_pick("stock")
        self.assertTrue(h.gp_add_btn.instate(["disabled"]), "only one Stock up goal")

    def test_ui_text_has_no_brackets(self):
        import tkinter as tk
        self.h.gp_use_start()
        for k, _n, _w in F.GOAL_KINDS:
            self.h.gp_kind_pick(k)

            def walk(w):
                if isinstance(w, tk.Label):
                    self.assertNotIn("(", str(w.cget("text")))
                for c in w.winfo_children():
                    walk(c)
            walk(self.page)


class CampaignCard(unittest.TestCase):
    def test_count(self):
        from soe2.campaign_ui import CampaignUI
        rows = [{"state": "done"}, {"state": "passed"}, {"state": "here"}, {"state": "todo"}]
        self.assertEqual(CampaignUI.camp_count_text(rows), "· 2 of 4 done")
        self.assertEqual(CampaignUI.camp_count_text([]), "")
        self.assertEqual([k for k, _n in CampaignUI.CAMP_FILTERS], ["all", "rewards", "bosses"])


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class CampaignLine(unittest.TestCase):
    def test_no_act_and_zone_line_on_top(self):
        import tkinter as tk
        from tkinter import font as tkfont
        from soe2.campaign_ui import CampaignUI
        root = tk.Tk()
        root.withdraw()
        try:
            f = tkfont.Font(root=root, family="TkDefaultFont", size=10)
            h = CampaignUI.__new__(CampaignUI)
            h._camp_fonts = lambda P, cv=None: (f, f, f, f)
            d = {"head": "ACT I · CLEARFELL ENCAMPMENT", "step": "2 / 16", "tip": "",
                 "do": "Talk to Renly and Una for their quests", "then": "Clearfell"}
            rows = h.camp_rows({}, 600, d)
            roles = [[r for _t, _f, r in row] for row in rows]
            self.assertNotIn("head", sum(roles, []))
            words = " ".join(t for row in rows for t, _f, _r in row)
            self.assertNotIn("CLEARFELL ENCAMPMENT", words)
            self.assertEqual(roles[0][-1], "step", "the step count sits on the first line")
            self.assertEqual(len(rows), 2)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
