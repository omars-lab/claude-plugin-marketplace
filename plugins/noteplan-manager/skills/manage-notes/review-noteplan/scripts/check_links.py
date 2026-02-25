#!/usr/bin/env python3
"""
check_links.py
Discover and validate all links in a NotePlan vault.

Checks:
  - [[wikilinks]] — validates target file exists in notes dir
  - [text](path) — validates relative paths resolve
  - Headers with trailing whitespace (common NotePlan sync artifact)

Usage:
  python3 check_links.py --notes-dir /path/to/Notes
  python3 check_links.py --notes-dir /path/to/Notes --output results.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ── Patterns ───────────────────────────────────────────────────────────────────

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.*?)\s+$")  # trailing space on header


def find_all_note_names(notes_dir: Path) -> set[str]:
    """Build a set of all note names (filename without .md, lowercased for fuzzy match)."""
    names = set()
    for filepath in notes_dir.rglob("*.md"):
        stem = filepath.stem
        names.add(stem)
        names.add(stem.lower())
    return names


def resolve_wikilink(link_text: str, note_names: set[str]) -> bool:
    """Return True if the wikilink target exists."""
    # Strip anchor (#section) if present
    target = link_text.split("#")[0].strip()
    if not target:
        return True  # anchor-only link, assume valid
    # Exact match or case-insensitive match
    return target in note_names or target.lower() in note_names


def check_file(filepath: Path, notes_dir: Path, note_names: set[str]) -> dict:
    """Return link and header findings for a single file."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"file": str(filepath), "error": "unreadable"}

    lines = text.splitlines()
    broken_links = []
    headers_with_trailing_space = []
    all_links = []

    for i, line in enumerate(lines, 1):
        # Wiki links
        for match in WIKILINK_PATTERN.finditer(line):
            link_text = match.group(1)
            all_links.append({"type": "wiki", "link": link_text})
            if not resolve_wikilink(link_text, note_names):
                broken_links.append({
                    "file": str(filepath),
                    "line": i,
                    "link": f"[[{link_text}]]",
                    "reason": "target note not found",
                })

        # Markdown links
        for match in MD_LINK_PATTERN.finditer(line):
            link_target = match.group(2)
            all_links.append({"type": "md", "link": link_target})
            # Skip http/https/mailto links and anchors
            if link_target.startswith(("http://", "https://", "mailto:", "#", "vscode://", "obsidian://")):
                continue
            # Resolve relative path from file's parent
            resolved = (filepath.parent / link_target).resolve()
            if not resolved.exists():
                broken_links.append({
                    "file": str(filepath),
                    "line": i,
                    "link": link_target,
                    "reason": "file not found",
                })

        # Headers with trailing whitespace
        if HEADER_PATTERN.match(line):
            headers_with_trailing_space.append({
                "file": str(filepath),
                "line": i,
                "header": repr(line),
            })

    return {
        "file": str(filepath),
        "links_found": len(all_links),
        "broken_links": broken_links,
        "headers_with_trailing_space": headers_with_trailing_space,
    }


def main():
    parser = argparse.ArgumentParser(description="Check links in a NotePlan vault")
    parser.add_argument("--notes-dir", required=True, help="Path to NotePlan Notes directory")
    parser.add_argument("--output", help="Output JSON path (default: stdout)")
    parser.add_argument("--broken-only", action="store_true", help="Only report broken links")
    args = parser.parse_args()

    notes_dir = Path(args.notes_dir)
    if not notes_dir.exists():
        print(f"Error: notes dir not found: {notes_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Building note index...", file=sys.stderr)
    note_names = find_all_note_names(notes_dir)
    md_files = list(notes_dir.rglob("*.md"))
    print(f"Checking {len(md_files)} files...", file=sys.stderr)

    all_broken: list[dict] = []
    all_headers: list[dict] = []
    total_links = 0

    for filepath in md_files:
        result = check_file(filepath, notes_dir, note_names)
        if "error" in result:
            continue
        total_links += result["links_found"]
        all_broken.extend(result["broken_links"])
        all_headers.extend(result["headers_with_trailing_space"])

    # Deduplicate broken links by (file, line)
    seen = set()
    deduped_broken = []
    for item in all_broken:
        key = (item["file"], item["line"], item["link"])
        if key not in seen:
            seen.add(key)
            deduped_broken.append(item)

    unique_links = len({item["link"] for item in all_broken} | set())  # rough unique count

    output = {
        "summary": {
            "files_checked": len(md_files),
            "total_links": total_links,
            "broken_links": len(deduped_broken),
            "headers_with_trailing_space": len(all_headers),
        },
        "broken_links": deduped_broken,
        "headers_with_trailing_space": all_headers,
    }

    output_json = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"✓ Checked {len(md_files)} files → {len(deduped_broken)} broken links, "
              f"{len(all_headers)} headers with trailing space", file=sys.stderr)
        print(f"✓ Results written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
