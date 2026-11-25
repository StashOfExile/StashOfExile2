"""3.3.0 owner: every mod in Mod Lab says what kind it is: Prefix, Suffix, Implicit, Corrupted and so on."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import ratemods as RM  # noqa: E402
from soe2 import uniquedata as UD  # noqa: E402


class Kinds(unittest.TestCase):
    def setUp(self):
        RM.kinds_forget()
        self.addCleanup(RM.kinds_forget)

    def test_map_items_and_jewels_say_prefix_or_suffix(self):
        for s in ("tablet", "waystone", "relic", "jewel"):
            kinds = {e["kind"] for e in RM.entries(s)}
            self.assertTrue(kinds <= {"Prefix", "Suffix"} and kinds, (s, kinds))

    def test_gear_says_prefix_suffix_or_both(self):
        with mock.patch("soe2.gearbook.class_mods", lambda cls: [{"key": "gear:ring:a", "kind": "Prefix"},
                                                                 {"key": "gear:ring:b", "kind": "Either"}]):
            self.assertEqual(RM.mod_kind("gear:ring", ["gear:ring:a"]), "Prefix")
            self.assertEqual(RM.mod_kind("gear:ring", ["gear:ring:b"]), "Prefix or Suffix")
            self.assertEqual(RM.mod_kind("gear:ring", ["gear:ring:zzz"]), "")

    def test_uniques_say_implicit_explicit_or_corrupted(self):
        UD.reset({"Astramentis": {"group": "Amulets", "implicit": ["+(5-7) to all Attributes"],
                                  "explicit": ["-4 Physical Damage taken from Attack Hits"],
                                  "corruption": ["+1 to Level of all Skills"]}})
        self.addCleanup(UD.reset)
        with mock.patch("soe2.gearbook.store", lambda: {}):
            from soe2 import gearbook as GB
            rows = GB.unique_rows("Astramentis")
            got = [RM.mod_kind("unique:astramentis", [r["key"]]) for r in rows]
        self.assertEqual(got, ["Implicit", "Explicit", "Corrupted"])

    def test_every_word_is_a_word(self):
        self.assertTrue(all(w and w[0].isupper() for w in RM.KIND_WORDS.values()))


if __name__ == "__main__":
    unittest.main()
