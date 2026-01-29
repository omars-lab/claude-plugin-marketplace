# 🎯 OEID Claude Plugin Marketplace

Personal plugin marketplace for NotePlan management and productivity tools.

## Overview

This marketplace contains custom Claude Code plugins designed to enhance NotePlan productivity through intelligent automation, organization, and content management.

## Available Plugins

### 🚀 Getting Started

#### discover-oeid-plugins
Discover available personal plugins and see what's installed.

**Skills:**
- `/discover-oeid-plugins:explore-plugins` - Explore plugins with installation status

**Use Case:** When you want to see what plugins are available and their status.

---

### ⚙️ Development Tools

#### claude-permission-config-manager
Manage Claude Code permissions and working directories for marketplace development.

**Skills:**
- `/claude-permission-config-manager:manage-permissions` - Manage bash command permissions
- `/claude-permission-config-manager:setup-working-dirs` - Configure working directories
- `/claude-permission-config-manager:setup-dev-env` - Complete dev environment setup

**Use Case:** Eliminating permission prompts for common bash commands and directories during marketplace development and NotePlan workflows.

**Configuration Location:**
- Settings: `~/.claude/settings.local.json`

---

### 📝 NotePlan Management Suite

#### noteplan-templates
Maintain and manage NotePlan templates in the @Templates directory.

**Skills:**
- `/noteplan-templates:manage-templates` - Edit and maintain templates
- `/noteplan-templates:list-templates` - List all available templates
- `/noteplan-templates:create-template` - Create new templates

**Use Case:** Template creation, editing, and organization.

**Templates Location:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/`

---

#### noteplan-daily-organizer
Move content from daily files to relevant notes with folder and emoji awareness.

**Skills:**
- `/noteplan-daily-organizer:organize-daily` - Organize daily notes intelligently
- `/noteplan-daily-organizer:move-content` - Move specific content between notes

**Use Case:** Daily note processing, content organization, and task migration.

**Daily Files:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar/`

**Notes:** `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/`

---

#### noteplan-structure-analyzer
Analyze NotePlan folder structure, emoji usage, and suggest enhancements.

**Skills:**
- `/noteplan-structure-analyzer:analyze-structure` - Comprehensive structure analysis
- `/noteplan-structure-analyzer:suggest-improvements` - Actionable improvement recommendations

**Use Case:** Understanding your NotePlan organization and optimizing structure.

---

#### noteplan-note-creator
Create new NotePlan notes following existing conventions and patterns.

**Skills:**
- `/noteplan-note-creator:create-note` - Create structured notes with full context
- `/noteplan-note-creator:quick-note` - Rapidly create simple notes

**Use Case:** Creating new notes that seamlessly integrate with existing organization.

---

## Installation

### Add the Marketplace

```bash
/plugin marketplace add /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace
```

### Install Plugins

#### Option 1: Individual Installation

```bash
# Install discovery plugin (recommended first)
/plugin install discover-oeid-plugins@oeid-claude-plugins

# Install development tools
/plugin install claude-permission-config-manager@oeid-claude-plugins

# Install NotePlan plugins
/plugin install noteplan-templates@oeid-claude-plugins
/plugin install noteplan-daily-organizer@oeid-claude-plugins
/plugin install noteplan-structure-analyzer@oeid-claude-plugins
/plugin install noteplan-note-creator@oeid-claude-plugins
```

#### Option 2: Install All at Once

```bash
cd /path/to/oeid-claude-plugin-marketplace
make install-all
```

#### Verify Installation

```bash
# Verify all plugins installed correctly
make verify-installs

# List plugins with status
make list-plugins
```

### List Available Plugins

```bash
/plugin list
```

Or use the discovery skill:
```bash
/discover-oeid-plugins:explore-plugins
```

### Update Plugins

```bash
# Update marketplace
/plugin marketplace update

# Update specific plugin
/plugin update <plugin-name>
```

## Quick Start Guide

1. **Add and install the discovery plugin** to explore available plugins
2. **Install claude-permission-config-manager** and run `/claude-permission-config-manager:setup-dev-env` to configure your development environment
3. **Install noteplan-structure-analyzer** to understand your current organization
4. **Install noteplan-templates** to manage your templates
5. **Install noteplan-daily-organizer** for daily note processing
6. **Install noteplan-note-creator** for creating new notes

## Common Workflows

### Development Environment Setup
```bash
# Complete dev environment setup (permissions + directories)
/claude-permission-config-manager:setup-dev-env

# Add specific bash permissions
/claude-permission-config-manager:manage-permissions

# Configure working directories
/claude-permission-config-manager:setup-working-dirs
```

### Daily Note Processing
```bash
# Organize today's daily note
/noteplan-daily-organizer:organize-daily

# Move specific content
/noteplan-daily-organizer:move-content
```

### Template Management
```bash
# List all templates
/noteplan-templates:list-templates

# Create a new template
/noteplan-templates:create-template

# Edit templates
/noteplan-templates:manage-templates
```

### Structure Analysis
```bash
# Analyze your NotePlan organization
/noteplan-structure-analyzer:analyze-structure

# Get improvement suggestions
/noteplan-structure-analyzer:suggest-improvements
```

### Note Creation
```bash
# Create a structured note
/noteplan-note-creator:create-note

# Quick note capture
/noteplan-note-creator:quick-note
```

## Plugin Development

### Structure

```
oeid-claude-plugin-marketplace/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace catalog
├── plugins/
│   └── <plugin-name>/
│       ├── .claude-plugin/
│       │   └── plugin.json       # Plugin manifest
│       ├── skills/
│       │   └── <skill-name>/
│       │       └── SKILL.md      # Skill definition
│       └── README.md             # Plugin documentation
├── docs/                         # Documentation
├── Makefile                      # Build and test targets
└── README.md                     # This file
```

### Make Commands

```bash
# Installation
make install-all        # Install all plugins
make verify-installs    # Verify installations succeeded
make list-plugins       # List plugins with status

# Testing
make test-all          # Test all plugins
make test-discover     # Test specific plugin
make test-templates
make test-organizer
make test-analyzer
make test-creator

# Maintenance
make validate          # Validate marketplace structure
make update-all        # Update all installed plugins
make clean            # Clean build artifacts

# Help
make help             # Show all available commands
```

For detailed documentation on Makefile commands, scripts, and automation, see:
- **[Makefile Guide](docs/guides/MAKEFILE_GUIDE.md)** - Comprehensive guide to using Make
- **[Quick Start Guide](docs/getting-started/QUICK_START.md)** - Get started quickly

## NotePlan Paths Reference

- **Notes**: `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/`
- **Calendar/Daily**: `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Calendar/`
- **Templates**: `/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/Notes/@Templates/`

## Support

For issues or suggestions:
- Open an issue in the repository
- Contact: omar.eid@servicenow.com

## License

MIT License - See individual plugin licenses for details.

---

**Version**: 1.0.0
**Author**: Omar Eid
**Last Updated**: 2026-01-29
