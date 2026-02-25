---
name: fix-frontmatter
description: Validate and fix frontmatter across all NotePlan note types (plans, meetings, questions, ideas, thoughts, habits) using Python tooling with parse → fix → re-validate roundtrip
---

# Fix Frontmatter

You are a NotePlan frontmatter fixer. This skill validates and corrects frontmatter across **all note types** — not just plans. It uses Python scripts for reliable parse → validate → fix → re-validate roundtrips.

## What This Skill Does

1. **Selects scope** (all notes, plans only, single directory, or single file)
2. **Pre-commit checkpoint** — clean baseline for diff validation
3. **Checks frontmatter** via `check_frontmatter.py` — collects issues report
4. **Presents findings** — user approves before any writes
5. **Fixes frontmatter** via `fix_frontmatter.py` — infers missing fields, corrects delimiter
6. **Re-validates** — `check_frontmatter.py` must return `[]` (empty)
7. **Commits** with descriptive message

## Scripts Location

```bash
SCRIPTS_DIR="$HOME/.claude/plugins/noteplan-manager/skills/fix-frontmatter/scripts"
```

Five scripts:

| Script | Purpose |
|---|---|
| `frontmatter.py` | Core library — imported by all other scripts |
| `check_frontmatter.py` | Validate real note files (plans, meetings, etc.) |
| `fix_frontmatter.py` | Fix real note files in place, then re-validate |
| `check_templates.py` | Validate `@Templates/` EJS frontmatter blocks |
| `fix_templates.py` | Report unfixable issues in `@Templates/` EJS blocks (manual action required) |

## Frontmatter Schemas

**Real note files** use `---` (triple dash) delimiters — standard YAML.

| doctype | Notes | Required fields | Date format |
|---|---|---|---|
| `📆` Plan | `🏢` namespace | `doctype`, `status`, `started`, `namespace`, `workstream` | `YYYY-MM-DD` |
| `📆` Plan | `🏡` namespace | `doctype`, `status`, `started`, `namespace`, `plantype` | `YYMMDD` |
| `🗒️` Meeting | `🏢` namespace | `doctype`, `started`, `namespace` | `YYMMDD` |
| `💡` Idea | `🏡` namespace | `doctype`, `started`, `namespace` | `YYMMDD` |
| `🧠` Thought | `🏡` namespace | `doctype`, `started`, `namespace`, `plantype` | `YYMMDD` |
| `❓` Question | any | `doctype`, `asked` | `YYYY-MM-DD` |

**Template files** (`@Templates/*.md`) have a two-section structure:
- **`---` outer block**: NotePlan template metadata (`title`, `type: empty-note`) — standard YAML, skip entirely.
- **`--` inner block**: EJS frontmatter template with `<%- field %>` placeholders. Uses `--` intentionally — this is EJS source code, not YAML. **Do not validate or modify.**

When a template creates a note, the EJS block is evaluated and written to the new file as `---` YAML. `fix-frontmatter` does **not** target `@Templates/` — those files are EJS source, not fixable note frontmatter.

**Notes without frontmatter** (lists, goals, habits): skipped silently.

## Task Management (MANDATORY)

Create all 7 tasks with dependencies before starting any work.

```javascript
// Task #1: Select scope
TaskCreate({ subject: "Select scope", activeForm: "Selecting scope",
  description: "Ask user which scope to process using AskUserQuestion.\nOptions: All notes, Plans only, Single directory, Single file.\nStore the target path(s) for subsequent tasks." })

// Task #2: Pre-commit checkpoint
TaskCreate({ subject: "Pre-commit pending changes", activeForm: "Pre-committing changes",
  description: "Auto-commit all pending changes to create clean baseline.\nRun git status, git add -A, git commit.\nRecord CHECKPOINT_COMMIT hash.\nDo NOT prompt the user." })

// Task #3: Check frontmatter
TaskCreate({ subject: "Run check_frontmatter.py", activeForm: "Checking frontmatter",
  description: "Run check_frontmatter.py on selected scope with --recursive --format json.\nCollect issues report. Files with no frontmatter are silently skipped." })

// Task #4: Present findings and get approval
TaskCreate({ subject: "Present findings and get approval", activeForm: "Presenting findings",
  description: "Show categorized issues to user via AskUserQuestion.\nList: files with issues, issue types, inferred values.\nGet explicit approval before proceeding to fix." })

// Task #5: Run fix_frontmatter.py
TaskCreate({ subject: "Run fix_frontmatter.py", activeForm: "Fixing frontmatter",
  description: "Run fix_frontmatter.py on approved files with --recursive --format json.\nCollect changes and remaining unfixable issues.\nSurface unfixable fields to user for manual resolution." })

// Task #6: Re-validate
TaskCreate({ subject: "Re-validate (check_frontmatter.py must return [])", activeForm: "Re-validating",
  description: "Run check_frontmatter.py again on same scope.\nResult MUST be empty [].\nIf any issues remain: stop and report to user, do NOT commit." })

// Task #7: Commit
TaskCreate({ subject: "Create git commit", activeForm: "Committing",
  description: "Only if Task #6 passes. Stage and commit all changes with descriptive message." })
```

After creating tasks, set up dependencies:
```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
```

Task dependency flow:
```
#1  Select scope
 └─► #2  Pre-commit checkpoint
      └─► #3  Run check_frontmatter.py
           └─► #4  Present findings, get approval
                └─► #5  Run fix_frontmatter.py
                     └─► #6  Re-validate (must return [])
                          └─► #7  Commit
```

## Workflow

### Step 0: Create Tasks (MANDATORY FIRST STEP)

Create all 7 tasks and set dependencies. Run `TaskList()` to show workflow to user.

### Step 1 (Task #1): Select Scope

Use `AskUserQuestion`:
```
Which notes should I fix frontmatter for?
- All notes with frontmatter (scan Notes/ recursively, including @Templates/)
- Plans only (work + personal plan directories)
- Single directory (I'll specify the path)
- Single file (I'll specify the file)
```

Resolve the target path(s):

```bash
NOTES_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"
WORK_PLANS="$NOTES_ROOT/🏢 ServiceNow/📆 Plans"
PERSONAL_PLANS="$NOTES_ROOT/🏡 Personal/🏡📆 Plans"
```

### Step 2 (Task #2): Pre-commit Pending Changes

```bash
NOTES_REPO="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
cd "$NOTES_REPO"
git status --short
git add -A
git commit -m "chore(noteplan): Auto-commit pending changes before frontmatter fixes

Auto-committed by fix-frontmatter skill to create clean baseline.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
```

**This is an auto-commit. Do NOT prompt the user.**

### Step 3 (Task #3): Check Frontmatter

```bash
# All notes
python3 "$SCRIPTS_DIR/check_frontmatter.py" "$NOTES_ROOT" --recursive --format json

# Plans only (run both, combine results)
python3 "$SCRIPTS_DIR/check_frontmatter.py" "$WORK_PLANS" --recursive --format json
python3 "$SCRIPTS_DIR/check_frontmatter.py" "$PERSONAL_PLANS" --recursive --format json

# Single directory or file
python3 "$SCRIPTS_DIR/check_frontmatter.py" "$TARGET" --recursive --format json
```

Parse the JSON output to collect all issue records.

### Step 4 (Task #4): Present Findings

Show a summary using `AskUserQuestion`:

```
Frontmatter Check Complete

Scanned: N files with frontmatter
Issues found: M issues across K files

By issue type:
  missing_field: X occurrences
  bad_delimiter: Y files (-- → ---)
  bad_value: Z occurrences

Files with issues:
  path/to/file.md — missing: status, workstream
  path/to/other.md — bad delimiter: --

Inferred values (please verify):
  namespace: 🏢 (from path) — 3 files
  workstream: 🏁 (from parent folder) — 2 files
  started: 260118 (from filename) — 1 file

N files have unfixable fields (will need manual input after fixing).

Proceed with fixes?
- Yes, fix all
- Show per-file details first
- Cancel
```

**Collect user approval before Step 5.**

### Step 5 (Task #5): Fix Frontmatter

```bash
python3 "$SCRIPTS_DIR/fix_frontmatter.py" "$TARGET" --recursive --format json
```

For dry-run preview before applying:
```bash
python3 "$SCRIPTS_DIR/fix_frontmatter.py" "$TARGET" --dry-run --recursive --format json
```

Parse the JSON output. Surface any `remaining_issues` to the user:

```
Frontmatter Fixed

Changes applied:
  path/to/file.md:
    ✓ added namespace: 🏢 (from: path contains ServiceNow)
    ✓ fixed delimiter: -- → ---
    ✓ added started: 260118 (from: filename YYMMDD pattern)

Unfixable (need manual input):
  path/to/other.md:
    ✗ missing status — cannot infer (no H1 emoji found)
    ✗ missing workstream — no emoji in filename or parent folder

Please fix the above manually before re-validation, or skip those files.
```

Wait for user to resolve unfixable fields if any.

### Step 6 (Task #6): Re-validate

```bash
python3 "$SCRIPTS_DIR/check_frontmatter.py" "$TARGET" --recursive --format json
```

**Result MUST be `[]` (empty array).**

- If empty: proceed to commit.
- If issues remain: STOP. Report remaining issues to user. Do NOT commit.

### Step 7 (Task #7): Commit

```bash
cd "$NOTES_REPO"
git add -A
git commit -m "$(cat <<'EOF'
fix(noteplan): Fix frontmatter across note files

- Fixed delimiter in X files (-- → ---)
- Added missing fields in Y files
- Corrected date formats in Z files

Validated via re-run of check_frontmatter.py (returned []).
Skill: fix-frontmatter

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Adjust the message to reflect actual changes.

## Safety Checks

- **No content modification**: Only frontmatter is modified. Never touch body content, todos, or links.
- **Pre-commit baseline**: Always auto-commit before making changes.
- **User approval required**: Always present findings and get explicit approval before fixing.
- **Re-validate before commit**: check_frontmatter.py must return [] — no silent failures.
- **Unfixable fields surfaced**: Fields that cannot be inferred are shown to user for manual resolution.
- **Templates validated structurally only**: EJS placeholder values are never modified.
- **@Trash excluded**: Trashed files are always skipped.

## Template Validation (Optional)

To separately validate or audit `@Templates/` EJS frontmatter blocks:

```bash
# Check that all templates declare the right fields in their -- EJS block
python3 "$SCRIPTS_DIR/check_templates.py" "$NOTES_ROOT/@Templates" --format human

# Report any template EJS block issues (always dry-run — EJS wiring is manual)
python3 "$SCRIPTS_DIR/fix_templates.py" "$NOTES_ROOT/@Templates" --format human
```

Templates are **never** modified by `fix_frontmatter.py` — their `--` block is EJS source code.
`fix_templates.py` reports structural issues and what manual EJS changes are needed.

## Related Skills

- **fix-plans** — Broader plan structure fixing (headers, self-ref todos, emojis, bullets); delegates frontmatter to this skill's tooling
- **flatten-plans** — One-time migration from Future/Present/Past folder structure
- **update-plan-status** — Change plan status (frontmatter + H1 emoji + filename)
- **manage-templates** — Create and validate NotePlan templates
