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
                                                               "Archaic Corruption", "Disengaged Safeties",
                                                               "Improved Calibration", "Careful Procurement"),
                         "the game's order: 3 across, 4 down")

    def test_map_type_and_retag(self):
        self.assertEqual(MM.TAG_GROUPS["Map type"], ("City", "Juiced maps", "Low-tier maps", "Campaign zones"))
        self.assertNotIn("Farm type", MM.TAG_GROUPS)
        old = dict(NOW, tags=["City area farm", "Sacred Bloom farm", "Mid budget"])
        new = MM.migrate(old)
        self.assertEqual(new["tags"], ["City", "Mid budget"], "City area farm is City; Sacred Bloom farm goes")
        self.assertEqual(MM.validate(new), [])

    def test_device_slots(self):
        s = dict(NOW, tablets=["3× Breach tablets with Unstable Breaches"], waystone_tiers={"min": 15, "max": 15})
        sl = MM.device_slots(s)
        self.assertEqual([(x["kind"], x["base"], x["count"]) for x in sl],
                         [("waystone", "Waystone (Tier 15)", 1), ("tablet", "Breach Tablet", 3)], "from the text")
        s2 = dict(NOW, items=[{"kind": "waystone", "base": "Waystone (Tier 16)", "count": 1},
                              {"kind": "tablet", "base": "Ritual Tablet", "count": 2}])
        self.assertEqual([(x["word"], x["sub"]) for x in MM.device_slots(s2)],
                         [("Waystone", "Tier 16"), ("Ritual", "2 needed")])

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
        self.assertEqual(q["query"]["stats"][0], {"type": "and", "filters": [{"id": "explicit.stat_1",
                                                                                 "value": {"min": 25}}]},
                         "its number is the minimum")
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


class Art(unittest.TestCase):
    def test_waystone_tier_icons(self):
        """A waystone's picture by its tier: the trade site's static list (Waystones), the shipped one last."""
        from soe2 import pricecheck_page as PCP
        from soe2.config import P
        save_json(P("trade_static.json"), {"result": [
            {"id": "Waystones", "label": "Waystones", "entries": [
                {"id": "waystone-tier-7", "text": "Waystone (Tier 7)", "image": "/gen/image/t7.png"},
                {"id": "waystone-tier-15", "text": "Waystone (Tier 15)", "image": "https://x.example/t15.png"}]},
            {"id": "Currency", "entries": [{"id": "chaos", "text": "Chaos Orb", "image": "/c.png"}]}]})
        os.utime(P("trade_static.json"), (time.time() + 5, time.time() + 5))
        try:
            self.assertEqual(PCP.waystone_tier_icons(), {7: "https://web.poecdn.com/gen/image/t7.png",
                                                         15: "https://x.example/t15.png"})
            self.assertEqual(PCP.art_url("Waystone (Tier 7)"), "https://web.poecdn.com/gen/image/t7.png")
            self.assertEqual(PCP.art_url("Waystone (Tier 3)"), PCP.icons().get("Waystone"), "else the shipped one")
        finally:
            os.remove(P("trade_static.json"))
            self.assertEqual(PCP.waystone_tier_icons(), {}, "(gone with its file)")


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
        a.mm_new_pick("mech", "Breach")
        a.mm_new_pick("budget", "Mid budget")
        for c in ("Archaic Corruption", "Improved Calibration"):
            a.mm_new_master("Doryani's Science", c)
        a.mm_nw["steps"][0].var.set("Put your atlas points into Breach.")
        a.mm_nw["loot"].var.set("Breach splinters, Catalysts")
        a.mm_new_loot_add()
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
        for tag in ("nw_mech_i", "nw_eff_i", "nw_i2"):
            self.assertTrue(cv.tips.get(tag), tag)
        self.assertEqual(cv.tips["nw_eff_i"], "How much thinking and clicking a map takes.")
        words = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        for w in ("1 · What you farm", "2 · In your map device", "3 · Atlas master", "4 · How it goes", "5 · Notes",
                  "HOW IT SHOWS IN FIND", "COST PER MAP", "PARTS", "MAP TYPE", "MAP CONTENT", "BOSSES"):
            self.assertIn(w, words, "the mockup's parts, in its words")
        self.assertNotIn("More details", " ".join(words))
        self.fill()
        self.assertEqual(cv.primaries, ["Save strat"], "one orange button")
        self.assertIn("nw_save", cv.acts)
        self.assertEqual(len(a.mm_nw["steps"]), 2, "a new empty step appears when the last is filled")
        self.assertIn("nw_cancel", cv.acts)
        self.assertIn("nw_slot_0", cv.menus, "right-click a copied slot: remove it")
        self.assertIn("nw_trade_waystone", cv.acts, "the last copy's mods show: the waystone's")
        a.mm_new_select(0)
        self.pump()
        self.assertIn("nw_copy_tablet", cv.acts, "a slot clicked: its mods")
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
        jado = list(MM.MASTERS).index(m)
        self.assertIn("4 of 4 used", cv.tips.get(f"am_{jado}_5", ""))
        self.assertIn("am_tab_0", cv.acts, "the master list: one each")
        self.assertNotIn("am_0_0", cv.acts, "only the shown master's choices")
        self.assertIn("4 of 4 ✓", self.words(cv), "the list says how many points it has")
        cv.acts["am_tab_0"]()
        self.pump()
        self.assertIn("nw_mswitch", cv.find_all() and [t_ for i in cv.find_all() for t_ in cv.gettags(i)],
                      "says that ticking here switches the master")
        self.assertEqual(a.mm_new_master("Doryani's Science", "Archaic Corruption"), "switch")
        self.assertEqual(a.mm_nd["masters"], {"Doryani's Science": ["Archaic Corruption"]}, "one master a strat")
        self.pump()
        self.assertIn("1 · Archaic Corruption".split(" · ")[1], self.words(cv), "the picks, numbered")
        self.assertIn("one more point", self.words(cv))
        cv.acts["am_clear"]()
        self.assertEqual(a.mm_nd["masters"], {})

    def test_mechanics_multi(self):
        a = self.app
        a.mm_add()
        for t_ in ("Breach", "Delirium", "Ritual"):
            a.mm_new_pick("mech", t_)
        self.assertEqual(a.mm_nd["mechs"], ["Breach", "Delirium", "Ritual"])
        self.assertEqual(a.mm_new_type(), "Breach", "the first is the main one")
        a.mm_new_pick("mech", "Breach")
        self.assertEqual(a.mm_new_type(), "Delirium", "the next becomes the main one")
        self.pump()
        cv = a.mm_new_cv
        words = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        self.assertIn("✓ Delirium", words)
        self.assertIn("MAIN", words)
        self.assertIn("ALSO", words)
        a.mm_new_pick("cat", "Bossing")
        self.assertEqual(a.mm_new_missing()[1:2], ["a boss"], "Bossing: its boss")
        a.mm_new_pick("bosses", "Simulacrum")
        a.mm_new_pick("maptype", "Juiced maps")
        a.mm_new_pick("content", "Towers")
        a.mm_nw["name"].var.set("Delirium into Simulacrums")
        a.mm_nw["steps"][0].var.set("Go.")
        out = a.mm_new_save()
        self.assertEqual((out["category"], out["type"]), ("Bossing", "Simulacrum"))
        self.assertTrue({"Delirium", "Ritual", "Simulacrum", "Juiced maps", "Towers"} <= set(out["tags"]))
        a.mm_edit()
        self.assertEqual((a.mm_nd["cat"], a.mm_nd["mechs"], a.mm_nd["bosses"]),
                         ("Bossing", ["Delirium", "Ritual"], ["Simulacrum"]))

    def test_city_auto(self):
        a = self.app
        a.mm_add()
        for _ in range(3):
            a.mm_new_take_clip(TABLET)
        self.assertNotIn("City", a.mm_nd["maptype"])
        a.mm_new_take_clip(TABLET2)
        self.assertEqual((a.mm_nd["maptype"], a.mm_nd["city_auto"]), (["City"], True), "a 4th tablet: City")
        self.pump()
        words = [a.mm_new_cv.itemcget(i, "text") for i in a.mm_new_cv.find_all() if a.mm_new_cv.type(i) == "text"]
        self.assertIn("AUTO", words)
        self.assertIn("(only Cities have a 4th slot)", words)
        a.mm_new_remove(3)
        self.assertEqual(a.mm_nd["maptype"], [], "the app's tick goes with the 4th tablet")

    def test_loot_and_notes(self):
        a = self.app
        a.mm_add()
        a.mm_new_loot_add("Voices, Raven's Reflection")
        self.pump()
        self.assertIn("nw_loot_0", a.mm_new_cv.acts)
        a.mm_new_cv.acts["nw_loot_0"]()
        self.assertEqual(a.mm_nd["loot"], ["Raven's Reflection"], "✕ removes it")
        a.mm_nw["name"].var.set("x")
        a.mm_new_pick("mech", "Ritual")
        a.mm_nw["steps"][0].var.set("Go.")
        a.mm_nw["tips"].insert("1.0", "Tip one\nTip two")
        a.mm_nw["source"].var.set("Discord, Sep 15")
        self.assertIsNone(a.mm_new_save(), "a source needs its link")
        self.assertIn("link", a.mm_nd["msg"][0])
        a.mm_nw["source"].var.set("https://example.com/guide GimmickNL's guide")
        out = a.mm_new_save()
        self.assertEqual(out["tips"], ["Tip one", "Tip two"])
        self.assertEqual(out["sources"], [{"title": "GimmickNL's guide", "url": "https://example.com/guide"}])

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
        """The owner's case: the price check key is Ctrl+D, listen on - a plain Ctrl+C, a
        Ctrl+Alt+C or Ctrl+D on a tablet while New strat is open lands there (through clip_read_once: one read)."""
        from soe2 import clipread
        from soe2.app import App
        from soe2.utilities_page import UtilitiesPage
        a = self.app
        a.mm_add()
        self.pump()
        logged = []
        keys = types.SimpleNamespace(active=True, combo_recent=lambda *x: False, copy_recent=lambda *x: True,
                                     pc_recent=lambda *x: False, hook_stale=lambda *x: False)
        a.keys = keys
        a.last_clip, a.own_clip, a.records = "", "", {}
        a._clip_ignored = lambda text: False
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
                                       mp_on=lambda: False)
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
        self.assertEqual(cost["sum"], "0.2 + 0.3 ÷ 10 uses", "Cost per map, written out")
        self.assertTrue(cost["how"].startswith("Waystone 0.2 + Breach tablet 0.3 ÷ 10 uses, at today's prices"))
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
        self.assertEqual(s["masters"], {"Doryani's Science": ["Archaic Corruption", "Improved Calibration"]})
        self.assertEqual((s["category"], s["type"]), ("Mapping", "Breach"))
        self.assertEqual((s["thoughts_per_click"], s["clicks_per_hour"]), MM.EFFORTS["Easy"])
        self.assertIn("Mid budget", s["tags"])
        self.assertNotIn("est_profit", s, "profit an hour comes from runs")
        self.assertEqual(s["waystone_tiers"], {"min": 15, "max": 15})
        self.assertEqual(s["loot"], ["Breach splinters", "Catalysts"])
        tab = next(i for i in s["items"] if i["kind"] == "tablet")
        self.assertEqual((tab["lasts"], tab["key_mods"], len(tab["mods"])), (10, [tab["mods"][0]], 3))
        self.assertIn(s["id"], a.mm_costs(), "it starts with its Cost per map")
        self.assertTrue(a.mm_detail_on, "saved: opened, in Mine")
        self.pump()
        dv = a.mm_detail_cv
        self.assertTrue([k for k in dv.tips if k.startswith("am_")], "the opened strat shows its Atlas master")
        self.assertFalse([k for k in dv.acts if k.startswith("am_")], "read only there")
        for tag in ("tile_ph_i", "tile_cost_i", "tile_way", "tile_master"):
            self.assertIn(tag, dv.tips, tag)
        self.assertEqual(dv.primaries, ["Run this strat"])
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
        self.assertEqual(a.mm_nd["loot"], ["Breach splinters", "Catalysts"])
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

    def test_art_downloads_and_draws(self):
        """The owner saw no tablet / waystone pictures: the shipped art (the waystone's too) downloads once, is kept
        in the art cache, and the opened strat and New strat draw it."""
        import io
        import requests
        from PIL import Image
        from soe2 import pricecheck_page as PCP
        a = self.app
        for name in ("pc_art", "_pc_art_get", "_pc_art_poll", "_pc_art_path", "_pc_art_init"):
            setattr(a, name, types.MethodType(getattr(PCP.PriceCheckPage, name), a))
        buf = io.BytesIO()
        Image.new("RGBA", (78, 78), (200, 80, 40, 255)).save(buf, "PNG")
        got = []

        class Answer:
            status_code, content = 200, buf.getvalue()
        a._pc_art_init()
        for url in (PCP.WAYSTONE_ICON, PCP.TABLET_ICONS["Breach Tablet"]):    # (a test before may have kept it:
            for k in [k for k in a._pc_art_cache if k.split("#")[0] == url]:  # the Linux build machine downloads
                a._pc_art_cache.pop(k)
            if os.path.exists(a._pc_art_path(url)):                          # for real)
                os.remove(a._pc_art_path(url))
        orig = requests.get
        requests.get = lambda url, **k: (got.append(url), Answer())[1]
        try:
            s = dict(NOW, id="my-art", items=[{"kind": "waystone", "base": "Waystone (Tier 15)", "count": 1},
                                             {"kind": "tablet", "base": "Breach Tablet", "count": 3}])
            save_json(MM.MINE, [s])
            a.mm_view_set("Mine")
            a.mm_open("my-art|mine")
            dv = a.mm_detail_cv
            for _ in range(300):                                   # (a slow CI runner needs longer)
                self.pump(2)
                if len([i for i in dv.find_all() if dv.type(i) == "image"]) >= 3 and len(set(got)) >= 2:
                    break
                time.sleep(0.05)
            self.assertIn(PCP.WAYSTONE_ICON, got, "the waystone's picture (any tier) ships with the app")
            self.assertIn(PCP.TABLET_ICONS["Breach Tablet"], got)
            images = [i for i in dv.find_all() if dv.type(i) == "image"]
            self.assertGreaterEqual(len(images), 3, "drawn: the hero's tablet, the Waystone tile, the slots")
            self.assertTrue(os.path.exists(a._pc_art_path(PCP.WAYSTONE_ICON)), "kept in the art cache")
            a.mm_add()
            a.mm_new_take_clip(WAY)
            self.pump()
            cv = a.mm_new_cv
            self.assertTrue([i for i in cv.find_withtag("nw_slot_way") if cv.type(i) == "image"],
                            "New strat: the copied waystone's picture")
        finally:
            requests.get = orig

    def words(self, cv):
        return [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]

    def test_waystone_by_hand(self):
        """No waystone to copy (mockup v3): its tier (16 squares) and its WAYSTONE MODIFIERS with Min and Max, as a
        waystone reads them - nothing goes in the slot until Done; Cancel adds nothing."""
        from soe2.waystone import PROPS, WAYSTONE_HEADERS
        a = self.app
        a.mm_add()
        self.pump()
        cv = a.mm_new_cv
        self.assertIn("nw_slot_way", cv.acts, "an empty slot: click it to pick by hand")
        cv.acts["nw_slot_way"]()
        self.pump()
        self.assertEqual(a.mm_nd["hand"]["kind"], "waystone")
        self.assertEqual(list(a.mm_nw["hand_props"]), [PROPS[k][1] for k in WAYSTONE_HEADERS], "the header numbers")
        self.assertEqual(list(a.mm_nw["hand_props"]), ["Waystone Drop Chance", "Item Rarity", "Pack Size",
                                                       "Monster Rarity", "Monster Effectiveness", "Revives Available"])
        w_ = self.words(cv)
        for x in ("Waystone by hand", "WAYSTONE MODIFIERS", "· Min and Max, either can stay empty", "Item Rarity:",
                  "Revives Available:"):
            self.assertIn(x, w_, x)
        self.assertNotIn("ADD A MOD", w_, "a waystone's mods aren't picked")
        self.assertEqual(w_.count("%"), 10, "a unit after each Min and Max - Revives has none")
        self.assertEqual(w_.count("to"), 6, "Min to Max on every line")
        self.assertEqual([f"nw_ht_{n}" in cv.acts for n in range(1, 17)], [True] * 16, "Tier 1-16")
        self.assertEqual(cv.tips.get("nw_hand_x"), "Close without adding")
        self.assertEqual(cv.primaries, [], "Done greyed until a tier is picked")
        self.assertIn("Finish or cancel the picker first", cv.tips.get("nw_save", ""), "Save waits")
        a.mm_new_hand_set("tier", 15)
        a.mm_nw["hand_props"]["Item Rarity"].var.set("30")
        a.mm_nw["hand_props"]["Revives Available"].var.set("1")
        self.pump()
        self.assertEqual(cv.primaries, ["Done"], "while the picker is open, Done is the one orange button")
        self.assertIsNone(a.mm_nd["way"], "nothing in the slot before Done")
        self.assertEqual(a.mm_new_hand_summary(),
                         "Waystone (Tier 15) · Item Rarity 30% or more, Revives Available 1 or more")
        a.mm_nw["hand_props_max"]["Item Rarity"].var.set("60")
        self.assertEqual(a.mm_new_hand_summary(),
                         "Waystone (Tier 15) · Item Rarity 30 to 60%, Revives Available 1 or more")
        a.mm_nw["hand_props_max"]["Item Rarity"].var.set("")
        cv.acts["nw_hand_cancel"]()
        self.pump()
        self.assertIsNone(a.mm_nd["way"], "Cancel: nothing added")
        cv.acts["nw_slot_way"]()
        a.mm_new_hand_set("tier", 15)
        a.mm_nw["hand_props"]["Item Rarity"].var.set("30")
        a.mm_nw["hand_props"]["Revives Available"].var.set("1")
        self.pump()
        cv.acts["nw_hand_done"]()
        w = a.mm_nd["way"]
        self.assertEqual((w["base"], w["tier"], w["hand"]), ("Waystone (Tier 15)", 15, True))
        self.assertEqual(w["ticked"], ["Item Rarity: +30%", "Revives Available: 1"])
        m = a.mm_new_made("waystone")
        q = unquote(m["url"])
        for part in ('"map_iir":{"min":30}', '"map_revives":{"min":1}', '"map_tier":{"min":15,"max":15}'):
            self.assertIn(part, q)
        self.pump()
        self.assertIn("T15 · by hand", self.words(cv))
        self.assertIsNone(a.mm_nd["hand"], "Done closes it")
        cv.acts["nw_slot_way"]()                          # opens again with what it has
        self.assertEqual((a.mm_nd["hand"]["tier"], a.mm_nw["hand_props"]["Item Rarity"].var.get()), (15, "30"))

    def test_tablet_by_hand(self):
        a = self.app
        a.mm_add()
        a.mm_new_hand_menu(x=0, y=0)
        a.mm_last_menu.invoke(1)                         # Pick by hand ▾ › Tablet
        self.pump()
        cv = a.mm_new_cv
        self.assertEqual(a.mm_nd["hand"]["kind"], "tablet")
        types_ = list(MM.hand_tablet_types())
        self.assertIn("Breach Tablet", types_)
        self.assertIn("Irradiated Tablet", types_)
        self.assertEqual(cv.primaries, [], "Done greyed until a type is picked")
        a.mm_new_hand_set("ttype", "Breach Tablet")
        self.pump()
        self.assertEqual(a.mm_nd["hand"]["rows"], {}, "a type picks nothing for you")
        self.assertEqual(cv.primaries, ["Done"])
        w_ = self.words(cv)
        for x in ("PREFIX 1", "PREFIX 2", "SUFFIX 1", "SUFFIX 2", "Pick a prefix…", "Pick a suffix…"):
            self.assertIn(x, w_, x)
        self.assertNotIn("(any value)", " ".join(w_))
        self.assertIn("added by name", cv.tips.get("nw_huniq", ""), "the unique note: the button's tooltip")
        self.assertFalse([x for x in w_ if "lists every unique tablet" in x], "no mockup annotation on the page")
        b = cv.bbox("nw_hand_done")
        self.assertLess(b[2] - cv.bbox("nw_slot_way")[0], 660, "the picker: at most 650 px, under the slots")
        pre, suf = MM.hand_tablet_affixes("Breach Tablet")
        cv.acts["nw_hrow_p1"]()
        self.pump()
        self.assertEqual(a._mm_hand_options("p1"), pre, "only this type's prefixes")
        a.mm_nw["hand_q"].var.set("pack size")
        self.pump()
        self.assertEqual(a._mm_hand_options("p1"), ["(5—7)% increased Pack Size in Map"], "the search narrows it")
        a.mm_new_hand_choose("p1", "(5—7)% increased Pack Size in Map")
        self.assertNotIn("(5—7)% increased Pack Size in Map", a._mm_hand_options("p2"), "not the one Prefix 1 has")
        a.mm_nw["hand_q"].var.set("")
        self.assertEqual(a._mm_hand_options("s1"), suf, "the suffixes: only this type's")
        pick = "Breaches in Map have (5—15)% increased Pack Size"
        a.mm_new_hand_choose("s1", pick)
        a.mm_nw["hand_rows"]["s1"].var.set("12")
        self.assertEqual(a.mm_new_hand_summary(), "Breach Tablet · 10 uses · 2 mods")
        self.pump()
        self.assertEqual(cv.primaries, ["Done"], "one orange button")
        cv.acts["nw_hand_done"]()
        c = a.mm_nd["cards"][0]
        self.assertEqual((c["base"], c["uses"], c["hand"]), ("Breach Tablet", 10, True))
        self.assertEqual(c["ticked"], ["5% increased Pack Size in Map", "Breaches in Map have 12% increased Pack Size"],
                         "its minimum in the line (else its lowest)")
        m = MM.made_for_you("tablet", [dict(c, ticked=c["ticked"][1:])], "Standard",
                            sid_of=lambda line: "explicit.pack", uses_sid="implicit.uses")
        q = json.loads(unquote(m["url"].split("?q=", 1)[1]))
        self.assertEqual(q["query"]["stats"][0]["filters"], [{"id": "explicit.pack", "value": {"min": 12}}])
        self.assertTrue(a.mm_new_made("tablet")["regex"])
        a.mm_costs()["_new1"] = {"prices": {"0": 0.3}, "at": time.time()}
        a.mm_nd["cost_sid"], a.mm_nd["cost_items"] = "_new1", [i for i in a.mm_new_items()]
        self.assertIn("by hand", a.mm_new_cost()[0]["how"], "the sum's tooltip says it")
        a.mm_nw["name"].var.set("By hand")
        a.mm_new_pick("mech", "Breach")
        a.mm_nw["steps"][0].var.set("Go.")
        out = a.mm_new_save()
        self.assertEqual(out["items"][0]["key_mods"][1], "Breaches in Map have 12% increased Pack Size")

    def test_tablet_row_any(self):
        """3.0.6 (owner): a tablet row can be 'Any' - it shows, has no number box, and is not searched for."""
        a = self.app
        a.mm_add()
        a.mm_new_hand_menu(x=0, y=0)
        a.mm_last_menu.invoke(1)
        a.mm_new_hand_set("ttype", "Breach Tablet")
        self.pump()
        cv = a.mm_new_cv
        cv.acts["nw_hrow_p1"]()
        self.pump()
        self.assertIn("Any - it doesn't matter", self.words(cv), "first in the list")
        self.assertIn("isn't searched", cv.tips.get("nw_hopt_p1_0", ""))
        a.mm_new_hand_choose("p1", "Any")
        a.mm_new_hand_choose("s1", "Breaches in Map have (5—15)% increased Pack Size")
        self.assertEqual(a.mm_new_hand_summary(), "Breach Tablet · 10 uses · 1 mod · 1 any")
        self.pump()
        self.assertIn("Any - it doesn't matter", self.words(cv), "the row says it")
        cv.acts["nw_hand_done"]()
        self.assertEqual(a.mm_nd["cards"][0]["ticked"], ["Breaches in Map have 5% increased Pack Size"],
                         "Any is not a mod")

    def test_no_master_needed(self):
        """3.0.6 (owner): 'No atlas master needed' - the part is done with no picks; a pick turns it off."""
        a = self.app
        a.mm_add()
        a.mm_new_master("Jado's Spycraft", MM.MASTERS["Jado's Spycraft"][0])
        self.pump()
        cv = a.mm_new_cv
        cv.acts["nw_nomaster"]()
        self.pump()
        self.assertEqual((a.mm_nd["no_master"], a.mm_nd["masters"]), (True, {}), "on clears the picks")
        w_ = " ".join(self.words(cv))
        self.assertIn("This strat works without an atlas master.", w_)
        self.assertIn("✓ Atlas master · none needed", w_)
        a.mm_new_master("Jado's Spycraft", MM.MASTERS["Jado's Spycraft"][1])
        self.assertFalse(a.mm_nd["no_master"], "a pick turns it off")

    def test_unique_tablet(self):
        """★ Unique ▾: every unique tablet, added by name - its slot, the trade search and a copy of one."""
        a = self.app
        names = MM.unique_tablets()
        self.assertGreaterEqual(len(names), 5)
        name = next(iter(names))
        a.mm_add()
        a.mm_new_hand_open(0)
        self.pump()
        cv = a.mm_new_cv
        cv.acts["nw_huniq"]()
        self.pump()
        self.assertEqual(set(a._mm_hand_options("unique")), set(names), "every unique tablet")
        self.assertIn("nw_hopt_unique_0", cv.acts)
        a.mm_new_hand_choose("unique", name)
        self.pump()
        self.assertNotIn("PREFIX 1", self.words(cv), "a unique: no affix rows")
        cv.acts["nw_hand_done"]()
        c = a.mm_nd["cards"][0]
        self.assertEqual((c["name"], c["rarity"], c.get("unique")), (name, "Unique", True))
        from soe2 import stratcost as SC
        m = a.mm_new_made("tablet")
        self.assertIn(name, unquote(m["url"]).replace("+", " "), "Made for you: by name")
        item = MM.card_item(c)
        q, _a, _b = SC.query(item)
        self.assertEqual(q["query"]["name"], name, "the Trade Site query: by name")
        slots = MM.device_slots({"items": [item]})
        self.assertTrue(any(s_.get("word") == name for s_ in slots), "its slot shows its name")
        txt = ("Item Class: Tablet\nRarity: Unique\n" + name + "\n" + names[name] + "\n--------\nUses Remaining: 3\n")
        self.assertEqual(MM.unique_from_text(txt)[0], name, "a copied unique lands by name")

    def test_tiles_fill_the_row(self):
        """A tile with nothing to say goes; the rest share the row evenly (no lone tile, no gap) - Tier 1–15."""
        a = self.app
        s = dict(NOW, id="tiles", items=[{"kind": "waystone", "base": "Waystone (Tier 15)", "count": 1}],
                 waystone_tiers={"min": 1, "max": 15}, masters={})
        s.pop("items")
        save_json(MM.MINE, [s])
        a.mm_league_set(MM.ALL_LEAGUES)
        a.mm_view_set("Mine")
        a.mm_open("tiles|mine")
        self.pump()
        dv = a.mm_detail_cv
        dv.redraw()
        boxes = dv.tile_boxes
        self.assertNotIn("master", boxes, "no master: no tile")
        ws = {round(b[2] - b[0]) for b in boxes.values()}
        self.assertEqual(len(ws), 1, f"even widths: {boxes}")
        right = max(b[2] for b in boxes.values())
        self.assertGreater(right, dv.winfo_width() - 60, "they fill the row")
        self.assertIn("Tier 1–15", self.words(dv))
        self.assertEqual(MM._tiers_words({"min": 1, "max": 15}), "Tier 1–15")

    def test_unique_tablets_every_source(self):
        """The unique tablets: game data + the trade site's list + poe.ninja's UniqueTablets, each addable by hand
        (the list shows every one - Visions of Paradise was past the 8th) and by copy."""
        from soe2.config import P
        save_json(P("wealth_prices.json"), {"v": 3, "parts": {"UniqueTablets": {"lines": [
            ["Visions of Paradise", "Irradiated Tablet", 0.2, 10, False],
            ["Newer Than The Data", "Breach Tablet", 0.1, 3, False]]}}})
        os.utime(P("wealth_prices.json"), (time.time() + 7, time.time() + 7))
        try:
            names = MM.unique_tablets()
            self.assertEqual(names.get("Newer Than The Data"), "Breach Tablet", "poe.ninja's list counts")
            for n in ("Visions of Paradise", "Mastered Domain", "Clear Skies", "Season of the Hunt"):
                self.assertIn(n, names)
            a = self.app
            a.mm_add()
            a.mm_new_hand_open(0)
            a.mm_new_hand_dropdown("unique")
            self.pump()
            cv = a.mm_new_cv
            shown = [cv.tips.get(f"nw_hopt_unique_{i}") for i in range(len(names))]
            self.assertEqual(shown, list(names), "every one is in the list")
            for n, base in names.items():
                a.mm_new_hand_open(0)
                a.mm_new_hand_choose("unique", n)
                c = a.mm_new_hand_done()
                self.assertEqual((c["name"], c["base"]), (n, base), "added by hand: " + n)
                txt = f"Item Class: Tablet\nRarity: Unique\n{n}\n{base}\n--------\nUses Remaining: 3\n"
                self.assertEqual(MM.unique_from_text(txt)[:2], (n, base), "by copy: " + n)
        finally:
            os.remove(P("wealth_prices.json"))

    def test_ninja_icons_learned(self):
        """poe.ninja's item overview carries each unique's picture: kept with the prices and learned into the
        app's picture list - no request of its own; a cached part without pictures is fetched in full once."""
        from soe2 import pricecheck_page as PCP
        from soe2 import wealth as W
        url = "https://web.poecdn.com/gen/image/abc/MasteredDomain.png"
        bodies = {"Currency": {"core": {"primary": "divine"}, "items": [{"id": "divine", "name": "Divine Orb"}],
                               "lines": [{"id": "divine", "primaryValue": 1}]},
                  "UniqueTablets": {"lines": [{"name": "Mastered Domain", "baseType": "Irradiated Tablet",
                                               "primaryValue": 0.3, "listingCount": 4, "icon": url},
                                              {"name": "No Picture", "baseType": "Breach Tablet", "primaryValue": 1,
                                               "icon": "/relative.png"}]}}
        wp = W.WealthPrices()
        asked = []
        wp._get = lambda typ, league: (asked.append(typ), bodies.get(typ, {}))[1]
        orig = W.Rates.names_for
        W.Rates.names_for = staticmethod(lambda league: [league])
        try:
            wp.ensure("Standard", force=True)
        finally:
            W.Rates.names_for = orig
        self.assertEqual(wp.parts["UniqueTablets"]["icons"], {"Mastered Domain": url}, "https pictures only")
        self.assertEqual(PCP.icons().get("Mastered Domain"), url, "learned: every unique gets its picture")
        self.assertEqual(PCP.art_url("Mastered Domain"), url)
        self.assertEqual(PCP.icons_learn({"Mastered Domain": url}), 0, "unchanged: icons.json isn't written")
        self.assertEqual(len(asked), len(W.NINJA_EXCHANGE_TYPES) + len(W.NINJA_ITEM_TYPES), "no extra requests")
        # a part cached before pictures were kept: asked in full (no ETag), once
        sent = []

        class R:
            status_code, headers = 200, {"ETag": "e2"}

            def raise_for_status(self):
                pass

            def json(self):
                return {"lines": []}
        orig_get = W.requests.get
        W.requests.get = lambda *a_, **k: (sent.append(k.get("headers") or {}), R())[1]
        try:
            wp2 = W.WealthPrices()
            wp2.src, wp2.etags, wp2.parts = "Standard", {"UniqueTablets": "e1", "UniqueRelics": "e1"}, {
                "UniqueTablets": {"lines": []}, "UniqueRelics": {"lines": [], "icons": {}}}
            wp2._get("UniqueTablets", "Standard")
            wp2._get("UniqueRelics", "Standard")
        finally:
            W.requests.get = orig_get
        self.assertNotIn("If-None-Match", sent[0], "no pictures yet: asked in full")
        self.assertEqual(sent[1].get("If-None-Match"), "e1", "with pictures: the ETag as before")

    def test_atlas_master_text(self):
        """What a choice does: atlasmasters.json (when it has it) - in the details on hover and in each tile's
        tooltip, on New strat and on the opened strat; missing file or choice: the plain line."""
        from soe2.config import P
        m = "Doryani's Science"
        ch = MM.MASTERS[m][0]
        a = self.app
        a.mm_add()
        a.mm_new_master_tab(m)
        self.pump()
        cv = a.mm_new_cv
        i = list(MM.MASTERS).index(m)
        save_json(P("atlasmasters.json"), {"version": 1, "game_version": "0.5.5", "masters": {
            m: {ch: {"text": "Monsters evolve faster.", "source": "game data"}}}})
        try:
            self.assertEqual(MM.master_text(m, ch), "Monsters evolve faster.")
            self.assertIsNone(MM.master_text(m, MM.MASTERS[m][1]), "a choice it lacks: nothing")
            a.mm_new_cv.redraw()
            self.assertIn("Monsters evolve faster.", cv.tips[f"am_{i}_0"], "the tile's tooltip")
            hover = [new for _it, _old, new in cv.lifts[f"am_{i}_0"]]
            self.assertIn({"text": "Monsters evolve faster."}, hover, "the details column on hover")
            self.assertIn({"text": "What it does shows here when the game data has it."},
                          [new for _it, _old, new in cv.lifts[f"am_{i}_1"]], "a choice it lacks: the plain line")
            s = dict(NOW, id="mt", masters={m: [ch]})
            save_json(MM.MINE, [s])
            a.mm_league_set(MM.ALL_LEAGUES)
            a.mm_view_set("Mine")
            a.mm_open("mt|mine")
            self.pump()
            a.mm_detail_cv.redraw()
            self.assertIn("Monsters evolve faster.", a.mm_detail_cv.tips[f"am_{i}_0"], "the opened strat too")
        finally:
            os.remove(P("atlasmasters.json"))
        self.assertNotEqual(MM.master_text(m, ch), "Monsters evolve faster.", "(gone with its file)")

    def test_tracker_new_is_new_strat(self):
        """Strat Tracker's ＋ New strat opens the same New strat page as Find's (no second way to make one)."""
        import inspect
        from soe2.ledger_page import LedgerPage
        a = self.app
        self.assertIn('text="＋ New strat", command=self.fl_new_strat', inspect.getsource(LedgerPage.build_ledger))
        a.mm_page.pick("Strat Tracker", notify=False)
        a._fl_to_strats = types.MethodType(LedgerPage._fl_to_strats, a)
        LedgerPage.fl_new_strat(a)
        self.pump()
        self.assertTrue(a.mm_new_on, "the New strat page")
        self.assertEqual(a.mm_page.current(), "Find") if hasattr(a.mm_page, "current") else None

    def test_example_strats_render_all_sections(self):
        """Every example strat opens with all its parts - a broken one used to leave the hero empty."""
        from soe2 import buglog
        a = self.app
        orig = buglog.caught
        boom = []
        buglog.caught = lambda *x, **k: boom.append(x)
        gimmick = {"id": "gimmick", "name": "Delirium into Simulacrums (Doryani)", "type": "Bossing",
                   "subtype": "Simulacrum", "tags": ["Delirium", "Breach", "Simulacrum"],
                   "masters": {"Doryani's Science": MM.MASTERS["Doryani's Science"][:4]},
                   "sources": ["GimmickNL on YouTube", "https://example.org/x"], "steps": ["Run it."]}
        try:
            every = [dict(s, id=f"ex{i}") for i, s in enumerate(list(TF.STRATS) + [OLD, NOW, gimmick])]
            save_json(MM.MINE, every)
            a.mm_league_set(MM.ALL_LEAGUES)
            a.mm_view_set("Mine")
            for s in every:
                a.mm_open(f"{s['id']}|mine")
                self.pump()
                a.mm_detail_cv.redraw()
                dv = a.mm_detail_cv
                self.assertEqual(boom, [], s.get("name"))
                tips = set(dv.tips) | set(dv.acts)
                self.assertTrue(tips, s.get("name"))
                self.assertIn("Run this strat", dv.primaries, s.get("name"))
                w_ = self.words(dv)
                self.assertIn(s["name"], w_, "the hero: its name")
            self.assertTrue([k for k in dv.tips if k.startswith("am_")], "the master card")
            self.assertIn("GimmickNL on YouTube", " ".join(self.words(dv)), "a plain source line shows")
        finally:
            buglog.caught = orig

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
        self.assertEqual((a.mm_new_type(), d["effort"]), ("Breach", "Easy"))
        self.pump()
        out = a.mm_new_save()
        self.assertEqual((out["thoughts_per_click"], out["clicks_per_hour"]), (1, "Frantic"),
                         "Effort untouched: its own numbers stay")
        self.assertEqual(out["est_profit"], OLD["est_profit"], "an older estimate is kept")
        self.assertEqual(out["patch"], "0.4")
        self.assertNotIn("league", out, "an older strat keeps going by its game version")


if __name__ == "__main__":
    unittest.main()


class RenamedChoice(unittest.TestCase):
    def test_refined_formula_is_archaic_corruption(self):
        from soe2 import moneymakers as M
        old = {"name": "x", "category": "Mapping", "type": "Juiced mapping", "clicks_per_hour": "Steady",
               "masters": {"Doryani's Science": ["Refined Formula", "Improved Calibration"]}}
        self.assertEqual(M.migrate(old)["masters"], {"Doryani's Science": ["Archaic Corruption", "Improved Calibration"]})
        self.assertIn("Archaic Corruption", M.MASTERS["Doryani's Science"])
