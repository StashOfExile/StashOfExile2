"""Who am I (3.3.0, owner): one answer for the whole app to "which character is this?".

The game's log never says which character you logged in as, and a party member's level-up, death or reward line looks
just like yours. What the log does say: "X has joined the area" and "X has left the area" are written for OTHER
players only, never for you. So:

  1. a name the log shows joining or leaving an area is not you;
  2. a level-up, death or reward line from any other name is you - the current character becomes that name;
  3. The Riverbank (where every new character starts) begins a blank run with no name; rule 2 names it;
  4. a name typed in Overlay › Options wins over all of it;
  5. Not my character (the YOU list) puts a name on the not-you list - a friend whose areas you always join never
     shows a join line.

State: "known" (the log named you since you last came through the character screen, or you picked or typed the
name), "assumed" (back from the character screen, nothing yet: the last one), "unknown" (nobody yet).

No questions are ever asked.

Privacy (owner, 2026-11-23): no other player's name is ever saved. The game's own Client.txt is the list - its last
part is read at each start and the names are held in memory only, gone when the app closes. Not my character is the
one thing kept about someone else, as a salted one-way hash that can't be turned back into a name. Only your own
characters' names, classes and levels are in your settings, as before."""
import hashlib
import os
import re
import time

from . import buglog
from .config import SETTINGS, save_json

OTHERS = set()                     # lower-case names seen joining or leaving your area: memory only, never saved
RIVERBANK = "G1_1"                 # the first zone of act 1: a level 1 area only a new character is made in
EVIDENCE = ("level", "death", "gain")
_JOIN = re.compile(rb"\] : (.+?) has (?:joined|left) the area\.")


def cfg():
    d = SETTINGS.get("identity")
    if not isinstance(d, dict):
        d = SETTINGS["identity"] = {}
    d.pop("others", None)                      # (never saved: see the privacy note above)
    d.setdefault("not_mine", [])               # Not my character: salted hashes, not names
    d.setdefault("mine", {})                   # name -> {"cls", "level", "seen"}
    d.setdefault("current", "")
    d.setdefault("state", "unknown")
    if not d.get("seeded"):                    # once: what the app believed before - minus anyone who joined an area
        d["seeded"] = True
        try:
            st = (SETTINGS.get("focus") or {}).get("state") or {}
            camp = SETTINGS.get("campaign") or {}
            last = st.get("last_char") or camp.get("last_char") or ""
            for name, lvl in list((st.get("levels") or {}).items()) + list((camp.get("char_levels") or {}).items()):
                if name:
                    m = d["mine"].setdefault(name, {"cls": (st.get("classes") or {}).get(name, ""), "level": 0, "seen": 0})
                    m["level"] = max(int(m.get("level") or 0), int(lvl or 0))
            if last:
                d["current"], d["state"] = last, "assumed"
        except Exception:
            buglog.caught()
    return d


def save():
    save_json("settings.json", SETTINGS)


def typed():
    """The name typed in Overlay › Options - it wins over the log."""
    return ((SETTINGS.get("tracker") or {}).get("character") or "").strip()


def _hash(name):
    d = cfg()
    if not d.get("salt"):
        d["salt"] = os.urandom(16).hex()
    return hashlib.sha256((d["salt"] + str(name).strip().lower()).encode("utf-8")).hexdigest()[:24]


def is_other(name):
    low = str(name or "").strip().lower()
    if not low:
        return False
    return low in OTHERS or (bool(cfg()["not_mine"]) and _hash(low) in cfg()["not_mine"])


def is_me(name):
    """Could this name in the log be you? The typed name if there is one, else anyone who never joined an area."""
    n = str(name or "").strip()
    if not n:
        return False
    t = typed()
    return n.lower() == t.lower() if t else not is_other(n)


def current():
    """Your character's name, or "" while nobody is named."""
    return typed() or cfg()["current"]


def state():
    if typed():
        return "known"
    d = cfg()
    return d["state"] if d["current"] else "unknown"


def known():
    return state() == "known"


def characters():
    """Your characters, the one played last first: [(name, class, level)]."""
    d = cfg()
    rows = sorted(d["mine"].items(), key=lambda kv: -float(kv[1].get("seen") or 0))
    return [(n, m.get("cls") or "", int(m.get("level") or 0)) for n, m in rows if not is_other(n)]


def level(name=None):
    m = cfg()["mine"].get(name or current()) or {}
    return int(m.get("level") or 0)


def _other(name):
    """A name joins the not-you set (memory). -> True when that changed what the app believes about YOU: the
    name was one of "your" characters, or the current one."""
    d = cfg()
    low = str(name or "").strip().lower()
    if not low:
        return False
    new = low not in OTHERS
    OTHERS.add(low)
    changed = False
    for k in [k for k in d["mine"] if k.lower() == low]:
        d["mine"].pop(k)
        changed = True
    if d["current"].lower() == low:
        d["current"], d["state"] = "", "unknown"
        changed = True
    if changed:
        save()
    return new


def purge():
    """Names the log has shown joining an area come out of what older versions saved as "your" characters: League
    Plan's levels and classes, the Campaign Helper's levels, the death counter's guess. -> True when any did."""
    hit = False
    try:
        st = (SETTINGS.get("focus") or {}).get("state") or {}
        camp = SETTINGS.get("campaign") or {}
        tr = SETTINGS.get("tracker") or {}
        for box in (st.get("levels"), st.get("classes"), camp.get("char_levels")):
            if isinstance(box, dict):
                for k in [k for k in box if is_other(k)]:
                    box.pop(k)
                    hit = True
        if isinstance(st.get("chars"), list) and any(is_other(k) for k in st["chars"]):
            st["chars"] = [k for k in st["chars"] if not is_other(k)]
            hit = True
        for box, key in ((st, "last_char"), (camp, "last_char"), (tr, "character_guess")):
            if box.get(key) and is_other(box[key]):
                box[key] = ""
                hit = True
        if hit:
            save()
    except Exception:
        buglog.caught()
    return hit


def note(kind, data, ts=None):
    """A game-log event. -> None, or what changed: "other" (a name joined the not-you list), "known" (the log named
    the character you were assumed to be, or the first one), "switch" (it named a different one of yours - data
    ["was"] is set to the one before), "assumed" (back from the character screen), "new" (The Riverbank)."""
    d = cfg()
    data = data if isinstance(data, dict) else {}
    if kind == "party":
        return "other" if _other(data.get("who")) else None
    if kind == "login":                         # through the character screen: it may be another character now
        if d["state"] == "known":
            d["state"] = "assumed"
            return "assumed"
        return None
    if kind == "area" and data.get("area") == RIVERBANK and int(data.get("level") or 0) <= 3 and not typed():
        if d["current"] or d["state"] != "unknown":
            d["current"], d["state"] = "", "unknown"
            save()
            return "new"
        return None
    if kind in EVIDENCE:
        who = str(data.get("who") or "").strip()
        if not who or not is_me(who):
            return None
        m = d["mine"].setdefault(who, {"cls": "", "level": 0, "seen": 0})
        m["seen"] = ts or time.time()
        if kind == "level":
            m["level"], m["cls"] = int(data.get("level") or 0), str(data.get("cls") or m.get("cls") or "")
        was, was_state = d["current"], d["state"]
        d["current"], d["state"] = who, "known"
        if len(d["mine"]) > 60:
            for k in sorted(d["mine"], key=lambda k: float(d["mine"][k].get("seen") or 0))[:-60]:
                d["mine"].pop(k)
        if was.lower() == who.lower():
            if was_state != "known":
                save()
                return "known"
            if kind == "level":
                save()
            return None
        data["was"] = was
        save()
        return "switch" if was else "known"
    return None


def pick(name):
    """You picked your character on the YOU list."""
    d = cfg()
    name = str(name or "").strip()
    if not name or is_other(name):
        return False
    d["mine"].setdefault(name, {"cls": "", "level": 0, "seen": 0})["seen"] = time.time()
    d["current"], d["state"] = name, "known"
    save()
    return True


def not_mine(name):
    """Not my character: the name never counts as you again. Kept as a salted hash, not as a name."""
    low = str(name or "").strip().lower()
    if not low:
        return False
    h = _hash(low)
    d = cfg()
    if h not in d["not_mine"]:
        d["not_mine"].append(h)
        del d["not_mine"][:-500]
    _other(low)
    save()
    return True


def backfill(path, max_bytes=96 * 1024 * 1024):
    """At each start: the names that joined or left your area in the last part of Client.txt - into memory only.
    Only the file is read; nothing about them is saved. -> how many names. Safe on a background thread."""
    if not path or not os.path.exists(path):
        return 0
    found = set()
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            for raw in f:
                if b" the area." not in raw:
                    continue
                m = _JOIN.search(raw)
                if m:
                    found.add(m.group(1).decode("utf-8", "replace").strip())
    except OSError:
        return 0
    for name in found:
        _other(name)
    purge()
    return len(found)
