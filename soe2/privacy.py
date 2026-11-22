"""2.89.2: never let personal details out. Error logs, problem reports and bug reports name files by their path, and
on Windows a path holds your user name (C:\\Users\\<you>\\...). scrub() swaps your home folder and user name for
neutral words before anything is written to a log or leaves the computer."""
import getpass
import os
import re


def _names():
    out = set()
    try:
        out.add(getpass.getuser())
    except Exception:
        pass
    for k in ("USERNAME", "USER", "LOGNAME"):
        if os.environ.get(k):
            out.add(os.environ[k])
    home = os.path.expanduser("~")
    if home and home != "~":
        out.add(os.path.basename(home.rstrip("\\/")))
    return {n for n in out if n and len(n) >= 2 and n.lower() not in ("root", "user", "admin", "public", "default")}


def scrub(text):
    """-> text with your home folder as ~ and your user name as <you> (any case, either slash)."""
    if not text:
        return text
    s = str(text)
    home = os.path.expanduser("~")
    for h in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
        if h and h not in ("~", "/", "\\"):
            s = re.sub(re.escape(h), "~", s, flags=re.I)
    s = re.sub(r"([\\/](?:Users|home|Documents and Settings)[\\/])[^\\/\r\n\"']+", r"\1<you>", s, flags=re.I)
    for n in _names():
        s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", "<you>", s, flags=re.I)
    return s


# ---------------------------------------------------------------- 2.89.3: names that point at a person
def known_names():
    """Every character name the app has seen (from the game's log) -> {name: placeholder}. Read only from this PC's
    settings; used to keep them OUT of logs, reports and the community name. (3.0.7: the app keeps no account name -
    anything shaped like one, Name#1234, is taken out by scrub_names.)"""
    out = {}
    try:
        from .config import SETTINGS
        chars = set()
        tr = SETTINGS.get("tracker") or {}
        chars |= {tr.get("character") or "", tr.get("character_guess") or ""}
        st = (SETTINGS.get("focus") or {}).get("state") or {}
        chars |= {st.get("last_char") or ""} | set((st.get("levels") or {}).keys()) | set((st.get("classes") or {}).keys())
        chars |= set(((SETTINGS.get("campaign") or {}).get("chars") or {}).keys())
        for c in chars:
            if isinstance(c, str) and c.strip():
                out.setdefault(c.strip(), "<character>")
    except Exception:
        pass
    return {k: v for k, v in out.items() if len(k) >= 3}


ACCOUNT_TAG = re.compile(r"[^\W_][\w]{1,39}#\d{4}\b")


def scrub_names(text):
    """scrub() and also your character names and anything shaped like an account name (Name#1234)."""
    s = scrub(text)
    if not s:
        return s
    for n, ph in sorted(known_names().items(), key=lambda kv: -len(kv[0])):
        s = re.sub(r"(?<![\w])" + re.escape(n) + r"(?![\w])", ph, s, flags=re.I)
    return ACCOUNT_TAG.sub("<account>", s)


PRIVATE_LEAGUE = re.compile(r"\(PL\d+\)", re.I)


def is_private_league(league):
    """A private league (its owner named it; "(PL12345)") - its name can point at people, so it never goes public."""
    return bool(PRIVATE_LEAGUE.search(str(league or "")))


def public_league(league):
    return "Private league" if is_private_league(league) else (league or "")


# 2.131.1 (feedback: encourage users not to use personally identifiable names, and never their Path of Exile
# account or character names): the one line every community-name ask shows, and its ⓘ
NAME_RULE = ("Pick a made-up name - not your real name, and never your Path of Exile account or character names. "
             "Other players see it.")
NAME_TIP = ("A made-up name keeps the board from pointing at you, or at your characters in game. The app doesn't "
            "check it against your characters - the choice is yours.")
