"""3.2.0 bug reports #291 and #292: the inventory was never found on one player's 1440p screen. Report a bug can now add
the screen setup, shown word for word before Send; a missed inventory read logs what it saw; the whole top of the game
is searched when the title isn't at the right; a learned title that stops matching is learned again.

    DISPLAY=:99 python3.12 -m unittest tests.test_screen_setup          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-setup-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tkinter as tk                                 # noqa: E402

from PIL import Image, ImageDraw                    # noqa: E402

from soe2 import feedback_page as F                 # noqa: E402
from soe2 import gameart as GA                      # noqa: E402
from soe2 import sysinfo as SI                      # noqa: E402
from soe2 import topup as TU                        # noqa: E402

GAME = (0, 0, 2560, 1440)


class Text(unittest.TestCase):
    def test_one_screen(self):
        t = SI.text({"screens": [{"w": 2560, "h": 1440, "hz": 240, "scale": 100, "hdr": False, "main": True}],
                     "game": {"w": 2560, "h": 1440, "cw": 2560, "ch": 1440, "screen": 1,
                              "mode": "fills the screen, no border"},
                     "reader": "en-US", "miss": ""})
        self.assertEqual(t, "**Screen setup**\nScreen: 2560×1440 · 240 Hz · scaling 100% · HDR off\n"
                            "Game window: 2560×1440 · fills the screen, no border\nText reader: en-US")

    def test_two_screens_and_a_window(self):
        t = SI.text({"screens": [{"w": 2560, "h": 1440, "hz": 165, "scale": 125, "hdr": True, "main": True},
                                 {"w": 1920, "h": 1080, "hz": 60}],
                     "game": {"w": 1936, "h": 1119, "cw": 1920, "ch": 1080, "screen": 2,
                              "mode": "windowed, with a title bar"},
                     "reader": "", "miss": "18:11: something"})
        self.assertIn("Screen 1, main: 2560×1440 · 165 Hz · scaling 125% · HDR on", t)
        self.assertIn("Screen 2: 1920×1080 · 60 Hz", t)
        self.assertIn("Game window: 1936×1119 · inside 1920×1080 · on screen 2 · windowed, with a title bar", t)
        self.assertIn("Last inventory miss: 18:11: something", t)
        self.assertNotIn("Text reader", t)

    def test_no_game(self):
        self.assertIn("Game window: not open", SI.text({"screens": [], "game": None}))
        self.assertIn("Game window: minimized", SI.text({"screens": [], "game": {"mode": "minimized"}}))

    def test_read_once_per_form(self):
        SI._CACHE.clear()
        with mock.patch.object(SI, "gather", return_value={"screens": [], "game": None}) as g:
            a = SI.report_part()
            b = SI.report_part()
        self.assertEqual(a, b)
        self.assertEqual(g.call_count, 1)
        SI._CACHE.clear()


def banner_pic(word_at=None):
    return Image.new("RGB", (648, 173), (40, 40, 40))


class Miss(unittest.TestCase):
    def setUp(self):
        TU.MISS.clear()
        self.ocr = GA.OCR[0]
        GA._LOOKS.clear()

    def tearDown(self):
        GA.OCR[0] = self.ocr
        TU.MISS.clear()
        GA._LOOKS.clear()

    def test_miss_logs_what_it_read(self):
        GA.OCR[0] = lambda pic: [("Doryani", (0, 0, 50, 10)), ("Ritual Sta", (0, 20, 60, 30))]
        self.assertFalse(TU.is_open(banner_pic(), 1440))
        with mock.patch.object(TU.buglog, "record") as rec:
            TU.note_miss(GAME, banner_pic(), None)
        t = TU.miss_text()
        self.assertIn("game window 2560×1440", t)
        self.assertIn("looked at the top right 648×173", t)
        self.assertIn("brightness 40 of 255", t)
        self.assertIn("not anywhere along the top either", t)
        self.assertIn("Doryani | Ritual Sta", t)
        self.assertEqual(rec.call_args[0][:2], ("read", "Inventory not found"))

    def test_a_black_picture_says_so(self):
        GA.OCR[0] = lambda pic: []
        TU.is_open(Image.new("RGB", (648, 173)), 1440)
        with mock.patch.object(TU.buglog, "record"):
            TU.note_miss(GAME, Image.new("RGB", (648, 173)), None)
        self.assertIn("brightness 0 of 255", TU.miss_text())
        self.assertIn("Words read there: nothing", TU.miss_text())

    def test_reader_failing_is_said(self):
        def boom(pic):
            raise OSError("x")
        GA.OCR[0] = boom
        self.assertIsNone(GA.find_word(banner_pic(), ("inventory",)))
        self.assertIn("<the text reader failed: OSError>", GA.LAST_READ)

    def test_found_elsewhere_moves_the_grid(self):
        # the title read 300 px left of and 20 px below where it's expected
        ex = 2560 - TU.TITLE_MID[0] * 1440
        ey = TU.TITLE_MID[1] * 1440
        GA.OCR[0] = lambda pic: [("INVENTORY", (int(ex - 300 - 80), int(ey + 20 - 14),
                                                int(ex - 300 + 80), int(ey + 20 + 14)))]
        with mock.patch.object(GA, "keep_screen_look"):
            mid = TU.find_title(Image.new("RGB", (2560, 173)), 1440)
        d = TU.title_shift(mid, GAME)
        self.assertLessEqual(abs(d[0] + 300), 1)
        self.assertLessEqual(abs(d[1] - 20), 1)
        r = TU.grid_rect(GAME)
        self.assertEqual(TU.shifted(r, d), (r[0] + d[0], r[1] + d[1], r[2] + d[0], r[3] + d[1]))

    def test_biggest_match_wins(self):
        GA.OCR[0] = lambda pic: [("INVENTORY", (0, 20, 100, 30)), ("INVENTORY", (300, 0, 600, 60))]
        box = GA.find_word(Image.new("RGB", (2560, 173)), ("inventory",), biggest=True)
        self.assertEqual(box, (300, 0, 600, 60))

    def test_learned_title_that_stopped_matching_is_learned_again(self):
        import numpy as np
        GA._LOOKS[GA._ck(TU.BANNER_KEY)] = (np.random.default_rng(1).integers(0, 255, (31, 172), np.uint8), 1440)
        img = Image.new("RGB", (648, 173), (20, 20, 20))
        ImageDraw.Draw(img).rectangle((200, 70, 380, 100), fill=(230, 200, 120))
        GA.OCR[0] = lambda pic: [("INVENTORY", (400, 140, 760, 200))]       # in the 2x picture
        with mock.patch.object(GA, "keep_screen_look") as keep:
            self.assertTrue(TU.is_open(img, 1440))
        self.assertEqual(keep.call_count, 1)


class Host(F.FeedbackPage):
    def __init__(self, root):
        self.root = root

    def dlg_parent(self):
        return self.root

    def run_bg(self, work, done):
        done(work())


class Form(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, self.root)
        S.setup_style(self.root)
        self.h = Host(self.root)
        SI._CACHE.clear()

    def tearDown(self):
        SI._CACHE.clear()
        self.root.destroy()

    def preview(self):
        return self.h.bug_prev.get("1.0", "end-1c")

    def test_shown_before_send_and_can_be_left_out(self):
        with mock.patch.object(SI, "gather", return_value={"screens": [{"w": 2560, "h": 1440, "hz": 240}],
                                                           "game": None, "reader": "en-US", "miss": ""}):
            self.h.bug_report_open()
        self.assertIn("**Screen setup**\nScreen: 2560×1440 · 240 Hz", self.preview())
        self.h.bug_setup_on.set(False)
        self.h._bug_preview()
        self.assertNotIn("Screen setup", self.preview())

    def test_what_is_sent_is_what_is_shown(self):
        with mock.patch.object(SI, "gather", return_value={"screens": [{"w": 1920, "h": 1080}], "game": None}):
            self.h.bug_report_open()
        self.h.bug_vars["title"].set("Inventory not found")
        self.h.bug_vars["what"].insert("1.0", "Ctrl+Shift+R says nothing found.")
        sent = {}

        def call(method, path, body=None):
            sent.update(body)
            return True, {"url": "u", "number": 1}
        with mock.patch.object(F.B, "call", side_effect=call):
            self.h._bug_preview()
            shown = self.preview()
            self.h.bug_send()
        self.assertIn("**Screen setup**\nScreen: 1920×1080", sent["body"])
        self.assertTrue(shown.endswith(sent["body"]))


if __name__ == "__main__":
    unittest.main()
