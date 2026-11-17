"""3.0.6 (owner: dragging the Drawer's edge is "laggy as fuck" on every page but Dashboard - fixed blind four times, not
gone): Settings › Advanced › Problems › Measure resizing. The app resizes its own window step by step on a few pages,
the way a drag does, in different ways, and times each step - on YOUR PC, where the lag is. Written to
resize_test_drawer.txt / _full.txt in the data folder: page names, step times and counts only, nothing about you.

Ways, for each page:
  normal        - as it is (the page laid out once the size settles)
  laid out      - the page laid out on every step
  page hidden   - the open page(s) taken off (is it the page at all?)
  page fixed    - the open page kept at its size (is it laying the page out, or moving its parts on the screen?)
  bars hidden   - also the sidebar, the top strip and the status bar off (what's left: the window itself)
Windows: the number of the app's windows (each button, label ... is one) is counted too."""
import os
import sys
import time
import tkinter as tk

from . import buglog
from .config import DATA_DIR

PAGES = ("dashboard", "settings", "regex", "pricecheck")
STEPS = 16


def _win_count(root):
    """(all, visible) child windows of the app's window - Windows only."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        top = u.GetParent(root.winfo_id()) or root.winfo_id()
        n = [0, 0]
        cb_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(h, _l):
            n[0] += 1
            if u.IsWindowVisible(h):
                n[1] += 1
            return True
        u.EnumChildWindows(top, cb_t(cb), 0)
        return tuple(n)
    except Exception:
        buglog.caught()
        return None


def _steps(root, w0, h0, each=None):
    """STEPS resizes (wider, narrower, ...) -> (median ms, worst ms) for one step drawn on the screen. each(): run
    after every resize (the page laid out at once)."""
    times = []
    for i in range(STEPS):
        w = w0 + (24 if i % 2 == 0 else 0) + (i // 2) * 2
        t = time.perf_counter()
        root.geometry(f"{w}x{h0}")
        if each:
            root.update_idletasks()
            each()
        root.update()                                    # (layout + painting, as a drag step waits for)
        times.append((time.perf_counter() - t) * 1000)
    root.geometry(f"{w0}x{h0}")
    root.update()
    times.sort()
    return times[len(times) // 2], times[-1]


def run(app):
    root, sh = app.root, app.shell
    lines = [f"Measure resizing - {time.strftime('%Y-%m-%d %H:%M')} - "
             f"{'Drawer' if getattr(app, 'drawer_shown_as_drawer', lambda: False)() else 'Full window'} - "
             f"{STEPS} steps each, ms per step (median / worst)", ""]
    root.update()
    w0, h0 = root.winfo_width(), root.winfo_height()
    was = sh.active
    bars = [w for w in root.winfo_children() if isinstance(w, (tk.Frame, tk.Canvas)) and w is not sh.desk
            and w.winfo_manager() == "pack" and w.winfo_ismapped()]
    try:
        for key in PAGES:
            try:
                sh.open(key)
            except Exception:
                buglog.caught()
                continue
            root.update()
            shown = [w for w in sh.windows.values() if getattr(w, "_shown", False) and w.winfo_ismapped()]
            wc = _win_count(root)
            res = {"normal": _steps(root, w0, h0),                # (as the app does now: laid out 40 ms after)
                   "laid out": _steps(root, w0, h0, sh._pages_fit)}  # (laid out on every step, as before 3.0.6)
            for w in shown:                                       # page fixed: its size, not the area's
                tk.Place.place_configure(w, relwidth=0, relheight=0, width=w.winfo_width(), height=w.winfo_height())
            sh._fit_hold = True
            res["page fixed"] = _steps(root, w0, h0)
            for w in shown:
                w.place_forget()
            res["page hidden"] = _steps(root, w0, h0)
            order = [(b, b.pack_info()) for b in root.pack_slaves()]   # (put back in the same order)
            for b in bars:
                b.pack_forget()
            res["bars hidden"] = _steps(root, w0, h0)
            for b, _i in order:
                b.pack_forget()
            for b, info in order:
                try:
                    b.pack(**{k: v for k, v in info.items() if k != "in"})
                except tk.TclError:
                    pass
            sh._fit_hold = False
            for w in shown:
                w._place_now()
            root.update()
            lines.append(f"{key}:" + (f"  ({wc[1]} of {wc[0]} windows shown)" if wc else ""))
            for k, (med, worst) in res.items():
                lines.append(f"  {k:<12} {med:7.1f} / {worst:7.1f}")
            lines.append("")
    finally:
        try:
            if was:
                sh.open(was)
            sh._fit_hold = False
            sh._pages_fit_soon()
        except Exception:
            buglog.caught()
    shape = "drawer" if getattr(app, "drawer_shown_as_drawer", lambda: False)() else "full"
    path = os.path.join(DATA_DIR, f"resize_test_{shape}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        buglog.caught()
    return path, lines
