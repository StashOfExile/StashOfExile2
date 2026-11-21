"""The read mark (GGG policy, Nov 2026: "You may only read this information as long as the user is aware of what you
are doing with that data").

Each time the app reads your screen or your clipboard - once, on a key you pressed - it says so over the game.
Round 18 (feedback: a small tooltip with too much text): the same alert card every helper uses (alertcard), with
the eye (👁) and a few words - "Reading the screen", "Reading the item"; a press whose picture no helper could use
says "Read the screen · nothing here" (it was still read, so it still shows); a copy that isn't an item says "Not an item"
and an empty copy shows nothing (the reason is on Price Checks' status line). A click closes it; it goes by itself
in two seconds; it is left out of screen captures (a quick second press never reads it). The status line and the
app's log keep the whole line ("👁 Screen read once: Ritual, Temple"), never by color alone."""
import sys
import time
import tkinter as tk

from . import buglog

SECS = 2.0                         # how long the card stays up
SECS_MISSED = 3.0                  # a copy that didn't land says so a little longer
EYE = "👁"
SHOWN = []                         # (tests) every mark's text, in order
READING = "Reading the screen"
READ_NOTHING = "Read the screen · nothing here"   # (owner: a press on the closed trial map - read, nothing found)


def mark_text(source, what):
    """("screen" | "clipboard", [purposes]) -> the status line's (and the log's) words."""
    from .screenread import NOTHING
    parts = [str(p) for p in (what or []) if p]
    if source == "clipboard":
        p = ", ".join(parts) or "the app"
        if p.startswith("nothing - "):
            return f"{EYE} Clipboard read once: {p[len('nothing - '):]}"
        return f"{EYE} Clipboard read once: {p}"
    nothing = NOTHING in parts
    parts = [p for p in parts if p != NOTHING]
    return f"{EYE} Screen read once: {', '.join(parts) or 'the helpers'}" + (f" - {NOTHING}" if nothing else "")


def card_text(source, what):
    """The card's words -> its title, or None (an empty copy: nothing to show over the game)."""
    from . import gamedata as GD
    parts = [str(p) for p in (what or []) if p]
    if source != "clipboard":
        from .screenread import NOTHING
        return READ_NOTHING if NOTHING in parts else READING
    if any(p.lower().startswith("chat command") for p in parts):
        return None                                   # (owner: F1 /hideout showed the "Reading the item" card - a chat
                                                      # keeps your clipboard to put it back; the log line stays)
    missed = next((p[len("nothing - "):] for p in parts if p.startswith("nothing - ")), None)
    if missed is None:
        return "Reading the item"
    if missed in (GD.COPY_MISSED, ""):
        return None                                   # (nothing was copied: nothing to say over the game)
    if missed in (GD.COPY_NOT_ITEM, GD.COPY_NOT_ENGLISH):
        return "Not an item"
    return "Can't price this item"                    # (why: Price Checks' status line)


class ReadMark:
    """The read's row on the alert card; a new read replaces it."""

    def __init__(self, root):
        self.root, self.win, self.job = root, None, None

    def hide(self):
        w, self.win = self.win, None
        if w is not None:
            try:
                w.destroy()                            # (quietly: only this row)
            except tk.TclError:
                pass

    def show(self, text, rect=None, secs=SECS):
        """text (the card's title) over the game window rect (left, top, width, height) - without one, nothing over
        the game (the status line still says it). -> the card's row or None."""
        SHOWN.append(text)
        self.hide()
        if not rect or not text:
            return None
        try:
            from . import alertcard
            from .style import C
            row = alertcard.show(self.root, text, "", color=C.get("steel") or C["accent"], mark=EYE, secs=secs,
                                 game=rect, tag="Read Key", rank=9)
            self.win = row
            self._quiet(row.card.win)
            return row
        except Exception:
            buglog.caught()
            return None

    @staticmethod
    def _quiet(w):
        """Never in a screen capture (Windows): a quick second press never reads the card."""
        if sys.platform != "win32" or w is None:
            return
        try:
            from .remnant_page import no_capture
            no_capture(w)
        except Exception:
            buglog.caught()


class ReadMarkPage:
    """Mixed into App: the read mark for every screen and clipboard read (screenread.SAID / clipread.SAID put
    ("read_mark", ...) on the window thread's queue)."""

    def ev_read_mark(self, source, key, what):
        text = mark_text(source, what)
        missed = any(str(p).startswith("nothing - ") for p in (what or []))
        self.status_text, self.status_until = f"{text}  ({key})", time.time() + (6 if missed else 3)
        rect = None
        try:
            from .alerts_page import game_rect
            from .overlay import game_open
            rect = game_rect() if game_open() else None
        except Exception:
            buglog.caught()
        mark = getattr(self, "read_mark", None)
        if mark is None:
            mark = self.read_mark = ReadMark(self.root)
        return mark.show(card_text(source, what), rect, SECS_MISSED if missed else SECS)

    # Round 18 (feedback): Esc in the game clears what the Read Key drew over it. The game still gets Esc.
    LOOK_DRAWN = ("remnant_hide", "favours_hide", "ru_hide", "ws_hide", "temple_pad_close", "sek_hide")

    def ev_look_clear(self):
        """Esc while the game is in front: every tag, card and mark the Read Key put over the game goes - Expedition
        prices and Runeshapes, Favours, Island Rumors, Desecration tiers, the Vaal Lens card and its marks, the
        Trial of the Sekhemas legend and the read mark."""
        for fn in self.LOOK_DRAWN:
            try:
                getattr(self, fn)()
            except AttributeError:
                pass
            except Exception:
                buglog.caught()
        mk = getattr(self, "tm_marks_win", None)
        try:
            if mk is not None:
                mk.hide()
        except Exception:
            buglog.caught()
        mark = getattr(self, "read_mark", None)
        if mark is not None:
            mark.hide()
