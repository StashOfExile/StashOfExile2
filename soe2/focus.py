"""League Plan (2.73.0 as League Focus; one name from 2.119.0): a set-and-forget game plan for the league - goals by phase, a stockpile to buy while it's
cheap, the farms you planned - and (2.73.1) reminders over the game. Built for players who get sidetracked
(ADHD-friendly): everything is optional, quiet by default, and always says why it showed up.

3.2.0 rework (owner, mockups 2026-11-22): a goal's Done when is only what the game's log can see (a level, an act,
reaching maps, maps run) or "I tick it myself" - no divines, no typed numbers. A farm's Goal is a level, hours of
play, maps run or a date, counted from the log once that farm is NOW; reaching it reminds you to move on. The build
lock is gone - the app can't know your build, character or divines. Reminders: always in town or your hideout,
always while you play, always say why, always gentle; Snooze is a real button.

Stored in SETTINGS["focus"]. Reads only what the app already knows - the game's log (Client.txt: zones, levels),
poe.ninja prices; counts and progress are what you type (2.73.2: not Wealth - it doesn't track live and is a beta).
Nothing touches the game.

Phases: "start" (league start / campaign), "maps" (once you reach maps), "long" (long term). The current phase moves
to "maps" by itself the first time the log shows you in a waystone map (2.73.1), or by hand."""
import copy
import time
import uuid

from .config import SETTINGS, save_json

PHASES = (("start", "League start"), ("maps", "When I reach maps"), ("long", "Long term"))
TRIGGERS = (("town", "In town, now and then"), ("phase", "Once, when this phase starts"),
            ("never", "Never, keep it on the plan"))
DEFAULTS = {
    "on": True,                     # the whole feature (Overlay › Helpers); 2.118.0: on for a new install
    "line": True,                   # the focus line on the overlay (I)
    "phase": "start",
    "now": None,                    # the goal shown on the focus line (None: the first open one of this phase)
    "goals": [],                    # [{id, text, phase, done, trigger, target_div, created, snooze, stopped}]
    "stockpile": [],                # [{name, goal, under, paid}]
    "farms": [],                    # [{strat, name, src, kind, target, started, maps_at, secs, done}]
    "pokes": {"per_hour": 2, "checkin_min": 45, "snooze_min": 60, "milestones": True, "prices": True,
              "farms": True, "alert": True, "sound": True, "windows": False, "quiet_on": False, "quiet": [23, 8]},
    # (2.131.2: Map supplies moved to Top Up Reminders - supplies_out hands them over)
    "history": [],
}


GONE_POKES = ("tone", "town_only", "session_only", "why", "quieter")   # 3.2.0: always on, no switch


def cfg():
    f = SETTINGS.setdefault("focus", {})
    for k, v in DEFAULTS.items():
        if k not in f:                                   # 2.125.4: copied only when missing
            f[k] = copy.deepcopy(v)
    for k, v in DEFAULTS["pokes"].items():
        f["pokes"].setdefault(k, v)
    if not f.get("lp_320"):                              # 3.2.0 rework, once
        f.pop("lock", None)
        for k in GONE_POKES:
            f["pokes"].pop(k, None)
        for g in f["goals"]:
            if g.get("trigger") not in dict(TRIGGERS):   # (once a week is gone: in town, now and then)
                g["trigger"] = "town"
            if g.get("target_kind") in ("div", "count") or (g.get("target_div") and not g.get("target_kind")):
                g["target_kind"], g["target"], g["target_div"] = None, None, None   # (the app can't see those)
        for r in f["farms"]:
            r.setdefault("kind", "none")
        f["lp_320"] = True
    return f


def save():
    save_json("settings.json", SETTINGS)


def phase_name(key):
    return dict(PHASES).get(key, key)


# ---------------------------------------------------------------- goals
# 3.2.0: what a goal's Done when can be - each one the game's log can see, so it ticks itself; or you tick it.
# (kind, the words, what the number is - "" for none)
DONE_WHEN = (("tick", "I tick it myself", ""), ("level", "My character reaches level", "Level"),
             ("act", "I reach act", "Act"), ("reach_maps", "I reach maps", ""), ("maps", "I've run maps", "Maps"))
DONE_HINT = {"tick": "For anything the game's log can't see, like a drop or a craft.",
             "level": "Ticks itself. The level comes from the game's log.",
             "act": "Ticks itself when the log shows you in that act.",
             "reach_maps": "Ticks itself in your first waystone map.",
             "maps": "Counted from the day you add it, from the game's log."}
TARGETS = tuple((k, n, u.lower()) for k, n, u in DONE_WHEN if k != "tick")      # (older callers)
AUTO_TARGETS = ("level", "act", "reach_maps", "maps")


def add_goal(text, phase="start", trigger="town", target_div=None, target_kind=None, target=None):
    """target_kind / target (2.73.4) - or the older target_div (a div target)."""
    if target is None and target_div is not None:
        target_kind, target = "div", target_div
    kind = target_kind if target_kind in dict((k, n) for k, n, _u in TARGETS) else None
    if kind == "reach_maps":
        target = 1
    g = {"id": uuid.uuid4().hex[:10], "text": text.strip(), "phase": phase if phase in dict(PHASES) else "start",
         "done": False, "trigger": trigger if trigger in dict(TRIGGERS) else "town",
         "target_kind": kind if kind and target else None, "target": float(target) if kind and target else None,
         "target_div": None,
         "maps_at": state()["maps"], "created": time.time(), "snooze": 0, "stopped": False}
    cfg()["goals"].append(g)
    save()
    return g


def goal(gid):
    return next((g for g in cfg()["goals"] if g["id"] == gid), None)


def remove_goal(gid):
    f = cfg()
    f["goals"] = [g for g in f["goals"] if g["id"] != gid]
    if f.get("now") == gid:
        f["now"] = None
    save()


def set_done(gid, done=True):
    g = goal(gid)
    if g:
        g["done"] = bool(done)
        f = cfg()
        if done and f.get("now") == gid:
            f["now"] = None
        save()
    return g


def goals_of(phase):
    return [g for g in cfg()["goals"] if g["phase"] == phase]


def current():
    """The goal on the focus line: the one you picked, else the first open one of the current phase (then the
    phases after it)."""
    f = cfg()
    g = goal(f.get("now")) if f.get("now") else None
    if g and not g["done"]:
        return g
    order = [p for p, _n in PHASES]
    start = order.index(f["phase"]) if f["phase"] in order else 0
    for p in order[start:]:
        for g in goals_of(p):
            if not g["done"]:
                return g
    return None


def goal_target(g):
    """-> (kind, target) of a goal, or (None, None): one you tick yourself."""
    if not g or not g.get("target") or g.get("target_kind") not in AUTO_TARGETS:
        return None, None
    return g["target_kind"], float(g["target"])


def char_level():
    """The level the log last showed for your character: the name typed in Options, else the last one to level."""
    st = state()
    lv = st.get("levels") or {}
    mine = ((SETTINGS.get("tracker") or {}).get("character") or "").strip().lower()
    for who, n in lv.items():
        if who.lower() == mine and mine:
            return n
    last = st.get("last_char")
    return lv.get(last) if last else None


def act_now():
    """The act the Campaign Helper last saw you in, 1-4 (an interlude counts as 4), or 0."""
    try:
        from . import campaign as CP
        a = str(CP.char().get("act") or "")
    except Exception:
        return 0
    return int(a) if a.isdigit() else (4 if a.startswith("i") else 0)


def progress(g, worth=None):
    """(have, target) for a goal with a target, or None. Divines, acts and numbers: what you type on the goal
    (2.73.2: Wealth isn't used - it doesn't track live). 2.73.4: a level comes from the log, maps run are counted
    by the log since the goal was set. worth is ignored (kept for older callers)."""
    kind, target = goal_target(g)
    if not kind:
        return None
    if kind == "level":
        have = char_level() or 0
    elif kind == "maps":
        have = state()["maps"] - int(g.get("maps_at") or 0)
    elif kind == "reach_maps":
        have = 1 if state()["reached_maps"] else 0
    else:                                                    # act: the furthest the Campaign Helper saw
        have = g["have"] = max(int(g.get("have") or 0), act_now())
    return max(0.0, float(have)), target


def progress_text(g):
    """ "Level 74 of 90", "Act 2 of 4", "37 of 100 maps", "Not in maps yet" - or "" (you tick it)."""
    p = progress(g)
    if not p:
        return ""
    kind = goal_target(g)[0]
    h, t = p
    if kind == "level":
        return f"Level {h:g} of {t:g}"
    if kind == "act":
        return f"Act {h:g} of {t:g}"
    if kind == "reach_maps":
        return "In maps" if h else "Not in maps yet"
    return f"{h:g} of {t:g} maps"


def check_goals(now=None):
    """Goals the log can see tick themselves once reached. -> the ones that just did (each gets a milestone
    reminder when Remind me about goals is on)."""
    f, st = cfg(), state()
    done = []
    for g in f["goals"]:
        if g["done"]:
            continue
        p = progress(g)
        if p and p[1] and p[0] >= p[1]:
            g["done"], g["auto_done"] = True, True
            if f.get("now") == g["id"]:
                f["now"] = None
            done.append(g)
            if f["pokes"].get("milestones"):
                st["pending"].append({"kind": "reached", "goal": g["id"], "at": now or time.time()})
    if done:
        save()
    return done


def set_have(gid, have):
    g = goal(gid)
    if g is not None:
        g["have"] = max(0.0, float(have or 0))
        save()
    return g


def set_phase(phase):
    f = cfg()
    if phase in dict(PHASES) and f["phase"] != phase:
        f["phase"] = phase
        f["now"] = None
        save()
        return True
    return False


# ---------------------------------------------------------------- stockpile, farms
def add_stock(name, goal_qty=0, under=None):
    row = {"name": name.strip(), "goal": int(goal_qty or 0), "under": under, "paid": None, "have": 0}
    cfg()["stockpile"].append(row)
    save()
    return row


def set_stock_have(name, have):
    row = next((r for r in cfg()["stockpile"] if r["name"] == name), None)
    if row is not None:
        row["have"] = max(0, int(have or 0))
        save()
    return row


def stock_have(name):
    row = next((r for r in cfg()["stockpile"] if r["name"] == name), None)
    return None if row is None else int(row.get("have") or 0)


def remove_stock(name):
    f = cfg()
    f["stockpile"] = [r for r in f["stockpile"] if r["name"] != name]
    save()


def stock_status(row, have=None, each=None):
    """-> "cheap" (under your price), "ok", "done" (you have enough) or "?" (no price)."""
    if have is not None and row.get("goal") and have >= row["goal"]:
        return "done"
    if each is None:
        return "?"
    under = row.get("under")
    return "cheap" if under is not None and each <= float(under) else "ok"


# 3.2.0: a farm's Goal - when to move on to the next one. (kind, the words, what the number is)
FARM_GOALS = (("level", "My character reaches level", "Level"), ("hours", "I've played it for hours", "Hours"),
              ("maps", "I've run maps of it", "Maps"), ("date", "A date", "Date"), ("none", "I move on myself", ""))


def add_farm(strat_id, name, kind="none", target=None, src="", until=None):
    """strat_id: a Farming Strategies strat (src: Mine / Community / Official), or None for one of your own. kind /
    target: its Goal (FARM_GOALS); a date is a timestamp. until: the 2.73 words, kept for older callers."""
    f = cfg()
    name = (name or "").strip()
    if not name or any((strat_id and x["strat"] == strat_id) or x["name"].lower() == name.lower() for x in f["farms"]):
        return None
    kind = kind if kind in dict((k, n) for k, n, _u in FARM_GOALS) else "none"
    if kind != "none" and not target:
        kind = "none"
    row = {"strat": strat_id, "name": name, "src": src, "kind": kind,
           "target": float(target) if kind != "none" and target else None,
           "started": None, "maps_at": None, "secs": 0.0, "done": False}
    if until:
        row["until"] = until
    f["farms"].append(row)
    farm_now()                                           # (the first one starts counting at once)
    save()
    return row


def farm_now():
    """The farm you're on: the first one not moved on from. It starts counting the first time it's NOW."""
    for r in cfg()["farms"]:
        if not r.get("done"):
            if r.get("started") is None:
                r["started"], r["maps_at"], r["secs"] = time.time(), state()["maps"], 0.0
            return r
    return None


def farm_progress(r):
    """(have, target) of a farm's Goal, or None (I move on myself / not started yet)."""
    kind, t = r.get("kind") or "none", r.get("target")
    if kind == "none" or not t or r.get("started") is None:
        return None
    if kind == "level":
        return float(char_level() or 0), float(t)
    if kind == "hours":
        return round(float(r.get("secs") or 0) / 3600, 1), float(t)
    if kind == "maps":
        return float(state()["maps"] - int(r.get("maps_at") or 0)), float(t)
    return (1.0 if time.time() >= float(t) else 0.0), 1.0                 # a date


def farm_text(r):
    """ "Goal: level 95 · now 93" - the words for a farm's row."""
    kind, t = r.get("kind") or "none", r.get("target")
    if kind == "none":
        return "Goal: I move on myself" + (f" · {r['until']}" if r.get("until") else "")
    goal_words = {"level": f"level {t:g}", "hours": f"{t:g} hours of play", "maps": f"{t:g} maps",
                  "date": time.strftime("%b %d", time.localtime(t))}[kind]
    p = farm_progress(r)
    if p is None:
        return f"Goal: {goal_words} · counted once it's NOW"
    have = {"level": f"now {p[0]:g}", "hours": f"{p[0]:g} hours so far", "maps": f"{p[0]:g} so far",
            "date": "today" if p[0] else ""}[kind]
    return f"Goal: {goal_words}" + (f" · {have}" if have else "") + " · from the game's log"


def check_farms(now=None):
    """The farm you're on reached its Goal: it's moved on from and the next one starts. -> that farm or None."""
    f, st = cfg(), state()
    r = farm_now()
    p = farm_progress(r) if r else None
    if not p or p[0] < p[1]:
        return None
    r["done"] = True
    nxt = farm_now()
    if f["pokes"].get("farms"):
        st["pending"].append({"kind": "farm", "name": r["name"], "next": nxt["name"] if nxt else None,
                              "at": now or time.time()})
    save()
    return r


def move_farm(i, step):
    farms = cfg()["farms"]
    j = i + step
    if 0 <= i < len(farms) and 0 <= j < len(farms):
        farms[i], farms[j] = farms[j], farms[i]
        save()
        return True
    return False


def remove_farm(i):
    farms = cfg()["farms"]
    if 0 <= i < len(farms):
        del farms[i]
        farm_now()
        save()


NO_GOAL = "No goal yet - click to set one in League Plan"


def line_text(worth=None):
    """The overlay's focus line: "NOW  <goal>" (+ progress), or "" when there is nothing to show."""
    f = cfg()
    if not f["on"]:                                    # 2.97.0: on = its line shows (no line switch)
        return "", None
    g = current()
    r = next((x for x in f["farms"] if not x.get("done")), None)
    farm = f" · farm: {r['name']}" if r else ""          # (3.2.0: the farm you're on, under your goal)
    if not g:
        return (f"Farm: {r['name']}", None) if r else (NO_GOAL, None)
    p = progress(g, worth)
    return g["text"] + farm, (p[0] / p[1] if p and p[1] else None)


# ---------------------------------------------------------------- 2.131.2: map supplies moved to Top Up
def supplies_out():
    """Map supplies (2.73.3-2.131.1: refill every N maps / minutes) are Top Up Reminders now, which counts what your
    inventory really holds. -> the names that were on the list (once; the list is then gone)."""
    f = SETTINGS.get("focus") or {}
    rows = f.pop("supplies", None) or []
    f.pop("sup_2985", None)
    (f.get("pokes") or {}).pop("supplies", None)
    if rows:
        save()
    return [str(r.get("name") or "").strip() for r in rows if str(r.get("name") or "").strip()]


# ---------------------------------------------------------------- 2.73.1: pokes
# What each reminder is, in the order they win when several are due. "urgent" ones (milestones, a goal reached, a
# farm to move on from) don't count toward the per-hour limit; every one waits for town or your hideout.
KINDS = {"milestone": "urgent", "reached": "urgent", "farm": "urgent", "price": "normal", "checkin": "normal",
         "nudge": "normal"}
HEAD, ASK = "A nudge from your plan", "Still on plan?"           # (3.2.0: always gentle)
PLAYING = 10 * 60          # the log showed you within this many seconds: you're playing


def state():
    """The pokes' own bookkeeping (kept with the plan)."""
    f = cfg()
    st = f.setdefault("state", {})
    st.setdefault("pending", [])           # urgent pokes waiting for town: [{kind, ...}]
    st.setdefault("sent", [])              # timestamps of normal pokes (per-hour limit)
    st.setdefault("chars", [])             # characters the log has shown
    st.setdefault("reached_maps", False)
    st.setdefault("price_day", {})         # stockpile name -> the day it was poked
    st.setdefault("notoday", {})           # goal id -> the day you said "Not today"
    st.setdefault("notoday_streak", 0)
    st.setdefault("played", 0.0)           # seconds of play since the last check-in
    st.setdefault("checkin_snooze", 0.0)
    st.setdefault("maps", 0)               # 2.73.3: waystone maps the log has shown
    st.setdefault("map_secs", 0.0)         # seconds spent in maps
    st.setdefault("map_in", None)          # when the current map was entered
    st.setdefault("map_seed", None)
    st.setdefault("seen", 0.0)             # 3.2.0: when the log last showed you playing
    st.setdefault("where", None)           # 3.2.0: the log's last area kind - town / hideout / map / other
    return st


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def log_event(kind, data, area_kind=None, now=None):
    """A game-log event -> may queue an urgent poke. area_kind: the tracker's 'map' / 'town' / 'hideout' / 'other'."""
    f, st = cfg(), state()
    if not f["on"]:
        return None
    now = now or time.time()
    last, st["seen"] = st.get("seen") or 0.0, now          # 3.2.0: time played, from the log alone - the farm
    r = farm_now()                                         # you're on counts it, overlay or not
    if r is not None and last and 0 < now - last <= PLAYING:
        r["secs"] = float(r.get("secs") or 0) + (now - last)
    if kind == "area":
        st["where"] = area_kind
    if kind == "area":                                     # 2.73.3: count maps and time in maps (map goals)
        if st["map_in"] is not None:
            st["map_secs"] += max(0.0, min(now - st["map_in"], 3 * 3600))
            st["map_in"] = None
        if area_kind == "map":
            st["map_in"] = now
            key = f"{data.get('area')}|{data.get('seed')}"
            if key != st["map_seed"]:                      # back into the same map (a portal) isn't a new one
                st["maps"] += 1
                st["map_seed"] = key
    if kind == "area" and area_kind == "map" and not st["reached_maps"]:
        st["reached_maps"] = True
        moved = set_phase("maps")
        if f["pokes"].get("milestones") and (moved or goals_of("maps")):
            st["pending"].append({"kind": "milestone", "id": "maps", "at": now})
        check_goals(now)
        check_farms(now)
        save()
        return "milestone"
    if kind == "area":
        check_goals(now)
        check_farms(now)
        save()
    if kind == "level":
        who, lvl = data.get("who", ""), int(data.get("level") or 0)
        known = who in st["chars"]
        if not known:
            st["chars"] = (st["chars"] + [who])[-30:]
        lv = st.setdefault("levels", {})                   # 2.73.4: level goals
        lv[who] = max(lvl, lv.get(who, 0)) if known else lvl
        st["last_char"] = who
        if data.get("cls"):                                # 2.86.0: the class / ascendancy, for the leaderboards
            cl = st.setdefault("classes", {})
            cl[who] = data["cls"]
            for k in list(cl)[:-30]:
                cl.pop(k, None)
        if len(lv) > 30:
            for k in list(lv)[:-30]:
                lv.pop(k, None)
        check_goals(now)
        check_farms(now)
        save()
    return None


def _quiet(pk, now):
    if not pk.get("quiet_on"):
        return False
    a, b = (pk.get("quiet") or [23, 8])[:2]
    h = time.localtime(now).tm_hour
    return (a <= h or h < b) if a > b else (a <= h < b)


def _room(pk, st, now):
    per = int(pk.get("per_hour") or 0)
    if st["notoday_streak"] >= 3:                          # (3.2.0: quieter after 3 "Not today", always)
        per = per // 2
    st["sent"] = [t for t in st["sent"] if now - t < 3600]
    return per > 0 and len(st["sent"]) < per


def due(now=None, in_town=True, session=True, played=0.0, prices=None, have=None):
    """The poke to show now, or None. prices(name) -> divines each or None; have(name) -> count or None.
    played: seconds of play since the last call (for the check-in)."""
    f, st = cfg(), state()
    if not f["on"]:
        return None
    now = now or time.time()
    pk = f["pokes"]
    st["played"] += max(0.0, played)
    playing = session or now - float(st.get("seen") or 0) <= PLAYING      # (3.2.0: always only while you play,
    if st.get("where") in ("town", "hideout", "map", "other") and not session:   # always only in town or hideout)
        in_town = st["where"] in ("town", "hideout")
    if not playing or _quiet(pk, now) or not in_town:
        return None
    if st["pending"]:
        return st["pending"].pop(0)
    if not _room(pk, st, now):
        return None
    if pk.get("prices") and prices:
        for row in f["stockpile"]:
            if st["price_day"].get(row["name"]) == today(now):
                continue
            each = prices(row["name"])
            h = have(row["name"]) if have else None
            if stock_status(row, h, each) == "cheap":
                st["price_day"][row["name"]] = today(now)
                return {"kind": "price", "name": row["name"], "each": each, "have": h, "goal": row.get("goal"),
                        "under": row.get("under")}
    cm = int(pk.get("checkin_min") or 0)
    if cm and st["played"] >= cm * 60 and now >= st["checkin_snooze"] and current():
        st["played"] = 0.0
        return {"kind": "checkin", "goal": current()["id"]}
    for g in _nudgeable(now):
        g["poked"] = now
        return {"kind": "nudge", "goal": g["id"]}
    return None


def _nudgeable(now):
    st = state()
    out = []
    for g in cfg()["goals"]:
        if g["done"] or g.get("stopped") or (g.get("snooze") or 0) > now or st["notoday"].get(g["id"]) == today(now):
            continue
        last = g.get("poked") or 0
        if g["trigger"] == "town" and now - last >= 3 * 3600:
            out.append(g)
    return sorted(out, key=lambda g: g.get("poked") or 0)


def sent(poke, now=None):
    """A poke was shown: count it (urgent ones don't) and keep it in the history."""
    st, f = state(), cfg()
    now = now or time.time()
    if KINDS.get(poke["kind"]) == "normal":
        st["sent"].append(now)
    f["history"] = (f["history"] + [{"ts": now, "kind": poke["kind"], "text": poke_text(poke)[1][:200],
                                     "answer": None}])[-60:]
    save()


def answer(poke, what, now=None):
    """Your answer to a reminder -> what it changes. what: done / snooze / nottoday / stop / ontrack / sidetracked /
    break / ok."""
    st, f = state(), cfg()
    now = now or time.time()
    g = goal(poke.get("goal")) if poke.get("goal") else None
    if what == "done" and g:
        set_done(g["id"])
    elif what == "snooze" and g:
        g["snooze"] = now + int(f["pokes"].get("snooze_min") or 60) * 60
    elif what == "nottoday" and g:
        st["notoday"][g["id"]] = today(now)
        st["notoday_streak"] += 1
    elif what == "stop" and g:
        g["stopped"] = True
    elif what == "break":
        st["checkin_snooze"] = now + 30 * 60
    if what not in ("nottoday",):
        st["notoday_streak"] = 0
    if f["history"] and f["history"][-1]["kind"] == poke["kind"] and f["history"][-1]["answer"] is None:
        f["history"][-1]["answer"] = what
    save()


def poke_text(poke):
    """-> (title, text, why, [(answer, label)]) for a reminder - always gentle, always with why."""
    f = cfg()
    head, ask = HEAD, ASK
    k = poke["kind"]
    snooze = ("snooze", f"Snooze · {int(f['pokes'].get('snooze_min') or 60)} min")
    if k == "nudge":
        g = goal(poke["goal"]) or {"text": "?", "created": time.time(), "phase": "start", "trigger": "town"}
        pt = progress_text(g)
        return (head.upper(), f"Still on: {g['text']}" + (f"\n{pt} · from the game's log" if pt else ""),
                f"Why now: you're in town, where you asked to be reminded. A {phase_name(g['phase'])} goal.",
                [("done", "✓ Done"), snooze, ("nottoday", "Not today")])
    if k == "reached":
        g = goal(poke.get("goal")) or {"text": "?"}
        return ("GOAL REACHED", f"✓ {g['text']}\n{progress_text(g) or 'Done'}",
                "Why now: the game's log shows you reached it, so it ticked itself.",
                [("plan", "Open League Plan"), ("ok", "Got it")])
    if k == "farm":
        nxt = poke.get("next")
        body = f"You reached the Goal for {poke.get('name', '?')}." + (f"\nNext on your plan: {nxt}." if nxt else
                                                                    "\nThat was the last farm on your plan.")
        return ("TIME TO MOVE ON", body, "Why now: the game's log shows the farm's Goal is reached.",
                [("plan", "Open League Plan"), ("ok", "Got it")])
    if k == "milestone":
        lines = [g["text"] for g in goals_of("maps") if not g["done"]][:5]
        farms = [x["name"] for x in f["farms"]][:2]
        body = "Your first waystone map - here's what you planned for this moment:"
        body += "".join(f"\n{i}. {t}" for i, t in enumerate(lines, 1)) or "\n(no goals for maps yet)"
        if farms:
            body += "\nFarm plan: " + ", then ".join(farms)
        return ("YOU REACHED MAPS", body, "Why now: the log shows you in your first waystone map.",
                [("plan", "Open League Plan"), ("ok", "Got it")])
    if k == "price":
        under = poke.get("under")
        body = f"{poke['name']} is {poke['each']:.3g} div" + (f" (you buy under {under:g})." if under is not None else ".")
        if poke.get("goal"):
            body += f"\nYou have {poke.get('have') if poke.get('have') is not None else '?'} of {poke['goal']}."
        return ("CHEAP NOW - YOUR STOCKPILE", body, "Why now: poe.ninja's price is under the one you set.",
                [("exchange", "Open the exchange"), ("ok", "Not today")])
    if k == "checkin":
        g = goal(poke.get("goal"))
        body = ask + (f"\nNow: {g['text']}" if g else "")
        hist = [h for h in f["history"] if h["kind"] == "checkin" and h.get("answer")][-5:]
        if hist:
            body += f"\nOn plan {sum(1 for h in hist if h['answer'] == 'ontrack')} of your last {len(hist)} check-ins."
        return ("CHECK-IN", body, f"Why now: {int(f['pokes'].get('checkin_min') or 45)} min of play since the last one.",
                [("ontrack", "On track"), ("sidetracked", "Got sidetracked"), ("break", "Taking a break")])
    return ("", "", "", [("ok", "OK")])
