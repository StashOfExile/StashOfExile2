"""3.3.0 owner: Del did nothing on Favorites, and other list keys were hit and miss. Keys go to the list that
has the keyboard, whatever page it sits on. Admins can make a favorite Official. The how-to row on Helpers."""
import inspect
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import app as APP, favorites_page, listkeys, regex_page, share_page, tracker_page  # noqa: E402


class Host(listkeys.ListKeys):
    def __init__(self):
        self.said = []

    def undo_changed(self, key):
        pass


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Keys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def make(self, key, delete=True):
        h, gone = Host(), []
        tv = ttk.Treeview(self.root)
        tv.pack()
        for i in range(3):
            tv.insert("", "end", iid=f"r{i}", text=str(i))
        h.list_register(key, tv, delete=(lambda rows: gone.extend(rows)) if delete else None)
        return h, tv, gone

    def test_delete_goes_to_the_list_whatever_its_page_is_called(self):
        h, tv, gone = self.make("favorites")              # a list that lives inside another page
        tv.selection_set("r1")
        self.assertTrue(h.list_key_on(tv, "delete"))
        self.assertEqual(gone, ["r1"])

    def test_select_all_and_undo(self):
        h, tv, gone = self.make("regex")
        self.assertTrue(h.list_key_on(tv, "all"))
        self.assertEqual(len(tv.selection()), 3)
        self.assertFalse(h.list_key_on(tv, "undo"), "nothing to undo yet")
        back = []
        h.push_undo("regex", "1 favorite", lambda: back.append(1))
        self.assertTrue(h.list_key_on(tv, "undo"))
        self.assertEqual(back, [1])

    def test_a_list_that_cannot_delete_does_nothing(self):
        h, tv, gone = self.make("rates", delete=False)
        tv.selection_set("r0")
        self.assertFalse(h.list_key_on(tv, "delete"))

    def test_a_list_we_do_not_know_is_left(self):
        h = Host()
        tv = ttk.Treeview(self.root)
        self.assertFalse(h.list_key_on(tv, "delete"))


class Wiring(unittest.TestCase):
    def test_the_key_router_asks_the_focused_list_first(self):
        src = inspect.getsource(APP.App.on_list_key)
        self.assertLess(src.index("self.list_key_on("), src.index("self._on_checks()"))

    def test_admins_can_make_a_favorite_official(self):
        self.assertIn("def share_admin(", inspect.getsource(share_page))
        fav = inspect.getsource(favorites_page)
        self.assertIn('self.share_admin_actions("trade"', fav)
        self.assertIn('"official": ("Make Official", self.fav_admin_official', fav)
        self.assertIn("if self.share_is_admin():", inspect.getsource(share_page), "only admins see the button")
        self.assertIn('self.share_admin_actions("regex"', inspect.getsource(regex_page))

    def test_empty_box_sits_on_the_favorites_list(self):
        self.assertIn("e.place(in_=tv, relx=0.5, rely=0.5", inspect.getsource(favorites_page))

    def test_helpers_has_one_how_to_row(self):
        src = inspect.getsource(tracker_page)
        self.assertEqual(src.count('text="Your Read Key is"'), 1)
        self.assertIn('text="Change key"', src)
        self.assertIn("self.look_key_open()", src)
        self.assertNotIn("flowify(box)", src, "no box of its own: one plain line")

    def test_change_key_lights_the_read_key_row(self):
        from soe2 import settings_page
        src = inspect.getsource(settings_page)
        self.assertIn("def _hotkey_row_show(", src)
        self.assertIn('lab.config(text="▶ " + str(was))', src, "a mark, never color alone")
        self.assertIn("yview_moveto", src)

    def test_one_name_for_the_favorites_tab(self):
        self.assertNotIn("★ Favorites", inspect.getsource(regex_page))


if __name__ == "__main__":
    unittest.main()
