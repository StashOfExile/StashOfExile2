"""gamedb.json (Game Search's offline game database), 3.0.6: the build tool's checks (a bad row fails the build and
nothing is written), the hide list (a wrong row removed with no rebuild), Game Search showing the new categories, and
the Path of Exile 1 leftovers filter of tools/build_searchdata.py.

    python3.12 -m unittest tests.test_gamedb          (or tests/runall.sh; needs a display, e.g. Xvfb :99)"""
import json
import os
import re
import shutil
import sys
import tempfile
import tkinter as tk
import unittest

HOME = tempfile.mkdtemp(prefix="soe2-gamedb-test-")
for _k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[_k] = HOME
os.environ["SOE2_TRADE_API"] = "http://127.0.0.1:9/api/trade2"
os.environ["SOE2_NINJA"] = "http://127.0.0.1:9"
os.environ["SOE2_GAMEDB_KEEP_HOME"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_gamedb as BG                                  # noqa: E402
import build_searchdata as BS                              # noqa: E402
from soe2 import config, gamesearch, names                 # noqa: E402

FILES = ("gamedata.json", "searchdata.json", "modlists.json", "regexdata.json", "mapdata.json", "trialdata.json", "anointdata.json", "atlasmasters.json",
         "campaign.json", "crafthelper.json", "soe2/moneymakers.py", "soe2/waystone.py", "soe2/vaallens_plan.py",
         "soe2/medallions.py", "soe2/ritualaltars.py", "soe2/sekhemas.json", "tests/fixtures/gamedb_samples.txt")


def copy_root():
    d = tempfile.mkdtemp(prefix="soe2-gamedb-root-")
    for f in FILES:
        os.makedirs(os.path.dirname(os.path.join(d, f)), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, f), os.path.join(d, f))
    return d


def edit_json(root, name, fn):
    p = os.path.join(root, name)
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    fn(d)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


class AtlasMastersFile(unittest.TestCase):
    """atlasmasters.json (3.0.6): the 36 master choices match MASTERS; text comes from an allowed source only."""

    def test_names_match_masters_and_sources_clean(self):
        from soe2.moneymakers import MASTERS
        with open(os.path.join(ROOT, "atlasmasters.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual({m: set(c) | {x.split(" / ", 1)[1] for x in d["missing"] if x.startswith(m + " / ")}
                          for m, c in d["masters"].items()}, {m: set(c) for m, c in MASTERS.items()})
        self.assertEqual(sum(len(v) for v in MASTERS.values()), 36)
        for m, ch in d["masters"].items():
            for c, e in ch.items():
                self.assertTrue(e["text"].strip() and e["source"].startswith("https://"), (m, c))
                self.assertIsNone(BG.BLACKLIST.search(e["text"] + e["source"]), (m, c))
        self.assertIsNone(BG.BLACKLIST.search(json.dumps(d["conflicts"]).replace("game8", "")))


class BuildChecks(unittest.TestCase):
    def test_real_data_builds_clean(self):
        b = BG.Build().run()
        self.assertEqual(b.fail, [])
        n = {g: sum(1 for r in b.rows if r["group"] == g) for g in BG.GROUPS}
        self.assertEqual(n["Tablets"], 8 + 86)                       # 8 tablet types + 86 tablet mods
        self.assertEqual(n["Waystones"], 6 + 16 + 32)                # header numbers, tiers, mods
        self.assertEqual(n["Atlas Masters"], 3 + 36)
        self.assertEqual(n["Ritual Altars"], 10)
        self.assertEqual(n["Trial of Chaos"], 11 + 8 + 5 + 1 + 2)    # modifiers, wagers, items, Ruin, areas
        self.assertTrue(all(n[g] for g in BG.GROUPS), n)
        for r in b.rows:                                             # every row has what Game Search shows
            for f in ("id", "name", "group", "class", "text", "source", "version"):
                self.assertTrue(r[f], (r["id"], f))
        self.assertGreater(b.n_samples, 5)

    def test_file_is_current(self):
        self.assertEqual(BG.main(["--check"]), 0)                   # gamedb.json is what the build makes now

    def test_groups_are_the_one_name_list(self):
        self.assertEqual(BG.GROUPS, names.GAME_SEARCH_GROUPS)
        for g in names.GAME_SEARCH_GROUPS:
            self.assertTrue(names.title_case(g), g)

    def test_masters_have_no_invented_effects(self):
        b = BG.Build().run()
        ch = [r for r in b.rows if r["class"] == "Atlas Master Choice"]
        self.assertEqual(len(ch), 36)
        with open(os.path.join(ROOT, "atlasmasters.json"), encoding="utf-8") as f:
            am = json.load(f)
        for r in ch:                                                   # text only from atlasmasters.json, else "not in the data"
            m = r["props"][0][1]
            e = am["masters"][m].get(r["name"])
            self.assertEqual(r["lines"], e["text"].split("\n") if e else [BG.NOT_IN_DATA], r["name"])
            self.assertEqual(r["source"], e["source"] if e else "soe2/moneymakers.py MASTERS")
        sk = [r for r in b.rows if r["group"] == "Trial of the Sekhemas"]
        self.assertEqual(len(sk), 85)
        self.assertTrue(all(r["text"] == BG.NOT_IN_DATA for r in sk))    # no ratings, no "why"

    def test_trial_of_chaos_comes_only_from_the_export(self):
        b = BG.Build().run()
        tc = [r for r in b.rows if r["group"] == "Trial of Chaos"]
        ver = BG.read_json(BG.ROOT, "trialdata.json").get("game_version")            # follows the export
        self.assertTrue(all(r["version"] == ver and "RePoE" in r["source"] for r in tc))
        names_ = {r["name"] for r in tc}
        for n in ("Cowardly Fate", "Deadly Fate", "Victorious Fate", "Inscribed Ultimatum", "Ruin",
                  "The Trialmaster's Reliquary Key", "The Trial of Chaos", "Trial Modifier: of Exposure"):
            self.assertIn(n, names_)
        exp = next(r for r in tc if r["name"] == "Trial Modifier: of Exposure")
        self.assertIn("(20-30)% maximum Player Resistances", exp["text"])       # a reversed range is printed low-high
        self.assertFalse(any("[]" in r["text"] or "[" in r["text"] for r in tc))   # no markup left
        self.assertTrue(any("12 wagers left out" in n for n in b.notes))

    def test_trial_row_not_in_the_export_fails(self):
        root = copy_root()
        edit_json(root, "trialdata.json", lambda d: d["items"][1].update(directions="Invented text"))
        b = BG.Build(root=root).run()
        self.assertTrue(any("differs from searchdata.json" in f for f in b.fail), b.fail)
        root = copy_root()
        edit_json(root, "trialdata.json", lambda d: d["modifiers"][0].update(stats=[]))
        self.assertTrue(BG.Build(root=root).run().fail)

    def test_blacklisted_source_fails_the_build(self):
        for bad in ("game8.co runeshapes", "Fextralife wiki", "poe2.game8.co"):
            b = BG.Build()
            b.run()
            b.fail = []
            b.rows[0]["source"] = bad
            b.finish()
            self.assertTrue(any("blacklist" in f for f in b.fail), (bad, b.fail))
        for f in ("soe2/remnant.py", "stashofexile2.py", "tools/README.txt"):    # and no credit to them in the code
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                t = fh.read().lower()
            self.assertEqual([w for w in ("game8", "fextralife") if w in t and f != "tools/README.txt"], [], f)

    def test_bad_mod_fails_the_build_and_writes_nothing(self):
        root = copy_root()
        edit_json(root, "modlists.json", lambda d: d["tablets"]["Abyss Tablet"]["Prefix"].append(
            "Map contains (1—2) additional Invented Things"))
        b = BG.Build(root=root).run()
        self.assertTrue(any("Invented Things" in f and "not in regexdata.json" in f for f in b.fail), b.fail)
        self.assertTrue(any("Invented Things" in f and "no stat in gamedata.json" in f for f in b.fail), b.fail)
        out = os.path.join(root, "gamedb.json")
        self.assertEqual(BG.main(["--root", root]), 1)
        self.assertFalse(os.path.exists(out))

    def test_sources_that_disagree_fail(self):
        root = copy_root()

        def widen(d):
            for m in d["types"]["tablet"]["mods"]:
                if m["lines"][0].startswith("#% increased gold found"):
                    m["max"] += 5
        edit_json(root, "regexdata.json", widen)
        b = BG.Build(root=root).run()
        self.assertTrue(any("Gold found" in f and "regexdata.json" in f and "range" in f for f in b.fail), b.fail)

        root = copy_root()

        def retag(d):
            for m in d["types"]["tablet"]["mods"]:
                if "Breach" in m["tags"]:
                    m["tags"] = ["Delirium"]
                    break
        edit_json(root, "regexdata.json", retag)
        b = BG.Build(root=root).run()
        self.assertTrue(any("modlists.json says" in f and "regexdata.json says" in f for f in b.fail), b.fail)

    def test_reversed_range_is_not_a_difference(self):
        self.assertEqual(BG.pairs("Delirium Fog dissipates (30—20)% slower"), [(20.0, 30.0)])
        b = BG.Build().run()
        row = next(r for r in b.rows if "dissipates" in r["name"])
        self.assertIn("Range: 20–30", row["text"])
        self.assertIn(["Range", "20–30"], row["props"])

    def test_unknown_names_fail(self):
        root = copy_root()
        edit_json(root, "gamedata.json", lambda d: d["bases"].pop("Abyss Tablet"))
        b = BG.Build(root=root).run()
        self.assertTrue(any("Abyss Tablet" in f for f in b.fail), b.fail)

    def test_real_copies_are_checked(self):
        root = copy_root()
        samples = os.path.join(root, "tests", "fixtures", "gamedb_samples.txt")
        with open(samples, encoding="utf-8") as f:
            text = f.read()
        bad = text.replace("Map has 77(70-100)% increased chance to contain a Summoning Circle",
                           "Map has 77(70-100)% increased chance to contain a Dragon")
        with open(samples, "w", encoding="utf-8") as f:
            f.write(bad)
        b = BG.Build(root=root).run()
        self.assertTrue(any("sample" in f and "Dragon" in f for f in b.fail), b.fail)
        # a real mod on the wrong tablet type
        wrong = text.replace("Voidtouched Project\nTemple Tablet", "Voidtouched Project\nBreach Tablet")
        with open(samples, "w", encoding="utf-8") as f:
            f.write(wrong)
        b = BG.Build(root=root).run()
        self.assertTrue(any("rolls on" in f and "Breach" in f for f in b.fail), b.fail)
        # a roll outside the row's range
        far = text.replace("17(15-19)% increased Monster Damage", "99(90-99)% increased Monster Damage")
        with open(samples, "w", encoding="utf-8") as f:
            f.write(far)
        b = BG.Build(root=root).run()
        self.assertTrue(any("outside the row's" in f for f in b.fail), b.fail)

    def test_samples_hold_only_item_text(self):
        with open(os.path.join(ROOT, BG.SAMPLES), encoding="utf-8") as f:
            text = f.read()
        for bad in ("tiwomm", "@", "Account", "Character", "Price", "price", "div"):
            self.assertNotIn(bad, text, bad)
        for chunk in re.split(r"\n={5,}\n", text):
            self.assertRegex(chunk.strip(), r"^Item Class: (Tablets?|Waystones?)\b")

    def test_refresh_samples_keeps_only_tablet_and_waystone_text(self):
        d = tempfile.mkdtemp()
        raw = "Item Class: Tablet\nRarity: Normal\nAbyss Tablet\n--------\nItem Level: 79"
        with open(os.path.join(d, "session.json"), "w", encoding="utf-8") as f:
            json.dump({"records": [{"raw": raw, "total": 5, "label": "someone"}, {"raw": "Item Class: Rings\nx"},
                                   {"raw": raw}]}, f)
        with open(os.path.join(d, "unpriced_items.txt"), "w", encoding="utf-8") as f:
            f.write("===== 2026-11-17 v3.0.5\nItem Class: Waystones\nRarity: Rare\nX\nWaystone (Tier 1)\n")
        out = os.path.join(d, "s.txt")
        self.assertEqual(BG.refresh_samples(d, out), 2)
        with open(out, encoding="utf-8") as f:
            got = f.read()
        self.assertNotIn("someone", got)
        self.assertNotIn("Rings", got)


class HideList(unittest.TestCase):
    def test_build_skips_hidden_ids(self):
        full = BG.Build().run()
        rid = "tablet/any/mod/increased-rarity-of-items-found-in-map"
        self.assertIn(rid, {r["id"] for r in full.rows})
        b = BG.Build(hide={rid: "test", "no/such/row": "x"}).run()
        self.assertNotIn(rid, {r["id"] for r in b.rows})
        self.assertEqual(len(b.rows), len(full.rows) - 1)
        self.assertTrue(any("no/such/row" in w for w in b.warn))

    def test_game_search_leaves_a_hidden_row_out(self):
        rid = "waystone/mod/increased-monster-damage"
        hide = config.P("gamedb_hide.json")

        def ids():
            gamesearch._DATA["rows"] = None
            return {r.get("id") for r in gamesearch.load()["rows"]}
        try:
            if os.path.exists(hide):
                os.remove(hide)
            self.assertIn(rid, ids())
            with open(hide, "w", encoding="utf-8") as f:
                json.dump([{"id": rid, "reason": "test: wrong in this patch"}], f)
            self.assertNotIn(rid, ids())
        finally:
            if os.path.exists(hide):
                os.remove(hide)
            gamesearch._DATA["rows"] = None

    def test_shipped_hide_list_is_a_list_of_id_or_name_and_reason(self):
        with open(os.path.join(ROOT, "gamedb_hide.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.assertIsInstance(d, list)
        for e in d:
            self.assertTrue((e.get("id") or e.get("name")) and e.get("reason"), e)


class GameSearchGroups(unittest.TestCase):
    def setUp(self):
        gamesearch._DATA["rows"] = None

    def test_new_groups_follow_endgame_items(self):
        d = gamesearch.load()
        o = d["order"]
        i = o.index("Endgame Items")
        self.assertEqual(o[i + 1:i + 1 + len(names.GAME_SEARCH_GROUPS)], list(names.GAME_SEARCH_GROUPS))
        self.assertLess(o.index("Tablets"), o.index("Modifiers"))
        got = {r["g"] for r in d["rows"]}
        for g in names.GAME_SEARCH_GROUPS:
            self.assertIn(g, got)

    def test_search_finds_them(self):
        hit = gamesearch.search("hiveblood")
        db = [r for r in hit if r.get("db")]
        self.assertEqual([r["g"] for r in db], ["Tablets"])
        self.assertIn("Breach Tablet", db[0]["t"])
        self.assertTrue(any(r["n"] == "Garrison" for r in gamesearch.search("warrior assembly")))
        self.assertTrue(any(r["n"] == "Juatalotli's Medallion" for r in gamesearch.search("destabilisation medallion")))
        self.assertTrue(any(r["g"] == "Leagues" for r in gamesearch.search("forbidden rites")))

    def test_rows_carry_source_and_version(self):
        for r in gamesearch.load()["rows"]:
            if r.get("db"):
                self.assertTrue(r["src"] and r["v"] and r["id"], r["n"])


class GameSearchPage(unittest.TestCase):
    """The page itself (own process: it starts the whole app): the new categories are in its list, a row is one line,
    opened it shows its source and game."""

    def test_page(self):
        import subprocess
        try:
            tk.Tk().destroy()
        except tk.TclError:
            self.skipTest("no display")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "gamedb_page_check.py")], capture_output=True,
                           text=True, timeout=240)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PoE1Filter(unittest.TestCase):
    def test_drops_only_unknown_names_in_poe1_classes(self):
        gd = {"bases": {"Abyss Tablet": {}}, "currency": {"Divine Orb": {}}, "uniques": {}}
        rows = [["Rusted Abyss Scarab", "Endgame Items", "MapFragment", "", "x"],
                ["Ivory Watchstone", "Endgame Items", "AtlasUpgradeItem", "", ""],
                ["Divine Orb", "Currency & Omens", "StackableCurrency", "", ""],
                ["Raven's Reflection", "Endgame Items", "MapFragment", "", "Mirror in the Withered Willow."],
                ["Omen of Recombination", "Currency & Omens", "Omen", "", ""],          # (an Omen is PoE2: kept)
                ["Ancient Reliquary Key", "Endgame Items", "VaultKey", "", ""],
                ["Phalanx Tower Shield", "Off-hand", "Shield", "", ""],                 # (gear is never dropped)
                ["Whispering Incubator", "Currency & Omens", "Incubator", "", ""]]
        kept, dropped = BS.drop_poe1(rows, gd)
        self.assertEqual({r[0] for r in dropped}, {"Rusted Abyss Scarab", "Ivory Watchstone", "Whispering Incubator"})
        self.assertEqual(len(kept), 5)
        kept, dropped = BS.drop_poe1(rows, gd, extra={"Ivory Watchstone"})                # (a trade list names it)
        self.assertNotIn("Ivory Watchstone", {r[0] for r in dropped})

    def test_shipped_searchdata_has_none(self):
        with open(os.path.join(ROOT, "searchdata.json"), encoding="utf-8") as f:
            sd = json.load(f)
        with open(os.path.join(ROOT, "gamedata.json"), encoding="utf-8") as f:
            gd = json.load(f)
        kept, dropped = BS.drop_poe1(sd["rows"], gd)
        self.assertEqual(dropped, [])
        names_ = {r[0] for r in sd["rows"]}
        for gone in ("Rusted Abyss Scarab", "Ivory Watchstone", "Ceremonial Voidstone", "Maven's Invitation: The Atlas",
                     "Xoph's Breachstone", "Timeless Karui Emblem", "Whispering Incubator", "Orb of Fusing"):
            self.assertNotIn(gone, names_)
        for stay in ("Breach Tablet", "Waystone (Tier 15)", "Kulemak's Invitation", "Raven's Reflection",
                     "The Triskelion Reforged", "Timeless Jewel", "Omen of Recombination"):
            self.assertIn(stay, names_ | set(gd["bases"]))


class Shipped(unittest.TestCase):
    def test_bundled_and_built_everywhere(self):
        self.assertGreaterEqual(config.BUNDLED_DATA["gamedb.json"], 6)       # raised by tools/update_game_data.py
        self.assertEqual(config.BUNDLED_DATA["atlasmasters.json"], 2)
        self.assertEqual(config.BUNDLED_DATA["gamedb_hide.json"], 2)
        self.assertGreaterEqual(config.BUNDLED_DATA["searchdata.json"], 2)         # (the PoE1 rows left it)
        for f in ("build_exe.bat", "build_linux.sh", os.path.join(".github", "workflows", "release.yml")):
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                s = fh.read()
            self.assertIn("gamedb.json", s, f)
            self.assertIn("gamedb_hide.json", s, f)
            self.assertIn("atlasmasters.json", s, f)
        for f in ("gamedb.json", "gamedb_hide.json", "atlasmasters.json"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, f)), f)


if __name__ == "__main__":
    unittest.main()
