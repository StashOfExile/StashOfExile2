"""3.0.6: the owner's Currency tab scan - one test per cause. The picture is a strip of six stack-number slots (item
art and its number only, nothing about the player)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from soe2 import stashlayouts as L, stashread as SR  # noqa: E402

STRIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "stash_stacks.png")


class StackNumbers(unittest.TestCase):
    """131 Orbs of Annulment read as 13: the last 1 sits on the white face and matches faintly."""

    def test_strip(self):
        import cv2
        img = cv2.imread(STRIP)
        for i, want in enumerate((131, 671, 13, 1065, 3025, 2)):
            self.assertEqual(SR.read_number(img, (i * 82 + 6, 6, 70, 70), 1.0), want)


class ShardRow(unittest.TestCase):
    def test_the_four_shards_are_read(self):
        names = [n for n, _r in L.TABS["currency"]["slots"]]
        for n in ("Transmutation Shard", "Regal Shard", "Chance Shard", "Artificer's Shard"):
            self.assertIn(n, names)

    def test_no_slot_overlaps(self):
        rects = [r for _n, r in L.TABS["currency"]["slots"]] + list(L.TABS["currency"]["wild"])
        for i, (x, y, w, h) in enumerate(rects):
            for x2, y2, w2, h2 in rects[i + 1:]:
                self.assertFalse(x < x2 + w2 and x2 < x + w and y < y2 + h2 and y2 < y + h, (x, y, x2, y2))


def _icon(bgr, shade=0):
    import numpy as np
    rng = np.random.default_rng(7)
    a = rng.uniform(0, 200, (26, 40, 3)).astype(np.float32)
    a[:, :, 2] += shade
    return a


class WildcardColors(unittest.TestCase):
    """A Vaal Blacksmith's Infuser in a wildcard slot was counted as a Blacksmith's Whetstone (same shape, red)."""

    def test_same_shape_other_colors_is_not_a_match(self):
        name, _sc = SR._same_item(_icon(None, shade=40), {"Blacksmith's Whetstone": _icon(None)})
        self.assertIsNone(name)

    def test_same_picture_still_matches(self):
        name, _sc = SR._same_item(_icon(None), {"Divine Orb": _icon(None)})
        self.assertEqual(name, "Divine Orb")


class WildcardByPicture(unittest.TestCase):
    """Wildcard slots no tab's slot looks like are named by Map Profit's picture naming."""

    def test_named_by_picture(self):
        import numpy as np
        slot = np.zeros((70, 70, 3), np.uint8)
        wild = [(2, _icon(None), slot), (1, _icon(None), None), (None, _icon(None), slot)]
        got, unk = SR.match_wild(wild, {}, keep=True, by_pic=lambda bgr: "Sacred Bloom")
        self.assertEqual(got, [("Sacred Bloom", 2)])
        self.assertEqual(len(unk), 2)              # (no picture kept / no number: left for you)

    def test_picture_says_nothing(self):
        import numpy as np
        got, unk = SR.match_wild([(3, _icon(None), np.zeros((70, 70, 3), np.uint8))], {}, keep=True,
                                 by_pic=lambda bgr: None)
        self.assertEqual((got, len(unk)), ([], 1))


if __name__ == "__main__":
    unittest.main()
