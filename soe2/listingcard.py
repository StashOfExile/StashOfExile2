"""The cheapest listings as small in-game-style item cards (Price Checks and Bulk Pricing share it).

Each listing: the base type's picture in its own column, in the middle of it (a rounded placeholder until it
arrives); beside it, in the middle of the card, the price, "item level 82 · listed 1 d ago" and a "▸ Whole item"
toggle, the mods one per line (a tier tag, then the text in its mod color) and the flags as chips. Whole item opens the
item inside that card in the item card's own order and words (names.CARD_SECTIONS): BASE AND PROPERTIES, REQUIREMENTS,
AUGMENTS, ITEM FLAGS, MODS, PSEUDO FILTERS - only the parts it has - as plain rows ("Quality: +21%"), the seller's
note as a quiet last row. No seller names anywhere (privacy). A click anywhere on a card does what the toggle does.

UI rule 22: a search result draws the cards once; the toggle changes one card; a picture that arrives is put into its
placeholder (draw_art), the card is not built again. The pictures come from Price Checks' art cache (pc_art): loaded
in a thread, kept on disk - never a network call on the UI thread."""
import tkinter as tk

from . import buglog
from .config import SETTINGS
from .style import C, MOD_COL, Tooltip

PIC = 78                                    # the picture's box (the art cache's size)
SHOWN_KINDS = ("explicit", "fractured", "desecrated", "crafted")
FLAG_COL = {"fractured": "fractured", "desecrated": "desecrated", "crafted": "enchant"}
OPEN, SHUT = "▾ Less", "▸ Whole item"
# Whole item: a mod's kind in a word before it, as the item card says it ("Implicit · +10% to Fire Resistance")
KIND_WORDS = {"implicit": "Implicit", "enchant": "Enchant", "rune": "Rune", "fractured": "Fractured",
              "desecrated": "Desecrated"}


def kind_text(text, kind):
    w = KIND_WORDS.get(kind)
    return f"{w} \u00b7 {text}" if w and not text.startswith(w) else text


def mod_color(kind):
    return MOD_COL.get({"crafted": "enchant"}.get(kind, kind), MOD_COL["explicit"])


def tier_tip(tier):
    """"P1" -> "Prefix, tier 1 (1 is the best roll)" (the item card's hover)."""
    word = {"P": "Prefix", "S": "Suffix"}.get(tier[:1].upper(), "Mod")
    return f"{word}, tier {tier[1:] or tier} (1 is the best roll)"


def price_text(f):
    from .pricefmt import UNIT_NAMES
    from .pricecheck_page import cur_label
    if not f["price"]:
        return "no price"
    amt, cur = f["price"]
    amt = int(amt) if float(amt).is_integer() else amt
    return f"{amt} {UNIT_NAMES.get(cur) or cur_label(cur)}"


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


def _mod_row(parent, bg, tier, text, kind, wrap):
    """One mod: its tier tag (P1 / S1, with the item card's hover), then its text in its mod color."""
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x")
    tg = tk.Label(row, text=tier, bg=bg, fg=C["muted"], font=("Segoe UI", 9), width=3, anchor="w")
    tg.pack(side="left", anchor="n")
    if tier:
        Tooltip(tg, tier_tip(tier))
    tk.Label(row, text=text, bg=bg, fg=mod_color(kind), font=("Segoe UI", 9), anchor="w", justify="left",
             wraplength=wrap - 32).pack(side="left", fill="x")
    return row


def _flag_row(parent, bg, flags):
    """The flags as a mark and a word each (the game's order), in their colors, on one plain row."""
    from .pricecheck_page import FLAG_MARKS, flag_text
    keys = [k for k, _m, _w in FLAG_MARKS if k in (flags or ())]
    if not keys:
        return None
    fr = tk.Frame(parent, bg=bg)
    for i, k in enumerate(keys):
        col_key = FLAG_COL.get(k)
        fg = MOD_COL[col_key] if col_key else (C["red"] if "corrupted" in k else C["text"])
        tk.Label(fr, text=flag_text({k}), bg=bg, fg=fg, font=("Segoe UI", 9)).pack(side="left", padx=(0 if not i else 12, 0))
    return fr


def _detail(parent, f, wrap, bg=None):
    """The whole item, as the item card has it: its sections in the card's order and words (only those it has),
    plain rows; the seller's note last, quiet."""
    from .names import CARD_SECTIONS as SEC
    bg = bg or C["panel2"]
    box = tk.Frame(parent, bg=bg)
    mut, txt = C["muted"], C["text"]
    n = {"heads": 0}

    def head(key, summary=""):
        h = tk.Frame(box, bg=bg)
        h.pack(fill="x", pady=(8 if n["heads"] else 0, 2))
        n["heads"] += 1
        tk.Label(h, text=SEC[key], bg=bg, fg=txt, font=("Segoe UI", 9, "bold"), anchor="w").pack(side="left")
        if summary:
            tk.Label(h, text=summary, bg=bg, fg=mut, font=("Segoe UI", 9), anchor="w").pack(side="left", padx=(8, 0))

    def line(text, fg=txt):
        tk.Label(box, text=text, bg=bg, fg=fg, font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=wrap).pack(fill="x")
    props = []
    if f.get("base"):
        props.append(f"Base type: {f['base']}")
    if f.get("ilvl"):
        props.append(f"Item level: {f['ilvl']}")
    for label, value, _aug in f.get("parts") or [(x, "", False) for x in f["props"]]:
        if value:
            props.append(f"{label}: {value}")
        elif any(ch.isdigit() for ch in label):          # (a line with its numbers in it; the bare class name -
            props.append(label)                          # "Gloves" - is what Base type says)
    if props:
        head("props")
        for p in props:
            line(p)
    req = f.get("req_parts") or []
    if req:
        head("req", "  ·  ".join(req))                   # (as the card's REQUIREMENTS row: Level 80 · Int 101)
    aug = [m for m in f["mods"] if m[2] == "rune"]
    if aug:
        head("aug")
        for tier, text, kind in aug:
            _mod_row(box, bg, tier, kind_text(text, kind), kind, wrap)
    fl = _flag_row(box, bg, f.get("flags"))
    if fl is not None:
        head("misc")
        fl.pack(fill="x")
    mods = [m for m in f["mods"] if m[2] in ("implicit", "enchant")] + [m for m in f["mods"] if m[2] in SHOWN_KINDS]
    if mods:
        head("stats")
        for tier, text, kind in mods:
            _mod_row(box, bg, tier, kind_text(text, kind), kind, wrap)
    pseudo = [p for p in f.get("pseudo") or [] if p]
    if pseudo:
        head("pseudo")
        for p in pseudo:
            line(p, MOD_COL["pseudo"])
    quiet = ([f"Listed {f['times']} times"] if f.get("times", 1) > 1 else []) + \
        ([f"Note: {f['note']}"] if f.get("note") else [])
    for i, q in enumerate(quiet):
        tk.Label(box, text=q, bg=bg, fg=mut, font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=wrap).pack(fill="x", pady=(8 if not i and n["heads"] else 0, 0))
    if not box.winfo_children():
        line("Nothing more to show.", mut)
    return box


def _card(app, parent, f, e_key, opened, wrap):
    """One listing's card: the picture in the middle of its own column, the rest in the middle beside it.
    -> the card."""
    from .pricecheck_page import flag_text
    from .trade import ago
    bg, mut, txt = C["panel2"], C["muted"], C["text"]
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
    tk.Label(head, text=price_text(f), bg=bg, fg=txt if f["price"] else mut, font=("Segoe UI", 12, "bold"),
             anchor="w").pack(side="left")
    meta = " · ".join(x for x in ((f"item level {f['ilvl']}" if f["ilvl"] else ""),
                                  ("listed " + ago(f["ts"]) if f["ts"] else "")) if x)
    tk.Label(head, text=meta, bg=bg, fg=mut, font=("Segoe UI", 9), anchor="w").pack(side="left", padx=(8, 0))
    tog = tk.Label(head, text=OPEN if opened else SHUT, bg=bg, fg=mut, font=("Segoe UI", 9), cursor="hand2")
    tog.pack(side="right")
    quick = tk.Frame(body, bg=bg)                        # (the mods and the flags; Whole item takes their place)
    quick.pack(fill="x")
    mods = [m for m in f["mods"] if m[2] in SHOWN_KINDS]
    if mods:
        col = tk.Frame(quick, bg=bg)
        col.pack(fill="x", pady=(4, 0))
        for tier, text, kind in mods:
            _mod_row(col, bg, tier, text, kind, wrap)
    from .pricecheck_page import FLAG_MARKS
    keys = [k for k, _m, _w in FLAG_MARKS if k in (f.get("flags") or ())]      # (the game's order)
    if keys:
        fr = tk.Frame(quick, bg=bg)
        fr.pack(fill="x", pady=(8, 0))
        for k in keys:
            col_key = FLAG_COL.get(k)
            fg = MOD_COL[col_key] if col_key else (C["red"] if k == "corrupted" else txt)
            tk.Label(fr, text=flag_text({k}), bg=C["panel"], fg=fg, font=("Segoe UI", 9), padx=8, pady=1).pack(
                side="left", padx=(0, 4))
    slot = tk.Frame(body, bg=bg)

    def toggle(_e=None):
        if slot.winfo_manager():
            slot.pack_forget()
            quick.pack(fill="x")
            tog.config(text=SHUT)
            opened_ids.discard(e_key)
            return
        if not slot.winfo_children():
            _detail(slot, f, wrap, bg).pack(fill="x")
            _bind_all(slot, toggle)                      # (a click on the whole item closes it too)
        quick.pack_forget()
        slot.pack(fill="x", pady=(8, 0))
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
    holder = tk.Frame(v.lst, bg=C["panel"])
    holder.pack(fill="x", pady=(0, 12))
    holder._lc_ids = st["ids"]
    for i, e in enumerate(entries):
        f = listing_facts(e)
        key = f.get("id") or f"#{i}"
        c = _card(app, holder, f, key, key in st["ids"], wrap)
        c.pack(fill="x", pady=(0, 8))
    return holder
