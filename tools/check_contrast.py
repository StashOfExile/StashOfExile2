"""WCAG 2.1 AA contrast check for every theme pack x accent (2.34.0, Polish 1; 2.60.0 theme packs).

  py tools/check_contrast.py      prints the lowest pairs, exit 1 if any text pair is under 4.5 : 1

Pairs = the text colors the app puts on its surfaces (style.C), the bevelled button / heading faces and the title
bars - all from the pack itself."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soe2 import style as S  # noqa: E402

AA = 4.5


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


EDGE = 3.0                                          # a button's outline against the page behind it (WCAG non-text)


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _hex(c):
    return "#%02x%02x%02x" % c


def secondary_pairs(under):
    """Text pairs (>= 4.5) of the Quiet / Strip buttons and the SegBar on the page color `under`: [(label, fg, bg)]."""
    from soe2 import soft, themes as TH
    t = TH.ST.theme
    muted, text = _rgb(S.C["muted"]), _rgb(S.C["text"])
    steel = _rgb(S.C["steel"])
    lk = soft.secondary_looks(muted, _rgb(under), text, ink=steel)
    on = soft.secondary_looks(muted, _rgb(under), text, picked=True, ink_hover=text)
    seg = soft.secondary_looks(muted, _rgb(under), text, ink=_rgb(t.c("text")))
    sel, sel_ink = soft.segment_picked(_rgb(t.c("selection")), _rgb(t.c("selection_text", "#ffffff")), seg["n"][0])
    out = [("quiet button text", S.C["steel"], _hex(lk["n"][0])), ("quiet button hover text", S.C["text"], _hex(lk["h"][0])),
           ("tab chip (shown) text", S.C["text"], _hex(on["n"][0])),
           ("segment (unpicked) text", t.c("text"), _hex(seg["n"][0])),
           ("segment (picked) text", _hex(sel_ink), _hex(sel))]
    return out


def edge_pairs():
    """Non-text pairs that must reach 3 : 1: [(label, a, b)] - a secondary button's outline against the page, the
    picked segment against the unpicked ones (a fill you can tell apart) and its bar's outline against the page."""
    from soe2 import soft, themes as TH
    t = TH.ST.theme
    muted, text = _rgb(S.C["muted"]), _rgb(S.C["text"])
    out = []
    for under, uname in ((S.C["bg"], "bg"), (S.C["panel"], "panel"), (S.C["panel2"], "panel2")):
        lk = soft.secondary_looks(muted, _rgb(under), text)
        on = soft.secondary_looks(muted, _rgb(under), text, picked=True)
        seg = soft.secondary_looks(muted, _rgb(under), _rgb(t.c("text")), ink=_rgb(t.c("text")))
        sel, _ink = soft.segment_picked(_rgb(t.c("selection")), _rgb(t.c("selection_text", "#ffffff")), seg["n"][0])
        out.append((f"picked segment vs unpicked on {uname}", _hex(sel), _hex(seg["n"][0])))
        out.append((f"button outline on {uname}", _hex(lk["n"][1]), under))
        out.append((f"button outline (hover) on {uname}", _hex(lk["h"][1]), under))
        out.append((f"tab chip (shown) outline on {uname}", _hex(on["n"][1]), under))
    under = t.c("surface_raised")                           # Rate Mods: each letter's color strip on its button
    for g in S.LETTER_ROLES:
        out.append((f"letter {g} strip on its button", S.letter_color(g, under), under))
    return out


def pairs():
    from soe2 import themes as TH
    C, mix = S.C, S.mix
    t = TH.ST.theme
    out = []
    for surf in ("bg", "panel", "panel2", "odd", "stripe"):
        for fg in ("text", "muted", "steel", "accent", "good", "green", "red", "blue", "purple", "rare", "magic"):
            out.append((f"{fg} on {surf}", C[fg], C[surf]))
    out.append(("selected row", t.c("selection_text", "#ffffff"), C["sel"]))
    for spec, name in (("normal", "button"), ("heading", "list heading"), ("primary", "primary button"),
                       ("danger", "danger button")):
        bs = TH.button_spec(t, spec)
        for k in ("fill", "hover"):
            face = TH.grad_at(t.grad(bs[k]), 0.5)
            if spec == "primary":
                fg = TH.text_of(t, "primary", "text", S.text_on(TH.grad_at(t.grad(bs["fill"]), 0.5)))
            elif spec == "danger":
                fg = TH.text_of(t, "danger", "text", S.text_on(TH.grad_at(t.grad(bs["fill"]), 0.5), "#ffe9e6"))
            else:
                fg = TH.text_of(t, spec, "text" if k == "fill" else "text_hover", C["text"])
            out.append((f"{name} ({k})", fg, face))
    out.append(("quiet button", C["steel"], C["panel"]))
    for under, uname in ((C["bg"], "bg"), (C["panel"], "panel"), (C["panel2"], "panel2")):   # the soft secondary buttons
        for name, text, ink in secondary_pairs(under):
            out.append((f"{name} on {uname}", text, ink))
    cap, txt, _edge = TH.window_colors()
    out.append(("app window title bar (2.61.0)", txt, cap))
    for kind in ("title", "title_off", "section"):          # 2.63.0: + the section header strips
        spec = t.part("bars", kind)
        for at in ((0.0, 0.5, 1.0) if kind == "section" else (0.5,)):
            out.append((f"{kind} bar", t.c(spec.get("text", "#ffffff")), TH.grad_at(t.grad(spec["fill"]), at)))
    if "section" in (t.part("bars") or {}):
        spec = t.part("bars", "section")
        out.append(("section bar note", C["steel"], TH.grad_at(t.grad(spec["fill"]), 0.5)))
    for g in S.LETTER_ROLES:                                # Rate Mods: a picked letter button is filled with its color
        col = S.letter_color(g)
        out.append((f"letter {g} on its picked button", S.text_on(col), col))
    return out


def overlay_pairs():
    """2.x legibility: the pairs the overlay draws in every ornate skin and every light style x color set (bar,
    Quick settings, windows over the game): [(label, fg, bg)]."""
    from soe2 import ovlight as OL, ovskins as OS
    out = []
    for name, s in OS.SKINS.items():
        t = f"{name}"
        out += [(f"{t} text on bg", s["text"], s["bg"]), (f"{t} muted on bg", s["muted"], s["bg"]),
                (f"{t} muted on field", s["muted"], s["field"]), (f"{t} text on field", s["text"], s["field"]),
                (f"{t} accent on bg", s["accent"], s["bg"]), (f"{t} head on band", s["head"], s["band"]),
                (f"{t} on chip", s["on_fg"], s["on_bg"]), (f"{t} off chip", s["off_fg"], s["off_bg"]),
                (f"{t} big on bg", s["big"], s["bg"])]
        for i, g in enumerate(s["band_grad"] or ()):
            out.append((f"{t} head on band stop {i}", s["head"], g))
    for style in ("hairline", "slate", "micro"):
        for cid in OL.COLORS:
            if cid == "theme":
                continue
            P = OL.palette(style, cid, boxed=True)
            t = f"{style}/{cid}"
            out += [(f"{t} text on bg", P["text"], P["bg"]), (f"{t} muted on bg", P["muted"], P["bg"]),
                    (f"{t} accent on bg", P["accent"], P["bg"]), (f"{t} big on bg", P["big"], P["bg"]),
                    (f"{t} head on band", P["head"], P["band"])]
    out += split_pairs()
    return out


def split_pairs():
    """The Split layout's halves (ovsplit.py), in every style: the labels (muted), values (big / text), the map's
    time and the profit (accent) on the half's box, the state chip's word (accent) on its field."""
    from soe2 import hudart, ovlight as OL, ovskins as OS
    from soe2.overlaywin import PALETTES
    out = []
    for style in OL.STYLES:
        if style == "classic":
            P = hudart.panel_palette(PALETTES["codex"])
        elif style in OS.ORNATE:
            P = OS.palette(style)
        else:
            P = OL.palette(style, OL.DEFAULT_COLORS, boxed=True)
        chip = P.get("cell_bg") or P.get("field") or P["bg"]
        t = f"split {style}"
        out += [(f"{t} text on bg", P["text"], P["bg"]), (f"{t} muted on bg", P["muted"], P["bg"]),
                (f"{t} big on bg", P["big"], P["bg"]), (f"{t} accent on bg", P.get("accent") or P["big"], P["bg"]),
                (f"{t} chip on field", P.get("accent") or P["text"], chip)]
    return out


def run_edges():
    """Every theme: the non-text pairs (button outlines) at 3 : 1; the picked segment against the unpicked at 1.5 : 1
    (it also has its mark and a bold word)."""
    from soe2 import themes as TH
    fails = []
    for theme in S.THEMES:
        S.apply_look(theme)
        for name, a, b in edge_pairs():
            need = 1.5 if "picked segment" in name else EDGE
            r = ratio(a, b)
            if r < need:
                fails.append((r, theme, name, a, b))
    S.apply_look(TH.DEFAULT)
    return sorted(fails)


def run_overlay():
    rows = sorted((ratio(fg, bg), n, fg, bg) for n, fg, bg in overlay_pairs())
    return rows[:8], [r for r in rows if r[0] < AA]


def run():
    from soe2 import themes as TH
    worst, fails = [], []
    for theme in S.THEMES:
        for accent in ["theme"]:                     # (2.119.0: a theme's own accent only)
            S.apply_look(theme)
            for name, fg, bg in pairs():
                with TH.raw():
                    pass
                r = ratio(fg, bg)
                worst.append((r, theme, accent, name, fg, bg))
                if r < AA:
                    fails.append((r, theme, accent, name, fg, bg))
    S.apply_look(TH.DEFAULT)
    return sorted(worst)[:8], sorted(fails)


if __name__ == "__main__":
    worst, fails = run()
    for r, t, a, n, fg, bg in (fails or worst)[:40]:
        print(f"{r:5.2f}  {t:9} {a:7} {n:28} {fg} on {bg}")
    print("OK - every pair is at least 4.5 : 1" if not fails else f"{len(fails)} pairs under 4.5 : 1")
    e_fails = run_edges()
    for r, t, n, a, b in e_fails[:40]:
        print(f"{r:5.2f}  {t:9} {n:40} {a} vs {b}")
    print("OK - every button outline is at least 3 : 1" if not e_fails else f"{len(e_fails)} outlines under 3 : 1")
    o_worst, o_fails = run_overlay()
    for r, n, fg, bg in (o_fails or o_worst)[:40]:
        print(f"{r:5.2f}  overlay {n:36} {fg} on {bg}")
    print("OK - every overlay pair is at least 4.5 : 1" if not o_fails else f"{len(o_fails)} overlay pairs under 4.5 : 1")
    sys.exit(1 if fails or o_fails or e_fails else 0)
