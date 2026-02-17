---
name: fix-work-emojis
description: Fix emoji encoding issues in work plan files and ensure consistent emoji usage across work plans directory
---

# Fix Work Plan Emojis

You are a NotePlan work plan emoji fixer. When this skill is invoked, you'll scan and fix emoji encoding issues in work plan files to ensure consistency and proper display.

## What This Skill Does

This skill:
1. **Scans work plan files** in the work plans directory
2. **Detects emoji encoding issues** (mojibake, broken emojis, inconsistent encoding)
3. **Fixes emoji encoding** to ensure proper UTF-8 display
4. **Normalizes emoji usage** across plan files
5. **Reports changes** made to files

## Work Plans Structure

**Directory:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans`

**Subdirectories (workstreams):**
- 🧑🏻‍💻 Development
- 🎯 Impact
- 🏁 Onboarding
- ✈️ Travel
- 🖥️ Workspace

**File Naming Pattern:**
```
🏢YYMMDD<emoji> Title.md
```

Example: `🏢260118🏁 ServiceNow Onboarding Emails.md`

## Emoji Categories to Check

### 1. Namespace Emoji
- `🏢` - Work namespace (should be at start of filename)

### 2. Workstream Emojis (from subdirectories)
- `🧑🏻‍💻` - Development
- `🎯` - Impact/Goals
- `🏁` - Onboarding
- `✈️` - Travel
- `🖥️` - Workspace

### 3. Status Emojis
- `🔮` - Future
- `🚦` - Ready
- `🟢` - Started
- `🟡` - Paused
- `🔴` - Blocked
- `❎` - Canceled
- `✅` - Done

### 4. Additional Activity Emojis
- `⏰` - Productivity
- Any other emojis used in frontmatter or content

## How to Fix Emojis

### Step 1: Scan for Issues

```bash
# List all work plan files
find "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans" -type f -name "*.md"
```

### Step 2: Detect Encoding Issues

Look for:
- **Broken emojis** - Displayed as `?`, `�`, or boxes
- **Mojibake** - Garbled text like `ð\237\217¢` instead of `🏢`
- **Inconsistent encoding** - Some files use different emoji variants
- **Missing emojis** - Files that should have emojis but don't
- **Wrong emoji variants** - Using `🏢` vs `🏢️` (with variation selector)

### Step 3: Fix Each File

For each file with issues:

1. **Read the file** and identify encoding problems
2. **Normalize emojis** to their standard form (NFC normalization)
3. **Fix mojibake** by converting to proper UTF-8
4. **Ensure consistency** with workstream emojis from subdirectory names
5. **Update frontmatter** if emoji metadata is broken
6. **Write the corrected file** back

### Step 4: Verify Frontmatter

Check that frontmatter contains proper emojis:
```yaml
--
doctype: 📆
status: 🟢
namespace: 🏢
workstream: 🏁
--
```

### Step 5: Verify Filenames

Ensure filenames follow the pattern:
- Start with `🏢` (work namespace)
- Include date as `YYMMDD`
- Include workstream emoji
- Have descriptive title

## Common Emoji Issues

### Issue 1: Multi-byte Emojis Broken

**Problem:** Complex emojis like `🧑🏻‍💻` (person with skin tone and laptop) break into parts

**Fix:** Ensure full emoji sequence is preserved
```python
# Python example for fixing
import unicodedata
text = unicodedata.normalize('NFC', text)
```

### Issue 2: Emoji Variation Selectors

**Problem:** Same emoji with/without variation selector (U+FE0F)

**Fix:** Standardize to one form (with or without selector)

### Issue 3: Filesystem Encoding

**Problem:** macOS filesystem uses NFD normalization, but display expects NFC

**Fix:** Convert between normalizations as needed

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

M  🏢 ServiceNow/📆 Plans/🏁 Onboarding/file1.md
M  🏡 Personal/note.md

Would you like to commit these before fixing emojis? (yes/no/show)

- yes: Create commit with pending changes first
- no: Continue without committing (changes will be mixed)
- show: Show detailed diff of pending changes
```

**Recommended:** Always commit pending changes first to keep work separated.

### Task Management (MANDATORY)

This skill **MUST** use task management to track progress. Tasks are not optional.

**BEFORE starting any work, create all tasks with proper dependencies:**

#### Task Creation (Step 0 - Do this FIRST)

```javascript
// Task #1: Git safety check
TaskCreate({
  subject: "Check git status and handle pending changes",
  description: "Check for uncommitted changes in NotePlan repository. If found, offer to commit folder restructuring changes before making emoji fixes. This keeps commits separated and organized.\n\nActions:\n- Run git status in NotePlan Notes directory\n- Identify pending changes (modified, deleted, untracked files)\n- If changes exist, ask user whether to commit first\n- Create commit if approved\n\nLocation: /Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes",
  activeForm: "Checking git status"
})

// Task #2: Scan for issues
TaskCreate({
  subject: "Scan work plan files for emoji issues",
  description: "Scan all work plan files in the Plans directory and subdirectories to identify emoji encoding issues, pattern violations, and inconsistencies.\n\nCheck for:\n- Filename pattern issues (missing 🏢, extra spaces, missing dates)\n- Workstream emoji mismatches (filename vs parent folder)\n- Frontmatter workstream mismatches (frontmatter vs folder)\n- Wrong doctypes (🗒️ instead of 📆)\n- Missing frontmatter\n- Broken emoji encoding (mojibake, broken UTF-8)\n\nExpected: ~16 files across 5 workstream directories\nGenerate detailed report of all issues found.",
  activeForm: "Scanning work plan files"
})

// Task #3: Fix issues
TaskCreate({
  subject: "Fix emoji encoding and patterns in work plan files",
  description: "Fix all identified emoji issues in work plan files based on scan results.\n\nFixes to apply:\n- Fix filename patterns (remove extra spaces, add missing emojis/dates)\n- Sync workstream emojis in filenames to match parent folder\n- Update frontmatter workstream fields to match folder\n- Fix doctypes (change 🗒️ to 📆 for plan files)\n- Add missing frontmatter where needed\n- Normalize emoji encoding to NFC\n\nPreserve file timestamps and backup before modifying.\nReport all changes made.",
  activeForm: "Fixing emoji encoding"
})

// Task #4: Check filename/header title matching (MANDATORY POST-FIX CHECK)
TaskCreate({
  subject: "Verify filename matches header title",
  description: "MANDATORY CHECK: Ensure filename and header title are consistent.\n\nFor each file, verify:\n1. Extract header title (first line starting with #)\n2. Extract filename (without .md extension)\n3. Compare:\n   - Filename should match header minus the '#' and spaces\n   - If they don't match, flag as inconsistent\n\nExample issues:\n- Filename: \"Personal Automation Setup.md\"\n  Header: \"# 🏢260121⏰ Personal Automation Setup\"\n  Problem: Filename missing emoji prefix!\n\n- Filename: \"🏢260118🏁 Old Title.md\"\n  Header: \"# 🏢260118🏁 New Title\"\n  Problem: Title text doesn't match\n\nReport:\n- Files where filename != header (minus # and .md)\n- Suggest renaming files or updating headers to match\n\nThis ensures visual consistency between file lists and document titles.",
  activeForm: "Verifying filename/header consistency"
})

// Task #5: Check folder emoji in headers (MANDATORY POST-FIX CHECK)
TaskCreate({
  subject: "Check header contains parent folder emoji",
  description: "MANDATORY CHECK: Verify that header title includes the parent folder emoji for visual consistency.\n\nFor each fixed file:\n- Read the header line (# title)\n- Extract emojis from header\n- Get parent folder emoji\n- Verify folder emoji appears in header\n- Report mismatches\n\nExample issue: File in \"🏁 Onboarding/\" folder has header \"# 🏢260118 File\" (missing 🏁)\n\nIf mismatches found, recommend running sync-header-emojis skill.\n\nThis check helps determine if additional maintenance is needed.",
  activeForm: "Checking header folder emoji"
})

// Task #6: Check template (MANDATORY POST-FIX CHECK)
TaskCreate({
  subject: "Check template sync status (MANDATORY)",
  description: "MANDATORY CHECK: Always verify Work Plan template is in sync with current workstream structure. This is NOT optional.\n\nSteps:\n1. Read template: @Templates/🏢📆 Work Plan.md\n2. Extract workstream list from prompt('workstream', ...) line\n3. Get current workstream subdirectories from Plans folder\n4. Compare template workstreams vs actual subdirectories\n5. Identify:\n   - Missing workstreams (in folders but not template)\n   - Obsolete workstreams (in template but folders removed)\n   - Wrong labels (emoji correct but name different)\n\nReport findings with severity:\n- OUT OF SYNC: Requires template update to prevent future issues\n- IN SYNC: No action needed\n\nIf out of sync, STRONGLY RECOMMEND including sync-plan-templates in workflow.\n\nThis explains why files have wrong emojis - users select from outdated template options!",
  activeForm: "Checking template sync status"
})

// Task #7: Comprehensive workflow
TaskCreate({
  subject: "Offer and execute comprehensive maintenance workflow",
  description: "Based on all checks, offer user the complete maintenance workflow to fix ALL identified issues.\n\nPresent results:\n- Show what was fixed (emoji encoding)\n- Show what needs fixing (headers, template)\n- Recommend complete workflow if template out of sync\n\nOptions:\n- yes: Run all maintenance (sync-header-emojis + sync-plan-templates)\n- no: Stop after emoji fixes\n- custom: User chooses which fixes to run\n\nIf template is out of sync, STRONGLY emphasize:\n\"Without template update, new work plans will continue to have wrong workstream emojis\"\n\nExecute approved skills and report results.",
  activeForm: "Running comprehensive maintenance"
})

// Task #8: Validate changes and create final commit
TaskCreate({
  subject: "Validate changes and create git commit",
  description: "MANDATORY VALIDATION: Review all changes before committing.\n\nStep 1: Get starting checkpoint\n- The auto-commit from Task #1 is our baseline\n- All changes after that commit are from this skill\n\nStep 2: Review git diff\n```bash\n# Show all changes since the auto-commit\ngit diff HEAD~1\n\n# Or if multiple commits were made, show all unstaged + staged changes\ngit diff [checkpoint-commit]\n```\n\nStep 3: Validate changes\nReview diff and verify:\n✅ Only work plan files modified (expected)\n✅ Emoji changes are correct (filename, frontmatter, headers)\n✅ No unexpected file modifications\n✅ Template updates look correct (if ran)\n✅ No content accidentally modified\n\n⚠️ If unexpected changes found:\n- Investigate what caused them\n- Fix issues before committing\n- Re-validate\n\nStep 4: Create commit only if validation passes\n\nCommit message format:\n```\nfix(noteplan): Fix work plan emoji encoding and consistency\n\n- Fixed emoji encoding in X work plan files\n- Updated Y filename patterns\n- Synchronized Z frontmatter workstream fields\n- [if applicable] Renamed N files to match headers\n- [if applicable] Updated template with current workstreams\n- [if applicable] Synced headers to match folder emojis\n\nAffected workstreams: [list]\n\nValidated changes via git diff before committing.\nSkill: fix-work-emojis\n\nCo-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>\n```\n\nShow commit hash and validation summary when complete.",
  activeForm: "Validating and committing changes"
})
```

#### Set Up Task Dependencies

**After creating all 8 tasks, set up dependencies:**

```javascript
// Task #2 depends on #1 (commit pending changes first)
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })

// Task #3 depends on #2 (need scan results to fix)
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })

// Tasks #4, #5, #6 all depend on #3 (run checks AFTER fixing)
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "6", addBlockedBy: ["3"] })

// Task #7 depends on #4, #5, AND #6 (need ALL check results)
TaskUpdate({ taskId: "7", addBlockedBy: ["4", "5", "6"] })

// Task #8 depends on #7 (commit after all work done)
TaskUpdate({ taskId: "8", addBlockedBy: ["7"] })
```

#### Task Dependency Flow

```
#1 ⚡ Check git status and handle pending changes
    └─► #2 🔍 Scan work plan files for emoji issues
         └─► #3 🔧 Fix emoji encoding and patterns
              ├─► #4 📋 Verify filename matches header ────┐
              ├─► #5 📝 Check header folder emoji ─────────┤
              └─► #6 📋 Check template sync (MANDATORY) ────┤
                                                             │
                   #7 🎯 Offer comprehensive workflow ◄──────┘
                    └─► #8 💾 Create git commit
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

#### Why This Task Structure?

1. **#1 First**: Must check git before making changes (safety)
2. **#2 Depends on #1**: Don't scan if pending changes need committing
3. **#3 Depends on #2**: Can't fix without knowing what's broken
4. **#4, #5, #6 in Parallel**: All three checks run AFTER fixing, independent of each other
   - #4: Filename/header title consistency
   - #5: Header folder emoji presence
   - #6: Template sync status (mandatory)
5. **#7 Depends on All Three**: Need results from ALL checks (#4, #5, #6) to offer complete workflow
6. **#8 Last**: Commit only after all work is done

**This 8-task structure is MANDATORY for every execution of this skill.**

### Post-Work: Git Commit

After successfully fixing emojis, create a commit:

```bash
# Stage modified files
git add "🏢 ServiceNow/📆 Plans/"

# Create descriptive commit
git commit -m "fix(noteplan): Fix work plan emoji encoding

- Fixed emoji encoding in X work plan files
- Normalized emoji variants to NFC
- Restored broken skin tone modifiers
- Updated workstream emojis: [list]

Skill: fix-work-emojis

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Commit message should include:**
- Number of files fixed
- Types of fixes applied (encoding, variants, skin tones, etc.)
- Specific workstreams affected
- Skill name for traceability

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
📋 Work Plan Emoji Fix - Task Workflow (8 Tasks)

#1 ⚡ Check git status and handle pending changes [STARTING]
    └─► #2 🔍 Scan work plan files for emoji issues
         └─► #3 🔧 Fix emoji encoding and patterns
              ├─► #4 📋 Verify filename matches header
              ├─► #5 📝 Check header folder emoji
              └─► #6 📋 Check template sync (MANDATORY)
                   └─► #7 🎯 Offer comprehensive workflow
                        └─► #8 💾 Create git commit

Ready to begin!
```

### **Step 1 (Task #1): Git Safety Check**

Mark task as in_progress, then check for pending changes:

```bash
cd "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"
git status --short
```

**If pending changes found: AUTO-COMMIT them (do NOT ask user)**

```bash
# Stage all changes
git add -A

# Create descriptive commit based on what changed
git commit -m "chore(noteplan): Auto-commit pending changes before emoji fixes

[Describe what changes were pending]

Auto-committed by fix-work-emojis skill to keep commits separated.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Rationale for auto-commit:**
- Keeps emoji fixes isolated in their own commit
- User already made changes intentionally, just commit them
- No need to interrupt workflow with questions
- Makes git history cleaner and more traceable

**Complete Task #1 and mark as completed**, then start Task #2.

### **Step 2 (Task #2): Scan Files**

```javascript
TaskUpdate({ taskId: "1", status: "completed" })
TaskUpdate({ taskId: "2", status: "in_progress" })
```

Scan all files:
```bash
find "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans" -name "*.md" -type f
```

### **Step 3 (Task #2): Analyze Each File**
   - Read file content
   - Check filename emoji encoding
   - Check frontmatter emojis
   - Check content emojis
   - Identify encoding issues

### **Step 4 (Task #2): Report Findings**

```
Found 5 files with emoji issues:

1. 🏢260118🏁 File.md
   - Frontmatter status emoji broken: � → 🟢

2. 🏢260120🎯 Another.md
   - Filename workstream emoji missing variation selector
```

### **Step 5 (Task #2→#3): Ask for Confirmation**

Ask user for confirmation before making changes.

**Complete Task #2 and start Task #3:**
```javascript
TaskUpdate({ taskId: "2", status: "completed" })
TaskUpdate({ taskId: "3", status: "in_progress" })
```

### **Step 6 (Task #3): Fix Issues**

- Normalize emoji encoding
- Update files
- Preserve file metadata (timestamps)
- Report changes as you make them

### **Step 7 (Task #3): Report Results**

```
✅ Fixed 5 files:
- Corrected 3 frontmatter emojis
- Fixed 2 filename emojis
- Normalized 8 content emojis
```

**Complete Task #3 and start Tasks #4, #5, #6 in parallel:**
```javascript
TaskUpdate({ taskId: "3", status: "completed" })
TaskUpdate({ taskId: "4", status: "in_progress" })
TaskUpdate({ taskId: "5", status: "in_progress" })
TaskUpdate({ taskId: "6", status: "in_progress" })
```

### **Step 8 (Tasks #4, #5, #6): MANDATORY POST-FIX CHECKS**

These checks run in PARALLEL after fixes are complete:

   After fixing emoji encoding, **MANDATORY CHECKS** for related work:

   **a) ALWAYS check template consistency:**

   This is a REQUIRED step, not optional. Template issues cause recurring problems.

   1. Read template file: `@Templates/🏢📆 Work Plan.md`
   2. Extract workstream options from `prompt('workstream', ...)` line
   3. Compare with current subdirectory structure
   4. Report any differences and ALWAYS offer to include template sync in workflow

   **b) Check if headers need syncing:**

   - Compare header emojis with parent folder emojis
   - If mismatches found, suggest: `/noteplan-manager:sync-header-emojis`

   Example check:
   ```
   🔍 Running post-fix validation checks...

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📋 Check 1: Filename/Header Title Consistency (Task #4)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Found 2 files where filename doesn't match header:

   ⚠️  Personal Automation Setup.md
      Header: # 🏢260121⏰ Personal Automation Setup
      Problem: Filename missing emoji prefix!

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📝 Check 2: Header Folder Emoji (Task #5)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Found 3 files where header missing folder emoji:

   📂 🏁 Onboarding/
   - 🏢260118 File.md
     Header: # 🏢260118 File
     ⚠️  Missing 🏁 in header

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📋 Check 3: Template Sync Status (Task #6 - MANDATORY)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Current subdirectories: 🧑🏻‍💻 Development, 🎯 Impact, 🏁 Onboarding, ✈️ Travel, 🖥️ Workspace
   Template workstreams: ⏰ Productivity, 🎯 Goals, 🏁 Onboarding

   ⚠️  OUT OF SYNC - Template update REQUIRED

   💡 Recommendation: Include all fixes in comprehensive workflow
   ```

   **b) ALWAYS check if templates need syncing:**

   **MANDATORY STEP** - Always read and verify template consistency:

   1. Read the Work Plan template at:
      `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/🏢📆 Work Plan.md`

   2. Extract workstream list from template (look for the `prompt('workstream', ...)` line)

   3. Get current workstream subdirectories:
      ```bash
      ls -1 "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans/"
      ```

   4. Compare and report differences

   5. If ANY differences found, ALWAYS offer to run template sync as part of workflow

   Example check:
   ```
   📋 Checking template consistency...

   Current workstream subdirectories:
   - 🧑🏻‍💻 Development
   - 🎯 Impact
   - 🏁 Onboarding
   - ✈️ Travel
   - 🖥️ Workspace

   Work Plan template workstreams (from @Templates/🏢📆 Work Plan.md):
   - ⏰ Productivity
   - 🎯 Goals
   - 🏁 Onboarding

   ⚠️  Template is OUT OF SYNC:
   - Missing from template: 🧑🏻‍💻 Development, ✈️ Travel, 🖥️ Workspace
   - Obsolete in template: ⏰ Productivity
   - Wrong label: 🎯 Goals (should be 🎯 Impact)

   🚨 This explains why files have wrong workstream emojis!

   Template sync is REQUIRED to prevent future issues.
   Include template update in workflow? (Recommended: yes)
   ```

9. **ALWAYS offer comprehensive fix when needed:**

   Based on the mandatory checks, offer to complete ALL needed fixes:

   ```
   🎯 Comprehensive Fix Workflow

   Current Status:
   1. ✅ Emoji encoding fixed (completed)
   2. ⚠️  Filename/header mismatches (2 files need renaming)
   3. ⚠️  Header folder emojis missing (3 files)
   4. 🚨 Template OUT OF SYNC (STRONGLY RECOMMENDED)

   Would you like to run the complete maintenance workflow?

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Complete Fix (Recommended)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Step 1: ✅ Fix work plan emojis (DONE)
   Step 2: 📋 Rename files to match headers
   Step 3: 📝 Sync header emojis to match folders
   Step 4: 📋 Update template to prevent future issues

   Run complete workflow? (yes/no/custom)

   - yes: Run all fixes (recommended)
   - no: Skip additional fixes
   - custom: Choose which fixes to run

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   If template is out of sync, STRONGLY RECOMMEND including it:
   "⚠️  Without template update, new work plans will continue
      to have wrong workstream emojis. Highly recommended!"

   If filenames don't match headers, RECOMMEND fixing:
   "⚠️  Filenames should match headers for consistency in
      file browsers and NotePlan navigation."
   ```

   If user confirms:
   ```
   Running comprehensive maintenance...

   Step 2: Renaming files to match headers...
   ✅ Renamed 2 files

   Step 3: Running sync-header-emojis...
   ✅ Fixed 3 headers

   Step 4: Running sync-plan-templates...
   ✅ Updated template with current workstreams

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🎉 All emoji maintenance complete!
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Summary:
   - Fixed emoji encoding in 9 files
   - Renamed 2 files to match headers
   - Synced 3 headers to match folders
   - Updated template with 5 current workstreams

   Your work plans are now fully consistent! ✨
   ```

**Complete Tasks #4, #5, #6, #7 and start Task #8:**
```javascript
TaskUpdate({ taskId: "4", status: "completed" })
TaskUpdate({ taskId: "5", status: "completed" })
TaskUpdate({ taskId: "6", status: "completed" })
TaskUpdate({ taskId: "7", status: "completed" })
TaskUpdate({ taskId: "8", status: "in_progress" })
```

### **Step 10 (Task #8): Validate Changes and Commit**

**MANDATORY: Validate before committing**

```bash
# Get the checkpoint commit (from Task #1 auto-commit)
git log --oneline -5

# Review all changes made by this skill
git diff [checkpoint-commit-hash]
```

**Analyze the diff:**
```
Validating changes...

✅ Files modified: 9 work plan files
✅ Filename changes: 3 files renamed
✅ Frontmatter updates: 5 files (workstream field corrected)
✅ Emoji normalization: All look correct
✅ Template updates: @Templates/🏢📆 Work Plan.md (if ran)
✅ No unexpected modifications detected

Changes validated successfully! ✅
```

**If validation passes, create commit:**
```
Creating git commit with validated emoji fixes...

Files modified: 9
Changes:
- Fixed 3 filename patterns
- Normalized 5 frontmatter workstream fields
- Updated 2 workstream emojis
- [if applicable] Updated template with 5 current workstreams

Committing to git...
✅ Commit created: a1b2c3d
   "fix(noteplan): Fix work plan emoji encoding"

Validation: All changes reviewed and confirmed correct via git diff
```

**Complete Task #8 and show final summary:**
```javascript
TaskUpdate({ taskId: "8", status: "completed" })
TaskList() // Show all tasks completed
```

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 All Work Plan Emoji Fixes Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Task #1: Git safety check
✅ Task #2: Scanned files for issues
✅ Task #3: Fixed emoji encoding
✅ Task #4: Verified filename/header consistency
✅ Task #5: Checked header folder emojis
✅ Task #6: Checked template sync
✅ Task #7: Ran comprehensive maintenance
✅ Task #8: Created git commit

All tasks completed! ✨
```

## Safety Checks

- ✅ Always **back up** files before modifying (or just report changes first)
- ✅ **Preserve** file modification times when possible
- ✅ **Validate** emoji encoding after fix
- ✅ **Don't** modify file content unnecessarily
- ✅ **Only** fix actual emoji encoding issues

## Example Usage

```bash
# User invokes skill
/noteplan-manager:fix-work-emojis

# Claude scans and reports
Found 3 files with emoji encoding issues in work plans:

1. /🏢 ServiceNow/📆 Plans/🏁 Onboarding/🏢260118🏁 File.md
   - Status emoji in frontmatter is broken: �
   - Should be: 🟢

2. /🏢 ServiceNow/📆 Plans/🎯 Impact/🏢260120🎯 Goals.md
   - Workstream emoji uses wrong variant

3. /🏢 ServiceNow/📆 Plans/🖥️ Workspace/🏢260115🖥 Setup.md
   - Namespace emoji missing from filename

Fix these issues? (yes/no)

# User confirms
yes

# Claude fixes and reports
✅ Fixed all 3 files:
- Restored status emoji to 🟢 in file 1
- Normalized workstream emoji in file 2
- Added 🏢 namespace emoji to filename in file 3

All work plan emojis are now consistent!
```

## Advanced: Batch Operations

For bulk fixes across all work plans:

1. **Generate report** of all emoji issues
2. **Group by issue type** (broken, missing, inconsistent)
3. **Prioritize** critical issues (filename vs content)
4. **Batch fix** similar issues together
5. **Validate** all fixes before completing

## Tips

- **Check subdirectory names** first - they define the canonical workstream emojis
- **Use Unicode normalization** (NFC) for consistency
- **Test with one file** before batch operations
- **Keep emoji reference** handy for the correct forms
- **Don't change** emoji meanings, only fix encoding

## Related Skills & Comprehensive Workflow

### Related Skills

- **sync-header-emojis** - Sync header titles with parent folder emojis
- **sync-plan-templates** - Keep plan templates in sync with workstream emojis
- **fix-personal-emojis** - Fix emojis in personal plans
- **analyze-structure** - Analyze NotePlan structure including emoji usage

### Complete Emoji Maintenance Workflow

For comprehensive emoji maintenance, run skills in this order:

**1. Fix Encoding First** (this skill)
```bash
/noteplan-manager:fix-work-emojis
```
- Fixes broken emoji encoding
- Normalizes emoji variants
- Ensures proper UTF-8 display

**2. Sync Headers to Folders**
```bash
/noteplan-manager:sync-header-emojis --recursive "/path/to/📆 Plans"
```
- Ensures header emojis match parent folder emojis
- Updates all subdirectories (Development, Impact, etc.)
- Maintains visual consistency

**3. Update Templates**
```bash
/noteplan-manager:sync-plan-templates
```
- Keeps Work Plan template in sync with current workstreams
- Adds new categories discovered from folders
- Removes obsolete categories

**Result:** All work plan emojis are correctly encoded, headers match folders, and templates are up-to-date!

### When to Run Each Skill

| Situation | Skills to Run | Order |
|-----------|---------------|-------|
| **Emojis display incorrectly** | fix-work-emojis | 1 |
| **Added new workstream folder** | fix-work-emojis → sync-header-emojis → sync-plan-templates | 1→2→3 |
| **Moved files between folders** | sync-header-emojis | 2 |
| **Template outdated** | sync-plan-templates | 3 |
| **Complete maintenance** | All three in order | 1→2→3 |
| **After bulk import** | fix-work-emojis → sync-header-emojis | 1→2 |

### Quick Check Commands

Before running this skill, you can manually check:

```bash
# Check for emoji encoding issues
find "/Users/omar.eid/.../📆 Plans" -name "*.md" -exec file {} \; | grep -v UTF-8

# Check header consistency
# (look for headers that don't match parent folder emoji)

# Check template sync
cat "/Users/omar.eid/.../🏢📆 Work Plan.md" | grep "workstream"
ls -1 "/Users/omar.eid/.../📆 Plans/"
```

### Automated Maintenance Suggestion

Consider running the complete workflow:
- **Weekly:** Quick check and fix encoding issues
- **After folder changes:** Run sync-header-emojis
- **Monthly:** Full maintenance (all three skills)
- **After template changes:** Run sync-plan-templates
