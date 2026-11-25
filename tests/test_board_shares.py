"""3.3.0: the board's pooled prices count each install once (board/test/shares.test.mjs), and a refused
community send is written to the app's log instead of passing silently."""
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import communitymods as CM  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BoardShares(unittest.TestCase):
    def test_the_board_s_own_test_passes(self):
        if not shutil.which("node"):
            self.skipTest("needs node")
        r = subprocess.run(["node", os.path.join(ROOT, "board", "test", "shares.test.mjs")], capture_output=True,
                           text=True, timeout=120)
        self.assertIn("shares: ok", r.stdout, r.stderr[-1500:])


class RefusedSend(unittest.TestCase):
    def send(self, answer):
        seen = []
        with mock.patch.object(CM.B, "configured", lambda: True), mock.patch.object(CM, "sharing", lambda: True), \
                mock.patch("soe2.privacy.is_private_league", lambda *_a: False), \
                mock.patch.object(CM, "summary", lambda *a: ([{"base": "Ring"}], [], 1.0)), \
                mock.patch.object(CM, "vote_changes", lambda *a: []), \
                mock.patch.object(CM, "unmatched_unsent", lambda *a: []), \
                mock.patch.object(CM, "gems_unsent", lambda *a: ([], 0)), \
                mock.patch.object(CM, "sent_state", lambda: {}), mock.patch.object(CM, "cid", lambda: "a" * 32), \
                mock.patch("soe2.maplib.ranks", lambda: {}), mock.patch("soe2.campaign.to_pool", lambda: []), \
                mock.patch("soe2.buglog.record", lambda *a, **k: seen.append(a)):
            got = CM.push({}, {}, call=lambda *a, **k: answer)
        return got, seen

    def test_a_refusal_is_written_down(self):
        got, seen = self.send((False, "too many today"))
        self.assertEqual(got, (False, "too many today"))
        self.assertEqual(seen, [("net", "community data send", "too many today")])

    def test_waiting_for_the_next_hour_is_not_an_error(self):
        _got, seen = self.send((False, "too soon"))
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
