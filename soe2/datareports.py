"""3.3.0 owner: report a wrong or missing line on a Codex page, for an admin to review.

A report is sent to the community board with no account: the page, the row's ref, what is wrong and a note. Admins
see every open report and can hide the row, mark it fixed, or dismiss it. Rows an admin hid are downloaded by every
app and left out of Game Search and Mod Lab at once, with no update.

  send(page, ref, kind, item, line, note)  -> (ok, why)
  pull()                                     -> the hidden rows, saved in data_hidden.json, or None
  hidden(page)                               -> the refs hidden on that page
  reports() / act(rid, action)               -> admins"""
from .config import APP_VERSION, load_json, save_json

FILE = "data_hidden.json"
PAGES = {"search": "Game Search", "ratemods": "Mod Lab", "maps": "Map Library", "library": "Under the Hood"}
KINDS = (("wrong", "Wrong: a number or wording is not what the game says"),
         ("missing", "Something is missing"),
         ("removed", "No longer in the game"),
         ("other", "Something else"))
KIND_WORD = {"wrong": "Wrong", "missing": "Missing", "removed": "Not in game", "other": "Other"}
HIDE_WORKS = ("search", "ratemods")             # where Hide leaves the row out at once; elsewhere it waits for an update
NOTE_MAX, LINE_MAX, ITEM_MAX, REF_MAX = 500, 300, 120, 300
_hidden = None


def _clip(text, n):
    return " ".join(str(text or "").split())[:n]


def body(page, ref, kind, item="", line="", note=""):
    """What send() sends, or a line saying what is wrong with it."""
    from . import cleantext
    if page not in PAGES:
        return "This page cannot be reported from."
    if kind not in dict(KINDS):
        return "Pick what is wrong."
    ref = _clip(ref, REF_MAX)
    if not ref:
        return "Pick a row first, then report it."
    note = str(note or "").strip()[:NOTE_MAX]
    if cleantext.problem(note):
        return "That wording is not allowed."
    return {"page": page, "ref": ref, "kind": kind, "item": _clip(item, ITEM_MAX), "line": _clip(line, LINE_MAX),
            "note": " ".join(note.split()), "version": APP_VERSION}


def send(page, ref, kind, item="", line="", note="", call=None):
    b = body(page, ref, kind, item, line, note)
    if isinstance(b, str):
        return False, b
    from . import board as B
    if call is None and not B.configured():
        return False, "The community board is not set up."
    ok, res = (call or B.call)("POST", "/reports", body=b)
    if not ok:
        return False, "The board does not take reports yet. It arrives with the next board update." \
            if "404" in str(res) or str(res).strip().lower() == "not found" else str(res)
    return True, ""


def hidden(page):
    global _hidden
    if _hidden is None:
        d = load_json(FILE, {})
        _hidden = d if isinstance(d, dict) else {}
    return set(_hidden.get(page) or ())


def set_hidden(rows):
    """[[page, ref], ...] from the board -> saved, by page."""
    global _hidden
    out = {}
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, list) and len(r) == 2 and r[0] in PAGES and isinstance(r[1], str) and 0 < len(r[1]) <= REF_MAX:
            out.setdefault(r[0], [])
            if r[1] not in out[r[0]]:
                out[r[0]].append(r[1])
    _hidden = out
    save_json(FILE, out)
    return out


def reset(data=None):
    """Tests: start from this."""
    global _hidden
    _hidden = data


def pull(call=None):
    from . import board as B
    if call is None and not B.configured():
        return None
    ok, res = (call or B.call)("GET", "/reports/hidden")
    if not ok or not isinstance(res, dict):
        return None
    return set_hidden(res.get("hidden"))


def reports(call=None):
    """Admins: open and hidden reports. -> (True, [report]) or (False, why)."""
    from . import board as B
    ok, res = (call or B.call)("GET", "/reports")
    if not ok:
        return False, "The board does not take reports yet. It arrives with the next board update." \
            if "404" in str(res) or str(res).strip().lower() == "not found" else str(res)
    rows = res.get("reports") if isinstance(res, dict) else None
    keep = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and isinstance(r.get("id"), int) and r.get("page") in PAGES:
            keep.append({k: (str(r.get(k) or "")[:NOTE_MAX] if k not in ("id", "n") else int(r.get(k) or 0))
                         for k in ("id", "page", "ref", "kind", "item", "line", "note", "version", "n", "status")})
    return True, keep


def act(rid, action, call=None):
    from . import board as B
    return (call or B.call)("POST", f"/reports/{int(rid)}", body={"action": action})
