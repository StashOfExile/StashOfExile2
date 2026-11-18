"""The Currency Exchange's item list (catalog): what the trade site's /data/static lists by group (Currency, Fragments,
Essences, Runes, Omens ...), for the pickers (Stockpile). Names only - no prices.
3.0.6 (owner: "I don't think the bulk exchange is a valid method of checking any prices, the data and pricing there is
player set ... that skews our pricing data too much"): this file used to price items poe.ninja doesn't list from the
trade site's bulk exchange. That is gone; the only price source is poe.ninja."""
from . import buglog
from .config import load_json


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
