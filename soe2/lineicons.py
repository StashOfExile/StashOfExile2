"""Line icons (drawer build, the Drawer look from mockups.html): the mockup's 24 x 24 stroke icons, drawn with Pillow
(4x, then scaled down, so they're smooth) in any color - the caller passes a theme color, so they follow the theme.

  icon(root, "tag", 18, C["muted"]) -> a PhotoImage (cached per name, size, color)

GGG ToS: looks only - nothing here touches the game."""
import math
import re

from . import buglog

# name -> SVG elements (24 x 24 viewBox, stroke 1.6, round caps and joins) - mockups.html's sprite
ICONS = {
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "grid": '<rect x="4" y="4" width="7" height="7"/><rect x="13" y="4" width="7" height="7"/>'
            '<rect x="4" y="13" width="7" height="7"/><rect x="13" y="13" width="7" height="7"/>',
    "layers": '<path d="M12 4l8 4.5-8 4.5-8-4.5z"/><path d="M4 13l8 4.5 8-4.5"/>',
    "tag": '<path d="M4 12V4h8l8 8-8 8z"/><circle cx="8.5" cy="8.5" r="1.3"/>',
    "history": '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4h4"/><path d="M12 8v4l3 2"/>',
    "stack": '<rect x="4" y="5" width="16" height="4"/><rect x="4" y="11" width="16" height="4"/>'
             '<rect x="4" y="17" width="16" height="3"/>',
    "star": '<path d="M12 4l2.4 5 5.4.6-4 3.7 1.1 5.4L12 16l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z"/>',
    "rate": '<path d="M5 7h9M5 12h6M5 17h9"/><path d="M17 6l1.5 1.5L21 5"/><path d="M15 12l1.5 1.5L19 11"/>',
    "swap": '<path d="M5 8h13l-3-3"/><path d="M19 16H6l3 3"/>',
    "coins": '<ellipse cx="12" cy="7" rx="7" ry="2.5"/><path d="M5 7v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V7"/>'
             '<path d="M5 12v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5"/>',
    "regex": '<path d="M15 4v9M11.2 6.2l7.6 4.6M18.8 6.2l-7.6 4.6"/><circle cx="7" cy="18" r="1.6"/>',
    "hammer": '<path d="M14 4l6 6-2 2-6-6z"/><path d="M13 9L5 17l2 2 8-8"/>',
    "flag": '<path d="M6 21V4"/><path d="M6 5h11l-2 4 2 4H6"/>',
    "route": '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h6a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6"/>',
    "trend": '<path d="M4 17l5-5 4 3 7-8"/><path d="M15 7h5v5"/>',
    "map": '<path d="M4 6l5-2 6 2 5-2v14l-5 2-6-2-5 2z"/><path d="M9 4v14M15 6v14"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5a3 3 0 0 0 3 3M16 6h3a3 3 0 0 1-3 3"/>'
              '<path d="M12 13v4M9 20h6"/>',
    "book": '<path d="M5 5a2 2 0 0 1 2-2h12v15H7a2 2 0 0 0-2 2z"/><path d="M5 20a2 2 0 0 0 2 1h12"/>',
    "expand": '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
    "side": '<rect x="3" y="5" width="18" height="14"/><path d="M9 5v14"/><path d="M14 10l-2 2 2 2"/>',
    "side_r": '<rect x="3" y="5" width="18" height="14"/><path d="M15 5v14"/><path d="M10 10l2 2-2 2"/>',
    "away": '<path d="M10 7l5 5-5 5"/><path d="M19 5v14"/>',
    "dock": '<rect x="3" y="5" width="18" height="14"/><path d="M15 5v14"/>',
    "info": '<circle cx="12" cy="12" r="8"/><path d="M12 11v5M12 8v.5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "circle": '<circle cx="12" cy="12" r="6"/>',
    "warn": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.5"/>',
    "open": '<path d="M9 5H5v14h14v-4"/><path d="M13 5h6v6M19 5l-8 8"/>',
    "mark": '<path d="M12 3l8 9-8 9-8-9z"/><path d="M12 8l3.5 4-3.5 4-3.5-4z"/>',
    "up": '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
    "note": '<path d="M6 4h9l4 4v12H6z"/><path d="M14 4v5h5"/><path d="M9 13h7M9 16h5"/>',
    "bars": '<path d="M5 20V11M10 20V6M15 20v-7M20 20V9"/>',
    "dot": '<circle cx="12" cy="12" r="3"/>',
    "globe": '<circle cx="12" cy="12" r="8"/><ellipse cx="12" cy="12" rx="3.5" ry="8"/><path d="M4 12h16"/>'
             '<path d="M5.5 8h13M5.5 16h13"/>',          # 3.0.6: Trade Site (a web browser)
}

# a page's key -> its icon (the sidebar's rail in the Drawer); a page not named here gets "dot". Settings is not here:
# its gear is the app's one gear everywhere (gearicon.py - sidebar, overlay, price check card, Price Checks)
PAGE_ICON = {
    "_goto": "search", "_update": "up", "dashboard": "grid", "tracker": "layers", "pricecheck": "tag",
    "checks": "stack", "favorites": "star", "ratemods": "rate", "rates": "swap", "insights": "bars",
    "wealth": "coins", "regex": "regex", "crafthelper": "hammer", "plan": "flag", "mapprofit": "route",
    "money": "trend", "maps": "map", "leaderboards": "trophy", "search": "book",
    "library": "history", "modbook": "book", "notes": "note",
}

SS = 4                       # drawn this many times larger, then scaled down (smooth edges)
_CACHE = {}
_TOK = re.compile(r"[MmLlHhVvCcAaZzSsQq]|-?\d*\.?\d+(?:e-?\d+)?")
_EL = re.compile(r"<(\w+)([^>]*)/>")
_AT = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _arc(x1, y1, rx, ry, phi, fa, fs, x2, y2, n=16):
    """SVG's endpoint arc -> points (x1, y1 excluded)."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if fa == fs:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def _path(d):
    """An SVG path's d -> a list of (points, closed) polylines."""
    toks = _TOK.findall(d)
    out, cur, x, y, sx, sy, i, cmd = [], [], 0.0, 0.0, 0.0, 0.0, 0, None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if cur:
                    out.append((cur, True))
                cur, x, y = [], sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            if cur:
                out.append((cur, False))
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            sx, sy, cur = x, y, [(x, y)]
            cmd = "l" if rel else "L"                  # (more pairs after M are lines)
        elif c == "L":
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            cur.append((x, y))
        elif c == "H":
            nx = num()
            x = x + nx if rel else nx
            cur.append((x, y))
        elif c == "V":
            ny = num()
            y = y + ny if rel else ny
            cur.append((x, y))
        elif c == "C":
            p = [num() for _ in range(6)]
            if rel:
                p = [p[0] + x, p[1] + y, p[2] + x, p[3] + y, p[4] + x, p[5] + y]
            for k in range(1, 13):
                t = k / 12
                a, b = (1 - t) ** 3, 3 * (1 - t) ** 2 * t
                cc, dd = 3 * (1 - t) * t * t, t ** 3
                cur.append((a * x + b * p[0] + cc * p[2] + dd * p[4], a * y + b * p[1] + cc * p[3] + dd * p[5]))
            x, y = p[4], p[5]
        elif c == "A":
            rx, ry, phi, fa, fs, nx, ny = num(), num(), num(), num(), num(), num(), num()
            if rel:
                nx, ny = x + nx, y + ny
            cur.extend(_arc(x, y, rx, ry, phi, int(fa), int(fs), nx, ny))
            x, y = nx, ny
        else:                                          # (not used by these icons)
            i += 1
    if cur:
        out.append((cur, False))
    return out


def _shapes(name):
    """name -> [("poly", points, closed) | ("ellipse", cx, cy, rx, ry)] in the 24 x 24 space."""
    out = []
    for tag, attrs in _EL.findall(ICONS.get(name) or ICONS["dot"]):
        a = {k: v for k, v in _AT.findall(attrs)}
        f = {k: float(v) for k, v in a.items() if k != "d"}
        if tag == "path":
            out += [("poly", pts, closed) for pts, closed in _path(a.get("d", ""))]
        elif tag == "circle":
            out.append(("ellipse", f["cx"], f["cy"], f["r"], f["r"]))
        elif tag == "ellipse":
            out.append(("ellipse", f["cx"], f["cy"], f["rx"], f["ry"]))
        elif tag == "rect":
            x, y, w, h = f["x"], f["y"], f["width"], f["height"]
            out.append(("poly", [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True))
    return out


def image(name, size, color, stroke=1.6):
    """A Pillow RGBA image of the icon (size x size px)."""
    from PIL import Image, ImageDraw
    big = size * SS
    k = big / 24.0
    wd = max(1, int(round(stroke * k)))
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    im = Image.new("RGBA", (big, big), rgb + (0,))
    d = ImageDraw.Draw(im)
    ink = rgb + (255,)
    r = wd / 2
    for sh in _shapes(name):
        if sh[0] == "ellipse":
            _, cx, cy, rx, ry = sh
            d.ellipse((cx * k - rx * k, cy * k - ry * k, cx * k + rx * k, cy * k + ry * k), outline=ink, width=wd)
            continue
        pts = [(px * k, py * k) for px, py in sh[1]]
        if sh[2] and pts:
            pts = pts + [pts[0]]
        if len(pts) == 1:
            pts = pts * 2
        d.line(pts, fill=ink, width=wd, joint="curve")
        for px, py in (pts[0], pts[-1]):              # round caps
            d.ellipse((px - r, py - r, px + r, py + r), fill=ink)
    return im.resize((size, size), Image.LANCZOS)


def icon(root, name, size, color, stroke=1.6):
    """A Tk PhotoImage of the icon, cached (keep a reference while it's shown - the cache does)."""
    key = (name, int(size), str(color).lower(), stroke)
    img = _CACHE.get(key)
    if img is None:
        try:
            from PIL import ImageTk
            img = ImageTk.PhotoImage(image(name, int(size), str(color), stroke), master=root)
        except Exception:
            buglog.caught()
            return None
        _CACHE[key] = img
    return img
