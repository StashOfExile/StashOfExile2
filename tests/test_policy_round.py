"""Owner decisions (GGG policy round, Nov 2026): what's gone stays gone, and what's left reads only on the Read Key.

  * Temple: no Vaal Beacon read, no crystals on the overlay, no Crystals full card - the Temple Console only.
  * Maps: Map Content is never read (no Ritual all-done tick, no Expedition mark); Ritual only prices Favours.
  * Map profit + Top Up Reminders: one Back from a map card; one press counts the map and checks the top ups.
  * Favours prices, Expedition prices, Island rumors: each a Read Key job, nothing else calls it.
  * Each helper's one line names the current Read Key; Settings › About has GGG's notice word for word.
  * The settings gear is drawn in the color it's given.

    python3.12 -m unittest discover -s tests        (or tests/runall.sh)"""
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import alerts_page as AP       # noqa: E402
from soe2 import remnant as RM           # noqa: E402
from soe2 import temple as TM            # noqa: E402
from soe2.hover_page import HoverPage    # noqa: E402
from soe2.topup_page import TopUpPage    # noqa: E402

NOTICE = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way."


def source(name):
    with open(os.path.join(ROOT, "soe2", name), encoding="utf-8") as f:
        return f.read()


class TempleConsoleOnly(unittest.TestCase):
    def test_no_beacon_read(self):
        for gone in ("fast_parse", "parse", "content_has", "content_box", "full", "region", "bar_text"):
            self.assertFalse(hasattr(TM, gone), f"temple.{gone} is gone (removed)")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "templates", "temple_content.png")))
        self.assertEqual(TM.parse_console([("18/60", (0, 0, 1, 1))]), (18, 60))
        self.assertEqual(TM.count_text({"have": 18, "most": 60, "old": False}), "Crystals 18/60 (3 runs)")

    def test_hover_job_reads_nothing_for_temple_in_maps(self):
        class App(HoverPage):
            def ritid_on(self):
                return False

            def temple_pad_on(self):
                return True                       # (the Temple Helper on, Vaal Lens on - but not in the temple)
        app = App()
        ctx = {"area": "map", "g": (0, 0, 1920, 1080), "ptr": (900, 500)}
        self.assertIsNone(app.hover_look_job(ctx), "a Read Key press in a map reads nothing for the Temple Helper")
        app.tm_in_temple = True
        self.assertEqual(app.hover_look_job(ctx)[0], "Vaal Lens", "in the temple: Vaal Lens' medallion names")

    def test_helpers_line_has_no_crystals(self):
        self.assertFalse(hasattr(AP.AlertsPage, "_temple_part"))
        self.assertIn("Temple Console", AP.HELPER_BLURBS["temple"])
        self.assertNotIn("Beacon", AP.HELPER_BLURBS["temple"])


class NoMapContent(unittest.TestCase):
    def test_ritual_reads_no_map_content(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "templates", "ritual_content.png")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "ritual_alert.py")), "the counter reader is gone")

    def test_expedition_mark_gone(self):
        for gone in ("has_marker", "marker_rect", "MARKER_B64"):
            self.assertFalse(hasattr(RM, gone), f"remnant.{gone} is gone (removed)")
        self.assertNotIn("rm_mark_check", source("rumours_page.py") + source("remnant_page.py"))


class BackFromAMap(unittest.TestCase):
    def app(self, tu=True, mp=True, key="Ctrl+Shift+R", counted=True):
        class App(TopUpPage):
            root = None

            def topup_on(self):
                return tu

            def mp_on(self):
                return mp

            def look_key_label(self):
                return key
        a = App()
        a.mp_pending = {"map": "Sun Temple"} if counted else None
        return a

    def test_owner_words(self):
        title, line = self.app().back_card_text("Sun Temple")       # Round 18: short - the title and one line
        self.assertEqual(f"{title}: {line}", "Back from Sun Temple: Open inventory, press Ctrl+Shift+R")
        self.assertNotIn("Stash", line, "the stash tip is on Map Profit's page line, not the card")

    def test_key_from_the_setting(self):
        self.assertEqual(self.app(key="F9").back_card_text("X")[1], "Open inventory, press F9")

    def test_one_helper_on(self):
        for a in (self.app(mp=False), self.app(tu=False)):
            self.assertEqual(a.back_card_text("X")[1], "Open inventory, press Ctrl+Shift+R")

    def test_uncounted_map_says_so(self):
        # 3.0.6 (owner: "it didn't update any information"): no read before the map - the card says why
        self.assertEqual(self.app(counted=False).back_card_text("X")[1],
                         "Not counted: no read before it. Open inventory, press Ctrl+Shift+R")

    def test_no_card(self):
        self.assertIsNone(self.app(tu=False, mp=False).back_card_text("X"))
        self.assertIsNone(self.app(key="").back_card_text("X"), "no Read Key: nothing to press")

    def test_one_card_no_buttons(self):
        a = self.app()
        shown = []

        class Row:
            def winfo_exists(self):
                return True

            def destroy(self):
                shown.append("closed")
        with mock.patch("soe2.alertcard.show", lambda *a_, **k: (shown.append((a_, k)), Row())[1]), \
                mock.patch("soe2.alerts_page.game_rect", lambda: (0, 0, 1920, 1080)):
            a.back_card("Sun Temple")
            a.back_card("Sun Temple")
            self.assertEqual(shown[1], "closed", "a second card replaces the first - never two")
            a.back_card_close()
        cards = [s for s in shown if s != "closed"]
        self.assertEqual(cards[0][0][1], "Back from Sun Temple")
        self.assertEqual(set(cards[0][1]) - {"color", "mark", "secs", "game", "tag", "rank"}, set(),
                         "an alert card: no buttons (a click closes it - not now)")
        self.assertEqual(getattr(a, "back_win", None), None)
        self.assertEqual(a.tu_visit, 2)

    def test_the_press_closes_it(self):
        self.assertIn("self.back_card_close()", source("topup_page.py").split("def topup_seen")[1].split("def ")[0])

    def test_map_profit_says_skipped_maps_have_no_entry(self):
        src = source("mapprofit_page.py")
        self.assertIn("A map you skip has no entry", src)


class LookKeyOnly(unittest.TestCase):
    JOBS = ("hover_look_job", "temple_console_job", "remnant_look_job", "favours_look_job",
            "ru_look_job", "ws_look_job", "topup_look_job")

    def test_each_job_is_called_only_from_the_look_key(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from check_removed import tokens                 # (names in the code - not comments or docstrings)
        names = {f: [t for k, t, _n in tokens(os.path.join(ROOT, "soe2", f))[0] if k == "name"]
                 for f in os.listdir(os.path.join(ROOT, "soe2")) if f.endswith(".py")}
        for job in self.JOBS:
            callers = [f for f, ns in names.items() if ns.count(job) > (1 if f"def {job}(" in source(f) else 0)]
            self.assertEqual(callers, ["look_page.py"], f"{job} is reached only from look_page.look_jobs")

    def test_no_timer_in_the_readers(self):
        for f in ("hover_page.py", "favours.py", "rumours.py", "temple.py"):
            s = source(f)
            self.assertNotRegex(s, r"\.after\(|after_idle|threading\.|Thread\(", f"{f}: nothing on a timer or thread")

    def test_no_tribute_reminder_left(self):
        for f in ("alerts_page.py", "favours_page.py", "ovquick.py", "features_page.py"):
            self.assertNotIn("Tribute reminder", source(f))


class LookKeyNamed(unittest.TestCase):
    def test_every_reading_helper_names_the_key(self):
        for k in AP.LOOK_HELPERS:
            self.assertIn("Ctrl+Shift+R", AP.helper_blurb(k, "your Read Key (Ctrl+Shift+R)"), k)
        for k in ("ritual", "remnant", "desecrate", "topup", "mapprofit", "temple"):
            self.assertIn(k, AP.LOOK_HELPERS)

    def test_look_key_text_default(self):
        from soe2.config import SETTINGS
        from soe2.look_page import LookPage
        SETTINGS.pop("look_key", None)
        self.assertEqual(LookPage().look_key_text(), "your Read Key (Ctrl+Shift+R)")
        SETTINGS["look_key"] = "F9"
        try:
            self.assertEqual(LookPage().look_key_text(), "your Read Key (F9)")
        finally:
            SETTINGS.pop("look_key", None)

    def test_about_notice_word_for_word(self):
        self.assertIn(f'"{NOTICE}"', source("about_page.py"))


@unittest.skipUnless(os.environ.get("DISPLAY") or sys.platform == "win32", "needs a display")
class Gear(unittest.TestCase):
    def test_drawn_in_its_color(self):
        import tkinter as tk
        from soe2 import gearicon as G
        root = tk.Tk()
        try:
            img = G.image(root, 32, "#e6e1d2")
            self.assertEqual((img.width(), img.height()), (32, 32))

            def clear(x, y):
                return bool(int(root.tk.call(str(img), "transparency", "get", x, y)))

            def rgb(x, y):
                return tuple(int(v) for v in root.tk.splitlist(root.tk.call(str(img), "get", x, y)))[:3]
            self.assertTrue(clear(0, 0), "transparent round the gear")
            self.assertTrue(clear(16, 16), "a hole in the middle")
            solid = [(x, y) for x in range(32) for y in range(32) if not clear(x, y)]
            self.assertTrue(solid)
            self.assertIn((230, 225, 210), {rgb(x, y) for x, y in solid}, "drawn in the color it's given")
            cv = tk.Canvas(root)
            item = G.draw(cv, 10, 10, 14, "#ffffff", anchor="e", tags=("mg", "mg_cog"))
            self.assertIn("mg_cog", cv.gettags(item))
        finally:
            root.destroy()

    def test_no_glyph_left_in_the_ui(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from check_removed import tokens
        for f in os.listdir(os.path.join(ROOT, "soe2")):
            if not f.endswith(".py") or f == "whatsnew.py":
                continue
            toks, _lines = tokens(os.path.join(ROOT, "soe2", f))
            for kind, text, n in toks:
                if kind == "str" and "⚙" in text:
                    self.fail(f"soe2/{f}:{n}: the ⚙ glyph in the UI")

class LookClear(unittest.TestCase):
    """Round 18: Esc in the game clears everything the Read Key drew over it; the game still gets Esc."""

    def test_esc_clears_everything(self):
        from soe2.readmark import ReadMarkPage
        done = []

        class Hide:
            def __init__(self, name):
                self.name = name

            def hide(self):
                done.append(self.name)

            def destroy(self):
                done.append(self.name)

        class App(ReadMarkPage):
            tm_marks_win, read_mark = Hide("vaal lens marks"), Hide("read mark")
        for fn in ReadMarkPage.LOOK_DRAWN:
            setattr(App, fn, lambda self, n=fn: done.append(n))
        App().ev_look_clear()
        self.assertEqual(set(done), set(ReadMarkPage.LOOK_DRAWN) | {"vaal lens marks", "read mark"})

    def test_esc_is_never_swallowed(self):
        from unittest import mock
        from soe2 import overlay as OV
        from soe2.utilities_page import UtilitiesPage
        q = []

        class App(UtilitiesPage):
            overlay = None

            class ui_q:
                put = staticmethod(q.append)
        with mock.patch.object(OV, "game_active", lambda *_a: True):
            self.assertFalse(App().look_esc_on_key(0x1B, False, False, False))
            self.assertFalse(App().look_esc_on_key(0x1B, True, False, False))      # (Ctrl+Esc: not ours)
        with mock.patch.object(OV, "game_active", lambda *_a: False):
            App().look_esc_on_key(0x1B, False, False, False)                       # (the app in front: not ours)
        self.assertEqual(q, [("look_clear",)])

    def test_read_mark_words(self):
        from soe2 import gamedata as GD
        from soe2.readmark import card_text
        self.assertEqual(card_text("screen", ["Ritual", "Temple", "Expedition"]), "Reading the screen")
        self.assertEqual(card_text("clipboard", ["nothing - " + GD.COPY_NOT_ITEM]), "Not an item")
        self.assertIsNone(card_text("clipboard", ["nothing - " + GD.COPY_MISSED]))
        self.assertEqual(card_text("clipboard", ["nothing - Rings: not priced - its base type isn't in the library."]),
                         "Can't price this item")


if __name__ == "__main__":
    unittest.main()
