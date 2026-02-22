---
name: archive-role
description: Removes or merges a role that is no longer needed. Use when a role is obsolete, redundant, or should be consolidated with another role. Ensures safe content preservation before deletion.
link: not
---

# Archiving a Role

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Remove this role"
- "Delete [Role Name]"
- "Merge [Role A] into [Role B]"
- "Archive this role"
- "This role is no longer needed"
- Or using the slash command: `/role-manager:archive-role`

## Purpose

This skill safely removes or merges roles that are no longer needed, ensuring all valuable content is preserved before deletion.

## Two Archive Options

| Option | When to Use | Process |
|--------|-------------|---------|
| **Remove Entirely** | Role is obsolete, no valuable content | Verify empty/obsolete → Delete |
| **Merge Into Another** | Role overlaps with another, content is valuable | Migrate content → Verify → Delete source |

## Option 1: Remove Entirely

Use when the role has no valuable content or is completely obsolete.

### Step 1: Verify Role is Safe to Delete

```bash
# List all files in the role
find "[role-path]/" -type f \( -name "*.md" -o -name "*.txt" \)

# Count total content lines
find "[role-path]/" -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l

# Check for high-value content
grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" "[role-path]/"
```

### Step 2: Check for Dependencies

```bash
# Find references to this role from other roles
grep -r "[[Role Name]]" --include="*.md" . | grep -v "[role-path]"
grep -r "[Role Name]" --include="*.md" . | grep -E "\[.*\]\(.*[Role Name]" | grep -v "[role-path]"

# Find skills that extend skills from this role
grep -r "extends:" --include="*.md" . | grep "[role-name]"
```

### Step 3: Get User Confirmation

Present to user:
- Number of files to delete
- Total content lines
- Any high-value markers found
- Any dependencies found

**Ask**: "This role has [N] files with [M] lines. [Dependencies/No dependencies] found. Proceed with deletion?"

### Step 4: Delete the Role

```bash
# Use git rm for recovery option
git rm -r "[role-path]/"

# Commit with clear message
git commit -m "Remove [Role Name] - role no longer needed

Reason: [Why the role was removed]
Content: [X files, Y lines - all obsolete/empty]"
```

## Option 2: Merge Into Another Role

Use when the role has valuable content that should be preserved elsewhere.

### Step 1: Create Content Mapping

**⛔ CRITICAL: Map ALL content before deleting anything ⛔**

Create a comprehensive mapping table:

| Source File | Content Type | Lines | Destination | Status |
|-------------|--------------|-------|-------------|--------|
| Overview.md | Role description | 45 | [dest-role]/Overview.md (Role Evolution) | Pending |
| skills/skill-a/ | Skill | 120 | [dest-role]/skills/skill-a/ | Pending |
| habits/habit-b/ | Habit | 80 | [dest-role]/habits/habit-b/ | Pending |
| artifacts/notes.md | Personal content | 200 | [dest-role]/artifacts/notes.md | Pending |

### Step 2: Identify Cross-Role Destinations

Some content may belong in different roles entirely:

| Content Type | Likely Destination |
|--------------|-------------------|
| Motivational quotes (`#id:`) | `roles/The Motivator/` |
| Spiritual content | `roles-self-development/The Servant/` |
| Learning content | `roles-self-development/The Learner/` |
| Discipline content | `roles-self-development/The Self Master/` |

### Step 3: Get User Approval

Present the mapping to user:

```markdown
## Proposed Migration Plan

### To [Destination Role]
- skills/skill-a/ (120 lines)
- habits/habit-b/ (80 lines)
- artifacts/notes.md (200 lines)

### To Other Roles
- [spiritual content] → The Servant (50 lines)
- [quotes] → The Motivator (30 lines)

### Content to Delete (duplicate/obsolete)
- Overview.md header sections (structural only)

**Total**: 500 lines to migrate, 20 lines to delete

Proceed with this plan?
```

### Step 4: Execute Migrations

Use `/role-manager:migrate-content` for each piece:

1. **Migrate to primary destination first**
2. **Migrate cross-role content second**
3. **Verify each migration before proceeding**

### Step 5: Update Destination Role

Add to destination role's Overview.md:

```markdown
## Role Evolution

- **Merged Roles**:
  - [Source Role Name] - [date] - [what was absorbed]
```

### Step 6: Verify All Content Migrated

```bash
# Compare line counts
echo "Source total:"
find "[source-role]/" -type f \( -name "*.md" -o -name "*.txt" \) -exec cat {} \; | grep -v '^[[:space:]]*$' | wc -l

echo "Destination additions:"
git diff --stat HEAD~N -- "[dest-role]/" | tail -1

# Check high-value markers migrated
echo "Source high-value:"
grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" "[source-role]/" | wc -l

echo "Destination high-value:"
grep -r "#id:\|https://\|>20[0-9][0-9]\|\[ \]" "[dest-role]/" | wc -l
```

### Step 7: Delete Source Role

Only after verification:

```bash
git rm -r "[source-role]/"

git commit -m "Merge [Source Role] into [Dest Role]

All content migrated:
- skills/: [X] skills moved
- habits/: [Y] habits moved
- artifacts/: [Z] lines migrated
- Cross-role: [content] → [roles]

Verification:
- Source: [N] lines
- Migrated: [M] lines
- Gap: [explained]"
```

## Merge Strategies

### Strategy 1: Absorb Entirely

Source role is completely absorbed into destination:
- All skills → destination skills/
- All habits → destination habits/
- All artifacts → destination artifacts/
- All knowledge → destination knowledge/

### Strategy 2: Distribute Across Roles

Source role content goes to multiple destinations:
- Technical skills → software-development role
- Management skills → business-development role
- Personal growth → self-development role

### Strategy 3: Partial Merge

Only some content is valuable:
- Migrate valuable content
- Delete obsolete content
- Document what was discarded

## Archive Report Template

```markdown
# Role Archive Report

**Date**: [YYYY-MM-DD]
**Role Archived**: [Role Name]
**Archive Type**: Remove Entirely / Merge Into [Role]

## Pre-Archive State

| Metric | Value |
|--------|-------|
| Total Files | [N] |
| Total Lines | [N] |
| Skills | [N] |
| Habits | [N] |
| Artifacts | [N] |
| High-Value Markers | [N] |

## Dependencies Checked

| Reference From | Reference Type | Updated |
|----------------|----------------|---------|
| [file] | [[link]] | ✅/N/A |

## Content Disposition

### Migrated
| Content | Lines | Destination |
|---------|-------|-------------|
| [skill] | [N] | [dest] |

### Deleted (obsolete)
| Content | Lines | Reason |
|---------|-------|--------|
| [file] | [N] | [reason] |

## Verification

- [ ] All content mapped before deletion
- [ ] High-value markers accounted for
- [ ] Dependencies updated
- [ ] User approved deletion
- [ ] Git commit with clear message

## Recovery Information

To recover this role if needed:
```bash
git checkout [commit-before-deletion] -- "[role-path]/"
```
Last good commit: [commit-hash]
```

## Safety Checklist

Before archiving ANY role:

- [ ] Listed ALL files with line counts
- [ ] Searched for high-value markers (#id:, URLs, dates, TODOs)
- [ ] Checked for dependencies from other roles
- [ ] Created content mapping table
- [ ] Identified cross-role destinations
- [ ] Got user approval for the plan
- [ ] Migrated all valuable content
- [ ] Verified migrations with line counts
- [ ] Updated destination role's Overview.md
- [ ] Removed cross-references
- [ ] Committed with descriptive message
- [ ] Recorded recovery information
