#!/usr/bin/env python3
"""Check that every function and class of an old module still exists, unchanged, in the new code.

    python3 scripts/review/moved_functions_check.py OLD_FILE NEW_FILE_OR_DIR [...]

OLD_FILE is a Python file (for the application-factory job: backend/app.py as it
is on main, e.g. from `git show origin/main:backend/app.py > /tmp/app_old.py`).
The NEW arguments are files or folders; every .py file under them is parsed.

For each function and class defined in OLD_FILE (at any depth) the check looks for
a definition of the same name in the new files and compares the two with ast.dump,
line numbers left out. Two comparisons are made:
  body      the arguments, the body and the return annotation
  decorators the decorator list
A function passes when some definition of that name matches on both. A function
whose body matches but whose decorators differ is listed separately (a route that
moved from @app.route to @blueprint.route), so a person can look at each. A
function with no matching body is a failure and the exit status is 1.
"""
import ast
import os
import sys


def _defs(tree):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(node)
    return out


def _body_dump(node):
    if isinstance(node, ast.ClassDef):
        parts = [node.bases, node.keywords, node.body]
    else:
        parts = [node.args, node.body, node.returns]
    elts = []
    for p in parts:
        if isinstance(p, ast.AST):
            elts.append(p)
        elif isinstance(p, list):
            elts.append(ast.List(elts=p, ctx=ast.Load()))
        else:
            elts.append(ast.Constant(None))
    return ast.dump(ast.Tuple(elts=elts, ctx=ast.Load()), include_attributes=False)


def _deco_dump(node):
    return ast.dump(ast.List(elts=list(node.decorator_list), ctx=ast.Load()), include_attributes=False)


def _py_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in ('node_modules', '__pycache__', 'venv', '.git')]
                for f in files:
                    if f.endswith('.py'):
                        yield os.path.join(root, f)
        else:
            yield p


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    old = ast.parse(open(sys.argv[1], encoding='utf-8').read())
    new = {}  # name -> list of (file, body_dump, deco_dump)
    for path in _py_files(sys.argv[2:]):
        try:
            tree = ast.parse(open(path, encoding='utf-8').read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in _defs(tree):
            new.setdefault(node.name, []).append((path, _body_dump(node), _deco_dump(node)))
    checked = 0
    deco_only = []
    missing = []
    differ = []
    for node in _defs(old):
        checked += 1
        cands = new.get(node.name, [])
        if not cands:
            missing.append(node.name)
            continue
        body, deco = _body_dump(node), _deco_dump(node)
        if any(c[1] == body and c[2] == deco for c in cands):
            continue
        if any(c[1] == body for c in cands):
            deco_only.append((node.name, [c[0] for c in cands if c[1] == body][0]))
        else:
            differ.append((node.name, [c[0] for c in cands]))
    print(f"checked {checked} functions and classes")
    print(f"identical body and decorators: {checked - len(deco_only) - len(missing) - len(differ)}")
    print(f"identical body, decorators differ: {len(deco_only)}")
    for name, where in deco_only:
        print(f"  decorators: {name}  ({where})")
    print(f"missing: {len(missing)}")
    for name in missing:
        print(f"  MISSING: {name}")
    print(f"body differs: {len(differ)}")
    for name, where in differ:
        print(f"  DIFFERS: {name}  (same name in: {', '.join(where)})")
    return 1 if (missing or differ) else 0


if __name__ == '__main__':
    sys.exit(main())
