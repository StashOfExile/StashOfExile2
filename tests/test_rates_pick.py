"""Exchange Rates overlay: the player picks which currencies show and drags them into order. Picks and order survive
a restart; a drag shows a line where the row will land; no picks shows an empty state with one button.

    DISPLAY=:99 python3.12 -m unittest tests.test_rates_pick"""
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402

from soe2 import ovrates as OR, ovrates_pick as PK  # noqa: E402
from soe2.config import SETTINGS, P as data_path  # noqa: E402
from soe2.rates import RATES  # noqa: E402

TABLE = {"exalted": 0.01, "chaos": 0.02, "divine": 1.0, "mirror": 900.0, "regal": 0.002}
PAL = {"bg": "#000000", "fg": "#ffffff", "text": "#ffffff", "muted": "#888888", "font": "Segoe UI",
       "head": "#d4af5f"}


class Pure(unittest.TestCase):
    def setUp(self):
        SETTINGS.pop("rates_ov", None)

    def test_default_is_the_old_list(self):
        self.assertEqual(PK.picked(), list(OR.COMMON)[:PK.MAX_PICKS], "the old list, up to 10")

    def test_moved(self):
        ids = ["a", "b", "c", "d"]
        self.assertEqual(PK.moved(ids, 0, 4), ["b", "c", "d", "a"], "to the end")
        self.assertEqual(PK.moved(ids, 3, 0), ["d", "a", "b", "c"], "to the top")
        self.assertEqual(PK.moved(ids, 1, 3), ["a", "c", "b", "d"])
        self.assertEqual(PK.moved(ids, 2, 1), ["a", "c", "b", "d"])

    def test_picks_survive_a_restart(self):
        PK.set_picked(["mirror", "chaos", "chaos", "divine"])
        with open(data_path("settings.json"), encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["rates_ov"]["picked"], ["mirror", "chaos", "divine"], "saved, in order, once each")

    def test_rows_follow_your_order(self):
        rows = OR.rate_rows(TABLE, ["mirror", "chaos", "nothing"])
        self.assertEqual([r[0] for r in rows], ["mirror", "chaos", "nothing"])
        self.assertEqual(rows[0][2], "900 div each")
        self.assertEqual(rows[1][2], "50 : 1 div")
        self.assertEqual(rows[2][2], "no rate yet")


class Tk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        S.setup_style(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        SETTINGS.pop("rates_ov", None)
        self.addCleanup(setattr, RATES, "table", RATES.table)
        RATES.table = dict(TABLE)
        self.top = tk.Toplevel(self.root)
        self.addCleanup(self.top.destroy)

    def app(self, locked=False):
        body = tk.Frame(self.top)
        body.pack(fill="both", expand=True)
        win = types.SimpleNamespace(locked=locked, draggable=lambda w: None)
        a = types.SimpleNamespace(ovr_body=body, ovr_P=PAL, ovr_win=win, root=self.root, ovr_picker=None)
        a.ov_font = lambda n: n
        a.ovr_cfg = lambda: SETTINGS.setdefault("rates_ov", {})
        for fn in ("ovr_fill", "ovr_refresh", "ovr_pick", "_ovr_reorder"):
            setattr(a, fn, types.MethodType(getattr(OR.OverlayRates, fn), a))
        return a, body

    def texts(self, w):
        out = []
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                out.append(c.cget("text"))
            out += self.texts(c)
        return out

    def test_only_picks_in_order_with_grips_when_unlocked(self):
        PK.set_picked(["mirror", "chaos"])
        a, body = self.app()
        with mock.patch.object(self.root, "after", lambda *x, **k: None):
            a.ovr_fill()
        t = self.texts(body)
        self.assertEqual([x for x in t if x in ("Mirror of Kalandra", "Chaos Orb", "Exalted Orb")],
                         ["Mirror of Kalandra", "Chaos Orb"])
        self.assertEqual(t.count(PK.GRIP), 2, "a grip on each row while unlocked")
        a2, body2 = self.app(locked=True)
        with mock.patch.object(self.root, "after", lambda *x, **k: None):
            a2.ovr_fill()
        self.assertEqual(self.texts(body2).count(PK.GRIP), 0, "locked: no grips")

    def test_empty_state_has_one_button(self):
        PK.set_picked([])
        a, body = self.app()
        with mock.patch.object(self.root, "after", lambda *x, **k: None):
            a.ovr_fill()
        self.assertEqual([x for x in self.texts(body) if x], ["No currencies picked", "Pick currencies"])

    def test_drag_shows_a_line_and_drops(self):
        PK.set_picked(["mirror", "chaos", "divine"])
        a, body = self.app()
        with mock.patch.object(self.root, "after", lambda *x, **k: None):
            a.ovr_fill()
        self.top.update()
        d = a.ovr_drag
        rows = d.rows
        last = rows[-1][1]
        below = last.winfo_rooty() + last.winfo_height() + 5
        kids = list(body.winfo_children())
        d._press(0)
        d._motion(types.SimpleNamespace(y_root=below))
        self.top.update()
        self.assertTrue(d.mark.winfo_ismapped(), "a line shows where the row will land")
        with mock.patch.object(self.root, "after_idle", lambda fn: fn()), \
                mock.patch.object(self.root, "after", lambda *x, **k: None):
            d._release(None)
        self.assertEqual(PK.picked(), ["chaos", "divine", "mirror"], "dropped at the end, and saved")
        order = [[c.cget("text") for c in r.pack_slaves() if isinstance(c, tk.Label) and c.cget("text") != PK.GRIP][0]
                 for r in body.pack_slaves() if isinstance(r, tk.Frame) and r.pack_slaves()]
        self.assertEqual(order, ["Chaos Orb", "Divine Orb", "Mirror of Kalandra"], "the overlay shows the new order")
        self.assertEqual([k for k in body.winfo_children() if k is not d.mark], [k for k in kids if k is not d.mark],
                         "moved, not made again")

    def test_picker_search_first_tick_and_remove(self):
        PK.set_picked(["chaos"])
        a, _body = self.app()
        a.ovr_refresh = lambda: None
        p = PK.RatesPicker(a)
        self.addCleanup(p.close)
        p.win.update()
        self.assertEqual(p.search.winfo_class(), "Entry")
        p.tick("mirror", True)
        self.assertEqual(PK.picked(), ["chaos", "mirror"])
        p.tick("chaos", False)
        self.assertEqual(PK.picked(), ["mirror"])
        p.q.set("regal")
        p.win.update()
        shown = [self.texts(r) for r in p.all_box.pack_slaves()]
        self.assertTrue(any("Regal Orb" in t for t in shown))
        self.assertFalse(any("Mirror of Kalandra" in t for t in shown))
        self.assertIn(PK.HELP, self.texts(p.win))

    def test_picker_limit_against_and_no_rebuild(self):
        PK.set_picked(["chaos"])
        a, _body = self.app()
        a.ovr_refresh = lambda: None
        p = PK.RatesPicker(a)
        self.addCleanup(p.close)
        p.win.update()
        rows = dict(p.all_rows)
        for cid in TABLE:
            p.tick(cid, True)
        self.assertEqual(len(PK.picked()), 5)
        self.assertEqual(p.all_rows, rows, "ticks change only the ticks")
        PK.set_picked([f"x{i}" for i in range(10)])
        self.assertFalse(p.tick("mirror", True), "10 is the most")
        self.assertEqual(p.note.cget("text"), PK.FULL)
        self.assertNotIn("mirror", PK.picked())
        p.vs.set("Exalted Orb")
        p.pick_against()
        self.assertEqual(PK.against(), "exalted")
        self.assertEqual(OR.rate_rows(TABLE, ["divine"], None, "exalted")[0][2], "100 ex each")

    def test_first_use_once(self):
        SETTINGS["rates_ov"] = {"on": True}
        self.assertTrue(PK.first_use_due())
        PK.mark_first_use()
        self.assertFalse(PK.first_use_due())


if __name__ == "__main__":
    unittest.main()
