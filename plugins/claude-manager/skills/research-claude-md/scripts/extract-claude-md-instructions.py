#!/usr/bin/env python3
"""
extract-claude-md-instructions.py

Scans ALL Claude session logs (~/.claude/projects/**/*.jsonl) and all
CLAUDE.md files in known workspace roots.

Outputs a JSON report with two sections:
  - instructions: user messages where they asked Claude to modify CLAUDE.md
  - existing_claude_mds: content of every CLAUDE.md found on disk

Usage:
    python3 extract-claude-md-instructions.py [--workspace-root PATH] [--out FILE]

Defaults:
    --workspace-root  ~/Library/CloudStorage/OneDrive-ServiceNow/workspace
                      ~/workspace
    --out             stdout (pipe to file or let the skill capture it)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── Session log location ──────────────────────────────────────────────────────
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

# ── Workspace roots to scan for CLAUDE.md files ──────────────────────────────
DEFAULT_WORKSPACE_ROOTS = [
    Path.home() / "Library" / "CloudStorage" / "OneDrive-ServiceNow" / "workspace",
    Path.home() / "workspace",
    Path.home() / "Documents",
]

# ── Patterns that indicate the user is giving CLAUDE.md instructions ──────────
# Match on the lowercased user text.
CLAUDE_MD_PATTERNS = [
    # Direct file mentions
    r"claude\.md",
    r"project\s+instructions?",
    # Common imperative forms aimed at instruction files
    r"\b(add|append|include|put|insert)\s+(this|that|it)\s+(to|in|into)\s+(the\s+)?(project\s+)?instructions?",
    r"\b(update|modify|edit|change|fix|rewrite|improve|reorganize|organize)\s+(the\s+)?(project\s+)?instructions?",
    r"\b(remove|delete|drop|strip)\s+(this|that|from)\s+(the\s+)?(project\s+)?instructions?",
    # Meta-instructions (remember / always / never)
    r"\bremember\s+(this|that|to\s+always|to\s+never|going\s+forward)",
    r"\balways\s+(use|do|run|prefer|avoid|check|ask)",
    r"\bnever\s+(use|do|run|modify|commit|push|delete|skip)",
    r"\bfrom\s+now\s+on\b",
    r"\bgoing\s+forward\b",
    r"\bmake\s+(a\s+)?note\s+of\b",
    r"\bkeep\s+(this|that)\s+in\s+mind\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in CLAUDE_MD_PATTERNS]

# Directories to skip while scanning for CLAUDE.md files
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_text(content) -> str:
    """Flatten a message content field to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "\n".join(parts)
    return ""


def is_claude_md_instruction(text: str) -> bool:
    """Return True if the text looks like a CLAUDE.md instruction."""
    for pattern in _COMPILED:
        if pattern.search(text):
            return True
    return False


def project_label(jsonl_path: Path) -> str:
    """Derive a human-readable project name from the session file path."""
    # ~/.claude/projects/<encoded-path>/<uuid>.jsonl
    # The encoded path uses hyphens for path separators.
    parts = jsonl_path.parts
    try:
        idx = parts.index("projects")
        encoded = parts[idx + 1]
        # Strip the leading '-Users-<name>-' prefix that's common to all
        label = re.sub(r"^-Users-[^-]+-", "", encoded)
        # Convert remaining hyphens back to slashes for readability
        return label.replace("-", "/").strip("/") or encoded
    except (ValueError, IndexError):
        return str(jsonl_path.parent.name)


def scan_session(jsonl_path: Path) -> list[dict]:
    """Return CLAUDE.md-related user messages from one session file."""
    results = []
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "user":
                    continue
                if obj.get("isMeta"):
                    continue

                msg = obj.get("message") or {}
                text = extract_text(msg.get("content", ""))
                if len(text) < 20:
                    continue
                # Skip system-injected caveats
                if "local-command-caveat" in text or "system-reminder" in text:
                    continue

                if is_claude_md_instruction(text):
                    results.append(
                        {
                            "project": project_label(jsonl_path),
                            "session_file": str(jsonl_path),
                            "timestamp": obj.get("timestamp", ""),
                            "text": text[:800],  # cap length
                        }
                    )
    except (IOError, PermissionError, OSError):
        pass
    return results


def find_all_claude_mds(workspace_roots: list[Path]) -> list[dict]:
    """Walk workspace roots and collect every CLAUDE.md found."""
    results = []
    seen = set()
    for root in workspace_roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs in-place
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                if fname != "CLAUDE.md":
                    continue
                full = Path(dirpath) / fname
                if full in seen:
                    continue
                seen.add(full)
                try:
                    content = full.read_text(encoding="utf-8", errors="replace")
                    results.append(
                        {
                            "path": str(full),
                            "content": content[:3000],  # cap at 3k chars
                            "truncated": len(content) > 3000,
                        }
                    )
                except (IOError, PermissionError, OSError):
                    pass
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--workspace-root",
        action="append",
        dest="workspace_roots",
        metavar="PATH",
        help="Workspace root(s) to scan for CLAUDE.md files (repeatable). Defaults to ~/workspace and OneDrive workspace.",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a human-readable summary to stderr alongside the JSON output.",
    )
    args = parser.parse_args()

    workspace_roots = (
        [Path(r).expanduser() for r in args.workspace_roots]
        if args.workspace_roots
        else DEFAULT_WORKSPACE_ROOTS
    )

    # ── 1. Scan session logs ────────────────────────────────────────────────
    if args.summary:
        print("Scanning session logs...", file=sys.stderr)

    all_instructions: list[dict] = []
    jsonl_files = sorted(CLAUDE_PROJECTS.rglob("*.jsonl")) if CLAUDE_PROJECTS.exists() else []

    if args.summary:
        print(f"  {len(jsonl_files)} session files found", file=sys.stderr)

    for jsonl_path in jsonl_files:
        all_instructions.extend(scan_session(jsonl_path))

    # Sort by timestamp descending (most recent first)
    all_instructions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    if args.summary:
        print(f"  {len(all_instructions)} CLAUDE.md-related instructions extracted", file=sys.stderr)

    # ── 2. Find CLAUDE.md files ─────────────────────────────────────────────
    if args.summary:
        print("Scanning for CLAUDE.md files...", file=sys.stderr)

    claude_mds = find_all_claude_mds(workspace_roots)

    if args.summary:
        print(f"  {len(claude_mds)} CLAUDE.md files found", file=sys.stderr)

    # ── 3. Emit output ──────────────────────────────────────────────────────
    report = {
        "stats": {
            "session_files_scanned": len(jsonl_files),
            "instructions_found": len(all_instructions),
            "claude_mds_found": len(claude_mds),
        },
        "instructions": all_instructions,
        "existing_claude_mds": claude_mds,
    }

    output = json.dumps(report, indent=2, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        if args.summary:
            print(f"\nReport written to: {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
