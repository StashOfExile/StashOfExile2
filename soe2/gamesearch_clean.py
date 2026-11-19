"""Game Search: what never reaches a player (pure functions, no window; tests/test_gamesearch_clean.py).

The game's export carries developer-only items and text: "[DNT]" / "[DNT-UNUSED]" ("do not translate") entries, test
gems ("Playtest Attack"), placeholder descriptions ("DNT Description", "Fill me in") and UI markup
("<<ExpedRuneFire>><rgb(219,217,206)>{Fire Rune} ..."). The loader (gamesearch.load) runs every row through here, so a
new data pack stays clean without a rebuild; tools/build_searchdata.py uses the same rules.
A row can also be left out by name in gamedb_hide.json: {"name": "Fishing Rod", "group": "Other Items", "reason": "..."}."""
import re

# a developer-only name: [DNT], [DNT-UNUSED], [DNT-Unused], "UNUSED", the "Playtest ..." gems
DEV_NAME = re.compile(r"\bDNT\b|\bUNUSED\b|^Playtest\b|\bPew pew\b", re.I)
# a name that is a code identifier (no space, a lower-to-upper hump twice or more): "MistRavenCompanionSwoop"
CODE_NAME = re.compile(r"^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+){2,}$")
# rows about the app's own data files (gamedb.json's "Game data: campaign.json"): not part of the game, never shown
APP_ROWS = ("Data File Version",)
GEM_GROUPS = ("Skill Gems", "Support Gems", "Spirit Gems")

_MARK = re.compile(r"\bDNT(?:-UNUSED)?\b[:\s]*", re.I)
_NOTE = re.compile(r"(?:Fill me in|Fill this in|Description|Ring Ring but small|Ezomyte Four)\s*", re.I)
_CODE_WORD = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")                    # triggered_hoarfrost
_TAGS = re.compile(r"<<[^>]*>>|<[A-Za-z]+(?::'?[^>]*)?(?:\([^)]*\))?>")      # <<Id>> <rgb(1,2,3)> <font:'x'> <italic>
_BRACED = re.compile(r"\{([^{}]*)\}")


def is_dev_name(name):
    n = (name or "").strip()
    return bool(DEV_NAME.search(n) or (" " not in n and CODE_NAME.match(n)))


def strip_markup(text):
    """The game's own text markup -> plain lines (' | ' apart): the first braced word is the title (dropped when it is
    the row's name - the caller checks), 'Monsters gain:' starts a group, the braced items after it follow, comma apart.
    '<<ExpedRuneFire>><rgb(1)>{Fire Rune} <font:'x'>{<italic>{<rgb(2)>{Monsters gain:}}} <rgb(3)>{Extra Fire Damage}'
    -> 'Fire Rune | Monsters gain: Extra Fire Damage'"""
    if "<" not in text and "{" not in text:
        return text
    words = [w.strip() for w in _BRACED.findall(_TAGS.sub(" ", text).replace("{<", "{").replace(">{", "{"))]
    if not words:
        words = [re.sub(r"[{}]", "", _TAGS.sub(" ", text)).strip()]
    out, group = [], None
    for w in words:
        if not w:
            continue
        if w.endswith(":"):
            group = [w]
            out.append(group)
        elif group is not None:
            group.append(w)
        else:
            out.append([w])
    lines = []
    for g in out:
        lines.append(g[0] if len(g) == 1 else g[0] + " " + ", ".join(g[1:]))
    return " | ".join(lines)


def clean_text(text):
    """A row's text without markers, placeholders, markup and stray spaces. Idempotent."""
    t = strip_markup(text or "")
    parts = []
    for p in t.split(" | "):
        if re.search(r"\bDNT", p):
            p = _MARK.sub(" ", _CODE_WORD.sub("", p)).strip()
            while _NOTE.match(p):                           # a placeholder note a marker left ("Fill me in")
                p = _NOTE.sub("", p, count=1).strip()
        p = re.sub(r"\s{2,}", " ", p).strip()
        if p:
            parts.append(p)
    return " | ".join(parts)


def hide_names(entries):
    """The hide list's {"name", "group"} entries -> {(name, group or None)}."""
    return {(e["name"], e.get("group")) for e in entries or [] if isinstance(e, dict) and e.get("name")}


def keep(row, hidden=()):
    """False for a row a player should never see: developer-only, a gem nobody wrote a description for, or hidden by name."""
    n = (row.get("n") or "").strip()
    if not n or is_dev_name(n) or row.get("c") in APP_ROWS:
        return False
    if (n, row.get("g")) in hidden or (n, None) in hidden:
        return False
    if row.get("g") in GEM_GROUPS and not clean_text(row.get("t") or ""):
        return False                                       # (an unfinished gem: no description at all)
    return True


def clean_rows(rows, hidden=()):
    """Rows (dicts with n, g, c, k, t) -> the rows a player sees, their names and texts tidied. New dicts."""
    out = []
    for r in rows:
        if not keep(r, hidden):
            continue
        t = clean_text(r.get("t") or "")
        n = r["n"].strip()
        if "<" in (r.get("t") or "") and t.split(" | ")[0] == n:
            t = " | ".join(t.split(" | ")[1:])              # (the markup's title is the row's name)
        if t != r.get("t") or n != r["n"]:
            r = dict(r, n=n, t=t, ln=n.lower(), lt=t.lower()) if "ln" in r else dict(r, n=n, t=t)
        out.append(r)
    return out


def drop_dev_rows(rows):
    """For the build tool: [name, group, class, tags, text] rows -> (kept, dropped), same rules as the loader."""
    kept, dropped = [], []
    for r in rows:
        d = {"n": r[0], "g": r[1], "t": r[4]}
        (kept if keep(d) else dropped).append(r)
    return kept, dropped
