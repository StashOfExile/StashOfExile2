"""The overlay's lines over the XP bar (Round 18, owner bug: a black box beside the campaign line, even with the color
key set and read back): the Campaign / Ritual / NOW lines are drawn in their own small borderless window
(overlaywin.LinesWindow), centered over the bar with both ends clear - there is no see-through color round them, so
no black box. It moves, shows, hides and fades with the bar and takes its click-through and capture setting.
The see-through color itself (soe2/layered.py) stays for a boxless Style and the Vaal Lens marks: a fake user32
that, like the worst case on a real PC, drops a window's color key whenever its extended style is changed checks
that click-through, capture and opacity changes put it back.

    python3.12 -m unittest discover -s tests        (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import layered as L            # noqa: E402

KEY = "#010101"


class FakeUser32:
    """Windows' layered-window calls, as far as these checks need them. drops_key: a style change loses the color
    key (what the owner's PC showed). keeps_key=False: Windows never keeps one."""

    def __init__(self, drops_key=True, keeps_key=True):
        self.ex, self.cr, self.alpha, self.flags = 0, 0, 255, 0
        self.drops_key, self.keeps_key = drops_key, keeps_key
        self.calls = []

    def GetParent(self, wid):
        return 0xABC if wid == 42 else 0

    def GetWindowLongW(self, h, idx):
        return self.ex

    def SetWindowLongW(self, h, idx, val):
        self.calls.append(("style", val))
        if val != self.ex and self.drops_key:
            self.flags &= ~L.LWA_COLORKEY                # (the color key is gone - the black box)
        self.ex = val
        return 0

    def SetLayeredWindowAttributes(self, h, cr, alpha, flags):
        self.calls.append(("slwa", cr, alpha, flags))
        self.cr, self.alpha = cr, alpha
        self.flags = flags if self.keeps_key else flags & ~L.LWA_COLORKEY
        return 1

    def GetLayeredWindowAttributes(self, h, pcr, pa, pfl):
        pcr._obj.value, pa._obj.value, pfl._obj.value = self.cr, self.alpha, self.flags
        return 1

    def SetWindowDisplayAffinity(self, h, how):
        self.calls.append(("affinity", how))
        self.SetWindowLongW(h, -20, self.ex ^ 0x1000)    # (as if Windows touched the style too)
        return 1


class FakeWin:
    """A Tk window as layered.py sees it."""

    def __init__(self, key=KEY, alpha=0.88):
        self.attrs = {"-transparentcolor": key, "-alpha": alpha}
        self.after_calls = []

    def winfo_id(self):
        return 42

    def winfo_rgb(self, color):
        c = color.lstrip("#")
        return tuple(int(c[i:i + 2], 16) * 257 for i in (0, 2, 4))

    def attributes(self, name, value=None):
        if value is None:
            return self.attrs.get(name, "")
        self.attrs[name] = value

    def winfo_exists(self):
        return True

    def after(self, ms, fn):
        self.after_calls.append(ms)


class ColorKey(unittest.TestCase):
    def setUp(self):
        self.u = FakeUser32()
        self._was = L._U[0]
        L._U[0] = self.u
        self.plat = mock.patch.object(sys, "platform", "win32")
        self.plat.start()

    def tearDown(self):
        self.plat.stop()
        L._U[0] = self._was

    def key_in_force(self):
        return bool(self.u.flags & L.LWA_COLORKEY) and self.u.cr == 0x010101

    def test_click_through_on_reapplies_the_key(self):
        from soe2.merged_page import set_click_through
        w = FakeWin()
        self.assertTrue(set_click_through(w, True))
        self.assertTrue(self.u.ex & L.WS_EX_TRANSPARENT and self.u.ex & L.WS_EX_LAYERED)
        last = [c for c in self.u.calls if c[0] == "slwa"][-1]
        self.assertEqual(last, ("slwa", 0x010101, round(0.88 * 255), L.LWA_ALPHA | L.LWA_COLORKEY))
        self.assertTrue(self.key_in_force(), "the color key must be back after the style change")
        self.assertIs(L.holds(w), True)
        style_at = max(i for i, c in enumerate(self.u.calls) if c[0] == "style")
        slwa_at = max(i for i, c in enumerate(self.u.calls) if c[0] == "slwa")
        self.assertLess(style_at, slwa_at, "the key is set after the style, never before")

    def test_click_through_off_reapplies_the_key(self):
        from soe2.merged_page import set_click_through
        w = FakeWin()
        set_click_through(w, True)
        set_click_through(w, False)
        self.assertFalse(self.u.ex & L.WS_EX_TRANSPARENT)
        self.assertTrue(self.key_in_force())

    def test_no_key_keeps_opacity_only(self):
        w = FakeWin(key="")
        self.assertIs(L.apply(w, click_through=True), True)
        self.assertEqual(self.u.flags, L.LWA_ALPHA)
        self.assertIsNone(L.keep(w), "no see-through color: nothing to keep")

    def test_no_frame_yet_is_tried_again(self):
        from soe2.merged_page import set_click_through
        w = FakeWin()
        w.winfo_id = lambda: 7                                       # (GetParent -> 0: not on screen yet)
        self.assertTrue(set_click_through(w, True))
        self.assertEqual(w.after_calls, [50])

    def test_capture_affinity_reapplies_the_key(self):
        from soe2.remnant_page import capture_affinity
        w = FakeWin()
        L.apply(w)
        fake = mock.MagicMock()
        fake.user32 = self.u
        real = self.u.SetWindowDisplayAffinity
        self.u.GetParent = lambda wid: 0xABC                       # (plain functions: the caller sets argtypes on them)
        self.u.SetWindowDisplayAffinity = lambda h, how: real(h, how)
        with mock.patch("ctypes.windll", fake, create=True):
            capture_affinity(w, True)
        self.assertIn(("affinity", 0x11), self.u.calls)
        self.assertTrue(self.key_in_force(), "leaving the bar out of captures must not drop the color key")

    def test_new_opacity_keeps_the_key(self):
        from soe2.overlaywin import OverlayWindow
        w = FakeWin()
        L.apply(w)
        self.u.flags = 0                                             # (lost somewhere)
        OverlayWindow.set_opacity(w, 200)
        self.assertTrue(self.key_in_force())
        self.assertEqual(self.u.alpha, round(200 / 255 * 255))


def _tk():
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        return r
    except Exception:
        return None


class LinesWindowTest(unittest.TestCase):
    """The lines' own window over the bar (needs a display: skipped without one)."""

    def setUp(self):
        self.root = _tk()
        if self.root is None:
            self.skipTest("no display")
        from soe2.overlaywin import OverlayWindow
        self.main = OverlayWindow(self.root, "Session", "", (300, 900, 1200, 60), opacity=200, titlebar=False,
                                  resizable=False, follow_game=False, palette=None)
        self.main.update()

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()

    def pump(self):
        for _ in range(5):
            self.root.update()

    def test_centered_over_the_bar_without_a_color_key(self):
        from soe2.overlaywin import LinesWindow
        lw = LinesWindow(self.main, "#15130f", 216, 40)
        lw.follow()
        self.pump()
        self.assertEqual(lw.where(), (1200 - 2 * 216, 40, 300 + 216, 900 - 40))
        self.assertEqual(str(lw.attributes("-transparentcolor") or "") if sys.platform == "win32" else "", "")
        self.assertNotEqual(lw.state(), "withdrawn")
        self.assertIn(lw, self.main.companions)

    def test_moves_hides_and_fades_with_the_bar(self):
        from soe2.overlaywin import LinesWindow
        lw = LinesWindow(self.main, "#15130f", 100, 30)
        lw.follow()
        self.pump()
        self.main.geometry("+500+700")                     # dragged / a new spot
        self.pump()
        self.main._companions_follow()
        self.assertEqual(lw.where()[2:], (600, 670))
        self.assertEqual(lw.geometry().split("+")[1:], ["600", "670"])
        self.main.hide()                                  # the game not in front / the overlay off
        self.pump()
        self.assertEqual(lw.state(), "withdrawn")
        self.main.wanted = True
        self.main.sync(True)
        self.pump()
        self.assertNotEqual(lw.state(), "withdrawn")
        self.main.set_opacity(120)
        self.assertAlmostEqual(float(lw.attributes("-alpha")), float(self.main.attributes("-alpha")), places=2)
        lw.destroy()
        self.assertNotIn(lw, self.main.companions)

    def test_inset_needs_no_color_key(self):
        from soe2.ovparts import OverlayParts

        class Parts(OverlayParts):
            pass
        self.assertEqual(Parts()._gb_inset(self.main, 1600), int(1600 * OverlayParts.ENDS_CLEAR))
        self.assertEqual(Parts()._gb_inset(object(), 1600), 0, "a window that can't carry it: full width")

    def test_no_color_key_path_left(self):
        import soe2.ovparts as OP
        import soe2.overlaywin as OW
        for mod in (OP, OW):
            with open(mod.__file__, encoding="utf-8") as f:
                src = f.read()
            for gone in ("_gb_see_through", "_gb_key_lost", "on_key_lost", "key_check", "BROKEN"):
                self.assertNotIn(gone, src, f"{mod.__name__}: {gone}")


if __name__ == "__main__":
    unittest.main()
