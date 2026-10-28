#!/usr/bin/env python3
"""forget_unsaved.py — take the saves the last import found no longer saved out of data/.

    forget_unsaved.py [--dry-run]

Reads `gone` from $INSTAGRAM_HOME/.cache/import-diff.json (written by import_saved.py) and, in each
data/*.yaml and data/items/*.yaml keyed by post code, removes that code's whole block as text, so the
rest of the file keeps its exact layout. A code that is back in saves.json is kept. Media files in
the bucket are left alone; git history keeps what was removed.

Logs ev=forget file=... removed=N per file, then ev=forget_end; --dry-run changes nothing.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
from home import cache, home  # noqa: E402
from log import log  # noqa: E402

TOP = re.compile(r"^(['\"]?)([A-Za-z0-9_-]+)\1:")


def drop_blocks(text, codes):
    """(text without the top-level blocks keyed by these codes, how many went)."""
    out, removed, skipping = [], 0, False
    for line in text.splitlines(keepends=True):
        m = TOP.match(line)
        if m or (line.strip() and not line[0].isspace() and not line.startswith("-")):
            skipping = bool(m) and m.group(2) in codes
            removed += skipping
        if not skipping:
            out.append(line)
    return "".join(out), removed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="count what would go; change nothing")
    a = ap.parse_args(argv)
    diff_path = cache("import-diff.json")
    if not os.path.exists(diff_path):
        log("forget_missing", diff=diff_path, msg="run make import first; it writes the diff")
        return 1
    with open(diff_path, encoding="utf-8") as fh:
        gone = set(json.load(fh).get("gone") or [])
    with open(cache("saves.json"), encoding="utf-8") as fh:
        gone -= {s["code"] for s in json.load(fh)["saves"]}
    root = home()
    total = 0
    for path in sorted(glob.glob(os.path.join(root, "data", "*.yaml")) + glob.glob(os.path.join(root, "data", "items", "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new, removed = drop_blocks(text, gone)
        if not removed:
            continue
        total += removed
        log("forget", file=os.path.relpath(path, root), removed=removed, dry_run="yes" if a.dry_run else "no")
        if not a.dry_run:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
    log("forget_end", gone=len(gone), removed=total, dry_run="yes" if a.dry_run else "no")
    print(f"{len(gone)} saves are no longer saved; {'would remove' if a.dry_run else 'removed'} "
          f"{total} entries for them from data/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
