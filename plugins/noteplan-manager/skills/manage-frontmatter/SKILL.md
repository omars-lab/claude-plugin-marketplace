---
name: manage-frontmatter
description: Validate and fix YAML frontmatter across all NotePlan note types using a parse → fix → re-validate roundtrip
---

# Manage Frontmatter

You are the frontmatter management skill for noteplan-manager. When invoked, detect the scope and route to the appropriate operation.

## Routing

| Signal | Operation | CLI |
|---|---|---|
| Single file with `--` delimiters (broken) | Quick-fix delimiters only | `noteplan-sweep fix-frontmatter-delimiters <file>` |
| "fix delimiters", "broken frontmatter", `--` in file | Quick-fix delimiters only | `noteplan-sweep fix-frontmatter-delimiters <file>` |
| Bulk fix, all files, validate across notes | Full roundtrip workflow | [fix-frontmatter/SKILL.md](fix-frontmatter/SKILL.md) |

### Single-file quick-fix

When the user points at one file with broken `--` delimiters (instead of `---`), run the CLI directly — no need to invoke the full sub-skill:

```bash
noteplan-sweep fix-frontmatter-delimiters "path/to/note.md"
# Then verify:
noteplan-sweep check-frontmatter "path/to/note.md"
```

Report the before/after delimiter change and whether `check-frontmatter` now passes.

### Full workflow

For bulk fixes or anything beyond delimiter repair, read [fix-frontmatter/SKILL.md](fix-frontmatter/SKILL.md) and follow its workflow.

## Task Management

Use `TaskCreate` and `TaskUpdate` to track progress as instructed in the sub-skill workflow.

## User Interaction

Use `AskUserQuestion` when the scope requires clarification — which note types or directories to process.

## What This Skill Does NOT Do

- Does not fix plan-specific structure (headers, self-ref todos) — use `/noteplan-manager:manage-plans`
- Does not fix template files' EJS inner blocks — only real note `---` frontmatter
