#!/usr/bin/env python3
"""Index existing NotePlan meeting notes by date, title, and attendees.

Usage:
    python3 scan_meetings.py [--root PATH] [--date YYMMDD] [--date-range YYMMDD:YYMMDD]

Output:
    JSON array: [{file, date, title, attendees, domain_emoji}]
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path

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

MEETING_ROOTS = [
    ("🏢", "Notes/🏢 ServiceNow/👤 Meetings"),
    ("🏡", "Notes/🏡 Personal/🏡👥 Meetings"),
    ("☕️", "Notes/☕️ NaqshCoffee/☕️👤 Meetings"),
    ("👥", "Notes/👥 EarlBear/👥 Meetings"),
]


def yymmdd_to_iso(raw: str) -> str:
    """Convert YYMMDD string to YYYY-MM-DD."""
    if len(raw) != 6:
        return ""
    try:
        yy, mm, dd = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
        return f"{2000+yy:04d}-{mm:02d}-{dd:02d}"
    except ValueError:
        return ""


def iso_to_yymmdd(iso: str) -> str:
    """Convert YYYY-MM-DD to YYMMDD."""
    parts = iso.replace("-", "")
    if len(parts) == 8:
        return parts[2:]
    return ""


def extract_attendees(text: str) -> list:
    """Extract attendee names from frontmatter, ## Attendees section, or @mentions."""
    attendees = []
    # Frontmatter attendees field
    m = re.search(r"^attendees:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if m:
        raw = m.group(1)
        attendees.extend([a.strip().strip("-").strip() for a in re.split(r"[,;]", raw) if a.strip()])
    # ## Attendees section
    section_m = re.search(r"##\s+Attendees\s*\n(.*?)(?:\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if section_m:
        for line in section_m.group(1).splitlines():
            name = line.strip().lstrip("-*•").strip()
            if name and not name.startswith("#"):
                attendees.append(name)
    # @mentions (e.g. @Ritesh, @omar)
    mentions = re.findall(r"@(\w[\w.]+)", text)
    attendees.extend(mentions)
    # Deduplicate, filter obvious boilerplate
    seen = set()
    result = []
    for a in attendees:
        a_clean = a.strip()
        if a_clean and a_clean.lower() not in seen and len(a_clean) > 1:
            seen.add(a_clean.lower())
            result.append(a_clean)
    return result


def extract_title(filename: str, domain_prefix: str) -> str:
    """Extract meeting title from filename (strip prefix + YYMMDD)."""
    name = filename[:-3] if filename.endswith(".md") else filename
    name = unicodedata.normalize("NFC", name)
    # Find 6-digit date and take everything after
    m = re.search(r"\d{6}\s*(.*)", name)
    if m:
        return m.group(1).strip()
    # Fallback: strip leading non-ASCII then return
    return re.sub(r"^[^\w\s]+\s*", "", name).strip()


def date_in_range(date_iso: str, lo_yymmdd: str, hi_yymmdd: str) -> bool:
    lo = yymmdd_to_iso(lo_yymmdd)
    hi = yymmdd_to_iso(hi_yymmdd)
    return lo <= date_iso <= hi


def scan_meetings(root: Path, filter_date: str = None, date_range: tuple = None) -> list:
    meetings = []
    for domain_emoji, rel_path in MEETING_ROOTS:
        meeting_root = root / rel_path
        if not meeting_root.exists():
            continue
        for md_file in meeting_root.rglob("*.md"):
            lower_parts = {p.lower() for p in md_file.parts}
            if {"@archive", "@trash"} & lower_parts:
                continue
            name = unicodedata.normalize("NFC", md_file.name)
            # Extract YYMMDD from filename
            m = re.search(r"\d{6}", name)
            if not m:
                continue
            date_iso = yymmdd_to_iso(m.group(0))
            if not date_iso:
                continue
            # Apply date filters
            if filter_date:
                if date_iso != yymmdd_to_iso(filter_date):
                    continue
            if date_range:
                if not date_in_range(date_iso, date_range[0], date_range[1]):
                    continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                text = ""
            title = extract_title(md_file.name, domain_emoji)
            attendees = extract_attendees(text)
            meetings.append({
                "file": str(md_file),
                "date": date_iso,
                "title": title,
                "attendees": attendees,
                "domain_emoji": domain_emoji,
            })
    return sorted(meetings, key=lambda m: m["date"])


def main():
    args = sys.argv[1:]
    root = NOTEPLAN_ROOT
    filter_date = None
    date_range = None

    if "--root" in args:
        idx = args.index("--root")
        root = Path(unicodedata.normalize("NFC", os.path.expanduser(args[idx + 1])))
    if "--date" in args:
        idx = args.index("--date")
        filter_date = args[idx + 1]
    if "--date-range" in args:
        idx = args.index("--date-range")
        parts = args[idx + 1].split(":")
        if len(parts) == 2:
            date_range = (parts[0], parts[1])

    meetings = scan_meetings(root, filter_date, date_range)
    print(json.dumps(meetings, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
