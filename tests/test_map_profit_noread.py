"""3.0.6 (most players forget to read the inventory before a run): a map with no read before
it still counts - all you came back with except Top Up supplies, marked ≈."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from soe2 import mapprofit as MP  # noqa: E402
from soe2 import topup as TU  # noqa: E402
from soe2.mapprofit_page import MapProfitPage  # noqa: E402

_TMP = None


def setUpModule():                         # (the map in progress is saved: never into the real data folder)
    import tempfile
    from soe2 import config
    global _TMP
    _TMP = (tempfile.TemporaryDirectory(), mock.patch.object(config, "DATA_DIR", None))
    _TMP[1].new = _TMP[0].name
    _TMP[1].start()


def tearDownModule():
    _TMP[1].stop()
    _TMP[0].cleanup()


PRICES = {"Exalted Orb": 0.002, "Divine Orb": 1.0, "Vaal Orb": 0.001}


class App(MapProfitPage):
    br_area = "hideout"
    _mp_restored = True                    # (no state from another test)

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
        with mock.patch.object(MP, "identify", lambda *x, **k: (dict(inv), 0)), \
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


class ReadCard(unittest.TestCase):
    def test_a_check_window_lists_what_was_counted(self):
        # 3.0.6 (a confirmation box for the currency and inventory items read, like Scan stash on Wealth)
        import tkinter as tk
        from PIL import Image
        a = App()
        a.root = tk.Tk()
        a.root.withdraw()
        a.mp_save = lambda: None
        inv = {"Divine Orb": 2}

        def ident(*x, **k):
            k["info"]["unknown_cells"] = [(Image.new("RGB", (70, 70)), 1)]
            return dict(inv), 1
        try:
            with mock.patch.object(MP, "identify", ident), \
                    mock.patch.object(TU, "learned", lambda: {}), \
                    mock.patch.object(TU, "cfg", lambda: {"items": []}), \
                    mock.patch("soe2.alerts_page.game_rect", lambda: (0, 0, 1920, 1080)):
                a.mp_area("map", "hideout", ("MapSunTemple",), False)
                a.mp_area("hideout", "map", None, True)
                a.mp_seen({"cells": [1]})
            dlg = a.mp_rev
            tv = next(w for w in dlg.winfo_children()[2].winfo_children() if w.winfo_class() == "Treeview")
            names = [tv.item(i, "text") for i in tv.get_children()]
            self.assertEqual(names, ["Divine Orb"])           # (no "? not known" rows: currency it knows only)
            save = [b for b in dlg.winfo_children()[-1].winfo_children() if b.cget("text") == "Save"][0]
            save.invoke()
            self.assertEqual(a.mp_pending["fix"], {"Divine Orb": 2})
        finally:
            a.root.destroy()


class LearnedItems(unittest.TestCase):
    """3.0.6 (things already learned for Scan stash were missing): no stack number = not currency,
    look-alikes count as the cheaper one."""

    def test_no_stack_number_is_skipped_not_unknown(self):
        from soe2 import mapprofit as MP
        info = {}
        got, unknown = MP.identify([{"sig": None, "count": 1, "shown": False, "img": object()}], {}, refs=None,
                                   info=info)
        self.assertEqual((got, unknown, info["skipped"]), ({}, 0, 1))

    def test_look_alikes_are_never_a_guess(self):
        # owner: an ambiguous "looks like another item" result is not acceptable
        from unittest import mock
        from soe2 import mapprofit as MP
        cells = [{"sig": None, "count": 1, "shown": True, "img": object()}]
        info = {}
        with mock.patch.object(MP, "fv_match", return_value=["Perfect Essence of Abrasion",
                                                             "Perfect Essence of Enhancement"]):
            got, unknown = MP.identify(cells, {}, refs=object(), info=info)
        self.assertEqual((got, unknown), ({}, 1))
        self.assertTrue(info["alike"])

    def test_a_III_keeps_only_perfect_ones(self):
        known = {"Greater Orb of Augmentation": 1, "Perfect Regal Orb": 1, "Regal Orb": 1}
        self.assertEqual(MP.grade(["Greater Orb of Augmentation", "Perfect Regal Orb"], "III", known),
                         ["Perfect Regal Orb"])

    def test_six_is_read(self):
        from soe2 import topup as TU
        self.assertIn("6", TU.digit_templates())


class Restart(unittest.TestCase):
    """3.0.6 (restarting the program mid-run broke the profit count for that map)."""

    def _page(self, tmp):
        from soe2 import config
        p = MapProfitPage()
        p.mp_on = lambda: True
        p.mp_price = lambda n: 1.0
        p.mp_paint = lambda: None
        p.mp_map_name = lambda w: "Grotto"
        return p

    def test_same_map_after_a_restart_goes_on(self):
        import tempfile
        from soe2 import config
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "DATA_DIR", tmp):
            a = self._page(tmp)
            a.mp_home = {"t": __import__("time").time(), "counts": {"Chaos Orb": 2}, "unknown": 0}
            a.mp_area("map", "hideout", ("Grotto", 7), False)
            run = a.mp_run
            b = self._page(tmp)                               # the app restarted
            b.mp_area("map", None, ("Grotto", 7), False)
            self.assertEqual(b.mp_run["run"], run["run"])
            self.assertEqual(b.mp_run["before"]["counts"], {"Chaos Orb": 2})
            self.assertFalse(b.mp_run.get("est"))

    def test_restart_at_home_keeps_the_map_to_count(self):
        import tempfile
        from soe2 import config
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "DATA_DIR", tmp):
            a = self._page(tmp)
            a.mp_home = {"t": __import__("time").time(), "counts": {"Chaos Orb": 2}, "unknown": 0}
            a.mp_area("map", "hideout", ("Grotto", 7), False)
            b = self._page(tmp)                               # closed in the map, opened at home
            b.mp_area("hideout", None, ("Hideout", 1), False)
            self.assertIsNone(b.mp_run)
            self.assertEqual(b.mp_pending["where"], ("Grotto", 7))


if __name__ == "__main__":
    unittest.main()


class Waystones(unittest.TestCase):
    """3.0.6 (show waystones by tier without a price, to show they were read)."""

    def test_roman(self):
        self.assertEqual([MP.roman(x) for x in ("XV", "XIV", "IX", "XVI", "", "Q")], [15, 14, 9, 16, None, None])

    def test_the_shipped_waystone_is_tier_15(self):
        from PIL import Image
        from soe2.topup import _templates
        self.assertEqual(MP.waystone_tier(Image.open(_templates() / "waystone_cell.png")), 15)

    def test_counted_by_tier_with_no_number(self):
        from PIL import Image
        from soe2.topup import _templates
        cell = {"sig": None, "count": 1, "shown": False, "img": Image.open(_templates() / "waystone_cell.png")}
        self.assertEqual(MP.identify([cell], {}, refs=None)[0], {"Waystone (Tier 15)": 1})


class FavoursLookAlikes(unittest.TestCase):
    """3.0.6 (owner: a 22 div Omen of Sinistral Erasure tagged as a cheap omen - a costly miss)."""

    def test_maybe_names_close_ones_only(self):
        from soe2 import favours as FV
        top = [(0.82, "Omen of Resurgence", "learned"), (0.71, "Omen of Sinistral Erasure", "shipped"),
               (0.60, "Omen of Light", "learned")]
        self.assertEqual(FV.maybe_names(top), ["Omen of Resurgence", "Omen of Sinistral Erasure"])
        self.assertEqual(FV.maybe_names([(0.5, "X", "learned")]), [])

    def test_sinistral_erasure_ships(self):
        from soe2 import favours as FV
        sl = FV.shipped_learned()
        self.assertIn("Omen of Sinistral Erasure", sl["top"])
        self.assertIn("Omen of Light", sl["box"])


class SuppliesAboveKeep(unittest.TestCase):
    def test_picked_up_supplies_count_above_their_amount(self):
        a = App()
        logged = []
        seq = [{"Vaal Orb": 20}, {"Vaal Orb": 22}]
        with mock.patch.object(MP, "identify", lambda *x, **k: (dict(seq.pop(0)), 0)), \
                mock.patch.object(MP, "log_add", logged.append), \
                mock.patch.object(TU, "learned", lambda: {}), \
                mock.patch.object(TU, "cfg", lambda: {"items": [{"name": "Vaal Orb", "keep": 20}]}):
            a.mp_seen({"cells": [1]})                                        # before
            a.mp_area("map", "hideout", ("MapSunTemple", 1), False)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1]})                                        # after
            e = a.mp_done()
        self.assertEqual([(r[0], r[2] - r[1]) for r in e["rows"]], [("Vaal Orb", 2)])

    def test_greater_mark(self):
        known = {"Exalted Orb": 1, "Greater Exalted Orb": 1, "Perfect Exalted Orb": 1}
        self.assertEqual(MP.grade(["Exalted Orb"], "II", known), ["Greater Exalted Orb"])
        self.assertEqual(MP.grade(["Greater Exalted Orb"], "", known), ["Greater Exalted Orb"])
        self.assertEqual(MP.grade(["Exalted Orb"], "III", known), ["Perfect Exalted Orb"])
        self.assertEqual(MP.grade(["Divine Orb"], "II", {"Divine Orb": 1}), ["Divine Orb"])


class StashedAfterRead(unittest.TestCase):
    """Owner: yes - after the read that counts a map you stash; the next map counts from Top Up supplies only."""

    def test_an_item_picked_up_again_counts(self):
        a = App()
        logged = []
        seq = [{"Divine Orb": 1}, {"Divine Orb": 1}, {"Divine Orb": 1}]
        with mock.patch.object(MP, "identify", lambda *x, **k: (dict(seq.pop(0)), 0)), \
                mock.patch.object(MP, "log_add", logged.append), \
                mock.patch.object(TU, "learned", lambda: {}), \
                mock.patch.object(TU, "cfg", lambda: {"items": []}), \
                mock.patch.object(MapProfitPage, "mp_review", lambda *x: None):
            a.mp_seen({"cells": [1]})                                        # before map 1
            a.mp_area("map", "hideout", ("A", 1), False)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1]})                                        # map 1's read - then stashed
            a.mp_area("map", "hideout", ("B", 2), False)                     # map 2 (map 1 done)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1]})                                        # a Scrap again
            e = a.mp_done()
        self.assertEqual([(r[0], r[2] - r[1]) for r in e["rows"]], [("Divine Orb", 1)])


class FavoursJunk(unittest.TestCase):
    def test_no_stack_number_no_question_tag(self):
        # owner: junk uniques need no identifying
        import numpy as np
        from PIL import Image
        from soe2 import favours as FV
        from soe2.topup import _templates
        way = np.asarray(Image.open(_templates() / "waystone_cell.png").convert("RGB"))[:, :, ::-1].copy()
        img = np.zeros((200, 200, 3), np.uint8)
        img[10:80, 10:80] = way
        grid = (10, 10, 70, 70)
        with mock.patch.object(FV, "cell_rect", lambda g, r, c: (10, 10, 70, 70)):
            self.assertFalse(FV.has_stack_number(img, grid, 0, 0))


class EscHides(unittest.TestCase):
    def test_esc_hides_expedition_and_favours_tags(self):
        from soe2.app import App as RealApp
        hid = []

        class Fake:
            rm_win, fv_wins = [1], [1]
            remnant_hide = lambda self: hid.append("rm")
            favours_hide = lambda self: hid.append("fv")
        f = Fake()
        RealApp.esc_hide_tags(f)
        self.assertEqual(hid, ["rm", "fv"])


class CoveredReads(unittest.TestCase):
    """Owner's run: every read with the mouse over the inventory (covered); a Scrap from maps ago, since stashed,
    was still taken as 'went in with', so the new one wasn't counted."""

    def test_covered_reads_only(self):
        a = App()
        logged = []
        seq = [{"Divine Orb": 2}, {"Divine Orb": 2}, {"Divine Orb": 1}]
        with mock.patch.object(MP, "identify", lambda *x, **k: (dict(seq.pop(0)), 0)), \
                mock.patch.object(MP, "log_add", logged.append), \
                mock.patch.object(TU, "learned", lambda: {}), \
                mock.patch.object(TU, "cfg", lambda: {"items": []}), \
                mock.patch.object(MapProfitPage, "mp_review", lambda *x: None):
            a.mp_seen({"cells": [1], "covered": True})                       # before map 1 (covered)
            a.mp_area("map", "hideout", ("A", 1), False)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1], "covered": True})                       # map 1's read - then stashed
            a.mp_area("map", "hideout", ("B", 2), False)
            a.mp_area("hideout", "map", None, True)
            a.mp_seen({"cells": [1], "covered": True})                       # one picked up in map 2
            e = a.mp_done()
        self.assertEqual([(r[0], r[2] - r[1]) for r in e["rows"]], [("Divine Orb", 1)])
