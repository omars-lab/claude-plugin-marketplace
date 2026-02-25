---
name: manage-frontmatter
description: Validate and fix YAML frontmatter across all NotePlan note types using a parse → fix → re-validate roundtrip
---

# Manage Frontmatter

You are the frontmatter management skill for noteplan-manager. When invoked, read and follow the [fix-frontmatter/SKILL.md](fix-frontmatter/SKILL.md) workflow directly.

## What This Skill Does

Validates and fixes frontmatter across all note types (plans, meetings, questions, ideas, thoughts) using Python tooling with a parse → fix → re-validate roundtrip.

Read [fix-frontmatter/SKILL.md](fix-frontmatter/SKILL.md) and follow its workflow.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress as instructed in the sub-skill workflow.

## User Interaction

Use `AskUserQuestion` when the scope requires clarification — which note types or directories to process.

## What This Skill Does NOT Do

- Does not fix plan-specific structure (headers, self-ref todos) — use `/noteplan-manager:manage-plans`
- Does not fix template files' EJS inner blocks — only real note `---` frontmatter
