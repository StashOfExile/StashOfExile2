"""3.3.0 owner: every unique in the game with its mods, for Mod Lab (uniquedata.json, built by tools/build_uniquedata.py
from Path of Building Community's PoE2 data, MIT license, see THIRD_PARTY_NOTICES.txt). The item data belongs to
Grinding Gear Games. Nothing is looked up while the app runs.

  get(name)  -> {"base", "kind", "group", "implicit": [...], "explicit": [...], "corruption": [...]} or None
               "corruption": the enchantments a Vaal Orb can give its base, from RePoE's export
  names()    -> every unique the file has
  GROUP_ORDER - the groups Mod Lab folds them under, in its order"""
import json
import os
import re
import threading

FILE = "uniquedata.json"
GROUP_ORDER = ("Amulets", "Rings", "Belts", "Body Armours", "Helmets", "Gloves", "Boots", "Shields", "Foci", "Quivers",
               "Axes", "Bows", "Claws", "Crossbows", "Daggers", "Flails", "Maces", "Sceptres", "Spears", "Staves",
               "Swords", "Talismans", "Wands", "Jewels", "Flasks and Charms", "Soul Cores", "Tablets", "Relics")
OTHER = "Other uniques"
CORRUPT_MARK = "Corrupted: "        # a corruption enchantment's row in Mod Lab starts with this
RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
_lock = threading.Lock()
_data = None


def _find():
    from .config import APP_DIR, RESOURCE_DIR, P
    for p in (P(FILE), os.path.join(RESOURCE_DIR, FILE), os.path.join(APP_DIR, FILE)):
        if os.path.isfile(p):
            return p
    return None


def load():
    global _data
    with _lock:
        if _data is None:
            try:
                with open(_find(), encoding="utf-8") as f:
                    d = json.load(f)
                _data = d.get("uniques") if isinstance(d, dict) and isinstance(d.get("uniques"), dict) else {}
            except (OSError, TypeError, ValueError):
                _data = {}
        return _data


def reset(data=None):
    """Tests: start from this."""
    global _data
    _data = data


def names():
    return list(load())


def get(name):
    if not name:
        return None
    d = load()
    u = d.get(name)
    if u is None:
        low = str(name).strip().lower()
        u = next((v for k, v in d.items() if k.lower() == low), None)
    return u if isinstance(u, dict) else None


def group_of(name):
    u = get(name)
    g = (u or {}).get("group")
    if g in GROUP_ORDER:
        return g
    return _group_from_base(name) or OTHER


def _group_from_base(name):
    """3.3.0 owner: a unique Path of Building doesn't list, a unique tablet, by its base in the game data."""
    try:
        from . import gamedata
        from .gearbook import base_cat
        bases = (gamedata.load().get("uniques") or {}).get(name) or []
        cat = base_cat(bases[0]) if bases else None
    except Exception:
        return None
    if not cat:
        return None
    simple = {"tablet": "Tablets", "relic": "Relics", "jewel": "Jewels"}
    if cat in simple:
        return simple[cat]
    word = cat.split(":", 1)[-1].replace("_", " ").title()
    for g in GROUP_ORDER:
        if g.lower().rstrip("s") == word.lower() or g.lower() == word.lower() + "s":
            return g
    return None


def as_rolled(text):
    """A line with ranges as one roll could be: "+(30-40) to maximum Life" -> "+30 to maximum Life". The rule key is
    the same as the key of the line copied off a real item."""
    return RANGE.sub(lambda m: m.group(1), str(text))
