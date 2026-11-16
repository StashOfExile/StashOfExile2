"""NEW chip (3.0.0, owner): a small "NEW" chip on a feature that is new in this version - on its row, and on its
page's icon in the rail (the Full window's sidebar and the Drawer's rail). It clears for good the first time you open
the place it lives in (its page, its tab) or use it; your settings keep that (settings.json "new_seen").

One name: "NEW chip" (names.FEATURES). Never color alone: the chip is the word NEW. The one BETA chip rule holds: a
Beta feature shows NEW until it has been used, then its BETA as before (on a Helpers row a helper's Beta is a word in
its gray line, never a chip).

Opening a place: the chip on its row stays while you are there (so you see what was new), the rail's chip goes at
once; leave and the row's chip goes too. Using the feature clears both at once.

GGG ToS: looks only - nothing here touches the game."""
import tkinter as tk

from . import buglog
from .config import SETTINGS, save_json

NAME = "NEW chip"                      # (names.py)
WORD = "NEW"
TIP = "New in 3.0 - this chip goes once you've opened or used it."
SINCE = "3.0.0"

# feature (its name in names.FEATURES) -> where it lives: the rail's page, and the tab of that page whose opening
# counts as opening it. Only the genuinely new 3.0 features with a place of their own.
FEATURES = {
    "Look key": ("settings", "Keybinds"),              # Settings › Keybinds: the key every screen read waits for
    "Drawer": ("settings", "General"),                 # Settings › General › Window: Drawer or Full window
    "Trial of the Sekhemas": ("tracker", "Helpers"),   # Overlay › Helpers: the trial map's legend (BETA)
}

_rows = {}                             # feature -> [chip widgets]
_listeners = []                        # callables run when a chip goes (the sidebar redraws)
_leaving = set()                       # opened now: the row's chip goes once you leave the place


def _seen():
    s = SETTINGS.get("new_seen")
    if not isinstance(s, dict):
        s = SETTINGS["new_seen"] = {}
    return s


def is_new(name):
    """Is this feature's NEW chip still on? (Not yet opened or used.)"""
    return name in FEATURES and not _seen().get(name)


def row_shown(name):
    """The chip on the feature's row: on while it's new, and while you're still in the place you opened it in."""
    return is_new(name) or name in _leaving


def page_new(key):
    """Does this page's rail icon carry a NEW chip? (A feature that lives there is still new.)"""
    return any(page == key and is_new(n) for n, (page, _tab) in FEATURES.items())


def page_tip(key):
    """What's new on this page, for the rail's tip: "NEW: Look key, Drawer" (or "")."""
    names = [n for n, (page, _tab) in FEATURES.items() if page == key and is_new(n)]
    return f"{WORD}: " + ", ".join(names) if names else ""


def listen(fn):
    _listeners.append(fn)


def _changed():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            buglog.caught()


def _mark(name):
    if not is_new(name):
        return False
    _seen()[name] = SINCE
    save_json("settings.json", SETTINGS)
    return True


def used(name):
    """The feature was used (a Look key press, the Drawer shown, the trial's legend shown): its chips go for good."""
    _leaving.discard(name)
    changed = _mark(name)
    _paint(name)
    if changed:
        _changed()


def at(page, tab):
    """You are on this page and tab now (the shell calls this on every page or tab change). A feature living here
    counts as opened: its rail chip goes now, its row's chip once you leave."""
    changed = False
    for name, (p, t) in FEATURES.items():
        here = p == page and (t is None or t == tab)
        if here:
            if _mark(name):
                _leaving.add(name)
                changed = True
        elif name in _leaving:
            _leaving.discard(name)
            _paint(name)
    if changed:
        _changed()


def chip(parent, name, bg=None):
    """The NEW chip for a feature's row (a tk.Label; pack / grid it as you like). Already seen: an empty, unmapped
    label that stays that way - pack it anyway."""
    from .style import C, Tooltip
    lab = tk.Label(parent, text=WORD, bg=C["accent"], fg=C["bg"], font=("Segoe UI", 9, "bold"), padx=4, pady=0)
    Tooltip(lab, TIP)
    lab._new_of = name
    _rows.setdefault(name, []).append(lab)
    lab.bind("<Destroy>", lambda e, w=lab: _forget(name, w), add="+")
    if not row_shown(name):
        lab.after_idle(lambda: _hide(lab))
    return lab


def _forget(name, w):
    try:
        _rows.get(name, []).remove(w)
    except ValueError:
        pass


def _hide(w):
    """The chip goes: no word, no tip, and it takes no room. (A row that wraps - style.flowify - places its widgets
    itself and would put an unmapped one back: there the chip stays, empty, in the row's own color.)"""
    try:
        if not w.winfo_exists():
            return
        tip = getattr(w, "_tip", None)
        if tip is not None:
            tip.text = ""
        try:
            bg = w.master.cget("bg")
        except tk.TclError:
            bg = w.cget("bg")
        w.configure(text="", padx=0, pady=0, bd=0, width=0, bg=bg, font=("Segoe UI", 1))   # token-ok (no room)
        if w.winfo_manager() == "grid":
            w.grid_remove()
        elif w.winfo_manager() == "pack":
            w.pack_forget()
    except tk.TclError:
        pass


def _paint(name):
    if row_shown(name):
        return
    for w in list(_rows.get(name, [])):
        _hide(w)


def draw(cv, x, y, color, ink, anchor="e", size=7):
    """The NEW chip drawn on a canvas (the rail): a small filled pill with the word in it. -> its right / left edge."""
    t = cv.create_text(x, y, text=WORD, anchor=anchor, font=("Segoe UI", size, "bold"), fill=ink, tags=("newchip",))
    bb = cv.bbox(t)
    if bb:
        r = cv.create_rectangle(bb[0] - 3, bb[1], bb[2] + 3, bb[3], fill=color, outline=color, tags=("newchip",))
        cv.tag_lower(r, t)
        return bb[0] - 3 if anchor == "e" else bb[2] + 3
    return x
