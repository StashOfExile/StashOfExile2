"""Bulk Pricing's layout (owner pick: mockup A in a wide window, C in the Drawer). The picked item is shown as Price
Checks shows one - the price card, the item card in the one order, the cheapest listings, Search again | Trade Site |
Add to favorites at the bottom of that column - beside the list when wide, under it when narrow; nothing picked: no
side panel, the list has the whole width. One orange button a screen (Search again, or Read tab with Read a stash
tab); the account name is never on the page; Filters · n ▾ counts the filters set. UI rule 22: a new price paints the
price card and the listings in place, and a resize lays the page out again without building the list again.

    python3.12 -m unittest tests.test_bulk_layout          (or tests/runall.sh)"""
import collections
import os
import sys
import tempfile
import time
import tkinter as tk
import types
import unittest
from tkinter import ttk
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-bulklayout-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_pricecheck_golden as GOLD                     # noqa: E402
import test_pricecheck_layout as PCL                      # noqa: E402
from soe2 import mods as M, trade as T                    # noqa: E402
from soe2.config import SETTINGS                          # noqa: E402

ACCOUNT = "SecretStreamer#4242"


def bulk_rec(name, rid, src="manual"):
    rec = PCL.rec_of(name, rid)
    rec.update(src=src, mark="new", resolved=True, time=time.time())
    return rec


def make_app(root):
    """The real App's Bulk Pricing page, without the rest of the app (no window, no threads, nothing searched)."""
    from soe2.app import App
    a = App.__new__(App)
    a.root, a.records, a.shell, a.dirty, a.next_id = root, {}, None, False, 100
    a.status_text, a.status_until, a.batch_ids = "", 0, set()
    a.pp_win, a.sort_col, a.sort_rev = None, None, False
    a.shown_rec, a._dwidth, a._dafter = None, 0, None
    a.price_var, a.detail_vars, a.seen_texts = None, [], {}
    a.engine = types.SimpleNamespace(paused=False, hold=lambda rid: None, unhold=lambda rid: None)
    a.log_error = lambda where: (_ for _ in ()).throw(AssertionError(where))
    a.favs = lambda: {}
    a._drawer_mouse_down = lambda: False
    a.reprice = lambda ids: None
    a.settings_open = lambda *x: None
    a.done_times, a.was_busy = collections.deque(maxlen=6), False
    a.append_history = lambda rec: None                    # (nothing written)
    a.value_log_save_soon = lambda: None
    return a


class Layout(unittest.TestCase):
    ORDER, OLD_NAMES = PCL.Layout.ORDER, PCL.Layout.OLD_NAMES

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        S.setup_style(cls.root)
        SETTINGS.update(league="Standard", min_results=3, range_factor=0.9, status="Instant Buyout", age="2 days",
                        pc_fold={}, pc_art=False, wealth_account=ACCOUNT, view="Not yet listed", detail_adv=False)
        if GOLD.TABLE is None:
            GOLD.TABLE = GOLD.stat_table()
            M.DUPS.clear()
            M.OPTS.clear()
            T.build_sidtext(GOLD.TABLE)
        PCL.ITEMS.update(GOLD.load_items())

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.minsize(1, 1)
        SETTINGS["pctab"] = {"mode": "Manual Add", "tabs": [{"id": "t1", "name": "Tab 1", "amount": 62555,
                                                            "currency": "chaos", "currency_name": "Chaos Orb"},
                                                           {"id": "t2", "name": "Tab 2", "amount": None,
                                                            "currency": "divine", "currency_name": "Divine Orb"}],
                             "current": "t1"}
        self.app = make_app(self.root)
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_checks(self.body)
        self.size(1400, 1000)

    def tearDown(self):
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.tk.call("after", "cancel", job)       # (a later test's widgets aren't these)

    def size(self, w, h):
        self.root.geometry(f"{w}x{h}+0+0")
        for _ in range(3):
            self.pump()
            time.sleep(0.2)                               # (the layout waits for the resize to pause: 150 ms)
        self.pump()

    def pump(self, n=8):
        for _ in range(n):
            self.root.update()

    def fill(self, src="manual", n=3):
        names = ("rare_gloves_quality_sockets", "rare_amulet_fractured", "rare_gloves_quality_sockets")
        for i in range(1, n + 1):
            self.app.records[i] = bulk_rec(names[(i - 1) % len(names)], i, src)
        self.app.rebuild_tree()
        self.pump()

    def pick(self, rid=1):
        self.app.tree.selection_set(str(rid))
        self.pump()
        time.sleep(0.3)
        self.pump()
        return self.app.records[rid]

    def walk(self, w):
        yield w
        for c in w.winfo_children():
            yield from self.walk(c)

    def oranges(self):
        from soe2.style import C
        ws = [w for w in self.walk(self.body) if w.winfo_viewable()]
        btns = [w for w in ws if isinstance(w, ttk.Button) and "Primary" in str(w.cget("style"))]
        filled = [w for w in ws if isinstance(w, (tk.Label, tk.Frame, tk.Button)) and
                  str(w.cget("bg")).lower() in {C["accent"].lower(), C["orange"].lower()}]
        return btns, filled

    def heads(self, cv):
        items = sorted(cv.find_withtag("cardsec"), key=lambda i: cv.coords(i)[1])
        return [cv.itemcget(i, "text").lstrip("▾▸ ") for i in items]

    # ---- one orange button a screen
    def test_one_orange_with_an_item_picked(self):
        self.fill()
        self.pick()
        btns, filled = self.oranges()
        self.assertEqual([b.cget("text") for b in btns], [self.app.bk_search_btn.cget("text")])
        self.assertIs(btns[0], self.app.bk_search_btn)
        self.assertEqual(filled, [], "nothing else is orange-filled")
        self.assertNotIn("Primary", str(self.app.reprice_all_btn.cget("style")), "Re-price all is secondary")

    def test_one_orange_on_an_empty_stash_tab(self):
        self.app.pc_mode.pick("Add from stash tab")
        self.app.pctab_pick("Tab 2")
        self.pump()
        e = self.app.empty_lbl
        self.assertTrue(e.winfo_viewable())
        self.assertEqual(e.title_lbl.cget("text"), "Tab 2 is empty")
        btns, filled = self.oranges()
        self.assertEqual(len(btns), 1, [b.cget("text") for b in btns])
        self.assertIs(btns[0], e.btn)
        self.assertEqual(btns[0].cget("text"), "Read tab")
        self.assertFalse(self.app.pc_read_btn.winfo_viewable(), "the stash row's Read tab waits")
        self.assertEqual(filled, [])

    def test_one_orange_on_a_stash_tab_with_an_item_picked(self):
        self.app.pc_mode.pick("Add from stash tab")
        self.pump()
        self.fill(src="tab:t1")
        self.pick()
        btns, _filled = self.oranges()
        self.assertEqual(btns, [self.app.pc_read_btn], "Read tab - Search again is secondary while the row shows")

    def test_source_switch_is_plain_with_a_mark(self):
        sw = self.app.pc_mode
        self.assertTrue(sw.plain)
        self.assertTrue(sw.btns[sw.get()][0].cget("text").startswith("✓ "))
        self.assertEqual(set(sw.btns), {"Manually Add", "Add from stash tab"})

    # ---- privacy
    def test_account_name_never_shown(self):
        self.app.pc_mode.pick("Add from stash tab")
        self.pump()
        self.fill(src="tab:t1")
        self.pick()
        seen = []
        for w in self.walk(self.body):
            try:
                seen.append(str(w.cget("text")))
            except tk.TclError:
                pass
            tip = getattr(w, "_tip", None)
            if tip is not None:
                seen.append(str(tip.text))
        self.assertTrue(any("Account set" in t for t in seen))
        name = ACCOUNT.split("#")[0]
        self.assertFalse([t for t in seen if name in t], "the account name is on the page")
        self.assertIn("hidden", self.app.pc_acc_lbl._tip.text)

    # ---- the layout
    def test_item_beside_the_list_when_wide_and_under_it_when_narrow(self):
        self.fill()
        self.pick()
        sp = self.app.bk_split
        self.assertTrue(self.app.bk_layout_wide())
        lst, side = sp.left, sp.right
        self.assertTrue(side.winfo_viewable())
        self.assertGreaterEqual(side.winfo_rootx(), lst.winfo_rootx() + lst.winfo_width(), "beside the list")
        with mock.patch.object(self.app, "rebuild_tree", side_effect=AssertionError("the list was built again")), \
                mock.patch.object(self.app.tree, "insert", side_effect=AssertionError("a row was added")), \
                mock.patch.object(self.app.tree, "delete", side_effect=AssertionError("a row was removed")):
            kids = list(self.app.tree.get_children())
            self.size(700, 1000)
            self.assertFalse(self.app.bk_layout_wide())
            self.assertGreaterEqual(side.winfo_rooty(), lst.winfo_rooty() + lst.winfo_height(), "under the list")
            self.assertGreater(side.winfo_width(), 600 - 100, "one column, the whole width")
            self.size(1400, 1000)
            self.assertTrue(self.app.bk_layout_wide())
            self.assertEqual(list(self.app.tree.get_children()), kids)
        self.assertGreaterEqual(side.winfo_rootx(), lst.winfo_rootx() + lst.winfo_width())

    def test_price_and_buttons_in_the_items_column(self):
        self.fill()
        self.pick()
        col = self.app.bk_split.right
        for w in (self.app.bk_price.frame, self.app.bk_foot):
            self.assertIs(w.master, col)
        self.assertEqual(self.app.bk_foot.winfo_width(), col.winfo_width())
        p, card, foot = self.app.bk_price.frame, self.app.bk_cardbox, self.app.bk_foot
        # owner (round 2): the price box has the card's box's left and right edges (not over the scroll bar)
        self.assertEqual(p.winfo_rootx(), card.winfo_rootx())
        self.assertEqual(p.winfo_rootx() + p.winfo_width(), card.winfo_rootx() + card.winfo_width())
        self.assertLessEqual(p.winfo_rooty() + p.winfo_height(), card.winfo_rooty(), "the price on top")
        self.assertEqual(foot.winfo_rooty() + foot.winfo_height(), col.winfo_rooty() + col.winfo_height())

    def test_side_always_there_first_row_picked(self):
        sp = self.app.bk_split
        self.assertTrue(sp.right.winfo_ismapped(), "the item side shows with an empty list too")
        e = self.app.bk_none
        self.assertTrue(e.winfo_viewable(), "nothing picked: what it is")
        self.assertEqual(str(e.btn.cget("state")), "disabled", "Show the first item waits for a row")
        for b in (self.app.bk_search_btn, self.app.bk_trade_btn, self.app.bk_fav_btn):
            self.assertEqual(str(b.cget("state")), "disabled", "a button that needs a pick is greyed out")
        self.fill()
        self.pump()
        time.sleep(0.2)
        self.pump()
        self.assertEqual(self.app.tree.selection(), ("1",), "the first row is picked by itself")
        self.assertIs(self.app.shown_rec, self.app.records[1])
        self.assertFalse(e.winfo_ismapped())
        self.assertTrue(self.app.bk_price.frame.winfo_viewable())
        self.app.tree.selection_set(())
        self.pump()
        time.sleep(0.2)
        self.pump()
        self.assertTrue(sp.right.winfo_ismapped(), "no pick: the side stays")
        self.assertTrue(e.winfo_viewable())
        self.assertEqual(str(e.btn.cget("state")), "normal")
        self.assertNotIn("Primary", str(e.btn.cget("style")), "one orange button a screen")
        e.btn.invoke()
        self.pump()
        time.sleep(0.2)
        self.pump()
        self.assertIs(self.app.shown_rec, self.app.records[1])

    def test_picked_item_is_smaller_than_price_checks(self):
        from soe2 import cardscale
        self.fill()
        self.pick()
        cv = self.app.detail_card
        self.assertEqual(cardscale.BULK, 0.9, "owner (round 2): 0.8 was too small to read")
        self.assertEqual(cv._k, cardscale.BULK, "never smaller: a long card scrolls")
        self.assertEqual(self.app.bk_price.k, cardscale.BULK)
        self.assertLessEqual(self.app.bk_split.right.winfo_width(), 0.9 * 520 + 40, "about 10% narrower")
        self.assertGreaterEqual(self.app.bk_split.right.winfo_width(), 0.9 * 520 - 40)
        import tkinter.font as tkf
        sizes = {abs(int(tkf.Font(font=cv.itemcget(i, "font")).actual("size"))) for i in cv.find_all()
                 if cv.type(i) == "text" and cv.itemcget(i, "font")}
        self.assertGreaterEqual(min(sizes), 8, sizes)         # (the 8 pt tier tags stay as they are)
        texts = [i for i in cv.find_all() if cv.type(i) == "text" and cv.itemcget(i, "text").startswith("Item level")]
        for i in texts:                                    # (a 10 pt row: 9 at 0.9 - the normal small size, not less)
            self.assertGreaterEqual(abs(int(tkf.Font(font=cv.itemcget(i, "font")).actual("size"))), cardscale.MIN_PT)
        foot = self.app.bk_foot_row                        # Search again | Trade Site | Add to favorites: one row
        ys = {b.winfo_y() for b in (self.app.bk_search_btn, self.app.bk_trade_btn, self.app.bk_fav_btn)}
        self.assertEqual(len(ys), 1, "the footer's buttons on one row")
        self.assertTrue(foot.winfo_ismapped())

    def test_side_width_migration(self):
        """Once: a side made 0.8 narrower (round 1) gets 0.9 back, and is ITEM_W at least."""
        from soe2 import bulk_page as BP
        self.addCleanup(SETTINGS.update, panel_w=BP.ITEM_W, bk_side_k=True, bk_side_k2=True)
        for had, k1, want in ((344, True, BP.ITEM_W), (600, True, int(600 * 0.9 / 0.8)), (430, False, BP.ITEM_W),
                              (700, False, 700)):
            SETTINGS.update(panel_w=had, bk_side_k=k1, bk_side_k2=False)
            for w in self.root.winfo_children():
                w.destroy()
            app = make_app(self.root)
            body = tk.Frame(self.root)
            body.pack(fill="both", expand=True)
            app.build_checks(body)
            self.assertEqual(SETTINGS["panel_w"], want, (had, k1))
            self.assertTrue(SETTINGS["bk_side_k2"])
            make_app(self.root).build_checks(tk.Frame(self.root))     # (only once)
            self.assertEqual(SETTINGS["panel_w"], want)

    def test_tabs_named_by_place(self):
        tabs = SETTINGS["pctab"]["tabs"]
        tabs.append({"id": "t3", "name": "Maps", "amount": None, "currency": "divine"})
        tabs.append({"id": "t4", "name": "Tab 7", "amount": None, "currency": "divine"})
        names = lambda: [t["name"] for t in self.app.pctab_tabs()]          # noqa: E731
        self.assertEqual(names(), ["Tab 1", "Tab 2", "Maps", "Tab 4"],
                         "a saved tab never renamed is named by its place; a name of its own stays")
        self.app.pctab_new()
        self.assertEqual(names()[-1], "Tab 5")
        self.app.pctab_delete("t1")
        self.assertEqual(names(), ["Tab 1", "Maps", "Tab 3", "Tab 4"], "Tab 1 closed: the next one is Tab 1 now")
        self.assertEqual(self.app.pctab_tabs()[0]["id"], "t2")
        self.assertIn("Tab 1 · ", self.app.pc_tabs["t2"].cget("text"))
        with mock.patch("tkinter.simpledialog.askstring", return_value="Jewels"):
            self.app.pctab_rename("t2")
        self.app.pctab_delete("t3")
        self.assertEqual(names(), ["Jewels", "Tab 2", "Tab 3"], "a renamed tab keeps its name")
        with mock.patch("tkinter.simpledialog.askstring", return_value="Tab 9"):
            self.app.pctab_rename("t4")
        self.assertEqual(names(), ["Jewels", "Tab 2", "Tab 3"], "a name like Tab 9 is its place's name")

    def test_the_card_has_price_checks_look_and_order(self):
        self.fill()
        self.pick()
        cv = self.app.detail_card
        self.assertEqual(getattr(cv, "_look", ""), "drawer")
        PCL.Layout.assert_order(self, self.heads(cv))
        self.assertIn("cardbase", cv._soe_ticks, "drag-to-tick on every box")
        self.assertTrue([t for t in cv._soe_ticks if t.startswith("cardrow")])

    def test_item_flags_are_plain_rows(self):
        self.fill()
        rec = self.pick(2)
        PCL.Layout.flags_check(self, self.app.detail_card, rec)

    def card(self):
        return self.app.detail_card

    # ---- UI rule 22
    def test_new_price_paints_in_place(self):
        self.fill()
        rec = self.pick()
        cv = self.app.detail_card
        h = self.app.bk_price.frame.winfo_height()
        from soe2 import app as A
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("the card was built again")), \
                mock.patch.object(self.app, "rebuild_tree", side_effect=AssertionError("the list was built again")), \
                mock.patch.object(A.VALUE_LOG, "add", return_value=False):
            rec["state"] = "pricing"
            self.app.ev_priced(rec["id"])
            self.pump()
            self.assertIn("Searching", self.app.bk_price.big.cget("text"))
            self.assertEqual(self.app.bk_price.frame.winfo_height(), h)
            rec.update(state="done", est=7.5)
            self.app.ev_priced(rec["id"])
            self.pump()
        self.assertIs(self.app.detail_card, cv)
        self.assertTrue(cv.winfo_exists())
        self.assertIn("7.5", self.app.bk_price.big.cget("text"))
        self.assertTrue(self.app.bk_price.how.cget("text").startswith("~ "), "how sure: a mark and a word")
        self.assertIn("CHEAPEST LISTINGS", self.app.bk_count.cget("text"))
        row = self.app.tree.item(str(rec["id"]), "values")
        self.assertTrue(str(row[1]).startswith("▸ "), "the picked row is marked")
        self.assertEqual(row[3], "✓ Priced")

    def test_tick_paints_in_place(self):
        self.fill()
        rec = self.pick()
        cv = self.app.detail_card
        v = self.app.bulkv
        idx, (m, _on, _rect) = next((i, r) for i, r in sorted(v.card_rows.items()) if r[1] and r[0].get("sid")
                                    and r[0].get("kind") != "Total")
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("the card was built again")):
            self.app.card_toggle(rec, m, False)
            self.pump()
        self.assertIs(self.app.detail_card, cv)
        self.assertFalse(v.card_rows[idx][1])

    # ---- the toolbar
    def test_search_first_and_filters_count(self):
        tb = self.app.bk_tb
        first = tb._flow_lefts[0]["w"]
        self.assertIn(self.app.search_box, list(self.walk(first)), "the search box is first, top left")
        self.fill()
        self.assertEqual(self.app.bk_filt_btn.cget("text"), "Filters · 0 ▾")
        self.app.bk_filters_toggle(True)
        self.pump()
        self.assertTrue(self.app.cat_box.winfo_viewable())
        vals = list(self.app.cat_box["values"])
        self.app.cat_var.set(vals[1])
        self.app.on_cat("cat")
        self.pump()
        self.assertEqual(self.app.bk_filt_btn.cget("text"), "Filters · 1 ▾")
        self.app.cat_reset()
        self.pump()
        self.assertEqual(self.app.bk_filt_btn.cget("text"), "Filters · 0 ▾")
        self.app.bk_filters_toggle(False)
        self.pump()
        self.assertFalse(self.app.bk_filt_pop.winfo_ismapped())

    def test_status_and_confidence_have_a_mark_and_a_word(self):
        self.fill()
        r = self.app.records[2]
        r.update(state="done", nomatch=True, est=None)
        self.app.update_row(2)
        r3 = self.app.records[3]
        r3.update(state="error", label="The trade site didn't answer")
        self.app.update_row(3)
        vals = {i: self.app.tree.item(str(i), "values") for i in (1, 2, 3)}
        self.assertEqual(vals[1][3], "✓ Priced")
        self.assertEqual(vals[1][5], "~ Medium")
        self.assertEqual(vals[2][3], "– No listings")
        self.assertEqual(vals[3][3], "✗ Error")
        self.assertIn("worth", self.app.bk_worth_lbl.cget("text"))
        self.assertTrue(self.app.bk_worth_val.cget("text").startswith("≈ "))
        self.assertIn("sum", self.app.bk_worth_tip.text)


if __name__ == "__main__":
    unittest.main()
