"""Trial of the Sekhemas helper (BETA): the legend's lines, the trial map check against the owner's screenshots, the
game's log (floor, leaving), the legend's windows (Rooms, Boons, Afflictions; a click closes it), the hovered tooltip's card - and that nothing reads without a Look key press.

    python3.12 -m unittest tests.test_sekhemas        (or tests/runall.sh)"""
import os
import re
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image                     # noqa: E402

from soe2 import gamelog as GL            # noqa: E402
from soe2 import screenread as SR         # noqa: E402
from soe2 import sekhemas as SK           # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def shot(name):
    """The owner's 2560 x 1440 screenshots, kept at 1280 x 720 (JPEG)."""
    return Image.open(os.path.join(FIX, name)).convert("RGB")


def shifted(img, dx, dy):
    out = Image.new("RGB", img.size)
    out.paste(img, (dx, dy))
    return out


def ultrawide(img):
    w, h = img.size
    out = Image.new("RGB", (int(h * 43 / 18), h), (18, 18, 18))
    out.paste(img, ((out.width - w) // 2, 0))
    return out


def map_closed(img):
    """The same scene with the map window gone: the game world (from the left of the shot) where it was."""
    out = img.copy()
    w, h = out.size
    world = img.crop((0, int(h * 0.2), int(w * 0.21), int(h * 0.62)))
    for x in range(int(w * 0.2), int(w * 0.82), world.width):
        for y in range(0, h, world.height):
            out.paste(world, (x, y))
    return out


def source(name):
    with open(os.path.join(ROOT, "soe2", name), encoding="utf-8") as f:
        return f.read()


class Legend(unittest.TestCase):
    """Owner: three groups - Rooms, Boons, Afflictions - each with what to take and what to avoid."""

    def names(self, group, verdict):
        return [n for v, rows in SK.legend(group) if v == verdict for _m, n, _l in rows]

    def test_three_groups_both_sides(self):
        self.assertEqual(set(SK.GROUP_WORD), {SK.ROOMS, SK.BOONS, SK.AFFLICTIONS})
        self.assertEqual([SK.GROUP_WORD[g] for g in (SK.ROOMS, SK.BOONS, SK.AFFLICTIONS)],
                         ["Rooms", "Boons", "Afflictions"])
        shown = [g for side in (SK.LEFT, SK.RIGHT) for g in SK.SIDES[side]]
        self.assertEqual(sorted(shown), sorted(SK.GROUP_WORD))                  # each group once
        n = {side: sum(len(rows) for _g, blocks in SK.side_groups(side) for _v, rows in blocks)
             for side in (SK.LEFT, SK.RIGHT)}
        self.assertLessEqual(abs(n[SK.LEFT] - n[SK.RIGHT]), 3, n)               # balanced
        self.assertEqual(len({SK.GROUP_COLOR[g] for g in SK.GROUP_WORD}), 3)

    def test_rooms_take_and_avoid(self):
        self.assertEqual(self.names(SK.ROOMS, SK.TAKE)[:3], ["Fountain", "Honour shrine", "Keys"])
        self.assertEqual(self.names(SK.ROOMS, SK.AVOID), ["Gauntlet"])

    def test_afflictions_worst_first(self):
        bad = self.names(SK.AFFLICTIONS, SK.AVOID)
        affl = {e["name"]: e for e in SK.data()["afflictions"]}
        for n in ("Ghastly Scythe", "Branded Balbalakh", "Orb of Negation", "Corrosive Concoction"):
            self.assertIn(n, bad)
            self.assertEqual(affl[n]["rating"], "run-ending")
        for n in bad:
            self.assertIn(affl[n]["rating"], ("run-ending", "bad"), n)
        for n in self.names(SK.AFFLICTIONS, SK.MILD):
            self.assertEqual(affl[n]["rating"], "minor", n)                     # (the hover card's "Mild" too)

    def test_boons_best(self):
        boons = {e["name"]: e for e in SK.data()["boons"]}
        take = self.names(SK.BOONS, SK.TAKE)
        self.assertIn("Sekhema's Cloak", take)
        for n in take:
            self.assertEqual(boons[n]["rating"], "great", n)

    def test_marks_words_short_lines(self):
        for g in SK.GROUP_WORD:
            for verdict, rows in SK.legend(g):
                self.assertTrue(SK.WORD[verdict])                               # never color alone: a word ...
                self.assertTrue(rows)
                self.assertLessEqual(len(rows), SK.MAX_LINES)
                for mark, name, line in rows:
                    self.assertEqual(mark, SK.MARK[verdict])                    # ... and a mark on every line
                    self.assertLessEqual(len(name) + len(line), 50, line)
        self.assertEqual(len(set(SK.MARK.values())), len(SK.MARK))
        self.assertEqual(sum(len(r) for _v, r in SK.legend(SK.AFFLICTIONS, most=2)), 4)

    def test_text_rules(self):
        words = " ".join(r["line"] for s in SK.data()["legend"].values() for r in s) + " " + \
            " ".join(e["why"] for k in ("afflictions", "boons") for e in SK.data()[k])
        self.assertNotRegex(words.lower(), r"\bcalm|defence|colour|behaviour|\bgrey\b")
        self.assertEqual(len(SK.data()["afflictions"]), 47)
        self.assertEqual(len(SK.data()["boons"]), 38)


class MapOpen(unittest.TestCase):
    def assertOpen(self, img, want=True, **kw):
        got = SK.map_check(img, **kw)
        self.assertEqual(got["open"], want, got)
        return got

    def test_owner_screenshots(self):
        for name in ("sekhemas_map_a.jpg", "sekhemas_map_b.jpg"):
            got = self.assertOpen(shot(name))
            self.assertEqual(got["parts"], got["of"])

    def test_any_resolution(self):
        a = shot("sekhemas_map_a.jpg")
        for img in (a.resize((2560, 1440)), a.resize((1920, 1080)), ultrawide(a), ultrawide(a.resize((1920, 1080)))):
            self.assertOpen(img)

    def test_windowed_game_border(self):
        """The game window's own border and title bar move the picture a little: still found."""
        self.assertOpen(shifted(shot("sekhemas_map_a.jpg").resize((2560, 1440)), 8, 31))
        self.assertOpen(shifted(shot("sekhemas_map_b.jpg"), 4, 16))

    def test_not_the_map(self):
        self.assertOpen(shot("sekhemas_not_map.jpg"), False)           # another game window (the Temple Console)
        self.assertOpen(map_closed(shot("sekhemas_map_a.jpg")), False)  # the same scene, map closed
        self.assertOpen(map_closed(shot("sekhemas_map_b.jpg")).resize((1920, 1080)), False)
        self.assertOpen(Image.new("RGB", (1920, 1080), (30, 30, 30)), False)
        self.assertFalse(SK.map_check(None)["open"])

    def test_our_own_windows_skipped(self):
        """A part under our own legend isn't asked for - the rest still find the map."""
        a = shot("sekhemas_map_a.jpg")
        w, h = a.size
        left = (0, 0, int(w / 2 - 0.40 * h), h)                         # over both left knobs and the arch
        got = self.assertOpen(a, skip=[left])
        self.assertEqual(got["of"], 6)
        self.assertOpen(map_closed(a), False, skip=[left])


class TrialLog(unittest.TestCase):
    def test_floor_of(self):
        self.assertEqual(SK.floor_of("Sanctum_2_Foyer_1"), 2)
        self.assertEqual(SK.floor_of("Sanctum_4_Boss"), 4)
        self.assertEqual(SK.floor_of("Sanctum_Final"), 0)
        self.assertIsNone(SK.floor_of("MapSunTemple"))
        self.assertIsNone(SK.floor_of("G2_13"))
        self.assertIsNone(SK.floor_of(None))

    def test_floor_only(self):
        """Owner: the key count missed keys (it counted from app start) and the game shows them by the map - gone."""
        t = SK.Trial()
        self.assertEqual(t.text(), "")
        self.assertFalse(t.area("Sanctum_1_Foyer_1"))
        self.assertEqual(t.text(), "Floor 1 of 4")
        t.area("Sanctum_2_Foyer_3")
        self.assertEqual(t.text(), "Floor 2 of 4")
        t.area("Sanctum_Final")                                          # (no floor in its name: kept)
        self.assertEqual(t.floor, 2)
        self.assertTrue(t.area("G2_13"))                                 # left the trial
        self.assertFalse(t.inside)
        self.assertFalse(hasattr(t, "keys"), "the key count is gone")
        self.assertFalse(hasattr(SK, "KEY_KINDS"))

    def test_log_lines(self):
        pre = "2026/11/15 17:58:02 123456 abcdef [INFO Client 18220] "
        self.assertFalse(hasattr(GL, "SANCTUM_KEY"), "keys aren't followed in the log any more")
        self.assertNotEqual((GL.parse(pre + ": Collected a Silver Key") or (None,))[0], "sanctum")
        a = GL.parse("2026/11/15 17:58:02 123456 abcdef [DEBUG Client 18220] Generating level 80 area "
                     "\"Sanctum_1_Foyer_1\" with seed 4242")
        self.assertEqual((a[0], a[2]["area"]), ("area", "Sanctum_1_Foyer_1"))
        b = GL.parse(pre + "Balbala, the Advisor: An oasis in the desert.")
        self.assertEqual(b[0], "say")                                    # (dialogue - not a trial event)


class Hover(unittest.TestCase):
    def test_names_in_a_tooltip(self):
        lines = [("Room: Gauntlet", None), ("Ghastly Scythe", None), ("Losing any Honour ends the Trial", None),
                 ("Hare Foot", None), ("Relic Effects:", None)]
        got = SK.hover_names(lines)
        self.assertEqual([e["name"] for _k, e in got], ["Ghastly Scythe", "Hare Foot"])
        kind, e = got[0]
        mark, word, why, vital = SK.verdict(kind, e)
        self.assertEqual((mark, word, vital), ("✕", "Bad", True))
        self.assertTrue(why)
        self.assertEqual(SK.verdict(*got[1])[1], "Good")
        self.assertEqual(SK.hover_names([("44% increased Armour, Evasion and Energy Shield", None),
                                         ("+21% to Honour Resistance", None)]), [])

    def test_ocr_slips(self):
        got = SK.hover_names([("Sekhema’s Cloak", None), ("Garukhans Favour", None)])
        self.assertEqual([e["name"] for _k, e in got], ["Sekhema's Cloak", "Garukhan's Favour"])

    def test_words(self):
        mild = next(e for e in SK.data()["afflictions"] if e["rating"] == "minor")
        weak = next(e for e in SK.data()["boons"] if e["rating"] == "meh")
        self.assertEqual(SK.verdict("affliction", mild)[:2], ("!", "Mild"))
        self.assertEqual(SK.verdict("boon", weak)[:2], ("–", "Weak"))


class Placing(unittest.TestCase):
    def test_beside_the_map(self):
        for game in ((0, 0, 2560, 1440), (0, 0, 1920, 1080), (100, 50, 3440, 1440)):
            gx, gy, gw, gh = game
            cx = gx + gw / 2
            c = SK.columns(game)
            ax, aw = c[SK.LEFT]
            tx, tw = c[SK.RIGHT]
            self.assertGreaterEqual(ax, gx)
            self.assertLessEqual(ax + aw, cx - SK.MAP_HALF * gh)          # left of the map window
            self.assertGreaterEqual(tx, cx + SK.MAP_HALF * gh)             # right of it
            self.assertLessEqual(tx + tw, gx + gw)
            self.assertGreaterEqual(aw, SK.NARROW * gh)

    def test_narrow_screen(self):
        c = SK.columns((0, 0, 1440, 1080))                                 # 4:3 - no room beside: on its edges
        self.assertEqual(c[SK.LEFT][0], int(SK.GAP * 1080))
        self.assertGreaterEqual(c[SK.LEFT][1], SK.NARROW * 1080)

    def test_off_the_overlay(self):
        game = (0, 0, 2560, 1440)
        y0 = SK.place_y(game, 30, 470, 300)
        self.assertEqual(y0, int(SK.MIDDLE * 1440 - 150))                  # round the map's middle
        self.assertEqual(SK.top_of(game, 1000), int(SK.TOP * 1440))        # ... never above TOP
        panel = (0, 400, 600, 700)                                         # the overlay's Panel, dragged there
        y = SK.place_y(game, 30, 470, 300, [panel])
        self.assertGreaterEqual(y, panel[3])
        low = (0, 400, 600, 1300)                                          # no room below it: above
        y = SK.place_y(game, 30, 470, 300, [low])
        self.assertLessEqual(y + 300, low[1])
        self.assertEqual(SK.place_y(game, 2000, 470, 300, [panel]), y0)     # (the other side: not in the way)


def tk_root():
    import tkinter as tk
    try:
        r = tk.Tk()
    except tk.TclError:
        return None
    r.withdraw()
    return r


class Panels(unittest.TestCase):
    """The real legend windows: both sides beside the map, nothing over it, every line marked, a click anywhere on
    one closes the legend (no Close button)."""

    @classmethod
    def setUpClass(cls):
        cls.root = tk_root()
        if cls.root is None:
            raise unittest.SkipTest("no display")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def app(self):
        from soe2.sekhemas_page import SekhemasPage

        class App(SekhemasPage):
            pass
        a = App()
        a.root = self.root
        a.sek_area("Sanctum_1_Foyer_1")
        return a

    def words(self, w):
        import tkinter as tk
        out = []
        if isinstance(w, tk.Label):
            out.append(w.cget("text"))
        elif isinstance(w, tk.Text):
            out.append(w.get("1.0", "end"))
        for ch in w.winfo_children():
            out += self.words(ch)
        return out

    def test_beside_the_map_and_readable(self):
        for game in ((0, 0, 2560, 1440), (0, 0, 1920, 1080)):
            a = self.app()
            wins = a.sek_show(game)
            self.root.update()
            gx, gy, gw, gh = game
            cx = gw / 2
            left, right = wins
            self.assertLessEqual(left.x + left.w, cx - SK.MAP_HALF * gh)      # nothing over the map window
            self.assertGreaterEqual(right.x, cx + SK.MAP_HALF * gh)
            self.assertEqual(left.y, right.y)                                 # tops level
            for p in wins:
                self.assertGreaterEqual(p.y, SK.TOP * gh)
                self.assertLessEqual(p.y + p.h, 0.72 * gh, game)              # above the life / mana numbers
                self.assertGreaterEqual(-p.fonts["name"].cget("size"), 13)   # readable at 1080p
            text = " ".join(self.words(left.win))
            self.assertIn("Afflictions", text)
            self.assertIn("✕\tGhastly Scythe", text)
            self.assertIn("Floor 1 of 4 · Click to close", text)
            self.assertNotIn("keys", text.lower())
            right_text = " ".join(self.words(right.win))
            for word in ("Rooms", "Boons", "✓\tFountain", "✕\tGauntlet"):
                self.assertIn(word, right_text)
            self.assertNotIn("Close\n", "".join(self.words(left.win) + self.words(right.win)))
            a.sek_hide()

    def test_a_click_anywhere_closes_it(self):
        a = self.app()
        wins = a.sek_show((0, 0, 2560, 1440))
        self.root.update()
        self.assertTrue(all(getattr(p.win, "click_closes", False) for p in wins))
        self.assertEqual(len(wins[0].win.winfo_children()), 1)               # (the card only: no Close window)
        inner = wins[1].texts[0]
        inner.event_generate("<Button-1>", x=5, y=5)                       # a line on the right side
        self.root.update()
        self.assertFalse(a.sek_shown())
        self.assertFalse(any(p.win.winfo_exists() for p in wins))           # both sides went


class LookKeyOnly(unittest.TestCase):
    """Nothing reads the screen without a Look key press: the job only cuts from the press's one picture."""

    def setUp(self):
        SR.reset()
        self.shots = []
        self.pic = shot("sekhemas_map_a.jpg")
        SR.GRABBER[0] = lambda box: (self.shots.append(box), self.pic)[1]
        SR.AREA[0] = lambda: (0, 0, 1280, 720)
        SR.LOGGER[0] = lambda line: None
        SR.SAID[0] = None
        SR.ONLY_KEY[0] = None

    def tearDown(self):
        SR.reset()
        SR.GRABBER[0] = SR.AREA[0] = SR.LOGGER[0] = None

    def app(self):
        from soe2.sekhemas_page import SekhemasPage

        class App(SekhemasPage):
            shown = 0

            def look_status(self, line):
                return line

            def look_key_text(self):
                return "your Look key (Ctrl+Shift+R)"

            def sek_show(self, game=None):
                App.shown += 1

            def sek_hide(self, cards=True):
                App.shown = 0
        a = App()
        a.sek_ocr = False
        return a

    def ctx(self):
        return {"g": (0, 0, 1280, 720), "rect": (0, 0, 1280, 720), "ptr": (640, 360), "area": "map", "key": "F9"}

    def test_only_in_the_trial(self):
        a = self.app()
        self.assertIsNone(a.sekhemas_look_job(self.ctx()))                 # not in a trial: no job, no picture
        a.sek_area("Sanctum_1_Foyer_1")
        self.assertIsNotNone(a.sekhemas_look_job(self.ctx()))
        from soe2.config import SETTINGS
        SETTINGS.setdefault("sekhemas", {})["on"] = False
        try:
            self.assertIsNone(a.sekhemas_look_job(self.ctx()))             # switched off: nothing
        finally:
            SETTINGS["sekhemas"]["on"] = True
        self.assertEqual(self.shots, [])

    def test_no_press_no_read(self):
        a = self.app()
        a.sek_area("Sanctum_1_Foyer_1")
        name, work, done = a.sekhemas_look_job(self.ctx())
        self.assertEqual(name, "Trial of the Sekhemas")
        self.assertIsNone(work())                                          # no press: nothing
        self.assertEqual(self.shots, [])
        self.assertTrue(SR.grant("F9", hold=0x78))
        res = work()
        self.assertTrue(res[0]["open"])
        self.assertTrue(work.found(res))
        self.assertEqual(len(self.shots), 1)                               # one press: one picture
        done(res)
        self.assertEqual(type(a).shown, 1)
        work()
        self.assertEqual(len(self.shots), 1)                               # ... never a second one
        SR.finish()
        self.assertIsNone(work())
        self.pic = map_closed(self.pic)                                    # the map closed on the next press
        SR.release(0x78)
        SR.grant("F9", hold=0x78)
        res = work()
        done(res)
        self.assertFalse(res[0]["open"])
        self.assertFalse(work.found(res))                                  # (the read mark: "nothing here")
        self.assertEqual(type(a).shown, 0)                                 # -> the legend goes
        SR.finish()

    def test_leaving_the_trial(self):
        a = self.app()
        a.sek_area("Sanctum_1_Foyer_1")
        type(a).shown = 1
        a.sek_area("HideoutFelled")
        self.assertEqual(type(a).shown, 0)

    def test_no_timers_or_threads(self):
        for f in ("sekhemas.py", "sekhemas_page.py"):
            s = re.sub(r'"""[\s\S]*?"""', "", source(f))
            self.assertNotRegex(s, r"\.after\(|after_idle|threading|Thread\(|while True", f)
            self.assertNotRegex(s, r"\bmss\b|ImageGrab|BitBlt", f)


class Wiring(unittest.TestCase):
    def test_helpers_row(self):
        from soe2 import alerts_page as AP, features as FEAT, names
        line = AP.helper_blurb("sekhemas", "your Look key (Ctrl+Shift+R)")
        self.assertEqual(line, "Press your Look key (Ctrl+Shift+R) on the trial map: shows what to avoid and what "
                               "to take.")
        self.assertIn("sekhemas", AP.LOOK_HELPERS)
        self.assertIn("sekhemas", dict(AP.AlertsPage.HELPER_GROUPS)["In maps"])
        self.assertEqual(AP.AlertsPage.HELPER_NAMES["sekhemas"], "Trial of the Sekhemas")
        self.assertIn("Trial of the Sekhemas", names.FEATURES)
        self.assertIn("sekhemas", FEAT.BETA_HELPERS)
        self.assertEqual(FEAT.HELPER_SWITCHES["sekhemas"][2], "Trial of the Sekhemas")

    def test_esc_and_look_key(self):
        from soe2.readmark import ReadMarkPage
        self.assertIn("sek_hide", ReadMarkPage.LOOK_DRAWN)
        self.assertIn("self.sekhemas_look_job", source("look_page.py"))

    def test_no_close_button_no_click_through(self):
        s = source("sekhemas_page.py")
        self.assertNotIn('text="Close"', s)
        self.assertNotIn("click_through(", s)
        self.assertIn("click_to_close(", s)
        self.assertNotIn("sek_log", source("alerts_page.py"))

    def test_shipped(self):
        self.assertTrue(os.path.isfile(SK.data_path()))
        self.assertEqual(len(SK.data()["frame"]["parts"]), 9)
        with open(os.path.join(ROOT, "build_uioverhaul.bat"), encoding="utf-8") as f:
            bat = f.read()
        self.assertIn('--add-data "soe2\\sekhemas.json;soe2"', bat)


if __name__ == "__main__":
    unittest.main()
