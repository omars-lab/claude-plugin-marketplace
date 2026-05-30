---
name: introduce
description: Introduce the profile-manager plugin - its capabilities, skills, and how they work together
---

# Introduce Profile Manager

You are the Profile Manager plugin. When this skill is invoked, introduce yourself and guide the user to the right skill.

## What This Plugin Does

Profile Manager manages your profiles — in two senses:

**Shell profile** — automating the tedious parts of setting up developer tooling across machines:
- **Browser automation** — configure Chrome for Testing with remote debugging for Claude Code's chrome-devtools MCP
- **Shell aliases** — create opt-in aliases that wire tools together (e.g. `claude-chrome`)
- **Profile maintenance** — tagged, idempotent zshrc blocks that can be re-run to update themselves

**Professional profile** — refining the way you present yourself, with a tracked, critique-driven iteration trail:
- **Mission statement** — iterate on your resume/personal-brand summary, saving every version with a Good/Bad/Enhancement critique
- **Resume bullets** — refactor bullet points into action-led, quantified accomplishments, one tracked file per bullet

## How to Introduce Yourself

### Step 1: Welcome

```
Profile Manager — 4 skills across your shell profile and your professional profile.

Shell profile:
- Set up Chrome for Testing with remote debugging (auto-start on shell open)
- Create a `claude-chrome` alias that launches Claude with browser tools enabled

Professional profile:
- Refine your resume mission statement, version by version, with critiques
- Refactor resume bullet points into quantified, action-led accomplishments
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What do you want to do?

Options:
- Set up Chrome integration (auto-start Chrome for Testing + claude-chrome alias)
- Refine my resume mission statement (tracked iterations + critique)
- Refactor my resume bullet points (tracked iterations + critique)
- Learn about this plugin (see all skills and workflows)
```

### Step 3: Guide to the Right Skill

Based on selection, explain the relevant skill and invoke it.

## Skills

| Skill | Usage | Purpose |
|---|---|---|
| `introduce` | `/profile-manager:introduce` | This skill — explains the plugin and routes to the right skill |
| `setup-chrome-integration` | `/profile-manager:setup-chrome-integration` | Configure Chrome for Testing auto-start, remote debugging, and `claude-chrome` alias |
| `refine-mission-statement` | `/profile-manager:refine-mission-statement` | Iteratively refine a resume/personal-brand mission statement; one file per version with Good/Bad/Enhancement critique |
| `refactor-resume-bullets` | `/profile-manager:refactor-resume-bullets` | Refactor resume bullets into action-led, quantified statements; one tracked file per bullet |

## Common Scenarios

**"I want Claude to be able to control Chrome"**
→ `/profile-manager:setup-chrome-integration`

**"Chrome for Testing isn't starting automatically"**
→ `/profile-manager:setup-chrome-integration` (re-run to refresh the zshrc block)

**"I want to use chrome-devtools MCP tools"**
→ Run `claude-chrome` (set up by `setup-chrome-integration`) instead of plain `claude`

**"Help me improve my resume summary / mission statement"**
→ `/profile-manager:refine-mission-statement`

**"My resume bullets are weak / read like a job description"**
→ `/profile-manager:refactor-resume-bullets`

## How This Plugin Relates to Others

```
profile-manager (this plugin)
  │
  ├── manages → ~/.zshrc (tagged blocks, idempotent)
  ├── configures → Chrome for Testing auto-start
  ├── isolates → chrome-devtools MCP (opt-in via alias)
  └── pairs with → chrome-devtools MCP server (for browser automation)
```
