"""2.72.1: stackable items poe.ninja doesn't list, priced from the trade site's bulk exchange - the same "I have /
I want" search the site's own Bulk Item Exchange page runs. One search per item (rate-limited like every other
trade-site request, its own "exchange" limits), the answer kept an hour (bulk_prices.json). Nothing is bought or
sent to the game: it only reads the offers.

How a price is read: the offers that sell the item for Divine Orbs (then, if too few, for Exalted Orbs), cheapest
first; each offer's price per item is what it asks / how many it gives. The median of the cheapest five (an offer
far from the rest - a price-fixer - is left out first, like the price checker does) is the price, in divines."""
import statistics
import time

from . import buglog
from .config import BASE, load_json, save_json
from .net import call

FILE = "bulk_prices.json"          # {league: {exchange id: [divines each, ts, offers, currency]}} - divines None (3.0.4):
                                   # asked, too few offers (kept like a price, so a restart doesn't ask again at once)
MAX_AGE = 3600
MIN_OFFERS = 3
HAVE = ("chaos", "divine")
# 3.0.6 (a user's 17 Greater Essence of Battle at 12 div each - 6 sell for 1 chaos; owner: "check the div price and
# chaos price and go with the lower cost one" - on a slim market someone lists an item that isn't sold for divines at an
# absurd divine price): both are asked, each needs MIN_OFFERS offers, and the cheaper one (in divines) is the price.


def ids_from_static(static):
    """The trade site's /data/static answer -> {name (lower case): exchange id} for every item the bulk exchange
    knows (currency, fragments, essences, runes, omens ...)."""
    out = {}
    for group in (static or {}).get("result") or []:
        for e in group.get("entries") or []:
            if e.get("text") and e.get("id"):
                out.setdefault(str(e["text"]).strip().lower(), str(e["id"]))
    return out


_IDS = {"at": -1, "ids": {}}


def exchange_id(name, static=None):
    """The bulk exchange's id for an item name (from the trade site's list, downloaded once a day), or None."""
    if static is not None:
        return ids_from_static(static).get((name or "").strip().lower())
    import os
    from .config import P
    try:
        at = os.path.getmtime(P("trade_static.json"))
    except OSError:
        at = 0
    if at != _IDS["at"]:
        _IDS.update(at=at, ids=ids_from_static(load_json("trade_static.json", {})))
    return _IDS["ids"].get((name or "").strip().lower())


def _cache():
    d = load_json(FILE, {})
    return d if isinstance(d, dict) else {}


def cached(league, xid, max_age=MAX_AGE):
    """-> (divines each, offers, currency) from the last hour, or None."""
    hit = _cache().get(league, {}).get(xid)
    if hit and hit[0] is not None and time.time() - hit[1] < max_age and (hit[2] or 0) >= MIN_OFFERS:
        return hit[0], hit[2], hit[3] if len(hit) > 3 else "divine"
    return None                                     # (3.0.6: a price from fewer than MIN_OFFERS offers isn't one)


def missed(league, xid, max_age=MAX_AGE * 6):
    """3.0.4: asked within max_age and the exchange had too few offers -> True."""
    hit = _cache().get(league, {}).get(xid)
    return bool(hit and (hit[0] is None or (hit[2] or 0) < MIN_OFFERS) and time.time() - hit[1] < max_age)


def per_unit(result):
    """The exchange search's "result" -> [price per item in the currency asked for], cheapest first."""
    out = []
    for lst in (result or {}).values() if isinstance(result, dict) else result or []:
        for off in ((lst or {}).get("listing") or {}).get("offers") or []:
            try:
                pay, give = float(off["exchange"]["amount"]), float(off["item"]["amount"])
                if give > 0 and pay > 0 and (off["item"].get("stock") or give) >= give:
                    out.append(pay / give)
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(out)


def robust(prices):
    """The median of the cheapest five, after leaving out ones far below / above the rest."""
    five = prices[:5]
    if not five:
        return None
    med = statistics.median(five)
    kept = [p for p in five if med / 5 <= p <= med * 5] or five
    return statistics.median(kept)


def search(league, xid, have, call_=None):
    """One bulk-exchange search: offers selling `xid` for `have`. -> [price per item], cheapest first."""
    body = {"query": {"status": {"option": "online"}, "have": [have], "want": [xid]},
            "sort": {"have": "asc"}, "engine": "new"}
    res = (call_ or call)("POST", f"{BASE}/exchange/poe2/{league}", json=body)
    return per_unit(res.get("result"))


def price(league, xid, to_div, call_=None):
    """-> (divines each, offers, currency) - from the last hour's answer, or one or two new searches; None when the
    exchange has too few offers. to_div(amount, currency) converts (rates.RATES.to_div)."""
    hit = cached(league, xid)
    if hit:
        return hit
    if missed(league, xid, MAX_AGE):
        return None
    best = None
    for have in HAVE:
        prices = search(league, xid, have, call_)
        p = robust(prices)
        if p is None or len(prices) < MIN_OFFERS:
            continue                                # (too few offers in this currency: one seller isn't a price)
        d = p if have == "divine" else to_div(p, have)
        if d is not None and (best is None or d < best[0]):
            best = (d, len(prices), have)          # the cheaper of the chaos and the divine price
    c = _cache()
    if best is None:
        c.setdefault(league, {})[xid] = [None, time.time(), 0, None]
        save_json(FILE, c)
        return None
    c.setdefault(league, {})[xid] = [best[0], time.time(), best[1], best[2]]
    save_json(FILE, c)
    return best


def text(hit):
    if not hit:
        return ""
    d, n, cur = hit
    return f"bulk exchange ({n} offer{'s' if n != 1 else ''} in {cur})"


def catalog(static=None):
    """2.73.4: everything the Currency Exchange trades, by group -> [(group, [names])] in the trade site's order
    (Currency, Fragments, Essences, Runes, Omens ...), from its /data/static list (downloaded once a day). Before
    that list is here: the names poe.ninja's exchange prices have (your league), else []."""
    if static is None:
        static = load_json("trade_static.json", {})
    out = []
    for group in (static or {}).get("result") or []:
        names, seen = [], set()
        for e in group.get("entries") or []:
            t = str(e.get("text") or "").strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                names.append(t)
        if names:
            out.append((str(group.get("label") or group.get("id") or "Other"), names))
    if out:
        return out
    try:
        from .wealth import NINJA_EXCHANGE_TYPES, WPRICES
        if WPRICES.for_league():
            for typ in NINJA_EXCHANGE_TYPES:
                names = sorted({ln[1] for ln in (WPRICES.parts.get(typ) or {}).get("lines") or [] if ln[1]})
                if names:
                    out.append((typ, names))
    except Exception:
        buglog.caught()
    return out
