"""Build gamedb.json - the offline game database inside Game Search (tablets, waystones, Atlas masters, Vaal Temple,
pinnacles and areas, Trial of the Sekhemas, Trial of Chaos, Ritual altars, leagues). Only facts from the game's own files: the RePoE
exports already in the repo (modlists.json, regexdata.json, mapdata.json, trialdata.json), gamedata.json, searchdata.json (the game's
text), and a few names that live in the app's code (soe2/ritualid.py, medallions.py, vaallens_plan.py, moneymakers.py,
waystone.py). No community opinions (ratings, tier lists, "why" lines) and nothing is looked up when the app runs.

    py tools/build_gamedb.py                 build, verify, write gamedb.json (refuses to write if a check fails)
    py tools/build_gamedb.py --check         verify only (also says if gamedb.json is out of date)
    py tools/build_gamedb.py --refresh-samples DIR
                                             rewrite tests/fixtures/gamedb_samples.txt from the tablet / waystone copies in
                                             DIR (the test build's data folder: session.json "raw" text, unpriced_items.txt);
                                             only item text is kept - no ids, names, prices or accounts
    options: --samples FILE (default tests/fixtures/gamedb_samples.txt), --trade-dir DIR (a data folder with the app's
             cached trade_filters.json, to check the waystone header filter ids), --out FILE

Checks (any failure: each is printed, nothing is written, exit 1):
  * every tablet / waystone mod resolves to a stat in gamedata.json (or is in KNOWN_UNRESOLVED below, with a reason)
  * every item / base name exists in gamedata.json bases / currency / uniques (or searchdata's keywords for medallions)
  * modlists.json and regexdata.json agree on every tablet type's mods, sides and ranges (RePoE sometimes prints a range
    reversed, (30-20): compared as numbers); waystone tier bands agree with the base's tier
  * every tablet / waystone mod line on the owner's real copies (tests/fixtures/gamedb_samples.txt) matches a row,
    rolls on that tablet type, and its roll range lies inside the row's range

REMOVING A WRONG ROW WITHOUT A REBUILD: add its id to gamedb_hide.json (a list of {"id": "...", "reason": "one line"}).
Game Search hides it the next time it opens (and the build skips it the next time it runs). Row ids are in gamedb.json
and shown in the row's details. A hidden id that matches no row is only warned about.

After a rebuild, raise "gamedb.json" in BUNDLED_DATA (soe2/config.py) so existing data folders take the new file."""
import argparse
import ast
import collections
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.environ.get("SOE2_GAMEDB_KEEP_HOME"):                      # (importing soe2 must not touch the owner's data folder)
    _tmp = tempfile.mkdtemp(prefix="soe2-gamedb-")
    os.environ["HOME"] = os.environ["APPDATA"] = _tmp
sys.path.insert(0, ROOT)
from soe2 import gamedata, mods, names                                # noqa: E402

SCHEMA = 1
GROUPS = names.GAME_SEARCH_GROUPS                                     # (one name per feature: soe2/names.py)
NOT_IN_DATA = "Effect not in the game data yet"
# permanent owner rule: game8 and fextralife are AI-generated and wrong - never a data source (see tools/README.txt)
BLACKLIST = re.compile(r"game8|fextralife", re.I)
SAMPLES = os.path.join("tests", "fixtures", "gamedb_samples.txt")
BANDS = {"map_key_low": "T1-5", "map_key_medium": "T6-10", "map_key_high": "T11-15", "map_key_highest": "T16"}
BAND_TIERS = {"T1-5": range(1, 6), "T6-10": range(6, 11), "T11-15": range(11, 16), "T16": range(16, 17)}
# mod lines the gamedata.json stat table (Exiled Exchange 2 snapshot of 2026-09-06) has no stat for yet. The live
# trade site list has both (stats_cache.json); the snapshot is older than the game. Key = mods.norm() of the line.
KNOWN_UNRESOLVED = {
    "delirium fog in map spawns #% increased mirror shards": "newer than gamedata.json; the live trade stat list has it",
    "expeditions have #% surpassing chance to contain an additional verisium remnant":
        "newer than gamedata.json; the live trade stat list has it",
}


# ---------------------------------------------------------------- reading
def read_json(root, name):
    with open(os.path.join(root, name), encoding="utf-8-sig") as f:
        return json.load(f)


def py_const(root, rel, name):
    """The literal value of NAME = ... in a module (read from the source, so nothing is imported or run)."""
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {rel}")


def slug(text, limit=110):
    t = re.sub(r"[^a-z0-9]+", "-", str(text).lower().replace("&", " and ").replace("'", "")).strip("-")
    return t[:limit].strip("-")


def pairs(line):
    """[(min, max)] for every (a—b) range in a modlists line (reversed ranges like (30—20) become (20, 30))."""
    out = []
    for m in re.finditer(r"\((-?\d+(?:\.\d+)?)\s*[—–-]\s*(-?\d+(?:\.\d+)?)\)", line):
        a, b = float(m.group(1)), float(m.group(2))
        out.append((min(a, b), max(a, b)))
    return out


COPY_ROLL = re.compile(r"[+-]?\d+(?:\.\d+)?\(-?\d+(?:\.\d+)?-\d+(?:\.\d+)?\)")      # "17(15-19)" on a copied item


def line_key(line):
    """One key for a mod line from any source (modlists "(10—15)%", regexdata "#%", a copied item's "17(15-19)%"):
    every number or range -> #, markup and signs gone, lower case."""
    t = mods._RANGE.sub("#", COPY_ROLL.sub("#", line))
    return gamedata.norm_mod(t).replace("-#", "#")


def fmt(n):
    return str(int(n)) if float(n) == int(n) else str(n)


def rng(a, b):
    return fmt(a) if a == b else f"{fmt(a)}–{fmt(b)}"


class Build:
    def __init__(self, root=ROOT, samples=None, trade_dir=None, hide=None):
        self.root, self.samples, self.trade_dir = root, samples, trade_dir
        self.rows, self.fail, self.warn, self.notes = [], [], [], []
        self.hide = hide if hide is not None else self._read_hide()
        self.versions = {}

    # ---- helpers
    def _read_hide(self):
        p = os.path.join(self.root, "gamedb_hide.json")
        if not os.path.isfile(p):
            return {}
        data = read_json(self.root, "gamedb_hide.json")
        out = {}
        for e in data if isinstance(data, list) else []:
            if isinstance(e, dict) and e.get("id"):
                out[e["id"]] = e.get("reason", "")
        return out

    def add(self, id_, name, group, cls, tags, parts, source, version):
        """parts: a str is a line of game text / effect; a (label, value) pair is a property. Game Search draws the
        properties as a label / value list and the lines one each; "text" is all of it as one string (for search)."""
        props = [list(p) for p in parts if isinstance(p, tuple) and p[1]]
        lines = [p for p in parts if isinstance(p, str) and p]
        text = " | ".join(p if isinstance(p, str) else f"{p[0]}: {p[1]}" for p in parts if p and (isinstance(p, str) or p[1]))
        self.rows.append({"id": id_, "name": name, "group": group, "class": cls, "tags": tags, "text": text,
                          "props": props, "lines": lines, "source": source, "version": version})

    def bad(self, msg):
        self.fail.append(msg)

    def resolve(self, line):
        """-> the gamedata.json stat entry for a mod line, or None."""
        e, _neg = gamedata.stat_for(mods._RANGE.sub("5", line).replace("#", "5"), learn=False)
        return e

    # ---- the whole build
    def run(self):
        r = self.root
        self.gd = read_json(r, "gamedata.json")
        self.sd = read_json(r, "searchdata.json")
        self.ml = read_json(r, "modlists.json")
        self.rx = read_json(r, "regexdata.json")
        self.mp = read_json(r, "mapdata.json")
        self.league = py_const(r, "soe2/moneymakers.py", "LEAGUE_VERSIONS")
        self.current = list(self.league.values())[-1]             # the version a file with none of its own is shown as
        self.names = set(self.gd["bases"]) | set(self.gd["currency"]) | set(self.gd["uniques"])
        self.sd_rows = {(x[0], x[1]): x for x in self.sd["rows"]}
        self.ml_ver = self.ml.get("game_version") or self.current
        self.versions = {"modlists.json": self.ml.get("game_version"), "anointdata.json": None, "searchdata.json":
                         self.sd.get("version"), "regexdata.json": None, "mapdata.json": None, "gamedata.json": None}
        self.tablets()
        self.waystones()
        self.masters()
        self.temple()
        self.areas()
        self.sekhemas()
        self.trialofchaos()
        self.altars()
        self.leagues()
        self.samples_check()
        self.finish()
        return self

    # ---------------------------------------------------------------- Tablets
    def tablets(self):
        G = "Tablets"
        tags_by_base = {n: b for n, b in self.gd["bases"].items() if b.get("class") == "tablet"}
        impl = {s["ref"].splitlines()[0].strip(): s for s in self.gd["stats"]
                if "use" in s["ref"] and "remaining" in s["ref"] and (s.get("trade") or {}).get("implicit")}
        types = {}                                              # "Abyss" -> {"base", "implicit", "id", "tag"}
        for base, b in sorted(tags_by_base.items()):
            word = base.rsplit(" ", 1)[0]
            row = self.sd_rows.get((base, "Endgame Items"))
            text = row[4] if row else ""
            m = re.match(r"(.*?)\s*(\d+) uses remaining$", text)
            if not row or not m:
                self.bad(f"{base}: no tablet row with an implicit line in searchdata.json (Endgame Items)")
                continue
            implicit, uses = m.group(1), int(m.group(2))
            st = impl.get(implicit)
            tid = ((st or {}).get("trade") or {}).get("implicit") or [None]
            if not st:
                self.bad(f"{base}: implicit '{implicit}' has no stat in gamedata.json")
            types[word] = {"base": base, "implicit": implicit, "uses": uses, "id": tid[0], "tag": row[3].split(",")[0].strip(),
                           "gtags": b.get("tags") or []}
        self.tablet_types = types
        # modlists: every mod, which types roll it, which side, which ranges
        pool = collections.OrderedDict()
        for tname, secs in self.ml["tablets"].items():
            word = tname.rsplit(" ", 1)[0]
            if word not in types:
                self.bad(f"modlists.json has a tablet type '{tname}' that gamedata.json has no base for")
            for side in ("Prefix", "Suffix"):
                for line in secs.get(side) or []:
                    k = line_key(line)
                    e = pool.setdefault(k, {"lines": {}, "sides": set(), "types": set(), "pairs": {}})
                    e["lines"][word] = line
                    e["sides"].add(side)
                    e["types"].add(word)
                    e["pairs"][word] = pairs(line)
        rx = {}
        for m in self.rx["types"]["tablet"]["mods"]:
            for ln in m["lines"]:
                rx[line_key(ln)] = m
        # cross-source agreement
        for k, e in pool.items():
            if len(e["sides"]) > 1:
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}': Prefix in some tablet types and Suffix in others")
            if len({tuple(v) for v in e["pairs"].values()}) > 1:
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}': the range differs between tablet types "
                         + "; ".join(f"{t} {e['lines'][t]}" for t in sorted(e["lines"])))
            m = rx.get(k)
            if not m:
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}' is in modlists.json but not in regexdata.json")
                continue
            want = set(types) if "Any" in m["tags"] else {t for t in m["tags"] if t != "Any"}
            if want != e["types"]:
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}': modlists.json says {sorted(e['types'])}, "
                         f"regexdata.json says {sorted(want)}")
            if m["side"].capitalize() not in e["sides"]:
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}': side differs ({sorted(e['sides'])} vs {m['side']})")
            pr = next(iter(e["pairs"].values()))
            if pr and (abs(pr[0][0] - m["min"]) > 1e-9 or abs(pr[0][1] - m["max"]) > 1e-9):
                self.bad(f"tablet mod '{next(iter(e['lines'].values()))}': range {pr[0]} in modlists.json, "
                         f"{(m['min'], m['max'])} in regexdata.json")
        for k, m in rx.items():
            if k not in pool:
                self.bad(f"tablet mod '{m['lines'][0]}' is in regexdata.json but not in modlists.json")
        self.tablet_pool, self.tablet_rx = pool, rx
        # rows: one per type
        counts = {w: [0, 0] for w in types}
        for e in pool.values():
            for w in e["types"]:
                if w in counts:
                    counts[w][0 if "Prefix" in e["sides"] else 1] += 1
        for word, t in sorted(types.items()):
            n = sum(counts[word])
            extra = {"Temple": "incursion, vaal beacons", "Overseer": "map boss", "Irradiated": "generic"}.get(word, "")
            self.add(f"tablet/{slug(word)}", t["base"], G, "Tablet", ", ".join(x for x in (t["tag"], "tablet", extra) if x),
                     [t["implicit"], ("Uses", f"{t['uses']} (the item says '{t['uses']} uses remaining')"),
                      ("Mods that can roll", f"{n}: {counts[word][0]} prefixes, {counts[word][1]} suffixes"),
                      ("Implicit trade stat", t["id"])],
                     f"searchdata.json Endgame Items + gamedata.json stats + modlists.json {t['base']}", self.ml_ver)
        # rows: one per mod
        for k, e in pool.items():
            first = e["lines"][sorted(e["lines"])[0]]
            st = self.resolve(first)
            tid = self.stat_id(st, k, first, "tablet")
            side = sorted(e["sides"])[0]
            m = rx.get(k) or {}
            tn = sorted(e["types"])
            every = len(tn) == len(types)
            where = f"all {len(types)} tablet types" if every else (tn[0] + " Tablet" if len(tn) == 1 else
                                                                   ", ".join(t + " Tablet" for t in tn))
            pr = next(iter(e["pairs"].values()))
            self.add(f"tablet/{'any' if every else slug(tn[0]) if len(tn) == 1 else 'some'}/mod/{slug(mods._RANGE.sub('', first))}",
                     first, G, f"Tablet {side}", ", ".join(x for x in ["tablet", side.lower()] + tn + list(m.get("names") or [])),
                     [("Affix", side), ("Rolls on", where),
                      ("Range", " and ".join(rng(a, b) for a, b in pr) if pr else ""),
                      ("Mod name", ", ".join(m["names"]) if m.get("names") else ""), ("Trade stat", tid)],
                     "modlists.json tablets + regexdata.json tablet", self.ml_ver)

    def stat_id(self, st, key, line, what):
        if st is None:
            if key not in KNOWN_UNRESOLVED:
                self.bad(f"{what} mod '{line}' has no stat in gamedata.json (not in KNOWN_UNRESOLVED either)")
            return ""
        if key in KNOWN_UNRESOLVED:
            self.warn.append(f"'{key}' is in KNOWN_UNRESOLVED but now resolves - remove it")
        tr = st.get("trade") or {}
        return (tr.get("explicit") or tr.get("implicit") or [""])[0] if tr else ""

    # ---------------------------------------------------------------- Waystones
    def waystones(self):
        G = "Waystones"
        props = py_const(self.root, "soe2/waystone.py", "PROPS")
        heads = py_const(self.root, "soe2/waystone.py", "WAYSTONE_HEADERS")
        filt = None
        if self.trade_dir and os.path.isfile(os.path.join(self.trade_dir, "trade_filters.json")):
            with open(os.path.join(self.trade_dir, "trade_filters.json"), encoding="utf-8-sig") as f:
                tf = json.load(f)
            filt = {fl["id"] for grp in tf.get("result", []) if grp.get("id") == "map_filters"
                    for fl in grp.get("filters", [])}
        else:
            self.notes.append("waystone header filter ids not checked against the trade site's filter list (no --trade-dir)")
        for key in heads:
            if key not in props:
                self.bad(f"waystone header '{key}' is not in waystone.PROPS")
                continue
            fid, short, _d = props[key]
            if filt is not None and fid not in filt:
                self.bad(f"waystone header '{short}': filter id {fid} is not in the trade site's map_filters")
            self.add(f"waystone/header/{slug(short)}", short, G, "Waystone Header Number", "waystone, header, endgame filter",
                     [f"A number at the top of a waystone ('{short}: +N%')", ("Trade filter", f"map_filters.{fid}")],
                     "soe2/waystone.py PROPS + WAYSTONE_HEADERS", self.current)
        for n in range(1, 17):
            base = f"Waystone (Tier {n})"
            b = self.gd["bases"].get(base)
            if not b:
                self.bad(f"{base} is not in gamedata.json bases")
                continue
            band = next((BANDS[t] for t in b.get("tags") or [] if t in BANDS), None)
            if band is None or n not in BAND_TIERS[band]:
                self.bad(f"{base}: tags {b.get('tags')} do not give a tier band that contains tier {n}")
            self.add(f"waystone/tier/{n}", base, G, "Waystone Tier", ", ".join(["waystone", f"tier {n}", band or ""] + list(b.get("tags") or [])),
                     ["Used in a Map Device to open a map of that tier", ("Tier", str(n)), ("Mod band", band or "")],
                     "gamedata.json bases", self.current)
        for m in self.rx["types"]["waystone"]["mods"]:
            line = m["lines"][0]
            key = line_key(line)
            st = self.resolve(line)
            tid = self.stat_id(st, key, line, "waystone")
            for extra in m["lines"][1:]:
                if self.resolve(extra) is None and line_key(extra) not in KNOWN_UNRESOLVED:
                    self.bad(f"waystone mod '{extra}' (second line of {m['id']}) has no stat in gamedata.json")
            shown = []
            for ln in m["lines"]:
                s = self.resolve(ln)
                # the stat's wording has the game's capitals; but it may be the "increased" form of a "reduced" /
                # "more" / "less" line (the trade site's sign flip), so use it only when it says the same thing
                ref = s["ref"] if s and line_key(s["ref"]) == line_key(ln) else None
                text = ref or (ln[:1].upper() + ln[1:])
                sign = re.match(r"[+-]", ln)
                shown.append(("+" if sign and sign.group(0) == "+" and not text.startswith("+") else
                              "-" if sign and sign.group(0) == "-" and not text.startswith("-") else "") + text)
            lo, hi = m["min"], m["max"]
            one = "(" + fmt(lo) + "—" + fmt(hi) + ")" if lo != hi else fmt(lo)
            name = shown[0].replace("#", one, 1) if "#" in shown[0] else shown[0]
            bands = sorted({t for t in m["tags"] if t != "Any"}, key=lambda t: list(BAND_TIERS).index(t) if t in BAND_TIERS else 9)
            if "Any" in m["tags"] or len(bands) == 4:
                tier_text = "all waystone tiers"
            elif not bands:
                tier_text = "?"
                self.bad(f"waystone mod {m['id']} has no tier band")
            else:
                tier_text = "only " + ", ".join(bands)
            side = m["side"].capitalize()
            self.add(f"waystone/mod/{slug(mods._RANGE.sub('', name))}", name, G, f"Waystone {side}",
                     ", ".join(["waystone", side.lower()] + list(m.get("names") or []) + bands),
                     [" / ".join(shown[1:]) if len(shown) > 1 else "", ("Affix", side),
                      ("Mod name", ", ".join(m["names"])), ("Rolls on", tier_text),
                      ("Range", rng(lo, hi) if lo != hi else ""), ("Trade stat", tid)],
                     "regexdata.json waystone", self.current)

    # ---------------------------------------------------------------- Atlas masters
    def masters(self):
        G = "Atlas Masters"
        M = py_const(self.root, "soe2/moneymakers.py", "MASTERS")
        AM = read_json(self.root, "atlasmasters.json")["masters"]       # effect text + source (poe2db.tw), not invented
        for master, ch in M.items():
            if len(ch) != 12:
                self.bad(f"{master}: {len(ch)} choices, expected 12")
            self.add(f"atlas-master/{slug(master)}", master, G, "Atlas Master", "atlas, master",
                     [", ".join(ch), ("Choices", str(len(ch)))], "soe2/moneymakers.py MASTERS", self.current)
            for c in ch:
                e = (AM.get(master) or {}).get(c)
                lines = [x for x in e["text"].split("\n") if x] if e and e.get("text") else [NOT_IN_DATA]
                self.add(f"atlas-master/{slug(master)}/choice/{slug(c)}", c, G, "Atlas Master Choice", f"atlas, master, {master}",
                         lines + [("Master", master)], e["source"] if e and e.get("text") else "soe2/moneymakers.py MASTERS",
                         self.current)

    # ---------------------------------------------------------------- Vaal Temple
    def temple(self):
        G = "Vaal Temple"
        R = py_const(self.root, "soe2/vaallens_plan.py", "ROOMS")
        for fam, names in R.items():
            if not 1 <= len(names) <= 4:
                self.bad(f"room family {fam}: {len(names)} tier names")
            self.add(f"vaal-temple/room/{slug(fam)}", fam, G, "Temple Room", ", ".join(["temple room", "tier"] + list(names)),
                     [" → ".join(names)] + [(f"Tier {i}", n) for i, n in enumerate(names, 1)],
                     "soe2/vaallens_plan.py ROOMS", self.current)
        M = py_const(self.root, "soe2/medallions.py", "MEDALLIONS")
        for name, (short, effect, _w) in M.items():
            row = self.sd_rows.get((name, "Keywords & Mechanics"))
            if not row:
                self.bad(f"medallion '{name}' is not in searchdata.json keywords (not an item in gamedata.json either)")
            text = row[4] if row else effect
            self.add(f"vaal-temple/medallion/{slug(name)}", name, G, "Medallion", f"medallion, atziri's temple, {short.lower()}",
                     [text], "searchdata.json Keywords & Mechanics" if row else "soe2/medallions.py MEDALLIONS",
                     self.sd.get("version") if False else self.current)

    # ---------------------------------------------------------------- Pinnacles & areas
    def areas(self):
        G = "Pinnacles & Areas"
        items = [x for x in self.sd["rows"] if x[1] == "Endgame Items" and x[4]]
        for aid, a in sorted(self.mp["areas"].items(), key=lambda kv: (kv[1]["kind"], kv[1]["name"], kv[0])):
            if a["kind"] not in ("Pinnacle", "Citadel", "Tower"):
                continue
            access = []
            if a["kind"] != "Tower":
                nm = re.sub(r"^The ", "", a["name"])
                for it in items:
                    if re.search(r"\b" + re.escape(nm) + r"\b", it[4], re.I) and it[0] not in access:
                        access.append(it[0])
            parts = [("Area level", str(a["level"])), ("Area id", aid)]
            for it in access:
                parts.append(f"{it}: {self.sd_rows[(it, 'Endgame Items')][4]}")
            self.add(f"area/{slug(aid)}", a["name"], G, a["kind"], ", ".join(["area", a["kind"].lower()] + access),
                     parts, f"mapdata.json areas[{aid}]" + (" + searchdata.json Endgame Items" if access else ""), self.current)
            self.access = getattr(self, "access", {})
            self.access[aid] = access

    # ---------------------------------------------------------------- Trial of the Sekhemas
    def sekhemas(self):
        G = "Trial of the Sekhemas"
        d = read_json(self.root, "soe2/sekhemas.json")
        m = re.search(r"patch (\d+\.\d+\.x|\d+\.\d+)", (d.get("meta") or {}).get("what", ""))
        ver = m.group(1) if m else self.current
        for kind, key in (("Boon", "boons"), ("Affliction", "afflictions")):
            for e in d[key]:
                # only the name and its major / minor class: the file's rating and "why" lines are community notes
                self.add(f"sekhemas/{kind.lower()}/{slug(e['name'])}", e["name"], G, f"{kind} ({e['tier']})",
                         f"trial of the sekhemas, {kind.lower()}, {e['tier']}", [NOT_IN_DATA],
                         f"soe2/sekhemas.json {key}", ver)

    # ---------------------------------------------------------------- Trial of Chaos
    def trialofchaos(self):
        """From trialdata.json (tools/build_trialdata.py: the RePoE poe2 export). Only what the export holds; the checks:
        the export's version is on every row, each modifier has its stat ids and text, each item / keyword is also in
        searchdata.json with the same text, and every id is an export id."""
        G = "Trial of Chaos"
        d = read_json(self.root, "trialdata.json")
        ver, src = d["game_version"], "trialdata.json (RePoE poe2 export)"
        self.versions["trialdata.json"] = ver
        norm = lambda t: re.sub(r"\s+", " ", t or "").strip()                 # noqa: E731
        for kind, key, label in (("modifier", "modifiers", "Trial Modifier"), ("wager", "wagers", "Wager")):
            for m in d[key]:
                if not (m["id"].startswith(("Ultimatum")) and m["stats"] and m["text"] and m["name"]):
                    self.bad(f"trialdata {m.get('id')}: not a complete {kind} from the export")
                    continue
                if kind == "modifier":
                    name, cls, tags = f"Trial Modifier: {m['name']}", "Trial Modifier", "Trial of Chaos, ultimatum, modifier, suffix"
                else:
                    name, cls, tags = f"{m['name']} Wager", "Wager", "Trial of Chaos, ultimatum, wager, prefix"
                self.add(f"trial-of-chaos/{kind}/{slug(m['id'])}", name, G, cls, tags,
                         [("Required level", str(m["level"]))] + m["text"].split("\n"), src, ver)
        for it in d["items"]:
            if not it["id"].startswith("Metadata/Items/"):
                self.bad(f"trialdata item {it['name']}: not an export id")
            hit = self.sd_rows.get((it["name"], "Endgame Items"))
            if hit and norm(hit[4]) != norm(it["directions"]):
                self.bad(f"{it['name']}: the export's text differs from searchdata.json")
            parts = [("Drop level", str(it["drop_level"])), ("Stack size", str(it["stack_size"] or ""))]
            if it["directions"]:
                parts.append(it["directions"])
            self.add(f"trial-of-chaos/item/{slug(it['id'].split('/')[-1])}", it["name"], G, "Trial Item",
                     ", ".join(["Trial of Chaos"] + it["tags"]), parts, src, ver)
        for k in d["keywords"]:
            hit = self.sd_rows.get((k["term"], "Keywords & Mechanics"))
            if hit and norm(hit[4]) != norm(k["text"]):
                self.bad(f"keyword {k['term']}: the export's text differs from searchdata.json")
            self.add(f"trial-of-chaos/keyword/{slug(k['id'])}", k["term"], G, "Keyword", "Trial of Chaos, ruin, keyword",
                     [k["text"].split("\n")[0], *[t for t in k["text"].split("\n")[1:] if t]], src, ver)
        for a in d["areas"]:
            self.add(f"trial-of-chaos/area/{slug(a['id'])}", a["name"], G, "Area", "Trial of Chaos, area",
                     [("Area level", str(a["level"])), ("Act", str(a["act"])), ("Waypoint", "yes" if a["waypoint"] else "no"),
                      ("Area id", a["id"])], src, ver)
        self.notes.append(f"trial of chaos: {d['left_out']['wagers_without_item_name']} wagers left out "
                          "(the export prints no item name for them)")

    # ---------------------------------------------------------------- Ritual altars
    def altars(self):
        G = "Ritual Altars"
        T = py_const(self.root, "soe2/ritualid.py", "TYPES")
        for key, (name, loot, danger) in T.items():
            self.add(f"ritual-altar/{key}", f"{name} Ritual Altar", G, "Ritual Altar", "ritual, altar, " + name.lower(),
                     [danger, ("Reward", loot.rstrip(" ↑"))], "soe2/ritualid.py TYPES", "0.5.2")

    # ---------------------------------------------------------------- Leagues
    def leagues(self):
        G = "Leagues"
        for name, ver in self.league.items():
            self.add(f"league/{slug(name)}", name, G, "League", "league, game version",
                     [("Game version", ver)], "soe2/moneymakers.py LEAGUE_VERSIONS", ver)
        files = [("modlists.json", self.ml.get("game_version"), "tablet and jewel mods (RePoE)"),
                 ("anointdata.json", read_json(self.root, "anointdata.json").get("version"), "anoints"),
                 ("searchdata.json", self.sd.get("version"), "Game Search's other groups"),
                 ("campaign.json", read_json(self.root, "campaign.json").get("patch"), "campaign guide"),
                 ("crafthelper.json", read_json(self.root, "crafthelper.json").get("patch"), "craft flows"),
                 ("regexdata.json", None, f"generated {self.rx.get('generated')}"),
                 ("mapdata.json", None, "areas (RePoE world_areas)"),
                 ("gamedata.json", None, f"generated {self.gd.get('generated')} from an Exiled Exchange 2 snapshot")]
        for f, ver, what in files:
            self.add(f"league/data/{slug(f)}", f"Game data: {f}", G, "Data File Version", "game version, data file",
                     [what, ("Game version", ver or "none in the file")], f, ver or "none")

    # ---------------------------------------------------------------- real-game samples
    def load_samples(self):
        p = self.samples or os.path.join(self.root, SAMPLES)
        if not os.path.isfile(p):
            self.notes.append(f"no samples file ({p}): real-game copies not checked")
            return []
        with open(p, encoding="utf-8") as f:
            return [s.strip("\n") for s in re.split(r"\n={5,}\n", f.read()) if s.strip()]

    def samples_check(self):
        items = self.load_samples()
        self.n_samples = len(items)
        wmods = {}
        for m in self.rx["types"]["waystone"]["mods"]:
            for i, ln in enumerate(m["lines"]):
                wmods[line_key(ln)] = (m, i)
        tipl = {t["implicit"].lower(): w for w, t in self.tablet_types.items()}
        for n, text in enumerate(items, 1):
            lines = text.splitlines()
            cls = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Item Class:")), "")
            where = f"sample {n} ({cls})"
            tb = mods.TABLET_BASE.search(next((l for l in lines[2:6] if "Tablet" in l), ""))
            wb = re.search(r"Waystone \(Tier \d+\)", text)
            base = tb.group(1) if tb and cls.startswith("Tablet") else (wb.group(0) if wb else None)
            if base is None:
                self.bad(f"{where}: no tablet / waystone base found")
                continue
            if base not in self.names:
                self.bad(f"{where}: base '{base}' is not in gamedata.json")
            rarity = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Rarity:")), "")
            if rarity == "Unique":
                nm = lines[2].strip()
                if nm not in self.gd["uniques"]:
                    self.bad(f"{where}: unique '{nm}' is not in gamedata.json uniques")
            word = base.rsplit(" ", 1)[0] if cls.startswith("Tablet") else None
            kind = None
            for i, l in enumerate(lines):
                if l.startswith("{"):
                    kind = "implicit" if "Implicit" in l else "unique" if "Unique" in l else "prefix" if "Prefix" in l \
                        else "suffix" if "Suffix" in l else "other"
                    continue
                if l.startswith("--------"):
                    kind = None
                    continue
                if not kind or kind in ("unique", "other") or not l.strip():
                    continue
                if kind == "implicit":
                    if re.match(r"^\d+ uses? remaining$", l.strip()):
                        continue
                    if word and tipl.get(l.strip().lower()) != word:
                        self.bad(f"{where}: implicit '{l.strip()}' is not {word}'s implicit in the data")
                    continue
                k = line_key(l)
                nums = re.findall(r"(-?\d+(?:\.\d+)?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)", l)
                if word:
                    e = self.tablet_pool.get(k)
                    if not e:
                        self.bad(f"{where}: mod line '{l.strip()}' matches no tablet mod row")
                        continue
                    if word not in e["types"]:
                        self.bad(f"{where}: '{l.strip()}' is on a {word} Tablet but the data says it rolls on {sorted(e['types'])}")
                    if kind.capitalize() not in e["sides"]:
                        self.bad(f"{where}: '{l.strip()}' is a {kind} on the copy but {sorted(e['sides'])} in the data")
                    pr = e["pairs"].get(word) or []
                    for (v, a, b), (lo, hi) in zip(nums, pr):
                        if not (lo <= float(a) and float(b) <= hi and lo <= float(v) <= hi):
                            self.bad(f"{where}: '{l.strip()}' roll range {a}-{b} is outside the row's {rng(lo, hi)}")
                else:
                    hit = wmods.get(k)
                    if not hit:
                        self.bad(f"{where}: mod line '{l.strip()}' matches no waystone mod row")
                        continue
                    m, idx = hit
                    if m["side"] != kind:
                        self.bad(f"{where}: '{l.strip()}' is a {kind} on the copy but {m['side']} in the data")
                    if len(m["lines"]) == 1:
                        for v, a, b in nums:
                            if not (m["min"] <= float(a) and float(b) <= m["max"]):
                                self.bad(f"{where}: '{l.strip()}' roll range {a}-{b} is outside the row's "
                                         f"{rng(m['min'], m['max'])}")

    # ---------------------------------------------------------------- finish
    def finish(self):
        ids = collections.Counter(r["id"] for r in self.rows)
        for i, n in ids.items():
            if n > 1:
                self.bad(f"row id '{i}' is used {n} times")
        for r in self.rows:
            for f in ("id", "name", "group", "class", "text", "source", "version"):
                if not r.get(f):
                    self.bad(f"row {r.get('id')}: empty {f}")
            if BLACKLIST.search(" ".join(str(r.get(f, "")) for f in ("source", "text", "tags"))):
                self.bad(f"row {r['id']}: source is on the blacklist (game8 / fextralife are AI-written and wrong)")
            if r["group"] not in GROUPS:
                self.bad(f"row {r['id']}: unknown group {r['group']}")
        for h in self.hide:
            if h not in ids:
                self.warn.append(f"gamedb_hide.json: id '{h}' matches no row")
        self.all_rows = list(self.rows)
        self.rows = [r for r in self.rows if r["id"] not in self.hide]

    def output(self):
        return {"version": SCHEMA, "game_version": self.current,
                "source": "RePoE exports (modlists.json, regexdata.json, mapdata.json), gamedata.json, searchdata.json and "
                          "the app's own names; tools/build_gamedb.py",
                "order": list(GROUPS), "nolink": list(GROUPS), "rows": self.rows}


def dumps(out):
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"


# ---------------------------------------------------------------- samples from the test build's data folder
def refresh_samples(folder, dest):
    """Only the tablet / waystone item text from session.json (records' "raw") and unpriced_items.txt."""
    texts = []
    p = os.path.join(folder, "session.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            for r in json.load(f).get("records", []):
                raw = r.get("raw") or ""
                texts.append("\n".join(raw) if isinstance(raw, list) else raw)
    p = os.path.join(folder, "unpriced_items.txt")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            for chunk in re.split(r"^===== .*$", f.read(), flags=re.M):
                texts.append(chunk)
    out, seen = [], set()
    for t in texts:
        t = t.strip("\n")
        if re.match(r"Item Class: (Tablets?|Waystones?)\b", t) and t not in seen:
            seen.add(t)
            out.append(t)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n=====\n".join(out) + "\n")
    return len(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    ap.add_argument("--samples")
    ap.add_argument("--trade-dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--root", default=ROOT, help="the folder with the data files (tests use a copy)")
    ap.add_argument("--refresh-samples", metavar="DIR")
    a = ap.parse_args(argv)
    if a.refresh_samples:
        n = refresh_samples(a.refresh_samples, a.samples or os.path.join(a.root, SAMPLES))
        print(f"{n} tablet / waystone copies saved to {a.samples or SAMPLES}")
    a.out = a.out or os.path.join(a.root, "gamedb.json")
    b = Build(root=a.root, samples=a.samples, trade_dir=a.trade_dir).run()
    for w in b.warn:
        print("warning:", w)
    for n in b.notes:
        print("note:", n)
    if b.fail:
        print(f"\n{len(b.fail)} check(s) failed - gamedb.json NOT written:")
        for f in b.fail:
            print("  FAIL", f)
        return 1
    out = dumps(b.output())
    counts = collections.Counter(r["group"] for r in b.rows)
    if a.check:
        try:
            with open(a.out, encoding="utf-8") as f:
                same = f.read() == out
        except OSError:
            same = False
        if not same:
            print("FAIL gamedb.json is missing or out of date - run: py tools/build_gamedb.py")
            return 1
        print(f"gamedb.json ok: {len(b.rows)} rows ({b.n_samples} real-game copies checked)")
        return 0
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"gamedb.json: {len(b.rows)} rows, {b.n_samples} real-game copies checked"
          + (f", {len(b.all_rows) - len(b.rows)} hidden" if len(b.all_rows) != len(b.rows) else ""))
    for g in GROUPS:
        print(f"  {g}: {counts.get(g, 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
