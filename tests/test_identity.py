"""3.3.0 owner, who am I: a party member's level-up is never you; a new character; a switch; Ranked and Personal;
no other player's name is saved.

    DISPLAY=:99 python3.12 -m unittest tests.test_identity          (or tests/runall.sh)"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-id-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import campaign as CP           # noqa: E402
from soe2 import focus as F               # noqa: E402
from soe2 import gamelog as GL            # noqa: E402
from soe2 import identity as ID           # noqa: E402
from soe2.config import SETTINGS          # noqa: E402

KEYS = ("identity", "focus", "campaign", "tracker")
REAL_CURRENT = CP.current_char


class Fresh(unittest.TestCase):
    def setUp(self):
        self.old = {k: SETTINGS.get(k) for k in KEYS}
        for k in KEYS:
            SETTINGS.pop(k, None)
        ID.OTHERS.clear()
        self.ps = [mock.patch.object(ID, "save", lambda: None), mock.patch.object(F, "save", lambda: None),
                   mock.patch.object(CP, "save", lambda: None),
                   # (test_campaign leaves its own current_char behind: the real one asks identity, as here)
                   mock.patch.object(CP, "current_char", REAL_CURRENT)]
        for p in self.ps:
            p.start()

    def tearDown(self):
        for p in self.ps:
            p.stop()
        ID.OTHERS.clear()
        for k, v in self.old.items():
            SETTINGS.pop(k, None) if v is None else SETTINGS.__setitem__(k, v)


class Rules(Fresh):
    def test_the_owners_case(self):
        """Level 97 in town with a level 38 party member: his level-up is not yours."""
        ID.note("level", {"who": "iLoveDanglyLips", "cls": "Stormweaver", "level": 97})
        self.assertEqual((ID.current(), ID.state()), ("iLoveDanglyLips", "known"))
        self.assertEqual(ID.note("party", {"who": "itThatFartz", "joined": True}), "other")
        self.assertIsNone(ID.note("level", {"who": "itThatFartz", "cls": "Druid", "level": 38}))
        self.assertEqual(ID.current(), "iLoveDanglyLips")
        self.assertFalse(ID.is_me("ITTHATFARTZ"))
        self.assertEqual([c[0] for c in ID.characters()], ["iLoveDanglyLips"])

    def test_a_join_after_a_level_up_takes_the_name_back(self):
        """You joined a friend's area: his level-up came before any join line."""
        ID.note("level", {"who": "Mine", "cls": "Monk", "level": 12})
        self.assertEqual(ID.note("level", {"who": "Friend", "cls": "Druid", "level": 20}), "switch")
        self.assertEqual(ID.current(), "Friend")
        ID.note("party", {"who": "Friend", "joined": False})
        self.assertEqual((ID.current(), ID.state()), ("", "unknown"))
        self.assertEqual([c[0] for c in ID.characters()], ["Mine"])

    def test_a_new_character(self):
        ID.note("level", {"who": "Old", "cls": "Monk", "level": 90})
        self.assertEqual(ID.note("area", {"area": "G1_1", "level": 1, "seed": 5}), "new")
        self.assertEqual((ID.current(), ID.state()), ("", "unknown"))
        ID.note("party", {"who": "Buddy", "joined": True})
        self.assertIsNone(ID.note("level", {"who": "Buddy", "cls": "Witch", "level": 2}))
        self.assertEqual(ID.note("level", {"who": "Fresh", "cls": "Warrior", "level": 2}), "known")
        self.assertEqual((ID.current(), ID.state(), ID.level()), ("Fresh", "known", 2))

    def test_the_character_screen_then_a_switch(self):
        ID.note("level", {"who": "A", "cls": "Monk", "level": 30})
        self.assertEqual(ID.note("login", {}), "assumed")
        self.assertEqual((ID.current(), ID.state()), ("A", "assumed"))
        self.assertFalse(ID.known())
        d = {"who": "B"}
        self.assertEqual(ID.note("death", d), "switch")
        self.assertEqual(d["was"], "A")
        ID.note("login", {})
        self.assertEqual(ID.note("gain", {"who": "B"}), "known", "the same one again: no switch")

    def test_a_typed_name_wins(self):
        SETTINGS["tracker"] = {"character": "Typed"}
        ID.note("level", {"who": "Someone", "cls": "Monk", "level": 5})
        self.assertEqual((ID.current(), ID.state()), ("Typed", "known"))
        self.assertFalse(ID.is_me("Someone"))
        self.assertTrue(ID.is_me("typed"))

    def test_pick_and_not_my_character(self):
        ID.note("level", {"who": "Leader", "cls": "Druid", "level": 40})
        self.assertTrue(ID.not_mine("Leader"))
        self.assertEqual(ID.state(), "unknown")
        ID.OTHERS.clear()                                     # the app restarts: memory is gone, the choice is not
        self.assertTrue(ID.is_other("leader"))
        self.assertIsNone(ID.note("level", {"who": "Leader", "cls": "Druid", "level": 41}))
        self.assertFalse(ID.pick("Leader"))
        self.assertTrue(ID.pick("Me"))
        self.assertEqual((ID.current(), ID.state()), ("Me", "known"))


class Privacy(Fresh):
    def test_no_other_players_name_is_saved(self):
        ID.note("level", {"who": "Mine", "cls": "Monk", "level": 12})
        ID.note("party", {"who": "SomeStranger", "joined": True})
        ID.not_mine("AnotherPerson")
        saved = json.dumps(SETTINGS, default=str)
        self.assertNotIn("SomeStranger", saved)
        self.assertNotIn("somestranger", saved)
        self.assertNotIn("anotherperson", saved.lower())
        self.assertIn("Mine", saved)

    def test_backfill_reads_the_log_into_memory_and_cleans_old_guesses(self):
        SETTINGS["focus"] = {"state": {"levels": {"Mine": 50, "Fartz": 38}, "classes": {"Fartz": "Druid"},
                                       "chars": ["Mine", "Fartz"], "last_char": "Fartz"}}
        SETTINGS["campaign"] = {"char_levels": {"Fartz": 38}, "last_char": "Fartz"}
        self.assertEqual(ID.current(), "Fartz", "what 3.2 believed")
        path = os.path.join(HOME, "Client.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("2026/11/23 10:00:00 1 a [INFO Client 1] : Fartz has joined the area.\n"
                    "2026/11/23 10:00:01 1 a [INFO Client 1] : Mine (Monk) is now level 50\n"
                    "2026/11/23 10:00:02 1 a [INFO Client 1] : Other One has left the area.\n")
        self.assertEqual(ID.backfill(path), 2)
        self.assertEqual(ID.current(), "")
        st = SETTINGS["focus"]["state"]
        self.assertEqual((st["levels"], st["classes"], st["chars"], st["last_char"]), ({"Mine": 50}, {}, ["Mine"], ""))
        self.assertEqual(SETTINGS["campaign"]["char_levels"], {})
        self.assertNotIn("Fartz", json.dumps(SETTINGS))

    def test_the_log_parser_knows_the_lines(self):
        pre = "2026/11/23 10:00:00 123 abc [INFO Client 1] "
        self.assertEqual(GL.parse(pre + ": Bob has received +10% to [Resistances|Cold Resistance].")[0::2],
                         ("gain", {"who": "Bob"}))
        self.assertEqual(GL.parse(pre + ": Bob has joined the area.")[0], "party")


class Features(Fresh):
    def test_league_plan_ignores_a_party_members_level(self):
        g = F.add_goal(kind="level", target=40)
        ID.note("party", {"who": "Fartz", "joined": True})
        F.log_event("level", {"who": "Fartz", "cls": "Druid", "level": 99}, None)
        self.assertFalse(g["done"])
        self.assertNotIn("Fartz", F.state().get("levels") or {})
        d = {"who": "Mine", "cls": "Monk", "level": 40}
        ID.note("level", d)
        F.log_event("level", d, None)
        self.assertTrue(g["done"])

    def test_campaign_uses_the_identity(self):
        import inspect
        self.assertIn("ID.current()", inspect.getsource(REAL_CURRENT))
        ID.note("level", {"who": "Mine", "cls": "Monk", "level": 12})
        self.assertEqual(CP.current_char(), "Mine")
        ID.note("party", {"who": "Fartz", "joined": True})
        CP.cfg()["on"] = True
        CP.log_event("level", 0, {"who": "Fartz", "cls": "Druid", "level": 38})
        self.assertEqual(CP.current_char(), "Mine")
        self.assertNotIn("Fartz", CP.cfg().get("char_levels") or {})

    def test_ranked_and_personal(self):
        run = {"from_start": True, "act": "2", "secs": {"1": 2500.0}}
        CP.cfg()["chars"]["Mine"] = run
        self.assertTrue(CP.ranked("Mine", run, "1"))
        CP.mark_personal("Mine")
        self.assertEqual(run["personal"], ["2"])
        self.assertFalse(CP.ranked("Mine", run, "2"))
        self.assertTrue(CP.ranked("Mine", run, "1"), "only the act that was going")
        self.assertFalse(CP.ranked("Mine", {"secs": {"1": 9}}, "1"), "picked up partway")
        ID.note("party", {"who": "Fartz", "joined": True})
        self.assertFalse(CP.ranked("Fartz #1", {"from_start": True}, "1"), "a run under a party member's name")

    def test_only_ranked_times_reach_the_leaderboards(self):
        from soe2 import leaderboard as LB
        SETTINGS["league"] = "L"
        key = CP.acts()[0]["key"]
        chars = CP.cfg()["chars"]
        chars["Mine"] = {"league": "L", "from_start": True, "done": True, "secs": {key: 3000.0}}
        chars["Half"] = {"league": "L", "done": True, "secs": {key: 3100.0}}
        chars["Fartz"] = {"league": "L", "from_start": True, "done": True, "secs": {key: 2000.0}}
        chars["Swap"] = {"league": "L", "from_start": True, "done": True, "secs": {key: 2100.0}, "personal": [key]}
        ID.note("party", {"who": "Fartz", "joined": True})
        with mock.patch.object(LB, "classes", lambda: {}):
            sent = sorted(e["char"] for e in LB.campaign_entries())
        self.assertEqual(sent, ["Mine"])

    def test_old_runs_count_as_from_the_start(self):
        SETTINGS["campaign"] = {"chars": {"Old": {"secs": {"1": 5.0}}}}
        self.assertTrue(CP.cfg()["chars"]["Old"]["from_start"])

    def test_you_shows_a_dash_until_named(self):
        from soe2.campaign_ui import CampaignUI
        h = CampaignUI.__new__(CampaignUI)
        self.assertEqual(h.camp_you_text(), "–")
        self.assertEqual(h.camp_got_text(), "–")
        self.assertIn("Click to pick", h.camp_you_tip())
        for t in (h.camp_you_tip(), h.camp_got_tip()):
            self.assertNotIn("(", t)


if __name__ == "__main__":
    unittest.main()
