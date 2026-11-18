"""Price check, 3.0.6: Broaden Search for every item (every price check, as bases already do).

  * Too few listings: the orange button is ↔ Broaden Search. Owner (3.0.6 checklist): loosen values and ranges
    first, before removing mods - 10% variance, then 20% - every ticked mod's values 10% looser, then 20% (from
    the item's own values), then a search without the lowest-rated ticked mod (your Rate letter; unrated counts as C;
    a total goes last; the last on a tie). A value you typed is yours: never loosened.
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


def vmod(text, value, sid="explicit.stat_1"):
    m = mod(text, sid=sid)
    m.update(value=value, lo=None, hi=None, min=None, max=None)
    return m


class Loosen(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch("soe2.mods.vfilter", lambda m: dict(m["uval"]) if m.get("uval") else
                            ({"min": m["value"]} if m.get("value") is not None else None))
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_values(self):
        self.assertEqual(engine.loosen_vals({"min": 144}, 10), {"min": 129.0})      # (a Min rounds down)
        self.assertEqual(engine.loosen_vals({"max": -20}, 10), {"max": -18.0})     # (a Max goes up)
        self.assertEqual(engine.loosen_vals({"min": 80, "max": 100}, 20), {"min": 64.0, "max": 120.0})
        self.assertEqual(engine.loosen_vals({"min": 1.5}, 10), {"min": 1.35})

    def test_ladder_10_20_then_a_mod(self):
        life, arm = vmod("+144 to maximum Life", 144), vmod("+345 to Armour", 345, sid="explicit.stat_2")
        rec = {"item": {"mods": [life, arm]}}
        b = engine.broaden_step(rec, [life, arm])
        self.assertEqual(b["loosen"], 10)
        self.assertIn("10%", b["next"])
        engine.apply_loosen(rec, b)
        self.assertEqual(life["uval"]["min"], 129.0)
        b = engine.broaden_step(rec, [life, arm])
        self.assertEqual(b["loosen"], 20)
        engine.apply_loosen(rec, b)
        self.assertEqual(life["uval"]["min"], 115.0)               # 20% of 144, not 10% of 129
        with mock.patch.object(ratemods, "key_for", lambda r, m: m["text"]), \
                mock.patch.object(ratemods, "current", lambda keys: None):
            b = engine.broaden_step(rec, [life, arm])
        self.assertIn("drop", b)

    def test_typed_value_is_yours(self):
        life = vmod("+144 to maximum Life", 144)
        life["uval"] = {"min": 100.0, "max": None}
        self.assertIsNone(engine.loosen_offer({"item": {"mods": [life]}}, [life]))

    def test_exact_roll_never_loosened(self):
        m = vmod("Favours cost 10% increased tribute", 10)
        m["exact"] = True
        self.assertIsNone(engine.loosen_offer({"item": {"mods": [m]}}, [m]))


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
