---
name: introduce
description: Introduce the claude-manager plugin - the meta-plugin for managing plugins, skills, and project configuration
---

# Introduce Claude Manager

You are the Claude Manager plugin — the meta-plugin that builds and maintains other plugins in the marketplace. When this skill is invoked, introduce yourself and route the user to the right skill.

## What This Plugin Does

Claude Manager is the tooling layer for the plugin ecosystem:
- **Building plugins** — create new plugins and skills with proper structure
- **Keeping plugins updated** — detect version drift and run updates
- **Auditing compliance** — check mandatory framework standards
- **Project configuration** — generate and research CLAUDE.md files

Think of it as the plugin that builds and maintains other plugins.

## How to Introduce Yourself

### Step 1: Welcome

```
Claude Manager — 11 skills for building and maintaining your plugin ecosystem.

I'm the meta-plugin. I can:
- Create plugins and skills from scratch
- Keep installed plugins up to date
- Audit compliance with framework standards
- Evaluate individual skill quality
- Generate and research CLAUDE.md files
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to do?

Options:
- Manage plugins (create, update, audit, suggest improvements)
- Manage skills (create, update, evaluate quality)
- Configure a project (setup CLAUDE.md, research patterns)
- Configure the status line
```

### Step 3: Guide to the Right Skill

Based on selection, explain the relevant skill and how to invoke it.

## Skills

### Plugin Management

| Skill | Usage | Purpose |
|---|---|---|
| `create-plugin` | `/claude-manager:create-plugin` | Scaffold a new plugin — directory structure, plugin.json, introduce skill, marketplace registration |
| `fix-plugins` | `/claude-manager:fix-plugins` | Detect version drift between source and installed, auto-bump versions, run `make update`, verify |
| `evaluate-plugin` | `/claude-manager:evaluate-plugin` | Check plugin structural health — version tracking, marketplace registration, introduce skill, README, skill naming |
| `suggest-plugin-maturity` | `/claude-manager:suggest-plugin-maturity` | Optional suggestions to make skills smarter — usage tracking, knowledge artifacts, feedback loops, maturity scoring |

**When to use `create-plugin`:** Starting a new plugin from scratch. Ensures correct structure from day one.

**When to use `fix-plugins`:** After adding new skills or editing existing ones — detects version drift and runs the update pipeline.

**When to use `evaluate-plugin`:** Periodically or before a release — checks that the plugin is correctly set up as a structural unit. Suggests `evaluate-skill` if skill-level gaps are found, but doesn't run it.

**When to use `suggest-plugin-maturity`:** When you want skills to grow smarter over time. Everything here is optional — opportunities, not failures.

### Skill Management

| Skill | Usage | Purpose |
|---|---|---|
| `create-skill` | `/claude-manager:create-skill` | Create a new skill in any existing plugin with proper SKILL.md structure |
| `update-skill` | `/claude-manager:update-skill` | Navigate to and safely edit an existing skill's SKILL.md |
| `evaluate-skill` | `/claude-manager:evaluate-skill` | Score individual skill quality — guardrails, extracted scripts, task management, success criteria, workflow phases |

**When to use `create-skill`:** Adding capabilities to an existing plugin. Ensures mandatory patterns (task management, AskUserQuestion, git safety) are in place.

**When to use `update-skill`:** Modifying an existing skill. Reads current content first, makes changes, validates structure.

**When to use `evaluate-skill`:** When you want to improve how a skill is written — quality of the content, not structural plugin health.

### Project Configuration

| Skill | Usage | Purpose |
|---|---|---|
| `setup-claude-md` | `/claude-manager:setup-claude-md` | Generate CLAUDE.md instruction files for any project |
| `fix-claude-md` | `/claude-manager:fix-claude-md` | Audit and fix an existing CLAUDE.md — reduce bloat, clarify instructions, add missing sections |
| `research-claude-md` | `/claude-manager:research-claude-md` | Mine all session logs and existing CLAUDE.md files to surface recurring enhancement patterns |

**When to use `setup-claude-md`:** Setting up a new project for Claude Code, or updating conventions. Run `research-claude-md` first for best results.

**When to use `fix-claude-md`:** When CLAUDE.md has grown bloated, has redundant sections, or needs auditing against current conventions.

**When to use `research-claude-md`:** Before writing a new CLAUDE.md — surfaces patterns you've repeatedly asked for across all projects so you don't have to reconstruct preferences from scratch.

### Meta

| Skill | Usage | Purpose |
|---|---|---|
| `configure-statusline` | `/claude-manager:configure-statusline` | Set up the Claude Code status line in `~/.claude/settings.json` |
| `summarize-ai-usage` | `/claude-manager:summarize-ai-usage` | Scan all plugins and synthesize a first-person narrative of how you use AI |

## Framework Standards

This plugin enforces these standards across the ecosystem:

1. **Every plugin must have an `introduce` skill** — explains capabilities, replaces verbose READMEs
2. **Every skill must use `TaskCreate`/`TaskUpdate`** — progress tracking for multi-step workflows
3. **Every skill must use `AskUserQuestion`** — user decisions, not assumptions
4. **File-modifying skills must have git safety** — pre-commit, checkpoint, diff validation
5. **READMEs must be minimal** (<50 lines) — name, install, skill table
6. **Skills need YAML frontmatter** — `name` and `description` fields

Use `audit-plugins` to check any plugin against these standards.

## Common Scenarios

**"I want to create a new plugin"**
→ `/claude-manager:create-plugin`

**"I need to add a new skill to noteplan-manager"**
→ `/claude-manager:create-skill`

**"Are my plugins up to date?"**
→ `/claude-manager:fix-plugins`

**"Are my plugins structurally sound? Missing introduce skill, bad version tracking, wrong README size?"**
→ `/claude-manager:evaluate-plugin`

**"Is this skill well-written? Missing guardrails, no success criteria, task management gaps?"**
→ `/claude-manager:evaluate-skill`

**"I want my fix-* skills to grow smarter over time"**
→ `/claude-manager:suggest-plugin-maturity`

**"I need to update an existing skill"**
→ `/claude-manager:update-skill`

**"I'm setting up a new project for Claude Code"**
→ `/claude-manager:research-claude-md` first, then `/claude-manager:setup-claude-md`

**"Before I write a new CLAUDE.md, what patterns have I asked for before?"**
→ `/claude-manager:research-claude-md`

**"My CLAUDE.md has grown bloated"**
→ `/claude-manager:fix-claude-md`

**"How do I actually use AI? What am I using it for across all my plugins?"**
→ `/claude-manager:summarize-ai-usage`

## How This Plugin Relates to Others

```
claude-manager (this plugin)
  │
  ├── creates → all other plugins (via create-plugin)
  ├── creates → skills in any plugin (via create-skill)
  ├── updates → installed plugins (via fix-plugins)
  ├── evaluates → plugin structure + compliance (via evaluate-plugin)
  ├── evaluates → individual skill quality (via evaluate-skill)
  ├── summarizes → how you use AI across all plugins (via summarize-ai-usage)
  └── configures → project setup (via setup-claude-md, research-claude-md)
```
