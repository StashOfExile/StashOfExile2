"""The DPI fix (drawer build, owner-approved): the app's window thread keeps one DPI all run (drawer.pin_ui_dpi, ON),
and a Read Key press reads the game window, the mouse and its one picture in REAL pixels whatever that DPI is
(screenread.game_real / real_pixels), so the capture regions don't depend on Windows' scaling. Windows is mocked: a
fake user32 that virtualizes coordinates the way Windows does for a DPI-unaware thread (real / scale), keeps a DPI
context per thread, and - like mss on the first screen read - lets a capture switch the PROCESS to per-monitor.

    python3.12 -m unittest discover -s tests        (or tests/runall.sh)"""
import ctypes
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soe2 import screenread as SR        # noqa: E402
from soe2 import drawer as D             # noqa: E402
from soe2 import alerts_page as A        # noqa: E402
from soe2 import topup as TU             # noqa: E402
from soe2.hover_page import region       # noqa: E402
from soe2.look_page import LookPage      # noqa: E402

GAME = (0, 0, 2560, 1440)                # the game window in real pixels (a 2560 x 1440 screen)
MOUSE = (1700, 900)                      # the mouse in real pixels
SCALES = (1.0, 1.25, 1.5, 1.75)
REAL = (-4, -3, -2)                      # per-monitor v2 / v1 / system aware: coordinates are real pixels
HWND = 0x5EE


def _v(x):
    v = getattr(x, "value", x)
    if v is not None and v >= 2 ** 63:
        v -= 2 ** 64
    return v


class FakeUser32:
    """What Windows does with DPI, as far as these checks need it."""

    def __init__(self, scale):
        self.scale = scale
        self.process = -1                # the process starts DPI-unaware (python.exe's manifest says nothing)
        self.thread = {}                 # thread id -> its own DPI context (none: it follows the process)
        self.SetThreadDpiAwarenessContext = lambda ctx: self._set_thread(ctx)    # (a function: takes argtypes)

    # -- DPI contexts
    def now(self):
        return self.thread.get(threading.get_ident(), self.process)

    def _set_thread(self, ctx):
        old = self.now()
        self.thread[threading.get_ident()] = _v(ctx)
        return old

    def SetProcessDpiAwareness(self, level):          # (mss: on its first use, 2 = per-monitor)
        self.process = -4 if level == 2 else self.process

    def _px(self, v):
        return v if self.now() in REAL else int(round(v / self.scale))

    # -- the reads
    def FindWindowW(self, cls, title):
        return HWND if title == "Path of Exile 2" else 0

    def IsWindowVisible(self, h):
        return 1

    def GetWindowRect(self, h, ref):
        r = ref._obj
        r.left, r.top, r.right, r.bottom = (self._px(v) for v in GAME)
        return 1

    def GetCursorPos(self, ref):
        p = ref._obj
        p.x, p.y = (self._px(v) for v in MOUSE)
        return 1

    def app_game_rect(self, title="Path of Exile 2", dpi_hwnd=None):
        """alerts_page.game_rect as this thread sees it (the app's pixels when it is DPI-unaware)."""
        l_, t, r, b = (self._px(v) for v in GAME)
        return l_, t, r - l_, b - t


class Root:
    def __init__(self, u):
        self.u = u

    def winfo_pointerxy(self):
        return tuple(self.u._px(v) for v in MOUSE)


class Look(LookPage):
    """LookPage with two helpers that cut their part of the press's picture the way the app's do: Top Up's inventory
    (from the game window) and the hover read round the mouse (Ritual Identifier / Vaal Lens)."""

    def __init__(self, u):
        self.root = Root(u)
        self.boxes = []

    def look_jobs(self, ctx):
        g, ptr = ctx["g"], ctx["ptr"]

        def inv():
            self.boxes.append(("inventory", TU.grid_rect(g)))
            return SR.capture(TU.grid_rect(g), "Top Up")

        def hover():
            self.boxes.append(("hover", region(ptr, g)))
            return SR.capture(region(ptr, g), "Ritual Identifier")
        self.ctx = ctx
        return [("Top Up", inv, lambda _r: None), ("Ritual Identifier", hover, lambda _r: None)]

    def run_bg(self, work, done):
        done(work())

    def log_error(self, what):
        raise AssertionError(what)


def pinned(u):
    """drawer.pin_ui_dpi() on 'Windows' (the fake): this thread's DPI context, set before any window."""
    win = mock.MagicMock()
    win.user32 = u
    with mock.patch.object(D, "WIN", True), mock.patch.object(D, "UI_DPI", D.UI_DPI), \
            mock.patch.object(ctypes, "windll", win, create=True):
        return D.pin_ui_dpi()


class DpiPin(unittest.TestCase):
    def setUp(self):
        SR.reset()
        self.grabs = []
        SR.ONLY_KEY[0] = SR.LOGGER[0] = SR.SAID[0] = SR.AREA[0] = None
        SR.LOGGER[0] = lambda line: None

    def tearDown(self):
        SR.reset()
        SR.USER32[0] = SR.GRABBER[0] = SR.MAP[0] = SR.LOGGER[0] = None

    def press(self, u, real=True):
        """One Read Key press through the app's own path (look_page.ev_look) -> (the helpers' boxes, the picture's
        box, the press's ctx)."""
        from PIL import Image

        def grab(box):                                    # mss: switches the process, then takes the picture
            u.SetProcessDpiAwareness(2)
            self.grabs.append((box, u.now()))
            return Image.new("RGB", (box[2] - box[0], box[3] - box[1]))
        SR.USER32[0], SR.GRABBER[0] = (u if real else None), grab
        SR.release("Ctrl+Shift+R")
        self.assertTrue(SR.grant("Ctrl+Shift+R"))
        lk = Look(u)
        with mock.patch.object(A, "game_rect", u.app_game_rect):
            self.assertEqual(lk.ev_look(), ["Top Up", "Ritual Identifier"])
        return lk.boxes, self.grabs[-1][0], lk.ctx

    def test_pin_is_on(self):
        self.assertNotEqual(D.UI_DPI, "off", "pin_ui_dpi is switched on")
        u = FakeUser32(1.5)
        self.assertEqual(pinned(u), "gdiscaled")
        self.assertEqual(u.now(), -5, "the window thread: DPI-unaware, GDI-scaled")

    def test_capture_regions_same_at_every_scale(self):
        """With the pin on, the game window, the mouse, the picture and every helper's part of it are the same real
        pixels at 100 / 125 / 150 / 175 %."""
        seen = {}
        for s in SCALES:
            u = FakeUser32(s)
            pinned(u)
            boxes, pic, ctx = self.press(u)
            self.assertEqual(ctx["g"], GAME, f"{s}: the game window in real pixels")
            self.assertEqual(ctx["ptr"], MOUSE, f"{s}: the mouse in real pixels")
            self.assertEqual(pic, GAME, f"{s}: the one picture is the whole game window, real pixels")
            self.assertIn(self.grabs[-1][1], REAL, f"{s}: the picture taken in real pixels")
            seen[s] = (boxes, pic, ctx["rect"])
            # a helper's tag lands on the same spot of the game in the app's pixels
            self.assertEqual(SR.to_ui(ctx["rect"]), tuple(round(v / s) for v in GAME), f"{s}: to_ui")
            back = SR.to_screen(SR.to_ui(MOUSE))           # (one app pixel is up to 1.75 real ones: +-1)
            self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(back, MOUSE)), f"{s}: to_screen(to_ui(x)) {back}")
            self.assertEqual(u.now(), -5, f"{s}: the window thread is back to its own DPI after the reads")
        first = seen[SCALES[0]]
        for s in SCALES[1:]:
            self.assertEqual(seen[s], first, f"capture regions at {int(s * 100)} % = at 100 %")

    def test_ui_dpi_constant_across_first_capture(self):
        """The first screen read switches the process to per-monitor (mss): the pinned window thread keeps its DPI -
        the app's pixels (its windows' scale) are the same before and after."""
        u = FakeUser32(1.5)
        pinned(u)
        before = (u.now(), u.app_game_rect(), Root(u).winfo_pointerxy())
        self.press(u)
        self.assertEqual(u.process, -4, "the capture switched the process (as mss does)")
        self.assertEqual((u.now(), u.app_game_rect(), Root(u).winfo_pointerxy()), before,
                         "the UI's DPI and pixels didn't change after the first capture")
        boxes2, pic2, _ctx = self.press(u)                # a second press: the same regions
        self.assertEqual(pic2, GAME)

    def test_without_pin_first_capture_changes_ui(self):
        """(Why the pin: master's path - no pin, no real-pixel reads - the window thread follows the process, and the
        first capture changed its pixels.)"""
        u = FakeUser32(1.5)
        before = u.app_game_rect()
        self.press(u, real=False)
        self.assertNotEqual(u.app_game_rect(), before)

    def test_own_windows_masked_in_real_pixels(self):
        """Our own tags (placed in the app's pixels) are painted over in the press's picture (real pixels) where they
        really are - at 150 % a tag at app (100, 100)-(200, 120) covers real (150, 150)-(300, 180)."""
        from PIL import Image
        from soe2 import remnant as RM
        SR.set_map(GAME, (0, 0, round(2560 / 1.5), round(1440 / 1.5)))
        img = Image.new("RGB", (400, 400), (255, 255, 255))
        img.putpixel((290, 175), (0, 0, 0))               # inside the tag's real spot, outside its app-pixel spot
        with mock.patch.dict(RM.OWN, {"remnant": [(100, 100, 200, 120)]}):
            out = RM.mask_own(img, (0, 0))
        self.assertEqual(out.getpixel((290, 175)), (255, 255, 255))

    def test_not_windows(self):
        """No user32 (Linux, macOS): nothing changes - the app's own rect, nothing mapped."""
        SR.USER32[0] = None
        self.assertIsNone(SR.game_real())
        with SR.real_pixels() as ok:
            self.assertFalse(ok)
        SR.set_map(None, None)
        self.assertEqual(SR.to_ui((10, 20, 30, 40)), (10, 20, 30, 40))


if __name__ == "__main__":
    unittest.main()
