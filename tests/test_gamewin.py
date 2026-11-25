"""3.3.0 owner: Settings › Advanced › Over the game finds the game's window instead of a typed title."""
import os
import sys
import tkinter as tk
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import gamewin as G  # noqa: E402

OPEN = [("Discord", "Chrome_WidgetWin_1"), ("Stash of Exile 2", "TkTopLevel"), ("Path of Exile 2", G.GAME_CLASS),
        ("Discord", "Chrome_WidgetWin_1"), ("alpha", "x")]


class Finding(unittest.TestCase):
    def test_the_game_is_found_by_its_window_class(self):
        self.assertEqual(G.detect(lambda: OPEN), "Path of Exile 2")
        renamed = [("Путь изгнанника 2", G.GAME_CLASS)]
        self.assertEqual(G.detect(lambda: renamed), "Путь изгнанника 2", "a translated title is still the game")
        self.assertEqual(G.detect(lambda: OPEN[:2]), "")
        self.assertEqual(G.detect(lambda: []), "")

    def test_the_list_puts_the_game_first_and_leaves_the_app_out(self):
        self.assertEqual(G.titles(lambda: OPEN), ["Path of Exile 2", "alpha", "Discord"])

    def test_a_failing_list_is_empty_not_an_error(self):
        def boom():
            raise OSError("no display")
        self.assertEqual(G.windows(boom), [])
        self.assertEqual(G.detect(boom), "")


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Detect(unittest.TestCase):
    def setUp(self):
        from soe2 import settings_page
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        saved = []

        class H(settings_page.SettingsPage):
            pass
        h = H()
        h.ov_vars = {"poe_title": tk.StringVar(master=self.root, value="Path of Exile 2")}
        h.ov_save = lambda: saved.append(h.ov_vars["poe_title"].get())
        h.game_title_msg = tk.Label(self.root)
        self.h, self.saved = h, saved

    def test_detect_sets_and_saves_the_title_and_says_so_in_words(self):
        got = self.h.game_title_detect(lambda: [("PoE 2 renamed", G.GAME_CLASS)])
        self.assertEqual(got, "PoE 2 renamed")
        self.assertEqual(self.saved, ["PoE 2 renamed"])
        self.assertTrue(self.h.game_title_msg.cget("text").startswith("✓ Found the game"))

    def test_no_game_keeps_the_title_and_says_what_to_do(self):
        self.assertEqual(self.h.game_title_detect(lambda: [("Discord", "x")]), "")
        self.assertEqual(self.saved, [])
        self.assertEqual(self.h.ov_vars["poe_title"].get(), "Path of Exile 2")
        self.assertIn("Start it, then click Detect", self.h.game_title_msg.cget("text"))


if __name__ == "__main__":
    unittest.main()
