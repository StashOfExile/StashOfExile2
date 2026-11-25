"""3.3.0 owner: the Dashboard's greetings - by time of day, the owner's kept lines, name-only lines, pet names.

    python3.12 -m unittest tests.test_greetings          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-gr-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import greetings as GR          # noqa: E402
from soe2.config import SETTINGS          # noqa: E402


def at(hour):
    return time.mktime((2026, 11, 23, hour, 30, 0, 0, 0, -1))


class Greetings(unittest.TestCase):
    def setUp(self):
        self.old = SETTINGS.get("greet_playful")
        SETTINGS.pop("greet_playful", None)

    def tearDown(self):
        SETTINGS.pop("greet_playful", None) if self.old is None else SETTINGS.__setitem__("greet_playful", self.old)

    def test_time_of_day(self):
        self.assertEqual([GR.slot(at(h)) for h in (5, 11, 12, 17, 18, 22, 23, 4)],
                         ["morning", "morning", "afternoon", "afternoon", "evening", "evening", "late", "late"])

    def test_the_owners_lines_are_in(self):
        self.assertIn("Morning, {name}. That stash won't sort itself ;)", GR.MORNING)
        self.assertIn("Oi bruv, did you eat today?", GR.MORNING)
        self.assertIn("Sleep? Nah, go off sis, get to mappin'", GR.LATE)
        for line in ("Sup baddie", "Haaaayyyyyyyyy girl haaaaaayyyyyyyyyy", "Yaas king let's get them divs",
                     "That's a good exile.", "Now who's a good exile?", "Orbe Divino!"):
            self.assertIn(line, GR.ANY)
        every = GR.MORNING + GR.AFTERNOON + GR.EVENING + GR.LATE + GR.ANY
        for dropped in ("Coffee first, maps second, {name}", "Mother is mothering. And mapping",
                        "Q4 objectives: loot. Good morning, {name}"):
            self.assertNotIn(dropped, every)
        self.assertEqual(len(every), len(set(every)), "no line twice")
        self.assertGreater(len(every), 90)

    def test_name_only_lines_need_a_name(self):
        for line in GR.NAME_ONLY:
            self.assertIn(line, GR.MORNING + GR.AFTERNOON + GR.EVENING + GR.LATE + GR.ANY)
        for part in GR.POOLS:
            for line in GR.lines(part, named=False):
                self.assertNotIn(line, GR.NAME_ONLY)
        seen = {GR.greeting("", at(9), seed=i) for i in range(600)}
        self.assertFalse([g for g in seen if "Exile's biggest fan" in g or "named Exile" in g or "Exile o'clock" in g])
        named = {GR.greeting("Worm", at(15), seed=i) for i in range(900)}
        self.assertIn("This app is Worm's biggest fan", named)

    def test_it_stays_put_and_fits_the_hour(self):
        self.assertEqual(GR.greeting("Worm", at(9)), GR.greeting("Worm", at(9)))
        late = {GR.greeting("Worm", at(2), seed=i) for i in range(400)}
        self.assertFalse([g for g in late if g.startswith(("Good morning", "Good afternoon", "Mornin'"))])
        morning = {GR.greeting("Worm", at(8), seed=i) for i in range(400)}
        self.assertIn("Rise and grind, Worm", morning)

    def test_pet_names_are_rare(self):
        from unittest import mock
        with mock.patch.object(GR, "PET_CHANCE", 0.0):
            plain = [GR.greeting("Worm", at(20), seed=i) for i in range(4000)]
        mixed = [GR.greeting("Worm", at(20), seed=i) for i in range(4000)]
        pets = sum(1 for a, b in zip(plain, mixed) if a != b)
        self.assertTrue(40 < pets < 300, pets)
        swapped = next(b for a, b in zip(plain, mixed) if a != b)
        self.assertNotIn("Worm", swapped)
        self.assertTrue(any(p in swapped for p in GR.PET_NAMES))

    def test_the_switch_gives_plain_ones(self):
        SETTINGS["greet_playful"] = False
        self.assertEqual(GR.greeting("Worm", at(9)), "Good morning, Worm")
        self.assertEqual(GR.greeting("", at(15)), "Good afternoon, Exile")
        self.assertEqual(GR.greeting("", at(2)), "Good evening, Exile")



class NoRepeats(unittest.TestCase):
    """3.3.0 owner: a person should not see the same greeting again."""

    def setUp(self):
        self.was = {k: SETTINGS.get(k) for k in ("greet_playful", GR.SEEN_KEY, GR.NOW_KEY)}
        self.start = GR._START
        SETTINGS["greet_playful"] = True
        SETTINGS.pop(GR.SEEN_KEY, None)
        SETTINGS.pop(GR.NOW_KEY, None)

    def tearDown(self):
        GR._START = self.start
        for k, v in self.was.items():
            if v is None:
                SETTINGS.pop(k, None)
            else:
                SETTINGS[k] = v

    def test_it_stays_put_while_you_look_at_it(self):
        a = GR.greeting("Worm", at(9))
        self.assertEqual([GR.greeting("Worm", at(9)) for _ in range(5)], [a] * 5)

    def test_each_app_start_shows_one_not_seen_before(self):
        every = [r for r in list(GR.POOLS["morning"]) + list(GR.ANY)]
        seen = []
        for n in range(len(every) + 12):
            GR._START = self.start + 1000 * (n + 1)
            GR.greeting("Worm", at(9))
            seen.append(SETTINGS[GR.NOW_KEY]["line"])
        first = seen[:len(every)]
        self.assertEqual(sorted(first), sorted(every), "every morning line once before any comes back")
        self.assertFalse([i for i in range(1, len(seen)) if seen[i] == seen[i - 1]], "never the same twice running")

    def test_when_all_were_seen_it_starts_over_without_the_last_one(self):
        rows = ["a", "b", "c"]
        SETTINGS[GR.SEEN_KEY] = ["a", "b", "c"]
        self.assertEqual(GR.fresh(rows, "k1"), ["a", "b"])
        SETTINGS[GR.SEEN_KEY] = ["a"]
        self.assertEqual(GR.fresh(rows, "k1"), ["b", "c"])
        SETTINGS[GR.SEEN_KEY] = ["a", "b"]
        self.assertEqual(GR.fresh(["a", "b"], "k1", ["a", "b", "z"]), ["z"], "nothing new here: the wider list")

    def test_tests_with_a_seed_do_not_touch_what_was_seen(self):
        GR.greeting("Worm", at(9), seed=3)
        self.assertNotIn(GR.NOW_KEY, SETTINGS)


if __name__ == "__main__":
    unittest.main()
