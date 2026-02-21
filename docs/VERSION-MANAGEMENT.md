# Intelligent Version Management System

This marketplace includes an intelligent version management system that automatically detects changes in plugins and bumps versions according to semantic versioning principles.

## Overview

The version management system:

1. **Tracks changes** since the last version bump using Git history
2. **Analyzes changes** to determine the appropriate version bump (major/minor/patch)
3. **Auto-bumps versions** based on detected changes
4. **Updates plugins** via Claude CLI

## How It Works

### Version Tracking

Each plugin has a `.claude-plugin/version-tracking.json` file that tracks the Git commit SHA when the version was last set. This is kept separate from `plugin.json` to avoid conflicts with Claude's plugin schema validator.

```
plugins/my-plugin/.claude-plugin/
  plugin.json              # Version number + plugin metadata (schema-validated)
  version-tracking.json    # {"versionCommit": "abc123..."} (internal tracking)
```

### Change Detection

The system checks all files in a plugin directory for changes since the tracked commit:

- **New skills** -> `MINOR` bump (1.0.0 -> 1.1.0)
- **Modified skills** -> `PATCH` bump (1.0.0 -> 1.0.1)
- **Removed skills** -> `MAJOR` bump (1.0.0 -> 2.0.0) -- Breaking change
- **Metadata only** (README, plugin.json) -> `PATCH` bump

### Smart Version Bumping

The system follows semantic versioning:

- **MAJOR** (x.0.0) - Breaking changes (removed functionality)
- **MINOR** (0.x.0) - New functionality (backward compatible)
- **PATCH** (0.0.x) - Bug fixes, improvements (backward compatible)

## Usage

All commands work via `./scripts/cli`, with `make` targets as convenient wrappers.

### Quick Start: Update Everything

```bash
make update
# or directly:
./scripts/cli version-check <marketplace-name>
./scripts/cli update <marketplace-name>
```

This:
1. Checks all plugins for changes since last version
2. Auto-bumps versions as needed
3. Updates all installed plugins via Claude CLI

### Check What Would Change (Dry Run)

```bash
make version-check
# or:
./scripts/cli version-check <marketplace-name> --dry-run
```

### Manually Bump a Specific Plugin

```bash
make version-bump PLUGIN=my-plugin TYPE=minor
# or:
./scripts/cli version-bump <marketplace-name> my-plugin minor --commit
```

This will:
- Update the version in plugin.json
- Write the current Git SHA to version-tracking.json
- Auto-commit the change

### Force Update Without Version Check

```bash
make update-force
# or:
./scripts/cli update <marketplace-name>
```

### One-Time Setup: Initialize Version Tracking

```bash
make version-init
# or:
./scripts/cli version-init <marketplace-name>
```

This creates `version-tracking.json` files for all plugins using the current Git commit. If any plugins have a legacy `versionCommit` field in `plugin.json`, it will be migrated to the tracking file automatically.

## Local Scripts

All version management logic lives in `scripts/cli` at the repo root:

```bash
./scripts/cli version-check   # Detect changes in all plugins since last version bump
./scripts/cli version-bump    # Bump a plugin version and update tracking
./scripts/cli version-init    # Initialize or migrate version tracking
./scripts/cli verify          # Verify installed vs source versions
```

## Workflow Examples

### Adding a New Skill to a Plugin

1. Add the skill files
2. Commit: `git add . && git commit -m "Add new skill"`
3. Check: `make version-check` (shows minor bump)
4. Apply: `make update` (bumps version, updates installed plugin)

### Fixing a Bug in an Existing Skill

1. Fix the SKILL.md file
2. Commit the fix
3. Run `make update` (detects modified skill -> patch bump)

### Removing a Skill (Breaking Change)

1. Remove: `git rm -r plugins/my-plugin/skills/old-skill`
2. Commit
3. Run `make update` (detects removed skill -> major bump)

## Best Practices

1. **Commit before updating** -- The system only detects committed changes
2. **Use dry run first** -- `make version-check` before `make update`
3. **Let the system handle versions** -- Use `make version-bump` instead of editing plugin.json
4. **Update regularly** -- Run `make update` after making changes

## Troubleshooting

### Plugin shows as "up to date" but has uncommitted changes

Commit your work first. The system only detects committed changes.

### "No version tracking found" warning

Run `make version-init` to initialize tracking for all plugins.

### Version bump suggestions seem wrong

Override with a manual bump: `make version-bump PLUGIN=name TYPE=major`

### Plugin update fails

Run `make doctor` to diagnose installation issues.
