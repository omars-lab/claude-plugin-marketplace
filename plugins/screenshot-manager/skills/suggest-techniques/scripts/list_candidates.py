#!/usr/bin/env python3
"""List screenshots in a folder with their capture time, grouped into burst sequences.

Screenshots taken within --gap seconds of the previous one share a group id, so a
multi-shot walkthrough is reviewed (and moved) as one unit.

Usage:
    python3 list_candidates.py                       # ~/Desktop
    python3 list_candidates.py --dir <folder> --gap 120
    python3 list_candidates.py --alias-dir /tmp/st/desk   # also make plain-named symlinks

--alias-dir writes one symlink per screenshot named NN_<taken>_<group>.png. macOS names
carry a U+202F space before AM/PM, which is easy to mistype when opening a file to look at
it; the aliases sort by time and are safe to pass to an image viewer or the Read tool.

Output (JSON on stdout):
    [{"n", "path", "name", "taken": "YYYY-MM-DDTHH:MM:SS", "group": "g01", "group_size": N,
      "alias": "<path>" (with --alias-dir)}, ...]
"""
import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

NAME = re.compile(
    r"Screen ?[Ss]hot (\d{4}-\d{2}-\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})\s?(AM|PM)"
)


def taken(path: Path) -> dt.datetime:
    name = unicodedata.normalize("NFC", path.name).replace(" ", " ")
    m = NAME.search(name)
    if not m:
        return dt.datetime.fromtimestamp(path.stat().st_mtime)
    day, h, mi, s, ampm = m.groups()
    h = int(h) % 12 + (12 if ampm == "PM" else 0)
    return dt.datetime.fromisoformat(f"{day}T{h:02d}:{mi}:{s}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(Path.home() / "Desktop"))
    ap.add_argument("--gap", type=int, default=120, help="max seconds between shots in one group")
    ap.add_argument("--alias-dir", help="write plain-named symlinks to each screenshot here")
    args = ap.parse_args()

    folder = Path(args.dir).expanduser()
    shots = [p for p in folder.iterdir()
             if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".heic")
             and unicodedata.normalize("NFC", p.name).lower().startswith(("screenshot", "screen shot"))]
    rows = sorted(({"path": str(p), "name": p.name, "t": taken(p)} for p in shots), key=lambda r: r["t"])

    group, prev = 0, None
    for r in rows:
        if prev is None or (r["t"] - prev).total_seconds() > args.gap:
            group += 1
        r["group"] = f"g{group:02d}"
        prev = r["t"]
    sizes = {}
    for r in rows:
        sizes[r["group"]] = sizes.get(r["group"], 0) + 1
    out = [{"n": i, "path": r["path"], "name": r["name"], "taken": r["t"].isoformat(timespec="seconds"),
            "group": r["group"], "group_size": sizes[r["group"]]} for i, r in enumerate(rows, 1)]
    if args.alias_dir:
        alias_dir = Path(args.alias_dir).expanduser()
        alias_dir.mkdir(parents=True, exist_ok=True)
        for r in out:
            alias = alias_dir / f"{r['n']:02d}_{r['taken'].replace(':', '')}_{r['group']}{Path(r['name']).suffix.lower()}"
            if alias.is_symlink() or alias.exists():
                alias.unlink()
            alias.symlink_to(r["path"])
            r["alias"] = str(alias)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
