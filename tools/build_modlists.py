"""Builds modlists.json (every tablet / jewel mod, for the Mod rules pages) from RePoE's Path of Exile 2 export
(2.0 beta 12; before that tabs.txt / jewels.txt were pasted from a website; merged into one JSON in 3.0.x).
  git clone --depth 1 https://github.com/repoe-fork/poe2 repoe2
  python tools/build_modlists.py repoe2/data
Writes modlists.json (soe2/mods.py load_modlists reads it):
  {"version": 3, "source": "<header>", "game_version": "...",
   "tablets": {"Abyss Tablet": {"Prefix": [...], "Suffix": [...], "Corrupted": [...]}, ...},
   "jewels": {"Ruby": {"Prefix": [...], "Suffix": [...], "Corrupted": [...]}, ...}}
  one mod per entry, with (min—max) ranges.
RePoE is MIT licensed (code); the data itself is Grinding Gear Games' (see THIRD_PARTY_NOTICES.txt)."""
import json
import os
import re
import sys

MARKUP = re.compile(r"\[([^\]|]*\|)?([^\]]*)\]")


def clean(text):
    t = MARKUP.sub(r"\2", text or "")
    t = re.sub(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)", lambda m: f"({m.group(1)}—{m.group(2)})", t)
    return [l.strip() for l in t.split("\n") if l.strip()]


def _key(text):
    t = re.sub(r"\(-?\d+(?:\.\d+)?\s*[-—–]\s*-?\d+(?:\.\d+)?\)", "#", text)
    t = re.sub(r"-?\d+(?:\.\d+)?", "#", t).replace("+#", "#")
    return re.sub(r"\s+", " ", t).strip().lower()


def main(folder, out_dir="."):
    mods = json.load(open(os.path.join(folder, "mods.json"), encoding="utf-8"))
    bases = json.load(open(os.path.join(folder, "base_items.json"), encoding="utf-8"))
    by_base = json.load(open(os.path.join(folder, "mods_by_base.json"), encoding="utf-8"))
    name_of = {k: v.get("name") for k, v in bases.items()}
    try:
        version = open(os.path.join(folder, "..", "version.txt"), encoding="utf-8").read().strip()
    except OSError:
        version = "?"

    def pools(item_class):
        """-> {base name: {"prefix": [mod ids], "suffix": [...], "corrupted": [...]}}"""
        out = {}
        for _tags, entry in (by_base.get(item_class) or {}).items():
            for b in entry.get("bases", []):
                n = name_of.get(b)
                if not n:
                    continue
                d = out.setdefault(n, {})
                for gen, groups in (entry.get("mods") or {}).items():
                    for _g, ids in groups.items():
                        for mid in ids:
                            d.setdefault(gen, [])
                            if mid not in d[gen]:
                                d[gen].append(mid)
        return out

    # Time-Lost (radius) jewels: the export gives the bare stat ("(2-3)% increased Area of Effect"); the game shows it as
    # "Notable / Small Passive Skills in Radius also grant ...". Which one is taken from gamedata.json (Exiled Exchange 2's
    # stat wordings, MIT), so the list matches what a copied jewel says.
    radius = {}
    gd_path = os.path.join(out_dir, "gamedata.json")
    if os.path.isfile(gd_path):
        txt = open(gd_path, encoding="utf-8").read()
        for who, rest in re.findall(r"(Notable|Small) Passive Skills in Radius also grant ([^\"\\]+)", txt):
            radius.setdefault(_key(rest), set()).add(who)

    def build(order, pool):
        res = {}
        for name in order:
            p = pool.get(name)
            if not p:
                continue
            secs = {}
            for gen, title in (("prefix", "Prefix"), ("suffix", "Suffix"), ("corrupted", "Corrupted")):
                lines, seen = [], set()
                for mid in p.get(gen) or []:
                    m = mods.get(mid) or {}
                    if not m.get("text"):
                        continue
                    for l in clean(m["text"]):
                        outs = [l]
                        if name.startswith("Time-Lost") and gen in ("prefix", "suffix") and not l.startswith("Upgrades"):
                            who = sorted(radius.get(_key(l)) or [])
                            outs = [f"{w} Passive Skills in Radius also grant {l}" for w in who] or [l]
                        for o in outs:
                            if o not in seen and "uses remaining" not in o:
                                seen.add(o)
                                lines.append(o)
                if lines:
                    secs[title] = lines
            res[name] = secs
        return res

    tab_pool = pools("Tablet")
    tablets = build(sorted(n for n in tab_pool if n.endswith(" Tablet")), tab_pool)
    jew_pool = pools("Jewels")
    jew_order = [n for n in ("Ruby", "Emerald", "Sapphire", "Diamond", "Time-Lost Ruby", "Time-Lost Emerald",
                             "Time-Lost Sapphire", "Time-Lost Diamond") if n in jew_pool or n + " Jewel" in jew_pool]
    jew_pool = {k.replace(" Jewel", ""): v for k, v in jew_pool.items()}
    jewels = build(jew_order, jew_pool)
    data = {"version": 3, "source": "RePoE export of Path of Exile 2's game files, game version %s (tools/build_modlists.py)" % version,
            "game_version": version, "tablets": tablets, "jewels": jewels}
    with open(os.path.join(out_dir, "modlists.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    n = lambda d: sum(len(v) for s in d.values() for v in s.values())
    print(f"modlists.json: {len(tablets)} tablet types, {n(tablets)} mods;  {len(jewels)} jewels, {n(jewels)} mods")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "repoe2/data", sys.argv[2] if len(sys.argv) > 2 else ".")
