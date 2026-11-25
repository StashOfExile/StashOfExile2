"""data_manifest.json: what the app may download from main (soe2/datasync.py) - each shipped data file with its
BUNDLED_DATA number and SHA-256, and each snapshot. Run by .github/workflows/game-data.yml after an update.

    py tools/build_data_manifest.py"""
import ast
import glob
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled():
    tree = ast.parse(open(os.path.join(ROOT, "soe2", "config.py"), encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "BUNDLED_DATA" for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError("BUNDLED_DATA")


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    files = {n: {"version": v, "sha256": sha(os.path.join(ROOT, n))} for n, v in bundled().items()
             if os.path.isfile(os.path.join(ROOT, n))}
    snaps = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(ROOT, "snapshots", "poe2-*.json.gz")))}
    with open(os.path.join(ROOT, "data_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"files": files, "snapshots": snaps}, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"data_manifest.json: {len(files)} files, {len(snaps)} snapshots")


if __name__ == "__main__":
    main()
