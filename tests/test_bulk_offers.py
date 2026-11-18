"""3.0.6 (a user's 17 Greater Essence of Battle priced 12 div each; 6 sell for 1 chaos): the bulk exchange's price
needs MIN_OFFERS offers; exalted and chaos are asked before divine; one odd listing is never the price."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import bulk  # noqa: E402


def offers(pairs):
    return {"a": {"listing": {"offers": [{"exchange": {"amount": pay}, "item": {"amount": give, "stock": give}}
                                         for pay, give in pairs]}}}


class Offers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = bulk.FILE
        bulk.FILE = os.path.join(self.tmp, "bulk.json")

    def tearDown(self):
        bulk.FILE = self.old

    def run_price(self, answers):
        asked = []

        def call(_m, _u, json=None):
            have = json["query"]["have"][0]
            asked.append(have)
            return {"result": answers.get(have, {})}
        rate = {"chaos": 0.05}
        got = bulk.price("L", "greater-essence-of-battle-" + str(id(answers)), lambda a, c: a * rate[c], call)
        return got, asked

    def test_one_odd_divine_listing_is_not_a_price(self):
        got, asked = self.run_price({"divine": offers([(12, 1)])})
        self.assertIsNone(got)
        self.assertEqual(asked, ["chaos", "divine"], "both asked")

    def test_the_cheaper_of_chaos_and_divine(self):
        got, _ = self.run_price({"chaos": offers([(1, 6)] * 4), "divine": offers([(12, 1), (11, 1), (13, 1)])})
        self.assertEqual(got[2], "chaos")
        got, _ = self.run_price({"chaos": offers([(10, 1)] * 4), "divine": offers([(1, 4)] * 4)})
        self.assertEqual(got[2], "divine", "0.25 div beats 10 chaos (0.5 div)")

    def test_chaos_offers_price_it(self):
        got, _ = self.run_price({"chaos": offers([(1, 6), (1, 6), (1, 5), (1, 6)]), "divine": offers([(12, 1)])})
        self.assertAlmostEqual(got[0], 0.05 / 6, places=4)
        self.assertEqual(got[2], "chaos")


if __name__ == "__main__":
    unittest.main()
