"""Build trialdata.json - the Trial of Chaos facts that tools/build_gamedb.py turns into Game Search rows - from the
RePoE export of Path of Exile 2's game files (the data folder: mods.json, base_items.json, keywords.json,
world_areas.json; version.txt beside or above it).

    py tools/build_trialdata.py path\\to\\repoe2\\data [trialdata.json]

Only what the export holds: the trial modifiers (mods of the "ultimatum_key" domain: suffixes are the trial's
modifiers, prefixes the wagers), the Inscribed Ultimatum, the three Fates, the Trialmaster's Reliquary Key, the Ruin
keyword and the two areas. A wager whose item name the export prints as "[]" has no readable text and is left out (its
count is kept in "left_out"). Nothing comes from a website. This file is a build input only; it is not shipped."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), "repoe2", "data")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "trialdata.json")
NUM = r"-?\d+(?:\.\d+)?"
ITEM_IDS = ("Metadata/Items/Ultimatum/UltimatumKeyNew", "Metadata/Items/Ultimatum/TrialmasterKey1",
            "Metadata/Items/Ultimatum/TrialmasterKey2", "Metadata/Items/Ultimatum/TrialmasterKey3",
            "Metadata/Items/MapFragments/VaultKeyUltimatum")
AREAS = ("G3_10", "G3_10_Airlock")


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return json.load(f)


def clean(s):
    """Game markup -> plain text; a printed range is always low-high ((30-20) -> (20-30))."""
    s = re.sub(r"\[([^\]|]*)\|([^\]]*)\]", r"\2", s or "")
    s = re.sub(r"\[([^\]]*)\]", r"\1", s)
    s = re.sub(r"<[^>]*>|[{}]", "", s).replace("\r", "")
    def order(m):
        a, b = float(m.group(1)), float(m.group(2))
        lo, hi = (m.group(1), m.group(2)) if a <= b else (m.group(2), m.group(1))
        return f"({lo}-{hi})"
    return re.sub(rf"\(({NUM})-({NUM})\)", order, s).strip()


def main():
    mods, items, kws, areas = load("mods.json"), load("base_items.json"), load("keywords.json"), load("world_areas.json")
    vp = next(p for p in (os.path.join(SRC, "version.txt"), os.path.join(SRC, "..", "version.txt")) if os.path.isfile(p))
    with open(vp, encoding="utf-8") as f:
        version = f.read().strip()
    out = {"version": 1, "game_version": version, "source": "RePoE poe2 export (mods, base_items, keywords, world_areas)",
           "modifiers": [], "wagers": [], "items": [], "keywords": [], "areas": [], "left_out": {}}
    skipped = []
    for mid, m in mods.items():
        if m.get("domain") != "ultimatum_key":
            continue
        text = clean(m.get("text"))
        if "[]" in (m.get("text") or "") or not text:
            skipped.append(mid)
            continue
        rec = {"id": mid, "name": m["name"], "level": m["required_level"], "text": text,
               "stats": [s["id"] for s in m["stats"]]}
        out["modifiers" if m["generation_type"] == "suffix" else "wagers"].append(rec)
    out["left_out"]["wagers_without_item_name"] = len(skipped)
    for iid in ITEM_IDS:
        it = items[iid]
        p = {k: v for k, v in it["properties"].items() if v}
        out["items"].append({"id": iid, "name": it["name"], "class": it["item_class"], "drop_level": it["drop_level"],
                             "tags": [t for t in it["tags"] if t != "default"], "directions": clean(p.get("directions")),
                             "stack_size": p.get("stack_size")})
    kw = kws["UltimatumRuin"]
    out["keywords"].append({"id": "UltimatumRuin", "term": kw["term"], "text": clean(kw["definition"])})
    for aid in AREAS:
        a = areas[aid]
        out["areas"].append({"id": aid, "name": a["name"], "level": a["area_level"], "act": a["act"],
                             "waypoint": bool(a["has_waypoint"]), "bosses": len(a.get("bosses") or [])})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{OUT}: {len(out['modifiers'])} modifiers, {len(out['wagers'])} wagers (+{len(skipped)} left out), "
          f"{len(out['items'])} items, {len(out['areas'])} areas, version {version}")


if __name__ == "__main__":
    main()
