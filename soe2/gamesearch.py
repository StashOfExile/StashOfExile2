"""Game search (2.0 beta 10): every skill, support, unique, base, currency, rune, modifier and keyword in one search.

Data: searchdata.json (8,500+ entries from the RePoE export of Path of Exile 2's game files; tools/build_searchdata.py).
Search rules (same as the PoE2 Keyword Search page): every word must match; -word excludes; "exact phrase" for
phrases. Ranking: exact name, then name starts with it, then name contains it, then tags, then text."""
import json
import os
import re

from . import buglog, gamesearch_clean
from .config import APP_DIR, P

try:
    from .config import RESOURCE_DIR
except ImportError:                 # older config
    RESOURCE_DIR = APP_DIR

_DATA = {"rows": None}


JEWELS = "Jewels"


def load():
    if _DATA["rows"] is not None:
        return _DATA
    path = next((p for p in (P("searchdata.json"), os.path.join(RESOURCE_DIR, "searchdata.json"),
                             os.path.join(APP_DIR, "searchdata.json")) if os.path.isfile(p)), None)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        rows = []
        for n, g, c, k, t in d["rows"]:
            rows.append({"n": n, "g": g, "c": c, "k": k, "t": t, "ln": n.lower(), "lk": (k or "").lower(),
                         "lt": (t or "").lower()})
        order = list(d.get("order") or [])
        # 3.0.6 (owner): jewels get their own category, right after the rings and belts one
        for r in rows:
            if r["c"] == "Jewel" and r["g"] == "Jewellery & Belts":  # game text
                r["g"] = JEWELS
        if any(r["g"] == JEWELS for r in rows) and JEWELS not in order:
            at = order.index("Jewellery & Belts") + 1 if "Jewellery & Belts" in order else len(order)  # game text
            order.insert(at, JEWELS)
        rows += anoint_rows()
        _unique_lines(rows)                              # 3.3.0 owner: a unique's mods, so its effects can be searched
        db_rows, db_order = gamedb_rows()
        rows += db_rows
        rows = gamesearch_clean.clean_rows(rows, hidden_names())      # no developer-only entries, no placeholder text
        for g in reversed(db_order):                       # the new categories follow Endgame Items, in the file's order
            if g not in order:
                order.insert(order.index("Endgame Items") + 1 if "Endgame Items" in order else len(order), g)
        if any(r["g"] == ANOINTS for r in rows) and ANOINTS not in order:
            order.insert(order.index("Modifiers") if "Modifiers" in order else len(order), ANOINTS)
        _DATA.update(rows=rows, order=order, nolink=set(d.get("nolink") or []) | set(db_order),
                     version=d.get("version", "?"), error=None)
    except Exception as e:
        _DATA.update(rows=[], order=[], nolink=set(), version="?",
                     error=f"searchdata.json {'not found' if not path else 'could not be read'} ({e})")
    return _DATA


ANOINTS = "Anoints"


def _find(name):
    return next((p for p in (P(name), os.path.join(RESOURCE_DIR, name), os.path.join(APP_DIR, name))
                 if os.path.isfile(p)), None)


def anoint_rows():
    """2.17.0: Game search > Anoints - every notable an amulet can be instilled with, and the three Liquid Emotions it
    takes (anointdata.json, tools/build_anointdata.py). Searching an emotion's name finds every anoint that uses it."""
    path = _find("anointdata.json")
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        names = d["emotions"]
        out = []
        for n, rec, stats in d["rows"]:
            em = [names.get(r, r) for r in rec]
            k = ", ".join(dict.fromkeys(em)) + " · anoint, instil, amulet"
            out.append({"n": n, "g": ANOINTS, "c": "Anoint (amulet)", "k": k, "t": stats, "a": em, "ln": n.lower(),
                        "lk": k.lower(), "lt": (stats or "").lower()})
        return out
    except Exception:
        return []


def gamedb_rows():
    """3.0.6: the offline game database (gamedb.json, tools/build_gamedb.py): tablets, waystones, Atlas masters, Vaal
    Temple, pinnacles and areas, Trial of the Sekhemas, Ritual altars, leagues - facts from the game's own files only.
    A row listed in gamedb_hide.json ([{"id": ..., "reason": ...}] or {"name": ..., "group": ..., "reason": ...}) is left out, so a wrong row is removed by adding
    its id there, with no rebuild. -> (rows, the categories in order)"""
    path = _find("gamedb.json")
    if not path:
        return [], []
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        hide = hidden_ids()
        out = []
        for r in d["rows"]:
            if r["id"] in hide:
                continue
            t, k = r["text"], r.get("tags") or ""
            out.append({"n": r["name"], "g": r["group"], "c": r["class"], "k": k, "t": t, "ln": r["name"].lower(),
                        "lk": k.lower(), "lt": t.lower(), "db": True, "id": r["id"], "src": r["source"],
                        "v": r["version"], "props": r.get("props") or [], "lines": r.get("lines") or []})
        return out, list(d.get("order") or [])
    except Exception:
        buglog.caught()
        return [], []


def _hide_entries():
    path = _find("gamedb_hide.json")
    if not path:
        return []
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        return [e for e in d if isinstance(e, dict)]
    except Exception:
        buglog.caught()
        return []


def _unique_lines(rows):
    """Each unique row gets its lines from uniquedata.json (soe2/uniquedata.py): shown on its card and searched."""
    try:
        from . import uniquedata as UD
        for r in rows:
            if r.get("g") != "Unique Items":
                continue
            u = UD.get(r.get("n"))
            if not u:
                continue
            lines = list(u.get("implicit") or []) + list(u.get("explicit") or [])
            r["ul"] = lines
            r["lt"] = (r.get("lt") or "") + " " + " ".join(lines).lower()
    except Exception:
        buglog.caught()


def report_ref(row):
    """3.3.0 owner: what a data report names a Game Search row by: its id, or its group and name."""
    return row["id"] if row.get("db") and row.get("id") else f"{row.get('g', '')}|{row.get('n', '')}"


def _board_hidden():
    from . import datareports as DR
    try:
        return DR.hidden("search")
    except Exception:
        buglog.caught()
        return set()


def hidden_ids():
    """gamedb_hide.json ids, and 3.3.0: rows an admin hid from a data report."""
    return {e["id"] for e in _hide_entries() if e.get("id")} | {r for r in _board_hidden() if "|" not in r}


def hidden_names():
    """gamedb_hide.json entries with a "name" (and optionally a "group") hide a Game Search row that has no id; and
    3.3.0: rows an admin hid from a data report, by group and name."""
    out = gamesearch_clean.hide_names(_hide_entries())
    for r in _board_hidden():
        if "|" in r:
            g, n = r.split("|", 1)
            out.add((n, g))
    return out


def forget():
    """The rows are read again next time: an admin hid a row."""
    _DATA.clear()
    _DATA["rows"] = None


def emotion_counts(em):
    """['Liquid Envy', 'Diluted Liquid Guilt', 'Liquid Envy'] -> [('Liquid Envy', 2), ('Diluted Liquid Guilt', 1)]"""
    out = {}
    for e in em:
        out[e] = out.get(e, 0) + 1
    return list(out.items())


def parse(text):
    """'fire -cold "added damage"' -> (['fire', 'added damage'], ['cold'])"""
    terms, neg = [], []
    for m in re.finditer(r'(-?)"([^"]+)"|(-?)(\S+)', text or ""):
        is_neg = (m.group(1) or m.group(3)) == "-"
        w = (m.group(2) or m.group(4) or "").lower()
        if not w or w == "-":
            continue
        (neg if is_neg else terms).append(w)
    return terms, neg


def search(text):
    """-> [row] best first (all rows when nothing is typed)."""
    d = load()
    terms, neg = parse(text)
    order = d["order"]
    if not terms and not neg:
        return list(d["rows"])
    out = []
    for it in d["rows"]:
        hay = it["ln"] + " " + it["lk"] + " " + it["lt"]
        score, ok = 0, True
        for t in terms:
            if t not in hay:
                ok = False
                break
            if it["ln"] == t:
                score += 100
            elif it["ln"].startswith(t):
                score += 60
            elif t in it["ln"]:
                score += 40
            elif t in it["lk"]:
                score += 10
            else:
                score += 1
        if not ok or any(n in hay for n in neg):
            continue
        out.append((-score, order.index(it["g"]) if it["g"] in order else 99, it["n"], it))
    out.sort(key=lambda x: x[:3])
    return [x[3] for x in out]


def inspector_query(it):
    """What to show in Under the hood for this entry (a base or a mod the price checker knows), or None.
    (2.0 beta 12: replaces the web links - everything stays inside the app.)"""
    from . import gamedata
    try:
        if it["g"] == "Modifiers":
            text = (it["t"] or "").split(" | ")[0]
            one = re.sub(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)", r"\1", text)      # "(5-8)" -> "5"
            e, _neg = gamedata.stat_for(one, learn=False)
            if e:
                return re.sub(r"\s+", " ", re.sub(r"[+\-]?\(?-?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?\))?", " ", text)).strip()
        elif gamedata.base(it["n"]) is not None:
            return it["n"]
    except Exception:
        buglog.caught()
    return None
