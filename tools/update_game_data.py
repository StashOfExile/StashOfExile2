"""One command for a new patch: rebuild every game data file from the sources, keep what the new files leave out,
save the patch's snapshot, and ship the changed files.

    py tools/update_game_data.py --repoe <RePoE poe2/data> --pob <Path of Building PoE2> [--ee2 <Exiled Exchange 2>]
                                 [--dry] [--force]

Rules, decided with the owner on 25 Nov 2026:
  1. Nothing is removed. An item the new files leave out stays, marked with the version it went missing in. Game
     Search shows "Not in the <version> files".
  2. An item that turns up later is added on the next run and marked new.
  3. A patch's snapshot is never overwritten: snapshots/ keeps every patch for before and after.
  4. A run that would drop more than a tenth of a file's items stops and puts the old files back - a broken
     source, not a real change. --force runs it anyway.

Each data file that changed gets its number in BUNDLED_DATA (soe2/config.py) raised, so every PC picks it up.
A report is written to _update_report.md. Only steps whose sources were given run."""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
DROP_LIMIT = 0.10


def newest_tree(pob):
    """PoB's newest passive tree: src/TreeData/<n_n>/tree.json, the highest version."""
    trees = glob.glob(os.path.join(pob, "src", "TreeData", "*", "tree.json"))
    key = lambda p: [int(x) for x in re.findall(r"\d+", os.path.basename(os.path.dirname(p)))]   # noqa: E731
    return max(trees, key=key) if trees else None


def steps(a):
    """[(data file, command, what it needs)] in the order they must run: gamedb last, it reads the others."""
    r, p, e = a.repoe, a.pob, a.ee2
    out = []
    if r:
        out += [("modlists.json", ["tools/build_modlists.py", r, "."], "repoe"),
                ("regexdata.json", ["tools/build_regexdata.py", os.path.join(r, "mods.json"), "regexdata.json",
                                    os.path.join(r, "base_items.json")], "repoe"),
                ("tierdata.json", ["tools/build_tierdata.py", r], "repoe"),
                ("trialdata.json", ["tools/build_trialdata.py", r, "trialdata.json"], "repoe"),
                ("mapdata.json", ["tools/build_mapdata.py", os.path.join(r, "world_areas.json")], "repoe")]
    if e:
        out.append(("gamedata.json", ["tools/build_gamedata.py", e, "gamedata.json"], "ee2"))
    if p:
        out.append(("uniquedata.json", ["tools/build_uniquedata.py", p, "uniquedata.json"] +
                    (["--repoe", r] if r else []), "pob"))
        tree = newest_tree(p)
        if tree and r:
            ver = os.path.join(os.path.dirname(r.rstrip("/\\")), "version.txt")
            out.append(("anointdata.json", ["tools/build_anointdata.py", tree, os.path.join(r, "base_items.json")] +
                        ([ver] if os.path.exists(ver) else []), "pob + repoe"))
    # searchdata.json is left alone: it is built from a saved trade site page, not from these sources
    out.append(("gamedb.json", ["tools/build_gamedb.py"], "the files above"))
    return out


# ---------------------------------------------------------------- items in a file, by a stable key
def items(name, data):
    """{key: item} of a data file's main list, for counting and for keeping what a new build leaves out."""
    if not isinstance(data, dict):
        return {}
    if name == "uniquedata.json":
        return dict(data.get("uniques") or {})
    if name == "searchdata.json":                    # its rows are [name, group, class, keywords, text]
        return {f"{r[0]}|{r[1]}": r for r in data.get("rows") or [] if isinstance(r, list) and len(r) >= 2}
    if name in ("gamedb.json", "anointdata.json"):
        out = {}
        for r in data.get("rows") or []:
            k = r.get("id") or r.get("name") or r.get("n")
            if k:
                out[str(k)] = r
        return out
    if name == "gamedata.json":
        return dict(data.get("bases") or {})
    if name == "tierdata.json":
        return dict(data.get("mods") or {})
    if name == "regexdata.json":                    # counted, not kept: a mod the game dropped can't roll
        return {f"{t}/{i}": m for t, ms in (data.get("types") or {}).items()
                for i, m in enumerate(ms if isinstance(ms, list) else (ms or {}).get("mods") or [])}
    if name == "trialdata.json":
        return {f"{k}/{i}": x for k in ("modifiers", "wagers", "items", "keywords", "areas")
                for i, x in enumerate(data.get(k) or [])}
    if name == "mapdata.json":
        return dict(data.get("areas") or {})
    if name == "modlists.json":
        return {f"{part}/{kind}/{sec}/{line}": line for part in ("tablets", "jewels")
                for kind, secs in (data.get(part) or {}).items() for sec, lines in (secs or {}).items()
                for line in lines or [] if isinstance(line, str)}
    return {}


def keep_missing(name, old, new, version):
    """Put back what the new build left out, marked with the version it went missing in. Returns how many."""
    before, after = items(name, old), items(name, new)
    gone = [k for k in before if k not in after]
    if not gone:
        return 0
    if name == "uniquedata.json":
        for k in gone:
            u = dict(before[k])
            u.setdefault("gone", version)
            new.setdefault("uniques", {})[k] = u
    elif name == "searchdata.json":                 # a row stays as it was; its mark sits beside the rows
        for k in gone:
            new.setdefault("rows", []).append(before[k])
            new.setdefault("gone", {})[k] = (old.get("gone") or {}).get(k, version)
    elif name in ("gamedb.json", "anointdata.json"):
        for k in gone:
            r = dict(before[k])
            r.setdefault("gone", version)
            if name == "gamedb.json":
                props = [p for p in r.get("props") or [] if p and p[0] != "Not in the files of"]
                r["props"] = props + [["Not in the files of", version]]
            new.setdefault("rows", []).append(r)
    elif name == "gamedata.json":
        for k in gone:
            new.setdefault("bases", {})[k] = dict(before[k], gone=version)
    elif name == "mapdata.json":
        for k in gone:
            new.setdefault("areas", {})[k] = dict(before[k], gone=version)
    else:
        return 0                                     # modlists: a mod line the game dropped can't roll any more
    return len(gone)


def mark_new(name, old, new, version):
    """Mark what the new build added: Game Search can show it as new."""
    before, after = items(name, old), items(name, new)
    added = [k for k in after if k not in before]
    if name == "searchdata.json":
        marks = new.setdefault("added", {})
        for k in added:
            marks[k] = version
            (new.get("gone") or {}).pop(k, None)
        return len(added)
    for k in added:
        it = after[k]
        if isinstance(it, dict):
            it.setdefault("added", version)
            it.pop("gone", None)                         # back in the files
    return len(added)


# ---------------------------------------------------------------- helpers
def read(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def md5(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def game_version(repoe):
    for d in (repoe, os.path.dirname(repoe.rstrip("/\\"))) if repoe else ():
        p = os.path.join(d, "version.txt")
        if os.path.exists(p):
            return open(p, encoding="utf-8").read().strip()
    return "unknown"


def bump(names):
    """Raise each changed file's number in BUNDLED_DATA."""
    p = os.path.join(ROOT, "soe2", "config.py")
    s = open(p, encoding="utf-8").read()
    for n in names:
        s, k = re.subn(r'("%s":\s*)(\d+)' % re.escape(n), lambda m: m.group(1) + str(int(m.group(2)) + 1), s, count=1)
        if not k:
            print(f"  note: {n} is not in BUNDLED_DATA - add it by hand if the app ships it")
    open(p, "w", encoding="utf-8").write(s)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repoe", help="RePoE's poe2/data folder")
    ap.add_argument("--pob", help="Path of Building PoE2 checkout")
    ap.add_argument("--ee2", help="Exiled Exchange 2 checkout")
    ap.add_argument("--dry", action="store_true", help="say what would run; change nothing")
    ap.add_argument("--force", action="store_true", help="run on even when a file would lose many items")
    a = ap.parse_args(argv)
    ver = game_version(a.repoe)
    plan = steps(a)
    print(f"Game version {ver}. {len(plan)} steps:")
    for name, cmd, need in plan:
        print(f"  {name:18} from {need}")
    if a.dry:
        return 0
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(ROOT, "_update_backup", stamp)
    os.makedirs(backup, exist_ok=True)
    report, changed, stopped = [f"# Game data update {stamp}", "", f"Game version: {ver}", ""], [], False
    for name, cmd, _need in plan:
        path = os.path.join(ROOT, name)
        old = read(path)
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(backup, name))
        before = md5(path)
        res = subprocess.run([PY] + cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            report.append(f"- {name}: the builder failed, old file kept. {res.stderr.strip()[-300:]}")
            if os.path.exists(os.path.join(backup, name)):
                shutil.copy2(os.path.join(backup, name), path)
            continue
        new = read(path)
        n_old, n_new = len(items(name, old)), len(items(name, new))
        if old is not None and n_old and n_new < n_old * (1 - DROP_LIMIT) and not a.force:
            report.append(f"- {name}: STOPPED. {n_old} items would become {n_new}. Old file put back.")
            shutil.copy2(os.path.join(backup, name), path)
            stopped = True
            break
        kept = added = 0
        if old is not None and new is not None:
            kept = keep_missing(name, old, new, ver)
            added = mark_new(name, old, new, ver)
            if kept or added:
                write(path, new)
        if md5(path) != before:
            changed.append(name)
        report.append(f"- {name}: {n_old} → {n_new} items. {added} new, {kept} kept though not in the new files.")
    if stopped:
        for name, _c, _n in plan:                         # put every file back: a half update is worse
            b = os.path.join(backup, name)
            if os.path.exists(b):
                shutil.copy2(b, os.path.join(ROOT, name))
        report += ["", "Stopped: every file is back as it was. Check the sources, or run again with --force."]
        changed = []
    elif a.repoe and a.pob:
        snap = subprocess.run([PY, "tools/build_snapshot.py", a.repoe, a.pob], cwd=ROOT, capture_output=True, text=True)
        report.append("- snapshot: " + (snap.stdout.strip().splitlines() or ["made"])[-1] if snap.returncode == 0
                      else "- snapshot: kept the one already saved for this version")
    if changed:
        bump(changed)
        report += ["", "Shipped again: " + ", ".join(changed)]
    with open(os.path.join(ROOT, "_update_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print("\n".join(report))
    return 1 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
