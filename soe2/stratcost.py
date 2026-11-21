"""What a strat costs today (2.46.0). A strat that lists its items (the waystone it runs, its tablets - with the mods
that matter, "key_mods") gets one trade-site search per item, at most once a day: base type + those mods, cheapest
first, the cheapest real offer (trade.cheapest_real) in divines. Results in strat_costs.json; Money Makers shows
"Cost now" next to the strat's own estimate.

Engine jobs (mixed into Engine: the same thread and trade-site limits as every other search). Only searches and
reads listings - never buys, whispers or lists anything (TOS.md)."""
import re
import time

import requests

from .config import BASE, STATUS_OPTIONS, SETTINGS, load_json, save_json
from .net import call

FILE = "strat_costs.json"
EVERY = 24 * 3600
PRIO = 6                     # behind your own price checks


def costs():
    d = load_json(FILE, {})
    return d if isinstance(d, dict) else {}


def save_costs(d):
    save_json(FILE, d)


def due(s, all_costs, league, now=None):
    """Has this strat's cost not been checked in this league for a day?"""
    if not s.get("items"):
        return False
    c = all_costs.get(s.get("id")) or {}
    return c.get("league") != league or (now or time.time()) - (c.get("at") or 0) > EVERY


def query(item):
    """One item of a strat -> a trade search: its base type, its key mods (those the app knows), cheapest first."""
    from .moneymakers import _num, stat_id, value_range, waystone_maxes, waystone_props
    st = dict(STATUS_OPTIONS).get(SETTINGS.get("status"), "securable")
    q = {"query": {"status": {"option": st}, "type": item["base"]}, "sort": {"price": "asc"}}
    if str(item.get("rarity") or "").lower() == "unique" and item.get("name"):
        q["query"]["name"] = item["name"]                   # 3.0.6: a unique tablet - by its name
        return q, 0, 0
    wp = waystone_props(item)                               # 3.0.6: a waystone - its tier and numbers, as
    if wp is not None:                                      # Endgame filters with your Min and Max
        tier, props = wp
        his = waystone_maxes(item)
        mp = {fid: value_range(v, his.get(fid)) for fid, _ro, v in props}
        if tier:
            mp["map_tier"] = {"min": tier, "max": tier}
        if mp:
            q["query"]["filters"] = {"map_filters": {"filters": mp}}
        return q, len(props), len(item.get("key_mods") or [])
    flt, his = [], item.get("key_max") or {}
    for line in item.get("key_mods") or []:
        sid = stat_id(line)
        if not sid or any(f["id"] == sid for f in flt):
            continue
        f = {"id": sid}
        if his.get(line) is not None:                       # a Max you set: sent with the line's own number as Min
            n = re.search(r"[-+]?\d+(?:\.\d+)?", str(line))
            f["value"] = value_range(_num(n.group(0)) if n else None, his[line])
        flt.append(f)
    ids = [f["id"] for f in flt]
    if flt:
        q["query"]["stats"] = [{"type": "and", "filters": flt}]
    return q, len(ids), len(item.get("key_mods") or [])


class StratCostJobs:
    def strat_cost_start(self, s, league):
        """Queue one strat's items (from the Money Makers window)."""
        for i, it in enumerate(s.get("items") or []):
            if it.get("base"):
                self.add(PRIO, "strat_cost", s["id"], i, dict(it), league)
        self.add(PRIO + 0.5, "strat_cost_done", s["id"], league)

    def do_strat_cost(self, sid, i, item, league):
        from .trade import cheapest_real
        q, known, wanted = query(item)
        res = call("POST", f"{BASE}/search/poe2/{requests.utils.quote(league)}", json=q)
        ids = list(res.get("result") or [])[:10]
        prices = []
        if ids:
            got = call("GET", f"{BASE}/fetch/{','.join(ids)}", params={"query": res.get("id")})
            seen = set()
            for e in got.get("result") or []:
                lst = (e or {}).get("listing") or {}
                p = lst.get("price") or {}
                who = str((lst.get("account") or {}).get("name") or "").lower()
                if who and who in seen:                   # 2.113.0 (core): one price per seller - their cheapest
                    continue
                seen.add(who) if who else None
                if p.get("amount") is not None and p.get("currency"):
                    prices.append((p["amount"], p["currency"]))
        price = cheapest_real(prices, league) if prices else None
        self.ui_q.put(("strat_cost", sid, i, price, {"listings": int(res.get("total") or 0), "mods_known": known,
                                                     "mods_wanted": wanted}))

    def do_strat_cost_done(self, sid, league):
        self.ui_q.put(("strat_cost_finished", sid, league))
