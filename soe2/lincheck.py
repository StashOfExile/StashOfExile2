"""Linux check (names.py): what works on this Linux desktop, one line each with its fix - the session, the game window,
the keys, the screen picture, the clipboard, key sending, OCR and Client.txt.

  StashOfExile2 --check-linux        prints it and exits (0 all OK, 1 something to fix)
  Settings › Advanced › Linux check  one line (how many are OK) and an ⓘ with every line

Nothing is read here: no picture is taken and the clipboard isn't touched - it only looks at which tools are installed
and what the session says."""
import os
import sys

OK, WARN, FIX = "ok", "warn", "fix"
MARK = {OK: "✓ OK  ", WARN: "⚠ NOTE", FIX: "✗ FIX "}


def hypr_line(env=None, path=None, running=None, binds=None):
    """Hyprland (the main tested setup): its IPC, the pass-through binds, socat. -> (state, what, fix)."""
    from . import linkeys, linsys
    ver = linsys.hypr("j/version")
    if not isinstance(ver, dict):
        return FIX, "Hyprland's IPC socket didn't answer", "is HYPRLAND_INSTANCE_SIGNATURE from this session?"
    binds = linsys.hypr("j/binds") if binds is None else binds
    ours = len(linkeys.bound_lines(binds)) if isinstance(binds, list) else 0
    tag = str(ver.get("tag") or ver.get("version") or "").lstrip("v")
    what = f"IPC ok{f' ({tag})' if tag else ''} · {ours} pass-through binds in place"
    socat = linsys.which("socat", path)
    if running and running.get("hypr") is True:
        h = linkeys.HYPR
        if h.get("want"):
            what = f"IPC ok{f' ({tag})' if tag else ''} · {h.get('have', 0)} of {h['want']} pass-through binds in place"
        if h.get("err") and h["err"] != "no socat":
            return WARN, what + f" - {h['err']}", "Settings › Advanced › Problems › the app's log says which"
    what += " · socat" if socat else " · no socat"
    if not socat:
        return FIX, what, f"install socat ({linsys.install_cmd('socat')}) - the binds use it to tell the app"
    return OK, what, ""


def _keys_line(env, path, running=None):
    """The key watcher: running = linkeys.STATE (in the app), else what would start."""
    from . import linkeys, linsys
    if linsys.hypr_socket():
        return OK, "Hyprland's pass-through binds tell the app", ""
    if running and running.get("x11") is True:
        return OK, "your key presses are heard (X11 RECORD)", ""
    sess = linsys.session_type(env)
    why = running.get("x11") if running and isinstance(running.get("x11"), str) else None
    if why is None:
        if not linsys.has_x(env):
            why = "no X server (DISPLAY isn't set)"
        else:
            try:
                import Xlib  # noqa: F401
            except Exception:
                why = "python-xlib is missing"
    sock = linkeys.sock_path()
    bind = f'bind a key in your desktop to: StashOfExile2 --key "Ctrl+Shift+R" (socket {sock})'
    if why:
        return FIX, f"the key watcher can't start: {why}", ("log in with an X11 session, or " + bind) \
            if sess == "wayland" else f"install python-xlib ({linsys.install_cmd('python3-xlib')})"
    if sess == "wayland":
        return WARN, "keys are heard while the game (XWayland) is in front", \
            f"if a key does nothing: {bind}"
    return OK, "your key presses are heard (X11 RECORD)", ""


def report(env=None, path=None, running=None):
    """-> [(name, state, what, fix)]. env / path: tests (os.environ / PATH); running: linkeys.STATE in the app."""
    from . import linsys, ocrengine, screenread
    env = os.environ if env is None else env
    out = []
    sess, desk = linsys.session_type(env), linsys.desktop(env)
    what = {"x11": "X11", "wayland": "Wayland"}.get(sess, "no desktop session")
    if linsys.hypr_socket():                         # the main tested setup: Arch + Hyprland, the game through Proton
        out.append(("Hyprland",) + hypr_line(env, path, running))
        out.append(("Session", OK if linsys.has_x(env) else FIX,
                    f"Wayland (Hyprland){' + XWayland' if linsys.has_x(env) else ''}",
                    "" if linsys.has_x(env) else "the app needs XWayland (Tk is an X11 toolkit)"))
    else:
        out.append(("Session", OK if sess == "x11" else WARN if sess == "wayland" else FIX,
                    what + (f" ({desk})" if desk else ""),
                    "" if sess == "x11" else "Hyprland or X11 (\"Xorg\" at the login screen) work best - see "
                    "linux/README.md" if sess == "wayland" else "start it from your desktop, not a plain terminal"))
    if linsys.hypr_socket():
        out.append(("Game window", OK, "Hyprland tells which window is in front", ""))
    elif linsys.has_x(env) and linsys.x_can_tell():
        out.append(("Game window", OK, "the window manager tells which window is in front", ""))
    else:
        out.append(("Game window", WARN, "can't tell when the game is in front - the in-game keys stay off",
                    "your window manager doesn't say which window is in front (EWMH) - GNOME, KDE, Xfce, "
                    "Cinnamon and Hyprland do" if sess != "wayland" else
                    "under Wayland the game must run through XWayland (Proton's default) - or use Hyprland"))
    out.append(("Keys",) + _keys_line(env, path, running))
    out.append(("Screen picture",) + screenread.capture_check(env, path))
    clip = linsys.clipboard_tool(env, path)
    if clip:
        out.append(("Clipboard", OK, clip, ""))
    elif linsys.has_x(env) and sess != "wayland":
        out.append(("Clipboard", WARN, "Tk's own (X11) - chat commands can't put your clipboard back",
                    f"install xclip ({linsys.install_cmd('xclip')})"))
    else:
        pkg = "wl-clipboard" if sess == "wayland" else "xclip"
        out.append(("Clipboard", FIX, "no clipboard tool", f"install {pkg} ({linsys.install_cmd(pkg)})"))
    kt = linsys.key_tool(env, path)
    if kt:
        out.append(("Key sending", OK, f"{kt} (chat commands, the price check key's copy)", ""))
    else:
        out.append(("Key sending", FIX, "no xdotool / ydotool: chat commands and the price check key can't press keys",
                    f"install xdotool ({linsys.install_cmd('xdotool')})"))
    eng = ocrengine.engine()
    if eng:
        out.append(("OCR", OK, {"tesseract": "Tesseract", "pytesseract": "Tesseract (pytesseract)",
                                "windows": "Windows"}.get(eng, eng), ""))
    else:
        out.append(("OCR", FIX, "no OCR engine: the helpers that read text are off",
                    f"install tesseract ({ocrengine.install_hint()})"))
    from .gamelog import find_log
    try:
        from .config import SETTINGS
        saved = SETTINGS.get("tracker", {}).get("log_path") if isinstance(SETTINGS.get("tracker"), dict) else None
    except Exception:
        saved = None
    log = find_log(saved) or linsys.find_log()
    if log:
        out.append(("Client.txt", OK, _short(log), ""))
    else:
        out.append(("Client.txt", FIX, "not found",
                    "start the game once (Steam / Proton writes it to steamapps/common/Path of Exile 2/logs), "
                    "or pick it in Settings › Advanced › Game log"))
    return out


def _short(p):
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if home and p.startswith(home) else p


def summary(rows):
    """'7 of 8 OK · 1 to fix: OCR' (one line)."""
    fix = [r[0] for r in rows if r[1] == FIX]
    ok = sum(1 for r in rows if r[1] == OK)
    line = f"{ok} of {len(rows)} OK"
    if fix:
        line += f" · {len(fix)} to fix: " + ", ".join(fix)
    elif any(r[1] == WARN for r in rows):
        line += " · " + ", ".join(r[0] for r in rows if r[1] == WARN) + ": see ⓘ"
    return line


def text(rows):
    """Every line, with its mark and word (never by color alone) and its fix."""
    out = []
    for name, st, what, fix in rows:
        out.append(f"{MARK[st]}  {name}: {what}" + (f"\n          fix: {fix}" if fix else ""))
    return "\n".join(out)


def main(argv=None):
    """StashOfExile2 --check-linux -> prints the check; 0 when nothing needs fixing."""
    rows = report()
    from .config import APP_VERSION
    print(f"StashOfExile2 {APP_VERSION} - Linux check")
    print(text(rows))
    print(summary(rows))
    print("Report a bug: https://github.com/StashOfExile/StashOfExile2/issues (paste these lines)")
    return 1 if any(r[1] == FIX for r in rows) else 0


# ---------------------------------------------------------------- Settings › Advanced › Linux check
def build(app, section):
    """Settings › Advanced: one line (how many are OK), an ⓘ with every line and its fix, and Check again."""
    import tkinter as tk
    from tkinter import ttk
    from .style import C, Tooltip
    from . import linkeys
    row = section("Advanced", "Linux check", "What works on this Linux desktop - each line has its fix.")
    P2 = row.cget("bg")
    lbl = tk.Label(row, text="", bg=P2, fg=C["text"], anchor="w")
    lbl.pack(side="left")
    info = tk.Label(row, text="ⓘ", bg=P2, fg=C["muted"], cursor="question_arrow")
    info.pack(side="left", padx=(4, 8))
    tip = Tooltip(info, "")

    def paint():
        from . import ocrengine
        ocrengine.rescan()
        try:
            rows = report(running=dict(linkeys.STATE))
        except Exception:
            from . import buglog
            buglog.caught()
            return
        lbl.config(text=summary(rows))
        tip.text = text(rows) + "\n\nThe same in a terminal: StashOfExile2 --check-linux"
    ttk.Button(row, text="Check again", command=paint, style="Quiet.TButton").pack(side="left")
    paint()
    app.lin_check_paint = paint
    return row


if __name__ == "__main__":
    sys.exit(main())
