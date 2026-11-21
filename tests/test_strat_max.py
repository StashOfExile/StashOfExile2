"""Farming Strategies: Max next to Min for tablets and waystones made by hand. The trade link, Made for you and Check
cost send both limits the way Price Checks does; Min alone still works; Max stays on this PC, the board never gets it.

    python3.12 -m unittest tests.test_strat_max"""
import json
import os
import sys
import tempfile
import unittest
import urllib.parse

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import moneymakers as MM, stratcost  # noqa: E402


def q_of(url):
    return json.loads(urllib.parse.unquote(url.split("?q=", 1)[1]))


class Values(unittest.TestCase):
    def test_value_range(self):
        self.assertEqual(MM.value_range(5, 9), {"min": 5, "max": 9})
        self.assertEqual(MM.value_range(5, None), {"min": 5})
        self.assertEqual(MM.value_range(None, 9), {"max": 9})
        self.assertIsNone(MM.value_range())


class Waystone(unittest.TestCase):
    def card(self, lo, hi):
        name = MM.hand_props()[1]
        return MM.hand_card("waystone", tier=15, props={name: lo} if lo else {},
                            props_max={name: hi} if hi else None), name

    def filters(self, card):
        it = MM.card_item(card)
        return q_of(MM.item_trade_link("Standard", it))["query"]["filters"]["map_filters"]["filters"], it

    def test_min_and_max(self):
        c, _name = self.card("30", "60")
        flt, it = self.filters(c)
        vals = [v for k, v in flt.items() if k != "map_tier"]
        self.assertEqual(vals, [{"min": 30, "max": 60}])
        self.assertEqual(flt["map_tier"], {"min": 15, "max": 15})
        q, _k, _w = stratcost.query(it)
        self.assertIn({"min": 30, "max": 60}, q["query"]["filters"]["map_filters"]["filters"].values())

    def test_min_alone(self):
        c, _name = self.card("30", None)
        flt, it = self.filters(c)
        self.assertEqual([v for k, v in flt.items() if k != "map_tier"], [{"min": 30}])
        self.assertNotIn("key_max", it)


class Tablet(unittest.TestCase):
    def setUp(self):
        self.tpl = "(10—15)% increased Rarity of Items found in your Maps"

    def test_line_keeps_min_and_card_keeps_max(self):
        c = MM.hand_card("tablet", base="Breach Tablet", mods=[(self.tpl, "12", "14")])
        line = c["mods"][0]
        self.assertTrue(line.startswith("12%"))
        self.assertEqual(c["maxes"], {line: 14})
        it = MM.card_item(c)
        self.assertEqual(it["key_max"], {line: 14})
        back = MM.item_card(it)
        self.assertEqual(back["maxes"], {line: 14})

    def test_trade_link_sends_both(self):
        c = MM.hand_card("tablet", base="Breach Tablet", mods=[(self.tpl, "12", "14")])
        it = MM.card_item(c)
        old = MM.stat_id
        MM.stat_id = lambda line: "explicit.stat_rarity"
        try:
            q = q_of(MM.item_trade_link("Standard", it))
            self.assertEqual(q["query"]["stats"][0]["filters"][0]["value"], {"min": 12, "max": 14})
            mfy = MM.made_for_you("tablet", [c], "Standard", sid_of=lambda line: "explicit.stat_rarity")
            self.assertEqual(q_of(mfy["url"])["query"]["stats"][0]["filters"][0]["value"], {"min": 12, "max": 14})
            sq, _k, _w = stratcost.query(it)
            self.assertEqual(sq["query"]["stats"][0]["filters"][0]["value"], {"min": 12, "max": 14})
        finally:
            MM.stat_id = old

    def test_min_alone_unchanged(self):
        c = MM.hand_card("tablet", base="Breach Tablet", mods=[(self.tpl, "12")])
        it = MM.card_item(c)
        old = MM.stat_id
        MM.stat_id = lambda line: "explicit.stat_rarity"
        try:
            q = q_of(MM.item_trade_link("Standard", it))
            self.assertEqual(q["query"]["stats"][0]["filters"][0]["value"], {"min": 12})
            sq, _k, _w = stratcost.query(it)
            self.assertNotIn("value", sq["query"]["stats"][0]["filters"][0])   # Check cost as before
        finally:
            MM.stat_id = old


class Board(unittest.TestCase):
    def test_max_stays_on_this_pc(self):
        from soe2.moneymakers_page import MoneyMakersPage
        sent = []
        data = {"name": "x", "items": [{"kind": "tablet", "base": "Breach Tablet", "key_mods": ["a"],
                                        "key_max": {"a": 3}}]}
        MoneyMakersPage.mm_board_send(None, lambda d: (sent.append(d), (True, ""))[1], data)
        self.assertNotIn("key_max", sent[0]["items"][0])
        self.assertIn("key_max", data["items"][0])


if __name__ == "__main__":
    unittest.main()
