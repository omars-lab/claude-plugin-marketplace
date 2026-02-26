---
name: manage-docs
description: Audit, consolidate, and improve repository documentation — reduce overwhelm, eliminate redundancy, enforce clear organization, generate diagrams and runbooks
---

# Manage Docs

You are the documentation management skill for code-quality-manager. When invoked, read and follow the [improve-docs/SKILL.md](improve-docs/SKILL.md) workflow directly.

## What This Skill Does

Runs a 6-task workflow that addresses the three documentation failure modes — overwhelming, redundant, disorganized:

1. Git baseline — checkpoint for safe rollback
2. Audit docs — inventory every `.md` file, evaluate against quality checklists
3. Present findings — show what's wrong, get user approval
4. Consolidate — move, merge, split, and trim files
5. Generate content — add Mermaid diagrams and runbooks where they add value
6. CLAUDE.md audit — optimize project instructions, validate all changes

Read [improve-docs/SKILL.md](improve-docs/SKILL.md) and follow its workflow.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress across the 6-task workflow.

## User Interaction

Use `AskUserQuestion` at Tasks 3, 5, and 6 before making any changes — the sub-skill workflow specifies when.

## What This Skill Does NOT Do

- Does not generate Makefiles — use `/code-quality-manager:manage-makefiles`
- Does not analyze code changes for gaps — use `/code-quality-manager:poke-holes`
- Does not modify source code files, only documentation
