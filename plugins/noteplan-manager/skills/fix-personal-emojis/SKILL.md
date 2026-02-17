---
name: fix-personal-emojis
description: Fix emoji encoding issues in personal plan files and ensure consistent emoji usage across personal plans directory
---

# Fix Personal Plan Emojis

You are a NotePlan personal plan emoji fixer. When this skill is invoked, you'll scan and fix emoji encoding issues in personal plan files to ensure consistency and proper display.

## What This Skill Does

This skill:
1. **Scans personal plan files** in the personal plans directory
2. **Detects emoji encoding issues** (mojibake, broken emojis, inconsistent encoding)
3. **Fixes emoji encoding** to ensure proper UTF-8 display
4. **Normalizes emoji usage** across plan files
5. **Reports changes** made to files

## Personal Plans Structure

**Directory:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans`

**Subdirectories (time-based organization):**
- Future - Plans not yet started
- Present - Active plans
- Past - Completed plans
- Paused - On hold plans

**File Naming Pattern:**
```
🏡YYMMDD<emoji> Title.md
```

Example: `🏡260115⚙️ Automating Home Tasks.md`

## Emoji Categories to Check

### 1. Namespace Emoji
- `🏡` - Personal namespace (should be at start of filename)

### 2. Plan Type Emojis (from template)
- ⚖️ Deciding
- ⚙️ Automating
- ✈️ Traveling
- ❓ Questioning
- 🎉 Celebration
- 🎒 Activities
- 🏃🏻 Health
- 🏠 Home
- 🏢 Career
- 👨🏻‍🏫 Mentorship
- 👨🏻‍💻 Development
- 👨🏻‍💼 Entrepreneurship
- 👨🏻‍🔧 Fixing
- 💰 Assets
- 📊 Tracking
- 📑 Paperwork
- 📚 Education / Learning
- 📝 Authoring / Blogging
- 🔍 Discovering
- 🗣️ Communicating
- 🛒 Shopping
- 🧎🏻 Spirituality
- 🧑‍🧑‍🧒‍🧒 Family
- 🧮 Managing
- 🧰 Craftsmanship
- 🪵 Backlogs

### 3. Status Emojis
- `🔮` - Future
- `🚦` - Ready
- `🟢` - Started
- `🟡` - Paused
- `🔴` - Blocked
- `❎` - Canceled
- `✅` - Done

## How to Fix Emojis

### Step 1: Scan for Issues

```bash
# List all personal plan files across all time-based directories
find "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans" -type f -name "*.md"
```

### Step 2: Detect Encoding Issues

Look for:
- **Broken emojis** - Displayed as `?`, `�`, or boxes
- **Mojibake** - Garbled text like `ð\237\217¡` instead of `🏡`
- **Inconsistent encoding** - Some files use different emoji variants
- **Missing emojis** - Files that should have emojis but don't
- **Complex emoji issues** - Skin tone modifiers breaking (e.g., `👨🏻‍💻`, `🏃🏻`)
- **Multi-codepoint emojis** - Family emojis like `🧑‍🧑‍🧒‍🧒` breaking apart

### Step 3: Fix Each File

For each file with issues:

1. **Read the file** and identify encoding problems
2. **Normalize emojis** to their standard form (NFC normalization)
3. **Fix mojibake** by converting to proper UTF-8
4. **Preserve complex emojis** with skin tones and ZWJ sequences
5. **Update frontmatter** if emoji metadata is broken
6. **Write the corrected file** back

### Step 4: Verify Frontmatter

Check that frontmatter contains proper emojis:
```yaml
--
doctype: 📆
status: 🟢
namespace: 🏡
plantype: ⚙️
--
```

### Step 5: Verify Filenames

Ensure filenames follow the pattern:
- Start with `🏡` (personal namespace)
- Include date as `YYMMDD`
- Include plan type emoji
- Have descriptive title

## Common Emoji Issues in Personal Plans

### Issue 1: Skin Tone Modifiers

**Problem:** Emojis with skin tone modifiers break into separate parts
- `👨🏻‍💻` → `👨` + `🏻` + `💻`
- `🏃🏻` → `🏃` + `🏻`
- `👨🏻‍🏫` → `👨` + `🏻` + `🏫`

**Fix:** Preserve the entire emoji sequence including skin tone modifier (U+1F3FB - U+1F3FF)

### Issue 2: Zero-Width Joiner (ZWJ) Sequences

**Problem:** Complex emojis with ZWJ break into components
- `🧑‍🧑‍🧒‍🧒` (family) → `🧑` + `🧑` + `🧒` + `🧒`
- `👨🏻‍💻` (technologist) → separate parts

**Fix:** Maintain ZWJ (U+200D) sequences intact

### Issue 3: Variation Selectors

**Problem:** Some emojis appear with/without variation selector (U+FE0F)
- `⚙️` (gear with selector) vs `⚙` (gear without)
- `✈️` (airplane with selector) vs `✈` (airplane without)

**Fix:** Standardize to the presentation form (usually with selector for emoji style)

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

M  🏡 Personal/🏡📆 Plans/Present/file1.md
M  🏢 ServiceNow/note.md

Would you like to commit these before fixing emojis? (yes/no/show)

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
Task #2: Scan personal plan files for emoji issues (especially complex sequences)
Task #3: Fix emoji encoding in identified files (skin tones, ZWJ sequences)
Task #4: Verify header consistency with filename patterns
Task #5: Check template sync status
Task #6: Create git commit with changes
```

**Update task status as work progresses** to show user current step.

### Post-Work: Git Commit

After successfully fixing emojis, create a commit:

```bash
# Stage modified files
git add "🏡 Personal/🏡📆 Plans/"

# Create descriptive commit
git commit -m "fix(noteplan): Fix personal plan emoji encoding

- Fixed emoji encoding in X personal plan files
- Restored Y skin tone modifier sequences
- Fixed Z ZWJ sequences (family, technologist, etc.)
- Normalized complex emojis to NFC

Skill: fix-personal-emojis

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Commit message should include:**
- Number of files fixed
- Types of fixes (skin tones, ZWJ sequences, normalization)
- Specific complex emojis handled
- Skill name for traceability

## Workflow

When invoked:

**0. Git safety and task setup:**
   - Check git status for pending changes
   - Offer to commit pending work
   - Create tasks for workflow steps
   - Mark first task as in_progress

1. **Ask for scope** (optional):
   - All personal plans
   - Specific time period (Future/Present/Past/Paused)
   - Specific file

2. **Scan files:**
   ```bash
   # Scan all personal plans
   find "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/🏡 Personal/🏡📆 Plans" -name "*.md" -type f
   ```

3. **Analyze each file:**
   - Read file content
   - Check filename emoji encoding
   - Check frontmatter emojis (especially complex ones with skin tones)
   - Check content emojis
   - Identify encoding issues

4. **Report findings:**
   ```
   Found 7 files with emoji issues in personal plans:

   Present/
   1. 🏡260115👨🏻‍💻 Learning Python.md
      - Filename emoji broken: skin tone modifier separated
      - Should be: 👨🏻‍💻 (single emoji sequence)

   2. 🏡260120🏃 Health Routine.md
      - Missing skin tone modifier
      - Should be: 🏃🏻

   Future/
   3. 🏡260125🧑‍🧑‍🧒‍🧒 Family Trip.md
      - ZWJ sequence broken in frontmatter
   ```

5. **Ask for confirmation** before making changes

6. **Fix issues:**
   - Normalize emoji encoding
   - Preserve complex emoji sequences
   - Update files carefully
   - Maintain file metadata

7. **Report results:**
   ```
   ✅ Fixed 7 files:
   - Restored 4 skin tone modifier sequences
   - Fixed 2 ZWJ sequences
   - Normalized 11 emojis in frontmatter
   ```

8. **Check for additional work needed:**

   After fixing emoji encoding, check if related skills should run:

   **a) Check if headers need syncing:**
   - Personal plans don't use folder-based organization like work plans
   - Headers typically match filename pattern
   - But still check for consistency

   Example check:
   ```
   Checking header consistency...

   Found 2 files where header doesn't match filename emoji:

   Present/
   - 🏡260115👨🏻‍💻 Learning Python.md
     Filename: 🏡260115👨🏻‍💻 ...
     Header: # 🏡 Learning Python
     ⚠️  Header missing 👨🏻‍💻

   Future/
   - 🏡260120✈️ Travel Plans.md
     Filename: 🏡260120✈️ ...
     Header: # Travel Plans
     ⚠️  Header missing 🏡✈️

   💡 Headers should match filename pattern
   ```

   **b) Check if templates need syncing:**
   - Scan all personal plan files for unique plan type emojis
   - Compare with Personal Plan template plan type list
   - If new emojis found, suggest: `/noteplan-manager:sync-plan-templates`

   Example check:
   ```
   Checking template consistency...

   Discovered plan type emojis from files:
   - Found 24 unique plan type emojis in use
   - Template lists 25 plan types

   Analysis:
   ✅ All in-use emojis are in template
   ⚠️  Template has 1 emoji not found in any files: 🪵 Backlogs

   New emojis discovered since last template update:
   - 🧘🏻 (found in 2 files) - not in template

   💡 Run /noteplan-manager:sync-plan-templates to update template
   ```

9. **Offer comprehensive fix:**
   ```
   Would you like to run the complete emoji maintenance workflow?

   1. ✅ Fix encoding (completed)
   2. Verify header consistency
   3. Update templates with newly discovered plan types

   Run all checks? (yes/no) [default: no]

   If yes:
     Checking headers...
     Running sync-plan-templates...

   All emoji maintenance complete! ✨
   ```

10. **Create git commit:**
   ```
   Creating git commit with emoji fixes...

   Files modified: 7
   Changes:
   - Restored 4 skin tone modifier sequences
   - Fixed 2 ZWJ sequences
   - Normalized 11 emojis

   Committing to git...
   ✅ Commit created: x9y8z7w
      "fix(noteplan): Fix personal plan emoji encoding"

   All tasks completed! ✅
   ```

   **Mark all tasks as completed** when done.

## Special Considerations for Personal Plans

### Complex Emoji Sequences

Personal plans use more complex emojis than work plans:

1. **Skin tone modifiers:** `🏻`, `🏼`, `🏽`, `🏾`, `🏿` (U+1F3FB - U+1F3FF)
2. **ZWJ sequences:** Multiple emojis joined with U+200D
3. **Presentation selectors:** U+FE0F for emoji presentation

### Plan Type Consistency

Ensure plan type emoji in:
- **Filename** matches frontmatter `plantype`
- **Frontmatter** uses correct emoji from template list
- **Content** references use same emoji variant

### Time-Based Organization

Unlike work plans (organized by workstream), personal plans are organized by time:
- Files can move between Future/Present/Past/Paused
- Emoji encoding should remain consistent across moves

## Safety Checks

- ✅ **Test complex emojis** (skin tones, ZWJ) carefully
- ✅ **Preserve** emoji meaning when fixing encoding
- ✅ **Back up** before modifying files with complex sequences
- ✅ **Validate** complex emoji sequences after fix
- ✅ **Don't** accidentally split multi-codepoint emojis

## Example Usage

```bash
# User invokes skill
/noteplan-manager:fix-personal-emojis

# Claude scans and reports
Found 5 files with emoji encoding issues in personal plans:

Present/
1. 🏡260115👨🏻💻 Learning Python.md
   - Technologist emoji missing ZWJ: 👨🏻💻
   - Should be: 👨🏻‍💻 (with ZWJ between components)

2. 🏡260120🏃 Health Routine.md
   - Missing skin tone modifier
   - Should be: 🏡260120🏃🏻 Health Routine.md

Future/
3. 🏡260125🧑🧑🧒🧒 Family Trip.md
   - Family emoji missing ZWJ sequences
   - Should be: 🏡260125🧑‍🧑‍🧒‍🧒 Family Trip.md

Fix these issues? (yes/no)

# User confirms
yes

# Claude fixes and reports
✅ Fixed all 5 files:
- Added ZWJ to technologist emoji in file 1
- Added skin tone modifier in file 2
- Restored family emoji ZWJ sequence in file 3
- Normalized 8 other emojis across files

All personal plan emojis are now consistent!
```

## Technical Details

### Unicode Normalization

Personal plans require careful normalization:

```python
import unicodedata

# NFC (Composed) - Preferred for display
text = unicodedata.normalize('NFC', text)

# NFD (Decomposed) - Used by macOS filesystem
filename = unicodedata.normalize('NFD', filename)
```

### Emoji Component Preservation

Keep these together:
1. Base emoji
2. Skin tone modifier (if present)
3. ZWJ (U+200D)
4. Additional emojis in sequence
5. Variation selector (U+FE0F)

Example: `👨🏻‍💻` = `👨` (person) + `🏻` (light skin) + `‍` (ZWJ) + `💻` (laptop)

## Related Skills & Comprehensive Workflow

### Related Skills

- **sync-header-emojis** - Sync header titles with filename emoji patterns
- **sync-plan-templates** - Keep plan templates in sync with plan type emojis
- **fix-work-emojis** - Fix emojis in work plans
- **analyze-structure** - Analyze NotePlan structure including emoji usage

### Complete Emoji Maintenance Workflow

For comprehensive emoji maintenance of personal plans, run skills in this order:

**1. Fix Encoding First** (this skill)
```bash
/noteplan-manager:fix-personal-emojis
```
- Fixes broken emoji encoding (especially complex sequences)
- Preserves skin tone modifiers and ZWJ sequences
- Normalizes emoji variants
- Ensures proper UTF-8 display

**2. Verify Header Consistency**
```bash
# Personal plans typically organize by time, not folders
# But headers should still match filename patterns
```
- Check that headers include plan type emoji from filename
- Ensure `🏡` namespace is present in headers
- Validate header format matches NotePlan conventions

**3. Update Templates**
```bash
/noteplan-manager:sync-plan-templates
```
- Scans all personal plan files for used plan type emojis
- Keeps Personal Plan template in sync with actual usage
- Adds newly discovered plan types
- Reports plan types that are defined but unused

**Result:** All personal plan emojis are correctly encoded, headers are consistent, and templates include all plan types you're actually using!

### When to Run Each Skill

| Situation | Skills to Run | Order |
|-----------|---------------|-------|
| **Emojis display incorrectly** | fix-personal-emojis | 1 |
| **Complex emojis broken (skin tones, ZWJ)** | fix-personal-emojis | 1 |
| **Started using new plan type emoji** | fix-personal-emojis → sync-plan-templates | 1→3 |
| **Template outdated** | sync-plan-templates | 3 |
| **Complete maintenance** | fix-personal-emojis → sync-plan-templates | 1→3 |
| **After bulk import** | fix-personal-emojis | 1 |
| **Header inconsistencies** | Manual review (personal plans vary) | - |

### Differences from Work Plans

Personal plans have different maintenance needs:

| Aspect | Work Plans | Personal Plans |
|--------|-----------|----------------|
| **Organization** | By workstream folders | By time (Future/Present/Past/Paused) |
| **Header syncing** | sync-header-emojis (folder-based) | Verify manually (filename-based) |
| **Template source** | Subdirectory names | File content analysis |
| **Emoji complexity** | Simpler | Complex (skin tones, ZWJ) |
| **Frequency** | After folder changes | After discovering new plan types |

### Quick Check Commands

Before running this skill, you can manually check:

```bash
# Check for emoji encoding issues (especially complex ones)
find "/Users/omar.eid/.../🏡📆 Plans" -name "*.md" -exec grep -l "�" {} \;

# Check for plan types in use
find "/Users/omar.eid/.../🏡📆 Plans" -name "*.md" -exec head -1 {} \; | grep -o "🏡[0-9]*." | sort -u

# Check template plan types
cat "/Users/omar.eid/.../🏡📆 Personal Plan.md" | grep "planType"
```

### Automated Maintenance Suggestion

Consider running maintenance:
- **After using new plan type:** Run fix-personal-emojis + sync-plan-templates
- **Monthly:** Quick encoding check (complex emojis can break)
- **After template changes:** Run sync-plan-templates
- **After bulk operations:** Run fix-personal-emojis to ensure encoding survived

### Special Note on Complex Emojis

Personal plans use many complex emojis that require extra care:
- **Skin tone modifiers:** `👨🏻‍💻`, `🏃🏻`, `👨🏻‍🏫`, `🧎🏻`, `🧘🏻`
- **ZWJ sequences:** `🧑‍🧑‍🧒‍🧒`, `👨🏻‍💻`, `👨🏻‍💼`
- **Variation selectors:** `⚙️`, `✈️`, `⚖️`

Run this skill more frequently than fix-work-emojis due to complexity.

## Tips

- **Handle with care** - Complex emojis are fragile
- **Test one file** before batch operations
- **Check rendering** after fixes to ensure they display correctly
- **Use Unicode tools** to inspect emoji sequences when debugging
- **Keep plan type list** synced with template
