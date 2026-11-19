"""3.0.6 Scan stash: the Socketables tab's five pages (soe2/stashlayouts.py). The layout checks need no picture; the
reads use real 2560x1440 shots of each page (/mnt/user-data/uploads, or the folder in SOE2_SHOTS) and are skipped
when a shot isn't on this machine. The counts below were checked by eye on each shot.

    python3.12 -m unittest tests.test_socketables"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import cv2  # noqa: F401
    import numpy as np
    from PIL import Image
except Exception:           # pragma: no cover
    np = None

SHOTS = os.environ.get("SOE2_SHOTS") or "/mnt/user-data/uploads"
# page -> (shot, {item: count read}, [items whose slot is empty there])
PAGES = {
    "socketables_runes": ("60dd83b0-image.png",
                          {"Lesser Desert Rune": 1, "Desert Rune": 1, "Greater Desert Rune": 31,
                           "Greater Storm Rune": 76, "Greater Iron Rune": 84, "Craiceann's Rune of Recovery": 13},
                          ["Lesser Iron Rune", "Charging Rune"]),
    "socketables_more": ("b29940b9-image.png",
                         {"Warding Rune of Reinforcement": 10, "Ancient Rune of Splinters": 12, "Rune of Acrobatics": 25,
                          "Ancient Rune of Witchcraft": 11, "Breath of Aldur": 5},
                         ["Warding Rune of Desperation", "Aldur's Legacy"]),
    "socketables_cores": ("1311cbf2-image.png",
                          {"Soul Core of Topotante": 7, "Soul Core of Tacati": 3, "Soul Core of Citaqualotl": 5,
                           "Tacati's Soul Core of Affliction": 1},
                          ["Soul Core of Zalatl", "Atziri's Soul Core of Devotion"]),
    "socketables_idols": ("6037de84-image.png",
                          {"Snake Idol": 52, "Cat Idol": 68, "Stag Idol": 47, "Idol of Eramir": 26,
                           "Idol of the Pharisee": 6},
                          []),
    "socketables_others": ("c652b0ad-image.png", {"Citaqualotl's Thesis": 1}, ["Amanamu's Gaze", "Carved Cunning"]),
}


class Layout(unittest.TestCase):
    def test_pages_in_the_scan(self):
        from soe2 import names as N, stashlayouts as L
        self.assertEqual(L.ORDER[-5:], L.SOCKETABLES)
        self.assertEqual(tuple(L.TABS[t]["page"] for t in L.SOCKETABLES), N.SOCKETABLES_PAGES)
        for t in L.SOCKETABLES:
            with self.subTest(page=t):
                self.assertTrue(N.title_case(L.TABS[t]["page"]))
                self.assertEqual(L.tab_title(t), "Socketables › " + L.TABS[t]["page"])
        self.assertEqual(L.tab_title("currency"), "Currency")

    def test_slots_fit_and_never_overlap(self):
        from soe2 import stashlayouts as L
        for t in L.SOCKETABLES:
            slots = L.TABS[t]["slots"]
            names = [n for n, _r in slots]
            with self.subTest(page=t):
                self.assertEqual(len(names), len(set(names)), "each item once")
                for _n, (x, y, w, h) in slots:
                    self.assertTrue(0 <= x and x + w <= L.PANEL and 0 <= y and y + h <= L.PANEL)
                for i, (_a, (x, y, w, h)) in enumerate(slots):
                    for _b, (u, v, s, q) in slots[i + 1:]:
                        self.assertFalse(x < u + s and u < x + w and y < v + q and v < y + h)


@unittest.skipIf(np is None, "needs OpenCV + numpy + Pillow")
class Reads(unittest.TestCase):
    @staticmethod
    def shot(name):
        p = os.path.join(SHOTS, name)
        if not os.path.exists(p):
            return None
        im = Image.open(p)
        if im.size != (2560, 1440):
            return None
        return np.ascontiguousarray(np.asarray(im.convert("RGB"))[:, :, ::-1])

    def test_each_page_found_and_read(self):
        from soe2 import stashread as S
        done = 0
        for tab, (fn, want, empty) in PAGES.items():
            bgr = self.shot(fn)
            if bgr is None:
                continue
            done += 1
            with self.subTest(page=tab):
                spot = S.locate(bgr, 1440)
                self.assertEqual(spot["tab"], tab)
                self.assertGreaterEqual(spot["score"], S.FOUND_SCORE)
                r = S.read_tab(bgr, 1440, tab)
                self.assertTrue(r["ok"], r["why"])
                got = dict(r["items"])
                for name, n in want.items():
                    self.assertEqual(got.get(name), n, name)
                for name in empty:
                    self.assertNotIn(name, got)
                self.assertEqual(r["unread"], [])
        if not done:
            self.skipTest("no Socketables shots on this machine")

    def test_wrong_page_says_which(self):
        from soe2 import stashread as S
        bgr = self.shot(PAGES["socketables_idols"][0])
        if bgr is None:
            self.skipTest("no Socketables shots on this machine")
        r = S.read_tab(bgr, 1440, "socketables_runes")
        self.assertFalse(r["ok"])
        self.assertEqual(r["seen"], "socketables_idols")
        self.assertIn("Socketables › Idols", r["why"])


if __name__ == "__main__":
    unittest.main()
