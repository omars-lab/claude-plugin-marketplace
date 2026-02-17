---
name: fix-filenames
description: Fix filenames to match heading conventions, detect naming issues, and resolve conflicts across NotePlan notes with pending git changes
---

# Fix Filenames

You are a NotePlan filename fixer. When this skill is invoked, you'll scan files with pending git changes and fix filenames to match their `# Title` heading, following folder-specific naming conventions.

## What This Skill Does

This skill:
1. **Scans files with pending git changes** in the NotePlan Notes directory
2. **Reads the `# Title` heading** from each file
3. **Compares filename to heading** (the golden rule: `filename.md` = `# Title`)
4. **Detects naming issues** (mismatches, weird characters, duplication artifacts, misplaced files)
5. **Resolves conflicts** when target filenames already exist
6. **Renames files** using `git mv` (tracked) or `mv` (untracked)
7. **Validates changes** via git diff before committing

## The Golden Rule

> **Filename (minus `.md`) = Title heading (minus `# `)**

Every NotePlan note's filename must exactly match its first `# Title` heading. If they don't match, the filename is wrong and should be renamed.

## Naming Conventions by Folder

The heading format (and therefore filename) depends on which folder the file lives in:

| Folder Context | Heading Format | Example Heading / Filename |
|---|---|---|
| Work Plans (`📆 Plans/`) | `🏢YYMMDD[stream] Title` | `🏢260118🏁 Onboarding.md` |
| Personal Plans (`🏡📆 Plans/`) | `🏡YYMMDD[activity] Title` | `🏡260115⚙️ Automating.md` |
| Work Meetings (`👤 Meetings/`) | `🏢 YYMMDD Title` | `🏢 260213 Anna Intro.md` |
| Work Lists (`📋 Lists/`) | `🏢📋 Type` or `🏢📋 Type[Qualifier]` | `🏢📋 Benefits.md`, `🏢📋 References[Features].md` |
| Personal Lists (`🏡📋 Lists/`) | `🏡📋 Type` or `🏡📋 Type[Qualifier]` | `🏡📋 Activities.md`, `🏡📋 References[GenAI].md` |
| Research (`🔬 Research/`) | `🏢 YYMMDD Title` | `🏢 260204 Deep Dive.md` |
| Templates (`@Templates/`) | `[domain][type] Name` | `🏢📆 Work Plan.md` |

### Convention Details

**Work Plans** - `🏢YYMMDD[stream-emoji] Title`
- `🏢` namespace prefix, no space before date
- `YYMMDD` date format
- Workstream emoji from parent subdirectory (🏁, 🎯, 🧑🏻‍💻, etc.)
- Space before title text

**Personal Plans** - `🏡YYMMDD[activity-emoji] Title`
- `🏡` namespace prefix, no space before date
- `YYMMDD` date format
- Activity type emoji from template (⚙️, ✈️, 📚, etc.)
- Space before title text

**Work Meetings** - `🏢 YYMMDD Title`
- `🏢` namespace prefix with space
- `YYMMDD` date
- Space-separated title

**Work Lists** - `🏢📋 Type` or `🏢📋 Type[Qualifier]`
- `🏢📋` domain + doctype prefix with space
- Descriptive type name
- Optional qualifier in square brackets for subcategories

**Personal Lists** - `🏡📋 Type` or `🏡📋 Type[Qualifier]`
- `🏡📋` domain + doctype prefix with space
- Same pattern as work lists with personal namespace

**Research** - `🏢 YYMMDD Title`
- Same format as meetings

**Templates** - `[domain][type] Name`
- Domain emoji followed by type emoji
- Space before name

### Characters Allowed in Filenames

- Standard alphanumeric characters (a-z, A-Z, 0-9)
- Spaces
- Hyphens (`-`), underscores (`_`)
- Square brackets for qualifiers (`[`, `]`)
- Emojis from the NotePlan system (namespace, doctype, workstream, activity, status)
- Periods (only for `.md` extension)

### Characters NOT Allowed

- NotePlan duplication suffixes (` 2`, ` 3`, ` 2 8`, ` 2 8 2`)
- Special characters: `?`, `*`, `<`, `>`, `|`, `\`, `/`, `:`, `"`
- Leading/trailing whitespace in the name portion

## Issue Classification

When scanning files, classify each issue:

| Classification | Description | Example |
|---|---|---|
| `MISMATCH` | Filename doesn't match heading | File: `Old Name.md`, Heading: `# New Name` |
| `MISSING_PREFIX` | File in Lists/Plans lacks domain+type emoji prefix | File: `Benefits.md` in `📋 Lists/` (should be `🏢📋 Benefits.md`) |
| `WEIRD_CHARS` | NotePlan duplication artifacts or bad characters | `Benefits 2 8 2.md`, `Benefits 2 2.md` |
| `MISPLACED` | Naming pattern doesn't match folder | Plans-style name `🏢260216🏁 Title.md` in `📋 Lists/` |
| `NO_HEADING` | File has no `#` heading (needs one added) | File exists but has no title line |
| `CONFLICT` | Target filename already exists in same directory | `Benefits 2 2.md` wants to become `🏢📋 Benefits.md` but it already exists |
| `OK` | Filename matches heading and follows convention | No action needed |

### Detecting NotePlan Duplication Artifacts

NotePlan creates copies with numeric suffixes when syncing conflicts occur:
- `Name 2.md` - first duplicate
- `Name 3.md` - second duplicate
- `Name 2 8.md` - duplicate of a duplicate
- `Name 2 8 2.md` - duplicate of a duplicate of a duplicate

**Detection pattern:** Filename ends with ` N.md` or ` N N.md` where N is a digit.

**Resolution:**
1. Check if a "root" file exists (e.g., `Benefits.md` for `Benefits 2 8 2.md`)
2. If root exists: treat as `CONFLICT` - compare content of both files
3. If root doesn't exist: rename to clean name (strip duplication numbers)

## Git Safety and Task Management

### Task Management (MANDATORY)

This skill **MUST** use task management to track progress. Tasks are not optional.

**BEFORE starting any work, create all 7 tasks with proper dependencies:**

#### Task Creation (Step 0 - Do this FIRST)

```javascript
// Task #1: Pre-commit pending content changes
TaskCreate({
  subject: "Pre-commit pending content changes",
  description: "Auto-commit all pending changes to create a clean baseline checkpoint for diffing later.\n\nActions:\n- Run git status --short to capture current state\n- git add -A && git commit all pending changes with descriptive message\n- Record the commit hash as CHECKPOINT_COMMIT\n- This creates a clean baseline for validation in Task #6\n\nIMPORTANT: This is an auto-commit, do NOT prompt the user.",
  activeForm: "Pre-committing pending changes"
})

// Task #2: Scan pending files and read headings
TaskCreate({
  subject: "Scan pending files and read headings",
  description: "Run git status again to get fresh list of pending files after pre-commit.\n\nActions:\n- Run git status --short\n- Filter: only Notes/ files (skip Calendar/, .obsidian/, @Trash/)\n- For each file: Read the file, extract # Title heading and frontmatter\n- Build report: {filepath, current_filename, heading_title, frontmatter, folder_context}\n\nThis is a read-only scan step.",
  activeForm: "Scanning pending files"
})

// Task #3: Analyze naming issues and classify
TaskCreate({
  subject: "Analyze naming issues and classify",
  description: "For each scanned file, determine expected naming convention from folder context.\n\nActions:\n- Classify each issue: MISMATCH, MISSING_PREFIX, WEIRD_CHARS, MISPLACED, NO_HEADING, CONFLICT, OK\n- Build proposed fixes for each non-OK file\n- CONFLICT DETECTION (CRITICAL): Before proposing any rename, check if target filename already exists\n  - If target exists: mark as CONFLICT, read BOTH files, compare content\n  - Common scenario: Benefits 2 2.md wants to become 🏢📋 Benefits.md but Benefits.md exists\n- For conflicts, determine if files are duplicates, overlapping, or distinct\n\nThis is a read-only analysis step.",
  activeForm: "Analyzing naming issues"
})

// Task #4: Present proposed fixes to user
TaskCreate({
  subject: "Present proposed fixes to user",
  description: "Show categorized report of all issues found and get user approval.\n\nUse AskUserQuestion for each category:\n\n1. Straightforward renames (no conflict): 'Apply these N renames?'\n2. CONFLICT resolution (target exists): Offer Merge/Keep both/Replace/Skip per conflict\n   - Show content comparison: 'Both files contain X lines. ~Y% overlap.'\n3. Misplaced files: 'Move to correct folder, rename for current folder, or skip?'\n4. Files with no heading: 'Add heading to match expected convention?'\n5. NotePlan duplicates: Detect root file, treat as conflict or clean rename\n\nCollect all user decisions before proceeding.",
  activeForm: "Presenting proposed fixes"
})

// Task #5: Execute approved renames
TaskCreate({
  subject: "Execute approved renames",
  description: "For each approved fix:\n\n1. Pre-flight check: Verify target path doesn't exist (guard against race conditions)\n2. If heading needs updating: Edit file to fix heading/frontmatter\n3. If filename needs changing: git mv for tracked files, mv for untracked\n4. If file needs moving to different folder: git mv to correct location\n5. If merging files: Append content, verify merge, then delete source\n\nAfter all renames: check for broken [[Note Name]] wikilinks in recently modified files.",
  activeForm: "Executing approved renames"
})

// Task #6: Validate diff - ONLY filenames/headers/frontmatter changed
TaskCreate({
  subject: "Validate diff - only filenames/headers/frontmatter changed",
  description: "CRITICAL validation step.\n\nActions:\n- Run git diff CHECKPOINT_COMMIT to see ALL changes since pre-commit\n- Verify ONLY these types of changes occurred:\n  - Filename renames (shown as delete + add in diff)\n  - Header line changes (# Title updated to match new filename)\n  - Frontmatter changes (namespace, doctype fields)\n- Flag if ANY other content was modified (body text, tasks, links, etc.)\n- If unexpected changes found: STOP and report to user, do NOT proceed to commit\n\nShow validation summary with counts of each change type.",
  activeForm: "Validating changes"
})

// Task #7: Create git commit
TaskCreate({
  subject: "Create git commit",
  description: "Only proceed if Task #6 validation passes.\n\nActions:\n- Stage all changes\n- Create commit with descriptive message listing:\n  - Number of files renamed\n  - Number of headers updated\n  - Number of files moved\n  - Any merges performed\n- Include 'Validated via git diff' note\n- Include skill name and co-author\n\nIf validation failed in Task #6, do NOT commit - report issues instead.",
  activeForm: "Creating git commit"
})
```

#### Set Up Task Dependencies

**After creating all 7 tasks, set up dependencies:**

```javascript
// Task #2 depends on #1 (need clean baseline first)
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })

// Task #3 depends on #2 (need scan results to analyze)
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })

// Task #4 depends on #3 (need analysis to present)
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })

// Task #5 depends on #4 (need user approval to execute)
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })

// Task #6 depends on #5 (validate after execution)
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })

// Task #7 depends on #6 (commit only if validation passes)
TaskUpdate({ taskId: "7", addBlockedBy: ["6"] })
```

#### Task Dependency Flow

```
#1 Pre-commit pending content changes
 └─► #2 Scan pending files and read headings
      └─► #3 Analyze naming issues and classify
           └─► #4 Present proposed fixes to user
                └─► #5 Execute approved renames
                     └─► #6 Validate diff - ONLY filenames/headers/frontmatter changed
                          └─► #7 Create git commit
```

#### Update Task Status During Workflow

**ALWAYS update task status as you progress:**

```javascript
// When starting a task
TaskUpdate({ taskId: "1", status: "in_progress" })

// When completing a task
TaskUpdate({ taskId: "1", status: "completed" })

// List tasks to show progress
TaskList() // Shows what's done, in progress, and blocked
```

## Workflow

When invoked, **ALWAYS follow this exact workflow:**

### **Step 0: Task Setup (MANDATORY FIRST STEP)**

Before doing ANY work, create all tasks with dependencies:

```
1. Create 7 tasks (see Task Management section for exact definitions)
2. Set up task dependencies using TaskUpdate
3. Run TaskList to show workflow to user
4. Mark Task #1 as in_progress to begin work
```

**Display task plan to user:**
```
Filename Fix - Task Workflow (7 Tasks)

#1 Pre-commit pending content changes [STARTING]
 └─► #2 Scan pending files and read headings
      └─► #3 Analyze naming issues and classify
           └─► #4 Present proposed fixes to user
                └─► #5 Execute approved renames
                     └─► #6 Validate diff
                          └─► #7 Create git commit

Ready to begin!
```

### **Step 1 (Task #1): Pre-commit Pending Changes**

Mark task as in_progress, then auto-commit all pending changes:

```bash
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Check current state
git status --short

# Stage and commit everything
git add -A
git commit -m "chore(noteplan): Auto-commit pending changes before filename fixes

[Describe what changes were pending based on git status output]

Auto-committed by fix-filenames skill to create clean baseline.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Record the commit hash as `CHECKPOINT_COMMIT`** for validation later:
```bash
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
```

**This is an auto-commit. Do NOT prompt the user.**

**Complete Task #1 and start Task #2.**

### **Step 2 (Task #2): Scan Pending Files**

```javascript
TaskUpdate({ taskId: "1", status: "completed" })
TaskUpdate({ taskId: "2", status: "in_progress" })
```

Get fresh list of files with pending changes:

```bash
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
git status --short
```

**Filter rules:**
- INCLUDE: Files under `Notes/` with status M (modified), A (added), or ?? (untracked)
- SKIP: `Calendar/` files
- SKIP: `.obsidian/` files
- SKIP: `Notes/@Trash/` files

**For each included file:**
1. Read the file content
2. Extract the first `# Title` heading line
3. Extract frontmatter (if any)
4. Determine folder context (which folder convention applies)
5. Record: `{filepath, current_filename, heading_title, frontmatter, folder_context}`

**Report scan results:**
```
Scanned N files with pending changes:

Notes/🏢 ServiceNow/📋 Lists/
  - Benefits 2 2.md → Heading: "# 🏢📋 Benefits"
  - Benefits 2 8 2.md → Heading: "# 🏢📋 Benefits"
  - 🏢260216🏁 Researching MCPs.md → Heading: "# 🏢260216🏁 Researching MCPs"

Skipped: Calendar/*, .obsidian/*, @Trash/*
```

**Complete Task #2 and start Task #3.**

### **Step 3 (Task #3): Analyze Naming Issues**

```javascript
TaskUpdate({ taskId: "2", status: "completed" })
TaskUpdate({ taskId: "3", status: "in_progress" })
```

For each scanned file:

1. **Determine expected convention** from folder context (see Naming Conventions table)
2. **Compare filename to heading** - does filename (minus `.md`) match heading (minus `# `)?
3. **Check for duplication artifacts** - does filename match pattern `Name N.md` or `Name N N.md`?
4. **Check for misplaced files** - does the naming pattern belong in a different folder?
5. **Check for missing prefixes** - does the file lack the expected domain+type emoji prefix?
6. **CONFLICT DETECTION** (CRITICAL):
   - Before proposing any rename, check if the target filename already exists
   - If target exists: read BOTH files, compare content
   - Determine: duplicate (>80% overlap), overlapping (some shared content), or distinct

**Build classified report:**
```
Analysis Complete - N issues found:

WEIRD_CHARS (2 files):
  Benefits 2 2.md → duplication artifact, root: Benefits.md
  Benefits 2 8 2.md → duplication artifact, root: Benefits.md

MISPLACED (1 file):
  🏢260216🏁 Researching MCPs.md → Plans-style name in Lists folder

CONFLICT (2 files):
  Benefits 2 2.md → target 🏢📋 Benefits.md already exists
  Benefits 2 8 2.md → target 🏢📋 Benefits.md already exists
  (Content comparison: Both ~Y% overlap with existing file)

OK (0 files):
  [none with pending changes]
```

**Complete Task #3 and start Task #4.**

### **Step 4 (Task #4): Present Proposed Fixes**

```javascript
TaskUpdate({ taskId: "3", status: "completed" })
TaskUpdate({ taskId: "4", status: "in_progress" })
```

Present categorized findings using `AskUserQuestion`:

#### Straightforward Renames (no conflict)
```
These files need renaming to match their headings:

1. OldName.md → 🏢📋 NewName.md
2. Another.md → 🏢📋 Another[Qualifier].md

Apply these renames? (yes/no/show details)
```

#### CONFLICT Resolution (target already exists)

Use `AskUserQuestion` with options per conflict:

```
CONFLICT: Benefits 2 2.md wants to become 🏢📋 Benefits.md

🏢📋 Benefits.md already exists (42 lines)
Benefits 2 2.md has 38 lines
Content overlap: ~85%

Options:
- Merge: Append unique content from duplicate into existing file, delete duplicate
- Keep both: Rename to 🏢📋 Benefits[2].md
- Replace: Overwrite existing with this file
- Skip: Leave both files as-is
```

#### Misplaced Files

```
🏢260216🏁 Researching MCPs.md is in 📋 Lists/ but has Plans naming convention.

Options:
- Move to Plans: git mv to 📆 Plans/ folder
- Rename for Lists: Change to 🏢📋 Researching MCPs.md
- Skip: Leave as-is
```

#### Files with No Heading

```
file.md has no # heading.

Expected heading based on folder convention: # 🏢📋 FileName

Options:
- Add heading: Insert # 🏢📋 FileName as first line
- Skip: Leave as-is
```

#### NotePlan Duplicates

```
Benefits 2 8.md and Benefits 2 9.md appear to be NotePlan sync duplicates.

Root file Benefits.md exists with 42 lines.
Benefits 2 8.md has 40 lines (~90% overlap)
Benefits 2 9.md has 41 lines (~92% overlap)

Options:
- Merge all into root: Combine unique content, delete duplicates
- Keep all: Rename duplicates with [N] suffix
- Review individually: Show content diff for each
```

**Collect ALL user decisions before proceeding to Task #5.**

**Complete Task #4 and start Task #5.**

### **Step 5 (Task #5): Execute Approved Renames**

```javascript
TaskUpdate({ taskId: "4", status: "completed" })
TaskUpdate({ taskId: "5", status: "in_progress" })
```

For each approved fix:

1. **Pre-flight check**: Verify target path doesn't exist (guard against race conditions)
   ```bash
   ls -la "target/path/NewFilename.md" 2>/dev/null && echo "EXISTS" || echo "CLEAR"
   ```

2. **If heading needs updating**: Use Edit tool to fix `# Title` line and frontmatter fields

3. **If filename needs changing**:
   ```bash
   # For tracked files
   git mv "Notes/path/OldName.md" "Notes/path/NewName.md"

   # For untracked files
   mv "Notes/path/OldName.md" "Notes/path/NewName.md"
   ```

4. **If file needs moving to different folder**:
   ```bash
   git mv "Notes/path/Lists/MisplacedFile.md" "Notes/path/Plans/CorrectFile.md"
   ```

5. **If merging files** (user chose Merge for conflict):
   - Read both files
   - Identify unique content in the duplicate
   - Append unique content to the target file (clearly marked)
   - Verify merge looks correct
   - Delete the source duplicate:
     ```bash
     git rm "Notes/path/Duplicate.md"
     ```

6. **After all renames**: Check for broken `[[Note Name]]` wikilinks
   - Search recently modified files for `[[OldFilename]]` references
   - Report any broken links found (but don't auto-fix cross-file links)

**Report execution results:**
```
Executed N changes:

Renamed:
  Benefits 2 2.md → 🏢📋 Benefits[2].md
  Benefits 2 8 2.md → 🏢📋 Benefits[3].md

Moved:
  📋 Lists/🏢260216🏁 Researching MCPs.md → 📆 Plans/🏁 Onboarding/🏢260216🏁 Researching MCPs.md

Headers Updated:
  Benefits.md: # Benefits → # 🏢📋 Benefits

Wikilink Check:
  No broken [[wikilinks]] detected in recently modified files.
```

**Complete Task #5 and start Task #6.**

### **Step 6 (Task #6): Validate Diff**

```javascript
TaskUpdate({ taskId: "5", status: "completed" })
TaskUpdate({ taskId: "6", status: "in_progress" })
```

**CRITICAL: Validate ALL changes since pre-commit:**

```bash
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Show all changes since checkpoint
git diff $CHECKPOINT_COMMIT --stat
git diff $CHECKPOINT_COMMIT
```

**Verify ONLY these types of changes occurred:**
- Filename renames (shown as delete + add in diff, or rename detection)
- Header line changes (`# Title` updated to match new filename)
- Frontmatter changes (namespace, doctype fields)

**Flag if ANY other content was modified** (body text, tasks, links beyond heading, etc.)

**Show validation summary:**
```
Validating changes since checkpoint [HASH]...

Files renamed: 5
Headers updated: 3
Frontmatter updated: 2
No unexpected content changes detected

-- OR --

Unexpected change detected in Benefits.md line 42
Content was modified beyond filename/header/frontmatter
STOPPING - please review before committing
```

**If validation PASSES**: Complete Task #6 and start Task #7.
**If validation FAILS**: STOP. Report to user. Do NOT proceed to commit.

### **Step 7 (Task #7): Create Git Commit**

```javascript
TaskUpdate({ taskId: "6", status: "completed" })
TaskUpdate({ taskId: "7", status: "in_progress" })
```

**Only proceed if Task #6 validation passed.**

```bash
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Stage all changes
git add -A

# Create commit
git commit -m "$(cat <<'EOF'
fix(noteplan): Fix filenames to match heading conventions

- Renamed X files to match # Title headings
- Added domain+type emoji prefix to Y list files
- Updated Z headers to match new filenames
- Moved N misplaced files to correct folders
- Merged M duplicate files

Validated via git diff: only filenames, headers, and frontmatter changed.
Skill: fix-filenames

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**Adjust the commit message to reflect actual changes made.**

**Complete Task #7 and show final summary:**

```javascript
TaskUpdate({ taskId: "7", status: "completed" })
TaskList() // Show all tasks completed
```

```
Filename Fix Complete!

Task #1: Pre-commit pending changes
Task #2: Scanned N pending files
Task #3: Analyzed naming issues (X issues found)
Task #4: Presented fixes, user approved Y changes
Task #5: Executed Y renames/moves/merges
Task #6: Validated diff - no unexpected changes
Task #7: Created git commit [HASH]

All tasks completed!
```

## Safety Checks

- **Golden rule**: Filename always matches heading - never rename without checking heading first
- **Pre-commit**: Always auto-commit pending changes before making filename changes
- **Conflict detection**: Always check if target filename exists before renaming
- **Diff validation**: Always validate git diff before committing - only filenames, headers, and frontmatter should change
- **No content modification**: Never modify file body content (tasks, notes, links beyond the heading line)
- **User approval**: Always present proposed changes and get explicit approval before executing
- **Pre-flight checks**: Verify target path is clear immediately before each rename
- **Wikilink awareness**: Report broken `[[wikilinks]]` after renames (but don't auto-fix cross-file references)
- **Scope limitation**: Only process files with pending git changes, not the entire repository

## Example Usage

```bash
# User invokes skill
/noteplan-manager:fix-filenames

# Claude creates tasks, auto-commits pending changes, then scans
Scanned 5 files with pending changes:

📋 Lists/
  Benefits 2 2.md     → Heading: "# 🏢📋 Benefits"     [WEIRD_CHARS + CONFLICT]
  Benefits 2 8 2.md   → Heading: "# 🏢📋 Benefits"     [WEIRD_CHARS + CONFLICT]
  Benefits 3.md        → Heading: "# 🏢📋 Benefits"     [WEIRD_CHARS + CONFLICT]
  🏢260216🏁 Researching MCPs.md → Heading: "# 🏢260216🏁 Researching MCPs" [MISPLACED]

Analysis:
  3 files are NotePlan duplicates of Benefits.md (all CONFLICT - target exists)
  1 file has Plans-style naming in Lists folder

# Claude asks user via AskUserQuestion for each category
# User makes decisions
# Claude executes approved changes
# Claude validates diff
# Claude creates commit

Commit created: a1b2c3d
  "fix(noteplan): Fix filenames to match heading conventions"
```

## Related Skills

- **fix-work-emojis** - Fix emoji encoding in work plan files
- **fix-personal-emojis** - Fix emoji encoding in personal plan files
- **sync-header-emojis** - Sync header titles with parent folder emojis
- **create-note** - Create new notes following naming conventions (references this skill's conventions)
- **move-content** - Move content between notes with link preservation
- **analyze-structure** - Analyze NotePlan structure and naming patterns
