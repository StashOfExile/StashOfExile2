"""3.0.1 (owner: "the Min / Max boxes on the price check overlay don't take typing"): every Min / Max box on the card
over the game takes the keyboard when clicked - the item's own boxes (item level, quality, sockets) never asked for
it, only the mods' did; on Windows the card's window is made one that can have the keyboard and put in front
(overlaywin.take_keyboard: no-activate / click-through off). A gray box ticks its row and gets the cursor. A redraw
keeps the box you're in; the card waits only while you type (after Enter it shows what was found). Closing the card
hands the keyboard back to the game.

    python3.12 -m unittest tests.test_pcpop_typing          (or tests/runall.sh)"""
import os
import queue
import sys
import tempfile
import tkinter as tk
import types
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-pctype-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_pricecheck_golden as GOLD                     # noqa: E402
from soe2 import engine as EN, gear as G, mods as M, trade as T    # noqa: E402
from soe2 import overlaywin as OW                         # noqa: E402
from soe2.config import SETTINGS                          # noqa: E402
from soe2.pcpop import PricePopup                         # noqa: E402
from soe2.searchopts_page import SearchOptsPage           # noqa: E402

ITEMS = {}


def rec_of(name):
    """A price check of a fixture item, resolved offline (its mods have their trade ids), searched."""
    it = G.parse_gear(ITEMS[name])
    rec = {"id": 1, "item": it, "src": "pc", "ov": {}, "opts": None, "raw": ITEMS[name]}
    eng = EN.Engine({1: rec}, queue.Queue())
    eng.table = GOLD.TABLE
    with mock.patch.object(EN, "MARKET", GOLD._Market()):
        eng.resolve_rec(rec)
    rec["state"] = "done"
    return rec


class Pop(PricePopup, SearchOptsPage):
    """The card over the game with just enough of the app around it."""

    def __init__(self, root, rec):
        from soe2.app import App
        self._card_has_vals = types.MethodType(App._card_has_vals, self)
        self._card_misc_keys = App._card_misc_keys
        self.root, self.records, self.pp_open, self.ticked, self.calls = root, {rec["id"]: rec}, set(), None, []

    def pc_entries(self, rec):
        return [], 0, 0

    def pc_ticked(self, rec):
        mods = [m for m in rec["item"]["mods"] if m.get("sid")]
        return mods if self.ticked is None else [m for m in mods if id(m) in self.ticked]

    def toggle_mod(self, rec, m, on):
        if self.ticked is None:
            self.ticked = {id(x) for x in rec["item"]["mods"] if x.get("sid") and T.mod_impact(rec, x) != "ignore"}
        (self.ticked.add if on else self.ticked.discard)(id(m))

    def card_changed(self, rec):
        pass

    def reprice(self, ids):
        self.calls.append(("reprice", list(ids)))

    def pc_search_go(self, rec):
        self.calls.append(("search", rec["id"]))

    def pc_open_trade(self):
        pass

    def log_error(self, what):
        raise AssertionError(what)


class Typing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("no display")
        cls.root.withdraw()
        from soe2 import style as S, themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        SETTINGS.update(league="Standard", min_results=3, range_factor=0.9, status="Instant Buyout", age="2 days")
        if GOLD.TABLE is None:
            GOLD.TABLE = GOLD.stat_table()
            M.DUPS.clear()
            M.OPTS.clear()
            T.build_sidtext(GOLD.TABLE)
        ITEMS.update(GOLD.load_items())

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def card(self, name):
        rec = rec_of(name)
        p = Pop(self.root, rec)
        p.pcpop_show(rec)
        self.root.update()
        took = []
        p.pp_win.take_keyboard = lambda w=None: (took.append(w), w.focus_force(), None)[-1]   # (no Windows here)
        self.addCleanup(lambda: p.pp_win is not None and p.pcpop_close())
        return p, rec, took

    def click(self, e):
        e.event_generate("<Button-1>", x=4, y=4)
        self.root.update()

    def type_(self, p, e, text):
        for ch in text:
            e.event_generate("<KeyPress>", keysym=ch)
            e.event_generate("<KeyRelease>", keysym=ch)
        self.root.update()

    def test_every_box_takes_the_keyboard(self):
        for name in ("rare_ring", "normal_body_armour_base"):
            p, rec, took = self.card(name)
            kinds = {b[0] for b in p.pp_boxes}
            self.assertEqual(kinds, {"mod", "prop"}, name)              # (both kinds on these items)
            for box_id, e in list(p.pp_boxes.items()):
                if str(e.cget("state")) == "disabled":
                    continue
                self.click(e)
                self.assertIs(took[-1], e, f"{name} {box_id}: the click asked for the keyboard")
                self.assertIs(p.root.focus_get(), e, f"{name} {box_id}: the box has the keyboard")
            p.pcpop_close()

    def test_typed_value_is_searched_on_enter(self):
        p, rec, _took = self.card("normal_body_armour_base")
        e = p.pp_boxes[("prop", "ilvl", "min")]
        self.click(e)
        e.delete(0, "end")
        self.type_(p, e, "75")
        self.assertEqual(e.get(), "75")
        self.assertEqual(rec["opts"]["ilvl"]["min"], 75)
        e.event_generate("<Return>")
        self.root.update()
        self.assertEqual(p.calls[-1], ("reprice", [rec["id"]]))

    def test_gray_box_ticks_its_row(self):
        p, rec, took = self.card("normal_body_armour_base")
        gray = [b for b, e in p.pp_boxes.items() if str(e.cget("state")) == "disabled"]
        self.assertTrue(gray, "a gray box (quality not searched)")
        self.click(p.pp_boxes[gray[0]])
        e = p.pp_boxes[gray[0]]
        self.assertEqual(str(e.cget("state")), "normal", "its row is ticked now")
        self.assertIs(p.root.focus_get(), e, "the cursor is in the new box")
        self.assertIs(took[-1], e)

    def test_redraw_keeps_the_box_and_waits_only_while_typing(self):
        p, rec, _took = self.card("rare_ring")
        box_id = next(b for b, e in p.pp_boxes.items() if b[0] == "mod" and b[2] == "min" and e.get()
                      and str(e.cget("state")) == "normal")
        e = p.pp_boxes[box_id]
        typed = e.get()
        self.click(e)
        e.delete(0, "end")
        self.type_(p, e, typed)                               # (retyped: a Min the search takes)
        fills = []
        real = p.pcpop_fill
        p.pcpop_fill = lambda r: (fills.append(1), real(r))
        p.pcpop_refresh(rec)                                  # (a search result came while you type)
        self.root.after(150)
        self.root.update()
        self.assertEqual(fills, [], "never drawn again under your typing")
        e.event_generate("<Return>")                          # Enter: searched - the card may show what it found
        self.root.after(500)
        self.root.update()
        self.assertTrue(fills, "after Enter the waiting redraw ran")
        new = p.pp_boxes[box_id]
        self.assertIsNot(new, e, "(drawn again)")
        self.assertIs(p.root.focus_get(), new, "the same box has the keyboard after the redraw")
        self.assertEqual(new.get(), typed, "with what you typed")
        fills.clear()
        p.pcpop_refresh(rec)                                  # the result after that: not held back either
        self.root.after(150)
        self.root.update()
        self.assertTrue(fills, "a box that only keeps the keyboard doesn't hold the card back")

    def test_search_again_clears_typing(self):
        p, rec, _took = self.card("rare_ring")
        p._pp_typed = True
        p._pcpop_go(rec)
        self.assertFalse(p._pp_typed)
        self.assertEqual(p.calls[-1], ("search", rec["id"]))

    def test_close_hands_the_keyboard_back(self):
        p, rec, _took = self.card("rare_ring")
        p.pp_win.take_keyboard = lambda w=None: 4242            # (the game had it)
        e = next(e for e in p.pp_boxes.values() if str(e.cget("state")) == "normal")
        self.click(e)
        back = []
        p.pp_win.give_keyboard_back = back.append
        p.pcpop_close()
        self.assertEqual(back, [4242])

    def test_close_hands_back_to_the_game_it_opened_over(self):
        p, rec, _took = self.card("rare_ring")             # (the click gave the card the keyboard by itself)
        p._pp_game = 777                                    # (the game was in front as the card opened)
        e = next(e for e in p.pp_boxes.values() if str(e.cget("state")) == "normal")
        self.click(e)
        back = []
        p.pp_win.give_keyboard_back = back.append
        p.pcpop_close()
        self.assertEqual(back, [777])

    def test_no_typing_no_hand_back(self):
        p, rec, _took = self.card("rare_ring")
        p._pp_game = 777
        back = []
        p.pp_win.give_keyboard_back = back.append
        p.pcpop_close()
        self.assertEqual(back, [], "the card never took the keyboard: nothing to hand back")


class WindowsKeyboard(unittest.TestCase):
    """overlaywin.take_keyboard on Windows (faked): no-activate and click-through come off, the window is put in
    front, and the game's window is what give_keyboard_back hands it to."""

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

    def test_take_and_give_back(self):
        from soe2 import drawer as D, layered as L
        w = OW.OverlayWindow(self.root, "Price check", "⚖", (10, 10, 300, 200), no_activate=True)
        self.addCleanup(w.destroy)
        style = {"ex": OW.NOACTIVATE | L.WS_EX_TRANSPARENT | L.WS_EX_LAYERED}
        fg = [555]
        front = []
        u = types.SimpleNamespace(GetParent=lambda h: 100, GetWindowLongW=lambda h, i: style["ex"],
                                  SetWindowLongW=lambda h, i, v: style.update(ex=v))
        du = types.SimpleNamespace(GetForegroundWindow=lambda: fg[0],
                                   SetForegroundWindow=lambda h: (front.append(h), fg.__setitem__(0, h)))
        pids = {555: -1, 100: os.getpid()}
        with mock.patch.object(OW, "sys", types.SimpleNamespace(platform="win32")), \
                mock.patch.object(L, "user32", lambda: u), mock.patch.object(D, "_user32", lambda: du), \
                mock.patch.object(D, "_pid_of", lambda h: pids.get(h, -1)), \
                mock.patch.object(D, "set_foreground", lambda h: front.append(("back", h))):
            self.assertEqual(OW.foreign_foreground(), 555, "the game in front as the card opens")
            before = w.take_keyboard()
            self.assertIsNone(OW.foreign_foreground(), "the card (the app's own) is in front now")
            self.assertEqual(before, 555, "the game had the keyboard")
            self.assertFalse(style["ex"] & OW.NOACTIVATE, "no-activate is off")
            self.assertFalse(style["ex"] & L.WS_EX_TRANSPARENT, "click-through is off")
            self.assertTrue(style["ex"] & L.WS_EX_LAYERED, "(the rest of its style stays)")
            self.assertEqual(front, [100], "the card's window is put in front")
            self.assertFalse(w.no_activate)
            self.assertTrue(w.give_keyboard_back(before))
            self.assertEqual(front[-1], ("back", 555), "closing: the game gets it back")
            fg[0] = 555                                        # you clicked the game meanwhile: nothing to hand back
            self.assertFalse(w.give_keyboard_back(before))


if __name__ == "__main__":
    unittest.main()
