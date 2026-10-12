---
name: compact-prompt
description: Write a minimal handoff prompt that starts work in a fresh Claude Code session by carrying only the what (goal, scope, acceptance) and pointers to the skills, docs, and plan sections that hold the how. Use when someone asks for "a prompt for X", "a compact prompt", "a handoff brief", "summarize this task for a new session", "what should I paste into a fresh conversation", or wants to continue work without dragging the transcript along.
---

# Compact Prompt

Produce a prompt a person can paste into a fresh session to continue a task. The fresh session
is the point: it starts without the drift, dead ends, and half-remembered rules of the one that
is ending. So the prompt carries only what is specific to this task, and points at where
everything else already lives.

## Core principle

> Skills and docs carry the how. The prompt carries only the what.

Anything that would be true on the next ten tasks (workflow rules, test gates, commit
format, scope discipline, doc style) belongs in a skill, a CLAUDE.md, or a doc. If the
prompt restates it, the next session gets two sources that will drift apart. If the rule has
no home yet, the prompt says so and makes writing that home part of the task.

## Anatomy

These sections, in this order, and only when a section has something task-specific to say:

1. **Task**: one line, with the tracker id if there is one.
2. **Invoke**: the skills the next session must load, one per line as `/plugin:skill` or
   `/skill`. Nothing if no skill applies.
3. **Read**: files or plan sections to read for this task that the invoked skills do not
   already require. Each with a few words on why.
4. **Deliverables**: what to produce, as bullets, when not obvious from the task line.
5. **Out of scope**: adjacent work that looks tempting and is not this task.
6. **Notes**: gotchas that are genuinely task-specific and recorded nowhere else.
7. **Success criteria**: concrete and checkable. A command that must pass beats an adjective.
8. **Hand back**: what to report when done, if the person wants something specific.

Target length is 30 to 60 lines including code fences. Longer means skill content is being
duplicated, or the task should be split into several prompts.

## What never goes in

- Process rules that live in a CLAUDE.md or a skill (task tracking, test gates, commit style).
- Syntax or architecture recaps that live in a reference doc.
- Lessons already recorded in a lessons or decisions file.
- Transcript excerpts, tool output, or a narrative of how the ending session got here.
- Speculative warnings not grounded in a failure that actually happened.

When any of these shows up in a draft, replace it with a `/skill` or a `docs/<file>` pointer.

## Workflow

Track with `TaskCreate`: one task to gather the specifics, one to draft, one to self-check.

1. **Identify the work.** What kind of task is it, and which existing skills own that kind?
   List the repo's skills (`.claude/skills/`, installed plugins) and CLAUDE.md sections
   before writing, so pointers name things that exist.
2. **Pull the specifics.** Tracker entry (`TaskGet`), plan section, roadmap row, or the
   person's message. Extract the goal, the acceptance test, and the scope boundary.
3. **Check for a home.** For each rule you are tempted to include, find where it already
   lives. No home means either drop it or add "write it into <skill or doc>" as a
   deliverable.
4. **Draft** using the template. Lead with what the change means, then the technical names.
5. **Self-check.** Would the next session still have to ask "what about X" for any X a skill
   or doc covers? Then a pointer is missing. Does any line restate a skill? Then cut it.
6. **Confirm scope** with `AskUserQuestion` when the request could mean materially
   different tasks (a fix versus a redesign, one file versus the whole module). Offer the
   two or three readings with what each costs; do not ask whether to proceed.

## Template

````
Task: <one line, with tracker id if any>

Invoke:
/<plugin>:<skill>
/<skill>

Read:
- <path or plan section>: <why, in a few words>

Deliverables:
- <bullet>

Out of scope:
- <bullet>

Notes:
- <task-specific gotcha not recorded anywhere else>

Success criteria:
- <command that must pass, or an observable state>

Hand back: <what to report, if anything specific>
````

## Examples

A feature in a repo whose skills already carry the workflow:

````
Task: Add a `--since <date>` filter to the export command (tracker #42).

Invoke:
/dev-workflow
/regression-test

Read:
- src/export/cli.ts: the argument parser the flag joins
- docs/plan.md section "Export filters": the agreed semantics

Deliverables:
- Flag parsed, validated, and documented in the command's help text
- A unit test for an inclusive lower bound and one for a malformed date

Out of scope:
- An `--until` flag; separate tracker entry

Success criteria:
- `make test` green
- `export --since 2026-01-01` on the fixture returns only the three later rows
````

A task with no skill yet, where the prompt grows the skill library instead of inlining a
procedure:

````
Task: Cut the first tagged release of the core package.

No release skill exists beyond /publish. Draft .claude/skills/release/SKILL.md as part of
this work (tag convention, publish verification, changelog format), then run the release
through it.

Deliverables:
- .claude/skills/release/SKILL.md
- Tag created and pushed, package publish verified

Success criteria:
- The skill is reusable for the next release without edits
- A clean checkout installs the published version with the documented setup
````

## Rules

- Every prompt either uses an existing skill or names the skill it should create.
- Pointers name real files and sections; verify each one exists before handing the prompt
  over.
- The prompt is copy-pasteable as a single fenced block, with nothing the person has to fill
  in unless it is marked `<like this>`.
