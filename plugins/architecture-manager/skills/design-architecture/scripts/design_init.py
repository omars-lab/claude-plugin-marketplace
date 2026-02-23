#!/usr/bin/env python3
"""Architecture Design Document initializer.

Scaffolds a DESIGN-NNNN-<title>.md file for evaluating architecture options.
No third-party dependencies — uses only the Python standard library.

Usage:
    python design_init.py "Event-driven vs request-response for notifications"
    python design_init.py "Cache layer for product search" --type feature --dir ./docs/architecture/design
    python design_init.py --list --dir ./docs/architecture/design
"""

import argparse
import glob
import os
import re
import sys
from datetime import date

DESIGN_TEMPLATE = """\
# Architecture Design: {title}

**Date:** {date}
**Status:** Draft
**Author:** [your name]
**Type:** {design_type}

## Problem Statement

[What problem are we solving? What is the current situation and why is it inadequate?
Be specific about the pain point, not the solution.]

## Requirements

### Functional Requirements
- [requirement 1]
- [requirement 2]

### Non-Functional Requirements
- [performance: e.g. "must handle 10k req/s at p99 < 200ms"]
- [reliability: e.g. "99.9% uptime"]
- [scalability: e.g. "must scale to 1M users without rearchitecting"]

## Constraints

- [constraint 1 — non-negotiable boundaries, e.g. "must use existing Postgres instance"]
- [constraint 2 — e.g. "team has no Kubernetes experience"]
- [constraint 3 — e.g. "must stay within $X/month infrastructure budget"]

## Evaluation Criteria

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| Simplicity / operational burden | — | [why this matters for this decision] |
| Scalability | — | [why this matters] |
| Cost (build + run) | — | [why this matters] |
| Team capability fit | — | [why this matters] |
| Risk / reversibility | — | [why this matters] |

---

## Option 1: [Name — describe the distinguishing characteristic, not just "Option 1"]

**Summary:** [One sentence describing this approach]

### How It Works

[2–4 sentences describing the approach. Reference a diagram if one exists.]

See: [diagram link, or note "diagram TBD"]

### Pros

- [genuine strength tied to requirements]
- [another strength]

### Cons

- [honest weakness]
- [another weakness]

### Risks

- [risk 1 — what could go wrong, how likely, how impactful]
- [risk 2]

### Cost Estimate

- **Build effort:** [rough weeks/months — use a range, not false precision]
- **Infra cost:** [$/month estimate if applicable, or "no additional cost"]
- **Ongoing maintenance:** [Low / Medium / High]

### Fit Assessment

[1–2 sentences: does this option satisfy the must-have requirements? What's the main trade-off?]

---

## Option 2: [Name]

**Summary:** [One sentence]

### How It Works

[Description]

See: [diagram link]

### Pros

- [pro 1]
- [pro 2]

### Cons

- [con 1]
- [con 2]

### Risks

- [risk 1]

### Cost Estimate

- **Build effort:** [range]
- **Infra cost:** [estimate]
- **Ongoing maintenance:** [Low / Medium / High]

### Fit Assessment

[1–2 sentences]

---

## Option 3: [Name — remove this section if only two options are needed]

**Summary:** [One sentence]

### How It Works

[Description]

### Pros

- [pro 1]

### Cons

- [con 1]

### Risks

- [risk 1]

### Cost Estimate

- **Build effort:** [range]
- **Infra cost:** [estimate]
- **Ongoing maintenance:** [Low / Medium / High]

### Fit Assessment

[1–2 sentences]

---

## Summary Comparison

| Criterion              | Option 1: [Name] | Option 2: [Name] | Option 3: [Name] |
|------------------------|------------------|------------------|------------------|
| Simplicity             | ⚠️ Med           | ✅ High          | ❌ Low           |
| Scalability            | ✅ High          | ⚠️ Med           | ✅ High          |
| Cost (build)           | ✅ Low           | ⚠️ Med           | ❌ High          |
| Cost (run)             | ✅ Low           | ⚠️ Med           | ⚠️ Med           |
| Team capability fit    | ✅ High          | ⚠️ Med           | ❌ Low           |
| Risk / reversibility   | ✅ Low           | ⚠️ Med           | ❌ High          |

*Legend: ✅ Favorable  ⚠️ Neutral / trade-off  ❌ Unfavorable*

---

## Recommendation

**Recommended option:** [Option X: Name]

**Rationale:** [2–3 sentences. Tie the recommendation explicitly to the highest-weight
evaluation criteria. Be clear about which trade-offs you're accepting.]

**Conditions for revisiting:** [What would make you reconsider? e.g. "If user growth
exceeds 100k/month within 6 months, the scalability trade-off in Option 1 should be
re-evaluated against Option 2."]

**Open questions before committing:**
- [ ] [Question 1 — something that needs resolution]
- [ ] [Question 2]

## Next Steps

- [ ] Get stakeholder sign-off on this document
- [ ] Create ADR for the chosen option (`/architecture-manager:capture-architecture`)
- [ ] Generate diagrams for the chosen option (`/architecture-manager:generate-diagram`)
- [ ] Update architecture overview if this is a system-level decision
"""


def slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def next_design_number(design_dir: str) -> int:
    pattern = os.path.join(design_dir, "DESIGN-*.md")
    existing = glob.glob(pattern)
    if not existing:
        return 1
    numbers = []
    for path in existing:
        m = re.search(r"DESIGN-(\d+)", os.path.basename(path))
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def list_designs(design_dir: str):
    pattern = os.path.join(design_dir, "DESIGN-*.md")
    designs = sorted(glob.glob(pattern))
    if not designs:
        print(f"No design documents found in {design_dir}")
        return
    print(f"Design documents in {design_dir}:\n")
    for path in designs:
        filename = os.path.basename(path)
        title = filename
        status = "unknown"
        design_type = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# Architecture Design:"):
                        title = line.replace("# Architecture Design:", "").strip()
                    if line.startswith("**Status:**"):
                        status = line.replace("**Status:**", "").strip()
                    if line.startswith("**Type:**"):
                        design_type = line.replace("**Type:**", "").strip()
                        break
        except OSError:
            pass
        type_tag = f" [{design_type}]" if design_type else ""
        print(f"  [{status:8s}]{type_tag}  {title}")


def create_design(title: str, design_dir: str, design_type: str) -> str:
    os.makedirs(design_dir, exist_ok=True)
    number = next_design_number(design_dir)
    slug = slugify(title)
    filename = f"DESIGN-{number:04d}-{slug}.md"
    filepath = os.path.join(design_dir, filename)
    content = DESIGN_TEMPLATE.format(
        title=title,
        date=date.today().isoformat(),
        design_type=design_type,
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold an Architecture Design document for option evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python design_init.py "Event-driven vs request-response for notifications"
  python design_init.py "Database selection for user data" --type feature
  python design_init.py "Caching strategy for product search" --dir ./docs/architecture/design
  python design_init.py --list
        """,
    )
    parser.add_argument("title", nargs="?", help="Title / decision being evaluated")
    parser.add_argument(
        "--dir",
        default="./docs/architecture/design",
        help="Output directory (default: ./docs/architecture/design)",
    )
    parser.add_argument(
        "--type",
        choices=["system", "feature"],
        default="system",
        help="Design type: system (greenfield/high-level) or feature (within existing system). Default: system",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing design documents",
    )
    args = parser.parse_args()

    if args.list:
        list_designs(args.dir)
    elif args.title:
        create_design(args.title, args.dir, args.type)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
