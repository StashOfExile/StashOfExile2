"""Game Search's item cards (3.0.6): the raw export text becomes a kind, label / value properties, "Requires Level N",
one mod per line and readable tag chips; RePoE's units are fixed (a movement speed penalty in basis points).

    python3.12 -m unittest tests.test_gamecards          (or tests/runall.sh)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import gamecards as GC          # noqa: E402


def row(n, c, k, t, g="Armour"):
    return {"n": n, "g": g, "c": c, "k": k, "t": t}


class Cards(unittest.TestCase):
    def test_body_armour(self):
        c = GC.card(row("Rusted Cuirass", "Body Armour", "str_armour, ezomyte_basetype, body_armour, armour",
                        "Armour 45 Movement Speed -500 Requires level 1"))
        self.assertEqual(c["kind"], "Body Armour · Strength")
        self.assertEqual(c["props"], [("Armour", "45"), ("Movement Speed", "−5%")])      # -500 basis points
        self.assertEqual(c["req"], "Requires Level 1")
        self.assertEqual(c["lines"], [])
        self.assertEqual(c["chips"], [])                      # nothing readable is left: all internal

    def test_units(self):
        self.assertEqual(GC.speed(-500), "−5%")
        self.assertEqual(GC.speed(-300), "−3%")
        self.assertEqual(GC.speed(250), "+2.5%")
        c = GC.card(row("Tower", "Shield", "str_armour, str_shield, shield, armour",
                        "Armour 18 Block 26 Movement Speed -300 Requires level 1 Grants skill: "
                        "Metadata/Items/Gem/SkillGemShieldBlock", g="Off-hand"))
        self.assertIn(("Block", "26%"), c["props"])
        self.assertIn(("Grants skill", "Shield Block"), c["props"])
        self.assertNotIn("Metadata", str(c))

    def test_attributes_and_tags(self):
        self.assertEqual(GC.attribute(["dex_armour"]), "Dexterity")
        self.assertEqual(GC.attribute(["str_dex_armour", "x"]), "Strength/Dexterity")
        self.assertEqual(GC.attribute(["int_armour"]), "Intelligence")
        out = GC.chips("str_armour, ezomyte_basetype, default, not_for_sale, spell, area, map_key_low")
        self.assertEqual(out, ["Strength", "Spell", "Area", "Map Key Low"])
        for hidden in ("ezomyte_basetype", "default", "not_for_sale"):
            self.assertNotIn(hidden, " ".join(out).lower())

    def test_mods_one_per_line_and_numbers_marked(self):
        c = GC.card(row("Soul Core of X", "Soul Core", "",
                        "Helmet: 25% increased Pin duration | Martial Weapon: 40% increased Magnitude Limit: 1",
                        g="Soul Cores & Runes"))
        self.assertEqual(len(c["lines"]), 2)
        self.assertIn(("Limit", "1"), c["props"])
        segs = GC.segments("+(10-19) to maximum Life, 5% more")
        self.assertEqual([s for s, n in segs if n], ["+(10-19)", "5%"])

    def test_modifier_rows(self):
        c = GC.card(row("Hale", "Prefix", "IncreasedLife",
                        "+(10-19) to maximum Life | ilvl 1 | can roll on: body_armour, str_armour, mace",
                        g="Modifiers"))
        self.assertEqual(c["lines"], ["+(10-19) to maximum Life"])
        self.assertIn(("Item Level", "1"), c["props"])
        self.assertIn(("Rolls on", "Body Armour, Strength, Mace"), c["props"])

    def test_usage_text_is_muted(self):
        c = GC.card(row("Whetstone", "StackableCurrency", "quality_currency, currency",
                        "Improves the quality of a weapon Right click this item then left click it to apply it.",
                        g="Currency & Omens"))
        self.assertEqual(c["kind"], "Stackable Currency")
        self.assertEqual(c["lines"], ["Improves the quality of a weapon"])
        self.assertTrue(c["muted"][0].startswith("Right click"))

    def test_database_rows_keep_their_own_fields(self):
        c = GC.card({"n": "Abyss Tablet", "g": "Tablets", "c": "Tablet", "k": "tower_augment_abyss, tablet", "t": "x",
                     "db": True, "props": [["Uses", "10"]], "lines": ["Adds Abysses to a Map"]})
        self.assertEqual(c["props"], [("Uses", "10")])
        self.assertEqual(c["lines"], ["Adds Abysses to a Map"])
        self.assertEqual(c["chips"], [])           # (the type word is the kind; tower_augment_* is internal)


if __name__ == "__main__":
    unittest.main()
