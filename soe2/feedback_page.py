"""The update badge and Report a bug (2.48.0), both on the taskbar so they're there whatever window you're in.
2.74.2: a new version shows in the sidebar instead, above Toolkit and Settings (the taskbar badge is for no sidebar).

Update badge: a quiet look at GitHub's latest release a little after start and every hour. A newer version puts
"⬆ Update x.y.z" on the taskbar; clicking it is the same as Settings > Updates > Check for updates (asks before
downloading). It never downloads by itself (that's still the Settings option).

Report a bug: a small form - what happened, how to make it happen, what you expected - and, if you tick it, the app's
log (2.115.0: buglog.diagnostics - the last crash / freeze / slow report and the newest errors, cleaned).
You see exactly what will be sent. It goes to the community board server (board/), which opens a GitHub issue with
its own token (the app holds none) and tells Discord. If the board can't take it, GitHub's
"new issue" page opens in your browser with everything filled in.

Suggest a Feature (3.2.0, owner): the same way for an idea - a small form (the idea, how it would help, a name to be
credited by if it ships, all but the idea optional), every word shown before it's sent, an [Idea] issue on GitHub."""
import platform
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import ttk

from . import buglog
from . import board as B
from .config import APP_VERSION, SETTINGS
from .style import C, Tooltip, over_app

REPO = "StashOfExile/StashOfExile2"
UPDATE_EVERY = 3600                 # 2.79.1 (feedback): every hour (was 6 h)



CLEAN_MSG = "Please keep it clean"          # the board's answer to a refused word - board/src/index.js textProblem
SETUP_LABEL = "Add your screen setup"
SETUP_LINE = "Screen size, scaling, HDR, the game window's mode and the last missed inventory read."
SETUP_TIP = ("Helps with bugs where the app doesn't read your screen. It comes from Windows' display settings and "
             "the game window's size. Nothing is read from the game or its files, and no picture is taken or sent. "
             "Untick it to leave it out. The box below shows it word for word.")


def os_line():
    """3.0.6 (bug reports say the OS and the version): "Windows 11" / "Windows 10", or on Linux the distro
    family, the desktop and the session ("Linux (arch) · Hyprland · wayland") - never a build number or user name."""
    import sys
    if sys.platform == "win32":
        try:
            build = int((platform.version() or "0").split(".")[-1])
        except ValueError:
            build = 0
        return "Windows 11" if build >= 22000 else f"Windows {platform.release()}"
    if sys.platform.startswith("linux"):
        try:
            from . import linsys
            d = linsys.distro() or "?"
            return f"Linux ({d}) · {linsys.desktop() or '?'} · {linsys.session_type() or '?'}"
        except Exception:
            return "Linux"
    return platform.system() or "?"

class FeedbackPage:
    """Mixed into App."""

    # ================================================================ taskbar
    def build_feedback(self):
        tb = "#111b30"
        self.upd_badge = tk.Label(self.shell.task_right, text="", bg=C["accent"], fg="#1a1206", padx=8, pady=4,
                                  cursor="hand2", font=("Segoe UI", 9, "bold"))
        self.upd_badge.bind("<Button-1>", lambda e: self.check_updates("ask"))
        self.bug_btn = tk.Label(self.shell.task_right, text="🐞 Report a bug", bg=tb, fg="#cfdaf0", padx=8, pady=4,
                                cursor="hand2", font=("Segoe UI", 9), highlightthickness=1,
                                highlightbackground="#3d5582")
        self.bug_btn.pack(in_=self.shell.task_right, side="left", padx=4, before=self.league_chip)
        self.bug_btn.bind("<Button-1>", lambda e: self.bug_report_open())
        self.idea_btn = tk.Label(self.shell.task_right, text="💡 Suggest a Feature", bg=tb, fg="#cfdaf0", padx=8,
                                 pady=4, cursor="hand2", font=("Segoe UI", 9), highlightthickness=1,
                                 highlightbackground="#3d5582")
        self.idea_btn.pack(in_=self.shell.task_right, side="left", padx=4, before=self.bug_btn)
        self.idea_btn.bind("<Button-1>", lambda e: self.idea_open())
        self.upd_latest = None
        self.root.after(15000, self.quiet_update_check)

    def quiet_update_check(self):
        """Every hour: is there a newer release? Shows the badge. 2.100.0 (feedback): it follows Preview builds (it
        only ever looked at full releases, so with previews on it never found one), and with Settings' update
        switches on, a newer version also gets a card - Install now, or it installs when the app next starts."""
        from .config import SETTINGS

        def work():
            from .updates import latest_release
            try:
                kind, data = latest_release()
            except Exception:
                kind, data = "error", {}
            self.ui_q.put(("update_badge", data.get("tag_name") if kind == "ok" else None))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(UPDATE_EVERY * 1000, self.quiet_update_check)

    def update_found(self, tag):
        """A check during the session found a newer version: a card once per version (when an update switch is on)."""
        from .config import SETTINGS, pretty_version
        if getattr(self, "_upd_told", None) == tag or getattr(self, "_upd_busy", False):
            return False
        if not (SETTINGS.get("auto_update") or SETTINGS.get("auto_check_updates")):
            return False
        self._upd_told = tag
        later = "Later" if not SETTINGS.get("auto_update") else "When I next start the app"
        self.info_card(f"Version {pretty_version(tag)} is out - you have {pretty_version()}.",
                       [("Install now", lambda: self.check_updates("ask")), (later, lambda: None)], secs=120)
        return True

    def ev_update_badge(self, tag):
        from .updates import is_newer
        from .config import pretty_version
        sb = getattr(self.shell, "sidebar", None)
        if tag and is_newer(tag, APP_VERSION):
            self.upd_latest = tag
            try:
                self.update_found(tag)
            except Exception:
                buglog.caught()
            self.upd_badge.config(text=f"⬆ Update {pretty_version(tag)}")
            if sb is not None:                               # 2.74.2: in the sidebar, above Settings
                sb.redraw()
                return
            if not self.upd_badge.winfo_ismapped():
                self.upd_badge.pack(in_=self.shell.task_right, side="left", padx=4,
                                    before=getattr(self, "idea_btn", None) or self.bug_btn)
            from .style import Tooltip
            Tooltip(self.upd_badge, f"Version {pretty_version(tag)} is out - you have {pretty_version()}. Click to see "
                                    "what's new and update. It asks first.")
        else:
            self.upd_latest = None
            self.upd_badge.pack_forget()
            if sb is not None:
                sb.redraw()

    # ================================================================ Report a bug
    def bug_report_text(self, what, steps, expected, contact, with_log, with_setup=False):
        """Exactly what is sent, shown in the form before you send it. with_setup: 3.2.0, the screen setup part."""
        from .privacy import public_league, scrub_names
        try:
            sh = self.root.winfo_screenheight()
        except tk.TclError:
            sh = 0
        parts = [f"**What happened**\n{what.strip()}"]
        if steps.strip():
            parts.append(f"**How to make it happen**\n{steps.strip()}")
        if expected.strip():
            parts.append(f"**What I expected**\n{expected.strip()}")
        # 2.89.3: no exact Windows build or screen size (they help pick one person out); a private league's name stays here
        res = "4K" if sh >= 2000 else "1440p" if sh >= 1400 else "1080p" if sh >= 1000 else "under 1080p" if sh else "?"
        parts.append(f"**App** {APP_VERSION} · {os_line()} · {res} · "
                     f"league {public_league(SETTINGS.get('league')) or '?'}")
        if with_setup:
            parts.append(getattr(self, "bug_setup", "") or "**Screen setup**\nReading it…")
        if with_log:                                 # 2.115.0: the one log - the last crash / freeze / slow report and
            from . import buglog                     # the newest entries of app_log.txt, cleaned, capped
            parts.append(buglog.diagnostics() or "**App log**\n(nothing logged - no errors, crashes or freezes)")
        return scrub_names("\n\n".join(parts))      # 2.89.3: every word - your names / paths never reach the issue

    def bug_report_open(self, title="", what=""):
        """title / what (2.115.0): filled in for you - the "app closed by itself" message's Report it."""
        P1, P2 = C["panel"], C["panel2"]
        if getattr(self, "bug_win", None) is not None:
            try:
                self.bug_win.lift()
                return self.bug_win
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        over_app(win, self.dlg_parent())               # 2.114.3: over the app, on its monitor
        win.title("Report a bug")
        win.configure(bg=P1)
        win.transient(self.root)
        win.geometry("640x660")
        win.minsize(520, 560)
        self.bug_win = win
        win.protocol("WM_DELETE_WINDOW", self._bug_close)
        f = tk.Frame(win, bg=P1, padx=16, pady=12)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Report a bug", bg=P1, fg=C["accent"], font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(f, text="It becomes an issue on GitHub (StashOfExile/StashOfExile2), and the developer is told on Discord. "
                         "Your account and character names and your Windows user name are taken out - below is exactly "
                         "what goes, word for word. It's public: don't paste whispers or chat.", bg=P1,
                 fg=C["muted"], font=("Segoe UI", 9), wraplength=600, justify="left", anchor="w").pack(fill="x",
                                                                                                       pady=(2, 8))
        self.bug_vars = {}

        def field(key, label, h=0):
            tk.Label(f, text=label, bg=P1, fg=C["text"], anchor="w").pack(fill="x", pady=(4, 2))
            if h:
                t = tk.Text(f, height=h, bg=P2, fg=C["text"], insertbackground=C["text"], relief="flat",
                            highlightthickness=1, highlightbackground=C["line"], wrap="word", font=("Segoe UI", 9))
                t.pack(fill="x")
                t.bind("<KeyRelease>", lambda e: self._bug_preview())
                # 2.50.0: Tab moves on to the next box (in a text box it typed a tab character)
                t.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[1])
                t.bind("<Shift-Tab>", lambda e: (e.widget.tk_focusPrev().focus_set(), "break")[1])
                self.bug_vars[key] = t
            else:
                v = tk.StringVar()
                ttk.Entry(f, textvariable=v).pack(fill="x")
                v.trace_add("write", lambda *a: self._bug_preview())
                self.bug_vars[key] = v
        field("title", "The title, in a few words")
        field("what", "What happened?", 3)
        field("steps", "How can it be made to happen? Steps, optional", 3)
        field("expected", "What did you expect? (optional)", 2)
        self.bug_log = tk.BooleanVar(value=True)
        from . import buglog                         # 2.115.0: what the log holds, said plainly
        n = buglog.counts()
        seen = ", ".join(f"{v} {k}{'es' if k == 'crash' and v != 1 else 's' if v != 1 else ''}"
                         for k, v in sorted(n.items()) if v) or "nothing"
        ttk.Checkbutton(f, text="Add the app's log: errors, crashes, freezes - code locations only. Helps a lot",
                        variable=self.bug_log, command=self._bug_preview).pack(anchor="w", pady=(8, 0))
        tk.Label(f, text=f"In the last week: {seen}.", bg=P1, fg=C["muted"], font=("Segoe UI", 9),
                 anchor="w").pack(fill="x", padx=(24, 0), pady=(0, 4))
        self.bug_setup_on = tk.BooleanVar(value=True)      # 3.2.0 owner: the screen setup, shown before Send
        srow = tk.Frame(f, bg=P1)
        srow.pack(fill="x")
        ttk.Checkbutton(srow, text=SETUP_LABEL, variable=self.bug_setup_on,
                        command=self._bug_preview).pack(side="left")
        si = tk.Label(srow, text="ⓘ", bg=P1, fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow")
        si.pack(side="left", padx=(8, 0))
        Tooltip(si, SETUP_TIP)
        tk.Label(f, text=SETUP_LINE, bg=P1, fg=C["muted"], font=("Segoe UI", 9),
                 anchor="w").pack(fill="x", padx=(24, 0), pady=(0, 4))
        self.bug_setup = ""
        b = tk.Frame(f, bg=P1)                   # 2.50.0: the buttons first, at the bottom - never cut off
        b.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Label(f, text="What will be sent", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(fill="x")
        self.bug_prev = tk.Text(f, height=6, bg=C["bg"], fg=C["muted"], relief="flat", wrap="word",
                                font=("Consolas", 9), highlightthickness=1, highlightbackground=C["line"],
                                takefocus=0)
        self.bug_prev.pack(fill="both", expand=True)
        self.bug_msg = tk.Label(b, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                                wraplength=380)
        self.bug_msg.pack(side="left", fill="x", expand=True)
        self.bug_send_btn = ttk.Button(b, text="Send", style="Primary.TButton", command=self.bug_send)
        self.bug_send_btn.pack(side="right")
        ttk.Button(b, text="Cancel", style="Quiet.TButton", command=self._bug_close).pack(side="right", padx=(0, 8))
        if title:
            self.bug_vars["title"].set(title)
        if what:
            self.bug_vars["what"].insert("1.0", what)
        self._bug_preview()
        self._bug_setup_read()
        return win

    def _bug_close(self):
        w, self.bug_win = getattr(self, "bug_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _bug_val(self, key):
        v = self.bug_vars[key]
        return v.get("1.0", "end-1c") if isinstance(v, tk.Text) else v.get()

    def _bug_ready(self):
        """3.0.6 (Send appeared to do nothing - the title or the text was too short and the red line went unseen):
        Send stays gray, and the line under it says what's still needed, until both are long enough."""
        need = []
        if len(self._bug_val("title").strip()) < 4:
            need.append("a title of 4+ letters")
        if len(self._bug_val("what").strip()) < 10:
            need.append("10+ letters on what happened")
        try:
            if getattr(self, "bug_send_btn", None) is not None and str(self.bug_send_btn.cget("text")) == "Send":
                self.bug_send_btn.config(state="disabled" if need else "normal")
            if getattr(self, "bug_msg", None) is not None and self.bug_msg.cget("fg") != C["orange"]:
                self.bug_msg.config(text=("Still needed: " + " and ".join(need) + ".") if need else "",
                                    fg=C["muted"])
        except tk.TclError:
            pass
        return not need

    def _bug_preview(self):
        if getattr(self, "bug_win", None) is None:
            return
        self._bug_ready()
        text = self.bug_report_text(self._bug_val("what"), self._bug_val("steps"), self._bug_val("expected"), "",
                                    self.bug_log.get(), self._bug_setup_wanted())
        self.bug_prev.config(state="normal")
        self.bug_prev.delete("1.0", "end")
        self.bug_prev.insert("1.0", f"[Bug] {self._bug_val('title').strip()}\n\n{text}")
        self.bug_prev.config(state="disabled")

    def _bug_setup_wanted(self):
        v = getattr(self, "bug_setup_on", None)
        return bool(v.get()) if v is not None else False

    def _bug_setup_read(self):
        """The screen setup, read once as the form opens - off the window thread, then the preview shows it."""
        from . import sysinfo
        root = self.root

        def done(t):
            self.bug_setup = t or ""
            self._bug_preview()
        self.run_bg(lambda: sysinfo.report_part(root), done)

    def bug_send(self):
        title, what = self._bug_val("title").strip(), self._bug_val("what").strip()
        if len(title) < 4 or len(what) < 10:
            self.bug_msg.config(text="A title and a few words about what happened, please.", fg=C["red"])
            return None
        body = self.bug_report_text(what, self._bug_val("steps"), self._bug_val("expected"), "", self.bug_log.get(),
                                    self._bug_setup_wanted())
        self.bug_send_btn.config(state="disabled")
        self.bug_msg.config(text="Sending…", fg=C["muted"])

        def work():
            from .privacy import scrub_names
            return B.call("POST", "/bugs", body={"title": scrub_names(title), "body": body, "version": APP_VERSION})

        def done(res):
            ok, data = res
            if ok and isinstance(data, dict) and data.get("url"):
                self.app_toast(f"Thanks! Your report is issue #{data.get('number')} on GitHub.", "Report a bug",
                               kind="success") if hasattr(self, "app_toast") else None
                self.bug_last = data
                self._bug_close()
                return
            why = data if isinstance(data, str) else ""
            if why.startswith(CLEAN_MSG):            # 3.2.1: a word the board refuses - fix it here, no browser
                if getattr(self, "bug_win", None) is None:
                    return
                self.bug_send_btn.config(state="normal")
                self.bug_msg.config(text=why, fg=C["red"])
                return
            self.bug_browser(title, body, why=why)
        self.run_bg(work, done)

    def bug_browser(self, title, body, why=""):
        """The board couldn't take it: GitHub's new-issue page, filled in (you sign in to GitHub to send it)."""
        url = (f"https://github.com/{REPO}/issues/new?labels=bug&title=" + urllib.parse.quote(f"[Bug] {title}")
               + "&body=" + urllib.parse.quote(body[:6000]))
        self.bug_last = {"url": url, "browser": True}
        try:
            webbrowser.open(url)
        except Exception:
            buglog.caught()
        if getattr(self, "bug_win", None) is not None:
            self.bug_send_btn.config(state="normal")
            self.bug_msg.config(text=("The board couldn't take it" + (f" ({why})" if why else "") + " - GitHub's new "
                                      "issue page opened in your browser with everything filled in: press Submit "
                                      "there."), fg=C["orange"])
        return url

    # ================================================================ Suggest a Feature
    IDEA_INTRO = ("It becomes an idea on GitHub, StashOfExile/StashOfExile2, and the developer is told on Discord. Your "
                  "account and character names and your Windows user name are taken out. Below is exactly what goes, "
                  "word for word. It's public.")
    IDEA_CREDIT = "If your idea ships, What's new and the README thank you by this name. Leave it empty for no credit."

    def idea_text(self, what, why, credit):
        """Exactly what is sent, shown in the form before you send it."""
        from .privacy import scrub_names
        parts = [f"**The idea**\n{what.strip()}"]
        if why.strip():
            parts.append(f"**How it would help**\n{why.strip()}")
        if credit.strip():
            parts.append(f"**Credit me as** {credit.strip()[:40]}")
        parts.append(f"**App** {APP_VERSION} · {os_line()}")
        return scrub_names("\n\n".join(parts))

    def idea_open(self):
        P1, P2 = C["panel"], C["panel2"]
        if getattr(self, "idea_win", None) is not None:
            try:
                self.idea_win.lift()
                return self.idea_win
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        win.withdraw()                                  # (built hidden, shown once: no flicker)
        over_app(win, self.dlg_parent())
        win.title("Suggest a Feature")
        win.configure(bg=P1)
        win.transient(self.root)
        win.geometry("640x620")
        win.minsize(520, 520)
        self.idea_win = win
        win.protocol("WM_DELETE_WINDOW", self._idea_close)
        f = tk.Frame(win, bg=P1, padx=16, pady=12)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Suggest a Feature", bg=P1, fg=C["accent"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(f, text=self.IDEA_INTRO, bg=P1, fg=C["muted"], font=("Segoe UI", 9), wraplength=600, justify="left",
                 anchor="w").pack(fill="x", pady=(2, 8))
        self.idea_vars = {}

        def field(key, label, h=0, note=""):
            tk.Label(f, text=label, bg=P1, fg=C["text"], anchor="w").pack(fill="x", pady=(4, 2))
            if h:
                t = tk.Text(f, height=h, bg=P2, fg=C["text"], insertbackground=C["text"], relief="flat",
                            highlightthickness=1, highlightbackground=C["line"], wrap="word", font=("Segoe UI", 9))
                t.pack(fill="x")
                t.bind("<KeyRelease>", lambda e: self._idea_preview())
                t.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[1])
                t.bind("<Shift-Tab>", lambda e: (e.widget.tk_focusPrev().focus_set(), "break")[1])
                self.idea_vars[key] = t
            else:
                v = tk.StringVar()
                ttk.Entry(f, textvariable=v).pack(fill="x")
                v.trace_add("write", lambda *a: self._idea_preview())
                self.idea_vars[key] = v
            if note:
                tk.Label(f, text=note, bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                         wraplength=600).pack(fill="x")
        field("title", "Your idea, in a few words")
        field("what", "What would you like?", 3)
        field("why", "How would it help you? Optional", 2)
        field("credit", "A name to credit you by. Optional", note=self.IDEA_CREDIT)
        b = tk.Frame(f, bg=P1)                          # (the buttons first, at the bottom - never cut off)
        b.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Label(f, text="What will be sent", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w").pack(fill="x",
                                                                                                        pady=(8, 0))
        self.idea_prev = tk.Text(f, height=5, bg=C["bg"], fg=C["muted"], relief="flat", wrap="word",
                                 font=("Consolas", 9), highlightthickness=1, highlightbackground=C["line"],
                                 takefocus=0)
        self.idea_prev.pack(fill="both", expand=True)
        self.idea_msg = tk.Label(b, text="", bg=P1, fg=C["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                                 wraplength=380)
        self.idea_msg.pack(side="left", fill="x", expand=True)
        self.idea_send_btn = ttk.Button(b, text="Send", style="Primary.TButton", command=self.idea_send)
        self.idea_send_btn.pack(side="right")
        ttk.Button(b, text="Cancel", style="Quiet.TButton", command=self._idea_close).pack(side="right", padx=(0, 8))
        self._idea_preview()
        win.deiconify()
        return win

    def _idea_close(self):
        w, self.idea_win = getattr(self, "idea_win", None), None
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _idea_val(self, key):
        v = self.idea_vars[key]
        return v.get("1.0", "end-1c") if isinstance(v, tk.Text) else v.get()

    def _idea_ready(self):
        """Send stays gray, and the line beside it says what's still needed, until the title and the idea are there."""
        need = []
        if len(self._idea_val("title").strip()) < 4:
            need.append("a title of 4+ letters")
        if len(self._idea_val("what").strip()) < 10:
            need.append("10+ letters on your idea")
        try:
            if str(self.idea_send_btn.cget("text")) == "Send":
                self.idea_send_btn.config(state="disabled" if need else "normal")
            if self.idea_msg.cget("fg") != C["orange"]:
                self.idea_msg.config(text=("Still needed: " + " and ".join(need) + ".") if need else "", fg=C["muted"])
        except (tk.TclError, AttributeError):
            pass
        return not need

    def _idea_preview(self):
        if getattr(self, "idea_win", None) is None or getattr(self, "idea_prev", None) is None:
            return
        self._idea_ready()
        text = self.idea_text(self._idea_val("what"), self._idea_val("why"), self._idea_val("credit"))
        self.idea_prev.config(state="normal")
        self.idea_prev.delete("1.0", "end")
        self.idea_prev.insert("1.0", f"[Idea] {self._idea_val('title').strip()}\n\n{text}")
        self.idea_prev.config(state="disabled")

    def idea_send(self):
        if not self._idea_ready():
            return None
        title = self._idea_val("title").strip()
        body = self.idea_text(self._idea_val("what"), self._idea_val("why"), self._idea_val("credit"))
        self.idea_send_btn.config(state="disabled")
        self.idea_msg.config(text="Sending…", fg=C["muted"])

        def work():
            from .privacy import scrub_names
            return B.call("POST", "/bugs", body={"kind": "idea", "title": scrub_names(title), "body": body,
                                                 "version": APP_VERSION})

        def done(res):
            ok, data = res
            if ok and isinstance(data, dict) and data.get("url"):
                if hasattr(self, "app_toast"):
                    self.app_toast(f"Thanks! Your idea is #{data.get('number')} on GitHub.", "Suggest a Feature",
                                   kind="success")
                self.idea_last = data
                self._idea_close()
                return
            why = data if isinstance(data, str) else ""
            if why.startswith(CLEAN_MSG):
                if getattr(self, "idea_win", None) is None:
                    return
                self.idea_send_btn.config(state="normal")
                self.idea_msg.config(text=why, fg=C["red"])
                return
            self.idea_browser(title, body, why=why)
        self.run_bg(work, done)

    def idea_browser(self, title, body, why=""):
        """The board couldn't take it: GitHub's new-issue page, filled in. You sign in to GitHub to send it."""
        url = (f"https://github.com/{REPO}/issues/new?labels=enhancement&title=" + urllib.parse.quote(f"[Idea] {title}")
               + "&body=" + urllib.parse.quote(body[:6000]))
        self.idea_last = {"url": url, "browser": True}
        try:
            webbrowser.open(url)
        except Exception:
            buglog.caught()
        if getattr(self, "idea_win", None) is not None:
            self.idea_send_btn.config(state="normal")
            self.idea_msg.config(text="The board couldn't take it" + (f": {why}." if why else ".") + " GitHub's new "
                                      "issue page opened in your browser with everything filled in. Press Submit "
                                      "there.", fg=C["orange"])
        return url
