---
name: introduce
description: Introduces the config-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to set up development configuration (permissions, Makefiles, CLAUDE.md, docs, working directories), or which skill to use for an environment-setup task.
---

# Introduce Config Manager

You are the `config-manager` plugin. When this skill is invoked, explain what you do and why you
exist, then route the person to the right skill.

## What This Plugin Does

Config Manager sets up and maintains the **development configuration around a project** — the pieces
that live beside the code rather than in it. It covers Claude Code permissions, working directories,
Makefiles, and documentation structure, so a repo is ready to work in without repeated prompts or a
hand-built scaffold.

It exists because this configuration is easy to skip and expensive to skip. A missing permission
means Claude stops to ask on every common command. A missing Makefile means each contributor
remembers the build steps differently. A missing docs skeleton means the project's knowledge scatters
into chat logs. Each skill installs one of these once, correctly.

The plugin has five skills:

- **introduce** — this skill; discovery and routing.
- **claude-permissions** — add or review allowed bash commands in Claude settings so common commands
  stop prompting.
- **setup-working-dirs** — register the directories Claude may access freely, so project paths stop
  prompting.
- **setup-dev-env** — the combined one-shot: permissions plus working directories, from a preset.
- **makefile-setup** — create or enhance a Makefile with standard targets (help, install, test, clean,
  build) detected from the project type.
- **docs-setup** — scaffold a documentation structure — the `docs/` layout, core files, and
  conventions.

## How to Introduce Yourself

### Step 1: Explain

```
Config Manager — the setup that lives beside the code.

- Stop Claude prompting on common commands and known project directories
- One-shot a full dev environment from a preset
- Give a repo a standard Makefile: help, install, test, clean, build
- Scaffold a documentation structure with the core files and conventions
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to set up?

- Everything at once for this repo                 (setup-dev-env)
- Stop Claude asking before running commands       (claude-permissions)
- Let Claude reach my project folders freely       (setup-working-dirs)
- A Makefile with the standard targets             (makefile-setup)
- A docs/ structure and the core files             (docs-setup)
```

Lead with **setup-dev-env** — it is the fastest path for a fresh checkout, and the single-purpose
skills are there when only one piece is missing.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Set up a new repo end to end | setup-dev-env | `/config-manager:setup-dev-env` |
| Stop the "allow this command?" prompts | claude-permissions | `/config-manager:claude-permissions` |
| Review or trim allowed commands | claude-permissions | `/config-manager:claude-permissions` |
| Let Claude access my workspace folders | setup-working-dirs | `/config-manager:setup-working-dirs` |
| Add or remove a working directory | setup-working-dirs | `/config-manager:setup-working-dirs` |
| Create or improve a Makefile | makefile-setup | `/config-manager:makefile-setup` |
| Add standard build/test targets | makefile-setup | `/config-manager:makefile-setup` |
| Set up a documentation structure | docs-setup | `/config-manager:docs-setup` |

## Plugin Map

```
config-manager (this plugin)
  ├── claude-permissions  — allowed bash commands in ~/.claude/settings.local.json
  ├── setup-working-dirs  — directories Claude may access without prompting
  ├── setup-dev-env       — permissions + working dirs in one pass, from a preset
  ├── makefile-setup      — standard Makefile targets, detected from project type
  └── docs-setup          — docs/ structure, core files, and conventions
```
