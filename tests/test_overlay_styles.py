"""Overlay styles: legibility (4.5 : 1 on every pair drawn), Gilded gone with its saved setting falling back, and
Quick settings chips that keep the style's text color when off (the state is the mark, the edge and the field)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_contrast as CC  # noqa: E402
from soe2 import ovlight as OL, ovskins as OS, ovstylepick as SP  # noqa: E402
from soe2.ovquick import OverlayQuick, chip_colors  # noqa: E402


class _Chip:
    def __init__(self):
        self.opts = {}

    def config(self, **kw):
        self.opts.update(kw)

    def cget(self, k):
        return self.opts.get(k, "")


class _Stub(OverlayQuick):
    def __init__(self, Q):
        self.ovq_P = Q


class ContrastTests(unittest.TestCase):
    def test_every_overlay_pair_passes(self):
        bad = [(round(CC.ratio(fg, bg), 2), n, fg, bg) for n, fg, bg in CC.overlay_pairs() if CC.ratio(fg, bg) < CC.AA]
        self.assertEqual(bad, [])

    def test_every_skin_and_light_style_is_checked(self):
        names = " ".join(n for n, _f, _b in CC.overlay_pairs())
        for k in OS.ORNATE:
            self.assertIn(k + " ", names)
        for k in ("hairline", "slate", "micro"):
            self.assertIn(k + "/", names)

    def test_ornate_muted_reads_six_to_one(self):
        for k, s in OS.SKINS.items():
            self.assertGreaterEqual(CC.ratio(s["muted"], s["bg"]), 6.0, k)

    def test_ornate_skins_have_a_body_font(self):
        for k in OS.ORNATE:
            self.assertTrue(OS.palette(k).get("body"), k)


class GildedGone(unittest.TestCase):
    def test_not_in_the_lists(self):
        self.assertNotIn("gilded", OS.ORNATE)
        self.assertNotIn("gilded", OS.SKINS)
        self.assertNotIn("gilded", OL.STYLES)
        self.assertNotIn("gilded", SP.ABOUT)
        self.assertFalse([k for _t, ks in SP.GROUPS for k in ks if k == "gilded"])
        self.assertFalse(any(v.get("light") for v in OS.SKINS.values()))

    def test_saved_setting_falls_back(self):
        self.assertEqual(OL.look_valid("gilded"), "herald")
        self.assertIn(OL.look_valid("gilded"), OL.STYLES)
        self.assertEqual(OL.look_valid("nonsense"), "classic")
        self.assertEqual(OL.look_valid("totem"), "totem")

    def test_ov_look_reads_through_it(self):
        a = type("A", (OL.LightOverlay,), {"tracker_cfg": lambda self: {"look": "gilded"}})()
        self.assertEqual(a.ov_look(), "herald")


class QuickChips(unittest.TestCase):
    Q = {"bg": "#141210", "field": "#0c0a09", "text": "#ece4d4", "muted": "#b8ae9c", "line": "#5a4a32",
         "accent": "#e8a44a"}

    def test_off_chip_uses_text_color_and_dim_edge(self):
        c = chip_colors(self.Q, False)
        self.assertEqual((c["fg"], c["bg"], c["highlightbackground"]), (self.Q["text"], self.Q["bg"], self.Q["line"]))

    def test_on_chip_has_accent_edge_field_and_mark(self):
        c = chip_colors(self.Q, True)
        self.assertEqual((c["fg"], c["bg"], c["highlightbackground"]), (self.Q["text"], self.Q["field"], self.Q["accent"]))
        b = _Chip()
        _Stub(self.Q)._ovq_chip_look(b, True, "Regex")
        self.assertEqual(b.opts["text"], "✓ Regex")
        _Stub(self.Q)._ovq_chip_look(b, False, "Regex")
        self.assertEqual((b.opts["text"], b.opts["fg"]), ("Regex", self.Q["text"]))


if __name__ == "__main__":
    unittest.main()
