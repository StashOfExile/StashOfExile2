"""Boss Ledger's numbers (a start: no page yet): runs, fastest, usual time, deaths and logged chase drops per arena."""
import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("HOME", tempfile.mkdtemp(prefix="soe2-bl-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import bossledger as BL


def run(key, secs, deaths=0, league="L", at=100, cat="boss"):
    return {"cat": cat, "key": key, "secs": secs, "league": league, "deaths": deaths, "at": at}


class Numbers(unittest.TestCase):
    def test_runs_best_usual_deaths_clean_last(self):
        e = [run("The Burning Monolith", 300, 1, at=10), run("The Burning Monolith", 200, at=30),
             run("The Burning Monolith", 260, 2, at=20), run("Savannah", 90, cat="map")]
        s = BL.stats(e)
        self.assertEqual(list(s), ["The Burning Monolith"], "maps are not bosses")
        self.assertEqual(s["The Burning Monolith"], {"runs": 3, "best": 200, "usual": 260, "deaths": 3, "clean": 1,
                                                     "last": 30})

    def test_usual_of_an_even_count_is_the_middle_two(self):
        self.assertEqual(BL.stats([run("A", 100), run("A", 200)])["A"]["usual"], 150)

    def test_one_league_only(self):
        e = [run("A", 100, league="L"), run("A", 50, league="Standard")]
        self.assertEqual(BL.stats(e, "L")["A"]["best"], 100)
        self.assertEqual(BL.stats(e)["A"]["best"], 50)

    def test_boss_names(self):
        self.assertEqual(BL.boss_of("The Burning Monolith"), "Arbiter of Ash")
        self.assertEqual(BL.boss_of("Somewhere New"), "Somewhere New")


class Drops(unittest.TestCase):
    def setUp(self):
        self.store = {}
        for p in (mock.patch.object(BL, "load_json", lambda f, d=None: self.store.get(f, d)),
                  mock.patch.object(BL, "save_json", lambda f, v: self.store.__setitem__(f, v))):
            p.start()
            self.addCleanup(p.stop)

    def test_a_drop_is_kept_with_its_run(self):
        d = BL.log_drop("Simulacrum of Delusion", " Voices ", 650, "L", now=5)
        self.assertEqual(d, {"arena": "Simulacrum of Delusion", "item": "Voices", "run": 650, "league": "L", "at": 5})
        self.assertEqual(BL.drops(), [d])
        self.assertEqual(BL.drop_words(d), "Voices on run 650")
        self.assertIsNone(BL.log_drop("A", "  ", 1))

    def test_runs_between_two_drops(self):
        a = BL.log_drop("A", "X", 100)
        b = BL.log_drop("A", "X", 650)
        self.assertEqual(BL.runs_between(b, a), 550)
        self.assertEqual(BL.runs_between(a), 100)

    def test_forget(self):
        d = BL.log_drop("A", "X", 3)
        self.assertTrue(BL.forget_drop(d))
        self.assertFalse(BL.forget_drop(d))
        self.assertEqual(BL.drops(), [])

    def test_rows_list_every_arena_ran_ones_first(self):
        BL.log_drop("B", "Thing", 2, "L")
        with mock.patch.object(BL, "arenas", lambda: ["A", "B", "C"]):
            rows = BL.rows([run("B", 100), run("B", 120), run("C", 50)], "L")
        self.assertEqual([r["arena"] for r in rows], ["B", "C", "A"])
        self.assertEqual(rows[0]["drops"][0]["item"], "Thing")
        self.assertEqual((rows[2]["runs"], rows[2]["best"]), (0, None))

    def test_nothing_here_reads_the_game(self):
        src = open(BL.__file__, encoding="utf-8").read().split('"""', 2)[2]
        for word in ("Client.txt", "clipboard", "ImageGrab", "requests", "urllib"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
