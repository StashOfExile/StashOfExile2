"""The Ritual Identifier (Round 18, owner: hover a Ritual Altar, press the Look key - nothing showed but the read mark).
The game calls the place a Ritual Rune ("Tainted Ritual Rune"); a long danger line wraps ("Clouds of Elemental /
Disturbance ..."); and a frame found round the mouse may be another box. A drawn altar tooltip (a dark panel with a
bright frame, as find_tooltip looks for) and a stand-in for Windows' text reader check the whole path: the picture
round the mouse -> its lines -> the type -> the alert card.

    python3.12 -m unittest tests.test_ritual_identifier          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-ritid-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import ritualid as RID          # noqa: E402
from soe2.hover_page import find_tooltip, read_lines, region   # noqa: E402

GAME = (0, 0, 2560, 1440)


def altar_shot(w=1280, h=640, tip=(420, 160, 900, 470)):
    """A picture round the mouse: a dim map, and an altar tooltip - a dark panel with a bright double frame."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), (38, 34, 30))
    d = ImageDraw.Draw(im)
    for i in range(0, w, 37):                          # (some ground texture: short, broken lines)
        d.line((i, (i * 7) % h, i + 9, (i * 7) % h + 4), fill=(70, 60, 50))
    x0, y0, x1, y1 = tip
    d.rectangle(tip, fill=(12, 10, 9))
    for k in range(4):                                 # the frame: long, level, bright edges
        d.rectangle((x0 + k, y0 + k, x1 - k, y1 - k), outline=(190, 160, 110))
    d.rectangle((x0 + 8, y0 + 46, x1 - 8, y0 + 49), fill=(190, 160, 110))    # the line under the name
    return im


class Fake_OCR:
    """Windows' text reader, as the tooltip would read: the tooltip's own cut gives `tip`, the whole part `whole`."""

    def __init__(self, tip, whole, whole_size=(1280, 640)):
        self.tip, self.whole, self.whole_size, self.calls = tip, whole, whole_size, []

    def __call__(self, img):
        self.calls.append(img.size)
        if img.size != self.whole_size:               # (the tooltip's cut, made bigger)
            return [(t, (0, 0, 10, 10)) for t in self.tip]
        return [(t, (0, 0, 10, 10)) for t in self.whole]


class Parse(unittest.TestCase):
    def test_names(self):
        for text, key in (("Tainted Ritual Altar", "tainted"), ("Tainted Ritual Rune", "tainted"),
                          ("Queen's Ritual Rune", "queens"), ("NTED Ritual Altar", "tainted"),
                          ("Sapping Ritual Run", "sapping")):
            self.assertEqual(RID.parse([(text, None)]), key, text)
        self.assertEqual(RID.parse([("Smothered", None), ("Ritual Rune", None)]), "smothered",
                         "the type on the line above the name")
        self.assertIsNone(RID.parse([("Ritual Rewards", None)]))

    def test_dangers_wrap(self):
        self.assertEqual(RID.parse([("Clouds of Elemental", None), ("Disturbance slow you, lower your", None)]),
                         "sapping")
        self.assertEqual(RID.parse([("Giant plaguebringing Toads emerge", None), ("from the Darkness", None)]),
                         "croaking")
        self.assertEqual(RID.parse([("Waves of Blood pass through the Ritual Site", None)]), "contaminated")


class Read(unittest.TestCase):
    def test_tooltip_found(self):
        im = altar_shot()
        tip = find_tooltip(im, GAME[3])
        self.assertIsNotNone(tip, "the drawn tooltip's frame is found")
        self.assertLessEqual(tip[0], 430)
        self.assertGreaterEqual(tip[2], 890)

    def test_from_the_tooltip(self):
        im = altar_shot()
        ocr = Fake_OCR(["Tainted Ritual Rune", "Chaotic Boils grow and explode when Touched"], [])
        lines = read_lines(im, GAME[3], ocr, want=lambda ls: bool(RID.parse(ls)))
        self.assertEqual(RID.parse(lines), "tainted")
        self.assertEqual(len(ocr.calls), 1, "found in the tooltip: read once")

    def test_whole_part_when_the_frame_was_another_box(self):
        im = altar_shot()
        ocr = Fake_OCR(["Ritual"], ["Infested Ritual Rune", "Tornadoes of Rats traverse the Ritual Site"])
        lines = read_lines(im, GAME[3], ocr, want=lambda ls: bool(RID.parse(ls)))
        self.assertEqual(RID.parse(lines), "infested", "the whole part is read when the frame had no type")
        self.assertEqual(len(ocr.calls), 2)

    def test_region_round_the_mouse(self):
        l_, t, r, b = region((1280, 900), GAME)
        self.assertTrue(l_ < 1280 < r and t < 900 < b)
        self.assertGreaterEqual(900 - t, int(0.38 * 1440) - 1, "room above the mouse for the tooltip")

    def test_card_shown(self):
        from soe2.ritualid_page import RitualIdPage
        shown = []

        class App(RitualIdPage):
            def ritid_alert(self, key="tainted", test=False):
                shown.append(key)
                return key
        a = App()
        self.assertEqual(a.ritid_seen(RID.parse([("Queen's Ritual Rune", None)]), now=1000.0), "queens")
        self.assertIsNone(a.ritid_seen("queens", now=1010.0), "the same altar again: no second card")
        self.assertEqual(shown, ["queens"])
        self.assertEqual(RID.card_text("queens")[0], "Queen's Ritual")


if __name__ == "__main__":
    unittest.main()
