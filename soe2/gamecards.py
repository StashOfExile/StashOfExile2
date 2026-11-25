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
_GRANTS = re.compile(r"\bGrants skill: (\S+)")      # (replaced by _GRANTS_ALL: a list of skills)
_USE = re.compile(r"\s+(?=Right[ -]click)")
NUM = re.compile(r"[+\-−]?\(?\d[\d,]*(?:\.\d+)?(?:\s?[\-–—]\s?\d[\d,]*(?:\.\d+)?)?\)?%?")

ATTR = {"str_armour": "Strength", "dex_armour": "Dexterity", "int_armour": "Intelligence",
        "str_dex_armour": "Strength/Dexterity", "str_int_armour": "Strength/Intelligence",
        "dex_int_armour": "Dexterity/Intelligence", "str_dex_int_armour": "Strength/Dexterity/Intelligence",
        "strjewel": "Strength", "dexjewel": "Dexterity", "intjewel": "Intelligence",
        "str_radius_jewel": "Strength", "dex_radius_jewel": "Dexterity", "int_radius_jewel": "Intelligence"}
WORDS = {"onehand": "One-Handed", "twohand": "Two-Handed", "ranged": "Ranged", "warstaff": "Quarterstaff",
         "sanctum_relic": "Relic", "small_sanctum_relic": "Small Relic", "medium_sanctum_relic": "Medium Relic",
         "large_sanctum_relic": "Large Relic"}
# internal tags nobody reads: a card never shows them (they stay searchable)
NOT_SHOWN = ("Trade stat", "Implicit trade stat", "Trade filter",      # trade ids: not for reading
             "Area id", "Affix")                                      # the game's internal area id; "Affix" is the kind's last word
# the game's class words that are not what a player says
KIND_WORDS = {"Focii": "Focus", "Expedition2Logbooks": "Expedition Logbook", "Expedition2 Logbooks": "Expedition Logbook",
              "TowerAugmentation": "Tablet", "Tower Augmentation": "Tablet"}
SMALL = {"of", "the", "and", "or", "to", "in", "on", "for", "a"}
# a mod starts again where a bare "+(1-2)" / "(1-2)% increased" follows a word that ends a stat - unless the word before
# is a verb or a preposition that the number belongs to
_JOINERS = {"have", "has", "gain", "gains", "deal", "deals", "take", "takes", "grant", "grants", "to", "a", "of", "by", "from",
            "for", "with", "are", "is", "penetrate", "penetrates", "leech", "leeches", "causes", "cause", "regenerate",
            "recover", "revive", "prevent", "break", "spawn", "spawns", "costs", "cost", "allows", "expire", "drop",
            "applies", "contains", "reappear", "than", "per", "and", "or", "inflict", "gained"}
_SIGNED = re.compile(r"(\S+) (?=[+\-]\(\d)")
_RANGED = re.compile(r"(\S+) (?=\(\d[\d.]*-[\d.]+\)% (?:increased|reduced|more|less|Life Recovery)\b)")
_GLUE = re.compile(r"(?<=allowed) (?=[+\-]\d)|(?<=Map) (?=\d+ uses? remaining)|"
                   r" (?=Triggers all Socketed Spells and loses all Energy)")
_RUN = re.compile(r"(?:\b(?:Energy Shield|Movement Speed|Armour|Evasion|Block|Ward)\s+-?\d+(?:\.\d+)?\s*)+")
_GRANTS_ALL = re.compile(r"\bGrants skill: (.*)$")
_BOILER = "Triggers all Socketed Spells and loses all Energy on reaching maximum Energy"
_HIDDEN = re.compile(r"(_basetype$|^default$|^not_for_sale$|^demigods$|^no_\w+_mods$|^armour$|^weapon$|^one_hand_weapon$|"
                     r"^two_hand_weapon$|^tower_augment|^currency$|^str_shield$|^dex_shield$|^int_shield$|^metadata|"
                     r"_armour$|^jewel$|^radius_jewel$|^\w+jewel$|^\w+_radius_jewel$|^all_sentinels$|^sentinel_drone$|^ezomyte|^expedition_logbook$)")


def humanize(word):
    """'StackableCurrency' -> 'Stackable Currency'; 'map_key_low' -> 'Map Key Low'; 'IncreasedSpiritAndMana' ->
    'Increased Spirit and Mana'"""
    w = WORDS.get(word) or KIND_WORDS.get(word)
    if w:
        return w
    w = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word).replace("_", " ").strip()
    return nice(w)


def nice(text):
    """Title Case with the small words low: 'Trial of the sekhemas' -> 'Trial of the Sekhemas'."""
    words = text.split()
    return " ".join(x if x[:1].isdigit() else (x[:1].upper() + x[1:] if i == 0 or x.lower() not in SMALL else x.lower())
                    for i, x in enumerate(words))


def attribute(tags):
    """Every attribute the tags name, joined: a Diamond is 'Strength/Dexterity/Intelligence' (3.0.6: was the first)."""
    out = []
    for t in tags:
        for w in (ATTR.get(t) or "").split("/"):
            if w and w not in out:
                out.append(w)
    return "/".join(out)


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


def split_glued(part):
    """'+(1-2) to A +(3-4) to B' -> ['+(1-2) to A', '+(3-4) to B']: the export joins a row's mods with a space."""
    cuts = [m.end() - 1 for m in _GLUE.finditer(part)]
    for rx in (_SIGNED, _RANGED):
        cuts += [m.end() - 1 for m in rx.finditer(part) if m.group(1).lower().strip(",.:") not in _JOINERS]
    out, at = [], 0
    for c in sorted(set(cuts)):
        out.append(part[at:c].strip())
        at = c
    out.append(part[at:].strip())
    return [x for x in out if x]


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
            part = (part[:m.start()] + " " + part[m.end():]).strip()
        m = _GRANTS_ALL.search(part)                       # every skill it grants, by name
        if m:
            names = [skill_name(x.strip()) for x in m.group(1).split(",") if x.strip()]
            props.append(("Grants skill", ", ".join(dict.fromkeys(names))))
            part = part[:m.start()].strip()
        m = _LIMIT.search(part)
        if m:
            props.append(("Limit", m.group(1)))
            series = part[m.end():].strip()                # a rune's family ("Aldur's Legacy") follows its limit
            if series:
                props.append(("Series", series))
            part = part[:m.start()].strip()
        m = _RUN.search(part)                              # base stats glued after a mod: "... to Spirit Armour 218 ..."
        if m and m.start() > 0:
            for lab, val in re.findall(r"(Energy Shield|Movement Speed|Armour|Evasion|Block|Ward)\s+(-?\d+(?:\.\d+)?)", m.group(0)):
                props.append((lab, prop_value(lab, val)))
            part = (part[:m.start()] + " " + part[m.end():]).strip()
        for piece in split_glued(re.sub(r"\s{2,}", " ", part)):
            bits = _USE.split(piece)
            if bits[0].strip():
                lines.append(bits[0].strip())
            muted += [b.strip() for b in bits[1:] if b.strip()]
    lines = [x for x in dict.fromkeys(lines) if x != _BOILER or len(lines) == 1]      # no line twice; the Meta gem boilerplate
    return props, req, lines, muted                       # goes (its description says it already)


def _db_card(it, cls):
    props = [tuple(p) for p in it.get("props") or [] if p[0] not in NOT_SHOWN]    # (they stay in the row's text: searchable)
    lines = list(it.get("lines") or [])
    vals = ({str(v).lower() for _l, v in props} | {str(l).lower() for l, _v in props}
            | {str(l).split()[0].lower() for l, _v in props})
    # a line that only repeats the properties ("Dynamo → Shrine → ..." under Tier 1..4) is noise
    tiers = [str(v) for l, v in props if l.startswith("Tier ")]
    lines = [x for x in lines if not (tiers and "→" in x and all(v in x for v in tiers))]
    chips = []
    for w in dict.fromkeys(x.strip() for x in (it.get("k") or "").split(",")):
        if not w or _HIDDEN.search(w) or w.lower() in (cls.lower(),) + tuple(cls.lower().split()):
            continue
        c = humanize(w) if "_" in w else nice(w[:1].upper() + w[1:])
        if c.lower() not in vals:                          # (a tag that is a property's name or value says it twice)
            chips.append(c)
    return {"kind": cls, "props": props, "req": "", "lines": lines, "muted": [], "chips": chips, "db": True}


def unique_history(name):
    """3.3.0 owner: what a unique had before its last change, as muted lines on its card: "Before 0.4.0: ..."."""
    try:
        from . import gamesnap
        h = gamesnap.history(name)
    except Exception:
        return []
    if not h:
        return []
    patch, gone = h
    return [f"Before {patch}: {ln}" for ln in gone[:6]]


CHANGE_MARK = {"changed": "~ Changed:", "new": "+ New:", "removed": "− Removed:"}


def _change_card(it, cls):
    """A changed, new or removed unique or gem: each line with a mark and a word, the old number beside the new."""
    ov, nv = it.get("vs") or ("", "")
    lines = []
    for kind, now, was in it.get("chg") or []:
        lines.append(f"{CHANGE_MARK[kind]} {now}" + (f"   · was: {was}" if was else ""))
    status = it.get("chg_status") or "Changed"
    if status == "Removed":
        lines = [f"Not in the {nv} game files."]
    return {"kind": f"{cls} · {status} in {nv}", "props": [], "req": "", "lines": lines,
            "muted": ["Compared with the game data saved for the patch before."], "chips": [status],
            "db": False}


def card(it):
    """A Game Search row -> {kind, props, req, lines, muted, chips, db} (cached on the row)."""
    c = it.get("_card")
    if c:
        return c
    tags = [x.strip() for x in (it.get("k") or "").split(",")]
    cls = it.get("c") or ""
    if it.get("chg") is not None:                             # 3.3.0 owner: Changed in <patch>
        c = _change_card(it, cls)
    elif it.get("db"):
        c = _db_card(it, cls)
    else:
        props, req, lines, muted = parse_text(it.get("t") or "")
        attr = attribute(tags)
        kind = humanize(cls) if cls and " " not in cls and "(" not in cls else KIND_WORDS.get(cls, cls)
        if "radius_jewel" in tags:
            kind = "Radius Jewel"                             # 3.0.6: Time-Lost jewels say so in words, not tag chips
        if it.get("g") == "Unique Items":                     # the text only said "Unique <class>": that is the kind
            kind = f"Unique {KIND_WORDS.get(cls, cls)}"
            lines = [x for x in lines if x != f"Unique {cls}"] + list(it.get("ul") or [])
            muted = list(muted) + unique_history(it.get("n"))
        if it.get("gone"):                                   # kept by tools/update_game_data.py, never removed
            muted = list(muted) + [f"Not in the {it['gone']} files"]
        elif it.get("added"):
            muted = list(muted) + [f"New in {it['added']}"]
        c = {"kind": kind + (f" · {attr}" if attr else ""), "props": props, "req": req, "lines": lines, "muted": muted,
             "chips": chips(it.get("k"), skip=(cls, humanize(cls), *attr.split("/"))), "db": False}
        if it.get("g") == "Modifiers":                        # a mod row's tags are its stat group ids: one chip each is noise
            c["chips"] = c["chips"][:3]
        if it.get("a"):                                       # an anoint: its Liquid Emotions, not the search words
            c["chips"] = list(dict.fromkeys(it["a"]))
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
