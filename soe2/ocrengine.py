"""The one place that decides which OCR engine reads text out of a picture the Read Key took (remnant.ocr calls it).

  Windows: Windows' own text reader (Windows.Media.Ocr, in remnant.py) - nothing to install.
  Linux:   Tesseract - the `tesseract` command on PATH (one run per picture: PNG in on stdin, TSV out), else the
           optional pytesseract module (which runs the same command). Nothing found: problem() says what to install,
           in one line, and every helper that needs OCR shows it on its row; the rest keep working (template and
           frame matching - the Sekhemas map check -, Client.txt helpers, price checks).

OCR only ever reads a picture screenread.py already took for one key press - it never takes one itself."""
import io
import os
import subprocess
import sys

ENGINE = [None]                     # tests: "tesseract" / "pytesseract" / "windows" / "" (none) - else found once
TESS = [None]                       # tests: the tesseract command's path
RUNNER = [None]                     # tests: fn(args, stdin_bytes, timeout) -> stdout text
_FOUND = {}
LANG = "eng"
PSM = "3"                           # Tesseract's own page layout (the game's panels have columns and gaps)
MAX_PIXELS = 6_000_000              # a bigger picture is read smaller (a whole 4K window would take seconds)


def tesseract_path():
    if TESS[0] is not None:
        return TESS[0] or None
    if "tess" not in _FOUND:
        from .linsys import which
        p = which("tesseract")
        if not p and getattr(sys, "frozen", False):          # (a desktop launcher's short PATH)
            p = next((c for c in ("/usr/bin/tesseract", "/usr/local/bin/tesseract") if os.path.isfile(c)), None)
        _FOUND["tess"] = p
    return _FOUND["tess"]


def _has_pytesseract():
    """pytesseract with a tesseract it can run (its tesseract_cmd set to one off PATH)."""
    if "pyt" not in _FOUND:
        try:
            import pytesseract
            from .linsys import which
            cmd = str(pytesseract.pytesseract.tesseract_cmd or "")
            _FOUND["pyt"] = bool(cmd and (os.path.isfile(cmd) or which(cmd)))
        except Exception:
            _FOUND["pyt"] = False
    return _FOUND["pyt"]


def engine():
    """-> "windows", "tesseract", "pytesseract" or "" (none). Decided once a run (rescan() looks again)."""
    if ENGINE[0] is not None:
        return ENGINE[0]
    if sys.platform == "win32":
        return "windows"
    if tesseract_path():
        return "tesseract"
    if _has_pytesseract():
        return "pytesseract"
    return ""


def rescan():
    """Look for the engine again (after you installed it)."""
    _FOUND.clear()


def install_hint():
    """'sudo apt install tesseract-ocr' for this distro ("its tesseract package" when the distro isn't known - the ⓘ
    has every distro's line)."""
    from .linsys import distro, install_cmd
    fam = distro()
    return install_cmd("tesseract", fam) if fam else "your distro's tesseract package"


NEEDS = "needs OCR"


def problem():
    """'' when an OCR engine can be used here, else one short line: what to install (Linux)."""
    if engine():
        return ""
    return f"{NEEDS} - install tesseract ({install_hint()})"


def help_text():
    """The ⓘ tooltip for a helper that needs OCR (Linux): every distro's line."""
    from .linsys import install_all
    return ("The screen-reading helpers read text with Tesseract - free OCR. Install it, then restart the app: "
            + install_all("tesseract").replace(" / ", " · ") + ". Helpers that match pictures (the Sekhemas map "
            "check, Ritual's Favours prices), Client.txt helpers and price checks work without it.")


# ---------------------------------------------------------------- Tesseract
def prep(img):
    """The game's light text on dark -> dark on light gray, bigger (Tesseract reads that best). -> (image, scale)."""
    from PIL import ImageOps, ImageStat
    g = img.convert("L")
    w, h = g.size
    scale = 2.0 if h < 1200 else 1.0
    if w * h * scale * scale > MAX_PIXELS:
        scale = max(0.5, (MAX_PIXELS / float(w * h)) ** 0.5)
    if abs(scale - 1) > 0.05:
        g = g.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    if ImageStat.Stat(g).mean[0] < 128:
        g = ImageOps.invert(g)
    return ImageOps.autocontrast(g, cutoff=1), scale


def parse_tsv(text, scale=1.0):
    """Tesseract's TSV -> [(line text, (x0, y0, x1, y1))] in the original picture's pixels, top to bottom."""
    lines = {}
    order = []
    for row in str(text or "").splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        word = c[11].strip()
        if not word:
            continue
        try:
            key = (int(c[1]), int(c[2]), int(c[3]), int(c[4]))
            x, y, w, h = int(c[6]), int(c[7]), int(c[8]), int(c[9])
        except ValueError:
            continue
        if key not in lines:
            lines[key] = [[], [x, y, x + w, y + h]]
            order.append(key)
        words, b = lines[key]
        words.append(word)
        b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)
    out = []
    for key in order:
        words, b = lines[key]
        out.append((" ".join(words), tuple(int(v / scale) for v in b)))
    out.sort(key=lambda t: (t[1][1], t[1][0]))
    return out


class Slow(Exception):
    pass


def _run(args, data, timeout):
    fn = RUNNER[0]
    if fn is not None:
        return fn(args, data, timeout)
    try:
        r = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Slow("slow")
    if r.returncode != 0:
        raise OSError(r.returncode, "tesseract failed")
    return r.stdout.decode("utf-8", "replace")


def tesseract(img, timeout=8.0, psm=None, prepped=False):
    """PIL image -> [(line text, (x0, y0, x1, y1))] with the tesseract command (one run).
    3.0.6 (reader.py): psm - Tesseract's page layout for this read ("7": one line); prepped - the picture is already
    made ready (dark text on light, enlarged), so it is read as it is."""
    pic, scale = (img, 1.0) if prepped else prep(img)
    psm = str(psm or PSM)
    if engine() == "pytesseract" and RUNNER[0] is None:
        import pytesseract
        try:
            tsv = pytesseract.image_to_data(pic, lang=LANG, config=f"--psm {psm}", timeout=timeout)
        except RuntimeError:
            raise Slow("slow")
        return parse_tsv(tsv, scale)
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    args = [tesseract_path() or "tesseract", "stdin", "stdout", "-l", LANG, "--psm", psm, "tsv"]
    return parse_tsv(_run(args, buf.getvalue(), timeout), scale)


# ---------------------------------------------------------------- the helpers' rows (Overlay › Helpers, Linux)
FULL = ("remnant", "desecrate", "temple")          # read text only: nothing works without OCR
PART = ("sekhemas",)                              # matches pictures too: its text reads need OCR


def row_state(key, st, txt):
    """A switched-on helper row's (state, text) -> the same, saying what OCR is missing for (no engine), else as is.
    The ⓘ tooltip (help_text) gives every distro's install line."""
    why = problem()
    if not why or st == "off":
        return st, txt
    if key in FULL:
        if NEEDS in txt:                                 # (Expedition / Desecration say it themselves)
            return "warn", txt.rstrip() + ("" if txt.rstrip().endswith("ⓘ") else "  ⓘ")
        return "warn", f"Can't read the screen: {why}.  ⓘ"
    if key in PART and NEEDS not in txt:
        return st, f"{txt} · reading text {NEEDS}  ⓘ"
    return st, txt
