import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from soe2 import rumours as R  # noqa: E402


class Misreads(unittest.TestCase):
    """Windows' reader on the card's handwriting (rumours_read.txt, 2026-11-18): all three rumors are found."""

    def test_the_three_lines(self):
        lines = [("USE A LOGBOOK TO CHART THE AR", (0, 0, 9, 9)), ("b!fSLAND RUMOURS?", (0, 10, 9, 19)),
                 ("IWviw' to driwk..", (0, 20, 9, 29)), ("Wawo but risklå...", (0, 30, 9, 39)),
                 ("Somedtviw' Osho...", (0, 40, 9, 49))]
        self.assertEqual([r[1] for r in R.rows(lines)], ["Stagnant Basin", "Grazed Prairie", "Barren Atoll"])

    def test_heading_lines_are_not_rumors(self):
        for t in ("USE A LOGBOOK TO CHART THE AR", "b!fSLAND RUMOURS?", "REQUIRES:", "Expedition Logbook"):
            self.assertIsNone(R.match(t), t)


if __name__ == "__main__":
    unittest.main()


class CutShort(unittest.TestCase):
    def test_a_line_read_in_part(self):
        lines = [("USE A LOGBOOK TO CHART THE AREA", (0, 0, 9, 9)), ("RUMOURS?", (0, 10, 9, 19)),
                 ("SomedQiw' Osho...", (0, 20, 9, 29)), ("Cold as ice...", (0, 30, 9, 39)), ("least...", (0, 40, 9, 49))]
        got = [r[0] for r in R.rows(lines)]
        self.assertEqual(got, ["Somethin' fishy...", "Cold as ice...", "It's dry at least..."])
        self.assertEqual(len(R.rows(lines)), 3)

    def test_two_fits_is_no_guess(self):
        self.assertIsNone(R.part_match("fall..."))          # Fallen stars / Origin of the fall / The last to fall
