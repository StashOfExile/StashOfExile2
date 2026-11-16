"""Price check, 3.0.6: Broaden Search for every item (owner: "for all price checks, similar to how we did bases").

  * Too few listings and two or more mods ticked: the orange button is ↔ Broaden Search; its step searches without
    the lowest-rated ticked mod (your Rate letter; unrated counts as C; a total goes last; the last on a tie).
  * A box or tick changed since: the button says Search again (filters changed) instead.

    python3.12 -m unittest tests.test_broaden_all          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-broaden-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import engine, ratemods                         # noqa: E402
from soe2 import pricecheck_page as PC                    # noqa: E402


def mod(text, sid="explicit.stat_1", group="explicit", kind="Prefix"):
    return {"text": text, "shown": text, "sid": sid, "group": group, "kind": kind, "mid": hash(text) % 997}


class FewerOffer(unittest.TestCase):
    def offer(self, mods, grades):
        with mock.patch.object(ratemods, "key_for", lambda rec, m: m["text"]), \
                mock.patch.object(ratemods, "current", lambda keys: grades.get(keys[0])):
            return engine.fewer_offer({"item": {"mods": mods}}, mods)

    def test_lowest_rated_goes(self):
        life, armour, res = mod("+144 to maximum Life"), mod("+345 to Armour"), mod("+42% to Lightning Resistance")
        b = self.offer([life, armour, res], {"+144 to maximum Life": "A", "+345 to Armour": "D",
                                             "+42% to Lightning Resistance": "B"})
        self.assertEqual(b["text"], "+345 to Armour")
        self.assertTrue(b["next"].startswith("without +345 to Armour"))

    def test_unrated_counts_as_c(self):
        b = self.offer([mod("a"), mod("b")], {"a": "B"})
        self.assertEqual(b["text"], "b")
        b = self.offer([mod("a"), mod("b")], {"a": "D"})
        self.assertEqual(b["text"], "a")

    def test_total_last_and_tie_last(self):
        tot = mod("87% total Elemental Resistance", sid="pseudo.pseudo_total_elemental_resistance", group="pseudo")
        b = self.offer([tot, mod("x"), mod("y")], {})
        self.assertEqual(b["text"], "y")                         # (a tie: the last on the card)
        b = self.offer([tot, mod("x")], {"x": "S"})
        self.assertEqual(b["text"], "x")                         # the total stays while anything else can go

    def test_one_mod_nothing_to_drop(self):
        self.assertIsNone(self.offer([mod("only")], {}))


class Button(unittest.TestCase):
    def test_words(self):
        rec = {"state": "done", "broaden": {"next": "without +345 to Armour", "drop": "k"}}
        self.assertEqual(PC.search_word(rec), PC.BROADEN)
        self.assertIn("without +345 to Armour", PC.search_tip(rec))
        rec["changed"] = True
        self.assertNotEqual(PC.search_word(rec), PC.BROADEN)

    def test_no_second_name(self):
        src = open(os.path.join(ROOT, "soe2", "pricecheck_page.py"), encoding="utf-8").read()
        self.assertNotIn("Search with fewer mods", src)


if __name__ == "__main__":
    unittest.main()
