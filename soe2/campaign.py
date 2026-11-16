"""The Campaign Helper (2.77.0): where you are in the campaign, what's next and what it's worth - from the game's log.

  * It follows you. Entering a zone jumps to that zone's step; steps you went past without entering are "passed".
    It never forces a route: click a step (or ◀ ▶, or their keys) to say "I'm here".
  * Rewards (passive points, spirit, resistances ...): only what the log can prove ticks by itself (a reward's
    "proof" zones). Leaving an act, a reward whose zone you never entered is "Missed"; one whose zone you entered
    asks "Did you get it?" - Got it, Remind me in town, Skip it. A tick you set by hand always wins.
  * Zones the guide doesn't know (a new act) are added to your route in the order you went, with their level, and
    (with Community data sharing on) pooled so the next guide pack has them.
  * Act splits: time in each act (pauses for AFK and long gaps), and your best per league.
  * The game's own dialogue (Campaign Bar): a boss's lines say a fight began and that it is down - the step ticks,
    its reward too when the pack says that line proves it, and the line moves on. Leaving a zone while its boss
    fight was on says so. Rewards the log can't see are asked once, in town (Got it / Not yet).

The guide pack is campaign.json: bundled with the app, and updated from GitHub without an app update ("Check for a
newer one"). Stored in SETTINGS["campaign"]. Reads only Client.txt; nothing is sent to the game."""
import copy
import json
import os
import re
import time

from .config import APP_UA, APP_DIR, RESOURCE_DIR, P, SETTINGS, save_json

FILE = "campaign.json"
SCHEMA = 2                        # 2: interlude keys follow the area ids (P1 = i1), style 2 lines, cues
REPO = "StashOfExile/StashOfExile2"
LIVE_URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE}"
GAP = 15 * 60                     # a longer gap between two log lines isn't counted in a split (away, or closed)
ROUTES = (("full", "Full"), ("speed", "Speedrun"), ("rush", "Rush (carry)"))   # (2.125.3 names; 2.131.0: no 4th)
# 2.125.0 (feedback: "a rush/carry helper ... in the perspective of the person giving the carry"): each route in one line
ROUTE_LINES = {"full": "Every passive point, spirit and resistance, with the side zones that give them.",
               "speed": "The main story. Skips side zones and most extras; keeps the rewards worth the time.",
               "rush": "You're carrying someone: what to clear, when to bring them in, what they pick up and who they "
                       "talk to."}
KIND_NAMES = {"points": "passive points", "spirit": "spirit", "res_cold": "cold res", "res_fire": "fire res",
              "res_lightning": "lightning res", "life": "life", "life_pct": "% life", "mana": "mana", "other": "other"}
SHORT_GIVES = {"points": "+{n} points", "spirit": "+{n} spirit", "res_cold": "+{n}% cold res",
               "res_fire": "+{n}% fire res", "res_lightning": "+{n}% lightning res", "life": "+{n} life",
               "life_pct": "+{n}% life", "mana": "+{n}% mana"}
RES_KINDS = ("res_cold", "res_lightning", "res_fire")
TRIAL_IDS = ("G3_10_Airlock", "G3_10", "G2_13")    # ascendancy trials: the same areas come back in the endgame
ENDGAME_LEVEL = 60                                 # (a trial at this area level or more is an endgame run)
TOWN_ID = re.compile(r"_town$", re.I)
LOW_QUIET = 10 * 60                                # "Too low" pops up at most once in this many seconds
# the pack's reward ids before revision 4 (its interlude keys were the wrong way round: P2 was "i1" ...)
OLD_IDS = {"i1_risu": "i2_risu", "i1_molten": "i2_molten", "i1_pillars": "i2_pillars", "i2_lythara": "i3_lythara",
           "i2_yeti": "i3_yeti", "i3_oswin": "i1_oswin"}
DEFAULTS = {
    "on": True,                   # the feature (Overlay › Options › On the overlay, and the Campaign switch on the bar)
    "line": True,                 # its line on the goal bar (2.97.0: always - on means it shows)
    "vendor": True,               # Vendor search, in town
    "route": "full",              # the default guide (2.89.0: each character's run keeps its own, run["route"])
    "ask_route": True,            # 2.89.0: a new campaign asks which route
    "optional": False,            # show optional zones
    "tips": True,
    "warn": True,                 # rewards the log can't see: asked in town, and missed ones when an act ends
    "popups": True,               # pack 4: boss down / left a fight / too low - short pop-ups over the game
    "splits": True,
    "off_at_maps": True,          # turn itself off once you reach maps
    "chars": {},                  # character -> its run (see char())
    "best": {},                   # league -> {act key: seconds}
    "learned": {},                # act key -> [{zone, after, level}] zones the guide didn't know
    "notes": {},                  # zone (norm) -> your note
    "optional_zones": [],         # zones you marked optional
    "sent": [],                   # learned zones already pooled ("act|zone")
    "pack_checked": 0,
}
CAMP_ID = re.compile(r"^(G|P)(\d+)(?:_|$)")


def cfg():
    c = SETTINGS.setdefault("campaign", {})
    for k, v in DEFAULTS.items():
        if k not in c:                                   # 2.125.4: copied only when missing (it ran on every call)
            c[k] = copy.deepcopy(v)
    if "mine" in c:                                      # 2.131.0: the 4th route is gone - a run on it is on Full
        c.pop("mine", None)
        if c.get("route") not in dict(ROUTES):
            c["route"] = "full"
        for run in (c.get("chars") or {}).values():
            if isinstance(run, dict) and run.get("route") not in (None, *dict(ROUTES)):
                run["route"] = "full"
    if not c.get("ids4"):                                # guide pack 4: the interludes' rewards have new ids
        c["ids4"] = True
        for run in (c.get("chars") or {}).values():
            if not isinstance(run, dict):
                continue
            rw = run.get("rewards") or {}
            for old in [k for k in rw if k in OLD_IDS]:
                rw.setdefault(OLD_IDS[old], rw.pop(old))
            run["ask"] = [OLD_IDS.get(x, x) for x in run.get("ask") or []]
    return c


def save():
    save_json("settings.json", SETTINGS)


def norm(name):
    s = re.sub(r"[^a-z0-9 ]", "", str(name or "").lower()).strip()
    return s[4:] if s.startswith("the ") else s


# ---------------------------------------------------------------- the guide pack
_PACK = {"key": None, "data": None}


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("acts"), list) else None
    except (OSError, ValueError):
        return None


def _newness(d):
    return d.get("schema", 1), d.get("revision", 0)


def pack():
    """-> the newest guide pack (fetched or bundled)."""
    paths = (P(FILE), os.path.join(RESOURCE_DIR, FILE), os.path.join(APP_DIR, FILE))
    key = tuple((p, os.path.getmtime(p)) for p in paths if os.path.isfile(p))
    if _PACK["key"] == key and _PACK["data"] is not None:
        return _PACK["data"]
    best = None
    for p in paths:
        d = _read(p)
        if d and d.get("schema", 1) <= SCHEMA and (best is None or _newness(d) > _newness(best)):
            best = d
    best = best or {"schema": SCHEMA, "revision": 0, "patch": "?", "name": "none", "acts": [], "rewards": [], "vendor": []}
    _PACK.update(key=key, data=best)
    return best


def fetch_live(get=None):
    """Check GitHub for a newer guide pack. -> ("new", name) / ("same", name) / ("error", why)."""
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(LIVE_URL, headers={"User-Agent": APP_UA}, timeout=15)
        if r.status_code != 200:
            return "error", f"GitHub answered {r.status_code}."
        d = r.json()
    except Exception as e:
        return "error", f"Could not reach GitHub ({e.__class__.__name__})."
    cfg()["pack_checked"] = time.time()
    if not isinstance(d, dict) or not isinstance(d.get("acts"), list):
        return "error", "The guide pack on GitHub could not be read."
    if d.get("schema", 1) > SCHEMA:
        return "error", "The newest guide pack needs a newer version of the app - update it."
    if _newness(d) <= _newness(pack()):
        return "same", pack().get("name", "")
    save_json(FILE, d)
    _PACK["key"] = None
    return "new", d.get("name", "")


def acts():
    return pack().get("acts") or []


def act(key):
    return next((a for a in acts() if a.get("key") == key), None)


def act_order(key):
    keys = [a.get("key") for a in acts()]
    return keys.index(key) if key in keys else len(keys)


def act_name(key):
    a = act(key)
    if a:
        return a.get("name", key)
    if str(key).startswith("i"):
        return f"Interlude {key[1:]}"
    return f"Act {key}?"


def act_of_id(area_id):
    """'G2_4_1' -> '2', 'P1_x' -> 'i1', else None."""
    m = CAMP_ID.match(str(area_id or ""))
    if not m:
        return None
    return m.group(2) if m.group(1) == "G" else "i" + m.group(2)


def is_interlude(key):
    return str(key or "").startswith("i")


def find_zone(name, area_id=None):
    """-> (act key, step index) for a zone the guide knows, or (None, None). The area id first (pack 4: a step's
    "ids" - two zones can share a name, and a name in the pack can be spelled wrong), then the name."""
    if area_id:
        for a in acts():
            for i, s in enumerate(a.get("steps") or []):
                if area_id in (s.get("ids") or []) or area_id in (s.get("early_ids") or []):
                    return a.get("key"), i
    n = norm(name)
    for a in acts():
        for i, s in enumerate(a.get("steps") or []):
            if norm(s.get("zone")) == n:
                return a.get("key"), i
    return None, None


def rewards(act_key=None):
    return [r for r in pack().get("rewards") or [] if act_key is None or r.get("act") == act_key]


def short_gives(r):
    f = SHORT_GIVES.get(r.get("kind"))
    return f.format(n=r.get("amount", "")) if f else r.get("gives", "")


# ---------------------------------------------------------------- a character's run
def char(name=None):
    c = cfg()
    name = current_char() if name is None else name
    run = c["chars"].setdefault(name or "", {})
    if not run.get("league"):                             # 2.86.0: a new run - its league (for the leaderboards)
        run["league"] = SETTINGS.get("league") or ""      # (2.124.1: and an older run that had none)
    for k, v in (("act", None), ("zone", None), ("here", None), ("seen", {}), ("levels", {}), ("rewards", {}),
                 ("ask", []), ("secs", {}), ("last_ts", None), ("afk", False), ("done", False), ("zone_level", 0),
                 ("pending", None), ("unknown", None), ("visit", False),
                 # pack 4: the area id you're in, acts whose split is done, rewards asked about in town (and the
                 # ones that had a Not yet), areas whose boss is down, the boss fight going on, a quest's note
                 ("area", None), ("closed", []), ("asked", []), ("not_yet", []), ("killed", []), ("fight", None),
                 ("note", None), ("early", None), ("hub", None), ("warned", [])):
        run.setdefault(k, copy.deepcopy(v))
    return run


def current_char():
    from . import focus as F
    st = F.cfg().get("state") or {}
    return (st.get("last_char") or (SETTINGS.get("tracker") or {}).get("character") or cfg().get("last_char")
            or "")


def char_level():
    """Your level: League Plan's, or the Campaign Helper's own (it reads the level-up lines too - League Plan can be
    off)."""
    from . import focus as F
    st = F.cfg().get("state") or {}
    who = current_char()
    return max(int((st.get("levels") or {}).get(who, 0) or 0), int((cfg().get("char_levels") or {}).get(who, 0) or 0))


def route_of(run=None):
    """2.89.0: this run's guide - the one picked when its campaign started, else the default."""
    run = run or char()
    r = run.get("route") or cfg()["route"]
    return r if r in dict(ROUTES) else "full"


def needs_route(run=None):
    """2.89.0 (feedback): a run in the campaign that hasn't picked its guide yet."""
    c = cfg()
    run = run or char()
    return bool(c["on"] and c["ask_route"] and run.get("act") is not None and not run.get("done")
                and not run.get("route"))


def set_route(route, run=None, remember=False):
    """Pick this run's guide. remember: it's the default and new campaigns stop asking."""
    c = cfg()
    run = run or char()
    run["route"] = route if route in dict(ROUTES) else "full"
    if remember:
        c["route"], c["ask_route"] = run["route"], False
    save()


def speed_reward(r):
    """A reward a speedrun still takes (the pack marks it "speed": true)."""
    return bool(r.get("speed"))


def steps(act_key, run=None, route=None, optional=None):
    """The route for an act -> [{zone, do, side, optional, tip, learned, state}] (state: done / here / passed / todo).
    2.89.0: Speedrun leaves out steps the pack marks "speed": {"skip": true} (and side zones without a Speedrun
    text of their own), and shows a step's
    "speed": {"do": ...} instead of its usual "do". 2.125.0: Rush (carry) the same with "rush" (side zones with a
    rush line stay)."""
    c = cfg()
    run = run or char()
    route = route or route_of(run)
    optional = c["optional"] if optional is None else optional
    a = act(act_key) or {"steps": []}
    rows = [dict(s) for s in a.get("steps") or []]
    known = {norm(s["zone"]) for s in rows}
    for lz in c["learned"].get(act_key) or []:                 # zones the guide didn't know: after the one before
        if norm(lz["zone"]) in known:
            continue
        at = next((i for i, s in enumerate(rows) if norm(s["zone"]) == norm(lz.get("after"))), len(rows) - 1)
        rows.insert(at + 1, {"zone": lz["zone"], "do": "", "learned": True, "level": lz.get("level")})
        known.add(norm(lz["zone"]))
    marked = set(c["optional_zones"])
    for s in rows:
        if norm(s["zone"]) in marked:
            s["optional"] = True
    if route == "speed":                                      # (a side zone stays when the pack wrote it a Speedrun
        rows = [s for s in rows if not (s.get("speed") or {}).get("skip")      # text - Freythorn's +30 spirit)
                and (not s.get("side") or (s.get("speed") or {}).get("do"))]
        for s in rows:
            if (s.get("speed") or {}).get("do"):
                s["do"] = s["speed"]["do"]
    if route == "rush":                                       # 2.125.0: the carrier's guide ("rush" in the pack); a
        def rush(s):                                          # step without one follows Speedrun
            return s.get("rush") or s.get("speed") or {}
        rows = [s for s in rows if not rush(s).get("skip") and (not s.get("side") or (s.get("rush") or {}).get("do"))]
        for s in rows:
            if rush(s).get("do"):
                s["do"] = rush(s)["do"]
    if not optional:
        rows = [s for s in rows if not s.get("optional") or norm(s["zone"]) in _seen(run, act_key)]
    seen = _seen(run, act_key)
    cur = _here_index(run, act_key, rows)
    for i, s in enumerate(rows):
        z = norm(s["zone"])
        s["state"] = "here" if i == cur else ("done" if z in seen and (cur is None or i < cur) else
                                              ("passed" if cur is not None and i < cur else "todo"))
        if z in seen and s["state"] == "todo":
            s["state"] = "done"
        s["note"] = c["notes"].get(z, "")
    return rows


def _seen(run, act_key):
    return [norm(z) for z in (run["seen"].get(act_key) or [])]


def _here_index(run, act_key, rows):
    if run.get("act") != act_key:
        return None
    if run.get("here") is not None:
        return max(0, min(int(run["here"]), len(rows) - 1)) if rows else None
    z, aid = norm(run.get("zone")), run.get("area")
    return next((i for i, s in enumerate(rows) if norm(s["zone"]) == z or (aid and aid in (s.get("ids") or []))),
                None)


def set_here(i, run=None):
    """'I'm here': step i of the current act (a manual pick; the next zone you enter moves it again)."""
    run = run or char()
    if run.get("act") is None:
        return
    rows = steps(run["act"], run)
    if rows:
        run["here"] = max(0, min(int(i), len(rows) - 1))
    save()


def step_by(delta, run=None):
    """◀ / ▶: one step back or on."""
    run = run or char()
    if run.get("act") is None:
        return None
    rows = steps(run["act"], run)
    cur = _here_index(run, run["act"], rows)
    set_here((0 if cur is None else cur) + delta, run)
    return run["here"]


def start_here(act_key, i, run=None):
    """'Start from here' (a character that's partway through): this act, this step; earlier acts count as done."""
    run = run or char()
    run["act"], run["here"] = act_key, int(i)
    rows = steps(act_key, run)
    run["zone"] = rows[int(i)]["zone"] if rows and 0 <= int(i) < len(rows) else None
    save()


# ---------------------------------------------------------------- rewards


def set_reward(rid, state, run=None):
    """A tick by hand (or an answer: got / skip / not_yet / None to clear) - always wins over the log.
    not_yet (pack 4, the town card's Not yet): left open, asked once more at the next town."""
    run = run or char()
    if state == "not_yet":
        run["ask"] = [x for x in run["ask"] if x != rid]
        if run["rewards"].get(rid) in ("missed", "remind"):
            run["rewards"].pop(rid, None)
        if run["asked"].count(rid) < 2 and rid not in run["not_yet"]:
            run["not_yet"].append(rid)
        save()
        return
    if state is None:
        run["rewards"].pop(rid, None)
    else:
        run["rewards"][rid] = state
    if state in ("got", "skip", None):
        run["ask"] = [x for x in run["ask"] if x != rid]
        run["not_yet"] = [x for x in run["not_yet"] if x != rid]
    save()


def totals(run=None):
    """-> {kind: (have, of)} over the whole pack."""
    run = run or char()
    out = {}
    for r in rewards():
        k = r.get("kind", "other")
        have, of = out.get(k, (0, 0))
        n = int(r.get("amount") or 0) if k != "other" else 1
        out[k] = (have + (n if run["rewards"].get(r["id"]) == "got" else 0), of + n)
    return out


def asks(run=None):
    """Rewards waiting for an answer -> [(reward, 'missed' / 'ask' / 'remind')]."""
    run = run or char()
    by = {r["id"]: r for r in rewards()}
    return [(by[x], run["rewards"].get(x) or "ask") for x in run["ask"] if x in by]


def _close_act(run, key, now):
    """An act is over (its last boss is down, a later act began, or maps): its split and the rewards to ask about.
    Once per act (pack 4: an interlude never closes another - they go in any order)."""
    c = cfg()
    if key is None or key in run["closed"]:
        return
    run["closed"].append(key)
    secs = run["secs"].get(key)
    if secs:
        league = SETTINGS.get("league") or ""
        b = c["best"].setdefault(league, {})
        if key not in b or secs < b[key]:
            b[key] = round(secs)
    seen = set(_seen(run, key))
    for r in _route_rewards(run, key):
        st = run["rewards"].get(r["id"])
        if st in ("got", "skip"):
            continue
        if norm(r["zone"]) not in seen:
            run["rewards"][r["id"]] = "missed"
        elif r["id"] in run["asked"]:                       # (already asked in town - its answer stands)
            continue
        if c["warn"] and r["id"] not in run["ask"]:
            run["ask"].append(r["id"])


def _route_rewards(run, key=None):
    """The rewards this run's route takes (2.89.0: Speedrun and Rush leave the ones the pack doesn't mark)."""
    speed = route_of(run) in ("speed", "rush")
    return [r for r in rewards(key) if not speed or speed_reward(r)]


# ---------------------------------------------------------------- events for the overlay (pop-ups)
EVENTS = []


def _event(kind, **kw):
    EVENTS.append(dict(kind=kind, **kw))
    del EVENTS[:-8]


def take_events():
    """-> the pop-ups the log made since the last call (boss down, left before the boss died, too low, act done)."""
    out = list(EVENTS)
    EVENTS.clear()
    return out


# ---------------------------------------------------------------- the game's dialogue (pack 4: "cues")
def cue_norm(text):
    """A dialogue line as the cues compare it: <i>{word} markup -> word, dashes -> '-', spaces, lower case."""
    t = re.sub(r"<[^>]*>\{([^}]*)\}", r"\1", str(text or ""))
    t = t.replace("–", "-").replace("—", "-")
    return " ".join(t.split()).lower()


def find_cue(area_id, who, text):
    """-> (kind, note) when this speaker's line is one of the area's cues, else None. Only the exact speaker and the
    start of the exact line count, in that area only - a player's chat or a boss's voice somewhere else never does."""
    t = cue_norm(text)
    for cue in (pack().get("cues") or {}).get(area_id or "") or []:
        if len(cue) >= 3 and cue[1] == who and t.startswith(cue_norm(cue[2])):
            return cue[0], (cue[3] if len(cue) > 3 else "")
    return None


def _step_of_area(area_id, name=None):
    key, i = find_zone(name, area_id)
    if key is None:
        return None, None
    return key, ((act(key) or {}).get("steps") or [])[i]


def _gain_in(text):
    """'(+30 spirit)' / '(their +2 points)' in a step's text -> '+30 spirit' (the first), or ''."""
    m = re.search(r"\((?:their )?(\+[^)]*)\)", text or "")
    return m.group(1) if m else ""


def _said(run, data, ts):
    """An NPC's line. -> 'zone' when the line changed."""
    aid = (run.get("pending") or {}).get("id") or run.get("area")
    hit = find_cue(aid, data.get("who"), data.get("text"))
    if not hit:
        return None
    kind, note = hit
    key, step = _step_of_area(aid, run.get("zone"))
    if step is None:
        return None
    boss = step.get("boss") or "The boss"
    if kind == "s":
        if aid not in run["killed"]:
            run["fight"] = {"area": aid, "zone": step["zone"], "boss": boss, "act": key}
        return None
    if kind == "q":
        n = 1
        if "{n}" in note:
            got = set((run.get("note") or {}).get("lines") or []) if (run.get("note") or {}).get("area") == aid else set()
            got.add(cue_norm(data.get("text")))
            n = len(got)
            run["note"] = {"area": aid, "text": note.replace("{n}", str(n)), "lines": sorted(got)}
        else:
            run["note"] = {"area": aid, "text": note}
        save()
        return "zone"
    # kind == "d": the boss is down
    run["fight"] = None
    if aid in run["killed"]:
        if note:                                          # (the Hooded One after an island's boss: pieces left)
            run["note"] = {"area": aid, "text": note}
        return None
    run["killed"].append(aid)
    del run["killed"][:-200]
    run["note"] = {"area": aid, "text": note} if note else None
    got = []
    for r in rewards():
        if r.get("cue") == aid or (r.get("cue") and r.get("cue") in (step.get("ids") or [])
                                   and aid in (step.get("ids") or [])):
            if run["rewards"].get(r["id"]) not in ("got", "skip"):
                run["rewards"][r["id"]] = "got"
                run["ask"] = [x for x in run["ask"] if x != r["id"]]
            got.append(short_gives(r))
    nxt = _then_of(run, key, step)
    _event("boss", boss=boss, gives=", ".join(got) or _gain_in(step.get("do")), next=nxt, zone=step["zone"])
    if step.get("last"):
        _tick(run, ts)
        _close_act(run, key, ts)
        _event("act", act=act_name(key), secs=run["secs"].get(key),
               best=cfg()["best"].get(SETTINGS.get("league") or "", {}).get(key))
    save()
    return "zone"


def _then_of(run, key, step):
    """Where to go after this step: its own '→ ...' (a backtrack the order can't know), else the next step."""
    t = _split_to(_route_do(run, step))[1]
    if t:
        return t
    rows = steps(key, run)
    at = next((i for i, s in enumerate(rows) if norm(s["zone"]) == norm(step["zone"])), None)
    nxt = next((s for s in rows[(at + 1 if at is not None else 0):] if s["state"] == "todo"), None)
    return (nxt or {}).get("zone", "")


def _route_do(run, step):
    route = route_of(run)
    if route == "speed" and (step.get("speed") or {}).get("do"):
        return step["speed"]["do"]
    if route == "rush":
        r = step.get("rush") or step.get("speed") or {}
        if r.get("do"):
            return r["do"]
    return step.get("do") or ""


def _split_to(text):
    """'Kill Beira (+10% cold res) → The Grelwood' -> ('Kill Beira (+10% cold res)', 'The Grelwood')."""
    t = str(text or "").rstrip(" .")
    if "→" in t:
        a, b = t.split("→", 1)
        return a.strip(" ;,."), b.strip(" ;,.")
    return t, ""


# ---------------------------------------------------------------- the log
def log_event(kind, ts, data, area_kind=None):
    """A game-log event. -> 'zone' (moved, or the line changed), 'unknown' (a zone the guide doesn't know), 'ask'
    (rewards to answer), 'maps' or None."""
    c = cfg()
    if not c["on"]:
        return None
    run = char()
    out = None
    if kind == "afk":
        _tick(run, ts)
        run["afk"] = bool(data.get("on"))
        return None
    if kind == "level":                                      # (party members level up in the log too: your name, if
        who, lvl = data.get("who") or "", int(data.get("level") or 0)        # set, else the last one)
        mine = ((SETTINGS.get("tracker") or {}).get("character") or "").strip()
        if who and (not mine or mine.lower() == who.lower()):
            lv = c.setdefault("char_levels", {})
            lv[who] = lvl
            if len(lv) > 30:
                lv.pop(next(iter(lv)))
            c["last_char"] = who
            return "zone"
        return None
    if kind == "say":
        if run.get("act") is None or (run.get("done") and not run.get("visit")):
            return None
        return _said(run, data, ts)
    if kind == "area":
        if run["pending"]:                                        # (its scene line never came)
            out = _enter(run, run["pending"]["id"], run["pending"]["id"], run["pending"]["level"], ts)
        run["pending"] = None
        aid = data.get("area", "")
        ak = act_of_id(aid)
        if area_kind == "map":
            run["visit"] = False
            _tick(run, ts)
            run["area"] = aid
            if not run["done"]:
                run["done"] = True
                for key in list(run["seen"]):                     # every act you were in is over (the interludes
                    _close_act(run, key, ts)                      # too - no boss line ends two of them)
                if run.get("act"):
                    _close_act(run, run["act"], ts)
                save()
                return "maps"
            return out
        if ak is None:
            run["visit"] = False                                  # 2.97.0: left the campaign zones
            _tick(run, ts)
            _zone_done(run)                                       # (2.124.0: a hideout ends the zone's time)
            run["away"] = True
            run["last_ts"] = ts                                   # (a hideout: time there isn't the act's)
            run["area"] = aid
            return out
        run["pending"] = {"id": aid, "level": int(data.get("level") or 0), "act": ak}
        return out
    if kind == "scene" and run["pending"]:
        p, run["pending"] = run["pending"], None
        return _enter(run, data.get("name") or p["id"], p["id"], p["level"], ts, p["act"])
    return out


def _tick(run, ts):
    last, run["last_ts"] = run.get("last_ts"), ts
    if last is None or run.get("act") is None or run.get("afk") or run.get("done"):
        return
    dt = ts - last
    if 0 < dt < GAP:
        if run["act"] not in run.get("closed", []):        # (pack 4: an act's split ends with its last boss)
            run["secs"][run["act"]] = run["secs"].get(run["act"], 0) + dt
        if run.get("zone") and not run.get("away"):          # 2.124.0: the zone's own time too
            run["zone_secs"] = run.get("zone_secs", 0) + dt


def act_time(run=None, now=None):
    """The act you're in: its time so far (with the minutes since the last log line) -> secs, or None."""
    run = run or char()
    key = run.get("act")
    if key is None:
        return None
    secs = run["secs"].get(key) or 0
    last = run.get("last_ts")
    if last and key not in run.get("closed", []) and not run.get("afk") and not run.get("away") \
            and not run.get("done"):
        dt = (now or time.time()) - last
        if 0 < dt < GAP:
            secs += dt
    return secs


def _zone_done(run):
    """2.124.0: leaving a campaign zone - its time is kept, the best per zone (for the Campaign zones leaderboard)."""
    z, secs = run.get("zone"), run.get("zone_secs") or 0
    if z and secs > 0 and not run.get("away"):
        b = run.setdefault("zone_best", {})
        if z not in b or secs < b[z]:
            b[z] = round(secs, 1)
    run["zone_secs"] = 0


def zone_time(run=None, now=None):
    """The time since you came into the campaign zone you're in -> secs, or None (a hideout, or not known since the
    app started - 2.124.1: it showed 0:00 then). The leaderboard's time is zone_secs (AFK left out, campaign runs
    only)."""
    import time as _t
    run = run or char()
    if not active(run) or not run.get("zone") or run.get("away"):
        return None
    t0 = run.get("zone_t0")
    if not t0:
        return None
    dt = (now or _t.time()) - t0
    return dt if 0 <= dt < 3 * 3600 else None


def _is_town(step, area_id):
    return bool((step or {}).get("town")) or bool(TOWN_ID.search(str(area_id or "")))


def _enter(run, name, area_id, level, ts, id_act=None):
    c = cfg()
    if area_id in TRIAL_IDS and (run.get("done") or int(level or 0) >= ENDGAME_LEVEL):
        return None                                           # (an ascendancy trial in the endgame: not the campaign)
    _tick(run, ts)
    key, _i = find_zone(name, area_id)
    step = ((act(key) or {}).get("steps") or [])[_i] if key is not None else None
    key = key or id_act or act_of_id(area_id)
    if key is None:
        return None
    left, fight = run.get("area"), run.get("fight")
    _zone_done(run)                                           # 2.124.0: the zone you left, timed; this one starts
    run["away"] = False
    run["zone_t0"] = ts                                       # 2.124.1: when you came in (the overlay's Zone time)
    run["area"] = area_id
    run["early"] = run["hub"] = None
    if (run.get("note") or {}).get("area") != area_id:
        run["note"] = None
    if run.get("done"):                                       # 2.97.0: back in a campaign zone after maps - the line
        run["visit"] = True                                   # (and Vendor ▾) show here; the finished run is kept
        run["act"], run["zone"], run["here"], run["zone_level"] = key, name, None, int(level or 0)
        run["unknown"] = None
        save()
        return "zone"
    town = _is_town(step, area_id)
    if fight and fight.get("area") != area_id and fight.get("area") == left and not town:
        run["fight"] = None                                   # left while its boss fight was on (a town portal to
        rs = [r for r in _route_rewards(run) if norm(r["zone"]) == norm(fight["zone"])     # restock doesn't count)
              and run["rewards"].get(r["id"]) not in ("got", "skip")]
        _event("left", boss=fight["boss"], zone=fight["zone"], gives=", ".join(short_gives(r) for r in rs))
    elif fight and fight.get("area") != area_id and not town:
        run["fight"] = None
    out = "zone"
    prev = run.get("act")
    if is_interlude(prev) and key != prev and town and not is_interlude(key):
        # Kingsmarch while you're on an interlude: the hub, not Act IV again (nothing closes, the act stays)
        run["zone"], run["here"], run["zone_level"], run["hub"] = name, None, int(level or 0), name
        run["unknown"] = None
        save()
        return "zone"
    if step is not None and area_id in (step.get("early_ids") or []):
        run["act"], run["zone"], run["here"], run["zone_level"] = key, name, None, int(level or 0)
        run["early"], run["unknown"] = step.get("early") or "Nothing to do here yet", None
        save()
        return "zone"
    if prev is not None and prev != key and act_order(key) > act_order(prev) \
            and not (is_interlude(prev) and is_interlude(key)):
        _close_act(run, prev, ts)
        if run["ask"]:
            out = "ask"
    came_from = run.get("zone") if prev == key else None
    run["act"], run["zone"], run["here"], run["zone_level"] = key, name, None, int(level or 0)
    seen = run["seen"].setdefault(key, [])
    if norm(name) not in [norm(z) for z in seen]:
        seen.append(name)
    if step is not None and norm(step["zone"]) not in [norm(z) for z in seen]:
        seen.append(step["zone"])                             # (the pack's name for it: "Dreadnought Vanguard" is
    run["levels"][norm(name)] = int(level or 0)               # the Dreadnought's step)
    for r in rewards(key):                                    # rewards a zone proves
        if any(norm(z) == norm(name) for z in r.get("proof") or []) and r["id"] not in run["rewards"]:
            run["rewards"][r["id"]] = "got"
    if town and c["warn"] and _town_asks(run, key):           # rewards the log can't see: asked once, in town
        out = "ask"
    you, zl = char_level(), int(level or 0)
    lv = level_check(you, zl)
    if lv and lv[0] == "under" and (step or {}).get("boss") and area_id not in run["warned"] \
            and not 0 <= ts - (run.get("low_ts") or 0) < LOW_QUIET:          # (a boss zone; not again for a while)
        run["warned"].append(area_id)
        run["low_ts"] = ts
        del run["warned"][:-100]
        _event("low", under=lv[1], you=you, zone_level=zl, zone=name)
    if _i is None:                                            # a zone the guide doesn't know (P)
        lz = c["learned"].setdefault(key, [])
        if norm(name) not in [norm(x["zone"]) for x in lz]:
            lz.append({"zone": name, "after": came_from, "level": int(level or 0)})
        run["unknown"] = name
        out = "unknown" if out == "zone" else out
    else:
        run["unknown"] = None
    save()
    return out


def _town_asks(run, key):
    """In town: the rewards of zones you've been through that the log can't prove (no boss line for them) - each
    asked once (a Not yet asks once more, next town). -> True when there is something to ask."""
    added = False
    order = act_order(key)
    for r in _route_rewards(run):
        rid = r["id"]
        if run["rewards"].get(rid) in ("got", "skip", "missed") or rid in run["ask"]:
            continue
        n = run["asked"].count(rid)
        if n >= 2 or (n == 1 and rid not in run["not_yet"]):
            continue
        if act_order(r["act"]) > order or norm(r["zone"]) not in _seen(run, r["act"]):
            continue
        if r.get("cue") and r["cue"] not in run["killed"] and rid not in run["not_yet"] and not r.get("town"):
            continue                                          # (its boss line will tick it)
        if rid in run["not_yet"]:
            run["not_yet"].remove(rid)                        # (the once more)
        run["asked"].append(rid)
        run["ask"].append(rid)
        added = True
    return added


def level_check(you, zone):
    """Your level against the zone's -> ('ok' / 'under' / 'over', levels off, safe range) or None (one is unknown).
    Under: 3 or more below the zone (bosses hit harder). Over: more than 3 + your level / 16 above it (the XP
    penalty starts there)."""
    you, zone = int(you or 0), int(zone or 0)
    if not you or not zone:
        return None
    safe = 3 + you // 16
    d = you - zone
    if d <= -3:
        return "under", -d, safe
    if d > safe:
        return "over", d, safe
    return "ok", d, safe


def level_text(you, zone):
    """'✓ Lvl 12 · OK', '! Lvl 9 · 3 under', '! Lvl 30 · 6 over', or 'Lvl ?' - a mark and a word, never a color
    alone."""
    lv = level_check(you, zone)
    if not lv:
        return f"Lvl {you}" if you else "Lvl ?"
    if lv[0] == "ok":
        return f"✓ Lvl {you} · OK"
    return f"! Lvl {you} · {lv[1]} {lv[0]}"


def level_how(you, zone):
    """The level check's hover: the numbers and the rule."""
    lv = level_check(you, zone)
    if not lv:
        return ("Your level shows after your next level-up (the game's log says it then)." if not you else
                "The zone's level shows once you enter a campaign zone.")
    st, n, safe = lv
    now = {"ok": "in range", "under": f"{n} under", "over": f"{n} over"}[st]
    return (f"You {you}, zone {zone}: {now}.\n"
            f"Under: 3 or more levels below the zone - bosses hit harder. Kill a few packs first.\n"
            f"Over: more than 3 + {you} ÷ 16 (rounded down) = {safe} above - the game cuts your XP.")


# ---------------------------------------------------------------- the line on the overlay
MAPS_LEVEL = 65                   # 2.90.0: a character this level is past the campaign (maps start at 65)


def active(run=None):
    c = cfg()
    run = run or char()
    if not run.get("done") and run.get("act") is not None and char_level() >= MAPS_LEVEL:
        run["done"] = True              # 2.90.0: maps were reached while the log wasn't being read (it showed in the
                                        # hideout, post-campaign)
    return bool(c["on"]) and run.get("act") is not None and not (run.get("done") and c["off_at_maps"]
                                                                 and not run.get("visit"))


def shown(run=None):
    """Round 18 (feedback: the Campaign Helper showed in the hideout): does the Campaign Bar / line show now? Only in
    a campaign area (its towns too) - never in a hideout or anywhere else outside the campaign (run["away"], from the
    game's log; at start-up from the log's last area - where_now)."""
    run = run or char()
    return active(run) and not run.get("away")


def where_now(area_id, area_kind=None):
    """Round 18: the area you're in when the app starts (the last area line in the log's tail): a hideout or any
    place outside the campaign -> away (the line hides); a campaign area -> not away. -> True when that changed."""
    if not cfg()["on"] or not area_id:
        return False
    run = char()
    away = area_kind == "map" or act_of_id(area_id) is None
    if bool(run.get("away")) == away:
        return False
    run["away"] = away
    if away:
        run["visit"] = False
    return True


def line(run=None):
    """-> what the Campaign Bar's line says, or None:
      act, zone, head ('ACT I · CLEARFELL'), step ('3 / 14'), do (what to do now, its gain in it), then (where
      next: the step's own '→ ...', else the next step), gain ('+30 spirit' - in do), done (its boss is down),
      tip, unknown, in_town, early, level (you, zone)."""
    run = run or char()
    if not active(run):
        return None
    key = run["act"]
    rows = steps(key, run)
    cur = _here_index(run, key, rows)
    here = rows[cur] if cur is not None else None
    zone = (here or {}).get("zone") or run.get("zone") or "?"
    if run.get("hub"):
        zone = run["hub"]
    a = act(key) or {}
    if cur is None:                       # a zone this route leaves out (or not known): next from where it is in
        order = [norm(s["zone"]) for s in a.get("steps") or []]    # the act - never from the top (2.143: "On
        z = norm(run.get("zone"))                                   # you go, then the Riverbank" in Freythorn)
        at = order.index(z) if z in order else -1
        start = next((i for i, s in enumerate(rows) if norm(s["zone"]) in order and order.index(norm(s["zone"])) > at),
                     len(rows))
    else:
        start = cur + 1
    nxt = next((s for s in rows[start:] if s["state"] == "todo"), None)
    if a.get("hub") and here is not None and here.get("town"):  # Act IV: an island you haven't done
        nxt = next((s for s in rows if s.get("island") and s["state"] == "todo"), nxt)
    if run.get("hub"):                                           # (an interlude, in Kingsmarch)
        nxt = next((s for s in rows if s["state"] == "todo"), None)
    done = run.get("area") in run.get("killed", []) and here is not None
    gain = ""
    if run.get("early"):
        do = run["early"]
    elif run.get("hub"):
        do = f"In {zone}: hand in, then go on with {act_name(key)}"
    elif here is not None:
        do = here.get("do") or ""
        if here.get("back") and cur is not None:
            after = [norm(z) for z in here.get("back_after") or []]
            seen = _seen(run, key)
            if (after and all(z in seen for z in after)) or \
                    (not after and any(s["state"] == "done" for s in rows[cur + 1:])):
                do = here["back"]
        if not do and here.get("learned"):
            do = "Not in the guide yet"
    elif run.get("unknown"):
        do = "Not in the guide yet"
    else:
        do = f"Not on the {dict(ROUTES)[route_of(run)]} route"
    do, to = _split_to(do)
    gain = _gain_in(do)
    note = (run.get("note") or {}).get("text") if (run.get("note") or {}).get("area") == run.get("area") else ""
    if done:
        boss = (here or {}).get("boss") or "The boss"
        do = f"✓ {boss[0].upper() + boss[1:]} is down" + (f" ({gain})" if gain else "")
        if note:
            do += f" - {note}"
    elif note:
        do = note
    if not pack().get("style", 1) >= 2 and here is not None:   # (an old pack: the reward added, as it was)
        gives = [short_gives(r) for r in rewards(key) if norm(r["zone"]) == norm(zone)
                 and run["rewards"].get(r["id"]) not in ("got", "skip")]
        if gives and "(+" not in do:
            do += f" ({', '.join(gives)})"
    then = to or (nxt or {}).get("zone", "")
    return {"act": act_name(key), "zone": zone, "head": f"{act_name(key).upper()} · {zone.upper()}",
            "do": do, "then": then, "next": (nxt or {}).get("zone", ""), "gain": gain, "done": done,
            "step": f"{cur + 1} / {len(rows)}" if cur is not None and rows else "",
            "tip": (here or {}).get("tip", "") if cfg()["tips"] else "",
            "unknown": bool(run.get("unknown")), "in_town": bool((here or {}).get("town") or run.get("hub")),
            "early": bool(run.get("early")),
            "level": (char_level(), 0 if ((here or {}).get("town") or run.get("hub")) else int(run.get("zone_level") or 0)),
            "levels": " · ".join(x for x in (f"You {char_level()}" if char_level() else "",
                                             f"zone {run.get('zone_level')}" if run.get("zone_level") else "") if x)}


def line_text(run=None):
    """The line in one piece: 'Kill Beira of the Rotten Pack (+10% cold res) → The Grelwood'."""
    d = line(run)
    if not d:
        return ""
    return d["do"] + (f" → {d['then']}" if d["then"] else "")


def got_so_far(run=None):
    """The Campaign Bar's Got so far -> {points: (have, of, [lines]), spirit: ..., res: ...} over the route's
    rewards; each line is how it was worked out (✓ got, ✕ missed, ○ to come)."""
    run = run or char()
    out = {}
    for name, kinds in (("points", ("points",)), ("spirit", ("spirit",)), ("res", RES_KINDS)):
        have = of = 0
        lines = []
        for r in _route_rewards(run):
            if r.get("kind") not in kinds:
                continue
            n = int(r.get("amount") or 0)
            st = run["rewards"].get(r["id"])
            of += n
            if st == "got":
                have += n
            mark = {"got": "✓", "missed": "✕", "skip": "–"}.get(st, "○")
            lines.append(f"{mark} {r['what']} ({r['zone']}): {short_gives(r)}")
        out[name] = (have, of, lines)
    return out


def got_text(g):
    p, sp, rs = g["points"], g["spirit"], g["res"]
    return f"Points {p[0]}/{p[1]} · Spirit {sp[0]}/{sp[1]} · Res {rs[0]}/{rs[1]}%"


def got_how(g):
    """Got so far's hover: each total and the rewards behind it."""
    out = []
    for name, title in (("points", "Passive points"), ("spirit", "Spirit"), ("res", "Resistances (%)")):
        have, of, lines = g[name]
        out.append(f"{title}: {have} of {of}")
        got = [x for x in lines if x.startswith("✓")]
        miss = [x for x in lines if x.startswith("✕")]
        out += ["  " + x for x in got + miss]
        rest = len(lines) - len(got) - len(miss)
        if rest:
            out.append(f"  ○ {rest} more to come")
    out.append("✓ from a boss's line in the game's log or your answer in town. Tick any by hand: click the line "
               "above the bar › Rewards.")
    return "\n".join(out)


def vendor_searches(act_key=None):
    """-> [(name, regex)] for this act (the guide pack's)."""
    act_key = act_key if act_key is not None else char().get("act")
    return [(v["name"], v["regex"]) for v in pack().get("vendor") or [] if v.get("act") in ("*", act_key)]


def splits(run=None):
    """-> [(act name, this run's secs or None, best or None, here?)] for every act in the pack."""
    run = run or char()
    best = cfg()["best"].get(SETTINGS.get("league") or "", {})
    return [(a.get("name"), run["secs"].get(a["key"]), best.get(a["key"]), run.get("act") == a["key"])
            for a in acts()]


def fmt(secs):
    if secs is None:
        return "-"
    s = int(secs)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


def mark_optional(zone):
    c = cfg()
    if norm(zone) not in c["optional_zones"]:
        c["optional_zones"].append(norm(zone))
    save()


def set_note(zone, text):
    c = cfg()
    if text.strip():
        c["notes"][norm(zone)] = text.strip()[:200]
    else:
        c["notes"].pop(norm(zone), None)
    save()


def to_pool():
    """Learned zones not pooled yet -> [{act, zone, after, level}] (Community data sharing)."""
    c = cfg()
    out = []
    for key, rows in c["learned"].items():
        for lz in rows:
            k = f"{key}|{norm(lz['zone'])}"
            if k not in c["sent"]:
                out.append({"act": key, "zone": lz["zone"][:80], "after": (lz.get("after") or "")[:80],
                            "level": int(lz.get("level") or 0)})
    return out[:100]


def pooled(rows):
    c = cfg()
    for r in rows:
        k = f"{r['act']}|{norm(r['zone'])}"
        if k not in c["sent"]:
            c["sent"].append(k)
    c["sent"] = c["sent"][-500:]
    save()
