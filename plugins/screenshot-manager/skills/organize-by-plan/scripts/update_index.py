#!/usr/bin/env python3
"""Idempotently update (or create) a plan subdir's INDEX.md.

Usage:
    python3 update_index.py --subdir PATH --entry JSON_STRING

Entry JSON fields:
    new_filename   required  Renamed screenshot filename (e.g. "20260424-092158 batch-ocr.png")
    original       optional  Original macOS filename before rename
    mtime          required  ISO date "YYYY-MM-DD"
    ocr_excerpt    optional  Up to 120 chars of OCR text
    plan_file      optional  Absolute path to matched plan .md (for wikilink frontmatter)

Idempotent: if new_filename already appears in the INDEX.md, the call is a no-op.
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path
from datetime import date as date_cls


def load_index(index_path: Path) -> str:
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return ""


def extract_plan_title(plan_file: str) -> str:
    """Return plan filename without .md for wikilink."""
    if not plan_file:
        return ""
    name = Path(plan_file).name
    return name[:-3] if name.endswith(".md") else name


def build_stub(subdir: Path, plan_file: str) -> str:
    """Build a fresh INDEX.md stub."""
    plan_title = extract_plan_title(plan_file)
    today = date_cls.today().isoformat()
    subdir_name = unicodedata.normalize("NFC", subdir.name)
    lines = [f"---"]
    if plan_title:
        lines.append(f"plan: [[{plan_title}]]")
    else:
        lines.append(f"plan: null")
    lines += [f"updated: {today}", "---", "", f"# {subdir_name} — Screenshots", ""]
    return "\n".join(lines)


def entry_line(new_filename: str, ocr_excerpt: str) -> str:
    excerpt = (ocr_excerpt or "").strip()[:120]
    if excerpt:
        return f"- **{new_filename}**\n  OCR excerpt: \"{excerpt}\""
    return f"- **{new_filename}**"


def update_index(subdir: Path, entry: dict) -> None:
    new_filename = entry.get("new_filename", "")
    mtime = entry.get("mtime", date_cls.today().isoformat())
    ocr_excerpt = entry.get("ocr_excerpt", "")
    plan_file = entry.get("plan_file", "")

    if not new_filename:
        print("Error: new_filename is required", file=sys.stderr)
        sys.exit(1)

    index_path = subdir / "INDEX.md"
    content = load_index(index_path)

    if not content:
        content = build_stub(subdir, plan_file)

    # Idempotency check
    if new_filename in content:
        return

    # Update frontmatter updated date
    today = date_cls.today().isoformat()
    content = re.sub(r"^updated: .+$", f"updated: {today}", content, flags=re.MULTILINE)

    # Parse date for section header (YYYY-MM-DD → ## YYYY-MM-DD)
    try:
        section_date = mtime[:10]
    except (TypeError, IndexError):
        section_date = today
    section_header = f"## {section_date}"

    new_entry = entry_line(new_filename, ocr_excerpt)

    if section_header in content:
        # Insert entry after the section header (find the header, then find where to insert)
        parts = content.split(section_header, 1)
        before = parts[0] + section_header
        after = parts[1]
        # Insert after any blank lines immediately following the header
        lines = after.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if i == 0 and not line.strip():
                insert_idx = 1
                break
            break
        lines.insert(insert_idx + 1, new_entry)
        content = before + "\n".join(lines)
    else:
        # Add new section before next ## section or at end
        # Find insertion point: insert in descending date order
        sections = re.findall(r"^## (\d{4}-\d{2}-\d{2})", content, re.MULTILINE)
        inserted = False
        if sections:
            # Find the first existing section that is older than section_date
            for existing_date in sections:
                if existing_date < section_date:
                    # Insert before this section
                    old_section_header = f"## {existing_date}"
                    new_section = f"\n{section_header}\n\n{new_entry}\n"
                    content = content.replace(old_section_header, new_section + old_section_header, 1)
                    inserted = True
                    break
        if not inserted:
            # Append at end
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n{section_header}\n\n{new_entry}\n"

    subdir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")


def main():
    args = sys.argv[1:]
    subdir_path = None
    entry_json = None

    if "--subdir" in args:
        idx = args.index("--subdir")
        subdir_path = Path(unicodedata.normalize("NFC", os.path.expanduser(args[idx + 1])))
    if "--entry" in args:
        idx = args.index("--entry")
        entry_json = args[idx + 1]

    if not subdir_path or not entry_json:
        print("Usage: update_index.py --subdir PATH --entry JSON_STRING", file=sys.stderr)
        sys.exit(1)

    try:
        entry = json.loads(entry_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing entry JSON: {e}", file=sys.stderr)
        sys.exit(1)

    update_index(subdir_path, entry)


if __name__ == "__main__":
    main()
