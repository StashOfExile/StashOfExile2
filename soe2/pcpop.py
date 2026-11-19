"""2.113.0: the Price check overlay - the price check in a card over the game.

Where the price shows › "Price check overlay" (Settings › Price checking, Price Checks' top row, the card's gear - one
setting, pc_popup): your price check key copies the hovered item (one press = one copy, as always) and, instead of
showing the app (drawer build: "In the app" opens the Drawer quietly), a card opens over the game at a spot you
choose - drag it by its title, resize it from any edge; both are remembered. It takes the overlay's Style.

The card: the item (name in its rarity color; rarity, class, base, item level, quality, corrupted), the price and
how sure it is, the mods searched with their ticks (a tick changes the search; Search again runs it), and the cheapest
listings - each a one-line summary that opens to the whole item (implicits, every mod, corrupted). Search again,
Trade site and Open in app sit at the bottom.

Typing: click into a Min / Max box and the card takes the keyboard (Enter searches again); click back into the
game and it has the keyboard again. 3.0.1 (the Min / Max boxes did not take typing): every box takes it - the
item's own boxes (item level, quality, sockets) never asked for the keyboard, only the mods' did; on Windows the card's
window is made one that can have it (overlaywin.take_keyboard); a gray box ticks its row and puts the cursor in it; the
box keeps the keyboard when the card is drawn again; the card waits only while you type (a key since the last search
- after Enter it shows what was found); closing the card hands the keyboard back to the game.

Close key (2.121.1, feedback): Esc by default, as PoE Overlay closes its dialogs - only while the card is open and the
game (or the card) is in front, and that press is used up (the game's menu doesn't open). Set it on Settings › Keybinds or
with the card's ⚙ (Card settings: the close key, where the price shows, All price check settings…).

Privacy: other players' seller names show as on the app's card (public on the trade site); your own account name
is never shown here.
GGG ToS: the key presses the game's copy once (overlay.py, as before); the card only shows what the app found.
Works the same on Windows and Linux / Hyprland (an OverlayWindow: topmost, follows the game)."""
import tkinter as tk
from tkinter import ttk

from . import gearicon
from .config import SETTINGS, save_json
from .style import C, MOD_COL, trade_icon

def ilvl_matters(it):
    """Round 18: does a listing's item level matter for this item (gear, jewels, bases)? Not for waystones (their
    tier says it), tablets, gems, currency or uniques."""
    it = it or {}
    return not (it.get("waystone") or it.get("rarity") in ("Currency", "Gem", "Unique") or it.get("class") == "Tablet"
                or (it.get("search") or {}).get("gem"))


def socket_words(it):
    """2.125.5: an item's socket letters in words -> " (2 augment, 1 jewel)" or ""."""
    t = it.get("socket_types") or ""
    parts = [f"{n} {w}" for n, w in ((t.count("S"), "augment"), (t.count("J"), "jewel")) if n]
    return f" ({', '.join(parts)})" if parts else ""


KIND_COL = {"Implicit": "implicit", "Rune": "rune", "Enchant": "enchant", "Prefix": "explicit", "Suffix": "explicit",
            "Total": "pseudo"}
W0, H0 = 430, 600                 # the first size (then yours)


def pop_on():
    return bool(SETTINGS.get("pc_popup", False))


def ink(c, bg):
    """A game color (rarity, mod kind) made readable on this card: on a light card the light
    blues / greens / yellows are darkened, same hue, until they reach 4.5 : 1 against it. Dark styles: as is."""
    from .style import contrast, mix
    try:
        if contrast(c, bg) >= 4.5:
            return c
        out = c
        for t in (0.15, 0.3, 0.45, 0.6, 0.75):
            out = mix(c, "#000000", t)
            if contrast(out, bg) >= 4.5:
                return out
        return out
    except Exception:
        return c


class PricePopup:
    """Mixin on the App."""

    # ---------------------------------------------------------------- the window
    def pcpop_geo(self):
        g = SETTINGS.get("pc_pop_geo")
        if isinstance(g, (list, tuple)) and len(g) == 4:
            return tuple(int(v) for v in g)
        try:
            from .alerts_page import game_rect
            r = game_rect()
        except Exception:
            r = None
        if not r:
            r = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        gx, gy, gw, gh = r
        return gx + gw - W0 - 48, gy + int(gh * 0.12), W0, H0       # right of the middle, clear of the bar

    def pcpop_close(self):
        self.pcpop_settings_close()
        self._pcpop_cancel()
        w, self.pp_win = getattr(self, "pp_win", None), None
        self.pp_rid, self.pp_up = None, False
        back, self._pp_back = getattr(self, "_pp_back", None), None
        self._pp_typed, self._pp_refocus = False, None
        if w is not None:
            try:
                if back:                                  # 3.0.1: you typed in a box - the game gets the keyboard back
                    w.give_keyboard_back(back)
                w.destroy()
            except tk.TclError:
                pass

    def pcpop_show(self, rec):
        """Open (or refill) the card for this item."""
        if rec is None:
            return None
        if getattr(self, "pp_rid", None) != rec["id"]:
            self.pp_open = set()                          # (which listings are opened - a new item starts closed)
            self._pp_typed, self._pp_refocus = False, False      # (3.0.1: no box of the item before keeps the keyboard)
        self.pp_rid = rec["id"]
        self._pcpop_cancel()                              # (a refresh asked for the item before: not over this one)
        w = self._pcpop_window()
        self.pcpop_fill(rec)
        return self._pcpop_up(w)

    def _pcpop_up(self, w):
        self.pp_up = True                                 # (read by the keyboard watcher: the close key works now)
        from .overlaywin import foreign_foreground
        game = foreign_foreground()                       # 3.0.1: the game in front as the card opens - it gets the
        if game:                                          # keyboard back when the card closes, if you typed in it
            self._pp_game = game
        w.show()
        try:
            w.lift()
        except tk.TclError:
            pass
        return w

    def _pcpop_window(self):
        """The card's window - the one that's open, or a new one."""
        from .overlaywin import OverlayWindow, pal
        w = getattr(self, "pp_win", None)
        if w is not None:
            try:
                if not w.winfo_exists():
                    w = None
            except tk.TclError:
                w = None
        if w is None:
            P = pal()

            def moved(x, y, ww, hh):
                SETTINGS["pc_pop_geo"] = [int(x), int(y), int(ww), int(hh)]
                save_json("settings.json", SETTINGS)
            w = OverlayWindow(self.root, "Price check", "⚖", self.pcpop_geo(), opacity=255, locked=False,
                              min_size=(320, 260), on_close=self.pcpop_close, on_moved=moved, follow_game=True,
                              no_activate=False, resizable=True, lockable=False, palette=P,   # (Min / Max: typing)
                              extra=[(gearicon.GEAR, self.pcpop_settings_toggle, "Card settings")])
            self.pp_win, self.pp_P = w, P
            w.bind("<Escape>", lambda _e: self._pcpop_esc(), add="+")    # (the card has the keyboard: Min / Max)
            self._pcpop_frame(w, P)
        return w

    # ---------------------------------------------------------------- 2.127.0: currency and lineage gems
    def pcpop_rates(self, name, qty, each, src):
        """2.127.0 (feedback: Ctrl+D on currency items should show the current common exchange rates): a currency
        (or a lineage gem, or anything poe.ninja's exchange lists) in the card - what one is worth in the
        currencies people trade in, what a Divine / Exalted Orb buys of it, and the stack's worth."""
        self.pp_rid, self.pp_open = None, set()
        self._pcpop_cancel()                              # (a refresh asked for an item: not over the rates)
        w = self._pcpop_window()
        self.pcpop_rates_fill(name, qty, each, src)
        return self._pcpop_up(w)

    def pcpop_rates_fill(self, name, qty, each, src):
        from .pricefmt import fmt_div
        from .rates import RATES
        P, inner, foot = self.pp_P, self.pp_inner, self.pp_foot
        for c in list(inner.winfo_children()) + list(foot.winfo_children()):
            c.destroy()
        self.pp_wraps, self.pp_boxes, self._pp_refocus = [], {}, None
        body, head = P.get("body") or P["font"], P.get("hfont") or P["font"]

        def lab(parent, text, fg=None, size=10, bold=False, font=None, **pk):
            l_ = tk.Label(parent, text=text, bg=parent["bg"], fg=fg or P["text"], anchor="w", justify="left",
                          font=(font or body, size, "bold") if bold else (font or body, size))
            l_.pack(fill="x", **pk)
            self.pp_wraps.append(l_)
            return l_
        lab(inner, name + (f"  ×{qty:,}" if qty > 1 else ""), fg=P["big"], size=13, bold=True, font=head,
            pady=(8, 0), padx=16)
        lab(inner, "Going rate" + (f" · {src}" if src else ""), fg=P["muted"], size=9, padx=16)
        box = tk.Frame(inner, bg=P.get("field", P["bg"]), highlightthickness=1, highlightbackground=P["line"])
        box.pack(fill="x", padx=16, pady=(8, 0))
        if each is None:
            lab(box, "Not found on poe.ninja.", padx=8, pady=8)
            return
        lab(box, "1 ≈ " + fmt_div(each), fg=P["big"], size=16, bold=True, font=head, padx=8, pady=(8, 0))
        worth, buys = RATES.common(each, RATES.key(name.replace(" ", "-")))
        if worth:
            lab(box, "1 = " + "  ·  ".join(worth), size=10, padx=8, pady=(4, 0))
        if buys:                                           # what one of the dear ones buys of this
            lab(box, "  ·  ".join(buys), fg=P["muted"], size=9, padx=8, pady=(4, 0))
        if qty > 1:
            lab(box, f"Your {qty:,}: ≈ {fmt_div(each * qty)}", bold=True, padx=8, pady=(8, 0))
        tk.Frame(box, bg=box["bg"], height=8).pack(fill="x")
        self._pcpop_btn("Open Exchange Rates", self._pcpop_rates_page).pack(side="right")

    def _pcpop_rates_page(self):
        try:
            self.app_show("rates", focus=True, why="pcpop")      # (a click on the card: the app may take the keyboard)
        except Exception:
            self.log_error("opening Exchange Rates")

    # ---------------------------------------------------------------- the close key (2.121.1)
    def pc_close_hotkey(self, vk, ctrl, alt, shift):
        """Keyboard watcher thread: your close key while the card is open and the game is in front -> close it (the
        press is used up). Anywhere else the key does its usual job."""
        if not getattr(self, "pp_up", False):
            return False
        from .overlay import parse_key, game_active, POE_TITLE
        k = parse_key(SETTINGS.get("pc_close_key", "Esc") or "")
        if not k or k != (vk, ctrl, alt, shift):
            return False
        if not game_active((getattr(self, "overlay", None) and self.overlay.cfg.get("poe_title")) or POE_TITLE):
            return False
        self.ui_q.put(("pcclose",))
        return True

    def ev_pcclose(self):
        if getattr(self, "pcs_win", None) is not None:   # Card settings open: that goes first
            return self.pcpop_settings_close()
        self.pcpop_close()

    def _pcpop_esc(self):
        """Esc while the card itself has the keyboard (typing a Min / Max) - when Esc is your close key."""
        from .overlay import parse_key
        if parse_key(SETTINGS.get("pc_close_key", "Esc") or "") == (0x1B, False, False, False):
            self.ev_pcclose()

    # ---------------------------------------------------------------- ⚙ Card settings (2.121.1)
    def pcpop_settings_toggle(self):
        if getattr(self, "pcs_win", None) is not None:
            return self.pcpop_settings_close()
        self.pcpop_settings_show()

    def pcpop_settings_close(self, _e=None):
        w, self.pcs_win = getattr(self, "pcs_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def pcpop_settings_show(self):
        """A small box under the ⚙, over the game: where the price shows (In the app | Price check overlay - the same setting as
        Settings and Price Checks), the close key (2.125.5: shown here, set on Keybinds only), All price check settings….
        2.125.5 (feedback: everything over the game follows the overlay's style): in the overlay's colors and font."""
        from .style import CAPTURING, Tooltip
        from .overlay import key_label
        self.pcpop_settings_close()
        card = getattr(self, "pp_win", None)
        if card is None:
            return
        Q = self.ov_quick_style()
        P1, P2, F = Q["bg"], Q["band"], Q["font"]
        w = tk.Toplevel(self.root, bg=Q["line"])
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.pcs_win = w
        box = tk.Frame(w, bg=P1)
        box.pack(padx=1, pady=1)
        head = tk.Frame(box, bg=P2, padx=12, pady=8)
        head.pack(fill="x")
        tk.Label(head, text="Price check overlay", bg=P2, fg=Q["text"], font=(Q["hfont"], 12, "bold")).pack(side="left")
        x_ = tk.Label(head, text="✕", bg=P2, fg=Q["muted"], font=(F, 11), cursor="hand2", padx=4)
        x_.pack(side="right")
        x_.bind("<Button-1>", lambda _e: self.pcpop_settings_close())
        Tooltip(x_, "Close")
        body = tk.Frame(box, bg=P1, padx=12, pady=8)
        body.pack(fill="x")
        tk.Label(body, text="Price shows", bg=P1, fg=Q["text"], font=(F, 10), anchor="w").pack(fill="x")
        chips = tk.Frame(body, bg=P1)
        chips.pack(fill="x", pady=(4, 8))
        cur = "Price check overlay" if self.pc_show_get() == "both" else "In the app"
        self.pcs_chips = {}
        # 2.125.6: over the game the app is named. Drawer build: the same two words as everywhere (one place each)
        words = {"In the app": "In the app", "Price check overlay": "Price check overlay"}
        for name in self.PC_WHERE:
            on = name == cur
            c = tk.Label(chips, text=("✓ " if on else "") + words[name], bg=Q["field"] if on else P1,
                         fg=Q["text"] if on else Q["muted"], font=(F, 10, "bold" if on else "normal"), padx=8, pady=4,
                         cursor="hand2", highlightthickness=1, highlightbackground=Q["accent"] if on else Q["line"])
            c.pack(side="left", padx=(0, 8))
            c.bind("<Button-1>", lambda _e, n=name: (self._pc_where_pick(n), self.pcpop_settings_show()))
            self.pcs_chips[name] = c
        k = SETTINGS.get("pc_close_key", "Esc")
        r = tk.Frame(body, bg=P1)
        r.pack(fill="x")
        tk.Label(r, text=f"Close key: {key_label(k)}" if k else "Close key: none", bg=P1, fg=Q["text"],
                 font=(F, 10)).pack(side="left")
        go = tk.Label(r, text="Change in Keybinds ›", bg=P1, fg=Q["accent"], font=(F, 9, "underline"), cursor="hand2")
        go.pack(side="right")
        go.bind("<Button-1>", lambda _e: (self.pcpop_settings_close(), self._pcs_keys()))
        foot = tk.Frame(box, bg=P1, padx=12, pady=8)
        foot.pack(fill="x")
        allb = tk.Label(foot, text="All price check settings…", bg=Q["field"], fg=Q["text"], font=(F, 10), pady=4,
                        cursor="hand2", highlightthickness=1, highlightbackground=Q["line"])
        allb.pack(fill="x")
        allb.bind("<Button-1>", lambda _e: self._pcs_all())
        allb.bind("<Enter>", lambda _e: allb.config(highlightbackground=Q["accent"]))
        allb.bind("<Leave>", lambda _e: allb.config(highlightbackground=Q["line"]))
        w.bind("<Escape>", lambda e: None if CAPTURING[0] is not None else self.pcpop_settings_close())
        w.update_idletasks()
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        try:
            cx, cy, cw = card.winfo_rootx(), card.winfo_rooty(), card.winfo_width()
        except tk.TclError:
            cx, cy, cw = self.root.winfo_pointerx(), self.root.winfo_pointery(), ww
        try:
            from .alerts_page import game_rect
            g = game_rect()
        except Exception:
            g = None
        if not g:
            g = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        gx, gy, gw, gh = g
        x = min(max(gx, cx + cw - ww), gx + gw - ww)              # (under the ⚙, on the game's monitor)
        y = min(cy + 34, gy + gh - wh)
        w.geometry(f"+{int(x)}+{int(y)}")
        w.deiconify()
        try:
            w.focus_force()
        except tk.TclError:
            pass
        w.bind("<FocusOut>", lambda _e: self.root.after(150, self._pcs_focus_gone))

    def _pcs_focus_gone(self):
        w = getattr(self, "pcs_win", None)
        if w is None:
            return
        from .style import CAPTURING
        if CAPTURING[0] is not None:                       # (the key box is waiting for a key)
            return
        try:
            f = str(w.tk.call("focus"))
        except tk.TclError:
            f = ""
        if not f.startswith(str(w)):
            self.pcpop_settings_close()

    def _pcs_keys(self):
        """The overlay's close key is set on Keys (2.125.5: one place)."""
        try:
            self.app_show(focus=True, why="pcpop")
            self.hotkeys_open("checks:pc_close_key")
        except Exception:
            from . import buglog
            buglog.caught()

    def _pcs_all(self):
        self.pcpop_settings_close()
        try:
            self.app_show(focus=True, why="pcpop")
            self.settings_open("Price checking", "pc_single")
        except Exception:
            from . import buglog
            buglog.caught()

    def _pcpop_frame(self, w, P):
        """The scrolling body (its bar in the style's colors) and the button row under it."""
        st = ttk.Style(self.root)
        name = "PcPop.Vertical.TScrollbar"
        st.configure(name, background=P["line"], troughcolor=P.get("field", P["bg"]), bordercolor=P["bg"],
                     arrowcolor=P["muted"], lightcolor=P["line"], darkcolor=P["line"], gripcount=0, arrowsize=12)
        st.map(name, background=[("active", P["accent"]), ("pressed", P["accent"])])
        from . import soft                       # rule 24: thin and round, in the overlay style's colors
        soft.scrollbar_style(self.root, st, name, soft.rgb(self.root, P["muted"]), ns="pcpop",
                             strong=soft.rgb(self.root, P["accent"]))
        foot = tk.Frame(w.body, bg=P["bg"])
        foot.pack(fill="x", side="bottom", padx=8, pady=8)
        self.pp_foot = foot
        tk.Frame(w.body, bg=P["line"], height=1).pack(fill="x", side="bottom")
        box = tk.Frame(w.body, bg=P["bg"])
        box.pack(fill="both", expand=True)
        cv = tk.Canvas(box, bg=P["bg"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=cv.yview, style=name)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=P["bg"])
        win = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(win, width=e.width), self._pcpop_wrap(e.width)))
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=(0, 0, e.width, e.height)))

        def wheel(e):
            d = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            cv.yview_scroll(d * 3, "units")
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            w.bind_all(ev, lambda e: wheel(e) if self._pcpop_under(e) else None, add="+")
        self.pp_cv, self.pp_inner, self.pp_sb = cv, inner, sb

    def _pcpop_under(self, e):
        w = getattr(self, "pp_win", None)
        try:
            x, y = w.winfo_rootx(), w.winfo_rooty()
            return w.winfo_ismapped() and x <= e.x_root < x + w.winfo_width() and y <= e.y_root < y + w.winfo_height()
        except (tk.TclError, AttributeError):
            return False

    def _pcpop_wrap(self, width):
        for lbl in getattr(self, "pp_wraps", []):
            try:
                lbl.configure(wraplength=max(160, width - 40))
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- what it shows
    def pcpop_refresh(self, rec):
        """The item on Price Checks changed (searched, priced, a tick): the card follows if it shows that item.
        Another Price Checks item shown in the app while the card is open: the card shows that one too."""
        if rec is None or getattr(self, "pp_win", None) is None or getattr(self, "_pp_own_change", False):
            return
        if rec["id"] != getattr(self, "pp_rid", None):
            if not (getattr(self, "pp_up", False) and getattr(self, "pp_rid", None) is not None
                    and rec.get("src") == "pc"):
                return
            self.pp_rid, self.pp_open = rec["id"], set()  # (a new item starts with its listings closed)
        if getattr(self, "_pp_job", None):
            return

        def go():
            self._pp_job = None
            if self._pcpop_typing():                      # (never under your typing - try again in a moment. 3.0.1:
                self._pp_job = self.root.after(400, go)   #  only while you type: a box that just keeps the keyboard
                return                                    #  after Enter / Search again no longer holds the card back)
            # (feedback: another price check showed the one before's Miscellaneous Yes / No): the item the card shows
            # NOW - a refresh asked for the item before must never fill the card over the new one
            cur = self.records.get(getattr(self, "pp_rid", None))
            if cur is not None and getattr(self, "pp_win", None) is not None:
                self.pcpop_fill(cur)
        self._pp_job = self.root.after(60, go)

    def _pcpop_cancel(self):
        """A refresh waiting to run: dropped (the card is filled or closed right now)."""
        job, self._pp_job = getattr(self, "_pp_job", None), None
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                from . import buglog
                buglog.caught()

    def pcpop_fill(self, rec):
        from .pricecheck_page import RARITY_COL, cur_label, flag_text, listing_facts, own_flags, widened_line
        from .pricefmt import fmt_div
        from .trade import ago, mod_impact
        P = self.pp_P
        inner = self.pp_inner
        top = self.pp_cv.yview()[0] if inner.winfo_children() else 0.0
        if getattr(self, "_pp_refocus", None) is None:     # 3.0.1: a box you're in keeps the keyboard after a redraw
            self._pp_refocus = self._pcpop_box_focused()
        for c in inner.winfo_children():
            c.destroy()
        self.pp_wraps = []
        self.pp_ticks = []                                   # every box on the card - for drag-to-tick
        self.pp_boxes = {}
        it = rec.get("item") or {}
        body, head = P.get("body") or P["font"], P.get("hfont") or P["font"]
        pad = dict(padx=16)

        def lab(parent, text, fg=None, size=10, bold=False, font=None, wrap=True, **pk):
            l_ = tk.Label(parent, text=text, bg=P["bg"], fg=fg or P["text"], anchor="w", justify="left",
                          font=(font or body, size, "bold") if bold else (font or body, size))
            l_.pack(fill="x", **pk)
            if wrap:
                self.pp_wraps.append(l_)
            return l_

        # the item
        rcol = ink(C.get(RARITY_COL.get(it.get("rarity"), ""), P["big"]), P["bg"])
        name = " ".join(x for x in (it.get("name"), it.get("base")) if x and x != it.get("name") or x == it.get("name")
                        ) if it.get("name") else (it.get("base") or "Item")
        lab(inner, it.get("name") or it.get("base") or "Item", fg=rcol, size=13, bold=True, font=head, pady=(8, 0), **pad)
        info = [f"{it.get('rarity') or ''} {it.get('class') or ''}".strip(),
                it.get("base") if it.get("name") and it.get("base") and it.get("base") != it.get("name") else "",
                f"item level {it['ilvl']}" if it.get("ilvl") else "",
                f"area level {it['area_level']}" if it.get("area_level") else "",      # (waystones: shown only)
                f"quality {it['quality']}%" if it.get("quality") else ""]
        lab(inner, " · ".join(x for x in info if x), fg=P["muted"], size=9, **pad)
        flags = own_flags(rec)
        if flags:                                            # Corrupted, Mirrored, Fractured ... (a mark + a word)
            lab(inner, flag_text(flags), fg=ink(C["red"] if "corrupted" in flags else P["text"], P["bg"]), size=9,
                bold=True, **pad)
        del name

        # the price
        st = rec.get("state")
        box = tk.Frame(inner, bg=P.get("field", P["bg"]), highlightthickness=1, highlightbackground=P["line"])
        box.pack(fill="x", padx=16, pady=(8, 0))
        if st == "done" and rec.get("est") is not None:
            tk.Label(box, text="≈ " + fmt_div(rec["est"]), bg=box["bg"], fg=P["big"], font=(head, 18, "bold"),
                     anchor="w").pack(fill="x", padx=8, pady=(8, 0))
            entries, total, n = self.pc_entries(rec)
            conf = {"high": "a solid price", "medium": "a fair guess", "low": "thin data - check by hand"}.get(
                str(rec.get("conf") or "").lower(), "")
            sub = f"from the {min(n, 5) or n} cheapest of {total} listing{'s' if total != 1 else ''}" + \
                (f" · {conf}" if conf else "")
            tk.Label(box, text=sub, bg=box["bg"], fg=P["muted"], font=(body, 9), anchor="w").pack(
                fill="x", padx=8, pady=(0, 8))
        else:
            msg = {"pricing": "Searching the trade site…", "error": rec.get("label") or "Couldn't search",
                   "done": "No listings matched these mods"}.get(st, "Waiting in line…")
            tk.Label(box, text=msg, bg=box["bg"], fg=C["red"] if st == "error" else P["text"], font=(body, 11),
                     anchor="w", justify="left", wraplength=360).pack(fill="x", padx=8, pady=8)
        slot = tk.Frame(inner, bg=P["bg"])                  # 3.0.6: a slot, so a tick can show it in place
        slot.pack(fill="x", **pad)
        self.pp_notice = (slot, P, body)
        if rec.get("changed"):
            self._pcpop_notice()
        wl = widened_line(rec)                               # owner (base widening): as the app's card
        if wl:
            lab(inner, wl, fg=P["text"], size=9, pady=(4, 0), **pad)

        # 2.114.0 (feedback: white / magic bases didn't price the same here): the item's own filters, as on the
        # app's card - base type, item level, quality, sockets (a base's search is these, not its mods)
        s_ = it.get("search") or {}
        if it.get("gear") and s_.get("rarity") != "unique" and it.get("rarity") != "Currency":
            self._pcpop_props(inner, P, rec, it, body, head)

        if it.get("rarity") != "Currency":                   # Round 18: the flags, as the app's Miscellaneous
            self._pcpop_misc(inner, P, rec, it, body, head)

        # the mods searched (tick = searched; a click changes it, Search again runs it)
        every = [m for m in it.get("mods") or [] if m.get("text")]
        mods = [m for m in every if m.get("kind") != "Rune"]
        runes = [m for m in every if m.get("kind") == "Rune"]
        if runes or "J" in (it.get("socket_types") or ""):
            self._pcpop_socketed(inner, P, rec, it, runes, body, head)
        if mods:
            hr = tk.Frame(inner, bg=P["bg"])
            hr.pack(fill="x", padx=16, pady=(12, 2))
            tk.Label(hr, text="MODS SEARCHED", bg=P["bg"], fg=P["head"], font=(head, 9, "bold")).pack(side="left")
            if any(m.get("sid") and self._card_has_vals(rec, m) for m in mods):
                tk.Label(hr, text="Min      Max", bg=P["bg"], fg=P["muted"], font=(body, 9)).pack(side="right")
            ticked = {id(m) for m in self.pc_ticked(rec)}
            if not ticked:
                ticked = {id(m) for m in mods if m.get("sid") and mod_impact(rec, m) != "ignore"}
            for m in mods:
                row = tk.Frame(inner, bg=P["bg"])
                row.pack(fill="x", padx=16)
                on = id(m) in ticked
                can = bool(m.get("sid"))
                cb = tk.Label(row, text=("☑" if on else "☐") if can else "·", bg=P["bg"],
                              fg=P["accent"] if on else P["muted"], font=("Segoe UI Symbol", 10),
                              cursor="hand2" if can else "")
                cb.pack(side="left", anchor="n")
                col = MOD_COL.get(KIND_COL.get(m.get("kind"), "explicit"), P["text"])
                flags = m.get("flags") or set()
                if "fractured" in flags:
                    col = MOD_COL["fractured"]
                elif "desecrated" in flags:
                    col = MOD_COL["desecrated"]
                tl = tk.Label(row, text=m.get("shown") or m["text"], bg=P["bg"], fg=ink(col, P["bg"]) if on or not can else P["muted"],
                              font=(body, 10), anchor="w", justify="left", cursor="hand2" if can else "")
                vb = None
                if can and self._card_has_vals(rec, m):
                    vb = self._pcpop_vals(row, P, rec, m, on)
                tl.pack(side="left", fill="x", expand=True, padx=(4, 0))
                self.pp_wraps.append(tl)
                if can:
                    t = self._pcpop_drag_add(rec, cb, tl, on, lambda to, mm=m: self.toggle_mod(rec, mm, to),
                                             ink(col, P["bg"]), P["muted"], P)
                    t["mod"], t["boxes"] = m, vb
                src = next((x for x in ("fractured", "desecrated")
                            if x in flags or str(m.get("sid") or "").startswith(x + ".")), None)
                if src and can:
                    self._pcpop_only(inner, P, rec, m, src, body)

        # the cheapest listings - a summary each; click opens the whole item (no seller names)
        if st == "done":
            entries, total, n = self.pc_entries(rec)
            if entries:
                lab(inner, "CHEAPEST LISTINGS", fg=P["head"], size=9, bold=True, font=head, pady=(12, 2), **pad)
            lvl = ilvl_matters(it)
            for e in entries:
                f = listing_facts(e)
                self._pcpop_listing(inner, P, f, body, head, cur_label, ago, RARITY_COL, lvl)
        tk.Frame(inner, bg=P["bg"], height=10).pack(fill="x")

        # the buttons
        for c in self.pp_foot.winfo_children():
            c.destroy()
        from .pricecheck_page import search_tip, search_word
        from .style import Tooltip
        go = self._pcpop_btn(search_word(rec), lambda: self._pcpop_go(rec), primary=True)     # (owner: ↔ Broaden
        go.pack(side="left")                                                             # Search - one step a click)
        go._search_tip = Tooltip(go, search_tip(rec))
        self.pp_go = go
        tb = self._pcpop_btn("Trade Site", self.pc_open_trade, enabled=bool(rec.get("qid")))
        trade_icon(tb, color=tb.cget("fg"), size=14).pack(side="left", padx=(8, 0))
        self._pcpop_btn("Open in app", lambda: self._pcpop_in_app(rec)).pack(side="right")
        self.root.after_idle(lambda: self._pcpop_after(top))
        want, self._pp_refocus = getattr(self, "_pp_refocus", None), None
        if want:
            self._pcpop_refocus(*want)

    def _pcpop_socketed(self, inner, P, rec, it, runes, body, head):
        """2.125.5 (feedback: the card did not show the slots or what is in them): what's in the item's sockets - the
        game's copy gives each socketed rune / soul core / talisman's effect, marked (rune), but not its name, so
        those effects are listed here (tick one to search it); a jewel socket says it's there."""
        from .style import Tooltip
        hr = tk.Frame(inner, bg=P["bg"])
        hr.pack(fill="x", padx=16, pady=(12, 2))
        tk.Label(hr, text="SOCKETED", bg=P["bg"], fg=P["head"], font=(head, 9, "bold")).pack(side="left")
        info = tk.Label(hr, text=(socket_words(it).strip(" ()") or "") + "  ⓘ", bg=P["bg"], fg=P["muted"],
                        font=(body, 9))
        info.pack(side="left", padx=(8, 0))
        Tooltip(info, "What the item's sockets hold. The game's copy (Ctrl+C) lists what each socketed rune, soul "
                      "core or talisman does - not its name - and nothing about a socketed jewel. Socketed effects "
                      "can be swapped, so they aren't searched unless you tick one.")
        ticked = {id(m) for m in self.pc_ticked(rec)}
        for m in runes:
            row = tk.Frame(inner, bg=P["bg"])
            row.pack(fill="x", padx=16)
            on, can = id(m) in ticked, bool(m.get("sid"))
            cb = tk.Label(row, text=("☑" if on else "☐") if can else "◆", bg=P["bg"],
                          fg=P["accent"] if on else P["muted"], font=("Segoe UI Symbol", 10), cursor="hand2" if can else "")
            cb.pack(side="left", anchor="n")
            tl = tk.Label(row, text=m.get("shown") or m["text"], bg=P["bg"],
                          fg=ink(MOD_COL["rune"], P["bg"]) if on or not can else P["muted"], font=(body, 10),
                          anchor="w", justify="left", cursor="hand2" if can else "")
            tl.pack(side="left", fill="x", expand=True, padx=(4, 0))
            self.pp_wraps.append(tl)
            if can:
                t = self._pcpop_drag_add(rec, cb, tl, on, lambda to, mm=m: self.toggle_mod(rec, mm, to),
                                         ink(MOD_COL["rune"], P["bg"]), P["muted"], P)
                t["mod"] = m
        if "J" in (it.get("socket_types") or ""):
            tk.Label(inner, text="◇ A jewel socket - the game's copy doesn't say which jewel is in it.", bg=P["bg"],
                     fg=P["muted"], font=(body, 9), anchor="w", justify="left").pack(fill="x", padx=16)

    def _pcpop_btn(self, text, cmd, primary=False, enabled=True):
        """A button in the overlay's Style (not the app theme's): the main one filled with its accent."""
        P = self.pp_P
        if not enabled:
            bg, fg, line = P["bg"], P["muted"], P["line"]
        elif primary:
            bg, fg, line = P["accent"], P.get("on_fg") if P.get("skin") and P.get("on_bg") == P["accent"] else P["bg"], P["accent"]
        else:
            bg, fg, line = P.get("off_bg", P["bg"]), P["text"], P["line"]
        b = tk.Label(self.pp_foot, text=text, bg=bg, fg=fg, padx=12, pady=4, highlightthickness=1,
                     highlightbackground=line, font=(P.get("body") or P["font"], 10, "bold" if primary else "normal"),
                     cursor="hand2" if enabled else "")
        if enabled:
            b.bind("<Button-1>", lambda _e: cmd())
            b.bind("<Enter>", lambda _e: b.config(highlightbackground=P["accent"]))
            b.bind("<Leave>", lambda _e: b.config(highlightbackground=line))
        return b

    def _pcpop_after(self, top):
        try:
            self._pcpop_wrap(self.pp_cv.winfo_width())
            self.pp_cv.update_idletasks()
            self.pp_cv.yview_moveto(top)
        except (tk.TclError, AttributeError):
            pass

    def _pcpop_listing(self, inner, P, f, body, head, cur_label, ago, RARITY_COL, lvl=False):
        from .pricecheck_page import flag_text
        lid = f.get("id")
        opened = lid in self.pp_open
        card = tk.Frame(inner, bg=P["bg"], highlightthickness=1, highlightbackground=P["line"])
        card.pack(fill="x", padx=16, pady=(4, 0))
        top = tk.Frame(card, bg=P["bg"], cursor="hand2")
        top.pack(fill="x", padx=8, pady=4)
        amt, cur = f["price"] if f.get("price") else (None, None)
        price = f"{amt:g} {cur_label(cur)}" if amt is not None else "?"
        arrow = tk.Label(top, text="▾" if opened else "▸", bg=P["bg"], fg=P["muted"], font=("Segoe UI Symbol", 10))
        arrow.pack(side="left")
        tk.Label(top, text=price, bg=P["bg"], fg=P["big"], font=(head, 10, "bold")).pack(side="left", padx=(4, 8))
        when = ago(f["ts"]) if f.get("ts") else ""
        seller = f.get("seller") or ""
        if seller and not self._pcpop_mine(seller):          # (yours never shows - with or without its #1234)
            when = f"{seller} · {when}" if when else seller
        if f.get("times", 1) > 1:                             # 2.113.0: one row per seller
            when = f"listed {f['times']}× · {when}" if when else f"listed {f['times']}×"
        if lvl and f.get("ilvl"):                             # Round 18: its item level, where that matters
            when = f"ilvl {f['ilvl']} · {when}" if when else f"ilvl {f['ilvl']}"
        if when:
            tk.Label(top, text=when, bg=P["bg"], fg=P["muted"], font=(body, 9)).pack(side="right")
        if f.get("flags"):                                   # spotted at a glance, folded or not
            tk.Label(top, text=flag_text(f["flags"]), bg=P["bg"], fg=P["text"], font=(body, 9)).pack(side="left")
        mods = [t for _tier, t, k in f.get("mods") or [] if k not in ("implicit", "enchant", "rune")]
        summ = " · ".join(mods[:3]) + (" …" if len(mods) > 3 else "")
        sl = tk.Label(card, text=summ or "(no mods)", bg=P["bg"], fg=P["muted"], font=(body, 9), anchor="w",
                      justify="left", cursor="hand2")
        sl.pack(fill="x", padx=(24, 8), pady=(0, 4))
        self.pp_wraps.append(sl)
        if opened:
            sl.pack_forget()
            full = tk.Frame(card, bg=P["bg"])
            full.pack(fill="x", padx=(24, 8), pady=(0, 8))
            rcol = ink(C.get(RARITY_COL.get(f.get("rarity"), ""), P["text"]), P["bg"])
            nm = " ".join(x for x in (f.get("name"), f.get("base")) if x)
            tk.Label(full, text=nm, bg=P["bg"], fg=rcol, font=(head, 10, "bold"), anchor="w").pack(fill="x")
            parts = " · ".join(str(p) for p in (f.get("parts") or []) if p)
            if f.get("ilvl"):
                parts = (parts + " · " if parts else "") + f"item level {f['ilvl']}"
            if parts:
                l_ = tk.Label(full, text=parts, bg=P["bg"], fg=P["muted"], font=(body, 9), anchor="w", justify="left")
                l_.pack(fill="x")
                self.pp_wraps.append(l_)
            for tier, text, kind in f.get("mods") or []:
                l_ = tk.Label(full, text=(f"{tier}  " if tier else "") + text, bg=P["bg"],
                              fg=ink(MOD_COL.get(kind, P["text"]), P["bg"]), font=(body, 10), anchor="w", justify="left")
                l_.pack(fill="x")
                self.pp_wraps.append(l_)
            if f.get("flags"):
                tk.Label(full, text=flag_text(f["flags"]), bg=P["bg"], anchor="w", font=(body, 9, "bold"),
                         fg=ink(C["red"] if "corrupted" in f["flags"] else P["text"], P["bg"])).pack(fill="x")
            if f.get("note"):
                l_ = tk.Label(full, text=f["note"], bg=P["bg"], fg=P["muted"], font=(body, 9), anchor="w", justify="left")
                l_.pack(fill="x")
                self.pp_wraps.append(l_)

        def flip(_e=None):
            (self.pp_open.discard if opened else self.pp_open.add)(lid)
            rec = self.records.get(self.pp_rid)
            if rec is not None:
                self.pcpop_fill(rec)
        for wdg in (top, arrow, sl, *top.winfo_children()):
            wdg.bind("<Button-1>", flip)

    def _pcpop_props(self, inner, P, rec, it, body, head):
        """PROPERTIES: [✓] Base type (unticked = any base of its kind), [✓] Item level / Quality / Sockets with
        Min / Max - the same rec["opts"] the app's card changes (search_opt_set); Enter searches again."""
        from .searchopts_page import default_opts
        cur = {**default_opts(it), **(rec.get("opts") or {})}
        rows = []
        if it.get("ilvl"):
            rows.append(("ilvl", f"Item level: {it['ilvl']}", it["ilvl"]))
        if it.get("quality"):
            rows.append(("quality", f"Quality: +{it['quality']}%", it["quality"]))
        if it.get("sockets"):
            rows.append(("sockets", f"Sockets: {it['sockets']}" + socket_words(it), it["sockets"]))
        hr = tk.Frame(inner, bg=P["bg"])
        hr.pack(fill="x", padx=16, pady=(12, 2))
        tk.Label(hr, text="PROPERTIES", bg=P["bg"], fg=P["head"], font=(head, 9, "bold")).pack(side="left")
        if rows:
            tk.Label(hr, text="Min      Max", bg=P["bg"], fg=P["muted"], font=(body, 9)).pack(side="right")

        def tick_row(on, text, cmd):
            row = tk.Frame(inner, bg=P["bg"])
            row.pack(fill="x", padx=16)
            cb = tk.Label(row, text="☑" if on else "☐", bg=P["bg"], fg=P["accent"] if on else P["muted"],
                          font=("Segoe UI Symbol", 10), cursor="hand2")
            cb.pack(side="left", anchor="n")
            tl = tk.Label(row, text=text, bg=P["bg"], fg=P["text"] if on else P["muted"], font=(body, 10),
                          anchor="w", cursor="hand2")
            tl.pack(side="left", fill="x", expand=True, padx=(4, 0))
            self._pcpop_drag_add(rec, cb, tl, on, cmd, P["text"], P["muted"], P)
            return row

        def changed():
            rec["changed"] = True
            self.dirty = True

        same = cur.get("base") == "same"
        tick_row(same, f"Base type: {it['base']}" if same else f"Any {it.get('class') or 'base'}",
                 lambda to: (self.search_opt_set(rec, "base", "same" if to else "class", redraw=False), changed()))
        self.pp_ticks[-1]["texts"] = (f"Base type: {it['base']}", f"Any {it.get('class') or 'base'}")
        self.pp_props = {}
        for key, label, have in rows:
            v = cur.get(key)
            lo, hi = (v.get("min"), v.get("max")) if isinstance(v, dict) else (v, None)
            on = v not in (None, "", 0, {})
            tick = (lambda to, k=key, h=have: (self.search_opt_set(rec, k, {"min": h} if to else None, redraw=False),
                                               changed()))
            row = tick_row(on, label, tick)
            boxes = {}
            for k, val in (("max", hi if on else None), ("min", lo if on else have)):    # (packed from the right)
                e = tk.Entry(row, width=5, bg=P.get("field", P["bg"]), fg=P["text"], insertbackground=P["text"],
                             relief="flat", highlightthickness=1, highlightbackground=P["line"],
                             highlightcolor=P["accent"], justify="center", font=(body, 9),
                             state="normal" if on else "disabled", disabledbackground=P["bg"],
                             disabledforeground=P["muted"])
                e.insert(0, "" if val is None else str(val))
                e.pack(side="right", padx=(4, 0))
                boxes[k] = e

            def keep(_e=None, k_=key, b=boxes):
                vals = {}
                for k2, e2 in b.items():
                    t = e2.get().strip()
                    try:
                        vals[k2] = int(float(t)) if t else None
                        e2.config(highlightbackground=P["line"])
                    except ValueError:
                        e2.config(highlightbackground=C["red"])
                        return False
                vals = {k2: v2 for k2, v2 in vals.items() if v2 is not None}
                before = (rec.get("opts") or {}).get(k_)
                self.search_opt_set(rec, k_, vals or None, redraw=False)
                if (rec.get("opts") or {}).get(k_) != before:
                    self._pcpop_changed(rec)
                return True
            for k, e in boxes.items():
                e.keep = keep                                 # (tests call it, as on the mods' boxes)
                e.bind("<KeyRelease>", keep)
                e.bind("<Return>", lambda _e, kp=keep: self._pcpop_enter(rec, kp))
                self._pcpop_box(e, ("prop", key, k),           # 3.0.1: a click here takes the keyboard (it never did)
                                lambda t=tick: (t(True), self.pcpop_fill(rec)))
            self.pp_props[key] = boxes
            self.pp_ticks[-1]["boxes"] = boxes

    def _pcpop_misc(self, inner, P, rec, it, body, head):
        """MISCELLANEOUS (compact): the item's own flags (at Yes), Corrupted and Crafted - Any / Yes / No, the same
        rec["opts"] as the app card's Miscellaneous; a click steps through them, Search again runs it."""
        from .app import misc_tip
        from .searchopts_page import default_opts
        from .style import Tooltip
        cur = {**default_opts(it), **(rec.get("opts") or {})}
        has = set(it.get("flags") or ()) | ({"corrupted"} if it.get("corrupted") else set())
        rows = [(k, lab_) for k, lab_ in self._card_misc_keys(it)     # (and any the search uses: a base's No's)
                if k in has or k in ("corrupted", "crafted") or (cur.get(k) or "any") != "any"]
        if not rows:
            return
        tk.Label(inner, text="MISCELLANEOUS", bg=P["bg"], fg=P["head"], font=(head, 9, "bold"), anchor="w").pack(
            fill="x", padx=16, pady=(12, 2))
        grid = tk.Frame(inner, bg=P["bg"])
        grid.pack(fill="x", padx=16)
        for i, (key, label) in enumerate(rows):
            v = cur.get(key) or "any"
            cell = tk.Frame(grid, bg=P["bg"], cursor="hand2")
            cell.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16))
            a = tk.Label(cell, text=label, bg=P["bg"], fg=P["text"] if key in has else P["muted"], font=(body, 9),
                         cursor="hand2")
            a.pack(side="left")
            b = tk.Label(cell, text=f"{v.title()} ▾", bg=P["bg"], fg=P["accent"] if v != "any" else P["text"],
                         font=(body, 9, "bold"), cursor="hand2")
            b.pack(side="left", padx=(8, 0))
            Tooltip(cell, misc_tip(key, label))

            def step(_e=None, k=key, v_=v):
                self.search_opt_set(rec, k, {"any": "yes", "yes": "no", "no": "any"}[v_], redraw=False)
                rec["changed"] = True
                self.dirty = True
                self.pcpop_fill(rec)
            for wdg in (cell, a, b):
                wdg.bind("<Button-1>", step)
        grid.columnconfigure(1, weight=1)

    def _pcpop_vals(self, row, P, rec, m, on):
        """Min / Max for one mod, as on the app's card: what the search uses; typing changes it for this item (the same
        m["uval"] the app's card keeps); Enter searches again."""
        from .mods import vfilter
        saved = m.pop("uval", None)
        try:
            auto = vfilter(m) or {}
        finally:
            if saved is not None:
                m["uval"] = saved
        cur = m.get("uval") if m.get("uval") is not None else auto
        boxes = {}
        for key in ("max", "min"):                      # (packed from the right: Min | Max)
            v = cur.get(key)
            e = tk.Entry(row, width=5, bg=P.get("field", P["bg"]), fg=P["text"], insertbackground=P["text"],
                         relief="flat", highlightthickness=1, justify="center",
                         highlightbackground=P["accent"] if m.get("uval") is not None else P["line"],
                         highlightcolor=P["accent"], font=(P.get("body") or P["font"], 9),
                         state="normal" if on else "disabled", disabledbackground=P["bg"],
                         disabledforeground=P["muted"])
            e.insert(0, "" if v is None else f"{v:g}")
            e.pack(side="right", padx=(4, 0))
            boxes[key] = e

        def keep(_e=None):
            vals = {}
            for key, e in boxes.items():
                t = e.get().strip().replace(",", ".")
                try:
                    vals[key] = float(t) if t else None
                    e.config(highlightbackground=P["line"])
                except ValueError:
                    e.config(highlightbackground=C["red"])
                    return False
            if vals["min"] is not None and vals["max"] is not None and vals["min"] > vals["max"]:
                boxes["max"].config(highlightbackground=C["red"])
                return False
            norm_auto = {k: (None if auto.get(k) is None else float(auto[k])) for k in ("min", "max")}
            before = m.get("uval")
            if vals == norm_auto:
                m.pop("uval", None)
            else:
                m["uval"] = vals
                for e in boxes.values():
                    e.config(highlightbackground=P["accent"])
            if m.get("uval") != before:
                self._pcpop_changed(rec)
            return True
        for key, e in boxes.items():
            e.keep = keep                                 # (tests call it: no window manager there to focus a box)
            e.bind("<KeyRelease>", keep)
            e.bind("<Return>", lambda _e: self._pcpop_enter(rec, keep))
            self._pcpop_box(e, ("mod", id(m), key), lambda: self._pcpop_tick(rec, m, True))
        return boxes

    def _pcpop_changed(self, rec):
        """3.0.6 (owner: the button kept saying Broaden after a value was typed): a box you changed is a filter change -
        the orange button says Search at once (the card isn't drawn again, so the box keeps the keyboard)."""
        rec["changed"] = True
        self.dirty = True
        self._pcpop_notice()
        go = getattr(self, "pp_go", None)
        if go is None:
            return
        from .pricecheck_page import search_tip, search_word
        try:
            go.config(text=search_word(rec))
            tip = getattr(go, "_search_tip", None)
            if tip is not None:
                tip.text = search_tip(rec)
        except tk.TclError:
            pass

    def _pcpop_notice(self):
        """The line under the price once the filters changed (once)."""
        slot, P, body = getattr(self, "pp_notice", (None, None, None))
        try:
            if slot is None or slot.winfo_children():
                return
            tk.Label(slot, text="↻ Filters changed - press Search again.", bg=P["bg"], fg=P["accent"],
                     font=(body, 9), anchor="w", justify="left").pack(fill="x", pady=(4, 0))
        except tk.TclError:
            pass

    def _pcpop_go(self, rec):
        """Search again / ↔ Broaden Search: what you typed is searched, and the card shows what it found."""
        self._pp_typed = False
        return self.pc_search_go(rec)

    # ---------------------------------------------------------------- 3.0.1: typing in a Min / Max box
    def _pcpop_box(self, e, box_id, tick):
        """Every Min / Max box: a click takes the keyboard (a gray one ticks its row first), a key marks typing."""
        e._pp_id = box_id
        self.pp_boxes[box_id] = e
        e.bind("<Button-1>", lambda _e, ee=e, t=tick: self._pcpop_box_click(ee, t), add="+")
        e.bind("<KeyPress>", self._pcpop_key, add="+")

    def _pcpop_box_click(self, e, tick):
        """A click in a Min / Max box: you can type in it. A gray box (its row not ticked) ticks its row - the card is
        drawn again with the box on - and the cursor goes in the new box."""
        try:
            gray = str(e.cget("state")) == "disabled"
        except tk.TclError:
            return None
        if gray:
            self._pp_refocus = (e._pp_id, True)
            tick()
            return "break"
        self._pcpop_type(e)
        return None

    def _pcpop_type(self, e):
        """The card takes the keyboard for typing - Windows: the card's window is made one that can have it and put
        in front (overlaywin.take_keyboard: a click on a window over the game may not hand it over). The window that
        had the keyboard (the game) gets it back when the card closes."""
        w = getattr(self, "pp_win", None)
        try:
            take = getattr(w, "take_keyboard", None)
            before = take(e) if take is not None else None
            back = before or getattr(self, "_pp_game", None)    # (the click itself may have given the card the
            if back:                                            #  keyboard already: then the game it opened over)
                self._pp_back = back
            if take is None:
                w.focus_force()
            e.focus_set()
        except (tk.TclError, AttributeError):
            pass

    def _pcpop_key(self, ev):
        """A key in a Min / Max box: you're typing - the card isn't drawn again under it until you search."""
        if ev.keysym not in ("Return", "KP_Enter", "Escape", "Tab", "ISO_Left_Tab"):
            self._pp_typed = True

    def _pcpop_enter(self, rec, keep):
        """Enter in a Min / Max box: search again with it; the box keeps the keyboard when the card is drawn again."""
        if not keep():
            return "break"
        self._pp_typed = False
        self.reprice([rec["id"]])
        return "break"

    def _pcpop_typing(self):
        """Are you typing in one of the card's boxes (a key since the last search, and the box has the keyboard)?"""
        return bool(getattr(self, "_pp_typed", False)) and self._pcpop_box_focused() is not None

    def _pcpop_box_focused(self):
        """(box id, False) of the Min / Max box that has the keyboard, or None."""
        w = getattr(self, "pp_win", None)
        try:
            f = str(w.tk.call("focus")) if w is not None else ""
        except tk.TclError:
            return None
        for box_id, e in (getattr(self, "pp_boxes", None) or {}).items():
            if f and str(e) == f:
                return box_id, False
        return None

    def _pcpop_refocus(self, box_id, take=False):
        """After the card is drawn again: the same box has the keyboard, the cursor at its end (once it's on screen -
        Tk gives an unmapped box the keyboard only when it shows)."""
        def go():
            e = (getattr(self, "pp_boxes", None) or {}).get(box_id)
            if e is None:
                return
            try:
                if not e.winfo_exists() or str(e.cget("state")) == "disabled":
                    return
                e.update_idletasks()
                if take:
                    self._pcpop_type(e)
                else:
                    e.focus_set()
                e.icursor("end")
            except tk.TclError:
                pass
        self.root.after_idle(go)

    @staticmethod
    def _pcpop_mine(seller):
        try:
            from .trade import is_own
            return is_own(seller)
        except Exception:
            return False

    def _pcpop_drag_add(self, rec, cb, tl, on, apply, on_fg, off_fg, P):
        """3.0.6 (owner: tick boxes by holding the left button and dragging across them - every box on the card, not
        just the mods): a press flips this box; every box the mouse then crosses takes that same state. The boxes
        are painted at once; the search changes once, on release. apply(on) changes the search (no redraw)."""
        t = {"cb": cb, "tl": tl, "on": on, "apply": apply, "fg": (on_fg, off_fg), "P": P}
        self.pp_ticks.append(t)
        for w in (cb, tl):
            if w is None:
                continue
            w.bind("<ButtonPress-1>", lambda e, tt=t: self._pcpop_drag_start(tt))
            w.bind("<B1-Motion>", lambda e: self._pcpop_drag_over(e.x_root, e.y_root))
            w.bind("<ButtonRelease-1>", lambda e: self._pcpop_drag_end(rec))
        return t

    def _pcpop_drag_paint(self, t, on):
        try:
            t["cb"].config(text="☑" if on else "☐", fg=t["P"]["accent"] if on else t["fg"][1])
            if t["tl"] is not None:
                t["tl"].config(fg=t["fg"][0] if on else t["fg"][1])
                if t.get("texts"):
                    t["tl"].config(text=t["texts"][0 if on else 1])
        except tk.TclError:
            pass

    def _pcpop_drag_start(self, t):
        self._pp_drag = {"to": not t["on"], "set": [t]}
        self._pcpop_drag_paint(t, self._pp_drag["to"])

    def _pcpop_drag_over(self, x, y):
        d = getattr(self, "_pp_drag", None)
        if not d:
            return
        try:
            under = self.root.winfo_containing(x, y)
        except (tk.TclError, KeyError):
            under = None
        if under is None:
            return
        for t in self.pp_ticks:
            if under in (t["cb"], t["tl"]) and all(t is not u for u in d["set"]) and t["on"] != d["to"]:
                d["set"].append(t)
                self._pcpop_drag_paint(t, d["to"])

    def _pcpop_drag_end(self, rec):
        d, self._pp_drag = getattr(self, "_pp_drag", None), None
        if not d:
            return
        changed = [t for t in d["set"] if t["on"] != d["to"]]
        if not changed:
            return
        self._card_quiet = True                          # (the app's card redraws itself when it's shown)
        try:
            for t in changed:
                t["apply"](d["to"])
        finally:
            self._card_quiet = False
        self._pp_own_change = True                       # 3.0.6 (owner round 17: the overlay still flickered on a
        try:                                             # tick): the app's card follows, but its pcpop_refresh would
            self.card_changed(rec)                       # draw this card again - it's already painted
        finally:
            self._pp_own_change = False
        if any(t.get("redraw") for t in changed):
            return self.pcpop_fill(rec)
        # 3.0.6 (owner: the card flickered on every tick - it was drawn again): painted in place - the boxes are
        # already ticked; their Min / Max turn on or off, and the button and the notice say Search
        for t in changed:
            t["on"] = d["to"]
            for e in (t.get("boxes") or {}).values():
                try:
                    e.config(state="normal" if d["to"] else "disabled")
                except tk.TclError:
                    pass
        self._pcpop_changed(rec)
        return None

    def _pcpop_only(self, inner, P, rec, m, src, body):
        """3.0.6 (owner: the box under a fractured / desecrated mod was missing here - Price Checks has it): right
        under the mod, tied with └, a small box to search it only as fractured / desecrated. Ticking it ticks the
        mod too."""
        from .mods import norm
        only = bool((rec.get("only") or {}).get(norm(m["text"])))
        col = ink(MOD_COL[src], P["bg"])
        row = tk.Frame(inner, bg=P["bg"])
        row.pack(fill="x", padx=(24, 16))
        parts = [tk.Label(row, text="└", bg=P["bg"], fg=col, font=(body, 9)),
                 tk.Label(row, text="☑" if only else "☐", bg=P["bg"], fg=col, font=("Segoe UI Symbol", 9),
                          cursor="hand2"),
                 tk.Label(row, text=f"{src.capitalize()} only", bg=P["bg"], fg=col, font=(body, 9), cursor="hand2")]
        for w in parts:
            w.pack(side="left", padx=(0, 4))
        t = self._pcpop_drag_add(rec, parts[1], parts[2], only, lambda to: self.card_only(rec, m, to), col, col, P)
        t["redraw"] = True                               # (it may tick its mod too: the card is drawn again)

    def _pcpop_tick(self, rec, mod, on):
        self.toggle_mod(rec, mod, on)
        self.card_changed(rec)
        self.pcpop_fill(rec)

    def _pcpop_in_app(self, rec):
        try:
            self.pc_show(rec)
            self.app_show("pricecheck", focus=True, why="pcpop")
        except Exception:
            self.log_error("opening Price Checks")
