---
name: reorganize-roles
description: Moves roles between categories (self-development, software-development, business-development, etc.) following organizational conventions. Use when a role belongs in a different category or when restructuring role groupings.
link: not
---

# Reorganizing Roles Between Categories

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Move this role to a different category"
- "This role belongs in software-development"
- "Reorganize [Role Name] to [category]"
- "Change the category for [Role Name]"
- Or using the slash command: `/role-manager:reorganize-roles`

## Purpose

This skill moves entire roles between category directories (e.g., from `roles-career/` to `roles-business-development/`) while preserving all content and updating cross-references.

## Role Categories

Roles are organized by what they **develop**:

| Category | What It Develops | Directory |
|----------|------------------|-----------|
| **Self-Development** | The person (you) | `roles-self-development/` |
| **Software-Development** | Software systems | `roles-software-development/` |
| **Business-Development** | Businesses/organizations | `roles-business-development/` |
| **Life Roles** | Life experiences | `roles/` |
| **Family** | Family relationships | `roles-family/` |
| **Creative** | Creative works | `roles-creative/` |

See [guides/role-groupings.md](../structure-role/guides/role-groupings.md) for detailed category descriptions.

## Deciding Where a Role Belongs

Ask these questions:

1. **What does this role primarily build/develop?**
   - Yourself → `roles-self-development/`
   - Software → `roles-software-development/`
   - Business/organization → `roles-business-development/`
   - Experiences → `roles/`

2. **What knowledge overlaps with other roles in that category?**
   - If 70%+ knowledge overlap → belongs in that category

3. **What is the primary outcome?**
   - Personal growth → self-development
   - Working software → software-development
   - Business success → business-development

4. **Who are the stakeholders/beneficiaries?**
   - Yourself → self-development
   - Users/systems → software-development
   - Organization/investors/customers → business-development

## Reorganization Workflow

### Phase 1: Verify the Move

1. **Confirm current location**:
   ```bash
   ls -la "[current-path]/[Role Name]/"
   ```

2. **Confirm destination category exists**:
   ```bash
   ls -la "[destination-category]/"
   ```

3. **Check for naming conflicts**:
   ```bash
   ls -la "[destination-category]/[Role Name]/" 2>/dev/null
   ```

4. **Get user confirmation**:
   - "I'll move [Role Name] from [source-category] to [dest-category]. Proceed?"

### Phase 2: Pre-Move Audit

Document the current state:

```bash
# Count all files in the role
find "[current-path]/[Role Name]/" -type f | wc -l

# List all files
find "[current-path]/[Role Name]/" -type f -name "*.md"

# Check for cross-references to this role
grep -r "[[Role Name]]" --include="*.md" .
grep -r "[Role Name]" --include="*.md" . | grep -E "\[.*\]\(.*[Role Name]"
```

### Phase 3: Execute the Move

1. **Move the role directory**:
   ```bash
   git mv "[source-category]/[Role Name]" "[dest-category]/[Role Name]"
   ```

2. **Update the role's Overview.md**:
   Add to Role Evolution section:
   ```markdown
   ## Role Evolution

   - **Previous Locations**: [source-category]/
   - **Current Location**: [dest-category]/
   - **Move Date**: [YYYY-MM-DD]
   - **Reason**: [Why the role was moved]
   ```

3. **Update relative paths** in the role if any exist

### Phase 4: Update Cross-References

1. **Find all references to the role**:
   ```bash
   grep -rn "[[Role Name]]" --include="*.md" .
   grep -rn "[source-category]/[Role Name]" --include="*.md" .
   ```

2. **Update each reference** to point to new location

3. **Update category Overview.md files**:
   - Remove from source category's Overview.md
   - Add to destination category's Overview.md

### Phase 5: Handle Cross-Category Roles

Some roles belong in multiple categories (e.g., The CTO is both business and technical).

**Pattern: Primary location + Cross-reference**

1. **Place role in primary category** (where outcome is focused)
2. **Add cross-reference** in secondary category's Overview.md:

```markdown
## Cross-Category Roles

| Role | Primary Category | Why Cross-Listed |
|------|-----------------|------------------|
| [The CTO](../roles-business-development/The%20CTO/) | Business Development | Deep technical knowledge required |
```

### Phase 6: Verify the Move

```bash
# Confirm role exists in new location
ls -la "[dest-category]/[Role Name]/"

# Confirm old location is empty/removed
ls -la "[source-category]/[Role Name]/" 2>/dev/null

# Check file count matches
find "[dest-category]/[Role Name]/" -type f | wc -l

# Verify cross-references updated
grep -r "[source-category]/[Role Name]" --include="*.md" .
```

### Phase 7: Commit the Change

```bash
git add -A
git commit -m "Move [Role Name] from [source-category] to [dest-category]

Reason: [Why the role was moved]

Updated cross-references:
- [list of files updated]"
```

## Deprecating Old Categories

When reorganizing multiple roles, you may need to deprecate an entire category:

1. **Ensure all roles are moved**:
   ```bash
   ls -la "[old-category]/"
   # Should show only Overview.md or be empty
   ```

2. **Update Overview.md** with deprecation notice:
   ```markdown
   ---
   status: deprecated
   deprecated_date: [YYYY-MM-DD]
   migrated_to: [new-categories]
   ---

   # [Category Name] (DEPRECATED)

   **⚠️ This category has been deprecated.**

   Roles have been moved to:
   - [Role A] → [new-category]/
   - [Role B] → [new-category]/
   ```

3. **Delete the category** (after confirming empty):
   ```bash
   git rm -r "[old-category]/"
   ```

## Reorganization Report Template

```markdown
# Role Reorganization Report

**Date**: [YYYY-MM-DD]
**Role**: [Role Name]
**From**: [source-category]/
**To**: [dest-category]/

## Reason for Move

[Explanation of why the role belongs in the new category]

## Files Moved

| File | Status |
|------|--------|
| Overview.md | ✅ |
| Responsibilities.md | ✅ |
| skills/ | ✅ |
| habits/ | ✅ |
| artifacts/ | ✅ |

## Cross-References Updated

| File | Reference Type | Updated |
|------|----------------|---------|
| [file-path] | [[link]] | ✅ |

## Category Overview Updates

- [ ] Removed from [source-category]/Overview.md
- [ ] Added to [dest-category]/Overview.md
- [ ] Cross-reference added (if cross-category role)

## Verification

- [ ] Role exists in new location
- [ ] Old location removed
- [ ] File count matches
- [ ] No broken cross-references
```

## Common Reorganizations

| Role | From | To | Reason |
|------|------|-----|--------|
| The CTO | roles-career/ | roles-business-development/ | Primary outcome is business success |
| The Developer | roles-career/ | roles-software-development/ | Primary focus is building software |
| The Manager | roles-leadership/ | roles-business-development/ | Organizational/business focus |
| The Learner | roles/ | roles-self-development/ | Personal growth focus |

## Recovery: If Something Goes Wrong

```bash
# Find the commit before the move
git log --oneline -10

# Revert the commit
git revert <commit-hash>

# Or restore specific files
git checkout <commit-hash> -- "[path-to-restore]"
```
