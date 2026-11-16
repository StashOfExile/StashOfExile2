"""Release 3.0.0 (owner decisions): the version, the What's new lead, and the NEW chip.

  * 3.0.0 in both places; the title is the tagline, not TEST BUILD.
  * What's new 3.0.0 leads with "Why 3.0" and "How helpers work now"; it shows to everyone once - after updating
    (from 2.142.2) and on a first start (lead_due until settings' "whatsnew_lead" says it was seen).
  * The NEW chip: on while a feature is new; opening its place clears its rail chip at once and its row's chip once
    you leave; using it clears both; it's remembered in settings ("new_seen"). One name in names.py.

    python3.12 -m unittest discover -s tests        (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import config, names, newchip, whatsnew as W      # noqa: E402
import soe2                                                    # noqa: E402


class Version(unittest.TestCase):
    def test_version(self):
        self.assertEqual(soe2.__version__, "3.0.0")
        self.assertEqual(config.APP_VERSION, "3.0.0")
        self.assertNotIn("TEST BUILD", config.APP_TITLE)
        self.assertTrue(config.APP_TITLE.endswith(config.TAGLINE))
        self.assertFalse(config.UI_OVERHAUL)


class WhatsNewLead(unittest.TestCase):
    def test_lead_first(self):
        notes = W.notes_between("2.142.2", "3.0.0")
        self.assertEqual([v for v, _ in notes][:1], ["3.0.0"])
        heads = [h for _i, h, _l in W.lead_of(notes)]
        self.assertEqual(heads, ["Why 3.0", "How helpers work now"])
        lines = " ".join(x for _i, _h, ls in W.lead_of(notes) for _ic, x in ls)
        self.assertIn("{look}", lines)                 # (the Look key's own name goes there)
        self.assertIn("Ctrl+D", lines)
        for _i, _h, ls in W.lead_of(notes):
            self.assertTrue(all(len(x.split()) <= 18 for _ic, x in ls), "short lines")

    def test_lead_once_for_everyone(self):
        self.assertTrue(W.lead_due(None, "3.0.0"))            # first start / updating: shown
        self.assertFalse(W.lead_due("3.0.0", "3.0.0"))        # seen: never again
        self.assertTrue(W.lead_due("2.142.2", "3.0.0"))
        self.assertFalse(W.lead_due(None, "2.142.2"))         # (no lead before 3.0)
        self.assertEqual(W.lead_version("3.0.1"), "3.0.0")

    def test_big_first_three(self):
        big, _small = W.split_notes(W.notes_between("2.142.2", "3.0.0"))
        self.assertEqual([t for _i, t, _x, _g in big], ["Drawer", "Trial of the Sekhemas", "Back from a map"])


class NewChip(unittest.TestCase):
    def setUp(self):
        self.S = {}
        self.p = mock.patch.object(newchip, "SETTINGS", self.S)
        self.p.start()
        self.save = mock.patch.object(newchip, "save_json").start()
        newchip._leaving.clear()

    def tearDown(self):
        mock.patch.stopall()

    def test_names(self):
        self.assertIn(newchip.NAME, names.FEATURES)
        for n in newchip.FEATURES:
            self.assertIn(n, names.FEATURES)

    def test_open_clears_rail_now_row_on_leave(self):
        self.assertTrue(newchip.page_new("settings") and newchip.page_new("tracker"))
        newchip.at("settings", "Keybinds")
        self.assertFalse(newchip.is_new("Look key"))
        self.assertTrue(newchip.row_shown("Look key"))          # still on Keybinds: the row keeps it
        self.assertTrue(newchip.page_new("settings"))           # the Drawer (General) is still new
        self.assertIn("Drawer", newchip.page_tip("settings"))
        newchip.at("settings", "General")
        self.assertFalse(newchip.row_shown("Look key"))         # left Keybinds: gone
        self.assertFalse(newchip.page_new("settings"))
        self.assertEqual(self.S["new_seen"]["Look key"], "3.0.0")
        self.assertTrue(self.save.called)

    def test_use_clears_both(self):
        newchip.used("Trial of the Sekhemas")
        self.assertFalse(newchip.row_shown("Trial of the Sekhemas"))
        self.assertFalse(newchip.page_new("tracker"))

    def test_kept(self):
        self.S["new_seen"] = {"Drawer": "3.0.0"}
        self.assertFalse(newchip.is_new("Drawer"))
        self.assertTrue(newchip.is_new("Look key"))
        self.assertFalse(newchip.is_new("Price Checks"))        # (only the listed features)


if __name__ == "__main__":
    unittest.main()
