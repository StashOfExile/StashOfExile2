"""Exchange rates > Exchange Helper: Compare a currency - pick one and see what one of it is worth in every other
currency, worked out from the poe.ninja rates the app already has. No requests and no routes: a price list
in another currency."""
import tkinter as tk
from tkinter import ttk

from . import buglog
from . import cxnames as CXN
from .style import C
from .chrome import section as chrome_section


def _n(x):
    if x is None:
        return "-"
    if x >= 100:
        return f"{x:,.0f}"
    if x >= 1:
        return f"{x:,.2f}".rstrip("0").rstrip(".")
    return f"{x:.3g}"


class ExchangePage:
    """Mixed into App."""

    def build_compare(self, page):
        """Compare a currency: pick one and see what one of it is worth in every other currency."""
        from .style import Tooltip
        P2 = C["panel2"]
        cmo, cm = chrome_section(page, "Compare a currency", "Worked out from each currency's divine price on "
                                                             "poe.ninja, the rates the app already has.")
        cmo.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        row = tk.Frame(cm, bg=P2)
        row.pack(fill="x")
        tk.Label(row, text="1", bg=P2, fg=C["text"]).pack(side="left")
        self.cmp_pick = tk.StringVar(value="")
        self.cmp_box = ttk.Combobox(row, textvariable=self.cmp_pick, values=self.cmp_names(), width=30)
        self.cmp_box.pack(side="left", padx=8)
        self.cmp_box.bind("<KeyRelease>", lambda e: self.cmp_filter(), add="+")
        self.cmp_box.bind("<Button-1>", lambda e: self.cmp_box.configure(values=self.cmp_names()), add="+")
        self.cmp_box.bind("<<ComboboxSelected>>", lambda e: self.cmp_draw(), add="+")
        tk.Label(row, text="is worth", bg=P2, fg=C["text"]).pack(side="left")
        self.cmp_note = tk.Label(cm, text="", bg=P2, fg=C["muted"], anchor="w", justify="left")
        self.cmp_note.pack(fill="x", pady=(8, 0))
        box = tk.Frame(cm, bg=P2)
        box.pack(fill="both", expand=True, pady=(8, 0))
        tv = ttk.Treeview(box, columns=("amt", "cur"), show="headings", height=18)
        tv.heading("amt", text="Amount")
        tv.heading("cur", text="Currency")
        tv.column("amt", width=120, anchor="e", stretch=False)
        tv.column("cur", width=320, anchor="w", stretch=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        self.cmp_tv, self.cmp_how = tv, {}
        tip = Tooltip(tv, "")

        def hover(e):
            tip.text = self.cmp_how.get(tv.identify_row(e.y), "")
        tv.bind("<Motion>", hover, add="+")
        self.cmp_pick.trace_add("write", lambda *a: self.cmp_draw())
        self.cmp_draw()

    def cx_name(self, cid):
        n = CXN.item_name(cid)                                 # 2.26.0: game ids -> names (cxnames.json)
        if n:
            return n
        try:
            from .wealth import WPRICES
            for part in (WPRICES.parts or {}).values():
                n = (part.get("names") or {}).get(cid)
                if n:
                    return n
        except Exception:
            buglog.caught()
        return cid.rsplit("/", 1)[-1].replace("-", " ").title()

    # ---- Compare a currency
    def cmp_table(self):
        """{currency id: its worth in divines} and {currency id: its name}, from the rates already loaded."""
        from .rates import RATES
        tbl = {c: v for c, v in (RATES.table or {}).items() if v and v > 0}
        tbl.setdefault("divine", 1.0)
        names = {c: (getattr(RATES, "names", {}) or {}).get(c) or self.cx_name(c) for c in tbl}
        names["divine"] = names.get("divine") or "Divine Orb"
        return tbl, names

    def cmp_names(self):
        """Every currency with a rate, by name, most traded first."""
        from .rates import RATES
        tbl, names = self.cmp_table()
        order = sorted(tbl, key=lambda c: (-(RATES.vol.get(c, 0)), names[c]))
        out, seen = [], set()
        for c in order:
            if names[c].lower() not in seen:
                seen.add(names[c].lower())
                out.append(names[c])
        return out

    def cmp_filter(self):
        """Typing narrows the list to the names that hold what you typed."""
        t = self.cmp_pick.get().strip().lower()
        allv = self.cmp_names()
        self.cmp_box.configure(values=[n for n in allv if t in n.lower()] if t else allv)

    def cmp_draw(self):
        tv = getattr(self, "cmp_tv", None)
        if tv is None:
            return
        tbl, names = self.cmp_table()
        by_name = {n.lower(): c for c, n in names.items()}
        cid = by_name.get(self.cmp_pick.get().strip().lower())
        tv.delete(*tv.get_children())
        self.cmp_how = {}
        if not tbl or len(tbl) < 2:
            self.cmp_note.config(text="No rates yet: set your league.")
            return
        if cid is None:
            self.cmp_note.config(text="Pick a currency to see what one is worth in each of the others.")
            return
        from .rates import RATES
        rows = compare_rows(cid, tbl, names, RATES.vol)
        self.cmp_note.config(text=f"1 {names[cid]} in {len(rows)} other currencies. Hover a row to see how it was "
                                  "worked out.")
        for i, (oc, amt, how) in enumerate(rows):
            iid = tv.insert("", "end", values=(_n(amt), names[oc]), tags=("odd",) if i % 2 else ())
            self.cmp_how[iid] = how
        tv.tag_configure("odd", background=C["odd"])


def compare_rows(cid, tbl, names, vol=None):
    """One of cid in every other currency: [(other id, how many, how it was worked out)], most traded first."""
    me = tbl.get(cid)
    if not me:
        return []
    vol = vol or {}
    out = []
    for oc in sorted((c for c in tbl if c != cid), key=lambda c: (-(vol.get(c, 0)), names.get(c, c))):
        v = tbl[oc]
        amt = me / v
        how = (f"{names.get(cid, cid)} is worth {_w(me)} div and {names.get(oc, oc)} is worth {_w(v)} div on "
               f"poe.ninja. {_w(me)} ÷ {_w(v)} = {_n(amt)}. Worked out through the divine price, so it can differ "
               "a little from a direct trade.")
        out.append((oc, amt, how))
    return out


def _w(v):
    """A worth in divines, short: 0.52, 0.0021, 150."""
    return f"{v:.4g}"
