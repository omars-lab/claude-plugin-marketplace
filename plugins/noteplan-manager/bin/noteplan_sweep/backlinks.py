"""
backlinks.py — Backlink and living artifact commands (Phase E) for noteplan-sweep CLI.

Commands:
  update-backlinks        Replace [[old-stem]] with [[new-stem]] across all .md files
  check-backlinks         Report all files referencing [[stem]] (informational)
  check-emoji-mappings    Report mismatches between actual plan dirs and CLAUDE.md tables
  sync-emoji-mappings     Rewrite emoji tables in CLAUDE.md from actual plan dirs
  check-living-artifacts  After rename or new plan, list every living doc that may need updating
  check-note-map          Validate Note Map folder tree matches actual directory structure
  sync-note-map           Rebuild Note Map folder tree from actual directory structure
"""

import re
import sys
from pathlib import Path

import noteplan_sweep.utils as utils

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _all_md_roots() -> list[Path]:
    """Return [notes_root, calendar_root], filtering out missing ones."""
    roots = []
    try:
        nr = utils.notes_root()
        if nr.exists():
            roots.append(nr)
    except FileNotFoundError:
        pass
    try:
        cr = utils.calendar_root()
        if cr.exists():
            roots.append(cr)
    except FileNotFoundError:
        pass
    return roots


def _scan_all_md(notes_dir: Path | None = None) -> list[Path]:
    """
    Collect all .md files under notes_dir + calendar_root (or auto-detected roots).
    Skips @Backup directories.
    """
    if notes_dir is not None:
        roots = [notes_dir]
        try:
            cr = utils.calendar_root()
            if cr.exists():
                roots.append(cr)
        except FileNotFoundError:
            pass
    else:
        roots = _all_md_roots()

    files: list[Path] = []
    for root in roots:
        for p in root.rglob("*.md"):
            if "@Backup" not in str(p):
                files.append(p)
    return files


def _files_referencing(stem: str, notes_dir: Path | None = None) -> list[Path]:
    """Return all .md files that contain [[stem]]."""
    pattern = f"[[{stem}]]"
    matches = []
    for md_file in _scan_all_md(notes_dir):
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            utils.verbose(f"  skipping unreadable: {md_file}")
            continue
        if pattern in content:
            matches.append(md_file)
    return matches


def _extract_emoji(name: str) -> str:
    """
    Extract the leading emoji(s) from a directory name.

    Emoji characters can be multi-codepoint (ZWJ sequences, variation selectors,
    skin tone modifiers). We grab all leading non-ASCII-letter, non-digit,
    non-space characters up to the first space or ASCII word character.

    Examples:
      "🧑🏻‍💻 Development" → "🧑🏻‍💻"
      "✍🏻 Documenting"   → "✍🏻"
      "🤿 Deep Dives"     → "🤿"
    """
    # Walk codepoints, consuming emoji/modifier/ZWJ/variation sequences
    EMOJI_RANGES = (
        (0x1F300, 0x1FAFF),  # Misc symbols, emoticons, supplemental
        (0x2600,  0x27BF),   # Misc symbols, dingbats
        (0x2B00,  0x2BFF),   # Misc symbols and arrows
        (0xFE00,  0xFE0F),   # Variation selectors
        (0x1F1E0, 0x1F1FF),  # Regional indicator symbols
        (0x200D,  0x200D),   # ZWJ
        (0x1F3FB, 0x1F3FF),  # Skin-tone modifiers
        (0xFE0F,  0xFE0F),   # Variation selector-16
        (0x20E3,  0x20E3),   # Combining enclosing keycap
        (0x231A,  0x231B),   # Watch, hourglass
        (0x23E9,  0x23F3),   # Various clock/time
        (0x23F8,  0x23FA),
        (0x25AA,  0x25AB),
        (0x25B6,  0x25B6),
        (0x25C0,  0x25C0),
        (0x25FB,  0x25FE),
        (0x2614,  0x2615),
        (0x2648,  0x2653),
        (0x267F,  0x267F),
        (0x2693,  0x2693),
        (0x26A1,  0x26A1),
        (0x26AA,  0x26AB),
        (0x26BD,  0x26BE),
        (0x26C4,  0x26C5),
        (0x26CE,  0x26CE),
        (0x26D4,  0x26D4),
        (0x26EA,  0x26EA),
        (0x26F2,  0x26F3),
        (0x26F5,  0x26F5),
        (0x26FA,  0x26FA),
        (0x26FD,  0x26FD),
        (0x2702,  0x2702),
        (0x2705,  0x2705),
        (0x2708,  0x270D),
        (0x270F,  0x270F),
        (0x2712,  0x2712),
        (0x2714,  0x2714),
        (0x2716,  0x2716),
        (0x271D,  0x271D),
        (0x2721,  0x2721),
        (0x2728,  0x2728),
        (0x2733,  0x2734),
        (0x2744,  0x2744),
        (0x2747,  0x2747),
        (0x274C,  0x274C),
        (0x274E,  0x274E),
        (0x2753,  0x2755),
        (0x2757,  0x2757),
        (0x2763,  0x2764),
        (0x2795,  0x2797),
        (0x27A1,  0x27A1),
        (0x27B0,  0x27B0),
        (0x27BF,  0x27BF),
        (0x2934,  0x2935),
        (0x2B05,  0x2B07),
        (0x2B1B,  0x2B1C),
        (0x2B50,  0x2B50),
        (0x2B55,  0x2B55),
        (0x3030,  0x3030),
        (0x303D,  0x303D),
        (0x3297,  0x3297),
        (0x3299,  0x3299),
    )

    def _is_emoji_cp(cp: int) -> bool:
        for lo, hi in EMOJI_RANGES:
            if lo <= cp <= hi:
                return True
        return False

    codepoints = list(name)
    i = 0
    end = 0
    while i < len(codepoints):
        cp = ord(codepoints[i])
        if _is_emoji_cp(cp) or cp == 0x200D or (0xFE00 <= cp <= 0xFE0F):
            end = i + 1
            i += 1
        else:
            break

    if end == 0:
        return ""
    return name[:end]


def _subdir_names(path: Path) -> list[str]:
    """Return sorted list of immediate subdirectory names under path (if it exists)."""
    if not path.exists():
        return []
    return sorted(d.name for d in path.iterdir() if d.is_dir())


# ---------------------------------------------------------------------------
# CLAUDE.md table parsing helpers
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r'^\|(.+)\|$')


def _parse_markdown_table(lines: list[str]) -> list[list[str]]:
    """
    Parse a simple markdown table (header + separator + rows) into a list of
    row cell-lists. Ignores the header row and separator row.
    Returns only data rows.
    """
    rows = []
    header_done = False
    for line in lines:
        m = _TABLE_ROW_RE.match(line.strip())
        if not m:
            break  # table ended
        cells = [c.strip() for c in m.group(1).split("|")]
        if all(re.match(r'^-+$', c) for c in cells):
            header_done = True
            continue
        if not header_done:
            # This is the header row — skip
            continue
        rows.append(cells)
    return rows


def _find_section_lines(text: str, section_header: str) -> tuple[int, int]:
    """
    Find the line range [start, end) of a markdown section identified by its
    `## SectionHeader` heading. Returns (start_line_idx, end_line_idx) where
    start_line_idx is the `## ` line itself and end_line_idx is exclusive
    (either next `##`/`#` header or EOF).

    Returns (-1, -1) if not found.
    """
    lines = text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            start = i
            break
    if start == -1:
        return (-1, -1)

    # Find next header of equal or higher level
    # Determine level from section_header
    level = 0
    for ch in section_header:
        if ch == "#":
            level += 1
        else:
            break
    prefix_pattern = re.compile(r'^#{1,' + str(level) + r'} ')

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if prefix_pattern.match(lines[i]):
            end = i
            break
    return (start, end)


def _build_table_rows_2col(data: list[tuple[str, str]], col1: str, col2: str) -> str:
    """Build a 2-column markdown table string (header + separator + rows)."""
    lines = [
        f"| {col1} | {col2} |",
        "|---|---|",
    ]
    for v1, v2 in data:
        lines.append(f"| {v1} | {v2} |")
    return "\n".join(lines)


def _extract_emoji_table(claude_text: str, section_header: str) -> dict[str, str]:
    """
    Parse a 2-column markdown table under `section_header` in CLAUDE.md.
    Returns {name: emoji} for each row where col1=Name, col2=Emoji.
    """
    lines = claude_text.splitlines()
    start, end = _find_section_lines(claude_text, section_header)
    if start == -1:
        return {}

    section_lines = lines[start:end]

    # Find the table within the section
    in_table = False
    table_lines = []
    for line in section_lines:
        if _TABLE_ROW_RE.match(line.strip()):
            in_table = True
            table_lines.append(line.strip())
        elif in_table:
            # Table ended
            break

    rows = _parse_markdown_table(table_lines)
    result = {}
    for row in rows:
        if len(row) >= 2:
            name = row[0].strip()
            emoji = row[1].strip()
            result[name] = emoji
    return result


def _dirs_to_name_emoji(dir_names: list[str]) -> list[tuple[str, str]]:
    """
    Convert directory names like "🧑🏻‍💻 Development" into (name, emoji) tuples.
    Returns sorted by name.
    """
    result = []
    for dirname in dir_names:
        emoji = _extract_emoji(dirname)
        name = dirname[len(emoji):].strip()
        if name and emoji:
            result.append((name, emoji))
    return sorted(result, key=lambda t: t[0])


# ---------------------------------------------------------------------------
# 1. cmd_update_backlinks
# ---------------------------------------------------------------------------

def cmd_update_backlinks(args):
    """
    Replace all [[old_stem]] with [[new_stem]] across all .md files.

    Two modes:
      --from-rename OLD_FILE NEW_FILE  — derive stems from file paths
      --old-stem OLD --new-stem NEW    — use stems directly

    Scans args.notes_dir (or auto-detected notes + calendar roots).
    Prints count of files changed and total replacements.
    Writes via utils.write_file (respects DRY_RUN).
    """
    # Resolve stems
    if hasattr(args, 'from_rename') and args.from_rename:
        old_file, new_file = args.from_rename
        old_stem = Path(old_file).stem
        new_stem = Path(new_file).stem
    elif hasattr(args, 'old_stem') and args.old_stem and hasattr(args, 'new_stem') and args.new_stem:
        old_stem = args.old_stem
        new_stem = args.new_stem
    else:
        utils.err("update-backlinks requires either --from-rename or both --old-stem and --new-stem")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else None

    old_link = f"[[{old_stem}]]"
    new_link = f"[[{new_stem}]]"

    utils.verbose(f"Replacing {old_link} → {new_link}")
    utils.log(f"Scanning for {old_link} ...")

    all_files = _scan_all_md(notes_dir)
    files_changed = 0
    total_replacements = 0

    for md_file in all_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            utils.verbose(f"  skipping unreadable: {md_file}")
            continue

        count = content.count(old_link)
        if count == 0:
            continue

        new_content = content.replace(old_link, new_link)
        utils.verbose(f"  {md_file.name}: {count} replacement(s)")
        utils.write_file(md_file, new_content)
        files_changed += 1
        total_replacements += count

    if files_changed == 0:
        utils.log(f"No files reference {old_link} — nothing to update")
    else:
        utils.log(
            f"Updated {total_replacements} occurrence(s) of {old_link} → {new_link} "
            f"across {files_changed} file(s)"
        )

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 2. cmd_check_backlinks
# ---------------------------------------------------------------------------

def cmd_check_backlinks(args):
    """
    Scan all .md files under notes root + calendar root.
    Find all containing [[args.stem]]. Print file paths and count.
    Exit 0 (informational).
    """
    stem = args.stem
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else None

    utils.verbose(f"Searching for [[{stem}]] ...")
    matches = _files_referencing(stem, notes_dir)

    if matches:
        utils.log(f"Found {len(matches)} file(s) referencing [[{stem}]]:")
        for p in sorted(matches):
            utils.log(f"  {p}")
    else:
        utils.log(f"No files reference [[{stem}]]")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 3. cmd_check_emoji_mappings
# ---------------------------------------------------------------------------

def cmd_check_emoji_mappings(args):
    """
    Compare emoji mapping tables in CLAUDE.md against actual filesystem subdirs.

    Checks two sections:
      "## Workstream Emojis (Work Plans)"
        → actual dirs under Notes/🏢 ServiceNow/📆 Plans/
      "## Activity Emojis (Personal Plans)"
        → actual dirs under Notes/🏡 Personal/🏡📆 Plans/Present/

    Reports:
      - Dirs present on filesystem but absent from CLAUDE.md table
      - Table entries with no matching filesystem dir

    Exit 1 if mismatches, 0 if clean.
    """
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else utils.notes_root()

    try:
        claude_path = utils.noteplan_root() / "CLAUDE.md"
        claude_text = claude_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        utils.err(f"Cannot read CLAUDE.md: {e}")
        sys.exit(utils.EXIT_NOT_FOUND)

    work_plans_dir = notes_dir / "🏢 ServiceNow" / "📆 Plans"
    personal_plans_dir = notes_dir / "🏡 Personal" / "🏡📆 Plans" / "Present"

    work_dirs = _subdir_names(work_plans_dir)
    personal_dirs = _subdir_names(personal_plans_dir)

    work_table = _extract_emoji_table(claude_text, "## Workstream Emojis (Work Plans)")
    personal_table = _extract_emoji_table(claude_text, "## Activity Emojis (Personal Plans)")

    has_mismatch = False

    def _check_section(section_name: str, fs_dirs: list[str], table: dict[str, str]):
        nonlocal has_mismatch

        # Build a set of (name, emoji) from filesystem dirs
        fs_pairs = _dirs_to_name_emoji(fs_dirs)
        fs_names = {name for name, _ in fs_pairs}
        table_names = set(table.keys())

        in_fs_not_table = fs_names - table_names
        in_table_not_fs = table_names - fs_names

        utils.log(f"\n--- {section_name} ---")
        if not in_fs_not_table and not in_table_not_fs:
            utils.log("  ✓ No mismatches")
        else:
            has_mismatch = True
            if in_fs_not_table:
                utils.log(f"  Dirs on filesystem but NOT in CLAUDE.md table ({len(in_fs_not_table)}):")
                for name in sorted(in_fs_not_table):
                    # Find matching emoji from fs_pairs
                    emoji = next((e for n, e in fs_pairs if n == name), "?")
                    utils.log(f"    + {emoji} {name}")
            if in_table_not_fs:
                utils.log(f"  Table entries with NO matching filesystem dir ({len(in_table_not_fs)}):")
                for name in sorted(in_table_not_fs):
                    emoji = table.get(name, "?")
                    utils.log(f"    - {emoji} {name}")

    _check_section("Workstream Emojis (Work Plans)", work_dirs, work_table)
    _check_section("Activity Emojis (Personal Plans)", personal_dirs, personal_table)

    if has_mismatch:
        utils.log("\nRun 'sync-emoji-mappings' to update CLAUDE.md from filesystem.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    else:
        utils.log("\n✓ CLAUDE.md emoji tables match filesystem")
        sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 4. cmd_sync_emoji_mappings
# ---------------------------------------------------------------------------

def cmd_sync_emoji_mappings(args):
    """
    Rewrite the emoji mapping tables in CLAUDE.md to match actual filesystem dirs.

    Rewrites two sections:
      "## Workstream Emojis (Work Plans)"  ← from Notes/🏢 ServiceNow/📆 Plans/
      "## Activity Emojis (Personal Plans)" ← from Notes/🏡 Personal/🏡📆 Plans/Present/

    Prints what changed. Writes via utils.write_file.
    Exit 0.
    """
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else utils.notes_root()

    try:
        claude_path = utils.noteplan_root() / "CLAUDE.md"
        claude_text = claude_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        utils.err(f"Cannot read CLAUDE.md: {e}")
        sys.exit(utils.EXIT_NOT_FOUND)

    work_plans_dir = notes_dir / "🏢 ServiceNow" / "📆 Plans"
    personal_plans_dir = notes_dir / "🏡 Personal" / "🏡📆 Plans" / "Present"

    work_dirs = _subdir_names(work_plans_dir)
    personal_dirs = _subdir_names(personal_plans_dir)

    def _rebuild_section(text: str, section_header: str, fs_dirs: list[str]) -> tuple[str, bool]:
        """
        Replace the table in section_header with a freshly built one from fs_dirs.
        Returns (new_text, changed_bool).
        """
        pairs = _dirs_to_name_emoji(fs_dirs)  # [(name, emoji), ...]
        new_table = _build_table_rows_2col(
            [(name, emoji) for name, emoji in pairs],
            col1="Workstream" if "Workstream" in section_header else "Activity",
            col2="Emoji",
        )

        lines = text.splitlines(keepends=True)
        start, end = _find_section_lines(text, section_header)
        if start == -1:
            utils.verbose(f"  Section '{section_header}' not found in CLAUDE.md — skipping")
            return text, False

        # Find the table within [start, end)
        section_text_lines = [l.rstrip('\n') for l in lines[start:end]]

        # Locate table start and end within the section
        table_start_rel = -1
        table_end_rel = len(section_text_lines)
        for i, line in enumerate(section_text_lines):
            if _TABLE_ROW_RE.match(line.strip()):
                if table_start_rel == -1:
                    table_start_rel = i
            elif table_start_rel != -1 and not _TABLE_ROW_RE.match(line.strip()):
                table_end_rel = i
                break

        if table_start_rel == -1:
            utils.verbose(f"  No table found under '{section_header}' — skipping")
            return text, False

        # Reconstruct section lines
        before_table = section_text_lines[:table_start_rel]
        after_table = section_text_lines[table_end_rel:]

        old_table_lines = section_text_lines[table_start_rel:table_end_rel]
        new_table_lines = new_table.splitlines()

        changed = old_table_lines != new_table_lines

        if not changed:
            return text, False

        new_section_lines = before_table + new_table_lines + ([""] if after_table else []) + after_table

        # Replace lines[start:end] with new_section_lines
        # Reconstruct full text
        before_section = lines[:start]
        after_section = lines[end:]

        # Determine line ending from original
        le = "\n"
        new_content = (
            "".join(before_section)
            + "\n".join(new_section_lines)
            + "\n"
            + "".join(after_section)
        )
        return new_content, True

    updated_text, work_changed = _rebuild_section(
        claude_text, "## Workstream Emojis (Work Plans)", work_dirs
    )
    updated_text2, personal_changed = _rebuild_section(
        updated_text, "## Activity Emojis (Personal Plans)", personal_dirs
    )

    if not work_changed and not personal_changed:
        utils.log("✓ CLAUDE.md emoji tables already match filesystem — no changes needed")
        sys.exit(utils.EXIT_OK)

    if work_changed:
        utils.log(f"Workstream table updated from {len(work_dirs)} dirs in {work_plans_dir.name}")
    if personal_changed:
        utils.log(f"Activity table updated from {len(personal_dirs)} dirs in {personal_plans_dir.name}")

    utils.write_file(claude_path, updated_text2)
    utils.log("✓ CLAUDE.md written")
    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 5. cmd_check_living_artifacts
# ---------------------------------------------------------------------------

def cmd_check_living_artifacts(args):
    """
    Context-aware checker that lists living documents that may need updating.

    Two modes:
      --after-rename OLD NEW  — list files referencing [[OLD]], remind about CLAUDE.md
      --after-new-plan STEM   — remind about CLAUDE.md, Note Map, reference lists

    Always checks whether CLAUDE.md and Note Map exist and mentions them.
    Exit 0 (informational).
    """
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else None
    nr = notes_dir or utils.notes_root()

    # Locate living artifacts
    try:
        claude_path = utils.noteplan_root() / "CLAUDE.md"
        claude_exists = claude_path.exists()
    except FileNotFoundError:
        claude_path = None
        claude_exists = False

    note_map_path = nr / "🗺️ Note Map.md"
    note_map_exists = note_map_path.exists()

    utils.log("=" * 60)
    utils.log("Living Artifact Checklist")
    utils.log("=" * 60)

    after_rename = getattr(args, 'after_rename', None)
    after_new_plan = getattr(args, 'after_new_plan', None)

    if after_rename:
        old_stem, new_stem = after_rename
        utils.log(f"\nMode: after-rename  {old_stem!r} → {new_stem!r}")

        # Find files referencing old stem
        utils.log(f"\n[1] Files referencing [[{old_stem}]] (need backlink update):")
        refs = _files_referencing(old_stem, notes_dir)
        if refs:
            for p in sorted(refs):
                utils.log(f"    {p}")
            utils.log(f"\n  → Run: noteplan-sweep update-backlinks --old-stem {old_stem!r} --new-stem {new_stem!r}")
        else:
            utils.log(f"    (none found — [[{old_stem}]] not referenced anywhere)")

        # CLAUDE.md
        utils.log(f"\n[2] CLAUDE.md {'✓ exists' if claude_exists else '✗ not found'}:")
        if claude_exists:
            utils.log(f"    {claude_path}")
            utils.log( "    Check if renamed file was a plan dir → run: noteplan-sweep sync-emoji-mappings")
        else:
            utils.log("    (CLAUDE.md not found — skipping)")

        # Note Map
        utils.log(f"\n[3] Note Map {'✓ exists' if note_map_exists else '✗ not found'}:")
        if note_map_exists:
            utils.log(f"    {note_map_path}")
            utils.log( "    If the rename changed directory structure → run: noteplan-sweep sync-note-map")
        else:
            utils.log("    (Note Map not found — skipping)")

    elif after_new_plan:
        stem = after_new_plan
        utils.log(f"\nMode: after-new-plan  stem={stem!r}")

        # CLAUDE.md
        utils.log(f"\n[1] CLAUDE.md {'✓ exists' if claude_exists else '✗ not found'}:")
        if claude_exists:
            utils.log(f"    {claude_path}")
            utils.log( "    If this plan created a NEW workstream dir → run: noteplan-sweep sync-emoji-mappings")
            utils.log( "    Then verify emoji table accuracy:          run: noteplan-sweep check-emoji-mappings")
        else:
            utils.log("    (CLAUDE.md not found — skipping)")

        # Note Map
        utils.log(f"\n[2] Note Map {'✓ exists' if note_map_exists else '✗ not found'}:")
        if note_map_exists:
            utils.log(f"    {note_map_path}")
            utils.log( "    If this plan added a new folder → run: noteplan-sweep sync-note-map")
        else:
            utils.log("    (Note Map not found — skipping)")

        # Relevant reference lists
        utils.log(f"\n[3] Reference lists to consider updating:")
        utils.log(f"    - 🏡📋 References.md  (if this plan links external resources)")
        utils.log(f"    - 🏢📋 References.md  (if a work plan with external links)")
        utils.log(f"    - Any backlog or index file relevant to this workstream")

    else:
        utils.log("\nNo mode specified. Use --after-rename OLD NEW or --after-new-plan STEM")
        utils.log("\nLiving artifacts in this vault:")
        if claude_exists:
            utils.log(f"  CLAUDE.md      : {claude_path}")
        else:
            utils.log(f"  CLAUDE.md      : NOT FOUND")
        if note_map_exists:
            utils.log(f"  Note Map       : {note_map_path}")
        else:
            utils.log(f"  Note Map       : NOT FOUND")

    utils.log("\n" + "=" * 60)
    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 6. cmd_check_note_map
# ---------------------------------------------------------------------------

# Header marking the auto-generated folder tree section in Note Map
_NOTE_MAP_TREE_HEADER = "## Top-Level Structure"


def _get_top_level_dirs(notes_root: Path, depth: int = 2) -> list[str]:
    """
    Return a sorted list of directory paths (relative to notes_root) up to `depth`
    levels deep. Excludes @Backup. Format: "DirName" or "DirName/SubDir".
    """
    result = []
    if not notes_root.exists():
        return result
    for entry in sorted(notes_root.iterdir()):
        if not entry.is_dir():
            continue
        if "@Backup" in entry.name:
            continue
        result.append(entry.name)
        if depth >= 2:
            for sub in sorted(entry.iterdir()):
                if sub.is_dir() and "@Backup" not in sub.name:
                    result.append(f"{entry.name}/{sub.name}")
    return result


def _extract_dirs_from_note_map(text: str) -> set[str]:
    """
    Extract top-level directory names mentioned in the Note Map's Top-Level Structure
    table.  Only rows from the table under '## Top-Level Structure' are considered.

    The table has columns like:
      | Namespace | Folder | Purpose | Subfolders |
    We look for the Folder column value, which is a backtick-quoted name like
    `🏢 ServiceNow`.  We also look for @-prefixed special dirs mentioned explicitly
    in the section text.
    """
    found = set()

    # Locate the Top-Level Structure section
    start, end = _find_section_lines(text, _NOTE_MAP_TREE_HEADER)
    if start == -1:
        # Fallback: search entire document for table rows with backtick folder names
        section_text = text
    else:
        lines = text.splitlines()
        section_text = "\n".join(lines[start:end])

    # Match backtick-quoted names that look like top-level directory names.
    # Top-level dirs either:
    #   - Start with an emoji character (non-ASCII, codepoint >= 0x100)
    #   - Start with @ (special system dirs)
    #   - Are plain word names without path separators
    # Exclude anything containing / \ $ ~ ( ) = : or newlines.
    pattern = re.compile(r'`([^`\n/\\$~()=:]+)`')
    for m in pattern.finditer(section_text):
        val = m.group(1).strip()
        if not val:
            continue
        # Must start with emoji or @, and not contain pipe or spaces at start
        first = val[0]
        first_cp = ord(first)
        is_emoji_start = first_cp > 0x2000
        is_at_start = first == "@"
        if (is_emoji_start or is_at_start) and len(val) >= 2:
            # Exclude multi-token table cell content (contains | or newline)
            if "|" not in val:
                found.add(val)

    # Also capture @-prefixed dirs mentioned in prose (not just backticks)
    for m in re.finditer(r'`(@\w+)`', section_text):
        found.add(m.group(1))

    return found


def cmd_check_note_map(args):
    """
    Find 🗺️ Note Map.md under notes root. Read it.
    Compare top-2-level directory structure against actual filesystem.
    Report dirs in filesystem but missing from Note Map, and vice versa.
    Exit 1 if mismatches, 0 if clean.
    """
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else utils.notes_root()

    note_map_path = notes_dir / "🗺️ Note Map.md"
    if not note_map_path.exists():
        utils.err(f"Note Map not found at {note_map_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    note_map_text = note_map_path.read_text(encoding="utf-8")

    # Get actual top-level dirs (1 level only for the note map comparison)
    actual_top_dirs = set()
    for entry in notes_dir.iterdir():
        if entry.is_dir() and "@Backup" not in entry.name:
            actual_top_dirs.add(entry.name)

    # Extract dirs mentioned in Note Map
    map_dirs = _extract_dirs_from_note_map(note_map_text)

    # Intersect: find which actual dirs are mentioned vs not
    in_fs_not_map = actual_top_dirs - map_dirs
    in_map_not_fs = {d for d in map_dirs if d not in actual_top_dirs and not d.startswith("$")}

    has_mismatch = bool(in_fs_not_map or in_map_not_fs)

    utils.log(f"Note Map: {note_map_path}")
    utils.log(f"Actual top-level dirs: {len(actual_top_dirs)}")
    utils.log(f"Dirs mentioned in Note Map: {len(map_dirs)}")

    if in_fs_not_map:
        utils.log(f"\nDirs on filesystem but NOT mentioned in Note Map ({len(in_fs_not_map)}):")
        for d in sorted(in_fs_not_map):
            utils.log(f"  + {d}")

    if in_map_not_fs:
        utils.log(f"\nNote Map entries with NO matching filesystem dir ({len(in_map_not_fs)}):")
        for d in sorted(in_map_not_fs):
            utils.log(f"  - {d}")

    if not has_mismatch:
        utils.log("\n✓ Note Map top-level dirs match filesystem")
        sys.exit(utils.EXIT_OK)
    else:
        utils.log("\nRun 'sync-note-map' to rebuild the folder tree in Note Map.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)


# ---------------------------------------------------------------------------
# 7. cmd_sync_note_map
# ---------------------------------------------------------------------------

def _build_folder_tree(notes_root: Path, depth: int = 2) -> str:
    """
    Build a markdown tree of directories under notes_root up to `depth` levels.
    Returns a markdown list string.
    """
    lines = []

    def _recurse(path: Path, current_depth: int, indent: str):
        entries = sorted(
            [e for e in path.iterdir() if e.is_dir() and "@Backup" not in e.name],
            key=lambda e: e.name,
        )
        for entry in entries:
            lines.append(f"{indent}- `{entry.name}`")
            if current_depth < depth:
                _recurse(entry, current_depth + 1, indent + "  ")

    _recurse(notes_root, 1, "")
    return "\n".join(lines)


def cmd_sync_note_map(args):
    """
    Rebuild the folder tree section in Note Map from actual filesystem.

    Finds the ## Top-Level Structure section and replaces the table/content
    within it with a fresh directory tree (up to 2 levels deep).
    Writes via utils.write_file. Prints what changed.
    Exit 0.
    """
    notes_dir = Path(args.notes_dir) if (hasattr(args, 'notes_dir') and args.notes_dir) else utils.notes_root()

    note_map_path = notes_dir / "🗺️ Note Map.md"
    if not note_map_path.exists():
        utils.err(f"Note Map not found at {note_map_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    note_map_text = note_map_path.read_text(encoding="utf-8")

    # Build fresh tree
    tree_md = _build_folder_tree(notes_dir, depth=2)

    # Find Top-Level Structure section bounds
    lines = note_map_text.splitlines(keepends=True)
    start, end = _find_section_lines(note_map_text, _NOTE_MAP_TREE_HEADER)

    if start == -1:
        # Append at end of file
        utils.log(f"Section '{_NOTE_MAP_TREE_HEADER}' not found — appending at end of Note Map")
        new_section = f"\n## Top-Level Structure\n\n{tree_md}\n"
        new_text = note_map_text.rstrip("\n") + new_section
        utils.write_file(note_map_path, new_text)
        utils.log("✓ Note Map updated (section appended)")
        sys.exit(utils.EXIT_OK)

    # Extract the existing section content (between header and next header)
    # We preserve the header line and any frontmatter/description lines immediately after it,
    # then replace everything until the next `---` or next `##` header.
    section_lines = [l.rstrip('\n') for l in lines[start:end]]

    # Keep only the header line; replace everything else with fresh tree
    header_line = section_lines[0]

    # Check for an existing description line (non-table, non-list line right after header)
    description_lines = []
    i = 1
    while i < len(section_lines):
        line = section_lines[i].strip()
        if line.startswith("|") or line.startswith("-") or line.startswith("#") or line == "---":
            break
        description_lines.append(section_lines[i])
        i += 1

    new_section_lines = [header_line] + description_lines + ["", tree_md, ""]

    # Reconstruct
    before = "".join(lines[:start])
    after = "".join(lines[end:])
    new_text = before + "\n".join(new_section_lines) + "\n" + after

    old_section_text = "\n".join(section_lines)
    new_section_text = "\n".join(new_section_lines)

    if old_section_text == new_section_text:
        utils.log("✓ Note Map folder tree already up to date — no changes needed")
        sys.exit(utils.EXIT_OK)

    # Count top-level dirs
    top_count = sum(
        1 for e in notes_dir.iterdir()
        if e.is_dir() and "@Backup" not in e.name
    )
    utils.log(f"Rebuilding Note Map folder tree from {top_count} top-level dirs ...")
    utils.write_file(note_map_path, new_text)
    utils.log("✓ Note Map written")
    sys.exit(utils.EXIT_OK)
