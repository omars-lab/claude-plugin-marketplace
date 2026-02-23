#!/usr/bin/env python3
"""ADR (Architecture Decision Record) initializer.

Creates new ADR files from a standard template, auto-numbered sequentially.
No third-party dependencies — uses only the Python standard library.

Usage:
    python adr_init.py "Use PostgreSQL for primary storage" [--dir ./docs/adr]
    python adr_init.py "Adopt event-driven messaging" --dir ./docs/decisions
    python adr_init.py --list --dir ./docs/adr
"""

import argparse
import glob
import os
import re
import sys
from datetime import date

ADR_TEMPLATE = """\
# ADR-{number:04d}: {title}

**Date:** {date}
**Status:** Proposed
**Deciders:** [list who is involved in this decision]

## Context

[Describe the forces at play: technical, political, social, project constraints.
What is the problem or situation we're addressing? Why does it need to be decided now?]

## Decision Drivers

- [driver 1 — e.g. "must support 10k concurrent users"]
- [driver 2 — e.g. "team has no experience with Go"]
- [driver 3]

## Considered Options

1. [Option 1 — name it clearly]
2. [Option 2 — name it clearly]
3. [Option 3 — name it clearly, even if quickly rejected]

## Decision Outcome

**Chosen option:** [Option X], because [justification tied to the decision drivers above].

### Consequences

**Good:**
- [positive consequence 1]
- [positive consequence 2]

**Accepted trade-offs / risks:**
- [negative consequence or risk]
- [another trade-off]

## Pros and Cons of the Options

### Option 1: [Name]

- **Pro:** [argument a]
- **Pro:** [argument b]
- **Con:** [argument c]

### Option 2: [Name]

- **Pro:** [argument a]
- **Con:** [argument b]
- **Con:** [argument c]

### Option 3: [Name]

- **Pro:** [argument a]
- **Con:** [argument b]

## Links

- [Link to relevant diagrams, tickets, or related ADRs]
- [Supersedes: ADR-XXXX (if applicable)]
"""


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def next_adr_number(adr_dir: str) -> int:
    pattern = os.path.join(adr_dir, "ADR-*.md")
    existing = glob.glob(pattern)
    if not existing:
        return 1
    numbers = []
    for path in existing:
        m = re.search(r"ADR-(\d+)", os.path.basename(path))
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def list_adrs(adr_dir: str):
    pattern = os.path.join(adr_dir, "ADR-*.md")
    adrs = sorted(glob.glob(pattern))
    if not adrs:
        print(f"No ADRs found in {adr_dir}")
        return
    print(f"ADRs in {adr_dir}:\n")
    for path in adrs:
        filename = os.path.basename(path)
        title = filename
        status = "unknown"
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# ADR-"):
                        title = line.lstrip("# ").strip()
                    if line.startswith("**Status:**"):
                        status = line.replace("**Status:**", "").strip()
                        break
        except OSError:
            pass
        print(f"  [{status:12s}]  {title}")


def create_adr(title: str, adr_dir: str) -> str:
    os.makedirs(adr_dir, exist_ok=True)
    number = next_adr_number(adr_dir)
    slug = slugify(title)
    filename = f"ADR-{number:04d}-{slug}.md"
    filepath = os.path.join(adr_dir, filename)
    content = ADR_TEMPLATE.format(
        number=number,
        title=title,
        date=date.today().isoformat(),
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Create or list Architecture Decision Records (ADRs)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python adr_init.py "Use PostgreSQL for primary storage"
  python adr_init.py "Adopt event-driven messaging" --dir ./docs/decisions
  python adr_init.py --list
  python adr_init.py --list --dir ./docs/adr
        """,
    )
    parser.add_argument("title", nargs="?", help="Title for the new ADR")
    parser.add_argument(
        "--dir",
        default="./docs/adr",
        help="ADR directory (default: ./docs/adr)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing ADRs in the directory",
    )
    args = parser.parse_args()

    if args.list:
        list_adrs(args.dir)
    elif args.title:
        create_adr(args.title, args.dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
