"""3.3.0 owner: the game's item window stayed up after a price check, as if Alt were still held. The copy lets go
of Alt, and Alt is let go again shortly after, only while the game is in front."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import overlay as O  # noqa: E402

ALT, CTRL, C = 0x12, 0x11, 0x43


class Copy(unittest.TestCase):
    def test_copy_ends_with_every_key_up(self):
        sent = []
        O.send_copy(sender=sent.extend)
        down = set()
        for vk, _ch, up in sent:
            down.discard(vk) if up else down.add(vk)
        self.assertEqual(down, set())
        self.assertIn((C, None, False), sent)

    def test_release_alt_only_lets_go(self):
        sent = []
        O.release_alt(sender=sent.extend)
        self.assertEqual(sent, [(ALT, None, True)])

    def test_alt_is_let_go_again_soon_after(self):
        self.assertTrue(O.ALT_AGAIN)
        self.assertEqual(list(O.ALT_AGAIN), sorted(O.ALT_AGAIN))
        self.assertLessEqual(max(O.ALT_AGAIN), 0.5)

    def test_the_key_only_goes_to_the_game(self):
        import inspect
        from soe2 import utilities_page as U
        src = inspect.getsource(U)
        body = src[src.index("for at in ALT_AGAIN"):src.index("threading.Thread(target=go")]
        self.assertLess(body.index("game_active(title)"), body.index("release_alt()"))
        self.assertIn("if front:", body)


if __name__ == "__main__":
    unittest.main()
