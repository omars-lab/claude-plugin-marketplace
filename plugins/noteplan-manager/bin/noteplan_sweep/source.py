"""
source.py — Source management commands (Phase C).

Commands: clear-source, add-breadcrumb
"""

import re
import sys
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches a completed task bullet: "- [x] ..." or "* [x] ..."
_COMPLETED_RE = re.compile(r'^[\-\*] \[x\] ', re.IGNORECASE)

# Matches the breadcrumb table header row exactly
_BREADCRUMB_HEADER = "| Swept | Section | Summary | Destination |"
_BREADCRUMB_SEP    = "| --- | --- | --- | --- |"

# Matches any markdown table row
_TABLE_ROW_RE = re.compile(r'^\|')


def _is_completed_task(line: str) -> bool:
    """Return True if line is a completed task bullet."""
    return bool(_COMPLETED_RE.match(line.strip()))


def _is_indented_child(line: str) -> bool:
    """Return True if line is indented (continuation/child of a task)."""
    return len(line) > 0 and line[0] in (" ", "\t")


def _is_open_task(line: str) -> bool:
    """Return True if line is an open/unchecked task bullet."""
    stripped = line.strip()
    return bool(re.match(r'^[\-\*] \[ \] ', stripped))


def _collect_breadcrumb_block(lines: list[str]) -> tuple[int, int] | None:
    """
    Find the breadcrumb table in lines.
    Returns (start_idx, end_idx) where lines[start_idx:end_idx] is the full
    table (inclusive of header, separator, all rows). Returns None if absent.
    """
    for i, line in enumerate(lines):
        if line.strip() == _BREADCRUMB_HEADER:
            # Find where the table ends (first non-table line)
            j = i + 1
            while j < len(lines) and _TABLE_ROW_RE.match(lines[j].strip()):
                j += 1
            return (i, j)
    return None


# ---------------------------------------------------------------------------
# cmd_clear_source
# ---------------------------------------------------------------------------

def cmd_clear_source(args):
    """
    Clean a swept source note, keeping only:
      1. Completed tasks (lines matching '- [x]' or '* [x]') and their
         indented children.
      2. The breadcrumb table block ('| Swept | ...' through end of table).

    Everything else is removed: open tasks, unlabeled content, section
    headers that become empty after removal.  The breadcrumb block is
    preserved verbatim.

    Args:
        args.file           — source daily note path
        args.keep_completed — (default True) keep [x] tasks
    """
    path = Path(args.file)
    text = utils.read_file(path)
    lines = text.split("\n")

    breadcrumb = _collect_breadcrumb_block(lines)
    breadcrumb_range = set(range(*breadcrumb)) if breadcrumb else set()

    keep: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Always preserve breadcrumb table lines verbatim
        if i in breadcrumb_range:
            keep.append(line)
            i += 1
            continue

        # Keep completed tasks and their indented children
        if _is_completed_task(line):
            keep.append(line)
            i += 1
            # Collect indented children
            while i < len(lines) and _is_indented_child(lines[i]):
                keep.append(lines[i])
                i += 1
            continue

        # Skip everything else (open tasks, unlabeled content, headers)
        i += 1

    # Remove section headers that have no content after them
    # (i.e. headers immediately followed by another header or EOF)
    cleaned = _remove_empty_section_headers(keep)

    # Collapse multiple consecutive blank lines into at most one
    collapsed = _collapse_blank_lines(cleaned)

    new_text = "\n".join(collapsed)
    if not new_text.endswith("\n"):
        new_text += "\n"

    utils.write_file(path, new_text)
    utils.log(f"cleared source {path.name} — kept {len(collapsed)} lines")


def _remove_empty_section_headers(lines: list[str]) -> list[str]:
    """
    Remove any `#`-prefixed header line that has no non-whitespace content
    between it and the next header (or EOF).  Breadcrumb table rows count
    as content.
    """
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^#{1,6} ', line):
            # Look ahead for content
            j = i + 1
            has_content = False
            while j < len(lines):
                ahead = lines[j]
                if re.match(r'^#{1,6} ', ahead):
                    break
                if ahead.strip():
                    has_content = True
                    break
                j += 1
            if has_content:
                result.append(line)
            # Skip empty headers silently
        else:
            result.append(line)
        i += 1
    return result


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    """Collapse runs of more than one blank line into a single blank line."""
    result = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# cmd_add_breadcrumb
# ---------------------------------------------------------------------------

def cmd_add_breadcrumb(args):
    """
    Append a row to the '| Swept | Section | Summary | Destination |' table
    in args.file.  Creates the full table (header + separator + row) at EOF
    if not found.  Inserts before a trailing '---' separator if one exists.

    Args:
        args.file        — source note to append breadcrumb table to
        args.date        — sweep date (YYYY-MM-DD)
        args.section     — section name that was swept
        args.summary     — one-line summary of what was moved
        args.destination — destination wikilink e.g. [[20260412]]
    """
    path = Path(args.file)
    text = utils.read_file(path)
    lines = text.split("\n")

    new_row = f"| {args.date} | {args.section} | {args.summary} | {args.destination} |"

    breadcrumb = _collect_breadcrumb_block(lines)

    if breadcrumb is not None:
        # Table exists — append new row at end of table
        _start, end_idx = breadcrumb
        # Insert the new row just before end_idx
        lines = lines[:end_idx] + [new_row] + lines[end_idx:]
        utils.verbose(f"appended breadcrumb row at line {end_idx + 1}")
    else:
        # Table does not exist — create it at EOF (before trailing '---' if present)
        table_block = [
            "",
            _BREADCRUMB_HEADER,
            _BREADCRUMB_SEP,
            new_row,
        ]

        # Strip trailing empty lines to find the insertion point
        insert_at = len(lines)
        # If last non-empty line is '---', insert before it
        trimmed_end = insert_at
        while trimmed_end > 0 and lines[trimmed_end - 1].strip() == "":
            trimmed_end -= 1

        if trimmed_end > 0 and lines[trimmed_end - 1].strip() == "---":
            insert_at = trimmed_end - 1
            lines = lines[:insert_at] + table_block + [""] + lines[insert_at:]
        else:
            lines = lines[:insert_at] + table_block

        utils.verbose("created breadcrumb table at EOF")

    new_text = "\n".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"

    utils.write_file(path, new_text)
    utils.log(f"added breadcrumb row to {path.name}: {new_row}")
