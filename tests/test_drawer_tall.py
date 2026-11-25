"""3.3.0 owner: over the game the Drawer would not be made taller. A dragged height is kept as a share of the
game's height."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import drawer as D  # noqa: E402

GAME = (0, 0, 2560, 1440)


class Tall(unittest.TestCase):
    def test_default_height_leaves_the_skill_bar_clear(self):
        self.assertEqual(D.drawer_rect(GAME)[3], round(1440 * (1 - D.BOTTOM)))

    def test_a_dragged_height_is_used(self):
        tall = D.tall_from_drag(1440, 1440)
        self.assertEqual(D.drawer_rect(GAME, tall=tall)[3], 1440)
        self.assertEqual(D.drawer_rect(GAME, tall=D.tall_from_drag(900, 1440))[3], 900)

    def test_it_follows_the_game_when_the_game_changes_size(self):
        tall = D.tall_from_drag(1440, 1440)
        self.assertEqual(D.drawer_rect((0, 0, 1920, 1080), tall=tall)[3], 1080)

    def test_never_taller_than_the_game_nor_tiny(self):
        self.assertEqual(D.tall_from_drag(5000, 1440), 1.0)
        self.assertEqual(D.tall_from_drag(10, 1440), D.TALL_LO)
        self.assertIsNone(D.tall_from_drag(100, 0))

    def test_top_and_width_do_not_move(self):
        a, b = D.drawer_rect(GAME), D.drawer_rect(GAME, tall=1.0)
        self.assertEqual(a[:3], b[:3])

    def test_the_page_keeps_it(self):
        import inspect
        from soe2 import drawer_page as P
        src = inspect.getsource(P)
        self.assertIn('tall=c.get("tall")', src)
        self.assertGreaterEqual(src.count("self._drawer_note_height()"), 3)


if __name__ == "__main__":
    unittest.main()
