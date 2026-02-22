---
name: validate-role
description: Validates a role directory against personalbook conventions. Checks for required files, proper structure, frontmatter, and orphaned content. Use when checking if a role is properly structured or before committing role changes.
link: not
---

# Validating a Role

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Validate this role"
- "Check if this role is properly structured"
- "Is this role following conventions?"
- "Validate [Role Name]"
- Or using the slash command: `/role-manager:validate-role`

## Purpose

This skill validates that a role directory follows personalbook conventions, identifying missing files, structural issues, and potential problems before they cause issues.

## Role Identification

**CRITICAL**: Before proceeding, identify the specific role to validate.

If not provided, ask: "Which role would you like me to validate? (e.g., roles-self-development/The Self Reflector)"

## Validation Checklist

### 1. Required Files

Every role MUST have:

| File | Purpose | Check |
|------|---------|-------|
| **Overview.md** | Role description, component tables | ❌ Missing / ✅ Present |
| **Responsibilities.md** | Inputs, outputs, success metrics | ❌ Missing / ✅ Present |

### 2. Directory Structure

Check these directories exist if role has content for them:

| Directory | When Required | Check |
|-----------|--------------|-------|
| **skills/** | Role has reusable processes | ❌/✅ |
| **habits/** | ALWAYS (every role should have habits, even ideating) | ❌/✅ |
| **artifacts/** | Role has personal content | ❌/✅ |
| **knowledge/** | Role has reference material | ❌/✅ |
| **decisions/** | Role has major choices | ❌/✅ |
| **expectations/** | Role has standards to embody | ❌/✅ |

### 3. Skill Structure

For each skill in `skills/`:

| Check | Requirement |
|-------|-------------|
| Directory named in kebab-case | `reflecting-on-learnings/` not `Reflecting on Learnings/` |
| Contains SKILL.md | Required file |
| SKILL.md has frontmatter | `name`, `description` fields |
| Frontmatter `name` matches directory | `reflecting-on-learnings` matches `reflecting-on-learnings/` |
| Has `status` field | `ideating`, `establishing`, `practicing`, `established`, `paused`, `retired` |

### 4. Habit Structure

For each habit in `habits/`:

| Check | Requirement |
|-------|-------------|
| Directory named in kebab-case | `daily-reflection/` not `Daily Reflection/` |
| Contains HABIT.md | Required file |
| HABIT.md has frontmatter | `name`, `description`, `frequency`, `timing` fields |
| Has `status` field | `ideating`, `establishing`, `practicing`, `established`, `paused`, `retired` |
| References skills used | Links to skill files |

### 5. Artifact Structure

For each artifact in `artifacts/`:

| Check | Requirement |
|-------|-------------|
| Has frontmatter | `intent`, `habits` fields |
| File named in kebab-case | `reflecting-on-actions.md` not `Reflecting on Actions.md` |
| Personal content only | No generic questions without answers |

### 6. Knowledge Structure

For each file in `knowledge/`:

| Check | Requirement |
|-------|-------------|
| Has frontmatter | `topic`, `status` fields |
| Contains prerequisite info | Not experiential wisdom (that goes in artifacts) |

### 7. Overview.md Structure

Overview.md should contain:

| Section | Required For |
|---------|-------------|
| Role description | All roles |
| Skills table | Roles with skills |
| Habits table | All roles |
| Expectations table | Roles with expectations |
| Knowledge Areas table | Roles with knowledge |
| Decisions table | Roles with decisions |

### 8. Orphaned Content Check

Look for content that should be organized:

```bash
# Find files not in standard directories
find "[role-path]" -type f \( -name "*.md" -o -name "*.txt" \) | grep -v "/skills/" | grep -v "/habits/" | grep -v "/artifacts/" | grep -v "/knowledge/" | grep -v "/decisions/" | grep -v "/expectations/" | grep -v "Overview.md" | grep -v "Responsibilities.md"
```

### 9. Cross-Role Content Check

Scan for content that might belong elsewhere:

| Content Pattern | Likely Destination |
|-----------------|-------------------|
| `#id:motivational-quote` | `roles/The Motivator/` |
| Religious/spiritual content | `roles-self-development/The Servant/` |
| Career/vocation content | `roles-business-development/` |
| Learning/education content | `roles-self-development/The Learner/` |

### 10. File Naming Conventions

| Check | Requirement |
|-------|-------------|
| All directories use kebab-case | `reflecting-on-learnings/` not `Reflecting on Learnings/` |
| All files use .md extension | Not .txt (except for historical artifacts) |
| No spaces in file names | Use hyphens instead |

## Validation Commands

Run these commands to check the role:

```bash
# 1. Check required files exist
ls -la "[role-path]/Overview.md" "[role-path]/Responsibilities.md"

# 2. Check directory structure
ls -la "[role-path]/"

# 3. Check skill frontmatter
for skill in "[role-path]/skills/"*/SKILL.md; do
  echo "=== $skill ==="
  head -20 "$skill"
done

# 4. Check habit frontmatter
for habit in "[role-path]/habits/"*/HABIT.md; do
  echo "=== $habit ==="
  head -20 "$habit"
done

# 5. Find orphaned files
find "[role-path]" -type f \( -name "*.md" -o -name "*.txt" \) | grep -vE "/(skills|habits|artifacts|knowledge|decisions|expectations)/"

# 6. Check for cross-role content
grep -r "#id:motivational-quote\|Quran\|Ramadan\|prayer" "[role-path]/"
```

## Validation Report Template

After validation, generate a report:

```markdown
# Role Validation Report: [Role Name]

**Path**: [role-path]
**Date**: [date]

## Summary

| Category | Status | Issues |
|----------|--------|--------|
| Required Files | ✅/❌ | [count] |
| Directory Structure | ✅/❌ | [count] |
| Skills | ✅/❌ | [count] |
| Habits | ✅/❌ | [count] |
| Artifacts | ✅/❌ | [count] |
| File Naming | ✅/❌ | [count] |

## Issues Found

### Critical (Must Fix)
1. [Issue description]
2. [Issue description]

### Warnings (Should Fix)
1. [Issue description]
2. [Issue description]

### Suggestions (Nice to Have)
1. [Suggestion]
2. [Suggestion]

## Recommendations

[List of specific actions to fix issues]
```

## Common Issues

### Issue: Missing habits/ directory

**Problem**: Role has no habits directory
**Fix**: Create `habits/` and add at least one habit with `status: ideating`

### Issue: Skill missing frontmatter

**Problem**: SKILL.md doesn't have frontmatter block
**Fix**: Add frontmatter with `name`, `description`, `status` fields

### Issue: Mixed case file names

**Problem**: Files like `Reflecting on Actions.md`
**Fix**: Rename to `reflecting-on-actions.md`

### Issue: Orphaned personal content

**Problem**: Personal reflections in root of role directory
**Fix**: Move to `artifacts/` with proper frontmatter

### Issue: Cross-role content present

**Problem**: Content that belongs in another role
**Fix**: Use `/role-manager:migrate-content` to move safely

## Post-Validation Actions

After validation, recommend:

1. **Fix critical issues first** - Missing required files, broken structure
2. **Address warnings** - Missing frontmatter, naming conventions
3. **Consider suggestions** - Optimizations, better organization
4. **Run `/role-manager:structure-role`** - For comprehensive restructuring if many issues
