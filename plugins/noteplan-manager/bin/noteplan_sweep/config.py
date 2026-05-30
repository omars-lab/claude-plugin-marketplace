"""
config.py — Shared NotePlan configuration derived from the live filesystem.

Provides plantype names, domain emojis, and workstream directories by scanning
the actual Notes folder structure. Falls back to CLAUDE.md tables when the
filesystem isn't available.

Key exports:
  plantype_names(notes_root)  → dict[emoji, name]   (all workstreams + activities + projects)
  domain_for_path(path_str)   → 'work'|'personal'|'earlbear'|'other'
  domain_for_label(label)     → 'work'|'personal'|'earlbear'|'other'
  workstream_dirs(notes_root) → list[Path]           (all plan subdirectories)

Results are cached per notes_root using functools.lru_cache.
"""

import re
from functools import lru_cache
from pathlib import Path

# Import the battle-tested emoji extractor from backlinks.py (no circular dep)
from noteplan_sweep.backlinks import _extract_emoji as _leading_emoji, _subdir_names


# ---------------------------------------------------------------------------
# Domain inference
# ---------------------------------------------------------------------------

_DOMAIN_MARKERS = {
    "work":     ["ServiceNow", "🏢"],
    "personal": ["Personal",   "🏡"],
    "earlbear": ["EarlBear",   "👥"],
}


def domain_for_path(path_str: str) -> str:
    """Infer domain from a file's path string."""
    for domain, markers in _DOMAIN_MARKERS.items():
        if any(m in path_str for m in markers):
            return domain
    return "other"


def domain_for_label(label: str) -> str:
    """
    Infer domain from a project label or repo name.
    Uses keyword heuristics tuned to common repo naming conventions.
    """
    lower = label.lower()
    if any(k in lower for k in ("earlbear", "earl-bear", "oeid")):
        return "earlbear"
    if any(k in lower for k in ("noteplan", "personal", "dotfiles", "home")):
        return "personal"
    return "work"


# ---------------------------------------------------------------------------
# Filesystem scanner
# ---------------------------------------------------------------------------

def _scan_dir_for_names(plan_dir: Path) -> dict[str, str]:
    """
    Scan a plan directory for emoji-named subdirs.
    Returns {emoji: name} for each direct child dir like "🧑🏻‍💻 Development".
    Also recurses one level for project subfolders.
    """
    result: dict[str, str] = {}
    if not plan_dir.exists():
        return result

    for subdir in sorted(plan_dir.iterdir()):
        if not subdir.is_dir():
            continue
        emoji = _leading_emoji(subdir.name)
        name = subdir.name[len(emoji):].strip()
        if emoji and name:
            result[emoji] = name

        # One level of project subfolders (e.g. 🧑🏻‍💻 Development/🤖 Config Agent)
        for proj in sorted(subdir.iterdir()):
            if not proj.is_dir():
                continue
            pemoji = _leading_emoji(proj.name)
            pname  = proj.name[len(pemoji):].strip()
            if pemoji and pname and pemoji not in result:
                result[pemoji] = pname

    return result


@lru_cache(maxsize=4)
def plantype_names(notes_root: Path) -> dict[str, str]:
    """
    Return {emoji: name} for all known plan types.

    Sources (merged in priority order):
      1. Work workstreams:   Notes/🏢 ServiceNow/📆 Plans/
      2. Personal activities: Notes/🏡 Personal/🏡📆 Plans/Present/
      3. EarlBear plans:     Notes/👥 EarlBear/📆 Plans/
      4. CLAUDE.md tables:   fallback when dirs don't exist

    Result is cached per notes_root so repeated calls within a process are free.
    """
    result: dict[str, str] = {}

    plan_roots = [
        notes_root / "Notes" / "🏢 ServiceNow" / "📆 Plans",
        notes_root / "Notes" / "🏡 Personal"   / "🏡📆 Plans" / "Present",
        notes_root / "Notes" / "👥 EarlBear"   / "📆 Plans",
    ]

    for plan_root in plan_roots:
        result.update(_scan_dir_for_names(plan_root))

    # Fallback: parse CLAUDE.md tables if filesystem gave nothing useful
    if len(result) < 5:
        result.update(_plantype_names_from_claude_md(notes_root.parent))

    return result


def _plantype_names_from_claude_md(noteplan_root: Path) -> dict[str, str]:
    """Parse CLAUDE.md workstream and activity tables → {emoji: name}."""
    claude_path = noteplan_root / "CLAUDE.md"
    if not claude_path.exists():
        return {}
    try:
        text = claude_path.read_text(encoding="utf-8")
    except Exception:
        return {}
    result: dict[str, str] = {}
    result.update(_parse_two_col_table(text, "## Workstream Emojis"))
    result.update(_parse_two_col_table(text, "## Activity Emojis"))
    result.update(_parse_two_col_table(text, "### Project Subfolders"))
    return result


def _parse_two_col_table(text: str, section: str) -> dict[str, str]:
    """
    Parse a markdown table under `section` header.
    Expects rows like | Name | Emoji | or | Name | Emoji | Path |
    Returns {emoji: name}.
    """
    result: dict[str, str] = {}
    in_section = False
    in_table = False
    for line in text.splitlines():
        if line.startswith(section):
            in_section = True
            continue
        if in_section and line.startswith("## ") and not line.startswith(section):
            break
        if not in_section:
            continue
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.match(r"^[-:]+$", c) for c in cells if c):
            in_table = True
            continue
        if len(cells) >= 2:
            name  = cells[0].strip("`").strip()
            emoji = cells[1].strip("`").strip()
            # Skip header row
            if name.lower() in ("workstream", "activity", "name", "project", "type"):
                continue
            if emoji and name and len(emoji) <= 8:
                result[emoji] = name
    return result


# ---------------------------------------------------------------------------
# Workstream directory lister
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4)
def workstream_dirs(notes_root: Path) -> list[Path]:
    """
    Return all plan subdirectories across all domains.
    Useful for discovery commands and template routing.
    """
    dirs: list[Path] = []
    for plan_root in [
        notes_root / "🏢 ServiceNow" / "📆 Plans",
        notes_root / "🏡 Personal"   / "🏡📆 Plans" / "Present",
        notes_root / "👥 EarlBear"   / "📆 Plans",
    ]:
        if plan_root.exists():
            dirs.extend(sorted(d for d in plan_root.iterdir() if d.is_dir()))
    return dirs


# ---------------------------------------------------------------------------
# Document type emoji map (static — mirrors CLAUDE.md Document Type Emojis)
# ---------------------------------------------------------------------------

DOC_TYPE_EMOJIS: dict[str, str] = {
    "📆": "Plans",
    "📋": "Lists",
    "👤": "Meetings",
    "👥": "Group Meetings",
    "📝": "Notes",
    "🔬": "Research",
    "🪵": "Backlogs",
    "🎯": "Goals",
    "💭": "Thoughts",
    "♻️": "Habits",
    "📊": "Metrics / Tracking",
    "🧰": "Craftsmanship",
}

# Domain emoji → domain name (mirrors CLAUDE.md Domain Emojis)
DOMAIN_EMOJIS: dict[str, str] = {
    "🏢": "work",
    "🏡": "personal",
    "👥": "earlbear",
}
