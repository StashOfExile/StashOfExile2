"""3.0.6 (RMT is always blocked / disallowed): no real-money-trading or currency-seller site is ever a source.
Fails when one is named anywhere in the app, its data or its docs (this file and the list below aside)."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# RMT / currency sellers / boosting shops, plus the two AI-written guide sites the owner banned
SITES = ("aoeah", "mmoexp", "u4n", "u4gm", "poecurrency", "mulefactory", "g2g", "eldorado.gg", "playerauctions",
         "mmogah", "iggm", "lootbar", "rpgstash", "odealo", "z2u", "boostmatch", "overgear", "expcarry", "game8",
         "fextralife", "chimba.ru", "gamingwithdaopa")
PAT = re.compile(r"\b(" + "|".join(re.escape(s) for s in SITES) + r")\b", re.I)
SKIP = {os.path.join("tools", "check_rmt.py"), os.path.join("tools", "build_gamedb.py"), os.path.join("soe2", "whatsnew.py"),
        os.path.join("tests", "test_gamedb.py")}              # (the blacklist itself, and its tests)


def main():
    bad = []
    for top in ("soe2", "tools", "tests", "."):
        base = os.path.join(ROOT, top)
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in (".git", "__pycache__", "node_modules", "dist", "build")]
            if top == "." and os.path.abspath(dp) != os.path.abspath(ROOT):
                continue
            for f in fn:
                if not f.endswith((".py", ".json", ".md", ".txt")):
                    continue
                rel = os.path.relpath(os.path.join(dp, f), ROOT)
                if rel in SKIP or rel.startswith(os.path.join("tests", "test_check_rmt")):
                    continue
                try:
                    text = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                for k, line in enumerate(text.splitlines(), 1):
                    m = PAT.search(line)
                    if m and "RMT" not in line and "never" not in line.lower():
                        bad.append(f"{rel}:{k}: {m.group(1)}")
    for b in bad:
        print("RMT / banned source named:", b)
    print(f"check_rmt: {len(bad)} found")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
