"""The cheapest listings as small in-game-style item cards (Price Checks, Bulk Pricing and Favorites share it).

Each listing: the base type's picture in its own column, in the middle of it (a rounded placeholder until it
arrives); beside it the item's name as the card's title (the unique's or the rare's name, in its rarity color) with the
base type muted next to it (under it when there's no room), "item level 82 · listed 1 d ago" muted under that; on the
right the price as the trade site has it - "2000 ×" and the currency's picture (poe.ninja's, from the art cache that
Exchange Rates fills - 3.1: no game pictures ship; its name in words when there is no picture, and on hover) - with the
"▸ Whole item" toggle under it; then the mods one per line (the tier tags in one column, the text in its mod color)
and the flags as chips. Whole item opens the item inside that card in the item card's own order and words
(names.CARD_SECTIONS): BASE AND PROPERTIES, REQUIREMENTS, AUGMENTS, ITEM FLAGS, MODS, PSEUDO FILTERS - only the
parts it has - headed as the item card heads its sections, the rows indented under them, labels muted and values
bright ("Quality" "+21%"), the seller's note as a quiet last row. No seller names anywhere (privacy). A click
anywhere on a card does what the toggle does.

Scale (soe2/cardscale.py): Price Checks' full window WIDE, Bulk Pricing BULK, else 1 - text never below MIN_PT.

UI rule 22: a search result draws the cards once; the toggle changes one card; a picture that arrives is put into its
placeholder (draw_art), the card is not built again. The pictures come from Price Checks' art cache (pc_art): loaded
in a thread, kept on disk - never a network call on the UI thread."""
import tkinter as tk
import tkinter.font as tkfont

from .cardscale import font_size
from .config import SETTINGS
from .style import C, MOD_COL, Tooltip

PIC = 78                                    # the picture's box (the art cache's size)
SHOWN_KINDS = ("explicit", "fractured", "desecrated", "crafted")
FLAG_COL = {"fractured": "fractured", "desecrated": "desecrated", "crafted": "enchant"}
OPEN, SHUT = "▾ Less", "▸ Whole item"
INDENT = 12                                 # Whole item: the rows under their section's heading
SEC_GAP = 12                                # Whole item: between two sections (the item card's gap)
CUR_PX = 22                                 # the currency's picture beside the price, at scale 1
# Whole item: a mod's kind in a word before it, as the item card says it ("Implicit · +10% to Fire Resistance")
KIND_WORDS = {"implicit": "Implicit", "enchant": "Enchant", "rune": "Rune", "fractured": "Fractured",
              "desecrated": "Desecrated"}


def kind_text(text, kind):
    w = KIND_WORDS.get(kind)
    return f"{w} · {text}" if w and not text.startswith(w) else text


def mod_color(kind):
    return MOD_COL.get({"crafted": "enchant"}.get(kind, kind), MOD_COL["explicit"])


def tier_tip(tier):
    """"P1" -> "Prefix, tier 1 (1 is the best roll)" (the item card's hover)."""
    word = {"P": "Prefix", "S": "Suffix"}.get(tier[:1].upper(), "Mod")
    return f"{word}, tier {tier[1:] or tier} (1 is the best roll)"


def amount_text(f):
    """The price's number: "2000", "2.5" ("" when it has no price)."""
    if not f["price"]:
        return ""
    amt = f["price"][0]
    return str(int(amt)) if float(amt).is_integer() else str(amt)


def price_text(f):
    """The price in words: "2000 Divine Orb" (the price's hover; "no price")."""
    from .pricecheck_page import cur_label
    if not f["price"]:
        return "no price"
    return f"{amount_text(f)} {cur_label(f['price'][1])}"


def scale_for(app, v):
    """The cards' scale on this view: Price Checks' full window WIDE, Bulk Pricing BULK, else 1 (the Drawer)."""
    from .cardscale import BULK, WIDE
    if v is getattr(app, "pcv", None):
        try:
            return WIDE if app.pc_layout_wide() else 1.0
        except Exception:
            return 1.0
    if v is getattr(app, "bulkv", None):
        return BULK
    return 1.0


def cur_icon(app, cur, k=1.0):
    """The currency's picture: poe.ninja's icon from the art cache Exchange Rates fills (the same downloads and rules as
    there), or None - its name stands in (3.1, GGG ToS 7a: no game pictures ship with the app)."""
    from .pricecheck_page import cur_label
    from .rates_view import Icons, picture_paths, url_for
    size = max(14, int(round(CUR_PX * k)))
    box = app.__dict__.setdefault("_lc_cur_icons", {})
    if size not in box:
        def ready():                                  # new pictures arrived: the listings draw again (once)
            for v in (getattr(app, "pcv", None), getattr(app, "favv", None)):     # (Bulk: its next draw)
                fn = getattr(v, "redraw", None)
                if fn:
                    try:
                        fn()
                    except Exception:
                        pass
        box[size] = (Icons(app.root, ready, size=size), {"paths": None, "at": 0.0})
    icons, st = box[size]
    try:
        import time as _t
        if st["paths"] is None or _t.time() - st["at"] > 60:
            st["paths"], st["at"] = picture_paths(), _t.time()
        name = cur_label(cur)
        url = url_for(cur, st["paths"]) or url_for(name, st["paths"])
        return icons.get(url) if url else None
    except Exception:
        return None


def _place_art(cv, img):
    """Put the picture into its box (replacing the placeholder)."""
    cv.delete("ph")
    cv.delete("art")
    cv.create_image(PIC // 2, PIC // 2, image=img, anchor="center", tags=("art",))
    cv._img = img


def _placeholder(cv):
    from . import themes as _th
    _th.round_rect(cv, 1, 1, PIC - 1, PIC - 1, 8, fill=C["panel"], outline=C["line"], tags=("ph",))


def draw_art(app, done):
    """Pictures that arrived (urls) -> into their cards' boxes. Called from Price Checks' art poll."""
    pics = getattr(app, "_lc_pics", None) or {}
    for url in done:
        keep = []
        for cv in pics.get(url, ()):
            try:
                if not cv.winfo_exists():
                    continue
                keep.append(cv)
                img = app.pc_art(url)
                if img is not None:
                    _place_art(cv, img)
            except tk.TclError:
                continue
        pics[url] = keep


def _bind_all(w, fn):
    w.bind("<Button-1>", fn, add="+")
    try:
        w.config(cursor="hand2")
    except tk.TclError:
        pass
    for c in w.winfo_children():
        _bind_all(c, fn)


class _Look:
    """One card's fonts at its scale (text never below cardscale.MIN_PT)."""

    def __init__(self, k):
        self.k = k

    def f(self, size, *style):
        return ("Segoe UI", font_size(size, self.k)) + style

    def tier_w(self, root):
        """The tier tags' column: as wide as "P10" and a gap, so the mods' text lines up."""
        try:
            return tkfont.Font(root=root, font=self.f(9)).measure("P10") + 8
        except tk.TclError:
            return 32


def _mod_grid(parent, bg, mods, wrap, look, words=False):
    """The mods one per line: the tier tags (P1 / S1, with the item card's hover) in one column, the text in its mod
    color beside it (words: its kind in a word first, as the item card says it). -> the grid."""
    g = tk.Frame(parent, bg=bg)
    tw = look.tier_w(parent)
    g.columnconfigure(0, minsize=tw)
    g.columnconfigure(1, weight=1)
    for r, (tier, text, kind) in enumerate(mods):
        tg = tk.Label(g, text=tier, bg=bg, fg=C["muted"], font=look.f(9), anchor="w", bd=0, padx=0)
        tg.grid(row=r, column=0, sticky="nw")
        if tier:
            Tooltip(tg, tier_tip(tier))
        tk.Label(g, text=kind_text(text, kind) if words else text, bg=bg, fg=mod_color(kind), font=look.f(9),
                 anchor="w", justify="left", bd=0, padx=0, wraplength=max(80, wrap - tw)).grid(
            row=r, column=1, sticky="w", pady=(0, 2))
    return g


def _flag_row(parent, bg, flags, look, chips=True):
    """The flags as a mark and a word each (the game's order), in their colors (chips: each on its own fill)."""
    from .pricecheck_page import FLAG_MARKS, flag_text
    keys = [k for k, _m, _w in FLAG_MARKS if k in (flags or ())]
    if not keys:
        return None
    fr = tk.Frame(parent, bg=bg)
    for i, k in enumerate(keys):
        col_key = FLAG_COL.get(k)
        fg = MOD_COL[col_key] if col_key else (C["red"] if "corrupted" in k else C["text"])
        if chips:
            tk.Label(fr, text=flag_text({k}), bg=C["panel"], fg=fg, font=look.f(9), padx=8, pady=1).pack(
                side="left", padx=(0, 4))
        else:
            tk.Label(fr, text=flag_text({k}), bg=bg, fg=fg, font=look.f(9), bd=0, padx=0).pack(
                side="left", padx=(0 if not i else 12, 0))
    return fr


def _detail(parent, f, wrap, bg=None, look=None):
    """The whole item, as the item card has it: its sections in the card's order and words (only those it has),
    headed as the card heads them, the rows indented under them - labels muted, values bright; the seller's note
    last, quiet."""
    from .names import CARD_SECTIONS as SEC
    bg = bg or C["panel2"]
    look = look or _Look(1.0)
    box = tk.Frame(parent, bg=bg)
    mut, txt = C["muted"], C["text"]
    n = {"heads": 0}
    inner = max(120, wrap - INDENT)

    def head(key):
        """The section's heading, as the item card's (bold, the card's size and color); -> the rows' frame."""
        tk.Label(box, text=SEC[key], bg=bg, fg=txt, font=look.f(9, "bold"), anchor="w", bd=0, padx=0).pack(
            fill="x", pady=(SEC_GAP if n["heads"] else 0, 4))
        n["heads"] += 1
        rows = tk.Frame(box, bg=bg)
        rows.pack(fill="x", padx=(INDENT, 0))
        return rows

    def pairs(rows, items):
        """Label | value rows: the labels muted in one column, the values bright beside them."""
        g = tk.Frame(rows, bg=bg)
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)
        for r, (label, value) in enumerate(items):
            if value:
                tk.Label(g, text=label, bg=bg, fg=mut, font=look.f(9), anchor="w", bd=0, padx=0).grid(
                    row=r, column=0, sticky="nw", padx=(0, 12), pady=(0, 2))
                tk.Label(g, text=value, bg=bg, fg=txt, font=look.f(9), anchor="w", justify="left", bd=0, padx=0,
                         wraplength=max(80, inner // 2)).grid(row=r, column=1, sticky="w", pady=(0, 2))
            else:                                        # (a line that says it all: "Sockets: S S")
                tk.Label(g, text=label, bg=bg, fg=txt, font=look.f(9), anchor="w", justify="left", bd=0, padx=0,
                         wraplength=inner).grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, 2))
    props = []
    if f.get("base"):
        props.append(("Base type", f["base"]))
    if f.get("ilvl"):
        props.append(("Item level", str(f["ilvl"])))
    for label, value, _aug in f.get("parts") or [(x, "", False) for x in f["props"]]:
        if value:
            props.append((label, value))
        elif any(ch.isdigit() for ch in label):          # (a line with its numbers in it; the bare class name -
            props.append((label, ""))                    # "Gloves" - is what Base type says)
    if props:
        pairs(head("props"), props)
    req = f.get("req_parts") or []
    if req:                                              # (as the card's REQUIREMENTS: Level 80 · Int 101)
        rows = head("req")
        line = tk.Frame(rows, bg=bg)
        line.pack(fill="x")
        for i, part in enumerate(req):
            label, _sp, value = part.rpartition(" ")
            tk.Label(line, text=label or part, bg=bg, fg=mut, font=look.f(9), bd=0, padx=0).pack(
                side="left", padx=(12 if i else 0, 4))
            if label:
                tk.Label(line, text=value, bg=bg, fg=txt, font=look.f(9), bd=0, padx=0).pack(side="left")
    aug = [m for m in f["mods"] if m[2] == "rune"]
    if aug:                                              # (owner: not deep in - the kind muted, the text bright)
        g = tk.Frame(head("aug"), bg=bg)
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)
        for r, (_tier, text, kind) in enumerate(aug):
            tk.Label(g, text=KIND_WORDS.get(kind, "Rune"), bg=bg, fg=mut, font=look.f(9), anchor="w", bd=0,
                     padx=0).grid(row=r, column=0, sticky="nw", padx=(0, 12), pady=(0, 2))
            tk.Label(g, text=text, bg=bg, fg=mod_color(kind), font=look.f(9), anchor="w", justify="left", bd=0,
                     padx=0, wraplength=max(80, inner - 48)).grid(row=r, column=1, sticky="w", pady=(0, 2))
    from .pricecheck_page import FLAG_MARKS
    if any(k in (f.get("flags") or ()) for k, _m, _w in FLAG_MARKS):
        _flag_row(head("misc"), bg, f.get("flags"), look, chips=False).pack(fill="x")
    mods = [m for m in f["mods"] if m[2] in ("implicit", "enchant")] + [m for m in f["mods"] if m[2] in SHOWN_KINDS]
    if mods:
        _mod_grid(head("stats"), bg, mods, inner, look, words=True).pack(fill="x")
    pseudo = [p for p in f.get("pseudo") or [] if p]
    if pseudo:
        rows = head("pseudo")
        for p in pseudo:
            tk.Label(rows, text=p, bg=bg, fg=MOD_COL["pseudo"], font=look.f(9), anchor="w", justify="left", bd=0,
                     padx=0, wraplength=inner).pack(fill="x", pady=(0, 2))
    quiet = ([f"Listed {f['times']} times"] if f.get("times", 1) > 1 else []) + \
        ([f"Note: {f['note']}"] if f.get("note") else [])
    for i, q in enumerate(quiet):
        tk.Label(box, text=q, bg=bg, fg=mut, font=look.f(9), anchor="w", justify="left", bd=0, padx=0,
                 wraplength=wrap).pack(fill="x", pady=(SEC_GAP if not i and n["heads"] else 0, 0))
    if not box.winfo_children():
        tk.Label(box, text="Nothing more to show.", bg=bg, fg=mut, font=look.f(9), anchor="w").pack(fill="x")
    return box


def _title(app, head, f, bg, look, room):
    """The card's title: the item's name in its rarity color, the base type muted beside it (under it when there's
    no room) and "item level 82 · listed 1 d ago" muted under that. -> its frame."""
    from . import themes as _th
    from .trade import ago
    t = _th.ST.theme
    rar = str(f.get("rarity") or "").lower()
    col = {"rare": C["rare"], "magic": C["magic"],
           "unique": t.c("unique", "#af6025") if t is not None else "#af6025"}.get(rar, C["text"])
    name = f.get("name") or f.get("base") or "Item"
    base = f["base"] if f.get("base") and f["base"] != name else ""
    box = tk.Frame(head, bg=bg)
    top = tk.Frame(box, bg=bg)
    top.pack(fill="x")
    nfont = (_th.head_font(), font_size(12, look.k), "bold")
    tk.Label(top, text=name, bg=bg, fg=col, font=nfont, anchor="w", bd=0, padx=0, justify="left",
             wraplength=max(120, room)).pack(side="left")
    meta = [x for x in ((f"item level {f['ilvl']}" if f["ilvl"] else ""),
                        ("listed " + ago(f["ts"]) if f["ts"] else "")) if x]
    beside = False
    if base:
        try:
            need = tkfont.Font(root=head, font=nfont).measure(name) + 8 + \
                tkfont.Font(root=head, font=look.f(9)).measure(base)
            beside = need <= room
        except tk.TclError:
            beside = False
        if beside:
            tk.Label(top, text=base, bg=bg, fg=C["muted"], font=look.f(9), anchor="w", bd=0, padx=0).pack(
                side="left", padx=(8, 0))
        else:
            meta.insert(0, base)
    if meta:
        tk.Label(box, text=" · ".join(meta), bg=bg, fg=C["muted"], font=look.f(9), anchor="w", justify="left",
                 bd=0, padx=0, wraplength=max(120, room)).pack(fill="x", pady=(2, 0))
    return box


def _price(app, head, f, bg, look):
    """The price on the card's right, as the trade site has it: "2000 ×" and the currency's picture (its name in words
    when there's none; on hover, always). -> (its frame, the toggle's row)."""
    box = tk.Frame(head, bg=bg)
    row = tk.Frame(box, bg=bg)
    row.pack(anchor="e")
    if not f["price"]:
        tk.Label(row, text="no price", bg=bg, fg=C["muted"], font=look.f(10), bd=0, padx=0).pack(side="left")
        return box
    from .pricecheck_page import cur_label
    amt = tk.Label(row, text=amount_text(f), bg=bg, fg=C["text"], font=look.f(13, "bold"), bd=0, padx=0)
    amt.pack(side="left")
    tk.Label(row, text="×", bg=bg, fg=C["muted"], font=look.f(10), bd=0, padx=0).pack(side="left", padx=(4, 4))
    img = cur_icon(app, f["price"][1], look.k)
    if img is not None:
        pic = tk.Label(row, image=img, bg=bg, bd=0, padx=0, pady=0)
        pic.image = img
        pic.pack(side="left")
        Tooltip(pic, price_text(f))
    else:                                                # (no picture: the currency in words)
        tk.Label(row, text=cur_label(f["price"][1]), bg=bg, fg=C["text"], font=look.f(10), bd=0, padx=0).pack(
            side="left")
    Tooltip(amt, price_text(f))
    box._amt = amt
    return box


def _card(app, parent, f, e_key, opened, wrap, look):
    """One listing's card: the picture in the middle of its own column, the rest in the middle beside it.
    -> the card."""
    bg = C["panel2"]
    card = tk.Frame(parent, bg=bg, padx=12, pady=12, highlightthickness=1, highlightbackground=C["line"])
    card.columnconfigure(1, weight=1)
    card.rowconfigure(0, weight=1)
    pic = tk.Canvas(card, width=PIC, height=PIC, bg=bg, highlightthickness=0, bd=0)
    pic.grid(row=0, column=0, padx=(0, 12))              # (no sticky: the middle of the column, both ways)
    _placeholder(pic)
    url = f["icon"] if SETTINGS.get("pc_art", True) else ""
    if url:
        img = app.pc_art(url)
        if img is not None:
            _place_art(pic, img)
        else:
            pics = app.__dict__.setdefault("_lc_pics", {})
            pics.setdefault(url, []).append(pic)
    body = tk.Frame(card, bg=bg)
    body.grid(row=0, column=1, sticky="ew")              # (the middle of the card, top to bottom)
    head = tk.Frame(body, bg=bg)
    head.pack(fill="x")
    head.columnconfigure(0, weight=1)
    right = _price(app, head, f, bg, look)
    right.grid(row=0, column=1, sticky="ne", padx=(12, 0))
    tog = tk.Label(right, text=OPEN if opened else SHUT, bg=bg, fg=C["muted"], font=look.f(9), cursor="hand2", bd=0,
                   padx=0)
    tog.pack(anchor="e", pady=(4, 0))
    try:
        rw = right.winfo_reqwidth()
    except tk.TclError:
        rw = 120
    _title(app, head, f, bg, look, max(120, wrap - rw - 12)).grid(row=0, column=0, sticky="nw")
    quick = tk.Frame(body, bg=bg)                        # (the mods and the flags; Whole item takes their place)
    quick.pack(fill="x")
    mods = [m for m in f["mods"] if m[2] in SHOWN_KINDS]
    if mods:
        _mod_grid(quick, bg, mods, wrap, look).pack(fill="x", pady=(8, 0))
    fr = _flag_row(quick, bg, f.get("flags"), look)
    if fr is not None:
        fr.pack(fill="x", pady=(8, 0))
    slot = tk.Frame(body, bg=bg)

    def toggle(_e=None):
        if slot.winfo_manager():
            slot.pack_forget()
            quick.pack(fill="x")
            tog.config(text=SHUT)
            opened_ids.discard(e_key)
            return
        if not slot.winfo_children():
            _detail(slot, f, wrap, bg, look).pack(fill="x")
            _bind_all(slot, toggle)                      # (a click on the whole item closes it too)
        quick.pack_forget()
        slot.pack(fill="x", pady=(12, 0))
        tog.config(text=OPEN)
        opened_ids.add(e_key)
    opened_ids = parent._lc_ids
    _bind_all(card, toggle)
    if opened:
        toggle()
    return card


def draw(app, v, entries, rec=None):
    """The listings (entries: trade-site results) as cards, in v.lst. Drawn once per call."""
    from .pricecheck_page import listing_facts
    rid = (rec or {}).get("id")
    st = getattr(v, "_lc_open", None)
    if not st or st["rid"] != rid:                    # (another item: all closed again)
        st = v._lc_open = {"rid": rid, "ids": set()}
    if not getattr(app, "_lc_hooked", False):
        app._lc_hooked = True
        app._art_hooks = list(getattr(app, "_art_hooks", [])) + [lambda done: draw_art(app, done)]
    try:
        cw = v.rcanvas.winfo_width()
    except tk.TclError:
        cw = 0
    avail = max(240, cw - 24 - 2) if cw > 50 else 420
    wrap = max(160, avail - PIC - 12 - 24 - 2)
    look = _Look(scale_for(app, v))
    holder = tk.Frame(v.lst, bg=C["panel"])
    holder.pack(fill="x", pady=(0, 12))
    holder._lc_ids = st["ids"]
    holder._lc_k = look.k
    for i, e in enumerate(entries):
        f = listing_facts(e)
        key = f.get("id") or f"#{i}"
        c = _card(app, holder, f, key, key in st["ids"], wrap, look)
        c.pack(fill="x", pady=(0, 8))
    return holder
