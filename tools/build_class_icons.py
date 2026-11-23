"""3.3.0 owner: a picture for every item type ships with the app, so Mod Lab and the rest never wait on a price check.
Links only: the app never holds the game's art.

Writes soe2/class_icons.py:
  BASE_ART    {base name: its picture's path} for every equipment base, from RePoE's export: each base's own art,
              served from RePoE's GitHub repository at one fixed commit - ART_ROOT + path + ".png".
  CLASS_ICONS {base name: picture link}, one base for each class: a link the app learned from a listing on this PC
              when there is one, the trade site's own; else the class's lowest-level base from BASE_ART.

    git clone --depth 1 --filter=blob:none --sparse https://github.com/repoe-fork/poe2 repoe2
    cd repoe2 && git sparse-checkout set data && cd ..
    py tools/build_class_icons.py repoe2"""
import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "soe2", "class_icons.py")
SKIP = {"tablet", "waystone"}                    # tablets and waystones ship already: TABLET_ICONS, WAYSTONE_ICON
PREFIX = "Art/2DItems/"


def classes():
    """{class: [bases, lowest level first]} from gamedata.json."""
    from soe2 import gamedata
    out = {}
    for name, e in (gamedata.load().get("bases") or {}).items():
        c = (e or {}).get("class")
        if c and c not in SKIP and not name.startswith("Runeforged"):
            out.setdefault(c, []).append((int((e or {}).get("level") or 0), name))
    return {c: [n for _lv, n in sorted(v)] for c, v in out.items()}


def base_art(repo):
    """{base name: path under Art/2DItems without the extension} for every gamedata base whose png RePoE has -
    waystones and tablets aside: their pictures ship already."""
    from soe2 import gamedata
    items = json.load(open(os.path.join(repo, "data", "base_items.json"), encoding="utf-8"))
    pngs = set(subprocess.run(["git", "-C", repo, "ls-files", "data/Art/2DItems/*.png"], capture_output=True,
                              text=True, check=True).stdout.split())
    by_name = {}
    for e in items.values():
        dds = ((e or {}).get("visual_identity") or {}).get("dds_file") or ""
        n = (e or {}).get("name")
        if n and dds.startswith(PREFIX) and n not in by_name and f"data/{dds[:-4]}.png" in pngs:
            by_name[n] = dds[len(PREFIX):-4]
    bases = gamedata.load().get("bases") or {}
    return {b: by_name[b] for b in sorted(bases) if b in by_name and (bases[b] or {}).get("class") not in SKIP}


def from_learned(by_class):
    from soe2.config import load_json
    from soe2.pricecheck_page import unique_art
    learned = load_json("icons.json", {}) or {}
    got = {}
    for c, bases in by_class.items():
        for b in bases:
            url = learned.get(b)
            if str(url or "").startswith("https://") and not unique_art(url):
                got[c] = (b, url)
                break
    return got


def art_root(commit):
    return f"https://raw.githubusercontent.com/repoe-fork/poe2/{commit}/data/Art/2DItems/"


def write(commit, art, got):
    lines = ['"""3.3.0: a picture link for every equipment base and one for each class - tools/build_class_icons.py',
             "writes this file; do not edit by hand. Links only: RePoE's export of the game's base art, and the trade",
             "site's own picture links learned on the owner's PC. A picture learned from a listing wins.\"\"\"",
             f"ART_ROOT = {json.dumps(art_root(commit))}", "", "BASE_ART = {"]
    lines += [f"    {json.dumps(b)}: {json.dumps(p)}," for b, p in art.items()]
    lines += ["}", "", "CLASS_ICONS = {"]
    for c in sorted(got):
        b, url = got[c]
        lines.append(f"    {json.dumps(b)}: {json.dumps(url)},   # {c}")
    lines.append("}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main(argv):
    repo = argv[0] if argv else "repoe2"
    commit = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    art = base_art(repo)
    by_class = classes()
    got = from_learned(by_class)
    for c, bases in by_class.items():
        if c not in got:
            b = next((x for x in bases if x in art), None)
            if b:
                got[c] = (b, art_root(commit) + art[b] + ".png")
    write(commit, art, got)
    missing = sorted(set(by_class) - set(got))
    print(f"Wrote {OUT}: {len(art)} bases, {len(got)} classes." + (f" No picture: {', '.join(missing)}." if missing
                                                                    else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
