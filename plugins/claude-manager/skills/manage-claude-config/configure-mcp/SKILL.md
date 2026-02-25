---
name: configure-mcp
description: Audit and configure MCP servers — restrict tools, disable servers, and reduce token context consumption across ~/.claude.json and ~/.claude/settings.json
---

# Configure MCP

You are an MCP configuration assistant. Your role is to audit active MCP servers, apply tool restrictions, and recommend strategies to reduce token context overhead from MCP tool definitions.

## Background

Every active MCP tool injects its name, description, and parameter schema into the system prompt at session start. A server with 20+ tools can add thousands of tokens before you type a single message. The goal of this skill is to surface that cost and help the user control it.

### Config File Map

Claude Code reads MCP servers from two user-scope files — **both are active**:

| File | Scope | Notes |
|---|---|---|
| `~/.claude.json` | Global (legacy) | Primary location for most installed servers |
| `~/.claude/settings.json` | Global (newer) | Preferred for new entries; also active |
| `./.claude/settings.json` | Project-local | Overrides for a specific repo |

### What Actually Reduces Tokens (Critical)

There are two distinct mechanisms — they are **not interchangeable**:

| Mechanism | Reduces system prompt tokens? | Prevents tool execution? |
|---|---|---|
| `disabledTools` in `~/.claude.json` | ❌ No | ✅ Yes |
| Server-level tool filtering | ✅ Yes | ✅ Yes |
| Opt-in alias (server not loaded) | ✅ Yes | ✅ Yes |

**`disabledTools` is an execution restriction only.** Tool definitions are still reported by the server, injected into the system prompt, and billed as tokens. Use it to block tool calls — not to save context budget.

To actually reduce token overhead you must either:
- **Not load the server** (opt-in alias pattern), or
- **Configure the server to report fewer tools** (server-level filtering)

### Server-Level Tool Filtering

Some servers support native filtering. Always prefer this over `disabledTools` when available.

**Docker MCP Gateway** supports `--tools` to restrict which tools the gateway exposes. Unlisted tools never start, never appear in the system prompt:

```json
"MCP_DOCKER": {
  "command": "docker",
  "args": ["mcp", "gateway", "run", "--tools", "get_timed_transcript,get_transcript,get_video_info"]
}
```

Check other servers for equivalent flags (`--tools`, `--filter`, `--allow`, etc.) before reaching for `disabledTools`.

### Tool Restriction Mechanism (`disabledTools`)

Use `disabledTools` when you want to **block execution** of specific tools (e.g. destructive tools like `delete_record`, `execute_script`) while keeping them visible in the system prompt — or when server-level filtering is not available.

```json
"mcpServers": {
  "MY_SERVER": {
    "command": "...",
    "args": ["..."],
    "disabledTools": ["tool-name-1", "tool-name-2"]
  }
}
```

Tool names use the **raw server-reported name** — no `mcp__ServerName__` prefix.

### Plugin-Provided MCP Servers (Critical Nuance)

When a plugin registers a server via `.mcp.json`, Claude Code namespaces its tools as:
`mcp__plugin_{plugin-name}_{server-name}__{tool}`

This differs from user-configured servers (`mcp__{server-name}__{tool}`).

**Two layers of failure for plugin servers:**
1. **`disabledTools` inside a plugin's `.mcp.json` is silently ignored** — Claude Code does not read it
2. **`disabledTools` in user `~/.claude.json` does not reduce tokens** — tool definitions still inject (execution restriction only)

**The only way to actually suppress tokens from a plugin-provided server is the opt-in alias pattern:**

1. Add the server to `~/.claude.json` mcpServers with **all tools in `disabledTools`** — this blocks execution in default sessions (tokens still injected, but tools can't be called)
2. Create a version-resolving opt-in alias that loads the plugin's `.mcp.json` via `--mcp-config`

```json
// ~/.claude.json — blocks execution in default sessions
"mcpServers": {
  "ceg": {
    "command": "conda", "args": ["run", ...],
    "disabledTools": ["tool1", "tool2", ...]
  }
}
```

```zsh
# ~/.zshrc — opt-in alias: auto-resolves to the latest installed plugin version
_ceg_mcp_config() {
  local base="${HOME}/.claude/plugins/cache/ceg-claude-plugins/ceg-mcp-plugin"
  local ver; ver=$(ls "$base" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -t. -k1,1n -k2,2n -k3,3n | tail -1)
  echo "${base}/${ver}/.mcp.json"
}
alias claude-with-servicenow='claude --mcp-config "$(_ceg_mcp_config)"'
```

The resolver auto-finds the latest plugin version — no manual update needed after `claude plugin update`.

> **Note:** Token overhead from the plugin server's tools will still appear in default sessions until/unless the plugin's server registration is removed from `.mcp.json`. The `disabledTools` approach trades token cost for execution safety.

### Token Cost Tiers (rough guidance)

| Tools active | Estimated overhead |
|---|---|
| 0–5 | Negligible |
| 6–15 | Low (~500–1500 tokens) |
| 16–30 | Medium (~1500–3000 tokens) |
| 31+ | High — consider opt-in alias pattern |

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Audit MCP config", description: "Parse both config files, enumerate servers and tool counts", activeForm: "Auditing MCP configuration" })
TaskCreate({ subject: "Present findings and get action", description: "Show cost dashboard, ask what to configure", activeForm: "Presenting MCP dashboard" })
TaskCreate({ subject: "Apply changes", description: "Write disabledTools / remove servers / create opt-in alias", activeForm: "Applying MCP changes" })
TaskCreate({ subject: "Verify", description: "Confirm config is valid JSON and changes are reflected", activeForm: "Verifying changes" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Your Workflow

### Phase 1 — Audit MCP Config

**1. Parse both config files**

```python
import json, pathlib

configs = {}
for name, path_str in [
    ("~/.claude.json", "~/.claude.json"),
    ("~/.claude/settings.json", "~/.claude/settings.json"),
]:
    path = pathlib.Path(path_str).expanduser()
    if path.exists():
        s = json.loads(path.read_text())
        configs[name] = s.get("mcpServers", {})
```

For each server found, report:
- Server name
- Source file
- Command / args
- Any existing `disabledTools`
- **Tool count** — if the server is active in the current session, use the known tool list; otherwise note "tool count unknown (not running)"

**2. Run the audit script**

```bash
python3 scripts/audit-mcp.py
```

The script enumerates servers, estimates token cost tier, flags high-cost servers, and lists disabled vs active tools per server.

**3. Present the MCP Cost Dashboard**

Example format:

```
MCP Configuration Audit
────────────────────────────────────────
Server          Source           Tools   Cost Tier   Notes
──────────────  ───────────────  ──────  ──────────  ──────────────────────
MCP_DOCKER      ~/.claude.json   9/9     Medium      All tools active
plantuml        ~/.claude.json   3/3     Negligible
chrome-devtools opt-in only      —       —           Excluded via alias ✓

Total active tools: 12  |  Estimated overhead: ~1,200 tokens/session
────────────────────────────────────────
```

### Phase 2 — Present Recommendations and Get Action

**4. Offer token reduction strategies**

For any server with more than 5 active tools, proactively suggest:

| Strategy | When to use | How |
|---|---|---|
| `disabledTools` | Server is used, but not all tools | Add array to server entry; keep only what you use |
| Opt-in alias | Server rarely needed | Move to `--mcp-config` alias (like `claude-with-chrome`) — zero cost by default |
| Disable server entirely | Server not in use | Remove from config or set `"disabled": true` |
| Project-local override | Only needed in specific repos | Add to `./.claude/settings.json` instead of global |

**5. Use `AskUserQuestion` to select action**

Options:
- Restrict tools on a specific server (specify which tools to keep)
- Move a server to opt-in alias
- Disable a server entirely
- Apply all recommendations automatically
- Just show me the report (no changes)

### Phase 3 — Apply Changes

**6. Confirm before writing**

Always show the exact diff of what will change in the JSON and use `AskUserQuestion` to confirm.

**For `disabledTools` restriction:**

```python
import json, pathlib

path = pathlib.Path("~/.claude.json").expanduser()
s = json.loads(path.read_text())
server = s["mcpServers"]["SERVER_NAME"]

# Set disabledTools to everything except the tools the user wants to keep
all_tools = [...]       # known tool list for this server
keep_tools = [...]      # tools user selected
server["disabledTools"] = [t for t in all_tools if t not in keep_tools]

path.write_text(json.dumps(s, indent=2) + "\n")
```

**For opt-in alias (move server to --mcp-config):**

1. Extract the server entry from the global config
2. Write it to `~/.claude/mcp-<server-name>.json`
3. Remove from global config
4. Add a zshrc alias: `alias claude-with-<server>='claude --mcp-config ~/.claude/mcp-<server-name>.json'`

**For disabling entirely:**

```python
s["mcpServers"].pop("SERVER_NAME", None)
```

### Phase 4 — Verify

**7. Validate JSON and confirm**

```python
# Re-parse to confirm valid JSON
for name, path_str in [("~/.claude.json", "~/.claude.json"), ("~/.claude/settings.json", "~/.claude/settings.json")]:
    path = pathlib.Path(path_str).expanduser()
    if path.exists():
        json.loads(path.read_text())  # throws if invalid
        print(f"✓ {name} — valid JSON")
```

Report the updated server table with new tool counts and estimated token savings.

## Token Reduction Reference

**Quick wins in order of impact:**

1. **Identify your largest server** — run the audit, find the server with the most active tools
2. **Apply `disabledTools`** — if you use 3 of 20 tools, disable the other 17
3. **Move rarely-used servers to opt-in aliases** — zero cost until invoked
4. **Audit project configs** — servers enabled globally may not be needed in every project
5. **Remove stale servers** — servers you no longer use still cost tokens if defined

**The opt-in alias pattern** (established in profile-manager):
```zsh
alias claude-with-<tool>='claude --mcp-config ~/.claude/mcp-<tool>.json'
```
`--mcp-config` merges with the default config — it does NOT replace it.

## User Interaction

Use `AskUserQuestion` at these points:
1. **After audit** — present dashboard, ask which action to take
2. **Before any write** — show the exact JSON change, confirm
3. **On ambiguity** — if tool list for a server is unknown, ask user to list tools or run Claude with the server active first

Never modify config files without explicit confirmation.

## Known MCP Servers and Tool Inventories

Maintain this reference as servers are discovered. Update when new tools are found.

### MCP_DOCKER (docker mcp gateway run)
Full tool list:
- `code-mode` — multi-server JavaScript scripting tool
- `get_timed_transcript` — YouTube transcript with timestamps
- `get_transcript` — YouTube transcript
- `get_video_info` — YouTube video metadata
- `mcp-add` — add MCP server to session
- `mcp-config-set` — configure MCP server
- `mcp-exec` — execute arbitrary MCP tool
- `mcp-find` — search MCP catalog
- `mcp-remove` — remove MCP server

**Recommended default**: keep only `get_timed_transcript`, `get_transcript`, `get_video_info`.
Disable: `code-mode`, `mcp-add`, `mcp-config-set`, `mcp-exec`, `mcp-find`, `mcp-remove`

## Success Criteria

- [ ] Both config files audited and server/tool inventory presented
- [ ] Token cost tier shown per server
- [ ] Recommendations surfaced for high-cost servers
- [ ] Changes confirmed by user before writing
- [ ] Config files remain valid JSON after changes
- [ ] Tool counts accurately reflect `disabledTools` after changes

## Related Skills

- `/profile-manager:setup-chrome-integration` — reference implementation of the opt-in alias pattern
- `/claude-manager:fix-plugins` — version and install management
