"""The Campaign Helper's engine (soe2/campaign.py) and the game log's dialogue lines (soe2/gamelog.py).

    python3.12 -m unittest discover -s tests        (or tests/runall.sh)

Runs on a throwaway data folder: HOME points at a temp folder before the app's modules load."""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import campaign as CP          # noqa: E402
from soe2 import gamelog as GL           # noqa: E402

PREFIX = "2026/11/02 20:11:05 123456789 abc [INFO Client 18220] "


class Game:
    """Feeds the engine what the game's log would: an area, its scene line, dialogue."""

    def __init__(self, route="full", level=10):
        CP.SETTINGS["campaign"] = {}
        CP.SETTINGS["league"] = "Test"
        CP._PACK["key"] = None
        self.level = level
        CP.char_level = lambda: self.level
        CP.current_char = lambda: "Tester"
        CP.save = lambda: None
        CP.take_events()
        self.ts = 1_000_000.0
        CP.char()["route"] = route

    def enter(self, area, name, level=5, kind="other"):
        self.ts += 30
        CP.log_event("area", self.ts, {"area": area, "level": level, "seed": 7}, kind)
        self.ts += 1
        return CP.log_event("scene", self.ts, {"name": name})

    def say(self, who, text):
        self.ts += 5
        ev = GL.parse(PREFIX + f"{who}: {text}")
        assert ev and ev[0] == "say", ev
        return CP.log_event("say", self.ts, ev[2])

    @property
    def run(self):
        return CP.char()


class DialogueParser(unittest.TestCase):
    def say(self, text, level="INFO"):
        return GL.parse(PREFIX.replace("INFO", level) + text)

    def test_npc_line(self):
        ev = self.say("The King in the Mists: We will meet again...")
        self.assertEqual(ev[0], "say")
        self.assertEqual(ev[2], {"who": "The King in the Mists", "text": "We will meet again..."})

    def test_speaker_with_comma(self):
        ev = self.say("Geonor, the Putrid Wolf: The madness... It consumed my being.")
        self.assertEqual(ev[2]["who"], "Geonor, the Putrid Wolf")

    def test_chat_channels_are_never_npcs(self):
        for t in ("#Global: hello", "$Trade: WTS mirror", "&Guild: gg", "%Party: wait", "@To Bob: hi",
                  "*Someone: x", "<GLD> Bob: hello"):
            ev = self.say(t)
            self.assertFalse(ev and ev[0] == "say", t)

    def test_system_lines_are_not_npcs(self):
        self.assertEqual(self.say(": Bob (Monk) is now level 12")[0], "level")
        self.assertEqual(self.say(": AFK mode is now ON. Autoreply \"x\"")[0], "afk")
        self.assertIsNone(self.say(": You have entered Clearfell."))
        self.assertEqual(self.say("[SCENE] Set Source [Freythorn]")[0], "scene")
        self.assertIsNone(self.say("Connecting to instance server at 1.2.3.4:6112"))

    def test_only_info_lines(self):
        self.assertIsNone(self.say("Tile: 5", level="DEBUG"))

    def test_whisper_still_a_whisper(self):
        self.assertEqual(self.say("@From Bob: hi")[0], "whisper")

    def test_local_chat_never_trips_a_cue(self):
        """Local chat looks like an NPC line - only the pack's exact speaker + line in that area count."""
        Game()
        self.assertIsNone(CP.find_cue("G1_12", "Bob", "We will meet again..."))
        self.assertIsNone(CP.find_cue("G1_1", "The King in the Mists", "We will meet again..."))
        self.assertEqual(CP.find_cue("G1_12", "The King in the Mists", "We will meet again...")[0], "d")

    def test_cue_text_markup_and_dashes(self):
        self.assertEqual(CP.cue_norm("Now  then—it is <i>{time}</i>"), "now then-it is time</i>")


class OnYouGo(unittest.TestCase):
    """The owner's screenshot: Speedrun, the app started mid-act, Freythorn -> 'On you go, then the Riverbank'."""

    def test_freythorn_on_speedrun(self):
        g = Game("speed")
        g.enter("G1_12", "Freythorn", 11)
        t = CP.line_text()
        self.assertNotIn("On you go", t)
        self.assertNotIn("Riverbank", t)
        self.assertTrue(t.startswith("Do the 3 rituals, kill the King in the Mists (+30 spirit)"), t)
        self.assertEqual(CP.line()["then"], "Ogham Farmlands")

    def test_no_line_says_on_you_go(self):
        for route in ("full", "speed", "rush"):
            g = Game(route)
            for a in CP.acts():
                for s in a["steps"]:
                    g.enter((s.get("ids") or ["X"])[0], s["zone"], 10)
                    t = CP.line_text()
                    self.assertNotIn("On you go", t, (route, s["zone"]))
                    d = CP.line()
                    if d["next"]:                                       # (the app never adds ", then X")
                        self.assertNotIn(", then " + d["next"], t, (route, s["zone"]))
                    self.assertLessEqual(t.count("then"), 1, (route, s["zone"]))
                    self.assertNotIn(") (", t, (route, s["zone"]))       # no reward twice

    def test_zone_off_the_route_says_so(self):
        g = Game("speed")
        g.enter("G1_2", "Clearfell", 2)
        g.enter("G1_3", "The Mud Burrow", 3)
        d = CP.line()
        self.assertEqual(d["do"], "Not on the Speedrun route")
        self.assertEqual(d["then"], "The Grelwood")      # the next step after it - never the top of the act

    def test_back_text(self):
        g = Game()
        g.enter("G1_4", "The Grelwood", 4)
        self.assertIn("find Una", CP.line()["do"])
        g.enter("G1_5", "The Red Vale", 5)
        g.enter("G1_4", "The Grelwood", 4)
        self.assertIn("Runed Spikes", CP.line()["do"])
        self.assertEqual(CP.line()["then"], "The Grim Tangle")


class Lines(unittest.TestCase):
    def test_every_line_fits(self):
        Game()
        for a in CP.acts():
            for s in a["steps"]:
                for t in (s.get("do"), (s.get("speed") or {}).get("do"), (s.get("rush") or {}).get("do"),
                          s.get("back"), s.get("early")):
                    if t:
                        self.assertLessEqual(len(t), 70, t)

    def test_trial_of_the_ancestors_spelling(self):
        Game()
        self.assertEqual(CP.find_zone("Trial of the Ancestors")[0], "4")
        self.assertIsNone(CP.find_zone("Trail of the Ancestors")[0])

    def test_old_dreadnought_layout(self):
        g = Game("speed")
        g.enter("G2_12_2", "Dreadnought Vanguard", 32)
        self.assertIn("Jamanra", CP.line()["do"])


class InterludeKeys(unittest.TestCase):
    def test_keys_follow_the_area_ids(self):
        Game()
        for key, aid, zone in (("i1", "P1_5", "Wolvenhold"), ("i2", "P2_1", "The Khari Crossing"),
                               ("i3", "P3_2", "Kriar Village")):
            self.assertEqual(CP.act_of_id(aid), key)
            self.assertEqual(CP.find_zone(zone, aid)[0], key)
            self.assertEqual(CP.act(key)["prefix"], "P" + key[1:])
        for r in CP.rewards():
            if r["act"].startswith("i"):
                z = CP.find_zone(r["zone"])[0]
                self.assertEqual(z, r["act"], r["id"])

    def test_one_interlude_never_closes_another(self):
        g = Game()
        g.run["act"] = "4"
        g.enter("P1_Town", "The Refuge", 64, kind="town")
        g.enter("P1_1", "Scorched Farmlands", 62)
        g.enter("P2_Town", "The Khari Bazaar", 64, kind="town")
        g.enter("P2_1", "The Khari Crossing", 62)
        g.enter("P3_2", "Kriar Village", 62)
        self.assertNotIn("i1", g.run["closed"])
        self.assertNotIn("i2", g.run["closed"])
        missed = [k for k, v in g.run["rewards"].items() if v == "missed" and k.startswith("i")]
        self.assertEqual(missed, [])

    def test_kingsmarch_is_a_hub(self):
        g = Game()
        g.enter("P3_2", "Kriar Village", 62)
        g.enter("G4_town", "Kingsmarch", 65, kind="town")
        self.assertEqual(g.run["act"], "i3")
        self.assertTrue(CP.line()["do"].startswith("In Kingsmarch"))

    def test_old_reward_ids_move(self):
        CP.SETTINGS["campaign"] = {"chars": {"A": {"rewards": {"i1_risu": "got", "i3_oswin": "missed"},
                                                    "ask": ["i2_yeti"]}}}
        c = CP.cfg()
        self.assertEqual(c["chars"]["A"]["rewards"], {"i2_risu": "got", "i1_oswin": "missed"})
        self.assertEqual(c["chars"]["A"]["ask"], ["i3_yeti"])

    def test_endgame_trial_is_not_the_campaign(self):
        g = Game()
        g.enter("G3_3", "Jungle Ruins", 34)
        self.assertIsNone(g.enter("G3_10", "Trial of Chaos", 70))
        self.assertEqual(g.run["zone"], "Jungle Ruins")


class BossDeath(unittest.TestCase):
    def test_boss_down_ticks_and_moves_on(self):
        g = Game()
        g.enter("G1_12", "Freythorn", 11)
        g.say("The King in the Mists", "You have your audience, traveller!")
        self.assertEqual(g.run["fight"]["area"], "G1_12")
        self.assertEqual(g.say("The King in the Mists", "We will meet again..."), "zone")
        self.assertEqual(g.run["rewards"].get("a1_king"), "got")
        d = CP.line()
        self.assertTrue(d["done"])
        self.assertTrue(d["do"].startswith("✓ The King in the Mists is down"), d["do"])
        self.assertEqual(d["then"], "Ogham Farmlands")
        ev = [e for e in CP.take_events() if e["kind"] == "boss"]
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["boss"], ev[0]["gives"], ev[0]["next"]),
                         ("the King in the Mists", "+30 spirit", "Ogham Farmlands"))

    def test_second_line_no_second_popup(self):
        g = Game()
        g.enter("G1_15", "Ogham Manor", 15)
        g.say("Geonor, the Putrid Wolf", "The madness... It consumed my being.")
        g.say("Geonor, the Putrid Wolf", "Yes... Find her. Kill her.")
        self.assertEqual(len([e for e in CP.take_events() if e["kind"] == "boss"]), 1)

    def test_last_boss_ends_the_act(self):
        g = Game()
        g.enter("G1_15", "Ogham Manor", 15)
        g.say("Geonor, the Putrid Wolf", "The madness... It consumed my being.")
        self.assertIn("1", g.run["closed"])
        self.assertIn("act", [e["kind"] for e in CP.take_events()])

    def test_cue_from_another_area_does_nothing(self):
        g = Game()
        g.enter("G1_2", "Clearfell", 2)
        self.assertIsNone(g.say("The King in the Mists", "We will meet again..."))
        self.assertNotEqual(g.run["rewards"].get("a1_king"), "got")

    def test_left_before_the_boss_died(self):
        g = Game()
        g.enter("G1_8", "Mausoleum of the Praetor", 9)
        g.say("Draven, the Eternal Praetor", "Your intrusion will be punished!")
        CP.take_events()
        g.enter("G1_7", "Cemetery of the Eternals", 7)
        ev = [e for e in CP.take_events() if e["kind"] == "left"]
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["boss"], ev[0]["zone"]), ("Draven", "Mausoleum of the Praetor"))

    def test_town_portal_mid_fight_is_not_leaving(self):
        g = Game()
        g.enter("G1_12", "Freythorn", 11)
        g.say("The King in the Mists", "Ko leor... traveler.")
        g.enter("G1_town", "Clearfell Encampment", 15, kind="town")
        self.assertEqual([e for e in CP.take_events() if e["kind"] == "left"], [])
        g.enter("G1_12", "Freythorn", 11)
        self.assertIsNotNone(g.run["fight"])


class TownAsks(unittest.TestCase):
    def test_asked_once_then_once_more(self):
        g = Game()
        g.enter("G1_13_1", "Ogham Farmlands", 12)
        self.assertEqual(g.enter("G1_town", "Clearfell Encampment", 15, kind="town"), "ask")
        self.assertIn("a1_lute", g.run["ask"])
        CP.set_reward("a1_lute", "not_yet")
        self.assertNotIn("a1_lute", g.run["ask"])
        g.enter("G1_13_2", "Ogham Village", 13)
        g.enter("G1_town", "Clearfell Encampment", 15, kind="town")
        self.assertIn("a1_lute", g.run["ask"])             # once more
        CP.set_reward("a1_lute", "not_yet")
        g.enter("G1_14", "The Manor Ramparts", 14)
        g.enter("G1_town", "Clearfell Encampment", 15, kind="town")
        self.assertNotIn("a1_lute", g.run["ask"])          # and no more

    def test_boss_line_rewards_are_not_asked(self):
        g = Game()
        g.enter("G1_12", "Freythorn", 11)
        g.say("The King in the Mists", "We will meet again...")
        g.enter("G1_town", "Clearfell Encampment", 15, kind="town")
        self.assertNotIn("a1_king", g.run["ask"])


class LevelCheck(unittest.TestCase):
    def test_words_and_marks(self):
        self.assertEqual(CP.level_text(12, 12), "✓ Lvl 12 · OK")
        self.assertEqual(CP.level_text(9, 12), "! Lvl 9 · 3 under")
        self.assertEqual(CP.level_text(11, 12), "✓ Lvl 11 · OK")
        self.assertEqual(CP.level_text(30, 24), "! Lvl 30 · 6 over")      # safe = 3 + 30 // 16 = 4
        self.assertEqual(CP.level_text(30, 26), "✓ Lvl 30 · OK")
        self.assertEqual(CP.level_text(0, 12), "Lvl ?")

    def test_how_shows_the_sum(self):
        self.assertIn("3 + 30 ÷ 16 (rounded down) = 4", CP.level_how(30, 24))

    def test_level_up_line_kept_without_league_plan(self):
        Game()
        CP.SETTINGS.setdefault("tracker", {})["character"] = ""
        ev = GL.parse(PREFIX + ": Tester (Monk) is now level 12")
        self.assertEqual(CP.log_event(*ev), "zone")
        self.assertEqual(CP.cfg()["char_levels"]["Tester"], 12)

    def test_too_low_popup_once_per_zone(self):
        g = Game(level=8)
        g.enter("G1_15", "Ogham Manor", 15)
        g.enter("G1_14", "The Manor Ramparts", 14)
        g.enter("G1_15", "Ogham Manor", 15)
        g.enter("G1_12", "Freythorn", 11)                  # (another boss zone, a minute later: quiet)
        low = [e for e in CP.take_events() if e["kind"] == "low"]
        self.assertEqual([e["zone"] for e in low], ["Ogham Manor"])      # (boss zones only, once)


class GotSoFar(unittest.TestCase):
    def test_totals(self):
        g = Game()
        got = CP.got_so_far()
        self.assertEqual(got["points"][:2], (0, 24))
        self.assertEqual(got["spirit"][:2], (0, 100))
        self.assertEqual(got["res"][:2], (0, 30))
        CP.set_reward("a1_beira", "got")
        self.assertEqual(CP.got_text(CP.got_so_far()), "Points 0/24 · Spirit 0/100 · Res 10/30%")
        self.assertIn("✓ Beira of the Rotten Pack (Clearfell): +10% cold res", CP.got_how(CP.got_so_far()))
        self.assertTrue(g)


class Hideout(unittest.TestCase):
    """Round 18 (feedback: the Campaign Helper showed in the hideout): the line shows in campaign areas (towns too),
    never in a hideout - also right after a login there (the log's last area, read at start-up)."""

    def test_hideout_hides_the_line(self):
        g = Game()
        g.enter("G1_12", "Freythorn", 11)
        self.assertTrue(CP.shown())
        g.enter("HideoutFelled", "Felled Hideout", 11, kind="hideout")
        self.assertTrue(CP.active(), "the helper is still on (its card opens)")
        self.assertFalse(CP.shown(), "no Campaign Bar in the hideout")
        g.enter("G1_town", "Clearfell Encampment", 11, kind="town")
        self.assertTrue(CP.shown(), "a campaign town shows it")

    def test_started_in_the_hideout(self):
        g = Game()
        g.enter("G1_12", "Freythorn", 11)
        self.assertTrue(CP.shown())
        self.assertTrue(CP.where_now("HideoutFelled", "hideout"), "the log's last area: a hideout")
        self.assertFalse(CP.shown())
        self.assertFalse(CP.where_now("HideoutFelled", "hideout"), "nothing changes twice")
        self.assertTrue(CP.where_now("G1_12", "other"))
        self.assertTrue(CP.shown(), "started in a campaign area: it shows")
        CP.cfg()["on"] = False
        self.assertFalse(CP.where_now("HideoutFelled", "hideout"), "the helper off: nothing")


if __name__ == "__main__":
    unittest.main()
