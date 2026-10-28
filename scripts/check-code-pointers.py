#!/usr/bin/env python3
"""Check that a doc's links into the code still point at something, so a refactor can't leave them stale.

A doc opts in with the line `<!-- code-pointers: checked -->`. Every relative Markdown link in it,
`[text](path)` or `[text](path#name)`, must name a file that exists, and `#name` must name something
defined in that file:

  .py           a def, class or top-level NAME = at the start of a line
  Makefile, .mk a target (name:)
  .sh           a function, name() or function name
  .js .mjs .ts  a function, class, or const/let/var
  .md           a heading, as GitHub makes its anchor (lower case, spaces to hyphens)
  other files   the word appears in the file

`#L12` style line anchors are refused: they go stale with every edit. Name the function instead.
Web links (http:, https:, mailto:) are left alone.

Usage: check-code-pointers.py [--fix] [doc ...]     (default: every opted-in doc in the repo)
Prints each broken link as doc:line: target — why, and exits 1 when one is left.
--fix repoints a link when the answer is unique: a moved file that exactly one tracked file of the
same name replaces, or a name now defined in exactly one other tracked file. It prints what it
changed and what it could not fix, which needs a person to pick the new target.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "<!-- code-pointers: checked -->"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
WEB = ("http:", "https:", "mailto:")


def tracked():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True)
    return [ROOT / p for p in out.stdout.splitlines()]


def opted_in(files):
    docs = []
    for p in files:
        if p.suffix == ".md" and p.is_file():
            try:
                if MARKER in p.read_text(errors="ignore"):
                    docs.append(p)
            except OSError:
                continue
    return docs


def slug(heading):
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


def defines(path, name):
    """True when `name` is defined in the file at `path` (see the module doc for what counts)."""
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    n = re.escape(name)
    ext = path.suffix
    if ext == ".py":
        pat = rf"^\s*(?:async\s+)?(?:def|class)\s+{n}\b|^{n}\s*[:=]"
    elif path.name == "Makefile" or ext == ".mk":
        pat = rf"^{n}\s*:"
    elif ext == ".sh":
        pat = rf"^\s*(?:function\s+{n}\b|{n}\s*\(\))"
    elif ext in (".js", ".mjs", ".cjs", ".ts"):
        pat = rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?\s+{n}\b|class\s+{n}\b|(?:const|let|var)\s+{n}\b)"
    elif ext == ".md":
        return any(slug(h) == name.lower() for h in re.findall(r"^#+\s+(.+?)\s*#*$", text, re.M))
    else:
        return re.search(rf"\b{n}\b", text) is not None
    return re.search(pat, text, re.M) is not None


def problem(doc, target):
    """Why the link `target` in `doc` is broken, or None."""
    path, _, name = target.partition("#")
    file = (doc.parent / path).resolve() if path else doc
    if not file.exists():
        return "file not found"
    if name and re.fullmatch(r"L\d+(-L?\d+)?", name):
        return "a line-number anchor goes stale; name the function instead"
    if name and file.is_file() and not defines(file, name):
        return f"{name!r} is not defined in {file.name}"
    return None


def fixed(doc, target, files):
    """A repointed target when exactly one tracked file fits, else None."""
    path, _, name = target.partition("#")
    if not path or re.fullmatch(r"L\d+(-L?\d+)?", name or ""):
        return None
    file = (doc.parent / path).resolve()
    if not file.exists():
        cands = [f for f in files if f.name == file.name and f.is_file() and (not name or defines(f, name))]
    else:
        cands = [f for f in files if f.suffix == file.suffix and f.is_file() and f != file and defines(f, name)]
    if len(cands) != 1:
        return None
    new = os.path.relpath(cands[0], doc.parent)
    return new + (f"#{name}" if name else "")


def check(doc, files, fix):
    lines = doc.read_text().splitlines(keepends=True)
    left, changed = [], []
    for i, line in enumerate(lines):
        for target in LINK.findall(line):
            if target.startswith(WEB):
                continue
            why = problem(doc, target)
            if not why:
                continue
            new = fixed(doc, target, files) if fix else None
            if new:
                lines[i] = lines[i].replace(f"]({target})", f"]({new})")
                changed.append(f"{doc.relative_to(ROOT)}:{i + 1}: {target} → {new}")
            else:
                left.append(f"{doc.relative_to(ROOT)}:{i + 1}: {target} — {why}")
    if changed:
        doc.write_text("".join(lines))
    return left, changed


def main(argv):
    fix = "--fix" in argv
    names = [a for a in argv if a != "--fix"]
    files = tracked()
    docs = [Path(n).resolve() for n in names] if names else opted_in(files)
    left, changed = [], []
    for doc in docs:
        lt, ch = check(doc, files, fix)
        left += lt
        changed += ch
    for c in changed:
        print(f"repointed {c}")
    for b in left:
        print(b)
    if left:
        hint = "" if fix else " Run scripts/check-code-pointers.py --fix to repoint the ones with one clear new home."
        print(f"code-pointers: {len(left)} link(s) in {MARKER!r} docs point at code that moved or was renamed.{hint}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
