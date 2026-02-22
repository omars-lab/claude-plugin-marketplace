---
name: verifying-content-preservation
description: Guide for using git diff line counts to verify no content was lost during role migrations and restructuring.
---

# Verifying Content Preservation

This guide provides a systematic approach to verify that content wasn't lost during role migrations using git diff line counts.

## Why Line Count Verification?

During migrations, it's easy to:
- Miss nested content or indented items
- Forget personal notes inline with questions
- Skip links, resources, or dated entries
- Assume content was migrated when it wasn't

Line count analysis catches these gaps quantitatively.

## Quick Check Command

```bash
# Compare insertions vs deletions for a migration
git diff --stat HEAD~N -- "path/to/affected/roles" | tail -1

# Example output:
# 158 files changed, 1456 insertions(+), 1760 deletions(-)
```

If deletions significantly exceed insertions (more than ~15-20%), investigate.

## Full Verification Process

### Step 1: Identify the Baseline Commit

Find the commit before migration started:

```bash
git log --oneline -20
```

Note the commit hash or use relative reference like `HEAD~5`.

### Step 2: Get High-Level Diff Stats

```bash
# Overall stats for affected directories
git diff --stat <baseline> -- "path/to/old/role1" "path/to/old/role2" "path/to/new/role" | tail -1
```

This shows total insertions/deletions across the migration.

### Step 3: Count Non-Blank Lines

Count actual content lines (excluding whitespace-only lines):

```bash
# Current state
find path/to/new/role -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l

# Old state (using git show)
git show <baseline>:"path/to/old/role/file.md" | grep -v '^[[:space:]]*$' | wc -l
```

### Step 4: Identify What Was Deleted

View the actual deleted content:

```bash
# Show all deleted non-blank lines
git diff <baseline> -- "path/to/old/role" | grep "^-" | grep -v "^---" | grep -v '^-[[:space:]]*$' | head -100

# Filter for specific content types
git diff <baseline> | grep "^-" | grep -iE "(http|https|\.com|\.org)"  # Links
git diff <baseline> | grep "^-" | grep "\[ \]"                         # TODO items
git diff <baseline> | grep "^-" | grep ">"                             # Dated entries
```

### Step 5: Check Specific Files

If suspicious content appears in the diff:

```bash
# View old file content
git show <baseline>:"path/to/old/role/Specific File.md"

# Compare against current files
grep -r "specific phrase" path/to/new/role/
```

## Expected Line Reduction Factors

Not all line reduction indicates lost content. Account for:

### 1. Structural Overhead Removed

Old roles often had:
- Duplicate frontmatter across multiple files
- Separate Overview files for each role being merged
- Redundant headers and section markers

**Estimate**: ~10-20 lines per merged role

### 2. Duplicate Content Consolidated

The same questions often appeared in multiple files:
- "What are my goals?" might appear in 3+ places
- Generic reflection questions repeated across roles

**Estimate**: ~5-15% of original content may be legitimate duplicates

### 3. Intentionally Excluded Content

Some content doesn't belong in the destination role:
- Character/commitment content → Self Master or Striver
- Technical learning → Learner role
- Career decisions → Career roles

**Action**: Document what was intentionally excluded and where it should go

### 4. Empty Headers/Sections Removed

Old files often had:
- `## Section` with no content
- Placeholder text
- Abandoned organizational structures

**Estimate**: Variable, usually 2-5% of lines

## Creating an Adjustment Table

For transparency, create a table explaining line differences:

```markdown
## Line Count Analysis

| Factor | Lines | Notes |
|--------|-------|-------|
| Original content (4 roles) | 1,760 | From deletions count |
| New content (Learner) | 1,456 | From insertions count |
| **Gap** | **304** | |

### Accounting for Gap:

| Category | Est. Lines | Explanation |
|----------|------------|-------------|
| Structural overhead | ~60 | 4 Overview files → 1, frontmatter consolidation |
| Duplicate questions | ~80 | Same questions in Student/Learner/Developer of My Skills |
| Intentionally excluded | ~100 | Character/commitment content → Self Master |
| Empty sections removed | ~40 | Placeholder headers with no content |
| Possible content loss | ~24 | Requires investigation |
```

## Recovery Process

When line counts indicate possible content loss:

### 1. Generate Comprehensive Diff

```bash
git diff <baseline> -- "path/to/affected" | grep "^-" | grep -v "^---" | grep -v '^-[[:space:]]*$' > /tmp/deleted-lines.txt
```

### 2. Categorize Deleted Content

Review `/tmp/deleted-lines.txt` and categorize:
- ✅ Migrated (found in new location)
- ✅ Duplicate (consolidated with similar content)
- ⚠️ Excluded (belongs elsewhere - note where)
- ❌ Lost (needs to be recovered)

### 3. Recover Lost Content

For each ❌ Lost item:

```bash
# Find the original file
git show <baseline>:"path/to/original/file.md"

# Add to appropriate destination file
```

### 4. Re-verify After Recovery

Run the line count comparison again to confirm gap has narrowed.

## Automation Script

For frequent migrations, use this verification script:

```bash
#!/bin/bash
# verify-migration.sh <baseline-commit> <old-paths> <new-path>

BASELINE=$1
OLD_PATHS=$2
NEW_PATH=$3

echo "=== Migration Verification ==="
echo "Baseline: $BASELINE"
echo ""

# Overall stats
echo "=== Diff Stats ==="
git diff --stat $BASELINE -- $OLD_PATHS $NEW_PATH | tail -3

echo ""
echo "=== Current Non-Blank Lines ==="
find $NEW_PATH -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l

echo ""
echo "=== Deleted Links ==="
git diff $BASELINE -- $OLD_PATHS | grep "^-" | grep -iE "(http|https)" | head -10

echo ""
echo "=== Deleted TODOs ==="
git diff $BASELINE -- $OLD_PATHS | grep "^-" | grep "\[ \]" | head -10
```

## Checklist: Post-Migration Verification

- [ ] Run `git diff --stat` to get insertion/deletion counts
- [ ] Calculate gap percentage (deletions - insertions) / deletions
- [ ] If gap > 20%, investigate further
- [ ] Count non-blank lines in new structure
- [ ] Review deleted lines for links, TODOs, dated entries
- [ ] Create adjustment table explaining expected reductions
- [ ] Recover any identified lost content
- [ ] Re-verify after recovery
- [ ] Document any content intentionally excluded (and where it should go)

## High-Level Verification (After Multiple Commits)

**CRITICAL**: Per-commit checks can miss cumulative content loss. After a migration period, run a high-level check across ALL commits.

### Why Both Per-Commit AND High-Level?

| Check Type | What It Catches | Misses |
|------------|-----------------|--------|
| Per-commit | Immediate issues in single commit | Cumulative loss across commits |
| High-level | Total content balance over time | Which specific commit caused loss |

### High-Level Verification Commands

```bash
# 1. Find baseline commit (before migrations started)
git log --oneline -30

# 2. Overall stats from baseline to now
git diff --stat <baseline>..HEAD -- roles-self-development/ roles/ | tail -1
# Expected: Insertions >= Deletions (or close, with documented gap reasons)

# 3. Check high-value markers
echo "=== HIGH-VALUE MARKER CHECK ==="

echo "Motivational quotes:"
echo "  Deleted: $(git diff <baseline>..HEAD | grep "^-" | grep -c "#id:motivational-quote")"
echo "  Current: $(grep -r "#id:motivational-quote" --include="*.md" | wc -l)"

echo "URLs:"
echo "  Deleted: $(git diff <baseline>..HEAD -- roles-self-development/ roles/ | grep "^-" | grep -cE "https?://")"
echo "  Added: $(git diff <baseline>..HEAD -- roles-self-development/ roles/ | grep "^+" | grep -cE "https?://")"

echo "Dated entries:"
echo "  Deleted: $(git diff <baseline>..HEAD | grep "^-" | grep -cE ">[0-9]{4}-[0-9]{2}")"
echo "  Added: $(git diff <baseline>..HEAD | grep "^+" | grep -cE ">[0-9]{4}-[0-9]{2}")"

echo "TODO items:"
echo "  Deleted: $(git diff <baseline>..HEAD | grep "^-" | grep -c "\[ \]")"
echo "  Added: $(git diff <baseline>..HEAD | grep "^+" | grep -c "\[ \]")"
```

### Investigating High-Level Gaps

If high-level check shows significant gaps:

1. **Check for intentional external moves**:
   ```bash
   git log --oneline <baseline>..HEAD | grep -iE "blog|external|move|moving"
   ```

2. **Identify which commits caused the loss**:
   ```bash
   # For each migration commit, check its individual stats
   git diff --stat <commit>~1..<commit> | tail -1
   ```

3. **Sample deleted content to categorize**:
   ```bash
   git diff <baseline>..HEAD | grep "^-" | grep -E "https?://" | head -30
   ```

### Expected Gap Reasons

Document any gap with these categories:

| Category | Expected? | Action |
|----------|-----------|--------|
| Structural overhead | Yes | No action needed |
| Intentional external move | Yes | Document where content went |
| Duplicate consolidation | Yes | No action needed |
| Cross-role migration | Yes | Verify content in destination role |
| **Unaccounted loss** | **NO** | **Recover immediately** |
