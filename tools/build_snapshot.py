"""3.3.0 owner: freeze the game's data as it is today, so the next patch (PoE2 1.0) can be shown before and after.

    py tools/build_snapshot.py <RePoE poe2 data folder> <Path of Building PoE2 checkout> [snapshots folder]

Writes snapshots/poe2-<game version>.json.gz: every unique with its current lines and every older version Path of Building
keeps ("Pre 0.4.0" and the like), every skill, spirit and support gem with its text and its stats at its first and last
level, and every item modifier with its kind (prefix, suffix, corrupted, desecrated, essence, unique ...). Sources: RePoE's
PoE2 export and Path of Building Community PoE2, both MIT, see THIRD_PARTY_NOTICES.txt; the game data belongs to
Grinding Gear Games. A snapshot is never changed once made: a new game version gets a new file.

soe2/gamesnap.py reads them and compares two of them."""
import datetime
import gzip
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_uniquedata as BU  # noqa: E402

SNAP_VERSION = 1
ITEM_KINDS = ("prefix", "suffix", "corrupted", "desecrated", "essence", "unique")
TAG = re.compile(r"\{[^}]*\}")


def git_head(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def game_version(repoe_data):
    for name in ("version.txt", "exported-version.txt"):
        p = os.path.join(os.path.dirname(os.path.abspath(repoe_data)), name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                v = f.read().split()
            if v:
                return v[0]
    return "unknown"


def unique_versions(block):
    """Every version Path of Building keeps of one unique: {"Pre 0.4.0": [lines], "Current": [lines]}."""
    lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
    variants, mods = [], []
    for ln in lines[2:]:
        bare = TAG.sub("", ln).strip()
        if ln.startswith("Variant:"):
            variants.append(ln.split(":", 1)[1].strip())
        elif ln.startswith("Implicits:") or BU.HEADER.match(bare) or bare in ("Corrupted", "Mirrored", "Unidentified"):
            continue
        else:
            mods.append(ln)
    if not any(v.lower().startswith(("pre ", "current")) for v in variants):
        return {}
    out = {}
    for i, v in enumerate(variants, 1):
        keep = []
        for ln in mods:
            m = re.search(r"\{variant:([\d,]+)\}", ln)
            if m and i not in [int(x) for x in m.group(1).split(",") if x]:
                continue
            bare = " ".join(TAG.sub("", ln).split())
            if bare and bare not in keep:
                keep.append(bare)
        out[v] = keep
    return out


def uniques(pob, repoe):
    current = BU.read(pob)
    bases, pool = BU.corruption_pool(repoe)
    folder = os.path.join(pob, "src", "Data", "Uniques")
    history = {}
    for fname in os.listdir(folder):
        if not fname.endswith(".lua"):
            continue
        with open(os.path.join(folder, fname), encoding="utf-8") as f:
            for block in BU.BLOCK.findall(f.read()):
                name = block.strip().splitlines()[0].strip() if block.strip() else ""
                v = unique_versions(block)
                if name and v:
                    history[name] = v
    out = {}
    for n, u in current.items():
        tags = bases.get(u["base"]) or set()
        cor = []
        for weights, ls in pool:
            if tags and BU.rolls_on(weights, tags):
                cor += [ln for ln in ls if ln not in cor]
        out[n] = {"base": u["base"], "group": u["group"], "implicit": u["implicit"], "explicit": u["explicit"],
                  "corruption": cor, "versions": history.get(n, {})}
    return out


def gems(repoe):
    with open(os.path.join(repoe, "skill_gems.json"), encoding="utf-8") as f:
        g = json.load(f)
    with open(os.path.join(repoe, "skills.json"), encoding="utf-8") as f:
        sk = json.load(f)
    out = {}
    for v in g.values():
        name = ((v.get("base_item") or {}).get("display_name") or "").strip()
        if not name or (v.get("base_item") or {}).get("release_state") == "unreleased":
            continue
        desc, first, last = "", [], []
        for sid in v.get("grants_skills") or []:
            s = sk.get(sid) or {}
            desc = desc or BU.plain((s.get("active_skill") or {}).get("description") or "")
            for st in s.get("stat_sets") or []:
                static = list(((st.get("static") or {}).get("stat_text") or {}).values())
                levels = st.get("per_level") or {}
                keys = sorted(levels, key=lambda x: int(x)) if levels else []
                lo = list(((levels.get(keys[0]) or {}).get("stat_text") or {}).values()) if keys else []
                hi = list(((levels.get(keys[-1]) or {}).get("stat_text") or {}).values()) if keys else []
                first += [BU.plain(t) for t in static + lo if t]
                last += [BU.plain(t) for t in static + hi if t]
        out[name] = {"type": v.get("gem_type") or "", "lineage": bool(v.get("is_lineage")),
                     "tags": [t for t in v.get("tags") or [] if t != "grants_active_skill"],
                     "text": BU.plain(v.get("support_text") or desc or ""),
                     "first_level": list(dict.fromkeys(first)), "last_level": list(dict.fromkeys(last))}
    return out


def mods(repoe):
    with open(os.path.join(repoe, "mods.json"), encoding="utf-8") as f:
        m = json.load(f)
    out = {}
    for mid, v in m.items():
        kind = v.get("generation_type")
        if v.get("domain") not in ("item", "desecrated", "flask") or kind not in ITEM_KINDS or not v.get("text"):
            continue
        out[mid] = {"kind": kind, "text": BU.plain(v["text"]), "level": v.get("required_level") or 0,
                    "groups": v.get("groups") or [],
                    "tags": sorted({w["tag"] for w in v.get("spawn_weights") or [] if w.get("weight")})}
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    repoe, pob = argv[1], argv[2]
    folder = argv[3] if len(argv) > 3 else os.path.join(ROOT, "snapshots")
    ver = game_version(repoe)
    snap = {"snapshot": SNAP_VERSION, "game_version": ver, "made": datetime.date.today().isoformat(),
            "sources": {"repoe": git_head(os.path.dirname(os.path.abspath(repoe))), "pob": git_head(pob)},
            "uniques": uniques(pob, repoe), "gems": gems(repoe), "mods": mods(repoe)}
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"poe2-{ver}.json.gz")
    if os.path.exists(path):
        print(f"{path} exists already. A snapshot is never changed: delete it by hand to make it again.")
        return 1
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"Wrote {path}: {len(snap['uniques'])} uniques, {len(snap['gems'])} gems, {len(snap['mods'])} mods, "
          f"{os.path.getsize(path) // 1024} KB.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
