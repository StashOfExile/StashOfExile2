"""Game Search shows no developer-only entries and no raw export text (soe2/gamesearch_clean.py, gamecards.py).

    python3.12 -m unittest tests.test_gamesearch_clean          (or tests/runall.sh)"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import gamecards as GC, gamesearch, gamesearch_clean as GX     # noqa: E402


def row(n, g="Skill Gems", t="x", c="Skill Gem", k=""):
    return {"n": n, "g": g, "c": c, "k": k, "t": t}


class DevEntries(unittest.TestCase):
    def test_names(self):
        for bad in ("[DNT] Flame Link", "[DNT-UNUSED] Arcane Archery", "[DNT-Unused] Rune of Chance", "Playtest Slam",
                    "[DNT] UNUSED", "MistRavenCompanionSwoop"):
            self.assertFalse(GX.keep(row(bad)), bad)
        for good in ("Fireball", "Hollow Form", "Atziri's Call", "Waystone (Tier 4)", "of the Hunt"):
            self.assertTrue(GX.keep(row(good)), good)

    def test_gem_without_any_description_is_unfinished(self):
        self.assertFalse(GX.keep(row("Removed Skill", t="")))
        self.assertFalse(GX.keep(row("Styrn's Anthem", "Support Gems", "DNT Description")))
        self.assertTrue(GX.keep(row("Holy Rod", "Weapons", "")))             # (an item can have no text)

    def test_hide_list_by_name(self):
        hid = GX.hide_names([{"name": "Fishing Rod", "group": "Other Items", "reason": "x"}, {"id": "a/b", "reason": "y"}])
        self.assertFalse(GX.keep(row("Fishing Rod", "Other Items"), hid))
        self.assertTrue(GX.keep(row("Fishing Rod", "Weapons"), hid))         # (only in that group)

    def test_fishing_rod_only_mods_are_gone(self):
        fish = "(30-50)% increased Fishing Range | ilvl 1 | can roll on: fishing_rod"
        self.assertFalse(GX.keep(row("of Flight", "Modifiers", fish, "Suffix")))
        shared = "+(5-8) to Strength | ilvl 1 | can roll on: ring, fishing_rod"
        self.assertTrue(GX.keep(row("of the Brute", "Modifiers", shared, "Suffix")))
        rows = [dict(r, ln=r["n"].lower()) for r in gamesearch.load()["rows"]]
        self.assertFalse([r for r in rows if r["g"] == "Modifiers" and GX.rolls_only_on_gone(r)])
        self.assertFalse([r for r in rows if r["g"] == "Modifiers" and "Fishing" in r["t"]])

    def test_text_is_tidied(self):
        self.assertEqual(GX.clean_text("DNT Fill me in DNT-UNUSED Supports Spells you use yourself"),
                         "Supports Spells you use yourself")
        self.assertEqual(GX.clean_text("DNT-UNUSED triggered_hoarfrost Supports Skills which create Ice Crystals."),
                         "Supports Skills which create Ice Crystals.")
        self.assertEqual(GX.clean_text("DNT Description"), "")
        self.assertEqual(GX.clean_text("Plain text | second"), "Plain text | second")      # (idempotent)

    def test_markup_becomes_words(self):
        raw = ("<<ExpedRuneFire>><rgb(219,217,206)>{Fire Rune} <font:'fontin'>{<italic>{<rgb(110,87,66)>{Monsters gain:}}} "
               "<rgb(135,134,253)>{Extra Fire Damage} <rgb(135,134,253)>{Ignited Ground Trails}")
        self.assertEqual(GX.strip_markup(raw), "Fire Rune | Monsters gain: Extra Fire Damage, Ignited Ground Trails")
        out = GX.clean_rows([row("Fire Rune", "Keywords & Mechanics", raw, "Keyword")])
        self.assertEqual(out[0]["t"], "Monsters gain: Extra Fire Damage, Ignited Ground Trails")


class Loaded(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gamesearch._DATA["rows"] = None
        cls.d = gamesearch.load()

    def test_no_dev_rows_in_any_category(self):
        for r in self.d["rows"]:
            self.assertFalse(re.search(r"DNT|UNUSED|Playtest", r["n"], re.I), r["n"])
            self.assertNotIn("DNT", r["t"], r["n"])
            self.assertNotIn("<<", r["t"], r["n"])

    def test_fishing_rod_and_data_file_rows_are_gone(self):
        self.assertFalse([r for r in self.d["rows"] if r["n"] == "Fishing Rod"])
        self.assertFalse([r for r in self.d["rows"] if r["g"] == "Leagues" and r["c"] == "Data File Version"])
        self.assertTrue([r for r in self.d["rows"] if r["g"] == "Leagues"])             # (the league itself stays)

    def test_counts_follow(self):
        other = [r for r in self.d["rows"] if r["g"] == "Other Items"]
        self.assertEqual(len(other), 3)


class Cards(unittest.TestCase):
    def test_internal_ids_are_not_shown(self):
        c = GC.card({"n": "The Iron Citadel", "g": "Pinnacles & Areas", "c": "Citadel", "k": "area", "t": "x", "db": True,
                     "props": [["Area level", "80"], ["Area id", "MapUberBoss_IronCitadel"]], "lines": []})
        self.assertEqual(c["props"], [("Area level", "80")])

    def test_glued_stats_split(self):
        c = GC.card(row("Mantle", "Armour", "+(20-30) to Spirit Armour 218 Energy Shield 61 Movement Speed -400 "
                        "Requires level 70", "Body Armour", "str_int_armour, body_armour"))
        self.assertEqual(c["lines"], ["+(20-30) to Spirit"])
        self.assertEqual(c["props"], [("Armour", "218"), ("Energy Shield", "61"), ("Movement Speed", "−4%")])
        c = GC.card(row("Hybrid", "Modifiers", "(35-38)% increased Spirit +(42-45) to maximum Mana", "Prefix"))
        self.assertEqual(c["lines"], ["(35-38)% increased Spirit", "+(42-45) to maximum Mana"])
        c = GC.card(row("Ring", "Jewellery & Belts", "-2 Prefix Modifiers allowed +2 Suffix Modifiers allowed", "Ring"))
        self.assertEqual(c["lines"], ["-2 Prefix Modifiers allowed", "+2 Suffix Modifiers allowed"])
        c = GC.card(row("Verbs stay", "Armour", "Allies in your Presence have +(3-5)% to all Elemental Resistances"))
        self.assertEqual(len(c["lines"]), 1)

    def test_every_granted_skill_by_name(self):
        c = GC.card(row("Amulet", "Jewellery & Belts", "Grants skill: Metadata/Items/Gems/SkillGemCastOnCritical, "
                        "Metadata/Items/Gem/SkillGemTrinity", "Amulet"))
        self.assertEqual(c["props"], [("Grants skill", "Cast on Critical, Trinity")])
        self.assertNotIn("Metadata", str(c))

    def test_meta_gem_boilerplate_once_and_not_glued(self):
        c = GC.card(row("Fire Spell on Hit", "Spirit Gems",
                        "While active, gains Energy. | Can only socket Fire Spells Triggers all Socketed Spells and loses "
                        "all Energy on reaching maximum Energy", "Meta"))
        self.assertEqual(c["lines"], ["While active, gains Energy.", "Can only socket Fire Spells"])

    def test_rune_series_and_uses(self):
        c = GC.card(row("Rune", "Soul Cores & Runes", "Helmet: 5% x Limit: 1 Aldur's Legacy Requires level 65", "Rune"))
        self.assertIn(("Series", "Aldur's Legacy"), c["props"])
        self.assertEqual(c["lines"], ["Helmet: 5% x"])
        c = GC.card(row("Abyss Tablet", "Endgame Items", "Adds Abysses to a Map 10 uses remaining", "TowerAugmentation"))
        self.assertEqual(c["lines"], ["Adds Abysses to a Map", "10 uses remaining"])
        self.assertEqual(c["kind"], "Tablet")

    def test_casing_and_repeats(self):
        self.assertEqual(GC.nice("Trial of the sekhemas"), "Trial of the Sekhemas")
        c = GC.card({"n": "Generator", "g": "Vaal Temple", "c": "Temple Room", "k": "tier, dynamo", "t": "x", "db": True,
                     "props": [["Tier 1", "Dynamo"], ["Tier 2", "Solar"]], "lines": ["Dynamo → Solar"]})
        self.assertEqual(c["lines"], [])                    # (it only repeated the properties)
        self.assertEqual(c["chips"], [])                    # ("Tier" and "Dynamo" say it twice)
        c = GC.card(row("Apep's Supremacy", "Unique Items", "Unique Focii", "Focii"))
        self.assertEqual((c["kind"], c["lines"]), ("Unique Focus", []))


if __name__ == "__main__":
    unittest.main()
