---
name: extract-skill
description: Extracts a specific skill from a personalbook role and creates it as a plugin skill in the marketplace. Updates the source role to reference the plugin skill. Use when a skill in a role should be shared via the plugin marketplace.
link: not
---

# Extracting a Skill to Plugin Marketplace

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Extract this skill to a plugin"
- "Move this skill to the marketplace"
- "Create a plugin skill from [skill-name]"
- "Share this skill via the plugin"
- Or using the slash command: `/role-manager:extract-skill`

## Purpose

This skill extracts a specific skill from a personalbook role and:
1. Creates the skill in an existing plugin (or creates a new plugin)
2. Updates the source role to reference the plugin skill instead
3. Optionally removes the local skill after verification

## Prerequisites

- Source skill exists in a role: `[role]/skills/[skill-name]/SKILL.md`
- Target plugin exists (or will be created)
- Plugin marketplace location: `/Users/omareid/workplace/git/oeid-claude-plugin-marketplace/plugins/`

## Workflow

### Phase 1: Identify Source and Destination

1. **Identify source skill**:
   ```
   Source: [role-path]/skills/[skill-name]/SKILL.md
   ```

2. **Identify target plugin**:
   - Use existing plugin: `[plugin-name]`
   - Or create new plugin (see `/role-manager:convert-role-to-plugin`)

3. **Get user confirmation**:
   - "I'll extract [skill-name] from [role] to [plugin]. Proceed?"

### Phase 2: Read and Validate Source Skill

```bash
# Read the source skill
cat "[role-path]/skills/[skill-name]/SKILL.md"

# Check for supporting files
ls -la "[role-path]/skills/[skill-name]/"

# Check if skill has guides or sub-skills
find "[role-path]/skills/[skill-name]/" -type f
```

**Validation checklist:**
- [ ] SKILL.md has frontmatter with `name`, `description`
- [ ] Name is kebab-case and slash-command compatible
- [ ] Skill is self-contained (no broken relative links)
- [ ] Any supporting files identified

### Phase 3: Create Skill in Plugin

1. **Create skill directory in plugin**:
   ```bash
   mkdir -p "[marketplace]/plugins/[plugin-name]/skills/[skill-name]"
   ```

2. **Copy SKILL.md** with any necessary path updates:
   - Update relative links if needed
   - Ensure frontmatter is correct
   - Add `extracted_from` metadata (optional)

3. **Copy supporting files** (guides, sub-skills, reference.md):
   ```bash
   # If skill has guides
   cp -r "[role-path]/skills/[skill-name]/guides" "[plugin-path]/skills/[skill-name]/"

   # If skill has sub-skills
   cp -r "[role-path]/skills/[skill-name]/sub-skills" "[plugin-path]/skills/[skill-name]/"
   ```

4. **Update introduce skill** if this is a new functional skill:
   - Add to the skills table in `[plugin]/skills/introduce/SKILL.md`

### Phase 4: Update Source Role

After extracting, update the source role to reference the plugin skill:

1. **Update role's Overview.md** skills table:

   **Before:**
   ```markdown
   | Skill | Essence | Invoke |
   |-------|---------|--------|
   | [skill-name](skills/skill-name/SKILL.md) | Description | `/skill-name` |
   ```

   **After:**
   ```markdown
   | Skill | Essence | Invoke |
   |-------|---------|--------|
   | skill-name | Description | `/[plugin-name]:skill-name` |
   ```

2. **Add extraction note** to role's Overview.md:
   ```markdown
   ## Extracted Skills

   The following skills have been extracted to plugins for broader use:

   | Skill | Plugin | Invoke |
   |-------|--------|--------|
   | skill-name | [plugin-name] | `/[plugin-name]:skill-name` |
   ```

3. **Update any internal references** in the role that point to the local skill

### Phase 5: Verify and Cleanup

1. **Verify skill works in plugin**:
   - Check skill appears in plugin validation
   - Test invocation if possible

2. **User decides on local skill**:

   **Option A: Keep local as reference**
   - Mark as deprecated with pointer to plugin:
   ```markdown
   ---
   status: deprecated
   extracted_to: [plugin-name]:skill-name
   extraction_date: [YYYY-MM-DD]
   ---

   # [Skill Name]

   **⚠️ This skill has been extracted to the [plugin-name] plugin.**

   Use: `/[plugin-name]:skill-name`
   ```

   **Option B: Remove local skill**
   ```bash
   git rm -r "[role-path]/skills/[skill-name]/"
   ```

### Phase 6: Commit Changes

```bash
# In plugin marketplace
cd [marketplace]
git add plugins/[plugin-name]/skills/[skill-name]/
git commit -m "Extract [skill-name] from [role] to [plugin-name]

Source: [role-path]/skills/[skill-name]/
Destination: plugins/[plugin-name]/skills/[skill-name]/

Invoke with: /[plugin-name]:skill-name"

# In personalbook (if removing local)
cd [personalbook]
git add -A
git commit -m "Update [role] to reference extracted skill

Skill [skill-name] extracted to [plugin-name] plugin
Invoke with: /[plugin-name]:skill-name"
```

## Example: Extracting a Skill

**Scenario**: Extract `reflecting-on-learnings` from The Self Reflector to role-manager plugin

### Before

```
personalbook/
└── roles-self-development/The Self Reflector/
    ├── Overview.md
    └── skills/
        └── reflecting-on-learnings/
            └── SKILL.md
```

### After

```
# Plugin marketplace
oeid-claude-plugin-marketplace/
└── plugins/role-manager/
    └── skills/
        └── reflecting-on-learnings/
            └── SKILL.md

# Personalbook (skill removed, reference added)
personalbook/
└── roles-self-development/The Self Reflector/
    └── Overview.md  # Updated with extraction note
```

**Updated Overview.md:**
```markdown
## Extracted Skills

| Skill | Plugin | Invoke |
|-------|--------|--------|
| reflecting-on-learnings | role-manager | `/role-manager:reflecting-on-learnings` |
```

## Extraction Checklist

- [ ] Source skill identified and validated
- [ ] Target plugin identified/exists
- [ ] Skill directory created in plugin
- [ ] SKILL.md copied with correct frontmatter
- [ ] Supporting files copied (guides, sub-skills)
- [ ] Plugin's introduce skill updated (if needed)
- [ ] Source role's Overview.md updated
- [ ] Internal references in role updated
- [ ] Local skill marked deprecated OR removed
- [ ] Changes committed to both repos

## When NOT to Extract

Don't extract a skill if:
- It's highly personal/role-specific (won't be useful elsewhere)
- It has many broken relative links that can't be fixed
- It's still in `ideating` or `establishing` status (not mature enough)
- The plugin would become too bloated

## Related Skills

- `/role-manager:convert-role-to-plugin` - Convert an entire role to a plugin
- `/role-manager:structure-role` - Structure a role before extraction
- `/claude-manager:skill-create` - Create a new skill from scratch
