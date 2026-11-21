"""The cheapest listings as small item cards (soe2/listingcard.py), on Price Checks, Bulk Pricing and Favorites: the
item's name as the title (the base type muted beside it), the price on the right as "2000 ×" and the currency's
picture, item level, the mods one per line (tier tags in one column), flag chips, no seller names, one toggle per card
(only that card changes), Whole item headed and indented like the item card (labels muted, values bright), and a
picture that arrives goes into its placeholder without building the card again (UI rule 22).

    python3.12 -m unittest tests.test_listing_cards          (or tests/runall.sh)"""
import os
import sys
import tempfile
import time
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-listingcards-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_bulk_layout as BKL                            # noqa: E402
import test_pricecheck_golden as GOLD                     # noqa: E402
import test_pricecheck_layout as PCL                      # noqa: E402
from soe2 import mods as M, trade as T                    # noqa: E402
from soe2.config import SETTINGS                          # noqa: E402

MODS = ["+59 to maximum Energy Shield", "97% increased Energy Shield", "12% increased Cast Speed"]
ICON = "https://web.poecdn.com/gen/image/test-listing-card.png"


def dress(rec):
    """Give a priced fake record's listings tiers, a fractured and a crafted mod, a note and a picture."""
    for i, lid in enumerate(rec["stages"][0]["ids"]):
        it = T.RAW_LISTINGS[lid]["item"]
        it.update(ilvl=82 + i, icon=ICON + f"?n={i}", note="~price 5 divine", corrupted=i == 1,
                  explicitMods=MODS[:2], fracturedMods=["+120 to maximum Mana"], craftedMods=[MODS[2]],
                  implicitMods=["+10% to Fire Resistance"], properties=[{"name": "Energy Shield", "values": [["211", 1]]}],
                  extended={"hashes": {"explicit": [["explicit.a", [0]], ["explicit.b", [1]]]},
                            "mods": {"explicit": [{"tier": "P1"}, {"tier": "S2"}]}})
        T.RAW_LISTINGS[lid]["listing"]["account"] = {"name": f"acct{i}Seller#{i}{i}{i}"}


class Base(unittest.TestCase):
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
                        pc_fold={}, pc_art=False, view="Not yet listed", detail_adv=False)
        if GOLD.TABLE is None:
            GOLD.TABLE = GOLD.stat_table()
            M.DUPS.clear()
            M.OPTS.clear()
            T.build_sidtext(GOLD.TABLE)
        PCL.ITEMS.update(GOLD.load_items())

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def tearDown(self):
        for job in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.tk.call("after", "cancel", job)

    def pump(self, n=8):
        for _ in range(n):
            self.root.update()

    def settle(self):
        for _ in range(3):
            self.pump()
            time.sleep(0.2)
        self.pump()

    def walk(self, w):
        yield w
        for c in w.winfo_children():
            yield from self.walk(c)

    def cards(self, lst):
        holder = next(w for w in lst.winfo_children() if hasattr(w, "_lc_ids"))
        return holder.winfo_children()

    def texts(self, w):
        return [str(x.cget("text")) for x in self.walk(w) if isinstance(x, (tk.Label, tk.Button))]

    def toggle_of(self, card):
        return next(x for x in self.walk(card) if isinstance(x, tk.Label)
                    and str(x.cget("text")) in ("▸ Whole item", "▾ Less"))

    def click(self, w):
        w.event_generate("<Button-1>", x=2, y=2)
        self.pump()


class OnPriceChecks(Base):
    def setUp(self):
        import artfixture                                  # 3.1: the currency's picture comes from the art cache
        from soe2.wealth import WPRICES                    # (poe.ninja's, downloaded) - none ship with the app
        was = WPRICES.parts
        self.addCleanup(setattr, WPRICES, "parts", was)
        artfixture.install()
        for w in self.root.winfo_children():
            w.destroy()
        self.app = PCL.make_app(self.root)
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_pc(self.body)
        self.root.geometry("1600x1000+0+0")
        self.settle()
        self.rec = PCL.rec_of("rare_gloves_quality_sockets", 1)
        dress(self.rec)
        self.app.records[1] = self.rec
        self.app.pc_show(self.rec)
        self.settle()
        self.cards_ = self.cards(self.app.pcv.lst)

    def label(self, card, text):
        return next(x for x in self.walk(card) if isinstance(x, tk.Label) and str(x.cget("text")) == text)

    def test_card_shows_price_level_mods_flags(self):
        self.assertEqual(len(self.cards_), 6)
        c = self.cards_[0]
        txt = self.texts(c)
        name, base, amt = self.label(c, "Thing"), self.label(c, "Vaal Wraps"), self.label(c, "3")
        from soe2.style import C
        self.assertEqual(base.cget("fg"), C["muted"], "the base type muted")
        self.assertEqual(base.winfo_rooty() // 4, base.winfo_rooty() // 4)
        self.assertGreater(base.winfo_rootx(), name.winfo_rootx(), "beside the name")
        self.assertGreater(amt.winfo_rootx(), base.winfo_rootx() + base.winfo_width(), "the price on the right")
        self.assertEqual(amt._tip.text, "3 Divine Orb", "the price in words on hover")
        self.assertIn("×", txt)
        pics = [x for x in self.walk(amt.master) if isinstance(x, tk.Label) and str(x.cget("image"))]
        self.assertEqual(len(pics), 1, "the currency's picture (poe.ninja's, from the art cache)")
        self.assertEqual(pics[0]._tip.text, "3 Divine Orb", "a picture alone says it on hover too")
        self.assertFalse(any(t.startswith("3 ") for t in txt), "not in the title spot")
        meta = next(t for t in txt if t.startswith("item level 82"))
        self.assertIn("listed", meta)
        self.assertGreater(self.label(c, meta).winfo_rooty(), name.winfo_rooty(), "under the name")
        self.assertTrue(any("listed" in t for t in txt), txt)
        ys = []
        for want in ("+120 to maximum Mana", "+59 to maximum Energy Shield", "97% increased Energy Shield",
                     "12% increased Cast Speed"):         # (the game's order: fractured first)
            lab = next(x for x in self.walk(c) if isinstance(x, tk.Label) and x.cget("text") == want)
            ys.append(lab.winfo_rooty())
        self.assertEqual(ys, sorted(set(ys)), "one mod per line, top to bottom")
        self.assertIn("P1", txt)
        self.assertIn("S2", txt)
        self.assertIn("◆ Fractured", txt)
        self.assertIn("✎ Crafted", txt)
        self.assertNotIn("⊘ Corrupted", txt)
        self.assertIn("⊘ Corrupted", self.texts(self.cards_[1]))
        self.assertNotIn("+10% to Fire Resistance", txt, "implicits wait behind Whole item")

    def test_tier_tag_has_the_item_cards_hover(self):
        tag = next(x for x in self.walk(self.cards_[0]) if isinstance(x, tk.Label) and x.cget("text") == "P1")
        self.assertEqual(tag._tip.text, "Prefix, tier 1 (1 is the best roll)")

    def test_no_seller_or_account_name(self):
        for c in self.cards_:
            for x in self.texts(c):
                self.assertNotIn("seller", x.lower())
                self.assertNotIn("acct", x.lower())
        self.click(self.toggle_of(self.cards_[0]))          # (opened too)
        for x in self.texts(self.cards_[0]):
            self.assertNotIn("seller", x.lower())
            self.assertNotIn("acct", x.lower())

    def test_toggle_changes_only_its_card(self):
        before = [list(self.walk(c)) for c in self.cards_]
        self.assertEqual(self.cards(self.app.pcv.lst), self.cards_)
        tog = self.toggle_of(self.cards_[2])
        self.assertEqual(tog.cget("text"), "▸ Whole item")
        h0 = self.cards_[2].winfo_height()
        self.click(tog)
        self.assertEqual(tog.cget("text"), "▾ Less")
        self.assertGreater(self.cards_[2].winfo_height(), h0)
        self.assertIn("Implicit · +10% to Fire Resistance", self.texts(self.cards_[2]))
        self.assertIn("Note: ~price 5 divine", self.texts(self.cards_[2]))
        es, val = self.label(self.cards_[2], "Energy Shield"), self.label(self.cards_[2], "211")
        self.assertEqual(es.winfo_rooty(), val.winfo_rooty(), "label and value on one row")
        for i, c in enumerate(self.cards_):
            self.assertEqual(self.toggle_of(c).cget("text"), "▾ Less" if i == 2 else "▸ Whole item")
        for i, c in enumerate(self.cards_):                 # (the same widgets: nothing rebuilt)
            if i != 2:
                self.assertEqual(list(self.walk(c)), before[i])
        self.click(tog)
        self.assertEqual(tog.cget("text"), "▸ Whole item")
        self.assertEqual(self.cards_[2].winfo_height(), h0)
        # a click on the card's body does the same as the toggle
        self.click(self.cards_[2])
        self.assertEqual(tog.cget("text"), "▾ Less")

    def test_picture_in_the_middle_of_its_column_and_body_beside_it(self):
        for c in (self.cards_[0], self.cards_[3]):
            pic = next(x for x in self.walk(c) if isinstance(x, tk.Canvas))
            inner_top = c.winfo_rooty() + int(str(c.cget("pady"))) + 1
            inner_h = c.winfo_height() - 2 * int(str(c.cget("pady"))) - 2
            mid = pic.winfo_rooty() + pic.winfo_height() / 2
            self.assertAlmostEqual(mid, inner_top + inner_h / 2, delta=2, msg="the picture: the middle, top to bottom")
            body = pic.master.grid_slaves(row=0, column=1)[0]
            bmid = body.winfo_rooty() + body.winfo_height() / 2
            self.assertAlmostEqual(bmid, inner_top + inner_h / 2, delta=2, msg="the mods: the middle beside it")
        self.click(self.toggle_of(self.cards_[0]))
        self.pump()
        c = self.cards_[0]
        pic = next(x for x in self.walk(c) if isinstance(x, tk.Canvas))
        inner_top = c.winfo_rooty() + int(str(c.cget("pady"))) + 1
        inner_h = c.winfo_height() - 2 * int(str(c.cget("pady"))) - 2
        self.assertAlmostEqual(pic.winfo_rooty() + pic.winfo_height() / 2, inner_top + inner_h / 2, delta=2,
                               msg="opened: still the middle of the card's full height")

    def test_whole_item_follows_the_item_cards_order_and_words(self):
        from soe2.names import CARD_SECTIONS
        it = T.RAW_LISTINGS[self.rec["stages"][0]["ids"][0]]["item"]
        it.update(requirements=[{"name": "Level", "values": [["80", 0]]}, {"name": "Int", "values": [["101", 0]]}],
                  runeMods=["Bonded: +20 to maximum Life"], pseudoMods=["+120 total maximum Mana"],
                  properties=[{"name": "Gloves", "values": []}, {"name": "Quality", "values": [["+21%", 1]]},
                              {"name": "Energy Shield", "values": [["297", 1]]}])
        self.app.pc_draw_list(self.rec)
        self.pump()
        c = self.cards(self.app.pcv.lst)[0]
        self.click(self.toggle_of(c))
        self.pump()
        shown = [x for x in self.walk(c) if isinstance(x, tk.Label) and x.winfo_viewable() and x.cget("text")]
        shown.sort(key=lambda x: (x.winfo_rooty(), x.winfo_rootx()))
        words = [str(x.cget("text")) for x in shown]
        heads = [w for w in words if w in CARD_SECTIONS.values()]
        order = list(CARD_SECTIONS.values())
        self.assertEqual(heads, ["BASE AND PROPERTIES", "REQUIREMENTS", "AUGMENTS", "ITEM FLAGS", "MODS",
                                 "PSEUDO FILTERS"], words)
        self.assertEqual(heads, sorted(heads, key=order.index), "the card's order")
        from soe2.style import C
        by = {str(x.cget("text")): x for x in shown}
        for lab, val in (("Quality", "+21%"), ("Energy Shield", "297"), ("Level", "80"), ("Int", "101"),
                         ("Rune", "Bonded: +20 to maximum Life"), ("Base type", "Vaal Wraps")):
            a, b = by[lab], next(x for x in shown if x.cget("text") == val and x.winfo_rooty() == by[lab].winfo_rooty())
            self.assertEqual(a.cget("fg"), C["muted"], f"{lab}: the label muted")
            self.assertNotEqual(b.cget("fg"), C["muted"], f"{val}: the value bright")
            self.assertGreater(b.winfo_rootx(), a.winfo_rootx())
        props = [by[x] for x in ("Base type", "Item level", "Quality", "Energy Shield")]
        vals = [next(x for x in shown if x.winfo_rooty() == p.winfo_rooty() and x is not p) for p in props]
        self.assertEqual(len({v.winfo_rootx() for v in vals}), 1, "the values in one column")
        for row in ("Implicit · +10% to Fire Resistance", "+120 total maximum Mana", "◆ Fractured", "✎ Crafted",
                    "P1", "S2"):
            self.assertIn(row, words)
        # headed as the item card heads its sections; the rows indented under them
        for h in heads:
            lab = by[h]
            self.assertEqual(lab.cget("fg"), C["text"])
            self.assertIn("bold", str(lab.cget("font")))
        self.assertGreater(by["Quality"].winfo_rootx(), by["BASE AND PROPERTIES"].winfo_rootx(), "indented")
        self.assertLessEqual(by["Rune"].winfo_rootx() - by["AUGMENTS"].winfo_rootx(), 16, "Augments: not deep in")
        gap = by["REQUIREMENTS"].winfo_rooty() - (by["Energy Shield"].winfo_rooty() + by["Energy Shield"].winfo_height())
        self.assertGreaterEqual(gap, 12, "a token gap between sections")
        mods = [x for x in shown if x.cget("text") in ("Implicit · +10% to Fire Resistance",
                                                        "+59 to maximum Energy Shield", "97% increased Energy Shield",
                                                        "Fractured · +120 to maximum Mana")]
        self.assertEqual(len({m.winfo_rootx() for m in mods}), 1, "the mods' text in one column, tags or not")
        tags = [by["P1"], by["S2"]]
        self.assertEqual(len({t.winfo_rootx() for t in tags}), 1, "the tier tags in one column")
        self.assertNotIn("Gloves", words, "the bare class name: Base type says it")
        self.assertFalse([w for w in words if w.startswith("Requires:")], "no raw item text")
        self.assertEqual(words[-1], "Note: ~price 5 divine", "the note: the last row")
        note = shown[-1]
        from soe2.style import C
        self.assertEqual(note.cget("fg"), C["muted"], "quiet")
        quick = [x for x in self.walk(c) if isinstance(x, tk.Label) and x.cget("text") == "+59 to maximum Energy Shield"]
        self.assertEqual(sum(1 for x in quick if x.winfo_viewable()), 1, "each mod once: the whole item replaces the "
                                                                          "short list")

    def test_open_state_is_kept_while_the_item_is_shown(self):
        self.click(self.toggle_of(self.cards_[1]))
        self.app.pc_draw_list(self.rec)                     # (drawn again, e.g. a resize)
        self.pump()
        again = self.cards(self.app.pcv.lst)
        self.assertEqual([self.toggle_of(c).cget("text") for c in again],
                         ["▸ Whole item", "▾ Less"] + ["▸ Whole item"] * 4)

    def test_picture_replaces_the_placeholder_in_place(self):
        SETTINGS["pc_art"] = True
        self.addCleanup(SETTINGS.update, pc_art=False)
        from PIL import Image
        from soe2 import pricecheck_page as PP

        def fake_get(url, path):                            # (the download: a file in the art cache)
            Image.new("RGBA", (40, 60), (200, 50, 50, 255)).save(path)
            with PP._ART_LOCK:
                self.app._pc_art_done = getattr(self.app, "_pc_art_done", set()) | {url}
        self.app._pc_art_get = fake_get
        self.app.pc_draw_list(self.rec)
        self.pump()
        cards = self.cards(self.app.pcv.lst)
        pics = [[x for x in self.walk(c) if isinstance(x, tk.Canvas)][0] for c in cards]
        everything = [list(self.walk(c)) for c in cards]
        self.assertTrue(all(cv.find_withtag("ph") for cv in pics), "a placeholder first")
        self.assertFalse(any(cv.find_withtag("art") for cv in pics))
        for _ in range(60):
            self.pump()
            time.sleep(0.1)
            if all(cv.find_withtag("art") for cv in pics):
                break
        self.assertTrue(all(cv.find_withtag("art") for cv in pics), "the pictures arrived")
        self.assertFalse(any(cv.find_withtag("ph") for cv in pics), "the placeholders are gone")
        self.assertEqual(self.cards(self.app.pcv.lst), cards, "the cards were not built again")
        self.assertEqual([list(self.walk(c)) for c in cards], everything)

    def test_narrow_drawer_one_column(self):
        self.root.geometry("640x900+0+0")
        self.settle()
        cs = self.cards(self.app.pcv.lst)
        self.assertEqual(len(cs), 6)
        w = self.app.pcv.lst.winfo_width()
        for c in cs:
            self.assertLessEqual(c.winfo_width(), w + 2)


class OnFavorites(Base):
    def test_favorites_uses_the_same_card_and_listing_cards(self):
        """Owner (round 2): a picked favorite shows its item as Price Checks does (the price card, the same card in
        its look and order) and the same listing cards - nothing drawn over them, no seller names."""
        import queue
        for w in self.root.winfo_children():
            w.destroy()
        app = BKL.make_app(self.root)
        app.favs = lambda: app.__class__.favs(app)
        app.ui_q = queue.Queue()
        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True)
        app.build_favorites(body)
        self.root.geometry("1900x1000+0+0")
        self.settle()
        src = PCL.rec_of("rare_gloves_quality_sockets", 1)
        dress(src)
        f = app.favs().add_item(src)
        app.fav_fill()
        self.pump()
        app.fav_tv.selection_set(f["id"])
        self.pump()
        r = app.fav_rec(f)
        for k in ("state", "est", "conf", "total", "prices", "qid", "stages", "priced_at", "resolved", "opts"):
            r[k] = src[k]
        app.fav_show()
        self.settle()
        cv = next(x for x in self.walk(app.favv.left) if isinstance(x, tk.Canvas) and hasattr(x, "_look"))
        self.assertEqual(cv._look, "drawer", "Price Checks' card")
        names = [cv.itemcget(i, "text").lstrip("▾▸ ").split(" · ")[0] for i in
                 sorted(cv.find_withtag("cardsec"), key=lambda i: cv.coords(i)[1])]
        self.assertEqual([n for n in names if n in PCL.Layout.ORDER], sorted([n for n in names if n in PCL.Layout.ORDER],
                                                                             key=PCL.Layout.ORDER.index))
        self.assertIn("BASE AND PROPERTIES", names)
        ns = app.favv.price_ns
        self.assertTrue(ns.frame.winfo_viewable(), "the price card")
        self.assertTrue(str(ns.big.cget("text")).startswith("≈"))
        cs = self.cards(app.favv.lst)
        self.assertEqual(len(cs), 6, "the same listing cards")
        for x in self.texts(app.favv.lst):
            self.assertNotIn("acct", x.lower())
            self.assertNotIn("seller", x.lower())
        self.assertFalse([x for x in self.walk(app.favv.lst) if isinstance(x, tk.Canvas)
                          and x.find_withtag("pcprice")], "no asking-price box drawn over a card")


class OnBulkPricing(Base):
    def test_bulk_pricing_uses_the_cards(self):
        for w in self.root.winfo_children():
            w.destroy()
        app = BKL.make_app(self.root)
        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True)
        app.build_checks(body)
        self.root.geometry("1400x1000+0+0")
        self.settle()
        rec = BKL.bulk_rec("rare_gloves_quality_sockets", 1)
        dress(rec)
        app.records[1] = rec
        app.rebuild_tree()
        self.pump()
        app.tree.selection_set("1")
        self.settle()
        cs = self.cards(app.bulkv.lst)
        self.assertEqual(len(cs), 6)
        txt = self.texts(cs[0])
        self.assertIn("◆ Fractured", txt)
        self.assertIn("P1", txt)
        for x in self.texts(app.bulkv.lst):
            self.assertNotIn("acct", x.lower())
            self.assertNotIn("seller", x.lower())
        self.click(self.toggle_of(cs[0]))
        self.assertEqual(self.toggle_of(cs[0]).cget("text"), "▾ Less")
        self.assertEqual(self.toggle_of(cs[1]).cget("text"), "▸ Whole item")
        from soe2 import cardscale
        import tkinter.font as tkf
        holder = next(w for w in app.bulkv.lst.winfo_children() if hasattr(w, "_lc_ids"))
        self.assertEqual(holder._lc_k, cardscale.BULK)
        sizes = {abs(int(tkf.Font(font=x.cget("font")).actual("size"))) for x in self.walk(holder)
                 if isinstance(x, tk.Label) and x.cget("text")}
        self.assertGreaterEqual(min(sizes), cardscale.MIN_PT, "never below the app's normal small size")


if __name__ == "__main__":
    unittest.main()
