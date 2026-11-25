"""3.3.0: switching sharing off never deletes times from the board, and a big payload goes up in parts the board
accepts."""
import inspect
import json
import unittest

from soe2 import leaderboard as LB


def entry(i):
    return {"cat": "map", "key": f"Map Number {i % 92}", "secs": 100.0 + i, "league": "Forbidden Rites",
            "cls": "Warrior", "level": 80, "deaths": 0, "at": 1795478400}


class Parts(unittest.TestCase):
    def test_every_part_fits_the_board(self):
        data = [entry(i) for i in range(400)]
        parts = LB.parts(data)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLess(len(json.dumps({"entries": p})), 24000)

    def test_nothing_lost_and_order_kept(self):
        data = [entry(i) for i in range(400)]
        self.assertEqual([e for p in LB.parts(data) for e in p], data)

    def test_small_payload_is_one_part(self):
        data = [entry(i) for i in range(20)]
        self.assertEqual(LB.parts(data), [data])

    def test_empty(self):
        self.assertEqual(LB.parts([]), [])


class SwitchOffKeepsTimes(unittest.TestCase):
    def test_no_switch_calls_the_delete(self):
        from soe2 import app, leaderboard_page
        self.assertNotIn("lb_forget", inspect.getsource(app))
        self.assertNotIn("lb_forget", inspect.getsource(leaderboard_page))


if __name__ == "__main__":
    unittest.main()
