"""3.3.0 owner: a Community or Official favorite showed nothing on the right, its link was not buyout only, a
grayed Trade Site button showed a dotted box, and menu check marks showed only on hover."""
import inspect
import json
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import bulk_page, favorites as FV, favorites_page, library_page, listkit, style  # noqa: E402


class Guests(unittest.TestCase):
    def store(self):
        st = FV.FavStore.__new__(FV.FavStore)
        st.items, st.groups, st.next, st.name = [], [], 1, "favorites_test_never_saved.json"
        return st

    def test_a_guest_is_found_but_never_listed_or_saved(self):
        st = self.store()
        g = st.guest("s:7", "https://x", {"query": {"type": "Utility Belt"}, "league": "L"}, "Mageblood")
        self.assertIs(st.get("s:7"), g)
        self.assertEqual(st.items, [], "not one of yours")
        self.assertEqual(st.in_group(""), [])
        self.assertIs(st.guest("s:7", "https://y", {"query": {}}, "Other"), g, "the same row is the same guest")
        self.assertEqual(g["kind"], "link")

    def test_your_own_come_first(self):
        st = self.store()
        mine = st.add_link("https://x", {"query": {"type": "Ring"}}, name="Mine")
        self.assertIs(st.get(mine["id"]), mine)
        self.assertIsNone(st.get("s:nope"))


class Links(unittest.TestCase):
    def test_a_shared_link_is_buyout_only_by_default(self):
        from soe2.config import SETTINGS
        was = SETTINGS.get("status")
        SETTINGS.pop("status", None)
        try:
            page = favorites_page.FavoritesPage if hasattr(favorites_page, "FavoritesPage") else None
            host = next(c for c in vars(favorites_page).values() if isinstance(c, type) and
                        hasattr(c, "_fav_shared_url"))
            url = host._fav_shared_url(host.__new__(host), {"query": {"type": "Utility Belt", "status": {"option": "any"}}})
            body = json.loads(unquote(url.split("?q=", 1)[1]))
            self.assertEqual(body["query"]["status"], {"option": "securable"})
            del page
        finally:
            if was is not None:
                SETTINGS["status"] = was

    def test_shared_rows_show_and_search(self):
        src = inspect.getsource(favorites_page)
        self.assertIn("return self.fav_shared_show()", src)
        self.assertIn('("Search now", self.fav_search, bool(r), "Enter")', src)
        self.assertIn('{"main": bool(r), "open": bool(r), "take": bool(r)}', src)


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Looks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        style.apply_look()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_a_grayed_trade_site_button_has_its_own_dim_globe(self):
        style._TRADE_IMG.clear()                          # pictures made for an earlier test window are gone
        b = style.trade_icon(ttk.Button(self.root, text="Trade Site"))
        img = b.cget("image")
        self.assertEqual(len(img), 3, "the picture, then one for the disabled state")
        self.assertEqual(str(img[1]), "disabled")
        self.assertNotEqual(str(img[0]), str(img[2]))

    def test_menu_check_marks_have_a_color_that_shows(self):
        m = listkit._menu(self.root)
        self.assertEqual(str(m.cget("selectcolor")).lower(), style.C["text"].lower())
        self.assertIn('selectcolor=C["text"]', inspect.getsource(bulk_page))

    def test_under_the_hood_left_side_is_a_titled_panel(self):
        src = inspect.getsource(library_page)
        self.assertIn('chrome_section(pane, "Game Data"', src)
        self.assertNotIn("ttk.Notebook(left)", src)



class GreenLines(unittest.TestCase):
    """3.3.0 owner: the key is named once, at the top of Helpers; a green line says only where to press."""

    def host(self, key="Ctrl+Shift+R"):
        from soe2 import alerts_page as AP

        class H(AP.AlertsPage):
            def look_key_text(self):
                return f"your Read Key ({key})" if key else "your Read Key"
        return H.__new__(H)

    def test_the_key_is_taken_out_of_a_status_line(self):
        h = self.host()
        self.assertEqual(h._helper_line_no_key("On - press your Read Key (Ctrl+Shift+R) with the Favours window open."),
                         "On - press your Read Key with the Favours window open.")
        self.assertEqual(self.host("")._helper_line_no_key("On - press your Read Key now."),
                         "On - press your Read Key now.")

    def test_temple_says_where_then_the_count_without_brackets(self):
        h = self.host()
        self.assertEqual(h._plain_count("Crystals 12/60 (2 runs)"), "Crystals 12/60, 2 runs")
        src = inspect.getsource(type(h).__mro__[1])
        self.assertIn("with the Temple Console open.\"", src)
        self.assertIn("self._plain_count(_TMs.count_text(_st))", src)


if __name__ == "__main__":
    unittest.main()
