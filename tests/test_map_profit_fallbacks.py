"""3.0.6 Map Profit names every item poe.ninja's exchange lists without teaching: a gem with no stack number
(lineage / uncut, by its level), Scan stash's wildcard pictures, and poe.ninja's art from the art cache as the last
fallback - each only when it's sure, never a guess. Synthetic pictures only."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from soe2 import favours as FV  # noqa: E402
from soe2 import mapprofit as MP  # noqa: E402

_TMP = None


def setUpModule():                         # (the art cache: never the real data folder)
    from soe2 import config
    global _TMP
    _TMP = (tempfile.TemporaryDirectory(), mock.patch.object(config, "DATA_DIR", None))
    _TMP[1].new = _TMP[0].name
    _TMP[1].start()


def tearDownModule():
    _TMP[1].stop()
    _TMP[0].cleanup()


def art(seed):
    """A made-up item picture (64 x 64 BGRA): a few colored shapes on a clear ground, different per seed."""
    rng = np.random.default_rng(seed)
    im = np.zeros((64, 64, 4), np.uint8)
    for _ in range(5):
        col = tuple(int(v) for v in rng.integers(60, 255, 3)) + (255,)
        pts = rng.integers(8, 56, (4, 2)).astype(np.int32)
        cv2.fillPoly(im, [pts], col)
    cv2.circle(im, tuple(int(v) for v in rng.integers(20, 44, 2)), int(rng.integers(6, 14)),
               tuple(int(v) for v in rng.integers(60, 255, 3)) + (255,), -1)
    return im


def cell_of(pic, letters=""):
    """The inventory cell the game would draw for this picture (70 x 70, a frame around it) - PIL, as Top Up
    splits the grid. letters: a white roman level at the bottom right ("V")."""
    c = np.zeros((70, 70, 3), np.uint8)
    c[:] = (20, 20, 20)
    c[FV.EDGE:FV.CELL - FV.EDGE, FV.EDGE:FV.CELL - FV.EDGE] = FV.art_cell(pic)
    if letters == "V":
        cv2.line(c, (50, 47), (55, 62), (255, 255, 255), 2)
        cv2.line(c, (55, 62), (60, 47), (255, 255, 255), 2)
    return Image.fromarray(c[:, :, ::-1].copy())


def box(pic):
    return FV.art_box(FV.art_cell(pic), corner=False)


class ArtKey(unittest.TestCase):
    def test_one_picture_many_names(self):
        self.assertEqual(FV.art_key(["Divine Orb"]), "Divine Orb")
        self.assertEqual(FV.art_key(["Uncut Skill Gem (Level 5)", "Uncut Skill Gem (Level 12)"]), "Uncut Skill Gem")
        self.assertEqual(FV.art_key(["Regal Orb", "Greater Regal Orb", "Perfect Regal Orb"]), "Regal Orb")
        self.assertIsNone(FV.art_key(["Greater Regal Orb", "Perfect Regal Orb"]), "no plain orb: not told apart")
        self.assertIsNone(FV.art_key(["Liquid Envy", "Ancient Liquid Envy"]), "other items: never told apart")

    def test_art_cell(self):
        a = art(1)
        a[:, :, 3] = 0                                              # all clear: only the cell's blue
        self.assertEqual(tuple(FV.art_cell(a)[10, 10]), FV.ART_BACKING)
        self.assertIsNone(FV.art_cell(np.zeros((128, 64, 4), np.uint8)), "a big item's picture isn't a cell")

    def test_cache_file_names(self):
        from soe2.config import P
        u = "https://web.poecdn.com/gen/image/x/y/A.png"
        self.assertIsNone(FV.art_cache_file(u))
        os.makedirs(P("art"), exist_ok=True)
        import hashlib
        p = os.path.join(P("art"), "cur_" + hashlib.sha1(u.encode()).hexdigest()[:20] + ".png")
        cv2.imwrite(p, art(2))
        self.assertEqual(FV.art_cache_file(u), p)
        self.assertEqual(FV.art_url("/gen/image/x/y/A.png"), u)
        self.assertIsNone(FV.art_url("relative.png"))

    def test_art_refs_only_from_the_cache(self):
        pics = {"https://web.poecdn.com/a.png": art(3), "https://web.poecdn.com/u.png": art(4)}
        items = {"a": ("Alpha Orb", "/a.png"), "m": ("Missing Orb", "/m.png"),
                 "u1": ("Uncut Skill Gem (Level 1)", "/u.png"), "u2": ("Uncut Skill Gem (Level 2)", "/u.png")}
        refs = FV.art_refs(items, pic=pics.get)
        self.assertEqual(sorted(refs.items), ["Alpha Orb", "Uncut Skill Gem"])
        self.assertEqual(refs.groups["Uncut Skill Gem"], ["Uncut Skill Gem (Level 1)", "Uncut Skill Gem (Level 2)"])


def art_only(pics):
    """Refs with no learned pictures and poe.ninja's art for {name: picture}."""
    refs = FV.Refs()
    refs.art = FV.art_refs({n: (n, "/" + str(i)) for i, n in enumerate(pics)},
                           pic=lambda u: list(pics.values())[int(u.rsplit("/", 1)[1])])
    return refs


class ArtFallback(unittest.TestCase):
    PICS = {"Alpha Orb": art(10), "Beta Orb": art(11), "Gamma Orb": art(12)}

    def test_the_right_item(self):
        refs = art_only(self.PICS)
        self.assertEqual(MP.fv_match(cell_of(self.PICS["Beta Orb"]), refs), "Beta Orb")

    def test_nothing_like_it(self):
        refs = art_only(self.PICS)
        self.assertIsNone(MP.fv_match(cell_of(art(99)), refs))

    def test_two_alike_pictures_name_nothing(self):
        pics = dict(self.PICS, **{"Twin Orb": self.PICS["Beta Orb"].copy()})
        self.assertIsNone(MP.fv_match(cell_of(self.PICS["Beta Orb"]), art_only(pics)), "no clear lead")

    def test_a_learned_picture_of_another_item_wins_over_art(self):
        refs = art_only(self.PICS)
        refs.add("Delta Orb", box(self.PICS["Beta Orb"]), "learned", "box")
        self.assertEqual(MP.fv_match(cell_of(self.PICS["Beta Orb"]), refs), "Delta Orb", "learned is trusted first")
        with mock.patch.object(FV, "MATCH_MIN", dict(FV.MATCH_MIN, learned=2.0)):     # (Delta never sure...)
            self.assertIsNone(MP.fv_match(cell_of(self.PICS["Beta Orb"]), refs), "...but close: no art guess")

    def test_strict_numbers(self):
        self.assertGreaterEqual(FV.ART_MIN, 0.80)
        self.assertGreaterEqual(FV.ART_BY, FV.MATCH_BY_SURE)


class Gems(unittest.TestCase):
    """A lineage or uncut gem shows no stack number: only gem pictures compete, an uncut gem by its level."""

    def refs(self):
        refs = FV.Refs()
        self.lin, self.gear = art(20), art(21)
        refs.add("Uhtred's Constellation", box(self.lin), "exchange", "box")
        refs.add("Catha's Brilliance", box(art(22)), "exchange", "box")
        refs.add("Divine Orb", box(art(23)), "learned", "box")
        refs.gems = {"Uhtred's Constellation", "Catha's Brilliance",
                     "Uncut Support Gem (Level 4)", "Uncut Support Gem (Level 5)"}
        self.uncut = art(24)
        refs.art = FV.art_refs({"u4": ("Uncut Support Gem (Level 4)", "/u"), "u5": ("Uncut Support Gem (Level 5)", "/u"),
                                "d": ("Divine Orb", "/d")},
                               pic={"https://web.poecdn.com/u": self.uncut,
                                    "https://web.poecdn.com/d": art(23)}.get)
        return refs

    def test_gem_names(self):
        parts = {"LineageSupportGems": {"names": {"a": "Uhtred's Rite", "d": "Divine Orb"}},
                 "UncutGems": {"names": {"u": "Uncut Skill Gem (Level 5)"}},
                 "Currency": {"names": {"d": "Divine Orb"}}}
        self.assertEqual(MP.gem_names(parts), {"Uhtred's Rite", "Uncut Skill Gem (Level 5)"})

    def test_lineage_gem_counted_without_a_stack_number(self):
        refs = self.refs()
        cells = [{"sig": None, "count": 1, "shown": False, "img": cell_of(self.lin)},
                 {"sig": None, "count": 1, "shown": False, "img": cell_of(self.gear)}]
        info = {}
        got, unknown = MP.identify(cells, {}, refs=refs, info=info)
        self.assertEqual((got, unknown, info["skipped"]), ({"Uhtred's Constellation": 1}, 0, 1))

    def test_uncut_gem_by_its_level(self):
        refs = self.refs()
        self.assertEqual(MP.gem_match(cell_of(self.uncut, "V"), refs), "Uncut Support Gem (Level 5)")
        self.assertIsNone(MP.gem_match(cell_of(self.uncut), refs), "no level read: not known")

    def test_never_a_non_gem_for_a_cell_with_no_number(self):
        refs = self.refs()
        self.assertIsNone(MP.gem_match(cell_of(art(23)), refs), "a Divine Orb's picture isn't a gem")

    def test_no_refs_still_skipped(self):
        info = {}
        got, unknown = MP.identify([{"sig": None, "count": 1, "shown": False, "img": object()}], {},
                                   refs=FV.Refs(), info=info)
        self.assertEqual((got, unknown, info["skipped"]), ({}, 0, 1))


class StashPictures(unittest.TestCase):
    """Scan stash's wildcard pictures (stashread.learned_icons) come after learned ones, before exchange icons."""

    def icon(self, pic):
        from soe2 import stashread as SR
        c = np.asarray(cell_of(pic))[:, :, ::-1].copy()
        return SR._icon(c, (0, 0, 70, 70))

    def test_names_an_item_nothing_else_knows(self):
        a, b = art(30), art(31)
        refs = FV.Refs()
        refs.stash = {"Vaal Cultivation Orb": self.icon(a), "Architect's Orb": self.icon(b)}
        self.assertEqual(MP.fv_match(cell_of(a), refs), "Vaal Cultivation Orb")
        self.assertIsNone(MP.fv_match(cell_of(art(32)), refs))

    def test_disagrees_with_an_exchange_icon_not_known(self):
        a = art(33)
        refs = FV.Refs()
        refs.add("Chance Shard", box(a), "exchange", "box")
        for i in range(12):                                         # (other exchange icons, far off)
            refs.add(f"Other {i}", box(art(40 + i)), "exchange", "box")
        self.assertEqual(MP.fv_match(cell_of(a), refs), "Chance Shard")
        refs.stash = {"Vaal Cultivation Orb": self.icon(a), "Architect's Orb": self.icon(art(34))}
        self.assertIsNone(MP.fv_match(cell_of(a), refs), "two pictures disagree: never a guess")

    def test_none_ship(self):
        # 3.1 (GGG ToS 7a): wildcard pictures are only those you named on this PC
        from soe2 import stashread as SR
        self.assertEqual(SR.learned_icons(), {})


class ExchangeIconChecks(unittest.TestCase):
    """An exchange icon alone names nothing when poe.ninja's art or the tint says another item."""

    def refs(self, a):
        refs = FV.Refs()
        refs.add("Omen of Light", box(a), "exchange", "box")
        for i in range(12):
            refs.add(f"Other {i}", box(art(60 + i)), "exchange", "box")
        return refs

    def test_art_of_another_item_far_closer(self):
        a = art(55)
        refs = self.refs(a)
        self.assertEqual(MP.fv_match(cell_of(a), refs), "Omen of Light")
        pics = {"Omen of Light": art(56), "Omen of Putrefaction": a}
        refs.art = art_only(pics).art
        self.assertIsNone(MP.fv_match(cell_of(a), refs), "its own art is far under another's: not known")

    def test_tint_far_off(self):
        a = art(57)
        refs = self.refs(a)
        with mock.patch.object(FV, "tint_gap", lambda *x: MP.EXCH_TINT_MAX + 7):
            self.assertIsNone(MP.fv_match(cell_of(a), refs))
        with mock.patch.object(FV, "tint_gap", lambda *x: 5.0):
            self.assertEqual(MP.fv_match(cell_of(a), refs), "Omen of Light")


class ArtDownloads(unittest.TestCase):
    def test_icons_pause_setting(self):
        from soe2.rates_view import Icons
        self.assertEqual(Icons.__init__.__code__.co_filename, Icons._work.__code__.co_filename)
        ic = Icons.__new__(Icons)
        Icons.__init__(ic, None, lambda: None)
        self.assertEqual(ic.gap, 0.0, "Exchange Rates keeps its pace")

    def test_map_profit_asks_once_for_missing_pictures_only(self):
        from soe2.mapprofit_page import MapProfitPage, ART_GAP
        from soe2 import rates_view
        asked = []

        class FakeIcons:
            def __init__(self, root, ready):
                self.gap = 0.0

            def get(self, u):
                asked.append((u, self.gap))

        parts = {"Currency": {"names": {"a": "Alpha", "b": "Beta"}, "images": {"a": "/a.png", "b": "/b.png"}}}
        page = MapProfitPage()
        page.root = object()
        from soe2 import gameart as GA
        from soe2.pricecheck_page import WAYSTONE_ICON
        with mock.patch.object(rates_view, "Icons", FakeIcons), \
                mock.patch("soe2.wealth.WPRICES", mock.Mock(parts=parts)), \
                mock.patch.object(GA, "cache_file", lambda u: "x" if u.endswith("/a.png") else None):
            page.mp_art_fetch()
            page.mp_art_fetch()
        self.assertEqual(asked, [("https://web.poecdn.com/b.png", ART_GAP), (WAYSTONE_ICON, ART_GAP)],
                         "every missing picture the readers compare with, once (the waystone too)")
        page.mp_refs_at = 5
        page._mp_art_ready()
        self.assertEqual(page.mp_refs_at, 0, "built again on the next Read Key press")


if __name__ == "__main__":
    unittest.main()


class LooseAndLetters(unittest.TestCase):
    def test_fragments_and_logbooks_are_loose(self):
        from soe2 import mapprofit as MP
        parts = {"Fragments": {"names": {"a": "Faded Crisis Fragment"}}, "Currency": {"names": {"b": "Chaos Orb"}}}
        got = MP.loose_names(parts)
        self.assertIn("Faded Crisis Fragment", got)
        self.assertIn("Expedition Logbook", got)
        self.assertNotIn("Chaos Orb", got)

    def test_letters_only_at_the_right_edge(self):
        import numpy as np
        from soe2 import mapprofit as MP
        img = np.zeros((70, 70, 3), np.uint8)
        img[49:63, 64:67] = 255                          # I at the right edge
        img[49:63, 58:61] = 255                          # I
        img[42:52, 25:35] = 255                          # a highlight, off the line, far left
        self.assertEqual(MP.tier_letters(img, white=True), "II")
