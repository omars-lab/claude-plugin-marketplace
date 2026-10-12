#!/usr/bin/env python3
"""Find `plugin:name` references that do not name anything Claude can call.

Claude Code lists a plugin's skills one folder deep (skills/<name>/SKILL.md), plus its
commands (commands/<name>.md) and agents (agents/<name>.md). A skill in a folder inside
another skill's folder is never listed, so `/skill-manager:create-plugin` reaches nothing;
it is reached through its routing skill (`/skill-manager:manage-plugins`) instead.

Only names of plugins in this marketplace are checked, so `plugin@marketplace` and other
text with a colon are left alone. Only Markdown and JSON are read: that is where skills,
commands and hooks name each other.

Usage: check-skill-refs.py [--fix] [plugin ...]     (default: every plugin)
Prints each broken reference as file:line: plugin:name, and exits 1 when one is left.
--fix rewrites a reference to a skill inside a routing skill's folder the way skill-manager
writes them, `/skill-manager:manage-skills` → evaluate-skill, and prints only what it could
not fix: names that are nowhere in the plugin, which need a person to pick the new target.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
TEXT = {".md", ".json"}


def callable_names(plugin_dir):
    names = {p.parent.name for p in plugin_dir.glob("skills/*/SKILL.md")}
    names |= {p.stem for p in plugin_dir.glob("commands/*.md")}
    names |= {p.stem for p in plugin_dir.glob("agents/*.md")}
    return names


def routed_names(plugin_dir):
    """A skill inside a routing skill's folder -> that routing skill's name."""
    routes = {}
    for p in plugin_dir.glob("skills/*/*/**/SKILL.md"):
        parts = p.relative_to(plugin_dir / "skills").parts
        routes.setdefault(p.parent.name, parts[0])
    return routes


def main(args):
    fix = "--fix" in args
    only = [a for a in args if a != "--fix"]
    registered = [p["name"] for p in json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"]]
    known = {n: callable_names(PLUGINS / n) for n in registered if (PLUGINS / n).is_dir()}
    routes = {n: routed_names(PLUGINS / n) for n in known}
    # A backtick right after the name is kept outside the arrow: `/p:x` -> `/p:route` → x
    pattern = re.compile(r"(?<![\w@.-])(/?)(" + "|".join(map(re.escape, known)) + r"):([a-z][a-z0-9-]*)(`?)")
    broken = 0
    for name in only or sorted(known):
        for path in sorted((PLUGINS / name).rglob("*")):
            if path.suffix not in TEXT or not path.is_file():
                continue
            lines = path.read_text(errors="replace").splitlines(keepends=True)
            changed = False
            for i, line in enumerate(lines):
                def swap(m):
                    nonlocal broken, changed
                    slash, plugin, skill, tick = m.groups()
                    if skill in known[plugin]:
                        return m.group(0)
                    route = routes[plugin].get(skill)
                    if fix and route:
                        changed = True
                        return f"{slash}{plugin}:{route}{tick} → {skill}"
                    print(f"{path.relative_to(ROOT)}:{i + 1}: {plugin}:{skill}")
                    broken += 1
                    return m.group(0)
                lines[i] = pattern.sub(swap, line)
            if changed:
                path.write_text("".join(lines))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
