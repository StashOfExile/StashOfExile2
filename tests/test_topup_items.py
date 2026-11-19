"""Top Up Reminders' Items window (3.0.6): plain words, the item picker with the app's own pictures, a read counts items
by those pictures (nothing is taught - the teach key is gone)."""
import os
import sys
import tempfile
import tkinter as tk
import types
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-topup-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import topup as TU  # noqa: E402
from soe2.config import SETTINGS  # noqa: E402


def words(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, (tk.Label, tk.Button)):
            try:
                out.append(str(c.cget("text")))
            except tk.TclError:
                pass
        out.extend(words(c))
    return out


class ItemsWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S
        from soe2 import themes as TH
        S.apply_look(TH.DEFAULT, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def make(self, items):
        from soe2.app import App
        SETTINGS["topup"] = {"on": True, "items": items, "below": 0.3}
        a = App.__new__(App)
        a.root, a.status_text, a.status_until = self.root, "", 0
        a.look_key_text = lambda: "Ctrl+Shift+R"
        a.tu_last = None
        return a

    def pump(self):
        self.root.update_idletasks()
        self.root.update()

    def test_display_icons_are_not_the_recognition_refs(self):
        """The window DRAWS poe.ninja's icons (fallback: the shipped crop); a read names cells with its own refs."""
        import inspect
        from soe2 import mapprofit as MP
        a = self.make([{"name": "Exalted Orb", "keep": 20}])
        self.assertTrue(a.tu_display(24)("Exalted Orb") is not None)          # (the crop stands in when nothing cached)
        self.assertIs(a.tu_display(24), a.tu_display(24))
        refs_src = inspect.getsource(a.tu_refs)
        self.assertIn("build_refs", refs_src)
        self.assertNotIn("tu_display", refs_src)
        self.assertNotIn("tu_display", inspect.getsource(a.tu_name))
        self.assertTrue(callable(MP.build_refs))

    def test_picker_is_one_combobox_field(self):
        from tkinter import ttk
        from soe2.imagepick import ImagePick
        a = self.make([])
        pick = ImagePick(self.root, ["Exalted Orb", "Chaos Orb"], a.tu_display(24))
        pick.pack()
        self.pump()
        self.assertIsInstance(pick.entry, ttk.Combobox)                       # arrow inside the field, no extra button
        self.assertFalse([w for w in pick.winfo_children() if isinstance(w, ttk.Button)])
        pick.entry.event_generate("<Button-1>", x=5, y=5)
        self.pump()
        self.assertIsNotNone(pick.pop)
        pick.close()
        pick.destroy()

    def test_plain_words(self):
        a = self.make([{"name": "Exalted Orb", "keep": 20}])
        w = a.topup_items()
        self.pump()
        text = " | ".join(words(w))
        self.assertIn("Remind me when I'm", text)
        self.assertIn("below what I keep", text)
        self.assertIn("In inventory", text)
        self.assertNotIn("e.g.", text)
        self.assertNotIn("Seen", text)
        self.assertEqual(a.tu_below_tip.text, "A reminder card shows when you have fewer than this - for example, "
                                              "keep 20 at 30% below: the card shows at 13 or fewer.")
        for b, most in ((0.0, 19), (0.5, 9), (0.7, 5)):
            TU.cfg()["below"] = b
            a.topup_below_paint()
            self.assertIn(f"at {most} or fewer", a.tu_below_tip.text)
        self.assertEqual([TU.below_text(b) for b in TU.BELOW_STEPS][:3], ["any amount", "10%", "20%"])
        w.destroy()

    def test_picker_has_pictures_and_types(self):
        a = self.make([])
        w = a.topup_items()
        self.pump()
        pick = a.tu_add_pick                                  # (empty list: the picker is open already)
        self.assertGreater(len(pick.names), 500)
        self.assertIn("Exalted Orb", pick.names)
        self.assertIsNotNone(pick.icon("Exalted Orb"), "the app's own picture")
        pick.entry.focus_force()
        pick.var.set("exalt")
        pick.open()
        self.pump()
        self.assertEqual(pick.shown[0], "Exalted Orb", "starts with what you typed comes first")
        pick._down(None)
        pick._enter(None)
        self.assertEqual(pick.get(), pick.shown[pick.sel] if pick.pop else pick.get())
        pick.var.set("Exalted Orb")
        self.pump()
        self.assertEqual(pick.exact(), "Exalted Orb")
        self.assertTrue(pick.pic.image is not None, "the picked field shows its picture")
        a.tu_add_keep.set("20")
        self.assertTrue(a.topup_add_picked())
        self.assertEqual(TU.cfg()["items"], [{"name": "Exalted Orb", "keep": 20}])
        self.pump()
        self.assertNotIn("Exalted Orb", a.tu_add_pick.names, "on the list: not offered again")
        pick = a.tu_add_pick
        pick.var.set("not an item")
        self.assertFalse(a.topup_add_picked())
        pick.close()
        w.destroy()

    def test_counts_by_the_apps_pictures(self):
        a = self.make([{"name": "Exalted Orb", "keep": 20}, {"name": "Not In The Game", "keep": 5}])
        cells = [{"cell": (0, 0), "sig": None, "count": 7, "sure": True, "name": "Exalted Orb"},
                 {"cell": (0, 1), "sig": None, "count": 5, "sure": True, "name": "Exalted Orb"},
                 {"cell": (0, 2), "sig": None, "count": None, "sure": False, "name": "Chaos Orb"}]
        a.tu_last = {"open": True, "cells": cells}
        tot = a.topup_totals()
        self.assertEqual(tot, {"Exalted Orb": (12, True)}, "an item with no picture is not counted")
        self.assertEqual([lw[0] for lw in TU.low(tot, TU.cfg()["items"])], ["Exalted Orb"])
        self.assertEqual(a._seen(tot, "Not In The Game")[0], "No picture")
        self.assertEqual(a._seen(tot, "Exalted Orb")[0], "12")

    def test_teach_key_is_gone(self):
        from soe2.topup_page import TopUpPage
        for n in ("topup_wants", "topup_take", "topup_copy_learn", "topup_key_text", "topup_key_is_copy"):
            self.assertFalse(hasattr(TopUpPage, n), n)
        self.assertFalse(hasattr(TU, "learn"))
        from soe2 import migrations
        S = {"topup_key": "Ctrl+C", "topup_key_2131": True}
        migrations._topup_key_gone(S)
        self.assertEqual(S, {})


if __name__ == "__main__":
    unittest.main()
