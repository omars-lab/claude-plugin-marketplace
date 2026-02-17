---
name: sync-header-emojis
description: Sync header title emojis to match parent folder emoji across all NotePlan files
---

# Sync Header Emojis

You are a NotePlan header emoji synchronizer. When this skill is invoked, you'll ensure that the emoji in file headers (# Title) matches the emoji from the parent folder, maintaining visual consistency across your NotePlan structure.

## What This Skill Does

This skill:
1. **Scans files** in a specified directory (or recursively)
2. **Extracts parent folder emoji** from the directory name
3. **Checks the first header** (# title) in each file
4. **Updates headers** to start with the parent folder emoji
5. **Preserves existing content** after the emoji
6. **Reports changes** made to files

## Problem This Solves

**Current state:** Files in `🧑🏻‍💻 Development` folder have headers like:
```markdown
# 🏢 260204 Deep Dive: Design Documentation Approach
```

**Desired state:** Headers should include the parent folder emoji:
```markdown
# 🧑🏻‍💻 260204 Deep Dive: Design Documentation Approach
```

This creates visual consistency and makes it clear which category/folder the note belongs to.

## NotePlan Structure

**Base path:**
```
/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/
```

**Example directories:**
- `🏢 ServiceNow/📆 Plans/🏁 Onboarding/` - Work plan files
- `🏢 ServiceNow/🔬 Research/🧑🏻‍💻 Development/` - Research notes
- `🏡 Personal/🏡📆 Plans/Present/` - Personal plans

## How It Works

### Step 1: Identify Target Directory

User provides directory to process:
```bash
# Specific directory
/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/🔬 Research/🧑🏻‍💻 Development

# Or process recursively from a parent
/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/🔬 Research
```

### Step 2: Extract Parent Folder Emoji

From the parent folder name, extract the leading emoji:

**Examples:**
- `🧑🏻‍💻 Development` → Extract: `🧑🏻‍💻`
- `🏁 Onboarding` → Extract: `🏁`
- `🔬 Research` → Extract: `🔬`
- `✈️ Travel` → Extract: `✈️`
- `Present` → No emoji (skip or use default)

**Emoji extraction pattern:**
1. Read folder name
2. Extract leading emoji(s) before first space
3. Handle complex emojis (skin tones, ZWJ sequences)
4. Stop at first non-emoji character

### Step 3: Scan Files in Directory

```bash
# Find all markdown files in directory
find "/path/to/directory" -maxdepth 1 -type f -name "*.md"
```

For each file:
1. Read the file content
2. Find the first header line (`# ...`)
3. Extract current emoji from header
4. Compare with parent folder emoji

### Step 4: Analyze Header

**Current header patterns:**

```markdown
# 🏢 260204 Deep Dive: Title
# 🏢260216🏁 Azure Agents POCs
# Deep Dive Outlook X-Callback-URLs
```

**Extract components:**
1. **Current emoji** (if any): `🏢`, `🏢`, or none
2. **Date** (optional): `260204`, `260216`
3. **Additional emojis**: `🏁` (in plan files)
4. **Title text**: The actual title

### Step 5: Determine Update Strategy

**Strategy 1: Replace namespace emoji with folder emoji**
```markdown
# 🏢 260204 Title      →  # 🧑🏻‍💻 260204 Title
```

**Strategy 2: Add folder emoji after namespace**
```markdown
# 🏢 260204 Title      →  # 🏢🧑🏻‍💻 260204 Title
```

**Strategy 3: Add folder emoji if no emoji exists**
```markdown
# 260204 Title         →  # 🧑🏻‍💻 260204 Title
# Deep Dive Title      →  # 🧑🏻‍💻 Deep Dive Title
```

**Default strategy:** Replace first emoji with folder emoji (Strategy 1)

**For plan files (special case):**
```markdown
# 🏢260216🏁 Azure Agents POCs  →  # 🏢260216🧑🏻‍💻 Azure Agents POCs
```
Keep namespace (🏢) and date, replace workstream emoji (🏁) with folder emoji (🧑🏻‍💻)

### Step 6: Update Headers

For each file needing updates:

1. **Read full file content**
2. **Find first header line**
3. **Replace header** with updated version
4. **Write file back**
5. **Preserve file metadata** (modification time optional)

## Git Safety and Task Management

### Pre-Work: Git Safety Check

Before making any changes, check for pending modifications:

```bash
# Check if NotePlan directory is in a git repo
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"

# Check git status
git status --short
```

If pending changes found:
```
⚠️  Found pending changes in NotePlan repository:

M  🏢 ServiceNow/🔬 Research/note1.md
M  🏡 Personal/note2.md

Would you like to commit these before syncing headers? (yes/no/show)

- yes: Create commit with pending changes first
- no: Continue without committing (changes will be mixed)
- show: Show detailed diff of pending changes
```

**Recommended:** Always commit pending changes first to keep work separated.

### Task Management

This skill uses task management to track progress:

**When invoked, create tasks for each major step:**
```
Task #1: Check git status and commit pending changes
Task #2: Identify target directories and extract folder emojis
Task #3: Scan files and analyze headers
Task #4: Update headers to match folder emojis
Task #5: Verify all changes
Task #6: Create git commit with changes
```

**Update task status as work progresses** to show user current step.

### Post-Work: Git Commit

After successfully syncing headers, create a commit:

```bash
# Stage modified files
git add [modified files]

# Create descriptive commit
git commit -m "feat(noteplan): Sync header emojis with folder structure

- Updated X file headers to match parent folder emojis
- Processed folders: [list]
- Synced headers in: [directories]

Skill: sync-header-emojis

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Commit message should include:**
- Number of files updated
- Directories/folders processed
- Specific emoji syncs performed
- Skill name for traceability

## Workflow

### When Invoked

```bash
/noteplan-manager:sync-header-emojis [directory]
```

**Options:**
- No directory: Ask user for target directory
- With directory: Process that directory
- With `--recursive`: Process all subdirectories

**0. Git safety and task setup:**
   - Check git status for pending changes
   - Offer to commit pending work
   - Create tasks for workflow steps
   - Mark first task as in_progress

### 1. Ask for Parameters

```
Where should I sync header emojis?

1. Specific directory: /path/to/folder
2. Recursive from: /path/to/parent
3. All work plans
4. All personal plans
5. Entire NotePlan structure

Choose option (1-5):
```

### 2. Ask for Strategy

```
How should I handle header emojis?

1. Replace existing emoji with folder emoji
2. Add folder emoji after namespace emoji
3. Prepend folder emoji (keep existing)

Choose strategy (1-3): [default: 1]
```

### 3. Scan and Analyze

```bash
Scanning: /Users/omar.eid/.../🧑🏻‍💻 Development

Parent folder emoji: 🧑🏻‍💻
Found 8 markdown files

Analyzing headers...
```

### 4. Report Findings

```
Header Analysis for 🧑🏻‍💻 Development:

Files needing updates:

1. Deep Dive Outlook X-Callback-URLs.md
   Current:  # 🏢 260129 Deep Dive: Outlook X-Callback-URLs
   Updated:  # 🧑🏻‍💻 260129 Deep Dive: Outlook X-Callback-URLs

2. Deep Dives Official MS Outlook MCP.md
   Current:  # 🏢 Deep Dives Official MS Outlook MCP
   Updated:  # 🧑🏻‍💻 Deep Dives Official MS Outlook MCP

3. Syncing Repos.md
   Current:  # Syncing Repos
   Updated:  # 🧑🏻‍💻 Syncing Repos

Files already correct: 5

Total changes: 3 files
```

### 5. Confirm Changes

```
Update these 3 headers? (yes/no/show)

- yes: Apply all changes
- no: Cancel
- show: Show full diff for each file
```

### 6. Apply Updates

```
Updating headers...

✅ Updated: Deep Dive Outlook X-Callback-URLs.md
✅ Updated: Deep Dives Official MS Outlook MCP.md
✅ Updated: Syncing Repos.md

Completed: 3 files updated
```

### 7. Create Git Commit

```
Creating git commit with header updates...

Files modified: 3
Folders processed:
- 🧑🏻‍💻 Development

Committing to git...
✅ Commit created: d4e5f6g
   "feat(noteplan): Sync header emojis with folder structure"

All tasks completed! ✅
```

**Mark all tasks as completed** when done.

## Special Cases

### Plan Files

Plan files have special naming and structure:
```markdown
# 🏢260216🏁 Azure Agents POCs
```

**Components:**
- `🏢` - Namespace
- `260216` - Date
- `🏁` - Workstream/plantype emoji
- `Azure Agents POCs` - Title

**Update strategy:**
Keep namespace and date, replace workstream emoji:
```markdown
# 🏢260216🏁 Azure Agents POCs  →  # 🏢260216🧑🏻‍💻 Azure Agents POCs
```

### Files Without Headers

If a file has no `#` header:
- **Option 1:** Skip (report as "no header found")
- **Option 2:** Add header at top using filename
- **Option 3:** Ask user what to do

Default: Skip and report

### Multiple Headers

If a file has multiple `#` headers (H1):
- Only update the **first** header
- Leave subsequent headers unchanged

### Folders Without Emojis

If parent folder has no emoji (e.g., "Notes", "Archive"):
- Skip files in that folder
- Report: "No emoji found in folder name"
- Don't modify headers

### Complex Emoji Sequences

Handle complex emojis carefully:
- **Skin tone modifiers:** `🧑🏻‍💻` (person + light skin + ZWJ + laptop)
- **ZWJ sequences:** `👨🏻‍🏫` (man + light skin + ZWJ + school)
- **Multi-codepoint:** `🧑‍🧑‍🧒‍🧒` (family emoji)

Preserve the entire emoji sequence as a unit.

## Recursive Processing

When processing recursively:

```bash
/noteplan-manager:sync-header-emojis --recursive "/Users/omar.eid/.../🏢 ServiceNow/🔬 Research"
```

**Process:**
1. Find all subdirectories with emojis
2. For each subdirectory, extract its emoji
3. Process files in that subdirectory
4. Report results grouped by folder

**Example output:**
```
Processing recursively from: 🔬 Research

Found 3 subdirectories with emojis:

📂 🧑🏻‍💻 Development (8 files)
   - Updated: 3 files
   - Already correct: 5 files

📂 🎯 Impact (12 files)
   - Updated: 7 files
   - Already correct: 5 files

📂 ✈️ Travel (4 files)
   - Updated: 1 file
   - Already correct: 3 files

Total: 11 files updated across 3 folders
```

## Command Options

### Basic Usage
```bash
# Interactive mode
/noteplan-manager:sync-header-emojis

# Specify directory
/noteplan-manager:sync-header-emojis "/path/to/folder"

# Recursive processing
/noteplan-manager:sync-header-emojis --recursive "/path/to/parent"
```

### Advanced Options
```bash
# Dry run (report only, don't modify)
/noteplan-manager:sync-header-emojis --dry-run

# Auto-confirm (no prompts)
/noteplan-manager:sync-header-emojis --yes

# Specific strategy
/noteplan-manager:sync-header-emojis --strategy=replace

# Include plan files
/noteplan-manager:sync-header-emojis --include-plans
```

## Safety Features

- ✅ **Dry run mode** - Report changes without modifying
- ✅ **Confirmation prompts** - Ask before updating
- ✅ **Backup suggestion** - Recommend backing up first
- ✅ **Detailed reporting** - Show before/after for each file
- ✅ **Undo information** - Track what was changed
- ✅ **Skip protection** - Don't modify special files (@Templates, etc.)

## Example Runs

### Example 1: Single Directory

```bash
/noteplan-manager:sync-header-emojis

# User provides directory
Directory: /Users/omar.eid/.../🧑🏻‍💻 Development

# Analysis
Parent folder: 🧑🏻‍💻 Development
Folder emoji: 🧑🏻‍💻

Found 8 markdown files

Changes needed:
1. Deep Dive Outlook.md
   # 🏢 260129 Deep Dive: Outlook
   # 🧑🏻‍💻 260129 Deep Dive: Outlook

2. Syncing Repos.md
   # Syncing Repos
   # 🧑🏻‍💻 Syncing Repos

Apply changes? yes

✅ Updated 2 files
```

### Example 2: Recursive Processing

```bash
/noteplan-manager:sync-header-emojis --recursive

# User provides parent directory
Parent directory: /Users/omar.eid/.../🔬 Research

# Recursive scan
Found 4 subdirectories:

1. 🧑🏻‍💻 Development (8 files, 3 need updates)
2. 🎯 Impact (12 files, 7 need updates)
3. ✈️ Travel (4 files, 1 needs update)
4. 🖥️ Workspace (6 files, 0 need updates)

Total: 11 files need updates

Show details? yes

[Shows detailed list...]

Apply all changes? yes

✅ Updated 11 files across 3 folders
```

### Example 3: Plan Files

```bash
/noteplan-manager:sync-header-emojis "/Users/omar.eid/.../🧑🏻‍💻 Development"

# Detects this is a plan subdirectory
This is a work plan subdirectory (🧑🏻‍💻 Development)

Plan files use special format:
🏢YYMMDD<workstream> Title

Update workstream emoji to match folder? yes

Found 5 plan files:

1. 🏢260216🏁 Azure Agents POCs.md
   Current workstream: 🏁 (Onboarding)
   New workstream: 🧑🏻‍💻 (Development)

   # 🏢260216🏁 Azure Agents POCs
   # 🏢260216🧑🏻‍💻 Azure Agents POCs

Also update filename? no

✅ Updated headers only (kept original filenames)
```

## Integration with Other Skills

Works well with:
- **fix-work-emojis** - Fix encoding after syncing
- **fix-personal-emojis** - Fix encoding after syncing
- **sync-plan-templates** - Keep templates in sync with folder structure
- **organize-daily** - Daily note organization

## Tips

- **Run after reorganizing** folders or moving files
- **Use recursive mode** to fix entire subtrees
- **Check plan files carefully** - they have special structure
- **Dry run first** on large batches
- **Backup before** bulk operations
- **Combine with emoji fixing** for complete cleanup

## Advanced Features

### Pattern Matching

Allow custom patterns for different file types:
- Daily notes: `# YYYY-MM-DD`
- Deep dives: `# Deep Dive: Title`
- Plans: `# 🏢YYMMDD🎯 Title`

### Smart Detection

Detect file type and apply appropriate strategy:
- Plan files → Update workstream emoji
- Regular notes → Replace namespace emoji
- Deep dives → Prepend folder emoji

### Batch Operations

Process multiple folders at once:
```bash
/noteplan-manager:sync-header-emojis --batch
  --folders "Development,Impact,Travel"
```

### Reporting

Generate detailed reports:
- CSV export of changes
- Before/after comparison
- Success/failure summary
- Emoji usage statistics

## Related Skills

- `fix-work-emojis` - Fix work plan emoji encoding
- `fix-personal-emojis` - Fix personal plan emoji encoding
- `sync-plan-templates` - Sync template emoji lists
- `analyze-structure` - Analyze NotePlan structure
