---
name: move-sessions
description: Move Claude Code session transcripts between project slug dirs in ~/.claude/projects — whole projects (after a repo moves on disk) or single sessions, with validation, cwd rewriting, and prompt-history migration
---

# Move Sessions

You are a session-migration assistant. Use the bundled script to relocate Claude Code session history when a project directory moves on disk, or when a single session belongs in a different project.

## Background

Claude Code stores sessions under `~/.claude/projects/<slug>/`, where the slug is the project's **absolute path with every non-alphanumeric character replaced by `-`** (e.g. `/Users/me/work/app` → `-Users-me-work-app`). The mapping is one-way: slugs cannot be reliably reversed (a `-` may have been `/`, `.`, `_`, or a literal dash). The true path is recoverable from the `cwd` field embedded in each transcript line.

Per project slug dir:

| Item | Purpose | Moves with session? |
|---|---|---|
| `<sessionId>.jsonl` | Transcript (images/pastes inline as base64) | yes — the script copies it |
| `<sessionId>/tool-results/` | Large tool outputs spilled to disk | yes — the script copies it |
| `sessions-index.json` | Resume-picker cache (absolute paths) | no — deleted; regenerated |
| `memory/` | Project memory | whole-project moves only |

Global, keyed by sessionId (work regardless of slug location — never moved): `file-history/<id>/`, `tasks/<id>/`, `session-env/<id>/`. Prompt history lives in `~/.claude/history.jsonl` keyed by project path (`--migrate-history` repoints it).

## Script

`scripts/move-claude-sessions.py` (also on PATH as `move-claude-sessions`).

```bash
# no args or --help — full help with examples and risk notes
move-claude-sessions

# dry run (default) — full plan + validation, writes nothing
move-claude-sessions OLD_PROJECT_PATH NEW_PROJECT_PATH

# execute whole-project move
move-claude-sessions OLD NEW --apply --migrate-history

# move one session between projects
move-claude-sessions OLD NEW --session <uuid> --apply

# also rewrite OLD->NEW path strings inside message content (re-parsed per
# line to guarantee valid JSON; skipped lines stay untouched)
move-claude-sessions OLD NEW --apply --rewrite-content

# remove source copies after verified copy
move-claude-sessions OLD NEW --apply --delete-source
```

Validations enforced before any write: source slug exists and contains the named sessions; no session is live (checks `~/.claude/sessions/*.json` locks against running pids); no sessionId collisions in the destination; src/dst slugs are not symlinks to the same physical dir; embedded `cwd` values sanity-checked against OLD (warns if already migrated). Top-level `cwd` rewriting is JSON-aware — never raw `sed`, which can corrupt inline base64 or historical content.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Dry-run move", description: "Run move-claude-sessions in dry-run mode and show plan", activeForm: "Dry-running move" })
TaskCreate({ subject: "Apply move", description: "Re-run with --apply after user confirms the plan", activeForm: "Applying move" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

## Your Workflow

1. Determine OLD and NEW project paths (and a session id if moving one session). If either path is ambiguous, use `AskUserQuestion` to confirm — e.g.:

```javascript
AskUserQuestion({
  questions: [{
    question: "Move the whole project's history or a single session?",
    header: "Scope",
    options: [
      { label: "Whole project", description: "All sessions + project memory move to the new slug dir" },
      { label: "Single session", description: "One transcript + its tool-results sidecar; memory and other sessions stay" }
    ],
    multiSelect: false
  }]
})
```

2. Run the dry run and show the user the plan, warnings, and errors verbatim.
3. Only after explicit confirmation, re-run with `--apply` (plus `--migrate-history` / `--delete-source` as agreed).
4. Verify: `claude --resume` discovery is by slug dir, so list the destination dir to confirm the files landed.

## Rules

- **Never move a live session.** The script blocks this; tell the user to close the session and re-run.
- Always show the user the dry run before `--apply`.
- Symlinked slug dirs (a legacy-path slug pointing at a new-path slug) are a valid alternative to moving files — check `ls -la ~/.claude/projects/ | grep '\->'` before assuming files need to move.
- `--delete-source` only after the user confirms the copy is good.
