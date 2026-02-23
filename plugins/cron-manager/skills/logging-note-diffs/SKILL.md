---
name: logging-note-diffs
description: Set up a background Claude Code session that fires on every new terminal open — automatically commits NotePlan changes, pulls, pushes, and alerts on merge conflicts via macOS notification
---

# Logging Note Diffs

Sets up an automated background Claude Code session that runs silently every time a new terminal opens. It checks the NotePlan notes git repo for uncommitted changes, commits them with a generated message, pulls, and pushes. If there are merge conflicts it fires a macOS notification and stops — it never blocks your terminal.

## What gets set up

| Artifact | Path | Purpose |
|---|---|---|
| Prompt file | `~/.claude/noteplan-sync-prompt.md` | The instruction set Claude runs in background |
| .zshrc hook | `~/.zshrc` (idempotent block) | Launches the background session on terminal open |
| Log | `~/Library/Logs/noteplan-sync.log` | Output from every sync run |

## Permissions (allowedTools)

The background session is locked down to only what it needs:

| Tool | Why |
|---|---|
| `Bash(git *)` | All git operations via `git -C <path>` (status, add, commit, pull, push, diff) |
| `Bash(osascript *)` | macOS notification for conflicts or errors |
| `Read` | Read files when needed |

All other tools are denied. The session cannot edit files, write to the repo, or run arbitrary commands.

---

## Workflow

### Step 0: Task Setup (MANDATORY FIRST STEP)

```javascript
TaskCreate({ subject: "Explain and confirm setup", activeForm: "Explaining setup" })
TaskCreate({ subject: "Create prompt file", activeForm: "Creating prompt file" })
TaskCreate({ subject: "Update .zshrc (idempotent)", activeForm: "Updating .zshrc" })
TaskCreate({ subject: "Test the sync", activeForm: "Testing sync" })
TaskCreate({ subject: "Verify and summarise", activeForm: "Verifying setup" })

TaskUpdate({ taskId: "1", addBlockedBy: [] })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
TaskUpdate({ taskId: "5", addBlockedBy: ["4"] })
```

### Phase 1: Explain & Confirm

Mark Task #1 `in_progress`.

Summarise what will happen:
```
This skill will:
1. Create ~/.claude/noteplan-sync-prompt.md  — the prompt Claude runs in background
2. Add a function + call to ~/.zshrc          — fires the sync on every new terminal
3. Log output to ~/Library/Logs/noteplan-sync.log

The background session can only run git commands and send macOS notifications.
It will NOT modify files, edit notes, or run arbitrary commands.
```

Use `AskUserQuestion` to confirm:
- "Ready to set up automated NotePlan sync?" with options: "Yes, set it up" / "Show me what the .zshrc change looks like first"

If "Show me first": display the full zshrc snippet below before proceeding. Then ask again.

Mark Task #1 `completed`.

### Phase 2: Create Prompt File

Mark Task #2 `in_progress`.

Write `~/.claude/noteplan-sync-prompt.md` with this exact content:

```markdown
You are a background NotePlan git sync agent. Run silently and efficiently. Do not ask for input — ever.

NOTEPLAN_DIR="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes"

Steps:
1. Check for changes: git -C "$NOTEPLAN_DIR" status --porcelain
2. If output is empty: print "no changes" and stop.
3. If changes exist:
   a. Understand what changed: git -C "$NOTEPLAN_DIR" diff --stat
   b. Stage all: git -C "$NOTEPLAN_DIR" add -A
   c. Compose a commit message:
      - Start with "chore(noteplan): "
      - Summarise what changed (e.g. "update 3 calendar entries, add work plan")
      - Add footer: Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
   d. Commit: git -C "$NOTEPLAN_DIR" commit -m "your message"
   e. Pull: git -C "$NOTEPLAN_DIR" pull --rebase
   f. Check pull output and git -C "$NOTEPLAN_DIR" status for CONFLICT markers
   g. No conflicts → git -C "$NOTEPLAN_DIR" push
   h. Conflicts → run:
      osascript -e 'display notification "Merge conflict in NotePlan — resolve manually then push" with title "NotePlan Sync ⚠️" sound name "Basso"'
      Then stop. Do NOT push.

Non-blocking failure rule:
If at any point you cannot proceed (permission denied, missing tool, unexpected state, unclear situation):
- Do NOT wait or ask for input.
- Immediately run: osascript -e 'display notification "<brief reason>" with title "NotePlan Sync — Needs Attention" sound name "Basso"'
- Then exit.
```

Mark Task #2 `completed`.

### Phase 3: Update .zshrc (Idempotent)

Mark Task #3 `in_progress`.

**Check for existing block:**
```bash
grep -c "BEGIN noteplan-sync" ~/.zshrc 2>/dev/null || echo "0"
```

**If 0 (not present):** append the block to `~/.zshrc`.
**If 1 (present):** replace the content between `# BEGIN noteplan-sync` and `# END noteplan-sync` markers using Edit tool (old_string = entire existing block, new_string = updated block).

**The block to write:**

```bash
# BEGIN noteplan-sync
_noteplan_sync() {
  local lockfile="/tmp/noteplan-sync.lock"
  local logfile="$HOME/Library/Logs/noteplan-sync.log"
  local promptfile="$HOME/.claude/noteplan-sync-prompt.md"

  # Abort if prompt file not set up
  [[ ! -f "$promptfile" ]] && return 0

  # Abort if a sync is already running
  if [[ -f "$lockfile" ]]; then
    local pid; pid=$(cat "$lockfile" 2>/dev/null)
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && return 0
    rm -f "$lockfile"
  fi

  mkdir -p "$(dirname "$logfile")"
  (
    echo $$ > "$lockfile"
    env -u CLAUDECODE claude \
      --print "$(cat "$promptfile")" \
      --allowedTools "Bash(git *),Bash(osascript *),Read" \
      --model claude-haiku-4-5-20251001 \
      --output-format text \
      >> "$logfile" 2>&1
    rm -f "$lockfile"
  ) &!
}
_noteplan_sync
# END noteplan-sync
```

**Notes on the snippet:**
- `&!` — zsh background + disown (process survives after terminal closes)
- `env -u CLAUDECODE` — strips the `CLAUDECODE` env var to prevent "nested session" errors
- Lockfile guards against duplicate runs if multiple terminals open quickly
- The prompt file guard means disabling sync is as simple as deleting `~/.claude/noteplan-sync-prompt.md`

Mark Task #3 `completed`.

### Phase 4: Test

Mark Task #4 `in_progress`.

Source the updated .zshrc and fire one sync:
```bash
source ~/.zshrc
sleep 5 && tail -20 ~/Library/Logs/noteplan-sync.log
```

Show the log output to the user. If the log shows "no changes" or a commit — success. If it shows an error, diagnose and fix before proceeding.

Mark Task #4 `completed`.

### Phase 5: Verify & Summary

Mark Task #5 `in_progress`.

```bash
grep -c "BEGIN noteplan-sync" ~/.zshrc  # should print 1
ls -la ~/Library/Logs/noteplan-sync.log  # should exist
```

Show summary:
```
✅ NotePlan auto-sync is set up.

Every new terminal will trigger a background sync.

Log:    ~/Library/Logs/noteplan-sync.log
        tail ~/Library/Logs/noteplan-sync.log

Disable: delete ~/.claude/noteplan-sync-prompt.md
         or comment out _noteplan_sync in ~/.zshrc

Conflicts: you'll get a macOS notification — resolve manually, then push.
```

Mark Task #5 `completed`. Show `TaskList()`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| No log file appearing | Check `which claude` — claude must be in PATH when .zshrc runs |
| "nested session" error in log | `env -u CLAUDECODE` should prevent this; verify it's in the snippet |
| Multiple syncs running | Stale lockfile — `rm /tmp/noteplan-sync.lock` |
| Sync fires but does nothing | Check that `~/.claude/noteplan-sync-prompt.md` exists |
| Want to disable temporarily | `mv ~/.claude/noteplan-sync-prompt.md ~/.claude/noteplan-sync-prompt.md.disabled` |
| Want to remove entirely | Delete prompt file + remove the BEGIN/END block from ~/.zshrc |
