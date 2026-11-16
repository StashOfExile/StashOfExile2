"""The Campaign Helper's guide pack, campaign.json (2.77.0).

    py tools/build_guide.py --check            check the layout (run on every pull request that touches it)
    py tools/build_guide.py --pull [board url] add the zones players' logs found that the pack doesn't have yet
                                               (pooled by the community board, seen by 3 or more installs), and
                                               raise the revision - the app downloads the new pack by itself

Hand-written: each step's "do", the tips, the rewards and the vendor searches. The route's zones are learned."""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "campaign.json")
KINDS = {"points", "spirit", "res_cold", "res_fire", "res_lightning", "life", "life_pct", "mana", "other"}
MIN_SEEN = 3
MAX_LINE = 70                    # style 2: a step's line is written whole (verb, target, gain, → next) - at most this
CUE_KINDS = {"s", "d", "q"}      # a boss fight began / the boss is down / a quest moved on


def norm(name):
    s = re.sub(r"[^a-z0-9 ]", "", str(name or "").lower()).strip()
    return s[4:] if s.startswith("the ") else s


def problems(d):
    out = []
    if d.get("schema") != 2:
        out.append("schema must be 2")
    keys = [a.get("key") for a in d.get("acts") or []]
    if len(set(keys)) != len(keys) or not keys:
        out.append("acts: every act needs its own key")
    for a in d.get("acts") or []:
        if not re.match(r"^(\d|i\d)$", str(a.get("key"))):
            out.append(f"act {a.get('key')}: key is a number, or i + a number (interludes)")
        zones = [norm(s.get("zone")) for s in a.get("steps") or []]
        if "" in zones:
            out.append(f"act {a.get('key')}: a step has no zone")
        if len(set(zones)) != len(zones):
            out.append(f"act {a.get('key')}: a zone is listed twice")
        for s in a.get("steps") or []:
            texts = [s.get("do"), (s.get("speed") or {}).get("do"), (s.get("rush") or {}).get("do"), s.get("back"),
                     s.get("early")]
            for t in texts:
                if d.get("style", 1) >= 2 and t and len(t) > MAX_LINE:
                    out.append(f"{s.get('zone')}: a line is {len(t)} characters (at most {MAX_LINE}): {t}")
                if t and "On you go" in t:
                    out.append(f"{s.get('zone')}: say what to do (never 'On you go')")
            if s.get("side") and not (s.get("speed") or {}).get("skip") and not (s.get("speed") or {}).get("do"):
                out.append(f"{s.get('zone')}: a side zone needs its own speed text (or speed skip)")
    ids = [r.get("id") for r in d.get("rewards") or []]
    if len(set(ids)) != len(ids):
        out.append("rewards: every reward needs its own id")
    for r in d.get("rewards") or []:
        if r.get("act") not in keys:
            out.append(f"reward {r.get('id')}: act {r.get('act')} isn't in acts")
        if r.get("kind") not in KINDS:
            out.append(f"reward {r.get('id')}: kind must be one of {sorted(KINDS)}")
        if not r.get("zone") or not r.get("what") or not r.get("gives"):
            out.append(f"reward {r.get('id')}: needs zone, what and gives")
    for aid, cues in (d.get("cues") or {}).items():
        for c in cues:
            if not isinstance(c, list) or len(c) < 3 or c[0] not in CUE_KINDS or not c[1] or not c[2]:
                out.append(f"cue in {aid}: needs [kind (s/d/q), speaker, line(, note)]: {c}")
    for r in d.get("rewards") or []:
        if r.get("cue") and r["cue"] not in (d.get("cues") or {}):
            out.append(f"reward {r.get('id')}: its cue area {r['cue']} has no cues")
    for v in d.get("vendor") or []:
        if not v.get("name") or not v.get("regex") or (v.get("act") != "*" and v.get("act") not in keys):
            out.append(f"vendor search {v.get('name')}: needs name, regex and an act (or *)")
    return out


def merge(d, zones):
    """Pooled zones -> added to their act after the zone players came from. -> how many were added."""
    added = 0
    for z in sorted(zones, key=lambda z: -int(z.get("n") or 0)):
        if int(z.get("n") or 0) < MIN_SEEN:
            continue
        if not all(re.fullmatch(r"[\w ',.\-]{0,80}", str(z.get(k) or "")) for k in ("zone", "after")) or not z.get("zone"):
            continue                                           # 2.89.3: odd text never reaches the guide pack
        a = next((x for x in d["acts"] if x["key"] == z.get("act")), None)
        if a is None:
            if not re.match(r"^(\d|i\d)$", str(z.get("act"))):
                continue
            n = z["act"]
            a = {"key": n, "name": f"Interlude {n[1:]}" if n.startswith("i") else f"Act {n}", "prefix": "", "town": "",
                 "steps": []}
            d["acts"].append(a)
        steps = a.setdefault("steps", [])
        if any(norm(s["zone"]) == norm(z["zone"]) for s in steps):
            continue
        at = next((i for i, s in enumerate(steps) if norm(s["zone"]) == norm(z.get("after"))), len(steps) - 1)
        steps.insert(at + 1, {"zone": z["zone"], "do": "", "learned": True})
        added += 1
    return added


def main(argv):
    with open(FILE, encoding="utf-8") as f:
        d = json.load(f)
    bad = problems(d)
    for p in bad:
        print("PROBLEM", p)
    if bad:
        return 1
    if "--pull" in argv:
        i = argv.index("--pull")
        url = argv[i + 1] if len(argv) > i + 1 else open(os.path.join(ROOT, "board", "url.txt")).read().strip()
        req = urllib.request.Request(url.rstrip("/") + "/campaign/zones", headers={"User-Agent": "soe2-build-guide"})
        with urllib.request.urlopen(req, timeout=30) as r:
            zones = json.load(r).get("zones") or []
        n = merge(d, zones)
        if n:
            d["revision"] = int(d.get("revision", 0)) + 1
            with open(FILE, "w", encoding="utf-8", newline="\n") as f:
                json.dump(d, f, indent=1, ensure_ascii=False)
                f.write("\n")
        print(f"campaign.json: {n} zones added, revision {d.get('revision')}")
        return 0
    print(f"campaign.json: {len(d['acts'])} acts, {len(d.get('rewards') or [])} rewards - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
