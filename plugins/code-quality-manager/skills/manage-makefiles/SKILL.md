---
name: manage-makefiles
description: Generate or enhance Makefiles following CEG standards — actionable output, consistent naming, clear status indicators
---

# Manage Makefiles

You are the Makefile management skill for code-quality-manager. When invoked, read and follow the [generate-makefile/SKILL.md](generate-makefile/SKILL.md) workflow directly.

## What This Skill Does

Analyzes the repository and generates or enhances a Makefile following CEG standards:
- **Actionability** — copy-paste ready commands, status indicators (✓/✗/⚠️)
- **Consistency** — standard naming (`test-X`, `install-X`), uniform output format
- **Simplicity** — one target = one action, fail fast with helpful errors

Read [generate-makefile/SKILL.md](generate-makefile/SKILL.md) and follow its workflow.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress as instructed in the sub-skill workflow.

## User Interaction

Use `AskUserQuestion` when the user's intent is ambiguous — generate from scratch vs. enhance an existing Makefile.

## What This Skill Does NOT Do

- Does not improve documentation — use `/code-quality-manager:manage-docs`
- Does not analyze code changes for gaps — use `/code-quality-manager:poke-holes`
