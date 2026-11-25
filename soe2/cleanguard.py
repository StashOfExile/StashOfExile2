"""3.3.0 owner: every box that takes typed text refuses the board's filtered words, at the box. One guard for the
whole app, wired once in listkit.install, so a new box is covered without anyone remembering it.

How it works: after each key and each paste the box is checked with cleantext. A box that now holds a refused
word goes back to what it held before, and a small line under it says why. The word still being typed is judged
when a space follows it or the box is left, so "assassin" can be typed.

Left alone, by the owner's word: Notes. Also boxes that hold the game's own text or a search, marked with
free(widget), and anything read-only."""
import tkinter as tk

from . import cleantext as CT

CLASSES = ("Entry", "TEntry", "TCombobox", "Text")
_last = {}                      # widget path -> the last text it held that was fine
_paused = [0]                   # > 0 while a dialog for free text is open
_tip = [None]


def free(widget):
    """This box takes any text: a note, a search, the game's own text. -> the widget."""
    try:
        widget._soe2_free_text = True
    except (AttributeError, tk.TclError):
        pass
    return widget


class paused:
    """with cleanguard.paused(): a dialog that takes any text, like a note's."""
    def __enter__(self):
        _paused[0] += 1

    def __exit__(self, *a):
        _paused[0] = max(0, _paused[0] - 1)


def _is_free(w):
    if _paused[0]:
        return True
    while w is not None:                               # a box inside a free frame is free too
        if getattr(w, "_soe2_free_text", False):
            return True
        w = getattr(w, "master", None)
    return False


def _read(w):
    if isinstance(w, tk.Text):
        return w.get("1.0", "end-1c"), len(w.get("1.0", "insert"))
    return w.get(), int(w.index("insert"))


def _write(w, text):
    if isinstance(w, tk.Text):
        w.delete("1.0", "end")
        w.insert("1.0", text)
    else:
        w.delete(0, "end")
        w.insert(0, text)


def _editable(w):
    try:
        state = str(w.cget("state"))
    except tk.TclError:
        return False
    return state not in ("disabled", "readonly")


NEAR = 160


def _near(text, cur):
    """The stretch of text around the cursor, cut at spaces."""
    a, b = max(0, cur - NEAR), min(len(text), cur + 40)
    while a > 0 and not text[a - 1].isspace():
        a -= 1
    while b < len(text) and not text[b].isspace():
        b += 1
    return a, b


def check(w, final=False):
    """Check one box now. final: the box is being left, so the word at the cursor is judged too.
    -> the refused word, or None."""
    try:
        if not isinstance(w, tk.Widget) or not _editable(w) or _is_free(w):
            return None
        text, cur = _read(w)
    except (tk.TclError, AttributeError, ValueError):
        return None
    key = str(w)
    if final:
        bad = CT.problem(text)
    else:                                              # while typing: only the words around the cursor, so a
        a, b = _near(text, cur)                        # long text stays quick; leaving the box checks all of it
        bad = CT.while_typing(text[a:b], cur - a)
    if not bad:
        if final or len(text) <= NEAR * 2 or not CT.problem(text[max(0, cur - NEAR * 2):cur]):
            _last[key] = text
        return None
    good = _last.get(key, "")
    if CT.problem(good):
        good = ""
    try:
        _write(w, good)
    except tk.TclError:
        return bad
    say(w)
    return bad


def say(w, text=None):
    """A small line under the box for a moment: a mark and words, never color alone."""
    hide()
    try:
        tip = tk.Toplevel(w)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(tip, text="✕  " + (text or CT.MSG), bg="#3a1418", fg="#ffd9d9", padx=8, pady=4,
                 font=("Segoe UI", 9, "bold"), highlightthickness=1, highlightbackground="#d9534f").pack()
        tip.wm_geometry("+%d+%d" % (w.winfo_rootx(), w.winfo_rooty() + w.winfo_height() + 2))
        _tip[0] = tip
        tip.after(2600, lambda t=tip: hide(t))
    except tk.TclError:
        _tip[0] = None


def hide(only=None):
    tip = _tip[0]
    if tip is None or (only is not None and only is not tip):
        return
    _tip[0] = None
    try:
        tip.destroy()
    except tk.TclError:
        pass


def _start(w):
    try:
        if isinstance(w, tk.Widget) and _editable(w) and not _is_free(w):
            text = _read(w)[0]
            if not CT.problem(text):
                _last[str(w)] = text
    except (tk.TclError, AttributeError, ValueError):
        pass


def clean_answer(ask):
    """Wraps tkinter.simpledialog.askstring: an answer with a refused word is asked for again. The box in the
    dialog is guarded as it is typed; this catches an OK pressed with the mouse before the last word was judged."""
    def asking(title, prompt, **kw):
        while True:
            got = ask(title, prompt, **kw)
            if got is None or _paused[0] or not CT.problem(got):
                return got
            kw["initialvalue"] = ""
            prompt = prompt.split("\n\n✕ ")[0] + "\n\n✕ " + CT.MSG
    asking._soe2_clean = True
    return asking


def install(root):
    """Once at start-up: every Entry, Combobox and Text box of the app."""
    for cls in CLASSES:
        root.bind_class(cls, "<FocusIn>", lambda e: _start(e.widget), add="+")
        root.bind_class(cls, "<KeyRelease>", lambda e: check(e.widget), add="+")
        root.bind_class(cls, "<<Paste>>", lambda e: e.widget.after_idle(lambda w=e.widget: check(w, final=True)),
                        add="+")
        root.bind_class(cls, "<FocusOut>", lambda e: check(e.widget, final=True), add="+")
        root.bind_class(cls, "<Return>", lambda e: check(e.widget, final=True), add="+")
    from tkinter import simpledialog
    if not getattr(simpledialog.askstring, "_soe2_clean", False):
        simpledialog.askstring = clean_answer(simpledialog.askstring)
