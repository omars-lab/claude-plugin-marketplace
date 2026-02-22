#!/usr/bin/env python3
"""Inventory screenshots directories and Desktop images.

Default (no flags): scans both the Screenshots root AND the Desktop.

Usage:
    python3 scan_inventory.py                    # Screenshots + Desktop (default)
    python3 scan_inventory.py --desktop          # Screenshots + Desktop (explicit)
    python3 scan_inventory.py --screenshots-only # Screenshots root only
    python3 scan_inventory.py --desktop-only     # Desktop only
    python3 scan_inventory.py --root /custom/path [--desktop]

Output:
    JSON with keys:
      "directories": {dir_name: {files, earliest, latest, range_days}}
      "desktop":     [{name, mtime}]  (included by default and with --desktop)
      "_summary":    {root, directory_count, total_files, desktop_image_count}
"""
import json
import sys
import os
import unicodedata
from pathlib import Path
from datetime import datetime

EXTS = {".png", ".jpg", ".jpeg", ".heic", ".pdf"}


def file_entry(f: Path) -> dict:
    mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return {"name": f.name, "mtime": mtime}


def scan_dir(root: Path) -> dict:
    inventory = {}
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        files = []
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in EXTS:
                files.append(file_entry(f))
        if files:
            dates = [e["mtime"][:10] for e in files]
            inventory[d.name] = {
                "files": files,
                "earliest": min(dates),
                "latest": max(dates),
                "range_days": (
                    datetime.strptime(max(dates), "%Y-%m-%d")
                    - datetime.strptime(min(dates), "%Y-%m-%d")
                ).days,
            }
    return inventory


def scan_desktop() -> list:
    desktop = Path.home() / "Desktop"
    images = []
    for f in sorted(desktop.iterdir()):
        if f.suffix.lower() in EXTS:
            images.append(file_entry(f))
    return images


def main():
    args = sys.argv[1:]
    desktop_only = "--desktop-only" in args
    screenshots_only = "--screenshots-only" in args
    # Default: scan both Screenshots and Desktop unless a scope flag says otherwise
    want_desktop = not screenshots_only
    want_screenshots = not desktop_only

    result = {}

    if want_screenshots:
        root = None
        if "--root" in args:
            idx = args.index("--root")
            if idx + 1 < len(args):
                raw = args[idx + 1]
                # Normalize unicode in path (handles copy-pasted emoji paths)
                root = Path(unicodedata.normalize("NFC", os.path.expanduser(raw)))
        if root is None:
            root = (
                Path.home()
                / "Library"
                / "CloudStorage"
                / "OneDrive-ServiceNow"
                / "\U0001f4f8 Screenshots"
            )
        result["directories"] = scan_dir(root)
        total_files = sum(len(v["files"]) for v in result["directories"].values())
        result["_summary"] = {
            "root": str(root),
            "directory_count": len(result["directories"]),
            "total_files": total_files,
        }

    if want_desktop:
        result["desktop"] = scan_desktop()
        result.setdefault("_summary", {})["desktop_image_count"] = len(result["desktop"])

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
