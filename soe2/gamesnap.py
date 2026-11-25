"""3.3.0 owner: the game's data frozen at a game version (snapshots/poe2-<version>.json.gz, tools/build_snapshot.py), so
a patch can be shown before and after: uniques, gems and item mods.

  versions()            -> the game versions there are snapshots of, oldest first
  load(version=None)    -> one snapshot (the newest by default), or {}
  history(name)         -> what a unique was before its last change, from the versions Path of Building keeps:
                           ("0.4.0", ["20% increased Block chance", ...]) or None
  compare(old, new)     -> what changed between two snapshots, per unique and per gem
Nothing is looked up while the app runs."""
import gzip
import json
import os
import re
import threading

_lock = threading.Lock()
_cache = {}
NAME = re.compile(r"^poe2-(.+)\.json\.gz$")


def folder():
    from .config import APP_DIR, RESOURCE_DIR
    for d in (os.path.join(RESOURCE_DIR, "snapshots"), os.path.join(APP_DIR, "snapshots")):
        if os.path.isdir(d):
            return d
    return None


def _vkey(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.\-]", v)]


def versions(path=None):
    d = path or folder()
    if not d:
        return []
    found = [m.group(1) for m in (NAME.match(f) for f in os.listdir(d)) if m]
    return sorted(found, key=_vkey)


def load(version=None, path=None):
    d = path or folder()
    vs = versions(d)
    if not vs:
        return {}
    v = version or vs[-1]
    with _lock:
        key = (d, v)
        if key not in _cache:
            try:
                with gzip.open(os.path.join(d, f"poe2-{v}.json.gz"), "rt", encoding="utf-8") as f:
                    _cache[key] = json.load(f)
            except (OSError, ValueError):
                _cache[key] = {}
        return _cache[key]


def reset():
    """Tests: forget what was read."""
    with _lock:
        _cache.clear()


def history(name, snap=None):
    """The unique's lines before its most recent change: (the patch it changed in, [lines it had then that it no
    longer has]), or None when nothing changed."""
    snap = load() if snap is None else snap
    u = (snap.get("uniques") or {}).get(name)
    vers = (u or {}).get("versions") or {}
    cur = vers.get("Current") or (u or {}).get("explicit")
    olds = [k for k in vers if k.lower().startswith("pre ")]
    if not olds or cur is None:
        return None
    last = max(olds, key=lambda k: _vkey(k[4:].strip()))
    gone = [ln for ln in vers[last] if ln not in cur]
    return (last[4:].strip(), gone) if gone else None


def _lines_diff(a, b):
    a, b = list(a or []), list(b or [])
    return [x for x in b if x not in a], [x for x in a if x not in b]


def compare(old, new):
    """-> {"uniques": {name: {"added": [...], "removed": [...]}, ...}, "gems": {name: {...}}, "new_uniques": [...],
    "gone_uniques": [...], "new_gems": [...], "gone_gems": [...]}. Only what changed is listed."""
    out = {"uniques": {}, "gems": {}}
    ou, nu = old.get("uniques") or {}, new.get("uniques") or {}
    for n in sorted(set(ou) & set(nu)):
        a = (ou[n].get("implicit") or []) + (ou[n].get("explicit") or [])
        b = (nu[n].get("implicit") or []) + (nu[n].get("explicit") or [])
        added, removed = _lines_diff(a, b)
        if added or removed:
            out["uniques"][n] = {"added": added, "removed": removed}
    og, ng = old.get("gems") or {}, new.get("gems") or {}
    for n in sorted(set(og) & set(ng)):
        ch = {}
        if (og[n].get("text") or "") != (ng[n].get("text") or ""):
            ch["text"] = {"before": og[n].get("text") or "", "after": ng[n].get("text") or ""}
        for k in ("first_level", "last_level"):
            added, removed = _lines_diff(og[n].get(k), ng[n].get(k))
            if added or removed:
                ch[k] = {"added": added, "removed": removed}
        if ch:
            out["gems"][n] = ch
    out["new_uniques"], out["gone_uniques"] = sorted(set(nu) - set(ou)), sorted(set(ou) - set(nu))
    out["new_gems"], out["gone_gems"] = sorted(set(ng) - set(og)), sorted(set(og) - set(ng))
    return out


# ---------------------------------------------------------------- 3.3.0 owner: Game Search's "Changed in <patch>"
_NUM = re.compile(r"[+-]?\(?\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?\)?")


def _shape(line):
    return _NUM.sub("#", str(line)).strip().lower()


def pair(added, removed):
    """Lines that only changed a number become one "changed" line. -> [("changed", after, before) |
    ("new", line, "") | ("removed", line, "")]."""
    out, left = [], list(removed or [])
    for a in added or []:
        hit = next((r for r in left if _shape(r) == _shape(a)), None)
        if hit is not None:
            left.remove(hit)
            out.append(("changed", a, hit))
        else:
            out.append(("new", a, ""))
    return out + [("removed", r, "") for r in left]


def short(version):
    """"1.0.0.3" -> "1.0"; the category says the patch, not the build."""
    parts = str(version).split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(version)


def change_rows(path=None):
    """Game Search rows for what changed between the two newest snapshots: each changed, new or removed unique
    and gem. [] while there is only one snapshot."""
    vs = versions(path)
    if len(vs) < 2:
        return []
    ov, nv = vs[-2], vs[-1]
    old, new = load(ov, path), load(nv, path)
    cmp = compare(old, new)
    group = f"Changed in {short(nv)}"
    rows = []

    def add(name, cls, status, changes):
        text = " ".join(f"{a} {b}" for _k, a, b in changes)
        rows.append({"n": name, "g": group, "c": cls, "k": status.lower(), "t": "", "ln": name.lower(),
                     "lk": status.lower(), "lt": (name + " " + text).lower(), "chg": changes, "chg_status": status,
                     "vs": (ov, nv)})
    nu, ng = new.get("uniques") or {}, new.get("gems") or {}
    ou, og = old.get("uniques") or {}, old.get("gems") or {}
    for n, d in cmp["uniques"].items():
        add(n, "Unique " + (nu[n].get("group") or "Item").rstrip("s"), "Changed", pair(d["added"], d["removed"]))
    for n in cmp["new_uniques"]:
        u = nu[n]
        add(n, "Unique " + (u.get("group") or "Item").rstrip("s"), "New",
            [("new", x, "") for x in (u.get("implicit") or []) + (u.get("explicit") or [])])
    for n in cmp["gone_uniques"]:
        add(n, "Unique " + (ou[n].get("group") or "Item").rstrip("s"), "Removed", [])
    for n, d in cmp["gems"].items():
        ch = []
        if "text" in d:
            ch.append(("changed", d["text"]["after"], d["text"]["before"]))
        for k in ("first_level", "last_level"):
            if k in d:
                ch += pair(d[k]["added"], d[k]["removed"])
        add(n, ng[n].get("type") or "Gem", "Changed", ch)
    for n in cmp["new_gems"]:
        add(n, ng[n].get("type") or "Gem", "New", [("new", ng[n].get("text") or "", "")])
    for n in cmp["gone_gems"]:
        add(n, og[n].get("type") or "Gem", "Removed", [])
    return rows
