---
name: sort-dirs
description: Prefix each screenshot directory with its earliest screenshot date, making the folder chronologically sortable
---

# Sort Screenshot Directories by Date

You are a directory renaming tool. When invoked, you scan screenshot directories, find the earliest date in each (from screenshot filenames), and rename directories with a `YYYY-MM-DD ` prefix so the folder sorts chronologically.

**This skill is safe:** it shows a full preview table before making any renames, and confirms with the user before executing.

## What This Skill Does

1. Confirm the Screenshots root path
2. List all subdirectories
3. For each dir, find the earliest date from screenshot filenames
4. Present a rename preview table to the user
5. Execute approved renames
6. Verify the final directory listing

## Task Management (MANDATORY)

**Before doing any work, create all 4 tasks:**

```javascript
TaskCreate({
  subject: "Scan — list directories and compute proposed renames",
  description: "List all subdirectories under Screenshots root. For each dir, extract dates from filenames matching 'Screenshot YYYY-MM-DD'. Use earliest found date as the prefix. For dirs with no screenshots (PDFs only), flag them for per-dir handling. Skip dirs already starting with a date (YYYY-MM-DD pattern).",
  activeForm: "Scanning directories"
})

TaskCreate({
  subject: "Present rename table and get user confirmation",
  description: "Show a table: Current Name → Proposed Name for all directories. For dirs with no screenshot dates, ask per-dir via AskUserQuestion. Get user approval before any renames.",
  activeForm: "Presenting rename preview"
})

TaskCreate({
  subject: "Execute approved renames",
  description: "Rename directories using mv. Only rename dirs the user approved. Skip any explicitly skipped by user.",
  activeForm: "Renaming directories"
})

TaskCreate({
  subject: "Verify final directory listing",
  description: "List the Screenshots root after all renames to confirm the result looks correct.",
  activeForm: "Verifying result"
})
```

**Set up dependencies (sequential):**

```javascript
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Workflow

### Step 0: Task Setup

Create all 4 tasks with dependencies. Run `TaskList()` to show the plan.

### Step 1: Confirm Root Path

Use `AskUserQuestion`:
- header: "Screenshots folder"
- question: "Which folder should I scan for screenshot directories?"
- options:
  - `~/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots` (label: "Default OneDrive location")
  - `Other (enter path)` (label: "Other location")

Expand `~` to `$HOME` for all bash commands.

Mark Task 1 as in_progress, then begin scanning.

### Step 2 (Task 1): Scan Directories

```bash
SCREENSHOTS_ROOT="$HOME/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots"

# List subdirectories
ls -1 "$SCREENSHOTS_ROOT"
```

For each subdirectory:

**Check if already prefixed (idempotent check):**
```bash
# Skip if name already starts with a date like YYYY-MM-DD
echo "$dir_name" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
```

**Find earliest date from screenshot filenames:**
```bash
# Extract dates from filenames matching "Screenshot YYYY-MM-DD"
ls "$SCREENSHOTS_ROOT/$dir_name" 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort | head -1
```

**Fallback: use earliest file modification time (for non-screenshot files):**
```bash
# Only use if no screenshot date found
stat -f "%Sm" -t "%Y-%m-%d" "$SCREENSHOTS_ROOT/$dir_name"/* 2>/dev/null | sort | head -1
```

Build a list:
```
dir_name        | earliest_date | source        | status
Agents in Azure | 2026-02-05    | filename      | will rename
Trainings       | 2026-01-22    | filename      | will rename
Slides          | (none found)  | no screenshots| needs manual input
```

Mark Task 1 as completed.

### Step 3 (Task 2): Present Preview and Confirm

Mark Task 2 as in_progress.

**For dirs with screenshot dates found**, present a preview table:

```
Current Name           → Proposed Name
─────────────────────────────────────────────────────
Agents in Azure        → 2026-02-05 Agents in Azure
Agents in Servicenow   → 2026-02-09 Agents in Servicenow
Canceling NYC Trip     → 2026-02-20 Canceling NYC Trip
Claude Usage           → 2026-02-13 Claude Usage
GSIP Workshop          → 2026-02-10 GSIP Workshop
Requesting Feedback    → 2026-02-13 Requesting Feedback
SF Trip                → 2026-02-16 SF Trip
Trainings              → 2026-01-22 Trainings
Update Set POC         → 2026-02-18 Update Set POC
```

**For dirs with no screenshot dates (PDFs only or empty)**, handle per-dir with `AskUserQuestion`:
- header: "No date found"
- question: "Directory '`<dir_name>`' has no screenshot filenames (files: `<file_list>`). How should I handle it?"
- options:
  - "Skip (don't rename)"
  - "Use earliest file date (`<mtime_date>`)"
  - "Enter date manually"

Use `AskUserQuestion` to confirm the full rename plan:
- header: "Confirm renames"
- question: "Ready to rename `N` directories with date prefixes. Proceed?"
- options:
  - "Rename all listed above"
  - "Skip specific directories (I'll tell you which)"
  - "Abort"

If user wants to skip specific dirs, ask which ones to skip.

Mark Task 2 as completed.

### Step 4 (Task 3): Execute Renames

Mark Task 3 as in_progress.

For each approved rename:

```bash
SCREENSHOTS_ROOT="$HOME/Library/CloudStorage/OneDrive-ServiceNow/📸 Screenshots"

mv "$SCREENSHOTS_ROOT/Agents in Azure" "$SCREENSHOTS_ROOT/2026-02-05 Agents in Azure"
mv "$SCREENSHOTS_ROOT/Trainings" "$SCREENSHOTS_ROOT/2026-01-22 Trainings"
# ... etc
```

Report each rename as it completes, or report any failures.

Mark Task 3 as completed.

### Step 5 (Task 4): Verify

Mark Task 4 as in_progress.

```bash
ls -1 "$SCREENSHOTS_ROOT"
```

Show the final directory listing. Confirm that all renamed directories now appear with their date prefix.

Mark Task 4 as completed.

## Date Extraction Logic

**Primary:** Parse dates from screenshot filenames using the macOS screenshot naming convention:

```
Screenshot 2026-02-05 at 10.30.15 AM.png
Screenshot 2026-02-05 at 10.30.15 AM.jpg
```

Extract pattern: `[0-9]{4}-[0-9]{2}-[0-9]{2}` from the filename string.

**Fallback:** Use `stat` mtime if no filename-embedded dates exist.

**Skip condition:** Directory name already matches `^[0-9]{4}-[0-9]{2}-[0-9]{2}` — this skill is idempotent.

## Safety Rules

- **Never rename without user confirmation.** Always show the preview table first.
- **Idempotent:** Skip any directory already starting with a date.
- **Per-dir handling for edge cases:** Don't silently skip dirs with no dates — ask the user what to do.
- **No destructive changes:** This is a rename, not a delete. But still confirm first.

## Related Skills

- **group-related** — After sorting by date, analyze content and propose consolidation
- **introduce** — Overview of both skills
