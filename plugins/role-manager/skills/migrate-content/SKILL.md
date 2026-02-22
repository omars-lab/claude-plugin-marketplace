---
name: migrate-content
description: Safely migrates content between roles following the Content Preservation Protocol. Use when moving content from one role to another, merging partial role content, or relocating misplaced content.
link: not
---

# Migrating Content Between Roles

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Move this content to another role"
- "Migrate content from [Role A] to [Role B]"
- "This content belongs in a different role"
- "Relocate [content] to [destination role]"
- Or using the slash command: `/role-manager:migrate-content`

## Purpose

This skill provides a safe, verified process for migrating content between roles, ensuring no content is lost during the move.

## The #1 Rule: When In Doubt, Keep It

**If you're unsure where content belongs, DO NOT DELETE IT.** Options:
1. Create a `holding/` directory for ambiguous content
2. Ask the user where it should go
3. Add it to an artifact with a `## Unsorted` section
4. Keep in original location until clarified

## Migration Workflow

### Phase 1: Identify Source and Destination

1. **Identify source content**:
   - What file(s) or content sections are being migrated?
   - What is the current location?
   - What is the line count?

2. **Identify destination role**:
   - Which role should receive this content?
   - What component type? (skill, artifact, knowledge, etc.)
   - Does the destination already have similar content to merge with?

3. **Get user confirmation**:
   - "I'll migrate [X] from [Source] to [Destination]. Proceed?"

### Phase 2: Pre-Migration Audit

Before migrating, run these checks:

```bash
# Count source lines
cat "[source-file]" | grep -v '^[[:space:]]*$' | wc -l

# Check for high-value markers
grep -E "#id:|https://|>20[0-9][0-9]|\[ \]" "[source-file]"

# Document what will be migrated
```

**Create a migration mapping:**

| Source | Content Type | Lines | Destination | Status |
|--------|--------------|-------|-------------|--------|
| `[file]` | [type] | [N] | `[dest-file]` | Pending |

### Phase 3: Execute Migration

1. **Read the ENTIRE source file** - Don't skim
2. **Create/update destination file** with proper frontmatter
3. **Add source attribution**: `### From [Source Role/File]`
4. **Preserve exact formatting**: hashtags, indentation, dates, checkboxes

**Migration template for destination:**

```markdown
---
intent: [What this artifact/knowledge captures]
migrated_from: [source-role/source-file]
migration_date: [YYYY-MM-DD]
---

# [Title]

### From [Source Role/File]
[Migrated content with exact formatting preserved]
```

### Phase 4: Verify Migration

**⛔ DO NOT DELETE SOURCE UNTIL VERIFIED ⛔**

1. **Re-read source file** line by line
2. **For EACH item**, verify it exists in destination
3. **Run line count check**:
   ```bash
   # Source lines
   cat "[source-file]" | grep -v '^[[:space:]]*$' | wc -l

   # Added to destination (approximate)
   git diff --stat HEAD -- "[dest-file]" | tail -1
   ```
4. **Spot-check 5+ unique phrases** in destination
5. **Check high-value markers migrated**:
   ```bash
   # Verify URLs migrated
   grep -E "https?://" "[dest-file]"

   # Verify tagged content migrated
   grep -E "#id:" "[dest-file]"
   ```

### Phase 5: Cleanup Source

Only after verification is complete:

1. **Show user what will be deleted**
2. **Get explicit approval**
3. **Use git rm** (not rm) for recovery option:
   ```bash
   git rm "[source-file]"
   ```
4. **Or mark as deprecated** instead of deleting:
   ```markdown
   ---
   status: deprecated
   migrated_to: [destination-path]
   migration_date: [YYYY-MM-DD]
   ---

   # [Title]

   **⚠️ This content has been migrated to [destination-path]**
   ```

## Content Type Guidelines

### Migrating Skills

**From**: `source-role/skills/skill-name/SKILL.md`
**To**: `dest-role/skills/skill-name/SKILL.md`

1. Create skill directory in destination
2. Copy SKILL.md with updated frontmatter
3. Update any relative paths in the skill
4. Add note in source role's Overview about migration

### Migrating Artifacts

**From**: `source-role/artifacts/file.md`
**To**: `dest-role/artifacts/file.md`

1. Check if destination has similar artifact to merge into
2. Add `### From [Source Role]` section header
3. Preserve all personal content, dates, checkboxes

### Migrating Knowledge

**From**: `source-role/knowledge/topic.md`
**To**: `dest-role/knowledge/topic.md`

1. Verify content is truly prerequisite knowledge (not experiential)
2. Update frontmatter with new topic context
3. Check for role-specific references to update

### Migrating Decisions

**From**: `source-role/decisions/decision-name/`
**To**: `dest-role/decisions/decision-name/`

1. Copy entire decision directory
2. Update any relative links
3. Check if decision context changes with new role

### Migrating Cross-Role Content

Common cross-role migrations:

| Content Type | Destination |
|--------------|-------------|
| Motivational quotes (`#id:motivational-quote-*`) | `roles/The Motivator/` |
| Spiritual/religious content | `roles-self-development/The Servant/` |
| Learning/education content | `roles-self-development/The Learner/` |
| Purpose/identity content | `roles-self-development/The Self Reflector/` |
| Discipline/habit content | `roles-self-development/The Self Master/` |

## Migration Report Template

After migration, provide a report:

```markdown
# Migration Report

**Date**: [YYYY-MM-DD]
**Source**: [source-role/source-file]
**Destination**: [dest-role/dest-file]

## Content Migrated

| Item | Type | Lines | Verified |
|------|------|-------|----------|
| [description] | [skill/artifact/etc] | [N] | ✅/❌ |

## High-Value Markers

- URLs: [count] found, [count] migrated
- Tagged items (`#id:`): [count] found, [count] migrated
- Dated entries: [count] found, [count] migrated
- TODO items: [count] found, [count] migrated

## Source Cleanup

- [ ] Source file deleted via `git rm`
- [ ] Or source file marked as deprecated

## Verification

- [ ] Line count matches (±10%)
- [ ] Unique phrases spot-checked
- [ ] High-value markers verified
- [ ] User approved deletion
```

## Recovery: If Content Was Lost

If you discover content was lost after migration:

```bash
# Find the commit before migration
git log --oneline -20

# View the original file
git show <commit>:"path/to/source/file.md"

# Recover the file
git checkout <commit> -- "path/to/source/file.md"

# Re-migrate properly
```

## Best Practices

1. **Small migrations** - Migrate one file/section at a time
2. **Commit frequently** - Commit after each successful migration
3. **Descriptive commits** - "Migrate X from Role A to Role B"
4. **Never assume** - Verify every item migrated
5. **Preserve context** - Include source attribution
6. **Get approval** - User must approve deletions
