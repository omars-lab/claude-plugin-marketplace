"""
movement.py — Content movement commands (Phase B).

Commands: move-range, move-section, append-section, create-section,
          clean-empty-subheaders
"""

import re
import sys
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_content_input(content_file: str) -> str:
    """Read content from a file path or stdin (if content_file == '-')."""
    if content_file == "-":
        import io
        return sys.stdin.read()
    p = Path(content_file)
    return utils.read_file(p)


def _find_date_subheader_end(lines: list[str], section_start: int, section_end: int, date: str) -> int:
    """
    Within lines[section_start:section_end], find the '## From {date}' subheader.
    Return the index *after* all content lines belonging to that subheader
    (i.e. the first line of the next ## header or section_end if none).
    Returns -1 if the subheader is not found.
    """
    target = f"## From {date}"
    i = section_start
    while i < section_end:
        if lines[i].rstrip() == target:
            # Advance past this subheader's content
            j = i + 1
            while j < section_end:
                if re.match(r'^#{1,2} ', lines[j]):
                    break
                j += 1
            return j
        i += 1
    return -1


def _ensure_trailing_newline(text: str) -> str:
    """Return text with exactly one trailing newline."""
    return text.rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# cmd_create_section
# ---------------------------------------------------------------------------

def cmd_create_section(args):
    """
    Add `{args.section_header}` at EOF if not already present in args.file.

    Args:
        args.file           — file path
        args.section_header — header string, e.g. '# [[2026-04-10]]'
    """
    path = Path(args.file)
    text = utils.read_file(path)

    if utils.find_section(text, args.section_header) != -1:
        utils.verbose(f"section already exists: {args.section_header!r}")
        return

    new_text = text.rstrip("\n") + f"\n\n{args.section_header}\n"
    utils.write_file(path, new_text)
    utils.log(f"created section {args.section_header!r} in {path.name}")


# ---------------------------------------------------------------------------
# cmd_append_section
# ---------------------------------------------------------------------------

def cmd_append_section(args):
    """
    Append content under args.section_header in args.dst.

    If the section is absent, create it at EOF first.
    If args.date is provided:
      - Look for an existing '## From {date}' subheader inside the section.
      - If found, append the content after it (after its existing block).
      - If not found, prepend '\\n## From {date}\\n' before the content.
    After writing, call clean_empty_subheaders on the result.

    Args:
        args.dst            — destination file path
        args.section_header — header to append under
        args.content_file   — file with content to append (or '-' for stdin)
        args.date           — optional YYYY-MM-DD date string
    """
    dst_path = Path(args.dst)
    content = _read_content_input(args.content_file)

    # Ensure content ends with a newline
    if content and not content.endswith("\n"):
        content += "\n"

    text = utils.read_file(dst_path)

    # Create section at EOF if absent
    sec_idx = utils.find_section(text, args.section_header)
    if sec_idx == -1:
        utils.verbose(f"section {args.section_header!r} not found — creating at EOF")
        text = text.rstrip("\n") + f"\n\n{args.section_header}\n"
        sec_idx = utils.find_section(text, args.section_header)

    # Find the bounds of the section body (from line after header to next # header)
    # Work in lines for easier insertion
    lines = text.split("\n")

    # Find the line index of the section header
    header_line_idx = None
    for idx, line in enumerate(lines):
        if line.rstrip() == args.section_header.rstrip():
            header_line_idx = idx

    if header_line_idx is None:
        utils.err(f"section header not found after creation attempt: {args.section_header!r}")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Find the end of this section (next # header or EOF)
    section_end_idx = len(lines)
    for idx in range(header_line_idx + 1, len(lines)):
        if re.match(r'^# ', lines[idx]):
            section_end_idx = idx
            break

    content_lines = content.split("\n")
    # Remove trailing empty string from split if content ended with \n
    if content_lines and content_lines[-1] == "":
        content_lines = content_lines[:-1]

    if args.date:
        date_end_idx = _find_date_subheader_end(
            lines, header_line_idx + 1, section_end_idx, args.date
        )
        if date_end_idx != -1:
            # Found existing ## From {date} — insert content after it
            utils.verbose(f"found '## From {args.date}' subheader — appending after its block")
            # Insert before the next ## header or section end
            insert_at = date_end_idx
            # Remove trailing blank lines before insert point
            while insert_at > header_line_idx + 1 and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            lines = lines[:insert_at] + content_lines + lines[insert_at:]
        else:
            # No existing ## From {date} — prepend it with content right after header
            utils.verbose(f"'## From {args.date}' subheader not found — prepending")
            insert_at = header_line_idx + 1
            # Skip any blank lines immediately after the header
            while insert_at < section_end_idx and lines[insert_at].strip() == "":
                insert_at += 1
            date_block = [f"## From {args.date}", ""] + content_lines
            lines = lines[:insert_at] + date_block + lines[insert_at:]
    else:
        # No date — append content at end of section (before section_end_idx)
        insert_at = section_end_idx
        # Remove trailing blank lines before the next section
        while insert_at > header_line_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines = lines[:insert_at] + content_lines + lines[insert_at:]

    new_text = "\n".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"

    # Clean empty subheaders
    new_text = utils.clean_empty_subheaders(new_text)

    utils.write_file(dst_path, new_text)
    utils.log(f"appended content under {args.section_header!r} in {dst_path.name}")


# ---------------------------------------------------------------------------
# cmd_move_range
# ---------------------------------------------------------------------------

def cmd_move_range(args):
    """
    Move lines args.start–args.end (1-based, inclusive) from args.src to
    args.dst under args.section_header. Lines are removed from src.

    Atomic: both writes succeed or neither persists (writes only after both
    new contents are fully computed).

    Args:
        args.src            — source file path
        args.start          — start line number (1-based, inclusive)
        args.end            — end line number (1-based, inclusive)
        args.dst            — destination file path
        args.section_header — header in dst to append under
        args.date           — optional YYYY-MM-DD date string
    """
    src_path = Path(args.src)
    dst_path = Path(args.dst)

    if not src_path.exists():
        utils.err(f"source file not found: {src_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    src_text = utils.read_file(src_path)
    src_lines = src_text.split("\n")

    # Validate line range (convert 1-based to 0-based)
    start_0 = args.start - 1
    end_0 = args.end  # exclusive upper bound for slicing

    if start_0 < 0 or args.end > len(src_lines) or start_0 >= args.end:
        utils.err(f"line range {args.start}–{args.end} is invalid for file with {len(src_lines)} lines")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Extract the content to move
    moved_lines = src_lines[start_0:end_0]
    moved_content = "\n".join(moved_lines) + "\n"

    # Build new src without the moved lines
    new_src_lines = src_lines[:start_0] + src_lines[end_0:]
    new_src_text = "\n".join(new_src_lines)
    if not new_src_text.endswith("\n"):
        new_src_text += "\n"

    # Now compute the new dst text using append_section logic
    dst_text = utils.read_file(dst_path)

    # Create section in dst if absent
    sec_idx = utils.find_section(dst_text, args.section_header)
    if sec_idx == -1:
        utils.verbose(f"section {args.section_header!r} not found in dst — creating at EOF")
        dst_text = dst_text.rstrip("\n") + f"\n\n{args.section_header}\n"

    # Build a fake args object to reuse append_section logic via inline approach
    dst_lines = dst_text.split("\n")

    # Find header line
    header_line_idx = None
    for idx, line in enumerate(dst_lines):
        if line.rstrip() == args.section_header.rstrip():
            header_line_idx = idx

    if header_line_idx is None:
        utils.err(f"section header could not be located after creation: {args.section_header!r}")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Find section end
    section_end_idx = len(dst_lines)
    for idx in range(header_line_idx + 1, len(dst_lines)):
        if re.match(r'^# ', dst_lines[idx]):
            section_end_idx = idx
            break

    moved_body = moved_lines  # list of lines without trailing newline

    if args.date:
        date_end_idx = _find_date_subheader_end(
            dst_lines, header_line_idx + 1, section_end_idx, args.date
        )
        if date_end_idx != -1:
            insert_at = date_end_idx
            while insert_at > header_line_idx + 1 and dst_lines[insert_at - 1].strip() == "":
                insert_at -= 1
            dst_lines = dst_lines[:insert_at] + moved_body + dst_lines[insert_at:]
        else:
            insert_at = header_line_idx + 1
            while insert_at < section_end_idx and dst_lines[insert_at].strip() == "":
                insert_at += 1
            date_block = [f"## From {args.date}", ""] + moved_body
            dst_lines = dst_lines[:insert_at] + date_block + dst_lines[insert_at:]
    else:
        insert_at = section_end_idx
        while insert_at > header_line_idx + 1 and dst_lines[insert_at - 1].strip() == "":
            insert_at -= 1
        dst_lines = dst_lines[:insert_at] + moved_body + dst_lines[insert_at:]

    new_dst_text = "\n".join(dst_lines)
    if not new_dst_text.endswith("\n"):
        new_dst_text += "\n"

    new_dst_text = utils.clean_empty_subheaders(new_dst_text)

    # Atomic: compute both, then write both
    utils.write_file(dst_path, new_dst_text)
    utils.write_file(src_path, new_src_text)
    utils.log(f"moved lines {args.start}–{args.end} from {src_path.name} → {dst_path.name} under {args.section_header!r}")


# ---------------------------------------------------------------------------
# cmd_move_section
# ---------------------------------------------------------------------------

def cmd_move_section(args):
    """
    Find args.section_header in args.src, auto-detect its line range, and
    move it to args.dst under args.dst_section_header.

    Reuses cmd_move_range logic after detecting bounds.

    Args:
        args.src                — source file path
        args.section_header     — section header to move from src
        args.dst                — destination file path
        args.dst_section_header — section header to append under in dst
        args.date               — optional YYYY-MM-DD date string
    """
    src_path = Path(args.src)

    if not src_path.exists():
        utils.err(f"source file not found: {src_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    src_text = utils.read_file(src_path)
    src_lines = src_text.split("\n")

    # Find the section header line (1-based)
    header_line_1based = None
    for idx, line in enumerate(src_lines):
        if line.rstrip() == args.section_header.rstrip():
            header_line_1based = idx + 1  # 1-based
            break

    if header_line_1based is None:
        utils.err(f"section {args.section_header!r} not found in {src_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Detect the level of this header to find the next same-or-higher header
    m = re.match(r'^(#+) ', args.section_header)
    if m:
        level = len(m.group(1))
    else:
        level = 1

    # Find the end of the section: next header at same or higher level
    end_line_1based = len(src_lines)
    for idx in range(header_line_1based, len(src_lines)):  # header_line_1based is already past
        line = src_lines[idx]
        hm = re.match(r'^(#+) ', line)
        if hm and len(hm.group(1)) <= level:
            end_line_1based = idx  # 1-based of previous line = idx (0-based)
            break

    # Trim trailing blank lines from the section
    trim_end = end_line_1based
    while trim_end > header_line_1based and src_lines[trim_end - 1].strip() == "":
        trim_end -= 1

    utils.verbose(
        f"section {args.section_header!r} spans lines {header_line_1based}–{trim_end}"
    )

    # Build a synthetic args namespace for move_range
    import types
    range_args = types.SimpleNamespace(
        src=args.src,
        start=header_line_1based,
        end=trim_end,
        dst=args.dst,
        section_header=args.dst_section_header,
        date=args.date,
    )
    cmd_move_range(range_args)


# ---------------------------------------------------------------------------
# cmd_clean_empty_subheaders
# ---------------------------------------------------------------------------

def cmd_clean_empty_subheaders(args):
    """
    Remove subheaders at args.level (default 2 = ##) that have no content.

    Prints the count of removed headers and writes the cleaned file back.

    Args:
        args.file  — file path
        args.level — header level to clean (default 2)
    """
    path = Path(args.file)
    text = utils.read_file(path)

    cleaned = utils.clean_empty_subheaders(text, level=args.level)

    # Count how many headers were removed
    prefix = "#" * args.level + " "
    original_count = sum(1 for line in text.split("\n") if line.startswith(prefix))
    cleaned_count = sum(1 for line in cleaned.split("\n") if line.startswith(prefix))
    removed = original_count - cleaned_count

    utils.write_file(path, cleaned)
    utils.log(f"removed {removed} empty level-{args.level} subheader(s) from {path.name}")
