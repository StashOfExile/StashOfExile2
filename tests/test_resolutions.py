"""Screen readers at any resolution: real 2560x1440 game screenshots (/mnt/user-data/uploads/*.png, or the folder in
SOE2_SHOTS) are turned into simulated screens - the whole picture scaled (1920x1080, 3840x2160), and ultrawide (the
game keeps its height; UI anchored to the left edge stays left, UI anchored to the right edge stays right, the middle
is stretched with black: 3440x1440, 5120x1440; 2560x1080 = 1920x1080 then widened). Every reader must give the same
result as at 2560x1440. No 2560x1440 shots on this machine: the tests are skipped.

    python3.12 -m unittest tests.test_resolutions"""
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import cv2
    import numpy as np
    from PIL import Image
except Exception:           # pragma: no cover
    cv2 = None

SHOTS = os.environ.get("SOE2_SHOTS") or "/mnt/user-data/uploads"
_TMP = []


def setUpModule():          # (3.1: titles learned from the shots go to a throwaway data folder, never the real one)
    import tempfile
    from unittest import mock
    from soe2 import config
    d = tempfile.TemporaryDirectory()
    p = mock.patch.object(config, "DATA_DIR", d.name)
    p.start()
    _TMP.extend([d, p])


def tearDownModule():
    _TMP[1].stop()
    _TMP[0].cleanup()
SIZES = [(1920, 1080), (3840, 2160), (3440, 1440), (5120, 1440), (2560, 1080)]
_CACHE = {}


def shots():
    """{path: PIL RGB} of the exactly-2560x1440 pictures (cached)."""
    if "s" not in _CACHE:
        out = {}
        for f in sorted(glob.glob(os.path.join(SHOTS, "*.png"))):
            try:
                im = Image.open(f)
                if im.size == (2560, 1440):
                    out[f] = im.convert("RGB")
            except Exception:
                continue
        _CACHE["s"] = out
    return _CACHE["s"]


def widen(img, w, left=None, right=None):
    """Keep the height; make the picture w wide. The left `left` columns stay at the left edge, the right `right`
    columns at the right edge, the rest of the picture stays in the middle (black between) - as the game anchors its
    panels. Default: split in half (left half left, right half right)."""
    if w <= img.width:
        return img
    left = img.width // 2 if left is None else left
    right = img.width - left if right is None else right
    out = Image.new("RGB", (w, img.height))
    out.paste(img.crop((0, 0, left, img.height)), (0, 0))
    mid = img.crop((left, 0, img.width - right, img.height))
    out.paste(mid, ((w - mid.width) // 2, 0))
    out.paste(img.crop((img.width - right, 0, img.width, img.height)), (w - right, 0))
    return out


def simulate(img, size, board=False):
    """-> a PIL picture of the 2560x1440 one on a W x H screen. board=True: the Vaal Lens console (the middle 16:9)
    stays in the middle with only the side panels (card list, Medallions) at the edges."""
    w, h = size
    k = h / 1440.0
    base = img if h == 1440 else img.resize((round(2560 * k), h), Image.LANCZOS)
    if w <= base.width:
        return base.resize((w, h), Image.LANCZOS) if w != base.width else base
    if board:                                   # left strip 0-480, right strip 2080-2560 (frame units), middle between
        return widen(base, w, round(480 * k), round(480 * k))
    return widen(base, w)


def sized(name):
    return "%dx%d" % name


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if cv2 is None or not shots():
            raise unittest.SkipTest("no 2560x1440 game screenshots here (%s)" % SHOTS)


class Inventory(Base):
    """soe2/topup.py: banner, grid_rect, split, scan - game rect = (0, 0, W, H)."""

    @classmethod
    def read(cls, img):
        from soe2 import topup as T
        w, h = img.size
        g = (0, 0, w, h)
        op = T.is_open(img.crop(T.banner_rect(g)), h)
        gr = T.grid_rect(g)
        sc = T.scan(img.crop(gr), ocr=False) if op else []
        return op, gr, {r["cell"]: (r["count"], r["sure"], r["shown"], r["sig"]) for r in sc}

    def test_grid_same_at_every_size(self):
        from soe2 import topup as T
        found = 0
        for path, im in shots().items():
            op, gr, ref = self.read(im)
            if not op:
                continue
            found += 1
            self.assertTrue(len(ref) > 0, path)
            for size in SIZES:
                with self.subTest(shot=os.path.basename(path), size=sized(size)):
                    op2, gr2, got = self.read(simulate(im, size))
                    self.assertTrue(op2, "inventory title not found")
                    self.assertEqual(sorted(got), sorted(ref), "cells that hold something")
                    for c, v in ref.items():
                        self.assertEqual(got[c][:3], v[:3], f"count in cell {c}")
                        self.assertLess(T.dist(got[c][3], v[3]), T.SAME, f"picture of cell {c}")
        if not found:
            self.skipTest("no shot with the inventory open")

    def test_grid_is_anchored_right_and_scaled_by_height(self):
        from soe2 import topup as T
        a = T.grid_rect((0, 0, 2560, 1440))
        for w, h in SIZES:
            r = T.grid_rect((0, 0, w, h))
            k = h / 1440.0
            self.assertAlmostEqual((w - r[2]) / k, 2560 - a[2], delta=1.5, msg=sized((w, h)))
            self.assertAlmostEqual((r[2] - r[0]) / k, a[2] - a[0], delta=1.5)
            self.assertAlmostEqual(r[1] / k, a[1], delta=1.5)


class Favours(Base):
    """soe2/favours.py: title_template, find_window, grid_box, occupied (the window is anchored to the left)."""

    @classmethod
    def read(cls, img):
        from soe2 import favours as F
        w, h = img.size
        bgr = np.ascontiguousarray(np.asarray(img)[:, :, ::-1])
        win = F.find_window(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), F.title_template(), h, w)
        if win is None:
            return None, None, None
        grid = F.grid_box(win)
        return win, grid, F.occupied(bgr, grid)

    def test_window_same_at_every_size(self):
        found = 0
        for path, im in shots().items():
            win, grid, occ = self.read(im)
            if win is None:
                continue
            found += 1
            self.assertTrue(occ)
            for size in SIZES:
                with self.subTest(shot=os.path.basename(path), size=sized(size)):
                    k = size[1] / 1440.0
                    w2, g2, o2 = self.read(simulate(im, size))
                    self.assertIsNotNone(w2, "Favours title not found")
                    self.assertAlmostEqual(g2[0] / k, grid[0], delta=3)
                    self.assertAlmostEqual(g2[1] / k, grid[1], delta=3)
                    self.assertEqual(o2, occ, "cells that hold items")
        if not found:
            self.skipTest("no shot with the Favours window open")


class VaalLens(Base):
    """soe2/vaallens.py + medallions.py + temple.py: the board is read from the middle 16:9; the card list (left) and
    the Medallions panel (right) are cut from the window's edges; the console's count is in the bottom middle."""

    @classmethod
    def boards(cls):
        if "b" not in _CACHE:
            from soe2 import vaallens as V
            out = {}
            for p, im in shots().items():
                b = V.read(im)
                if V.seen(b):
                    out[p] = b
                    if len(out) >= 3:
                        break
            _CACHE["b"] = out
        return _CACHE["b"]

    def test_board_same_at_every_size(self):
        from soe2 import vaallens as V
        paths = list(self.boards())
        if not paths:
            self.skipTest("no shot with the Temple Console open")
        for path in paths:
            ref = self.boards()[path]
            for size in SIZES:
                with self.subTest(shot=os.path.basename(path), size=sized(size)):
                    got = V.read(V.frame(simulate(shots()[path], size, board=True)))
                    self.assertTrue(V.seen(got), "Atziri's tile not found")
                    diff = [c for c in V.CELLS if got[c]["kind"] != ref[c]["kind"]]
                    scaled = size[1] != 1440                         # (resampled: a tile or two may blur)
                    self.assertLessEqual(len(diff), 3 if scaled else 0, f"tiles read differently: {diff}")

    @staticmethod
    def like(a, b):
        """Two same-content pictures of different sizes -> mean gray difference (0-255) at the smaller one's size."""
        a, b = a.convert("L"), b.convert("L")
        b = b.resize(a.size, Image.LANCZOS)
        return float(np.abs(np.asarray(a, np.float32) - np.asarray(b, np.float32)).mean())

    def test_edge_panels_follow_their_edge(self):
        """The card list is cut at the left edge, the Medallions panel at the right edge, the console's count in the
        middle - what is cut at a size looks like what is cut at 2560x1440."""
        from soe2 import temple as TM, vaallens as V
        path = next(iter(self.boards()), None)
        if path is None:
            self.skipTest("no shot with the Temple Console open")
        im = shots()[path]
        g0 = (0, 0, 2560, 1440)
        boxes = {"cards": lambda g: V.card_box(g),
                 "medallions": lambda g: V.side_box(g, V.MEDAL_BOX, right=True),
                 "console": lambda g: TM.console_box(g)}
        for size in SIZES:
            sim = simulate(im, size, board=True)
            g = (0, 0) + size
            for name, fn in boxes.items():
                with self.subTest(box=name, size=sized(size)):
                    ref = im.crop(fn(g0))
                    got = sim.crop(fn(g))
                    k = size[1] / 1440.0
                    self.assertAlmostEqual(got.height / k, ref.height, delta=2)
                    if name == "medallions":        # (the panel itself: the right strip kept, the rest is the board)
                        n = round(480 * k)
                        ref, got = ref.crop((ref.width - 480, 0, ref.width, ref.height)), \
                            got.crop((got.width - n, 0, got.width, got.height))
                    self.assertLess(self.like(got, ref), 14, "the cut doesn't show the same part of the screen")

    def test_slots_scale_with_height(self):
        from soe2 import medallions as M
        a = M.slots((2000, 560, 2300, 600), 1.0)
        for w, h in SIZES:
            k = h / 1440.0
            head = (2000 * k, 560 * k, 2300 * k, 600 * k)
            for s, r in zip(a, M.slots(head, k)):
                for u, v in zip(s, r):
                    self.assertAlmostEqual(u * k, v, delta=2.5 * max(1, k))


class Stash(Base):
    """soe2/stashread.py: the panel is at the left edge; its size follows the game's height."""

    @classmethod
    def read(cls, img):
        from soe2 import stashread as S
        h = img.height
        bgr = np.ascontiguousarray(np.asarray(img)[:, :, ::-1])
        r = S.read_tab(bgr, h, "currency")
        spot = S.locate(bgr, h)
        return spot, r

    def test_currency_tab_same_at_every_size(self):
        from soe2 import stashread as S
        found = 0
        for path, im in shots().items():
            if S.locate(np.ascontiguousarray(np.asarray(im)[:, :, ::-1]), 1440, tabs=("currency",))["score"] < 0.2:
                continue                                            # (cheap look first: is a stash open at all)
            spot, ref = self.read(im)
            if spot["tab"] != "currency" or spot["score"] < 0.2 or not ref["ok"]:
                continue
            found += 1
            for size in SIZES:
                with self.subTest(shot=os.path.basename(path), size=sized(size)):
                    k = size[1] / 1440.0
                    sp2, got = self.read(simulate(im, size))
                    self.assertTrue(got["ok"], got["why"])
                    self.assertAlmostEqual(sp2["x"] / k, spot["x"], delta=4)
                    self.assertAlmostEqual(sp2["y"] / k, spot["y"], delta=4)
                    self.assertEqual(sorted(n for n, _q in got["items"]), sorted(n for n, _q in ref["items"]))
                    if size[1] == 1440:                              # (same pixels: same numbers)
                        self.assertEqual(sorted(got["items"]), sorted(ref["items"]))
                    else:       # a resampled picture (not the game's own sharp one at that size) may lose a digit
                        same = sum(1 for a, b in zip(sorted(got["items"]), sorted(ref["items"])) if a == b)
                        self.assertGreaterEqual(same, 0.85 * len(ref["items"]), "stack numbers read the same")
        if not found:
            self.skipTest("no shot with the Currency tab open")


class Rects(unittest.TestCase):
    """Boxes that need no picture: kept in units of the game's height, anchored to the edge the game anchors them to."""

    def test_boxes_are_in_game_heights(self):
        from soe2 import hover_page as HP, remnant as RM, temple as TM
        for w, h in SIZES:
            k = h / 1440.0
            with self.subTest(size=sized((w, h))):
                c = TM.console_box((0, 0, w, h))
                self.assertAlmostEqual((c[0] + c[2]) / 2, w / 2 + 0.0178 * h, delta=2)        # the game's middle
                self.assertAlmostEqual((c[2] - c[0]) / k, 0.16 * 1440, delta=3)
                self.assertAlmostEqual((c[3] - c[1]) / k, 0.036 * 1440, delta=2)
                hb = HP.region((w // 2, h // 2), (0, 0, w, h))
                self.assertAlmostEqual((hb[2] - hb[0]) / k, 2 * 0.444 * 1440, delta=3)         # a tooltip's reach
                r = RM.area_rect(RM.AREA, (0, 0, w, h))
                self.assertAlmostEqual(r[0] / k, RM.AREA[0] * 1440, delta=2)       # left edge, in heights
                self.assertAlmostEqual((r[2] - r[0]) / k, (RM.AREA[2] - RM.AREA[0]) * 1440, delta=2)


if __name__ == "__main__":
    unittest.main()
