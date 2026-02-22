---
name: convert-role-to-plugin
description: Converts an entire personalbook role into a plugin in the marketplace. Creates plugin structure, moves skills and guides, and updates the role to reference the plugin. Use when a role's capabilities should be shared as a plugin.
link: not
---

# Converting a Role to a Plugin

## Triggering Criteria

Users can trigger this skill by saying things like:
- "Convert this role to a plugin"
- "Create a plugin from [role-name]"
- "Turn this role into a plugin"
- "Extract [role] as a plugin"
- Or using the slash command: `/role-manager:convert-role-to-plugin`

## Purpose

This skill converts an entire personalbook role into a plugin by:
1. Creating the plugin structure in the marketplace
2. Moving all skills, guides, and reusable content
3. Updating the source role to reference the plugin
4. Registering the plugin in marketplace.json

## Prerequisites

- Source role exists with skills worth extracting
- Plugin marketplace location: `/Users/omareid/workplace/git/oeid-claude-plugin-marketplace/plugins/`
- Role has been structured using `/role-manager:structure-role`

## What Gets Converted

| Role Component | Plugin Destination | Notes |
|----------------|-------------------|-------|
| **skills/** | `plugin/skills/` | All skills become plugin skills |
| **guides/** (under skills) | `plugin/skills/[skill]/guides/` | Guides stay with their skills |
| **knowledge/** (reusable) | `plugin/skills/[skill]/reference/` | Only if generic/reusable |
| **Role Overview** | `plugin/skills/introduce/SKILL.md` | Becomes the introduce skill |

## What Stays in Role

| Role Component | Reason |
|----------------|--------|
| **artifacts/** | Personal content, not shareable |
| **habits/** | Personal practices, stay in role |
| **decisions/** | Personal choices, stay in role |
| **expectations/** | Role-specific standards |
| **Responsibilities.md** | Role-specific definition |

## Workflow

### Phase 1: Analyze Role

1. **Read the role structure**:
   ```bash
   find "[role-path]/" -type f -name "*.md" | head -30
   ```

2. **Identify extractable content**:
   - Skills that are reusable
   - Guides that are generic
   - Knowledge that's reference material

3. **Determine plugin name**:
   - Convention: `[domain]-manager` (e.g., `role-manager`, `note-manager`)
   - Must be unique in marketplace

4. **Get user confirmation**:
   - Show what will be extracted vs what stays
   - Confirm plugin name

### Phase 2: Create Plugin Structure

1. **Create plugin directory**:
   ```bash
   mkdir -p "[marketplace]/plugins/[plugin-name]/.claude-plugin"
   mkdir -p "[marketplace]/plugins/[plugin-name]/skills/introduce"
   ```

2. **Create plugin.json**:
   ```json
   {
     "name": "[plugin-name]",
     "description": "[Description from role Overview]",
     "version": "1.0.0",
     "author": {
       "name": "Omar Eid"
     },
     "license": "MIT"
   }
   ```

3. **Create version-tracking.json**:
   ```json
   {
     "versionCommit": "[current-git-commit]"
   }
   ```

4. **Create README.md**:
   ```markdown
   # [plugin-name]

   [Brief description]

   Use `/[plugin-name]:introduce` to learn about available skills.
   ```

### Phase 3: Create Introduce Skill

Create `skills/introduce/SKILL.md` based on role Overview:

```markdown
---
name: introduce
description: Explains [plugin-name] capabilities and guides users to the right skill
---

# [Plugin Name]

[Description from role]

## What This Plugin Does

[Extracted from role Overview]

## Available Skills

| Skill | When to Use | Invoke |
|-------|-------------|--------|
| **[skill-1]** | [Description] | `/[plugin-name]:[skill-1]` |
| **[skill-2]** | [Description] | `/[plugin-name]:[skill-2]` |

## Quick Decision Guide

**"[User intent 1]"**
→ Use `/[plugin-name]:[skill-1]`

**"[User intent 2]"**
→ Use `/[plugin-name]:[skill-2]`
```

### Phase 4: Move Skills

For each skill in the role:

1. **Create skill directory**:
   ```bash
   mkdir -p "[plugin-path]/skills/[skill-name]"
   ```

2. **Copy SKILL.md**:
   - Update frontmatter if needed
   - Fix any relative paths

3. **Copy supporting files**:
   ```bash
   # Guides
   cp -r "[role]/skills/[skill]/guides" "[plugin]/skills/[skill]/"

   # Sub-skills
   cp -r "[role]/skills/[skill]/sub-skills" "[plugin]/skills/[skill]/"
   ```

### Phase 5: Register Plugin

Add to `[marketplace]/.claude-plugin/marketplace.json`:

```json
{
  "name": "[plugin-name]",
  "source": "./plugins/[plugin-name]",
  "description": "[Description]",
  "version": "1.0.0",
  "category": "[category]",
  "keywords": ["[keyword1]", "[keyword2]"]
}
```

### Phase 6: Update Source Role

1. **Update Overview.md** with extraction notice:
   ```markdown
   ## Plugin Extraction

   This role's skills have been extracted to the **[plugin-name]** plugin.

   ### Using the Plugin

   Install: `/plugin install [plugin-name]@oeid-claude-plugins`

   Introduce: `/[plugin-name]:introduce`

   ### Available Skills

   | Skill | Invoke |
   |-------|--------|
   | [skill-1] | `/[plugin-name]:[skill-1]` |
   | [skill-2] | `/[plugin-name]:[skill-2]` |
   ```

2. **Decide on local skills**:

   **Option A: Remove local skills** (recommended)
   ```bash
   git rm -r "[role]/skills/"
   ```

   **Option B: Keep as deprecated reference**
   - Mark each skill with `status: deprecated`
   - Add pointer to plugin skill

### Phase 7: Validate and Install

1. **Validate plugin**:
   ```bash
   cd [marketplace]
   make validate-plugins
   ```

2. **Install plugin**:
   ```bash
   make install
   # Or: claude plugin install [plugin-name]@oeid-claude-plugins
   ```

3. **Test plugin**:
   - Try `/[plugin-name]:introduce`
   - Try one of the functional skills

### Phase 8: Commit Changes

```bash
# Plugin marketplace
cd [marketplace]
git add plugins/[plugin-name]/
git add .claude-plugin/marketplace.json
git commit -m "Create [plugin-name] plugin from [role-name]

Skills extracted:
- [skill-1]
- [skill-2]
- [skill-3]

Source role: [role-path]"

# Personalbook
cd [personalbook]
git add -A
git commit -m "Update [role-name] after plugin extraction

Skills moved to [plugin-name] plugin.
Install: /plugin install [plugin-name]@oeid-claude-plugins
Introduce: /[plugin-name]:introduce"
```

## Example: Converting a Role

**Scenario**: Convert "The Manager" role to "management-manager" plugin

### Source Role Structure
```
roles-business-development/The Manager/
├── Overview.md
├── Responsibilities.md
├── skills/
│   ├── prioritizing/SKILL.md
│   ├── delegating/SKILL.md
│   └── holding-retrospectives/SKILL.md
├── habits/
│   └── weekly-review/HABIT.md
├── artifacts/
│   └── priorities.md
└── knowledge/
    └── prioritization-frameworks.md
```

### Resulting Plugin
```
plugins/management-manager/
├── .claude-plugin/
│   ├── plugin.json
│   └── version-tracking.json
├── README.md
└── skills/
    ├── introduce/SKILL.md
    ├── prioritizing/SKILL.md
    ├── delegating/SKILL.md
    └── holding-retrospectives/SKILL.md
```

### What Stays in Role
```
roles-business-development/The Manager/
├── Overview.md  # Updated with plugin reference
├── Responsibilities.md
├── habits/
│   └── weekly-review/HABIT.md
├── artifacts/
│   └── priorities.md
└── knowledge/
    └── prioritization-frameworks.md
```

## Conversion Checklist

### Pre-Conversion
- [ ] Role has been structured with `/role-manager:structure-role`
- [ ] Skills are mature (not `ideating` status)
- [ ] Plugin name determined and unique
- [ ] User approved conversion plan

### Plugin Creation
- [ ] Plugin directory created
- [ ] plugin.json created with correct metadata
- [ ] version-tracking.json created
- [ ] README.md created
- [ ] introduce skill created from Overview

### Skill Migration
- [ ] All skills copied to plugin
- [ ] Supporting files (guides, sub-skills) copied
- [ ] Frontmatter validated in each skill
- [ ] Relative paths fixed

### Registration
- [ ] Plugin added to marketplace.json
- [ ] Plugin validates with `make validate-plugins`

### Source Role Update
- [ ] Overview.md updated with plugin reference
- [ ] Local skills removed or deprecated
- [ ] Role still usable for habits/artifacts/decisions

### Final Steps
- [ ] Plugin installed with `make install`
- [ ] Plugin skills testable
- [ ] Changes committed to both repos

## When NOT to Convert

Don't convert a role to a plugin if:
- The role has few or no reusable skills
- Skills are still in development (ideating/establishing)
- The role is highly personal with no reuse value
- A similar plugin already exists (consider contributing to it instead)

## Related Skills

- `/role-manager:extract-skill` - Extract a single skill instead of full role
- `/role-manager:structure-role` - Structure role before conversion
- `/claude-manager:create-plugin` - Create a plugin from scratch
