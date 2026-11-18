"""The Ritual helper after the counter, the leave reminder and the Ritual Identifier were removed (3.0.6, owner: they
can't be automated, which defeats the purpose - GGG policy).

  * Overlay › Helpers: the Ritual row is Favours prices (one line, the Read Key in it) and Filter in the Ritual
    window - no counter, no reminder, no identifier, no On screen chip, no second Favours prices switch, no Test button
  * Filter in the Ritual window: one orange button in every state - Turn it on while it's off, Close once it's on;
    the steps only while it's off
  * old settings: the dead keys are cleared; Favours prices off turns the helper off
  * the hover read round the mouse (Vaal Lens) still finds a tooltip and reads it

    python3.12 -m unittest tests.test_ritual_helper          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-ritual-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
os.environ.setdefault("SOE2_NO_BOARD", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import alerts_page as AP                      # noqa: E402
from soe2 import migrations as MG                       # noqa: E402
from soe2.hover_page import find_tooltip, read_lines, region   # noqa: E402

GAME = (0, 0, 2560, 1440)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def texts(w, shown=False):
    """The words of every widget under w (shown=True: only those on screen now)."""
    out = []
    for x in walk(w):
        if shown and not x.winfo_ismapped():
            continue
        try:
            t = x.cget("text")
        except tk.TclError:
            continue
        if t:
            out.append(str(t))
    return out


class Words(unittest.TestCase):
    def test_the_ritual_helper_is_favours_prices(self):
        blurb = AP.HELPER_BLURBS["ritual"]
        self.assertIn(AP.LOOK, blurb, "it reads on the Read Key")
        self.assertIn("Favours", blurb)
        for gone in ("counter", "remind", "identif", "tribute"):
            self.assertNotIn(gone, blurb.lower())
        self.assertIn("ritual", AP.LOOK_HELPERS)
        self.assertEqual(AP.AlertsPage.HELPER_NAMES["ritual"], "Ritual")

    def test_no_ritual_alert_card(self):
        self.assertNotIn("ritual", AP.LEVELS)
        self.assertNotIn("ritual", AP.BANNER_SECS)
        for gone in ("alerts_ritual_leave_changed", "alerts_test_ritual", "ritual_readout", "ritual_look_job",
                     "ritual_estimate", "ritual_log"):
            self.assertFalse(hasattr(AP.AlertsPage, gone), gone)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "ritual_alert.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "ritualid.py")))

    def test_old_settings_cleared(self):
        S = {"ritual_alert": {"on": True, "sound": True, "leave_reminder": True, "readout": True, "identify": True,
                              "favours": True}}
        MG._ritual_only_favours_306(S)
        self.assertEqual(S["ritual_alert"], {"on": True})
        S = {"ritual_alert": {"on": True, "favours": False, "identify": False}}
        MG._ritual_only_favours_306(S)
        self.assertEqual(S["ritual_alert"], {"on": False}, "Favours prices off was the helper off")
        S = {"ritual_alert": {"on": False, "favours": True}}
        MG._ritual_only_favours_306(S)
        self.assertEqual(S["ritual_alert"], {"on": False})
        MG._ritual_only_favours_306({})                                    # (nothing saved: nothing to do)
        self.assertIn("ritual_only_favours_306", [s[0] for s in MG.STEPS])


class Hover(unittest.TestCase):
    """The tooltip find and read that Vaal Lens uses (it was shared with the Ritual Identifier)."""

    @staticmethod
    def shot(w=1280, h=640, tip=(420, 160, 900, 470)):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (w, h), (38, 34, 30))
        d = ImageDraw.Draw(im)
        for i in range(0, w, 37):
            d.line((i, (i * 7) % h, i + 9, (i * 7) % h + 4), fill=(70, 60, 50))
        x0, y0, x1, y1 = tip
        d.rectangle(tip, fill=(12, 10, 9))
        for k in range(4):
            d.rectangle((x0 + k, y0 + k, x1 - k, y1 - k), outline=(190, 160, 110))
        d.rectangle((x0 + 8, y0 + 46, x1 - 8, y0 + 49), fill=(190, 160, 110))
        return im

    def test_tooltip_found_and_read(self):
        im = self.shot()
        tip = find_tooltip(im, GAME[3])
        self.assertIsNotNone(tip)
        calls = []

        def ocr(img):
            calls.append(img.size)
            return [("Medallion", (0, 0, 10, 10))]
        lines = read_lines(im, GAME[3], ocr)
        self.assertEqual([t for t, _b in lines], ["Medallion"])
        self.assertEqual(len(calls), 1, "found in the tooltip: read once")

    def test_region_round_the_mouse(self):
        l_, t, r, b = region((1280, 900), GAME)
        self.assertTrue(l_ < 1280 < r and t < 900 < b)


class Panel(unittest.TestCase):
    """The real app's Overlay › Helpers row and the filter's dialog."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2.app import App
        cls.app = App(cls.root)
        cls.root.geometry("1500x1000+0+0")
        cls.box = tk.Frame(cls.root)
        cls.box.pack(fill="both", expand=True)
        cls.panel = cls.app.build_alerts_panel(cls.box)
        cls.panel.pack(fill="both", expand=True)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except tk.TclError:
            pass

    def row(self):
        for key, _group, words, ws in self.app.al_find:
            if key == "ritual":
                return words, ws
        self.fail("no Ritual row")

    def test_the_ritual_row(self):
        words, (_rl, _sw, cell, oc, tbt) = self.row()
        said = " ".join(texts(cell) + texts(oc)).lower()
        self.assertIn("favours window open", said)
        self.assertIn("filter in the ritual window", said)
        for gone in ("counter", "identifier", "on screen", "tribute", "rituals done", "not done"):
            self.assertNotIn(gone, said + " " + words)
        self.assertEqual(self.app.al_rows["ritual"]["chips"], [], "Favours prices is the helper itself: no 2nd switch")
        for name in ("Favours prices", "Ritual Identifier", "On screen"):
            self.assertNotIn(name, self.app.al_chips, name)
        self.assertFalse(isinstance(tbt, ttk.Button), "nothing to test: no Test button")

    def test_helpers_table_has_no_remind_column(self):
        said = [t for t in texts(self.app.al_table)]
        self.assertIn("Options", said)
        self.assertNotIn("Remind", said)
        self.assertNotIn("leave_reminder", self.app.breach_cfg())
        self.assertFalse(hasattr(self.app, "al_leave"))

    def test_breach_reminder_follows_the_helper(self):
        from unittest import mock
        cfg = self.app.breach_cfg()
        old = dict(cfg)
        seen = []
        try:
            with mock.patch.object(self.app, "breach_alert", lambda **k: seen.append(k.get("level"))), \
                    mock.patch.object(self.app, "fl_area", lambda *a: None), \
                    mock.patch.object(self.app, "mp_area", lambda *a: None), \
                    mock.patch.object(self.app, "back_card", lambda *a: None), \
                    mock.patch.object(self.app, "break_check", lambda *a, **k: None):
                for on, want in ((True, ["leave"]), (False, [])):
                    cfg.update(on=on, pending="almost")
                    seen.clear()
                    self.app.br_area, self.app.br_relog = "map", False
                    self.app.breach_area("hideout")
                    self.assertEqual(seen, want, f"helper on={on}")
        finally:
            cfg.clear()
            cfg.update(old)

    def test_breach_reminder_setting_dropped(self):
        S = {"breach_alert": {"on": True, "sound": True, "leave_reminder": False}}
        MG._breach_reminder_follows_helper(S)
        self.assertEqual(S["breach_alert"], {"on": True, "sound": True})
        MG._breach_reminder_follows_helper({})
        self.assertIn("breach_reminder_follows_helper", [s[0] for s in MG.STEPS])

    def test_favours_follows_the_helper(self):
        from soe2.config import SETTINGS
        old = SETTINGS.get("ritual_alert")
        try:
            SETTINGS["ritual_alert"] = {"on": False}
            self.assertFalse(self.app.favours_on())
            SETTINGS["ritual_alert"] = {"on": True}
            self.app.alerts_refresh()
            self.assertEqual(self.app.ritual_cfg(), {"on": True}, "one setting: on")
            self.assertFalse(hasattr(self.app, "favours_changed"))
        finally:
            if old is None:
                SETTINGS.pop("ritual_alert", None)
            else:
                SETTINGS["ritual_alert"] = old

    def primaries(self, dlg):
        return [str(w.cget("text")) for w in walk(dlg)
                if isinstance(w, ttk.Button) and str(w.cget("style")) == "Primary.TButton" and w.winfo_manager()]

    def dialog(self, state):
        with mock.patch("soe2.ritual_filter.state", lambda path=None: (state, os.path.join(HOME, "x.ini"))):
            dlg = self.app.ritual_filter_open()
            self.root.update()
        self.addCleanup(lambda: dlg.winfo_exists() and dlg.destroy())
        return dlg

    def test_filter_dialog_on(self):
        dlg = self.dialog("on")
        self.assertEqual(self.primaries(dlg), ["Close"], "on: nothing to do - Close is the one orange button")
        said = " ".join(texts(dlg, shown=True))
        self.assertIn("✓ On", said)
        self.assertNotIn("Turn it on", said)
        self.assertFalse(dlg.rf_steps.winfo_manager(), "the steps only while it's off")
        self.assertNotIn("Copy line", said)
        self.assertNotIn("Open folder", said)

    def test_filter_dialog_off(self):
        dlg = self.dialog("off")
        self.assertEqual(self.primaries(dlg), ["Turn it on"], "off: Turn it on is the one orange button")
        said = " ".join(texts(dlg, shown=True))
        self.assertIn("✗ Off", said)
        self.assertTrue(dlg.rf_steps.winfo_manager())
        for b in ("Open folder", "Copy line", "Check again", "Close"):
            self.assertIn(b, said)

    def test_filter_dialog_no_file(self):
        for st in ("nofile", "missing"):
            dlg = self.dialog(st)
            self.assertEqual(self.primaries(dlg), ["Close"], st)
            self.assertNotIn("Turn it on", " ".join(texts(dlg, shown=True)), st)

    def test_filter_dialog_follows_the_file(self):
        dlg = self.dialog("off")
        with mock.patch("soe2.ritual_filter.state", lambda path=None: ("on", os.path.join(HOME, "x.ini"))):
            dlg.rf_check()
            self.root.update()
        self.assertEqual(self.primaries(dlg), ["Close"], "after it's turned on: Close takes the orange")
        self.assertFalse(dlg.rf_steps.winfo_manager())


if __name__ == "__main__":
    unittest.main()
