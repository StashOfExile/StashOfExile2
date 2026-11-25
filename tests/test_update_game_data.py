"""tools/update_game_data.py: nothing is removed, new items are marked, a big drop stops the run."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import update_game_data as U   # noqa: E402


class KeepAndMark(unittest.TestCase):
    def test_unique_left_out_is_kept_and_marked(self):
        old = {"uniques": {"Headhunter": {"group": "Belts"}, "Kaom's Heart": {"group": "Body Armours"}}}
        new = {"uniques": {"Headhunter": {"group": "Belts"}, "Mageblood": {"group": "Belts"}}}
        self.assertEqual(U.keep_missing("uniquedata.json", old, new, "1.0.0"), 1)
        self.assertEqual(new["uniques"]["Kaom's Heart"]["gone"], "1.0.0")
        self.assertEqual(U.mark_new("uniquedata.json", old, new, "1.0.0"), 1)
        self.assertEqual(new["uniques"]["Mageblood"]["added"], "1.0.0")

    def test_search_rows_keep_their_shape(self):
        old = {"rows": [["A", "Unique Items", "Belt", "", ""], ["B", "Unique Items", "Ring", "", ""]]}
        new = {"rows": [["A", "Unique Items", "Belt", "", ""], ["C", "Unique Items", "Ring", "", ""]]}
        U.keep_missing("searchdata.json", copy.deepcopy(old), new, "1.0.0")
        U.mark_new("searchdata.json", old, new, "1.0.0")
        self.assertTrue(all(len(r) == 5 for r in new["rows"]))
        self.assertEqual(new["gone"], {"B|Unique Items": "1.0.0"})
        self.assertEqual(new["added"], {"C|Unique Items": "1.0.0"})

    def test_game_search_row_says_not_in_files(self):
        old = {"rows": [{"id": "x", "name": "X", "props": []}]}
        new = {"rows": []}
        U.keep_missing("gamedb.json", old, new, "1.0.0")
        self.assertIn(["Not in the files of", "1.0.0"], new["rows"][0]["props"])

    def test_dry_run_changes_nothing(self):
        self.assertEqual(U.main(["--dry"]), 0)


if __name__ == "__main__":
    unittest.main()
