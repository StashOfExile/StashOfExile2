"""Game Search's item cards (3.0.6): the raw export text of a row turned into what a card shows - its kind, its
properties as label / value pairs, "Requires Level N", its mods or effects one per line, and readable tag chips.
RePoE's units are fixed here too: a movement speed penalty is in basis points (-500 is -5%). Pure functions (no window):
tests/test_gamecards.py. The raw tags stay searchable (gamesearch keeps them in the row); a card only shows words."""
import re

MINUS = "−"
# a leading property of an armour, shield or jewel row: "Armour 45 Evasion 10 Block 26 Movement Speed -500"
PROP_LABELS = ("Energy Shield", "Movement Speed", "Armour", "Evasion", "Block", "Ward", "Spirit")
_PROP = re.compile(r"^(" + "|".join(PROP_LABELS) + r")\s+(-?\d+(?:\.\d+)?)\s*")
_REQ = re.compile(r"\bRequires level (\d+)", re.I)
_LIMIT = re.compile(r"\bLimit: (\d+)")
_GRANTS = re.compile(r"\bGrants skill: (\S+)")
_USE = re.compile(r"\s+(?=Right[ -]click)")
NUM = re.compile(r"[+\-−]?\(?\d[\d,]*(?:\.\d+)?(?:\s?[\-–—]\s?\d[\d,]*(?:\.\d+)?)?\)?%?")

ATTR = {"str_armour": "Strength", "dex_armour": "Dexterity", "int_armour": "Intelligence",
        "str_dex_armour": "Strength/Dexterity", "str_int_armour": "Strength/Intelligence",
        "dex_int_armour": "Dexterity/Intelligence", "str_dex_int_armour": "Strength/Dexterity/Intelligence",
        "strjewel": "Strength", "dexjewel": "Dexterity", "intjewel": "Intelligence"}
WORDS = {"onehand": "One-Handed", "twohand": "Two-Handed", "ranged": "Ranged", "warstaff": "Quarterstaff",
         "sanctum_relic": "Relic", "small_sanctum_relic": "Small Relic", "medium_sanctum_relic": "Medium Relic",
         "large_sanctum_relic": "Large Relic"}
# internal tags nobody reads: a card never shows them (they stay searchable)
_HIDDEN = re.compile(r"(_basetype$|^default$|^not_for_sale$|^demigods$|^no_\w+_mods$|^armour$|^weapon$|^one_hand_weapon$|"
                     r"^two_hand_weapon$|^tower_augment|^currency$|^str_shield$|^dex_shield$|^int_shield$|^metadata|"
                     r"_armour$|^all_sentinels$|^sentinel_drone$|^ezomyte|^expedition_logbook$)")


def humanize(word):
    """'StackableCurrency' -> 'Stackable Currency'; 'map_key_low' -> 'Map Key Low'"""
    w = WORDS.get(word)
    if w:
        return w
    w = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word).replace("_", " ").strip()
    return " ".join(x[:1].upper() + x[1:] for x in w.split())


def attribute(tags):
    for t in tags:
        if t in ATTR:
            return ATTR[t]
    return ""


def chips(tag_text, skip=()):
    """The readable tag words of a row, in order, none twice, the internal ones left out."""
    out = []
    for t in [x.strip() for x in (tag_text or "").split(",")]:
        if not t or _HIDDEN.search(t) and t not in ATTR:
            continue
        w = ATTR.get(t) or humanize(t)
        if w and w not in out and w.lower() not in {s.lower() for s in skip}:
            out.append(w)
    return out


def speed(bp):
    """RePoE stores a movement speed penalty in basis points: -500 -> '−5%'."""
    v = float(bp) / 100
    s = f"{abs(v):g}%"
    return (MINUS if v < 0 else "+") + s


def prop_value(label, raw):
    if label == "Movement Speed":
        return speed(raw)
    if label == "Block":
        return f"{float(raw):g}%"
    return f"{float(raw):g}"


def skill_name(path):
    """'Metadata/Items/Gems/SkillGemChaosbolt' -> 'Chaosbolt'"""
    n = path.rsplit("/", 1)[-1]
    n = re.sub(r"^SkillGem", "", n)
    return humanize(n) if n else path


def parse_text(text):
    """-> (props [(label, value)], requires 'Requires Level N' or '', lines [str], muted_lines [str])"""
    props, req, lines, muted = [], "", [], []
    parts = [p for p in (text or "").split(" | ") if p.strip()]
    for part in parts:
        part = part.strip()
        m = re.fullmatch(r"ilvl (\d+)", part)
        if m:
            props.append(("Item Level", m.group(1)))
            continue
        m = re.fullmatch(r"can roll on: (.*)", part)
        if m:
            props.append(("Rolls on", ", ".join(dict.fromkeys(ATTR.get(x) or humanize(x) for x in m.group(1).split(", ")))))
            continue
        while True:
            m = _PROP.match(part)
            if not m:
                break
            props.append((m.group(1), prop_value(m.group(1), m.group(2))))
            part = part[m.end():]
        m = _REQ.search(part)
        if m:
            req = f"Requires Level {m.group(1)}"
            part = (part[:m.start()] + part[m.end():]).strip()
        m = _LIMIT.search(part)
        if m:
            props.append(("Limit", m.group(1)))
            part = (part[:m.start()] + part[m.end():]).strip()
        m = _GRANTS.search(part)
        if m:
            props.append(("Grants skill", skill_name(m.group(1))))
            part = (part[:m.start()] + part[m.end():]).strip()
        if part:
            bits = _USE.split(part)
            lines.append(bits[0])
            muted += bits[1:]
    return props, req, lines, muted


def card(it):
    """A Game Search row -> {kind, props, req, lines, muted, chips, db} (cached on the row)."""
    c = it.get("_card")
    if c:
        return c
    tags = [x.strip() for x in (it.get("k") or "").split(",")]
    cls = it.get("c") or ""
    if it.get("db"):
        props = [tuple(p) for p in it.get("props") or []]
        c = {"kind": cls, "props": props, "req": "", "lines": list(it.get("lines") or []), "muted": [],
             "chips": [humanize(w) if "_" in w else w[:1].upper() + w[1:]
                       for w in dict.fromkeys(x.strip() for x in (it.get("k") or "").split(","))
                       if w and not _HIDDEN.search(w) and w.lower() not in (cls.lower(),) + tuple(cls.lower().split())],
             "db": True}
    else:
        props, req, lines, muted = parse_text(it.get("t") or "")
        attr = attribute(tags)
        kind = humanize(cls) if cls and " " not in cls and "(" not in cls else cls
        c = {"kind": kind + (f" · {attr}" if attr else ""), "props": props, "req": req, "lines": lines, "muted": muted,
             "chips": chips(it.get("k"), skip=(cls, humanize(cls), attr)), "db": False}
        if it.get("g") == "Modifiers":                        # a mod row's tags are its stat group ids: one chip each is noise
            c["chips"] = c["chips"][:3]
    it["_card"] = c
    return c


def segments(text):
    """text -> [(piece, is_number)]: numbers, ranges and percents are marked so a card can highlight them."""
    out, pos = [], 0
    for m in NUM.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out
