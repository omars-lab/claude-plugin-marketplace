---
name: setup-chrome-integration
description: Configure Chrome for Testing auto-start with remote debugging, isolate chrome-devtools MCP to an opt-in alias, and write a managed tagged block to ~/.zshrc
---

# Setup Chrome Integration

You are a shell profile integration assistant. Your role is to configure Chrome for Testing for Claude Code's chrome-devtools MCP server — auto-starting it with `--remote-debugging-port=9222`, isolating the MCP so it only activates via an opt-in `claude-with-chrome` alias, and writing all of this as a tagged, idempotent block in `~/.zshrc`.

## Objective

By the end of this skill:
- Chrome for Testing starts **on demand** when `claude-with-chrome` is invoked (not on every shell open)
- stdout/stderr are routed to `~/Library/Logs/profile-manager/chrome-for-testing.log` (viewable in Console.app)
- The chrome-devtools MCP server is **disabled by default** in all Claude config files
- A `claude-with-chrome` alias starts Chrome if needed, then launches Claude with browser tools
- The alias always resolves the **latest installed version** of the plugin's MCP config
- All zshrc changes are in a clearly tagged block maintainable by this skill
- Re-running the skill replaces the block idempotently (no duplicates)

## MCP Config Location

The chrome-devtools MCP config ships **inside this skill** at:

```
skills/setup-chrome-integration/mcp-chrome.json
```

After `make install` or `make update`, it lives at:

```
~/.claude/plugins/cache/oeid-claude-plugins/profile-manager/<version>/skills/setup-chrome-integration/mcp-chrome.json
```

The `.zshrc` block includes a `_pfm_chrome_mcp_config()` function that resolves the latest installed version at invocation time — so upgrading the plugin automatically picks up config changes without re-running this skill.

There is **no** `~/.claude/mcp-chrome.json`. If one exists from a previous install, inform the user it can be deleted.

## Task Management (MANDATORY)

Create all tasks upfront before starting:

```javascript
TaskCreate({ subject: "Audit prerequisites", description: "Check Chrome for Testing install, port availability, settings.json chrome-devtools entry", activeForm: "Auditing prerequisites" })
TaskCreate({ subject: "Isolate chrome-devtools MCP", description: "Ensure chrome-devtools is absent from settings.json default config", activeForm: "Isolating MCP config" })
TaskCreate({ subject: "Write .zshrc block", description: "Write the tagged profile-manager block to ~/.zshrc (replace existing if present)", activeForm: "Writing .zshrc block" })
TaskCreate({ subject: "Verify integration", description: "Source .zshrc, confirm Chrome starts, confirm curl reaches debug port, confirm alias exists", activeForm: "Verifying integration" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1 — Audit Prerequisites

**1. Check Chrome for Testing installation**

```bash
ls "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
```

If missing, present install options to the user:

| Method | Command | Notes |
|---|---|---|
| npx (recommended) | `npx @puppeteer/browsers install chrome@stable` | Requires Node.js; installs versioned binary |
| Manual | Download from [googlechromelabs.github.io/chrome-for-testing](https://googlechromelabs.github.io/chrome-for-testing/) | Pick Stable channel, macOS arm64 or x64 |

> **Why Chrome for Testing?** Regular Chrome auto-updates, which breaks automation. Chrome for Testing is a dedicated variant with no auto-update, designed specifically for this use case. It is also exempt from the Chrome 136+ `--remote-debugging-port` restriction that requires `--user-data-dir` — regular Chrome now requires a non-default user data directory for remote debugging, but Chrome for Testing does not.

**2. Check port 9222 availability**

```bash
lsof -nP -iTCP:9222 -sTCP:LISTEN
```

If port is in use by something other than Chrome for Testing, report the conflict to the user.

**3. Check current chrome-devtools MCP config**

Claude Code reads MCP servers from **two** user-scope config files — check both:

```bash
# Primary (newer)
~/.claude/settings.json

# Legacy (also active — often missed)
~/.claude.json
```

Check both for a `mcpServers.chrome-devtools` entry. Either or both may need to be cleaned in Phase 2.

Also check whether `~/.claude/mcp-chrome.json` exists from a previous install. If so, inform the user it is no longer needed and offer to delete it.

### Phase 2 — Isolate chrome-devtools MCP

**Goal:** chrome-devtools MCP should NOT load by default when running plain `claude`. It should ONLY load when running `claude-with-chrome`.

The MCP config is bundled in this plugin (`skills/setup-chrome-integration/mcp-chrome.json`) — no file needs to be written to `~/.claude/`. This phase only ensures `settings.json` is clean.

**4. Remove chrome-devtools from both config files (if present)**

Check and clean both files. Use `AskUserQuestion` to confirm before modifying either.

```python
import json, pathlib

for name in ['.claude/settings.json', '.claude.json']:
    path = pathlib.Path.home() / name
    if not path.exists():
        continue
    s = json.loads(path.read_text())
    removed = s.get('mcpServers', {}).pop('chrome-devtools', None)
    if removed:
        path.write_text(json.dumps(s, indent=2) + '\n')
        print(f"Removed from {name}")
```

If no entry exists in either file, nothing to do — confirm and proceed.

**5. Verify isolation**

Confirm `~/.claude/settings.json` no longer contains `chrome-devtools` under `mcpServers`.

### Phase 3 — Write .zshrc Block

**6. Check for existing managed block**

```bash
grep -n "profile-manager:setup-chrome-integration" ~/.zshrc
```

If found: the block will be replaced (not appended). If not found: it will be appended.

**7. Show the user a preview of the block before writing**

Use `AskUserQuestion` to confirm. Show the exact block:

```zsh
# >>> profile-manager:setup-chrome-integration >>>
# Managed by profile-manager via setup-chrome-integration skill.
# Re-run /profile-manager:setup-chrome-integration to update this block.

CHROME_FOR_TESTING_BIN="/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
CHROME_DEBUG_PORT=9222
CHROME_LOG_DIR="${HOME}/Library/Logs/profile-manager"
CHROME_LOG_FILE="${CHROME_LOG_DIR}/chrome-for-testing.log"

# Start Chrome for Testing with remote debugging (no-op if already running)
_pfm_start_chrome() {
  if ! pgrep -f "Google Chrome for Testing.*--remote-debugging-port" > /dev/null 2>&1; then
    if [[ -x "${CHROME_FOR_TESTING_BIN}" ]]; then
      mkdir -p "${CHROME_LOG_DIR}"
      "${CHROME_FOR_TESTING_BIN}" --remote-debugging-port=${CHROME_DEBUG_PORT} \
        >> "${CHROME_LOG_FILE}" 2>&1 &!
    fi
  fi
}

# Resolve latest installed profile-manager plugin's mcp-chrome.json
_pfm_chrome_mcp_config() {
  local base="${HOME}/.claude/plugins/cache/oeid-claude-plugins/profile-manager"
  local latest_version
  latest_version=$(ls "${base}" 2>/dev/null \
    | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -t. -k1,1n -k2,2n -k3,3n \
    | tail -1)
  echo "${base}/${latest_version}/skills/setup-chrome-integration/mcp-chrome.json"
}

# claude-with-chrome: starts Chrome on demand then launches Claude with browser tools
alias claude-with-chrome='_pfm_start_chrome && claude --mcp-config "$(_pfm_chrome_mcp_config)"'
# <<< profile-manager:setup-chrome-integration <<<
```

Key design choices to explain to the user:
- **`&!`** — zsh background + disown; process survives after the terminal closes (preferred over `& disown` in zsh)
- **`pgrep` check** — prevents spawning duplicate Chrome instances across multiple `claude-with-chrome` invocations
- **`_pfm_` prefix** — avoids namespace collisions with other shell functions
- **`~/Library/Logs/profile-manager/`** — macOS standard log location; visible in Console.app under `~/Library/Logs`
- **`--mcp-config`** — Claude Code flag to load an additional MCP config file (merges with default, does NOT replace it)
- **`_pfm_chrome_mcp_config()`** — resolves the latest installed plugin version at invocation time; upgrading the plugin automatically picks up config changes
- **No auto-start at shell open** — Chrome starts on demand when `claude-with-chrome` is invoked, not on every new terminal

**8. Write the block**

If replacing: use a Python one-liner to swap the old block (between the `>>>` and `<<<` markers) with the new one — this is safer than sed for multi-line replacement:

```python
import re, pathlib

path = pathlib.Path.home() / '.zshrc'
content = path.read_text()
new_block = """<the block above>"""

pattern = r'# >>> profile-manager:setup-chrome-integration >>>.*?# <<< profile-manager:setup-chrome-integration <<<'
if re.search(pattern, content, re.DOTALL):
    updated = re.sub(pattern, new_block.strip(), content, flags=re.DOTALL)
else:
    updated = content.rstrip() + '\n\n' + new_block.strip() + '\n'

path.write_text(updated)
```

If appending (no existing block): append to end of `~/.zshrc` with a leading blank line.

### Phase 4 — Verify

**9. Source and confirm**

```bash
source ~/.zshrc
```

Then run the verification script (located in this skill's `scripts/` directory):

```bash
zsh scripts/verify-integration.sh
```

This checks all 7 conditions and reports ✓/✗ for each:
- Chrome for Testing running (with `--remote-debugging-port`)
- Debug port 9222 responding with JSON
- `claude-with-chrome` alias defined
- Log directory present
- Plugin's `mcp-chrome.json` resolves to an existing file in the install cache
- `settings.json` isolation (chrome-devtools absent from default config)
- `~/.zshrc` managed block present

**10. Surface log access**

Remind the user how to access Chrome logs:
```bash
# Terminal tail
tail -f ~/Library/Logs/profile-manager/chrome-for-testing.log

# Console.app: open Console.app → Files → ~/Library/Logs → profile-manager/
```

## User Interaction

Use `AskUserQuestion` at these decision points:

1. **Before Phase 2 (MCP isolation)**: Confirm before modifying `~/.claude/settings.json`
2. **Before Phase 3 (zshrc write)**: Show block preview, confirm before writing
3. **On missing Chrome**: Ask whether to install via npx or manually
4. **On stale `~/.claude/mcp-chrome.json`**: Offer to delete it (no longer needed)

Never write to files without explicit user confirmation.

## Prerequisites Checklist

Present this at skill start before creating tasks:

```
Prerequisites for setup-chrome-integration:
  [ ] Chrome for Testing installed at /Applications/Google Chrome for Testing.app/
  [ ] Node.js available (for npx install path, if Chrome is missing)
  [ ] Port 9222 not in use by another service
  [ ] ~/.claude/settings.json is writable
  [ ] ~/.zshrc is writable
  [ ] profile-manager plugin is installed (make install in the marketplace)
```

Run the checks and show ✓/✗ for each before proceeding.

## Success Criteria

- [ ] Chrome for Testing is installed and executable
- [ ] `~/.zshrc` contains the tagged `profile-manager:setup-chrome-integration` block
- [ ] New shells auto-start Chrome for Testing with `--remote-debugging-port=9222`
- [ ] Chrome stdout/stderr routes to `~/Library/Logs/profile-manager/chrome-for-testing.log`
- [ ] `_pfm_chrome_mcp_config()` resolves to a valid `mcp-chrome.json` in the plugin cache
- [ ] `chrome-devtools` entry is absent from `~/.claude/settings.json` default config
- [ ] `claude-with-chrome` alias is available and launches Claude with browser tools
- [ ] `curl http://127.0.0.1:9222/json/version` returns JSON
- [ ] Re-running the skill replaces the block without duplicating it

## Common Mistakes to Avoid

1. **Using `& disown` instead of `&!`** — in zsh, `&!` is the idiomatic one-step background+disown
2. **Appending instead of replacing** — always check for the `>>>` marker before appending
3. **Forgetting `--mcp-config` merges** — it adds to the default config, not replaces it; chrome-devtools in the default config would still load even with isolation
4. **Wrong `pgrep` pattern** — must match `--remote-debugging-port` in the process args, not just the app name
5. **Hardcoding the port** — expose `CHROME_DEBUG_PORT` as a variable so it can be changed
6. **Writing to `~/.claude/mcp-chrome.json`** — the config lives in the plugin cache; no file should be written to `~/.claude/`

## Related Skills

- `/profile-manager:introduce` — overview of this plugin
- `/claude-manager:setup-claude-md` — configure Claude Code project instructions
