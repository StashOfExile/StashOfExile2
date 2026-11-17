"""modlists.json (tablet + jewel mods; replaced tabs.txt / jewels.txt) loads and feeds the Mod rules pages."""
import json
import os
import unittest

from soe2 import mods, wealth

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ModlistsTest(unittest.TestCase):
    def test_file_shape(self):
        d = json.load(open(os.path.join(ROOT, "modlists.json"), encoding="utf-8"))
        self.assertEqual(d["version"], 3)
        self.assertIn("RePoE", d["source"])
        self.assertGreaterEqual(len(d["tablets"]), 8)
        self.assertGreaterEqual(len(d["jewels"]), 8)
        for name, secs in {**d["tablets"], **d["jewels"]}.items():
            self.assertTrue(secs.get("Prefix") and secs.get("Suffix"), name)

    def test_loaded(self):
        self.assertGreater(len(mods.TABS), 50)
        self.assertGreater(len(mods.JEWELS), 200)
        self.assertTrue(any("Prefix" in k for k in mods.TAB_KINDS.values()))
        self.assertTrue(any("Suffix" in k for k in mods.JEWEL_KINDS.values()))
        self.assertTrue(all("(" not in t for t, _ in mods.TABS.values()))      # ranges became #

    def test_split_bases(self):
        self.assertIn("Abyss Tablet", wealth.split_bases("map.tablet"))
        self.assertIn("Ruby", wealth.split_bases("jewel"))
        self.assertEqual(wealth.split_bases("weapon"), [])

    def test_txt_files_gone(self):
        for f in ("tabs.txt", "jewels.txt"):
            self.assertFalse(os.path.exists(os.path.join(ROOT, f)))


if __name__ == "__main__":
    unittest.main()
