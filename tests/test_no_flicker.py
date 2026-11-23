"""UI rule 22 (no flicker: change in place): a click, a tick, a typed value or a new number changes only the widgets
that changed - the same widget objects are still there afterwards and show the new state. Rebuilds are kept for
when the rows themselves change.

    python3.12 -m unittest tests.test_no_flicker          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import types
import unittest
from tkinter import ttk
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-flicker-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import inplace as IP                            # noqa: E402


class Tk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def frame(self):
        f = tk.Toplevel(self.root)
        self.addCleanup(f.destroy)
        return f


class Helpers(Tk):
    def test_set_cfg_changes_only_what_differs(self):
        lab = tk.Label(self.frame(), text="a", fg="#111111")
        calls = []
        lab.config = lambda **kw: calls.append(kw)
        IP.set_cfg(lab, text="a", fg="#111111")
        self.assertEqual(calls, [])
        IP.set_cfg(lab, text="b", fg="#111111")
        self.assertEqual(calls, [{"text": "b"}])

    def test_tv_sync_same_rows_keeps_rows_selection_and_scroll(self):
        tv = ttk.Treeview(self.frame(), columns=("a", "b"), show="headings", height=5)
        tv.pack()
        rows = [(f"r{i}", dict(values=(f"n{i}", i), tags=())) for i in range(40)]
        self.assertFalse(IP.tv_sync(tv, rows))                 # first time: built
        tv.selection_set("r7")
        tv.yview_moveto(0.5)
        top = tv.yview()[0]
        rows2 = [(i, dict(values=(kw["values"][0], kw["values"][1] + (100 if i == "r7" else 0)), tags=()))
                 for i, kw in rows]
        with mock.patch.object(tv, "delete", side_effect=AssertionError("deleted")):
            self.assertTrue(IP.tv_sync(tv, rows2))             # same rows: cells only
        self.assertEqual(tv.item("r7", "values"), ("n7", "107"))
        self.assertEqual(tv.selection(), ("r7",))
        self.assertEqual(tv.yview()[0], top)

    def test_tv_sync_other_rows_keeps_selection_and_scroll(self):
        tv = ttk.Treeview(self.frame(), columns=("a",), show="headings", height=5)
        tv.pack()
        rows = [(f"r{i}", dict(values=(i,))) for i in range(40)]
        IP.tv_sync(tv, rows)
        tv.selection_set("r3")
        self.assertFalse(IP.tv_sync(tv, rows[:20]))            # rows go: built again, the pick stays
        self.assertEqual(tv.selection(), ("r3",))
        self.assertEqual(len(tv.get_children()), 20)


class Rates(Tk):
    """Rates › Exchange Helper: a typed amount changes the cards' words, it does not build them again."""

    def stub(self):
        from soe2 import app as A
        from soe2.rates import RATES
        self.addCleanup(setattr, RATES, "table", RATES.table)
        RATES.table = {"divine": 1.0, "exalted": 0.01, "chaos": 0.02}
        top = self.frame()
        s = types.SimpleNamespace()
        s.ex_out, s.ex_market, s.ex_back = (tk.Label(top) for _ in range(3))
        s.ex_cards = tk.Frame(top)
        s.ex_have, s.ex_want, s.ex_amt = tk.StringVar(value="Divine Orb"), tk.StringVar(value="Exalted Orb"), \
            tk.StringVar(value="10")
        s.ex_boxes, s.ex_pics, s.ex_blank = [], [], None
        s.ex_icons = types.SimpleNamespace(get=lambda *a: None)
        s.ex_currencies = lambda: [("Divine Orb", "divine"), ("Exalted Orb", "exalted"), ("Chaos Orb", "chaos")]
        s.ex_page = tk.Frame(top, width=1000)
        s.ex_cards_place = lambda card, col: card.grid(row=0, column=col)
        s._ex_cards_clear = types.MethodType(A.App._ex_cards_clear, s)
        s.draw = types.MethodType(A.App.draw_exchange, s)
        return s

    def test_typed_amount_keeps_the_cards(self):
        s = self.stub()
        s.draw()
        cards = list(s.ex_cards.winfo_children())
        self.assertEqual(len(cards), 3)
        texts = [[w.cget("text") for w in c.winfo_children()] for c in cards]
        s.ex_amt.set("25")
        s.draw()
        self.assertEqual(list(s.ex_cards.winfo_children()), cards)       # the same widgets
        self.assertTrue(all(c.winfo_exists() for c in cards))
        now = [[w.cget("text") for w in c.winfo_children()] for c in cards]
        self.assertNotEqual(texts, now)                                    # the "gets ≈" line shows the new number
        self.assertIn("25", now[0][-1])

    def test_a_new_pair_keeps_the_cards_and_no_amount_hides_the_line(self):
        s = self.stub()
        s.draw()
        cards = list(s.ex_cards.winfo_children())
        s.ex_want.set("Chaos Orb")
        s.ex_amt.set("")
        s.draw()
        self.assertEqual(list(s.ex_cards.winfo_children()), cards)
        self.assertTrue(all(len(c.pack_slaves()) == 4 for c in cards))     # the 5th (amount) line is hidden
        self.assertIn("Chaos Orb", cards[0].winfo_children()[3].cget("text"))

    def test_same_pair_picked_clears_then_builds_again(self):
        s = self.stub()
        s.draw()
        s.ex_want.set("Divine Orb")
        s.draw()
        self.assertEqual(s.ex_cards.winfo_children(), [])


class Overlay(Tk):
    def test_alert_card_countdown_moves_the_bar(self):
        from soe2 import alertcard as AC
        top = self.frame()
        cd = AC.Card.__new__(AC.Card)
        bar = tk.Canvas(top, height=2, width=200)
        bar.pack()
        top.update()
        row = types.SimpleNamespace(color="#ff0000")
        cd.bar, cd.rows, cd.left, cd.total, cd.win = bar, [row], 1000, 1000, top
        cd.alive = lambda: True
        cd.close_all = lambda: None
        top.after = lambda *a, **k: None
        cd.tick()
        items = bar.find_all()
        self.assertEqual(len(items), 1)
        cd.tick()
        cd.tick()
        self.assertEqual(bar.find_all(), items)                # the same item, moved - not deleted and drawn again
        self.assertLess(bar.coords(items[0])[2], 200)

    def test_note_tab_pick_repaints_the_labels_in_place(self):
        from soe2.overlay import Overlay as OV
        top = self.frame()
        o = OV.__new__(OV)
        o.cfg = {"notes_tabs": [{"name": "A", "text": ""}, {"name": "B", "text": ""}, {"name": "C", "text": ""}],
                 "notes_tab": 0}
        bar = tk.Frame(top)
        bar.pack()
        o.notes_tabbar, o.notes, o.root = bar, top, self.root
        o.note_colours = lambda: ("#101010", "#eeeeee")
        o.note_body_font = lambda: "Segoe UI"
        o.note_font_step = lambda d: None
        o.switch_tab = lambda i: None
        o.rename_inline = lambda i: None
        o.tab_menu = lambda *a: None
        o.add_tab = lambda: None
        o._paint_tabs()
        labs = [o.notes_tab_labels[i] for i in range(3)]
        kids = list(bar.winfo_children())
        o.cfg["notes_tab"] = 2
        self.assertTrue(o._tabs_select_in_place())
        self.assertEqual(list(bar.winfo_children()), kids)                  # nothing destroyed
        self.assertEqual([lab.cget("bg") for lab in labs], ["#101010", "#101010", "#eeeeee"])   # the pick: filled
        self.assertEqual(str(labs[2].cget("font")).split()[-1], "bold")     # ... and bold (a word, not color alone)
        o.cfg["notes_tabs"].append({"name": "D", "text": ""})
        self.assertFalse(o._tabs_select_in_place())                        # a tab came: the bar is built again

    def test_rates_overlay_refresh_rewords_in_place(self):
        from soe2 import ovrates as OR
        from soe2.rates import RATES
        top = self.frame()
        body = tk.Frame(top)
        body.pack()
        self.addCleanup(setattr, RATES, "table", RATES.table)
        RATES.table = {"exalted": 0.01, "chaos": 0.02}
        app = types.SimpleNamespace(ovr_body=body, ovr_P={"bg": "#000", "fg": "#fff", "text": "#fff", "muted": "#888",
                                                          "font": "Segoe UI"}, ovr_win=None, root=self.root)
        app.ov_font = lambda n: n
        fill = app.ovr_fill = types.MethodType(OR.OverlayRates.ovr_fill, app)
        with mock.patch.object(self.root, "after", lambda *a, **k: None):
            fill()
            kids = list(body.winfo_children())
            self.assertTrue(kids)
            RATES.table = {"exalted": 0.02, "chaos": 0.02}
            fill()
        self.assertEqual(list(body.winfo_children()), kids)


class Pages(Tk):
    def test_goto_arrow_keys_repaint_rows_in_place(self):
        from soe2 import goto as GO
        top = self.frame()
        g = GO.GoTo.__new__(GO.GoTo)
        real = GO.TH.ST.theme                                  # (None before the app set its look: a stand-in)
        theme = real or types.SimpleNamespace(c=lambda name, *a, **k: "#444444" if name == "hover" else "#222222",
                                              light=False)
        if real is None:
            GO.TH.ST.theme = theme
            self.addCleanup(setattr, GO.TH.ST, "theme", None)
        g.list, g.win, g._place = tk.Frame(top), None, lambda: None
        g.list.pack()
        g.rows = [("Page", f"Page {i}", "", "", lambda: None) for i in range(4)]
        g.sel = 0
        g.paint()
        kids = list(g.list.winfo_children())
        bgs = [k.cget("bg") for k in kids]
        g.sel = 2
        g.paint()
        self.assertEqual(list(g.list.winfo_children()), kids)
        self.assertNotEqual([k.cget("bg") for k in kids], bgs)             # the pick moved (its row is the raised one)
        g.rows = g.rows[:2]
        g.sel = 0
        g.paint()
        self.assertEqual(list(g.list.winfo_children()), kids[:2])         # fewer hits: the tail goes, the rest stays


class Lists(Tk):
    def test_bulk_pricing_filter_adds_and_removes_rows_only(self):
        from soe2.app import App
        top = self.frame()
        tv = ttk.Treeview(top, columns=("a",), show="headings", height=4)
        tv.pack()
        recs = {i: {"id": i, "name": f"item {i}", "src": "manual"} for i in range(1, 31)}
        self.shown_hide = set()
        s = types.SimpleNamespace(tree=tv, records=recs, COLS=("a",), sort_col=None, ALL_CATS="All items",
                                  cat_var=tk.StringVar(value="All items"), empty_text="empty",
                                  empty_lbl=tk.Label(top), updated=[], detail=[])
        s.stash_key = lambda rec: rec["id"]
        s.visible = lambda rec: rec["id"] not in self.shown_hide
        s.update_row = lambda rid: (s.updated.append(rid), tv.item(str(rid), values=(recs[rid]["name"],)))
        s._apply_sort = lambda: None
        s.in_list = lambda rec: True
        s.list_src = lambda: "manual"
        s.update_total = lambda: None
        s.bk_empty_paint = lambda: None                      # (Bulk Pricing's empty state: bulk_page)
        s.show_detail = lambda rec: s.detail.append(rec)
        s.bk_autopick = lambda: False                        # (Bulk Pricing picks the first row: bulk_page)
        s.go = types.MethodType(App._rebuild_tree_in_place, s)
        s.go(set())
        self.assertEqual(len(tv.get_children()), 30)
        tv.selection_set("5")
        tv.yview_moveto(0.5)
        top_pos = tv.yview()[0]
        kept = {i: tv.get_children().index(i) for i in ("5", "20")}
        self.shown_hide = {1, 2, 3}                          # a filter: three rows go
        with mock.patch.object(tv, "delete", wraps=tv.delete) as dele:
            s.go({"5"})
        self.assertEqual(dele.call_args[0], ("1", "2", "3"))            # only those
        self.assertEqual(len(tv.get_children()), 27)
        self.assertEqual(tv.selection(), ("5",))                         # the pick, the scroll and the item card stay
        self.assertEqual(s.detail, [])
        self.assertAlmostEqual(tv.yview()[0], top_pos, delta=0.2)
        self.shown_hide = set()                                          # the filter is cleared: they come back
        s.go({"5"})
        self.assertEqual(list(tv.get_children()), [str(i) for i in range(1, 31)])
        self.shown_hide = {5}                                            # the picked row goes: the card empties
        s.go({"5"})
        self.assertEqual(s.detail, [None])

    def test_price_check_chips_recolor_in_place(self):
        from soe2.pricecheck_page import PriceCheckPage
        top = self.frame()
        box = tk.Frame(top, width=900)
        box.pack()
        top.update()
        recs = {i: {"id": i, "item": {"name": f"Thing {i}"}, "est": 1.5, "state": "done", "src": "pc", "time": i}
                for i in (1, 2, 3)}
        s = types.SimpleNamespace(pc_listcol=None, pc_recent=box, records=recs, pc_rid=3, PC_CHIPS=8,
                                  pc_recent_menu=tk.Menu(top), pc_recent_all=tk.Label(top), pc_show=lambda r: None)
        s.pc_recs = lambda: sorted(recs.values(), key=lambda r: -r["time"])
        s.pc_label = lambda r: r["item"]["name"]
        paint = types.MethodType(PriceCheckPage.pc_recent_paint, s)
        paint()
        chips = dict(s.pc_chips)
        self.assertEqual(len(chips), 3)
        s.pc_rid = 2                                          # another one picked (a tick, a click)
        with mock.patch.object(tk.Label, "destroy", side_effect=AssertionError("destroyed")):
            paint()
        self.assertEqual(s.pc_chips, chips)                   # the same labels
        self.assertNotEqual(chips[2].cget("fg"), chips[3].cget("fg"))
        recs[3]["est"] = 9.0                                  # a new price: the chip's words change -> built again
        paint()
        self.assertNotEqual(dict(s.pc_chips)[3], chips[3])

    def test_price_check_history_keeps_rows(self):
        from soe2.pricecheck_page import PriceCheckPage
        top = self.frame()
        tv = ttk.Treeview(top, columns=("a", "b", "c"), show="headings")
        tv.pack()
        recs = {i: {"id": i, "item": {"name": f"Thing {i}"}, "est": 1.5, "state": "queued", "src": "pc", "time": i}
                for i in (1, 2, 3)}
        s = types.SimpleNamespace(pc_hist_cb=ttk.Combobox(top), pc_hist_var=tk.StringVar(), pc_hist_tv=tv, records=recs,
                                  pc_rid=2, pc_hist_empty=tk.Label(top), _pc_hist_quiet=False)
        s.pc_recent_paint = lambda: None
        s.pc_recs = lambda: sorted(recs.values(), key=lambda r: -r["time"])
        s.pc_label = lambda r: r["item"]["name"]
        refresh = types.MethodType(PriceCheckPage.pc_refresh_hist, s)
        with mock.patch("soe2.pricecheck_page.pc_key_label", lambda: "F2"):
            refresh()
            rows = tv.get_children()
            recs[2]["state"] = "done"
            with mock.patch.object(tv, "delete", side_effect=AssertionError("deleted")):
                refresh()
        self.assertEqual(tv.get_children(), rows)
        self.assertEqual(tv.selection(), ("2",))


class Wealth(Tk):
    def stub(self):
        from soe2.wealth_page import WealthPage
        top = self.frame()
        s = WealthPage.__new__(WealthPage)
        s.w_rows = []
        s.w_snap_cats = tk.Frame(top)
        s.w_snap_cats.pack()
        return s

    def test_snapshot_kinds_keep_their_labels(self):
        s = self.stub()
        a = {"by_cat": {"currency": 10.0, "gear": 4.0}}
        b = {"by_cat": {"currency": 12.0, "gear": 1.0, "maps": 3.0}}
        s._snap_cats(b, a)
        labs = list(s.w_snap_cats.winfo_children())
        self.assertEqual(len(labs), 9)
        s._snap_cats(a, None)                                # another snapshot picked: fewer kinds, no change column
        self.assertEqual(list(s.w_snap_cats.winfo_children()), labs)     # nothing destroyed
        mapped = [w for w in labs if w.winfo_ismapped() or w.grid_info()]
        self.assertTrue(mapped)
        s._snap_cats(None, clear=True)
        self.assertEqual(list(s.w_snap_cats.winfo_children()), labs)
        self.assertFalse(any(w.grid_info() for w in labs))


class Settings(Tk):
    def test_a_key_set_keeps_the_boxes(self):
        from soe2.settings_page import SettingsPage
        top = self.frame()
        frame = tk.Frame(top)
        frame.pack()
        keys = {"a:one": "F5", "a:two": "F6"}
        s = SettingsPage.__new__(SettingsPage)
        s.hk_frame, s.root = frame, self.root
        s.all_hotkeys = lambda: [("One", keys["a:one"], "Group", "a:one"), ("Two", keys["a:two"], "Group", "a:two"),
                                 ("Copy", "Ctrl+C", "Group", None)]
        s.save_hotkeys = lambda: None
        s.fill_hotkeys()
        kids, rows = list(frame.winfo_children()), dict(s.hk_rows)
        keys["a:one"] = "F7"                                  # a key was set: the same rows, a new key
        s.fill_hotkeys()
        self.assertEqual(list(frame.winfo_children()), kids)                # nothing destroyed: the box keeps its focus
        self.assertEqual(s.hk_rows, rows)
        self.assertEqual(s.hk_vars["a:one"].get(), "F7")
        keys["a:two"] = "F7"                                  # a clash: the words go red, and the box too
        s.fill_hotkeys()
        self.assertEqual(list(frame.winfo_children()), kids)
        from soe2.style import C
        self.assertEqual(rows["a:two"][0].cget("fg"), C["red"])
        keys["a:two"] = "F8"                                  # ... and back
        s.fill_hotkeys()
        self.assertEqual(rows["a:two"][0].cget("fg"), C["text"])
        s._hk_sig = None                                       # a row added or taken away: built again
        s.fill_hotkeys()
        self.assertNotEqual(list(frame.winfo_children()), kids)


class Plan(Tk):
    """League Plan's list: a tick, a move, a skip or a new count changes the rows that are there; a new goal adds
    one row and a removed goal takes only its own away."""

    def setUp(self):
        from soe2 import focus as F
        from soe2.config import SETTINGS
        from soe2.plan_page import GamePlanPage
        self.F = F
        self._old = SETTINGS.get("focus")
        SETTINGS["focus"] = {}
        self._p = mock.patch.object(F, "save", lambda: None)
        self._p.start()
        s = self.s = GamePlanPage.__new__(GamePlanPage)
        s.root, s.gp_overlay, s.shell = self.root, mock.Mock(), mock.Mock()
        s.focus_test = s.focus_history = lambda: None
        self.a, self.b, self.c = F.add_goal("First goal"), F.add_goal("Second goal"), F.add_goal(kind="level",
                                                                                                  target=90)
        s.build_game_plan(self.frame()).pack()

    def tearDown(self):
        from soe2.config import SETTINGS
        self._p.stop()
        if self._old is None:
            SETTINGS.pop("focus", None)
        else:
            SETTINGS["focus"] = self._old

    def all_widgets(self):
        out = []

        def walk(w):
            out.append(w)
            for k in w.winfo_children():
                walk(k)
        walk(self.s.gp_goal_box), walk(self.s.gp_next_box)
        return out

    def test_a_tick_changes_marks_not_rows(self):
        s, F = self.s, self.F
        before = self.all_widgets()
        s.gp_goal_done(self.a["id"], True)
        self.assertEqual(self.all_widgets(), before, "no widget made or destroyed")
        self.assertEqual(s._gp_done_lbl.cget("text"), "1 of 3 done")
        rows = s._gp_rows
        self.assertEqual(rows[self.a["id"]]["num"].cget("text"), "✓")
        self.assertEqual(rows[self.a["id"]]["tick"].cget("text"), "☑ Done", "a mark and a word")
        self.assertFalse(rows[self.a["id"]]["chip"].winfo_manager())
        self.assertTrue(rows[self.b["id"]]["chip"].winfo_manager(), "Next up moved on")
        self.assertEqual(s._gp_nx["text"].cget("text"), "Second goal")
        s.gp_goal_done(self.a["id"], False)
        self.assertEqual(self.all_widgets(), before)

    def test_a_move_and_a_skip_keep_the_rows(self):
        s, F = self.s, self.F
        before = self.all_widgets()
        F.move_goal(self.c["id"], -1)
        s.gp_fill()
        self.assertEqual(set(self.all_widgets()), set(before))
        self.assertEqual(s.gp_goal_box.pack_slaves(),
                         [s._gp_rows[g["id"]]["frame"] for g in F.cfg()["goals"]], "the same rows, re-ordered")
        self.assertEqual(s._gp_rows[self.c["id"]]["num"].cget("text"), "2")
        s.gp_skip(self.a["id"])
        self.assertEqual(set(self.all_widgets()), set(before))
        self.assertEqual(s._gp_nx["text"].cget("text"), "Level 90")

    def test_a_new_count_changes_words_in_place(self):
        s, F = self.s, self.F
        before = self.all_widgets()
        lbl = s._gp_rows[self.c["id"]]["meta"]
        F.state()["levels"], F.state()["last_char"] = {"Me": 74}, "Me"
        s.gp_fill()
        self.assertEqual(lbl.cget("text"), "Level 74 of 90 · from the game's log")
        self.assertEqual(self.all_widgets(), before)

    def test_add_and_remove_touch_one_row(self):
        s, F = self.s, self.F
        keep = {g: s._gp_rows[g]["frame"] for g in (self.a["id"], self.c["id"])}
        d = F.add_goal("Fourth goal")
        s.gp_fill()
        self.assertEqual(len(s._gp_rows), 4)
        F.remove_goal(self.b["id"])
        F.remove_goal(d["id"])
        s.gp_fill()
        self.assertEqual({g: r["frame"] for g, r in s._gp_rows.items()}, keep, "the other rows are the same widgets")
        self.assertTrue(all(f.winfo_exists() for f in keep.values()))

    def test_the_same_plan_is_not_drawn_again(self):
        s = self.s
        lbl = s._gp_done_lbl
        lbl.config = mock.Mock(side_effect=AssertionError("drawn again"))
        s.gp_fill()


class Overlay2(Tk):
    def test_focus_line_changes_where_it_is(self):
        from soe2.ovparts import OverlayParts
        top = self.frame()
        cv = tk.Canvas(top, width=300, height=30)
        cv.pack()
        s = OverlayParts.__new__(OverlayParts)
        s.gb_cv, s.mg_win, s.goal_rows = cv, object(), ["focus"]
        P = {"cell_bg": "#111111", "line": "#222222", "on": "#33ff33"}
        s._gb_focus = dict(cv=cv, mid=15, rgt=290, pw=56, P=P)
        OverlayParts._focus_prog(cv, 15, 290, 56, P, 0.2)
        before = len(cv.find_withtag("focusprog"))
        words = []
        s.tk_ov_lbls = {"focus": types.SimpleNamespace(config=lambda text="": words.append(text))}
        s.goalbar_rows = lambda: ["focus"]
        s.focus_line = lambda: ("Kill the boss", 0.6)
        self.assertTrue(s.focus_redraw())
        self.assertEqual(words, ["Kill the boss"])
        self.assertEqual(len(cv.find_withtag("focusprog")), before)
        s.focus_line = lambda: ("Kill the boss", None)       # the progress bar goes: the lines must be built again
        self.assertFalse(s.focus_redraw())
        s.focus_line = lambda: ("", None)
        s.goalbar_rows = lambda: []                           # the line goes
        self.assertFalse(s.focus_redraw())


class Search(Tk):
    def test_search_categories_keep_their_rows(self):
        from soe2.search_page import SearchPage
        top = self.frame()
        s = SearchPage.__new__(SearchPage)
        s.gs_chips = tk.Frame(top)
        s.gs_chips.pack()
        s.gs_active = None
        s.gs_pick = lambda g: None
        s._gs_chips({"Weapons": 3, "Armour": 0}, 3, ["Weapons", "Armour"])
        rows = list(s.gs_chips.winfo_children())
        self.assertEqual(len(rows), 3)
        s.gs_active = "Weapons"                               # a category picked
        s._gs_chips({"Weapons": 5, "Armour": 2}, 7, ["Weapons", "Armour"])
        self.assertEqual(list(s.gs_chips.winfo_children()), rows)
        self.assertEqual(rows[1].winfo_children()[1].cget("text"), "Weapons")
        self.assertEqual(str(rows[1].winfo_children()[1].cget("font")).split()[-1], "bold")     # a word, not color alone
        self.assertEqual(rows[1].winfo_children()[2].cget("text"), "5")
        s._gs_chips({"Weapons": 5}, 5, ["Weapons"])           # a category went: built again
        self.assertNotEqual(list(s.gs_chips.winfo_children()), rows)


if __name__ == "__main__":
    unittest.main()
