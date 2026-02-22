---
name: flatten-plans
description: One-time migration to flatten personal plans directory — removes Future/Present/Past/Paused status-bucket folders, moves all plan files into merged workstream folders directly under 🏡📆 Plans/, and migrates status to frontmatter + H1 title emoji
---

# Flatten Personal Plans Directory

You are a one-time migration tool. When invoked, you flatten the personal plans directory by removing the status-bucket folder structure (Future/, Present/, Past/, Paused/) and migrating status metadata into each file's frontmatter and H1 title. Files move into merged workstream folders directly under `🏡📆 Plans/`.

**This skill is destructive and irreversible without git.** It uses git throughout for safety and commits the result.

## What This Skill Does

1. **Pre-flight** — git status check, warn on pending changes
2. **Scan** — find all `.md` files in `Future/`, `Present/`, `Past/`, `Paused/`
3. **Plan** — show user: N files, workstream merge map, file rename preview
4. **Confirm** — user approves before any changes are made
5. **Migrate** — per file: update frontmatter, update H1, rename file, move file
6. **Validate** — git diff to check all moves and edits
7. **Commit** — commit the migration

## Status Inference (from source folder)

| Source Folder | Status Emoji | Status Name |
|---|---|---|
| `Future/` | `🔮` | Future |
| `Present/` | `🟢` | Started |
| `Past/` | `✅` | Done |
| `Paused/` | `🟡` | Paused |

## Title H1 Pattern After Migration

```
# 🏡<status><YYMMDD><plantype> Title
Example: # 🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization
```

The status emoji is inserted as the **2nd emoji** in the title — immediately after the namespace emoji (`🏡`), before the date.

## File Rename Rule (Golden Rule)

Filename (without `.md`) must match the H1 title (without `# `).

```
Before: 🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization.md
After:  🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization.md
```

## Frontmatter Format

Regular plan notes (not templates) use `---` (triple dash) delimiters — standard YAML.

```yaml
---
doctype: 📆
status: 🟢
started: 260117
namespace: 🏡
plantype: 👨🏻‍💻
---
```

For files from `Past/` (status `✅`), add a `completed` field:

```yaml
---
doctype: 📆
status: ✅
started: 251219
completed: unknown
namespace: 🏡
plantype: 👨🏻‍💻
---
```

Use `completed: unknown` unless the date is derivable from git log or file content.

## Self-Referencing Todo Update

After renaming a file, find and update the self-referencing todo to use the new filename (wiki-link must match):

```
Before: * [ ] Is [[🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization]] done? >2026-W3
After:  * [ ] Is [[🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization]] done? >2026-W3
```

## Workstream Merging

Multiple time-bucket folders may have the same workstream name (e.g., `👨🏻‍💻 Development` appears in Future, Present, and Past). These merge into one folder. Files don't collide because dates in filenames are unique.

```
Future/👨🏻‍💻 Development/🏡🔮260301👨🏻‍💻 Future Dev.md
Present/👨🏻‍💻 Development/🏡🟢260117👨🏻‍💻 Active Dev.md
Past/👨🏻‍💻 Development/🏡✅251219👨🏻‍💻 Done Dev.md
→
👨🏻‍💻 Development/🏡🔮260301👨🏻‍💻 Future Dev.md
👨🏻‍💻 Development/🏡🟢260117👨🏻‍💻 Active Dev.md
👨🏻‍💻 Development/🏡✅251219👨🏻‍💻 Done Dev.md
```

## Task Management (MANDATORY)

**Before doing ANY work, create all 7 tasks:**

```javascript
// Task #1: Pre-flight check
TaskCreate({
  subject: "Pre-flight — git status and pending changes check",
  description: "Check git status in the NotePlan repo. If there are pending changes, warn the user and ask how to proceed (auto-commit, abort, or continue anyway). Record the current HEAD as CHECKPOINT_COMMIT.",
  activeForm: "Running pre-flight check"
})

// Task #2: Scan source folders
TaskCreate({
  subject: "Scan — list all files in Future/Present/Past/Paused",
  description: "Find all .md files in the four time-bucket folders under 🏡📆 Plans/. For each file, record: source folder (Future/Present/Past/Paused), workstream subfolder name, filename, current H1 title, frontmatter status field. Build complete file inventory.",
  activeForm: "Scanning plan files"
})

// Task #3: Build migration plan and show user
TaskCreate({
  subject: "Plan — build migration map and show preview",
  description: "From the scan inventory, build:\n- Inferred status per file (from source folder)\n- New filename per file (with status emoji inserted)\n- New path per file (workstream folder directly under 🏡📆 Plans/)\n- Workstream merge map (which workstreams merge from multiple buckets)\n- Count of files per status\nShow the full plan to the user using AskUserQuestion before making any changes.",
  activeForm: "Building migration plan"
})

// Task #4: Confirm with user
TaskCreate({
  subject: "Confirm — ask user to approve migration",
  description: "Present summary to user via AskUserQuestion:\n- N files to migrate\n- Workstream merge map\n- Status breakdown (🔮 X, 🟢 Y, ✅ Z, 🟡 W)\n- Sample file renames\nOptions: Proceed / Abort / Show full file list",
  activeForm: "Awaiting user confirmation"
})

// Task #5: Migrate files
TaskCreate({
  subject: "Migrate — update frontmatter, title, self-ref, rename, move",
  description: "For each file in the migration plan:\n1. Update frontmatter: set status to inferred emoji, add completed field if ✅\n2. Update H1 title: insert status emoji after namespace emoji\n3. Update self-referencing todo: update wiki-link to match new title\n4. Use git mv to rename file (new name with status emoji)\n5. Use git mv to move file to merged workstream folder\n6. Remove empty source folders after all files are moved",
  activeForm: "Migrating files"
})

// Task #6: Validate
TaskCreate({
  subject: "Validate — git diff preview and lost file check",
  description: "Run git diff --stat and git status to verify:\n- All files show as renames (not delete + new)\n- No files were lost\n- Spot-check 3 files: frontmatter status correct, H1 has status emoji, filename matches title\nReport any anomalies to user.",
  activeForm: "Validating migration"
})

// Task #7: Commit
TaskCreate({
  subject: "Commit — commit the migration",
  description: "Stage all changes and commit with descriptive message listing:\n- Total files migrated\n- Status breakdown\n- Workstreams created/merged\nInclude skill name and co-author.",
  activeForm: "Committing migration"
})
```

**Set up dependencies (sequential):**

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
```

## Workflow

### Step 0: Task Setup (Do First)

Create all 7 tasks with dependencies, run `TaskList()` to show plan.

### Step 1 (Task #1): Pre-flight

```bash
NOTEPLAN_NOTES="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"
PLANS_DIR="$NOTEPLAN_NOTES/🏡 Personal/🏡📆 Plans"

cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
git status --short
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
echo "Checkpoint: $CHECKPOINT_COMMIT"
```

If pending changes exist: use `AskUserQuestion` — auto-commit them, abort, or continue.

### Step 2 (Task #2): Scan

```bash
# List all .md files in the four time-bucket folders
find "$PLANS_DIR/Future" "$PLANS_DIR/Present" "$PLANS_DIR/Past" "$PLANS_DIR/Paused" \
  -name "*.md" -type f 2>/dev/null | sort
```

For each file:
1. Record source folder (`Future`, `Present`, `Past`, or `Paused`)
2. Record workstream subfolder (e.g., `👨🏻‍💻 Development`)
3. Read file: extract frontmatter and H1 title

Report: total file count, per-bucket counts.

### Step 3 (Task #3): Build Plan

For each file, compute:

- **Status emoji** from source folder (see table above)
- **Current title** from H1 (e.g., `🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization`)
- **New title** with status emoji inserted: `🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization`
- **New filename**: `🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization.md`
- **New path**: `🏡📆 Plans/👨🏻‍💻 Development/🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization.md`

**Status emoji insertion rule:**
- If the title already has a status emoji as 2nd emoji (one of `🔮🚦🟢🟡🔴❎✅`), replace it
- Otherwise, insert the status emoji immediately after the first emoji (`🏡`)

Build workstream merge map:
```
👨🏻‍💻 Development: from Future (1 file), Present (2 files), Past (3 files) → merged (6 files)
🏃🏻 Health: from Future (1 file), Present (1 file) → merged (2 files)
...
```

### Step 4 (Task #4): Confirm

Use `AskUserQuestion`:
```
Ready to migrate personal plans:

- 45 files to migrate
- Status: 🔮 12, 🟢 14, ✅ 15, 🟡 4
- Workstreams: 22 unique (some merge from multiple buckets)

Sample renames:
  🏡260117👨🏻‍💻 Developing Claude Cron.md
  → 🏡🟢260117👨🏻‍💻 Developing Claude Cron.md

Workstream merges:
  👨🏻‍💻 Development: Future(1) + Present(2) + Past(3) = 6 files

Proceed?
- Yes, migrate all files
- Show full file list first
- Abort
```

### Step 5 (Task #5): Migrate

For each file in the plan (process in source-folder order: Future → Present → Past → Paused):

#### 5a: Update Frontmatter

Read the file. Find the frontmatter block (between `---` delimiters). Update `status:` field. If status is `✅` and no `completed` field exists, add `completed: unknown`.

```
---
doctype: 📆
status: 🟢        ← update this
started: 260117
namespace: 🏡
plantype: 👨🏻‍💻
---
```

Use the Edit tool to update frontmatter in place.

#### 5b: Update H1 Title

Find the line starting with `# 🏡`. Insert (or replace) status emoji as 2nd emoji:

```
Before: # 🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization
After:  # 🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization
```

Use the Edit tool.

#### 5c: Update Self-Referencing Todo

Find the line `* [ ] Is [[<old-title>]] done?`. Replace the wiki-link with the new title.

```
Before: * [ ] Is [[🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization]] done? >2026-W3
After:  * [ ] Is [[🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization]] done? >2026-W3
```

Use the Edit tool.

#### 5d: Rename and Move Using git mv

```bash
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
cd "$NOTEPLAN_ROOT"

# Create destination workstream folder if needed
mkdir -p "Notes/🏡 Personal/🏡📆 Plans/👨🏻‍💻 Development"

# Rename + move in one git mv
git mv "Notes/🏡 Personal/🏡📆 Plans/Present/👨🏻‍💻 Development/🏡260117👨🏻‍💻 Developing Claude Cron for Note Organization.md" \
       "Notes/🏡 Personal/🏡📆 Plans/👨🏻‍💻 Development/🏡🟢260117👨🏻‍💻 Developing Claude Cron for Note Organization.md"
```

**Important:** File content must be updated (steps 5a–5c) **before** the `git mv`. Edit in place first, then move.

#### 5e: Remove Empty Source Folders

After all files are moved:

```bash
# Remove empty time-bucket subfolders and then the buckets themselves
rmdir "$PLANS_DIR/Future/"*/ 2>/dev/null
rmdir "$PLANS_DIR/Present/"*/ 2>/dev/null
rmdir "$PLANS_DIR/Past/"*/ 2>/dev/null
rmdir "$PLANS_DIR/Paused/"*/ 2>/dev/null
rmdir "$PLANS_DIR/Future" "$PLANS_DIR/Present" "$PLANS_DIR/Past" "$PLANS_DIR/Paused" 2>/dev/null
```

Only remove if truly empty — `rmdir` will fail safely on non-empty directories.

### Step 6 (Task #6): Validate

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Show what changed
git diff --stat HEAD
git status --short

# Verify no files lost
find "Notes/🏡 Personal/🏡📆 Plans" -name "*.md" | wc -l
```

Spot-check 3 files (one `🔮`, one `🟢`, one `✅`):
- Frontmatter has correct status emoji
- H1 has status emoji as 2nd emoji
- Filename matches H1 title (without `# `)
- Self-referencing todo wiki-link matches new title

Report findings. If any anomaly: pause and ask user.

### Step 7 (Task #7): Commit

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

git add -A
git commit -m "$(cat <<'EOF'
refactor(personal-plans): Flatten status-bucket folders into workstream folders

- Removed Future/, Present/, Past/, Paused/ time-bucket structure
- Merged all workstreams into flat folders directly under 🏡📆 Plans/
- Migrated status to frontmatter + H1 title emoji for each file
- Status mapping: Future→🔮, Present→🟢, Past→✅, Paused→🟡
- Renamed files to include status emoji (Golden Rule compliance)
- Updated self-referencing todos with new filenames

Stats:
- XX files migrated (🔮 X, 🟢 Y, ✅ Z, 🟡 W)
- XX workstreams created (YY merged from multiple buckets)
Skill: flatten-plans

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## Safety Checks

- **Git required**: This skill uses `git mv` throughout. Abort if the NotePlan directory is not a git repo.
- **Pre-flight**: Always check git status before starting. Warn on pending changes.
- **User confirmation**: Show full plan before touching any file.
- **git mv only**: Never use plain `mv` — `git mv` preserves history and ensures renames show as renames in diff.
- **Edit before move**: Update file content (frontmatter, H1, self-ref) before `git mv`; do not edit a file at its new path.
- **Spot-check**: Validate at least 3 files after migration before committing.
- **Frontmatter delimiters**: Regular plan notes use `---` (triple dash), not `--` (double dash). The `fix-plans` skill uses `--` because it targets templates.

## Note Map Integration

After migration completes and commit is made, remind the user:

> Run `/noteplan-manager:discover-structure` to regenerate `🗺️ Note Map.md` with the new flat structure. Other skills depend on it.

## Related Skills

- **update-plan-status** — change status of individual plan files post-migration
- **fix-plans** — standardize plan frontmatter and structure (works on post-migration flat layout)
- **discover-structure** — regenerate `🗺️ Note Map.md` after migration
- **fix-filenames** — ensure filenames match H1 titles (Golden Rule)
