"""2.99.0: the Mod book's Gear rules and Unique rules - the data side (the page is gearbook_page.py).

  * Gear rules: every prefix / suffix that can roll on an item class, from tierdata.json (RePoE - the same file as
    the Desecration Helper), one row per line (a two-line mod is two rows). Rules are "gear:<class>:<wording>", the
    wording without numbers or a leading "+", so a rule set here and one set from a price check (Rate ▾) are one.
  * Unique rules: "unique:<name>:<wording>". 3.3.0 owner: every unique's lines come from uniquedata.json (Path of
    Building's data, soe2/uniquedata.py), plus any line your price checks saw that it lacks (unique_mods.json, on
    this PC only: item wording, nothing about you). A line with a choice (Mageblood's "Legacy of ...") brings
    every option the trade site lists for it.
GGG ToS: your own settings and the app's own data; nothing touches the game, nothing extra is fetched."""
from . import buglog
from .config import load_json, save_json
from .mods import norm

FILE = "unique_mods.json"
SKIP_CLASSES = ("jewel", "relic", "tablet", "waystone")       # (their own tabs)
_CACHE = {}


def gkey(text):
    """A line's wording for a gear / unique rule: numbers as #, lower case, no leading "+" (the game data has none)."""
    return " ".join(norm(text).replace("+", " ").split())


def gear_key(cls, text):
    return f"gear:{cls}:{gkey(text)}"


def unique_key(name, text):
    return f"unique:{str(name).strip().lower()}:{gkey(text)}"


def _ws():
    from . import wellsouls as W
    return W


def classes():
    """[(class key, name)] - every gear class the game data has mods for ("belt", "Belts"), in the game's order."""
    if "classes" in _CACHE:
        return _CACHE["classes"]
    from . import gamedata
    have = {b["c"] for b in _ws().data().get("bases") or []}
    out = [(k, v.get("name") or k) for k, v in (gamedata.load().get("classes") or {}).items()
           if k not in SKIP_CLASSES and (v.get("ee2") or "") in have]
    _CACHE["classes"] = out
    return out


def class_name(cls):
    return dict(classes()).get(cls, cls)


def class_mods(cls):
    """[{"key", "text", "kind", "tiers"}] - every line that can roll on this class (any of its bases), sorted."""
    ck = ("mods", cls)
    if ck in _CACHE:
        return _CACHE[ck]
    from . import gamedata
    W = _ws()
    ee2 = ((gamedata.load().get("classes") or {}).get(cls) or {}).get("ee2")
    tagsets = [set(b["t"]) for b in W.data().get("bases") or [] if b["c"] == ee2]
    rows, seen = [], set()
    for tpl, entries in (W.data().get("mods") or {}).items():
        fit = [e for e in entries if any(W.weight(e["s"], t) > 0 for t in tagsets)]
        if not fit:
            continue
        kind = "Prefix" if all(e.get("k") == "p" for e in fit) else "Suffix" if all(e.get("k") == "s" for e in fit) \
            else "Either"
        tiers = max(sum(1 for e in fit if e["g"] == g) for g in {e["g"] for e in fit})
        for line in tpl.split(" / "):
            k = gear_key(cls, line)
            if k in seen:
                continue
            seen.add(k)
            rows.append({"key": k, "text": line[:1].upper() + line[1:], "kind": kind, "tiers": tiers})
    rows.sort(key=lambda r: r["text"].lower())
    _CACHE[ck] = rows
    return rows


# ---------------------------------------------------------------- uniques
def unique_names():
    from . import gamedata
    return sorted((gamedata.load().get("uniques") or {}), key=str.lower)


def unique_bases(name):
    from . import gamedata
    return list((gamedata.load().get("uniques") or {}).get(name) or [])


def store():
    if "u" not in _CACHE:
        d = load_json(FILE, {})
        _CACHE["u"] = d if isinstance(d, dict) else {}
    return _CACHE["u"]


def learn(item):
    """A priced unique -> its lines remembered for Unique rules. -> True when something new was saved."""
    if not item or not item.get("gear") or item.get("rarity") != "Unique":
        return False
    name = str(item.get("name") or "").strip()
    if not name:
        return False
    d = store().setdefault(name, {"base": item.get("base") or "", "lines": {}})
    new = False
    for m in item.get("mods") or []:
        if m.get("kind") in ("Total", "Rune") or m.get("group") in ("total", "pseudo") or not m.get("text"):
            continue
        k = unique_key(name, m["text"])
        if k in d["lines"]:
            continue
        shown = (m.get("shown") or m["text"]).split("  (")[0]
        d["lines"][k] = {"text": shown, "kind": m.get("kind") or "", "sid": m.get("sid") if m.get("option") is not None
                         else None}
        new = True
    if new:
        save_json(FILE, store())
    return new


SMALL = {"of", "to", "the", "a", "an", "and", "or", "per", "in", "on", "for", "with", "you", "your"}


def nice(text):
    """An option's wording as the game writes it: "legacy of amethyst" -> "Legacy of Amethyst"."""
    out = []
    for i, w in enumerate(str(text).split()):
        out.append(w if (i and w in SMALL) or not w[:1].isalpha() else w[:1].upper() + w[1:])
    return " ".join(out)


def options_of(sid):
    """Every wording the trade site (or the game data) lists for a stat with a choice: ["legacy of gold", ...]."""
    from .mods import DUPS, OPTS
    out = []
    for i in DUPS.get(sid, [sid]):
        out += [w for w in (OPTS.get(i) or {}) if w not in out]
    try:
        from . import gamedata
        for st in gamedata.load().get("stats") or []:
            if sid in [i for ids in st["trade"].values() for i in ids]:
                for mt in st.get("matchers") or []:
                    w = norm(mt.get("string", ""))
                    if mt.get("value") is not None and w and w not in out:
                        out.append(w)
    except Exception:
        buglog.caught()
    return out


def unique_rows(name):
    """[{"key", "text", "kind", "option"}] - a unique's lines from the game data, the ones you've priced that it
    lacks, and every option of a choice line."""
    from . import uniquedata as UD
    d = next((v for k, v in store().items() if k.lower() == str(name).lower()), None) or {}
    rows, seen = [], set()
    u = UD.get(name) or {}
    for kind, lines in (("Implicit", u.get("implicit") or []), ("Explicit", u.get("explicit") or []),
                        ("Corruption", u.get("corruption") or [])):
        for text in lines:
            k = unique_key(name, UD.as_rolled(text))
            if k not in seen:
                seen.add(k)
                # 3.3.0 owner: a Vaal Orb's enchantment says so on its row; its rule key is the line's own
                rows.append({"key": k, "text": f"{UD.CORRUPT_MARK}{text}" if kind == "Corruption" else text,
                             "kind": kind, "option": False})
    for k, v in (d.get("lines") or {}).items():
        if k not in seen:
            seen.add(k)
            rows.append({"key": k, "text": v.get("text") or k.split(":", 2)[-1], "kind": v.get("kind") or "",
                         "option": bool(v.get("sid"))})
        if v.get("sid"):
            for w in options_of(v["sid"]):
                ok = unique_key(name, w)
                if ok not in seen:
                    seen.add(ok)
                    rows.append({"key": ok, "text": nice(w), "kind": v.get("kind") or "",
                                 "option": True})
    if u:                                                 # the game data's order: implicits, then the item's own lines
        order = {r["key"]: i for i, r in enumerate(rows)}
        rank = {"Implicit": 0, "Corruption": 2}
        rows.sort(key=lambda r: (rank.get(r["kind"], 1), order[r["key"]]))
    else:
        rows.sort(key=lambda r: (not r["option"], r["text"].lower()))
    return rows


def all_uniques():
    """Every unique Mod Lab lists: the game data's, and any you price checked that it does not have."""
    from . import uniquedata as UD
    out = {n.lower(): n for n in UD.names()}
    for n in store():
        out.setdefault(n.lower(), n)
    return sorted(out.values(), key=str.lower)


def migrate_plus(rules, tiers):
    """2.99.0, once: gear rules saved with a "+" ("gear:helmet:+# to maximum life") -> without it. -> changed?"""
    changed = False
    for book in (rules, tiers):
        for k in [k for k in book if k.startswith("gear:") and "+" in k]:
            head, _, text = k.partition(":")[2].partition(":")
            nk = f"gear:{head}:{gkey(text)}"
            book.setdefault(nk, book[k])
            del book[k]
            changed = True
    return changed


def base_cat(base):
    """A learned row's base -> "tablet" / "jewel" / "waystone" / "relic" / "gear:<class>" / None."""
    b = str(base or "")
    if b.endswith("Tablet") or b == "Tablet":
        return "tablet"
    from .mods import JEWEL_NAMES
    if b in JEWEL_NAMES:
        return "jewel"
    if b.lower().startswith("waystone"):
        return "waystone"
    from . import gamedata
    e = (gamedata.load().get("bases") or {}).get(b) or {}
    c = e.get("class")
    if c == "relic":
        return "relic"
    if c == "waystone":
        return "waystone"
    if c == "jewel":
        return "jewel"
    return f"gear:{c}" if c else None
