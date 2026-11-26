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


class Rows(unittest.TestCase):
    def test_source_and_day(self):
        n = {"title": "x", "url": "https://store.steampowered.com/news/app/2694490/view/1", "at": 1788393600}
        self.assertEqual(PN.source_of(n), "Steam")
        self.assertEqual(PN.source_of({"url": "https://www.pathofexile.com/forum/view-thread/1"}), "GGG Forum")
        self.assertRegex(PN.day_of(n), r"^[A-Z][a-z]{2}, [A-Z][a-z]+ \d{1,2}, 20\d\d$")

    def test_new_after_the_first_list_until_opened(self):
        from soe2.config import SETTINGS
        keep = {k: SETTINGS.get(k) for k in ("patch_known", "patch_new")}
        try:
            SETTINGS.pop("patch_known", None); SETTINGS.pop("patch_new", None)
            with mock.patch("soe2.patchnotes.save_json"):
                PN._note_new([{"url": "a"}])
                self.assertFalse(PN.is_new({"url": "a"}))
                PN._note_new([{"url": "b"}, {"url": "a"}])
                self.assertTrue(PN.is_new({"url": "b"}))
                PN.mark_seen("b")
                self.assertFalse(PN.is_new({"url": "b"}))
        finally:
            for k, v in keep.items():
                SETTINGS.pop(k, None) if v is None else SETTINGS.__setitem__(k, v)
