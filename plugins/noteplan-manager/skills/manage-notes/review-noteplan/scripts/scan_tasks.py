#!/usr/bin/env python3
"""
scan_tasks.py
Scan NotePlan notes and calendar for completed/scheduled tasks by year.

Usage:
  python3 scan_tasks.py --year 2026 --domain work --notes-dir /path/to/Notes
  python3 scan_tasks.py --year 2026 --domain all --output results.json

Outputs JSON with tasks categorized by workstream.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime


# ── Work/Personal Classification ──────────────────────────────────────────────

PERSONAL_PATTERNS = re.compile(
    r"personal|home|family|health|doctor|medical|finance|bank|grocery|"
    r"shopping|vacation|travel|hobby|exercise|gym|friend|weekend|birthday|"
    r"anniversary|house|car|insurance|tax|parking|bill|garden|lawn|yard|"
    r"cleaning|laundry|cooking|meal|dentist|appointment|vet|pet|repair|"
    r"maintenance|utilities|mortgage|rent|furniture|chores|kids|children|"
    r"school|daycare|relatives|parents|siblings|spouse|partner|wedding|"
    r"party|celebration|holiday|christmas|thanksgiving|gift|restaurant|"
    r"dinner|lunch|breakfast",
    re.IGNORECASE,
)

WORK_TOOL_PATTERNS = re.compile(
    r"asana|salesforce|jira|confluence|slack|teams|zoom|webex|github|"
    r"gitlab|jenkins|docker|kubernetes|terraform|datadog|splunk|grafana|"
    r"pagerduty|servicenow|snow|now platform",
    re.IGNORECASE,
)

WORK_LANGUAGE_PATTERNS = re.compile(
    r"schedule|coordinate|follow up|check in|sync up|catch up|review|"
    r"approve|sign off|escalate|prioritize|deliverable|stakeholder|"
    r"roadmap|sprint|milestone|deployment|release|onboarding|standup",
    re.IGNORECASE,
)

WORK_TECH_PATTERNS = re.compile(
    r"diagram|architecture|component|system|model|process|workflow|"
    r"requirement|specification|api|database|deployment|configuration|"
    r"monitoring|logging|metrics|dashboard|analytics|security|compliance|"
    r"documentation|runbook|training|knowledge|budget|roi|kpi|strategy|"
    r"customer|client|vendor|contractor|consultant",
    re.IGNORECASE,
)

# Workstream classification patterns (adapt to current employer context)
WORKSTREAM_PATTERNS = {
    "Development": re.compile(r"develop|code|implement|build|script|automation|api|debug|test|deploy|pr\b|pull request", re.IGNORECASE),
    "Deep Dives": re.compile(r"deep dive|research|investigate|analysis|explore|spike|poc", re.IGNORECASE),
    "Documenting": re.compile(r"document|wiki|runbook|guide|write up|kb article|knowledge base", re.IGNORECASE),
    "Impact": re.compile(r"impact|goal|objective|kpi|metric|target|review performance|promo|promotion", re.IGNORECASE),
    "Onboarding": re.compile(r"onboard|new hire|orient|ramp|set up access|access request", re.IGNORECASE),
    "Training": re.compile(r"train|learn|course|certif|workshop|study|reading", re.IGNORECASE),
    "Travel": re.compile(r"travel|flight|hotel|trip|conference|offsite", re.IGNORECASE),
    "Workspace": re.compile(r"workspace|setup|configure|tooling|laptop|equipment|environment", re.IGNORECASE),
    "Meetings": re.compile(r"meeting|sync|standup|1:1|one.on.one|review|retro|planning", re.IGNORECASE),
)


def is_work_task(content: str) -> bool:
    """Return True if content looks like a work task."""
    if PERSONAL_PATTERNS.search(content):
        return False
    if WORK_TOOL_PATTERNS.search(content):
        return True
    if WORK_LANGUAGE_PATTERNS.search(content):
        return True
    if WORK_TECH_PATTERNS.search(content):
        return True
    return False


def categorize_workstream(content: str) -> str:
    """Classify content into a workstream name."""
    for name, pattern in WORKSTREAM_PATTERNS.items():
        if pattern.search(content):
            return name
    return "Other"


# ── Task Extraction ────────────────────────────────────────────────────────────

DONE_PATTERN = re.compile(r"@done\((\d{4}-\d{2}-\d{2})")
SCHEDULED_PATTERN = re.compile(r"@scheduled\((\d{4}-\d{2}-\d{2})")
TASK_LINE = re.compile(r"^\s*[\*\-]\s+\[.?\]")


def extract_tasks_from_file(filepath: Path, year: int, domain: str) -> list[dict]:
    """Extract tasks matching year and domain from a single file."""
    tasks = []
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return tasks

    lines = text.splitlines()
    year_str = str(year)

    for i, line in enumerate(lines):
        # Look for @done or @scheduled tags matching the year
        done_match = DONE_PATTERN.search(line)
        sched_match = SCHEDULED_PATTERN.search(line)

        tag_date = None
        tag_type = None
        if done_match and done_match.group(1).startswith(year_str):
            tag_date = done_match.group(1)
            tag_type = "done"
        elif sched_match and sched_match.group(1).startswith(year_str):
            tag_date = sched_match.group(1)
            tag_type = "scheduled"
        else:
            continue

        # Domain filter
        task_is_work = is_work_task(line)
        if domain == "work" and not task_is_work:
            continue
        if domain == "personal" and task_is_work:
            continue

        # Get heading context (last heading seen above this line)
        heading = ""
        for prev_line in reversed(lines[:i]):
            if prev_line.startswith("#"):
                heading = prev_line.lstrip("#").strip()
                break

        workstream = categorize_workstream(line) if task_is_work else "Personal"

        tasks.append({
            "file": str(filepath),
            "line": i + 1,
            "task": line.strip(),
            "heading": heading,
            "workstream": workstream,
            "date": tag_date,
            "type": tag_type,
            "domain": "work" if task_is_work else "personal",
        })

    return tasks


def scan_directory(directory: Path, year: int, domain: str, pattern: str = "*.md") -> list[dict]:
    """Recursively scan a directory for tasks."""
    all_tasks = []
    if not directory.exists():
        return all_tasks
    for filepath in directory.rglob(pattern):
        if filepath.is_file():
            all_tasks.extend(extract_tasks_from_file(filepath, year, domain))
    return all_tasks


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scan NotePlan for completed/scheduled tasks")
    parser.add_argument("--notes-dir", required=True, help="Path to NotePlan Notes directory")
    parser.add_argument("--calendar-dir", help="Path to NotePlan Calendar directory")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Year to scan (default: current)")
    parser.add_argument("--domain", choices=["work", "personal", "all"], default="all", help="Filter by domain")
    parser.add_argument("--output", help="Output JSON path (default: stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Show file list without reading content")
    args = parser.parse_args()

    notes_dir = Path(args.notes_dir)
    calendar_dir = Path(args.calendar_dir) if args.calendar_dir else None

    if args.dry_run:
        count = sum(1 for _ in notes_dir.rglob("*.md")) if notes_dir.exists() else 0
        cal_count = sum(1 for _ in calendar_dir.rglob("*.txt")) if calendar_dir and calendar_dir.exists() else 0
        print(f"Notes .md files: {count}")
        print(f"Calendar .txt files: {cal_count}")
        return

    print(f"Scanning {args.year} tasks (domain={args.domain})...", file=sys.stderr)

    all_tasks = scan_directory(notes_dir, args.year, args.domain, "*.md")
    if calendar_dir:
        all_tasks.extend(scan_directory(calendar_dir, args.year, args.domain, "*.txt"))

    # Aggregate by workstream
    by_workstream: dict[str, int] = {}
    for t in all_tasks:
        ws = t["workstream"]
        by_workstream[ws] = by_workstream.get(ws, 0) + 1

    # Unique files
    unique_files = len({t["file"] for t in all_tasks})

    result = {
        "year": args.year,
        "domain": args.domain,
        "summary": {
            "total_files": unique_files,
            "total_tasks": len(all_tasks),
            "by_workstream": by_workstream,
        },
        "tasks": all_tasks,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"✓ Wrote {len(all_tasks)} tasks to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
