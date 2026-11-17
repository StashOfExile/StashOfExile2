"""Game search (2.0 beta 10): every skill, support, unique, base, currency, rune, modifier and keyword in one search.

Data: searchdata.json (8,500+ entries from the RePoE export of Path of Exile 2's game files; tools/build_searchdata.py).
Search rules (same as the PoE2 Keyword Search page): every word must match; -word excludes; "exact phrase" for
phrases. Ranking: exact name, then name starts with it, then name contains it, then tags, then text."""
import json
import os
import re

from . import buglog
from .config import APP_DIR, P

try:
    from .config import RESOURCE_DIR
except ImportError:                 # older config
    RESOURCE_DIR = APP_DIR

_DATA = {"rows": None}


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
        rows += anoint_rows()
        db_rows, db_order = gamedb_rows()
        rows += db_rows
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
    A row listed in gamedb_hide.json ([{"id": ..., "reason": ...}]) is left out, so a wrong row is removed by adding
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


def hidden_ids():
    path = _find("gamedb_hide.json")
    if not path:
        return set()
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        return {e["id"] for e in d if isinstance(e, dict) and e.get("id")}
    except Exception:
        buglog.caught()
        return set()


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
