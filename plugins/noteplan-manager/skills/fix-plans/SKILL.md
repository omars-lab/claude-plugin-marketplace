---
name: fix-plans
description: Fix plan file structure - standardize frontmatter, headers, emojis, and add missing standard elements across work and personal plan directories
---

# Fix Plan Structure

You are a NotePlan plan file structure fixer. When this skill is invoked, you'll scan plan files, detect structural issues (missing/old-style frontmatter, broken header hierarchies, missing self-referencing todos, emoji mismatches), and fix them without touching actual todo content.

## What This Skill Does

This skill:
1. **Scans plan files** in work and/or personal plan directories
2. **Detects structural issues** (missing frontmatter, old-style fields, broken headers)
3. **Infers missing data** from context (folder path, parent folder emoji, time-period folder)
4. **Presents inferred values** for user approval before making changes
5. **Fixes structure** (frontmatter, headers, self-referencing todos, emoji consistency, bullet normalization)
6. **Validates changes** via git diff to ensure no todo content was modified

## Note Map Integration

Before running, check for `🗺️ Note Map.md` to get structure context:

```bash
NOTE_MAP="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🗺️ Note Map.md"
```

- **If the map exists**: read the "Key Structural Facts" section to get paths, folder names, and workstream/reference-file lists. Use those discovered values instead of the hardcoded defaults below.
- **If the map is missing**: proceed with the defaults below, then warn:
  > ⚠️  No `🗺️ Note Map.md` found. Run `/noteplan-manager:discover-structure` to generate it and make this skill structure-aware.
- **If structural discrepancy detected** (e.g. a workstream or folder listed in the map no longer exists on disk): report the diff and offer to refresh the map via `/noteplan-manager:discover-structure`.

## Scope Selection

When invoked, first ask the user which directories to process using `AskUserQuestion`:

```
Which plan directories should I fix?

- Work plans (🏢 ServiceNow/📆 Plans/)
- Personal plans (🏡 Personal/🏡📆 Plans/)
- Both
```

## Plan File Standards

### Work Plan Frontmatter (Canonical)

From template `@Templates/🏢📆 Work Plan.md`:

```yaml
---
doctype: 📆
status: <status-emoji>
started: <YYYY-MM-DD>
namespace: 🏢
workstream: <workstream-emoji>
---
```

**Required fields:** `doctype`, `status`, `started`, `namespace`, `workstream`

### Personal Plan Frontmatter (Canonical)

From template `@Templates/🏡📆 Personal Plan.md`:

```yaml
---
doctype: 📆
status: <status-emoji>
started: <YYMMDD>
namespace: 🏡
plantype: <plantype-emoji>
---
```

**Required fields:** `doctype`, `status`, `started`, `namespace`, `plantype`

### Work Plan Naming Convention

```
🏢YYMMDD<workstream-emoji> Title.md
```

Example: `🏢260118🏁 ServiceNow Onboarding Emails.md`

### Personal Plan Naming Convention

```
🏡YYMMDD<plantype-emoji> Title.md
```

Example: `🏡260115⚙️ Automating Home Setup.md`

### Workstream Emojis (Work)

| Emoji | Workstream |
|---|---|
| `🧑🏻‍💻` | Development |
| `🎯` | Impact |
| `🏁` | Onboarding |
| `✈️` | Travel |
| `🖥️` | Workspace |

### Plantype Emojis (Personal)

| Emoji | Plantype |
|---|---|
| `⚖️` | Deciding |
| `⚙️` | Automating |
| `✈️` | Traveling |
| `❓` | Questioning |
| `🎉` | Celebration |
| `🎒` | Activities |
| `🏃🏻` | Health |
| `🏠` | Home |
| `🏢` | Career |
| `👨🏻‍🏫` | Mentorship |
| `👨🏻‍💻` | Development |
| `👨🏻‍💼` | Entrepreneurship |
| `👨🏻‍🔧` | Fixing |
| `💰` | Assets |
| `📊` | Tracking |
| `📑` | Paperwork |
| `📚` | Education / Learning |
| `📝` | Authoring / Blogging |
| `🔍` | Discovering |
| `🗣️` | Communicating |
| `🛒` | Shopping |
| `🧎🏻` | Spirituality |
| `🧑‍🧑‍🧒‍🧒` | Family |
| `🧮` | Managing |
| `🧰` | Craftsmanship |
| `🪵` | Backlogs |

### Status Emojis

| Emoji | Status |
|---|---|
| `🔮` | Future |
| `🚦` | Ready |
| `🟢` | Started |
| `🟡` | Paused |
| `🔴` | Blocked |
| `❎` | Canceled |
| `✅` | Done |

### Standard Plan Structure

Every plan file should have:

1. **Frontmatter block** with all required fields (using `---` delimiters)
2. **Title heading** as `# 🏢YYMMDD<emoji> Title` (only ONE `#` heading in the file)
3. **Self-referencing todo** immediately after the title: `* [ ] Is [[<title>]] done? >YYYY-WN`
4. **Sub-sections** using `##` (never `#` for sub-sections)
5. **Consistent bullet style** (either `*` or `-` throughout, not mixed)

## Issue Classification

When scanning files, classify each issue:

| Classification | Description | Example |
|---|---|---|
| `FRONTMATTER_MISSING` | No frontmatter block at all | File starts with `# Title` directly |
| `FRONTMATTER_OLD_STYLE` | Uses old field names | `Project: Onboarding` instead of `workstream: 🏁` |
| `FRONTMATTER_INCOMPLETE` | Has frontmatter but missing required fields | Has `doctype` but no `workstream` |
| `HEADER_HIERARCHY` | Sub-sections use `#` instead of `##` | `# Tasks` should be `## Tasks` |
| `MISSING_SELF_REF` | No self-referencing todo after title | Missing `* [ ] Is [[title]] done?` line |
| `EMOJI_MISMATCH` | Filename emoji doesn't match frontmatter/header | Filename has `🏁` but frontmatter says `workstream: 🎯` |
| `STATUS_EMOJI_MISSING` | Personal plan H1 title is missing status emoji as 2nd emoji | `# 🏡260117👨🏻‍💻 Title` should be `# 🏡🟢260117👨🏻‍💻 Title` |
| `MIXED_BULLETS` | File uses both `*` and `-` for bullets | Some lines `* item`, others `- item` |
| `FILENAME_MISMATCH` | Filename doesn't match heading (defer to fix-filenames) | Report only, don't fix |
| `OK` | File passes all structural checks | No action needed |

A single file can have multiple issues.

## Frontmatter Inference Rules

When frontmatter fields are missing, infer from context:

### `namespace`
- File is under `🏢 ServiceNow/` -> `🏢`
- File is under `🏡 Personal/` -> `🏡`

### `doctype`
- Always `📆` (these are plan files)

### `workstream` (work plans only)
- Extract emoji from parent folder name
- Example: parent folder `🏁 Onboarding` -> `workstream: 🏁`

### `plantype` (personal plans only)
- Extract emoji from parent folder name or filename pattern
- Example: filename `🏡260115⚙️ Automating.md` -> `plantype: ⚙️`
- Example: parent folder `⚙️ Automating` -> `plantype: ⚙️`

### `status`
- Read from existing frontmatter `status:` field if present
- If frontmatter `status:` is missing: check H1 title — if 2nd emoji is a status emoji (`🔮🚦🟢🟡🔴❎✅`), use that
- If still missing: prompt user — do NOT infer from folder structure (personal plans are now flat; time-period folders no longer exist)

### `started`
- Extract from filename date pattern `YYMMDD`
- Example: `🏢260118🏁 Title.md` -> `started: 2026-01-18` (work) or `started: 260118` (personal)
- If no date in filename: use git file creation date or today's date

### Old-Style Field Mapping

| Old Field | Maps To |
|---|---|
| `Project:` | `workstream:` (extract emoji from value or folder) |
| `Created:` | `started:` |
| `Type:` | `doctype: 📆` |
| `Status:` (text) | `status:` (convert to emoji) |

## Git Safety and Task Management

### Task Management (MANDATORY)

This skill **MUST** use task management to track progress. Tasks are not optional.

**BEFORE starting any work, create all 10 tasks with proper dependencies:**

#### Task Creation (Step 0 - Do this FIRST)

```javascript
// Task #1: Select plan directory scope
TaskCreate({
  subject: "Select plan directory scope",
  description: "Ask user which directories to process using AskUserQuestion.\n\nOptions:\n- Work plans (🏢 ServiceNow/📆 Plans/)\n- Personal plans (🏡 Personal/🏡📆 Plans/)\n- Both\n\nStore selection for use in subsequent tasks.",
  activeForm: "Selecting plan directory scope"
})

// Task #2: Pre-commit pending changes
TaskCreate({
  subject: "Pre-commit pending content changes",
  description: "Auto-commit all pending changes to create a clean baseline checkpoint for diffing later.\n\nActions:\n- Run git status --short to capture current state\n- git add -A && git commit all pending changes with descriptive message\n- Record the commit hash as CHECKPOINT_COMMIT\n- This creates a clean baseline for validation in Task #9\n\nIMPORTANT: This is an auto-commit, do NOT prompt the user.",
  activeForm: "Pre-committing pending changes"
})

// Task #3: Scan plan files and read content
TaskCreate({
  subject: "Scan plan files and read content",
  description: "Scan all .md files in selected plan directories.\n\nActions:\n- List all .md files in selected plan directories (recursively)\n- Skip @Trash/ files\n- For each file: read content, extract frontmatter, extract # Title heading\n- Build inventory: {filepath, filename, frontmatter_fields, heading, folder_context, parent_folder}\n\nThis is a read-only scan step.",
  activeForm: "Scanning plan files"
})

// Task #4: Analyze structural issues
TaskCreate({
  subject: "Analyze structural issues",
  description: "For each scanned file, check all structural aspects.\n\nChecks:\n- Frontmatter present? Complete? Old-style fields?\n- Header hierarchy correct? (only one #, sub-sections use ##)\n- Self-referencing todo present after title?\n- Emoji consistency (filename vs frontmatter vs heading)\n- Bullet consistency (* vs - mixed?)\n- Filename matches heading? (report only, defer to fix-filenames)\n\nClassify each issue: FRONTMATTER_MISSING, FRONTMATTER_OLD_STYLE, FRONTMATTER_INCOMPLETE, HEADER_HIERARCHY, MISSING_SELF_REF, EMOJI_MISMATCH, MIXED_BULLETS, FILENAME_MISMATCH, OK\n\nFor missing fields, apply inference rules to determine values.\n\nBuild categorized report with proposed fixes and inferred values.",
  activeForm: "Analyzing structural issues"
})

// Task #5: Present findings and proposed fixes
TaskCreate({
  subject: "Present findings and proposed fixes",
  description: "Show categorized report of all issues found using AskUserQuestion.\n\nPresent:\n- Summary: N files scanned, M issues found across K files\n- By category: count of each issue type\n- Inferred values: show what was inferred and from what context\n- Proposed fixes: list each fix that will be applied\n\nAsk user to approve fixes. Show inferred values clearly so user can verify.\n\nCollect all user decisions before proceeding to fix tasks.",
  activeForm: "Presenting findings"
})

// Task #6: Fix frontmatter (delegates to fix-frontmatter skill tooling)
TaskCreate({
  subject: "Fix frontmatter (add/correct fields)",
  description: "Run fix_frontmatter.py from the fix-frontmatter skill on the plan files identified in Task #3.\n\nThe script handles parse → fix → re-validate roundtrip automatically.\n\nActions:\n- MISSING: infers and adds complete frontmatter block with --- delimiters\n- OLD_STYLE: replaces old field names with canonical names\n- INCOMPLETE: adds missing fields using inference rules\n\nSurface any `unfixable` fields to the user before proceeding to Task #7.\n\nCross-reference: Frontmatter fixes are powered by `fix-frontmatter` skill tooling.\n\nFrontmatter uses --- delimiters. Place before # Title heading.\n\nDo NOT modify any content below the frontmatter and heading.",
  activeForm: "Fixing frontmatter"
})

// Task #7: Fix headers and add self-referencing todo
TaskCreate({
  subject: "Fix headers and add self-referencing todo",
  description: "For each file with header/self-ref issues:\n\n- HEADER_HIERARCHY: Change sub-section # headers to ## (keep the first # Title as-is)\n- MISSING_SELF_REF: Add self-referencing todo line after the # Title heading\n  Format: * [ ] Is [[<title>]] done? >YYYY-WN\n  Where <title> is the heading text without #, and YYYY-WN is derived from started date\n\nOnly add new lines for self-ref todos. Only change # to ## for sub-sections.\nDo NOT modify any todo text, links, or note content.",
  activeForm: "Fixing headers"
})

// Task #8: Fix emojis and normalize bullets
TaskCreate({
  subject: "Fix emojis and normalize bullets",
  description: "For each file with emoji/bullet issues:\n\n- EMOJI_MISMATCH: Ensure filename emoji matches frontmatter field and heading title emoji\n  (Only fix frontmatter and heading to match filename - defer filename renames to fix-filenames)\n- MIXED_BULLETS: Determine dominant bullet style per file (* or -), normalize all to dominant\n  Count * bullets vs - bullets, use whichever has more\n\nDo NOT modify todo text content, only bullet characters.",
  activeForm: "Fixing emojis and bullets"
})

// Task #9: Validate git diff
TaskCreate({
  subject: "Validate git diff",
  description: "CRITICAL validation step.\n\nActions:\n- Run git diff CHECKPOINT_COMMIT to see ALL changes since pre-commit\n- Verify ONLY these types of changes occurred:\n  - Frontmatter block changes (added/modified fields within -- delimiters)\n  - Header level changes (# -> ##)\n  - Added self-referencing todo lines (new lines, not modified lines)\n  - Bullet character swaps (* <-> -)\n  - Emoji corrections in frontmatter/heading only\n- Flag if ANY actual todo text, links, or note content was modified\n- If unexpected changes found: STOP and report to user, do NOT proceed to commit\n\nShow validation summary with counts of each change type.",
  activeForm: "Validating changes"
})

// Task #10: Create git commit
TaskCreate({
  subject: "Create git commit",
  description: "Only proceed if Task #9 validation passes.\n\nActions:\n- Stage all changes\n- Create commit with descriptive message listing:\n  - Number of files with frontmatter fixes\n  - Number of header hierarchy fixes\n  - Number of self-referencing todos added\n  - Number of bullet normalizations\n  - Number of emoji corrections\n- Include 'Validated via git diff' note\n- Include skill name and co-author\n\nIf validation failed in Task #9, do NOT commit - report issues instead.",
  activeForm: "Creating git commit"
})
```

#### Set Up Task Dependencies

**After creating all 10 tasks, set up dependencies:**

```javascript
// Task #2 depends on #1 (need scope selection first)
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })

// Task #3 depends on #2 (need clean baseline first)
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })

// Task #4 depends on #3 (need scan results to analyze)
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })

// Task #5 depends on #4 (need analysis to present)
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })

// Tasks #6, #7, #8 depend on #5 (need user approval, run in parallel)
TaskUpdate({ taskId: "6", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "7", addBlockedBy: ["5"] })
TaskUpdate({ taskId: "8", addBlockedBy: ["5"] })

// Task #9 depends on #6, #7, #8 (validate after all fixes)
TaskUpdate({ taskId: "9", addBlockedBy: ["6", "7", "8"] })

// Task #10 depends on #9 (commit only if validation passes)
TaskUpdate({ taskId: "10", addBlockedBy: ["9"] })
```

#### Task Dependency Flow

```
#1  Select plan directory scope
 └─► #2  Pre-commit pending changes
      └─► #3  Scan plan files and read content
           └─► #4  Analyze structural issues
                └─► #5  Present findings and proposed fixes
                     ├─► #6  Fix frontmatter ────────────────┐
                     ├─► #7  Fix headers and self-ref todo ──┤
                     └─► #8  Fix emojis and normalize bullets ┤
                                                              │
                          #9  Validate git diff ◄─────────────┘
                           └─► #10 Create git commit
```

Tasks #6, #7, #8 run in parallel after #5 approval.

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
1. Create 10 tasks (see Task Management section for exact definitions)
2. Set up task dependencies using TaskUpdate
3. Run TaskList to show workflow to user
4. Mark Task #1 as in_progress to begin work
```

**Display task plan to user:**
```
Plan Structure Fix - Task Workflow (10 Tasks)

#1  Select plan directory scope [STARTING]
 └─► #2  Pre-commit pending changes
      └─► #3  Scan plan files and read content
           └─► #4  Analyze structural issues
                └─► #5  Present findings and proposed fixes
                     ├─► #6  Fix frontmatter
                     ├─► #7  Fix headers and self-ref todo
                     └─► #8  Fix emojis and bullets
                          └─► #9  Validate git diff
                               └─► #10 Create git commit

Ready to begin!
```

### **Step 1 (Task #1): Select Scope**

Mark task as in_progress, then ask user:

Use `AskUserQuestion`:
```
Which plan directories should I fix?

- Work plans (🏢 ServiceNow/📆 Plans/)
- Personal plans (🏡 Personal/🏡📆 Plans/)
- Both
```

Store the selected directories for subsequent tasks.

**Work plans directory:**
```
$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans
```

**Personal plans directory:**
```
$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans
```

**Note:** After running `flatten-plans`, personal plans are organized in flat workstream folders directly under `🏡📆 Plans/` — there are no longer Future/, Present/, Past/, or Paused/ subfolders.

**Complete Task #1 and start Task #2.**

### **Step 2 (Task #2): Pre-commit Pending Changes**

```javascript
TaskUpdate({ taskId: "1", status: "completed" })
TaskUpdate({ taskId: "2", status: "in_progress" })
```

Auto-commit all pending changes:

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Check current state
git status --short

# Stage and commit everything
git add -A
git commit -m "chore(noteplan): Auto-commit pending changes before plan structure fixes

[Describe what changes were pending based on git status output]

Auto-committed by fix-plans skill to create clean baseline.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

**Record the commit hash as `CHECKPOINT_COMMIT`** for validation later:
```bash
CHECKPOINT_COMMIT=$(git rev-parse HEAD)
```

**This is an auto-commit. Do NOT prompt the user.**

**Complete Task #2 and start Task #3.**

### **Step 3 (Task #3): Scan Plan Files**

```javascript
TaskUpdate({ taskId: "2", status: "completed" })
TaskUpdate({ taskId: "3", status: "in_progress" })
```

List all `.md` files in selected plan directories:

```bash
# For work plans
find "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans" -name "*.md" -type f

# For personal plans
find "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans" -name "*.md" -type f
```

**For each file:**
1. Read the file content
2. Extract frontmatter (between `---` delimiters)
3. Extract `# Title` heading
4. Determine parent folder (workstream/plantype context)
5. Record: `{filepath, filename, frontmatter, heading, parent_folder, folder_context}`

**Report scan results:**
```
Scanned N plan files:

Work Plans (📆 Plans/):
  🏁 Onboarding/ - 5 files
  🎯 Impact/ - 3 files
  🧑🏻‍💻 Development/ - 2 files
  ...

Personal Plans (🏡📆 Plans/):
  ⚙️ Automating/ - 4 files
  📚 Learning/ - 6 files
  ...

Total: N files to analyze
```

**Complete Task #3 and start Task #4.**

### **Step 4 (Task #4): Analyze Structural Issues**

```javascript
TaskUpdate({ taskId: "3", status: "completed" })
TaskUpdate({ taskId: "4", status: "in_progress" })
```

For each scanned file, check:

1. **Frontmatter presence and completeness**
   - Is there a `---` delimited frontmatter block?
   - Are all required fields present? (`doctype`, `status`, `started`, `namespace`, `workstream`/`plantype`)
   - Are there old-style fields? (`Project:`, `Created:`, etc.)

2. **Header hierarchy**
   - Is there exactly one `# Title` heading?
   - Are sub-sections using `##` (not `#`)?

3. **Self-referencing todo**
   - Is there a `* [ ] Is [[<title>]] done?` line after the heading?

4. **Emoji consistency**
   - Does filename emoji match frontmatter field?
   - Does filename emoji match heading emoji?
   - For personal plans: does H1 title have a status emoji as the 2nd emoji (one of `🔮🚦🟢🟡🔴❎✅`)? Classify missing status emoji as `STATUS_EMOJI_MISSING` — report to user but defer fix to `update-plan-status` skill.

5. **Bullet consistency**
   - Are bullets uniformly `*` or `-`?
   - Count each type to determine dominant style

6. **Filename match** (report only)
   - Does filename match heading? (defer fix to fix-filenames)

**Apply inference rules** for any missing fields and record what was inferred and from where.

**Build categorized report:**
```
Analysis Complete - M issues found across K files:

FRONTMATTER_MISSING (2 files):
  🏢260118🏁 Onboarding Emails.md - No frontmatter block
  🏡260115⚙️ Home Automation.md - No frontmatter block

FRONTMATTER_OLD_STYLE (1 file):
  🏢260120🎯 Goals Review.md - Has 'Project:' and 'Created:' fields

FRONTMATTER_INCOMPLETE (3 files):
  🏢260122🧑🏻‍💻 API Work.md - Missing: workstream, started
  ...

HEADER_HIERARCHY (4 files):
  🏢260118🏁 Onboarding Emails.md - 3 sub-sections using # instead of ##

MISSING_SELF_REF (5 files):
  🏢260118🏁 Onboarding Emails.md - No self-referencing todo

EMOJI_MISMATCH (1 file):
  🏢260120🏁 Impact Work.md - Filename has 🏁, frontmatter says workstream: 🎯

MIXED_BULLETS (2 files):
  🏢260118🏁 Onboarding Emails.md - 12 * bullets, 3 - bullets

FILENAME_MISMATCH (1 file) [report only]:
  Old Title.md - Heading says "# 🏢260118🏁 New Title"
  (Defer to fix-filenames)

OK (8 files):
  No issues found

Inferred Values:
  🏢260118🏁 Onboarding Emails.md:
    namespace: 🏢 (from path: 🏢 ServiceNow/)
    doctype: 📆 (plan file)
    workstream: 🏁 (from parent folder: 🏁 Onboarding)
    started: 2026-01-18 (from filename date: 260118)
    status: 🟢 (default: Started)
```

**Complete Task #4 and start Task #5.**

### **Step 5 (Task #5): Present Findings**

```javascript
TaskUpdate({ taskId: "4", status: "completed" })
TaskUpdate({ taskId: "5", status: "in_progress" })
```

Present using `AskUserQuestion`:

```
Plan Structure Analysis Complete

Scanned: N files
Issues found: M across K files

Fixes to apply:
- Add frontmatter to 2 files
- Convert old-style frontmatter in 1 file
- Add missing fields to 3 files
- Fix header hierarchy in 4 files (# -> ##)
- Add self-referencing todo to 5 files
- Fix emoji mismatch in 1 file (frontmatter/heading only)
- Normalize bullets in 2 files

Inferred values (please verify):
  namespace: 🏢 (5 files), 🏡 (3 files)
  workstream: 🏁 (3), 🎯 (1), 🧑🏻‍💻 (1)
  status: 🟢 (4), ✅ (1)

1 filename mismatch will be deferred to fix-filenames.

Apply these structural fixes?
- Yes, apply all fixes
- Show details per file
- Skip (cancel)
```

**Collect all user decisions before proceeding.**

**Complete Task #5 and start Tasks #6, #7, #8 in parallel.**

### **Step 6 (Tasks #6, #7, #8): Apply Fixes in Parallel**

```javascript
TaskUpdate({ taskId: "5", status: "completed" })
TaskUpdate({ taskId: "6", status: "in_progress" })
TaskUpdate({ taskId: "7", status: "in_progress" })
TaskUpdate({ taskId: "8", status: "in_progress" })
```

#### Task #6: Fix Frontmatter (via fix-frontmatter skill tooling)

Run `fix_frontmatter.py` from the `fix-frontmatter` skill on the plan files identified in Task #3. The script handles parse → fix → re-validate automatically.

```bash
SCRIPTS_DIR="$HOME/.claude/plugins/noteplan-manager/skills/fix-frontmatter/scripts"

# Fix all plan files in scope (example: both directories)
python3 "$SCRIPTS_DIR/fix_frontmatter.py" "$WORK_PLANS" --recursive --format json
python3 "$SCRIPTS_DIR/fix_frontmatter.py" "$PERSONAL_PLANS" --recursive --format json
```

The script handles:
- **FRONTMATTER_MISSING**: Adds complete `---`-delimited frontmatter with inferred values
- **FRONTMATTER_OLD_STYLE**: Replaces old field names with canonical names
- **FRONTMATTER_INCOMPLETE**: Adds missing fields using inference rules

**Surface any `unfixable` fields** from the JSON output to the user before proceeding to Task #7. These are fields that could not be inferred automatically and need manual input.

Example output parsing:
```json
[{"file": "...", "changes": [...], "remaining_issues": [
  {"type": "missing_field", "field": "status",
   "reason": "cannot infer — no H1 emoji found"}
]}]
```

Do NOT modify content below frontmatter and heading.

#### Task #7: Fix Headers and Self-Referencing Todo

**HEADER_HIERARCHY:** For each sub-section `#` that is NOT the title, change to `##`:
```
Before:
# 🏢260118🏁 Title
...
# Tasks
# Notes

After:
# 🏢260118🏁 Title
...
## Tasks
## Notes
```

**MISSING_SELF_REF:** Add self-referencing todo immediately after the `# Title` heading:
```
# 🏢260118🏁 Title
* [ ] Is [[🏢260118🏁 Title]] done? >2026-W04
```

The week reference `>YYYY-WN` is derived from the `started` date.

Only ADD new lines. Do NOT modify existing todo text.

#### Task #8: Fix Emojis and Normalize Bullets

**EMOJI_MISMATCH:** Correct frontmatter and heading to match filename emoji:
- If filename has `🏁` but frontmatter says `workstream: 🎯`, fix frontmatter to `workstream: 🏁`
- If heading emoji doesn't match filename emoji, fix heading
- Do NOT rename files (defer to fix-filenames)

**MIXED_BULLETS:** Count `*` vs `-` bullets, normalize to dominant style:
```
File has 12 * bullets and 3 - bullets -> normalize to *
Change: - item -> * item (for 3 lines)
```

Only change the bullet character. Do NOT modify bullet content.

**Complete Tasks #6, #7, #8 and start Task #9:**
```javascript
TaskUpdate({ taskId: "6", status: "completed" })
TaskUpdate({ taskId: "7", status: "completed" })
TaskUpdate({ taskId: "8", status: "completed" })
TaskUpdate({ taskId: "9", status: "in_progress" })
```

### **Step 7 (Task #9): Validate Diff**

**CRITICAL: Validate ALL changes since pre-commit:**

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Show all changes since checkpoint
git diff $CHECKPOINT_COMMIT --stat
git diff $CHECKPOINT_COMMIT
```

**Verify ONLY these types of changes occurred:**
- Frontmatter block added or fields changed (within `---` delimiters)
- Header level changes (`#` -> `##` for sub-sections only)
- New self-referencing todo lines added (entirely new lines)
- Bullet character swaps (`*` <-> `-`)
- Emoji corrections in frontmatter fields or heading line only

**Flag if ANY of these occurred (UNEXPECTED):**
- Todo text modified (any `* [ ]` or `* [x]` line content changed)
- Links modified (`[[...]]` content changed)
- Note body content added, removed, or changed
- Lines deleted (other than old-style frontmatter fields being replaced)

**Show validation summary:**
```
Validating changes since checkpoint [HASH]...

Frontmatter added/fixed: 6 files
Headers fixed (# -> ##): 12 occurrences in 4 files
Self-referencing todos added: 5 new lines
Bullets normalized: 3 lines in 2 files
Emoji corrections: 1 file

No unexpected content changes detected.
Validation PASSED.

-- OR --

UNEXPECTED CHANGE in 🏢260118🏁 Onboarding Emails.md line 42:
  - * [ ] Send welcome email to team
  + * [ ] Send welcome emails to team
Content was modified beyond structural fixes!
STOPPING - please review before committing.
```

**If validation PASSES**: Complete Task #9 and start Task #10.
**If validation FAILS**: STOP. Report to user. Do NOT proceed to commit.

### **Step 8 (Task #10): Create Git Commit**

```javascript
TaskUpdate({ taskId: "9", status: "completed" })
TaskUpdate({ taskId: "10", status: "in_progress" })
```

**Only proceed if Task #9 validation passed.**

```bash
cd "$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Stage all changes
git add -A

# Create commit
git commit -m "$(cat <<'EOF'
fix(noteplan): Fix plan file structure and standardize frontmatter

- Added/fixed frontmatter in X files
- Fixed header hierarchy in Y files (# -> ## for sub-sections)
- Added self-referencing todos to Z files
- Normalized bullet style in N files
- Corrected emoji mismatches in M files

Validated via git diff: only structural changes, no todo content modified.
Skill: fix-plans

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**Adjust the commit message to reflect actual changes made.**

**Complete Task #10 and show final summary:**

```javascript
TaskUpdate({ taskId: "10", status: "completed" })
TaskList() // Show all tasks completed
```

```
Plan Structure Fix Complete!

Task #1:  Selected scope: [Work/Personal/Both]
Task #2:  Pre-committed pending changes
Task #3:  Scanned N plan files
Task #4:  Analyzed structural issues (M issues in K files)
Task #5:  Presented fixes, user approved
Task #6:  Fixed frontmatter in X files
Task #7:  Fixed headers in Y files, added Z self-ref todos
Task #8:  Normalized bullets in N files, fixed M emoji mismatches
Task #9:  Validated diff - no unexpected changes
Task #10: Created git commit [HASH]

All tasks completed!
```

## Safety Checks

- **No content modification**: NEVER modify todo text, links, or note body content - only frontmatter, headers, self-referencing todos, bullet characters, and emoji fields
- **Pre-commit**: Always auto-commit pending changes before making structural fixes
- **Inference approval**: Always show inferred values to user before applying them
- **Diff validation**: Always validate git diff before committing - only structural changes should appear
- **User approval**: Always present proposed changes and get explicit approval before executing
- **Filename deference**: Report filename mismatches but defer actual renames to fix-filenames skill
- **Frontmatter delimiters**: Plan files use `---` (triple dash) for frontmatter
- **Self-ref format**: Self-referencing todo uses `* [ ] Is [[title]] done? >YYYY-WN` format exactly
- **One # heading**: Only the title uses `#`, all sub-sections must use `##` or deeper

## Example Usage

```bash
# User invokes skill
/noteplan-manager:fix-plans

# Claude creates 10 tasks, asks for scope
Which plan directories should I fix?
> Both

# Claude auto-commits, scans 25 plan files
Scanned 25 plan files (15 work, 10 personal)

# Claude analyzes and reports
Analysis Complete - 18 issues found across 12 files:
  FRONTMATTER_MISSING: 2 files
  FRONTMATTER_INCOMPLETE: 4 files
  HEADER_HIERARCHY: 3 files
  MISSING_SELF_REF: 7 files
  MIXED_BULLETS: 2 files

# Claude presents inferred values for approval
Inferred frontmatter values:
  🏢260118🏁 Onboarding Emails.md:
    namespace: 🏢 (from path)
    workstream: 🏁 (from folder: 🏁 Onboarding)
    started: 2026-01-18 (from filename)
    status: 🟢 (default)

Apply fixes? > Yes

# Claude fixes in parallel (Tasks #6, #7, #8)
# Claude validates diff
# Claude creates commit

Commit created: a1b2c3d
  "fix(noteplan): Fix plan file structure and standardize frontmatter"
```

## Related Skills

- **fix-filenames** - Fix filenames to match heading conventions (handles FILENAME_MISMATCH issues reported by this skill)
- **update-plan-status** - Change plan status (frontmatter + H1 emoji + filename rename); handles STATUS_EMOJI_MISSING issues reported by this skill
- **flatten-plans** - One-time migration from Future/Present/Past/Paused folder structure to flat workstream layout
- **fix-work-emojis** - Fix emoji encoding in work plan files
- **fix-personal-emojis** - Fix emoji encoding in personal plan files
- **sync-header-emojis** - Sync header titles with parent folder emojis
- **sync-plan-templates** - Keep plan templates in sync with workstream/plantype emojis
- **create-note** - Create new notes following naming conventions
- **analyze-structure** - Analyze NotePlan structure and naming patterns
