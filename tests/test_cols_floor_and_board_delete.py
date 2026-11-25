"""3.3.0 owner: Bulk Pricing's columns shrank to slivers and stayed so; Delete did nothing on a Community
favorite, even for an admin."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import app as APP, bulk_page, favorites_page, regex_page, share_page  # noqa: E402


def host():
    return next(c for c in vars(bulk_page).values() if isinstance(c, type) and hasattr(c, "col_floor"))


class Columns(unittest.TestCase):
    def test_every_column_has_a_floor_it_can_be_read_at(self):
        H = host()
        for cid, title, w, _a in APP.App.COLS:
            f = H.col_floor(cid, w)
            self.assertGreaterEqual(f, 36, cid)
            self.assertLessEqual(f, max(w, 140), cid)
        self.assertEqual(H.col_floor("name", 170), 140)
        self.assertGreaterEqual(H.col_floor("type", 110), 56)

    def test_a_saved_width_under_the_floor_is_not_used_or_saved(self):
        src = inspect.getsource(bulk_page)
        self.assertIn("minwidth=floor", src)
        self.assertIn("width=max(keep, floor,", src)
        self.assertIn(">= self.col_floor(c[0], c[2])", inspect.getsource(APP.App.save_widths))

    def test_one_click_back_to_normal(self):
        src = inspect.getsource(bulk_page)
        self.assertIn('label="Reset widths", command=self.cols_reset', src)


class BoardDelete(unittest.TestCase):
    def make(self, admin):
        Base = next(c for c in vars(share_page).values() if isinstance(c, type) and hasattr(c, "share_delete"))

        class H(Base):
            def share_is_admin(self):
                return admin
        return H.__new__(H)

    def test_only_its_author_or_an_admin(self):
        self.assertTrue(self.make(True).share_can_delete({"id": 1}))
        self.assertTrue(self.make(False).share_can_delete({"id": 1, "mine": True}))
        self.assertFalse(self.make(False).share_can_delete({"id": 1}))
        self.assertFalse(self.make(True).share_can_delete(None))
        self.assertIsNone(self.make(False).share_delete("trade", {"id": 1}))

    def test_it_asks_first_and_says_it_cannot_be_undone(self):
        src = inspect.getsource(share_page)
        body = src[src.index("    def share_delete(self"):src.index("    def share_admin_actions(self")]
        self.assertLess(body.index("messagebox.askyesno("), body.index("B.delete(post[\"id\"])"))
        self.assertIn("cannot be brought back", body)

    def test_both_favorites_pages_reach_it(self):
        self.assertIn('self.share_delete("trade", post, self.fav_shared_fill)', inspect.getsource(favorites_page))
        self.assertIn('self.share_delete("regex", post, self.rx_fill_favorites)', inspect.getsource(regex_page))


if __name__ == "__main__":
    unittest.main()
