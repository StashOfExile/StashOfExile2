"""3.3.0 owner: the two Favorites screens and the right-click menus did not match. One toolbar builds both
screens, and one order sorts every list's menu."""
import inspect
import os
import sys
import tkinter as tk
from tkinter import ttk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import favorites_page, listkit, regex_page, share_page  # noqa: E402


class Host(share_page.SharePage if hasattr(share_page, "SharePage") else object):
    pass


def host_class():
    """The mixin that holds share_toolbar, whatever it is called."""
    for name in dir(share_page):
        c = getattr(share_page, name)
        if isinstance(c, type) and hasattr(c, "share_toolbar"):
            return c
    raise AssertionError("share_toolbar not found")


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Toolbar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        from soe2 import style
        style.apply_look()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def make(self, ids, admin=False):
        Base = host_class()

        class H(Base):
            def undo_button(self, parent, key, **pack):
                b = ttk.Button(parent, text="Undo")
                b.pack(**pack)
                return b

            def share_is_admin(self):
                return admin
        h = H()
        acts = {i: (i.title(), lambda: None, "tip") for i in ids}
        box, view, btns = h.share_toolbar(self.root, "k", tk.StringVar(), lambda: None, acts)
        box.pack()
        self.root.update()
        return h, box, view, btns

    def order(self, btns):
        return [i for i, b in sorted(btns.items(), key=lambda kv: kv[1].winfo_x()) if b.winfo_manager()]

    def test_same_order_whatever_a_page_passes(self):
        all_ids = ["delete", "take", "post", "key", "tags", "rename", "open", "main"]
        _h, box, _v, btns = self.make(all_ids)
        self.assertEqual(self.order(btns), ["main", "open", "rename", "tags", "key", "post", "take", "delete"])
        _h, box2, _v, few = self.make(["post", "main", "delete", "open"])
        self.assertEqual(self.order(few), ["main", "open", "post", "delete"])

    def test_one_orange_button_and_all_gray_until_a_row_is_picked(self):
        _h, _box, _v, btns = self.make(["main", "open", "rename", "delete"])
        self.assertEqual([i for i, b in btns.items() if str(b.cget("style")) == "Primary.TButton"], ["main"])
        self.assertTrue(all(b.instate(["disabled"]) for b in btns.values()))

    def test_greys_follow_what_a_page_says(self):
        h, _box, _v, btns = self.make(["main", "open", "rename", "delete"])
        h.share_tool_greys(btns, {"main": True, "delete": True})
        self.assertEqual(sorted(i for i, b in btns.items() if b.instate(["!disabled"])), ["delete", "main"])

    def test_make_official_only_for_admins(self):
        h, _box, _v, btns = self.make(["main", "official", "delete"])
        h.share_tool_greys(btns, {}, {"id": 1})
        self.assertFalse(btns["official"].winfo_manager())
        h, _box, _v, btns = self.make(["main", "official", "delete"], admin=True)
        h.share_tool_greys(btns, {}, {"id": 1, "promoted": 1})
        self.assertTrue(btns["official"].winfo_manager())
        self.assertEqual(btns["official"].cget("text"), "Remove from Official")

    def test_views_are_the_same_three(self):
        _h, _box, view, _b = self.make(["main"])
        self.assertEqual(view.get(), "Mine")


class BothPagesUseIt(unittest.TestCase):
    def test_both_build_with_the_shared_toolbar(self):
        for mod in (favorites_page, regex_page):
            src = inspect.getsource(mod)
            self.assertIn("self.share_toolbar(", src, mod.__name__)
            self.assertIn("PanelHead(", src, mod.__name__ + ": the theme's header strip")
            self.assertNotIn("Upvote", src.split('"""', 2)[-1] if False else
                             "\n".join(ln for ln in src.split("\n") if not ln.strip().startswith("#")),
                             mod.__name__)

    def test_same_button_words_on_both(self):
        fav, rx = inspect.getsource(favorites_page), inspect.getsource(regex_page)
        for words in ('("Rename", ', '("Tags…", ', '("Post", ', '("Add to Mine", ', '("Delete", '):
            self.assertIn(words, fav)
            self.assertIn(words, rx)


class MenuOrder(unittest.TestCase):
    def test_lines_are_sorted_into_the_one_order(self):
        f = lambda: None  # noqa: E731
        acts = [("⚑ Report…", f), ("Delete it all", f), ("Rename…", f, True, "F2"), None, ("Search now", f, True, "Enter"),
                ("Admin: Make Official", f), ("Trade Site", f), ("Move up", f), ("📤 Post to Community", f),
                ("Copy trade link", f), ("Tags…", f), ("Add to Mine", f), ("Remove", f), ("New group…", f)]
        b = listkit.menu_blocks(acts)
        names = {k: [a[0] for a in v] for k, v in b.items()}
        self.assertEqual(names["top"], ["Search now", "Trade Site", "Copy trade link"])
        self.assertEqual(names["edit"], ["Rename…", "Move up", "Tags…", "New group…"])
        self.assertEqual(names["share"], ["⚑ Report…", "📤 Post to Community", "Add to Mine"])
        self.assertEqual(names["remove"], ["Delete it all", "Remove"])
        self.assertEqual(names["admin"], ["Admin: Make Official"])

    def test_the_menu_is_built_in_that_order(self):
        src = inspect.getsource(listkit.list_menu)
        marks = ['put(blocks["top"])', 'label=f"Copy {n} rows"', 'for name in ("edit", "share")', 'label="Select all"',
                 'label="Undo"', 'put(blocks["remove"])', 'label=f"Delete {n}"', 'put(blocks["admin"])']
        at = [src.index(m) for m in marks]
        self.assertEqual(at, sorted(at))


if __name__ == "__main__":
    unittest.main()
