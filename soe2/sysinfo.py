"""3.2.0 Report a bug › Add your screen setup. Owner: a reading bug needs the player's screen setup, shown word for
word before Send, only when the box is ticked.

What it says: each screen's size, refresh rate, Windows scaling and HDR; the game window's size, its screen and its
mode; which language Windows' text reader uses; the last Read Key press that didn't find the inventory.
Where it comes from: Windows' own display and window calls - the same window metadata the overlay already uses.
TOS.md: window rects and monitor sizes are not screen content. Nothing is read from the game, its files or its
settings; no picture is taken. Every call can fail: a part that can't be read is left out."""
import sys
import time

from . import buglog

GAME_TITLE = "Path of Exile 2"
WS_CAPTION = 0x00C00000
_USER32 = []


def _user32():
    """This module's own user32: other parts of the app set argtypes on the shared windll with their own structs,
    and a call here with ours then fails - owner's report: no screen line, an ArgumentError."""
    if not _USER32:
        import ctypes
        _USER32.append(ctypes.WinDLL("user32"))
    return _USER32[0]


def _windows_screens():
    """[{name, x, y, w, h, hz, scale, main, hmon}] in real pixels, Windows."""
    import ctypes
    from ctypes import wintypes
    u = _user32()

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

    class DEVMODEW(ctypes.Structure):
        _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                    ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD),
                    ("dmFields", wintypes.DWORD), ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                    ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                    ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                    ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                    ("dmFormName", wintypes.WCHAR * 32), ("dmLogPixels", wintypes.WORD),
                    ("dmBitsPerPel", wintypes.DWORD), ("dmPelsWidth", wintypes.DWORD),
                    ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                    ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD),
                    ("dmICMIntent", wintypes.DWORD), ("dmMediaType", wintypes.DWORD),
                    ("dmDitherType", wintypes.DWORD), ("dmReserved1", wintypes.DWORD),
                    ("dmReserved2", wintypes.DWORD), ("dmPanningWidth", wintypes.DWORD),
                    ("dmPanningHeight", wintypes.DWORD)]

    mons = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    u.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, proc, ctypes.c_void_p]
    u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFOEXW)]
    u.EnumDisplaySettingsW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DEVMODEW)]

    def each(hmon, _dc, _r, _l):
        mons.append(hmon)
        return True
    cb = proc(each)
    u.EnumDisplayMonitors(None, None, cb, None)
    try:
        shcore = ctypes.windll.shcore
    except Exception:
        shcore = None
    out = []
    for hm in mons:
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not u.GetMonitorInfoW(hm, ctypes.byref(mi)):
            continue
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(DEVMODEW)
        w = h = hz = 0
        x, y = mi.rcMonitor.left, mi.rcMonitor.top
        if u.EnumDisplaySettingsW(mi.szDevice, 0xFFFFFFFF, ctypes.byref(dm)):        # ENUM_CURRENT_SETTINGS: real pixels
            w, h, hz = dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency
            x, y = dm.dmPositionX, dm.dmPositionY
        scale = 0
        if shcore is not None:
            dx, dy = wintypes.UINT(0), wintypes.UINT(0)
            try:
                if shcore.GetDpiForMonitor(ctypes.c_void_p(hm), 0, ctypes.byref(dx), ctypes.byref(dy)) == 0 and dx.value:
                    scale = int(round(dx.value * 100 / 96.0))
            except Exception:
                scale = 0
        lw = mi.rcMonitor.right - mi.rcMonitor.left
        if not scale and w and lw and lw != w:                          # a DPI-unaware read: work it out
            scale = int(round(w * 100.0 / lw))
        out.append({"name": mi.szDevice, "x": x, "y": y, "w": w or lw, "h": h or (mi.rcMonitor.bottom -
                    mi.rcMonitor.top), "hz": hz, "scale": scale, "main": bool(mi.dwFlags & 1), "hmon": hm})
    return out


def _windows_hdr():
    """{GDI device name: True / False} - HDR on each screen, Windows 10 1709 or newer; {} when it can't be read."""
    import ctypes
    from ctypes import wintypes
    u = _user32()

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class SRC(ctypes.Structure):
        _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32), ("modeInfoIdx", ctypes.c_uint32),
                    ("statusFlags", ctypes.c_uint32)]

    class RATIONAL(ctypes.Structure):
        _fields_ = [("Numerator", ctypes.c_uint32), ("Denominator", ctypes.c_uint32)]

    class TGT(ctypes.Structure):
        _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32), ("modeInfoIdx", ctypes.c_uint32),
                    ("outputTechnology", ctypes.c_uint32), ("rotation", ctypes.c_uint32),
                    ("scaling", ctypes.c_uint32), ("refreshRate", RATIONAL), ("scanLineOrdering", ctypes.c_uint32),
                    ("targetAvailable", wintypes.BOOL), ("statusFlags", ctypes.c_uint32)]

    class PATH(ctypes.Structure):
        _fields_ = [("sourceInfo", SRC), ("targetInfo", TGT), ("flags", ctypes.c_uint32)]

    class MODE(ctypes.Structure):
        _fields_ = [("raw", ctypes.c_byte * 64)]

    class HEADER(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint32), ("size", ctypes.c_uint32), ("adapterId", LUID),
                    ("id", ctypes.c_uint32)]

    class SRCNAME(ctypes.Structure):
        _fields_ = [("header", HEADER), ("viewGdiDeviceName", wintypes.WCHAR * 32)]

    class COLOR(ctypes.Structure):
        _fields_ = [("header", HEADER), ("value", ctypes.c_uint32), ("colorEncoding", ctypes.c_uint32),
                    ("bitsPerColorChannel", ctypes.c_uint32)]

    np_, nm = ctypes.c_uint32(0), ctypes.c_uint32(0)
    if u.GetDisplayConfigBufferSizes(2, ctypes.byref(np_), ctypes.byref(nm)) != 0:     # QDC_ONLY_ACTIVE_PATHS
        return {}
    paths, modes = (PATH * max(1, np_.value))(), (MODE * max(1, nm.value))()
    if u.QueryDisplayConfig(2, ctypes.byref(np_), paths, ctypes.byref(nm), modes, None) != 0:
        return {}
    out = {}
    for p in paths[:np_.value]:
        sn = SRCNAME()
        sn.header.type, sn.header.size = 1, ctypes.sizeof(SRCNAME)                 # GET_SOURCE_NAME
        sn.header.adapterId, sn.header.id = p.sourceInfo.adapterId, p.sourceInfo.id
        if u.DisplayConfigGetDeviceInfo(ctypes.byref(sn.header)) != 0:
            continue
        ci = COLOR()
        ci.header.type, ci.header.size = 9, ctypes.sizeof(COLOR)                   # GET_ADVANCED_COLOR_INFO
        ci.header.adapterId, ci.header.id = p.targetInfo.adapterId, p.targetInfo.id
        if u.DisplayConfigGetDeviceInfo(ctypes.byref(ci.header)) != 0:
            continue
        out[sn.viewGdiDeviceName] = bool(ci.value & 2)                             # advancedColorEnabled
    return out


def _windows_game(screens):
    """{w, h, screen, mode} of the game window, or None when it isn't running."""
    import ctypes
    from ctypes import wintypes
    u = _user32()
    u.FindWindowW.argtypes, u.FindWindowW.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR], ctypes.c_void_p
    u.MonitorFromWindow.argtypes, u.MonitorFromWindow.restype = [ctypes.c_void_p, wintypes.DWORD], ctypes.c_void_p
    for fn in ("GetWindowRect", "GetClientRect"):
        getattr(u, fn).argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    u.IsIconic.argtypes = [ctypes.c_void_p]
    u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    hwnd = u.FindWindowW(None, GAME_TITLE)
    if not hwnd:
        return None
    if u.IsIconic(hwnd):
        return {"mode": "minimized"}
    r, c = wintypes.RECT(), wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    u.GetClientRect(hwnd, ctypes.byref(c))
    style = u.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF
    w, h = r.right - r.left, r.bottom - r.top
    hm = u.MonitorFromWindow(hwnd, 2)
    n, mon = 0, None
    for i, s in enumerate(screens):
        if s.get("hmon") == hm:
            n, mon = i + 1, s
    if style & WS_CAPTION == WS_CAPTION:
        mode = "windowed, with a title bar"
    elif mon and (r.left, r.top, w, h) == (mon["x"], mon["y"], mon["w"], mon["h"]):
        mode = "fills the screen, no border"
    else:
        mode = "no border, smaller than the screen"
    return {"w": w, "h": h, "cw": c.right - c.left, "ch": c.bottom - c.top, "screen": n, "mode": mode}


def _reader_language():
    """The language Windows' text reader uses, or why there's none."""
    try:
        if sys.platform == "win32":
            from . import remnant as RM
            why = RM.ocr_available()
            if why:
                return why
            eng = RM._engine()
            lang = getattr(eng, "recognizer_language", None)
            return str(getattr(lang, "language_tag", "") or getattr(lang, "display_name", "") or "?")
        from . import ocrengine
        return ocrengine.problem() or "Tesseract"
    except Exception:
        buglog.caught()
        return "?"


def gather(root=None):
    """-> {screens, game, reader, miss}: every part that could be read."""
    info = {"screens": [], "game": None, "reader": "", "miss": ""}
    if sys.platform == "win32":
        from .screenread import real_pixels
        try:
            with real_pixels():
                info["screens"] = _windows_screens()
        except Exception:
            buglog.caught()
        try:
            hdr = _windows_hdr()
            for s in info["screens"]:
                if s["name"] in hdr:
                    s["hdr"] = hdr[s["name"]]
        except Exception:
            buglog.caught()
        try:
            with real_pixels():
                info["game"] = _windows_game(info["screens"])
        except Exception:
            buglog.caught()
    elif root is not None:
        try:
            info["screens"] = [{"w": root.winfo_screenwidth(), "h": root.winfo_screenheight(), "main": True}]
        except Exception:
            pass
        try:
            from .alerts_page import game_rect
            g = game_rect()
            if g:
                info["game"] = {"w": g[2], "h": g[3]}
        except Exception:
            buglog.caught()
    info["reader"] = _reader_language()
    try:
        from . import topup as TU
        info["miss"] = TU.miss_text()
    except Exception:
        buglog.caught()
    return info


def text(info):
    """The report's part, as it is sent."""
    lines = []
    many = len(info.get("screens") or []) > 1
    for i, s in enumerate(info.get("screens") or []):
        bits = [f"{s.get('w', '?')}×{s.get('h', '?')}"]
        if s.get("hz"):
            bits.append(f"{s['hz']} Hz")
        if s.get("scale"):
            bits.append(f"scaling {s['scale']}%")
        if "hdr" in s:
            bits.append("HDR on" if s["hdr"] else "HDR off")
        label = f"Screen {i + 1}" + (", main" if s.get("main") and many else "") if many else "Screen"
        lines.append(f"{label}: " + " · ".join(bits))
    g = info.get("game")
    if g is None:
        lines.append("Game window: not open")
    elif g.get("mode") == "minimized":
        lines.append("Game window: minimized")
    else:
        bits = [f"{g.get('w', '?')}×{g.get('h', '?')}"]
        if g.get("cw") and (g["cw"], g["ch"]) != (g.get("w"), g.get("h")):
            bits.append(f"inside {g['cw']}×{g['ch']}")
        if g.get("screen") and many:
            bits.append(f"on screen {g['screen']}")
        if g.get("mode"):
            bits.append(g["mode"])
        lines.append("Game window: " + " · ".join(bits))
    if info.get("reader"):
        lines.append(f"Text reader: {info['reader']}")
    if info.get("miss"):
        lines.append(f"Last inventory miss: {info['miss']}")
    return "**Screen setup**\n" + "\n".join(lines)


_CACHE = {}


def report_part(root=None, max_age=30.0):
    """text(gather()) - read once for a form, not on every key typed in it."""
    now = time.time()
    if _CACHE.get("t", 0) > now - max_age and "text" in _CACHE:
        return _CACHE["text"]
    try:
        t = text(gather(root))
    except Exception:
        buglog.caught()
        t = "**Screen setup**\nIt couldn't be read."
    _CACHE.update({"t": now, "text": t})
    return t
