"""2.141.0 Vaal Lens (BETA), the thinking part: the board as read (vaallens.read), the tiles the game lights green
for the picked card, and that card -> where it should go (1, 2) and where it must not (touches a reward room).

The plan (rules told by the player): the gold path straight up the middle (i = 0) to Atziri; the Architect only past
the middle row (j 6-9); the key room anywhere, joined back to the paths; reward rooms (the Architect's special
cards, on the outer wall) touched by nothing - a path or room next to one connects it and it destabilizes."""
import difflib
from collections import deque

ATZIRI = (0, 10)
ENTRANCE = (0, 0)
LANE = [(0, j) for j in range(1, 10)]
ARCHITECT_ROWS = range(6, 10)
STEP = ((0, 1), (0, -1), (1, 0), (-1, 0))
# outer squares a reward card is best kept on: every other one on the two long walls, top first
BLOCKERS = [(s * 4, j) for j in (9, 7, 5, 3, 1) for s in (-1, 1)]

# a room card's printed name (any tier) -> its family
ROOMS = {
    "Garrison": ("Guardhouse", "Barracks", "Hall of War", "Warrior Assembly"),
    "Commander": ("Commander's Chamber", "Commander's Hall", "Commander's Headquarters", "Commander's Station"),
    "Armoury": ("Depot", "Arsenal", "Gallery", "Royal Reserves"),
    "Smithy": ("Bronzeworks", "Chamber of Iron", "Golden Forge", "Immaculate Forge"),
    "Generator": ("Dynamo", "Shrine of Empowerment", "Solar Nexus", "Infinite Horizon"),
    "Spymaster": ("Spymaster's Study", "Hall of Shadows", "Omnipresent Panopticon", "Espionage Core"),
    "Synthflesh Lab": ("Prosthetic Research", "Synthflesh Sanctum", "Crucible of Transcendence", "Supremacy of Function"),
    "Flesh Surgeon": ("Surgeon's Ward", "Surgeon's Theatre", "Surgeon's Symphony", "Surgical Glory"),
    "Transcendent Barracks": ("Steelflesh Quarters", "Collective Legion", "Chamber of the Perfected"),
    "Alchemy Lab": ("Chamber of Souls", "Core Machinarium", "Grand Phylactory", "Decorous Phylactory"),
    "Golem Works": ("Workshop", "Automaton Lab", "Stone Legion", "Precision of Science"),
    "Corruption Chamber": ("Crimson Hall", "Catalyst of Corruption", "Locus of Corruption", "Rapture of Corruption"),
    "Thaumaturge": ("Thaumaturge's Laboratory",),
    "Sacrificial Chamber": ("Sacrificial Chamber",),
    "Sealed Vault": ("Sealed Vault",),
}
FAMILY = {n.lower(): fam for fam, names in ROOMS.items() for n in names}
PATHS = ("path", "halls")
KEY = "royal access chamber"
# who raises whose tier when beside it (watched in game)
TOUCH = {
    "Garrison": {"Commander", "Armoury", "Spymaster", "Synthflesh Lab"}, "Commander": {"Garrison"},
    "Armoury": {"Garrison", "Smithy", "Alchemy Lab"}, "Spymaster": {"Garrison"}, "Smithy": {"Armoury", "Golem Works"},
    "Golem Works": {"Smithy"}, "Generator": {"Thaumaturge", "Sacrificial Chamber"},
    "Synthflesh Lab": {"Flesh Surgeon", "Garrison"}, "Flesh Surgeon": {"Synthflesh Lab"},
    "Alchemy Lab": {"Armoury", "Thaumaturge"},
    "Thaumaturge": {"Alchemy Lab", "Corruption Chamber", "Sacrificial Chamber", "Generator"},
    "Corruption Chamber": {"Thaumaturge", "Sacrificial Chamber"},
    "Sacrificial Chamber": {"Corruption Chamber", "Thaumaturge", "Generator"},
}


# 2.142.0 (feedback: "I should be getting suggestions to place the thaumaturge then the corruption chamber attached to
# it and upgrade it to t3 and lock it"): the rooms that pay at tier 3, and the room each wants beside it
HIGH = ("Corruption Chamber", "Sacrificial Chamber", "Thaumaturge", "Alchemy Lab", "Smithy")
PARTNER = {
    "Thaumaturge": ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab"),
    "Corruption Chamber": ("Thaumaturge", "Sacrificial Chamber"),
    "Sacrificial Chamber": ("Thaumaturge", "Generator"),
    "Alchemy Lab": ("Thaumaturge",),
    "Smithy": ("Golem Works", "Generator"),
}


def card(name):
    """A card's printed name -> ("path", None) | ("key", None) | ("room", family) | None (not read / not known).
    2.141.0: only a name read close to a known card counts - anything else gets the ✕ marks only."""
    low = " ".join(str(name or "").lower().replace("’", "'").split())
    if not low:
        return None
    if difflib.get_close_matches(low, (KEY,), 1, 0.85):
        return ("key", None)
    if difflib.get_close_matches(low, PATHS, 1, 0.85) or (low.split() or [""])[0].strip(".,:;'\"|>") in PATHS:
        return ("path", None)                       # (3.0.6: "PATH >" - OCR takes in the card's art: still a path)
    if any(w in low for w in ("vault", "reliquary")) and low != "sealed vault":
        # 3.0.6: the Architect's restricted reward cards (Kishara's Vault, Vault of Reverence ...)
        return ("reward", " ".join(w[:1].upper() + w[1:] for w in low.strip(".,:;'\"|> ").split()))
    m = difflib.get_close_matches(low, list(FAMILY), 1, 0.85)
    if not m and len(low.split()) > 1 and len(low.split()[-1]) <= 2:
        return card(" ".join(low.split()[:-1]))     # (3.0.6: "DEPOT 4" - the card's art read as a short word)
    return ("room", FAMILY[m[0]]) if m else None


def names(board):
    """A read board -> {tile: what's there} for the taken tiles ("?" for a covered one)."""
    out = {ENTRANCE: "Entrance"}
    for c, v in board.items():
        if not isinstance(c, tuple):
            continue
        k = (v or {}).get("kind")
        if k in (None, "empty"):
            continue
        out[c] = {"path": "Path", "reward": "Reward", "architect": "Architect", "atziri": "Atziri",
                  "key": "Key Room", "room": (v.get("name") or "Room"), "unknown": "?"}.get(k, "?")
    return out


def inside(c):
    i, j = c
    return c in (ATZIRI, ENTRANCE) or (-4 <= i <= 4 and 1 <= j <= 9)


def near(c):
    return [(c[0] + di, c[1] + dj) for di, dj in STEP if inside((c[0] + di, c[1] + dj))]


def touches_reward(taken, t, kind=None):
    """Placing here joins a reward room: next to one (or, for a reward card, next to a path or room)."""
    if kind == "reward":
        return any(taken.get(n) not in (None, "Reward", "Architect", "Atziri") for n in near(t))
    return any(taken.get(n) == "Reward" for n in near(t))


# 3.0.7 (round 14, the owner's run: a reward room sat beside the only square next to Atziri; the planner never joined
# her - the owner did, with a Prosthetic Research beside his Flesh Surgeon): Atziri's doorstep - the one square beside
# her chamber - may touch a reward room. Atziri comes first (owner's #1); there is no other way in.
DOOR = (0, 9)


def blocked(b, n, goal=None):
    """A square a path or room on the way to goal must not take: it touches a reward room (Atziri's doorstep, on the
    way to her, excepted)."""
    return touches_reward(b, n) and not (goal == ATZIRI and n == DOOR)


# 3.0.7 (round 14, 3 screenshots: the owner's Path card art vs the squares the game lit green): a Path card has a
# shape - the sides its corridor opens to, drawn on the card - and is placed as drawn (never turned: the T card open
# NE, SW and SE lit the three squares north-west of the gold path and none of the three south-east of it). It goes
# only where one of its openings faces a path (or the entrance). Sides as on screen: NE = j + 1, SE = i + 1,
# SW = j - 1, NW = i - 1. A card whose shape wasn't read (None) may open any way.
SIDE = {"NE": (0, 1), "SE": (1, 0), "SW": (0, -1), "NW": (-1, 0)}


def path_fits(b, t, shape=None):
    """May a Path card of this shape go on t? Free, on the board, one opening facing a path or the entrance."""
    if b.get(t) or not inside(t) or t in (ATZIRI, ENTRANCE):
        return False
    for s, (di, dj) in SIDE.items():
        n = (t[0] + di, t[1] + dj)
        if (shape is None or s in shape) and (n == ENTRANCE or b.get(n) == "Path"):
            return True
    return False


def opens_to(t, n, shape=None):
    """Does a path of this shape on t open toward its neighbor n?"""
    return shape is None or any((t[0] + di, t[1] + dj) == n for s, (di, dj) in SIDE.items() if s in shape)


def route(taken, starts, goal):
    """Fewest free tiles from any start to goal (ties: nearer the middle). -> the tiles between, or None."""
    best, q = {}, deque()
    for s in starts:
        best[s] = (0, abs(s[0]), None)
        q.append(s)
    while q:
        c = q.popleft()
        if c == goal:
            break
        for n in near(c):
            if n != goal and taken.get(n):
                continue
            cost = (best[c][0] + 1, best[c][1] + abs(n[0]))
            if n not in best or cost < best[n][:2]:
                best[n] = (*cost, c)
                q.append(n)
    if goal not in best:
        return None
    out, c = [], best[goal][2]
    while c is not None and c not in starts:
        out.append(c)
        c = best[c][2]
    return out[::-1]


def network(taken):
    """Tiles joined to the entrance through paths and rooms."""
    seen, q = {ENTRANCE}, deque([ENTRANCE])
    while q:
        c = q.popleft()
        for n in near(c):
            if n not in seen and taken.get(n) and taken[n] not in ("Architect", "Atziri", "Reward"):
                # (3.0.6: "?" - a placed tile the reader didn't know - is joined too: you can only place next to
                # your paths and rooms; the owner's key room was 1 tile away through one)
                seen.add(n)
                q.append(n)
    return seen


def path_network(taken):
    """3.0.6 (owner: "paths cannot connect to rooms by themselves, they need a path to connect to"): the entrance and
    the path tiles joined to it through paths only - where a new path card can go next to."""
    seen, q = {ENTRANCE}, deque([ENTRANCE])
    while q:
        c = q.popleft()
        for n in near(c):
            if n not in seen and taken.get(n) == "Path":
                seen.add(n)
                q.append(n)
    return seen


def spine(taken):
    """The gold path built so far plus what's left of it to Atziri (the route the rooms keep off)."""
    net = network(taken)
    edge = [c for c in net if any(not taken.get(n) for n in near(c))]
    return set(LANE) | set(route(taken, edge, ATZIRI) or [])


def rank(board, lit, what):
    """-> [(score, tile, why)] best first, for the lit tiles; ruled-out ones (touch a reward room) score -1000.
    what: card() of the picked card, or None (not read: only the ✕ marks count)."""
    taken = names(board)
    kind = what[0] if what else None
    lane = spine(taken)
    out = []
    door = not any(n in network(taken) for n in near(ATZIRI))      # (3.0.7: her doorstep, while she isn't joined)
    for t in lit:
        if touches_reward(taken, t, kind) and not (door and t == DOOR and kind != "reward"):
            out.append((-1000, t, "touches a reward room"))
            continue
        if kind is None:
            continue
        if kind == "path":
            b = dict(taken)
            b[t] = "Path"
            r = route(b, [t], ATZIRI)
            d = len(r) + 1 if r is not None else 99
            score = -d * 10 - abs(t[0]) * 3 + (5 if t in lane else 0)
            out.append((score, t, f"{d} tiles from Atziri after this" if d < 99 else "leads nowhere new"))
        elif kind == "key":
            r = route(taken, [c for c in network(taken)] or [ENTRANCE], t)
            d = len(r) + 1 if r is not None else 99
            out.append((-d, t, f"{d} tiles from your paths"))
        else:
            fam = what[1]
            friends = sorted({taken[n] for n in near(t) if taken.get(n) in TOUCH.get(fam, ())})
            pals = sorted({taken[n] for n in near(t) if taken.get(n) in PARTNER.get(fam, ())})
            free = sum(1 for n in near(t) if not taken.get(n))
            spot = partner_spot(taken, t, lane)
            on_lane = t in lane
            score = len(friends) * 6 + len(pals) * 10 + free - (8 if on_lane else 0)
            want = fam in PARTNER and spot and PARTNER[fam][0] not in pals
            if want:
                score += 8                              # room beside it for the room it wants most
            why = ["next to " + ", ".join(sorted(set(friends) | set(pals)))] if friends or pals else []
            if want:
                why.append(f"room beside it for a {PARTNER[fam][0]}")
            if on_lane:
                why.append("on the gold path's way")
            why.append(f"{free} free sides")
            out.append((score, t, " · ".join(why)))
    return sorted(out, key=lambda x: (-x[0], abs(x[1][0]), x[1][1]))


def partner_spot(taken, t, lane=()):
    """A free tile beside t for the next room: not on the gold path's lane, touching no reward room (t counted as
    taken); the one with the most free sides of its own. None: no room."""
    b = dict(taken)
    b[t] = "Room"
    best = None
    for n in near(t):
        if b.get(n) or n in lane or n in (ATZIRI, ENTRANCE) or touches_reward(b, n):
            continue
        free = sum(1 for m in near(n) if not b.get(m))
        if best is None or free > best[0]:
            best = (free, n)
    return best[1] if best else None


def marks(board, lit, what):
    """-> {tile: ("1" | "2" | "x" | "+", why)}: the best two (when the card is known), every ruled-out tile, and for a
    room that wants a partner (Thaumaturge -> Corruption Chamber...) "+" where that partner goes beside 1."""
    out, n = {}, 0
    for score, t, why in rank(board, lit, what):
        if score <= -1000:
            out[t] = ("x", why)
        elif n < 2:
            n += 1
            out[t] = (str(n), why)
    fam = what[1] if what and what[0] == "room" else None
    one = [t for t, (m, _w) in out.items() if m == "1"]
    if fam in PARTNER and one:
        taken = names(board)
        if not any(taken.get(x) == PARTNER[fam][0] for x in near(one[0])):
            p = partner_spot(taken, one[0], spine(taken))
            if p and p not in out:
                out[p] = ("+", f"{PARTNER[fam][0]} here, beside it")
    return out


def combo(fam, hand=()):
    """A high-value room picked -> the steps after placing it: [(mark, text)] (its partner beside it, then upgrade and
    lock the one that pays). hand: medallion names you hold (learned), to say which ones do it."""
    if fam not in PARTNER:
        return []
    pay = fam if fam in ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab", "Smithy") else PARTNER[fam][0]
    steps = []
    if pay != fam:
        steps.append(("+", f"Then {pay} on +, beside it"))
    steps.append(("▲", f"Upgrade {pay} to tier 3"))         # (2.142.2: no medallion names - fewer words)
    steps.append(("■", "Lock it"))
    return steps


# ---------------------------------------------------------------- 2.142.0 the hand's plan
# (feedback, with two layouts: "the corruption chamber medallion + 2 of the cards in hand, those are the kinds of
# suggestions a player needs"): every room card in the list plus the rooms your medallions add, laid out together -
# each Thaumaturge first, with room beside it; the Corruption Chambers, Alchemy Labs and Sacrificial Chambers it
# raises go beside it (an Alchemy Lab beside two when it can). Only free tiles joined to your paths and rooms, off the
# gold path's lane, touching no reward room.
ORDER = ("Thaumaturge", "Corruption Chamber", "Alchemy Lab", "Sacrificial Chamber", "Generator", "Smithy",
         "Golem Works")
SHORT = {"Thaumaturge": "TH", "Corruption Chamber": "CC", "Alchemy Lab": "AL", "Sacrificial Chamber": "SC",
         "Generator": "GE", "Smithy": "SM", "Golem Works": "GW"}


def _safe(b, n, lane):
    """A free tile a room can go on: inside, off the gold path's lane, not the entrance or Atziri, touching no reward
    room."""
    return inside(n) and not b.get(n) and n not in lane and n not in (ATZIRI, ENTRANCE) and not touches_reward(b, n)


def _open_tiles(b, lane):
    """Free safe tiles joined to your paths and rooms."""
    return {n for c in network(b) for n in near(c) if _safe(b, n, lane)}


def _room_for(b, t, lane):
    """With a room on t: how many safe free tiles beside it (2.142.2 feedback: a Thaumaturge put where the next room
    beside it would touch a reward room - only safe sides count)."""
    nb = dict(b)
    nb[t] = "Room"
    return sum(1 for n in near(t) if _safe(nb, n, lane))


ANCHORS = {"Thaumaturge": ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab")}


def architect_route(board):
    """2.143.0 (feedback: "the most important step for this run is to connect to the architect and kill him so that I
    gain access to his special room cards to place the key room"): -> the free tiles a path needs from your paths and
    rooms to the Architect, fewest first, none touching a reward room; [] when he's already joined; None when he isn't
    on the board (or can't be reached safely)."""
    taken = names(board)
    arch = [c for c, v in taken.items() if v == "Architect"]
    if not arch:
        return None
    a = arch[0]
    net = network(taken)
    if any(n in net for n in near(a)):
        return []
    best, q = {c: None for c in net}, deque(net)
    while q:
        c = q.popleft()
        for n in near(c):
            if n in best:
                continue
            if n == a:
                out, k = [], c
                while k is not None and k not in net:
                    out.append(k)
                    k = best[k]
                return out[::-1]
            if taken.get(n) or n in (ATZIRI, ENTRANCE) or touches_reward(taken, n):
                continue
            best[n] = c
            q.append(n)
    return None


def architect_chain(board):
    """-> [your tile, the path's tiles..., the Architect] for drawing the path as one gold lane, or None."""
    route = architect_route(board)
    if not route:
        return None
    taken = names(board)
    net = network(taken)
    arch = next(c for c, v in taken.items() if v == "Architect")
    start = next((n for n in near(route[0]) if n in net), None)
    return ([start] if start else []) + route + [arch]


def steps(plan):
    """The step number of each planned tile: the Architect's path is one step (however many tiles), each room one."""
    out, k, prev = [], 0, None
    for _t, fam, why in plan:
        if not (fam == "Path" and prev == ("Path", why)):    # (3.0.6: a path to the key room, then to Atziri: 2 steps)
            k += 1
        out.append(k)
        prev = (fam, why)
    return out


def hand_plan(board, fams):
    """board: a read board; fams: room families in hand (cards and medallions, repeats allowed).
    -> [(tile, family, why)] in the order to place them: each Thaumaturge first, on a tile with safe room beside it
    for the rooms it raises that you hold; then those rooms beside a Thaumaturge (yours or one already placed). A room
    with no Thaumaturge to go beside isn't planned. Every tile safe (no reward room touched, off the lane)."""
    taken = names(board)
    lane = spine(taken)
    b = dict(taken)
    plan = []
    for t in architect_route(board) or []:               # 2.143.0: first, a path to the Architect
        b[t] = "Path"
        plan.append((t, "Path", "to the Architect"))
    for anchor, partners in ANCHORS.items():
        want = [f for f in fams if f in partners]
        want.sort(key=partners.index)
        for _k in range(sum(1 for f in fams if f == anchor)):
            need = min(len(want), 3)
            best = None
            for t in _open_tiles(b, lane):
                room = _room_for(b, t, lane)
                if room < min(need, 2):
                    continue
                pals = sum(1 for n in near(t) if b.get(n) in partners)
                score = pals * 10 + min(room, need + 1) * 3 - abs(t[0]) * 0.2
                if best is None or score > best[0]:
                    best = (score, t)
            if best is None:
                continue
            b[best[1]] = anchor
            plan.append((best[1], anchor, "room beside it"))
        anchors = [c for c, f in b.items() if f == anchor]
        for fam in want:
            best = None
            for a_ in anchors:
                for n in near(a_):
                    if not _safe(b, n, lane):
                        continue
                    k = sum(1 for m in near(n) if b.get(m) == anchor)     # beside two Thaumaturges: better
                    score = k * 10 + _room_for(b, n, lane)
                    if best is None or score > best[0]:
                        best = (score, n)
            if best is None:
                continue
            b[best[1]] = fam
            plan.append((best[1], fam, "beside " + anchor))
    return plan


def card_title(name):
    """An OCR'd card name ("THAUMATURGE'S LABORATORY") -> as the game prints it ("Thaumaturge's Laboratory").
    3.0.6 (owner's card said "Wor Kshop"): a near miss is snapped to the printed name too."""
    low = " ".join(str(name or "").lower().replace("’", "'").split())
    every = [n for names_ in ROOMS.values() for n in names_]
    for n in every:
        if n.lower() == low:
            return n
    m = difflib.get_close_matches(low, [n.lower() for n in every], 1, 0.8) or \
        difflib.get_close_matches(low.replace(" ", ""), [n.lower().replace(" ", "") for n in every], 1, 0.85)
    if m:
        return next(n for n in every if n.lower() == m[0] or n.lower().replace(" ", "") == m[0])
    if card(low) == ("path", None):
        return "Path"
    if len(low.split()) > 1 and len(low.split()[-1]) <= 2 and card(low):
        return card_title(" ".join(low.split()[:-1]))
    return " ".join(w[:1].upper() + w[1:] for w in low.split()) if low else ""


def with_plan(marks, plan, lit, what, card=None):
    """The marks over the game (2.142.2, feedback: "I want it to be self-explanatory of what to place where"): each
    planned tile -> ("p", (step, family)), drawn with that room's own picture and its step; the picked card's tile ->
    ("now", (step or None, family or card name)): its planned tile when lit, else its best tile; ✕ tiles stay."""
    out = {t: v for t, v in marks.items() if v[0] == "x"}
    fam = what[1] if what and what[0] == "room" else ("Path" if what and what[0] == "path" else None)
    key = (fam if fam != "Path" else None) or (str(card or "").lower() or None)
    st = steps(plan)
    mine = next(((st[k], t) for k, (t, f, _w) in enumerate(plan) if f == fam and t in lit), None)
    if mine is not None:
        out[mine[1]] = ("now", (mine[0], key))
    elif lit and key:
        best = next((t for t, (m, _w) in marks.items() if m == "1"), None)
        if best is not None:
            out[best] = ("now", (None, key))
    for k, (t, f, _w) in enumerate(plan):
        if t not in out:                    # (3.0.6 owner: every tile numbered - one path card per path tile)
            out[t] = ("p", (st[k], "path" if f == "Path" else ("Royal Access Chamber" if f == "Key Room" else f)))
    return out


# ================================================================ 3.0.6 the full plan (owner's rules, TEMPLE_RULES.md)
# One Read Key press reads the board, the cards and the medallions; this lays out everything in order:
#   1. the key room (Royal Access Chamber) joined, and Atziri joined - nothing comes before this
#   2. a path to the Architect (kill him: his restricted cards bring the key room)
#   3. every room in hand: chains in the LEFT quadrant, the BOTTOM one kept free for the key room, TOP and RIGHT kept
#      free for the Architect (he lands on either), no loops (rooms joined in a circle destabilize more), never
#      beside a reward room, a Generator only on a path
#   + medallions: where the upgrade and the lock go, a reroll when the hand pays nothing.
# The quadrants are split by the gold path (i = 0) and the middle row (j = 5), as on the owner's screenshot:
# left = i < 0, j < 5 · top = i < 0, j > 5 · right = i > 0, j > 5 · bottom = i > 0, j < 5.

# 3.0.7 (round 14, owner: the tier 3-4 Transcendent Barracks and Synthflesh Lab "offered no reward"; the Flesh
# Surgeon is "way low priority"): both below PAYS - filler and joiners
VALUE = {"Thaumaturge": 10, "Corruption Chamber": 9, "Sacrificial Chamber": 8, "Flesh Surgeon": 5, "Alchemy Lab": 7,
         "Synthflesh Lab": 3, "Smithy": 6, "Generator": 5, "Golem Works": 4, "Armoury": 4, "Garrison": 3,
         "Commander": 3, "Spymaster": 2, "Transcendent Barracks": 2, "Sealed Vault": 1}
PAYS = 6                                     # a room worth placing for itself (VALUE >= PAYS) - below that, filler
PARTNER.setdefault("Flesh Surgeon", ("Synthflesh Lab",))      # owner: tier-3 Flesh Surgeon (limbs) beside Synthflesh
PARTNER.setdefault("Synthflesh Lab", ("Flesh Surgeon",))
# rooms that others are placed beside: placed first, so their partners have room
FIRST = ("Thaumaturge", "Synthflesh Lab", "Smithy", "Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab",
         "Flesh Surgeon", "Generator", "Golem Works", "Armoury", "Garrison", "Commander", "Spymaster")
KEEP_ALONE = ("Commander",)      # (owner) placed only beside a Garrison: a tier-3 Commander drops medallions best
# 3.0.7 (round 14, owner): Upgrades only where a higher tier pays - not the Transcendent Barracks, the Synthflesh Lab,
# the Generator (more monsters, xp, effectiveness only); the Flesh Surgeon last, and never while a Corruption Chamber
# is in play
UPGRADE_FIRST = ("Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab", "Smithy", "Flesh Surgeon")
UPGRADE_LOW = ("Flesh Surgeon",)


def quadrant(t):
    """'left' | 'top' | 'right' | 'bottom' | None (the gold path's column, the middle row, the entrance, Atziri)."""
    i, j = t
    if i == 0 or j == 5 or t in (ATZIRI, ENTRANCE) or not inside(t):
        return None
    if i < 0:
        return "left" if j < 5 else "top"
    return "bottom" if j < 5 else "right"


def _loops(b, t):
    """Placing t closes a circle: two of its neighbors are already joined to each other (through the network)."""
    net = network(b)
    return sum(1 for n in near(t) if n in net and b.get(n) not in (None, "?")) >= 2


def path_to(b, goal, avoid=()):
    """The free tiles a path needs from your joined tiles to goal (fewest, none beside a reward room, off the
    `avoid` tiles - the key room's landing spot - when it can); [] already joined; None no safe way."""
    if avoid:
        got = path_to(b, goal)
        r = _path_to(b, goal, set(avoid))
        return r if r is not None and got is not None and len(r) <= len(got) + 1 else got
    return _path_to(b, goal, set())


def _path_to(b, goal, avoid):
    # (3.0.6 owner: Atziri is joined by paths - "as soon as I end up ... having no rooms that can connect my chain to
    # atziri I'm in trouble"; the key room and the Architect may be joined by a room too)
    # 3.0.7 (round 14: Atziri's doorstep taken by a room joined to the rest - her chamber lit up for the run): joined
    # by anything is joined; a path can't go there any more
    if any(n in network(b) for n in near(goal)):
        return []
    net = path_network(b)                              # (a new path goes next to a path)
    best, q = {c: None for c in net}, deque(sorted(net, key=lambda c: abs(c[0])))
    while q:
        c = q.popleft()
        for n in near(c):
            if n in best:
                continue
            if n == goal:
                out, k = [], c
                while k is not None and k not in net:
                    out.append(k)
                    k = best[k]
                return out[::-1]
            if b.get(n) or n in (ATZIRI, ENTRANCE) or blocked(b, n, goal) or n in avoid:
                continue
            best[n] = c
            q.append(n)
    return None


def _form(shape):
    return "".join(sorted(shape)) if shape else "*"


def shaped_route(b, goal, cards, avoid=()):
    """3.0.7: the fewest free squares from your paths to goal that the Path cards in hand can fill as drawn - each
    card on its square opens toward a path already there or the square before it. cards: [(id, shape)]. -> [(tile,
    id)] (the last one opening toward goal when a card can), [] already joined, None no way with these cards."""
    if any(n in network(b) for n in near(goal)):
        return []
    pn = path_network(b)
    seen, q, done = set(), deque(), []
    for t in sorted({n for c in pn for n in near(c)}, key=lambda c: abs(c[0])):
        q.append((t, ()))
    while q:
        t, route = q.popleft()
        if done and len(route) + 1 > len(done[0]):
            break
        if b.get(t) or not inside(t) or t in (ATZIRI, ENTRANCE) or blocked(b, t, goal) or t in avoid:
            continue
        on = {x for x, _k in route}
        if t in on:
            continue
        used = {k for _x, k in route}
        trial = dict(b)
        trial.update({x: "Path" for x in on})
        tried = set()
        for k, shape in cards:
            if k in used or _form(shape) in tried or not path_fits(trial, t, shape):
                continue
            tried.add(_form(shape))                     # (cards of one shape: one try)
            key = (t, tuple(sorted(_form(s) for kk, s in cards if kk in used | {k})))
            if key in seen:
                continue
            seen.add(key)
            r = route + ((t, k),)
            if goal in near(t):
                done.append(r)
                continue
            q.extend((n, r) for n in near(t) if n not in on)
    if not done:
        return None
    sh = dict(cards)
    return list(min(done, key=lambda r: (not opens_to(r[-1][0], goal, sh.get(r[-1][1])), len(r))))


def tier_of(board, t):
    return ((board or {}).get(t) or {}).get("tier") or 1


def _tiers(fam):
    return len(ROOMS.get(fam, ())) or 1


def landing(b, quad):
    """A free tile in quad with all four sides free and no reward room beside it (where the game can drop the key
    room / the Architect without forcing it in), the most open first; None: no clean spot."""
    best = None
    for t in [c for c in ((i, j) for i in range(-4, 5) for j in range(1, 10)) if quadrant(c) == quad]:
        if b.get(t) or touches_reward(b, t):
            continue
        free = sum(1 for n in near(t) if not b.get(n))
        if free < len(near(t)):
            continue
        score = free - abs(t[0] - (2 if quad in ("bottom", "right") else -2)) * 0.1
        if best is None or score > best[0]:
            best = (score, t)
    return best[1] if best else None


CURRENCY_VAULT = "Kishara's Vault"


def reachable_later(b, t, keep=()):
    """3.0.7 (owner, round 14): a reward room on t can be joined by a later run's path without opening another reward
    room: t touches no other reward room, and a free square beside it (touching no other reward room) is reached
    from your paths over free squares that touch no reward room."""
    if any(b.get(n) == "Reward" for n in near(t)):
        return False
    nb = dict(b)
    nb[t] = "Reward"
    doors = {a for a in near(t) if not nb.get(a) and inside(a) and a not in (ATZIRI, ENTRANCE) and a not in keep and
             not any(nb.get(m) == "Reward" for m in near(a) if m != t)}
    if not doors:
        return False
    pn = path_network(nb)
    seen, q = set(), deque(n for c in pn for n in near(c))
    while q:
        c = q.popleft()
        if c in seen or nb.get(c) or not inside(c) or c in (ATZIRI, ENTRANCE) or c in keep:
            continue
        seen.add(c)
        if c in doors:
            return True
        if touches_reward(nb, c):
            continue
        q.extend(near(c))
    return False


def edge_blocks(b):
    """3.0.6 (owner: "If no reward rooms lining the outside edges ... they need the every other placement at the very
    least to block off atziri key room and architect from spawning near the edges"): every other outer square, on
    each wall with no reward room on it - where filler rooms go."""
    walls = {"l": lambda t: t[0] == -4, "r": lambda t: t[0] == 4, "b": lambda t: t[1] == 1, "t": lambda t: t[1] == 9}
    out = set()
    for on in walls.values():
        wall = [(i, j) for i in range(-4, 5) for j in range(1, 10) if on((i, j))]
        if any(b.get(t) == "Reward" for t in wall):
            continue
        out |= {t for t in wall if (t[0] + t[1]) % 2 and t not in LANE}
    return out


def key_spot(b):
    """Where the key room will land after the Architect (a clean bottom-quadrant tile) and its four sides - kept free."""
    t = landing(b, "bottom")
    return {t, *near(t)} if t else set()


PATH_ONLY = ("Sealed Vault", "Generator")       # (owner: "sealed vaults have to connect to a path and cannot connect
#                                                 to anything else"; the cheat sheet: a Generator joins a path)


def can_place(b, t, fam):
    """3.0.6 (the game: a room goes beside a path, or beside a room it works with): may fam go on t?"""
    for n in near(t):
        v = b.get(n) if n != ENTRANCE else "Entrance"
        if v in ("Path", "Entrance"):
            return True
        if fam not in PATH_ONLY and v in ROOMS and (v in TOUCH.get(fam, ()) or fam in TOUCH.get(v, ())):
            return True
    return False


def _room_score(b, t, fam, rest, lane, arch, key_needed, keep=(), edges=(), ups=0):
    """How good t is for a room of fam (None: not allowed). rest: rooms still to place (their partners count).
    keep: tiles held free for the key room; edges: filler squares on a bare outer wall (edge_blocks)."""
    if b.get(t) or t in (ATZIRI, ENTRANCE) or not inside(t) or touches_reward(b, t) or t in lane or t in keep:
        return None
    if not any(n in network(b) for n in near(t)) or not can_place(b, t, fam):
        return None
    if fam == "Sealed Vault" and any(b.get(n) in ROOMS for n in near(t)):
        return None
    nbs = [b.get(n) for n in near(t)]
    if (fam == "Spymaster" and "Commander" in nbs) or (fam == "Commander" and "Spymaster" in nbs):
        return None                                   # (cheat sheet: a Spymaster can't join a Commander)
    if fam == "Generator" and not any(b.get(n) in ("Path", "Entrance") for n in near(t)):
        return None                                   # (cheat sheet: a Generator must be joined to a path)
    nb = [b.get(n) for n in near(t)]
    pals = sum(1 for x in nb if x in PARTNER.get(fam, ()))
    friends = sum(1 for x in nb if x in TOUCH.get(fam, ()))
    wanted = [p for p in PARTNER.get(fam, ()) if p in rest]
    nb_ = dict(b)
    nb_[t] = fam                                      # free sides a partner can take later without closing a loop
    room = sum(1 for n in near(t) if _safe(nb_, n, lane) and not _loops(nb_, n))
    score = pals * 12 + friends * 6 + min(room, len(wanted)) * 4
    # 3.0.7 (round 14: the owner's Workshop beside his Bronzeworks took it to tier 3): raising a room that pays counts
    if not any(n in LANE and b.get(n) == "Path" for n in near(t)):          # (not a loop back into the road)
        score += 6 * sum(1 for x in nb if x in ROOMS and VALUE.get(x, 0) >= PAYS and fam in TOUCH.get(x, ()))
    if t in edges and not pals and not wanted and VALUE.get(fam, 0) < PAYS:
        score += 15                                   # (#5 everything else: a filler blocks a bare wall)
    q = quadrant(t)
    score += {"left": 8, None: 0}.get(q, 0)
    if q == "bottom" and key_needed:
        score -= 25                                   # the key room's landing quadrant
    if q in ("top", "right"):
        score -= 20                                   # the Architect's (he switches sides run to run)
    if arch and any(n == arch for n in near(t)):
        score -= 40                                   # his one free square on each side
    if _loops(b, t):
        score -= 10 if pals or friends else 30          # (owner: a loop is worth it for a second tier-3 Smithy)
        if any(n in LANE and b.get(n) == "Path" for n in near(t)) and (friends < 2 or ups):
            score -= 40                                 # (owner: not "back into the main road down the middle" -
            #                                             unless it pays: his Golem Works beside three tier-3 Smithies)
    return score - abs(t[0]) * 0.1


def gain(b, t, fam):
    """How many of t's neighbors raise a room of fam there, or are raised by it (TOUCH, both ways)."""
    return sum(1 for n in near(t) if b.get(n) in ROOMS and (b[n] in TOUCH.get(fam, ()) or fam in TOUCH.get(b[n], ())))


def _ends(b, t):
    """How many placed tiles (or the entrance) t touches: 1 = a dead end."""
    return sum(1 for n in near(t) if n == ENTRANCE or b.get(n) not in (None, "Reward", "Atziri", "Architect"))


def _worth_keeping(b, t, board):
    fam = b.get(t)
    return fam in ROOMS and (VALUE.get(fam, 0) >= PAYS or tier_of(board, t) >= 3)


def dead_ends(b, board):
    """3.0.6: valuable rooms (they pay, or tier 3+) at a dead end - the tiles destabilisation takes most."""
    return [t for t, f in b.items() if f in ROOMS and _worth_keeping(b, t, board) and _ends(b, t) <= 1]


def full_plan(board, cards=(), medals=(), medal_rooms=(), prev=()):
    """board: a read board; cards: the room card names in the list; medals: medallion names held (None = not known);
    medal_rooms: room families the medallions add; prev: the last plan's steps for this board (kept while they still
    fit - owner: "too many changed decisions ... per each card I place"). -> {"plan": [(tile, family, why)] in order,
    "targets": {tile: ("Upgrade" | "Lock", family)}, "notes": [str]}."""
    from . import medallions as M
    taken = names(board)
    b = dict(taken)
    lane = spine(taken)
    plan, notes, targets, chains = [], [], {}, []
    keyroom = next((c for c, v in taken.items() if v == "Key Room"), None)
    arch = next((c for c, v in taken.items() if v == "Architect"), None)
    hand = [card(n) for n in cards or ()]
    # 3.0.6 (owner: "it's still making lock/whatever suggestions at the architect's console, I cannot perform any
    # actions except placing the special reward room cards"): his console - only restricted cards (vaults, the key
    # room, an Extraction Chamber ...); a card name not known there is one of his too
    restricted = bool(hand) and any(h and h[0] in ("reward", "key") for h in hand) and \
        not any(h and h[0] in ("path", "room") for h in hand)
    if restricted:
        hand = [h if h else ("reward", card_title(n)) for h, n in zip(hand, cards)]
        medals, medal_rooms = (), ()
    key_card = any(h and h[0] == "key" for h in hand)
    # 3.0.7: the Path cards in hand, each with its shape as read off its card (None: not read - any way)
    shapes = list((board or {}).get("card_shapes") or [])
    pcards = [(k, frozenset(shapes[k]) if k < len(shapes) and shapes[k] else None)
              for k, h in enumerate(hand) if h and h[0] == "path"]
    path_cards = {}                                    # tile -> the card (its place in the list) that goes there

    def put_path(t, k=None):
        """A Path card on t: card k, else the first one whose shape fits there. -> False when none fits."""
        got = next((c for c in pcards if c[0] == k), None) if k is not None else \
            next((c for c in pcards if path_fits(b, t, c[1])), None)
        if got is None:
            return False
        pcards.remove(got)
        path_cards[t] = got[0]
        b[t] = "Path"
        return True
    # (3.0.6 owner: "it needs to use what I have") - a tile with no path card left takes a room card instead (the
    # owner joined the key room with a Sealed Vault): the one worth least, kept for the rooms worth placing
    spare = sorted([h[1] for h in hand if h and h[0] == "room"] + [f for f in medal_rooms if f],
                   key=lambda f: VALUE.get(f, 0))

    room_cards = [h[1] for h in hand if h and h[0] == "room"]

    def joiner(t):
        """3.0.6 (owner's board: Atziri joined with a Guardhouse and a Depot on the gold path - each raised a
        neighbor's tier): a room card that gains a tier there joins it instead of a path card. The worth-most rooms
        only for two gains."""
        best = None
        for fam in set(room_cards):
            g = gain(b, t, fam)
            if fam in KEEP_ALONE and "Garrison" not in [b.get(n) for n in near(t)]:
                continue
            if g < (2 if VALUE.get(fam, 0) >= PAYS else 1) or not can_place(b, t, fam):
                continue
            score = g * 10 - VALUE.get(fam, 0)
            if best is None or score > best[0]:
                best = (score, fam)
        return best[1] if best else None

    def use_room(fam):
        room_cards.remove(fam)
        if fam in spare:
            spare.remove(fam)

    def chain_to(goal, why):
        """3.0.6 (owner's board: not enough path cards, so a Garrison / Commander chain snaked up to Atziri, and one
        more room after it "to hopefully preserve that chain"): rooms that raise each other, joined to anything."""
        net = network(b)
        best, q = {c: None for c in net}, deque(sorted(net))
        end = None
        while q and end is None:
            c = q.popleft()
            for n in near(c):
                if n in best:
                    continue
                if n == goal:
                    end = c
                    break
                if b.get(n) or n in (ATZIRI, ENTRANCE) or blocked(b, n, goal) or n in keep:
                    continue
                best[n] = c
                q.append(n)
        if end is None or end in net:
            return False
        r, k = [], end
        while k is not None and k not in net:
            r.append(k)
            k = best[k]
        r = r[::-1]
        trial, used = dict(b), []
        left = list(room_cards)
        for t in r:
            # 3.0.7 (round 14: only the Prosthetic Research could join Atziri - beside the Flesh Surgeon): a cheap
            # room first; a room worth more only when no cheap one fits (Atziri is #1)
            fam = max((f for f in set(left) if gain(trial, t, f) >= 1 and
                       can_place(trial, t, f) and not (
                f in KEEP_ALONE and "Garrison" not in [trial.get(n) for n in near(t)])),
                key=lambda f: (VALUE.get(f, 0) < PAYS, gain(trial, t, f), -VALUE.get(f, 0)), default=None)
            if fam is None:
                return False
            left.remove(fam)
            trial[t] = fam
            used.append((t, fam))
        for t, fam in used:
            use_room(fam)
            b[t] = fam
            plan.append((t, fam, f"joins {why}"))
        tip = used[-1][0]                              # (one more room beside the last one: it guards the chain)
        for n in sorted(near(tip)):
            if b.get(n) or not inside(n) or n in (ATZIRI, ENTRANCE) or touches_reward(b, n) or n in keep:
                continue
            fam = max((f for f in set(room_cards) if gain(b, n, f) >= 1 and not (
                f in KEEP_ALONE and "Garrison" not in [b.get(x) for x in near(n)])),
                      key=lambda f: gain(b, n, f), default=None)
            if fam:
                use_room(fam)
                b[n] = fam
                plan.append((n, fam, "guards the chain to Atziri"))
                break
        notes.append("Atziri is joined by rooms: one lost to destabilization cuts it. Use path cards when you "
                     "have them.")
        guard = plan[-1][2] == "guards the chain to Atziri"
        chains.append(f"Chain to Atziri: {len(used)} room{'s' if len(used) != 1 else ''}"
                      f"{', then a guard room' if guard else ''}.")
        return True

    def add_path(goal, why):
        r = path_to(b, goal, keep)
        if r == []:
            return True
        # 3.0.7: the Path cards as drawn - a route they can fill, each card where its shape fits
        sr = shaped_route(b, goal, pcards, keep) if pcards else None
        if sr is None and pcards and keep:
            sr = shaped_route(b, goal, pcards)
        if goal == ATZIRI and sr is None and chain_to(goal, why):
            return True                                # (paths short, or no way for a path: a room chain)
        if sr:
            for t, k in sr:
                last = t == sr[-1][0] and goal != ATZIRI   # (a path can't go on from a room: a room only ends it)
                j = joiner(t) if last and not touches_reward(b, t) else None
                if j:
                    use_room(j)
                    b[t] = j
                    plan.append((t, j, f"joins {why}"))
                    continue
                put_path(t, k)
                plan.append((t, "Path", why))
            n = sum(1 for _t, k in sr if path_cards.get(_t) == k)
            chains.append(f"Path to {why}: {n} path{'s' if n != 1 else ''}"
                          f"{', then a room' if n < len(sr) else ''}.")
            return True
        if r is None:
            notes.append(f"No safe path to {why} yet.")
            return False
        for t in r:
            last = t == r[-1] and goal != ATZIRI       # (a path can't go on from a room: a room only ends a route)
            j = joiner(t) if last and not touches_reward(b, t) else None
            if j:
                use_room(j)
                b[t] = j
                plan.append((t, j, f"joins {why}"))
            elif put_path(t):
                plan.append((t, "Path", why))
            elif last and [f for f in spare if f not in KEEP_ALONE and VALUE.get(f, 0) < PAYS and
                           can_place(b, t, f)] and not touches_reward(b, t) and t not in LANE:
                fam = next(f for f in spare if f not in KEEP_ALONE and VALUE.get(f, 0) < PAYS and can_place(b, t, f))
                spare.remove(fam)                      # (never a Commander: it waits for a Garrison)
                if fam in room_cards:
                    room_cards.remove(fam)
                b[t] = fam
                plan.append((t, fam, f"joins {why}"))
            else:
                left = len(r) - r.index(t)
                word = "path card" if not any(c[1] for c in pcards) and not path_cards else "path card that fits"
                notes.append(f"{why[0].upper() + why[1:]}: {left} more {word}{'s' if left != 1 else ''} needed.")
                return False
        return True

    # 3.0.6 (owner, in order): "#1: Atziri Chamber #2: Key Room (if available) #3: Architect #4: chains that give
    # profits for t3 rooms / upgrade / lock #5: Everything else"
    key_needed = keyroom is None
    keep = key_spot(b) if key_needed and not key_card else set()   # (no key room yet: its landing spot stays free)
    if key_card and keyroom is not None:
        # 3.0.6 (owner: "it also needs to tell me where to place atziri's key room ... it should have the number on
        # her room and the board"): the key room card held and its room on the board = the game's preview of
        # where it goes (it lights that one square) - step 1, then what joins it
        b.pop(keyroom, None)
        b[keyroom] = "Key Room"
        plan.append((keyroom, "Key Room", "the key room"))
        key_card, key_needed, keep = False, False, set()
    for t, fam, why in prev or ():                     # (the last plan, step by step, while it still fits)
        if b.get(t) or not any(n in network(b) for n in near(t)) or blocked(b, t, ATZIRI if "Atziri" in why else None):
            continue
        if fam == "Path":
            if not put_path(t):                        # (3.0.7: no card left whose shape fits there)
                continue
        elif fam in spare:
            spare.remove(fam)
            if fam in room_cards:
                room_cards.remove(fam)
        else:
            continue
        b[t] = fam
        plan.append((t, fam, why))
    add_path(ATZIRI, "Atziri")
    if keyroom is not None:
        add_path(keyroom, "the key room")
    if arch is not None:
        add_path(arch, "the Architect")
    # the key room card in hand (after the Architect): a clean spot in the bottom quadrant
    if key_card:
        # 3.0.7 (round 14: the key room card picked, the game lit three squares; the owner took the bottom one): with
        # the key room card picked, only the squares the game lights - the bottom quadrant first, most safe sides
        lit = [t for t in (board or {}).get("lit") or [] if not b.get(t) and inside(t)] \
            if card((board or {}).get("card")) == ("key", None) else []
        spot = max(lit, key=lambda t: (quadrant(t) == "bottom", _room_for(b, t, ()), -abs(t[0]))) if lit else \
            landing(b, "bottom") or next((t for t in (landing(b, q) for q in ("left", "top", "right")) if t), None)
        if spot and (restricted or any(n in network(b) for n in near(spot))):
            b[spot] = "Key Room"                       # (at his console no path can go down: it joins next run)
            plan.append((spot, "Key Room", "the key room"))
            key_needed = False
            if restricted and not any(n in network(b) for n in near(spot)):
                chains.append("Key room alone for now: one path joins it next run.")
        elif spot:
            r = path_to(b, spot)
            for t in r or []:
                b[t] = "Path"
                plan.append((t, "Path", "the key room"))
            if r is not None:
                b[spot] = "Key Room"
                plan.append((spot, "Key Room", "the key room"))
                key_needed = False
        else:
            notes.append("No free spot for the key room: placed now, it opens on the next run.")
    # 3. the rooms in hand, the ones others go beside first
    fams = list(spare)                                 # (the room cards not used to join something)
    from collections import Counter
    card_left = Counter(h[1] for h in hand if h and h[0] == "room")
    med_left = Counter(f for f in medal_rooms if f)
    for _t, f, w in plan:                              # (a room already used to join something)
        if w.startswith("joins "):
            if card_left.get(f, 0) > 0:
                card_left[f] -= 1
            else:
                med_left[f] -= 1
    ups = sum(1 for m in medals or () if m and M.base(m)[0] == "Quipolatl's Medallion")
    locks = sum(1 for m in medals or () if m and M.base(m)[0] == "Juatalotli's Medallion")
    order = sorted(fams, key=lambda f: (FIRST.index(f) if f in FIRST else 99, -VALUE.get(f, 0)))
    # 3.0.7 (round 14: two Thaumaturge medallions went down and the Corruption Chamber found no square left beside
    # them): the chain goes down together - a Thaumaturge, the Corruption Chamber beside it, then the next one
    if "Thaumaturge" in order and "Corruption Chamber" in order:
        k = order.index("Thaumaturge")
        ccs = [f for f in order if f == "Corruption Chamber"]
        order = [f for f in order if f != "Corruption Chamber"]
        order[k + 1:k + 1] = ccs
    rest = list(order)
    leads = []
    for fam in order:
        rest.remove(fam)
        best = None
        edges = edge_blocks(b)
        lead = any(p in rest for p in (ANCHORS.get(fam) or PARTNER.get(fam) or ()))
        for t in sorted({n for c in network(b) for n in near(c)}):
            s = _room_score(b, t, fam, rest, lane, arch, key_needed, keep, edges, ups)
            if s is not None and lead and _room_for(b, t, lane) < 1:
                continue                               # (a square beside it, free and off the ✕ squares, for its partner)
            if s is not None and (best is None or s > best[0]):
                best = (s, t)
        if best is None:
            continue
        pals = [b.get(n) for n in near(best[1]) if b.get(n) in PARTNER.get(fam, ()) + tuple(TOUCH.get(fam, ()))]
        med = med_left.get(fam, 0) > card_left.get(fam, 0)          # (cards are placed first, medallions after)
        if med and fam in ("Corruption Chamber", "Sacrificial Chamber") and not (
                ups and (locks or fam != "Corruption Chamber")) and gain(b, best[1], fam) < 2:
            # (two rooms beside it that raise it take it to tier 3 without an Upgrade - the owner's Alchemy Lab went
            # 1 -> 3 between two Thaumaturges)
            # 3.0.6 (owner: "I need an upgrade medallion before placing the corruption chamber otherwise it's wasted")
            # 3.0.7 (owner: "I will place the corruption chamber and thaumaturge, upgrade corruption chamber and lock
            # it so I get 2 runs out of it which is 2 guaranteed architect's orbs"): an Upgrade and a Lock first
            if fam == "Corruption Chamber":
                notes.append(f"Keep the {fam} medallion until you hold an Upgrade and a Lock.")
                why_cc = "Corruption Chamber: upgraded and locked, it pays 2 runs (2 Architect's Orbs)."
                if why_cc not in notes:
                    notes.append(why_cc)
            else:
                notes.append(f"Keep the {fam} medallion until you hold an Upgrade: it pays at tier 3.")
            med_left[fam] -= 1
            continue
        if med and pals and best[0] < 0:
            # 3.0.6 (owner: the Golem Works medallion would loop back into the gold path; the two tier-2 Smithies
            # beside it can take the upgrade medallions instead): only a loop left - it waits for a better board
            notes.append(f"Keep the {fam} medallion: here it only loops back into your paths.")
            med_left[fam] -= 1
            continue
        anchor = med and fam in ANCHORS and any(
            p in rest and (p != "Corruption Chamber" or (ups and locks)) for p in ANCHORS[fam])
        if not pals and (med or fam in KEEP_ALONE) and not anchor:
            # (3.0.7: a Thaumaturge medallion is the anchor when what it raises is in hand and goes down too)
            # 3.0.6 (owner: "commanders should be saved for the next run (especially if it's a medallion, it can be
            # paired with a garrison ...)"): a medallion room - or a Commander - with nothing beside it to raise it
            # waits for a run where it has its partner
            mate = (sorted(TOUCH.get(fam) or ()) or list(PARTNER.get(fam) or ()) or ["partner"])[0]
            notes.append(f"Keep the {fam}{' medallion' if med else ''} for a run with a {mate} to sit beside.")
            if med:
                med_left[fam] -= 1
            else:
                card_left[fam] -= 1
            continue
        if card_left.get(fam, 0) > 0:
            card_left[fam] -= 1
        else:
            med_left[fam] = med_left.get(fam, 0) - 1
        b[best[1]] = fam
        plan.append((best[1], fam, ("beside " + pals[0]) if pals else "joined to your rooms"))
        if lead and not pals and med and fam in ANCHORS:
            leads.append((best[1], fam))
    for t, fam in leads:
        # 3.0.7 (owner: "I'm saving my medallions for next run when I have empty space to work with"): a
        # Thaumaturge medallion put down for its partner, and the partner found no clean square - both wait
        if not any(b.get(n) in ANCHORS[fam] for n in near(t)):
            plan[:] = [x for x in plan if x[0] != t]
            b.pop(t, None)
            notes.append(f"Keep the {fam} medallion: no clean square beside it for the "
                         f"{ANCHORS[fam][0]} now.")
    # the Architect's reward cards (owner's picture: the side walls, every other square): touching nothing at all
    rewards = [h for h in hand if h and h[0] == "reward"]
    kr = next((t for t, v in b.items() if v == "Key Room"), None)
    if rewards and kr is not None and kr not in network(b):
        # 3.0.7 (owner: "where the key room is by itself and has an option to connect a reward room to it, it's okay
        # to place it beside it as long as it doesn't connect to other reward rooms. I will take a currency vault"):
        # one vault beside the lone key room - touching no other reward room and nothing else of yours, off the
        # square that joins the key room to your paths; a currency vault (Kishara's Vault) first
        pn = path_network(b)
        spots = [n for n in near(kr) if not b.get(n) and inside(n) and n not in LANE and n not in keep and
                 n not in (ATZIRI, ENTRANCE) and not any(n in near(c) for c in pn) and
                 not any(b.get(m) not in (None,) for m in near(n) if m != kr)]
        if spots:
            n = min(spots, key=lambda t: (min(abs(t[0] - c[0]) + abs(t[1] - c[1]) for c in pn), t[1]))
            h = next((h for h in rewards if h[1] == CURRENCY_VAULT), rewards[0])
            rewards.remove(h)
            b[n] = "Reward"
            plan.append((n, h[1], "beside the key room: joins with it"))
    rewards.sort(key=lambda h: h[1] != CURRENCY_VAULT)       # (owner: a currency vault where he can reach it)
    for h in rewards:
        # (a side-wall square first; walls full: any square) - touching no path or room, so it isn't open yet
        # (an open restricted room always goes on exit); beside another reward room is fine
        def free_of_yours(t):
            return not b.get(t) and inside(t) and t not in keep and t not in LANE and \
                not any(b.get(n) not in (None, "Reward") or n in (ENTRANCE, ATZIRI) for n in near(t))
        cells = [(i, j) for i in range(-4, 5) for j in range(1, 10)]
        # 3.0.7 (owner: "I also placed a currency vault on the opposite side because I can safely access it and
        # connect to it next run without breaking my outside 'block' rooms along the walls"): a square a later path
        # can reach safely first
        spot = next((t for t in sorted(cells, key=lambda t: (not reachable_later(b, t, keep), abs(t[0]) != 4,
                                                             -sum(1 for n in near(t) if not b.get(n)), abs(t[1] - 5)))
                     if free_of_yours(t)), None)
        if spot is None:
            if not any(n.startswith("No free square") for n in notes):
                notes.append("No free square away from your paths for the vault cards.")
            continue
        b[spot] = "Reward"
        plan.append((spot, h[1], "a reward room: touches nothing"))
    if restricted:                                   # (nothing else can be done at his console)
        return {"plan": plan, "targets": {}, "notes": notes[:2], "chains": chains, "path_cards": path_cards}
    # conversions (cheat sheet)
    for t, fam, _w in list(plan):
        if fam in ("Synthflesh Lab", "Spymaster") and "Garrison" in [b.get(n) for n in near(t)]:
            notes.append(f"The {fam} turns the Garrison beside it into "
                         f"{'Transcendent Barracks' if fam == 'Synthflesh Lab' else 'a Legion Barracks'}.")
    # #5 (owner: "using up all of the cards in my hand and creating filler for when destabilization happens to reduce
    # chances of my good rooms getting deleted, creating intentional loop of paths"): spare path cards, path to path
    while pcards:
        pn = path_network(b)
        best = None
        for t in sorted({n for c in pn for n in near(c)}):
            if b.get(t) or not inside(t) or t in (ATZIRI, ENTRANCE) or touches_reward(b, t) or t in keep:
                continue
            if arch is not None and t in near(arch) and sum(1 for n in near(arch) if not b.get(n)) <= 1:
                continue                               # (his last free side)
            card_ = next((c for c in pcards if path_fits(b, t, c[1])), None)
            if card_ is None:
                continue                               # (3.0.7: no Path card left whose shape fits here)
            # 3.0.6, from 12 destabilisations on the owner's boards (Temple Watcher shots): a dead end (one
            # neighbor) was lost 67% of the time, a tile in the middle of a chain 28%; nothing was ever left cut
            # off. So a spare path goes where it turns a valuable room's dead end into a middle (a guard) - else
            # out on its own as a dead end of its own (a decoy: it draws the loss), not into a loop
            guard = sum(1 for n in near(t) if b.get(n) in ROOMS and _worth_keeping(b, n, board) and
                        _ends(b, n) <= 1)
            sc = guard * 12 + (3 if _ends(b, t) == 0 else 0) - sum(1 for n in near(t) if n in pn) * 2 - \
                (5 if arch is None and quadrant(t) in ("top", "right") else 0) - abs(t[0]) * 0.1
            if best is None or sc > best[0]:
                best = (sc, t, card_[0])
        if best is None:
            if any(c[1] for c in pcards):
                notes.append("Your other Path cards fit nowhere useful now: keep them.")
            break
        put_path(best[1], best[2])
        plan.append((best[1], "Path", "filler"))
    if key_needed and arch is None and keyroom is None and not landing(b, "bottom"):
        notes.append("Keep the bottom quadrant clear: the key room needs a free spot there.")
    left = dead_ends(b, board)
    if left:
        fams = sorted({b[t] for t in left})
        notes.insert(0, f"{', '.join(fams)} at a dead end: dead ends are lost most - put a cheap room or a path "
                        f"beside it, or lock it.")
    # medallions: where the upgrade and the lock go; a reroll when nothing in hand pays
    held = [M.base(m)[0] for m in medals or () if m]
    rooms = {t: v for t, v in taken.items() if v in ROOMS}      # (placed rooms only: a medallion goes on a real one)

    def used_up(t, f):
        """3.0.6 (owner: "if a room is a t2 without it's connected upgrade room, it means it was already upgraded with
        a medallion and cannot be upgraded anymore unless via room connection"): higher than its neighbors make it."""
        raised = sum(1 for n in near(t) if rooms.get(n) in TOUCH.get(f, ()))
        return tier_of(board, t) > 1 + raised

    def best_room(pref, need_up):
        cand = [(t, f) for t, f in rooms.items() if f in pref and t not in targets and not (need_up and used_up(t, f))
                and not (need_up and tier_of(board, t) >= min(3, _tiers(f)))]
        # (3.0.6, owner's board: both tier-2 Smithies beside the Golem Works took the two upgrades) - closest to tier
        # 3 first, then a room in a chain (something beside it raises it), then the room that pays most
        # 3.0.6 (owner: "Corruption chamber takes upgrade + lock priority over everything else")
        cand.sort(key=lambda x: (x[1] != "Corruption Chamber", 3 - tier_of(board, x[0]) if need_up else 0,
                                 -gain(rooms, x[0], x[1]), pref.index(x[1]), -tier_of(board, x[0])))
        return cand[0] if cand else None

    # 3.0.7 (round 14, owner: "it wants me to upgrade the flesh surgeon, that's like way low priority, I'm saving the
    # upgrade for the next corruption chamber upgrade"; "the t3/t4 barracks and synthflesh were useless and offered
    # no reward ... not worth upgrading"; "why is it suggesting I upgrade the generator/dynamo?"): an Upgrade goes to
    # a room that pays (the Corruption Chamber first); a Corruption Chamber in hand keeps one Upgrade back for it; the
    # Flesh Surgeon only when no Corruption Chamber is in play; no use = keep it for next run
    cc_hand = sum(1 for h in hand if h and h == ("room", "Corruption Chamber")) + \
        sum(1 for f in medal_rooms or () if f == "Corruption Chamber")
    cc_play = cc_hand or any(f == "Corruption Chamber" for f in rooms.values())
    unknown = any(m is None for m in medals or ())      # (a medallion not read could be a Corruption Chamber)
    pref = tuple(f for f in UPGRADE_FIRST if not ((cc_play or unknown) and f in UPGRADE_LOW))
    ups_held = held.count("Quipolatl's Medallion")
    kept_for_cc = 0
    for _k in range(ups_held):                      # (3.0.6: each upgrade medallion held, its own room)
        up = best_room(pref, True)
        if up and up[1] != "Corruption Chamber" and kept_for_cc < cc_hand:
            kept_for_cc += 1                        # (one back for each Corruption Chamber still in hand)
            continue
        if not up:
            if cc_play:
                kept_for_cc += 1
            break
        targets[up[0]] = ("Upgrade", up[1])
    spent = sum(1 for w, _f in targets.values() if w == "Upgrade")
    if ups_held > spent:
        notes.append("Keep the Upgrade for the Corruption Chamber." if cc_play else
                     "Keep the Upgrade for next run: nothing here pays for it.")
    if "Juatalotli's Medallion" in held and rooms:
        # (owner: upgrade the Corruption Chamber to tier 3, then lock it - the room that pays, highest tier first)
        # 3.0.7 (owner: "upgrade corruption chamber and lock it so I get 2 runs out of it which is 2 guaranteed
        # architect's orbs"): a Corruption Chamber, else a paying room at tier 3; nothing like that = keep it
        ok = [x for x in rooms.items() if x[1] == "Corruption Chamber" or
              (x[1] in pref and x[1] not in UPGRADE_LOW and tier_of(board, x[0]) >= 3)]
        lk = max(ok, key=lambda x: (x[1] == "Corruption Chamber", tier_of(board, x[0]),
                                    -UPGRADE_FIRST.index(x[1]) if x[1] in UPGRADE_FIRST else 0), default=None)
        if lk is None:
            notes.append("Keep the Lock for the Corruption Chamber." if cc_play else
                         "Keep the Lock for next run: nothing here pays for it.")
        elif lk[0] not in targets:
            targets[lk[0]] = ("Lock", lk[1])
        else:
            notes.append(f"Lock the {lk[1]} after its upgrade.")
    card_fams = [h[1] for h in hand if h and h[0] == "room"]
    pays = any(VALUE.get(f, 0) >= PAYS or any(v in TOUCH.get(f, ()) or v in PARTNER.get(f, ()) for v in rooms.values())
               for f in card_fams)
    if card_fams and "Puhuarte's Medallion" in held and not pays:
        notes.append("Nothing in your cards pays: reroll them (Puhuarte's Medallion).")
    # (owner: AuDHD - one line, not five): the medallions kept for a later run, together
    keep_meds = [n.split("Keep the ")[1].split(" medallion")[0] for n in notes
                 if n.startswith("Keep the ") and " medallion" in n]
    if len(keep_meds) > 1:
        notes = [n for n in notes if not (n.startswith("Keep the ") and " medallion" in n)]
        notes.append("Keep for next run: " + ", ".join(keep_meds) + " medallions.")
    # 3.0.7 (owner: "we need to factor for chains/snakes and have a more clear method of explaining what we're doing
    # to place those, with built in protections of the x rooms not to connect to"): one plain line per chain
    for t, fam, why in plan:
        if why.startswith("beside ") and fam in ROOMS and len(chains) < 4:
            chains.append(f"{fam} beside the {why[7:]}: they raise each other.")
    if any(not c.startswith("Path to") for c in chains):
        chains.append("No chain touches a ✕ square (a reward room).")
    return {"plan": plan, "targets": targets, "notes": notes, "chains": chains, "path_cards": path_cards}
