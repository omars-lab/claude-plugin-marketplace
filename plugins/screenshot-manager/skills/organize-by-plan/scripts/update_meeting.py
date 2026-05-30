#!/usr/bin/env python3
"""Idempotently append screenshot references to a NotePlan meeting note.

Usage:
    # Update existing meeting note:
    python3 update_meeting.py --meeting-file PATH --entries JSON_ARRAY

    # Create placeholder + update:
    python3 update_meeting.py --create --meeting-file PATH --title TITLE \
                               --date YYMMDD --domain-emoji EMOJI \
                               --entries JSON_ARRAY

Entries JSON array items:
    new_filename   required  Renamed screenshot filename
    abs_path       required  Absolute post-move path to the screenshot
    ocr_excerpt    optional  Up to 120 chars of OCR text

Appends under a `## Screenshots` section (created if missing).
Idempotent: entries already present by new_filename are skipped.
Never modifies content above the `## Screenshots` section.
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path
from datetime import date as date_cls

MEETING_ROOTS = {
    "🏢": "Notes/🏢 ServiceNow/👤 Meetings",
    "🏡": "Notes/🏡 Personal/🏡👥 Meetings",
    "☕️": "Notes/☕️ NaqshCoffee/☕️👤 Meetings",
    "👥": "Notes/👥 EarlBear/👥 Meetings",
}

NOTEPLAN_ROOT = (
    Path.home()
    / "Library"
    / "Containers"
    / "co.noteplan.NotePlan3"
    / "Data"
    / "Library"
    / "Application Support"
    / "co.noteplan.NotePlan3"
)


def entry_bullet(new_filename: str, abs_path: str, ocr_excerpt: str) -> str:
    excerpt = (ocr_excerpt or "").strip()[:120]
    link = f"[{new_filename}](file://{abs_path})"
    if excerpt:
        return f"- {link} — OCR: \"{excerpt}\""
    return f"- {link}"


def build_placeholder(title: str, yymmdd: str, domain_emoji: str) -> str:
    """Minimal meeting note stub."""
    lines = [
        "---",
        f"doctype: 👤",
        f"date: {yymmdd}",
        "---",
        "",
        f"# {domain_emoji} {yymmdd} {title}",
        "",
        "## Notes",
        "",
        "## Screenshots",
        "",
    ]
    return "\n".join(lines)


def update_meeting(meeting_file: Path, entries: list) -> None:
    if not meeting_file.exists():
        print(f"Error: meeting file not found: {meeting_file}", file=sys.stderr)
        sys.exit(1)

    content = meeting_file.read_text(encoding="utf-8")
    changed = False

    for entry in entries:
        new_filename = entry.get("new_filename", "")
        abs_path = entry.get("abs_path", "")
        ocr_excerpt = entry.get("ocr_excerpt", "")

        if not new_filename or not abs_path:
            continue

        # Idempotency check
        if new_filename in content:
            continue

        bullet = entry_bullet(new_filename, abs_path, ocr_excerpt)

        if "## Screenshots" in content:
            # Insert after the ## Screenshots header
            parts = content.split("## Screenshots", 1)
            before = parts[0] + "## Screenshots"
            after = parts[1]
            # Skip blank lines immediately after header, then insert
            lines = after.split("\n")
            insert_idx = 1  # after the newline following the header
            while insert_idx < len(lines) and not lines[insert_idx].strip():
                insert_idx += 1
            lines.insert(insert_idx, bullet)
            content = before + "\n".join(lines)
        else:
            # Append ## Screenshots section at end
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n## Screenshots\n\n{bullet}\n"

        changed = True

    if changed:
        meeting_file.write_text(content, encoding="utf-8")


def create_and_update(meeting_file: Path, title: str, yymmdd: str,
                      domain_emoji: str, entries: list) -> None:
    if not meeting_file.exists():
        meeting_file.parent.mkdir(parents=True, exist_ok=True)
        content = build_placeholder(title, yymmdd, domain_emoji)
        meeting_file.write_text(content, encoding="utf-8")
    update_meeting(meeting_file, entries)


def main():
    args = sys.argv[1:]
    create = "--create" in args
    meeting_file = None
    title = ""
    yymmdd = ""
    domain_emoji = "🏡"
    entries_json = None

    if "--meeting-file" in args:
        idx = args.index("--meeting-file")
        meeting_file = Path(unicodedata.normalize("NFC", os.path.expanduser(args[idx + 1])))
    if "--title" in args:
        idx = args.index("--title")
        title = args[idx + 1]
    if "--date" in args:
        idx = args.index("--date")
        yymmdd = args[idx + 1]
    if "--domain-emoji" in args:
        idx = args.index("--domain-emoji")
        domain_emoji = args[idx + 1]
    if "--entries" in args:
        idx = args.index("--entries")
        entries_json = args[idx + 1]

    if not meeting_file or not entries_json:
        print("Usage: update_meeting.py --meeting-file PATH --entries JSON_ARRAY", file=sys.stderr)
        sys.exit(1)

    try:
        entries = json.loads(entries_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing entries JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if create:
        create_and_update(meeting_file, title, yymmdd, domain_emoji, entries)
    else:
        update_meeting(meeting_file, entries)


if __name__ == "__main__":
    main()
