"""Boss Ledger - the numbers behind it (3.3.0, a start: no page yet, nothing in the app calls this).

Per pinnacle arena: how many runs, the fastest, the usual time, deaths, runs without a death and the last run - all
from the runs the Session timer already counted (leaderboard.map_entries), so nothing new is read from the game or
its log. Chase drops are yours to log: "the Voices jewel on run 650" is the run count at the moment you logged it.

Ideas credit: Solo Self Tracking (github.com/ggw1776/SoloSelfTracking, MIT) tracks runs and drops per kind of content;
no code or data of it is used here.

A run is a run, not a kill: the game's log names the arena you entered, never the kill (focus.py says the same of
its boss goal). The page must say "runs".

GGG ToS: reads nothing by itself. All of it stays on this PC (boss_ledger.json)."""
import time

from .config import load_json, save_json

FILE = "boss_ledger.json"


def arenas():
    """[arena] - the pinnacle fights the Map Library knows, by name."""
    from .maplib import library
    return sorted(n for n, e in library().items() if (e or {}).get("kind") == "Pinnacle")


def boss_of(arena):
    """Who you fight there, when the app knows it by name - else the arena's own name."""
    from .focus import BOSS_OF
    who = BOSS_OF.get(arena)
    return (who[4:] if who.startswith("the ") else who) if who else arena


def stats(entries, league=None):
    """entries: leaderboard.map_entries(...) -> {arena: {"runs", "best", "usual", "deaths", "clean", "last"}} for
    the boss runs in them (one league, or all). usual: the middle run time. clean: runs without a death."""
    out = {}
    for e in entries:
        if e.get("cat") != "boss" or (league and e.get("league") != league):
            continue
        out.setdefault(e["key"], []).append(e)
    done = {}
    for arena, runs in out.items():
        secs = sorted(r["secs"] for r in runs)
        n = len(secs)
        mid = secs[n // 2] if n % 2 else (secs[n // 2 - 1] + secs[n // 2]) / 2
        done[arena] = {"runs": n, "best": secs[0], "usual": round(mid, 1),
                       "deaths": sum(int(r.get("deaths") or 0) for r in runs),
                       "clean": sum(1 for r in runs if not r.get("deaths")),
                       "last": max(int(r.get("at") or 0) for r in runs)}
    return done


def rows(entries, league=None):
    """Every arena the Map Library knows, run or not -> [{"arena", "boss", "runs", ...stats, "drops": [..]}],
    the ones you ran first, most runs first."""
    st, logged = stats(entries, league), drops()
    out = []
    for arena in sorted(set(arenas()) | set(st)):
        s = st.get(arena) or {"runs": 0, "best": None, "usual": None, "deaths": 0, "clean": 0, "last": 0}
        out.append(dict(s, arena=arena, boss=boss_of(arena),
                        drops=[d for d in logged if d.get("arena") == arena and (not league or d.get("league") == league)]))
    out.sort(key=lambda r: (-r["runs"], r["arena"]))
    return out


# ---------------------------------------------------------------- chase drops: logged by you
def drops():
    d = load_json(FILE, {})
    got = d.get("drops") if isinstance(d, dict) else None
    return [x for x in got if isinstance(x, dict) and x.get("arena") and x.get("item")] if isinstance(got, list) else []


def log_drop(arena, item, run_no, league="", now=None):
    """You say an item dropped there: kept with the run it was (your run count at that moment). -> the entry."""
    entry = {"arena": str(arena), "item": str(item).strip()[:80], "run": max(0, int(run_no or 0)),
             "league": str(league or ""), "at": int(now or time.time())}
    if not entry["item"]:
        return None
    all_ = drops() + [entry]
    save_json(FILE, {"v": 1, "drops": all_})
    return entry


def forget_drop(entry):
    """Take one logged drop out again. -> True when it was there."""
    all_ = drops()
    if entry not in all_:
        return False
    all_.remove(entry)
    save_json(FILE, {"v": 1, "drops": all_})
    return True


def drop_words(d):
    """"Voices on run 650" - how a logged drop reads."""
    return f"{d['item']} on run {d['run']:,}" if d.get("run") else str(d["item"])


def runs_between(d, earlier=None):
    """How many runs a drop took since the one before it in the same arena (or since the first run)."""
    return max(0, int(d.get("run") or 0) - int((earlier or {}).get("run") or 0))
