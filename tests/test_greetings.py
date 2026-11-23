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
                     "That's a good exile.", "Now who's a good exile?"):
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


if __name__ == "__main__":
    unittest.main()
