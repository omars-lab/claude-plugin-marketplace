# OEID Claude Plugin Marketplace

Personal plugin marketplace for NotePlan management and productivity tools.

## Quick Start

```bash
git clone https://github.com/omareid/oeid-claude-plugin-marketplace ~/workspace/oeid-claude-plugin-marketplace
cd ~/workspace/oeid-claude-plugin-marketplace
make register   # Add marketplace to Claude
make install    # Install all plugins
```

Then in Claude Code:
```
/discover-oeid-plugins:explore-plugins   # See what's installed
/noteplan-manager:introduce              # Explore NotePlan skills
```

## Overview

This marketplace contains custom Claude Code plugins designed to enhance productivity through intelligent automation, organization, and content management.

## Available Plugins

### Getting Started

#### discover-oeid-plugins
Discover available personal plugins and see what's installed.

**Skills:**
- `/discover-oeid-plugins:explore-plugins` - Explore plugins with installation status

**Use Case:** When you want to see what plugins are available and their status.

---

### Development Tools

#### config-manager
Manage Claude Code permissions and working directories for marketplace development.

**Skills:**
- `/config-manager:manage-permissions` - Manage bash command permissions
- `/config-manager:setup-working-dirs` - Configure working directories
- `/config-manager:setup-dev-env` - Complete dev environment setup

**Use Case:** Eliminating permission prompts for common bash commands and directories during marketplace development and NotePlan workflows.

**Configuration Location:**
- Settings: `~/.claude/settings.local.json`

---

### NotePlan Management Suite

#### noteplan-manager
Complete NotePlan management: templates, organization, analysis, note creation.

**Skills:** Run `/noteplan-manager:introduce` to see all skills.

**Use Case:** Everything NotePlan — templates, daily organization, structure analysis, note creation.

---

#### servicenow-manager
ServiceNow-specific Tampermonkey userscripts and automation patterns.

**Skills:** Run `/servicenow-manager:introduce` to see all skills.

---

#### script-manager
Create and manage Tampermonkey userscripts with best practices.

**Skills:** Run `/script-manager:introduce` to see all skills.

---

#### claude-manager
Manage Claude skills and CLAUDE.md files — create, update, and organize skills across plugins.

**Skills:** Run `/claude-manager:introduce` to see all skills.

---

#### spirituality-manager
Plan and track spiritual practices — Ramadan schedules, Quran memorization, and dua routines.

**Skills:** Run `/spirituality-manager:introduce` to see all skills.

---

#### knowledge-manager
Extract, map, and query knowledge from notes — Zettelkasten-style atomic notes.

**Skills:** Run `/knowledge-manager:introduce` to see all skills.

---

#### documentation-manager
Professional documentation management — structure notes, organize docs, ensure scannability.

**Skills:** Run `/documentation-manager:introduce` to see all skills.

---

## Installation

### Add the Marketplace

```bash
cd ~/workspace/oeid-claude-plugin-marketplace
make register
# or:
./scripts/cli register
```

### Install Plugins

```bash
# Install all plugins
make install

# Install a single plugin
./scripts/cli install-single oeid-claude-plugins <plugin-name>
```

### Verify Installation

```bash
make verify-installs
make list-plugins
```

### Update Plugins

```bash
make update
```

## Make Commands

```bash
# Installation
make install          # Install all plugins
make verify-installs  # Verify installations succeeded
make list-plugins     # List plugins with status

# Testing
make test-all         # Test all plugins
make validate         # Validate marketplace structure

# Maintenance
make update           # Check versions + update all plugins
make version-check    # Dry run: show what would change
make version-init     # Initialize version tracking (one-time)
make clean            # Clean build artifacts
make doctor           # Diagnose installation issues

# Help
make help             # Show all available commands
```

For detailed documentation on version management, see [docs/VERSION-MANAGEMENT.md](docs/VERSION-MANAGEMENT.md).

## Plugin Development

### Structure

```
oeid-claude-plugin-marketplace/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace catalog
├── plugins/
│   └── <plugin-name>/
│       ├── .claude-plugin/
│       │   ├── plugin.json       # Plugin manifest
│       │   └── version-tracking.json
│       ├── skills/
│       │   └── <skill-name>/
│       │       └── SKILL.md      # Skill definition
│       └── README.md             # Plugin documentation
├── scripts/
│   └── cli                       # Marketplace management CLI
├── docs/                         # Documentation
├── Makefile                      # Build and test targets
└── README.md                     # This file
```

### Creating a New Plugin

```bash
/claude-manager:create-plugin
```

## NotePlan Paths Reference

NotePlan data lives at:

```
~/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3/
  Notes/        # Notes
  Calendar/     # Daily files
  Notes/@Templates/  # Templates
```

Run `make noteplan-info` to print the full paths for your user.

## Support

For issues or suggestions, open an issue in the repository:
https://github.com/omareid/oeid-claude-plugin-marketplace/issues

## License

MIT License - See individual plugin licenses for details.

---

**Version**: 1.0.0
**Author**: Omar Eid
