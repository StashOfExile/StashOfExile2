"""The Read Key (GGG policy, Nov 2026): every helper that reads the screen does it once, when you press the Read Key.

The owner takes GGG's rule at its strictest: a read needs a key pressed FOR the read. So the Read Key is a key you pick
only for this (Settings › Keybinds, or Setup's helpers step): Ctrl+Shift+R as the app comes (screenread.DEFAULT_KEY).
If you clear it nothing reads the screen at all and the helpers that need it say so with one button, "Set the Read Key". It can't be a key the app uses
for something else, one of the game's everyday keys (Tab, Enter, Space, Esc ...) or a mouse button, and while the
game is in front the app only listens (the key is never blocked - the game still gets it). Old settings with Tab - the
game's map key, the default before - are cleared once (migrations.look_key_dedicated) and the app says why.
On each press, in the game:
  1. screenread.grant() opens one read (a held key's repeats don't - let it go first),
  2. the helpers that apply where you are (the game's log says: a map, your hideout, a town, the campaign ...) each get
     their part of ONE picture of the game window (screenread.capture) on one background thread. Which apply is
     decided BEFORE the picture: none -> no picture, no read mark, one log line ("nothing to read here"),
  3. their results come back to the window's thread, the app's log gets one line ("F9 pressed: read the screen once
     for Ritual, Temple") and the read mark shows it for a second over the game (readmark.py) - "Reading the screen",
     or "Read the screen · nothing here" when no helper could use anything in the picture (found()).
No press, no read: nothing here runs on a timer. Helpers that follow the game's log (Breach, Campaign ...) still do that
by themselves - the log has no per-press limit."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import screenread as SR
from .config import SETTINGS

NAME = "Read Key"                   # (names.py)
SET_BUTTON = "Set the Read Key"
# the game's everyday keys (its defaults) and keys that mean something everywhere: never the Read Key
GAME_KEYS = {0x09: "Tab (the game's map key)", 0x0D: "Enter (the game's chat)", 0x20: "Space",
             0x1B: "Esc", 0x08: "Backspace", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt"}
AREA_WORDS = {"map": "in a map", "hideout": "in your hideout", "town": "in a town", "other": "in this area",
              "login": "at the character screen"}
UNSET_STATUS = "No Read Key set: it reads nothing until you set one."
NEED_LINE = "The screen helpers read only when you press your Read Key - a key just for that. None is set yet."


def look_key_problem(text, others=()):
    """Why this key can't be the Read Key (one line), or None. others: [(what, key text)] - the app's other keys."""
    from .overlay import MOUSE_VKS, key_label, parse_key
    t = (text or "").strip()
    if not t:
        return None
    k = parse_key(t)
    if not k:
        return f"\"{t}\" isn't a key the app knows."
    if k[0] in MOUSE_VKS:
        return "A mouse button can't be the Read Key - a click is not a key press."
    if k[0] in GAME_KEYS and not any(k[1:]):
        return f"{GAME_KEYS[k[0]]} can't be the Read Key - pick a key only for this."
    if k[0] == 0x43 and k[1]:
        return "Ctrl+C is the game's copy - pick a key only for this."
    for what, key in others:
        ok = parse_key(key) if key and key != "Ctrl+Alt+C" else ((0x43, True, True, False) if key == "Ctrl+Alt+C"
                                                                 else None)
        if ok and ok == k:
            return f"{key_label(t)} is already \"{what}\" - pick a key only for this."
    return None


def found(work, res):
    """Could a helper use anything in the press's picture? Its work's found(res) says (Trial of the Sekhemas,
    Expedition, Favours ...); a helper without one counts as found - "nothing here" is only said when it's sure."""
    fn = getattr(work, "found", None)
    if fn is None:
        return True
    try:
        return bool(fn(res))
    except Exception:
        buglog.caught()
        return True


class LookPage:
    """Mixed into App."""

    def look_key(self):
        v = SETTINGS.get("look_key")                    # (None = never set: the default; "" = you cleared it)
        return str(SR.DEFAULT_KEY if v is None else v).strip()

    def look_key_set(self):
        from .overlay import parse_key
        return bool(parse_key(self.look_key()))

    def look_key_vk(self):
        """The Read Key's key code, or None (screenread.ONLY_KEY: the one key that may open a read)."""
        from .overlay import parse_key
        k = parse_key(self.look_key())
        return k[0] if k else None

    def look_key_label(self):
        """The key's own name ("F9"), or "" when there's none."""
        from .overlay import key_label
        return key_label(self.look_key()) if self.look_key_set() else ""

    def look_key_text(self):
        """How the app's text names it: "your Read Key (F9)", or "your Read Key" until one is set."""
        k = self.look_key_label()
        return f"your {NAME} ({k})" if k else f"your {NAME}"

    def look_on_key(self, vk, ctrl, alt, shift):
        """(keyboard thread) The Read Key's key-down in the game -> one read for the helpers. -> True: the key was the
        Read Key in the game and a read was opened or held. It is only heard: the caller never swallows it (the game
        still gets the key). No Read Key: never."""
        from .overlay import parse_key, game_active, POE_TITLE
        k = parse_key(self.look_key())
        if not k or vk != k[0] or vk in SR.MOUSE:
            return False
        if any(k[1:]) and (ctrl, alt, shift) != k[1:]:
            return False                                # (a Read Key with Ctrl / Alt / Shift: only with them)
        if not any(k[1:]) and (ctrl or alt):
            return False                                # (a plain one: with Shift held too - you may be moving)
        if not game_active((getattr(self, "overlay", None) and self.overlay.cfg.get("poe_title")) or POE_TITLE):
            return False                                # outside the game: nothing is read, the key is yours
        if SR.grant(self.look_key_label(), hold=vk):
            self.ui_q.put(("look",))
        return True

    def look_area(self):
        """Where you are for the Read Key (the game's log): "map" / "hideout" / "town" / "other", "login" at the
        character screen, or None (not known yet). Until the first area change after the app starts, the log's last
        area (alerts_page.breach_start) - not "anywhere"."""
        if getattr(self, "look_at_login", False):
            return "login"
        a = getattr(self, "br_area", None)
        return a if a is not None else getattr(self, "br_area_start", None)

    def look_jobs(self, ctx):
        """The helpers that apply now, in order: [(name, work, done)] - decided from where you are (the game's log),
        each helper's switch and what it needs, BEFORE any picture. Scan stash's card, once Start reading armed it,
        takes the press alone. At the character screen nothing applies."""
        if ctx.get("area") == "login":
            return []
        ss = getattr(self, "ss", None)
        if ss and ss.get("armed"):
            job = self.stash_scan_job(ctx)
            return [job] if job else []
        out = []
        skip = ()
        import sys
        if sys.platform.startswith("linux"):         # Linux with no OCR engine: helpers that only read text don't
            from . import remnant as _RM             # apply (no picture for nothing - their rows say "needs OCR")
            if _RM.ocr_available():
                skip = (self.hover_look_job, self.temple_console_job)
        for make in (self.hover_look_job, self.temple_console_job,
                     self.remnant_look_job, self.favours_look_job, self.ru_look_job, self.ws_look_job,
                     self.topup_look_job, self.sekhemas_look_job):
            if make in skip:
                continue
            try:
                job = make(ctx)
            except Exception:
                self.log_error("the Read Key")
                job = None
            if job:
                out.append(job)
        return out

    def ev_look(self):
        """(window thread) A Read Key press: the helpers that apply read their part of one picture."""
        from . import newchip
        newchip.used(NAME)                               # 3.0.0: the Read Key's NEW chip goes (used)
        from .alerts_page import game_rect
        app_g = game_rect()                              # (in the app's pixels: where its tags go)
        if not app_g:
            SR.nothing("the game window wasn't found")
            return None
        real = SR.game_real()                            # drawer build, the DPI fix: the game and the mouse in REAL
        if real:                                         # pixels, whatever this thread's DPI (drawer.pin_ui_dpi)
            ptr, g = real
        else:                                            # (not Windows / too old a Windows: as before)
            g = app_g
            try:
                ptr = self.root.winfo_pointerxy()       # (where the mouse is - not the screen's content)
            except Exception:
                ptr = (g[0] + g[2] // 2, g[1] + g[3] // 2)
        SR.set_map(g, app_g)                             # (a helper's tag: SR.to_ui; the mouse later: SR.to_screen)
        ctx = {"g": g, "rect": (g[0], g[1], g[0] + g[2], g[1] + g[3]), "ptr": ptr,
               "area": self.look_area(), "key": SR.pressed_key()}
        jobs = self.look_jobs(ctx)
        if not jobs:                                     # (owner: "if it doesn't have anything to read it shouldn't
            SR.nothing(AREA_WORDS.get(ctx["area"], "here") + ": no helper applies")   # give the alert"): no picture,
            return []                                    # no card - one line in the app's log

        def work():
            SR.capture(ctx["rect"], None)                # the press's one picture, taken now (helpers cut from it)
            got = []
            for name, w, _d in jobs:
                try:
                    got.append(w())
                except Exception:
                    buglog.caught()
                    got.append(None)
            hit = any(found(w, res) for (_n, w, _d), res in zip(jobs, got))
            SR.finish(hit)                               # one line in the app's log, the read mark; picture dropped
            return got

        def done(got):
            for (name, _w, d), res in zip(jobs, got):
                try:
                    d(res)
                except Exception:
                    self.log_error(name)
        self.run_bg(work, done)
        return [n for n, _w, _d in jobs]

    # ---------------------------------------------------------------- setting it
    def look_key_others(self):
        """The app's other keys: [(what, key text)] (a Read Key may not be one of them)."""
        try:
            return [(what, key) for what, key, _w, kid in self.all_hotkeys() if kid != "checks:look_key" and key]
        except Exception:
            buglog.caught()
            return []

    def look_key_save(self, text):
        """Set the Read Key (Settings › Keybinds, Setup). -> None when saved, else the one line saying why not (the
        old key stays)."""
        from .config import save_json
        why = look_key_problem(text, self.look_key_others())
        if why:
            return why
        SETTINGS["look_key"] = (text or "").strip()
        save_json("settings.json", SETTINGS)
        self.look_key_changed()
        return None

    def look_status(self, line):
        """A helper's "On - press your Read Key ..." status line - or, with no Read Key, that it reads nothing yet."""
        return line if self.look_key_set() else UNSET_STATUS

    def look_key_open(self):
        """"Set the Read Key": Settings › Keybinds, its row lit up and its box waiting for the key."""
        self.hotkeys_open("checks:look_key")

    # ---------------------------------------------------------------- until it's set (the empty state)
    def look_needed(self, parent, bg, line=NEED_LINE, wrap=520):
        """One line and one button, "Set the Read Key", shown while no Read Key is set (it goes once one is). ->
        the frame that holds it (packed by the caller; it's empty when a key is set)."""
        holder = tk.Frame(parent, bg=bg)
        box = tk.Frame(holder, bg=bg)
        tk.Label(box, text="ⓘ " + line, bg=bg, fg=_text(), font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=wrap).pack(side="left", fill="x", expand=True)
        ttk.Button(box, text=SET_BUTTON, command=self.look_key_open).pack(side="right", padx=(8, 0))
        holder.look_box = box
        if not hasattr(self, "_look_needed"):
            self._look_needed = []
        self._look_needed.append(holder)
        _paint(holder, self.look_key_set())
        return holder

    def look_key_changed(self):
        """A Read Key was set or cleared: every "Set the Read Key" line shows or goes; texts naming it repaint."""
        on = self.look_key_set()
        keep = []
        for h in getattr(self, "_look_needed", []):
            try:
                if h.winfo_exists():
                    _paint(h, on)
                    keep.append(h)
            except tk.TclError:
                pass
        self._look_needed = keep
        for fn in ("_ovh_state_paint", "alerts_refresh", "stash_scan_card"):
            f = getattr(self, fn, None)
            if f is None or (fn == "stash_scan_card" and not getattr(self, "ss", None)):
                continue
            try:
                f()
            except Exception:
                buglog.caught()

    def look_key_notice(self):
        """Once, after the update that gave the Read Key its default (or replaced an old Tab): say which key it is."""
        if not SETTINGS.pop("look_key_notice", False):
            return None
        from .config import save_json
        save_json("settings.json", SETTINGS)
        k = self.look_key_label()
        if not k:
            return None
        text = f"Helpers read the screen once when you press {k}. Change it in Settings › Keybinds."
        self.status_text = f"Read Key: {k} - helpers read the screen once when you press it."
        try:
            return self.app_toast(text, title="Read Key", kind="info",
                                  actions=(("Change…", self.look_key_open),))
        except Exception:
            buglog.caught()
            return None


def _text():
    from .style import C
    return C["text"]


def _paint(holder, on):
    box = holder.look_box
    if on:
        box.pack_forget()
    elif not box.winfo_manager():
        box.pack(fill="x", pady=(0, 8))
