"""3.0.6 (owner): one switch - Hide all overlay information from screen captures - for every window over the game,
only in Overlay › Options; Helpers (by Sound) and Quick settings show a read-out that opens Options; off by default (everything shows on captures)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import names, remnant_page as RP  # noqa: E402
from soe2.config import SETTINGS  # noqa: E402
from soe2.ovquick import HIDECAP, QUICK_TIPS  # noqa: E402


class Switch(unittest.TestCase):
    def test_one_name(self):
        self.assertEqual(HIDECAP, "Hide all overlay information from screen captures")
        self.assertIn(HIDECAP, names.FEATURES)
        self.assertEqual(names.OLD["Hide the overlay from screen captures"], HIDECAP)
        self.assertIn(HIDECAP, QUICK_TIPS)

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


class ReadOuts(unittest.TestCase):
    def test_one_switch_only_in_options(self):
        import inspect
        from soe2 import alerts_page, ovquick, tracker_page
        self.assertNotIn("Checkbutton(top, text=HIDECAP", inspect.getsource(alerts_page))
        self.assertNotIn("row(HIDECAP", inspect.getsource(ovquick))
        self.assertIn("tk_hidecap = tk.BooleanVar", inspect.getsource(tracker_page))
        self.assertIn('ovh_open("Options")', inspect.getsource(alerts_page))
        self.assertIn('ovh_open("Options")', inspect.getsource(ovquick))

    def test_readout_text_follows_setting(self):
        from soe2.tracker_page import TrackerPage as T
        t = SETTINGS.setdefault("tracker", {})
        was = t.get("hide_capture")
        fake = type("X", (), {"overlay_hide_capture": lambda s: RP.capture_hidden()})()
        try:
            t["hide_capture"] = True
            self.assertEqual(T.ov_hidecap_text(fake), "\u2713 Hidden from captures: On")
            t["hide_capture"] = False
            self.assertEqual(T.ov_hidecap_text(fake), "\u25cb Hidden from captures: Off")
        finally:
            if was is None:
                t.pop("hide_capture", None)
            else:
                t["hide_capture"] = was


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
