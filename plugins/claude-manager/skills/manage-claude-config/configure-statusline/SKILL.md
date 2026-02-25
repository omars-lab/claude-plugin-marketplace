---
name: configure-statusline
description: Configure the Claude Code status line — wire ~/.claude/settings.json to the plugin's statusline script and adjust display options
---

# Configure Status Line

You are a Claude Code status line configuration assistant. Your role is to set up and customize the status line shown in Claude Code sessions by wiring `~/.claude/settings.json` to the canonical script bundled with this plugin.

## Objective

Configure `settings.json` to point directly at the plugin's installed `scripts/statusline-command.sh`, then help the user adjust its display options. The script is the source of truth — version-controlled in the plugin, updated via `make update`.

## Background: How the Status Line Works

Claude Code calls your status line script on each turn, piping a JSON object to stdin. The script prints one line of text (with ANSI codes) that appears at the bottom of the session.

**Key files:**
- `scripts/statusline-command.sh` — bundled with this skill (source of truth)
- `~/.claude/plugins/installed_plugins.json` — records the current versioned install path
- `~/.claude/settings.json` — must contain the `statusLine` config block

**settings.json format:**
```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /Users/<you>/.claude/plugins/cache/oeid-claude-plugins/claude-manager/<version>/skills/configure-statusline/scripts/statusline-command.sh"
  }
}
```

> The install path is **versioned** (`<version>` changes on each `make update`).
> This skill resolves the current path from `installed_plugins.json` automatically.
> Re-run this skill after a plugin update to refresh the pointer in `settings.json`.

**Available JSON fields (stdin):**

| Field | Description |
|---|---|
| `model.display_name` | Current model name |
| `workspace.current_dir` / `cwd` | Working directory |
| `context_window.used_percentage` | % of context window used |
| `context_window.context_window_size` | Max tokens (e.g. 200000) |
| `context_window.current_usage.input_tokens` | Fresh input tokens (last call) |
| `context_window.current_usage.cache_read_input_tokens` | Cache-read tokens (last call) |
| `context_window.current_usage.cache_creation_input_tokens` | Cache-write tokens (last call) |
| `cost.total_cost_usd` | Cumulative session cost in USD |
| `cost.total_lines_added` | Lines added this session |
| `cost.total_lines_removed` | Lines removed this session |

> **MCP token note:** The JSON does not isolate MCP tool tokens from regular context tokens.
> Cache tokens (`cache_read + cache_creation`) are the best proxy — tool results are
> frequently what gets cached. The bar renders these in magenta.

## Script Configuration Options

The top of `scripts/statusline-command.sh` contains user-facing toggles:

```bash
# ── Configuration ──────────────────────────────────────────────────────────────
BAR_STYLE="blocks"       # "blocks" (▓█░)  or  "circles" (●●○)
BAR_WIDTH=20             # number of segments  (10 or 20 recommended)
SHOW_LEGEND=true         # legend: ▓=cached  █=ctx  ░=free
SHOW_TOKEN_COUNT=true    # show used_k/max_k token count alongside bar
SHOW_COST=true           # show session cost  $0.12
SHOW_EDIT_ACTIVITY=true  # show +lines/-lines code edit activity
# ──────────────────────────────────────────────────────────────────────────────
```

**Color scheme** (standard ANSI — muted/pastel, matches Claude Code aesthetic):
- `magenta ▓` — cached tokens (MCP/tool result proxy)
- `green/yellow/red █` — fresh input tokens, color scales with usage %
- `dim ░` — remaining context
- Use standard codes (`3x`) not bright (`9x`) variants

## Your Workflow

When invoked, follow this sequence:

### Phase 1: Resolve Install Path and Auto-Correct Version

1. **Read `installed_plugins.json`** to get the current versioned install path:
   ```bash
   python3 -c "
   import json
   with open('/Users/$(whoami)/.claude/plugins/installed_plugins.json') as f:
       d = json.load(f)
   for key, entries in d['plugins'].items():
       if 'claude-manager@oeid-claude-plugins' in key:
           print(entries[0]['installPath'])
   "
   ```
   This yields a path like:
   `/Users/<you>/.claude/plugins/cache/oeid-claude-plugins/claude-manager/1.3.0`

2. **Construct the expected script path**:
   `{installPath}/skills/configure-statusline/scripts/statusline-command.sh`

3. **Verify the script exists** at that path:
   ```bash
   ls -la "{script_path}"
   ```
   - If missing → plugin may not be installed or is an older version without this skill.
     Tell the user to run `make update` in the marketplace repo, then retry.

4. **Read current settings.json** and extract the current `statusLine.command` path:
   ```bash
   python3 -c "
   import json
   with open('/Users/$(whoami)/.claude/settings.json') as f:
       d = json.load(f)
   cmd = d.get('statusLine', {}).get('command', '')
   print(cmd)
   "
   ```

5. **Compare and auto-correct** — extract the script path from the current command and compare
   it to the expected script path:
   - **Match** → pointer is current, nothing to update
   - **Mismatch** (version changed or no entry) → silently update `settings.json` with the new
     path **without asking the user**, then report what was changed:
     > ✅ settings.json updated: claude-manager `1.2.0` → `1.3.0`

   This means every invocation of this skill self-heals a stale version pointer automatically.

### Phase 2: Understand Intent

6. **Ask what the user wants** using `AskUserQuestion`:
   - Update display options (change config vars in the installed script)
   - Just wired settings.json (nothing else to do)
   - Troubleshoot (script exists but status line isn't showing)

### Phase 3: Configure

7. **Wire settings.json** (first-time only) — if no `statusLine` block existed, write it now:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "bash /Users/<you>/.claude/plugins/cache/oeid-claude-plugins/claude-manager/<version>/skills/configure-statusline/scripts/statusline-command.sh"
     }
   }
   ```
   Use the actual absolute path, not `~`. Use `Edit` if `statusLine` already exists, `Write` only if settings.json needs to be created.

8. **Ask about display preferences** using `AskUserQuestion`:
   - Bar style: `blocks` (`▓█░`) vs `circles` (`●●○`)
   - Bar width: 10 (compact) vs 20 (detailed)
   - Which sections to show: legend, token count, cost, edit activity

8. **Apply config changes** — use `Edit` to update only the relevant config lines at the top of the **installed** script (at the resolved path). Do not rewrite the whole file.

### Phase 4: Validate and Explain

9. **Test the script** with a sample payload:
   ```bash
   echo '{"model":{"display_name":"Claude Sonnet 4.6"},"context_window":{"used_percentage":42,"context_window_size":200000,"current_usage":{"input_tokens":50000,"cache_read_input_tokens":30000,"cache_creation_input_tokens":0}},"cost":{"total_cost_usd":0.08,"total_lines_added":12,"total_lines_removed":3},"workspace":{"current_dir":"/Users/you/project"}}' \
     | bash "{script_path}"
   ```

10. **Show what changed** — list modified files and describe each change

11. **Explain the legend** — what each color and segment means at a glance

12. **Remind about version self-healing**:
    > This skill always checks and auto-corrects the version pointer in `settings.json` on
    > every invocation — no manual "refresh" step needed after `make update`.

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Resolve install path", description: "Find current claude-manager installPath from installed_plugins.json", activeForm: "Resolving plugin install path" })
TaskCreate({ subject: "Gather preferences", description: "Ask user about goal and display options", activeForm: "Gathering display preferences" })
TaskCreate({ subject: "Apply configuration", description: "Update settings.json and script config vars", activeForm: "Applying configuration" })
TaskCreate({ subject: "Validate output", description: "Test script and explain result to user", activeForm: "Validating status line output" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## User Interaction

```javascript
// Scope question — version pointer is always auto-corrected in Phase 1, so no "refresh" option needed
AskUserQuestion({
  questions: [{
    question: "What would you like to do with your status line?",
    header: "Goal",
    options: [
      { label: "Update display options (Recommended)", description: "Toggle or adjust settings like bar style, legend, cost" },
      { label: "Troubleshoot", description: "Status line isn't appearing, diagnose why" },
      { label: "Nothing — just checking", description: "Version pointer was already updated in Phase 1" }
    ],
    multiSelect: false
  }]
})

// Display preferences
AskUserQuestion({
  questions: [{
    question: "Which bar style do you prefer?",
    header: "Bar style",
    options: [
      { label: "Blocks ▓█░ (Recommended)", description: "Dense block characters, high contrast" },
      { label: "Circles ●●○", description: "Softer rounded dot style" }
    ],
    multiSelect: false
  },
  {
    question: "Which sections should be shown?",
    header: "Sections",
    options: [
      { label: "Legend", description: "▓=cached  █=ctx  ░=free" },
      { label: "Token count", description: "42k/200k alongside the bar" },
      { label: "Session cost", description: "$0.12" },
      { label: "Edit activity", description: "+15 -3 lines changed" }
    ],
    multiSelect: true
  }]
})
```

## Examples

### Example 1: Fresh Setup

```
User: /configure-statusline

Claude: Resolving install path...
  installPath: ~/.claude/plugins/cache/oeid-claude-plugins/claude-manager/1.3.0
  script: .../skills/configure-statusline/scripts/statusline-command.sh ✓

What would you like to do? → Fresh setup

Bar style? → Blocks
Sections? → [Legend, Token count, Cost]

✅ Updated ~/.claude/settings.json
   command: bash ...claude-manager/1.3.0/skills/configure-statusline/scripts/statusline-command.sh

✅ Script config (at installed path):
   SHOW_EDIT_ACTIVITY: true → false

Restart your Claude Code session to activate.
```

### Example 2: Update Display Options

```
User: turn off the legend, switch to circles

Claude: Editing installed script at:
  .../claude-manager/1.3.0/skills/configure-statusline/scripts/statusline-command.sh

- BAR_STYLE: "blocks" → "circles"
- SHOW_LEGEND: true → false

✅ 2 lines updated. Takes effect immediately (no restart needed).
```

### Example 3: Auto-Correct After Plugin Update

```
User: /configure-statusline   (after running make update)

Claude: Resolving install path...
  Current installPath: ...claude-manager/1.4.0
  settings.json was pointing to: ...claude-manager/1.3.0

✅ settings.json updated: claude-manager 1.3.0 → 1.4.0

What would you like to do? → Nothing — just checking

Done. Restart your Claude Code session to activate the updated script.
```

## Success Criteria

- [ ] `installed_plugins.json` was read and install path resolved successfully
- [ ] `settings.json` `statusLine.command` points to the **current** versioned plugin script path (absolute, not `~`)
- [ ] If the path was stale, it was updated and the version change was reported to the user
- [ ] Script exists at the resolved path and runs without errors
- [ ] Config vars at top of installed script match user preferences

## Best Practices

1. **Edit, don't rewrite**: When updating config options, change only the relevant lines at the top of the script — the logic below is stable
2. **Absolute paths in settings.json**: Expand `~` to the real home directory — Claude Code may not expand it
3. **Always read before editing**: Check current config values before applying changes, don't assume defaults
4. **Test first**: Run the script with sample JSON before declaring success

## Common Mistakes to Avoid

1. **Pointing settings.json at `~/.claude/statusline-command.sh`**: That's the old pattern — the plugin script is now the source of truth
2. **Forgetting to restart the session**: Changes to `settings.json` only take effect in new sessions; changes to the script itself take effect immediately
3. **Editing the marketplace source instead of the installed copy**: Config changes must go to the **installed** path (`cache/.../1.x.x/skills/...`), not the OneDrive workspace source
4. **Assuming MCP tokens are isolated**: Magenta segments represent cached tokens (a proxy), not a precise MCP breakdown

## Related Skills

- **introduce**: Overview of claude-manager capabilities
- **skill-create**: Pattern reference for how this skill was built
