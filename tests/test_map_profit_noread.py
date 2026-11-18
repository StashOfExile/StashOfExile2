"""3.0.6 (owner: "everyone will forget or ignore to read their inventory before a run"): a map with no read before
it still counts - all you came back with except Top Up supplies, marked ≈."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import mapprofit as MP  # noqa: E402
from soe2 import topup as TU  # noqa: E402
from soe2.mapprofit_page import MapProfitPage  # noqa: E402

PRICES = {"Exalted Orb": 0.002, "Divine Orb": 1.0, "Vaal Orb": 0.001}


class App(MapProfitPage):
    br_area = "hideout"

    def mp_on(self):
        return True

    def mp_price(self, n):
        return PRICES.get(n)

    def mp_refs(self):
        return None

    def mp_paint(self):
        pass

    def mp_map_name(self, where):
        return "Sun Temple"


class NoReadBefore(unittest.TestCase):
    def test_counts_all_but_supplies(self):
        a = App()
        logged = []
        inv = {"Exalted Orb": 20, "Divine Orb": 2, "Vaal Orb": 10}
        with mock.patch.object(MP, "identify", lambda *x: (dict(inv), 0)), \
                mock.patch.object(MP, "log_add", logged.append), \
                mock.patch.object(TU, "learned", lambda: {}), \
                mock.patch.object(TU, "cfg", lambda: {"items": [{"name": "Exalted Orb"}, {"name": "Vaal Orb"}]}):
            a.mp_area("map", "hideout", ("MapSunTemple",), False)          # in, no read first
            self.assertIsNotNone(a.mp_run, "the map is still counted")
            a.mp_area("hideout", "map", None, True)                          # back home
            a.mp_seen({"cells": [1]})                                        # the Read Key press
            e = a.mp_done()
        self.assertTrue(e and e.get("est"))
        self.assertEqual([r[0] for r in e["rows"]], ["Divine Orb"], "Top Up supplies are never loot")
        self.assertTrue(a.mp_bar_text().startswith("≈"))
        self.assertTrue(any("No read before this map" in x for x in a.mp_breakdown(e)))


if __name__ == "__main__":
    unittest.main()


class ReadCard(unittest.TestCase):
    def test_a_card_says_what_was_counted(self):
        # 3.0.6 (owner: "we need some verification that it read the profits")
        a = App()
        a.root = None
        shown = []
        inv = {"Divine Orb": 2}
        with mock.patch.object(MP, "identify", lambda *x: (dict(inv), 1)), \
                mock.patch.object(TU, "learned", lambda: {}), \
                mock.patch.object(TU, "cfg", lambda: {"items": []}), \
                mock.patch("soe2.alertcard.show", lambda *x, **k: shown.append(x) or None), \
                mock.patch("soe2.alerts_page.game_rect", lambda: (0, 0, 1920, 1080)):
            a.mp_area("map", "hideout", ("MapSunTemple",), False)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1]})
        self.assertTrue(shown)
        title, line = shown[0][1], shown[0][2]
        self.assertIn("Map counted", title)
        self.assertIn("Divine Orb +2", line)
        self.assertIn("1 not known", line)
