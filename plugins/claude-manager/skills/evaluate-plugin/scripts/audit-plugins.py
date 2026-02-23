#!/usr/bin/env python3
"""
audit-plugins.py — Deterministic plugin compliance scanner.

Usage:
    python3 audit-plugins.py --marketplace /path/to/marketplace [--out /tmp/report.json]

Read-only. Safe to re-run. Outputs JSON compliance report.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _json_load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _git_commit_exists(commit: str, repo_root: Path) -> bool:
    if not commit:
        return False
    r = subprocess.run(
        ["git", "cat-file", "-e", commit],
        cwd=str(repo_root),
        capture_output=True,
    )
    return r.returncode == 0


def _head_commit(repo_root: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def _count_phases(skill_text: str) -> int:
    return len(re.findall(r"^###\s+(Phase|Step)\s+\d+", skill_text, re.MULTILINE))


def _is_file_modifying(skill_text: str) -> bool:
    keywords = ["write", "edit", "create", "delete", "modify", "move", "rename", "git mv"]
    lower = skill_text.lower()
    return any(k in lower for k in keywords)


# ---------------------------------------------------------------------------
# Check functions — each returns a list of issue dicts
# ---------------------------------------------------------------------------

def check_version_tracking(plugin_dir: Path, marketplace_json: dict, repo_root: Path) -> list:
    issues = []
    plugin_name = plugin_dir.name
    tracking_path = plugin_dir / ".claude-plugin" / "version-tracking.json"

    # 1. Missing version-tracking.json
    if not tracking_path.exists():
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "version_tracking",
            "severity": "ERROR",
            "message": "Missing .claude-plugin/version-tracking.json",
            "fix": "Run `make version-init` or create the file with { \"versionCommit\": \"<HEAD>\" }",
        })
        return issues  # No point checking contents if missing

    tracking = _json_load(tracking_path)
    commit = tracking.get("versionCommit", "")

    # 2. Empty versionCommit
    if not commit:
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "version_tracking",
            "severity": "ERROR",
            "message": "version-tracking.json has empty versionCommit",
            "fix": "Set versionCommit to current HEAD: `git rev-parse HEAD`",
        })
    # 3. Invalid commit
    elif not _git_commit_exists(commit, repo_root):
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "version_tracking",
            "severity": "ERROR",
            "message": f"versionCommit '{commit[:8]}' does not exist in git history",
            "fix": "Update versionCommit to a valid commit hash",
        })

    # 4. Not registered in marketplace.json
    registered_names = {p["name"] for p in marketplace_json.get("plugins", [])}
    if plugin_name not in registered_names:
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "version_tracking",
            "severity": "ERROR",
            "message": "Plugin not registered in .claude-plugin/marketplace.json",
            "fix": "Add plugin entry to marketplace.json",
        })

    return issues


def check_shell_scripts(marketplace_dir: Path) -> list:
    issues = []
    scripts_dir = marketplace_dir / "scripts"
    if not scripts_dir.exists():
        return issues

    for sh_file in scripts_dir.glob("*.sh"):
        content = _read(sh_file)
        # 5. pipefail + grep pattern without || true
        if "set -e" in content or "pipefail" in content:
            # Find grep in pipes without || true guard
            lines_with_grep_pipe = [
                ln for ln in content.splitlines()
                if re.search(r"\|\s*grep\b", ln) and "|| true" not in ln and not ln.strip().startswith("#")
            ]
            for ln in lines_with_grep_pipe:
                issues.append({
                    "plugin": "_marketplace_scripts",
                    "skill": None,
                    "category": "version_tracking",
                    "severity": "WARNING",
                    "message": f"{sh_file.name}: grep in pipeline without '|| true' (will crash on zero matches under pipefail)",
                    "fix": "Wrap as: { grep 'pattern' || true; }",
                })
                break  # one warning per file

    return issues


def check_skill_naming(plugin_dir: Path) -> list:
    issues = []
    plugin_name = plugin_dir.name
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return issues

    # Noun-first patterns: starts with a noun-like word before a verb
    noun_first_pattern = re.compile(
        r"^(skill|plugin|note|plan|file|folder|config|template|report|script|knowledge|role|version)-"
    )

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        if noun_first_pattern.match(skill_name):
            issues.append({
                "plugin": plugin_name,
                "skill": skill_name,
                "category": "skill_naming",
                "severity": "WARNING",
                "message": f"Skill '{skill_name}' appears noun-first; prefer verb-first (e.g., 'create-skill')",
                "fix": "Rename to verb-first: git mv skills/<old> skills/<new>",
            })
        if not re.match(r"^[a-z][a-z0-9-]+$", skill_name):
            issues.append({
                "plugin": plugin_name,
                "skill": skill_name,
                "category": "skill_naming",
                "severity": "WARNING",
                "message": f"Skill name '{skill_name}' is not lowercase kebab-case",
                "fix": "Rename to lowercase kebab-case",
            })

    return issues


def check_mandatory_patterns(plugin_dir: Path) -> list:
    issues = []
    plugin_name = plugin_dir.name
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return issues

    skill_dirs = [d for d in sorted(skills_dir.iterdir()) if d.is_dir()]

    # Check for introduce skill
    introduce_exists = (skills_dir / "introduce" / "SKILL.md").exists()
    if not introduce_exists:
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "mandatory_patterns",
            "severity": "ERROR",
            "message": "Plugin has no 'introduce' skill",
            "fix": "Create skills/introduce/SKILL.md explaining plugin capabilities",
        })

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        skill_name = skill_dir.name
        text = _read(skill_md)

        # YAML frontmatter
        if not text.startswith("---"):
            issues.append({
                "plugin": plugin_name,
                "skill": skill_name,
                "category": "mandatory_patterns",
                "severity": "WARNING",
                "message": "SKILL.md missing YAML frontmatter (--- block at top)",
                "fix": "Add --- frontmatter with 'name' and 'description' fields",
            })
        else:
            fm_end = text.find("\n---", 3)
            fm_block = text[3:fm_end] if fm_end > 0 else ""
            if "name:" not in fm_block:
                issues.append({
                    "plugin": plugin_name,
                    "skill": skill_name,
                    "category": "mandatory_patterns",
                    "severity": "WARNING",
                    "message": "YAML frontmatter missing 'name' field",
                    "fix": "Add 'name: <skill-name>' to frontmatter",
                })
            if "description:" not in fm_block:
                issues.append({
                    "plugin": plugin_name,
                    "skill": skill_name,
                    "category": "mandatory_patterns",
                    "severity": "WARNING",
                    "message": "YAML frontmatter missing 'description' field",
                    "fix": "Add 'description: ...' to frontmatter",
                })

        # Task management
        has_tasks = "TaskCreate" in text and "TaskUpdate" in text
        phases = _count_phases(text)
        if not has_tasks:
            severity = "ERROR" if phases >= 3 else "WARNING"
            issues.append({
                "plugin": plugin_name,
                "skill": skill_name,
                "category": "mandatory_patterns",
                "severity": severity,
                "message": f"Skill has {phases} phase(s) but no TaskCreate/TaskUpdate ({severity})",
                "fix": "Add '## Task Management (MANDATORY)' section with TaskCreate/TaskUpdate calls",
            })

        # AskUserQuestion
        if "AskUserQuestion" not in text:
            is_modifying = _is_file_modifying(text)
            severity = "ERROR" if is_modifying else "WARNING"
            issues.append({
                "plugin": plugin_name,
                "skill": skill_name,
                "category": "mandatory_patterns",
                "severity": severity,
                "message": f"Skill missing AskUserQuestion ({'file-modifying' if is_modifying else 'read-only'})",
                "fix": "Add AskUserQuestion for decisions and confirmations",
            })

        # Git safety (only for file-modifying skills)
        if _is_file_modifying(text):
            has_git_safety = any(kw in text for kw in ["git status", "CHECKPOINT", "Git Safety", "git diff"])
            if not has_git_safety:
                issues.append({
                    "plugin": plugin_name,
                    "skill": skill_name,
                    "category": "mandatory_patterns",
                    "severity": "ERROR",
                    "message": "File-modifying skill missing git safety (git status, checkpoint, git diff validation)",
                    "fix": "Add git safety pattern: check status, record CHECKPOINT_COMMIT, validate diff",
                })

    return issues


def check_readme_bloat(plugin_dir: Path) -> list:
    issues = []
    plugin_name = plugin_dir.name
    readme = plugin_dir / "README.md"
    if not readme.exists():
        return issues

    lines = _read(readme).splitlines()
    line_count = len(lines)
    if line_count > 50:
        has_introduce = (plugin_dir / "skills" / "introduce" / "SKILL.md").exists()
        severity = "WARNING" if has_introduce else "INFO"
        issues.append({
            "plugin": plugin_name,
            "skill": None,
            "category": "readme_bloat",
            "severity": severity,
            "message": f"README.md is {line_count} lines (>50). Substantive docs belong in the 'introduce' skill.",
            "fix": "Slim README to: plugin name + install command + skill table. Move content to introduce skill.",
        })

    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def audit(marketplace_dir: Path) -> dict:
    marketplace_dir = marketplace_dir.resolve()
    plugins_dir = marketplace_dir / "plugins"
    marketplace_json_path = marketplace_dir / ".claude-plugin" / "marketplace.json"
    marketplace_json = _json_load(marketplace_json_path)

    # Repo root for git operations
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(marketplace_dir),
        capture_output=True,
        text=True,
    )
    repo_root = Path(r.stdout.strip()) if r.returncode == 0 else marketplace_dir

    all_issues = []
    plugin_count = 0
    skill_count = 0

    # Marketplace-level shell script check
    all_issues.extend(check_shell_scripts(marketplace_dir))

    if plugins_dir.exists():
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            plugin_count += 1

            # Count skills
            skills_dir = plugin_dir / "skills"
            if skills_dir.exists():
                skill_count += sum(1 for d in skills_dir.iterdir() if d.is_dir())

            all_issues.extend(check_version_tracking(plugin_dir, marketplace_json, repo_root))
            all_issues.extend(check_skill_naming(plugin_dir))
            all_issues.extend(check_mandatory_patterns(plugin_dir))
            all_issues.extend(check_readme_bloat(plugin_dir))

    errors = sum(1 for i in all_issues if i["severity"] == "ERROR")
    warnings = sum(1 for i in all_issues if i["severity"] == "WARNING")
    infos = sum(1 for i in all_issues if i["severity"] == "INFO")

    return {
        "marketplace": str(marketplace_dir),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "plugins": plugin_count,
            "skills": skill_count,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "total_issues": len(all_issues),
        },
        "issues": all_issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit Claude plugin marketplace compliance")
    parser.add_argument("--marketplace", required=True, help="Path to marketplace root")
    parser.add_argument("--out", help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    result = audit(Path(args.marketplace))

    output = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
        print(
            f"Summary: {result['summary']['plugins']} plugins, {result['summary']['skills']} skills, "
            f"{result['summary']['errors']} errors, {result['summary']['warnings']} warnings",
            file=sys.stderr,
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
