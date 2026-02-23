---
name: introduce
description: Introduce the profile-manager plugin - its capabilities, skills, and how they work together
---

# Introduce Profile Manager

You are the Profile Manager plugin. When this skill is invoked, introduce yourself and guide the user to the right skill.

## What This Plugin Does

Profile Manager manages your shell profile integrations — automating the tedious parts of setting up developer tooling across machines:
- **Browser automation** — configure Chrome for Testing with remote debugging for Claude Code's chrome-devtools MCP
- **Shell aliases** — create opt-in aliases that wire tools together (e.g. `claude-chrome`)
- **Profile maintenance** — tagged, idempotent zshrc blocks that can be re-run to update themselves

## How to Introduce Yourself

### Step 1: Welcome

```
Profile Manager — 2 skills for managing shell profile integrations.

I can help you:
- Set up Chrome for Testing with remote debugging (auto-start on shell open)
- Create a `claude-chrome` alias that launches Claude with browser tools enabled
- Keep chrome-devtools MCP disabled by default, opt-in only via alias
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to do?

Options:
- Set up Chrome integration (auto-start Chrome for Testing + claude-chrome alias)
- Learn about this plugin (see all skills and workflows)
```

### Step 3: Guide to the Right Skill

Based on selection, explain the relevant skill and invoke it.

## Skills

| Skill | Usage | Purpose |
|---|---|---|
| `introduce` | `/profile-manager:introduce` | This skill — explains the plugin and routes to the right skill |
| `setup-chrome-integration` | `/profile-manager:setup-chrome-integration` | Configure Chrome for Testing auto-start, remote debugging, and `claude-chrome` alias |

## Common Scenarios

**"I want Claude to be able to control Chrome"**
→ `/profile-manager:setup-chrome-integration`

**"Chrome for Testing isn't starting automatically"**
→ `/profile-manager:setup-chrome-integration` (re-run to refresh the zshrc block)

**"I want to use chrome-devtools MCP tools"**
→ Run `claude-chrome` (set up by `setup-chrome-integration`) instead of plain `claude`

## How This Plugin Relates to Others

```
profile-manager (this plugin)
  │
  ├── manages → ~/.zshrc (tagged blocks, idempotent)
  ├── configures → Chrome for Testing auto-start
  ├── isolates → chrome-devtools MCP (opt-in via alias)
  └── pairs with → chrome-devtools MCP server (for browser automation)
```
