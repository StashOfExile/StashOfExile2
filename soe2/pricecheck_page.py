"""2.80.0: Price Checks - one item at a time (feedback: copy the price checker / item panel into a new panel called
Price Checks, showing the items on the trade site). Your price check key (Ctrl+D since 2.83.1) on an item in game
opens it here: the item
card with every filter on the left, the trade site's listings as cards on the right (name band, properties, item
level, requirements, each mod with its tier, price, seller, when it was listed, the item's picture). Ctrl+Alt+C
still adds to Bulk Pricing (the old Price checks page). Owner pick (mockup C): the price card first, then the item
card (Base and Properties above Mods) and the cheapest listings as a table - beside the card in a wide window, under it
in a narrow one (the Drawer); Search again | Trade Site | Add to favorites at the bottom. No seller names on the page.

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
from .inplace import set_cfg, tv_sync
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


def req_parts(item):
    """The requirements as the item card's head row says them: ["Level 80", "Int 101"]."""
    out = []
    for r in item.get("requirements") or []:
        name, vals = _clean(r.get("name")), [_clean(v[0]) for v in r.get("values") or [] if v]
        if vals:
            out.append(f"Level {vals[0]}" if name.lower() == "level" else f"{name[:3].title()} {vals[0]}")
    return out


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

# 3.0.6 (the waystone had no picture): the T15 waystone's art, the "Waystone" picture for every tier (a tier's
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
            "req_parts": req_parts(it),
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


# Price Checks (owner pick, mockup C): how sure the price is - a mark and a word (the wording the card over the game
# uses, pcpop.py), never a color alone
CONF_CHIP = {"high": ("✓", "High confidence", "good"), "medium": ("~", "Medium confidence", "orange"),
             "low": ("!", "Low confidence", "orange")}     # 3.0.6 (owner): High / Medium / Low, the word "confidence"
WIDE_PX = 1100          # Price Checks: from this page width up the listings go beside the item card; one column below


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

    def _pc_cur(self):
        """The check on the page (or None)."""
        return self.records.get(self.pc_rid) if getattr(self, "pc_rid", None) is not None else None

    # ---------------------------------------------------------------- the page
    def build_pc(self, body):
        """Price Checks (owner pick, mockup C), top to bottom: what your price check key does, your recent checks
        (a search box first), the price, then the item card (Base and Properties, Mods, Augments, Item Flags,
        Requirements) and the cheapest listings - beside the card in a wide window, under it in a narrow one (the
        Drawer). Search again | Trade Site | Add to favorites stay at the bottom."""
        self.pc_body = body
        self.pc_rid = None
        self._pc_art_init()
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
        self._pc_recent_row(body)                    # a search box, then your recent checks as chips
        # 2.123.3: the item and the listings share a divider you drag; its place is remembered (pc_card_w)
        cw = max(360, int(SETTINGS.get("pc_card_w", 520) or 520))
        wrap = Splitter(body, width=cw, lo=360, keep=380, on_set=self._pc_pane_saved, bg=C["panel"])
        self.limit_banner(body, wrap)                # 2.103.3: the "Staying under the limits" line
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.pc_pane = wrap
        left, right = wrap.left, wrap.right
        left.config(bg=C["panel"])
        right.config(bg=C["panel"])
        # owner: the price card on top of the item card's column and Search again | Trade Site | Add to favorites at
        # its bottom - as wide as that column (the listings sit beside it in a wide window). Packed with an item.
        self._pc_verdict_row(left)                   # the price, how sure, how it was worked out
        self._pc_foot_build(left)
        self.pc_hist_var = tk.StringVar()                    # (the old dropdown: kept for its callers, never shown)
        self.pc_hist_cb = ttk.Combobox(left, textvariable=self.pc_hist_var, state="readonly")
        self.pc_hist_cb.bind("<<ComboboxSelected>>", lambda e: self.pc_pick_hist())
        # ---- left: the item card; in a narrow window the listings follow it in the same column
        self.pc_lcanvas, inner = self._pc_scroller(left, bg_key="panel")
        self.pc_left = tk.Frame(inner, bg=C["panel2"], padx=16, pady=12, highlightthickness=1,
                                highlightbackground=C["line"])
        self.pc_left.pack(fill="x")
        self.pc_nlist_box = tk.Frame(inner, bg=C["panel"])          # (packed in a narrow window: pc_layout)
        self.pc_ncount = self._pc_list_head(self.pc_nlist_box)
        self.pc_nlist = tk.Frame(self.pc_nlist_box, bg=C["panel"])
        self.pc_nlist.pack(fill="x")
        # ---- right: the listings (a wide window)
        self.pc_count_lbl = self._pc_list_head(right, padx=(8, 0))
        self.pc_rcanvas, self.pc_list = self._pc_scroller(right, padx=8, bg_key="panel")
        self.pcv = PCView(self.pc_left, self.pc_lcanvas, self.pc_list, self.pc_rcanvas, self.pc_count_lbl,
                          self.pc_open_btn)
        self.pcv.redraw = lambda: self.pc_draw_list(self.records.get(self.pc_rid))
        # 3.0.6 (the screen flickered): a new width draws the card again only - the listings follow their own width
        self.pcv.recard = lambda: self.pc_show(self.records.get(self.pc_rid), card_only=True)
        self._pc_wide = None
        self.pcv_fit(self.pcv, wrap, None, layout=self.pc_layout)   # (2.123.3: no fixed share - the divider decides)
        self.pc_refresh_hist()
        recs = self.pc_recs()
        self.pc_show(recs[0] if recs else None)

    def _pc_list_head(self, parent, padx=0):
        """CHEAPEST LISTINGS · 6 of 37 - the listings' heading, as the card's section heads."""
        lab = tk.Label(parent, text="", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 9, "bold"), anchor="w")
        lab.pack(fill="x", padx=padx, pady=(0, 8))
        return lab

    def pc_layout(self, width=None, check=False):
        """The page's layout for its width: wide (WIDE_PX and up) - the listings beside the item card; narrow (the
        Drawer) - one column, the listings under the card. check: -> does this width need the other layout? Else it
        is laid out (no drawing here: pcv_fit draws the card and the listings once, for their new width).
        -> True when the layout changed."""
        pane = getattr(self, "pc_pane", None)
        if pane is None:
            return False
        try:
            w = int(width if width is not None else pane.winfo_width())
        except tk.TclError:
            return False
        if w <= 1:
            return False
        wide = w >= WIDE_PX
        if check or wide == self._pc_wide:
            return wide != self._pc_wide
        self._pc_wide = wide
        v = self.pcv
        old = v.lst
        try:
            pane.set_solo(not wide)
            if wide:
                self.pc_nlist_box.pack_forget()
                v.lst, v.count, v.rcanvas = self.pc_list, self.pc_count_lbl, self.pc_rcanvas
            else:
                self.pc_nlist_box.pack(fill="x", pady=(16, 0))
                v.lst, v.count, v.rcanvas = self.pc_nlist, self.pc_ncount, self.pc_lcanvas
            if old is not v.lst:                         # (hidden now: they go without a flicker)
                for c in old.winfo_children():
                    c.destroy()
                v.cards, v.list_w = [], -1               # (drawn again once, for the width it gets: pcv_fit)
        except tk.TclError:
            pass
        return True

    def pc_layout_wide(self):
        """True: the listings are beside the item card (a wide window)."""
        return bool(getattr(self, "_pc_wide", False))

    # 2.122.0 (feedback: "Show over the game" was unclear and sat oddly in the top right): one row across the
    # top of the page says what your price check key does and lets you pick where the price shows - the same setting
    # as Settings › Price checking › Where the price shows and the card's ⚙.
    # drawer build: each choice names one place - In the app (the Drawer or your full window opens quietly on Price
    # Checks) or Price check overlay (the card over the game; the app stays put). Stored as before: pc_popup.
    PC_WHERE = ("In the app", "Price check overlay")

    def _pc_where_row(self, body):
        from .style import SegBar, Tooltip
        row = tk.Frame(body, bg=C["panel"])               # (its padding is the pack's: flowify places inside it)
        row.pack(fill="x", padx=12, pady=8)
        self.pc_where_lbl = tk.Label(row, text="", bg=C["panel"], fg=C["text"], font=("Segoe UI", 10))
        self.pc_where_lbl.pack(side="left", padx=(0, 8))
        # owner (mockup C): a plain switch - the picked one says "✓" and its word, never orange
        self.pc_where = SegBar(row, list(self.PC_WHERE), value=self.PC_WHERE[0], size=9, pad=(12, 4),
                               command=self._pc_where_pick, plain=True)
        self.pc_where.pack(side="left")
        tip = tk.Label(row, text="ⓘ", bg=C["panel"], fg=C["muted"], font=("Segoe UI", 10), cursor="question_arrow")
        tip.pack(side="left", padx=(8, 0))
        Tooltip(tip, "In the app: the Drawer, or your Full window, opens on Price Checks and the game keeps the "
                     "keyboard. Ctrl+Shift+Space or Esc puts it away. Price check overlay: a card over the game with "
                     "the price. The app stays put and Price Checks has it next time. Every check is kept in Recent.")
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
            self.pc_where_lbl.config(text=f"{pc_key_label()} shows the price")
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

    # ---------------------------------------------------------------- Recent (a search box, then chips)
    def _pc_recent_row(self, body):
        """p6 (feedback: the Recent table took a quarter of the card's side): the last checks as chips - a search box
        first (it filters the chips), History › on the right."""
        from .style import Tooltip
        row = tk.Frame(body, bg=C["panel"])
        row.pack(fill="x", padx=12, pady=(0, 12))
        box = tk.Frame(row, bg=C["odd"], highlightthickness=1, highlightbackground=C["line"])
        box.pack(side="left", padx=(0, 8))
        tk.Label(box, text="⌕", bg=C["odd"], fg=C["muted"], font=("Segoe UI Symbol", 10)).pack(side="left", padx=(8, 0))
        self.pc_recent_q = tk.StringVar()
        ent = self.pc_recent_entry = tk.Entry(box, textvariable=self.pc_recent_q, width=22, bg=C["odd"], fg=C["text"],
                                              insertbackground=C["text"], relief="flat", font=("Segoe UI", 9),
                                              highlightthickness=0, bd=0)
        ent.pack(side="left", padx=(4, 8), ipady=4)
        ph = tk.Label(box, text="Search recent checks", bg=C["odd"], fg=C["muted"], font=("Segoe UI", 9))
        ph.bind("<Button-1>", lambda e: ent.focus_set())

        def placeholder(_e=None):
            try:
                if self.pc_recent_q.get() or ent.focus_get() is ent:
                    ph.place_forget()
                else:
                    ph.place(in_=ent, x=0, rely=0.5, anchor="w")
            except (tk.TclError, KeyError):
                pass
        for ev in ("<FocusIn>", "<FocusOut>"):
            ent.bind(ev, placeholder, add="+")
        ent.bind("<Escape>", lambda e: self.pc_recent_q.set(""))
        self.pc_recent_q.trace_add("write", lambda *_: (placeholder(), self.pc_recent_paint()))
        ent.after(200, placeholder)
        Tooltip(box, "Filters your recent checks by name or base. History › has every check.")
        self.pc_recent = tk.Frame(row, bg=C["panel"])
        self.pc_recent.pack(side="left", fill="x", expand=True)
        self.pc_recent_all = tk.Label(row, text="History ›", bg=C["panel"], fg=C["muted"], cursor="hand2",
                                      font=("Segoe UI", 9))
        self.pc_recent_all.pack(side="right")
        self.pc_recent_menu = tk.Menu(self.pc_recent_all, tearoff=0, bg=C["panel2"], fg=C["text"],
                                      activebackground=C["accent"])
        self.pc_recent_all.bind("<Button-1>", lambda e: self.shell.open_tab("pricecheck", "History"))
        Tooltip(self.pc_recent_all, "Every item you priced, on its own page")
        self.pc_recent.bind("<Configure>", self._pc_recent_resized, add="+")
        flowify(row)                               # D3: History › drops under the chips when it is narrow

    PC_CHIPS = 8

    def _pc_why_resized(self, e, lab=None):
        lab = lab if lab is not None else self.pc_v_why
        w = max(200, e.width - 8)
        if abs(int(lab.cget("wraplength") or 0) - w) >= 8:
            lab.config(wraplength=w)

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
        from .pclist import matches
        box = getattr(self, "pc_recent", None)
        if box is None:
            return
        allrecs = self.pc_recs()
        qv = getattr(self, "pc_recent_q", None)
        q = qv.get().strip() if qv is not None else ""
        recs = [r for r in allrecs if matches(r, q, "All")] if q else allrecs
        room = max(200, box.winfo_width() or 900)
        # UI rule 22: a tick or a new price on the same checks only re-colors the chips - they are built again
        # only when the list, a chip's words or the room changed. The one shown: outlined and marked ▸ (not color alone)
        want = []
        for r in recs[:self.PC_CHIPS]:
            it = r.get("item") or {}
            price = fmt_div(r["est"]) if r.get("est") is not None and not r.get("skip") else \
                ("…" if r.get("state") in ("queued", "pricing") else "no price")
            on = r["id"] == self.pc_rid
            t = f"{(it.get('name') or it.get('base') or 'item')[:22]} · {price}"
            want.append((r["id"], ("▸ " if on else "") + t, C["text"] if on else C["muted"],
                         C["text"] if on else C["line"]))
        have = getattr(self, "pc_chips", None) or {}
        shown = want[:len(have)]                          # (a chip that did not fit stays out while nothing changed)
        if shown and list(have) == [w[0] for w in shown] and all(b.winfo_exists() for b in have.values()) and \
                getattr(self, "_pc_chip_room", None) == room and \
                [b.cget("text").replace("▸ ", "") for b in have.values()] == [w[1].replace("▸ ", "") for w in shown]:
            for rid, text, fg, hb in shown:
                set_cfg(have[rid], text=text, fg=fg, highlightbackground=hb)
        else:
            self._pc_chip_room = room
            for w in box.winfo_children():
                w.destroy()
            self.pc_chips = {}
            if not recs:
                tk.Label(box, text=f"No recent check has “{q}”." if q and allrecs else
                         f"Your last {PC_MAX} checks show here.", bg=C["panel"], fg=C["muted"],
                         font=("Segoe UI", 9)).pack(side="left")
            used = 0
            for rid, text, fg, hb in want:
                b = tk.Label(box, text=text, bg=C["panel2"], fg=fg, font=("Segoe UI", 9),
                             padx=8, pady=2, cursor="hand2", highlightthickness=1, highlightbackground=hb)
                used += b.winfo_reqwidth() + 6
                if used > room and self.pc_chips:
                    b.destroy()
                    break
                b.pack(side="left", padx=(0, 8))
                b.bind("<Button-1>", lambda e, rid=rid: self.records.get(rid) and self.pc_show(self.records[rid]))
                self.pc_chips[rid] = b
        m = self.pc_recent_menu
        m.delete(0, "end")
        for r in allrecs:
            m.add_command(label=self.pc_label(r), command=lambda rid=r["id"]: self.records.get(rid) and
                          self.pc_show(self.records[rid]))
        self.pc_recent_all.config(fg=C["text"] if allrecs else C["muted"])

    # ---------------------------------------------------------------- the price (a card at the top)
    def _pc_verdict_row(self, body):
        """The price, big; how sure beside it (a mark and a word, plain); ⓘ how it was worked out (one hover); one line
        under it (while searching: the last price and when). As tall in every state - nothing below it jumps."""
        ns = self._pc_vns = self.price_card_build(body)
        self.pc_verdict, self.pc_v_big, self.pc_v_how = ns.frame, ns.big, ns.how
        self.pc_v_info, self.pc_v_info_tip, self.pc_v_why = ns.info, ns.info_tip, ns.why

    def price_card_build(self, parent, k=1.0):
        """The price card (Price Checks, and Bulk Pricing's picked item - k: its scale, soe2/cardscale.py): the price,
        big; how sure beside it - a mark and a word, plain (no box); one line under it. Owner: tight - little room
        around the price. One height in every state. -> its parts (price_card_paint fills them)."""
        import tkinter.font as tkf
        import types
        from .cardscale import font_size
        from .style import Tooltip
        P2 = C["panel2"]
        px, py = (12 if k >= 1 else 8), 4               # (owner, round 2: little room around the price)
        f = tk.Frame(parent, bg=P2, padx=px, pady=py, highlightthickness=1, highlightbackground=C["line"])
        top = tk.Frame(f, bg=P2)
        top.pack(fill="x")
        big = tk.Label(top, text="", bg=P2, fg=C["text"], font=("Segoe UI", font_size(22, k), "bold"), anchor="w",
                       bd=0, pady=0)
        big.pack(side="left")
        how = tk.Label(top, text="", bg=P2, fg=C["text"], font=("Segoe UI", font_size(10, k)), bd=0, padx=0,
                       pady=0)                                 # (how sure: a mark and a word, never in a box)
        low = tk.Frame(f, bg=P2)
        low.pack(fill="x")
        info = tk.Label(low, text="", bg=P2, fg=C["muted"], font=("Segoe UI", font_size(9, k)), anchor="nw",
                        cursor="question_arrow", bd=0, pady=0)
        info_tip = Tooltip(info, "")
        why = tk.Label(low, text="", bg=P2, fg=C["muted"], font=("Segoe UI", font_size(9, k)), anchor="nw",
                       justify="left", bd=0, pady=0)
        why.pack(side="left", fill="x", expand=True)
        why.bind("<Configure>", lambda e, lab=why: self._pc_why_resized(e, lab))   # (2.128.0: only a real change)
        try:                                             # one height for every state: the big line and two small ones
            bl = tkf.Font(font=big.cget("font")).metrics("linespace")
            sl = tkf.Font(font=why.cget("font")).metrics("linespace")
            f.config(height=bl + 2 * sl + 2 * py + 2)
            f.pack_propagate(False)
        except tk.TclError:
            pass
        return types.SimpleNamespace(frame=f, big=big, how=how, info=info, info_tip=info_tip, why=why, k=k)

    def _pc_foot_build(self, body):
        """Search again (the page's one orange button) | Trade Site | Add to favorites, then Broaden Search (too many
        filters for one search); Clear on the right - at the bottom of the page, always in view."""
        from .style import Tooltip
        P2 = C["panel2"]
        self.pc_foot = tk.Frame(body, bg=P2, highlightthickness=1, highlightbackground=C["line"])
        f = self.pc_foot_row = tk.Frame(self.pc_foot, bg=P2)
        f.pack(fill="x", padx=12, pady=8)
        btn = self.pc_search_btn = ttk.Button(f, text="Search again", style="Primary.TButton",
                                              command=lambda: self._pc_cur() and self.pc_search_go(self._pc_cur()))
        btn._search_tip = Tooltip(btn, "Searches the trade site with these filters.")
        btn.pack(side="left")
        self.pc_fewer_btn = ttk.Button(f, text=BROADEN, command=lambda: self._pc_cur() and
                                       self.pc_fewer(self._pc_cur()))
        self.pc_fewer_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.pc_fewer_btn, "Searches without your lowest-rated ticked mod.")
        self.pc_open_btn0 = self.pc_open_btn = trade_icon(ttk.Button(f, text="Trade Site", command=self.pc_open_trade,
                                                                     state="disabled"))
        self.pc_open_btn.pack(side="left", padx=(8, 0))
        Tooltip(self.pc_open_btn, "Opens this search on the trade site")
        self.pc_fav_btn0 = self.pc_fav_btn = ttk.Button(f, text="☆ Add to favorites", command=self.pc_add_fav,
                                                        state="disabled")
        self.pc_fav_btn.pack(side="left", padx=(8, 0))
        clear = self.pc_clear_lbl = tk.Label(f, text="Clear", bg=P2, fg=C["muted"], font=("Segoe UI", 9),
                                             cursor="hand2")
        clear.pack(side="right", padx=(8, 0))
        clear.bind("<Button-1>", lambda e: self.pc_clear())
        Tooltip(clear, "Clears every check on Price Checks, in Recent and History. Bulk Pricing and Favorites stay.")
        flowify(f)
        self._pc_foot_show(self.pc_fewer_btn, False)

    def _pc_foot_show(self, w, on):
        """Show / hide one of the footer's buttons (the row wraps by itself: flowify)."""
        row = self.pc_foot_row
        kids = getattr(row, "_flow_kids", None) or []
        k = next((k for k in kids if k["w"] is w), None)
        if k is None or k["hidden"] == (not on):
            return
        k["hidden"] = not on
        if not on:
            w.place_forget()
        try:
            row._flow_layout()
        except tk.TclError:
            pass

    def pc_verdict_paint(self, rec):
        """The price card says it with a mark and a word, never by color alone. In place: only its words change."""
        f = getattr(self, "pc_verdict", None)
        if f is None:
            return
        foot = getattr(self, "pc_foot", None)
        if rec is None:
            f.pack_forget()
            if foot is not None:
                foot.pack_forget()
            return
        cv = getattr(self, "pc_lcanvas", None)
        box = cv.master if cv is not None else None       # (the item card's scroller, in the same column)
        gap = int(getattr(cv, "_gap_w", 0) or 0)       # owner: the price box ends where the card ends (not over
        if foot is not None and not foot.winfo_manager():     # the scroll bar's strip); the buttons keep the column
            foot.pack(side="bottom", fill="x", pady=(8, 0), **({"before": box} if box is not None else {}))
        if not f.winfo_manager():
            f.pack(side="top", fill="x", pady=(0, 12), padx=(0, gap), **({"before": box} if box is not None else {}))
        fewer = self.price_card_paint(self._pc_vns, rec)
        try:                                             # the footer's buttons follow the check
            self.pc_search_paint(self.pc_search_btn, rec)
            self._pc_foot_show(self.pc_fewer_btn, fewer)
            self.pc_open_btn.config(state="normal" if rec.get("qid") else "disabled")
        except tk.TclError:
            pass

    def price_card_paint(self, ns, rec):
        """The price card's words for this item (a mark and a word, never color alone). In place: only its words
        change. -> True when Broaden Search should be offered (too many filters for one search)."""
        from .pricefmt import fmt_div
        st, fewer = rec.get("state"), False
        on = len(self.pc_ticked(rec))
        info, tip, chip, why = "", "", None, ""
        if st == "done" and rec.get("est") is not None and not rec.get("nomatch"):
            conf = str(rec.get("conf") or "").lower()
            mark, word, ck = CONF_CHIP.get(conf, ("~", "Confidence unknown", "orange"))
            chip = (f"{mark} {word}", C[ck])
            big = ("≥ " if rec.get("partial") else "≈ ") + fmt_div(rec["est"])
            _e, total, n = self.pc_entries(rec)
            total = rec.get("total") if rec.get("total") is not None else total
            info = (f"from the {min(n, 5)} cheapest of {total:,} listing{'s' if total != 1 else ''}" if n else
                    f"from {total:,} listing{'s' if total != 1 else ''}")     # (owner: no ⓘ - the line says how)
            try:
                tip = self.pc_price_how(rec)[1]
            except Exception:
                buglog.caught()
            if rec.get("manual"):
                why = "Check by hand: " + (rec.get("manual_why") or "the listings are priced far apart") + "."
            else:
                note = self._detail_note(rec)
                why = note[0] if note else (rec.get("memory") or "").replace("Memory: ", "Last time: ", 1)
            ns.big.config(text=big, fg=C["good"])
        elif st == "done":
            ns.big.config(text="✕ No match" if not rec.get("manual") else "! Check by hand", fg=C["red"])
            why = ("No listings matched these filters. " if not rec.get("manual") else "") + \
                (f"{on} mod filter{'s are' if on != 1 else ' is'} on. " if on else "") + \
                "Untick the rarest mod or lower a Min, then search again."
            if broaden_offer(rec):                       # owner: the next step, one click (3.0.6: every item)
                why = f"Press {BROADEN} to try {broaden_offer(rec)['next']}."
        elif st == "error":
            reason = rec.get("label") or "The trade site didn't answer."
            low = reason.lower()
            hint = ("Too many filters for one search: untick a few mods." if "complex" in low else
                    "Pick a league in Settings." if "league" in low else "Wait a moment and try again.")
            ns.big.config(text="✕ Couldn't search", fg=C["red"])
            why = f"{reason}. {hint}" if not reason.endswith(".") else f"{reason} {hint}"
            fewer = "complex" in low and on > 1
        else:
            ns.big.config(text="… Searching the trade site" if st == "pricing" else "… Waiting in line",
                          fg=C["muted"])
            if rec.get("est") is not None and rec.get("priced_at") and not rec.get("nomatch"):
                why = f"Last price: ≈ {fmt_div(rec['est'])}, {ago(rec['priced_at'])}"
        try:
            if chip:
                set_cfg(ns.how, text=chip[0], fg=chip[1])
                if not ns.how.winfo_manager():
                    ns.how.pack(side="left", padx=(8, 0))
            else:
                ns.how.pack_forget()
            if info:
                ns.info.config(text=info)
                ns.info_tip.text = tip or info
                if not ns.info.winfo_manager():
                    ns.info.pack(side="left", before=ns.why)
            else:
                ns.info.pack_forget()
            ns.why.config(text=(" · " + why) if info and why else why)
        except tk.TclError:
            pass
        return fewer

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

    # ---------------------------------------------------------------- the cheapest listings (a table)
    @staticmethod
    def _pc_matter(f, rec):
        """A listing's mods that matter: the ones your search ticked (by their wording, numbers aside), else its first
        two; then its flags as a mark and a word ("✚ Desecrated")."""
        from .mods import norm
        from .trade import mod_impact
        mods = [t for _tier, t, kind in f["mods"] if kind not in ("implicit", "enchant", "rune")]
        want = set()
        for m in ((rec or {}).get("item") or {}).get("mods") or []:
            try:
                if m.get("sid") and mod_impact(rec, m) != "ignore":
                    want.add(norm(m.get("text") or ""))
            except Exception:
                buglog.caught()
        hit = [t for t in mods if norm(t) in want]
        out = hit or mods[:2]
        fl = flag_text(f.get("flags"))
        return " · ".join(out + ([fl] if fl else []))

    def _pc_table(self, v, entries, total, n, rec=None):
        """The cheapest listings as small item cards (soe2/listingcard.py; no seller names). A click on a card opens
        the whole item under its mods (▸)."""
        v.count.config(text=f"CHEAPEST LISTINGS · {len(entries)} of {total:,}" if total else
                       "CHEAPEST LISTINGS · none found")
        if n and not entries:
            tk.Label(v.lst, text="The listings aren't loaded any more - press Search again to load them.",
                     bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x", pady=8)
            return
        if not entries:
            return
        from . import listingcard
        listingcard.draw(self, v, entries, rec)       # 3.0.7: each listing as a small item card
        if v.rcanvas is not getattr(self, "pc_lcanvas", None) and not getattr(v, "keep_scroll", False):
            v.rcanvas.yview_moveto(0)                    # (a narrow window, or Bulk Pricing: the card's scroll stays)

    def pcv_fit(self, v, page, side, lo=380, share=0.32, hi=620, layout=None):
        """2.97.0 (feedback: scale to fit, nothing cut off): the card's side takes about a third of the page (wider
        windows: fewer wrapped lines, so no scrollbar), and the card and the listings are drawn again for the width
        they have when the window changes size - once per resize (after a pause, and only when the mouse is let
        go). layout(width, check=...): Price Checks lays the page out for its width (pc_layout) the same way."""
        state = {"page": 0, "after_card": None, "after_list": None, "after_layout": None}

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
                try:                                     # 3.0.6 (the Drawer lagged when dragged
                    held = self._drawer_mouse_down()     # and resized): still dragging - drawn once, on release
                except Exception:
                    held = False
                if held:
                    state[slot] = self.root.after(150, go)
                    return
                if what == "layout":
                    try:
                        if layout(None):                 # (laid out again: the card and the listings follow)
                            later("card")
                            later("list")
                            if not getattr(v, "list_shown", False):
                                v.redraw and v.redraw()  # (no listings: only the heading - cheap)
                    except Exception:
                        self.log_error("the price check view")
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

        # 3.0.6 (the listings view updated inconsistently and was sometimes crunched): compared with the
        # width each was DRAWN for (not the last resize), so one drawn before the page had its width is drawn again
        # once it has it - the end state no longer depends on timing
        def card_off():
            return getattr(v, "shown_rid", None) is not None and \
                (abs(self.pcv_wrap(v) - (getattr(v, "card_wrap", 0) or 0)) >= 8 or self.pc_scale_off(v))

        def list_off():
            return getattr(v, "list_shown", False) and \
                abs(self._pc_list_w(v) - (getattr(v, "list_w", 0) or 0)) >= 8

        def canvas_cfg(e):
            if card_off():
                later("card")
            if list_off():
                later("list")

        def layout_cfg(e):
            if layout(e.width, check=True):
                if getattr(self, "_pc_wide", None) is None:
                    layout(e.width)                      # (the first time: at once - nothing is drawn yet)
                else:
                    later("layout")
        if side is not None:
            page.bind("<Configure>", page_cfg, add="+")
        if layout is not None:
            page.bind("<Configure>", layout_cfg, add="+")
        v.lcanvas.bind("<Configure>", canvas_cfg, add="+")     # (a narrow window: the listings are on this side)
        v.rcanvas.bind("<Configure>", canvas_cfg, add="+")

    def _pc_pane_saved(self, w=None):
        """The divider was let go (Splitter keeps it between 360 px and all but 380 px of the page): remember it."""
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
        if v is getattr(self, "pcv", None):              # (Price Checks: the card in its own box - 16 px inside, a line)
            return max(300, cw - 2 * 16 - 2 - 12) if cw > 50 else 420
        return max(330, cw - 24 - 12) if cw > 50 else 330

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
        # 3.0.6 (janky: flickers, sometimes cropped with a scroll bar, sometimes not): the bar's
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
                elif not need and sb.winfo_ismapped() and not getattr(cv, "_sb_later", None):
                    def again():                         # (held after a few quick flips: looked at once more when
                        cv._sb_later = None              # the hold is over - it fits now, so it goes)
                        fit()
                    cv._sb_later = cv.after(2100, again)
            except tk.TclError:
                pass
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(win, width=e.width), fit()))
        inner.bind("<Configure>", fit)
        cv._sb = sb
        cv._gap_w = sb.winfo_reqwidth()                  # (the strip kept for the bar: what sits above it lines up)

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
        if pc_key_is_copy():
            return keys.copy_recent() and not keys.combo_recent()
        return keys.pc_recent()

    def pc_take(self, text):
        """An item for Price Checks: priced first in line, shown on the page (the app comes to the front if you
        want - Settings › Keybinds)."""
        cur = self.copy_currency(text)                   # (one intake with Bulk Pricing: app.copy_currency)
        try:                                             # 2.128.0: a Favours reward - learn what it looks like
            self.favours_copy_learn(text)                # (2.129.3: exchange items, and ★ uniques - never priced)
        except Exception:
            buglog.caught()
        if cur:                                          # 2.129.0 (feedback): omens, essences, lineage gems, every
            self.status_text, self.status_until = f"Pricing {cur[0]}...", time.time() + 10     # currency: their
            self.stack_price(cur[0], cur[1], loud=True)  # going rate on poe.ninja's exchange - never a trade search
            return None
        rid = self.add_item_text(text, src="pc")
        if rid is None:                                  # which kind of item, and why it isn't priced (one line)
            self.status_text = self.status_line_unpriced(text)
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
            # 2.123.3: Overlay + Here - the app shows it too. 2.129.3 (feedback: the app was still brought to the
            # front - it should only use the overlay): while the game is
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
                rows = []
                for r in recs:
                    it = r.get("item") or {}
                    price = fmt_div(r["est"]) if r.get("est") is not None and not r.get("skip") else \
                        ("…" if r.get("state") in ("queued", "pricing") else "-")
                    rows.append((str(r["id"]), dict(values=(it.get("name") or it.get("base") or "item", price,
                                                            time.strftime("%H:%M", time.localtime(r.get("time", 0)))))))
                tv_sync(tv, rows)                       # (UI rule 22: same checks - only the changed cells are set)
                if cur is not None and tv.exists(str(cur["id"])):
                    if tv.selection() != (str(cur["id"]),):
                        tv.selection_set(str(cur["id"]))
                    tv.see(str(cur["id"]))
                elif tv.selection():
                    tv.selection_set(())
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
        if rec is not None and not card_only and self._pc_card_same(rec):
            # UI rule 22: a new price (or the search starting) on the same item - the card stays as it is; the price,
            # the buttons and the listings follow
            self.pc_refresh_hist()
            self.pc_verdict_paint(rec)
            self.pc_draw_list(rec)
            return None
        old = list(self.pc_left.winfo_children())
        if rec is not None and old:                      # 2.103.1 (feedback: a tick made the card flicker): the new
            return self._pc_show_swap(rec, old)          # card is built beside the old one, then swapped in
        for w in old:
            w.destroy()
        self._pc_show_into(rec)

    def _pc_card_sig(self, rec):
        """What the item card on Price Checks shows, in short: the same -> the card need not be built again."""
        return self.card_sig(rec, self.pcv_wrap(self.pcv))

    def card_sig(self, rec, wrap):
        """What an item card shows (Price Checks, Bulk Pricing), in short, at this width: the same -> the card need not
        be built again (a new price, a search starting)."""
        from .trade import mod_impact
        from . import themes as TH
        it = rec.get("item") or {}
        try:
            mods = tuple((id(m), m.get("sid"), m.get("text"), mod_impact(rec, m), repr(m.get("uval")), m.get("value"))
                         for m in it.get("mods") or [])
            ask = self.pc_ask_mod(rec)
        except Exception:
            buglog.caught()
            return None
        return (rec["id"], id(it), mods, repr(sorted((rec.get("opts") or {}).items())),
                repr(sorted((rec.get("only") or {}).items())), bool(rec.get("resolved")),
                repr(sorted((SETTINGS.get("pc_fold") or {}).items())), wrap,
                id(ask) if ask is not None else None, id(TH.ST.theme))

    def _pc_card_same(self, rec):
        try:
            return rec["id"] == getattr(self, "pc_rid", None) and getattr(self.pcv, "shown_rid", None) == rec["id"] \
                and bool(self.pc_left.winfo_children()) and \
                getattr(self, "_pc_card_sig_last", None) is not None and self._pc_card_sig(rec) == self._pc_card_sig_last
        except tk.TclError:
            return False

    def _pc_show_swap(self, rec, old):
        holder = tk.Frame(self.pc_left, bg=C["panel2"])
        self.pcv.left = holder
        try:
            self._pc_show_into(rec, swap=(holder, old))
        finally:
            self.pcv.left = self.pc_left

    def _pc_show_into(self, rec, swap=None):
        self.pc_rid = rec["id"] if rec else None
        self.pcv.open_btn = self.pc_open_btn
        self.pc_refresh_hist()
        P2 = C["panel2"]
        if rec is None:
            self.pc_verdict_paint(None)
            self.pcv.shown_rid = None                    # (no card: nothing to draw again for a new width)
            self._pc_card_sig_last = None
            tk.Label(self.pc_left, text=f"No item yet. Hover an item in game and press {pc_key_label()}: its price "
                                        "and the trade site's cheapest listings show here.\n\nCtrl+Alt+C adds items "
                                        "to Bulk Pricing.", bg=P2, fg=C["muted"], font=("Segoe UI", 10),
                     justify="left", anchor="nw", wraplength=360).pack(fill="x", pady=(0, 12))
            ttk.Button(self.pc_left, text="Price check settings",
                       command=lambda: self.settings_open("Price checking", "pc_single")).pack(anchor="w")
            self.pc_draw_list(None)
            return
        self.pc_card, _btn = self.pcv_card(self.pcv, rec, swap=swap)
        self._pc_card_sig_last = self._pc_card_sig(rec)
        self.pc_verdict_paint(rec)                       # (2.123.2: after the card - its rows count the ticks)
        if getattr(self, "_pc_card_only", False):        # 2.103.2: a tick / a typed value - the listings stay as they
            self._pc_card_only = False                   # are (redrawing them was the flicker)
            self.pc_fav_state(rec)
            return
        self.pc_draw_list(rec)

    def pcv_card(self, v, rec, swap=None):
        """The item card with every filter, into a view's left side (Favorites: with its Search button under it;
        Price Checks: its buttons are at the bottom of the page). swap = (new holder, old widgets): built into the
        holder, then the old ones go and the holder shows - in one go (no flicker)."""
        P2, wrap = C["panel2"], self.pcv_wrap(v)
        same = getattr(v, "shown_rid", None) == rec["id"]        # 2.88.2: a tick on the same card keeps the scroll
        top = v.lcanvas.yview()[0] if same else 0
        v.shown_rid, v.card_wrap = rec["id"], wrap               # 3.0.6: the width it was drawn for (pcv_fit)
        pcv = v is getattr(self, "pcv", None)
        fav = v is getattr(self, "favv", None)
        self._card_no_price = pcv or fav                         # 2.123.0 (p4): the price card says the price
        try:
            if pcv:                                              # owner: the card fits the page (its scale)
                from .cardscale import WIDE                      # (the full window a bit bigger; the Drawer 1)
                wide = self.pc_layout_wide()
                self.card_fit_draw(v, v.left, rec, wrap, WIDE if wide else 1.0, self.pc_card_room() if wide else 0)
            elif fav:                                            # owner (round 2): Favorites shows the item as Price
                v.price_ns = self.price_card_build(v.left)       # Checks does - the price card, then the same card
                v.price_ns.frame.pack(fill="x", pady=(0, 12))    # in its box
                box = tk.Frame(v.left, bg=P2, padx=16, pady=12, highlightthickness=1, highlightbackground=C["line"])
                box.pack(fill="x")
                try:                                             # (the room inside its box: the scroller's 12 px
                    cw = v.lcanvas.winfo_width()                 # each side, the box's 16 and its line)
                except tk.TclError:
                    cw = 0
                self._detail_card(box, rec, rec["item"], max(228, cw - 24 - 2 * 16 - 2 - 12) if cw > 50 else
                                  max(228, wrap - 2 * 16 - 2))
                self.price_card_paint(v.price_ns, rec)
            else:
                self._detail_card(v.left, rec, rec["item"], wrap)
        finally:
            self._card_no_price = False
        v.card_rows, v.card_paint, v.card_vals = self.card_rows, self.card_paint, self.card_vals   # 2.103.3: per view
        card = self.detail_card
        btn = None
        if pcv:
            btn = self.pc_search_btn                        # (the footer's: Search again, Trade Site, favorites)
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
            note = self._detail_note(rec)
            if note:
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

    def card_fit_draw(self, v, parent, rec, wrap, base, avail):
        """Owner (the card fits the window, no scroll bar wherever it can): the item card into parent at the scale
        that fits avail px (soe2/cardscale.py; avail 0: base - the Drawer, where the listings follow the card). The
        scale found is kept for this card at this room, so a tick, a new price or a redraw for the same room draws it
        once. Built in its hidden holder before it shows (no flicker). Remembers on v what it was drawn for
        (card_k, card_h, card_avail - pcv_fit and Bulk Pricing compare with them). -> the card's canvas."""
        from . import cardscale
        sig = (self.card_sig(rec, wrap), base, int(avail) // 4)
        cache = v.__dict__.setdefault("_fit_cache", {})
        made = []

        def draw(k):
            for cv in made:                                      # (a try that didn't fit: gone before it shows)
                try:
                    cv.destroy()
                except tk.TclError:
                    pass
            made.clear()
            self._card_k = k
            try:
                cv = self._detail_card(parent, rec, rec["item"], wrap)
            finally:
                self._card_k = 1.0
            made.append(cv)
            try:
                return int(cv.cget("height"))
            except (tk.TclError, ValueError):
                return 0
        if sig in cache:
            k = cache[sig]
            h = draw(k)
        else:
            k, h = cardscale.fit(draw, avail, base)
            if len(cache) > 40:
                cache.clear()
            cache[sig] = k
        v.card_k, v.card_h, v.card_avail, v.card_base = k, h, int(avail), base
        return made[-1] if made else None

    def pc_card_room(self):
        """The px Price Checks' item card has in a wide window: its scroller's height, less the padding inside it
        and its box's (0 before the page is laid out)."""
        try:
            h = self.pc_lcanvas.winfo_height()
        except (tk.TclError, AttributeError):
            return 0
        if h <= 50:
            return 0
        for w, gap in ((getattr(self, "pc_verdict", None), 12), (getattr(self, "pc_foot", None), 8)):
            try:                                         # (the price card and the buttons not packed yet - the
                if w is not None and not w.winfo_manager():     # first item: they will take their room)
                    h -= w.winfo_reqheight() + gap
            except tk.TclError:
                pass
        pad = int(self.pc_left.cget("pady") or 0)
        return max(0, h - 2 * 4 - 2 * pad - 2)

    def pc_scale_off(self, v):
        """Is the card's scale wrong for the room it has now (a window made taller or shorter)? Only a wide window
        (the Drawer: the listings follow the card - it keeps its scale)."""
        from . import cardscale
        if v is not getattr(self, "pcv", None) or getattr(v, "shown_rid", None) is None or not self.pc_layout_wide():
            return False
        k, h, was = getattr(v, "card_k", 1.0), getattr(v, "card_h", 0), getattr(v, "card_avail", 0)
        room = self.pc_card_room()
        if room <= 0 or abs(room - was) < 8:
            return False
        if h > room and k > cardscale.KMIN:                   # (it no longer fits: smaller)
            return True
        return k < getattr(v, "card_base", 1.0) and room > was   # (more room: bigger again)

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
            self.pcv_entries(v, None, 0, 0, ("CHEAPEST LISTINGS" if st in ("pricing", "queued") else "")
                             if v is getattr(self, "pcv", None) or getattr(v, "table", False) else   # (the price
                             # card says the rest)
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
        self.pcv_entries(v, entries, total, n, rec=rec)
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

    def pcv_entries(self, v, entries, total, n, head=None, rec=None):
        """The listings (entries None: only the heading). Price Checks: a table; Favorites: as cards."""
        for w in v.lst.winfo_children():
            w.destroy()
        v.cards = []
        v.list_shown, v.list_w = bool(entries), self._pc_list_w(v)     # 3.0.6: the width drawn for (pcv_fit)
        if entries is None:
            v.count.config(text=head or "")
            return
        if v is getattr(self, "pcv", None) or getattr(v, "table", False):     # (Bulk Pricing: the same table)
            return self._pc_table(v, entries, total, n, rec)
        v.count.config(text=f"Showing {len(entries)} of {total:,} items" if total else "No listings found")
        if n and not entries:
            tk.Label(v.lst, text="The listings aren't loaded any more - press Search to load them again.",
                     bg=C["panel"], fg=C["muted"], anchor="w").pack(fill="x", pady=8)
            return
        if entries:                                      # owner (round 2): Favorites - the same listing cards (no
            from . import listingcard                    # seller names)
            listingcard.draw(self, v, entries, rec)
        v.rcanvas.yview_moveto(0)

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
