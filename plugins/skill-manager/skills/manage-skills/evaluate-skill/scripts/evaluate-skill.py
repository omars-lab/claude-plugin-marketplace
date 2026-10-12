#!/usr/bin/env python3
"""
evaluate-skill.py — Deterministic skill quality scanner.

Usage:
    python3 evaluate-skill.py --marketplace /path/to/marketplace [--plugin NAME] [--skill NAME] [--out /tmp/report.json]

Read-only. Safe to re-run. Outputs JSON array of per-skill scorecards.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def score_frontmatter(text: str) -> tuple[int, list[str]]:
    """1 point if YAML frontmatter exists with both name and description."""
    if not text.startswith("---"):
        return 0, ["missing YAML frontmatter (--- block at top of file)"]
    end = text.find("\n---", 3)
    block = text[3:end] if end > 0 else text[3:]
    missing = []
    if "name:" not in block:
        missing.append("frontmatter missing 'name' field")
    if "description:" not in block:
        missing.append("frontmatter missing 'description' field")
    if missing:
        return 0, missing
    return 1, []


def score_scripts_extracted(skill_dir: Path) -> tuple[int, list[str]]:
    """1 point if scripts/ subdir exists and contains at least one file."""
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists() and any(scripts_dir.iterdir()):
        return 1, []
    return 0, ["no scripts/ subdirectory (logic embedded in SKILL.md)"]


def score_task_management(text: str) -> tuple[int, list[str]]:
    """1 point if both TaskCreate and TaskUpdate are mentioned."""
    has_create = "TaskCreate" in text
    has_update = "TaskUpdate" in text
    if has_create and has_update:
        return 1, []
    missing = []
    if not has_create:
        missing.append("missing TaskCreate")
    if not has_update:
        missing.append("missing TaskUpdate")
    return 0, missing


def score_ask_user_question(text: str) -> tuple[int, list[str]]:
    """1 point if AskUserQuestion is mentioned."""
    if "AskUserQuestion" in text:
        return 1, []
    return 0, ["missing AskUserQuestion (skill doesn't ask for user decisions)"]


def score_guardrails(text: str) -> tuple[int, list[str]]:
    """1 point if behavioral guardrails are present."""
    patterns = [
        r"what (this|the) skill does not do",
        r"\bnever\b",
        r"\bavoid\b",
        r"\bdon'?t\b",
        r"\bdo not\b",
        r"guardrail",
        r"not (do|responsible for|meant to)",
    ]
    lower = text.lower()
    for p in patterns:
        if re.search(p, lower):
            return 1, []
    return 0, ["no behavioral guardrails (what this skill avoids / does not do)"]


def score_sensible_defaults(text: str) -> tuple[int, list[str]]:
    """1 point if the skill documents default behaviors near AskUserQuestion."""
    lower = text.lower()
    has_default = "default" in lower or "by default" in lower
    has_confirm = "confirm" in lower or "AskUserQuestion" in text
    if has_default and has_confirm:
        return 1, []
    return 0, ["no sensible defaults documented (pair 'default: ...' with AskUserQuestion confirmations)"]


def score_success_criteria(text: str) -> tuple[int, list[str]]:
    """1 point if a - [ ] checklist is present."""
    if re.search(r"^- \[ \]", text, re.MULTILINE):
        return 1, []
    return 0, ["no success criteria checklist (add '- [ ]' items)"]


def score_workflow_phases(text: str) -> tuple[int, list[str]]:
    """1 point if 2+ numbered phases or steps exist."""
    count = len(re.findall(r"^###\s+(Phase|Step)\s+\d+", text, re.MULTILINE))
    if count >= 2:
        return 1, []
    if count == 1:
        return 0, [f"only {count} workflow phase (need ≥2 for full score)"]
    return 0, ["no numbered workflow phases (### Phase N: or ### Step N:)"]


def score_size(text: str) -> tuple[int, list[str]]:
    """1 point if SKILL.md is ≤500 lines."""
    lines = len(text.splitlines())
    if lines <= 500:
        return 1, []
    return 0, [f"SKILL.md is {lines} lines (>500 — consider splitting into focused sub-skills)"]


# ---------------------------------------------------------------------------
# Evaluate one skill
# ---------------------------------------------------------------------------

def evaluate_skill(skill_dir: Path, plugin_name: str) -> dict:
    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    text = _read(skill_md)
    line_count = len(text.splitlines())

    dimension_fns = [
        ("frontmatter", lambda: score_frontmatter(text)),
        ("scripts_extracted", lambda: score_scripts_extracted(skill_dir)),
        ("task_management", lambda: score_task_management(text)),
        ("ask_user_question", lambda: score_ask_user_question(text)),
        ("guardrails", lambda: score_guardrails(text)),
        ("sensible_defaults", lambda: score_sensible_defaults(text)),
        ("success_criteria", lambda: score_success_criteria(text)),
        ("workflow_phases", lambda: score_workflow_phases(text)),
        ("size_ok", lambda: score_size(text)),
    ]

    scores = {}
    flags = []
    for dim_name, fn in dimension_fns:
        score, dim_flags = fn()
        scores[dim_name] = score
        flags.extend(dim_flags)

    total = sum(scores.values())

    return {
        "plugin": plugin_name,
        "skill": skill_name,
        "line_count": line_count,
        "total": total,
        "max": len(dimension_fns),
        "scores": scores,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate Claude skill quality")
    parser.add_argument("--marketplace", required=True, help="Path to marketplace root")
    parser.add_argument("--plugin", help="Limit scan to this plugin")
    parser.add_argument("--skill", help="Limit scan to this skill (requires --plugin)")
    parser.add_argument("--out", help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    marketplace_dir = Path(args.marketplace).resolve()
    plugins_dir = marketplace_dir / "plugins"

    results = []

    if not plugins_dir.exists():
        print(f"ERROR: {plugins_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    plugin_dirs = sorted(plugins_dir.iterdir())
    if args.plugin:
        plugin_dirs = [p for p in plugin_dirs if p.name == args.plugin]
        if not plugin_dirs:
            print(f"ERROR: plugin '{args.plugin}' not found in {plugins_dir}", file=sys.stderr)
            sys.exit(1)

    for plugin_dir in plugin_dirs:
        if not plugin_dir.is_dir():
            continue
        skills_dir = plugin_dir / "skills"
        if not skills_dir.exists():
            continue

        skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir())
        if args.skill:
            skill_dirs = [d for d in skill_dirs if d.name == args.skill]
            if not skill_dirs:
                print(f"ERROR: skill '{args.skill}' not found in {skills_dir}", file=sys.stderr)
                sys.exit(1)

        for skill_dir in skill_dirs:
            if not (skill_dir / "SKILL.md").exists():
                continue
            results.append(evaluate_skill(skill_dir, plugin_dir.name))

    # Sort by total score ascending (worst first)
    results.sort(key=lambda r: (r["total"], r["plugin"], r["skill"]))

    output = json.dumps(results, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        total_skills = len(results)
        avg = sum(r["total"] for r in results) / total_skills if total_skills else 0
        print(
            f"Evaluated {total_skills} skills. Avg score: {avg:.1f}/{results[0]['max'] if results else 9}. "
            f"Report: {args.out}",
            file=sys.stderr,
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
