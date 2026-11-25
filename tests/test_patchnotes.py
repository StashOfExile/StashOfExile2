"""Patch Notes come from the board, which reads GGG's forum; the app keeps the last list."""
import unittest
from unittest import mock

from soe2 import patchnotes as PN


class FromBoard(unittest.TestCase):
    def test_keeps_only_https_links(self):
        saved = {}
        with mock.patch("soe2.patchnotes.cached", return_value={}), \
             mock.patch("soe2.patchnotes.save_json", side_effect=lambda f, d: saved.update(d)), \
             mock.patch("soe2.board.call", return_value=(True, {"notes": [
                 {"title": "0.5.5h Patch Notes", "url": "https://www.pathofexile.com/forum/view-thread/1", "at": 2},
                 {"title": "bad", "url": "javascript:x"}]})), \
             mock.patch("threading.Thread") as th:
            PN._busy["on"] = False
            PN.refresh(force=True)
            th.call_args.kwargs["target"]()
        self.assertEqual([n["title"] for n in saved["notes"]], ["0.5.5h Patch Notes"])

    def test_board_down_keeps_last_list(self):
        saved = {}
        have = {"notes": [{"title": "old", "url": "https://x"}], "at": 0}
        with mock.patch("soe2.patchnotes.cached", return_value=have), \
             mock.patch("soe2.patchnotes.save_json", side_effect=lambda f, d: saved.update(d)), \
             mock.patch("soe2.board.call", return_value=(False, "down")), \
             mock.patch("threading.Thread") as th:
            PN._busy["on"] = False
            PN.refresh(force=True)
            th.call_args.kwargs["target"]()
        self.assertEqual(saved["notes"][0]["title"], "old")


if __name__ == "__main__":
    unittest.main()
