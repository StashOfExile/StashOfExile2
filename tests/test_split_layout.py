"""The Split layout (owner decision: Layout and Style are separate choices - Bar, Panel or Split, in every style).
Split replaced the old "flanks" style (removed): a saved one becomes Layout Split, Style Hairline. Each half fits
384 x 72 px on a 1440p game with real text, in every style; ⇄ Swap sides flips them; the windows over the game take
the style's palette (and its body font for small text).

    DISPLAY=:99 python3.12 -m unittest tests.test_split_layout"""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402

from soe2 import ovlight as OL, ovsplit as SP  # noqa: E402
from soe2.merged_page import LAYOUTS, MergedOverlay  # noqa: E402
from soe2.ova8 import OverlayA8  # noqa: E402
from soe2.ovlight import LightOverlay  # noqa: E402
from soe2.ovquick import OverlayQuick  # noqa: E402
from soe2.ovsplit import SplitOverlay  # noqa: E402

SAMPLE = {"a8_chip": "⌂ HIDEOUT", "a8_label": "LAST MAP", "a8_place": "Vaults of Kamasa", "a8_timer": "3:30",
          "session": "14:47:43", "profit": "+3 div"}
ALL_STYLES = list(OL.STYLES)


class _Notes:
    cfg = {"notes_enabled": True}

    def notes_shown(self):
        return False


class FakeApp(SplitOverlay, LightOverlay, OverlayA8, OverlayQuick, MergedOverlay):
    """The overlay's drawing parts of the App, with the rest stubbed."""

    def __init__(self, root, style="slate", layout="split", swap=False):
        self.root = root
        self.cfg = {"look": style, "layout": layout, "split_swap": swap, "mlocked": True, "clock": True,
                    "lines": {"map": True, "where": True, "session": True, "maps": True, "avg": True, "rank": True}}
        self.overlay = _Notes()
        self._hud_k = 1440 / 1080
        self.tk_ov_lbls, self.tk_ov_alerts, self.tk_ov_clock, self.tk_ov_cv = {}, {}, None, None

    def tracker_cfg(self):
        return self.cfg

    def tracker_save(self):
        pass

    def tracker_numbers(self):
        return {"maps": "6", "avg": "6:01"}

    def ov_spot(self):
        return "bottom"

    def ov_camp_mode(self):
        return False

    def bar_buttons(self):
        return ["notes", "calc", "regex", "rates", "app"]

    def mp_on(self):
        return True

    def mp_bar_bind(self, cv, item):
        cv.addtag_withtag("mg_profit", item)

    def calc_ov_shown(self):
        return False

    def ovr_shown(self):
        return False

    def calc_ov_toggle(self):
        pass

    def ovr_toggle(self):
        pass

    def camp_vendor_toggle(self):
        pass

    def app_show(self, **_kw):
        pass

    def merged_set(self, layout=None):
        if layout in LAYOUTS:
            self.cfg["layout"] = layout
        self.rebuilt = getattr(self, "rebuilt", 0) + 1

    def fill(self):
        for k, lab in self.tk_ov_lbls.items():
            lab.config(text=SAMPLE.get(k, ""))
        if self.tk_ov_clock is not None:
            self.tk_ov_clock.config(text="9:50 PM")


def build_half(root, style, half, swap=False, host=None):
    """-> (app, frame, canvas) of one Split half of `style`, filled with real text, at 1440p."""
    from soe2.overlaywin import OverlayFrame, _seed
    from soe2 import themes as TH
    a = FakeApp(root, style, swap=swap)
    P = a.split_palette(style)
    _seed(TH, P)
    a.mg_P = P
    f = OverlayFrame(host or root, P)
    cv = f.canvas_body()
    W, H = a.split_half(f, cv, P, {"bar": True, "timer": True, "helpers": False, "notes": False}, half)
    cv.configure(width=W, height=H)
    a.fill()
    return a, f, cv


def _fresh_caches():
    """Fonts and gear pictures are kept per run (one Tk root in the app); each test class has its own root."""
    from soe2 import gearicon
    OL._FM_CACHE.clear()
    gearicon._CACHE.clear()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _fresh_caches()
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        _fresh_caches()


class Layouts(unittest.TestCase):
    def test_bar_panel_split(self):
        self.assertEqual(list(LAYOUTS.values()), ["Bar", "Panel", "Split"])
        self.assertEqual(LAYOUTS["split"], "Split")

    def test_split_is_not_a_style(self):
        self.assertNotIn("flanks", OL.STYLES)            # (removed: a Layout now)
        self.assertNotIn("Split", OL.STYLES.values())

    def test_names_has_split_and_swap(self):
        from soe2 import names
        self.assertIn("Split", names.FEATURES)
        self.assertIn("Swap sides", names.FEATURES)
        self.assertTrue(SP.SWAP.endswith("Swap sides"))


class Migration(unittest.TestCase):
    def test_saved_flanks_becomes_split(self):        # (test data: the removed style's key)
        cfg = {"look": "flanks", "layout": "xpbar", "lt_pos": {"flanks": [[1, 2]]}}
        self.assertTrue(OL.retire_look(cfg))
        self.assertEqual((cfg["look"], cfg["layout"]), ("hairline", "split"))
        self.assertNotIn("lt_pos", cfg)
        self.assertFalse(OL.retire_look(cfg))

    def test_migration_step(self):
        from soe2 import migrations as M
        S = {"tracker": {"look": "flanks", "layout": "panel"}}          # (removed style, test data)
        self.assertIn("split_layout", M.run(S, "settings"))
        self.assertEqual((S["tracker"]["look"], S["tracker"]["layout"]), ("hairline", "split"))

    def test_ov_look_reads_through_it(self):
        a = type("A", (LightOverlay,), {})()
        cfg = {"look": "flanks"}                                          # (removed style, test data)
        a.tracker_cfg = lambda: cfg
        self.assertEqual(a.ov_look(), "hairline")
        self.assertEqual(cfg["layout"], "split")

    def test_gilded_still_falls_back(self):
        self.assertEqual(OL.look_valid("gilded"), "herald")


class Halves(Base):
    def test_every_style_builds_both_halves_within_384_by_72(self):
        k = 1440 / 1080
        for style in ALL_STYLES:
            for half in ("run", "tools"):
                with self.subTest(style=style, half=half):
                    a, f, cv = build_half(self.root, style, half)
                    f.pack()
                    self.root.update_idletasks()
                    w, h = f.winfo_reqwidth(), f.winfo_reqheight()
                    self.assertLessEqual(w, round(SP.HALF[0] * k), (style, half, w))
                    self.assertLessEqual(h, round(SP.HALF[1] * k), (style, half, h))
                    self.assertGreater(len(cv.find_all()), 5)
                    bb = cv.bbox("mg")                     # nothing drawn past the canvas
                    W, H = int(cv.cget("width")), int(cv.cget("height"))
                    self.assertGreaterEqual(bb[0], -3)          # (a band's edge pixels; Tk's bbox adds 1-2 px)
                    self.assertLessEqual(bb[2], W + 3, (style, half, bb, W))
                    self.assertLessEqual(bb[3], H + 3, (style, half, bb, H))
                    f.destroy()

    def test_run_half_says_it_all(self):
        a, f, cv = build_half(self.root, "herald", "run")
        texts = " ".join(cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text")
        for word in ("HIDEOUT", "LAST MAP", "Vaults", "3:30", "SESSION", "14:47:43", "LAST MAP'S PROFIT", "+3 div",
                     "ⓘ"):
            self.assertIn(word, texts)
        self.assertEqual(texts.count("ⓘ"), 2)               # (Herald has no halos round its text)
        f.destroy()

    def test_tools_half_has_tools_clock_lock_gear_with_tips(self):
        a, f, cv = build_half(self.root, "psionic", "tools")
        for tag in ("mg_notes", "mg_calc", "mg_regex", "mg_rates", "mg_app", "mg_lock", "mg_cog"):
            self.assertTrue(cv.find_withtag(tag), tag)
            self.assertIn("<Enter>", cv.tag_bind(tag), tag + " has a tooltip")
        rows = {tag: cv.bbox(tag)[1] for tag in ("mg_notes", "mg_app", "mg_cog")}
        self.assertLess(rows["mg_notes"], rows["mg_app"], "tools on row 1, App ▸ on row 2")
        self.assertEqual(a.tk_ov_clock.text, "9:50 PM")
        f.destroy()

    def test_hairline_is_the_old_boxless_look(self):
        P = OL.palette("hairline", OL.DEFAULT_COLORS)
        self.assertEqual(bool(P["boxless"]), OL.can_see_through())
        self.assertIn("hairline", OL.BOXLESS)


class Swap(Base):
    def test_swap_sides_flips_them(self):
        a = FakeApp(self.root)
        self.assertEqual((a.split_side("run"), a.split_side("tools")), ("left", "right"))
        a.cfg["sp_pos"] = {"run": [1, 2]}
        a.split_swap_set(True)
        self.assertEqual((a.split_side("run"), a.split_side("tools")), ("right", "left"))
        self.assertNotIn("sp_pos", a.cfg)
        self.assertEqual(a.rebuilt, 1)

    def test_places_by_the_orbs(self):
        x, y = SP.place("left", 384, 72, (0, 0, 2560, 1440))
        self.assertTrue(270 <= x <= 300 and 1150 <= y <= 1165, (x, y))
        x, y = SP.place("right", 384, 72, (0, 0, 2560, 1440))
        self.assertTrue(1860 <= x <= 1880 and 1140 <= y <= 1160, (x, y))
        x, y = SP.place("right", 384, 72, (0, 0, 3440, 1440))         # ultrawide: still by the mana orb
        self.assertEqual(x, 3440 - 2560 + SP.place("right", 384, 72, (0, 0, 2560, 1440))[0])

    def test_quick_settings_has_swap_only_in_split(self):
        from soe2 import ovquick as Q
        self.assertIn("Swap sides", Q.QUICK_TIPS)
        self.assertIn("Split", Q.QUICK_TIPS["Layout"])
        with open(Q.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('if self.merged_layout() == "split":', src)


class Windows(Base):
    """The windows over the game take the overlay's palette - colors, frame - and its body font for small text."""

    def setUp(self):
        from soe2 import overlaywin as OW
        self.OW = OW
        self.was = OW.OV_PAL[0]
        from soe2 import ovskins
        self.P = ovskins.palette("herald")
        OW.OV_PAL[0] = lambda: self.P

    def tearDown(self):
        self.OW.OV_PAL[0] = self.was

    def test_pal_is_the_style(self):
        self.assertIs(self.OW.pal(), self.P)
        self.assertEqual(self.OW.body_font(self.P), self.P["body"])

    def test_windows_use_pal_and_body_font(self):
        import inspect
        from soe2 import alertcard, calc, music_page, overlay, ovrates
        for mod, fn in ((calc.CalcOverlay, "calc_ov_build"), (music_page.MusicPage, "music_build"),
                        (ovrates.OverlayRates, "ovr_fill"), (MergedOverlay, "rx_ov_show")):
            src = inspect.getsource(getattr(mod, fn))
            self.assertNotIn('font=(P["font"]', src, f"{fn}: small text in the display font")
        self.assertIn("pal()", inspect.getsource(alertcard.Card.render))
        self.assertIn("skin_inner", inspect.getsource(alertcard.Card.render))
        self.assertIn("body_font", inspect.getsource(overlay))

    def test_quick_settings_takes_the_style(self):
        a = FakeApp(self.root, "herald")
        a.ov_look = lambda: "herald"
        Q = a.ov_quick_style()
        self.assertEqual((Q["bg"], Q["band"], Q["body"]), (self.P["bg"], self.P["band"], self.P["body"]))

    def test_overlay_window_frame_and_colors(self):
        w = self.OW.OverlayWindow(self.root, "Calculator", "x", (0, 0, None, None), palette=self.OW.pal(),
                                  locked=True)
        try:
            self.assertEqual(w.cget("bg"), self.P["leather"])
            self.assertEqual(w.body.cget("bg"), self.P["bg"])
        finally:
            w.destroy()


if __name__ == "__main__":
    unittest.main()
