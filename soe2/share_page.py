"""2.132.6 Shared lists (feedback: let people publish their regexes to the database, and favorites from the
trade site section, like the one-liners; sorting for Official | Community | Mine): the board side of Regex
favorites and trade-site Favorites - the three views, each copy once, Post, Upvote and Tags. Posting needs Community
data sharing and a community name, like strats."""
import tkinter as tk
from tkinter import ttk

from . import board as B
from . import buglog
from .config import load_json
from .style import C

VIEWS = ("Official", "Community", "Mine")
OFFICIAL_KEY = {"regex": "regex", "trade": "trade"}


def view_rows(view, mine, posts, official, key):
    """-> the rows for one view, each copy once: [{"data", "origin" ("mine" / "board" / "official"), "_post", "_i"}].
    mine: your local items; posts: board posts ({"data", ...}); official: the Official list's data; key(data) -> the
    text that makes two copies the same."""
    if view == "Official":
        pool = [{"data": p["data"], "origin": "board", "_post": p} for p in posts if p.get("promoted")] + \
               [{"data": d, "origin": "official"} for d in official]
    elif view == "Community":
        pool = [{"data": p["data"], "origin": "board", "_post": p} for p in posts if not p.get("promoted")]
    else:
        pool = [{"data": d, "origin": "mine", "_i": i} for i, d in enumerate(mine)] + \
               [{"data": p["data"], "origin": "board", "_post": p} for p in posts if p.get("mine")]
    seen, out = set(), []
    for r in pool:
        k = key(r["data"])
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return out


class SharePage:
    """Mixed into App."""

    def share_posts(self, kind):
        return (getattr(self, "_share_posts", {}) or {}).get(kind, [])

    def share_official(self, kind):
        d = getattr(self, "mm_official", None)
        if not isinstance(d, dict) or not d:
            d = load_json("board_official.json", {}) or {}
        return [x for x in d.get(OFFICIAL_KEY[kind]) or [] if isinstance(x, dict)]

    def share_fetch(self, kind, done=None):
        """The board's posts of this kind (in the background), then done()."""
        if not B.configured():
            return False

        def got(res):
            ok, d = res
            if ok and isinstance(d, dict):
                self._share_posts = dict(getattr(self, "_share_posts", {}) or {})
                self._share_posts[kind] = [p for p in d.get("posts") or [] if isinstance(p.get("data"), dict)]
            if done:
                done()
        self.run_bg(lambda: B.posts(kind, "top", limit=100), got)
        return True

    def share_post(self, kind, data, done=None):
        """Post one of yours (asks for sharing and a name first, as strats do)."""
        if not self.cm_need_sharing(lambda: self.share_post(kind, data, done)) or self.mm_need_login("post"):
            return None
        self.run_bg(lambda: B.post(kind, data), lambda r: self._share_result(r, kind, "Posted to the Community board.",
                                                                              done))
        return True

    def share_vote(self, kind, post, done=None):
        if not post:
            self._say("Upvotes are for Community posts.", 5)
            return None
        if self.mm_need_login("upvote"):
            return None
        self.run_bg(lambda: B.vote(post["id"], not post.get("voted")), lambda r: self._share_result(r, kind, None, done))
        return True

    def share_report(self, kind, post, done=None):
        from tkinter import simpledialog
        if not post or self.mm_need_login("report"):
            return None
        why = simpledialog.askstring("Report", "What's wrong with it?", parent=self.root)
        if why is not None:
            self.run_bg(lambda: B.report(post["id"], why), lambda r: self._share_result(r, kind, "Reported - thanks.",
                                                                                       done))

    def _share_result(self, res, kind, text, done):
        ok, d = res
        if not ok:
            self.app_toast(d, "Community")
            return False
        if text:
            self._say(text, 6)
        self.share_fetch(kind, done)
        return True

    # 3.3.0 owner: the two Favorites screens were built apart and did not match. One toolbar builds both: the
    # same rows, the same names, the same order. A page passes only the actions it has.
    TOOL_ORDER = ("main", "open", None, "rename", "tags", "key", "post", None, "take")

    def share_toolbar(self, parent, key, q_var, on_view, actions, q_tip="Search names and tags"):
        """Rows 1 and 2 of a Favorites screen. Row 1: find, then Official | Community | Mine, Undo at the right.
        Row 2: the orange main action, open elsewhere, Rename, Tags, Key, Post, Add to Mine; Delete at the right,
        with the admin's Make Official beside it. actions: {id: (text, command, tip)} with ids from TOOL_ORDER,
        "official" and "delete". -> (frame, the view bar, {id: button})"""
        from .style import SegBar, Tooltip
        from . import cleanguard
        P1 = C["panel"]
        box = tk.Frame(parent, bg=P1, padx=8)
        r1 = tk.Frame(box, bg=P1)
        r1.pack(fill="x", pady=(8, 0))
        tk.Label(r1, text="🔍", bg=P1, fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(0, 4))
        q = ttk.Entry(r1, textvariable=q_var, width=22)
        q.pack(side="left")
        cleanguard.free(q)                                  # a search
        Tooltip(q, q_tip)
        view = SegBar(r1, list(VIEWS), value="Mine", command=lambda v: on_view(), size=10, pad=(12, 4))
        view.pack(side="left", padx=(12, 0))
        self.undo_button(r1, key, side="right")
        r2 = tk.Frame(box, bg=P1)
        r2.pack(fill="x", pady=(8, 8))
        btns = {}

        def add(aid, side="left"):
            text, fn, tip = actions[aid]
            b = ttk.Button(r2, text=text, command=fn, style="Primary.TButton" if aid == "main" else "TButton",
                           width=0)                         # as wide as its words, so the row fits a Drawer
            b.pack(side=side, padx=(0, 8) if side == "left" else (8, 0))
            Tooltip(b, tip)
            b.state(["disabled"])                           # gray until a row that it works on is picked
            btns[aid] = b
            return b
        gap = False
        for aid in self.TOOL_ORDER:
            if aid is None:
                gap = bool(btns)
                continue
            if aid not in actions:
                continue
            if gap:
                tk.Frame(r2, bg=C["line"], width=1).pack(side="left", fill="y", padx=(2, 8), pady=4)
                gap = False
            add(aid)
        if "delete" in actions:
            add("delete", side="right")
        if "official" in actions:                           # packed only for an admin, by share_tool_greys
            text, fn, tip = actions["official"]
            b = btns["official"] = ttk.Button(r2, text=text, command=fn, width=0)
            Tooltip(b, tip)
        try:
            from .style import flowify
            flowify(r2)                                     # too narrow: the row wraps, nothing is cut off
        except Exception:
            buglog.caught()
        return box, view, btns

    def share_tool_greys(self, btns, on, post=None):
        """Gray out what does not work on the picked row. on: {id: bool}. post: the picked board post, for the
        admin's button, which only admins ever see."""
        for aid, b in btns.items():
            if aid == "official":
                continue
            b.state(["!disabled"] if on.get(aid) else ["disabled"])
        ab = btns.get("official")
        if ab is None:
            return
        if self.share_is_admin():
            ab.config(text="Remove from Official" if (post or {}).get("promoted") else "Make Official")
            ab.state(["!disabled"] if post else ["disabled"])
            if not ab.winfo_manager():
                ab.pack(side="right", padx=(8, 0))
        elif ab.winfo_manager():
            ab.pack_forget()

    # 3.3.0 owner: an admin had no way to make a favorite Official
    def share_is_admin(self):
        return bool((B.signed_in() or {}).get("admin"))

    def share_admin(self, kind, post, action, done=None):
        """An admin's promote, unpromote or hide on a board post. The Official list is read again after."""
        if not post or not self.share_is_admin():
            return None
        said = {"promote": "Now Official.", "unpromote": "No longer Official.", "hide": "Hidden from the board."}

        def after(res):
            if self._share_result(res, kind, said.get(action, "Done."), done) and action in ("promote", "unpromote"):
                self.run_bg(B.official, lambda r: (self._mm_official_done(r) if hasattr(self, "_mm_official_done")
                                                   else None, done and done()))
        self.run_bg(lambda: B.admin(post["id"], action), after)
        return True

    def share_can_delete(self, post):
        """Its author or an admin may take a post off the board."""
        return bool(post) and bool(post.get("mine") or self.share_is_admin())

    def share_delete(self, kind, post, done=None):
        """3.3.0 owner: Delete did nothing on a Community favorite, even for an admin. It asks first: a post
        deleted from the board is gone for everyone and cannot be brought back."""
        if not self.share_can_delete(post):
            return None
        from tkinter import messagebox
        name = str((post.get("data") or {}).get("name") or "this post")
        if not messagebox.askyesno("Delete from the board", f"Delete \"{name}\" from the Community board?\n\n"
                                   "It is removed for everyone and cannot be brought back.",
                                   parent=self.dlg_parent() if hasattr(self, "dlg_parent") else self.root):
            return False

        def after(res):
            if self._share_result(res, kind, f"\"{name}\" is deleted from the board.", done):
                self.run_bg(B.official, lambda r: (self._mm_official_done(r) if hasattr(self, "_mm_official_done")
                                                   else None, done and done()))
        self.run_bg(lambda: B.delete(post["id"]), after)
        return True

    def share_admin_actions(self, kind, post, done=None):
        """The admin's lines for a list's right-click menu, or nothing for everyone else."""
        if not post or not self.share_is_admin():
            return []
        up = "unpromote" if post.get("promoted") else "promote"
        return [None, ("Admin: " + ("Remove from Official" if post.get("promoted") else "Make Official"),
                       lambda: self.share_admin(kind, post, up, done), True),
                ("Admin: Hide from the board", lambda: self.share_admin(kind, post, "hide", done), True)]

    def share_tags(self, title, tags, on_save):
        """A window of tag checkboxes (the strats' tag groups) -> on_save([tags])."""
        from . import moneymakers as MM
        w = tk.Toplevel(self.root)
        w.title("Tags")
        w.configure(bg=C["panel"])
        w.transient(self.root)
        P1 = C["panel"]
        tk.Label(w, text=title[:90], bg=P1, fg=C["text"], wraplength=420, justify="left",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 8))
        have, picks = set(tags or []), {}
        box = tk.Frame(w, bg=P1)
        box.pack(fill="both", padx=12, pady=8)
        try:
            groups = MM.tag_groups()
        except Exception:
            buglog.caught()
            groups = dict(MM.TAG_GROUPS)
        for col, (g, names) in enumerate(groups.items()):
            f = tk.Frame(box, bg=P1)
            f.grid(row=0, column=col, sticky="nw", padx=(0, 16))
            tk.Label(f, text=g.upper(), bg=P1, fg=C["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
            for t in names:
                v = tk.BooleanVar(value=t in have)
                picks[t] = v
                ttk.Checkbutton(f, text=t, variable=v).pack(anchor="w")

        def save():
            w.destroy()
            on_save([t for t, v in picks.items() if v.get()])
        btns = tk.Frame(w, bg=P1)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Save", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right", padx=(0, 8))
        self.share_tags_win = w
        return w
