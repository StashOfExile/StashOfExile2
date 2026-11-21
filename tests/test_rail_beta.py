"""The Drawer's rail shows BETA on a beta page, as the wide sidebar does (feedback: the BETA tags were gone in the
Drawer).

    DISPLAY=:99 python3.12 -m unittest tests.test_rail_beta"""
import os
import sys
import tempfile
import types
import unittest
import unittest.mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402

from soe2 import sidebar as SB, style as S, themes as TH  # noqa: E402


class Rail(unittest.TestCase):
    def test_beta_word_on_the_rail(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        self.addCleanup(root.destroy)
        S.apply_look(TH.DEFAULT, root)
        S.setup_style(root)
        mods = {k: types.SimpleNamespace(key=k, title=t, icon="•", kind="module", parent=None, labs=False, beta=b)
                for k, t, b in (("crafthelper", "Craft Helper", True), ("ratemods", "Rate Mods", False))}
        shell = types.SimpleNamespace(active="ratemods", modules=mods, app=types.SimpleNamespace(drawer_look_on=lambda: True),
                                      listed=lambda m: True, children=lambda k: [], tab_titles=lambda k: [],
                                      tab_current=lambda k: None)
        sb = SB.Sidebar(shell, root)
        sb.pack(fill="y", expand=True)
        root.geometry("200x900")
        sb.compact = True
        with unittest.mock.patch.object(SB, "_beta", lambda m: getattr(m, "beta", False)):
            root.update()
            sb.delete("all")
            sb._redraw_rail(TH.ST.theme)
        words = [sb.itemcget(i, "text") for i in sb.find_all() if sb.type(i) == "text"]
        self.assertEqual(words.count("BETA"), 1, "BETA on Craft Helper only")


if __name__ == "__main__":
    unittest.main()
