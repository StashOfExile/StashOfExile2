"""3.3.0 owner: with the game closed the Drawer is a plain window - it stays where you put it, at the size you gave
it, and is not kept on top of other apps. Over the game it docks and stays on top as before."""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("HOME", tempfile.mkdtemp(prefix="soe2-dfree-"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import drawer as D
from soe2 import drawer_page as DP
from soe2 import style


class Host(DP.DrawerHost):
    def __init__(self, cur, game=None):
        self.cfg = {"share": 0.3}
        self.cur, self.game, self.placed = cur, game, []
        self.drawer_st = types.SimpleNamespace(as_drawer=lambda: True, side="right")
        self.drawer_ad = types.SimpleNamespace(outer_rect=lambda: self.cur, hwnd=lambda: None,
                                               place=lambda r: self.placed.append(r))
        self.root = None
        self._drawer_side_now, self._drawer_rect_now, self._drawer_dock_miss = "right", None, 0
        self._drawer_showing_until = 0

    def drawer_cfg(self):
        return self.cfg

    def drawer_wm_state(self):
        return "normal"

    def drawer_game_rect(self):
        return self.game

    def drawer_work_area(self):
        return (0, 0, 1920, 1040)

    def _drawer_compact(self):
        pass

    def _drawer_note_width(self):
        pass


def monitors(_root, x, y, full=False):
    """Two monitors side by side: a short one on the left, the main one on the right."""
    return (-1920, 200, 0, 1000) if x < 0 else (0, 0, 2560, 1400)


class Free(unittest.TestCase):
    def setUp(self):
        for p in (mock.patch.object(DP, "save_json", lambda *a, **k: None),
                  mock.patch.object(style, "monitor_rect", monitors),
                  mock.patch.object(D, "root_dpi", lambda hwnd: mock.MagicMock())):
            p.start()
            self.addCleanup(p.stop)

    def test_no_game_a_move_is_kept_and_nothing_is_put_back(self):
        h = Host((300, 0, 900, 1400))
        h.drawer_redock()
        self.assertEqual(h.placed, [])
        self.assertEqual(h.cfg["free"], [300, 0, 900, 1400])

    def test_no_game_the_next_show_uses_your_place(self):
        h = Host((300, 0, 900, 1400))
        h.drawer_redock()
        self.assertEqual(h.drawer_target(), (300, 0, 900, 1400))

    def test_a_place_on_a_monitor_that_is_gone_is_not_used(self):
        h = Host(None)
        h.cfg["free"] = [9000, 0, 900, 1000]
        with mock.patch.object(style, "monitor_rect", lambda *a, **k: (0, 0, 2560, 1400)):
            self.assertIsNone(h.drawer_free_rect())
            self.assertEqual(h.drawer_target(), D.drawer_rect(None, (0, 0, 1920, 1040), "right", 0.3, cap=True))

    def test_with_the_game_it_docks_as_before(self):
        h = Host((300, 0, 900, 1400), game=(0, 0, 2560, 1440))
        h.cfg["free"] = [300, 0, 900, 1400]
        want = D.drawer_rect((0, 0, 2560, 1440), None, "right", 0.3, cap=True)
        self.assertEqual(h.drawer_target(), want)
        h.drawer_redock()
        self.assertEqual(h.placed, [want])

    def test_no_game_the_side_button_still_moves_it(self):
        h = Host((300, 0, 900, 1400))
        h.drawer_redock()                                   # (your place: kept)
        h.drawer_strip_paint = lambda: None
        h.drawer_st.side = "right"
        h.cfg["side"] = "right"
        h.drawer_flip_side()
        self.assertEqual(h.placed[-1], (0, 0, 900, 1400))   # the left edge of the monitor it is on, same size
        h.cur = h.placed[-1]
        h.drawer_flip_side()
        self.assertEqual(h.placed[-1], (2560 - 900, 0, 900, 1400))
        self.assertEqual(h.cfg["free"], [1660, 0, 900, 1400])

    def test_on_top_over_the_game_only(self):
        h = Host((0, 0, 900, 1000))
        with mock.patch.object(D, "GAME_CLOSED", [True]):
            self.assertFalse(h.drawer_topmost_wanted())
        with mock.patch.object(D, "GAME_CLOSED", [False]):
            self.assertTrue(h.drawer_topmost_wanted())

    def test_closed_only_when_it_can_be_told(self):
        with mock.patch.object(D, "GAME_RECT_HOOK", lambda: None):
            self.assertTrue(D.game_closed_now())
        with mock.patch.object(D, "GAME_RECT_HOOK", lambda: (0, 0, 10, 10)):
            self.assertFalse(D.game_closed_now())


if __name__ == "__main__":
    unittest.main()
