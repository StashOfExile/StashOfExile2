"""3.3.0 owner: Mod Lab showed Megalomaniac as 0 of 0. A unique with nothing to rate is not listed."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import ratemods_page  # noqa: E402


class EmptyUniques(unittest.TestCase):
    def test_a_unique_with_no_mods_is_left_out(self):
        class H(ratemods_page.RateModsPage):
            records = {}
        h = H()
        rows = {"Megalomaniac": [], "Headhunter": [{"key": "k1", "text": "+1 to Strength"}]}
        with mock.patch("soe2.gearbook.store", lambda: {"Megalomaniac": {}, "Headhunter": {}}), \
                mock.patch("soe2.gearbook.classes", lambda: []), \
                mock.patch("soe2.gearbook.unique_rows", lambda name: rows.get(name, [])), \
                mock.patch("soe2.ratemods.entries", lambda s, mods=None: [{"keys": k} for k, _t in (mods or [])]):
            names = [lab for s, lab in h.rm_sets() if s.startswith("unique:")]
        self.assertEqual(names, ["Headhunter"])


if __name__ == "__main__":
    unittest.main()
