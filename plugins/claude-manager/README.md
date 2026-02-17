# Claude Manager

Meta-plugin for managing Claude Code plugins, skills, and CLAUDE.md files across your plugin ecosystem.

## Getting Started

```bash
# Install
/plugin install claude-manager@oeid-claude-plugins

# Learn what this plugin can do
/claude-manager:introduce
```

## Skills (5)

| Category | Skill | What it does |
|---|---|---|
| **Plugin** | `create-plugin` | Scaffold a new plugin with proper structure and framework compliance |
| | `fix-plugins` | Audit plugin health, detect version issues, fix compliance gaps |
| **Skill** | `skill-create` | Create new skills in any plugin with mandatory patterns |
| | `skill-update` | Navigate to and safely edit existing skills |
| **Setup** | `claude-md-setup` | Generate comprehensive CLAUDE.md project instruction files |

## Framework Standards

All plugins in the marketplace must have:
- An `introduce` skill explaining capabilities
- Skills using `TaskCreate`/`TaskUpdate` for progress tracking
- Skills using `AskUserQuestion` for user decisions
- Git safety patterns for file-modifying skills
- Minimal README (<50 lines) - substantive docs go in `introduce` skill

Use `fix-plugins` to audit compliance and `create-plugin` to scaffold correctly from the start.

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
