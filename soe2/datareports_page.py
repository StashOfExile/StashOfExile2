"""3.3.0 owner: Report a Problem on every Codex page, and the admins' Reports list. The data side is datareports.py.

Every Codex page header has Report a Problem: it reports the row picked on that page. Rows also have it on their
right-click menu. Admins get a Reports link in the same header, with how many wait. Hide leaves the row out of Game
Search and Mod Lab for every user at once; on Map Library and Under the Hood a fix comes with the next update."""
import time
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import datareports as DR
from .style import C, over_app

PULL_SECS = 1800


class DataReportsPage:
    # ---------------------------------------------------------------- start
    def dr_start(self):
        self.dr_n = 0
        try:
            self.root.after(9000, self.dr_tick)
        except tk.TclError:
            pass

    def dr_tick(self):
        try:
            self.dr_pull()
        except Exception:
            buglog.caught()
        try:
            self.root.after(PULL_SECS * 1000, self.dr_tick)
        except tk.TclError:
            pass

    def dr_is_admin(self):
        try:
            return bool(self.share_is_admin())
        except Exception:
            return False

    def dr_pull(self):
        """Rows an admin hid, for every user; for an admin also how many reports wait."""
        before = {p: DR.hidden(p) for p in DR.HIDE_WORKS}

        def done(got):
            if got is not None and any(DR.hidden(p) != before[p] for p in DR.HIDE_WORKS):
                self.dr_applied()
        self.run_bg(DR.pull, done)
        if self.dr_is_admin():
            self.run_bg(DR.reports, lambda res: self.dr_count_set(
                sum(1 for r in res[1] if r["status"] == "open") if res and res[0] else getattr(self, "dr_n", 0)))

    def dr_count_set(self, n):
        self.dr_n = max(0, int(n or 0))
        sh = getattr(self, "shell", None)
        for key in DR.PAGES:
            w = getattr(sh, "windows", {}).get(key) if sh else None
            bar = getattr(w, "bar", None)
            if bar is not None and hasattr(bar, "redraw"):
                try:
                    bar.redraw()
                except Exception:
                    buglog.caught()

    def dr_count(self):
        return int(getattr(self, "dr_n", 0) or 0) if self.dr_is_admin() else 0

    def dr_applied(self):
        """Hidden rows changed: Game Search and Mod Lab read their rows again."""
        try:
            from . import gamesearch
            gamesearch.forget()
            if getattr(self, "gs_cards", None) is not None:
                self.gs_render(keep_scroll=True)
        except Exception:
            buglog.caught()
        try:
            self.__dict__.pop("_rm_ent", None)
            if getattr(self, "rm_page", None) is not None:
                self._rm_recount_all()
                self.rm_load(keep=True)
        except Exception:
            buglog.caught()

    # ---------------------------------------------------------------- what is picked on each page
    def dr_context(self, page):
        """(ref, item, line) of the row picked on a Codex page, or None."""
        try:
            fn = getattr(self, f"_dr_ctx_{page}", None)
            return fn() if fn else None
        except Exception:
            buglog.caught()
            return None

    def _dr_ctx_ratemods(self):
        e = None
        if getattr(self, "rm_view", "") == "Table" and getattr(self, "rm_tpick", None):
            e = next((x for x in self.rm_entries(self.rm_set) if tuple(x["keys"]) == tuple(self.rm_tpick)), None)
        e = e or self.rm_current()
        if not e:
            return None
        return e["keys"][0], getattr(self, "rm_set_label", ""), e.get("text") or ""

    def _dr_ctx_maps(self):
        sel = list(self.ml_tv.selection()) if getattr(self, "ml_tv", None) is not None else []
        return (sel[0], sel[0], "") if sel else None

    def _dr_ctx_library(self):
        for tv, kind in ((getattr(self, "lib_stats", None), "stat"), (getattr(self, "lib_tree", None), "base")):
            if tv is None or not tv.winfo_ismapped():
                continue
            sel = tv.selection()
            if not sel:
                continue
            text = tv.item(sel[0], "text") or (tv.item(sel[0], "values") or [""])[0]
            if text:
                return f"{kind}:{text}", str(text), ""
        return None

    # ---------------------------------------------------------------- the report box
    def dr_report_page(self, page):
        """The header's Report a Problem: the row picked on that page."""
        ctx = self.dr_context(page)
        if not ctx:
            from tkinter import messagebox
            tip = "Right-click a result, then Report a Problem." if page == "search" else \
                "Pick a row on this page first, then click Report a Problem. You can also right-click a row."
            messagebox.showinfo("Report a Problem", tip, parent=self.dlg_parent())
            return None
        return self.dr_report(page, *ctx)

    def dr_report(self, page, ref, item="", line=""):
        P2 = C["panel2"]
        dlg = tk.Toplevel(self.root)
        over_app(dlg, self.dlg_parent())
        dlg.title("Report a Problem")
        dlg.configure(bg=P2, padx=16, pady=12)
        dlg.transient(self.root)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        tk.Label(dlg, text="An admin looks at each report. A wrong row can be hidden for everyone.", bg=P2,
                 fg=C["muted"], justify="left", wraplength=420).pack(anchor="w", pady=(0, 8))
        kv = tk.Frame(dlg, bg=P2)
        kv.pack(fill="x")
        for i, (k, v) in enumerate((("Page", DR.PAGES.get(page, page)), ("Item", item), ("Line", line))):
            if not v:
                continue
            tk.Label(kv, text=k, bg=P2, fg=C["muted"]).grid(row=i, column=0, sticky="nw", padx=(0, 12), pady=2)
            tk.Label(kv, text=v, bg=P2, fg=C["text"], justify="left", wraplength=360).grid(row=i, column=1, sticky="w",
                                                                                         pady=2)
        tk.Label(dlg, text="What is wrong", bg=P2, fg=C["text"]).pack(anchor="w", pady=(8, 2))
        kind = tk.StringVar(value="")
        for k, words in DR.KINDS:
            ttk.Radiobutton(dlg, text=words, value=k, variable=kind).pack(anchor="w")
        tk.Label(dlg, text="Note, if it helps", bg=P2, fg=C["text"]).pack(anchor="w", pady=(8, 2))
        note = tk.StringVar()
        ent = ttk.Entry(dlg, textvariable=note, width=56)
        ent.pack(fill="x")
        msg = tk.Label(dlg, text="", bg=P2, fg=C["red"], anchor="w", justify="left", wraplength=420)
        msg.pack(fill="x", pady=(8, 0))

        def send():
            if not kind.get():
                return msg.config(text="Pick what is wrong.", fg=C["red"])
            b = DR.body(page, ref, kind.get(), item, line, note.get())
            if isinstance(b, str):
                return msg.config(text=b, fg=C["red"])
            msg.config(text="Sending…", fg=C["muted"])

            def done(res):
                ok, why = res if isinstance(res, tuple) else (False, "The board did not answer.")
                if not dlg.winfo_exists():
                    return
                if not ok:
                    return msg.config(text=str(why), fg=C["red"])
                dlg.destroy()
                say = getattr(self, "_say", None)
                if say:
                    say("✓ Report sent. Thank you.", 5)
            self.run_bg(lambda: DR.send(page, ref, kind.get(), item, line, note.get()), done)
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Send", style="Primary.TButton", command=send).pack(side="right")
        ttk.Button(row, text="Cancel", command=dlg.destroy).pack(side="right", padx=(0, 8))
        dlg.bind("<Return>", lambda e: send())
        try:
            dlg.grab_set()
        except tk.TclError:
            pass
        dlg.dr_send, dlg.dr_vars = send, {"kind": kind, "note": note, "msg": msg}
        return dlg

    # ---------------------------------------------------------------- admins: the Reports list
    def dr_reports(self):
        if not self.dr_is_admin():
            return None
        P2 = C["panel2"]
        dlg = tk.Toplevel(self.root)
        over_app(dlg, self.dlg_parent())
        dlg.title("Reports")
        dlg.configure(bg=P2, padx=16, pady=12)
        dlg.transient(self.root)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        tk.Label(dlg, text="Hide leaves the row out for every user at once, on Game Search and Mod Lab. On Map Library "
                           "and Under the Hood, fix it in the next update and mark it Fixed.", bg=P2, fg=C["muted"],
                 justify="left", wraplength=760).pack(anchor="w", pady=(0, 8))
        cols = (("page", "Page", 110), ("item", "Item", 150), ("line", "Line", 260), ("kind", "What", 90),
                ("n", "Reports", 70), ("status", "Status", 80), ("note", "Note", 220))
        tv = ttk.Treeview(dlg, columns=[c for c, _t, _w in cols], show="headings", selectmode="browse", height=12)
        for c, t, w in cols:
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor="w", stretch=c in ("line", "note"))
        tv.pack(fill="both", expand=True)
        msg = tk.Label(dlg, text="Loading…", bg=P2, fg=C["muted"], anchor="w")
        msg.pack(fill="x", pady=(8, 8))
        rows = {}
        btns = {}

        def picked():
            sel = tv.selection()
            return rows.get(sel[0]) if sel else None

        def greys(_e=None):
            r = picked()
            for a, b in btns.items():
                on = bool(r) and (a == "reopen") == (r["status"] == "hidden") if a in ("hide", "reopen") else bool(r)
                b.state(["!disabled"] if on else ["disabled"])

        def fill(res):
            if not dlg.winfo_exists():
                return
            tv.delete(*tv.get_children())
            rows.clear()
            ok, got = res if isinstance(res, tuple) else (False, "The board did not answer.")
            if not ok:
                msg.config(text=str(got), fg=C["red"])
                return greys()
            for r in got:
                rows[str(r["id"])] = r
                status = "● Hidden" if r["status"] == "hidden" else "Open"
                tv.insert("", "end", iid=str(r["id"]), values=(DR.PAGES.get(r["page"], r["page"]), r["item"], r["line"],
                                                              DR.KIND_WORD.get(r["kind"], r["kind"]), r["n"], status,
                                                              r["note"]))
            n_open = sum(1 for r in got if r["status"] == "open")
            self.dr_count_set(n_open)
            msg.config(fg=C["muted"], text=f"{n_open} open. Pick one." if got else "No reports. Nothing waits.")
            greys()

        def load():
            msg.config(text="Loading…", fg=C["muted"])
            self.run_bg(DR.reports, fill)

        def do(action):
            r = picked()
            if not r:
                return

            def after(res):
                ok, why = res if isinstance(res, tuple) else (False, "")
                if not ok and dlg.winfo_exists():
                    return msg.config(text=str(why), fg=C["red"])
                self.dr_pull()
                load()
            self.run_bg(lambda: DR.act(r["id"], action), after)
        row = tk.Frame(dlg, bg=P2)
        row.pack(fill="x")
        from .style import Tooltip
        for a, text, tip, primary in (("hide", "Hide", "Leaves this row out for every user", True),
                                      ("fixed", "Fixed", "It is put right in the data", False),
                                      ("dismiss", "Dismiss", "Nothing is wrong", False),
                                      ("reopen", "Show Again", "Brings a hidden row back", False)):
            b = btns[a] = ttk.Button(row, text=text, width=0, style="Primary.TButton" if primary else "TButton",
                                     command=lambda a=a: do(a))
            b.pack(side="left", padx=(0, 8))
            Tooltip(b, tip)
        ttk.Button(row, text="Close", width=0, command=dlg.destroy).pack(side="right")
        tv.bind("<<TreeviewSelect>>", greys)
        greys()
        load()
        dlg.dr_parts = {"tv": tv, "msg": msg, "btns": btns, "do": do, "rows": rows}
        return dlg
