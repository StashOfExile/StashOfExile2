"""2.80.0: Price Checks - one item at a time (feedback: "copy the price checker / item panel into a new panel called
Price Checks ... a display of the items on the trade site"). Your price check key (Ctrl+D since 2.83.1) on an item in game opens it here: the item
card with every filter on the left, the trade site's listings as cards on the right (name band, properties, item
level, requirements, each mod with its tier, price, seller, when it was listed, the item's picture). Ctrl+Alt+C
still adds to Bulk Pricing (the old Price checks page).

The listings are the ones the price search already fetched (trade.RAW_LISTINGS) - no extra request. Pictures come
from the trade site's own image server, cached in %APPDATA%/StashOfExile2/art.
GGG ToS: reads your clipboard after YOUR Ctrl+C (the game copies, the app sends nothing) and the trade site's search
within its limits; nothing is clicked, bought or whispered."""
import hashlib
import os
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import buglog
from .config import APP_UA, P, SETTINGS
from .style import C, Splitter, flowify, trade_icon
from .trade import ago, RAW_LISTINGS, strip_markup

PC_MAX = 20                  # items kept in Recent
ART_PX = 78
RARITY_COL = {"Unique": "unique", "Rare": "rare", "Magic": "magic"}
MOD_KEYS = (("enchantMods", "enchant"), ("implicitMods", "implicit"), ("runeMods", "rune"),
            ("fracturedMods", "fractured"), ("explicitMods", "explicit"), ("desecratedMods", "desecrated"),
            ("craftedMods", "crafted"))


def _clean(x):
    return re.sub(r"\s+", " ", strip_markup(str(x or ""))).strip()


def prop_lines(item):
    """The trade site's properties -> ["Gloves", "Quality: +30%", "Energy Shield: 138"]."""
    out = []
    for p in item.get("properties") or []:
        name, vals = _clean(p.get("name")), [_clean(v[0]) for v in p.get("values") or [] if v]
        if not vals:
            out.append(name)
        elif p.get("displayMode") == 3 and "{0}" in name:
            t = name
            for i, v in enumerate(vals):
                t = t.replace("{%d}" % i, v)
            out.append(t)
        else:
            out.append(f"{name}: {', '.join(vals)}" if name else ", ".join(vals))
    return [x for x in out if x]


def prop_parts(item):
    """2.93.1: the properties as the trade site draws them -> [(label, value, augmented)]: "Energy Shield", "211",
    True when the value is raised by quality / mods (drawn blue). A line without a value: (label, "", False)."""
    out = []
    for p in item.get("properties") or []:
        name = _clean(p.get("name"))
        vals = [v for v in p.get("values") or [] if v]
        if not vals:
            if name:
                out.append((name, "", False))
            continue
        aug = any(len(v) > 1 and v[1] == 1 for v in vals)
        txt = ", ".join(_clean(v[0]) for v in vals)
        if p.get("displayMode") == 3 and "{0}" in name:
            t = name
            for i, v in enumerate(vals):
                t = t.replace("{%d}" % i, _clean(v[0]))
            out.append((t, "", aug))
        else:
            out.append((name, txt, aug))
    return out


def cur_label(cur):
    """A trade-site currency id -> "Divine Orb" (its name when known)."""
    try:
        from .cxnames import item_name
        n = item_name(cur)
    except Exception:
        n = None
    return n or {"divine": "Divine Orb", "exalted": "Exalted Orb", "chaos": "Chaos Orb", "mirror": "Mirror of Kalandra",
                 "annul": "Orb of Annulment", "regal": "Regal Orb", "alch": "Orb of Alchemy",
                 "vaal": "Vaal Orb"}.get(cur, str(cur or "").replace("-", " ").title())


def req_line(item):
    parts = []
    for r in item.get("requirements") or []:
        name, vals = _clean(r.get("name")), [_clean(v[0]) for v in r.get("values") or [] if v]
        if not vals:
            continue
        parts.append(f"Level {vals[0]}" if name.lower() == "level" else f"{vals[0]} {name}")
    return ("Requires: " + ", ".join(parts)) if parts else ""


def _mod_obj(x, kind):
    """2.81.0 (feedback screenshot: mods showed as raw {'description': ...}): one mod as the trade site sends it now -
    {"description", "flags": {"fractured": True ...}, "domain": "rune" / "explicit" / "desecrated" ..., "mods":
    {"tier": "P1", ...} or [...]} -> [(tier, text, kind)]."""
    fl = x.get("flags") or {}
    dom = str(x.get("domain") or "")
    kind = next((k for k in ("fractured", "desecrated", "crafted") if fl.get(k) or dom == k), None) or \
        {"rune": "rune", "implicit": "implicit", "enchant": "enchant"}.get(dom, kind)
    m = x.get("mods")
    if isinstance(m, list):
        m = m[0] if m and isinstance(m[0], dict) else {}
    tier = str((m or {}).get("tier") or "") if isinstance(m, dict) else ""
    out = []
    for part in str(x.get("description") or x.get("text") or "").split("\n"):
        if part.strip():
            out.append((tier, _clean(part), kind))
            tier = ""
    return out


def mod_rows(item):
    """[(tier or "", text, kind)] in the game's order; the tier from the listing's extended data (P1 / S3)."""
    ext = item.get("extended") or {}
    hashes, mods = ext.get("hashes") or {}, ext.get("mods") or {}
    out = []
    for key, kind in MOD_KEYS:
        lines = item.get(key) or []
        hk = {"explicitMods": "explicit", "fracturedMods": "fractured", "desecratedMods": "desecrated",
              "implicitMods": "implicit", "craftedMods": "crafted"}.get(key)
        hl, ml = (hashes.get(hk) or []) if hk else [], (mods.get(hk) or []) if hk else []
        for i, line in enumerate(lines):
            if isinstance(line, dict):                   # 2.81.0: the trade site's mods are objects now
                out.extend(_mod_obj(line, kind))
                continue
            tier = ""
            try:
                idx = (hl[i][1] or [None])[0]
                if idx is not None and idx < len(ml):
                    tier = str(ml[idx].get("tier") or "")
            except (IndexError, TypeError, AttributeError):
                tier = ""
            for part in str(line).split("\n"):
                if part.strip():
                    out.append((tier, _clean(part), kind))
                    tier = ""
    return out


# 3.0.6: the Precursor Tablets' pictures (the trade site's art), shipped so Farming Strategies shows each strat's
# tablet before you price-check one. A picture learned from a listing wins (icons()).
_ART_LOCK = threading.Lock()
TABLET_ICONS = {
    "Breach Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRCcmVhY2giLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/b45b6e660e/PrecursorTabletBreach.png"),
    "Ritual Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRSaXR1YWwiLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/23c5248469/PrecursorTabletRitual.png"),
    "Expedition Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRFeHBlZGl0aW9uIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/1f8dc7fd47/PrecursorTabletExpedition.png"),
    "Irradiated Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRHZW5lcmljIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/4fbc73f060/PrecursorTabletGeneric.png"),
    "Delirium Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXREZWxpcml1bSIsInciOjEsImgiOjEsInNjYWxlIjoxLCJyZWFsbSI6InBvZTIifV0/8c2fac816e/PrecursorTabletDelirium.png"),
    "Abyss Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRBYnlzcyIsInciOjEsImgiOjEsInNjYWxlIjoxLCJyZWFsbSI6InBvZTIifV0/478e9f6ae2/PrecursorTabletAbyss.png"),
    "Temple Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRJbmN1cnNpb24iLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/9beb68ac5d/PrecursorTabletIncursion.png"),
    "Overseer Tablet": (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvUHJlY3Vyc29yVGFibGV0cy9QcmVjdXJzb3JUYWJsZXRCb3NzIiwidyI6MSwiaCI6MSwic2NhbGUiOjEsInJlYWxtIjoicG9lMiJ9XQ/6a422fabb8/PrecursorTabletBoss.png"),
}

# 3.0.6 (owner: the waystone had no picture): the T15 waystone's art, the "Waystone" picture for every tier (a tier's
# own, learned from a listing, wins - art_url)
WAYSTONE_ICON = ("https://web.poecdn.com/gen/image/WzI4LDE0LHsiZiI6IjJESXRlbXMvTWFwcy9FbmRnYW1lTWFwcy9FbmRnYW1lTWFwMTUi"
                 "LCJ3IjoxLCJoIjoxLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/17149586aa/EndgameMap15.png")
BUNDLED_ICONS = {**TABLET_ICONS, "Waystone": WAYSTONE_ICON}
_ICONS = None


_WAY_TIERS = {"key": None, "urls": {}}


def waystone_tier_icons():
    """{tier: picture URL} from the trade site's /data/static list (trade_static.json, downloaded once a day): its
    Waystones group has one entry a tier."""
    try:
        from .config import P, load_json
        path = P("trade_static.json")
        key = os.path.getmtime(path) if os.path.exists(path) else None
        if key != _WAY_TIERS["key"]:
            urls = {}
            for group in (load_json("trade_static.json", {}) or {}).get("result") or []:
                if "waystone" not in f"{group.get('id', '')} {group.get('label', '')}".lower():
                    continue
                for e in group.get("entries") or []:
                    m = re.search(r"(\d+)", f"{e.get('text', '')} {e.get('id', '')}")
                    img = str(e.get("image") or "")
                    if m and img:
                        urls[int(m.group(1))] = img if img.startswith("http") else "https://web.poecdn.com" + img
            _WAY_TIERS.update(key=key, urls=urls)
    except Exception:
        buglog.caught()
    return _WAY_TIERS["urls"]


def art_url(base):
    """The picture for an item base (or a unique's name): its own (learned from listings), else a waystone's tier
    picture (the trade site's static list), else the shipped waystone picture."""
    ic = icons()
    base = str(base or "")
    if ic.get(base):
        return ic[base]
    if base.startswith("Waystone"):
        m = re.search(r"Tier (\d+)", base)
        return (waystone_tier_icons().get(int(m.group(1))) if m else None) or ic.get("Waystone")
    return None


def icons():
    """2.105.0: base -> the trade site's picture of it (learned from listings; Market Insights' cards use it).
    3.0.6: the tablets' pictures ship with the app (TABLET_ICONS) - a learned one wins."""
    global _ICONS
    if _ICONS is None:
        from .config import load_json
        try:
            learned = load_json("icons.json", {}) or {}
            learned = learned if isinstance(learned, dict) else {}
        except Exception:
            learned = {}
        _ICONS = {**BUNDLED_ICONS, **learned}
    return _ICONS


def icon_learn(base, url):
    if not base or not str(url or "").startswith("https://"):
        return
    ic = icons()
    if ic.get(base) != url:
        ic[base] = url
        try:
            from .config import save_json
            save_json("icons.json", {k: v for k, v in ic.items() if BUNDLED_ICONS.get(k) != v})  # (only what was learned)
        except Exception:
            buglog.caught()


def icons_learn(found):
    """Many learned at once ({name: https URL}, e.g. poe.ninja's uniques): icons.json is written once, and only
    when something changed."""
    ic = icons()
    new = {k: v for k, v in (found or {}).items() if k and str(v or "").startswith("https://") and ic.get(k) != v}
    if not new:
        return 0
    ic.update(new)
    try:
        from .config import save_json
        save_json("icons.json", {k: v for k, v in ic.items() if BUNDLED_ICONS.get(k) != v})
    except Exception:
        buglog.caught()
    return len(new)


# Item flags as a mark and a word (never by color alone): on each listing and on the item you priced
FLAG_MARKS = (("corrupted", "⊘", "Corrupted"), ("twice_corrupted", "⊘", "Twice Corrupted"), ("mirrored", "◈", "Mirrored"),
              ("fractured", "◆", "Fractured"), ("desecrated", "✚", "Desecrated"), ("sanctified", "✦", "Sanctified"),
              ("unrevealed", "◌", "Unrevealed"), ("crafted", "✎", "Crafted"), ("cultivated", "❖", "Cultivated Vaal Unique"),
              ("unidentified", "?", "Unidentified"))


def widened_line(rec):
    """Owner (base widening): the card's one line saying how a white / blue base's search widened, or None. The app's card
    and the overlay card (pcpop) both show it."""
    if rec.get("state") != "done" or rec.get("nomatch") or not rec.get("widened"):
        return None
    return "↔ Widened: " + rec["widened"]


BROADEN = "↔ Broaden Search"     # owner: the card's one orange button while an item found too few (names.py)


def broaden_offer(rec):
    """Owner (Broaden Search): the next widening step the card offers ({"next": its words, ...}), or None - an item
    priced with too few listings (a white / blue base: its boxes; 3.0.6, any other: values 10% then 20% looser, then
    one mod fewer), a next step left and no box changed since."""
    b = rec.get("broaden")
    return b if b and rec.get("state") == "done" and not rec.get("changed") else None


def search_word(rec, again="Search again"):
    """The card's orange button: Search (filters changed), ↔ Broaden Search, or Search again."""
    if rec.get("changed"):
        return "Search  •  filters changed"
    return BROADEN if broaden_offer(rec) else again


def search_tip(rec):
    """What the orange button does, in one line."""
    b = broaden_offer(rec)
    return f"Next: {b['next']} - one more search" if b else "Searches the trade site with these filters."


def flag_text(flags):
    """{"corrupted", "mirrored" ...} -> "⊘ Corrupted   ◈ Mirrored" (the game's order), or ""."""
    return "   ".join(f"{mark} {word}" for key, mark, word in FLAG_MARKS if key in (flags or ()))


def listing_flags(it, mods=()):
    """A trade-site listing's item -> its flags. Mirrored is the site's "duplicated"; Fractured / Desecrated also
    from its mod lines."""
    kinds = {k for _t, _x, k in mods or ()}
    out = set()
    if it.get("corrupted"):
        out.add("corrupted")
    if it.get("duplicated") or it.get("mirrored"):
        out.add("mirrored")
    if it.get("fractured") or it.get("fracturedMods") or "fractured" in kinds:
        out.add("fractured")
    if it.get("desecrated") or it.get("desecratedMods") or "desecrated" in kinds:
        out.add("desecrated")
    if it.get("sanctified"):
        out.add("sanctified")
    if it.get("craftedMods") or "crafted" in kinds:
        out.add("crafted")
    if it.get("identified") is False:
        out.add("unidentified")
    return out


def own_flags(rec):
    """The flags of the item you priced (from its copied text), as listing_flags gives a listing's."""
    try:
        from .searchopts_page import item_facts
        fl = item_facts(rec)["flags"]
    except Exception:
        buglog.caught()
        fl = {"corrupted"} if (rec.get("item") or {}).get("corrupted") else set()
    return {k for k, _m, _w in FLAG_MARKS if k in fl}


def listing_facts(e):
    """One trade-site entry -> what its card shows."""
    it, lst = (e or {}).get("item") or {}, (e or {}).get("listing") or {}
    icon_learn(_clean(it.get("baseType") or it.get("typeLine")), it.get("icon"))
    price = lst.get("price") or {}
    ts = None
    try:
        from .trade import listed_ts
        ts = listed_ts(lst.get("indexed")) if lst.get("indexed") else None
    except Exception:
        ts = None
    mods = mod_rows(it)
    return {"name": _clean(it.get("name")), "base": _clean(it.get("typeLine") or it.get("baseType")),
            "rarity": it.get("rarity") or "", "props": prop_lines(it), "ilvl": it.get("ilvl"), "req": req_line(it),
            "mods": mods, "corrupted": bool(it.get("corrupted")), "icon": it.get("icon") or "",
            "flags": sorted(listing_flags(it, mods)),
            "parts": prop_parts(it), "pseudo": [_clean(x if not isinstance(x, dict) else x.get("description"))
                                                 for x in it.get("pseudoMods") or []],
            "note": _clean(it.get("note")) if it.get("note") else "",
            "price": (price.get("amount"), price.get("currency")) if price.get("amount") is not None else None,
            "seller": ((lst.get("account") or {}).get("name") or ""), "ts": ts, "id": (e or {}).get("id"),
            "times": int((e or {}).get("_times") or 1)}           # 2.113.0: the seller listed it this many times



def pc_key_is_copy():
    """2.83.1: is the price check key the game's own Ctrl+C (then the app only listens, as in 2.80.0)?"""
    from .overlay import parse_key
    return parse_key(SETTINGS.get("pc_key") or "") == (0x43, True, False, False)


def pc_key_label():
    from .overlay import key_label
    return key_label(SETTINGS.get("pc_key") or "") or "your price check key"


class PCView:
    """2.84.0: one item card + listings layout (Price Checks, and Favorites uses the same)."""

    def __init__(self, left, lcanvas, lst, rcanvas, count, open_btn):
        self.left, self.lcanvas, self.lst, self.rcanvas, self.count, self.open_btn = \
            left, lcanvas, lst, rcanvas, count, open_btn
        self.cards = []
        self.redraw = None           # fn() -> draw the listings again (a picture arrived)
        self.recard = None           # 2.97.0: fn() -> draw the item card again (its side changed width)


class PriceCheckPage:
    def pc_search_go(self, rec):
        """The card's orange button: ↔ Broaden Search runs the ladder's next step (one search, its boxes set to what
        is searched); otherwise the boxes as they are (Search again)."""
        b = broaden_offer(rec)
        if b and b.get("loosen"):                        # 3.0.6 (owner): values 10%, then 20% looser, before a mod goes
            from .engine import apply_loosen
            rec["broaden"] = None
            apply_loosen(rec, b)
            self.status_text, self.status_until = f"Searched with every value {b['loosen']}% looser", time.time() + 6
        elif b and b.get("drop"):                          # 3.0.6: every item - the offered mod out (fewer_offer)
            from .trade import ov_key
            m = next((x for x in rec["item"]["mods"] if ov_key(x) == b["drop"]), None)
            rec["broaden"] = None
            if m is not None:
                self.toggle_mod(rec, m, False)
                self.status_text, self.status_until = f"Searched without: {str(b.get('text') or '')[:60]}", \
                    time.time() + 6
        elif b:
            from .gear import broadened_opts
            rec["opts"] = broadened_opts(rec.get("opts"), b)
            rec["broaden"] = None
        self.reprice([rec["id"]])

    def pc_search_button(self, parent, rec, again="Search again"):
        """The card's one orange button (search_word), with its one-line tip."""
        from .style import Tooltip
        btn = ttk.Button(parent, text=search_word(rec, again), style="Primary.TButton",
                         command=lambda: self.pc_search_go(rec))
        btn._search_tip = Tooltip(btn, search_tip(rec))
        return btn

    @staticmethod
    def pc_search_paint(btn, rec, again="Search again"):
        """The orange button's words and tip, after a price comes in or a box changes."""
        btn.config(text=search_word(rec, again))
        tip = getattr(btn, "_search_tip", None)
        if tip is not None:
            tip.text = search_tip(rec)

    # ---------------------------------------------------------------- the page
    def build_pc(self, body):
        self.pc_body = body
        self.pc_rid = None
        self._pc_art_init()
        P2 = C["panel2"]
        # UI overhaul: two views, listed under Price Checks in the sidebar - the check itself (home) and History, every
        # item you priced (pclist.py)
        from .style import SegBar
        from .pclist import PCList
        page = body
        self.pc_view = SegBar(page, ["Check", "History"], command=lambda v: self.pc_view_show())   # (not shown:
        if getattr(self, "shell", None) is not None:                                              # the sidebar is)
            self.shell.register_tabs("pricecheck", self.pc_view, home="Check")
        self.pc_hist_page = tk.Frame(page, bg=C["panel"])
        self.pc_listcol = PCList(self.pc_hist_page, self)
        self.pc_listcol.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body = self.pc_check_page = tk.Frame(page, bg=C["panel"])
        body.pack(fill="both", expand=True)
        self._pc_where_row(body)                     # 2.122.0: what your price check key does - first, full width
        self._pc_recent_row(body)                    # 2.123.0 (p6): Recent as chips (was a table under the card)
        self._pc_verdict_row(body)                   # 2.123.0 (p4): the price, how sure, why - once, across the top
        # 2.123.3 (feedback: "too wide ... allow a person to resize its horizontal width"): the item and the listings
        # share a divider you drag; its place is remembered (pc_card_w)
        cw = max(330, int(SETTINGS.get("pc_card_w", 420) or 420))
        # 2.123.4 (feedback: "janky and slow ... no visible indicator"): a grip you can see; only a guide line moves
        # while you drag, and the item is drawn again once, when you let go
        wrap = Splitter(body, width=cw, lo=330, keep=300, on_set=self._pc_pane_saved, bg=C["bg"])
        self.limit_banner(body, wrap)                # 2.103.3: the "Staying under the limits" line
        wrap.pack(fill="both", expand=True)
        self.pc_pane = wrap
        left = wrap.left
        top = tk.Frame(left, bg=P2, padx=12, pady=4)
        top.pack(fill="x")
        self.pc_hist_var = tk.StringVar()                    # (the old dropdown: kept for its callers, never shown)
        self.pc_hist_cb = ttk.Combobox(top, textvariable=self.pc_hist_var, state="readonly")
        self.pc_hist_cb.bind("<<ComboboxSelected>>", lambda e: self.pc_pick_hist())
        self.pc_lcanvas, self.pc_left = self._pc_scroller(left, padx=12)
        # ---- right: the listings
        right = wrap.right
        head = tk.Frame(right, bg=C["panel"], padx=12, pady=8)
        head.pack(fill="x")
        self.pc_count_lbl = tk.Label(head, text="", bg=C["panel"], fg=C["text"], font=("Segoe UI", 10, "bold"))
        self.pc_count_lbl.pack(side="left")
        self.pc_rcanvas, self.pc_list = self._pc_scroller(right, padx=12, bg_key="panel")
        self.pcv = PCView(self.pc_left, self.pc_lcanvas, self.pc_list, self.pc_rcanvas, self.pc_count_lbl,
                          self.pc_open_btn)
        self.pcv.redraw = lambda: self.pc_draw_list(self.records.get(self.pc_rid))
        # 3.0.6 (owner: "screen flickers"): a new width draws the card again only - the listings follow their own width
        self.pcv.recard = lambda: self.pc_show(self.records.get(self.pc_rid), card_only=True)
        self.pcv_fit(self.pcv, wrap, None)               # (2.123.3: no fixed share - the divider decides)
        self._pc_side_build(left)                        # drawer build: the price card beside the item (the Drawer)
        self._pc_lbox = self.pc_lcanvas.master
        self._pc_top = top
        self.pc_left.bind("<Configure>", lambda e: self._pc_stack_need(), add="+")
        self._pc_count_head = head
        self._drawer_look_hooks = getattr(self, "_drawer_look_hooks", []) + [self.pc_drawer_look]
        self.pc_refresh_hist()
        recs = self.pc_recs()
        self.pc_show(recs[0] if recs else None)
        try:
            self.drawer_look()                           # the Drawer: the item over its listings
        except Exception:
            buglog.caught()

    # 2.122.0 (feedback: "Show over the game" was unclear and "randomly thrown in the top right"): one row across the
    # top of the page says what your price check key does and lets you pick where the price shows - the same setting
    # as Settings › Price checking › Where the price shows and the card's ⚙.
    # drawer build: each choice names one place - In the app (the Drawer or your full window opens quietly on Price
    # Checks) or Price check overlay (the card over the game; the app stays put). Stored as before: pc_popup.
    PC_WHERE = ("In the app", "Price check overlay")

    def _pc_where_row(self, body):
        from .style import SegBar, Tooltip
        row = tk.Frame(body, bg=C["panel"], padx=12, pady=8)
        row.pack(fill="x")
        self.pc_where_lbl = tk.Label(row, text="", bg=C["panel"], fg=C["text"], font=("Segoe UI", 10))
        self.pc_where_lbl.pack(side="left", padx=(0, 8))
        self.pc_where = SegBar(row, list(self.PC_WHERE), value=self.PC_WHERE[0], size=9, pad=(12, 4),
                               command=self._pc_where_pick)
        self.pc_where.pack(side="left")
        tip = tk.Label(row, text="ⓘ", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow")
        tip.pack(side="left", padx=(8, 0))
        Tooltip(tip, "In the app: the Drawer (or your full window) opens on Price Checks and the game keeps the "
                     "keyboard; Ctrl+Shift+Space or Esc puts it away. Price check overlay: a card over the game with "
                     "the price; the app stays put and Price Checks has it next time. Every check is kept in Recent.")
        self.pc_where_note = tk.Label(row, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9))
        self.pc_where_note.pack(side="left", padx=(8, 0))
        from . import gearicon                            # (UI overhaul: drawn - the ⚙ glyph looked like a flower)
        gear = gearicon.label(row, 14, bg=C["panel"], cursor="hand2")
        gear.pack(side="right")                          # 2.123.0 (p3): this page's settings, one click away
        self.pc_gear = gear
        gear.bind("<Button-1>", lambda e: self.settings_open("Price checking", "pc_single"))
        Tooltip(gear, "Price check settings")
        flowify(row)                               # D3: wraps at Drawer width, the gear stays on the right
        self._pc_key_text = self.pc_where_paint          # (Settings › Keybinds calls it when a key changes)
        self.pc_where_paint()

    def pc_where_paint(self):
        """The row follows the setting, wherever it was changed."""
        try:
            self.pc_where_lbl.config(text=f"When you press {pc_key_label()} on an item in game, show the price")
            k = self.pc_show_get()
            self.pc_where.pick("Price check overlay" if k in ("over", "both") else "In the app", notify=False)
            self.pc_where_note.config(text={"off": "· the key is off - pick one to turn it on"}.get(k, ""))
        except (AttributeError, tk.TclError):
            pass

    def _pc_where_pick(self, label):
        if label == "Price check overlay":
            self.pc_show_set("both")
        else:
            self.pc_show_set("front")                        # (2.125.5: "behind the game" is gone)

    # ---------------------------------------------------------------- 2.123.0: Recent chips and the verdict strip
    def _pc_recent_row(self, body):
        """p6 (feedback: the Recent table took a quarter of the card's side): the last checks as chips."""
        row = tk.Frame(body, bg=C["panel"], padx=12, pady=2)
        row.pack(fill="x")
        tk.Label(row, text="Recent", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.pc_recent = tk.Frame(row, bg=C["panel"])
        self.pc_recent.pack(side="left", fill="x", expand=True)
        self.pc_recent_all = tk.Label(row, text="All ▾", bg=C["panel"], fg=C["accent"], cursor="hand2",
                                      font=("Segoe UI", 9))
        self.pc_recent_all.pack(side="right")
        self.pc_recent_menu = tk.Menu(self.pc_recent_all, tearoff=0, bg=C["panel2"], fg=C["text"],
                                      activebackground=C["accent"])
        self.pc_recent_all.config(text="History ›")         # UI overhaul: every check, on its own page
        self.pc_recent_all.bind("<Button-1>", lambda e: self.shell.open_tab("pricecheck", "History"))
        self.pc_recent.bind("<Configure>", self._pc_recent_resized, add="+")
        flowify(row)                               # D3: History › drops under the chips when it is narrow

    PC_CHIPS = 8

    def _pc_why_resized(self, e):
        w = max(200, e.width - 8)
        if abs(int(self.pc_v_why.cget("wraplength") or 0) - w) >= 8:
            self.pc_v_why.config(wraplength=w)

    def _pc_recent_resized(self, e):
        """2.128.0 (feedback: the app froze after a theme change): repaint the chips only when the row's width really
        changed, and not from inside the idle loop - each repaint changes what the row asks for, which could set off
        another resize, again and again, inside update_idletasks."""
        if abs(e.width - getattr(self, "_pc_recent_w", -99)) < 8:
            return
        self._pc_recent_w = e.width
        job = getattr(self, "_pc_recent_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                buglog.caught()
        self._pc_recent_job = self.root.after(60, self._pc_recent_go)

    def _pc_recent_go(self):
        self._pc_recent_job = None
        self.pc_recent_paint()

    def pc_view_show(self):
        """UI overhaul: Price Checks (the check) or Price Checks › History."""
        hist = self.pc_view.get() == "History"
        (self.pc_check_page if hist else self.pc_hist_page).pack_forget()
        (self.pc_hist_page if hist else self.pc_check_page).pack(fill="both", expand=True)
        if hist:
            self.pc_listcol.paint()
            self.pc_listcol.entry.focus_set()

    def pc_hist_open(self, rec):
        """A row in History: back to the check, showing that item."""
        try:
            self.shell.open_tab("pricecheck", "Check")
        except Exception:
            buglog.caught()
        self.pc_show(rec)

    def pc_recent_paint(self):
        lst = getattr(self, "pc_listcol", None)          # UI overhaul: History follows too
        if lst is not None:
            try:
                lst.paint()
            except tk.TclError:
                pass
        from .pricefmt import fmt_div
        box = getattr(self, "pc_recent", None)
        if box is None:
            return
        for w in box.winfo_children():
            w.destroy()
        recs = self.pc_recs()
        self.pc_chips = {}
        if not recs:
            tk.Label(box, text=f"Your last {PC_MAX} checks show here.", bg=C["panel"], fg=C["muted"],
                     font=("Segoe UI", 9)).pack(side="left")
        room = max(200, box.winfo_width() or 900)
        used = 0
        for r in recs[:self.PC_CHIPS]:
            it = r.get("item") or {}
            price = fmt_div(r["est"]) if r.get("est") is not None and not r.get("skip") else \
                ("…" if r.get("state") in ("queued", "pricing") else "no price")
            on = r["id"] == self.pc_rid
            t = f"{(it.get('name') or it.get('base') or 'item')[:22]} · {price}"
            dl = getattr(self, "_pc_dl", False)
            b = tk.Label(box, text=("\u25b8 " if on and dl else "") + t, bg=C["panel2"],
                         fg=C["text"] if on else C["muted"], font=("Segoe UI", 9),
                         padx=8, pady=2, cursor="hand2", highlightthickness=1,
                         highlightbackground=(C["text"] if dl else C["accent"]) if on else C["line"])
            used += b.winfo_reqwidth() + 6
            if used > room and self.pc_chips:
                b.destroy()
                break
            b.pack(side="left", padx=(0, 8))
            b.bind("<Button-1>", lambda e, rid=r["id"]: self.records.get(rid) and self.pc_show(self.records[rid]))
            self.pc_chips[r["id"]] = b
        m = self.pc_recent_menu
        m.delete(0, "end")
        for r in recs:
            m.add_command(label=self.pc_label(r), command=lambda rid=r["id"]: self.records.get(rid) and
                          self.pc_show(self.records[rid]))
        self.pc_recent_all.config(fg=(C["text"] if getattr(self, "_pc_dl", False) else C["accent"]) if recs else
                                  C["muted"])

    def _pc_verdict_row(self, body):
        """p4 (feedback: "Couldn't price" in the card and "Couldn't search" again on the right): the answer, how sure,
        how it was worked out and the next steps - one strip across the top. The only orange button: Search again."""
        f = self.pc_verdict = tk.Frame(body, bg=C["panel2"], padx=12, pady=8, highlightthickness=1,
                                       highlightbackground=C["line"])
        left = tk.Frame(f, bg=C["panel2"])
        left.pack(side="left", fill="x", expand=True)
        self.pc_v_big = tk.Label(left, text="", bg=C["panel2"], fg=C["text"], font=("Segoe UI", 16, "bold"), anchor="w")
        self.pc_v_big.pack(side="left")
        self.pc_v_how = tk.Label(left, text="", bg=C["panel2"], fg=C["text"], font=("Segoe UI", 10), anchor="w")
        self.pc_v_how.pack(side="left", padx=(12, 0))
        self.pc_v_why = tk.Label(left, text="", bg=C["panel2"], fg=C["muted"], font=("Segoe UI", 9), anchor="w",
                                 justify="left")
        self.pc_v_why.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.pc_v_why.bind("<Configure>", self._pc_why_resized)     # (2.128.0: only a real change re-wraps)
        from .style import Tooltip as _Tip                 # drawer-look: how the price was worked out (listings,
        self.pc_v_info = tk.Label(left, text="ⓘ", bg=C["panel2"], fg=C["muted"], font=("Segoe UI", 10),
                                  cursor="question_arrow")          # middle, range) - one hover, as in the Drawer
        self.pc_v_info_tip = _Tip(self.pc_v_info, "")
        # 2.123.2 (hotfix, feedback: the buttons belong under the item): Search again, fewer mods, Clear, favorites and
        # Trade Site are made with each card, under it (pcv_card). These stand in, unshown, while there's no item.
        hold = tk.Frame(f, bg=C["panel2"])
        self.pc_open_btn0 = self.pc_open_btn = trade_icon(ttk.Button(hold, text="Trade Site", command=self.pc_open_trade,
                                                                     state="disabled"))
        self.pc_fav_btn0 = self.pc_fav_btn = ttk.Button(hold, text="☆ Add to favorites", command=self.pc_add_fav,
                                                        state="disabled")
        self.pc_search_btn = ttk.Button(hold, text="Search again", style="Primary.TButton")
        self.pc_fewer_btn = ttk.Button(hold, text=BROADEN)

    def pc_verdict_paint(self, rec):
        """The strip says it with a mark and a word, never by color alone."""
        f = getattr(self, "pc_verdict", None)
        if f is None:
            return
        try:
            self.pc_side_paint(rec)                      # drawer build: the Drawer's price card says the same
        except Exception:
            buglog.caught()
        if rec is None:
            f.pack_forget()
            return
        elif not f.winfo_manager():
            f.pack(fill="x", padx=12, pady=(4, 8), after=self.pc_recent.master)
        from .pricefmt import fmt_div
        st, fewer = rec.get("state"), False
        entries, total, n = self.pc_entries(rec) if st == "done" else ([], 0, 0)
        on = len(self.pc_ticked(rec))
        if st == "done" and rec.get("est") is not None and not rec.get("nomatch"):
            conf = str(rec.get("conf") or "").lower()
            mark, word, col = {"high": ("✓", "a solid price", C["good"]), "medium": ("~", "a fair guess", C["orange"]),
                               "low": ("!", "thin data - check by hand", C["orange"])}.get(conf, ("~", "a guess", C["orange"]))
            big = ("≥ " if rec.get("partial") else "≈ ") + fmt_div(rec["est"])
            how = f"{mark} {word}"
            total = rec.get("total") if rec.get("total") is not None else total
            why = (f"from the {min(n, 5)} cheapest of {total:,} listing{'s' if total != 1 else ''}" if n else
                   f"from {total:,} listing{'s' if total != 1 else ''}")
            self.pc_v_big.config(text=big, fg=C["good"])
            self.pc_v_how.config(text=how, fg=col)
            try:
                self.pc_v_info_tip.text = self.pc_price_how(rec)[1]
                if not self.pc_v_info.winfo_manager():
                    self.pc_v_info.pack(side="left", padx=(8, 0), before=self.pc_v_why)
            except Exception:
                buglog.caught()
        elif st == "done":
            self.pc_v_big.config(text="✕ No match" if not rec.get("manual") else "! Check by hand", fg=C["red"])
            self.pc_v_how.config(text="No listings matched these filters" if not rec.get("manual") else "", fg=C["text"])
            why = (f"{on} mod filter{'s are' if on != 1 else ' is'} on. " if on else "") + \
                "Untick the rarest mod or lower a Min, then search again."
            if broaden_offer(rec):                       # owner: the next step, one click (3.0.6: every item)
                why = f"Press {BROADEN} to try {broaden_offer(rec)['next']}."
        elif st == "error":
            reason = rec.get("label") or "The trade site didn't answer."
            low = reason.lower()
            tip = ("Too many filters for one search: untick a few mods." if "complex" in low else
                   "Pick a league in Settings." if "league" in low else "Wait a moment and try again.")
            self.pc_v_big.config(text="✕ Couldn't search", fg=C["red"])
            self.pc_v_how.config(text="", fg=C["text"])
            why = f"{reason}. {tip}" if not reason.endswith(".") else f"{reason} {tip}"
            fewer = "complex" in low and on > 1
        else:
            self.pc_v_big.config(text="… Searching the trade site" if st == "pricing" else "… Waiting in line",
                                 fg=C["muted"])
            self.pc_v_how.config(text="", fg=C["text"])
            why = ""
        self.pc_v_why.config(text=why)
        if not (st == "done" and rec.get("est") is not None and not rec.get("nomatch")):
            self.pc_v_info.pack_forget()
        try:                                             # (the card's buttons - made with each card, 2.123.2)
            self.pc_search_paint(self.pc_search_btn, rec)
            if fewer:
                if not self.pc_fewer_btn.winfo_manager():
                    self.pc_fewer_btn.pack(side="left", padx=(8, 0), after=self.pc_search_btn)
            else:
                self.pc_fewer_btn.pack_forget()
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- the Drawer's look (mockups.html)
    PC_SIDE_W = 300
    SURE = {"high": ("sure", "●●●"), "medium": ("fairly", "●●○"),
            "low": ("not very", "●○○")}

    def pc_drawer_look(self, on):
        """drawer build: Price Checks in the Drawer is laid out as mockups.html shows it - the item card with its
        buttons and the price card side by side, the cheapest listings as a table under them. The Full window keeps
        its own (the price strip across the top, the item beside its listings)."""
        on = bool(on)
        was = getattr(self, "_pc_dl", None)
        self._pc_dl = on
        pane = getattr(self, "pc_pane", None)
        if pane is None:
            return
        P1, P2 = C["panel"], C["panel2"]
        try:
            pane.left.config(bg=P1 if on else P2)
            pane.right.config(bg=P1)
            pane.pack_configure(padx=12 if on else 0)
            self._pc_top.pack_forget() if on else self._pc_top.pack(fill="x", before=self._pc_lbox)
            self._pc_count_head.config(pady=8)
            self.pc_side.pack_forget()                   # 3.0.6 (owner: "why is it a different layout than full
            # screen mode? price card doesn't go on the right"): the Drawer has the price strip across the top too
            lcv, inner = self.pc_lcanvas, self.pc_left
            lcv.config(bg=P2)
            lcv.master.config(bg=P2, highlightthickness=1 if on else 0, highlightbackground=C["line"])
            inner.config(bg=P2, padx=16 if on else 12, pady=12 if on else 4)
            if not on and getattr(self, "_pc_btnrow", None) is not None:
                self._pc_btnrow.destroy()
                self._pc_btnrow = None
            self.pc_count_lbl.config(fg=C["muted"] if on else C["text"],
                                     font=("Segoe UI", 9) if on else ("Segoe UI", 10, "bold"))
            self.pc_where_lbl.config(fg=C["muted"] if on else C["text"],
                                     font=("Segoe UI", 9) if on else ("Segoe UI", 10))
        except tk.TclError:
            return
        if was is not None and was != on:                # the item and its listings again, in this look
            rec = self.records.get(self.pc_rid) if self.pc_rid else None
            if rec is not None:
                old = list(self.pc_left.winfo_children())
                for w in old:
                    w.destroy()
                self._pc_show_into(rec)
            else:
                self.pc_verdict_paint(None)

    def _pc_stack_need(self):
        """Round 18: the Drawer's item card is as tall as it is (its buttons too) - the listings get the rest; the
        card scrolls only when the page can't hold it (Splitter.stack_need)."""
        pane = getattr(self, "pc_pane", None)
        if pane is None or not getattr(pane, "_stacked", False):
            return
        try:
            need = self.pc_left.winfo_reqheight() + 4
            row = getattr(self, "_pc_btnrow", None)
            if row is not None and row.winfo_exists():
                need += row.winfo_reqheight()
            side = 0
            if self.pc_side.winfo_manager():              # (the price card beside it: what its lines need - it
                side = sum(c.winfo_reqheight() + 12 for c in self.pc_side.winfo_children()   # doesn't ask for
                           if c.winfo_manager()) + 2 * 12 + 12                              # its own size)
            need = max(need, side) + 16
            pane.stack_need(need)
        except tk.TclError:
            pass

    def _pc_side_build(self, parent):
        """The price card (mockups.html): Price, the number, what it is in another currency, how sure, how it was
        worked out (listings · middle · range, one hover on ⓘ for the rest), and the last time. Shown in the Drawer."""
        from .style import Tooltip
        from . import themes as TH
        P2 = C["panel2"]
        f = self.pc_side = tk.Frame(parent, bg=P2, width=self.PC_SIDE_W, padx=16, pady=12, highlightthickness=1,
                                    highlightbackground=C["line"])
        tk.Frame(f, bg=P2, width=self.PC_SIDE_W - 2 * 16 - 2, height=0).pack()   # 3.0.6 (owner: "the layout is
        lab = dict(bg=P2, anchor="w", justify="left", bd=0)           # weird"): as tall as its lines, not the page
        self.pcs_head = tk.Label(f, text="Price", fg=C["muted"], font=("Segoe UI", 9), **lab)
        self.pcs_head.pack(fill="x")
        row = tk.Frame(f, bg=P2)
        row.pack(fill="x", pady=(4, 0))
        self.pcs_big = tk.Label(row, text="", fg=C["good"], font=(TH.head_font(), 28), **lab)
        self.pcs_big.pack(side="left", anchor="s")
        self.pcs_unit = tk.Label(row, text="", fg=C["good"], font=(TH.head_font(), 16), **lab)
        self.pcs_unit.pack(side="left", anchor="s", padx=(8, 0), pady=(0, 4))
        self.pcs_alt = tk.Label(f, text="", fg=C["muted"], font=("Segoe UI", 9), **lab)
        self.pcs_alt.pack(fill="x", pady=(4, 0))
        sure = self.pcs_sure = tk.Frame(f, bg=P2)
        sure.pack(fill="x", pady=(12, 0))
        tk.Label(sure, text="How sure:", fg=C["text"], font=("Segoe UI", 9), **lab).pack(side="left")
        self.pcs_word = tk.Label(sure, text="", fg=C["text"], font=("Segoe UI", 9, "bold"), **lab)
        self.pcs_word.pack(side="left", padx=(4, 0))
        self.pcs_dots = tk.Label(sure, text="", fg=C["muted"], font=("Segoe UI", 9), **lab)
        self.pcs_dots.pack(side="left", padx=(4, 0))
        how = self.pcs_howrow = tk.Frame(f, bg=P2)
        how.pack(fill="x", pady=(8, 0))
        self.pcs_how = tk.Label(how, text="", fg=C["muted"], font=("Segoe UI", 9), wraplength=self.PC_SIDE_W - 60,
                                **lab)
        self.pcs_how.pack(side="left")
        self.pcs_info = tk.Label(how, text="ⓘ", fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow",
                                 **lab)
        self.pcs_info.pack(side="left", anchor="n", padx=(4, 0))
        self.pcs_tip = Tooltip(self.pcs_info, "")
        self.pcs_tip2 = Tooltip(self.pcs_how, "")
        self.pcs_why = tk.Label(f, text="", fg=C["text"], font=("Segoe UI", 9), wraplength=self.PC_SIDE_W - 36,
                                **lab)
        self.pcs_why.pack(fill="x", pady=(8, 0))
        self.pcs_last = tk.Label(f, text="", fg=C["muted"], font=("Segoe UI", 9), wraplength=self.PC_SIDE_W - 36,
                                 **lab)
        self.pcs_last.pack(fill="x", pady=(16, 0))

    @staticmethod
    def _short(x):
        """fmt_div with the short units: "3.5 ex", "1.2 div"."""
        from .pricefmt import fmt_div, SHORT_UNITS
        num, _, unit = fmt_div(x).rpartition(" ")
        short = {"d": "div"}.get(SHORT_UNITS.get(unit, unit), SHORT_UNITS.get(unit, unit))
        return f"{num} {short}" if num else unit

    def pc_price_how(self, rec):
        """How the price was worked out, from the record: (one line, the tooltip's lines). The middle of the cheapest
        5 (half cheaper, half dearer) is the price; far-off prices are left out first (trade.estimate)."""
        fmt_div = self._short
        from .trade import RATES
        prices = (rec.get("prices") or [])[:5]
        league = SETTINGS.get("league")
        conv = [d for d in (RATES.to_div(a, c, league) for a, c in prices) if d is not None]
        total = rec.get("total") if rec.get("total") is not None else len(rec.get("prices") or [])
        mid = fmt_div(rec["est"]) if rec.get("est") is not None else "-"
        tip = [f"Listings with the ticked mods: {total:,}",
               f"Middle (half cheaper, half dearer) of the {min(5, len(prices)) or 5} cheapest: {mid}"]
        rng = ""
        if conv:
            import statistics
            med = statistics.median(conv)
            kept = [d for d in conv if med / 5 <= d <= med * 5] or conv
            lo, hi = fmt_div(min(kept)), fmt_div(max(kept))
            if lo == hi:
                rng = lo
            elif lo.rpartition(" ")[2] == hi.rpartition(" ")[2]:      # (one unit: "2.8 – 4.4 ex")
                rng = f"{lo.rpartition(' ')[0]} – {hi}"
            else:
                rng = f"{lo} – {hi}"
            tip.append(f"Range, lowest to highest: {rng}")
            if len(kept) < len(conv):
                tip.append(f"Far-off prices left out: {len(conv) - len(kept)}")
        elif prices:
            from .pricefmt import fmt_price
            rng = f"{fmt_price(prices[0])} – {fmt_price(prices[-1])}"
            tip.append(f"Range, lowest to highest: {rng} (no exchange rate to compare them)")
        why = rec.get("conf_why") or []
        if why:
            tip.append("How sure: " + "; ".join(str(w) for w in why[:4]))
        line = f"{total:,} listing{'s' if total != 1 else ''} · middle {mid}" + (f" · range {rng}" if rng else "")
        return line, "\n".join(tip)

    def pc_side_paint(self, rec):
        f = getattr(self, "pc_side", None)
        if f is None:
            return
        from .pricefmt import fmt_div, SHORT_UNITS
        st = (rec or {}).get("state")
        why, alt, last = "", "", ""
        good = st == "done" and rec.get("est") is not None and not rec.get("nomatch")
        show_sure = good
        if rec is None:
            big, unit, col = "—", "", C["muted"]
            why = f"Hover an item in game and press {pc_key_label()}."
        elif good:
            txt = ("≥ " if rec.get("partial") else "") + fmt_div(rec["est"])
            num, _, u = txt.rpartition(" ")
            big, unit, col = (num, SHORT_UNITS.get(u, u), C["good"]) if num else (txt, "", C["good"])
            if u not in ("div", "divine"):
                e_ = rec["est"]
                alt = "≈ " + (f"{e_:.3f}" if e_ < 0.1 else f"{e_:.2f}" if e_ < 10 else f"{e_:,.0f}") + " div"
            if rec.get("manual"):
                why = "Check by hand: " + (rec.get("manual_why") or "the listings are priced far apart") + "."
            last = (rec.get("memory") or "").replace("Memory: ", "Last time: ", 1)
        elif st == "done":
            on = len(self.pc_ticked(rec))
            big, unit, col = ("✕ No match" if not rec.get("manual") else "! Check by hand"), "", C["red"]
            why = (f"{on} mod filter{'s are' if on != 1 else ' is'} on. " if on else "") + \
                "Untick the rarest mod or lower a Min, then search again."
            if broaden_offer(rec):                       # owner: a base - the ladder's next step, one click
                why = f"Press {BROADEN} to try {broaden_offer(rec)['next']}."
        elif st == "error":
            reason = rec.get("label") or "The trade site didn't answer."
            big, unit, col = "✕ Couldn't search", "", C["red"]
            why = reason
        else:
            big, unit, col = ("… Searching" if st == "pricing" else "… Waiting in line"), "", C["muted"]
        long_ = not good
        from . import themes as TH
        self.pcs_big.config(text=big, fg=col, font=("Segoe UI", 16, "bold") if long_ else (TH.head_font(), 28))
        self.pcs_unit.config(text=unit, fg=col)
        self.pcs_alt.config(text=alt)
        if show_sure:
            word, dots = self.SURE.get(str(rec.get("conf") or "").lower(), ("a guess", "●○○"))
            self.pcs_word.config(text=word)
            self.pcs_dots.config(text=f"({dots})")
            line, tip = self.pc_price_how(rec)
            self.pcs_how.config(text=line)
            self.pcs_tip.text = self.pcs_tip2.text = tip
            if not self.pcs_sure.winfo_manager():
                self.pcs_sure.pack(fill="x", pady=(12, 0), after=self.pcs_alt)
                self.pcs_howrow.pack(fill="x", pady=(8, 0), after=self.pcs_sure)
        else:
            self.pcs_sure.pack_forget()
            self.pcs_howrow.pack_forget()
        self.pcs_why.config(text=why)
        self.pcs_last.config(text=last)

    def _pc_card_buttons(self, v, rec):
        """The card's buttons in the Drawer (mockups.html): Search again (the one orange button), Trade Site,
        Add to favorites, then Broaden Search (too many filters for one search) and Clear - one row that wraps."""
        from .style import Tooltip
        P2 = C["panel2"]
        old = getattr(self, "_pc_btnrow", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
        btns = self._pc_btnrow = tk.Frame(self._pc_lbox, bg=P2, padx=16, pady=12)   # (under the card's scroll:
        btns.pack(side="bottom", fill="x", before=self.pc_lcanvas)                   # always in view)
        btn = self.pc_search_button(btns, rec)
        btn.pack(side="left")
        self.pc_search_btn = btn
        self.pc_fewer_btn = ttk.Button(btns, text=BROADEN, command=lambda: self.pc_fewer(rec))
        Tooltip(self.pc_fewer_btn, "Searches without your lowest-rated ticked mod.")
        self.pc_open_btn = trade_icon(ttk.Button(btns, text="Trade Site", command=self.pc_open_trade,
                                                 state="normal" if rec.get("qid") else "disabled"))
        self.pc_open_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.pc_open_btn, "Opens this search on the trade site")
        self.pc_fav_btn = ttk.Button(btns, text="☆ Add to favorites", command=self.pc_add_fav, state="disabled")
        self.pc_fav_btn.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear", command=self.pc_clear).pack(side="left", padx=(8, 0))
        v.open_btn = self.pc_open_btn
        flowify(btns)
        return btn

    def _pc_table(self, v, entries, total, n):
        """The cheapest listings as a table (mockups.html): the item and its mods, the asking price, when it was
        listed, the seller; ▸ opens the listing's full card under its row."""
        from . import themes as TH
        P2 = C["panel2"]
        v.count.config(text=f"Showing {len(entries)} of {total:,} listings" if total else "No listings found")
        if n and not entries:
            tk.Label(v.lst, text="The listings aren't loaded any more - press Search again to load them.",
                     bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x", pady=8)
            return
        if not entries:
            return
        card = tk.Frame(v.lst, bg=P2, padx=8, pady=4, highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x", pady=(0, 12))
        card.columnconfigure(0, weight=1)
        mut, txt = C["muted"], C["text"]
        for c, (head, anchor) in enumerate((("Cheapest listings", "w"), ("Price", "e"), ("Listed", "w"),
                                            ("Seller", "w"), ("", "w"))):
            tk.Label(card, text=head, bg=P2, fg=mut, font=("Segoe UI", 9), anchor=anchor).grid(
                row=0, column=c, sticky="ew", padx=8, pady=(4, 4))
        tk.Frame(card, bg=C["line"], height=1).grid(row=1, column=0, columnspan=5, sticky="ew")
        width = max(420, v.rcanvas.winfo_width() - 24 - 2 - 18)
        r = 2
        for e in entries:
            f = listing_facts(e)
            name = " · ".join(x for x in (f["name"], f["base"]) if x) or "Item"
            mods = [t for _tier, t, kind in f["mods"] if kind not in ("implicit", "enchant", "rune")]
            cell = tk.Frame(card, bg=P2)
            cell.grid(row=r, column=0, sticky="ew", padx=8, pady=8)
            tk.Label(cell, text=name, bg=P2, fg=txt, font=("Segoe UI", 10), anchor="w").pack(fill="x")
            if mods:
                ml = tk.Label(cell, text=" · ".join(mods), bg=P2, fg=mut, font=("Segoe UI", 9), anchor="w",
                              justify="left", wraplength=max(200, width - 380))
                ml.pack(fill="x")
            if f["price"]:
                amt, cur = f["price"]
                amt = int(amt) if float(amt).is_integer() else amt
                from .pricefmt import UNIT_NAMES
                ptxt = f"{amt} {UNIT_NAMES.get(cur) or cur_label(cur)}"
            else:
                ptxt = "no price"
            tk.Label(card, text=ptxt, bg=P2, fg=C["good"] if f["price"] else mut, font=("Segoe UI", 10),
                     anchor="e").grid(row=r, column=1, sticky="ne", padx=8, pady=8)
            tk.Label(card, text=ago(f["ts"]) if f["ts"] else "", bg=P2, fg=mut, font=("Segoe UI", 9),
                     anchor="w").grid(row=r, column=2, sticky="nw", padx=8, pady=8)
            seller = f["seller"] + (f" ({f['times']}×)" if f.get("times", 1) > 1 else "")
            tk.Label(card, text=seller, bg=P2, fg=mut, font=("Segoe UI", 9), anchor="w").grid(
                row=r, column=3, sticky="nw", padx=8, pady=8)
            more = tk.Label(card, text="▸", bg=P2, fg=mut, font=("Segoe UI", 10), cursor="hand2")
            more.grid(row=r, column=4, sticky="ne", padx=8, pady=8)
            from .style import Tooltip
            tip = Tooltip(more, "Show the whole listing")
            slot = tk.Frame(card, bg=P2)
            slot.grid(row=r + 1, column=0, columnspan=5, sticky="ew")
            slot.grid_remove()

            def toggle(_e=None, slot=slot, more=more, f=f, tip=tip):
                if slot.winfo_manager():
                    slot.grid_remove()
                    more.config(text="▸")
                    tip.text = "Show the whole listing"
                    return
                if not slot.winfo_children():
                    cv = self._pc_card(slot, f, width)
                    v.cards.append(cv)
                slot.grid()
                more.config(text="▾")
                tip.text = "Hide the whole listing"
            more.bind("<Button-1>", toggle)
            r += 2
            tk.Frame(card, bg=C["line"], height=1).grid(row=r, column=0, columnspan=5, sticky="ew")
            r += 1
        v.rcanvas.yview_moveto(0)

    def pcv_fit(self, v, page, side, lo=380, share=0.32, hi=620):
        """2.97.0 (feedback: scale to fit, nothing cut off): the card's side takes about a third of the page (wider
        windows: fewer wrapped lines, so no scrollbar), and the card and the listings are drawn again for the width
        they have when the window changes size."""
        state = {"page": 0, "after_card": None, "after_list": None}

        def side_w(pw):
            return max(lo, min(hi, int(pw * share)))

        def page_cfg(e):
            if abs(e.width - state["page"]) < 8:
                return
            state["page"] = e.width
            try:
                side.config(width=side_w(e.width))
            except tk.TclError:
                pass

        def later(what):
            slot = "after_" + what
            if state[slot] is not None:
                try:
                    self.root.after_cancel(state[slot])
                except Exception:
                    buglog.caught()

            def go():
                state[slot] = None
                try:                                     # 3.0.6 (owner: the Drawer "super laggy when trying to drag
                    held = self._drawer_mouse_down()     # and resize it"): still dragging - drawn once, on release
                except Exception:
                    held = False
                if held:
                    state[slot] = self.root.after(150, go)
                    return
                if what == "card" and not card_off():   # (it fits now - nothing to draw)
                    return
                if what == "list" and not list_off():
                    return
                fn = v.recard if what == "card" else v.redraw
                if fn is not None:
                    try:
                        fn()
                    except Exception:
                        self.log_error("the price check view")
            state[slot] = self.root.after(150, go)

        # 3.0.6 (owner: "doesn't update consistently ... sometimes the listings view is crunched"): compared with the
        # width each was DRAWN for (not the last resize), so one drawn before the page had its width is drawn again
        # once it has it - the end state no longer depends on timing
        def card_off():
            return getattr(v, "shown_rid", None) is not None and \
                abs(self.pcv_wrap(v) - (getattr(v, "card_wrap", 0) or 0)) >= 8

        def list_off():
            return getattr(v, "list_shown", False) and \
                abs(self._pc_list_w(v) - (getattr(v, "list_w", 0) or 0)) >= 8

        def card_cfg(e):
            if card_off():
                later("card")

        def list_cfg(e):
            if list_off():
                later("list")
        if side is not None:
            page.bind("<Configure>", page_cfg, add="+")
        v.lcanvas.bind("<Configure>", card_cfg, add="+")
        v.rcanvas.bind("<Configure>", list_cfg, add="+")

    def _pc_pane_saved(self, w=None):
        """The divider was let go (Splitter keeps it between 330 px and all but 300 px of the page): remember it."""
        try:
            SETTINGS["pc_card_w"] = int(self.pc_pane.sashpos(0) if w is None else w)
            from .config import save_json
            save_json("settings.json", SETTINGS)
        except (tk.TclError, AttributeError, ValueError):
            pass

    def pcv_wrap(self, v):
        """The card's text width: what its side has (2.97.0; was a fixed 330)."""
        try:
            cw = v.lcanvas.winfo_width()
        except tk.TclError:
            cw = 0
        wrap = max(330, cw - 24 - 12) if cw > 50 else 330
        if v is getattr(self, "pcv", None) and getattr(self, "_pc_dl", False):
            return max(300, cw - 2 * 16 - 12) if cw > 50 else 420     # (the Drawer: the card fills its side)
        if getattr(getattr(self, "pc_pane", None), "_stacked", False):      # (the Drawer: the item over its listings)
            wrap = min(wrap, 620)
        return wrap

    @staticmethod
    def _pc_list_w(v):
        """A listing card's width: what the listings have (2.97.0: inner padx 12 + 12)."""
        try:
            return max(420, v.rcanvas.winfo_width() - 24 - 2)
        except tk.TclError:
            return 420

    def _pc_scroller(self, parent, padx=0, bg_key="panel2"):
        bg = C[bg_key]
        box = tk.Frame(parent, bg=bg)
        box.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(box, orient="vertical")
        # 3.0.6 (owner: "janky ... flickers ... sometimes cropped and has scroll down, sometimes it doesn't"): the bar's
        # room is kept when it's hidden (an empty strip as wide), so showing it never narrows the page - no re-wrap,
        # no redraw, no bar flipping on and off
        gap = tk.Frame(box, bg=bg, width=sb.winfo_reqwidth(), height=1)
        gap.pack(side="right", fill="y")
        cv = tk.Canvas(box, bg=bg, highlightthickness=0, yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.config(command=cv.yview)
        inner = tk.Frame(cv, bg=bg, padx=padx, pady=4)
        win = cv.create_window((0, 0), window=inner, anchor="nw")

        from .style import SbGuard
        guard = SbGuard()

        def fit(_e=None):
            """2.97.0 (feedback: no scrollbar when it fits): the bar shows only when there's more to see (2.112.2:
            never flipping back and forth - SbGuard)."""
            try:
                cv.configure(scrollregion=cv.bbox("all"))
                need = inner.winfo_reqheight() > cv.winfo_height() + 1
                if need and not sb.winfo_ismapped():
                    gap.pack_forget()
                    sb.pack(side="right", fill="y", before=cv)
                    guard.flipped()
                elif not need and sb.winfo_ismapped() and guard.may_hide():
                    sb.pack_forget()
                    gap.pack(side="right", fill="y", before=cv)
                    guard.flipped()
                    cv.yview_moveto(0)
            except tk.TclError:
                pass
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(win, width=e.width), fit()))
        inner.bind("<Configure>", fit)
        cv._sb = sb

        def wheel(e):
            d = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            if inner.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(d * 2, "units")
        box.bind("<Enter>", lambda e: (box.bind_all("<MouseWheel>", wheel), box.bind_all("<Button-4>", wheel),
                                       box.bind_all("<Button-5>", wheel)))
        box.bind("<Leave>", lambda e: (box.unbind_all("<MouseWheel>"), box.unbind_all("<Button-4>"),
                                       box.unbind_all("<Button-5>")))
        return cv, inner

    # ---------------------------------------------------------------- items in
    def pc_pop_var(self):
        """The one switch for the card over the game (Price Checks' header and Settings › Keybinds share it)."""
        v = getattr(self, "_pc_pop_var", None)
        if v is None:
            v = self._pc_pop_var = tk.BooleanVar(value=bool(SETTINGS.get("pc_popup", False)))
        return v

    def pc_pop_set(self):
        from .config import save_json
        SETTINGS["pc_popup"] = bool(self.pc_pop_var().get())
        save_json("settings.json", SETTINGS)
        if not SETTINGS["pc_popup"]:
            self.pcpop_close()
        self.pc_where_paint()

    def pc_wants(self, text):
        """An item copied with your price check key (Ctrl+D; Settings › Keybinds), with its switch on. Set to Ctrl+C,
        the game's own plain copy counts as before."""
        keys = getattr(self, "keys", None)
        from . import features as FEAT
        if not SETTINGS.get("pc_ctrl_c", True) or keys is None or not getattr(keys, "active", False) \
                or not FEAT.on("price"):                         # 2.131.0: Price checking off (Features)
            return False
        if not text.lstrip().startswith("Item Class:"):
            return False
        if getattr(keys, "tu_recent", None) and keys.tu_recent():
            return False                                         # (2.131.1: the Top Up key's copy - not priced)
        if pc_key_is_copy():
            return keys.copy_recent() and not keys.combo_recent()
        return keys.pc_recent()

    def pc_take(self, text):
        """An item for Price Checks: priced first in line, shown on the page (the app comes to the front if you
        want - Settings › Keybinds)."""
        from .wealth import parse_currency_item
        cur = parse_currency_item(text)
        try:                                             # 2.128.0: a Favours reward - learn what it looks like
            self.favours_copy_learn(text)                # (2.129.3: exchange items, and ★ uniques - never priced)
        except Exception:
            buglog.caught()
        if cur and cur[2] == "Wombgifts":                # (feedback: "use trade site for the 5 types of wombgifts")
            cur = None
        if cur:                                          # 2.129.0 (feedback): omens, essences, lineage gems, every
            self.status_text, self.status_until = f"Pricing {cur[0]}...", time.time() + 10     # currency: their
            self.stack_price(cur[0], cur[1], loud=True)  # going rate on poe.ninja's exchange - never a trade search
            return None
        rid = self.add_item_text(text, src="pc")
        if rid is None:                                  # which kind of item, and why it isn't priced (one line)
            from . import gamedata
            g = gamedata.read_item(text)
            self.status_text = gamedata.unpriced_line(g) if g else gamedata.copy_problem(text) or gamedata.COPY_NOT_ITEM
            self.status_until = time.time() + 8
            self.pc_missed = self.status_text            # (the read mark over the game says it too)
            return None
        old = self.pc_recs()[PC_MAX:]
        for r in old:
            self.records.pop(r["id"], None)
        self.pc_refresh_hist()
        self.pc_show(self.records[rid])
        from .pcpop import pop_on
        if pop_on():                                     # 2.113.0: a card over the game; the app stays where it is
            try:
                self.pcpop_show(self.records[rid])
            except Exception:
                self.log_error("the price check card over the game")
            # 2.123.3: Overlay + Here - the app shows it too. 2.129.3 (feedback: "it's still prioritizing the app and
            # bringing it to the front ... it should not bring to front and only use the overlay"): while the game is
            # in front the app isn't touched at all - Price Checks opens on it the next time you come to the app
            try:
                from .overlay import game_active, POE_TITLE
                if game_active((getattr(self, "overlay", None) and self.overlay.cfg.get("poe_title")) or POE_TITLE):
                    self._pc_open_later = True
                    if not getattr(self, "_pc_later_bound", False):
                        self._pc_later_bound = True
                        self.root.bind("<FocusIn>", self._pc_open_pending, add="+")
                else:
                    self.shell.open("pricecheck")
            except Exception:
                self.log_error("opening Price Checks")
            return rid
        try:                                             # drawer build: In the app - shown quietly on Price Checks,
            self.app_show("pricecheck", focus=False, why="price")    # the game keeps the keyboard (pc_front isn't
        except Exception:                                # read in this build; the main build still reads it)
            self.log_error("opening Price Checks")
        return rid

    def _pc_open_pending(self, _e=None):
        """You came back to the app after a price check shown over the game: Price Checks, with it."""
        if getattr(self, "_pc_open_later", False):
            self._pc_open_later = False
            try:
                self.shell.open("pricecheck")
            except Exception:
                self.log_error("opening Price Checks")

    def pc_clear(self):
        """2.93.1: clear the single searches - every item on Price Checks (Recent too). Bulk Pricing and Favorites
        stay as they are."""
        for r in self.pc_recs():
            self.records.pop(r["id"], None)
            getattr(self, "batch_ids", set()).discard(r["id"])
            if r.get("raw"):
                getattr(self, "seen_texts", {}).pop(hash(r["raw"].strip()), None)      # copying it again checks it again
        self.dirty = True
        self.pc_rid = None
        self.pc_refresh_hist()
        self.pc_show(None)

    def pc_recs(self):
        return sorted((r for r in self.records.values() if r.get("src") == "pc"), key=lambda r: -r.get("time", 0))

    def pc_label(self, r):
        it = r.get("item") or {}
        name = it.get("name") or it.get("base") or "item"
        return f"{name}  ·  {time.strftime('%H:%M', time.localtime(r.get('time', 0)))}"

    def pc_refresh_hist(self):
        if not hasattr(self, "pc_hist_cb"):
            return
        self.pc_recent_paint()
        recs = self.pc_recs()
        self._pc_hist_ids = [r["id"] for r in recs]
        self.pc_hist_cb.config(values=[self.pc_label(r) for r in recs])
        cur = self.records.get(self.pc_rid)
        self.pc_hist_var.set(self.pc_label(cur) if cur else (f"{pc_key_label()} on an item in game" if not recs else ""))
        tv = getattr(self, "pc_hist_tv", None)
        if tv is not None:
            from .pricefmt import fmt_div
            self._pc_hist_quiet = True
            try:
                tv.delete(*tv.get_children())
                for r in recs:
                    it = r.get("item") or {}
                    price = fmt_div(r["est"]) if r.get("est") is not None and not r.get("skip") else \
                        ("…" if r.get("state") in ("queued", "pricing") else "-")
                    tv.insert("", "end", iid=str(r["id"]), values=(it.get("name") or it.get("base") or "item", price,
                                                                   time.strftime("%H:%M", time.localtime(r.get("time", 0)))))
                if cur is not None and tv.exists(str(cur["id"])):
                    tv.selection_set(str(cur["id"]))
                    tv.see(str(cur["id"]))
            finally:
                self._pc_hist_quiet = False
            if recs:
                self.pc_hist_empty.place_forget()
            else:
                self.pc_hist_empty.place(relx=0.5, rely=0.5, anchor="center")

    def pc_pick_hist(self):
        i = self.pc_hist_cb.current()
        ids = getattr(self, "_pc_hist_ids", [])
        if 0 <= i < len(ids) and ids[i] in self.records:
            self.pc_show(self.records[ids[i]])

    # ---------------------------------------------------------------- showing it
    def pc_show(self, rec, card_only=False):
        if rec is not None and getattr(self, "pp_win", None) is not None:
            self.pcpop_refresh(rec)                      # 2.113.0: the card over the game follows
        if not hasattr(self, "pc_left"):
            return
        self._pc_card_only = card_only and rec is not None and rec["id"] == getattr(self, "pc_rid", None)
        old = list(self.pc_left.winfo_children())
        if rec is not None and old:                      # 2.103.1 (feedback: a tick made the card flicker): the new
            return self._pc_show_swap(rec, old)          # card is built beside the old one, then swapped in
        for w in old:
            w.destroy()
        self._pc_show_into(rec)

    def _pc_show_swap(self, rec, old):
        holder = tk.Frame(self.pc_left, bg=C["panel2"])
        self.pcv.left = holder
        try:
            self._pc_show_into(rec, swap=(holder, old))
        finally:
            self.pcv.left = self.pc_left

    def _pc_show_into(self, rec, swap=None):
        self.pc_rid = rec["id"] if rec else None
        self.pc_open_btn, self.pc_fav_btn = self.pc_open_btn0, self.pc_fav_btn0     # (the verdict strip's)
        self.pcv.open_btn = self.pc_open_btn
        self.pc_refresh_hist()
        if rec is None:
            self.pc_verdict_paint(None)
            self.pcv.shown_rid = None                    # (no card: nothing to draw again for a new width)
        P2 = C["panel2"]
        if rec is None and getattr(self, "_pc_btnrow", None) is not None:
            try:                                         # (the Drawer: the card's buttons go with the card)
                self._pc_btnrow.destroy()
            except tk.TclError:
                pass
            self._pc_btnrow = None
        if rec is None:
            tk.Label(self.pc_left, text=f"Hover an item in game and press {pc_key_label()}.\nIt shows here with the trade "
                                        "site's listings.\n\n(Ctrl+Alt+C adds items to Bulk Pricing.)",
                     bg=P2, fg=C["muted"], font=("Segoe UI", 10), justify="left", anchor="nw").pack(fill="x", pady=12)
            self.pc_draw_list(None)
            return
        self.pc_card, _btn = self.pcv_card(self.pcv, rec, swap=swap)
        self.pc_verdict_paint(rec)                       # (2.123.2: after the card - its buttons are made with it)
        if getattr(self, "_pc_card_only", False):        # 2.103.2: a tick / a typed value - the listings stay as they
            self._pc_card_only = False                   # are (redrawing them was the flicker)
            self.pc_fav_state(rec)
            return
        self.pc_draw_list(rec)

    def pcv_card(self, v, rec, swap=None):
        """The item card with every filter and the Search button, into a view's left side. swap = (new holder, old
        widgets): built into the holder, then the old ones go and the holder shows - in one go (no flicker)."""
        P2, wrap = C["panel2"], self.pcv_wrap(v)
        same = getattr(v, "shown_rid", None) == rec["id"]        # 2.88.2: a tick on the same card keeps the scroll
        top = v.lcanvas.yview()[0] if same else 0
        v.shown_rid, v.card_wrap = rec["id"], wrap               # 3.0.6: the width it was drawn for (pcv_fit)
        self._card_no_price = v is getattr(self, "pcv", None)     # 2.123.0 (p4): the strip says the price
        try:
            self._detail_card(v.left, rec, rec["item"], wrap)
        finally:
            self._card_no_price = False
        v.card_rows, v.card_paint, v.card_vals = self.card_rows, self.card_paint, self.card_vals   # 2.103.3: per view
        card = self.detail_card
        btn = None
        if v is getattr(self, "pcv", None) and getattr(self, "_pc_dl", False):
            btn = self._pc_card_buttons(v, rec)             # drawer build: one row, Search again first
        elif v is getattr(self, "pcv", None):                 # 2.123.2 (hotfix): under the card again
            from .style import Tooltip
            btns = tk.Frame(v.left, bg=P2)
            btns.pack(fill="x", pady=(8, 0))
            btn = self.pc_search_button(btns, rec)
            btn.pack(side="left", fill="x", expand=True)
            self.pc_search_btn = btn
            self.pc_fewer_btn = ttk.Button(btns, text=BROADEN, command=lambda: self.pc_fewer(rec))
            Tooltip(self.pc_fewer_btn, "Searches without your lowest-rated ticked mod.")
            ttk.Button(btns, text="Clear", command=self.pc_clear).pack(side="right", padx=(8, 0))
            more = tk.Frame(v.left, bg=P2)
            more.pack(fill="x", pady=(8, 0))
            self.pc_fav_btn = ttk.Button(more, text="☆ Add to favorites", command=self.pc_add_fav, state="disabled")
            self.pc_fav_btn.pack(side="left", fill="x", expand=True)
            self.pc_open_btn = trade_icon(ttk.Button(more, text="Trade Site", command=self.pc_open_trade,
                                                     state="normal" if rec.get("qid") else "disabled"))
            self.pc_open_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))
            v.open_btn = self.pc_open_btn
        else:
            btns = tk.Frame(v.left, bg=P2)
            btns.pack(fill="x", pady=(8, 0))
            btn = ttk.Button(btns, text="Search  •  filters changed" if rec.get("changed") else "Search",
                             style="Primary.TButton", command=lambda: self.reprice([rec["id"]]))
            btn.pack(side="left", fill="x", expand=True)
            if v is getattr(self, "favv", None):            # P2 (2.104.0): Open on trade site under the card
                ob = trade_icon(ttk.Button(btns, text="Trade Site", command=self.fav_open_trade,
                                           state="normal" if rec.get("qid") else "disabled"))
                ob.pack(side="left", padx=(8, 0))
                v.open_btn = ob
        note = self._detail_note(rec) if v is not getattr(self, "pcv", None) or rec.get("state") == "done" else None
        if note and not (v is getattr(self, "pcv", None) and rec.get("nomatch")):
            tk.Label(v.left, text=note[0], bg=P2, fg=note[1], font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=wrap).pack(fill="x", pady=(8, 0))
        if swap:
            holder, old = swap
            for w in old:
                w.destroy()
            holder.pack(fill="both", expand=True)
        # 2.128.0 (feedback: froze here after a theme change - "not responding", stuck in update_idletasks): the
        # scroll goes back once the card is laid out, without forcing every pending resize of the app right now
        self.root.after_idle(lambda: v.lcanvas.winfo_exists() and v.lcanvas.yview_moveto(top))
        # 3.0.6: (was a second draw 250 ms later, racing the resize's own) - drawn before the page had its width, it
        # is drawn again once it has it: pcv_fit compares with card_wrap
        return card, btn

    def pc_entries(self, rec):
        """The listings behind this item's price: the search the price came from (its first 10)."""
        stages = rec.get("stages") or []
        st = next((s for s in stages if s.get("qid") and s.get("qid") == rec.get("qid")), None) or \
            next((s for s in stages if s.get("ids")), None)
        ids = (st or {}).get("ids") or []
        return [RAW_LISTINGS[i] for i in ids if i in RAW_LISTINGS], (st or {}).get("total", rec.get("total") or 0), \
            len(ids)

    def pc_draw_list(self, rec):
        self.pcv_list(self.pcv, rec)
        self.pc_cards = self.pcv.cards
        self.pc_fav_state(rec)

    def pcv_list(self, v, rec):
        v.open_btn.config(state="normal" if rec and rec.get("qid") else "disabled")
        if rec is None:
            return self.pcv_entries(v, None, 0, 0, "")
        st = rec["state"]
        if st != "done":
            self.pcv_entries(v, None, 0, 0, "" if v is getattr(self, "pcv", None) else   # (the strip says it)
                             "Searching the trade site…" if st == "pricing" else
                             ("Couldn't search" if st == "error" else "Waiting in line…"))
            if st == "error" and v is getattr(self, "favv", None):     # (Price Checks: the verdict strip says it)
                why = rec.get("label") or "The trade site didn't answer."
                low = why.lower()
                tip = ("Too many filters for one search: untick a few mods." if "complex" in low else
                       "Pick a league in Settings." if "league" in low else "Wait a moment and try again.")
                self.pc_why_box(v, rec, "Couldn't search", f"{why}\n{tip}",
                                fewer="complex" in low and len(self.pc_ticked(rec)) > 1)
            return
        entries, total, n = self.pc_entries(rec)
        self.pcv_entries(v, entries, total, n)
        if not total and not n and v is getattr(self, "favv", None):
            on = len(self.pc_ticked(rec))                    # P2: Favorites says why too
            self.pc_why_box(v, rec, "No listings matched these filters",
                            (f"{on} mod filter{'s are' if on != 1 else ' is'} on. " if on else "")
                            + (f"Press {BROADEN} to try {broaden_offer(rec)['next']}." if broaden_offer(rec) else
                               "Untick the rarest mod or lower a Min, then press Search."))

    def pc_ticked(self, rec):
        """P1 (2.103.0): the card's ticked mods, top to bottom (the card on screen)."""
        v = self._card_view(rec)                            # P2: Price Checks or Favorites, whichever shows it
        if v is None:
            return []
        rows = v.card_rows or {}
        return [m for _i, (m, on, _r) in sorted(rows.items()) if on and m.get("sid")]

    def pc_why_box(self, v, rec, title, text, fewer=False):
        """P1 (2.103.0): a price check that found nothing says why and what to try, with the buttons for it."""
        box = tk.Frame(v.lst, bg=C["panel2"], padx=16, pady=12, highlightthickness=1, highlightbackground=C["red"])
        box.pack(fill="x", pady=(12, 0))
        tk.Label(box, text=title, bg=C["panel2"], fg=C["red"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(box, text=text, bg=C["panel2"], fg=C["text"], anchor="w", justify="left",
                 wraplength=520).pack(fill="x", pady=(4, 0))
        row = tk.Frame(box, bg=C["panel2"])
        row.pack(fill="x", pady=(8, 0))
        self.pc_search_button(row, rec).pack(side="left")
        if fewer:
            b = ttk.Button(row, text=BROADEN, command=lambda: self.pc_fewer(rec))
            b.pack(side="left", padx=(8, 0))
            from .style import Tooltip
            Tooltip(b, "Searches without your lowest-rated ticked mod.")
        v.why_box = box
        return box

    def pc_fewer(self, rec):
        """Broaden Search when the search was too big for the trade site: without the lowest-rated ticked mod
        (engine.fewer_offer - the same pick as the orange button's), then search again."""
        from .engine import fewer_offer
        from .trade import ov_key
        ticked = self.pc_ticked(rec)
        b = fewer_offer(rec, ticked) if ticked else None
        m = next((x for x in ticked if ov_key(x) == b["drop"]), None) if b else None
        if m is None:
            return self.reprice([rec["id"]])
        self.toggle_mod(rec, m, False)
        self.status_text, self.status_until = f"Searched without: {m.get('text', '')[:60]}", time.time() + 6
        self.reprice([rec["id"]])

    def pcv_entries(self, v, entries, total, n, head=None):
        """The listings as cards (entries None: only the heading)."""
        for w in v.lst.winfo_children():
            w.destroy()
        v.cards = []
        v.list_shown, v.list_w = bool(entries), self._pc_list_w(v)     # 3.0.6: the width drawn for (pcv_fit)
        if entries is None:
            v.count.config(text=head or "")
            return
        v.count.config(text=f"Showing {len(entries)} of {total:,} items" if total else "No listings found")
        if n and not entries:
            tk.Label(v.lst, text="The listings aren't loaded any more - press Search to load them again.",
                     bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x", pady=8)
            return
        if v is getattr(self, "pcv", None) and getattr(self, "_pc_dl", False):
            return self._pc_table(v, entries, total, n)          # drawer build: the cheapest listings as a table
        width = v.list_w                                            # 2.97.0: the width it has (inner padx 12 + 12)
        for e in entries:
            v.cards.append(self._pc_card(v.lst, listing_facts(e), width))
        v.rcanvas.yview_moveto(0)

    def _pc_card(self, parent, f, w):
        """One listing, laid out as the trade site does (2.93.1, feedback: cleaner, like the site): the picture on the
        left; in the middle the name band, then centered groups split by thin lines - properties (raised values in
        blue), item level and requirements, the socketed / implicit lines, the mods with their tiers at the block's
        left edge (P red, S blue), the site's own totals, Corrupted, the seller's note; on the right the asking
        price, the seller and how long ago."""
        from . import themes as _th
        t = _th.ST.theme
        bg, panel = C["odd"], C["panel"]
        rk = RARITY_COL.get(f["rarity"])
        col = t.c("unique", "#af6025") if rk == "unique" else (C[rk] if rk else C["text"])
        cv = tk.Canvas(parent, width=w, height=200, bg=panel, highlightthickness=0, bd=0)
        cv.pack(fill="x", pady=(0, 8))
        blue, red = "#8888ff", "#d26e5e"
        with _th.raw():
            art_w, side = 100, 190                         # the picture column, the price column
            mx0, mx1 = art_w, max(art_w + 300, w - side - 12)
            cx = (mx0 + mx1) // 2
            box = cv.create_rectangle(mx0, 0, mx1, 199, fill=bg, outline=t.c(t.part("card", "border",
                                                                                     default="border_light")))
            two = bool(f["name"]) and f["name"] != f["base"]
            hh = 46 if two else 30
            name_c = _th.card_header(cv, mx0 + 2, 2, mx1 - 2, hh, col, bg)
            if two:
                cv.create_text(cx, 14, text=f["name"], fill=name_c, font=(_th.head_font(), 11, "bold"))
                cv.create_text(cx, 33, text=f["base"], fill=name_c, font=(_th.head_font(), 10, "bold"))
            else:
                cv.create_text(cx, hh // 2 + 1, text=f["base"] or f["name"], fill=name_c, font=(_th.head_font(), 11, "bold"))
            font = ("Segoe UI", 9)
            tw = mx1 - mx0 - 70
            y = hh + 12

            def sep():
                nonlocal y
                y += 1
                cv.create_line(cx - 110, y, cx + 110, y, fill=C["line"])
                y += 9

            def line(text, fill, bold=False):
                nonlocal y
                tid = cv.create_text(cx, y, text=text, fill=fill, font=("Segoe UI", 9, "bold") if bold else font,
                                     width=tw, justify="center", anchor="n")
                bb = cv.bbox(tid)
                y = (bb[3] if bb else y + 14) + 1
                return tid

            def pair(label, value, aug):
                """"Energy Shield: 211" - the label gray, the value white (blue when raised)."""
                nonlocal y
                if not value:
                    return line(label, C["muted"])
                fm = tkfont.Font(root=cv, family="Segoe UI", size=9)
                a, b = label + ": ", value
                x0 = cx - (fm.measure(a) + fm.measure(b)) // 2
                cv.create_text(x0, y, text=a, fill=C["muted"], font=font, anchor="nw")
                cv.create_text(x0 + fm.measure(a), y, text=b, fill=blue if aug else C["text"], font=font, anchor="nw")
                y += 15
            for label, value, aug in f.get("parts") or [(x, "", False) for x in f["props"]]:
                pair(label, value, aug)
            if f["ilvl"] or f["req"]:
                sep()
                if f["ilvl"]:
                    pair("Item Level", str(f["ilvl"]), False)
                if f["req"]:
                    line(f["req"], C["muted"])
            from .style import MOD_COL                     # 2.97.2: the same colors as the item card
            kc = {"implicit": MOD_COL["implicit"], "rune": MOD_COL["rune"], "enchant": MOD_COL["enchant"],
                  "fractured": MOD_COL["fractured"], "desecrated": MOD_COL["desecrated"], "crafted": MOD_COL["enchant"]}
            first = [m for m in f["mods"] if m[2] in ("enchant", "implicit", "rune")]
            rest = [m for m in f["mods"] if m not in first]
            for group in (first, rest):
                if not group:
                    continue
                sep()
                for tier, text, kind in group:
                    if tier:
                        cv.create_text(mx0 + 10, y, text=tier, anchor="nw", font=("Segoe UI", 8, "bold"),
                                       fill=red if tier[:1] == "P" else blue if tier[:1] == "S" else C["muted"])
                    line(text, kc.get(kind, MOD_COL["explicit"]))
            if f.get("pseudo"):
                y += 2
                for p in f["pseudo"]:
                    line(p, MOD_COL["pseudo"])
            if f.get("flags"):                             # Corrupted, Mirrored, Fractured ... as a mark + word
                sep()
                line(flag_text(f["flags"]), C["red"] if "corrupted" in f["flags"] else C["text"], bold=True)
            if f.get("note"):
                sep()
                line(f["note"], C["muted"])
            h_mid = y + 10
            # ---- right: asking price, seller, when
            px = w - side // 2 - 4
            py = 18
            cv.create_rectangle(w - side + 4, py - 8, w - 8, py + 46, fill=C["odd"], outline="")
            cv.create_text(px, py, text="Asking price:", fill=C["muted"], font=("Segoe UI", 9), anchor="n")
            if f["price"]:
                amt, cur = f["price"]
                amt = int(amt) if float(amt).is_integer() else amt
                cv.create_text(px, py + 18, text=f"{amt}× {cur_label(cur)}", fill=C["text"],
                               font=(_th.head_font(), 11, "bold"), anchor="n", width=side - 20, tags=("pcprice",))
            else:
                cv.create_text(px, py + 18, text="no price", fill=C["muted"], font=font, anchor="n")
            cv.create_text(px, py + 60, text=f["seller"] + (f"\nlisted {f['times']} times" if f.get("times", 1) > 1 else ""),
                           fill=C["text"], font=("Segoe UI", 9, "bold"), width=side - 16, anchor="n", justify="center")
            if f["ts"]:
                cv.create_text(px, py + 78, text="listed " + ago(f["ts"]), fill=C["muted"], font=("Segoe UI", 8),
                               anchor="n")
            # ---- left: the picture
            img = self.pc_art(f["icon"]) if SETTINGS.get("pc_art", True) else None
            if img is not None:
                cv.create_image(art_w // 2, max(hh + 8, h_mid // 2 - ART_PX // 2), image=img, anchor="n")
                cv._art = img
            elif f["icon"] and SETTINGS.get("pc_art", True):
                cv._art_url = f["icon"]
            h = max(h_mid, py + 100, ART_PX + hh + 16)
            cv.configure(height=h)
            cv.coords(box, mx0, 0, mx1, h_mid - 1)
        cv._facts = f
        return cv

    def pc_open_trade(self):
        self.open_rec_trade(self.records.get(self.pc_rid))     # 2.105.1: changes are searched first

    # ---------------------------------------------------------------- pictures (the trade site's image server)
    def _pc_art_path(self, url):
        d = P("art")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, hashlib.sha1(url.encode()).hexdigest()[:20] + ".png")

    def _pc_art_init(self):
        if not hasattr(self, "_pc_art_cache"):          # (3.0.6: Farming Strategies may ask before Price Checks is built)
            self._pc_art_cache, self._pc_art_wait = {}, set()

    def pc_art(self, url, px=ART_PX):
        """The item's picture, from the cache or loaded in the background (the cards are redrawn once it's here).
        px: its size (3.0.6: Farming Strategies' tablets are smaller)."""
        if not url or not url.startswith("https://"):
            return None
        self._pc_art_init()
        key = url if px == ART_PX else f"{url}#{px}"
        if key in self._pc_art_cache:
            return self._pc_art_cache[key]
        path = self._pc_art_path(url)
        if os.path.exists(path):
            try:
                from PIL import Image, ImageTk
                im = Image.open(path)
                if px == ART_PX:
                    im.thumbnail((px, px))
                else:
                    im = im.convert("RGBA").resize((px, max(1, round(px * im.height / max(1, im.width)))),
                                                   Image.LANCZOS)
                ph = ImageTk.PhotoImage(im, master=self.root)
                self._pc_art_cache[key] = ph
                return ph
            except Exception:
                self._pc_art_cache[key] = None
                return None
        failed = getattr(self, "_pc_art_failed", {})
        if url not in self._pc_art_wait and time.time() - failed.get(url, 0) > 600:   # a failed one: again in 10 min
            self._pc_art_wait.add(url)
            threading.Thread(target=self._pc_art_get, args=(url, path), daemon=True).start()
            self.root.after(500, self._pc_art_poll)
        return None

    def _pc_art_get(self, url, path):
        try:
            import requests
            r = requests.get(url, headers={"User-Agent": APP_UA}, timeout=10)
            if r.status_code == 200 and r.content:
                tmp = path + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(r.content)
                os.replace(tmp, path)
        except Exception:
            buglog.caught()
        finally:
            with _ART_LOCK:                              # 3.0.6: the window thread swaps the set - no lost picture
                self._pc_art_done = getattr(self, "_pc_art_done", set()) | {url}

    def _pc_art_poll(self):
        with _ART_LOCK:
            done = getattr(self, "_pc_art_done", set())
            self._pc_art_done = set()
        if not done:
            if self._pc_art_wait:
                self.root.after(500, self._pc_art_poll)
            return
        self._pc_art_wait -= done
        got = {u for u in done if os.path.exists(self._pc_art_path(u))}
        self._pc_art_failed = {**getattr(self, "_pc_art_failed", {}), **{u: time.time() for u in done - got}}
        done = got
        for v in (getattr(self, "pcv", None), getattr(self, "favv", None)):      # 2.84.0: each view with cards
            if v is not None and v.redraw and any(getattr(c, "_art_url", None) in done for c in v.cards):
                v.redraw()
        for fn in getattr(self, "_art_hooks", ()):         # 3.0.6: other pages with pictures (Farming Strategies)
            try:
                fn(done)
            except Exception:
                buglog.caught()
        card = next(iter(getattr(self, "ins_card", None) and self.ins_card.winfo_children() or []), None)
        if card is not None and getattr(card, "_art_url", None) in done and getattr(self, "ins_pick", None):
            try:                                          # 2.105.0: Market Insights' card gets its picture too
                self.ins_show(self.ins_pick[0])
            except Exception:
                buglog.caught()
        if self._pc_art_wait:
            self.root.after(500, self._pc_art_poll)
