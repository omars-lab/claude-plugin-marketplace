# Plan Manager

Manage Claude Code plans -- inspect quality, move to projects, and produce changelogs.

## Getting Started

```bash
# Install
/plugin install plan-manager@oeid-claude-plugins

# Learn what this plugin can do
/plan-manager:introduce
```

## Skills (3)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain plugin capabilities and guide to the right skill |
| **Analysis** | `inspect-plan` | Analyze a Claude plan for gaps, risks, missing steps, and quality issues |
| **Tracing** | `trace-plan` | Find repos, commits, and Claude sessions related to a plan's execution |

## Future Skills

- `move-plan` - Move a plan to the relevant project directory
- `plan-changelog` - Generate changelog entries from traced commits
- `compare-plans` - Diff two plan versions or compare plan vs implementation

## Requirements

- Claude Code CLI
- Access to `~/.claude/plans/` directory

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
