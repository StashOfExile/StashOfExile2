"""3.0.6: Leaderboards - each player's 10 fastest runs per board entry (client side), campaign times that don't depend on
the character's name, and the campaign times rebuilt from Client.txt. (The board's own code: board/test/lb.test.mjs,
run from here too when node is installed.)

Runs on a throwaway data folder: HOME points at a temp folder before the app's modules load."""
import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import campaign as CP          # noqa: E402
from soe2 import leaderboard as LB       # noqa: E402

DAY = 86400
T0 = 1_800_000_000                       # (a whole day: 2027-01-15 08:00 UTC)


def run_entry(secs, key="Citadel", cat="map", league="L", cls="Witch", at=T0, char="Secret"):
    return {"cat": cat, "key": key, "secs": float(secs), "league": league, "cls": cls, "char": char, "level": 80,
            "deaths": 1, "at": at}


class Payload(unittest.TestCase):
    def test_ten_fastest_per_key_league_class(self):
        es = [run_entry(100 + i, at=T0 + i * DAY) for i in range(15)]
        es += [run_entry(50 + i, cls="Monk", at=T0 + i * DAY) for i in range(3)]       # (another class: its own entry)
        out = LB.payload(es)
        witch = sorted(e["secs"] for e in out if e["cls"] == "Witch")
        self.assertEqual(witch, [100.0 + i for i in range(10)])
        self.assertEqual(len([e for e in out if e["cls"] == "Monk"]), 3)

    def test_no_character_names_and_only_the_day(self):
        out = LB.payload([run_entry(100, at=T0 + 12345)])
        self.assertEqual(len(out), 1)
        self.assertNotIn("char", out[0])
        self.assertNotIn("Secret", repr(out))
        self.assertEqual(out[0]["at"] % DAY, 0)

    def test_the_same_run_is_listed_once(self):
        out = LB.payload([run_entry(100, at=T0 + 5), run_entry(100, at=T0 + 900), run_entry(100, at=T0 + DAY)])
        self.assertEqual(len(out), 2, "same time on the same day once; another day is another run")

    def test_cap_fills_fastest_first_across_keys(self):
        # 60 keys x 10 runs = 600 > 400: every key gets its 1st, then its 2nd ... (400 = 6 full rounds + 40 of the 7th)
        es = [run_entry(100 + r, key=f"Map {k:02d}", at=T0 + r * DAY) for k in range(60) for r in range(10)]
        out = LB.payload(es)
        self.assertEqual(len(out), 400)
        per_key = {}
        for e in out:
            per_key.setdefault(e["key"], []).append(e["secs"])
        self.assertEqual(len(per_key), 60, "every key got its best")
        self.assertTrue(all(v[0] == 100.0 for v in (sorted(x) for x in per_key.values())))
        counts = sorted(len(v) for v in per_key.values())
        self.assertEqual((counts[0], counts[-1]), (6, 7), "no key gets a 7th before every key has its 6th")
        for v in per_key.values():
            self.assertEqual(sorted(v), [100.0 + i for i in range(len(v))], "each key's fastest ones")

    def test_private_leagues_stay_home(self):
        with mock.patch("soe2.privacy.is_private_league", lambda lg: lg == "Private"):
            out = LB.payload([run_entry(100, league="Private"), run_entry(100)])
        self.assertEqual([e["league"] for e in out], ["L"])

    def test_page_groups_a_players_runs_under_their_best(self):
        try:
            from soe2.leaderboard_page import LeaderboardPage
        except ImportError:                                    # (no tkinter here)
            self.skipTest("no tkinter")
        rows = [{"id": 1, "name": "Anna", "secs": 100, "rank_in_player": 1}, {"id": 2, "name": "Bo", "secs": 105, "rank_in_player": 1},
                {"id": 3, "name": "Anna", "secs": 110, "rank_in_player": 2}, {"id": 4, "name": "Bo", "secs": 115, "rank_in_player": 2},
                {"id": 5, "name": "Cy", "secs": 120, "rank_in_player": 1}]
        g = LeaderboardPage.lb_groups(rows)
        self.assertEqual([(n, [r["id"] for r in rs]) for n, rs in g], [("Anna", [1, 3]), ("Bo", [2, 4]), ("Cy", [5])])


class AreaLevelColumn(unittest.TestCase):
    def test_header_and_hover_text(self):
        try:
            from soe2 import leaderboard_page as LP
        except ImportError:
            self.skipTest("no tkinter")
        self.assertEqual(LP.LEVEL_HEADER, "Area level")
        self.assertEqual(LP.LEVEL_TIP, "The map's area level when it was run. Waystone tier 1 is area level 65; tier 16 is 80.")
        src = open(os.path.join(ROOT, "soe2", "leaderboard_page.py"), encoding="utf-8").read()
        self.assertIn('("lvl", LEVEL_HEADER,', src, "the column uses the header text")
        self.assertNotIn('"Level"', src)

    def test_zero_shows_a_dash(self):
        self.assertEqual([LB.level_text(v) for v in (0, None, 80, 65.0)], ["-", "-", "80", "65"])


# ------------------------------------------------------------------ the log
PRE = "2026/11/02 {} 123456789 abc [{} Client 18220] "   # (a line before the first event)


def fake_log(path, events):
    """events: [(seconds after the start, kind, text)] -> a Client.txt."""
    import datetime
    base = datetime.datetime(2026, 11, 2, 12, 0, 0)
    with open(path, "w", encoding="utf-8") as f:
        f.write(PRE.format("11:59:00", "INFO") + "Some earlier line\n")
        for t, kind, text in events:
            at = base + datetime.timedelta(seconds=t)
            f.write(f"{at:%Y/%m/%d %H:%M:%S} 123456789 abc [{kind} Client 18220] {text}\n")


def area(t, aid, level=1):
    return (t, "DEBUG", f'Generating level {level} area "{aid}" with seed 4242')


def scene(t, name):
    return (t, "DEBUG", f"[SCENE] Set Source [{name}]")


# Act 1 (zones, a hideout trip, AFK), Act 2 (a long gap), Act 3, then a map
LOG = [
    area(0, "G1_1"), scene(1, "The Riverbank"),
    (60, "INFO", ": Tester (Witch) is now level 2"),                  # (the name only now - after the first zone)
    area(120, "G1_town"), scene(121, "Clearfell Encampment"),
    area(300, "G1_2"), scene(301, "Clearfell"),
    area(400, "HideoutFelled"),                                       # (hideout: no zone time)
    area(500, "G1_2"), scene(501, "Clearfell"),
    (700, "INFO", ": AFK mode is now ON. Autoreply \"This player is AFK.\""),
    (3700, "INFO", ": AFK mode is now OFF."),
    area(3800, "G2_1", 12), scene(3801, "Vastiri Outskirts"),
    area(4000, "G2_town", 12), scene(4001, "The Ardura Caravan"),
    area(5201, "G3_1", 24), scene(5202, "Sandswept Marsh"),            # (20 minutes with no line: not counted)
    area(5300, "G3_town", 24), scene(5301, "Ziggurat Encampment"),
    area(5400, "MapCrypt", 65),
]
EXPECT_ACTS = {"1": 800.0, "2": 200.0, "3": 198.0}
EXPECT_ZONES = {"The Riverbank": 120.0, "Clearfell Encampment": 180.0, "Clearfell": 99.0, "Vastiri Outskirts": 200.0,
                "Sandswept Marsh": 99.0, "Ziggurat Encampment": 99.0}


class Rebuild(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="soe2-log-")
        self.path = os.path.join(self.dir, "Client.txt")
        fake_log(self.path, LOG)
        CP.SETTINGS["campaign"] = {}
        CP.SETTINGS["league"] = "Test"
        CP._PACK["key"] = None
        self.save = mock.patch.object(CP, "save", lambda: None)
        self.save.start()

    def tearDown(self):
        self.save.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_act_and_zone_times_from_the_log(self):
        runs = CP.rebuild_from_log(self.path)
        self.assertEqual(len(runs), 1)
        r = runs[0]
        self.assertEqual(r["char"], "Tester", "the name from the level-up line, though it came after the first zone")
        self.assertEqual(r["league"], "Test")
        self.assertEqual(r["secs"], EXPECT_ACTS, "AFK (50 min) and the 20-minute gap are left out")
        self.assertEqual(r["zone_best"], EXPECT_ZONES, "the hideout trip isn't zone time; each zone entering to leaving")
        self.assertTrue(r["done"])
        self.assertIsNone(r["total"], "not every act of the guide has a time")

    def test_the_live_data_is_not_touched(self):
        CP.SETTINGS["campaign"] = {"chars": {"Live": {"act": "2", "secs": {"1": 5.0}, "league": "Test"}}}
        before = copy.deepcopy(CP.SETTINGS["campaign"])
        CP.take_events()
        with mock.patch.object(CP, "current_char", lambda: "Live"):
            CP.rebuild_from_log(self.path)
            self.assertEqual(CP.current_char(), "Live")
        self.assertEqual(CP.SETTINGS["campaign"], before)
        self.assertEqual(CP.take_events(), [], "no pop-ups from a rebuild")
        self.assertIsNone(CP._sandbox())

    def test_only_the_last_part_of_the_file(self):
        runs = CP.rebuild_from_log(self.path, max_bytes=200)            # (the log's last few lines: no act time)
        self.assertEqual(runs, [])
        self.assertEqual(CP.rebuild_from_log(os.path.join(self.dir, "missing.txt")), [])

    def test_whole_campaign_when_every_act_has_a_time(self):
        keys = [a["key"] for a in CP.acts()]
        ev, t = [], 0
        for i, k in enumerate(keys):
            first = next(s for s in CP.act(k)["steps"] if s.get("ids"))
            aid = first["ids"][0]
            ev += [area(t, aid, 5), scene(t + 1, first["zone"])]
            t += 600
        ev.append((10, "INFO", ": Tester (Witch) is now level 3"))
        ev.append(area(t, "MapCrypt", 65))
        ev.sort(key=lambda e: e[0])
        path = os.path.join(self.dir, "full.txt")
        fake_log(path, ev)
        r = CP.rebuild_from_log(path)[0]
        self.assertTrue(r["done"])
        self.assertEqual(sorted(r["secs"]), sorted(keys))
        self.assertEqual(r["total"], round(sum(r["secs"].values()), 1))

    def test_merge_keeps_the_faster_and_sends_the_times(self):
        CP.SETTINGS["campaign"] = {"chars": {"": {"act": "3", "done": True, "secs": {}, "league": "Test"},
                                             "Tester": {"act": "1", "secs": {"1": 700.0}, "league": "Test",
                                                        "closed": ["1"], "zone_best": {"Clearfell": 50.0}}}}
        runs = CP.rebuild_from_log(self.path)
        acts, zones, tot = CP.merge_rebuilt(runs)
        run = CP.cfg()["chars"]["Tester"]
        self.assertEqual(run["secs"], {"1": 700.0}, "its own run is left as it is")
        self.assertEqual(run["best_secs"], EXPECT_ACTS)
        self.assertEqual(run["zone_best"]["Clearfell"], 50.0, "the old one was faster")
        self.assertEqual(run["zone_best"]["Vastiri Outskirts"], 200.0)
        self.assertEqual((acts, zones), (3, 5))
        self.assertEqual(CP.cfg()["best"]["Test"], {"1": 800, "2": 200, "3": 198})
        CP.merge_rebuilt(runs)                                            # (again: nothing new)
        self.assertEqual(CP.merge_rebuilt(runs)[:2], (0, 0))
        es = LB.campaign_entries() + LB.zone_entries()
        got = {(e["cat"], e["key"]): e["secs"] for e in es}
        self.assertEqual(got[("campaign", "Act I")], 700.0, "the better of old (700) and rebuilt (800)")
        self.assertEqual(got[("campaign", "Act II")], 200.0)
        self.assertEqual(got[("zone", "Vastiri Outskirts")], 200.0)
        self.assertTrue(all(e["league"] == "Test" for e in es))
        again = {(e["cat"], e["key"]): e["at"] for e in LB.campaign_entries() + LB.zone_entries()}
        self.assertEqual(again, {(e["cat"], e["key"]): e["at"] for e in es}, "stable days: a re-send is the same run")


class NameFree(unittest.TestCase):
    """Owner's data: the nameless run was marked done with no times, so no campaign time was ever kept."""

    def setUp(self):
        CP.SETTINGS["campaign"] = {}
        CP.SETTINGS["league"] = "Test"
        CP._PACK["key"] = None
        self.ts = 1_000_000.0
        self.patches = [mock.patch.object(CP, "current_char", lambda: ""), mock.patch.object(CP, "char_level", lambda: 0),
                        mock.patch.object(CP, "save", lambda: None)]
        for p in self.patches:
            p.start()
        CP.take_events()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def enter(self, aid, name, level=1, kind="other", dt=30):
        self.ts += dt
        CP.log_event("area", self.ts, {"area": aid, "level": level, "seed": 7}, kind)
        self.ts += 1
        return CP.log_event("scene", self.ts, {"name": name})

    def test_a_map_first_does_not_close_a_run_without_times(self):
        CP.log_event("area", self.ts, {"area": "MapCrypt", "level": 70, "seed": 7}, "map")
        run = CP.char()
        self.assertFalse(run["done"], "no times: not done")
        self.enter("G1_1", "The Riverbank")
        self.enter("G1_town", "Clearfell Encampment", dt=120)
        run = CP.char()
        self.assertGreater(run["secs"].get("1", 0), 0, "act time kept with no character name")
        self.assertIn("The Riverbank", run["zone_best"])
        es = LB.campaign_entries() + LB.zone_entries()
        self.assertTrue([e for e in es if e["cat"] == "zone" and e["key"] == "The Riverbank"])
        self.assertEqual({e["league"] for e in es}, {"Test"})

    def test_a_nameless_run_that_was_done_with_no_times_starts_timing_again(self):
        """The shape of the owner's data: chars[""] = {secs: {}, done: True}."""
        CP.SETTINGS["campaign"] = {"chars": {"": {"secs": {}, "done": True, "league": "Test"}}}
        run = CP.char()
        self.assertTrue(run["done"])
        self.enter("G1_1", "The Riverbank", 1)                    # (a new campaign: the first zone at a low level)
        self.enter("G1_town", "Clearfell Encampment", 1, dt=120)
        run = CP.char()
        self.assertFalse(run["done"])
        self.assertGreater(run["secs"].get("1", 0), 0)
        self.assertIn("The Riverbank", run.get("zone_best", {}))

    def test_a_finished_run_is_kept_when_the_next_character_starts(self):
        self.enter("G1_1", "The Riverbank", 1)
        self.enter("G1_town", "Clearfell Encampment", 1, dt=120)
        self.enter("G1_2", "Clearfell", 2, dt=100)
        CP.log_event("area", self.ts + 60, {"area": "MapCrypt", "level": 70, "seed": 7}, "map")
        self.assertTrue(CP.char()["done"])
        first = dict(CP.char()["secs"])
        self.ts += 600
        self.enter("G1_1", "The Riverbank", 1)                    # a new character, still no name known
        self.enter("G1_town", "Clearfell Encampment", 1, dt=50)
        chars = CP.cfg()["chars"]
        old = [r for r in chars.values() if r.get("archived")]
        self.assertEqual(len(old), 1)
        self.assertEqual(old[0]["secs"], first)
        self.assertFalse(chars[""]["done"])
        self.assertGreater(chars[""]["secs"].get("1", 0), 0)
        acts = [e for e in LB.campaign_entries() if e["key"] == "Act I"]
        self.assertEqual([e["secs"] for e in acts], [round(first["1"], 1)],
                         "the kept run's Act I; the new run's act isn't finished")

    def test_the_name_arrives_late_the_run_goes_on_under_it(self):
        self.enter("G1_1", "The Riverbank", 1)
        self.enter("G1_town", "Clearfell Encampment", 1, dt=120)
        with mock.patch.object(CP, "current_char", lambda: "Tester"):
            run = CP.char()
            self.assertGreater(run["secs"]["1"], 0, "the nameless run's times came along")
            self.assertNotIn("", CP.cfg()["chars"])

    def test_a_done_run_sends_its_last_act_and_the_class_is_whatever_is_known(self):
        CP.SETTINGS["campaign"] = {"chars": {"": {"act": "3", "done": True, "secs": {"1": 900.0, "3": 500.0},
                                                  "league": "", "closed": ["1", "3"]}}}
        with mock.patch.object(LB, "classes", lambda: {"Someone": "Invoker"}), \
                mock.patch("soe2.focus.cfg", lambda: {"state": {"last_char": "Someone"}}):
            es = LB.campaign_entries()
        self.assertEqual({(e["key"], e["secs"]) for e in es}, {("Act I", 900.0), ("Act III", 500.0)})
        self.assertEqual({e["league"] for e in es}, {"Test"}, "no league on the run: the current one")
        self.assertEqual({e["cls"] for e in es}, {"Invoker"})

    def test_a_run_is_not_done_at_maps_level_without_times(self):
        CP.SETTINGS["campaign"] = {"chars": {"": {"act": "2", "secs": {}, "league": "Test"}}}
        with mock.patch.object(CP, "char_level", lambda: 70):
            self.assertFalse(CP.active())
        self.assertFalse(CP.char()["done"])


class BoardCode(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node isn't installed")
    def test_worker_lb(self):
        r = subprocess.run(["node", os.path.join(ROOT, "board", "test", "lb.test.mjs")], capture_output=True, text=True,
                           timeout=120)
        if "node:sqlite" in (r.stderr or "") and r.returncode:
            self.skipTest("this node has no node:sqlite")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
