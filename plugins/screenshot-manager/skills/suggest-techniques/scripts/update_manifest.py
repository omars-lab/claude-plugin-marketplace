#!/usr/bin/env python3
"""Merge entries into techniques.json, the manifest of the Techniques folder.

technique-manager reads this manifest to know which screenshots are techniques and
which ones still need a page. Entries are keyed by file name; a re-run updates in place.

Usage:
    python3 update_manifest.py --entries entries.json [--root <techniques folder>]
    echo '[{...}]' | python3 update_manifest.py

Entry shape:
    {"file": "Screenshot ... .png", "taken": "2026-01-01T09:00:00", "mechanism": "hooks",
     "title": "Short title", "reason": "One line on why it is worth keeping",
     "score": 4, "group": "g03"}

Output (JSON on stdout):
    {"manifest": "<path>", "added": N, "updated": N, "total": N}
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

DEFAULT_ROOT = Path.home() / "Desktop" / "📸 Screenshots of Techniques"


def key(name: str) -> str:
    return unicodedata.normalize("NFC", name).replace(" ", " ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--entries", help="JSON file with a list of entries (default: stdin)")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    if not root.exists():
        root = Path(unicodedata.normalize("NFD", str(root)))
    if not root.exists():
        raise SystemExit(f"Techniques folder not found: {args.root}")
    entries = json.loads(Path(args.entries).read_text() if args.entries else sys.stdin.read())

    path = root / "techniques.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "techniques": []}
    by_file = {key(t["file"]): t for t in manifest["techniques"]}
    added = updated = 0
    for e in entries:
        if not e.get("file"):
            continue
        k = key(e["file"])
        if k in by_file:
            by_file[k].update(e)
            updated += 1
        else:
            by_file[k] = dict(e)
            added += 1
    manifest["techniques"] = sorted(by_file.values(), key=lambda t: t.get("taken") or t["file"])
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(path), "added": added, "updated": updated,
                      "total": len(manifest["techniques"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
