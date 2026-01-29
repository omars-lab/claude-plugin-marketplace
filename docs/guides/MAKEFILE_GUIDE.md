# Makefile Guide

Complete guide to using the Makefile for managing the OEID Claude Plugin Marketplace.

## Overview

The Makefile provides convenient commands for installing, verifying, testing, and maintaining plugins in this marketplace. It's designed for both manual use and automation (CI/CD, scripts).

## Quick Reference

```bash
make help              # Show all available commands
make install-all       # Install all plugins
make verify-installs   # Verify installations succeeded
make list-plugins      # List plugins with status
make update-all        # Update all installed plugins
make validate          # Validate plugin structure
make clean             # Clean build artifacts
```

## Installation Commands

### Install All Plugins

```bash
make install-all
```

**What it does:**
- Iterates through all plugins in `plugins/` directory
- Calls `/scripts/install-plugin.sh` for each plugin
- Creates symlinks to `~/.claude/plugins/marketplaces/oeid-claude-plugins/plugins/`
- Tracks failures and reports accurate results
- Returns non-zero exit code if any installation fails

**Output:**
```
Installing all plugins from oeid-claude-plugins...
Installing claude-permission-config-manager...
✓ Successfully installed claude-permission-config-manager

Installing discover-oeid-plugins...
✓ Successfully installed discover-oeid-plugins

...

✓ All plugins installed successfully
```

**On failure:**
```
✗ 2 plugin(s) failed to install
```
Exit code: 1

### Verify Installations

```bash
make verify-installs
```

**What it does:**
- Checks each plugin directory exists in `~/.claude/plugins/marketplaces/oeid-claude-plugins/plugins/`
- Verifies `plugin.json` exists for each plugin
- Reports status of each plugin
- Returns non-zero exit code if any verification fails

**Output on success:**
```
Verifying plugin installations...

✓ claude-permission-config-manager - installed
✓ discover-oeid-plugins - installed
✓ noteplan-daily-organizer - installed
✓ noteplan-note-creator - installed
✓ noteplan-structure-analyzer - installed
✓ noteplan-templates - installed

All 6 plugins verified successfully
```

**Output on failure:**
```
Verifying plugin installations...

✓ claude-permission-config-manager - installed
✗ discover-oeid-plugins - not installed
...

2 of 6 plugins failed verification
```
Exit code: 1

### List Plugin Status

```bash
make list-plugins
```

**What it does:**
- Shows all plugins with installation status
- Displays plugin descriptions
- Checks actual installation directory, not just symlinks

**Output:**
```
📦 Plugins in oeid-claude-plugins

  ✓ installed   claude-permission-config-manager
                Manage Claude Code permissions and dev environment

  ✗ not installed   someother-plugin
                Description of the plugin
```

## Maintenance Commands

### Update All Plugins

```bash
make update-all
```

**What it does:**
- Updates marketplace metadata
- Updates only plugins that are currently installed
- Skips uninstalled plugins

### Validate Structure

```bash
make validate
```

**What it does:**
- Validates `marketplace.json` is valid JSON
- Checks each plugin has `plugin.json`
- Validates JSON syntax for all plugin configs

**Output:**
```
Validating marketplace configuration...
✓ marketplace.json is valid JSON
Checking plugin structure...
✓ claude-permission-config-manager: plugin.json valid
✓ discover-oeid-plugins: plugin.json valid
...
```

### Clean Artifacts

```bash
make clean
```

**What it does:**
- Removes Python cache files (`*.pyc`, `__pycache__`)
- Removes pytest cache
- Removes `.DS_Store` files
- Does NOT remove installed plugins

## Helper Scripts

The Makefile uses shell scripts in `/scripts/` for core operations:

### install-plugin.sh

**Usage:**
```bash
./scripts/install-plugin.sh <plugin-name>
```

**What it does:**
1. Validates plugin exists in `plugins/` directory
2. Checks for required `plugin.json`
3. Creates marketplace directory structure if needed
4. Copies `marketplace.json` to install location if needed
5. Creates symlink from source to install location
6. Returns exit code 0 on success, 1 on failure

**Example:**
```bash
./scripts/install-plugin.sh noteplan-templates
# Output: ✓ Successfully installed noteplan-templates
```

### verify-installs.sh

**Usage:**
```bash
./scripts/verify-installs.sh
```

**What it does:**
1. Checks each plugin in `plugins/` directory
2. Verifies installation directory exists
3. Verifies `plugin.json` exists in installation
4. Reports status for each plugin
5. Returns exit code 0 if all pass, 1 if any fail

**Exit codes:**
- `0`: All plugins verified successfully
- `1`: One or more plugins failed verification

## Testing Commands

### Test All Plugins

```bash
make test-all
```

Shows available skills for all plugins. Useful for verifying plugin structure and skill definitions.

### Test Individual Plugins

```bash
make test-discover       # Test discover-oeid-plugins
make test-config-manager # Test claude-permission-config-manager
make test-templates      # Test noteplan-templates
make test-organizer      # Test noteplan-daily-organizer
make test-analyzer       # Test noteplan-structure-analyzer
make test-creator        # Test noteplan-note-creator
```

## Automation & CI Usage

### Non-Interactive Verification

The verification script is designed for CI/CD and automation:

```bash
#!/bin/bash
# In a CI script

# Install plugins
if make install-all; then
    echo "Installation succeeded"
else
    echo "Installation failed"
    exit 1
fi

# Verify installations
if make verify-installs; then
    echo "Verification passed"
else
    echo "Verification failed"
    exit 1
fi
```

### Checking Individual Plugin Status

```bash
# Check if a specific plugin is installed
if [ -d "$HOME/.claude/plugins/marketplaces/oeid-claude-plugins/plugins/noteplan-templates" ]; then
    echo "noteplan-templates is installed"
else
    echo "noteplan-templates is NOT installed"
fi
```

### Scripted Installation

```bash
# Install specific plugins only
./scripts/install-plugin.sh noteplan-templates
./scripts/install-plugin.sh noteplan-daily-organizer

# Verify those specific installations
./scripts/verify-installs.sh
```

## Troubleshooting

### Installation Fails Silently

**Problem:** Installation appears to succeed but plugins don't work

**Solution:** Run verification
```bash
make verify-installs
```

### Symlinks vs. Copies

The installation uses **symlinks** by default. This means:
- Changes to source plugins immediately affect installed plugins
- Development workflow is easier (no reinstall needed)
- You must not move the marketplace directory after installation

To check symlinks:
```bash
ls -la ~/.claude/plugins/marketplaces/oeid-claude-plugins/plugins/
```

### Permission Denied

**Problem:** `make install-all` fails with permission errors

**Solution:** Ensure you have write access to `~/.claude/plugins/`
```bash
ls -la ~/.claude/plugins/
chmod -R u+w ~/.claude/plugins/
```

### Plugin Not Found After Installation

**Problem:** Plugin installs but Claude Code doesn't see it

**Solution:**
1. Verify installation: `make verify-installs`
2. Check Claude Code sees the marketplace: `/plugin marketplace list`
3. Update marketplace: `/plugin marketplace update`
4. Restart Claude Code session

### Make Command Not Found

**Problem:** `make: command not found`

**Solution:** Install make (usually comes with Xcode Command Line Tools on macOS)
```bash
xcode-select --install
```

## Directory Structure

Understanding where things go:

```
Marketplace Source:
/path/to/oeid-claude-plugin-marketplace/
├── plugins/
│   ├── noteplan-templates/
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   └── skills/
│   └── ...

Installation Target:
~/.claude/plugins/marketplaces/oeid-claude-plugins/
├── marketplace.json
└── plugins/
    ├── noteplan-templates -> /path/to/source/plugins/noteplan-templates/
    └── ...
```

## Best Practices

### Development Workflow

1. Make changes to plugin in source directory
2. Changes are immediately available (symlinked)
3. No reinstall needed
4. Periodically verify: `make verify-installs`

### Before Committing

```bash
make validate        # Ensure configs are valid
make clean          # Remove build artifacts
make verify-installs # Ensure your setup is clean
```

### Setting Up New Environment

```bash
cd /path/to/oeid-claude-plugin-marketplace
make install-all    # Install all plugins
make verify-installs # Verify everything worked
make list-plugins   # See what's installed
```

### Continuous Integration

```yaml
# Example GitHub Actions
- name: Install plugins
  run: make install-all

- name: Verify installations
  run: make verify-installs

- name: Validate structure
  run: make validate
```

## Advanced Usage

### Parallel Installation

The Makefile installs plugins sequentially. For parallel installation:

```bash
# Manual parallel installation (use with caution)
for plugin in plugins/*/; do
    plugin_name=$(basename "$plugin")
    ./scripts/install-plugin.sh "$plugin_name" &
done
wait
make verify-installs
```

### Selective Installation

Install only specific plugins:

```bash
./scripts/install-plugin.sh noteplan-templates
./scripts/install-plugin.sh noteplan-daily-organizer
```

### Force Reinstall

```bash
# Remove installation
rm -rf ~/.claude/plugins/marketplaces/oeid-claude-plugins/

# Reinstall
make install-all
```

## Environment Variables

Currently no environment variables are used, but installation paths are:

- **Source**: `$(pwd)` (current directory)
- **Target**: `$HOME/.claude/plugins/marketplaces/oeid-claude-plugins/`
- **Marketplace name**: `oeid-claude-plugins` (hardcoded in Makefile)

## See Also

- [Quick Start Guide](../getting-started/QUICK_START.md)
- [Installation Guide](INSTALLATION.md) *(if it exists)*
- Individual plugin documentation in `plugins/*/README.md`
