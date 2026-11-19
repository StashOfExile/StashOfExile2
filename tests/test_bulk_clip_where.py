"""3.0.6 (owner: Megalomaniacs didn't add): accept_clip says where each Ctrl+Alt+C copy really went, and a copy that
waits on 'Same item again?' says so over the game too."""
import os
import re
import types
import unittest

from soe2 import app as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mega():
    src = open(os.path.join(ROOT, "tests", "fixtures", "pricecheck_items.txt"), encoding="utf-8").read()
    return [b for b in re.split(r"^=== .*$", src, flags=re.M) if "Megalomaniac" in b][0].strip()


def fake(**over):
    f = types.SimpleNamespace(records={}, dup_pending=[], dup_win=None, own_clip=None, status_text="", status_until=0,
                              added=[], notices=[], ADVANCED=A.App.ADVANCED)
    f.fd_capturing = lambda: False
    f.fl_capturing = lambda: False
    f.fl_ed_open = lambda: False
    f.favours_copy_learn = lambda t: False
    f.read_any = A.App.read_any
    f.item_sig = A.App.item_sig
    f.show_dup = lambda: setattr(f, "dup_win", object())
    f.dup_notice = lambda it: f.notices.append(it["name"])
    f.add_clean = lambda t: f.added.append(t)
    f.not_priceable_yet = lambda t: None
    for k, v in over.items():
        setattr(f, k, v)
    return f


class BulkClipWhere(unittest.TestCase):
    def test_new_item_goes_to_bulk_pricing(self):
        f = fake()
        self.assertEqual(A.App.accept_clip(f, mega()), "Bulk Pricing")
        self.assertEqual(len(f.added), 1)

    def test_same_item_waits_and_says_so_over_the_game(self):
        f = fake()
        item = A.App.read_any(mega())
        f.records = {1: {"id": 1, "item": item, "src": "manual"}}
        self.assertIn("Same item again", A.App.accept_clip(f, mega()))
        self.assertEqual(f.added, [])
        self.assertEqual(f.notices, ["Megalomaniac"])

    def test_strat_loot_box_is_named(self):
        f = fake(fl_capturing=lambda: True, fl_take_clip=lambda t: None)
        self.assertEqual(A.App.accept_clip(f, mega()), "the Strat Tracker's loot box")

    def test_plain_copy_of_a_rare_is_named(self):
        plain = re.sub(r"\{[^}]*\}\n", "", mega()).replace("Rarity: Unique", "Rarity: Rare")
        f = fake()
        self.assertIn("plain Ctrl+C", A.App.accept_clip(f, plain))

    def test_megalomaniac_enhancement_copy_is_advanced(self):
        """The game copies a Megalomaniac's passives as '{ Enhancement }' lines - it was turned away as a plain copy."""
        text = ("Item Class: Jewels\nRarity: Unique\nMegalomaniac\nDiamond\n--------\nItem Level: 84\n--------\n"
                "{ Enhancement }\nAllocates Paragon() — Unscalable Value\n{ Enhancement }\n"
                "Allocates Empowering Remnants() — Unscalable Value\n--------\nThe weak imagine; the strong decide.\n"
                "--------\nCorrupted\n")
        self.assertTrue(A.App.ADVANCED.search(text))
        f = fake()
        self.assertEqual(A.App.accept_clip(f, text), "Bulk Pricing")
        it = A.App.read_any(text)
        self.assertTrue(it and any("Paragon" in m["text"] for m in it["mods"]))


if __name__ == "__main__":
    unittest.main()
