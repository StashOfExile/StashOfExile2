"""3.0.6: regression tests for screen reads that missed in real play - one per cause. Only the misread game text is
used here (what the OCR returned for a line of the game), nothing about the player."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PIL import Image  # noqa: E402

from soe2 import hover_page as HP, medallions as M, remnant as RM, rumours as RU, temple as TM  # noqa: E402


class TempleConsoleCount(unittest.TestCase):
    """The small icon beside "18/60" read as a dot and a 4 (".418/60")."""

    def test_icon_read_as_a_digit(self):
        for text, want in ((".418/60", 18), (".412/60", 12), (".415/60", 15), ("418 / 60", 18)):
            self.assertEqual(TM.parse_console([(text, (0, 0, 9, 9))]), (want, 60), text)

    def test_plain_counts_unchanged(self):
        for text, want in (("18/60", 18), ("54/60", 54), ("0/60", 0), ("6/60", 6)):
            self.assertEqual(TM.parse_console([(text, None)]), (want, 60), text)

    def test_no_guessing(self):
        self.assertIsNone(TM.parse_console([("106/60", None)]))       # what is left would start with a 0
        self.assertIsNone(TM.parse_console([("409/60", None)]))       # one digit left: a guess
        self.assertIsNone(TM.parse_console([(".418/60", None)], most=100))
        self.assertIsNone(TM.parse_console([("LAST MAP'S | 0 div", None)]))


class MedallionTitles(unittest.TestCase):
    def test_name_with_stray_letters(self):
        for text, want in (("ESTAZU NTI rs MEDALLION", "Estazunti's Medallion"),
                           ("~ ESTAZU NTI 5 MEDALLION", "Estazunti's Medallion"),
                           ("UROMOTY S MEDALLION.", "Uromoti's Medallion"),
                           ("ZANTIP MEDALLION", "Zantipi's Medallion"),
                           ("HAYOXI'S MEDALLION”", "Hayoxi's Medallion")):
            self.assertEqual(M.name_of(text), want, text)

    def test_not_a_name(self):
        for text in ("ESTATE $ MEDALLION.", "MEDALLIONS (6/6)", "THIS MEDALLION CAN ONLY BE USED ON AN INACTIVE TEMPLE"):
            self.assertIsNone(M.name_of(text), text)

    def test_panel_title_counts(self):
        for text, want in (("MEDALLIONS 66) >]", (6, 6)), ("MEDALLIONS 5 (6/6) | >!", (6, 6)),
                           ("MEDALLIONS 5 (4/6). Pl", (4, 6)), ("WorKSHOP MEDALLIONS (4/6)", (4, 6)),
                           ("VAULT OF REVERENCE MEDALLIONS (6/6)", (6, 6)), ("MEDALLIONS (6/6) | eal", (6, 6)),
                           ("MEDALLIONS 6/6) >!", (6, 6))):
            self.assertEqual(M.parse([(text, (100, 10, 500, 40))])["count"], want, text)

    def test_title_left_edge_skips_a_neighbors_name(self):
        head = M.parse([("PROSTHETIC RESEARCH MEDALLIONS (6/6) }", (0, 10, 400, 40))])["head"]
        self.assertGreater(head[0], 100)

    def test_own_sentence_is_not_a_title(self):
        for text in ("Medallions 6/6: Reroll restricted, Add room (Commander)", "Medallions 5/6: Add room (Commander), Add"):
            self.assertIsNone(M.parse([(text, None)])["count"], text)


class MedallionByWhatItDoes(unittest.TestCase):
    def names(self, *texts):
        return HP.medal_names([(t, (0, 0, 9, 9)) for t in texts])[0]

    def test_commas_inside_the_line(self):
        self.assertEqual(self.names("USE TO PREVENT THE, NEXT DESTABILISATION OF A ROOM"), [("Juatalotli's Medallion", None)])
        self.assertEqual(self.names("UsE TO ADD, ROOM; ARMOURY"), [("Uromoti's Medallion", "Armoury")])

    def test_restricted_room_medallions(self):
        self.assertEqual(self.names("USE TO PLACE AN ADDITIONAL RESTRICTED ROOM CARD:AFTER", "DEFEATING THE ARCHITECT"),
                         [("Estazunti's Medallion", None)])
        self.assertEqual(self.names("Apo UsE TO REROLL A RESTRICTED ROOM IN THE TEMPLE"), [("Hayoxi's Medallion", None)])

    def test_title_strip_above_the_first_use_to_line(self):
        """The tooltip's title bar was lost in the one big read; it is read on its own from the same picture."""
        img = Image.new("RGB", (1000, 600), (20, 20, 20))

        def ocr(pic):
            if pic.size == (1000, 600):
                return [("/ THIS MEDALLION CAN ONLY BE USED ON AN INACTIVE TEMPLE", (100, 300, 900, 330)),
                        ("USE TO PLACE AN ADDITIONAL RESTRICTED ROOM CARD AFTER", (100, 200, 900, 230))]
            return [("~ ESTAZU NTI rs MEDALLION", (10, 10, 300, 40))]
        lines = HP.read_medals(img, 1440, ocr)
        self.assertEqual(HP.medal_names(lines)[0], [("Estazunti's Medallion", None)])
        strip = HP.title_above(img, [("USE TO PLACE AN ADDITIONAL", (100, 200, 900, 230))], ocr, 1440)
        self.assertTrue(strip and strip[0][1][1] < 200)           # (placed above the line, in the part's pixels)
        self.assertEqual(HP.title_above(img, [("nothing here", (0, 0, 5, 5))], ocr, 1440), [])


class RemnantLines(unittest.TestCase):
    def test_stray_letters_before_a_count(self):
        self.assertEqual(RM.split_qty("fly lx Warding Rune of Armature"), ("Warding Rune of Armature", 1))
        self.assertEqual(RM.split_qty("IOX Divine Orb"), ("Divine Orb", 10))
        self.assertTrue(RM.explicit_qty("fly lx Warding Rune of Armature"))
        self.assertFalse(RM.explicit_qty("Skill Level 20: Conductive Runes"))

    def test_gem_line_with_a_broken_kind_word(self):
        self.assertEqual(RM.gem_line("S ill Level 20: Rain of Blades"), ("skill", 20, "Rain of Blades"))
        self.assertEqual(RM.gem_line("' JUå@Skill Level 20: Rain of Blad"), ("skill", 20, "Rain of Blad"))
        self.assertEqual(RM.gem_line("Skill Level 20: Repulsion"), ("skill", 20, "Repulsion"))
        self.assertIsNone(RM.gem_line("skill Level Runes"))
        self.assertIsNone(RM.gem_line("Monsters gain:"))
        self.assertIsNone(RM.gem_line("Skill Level 2"))

    def test_gem_names_snap_to_the_trade_sites_names(self):
        vocab = {"Rain of Blades", "Wardbound Minions", "Skyfall", "Animus Exchange", "Frostflame Nova", "Voltaic Barrier"}
        for read, want in (("Rain of Blade", "Rain of Blades"), ("Wardbound Minion", "Wardbound Minions"),
                           ("Skyfall ill", "Skyfall"), ("Animus Exchan e", "Animus Exchange"),
                           ("rain of blades", "Rain of Blades")):
            self.assertEqual(RM.snap_gem(read, vocab), want, read)
        self.assertEqual(RM.snap_gem("Hollow Shell", vocab), "Hollow Shell")      # not listed: as read, never another gem
        self.assertEqual(RM.snap_gem("Voltaic Barrier", None), "Voltaic Barrier")

    def test_priced_lines_end_to_end(self):
        names = RM.Names(["Exalted Orb", "Orb of Alchemy", "Greater Chaos Orb", "Chaos Orb"])
        asked = []

        def gem_value(kind, level, name):
            asked.append((kind, level, name))
            return None, True
        rows = RM.price_lines([("S ill Level 20: Rain of Blade", (0, 0, 9, 9)), ("2x Exalted", (0, 10, 9, 19)),
                               ("IOX Orb of Alchemy", (0, 20, 9, 29))], names, lambda n: 1.0, gem_value,
                              gem_vocab={"Rain of Blades"})
        self.assertEqual(asked, [("skill", 20, "Rain of Blades")])
        self.assertEqual([(r["name"], r["qty"]) for r in rows[1:]], [("Exalted Orb", 2), ("Orb of Alchemy", 10)])

    def test_a_cut_name_needs_one_name_only(self):
        names = RM.Names(["Exalted Orb", "Exalted Shard", "Orb of Alchemy"])
        self.assertIsNone(names.match("Exalted", cut_ok=True))           # two names start so: no guess
        self.assertIsNone(names.match("Exalted"))
        names = RM.Names(["Exalted Orb", "Orb of Alchemy"])
        self.assertEqual(names.match("Exalted", cut_ok=True), "Exalted Orb")
        self.assertIsNone(names.match("Exalted"))                        # (a line with no amount is never cut short)
        self.assertIsNone(names.match("Orb", cut_ok=True))               # too short to say


class IslandRumours(unittest.TestCase):
    """(Fixed with the same release, see test_rumours_read.py) the handwriting's letter swaps still find the island."""

    def test_swapped_letters(self):
        self.assertEqual(RU.match("IWviw' to driwk..")[1], "Stagnant Basin")
        self.assertEqual(RU.match("Wawo but risklå...")[1], "Grazed Prairie")
        self.assertEqual(RU.match("Somedtviw' Osho...")[1], "Barren Atoll")


if __name__ == "__main__":
    unittest.main()
