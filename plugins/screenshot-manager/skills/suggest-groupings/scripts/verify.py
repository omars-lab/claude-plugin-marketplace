#!/usr/bin/env python3
"""Print a file-count summary of each subdirectory in the Screenshots root.

Usage:
    python3 verify.py                  # JSON output
    python3 verify.py --pretty         # Human-readable table
    python3 verify.py --root /custom/path [--pretty]

Output (JSON):
    {root, total_files, dirs: [{dir, file_count, files[]}]}

Output (--pretty):
    N files across M dirs
      <count>  <dir name>
      ...
"""
import json
import sys
import os
import unicodedata
from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".heic", ".pdf"}


def main():
    args = sys.argv[1:]
    pretty = "--pretty" in args
    root = None
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            raw = args[idx + 1]
            root = Path(unicodedata.normalize("NFC", os.path.expanduser(raw)))
    if root is None:
        root = (
            Path.home()
            / "Library"
            / "CloudStorage"
            / "OneDrive-ServiceNow"
            / "\U0001f4f8 Screenshots"
        )

    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        files = [f.name for f in sorted(d.iterdir()) if f.suffix.lower() in EXTS]
        rows.append({"dir": d.name, "file_count": len(files), "files": files})

    total = sum(r["file_count"] for r in rows)

    if pretty:
        print(f"Total: {total} files across {len(rows)} dirs\n")
        for r in rows:
            print(f"  {r['file_count']:3d}  {r['dir']}")
    else:
        print(json.dumps({"root": str(root), "total_files": total, "dirs": rows}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
