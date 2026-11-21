"""2.131.0 Break reminders (feedback: reminders after a set amount of playtime to eat, drink water, take breaks and
rest - some players go 20+ hours without):
off until you turn it on. Every N minutes of play (a choice from EVERY, or your own), the next time you reach your hideout or a town
(never mid-map), one alert card with the next line of a rotation - kind, short, never nagging. More lines join the
rotation the longer you've played. Play time is the Session timer's (or this app run's); nothing about you is saved or
sent anywhere."""
import time

from .config import SETTINGS

EVERY = (15, 30, 45, 60, 75, 90, 120, 150, 180)     # the list's choices (owner: more of them, and your own)
LOWEST, HIGHEST = 5, 600                           # minutes a typed value may be
DEFAULTS = {"on": True, "every": 60}
# (hours played from, lines) - every line whose hours have come is in the rotation
LINES = [
    (0, ("Drink some water", "Stretch your back, neck and wrists", "Rest your eyes: look far away for 20 seconds",
         "Bathroom break?", "Sit back and drop your shoulders", "Take a few slow breaths",
         "Stand up and walk for a minute")),
    (2, ("Have you eaten? A real meal or a snack", "Any medication due?", "Check on your pets, plants and people")),
    (4, ("Step outside for fresh air and daylight", "Open a window for a bit", "Take a proper 10-15 minute break")),
    (8, ("When did you last shower?", "Brush your teeth", "Plan a real stopping point")),
    (12, ("You've been at it a long time - sleep will help tomorrow's runs", "Set an alarm to stop")),
]
NIGHT = range(1, 6)                     # 1-6 AM on your clock: the sleep lines join too


def cfg():
    c = SETTINGS.setdefault("breaks", {})
    for k, v in DEFAULTS.items():
        c.setdefault(k, v)
    c["every"] = minutes(c["every"]) or DEFAULTS["every"]
    return c


def minutes(value):
    """A choice or a typed value ("40", "40 min") -> whole minutes within LOWEST-HIGHEST, or None if it isn't one."""
    try:
        m = int(round(float(str(value).lower().replace("min", "").strip())))
    except (TypeError, ValueError):
        return None
    return max(LOWEST, min(HIGHEST, m))


def pool(hours, hour_of_day=None):
    """The lines in the rotation after this many hours played (and at this hour of the night)."""
    hod = time.localtime().tm_hour if hour_of_day is None else hour_of_day
    late = hod in NIGHT
    out = []
    for frm, lines in LINES:
        if hours >= frm or (late and frm == 12):
            out += lines
    return out


def due(played, last_at, every_min):
    """Played seconds now, played seconds at the last card -> time for the next one?"""
    return played - (last_at or 0) >= every_min * 60


def next_line(hours, n, hour_of_day=None):
    """-> (line, the next n). The rotation goes round the pool; a newly joined group's lines come first once."""
    p = pool(hours, hour_of_day)
    return p[n % len(p)], n + 1


def played_text(secs):
    h, m = int(secs // 3600), int(secs % 3600 // 60)
    return f"{h} h {m:02d} min played" if h else f"{m} min played"
