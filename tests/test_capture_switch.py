"""3.0.6 (owner): one switch - Hide all overlay information from screen captures - for every window over the game,
only in Overlay › Options; Helpers (by Sound) and Quick settings show a read-out that opens Options; off by default (everything shows on captures)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import names, remnant_page as RP  # noqa: E402
from soe2.config import SETTINGS  # noqa: E402
from soe2.ovquick import HIDECAP  # noqa: E402


class Switch(unittest.TestCase):
    def test_one_name(self):
        self.assertEqual(HIDECAP, "Hide all overlay information from screen captures")
        self.assertIn(HIDECAP, names.FEATURES)
        self.assertEqual(names.OLD["Hide the overlay from screen captures"], HIDECAP)

    def test_off_by_default_and_follows_setting(self):
        t = SETTINGS.setdefault("tracker", {})
        was = t.get("hide_capture")
        try:
            t.pop("hide_capture", None)
            self.assertFalse(RP.capture_hidden(), "everything shows on captures unless switched on")
            t["hide_capture"] = True
            self.assertTrue(RP.capture_hidden())
        finally:
            if was is None:
                t.pop("hide_capture", None)
            else:
                t["hide_capture"] = was


class OneHome(unittest.TestCase):
    def test_only_in_options_no_readouts(self):
        # (owner: the read-outs in Helpers and Quick settings were "a poor UI choice")
        import inspect
        from soe2 import alerts_page, ovquick, tracker_page
        self.assertIn("tk_hidecap = tk.BooleanVar", inspect.getsource(tracker_page))
        self.assertNotIn("al_hidecap", inspect.getsource(alerts_page))
        self.assertNotIn("ovq_hidecap", inspect.getsource(ovquick))


class MedallionSlots(unittest.TestCase):
    def test_filled_slot_by_picture(self):
        from PIL import Image
        from soe2 import medallions as M
        self.assertFalse(M.slot_filled(Image.new("RGB", (56, 60), (6, 6, 6))))
        im = Image.new("RGB", (56, 60), (60, 50, 30))
        im.paste((220, 190, 120), (10, 10, 40, 50))
        self.assertTrue(M.slot_filled(im))


if __name__ == "__main__":
    unittest.main()
