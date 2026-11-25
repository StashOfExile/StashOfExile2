"""The Dashboard's greeting (3.3.0, owner): a different hello by the time of day - plain ones, silly ones, puns, a
bit of internet. Every line here was kept or reworded by the owner on the keep-or-drop pages (2026-11-23); the ones
he skipped are gone. Add a line only with his say.

  {name}  is your board name, or "Exile" without one.
  A line in NAME_ONLY only shows when you have a name ("This app is Exile's biggest fan" makes no sense).
  About 1 time in 20 the name is swapped for a pet name ("Mornin', cutie").
  One greeting per time of day and app start: it does not change while you look at it.
  Settings › General › Window has the switch; off gives Good morning / afternoon / evening."""
import random
import time

from .config import SETTINGS

MORNING = (
    "Good morning, {name}",
    "Rise and grind, {name}",
    "Morning, {name}. That stash won't sort itself ;)",
    "Up before the servers, {name}?",
    "New day, same waystones, {name}",
    "Mornin', {name}. Things happened, prices changed, so much stuff and so many things. AHH",
    "Oi bruv, did you eat today?",
    "The early exile gets the divs",
    "Rise and shine, {name}. Mostly rise",
    "Morning, {name}. Did you drink water? Go drink water",
    "Morning person, or just never slept, {name}?",
    "Good morning to {name} and {name} only",
    "First coffee, then chaos. The orb kind",
    "It's morning, {name}. The grind is calling and it's on speaker",
    "Mornin', cutie :3",
    "Top of the mornin' to ya, legend",
    "Morning, {name}. Hair's a mess, stash is worse",
)

AFTERNOON = (
    "Good afternoon, {name}",
    "Lunch break mapping, {name}? Bold",
    "Per my last email, {name}: it's time to map",
    "Touch grass later, {name}. Maps now",
    "Just one more map, {name}. We both know that's a lie",
    "Afternoon, {name}. RNG owes you one",
    "Buy high sell low, that's what I always say!",
    "You could've been mapping instead of wasting time in a meeting!",
    "Afternoon, {name}. Peak snack-and-map hours",
    "Sneaking in a map at work, {name}? I saw nothing",
    "It's the afternoon slump, {name}. The cure is loot",
    "Afternoon, bestie. Did you eat? A real meal?",
    "Good afternoon, {name}. Let's be unproductive together",
    "Afternoon, {name}. Your boss thinks you're in a spreadsheet",
    "It's wine o'clock somewhere, {name}. Here it's divine o'clock",
)

EVENING = (
    "Good evening, {name}",
    "Welcome back, {name}. The grind missed you",
    "Clocking in for the night shift, {name}?",
    "Evening, {name}. Let's make some bad financial decisions",
    "Good evening, {name}. Tonight's the night it drops",
    "Evening, {name}. One more map, then bed. Sure",
    "Evening, {name}. You survived the day. Now survive the boss",
    "Good evening, gamer. Snacks ready?",
    "Home sweet hideout, {name}",
    "It's {name} o'clock. Time to map",
    "Evening, {name}. Pants optional, loot mandatory",
    "The day is over, {name}. The grind is forever",
    "Evening, cutie. Go off",
    "Dinner and a boss fight, {name}? Romantic",
)

LATE = (
    "Still up, {name}?",
    "It's late, {name}. The loot doesn't sleep either",
    "Bold of you to map at this hour, {name}",
    "Past midnight, {name}. Peak gamer hours",
    "Good night? No. Good loot, {name}",
    "Your bed called, I sent it straight to voicemail.",
    "One. More. Map. {name}",
    "The sun's coming up soon, {name}. Worth it",
    "Quiet hours, {name}. Good time to check prices",
    "Overtime approved, {name}",
    "Night owl hours, {name}. Hoot",
    "Sleep? Nah, go off sis, get to mappin'",
    "Still here, {name}? Icon behavior",
    "Go to bed? In THIS economy, {name}?",
    "The night is young and so is this league, {name}",
    "Me and {name} against bedtime",
    "Nocturnal exile detected. Hi {name}",
    "Tomorrow-you can deal with it, {name}. Map",
    "Sleep is a side quest, {name}",
    "The gremlin hours have begun, {name}",
)

ANY = (
    "Sup baddie",
    "Haaaayyyyyyyyy girl haaaaaayyyyyyyyyy",
    "Yaas king let's get them divs",
    "Oh hey, it's my favorite exile",
    "There you are, {name}. The stash was asking about you",
    "{name}! You absolute legend. Hi",
    "Hi bestie. Ready to get rich or die mapping?",
    "It's giving... loot day, {name}",
    "No thoughts, just maps. Hi {name}",
    "{name} has entered the chat",
    "You look like someone who's about to drop a divine",
    "Hello gorgeous. The currency tab missed you",
    "Okay {name}, be so for real: one map or ten?",
    "Div-ine to see you, {name}",
    "Looking exalted today, {name}",
    "Orb you glad to see me, {name}?",
    "Chaos? In this economy? Hi {name}",
    "You're doing amazing, sweetie",
    "Proud of you for logging in, {name}. Truly",
    "W exile. W stash. Hi {name}",
    "Bestie, the vibes are immaculate and the prices are not",
    "Live, laugh, loot, {name}",
    "POV: you're about to have a great session",
    "Lowkey happy you're here, {name}",
    "Hey you. Yeah, you. Go get that bread",
    "{name}, you dropped this 👑",
    "Stash check! Just kidding. Unless?",
    "Well well well, if it isn't the loot enjoyer",
    "Big day for people named {name}",
    "You again? Good. I like you",
    "That's a good exile.",
    "Now who's a good exile?",
    "This app is {name}'s biggest fan",
    "Orbe Divino!",
)

PLAIN = {"morning": "Good morning, {name}", "afternoon": "Good afternoon, {name}", "evening": "Good evening, {name}",
         "late": "Good evening, {name}"}
POOLS = {"morning": MORNING, "afternoon": AFTERNOON, "evening": EVENING, "late": LATE}
# these read wrong with "Exile" in place of a name
NAME_ONLY = ("This app is {name}'s biggest fan", "Big day for people named {name}",
             "Good morning to {name} and {name} only", "It's {name} o'clock. Time to map")
PET_NAMES = ("cutie", "bestie", "legend", "sunshine", "gorgeous", "champ")
PET_CHANCE = 0.05
ANY_SHARE = 0.4                    # how often a time-of-day greeting gives way to an any-time one
_START = time.time()               # a new greeting each time the app starts


def slot(now=None):
    h = time.localtime(now or time.time()).tm_hour
    return "morning" if 5 <= h < 12 else "afternoon" if 12 <= h < 18 else "evening" if 18 <= h < 23 else "late"


def playful():
    return SETTINGS.get("greet_playful", True) is not False


def lines(part, named):
    """Every greeting that can show in this part of the day."""
    rows = list(POOLS[part]) + list(ANY)
    return rows if named else [r for r in rows if r not in NAME_ONLY]


SEEN_KEY, NOW_KEY = "greet_seen", "greet_now"


def fresh(rows, key, both=None):
    """3.3.0 owner: a person should not see the same greeting again. -> the lines not shown yet. The one on
    screen for this time of day and app start stays the one on screen. rows: the lines this pick would draw
    from; both: every line that fits this time of day, used once rows has nothing new. When every one of those
    has been seen, they start over, without the one shown last."""
    both = list(both or rows)
    cur = SETTINGS.get(NOW_KEY) or {}
    if cur.get("key") == key and cur.get("line") in both:
        return [cur["line"]]
    seen = [s for s in SETTINGS.get(SEEN_KEY) or [] if isinstance(s, str)]
    for pool in (rows, both):
        left = [r for r in pool if r not in seen]
        if left:
            return left
    last = seen[-1] if seen else None
    SETTINGS[SEEN_KEY] = [s for s in seen if s not in both]       # this time of day starts over
    return [r for r in both if r != last] or list(both)


def remember(line, key):
    cur = SETTINGS.get(NOW_KEY) or {}
    if cur.get("key") == key and cur.get("line") == line:
        return
    seen = [s for s in SETTINGS.get(SEEN_KEY) or [] if isinstance(s, str) and s != line]
    SETTINGS[SEEN_KEY] = (seen + [line])[-400:]
    SETTINGS[NOW_KEY] = {"key": key, "line": line}
    try:
        from .config import save_json
        save_json("settings.json", SETTINGS)
    except Exception:
        pass


def greeting(name="", now=None, seed=None):
    """The hello for right now. name: your board name, "" without one."""
    now = now or time.time()
    part = slot(now)
    who = (name or "").strip()
    if not playful():
        return PLAIN[part].format(name=who or "Exile")
    day = time.strftime("%Y%m%d", time.localtime(now))
    key = f"{day}-{part}-{int(_START)}"
    rng = random.Random(seed if seed is not None else key)
    pool = ANY if rng.random() < ANY_SHARE else POOLS[part]
    rows = [r for r in pool if who or r not in NAME_ONLY]
    if seed is None:
        both = [r for r in list(POOLS[part]) + list(ANY) if who or r not in NAME_ONLY]
        rows = fresh(rows, key, both)
    line = rng.choice(rows)
    if seed is None:
        remember(line, key)
    if "{name}" in line and line not in NAME_ONLY and rng.random() < PET_CHANCE:
        return line.format(name=rng.choice(PET_NAMES))
    return line.format(name=who or "Exile")
