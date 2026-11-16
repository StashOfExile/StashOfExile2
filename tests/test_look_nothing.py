"""The Look key with nothing to read (owner: "if it doesn't have anything to read it shouldn't give the alert"):
which helpers apply is decided BEFORE any picture - from where you are (the game's log), each helper's switch and what
it needs. None applies -> no picture, no read mark (👁 card), one line in the app's log. One applies -> one picture
and the card, as before (a read that happened is never hidden).

    python3.12 -m unittest tests.test_look_nothing          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-look-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import alerts_page as AP, screenread as SR       # noqa: E402
from soe2.config import SETTINGS                          # noqa: E402
from soe2.favours_page import FavoursPage                 # noqa: E402
from soe2.hover_page import HoverPage                     # noqa: E402
from soe2.look_page import LookPage                       # noqa: E402
from soe2.mapprofit_page import MapProfitPage             # noqa: E402
from soe2.remnant_page import RemnantPage                 # noqa: E402
from soe2.ritualid_page import RitualIdPage               # noqa: E402
from soe2.rumours_page import RumoursPage                 # noqa: E402
from soe2.sekhemas_page import SekhemasPage               # noqa: E402
from soe2.stashscan_page import StashScanPage             # noqa: E402
from soe2.temple_page import TemplePage                   # noqa: E402
from soe2.topup_page import TopUpPage                     # noqa: E402
from soe2.wellsouls_page import WellSoulsPage             # noqa: E402

GAME = (0, 0, 1920, 1080)
AREAS = ("map", "hideout", "town", "other", None)


class App(LookPage, AP.AlertsPage, HoverPage, TemplePage, RemnantPage, FavoursPage, RumoursPage, WellSoulsPage,
          TopUpPage, SekhemasPage, StashScanPage, RitualIdPage, MapProfitPage):
    """Every Look key helper of the app (look_page.look_jobs' list), without windows."""
    mm_sync = True

    def __init__(self):
        self.root = type("R", (), {"winfo_pointerxy": staticmethod(lambda: (900, 500))})()

    def log_error(self, where):
        raise AssertionError(where)

    def run_bg(self, work, done):
        return done(work())


def ctx(area):
    return {"g": GAME, "rect": (0, 0, 1920, 1080), "ptr": (900, 500), "area": area, "key": "Ctrl+Shift+R"}


class Base(unittest.TestCase):
    def setUp(self):
        SR.reset()
        self.shots, self.lines, self.said = [], [], []
        SR.GRABBER[0] = lambda box: (self.shots.append(box), Pic())[1]
        SR.AREA[0] = lambda: GAME
        SR.LOGGER[0] = self.lines.append
        SR.SAID[0] = lambda *a: self.said.append(a)
        SR.USER32[0] = None
        self.saved = {k: SETTINGS.get(k) for k in ("ritual_alert", "remnant", "topup", "map_profit", "temple",
                                                    "sekhemas", "desecrate")}

    def tearDown(self):
        SR.reset()
        SR.GRABBER[0] = SR.AREA[0] = SR.LOGGER[0] = SR.SAID[0] = None
        for k, v in self.saved.items():
            if v is None:
                SETTINGS.pop(k, None)
            else:
                SETTINGS[k] = v

    def all_off(self):
        for k in self.saved:
            SETTINGS[k] = {"on": False, "asked": True}

    def press(self, app):
        SR.release("Ctrl+Shift+R")
        self.assertTrue(SR.grant("Ctrl+Shift+R"))
        with mock.patch.object(AP, "game_rect", lambda *_a: GAME):
            return app.ev_look()


class Pic:
    def crop(self, b):
        return self

    def copy(self):
        return self


class NothingToRead(Base):
    def test_nothing_closes_the_press_without_a_read(self):
        self.assertTrue(SR.grant("F9", hold=0x78))
        self.assertIn("nothing to read here", SR.nothing("in a map: no helper applies"))
        self.assertEqual(self.shots, [], "no picture")
        self.assertEqual(self.said, [], "no read mark: nothing was read")
        self.assertEqual(self.lines, ["F9 pressed: nothing to read here (in a map: no helper applies) - the screen "
                                      "wasn't read"])
        self.assertIsNone(SR.capture((0, 0, 10, 10), "Ritual"), "the press is closed: no picture after it")
        self.assertEqual(self.shots, [])

    def test_a_read_that_happened_is_never_hidden(self):
        SR.release(0x78)
        self.assertTrue(SR.grant("F9", hold=0x78))
        SR.capture((0, 0, 10, 10), "Ritual")
        SR.nothing()                                      # (a picture was taken: the card says so all the same)
        self.assertEqual(len(self.shots), 1)
        self.assertEqual(self.said, [("screen", "F9", ["Ritual"])])
        self.assertEqual(self.lines, ["F9 pressed: read the screen once for Ritual"])

    def test_every_helper_off_in_a_map_no_picture_no_card(self):
        """The owner's case: Ctrl+Shift+R in a map where nothing applies - no capture, no 👁 card, a log line."""
        self.all_off()
        app = App()
        for area in AREAS:
            self.assertEqual(app.look_jobs(ctx(area)), [], f"every helper off: nothing applies ({area})")
        app.br_area = "map"
        self.assertEqual(self.press(app), [])
        self.assertEqual(self.shots, [], "nothing applies: the screen isn't read")
        self.assertEqual(self.said, [], "nothing applies: no read mark")
        self.assertEqual(len(self.lines), 1)
        self.assertIn("nothing to read here (in a map: no helper applies)", self.lines[0])

    def test_one_helper_applies_one_picture_and_the_card(self):
        self.all_off()
        SETTINGS["ritual_alert"] = {"on": True, "identify": False, "favours": False}
        app = App()
        app.br_area = "map"
        names = [n for n, _w, _d in app.look_jobs(ctx("map"))]
        self.assertEqual(names, ["Ritual"])
        with mock.patch("soe2.ritual_alert.look", lambda g, tribute=True: SR.capture((0, 0, 50, 50), "Ritual")
                        and {"kind": "none", "val": None, "tribute": None}), \
                mock.patch.object(App, "ritual_seen", lambda self: None, create=True):
            self.assertEqual(self.press(app), ["Ritual"])
        self.assertEqual(len(self.shots), 1, "one picture")
        self.assertEqual(self.said, [("screen", "Ctrl+Shift+R", ["Ritual", SR.NOTHING])],
                         "the card: a read happened (no counter seen: nothing found)")
        self.assertEqual(app.look_jobs(ctx("hideout")), [], "Ritual is for maps: not in your hideout")
        self.said.clear()
        with mock.patch("soe2.ritual_alert.look", lambda g, tribute=True: SR.capture((0, 0, 50, 50), "Ritual")
                        and {"kind": "ok", "val": (2, 5), "tribute": None}), \
                mock.patch.object(App, "ritual_seen", lambda self: None, create=True):
            self.assertEqual(self.press(app), ["Ritual"])
        self.assertEqual(self.said, [("screen", "Ctrl+Shift+R", ["Ritual"])], "the counter seen: a plain read")

    def test_a_helper_that_cannot_read_does_not_apply(self):
        self.all_off()
        SETTINGS["ritual_alert"] = {"on": True, "identify": False, "favours": True}
        app = App()
        with mock.patch("soe2.ritual_alert.template", lambda: None), \
                mock.patch("soe2.favours.title_template", lambda: None):
            self.assertEqual(app.look_jobs(ctx("map")), [], "no icon / title to look for: nothing to read")
            app.br_area = "map"
            self.assertEqual(self.press(app), [])
        self.assertEqual((self.shots, self.said), ([], []))


class NothingFound(Base):
    """A press whose picture no helper could use (owner: the trial map closed + the Look key): it was read, so the
    👁 card still shows - with honest words, "Read the screen · nothing here"."""

    def test_the_words(self):
        from soe2 import readmark as RMK
        self.assertEqual(RMK.card_text("screen", ["Trial of the Sekhemas"]), RMK.READING)
        self.assertEqual(RMK.card_text("screen", ["Trial of the Sekhemas", SR.NOTHING]), RMK.READ_NOTHING)
        self.assertEqual(RMK.READ_NOTHING, "Read the screen · nothing here")
        self.assertEqual(RMK.mark_text("screen", ["Ritual", SR.NOTHING]), "👁 Screen read once: Ritual - nothing found")

    def test_finish_says_so(self):
        SR.release(0x78)
        self.assertTrue(SR.grant("F9", hold=0x78))
        SR.capture((0, 0, 10, 10), "Trial of the Sekhemas")
        SR.finish(False)
        self.assertEqual(self.said, [("screen", "F9", ["Trial of the Sekhemas", SR.NOTHING])])
        self.assertEqual(self.lines, ["F9 pressed: read the screen once for Trial of the Sekhemas - nothing found"])

    def test_one_helper_found_something_is_enough(self):
        from soe2 import look_page as LP

        def none(_r):
            return None

        def some(_r):
            return [1]
        none.found = bool
        some.found = bool
        self.assertFalse(LP.found(none, None))
        self.assertTrue(LP.found(some, [1]))
        self.assertTrue(LP.found(lambda: 0, None), "a helper that can't say: counted as found (never a false "
                                                  "'nothing here')")

    def test_closed_trial_map(self):
        """The owner's case: in the trial, the map closed, the Look key -> one read, "nothing here" on the card."""
        self.all_off()
        SETTINGS["sekhemas"] = {"on": True}
        app = App()
        app.br_area = "other"
        app.sek_ocr = False
        app.sek_area("Sanctum_1_Foyer_1")
        with mock.patch("soe2.features.on", lambda *_a: True), \
                mock.patch("soe2.sekhemas.map_check", lambda *a, **k: {"open": False, "parts": 0, "of": 9, "seen": {}}), \
                mock.patch.object(App, "sek_hide", lambda self, cards=True: None):
            self.assertEqual(self.press(app), ["Trial of the Sekhemas"])
        self.assertEqual(len(self.shots), 1)
        self.assertEqual(self.said, [("screen", "Ctrl+Shift+R", ["Trial of the Sekhemas", SR.NOTHING])])


class WhereYouAre(Base):
    def test_start_up_area_until_the_next_change(self):
        app = App()
        app.br_area, app.br_area_start = None, "hideout"
        self.assertEqual(app.look_area(), "hideout", "after start-up: the log's last area, not 'anywhere'")
        app.br_area = "map"
        self.assertEqual(app.look_area(), "map")
        app.look_at_login = True
        self.assertEqual(app.look_area(), "login")

    def test_character_screen_reads_nothing(self):
        app = App()
        app.ss = {"armed": True, "busy": False, "i": 0}
        self.assertEqual(app.look_jobs(ctx("login")), [], "the character screen: nothing to read")
        app.ss = None
        app.look_at_login = True
        self.assertEqual(self.press(app), [])
        self.assertEqual((self.shots, self.said), ([], []))
        self.assertIn("at the character screen", self.lines[-1])

    def test_ritual_helpers_only_where_they_belong(self):
        """With the Ritual helpers on: maps (and the campaign for the counter) only - a hideout or town press reads
        nothing for them."""
        self.all_off()
        SETTINGS["ritual_alert"] = {"on": True}
        app = App()
        for area in ("hideout", "town"):
            self.assertEqual(app.look_jobs(ctx(area)), [], area)
        self.assertTrue(app.look_jobs(ctx("map")))


if __name__ == "__main__":
    unittest.main()
