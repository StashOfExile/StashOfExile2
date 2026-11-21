"""3.0.7 (GGG policy audit risk 3): nothing searches the trade site for your own account's listings, and the app keeps
no account name. Bulk Pricing's "Add from stash tab" and Wealth's synced tabs are removed; the first start of the new
version deletes the saved account name and every stash-tab price (migrations.no_stash_reading_307).

    python3.12 -m unittest tests.test_no_stash_reading          (or tests/runall.sh)"""
import json
import os
import sys
import tempfile
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-nostash-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import migrations as MG                          # noqa: E402
from soe2.config import P, SETTINGS                        # noqa: E402


class Migration(unittest.TestCase):
    def old_settings(self):
        return {"wealth_account": "SecretStreamer#4242", "own_markers": [[37882, "divine"], [62555, "chaos"]],
                "stash_order": "rows", "wealth_skip_tab": True, "notices_closed": {"pctab_beta": True, "other": True},
                "pctab": {"mode": "Stash tab", "amount": 1, "currency": "divine", "read_ok": True, "current": "t2",
                          "tabs": [{"id": "t1", "name": "Tab 1", "amount": 62555, "currency": "chaos",
                                    "currency_name": "Chaos Orb"},
                                   {"id": "t2", "name": "Rings", "amount": 37882, "currency": "divine"},
                                   {"id": "t3", "name": "Tab 3", "renamed": False, "amount": 5, "currency": "exalted"}]}}

    def write_session(self, srcs):
        recs = [{"id": i, "src": s, "item": {"mods": []}} for i, s in enumerate(srcs, 1)]
        with open(P("session.json"), "w", encoding="utf-8") as f:
            json.dump({"records": recs}, f)
        self.addCleanup(lambda: os.path.exists(P("session.json")) and os.remove(P("session.json")))

    def test_account_and_prices_are_deleted(self):
        self.write_session(["manual", "tab:t2", "tab:t3"])
        with open(P("tab_reader_log.txt"), "w") as f:
            f.write("a log")
        S = self.old_settings()
        MG._no_stash_reading_307(S)
        for k in ("wealth_account", "own_markers", "stash_order", "wealth_skip_tab"):
            self.assertNotIn(k, S)
        self.assertEqual(S["notices_closed"], {"other": True})
        self.assertNotIn("SecretStreamer", json.dumps(S))
        self.assertEqual(set(S["pctab"]), {"tabs", "current"}, "no mode, price or currency left")
        for t in S["pctab"]["tabs"]:
            self.assertEqual(set(t), {"id", "name", "renamed"}, "a tab has no price")
        self.assertFalse(os.path.exists(P("tab_reader_log.txt")))

    def test_tabs_become_plain_lists(self):
        self.write_session(["manual", "tab:t2", "tab:t3"])
        S = self.old_settings()
        MG._no_stash_reading_307(S)
        tabs = S["pctab"]["tabs"]
        self.assertEqual([t["id"] for t in tabs], ["manual", "t2", "t3"],
                         "Manually Add's list is Tab 1; a stash tab's list with items stays; an empty one goes")
        self.assertEqual(tabs[1], {"id": "t2", "name": "Rings", "renamed": True})
        self.assertFalse(tabs[2]["renamed"])
        self.assertEqual(S["pctab"]["current"], "t2", "the shown tab stays shown")

    def test_nobody_used_stash_tabs(self):
        self.write_session(["manual", "manual"])
        S = {"wealth_account": "Me#1", "pctab": {"mode": "Manual Add", "tabs": [{"id": "t1", "name": "Tab 1",
                                                                                "amount": None}], "current": "t1"}}
        MG._no_stash_reading_307(S)
        self.assertEqual(S["pctab"], {"tabs": [{"id": "manual", "name": "Tab 1", "renamed": False}],
                                      "current": "manual"})

    def test_no_session_no_settings(self):
        S = {}
        MG._no_stash_reading_307(S)
        self.assertEqual(S["pctab"]["tabs"], [{"id": "manual", "name": "Tab 1", "renamed": False}])

    def test_it_is_a_settings_step(self):
        step = next(s for s in MG.STEPS if s[0] == "no_stash_reading_307")
        self.assertEqual(step[2], "settings")
        self.assertNotIn("wealth_account", SETTINGS, "not a default any more")


class Gone(unittest.TestCase):
    def test_no_account_search_left(self):
        from soe2 import engine, trade, wealth
        for mod, names in ((trade, ("own_account", "is_own", "OWN_SKIPPED")),
                           (wealth, ("WealthJobs", "wealth_query", "WEALTH_SYNC", "parse_trade_link")),
                           (engine.Engine, ("pctab_start", "wealth_start", "do_wealth_search", "do_pctab_search"))):
            for n in names:
                self.assertFalse(hasattr(mod, n), n)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "tabreader.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "soe2", "tabreader_page.py")))

    def test_no_search_sends_an_account_filter(self):
        """No code builds a trade search with an account filter ("account": {"input": ...})."""
        hits = []
        for f in sorted(os.listdir(os.path.join(ROOT, "soe2"))):
            if f.endswith(".py"):
                with open(os.path.join(ROOT, "soe2", f), encoding="utf-8") as fh:
                    src = fh.read()
                if '"account": {"input"' in src or "'account': {'input'" in src:
                    hits.append(f)
        self.assertEqual(hits, [])

    def test_own_listings_are_not_left_out(self):
        """Other price checkers don't know your account: every listing counts, a seller shows on the card."""
        from soe2 import pcpop
        self.assertFalse(hasattr(pcpop.PricePopup, "_pcpop_mine"))


if __name__ == "__main__":
    unittest.main()
