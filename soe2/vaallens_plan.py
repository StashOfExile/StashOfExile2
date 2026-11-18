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
    if difflib.get_close_matches(low, PATHS, 1, 0.85):
        return ("path", None)
    m = difflib.get_close_matches(low, list(FAMILY), 1, 0.85)
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
            if n not in seen and taken.get(n) and taken[n] not in ("Architect", "Atziri", "Reward", "?"):
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
    for t in lit:
        if touches_reward(taken, t, kind):
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
    """An OCR'd card name ("THAUMATURGE'S LABORATORY") -> as the game prints it ("Thaumaturge's Laboratory")."""
    low = " ".join(str(name or "").lower().replace("’", "'").split())
    for fam, names_ in ROOMS.items():
        for n in names_:
            if n.lower() == low:
                return n
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
    shown = set()
    for k, (t, f, _w) in enumerate(plan):
        if t not in out:
            num = st[k] if st[k] not in shown else None     # (3.0.6: a path's step number on its first tile only)
            shown.add(st[k])
            out[t] = ("p", (num, "path" if f == "Path" else ("Royal Access Chamber" if f == "Key Room" else f)))
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

VALUE = {"Thaumaturge": 10, "Corruption Chamber": 9, "Sacrificial Chamber": 8, "Flesh Surgeon": 8, "Alchemy Lab": 7,
         "Synthflesh Lab": 6, "Smithy": 6, "Generator": 5, "Golem Works": 4, "Armoury": 4, "Garrison": 3,
         "Commander": 3, "Spymaster": 2, "Transcendent Barracks": 2, "Sealed Vault": 1}
PAYS = 6                                     # a room worth placing for itself (VALUE >= PAYS) - below that, filler
PARTNER.setdefault("Flesh Surgeon", ("Synthflesh Lab",))      # owner: tier-3 Flesh Surgeon (limbs) beside Synthflesh
PARTNER.setdefault("Synthflesh Lab", ("Flesh Surgeon",))
# rooms that others are placed beside: placed first, so their partners have room
FIRST = ("Thaumaturge", "Synthflesh Lab", "Smithy", "Corruption Chamber", "Sacrificial Chamber", "Alchemy Lab",
         "Flesh Surgeon", "Generator", "Golem Works", "Armoury", "Garrison", "Commander", "Spymaster")
UPGRADE_FIRST = ("Corruption Chamber", "Sacrificial Chamber", "Flesh Surgeon", "Alchemy Lab", "Smithy",
                 "Synthflesh Lab", "Generator", "Garrison")


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


def path_to(b, goal):
    """The free tiles a path needs from your joined tiles to goal (fewest, none beside a reward room, off the
    Architect's and the key room's landing squares when it can); [] already joined; None no safe way."""
    net = network(b)
    if any(n in net for n in near(goal)):
        return []
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
            if b.get(n) or n in (ATZIRI, ENTRANCE) or touches_reward(b, n):
                continue
            best[n] = c
            q.append(n)
    return None


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


def _room_score(b, t, fam, rest, lane, arch, key_needed):
    """How good t is for a room of fam (None: not allowed). rest: rooms still to place (their partners count)."""
    if b.get(t) or t in (ATZIRI, ENTRANCE) or not inside(t) or touches_reward(b, t) or t in lane:
        return None
    if not any(n in network(b) for n in near(t)):
        return None
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
    q = quadrant(t)
    score += {"left": 8, None: 0}.get(q, 0)
    if q == "bottom" and key_needed:
        score -= 25                                   # the key room's landing quadrant
    if q in ("top", "right"):
        score -= 20                                   # the Architect's (he switches sides run to run)
    if arch and any(n == arch for n in near(t)):
        score -= 40                                   # his one free square on each side
    if _loops(b, t):
        score -= 30
    return score - abs(t[0]) * 0.1


def full_plan(board, cards=(), medals=(), medal_rooms=()):
    """board: a read board; cards: the room card names in the list; medals: medallion names held (None = not known);
    medal_rooms: room families the medallions add. -> {"plan": [(tile, family, why)] in order, "targets":
    {tile: ("Upgrade" | "Lock", family)}, "notes": [str]}."""
    from . import medallions as M
    taken = names(board)
    b = dict(taken)
    lane = spine(taken)
    plan, notes, targets = [], [], {}
    keyroom = next((c for c, v in taken.items() if v == "Key Room"), None)
    arch = next((c for c, v in taken.items() if v == "Architect"), None)
    hand = [card(n) for n in cards or ()]
    key_card = any(h and h[0] == "key" for h in hand)

    def add_path(goal, why):
        r = path_to(b, goal)
        if r is None:
            notes.append(f"No safe path to {why} yet.")
            return False
        for t in r:
            b[t] = "Path"
            plan.append((t, "Path", why))
        return True

    # 1. the key room and Atziri, before anything else
    if keyroom is not None:
        add_path(keyroom, "the key room")
        add_path(ATZIRI, "Atziri")
    # 2. the Architect
    if arch is not None:
        add_path(arch, "the Architect")
    # the key room card in hand (after the Architect): a clean spot in the bottom quadrant
    key_needed = keyroom is None
    if key_card:
        spot = landing(b, "bottom") or next((t for t in (landing(b, q) for q in ("left", "top", "right")) if t), None)
        if spot and any(n in network(b) for n in near(spot)):
            b[spot] = "Key Room"
            plan.append((spot, "Key Room", "the key room"))
            key_needed = False
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
    fams = [h[1] for h in hand if h and h[0] == "room"] + [f for f in medal_rooms if f]
    order = sorted(fams, key=lambda f: (FIRST.index(f) if f in FIRST else 99, -VALUE.get(f, 0)))
    rest = list(order)
    for fam in order:
        rest.remove(fam)
        best = None
        for t in {n for c in network(b) for n in near(c)}:
            s = _room_score(b, t, fam, rest, lane, arch, key_needed)
            if s is not None and (best is None or s > best[0]):
                best = (s, t)
        if best is None:
            continue
        b[best[1]] = fam
        pals = [b.get(n) for n in near(best[1]) if b.get(n) in PARTNER.get(fam, ()) + tuple(TOUCH.get(fam, ()))]
        plan.append((best[1], fam, ("beside " + pals[0]) if pals else "joined to your rooms"))
    if key_needed and arch is None and keyroom is None and not landing(b, "bottom"):
        notes.append("Keep the bottom quadrant clear: the key room needs a free spot there.")
    # medallions: where the upgrade and the lock go; a reroll when nothing in hand pays
    held = [M.base(m)[0] for m in medals or () if m]
    rooms = {t: v for t, v in b.items() if v in ROOMS}

    def best_room(pref, need_up):
        cand = [(t, f) for t, f in rooms.items() if f in pref and not (need_up and tier_of(board, t) >= min(3, _tiers(f)))]
        cand.sort(key=lambda x: (pref.index(x[1]), -tier_of(board, x[0])))
        return cand[0] if cand else None

    if "Quipolatl's Medallion" in held:
        up = best_room(UPGRADE_FIRST, True)
        if up:
            targets[up[0]] = ("Upgrade", up[1])
    if "Juatalotli's Medallion" in held and rooms:
        # (owner: upgrade the Corruption Chamber to tier 3, then lock it - the room that pays, highest tier first)
        lk = max(rooms.items(), key=lambda x: (x[1] in UPGRADE_FIRST, tier_of(board, x[0]),
                                                -UPGRADE_FIRST.index(x[1]) if x[1] in UPGRADE_FIRST else 0))
        if lk[0] not in targets:
            targets[lk[0]] = ("Lock", lk[1])
        else:
            notes.append(f"Lock the {lk[1]} after its upgrade.")
    card_fams = [h[1] for h in hand if h and h[0] == "room"]
    pays = any(VALUE.get(f, 0) >= PAYS or any(v in TOUCH.get(f, ()) or v in PARTNER.get(f, ()) for v in rooms.values())
               for f in card_fams)
    if card_fams and "Puhuarte's Medallion" in held and not pays:
        notes.append("Nothing in your cards pays: reroll them (Puhuarte's Medallion).")
    return {"plan": plan, "targets": targets, "notes": notes}
