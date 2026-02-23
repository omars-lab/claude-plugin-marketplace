#!/usr/bin/env python3
"""
summarize-ai-usage.py — Extract structured capability data from installed/available plugins.

Usage:
    python3 summarize-ai-usage.py \
        [--installed ~/.claude/plugins/installed_plugins.json] \
        [--marketplace /path/to/marketplace] \
        [--out /tmp/ai-usage-data.json]

Read-only. Safe to re-run. Outputs JSON array of plugin capability records.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _json_load(path: Path) -> dict | list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_frontmatter(text: str) -> dict:
    """Extract name and description from YAML frontmatter."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end > 0 else text[3:]
    result = {}
    for line in block.splitlines():
        m = re.match(r"^(name|description):\s*(.+)$", line.strip())
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _extract_phases(text: str) -> list[str]:
    """Extract condensed phase/step names from workflow headings."""
    phases = re.findall(
        r"^###\s+(?:Phase|Step)\s+\d+[:\s]+(.+)$",
        text,
        re.MULTILINE,
    )
    # Trim to 5 max, clean up
    return [p.strip().rstrip(":") for p in phases[:5]]


def _plugin_description_from_introduce(text: str) -> str:
    """Extract plugin description from the intro paragraph of an introduce skill."""
    # Skip frontmatter
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        body = text[end + 4:].lstrip() if end > 0 else text

    # Look for "What This Plugin Does" section
    m = re.search(r"## What This Plugin Does\n\n(.+?)(?:\n\n|\n##)", body, re.DOTALL)
    if m:
        # First non-empty line of that section
        for line in m.group(1).splitlines():
            line = line.strip().lstrip("*- ")
            if line and not line.startswith("#"):
                return line

    # Fallback: description from YAML frontmatter
    fm = _extract_frontmatter(text)
    return fm.get("description", "")


def _skills_from_introduce(text: str, plugin_name: str) -> list[dict]:
    """
    Try to extract skills from the Skills table in an introduce SKILL.md.
    Table format: | `skill-name` | `/plugin:skill` | Purpose |
    """
    skills = []
    # Find markdown table rows with skill info
    for line in text.splitlines():
        # Match: | `skill-name` | `/plugin:skill` | Description |
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*`(/[^`]+)`\s*\|\s*(.+?)\s*\|", line)
        if m:
            skill_name = m.group(1)
            # invocation = m.group(2)  # e.g. /claude-manager:fix-plugins
            description = m.group(3).strip()
            # Skip header rows
            if skill_name in ("Skill", "---", "skill"):
                continue
            # Skip introduce itself
            if skill_name == "introduce":
                continue
            skills.append({"name": skill_name, "description": description, "phases": []})
    return skills


def _skills_from_skill_mds(skills_dir: Path) -> list[dict]:
    """Read each skill's SKILL.md directly."""
    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        if skill_name == "introduce":
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = _read(skill_md)
        fm = _extract_frontmatter(text)
        description = fm.get("description", "")
        # Fallback: first H1 line after frontmatter
        if not description:
            body = text
            if text.startswith("---"):
                end = text.find("\n---", 3)
                body = text[end + 4:].lstrip() if end > 0 else text
            m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if m:
                description = m.group(1).strip()
        phases = _extract_phases(text)
        skills.append({
            "name": skill_name,
            "description": description,
            "phases": phases,
        })
    return skills


# ---------------------------------------------------------------------------
# Process one plugin
# ---------------------------------------------------------------------------

def process_plugin(plugin_dir: Path) -> dict | None:
    plugin_name = plugin_dir.name
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return None

    # Try introduce skill first
    introduce_md = skills_dir / "introduce" / "SKILL.md"
    plugin_description = ""
    skills = []
    source = "skills"

    if introduce_md.exists():
        text = _read(introduce_md)
        plugin_description = _plugin_description_from_introduce(text)
        skills = _skills_from_introduce(text, plugin_name)
        if skills:
            source = "introduce"
            # Enrich with phases from individual SKILL.md files
            for skill in skills:
                skill_md = skills_dir / skill["name"] / "SKILL.md"
                if skill_md.exists():
                    skill["phases"] = _extract_phases(_read(skill_md))

    if not skills:
        skills = _skills_from_skill_mds(skills_dir)

    # Fallback description from plugin.json
    if not plugin_description:
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        pj = _json_load(plugin_json)
        if isinstance(pj, dict):
            plugin_description = pj.get("description", "")

    if not skills:
        return None

    return {
        "plugin": plugin_name,
        "description": plugin_description,
        "source": source,
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# Resolve plugin paths
# ---------------------------------------------------------------------------

def find_plugin_dirs(
    installed_path: Path | None,
    marketplace_path: Path | None,
) -> list[Path]:
    """Collect plugin source directories from installed_plugins.json and/or a marketplace."""
    dirs = []
    seen = set()

    def _add(d: Path):
        d = d.resolve()
        if d not in seen and d.is_dir():
            seen.add(d)
            dirs.append(d)

    if installed_path and installed_path.exists():
        data = _json_load(installed_path)
        # installed_plugins.json format:
        # { "marketplace-name": { "plugin-name": { "source": "/path/to/plugin", ... }, ... } }
        if isinstance(data, dict):
            for marketplace_name, plugins in data.items():
                if isinstance(plugins, dict):
                    for plugin_name, info in plugins.items():
                        if isinstance(info, dict):
                            src = info.get("source") or info.get("sourcePath")
                            if src:
                                _add(Path(src))

    if marketplace_path:
        plugins_dir = marketplace_path / "plugins"
        if plugins_dir.exists():
            for d in sorted(plugins_dir.iterdir()):
                if d.is_dir():
                    _add(d)

    return dirs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract plugin capability data for AI usage summary")
    parser.add_argument("--installed", help="Path to installed_plugins.json")
    parser.add_argument("--marketplace", help="Path to marketplace root (reads plugins/ subdir)")
    parser.add_argument("--out", help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    if not args.installed and not args.marketplace:
        print("ERROR: provide --installed or --marketplace (or both)", file=sys.stderr)
        sys.exit(1)

    plugin_dirs = find_plugin_dirs(
        Path(args.installed).expanduser() if args.installed else None,
        Path(args.marketplace).expanduser() if args.marketplace else None,
    )

    if not plugin_dirs:
        print("ERROR: no plugin directories found", file=sys.stderr)
        sys.exit(1)

    results = []
    for plugin_dir in plugin_dirs:
        rec = process_plugin(plugin_dir)
        if rec:
            results.append(rec)

    output = json.dumps(results, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Extracted {len(results)} plugins. Report: {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
