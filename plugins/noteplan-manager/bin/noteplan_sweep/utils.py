"""
utils.py — Shared utilities for noteplan-sweep CLI.
"""

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_VALIDATION_FAILURE = 1
EXIT_NOT_FOUND = 2
EXIT_CONFLICT = 3

# ---------------------------------------------------------------------------
# Global flags (set by main before dispatching)
# ---------------------------------------------------------------------------
DRY_RUN = False
VERBOSE = False
QUIET = False

def log(msg: str):
    """Print unless --quiet."""
    if not QUIET:
        print(msg)

def verbose(msg: str):
    """Print only if --verbose."""
    if VERBOSE:
        print(msg, file=sys.stderr)

def err(msg: str):
    """Always print to stderr."""
    print(f"ERROR: {msg}", file=sys.stderr)

def dry(msg: str):
    """Print a dry-run action description."""
    if DRY_RUN:
        print(f"[dry-run] {msg}")

# ---------------------------------------------------------------------------
# NotePlan root detection
# ---------------------------------------------------------------------------
def noteplan_root() -> Path:
    home = Path.home()
    p = home / "Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
    if p.exists():
        return p
    raise FileNotFoundError(f"NotePlan root not found at {p}")

def notes_root() -> Path:
    return noteplan_root() / "Notes"

def calendar_root() -> Path:
    return noteplan_root() / "Calendar"

def templates_root() -> Path:
    return notes_root() / "@Templates"

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        err(f"File not found: {path}")
        sys.exit(EXIT_NOT_FOUND)

def write_file(path: Path, content: str):
    if DRY_RUN:
        dry(f"write {path} ({len(content.splitlines())} lines)")
        return
    path.write_text(content, encoding="utf-8")
    verbose(f"wrote {path}")

def all_md_files(root: Path) -> list[Path]:
    """Recursively find all .md files under root, excluding @Backup."""
    return [
        p for p in root.rglob("*.md")
        if "@Backup" not in str(p)
    ]

# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------
def find_section(text: str, header: str) -> int:
    """Return index of last occurrence of header line, or -1."""
    idx = text.rfind(f"\n{header}\n")
    if idx == -1 and text.startswith(f"{header}\n"):
        return 0
    return idx + 1 if idx != -1 else -1

def next_top_section(text: str, after: int) -> int:
    """Return index of next `# ` header after position, or len(text)."""
    m = re.search(r'\n# ', text[after:])
    return after + m.start() if m else len(text)

def clean_empty_subheaders(text: str, level: int = 2) -> str:
    """
    Remove `##`-level (or given level) subheaders that have no non-whitespace
    content before the next header of same or higher level.
    Catches the 'From YYYY-MM-DD' empty block pattern from sweep.
    """
    prefix = "#" * level + " "
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(prefix):
            # Collect lines until next header of same or higher level
            j = i + 1
            content_lines = []
            while j < len(lines):
                if re.match(r'^#{1,' + str(level) + r'} ', lines[j]):
                    break
                content_lines.append(lines[j])
                j += 1
            # Check if there's any non-whitespace content
            has_content = any(l.strip() for l in content_lines)
            if has_content:
                result.append(line)
                result.extend(content_lines)
            else:
                verbose(f"removed empty subheader: {line!r}")
            i = j
        else:
            result.append(line)
            i += 1
    return "\n".join(result)
