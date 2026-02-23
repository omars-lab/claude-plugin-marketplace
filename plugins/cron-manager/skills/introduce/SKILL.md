---
name: introduce
description: Introduce the cron-manager plugin — automated background Claude Code tasks that run on terminal open, schedule-based, or event-based triggers
---

# cron-manager

`cron-manager` sets up automated background Claude Code sessions for recurring maintenance tasks — things you'd otherwise run manually every time.

## Skills

| Skill | What it does |
|---|---|
| `logging-note-diffs` | Sets up a background sync that fires on every new terminal open — commits NotePlan changes, pulls, pushes, and alerts on conflicts |

## How it works

Each skill in cron-manager provisions two things:
1. **A prompt file** — the instruction set for the background Claude session (lives in `~/.claude/`)
2. **A shell hook** — a function in `~/.zshrc` (or another shell config) that launches the session non-interactively in the background

Background sessions run with tightly scoped `--allowedTools` so they can only do what they need to — nothing more.

## Logs

All background jobs write to `~/Library/Logs/<job-name>.log`. View in Console.app or tail directly.

## Get started

```
/cron-manager:logging-note-diffs
```
