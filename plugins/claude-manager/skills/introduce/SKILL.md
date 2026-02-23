---
name: introduce
description: Introduce the claude-manager plugin - the meta-plugin for managing plugins, skills, and project configuration
---

# Introduce Claude Manager

You are the Claude Manager plugin - the meta-plugin that manages all other plugins in the marketplace. When this skill is invoked, introduce yourself and explain what you can do.

## What This Plugin Does

Claude Manager is the tooling layer for the plugin ecosystem. It handles:
- **Creating new plugins** with proper structure and framework compliance
- **Creating and updating skills** in any plugin
- **Auditing plugin health** and fixing compliance issues
- **Generating CLAUDE.md** project instruction files

Think of it as the plugin that builds and maintains other plugins.

## How to Introduce Yourself

### Step 1: Welcome

```
Claude Manager - 5 skills for building and maintaining your plugin ecosystem.

I'm the meta-plugin. I help you:
- Create new plugins from scratch (with proper structure)
- Add skills to existing plugins
- Audit plugins for framework compliance
- Generate CLAUDE.md files for projects
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:
```
What do you want to do?

- Create a new plugin (create-plugin)
- Add a skill to an existing plugin (skill-create)
- Audit and fix plugin issues (fix-plugins)
- Update an existing skill (skill-update)
- Generate a CLAUDE.md file (claude-md-setup)
```

### Step 3: Guide to the Right Skill

Based on selection, explain the relevant skill and how to invoke it.

## Skills

### Plugin Management

| Skill | Usage | Purpose |
|---|---|---|
| `create-plugin` | `/claude-manager:create-plugin` | Scaffold a new plugin with directory structure, plugin.json, introduce skill, first skill, and marketplace registration |
| `fix-plugins` | `/claude-manager:fix-plugins` | Audit both marketplaces for version issues, missing skills, compliance gaps, and auto-fix |

**When to use `create-plugin`:** Starting a new plugin from scratch. It ensures you get the structure right from day one - introduce skill, task management, AskUserQuestion, git safety.

**When to use `fix-plugins`:** After adding new skills, before releases, or periodically to check that all plugins follow framework standards. Detects missing introduce skills, skills without task management, bloated READMEs, version bump issues.

### Skill Management

| Skill | Usage | Purpose |
|---|---|---|
| `skill-create` | `/claude-manager:skill-create` | Create a new skill in any existing plugin with proper SKILL.md structure |
| `skill-update` | `/claude-manager:skill-update` | Navigate to and safely edit an existing skill's SKILL.md |

**When to use `skill-create`:** Adding capabilities to an existing plugin. Ensures the new skill follows mandatory patterns (task management, AskUserQuestion, git safety).

**When to use `skill-update`:** Modifying an existing skill. Reads the current content first, makes changes, validates structure.

### Project Configuration

| Skill | Usage | Purpose |
|---|---|---|
| `claude-md-setup` | `/claude-manager:claude-md-setup` | Generate CLAUDE.md instruction files for any project |
| `research-claude-md-usage` | `/claude-manager:research-claude-md-usage` | Mine all session logs and CLAUDE.md files to derive general enhancements |

**When to use `claude-md-setup`:** Setting up a new project for Claude Code, or updating an existing CLAUDE.md with new conventions.

**When to use `research-claude-md-usage`:** Before setting up or improving a CLAUDE.md — this skill surfaces patterns from your full history of instructions to Claude, so you don't have to reconstruct your preferences from scratch.

## Framework Standards

This plugin enforces these standards across the ecosystem:

1. **Every plugin must have an `introduce` skill** - explains capabilities, replaces verbose READMEs
2. **Every skill must use `TaskCreate`/`TaskUpdate`** - progress tracking for multi-step workflows
3. **Every skill must use `AskUserQuestion`** - user decisions, not assumptions
4. **File-modifying skills must have git safety** - pre-commit, checkpoint, diff validation
5. **READMEs must be minimal** (<50 lines) - name, install, skill table, requirements
6. **Skills need YAML frontmatter** - `name` and `description` fields

Use `fix-plugins` to audit any plugin against these standards.

## Common Scenarios

**"I want to create a new plugin"**
→ `/claude-manager:create-plugin`

**"I need to add a new skill to noteplan-manager"**
→ `/claude-manager:skill-create`

**"Are my plugins up to date and following standards?"**
→ `/claude-manager:fix-plugins`

**"I need to update an existing skill"**
→ `/claude-manager:skill-update`

**"I'm setting up a new project for Claude Code"**
→ `/claude-manager:claude-md-setup`

**"What patterns have I repeatedly asked Claude to follow across all my projects?"**
→ `/claude-manager:research-claude-md-usage`

**"Before I write a new CLAUDE.md, what have I asked for in the past?"**
→ `/claude-manager:research-claude-md-usage` first, then `/claude-manager:claude-md-setup`

## How This Plugin Relates to Others

```
claude-manager (this plugin)
  │
  ├── creates → all other plugins (via create-plugin)
  ├── creates → skills in any plugin (via skill-create)
  ├── audits → all plugins for compliance (via fix-plugins)
  └── configures → project setup (via claude-md-setup)

config-manager (sibling)
  │
  ├── manages → Claude permissions
  ├── manages → working directories
  ├── manages → Makefiles
  └── manages → documentation frameworks
```

claude-manager builds the plugin structure. config-manager configures the development environment.
