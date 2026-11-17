"""Farming Strategies › New strat (3.0.6, the approved mockup) and the League filter.

  * Atlas masters: at most 4 picks a master (a 5th click does nothing and says so)
  * the League filter: your league (Settings) by default, All leagues shows every strat; a strat's league is its own,
    else its game version's (LEAGUE_VERSIONS), else "Game <version>"; the Drawer's Filters ▾ has it
  * a copied tablet / waystone (the one read of a copy key press, through app.accept_clip) drops in as a card; its
    ticks make the Made for you regex and trade search (base, ticked mods, 10+ uses / tier + Endgame filters)
  * Save strat (the one orange button, grayed until a name, a mechanic and one step) and Edit: the same page, filled
  * .txt, CSV and JSON keep the league, the Atlas masters and the ticked mods; older strats still load and keep
    their own numbers

    python3.12 -m unittest tests.test_strats_new          (or tests/runall.sh)"""
import json
import os
import sys
import tempfile
import time
import tkinter as tk
import types
import unittest
from urllib.parse import unquote

HOME = tempfile.mkdtemp(prefix="soe2-stratnew-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
os.environ.setdefault("SOE2_NO_BOARD", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from soe2 import moneymakers as MM                      # noqa: E402
from soe2.config import SETTINGS, save_json            # noqa: E402
import test_strats_find as TF                           # noqa: E402


def fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", "pricecheck_items.txt"), encoding="utf-8") as f:
        text = f.read()
    for b in text.split("=== ")[1:]:
        head, _, body = b.partition("\n")
        if head.strip() == name:
            return body
    raise KeyError(name)


TABLET, TABLET2, WAY = fixture("rare_tablet_breach"), fixture("magic_tablet_used"), fixture("rare_waystone")
OLD = TF.strat("old-breach", "Old breach strat", patch="0.4", thoughts_per_click=1, clicks_per_hour="Frantic")
NOW = TF.strat("rites-breach", "Rites breach strat", patch="0.5.5")


class Data(unittest.TestCase):
    def test_masters_one_master_max_four(self):
        ms = {}
        m = "Hilda's Hunting"
        for c in MM.MASTERS[m][:4]:
            ms, what = MM.master_pick(ms, m, c)
            self.assertEqual(what, "on")
        ms2, what = MM.master_pick(ms, m, MM.MASTERS[m][4])
        self.assertEqual(what, "full", "a 5th pick does nothing")
        self.assertEqual(ms2, ms)
        ms3, what = MM.master_pick(ms, m, MM.MASTERS[m][0])
        self.assertEqual((what, len(ms3[m])), ("off", 3))
        ms4, what = MM.master_pick(ms, "Jado's Spycraft", "Long Days")
        self.assertEqual((what, ms4), ("switch", {"Jado's Spycraft": ["Long Days"]}), "one master: the old picks go")
        self.assertTrue(MM.masters_ok(ms))
        self.assertFalse(MM.masters_ok({m: list(MM.MASTERS[m][:5])}), "5 of one master")
        self.assertFalse(MM.masters_ok({m: ["Not a choice"]}))
        self.assertFalse(MM.masters_ok({m: ["Mighty Prey"], "Jado's Spycraft": ["Long Days"]}), "two masters")
        self.assertIn("masters", MM.validate(dict(NOW, masters={"Nobody": ["x"]}))[0])
        self.assertEqual([len(d) for d in MM.MASTERS.values()], [12, 12, 12])
        self.assertEqual(MM.MASTERS["Doryani's Science"][:6], ("Evolutionary Pressure", "Stitch the Flesh",
                                                               "Refined Formula", "Disengaged Safeties",
                                                               "Improved Calibration", "Careful Procurement"),
                         "the game's order: 3 across, 4 down")

    def test_farming_only(self):
        self.assertEqual(MM.CATEGORIES, ("Mapping", "Bossing"))
        crafting = dict(NOW, id="craft", category="Crafting", type="Tablet crafting")
        self.assertFalse(MM.is_farming(crafting))
        self.assertTrue(MM.validate(crafting), "not in the layout any more")
        old = {"id": "old-craft", "name": "x", "category": "Crafting", "clicks_per_hour": 600, "steps": ["a"]}
        self.assertEqual(MM.migrate(old)["category"], "Crafting", "migrate maps nothing silently")

    def test_league_of(self):
        self.assertEqual(MM.LEAGUE_VERSIONS["Forbidden Rites"], "0.5.5")
        self.assertEqual(MM.league_of(NOW), "Forbidden Rites", "from its game version")
        self.assertEqual(MM.league_of(OLD), "Game 0.4", "unknown: its game version")
        self.assertEqual(MM.league_of(dict(OLD, league="SSF Forbidden Rites")), "Forbidden Rites", "its own wins")
        self.assertEqual(MM.league_base("HC SSF Forbidden Rites (PL123)"), "Forbidden Rites")
        self.assertEqual(MM.league_text("Forbidden Rites"), "Forbidden Rites · 0.5.5")
        self.assertEqual(MM.league_text("Standard"), "Standard")

    def test_cards_and_made_for_you(self):
        c = MM.copied_card(TABLET)
        self.assertEqual((c["kind"], c["base"], c["uses"], c["ticked"]), ("tablet", "Breach Tablet", 10, []))
        self.assertEqual(len(c["mods"]), 3)
        c["ticked"] = [c["mods"][0]]
        m = MM.made_for_you("tablet", [c], "Forbidden Rites", sid_of=lambda line: "explicit.stat_1",
                            uses_sid="implicit.uses")
        self.assertTrue(m["regex"], "a stash regex for the ticked mod")
        q = json.loads(unquote(m["url"].split("?q=", 1)[1]))
        self.assertEqual(q["query"]["type"], "Breach Tablet")
        self.assertEqual(q["query"]["stats"][0], {"type": "and", "filters": [{"id": "explicit.stat_1"}]})
        self.assertEqual(q["query"]["stats"][1]["filters"][0], {"id": "implicit.uses", "value": {"min": 10}})
        self.assertIn("10+ uses", m["caption"])
        c2 = MM.copied_card(TABLET2)
        c2["ticked"] = list(c2["mods"])
        m2 = MM.made_for_you("tablet", [c, c2], "Forbidden Rites", sid_of=lambda line: "s" + str(len(line)))
        q2 = json.loads(unquote(m2["url"].split("?q=", 1)[1]))
        self.assertEqual(q2["query"]["stats"][0]["type"], "count", "several tablets: any of the ticked mods")
        w = MM.copied_card(WAY)
        self.assertEqual((w["kind"], w["tier"]), ("waystone", 15))
        self.assertNotIn("Revives Available: 0", w["mods"], "a 0 searches nothing")
        w["ticked"] = ["Item Rarity: +32%"]
        mw = MM.made_for_you("waystone", [w], "Forbidden Rites")
        self.assertIn("rar", mw["regex"])
        self.assertIn("map_iir", unquote(mw["url"]))
        self.assertIn("map_tier", unquote(mw["url"]))
        self.assertEqual(mw["caption"], "Tier 15 · 1 ticked mod")
        self.assertIsNone(MM.copied_card(fixture("normal_tablet").replace("Tablet", "Ring")))

    def test_text_csv_json_keep_new_fields(self):
        c = MM.copied_card(TABLET)
        c["ticked"] = [c["mods"][1]]
        w = MM.copied_card(WAY)
        w["ticked"] = ["Pack Size: +16%"]
        s = dict(NOW, league="Forbidden Rites", masters={"Jado's Spycraft": ["Long Days", "Stolen Relics"]},
                 items=[MM.card_item(w), MM.card_item(c)])
        self.assertEqual(MM.validate(s), [])
        for back in (MM.from_text(MM.to_text(s)), MM.from_csv(MM.to_csv(s)),
                     json.loads(json.dumps(MM.tidy(s)))):
            self.assertEqual(MM.validate(back), [])
            for k in ("league", "masters", "items"):
                self.assertEqual(back.get(k), s[k], k)
        self.assertEqual(MM.item_card(s["items"][1])["ticked"], [c["mods"][1]], "the ticks come back")
        self.assertEqual(MM.item_card(s["items"][1])["mods"], c["mods"], "and the unticked lines")
        old_txt = MM.to_text(OLD).replace("Profit per hour (div, older strats - runs say it now)",
                                          "Est. profit per hour (div, e.g. 5-10)")    # (a file from before 3.0.6)
        self.assertEqual(MM.from_text(old_txt)["est_profit"], OLD["est_profit"])

    def test_board_compat(self):
        s = dict(NOW, league="Forbidden Rites", masters={"Jado's Spycraft": ["Long Days"]},
                 items=[{"kind": "tablet", "base": "Breach Tablet", "count": 1, "mods": ["a"], "rarity": "Rare"}])
        b = MM.board_compat(s)
        self.assertNotIn("league", b)
        self.assertNotIn("masters", b)
        self.assertEqual(b["items"], [{"kind": "tablet", "base": "Breach Tablet", "count": 1}])


class Page(unittest.TestCase):
    """New strat in the Farming Strategies page (the same stand-in for the app as test_strats_find)."""
    setUpClass = classmethod(TF.Page.setUpClass.__func__)
    tearDownClass = classmethod(TF.Page.tearDownClass.__func__)

    def setUp(self):
        SETTINGS["league"] = "Forbidden Rites"
        save_json(MM.FILE, {"schema": MM.SCHEMA, "revision": 999, "strats": TF.STRATS + [OLD, NOW], "oneliners": []})
        save_json(MM.MINE, [])
        for w in self.root.winfo_children():
            w.destroy()
        self.app = TF.make_app(self.root)
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.app.build_money_window(self.body)
        self.pump()

    def tearDown(self):
        SETTINGS["league"] = ""

    def pump(self, n=6):
        TF.Page.pump(self, n)
        if self.app.mm_new_cv._job:
            self.app.mm_new_cv.redraw()
        self.root.update()

    # ---- the League filter
    def test_league_filter(self):
        self.assertEqual(self.app.mm_league.get(), "Forbidden Rites", "your league by default")
        self.assertEqual([r["s"]["id"] for r in self.app.mm_find_rows], ["rites-breach"])
        self.assertIn("League: Forbidden Rites", self.app.mm_drops["league"].cget("text"))
        lefts = [k["w"] for k in self.app.mm_bar._flow_lefts]
        self.assertIs(lefts[0], self.app.mm_sbox, "the search box first")
        self.assertIs(lefts[1], self.app.mm_drops["league"], "then League, the first filter")
        self.assertTrue(self.app.mm_filter_words().upper().startswith("FORBIDDEN RITES"))
        self.app.mm_budget.set("Mid budget")
        self.assertEqual(self.app.mm_filter_words().upper(), "FORBIDDEN RITES · MID BUDGET")
        self.app.mm_budget.set("Any")
        self.app.mm_league_set(MM.ALL_LEAGUES)
        self.pump()
        self.assertEqual(len(self.app.mm_find_rows), 5, "All leagues: every strat")
        self.assertIn("clear", self.app.mm_find_cv.acts, "away from your league: Clear filters")
        self.app.mm_clear_filters()
        self.assertEqual(self.app.mm_league.get(), "Forbidden Rites", "Clear filters: your league again")
        m = self.app.mm_drop_menu("league")
        labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) != "separator"]
        self.assertTrue(labels[0].startswith(MM.ALL_LEAGUES))
        self.assertTrue(any(lab.startswith("Forbidden Rites · 0.5.5  (yours)") for lab in labels))
        self.assertTrue(any(lab.startswith("Game 0.4") for lab in labels))
        self.app._drawer = True
        self.app.mm_drawer_look(True)
        fm = self.app.mm_drop_menu("filters")
        self.assertTrue(fm.entrycget(0, "label").startswith("League: "), "the Drawer's Filters ▾ has it first")

    def test_league_empty_state(self):
        SETTINGS["league"] = "Some New League"
        self.app.mm_league.set(self.app.mm_league_default())
        self.app.mm_filters_changed()
        self.pump()
        self.assertEqual(self.app.mm_find_rows, [])
        cv = self.app.mm_find_cv
        self.assertIn("empty_btn", cv.acts)
        cv.acts["empty_btn"]()
        self.pump()
        self.assertEqual(self.app.mm_league.get(), MM.ALL_LEAGUES, "its one button: All leagues")
        self.assertEqual(len(self.app.mm_find_rows), 5)

    # ---- New strat
    def fill(self, name="Breach in juiced T15 maps"):
        a = self.app
        a.mm_add()
        self.pump()
        a.mm_new_take_clip(TABLET)
        a.mm_new_take_clip(WAY)
        a.mm_new_tick(0, a.mm_nd["cards"][0]["mods"][0])
        a.mm_new_tick("way", "Item Rarity: +32%")
        a.mm_nw["name"].var.set(name)
        a.mm_new_pick("typ", "Breach")
        a.mm_new_pick("budget", "Mid budget")
        for c in ("Refined Formula", "Improved Calibration"):
            a.mm_new_master("Doryani's Science", c)
        a.mm_nw["steps"][0].var.set("Put your atlas points into Breach.")
        a.mm_nw["loot"].var.set("Breach splinters, Catalysts")
        self.pump()

    def test_new_page_one_orange_and_needs(self):
        a = self.app
        a.mm_add()
        self.pump()
        cv = a.mm_new_cv
        self.assertTrue(a.mm_new_on)
        self.assertFalse(a.mm_find_f.winfo_manager(), "an in-page view: Find hides")
        self.assertEqual(cv.primaries, [], "Save strat is grayed until it's ready")
        self.assertNotIn("nw_save", cv.acts)
        self.assertEqual(a.mm_new_missing(), ["a name", "a mechanic", "one step"])
        self.assertEqual(cv.itemcget(cv.find_withtag("nw_needs")[0], "text"), "Needs: a name, a mechanic, one step")
        for tag in ("nw_league_i", "nw_eff_i"):
            self.assertTrue(cv.tips.get(tag), tag)
        self.fill()
        self.assertEqual(cv.primaries, ["Save strat"], "one orange button")
        self.assertIn("nw_save", cv.acts)
        self.assertEqual(len(a.mm_nw["steps"]), 2, "a new empty step appears when the last is filled")
        self.assertIn("nw_cancel", cv.acts)
        self.assertIn("nw_rm_0", cv.tips, "the icon-only ✕ has a tooltip")
        self.assertIn("nw_copy_tablet", cv.acts)
        self.assertIn("nw_trade_waystone", cv.acts)
        cv.acts["nw_cancel"]()
        self.pump()
        self.assertFalse(a.mm_new_on)
        self.assertTrue(a.mm_find_f.winfo_manager(), "Cancel: back to Find")

    def test_masters_on_page(self):
        a = self.app
        a.mm_add()
        self.pump()
        m = "Jado's Spycraft"
        for c in MM.MASTERS[m][:4]:
            self.assertEqual(a.mm_new_master(m, c), "on")
        self.assertEqual(a.mm_new_master(m, MM.MASTERS[m][5]), "full")
        self.assertEqual(len(a.mm_nd["masters"][m]), 4)
        self.assertTrue(any("4 of 4 used" in x for x in a.said))
        self.pump()
        cv = a.mm_new_cv
        self.assertIn("4 of 4 used", cv.tips.get("nw_ms_2_5", ""))
        self.assertIn("nw_mtab_0", cv.acts, "one master at a time: a tab each")
        self.assertNotIn("nw_ms_0_0", cv.acts, "only the shown master's choices")
        cv.acts["nw_mtab_0"]()
        self.pump()
        self.assertIn("nw_mswitch", cv.find_all() and [t_ for i in cv.find_all() for t_ in cv.gettags(i)],
                      "says that ticking here switches the master")
        self.assertEqual(a.mm_new_master("Doryani's Science", "Refined Formula"), "switch")
        self.assertEqual(a.mm_nd["masters"], {"Doryani's Science": ["Refined Formula"]}, "one master a strat")
        self.pump()
        cv.acts["nw_mclear"]()
        self.assertEqual(a.mm_nd["masters"], {})

    def test_mechanics_multi(self):
        a = self.app
        a.mm_add()
        for t_ in ("Breach", "Delirium", "Ritual"):
            a.mm_new_pick("mech", t_)
        self.assertEqual((a.mm_nd["typ"], a.mm_nd["also"]), ("Breach", ["Delirium", "Ritual"]), "the first is main")
        a.mm_new_pick("mech", "Breach")
        self.assertEqual((a.mm_nd["typ"], a.mm_nd["also"]), ("Delirium", ["Ritual"]), "the next becomes main")
        a.mm_new_pick("mech", "Juiced mapping")
        self.assertEqual((a.mm_nd["typ"], a.mm_nd["also"]), ("Juiced mapping", ["Delirium", "Ritual"]))
        self.pump()
        cv = a.mm_new_cv
        words = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        self.assertIn("✓ Delirium", words)
        self.assertTrue(any(w.startswith("Main: Juiced mapping · also uses Delirium, Ritual") for w in words))
        a.mm_nw["name"].var.set("Juiced")
        a.mm_nw["steps"][0].var.set("Go.")
        out = a.mm_new_save()
        self.assertEqual(out["type"], "Juiced mapping")
        self.assertEqual([x for x in out["tags"] if x in MM.TAG_GROUPS["Also uses"]], ["Delirium", "Ritual"])
        a.mm_edit()
        self.assertEqual((a.mm_nd["typ"], a.mm_nd["also"]), ("Juiced mapping", ["Delirium", "Ritual"]))
        a.mm_new_more()
        self.pump()
        self.assertFalse([t_ for t_ in a.mm_new_cv.acts if t_.startswith("nw_tag_Also uses")],
                         "Also uses is part 1's Mechanic, not a More details row")

    def test_copies(self):
        a = self.app
        a.mm_add()
        self.pump()
        self.assertTrue(a.mm_new_capturing())
        for _ in range(4):
            self.assertIsNotNone(a.mm_new_take_clip(TABLET))
        self.assertIsNone(a.mm_new_take_clip(TABLET2), "up to 4 tablets")
        self.assertTrue(any("4 of 4" in x for x in a.said))
        a.mm_new_remove(3)
        self.assertEqual(len(a.mm_nd["cards"]), 3)
        self.assertIsNone(a.mm_new_take_clip("Item Class: Rings\nRarity: Rare\nX\nRuby Ring\n--------\n"),
                          "only tablets and waystones")
        a.mm_new_take_clip(WAY)
        self.assertEqual(a.mm_nd["way"]["base"], "Waystone (Tier 15)")
        self.assertEqual(a.mm_new_made("tablet")["regex"], "", "no tick: no regex")
        a.mm_new_tick(0, a.mm_nd["cards"][0]["mods"][2])
        self.assertTrue(a.mm_new_made("tablet")["regex"])
        self.pump()
        self.assertEqual(a.mm_new_copy("tablet"), self.root.clipboard_get())
        a.mm_new_close()
        self.pump()
        self.assertFalse(a.mm_new_capturing(), "closed: copies go where they always went")

    def test_copy_key_reaches_new_strat(self):
        """The owner's case: Top Up's key is Ctrl+C, the price check key Ctrl+D, listen on - a plain Ctrl+C, a
        Ctrl+Alt+C or Ctrl+D on a tablet while New strat is open lands there (through clip_read_once: one read)."""
        from soe2 import clipread
        from soe2.app import App
        from soe2.utilities_page import UtilitiesPage
        a = self.app
        a.mm_add()
        self.pump()
        logged = []
        keys = types.SimpleNamespace(active=True, combo_recent=lambda *x: False, copy_recent=lambda *x: True,
                                     pc_recent=lambda *x: False, tu_recent=lambda *x: False, hook_stale=lambda *x: False)
        a.keys = keys
        a.last_clip, a.own_clip, a.records = "", "", {}
        a._clip_ignored = lambda text: False
        a.topup_wants = lambda text: True                # (Top Up's key is Ctrl+C: it would take it - but after us)
        a.topup_take = lambda text: False
        a.wealth_takes = lambda text: False
        a.pc_wants = lambda text: True                   # (Ctrl+D: Price Checks would take it)
        a.pc_take = lambda text: logged.append("priced")
        a.gate_ok = lambda text: False                   # (a plain Ctrl+C isn't Bulk Pricing's)
        a.accept_clip = lambda text: logged.append("bulk")
        old_reader, old_logger = clipread.READER[0], clipread.LOGGER[0]
        clipread.LOGGER[0] = logged.append
        try:
            for key, text in (("Ctrl+C", TABLET), ("Ctrl+Alt+C", TABLET2), ("Ctrl+D", WAY)):
                clipread.READER[0] = lambda text=text: text
                gid = clipread.grant(key, hold=key)
                clipread.release(key)
                self.assertEqual(App.clip_read_once(a, gid), "New strat", key)
            self.assertEqual(len(a.mm_nd["cards"]), 2)
            self.assertEqual(a.mm_nd["way"]["base"], "Waystone (Tier 15)")
            self.assertIn("Ctrl+C pressed: read the clipboard once for New strat", logged)
            self.assertNotIn("priced", logged)
            clipread.READER[0] = lambda: "Item Class: Rings\nRarity: Rare\nX\nRuby Ring\n--------\n"
            gid = clipread.grant("Ctrl+D", hold="Ctrl+D")
            clipread.release("Ctrl+D")
            self.assertEqual(App.clip_read_once(a, gid), "Price Checks", "not a tablet: where it always went")
            a.mm_new_close()
            clipread.READER[0] = lambda: TABLET
            gid = clipread.grant("Ctrl+D", hold="Ctrl+D")
            clipread.release("Ctrl+D")
            self.assertEqual(App.clip_read_once(a, gid), "Price Checks", "closed: nothing for New strat")
        finally:
            clipread.READER[0], clipread.LOGGER[0] = old_reader, old_logger
        # the key watcher hears a plain Ctrl+C while it's open (Top Up off, listen off)
        listen = SETTINGS.get("listen", True)
        try:
            SETTINGS["listen"] = False
            on = types.SimpleNamespace(w_counting=False, fd_capturing=lambda: False, fl_capturing=lambda: False,
                                       fl_ed_open=lambda: False, mm_new_capturing=lambda: True,
                                       topup_key_is_copy=lambda: False, mp_on=lambda: False)
            self.assertTrue(UtilitiesPage.clip_wanted(on, True), "Ctrl+Alt+C")
            self.assertTrue(UtilitiesPage.clip_wanted(on, False), "plain Ctrl+C")
        finally:
            SETTINGS["listen"] = listen

    def test_modifiers_synced_on_c(self):
        """Ctrl+Alt+C heard as Ctrl+C: a missed Alt key-down left Alt "up"; on C, Windows' own state wins."""
        from soe2.winsys import KeyWatch
        k = KeyWatch()
        k.feed(0xA2, True, False)                        # Ctrl down; Alt's key-down never reached the hook
        user32 = types.SimpleNamespace(GetAsyncKeyState=lambda vk: 0x8000 if vk in (0x11, 0x12) else 0)
        k.sync_mods(user32)
        seen = []
        k.listener = lambda vk, c, a_, s: seen.append((vk, c, a_, s)) and False
        k.feed(0x43, True, False)
        self.assertEqual(seen[-1], (0x43, True, True, False))
        self.assertGreater(k.combo_time, 0, "a Ctrl+Alt+C")

    def test_save_edit_round_trip(self):
        a = self.app
        self.fill()
        a.mm_costs()["_new1"] = {"prices": {"0": 0.2, "1": 0.3}, "at": time.time()}
        a.mm_nd["cost_sid"], a.mm_nd["cost_items"] = "_new1", a.mm_new_items()
        cost, _busy = a.mm_new_cost()
        self.assertAlmostEqual(cost["value"], 0.2 + 0.3 / 10)
        self.assertEqual(cost["sum"], "waystone 0.2 + tablet 0.3 ÷ 10 runs", "Cost per map, written out")
        self.pump()
        self.assertIn("nw_cost_i", a.mm_new_cv.tips)
        out = a.mm_new_save()
        self.assertIsNotNone(out)
        self.assertFalse(a.mm_new_on)
        mine = MM.mine()
        self.assertEqual([s["id"] for s in mine], [out["id"]])
        s = mine[0]
        self.assertEqual(MM.validate(s), [])
        self.assertEqual(s["league"], "Forbidden Rites")
        self.assertEqual(s["patch"], "0.5.5")
        self.assertEqual(s["masters"], {"Doryani's Science": ["Refined Formula", "Improved Calibration"]})
        self.assertEqual((s["category"], s["type"]), ("Mapping", "Breach"))
        self.assertEqual((s["thoughts_per_click"], s["clicks_per_hour"]), MM.EFFORTS["Moderate"])
        self.assertIn("Mid budget", s["tags"])
        self.assertNotIn("est_profit", s, "profit an hour comes from runs")
        self.assertEqual(s["waystone_tiers"], {"min": 15, "max": 15})
        self.assertEqual(s["loot"], ["Breach splinters", "Catalysts"])
        tab = next(i for i in s["items"] if i["kind"] == "tablet")
        self.assertEqual((tab["lasts"], tab["key_mods"], len(tab["mods"])), (10, [tab["mods"][0]], 3))
        self.assertIn(s["id"], a.mm_costs(), "it starts with its Cost per map")
        self.assertTrue(a.mm_detail_on, "saved: opened, in Mine")
        self.pump()
        self.assertIn("masters_i", a.mm_detail_cv.tips, "the opened strat shows its Atlas masters")
        # Edit: the same page, filled in
        a.mm_edit()
        self.pump()
        self.assertTrue(a.mm_new_on)
        self.assertEqual(a.mm_nw["name"].var.get(), "Breach in juiced T15 maps")
        self.assertEqual(a.mm_nd["cards"][0]["ticked"], [tab["mods"][0]])
        self.assertEqual(a.mm_nd["way"]["ticked"], ["Item Rarity: +32%"])
        self.assertEqual(a.mm_nd["masters"], s["masters"])
        a.mm_new_pick("effort", "Hard")
        a.mm_nw["steps"][1].var.set("Sell the splinters.")
        out2 = a.mm_new_save()
        self.assertEqual(out2["id"], s["id"], "edited, not copied")
        s2 = MM.mine()[0]
        self.assertEqual(len(MM.mine()), 1)
        self.assertEqual(s2["steps"], ["Put your atlas points into Breach.", "Sell the splinters."])
        self.assertEqual(s2["thoughts_per_click"], MM.EFFORTS["Hard"][0])
        # export / import keep the new fields
        for ext in (".txt", ".json", ".csv"):
            path = os.path.join(HOME, "strat" + ext)
            a.mm_current = lambda s2=s2: dict(s2, origin="mine")
            a.mm_write_strat(dict(s2, origin="mine"), path)
            save_json(MM.MINE, [])
            self.assertEqual(a.mm_import(path), 1, ext)
            back = MM.mine()[0]
            for k in ("league", "masters", "items", "steps", "loot"):
                self.assertEqual(back.get(k), s2.get(k), f"{ext}: {k}")

    def test_old_strat_edit_keeps_its_numbers(self):
        a = self.app
        save_json(MM.MINE, [dict(OLD, id="my-old")])
        a.mm_view_set("Mine")
        a.mm_league_set(MM.ALL_LEAGUES)
        a.mm_open("my-old|mine")
        self.pump()
        a.mm_edit()
        self.pump()
        d = a.mm_nd
        self.assertEqual((d["typ"], d["effort"]), ("Breach", "Easy"))
        self.pump()
        out = a.mm_new_save()
        self.assertEqual((out["thoughts_per_click"], out["clicks_per_hour"]), (1, "Frantic"),
                         "Effort untouched: its own numbers stay")
        self.assertEqual(out["est_profit"], OLD["est_profit"], "an older estimate is kept")
        self.assertEqual(out["patch"], "0.4")
        self.assertNotIn("league", out, "an older strat keeps going by its game version")


if __name__ == "__main__":
    unittest.main()
