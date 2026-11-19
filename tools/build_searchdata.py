"""Turn the PoE2 Keyword Search page (PoE2-Search.html, built from the RePoE export of Path of Exile 2's game files)
into searchdata.json for the app's Game search window.

    py tools/build_searchdata.py path\\to\\PoE2-Search.html [--trade-dir DIR]
    py tools/build_searchdata.py --refilter [--trade-dir DIR]     (no page: filter the searchdata.json that is already here)

Writes searchdata.json next to the app; bump "searchdata.json" in BUNDLED_DATA (soe2/config.py) so existing data
folders take the new copy.

3.0.6: the export carries Path of Exile 1 leftovers (scarabs, Maven's Invitations, watchstones and voidstones, Breach-
stones, Metamorph / Legion / Harbinger / Blight items, emblems, fossils, sextants, nets, incubators ...). They are dropped
here, by one rule: in the item groups where those live, a row whose name is in none of gamedata.json (bases, currency,
uniques) nor the trade site's own item and currency lists (--trade-dir DIR: the data folder's trade_items.json and
trade_static.json, when given) is not in the game. Rows of a class that is also in Path of Exile 2 (Omens, Reliquary keys,
Verisium Sentry, weapons and armour newer than gamedata.json ...) are never dropped. KEEP_POE2 lists the few Path of Exile 2
items that no list names yet, each with its evidence. What was dropped is printed, by class."""
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEM_GROUPS = ("Endgame Items", "Currency & Omens", "Other Items")
# RePoE classes that only exist for Path of Exile 1 leftovers here. (Omen, VaultKey, FishingRod, SentinelDrone, Incubator
# kinds that gamedata.json names ... are real or unsure: never dropped on a name alone.)
POE1_CLASSES = {"AtlasUpgradeItem", "Breachstone", "MiscMapItem", "UltimatumKey", "MapFragment", "StackableCurrency",
                "Incubator", "IncubatorStackable", "UniqueFragment", "ArchnemesisMod", "DivinationCard",
                "UncutSkillGem_OLD", "UncutSupportGem_OLD", "UncutReservationGem_OLD", "SkillGemToken"}
# Path of Exile 2 items that gamedata.json and the trade lists don't name (yet). Evidence for each:
KEEP_POE2 = {
    # Ritual / Expedition / Delirium pinnacle access items, named by the game's own item text (Withered Willow,
    # Ruins of Kingsmarch, Verisium Anvil are Path of Exile 2 areas and objects)
    "Raven's Reflection", "The Triskelion Reforged", "Shattered Triskelion",
    # on the PoE2 trade site's static list (trade_static.json) but not in the gamedata.json snapshot
    "Zarokh's Reliquary Key: Sandstorm Visage", "Zarokh's Reliquary Key: Blessed Bonds",
    "Zarokh's Reliquary Key: Sekhema's Resolve", "Idol of Estazunti", "Thaumaturgic Flux (Level 2)",
    "Thaumaturgic Flux (Level 3)", "Thaumaturgic Flux (Level 4)", "Thaumaturgic Flux (Level 5)",
    "Thaumaturgic Flux (Level 6)", "Thaumaturgic Flux (Level 7)", "Mutated Verisium", "Corrupted Verisium",
    "Founders Verisium", "Starlit Ore",
}


def trade_names(folder):
    """Every name in the trade site's cached static list and item list (data folder), or an empty set."""
    out = set()
    if not folder:
        return out
    for f in ("trade_static.json", "trade_items.json"):
        p = os.path.join(folder, f)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8-sig") as fh:
            res = json.load(fh).get("result", [])
        for grp in res:
            for e in grp.get("entries", []):
                for k in ("text", "name", "type"):
                    if e.get(k):
                        out.add(e[k])
    return out


def drop_poe1(rows, gamedata, extra=()):
    """-> (kept rows, dropped rows). rows are [name, group, class, tags, text]."""
    known = set(gamedata["bases"]) | set(gamedata["currency"]) | set(gamedata["uniques"]) | set(extra) | KEEP_POE2
    kept, dropped = [], []
    for r in rows:
        if r[1] in ITEM_GROUPS and r[2] in POE1_CLASSES and r[0] not in known:
            dropped.append(r)
        else:
            kept.append(r)
    return kept, dropped


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    trade = argv[argv.index("--trade-dir") + 1] if "--trade-dir" in argv else None
    if trade:
        args = [a for a in args if a != trade]
    path = os.path.join(ROOT, "searchdata.json")
    if "--refilter" in argv:
        with open(path, encoding="utf-8") as f:
            out = json.load(f)
        rows = out["rows"]
    else:
        src = args[0] if args else "PoE2-Search.html"
        s = open(src, encoding="utf-8").read()
        data = json.loads(re.search(r"var DATA = (\[.*?\]);\s*\n", s, re.S).group(1))
        order = json.loads(re.search(r"var ORDER = (\[[^\]]*\])", s).group(1).replace("'", '"'))
        ver = re.search(r'var META = \{ version: "([^"]+)"', s).group(1)
        out = {"version": ver, "source": "RePoE export of Path of Exile 2's game files", "order": order,
               "nolink": ["Modifiers", "Keywords & Mechanics"]}
        rows = [[d["n"], d["g"], d["c"], d["k"], d["t"]] for d in data]
    with open(os.path.join(ROOT, "gamedata.json"), encoding="utf-8") as f:
        gd = json.load(f)
    kept, dropped = drop_poe1(rows, gd, trade_names(trade))
    sys.path.insert(0, ROOT)
    from soe2.gamesearch_clean import drop_dev_rows       # 3.0.6: no [DNT] / [DNT-UNUSED] / Playtest / unfinished gems
    kept, dev = drop_dev_rows(kept)
    print(f"{len(dev)} developer-only entries dropped (the app's loader also drops them, so an old file stays clean)")
    out["rows"] = kept
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"searchdata.json: {len(kept)} entries, game version {out['version']}; "
          f"{len(dropped)} Path of Exile 1 leftovers dropped")
    by = collections.Counter((r[1], r[2]) for r in dropped)
    for (g, c), n in sorted(by.items(), key=lambda kv: -kv[1]):
        names = sorted({r[0] for r in dropped if r[1] == g and r[2] == c})
        print(f"  {n:4} {g} / {c}: {', '.join(names[:4])}{' ...' if len(names) > 4 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
