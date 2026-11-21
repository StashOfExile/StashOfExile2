"""UI rule 24 (the softer look): round corners drawn smooth (Pillow pictures, not a jagged canvas polygon), one picture
per key and per Tk, a thin scroll bar with no arrows, and pictures made again when the theme changes.

    python3.12 -m unittest tests.test_soft_look          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk

HOME = tempfile.mkdtemp(prefix="soe2-soft-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import soft as SOFT                               # noqa: E402
from soe2 import style as ST                                # noqa: E402
from soe2 import themes as TH                               # noqa: E402

try:
    import PIL                                              # noqa: F401
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


def _tk():
    try:
        r = tk.Tk()
    except tk.TclError:
        raise unittest.SkipTest("no display")
    r.withdraw()
    return r


@unittest.skipUnless(HAVE_PIL, "needs Pillow")
class Cache(unittest.TestCase):
    def test_one_picture_per_key_and_a_new_tk_gets_new_ones(self):
        a = _tk()
        try:
            one = SOFT.corners(a, 6, (10, 20, 30), (90, 90, 90), 1)
            two = SOFT.corners(a, 6, (10, 20, 30), (90, 90, 90), 1)
            self.assertIs(one, two, "the same key gives the same pictures")
            other = SOFT.corners(a, 6, (10, 20, 31), (90, 90, 90), 1)
            self.assertIsNot(one, other, "another color is another picture")
            p1 = SOFT.photo(a, ("t", 1), lambda: SOFT.shape(20, 20, 6, (1, 2, 3)))
            self.assertIs(p1, SOFT.photo(a, ("t", 1), lambda: SOFT.shape(20, 20, 6, (1, 2, 3))))
            names_a = {str(i) for i in one}
        finally:
            a.destroy()
        b = _tk()
        try:
            again = SOFT.corners(b, 6, (10, 20, 30), (90, 90, 90), 1)
            self.assertFalse(names_a & {str(i) for i in again}, "a new Tk makes its own pictures")
            for img in again:                               # (and they belong to it: usable on its canvas)
                cv = tk.Canvas(b)
                cv.create_image(0, 0, image=img)
        finally:
            b.destroy()

    def test_corners_are_smooth(self):
        """The edge of a corner has in-between alpha (anti-aliased), not only on / off."""
        im = SOFT.shape(13, 13, 6, (200, 100, 50))
        alphas = {im.getpixel((x, y))[3] for x in range(6) for y in range(6)}
        self.assertTrue(any(0 < a < 255 for a in alphas), alphas)


@unittest.skipUnless(HAVE_PIL, "needs Pillow")
class RoundRect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = _tk()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_round_rect_is_an_image_item_not_a_polygon(self):
        cv = tk.Canvas(self.root, width=300, height=200)
        i = TH.round_rect(cv, 10, 10, 210, 110, 8, fill="#223344", outline="#556677", tags=("card",))
        self.assertEqual(cv.type(i), "image")
        self.assertFalse([k for k in cv.find_all() if cv.type(k) == "polygon"], "no polygon")
        self.assertIn(i, cv.find_withtag("card"))
        b = cv.bbox(i)                                       # the whole box, not one corner
        self.assertLessEqual(b[0], 10)
        self.assertGreaterEqual(b[2], 210)

    def test_it_acts_as_one_item(self):
        cv = tk.Canvas(self.root, width=300, height=200)
        t = cv.create_text(50, 50, text="x")
        i = TH.round_rect(cv, 10, 10, 110, 90, 6, fill="#223344", outline="#556677")
        cv.tag_lower(i, t)                                   # every part goes under the text
        order = cv.find_all()
        self.assertEqual(order[-1], t)
        cv.itemconfigure(i, fill="#aa0000", outline="")
        self.assertEqual(cv.itemcget(i, "fill"), "#aa0000")
        cv.coords(i, 20, 20, 200, 150)                       # (or a polygon's points: its bounds)
        self.assertGreaterEqual(cv.bbox(i)[2], 199)
        cv.delete(i)
        self.assertEqual(cv.find_all(), (t,), "deleting the id deletes every part")

    def test_square_without_radius(self):
        cv = tk.Canvas(self.root)
        self.assertEqual(cv.type(TH.round_rect(cv, 0, 0, 10, 10, 0, fill="#000000")), "rectangle")


@unittest.skipUnless(HAVE_PIL, "needs Pillow")
class Ttk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = _tk()
        ST.apply_look("emberforge", cls.root)
        ST.setup_style(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        TH.set_theme(TH.packs()[TH.pick_id(None)], None)

    def _elements(self, layout):
        out = []
        for name, opts in layout:
            out.append(name)
            out += self._elements(opts.get("children", []))
        return out

    def test_scrollbar_has_no_arrows_and_is_thin(self):
        s = ttk.Style(self.root)
        for o in ("Vertical", "Horizontal"):
            els = self._elements(s.layout(o + ".TScrollbar"))
            self.assertFalse([e for e in els if "arrow" in e], els)
            self.assertTrue([e for e in els if e.endswith("thumb")], els)
        f = tk.Frame(self.root, bg="#123456")
        sb = ttk.Scrollbar(f, orient="vertical")
        sb.pack(side="right", fill="y")
        f.pack()
        self.root.update_idletasks()
        self.assertLessEqual(sb.winfo_reqwidth(), 12)
        self.assertEqual(str(sb.cget("style")), "", "the code's own style is what cget says")
        want = "Bg%s." % str(f.cget("bg")).lstrip("#").lower()
        self.assertTrue(str(sb.tk.call(sb._w, "cget", "-style")).startswith(want), "blends into its parent")

    def test_buttons_and_fields_are_round_pictures(self):
        s = ttk.Style(self.root)
        self.assertIn(".soft.", str(s.layout("TEntry")))
        self.assertIn(".soft.", str(s.layout("TCombobox")))
        self.assertIn(".face", str(s.layout("TButton")))
        self.assertEqual(TH.button_spec(TH.ST.theme, "normal")["radius"], SOFT.RADIUS)
        b = ttk.Button(tk.Frame(self.root, bg="#204060"), text="Go", style="Primary.TButton")
        self.assertEqual(b.cget("style"), "Primary.TButton")
        self.assertEqual(b["style"], "Primary.TButton")

    def test_theme_change_makes_the_pictures_again(self):
        s = ttk.Style(self.root)
        before = str(s.layout("TButton"))
        sb_before = str(s.layout("Vertical.TScrollbar"))
        n = len(SOFT.tk_cache(self.root))
        other = next(t for t in TH.ordered() if t.id != TH.ST.theme.id and not t.light)
        ST.relook(self.root, other.id)
        try:
            self.assertNotEqual(before, str(s.layout("TButton")), "new faces, in the new colors")
            self.assertNotEqual(sb_before, str(s.layout("Vertical.TScrollbar")))
            self.assertGreater(len(SOFT.tk_cache(self.root)), n, "new pictures made")
        finally:
            ST.relook(self.root, "emberforge")

    def test_theme_change_recolors_canvas_corners(self):
        cv = tk.Canvas(self.root)
        cv.pack()
        i = TH.round_rect(cv, 4, 4, 80, 40, 6, fill=ST.C["panel"], outline=ST.C["line"])
        rec = SOFT.round_rect_rec(cv, i)
        old = rec["imgs"]
        other = next(t for t in TH.ordered() if t.id != TH.ST.theme.id and not t.light)
        ST.relook(self.root, other.id)
        try:
            self.assertIsNot(SOFT.round_rect_rec(cv, i)["imgs"], old)
            self.assertEqual(SOFT.round_rect_rec(cv, i)["fill"], str(cv.tk.call(cv._w, "itemcget", rec["parts"][4],
                                                                                   "-fill")))
        finally:
            ST.relook(self.root, "emberforge")


@unittest.skipUnless(HAVE_PIL, "needs Pillow")
class Caps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = _tk()
        ST.apply_look("emberforge", cls.root)
        ST.setup_style(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_a_card_frame_gets_round_corners_unseen_by_the_code(self):
        top = tk.Toplevel(self.root)
        self.addCleanup(top.destroy)
        outer = tk.Frame(top, bg="#101010", width=300, height=200)
        outer.pack(fill="both", expand=True)
        card = tk.Frame(outer, bg="#303030", padx=16, pady=12, highlightthickness=1, highlightbackground="#505050")
        tk.Label(card, text="hi").pack()
        card.pack(padx=16, pady=16)
        flush = tk.Frame(outer, bg="#303030", padx=16, pady=12)     # (flush with its parent's edges: left square)
        flush.pack(fill="x")
        top.update()
        self.assertTrue(card.__dict__.get("_soe2_caps"))
        self.assertFalse(flush.__dict__.get("_soe2_caps"))
        self.assertEqual(len(card.winfo_children()), 1, "the caps aren't the page's children")
        for w in card.winfo_children():
            w.destroy()
        self.assertTrue(all(c.winfo_exists() for c in card.__dict__["_soe2_caps"].values()))
