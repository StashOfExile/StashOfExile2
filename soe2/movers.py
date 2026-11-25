"""Top Movers (3.3.0, Dashboard): what went up and down the most - Daily from poe.ninja's own 7-day line, Hourly
from the prices the app read about an hour before. Reads only what Wealth's price store already holds.

Hourly needs two reads an hour apart, so it shows once the app has been open that long. Thin markets are left out:
only the busier half of what poe.ninja lists counts."""
import time

from . import buglog
from .config import load_json, save_json

FILE = "movers_history.json"          # [{ts, league, v: {id: divines}}], the last few reads
KEEP = 4 * 3600                       # reads older than this are dropped
HOUR_MIN, HOUR_MAX = 45 * 60, 3 * 3600
MIN_PCT = 0.5                         # a move smaller than this is no move
TOP = 5


def _lines(prices):
    """[(id, name, divines, volume)] - everything on the Currency Exchange that poe.ninja prices."""
    from .wealth import NINJA_EXCHANGE_TYPES
    out = []
    for typ in NINJA_EXCHANGE_TYPES:
        for cid, name, _v, vol in (prices.parts.get(typ) or {}).get("lines", []):
            hit = prices.by_slug.get(str(cid).lower())
            if hit and hit[0] > 0:
                out.append((str(cid).lower(), str(name), float(hit[0]), float(vol or 0)))
    return out


def _busy(lines):
    """The busier half by volume: a price two people traded at swings for no reason."""
    vols = sorted(v for _c, _n, _d, v in lines)
    if not vols:
        return []
    cut = vols[len(vols) // 2]
    return [ln for ln in lines if ln[3] >= cut and ln[3] > 0]


def note(prices, now=None):
    """After a fresh read from poe.ninja: keep its prices for Hourly. Never raises."""
    try:
        if not getattr(prices, "ok", False) or not prices.league:
            return
        now = now or time.time()
        hist = [h for h in load_json(FILE, []) if isinstance(h, dict) and h.get("league") == prices.league
                and now - float(h.get("ts") or 0) < KEEP]
        if hist and now - float(hist[-1]["ts"]) < 20 * 60:       # two reads close together are one
            return
        hist.append({"ts": now, "league": prices.league, "v": {c: round(d, 8) for c, _n, d, _v in _lines(prices)}})
        save_json(FILE, hist[-6:])
    except Exception:
        buglog.caught()


def _rank(rows):
    up = sorted((r for r in rows if r["pct"] >= MIN_PCT), key=lambda r: -r["pct"])[:TOP]
    down = sorted((r for r in rows if r["pct"] <= -MIN_PCT), key=lambda r: r["pct"])[:TOP]
    return up, down


def _g(x):
    return f"{x:,.0f}" if x >= 100 else f"{x:.2f}".rstrip("0").rstrip(".") if x >= 1 else f"{x:.3g}"


def daily(prices):
    """-> {"up": [row], "down": [row], "empty": why or ""} - row: name, div, pct, how."""
    rows = []
    for cid, name, div, _vol in _busy(_lines(prices)):
        t = prices.trend_by_slug.get(cid)
        pts = [p for p in (t[1] if t else []) if p is not None]
        if len(pts) < 2 or pts[-2] <= -100:
            continue
        pct = ((1 + pts[-1] / 100.0) / (1 + pts[-2] / 100.0) - 1) * 100.0
        was = div / (1 + pct / 100.0) if pct > -100 else 0
        rows.append({"name": name, "div": div, "pct": pct,
                     "how": f"poe.ninja's price yesterday against today: {_g(was)} to {_g(div)} div."})
    up, down = _rank(rows)
    return {"up": up, "down": down, "empty": "" if up or down else "No prices from poe.ninja yet."}


def hourly(prices, now=None):
    now = now or time.time()
    hist = [h for h in load_json(FILE, []) if isinstance(h, dict) and h.get("league") == prices.league
            and HOUR_MIN <= now - float(h.get("ts") or 0) <= HOUR_MAX]
    if not hist or not getattr(prices, "ts", 0) or now - prices.ts > 2 * 3600:
        return {"up": [], "down": [], "empty": "Hourly shows after the app has been open for an hour."}
    old = hist[-1]                                               # the newest read that is old enough
    mins = int((prices.ts - float(old["ts"])) // 60)
    if mins < HOUR_MIN // 60:
        return {"up": [], "down": [], "empty": "Hourly shows after the app has been open for an hour."}
    rows = []
    for cid, name, div, _vol in _busy(_lines(prices)):
        was = (old.get("v") or {}).get(cid)
        if not was or was <= 0:
            continue
        pct = (div / was - 1) * 100.0
        rows.append({"name": name, "div": div, "pct": pct,
                     "how": f"The app's read {mins} min ago against now: {_g(was)} to {_g(div)} div."})
    up, down = _rank(rows)
    return {"up": up, "down": down, "empty": "" if up or down else "Nothing moved in the last hour."}
