"""3.3.0 owner: every box that takes typed text refuses the words the board refuses. The words are not written
here: soe2/cleanwords.json is made from the board's own filter by tools/build_cleanwords.mjs, so the app and the
board read one list. The board stays the last check on anything that leaves this PC.

problem(text) -> the word that is not allowed, or None. It follows the board's textProblem step for step:
threats, the library's patterns with look-alike letters and repeated letters undone, hate terms written as
phrases, then the board's own word lists."""
import json
import os
import re
import sys
import unicodedata

MSG = "That word is not allowed here."
_LEET_LIB = {"@": "a", "4": "a", "(": "c", "3": "e", "6": "g", "1": "i", "|": "i", "!": "i", "/": "l", "0": "o",
             "$": "s", "5": "s", "7": "t", "2": "z"}
_LEET = {"0": "o", "1": "i", "2": "z", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t", "8": "b", "9": "g",
         "@": "a", "$": "s", "|": "i", "!": "i"}
_HARM = re.compile(r"\b(kill|neck|hang|off)\s*(yo)?u?r\s*self\b(?!-)|\bkys\b|\bgo\s+back\s+to\s+"
                   r"(africa|asia|china|mexico|india|your\s+(own\s+)?country)\b", re.I)
_SPACED = re.compile(r"(?<![^\W_])(?:[^\W_@$!|€*]|[@$!|€*])(?:[\s._\-*+~]+(?:[^\W_]|[@$!|€*])){2,}(?![^\W_])")
_SPLIT = re.compile(r"[^\w@$|!€]+|_+")
_D = {}


def _data():
    if not _D:
        base = getattr(sys, "_MEIPASS", None)             # the built app keeps it beside sekhemas.json
        path = os.path.join(base, "soe2", "cleanwords.json") if base else \
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleanwords.json")
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {"patterns": [], "white": [], "keep": {}, "hate": [], "rude": [], "phrases": []}
        d.setdefault("allow", [])
        _D.update(d)
        _D["allow_rx"] = (re.compile(r"(?<![^\W\d_])(?:" + "|".join(sorted(map(re.escape, d["allow"]), key=len,
                                                                          reverse=True)) + r")(?![^\W\d_])", re.I)
                          if d["allow"] else None)
        _D["rx"] = [re.compile(_to_regex(p)) for p in d["patterns"]]
        _D["white_l"] = [w.lower() for w in d["white"]]
    return _D


def _to_regex(p):
    """The library's pattern -> a regex: | is a word edge, [x] is optional, ? is any one character."""
    out, i = [], 0
    start, end = p.startswith("|"), p.endswith("|") and len(p) > 1
    body = p[1 if start else 0:len(p) - 1 if end else len(p)]
    while i < len(body):
        c = body[i]
        if c == "[":
            j = body.index("]", i)
            out.append("(?:" + re.escape(body[i + 1:j]) + ")?")
            i = j + 1
            continue
        if c == "\\" and i + 1 < len(body):
            out.append(re.escape(body[i + 1]))
            i += 2
            continue
        out.append("." if c == "?" else re.escape(c))
        i += 1
    return ("(?<![a-z])" if start else "") + "".join(out) + ("(?![a-z])" if end else "")


def _squash(text, keep):
    """Look-alike letters undone, lower case, repeated letters cut to what a real word can hold. -> (the new
    text, for each of its characters the place it came from)."""
    out, at, last, run = [], [], "", 0
    for i, ch in enumerate(text):
        c = _LEET_LIB.get(ch, ch).lower()
        run = run + 1 if c == last else 1
        last = c
        if c.isalpha() and run > int(keep.get(c, 1)):
            continue
        out.append(c)
        at.append(i)
    return "".join(out), at


def _lib_hit(text, d):
    """The library's patterns on one text -> the part of the text that matched, or None. A match inside a word
    the library lists as fine, like a place name, does not count."""
    low = text.lower()
    fine = []
    for w in d["white_l"]:
        k = low.find(w)
        while k >= 0:
            fine.append((k, k + len(w)))
            k = low.find(w, k + 1)
    sq, at = _squash(text, d["keep"])
    for rx in d["rx"]:
        for m in rx.finditer(sq):
            if m.end() <= m.start():
                continue
            a, b = at[m.start()], at[m.end() - 1] + 1
            if not any(x <= a and b <= y for x, y in fine):
                return text[a:b]
    return None


def _sqz(w):
    return re.sub(r"(.)\1+", r"\1", w)


def _join(m):
    """Letters spaced out are read as one word. A run of digits is a number or a version, like 4.5.5.2: left."""
    got = re.sub(r"[\s._\-*+~]+", "", m.group(0))
    return m.group(0) if got.isdigit() else got


def problem(text):
    """The word in text that is not allowed, or None."""
    raw = unicodedata.normalize("NFKC", str(text or ""))
    if not raw.strip():
        return None
    d = _data()
    if d["allow_rx"] is not None:                 # the game's own words are fine: Strongbox, Bestial ...
        raw = d["allow_rx"].sub("\n", raw)
    joined = _SPACED.sub(_join, raw)
    for t in (raw, joined):
        m = _HARM.search(t)
        if m:
            return m.group(0)
    for t in ([raw] if joined == raw else [raw, joined]):
        hit = _lib_hit(t, d)
        if hit:
            return hit
    low = joined.lower()
    squashed = "".join(_LEET.get(c, c) for c in re.sub(r"[^\w@$|!€]+|_+", "", low))
    for h in d["phrases"]:
        if h in squashed:
            return h
    hate, rude = d["hate"], d["rude"]
    for word in _SPLIT.split(low):
        if not word:
            continue
        if (word in hate and not word.isdigit()) or word in rude:
            return word
        plain = "".join(_LEET.get(c, c) for c in word).replace("€", "e")
        sq = _sqz(plain)
        for h in hate:
            if plain == h or sq == _sqz(h) or (len(h) >= 5 and not h.isdigit() and (h in plain or _sqz(h) in sq)):
                return word
        for h in rude:
            if plain == h or sq == _sqz(h) or plain == h + "s" or sq == _sqz(h) + "s":
                return word
    return None


def while_typing(text, cursor=None):
    """problem() for a box someone is still typing in: the word the cursor is at the end of is not judged yet,
    since it may grow into a fine word. It is judged once a space follows, or the box is left."""
    text = str(text or "")
    cur = len(text) if cursor is None else max(0, min(len(text), int(cursor)))
    a = cur
    while a > 0 and not text[a - 1].isspace():
        a -= 1
    b = cur
    while b < len(text) and not text[b].isspace():
        b += 1
    if a == cur or b != cur:                    # not at the end of a word: judge all of it
        return problem(text)
    return problem(text[:a] + text[b:])
