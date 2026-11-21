"""A drop-down list with a picture beside each name (Top Up Reminders' Item).

ttk's Combobox can't show pictures, so this IS a ttk Combobox (one field, the arrow inside it, the look of every other
Combobox in every theme) with the picked item's picture laid over its left padding, and a list of our own that opens under
it; a click anywhere on the field opens it. The list
is one canvas that draws only the rows in view (hundreds of items cost nothing). Typing narrows the list (names that
start with what you typed come first), Up / Down move, Enter picks, Esc closes. The pictures come from icon(name) ->
PhotoImage or None - the app's own, nothing is fetched."""
import tkinter as tk
from tkinter import ttk

from .style import C

ROW = 28                    # one row's height
ICON_PX = 24                # the picture's room
PAD_LEFT = 36               # the field's left padding: the picture sits in it
SHOW = 8                    # rows in view before it scrolls


class ImagePick(tk.Frame):
    def __init__(self, master, names, icon, textvariable=None, width=26, on_pick=None, bg=None):
        bg = bg or C["panel2"]
        super().__init__(master, bg=bg)
        self.names, self.icon, self.on_pick = list(names), icon, on_pick
        self.var = textvariable or tk.StringVar()
        self.shown, self.sel, self.top, self.pop = [], 0, 0, None
        self._imgs = {}
        ttk.Style(self).configure("Pick.TCombobox", padding=(PAD_LEFT, 4, 4, 4))     # room for the picture
        self.entry = ttk.Combobox(self, textvariable=self.var, width=width, style="Pick.TCombobox")
        self.entry.pack(fill="x", expand=True)
        self.pic = tk.Label(self.entry, bd=0, highlightthickness=0)
        self.pic.place(x=6, rely=0.5, anchor="w")
        self.pic.bind("<Button-1>", self._click_field)
        self.arrow = self.entry                  # (the arrow is the field's own: no separate button)
        self.entry.bind("<KeyRelease>", self._typed)
        self.entry.bind("<Down>", self._down)
        self.entry.bind("<Up>", self._up)
        self.entry.bind("<Return>", self._enter)
        self.entry.bind("<Escape>", self._esc)
        self.entry.bind("<Button-1>", self._click_field)
        self.var.trace_add("write", lambda *_a: self._paint_pic())
        self.bind("<Destroy>", lambda _e: self.close(), add="+")
        self._paint_pic()

    # ------------------------------------------------------------ the field
    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def exact(self):
        """The list's own spelling of what is typed, or None (not an item on the list)."""
        t = self.var.get().strip().lower()
        return next((n for n in self.names if n.lower() == t), None)

    def _picture(self, name):
        img = self._imgs.get(name)
        if img is None:
            img = self.icon(name)
            if img is not None:                  # (no picture yet: asked again next time, it may have arrived)
                self._imgs[name] = img
        return img

    def _paint_pic(self):
        name = self.exact()
        img = self._picture(name) if name else None
        try:
            bg = ttk.Style(self).lookup("TCombobox", "fieldbackground") or C["odd"]
            self.pic.config(image=img or "", bg=bg, width=ICON_PX if img else 0)
            self.pic.image = img
            if img:
                self.pic.place(x=6, rely=0.5, anchor="w")
            else:
                self.pic.place_forget()
        except tk.TclError:
            pass

    def refresh_pictures(self):
        """Pictures arrived later (poe.ninja's, once cached): draw the field and the open list again."""
        self._imgs.clear()
        self._paint_pic()
        if self.pop is not None:
            self._draw()

    def _click_field(self, _e):
        """A click anywhere on the field (text, picture or arrow) opens the list, or closes it."""
        self.entry.focus_set()
        if self.pop is not None:
            self.close()
        else:
            self.open(everything=True)
            self.entry.selection_range(0, "end")
        return "break"

    # ------------------------------------------------------------ the list
    def _match(self):
        t = self.var.get().strip().lower()
        if not t:
            return list(self.names)
        first = [n for n in self.names if n.lower().startswith(t)]
        rest = [n for n in self.names if t in n.lower() and n not in first]
        return first + rest

    def toggle(self):
        self.close() if self.pop is not None else self.open(everything=True)

    def open(self, everything=False):
        self.shown = list(self.names) if everything else self._match()
        if self.pop is None:
            self.pop = tk.Toplevel(self, bg=C["accent"])
            self.pop.withdraw()
            self.pop.overrideredirect(True)
            body = tk.Frame(self.pop, bg=C["panel"])
            body.pack(fill="both", expand=True, padx=1, pady=1)
            self.cv = tk.Canvas(body, bg=C["panel"], highlightthickness=0, width=300, height=ROW * SHOW)
            self.sb = ttk.Scrollbar(body, orient="vertical", command=self._scroll_to)
            self.sb.pack(side="right", fill="y")
            self.cv.pack(side="left", fill="both", expand=True)
            self.cv.bind("<Button-1>", self._click)
            self.cv.bind("<Motion>", self._hover)
            self.cv.bind("<MouseWheel>", lambda e: self._wheel(-1 if e.delta > 0 else 1))
            self.cv.bind("<Button-4>", lambda _e: self._wheel(-1))
            self.cv.bind("<Button-5>", lambda _e: self._wheel(1))
            self._away = self.winfo_toplevel().bind("<Button-1>", self._outside, add="+")
        self.sel = max(0, next((i for i, n in enumerate(self.shown) if n == self.exact()), 0))
        self.top = max(0, min(self.sel, len(self.shown) - SHOW))
        self._place()
        self.pop.deiconify()
        self.pop.lift()
        self._draw()

    def _place(self):
        self.update_idletasks()
        w = max(self.winfo_width(), 240)
        rows = max(1, min(SHOW, len(self.shown)))
        self.cv.config(width=w - 18, height=ROW * rows)
        self.pop.geometry(f"{w}x{ROW * rows + 2}+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")

    def close(self):
        pop, self.pop = self.pop, None
        if pop is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._away)
            except (tk.TclError, AttributeError):
                pass
            try:
                pop.destroy()
            except tk.TclError:
                pass

    def _outside(self, e):
        if self.pop is None:
            return
        w = e.widget
        while w is not None:
            if w is self or w is self.pop:
                return
            w = getattr(w, "master", None)
        self.close()

    def _draw(self):
        if self.pop is None:
            return
        cv = self.cv
        cv.delete("all")
        w = cv.winfo_width() if cv.winfo_width() > 1 else 280
        if not self.shown:
            cv.create_text(8, ROW // 2, anchor="w", fill=C["muted"], font=("Segoe UI", 10), text="No item by that name")
        for i in range(self.top, min(len(self.shown), self.top + SHOW)):
            y = (i - self.top) * ROW
            name = self.shown[i]
            on = i == self.sel
            cv.create_rectangle(0, y, w, y + ROW, fill=C["sel"] if on else C["panel"], outline="")
            img = self._picture(name)
            if img is not None:
                cv.create_image(4 + ICON_PX // 2, y + ROW // 2, image=img)
            cv.create_text(8 + ICON_PX + 4, y + ROW // 2, anchor="w", text=("▸ " if on else "") + name,
                           fill=C["text"], font=("Segoe UI", 10, "bold" if on else "normal"))
        n = max(1, len(self.shown))
        self.sb.set(self.top / n, min(1.0, (self.top + SHOW) / n))

    def _scroll_to(self, *a):
        n = len(self.shown)
        if a and a[0] == "moveto":
            self.top = max(0, min(n - SHOW, int(float(a[1]) * n)))
        elif a and a[0] == "scroll":
            self.top = max(0, min(n - SHOW, self.top + int(a[1]) * (SHOW if a[2] == "pages" else 1)))
        self._draw()

    def _wheel(self, d):
        self.top = max(0, min(max(0, len(self.shown) - SHOW), self.top + d * 3))
        self._draw()

    def _row_at(self, y):
        i = self.top + int(y // ROW)
        return i if 0 <= i < len(self.shown) else None

    def _hover(self, e):
        i = self._row_at(e.y)
        if i is not None and i != self.sel:
            self.sel = i
            self._draw()

    def _click(self, e):
        i = self._row_at(e.y)
        if i is not None:
            self._pick(self.shown[i])

    # ------------------------------------------------------------ keys
    def _typed(self, e):
        if e.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right", "Shift_L", "Shift_R", "Control_L",
                        "Control_R", "Alt_L", "Alt_R"):
            return
        self.open()                             # (the list narrows to what is typed)

    def _step(self, d):
        if self.pop is None:
            self.open(everything=not self.var.get().strip())
            return "break"
        if self.shown:
            self.sel = max(0, min(len(self.shown) - 1, self.sel + d))
            self.top = min(max(0, self.sel - SHOW + 1), max(self.top, 0)) if self.sel < self.top else \
                max(self.top, self.sel - SHOW + 1)
            self._draw()
        return "break"

    def _down(self, _e):
        return self._step(1)

    def _up(self, _e):
        return self._step(-1)

    def _enter(self, _e):
        if self.pop is not None and self.shown:
            self._pick(self.shown[self.sel])
            return "break"
        return None                              # (closed: Enter goes on to the form - Add)

    def _esc(self, _e):
        if self.pop is not None:
            self.close()
            return "break"
        return None

    def _pick(self, name):
        self.close()
        self.var.set(name)
        self.entry.icursor("end")
        self.entry.focus_set()
        if self.on_pick:
            self.on_pick(name)
