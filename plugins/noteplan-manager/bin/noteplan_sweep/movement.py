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


def insert_into_section(dst_text: str, section_header: str,
                        content_lines: list[str], date: str | None) -> str:
    """Insert `content_lines` under `section_header` in `dst_text` and return
    the new text (with a single trailing newline, empty subheaders cleaned).

    Pure (no I/O). Shared by cmd_append_section and cmd_move_range so the
    insertion semantics stay byte-identical between "append content" and
    "move a line range". Behaviour:

      - If the section is absent, create it at EOF first.
      - With `date`, manage a '## From {date}' subheader inside the section:
        append after an existing block, or prepend a new '## From {date}' block.
      - Without `date`, append at the end of the section (before the next
        top-level '# ' header), trimming trailing blank lines first.

    `content_lines` is a list of raw lines WITHOUT trailing newlines (i.e. the
    result of splitting content and dropping a trailing empty element).

    Raises ValueError if the header cannot be located after creation (a bug).
    """
    # Create section at EOF if absent
    if utils.find_section(dst_text, section_header) == -1:
        utils.verbose(f"section {section_header!r} not found — creating at EOF")
        dst_text = dst_text.rstrip("\n") + f"\n\n{section_header}\n"

    lines = dst_text.split("\n")

    # Find the section header line (last match, matching legacy behaviour)
    header_line_idx = None
    for idx, line in enumerate(lines):
        if line.rstrip() == section_header.rstrip():
            header_line_idx = idx
    if header_line_idx is None:
        raise ValueError(f"section header not found after creation: {section_header!r}")

    # Find the end of this section (next top-level # header or EOF)
    section_end_idx = len(lines)
    for idx in range(header_line_idx + 1, len(lines)):
        if re.match(r'^# ', lines[idx]):
            section_end_idx = idx
            break

    body = list(content_lines)

    if date:
        date_end_idx = _find_date_subheader_end(
            lines, header_line_idx + 1, section_end_idx, date
        )
        if date_end_idx != -1:
            utils.verbose(f"found '## From {date}' subheader — appending after its block")
            insert_at = date_end_idx
            while insert_at > header_line_idx + 1 and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            lines = lines[:insert_at] + body + lines[insert_at:]
        else:
            utils.verbose(f"'## From {date}' subheader not found — prepending")
            insert_at = header_line_idx + 1
            while insert_at < section_end_idx and lines[insert_at].strip() == "":
                insert_at += 1
            date_block = [f"## From {date}", ""] + body
            lines = lines[:insert_at] + date_block + lines[insert_at:]
    else:
        insert_at = section_end_idx
        while insert_at > header_line_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines = lines[:insert_at] + body + lines[insert_at:]

    new_text = "\n".join(lines)
    if not new_text.endswith("\n"):
        new_text += "\n"

    return utils.clean_empty_subheaders(new_text)


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

    content_lines = content.split("\n")
    # Remove trailing empty string from split if content ended with \n
    if content_lines and content_lines[-1] == "":
        content_lines = content_lines[:-1]

    text = utils.read_file(dst_path)

    try:
        new_text = insert_into_section(text, args.section_header, content_lines, args.date)
    except ValueError as e:
        utils.err(str(e))
        sys.exit(utils.EXIT_NOT_FOUND)

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

    # Build new src without the moved lines
    new_src_lines = src_lines[:start_0] + src_lines[end_0:]
    new_src_text = "\n".join(new_src_lines)
    if not new_src_text.endswith("\n"):
        new_src_text += "\n"

    # Now compute the new dst text using the shared insertion logic
    dst_text = utils.read_file(dst_path)

    try:
        new_dst_text = insert_into_section(dst_text, args.section_header, moved_lines, args.date)
    except ValueError as e:
        utils.err(str(e))
        sys.exit(utils.EXIT_NOT_FOUND)

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
