---
name: introduce
description: Introduce the task-management-manager plugin — its four config-driven task-tracking hooks and the .claude/hooks/task-management.conf schema that opts a repo in.
type: user-invocable
allowed-tools: Read, Glob
---

# task-management-manager

A **hook-only plugin** shipping a suite of four task-tracking hooks. Because Claude Code plugin
hooks fire uniformly wherever the plugin is enabled (there is no per-repo wiring), every hook here
is **config-driven**: it is a **no-op unless the repo declares
`.claude/hooks/task-management.conf`** and opts that hook in. This keeps the plugin safe to install
everywhere while each repo controls exactly what runs.

## The four hooks

| Hook | Event | Enable flag | What it does |
|---|---|---|---|
| `guard-task-deletion.py` | PreToolUse `TaskUpdate` | `ENABLE_GUARD_DELETION` | Blocks `status: deleted` until the task is recorded in a task file (exit 2). "Recorded" = an **id match first** — a `- [x]`/`- [ ]` bullet headed by `**#N**` / `**gtm-N**` / `**slug**`, taken from a leading id in `subject` or from `taskId` as `#N` — then the original fuzzy fallback (≥60% of the subject's >3-char tokens found in the corpus). An explicit subject id that is *not* in the ledger blocks outright; fuzzy never rescues it. Live Task-tool ids restart when the list is cleared, so a repo whose ledger assigns ids should lead the live task's subject with that id. |
| `check-task-files.py` | PostToolUse `Write\|Edit\|MultiEdit` | `ENABLE_CHECK_FILES` | Enforces the invariant: done file holds only `- [x]`, backlog only `- [ ]` (exit 2 on violation). Also `--check` CLI mode for `make`. |
| `remind-track-tasks.py` | UserPromptSubmit | `ENABLE_TRACK_NUDGE` | Emits a "track your work as tasks" nudge on work-like prompts (silent on questions). |
| `remind-task-sync.py` | Stop | `ENABLE_TASK_SYNC` | After a turn, flags task-file inconsistencies (open item in done, pending SHA, etc). Advisory. |

## Config schema (`.claude/hooks/task-management.conf`)

```
DONE_FILE=docs/tasks/done.md            # default
BACKLOG_FILE=docs/tasks/backlog.md      # default

ENABLE_GUARD_DELETION=1
ENABLE_CHECK_FILES=1
ENABLE_TRACK_NUDGE=0
ENABLE_TASK_SYNC=0

# high-value knobs (optional — defaults shown):
VERIFY_COMMAND=make tasks-check         # command suggested after fixing task files
DONE_MARKER=@done                       # completion marker used in messages/normalization
PENDING_MARKER=#git:pending             # "SHA not yet backfilled" marker
# TRACK_NUDGE_MESSAGE=<custom nudge text overriding the default>
```

- `KEY=value`, `#` comments and blank lines ignored; optional surrounding quotes tolerated.
- **Absent conf → all four hooks no-op.** So installing the plugin without a conf changes nothing.
- `guard` / `check` / `sync` additionally self-no-op when the declared task files don't exist;
  `track_nudge` is controlled purely by its flag.

## When to use / ask

- "What does the task-management hook suite do?" / "Why was my task deletion blocked?"
- "How do I turn on task tracking for this repo?" → add `.claude/hooks/task-management.conf` with the
  flags you want. (The `configure-repo` skill can write this for you interactively.)
- "Where do the task-file paths / markers come from?" → the conf; defaults are `docs/tasks/…`.
