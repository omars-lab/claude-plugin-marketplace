#!/usr/bin/env python3
"""Move screenshot files according to a JSON manifest.

Handles macOS screenshot filenames that use U+202F (NARROW NO-BREAK SPACE)
before AM/PM. All moves use shutil.move() for safety.

Usage:
    python3 move_files.py --manifest /path/to/moves.json

    # Or pipe JSON directly:
    echo '[{"src": "/Desktop/Screenshot.png", "dest_dir": "/Screenshots/MyDir"}]' \
        | python3 move_files.py

Manifest format (JSON array):
    [
        {"src": "/full/path/to/file.png", "dest_dir": "/full/path/to/destination/"},
        ...
    ]

    dest_dir will be created if it does not exist.

Output:
    JSON: {"moved": [...], "failed": [...]}
"""
import json
import os
import shutil
import sys
import unicodedata
from pathlib import Path


def resolve_src(raw: str) -> Path | None:
    """Resolve a source path that may have NNBSP vs regular space mismatch."""
    for form in ("NFC", "NFD"):
        p = Path(unicodedata.normalize(form, raw))
        if p.exists():
            return p

    # Fallback: scan parent dir for a matching filename
    p = Path(raw)
    parent = p.parent
    name_norm = unicodedata.normalize("NFC", p.name).replace("\u202f", " ")
    for form in ("NFC", "NFD"):
        try:
            parent_norm = Path(unicodedata.normalize(form, str(parent)))
            for entry in os.listdir(parent_norm):
                entry_norm = unicodedata.normalize("NFC", entry).replace("\u202f", " ")
                if entry_norm == name_norm:
                    return parent_norm / entry
        except FileNotFoundError:
            pass

    return None  # not found


def main():
    args = sys.argv[1:]

    # Load manifest from --manifest flag or stdin
    if "--manifest" in args:
        idx = args.index("--manifest")
        manifest_path = args[idx + 1]
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = json.load(sys.stdin)

    moved = []
    failed = []

    for entry in manifest:
        raw_src = entry.get("src", "")
        raw_dest_dir = entry.get("dest_dir", "")

        if not raw_src or not raw_dest_dir:
            failed.append({"entry": entry, "error": "Missing 'src' or 'dest_dir'"})
            continue

        src = resolve_src(raw_src)
        if src is None or not src.exists():
            failed.append({"src": raw_src, "error": "Source file not found"})
            continue

        dest_dir = Path(unicodedata.normalize("NFC", os.path.expanduser(raw_dest_dir)))
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name

        try:
            shutil.move(str(src), str(dest))
            moved.append({"src": str(src), "dest": str(dest)})
        except Exception as e:
            failed.append({"src": str(src), "dest": str(dest), "error": str(e)})

    result = {"moved": moved, "failed": failed}
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
