"""Price Checks' layout (owner pick, mockup C): the page header's plain switch, a search box before the recent
checks, the price card first, then the item card - Base and Properties above Mods - and the cheapest listings as a
table: beside the card in a wide window, under it in a narrow one (the Drawer). Search again stays the page's one
orange button, at the bottom. UI rule 22: a tick (and a new price) paints in place - the card is not built again -
and drag-to-tick still crosses every box (base type, item level, quality, sockets, mods, Fractured only).

    python3.12 -m unittest tests.test_pricecheck_layout          (or tests/runall.sh)"""
import os
import queue
import sys
import tempfile
import time
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-pclayout-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_pricecheck_golden as GOLD                     # noqa: E402
from soe2 import engine as EN, gear as G, mods as M, trade as T    # noqa: E402
from soe2.config import SETTINGS                          # noqa: E402

ITEMS = {}


def rec_of(name, rid):
    """A price check of a fixture item, resolved offline, priced, with six listings."""
    it = G.parse_gear(ITEMS[name])
    rec = {"id": rid, "item": it, "src": "pc", "ov": {}, "opts": None, "raw": ITEMS[name], "time": time.time() - rid,
           "state": "queued", "label": "", "est": None, "total": None, "conf": "-"}
    eng = EN.Engine({rid: rec}, queue.Queue())
    eng.table = GOLD.TABLE
    with mock.patch.object(EN, "MARKET", GOLD._Market()):
        eng.resolve_rec(rec)
    ids = []
    for i in range(6):
        lid = f"L{rid}_{i}"
        T.RAW_LISTINGS[lid] = {"id": lid, "item": {
            "name": "Thing", "typeLine": it.get("base") or "", "baseType": it.get("base") or "", "rarity": "Rare",
            "ilvl": 80 + i, "identified": True, "properties": [],
            "explicitMods": [m["text"] for m in it["mods"] if m.get("kind") not in ("Implicit", "Total")][:3]},
            "listing": {"price": {"amount": 3 + i, "currency": "divine"}, "indexed": "2026-11-18T10:00:00Z",
                        "account": {"name": f"seller{i}"}}}
        ids.append(lid)
    rec.update(state="done", est=4.5, conf="medium", total=37, prices=[(3 + i, "divine") for i in range(5)],
               qid=f"q{rid}", stages=[{"qid": f"q{rid}", "ids": ids, "total": 37}], priced_at=time.time() - 300)
    return rec


def make_app(root):
    """The real App's Price Checks page and item card, without the rest of the app (no window, no threads)."""
    from soe2.app import App
    a = App.__new__(App)
    a.root, a.records, a.shell, a.dirty = root, {}, None, False
    a.status_text, a.status_until, a.batch_ids = "", 0, set()
    a.pp_win = None
    a.log_error = lambda where: (_ for _ in ()).throw(AssertionError(where))
    a.pc_show_get = lambda: "front"
    a.pc_add_fav = lambda: None
    a.favs = lambda: {}
    a._drawer_mouse_down = lambda: False
    a.reprice = lambda ids: None                            # (nothing is searched in a test)
    return a


class Layout(unittest.TestCase):
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
                        pc_fold={}, pc_art=False)
        if GOLD.TABLE is None:
            GOLD.TABLE = GOLD.stat_table()
            M.DUPS.clear()
            M.OPTS.clear()
            T.build_sidtext(GOLD.TABLE)
        ITEMS.update(GOLD.load_items())

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.minsize(1, 1)
        self.app = make_app(self.root)
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_pc(self.body)
        self.size(1600, 1000)

    def size(self, w, h):
        self.root.geometry(f"{w}x{h}+0+0")
        self.pump()
        time.sleep(0.2)                                   # (the layout waits for the resize to pause: 150 ms)
        self.pump()
        time.sleep(0.2)
        self.pump()

    def pump(self, n=8):
        for _ in range(n):
            self.root.update()

    def show(self, name, rid=1):
        rec = rec_of(name, rid)
        self.app.records[rid] = rec
        self.app.pc_show(rec)
        self.pump()
        time.sleep(0.2)
        self.pump()
        return rec

    def card(self):
        return self.app.detail_card if self.app.pcv.shown_rid is not None else None

    def heads(self, cv):
        items = sorted(cv.find_withtag("cardsec"), key=lambda i: cv.coords(i)[1])
        return [cv.itemcget(i, "text").lstrip("▾▸ ") for i in items]

    def walk(self, w):
        yield w
        for c in w.winfo_children():
            yield from self.walk(c)

    # ---- the order of the card's sections
    # the owner's one order on every item card (Price Checks, Bulk Pricing, Favorites)
    ORDER = ("BASE AND PROPERTIES", "REQUIREMENTS", "AUGMENTS", "ITEM FLAGS", "MODS", "PSEUDO FILTERS", "TRADE FILTERS")
    OLD_NAMES = {"PROPERTIES": "BASE AND PROPERTIES", "MISCELLANEOUS": "ITEM FLAGS", "STAT FILTERS": "MODS"}

    def assert_order(self, heads):
        names = [self.OLD_NAMES.get(n, n) for n in (h.split(" · ")[0].split("  ")[0] for h in heads)]
        known = [n for n in names if n in self.ORDER]
        self.assertEqual(known, sorted(known, key=self.ORDER.index), heads)
        self.assertEqual(names[0], "BASE AND PROPERTIES", heads)
        for must in ("ITEM FLAGS", "MODS", "TRADE FILTERS"):
            self.assertIn(must, names, heads)
        return names

    def test_section_order(self):
        for i, name in enumerate(("rare_gloves_quality_sockets", "rare_amulet_fractured"), 1):
            self.show(name, i)
            heads = self.heads(self.card())
            names = self.assert_order(heads)
            self.assertTrue(any(h.startswith("MODS · ") and h.endswith(" searched") for h in heads), heads)
            self.assertNotIn("MISCELLANEOUS", names)

    def test_favorites_card_unchanged(self):
        """The same card on Favorites (no Price Checks look) keeps its own names, in the one order. Bulk Pricing's
        picked item has the Price Checks look: tests/test_bulk_layout.py."""
        rec = rec_of("rare_gloves_quality_sockets", 7)
        rec["src"] = "fav"
        top = tk.Toplevel(self.root)
        self.addCleanup(top.destroy)
        cv = self.app._detail_card(top, rec, rec["item"], 400)
        heads = self.heads(cv)
        names = [h.split("  ")[0] for h in heads]
        self.assertIn("MISCELLANEOUS", names)              # (its own names)
        self.assertIn("STAT FILTERS", names)
        self.assert_order(heads)                           # (the one order)
        self.assertEqual(getattr(cv, "_look", ""), "")

    # ---- Item Flags (owner pick, mockup B): plain rows, a pill for a set value, no box per flag
    def flags_check(self, cv, rec):
        tags = sorted({t for i in cv.find_all() for t in cv.gettags(i) if t.startswith("cardtri_")
                       and t not in ("cardtri_hit", "cardtri_line") and not t.endswith("_pill")})
        self.assertTrue(tags, "the card has Item Flags")
        for t in tags:
            for i in cv.find_withtag(t):
                if cv.type(i) in ("rectangle", "polygon", "oval"):
                    self.assertEqual(cv.itemcget(i, "outline"), "", f"{t}: drawn with a border")
        texts = {t: [cv.itemcget(i, "text") for i in cv.find_withtag(t) if cv.type(i) == "text"] for t in tags}
        lit = [t for t, ws in texts.items() if any(w.startswith(("Yes", "No")) for w in ws)]
        for t in lit:                                 # (a set one: a pill, and the word says it)
            self.assertTrue(cv.find_withtag(t + "_pill"), t)
        anys = [t for t, ws in texts.items() if any(w.startswith("Any") for w in ws)]
        for t in anys:
            self.assertFalse(cv.find_withtag(t + "_pill"), t)
        t = anys[0]                                   # a click steps it in place: Any -> Yes, a pill shows
        items = set(cv.find_all())
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("built again")):
            x0, y0, x1, y1 = cv.bbox(t)
            fn = [i for i in cv.find_withtag(t) if cv.type(i) == "text"]
            cv.event_generate("<Motion>", x=(x0 + x1) // 2, y=(y0 + y1) // 2, when="now")
            cv.event_generate("<Button-1>", x=(x0 + x1) // 2, y=(y0 + y1) // 2, when="now")
            self.pump()
        self.assertIs(self.card(), cv)
        self.assertTrue(cv.find_withtag(t + "_pill"), "lit in place")
        self.assertTrue(any(cv.itemcget(i, "text").startswith("Yes") for i in fn))
        self.assertTrue(set(cv.find_all()) - items <= set(cv.find_withtag(t + "_pill")))

    def test_item_flags_are_plain_rows(self):
        rec = self.show("rare_amulet_fractured")
        self.flags_check(self.card(), rec)

    # ---- one orange button
    def test_one_orange_button(self):
        self.show("rare_amulet_fractured")
        ws = [w for w in self.walk(self.app.pc_check_page) if w.winfo_viewable()]
        orange = [w for w in ws if isinstance(w, ttk.Button) and "Primary" in str(w.cget("style"))]
        self.assertEqual(len(orange), 1, [w.cget("text") for w in orange])
        self.assertIs(orange[0], self.app.pc_search_btn)
        from soe2.style import C
        filled = [w for w in ws if isinstance(w, (tk.Label, tk.Frame, tk.Button)) and
                  str(w.cget("bg")).lower() in {C["accent"].lower(), C["orange"].lower()}]
        self.assertEqual(filled, [], "nothing else is orange-filled")
        for lab in (self.app.pc_recent_all, self.app.pc_clear_lbl):
            self.assertNotIn(str(lab.cget("fg")).lower(), {C["accent"].lower(), C["orange"].lower()})
        foot = self.app.pc_foot
        self.assertEqual(foot.winfo_manager(), "pack")
        self.assertGreaterEqual(foot.winfo_rooty() + foot.winfo_height(),
                                self.app.pc_pane.winfo_rooty() + self.app.pc_pane.winfo_height(),
                                "the buttons are at the bottom")

    def test_switch_is_plain_with_a_mark(self):
        sw = self.app.pc_where
        self.assertTrue(sw.plain)
        lab, line = sw.btns[sw.get()]
        self.assertTrue(lab.cget("text").startswith("✓ "), "the picked one says ✓ and its word")
        from soe2.style import C
        self.assertNotEqual(str(line.cget("bg")).lower(), C["accent"].lower())
        other = next(o for o in sw.btns if o != sw.get())
        self.assertFalse(sw.btns[other][0].cget("text").startswith("✓"))

    def test_search_box_first_and_filters_chips(self):
        for i, name in enumerate(("rare_gloves_quality_sockets", "rare_amulet_fractured"), 1):
            self.app.records[i] = rec_of(name, i)
        self.app.pc_show(self.app.records[1])
        self.pump()
        row = self.app.pc_recent.master
        first = row._flow_lefts[0]["w"]
        self.assertIn(self.app.pc_recent_entry, list(self.walk(first)), "the search box is first, top left")
        self.assertEqual(len(self.app.pc_chips), 2)
        self.app.pc_recent_q.set("oblivion")
        self.pump()
        self.assertEqual(list(self.app.pc_chips), [2])

    # ---- wide: beside; narrow: under
    def table(self):
        lst = self.app.pcv.lst
        kids = [c for c in lst.winfo_children() if isinstance(c, tk.Frame)]
        self.assertTrue(kids, "the listings table is drawn")
        return kids[0]

    def test_listings_beside_the_card_when_wide(self):
        self.show("rare_gloves_quality_sockets")
        self.assertTrue(self.app.pc_layout_wide())
        tb, card = self.table(), self.app.pc_left
        self.assertIs(self.app.pcv.lst, self.app.pc_list)
        self.assertTrue(tb.winfo_viewable())
        self.assertGreaterEqual(tb.winfo_rootx(), card.winfo_rootx() + card.winfo_width(), "beside the card")
        self.assertFalse(self.app.pc_nlist_box.winfo_ismapped())

    def test_listings_under_the_card_when_narrow(self):
        self.show("rare_gloves_quality_sockets")
        self.size(700, 1000)
        self.assertFalse(self.app.pc_layout_wide())
        self.assertIs(self.app.pcv.lst, self.app.pc_nlist)
        tb, card = self.table(), self.app.pc_left
        self.assertGreaterEqual(tb.winfo_rooty(), card.winfo_rooty() + card.winfo_height(), "under the card")
        self.assertFalse(self.app.pc_pane.right.winfo_ismapped(), "one column")
        self.assertLessEqual(card.winfo_width(), self.app.pc_pane.winfo_width())
        self.size(1600, 1000)                             # and back: beside it again
        self.assertTrue(self.app.pc_layout_wide())
        self.assertIs(self.app.pcv.lst, self.app.pc_list)
        self.assertTrue(self.table().winfo_viewable())

    def test_listings_have_no_seller(self):
        self.show("rare_gloves_quality_sockets")
        texts = [str(w.cget("text")) for w in self.walk(self.table()) if isinstance(w, tk.Label)]
        self.assertIn("item level 80", " ".join(texts))
        self.assertFalse([t for t in texts if "seller" in t.lower()], texts)

    # ---- UI rule 22
    def test_tick_paints_in_place(self):
        rec = self.show("rare_gloves_quality_sockets")
        cv = self.card()
        v = self.app.pcv
        idx, (m, on, rect) = next((i, r) for i, r in sorted(v.card_rows.items()) if r[1] and r[0].get("sid")
                                  and r[0].get("kind") != "Total")
        before = set(cv.find_all())
        head0 = cv.itemcget("cardsec_stats", "text")
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("built again")):
            self.app.card_toggle(rec, m, False)
            self.pump()
        self.assertIs(self.card(), cv, "the same card")
        self.assertTrue(cv.winfo_exists())
        self.assertEqual(cv.type(rect), "rectangle", "the row's box is still there")
        self.assertFalse(v.card_rows[idx][1], "unticked")
        self.assertFalse(cv.find_withtag(f"cardchk{idx}"), "its tick mark is gone")
        self.assertNotEqual(cv.itemcget("cardsec_stats", "text"), head0, "MODS · n of m follows, in place")
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("built again")):
            self.app.card_toggle(rec, m, True)
            self.pump()
        self.assertTrue(v.card_rows[idx][1])
        self.assertTrue(cv.find_withtag(f"cardchk{idx}"))
        self.assertEqual(cv.itemcget("cardsec_stats", "text"), head0)
        self.assertTrue(set(cv.find_all()) - before <= set(cv.find_withtag(f"cardchk{idx}")))

    def test_new_price_keeps_the_card(self):
        rec = self.show("rare_gloves_quality_sockets")
        cv = self.card()
        h = self.app.pc_verdict.winfo_height()
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("built again")):
            rec["state"] = "pricing"
            self.app.pc_show(rec)
            self.pump()
            self.assertIn("Searching", self.app.pc_v_big.cget("text"))
            self.assertIn("Last price", self.app.pc_v_why.cget("text"))
            self.assertEqual(self.app.pc_verdict.winfo_height(), h, "the price card's height doesn't jump")
            rec.update(state="done", est=6.0)
            self.app.pc_show(rec)
            self.pump()
        self.assertIs(self.card(), cv)
        self.assertIn("6", self.app.pc_v_big.cget("text"))
        self.assertTrue(self.app.pc_v_how.cget("text").startswith("~ "), "how sure: a mark and a word")
        self.assertEqual(self.app.pc_verdict.winfo_height(), h)

    def test_drag_ticks_property_boxes_and_mods(self):
        rec = self.show("rare_amulet_fractured")
        cv = self.card()
        ticks = cv._soe_ticks
        for t in ("cardbase", "cardopt_ilvl"):
            self.assertIn(t, ticks)
        rows = [t for t in ticks if t.startswith("cardrow")]
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue([t for t in ticks if t.startswith("cardonly")], "Fractured only")
        order = sorted(ticks, key=lambda t: cv.bbox(t)[1])
        start = order[0]
        to = not ticks[start][0]()
        self.app._card_drag_start(cv, rec, start)
        for t in order[1:]:
            x0, y0, x1, y1 = cv.bbox(t + "_box") if cv.find_withtag(t + "_box") else cv.bbox(t)
            self.app._card_drag_over(cv, (x0 + x1) // 2 if t.startswith("cardonly") else 16, (y0 + y1) // 2)
        self.app._cdrag = None
        got = {t: ticks[t][0]() for t in order}
        self.assertEqual(got, {t: to for t in order}, "every box crossed took the first box's state")

    def test_tier_and_star_have_a_hover(self):
        """P1 / S3 say what they mean on hover; ★ (must match) has its tip."""
        self.show("rare_amulet_fractured")
        cv = self.card()
        tiers = [t for i in cv.find_all() for t in cv.gettags(i) if t.startswith("cardtier")]
        self.assertTrue(tiers)
        for t in tiers:
            self.assertTrue(cv.tag_bind(t, "<Enter>"), t)
        stars = {t for i in cv.find_all() for t in cv.gettags(i) if t.startswith("cardstar")}
        self.assertTrue(stars)
        for t in stars:
            self.assertTrue(cv.tag_bind(t, "<Enter>"), t)

    def test_prices_shows_how_on_hover(self):
        self.show("rare_gloves_quality_sockets")
        tip = self.app.pc_v_info_tip.text
        self.assertIn("Middle", tip)
        txt = self.app.pc_v_info.cget("text")
        self.assertTrue(txt.startswith("from the "), txt)      # (owner: the line says how - no ⓘ beside the price)
        self.assertNotIn("ⓘ", txt)

    # ---- the price card and the footer belong to the item card's column
    def test_price_and_buttons_as_wide_as_the_card_column(self):
        self.show("rare_gloves_quality_sockets")
        self.assertTrue(self.app.pc_layout_wide())
        col, page = self.app.pc_pane.left, self.app.pc_pane
        for w in (self.app.pc_verdict, self.app.pc_foot):
            self.assertIs(w.master, col)
            self.assertLess(w.winfo_width(), page.winfo_width() - 300, "not the whole page")
        v, card, foot = self.app.pc_verdict, self.app.pc_left, self.app.pc_foot
        self.assertEqual(foot.winfo_width(), col.winfo_width())
        # owner (round 2): the price box has exactly the card's left and right edges (not over the scroll bar's strip)
        self.assertEqual(v.winfo_rootx(), card.winfo_rootx())
        self.assertEqual(v.winfo_rootx() + v.winfo_width(), card.winfo_rootx() + card.winfo_width())
        self.assertLessEqual(v.winfo_rooty() + v.winfo_height(), card.winfo_rooty(), "the price on top")
        self.assertEqual(foot.winfo_rooty() + foot.winfo_height(), col.winfo_rooty() + col.winfo_height(),
                         "the buttons at the column's bottom")
        tb = self.table()
        self.assertGreaterEqual(tb.winfo_rootx(), col.winfo_rootx() + col.winfo_width(), "the listings beside")

    # ---- owner: the card fits the window (one scale for the whole card), the price card is tight
    def scroller_needed(self):
        cv = self.app.pc_lcanvas
        inner = self.app.pc_left.master
        return inner.winfo_reqheight() > cv.winfo_height() + 1, cv._sb.winfo_ismapped()

    def test_card_fits_a_full_window(self):
        SETTINGS["pc_fold"] = {}
        self.addCleanup(SETTINGS.update, pc_fold={})
        self.size(1688, 1000)
        self.show("rare_gloves_corrupted_enchant")
        cv = self.card()
        from soe2 import cardscale
        self.assertLess(cv._k, cardscale.WIDE, "smaller to fit")
        self.assertGreaterEqual(cv._k, cardscale.KMIN)
        need, sb = self.scroller_needed()
        self.assertFalse(need, "it fits")
        self.assertFalse(sb, "no scroll bar")
        heads = self.heads(cv)
        self.assert_order(heads)

    def test_never_below_kmin_it_scrolls(self):
        """Owner (round 2): 0.75 was unreadable - never below 0.9, text never below 9 pt; everything open in a
        1920x1040 full window scrolls."""
        from soe2 import cardscale
        self.assertGreaterEqual(cardscale.KMIN, 0.9)
        self.assertGreaterEqual(cardscale.MIN_PT, 9)
        for size in (9, 10, 11, 13, 22):
            for k in (cardscale.KMIN, cardscale.BULK):
                self.assertGreaterEqual(cardscale.font_size(size, k), 9, (size, k))
        self.assertEqual(cardscale.font_size(8, cardscale.KMIN), 8, "a size already small stays")
        SETTINGS["pc_fold"] = {}
        self.addCleanup(SETTINGS.update, pc_fold={})
        self.size(1688, 840)                              # (the page in a 1920x1040 full window)
        self.show("rare_gloves_corrupted_enchant")
        self.assertEqual(self.card()._k, cardscale.KMIN)
        self.assertTrue(self.scroller_needed()[0], "a scroll bar, not smaller text")

    def test_card_full_size_with_room(self):
        from soe2 import cardscale
        self.size(1600, 1400)
        self.show("rare_gloves_quality_sockets")
        self.assertEqual(self.card()._k, cardscale.WIDE, "the full window: a bit bigger than the Drawer")
        self.assertFalse(self.scroller_needed()[1])
        lc = next(w for w in self.app.pcv.lst.winfo_children() if hasattr(w, "_lc_ids"))
        self.assertEqual(lc._lc_k, cardscale.WIDE, "the listing cards too")

    def test_taller_window_scales_up_once_after_the_resize(self):
        SETTINGS["pc_fold"] = {}
        self.addCleanup(SETTINGS.update, pc_fold={})
        self.size(1688, 840)
        self.show("rare_gloves_corrupted_enchant")
        k0 = self.card()._k
        lst = list(self.app.pcv.lst.winfo_children())
        calls = []
        real = self.app._detail_card
        with mock.patch.object(self.app, "_detail_card", side_effect=lambda *a: calls.append(1) or real(*a)):
            self.root.geometry("1688x1300+0+0")          # (several sizes while dragging: drawn after the pause)
            self.pump()
            self.root.geometry("1688x1400+0+0")
            self.pump()
            self.assertEqual(calls, [], "not while the window is still changing size")
            self.size(1688, 1400)
        self.assertTrue(calls, "drawn again for its room")
        self.assertLessEqual(len(calls), 3)
        self.assertGreater(self.card()._k, k0)
        self.assertEqual(list(self.app.pcv.lst.winfo_children()), lst, "the listings stay as they are")
        self.assertFalse(self.scroller_needed()[0], "it fits")
        for _ in range(30):                               # (the bar was there at the small size: it goes once the
            if not self.scroller_needed()[1]:            # bar's own hold is over - SbGuard)
                break
            self.pump()
            time.sleep(0.1)
        self.assertFalse(self.scroller_needed()[1])

    def test_small_window_scrolls(self):
        SETTINGS["pc_fold"] = {}
        self.addCleanup(SETTINGS.update, pc_fold={})
        self.size(1600, 560)
        self.show("rare_body_armour_runes")
        from soe2 import cardscale
        self.assertEqual(self.card()._k, cardscale.KMIN, "as small as it goes")
        self.assertTrue(self.scroller_needed()[0])

    def test_drawer_card_keeps_its_size(self):
        self.size(640, 1000)
        self.show("rare_gloves_quality_sockets")
        self.assertFalse(self.app.pc_layout_wide())
        self.assertEqual(self.card()._k, 1.0, "the Drawer: the listings follow the card - it scrolls")
        lc = next(w for w in self.app.pcv.lst.winfo_children() if hasattr(w, "_lc_ids"))
        self.assertEqual(lc._lc_k, 1.0, "the Drawer's text as it was")
        v, card = self.app.pc_verdict, self.app.pc_left
        self.assertEqual(v.winfo_rootx() + v.winfo_width(), card.winfo_rootx() + card.winfo_width(),
                         "the price box: the card's edges in the Drawer too")

    def test_footer_one_row_when_it_fits_wrapped_lines_line_up(self):
        """Owner (round 2): Search again | Trade Site | Add to favorites | Clear on one row where the width allows;
        narrower, a wrapped line starts at the same edge as the first."""
        self.show("rare_gloves_quality_sockets")
        a = self.app
        btns = (a.pc_search_btn, a.pc_open_btn, a.pc_fav_btn)
        self.assertEqual(len({b.winfo_y() for b in btns}), 1, "one row")
        cy = a.pc_clear_lbl.winfo_y() + a.pc_clear_lbl.winfo_height() / 2
        sb = a.pc_search_btn
        self.assertTrue(sb.winfo_y() <= cy <= sb.winfo_y() + sb.winfo_height(), "Clear on that row too")
        self.size(460, 1000)
        rows = sorted({b.winfo_y() for b in btns})
        self.assertGreater(len(rows), 1, "narrow: it wraps")
        first = {b for b in btns if b.winfo_y() == rows[0]}
        starts = [min((b for b in btns if b.winfo_y() == y), key=lambda b: b.winfo_x()) for y in rows]
        self.assertTrue(first)
        self.assertEqual({b.winfo_x() for b in starts}, {a.pc_search_btn.winfo_x()}, "each line starts at the edge")

    def test_scaled_card_ticks_in_place(self):
        SETTINGS["pc_fold"] = {}
        self.addCleanup(SETTINGS.update, pc_fold={})
        self.size(1688, 840)
        rec = self.show("rare_gloves_corrupted_enchant")
        cv = self.card()
        self.assertLess(cv._k, 1.0)
        idx, (m, _on, rect) = next((i, r) for i, r in sorted(self.app.pcv.card_rows.items()) if r[1]
                                   and r[0].get("sid") and r[0].get("kind") != "Total")
        box = cv.coords(rect)
        self.assertAlmostEqual(box[2] - box[0], round(14 * cv._k), delta=1, msg="the boxes follow the scale")
        with mock.patch.object(self.app, "_detail_card", side_effect=AssertionError("the card was built again")):
            self.app.card_toggle(rec, m, False)
            self.pump()
        self.assertIs(self.card(), cv)

    def test_price_card_is_tight_and_how_sure_is_plain(self):
        self.show("rare_gloves_quality_sockets")
        f, how = self.app.pc_verdict, self.app.pc_v_how
        self.assertLessEqual(int(str(f.cget("padx"))), 12)
        self.assertLessEqual(int(str(f.cget("pady"))), 8)
        self.assertEqual(int(str(how.cget("highlightthickness"))), 0, "how sure: no box")
        self.assertEqual(how.cget("text"), "~ Medium confidence", "a mark and a word")
        self.assertTrue(how.winfo_viewable())
        big = self.app.pc_v_big
        self.assertGreaterEqual(how.winfo_rootx(), big.winfo_rootx() + big.winfo_width(), "beside the price")
        self.assertLess(f.winfo_height(), 100)
        from soe2.pricecheck_page import CONF_CHIP
        self.assertEqual(CONF_CHIP["medium"][:2], ("~", "Medium confidence"), "the words themselves are the owner's")


if __name__ == "__main__":
    unittest.main()
