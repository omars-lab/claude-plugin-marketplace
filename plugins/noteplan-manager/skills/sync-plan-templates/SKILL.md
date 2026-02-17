---
name: sync-plan-templates
description: Sync plan templates with current workstream/plantype subdirectories to keep emoji mappings consistent
---

# Sync Plan Templates

You are a NotePlan template synchronizer. When this skill is invoked, you'll synchronize plan templates with the current subdirectory structure to ensure emoji mappings stay consistent as new categories are added.

## What This Skill Does

This skill:
1. **Scans work plan subdirectories** to discover current workstream emojis
2. **Scans personal plan files** to discover currently used plan type emojis
3. **Reads current templates** to see existing emoji lists
4. **Identifies mismatches** between templates and actual usage
5. **Updates templates** to reflect current emoji categories
6. **Reports changes** made to templates

## Problem This Solves

**Scenario:** You add a new workstream subdirectory like `✈️ Travel` or `🖥️ Workspace` to your work plans, or start using a new personal plan type emoji like `🪵 Backlogs`. The template still has the old list of emojis, so when you create a new plan, the new category isn't in the dropdown.

**Solution:** This skill scans your actual plan directories/files and updates the templates to include all currently used emoji categories.

## Templates to Sync

### Work Plan Template
**Path:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/🏢📆 Work Plan.md`

**Current workstream list in template:**
```javascript
<% prompt('workstream', 'What is the current work stream?', ['⏰ Productivity', '🎯 Goals', '🏁 Onboarding']) -%>
```

**Should sync with subdirectories in:**
`/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans`

### Personal Plan Template
**Path:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/🏡📆 Personal Plan.md`

**Current plantype list in template:**
```javascript
<% prompt('planType', 'What kind of plan is this?', ['⚖️ Deciding', '⚙️ Automating', ...]) -%>
```

**Should sync with plan type emojis used in files in:**
`/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans`

## How It Works

### For Work Plans

#### Step 1: Discover Workstream Subdirectories

```bash
# List subdirectories with emojis
ls -1 "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏢 ServiceNow/📆 Plans/"
```

Example output:
```
🧑🏻‍💻 Development
🎯 Impact
🏁 Onboarding
✈️ Travel
🖥️ Workspace
```

#### Step 2: Extract Emoji + Label

From each subdirectory name, extract:
- **Emoji:** `🧑🏻‍💻`, `🎯`, `🏁`, `✈️`, `🖥️`
- **Label:** `Development`, `Impact`, `Onboarding`, `Travel`, `Workspace`
- **Combined:** `🧑🏻‍💻 Development`, `🎯 Impact`, etc.

#### Step 3: Read Current Template

Read the work plan template and find the workstream prompt line:
```javascript
<% prompt('workstream', 'What is the current work stream?', ['⏰ Productivity', '🎯 Goals', '🏁 Onboarding']) -%>
```

#### Step 4: Compare Lists

**Template has:** `⏰ Productivity`, `🎯 Goals`, `🏁 Onboarding`

**Actual subdirectories have:** `🧑🏻‍💻 Development`, `🎯 Impact`, `🏁 Onboarding`, `✈️ Travel`, `🖥️ Workspace`

**Missing from template:** `🧑🏻‍💻 Development`, `🎯 Impact`, `✈️ Travel`, `🖥️ Workspace`

**In template but not in subdirs:** `⏰ Productivity`, `🎯 Goals`

#### Step 5: Update Template

Replace the old prompt with updated list:
```javascript
<% prompt('workstream', 'What is the current work stream?', ['🧑🏻‍💻 Development', '🎯 Impact', '🏁 Onboarding', '✈️ Travel', '🖥️ Workspace']) -%>
```

**Sort order:** Alphabetical by label (after emoji)

### For Personal Plans

Personal plans are different - there are no subdirectories by plan type. Instead, we need to discover plan types from actual files.

#### Step 1: Scan All Personal Plan Files

```bash
# Find all personal plan files
find "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans" -type f -name "*.md"
```

#### Step 2: Extract Plan Type Emojis from Files

For each file, extract the plan type emoji from:
1. **Filename pattern:** `🏡YYMMDD<emoji> Title.md` → extract `<emoji>`
2. **Frontmatter:** `plantype: <emoji>` → extract `<emoji>`

Build a list of all unique plan type emojis actually used.

#### Step 3: Map Emojis to Labels

For each emoji found, determine the label:
- Check template's current list for existing mapping
- For new emojis, prompt user for label or infer from filename

Example findings:
- `⚙️` → Automating
- `✈️` → Traveling
- `🪵` → Backlogs (newly discovered)
- `👨🏻‍💻` → Development (newly discovered)

#### Step 4: Update Template

Merge discovered plan types with template list, ensuring no duplicates.

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

M  @Templates/🏢📆 Work Plan.md
M  🏢 ServiceNow/note.md

Would you like to commit these before syncing templates? (yes/no/show)

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
Task #2: Scan work plan subdirectories for workstream emojis
Task #3: Scan personal plan files for plan type emojis
Task #4: Compare current template lists with discovered emojis
Task #5: Update templates with new emoji mappings
Task #6: Verify template syntax
Task #7: Create git commit with changes
```

**Update task status as work progresses** to show user current step.

### Post-Work: Git Commit

After successfully syncing templates, create a commit:

```bash
# Stage modified templates
git add "@Templates/🏢📆 Work Plan.md" "@Templates/🏡📆 Personal Plan.md"

# Create descriptive commit
git commit -m "feat(noteplan): Sync plan templates with current emoji categories

Work Plan Template:
- Added X new workstreams: [list]
- Removed Y obsolete workstreams: [list]

Personal Plan Template:
- Added Z new plan types: [list]

Templates now reflect current plan organization structure.

Skill: sync-plan-templates

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Commit message should include:**
- Templates updated (work, personal, or both)
- Number and list of added emoji categories
- Number and list of removed emoji categories
- Skill name for traceability

## Workflow

### When Invoked

**0. Git safety and task setup:**
   - Check git status for pending changes
   - Offer to commit pending work
   - Create tasks for workflow steps
   - Mark first task as in_progress

1. **Choose scope:**
   - Sync both templates (default)
   - Sync only work plan template
   - Sync only personal plan template

2. **Scan and discover:**
   - For work: scan subdirectories
   - For personal: scan files and extract plan types

3. **Read current templates**

4. **Compare and identify changes:**
   ```
   Work Plan Template Analysis:

   Current workstreams in template:
   - ⏰ Productivity
   - 🎯 Goals
   - 🏁 Onboarding

   Actual workstream subdirectories:
   - 🧑🏻‍💻 Development
   - 🎯 Impact
   - 🏁 Onboarding
   - ✈️ Travel
   - 🖥️ Workspace

   Changes needed:
   ➕ Add: 🧑🏻‍💻 Development
   ➕ Add: 🎯 Impact
   ➕ Add: ✈️ Travel
   ➕ Add: 🖥️ Workspace
   ➖ Remove: ⏰ Productivity (no matching subdir)
   ➖ Remove: 🎯 Goals (rename to "Impact"?)
   ```

5. **Ask for confirmation:**
   - Show proposed changes
   - Let user review additions/removals
   - Allow user to keep certain items even if no matching subdir

6. **Update templates:**
   - Replace prompt arrays with new lists
   - Maintain template structure
   - Preserve other template content

7. **Report completion:**
   ```
   ✅ Templates synced successfully!

   Work Plan Template:
   - Added 4 new workstreams
   - Removed 2 obsolete workstreams
   - Now lists 5 workstreams

   Personal Plan Template:
   - Added 3 new plan types
   - Now lists 27 plan types
   ```

8. **Create git commit:**
   ```
   Creating git commit with template updates...

   Templates modified:
   - Work Plan Template (4 additions, 2 removals)
   - Personal Plan Template (3 additions)

   Committing to git...
   ✅ Commit created: h7i8j9k
      "feat(noteplan): Sync plan templates with current emoji categories"

   All tasks completed! ✅
   ```

   **Mark all tasks as completed** when done.

## Smart Handling

### Emoji Variants

If subdirectory has `🎯 Impact` but template has `🎯 Goals`:
- These use the **same emoji**
- Ask user: "Rename 'Goals' to 'Impact', or keep both?"

### Manual Additions

User might want template entries that don't have subdirs yet:
- Keep items marked as "planned" or "future"
- Ask before removing
- Option to add `(planned)` suffix

### Sorting

Sort the lists in templates:
- **Primary:** By emoji category (people, objects, symbols, etc.)
- **Secondary:** Alphabetically by label
- Or: **Alphabetically by label only** (simpler)

### Preserve Comments

If template has comments explaining choices:
```javascript
<% prompt('workstream', 'What is the current work stream?', [
  '🎯 Goals',        // Strategic planning
  '🏁 Onboarding',   // New employee setup
  '⏰ Productivity'  // Time management
]) -%>
```

Preserve comment structure when updating.

## Example Run

```bash
/noteplan-manager:sync-plan-templates

# Claude runs analysis
Analyzing work plan template...

Found 5 workstream subdirectories:
1. 🧑🏻‍💻 Development
2. 🎯 Impact
3. 🏁 Onboarding
4. ✈️ Travel
5. 🖥️ Workspace

Current template lists 3 workstreams:
1. ⏰ Productivity
2. 🎯 Goals
3. 🏁 Onboarding

Proposed changes:
➕ Add: 🧑🏻‍💻 Development
➕ Add: 🎯 Impact (note: 🎯 also used for "Goals" - consolidate?)
➕ Add: ✈️ Travel
➕ Add: 🖥️ Workspace
➖ Remove: ⏰ Productivity (no matching subdirectory)
⚠️  🎯 Goals vs 🎯 Impact - same emoji, different labels

---

Analyzing personal plan template...

Scanned 47 personal plan files.

Found 24 unique plan type emojis in use:
- 22 already in template
- 2 NEW: 🪵 (in 3 files), 🧘🏻 (in 1 file)

Template currently lists 25 plan types.

Proposed changes:
➕ Add: 🪵 Backlogs
➕ Add: 🧘🏻 Meditation
(Need labels for new emojis - suggested from filenames)

---

Update templates with these changes? (yes/no)

# User confirms
yes

# Claude updates templates
✅ Updated work plan template:
   - Added 4 new workstreams
   - Removed 1 obsolete workstream
   - Consolidated "Goals" → "Impact"
   - Now lists 5 workstreams

✅ Updated personal plan template:
   - Added 2 new plan types
   - Now lists 27 plan types

Templates are now in sync with your current plan structure!
```

## Edge Cases

### No Changes Needed

```
✅ Templates are already in sync!

Work plan template matches subdirectories (5 workstreams)
Personal plan template includes all plan types found (25 types)

No updates needed.
```

### User Has Removed Subdirectories

```
⚠️  Template lists workstream "⏰ Productivity" but no matching subdirectory found.

Options:
1. Remove from template (subdir was deleted)
2. Keep in template (subdir temporarily moved/planned for future)

What should I do?
```

### Complex Emoji Encoding

If emoji encoding differs between subdir name and template:
- Normalize to consistent form
- Fix encoding issues
- Report normalization done

## Safety Features

- ✅ **Backup templates** before modifying
- ✅ **Show diff** of proposed changes
- ✅ **Require confirmation** before writing
- ✅ **Validate template** syntax after changes
- ✅ **Preserve template** structure and metadata

## Related Skills

- `fix-work-emojis` - Fix emoji encoding in work plans
- `fix-personal-emojis` - Fix emoji encoding in personal plans
- `analyze-structure` - Analyze NotePlan structure
- `manage-templates` - General template management

## Tips

- **Run periodically** when adding new categories
- **Run before creating** bulk plans in new categories
- **Check diffs carefully** before confirming changes
- **Keep labels consistent** with subdirectory names
- **Sort strategically** for easy selection in NotePlan

## Advanced Options

### Custom Sorting

Allow user to specify sort order:
- Alphabetical by label
- By usage frequency
- Custom order (manually specified)
- Grouped by theme

### Bidirectional Sync

Not just template ← subdirs, but also:
- Create missing subdirs from template
- Rename subdirs to match template changes
- Suggest new subdirs based on file clustering

### Version Control

Track template changes over time:
- Show history of emoji categories
- Detect trends (new categories added)
- Warn about frequently changing categories
