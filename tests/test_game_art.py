"""3.1 (GGG ToS 7a - no redistributing game content): the app ships no game art. Pictures come at runtime from the
image links poe.ninja / the trade site send (web.poecdn.com), downloaded into the art cache on this PC; the screen
readers' references are built here from them (gameart.py), and the game's window titles are learned from the
player's own screen the first time OCR reads them.

The real-pixel checks use tests/fixtures/stash_stacks.png and waystone_cell.png (crops of real 1440p screens) against
pictures as web.poecdn.com serves them (tests/fixtures/art, 'downloaded' by artfixture.py). tests/ is never built."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import artfixture  # noqa: E402
from soe2 import favours as FV  # noqa: E402
from soe2 import gameart as GA  # noqa: E402
from soe2 import mapprofit as MP  # noqa: E402

_TMP = []
STACKS = os.path.join(HERE, "fixtures", "stash_stacks.png")


def setUpModule():
    from soe2 import config
    d = tempfile.TemporaryDirectory()
    p = mock.patch.object(config, "DATA_DIR", d.name)
    p.start()
    _TMP.extend([d, p])


def tearDownModule():
    _TMP[1].stop()
    _TMP[0].cleanup()


def slots():
    """The six real stash slots of stash_stacks.png (BGR, whole slots)."""
    img = cv2.imread(STACKS)
    return [img[6:76, i * 82 + 6:i * 82 + 76] for i in range(6)]


class NothingShips(unittest.TestCase):
    def test_no_templates_folder(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "templates")))

    def test_no_game_pictures_in_the_package(self):
        found = []
        for d, _sub, files in os.walk(os.path.join(ROOT, "soe2")):
            found += [os.path.join(d, f) for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".dds"))]
        self.assertEqual(found, [])

    def test_builds_bundle_no_templates(self):
        for f in ("build_exe.bat", "build_linux.sh", os.path.join(".github", "workflows", "release.yml")):
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                self.assertNotIn("templates", open(p, encoding="utf-8").read(), f)

    def test_check_tos_has_the_rule(self):
        src = open(os.path.join(ROOT, "tools", "check_tos.py"), encoding="utf-8").read()
        self.assertIn("game art", src)


class Drawn(unittest.TestCase):
    def test_art_on_the_cell_backing(self):
        art = np.zeros((64, 64, 4), np.uint8)
        art[16:48, 16:48] = (255, 255, 255, 255)
        cell = GA.drawn(art)
        self.assertEqual(cell.shape, (70, 70, 3))
        self.assertEqual(tuple(cell[2, 2]), GA.BACKING, "the clear parts show the cell's blue")
        self.assertEqual(tuple(cell[35, 35]), (255, 255, 255), "the art in the middle")
        self.assertIsNone(GA.drawn(None))

    def test_two_cells_wide(self):
        self.assertEqual(GA.drawn(np.full((47, 94, 4), 255, np.uint8), 140, 70).shape, (70, 140, 3))


class RealSlots(unittest.TestCase):
    """Real stash slots named by poe.ninja's pictures alone - nothing learned, nothing shipped."""

    WANT = ["Orb of Annulment", "Vaal Orb", None, "Divine Orb", "Scroll of Wisdom", "Lesser Jeweller's Orb"]

    def looks(self):
        items = FV.ninja_items(artfixture.parts())
        return GA.looks(items, FV.art_key, pic=lambda u: artfixture.picture(
            next(cid for p in artfixture.parts().values() for cid, path in p["images"].items()
                 if artfixture.url_of(path) == u)))

    def test_each_slot(self):
        lk = self.looks()
        self.assertEqual(len(lk), 10)
        got = []
        for s in slots():
            key, sc, lead = lk.best(s)
            got.append(key)
        # slot 3 (a Greater Jeweller's Orb, drawn bigger than the rest) is not sure here: not named - never a guess
        self.assertEqual(got, self.WANT)

    def test_scores(self):
        lk = self.looks()
        for s, want in zip(slots(), self.WANT):
            if want:
                top = lk.rank(s, 2)
                self.assertEqual(top[0][1], want)
                self.assertGreaterEqual(top[0][0], 0.84)
                self.assertGreaterEqual(top[0][0] - top[1][0], 0.2)

    def test_map_profit_names_them(self):
        """The whole matcher (Map Profit / Top Up / Scan stash wildcards): cache -> references -> name."""
        from soe2.config import P
        artfixture.download(P("art"))
        refs = MP.build_refs(artfixture.parts())
        self.assertEqual(len(refs.items), 0, "nothing learned")
        self.assertEqual(len(refs.looks), 10)
        want = list(self.WANT)
        want[2] = "Greater Jeweller's Orb"            # (the art cropped to itself names the bigger one)
        for s, w in zip(slots(), want):
            got = MP.fv_match(Image.fromarray(s[:, :, ::-1].copy()), refs)
            self.assertEqual(got, w)

    def test_nothing_downloaded_names_nothing(self):
        with mock.patch.object(GA, "cache_file", lambda u: None):
            refs = MP.build_refs(artfixture.parts())
        self.assertEqual(len(refs.looks), 0)
        self.assertIsNone(MP.fv_match(Image.fromarray(slots()[0][:, :, ::-1].copy()), refs))


def title_picture(word="INVENTORY", size=(600, 160), at=(180, 50), k=1.0):
    """A made-up title plate: dark letters on a light plate, on a dark frame."""
    w, h = int(size[0] * k), int(size[1] * k)
    im = Image.new("RGB", (w, h), (30, 25, 20))
    d = ImageDraw.Draw(im)
    x, y = int(at[0] * k), int(at[1] * k)
    d.rectangle((x - 20 * k, y - 10 * k, x + 260 * k, y + 50 * k), fill=(220, 200, 150))
    try:
        f = ImageFont.truetype("DejaVuSerif-Bold.ttf", int(30 * k))
    except OSError:
        f = ImageFont.load_default()
    d.text((x, y), word, font=f, fill=(25, 20, 15))
    return im, (x, y, int(x + 230 * k), int(y + 36 * k))


class LearnedTitles(unittest.TestCase):
    """The inventory's title: OCR finds it once, then that piece of the player's own screen is matched."""

    def setUp(self):
        GA.forget_screen_look("inventory_title")

    def test_ocr_once_then_matched(self):
        from soe2 import topup as TU
        im, box = title_picture()
        calls = []

        def ocr(pic):
            calls.append(pic.size)
            k = pic.width / im.width
            return [("INVENTORY", tuple(int(v * k) for v in box))]
        with mock.patch.object(GA, "OCR", [ocr]):
            self.assertEqual(TU.open_score(im, 1440), 1.0)
        self.assertEqual(len(calls), 1)
        self.assertIsNotNone(GA.screen_look("inventory_title"))
        with mock.patch.object(GA, "OCR", [lambda pic: 1 / 0]):          # (never asked again)
            self.assertGreater(TU.open_score(im, 1440), 0.95)
            im2, _b = title_picture(k=0.75)                                  # (1080p: the look scaled)
            self.assertGreater(TU.open_score(im2, 1080), 0.8)
            other, _b = title_picture("COSMETICS")
            self.assertLess(TU.open_score(other, 1440), TU.BANNER_MIN)

    def test_no_word_nothing_learned(self):
        from soe2 import topup as TU
        im, _box = title_picture("STASH")
        with mock.patch.object(GA, "OCR", [lambda pic: [("STASH", (0, 0, 10, 10))]]):
            self.assertEqual(TU.open_score(im, 1440), 0.0)
        self.assertIsNone(GA.screen_look("inventory_title"))

    def test_kept_only_on_this_pc(self):
        from soe2.config import P
        im, box = title_picture()
        GA.keep_screen_look("inventory_title", np.asarray(im.convert("L"))[box[1]:box[3], box[0]:box[2]], 1440)
        self.assertTrue(os.path.exists(P(GA.LOOKS_FILE)))


class FavoursGrid(unittest.TestCase):
    """The Favours grid placed from the OCR'd title, then by its own cell borders."""

    def picture(self, gx=410, gy=355):
        img = np.full((1440, 2560), 40, np.uint8)
        for c in range(FV.COLS + 1):
            img[gy:gy + FV.ROWS * 70, gx + c * 70] = 140
        for r in range(FV.ROWS + 1):
            img[gy + r * 70, gx:gx + FV.COLS * 70] = 140
        img[192:233, 760:894] = 200                                          # (the title's plate)
        return img

    def test_learn_then_match(self):
        GA.forget_screen_look(FV.TITLE_KEY)
        gray = self.picture()
        with mock.patch.object(GA, "OCR", [lambda pic: [("FAVOURS", (760 * pic.width // 1587, 192 * pic.width // 1587 + 3,
                                                                     894 * pic.width // 1587, 233 * pic.width // 1587))]]):
            win = FV.find_window(gray, "ocr", 1440, 2560)
        self.assertIsNotNone(win)
        gx, gy, cs = FV.grid_box(win)
        self.assertLessEqual(abs(gx - 410), 1)
        self.assertLessEqual(abs(gy - 355), 1)
        tpl = FV.title_template()
        self.assertIsInstance(tpl, np.ndarray, "learned")
        win2 = FV.find_window(gray, tpl, 1440, 2560)
        self.assertEqual(FV.grid_box(win2)[:2], (gx, gy))
        GA.forget_screen_look(FV.TITLE_KEY)


class LocalPictures(unittest.TestCase):
    """What the app SHOWS: poe.ninja's pictures from the art cache by name, else nothing (the name stands in)."""

    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_by_name(self):
        from soe2.config import P
        from soe2.rates_view import LocalIcons
        artfixture.install(art=False)
        li = LocalIcons(self.root, size=24)
        self.assertIn("Exalted Orb", li.names())
        self.assertTrue(li.has("exalted orb"))
        with mock.patch.object(GA, "cache_file", lambda u: None):
            self.assertIsNone(li.get("Exalted Orb"), "not downloaded yet: no picture")
        artfixture.download(P("art"))
        self.assertIsNotNone(li.get("Exalted Orb"))
        self.assertIsNone(li.get("Not In The Game"))


if __name__ == "__main__":
    unittest.main()
