"""Farming Strategies, 3.0.6 (the approved mockups): Find and an opened strat.

  * the tablets' pictures ship with the app (pricecheck_page.TABLET_ICONS): icons() has them with no icons.json,
    a picture learned from a listing wins, and icon_learn saves only what was learned
  * each strat's picture is its mechanic's tablet (the generic one for crafting and the rest); no picture: the word
  * the numbers and how they were worked out: per hour (the middle of the estimate, its range, you), cost per run
    (the trade site's prices written out as a sum, else the author's estimate), profit per run, run time
  * the page: tabs Find | Strat Tracker (Lucrative Strats is gone - Quick tips fold into Find), the search box first,
    one orange button a screen (Run this strat), Quick tips closed by default with Copy grayed until a tip is
    picked, an empty state with one button, the Drawer's Filters ▾, an opened strat and ‹ All strats

    python3.12 -m unittest tests.test_strats_find          (or tests/runall.sh)"""
import json
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-strats-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import moneymakers as MM                      # noqa: E402
from soe2 import pricecheck_page as PCP                 # noqa: E402
from soe2.config import P, save_json                    # noqa: E402

BREACH_URL = PCP.TABLET_ICONS["Breach Tablet"]


def strat(id_, name, typ="Breach", cat="Mapping", tags=("Mid budget",), profit=(1.0, 3.0), **kw):
    s = {"id": id_, "name": name, "author": "Tester", "updated": "2026-11-10", "patch": "0.4", "category": cat,
         "type": typ, "summary": "One line.", "thoughts_per_click": 2, "clicks_per_hour": "Steady", "tags": list(tags),
         "est_profit": {"low": profit[0], "high": profit[1], "unit": "div"}, "est_cost": {"amount": 0.5, "unit": "div"},
         "steps": ["Do this.", "Then that."]}
    s.update(kw)
    assert not MM.validate(s), MM.validate(s)
    return s


STRATS = [strat("breach-t15", "Breach in juiced T15 maps", profit=(1.1, 3.6),
                items=[{"kind": "waystone", "base": "Waystone (Tier 15)", "count": 1},
                       {"kind": "tablet", "base": "Breach Tablet", "count": 4}],
                ledger={"runs": 38, "minutes": 408, "loot_per_run_div": 1.03, "cost_per_run_div": 0.6,
                        "div_per_hour": 2.4}),
          strat("simulacrum-runs", "Simulacrum runs", typ="Simulacrum", cat="Bossing", profit=(1.2, 2.2)),
          strat("essence-low", "Essence farming, low tier", typ="Essence", tags=("League start",), profit=(0.5, 1.1))]


class Icons(unittest.TestCase):
    def setUp(self):
        PCP._ICONS = None
        try:
            os.remove(P("icons.json"))
        except OSError:
            pass

    def tearDown(self):
        PCP._ICONS = None

    def test_shipped_tablets(self):
        brief = {"Breach Tablet", "Ritual Tablet", "Expedition Tablet", "Irradiated Tablet", "Delirium Tablet",
                 "Abyss Tablet", "Temple Tablet", "Overseer Tablet"}
        self.assertEqual(set(PCP.TABLET_ICONS), brief)
        for base, url in PCP.TABLET_ICONS.items():
            self.assertTrue(url.startswith("https://web.poecdn.com/"), base)
        self.assertEqual(PCP.icons().get("Breach Tablet"), BREACH_URL, "a tablet's picture with no price check yet")
        for t in MM.MECH_TABLET.values():
            self.assertIn(t, PCP.icons(), f"{t}: every mechanic's tablet has a picture")
        self.assertIn(MM.GENERIC_TABLET, PCP.icons())

    def test_learned_wins(self):
        save_json("icons.json", {"Breach Tablet": "https://web.poecdn.com/learned.png", "Gold Ring": "https://x/r.png"})
        self.assertEqual(PCP.icons()["Breach Tablet"], "https://web.poecdn.com/learned.png")
        self.assertEqual(PCP.icons()["Ritual Tablet"], PCP.TABLET_ICONS["Ritual Tablet"])

    def test_learn_saves_only_learned(self):
        PCP.icon_learn("Gold Ring", "https://web.poecdn.com/ring.png")
        with open(P("icons.json"), encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved, {"Gold Ring": "https://web.poecdn.com/ring.png"}, "the shipped ones aren't copied")
        PCP._ICONS = None
        self.assertEqual(PCP.icons()["Gold Ring"], "https://web.poecdn.com/ring.png")
        self.assertEqual(PCP.icons()["Breach Tablet"], BREACH_URL)


class Numbers(unittest.TestCase):
    def test_mechanic_and_tablet(self):
        self.assertEqual(MM.tablet_of(STRATS[0]), "Breach Tablet")
        self.assertEqual(MM.tablet_of(STRATS[1]), "Irradiated Tablet", "bossing: the generic tablet")
        self.assertEqual(MM.tablet_of(STRATS[2]), "Irradiated Tablet")
        juiced = strat("j", "Juiced", typ="Juiced mapping", tags=("Delirium", "Mid budget"))
        self.assertEqual(MM.tablet_of(juiced), "Delirium Tablet", "a mechanic it also uses")
        self.assertEqual(MM.budget_of(STRATS[2]), "League start")

    def test_per_hour_and_how(self):
        ph = MM.per_hour(STRATS[0], {"per_hour": 3.9, "runs": 18})
        self.assertAlmostEqual(ph["value"], 2.35)
        self.assertEqual((ph["low"], ph["high"], ph["you"]), (1.1, 3.6, 3.9))
        for bit in ("1.1-3.6 div an hour", "middle is 2.4", "38 runs", "◆ You: 3.9"):
            self.assertIn(bit, ph["how"])
        self.assertEqual(ph["count"], "38 runs")
        self.assertEqual(MM.per_hour(STRATS[1])["count"], "estimate")
        self.assertIsNone(MM.per_hour(dict(STRATS[1], est_profit=None)))

    def test_cost_written_out(self):
        costs = {"breach-t15": {"prices": {"0": 0.2, "1": 0.1}, "at": time.time()}}
        c = MM.run_cost(STRATS[0], costs)
        self.assertAlmostEqual(c["value"], 0.6)
        self.assertEqual(c["sum"], "waystone 0.2 + 4 tablets × 0.1")
        self.assertIn("Trade site", c["how"])
        est = MM.run_cost(STRATS[0], {})
        self.assertEqual((est["value"], est["sum"]), (0.5, "the author's estimate"))

    def test_profit_and_time(self):
        p = MM.run_profit(STRATS[0])
        self.assertAlmostEqual(p["value"], 0.43)
        self.assertEqual(p["sum"], "loot 1.0 − cost 0.6")
        t = MM.run_time(STRATS[0])
        self.assertAlmostEqual(t["secs"], 408 * 60 / 38)
        self.assertEqual(MM.mins_text(645), "10 min 45 s")
        self.assertIsNone(MM.run_profit(STRATS[1]))
        self.assertIsNone(MM.run_time(STRATS[1]))
        self.assertEqual([MM.short_div(v) for v in (2.35, 0.43, 0.6, 12.2)], ["2.4", "0.43", "0.6", "12"])


# ---------------------------------------------------------------- the page, in a small stand-in for the app
def make_app(root):
    from soe2.moneymakers_page import MoneyMakersPage

    class App(MoneyMakersPage):
        mm_sync = True

        def __init__(self, root):
            self.root = root
            self.shell = None
            self.said, self.tracked = [], []
            self._drawer = False

        def drawer_look_on(self):
            return self._drawer

        def build_ledger(self, page):
            tk.Label(page, text="Strat Tracker").pack()

        def fl_data(self):
            return {"setups": [], "logs": []}

        def fl_refresh(self):
            pass

        def fl_for_strat(self, sid):
            self.tracked.append(sid)

        def fl_all_strats(self):
            return MM.all_strats()

        def run_bg(self, work, done):
            return None                                   # (nothing goes to the network in a test)

        def _say(self, text, secs=0):
            self.said.append(text)

        def app_toast(self, *a, **k):
            self.said.append(a[0] if a else "")

        def log_error(self, where):
            raise AssertionError(where)

        def cy_paint(self):
            pass

        def pc_art(self, url, px=78):
            return None                                   # (offline: no pictures - the words alone)
    return App(root)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S
        from soe2 import themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        cls.root.geometry("1400x900")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        from soe2.config import SETTINGS
        SETTINGS["league"] = ""                           # (no league set: Find shows All leagues)
        save_json(MM.MINE, [])                            # (From: All shows yours too - none here)
        save_json(MM.FILE, {"schema": MM.SCHEMA, "revision": 999, "strats": STRATS,
                            "oneliners": [{"id": "tip-one", "author": "A", "text": "Sell splinters in 100s."},
                                          {"id": "tip-two", "author": "B", "text": "Buy waystones in bulk."}]})
        for w in self.root.winfo_children():
            w.destroy()
        self.app = make_app(self.root)
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_money_window(self.body)
        self.pump()

    def pump(self, n=6):
        for _ in range(n):
            self.root.update()
            time.sleep(0.03)
        for cv in (self.app.mm_find_cv, self.app.mm_detail_cv):
            if cv._job:
                cv.redraw()
        self.root.update()

    def test_tabs_and_search_first(self):
        self.assertEqual(list(self.app.mm_page.btns), ["Find", "Strat Tracker"], "Lucrative Strats is gone")
        lefts = self.app.mm_bar._flow_lefts
        self.assertIs(lefts[0]["w"], self.app.mm_sbox, "the search box is first, top left")

    def test_find_rows(self):
        cv = self.app.mm_find_cv
        rows = self.app.mm_find_rows
        self.assertEqual(rows[0]["s"]["id"], "breach-t15", "the most an hour first")
        self.assertNotIn("best", cv.acts, "no Best for you right now card (owner)")
        self.assertIn("row0", cv.acts)

    def test_filters(self):
        self.app.mm_budget.set("League start")
        self.app.mm_filters_changed()
        self.pump()
        self.assertEqual([r["s"]["id"] for r in self.app.mm_find_rows], ["essence-low"])
        self.assertIn("clear", self.app.mm_find_cv.acts, "Clear filters shows while a filter is on")
        self.assertIn("League start", self.app.mm_drops["budget"].cget("text"))
        self.app.mm_filter("Bossing", "Map bosses")
        self.pump()
        self.assertEqual(self.app.mm_find_rows, [])
        self.assertIn("empty_btn", self.app.mm_find_cv.acts, "empty: what it is + one button")
        self.app.mm_find_cv.acts["empty_btn"]()                                   # Clear filters
        self.pump()
        self.assertEqual(len(self.app.mm_find_rows), 3)

    def test_quick_tips(self):
        cv = self.app.mm_find_cv
        self.assertFalse(self.app.mm_tips_open, "folded by default")
        self.assertNotIn("t_add", cv.acts)
        cv.acts["tips_head"]()
        self.pump()
        self.assertIn("t_add", cv.acts)
        self.assertNotIn("t_copy", cv.acts, "Copy is grayed until a tip is picked")
        self.assertIn("Pick a tip first", cv.tips.get("t_copy", ""))
        cv.acts["tip0"]()
        self.pump()
        self.assertIn("t_copy", cv.acts)
        self.app.mm_one_copy()
        self.assertEqual(self.root.clipboard_get(), "Sell splinters in 100s.")
        self.assertLessEqual(len(cv.primaries), 1, "at most one orange button")

    def test_open_and_back(self):
        self.app.mm_open("breach-t15|community")
        self.pump()
        dv = self.app.mm_detail_cv
        self.assertTrue(self.app.mm_detail_on)
        self.assertEqual(dv.primaries, ["Run this strat"], "one orange button on an opened strat")
        for tag in ("tile_ph_i", "tile_cost_i", "tile_prof_i", "tile_time_i"):
            self.assertTrue(dv.tips.get(tag), f"{tag}: how it was worked out")
        self.assertIn("need1", dv.acts, "You need: a slot per item")
        dv.acts["back"]()
        self.pump()
        self.assertFalse(self.app.mm_detail_on)
        self.assertIsNone(self.app.mm_sel)

    def test_drawer(self):
        self.app._drawer = True
        self.app.mm_drawer_look(True)
        self.pump()
        kids = {k["w"]: k for k in self.app.mm_bar._flow_kids}
        self.assertFalse(kids[self.app.mm_drops["filters"]]["hidden"], "Filters ▾ in the Drawer")
        for key in ("budget", "effort", "type", "sort"):
            self.assertTrue(kids[self.app.mm_drops[key]]["hidden"], key)
        self.assertLessEqual(len(self.app.mm_find_cv.primaries), 1)
        m = self.app.mm_drop_menu("filters")
        self.assertGreaterEqual(m.index("end"), 6)


if __name__ == "__main__":
    unittest.main()
