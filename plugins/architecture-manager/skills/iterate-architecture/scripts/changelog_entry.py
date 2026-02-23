#!/usr/bin/env python3
"""Architecture change log entry appender.

Appends a structured change log entry to docs/architecture/CHANGELOG.md.
Keeps a chronological record of architecture changes with their drivers.
No third-party dependencies — uses only the Python standard library.

Usage:
    python changelog_entry.py "Migrated auth to JWT tokens" \\
        --type breaking \\
        --driver "session storage didn't scale to horizontal deployment" \\
        --artifacts "docs/architecture/auth_flow.puml,docs/adr/ADR-0003-jwt-auth.md"

    python changelog_entry.py --list
"""

import argparse
import os
import sys
from datetime import date

CHANGELOG_HEADER = """\
# Architecture Change Log

A chronological record of architecture changes — what changed, what drove it,
and what the previous state was. New entries are appended at the bottom.

Change types:
- **breaking** — changes an interface or contract; consumers must update
- **structural** — significant internal reorganization; no external interface change
- **refinement** — improvement or optimization within existing structure
- **constraint** — change forced by a new external constraint (regulatory, cost, org)

---

"""

ENTRY_TEMPLATE = """
## {date} — {title}

**Type:** {change_type}
**Driver:** {driver}
**Affected artifacts:**
{artifacts_list}

### What Changed

[Describe what was changed in the architecture — be specific about components,
interfaces, data flows, or decisions that are now different]

### Why

[What drove this change? Reference the feedback, requirement change, or observation
that made this change necessary. Link to ADRs or design docs if applicable]

### What Was There Before

[Describe the previous state — what are you moving away from?
This is the most important section for future readers]

### Trade-offs Accepted

[What did you give up or take on by making this change?
Be honest — if this change introduces new operational complexity, say so]

### References

{references_list}

---
"""


def format_list(items_str: str, placeholder: str) -> str:
    if not items_str.strip():
        return f"- {placeholder}"
    items = [item.strip() for item in items_str.split(",") if item.strip()]
    return "\n".join(f"- {item}" for item in items)


def list_entries(changelog_path: str):
    if not os.path.exists(changelog_path):
        print(f"No changelog found at {changelog_path}")
        return
    with open(changelog_path, "r", encoding="utf-8") as f:
        content = f.read()
    entries = []
    for line in content.splitlines():
        if line.startswith("## ") and " — " in line:
            entries.append(line.lstrip("# ").strip())
    if not entries:
        print(f"No entries found in {changelog_path}")
        return
    print(f"Change log entries in {changelog_path}:\n")
    for entry in entries:
        print(f"  {entry}")


def append_entry(
    title: str,
    changelog_path: str,
    change_type: str,
    driver: str,
    artifacts: str,
    references: str,
) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(changelog_path)), exist_ok=True)

    if not os.path.exists(changelog_path):
        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write(CHANGELOG_HEADER)

    entry = ENTRY_TEMPLATE.format(
        date=date.today().isoformat(),
        title=title,
        change_type=change_type,
        driver=driver if driver else "[describe what drove this change]",
        artifacts_list=format_list(artifacts, "[list affected diagrams, ADRs, docs]"),
        references_list=format_list(references, "[link to ADR, design doc, or ticket]"),
    )

    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"Appended entry to: {changelog_path}")
    return changelog_path


def main():
    parser = argparse.ArgumentParser(
        description="Append a structured entry to the architecture change log",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python changelog_entry.py "Migrated auth to JWT tokens" --type breaking --driver "session storage didn't scale"
  python changelog_entry.py "Split user service into profile + auth" --type structural
  python changelog_entry.py "Optimized query plan for search" --type refinement
  python changelog_entry.py --list
        """,
    )
    parser.add_argument("title", nargs="?", help="Short description of the change")
    parser.add_argument(
        "--changelog",
        default="./docs/architecture/CHANGELOG.md",
        help="Path to the changelog file (default: ./docs/architecture/CHANGELOG.md)",
    )
    parser.add_argument(
        "--type",
        choices=["breaking", "structural", "refinement", "constraint"],
        default="refinement",
        help="Change type (default: refinement)",
    )
    parser.add_argument(
        "--driver",
        default="",
        help="What drove this change (e.g. 'scaling requirements', 'security review feedback')",
    )
    parser.add_argument(
        "--artifacts",
        default="",
        help="Comma-separated list of affected artifacts (diagrams, ADRs, docs)",
    )
    parser.add_argument(
        "--references",
        default="",
        help="Comma-separated references (ADR numbers, tickets, design doc links)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing changelog entries",
    )
    args = parser.parse_args()

    if args.list:
        list_entries(args.changelog)
    elif args.title:
        append_entry(
            args.title,
            args.changelog,
            args.type,
            args.driver,
            args.artifacts,
            args.references,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
