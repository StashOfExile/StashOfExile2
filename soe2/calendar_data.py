"""3.3.0 owner: Calendar, a child of Dashboard. Leagues, Twitch Drops, events and races from the community board,
plus reminders of your own. This file is the data and the sums; calendar_page.py draws it.

An event: {"id", "kind", "name", "start", "end", "link", "by", "note", "remind"}
  kind    one of KINDS. Every kind has a mark and a word: never told apart by color alone.
  start   when it begins, seconds since 1970. end is 0 when nobody set one.
  by      who posted it: "Official" for a board event, "Me" for one of yours.
  remind  how long before the start to say so, in seconds; 0 is at the start. Kept on this PC for every event.

Yours stay on this PC in calendar.json and are never sent anywhere. Board events are posted by admins only.
GGG policy: nothing is read from the game and no keys are sent; a reminder is an alert card, like the helpers."""
import calendar as _cal
import datetime as _dt
import time

from .config import load_json, save_json

FILE = "calendar.json"
KINDS = {                      # kind: its mark, its word, the theme color it is drawn in
    "league": ("◆", "League", "orange"),
    "drops": ("▶", "Twitch Drops", "purple"),
    "event": ("★", "Event", "blue"),
    "race": ("⚑", "Race", "green"),
    "mine": ("●", "Mine", "text"),
}
ORDER = ("league", "drops", "event", "race", "mine")
FILTER_WORDS = {"league": "Leagues", "drops": "Twitch Drops", "event": "Events", "race": "Races", "mine": "Mine"}
LEADS = (("At the start", 0), ("1 hour before", 3600), ("1 day before", 86400), ("1 week before", 7 * 86400))
LEAD_WORDS = {secs: words for words, secs in LEADS}
DAY = 86400
NAME_MAX = 60
_STATE = None


def state():
    """What this PC keeps: your own events, the board's last list, and the reminders you set."""
    global _STATE
    if _STATE is None:
        d = load_json(FILE, {})
        if not isinstance(d, dict):
            d = {}
        d.setdefault("mine", [])
        d.setdefault("board", [])
        d.setdefault("remind", {})       # event id -> [seconds before the start]
        d.setdefault("told", {})         # "id:lead" -> when it was said, so one reminder is said once
        d.setdefault("seq", 0)
        _STATE = d
    return _STATE


def save():
    return save_json(FILE, state())


def reset(data=None):
    """Tests: start from this."""
    global _STATE
    _STATE = None if data is None else data
    if data is not None:
        for k, v in (("mine", []), ("board", []), ("remind", {}), ("told", {}), ("seq", 0)):
            data.setdefault(k, v)


def mark(kind):
    return KINDS.get(kind, KINDS["event"])[0]


def word(kind):
    return KINDS.get(kind, KINDS["event"])[1]


def label(ev):
    """'◆ League': the mark and the word, together everywhere."""
    return f"{mark(ev.get('kind'))} {word(ev.get('kind'))}"


def reminders(ev):
    return sorted({int(s) for s in state()["remind"].get(str(ev.get("id")), [])}, reverse=True)


def set_reminders(eid, leads):
    leads = sorted({int(s) for s in leads if int(s) >= 0}, reverse=True)
    if leads:
        state()["remind"][str(eid)] = leads
    else:
        state()["remind"].pop(str(eid), None)
    save()


def events():
    """Every event this PC knows, the board's and yours, earliest first."""
    st = state()
    out = [dict(e, by=e.get("by") or "Official") for e in st["board"] if _ok(e)]
    out += [dict(e, kind="mine", by="Me") for e in st["mine"] if _ok(e)]
    return sorted(out, key=lambda e: (e["start"], e.get("name", "")))


def _ok(e):
    return isinstance(e, dict) and e.get("id") and isinstance(e.get("start"), (int, float)) and e.get("name")


def add_mine(name, start, end=0, note="", leads=(0,)):
    """-> the new event, or a line saying what is wrong with it."""
    from . import cleantext
    name = " ".join(str(name or "").split())[:NAME_MAX]
    if not name:
        return "It needs a name."
    if cleantext.problem(name):
        return "That name is not allowed."
    if end and end < start:
        return "It ends before it starts."
    st = state()
    st["seq"] = int(st.get("seq", 0)) + 1
    ev = {"id": f"m{st['seq']}", "kind": "mine", "name": name, "start": float(start), "end": float(end or 0),
          "note": str(note or "")[:400], "link": ""}
    st["mine"].append(ev)
    set_reminders(ev["id"], leads)
    return ev


def remove_mine(eid):
    """-> the event taken out, for Undo, or None."""
    st = state()
    for i, e in enumerate(st["mine"]):
        if e.get("id") == eid:
            st["mine"].pop(i)
            leads = st["remind"].pop(str(eid), [])
            save()
            return dict(e, _leads=leads)
    return None


def restore_mine(ev):
    ev = dict(ev)
    leads = ev.pop("_leads", [])
    state()["mine"].append(ev)
    set_reminders(ev["id"], leads)


def is_mine(ev):
    return bool(ev) and ev.get("kind") == "mine"


def set_board(rows):
    """The board's list replaces the last one. Reminders for an event that is gone are dropped."""
    st = state()
    st["board"] = [dict(e) for e in rows if _ok(e) and e.get("kind") in KINDS and e.get("kind") != "mine"]
    keep = {str(e["id"]) for e in st["board"]} | {str(e["id"]) for e in st["mine"]}
    st["remind"] = {k: v for k, v in st["remind"].items() if k in keep}
    save()


# ---------------------------------------------------------------- days and words
def local_day(ts):
    return _dt.datetime.fromtimestamp(ts).date()


def span(ev):
    """The first and last day it is on, in this PC's time."""
    a = local_day(ev["start"])
    b = local_day(ev["end"]) if ev.get("end") and ev["end"] > ev["start"] else a
    return a, b


def on_day(evs, day):
    return [e for e in evs if span(e)[0] <= day <= span(e)[1]]


def weeks(year, month):
    """The month as weeks of 7 days, Monday first, with the days of the months beside it that share a week."""
    return _cal.Calendar(0).monthdatescalendar(year, month)


def step_month(year, month, by):
    n = year * 12 + (month - 1) + by
    return n // 12, n % 12 + 1


def month_name(year, month):
    return f"{_cal.month_name[month]} {year}"


def day_words(day):
    """'Fri 11 Dec'."""
    return f"{_cal.day_abbr[day.weekday()]} {day.day} {_cal.month_abbr[day.month]}"


def clock(ts):
    return _dt.datetime.fromtimestamp(ts).strftime("%H:%M")


def away(ts, now=None):
    """'in 9 days', 'tomorrow', 'in 3 hours', 'now'. Days are counted by the date, not by 24 hours."""
    now = time.time() if now is None else now
    d = (local_day(ts) - local_day(now)).days
    if d > 1:
        return f"in {d} days"
    if d == 1:
        return "tomorrow"
    if d < 0:
        return "over" if d < -1 else "yesterday"
    left = ts - now
    if left <= 0:
        return "now"
    if left < 3600:
        return f"in {max(1, int(left // 60))} min"
    return f"in {int(left // 3600)} hours" if left >= 7200 else "in 1 hour"


def live(ev, now=None):
    now = time.time() if now is None else now
    return ev["start"] <= now and bool(ev.get("end")) and now < ev["end"]


def over(ev, now=None):
    now = time.time() if now is None else now
    return now >= (ev["end"] if ev.get("end") else ev["start"] + 3600)


def when_line(ev, now=None):
    """The gray line beside an upcoming event: 'in 9 days · Fri 11 Dec', or 'Live · ends Fri 18 Dec'."""
    if live(ev, now):
        return f"Live · ends {day_words(local_day(ev['end']))}"
    return f"{away(ev['start'], now)} · {day_words(local_day(ev['start']))}"


def starts_line(ev, now=None):
    return f"{day_words(local_day(ev['start']))}, {clock(ev['start'])} · {away(ev['start'], now)}"


def ends_line(ev):
    if not ev.get("end"):
        return "Not set"
    return f"{day_words(local_day(ev['end']))}, {clock(ev['end'])}"


def remind_line(ev):
    leads = reminders(ev)
    if not leads:
        return "– None"
    return "✓ " + ", and ".join(LEAD_WORDS.get(s, away_words(s)) for s in leads).lower().capitalize()


def away_words(secs):
    return f"{secs // DAY} days before" if secs >= DAY else f"{max(1, secs // 3600)} hours before"


def upcoming(evs=None, now=None, n=3, kinds=None):
    """The next n that are not over, earliest first; a live one counts."""
    now = time.time() if now is None else now
    evs = events() if evs is None else evs
    out = [e for e in evs if not over(e, now) and (kinds is None or e.get("kind") in kinds)]
    return out[:n]


def matches(ev, q):
    q = " ".join(str(q or "").lower().split())
    if not q:
        return True
    hay = f"{ev.get('name', '')} {word(ev.get('kind'))} {ev.get('note', '')} {ev.get('by', '')}".lower()
    return all(part in hay for part in q.split())


def shown(evs, q="", kinds=None):
    return [e for e in evs if (kinds is None or e.get("kind") in kinds) and matches(e, q)]


def parse_clock(text):
    """'20:00' or '8pm' or '2030' -> (hour, minute), or None."""
    import re
    s = str(text or "").strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == "pm" else 0)
    if h > 23 or mi > 59:
        return None
    return h, mi


def at(day, hour=0, minute=0):
    """This PC's time on that day, as seconds since 1970."""
    return _dt.datetime(day.year, day.month, day.day, hour, minute).timestamp()


# ---------------------------------------------------------------- reminders
def due(now=None, evs=None):
    """Reminders whose moment has come and that were not said yet. -> [(event, seconds before)], and marks them said.
    One that came due more than a day ago while the app was closed is dropped quietly: old news."""
    now = time.time() if now is None else now
    evs = events() if evs is None else evs
    st = state()
    out, changed = [], False
    for ev in evs:
        for lead in reminders(ev):
            key = f"{ev['id']}:{lead}"
            fire = ev["start"] - lead
            if fire > now or key in st["told"]:
                continue
            st["told"][key] = now
            changed = True
            if now - fire <= DAY and not over(ev, now):
                out.append((ev, lead))
    if changed:
        live_keys = {f"{e['id']}:{s}" for e in evs for s in reminders(e)}
        st["told"] = {k: v for k, v in st["told"].items() if k in live_keys}
        save()
    return out


def remind_words(ev, lead, now=None):
    """-> (title, line) for the alert card."""
    title = f"{label(ev)}: {ev['name']}"
    if lead <= 0 or ev["start"] <= (time.time() if now is None else now):
        return title, f"Starts now · {clock(ev['start'])}"
    return title, f"Starts {away(ev['start'], now)} · {day_words(local_day(ev['start']))}, {clock(ev['start'])}"
