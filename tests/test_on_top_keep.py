"""3.0.6: the Scan stash check window flickered - put in front, then back to "not on top" while the app stayed on
top, so the app covered it (twice). It now stays as on top as the app. (A stand-in window: without a window
manager, X keeps no "on top" to read back.)"""
import unittest

from soe2.ratemods_page import on_top, owner_on_top


class Win:
    def __init__(self, owner=None, top=False):
        self.top, self.owner, self.later = top, owner, []

    def deiconify(self):
        pass

    lift = focus_force = deiconify

    def winfo_exists(self):
        return True

    def after(self, _ms, fn):
        self.later.append(fn)

    def attributes(self, key, value=None):
        if value is None:
            return int(self.top)
        self.top = bool(value)

    def transient(self):
        return "owner" if self.owner else ""

    master = None

    def nametowidget(self, _name):
        return self.owner

    def winfo_toplevel(self):
        return self


class OnTopKeep(unittest.TestCase):
    def run_later(self, w):
        for fn in w.later:
            fn()

    def test_stays_on_top_when_the_app_is(self):
        d = Win()
        on_top(d, lambda: True)
        self.run_later(d)
        self.assertTrue(d.top)

    def test_normal_again_when_the_app_isnt(self):
        d = Win()
        on_top(d, lambda: False)
        self.run_later(d)
        self.assertFalse(d.top)

    def test_follows_its_owner(self):
        d = Win(owner=Win(top=True))
        self.assertTrue(owner_on_top(d))
        on_top(d)
        self.run_later(d)
        self.assertTrue(d.top)
        d2 = Win(owner=Win(top=False))
        on_top(d2)
        self.run_later(d2)
        self.assertFalse(d2.top)


if __name__ == "__main__":
    unittest.main()
