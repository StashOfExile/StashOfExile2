"""2.131.0 the Feature Picker, now Setup (features.py has the groups): asked once at the first start, one question
a screen - which features you use, whether you want the Overlay, which of its helpers - and the same feature switches
in Settings › General › Features (Run setup again opens it). The helpers' switches are their rows in Overlay ›
Helpers; Setup writes those same settings."""
import tkinter as tk
from tkinter import filedialog, ttk

from . import buglog
from . import features as FEAT
from .config import SETTINGS, save_json
from .style import C, Tooltip


class FeaturesPage:
    # ---------------------------------------------------------------- applying
    def features_set(self, key, value):
        FEAT.set_on(key, value)
        save_json("settings.json", SETTINGS)
        self.features_apply()

    def features_apply(self):
        """Pages leave / come back to the menu; the overlay and its helpers follow the Game Overlay switch."""
        try:
            self.shell.features_changed()
        except Exception:
            buglog.caught()
        for fn in ("merged_build",):
            try:
                getattr(self, fn)()
            except Exception:
                buglog.caught()
        if not FEAT.on("overlay"):
            try:
                self.breach_dismiss()
                self.ws_hide()
                self.remnant_hide()
                self.favours_hide()
            except Exception:
                buglog.caught()
        if FEAT.on("overlay") and self.ritual_cfg().get("on"):
            try:
                self.ritual_start()
            except Exception:
                buglog.caught()
        try:
            self.features_paint()
        except Exception:
            buglog.caught()

    # ---------------------------------------------------------------- the switches (Settings and Setup)
    def features_rows(self, parent, bg, live=False, keys=None, wrap=520):
        """Each app feature: a switch, its name, what it does and its key; then the Beta cluster. live=True: a change
        applies at once (Settings); else the caller applies them (Setup). keys: only these (Setup asks about the
        Overlay on its own screen). -> {key: BooleanVar}. The overlay's helpers aren't here - each one's switch is
        its row in Overlay › Helpers."""
        sm, bold = ("Segoe UI", 9), ("Segoe UI", 10, "bold")
        vars_ = {}

        def row(g, box):
            r = tk.Frame(box, bg=bg)
            r.pack(fill="x", pady=(0, 8))
            v = tk.BooleanVar(value=FEAT.on(g["key"]))
            vars_[g["key"]] = v
            cb = ttk.Checkbutton(r, text=g["name"], variable=v, style="Card.TCheckbutton",
                                 command=(lambda k=g["key"], v=v: self.features_set(k, v.get())) if live else None)
            cb.pack(anchor="w")
            k_ = g.get("keys")
            if k_ == "pc_key":
                from .overlay import key_label
                k_ = key_label(SETTINGS.get("pc_key") or "") or ""
            tk.Label(r, text=g["what"] + (f"  Key: {k_}." if k_ else ""), bg=bg, fg=C["muted"], font=sm,
                     anchor="w", justify="left", wraplength=wrap).pack(fill="x", padx=(24, 0))
        for g in FEAT.GROUPS:
            if keys is None or g["key"] in keys:
                row(g, parent)
        head = tk.Frame(parent, bg=bg)
        head.pack(fill="x", pady=(8, 4))
        tk.Label(head, text="Beta", bg=bg, fg=C["text"], font=bold).pack(side="left")
        tk.Label(head, text="BETA", bg=bg, fg=C["accent"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
        bi = tk.Label(head, text="ⓘ", bg=bg, fg=C["muted"], font=sm, cursor="question_arrow")
        bi.pack(side="left")
        Tooltip(bi, "Features still being tried out: they work, but may change a lot or have rough edges.")
        for g in FEAT.BETA:
            if keys is None or g["key"] in keys:
                row(g, parent)
        return vars_

    def features_paint(self):
        vs = getattr(self, "feat_vars", None) or {}
        for k, v in vs.items():
            try:
                if v.get() != FEAT.on(k):
                    v.set(FEAT.on(k))
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- Setup: asked once, one question a screen
    def features_maybe(self):
        """At start-up: Setup, unless answered - after the quick start / What's new card. (Someone updating has it
        answered already - migrations._helpers_one_switch.)"""
        if FEAT.asked() in ("done", "never") and not getattr(self, "_drawer_setup_due", False):
            return None
        if self.drawer_defer(self.features_maybe):
            return None
        from .config import APP_VERSION
        from .whatsnew import lead_due                          # 3.0.0: "Why 3.0" first (after the quick start)
        if lead_due(SETTINGS.get("whatsnew_lead"), APP_VERSION):
            self.root.after(1500, self.features_maybe)
            return None
        if SETTINGS.get("seen_version") != APP_VERSION:          # 2.131.1 (feedback: it opened under What's new and
            self.root.after(1500, self.features_maybe)         # got lost): What's new / the quick start first -
            return None                                        # closing it brings Setup (close_whatsnew)
        wn = getattr(self, "_whatsnew", None)
        try:
            if wn is not None and wn.winfo_exists():
                self.root.after(1500, self.features_maybe)
                return None
        except tk.TclError:
            pass
        return self.features_picker(first=True)

    def features_picker(self, first=False):
        """Setup: 1 Which features do you want?  2 Do you want the Overlay?  3 Which helpers (only with the Overlay).
        Each screen one question, one orange button (Next / Done), a quiet Back and Skip - use the defaults. It writes
        the same settings as Settings › General › Features and Overlay › Helpers. first=True: the start-up one (×
        asks again next start; afterwards the sharing question, one at a time); else Settings' Run setup again."""
        old = getattr(self, "feat_win", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                return old
        except tk.TclError:
            pass
        self._drawer_setup_due = False
        P2 = C["panel2"]
        w = tk.Toplevel(self.root, bg=C["accent"], padx=1, pady=1)
        w.title("Setup")
        try:
            w.transient(self.root)
        except tk.TclError:
            pass
        w.protocol("WM_DELETE_WINDOW", lambda: self.features_close(w))      # (×: asked again next start)
        w.bind("<Escape>", lambda _e: self.features_close(w))
        self.feat_win = w
        w.minsize(720, 0)                               # (one width for every screen: it doesn't jump about)
        inner = tk.Frame(w, bg=P2, padx=16, pady=16)
        inner.pack(fill="both", expand=True)
        step_l = tk.Label(inner, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w")
        step_l.pack(fill="x")
        top = tk.Frame(inner, bg=P2)
        top.pack(fill="x")
        title_l = tk.Label(top, text="", bg=P2, fg=C["text"], font=("Segoe UI", 16, "bold"), anchor="w")
        title_l.pack(side="left")
        tip_l = tk.Label(top, text="ⓘ", bg=P2, fg=C["muted"], cursor="question_arrow")
        tip_l.pack(side="left", padx=8)
        tip = Tooltip(tip_l, "")
        intro_l = tk.Label(inner, text="", bg=P2, fg=C["muted"], anchor="w", justify="left", wraplength=640)
        intro_l.pack(fill="x", pady=(2, 12))
        body = tk.Frame(inner, bg=P2)
        body.pack(fill="both", expand=True)
        foot = tk.Frame(inner, bg=P2)
        foot.pack(fill="x", pady=(16, 0))
        skip = tk.Label(foot, text="Skip - use the defaults", bg=P2, fg=C["muted"], font=("Segoe UI", 9, "underline"),
                        cursor="hand2")
        skip.pack(side="left")
        Tooltip(skip, "Every feature and helper on, the Overlay as a Bar. Change them any time.")
        nxt = ttk.Button(foot, text="Next", style="Primary.TButton")
        nxt.pack(side="right")
        back = ttk.Button(foot, text="Back", style="Quiet.TButton")
        back.pack(side="right", padx=(0, 8))

        # the answers (what's set now - a new install: everything on)
        feat_keys = [g["key"] for g in FEAT.ALL if g["key"] != "overlay"]
        st = {"step": 0, "feats": None,
              "overlay": tk.StringVar(value="yes" if FEAT.on("overlay") else "no"),
              "helpers": {k: tk.BooleanVar(value=self.helper_switch_on(k))
                          for _g, ks in self.HELPER_GROUPS for k in ks},
              "layout": self.merged_layout(),
              "shape": tk.StringVar(value=self.drawer_cfg().get("shape", "drawer"))}

        def clear():
            for c in body.winfo_children():
                c.destroy()

        def head(step, total, title, intro, info):
            step_l.config(text=f"Step {step} of {total}")
            title_l.config(text=title)
            intro_l.config(text=intro)
            tip.text = info

        def total():
            return 4 if st["overlay"].get() == "yes" else 3             # (the last one: how the app sits with the game)

        def features_screen():
            clear()
            head(1, total(), "Which features do you want?",
                 "Untick what you don't need - it leaves the menu and its keys do nothing. The Overlay is next.",
                 "Your data is kept while a feature is off. Change these any time: Settings › General › Features.")
            old_v = st["feats"]
            st["feats"] = self.features_rows(body, P2, keys=feat_keys, wrap=600)
            if old_v:                                        # (back from screen 2: your ticks, not the saved ones)
                for k, v in st["feats"].items():
                    v.set(old_v[k])
            back.pack_forget()
            nxt.config(text="Next", command=lambda: go(1))

        def overlay_screen():
            clear()
            head(2, total(), "Do you want the Overlay?",
                 "Over the game: a session timer, Notes, Calc, Regex and helpers that warn you in maps.",
                 "Off: nothing shows over the game and its keys do nothing. Change it any time: Settings › General › "
                 "Features › Overlay.")
            for val, name, what in (("yes", "Yes", "Use the Overlay. Pick its helpers next."),
                                    ("no", "No", "No overlay over the game.")):
                r = tk.Frame(body, bg=P2)
                r.pack(fill="x", pady=(0, 8))
                ttk.Radiobutton(r, text=name, value=val, variable=st["overlay"], style="Card.TRadiobutton",
                                command=paint_overlay).pack(anchor="w")
                tk.Label(r, text=what, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(
                    fill="x", padx=(24, 0))
            back.pack(side="right", padx=(0, 8), before=nxt)
            back.config(command=lambda: go(0))
            paint_overlay()

        def paint_overlay():
            yes = st["overlay"].get() == "yes"
            step_l.config(text=f"Step 2 of {total()}")
            nxt.config(text="Next", command=(lambda: go(2)) if yes else (lambda: go(3)))

        def helpers_screen():
            clear()
            head(3, total(), "Which helpers do you want on the Overlay?",
                 "Each one warns you or shows something over the game. Untick what you don't need.",
                 "Each helper's switch and options: Overlay › Helpers. Beta helpers still have rough edges.")
            cols = tk.Frame(body, bg=P2)
            cols.pack(fill="x")
            from .alerts_page import helper_blurb
            for i, (group, ks) in enumerate(self.HELPER_GROUPS):     # (Overlay › Helpers' groups, two a row, in
                box = tk.Frame(cols, bg=P2)                             # its order: In maps, Play / Trading, Misc)
                box.grid(row=i // 2, column=i % 2, sticky="nw", padx=(0 if i % 2 == 0 else 24, 0),
                         pady=(0 if i < 2 else 8, 0))
                tk.Label(box, text=group.upper(), bg=P2, fg=C["muted"], font=("Segoe UI", 9, "bold"),
                         anchor="w").pack(fill="x", pady=(0, 4))
                for k in ks:
                    r = tk.Frame(box, bg=P2)
                    r.pack(fill="x", pady=(0, 8))
                    ttk.Checkbutton(r, text=self.HELPER_NAMES[k], variable=st["helpers"][k],
                                    style="Card.TCheckbutton").pack(anchor="w")
                    tk.Label(r, text=("Beta · " if k in FEAT.BETA_HELPERS else "") + helper_blurb(k, self.look_key_text()), bg=P2,
                             fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left", wraplength=300).pack(
                        fill="x", padx=(24, 0))
            # GGG policy: the helpers that read the screen need a Read Key - a key just for that (Ctrl+Shift+R as the
            # app comes). Shown here, while one of them is ticked, with Change…; the same setting as Settings › Keybinds.
            from .alerts_page import LOOK_HELPERS
            from .look_page import look_key_problem
            from .style import KeyCapture
            lk = tk.Frame(body, bg=P2)
            lk_top = tk.Frame(lk, bg=P2)
            lk_top.pack(fill="x")
            tk.Label(lk_top, text="Read Key", bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold")).pack(side="left",
                                                                                                    padx=(0, 8))
            st.setdefault("look", tk.StringVar(value=self.look_key()))
            lk_msg = tk.Label(lk, text="", bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                              wraplength=640)

            def look_said(_t=None):
                why = look_key_problem(st["look"].get(), self.look_key_others())
                st["look_bad"] = why
                lk_msg.config(text=("✖ " + why) if why else
                              ("✔ Each press reads the screen once for the helpers you ticked." if st["look"].get()
                               else "○ No Read Key: the helpers above read nothing. Pick a key the game doesn't use."),
                              fg=C["red"] if why else C["muted"])
            kc = KeyCapture(lk_top, st["look"], width=16, on_change=look_said)
            kc.pack(side="left")
            chg = ttk.Button(lk_top, text="Change…", command=kc.start)
            chg.pack(side="left", padx=(8, 0))
            Tooltip(chg, "Press the key you want for the Read Key, one the game doesn't use.")
            Tooltip(kc, "Click, then press the key. Right-click clears it. Settings › Keybinds changes it later.")
            lk_msg.pack(fill="x", pady=(2, 0))
            look_said()

            def look_row(*_a):
                need = any(st["helpers"][k].get() for k in LOOK_HELPERS if k in st["helpers"])
                if need and not lk.winfo_manager():
                    lk.pack(fill="x", pady=(12, 0), before=lr)
                elif not need and lk.winfo_manager():
                    lk.pack_forget()
            for var, tid in getattr(w, "look_traces", []):     # (a screen built before: its row is gone)
                try:
                    var.trace_remove("write", tid)
                except tk.TclError:
                    pass
            w.look_traces = [(st["helpers"][k], st["helpers"][k].trace_add("write", look_row))
                             for k in LOOK_HELPERS if k in st["helpers"]]
            w.look_capture = kc
            from .merged_page import LAYOUTS
            from .style import SegBar
            lr = tk.Frame(body, bg=P2)
            lr.pack(fill="x", pady=(12, 0))
            look_row()
            tk.Label(lr, text="Layout", bg=P2, fg=C["text"], font=("Segoe UI", 10, "bold")).pack(side="left",
                                                                                                padx=(0, 8))

            def pick(v):
                st["layout"] = next((k for k, t in LAYOUTS.items() if t == v), "xpbar")
            seg = SegBar(lr, list(LAYOUTS.values()), value=LAYOUTS.get(st["layout"], LAYOUTS["xpbar"]),
                         command=pick, size=9, pad=(16, 4))
            seg.pack(side="left")
            li = tk.Label(lr, text="ⓘ", bg=P2, fg=C["muted"], font=("Segoe UI", 9), cursor="question_arrow")
            li.pack(side="left", padx=8)
            Tooltip(li, "Bar: rests on the game's XP bar. Panel: a card you place anywhere. Split: two halves by the "
                        "orbs. Overlay › Appearance changes it.")
            w.seg_layout = seg
            back.pack(side="right", padx=(0, 8), before=nxt)
            back.config(command=lambda: go(1))
            nxt.config(text="Next", command=lambda: go(3))

        def window_screen():
            """The last question: the Drawer (suggested for one monitor) or a Full window (two or more). Done applies
            it."""
            clear()
            k = self.drawer_key_label()
            head(total(), total(), "How should the app sit with the game?",
                 "The Drawer is a panel over the side of the game that one key shows and puts away. A Full window is "
                 "a normal window.",
                 "Change it any time: Settings › General › Window. The key: Settings › Keybinds.")
            for val, name, what in (("drawer", "Drawer — suggested for one monitor", "A panel over the side of "
                                     "the game. The game keeps the keyboard when a price check opens it."),
                                    ("full", "Full window — suggested for two or more monitors",
                                     "The app as a normal window, where you left it.")):
                r = tk.Frame(body, bg=P2)
                r.pack(fill="x", pady=(0, 8))
                ttk.Radiobutton(r, text=name, value=val, variable=st["shape"], style="Card.TRadiobutton").pack(anchor="w")
                tk.Label(r, text=what, bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                         wraplength=600).pack(fill="x", padx=(24, 0))
            tk.Label(body, text=(f"{k} · check it's free in your game's keybinds · change it in Settings › Keybinds"
                                 if k else "Set a Drawer key in Settings › Keybinds to use the Drawer."),
                     bg=P2, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left", wraplength=640).pack(
                fill="x", pady=(8, 0))
            back.pack(side="right", padx=(0, 8), before=nxt)
            back.config(command=lambda: go(2 if st["overlay"].get() == "yes" else 1))
            nxt.config(text="Done", command=done)

        screens = (features_screen, overlay_screen, helpers_screen, window_screen)

        def go(i):
            st["step"] = i
            if st["feats"]:                              # (screen 1's ticks kept while it isn't built)
                st["feats"] = {k: values(v) for k, v in st["feats"].items()}
            screens[i]()
            fit()

        def apply(feats, overlay, helpers, layout, shape="drawer"):
            lv = st.get("look")
            if overlay and lv is not None and lv.get().strip() != self.look_key() and not st.get("look_bad"):
                self.look_key_save(lv.get())                    # (the Read Key asked on the helpers step)
            for k, v in feats.items():
                FEAT.set_on(k, bool(v))
            FEAT.set_on("overlay", bool(overlay))
            SETTINGS["features_asked"] = "done"
            save_json("settings.json", SETTINGS)
            self.features_apply()
            if overlay:
                for k, v in helpers.items():                     # (only a change: turning one on starts it)
                    if bool(v) != self.helper_switch_on(k):
                        try:
                            self.alerts_toggle(k, bool(v))
                        except Exception:
                            buglog.caught()
                from .merged_page import LAYOUTS
                if layout in LAYOUTS and layout != self.merged_layout():
                    try:
                        self.merged_set(layout=layout)
                    except Exception:
                        buglog.caught()
            self.features_close(w, answered=True)
            self._say("Saved. Change these any time: Settings › General › Features and Overlay › Helpers.", 8)
            try:
                self.drawer_setup_pick(shape)              # (the last screen: the Drawer or a Full window)
            except Exception:
                buglog.caught()
            if first:
                self.root.after(600, self.setup_then_ask)

        def values(v):
            return v.get() if hasattr(v, "get") else v

        def done():
            feats = {k: values(v) for k, v in (st["feats"] or {}).items()}
            apply(feats, st["overlay"].get() == "yes", {k: v.get() for k, v in st["helpers"].items()}, st["layout"],
                  st["shape"].get())

        def defaults():
            apply({k: True for k in feat_keys}, True, {k: True for k in st["helpers"]}, "xpbar", st["shape"].get())
        skip.bind("<Button-1>", lambda _e: defaults())

        def fit():
            try:
                from .style import center_over
                center_over(w, self.root)
            except Exception:
                buglog.caught()
        w.setup_go, w.setup_done, w.setup_skip, w.setup_state = go, done, defaults, st
        w.setup_next, w.setup_back, w.setup_skip_link = nxt, back, skip
        go(0)
        self.popup_over_app(w)
        return w

    def setup_then_ask(self):
        """After the start-up Setup: Community data sharing, its own question (one at a time; Error reports are
        asked at a later start - er_start)."""
        try:
            from . import board as BRD
            if not BRD.configured():
                return None
            if not self.cm_asked():
                return self.cm_ask()
            if self.cm_sharing():
                return self.cm_name_ask()
        except Exception:
            buglog.caught()
        return None

    def ask_unrated_set(self, on):
        """2.131.2: Ask me about mods I haven't rated - one switch (Settings › Price checking)."""
        SETTINGS["ask_unrated"] = bool(on)
        save_json("settings.json", SETTINGS)
        v = getattr(self, "ask_unrated_var", None)
        if v is not None and bool(v.get()) != bool(on):
            v.set(bool(on))
        rec = getattr(self, "shown_rec", None)
        if rec is not None:
            try:
                self.show_detail(rec)
            except Exception:
                buglog.caught()

    def popup_over_app(self, w):
        """2.131.1 (feedback: the picker got lost behind the app): Windows itself keeps it above the app's window, and
        it's on top when the app is (Settings › Always on top) - like the app's own pages."""
        try:
            from .shell import DeskWindow
            w.shell = self.shell
            DeskWindow.own_by_app(w)
            DeskWindow.follow_on_top(w)
            w.lift()
            w.focus_force()
        except Exception:
            buglog.caught()

    def features_close(self, w, answered=False):
        try:
            if w.winfo_exists():
                w.destroy()
        except tk.TclError:
            pass
        self.feat_win = None

    # ---------------------------------------------------------------- Settings › Advanced › Data folder: Change…
    def data_dir_change(self):
        from tkinter import messagebox
        d = filedialog.askdirectory(parent=self.dlg_parent(), title="Where should StashOfExile2 keep your data?")
        if not d:
            return None
        from .config import move_data
        ok, note = move_data(d)
        self._say(note, 10)
        if ok and messagebox.askyesno("Restart now?", note + "\n\nRestart now?", parent=self.dlg_parent()):
            self.restart_app()
        return ok
