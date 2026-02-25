---
name: manage-filenames
description: Fix NotePlan filenames to match their H1 title headings, detect naming issues, and resolve conflicts
---

# Manage Filenames

You are the filename management skill for noteplan-manager. When invoked, read and follow the [fix-filenames/SKILL.md](fix-filenames/SKILL.md) workflow directly.

## What This Skill Does

Enforces the Golden Rule: the filename (minus `.md`) must match the `# Title` heading (minus `# `). Detects naming issues, fixes mismatches, and resolves conflicts.

Read [fix-filenames/SKILL.md](fix-filenames/SKILL.md) and follow its workflow.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress as instructed in the sub-skill workflow.

## User Interaction

Use `AskUserQuestion` when conflict resolution requires a user decision (e.g., multiple files with the same heading, ambiguous renames).

## What This Skill Does NOT Do

- Does not fix frontmatter — use `/noteplan-manager:manage-frontmatter`
- Does not fix emoji encoding — use `/noteplan-manager:manage-emojis`
