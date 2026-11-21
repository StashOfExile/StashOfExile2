"""2.86.0: Global leaderboards - your best times, from the game's log, and everyone's (opt-in).

Four boards:
  * Campaign - each act's split and the whole campaign (the Campaign Helper's act times; the total once every act of
    the guide pack has one).
  * Campaign zones (2.124.0) - each campaign zone, from entering it to leaving it, by the zone's name.
  * Maps - fastest clear per map (time inside the map; maps, towers, unique maps, citadels).
  * Bosses & pinnacles - the Map library's pinnacle fights.
  * Trials - Trial of the Sekhemas, Trial of Chaos (and other trial areas the tracker learns); pinnacle fights such
    as Simulacrum of Delusion are on Bosses & pinnacles.
Mine is worked out on this PC. Everyone comes from the community board: with Community data sharing on, each
account's 10 fastest runs per board / league / class are sent (3.0.6; the board lists the best first, the rest under it) (its community name, never an account or character name). Times are
self-reported (from the log), so the board refuses impossible ones and reports / reviewers / admins can hide entries.
GGG ToS: reads Client.txt only; nothing is sent to the game."""
import re
import time

from .config import SETTINGS

CATS = (("campaign", "Campaign"), ("zone", "Campaign zones"), ("map", "Maps"), ("boss", "Bosses & pinnacles"),
        ("trial", "Trials"))
TOTAL = "Whole campaign"
# the fastest a time can honestly be (seconds) - the board checks the same
FLOOR = {"campaign": 120, "zone": 10, "map": 30, "boss": 10, "trial": 60}
CEIL = {"campaign": 48 * 3600, "zone": 3 * 3600, "map": 3 * 3600, "boss": 3600, "trial": 3 * 3600}
TRIAL = re.compile(r"trial|sekhema|simulacrum|sanctum|ultimatum|chaos", re.I)
SEND_EVERY = 15 * 60
PER_PLAYER = 10                                # 3.0.6: each player's fastest runs kept per board entry (key / league / class)
SEND_CAP = 400


def cat_of(name):
    """A map-run name -> "map", "boss" or "trial" (the Map library's kind; trials by name)."""
    from .maplib import library
    e = library().get(name) or {}
    kind = e.get("kind")
    ids = " ".join(e.get("ids") or [])
    if kind == "Pinnacle":                     # 2.87.0 (feedback): first - Simulacrum of Delusion is a pinnacle fight
        return "boss"
    if TRIAL.search(name or "") or TRIAL.search(ids):
        return "trial"
    return "map"


def classes():
    """Character -> class / ascendancy, as the log said at a level-up."""
    from . import focus as F
    return dict((F.cfg().get("state") or {}).get("classes") or {})


def learn_classes(path, max_bytes=64 * 1024 * 1024):
    """2.87.0 (feedback: no way to read the class): the game's log says it at every level-up
    ("ExampleWitch (Invoker) is now level 24"); the overlay only noted it from 2.86.0 on. Read the last part of Client.txt
    (64 MB at most) for each character's newest class. -> {character: class} (also saved). Thread-safe (no Tk)."""
    import os
    from .gamelog import parse
    from . import focus as F
    found = {}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            for raw in f:
                if b"is now level" not in raw:
                    continue
                ev = parse(raw.decode("utf-8", "replace"))
                if ev and ev[0] == "level" and ev[2].get("cls"):
                    found[ev[2]["who"]] = ev[2]["cls"]
    except OSError:
        return {}
    if found:
        st = F.cfg().setdefault("state", {})
        cl = st.setdefault("classes", {})
        for who, c in found.items():
            cl.setdefault(who, c)
    return found


def rebuild_campaign(path):
    """3.0.6: the campaign's act and zone times from the game's log (Campaign Helper rules, replayed into a throwaway
    run) -> [run]; also learns the classes. Reads Client.txt only. Thread-safe (no Tk); merge with
    campaign.merge_rebuilt on the window thread."""
    from . import campaign as CP
    runs = CP.rebuild_from_log(path)
    learn_classes(path)
    return runs


def best(entries):
    """[(cat, key, secs, ...)] -> only the fastest per (cat, key, league, class)."""
    out = {}
    for e in entries:
        k = (e["cat"], e["key"], e["league"], e.get("cls") or "")
        if k not in out or e["secs"] < out[k]["secs"]:
            out[k] = e
    return sorted(out.values(), key=lambda e: (e["cat"], e["key"], e["secs"]))


def top_runs(entries, per=PER_PLAYER):
    """3.0.6: the `per` fastest runs per (cat, key, league, class), fastest first overall. Identical runs (same time,
    same day) count once - the same run is never listed twice."""
    groups, seen = {}, set()
    for e in sorted(entries, key=lambda e: (e["secs"], e.get("at") or 0)):
        k = (e["cat"], e["key"], e["league"], e.get("cls") or "")
        day = int(e.get("at") or 0) // 86400
        if (k, e["secs"], day) in seen:
            continue
        seen.add((k, e["secs"], day))
        g = groups.setdefault(k, [])
        if len(g) < per:
            g.append(e)
    return sorted((e for g in groups.values() for e in g), key=lambda e: (e["cat"], e["key"], e["secs"]))


def map_entries(sessions, current=None, now=None):
    """Every counted run in the tracker's sessions -> entries {cat, key, secs, league, cls, char, level, deaths, at}.
    Sessions from before 2.86.0 don't know their league and are left out."""
    from .tracker import MIN_RUN_SECS
    cls = classes()
    pool = list(sessions) + ([current] if current is not None and current not in sessions else [])
    out = []
    for s in pool:
        league = getattr(s, "league", None)
        if not league:
            continue
        live = s.where.get("map") if (s.ended is None and s.where) else None
        for i, m in enumerate(s.maps):
            if live == i:
                continue                                   # still running: not a clear yet
            t = m.get("time")
            if not t or t < MIN_RUN_SECS:
                continue
            cat = cat_of(m["name"])
            if not FLOOR[cat] <= t <= CEIL[cat]:
                continue
            ch = m.get("char") or getattr(s, "char", "") or ""
            out.append({"cat": cat, "key": m["name"], "secs": round(float(t), 1), "league": league,
                        "cls": cls.get(ch, ""), "char": ch, "level": m.get("level") or 0,
                        "deaths": int(m.get("deaths") or 0), "at": int(m.get("first") or s.started)})
    return out


def _run_cls(ch, run, cls):
    """The class of a campaign run: its character's, as the log said at a level-up. A run that never learned its
    character's name takes your character's class, never the last one to level up: in a party that can be a party
    member's. Your character is the name typed in Options, else the one the Session timer worked out from deaths,
    else the only character the log has shown. Otherwise the class stays empty."""
    c = cls.get(run.get("char") or ch, "")
    if c or ch or run.get("char"):
        return c
    tr = SETTINGS.get("tracker") or {}
    low = {k.lower(): v for k, v in cls.items()}
    for who in (tr.get("character"), tr.get("character_guess")):
        if (who or "").strip().lower() in low:
            return low[who.strip().lower()]
    return list(cls.values())[0] if len(cls) == 1 else ""


def _stamp(run):
    """A stable day for times saved before 3.0.6 knew when they were set (a changing one would list one time again
    every day)."""
    if not run.get("stamp"):
        run["stamp"] = int(time.time())
    return run["stamp"]


def campaign_entries():
    """Each character's act splits (and the whole campaign, once every act has a time). 3.0.6: not tied to the
    character's name - a run with no name is sent too (the board keys it by your community name); the league is the
    run's (else the current one), the class whatever is known; the bests rebuilt from the log (best_secs, best_total)
    count too."""
    from . import campaign as CP
    cls = classes()
    acts = CP.acts()
    names = {a["key"]: a.get("name") or a["key"] for a in acts}
    out = []
    for ch, run in (CP.cfg().get("chars") or {}).items():
        league = run.get("league") or SETTINGS.get("league")
        if not league:
            continue
        own = run.get("secs") if isinstance(run.get("secs"), dict) else {}
        # (the act you're in isn't finished - unless the whole run is done)
        secs = {k: v for k, v in own.items() if isinstance(v, (int, float)) and v > 0
                and (run.get("done") or k != run.get("act") or k in (run.get("closed") or []))}
        at = run.get("secs_at") or {}
        best_at = run.get("best_at") or {}
        c = _run_cls(ch, run, cls)
        fast = {k: (v, at.get(k) or _stamp(run)) for k, v in secs.items()}
        for k, v in (run.get("best_secs") or {}).items():
            if isinstance(v, (int, float)) and v > 0 and (k not in fast or v < fast[k][0]):
                fast[k] = (v, best_at.get(k) or _stamp(run))
        for k, (v, when) in fast.items():
            if FLOOR["campaign"] <= v <= CEIL["campaign"] and k in names:
                out.append({"cat": "campaign", "key": names[k], "secs": round(float(v), 1), "league": league,
                            "cls": c, "char": ch, "level": 0, "deaths": 0, "at": int(when)})
        totals = []
        if acts and run.get("done") and all(a["key"] in secs for a in acts):
            totals.append((sum(secs[a["key"]] for a in acts), max([at.get(a["key"]) or 0 for a in acts]) or _stamp(run)))
        if run.get("best_total"):
            totals.append((run["best_total"], run.get("best_total_at") or _stamp(run)))
        for tot, when in totals:
            out.append({"cat": "campaign", "key": TOTAL, "secs": round(float(tot), 1), "league": league,
                        "cls": c, "char": ch, "level": 0, "deaths": 0, "at": int(when)})
    return out


def zone_entries():
    """2.124.0: each character's best time in each campaign zone (entering it to leaving it, AFK left out)."""
    from . import campaign as CP
    cls = classes()
    out = []
    for ch, run in (CP.cfg().get("chars") or {}).items():
        league = run.get("league") or SETTINGS.get("league")
        if not league:
            continue
        c = _run_cls(ch, run, cls)
        zat = run.get("zone_at") or {}
        for zone, secs in (run.get("zone_best") or {}).items():
            if isinstance(secs, (int, float)) and FLOOR["zone"] <= secs <= CEIL["zone"]:
                out.append({"cat": "zone", "key": str(zone)[:80], "secs": round(float(secs), 1), "league": league,
                            "cls": c, "char": ch, "level": 0, "deaths": 0, "at": int(zat.get(zone) or _stamp(run))})
    return out


def mine(sessions, current=None):
    return map_entries(sessions, current) + campaign_entries() + zone_entries()


def keys_of(entries, cat, league=None, cls=None):
    """[(key, my best secs, runs)] for one board - the list on the left."""
    agg = {}
    for e in entries:
        if e["cat"] != cat or (league and e["league"] != league) or (cls and e.get("cls") != cls):
            continue
        a = agg.setdefault(e["key"], [None, 0])
        a[0] = e["secs"] if a[0] is None else min(a[0], e["secs"])
        a[1] += 1
    order = {}
    if cat == "campaign":
        from . import campaign as CP
        order = {a.get("name") or a["key"]: i for i, a in enumerate(CP.acts())}
        order[TOTAL] = -1
    return sorted(((k, v[0], v[1]) for k, v in agg.items()), key=lambda r: (order.get(r[0], 999), r[0].lower()))


def payload(entries):
    """What goes to the board: each player's fastest runs (10) per board / key / league / class, no character names,
    only the day. At most 400 per send, filled fastest-first across keys: every key gets its best before any key gets
    its 2nd, and so on."""
    from .privacy import is_private_league                 # 2.89.3: private leagues stay off the board; only the day
    pool = [e for e in entries if not is_private_league(e.get("league"))]
    ranked = {}                                            # (cat, key, league, cls) -> its runs, fastest first
    for e in top_runs(pool):
        ranked.setdefault((e["cat"], e["key"], e["league"], e.get("cls") or ""), []).append(e)
    out = []
    for rank in range(PER_PLAYER):                         # round r: every key's r-th fastest
        for k in sorted(ranked):
            if rank < len(ranked[k]):
                e = ranked[k][rank]
                d = {f: e[f] for f in ("cat", "key", "secs", "league", "cls", "level", "deaths", "at")}
                d["at"] = int(d.get("at") or 0) // 86400 * 86400
                out.append(d)
        if len(out) >= SEND_CAP:
            break
    return out[:SEND_CAP]


def level_text(level):
    """The Area level column: the map's area level, "-" where there is none (campaign and zone rows are 0)."""
    return str(int(level)) if level and int(level) > 0 else "-"


def fmt(secs):
    if secs is None:
        return "-"
    s = int(round(secs))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def sharing_on():
    from . import communitymods as CM
    return CM.sharing() and SETTINGS.get("lb_share", True)
