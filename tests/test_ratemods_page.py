"""Rate Mods redesign (owner): the Mods group in the sidebar, the page's one intro line with its ⓘ, By roll (MIX B:
Top / Middle / Low rolls - "Same for every roll" by default, edges saved as values, a roll's group letter in the
price check: F left out the low-tier way with a note, other letters order what is dropped first), and the Table's
Rate selected bar grayed out until a row is ticked.

    python3.12 -m unittest tests.test_ratemods_page          (or tests/runall.sh)"""
import os
import sys
import tkinter as tk
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from soe2 import gear as G                                 # noqa: E402
from soe2 import mods as M                                 # noqa: E402
from soe2 import ratemods as RM                            # noqa: E402
from soe2 import sidebar as SB                             # noqa: E402
from soe2 import trade as T                                # noqa: E402

RING_MANA = "gear:ring:# to maximum mana"
GLOVES_FIRE = "gear:gloves:#% to fire resistance"


def ring_text():
    from test_pricecheck_golden import load_items
    return load_items()["rare_ring"]


class Saved(unittest.TestCase):
    """Nothing is written: the player's own files are kept in memory here."""

    def setUp(self):
        self.p = mock.patch.object(RM, "save_json", lambda *a, **k: True)
        self.p.start()
        self.by = dict(RM.ROLL_BY)
        RM.ROLL_BY.clear()

    def tearDown(self):
        RM.ROLL_BY.clear()
        RM.ROLL_BY.update(self.by)
        self.p.stop()


class Sidebar(unittest.TestCase):
    def test_mods_group_between_trade_and_stash(self):
        names = [g for g, _k in SB.GROUPS]
        self.assertEqual(names.index("Mods"), names.index("Trade") + 1)
        self.assertEqual(names.index("Stash"), names.index("Mods") + 1)
        groups = dict(SB.GROUPS)
        self.assertEqual(groups["Mods"], ("ratemods", "insights", "crafthelper"))
        self.assertEqual(groups["Trade"], ("pricecheck", "checks", "favorites", "rates"))
        self.assertEqual(groups["Stash"], ("wealth", "regex"))

    def test_caption_follows_the_group(self):
        for k in ("ratemods", "insights", "crafthelper"):
            self.assertEqual(SB.group_of(k), "Mods")


class Intro(unittest.TestCase):
    def test_one_line_with_its_tip(self):
        from soe2.modules.ratemods import RateMods
        from soe2 import ratemods_page as RP
        self.assertEqual(RateMods.blurb, "Bored, have a few minutes to kill? Rate some mods: it builds community mod "
                                         "data so everyone's price checks get more accurate.")
        self.assertEqual(RateMods.title, "Mod Lab", "owner, after 3.1.0: was Rate Mods")
        self.assertEqual([t for t, key in RateMods.blurb_rich if key],
                         ["a few minutes", "Rate some mods", "everyone's price checks"], "bold and in the accent")
        self.assertEqual(RP.QUESTION, "How valuable is each roll?")
        self.assertEqual(RateMods.blurb_tip(None), "S and A count as High, B, C and D as Normal, F is left out of "
                         "searches. Your ratings change your price checks at once. With Community data sharing on, "
                         "they're your vote too.")
        with open(RP.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("Rate how much each mod matters", src)          # (the old second line is gone)


class RichIntro(unittest.TestCase):
    """Owner, after 3.1.0: Mod Lab's intro bigger, its key words bold in the accent color, wrapping word by word and
    the header growing to fit, never cut off."""

    def test_wraps_and_the_header_grows(self):
        import tkinter as tk
        import types
        from soe2.modules.ratemods import RateMods
        from soe2.shell import PageBar
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        try:
            root.withdraw()
            mod = types.SimpleNamespace(blurb_rich=RateMods.blurb_rich, blurb=RateMods.blurb, blurb_tip=lambda: "tip",
                                        title="Mod Lab")
            win = types.SimpleNamespace(key="ratemods", title="Mod Lab",
                                        shell=types.SimpleNamespace(modules={"ratemods": mod}, where=lambda k: "Mods",
                                                                    app=types.SimpleNamespace()))
            pb = PageBar.__new__(PageBar)
            tk.Canvas.__init__(pb, root, width=1400, height=96)
            pb.win = win
            pb.place(x=0, y=0, width=1400)
            root.update()
            wide = pb._rich_layout()[1]
            self.assertEqual(len(wide), 1, "one line when it fits")
            keys = [p for line in wide for _x, p, k in line if k]
            self.assertEqual(" ".join(p.strip() for p in keys), "a few minutes Rate some mods everyone's price checks")
            h_wide = pb.height_now()
            pb.place(width=520)
            root.update()
            narrow = pb._rich_layout()[1]
            self.assertGreater(len(narrow), 1, "wraps in the Drawer")
            plain, bold, lh = pb._rich_fonts()
            for line in narrow:
                x, piece, key = line[-1]
                self.assertLessEqual(24 + x + (bold if key else plain).measure(piece.rstrip()), 520 - 24, piece)
            self.assertEqual(pb.height_now(), h_wide + (len(narrow) - 1) * lh, "the header grows a line at a time")
        finally:
            root.destroy()


class ByRoll(Saved):
    def test_default_is_same_for_every_roll(self):
        gs = RM.roll_groups("gear:gloves", GLOVES_FIRE)
        self.assertEqual([g["name"] for g in gs], ["Top rolls", "Middle rolls", "Low rolls"])
        self.assertTrue(all(g["grade"] is None for g in gs))
        self.assertTrue(RM.same_for_every_roll(GLOVES_FIRE))
        self.assertEqual(RM.by_roll_text("gear:gloves", GLOVES_FIRE, "B"), "same")

    def test_default_edges_25_40_rest(self):
        lad = RM.ladder("gear:gloves", GLOVES_FIRE)                # 8 tiers: 2 top, 3 middle, 3 low
        gs = RM.roll_groups("gear:gloves", GLOVES_FIRE)
        self.assertEqual([len(g["tiers"]) for g in gs], [2, 3, 3])
        self.assertEqual(RM.default_edges(lad), [lad[1][1], lad[4][1]])     # values, not tier numbers
        self.assertEqual(RM.group_range(gs[0], GLOVES_FIRE), "T1–T2 · 36–45%")
        self.assertIsNone(RM.default_edges(lad[:2]))               # (fewer than three tiers: no groups)

    def test_group_letter_back_to_the_mods_is_same_again(self):
        RM.set_group_grade(GLOVES_FIRE, 2, "ignore", mod_grade="B")
        self.assertEqual(RM.by_roll_text("gear:gloves", GLOVES_FIRE, "B"), "B · B · F")
        RM.set_group_grade(GLOVES_FIRE, 2, "B", mod_grade="B")
        self.assertTrue(RM.same_for_every_roll(GLOVES_FIRE))

    def test_price_check_takes_the_rolls_group_letter(self):
        RM.set_group_grade(RING_MANA, 1, "ignore")               # +60 mana on a ring: a middle roll
        it = G.parse_gear(ring_text())
        rec = {"item": it}
        mana = next(m for m in it["mods"] if "maximum Mana" in m["text"])
        self.assertEqual(mana["roll_key"], RING_MANA)
        self.assertEqual(mana["auto"], "ignore")
        self.assertEqual(mana["note"], "middle roll for this mod in Mod Lab - not searched - tick it to search on it")
        self.assertEqual(T.mod_impact(rec, mana), "ignore")
        rec["ov"] = {T.ov_key(mana): "normal"}                     # ticked: searched anyway
        self.assertEqual(T.mod_impact(rec, mana), "normal")
        RM.same_again(RING_MANA)                                   # back: as it was
        RM.apply_roll(mana)
        self.assertIsNone(mana.get("roll_grade"))
        self.assertNotEqual(mana.get("auto"), "ignore")

    def test_other_letters_order_the_drop(self):
        RM.set_group_grade(RING_MANA, 1, "D")
        it = G.parse_gear(ring_text())
        mana = next(m for m in it["mods"] if "maximum Mana" in m["text"])
        self.assertEqual(mana["roll_grade"], "D")
        self.assertEqual(M.drop_rank(M.tier_rank("S"), mana)[0], M.tier_rank("D"))
        self.assertEqual(T.mod_impact({"item": it}, mana), "normal")


class Votes(unittest.TestCase):
    """Players: the board's real High / Normal / Ignore counts (2 votes or more), never letters."""

    def setUp(self):
        RM._DATA.pop("ratings", None)

    def tearDown(self):
        RM._DATA.pop("ratings", None)

    def test_counts_and_not_enough(self):
        from soe2 import communitymods as CM
        d = {"ts": 5, "ratings": [["map contains an additional abyss", 9, 3, 1], ["one vote", 1, 0, 0]]}
        with mock.patch.object(CM, "cached", lambda: d):
            p = RM.players(["map contains an additional abyss"])
            self.assertEqual(RM.players_text(p), "High 9 · Normal 3 · Ignore 1")
            self.assertEqual(p[:2], ("High", 13))
            self.assertIsNone(RM.players(["one vote"]))
            self.assertEqual(RM.players_text(None), "not enough votes")
            self.assertIn("at least 2", RM.players_tip(None))
        with mock.patch.object(CM, "cached", lambda: {}):
            RM._DATA.pop("ratings", None)
            self.assertEqual(RM.players_text(None), "–")          # (nothing downloaded yet)


class Groups(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(RM.category("tablet", ["Any"]), "All tablets")
        self.assertEqual(RM.category("tablet", ["Breach"]), "Breach")
        self.assertEqual(RM.category("jewel", ["Ruby", "Time-Lost"]), "Ruby")
        self.assertEqual(RM.category("gear:gloves", []), "Gloves")


class Table(Saved):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S, themes as TH
        import test_bulk_layout as BL
        S.apply_look(TH.DEFAULT, cls.root)
        S.setup_style(cls.root)
        cls.app = BL.make_app(cls.root)
        cls.app.refresh_rules = lambda: None
        cls.body = tk.Frame(cls.root)
        cls.body.pack(fill="both", expand=True)
        cls.root.geometry("1400x900+0+0")
        cls.app.build_ratemods_page(cls.body)
        cls.app._rm_recount_all()
        cls.app.rm_pick("gear:gloves")
        cls.app.rm_view_pick("Table")
        for _ in range(10):
            cls.root.update()

    @classmethod
    def tearDownClass(cls):
        for job in cls.root.tk.splitlist(cls.root.tk.call("after", "info")):
            cls.root.tk.call("after", "cancel", job)
        cls.root.destroy()

    def states(self):
        return {g: b.instate(["disabled"]) for g, b in self.app.rm_bulk.items()}

    def test_three_roll_letters_rate_the_mod_and_move_on(self):
        """Feedback: a letter for Top, Middle and Low and nothing moved on. Now the mod is rated, Top's letter, and
        the next mod comes up; Middle and Low keep their own letters."""
        a = self.app
        a.rm_view_pick("One at a Time")
        a.rm_filter_pick("All")
        hit = next((i for i, e in enumerate(a.rm_q) if a.rm_roll_key(e) and RM.current([a.rm_roll_key(e)]) is None),
                   None)
        if hit is None:
            self.skipTest("no mod with three roll groups here")
        a.rm_i = hit
        key = a.rm_roll_key()
        with mock.patch.object(self.root, "after", lambda ms, fn=None: fn and fn()), \
                mock.patch.object(a, "_rm_rules_later", lambda: None):
            a.rm_group_pick(key, 0, "S")
            a.rm_group_pick(key, 1, "A")
            self.assertEqual(a.rm_i, hit, "two letters: still here")
            a.rm_group_pick(key, 2, "B")
        self.assertEqual(RM.current([key]), "S")
        self.assertEqual([g["grade"] or "S" for g in RM.roll_groups(a.rm_set, key)], ["S", "A", "B"])
        self.assertEqual(a.rm_i, hit + 1, "the next mod comes up")
        a.rm_view_pick("Table")

    def test_rate_selected_grayed_until_a_row_is_ticked(self):
        a = self.app
        a.rm_ticked.clear()
        a._rm_paint_bulk()
        self.assertTrue(all(self.states().values()))
        self.assertEqual(a.rm_bulk_n.cget("text"), "none selected")
        row = a.rm_rows()[0]
        a.rm_tick(row["keys"], True)
        self.assertFalse(any(self.states().values()))
        self.assertEqual(a.rm_bulk_n.cget("text"), "1 selected")
        a.rm_tick(row["keys"], False)
        self.assertTrue(all(self.states().values()))

    def test_rate_selected_rates_every_ticked_row(self):
        a = self.app
        a.rm_filter_pick("All")
        rows = a.rm_rows()[:2]
        with mock.patch.object(RM, "apply") as ap:
            for r in rows:
                a.rm_tick(r["keys"], True)
            self.assertEqual(a.rm_bulk_rate("A"), 2)
        self.assertEqual([c.args for c in ap.call_args_list], [(r["keys"], "A") for r in rows])
        self.assertFalse(a.rm_ticked)
        self.assertTrue(all(self.states().values()))

    def test_just_rated_keeps_the_last_five(self):
        a = self.app
        a.rm_recent = []
        es = a.rm_q[:7]
        for e in es:
            a.rm_note_recent([e])
        a.rm_note_recent([es[3]])                                  # rated again: to the top, once
        self.assertEqual([r["keys"] for r in a.rm_recent], [es[3]["keys"]] + [e["keys"] for e in es[6:3:-1]] +
                         [es[2]["keys"]])
        self.assertEqual(len(a.rm_recent), 5)

    def test_rated_today(self):
        from soe2.config import SETTINGS
        old = SETTINGS.get("rated_day")
        try:
            SETTINGS["rated_day"] = ["2026-11-18", 9]
            self.assertEqual(RM.rated_today("2026-11-19"), 0)
            RM.note_rated(2, "2026-11-19")
            RM.note_rated(1, "2026-11-19")
            self.assertEqual(RM.rated_today("2026-11-19"), 3)
        finally:
            SETTINGS["rated_day"] = old

    def test_gear_table_is_grouped_by_item_class(self):
        a = self.app
        a.rm_filter_pick("All")
        names = [g for g, _r in a.rm_tgroups()]
        self.assertIn("Gloves", names)
        self.assertIn("Helmets", names)                            # (Armour: every class of the kind)
        self.assertTrue(a.rm_group_open("Gloves"))
        self.assertFalse(a.rm_group_open("Helmets"))               # (folded: stays light)
        self.assertTrue(all(e["set"] == "gear:gloves" for e in a.rm_shown_rows()))

    def test_one_orange_button_opens_one_at_a_time(self):
        a = self.app
        self.assertEqual(str(a.rm_one_btn.cget("style")), "Primary.TButton")
        a.rm_one_btn.invoke()
        self.assertEqual(a.rm_view, "One at a Time")
        a.rm_view_pick("Table")

    def test_pictures_fit_a_square_and_load_when_missing(self):
        """Owner: some sets had no picture, some were far too big - a staff is tall."""
        from PIL import Image
        from unittest import mock
        from soe2.config import SETTINGS
        a = self.app
        self.addCleanup(SETTINGS.__setitem__, "pc_art", SETTINGS.get("pc_art", True))
        SETTINGS["pc_art"] = True                              # (Item pictures on, whatever a test before left)
        url = "https://web.poecdn.com/gen/image/x/abc/Staff.png"
        Image.new("RGBA", (78, 312), (200, 80, 40, 255)).save(a._pc_art_path(url))       # a 1x4 picture
        with mock.patch.object(type(a), "rm_pic_url", lambda self, s, e=None: url):
            ph = a.rm_pic("gear:staves", None, 24)
        self.assertEqual((ph.width(), ph.height()), (6, 24), "inside a 24 px square, never stretched")
        missing = "https://web.poecdn.com/gen/image/x/def/Bow.png"
        asked = []
        with mock.patch.object(type(a), "rm_pic_url", lambda self, s, e=None: missing), \
                mock.patch.object(type(a), "pc_art", lambda self, u, px=0: asked.append(u)):
            self.assertIsNone(a.rm_pic("gear:bows", None, 24))
        self.assertEqual(asked, [missing], "a picture not on this PC yet is loaded, then the page redraws")
        self.assertTrue(any(getattr(f, "__name__", "") == "came" for f in a._art_hooks))

    def test_card_default_same_for_every_roll(self):
        a = self.app
        a.rm_view_pick("One at a Time")
        e = next(x for x in a.rm_q if x["keys"] == [GLOVES_FIRE])
        a.rm_i = a.rm_q.index(e)
        a.rm_cardcv.redraw()
        self.assertEqual(a.rm_roll_key(), GLOVES_FIRE)
        self.assertEqual(a.rm_roll_state(GLOVES_FIRE), "same")
        cv = a.rm_cardcv
        self.assertTrue(any(t.startswith("grp:2:") for t in cv.acts))
        # owner: the three rolls' letters rate it - no second S A B C D F row under them, and a hint, not a pill
        self.assertFalse([t for t in cv.acts if t.startswith(("rate:", "grade:"))], "no second letter row")
        self.assertNotIn("same", cv.tips)
        texts = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        self.assertIn("Pick a letter for each roll to rate this mod.", texts)
        self.assertIn("Skip", texts)
        a._rm_apply([e["keys"]], "A")                             # rated: the pill, and Next to go on
        cv.redraw()
        self.assertIn("same", cv.tips)                            # the "✓ Same for every roll" mark
        self.assertNotIn("same", cv.acts)                         # (nothing to undo yet)
        texts = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        self.assertIn("Next ›", texts)
        self.assertNotIn("Skip", texts)
        a.rm_view_pick("Table")


if __name__ == "__main__":
    unittest.main()
