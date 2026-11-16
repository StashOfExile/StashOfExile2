"""Page smoke test (QA safety net for the navigation restructure). Starts the real app on a virtual screen, opens
every page and every tab the way the sidebar does, and records what it found: opened or not, tracebacks (with the
page they happened on), blank pages, the page header (PageBar) text, a screenshot each, the sidebar's rows, Settings,
Go to anything (Ctrl+K) and the status bar. Nothing in the app is changed: it only drives it from the outside.

Run (Linux, needs Xvfb + Pillow; starts its own Xvfb on :11 if none is there):
  python3.12 tools/smoke_pages.py                      run -> outputs/smoke/<YYYYmmdd-HHMMSS>/
  python3.12 tools/smoke_pages.py --run baseline       run named "baseline"
  python3.12 tools/smoke_pages.py --compare baseline   diff the newest other run against baseline
  python3.12 tools/smoke_pages.py --compare baseline after-nav   diff two named runs
  python3.12 tools/smoke_pages.py --run after --compare baseline run, then diff against baseline

Window options: --geom WxH (the app window, default 1600x1000)   --screen WxH (the Xvfb size, default 1920x1200;
only used when this run starts its own Xvfb)   --shape full|drawer (default full = today's behavior; drawer needs
soe2/drawer.py and is a no-op until it exists)   --clip-fail (a clipped control on a P1 page is a failure; else it is a
WARN "clip")
Clip detector (rec["clipped"] + a WARN "clip"), on Button/Label/Entry/Combobox/SegBar: edge = right edge more than 2 px past
the page's or any parent's right edge; squeezed = a Button/Label/SegBar narrower than it asks for; no room = still
pack/grid-managed but not shown. Controls scrolled out of view, or in a canvas that scrolls sideways, are skipped.
P1 pages (used in game): pricecheck, tracker > Helpers, rates (both tabs), regex > Favorites, dashboard.

Options: --checks (also run every tools/check_*.py and soe2-tests if found -> <run>/tests.txt)   --display :11   --out /mnt/user-data/outputs/smoke   --data /tmp/h2/.stashofexile2 (test data copied into
a throwaway HOME; a missing folder means an empty one)   --keep-home   --no-shots   --timeout 600

Exit code: 0 all good; 1 a page/tab failed (didn't open, blank, traceback) or the compare found a failure.
Compare: tracebacks that are new, pages/tabs that no longer open or are blank, and pages/tabs that disappeared are
failures; title, sidebar order and "how it was reached" changes are reported as CHANGED (expected in a restructure).

How it opens things (so a restructure keeps being tested the real way):
  page  - its row in the sidebar (Sidebar._click on the row's y), after opening its parent chain the same way;
          a page not in the sidebar is opened through Go to anything's own entry for it; last, Shell.open(key).
  tab   - its "key::tab" row in the sidebar; else Shell.open_tab (the path Go to anything uses).
Errors: Tk's report_callback_exception, buglog.record (error/crash; caught/net/freeze/slow are kept as warnings),
sys/threading excepthooks (through buglog) and any "Traceback" printed on stderr - each tagged with the step it
happened in."""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "/mnt/user-data/outputs/smoke"
DATA = "/tmp/h2/.stashofexile2"
OFFLINE = "http://127.0.0.1:9"                 # nothing listens there: every request fails at once (deterministic)
SCREEN = (1920, 1200)
GEOM = (1600, 1000)
SHAPE = "full"
SHARE = None
CLIP_FAIL = False
CLIP_SLACK = 2                                 # px a control may stick out past the page edge before it counts
# P1 pages (used while playing): page key -> its tabs that count (None = every tab and the page itself)
P1 = {"pricecheck": None, "dashboard": None, "rates": None, "tracker": ("Helpers",), "regex": ("\u2605 Favorites",)}
FAIL_KINDS = ("error", "crash", "tk", "stderr", "fatal", "caught")
# caught      - an exception the app stepped over (buglog.caught) - a failure, unless it is the network being off
# caught_net  - the same for a network error (this test runs offline on purpose): a warning


def is_net(t):
    names = {c.__name__ for c in getattr(t, "__mro__", ())}
    return bool(names & {"ConnectionError", "URLError", "Timeout", "TimeoutError", "RequestException", "socket.gaierror",
                         "gaierror", "ConnectionRefusedError", "HTTPError", "SSLError"})
SETTLE_MS = 900                                # after each open (Shell.open heals 600 ms later)
# pages taken out on purpose because they became tabs of another page: key -> (that page, its tabs). Gone is a CHANGE
# (not a failure) only while every one of those tabs opens.
MERGED = {"ovset": ("tracker", ("Helpers", "On the Overlay", "Look", "Options"))}   # nav phase 2: Overlay Settings
REDIRECT = {"notes": "the Notes overlay (Shell.open('notes') -> app.notes_open)"}   # pages that open something else


# ============================================================================ parent: set up, run the child, report
def parse_wh(text):
    try:
        w, h = text.lower().split("x")
        return int(w), int(h)
    except Exception:
        sys.exit(f"bad size {text!r}: use WxH, e.g. 900x1270")


def ensure_x(display):
    r = subprocess.run(["xdpyinfo", "-display", display], capture_output=True, text=True)
    if r.returncode == 0:
        import re
        m = re.search(r"dimensions:\s+(\d+)x(\d+)", r.stdout)
        if m and (int(m.group(1)), int(m.group(2))) != tuple(SCREEN):
            print(f"smoke: note - Xvfb {display} is already running at {m.group(1)}x{m.group(2)}, "
                  f"--screen {SCREEN[0]}x{SCREEN[1]} is ignored")
        return None
    p = subprocess.Popen(["Xvfb", display, "-screen", "0", f"{SCREEN[0]}x{SCREEN[1]}x24", "-nolisten", "tcp"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        time.sleep(0.1)
        if subprocess.run(["xdpyinfo", "-display", display], capture_output=True).returncode == 0:
            return p
    p.kill()
    sys.exit(f"Xvfb {display} didn't start")


def drawer_exists():
    return os.path.exists(os.path.join(ROOT, "soe2", "drawer.py"))


def make_home(data, shape="full"):
    home = tempfile.mkdtemp(prefix="soe2-smoke-")
    dst = os.path.join(home, ".stashofexile2")
    if data and os.path.isdir(data):
        shutil.copytree(data, dst, ignore=shutil.ignore_patterns(
            "crash_raw.tmp", "crash_steps.tmp", "hang_report.txt", "crash_report.txt", "slow_report.txt",
            "app_log.txt", "app_log.old.txt"))
    os.makedirs(dst, exist_ok=True)
    sp = os.path.join(dst, "settings.json")
    try:
        s = json.load(open(sp, encoding="utf-8"))
    except Exception:
        s = {}
    sys.path.insert(0, ROOT)
    from soe2 import __version__
    from soe2 import features as FEAT
    s.update({"labs": True, "show_advanced": True, "features_asked": "done", "seen_version": __version__,
              "whatsnew_lead": __version__, "quickstart_done": True, "share_asked": True, "board_name_asked": True, "lb_name_asked": True,
              "wealth_setup_seen": True, "check_updates": False})
    s.setdefault("league", "Standard")
    s["features"] = {g["key"]: True for g in FEAT.ALL}           # every feature on, BETA ones too
    for k, sub, _name in FEAT.HELPER_SWITCHES.values():           # every helper on (its own switch)
        if not isinstance(s.get(k), dict):
            s[k] = {}
        s[k][sub] = True
    s.setdefault("desecrate", {}).setdefault("asked", True)
    s.setdefault("tracker", {}).setdefault("chips_asked", True)
    if drawer_exists():                                  # (D1 on) the drawer build's shape setting; before that: no change
        s["drawer"] = dict(s.get("drawer") or {}, shape=shape, intro_done=True, first_run_done=True, **({"share": SHARE} if SHARE else {}))
    json.dump(s, open(sp, "w", encoding="utf-8"), indent=1)
    return home


def run(args):
    name = args.run or time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(args.out, name)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    xv = ensure_x(args.display)
    home = make_home(args.data, args.shape)
    env = dict(os.environ, HOME=home, APPDATA=home, USERPROFILE=home, DISPLAY=args.display,
               SOE2_TRADE_API=OFFLINE + "/api/trade2", SOE2_NINJA=OFFLINE, PYTHONDONTWRITEBYTECODE="1")
    if args.self_test:
        env["SOE2_SMOKE_SELFTEST"] = "1"
    cmd = [sys.executable, os.path.abspath(__file__), "--child", out, "--display", args.display] + \
          (["--no-shots"] if args.no_shots else []) + \
          ["--geom", f"{GEOM[0]}x{GEOM[1]}", "--screen", f"{SCREEN[0]}x{SCREEN[1]}", "--shape", args.shape] + \
          (["--clip-fail"] if args.clip_fail else [])
    t0 = time.time()
    log = open(os.path.join(out, "app_output.txt"), "w")
    try:
        rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    log.close()
    if xv is not None:
        xv.terminate()
    if not args.keep_home:
        shutil.rmtree(home, ignore_errors=True)
    rp = os.path.join(out, "report.json")
    if not os.path.exists(rp):
        print(f"smoke: no report (child exit {rc}) - see {out}/app_output.txt")
        return 1
    rep = json.load(open(rp))
    rep["run_seconds"] = round(time.time() - t0, 1)
    rep["child_exit"] = rc
    json.dump(rep, open(rp, "w"), indent=1)
    summary(rep, out)
    return 1 if rep["failures"] else 0


def summary(rep, out):
    rows = [("page", "tab", "via", "ok", "ms", "size", "kids", "errs", "title")]
    for p in rep["pages"]:
        for s in [p] + p.get("tabs", []):
            rows.append((p["key"], s.get("tab") or "-", s.get("via", ""), "OK" if s["ok"] else "FAIL",
                         str(s.get("open_ms", "")),
                         f'{s.get("w", 0)}x{s.get("h", 0)}', str(s.get("widgets", 0)), str(len(s.get("errors", []))),
                         (s.get("title") or "")[:40]))
    wd = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, wd)))
    n_tabs = sum(len(p.get("tabs", [])) for p in rep["pages"])
    print(f"\nsmoke {rep['run']}: {len(rep['pages'])} pages, {n_tabs} tabs, {len(rep['errors'])} errors, "
          f"{len(rep['warnings'])} warnings, checks: " +
          ", ".join(f"{k}={'OK' if v.get('ok') else 'FAIL'}" for k, v in rep["checks"].items()))
    clips = [(p["key"] + (f" \u203a {s['tab']}" if s.get("tab") else ""), s["clipped"]) for p in rep["pages"]
             for s in [p] + p.get("tabs", []) if s.get("clipped")]
    if clips:
        print(f"\nclipped controls (WARN): {sum(len(c) for _, c in clips)} on {len(clips)} page/tab views")
        for name, c in clips:
            print(f"  {name}: {len(c)}")
    seen = {}
    for w in rep["warnings"]:
        seen.setdefault((w["kind"], w.get("where")), []).append(w["step"])
    for (k, wh), st in sorted(seen.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        print(f"warning ({k}): {wh} - in {', '.join(sorted(set(st)))}"[:200])
    slow = [(p["key"] + (f" › {s['tab']}" if s.get("tab") else ""), s["open_ms"]) for p in rep["pages"]
            for s in [p] + p.get("tabs", []) if s.get("open_ms", 0) > 1500]
    for name, ms in slow:
        print(f"slow: {name} took {ms} ms to open (the UI thread was busy)")
    for f in rep["failures"]:
        print("FAIL:", f)
    print(f"report: {out}/report.json")


# ============================================================================ the existing checks and tests
def find_tests():
    """soe2-tests (runall.sh), if it is anywhere near: $SOE2_TESTS, next to the repo, or tests/ in it."""
    for d in (os.environ.get("SOE2_TESTS"), os.path.join(os.path.dirname(ROOT), "soe2-tests"),
              os.path.join(ROOT, "soe2-tests"), os.path.join(ROOT, "tests")):
        if d and os.path.isdir(d):
            return d
    return None


def run_checks(args, out):
    """Every tools/check_*.py (check_ux on the virtual screen) and the test suite if there is one -> tests.txt."""
    xv = ensure_x(args.display)
    lines = [f"checks and tests - {time.strftime('%Y-%m-%d %H:%M:%S')} - {sys.executable}", ""]
    bad = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "tools", "check_*.py"))):
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, f], cwd=ROOT, capture_output=True, text=True, timeout=600,
                               env=dict(os.environ, DISPLAY=args.display))
            rc, text = r.returncode, (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            rc, text = "timeout", ""
        bad += rc != 0
        last = text.splitlines()[-1] if text else ""
        lines.append(f"{'PASS' if rc == 0 else 'FAIL'}  {os.path.basename(f):22} {time.time() - t0:5.1f}s  {last}")
        if rc != 0:
            lines += ["      " + l for l in text.splitlines() if not l.startswith("to do")][:40]
    lines.append("")
    tests = find_tests()
    if tests is None:
        lines.append("test suite: none found (looked for $SOE2_TESTS, ../soe2-tests, soe2-tests/, tests/) - not run")
    else:
        runner = os.path.join(tests, "runall.sh")
        cmd = ["bash", runner] if os.path.exists(runner) else [sys.executable, "-m", "pytest", "-q", tests]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=3600,
                           env=dict(os.environ, DISPLAY=args.display))
        bad += r.returncode != 0
        lines.append(f"test suite {tests}: {'PASS' if r.returncode == 0 else 'FAIL'} (exit {r.returncode})")
        lines += ["      " + l for l in (r.stdout + r.stderr).strip().splitlines()[-30:]]
    lines.append(f"\n{bad} failing")
    if xv is not None:
        xv.terminate()
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "tests.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if bad else 0


# ============================================================================ compare
def load(out, name):
    p = os.path.join(out, name, "report.json")
    if not os.path.exists(p):
        sys.exit(f"no report {p}")
    return json.load(open(p))


def steps(rep):
    d = {}
    for p in rep["pages"]:
        d[(p["key"], None)] = p
        for t in p.get("tabs", []):
            d[(p["key"], t["tab"])] = t
    return d


def err_sig(e):
    return (e.get("kind"), (e.get("text") or "").strip().splitlines()[-1:][0] if e.get("text") else "")


def compare(a, b):
    """-> (failures, changes) between baseline a and new run b."""
    fails, changes = [], []
    sa, sb = steps(a), steps(b)
    lab = lambda k: k[0] + (f" › {k[1]}" if k[1] else "")
    for k in sa:
        if k not in sb:
            into = MERGED.get(k[0]) if not k[1] else None
            if into and all(sb.get((into[0], t), {}).get("ok") for t in into[1]):
                changes.append(f"MERGED (expected): {lab(k)} -> {into[0]} › {' / '.join(into[1])} (all open)")
                continue
            (fails if sa[k]["ok"] else changes).append(f"GONE (no longer opens): {lab(k)}" +
                                                       (f" - and {into[0]}'s tabs don't all open" if into else ""))
    for k in sb:
        if k not in sa:
            changes.append(f"NEW: {lab(k)}" + ("" if sb[k]["ok"] else " - and it FAILS"))
            if not sb[k]["ok"]:
                fails.append(f"NEW page/tab fails: {lab(k)}: {sb[k].get('why')}")
            continue
        x, y = sa[k], sb[k]
        if x["ok"] and not y["ok"]:
            fails.append(f"BROKEN: {lab(k)}: {y.get('why')}")
        elif not x["ok"] and y["ok"]:
            changes.append(f"FIXED: {lab(k)}")
        if (x.get("title") or "") != (y.get("title") or ""):
            changes.append(f"TITLE: {lab(k)}: {x.get('title')!r} -> {y.get('title')!r}")
        if (x.get("where") or "") != (y.get("where") or ""):
            changes.append(f"WHERE: {lab(k)}: {x.get('where')!r} -> {y.get('where')!r}")
        if x.get("via") != y.get("via"):
            changes.append(f"VIA: {lab(k)}: {x.get('via')} -> {y.get('via')}")
        if "clipped" in x and "clipped" in y and len(x["clipped"]) != len(y["clipped"]):
            changes.append(f"CLIPS: {lab(k)}: {len(x['clipped'])} -> {len(y['clipped'])} clipped controls")
        old = {err_sig(e) for e in x.get("errors", [])}
        for e in y.get("errors", []):
            if err_sig(e) not in old and e.get("kind") in FAIL_KINDS:
                fails.append(f"NEW ERROR on {lab(k)}: {err_sig(e)[1]}")
    olde = {err_sig(e) for e in a["errors"]}
    for e in b["errors"]:
        if e.get("step", "").startswith(("check:", "startup", "end")) and err_sig(e) not in olde:
            fails.append(f"NEW ERROR in {e['step']}: {err_sig(e)[1]}")
    for c in sorted(set(a["checks"]) | set(b["checks"])):
        x, y = a["checks"].get(c, {}), b["checks"].get(c, {})
        if x.get("ok") and not y.get("ok"):
            fails.append(f"CHECK BROKEN: {c}: {y.get('why', 'gone')}")
    ow, nw = a["sidebar"]["rows"], b["sidebar"]["rows"]
    if ow != nw:
        import difflib
        changes.append("SIDEBAR order/rows changed:\n" + "\n".join(
            "      " + l for l in difflib.unified_diff(ow, nw, "baseline", "new", lineterm="", n=1)))
    oldw = {(w["kind"], w.get("where")) for w in a["warnings"]}
    neww = [w for w in b["warnings"] if (w["kind"], w.get("where")) not in oldw and w["kind"] != "clip"]
    for w in neww:
        changes.append(f"NEW WARNING ({w['kind']}) in {w['step']}: {w.get('where')}")
    return fails, changes


def do_compare(args, base, new):
    if new is None:
        runs = sorted((d for d in glob.glob(os.path.join(args.out, "*", "report.json"))
                       if os.path.basename(os.path.dirname(d)) != base), key=os.path.getmtime)
        if not runs:
            sys.exit("nothing to compare with")
        new = os.path.basename(os.path.dirname(runs[-1]))
    a, b = load(args.out, base), load(args.out, new)
    fails, changes = compare(a, b)
    print(f"\ncompare {base} -> {new}")
    print(f"  pages {len(a['pages'])} -> {len(b['pages'])}, tabs {sum(len(p.get('tabs', [])) for p in a['pages'])}"
          f" -> {sum(len(p.get('tabs', [])) for p in b['pages'])}")
    for c in changes:
        print("  CHANGED", c)
    for f in fails:
        print("  FAIL   ", f)
    print(f"compare: {len(fails)} failures, {len(changes)} changes")
    return 1 if fails else 0


# ============================================================================ child: inside the app
def child(out, display, shots):
    import io
    import threading
    import traceback
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    sys.argv = ["stashofexile2.py"]
    R = {"run": os.path.basename(out), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "pages": [], "errors": [],
         "warnings": [], "checks": {}, "sidebar": {}, "failures": []}
    CTX = ["startup"]
    LOCK = threading.Lock()

    def add_err(kind, text, where=""):
        e = {"step": CTX[0], "kind": kind, "where": where, "text": (text or "").strip()[-4000:]}
        with LOCK:
            (R["errors"] if kind in FAIL_KINDS else R["warnings"]).append(e)
            CUR[0].setdefault("errors" if kind in FAIL_KINDS else "warnings", []).append(e)
    CUR = [{}]

    class Tee(io.TextIOBase):                      # stderr: a printed traceback counts too
        def __init__(self, real):
            self.real, self.buf, self.tb = real, "", None

        def write(self, s):
            self.real.write(s)
            self.buf += s
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                if line.startswith("Traceback (most recent call last)"):
                    self.tb = [line]
                elif self.tb is not None:
                    self.tb.append(line)
                    if line and not line.startswith((" ", "\t")) and not line.startswith(("During handling",
                                                                                         "The above exception")):
                        add_err("stderr", "\n".join(self.tb), self.tb[-1][:200])
                        self.tb = None
            return len(s)

        def flush(self):
            self.real.flush()
    sys.stderr = Tee(sys.stderr)

    from soe2 import buglog
    orig_record = buglog.record

    IN_TK = [False]

    def record(kind, where, detail="", exc=None):
        if IN_TK[0]:
            return orig_record(kind, where, detail, exc)
        try:
            tb = ""
            if exc is True:
                tb = traceback.format_exc()
            elif isinstance(exc, BaseException):
                tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            k = kind                                    # net/freeze/slow/debug -> warnings
            if kind == "error" and not tb.strip().startswith("Traceback"):
                k = "error_no_traceback"                # (a logged message - e.g. a stalled timer - no exception)
            if kind == "caught":                        # buglog.caught(): still inside the except - the full traceback
                t, v, _tb = sys.exc_info()
                if t is not None:
                    tb = traceback.format_exc()
                    k = "caught_net" if is_net(t) else "caught"
                else:
                    k = "caught_net"                    # ("more than N places" line: nothing to show)
            add_err(k, f"{where}\n{detail}\n{tb}", where)
        except Exception:
            pass
        return orig_record(kind, where, detail, exc)
    buglog.record = record

    import tkinter as tk
    import soe2.app as A
    orig_init = A.App.__init__
    APP = []

    def init(self, *a, **k):
        try:
            orig_init(self, *a, **k)
        except Exception:
            add_err("fatal", traceback.format_exc(), "App.__init__")
            finish(None)
        APP.append(self)
        old = self.root.report_callback_exception

        def tk_hook(t, v, tb):
            add_err("tk", "".join(traceback.format_exception(t, v, tb)), f"{t.__name__}: {v}"[:200])
            IN_TK[0] = True                         # (buglog's own hook logs it again: not a second error)
            try:
                old(t, v, tb)
            except Exception:
                pass
            finally:
                IN_TK[0] = False
        self.root.report_callback_exception = tk_hook
        place_window(self)
        if os.environ.get("SOE2_SMOKE_SELFTEST"):
            self_test(self)
        self.root.after(4000, lambda: Driver(self, R, CTX, CUR, add_err, out, display, shots, finish).start())
    A.App.__init__ = init

    def finish(_app):
        CTX[0] = "end"
        for p in R["pages"]:
            for s in [p] + p.get("tabs", []):
                if not s["ok"]:
                    R["failures"].append(f"{p['key']}" + (f" › {s['tab']}" if s.get("tab") else "") + f": {s.get('why')}")
        for c, v in R["checks"].items():
            if not v.get("ok"):
                R["failures"].append(f"check {c}: {v.get('why')}")
        for e in R["errors"]:
            R["failures"].append(f"{e['kind']} in {e['step']}: {e['where'] or e['text'].splitlines()[-1:]}")
        R["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        json.dump(R, open(os.path.join(out, "report.json"), "w"), indent=1, ensure_ascii=False)
        sys.stderr.flush()
        sys.stdout.flush()
        os._exit(0)

    import runpy
    try:
        runpy.run_path(os.path.join(ROOT, "stashofexile2.py"), run_name="__main__")
    except SystemExit:
        pass
    except Exception:
        add_err("fatal", traceback.format_exc(), "launcher")
    finish(None)


def place_window(app):
    """Put the window where the run says. Full shape: root.geometry as always. Drawer shape (D1 on): the hooks the
    Drawer provides - drawer.GAME_RECT_HOOK (the "game" is the whole screen) and app.app_show; until soe2/drawer.py
    exists this is today's root.geometry."""
    if SHAPE == "drawer" and drawer_exists():
        try:
            from soe2 import drawer
            drawer.GAME_RECT_HOOK = lambda: (0, 0, SCREEN[0], SCREEN[1])
            app.app_show(focus=True)
            return
        except Exception:
            import traceback
            print("smoke: drawer shape failed, using root.geometry\n" + traceback.format_exc(), file=sys.stderr)
    app.root.geometry(f"{GEOM[0]}x{GEOM[1]}+0+0")


def self_test(app):
    """--self-test: break things on purpose (in this process only) - every kind must show up as a failure."""
    sh = app.shell
    mods = {m.key: m for m in app.mods}
    if "maps" in mods:                                   # a Tk callback that raises while Map Library is open
        orig = mods["maps"].on_show
        mods["maps"].on_show = lambda: (orig(), app.root.after(10, lambda: 1 / 0))
    if "plan" in mods:                                   # an exception the app steps over (buglog.caught)
        mods["plan"].on_show = lambda: (_ for _ in ()).throw(KeyError("self-test"))
    if "leaderboards" in sh.windows:                     # a blank page
        body = sh.windows["leaderboards"].body
        mods["leaderboards"].on_show = lambda: [getattr(c, m)() for c in body.winfo_children()
                                                for m in ("pack_forget", "grid_forget", "place_forget")]


class Driver:
    """Runs the steps one after another from the Tk loop (root.after), so the app keeps running normally."""

    def __init__(self, app, R, CTX, CUR, add_err, out, display, shots, finish):
        self.app, self.R, self.CTX, self.CUR, self.add_err = app, R, CTX, CUR, add_err
        self.out, self.display, self.shots, self.finish = out, display, shots, finish
        self.sh = app.shell
        self.root = app.root
        self.queue = []
        self.cur = None

    # ---- scheduling
    def start(self):
        import tkinter as tk
        self.tk = tk
        self.plan()
        self.next()

    def then(self, fn, wait=0):
        self.queue.append((fn, wait))

    def next(self):
        """One short slice of the current step; a step is a generator that yields how long to wait (ms) before it
        goes on. (Never one long blocking call: this runs from root.after, and a long nested wait would stall the
        app's own timers - e.g. its clipboard watcher - and give false errors.)"""
        import traceback
        while True:
            if self.cur is None:
                if not self.queue:
                    self.finish(self.app)
                    return
                fn, _w = self.queue.pop(0)
                try:
                    g = fn()
                except Exception:
                    self.add_err("fatal", traceback.format_exc(), f"smoke step {getattr(fn, '__name__', '?')}")
                    continue
                if g is None or not hasattr(g, "__next__"):
                    continue
                self.cur = g
            try:
                wait = next(self.cur)
            except StopIteration:
                self.cur = None
                continue
            except Exception:
                self.add_err("fatal", traceback.format_exc(), "smoke step")
                self.cur = None
                continue
            self.root.after(max(1, int(wait or 1)), self._resume)
            return

    def _resume(self):
        try:
            self.root.update_idletasks()
        except self.tk.TclError:
            pass
        self.next()

    # ---- what is on screen
    def walk(self, w):
        yield w
        for c in w.winfo_children():
            yield from self.walk(c)

    def mapped_widgets(self, w):
        """-> (widgets on screen under w, items drawn on its canvases) - a page drawn on one canvas isn't blank."""
        n = items = 0
        for c in self.walk(w):
            try:
                if c is not w and c.winfo_ismapped() and c.winfo_width() > 1 and c.winfo_height() > 1:
                    n += 1
                    if isinstance(c, self.tk.Canvas):
                        items += len(c.find_all())
            except self.tk.TclError:
                pass
        return n, items

    def bar_text(self, win):
        """The PageBar's eyebrow (where), title and blurb, as drawn on its canvas."""
        bar = getattr(win, "bar", None)
        out = []
        try:
            for it in bar.find_withtag("pg"):
                if bar.type(it) == "text":
                    out.append(bar.itemcget(it, "text"))
        except Exception:
            pass
        return out

    def popups(self):
        out = []
        for w in self.root.winfo_children():
            try:
                if isinstance(w, self.tk.Toplevel) and w.winfo_viewable():
                    t = w.title() or ""
                    labels = [c.cget("text") for c in self.walk(w) if isinstance(c, self.tk.Label)
                              and str(c.cget("text")).strip()][:3]
                    out.append(f"{w.winfo_class()} {t!r} {labels}"[:160])
            except Exception:
                pass
        return sorted(out)

    def shot(self, name):
        if not self.shots:
            return None
        from PIL import ImageGrab
        self.root.update()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        path = os.path.join(self.out, safe + ".png")
        try:
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            img = ImageGrab.grab(xdisplay=self.display)
            img.crop((x, y, x + self.root.winfo_width(), y + self.root.winfo_height())).save(path)
            return os.path.basename(path)
        except Exception as ex:
            self.add_err("warn_shot", repr(ex), "screenshot")
            return None

    def sidebar_rows(self):
        sb = self.sh.sidebar
        out = []
        for it in sb.items():
            if "group" in it:
                out.append(f"[{it['group']}]")
            elif "tab" in it:
                out.append("  " * it.get("depth", 1) + f"· {it['tab']}")
            elif it.get("mod") is not None:
                m = it["mod"]
                beta = " (BETA)" if getattr(m, "beta", False) or getattr(m, "labs", False) else ""
                out.append(("  " * it.get("depth", 1) + "↳ " if it.get("child") else "") + f"{m.title} <{m.key}>{beta}")
            else:
                out.append(it.get("title", it.get("key")))
        out += ["---", "Toolkit", "Settings <settings>"]
        return out

    # ---- opening, the way a person does
    def click_row(self, key):
        """Click the sidebar row for key (a page key or "key::tab"). -> True if the row was there."""
        sb = self.sh.sidebar
        sb.redraw()
        self.root.update_idletasks()
        row = next(((y0, y1) for k, y0, y1 in sb._rows if k == key), None)
        if row is None:
            return False

        class E:
            pass
        e = E()
        e.y, e.x = (row[0] + row[1]) // 2, 40
        e.widget = sb
        sb._click(e)
        return True

    def chain(self, key):
        out, k = [], key
        while k and k not in out:
            out.insert(0, k)
            k = getattr(self.sh.modules.get(k), "parent", None)
        return out

    def open_page(self, key):
        """-> how it was reached: sidebar / goto / shell."""
        sh = self.sh
        ch = self.chain(key)
        for k in ch[:-1]:                               # the parents first, so the child's row is listed
            if sh.active != k:
                sh.sidebar.folded.discard(k)
                self.click_row(k)
                yield 300
        sh.sidebar.folded.discard(key)
        home = sh.tab_home(key)
        on_own = sh.active == key and (not home or sh.tab_current(key) == home)
        if on_own and key != "settings":
            return "sidebar (already open)"
        if self.click_row(key):
            return "sidebar"
        from soe2.goto import GoTo
        try:
            for kind, title, where, words, fn in GoTo(self.app).entries():
                if kind == "Page" and title == sh.modules[key].title:
                    fn()
                    return "goto"
        except Exception:
            import traceback
            self.add_err("fatal", traceback.format_exc(), "GoTo.entries")
        sh.open(key)
        return "shell"

    def open_tab(self, key, tab):
        if self.click_row(f"{key}::{tab}"):
            return "sidebar"
        self.sh.open_tab(key, tab)
        return "shell.open_tab"

    def clipped(self, win):
        """Controls (Button, Label, Entry, Combobox, SegBar) the user can't fully see. Rules:
          edge     - right edge more than CLIP_SLACK px past the page's right edge, or past any parent's (a parent
                     cuts its children off), checked on controls on screen (viewable) and not scrolled out of view
                     vertically. Skipped: anything inside a canvas that scrolls sideways (a wide table may).
          squeezed - a Button/Label/SegBar given less width than it asks for (text cut off); not for wrapping labels.
          no room  - pack/grid still manages it but there was no room, so it isn't mapped under a parent that is.
        -> ["rule Class 'text' (path) detail", ...]"""
        from tkinter import ttk
        try:
            from soe2.style import SegBar
        except Exception:
            SegBar = ()
        kinds = (self.tk.Button, self.tk.Label, self.tk.Entry, ttk.Combobox) + ((SegBar,) if SegBar else ())
        fixed = (self.tk.Button, self.tk.Label) + ((SegBar,) if SegBar else ())
        out = []
        try:
            px0, px1 = win.winfo_rootx(), win.winfo_rootx() + win.winfo_width()
            py0, py1 = win.winfo_rooty(), win.winfo_rooty() + win.winfo_height()
        except self.tk.TclError:
            return out

        def edge(c):
            """-> (the right edge that cuts c off, False if a sideways-scrolling canvas is above it)"""
            lim, w = px1, c.master
            while w is not None and w is not win:
                if isinstance(w, self.tk.Canvas) and str(w.cget("xscrollcommand")):
                    return lim, False
                lim = min(lim, w.winfo_rootx() + w.winfo_width())
                w = w.master
            return lim, True

        def label(rule, c, detail):
            txt = ""
            try:
                txt = str(c.cget("text"))
            except Exception:
                pass
            if not txt and isinstance(c, (self.tk.Entry, ttk.Combobox)):
                txt = "<" + str(c.cget("textvariable") or "input") + ">"
            txt = " ".join(txt.split())[:30]
            return f"{rule} {type(c).__name__} {txt!r} ({str(c).replace(str(win.body), '.body')[-60:]}) {detail}"
        for c in self.walk(win.body):
            try:
                if not isinstance(c, kinds):
                    continue
                if not c.winfo_ismapped():
                    m = c.master
                    if c.winfo_manager() in ("pack", "grid") and m is not None and m.winfo_viewable() and \
                            m.winfo_width() > 1 and c.winfo_reqwidth() > 1:
                        out.append(label("no room", c, "(not shown)"))
                    continue
                if not c.winfo_viewable() or c.winfo_width() < 2:
                    continue
                y0, y1 = c.winfo_rooty(), c.winfo_rooty() + c.winfo_height()
                if y1 <= py0 or y0 >= py1:
                    continue
                lim, ok = edge(c)
                if not ok:
                    continue
                x1 = c.winfo_rootx() + c.winfo_width()
                if x1 > lim + CLIP_SLACK:
                    out.append(label("edge", c, f"+{x1 - lim}px"))
                elif isinstance(c, fixed) and c.winfo_reqwidth() > c.winfo_width() + CLIP_SLACK and \
                        not int(str(c.cget("wraplength")) or 0 if "wraplength" in c.keys() else 0):
                    out.append(label("squeezed", c, f"{c.winfo_width()} of {c.winfo_reqwidth()}px"))
            except (self.tk.TclError, ValueError):
                continue
        return out

    def measure(self, key, rec, tab=None):
        sh = self.sh
        win = sh.windows.get(key)
        rec["active"] = sh.active
        rec["state"] = getattr(win, "state_", None)
        try:
            rec["mapped"] = bool(win.winfo_ismapped())
            rec["w"], rec["h"] = win.winfo_width(), win.winfo_height()
            rec["widgets"], rec["canvas_items"] = self.mapped_widgets(win.body)
        except Exception as ex:
            rec["mapped"], rec["w"], rec["h"], rec["widgets"], rec["canvas_items"] = False, 0, 0, 0, 0
            rec["why"] = repr(ex)
        bt = self.bar_text(win) if win is not None else []
        mod = sh.modules.get(key)
        rec["header"] = bt
        rec["title"] = (mod.title if key == "dashboard" and not bt else
                        next((t for t in bt if t == getattr(mod, "title", None)), bt[1] if len(bt) > 1 else
                             (bt[0] if bt else "")))
        try:
            rec["where"] = sh.where(key)
        except Exception:
            rec["where"] = None
        if tab is not None:
            rec["tab_now"] = sh.tab_current(key)
        rec["popups"] = self.popups()
        rec["clipped"] = self.clipped(win) if rec.get("mapped") else []
        if rec["clipped"]:
            self.add_err("clip", f"{len(rec['clipped'])} clipped: " + "; ".join(rec["clipped"][:8]),
                         f"{len(rec['clipped'])} clipped on {key}" + (f" \u203a {tab}" if tab else ""))
        why = []
        if key in REDIRECT:
            rec["redirect"] = REDIRECT[key]
        else:
            if rec["state"] != "open":
                why.append(f"window state {rec['state']}")
            if sh.active != key:
                why.append(f"active page is {sh.active}")
            if not rec.get("mapped"):
                why.append("not on screen")
            if rec.get("w", 0) < 50 or rec.get("h", 0) < 50:
                why.append(f"size {rec.get('w')}x{rec.get('h')}")
            if rec.get("widgets", 0) < 2 and rec.get("canvas_items", 0) < 5:
                why.append(f"blank ({rec.get('widgets')} widgets, {rec.get('canvas_items')} canvas items)")
            if tab is not None and rec.get("tab_now") != tab:
                why.append(f"tab shown is {rec.get('tab_now')!r}")
        if CLIP_FAIL and rec["clipped"] and key in P1:
            here = tab or sh.tab_current(key)
            if P1[key] is None or here in P1[key]:
                why.append(f"{len(rec['clipped'])} clipped control(s) on a P1 page: " + "; ".join(rec["clipped"][:4]))
        errs = [e for e in rec.get("errors", []) if e["kind"] in FAIL_KINDS]
        if errs:
            why.append(f"{len(errs)} traceback(s): " + "; ".join(e["where"] for e in errs)[:300])
        rec["ok"] = not why
        rec["why"] = "; ".join(why) if why else None

    # ---- the plan
    def plan(self):
        sh = self.sh
        self.R["app_version"] = getattr(__import__("soe2"), "__version__", "?")
        self.then(self.check_startup)
        keys = [m.key for m in self.app.mods if m.key != "settings"]
        for key in keys:
            self.then(lambda k=key: self.do_page(k))
        self.then(self.check_settings)
        self.then(self.check_goto)
        self.then(self.check_goto_enter)
        self.then(self.check_end)

    def check_startup(self):
        self.CTX[0] = "check:startup"
        self.CUR[0] = self.R["checks"].setdefault("startup", {})
        yield 1500
        sh, app = self.sh, self.app
        mods = []
        for m in self.app.mods:
            mods.append({"key": m.key, "title": m.title, "kind": getattr(m, "kind", ""),
                         "parent": getattr(m, "parent", None), "hidden": bool(getattr(m, "hidden", False)),
                         "advanced": bool(getattr(m, "advanced", False)), "labs": bool(getattr(m, "labs", False)),
                         "beta": bool(getattr(m, "beta", False)), "visible": sh.visible(m), "listed": sh.listed(m)})
        self.R["modules"] = mods
        rows = self.sidebar_rows()
        self.R["sidebar"] = {"active": sh.active, "rows": rows, "compact": sh.sidebar.compact}
        st = getattr(app, "status", None)
        ok_status = st is not None and st.winfo_ismapped() and sh.strip.winfo_ismapped() and sh.strip.winfo_height() > 4
        self.R["checks"]["status_bar"] = {"ok": bool(ok_status), "text": st.cget("text") if st is not None else None,
                                          "strip_h": sh.strip.winfo_height(),
                                          "why": None if ok_status else "status bar missing or not on screen"}
        self.R["checks"]["startup"].update({"ok": sh.active is not None, "active": sh.active,
                                            "popups": self.popups(), "shot": self.shot("_startup"),
                                            "why": None if sh.active else "no page open after start"})
        self.R["checks"]["sidebar"] = {"ok": len(rows) > 5, "rows": len(rows),
                                       "why": None if len(rows) > 5 else "sidebar has (almost) no rows"}

    def do_page(self, key):
        sh = self.sh
        mod = sh.modules[key]
        rec = {"key": key, "module_title": mod.title, "tabs": []}
        self.R["pages"].append(rec)
        self.CTX[0], self.CUR[0] = f"page:{key}", rec
        t0 = time.time()
        try:
            rec["via"] = yield from self.open_page(key)
        except Exception:
            import traceback
            self.add_err("fatal", traceback.format_exc(), f"opening {key}")
            rec["via"] = "error"
        self.root.update_idletasks()
        rec["open_ms"] = int((time.time() - t0) * 1000)
        yield SETTLE_MS
        self.measure(key, rec)
        rec["home_tab"] = sh.tab_home(key)
        rec["sidebar_here"] = self.sidebar_rows()
        rec["shot"] = self.shot(f"{key}__-")
        if key in REDIRECT:
            try:
                self.app.overlay.hide_notes()
            except Exception:
                pass
            return
        tabs = ([sh.tab_home(key)] if sh.tab_home(key) else []) + list(sh.tab_titles(key))
        for tab in tabs:
            trec = {"tab": tab}
            rec["tabs"].append(trec)
            self.CTX[0], self.CUR[0] = f"tab:{key}::{tab}", trec
            t0 = time.time()
            try:
                if tab == sh.tab_home(key):
                    if sh.active == key and sh.tab_current(key) == tab:
                        trec["via"] = "sidebar (already on it)"
                    else:
                        trec["via"] = "sidebar (page row)" if self.click_row(key) else "shell.open_tab"
                        if sh.tab_current(key) != tab:
                            trec["via"] = "shell.open_tab"
                            sh.open_tab(key, tab)
                else:
                    trec["via"] = self.open_tab(key, tab)
            except Exception:
                import traceback
                self.add_err("fatal", traceback.format_exc(), f"opening tab {key}::{tab}")
            self.root.update_idletasks()
            trec["open_ms"] = int((time.time() - t0) * 1000)
            yield 600
            self.measure(key, trec, tab=tab)
            trec["shot"] = self.shot(f"{key}__{tab}")

    def check_settings(self):
        sh, app = self.sh, self.app
        rec = {"key": "settings", "module_title": sh.modules["settings"].title, "tabs": []}
        self.R["pages"].append(rec)
        under = sh.active
        self.CTX[0], self.CUR[0] = "page:settings", rec
        rec["via"] = "sidebar" if self.click_row("settings") else (sh.open("settings") or "shell")
        yield SETTLE_MS
        self.measure("settings", rec)
        rec["shot"] = self.shot("settings__-")
        nb = getattr(app, "set_nb", None)
        for t in list(getattr(nb, "titles", []) or []):
            trec = {"tab": t}
            rec["tabs"].append(trec)
            self.CTX[0], self.CUR[0] = f"tab:settings::{t}", trec
            try:
                app.open_settings_tab(t)
                trec["via"] = "app.open_settings_tab"
            except Exception:
                import traceback
                self.add_err("fatal", traceback.format_exc(), f"settings tab {t}")
            yield 500
            self.measure("settings", trec)
            trec["tab_now"] = nb.titles[nb.cur] if nb.cur is not None else None
            if trec["tab_now"] != t:
                trec["ok"] = False
                trec["why"] = ((trec.get("why") or "") + f"; tab shown is {trec['tab_now']!r}").lstrip("; ")
            trec["shot"] = self.shot(f"settings__{t}")
        # close with Esc
        self.CTX[0] = "check:settings_close"
        self.CUR[0] = self.R["checks"].setdefault("settings_close", {})
        self.root.focus_force()
        self.root.event_generate("<Escape>")
        yield 500
        w = sh.windows["settings"]
        ok = w.state_ != "open" and not w.winfo_ismapped()
        self.R["checks"]["settings_close"].update({
            "ok": ok, "page_under": under, "active_after": sh.active,
            "why": None if ok else f"Settings still open after Esc (state {w.state_})"})

    def goto_box(self):
        g = getattr(self.sh, "_goto", None)
        return g if g is not None and g.win is not None else None

    def check_goto(self):
        self.CTX[0] = "check:goto"
        rec = self.CUR[0] = self.R["checks"].setdefault("goto", {})
        self.root.focus_force()
        yield 200
        self.root.event_generate("<Control-k>")
        yield 700
        g = self.goto_box()
        why = []
        rec["opened_by_ctrl_k"] = g is not None
        if g is None:
            self.sh.goto()                                  # (the sidebar's row does the same)
            yield 500
            g = self.goto_box()
            why.append("Ctrl+K didn't open Go to anything")
        if g is None:
            rec.update({"ok": False, "why": "Go to anything doesn't open"})
            return
        rec["entries"] = len(g._all)
        rec["kinds"] = {}
        for e in g._all:
            rec["kinds"][e[0]] = rec["kinds"].get(e[0], 0) + 1
        rec["empty_rows"] = [f"{r[0]}: {r[1]} ({r[2]})" for r in g.rows]
        g.entry.focus_force()
        yield 100
        for ch in "rates":
            g.entry.event_generate("<KeyPress>", keysym=ch)
        yield 300
        rec["typed_via"] = "keys"
        if g.q.get() != "rates":
            g.q.set("rates")
            rec["typed_via"] = "set (key events didn't reach the box)"
            yield 200
        rec["query"] = g.q.get()
        rec["rows"] = [f"{r[0]}: {r[1]} ({r[2]})" for r in g.rows]
        rec["shot"] = self.shot("_goto")
        if not g.rows:
            why.append("no rows for 'rates'")
        g.entry.event_generate("<Escape>")
        yield 400
        rec["closed_by_esc"] = self.goto_box() is None
        if not rec["closed_by_esc"]:
            why.append("Esc didn't close it")
            g.close()
        rec["ok"] = not why
        rec["why"] = "; ".join(why) or None

    def check_goto_enter(self):
        """Go to anything really goes there: type a page name, Enter -> that page is open."""
        self.CTX[0] = "check:goto_enter"
        rec = self.CUR[0] = self.R["checks"].setdefault("goto_enter", {})
        sh = self.sh
        target = next((m for m in self.app.mods if m.key == "rates"), None) or self.app.mods[1]
        start = next((m.key for m in self.app.mods if m.key == "dashboard"), None)
        if start:
            sh.open(start)
            yield 300
        sh.goto()
        yield 400
        g = self.goto_box()
        if g is None:
            rec.update({"ok": False, "why": "Go to anything doesn't open"})
            return
        g.q.set(target.title)
        yield 200
        rec["first_row"] = f"{g.rows[0][0]}: {g.rows[0][1]}" if g.rows else None
        g.entry.event_generate("<Return>")
        yield 700
        rec["target"], rec["active_after"] = target.key, sh.active
        rec["ok"] = sh.active == target.key and self.goto_box() is None
        rec["why"] = None if rec["ok"] else f"Enter on {target.title!r} left {sh.active!r} open"

    def check_end(self):
        self.CTX[0] = "end"
        self.CUR[0] = {}
        yield 1000                                  # late timers from the last steps


# ============================================================================
def main():
    global GEOM, SCREEN, SHAPE, CLIP_FAIL, SHARE
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", help="name of this run (folder under --out); default: a time stamp")
    ap.add_argument("--compare", nargs="+", metavar="RUN", help="BASELINE [NEW]: diff two runs")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--data", default=DATA, help="test data folder copied into the throwaway HOME")
    ap.add_argument("--display", default=":11")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--keep-home", action="store_true")
    ap.add_argument("--geom", default=f"{GEOM[0]}x{GEOM[1]}", help="app window size WxH (default 1600x1000)")
    ap.add_argument("--screen", default=f"{SCREEN[0]}x{SCREEN[1]}", help="Xvfb size WxH when this run starts it")
    ap.add_argument("--shape", choices=("full", "drawer"), default="full",
                    help="full (default) or drawer (no-op until soe2/drawer.py exists)")
    ap.add_argument("--share", type=float, default=None, help="drawer.share (width share of the game, default 0.40)")
    ap.add_argument("--clip-fail", action="store_true", help="a clipped control on a P1 page fails the run")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--checks", action="store_true", help="also run tools/check_*.py and the test suite -> tests.txt")
    ap.add_argument("--self-test", action="store_true", help="break pages on purpose: the run must fail")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    a = ap.parse_args()
    GEOM, SCREEN, SHAPE, CLIP_FAIL, SHARE = parse_wh(a.geom), parse_wh(a.screen), a.shape, a.clip_fail, a.share
    if a.child:
        child(a.child, a.display, not a.no_shots)
        return 0
    if a.compare and not a.run:                       # compare only (two runs, or baseline vs the newest run)
        return do_compare(a, a.compare[0], a.compare[1] if len(a.compare) > 1 else None)
    a.run = a.run or time.strftime("%Y%m%d-%H%M%S")
    rc = run(a)
    if a.checks:
        rc = max(rc, run_checks(a, os.path.join(a.out, a.run)))
    if a.compare:
        rc = max(rc, do_compare(a, a.compare[0], a.run))
    return rc


if __name__ == "__main__":
    sys.exit(main())
