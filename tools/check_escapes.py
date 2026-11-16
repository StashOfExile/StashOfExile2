"""Every .py file compiles with no SyntaxWarning (e.g. an invalid escape like "\\," in a docstring), as the
build does - Python 3.14 prints these while building, and a later Python will make them errors. Round 18: and no
return / break / continue that leaves a finally block (Python 3.14 warns about those too - PEP 765). A warning from
site-packages while building (pystray's _util/gtk.py has a return in a finally block) isn't ours."""
import ast
import subprocess
import sys
import warnings

files = subprocess.check_output(["git", "ls-files", "*.py"]).decode().split()
bad = []
for f in files:
    with open(f, encoding="utf-8") as fh:
        src = fh.read()
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        try:
            compile(src, f, "exec")
        except (SyntaxError, SyntaxWarning) as e:
            bad.append(f"{f}: {e}")
            continue
    for node in ast.walk(ast.parse(src, f)):
        for sub in getattr(node, "finalbody", None) or ():
            todo = [(sub, False)]
            while todo:                                  # (a loop or a def inside the finally may use its own)
                x, inner = todo.pop()
                if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                    continue
                if isinstance(x, ast.Return) or (isinstance(x, (ast.Break, ast.Continue)) and not inner):
                    bad.append(f"{f}:{x.lineno}: {type(x).__name__.lower()} leaves a finally block")
                loop = isinstance(x, (ast.For, ast.While, ast.AsyncFor))
                todo.extend((c, inner or loop) for c in ast.iter_child_nodes(x))
for b in bad:
    print(b)
print(f"check_escapes: {len(files)} files, {len(bad)} with warnings")
sys.exit(1 if bad else 0)
