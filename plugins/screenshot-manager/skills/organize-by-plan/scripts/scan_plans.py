#!/usr/bin/env python3
"""Build an index of active NotePlan plans for screenshot matching.

Usage:
    python3 scan_plans.py [--root PATH] [--since-days N] [--date-range YYMMDD:YYMMDD]

Options:
    --root PATH           NotePlan root (default: auto-detected)
    --since-days N        Include plans with mtime within last N days (default: 90)
    --date-range A:B      Also include plans whose started date falls in YYMMDD:YYMMDD window

Output:
    JSON array: [{file, title, subdir_name, domain_emoji, workstream_emoji,
                  description, status, started, mtime, headings, body_snippet}]
"""
import json
import sys
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta

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

PLAN_ROOTS = [
    ("🏢", "Notes/🏢 ServiceNow/📆 Plans"),
    ("🏡", "Notes/🏡 Personal/🏡📆 Plans/Present"),
    ("☕️", "Notes/☕️ NaqshCoffee/📆 Plans"),
    ("👥", "Notes/👥 EarlBear/📆 Plans"),
]

PLACEHOLDER_RE = re.compile(r"\b(a[sd][sd]f)(\s+\d+)?$", re.IGNORECASE)
SKIP_PATH_PARTS = {"@archive", "@trash"}
SKIP_PATH_CONTAINS = {"past", "future"}


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end]
    result = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def extract_headings(text: str) -> list:
    return [
        line.lstrip("#").strip()
        for line in text.splitlines()
        if re.match(r"^#{1,2}\s", line)
    ][:10]


def normalize_started(raw: str) -> str:
    """Normalize started value to YYYY-MM-DD."""
    raw = raw.strip()
    if re.match(r"^\d{6}$", raw):
        yy, mm, dd = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
        return f"{2000+yy:04d}-{mm:02d}-{dd:02d}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    return ""


def extract_title(filename: str) -> str:
    """Extract human title from plan filename (strip domain-emoji, date, workstream-emoji)."""
    name = filename[:-3] if filename.endswith(".md") else filename
    name = unicodedata.normalize("NFC", name)
    # Find 6-digit YYMMDD anywhere in name and take everything after
    m = re.search(r"\d{6}(.*)$", name)
    if not m:
        return name.strip()
    rest = m.group(1)
    # Strip leading workstream emoji (non-word, non-space clusters) and whitespace
    rest = re.sub(r"^[^\w\s]+", "", rest).strip()
    return rest


def is_in_active_window(started: str, date_range: tuple) -> bool:
    if not started or not date_range:
        return False
    try:
        dt = datetime.strptime(started, "%Y-%m-%d")
        lo_raw, hi_raw = date_range
        lo = datetime.strptime(f"20{lo_raw[:2]}-{lo_raw[2:4]}-{lo_raw[4:6]}", "%Y-%m-%d")
        hi = datetime.strptime(f"20{hi_raw[:2]}-{hi_raw[2:4]}-{hi_raw[4:6]}", "%Y-%m-%d")
        return lo <= dt <= hi
    except ValueError:
        return False


def is_active(mtime: datetime, status: str, started: str, since_days: int, date_range) -> bool:
    if datetime.now() - mtime <= timedelta(days=since_days):
        return True
    if "🟡" in status:
        return True
    if date_range and is_in_active_window(started, date_range):
        return True
    return False


def scan_plans(root: Path, since_days: int, date_range) -> list:
    plans = []
    for domain_emoji, rel_path in PLAN_ROOTS:
        plan_root = root / rel_path
        if not plan_root.exists():
            continue
        for md_file in plan_root.rglob("*.md"):
            # Skip archive / trash paths
            lower_parts = {p.lower() for p in md_file.parts}
            if lower_parts & SKIP_PATH_PARTS:
                continue
            if any(kw in p.lower() for p in md_file.parts for kw in SKIP_PATH_CONTAINS):
                continue
            stem = unicodedata.normalize("NFC", md_file.stem)
            if PLACEHOLDER_RE.search(stem):
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            fm = parse_frontmatter(text)
            # Extract body (after frontmatter)
            body = text
            if text.startswith("---"):
                end = text.find("\n---", 3)
                if end != -1:
                    body = text[end + 4:]
            if len(body.strip()) < 200:
                continue
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            raw_started = fm.get("started", "") or re.search(r"\d{6}", md_file.name)
            if hasattr(raw_started, "group"):
                raw_started = raw_started.group(0)
            started = normalize_started(str(raw_started or ""))
            status = fm.get("status", "")
            if not is_active(mtime, status, started, since_days, date_range):
                continue
            title = extract_title(md_file.name)
            plans.append({
                "file": str(md_file),
                "title": title,
                "subdir_name": f"{domain_emoji} {title}",
                "domain_emoji": domain_emoji,
                "description": fm.get("description", ""),
                "status": status,
                "started": started,
                "mtime": mtime.strftime("%Y-%m-%d"),
                "headings": extract_headings(body),
                "body_snippet": body.strip()[:500],
            })
    return plans


def main():
    args = sys.argv[1:]
    root = NOTEPLAN_ROOT
    since_days = 90
    date_range = None

    if "--root" in args:
        idx = args.index("--root")
        root = Path(unicodedata.normalize("NFC", os.path.expanduser(args[idx + 1])))
    if "--since-days" in args:
        idx = args.index("--since-days")
        since_days = int(args[idx + 1])
    if "--date-range" in args:
        idx = args.index("--date-range")
        parts = args[idx + 1].split(":")
        if len(parts) == 2:
            date_range = (parts[0], parts[1])

    plans = scan_plans(root, since_days, date_range)
    print(json.dumps(plans, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
