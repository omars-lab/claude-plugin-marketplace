"""
link_repair.py — Wikilink + heading repair commands for noteplan-sweep CLI.

Commands
--------
fix-links   Repair [[wikilinks]] (and [[Stem#Heading]] anchors) after file
            renames. Can auto-detect renames from git status or accept an
            explicit old→new stem pair. Also fixes the H1 heading in the
            renamed file to match the new stem (Golden Rule: filename = H1).
"""

import re
import subprocess
import sys
from pathlib import Path

import noteplan_sweep.utils as utils

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

# git status --porcelain lines that represent renames: "R  old -> new"
_GIT_RENAME_RE = re.compile(r'^R[M ]?\s+"?(.+?)"?\s+->\s+"?(.+?)"?$')

# Matches [[Stem]], [[Stem#Heading]], [[Stem|Alias]], [[Stem#Heading|Alias]]
# Groups: (1) stem  (2) #heading or ""  (3) |alias or ""
_WIKILINK_RE = re.compile(r'\[\[([^\]#|]+)(#[^\]|]+)?(\|[^\]]+)?\]\]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _replace_wikilinks(text: str, old_stem: str, new_stem: str) -> str:
    """
    Replace all ``[[old_stem…]]`` wikilinks with ``[[new_stem…]]``,
    preserving ``#heading`` anchors and ``|alias`` display text.
    """
    def replacer(m: re.Match) -> str:
        stem = m.group(1)
        heading = m.group(2) or ""
        alias = m.group(3) or ""
        if stem.strip() == old_stem:
            return f"[[{new_stem}{heading}{alias}]]"
        return m.group(0)
    return _WIKILINK_RE.sub(replacer, text)


def _fix_h1(path: Path, new_stem: str, dry_run: bool) -> bool:
    """
    If the file's H1 heading does not match *new_stem*, update it.
    Returns True if a change was (or would be) made.
    """
    text = utils.read_file(path)
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if line.rstrip("\n") != f"# {new_stem}":
                lines[i] = f"# {new_stem}\n"
                if not dry_run:
                    utils.write_file(path, "".join(lines))
                return True
            return False
    return False


# ---------------------------------------------------------------------------
# Command implementation
# ---------------------------------------------------------------------------

def cmd_fix_links(args):
    """
    Repair ``[[wikilinks]]`` and ``[[Stem#Heading]]`` anchors after file renames.

    Usage
    -----
    noteplan-sweep fix-links --from-git-renames [notes_root]
        Auto-detect renames from ``git status --porcelain`` and update every
        ``[[old_stem…]]`` reference across all .md files in *notes_root*.

    noteplan-sweep fix-links OLD_STEM NEW_STEM [notes_root]
        Explicit rename: update ``[[OLD_STEM…]]`` → ``[[NEW_STEM…]]``.

    In both modes:
    - ``[[Stem#Heading]]`` anchors are updated (stem part only; heading preserved).
    - The renamed file's H1 is updated to match the new stem if it differs.
    - ``--dry-run`` shows what would change without writing.

    Exits 0 always (errors are printed to stderr).
    """
    notes_root = Path(getattr(args, "notes_root", None) or ".").resolve()
    dry_run = utils.DRY_RUN
    pairs: list[tuple[str, str]] = []

    if getattr(args, "from_git_renames", False):
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
                cwd=notes_root,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            utils.err(f"git status failed: {exc}")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)

        for line in r.stdout.splitlines():
            m = _GIT_RENAME_RE.match(line)
            if m:
                old_stem = Path(m.group(1)).stem
                new_stem = Path(m.group(2)).stem
                if old_stem != new_stem:
                    pairs.append((old_stem, new_stem))

        if not pairs:
            utils.log("No renames detected in git status.")
            sys.exit(utils.EXIT_OK)

    else:
        old_stem = getattr(args, "old_stem", None)
        new_stem = getattr(args, "new_stem", None)
        if not old_stem or not new_stem:
            utils.err("Provide OLD_STEM NEW_STEM or use --from-git-renames.")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)
        pairs = [(old_stem, new_stem)]

    all_md = list(notes_root.rglob("*.md"))
    total_files_changed = 0

    for old_stem, new_stem in pairs:
        files_changed = 0
        for md in all_md:
            text = utils.read_file(md)
            new_text = _replace_wikilinks(text, old_stem, new_stem)
            if new_text != text:
                files_changed += 1
                total_files_changed += 1
                if dry_run:
                    utils.log(f"  [dry-run] would update wikilinks in {md.name}")
                else:
                    utils.write_file(md, new_text)

        # Fix H1 in the renamed file itself
        renamed_file = next(notes_root.rglob(f"{new_stem}.md"), None)
        if renamed_file:
            changed = _fix_h1(renamed_file, new_stem, dry_run)
            if changed:
                if dry_run:
                    utils.log(f"  [dry-run] would fix H1 in {renamed_file.name}")
                else:
                    utils.log(f"  Fixed H1 in {renamed_file.name}")

        dry_label = " (dry-run)" if dry_run else ""
        utils.log(
            f"  [[{old_stem}]] → [[{new_stem}]]{dry_label}: "
            f"{files_changed} file(s) updated"
        )

    utils.log(f"\nfix-links: {len(pairs)} rename(s), {total_files_changed} file(s) touched")
    sys.exit(utils.EXIT_OK)
