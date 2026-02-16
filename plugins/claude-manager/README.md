# Claude Manager Plugin

Meta-plugin for managing Claude Code skills and CLAUDE.md files across your plugin ecosystem.

## Features

- 🆕 **Create new skills** - Generate skill structure with proper files and registry updates
- ✏️ **Update existing skills** - Navigate to skills and edit them with context awareness
- 📝 **CLAUDE.md setup** - Generate comprehensive project instruction files

## Skills

### `/claude-md-setup`

Creates comprehensive CLAUDE.md files for projects with:
- Project overview and architecture
- Development workflows and conventions
- Coding standards and patterns
- Common tasks and examples

**Usage:**
```
/claude-md-setup
```

### `/skill-create`

Creates a new skill in any plugin with:
- Proper directory structure
- SKILL.md template with best practices
- Registry updates (plugin.json)
- Example prompts and workflows

**Usage:**
```
/skill-create
```

**Prompts you for:**
- Plugin name (which plugin to add to)
- Skill name
- Description
- Category
- What the skill should do

**What it creates:**
1. `plugins/{plugin-name}/skills/{skill-name}/SKILL.md`
2. Updates `plugins/{plugin-name}/.claude-plugin/plugin.json`
3. Provides testing instructions

### `/skill-update`

Updates an existing skill by:
- Navigating to the correct workspace directory
- Reading the current skill content
- Making requested changes
- Validating structure

**Usage:**
```
/skill-update
```

**Prompts you for:**
- Plugin name
- Skill name
- What changes to make

**Smart features:**
- Auto-detects plugin location
- Reads current skill before editing
- Preserves skill structure and format
- Validates changes

## Installation

```bash
claude plugin install /path/to/oeid-claude-plugin-marketplace/plugins/claude-manager
```

## Use Cases

### Creating a New Skill

1. Run `/skill-create`
2. Answer prompts (plugin name, skill name, description)
3. Skill structure generated automatically
4. Plugin registry updated
5. Start editing the generated SKILL.md

### Updating an Existing Skill

1. Run `/skill-update`
2. Specify plugin and skill name
3. Describe changes needed
4. Claude reads current content and updates it
5. Changes validated and saved

### Setting Up CLAUDE.md

1. Run `/claude-md-setup` in any project
2. Claude analyzes your codebase
3. Asks about preferences and conventions
4. Generates comprehensive CLAUDE.md
5. File placed in project root

## Best Practices

### Skill Naming

- Use kebab-case: `skill-name`
- Be descriptive: `create-tampermonkey-script` not `create-script`
- Action-oriented: `update-skill` not `skill-updater`

### Skill Structure

Every skill should have:
- Clear objective statement
- Step-by-step workflow (Phase 1, 2, 3...)
- User interaction guidelines
- Success criteria
- Examples

### Plugin Organization

- Group related skills in same plugin
- Keep plugins focused (single responsibility)
- Document cross-plugin dependencies
- Update marketplace.json when adding plugins

## Architecture

```
claude-manager/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata + skill registry
├── README.md                 # This file
└── skills/
    ├── claude-md-setup/      # Generate CLAUDE.md files
    │   └── SKILL.md
    ├── skill-create/         # Create new skills
    │   └── SKILL.md
    └── skill-update/         # Update existing skills
        └── SKILL.md
```

## Development

This is a meta-plugin - it manages other plugins and skills. When making changes:

1. Test skill creation in a test plugin first
2. Verify registry updates work correctly
3. Test navigation to different plugin locations
4. Ensure SKILL.md templates are comprehensive

## Integration

Works seamlessly with:
- **script-manager** - Create Tampermonkey skills
- **config-manager** - Setup development environment
- **noteplan-manager** - NotePlan automation skills
- Any custom plugin you create

## Version

1.0.0 - Initial release with claude-md-setup, skill-create, and skill-update

## License

MIT

## Author

Omar Eid (with Claude Code assistance)
