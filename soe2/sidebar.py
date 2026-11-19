"""The sidebar (2.62.0): every tool as a line of text down the left, grouped, child tools indented under their
parent with "↳", the open one marked in the theme's style; Settings at the bottom. Clicking a line
opens that tool as the page (one page at a time).

GGG ToS: looks only - nothing here touches the game."""
import tkinter as tk

from . import gearicon
from .gearicon import GEAR
from . import buglog
from . import newchip
from . import themes as TH
from .style import C, Tooltip

WIDE, NARROW = 232, 52                 # wide: icon + name; narrow (small app window): icons only
RAIL = 96                              # drawer-look: the Drawer's rail - a bigger icon with its short name under it
# UI overhaul: grouped by what you want to do. Page keys per group; a page not named here goes under Tools.
# Nav phase 1: Overlay sits under Dashboard with no group (was "In Game"); the "Earn" group is gone (Wealth and Craft
# Helper to Stash, the rest to League); Bulk Pricing, Favorites and Rate Mods are their own rows in Trade (they were
# children of Price Checks); Regex to Stash; the dead "notes" entry is gone (Notes is an overlay part).
# Owner (Rate Mods redesign): a Mods group between Trade and Stash - Rate Mods, Insights and Craft Helper all answer
# one question, which mods are worth money.
GROUPS = ((None, ("dashboard", "tracker")),
          ("Trade", ("pricecheck", "checks", "favorites", "rates")),
          ("Mods", ("ratemods", "insights", "crafthelper")),
          ("Stash", ("wealth", "regex")),
          ("League", ("plan", "mapprofit", "money", "maps", "leaderboards")),
          ("Tools", ("search",)))
NO_GROUP = ("settings",)               # pages that live outside the groups (Settings sits at the bottom)


def group_of(key):
    """The sidebar group a page's row is in: its GROUPS label, "" for a page with no group (Dashboard, Overlay,
    Settings), "Tools" for a page not named in GROUPS (the sidebar lists those under Tools)."""
    if key in NO_GROUP:
        return ""
    for label, keys in GROUPS:
        if key in keys:
            return label or ""
    return "Tools"


class Sidebar(tk.Canvas):
    def __init__(self, shell, parent):
        super().__init__(parent, width=WIDE, highlightthickness=0, bd=0, bg=C["panel2"])
        self.shell = shell
        self.hover, self.compact, self._rows = None, False, []
        self.folded = set()                    # 2.65.0: open tools folded shut by a click
        self._tip = Tooltip(self, "", delay=350)  # D3: the rail has icons only - a real tip beside the row
        TH.self_painted(self)
        TH.subscribe(lambda t: self.redraw(), owner=self)
        newchip.listen(lambda: self.winfo_exists() and self.redraw())     # 3.0.0: a NEW chip went
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(ev, self.rail_wheel, add="+")

    # ---- what is listed
    def items(self):
        """Rows top to bottom. 2.65.0: only the tools at first; the open one unfolds to show what's under it - its
        child tools and its tabs (2.64.0: {"tab": title, "of": key, "depth"}). A click on the open one folds it."""
        sh = self.shell
        act = sh.active
        chain, k = [], act                         # 2.74.0: the open tool and every tool above it (Mod book is
        while k and k not in chain:                # under Under the hood, under Price checks)
            chain.append(k)
            k = getattr(sh.modules.get(k), "parent", None)
        out = [{"key": "_goto", "title": "Go to anything", "icon": "⌕"}]     # UI overhaul: Ctrl+K, first

        def tabs(m, depth):
            if self.compact or m.key != act:
                return
            for t in sh.tab_titles(m.key):
                out.append({"key": f"{m.key}::{t}", "tab": t, "of": m.key, "depth": depth})
        named = {k for _, keys in GROUPS for k in keys}
        listed = [m for m in sh.modules.values() if sh.listed(m) and getattr(m, "kind", "") != "core"]
        for label, keys in GROUPS:
            mods = [m for k in keys for m in listed if m.key == k]
            if label == "Tools":
                mods += [m for m in listed if m.key not in named]
            if not mods:
                continue
            if label:
                out.append({"group": label})
            def kids(p, depth):
                for c in sh.children(p):
                    out.append({"key": c.key, "mod": c, "child": True, "depth": depth})
                    if c.key in self.folded:
                        continue
                    tabs(c, depth + 1)
                    if c.key in chain:
                        kids(c.key, depth + 1)
            for m in mods:
                out.append({"key": m.key, "mod": m})
                if m.key not in chain or m.key in self.folded:
                    continue
                tabs(m, 1)
                kids(m.key, 1)
        return out

    def _chain(self):
        chain, k = [], self.shell.active
        while k and k not in chain:
            chain.append(k)
            k = getattr(self.shell.modules.get(k), "parent", None)
        return chain

    def has_more(self, key):
        """Does this tool unfold (child tools or tabs)?"""
        return bool(self.shell.children(key) or self.shell.tab_titles(key))

    def set_compact(self, on):
        if on != self.compact:
            self.compact = on
            self.configure(width=self.rail_width() if on else WIDE)
            self.redraw()

    def rail_width(self):
        look = getattr(self.shell.app, "drawer_look_on", None)
        try:
            return RAIL if look and look() else NARROW
        except Exception:
            return NARROW

    def rail_label(self, k):
        """The short name under a rail icon: the page's name; a long one (over 13 letters) its short name, as the
        dock's tiles do. Go to anything and Settings keep theirs."""
        if k == "_goto":
            return "Go to anything"
        if k == "_update":
            return "Update"
        mod = self.shell.modules.get(k)
        if mod is None:
            return ""
        t = mod.title
        return (getattr(mod, "short", "") or t) if len(t) > 13 else t

    # ---- mouse
    def _hit(self, y):
        return next((k for k, y0, y1 in self._rows if y0 <= y < y1), None)

    def _motion(self, e):
        self._set_hover(self._hit(e.y))

    def _set_hover(self, k):
        if k != self.hover:
            self.hover = k
            self.configure(cursor="hand2" if k else "")
            self.redraw()
            mod = self.shell.modules.get(k)
            if k == "_update" and self.update_tag():
                from .config import pretty_version
                self.shell.app._say(f"Version {self.update_tag()} is out - you have {pretty_version()}. Click to see "
                                    "what's new and update. It asks first.", 6)
            self._rail_tip(k)
            if k == "_goto":
                self.shell.app._say("Find any page, setting or helper (Ctrl+K).", 4)
            if mod is not None and getattr(mod, "blurb", ""):
                self.shell.app._say(f"{mod.title}: {mod.blurb}", 4)

    def rail_text(self, k):
        """The words for a rail icon: "Trade › Price Checks" (a page's group, then its name)."""
        sh = self.shell
        if k == "_goto":
            return "Go to anything (Ctrl+K)"
        if k == "_update":
            return f"Update to {self.update_tag()}" if self.update_tag() else "Update"
        mod = sh.modules.get(k)
        if mod is None:
            return ""
        top, seen = k, set()
        while getattr(sh.modules.get(top), "parent", None) and top not in seen:
            seen.add(top)
            top = sh.modules[top].parent
        grp = group_of(top)
        name = f"{grp} \u203a {mod.title}" if grp else mod.title
        new = newchip.page_tip(k)                            # 3.0.0: "NEW: Read Key, Drawer"
        return f"{name}  ·  {new}" if new else name

    def _rail_tip(self, k):
        """D3: in the rail, hovering a row shows its name beside it (the status line alone is no tip)."""
        tip = self._tip
        tip._leave()
        if not (k and self.compact):
            return
        row = next((r for r in self._rows if r[0] == k), None)
        text = self.rail_text(k)
        if not row or not text:
            return
        tip.text = text
        tip.at = (self.winfo_rootx() + self.winfo_width() + 2, self.winfo_rooty() + row[1] + 2)
        tip._enter()

    def _click(self, e):
        k = self._hit(e.y)
        if k == "_goto":
            self.shell.goto()
        elif k == "_update":                                  # 2.74.2: see what's new and update (it asks first)
            self.shell.app.check_updates("ask")
        elif k and "::" in k:                                  # one of a page's tabs
            key, title = k.split("::", 1)
            self.shell.open_tab(key, title)
        elif k:
            sh = self.shell
            home = sh.tab_home(k)
            on_own = sh.active == k and (not home or sh.tab_current(k) == home)
            if on_own and k != "settings" and self.has_more(k):  # already on its own page: fold / unfold
                self.folded.symmetric_difference_update({k})
                self.redraw()
                return
            self.folded.discard(k)                               # else its own page (from a child or a tab)
            if home:                                             # its own page (Regex: Build a search)
                sh.open_tab(k, home)
            else:
                sh.open(k)

    # ---- drawing (the theme's own nav style: bar, glow, pill, gem, bracket, arrow, step)
    def redraw(self):
        with TH.raw():
            self._redraw()

    def rail_look(self):
        """The Drawer's own rail (mockups.html .rail): line icons in the theme's sidebar - only in the Drawer shape."""
        look = getattr(self.shell.app, "drawer_look_on", None)
        try:
            return bool(self.compact and look and look())
        except Exception:
            return False

    def _redraw_rail(self, t):
        """drawer-look (mockups.html, owner: the icons on the left bar were too small to make out): each page a big
        line icon with its short name under it - a touch-sized row; Settings at the bottom. The
        rows scroll with the wheel when the window is short. Every row keeps its tip beside it (_rail_tip: "Trade ›
        Price Checks"). Round 18 (feedback: everything blended together): the theme's own sidebar - its surface and
        texture, the group names (TRADE, STASH ...) in its group color, and the open page on its selection color with
        the marker in its accent at the left edge (a mark, not color alone) and its icon and name lit."""
        from . import lineicons
        w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        if w != self.rail_width() and int(float(str(self.cget("width")))) != self.rail_width():
            self.configure(width=self.rail_width())
        nav = t.part("nav") or {}
        bg = t.c(nav.get("bg", "surface_raised")) if t.id != TH.IDENTITY else C["panel2"]
        line = t.c("border")
        acc = t.c(nav.get("marker_color", "accent")) if nav.get("marker_color") else C["accent"]
        sel_bg = t.c(nav.get("sel_bg", "selection"))
        hov_bg = t.c(nav.get("hover_bg", "surface_high"))
        txt, sel_txt = t.c(nav.get("text", "text")), t.c(nav.get("sel_text", "text_strong"))
        grp = t.c(nav.get("group", "text_muted"))
        mut = t.c("text_muted")
        self.configure(bg=bg)
        if nav.get("texture", "none") not in ("none", None):
            TH.texture(self, t, nav["texture"], 0, 0, w, h, bg,
                       glow=t.c(nav["texture_color"]) if nav.get("texture_color") else None)
        self._rows, self._imgs = [], []
        active, chain = self.shell.active, self._chain()
        gap, y0 = 2, 8 - getattr(self, "_rail_top", 0)
        x0, x1 = 4, w - 5
        font = ("Segoe UI", 9)

        def row(k, y):
            sel = k == active or (k in chain and k != "_goto")
            hov = k == self.hover
            col = sel_txt if sel else txt if hov else mut
            lab = self.create_text((x0 + x1) // 2, y + 30, text=self.rail_label(k), anchor="n",
                                   font=(font[0], font[1], "bold" if sel else "normal"), fill=col,
                                   width=x1 - x0 - 2, justify="center", tags=("lab",))
            bb = self.bbox(lab) or (0, y, 0, y + 46)
            y1 = bb[3] + 6
            if sel or hov:
                rr = TH.round_rect(self, x0, y, x1, y1, 6, fill=sel_bg if sel else hov_bg, outline="")
                self.tag_lower(rr, lab)
            if sel:
                self.create_rectangle(0, y + 6, 3, y1 - 6, fill=acc, outline="")
            icol = acc if sel else col
            if k == "settings":                              # (the app's one gear - gearicon, as everywhere else)
                img = gearicon.image(self, 20, icol)
            else:
                img = lineicons.icon(self, lineicons.PAGE_ICON.get(k, "dot"), 22, icol)
            if img is not None:
                self._imgs.append(img)
                self.create_image((x0 + x1) // 2, y + 17, image=img)
            if newchip.page_new(k):                          # 3.0.0: the NEW chip by the icon's top right
                newchip.draw(self, x1 - 3, y + 8, acc, ink_on(acc), size=7)
            self._rows.append((k, y, y1))
            return y1
        upd = self.update_tag()
        bottom = (["_update"] if upd else []) + ["settings"]
        y = y0
        for it in self.items():
            if "group" in it:
                if it["group"]:
                    self.create_text(w // 2, y + 9, text=it["group"].upper(), anchor="center",
                                     font=("Segoe UI", 9, "bold"), fill=grp)
                    y += 18
                else:
                    self.create_line((w - 32) // 2, y + 6, (w + 32) // 2, y + 6, fill=line)
                    y += 13
                continue
            if "tab" in it or it.get("child"):
                continue
            y = row(it["key"], y) + gap
        need = y + getattr(self, "_rail_top", 0) + len(bottom) * 54 + 16
        self._rail_more = max(0, need - h)                  # (a short window: the rows scroll)
        y = max(y + 8, h - len(bottom) * 54 - 8) if not self._rail_more else y + 8
        self.create_line((w - 32) // 2, y - 4, (w + 32) // 2, y - 4, fill=line)
        for k in bottom:
            y = row(k, y) + gap
        self.create_line(w - 1, 0, w - 1, h, fill=line)

    def rail_wheel(self, e):
        """The rail's rows scroll with the wheel when they don't all fit (a short game window)."""
        if not self.rail_look() or not getattr(self, "_rail_more", 0):
            return
        d = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
        self._rail_top = max(0, min(self._rail_more, getattr(self, "_rail_top", 0) + d * 60))
        self.redraw()

    def _redraw(self):
        t = TH.ST.theme
        if t is None:
            return
        self.delete("all")
        if self.rail_look():
            return self._redraw_rail(t)
        want = NARROW if self.compact else WIDE                # (back from the Drawer's wider rail)
        if int(float(str(self.cget("width")))) != want:
            self.configure(width=want)
        nav = t.part("nav") or {}
        w, h = max(self.winfo_width(), 2), max(self.winfo_height(), 2)
        bg = t.c(nav.get("bg", "surface_raised")) if t.id != TH.IDENTITY else C["panel2"]
        self.configure(bg=bg)
        if nav.get("texture", "none") not in ("none", None):
            TH.texture(self, t, nav["texture"], 0, 0, w, h, bg,
                       glow=t.c(nav["texture_color"]) if nav.get("texture_color") else None)
        self.create_line(w - 1, 0, w - 1, h, fill=C["line"])
        acc = t.c(nav.get("marker_color", "accent")) if nav.get("marker_color") else C["accent"]
        sel_bg = t.c(nav.get("sel_bg", "selection"))
        hov_bg = t.c(nav.get("hover_bg", "surface_high"))
        txt, sel_txt = t.c(nav.get("text", "text")), t.c(nav.get("sel_text", "text_strong"))
        grp = t.c(nav.get("group", "text_muted"))
        mk = nav.get("marker", "bar")
        rh, y = 30, 8
        self._rows = []
        active = self.shell.active
        rows = self.items()
        upd = self.update_tag()                           # 2.74.2: a new version - above Settings
        bottom = ([{"key": "_update", "title": f"Update to {upd}", "icon": "⬆"}] if upd else []) + \
            [{"key": "settings", "title": "Settings", "icon": GEAR}]   # (UI overhaul: no Toolkit row - Go to anything
                                                                         # lists every page; Settings › About has the rest)
        for it in rows + [{"group": None}] + bottom:
            if "group" in it:
                if it["group"] is None:                       # the bottom: (Update,) Settings
                    y = max(y + 8, h - len(bottom) * (rh + 2) - 12)
                    self.create_line(10, y, w - 10, y, fill=C["line"])
                    y += 8
                    continue
                if self.compact:
                    self.create_line(10, y + 6, w - 10, y + 6, fill=C["line"])
                    y += 12
                    continue
                y += 6
                self.create_text(14, y + 8, text=it["group"].upper(), anchor="w", font=("Segoe UI", 8, "bold"), fill=grp)
                y += 22
                continue
            k = it["key"]
            if k == "_goto":
                y = self._goto_row(y, w, t)
                continue
            if k == "_update":
                y = self._update_row(y, w, rh, acc, t)
                continue
            if "tab" in it:                                    # 2.64.0: a page's tab, under it
                y = self._tab_row(it, y, w, mk, acc, sel_bg, bg, hov_bg, txt, sel_txt, grp, t, nav)
                continue
            mod = it.get("mod")
            title = mod.title if mod is not None else it["title"]
            icon = mod.icon if mod is not None else it["icon"]
            if it.get("child") and not self.compact:           # UI overhaul: a page under a page - on the rail
                y = self._nested_row(k, title, it.get("depth", 1), y, w, acc, sel_bg, hov_bg, txt, sel_txt, grp, t,
                                     sel=(k == active and not (k not in self.folded and self.shell.tab_current(k)
                                                               in self.shell.tab_titles(k))),
                                     more=mod is not None and bool(self.shell.children(k)) and self.has_more(k))
                continue
            y0, y1 = y, y + rh
            x0, x1 = (6, w - 6) if not self.compact else (4, w - 4)
            on_tab = (mod is not None and not self.compact and k not in self.folded
                      and self.shell.tab_current(k) in self.shell.tab_titles(k))
            sel = k == active and not on_tab
            if sel:
                self._marker(mk, x0, y0, x1, y1, acc, sel_bg, bg)
            elif k == self.hover:
                if mk == "pill":
                    TH.round_rect(self, x0, y0 + 1, x1, y1 - 1, 4, fill=hov_bg, outline=t.c(nav.get("hover_border", "border")))
                else:
                    self.create_rectangle(x0, y0, x1, y1, fill=hov_bg, outline="")
            cy = (y0 + y1) // 2
            opened = on_tab and k == active                    # its tab carries the marker; the page name is bold
            fg = sel_txt if sel or opened else txt
            fresh = not it.get("child") and newchip.page_new(k)     # 3.0.0: a new feature lives here
            if self.compact:
                if icon == GEAR:                               # (drawn: the ⚙ glyph looked like a flower)
                    gearicon.draw(self, (x0 + x1) // 2, cy, 16, fg)
                else:
                    self.create_text((x0 + x1) // 2, cy, text=icon, font=("Segoe UI Emoji", 12), fill=fg)
                if fresh:                                      # (the word NEW, never a dot of color alone)
                    newchip.draw(self, x1, y0 + 5, acc, ink_on(acc), size=6)
            else:
                ind = 14 * it.get("depth", 1) if it.get("child") else 0
                if it.get("child"):
                    self.create_text(x0 + ind - 4, cy, text="↳", anchor="w", font=("Segoe UI", 9), fill=grp)
                if icon == GEAR:
                    gearicon.draw(self, x0 + 12 + ind + (6 if mk == "gem" else 0), cy, 16, fg, anchor="w")
                else:
                    self.create_text(x0 + 12 + ind + (6 if mk == "gem" else 0), cy, text=icon, anchor="w",
                                     font=("Segoe UI Emoji", 12 if not it.get("child") else 10), fill=fg)
                self.create_text(x0 + 40 + ind, cy, text=title, anchor="w", fill=fg,
                                 font=("Segoe UI", 10 if not it.get("child") else 9, "bold" if sel or opened else "normal"))
                more = mod is not None and (not it.get("child") or self.shell.children(k)) and self.has_more(k)
                if more:                                       # 2.65.0: ▸ folded / ▾ open
                    unfolded = k in self._chain() and k not in self.folded
                    self.create_text(x1 - 4, cy, text="▾" if unfolded else "▸", anchor="e", fill=grp,
                                     font=("Segoe UI Symbol", 9))
                    x1 -= 14
                if fresh:                                      # 3.0.0: NEW until opened (then BETA, if it is)
                    newchip.draw(self, x1 - 6, cy, acc, ink_on(acc))
                elif mod is not None and getattr(mod, "kind", "") == "utility" and not it.get("child"):
                    st = None
                    try:
                        st = mod.status() if hasattr(mod, "status") else None
                    except Exception:
                        buglog.caught()
                    col = C["green"] if st is True else C["orange"] if st == "warn" else C["muted"]
                    mark = "✓" if st is True else "!" if st == "warn" else "–"      # (never color alone)
                    self.create_text(x1 - 12, cy, text=mark, font=("Segoe UI Symbol", 9, "bold"), fill=col)
                elif mod is not None and _beta(mod):
                    self.create_text(x1 - 6, cy, text="BETA", anchor="e", font=("Segoe UI", 7, "bold"), fill=acc)
            self._rows.append((k, y0, y1))
            y = y1 + 2

    def _goto_row(self, y, w, t):
        """UI overhaul: the Go to anything box at the top of the sidebar (opens the Ctrl+K box)."""
        x0, x1 = (8, w - 8) if not self.compact else (6, w - 6)
        y0, y1 = y + 4, y + 40
        hov = self.hover == "_goto"
        TH.round_rect(self, x0, y0, x1, y1, 8, fill=t.c("surface_sunken"),
                      outline=t.c("border_light") if hov else t.c("border"))
        cy = (y0 + y1) // 2
        mut = t.c("text_muted")
        if self.compact:
            self.create_text((x0 + x1) // 2, cy, text="⌕", font=("Segoe UI Symbol", 12), fill=mut)
        else:
            self.create_text(x0 + 12, cy, text="⌕", anchor="w", font=("Segoe UI Symbol", 11), fill=mut)
            self.create_text(x0 + 32, cy, text="Go to anything", anchor="w", font=("Segoe UI", 9), fill=mut)
            self.create_text(x1 - 10, cy, text="Ctrl K", anchor="e", font=("Segoe UI", 8), fill=mut)
        self._rows.append(("_goto", y0, y1))
        return y1 + 12

    def update_tag(self):
        """2.74.2: the newer version the quiet check found (feedback_page), or None."""
        tag = getattr(self.shell.app, "upd_latest", None)
        if not tag:
            return None
        from .config import pretty_version
        return pretty_version(tag)

    def _update_row(self, y, w, rh, acc, t):
        """A new version: a filled row in the accent color (it was a badge on the bottom bar)."""
        x0, x1 = (6, w - 6) if not self.compact else (4, w - 4)
        y0, y1 = y, y + rh
        hov = self.hover == "_update"
        fill = TH.mix(acc, "#ffffff", .15) if hov else acc
        TH.round_rect(self, x0, y0 + 1, x1, y1 - 1, 4, fill=fill, outline=acc)
        cy = (y0 + y1) // 2
        ink = "#1a1206"
        if self.compact:
            self.create_text((x0 + x1) // 2, cy, text="⬆", font=("Segoe UI Symbol", 12, "bold"), fill=ink)
        else:
            self.create_text(x0 + 12, cy, text="⬆", anchor="w", font=("Segoe UI Symbol", 11, "bold"), fill=ink)
            self.create_text(x0 + 40, cy, text=f"Update to {self.update_tag()}", anchor="w", fill=ink,
                             font=("Segoe UI", 10, "bold"))
        self._rows.append(("_update", y0, y1))
        return y1 + 2

    def _tab_row(self, it, y, w, mk, acc, sel_bg, bg, hov_bg, txt, sel_txt, grp, t, nav):
        sel = self.shell.active == it["of"] and self.shell.tab_current(it["of"]) == it["tab"]
        return self._nested_row(it["key"], it["tab"], it["depth"], y, w, acc, sel_bg, hov_bg, txt, sel_txt, grp, t,
                                sel=sel)

    def _nested_row(self, k, title, depth, y, w, acc, sel_bg, hov_bg, txt, sel_txt, grp, t, sel=False, more=False):
        """UI overhaul: a page's own parts and the pages under it, the same way - a thin rail under the parent's icon,
        the name lined up with the parent's name; the open one has a mark on the rail, bold text and a filled row."""
        rh = 26
        y0, y1 = y, y + rh
        x0, x1 = 6, w - 6
        rail = x0 + 19 + 14 * (depth - 1)
        tx = x0 + 40 + 14 * (depth - 1)
        if sel or k == self.hover:
            self.create_rectangle(rail + 6, y0 + 1, x1, y1 - 1, fill=sel_bg if sel else hov_bg, outline="")
        self.create_line(rail, y0 - 2, rail, y1 + 2, fill=t.c("border"))
        if sel:
            self.create_rectangle(rail - 1, y0 + 5, rail + 2, y1 - 5, fill=acc, outline="")
        self.create_text(tx, (y0 + y1) // 2, text=title, anchor="w", fill=sel_txt if sel else txt,
                         font=("Segoe UI", 9, "bold" if sel else "normal"))
        if more:
            unfolded = k in self._chain() and k not in self.folded
            self.create_text(x1 - 4, (y0 + y1) // 2, text="▾" if unfolded else "▸", anchor="e", fill=grp,
                             font=("Segoe UI Symbol", 9))
        self._rows.append((k, y0, y1))
        return y1

    def _marker(self, mk, x0, y0, x1, y1, acc, sbg, bg):
        draw_marker(self, mk, x0, y0, x1, y1, acc, sbg, bg)


def ink_on(color):
    """Dark or light words on a filled chip of this color (the NEW chip on the rail)."""
    try:
        c = color.lstrip("#")
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        return "#1a1206" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"
    except (ValueError, AttributeError):
        return "#1a1206"


def _beta(mod):
    from .shell import is_beta
    return is_beta(mod)


def draw_marker(cv, mk, x0, y0, x1, y1, acc, sbg, bg):
    """The selected page's marker in the nav (bar, pill, glow, gem, bracket, arrow, step). 2.118.0: a function, so
    the theme picker's preview draws the very same one."""
    mix = TH.mix
    if mk == "pill":
        TH.round_rect(cv, x0, y0 + 1, x1, y1 - 1, 4, fill=sbg, outline=acc)
        cv.create_line(x0 + 4, y0 + 2, x1 - 4, y0 + 2, fill=mix(sbg, "#ffffff", .6))
    elif mk == "glow":
        for i in range(x1 - x0):
            cv.create_line(x0 + i, y0, x0 + i, y1, fill=mix(mix(acc, sbg, .45), bg, (i / (x1 - x0)) ** .7))
        cv.create_line(x0, y0, x0, y1, fill=mix(acc, "#ffffff", .3), width=2)
    elif mk == "gem":
        for i in range(x1 - x0):
            cv.create_line(x0 + i, y0, x0 + i, y1, fill=mix(sbg, bg, i / (x1 - x0)))
        cy = (y0 + y1) // 2
        cv.create_polygon(x0 + 6, cy - 5, x0 + 11, cy, x0 + 6, cy + 5, x0 + 1, cy, fill=acc,
                            outline=mix(acc, "#000000", .55))
    elif mk == "bracket":
        cv.create_rectangle(x0, y0, x1, y1, fill=sbg, outline="")
        n = 6
        cv.create_line(x0 + n, y0, x0, y0 + n, x0, y1 - n, x0 + n, y1, fill=acc, width=2)
        cv.create_line(x1 - n, y0, x1, y0 + n, x1, y1 - n, x1 - n, y1, fill=acc, width=2)
    elif mk == "arrow":
        cv.create_rectangle(x0, y0, x1, y1, fill=sbg, outline="")
        my = y1 - 3
        cv.create_line(x0 + 6, my, x1 - 12, my, fill=mix(acc, sbg, .3))
        cv.create_polygon(x1 - 12, my - 4, x1 - 3, my, x1 - 12, my + 4, fill=acc, outline="")
    elif mk == "step":
        cv.create_rectangle(x0, y0, x1, y1, fill=sbg, outline="")
        cv.create_polygon(x0, y0 + 2, x0 + 3, y0 + 2, x0 + 3, y0 + 6, x0 + 6, y0 + 6, x0 + 6, y1 - 6,
                            x0 + 3, y1 - 6, x0 + 3, y1 - 2, x0, y1 - 2, fill=acc, outline="")
    else:                                                  # bar
        cv.create_rectangle(x0, y0, x1, y1, fill=sbg, outline="")
        for i in range(24):
            cv.create_line(x0 + 3 + i, y0, x0 + 3 + i, y1, fill=mix(acc, sbg, .6 + .4 * i / 24))
        cv.create_rectangle(x0, y0, x0 + 3, y1, fill=acc, outline="")
