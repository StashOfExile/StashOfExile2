"""3.3.0 owner: Mod Lab lists every unique with its mods (uniquedata.json, from Path of Building's data)."""
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from soe2 import gearbook as GB  # noqa: E402
from soe2 import uniquedata as UD  # noqa: E402
import build_uniquedata as BU  # noqa: E402


class Builder(unittest.TestCase):
    def test_current_version_only_and_every_choice(self):
        u = BU.parse_block("""
            The Anvil
            Bloodstone Amulet
            Variant: Pre 0.2.0
            Variant: Current
            League: Somewhere
            Implicits: 1
            {tags:life}+(30-40) to maximum Life
            {variant:1}20% increased Block chance
            {variant:2}25% increased Block chance
            Grants Skill: Level 20 Thing
        """)
        self.assertEqual(u["implicit"], ["+(30-40) to maximum Life"])
        self.assertEqual(u["explicit"], ["25% increased Block chance", "Grants Skill: Level 20 Thing"])
        m = BU.parse_block("""
            Mageblood
            Utility Belt
            Variant: Legacy of Ruby
            Variant: Legacy of Gold
            Selected Alt Variant: 2
            Has Alt Variant: true
            Implicits: 0
            {variant:1}Legacy of Ruby
            {variant:2}Legacy of Gold
        """)
        self.assertEqual(m["explicit"], ["Legacy of Ruby", "Legacy of Gold"], "a choice keeps every option")

    def test_the_shipped_file(self):
        with open(os.path.join(ROOT, "uniquedata.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.assertGreater(len(d["uniques"]), 400)
        for name, u in d["uniques"].items():
            for line in u["implicit"] + u["explicit"]:
                self.assertNotRegex(line, r"^(Variant|League|Source|Implicits|Selected|Has Alt|Version):", name)
                self.assertNotIn("{", line, name)
            self.assertIn(u["group"], UD.GROUP_ORDER, name)


class Corruption(unittest.TestCase):
    def test_a_base_gets_what_its_tags_allow_first_tag_decides(self):
        self.assertTrue(BU.rolls_on([{"tag": "amulet", "weight": 1}, {"tag": "default", "weight": 0}], {"amulet", "default"}))
        self.assertFalse(BU.rolls_on([{"tag": "ring", "weight": 1}, {"tag": "default", "weight": 0}], {"amulet", "default"}))
        self.assertFalse(BU.rolls_on([{"tag": "default", "weight": 0}, {"tag": "amulet", "weight": 1}], {"amulet", "default"}))
        self.assertEqual(BU.plain("(20-10)% reduced [Attribute|Attribute] Requirements"), "(10-20)% reduced Attribute Requirements")
        self.assertEqual(BU.plain("Leech 3% of [Physical] [Attack] Damage"), "Leech 3% of Physical Attack Damage")

    def test_the_shipped_file_has_them(self):
        with open(os.path.join(ROOT, "uniquedata.json"), encoding="utf-8") as f:
            d = json.load(f)["uniques"]
        self.assertGreater(sum(1 for u in d.values() if u.get("corruption")), 300)
        for name, u in d.items():
            for line in u.get("corruption") or []:
                self.assertNotIn("[", line, name)


class Rows(unittest.TestCase):
    def setUp(self):
        UD.reset({"Astramentis": {"base": "Stellar Amulet", "kind": "jewelry", "group": "Amulets",
                                  "implicit": ["+(5-7) to all Attributes"],
                                  "explicit": ["+(50-100) to all Attributes", "-4 Physical Damage taken from Attack Hits"],
                                  "corruption": ["+1 to Level of all Skills"]}})
        self.addCleanup(UD.reset)

    def test_every_line_and_the_price_checked_ones_are_one_rule(self):
        seen = {"Astramentis": {"lines": {GB.unique_key("Astramentis", "+73 to all Attributes"):
                                          {"text": "+73 to all Attributes", "kind": "Explicit"},
                                          GB.unique_key("Astramentis", "10% increased Spirit"):
                                          {"text": "10% increased Spirit", "kind": "Explicit"}}}}
        with mock.patch.object(GB, "store", lambda: seen):
            rows = GB.unique_rows("Astramentis")
            # the implicit and the explicit all Attributes share one wording, so they are one rule and one row
            self.assertEqual([r["text"] for r in rows], ["+(5-7) to all Attributes",
                                                          "-4 Physical Damage taken from Attack Hits",
                                                          "10% increased Spirit",
                                                          "Corrupted: +1 to Level of all Skills"])
            self.assertEqual(rows[-1]["key"], GB.unique_key("Astramentis", "+1 to Level of all Skills"),
                             "the same rule as the line copied off a corrupted item")
            self.assertEqual(rows[0]["kind"], "Implicit")
            self.assertEqual(GB.all_uniques(), ["Astramentis"])

    def test_a_price_checked_unique_the_data_lacks_still_shows(self):
        with mock.patch.object(GB, "store", lambda: {"New Thing": {"lines": {}}}):
            self.assertEqual(GB.all_uniques(), ["Astramentis", "New Thing"])

    def test_ranges_key_the_same_as_a_rolled_line(self):
        self.assertEqual(UD.as_rolled("Adds (3-5) to (10-15) Fire Damage"), "Adds 3 to 10 Fire Damage")
        self.assertEqual(GB.unique_key("x", UD.as_rolled("(25-50)% increased Armour")),
                         GB.unique_key("x", "31% increased Armour"))
        self.assertEqual(UD.group_of("Astramentis"), "Amulets")
        self.assertEqual(UD.group_of("Unknown"), UD.OTHER)


if __name__ == "__main__":
    unittest.main()
