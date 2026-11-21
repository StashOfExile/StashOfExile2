"""3.0.6 (owner: a T4 and a T1 max Mana are worth different amounts - automatic, nothing to set): when a search has
to leave mods out, a worse roll goes first, and a roll of T4 or worse counts one letter lower."""
import unittest

from soe2 import mods as M
from soe2 import engine as E


class RollTierDrop(unittest.TestCase):
    def test_roll_tier_read(self):
        self.assertEqual(M.roll_tier({"tier": "4"}), 4)
        self.assertIsNone(M.roll_tier({"tier": None}))
        self.assertIsNone(M.roll_tier({}))

    def test_same_letter_worse_roll_first(self):
        self.assertGreater(M.drop_rank(1, {"tier": "5"}), M.drop_rank(1, {"tier": "1"}))

    def test_t4_counts_a_letter_lower(self):
        a_t4 = M.drop_rank(M.tier_rank("A"), {"tier": "4"})
        b_t1 = M.drop_rank(M.tier_rank("B"), {"tier": "1"})
        self.assertEqual(a_t4[0], b_t1[0])               # A at T4 sits with B
        self.assertGreater(a_t4, b_t1)                   # and goes before a B at T1

    def test_d_stays_d(self):
        self.assertEqual(M.drop_rank(M.tier_rank("D"), {"tier": "9"})[0], M.tier_rank("D"))

    def test_broaden_offers_the_worse_roll(self):
        rec = {"item": {"class": "Gloves", "mods": []}}
        ticked = [{"sid": "explicit.a", "text": "+118 to maximum Mana", "tier": "1", "shown": "Mana"},
                  {"sid": "explicit.b", "text": "+60 to maximum Mana", "tier": "5", "shown": "Other mana"}]
        from soe2 import ratemods
        old_cur, old_key = ratemods.current, ratemods.key_for
        try:
            ratemods.current = lambda keys: "B"
            ratemods.key_for = lambda rec, m: m["sid"]
            off = E.fewer_offer(rec, ticked)
        finally:
            ratemods.current, ratemods.key_for = old_cur, old_key
        self.assertEqual(off["text"], "+60 to maximum Mana")


if __name__ == "__main__":
    unittest.main()
