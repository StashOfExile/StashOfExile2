"""Makes soe2/cleanwords.json and board/src/gamewords.json: the one word filter the app and the board share.

1. tools/build_cleanwords.mjs dumps the board's lists and the obscenity library's patterns.
2. Every word of the game's own text that the filter would refuse goes on an allow list: Strongbox, Bestial ...
   A filter that refuses the game's words is no use in a tool about the game.
Run after the board's lists or the game data change:   python tools/build_cleanwords.py"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
GAME = ("regexdata.json", "searchdata.json", "tierdata.json", "anointdata.json", "gamedata.json", "gamedb.json",
        "cxnames.json", "modlists.json")
# everyday words of the same families, which players type about the game
EXTRA = {"stronger", "strongest", "strongly", "stronghold", "headstrong", "beastial", "bestiary", "strongman"}
OUT, BOARD = os.path.join(ROOT, "soe2", "cleanwords.json"), os.path.join(ROOT, "board", "src", "gamewords.json")


def game_words():
    words = set()

    def walk(x):
        if isinstance(x, str):
            if 2 < len(x) < 90 and " " in x or x.istitle():          # shown text, not ids
                words.update(w.lower() for w in re.findall(r"[^\W\d_]{4,}", x))
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    for f in GAME:
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                walk(json.load(fh))
        except (OSError, ValueError):
            print("skipped", f)
    return words


def main():
    subprocess.run(["node", os.path.join(ROOT, "tools", "build_cleanwords.mjs"), os.path.join(ROOT, "board"), OUT],
                   check=True)
    with open(OUT, encoding="utf-8") as f:
        d = json.load(f)
    d["allow"] = []
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f)
    from soe2 import cleantext as CT
    CT._D.clear()
    listed = set(d["hate"]) | set(d["rude"])
    allow = sorted({w for w in game_words() | EXTRA if w not in listed and CT.problem(w)})
    d["allow"] = allow
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    with open(BOARD, "w", encoding="utf-8") as f:
        json.dump({"note": "Made by tools/build_cleanwords.py. The game's own words the filter must let through.",
                   "allow": allow}, f, ensure_ascii=False)
    print("allowed game words:", len(allow))
    return allow


if __name__ == "__main__":
    main()
