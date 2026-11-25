"""3.3.0 owner: Market Insights' Mods worth the most table is gone; the list of mods hidden in it goes with it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import insights_page, migrations


class Gone(unittest.TestCase):
    def test_the_page_has_no_mods_table(self):
        src = open(insights_page.__file__, encoding="utf-8").read()
        self.assertNotIn('table(0, 1,', src)
        self.assertFalse(hasattr(insights_page.InsightsPage, "refresh_insights")
                         and "worth the most" in src.split('"""', 2)[2])

    def test_the_saved_list_is_cleared(self):
        S = {"ins_hidden_mods": ["a|b"], "league": "Standard"}
        migrations._insights_mods_gone_330(S)
        self.assertEqual(S, {"league": "Standard"})
        self.assertIn("insights_mods_gone_330", [s[0] for s in migrations.STEPS])


if __name__ == "__main__":
    unittest.main()
