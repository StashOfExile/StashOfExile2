"""3.3.0 owner: uniquedata.json - every unique in Path of Exile 2 with its mods, for Mod Lab.

    git clone --depth 1 --filter=blob:none --sparse https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2 pob2
    cd pob2 && git sparse-checkout set src/Data/Uniques && cd ..
    py tools/build_uniquedata.py pob2 [uniquedata.json] [--repoe repoe2/data]

With --repoe (RePoE's PoE2 export, as tools/build_tierdata.py uses): each unique also gets the corruption
enchantments its base can roll (mods.json, generation type "corrupted"), matched by the base's tags (base_items.json).

Source: Path of Building Community for PoE2 (https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2, MIT
license, see THIRD_PARTY_NOTICES.txt), its src/Data/Uniques/*.lua files. The item data in them belongs to Grinding Gear
Games, as with RePoE's export. Only the current version of each unique is kept: a line marked for an older variant
is left out. Uniques the game data does not know, from gamedata.json, are left out too, and listed when it runs.

Run it again after each patch with an updated checkout and bump "uniquedata.json" in BUNDLED_DATA (soe2/config.py)."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VERSION = 2                     # 2: "corruption", the enchantments a Vaal Orb can give its base
MARKUP = re.compile(r"\[([^\]|]+)\|([^\]]+)\]|\[([^\]]+)\]")


RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")


def plain(text):
    """RePoE's wording markup: "[Armour|Armour]" -> "Armour", "[Physical]" -> "Physical". A range RePoE prints
    backwards, "(20-10)%", is put the right way round."""
    text = MARKUP.sub(lambda m: m.group(2) or m.group(3), str(text))
    return RANGE.sub(lambda m: f"({m.group(1)}-{m.group(2)})" if float(m.group(1)) <= float(m.group(2))
                     else f"({m.group(2)}-{m.group(1)})", text)


def corruption_pool(repoe):
    """(base name -> tags, [(spawn weights, lines)]) from RePoE's export."""
    with open(os.path.join(repoe, "base_items.json"), encoding="utf-8") as f:
        bases = {v["name"]: set(v.get("tags") or []) for v in json.load(f).values()
                 if v.get("domain") == "item" and v.get("release_state") != "unreleased" and v.get("name")}
    with open(os.path.join(repoe, "mods.json"), encoding="utf-8") as f:
        mods = [v for v in json.load(f).values() if v.get("generation_type") == "corrupted" and v.get("domain") == "item"]
    pool = []
    for v in mods:
        lines = [ln.strip() for ln in plain(v.get("text") or "").split("\n") if ln.strip()]
        if lines:
            pool.append((v.get("spawn_weights") or [], lines))
    return bases, pool


def rolls_on(weights, tags):
    """RePoE spawn weights: the first tag the base has decides."""
    for w in weights:
        if w.get("tag") in tags:
            return (w.get("weight") or 0) > 0
    return False
# a PoB file -> the group Mod Lab folds it under, and the group's name for one item
FILES = {
    "amulet": ("jewelry", "Amulets"), "ring": ("jewelry", "Rings"), "belt": ("jewelry", "Belts"),
    "body": ("armour", "Body Armours"), "helmet": ("armour", "Helmets"), "gloves": ("armour", "Gloves"),
    "boots": ("armour", "Boots"), "shield": ("armour", "Shields"), "focus": ("armour", "Foci"),
    "quiver": ("armour", "Quivers"),
    "axe": ("weapon", "Axes"), "bow": ("weapon", "Bows"), "claw": ("weapon", "Claws"), "crossbow": ("weapon", "Crossbows"),
    "dagger": ("weapon", "Daggers"), "flail": ("weapon", "Flails"), "mace": ("weapon", "Maces"),
    "sceptre": ("weapon", "Sceptres"), "spear": ("weapon", "Spears"), "staff": ("weapon", "Staves"),
    "sword": ("weapon", "Swords"), "talisman": ("weapon", "Talismans"), "wand": ("weapon", "Wands"),
    "jewel": ("jewel", "Jewels"), "flask": ("flask", "Flasks and Charms"), "soulcore": ("other", "Soul Cores"),
}
HEADER = re.compile(r"^(Variant|Selected Variant|Selected Alt Variant(?: \w+)?|Has Alt Variant(?: \w+)?|"
                    r"Allow Duplicate Variants|Implicits|League|Source|Requires|LevelReq|Sockets|Radius|Limited to|"
                    r"Item Level|Quality|Upgrade|Unreleased|Catalyst|Talisman Tier|Charm Slots?|Version|Crafted):\s*\S", re.I)
TAG = re.compile(r"\{[^}]*\}")
BLOCK = re.compile(r"\[\[(.*?)\]\]", re.S)


def parse_block(text):
    """One unique's text -> {"name", "base", "implicit": [...], "explicit": [...]} with only its current lines."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    name, base = lines[0], lines[1]
    variants, implicits, mods = [], 0, []
    for ln in lines[2:]:
        bare = TAG.sub("", ln).strip()
        if ln.startswith("Variant:"):
            variants.append(ln.split(":", 1)[1].strip())
            continue
        if ln.startswith("Implicits:"):
            try:
                implicits = int(ln.split(":", 1)[1])
            except ValueError:
                implicits = 0
            continue
        if HEADER.match(bare):
            continue
        if bare in ("Corrupted", "Mirrored", "Unidentified"):
            continue
        mods.append(ln)
    current = next((i + 1 for i, v in reversed(list(enumerate(variants))) if v.lower().startswith("current")),
                   len(variants))
    # variants that are game versions ("Pre 0.2.0", "Current"): only the current one. Variants that are a choice the
    # item rolls, like Mageblood's Legacies: every one, since each is a line that can be on the item
    versions = any(v.lower().startswith(("pre ", "current")) for v in variants)
    imp, exp = [], []
    for i, ln in enumerate(mods):
        m = re.search(r"\{variant:([\d,]+)\}", ln)
        if m and variants and versions and current not in [int(x) for x in m.group(1).split(",") if x]:
            continue
        bare = " ".join(TAG.sub("", ln).split())
        if not bare:
            continue
        into = imp if i < implicits else exp
        if bare not in into:
            into.append(bare)
    return {"name": name, "base": base, "implicit": imp, "explicit": exp}


def read(pob):
    folder = os.path.join(pob, "src", "Data", "Uniques")
    out = {}
    for fname in sorted(os.listdir(folder)):
        key = fname[:-4] if fname.endswith(".lua") else None
        if key not in FILES:
            continue
        kind, group = FILES[key]
        with open(os.path.join(folder, fname), encoding="utf-8") as f:
            text = f.read()
        for block in BLOCK.findall(text):
            u = parse_block(block)
            if u and (u["implicit"] or u["explicit"]):
                out[u["name"]] = dict(u, kind=kind, group=group)
    return out


def known_names():
    path = os.path.join(ROOT, "gamedata.json")
    try:
        with open(path, encoding="utf-8") as f:
            return set((json.load(f).get("uniques") or {}).keys())
    except (OSError, ValueError):
        return set()


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    args = list(argv[1:])
    repoe = None
    if "--repoe" in args:
        i = args.index("--repoe")
        repoe = args[i + 1]
        del args[i:i + 2]
    out_path = args[1] if len(args) > 1 else os.path.join(ROOT, "uniquedata.json")
    got = read(args[0])
    if repoe:
        bases, pool = corruption_pool(repoe)
        no_base = []
        for n, u in got.items():
            tags = bases.get(u["base"])
            if tags is None:
                no_base.append(n)
                continue
            lines = []
            for weights, ls in pool:
                if rolls_on(weights, tags):
                    lines += [ln for ln in ls if ln not in lines]
            u["corruption"] = lines
        if no_base:
            print(f"No base in RePoE, so no corruption lines: {len(no_base)}: " + ", ".join(sorted(no_base)[:30]))
    known = known_names()
    if known:
        left = sorted(n for n in got if n not in known)
        got = {n: u for n, u in got.items() if n in known}
        if left:
            print(f"Left out, not in gamedata.json: {len(left)}: " + ", ".join(left[:40]) + (" ..." if len(left) > 40 else ""))
        missing = sorted(n for n in known if n not in got)
        if missing:
            print(f"In gamedata.json with no mods here: {len(missing)}: " + ", ".join(missing[:40]))
    data = {"version": VERSION, "source": "Path of Building Community PoE2, MIT license",
            "uniques": {n: {k: got[n].get(k) or [] if k == "corruption" else got[n][k]
                            for k in ("base", "kind", "group", "implicit", "explicit", "corruption")}
                        for n in sorted(got, key=str.lower)}}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    lines = sum(len(u["explicit"]) + len(u["implicit"]) for u in data["uniques"].values())
    cor = sum(1 for u in data["uniques"].values() if u["corruption"])
    print(f"Corruption lines on {cor} uniques.")
    print(f"Wrote {out_path}: {len(data['uniques'])} uniques, {lines} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
