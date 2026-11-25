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


LINK_MAX, NOTE_MAX, BOARD_MAX = 300, 400, 200
BOARD_KINDS = tuple(k for k in ORDER if k != "mine")


def clean_board_rows(rows):
    """What the board sent, kept only when it is plain and sane: the app never trusts a download as it comes."""
    from . import cleantext
    out = []
    if not isinstance(rows, list):
        return out
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < 1e11     # noqa: E731
    for r in rows[:BOARD_MAX]:
        if not isinstance(r, dict):
            continue
        eid, name, link, note = r.get("id"), r.get("name"), r.get("link") or "", r.get("note") or ""
        if not (isinstance(eid, str) and 0 < len(eid) <= 20 and eid.startswith("b") and eid[1:].isdigit()):
            continue
        if r.get("kind") not in BOARD_KINDS or not isinstance(name, str) or not num(r.get("start")):
            continue
        name = " ".join(name.split())[:NAME_MAX]
        if not name or cleantext.problem(name) or not isinstance(link, str) or not isinstance(note, str):
            continue
        end = r.get("end") if num(r.get("end")) and r.get("end") >= r["start"] else 0
        if link and (not link.startswith("https://") or len(link) > LINK_MAX or any(c.isspace() for c in link)):
            link = ""
        out.append({"id": eid, "kind": r["kind"], "name": name, "start": float(r["start"]), "end": float(end),
                    "link": link, "note": "" if cleantext.problem(note) else note[:NOTE_MAX], "by": "Official"})
    return out


def pull(call=None):
    """Ask the board for its events. -> the cleaned rows, or None when it did not answer. Nothing is saved here:
    the window puts them in place with set_board, on its own thread."""
    from . import board as B
    if not B.configured():
        return None
    ok, res = (call or B.call)("GET", "/events")
    if not ok or not isinstance(res, dict):
        return None
    return clean_board_rows(res.get("events"))


def board_number(ev):
    """The board's own number for one of its events: 'b12' -> 12."""
    eid = str((ev or {}).get("id") or "")
    return int(eid[1:]) if eid.startswith("b") and eid[1:].isdigit() else 0


def event_body(kind, name, start, end=0, link="", note=""):
    """What an admin's Post Event sends, or a line saying what is wrong with it."""
    from . import cleantext
    name = " ".join(str(name or "").split())
    link = str(link or "").strip()
    if kind not in BOARD_KINDS:
        return "Pick what kind of event it is."
    if not name:
        return "It needs a name."
    if len(name) > NAME_MAX:
        return f"The name is over {NAME_MAX} letters."
    if cleantext.problem(name) or cleantext.problem(note):
        return "That wording is not allowed."
    if end and end < start:
        return "It ends before it starts."
    if link and (not link.startswith("https://") or len(link) > LINK_MAX or any(c.isspace() for c in link)):
        return "The link must start with https://"
    return {"kind": kind, "name": name, "start": int(start), "end": int(end or 0), "link": link,
            "note": str(note or "").strip()[:NOTE_MAX]}


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


def h24():
    """True when the app's clock shows 24 hours: the same choice as the clock in the app's corner."""
    try:
        from . import shell
        fmt = shell.CLOCK.get("format", "auto")
        return shell.windows_24h() if fmt == "auto" else fmt == "24"
    except Exception:
        return True


def clock(ts):
    """'8:00 PM' or '20:00', the way the app's own clock is set."""
    t = _dt.datetime.fromtimestamp(ts)
    return t.strftime("%H:%M") if h24() else t.strftime("%I:%M %p").lstrip("0")


def clock_hint():
    return "Like 20:00." if h24() else "Like 8pm or 8:30 PM."


MINUTE_STEP = 5


def clock_choices():
    """What the time pickers offer: (hours, minutes, AM and PM or nothing), in the app clock's own format."""
    mins = [f"{m:02d}" for m in range(0, 60, MINUTE_STEP)]
    if h24():
        return [f"{h:02d}" for h in range(24)], mins, []
    return [str(h) for h in (12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)], mins, ["AM", "PM"]


def clock_parts(hour, minute):
    """An hour and a minute as the three picker values: ('8', '30', 'PM') or ('20', '30', '')."""
    if h24():
        return f"{hour:02d}", f"{minute:02d}", ""
    return str(hour % 12 or 12), f"{minute:02d}", "PM" if hour >= 12 else "AM"


def clock_from_parts(hour, minute, half=""):
    """The pickers' three values back to (hour, minute), or None when one is not a number in range."""
    try:
        h, m = int(str(hour)), int(str(minute))
    except ValueError:
        return None
    if half in ("AM", "PM"):
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if half == "PM" else 0)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


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


OVERLAY_DAYS = 7               # the overlay's line shows an event from a week before it starts until it is over


def overlay_text(now=None, evs=None):
    """The overlay's one line: the next event that is live or starts within a week, or "" when there is none.
    '◆ League: 1.0 Release · in 3 days'."""
    now = time.time() if now is None else now
    for ev in upcoming(evs, now, n=1):
        if live(ev, now):
            return f"{label(ev)}: {ev['name']} · live, ends {day_words(local_day(ev['end']))}"
        if ev["start"] - now <= OVERLAY_DAYS * DAY:
            return f"{label(ev)}: {ev['name']} · {away(ev['start'], now)}"
    return ""


def plan_goal_text(ev):
    """The words of the League Plan goal an event becomes: one you tick yourself."""
    return f"Be ready for {ev['name']} · {day_words(local_day(ev['start']))}"


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
