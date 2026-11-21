"""Miscellaneous starts over on every price check (switching to another price check left the flags at their yes / no
states - each check
reverts to Any, then Yes depending on the mods on the item): a flag you set on one item never shows on the next -
each item shows Any, Yes for its own flags
(gamedata.copy_flags) and Corrupted as its route searches it (default_opts). The card over the game (pcpop) always
shows the item it says it shows: a refresh asked for the item before never fills it over the new one.

    python3.12 -m unittest tests.test_pricecheck_misc_reset          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-misc-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from soe2 import gamedata as GD, gear as G                      # noqa: E402
from soe2.pcpop import PricePopup                               # noqa: E402
from soe2.searchopts_page import SearchOptsPage, default_opts   # noqa: E402
from test_pricecheck_golden import load_items                   # noqa: E402

ITEMS = load_items()


def misc_keys(it):
    from soe2.app import App
    return [k for k, _l in App._card_misc_keys(it)]


def shown(rec):
    """What the card's Miscellaneous shows for this item (app.py _card_tri / pcpop._pcpop_misc use the same)."""
    cur = {**default_opts(rec["item"]), **(rec.get("opts") or {})}
    return {k: cur.get(k) or "any" for k in misc_keys(rec["item"])}


class Opts(SearchOptsPage):
    def show_detail(self, rec):
        pass


def rec(rid, name):
    return {"id": rid, "item": G.parse_gear(ITEMS[name]), "raw": ITEMS[name], "src": "pc"}


class MiscStartsOver(unittest.TestCase):
    def check_fresh(self, r, name):
        own = GD.copy_flags(ITEMS[name])
        want_c = default_opts(r["item"])["corrupted"]
        for k, v in shown(r).items():
            if k == "corrupted":
                self.assertEqual(v, want_c, f"{name}: Corrupted as its route searches it")
            elif k in own:
                self.assertEqual(v, "yes", f"{name}: its own {k} at Yes")
            else:
                self.assertEqual(v, "any", f"{name}: {k} at Any (not the item before's)")

    def test_set_on_one_never_on_the_next(self):
        app = Opts()
        a = rec(1, "rare_amulet_fractured")
        for k, v in (("crafted", "yes"), ("fractured", "no"), ("desecrated", "yes"), ("mirrored", "no"),
                     ("corrupted", "yes")):
            app.search_opt_set(a, k, v, redraw=False)
        self.assertEqual(shown(a)["crafted"], "yes")
        for rid, name in ((2, "rare_ring"), (3, "rare_belt_desecrated"), (4, "rare_ring_mirrored"),
                          (5, "rare_boots_twice_corrupted")):
            r = rec(rid, name)
            self.assertNotIn("opts", r)
            self.check_fresh(r, name)
        self.assertEqual(shown(a)["crafted"], "yes", "the first item keeps what you set on it")

    def test_copy_flags_mark_only_what_the_item_has(self):
        for name in ("rare_ring", "rare_amulet_fractured", "rare_ring_mirrored"):
            self.assertFalse({"crafted", "desecrated"} & GD.copy_flags(ITEMS[name]), name)
        self.assertEqual(GD.copy_flags(ITEMS["rare_belt_desecrated"]) & {"crafted", "desecrated"}, {"desecrated"})
        self.assertEqual(GD.copy_flags('Rarity: Rare\n{ Prefix Modifier "Crafted" (Tier: 1) — Life }\n+5 to Life'),
                         set(), "a mod's name isn't its source")


class Root:
    def __init__(self):
        self.jobs, self.n = {}, 0

    def after(self, _ms, fn):
        self.n += 1
        self.jobs[self.n] = fn
        return self.n

    def after_cancel(self, job):
        self.jobs.pop(job, None)

    def run(self):
        while self.jobs:
            _k, fn = self.jobs.popitem()
            fn()


class Win:
    def show(self):
        pass

    def lift(self):
        pass

    def winfo_exists(self):
        return True

    def destroy(self):
        pass


class Pop(PricePopup):
    """The card over the game without its window: pcpop_fill says which item it drew."""

    def __init__(self, recs):
        self.root, self.records, self.filled = Root(), {r["id"]: r for r in recs}, []
        self.pp_win = Win()

    def _pcpop_window(self):
        return self.pp_win

    def pcpop_fill(self, rec):
        self.filled.append(rec["id"])

    def pcpop_settings_close(self, _e=None):
        pass


class OverlayCardFollows(unittest.TestCase):
    def test_a_late_refresh_never_draws_the_item_before(self):
        a, b = rec(1, "rare_amulet_fractured"), rec(2, "rare_ring")
        p = Pop([a, b])
        p.pcpop_show(a)
        p.pcpop_refresh(a)                       # (A searched again / priced: its refresh waits 60 ms)
        p.pcpop_show(b)                          # ... and the next price check comes first
        p.root.run()
        self.assertEqual(p.pp_rid, 2)
        self.assertEqual(p.filled[-1], 2, f"the card shows B, not A's Yes / No (filled {p.filled})")
        self.assertNotIn(1, p.filled[p.filled.index(2):])

    def test_a_refresh_waiting_fills_the_item_shown_now(self):
        a, b = rec(1, "rare_amulet_fractured"), rec(2, "rare_ring")
        p = Pop([a, b])
        p.pcpop_show(a)
        p.pcpop_refresh(a)
        p.pp_rid = 2                             # (whatever moved the card on to B)
        p.root.run()
        self.assertEqual(p.filled[-1], 2)

    def test_another_check_picked_in_the_app_shows_on_the_card(self):
        a, b = rec(1, "rare_amulet_fractured"), rec(2, "rare_ring")
        p = Pop([a, b])
        p.pcpop_show(a)
        p.pcpop_refresh(b)                       # (Price Checks › History / Recent: B)
        p.root.run()
        self.assertEqual((p.pp_rid, p.filled[-1]), (2, 2), "the open card follows the app")
        p.pcpop_close()
        p.pp_win = Win()                         # (a window left over, the card closed: pp_up off)
        p.filled.clear()
        p.pcpop_refresh(a)                       # (closed: it stays closed)
        p.root.run()
        self.assertEqual(p.filled, [])


if __name__ == "__main__":
    unittest.main()
