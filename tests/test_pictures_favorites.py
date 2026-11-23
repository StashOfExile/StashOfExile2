"""3.3.0 batch 1, Price Checks: a picture for every item class, shipped; Favorites as a Price Checks tab; the ☆ Favorite
button; Prices in with the trade filters' choices.

    DISPLAY=:99 python3.12 -m unittest tests.test_pictures_favorites          (or tests/runall.sh)"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-pics-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import pricecheck_page as PC          # noqa: E402
from soe2 import pricefmt as PF                 # noqa: E402
from soe2.config import SETTINGS                # noqa: E402

RING = "https://web.poecdn.com/gen/image/x/ring/Ring1.png"


class Pictures(unittest.TestCase):
    def setUp(self):
        PC._ICONS = None
        PC._CLASS_ART["n"] = -1

    def tearDown(self):
        PC._ICONS = None
        PC._CLASS_ART["n"] = -1

    def test_shipped_class_pictures_are_bundled(self):
        from soe2.class_icons import CLASS_ICONS
        self.assertEqual(len(CLASS_ICONS), 31, "every class")
        for base, url in CLASS_ICONS.items():
            self.assertTrue(url.startswith(("https://web.poecdn.com/", "https://raw.githubusercontent.com/")), base)
            self.assertFalse(PC.unique_art(url), f"{base}: a unique's art")
            self.assertEqual(PC.BUNDLED_ICONS[base], url)

    def test_every_base_has_its_own_link(self):
        from soe2 import gamedata
        bases = gamedata.load().get("bases") or {}
        gear = [b for b, e in bases.items() if e.get("class") not in ("waystone", "tablet")]
        self.assertEqual(sorted(PC.BASE_ART), sorted(gear), "every base")
        url = PC.art_url("Rattling Sceptre")
        self.assertTrue(url.startswith("https://raw.githubusercontent.com/repoe-fork/poe2/"), url)
        self.assertTrue(url.endswith("/Scepters/Basetypes/Sceptre01.png"), url)

    def test_a_base_without_its_own_picture_gets_its_class(self):
        with mock.patch.object(PC, "CLASS_ICONS", {"Iron Ring": RING}), mock.patch.object(PC, "BASE_ART", {}), \
                mock.patch.dict(PC.BUNDLED_ICONS, {"Iron Ring": RING}):
            PC._ICONS = None
            self.assertEqual(PC.art_url("Iron Ring"), RING)
            self.assertEqual(PC.art_url("Ruby Ring"), RING, "same class")
            self.assertIsNone(PC.art_url("Andvarius"), "a unique's name never gets a base's picture")
            self.assertIsNone(PC.art_url("Not An Item"))

    def test_currency_and_runes_come_from_the_trade_sites_list(self):
        from soe2.config import P
        os.makedirs(os.path.dirname(P("trade_static.json")), exist_ok=True)
        with open(P("trade_static.json"), "w", encoding="utf-8") as f:
            json.dump({"result": [{"id": "Currency", "entries": [
                {"id": "exalted", "text": "Exalted Orb", "image": "/gen/image/ex/CurrencyAddModToRare.png"}]}]}, f)
        PC._STATIC["key"] = None
        self.assertEqual(PC.art_url("Exalted Orb"), "https://web.poecdn.com/gen/image/ex/CurrencyAddModToRare.png")

    def test_the_build_tool_keeps_only_base_art(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import build_class_icons as B
        by = {"ring": ["Iron Ring", "Ruby Ring"], "belt": ["Heavy Belt"]}
        unique = "https://web.poecdn.com/gen/image/WzI1LCAxNCwgeyJmIjogIjJESXRlbXMvUmluZ3MvVW5pcXVlcy9BbmR2YXJpdXMiLCAidyI6IDEsICJoIjogMX1d/x/a.png"
        with mock.patch("soe2.config.load_json", return_value={"Iron Ring": unique, "Ruby Ring": RING}):
            got = B.from_learned(by)
        self.assertEqual(got, {"ring": ("Ruby Ring", RING)})


class PricesIn(unittest.TestCase):
    def test_same_choices_as_the_trade_filters(self):
        from soe2.trade import CURRENCY_CHOICES
        self.assertEqual([t for _k, t in PF.PRICE_UNITS], [t for t, _v in CURRENCY_CHOICES])

    def test_an_old_vaal_setting_falls_back(self):
        old = SETTINGS.get("price_unit")
        try:
            SETTINGS["price_unit"] = "vaal"
            self.assertEqual(PF.price_unit(), "auto")
            SETTINGS["price_unit"] = "exalted_divine"
            with mock.patch.object(PF.RATES, "value", lambda cur: 0.01 if cur == "exalted" else None):
                self.assertEqual(PF.fmt_div(3), "3 div")
                self.assertEqual(PF.fmt_div(0.5), "50.00 exalted")
        finally:
            SETTINGS["price_unit"] = old


class Words(unittest.TestCase):
    def test_star_and_tab(self):
        src = {n: open(os.path.join(ROOT, "soe2", n), encoding="utf-8").read()
               for n in ("pricecheck_page.py", "bulk_page.py", "favorites_page.py", "sidebar.py")}
        self.assertIn('text="☆ Favorite"', src["pricecheck_page.py"])
        self.assertIn('text="☆ Favorite"', src["bulk_page.py"])
        self.assertIn('"★ Favorited" if on else "☆ Favorite"', src["favorites_page.py"])
        self.assertIn('["Check", "History", "Favorites"]', src["pricecheck_page.py"])
        self.assertNotIn('"favorites"', src["sidebar.py"], "no sidebar row of its own")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "modules", "favorites.py")))


if __name__ == "__main__":
    unittest.main()
