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
    cap, txt, _edge = TH.window_colors()
    out.append(("app window title bar (2.61.0)", txt, cap))
    for kind in ("title", "title_off", "section"):          # 2.63.0: + the section header strips
        spec = t.part("bars", kind)
        for at in ((0.0, 0.5, 1.0) if kind == "section" else (0.5,)):
            out.append((f"{kind} bar", t.c(spec.get("text", "#ffffff")), TH.grad_at(t.grad(spec["fill"]), at)))
    if "section" in (t.part("bars") or {}):
        spec = t.part("bars", "section")
        out.append(("section bar note", C["steel"], TH.grad_at(t.grad(spec["fill"]), 0.5)))
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
    o_worst, o_fails = run_overlay()
    for r, n, fg, bg in (o_fails or o_worst)[:40]:
        print(f"{r:5.2f}  overlay {n:36} {fg} on {bg}")
    print("OK - every overlay pair is at least 4.5 : 1" if not o_fails else f"{len(o_fails)} overlay pairs under 4.5 : 1")
    sys.exit(1 if fails or o_fails else 0)
