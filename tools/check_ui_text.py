"""No parenthesis asides in UI text: "Search it first (Enter)" or "Your session is kept (paused)" puts a detail in
brackets. The detail goes in the tooltip, or the sentence is rewritten.

Looks at every string in soe2/ and stashofexile2.py that a person may read: not docstrings, not raw strings such
as regexes, not SQL. A credit's name or license, like "Cinzel (Natanael Gama)" or "(MIT)", and a Windows path
like "Program Files (x86)" are allowed.

Strings that were there before this check came in are listed in tools/ui_text_baseline.txt and still pass. A new
one fails. Rewrite it instead of adding it to the baseline. To shrink the baseline after a rewrite, run
    python tools/check_ui_text.py --update
which drops the lines that no longer exist and never adds new ones.

3.3.0 owner, Google developer style: no hype or filler words in UI text either - "seamless", "robust",
"powerful", "simply", "just", "easily", "really", "please note". Greetings and What's New history are left as
written; "just now" and Mod Lab's "Just rated" name a time, not filler; item names like Robust Crossbow are the game's.

Run: python tools/check_ui_text.py - it exits with 1 and lists each new string."""
import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tools", "ui_text_baseline.txt")
ASIDE = re.compile(r"[A-Za-z0-9.,'’%+?!]\s\(([A-Za-z][^()]{0,80})\)")
# 3.3.0 owner: a keyboard shortcut after an action, "Undo (Ctrl+Z)", is how apps write it - allowed
ALLOWED = re.compile(r"^(?:x86|MIT|SIL Open Font License|CC BY[^)]*|Apache[^)]*|BSD[^)]*|optional|"
                     r"(?:Ctrl|Shift|Alt)\+[^()]{1,20}|F\d{1,2}|Del|Enter|Esc|[A-Z])$")
SQL = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|WHERE)\b")
CREDIT_FILES = ("soe2/about_page.py",)
FILLER = re.compile(r"\b(seamless(ly)?|robust|powerful|simply|just|easily|really|please note|it is important to note)\b",
                    re.I)
FILLER_OK = re.compile(r"\bjust (now|rated)\b|Robust (Crossbow|\b)", re.I)
FILLER_SKIP = ("soe2/greetings.py", "soe2/whatsnew.py", "soe2/class_icons.py", "soe2/stashlayouts.py")       # credits put a person's or a project's name in brackets after the work


def files():
    yield os.path.join(ROOT, "stashofexile2.py")
    for dp, dn, fn in os.walk(os.path.join(ROOT, "soe2")):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in sorted(fn):
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def doc_lines(tree):
    """The first lines of docstrings and of bare string statements - text for developers, not for players."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            out.add(n.lineno)
    return out


def hits():
    """Every string with an aside, as a list of relative path, line and the string as written."""
    out = []
    for p in files():
        if not os.path.exists(p):
            continue
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        src = open(p, encoding="utf-8").read()
        try:
            docs = doc_lines(ast.parse(src))
        except SyntaxError:
            continue
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if tokenize.tok_name[t.type] not in ("STRING", "FSTRING_MIDDLE"):
                continue
            s = t.string
            if t.start[0] in docs or re.match(r"^[rRbB]{1,2}['\"]", s) or SQL.search(s):
                continue
            if rel not in FILLER_SKIP and FILLER.search(FILLER_OK.sub("", s)):
                out.append((rel, t.start[0], s.strip()))
                continue
            for m in ASIDE.finditer(s):
                inner = m.group(1)
                if ALLOWED.match(inner) or rel in CREDIT_FILES and m.start() < 80 and "the " not in inner:
                    continue
                out.append((rel, t.start[0], s.strip()))
                break
    return out


def key(rel, s):
    return f"{rel}\t{' '.join(s.split())}"


def load():
    try:
        return {ln.rstrip("\n") for ln in open(BASELINE, encoding="utf-8") if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def main(argv):
    found = hits()
    base = load()
    if "--update" in argv:
        now = {key(r, s) for r, _ln, s in found}
        kept = sorted(base & now)
        with open(BASELINE, "w", encoding="utf-8") as f:
            f.write("# Strings with a parenthesis aside from before tools/check_ui_text.py. Shrink only; never add.\n")
            f.write("\n".join(kept) + "\n")
        print(f"UI text baseline: {len(kept)} kept, {len(base) - len(kept)} gone")
        return 0
    new = [(r, ln, s) for r, ln, s in found if key(r, s) not in base]
    if new:
        print("UI text with a parenthesis aside or a filler word - say it plainly, detail in the tooltip:")
        for r, ln, s in new:
            print(f"  {r}:{ln}: {s[:140]}")
        return 1
    print(f"UI text: no new parenthesis asides ({len(base)} older ones in the baseline to rewrite)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
