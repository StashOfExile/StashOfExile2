"""League Plan: your league goals in one ordered list. Next up is the first open one - on the overlay, and as a
reminder back in town.

3.3.0 redraw (owner, mockups 2026-11-23): no phases, no Farm plan. A goal is a level, an act, maps, a boss, a net
worth from Wealth, div an hour from Map Profit, a strat to farm, your Stockpile, or anything else you tick yourself.
The app counts what it can see. The Stockpile itself is on Exchange Rates; the plan has a Stock up goal for it.

Stored in SETTINGS["focus"]. Reads only what the app already knows - the game's log, Wealth's last count, Map
Profit's log, poe.ninja prices. Nothing touches the game."""
import copy
import time
import uuid

from .config import SETTINGS, save_json

OLD_PHASES = ("start", "maps", "long")           # what 3.2 called its three lists: only their order is kept
TRIGGERS = (("town", "In town, now and then"),)     # 3.2.1 owner: in town only, no choice
DEFAULTS = {
    "on": True,                     # the whole feature (Overlay › Helpers); 2.118.0: on for a new install
    "line": True,                   # the focus line on the overlay (I)
    "goals": [],                    # in order: [{id, text, done, target_kind, target, ref, ref_name, created, ...}]
    "stockpile": [],                # [{name, goal, under, paid, have}] - shown on Exchange Rates
    "pokes": {"per_hour": 2, "checkin_min": 45, "snooze_min": 60, "milestones": True, "prices": True,
              "alert": True, "sound": True, "windows": False, "quiet_on": False, "quiet": [23, 8]},
    # (2.131.2: Map supplies moved to Top Up Reminders - supplies_out hands them over)
    "history": [],
}


GONE_POKES = ("tone", "town_only", "session_only", "why", "quieter", "farms")   # 3.2.0: always on, no switch


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
        f["lp_320"] = True
    if not f.get("lp_321"):                              # 3.2.1 owner: in town only; a farm has no Goal
        f["pokes"].pop("farms", None)
        for g in f["goals"]:
            g["trigger"] = "town"
        f["lp_321"] = True
    if not f.get("lp_330"):                              # 3.3.0 redraw, once: one ordered list
        order = list(OLD_PHASES)
        f["goals"].sort(key=lambda g: order.index(g.get("phase")) if g.get("phase") in order else 0)
        now = f.pop("now", None)
        if now:                                          # the goal you had on the overlay goes first
            f["goals"].sort(key=lambda g: g.get("id") != now)
        for r in f.pop("farms", None) or []:             # a farm you hadn't moved on from: a Farm a strat goal
            if isinstance(r, dict) and r.get("name") and not r.get("done"):
                f["goals"].append(_goal(f"Farm {r['name']}", "farm", None, ref=r.get("strat"), ref_name=r["name"],
                                        secs=float(r.get("secs") or 0)))
        if f["stockpile"] and not any(g.get("target_kind") == "stock" for g in f["goals"]):
            f["goals"].append(_goal(STOCK_TEXT, "stock", 1))
        f.pop("phase", None)
        f["lp_330"] = True
    return f


def save():
    save_json("settings.json", SETTINGS)


# ---------------------------------------------------------------- goals
# What a goal can be, in the order Add a goal lists them: (key, name, where its count comes from)
GOAL_KINDS = (("level", "Level", "From the game's log"),
              ("act", "Campaign", "An act done · from the game's log"),
              ("maps", "Maps", "A tier, or a number run · from the game's log"),
              ("boss", "Boss", "A run of its arena · from the game's log"),
              ("networth", "Net worth", "Divine · from Wealth"),
              ("divhour", "Div an hour", "From Map Profit"),
              ("farm", "Farm a strat", "Hours of play · from the game's log"),
              ("stock", "Stock up", "Your Stockpile · from Exchange Rates"),
              ("tick", "Anything else", "You tick it"))
# what is stored on a goal as target_kind - "act" and "reach_maps" are also what 3.2 saved
AUTO_TARGETS = ("level", "act", "act_done", "campaign", "reach_maps", "maps", "tier", "boss", "networth",
                "divhour", "farm", "stock")
TARGET_RANGE = {"level": (1, 100), "act": (1, 6), "act_done": (1, 6), "maps": (1, 1000), "tier": (1, 16),
                "boss": (1, 100), "networth": (1, 100000), "divhour": (1, 1000), "farm": (1, 1000)}
STOCK_TEXT = "Stock up for the league"
# the tool a goal's count comes from: (the words, the page) - one click from the goal
SOURCE = {"networth": ("Wealth", "wealth"), "divhour": ("Map Profit", "mapprofit"),
          "stock": ("Stockpile in Exchange Rates", "rates"), "farm": ("Farming Strategies", "money"),
          "boss": ("Leaderboards", "leaderboards")}
# pinnacle arenas by their boss, where the name is known - the rest go by the arena's name
BOSS_OF = {"The Burning Monolith": "the Arbiter of Ash", "Twisted Domain": "Xesht, We That Are One",
           "Crux of Nothingness": "the King in the Mists", "Kalguuran Tomb": "Olroth, Origin of the Fall",
           "Simulacrum of Delusion": "the Simulacrum"}
START_PLAN = (("campaign", None, None), ("reach_maps", None, None), ("level", 90, None), ("tier", 15, None),
              ("networth", 10, None), ("boss", 1, "The Burning Monolith"))


def bosses():
    """[arena] - the pinnacle fights the Map library knows, which is what Leaderboards lists."""
    from .maplib import library
    return sorted(n for n, e in library().items() if (e or {}).get("kind") == "Pinnacle")


def goal_words(kind, target=None, ref_name=None):
    """What a goal reads as: "Level 90", "Kill the Arbiter of Ash", "Make 3 div an hour"."""
    n = f"{float(target):g}" if target else ""
    if kind == "level":
        return f"Level {n}"
    if kind == "act_done":
        return f"Finish act {n}"
    if kind == "act":
        return f"Reach act {n}"
    if kind == "campaign":
        return "Finish the campaign"
    if kind == "reach_maps":
        return "Reach maps"
    if kind == "maps":
        return f"Run {n} maps"
    if kind == "tier":
        return f"Reach tier {n} maps"
    if kind == "boss":
        who = BOSS_OF.get(ref_name or "")
        base = f"Kill {who}" if who else f"Beat {ref_name}"
        return base + (f" {n} times" if target and float(target) > 1 else "")
    if kind == "networth":
        return f"Reach a net worth of {n} divine"
    if kind == "divhour":
        return f"Make {n} div an hour"
    if kind == "farm":
        return f"Farm {ref_name}" + (f" for {n} hours" if n else "")
    if kind == "stock":
        return STOCK_TEXT
    return ""


def _goal(text, kind=None, target=None, ref=None, ref_name=None, **more):
    st = (SETTINGS.get("focus") or {}).get("state") or {}
    g = {"id": uuid.uuid4().hex[:10], "text": str(text).strip(), "done": False, "trigger": "town",
         "target_kind": kind if kind in AUTO_TARGETS else None,
         "target": float(target) if kind in AUTO_TARGETS and target else None,
         "ref": ref, "ref_name": ref_name, "maps_at": int(st.get("maps") or 0),
         "runs_at": int((st.get("boss_runs") or {}).get(ref_name or "", 0)), "secs": 0.0,
         "created": time.time(), "snooze": 0, "stopped": False}
    g.update(more)
    return g


def add_goal(text="", kind=None, target=None, ref=None, ref_name=None, target_kind=None, **_old):
    """A goal at the end of the plan. kind: one of AUTO_TARGETS, or None - you tick it. text: yours for a goal you
    tick; the others are worded from what they count."""
    kind = kind if kind in AUTO_TARGETS else target_kind if target_kind in AUTO_TARGETS else None
    if kind in ("reach_maps", "campaign", "stock"):
        target = 1
    rng = TARGET_RANGE.get(kind or "")
    if rng and target:
        target = min(max(float(target), rng[0]), rng[1])
    if kind and kind != "farm" and not target:               # nothing to count to: you tick it
        kind = None
    words = goal_words(kind, target, ref_name) if kind else ""
    text = words or str(text).strip()
    if not text:
        return None
    g = _goal(text, kind, target, ref, ref_name)
    cfg()["goals"].append(g)
    save()
    return g


def use_start_plan():
    """The league start plan: six goals most leagues begin with. Change or remove any after."""
    out = [add_goal(kind=k, target=t, ref_name=r) for k, t, r in START_PLAN]
    return [g for g in out if g]


def start_plan_words():
    return [goal_words(k, t, r) for k, t, r in START_PLAN]


def goal(gid):
    return next((g for g in cfg()["goals"] if g["id"] == gid), None)


def remove_goal(gid):
    f = cfg()
    f["goals"] = [g for g in f["goals"] if g["id"] != gid]
    save()


def move_goal(gid, step):
    gs = cfg()["goals"]
    i = next((n for n, g in enumerate(gs) if g["id"] == gid), None)
    if i is None or not 0 <= i + step < len(gs):
        return False
    gs[i], gs[i + step] = gs[i + step], gs[i]
    save()
    return True


def set_done(gid, done=True):
    g = goal(gid)
    if g:
        g["done"] = bool(done)
        if not done:
            g.pop("auto_done", None)
            g["hold"] = True                                 # you unticked it: the app won't tick it again
        save()
    return g


def skip(gid, now=None):
    """Skip for now: the goal after it is Next up until tomorrow."""
    g = goal(gid)
    if g:
        g["skip_day"] = today(now)
        save()
    return current(now)


def current(now=None):
    """Next up: the first goal not done - past the ones you skipped today, unless that leaves none."""
    open_ = [g for g in cfg()["goals"] if not g["done"]]
    day = today(now)
    return next((g for g in open_ if g.get("skip_day") != day), open_[0] if open_ else None)


def counts():
    gs = cfg()["goals"]
    return sum(1 for g in gs if g["done"]), len(gs)


def goal_target(g):
    """-> (kind, target) of a goal the app counts, or (None, None): one you tick yourself."""
    if not g or g.get("target_kind") not in AUTO_TARGETS:
        return None, None
    if g["target_kind"] == "farm":
        return "farm", float(g.get("target") or 0)
    if not g.get("target"):
        return None, None
    return g["target_kind"], float(g["target"])


def char_level():
    """The level the log last showed for your character: the name typed in Options, else the last one to level."""
    st = state()
    from . import identity as ID                            # 3.3.0: your character - never a party member
    lv = st.get("levels") or {}
    last = st.get("last_char") or ""
    mine = (ID.current() or (last if ID.is_me(last) else "")).lower()
    for who, n in lv.items():
        if who.lower() == mine and mine:
            return n
    return ID.level() or None


def act_now():
    """The act the Campaign Helper last saw you in, 1-4 (an interlude counts as 4), or 0."""
    try:
        from . import campaign as CP
        a = str(CP.char().get("act") or "")
    except Exception:
        return 0
    return int(a) if a.isdigit() else (4 if a.startswith("i") else 0)


def campaign_done():
    try:
        from . import campaign as CP
        if CP.char().get("done"):
            return True
    except Exception:
        pass
    return bool(state()["reached_maps"])


def net_worth():
    """(divines, when) - Wealth's last count for your league, or (None, None)."""
    try:
        from .wealth import WEALTH
        league = SETTINGS.get("league")
        for s in reversed(WEALTH.snapshots):
            if not league or s.get("league") == league:
                return float(s.get("total") or 0), float(s.get("ts") or 0)
    except Exception:
        pass
    return None, None


DIVHOUR_MAPS = 10


def div_hour():
    """(div an hour, maps counted) over your last 10 maps in Map Profit, or (None, 0)."""
    try:
        from . import mapprofit as MP
        es = sorted(MP.log_read(), key=lambda e: e.get("t", 0))[-DIVHOUR_MAPS:]
    except Exception:
        return None, 0
    secs = sum(e.get("secs", 0) for e in es)
    if secs < 60:
        return None, 0
    return sum(e.get("div", 0) for e in es) * 3600 / secs, len(es)


def stock_counts():
    """(bought, planned) - Stockpile items you have enough of, of the ones with a quantity."""
    rows = [r for r in cfg()["stockpile"] if int(r.get("goal") or 0) > 0]
    return sum(1 for r in rows if int(r.get("have") or 0) >= int(r["goal"])), len(rows)


def progress(g, worth=None):
    """(have, target) for a goal the app counts, or None. worth is ignored (kept for older callers)."""
    kind, target = goal_target(g)
    if not kind:
        return None
    st = state()
    if kind == "level":
        have = char_level() or 0
    elif kind == "maps":
        have = st["maps"] - int(g.get("maps_at") or 0)
    elif kind == "reach_maps":
        have = 1 if st["reached_maps"] else 0
    elif kind == "campaign":
        have = 1 if campaign_done() else 0
    elif kind == "act_done":                                 # act N is done once the log shows the one after
        have = target if campaign_done() else min(target, max(0, act_now() - 1))
    elif kind == "tier":
        have = int(st.get("top_tier") or 0)
    elif kind == "boss":
        have = int((st.get("boss_runs") or {}).get(g.get("ref_name") or "", 0)) - int(g.get("runs_at") or 0)
    elif kind == "networth":
        have = net_worth()[0] or 0
    elif kind == "divhour":
        have = div_hour()[0] or 0
    elif kind == "farm":
        have = round(float(g.get("secs") or 0) / 3600, 1)
    elif kind == "stock":
        have, target = stock_counts()
    else:                                                    # act: the furthest the Campaign Helper saw
        have = g["have"] = max(int(g.get("have") or 0), act_now())
    return max(0.0, float(have)), float(target)


def ago(ts, now=None):
    d = max(0, (now or time.time()) - ts)
    if d < 3600:
        return f"{max(1, int(d // 60))} min ago"
    if d < 86400:
        n = int(d // 3600)
        return f"{n} hour{'s' if n != 1 else ''} ago"
    n = int(d // 86400)
    return f"{n} day{'s' if n != 1 else ''} ago"


def num(x):
    """A number as people read it: 8,930 · 6.2 · 0.35 - never 8.93e+03."""
    x = float(x)
    t = f"{x:,.0f}" if abs(x) >= 100 else f"{x:.1f}" if abs(x) >= 1 else f"{x:.2f}"
    return t.rstrip("0").rstrip(".") if "." in t else t


def progress_text(g):
    """ "Level 74 of 90", "6.2 of 10 div", "Not yet" - or "" for a goal you tick."""
    p = progress(g)
    if not p:
        return ""
    kind = goal_target(g)[0]
    h, t = p
    if kind == "level":
        return f"Level {h:g} of {t:g}"
    if kind == "act":
        return f"Act {h:g} of {t:g}"
    if kind == "act_done":
        return f"{h:g} of {t:g} acts done"
    if kind == "reach_maps":
        return "In maps" if h else "Not in maps yet"
    if kind == "campaign":
        return "Done" if h else f"In act {act_now()}" if act_now() else "Not yet"
    if kind == "tier":
        return f"Tier {h:g} of {t:g}" if h else "No map yet"
    if kind == "boss":
        return "Not yet" if not h and t <= 1 else f"{h:g} of {t:g}"
    if kind == "networth":
        return f"{num(h)} of {num(t)} div" if net_worth()[0] is not None else "Nothing counted in Wealth yet"
    if kind == "divhour":
        v, n = div_hour()
        return f"{num(v)} div an hour over your last {n} maps" if v is not None else "No maps in Map Profit yet"
    if kind == "farm":
        return f"{h:g} of {t:g} hours" if t else f"{h:g} hours so far"
    if kind == "stock":
        return f"{h:g} of {t:g} bought" if t else "Nothing on your Stockpile yet"
    return f"{h:g} of {t:g} maps"


def source_text(g):
    """Where a goal's count comes from, in words: "from the game's log", "from Wealth"."""
    kind = goal_target(g)[0]
    if not kind:
        return ""
    if kind == "networth":
        ts = net_worth()[1]
        return f"from Wealth · last read {ago(ts)}" if ts else ""
    if kind == "divhour":
        return "from Map Profit" if div_hour()[0] is not None else ""
    if kind == "stock":
        return ""
    return "from the game's log"


def frac(g):
    p = progress(g)
    return min(1.0, p[0] / p[1]) if p and p[1] else None


def check_goals(now=None):
    """Goals the app counts tick themselves once reached. -> the ones that just did (each gets a reminder when
    Remind me about goals is on)."""
    f, st = cfg(), state()
    done = []
    for g in f["goals"]:
        if g["done"] or g.get("hold"):
            continue
        p = progress(g)
        if p and p[1] and p[0] >= p[1]:
            g["done"], g["auto_done"] = True, True
            done.append(g)
            if f["pokes"].get("milestones"):
                st["pending"].append({"kind": "reached", "goal": g["id"], "at": now or time.time()})
    if done:
        save()
    return done


# ---------------------------------------------------------------- the Stockpile: shown on Exchange Rates
def add_stock(name, goal_qty=0, under=None):
    row = {"name": name.strip(), "goal": int(goal_qty or 0), "under": under, "paid": None, "have": 0}
    f = cfg()
    f["stockpile"].append(row)
    if not any(g.get("target_kind") == "stock" for g in f["goals"]) and not f.get("stock_goal_off"):
        f["goals"].append(_goal(STOCK_TEXT, "stock", 1))   # your plan gets its Stock up goal with the first item
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


NO_GOAL = "No goal yet - click to set one in League Plan"


def line_text(worth=None):
    """The overlay's line: Next up's words and how far along it is, or "" when the plan is off."""
    f = cfg()
    if not f["on"]:
        return "", None
    g = current()
    if not g:
        return NO_GOAL, None
    return g["text"], frac(g)


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
KINDS = {"milestone": "urgent", "reached": "urgent", "price": "normal", "checkin": "normal",
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


TIER1_LEVEL = 65


def _arena(area_id):
    """The pinnacle arena an area id is, by the Map library's name, or None."""
    try:
        from .maplib import display_name, library
        name = display_name(area_id)
        return name if (library().get(name) or {}).get("kind") == "Pinnacle" else None
    except Exception:
        return None


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def log_event(kind, data, area_kind=None, now=None):
    """A game-log event -> may queue an urgent poke. area_kind: the tracker's 'map' / 'town' / 'hideout' / 'other'."""
    f, st = cfg(), state()
    if not f["on"]:
        return None
    now = now or time.time()
    last, st["seen"] = st.get("seen") or 0.0, now          # time played, from the log alone: a Farm a strat goal
    r = current(now)                                       # counts it while it is Next up, overlay or not
    if r is not None and r.get("target_kind") == "farm" and last and 0 < now - last <= PLAYING:
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
                lvl = int(data.get("level") or 0)
                if lvl >= TIER1_LEVEL:                     # a waystone map's tier is its area level - 64
                    st["top_tier"] = max(int(st.get("top_tier") or 0), min(16, lvl - TIER1_LEVEL + 1))
                name = _arena(data.get("area"))
                if name:                                   # a pinnacle fight: one more run of it
                    br = st.setdefault("boss_runs", {})
                    br[name] = int(br.get(name) or 0) + 1
    if kind == "area" and area_kind == "map" and not st["reached_maps"]:
        st["reached_maps"] = True
        if f["pokes"].get("milestones") and current(now):
            st["pending"].append({"kind": "milestone", "id": "maps", "at": now})
        check_goals(now)
        save()
        return "milestone"
    if kind == "area":
        check_goals(now)
        save()
    if kind == "level":
        who, lvl = data.get("who", ""), int(data.get("level") or 0)
        from . import identity as ID
        if not ID.is_me(who):                               # 3.3.0: a party member leveled, not you
            return None
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
    """Next up, when it is time to bring it back: at most every 3 hours, not snoozed or stopped."""
    g = current(now)
    if not g or g.get("stopped") or (g.get("snooze") or 0) > now or state()["notoday"].get(g["id"]) == today(now):
        return []
    return [g] if now - (g.get("poked") or 0) >= 3 * 3600 else []


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
    ask = ASK
    k = poke["kind"]
    snooze = ("snooze", f"Snooze · {int(f['pokes'].get('snooze_min') or 60)} min")
    if k == "nudge":
        g = goal(poke["goal"]) or {"text": "?"}
        pt = progress_text(g)
        mine = [] if goal_target(g)[0] else [("done", "✓ Done")]      # a goal you tick: tick it from here
        return ("NEXT UP", g["text"] + (f"\n{pt}" if pt else ""), "Why now: you're back in town.",
                [("ok", "Got it"), snooze] + mine)
    if k == "reached":
        g = goal(poke.get("goal")) or {"text": "?"}
        return ("GOAL REACHED", f"✓ {g['text']}\n{progress_text(g) or 'Done'}",
                "Why now: the game's log shows you reached it, so it ticked itself.",
                [("plan", "Open League Plan"), ("ok", "Got it")])
    if k == "milestone":
        g = current()
        body = "Your first waystone map." + (f"\nNext up: {g['text']}" if g else "")
        return ("YOU REACHED MAPS", body, "Why now: the log shows you in your first waystone map.",
                [("plan", "Open League Plan"), ("ok", "Got it")])
    if k == "price":
        under = poke.get("under")
        body = f"{poke['name']} is {num(poke['each'])} div" + (f", under your {num(under)}." if under is not None else ".")
        if poke.get("goal"):
            body += f"\nYou have {poke.get('have') if poke.get('have') is not None else '?'} of {poke['goal']}."
        return ("CHEAP NOW - YOUR STOCKPILE", body, "Why now: poe.ninja's price is under the one you set.",
                [("exchange", "Open the exchange"), ("ok", "Not today")])
    if k == "checkin":
        g = goal(poke.get("goal"))
        body = ask + (f"\nNext up: {g['text']}" if g else "")
        hist = [h for h in f["history"] if h["kind"] == "checkin" and h.get("answer")][-5:]
        if hist:
            body += f"\nOn plan {sum(1 for h in hist if h['answer'] == 'ontrack')} of your last {len(hist)} check-ins."
        return ("CHECK-IN", body, f"Why now: {int(f['pokes'].get('checkin_min') or 45)} min of play since the last one.",
                [("ontrack", "On track"), ("sidetracked", "Got sidetracked"), ("break", "Taking a break")])
    return ("", "", "", [("ok", "OK")])
