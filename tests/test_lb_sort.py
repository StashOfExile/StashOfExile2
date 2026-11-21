"""3.1.0: every Leaderboards column sorts on a header click, like a spreadsheet; a campaign run's class is never a
party member's.

    DISPLAY=:99 python3.12 -m unittest tests.test_lb_sort"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-test-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import leaderboard as LB       # noqa: E402

try:
    import tkinter as tk
    from tkinter import ttk
    from soe2 import leaderboard_page as LP
except ImportError:                       # pragma: no cover
    tk = LP = None


@unittest.skipIf(tk is None, "no tkinter")
class CellKey(unittest.TestCase):
    def test_values(self):
        k = LP.cell_key
        self.assertLess(k("time", "59:59"), k("time", "1:00:00"))
        self.assertLess(k("time", "1:07"), k("time", "2:18"))
        self.assertIsNone(k("mine", "-"))
        self.assertIsNone(k("n", ""))
        self.assertLess(k("n", "2"), k("n", "10"), "numbers as numbers, not text")
        self.assertEqual(k("name", "Worm (you)"), k("name", "worm"))
        self.assertEqual(k("name", "   ↳ run 2"), (1, "run 2"))

    def test_empty_last_both_ways(self):
        g = [((0, 2.0), ["b"]), (None, ["x"]), ((0, 1.0), ["a", "a2"])]
        self.assertEqual(LP.sorted_groups(g, False), ["a", "a2", "b", "x"])
        self.assertEqual(LP.sorted_groups(g, True), ["b", "a", "a2", "x"])


class Seg:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


@unittest.skipIf(tk is None, "no tkinter")
class HeaderClick(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()
        p = LP.LeaderboardPage.__new__(LP.LeaderboardPage)
        p.lb_sort = {}
        p.lb_titles = {"keys": {"#0": "Act / map", "mine": "My best", "best": "Best", "n": "Players"},
                       "board": {c: c for c in ("rank", "name", "time", "cls", "lvl", "deaths", "league", "when")}}
        p.lb_keys_tv = ttk.Treeview(self.root, columns=("mine", "best", "n"), show="tree headings")
        p.lb_tv = ttk.Treeview(self.root, columns=list(p.lb_titles["board"]), show="headings")
        p.lb_who = Seg("Everyone")
        p.lb_cat = "maps"
        p.lb_cat_key = lambda: p.lb_cat
        self.p = p

    def tearDown(self):
        self.root.destroy()

    def keys(self):
        kv = self.p.lb_keys_tv
        for k, mine, best, n in (("Lightless Void", "2:18", "2:18", 1), ("Caer Tarth", "-", "9:53", 12),
                                 ("The Origin Tower", "1:42", "1:42", 3)):
            kv.insert("", "end", iid=k, text=k, values=(mine, best, n))
        self.p.lb_key_pos = {k: i for i, k in enumerate(kv.get_children())}

    def test_left_table_every_column(self):
        self.keys()
        kv, p = self.p.lb_keys_tv, self.p
        p.lb_sort_by("keys", "mine")
        self.assertEqual(kv.get_children(), ("The Origin Tower", "Lightless Void", "Caer Tarth"), "no time goes last")
        self.assertEqual(kv.heading("mine", "text"), "My best ▲")
        p.lb_sort_by("keys", "mine")
        self.assertEqual(kv.get_children(), ("Lightless Void", "The Origin Tower", "Caer Tarth"))
        self.assertEqual(kv.heading("mine", "text"), "My best ▼")
        p.lb_sort_by("keys", "n")
        self.assertEqual(kv.get_children()[0], "Lightless Void")
        self.assertEqual(kv.heading("mine", "text"), "My best", "only the sorted column has a mark")
        p.lb_sort_by("keys", "#0")
        self.assertEqual(kv.get_children()[0], "Caer Tarth")

    def test_campaign_names_sort_in_act_order(self):
        self.p.lb_cat = "campaign"
        kv = self.p.lb_keys_tv
        for k in ("Act I", "Act II", "Interlude", "Whole campaign"):
            kv.insert("", "end", iid=k, text=k, values=("-", "-", ""))
        self.p.lb_key_pos = {k: i for i, k in enumerate(kv.get_children())}
        self.p.lb_sort_by("keys", "#0")
        self.p.lb_sort_by("keys", "#0")
        self.assertEqual(kv.get_children(), ("Whole campaign", "Interlude", "Act II", "Act I"))

    def test_a_players_other_runs_stay_under_their_best(self):
        bv, p = self.p.lb_tv, self.p
        p.lb_at = {"b1": 300, "b2": 100, "b3": 200, "b4": 50}
        bv.insert("", "end", iid="b1", values=(1, "Ann", "1:00", "Witch", "80", 0, "L", "x"))
        bv.insert("", "end", iid="b2", values=("", "   ↳ run 2", "1:30", "Witch", "80", 2, "L", "x"))
        bv.insert("", "end", iid="b3", values=(2, "Bob", "1:10", "", "-", 5, "L", "x"))
        bv.insert("", "end", iid="b4", values=(3, "Cy", "1:20", "Monk", "79", 1, "L", "x"))
        p.lb_sort_by("board", "deaths")
        p.lb_sort_by("board", "deaths")
        self.assertEqual(bv.get_children(), ("b3", "b4", "b1", "b2"))
        p.lb_sort_by("board", "lvl")
        self.assertEqual(bv.get_children(), ("b4", "b1", "b2", "b3"))
        p.lb_sort_by("board", "when")
        self.assertEqual(bv.get_children(), ("b4", "b3", "b1", "b2"), "by the date, not the text")
        p.lb_sort_by("board", "cls")
        self.assertEqual(bv.get_children(), ("b4", "b1", "b2", "b3"))

    def test_mine_sorts_each_run(self):
        self.p.lb_who = Seg("Mine")
        bv, p = self.p.lb_tv, self.p
        p.lb_at = {}
        bv.insert("", "end", iid="m0", values=(1, "me", "1:00", "", "80", 3, "L", "x"))
        bv.insert("", "end", iid="m1", values=(2, "   ↳ me · run 2", "1:30", "", "70", 0, "L", "x"))
        p.lb_sort_by("board", "deaths")
        self.assertEqual(bv.get_children(), ("m1", "m0"))

    def test_sort_is_kept_when_the_list_fills_again(self):
        self.keys()
        self.p.lb_sort_by("keys", "best")
        kv = self.p.lb_keys_tv
        kv.delete(*kv.get_children())
        self.keys()
        self.p.lb_sort_apply("keys")
        self.assertEqual(kv.get_children(), ("The Origin Tower", "Lightless Void", "Caer Tarth"))

    def test_every_header_is_clickable(self):
        src = open(os.path.join(ROOT, "soe2", "leaderboard_page.py"), encoding="utf-8").read()
        self.assertEqual(src.count("command=lambda c=cid: self.lb_sort_by("), 2)


class PartyClass(unittest.TestCase):
    """Owner: a campaign zone time showed Druid, a party member's class, not his."""

    def run_cls(self, classes, tracker):
        with mock.patch.dict(LB.SETTINGS, {"tracker": tracker}):
            return LB._run_cls("", {}, classes)

    def test_never_the_last_to_level(self):
        self.assertEqual(self.run_cls({"Me": "Invoker", "Friend": "Druid"}, {}), "")

    def test_your_name_from_options(self):
        self.assertEqual(self.run_cls({"Me": "Invoker", "Friend": "Druid"}, {"character": "me"}), "Invoker")

    def test_the_name_the_timer_worked_out(self):
        self.assertEqual(self.run_cls({"Me": "Invoker", "Friend": "Druid"}, {"character_guess": "Me"}), "Invoker")

    def test_one_character_only(self):
        self.assertEqual(self.run_cls({"Me": "Invoker"}, {}), "Invoker")

    def test_a_named_run_keeps_its_own(self):
        with mock.patch.dict(LB.SETTINGS, {"tracker": {"character": "Friend"}}):
            self.assertEqual(LB._run_cls("Me", {}, {"Me": "Invoker", "Friend": "Druid"}), "Invoker")


if __name__ == "__main__":
    unittest.main()
