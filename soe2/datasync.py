"""3.3.0 owner: new game data without a new app. Once a day the app reads data_manifest.json on the project's main
branch on GitHub (written by .github/workflows/game-data.yml). Each data file newer than this PC's copy is
downloaded, its SHA-256 checked, its JSON read back, and only then put in the data folder - a bad download changes
nothing. Only the data files the app ships (BUNDLED_DATA) and patch snapshots are taken, never code. Always on: it
is how the app stays current with the game. New data is used from the next start."""
import gzip
import hashlib
import json
import os
import threading
import time

from . import buglog
from .config import APP_UA, BUNDLED_DATA, P, SETTINGS, load_json, save_json

RAW = "https://raw.githubusercontent.com/StashOfExile/StashOfExile2/main/"
MANIFEST = "data_manifest.json"
EVERY = 24 * 3600
MAX_BYTES = 40 * 1024 * 1024
_busy = {"on": False}
UPDATED = []                                             # names taken this run, for the status line


def _get(name):
    import requests
    r = requests.get(RAW + name, headers={"User-Agent": APP_UA}, timeout=20)
    if r.status_code != 200 or len(r.content) > MAX_BYTES:
        return None
    return r.content


def _good(name, blob, sha):
    """The download is what the manifest says, and it reads."""
    if not blob or hashlib.sha256(blob).hexdigest() != sha:
        return False
    try:
        json.loads(gzip.decompress(blob) if name.endswith(".gz") else blob.decode("utf-8-sig"))
        return True
    except Exception:
        return False


def _put(path, blob):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)


def plan(manifest, seen, have_snaps):
    """-> ([(file, version, sha)], [(snapshot, sha)]) to take: data files newer than this PC's, snapshots it lacks."""
    files = []
    for name, m in (manifest.get("files") or {}).items():
        if name not in BUNDLED_DATA or not isinstance(m, dict):
            continue                                     # data the app ships, nothing else
        ver, sha = m.get("version"), str(m.get("sha256") or "")
        if isinstance(ver, int) and len(sha) == 64 and ver > int(seen.get(name, 0) or 0):
            files.append((name, ver, sha))
    snaps = [(n, s) for n, s in (manifest.get("snapshots") or {}).items()
             if n.startswith("poe2-") and n.endswith(".json.gz") and "/" not in n and "\\" not in n and len(str(s)) == 64
             and n not in have_snaps]
    return files, snaps


def run_once():
    blob = _get(MANIFEST)
    if not blob:
        return
    manifest = json.loads(blob.decode("utf-8"))
    seen = load_json("data_versions.json", {}) or {}
    snap_dir = P("snapshots")
    have = set(os.listdir(snap_dir)) if os.path.isdir(snap_dir) else set()
    try:
        from . import gamesnap
        have |= {f"poe2-{v}.json.gz" for v in gamesnap.versions()}
    except Exception:
        pass
    files, snaps = plan(manifest, seen, have)
    for name, ver, sha in files:
        data = _get(name)
        if not _good(name, data, sha):
            continue
        _put(P(name), data)
        seen[name] = ver
        UPDATED.append(name)
    for name, sha in snaps:
        data = _get("snapshots/" + name)
        if _good(name, data, sha):
            _put(os.path.join(snap_dir, name), data)
            UPDATED.append(name)
    save_json("data_versions.json", seen)


def refresh(force=False):
    """In the background, once a day."""
    if os.environ.get("SOE2_NO_BOARD") or os.environ.get("SOE2_NO_DATASYNC"):
        return False                                     # screenshots and tests stay offline
    last = float(SETTINGS.get("data_sync_at") or 0)
    if _busy["on"] or (not force and time.time() - last < EVERY):
        return False
    _busy["on"] = True

    def go():
        try:
            run_once()
            SETTINGS["data_sync_at"] = time.time()
        except Exception:
            buglog.caught()
        finally:
            _busy["on"] = False
    threading.Thread(target=go, daemon=True).start()
    return True
