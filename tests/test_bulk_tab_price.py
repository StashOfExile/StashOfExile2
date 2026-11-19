"""Bulk Pricing, Add from stash tab: each tab owns its price (typed amount and picked currency are saved to the shown
tab at once, a tab shows its own price, a new tab starts empty); the shown tab's chip and its box are one shape; the
chips carry the tab's price; the account mark is one for every tab, at the strip's right end (not in the tab's box),
and the name is never shown.

    python3.12 -m unittest tests.test_bulk_tab_price          (or tests/runall.sh)"""
import os
import sys
import time
import tkinter as tk
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_bulk_layout as BL                             # noqa: E402  (sets HOME)
from soe2.config import SETTINGS                          # noqa: E402

class TabPrice(unittest.TestCase):
    setUpClass = classmethod(BL.Layout.setUpClass.__func__)
    _tear = BL.Layout.tearDownClass.__func__

    @classmethod
    def tearDownClass(cls):
        SETTINGS.pop("pctab", None)                       # (a later test's page starts from Manually Add)
        cls._tear(cls)

    setUp, tearDown, size, pump, walk = BL.Layout.setUp, BL.Layout.tearDown, BL.Layout.size, BL.Layout.pump, BL.Layout.walk

    def stash(self):
        self.app.pc_mode.pick("Add from stash tab")
        self.pump()

    def tab(self, tid):
        return next(t for t in SETTINGS["pctab"]["tabs"] if t["id"] == tid)

    def type_amount(self, text):
        self.app.pc_amt_box.focus_force()
        self.app.pc_amt.set(text)
        self.pump()
        self.app.pctab_price_flush()

    def test_typed_amount_is_saved_to_the_shown_tab(self):
        self.stash()
        self.app.pctab_pick("Tab 2")
        self.type_amount("37882")
        self.assertEqual(self.tab("t2")["amount"], 37882)
        self.assertEqual(self.tab("t1")["amount"], 62555, "the other tab keeps its price")
        self.assertNotIn("amount", SETTINGS["pctab"], "no global price")

    def test_amount_is_saved_after_a_pause_without_leaving_the_box(self):
        self.stash()
        self.app.pc_amt.set("1500")
        self.assertNotEqual(self.tab("t1")["amount"], 1500, "not on every key")
        for _ in range(8):
            self.pump()
            time.sleep(0.1)
        self.assertEqual(self.tab("t1")["amount"], 1500)

    def test_typing_then_switching_saves_to_the_tab_it_was_typed_for(self):
        self.stash()
        self.app.pc_amt.set("999")
        self.app.pctab_pick("Tab 2")
        self.assertEqual(self.tab("t1")["amount"], 999)
        self.assertIsNone(self.tab("t2")["amount"])
        self.assertEqual(self.app.pc_amt.get(), "")

    def test_currency_is_saved_to_the_shown_tab_only(self):
        self.stash()
        self.app.pctab_pick("Tab 2")
        self.app.pc_cur.set("Chaos Orb")
        self.app.pctab_cur_picked()
        self.assertEqual(self.tab("t2")["currency"], "chaos")
        self.assertEqual(self.tab("t1")["currency"], "chaos")
        self.app.pc_cur.set("Exalted Orb")
        self.app.pctab_cur_picked()
        self.assertEqual(self.tab("t2")["currency"], "exalted")
        self.assertEqual(self.tab("t1")["currency"], "chaos", "Tab 1 keeps Chaos")
        self.assertNotIn("currency", SETTINGS["pctab"], "the old global currency is not written")

    def test_switching_shows_that_tabs_price_and_a_new_tab_is_empty(self):
        self.stash()
        self.assertEqual(self.app.pc_amt.get(), "62555")
        self.assertEqual(self.app.pc_cur.get(), "Chaos Orb")
        self.app.pctab_pick("Tab 2")
        self.assertEqual(self.app.pc_amt.get(), "")
        self.assertEqual(self.app.pc_cur.get(), "Divine Orb")
        self.app.pctab_pick("Tab 1")
        self.assertEqual(self.app.pc_amt.get(), "62555")
        self.app.pctab_new()
        self.assertEqual(self.app.pc_amt.get(), "")
        self.assertEqual(self.app.pc_cur.get(), "Divine Orb")

    def test_wealth_uses_the_shown_tabs_price(self):
        self.stash()
        self.assertEqual(self.app.pctab_current()["amount"], 62555)
        self.app.pctab_pick("Tab 2")
        self.type_amount("12")
        self.assertEqual(self.app.pctab_current()["amount"], 12)

    def test_chip_text_has_the_tabs_price(self):
        self.stash()
        self.fill(src="tab:t1", n=2)
        self.assertEqual(self.app.pc_tabs["t1"].cget("text"), "▸ Tab 1 · 2 · 62,555 c")
        self.assertEqual(self.app.pc_tabs["t2"].cget("text"), "Tab 2 · 0", "no price yet: just the count")
        self.app.pctab_pick("Tab 2")
        self.app.pc_cur.set("Divine Orb")
        self.type_amount("37882")
        self.assertEqual(self.app.pc_tabs["t2"].cget("text"), "▸ Tab 2 · 0 · 37,882 div")
        self.assertEqual(self.app.pc_tabs["t1"].cget("text"), "Tab 1 · 2 · 62,555 c", "the unshown one: no mark")

    def test_chip_updates_in_place(self):
        self.stash()
        chip, wrap = self.app.pc_tabs["t1"], self.app.pc_tab_wrap["t1"]
        self.type_amount("5")
        self.assertIs(self.app.pc_tabs["t1"], chip)
        self.assertIs(self.app.pc_tab_wrap["t1"], wrap)
        self.assertEqual(chip.cget("text"), "▸ Tab 1 · 0 · 5 c")

    fill = BL.Layout.fill

    def test_account_mark_is_in_the_strip_not_in_the_tabs_box(self):
        self.stash()
        a = self.app
        lbl = a.pc_acc_lbl
        self.assertEqual(lbl.winfo_parent(), str(a.pc_tabsrow))
        inside = {str(w) for w in self.walk(a.pc_tabrow)}
        self.assertNotIn(str(lbl), inside)
        self.assertTrue(lbl.winfo_viewable())
        strip_r = a.pc_tabsrow.winfo_rootx() + a.pc_tabsrow.winfo_width()
        self.assertGreater(lbl.winfo_rootx() + lbl.winfo_width(), strip_r - 4, "at the strip's right end")
        self.assertGreater(lbl.winfo_rootx(), a.pc_tabs["t2"].winfo_rootx())
        self.assertIn("any of your stash tabs", lbl._tip.text)
        self.assertIn("The name is hidden", lbl._tip.text)

    def test_no_account_name_anywhere(self):
        self.stash()
        self.fill(src="tab:t1")
        name = BL.ACCOUNT.split("#")[0]
        seen = []
        for w in self.walk(self.body):
            for opt in ("text",):
                try:
                    seen.append(str(w.cget(opt)))
                except tk.TclError:
                    pass
            tip = getattr(w, "_tip", None)
            if tip is not None:
                seen.append(str(tip.text))
        for tip in self.app.pc_tab_tips.values():
            seen.append(tip.text)
        self.assertTrue(any("Account set" in t for t in seen))
        self.assertFalse([t for t in seen if name in t])

    def test_shown_tab_and_its_box_are_one_shape(self):
        self.stash()
        a = self.app
        wrap = a.pc_sel_wrap
        self.assertEqual(a.pc_tabs["t1"].cget("bg"), a.pc_box_bg, "same fill as the box")
        self.assertEqual(a.pc_tabrow_row.cget("bg"), a.pc_box_bg)
        strip, box = a.pc_tabsrow, a.pc_tabrow
        self.assertEqual(strip.winfo_rooty() + strip.winfo_height(), box.winfo_rooty(), "the box is right under")
        self.assertEqual(wrap.winfo_rooty() + wrap.winfo_height(), box.winfo_rooty(), "the tab sits on the box")
        self.assertTrue(a.pc_join.winfo_ismapped(), "the outline is open under the tab")
        self.assertEqual(a.pc_join.winfo_width(), wrap.winfo_width() - 2)
        self.assertTrue(a.pc_tabs["t1"].cget("text").startswith("▸ "))
        self.assertEqual(str(a.pc_tabs["t2"].winfo_class()), "TButton", "the others stay chips")
        self.assertLess(self.app.pc_tabblock.winfo_rooty(), self.app.bk_tb.winfo_rooty(), "the toolbar is below")

    def test_drawer_width_wraps_and_keeps_everything(self):
        self.stash()
        self.app.pctab_new()
        self.app.pctab_new()
        self.size(520, 900)
        a = self.app
        right = a.pc_tabsrow.winfo_rootx() + a.pc_tabsrow.winfo_width()
        for w in list(a.pc_tab_wrap.values()) + [a.pc_add_btn, a.pc_acc_lbl]:
            self.assertTrue(w.winfo_viewable())
            self.assertLessEqual(w.winfo_rootx() + w.winfo_width(), right + 1)
        self.assertTrue(a.pc_read_btn.winfo_viewable() or a.empty_lbl.winfo_viewable())


if __name__ == "__main__":
    unittest.main()
