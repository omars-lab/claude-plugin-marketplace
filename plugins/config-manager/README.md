# Config Manager

Comprehensive development configuration management for projects - Claude permissions, Makefiles, CLAUDE.md files, documentation structure, and complete environment setup.

## Overview

Config Manager is your one-stop solution for setting up and maintaining development configurations. Whether you're configuring Claude Code permissions, setting up build automation with Makefiles, creating project-specific CLAUDE.md instructions, or organizing documentation, this plugin handles it all.

## Skills

### Claude Configuration

#### claude-permissions
**Usage:** `/config-manager:claude-permissions`

Manage bash command permissions in Claude settings to eliminate permission prompts.

**Features:**
- Add/remove allowed bash commands
- Review current permissions
- Get workflow-specific recommendations
- Validate settings.local.json structure
- Security-focused configurations

**Common Use Cases:**
- Marketplace development permissions (`make`, `tree`, `ln`)
- Git operations (`git status`, `git commit`, `git push`)
- Package management (`npm`, `node`, `pnpm`)
- File operations (`ls`, `find`, `grep`)

#### setup-working-dirs
**Usage:** `/config-manager:setup-working-dirs`

Configure working directories so Claude can access your projects without prompts.

**Features:**
- Add workspace directories
- Configure marketplace paths
- Set up NotePlan access
- Remove unnecessary directories
- Validate directory configurations

#### setup-dev-env
**Usage:** `/config-manager:setup-dev-env`

Complete Claude development environment setup in one command.

**Features:**
- Combined permissions + working directories setup
- Preset configurations (Minimal, Standard, Advanced)
- Interactive setup wizard
- Validation and testing

### Build Configuration

#### makefile-setup
**Usage:** `/config-manager:makefile-setup`

Create or enhance Makefiles with common development targets and best practices.

**Features:**
- Generate Makefiles from project analysis
- Add common targets (test, build, clean, install)
- Plugin marketplace-specific targets
- Documentation targets
- Help text generation
- PHONY targets and dependencies

### Project Documentation

#### claude-md-setup
**Usage:** `/config-manager:claude-md-setup`

Create and maintain CLAUDE.md files with project-specific instructions for Claude.

**Features:**
- Generate CLAUDE.md from project analysis
- Include coding conventions
- Document project structure
- Add workflow guidelines
- Custom preferences (formatting, commit style, etc.)

#### docs-setup
**Usage:** `/config-manager:docs-setup`

Set up comprehensive documentation structure for your project.

**Features:**
- Create documentation directories
- Generate README templates
- Set up CONTRIBUTING.md
- Create CHANGELOG structure
- API documentation scaffolding

## Installation

```bash
/plugin install config-manager@oeid-claude-plugins
```

## Common Workflows

### Initial Project Setup

Complete setup for a new project:
```bash
# 1. Configure Claude permissions and directories
/config-manager:setup-dev-env

# 2. Create project Makefile
/config-manager:makefile-setup

# 3. Set up project-specific CLAUDE.md
/config-manager:claude-md-setup

# 4. Create documentation structure
/config-manager:docs-setup
```

### Claude Permissions Only

Just need to fix permissions:
```bash
/config-manager:claude-permissions
```

### Add Build Automation

Add or enhance Makefile:
```bash
/config-manager:makefile-setup
```

## Configuration Files

### Claude Settings
**Location:** `~/.claude/settings.local.json`

```json
{
  "permissions": {
    "bash": {
      "allowedPrompts": ["make", "git status", "npm"]
    }
  },
  "workingDirectories": [
    "/Users/username/workspace"
  ]
}
```

### Project Makefile
**Location:** `./Makefile`

```makefile
.PHONY: help test install

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

test:  ## Run tests
	pytest tests/

install:  ## Install dependencies
	npm install
```

### Claude Instructions
**Location:** `./CLAUDE.md`

Project-specific instructions for Claude Code.

## Use Cases

### Marketplace Plugin Development
1. Set up Claude permissions for `make` commands
2. Create Makefile with plugin-specific targets
3. Document plugin structure in CLAUDE.md
4. Generate plugin documentation

### Web Application Project
1. Configure npm/node permissions
2. Create Makefile for build/test/deploy
3. Set up CLAUDE.md with architecture notes
4. Generate docs for API and guides

### Open Source Project
1. Full documentation setup (README, CONTRIBUTING, etc.)
2. Makefile for common contributor tasks
3. CLAUDE.md for maintainer workflows
4. Consistent structure and conventions

## Best Practices

- **Permissions**: Use least privilege, only allow necessary commands
- **Makefiles**: Include help target, use PHONY, document each target
- **CLAUDE.md**: Keep concise, focus on unique project aspects
- **Documentation**: Start with README, keep docs current

## Security

- Only allow necessary bash commands
- Restrict to project-specific paths
- Validate JSON syntax in settings
- No credentials in config files

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
