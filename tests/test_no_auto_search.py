"""Every trade search comes from a press (3.0.7, GGG policy audit risk 5).

  * opening Farming Strategies searches nothing; Check cost does; the New strat editor searches nothing while you type
  * the session restore brings queued items back as Not priced - nothing is searched at the start
  * a league change searches nothing: Prices are from <old league> and Re-price all
  * a mod's rating or a rule changing searches nothing: the items say Rating changed, Re-price N items searches
  * a 429 stops the searches: one try, no automatic retry, "The trade site asked us to slow down - try again in N s"
  * session.json keeps no seller, whisper or account of a saved listing

    python3.12 -m unittest tests.test_no_auto_search          (or tests/runall.sh)"""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-noauto-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
os.environ.setdefault("SOE2_NO_BOARD", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from soe2 import moneymakers as MM                      # noqa: E402
from soe2.config import SETTINGS, save_json            # noqa: E402
import test_strats_find as TF                           # noqa: E402


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status_code, self.headers, self.text = status, headers or {}, ""
        self.elapsed = None

    def json(self):
        return {}


class RateLimit429(unittest.TestCase):
    def test_a_429_stops_after_one_try(self):
        from soe2 import net
        calls = []

        def fake(method, url, **kw):
            calls.append(url)
            return FakeResponse(429, {"Retry-After": "42"})
        with mock.patch.object(net.requests, "request", fake), mock.patch.object(net.LIMITER, "acquire", lambda c: None), \
                mock.patch.object(net.LIMITER, "log_429", lambda *a: None), \
                mock.patch.object(net.LIMITER, "penalized", lambda *a, **k: None):
            seen = []
            net._STATUS_HOOK[0] = seen.append
            try:
                with self.assertRaises(net.RateLimited) as cm:
                    net.call("GET", "https://www.pathofexile.com/api/trade2/fetch/abc")
            finally:
                net._STATUS_HOOK[0] = lambda s: None
        self.assertEqual(len(calls), 1, "no automatic retry after a 429")
        self.assertEqual(str(cm.exception), "The trade site asked us to slow down - try again in 42 s")
        self.assertEqual(seen, [str(cm.exception)])

    def test_the_learn_setting_is_gone(self):
        from soe2 import net
        self.assertNotIn("learn", SETTINGS)
        self.assertFalse(hasattr(net.Limiter, "learn_ok"))


class FarmingStrategies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2 import style as S
        from soe2 import themes as TH
        S.apply_look(TH.DEFAULT, cls.root)
        cls.root.geometry("1400x900")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        SETTINGS["league"] = "Forbidden Rites"
        save_json(MM.FILE, {"schema": MM.SCHEMA, "revision": 999, "strats": TF.STRATS, "oneliners": []})
        save_json(MM.MINE, [])
        for w in self.root.winfo_children():
            w.destroy()
        self.app = TF.make_app(self.root)
        self.started = []
        self.app.engine = mock.Mock()
        self.app.engine.strat_cost_start = lambda s, league: self.started.append(s["id"])
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_money_window(self.body)
        self.root.update()

    def tearDown(self):
        SETTINGS["league"] = ""

    def test_opening_the_page_searches_nothing(self):
        self.app._mm_costs = {}                           # (nothing checked today)
        self.app.mm_on_show()
        self.app.mm_on_show()
        self.root.update()
        self.assertEqual(self.started, [], "no cost search from opening Farming Strategies")
        self.assertFalse(self.app.engine.add.called)

    def test_check_cost_is_the_press(self):
        self.app._mm_costs = {}
        n = self.app.mm_cost_check(True, "breach-t15")
        self.assertEqual((n, self.started), (1, ["breach-t15"]))

    def test_new_strat_editor_has_no_typing_search(self):
        self.assertFalse(hasattr(self.app, "_mm_new_cost_later"))
        self.app.mm_new_open() if hasattr(self.app, "mm_new_open") else None
        self.root.update()
        self.assertEqual(self.started, [])
        cost, busy = self.app.mm_new_cost()
        self.assertEqual((cost, busy), (None, False))


class Session(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"no display: {e}")
        from soe2.app import App
        cls.app = App(cls.root)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except tk.TclError:
            pass
        from soe2 import lineicons                    # (its pictures belong to this window - the next test's own)
        lineicons._CACHE.clear()

    def rec(self, rid, state="done", **kw):
        item = {"name": "Test Ring", "base": "Ruby Ring", "rarity": "Rare", "mods": [], "ilvl": 80}
        r = {"id": rid, "item": item, "state": state, "label": "", "total": 0, "prices": [], "est": None,
             "resolved": True, "raw": f"Item {rid}", "src": "manual", "mark": "new"}
        r.update(kw)
        return r

    def test_restore_does_not_search(self):
        from soe2.config import save_json as sj
        sj("session.json", {"next_id": 9, "records": [
            {**self.rec(5, "queued"), "item": {"name": "A", "base": "Ruby Ring", "rarity": "Rare", "mods": []}},
            {**self.rec(6, "pricing"), "item": {"name": "B", "base": "Ruby Ring", "rarity": "Rare", "mods": []}}]})
        self.app.records.clear()
        added = []
        with mock.patch.object(self.app.engine, "add", lambda *a, **k: added.append(a)):
            self.app.load_session()
        self.assertEqual(added, [], "nothing is searched at the start")
        self.assertEqual([self.app.records[i]["state"] for i in (5, 6)], ["idle", "idle"])
        self.assertEqual(self.app.price_status(self.app.records[5]), "– Not priced")
        with mock.patch.object(self.app.engine, "add", lambda *a, **k: added.append(a)):
            self.app.reprice([5])                         # the Re-price button is the press
        self.assertEqual(len(added), 1)
        self.assertEqual(self.app.records[5]["state"], "queued")
        self.app.records.clear()

    def test_league_change_searches_nothing(self):
        self.app.records.clear()
        self.app.records[1] = self.rec(1)
        old = SETTINGS.get("league")
        SETTINGS["league"] = "Old League"
        self.app.league_var.set("New League")
        added = []
        try:
            with mock.patch.object(self.app.engine, "add", lambda *a, **k: added.append(a)), \
                    mock.patch.object(self.app, "league_changed", lambda new: SETTINGS.__setitem__("league", new)):
                self.app.on_league()
            self.assertEqual(added, [], "no re-pricing for the new league")
            self.assertEqual(self.app.records[1]["state"], "done")
            self.assertIn("Prices are from Old League", self.app.notes["league"][0])
            self.assertEqual(self.app.notes["league"][1], "Re-price all")
            with mock.patch.object(self.app.engine, "add", lambda *a, **k: added.append(a)):
                with mock.patch.object(self.app, "list_src", lambda: "manual"):
                    self.app.notes["league"][2]()         # Re-price all
            self.assertEqual(len(added), 1)
            self.assertNotIn("league", self.app.notes)
        finally:
            SETTINGS["league"] = old
            self.app.records.clear()

    def test_rating_change_marks_and_the_press_searches(self):
        self.app.records.clear()
        self.app.records[1] = self.rec(1)
        self.app.records[2] = self.rec(2)
        added = []
        with mock.patch.object(self.app.engine, "add", lambda *a, **k: added.append(a)):
            self.app.rating_changed([1, 2])
            self.assertEqual(added, [], "a rating changing searches nothing")
            self.assertEqual(self.app.price_status(self.app.records[1]), "↻ Rating changed")
            text, button, fn = self.app.notes["rating"]
            self.assertEqual((text, button), ("Rating changed on 2 items", "Re-price 2 items"))
            fn()
        self.assertEqual(len(added), 2)
        self.assertNotIn("rating", self.app.notes)
        self.assertFalse(self.app.records[1].get("rating_changed"))
        self.app.records.clear()

    def test_a_429_pauses_until_a_search(self):
        self.app.engine.paused = self.app.engine.rate_stopped = False
        self.app.ev_rate_stop("The trade site asked us to slow down - try again in 60 s")
        self.assertTrue(self.app.engine.paused)
        self.app.records.clear()
        self.app.records[1] = self.rec(1)
        with mock.patch.object(self.app.engine, "add", lambda *a, **k: None):
            self.app.reprice([1])
        self.assertFalse(self.app.engine.paused, "pressing Search again goes on")
        self.app.records.clear()

    def test_saved_listings_have_no_seller_or_whisper(self):
        from soe2 import trade
        e = {"id": "abc", "item": {"name": "x"}, "listing": {"price": {"amount": 1, "currency": "divine"},
             "account": {"name": "Seller#1234"}, "whisper": "@Seller hi", "whisper_token": "t", "stash": {"name": "s"}}}
        out = trade.scrub_raw(e)
        self.assertEqual(out["listing"], {"price": {"amount": 1, "currency": "divine"}})
        self.assertIn("account", e["listing"], "the copy in memory is left as it is")
        trade.RAW_LISTINGS["abc"] = e
        self.app.records.clear()
        self.app.records[1] = self.rec(1, src="pc", stages=[{"ids": ["abc"]}])
        saved = {}
        with mock.patch("soe2.app.save_json", lambda name, data: saved.update({name: data})):
            self.app.save_session()
        raw = saved["session.json"]["records"][0]["_raw"]
        self.assertNotIn("Seller", repr(raw))
        self.assertNotIn("whisper", repr(raw))
        trade.RAW_LISTINGS.pop("abc", None)
        self.app.records.clear()

    def test_chat_command_has_no_newline(self):
        from soe2 import overlay
        sent = []
        overlay.type_chat("/hideout\nsecond", sender=lambda *a, **k: sent.append(a), sleep=lambda s: None,
                          clip=(lambda: "", lambda t: sent.append(("clip", t))))
        self.assertIn(("clip", "/hideout second"), [x for x in sent if x and x[0] == "clip"])


class Usage(unittest.TestCase):
    def test_usage_count_is_opt_in(self):
        from soe2 import usage
        old = SETTINGS.pop("usage_ping", None)
        try:
            self.assertFalse(usage.on(), "off until you say yes")
            calls = []
            usage.ping(call=lambda *a, **k: calls.append(a) or (False, None))
            self.assertFalse([c for c in calls if c[1] == "/usage/ping"], "nothing with an id is sent while off")
        finally:
            if old is not None:
                SETTINGS["usage_ping"] = old


if __name__ == "__main__":
    unittest.main()
