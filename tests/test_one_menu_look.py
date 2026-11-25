"""3.3.0 owner: drop-down styling must match across the app. Every menu is made by listkit._menu, in the drop-down
list's colors (style.menu_colors). Only the overlay's own menu keeps the overlay's colors."""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED = {"listkit.py", "overlay.py"}


class OneMenuLook(unittest.TestCase):
    def test_no_menu_makes_its_own_colors(self):
        found = []
        for path in glob.glob(os.path.join(ROOT, "soe2", "*.py")):
            if os.path.basename(path) in ALLOWED:
                continue
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if re.search(r"\btk\.Menu\(", line):
                        found.append(f"{os.path.basename(path)}:{n}")
        self.assertEqual(found, [], "use listkit._menu so every menu matches")

    def test_the_shared_menu_uses_the_drop_down_colors(self):
        from soe2 import style
        c = style.menu_colors()
        self.assertEqual(c["background"], style.C["panel2"])
        self.assertEqual(c["activeBackground"], style.C["sel"], "the same highlight as a drop-down list's")


if __name__ == "__main__":
    unittest.main()
