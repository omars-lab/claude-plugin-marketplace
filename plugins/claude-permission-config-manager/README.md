# Claude Permission Config Manager

Manage Claude Code permissions and working directories for marketplace development.

## Overview

This plugin helps you configure Claude Code settings to eliminate permission prompts for common bash commands and directories. Perfect for marketplace plugin development and NotePlan workflows.

## Skills

### manage-permissions

**Usage:** `/claude-permission-config-manager:manage-permissions`

Manage bash command permissions in Claude settings:
- Add/remove allowed bash commands
- Review current permissions
- Get recommendations for workflow-specific permissions
- Validate settings.local.json structure

**Common Permissions:**
- Marketplace development: `make`, `tree`, `ln`, `python3 -m json.tool`
- Git operations: `git status`, `git commit`, `git push`, `gh`
- Package management: `npm`, `node`
- File operations: `ls`, `find`, `grep`

### setup-working-dirs

**Usage:** `/claude-permission-config-manager:setup-working-dirs`

Configure working directories so Claude can access your projects without prompts:
- Add workspace directories
- Configure marketplace paths
- Set up NotePlan access
- Remove unnecessary directories
- Validate directory configurations

**Common Directories:**
- Workspace: `/Users/omar.eid/workspace`
- OneDrive workspace: `/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace`
- Marketplace: `/...workspace/oeid-claude-plugin-marketplace`
- NotePlan: `/...co.noteplan.NotePlan3/Data/Library/Application Support/...`

### setup-dev-env

**Usage:** `/claude-permission-config-manager:setup-dev-env`

Complete development environment setup in one command:
- Combines permissions + working directories
- Preset configurations (Minimal, Standard, Advanced)
- Interactive setup wizard
- Validates and tests configuration

**Presets:**
- **Minimal**: Essential commands and marketplace directory
- **Standard** (Recommended): Full marketplace development setup
- **Advanced**: Everything including NotePlan and multiple workspaces

## Features

- **No More Prompts**: Set up permissions once, work freely
- **Simple Configuration**: Easy-to-understand JSON settings
- **Security Focused**: Only allows what you explicitly approve
- **Validation**: Ensures correct JSON syntax
- **Interactive**: Guides you through setup
- **Context-Aware**: Recommends based on your workflow

## Configuration File

**Settings Location:** `~/.claude/settings.local.json`

Example configuration:
```json
{
  "permissions": {
    "bash": {
      "allowedPrompts": [
        "make",
        "tree",
        "git status",
        "git commit"
      ]
    }
  },
  "workingDirectories": [
    "/Users/omar.eid/workspace",
    "/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace"
  ]
}
```

## Installation

```bash
/plugin install claude-permission-config-manager@oeid-claude-plugins
```

## Use Cases

### Initial Marketplace Setup

Configure everything for marketplace development:
```bash
/claude-permission-config-manager:setup-dev-env
```

Choose "Standard Setup" for:
- Make commands for testing (`make help`, `make validate`)
- Git operations for version control
- JSON validation tools
- Tree for viewing structure
- Access to marketplace directories

### Adding Specific Commands

Need to add specific bash commands:
```bash
/claude-permission-config-manager:manage-permissions
```

Example: "Add docker and npm permissions"

### Configure Directory Access

Set up working directories to avoid prompts:
```bash
/claude-permission-config-manager:setup-working-dirs
```

Example: "Add my NotePlan directory and marketplace path"

## Common Workflows

### First Time Setup

1. Run `/claude-permission-config-manager:setup-dev-env`
2. Choose "Standard Setup"
3. Confirm working directories
4. Test with `make help` in marketplace

### Adding Commands

1. Run `/claude-permission-config-manager:manage-permissions`
2. Specify commands needed (e.g., "npm, node")
3. Review and apply changes
4. Test commands work without prompts

### Adding Directories

1. Run `/claude-permission-config-manager:setup-working-dirs`
2. Specify directory paths
3. Verify paths exist
4. Test access without prompts

## Security Best Practices

This plugin follows security best practices:

1. **Least Privilege**: Only allow commands actually needed
2. **Specific Commands**: Prefer "git status" over just "git"
3. **No Wildcards**: No "*" or overly broad patterns
4. **Explicit Directories**: Only add directories you use
5. **Regular Review**: Audit permissions periodically
6. **Validation**: Ensure JSON syntax is correct

## Example Configurations

### Marketplace Development Only

```json
{
  "permissions": {
    "bash": {
      "allowedPrompts": ["make", "tree", "ln", "python3 -m json.tool", "git status", "git commit"]
    }
  },
  "workingDirectories": [
    "/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace"
  ]
}
```

### Marketplace + NotePlan

```json
{
  "permissions": {
    "bash": {
      "allowedPrompts": ["make", "tree", "git status", "git commit", "find", "grep"]
    }
  },
  "workingDirectories": [
    "/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace",
    "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
  ]
}
```

### Full Development Environment

```json
{
  "permissions": {
    "bash": {
      "allowedPrompts": [
        "make", "tree", "ln", "python3 -m json.tool",
        "git status", "git add", "git commit", "git push", "git diff", "gh",
        "npm", "node", "ls", "find", "grep"
      ]
    }
  },
  "workingDirectories": [
    "/Users/omar.eid/workspace",
    "/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace",
    "/Users/omar.eid/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"
  ]
}
```

## Troubleshooting

### Commands Not Working

1. Check settings.local.json syntax: `python3 -m json.tool ~/.claude/settings.local.json`
2. Verify command is in allowedPrompts
3. Restart Claude Code
4. Check that tool is installed on system

### Directory Access Denied

1. Verify directory path in workingDirectories
2. Check directory exists and has proper permissions
3. Restart Claude Code
4. Try absolute path instead of ~

### JSON Syntax Errors

Run validation:
```bash
python3 -m json.tool ~/.claude/settings.local.json
```

Or use the manage-permissions skill to fix automatically.

## What This Plugin Does NOT Do

- ❌ No MCP server configuration (use local tools instead)
- ❌ No GitHub/database/cloud integrations
- ❌ No external service configurations

This plugin is focused on **local permissions management only**: bash commands and working directories.

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
