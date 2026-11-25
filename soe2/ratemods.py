"""2.96.0: Help rate mods - your ratings tune your own price checks at once, and (with Community data sharing on) they
are your vote in the community's ratings. (2.119.0: no rep - it was removed in 2.118.0.)

  * ▲ / ▼ beside each mod on Price Checks: "did this mod matter for the price?" ▲ = High, ▼ = Ignore, again = clear.
    Gear has its own rules per item class ("gear:helmet:# to maximum life"), so a helmet's ▲ doesn't touch rings.
  * Rate mods: one mod at a time, S / A / B / C / D or F (ignore), from one rule set (Tablets, Jewels, Waystones, Relics,
    or a gear class you've price checked). S / A count as High, B / C / D as Normal (the tier says what's left out first).
  * The ask: once, after you've priced enough items; Not now asks again once, at random 3-7 days later; No thanks
    never asks again. Rate Mods is always there (2.120.0: its own page; owner: Mods › Rate Mods).
  * By roll (owner, MIX B): a mod that rolls in tiers (gear) has three groups of rolls - Top / Middle / Low (the
    best ~25% of tiers, the next ~40%, the rest) - each with its own letter; "Same for every roll" (the default) is
    the mod's one letter for all three. The edges are saved as VALUES per rule key (roll_groups.json, yours only -
    never shared), so a patch's new tiers don't move them. A price check gives a roll its group's letter: F is left
    out the way a low tier is (gear.LOW_TIER: not searched, a note, tick it to search on it); the others order what
    is left out first (mods.drop_rank).
  (2.96.0's Bulk Pricing floor, "Skip cheap items", was removed in 2.125.5.)
GGG ToS: your own settings and the app's own data; nothing touches the game, nothing extra is fetched."""
import random
import re
import statistics
import time

from . import buglog
from .config import SETTINGS, load_json, save_json
from .mods import (RULES, TIER_ORDER, TIERS, auto_impact, impact_key, norm, rule_key)

ASK_AFTER = 25                      # items priced before the first ask
SNOOZE_DAYS = (3, 7)
ROLL_BY_FILE = "roll_groups.json"   # rule key -> {"edges": [top's lowest, middle's lowest], "by": [3 letters]}
ROLL_BY = load_json(ROLL_BY_FILE, {})                   # (yours only - never shared)
if not isinstance(ROLL_BY, dict):
    ROLL_BY = {}
GRADE_WORD = {"S": "High", "A": "High", "B": "Normal", "C": "Normal", "D": "Normal", "ignore": "Ignore"}
MEANING = {"High": "price hangs on it", "Normal": "adds a little", "Ignore": "buyers don't care"}


def set_of(rec):
    """The rule set an item's mods belong to: tablet / jewel / waystone / relic / gear:<class>, or None."""
    it = rec.get("item") or {}
    if it.get("waystone"):
        return "waystone"
    cls = str(it.get("class") or "")
    if cls.lower().startswith("relic"):
        return "relic"
    if it.get("gear") and it.get("rarity") == "Unique" and it.get("name"):     # 2.99.0: a unique has its own rules
        return "unique:" + str(it["name"]).strip().lower()
    if it.get("gear"):
        return "gear:" + str(it.get("gclass") or cls or "gear").lower()
    base = str(it.get("base") or "")
    return "tablet" if cls in ("Tablet", "Tablets") or base.endswith(" Tablet") else "jewel"


def key_for(rec, m):
    """The rule Rate ▾ on this mod sets, or None (totals, pseudo totals and lines with no trade id can't be rated)."""
    if m.get("kind") in ("Total", "Rune") or m.get("group") in ("total", "pseudo") or not m.get("text"):
        return None                     # (2.97.1: a socketed rune isn't rated - it shares an affix's wording)
    s = set_of(rec)
    k = norm(m["text"])
    if s is None:
        return None
    if s.startswith(("gear:", "unique:")):            # 2.99.0: no leading "+" (the Mod book's Gear / Unique rules)
        from .gearbook import gkey
        return f"{s}:{gkey(m['text'])}"
    return rule_key(s, k)


def thumb(key):
    """"up" (you rated it High), "down" (Ignore) or None - your own rule only, not the built-in default."""
    v = RULES.get(key)
    return "up" if v == "high" else "down" if v == "ignore" else None


def apply(keys, grade):
    """Rate these rule keys: S..D (S / A = High, B / C / D = Normal, with that tier), "ignore", "up", "down", or None
    (clear yours). -> the keys changed."""
    keys = [k for k in keys if k]
    for k in keys:
        if grade in (None, "clear"):
            RULES.pop(k, None)
            TIERS.pop(k, None)
            continue
        imp = {"up": "high", "down": "ignore", "ignore": "ignore"}.get(grade) or ("high" if grade in ("S", "A") else "normal")
        if imp == auto_impact(k) and grade not in TIER_ORDER + ("ignore",):   # 2.97.0: an F you gave stays yours
            RULES.pop(k, None)
        else:
            RULES[k] = imp
        if grade in TIER_ORDER:
            TIERS[k] = grade
        elif imp == "ignore":
            TIERS.pop(k, None)
    save_json("mod_rules.json", RULES)
    save_json("mod_tiers.json", TIERS)
    rated = SETTINGS.setdefault("rated_n", 0)
    SETTINGS["rated_n"] = rated + len(keys)
    save_json("settings.json", SETTINGS)
    return keys


def not_price():
    """3.3.0 owner: mods you marked Doesn't affect price - on the item but nothing to do with its price."""
    from .config import SETTINGS
    v = SETTINGS.get("rm_not_price")
    return set(v) if isinstance(v, list) else set()


def mark_not_price(keys, on=True):
    from .config import SETTINGS, save_json
    have = not_price()
    have = have | set(keys) if on else have - set(keys)
    SETTINGS["rm_not_price"] = sorted(have)
    save_json("settings.json", SETTINGS)


def fixed_line(set_name, text):
    """3.3.0 owner: a unique's line with no number - on every copy, so it never moves the price."""
    return set_name.startswith("unique:") and "#" not in str(text or "") and not any(c.isdigit() for c in str(text))


def queue(set_name, gear_mods=None):
    """Mods to rate in one set, the ones you haven't rated first: [(keys, text)]. 3.3.0: without a unique's fixed
    lines and the mods you marked Doesn't affect price."""
    out = []
    if set_name.startswith(("gear:", "unique:")):
        seen = set()
        for k, text in gear_mods or []:
            if k not in seen and not fixed_line(set_name, text):
                seen.add(k)
                out.append(([k], text))
    else:
        from . import regex as R
        for m in R.mods(set_name):
            lines = m.get("lines") or [m["line"]]
            keys = [rule_key(set_name, norm(line)) for line in lines]
            out.append((keys, " / ".join(line[:1].upper() + line[1:] for line in lines)))
    gone = not_price()
    out = [x for x in out if not any(k in gone for k in x[0])]
    mine = lambda keys: any(k in RULES or k in TIERS for k in keys)      # noqa: E731
    return [x for x in out if not mine(x[0])] + [x for x in out if mine(x[0])]


def current(keys):
    """Your grade for these keys: S..D, "ignore", or None."""
    k = keys[0]
    if impact_key(k) == "ignore" and k in RULES:
        return "ignore"
    t = TIERS.get(k)
    return t if t in TIER_ORDER else None


def note_rated(n, today=None):
    """Count mods rated today (SETTINGS "rated_day": [date, n]; saved with the ratings)."""
    today = today or time.strftime("%Y-%m-%d")
    d = SETTINGS.get("rated_day")
    cur = d[1] if isinstance(d, list) and len(d) == 2 and d[0] == today else 0
    SETTINGS["rated_day"] = [today, int(cur) + int(n)]
    return SETTINGS["rated_day"][1]


def rated_today(today=None):
    today = today or time.strftime("%Y-%m-%d")
    d = SETTINGS.get("rated_day")
    return int(d[1]) if isinstance(d, list) and len(d) == 2 and d[0] == today else 0


def grade_text(g):
    """"A · High", "F · Ignore" - your letter and what it counts as (a word, never the color alone)."""
    if g is None:
        return "– not yet"
    return f"{'F' if g == 'ignore' else g} · {GRADE_WORD.get(g, '')}"


# ---------------------------------------------------------------- the sets, grouped (owner: Map Items, Jewels, Gear)
MAP_SETS = (("tablet", "Tablets"), ("waystone", "Waystones"), ("relic", "Relics"))
JEWEL_SET = ("jewel", "Jewels")
GEAR_KINDS = (("armour", "Armour"), ("weapon", "Weapons"), ("jewelry", "Jewelry"))   # (US spelling: the app's rule)


def gear_kind(cls):
    """A gear class -> "armour" / "weapon" / "jewelry" (Quivers sit with Armour, as in the mockup)."""
    if cls == "quiver":
        return "armour"
    from . import gamedata
    k = ((gamedata.load().get("classes") or {}).get(cls) or {}).get("kind")
    return {"jewellery": "jewelry"}.get(k, k if k in ("armour", "weapon") else "weapon")   # game text


def set_label(set_name):
    for s, lab in MAP_SETS + (JEWEL_SET,):
        if s == set_name:
            return lab
    if set_name.startswith("gear:"):
        from . import gearbook as GB
        return GB.class_name(set_name[5:])
    if set_name.startswith("unique:"):
        from . import gearbook as GB
        return next((n for n in GB.all_uniques() if n.lower() == set_name[7:]), set_name[7:].title())
    return set_name


def _range(lo, hi):
    return f"{lo:g}" if lo == hi else f"({lo:g}–{hi:g})"


# ---------------------------------------------------------------- each mod as the game words it
_DATA = {}
_BRACKET = re.compile(r"\((-?\d+(?:\.\d+)?)\s*[—–-]\s*(-?\d+(?:\.\d+)?)\)")


def _modlines():
    """modlists.json (tablets and jewels) -> normalized wording -> the game's line with every type's ranges merged:
    "(2–3) additional Rare Monsters are spawned from Abysses in Map"."""
    if "lines" in _DATA:
        return _DATA["lines"]
    import json
    from .config import P
    out = {}
    try:
        with open(P("modlists.json"), encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        data = {}
    for part in ("tablets", "jewels"):
        for secs in (data.get(part) or {}).values():
            for lines in (secs or {}).values():
                for line in lines or []:
                    if not isinstance(line, str):
                        continue
                    k = norm(_BRACKET.sub("#", line.strip()))
                    rs = [(float(a), float(b)) for a, b in _BRACKET.findall(line)]
                    have = out.get(k)
                    if have is None:
                        out[k] = [_BRACKET.sub("{}", line.strip()), rs]
                    elif len(have[1]) == len(rs):
                        have[1] = [(min(a, c), max(b, d)) for (a, b), (c, d) in zip(have[1], rs)]
    _DATA["lines"] = out
    return out


def _fill(tpl, ranges):
    try:
        return tpl.format(*[_range(lo, hi) for lo, hi in ranges])
    except (IndexError, KeyError, ValueError):
        return tpl.replace("{}", "#")


def _cap(text):
    return text[:1].upper() + text[1:]


def _ref_case(text):
    """The trade stat's own capitals for a wording ("#% to fire resistance" -> "#% to Fire Resistance"), or None."""
    try:
        from . import gamedata
        from .gearbook import gkey
        e, _neg = gamedata.stat_for(text, learn=False)
        if e and gkey(e.get("ref") or "") == gkey(text):
            return e["ref"].lstrip("+")
    except Exception:
        buglog.caught()
    return None


def _tagsets(cls):
    """The tag sets of a gear class's bases (tierdata.json, as the Desecration Helper reads it)."""
    ck = ("tags", cls)
    if ck not in _DATA:
        from . import gamedata
        from . import wellsouls as W
        ee2 = ((gamedata.load().get("classes") or {}).get(cls) or {}).get("ee2")
        seen = {}
        for b in W.data().get("bases") or []:
            if b["c"] == ee2 and "heart_unique_jewel_prefix" not in b["t"]:
                seen.setdefault(tuple(sorted(b["t"])), set(b["t"]))
        _DATA[ck] = list(seen.values())
    return _DATA[ck]


def _tier_class(set_name):
    """The class whose tiers a set's mods roll in: "gloves" for gear:gloves, "jewel" for Jewels, else None."""
    if set_name.startswith("gear:"):
        return set_name[5:]
    return "jewel" if set_name == "jewel" else None


def _mod_text(key):
    """A rule key's wording ("gear:<class>:<wording>", "waystone:<wording>" -> the wording)."""
    if key.startswith(("gear:", "unique:")):
        return key.split(":", 2)[-1]
    if key.startswith(("waystone:", "relic:")):
        return key.split(":", 1)[-1]
    return key


def _entries(set_name, key):
    """The tierdata entries of this mod's main tier group on the set's class, best (highest level) first."""
    cls = _tier_class(set_name)
    if not cls:
        return []
    ck = ("ent", cls, key)
    if ck in _DATA:
        return _DATA[ck]
    from . import wellsouls as W
    tpl = W.template(_mod_text(key))
    tags = _tagsets(cls)
    fit = [e for e in W.data().get("mods", {}).get(tpl) or []
           if not e.get("a") and not e.get("h") and e.get("r") and any(W.weight(e["s"], t) > 0 for t in tags)]
    groups = {}
    for e in fit:
        groups.setdefault(e["g"], []).append(e)
    es = sorted(max(groups.values(), key=len), key=lambda e: -e["l"]) if groups else []
    _DATA[ck] = es
    return es


def ladder(set_name, key):
    """[(tier, lowest, highest)] best first - this mod's tiers on the set (a gear class or Jewels), when it has one
    number and two tiers or more; else None (every roll is searched, no question asked)."""
    es = _entries(set_name, key)
    if len(es) < 2 or any(len(e["r"]) != 1 or e["r"][0][0] < 0 for e in es):
        return None
    return [(i + 1, e["r"][0][0], e["r"][0][1]) for i, e in enumerate(es)]


def rolls_on(set_name, key, info=None):
    """The chips after "Rolls on:" - tablet types, jewel kinds, waystone tiers, relic sizes, or the gear classes it
    rolls on. info: the regex list's entry, when the set has one."""
    if set_name == "waystone":                       # 3.3.0 owner: one chip, tiers in order - All tiers or Tier 11-16
        g = waystone_group((info or {}).get("tags"))
        return ["All tiers" if g == "All waystones" else g]
    if set_name in ("relic", "tablet", "jewel"):     # 3.3.0 owner: the bases it spawns on, by name
        return bases_of(set_name, _mod_text(key), (info or {}).get("tags"))
    if set_name.startswith("gear:"):
        ck = ("on", key)
        if ck not in _DATA:
            from . import gearbook as GB
            from . import wellsouls as W
            tpl = W.template(_mod_text(key))
            es = [e for e in W.data().get("mods", {}).get(tpl) or [] if not e.get("a") and not e.get("h")]
            _DATA[ck] = [n for c, n in GB.classes() if any(W.weight(e["s"], t) > 0 for e in es for t in _tagsets(c))]
        return list(_DATA[ck])
    return []


def game_text(set_name, keys, text, info=None):
    """A mod in the game's words with its range: "(2–3) additional Rare Monsters are spawned from Abysses in Map",
    "+(6–45)% to Fire Resistance". From the data's ranges where it has them, else the best wording there is."""
    out = []
    lines = _modlines()
    parts = text.split(" / ") if len(keys) > 1 and text.count(" / ") == len(keys) - 1 else [text] * len(keys)
    for k, part in zip(keys, parts):
        plain = _mod_text(k) if set_name.startswith("gear:") else norm(part)
        if set_name in ("tablet", "jewel") and plain in lines:
            tpl, rs = lines[plain]
            out.append(_fill(tpl, rs))
            continue
        word = _ref_case(plain) or (part if set_name.startswith("unique:") else _cap(plain))
        if set_name.startswith("unique:"):
            out.append(word)
            continue
        es = _entries(set_name, k)
        n = word.count("#")
        sign = "+" if set_name.startswith("gear:") and re.match(r"#%? to ", word) else ""   # (as the game shows it)
        if es and all(len(e["r"]) == n for e in es) and n:
            rs = [(min(e["r"][i][0] for e in es), max(e["r"][i][1] for e in es)) for i in range(n)]
            out.append(sign + _fill(word.replace("#", "{}"), rs))
        elif info and n == 1 and info.get("min") is not None and info.get("max") is not None and len(keys) == 1:
            out.append(word.replace("#", _range(float(info["min"]), float(info["max"])), 1))
        else:
            out.append(sign + _cap(word))
    return " / ".join(out)


KIND_WORDS = {"prefix": "Prefix", "suffix": "Suffix", "either": "Prefix or Suffix", "implicit": "Implicit",
              "explicit": "Explicit", "corruption": "Corrupted", "enchant": "Enchant", "rune": "Rune",
              "desecrated": "Desecrated", "fractured": "Fractured", "crafted": "Crafted", "unique": "Unique"}
_KIND_CACHE = {}


def mod_kind(set_name, keys, info=None):
    """3.3.0 owner: what kind of mod a row is, as a word: Prefix, Suffix, Implicit, Explicit, Corrupted, Enchant ...
    or "" when the data does not say."""
    if info and info.get("side"):
        return KIND_WORDS.get(str(info["side"]).lower(), str(info["side"]).title())
    key = keys[0] if keys else ""
    if set_name.startswith(("gear:", "unique:")):
        if set_name not in _KIND_CACHE:
            from . import gearbook as GB
            rows = GB.class_mods(set_name[5:]) if set_name.startswith("gear:") else \
                GB.unique_rows(next((n for n in GB.all_uniques() if n.lower() == set_name[7:]), set_name[7:]))
            _KIND_CACHE[set_name] = {r["key"]: r.get("kind") or "" for r in rows}
        k = _KIND_CACHE[set_name].get(key, "")
        return KIND_WORDS.get(str(k).lower(), str(k).title()) if k else ""
    return ""


def kinds_forget():
    """The kinds are worked out again: new lines were learned."""
    _KIND_CACHE.clear()


def entries(set_name, gear_mods=None):
    """Every mod of a set as the page shows it: [{"keys", "text", "game", "rolls"}], in the queue's order."""
    infos = {}
    if not set_name.startswith(("gear:", "unique:")):
        from . import regex as R
        for m in R.mods(set_name):
            lines = m.get("lines") or [m["line"]]
            infos[tuple(rule_key(set_name, norm(line)) for line in lines)] = m
    out = []
    for keys, text in queue(set_name, gear_mods):
        info = infos.get(tuple(keys))
        cats = bases_of(set_name, text, (info or {}).get("tags"))
        out.append({"keys": keys, "text": text, "game": game_text(set_name, keys, text, info),
                    "rolls": cats if set_name in ("tablet", "jewel", "relic") else rolls_on(set_name, keys[0], info),
                    "info": info, "set": set_name, "cats": cats, "kind": mod_kind(set_name, keys, info),
                    "cat": "" if cats or set_name == "waystone" else category(set_name, (info or {}).get("tags"))})
    return out


# ---------------------------------------------------------------- By roll (owner, MIX B): three groups of rolls
ROLL_GROUPS = ("Top rolls", "Middle rolls", "Low rolls")
GROUP_SHORT = ("top", "middle", "low")
TOP_SHARE, MID_SHARE = 0.25, 0.40      # the default edges: the best ~25% of tiers, the next ~40%, the rest


def default_edges(lad):
    """[top's lowest value, middle's lowest value] for a ladder (best first): Top = the best ~25% of tiers, Middle =
    the next ~40%, Low = the rest - at least one tier each. None when it has fewer than three tiers."""
    n = len(lad or ())
    if n < 3:
        return None
    top = min(max(1, round(n * TOP_SHARE)), n - 2)
    mid = min(max(1, round(n * MID_SHARE)), n - 1 - top)
    return [lad[top - 1][1], lad[top + mid - 1][1]]


def _counts(lad, edges):
    """(tiers in Top, tiers in Middle) for saved edges (values): the tiers whose lowest roll reaches each edge - at
    least one tier each, after a patch too."""
    n = len(lad)
    top = sum(1 for _t, lo, _hi in lad if lo >= edges[0])
    top = min(max(1, top), n - 2)
    upto = sum(1 for _t, lo, _hi in lad if lo >= edges[1])
    mid = min(max(1, upto - top), n - 1 - top)
    return top, mid


def roll_groups(set_name, key):
    """The three groups of a mod that rolls in tiers on this set: [{"name", "tiers": [(t, lo, hi)], "grade"}] - grade
    None follows the mod's own letter. None when the mod has no tiers here (fewer than three)."""
    lad = ladder(set_name, key)
    edges = default_edges(lad)
    if not edges:
        return None
    mine = ROLL_BY.get(key) or {}
    if isinstance(mine.get("edges"), list) and len(mine["edges"]) == 2:
        edges = [float(x) for x in mine["edges"]]
    top, mid = _counts(lad, edges)
    by = (list(mine.get("by") or []) + [None] * 3)[:3]
    cuts = (lad[:top], lad[top:top + mid], lad[top + mid:])
    return [{"name": ROLL_GROUPS[i], "tiers": cuts[i], "grade": by[i] if by[i] in TIER_ORDER + ("ignore",) else None}
            for i in range(3)]


def group_range(g, key):
    """"T1–T2 · 36–45%" - a group's tiers and values."""
    ts = g["tiers"]
    unit = "%" if "#%" in _mod_text(key) else ""
    t = f"T{ts[0][0]}" if len(ts) == 1 else f"T{ts[0][0]}–T{ts[-1][0]}"
    lo, hi = min(x[1] for x in ts), max(x[2] for x in ts)
    return f"{t} · {lo:g}–{hi:g}{unit}" if lo != hi else f"{t} · {lo:g}{unit}"


def same_for_every_roll(key):
    by = (ROLL_BY.get(key) or {}).get("by") or []
    return not any(g for g in by)


def set_group_grade(key, i, grade, mod_grade=None):
    """One group's own letter (None: the mod's letter). All three back to the mod's letter -> "Same for every
    roll" again (the saved letters go; the edges stay)."""
    d = ROLL_BY.setdefault(key, {})
    by = (list(d.get("by") or []) + [None] * 3)[:3]
    by[i] = grade
    if mod_grade is not None:
        by = [None if b == mod_grade else b for b in by]
    d["by"] = by if any(by) else None
    _save_by(key)
    return by


def follow(key, grade):
    """The mod's letter changed: a group with that letter follows the mod again. -> True when something changed."""
    d = ROLL_BY.get(key)
    by = (d or {}).get("by")
    if not by or grade not in TIER_ORDER + ("ignore",):
        return False
    new = [None if b == grade else b for b in by]
    if new == list(by):
        return False
    d["by"] = new if any(new) else None
    _save_by(key)
    return True


def same_again(key):
    """Same for every roll: the groups follow the mod's letter again."""
    d = ROLL_BY.get(key)
    if d:
        d["by"] = None
        _save_by(key)


def _save_by(key):
    d = ROLL_BY.get(key)
    if d is not None:
        for k in ("by", "edges"):
            if not d.get(k):
                d.pop(k, None)
        if not d:
            ROLL_BY.pop(key, None)
    save_json(ROLL_BY_FILE, ROLL_BY)


def by_roll_text(set_name, key, mod_grade):
    """The Table's By roll: "same", or the three letters ("S · B · F")."""
    groups = roll_groups(set_name, key) if key else None
    if not groups:
        return "–"
    if all(g["grade"] is None for g in groups):
        return "same"
    return " · ".join(_short_letter(g["grade"] or mod_grade) for g in groups)


def _short_letter(g):
    return "–" if g is None else "F" if g == "ignore" else g


def roll_group_of(set_name, key, value):
    """(group index, group) a value falls in, or (None, None)."""
    groups = roll_groups(set_name, key)
    if not groups or not isinstance(value, (int, float)):
        return None, None
    for i, g in enumerate(groups[:2]):
        if value >= min(x[1] for x in g["tiers"]):
            return i, g
    return 2, groups[2]


def apply_roll(m):
    """A price check's mod that rolls in tiers (m["roll_key"]): the letter of its roll's group, when the groups
    differ (m["roll_grade"] - drop_rank orders by it, trade.mod_impact searches by it). F: not searched by default,
    the low-tier way (a note, tick it to search on it). Again after a change: back to how it was first. -> the letter,
    or None (the mod's own letter decides, as before)."""
    key = m.get("roll_key")
    if not key:
        return None
    if "roll_base" in m:
        m["auto"], m["note"] = m.pop("roll_base")
    m.pop("roll_grade", None)
    v = m.get("value")
    if m.get("covered") or not isinstance(v, (int, float)) or v < 0 or same_for_every_roll(key):
        return None                          # (a mod counted in a total is searched in the total)
    i, g = roll_group_of(key_set(key), key, v)
    if g is None or g["grade"] is None:
        return None
    m["roll_grade"] = g["grade"]
    m["roll_base"] = [m.get("auto"), m.get("note")]
    word = GROUP_SHORT[i]
    if g["grade"] == "ignore":
        m.update(auto="ignore", note=f"{word} roll for this mod in Mod Lab - not searched - tick it to search on it")
    elif m.get("auto") == "ignore" and m.get("low_tier"):
        m.update(auto=None, note=f"{word} roll for this mod in Mod Lab: {g['grade']} - searched")
    return g["grade"]


def key_set(key):
    """The set a By roll rule key belongs to: gear:<class> (Jewels have no tiers in the data)."""
    return "gear:" + key.split(":", 2)[1] if key.startswith("gear:") and key.count(":") >= 2 else "jewel"


# ---------------------------------------------------------------- what the app already knows: listings, players
_SEEN = {"t": 0.0, "lg": None, "idx": {}, "cat": {}}
SEEN_EVERY = 120                      # seconds a look at the stored listings is kept


def _cat_of(base):
    c = _SEEN["cat"]
    if base not in c:
        try:
            from .gearbook import base_cat
            c[base] = base_cat(base)
        except Exception:
            c[base] = None
    return c[base]


def seen_index(market=None, now=None):
    """(set, stat id) -> {listing id: asking price in divine}, from the listings your price checks fetched this
    league (the Mod Book's and the gear pool's). Kept for SEEN_EVERY seconds."""
    now = time.time() if now is None else now
    if market is None:
        from .market import MARKET as market
    lg = market.cur()
    if _SEEN["lg"] == lg and now - _SEEN["t"] < SEEN_EVERY:
        return _SEEN["idx"]
    import json
    idx = {}
    rows = []
    if market.db is not None:
        try:
            with market.lock:
                rows = market.db.execute("SELECT id, base, price_div, sids FROM listings WHERE league=? AND price_div "
                                         "IS NOT NULL ORDER BY seen DESC LIMIT 30000", (lg,)).fetchall()
                rows += market.db.execute("SELECT id, base, price_div, sids FROM pool WHERE league=? AND price_div IS "
                                          "NOT NULL ORDER BY seen DESC LIMIT 30000", (lg,)).fetchall()
        except Exception:
            buglog.caught()
    for lid, base, price, sids in rows:
        cat = _cat_of(base)
        if not cat:
            continue
        try:
            for sid in json.loads(sids or "[]"):
                idx.setdefault((cat, sid), {})[lid] = float(price)
        except (TypeError, ValueError):
            continue
    _SEEN.update(t=now, lg=lg, idx=idx)
    return idx


def sids_for(key):
    """The trade stat ids a rule key's wording is listed under."""
    from .mods import DUPS, sid_for_line
    text = _mod_text(key)
    out = set()
    for t in (text, "+" + text):
        s = sid_for_line(t)
        if s:
            out.add(s)
            out |= set(DUPS.get(s, ()))
    try:
        from . import gamedata
        from .gearbook import gkey
        e, _neg = gamedata.stat_for(text, learn=False)
        if e and gkey(e.get("ref") or "") == gkey(text):
            out |= set((e.get("trade") or {}).get("explicit") or [])
    except Exception:
        buglog.caught()
    return out


def seen(set_name, keys, idx=None):
    """(middle asking price in divine, listings) for items of this set with this mod, or None (none seen yet)."""
    cat = set_name if not set_name.startswith("unique:") else None
    if cat is None:
        return None
    idx = seen_index() if idx is None else idx
    got = {}
    for k in keys:
        for sid in sids_for(k):
            got.update(idx.get((cat, sid)) or {})
    if not got:
        return None
    return statistics.median(got.values()), len(got)


def seen_tip(set_name, s):
    if not s:
        return "No listings seen yet: none of your price checks this league fetched one with this mod."
    med, n = s
    return (f"The middle of the {n} asking prices seen for {set_label(set_name)} with this mod, in divine - half "
            f"asked more, half less. From the listings your price checks fetched this league.")


def div_text(v):
    return f"{v:.1f}" if v < 10 else f"{v:.0f}"


VOTE_MIN = 2            # the board lists a mod's votes once it has this many (board/src/index.js modRatings)


def players(keys):
    """(the answer most players picked, votes, (High, Normal, Ignore)) from the community board's ratings, or None
    (fewer than VOTE_MIN votes, or none downloaded yet). The board collects High / Normal / Ignore only - each
    install's Mod Book rule for the mod. Letter votes (S A B C D F) would need the Worker to store the letter
    (board/src/index.js: mod_votes.value and modRatings) - until then no letter counts are shown."""
    ck = "ratings"
    try:
        from . import communitymods as CM
        d = CM.cached()
        ts = d.get("ts")
        if ck not in _DATA or _DATA[ck][0] != ts:
            rows = {}
            for row in d.get("ratings", []) or []:
                try:
                    k, h, nm, ig = row
                    rows[k] = (int(h or 0), int(nm or 0), int(ig or 0))
                except (TypeError, ValueError):
                    continue
            _DATA[ck] = (ts, rows)
        rows = _DATA[ck][1]
    except Exception:
        buglog.caught()
        return None
    hit = next((rows[k] for k in keys if k in rows), None)
    if not hit or sum(hit) < VOTE_MIN:
        return None
    word = ("High", "Normal", "Ignore")[max(range(3), key=lambda i: hit[i])]
    return word, sum(hit), hit


def votes_synced():
    """Has the app downloaded the players' votes at least once? (the hourly community sync)"""
    try:
        from . import communitymods as CM
        return bool(CM.cached().get("ts"))
    except Exception:
        return False


def players_text(p):
    """"High 9 · Normal 3 · Ignore 1", or "not enough votes" (or "–" before the first download)."""
    if not p:
        return "not enough votes" if votes_synced() else "–"
    h, nm, ig = p[2]
    return f"High {h} · Normal {nm} · Ignore {ig}"


def players_tip(p):
    if not p:
        if not votes_synced():
            return ("The players' votes come with the community sync (once an hour) - none downloaded yet. Reading "
                    "them works with Community data sharing off too.")
        return (f"Players' votes show once a mod has at least {VOTE_MIN}. This one has fewer. With Community data "
                "sharing on, your rating is a vote.")
    _w, n, (h, nm, ig) = p
    return (f"{n} installs voted: {h} High, {nm} Normal, {ig} Ignore - each one's own rating for this mod (S and A "
            "count as High, B C D as Normal, F as Ignore), sent with Community data sharing. One vote per install.")


DIAMOND = "Diamond"
RELIC_SIZES = ("Large", "Medium", "Small")
RELIC_ART = {"Large": "Vase Relic", "Medium": "Amphora Relic", "Small": "Urn Relic"}
# 3.3.0 owner: Mod Lab's groups are the bases, each with every mod that can spawn on it - never a mix like
# "Emerald / Ruby". A mod is in each base it rolls on.
RELIC_BASES = {"Small": ("Urn Relic", "Seal Relic"), "Medium": ("Amphora Relic", "Tapestry Relic"),
               "Large": ("Vase Relic", "Coffer Relic", "Incense Relic")}
JEWEL_COLORS = ("Ruby", "Emerald", "Sapphire")


def _base_lines():
    """{"tablets"/"jewels": {base: {wording}}} from modlists.json, worded as _modlines() keys them."""
    if "bases" in _DATA:
        return _DATA["bases"]
    import json
    from .config import P
    try:
        with open(P("modlists.json"), encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        data = {}
    out = {}
    for part in ("tablets", "jewels"):
        out[part] = {}
        for base, secs in (data.get(part) or {}).items():
            out[part][base] = {norm(_BRACKET.sub("#", ln.strip())) for lines in (secs or {}).values()
                               for ln in lines or [] if isinstance(ln, str)}
    _DATA["bases"] = out
    return out


def base_order(set_name):
    """The bases of a set, in the game's order: the groups Mod Lab shows."""
    if set_name == "tablet":
        return list(_base_lines().get("tablets") or {})
    if set_name == "jewel":
        return list(_base_lines().get("jewels") or {})
    if set_name == "relic":
        return [b for z in RELIC_SIZES for b in RELIC_BASES[z]]
    return []


def bases_of(set_name, text, tags=None):
    """The bases a mod can spawn on. From modlists.json's own lists; for a jewel line worded differently there, from
    its tags: a color rolls on that jewel and on a Diamond, Time-Lost on the Time-Lost ones."""
    tags = list(tags or [])
    if set_name == "relic":
        return [b for z in RELIC_SIZES if z in tags or not tags for b in RELIC_BASES[z]]
    if set_name not in ("tablet", "jewel"):
        return []
    parts = [norm(p) for p in str(text).split(" / ")]
    lines = _base_lines().get("tablets" if set_name == "tablet" else "jewels") or {}
    got = [b for b, have in lines.items() if all(p in have for p in parts)]
    if set_name == "tablet" or not tags:
        return got
    cols = [c for c in JEWEL_COLORS if c in tags] or list(JEWEL_COLORS)
    out = list(got)                                  # the Time-Lost ones word a mod "in Radius": the tag says it
    if "Time-Lost" not in tags:
        out += cols + [DIAMOND]
    if "Time-Lost" in tags:
        out += [f"Time-Lost {c}" for c in cols] + ["Time-Lost Diamond"]
    order = base_order("jewel")
    return [b for b in order if b in out]


def waystone_group(tags):
    """("T11-15", "T16") -> "Tier 11-16"; every tier, or "Any" -> "All waystones"."""
    import re as _re
    spans = []
    for t in tags or []:
        m = _re.match(r"T(\d+)(?:-(\d+))?$", str(t))
        if m:
            spans.append((int(m.group(1)), int(m.group(2) or m.group(1))))
    if not spans or "Any" in (tags or []):
        return "All waystones"
    spans.sort()
    lo, hi = spans[0]
    joined = True
    for a, b in spans[1:]:
        joined &= a <= hi + 1
        hi = max(hi, b)
    if joined and lo <= 1 and hi >= 16:
        return "All waystones"
    if joined:
        return f"Tier {lo}-{hi}" if lo != hi else f"Tier {lo}"
    return "Tier " + ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in spans)


def on_diamond(e):
    """A Diamond, made from a Ruby, an Emerald and a Sapphire at the reforging bench, rolls every mod of the three."""
    return any(t in ("Ruby", "Emerald", "Sapphire") for t in ((e.get("info") or {}).get("tags") or []))


def category(set_name, tags):
    """The Table's group for a mod: its tablet type ("All tablets" for the shared ones), jewel type, waystone tiers or
    relic size."""
    tags = list(tags or [])
    if set_name == "tablet":
        return "All tablets" if "Any" in tags or len(tags) != 1 else tags[0]
    if set_name == "jewel":
        kinds = [t for t in tags if t != "Time-Lost"]
        return " / ".join(kinds) if kinds else ("Time-Lost" if tags else "All jewels")
    if set_name == "waystone":                       # 3.3.0 owner: tiers in order, every tier is All waystones
        return waystone_group(tags)
    if set_name == "relic":                          # 3.3.0 owner: the sizes it rolls on, said in words
        sizes = [z for z in RELIC_SIZES if z in tags]
        return (" and ".join(sizes) + " Relics") if sizes and len(sizes) < len(RELIC_SIZES) else "All relics"
    return set_label(set_name)


# ---------------------------------------------------------------- the ask
def ask_state():
    return SETTINGS.setdefault("rate_ask", {"state": "new", "at": 0})


def should_ask(priced):
    """Ask now? (new and enough items priced, or a snooze that's over and hasn't asked again yet)."""
    a = ask_state()
    if a.get("state") == "new":
        return priced >= ASK_AFTER
    if a.get("state") == "snoozed":
        return time.time() >= a.get("at", 0)
    return False


def answer(what, rng=random):
    """"yes" / "not_now" / "no". Not now once: again at random 3-7 days later; not now again, or no: never."""
    a = ask_state()
    if what == "not_now" and a.get("state") == "new":
        a.update(state="snoozed", at=time.time() + rng.uniform(*SNOOZE_DAYS) * 86400)
    elif what == "yes":
        a.update(state="yes", at=0)
    else:
        a.update(state="never", at=0)
    save_json("settings.json", SETTINGS)
    return a["state"]
