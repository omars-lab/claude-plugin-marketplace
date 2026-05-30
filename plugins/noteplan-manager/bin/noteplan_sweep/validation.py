"""
validation.py — Validation and repair commands (Phase D) for noteplan-sweep CLI.

Commands:
  check-source-clean          Verify no open tasks remain in a source note
  check-section-exists        Confirm a section header is present in a file
  check-date-tags             Report >YYYYMMDD date tags (no hyphens) in a file
  fix-date-tags               Rewrite >YYYYMMDD → >YYYY-MM-DD in a file
  check-wikilinks             Find [[Stem]] refs that don't resolve to any .md
  check-backlinks             Report all files referencing [[stem]]
  check-frontmatter           Validate frontmatter fields, delimiter, date formats
  fix-frontmatter-delimiters  Replace -- frontmatter delimiters with ---
"""

import re
import sys
from pathlib import Path

import noteplan_sweep.utils as utils

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Open task: `- [ ]` or `* [ ]` at any indent level
_OPEN_TASK_RE = re.compile(r'^(\s*)[-*] \[ \]', re.MULTILINE)

# Date tag without hyphens: >YYYYMMDD (8 consecutive digits after >)
_DATE_TAG_RE = re.compile(r'>(\d{8})\b')

# Date tag with exactly YYYYMMDD structure (4+2+2), no hyphens, to replace
_DATE_TAG_FIX_RE = re.compile(r'>(\d{4})(\d{2})(\d{2})\b')

# Wikilinks: [[StemName]]
_WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


# ---------------------------------------------------------------------------
# 1. cmd_check_source_clean
# ---------------------------------------------------------------------------

def cmd_check_source_clean(args):
    """
    Read args.file. Scan for any open task lines (- [ ] or * [ ] at any indent).
    If found, print each with its line number and exit 1.
    If none found, print "✓ source is clean" and exit 0.
    """
    path = Path(args.file)
    text = utils.read_file(path)
    lines = text.splitlines()

    open_tasks = []
    for lineno, line in enumerate(lines, start=1):
        if re.match(r'^\s*[-*] \[ \]', line):
            open_tasks.append((lineno, line))

    if open_tasks:
        utils.log(f"Open tasks found in {path.name} ({len(open_tasks)} total):")
        for lineno, line in open_tasks:
            utils.log(f"  L{lineno}: {line}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    else:
        utils.log("✓ source is clean")
        sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 2. cmd_check_section_exists
# ---------------------------------------------------------------------------

def cmd_check_section_exists(args):
    """
    Read args.file. Check whether args.section_header appears as a standalone line.
    Print found/not-found. Exit 0 if found, exit 2 if not found.
    """
    path = Path(args.file)
    header = args.section_header
    text = utils.read_file(path)

    # Look for the header as a complete line (exact match)
    found = False
    for line in text.splitlines():
        if line == header:
            found = True
            break

    if found:
        utils.log(f"✓ section found: {header}")
        sys.exit(utils.EXIT_OK)
    else:
        utils.log(f"✗ section not found: {header}")
        sys.exit(utils.EXIT_NOT_FOUND)


# ---------------------------------------------------------------------------
# 3. cmd_check_date_tags
# ---------------------------------------------------------------------------

def cmd_check_date_tags(args):
    """
    Read args.file. Find all >YYYYMMDD patterns (8-digit dates, no hyphens, after >).
    Print each with its line number.
    Exit 1 if any found (needs fixing), 0 if clean.
    """
    path = Path(args.file)
    text = utils.read_file(path)
    lines = text.splitlines()

    hits = []
    for lineno, line in enumerate(lines, start=1):
        for m in _DATE_TAG_RE.finditer(line):
            hits.append((lineno, m.group(0), line.strip()))

    if hits:
        utils.log(f"Found {len(hits)} unhyphenated date tag(s) in {path.name}:")
        for lineno, tag, line in hits:
            utils.log(f"  L{lineno}: {tag}  →  {line}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    else:
        utils.log("✓ no bare date tags found")
        sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 4. cmd_fix_date_tags
# ---------------------------------------------------------------------------

def cmd_fix_date_tags(args):
    """
    Read args.file. Replace all >YYYYMMDD patterns with >YYYY-MM-DD.
    Print count of replacements. Write back via utils.write_file.
    Exit 0 always.
    """
    path = Path(args.file)
    text = utils.read_file(path)

    count = [0]

    def _replacer(m):
        count[0] += 1
        y, mo, d = m.group(1), m.group(2), m.group(3)
        old = f">{y}{mo}{d}"
        new = f">{y}-{mo}-{d}"
        utils.verbose(f"  {old} → {new}")
        return new

    new_text = _DATE_TAG_FIX_RE.sub(_replacer, text)

    n = count[0]
    if n == 0:
        utils.log("✓ no date tags to fix")
    else:
        utils.log(f"Fixed {n} date tag(s) in {path.name}")
        utils.write_file(path, new_text)

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 5. cmd_check_wikilinks
# ---------------------------------------------------------------------------

def cmd_check_wikilinks(args):
    """
    Read args.file. Extract all [[StemName]] references.
    For each, search for a file with that stem anywhere under args.notes_dir
    (or utils.notes_root()). Also checks the Calendar root.
    Report broken (unresolved) links. Exit 1 if any broken, 0 if all resolve.
    """
    path = Path(args.file)
    text = utils.read_file(path)

    # Determine search roots
    if hasattr(args, 'notes_dir') and args.notes_dir:
        notes_dir = Path(args.notes_dir)
    else:
        notes_dir = utils.notes_root()

    # Also include Calendar root for date notes like [[20260410]]
    try:
        calendar_dir = utils.calendar_root()
    except FileNotFoundError:
        calendar_dir = None

    # Build stem → path index (case-insensitive stem comparison)
    utils.verbose(f"Building wikilink index under {notes_dir} ...")
    stem_index: dict[str, list[Path]] = {}

    search_roots = [notes_dir]
    if calendar_dir and calendar_dir.exists():
        search_roots.append(calendar_dir)

    for root in search_roots:
        for md_file in root.rglob("*.md"):
            if "@Backup" in str(md_file):
                continue
            stem = md_file.stem
            key = stem.casefold()
            stem_index.setdefault(key, []).append(md_file)

    # Extract all wikilinks from the file
    stems_in_file = _WIKILINK_RE.findall(text)
    if not stems_in_file:
        utils.log("✓ no wikilinks found in file")
        sys.exit(utils.EXIT_OK)

    # Deduplicate while preserving order
    seen = set()
    unique_stems = []
    for s in stems_in_file:
        # Strip display alias: [[Stem|Alias]] → Stem
        stem = s.split("|")[0].strip()
        if stem not in seen:
            seen.add(stem)
            unique_stems.append(stem)

    broken = []
    resolved = []
    for stem in unique_stems:
        key = stem.casefold()
        if key in stem_index:
            matches = stem_index[key]
            utils.verbose(f"  ✓ [[{stem}]] → {matches[0]}")
            resolved.append(stem)
        else:
            broken.append(stem)

    utils.log(f"Checked {len(unique_stems)} wikilink(s): {len(resolved)} resolved, {len(broken)} broken")

    if broken:
        utils.log("Broken links:")
        for stem in broken:
            utils.log(f"  [[{stem}]]")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    else:
        utils.log("✓ all wikilinks resolve")
        sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 6. cmd_check_backlinks
# ---------------------------------------------------------------------------

def cmd_check_backlinks(args):
    """
    Scan all .md files under args.notes_dir (or utils.notes_root()).
    Find all that contain [[{args.stem}]]. Print file paths.
    Exit 0 always (informational).
    """
    stem = args.stem

    if hasattr(args, 'notes_dir') and args.notes_dir:
        notes_dir = Path(args.notes_dir)
    else:
        notes_dir = utils.notes_root()

    # Also scan Calendar for completeness
    try:
        calendar_dir = utils.calendar_root()
    except FileNotFoundError:
        calendar_dir = None

    pattern = f"[[{stem}]]"
    utils.verbose(f"Searching for {pattern!r} under {notes_dir} ...")

    matches = []
    search_roots = [notes_dir]
    if calendar_dir and calendar_dir.exists():
        search_roots.append(calendar_dir)

    for root in search_roots:
        for md_file in root.rglob("*.md"):
            if "@Backup" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                utils.verbose(f"  skipping unreadable: {md_file}")
                continue
            if pattern in content:
                matches.append(md_file)

    if matches:
        utils.log(f"Found {len(matches)} file(s) referencing [[{stem}]]:")
        for p in sorted(matches):
            utils.log(f"  {p}")
    else:
        utils.log(f"No files reference [[{stem}]]")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 7. cmd_check_frontmatter
# ---------------------------------------------------------------------------

def cmd_check_frontmatter(args):
    """
    Import and use frontmatter.parse() and frontmatter.validate() from the
    existing frontmatter.py library. Add the library's directory to sys.path
    before importing. Print validation results. Exit 1 if invalid, 0 if valid.
    """
    _ensure_frontmatter_on_path()
    import frontmatter  # noqa: PLC0415

    path = Path(args.file)
    text = utils.read_file(path)
    filepath_str = str(path)

    fm = frontmatter.parse(text, filepath=filepath_str)

    # Template files are skipped
    if fm.is_ejs_template:
        utils.log(f"✓ {path.name}: EJS template file — skipped")
        sys.exit(utils.EXIT_OK)

    if fm.delimiter is None:
        utils.log(f"✓ {path.name}: no frontmatter block — skipped")
        sys.exit(utils.EXIT_OK)

    vr = frontmatter.validate(fm, filepath=filepath_str)

    if vr.valid:
        utils.log(f"✓ {path.name}: frontmatter valid (schema: {vr.schema})")
        if vr.warnings:
            for w in vr.warnings:
                utils.log(f"  warning: {w}")
        sys.exit(utils.EXIT_OK)
    else:
        utils.log(f"✗ {path.name}: frontmatter invalid (schema: {vr.schema})")
        if vr.missing:
            utils.log(f"  missing fields: {', '.join(vr.missing)}")
        if vr.bad_values:
            for field, reason in vr.bad_values.items():
                utils.log(f"  bad value [{field}]: {reason}")
        if vr.warnings:
            for w in vr.warnings:
                utils.log(f"  warning: {w}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)


# ---------------------------------------------------------------------------
# 8. cmd_fix_frontmatter_delimiters
# ---------------------------------------------------------------------------

def cmd_fix_frontmatter_delimiters(args):
    """
    Read args.file. If frontmatter uses -- delimiters (exactly two dashes, not
    three), replace the opening and closing delimiter lines with ---.
    Be careful: only the opening line and matching closing delimiter line are
    replaced — not any -- that appears inside body content.
    Print what was changed. Write back via utils.write_file. Exit 0.
    """
    path = Path(args.file)
    text = utils.read_file(path)

    # Check if it starts with a -- block (exactly two dashes, not ---+)
    # We match: ^--\n ... \n--\n? to find the frontmatter block
    # Pattern: line that is exactly "--" (two dashes, nothing else)
    _FM_DOUBLE_DASH_RE = re.compile(
        r'^(--)\n(.*?)\n(--)\s*$',
        re.DOTALL | re.MULTILINE
    )

    # More precise: match only if the opening line is EXACTLY "--" (not "---")
    # and there is a matching closing "--" line
    if not text.startswith("--\n") or text.startswith("---\n"):
        utils.log(f"✓ {path.name}: no -- delimiters to fix (already uses --- or no frontmatter)")
        sys.exit(utils.EXIT_OK)

    # Find the closing -- delimiter: scan lines for the first standalone "--"
    lines = text.splitlines(keepends=True)

    # Line 0 is the opening "--\n"
    # Find closing "--" line (exact match, possibly with trailing whitespace)
    closing_idx = None
    for i in range(1, len(lines)):
        stripped = lines[i].rstrip('\n').rstrip()
        if stripped == '--':
            closing_idx = i
            break
        # Stop if we hit something that looks like body content after a longer block
        # (don't scan the whole file — frontmatter should be near the top)
        if i > 50:
            break

    if closing_idx is None:
        utils.log(f"✓ {path.name}: opening -- found but no matching closing -- within first 50 lines — skipping")
        sys.exit(utils.EXIT_OK)

    # Replace opening delimiter
    old_opening = lines[0]
    lines[0] = lines[0].replace('--\n', '---\n', 1)

    # Replace closing delimiter (preserve trailing newline)
    old_closing = lines[closing_idx]
    closing_content = lines[closing_idx].rstrip('\n').rstrip()
    trailing = lines[closing_idx][len(closing_content):]  # newline or empty
    lines[closing_idx] = '---' + trailing

    new_text = ''.join(lines)

    utils.log(f"Fixed frontmatter delimiters in {path.name}: -- → ---"
              f" (opening line {1}, closing line {closing_idx + 1})")
    utils.verbose(f"  opening:  {old_opening.rstrip()!r} → {lines[0].rstrip()!r}")
    utils.verbose(f"  closing:  {old_closing.rstrip()!r} → {lines[closing_idx].rstrip()!r}")

    utils.write_file(path, new_text)
    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_LIB_PATH: Path | None = None


def _ensure_frontmatter_on_path():
    """
    Add the directory containing frontmatter.py to sys.path if not already present.
    Resolves the canonical location relative to the plugin layout:
      plugins/noteplan-manager/skills/manage-frontmatter/fix-frontmatter/scripts/frontmatter.py
    Raises FileNotFoundError if the library cannot be located.
    """
    global _FRONTMATTER_LIB_PATH

    if _FRONTMATTER_LIB_PATH is not None:
        # Already found; ensure it's still on path
        lib_dir = str(_FRONTMATTER_LIB_PATH)
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        return

    # Derive from this file's location:
    # noteplan_sweep/ is under plugins/noteplan-manager/bin/
    # frontmatter.py is under plugins/noteplan-manager/skills/manage-frontmatter/fix-frontmatter/scripts/
    this_dir = Path(__file__).resolve().parent          # .../bin/noteplan_sweep
    plugin_root = this_dir.parent.parent                # .../plugins/noteplan-manager
    candidate = (plugin_root
                 / "skills"
                 / "manage-frontmatter"
                 / "fix-frontmatter"
                 / "scripts")

    if (candidate / "frontmatter.py").exists():
        _FRONTMATTER_LIB_PATH = candidate
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        utils.verbose(f"frontmatter lib loaded from {candidate}")
        return

    # Fallback: search upward from plugin_root for the scripts dir
    for ancestor in [plugin_root] + list(plugin_root.parents)[:3]:
        alt = (ancestor
               / "plugins"
               / "noteplan-manager"
               / "skills"
               / "manage-frontmatter"
               / "fix-frontmatter"
               / "scripts")
        if (alt / "frontmatter.py").exists():
            _FRONTMATTER_LIB_PATH = alt
            if str(alt) not in sys.path:
                sys.path.insert(0, str(alt))
            utils.verbose(f"frontmatter lib loaded from {alt} (fallback)")
            return

    raise FileNotFoundError(
        "Cannot locate frontmatter.py. Expected at: "
        f"{candidate}/frontmatter.py"
    )
