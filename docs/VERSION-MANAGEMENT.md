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

Each plugin's `plugin.json` includes a `versionCommit` field that tracks the Git commit SHA when the version was last set:

```json
{
  "name": "claude-manager",
  "version": "1.1.0",
  "versionCommit": "16e0a03cf3949e4cc06dc4e0942b2096009862b7",
  ...
}
```

### Change Detection

The system recursively checks all files in a plugin directory for changes since the `versionCommit`:

- **New skills** → `MINOR` bump (1.0.0 → 1.1.0)
- **Modified skills** → `PATCH` bump (1.0.0 → 1.0.1)
- **Removed skills** → `MAJOR` bump (1.0.0 → 2.0.0) ⚠️ Breaking change
- **Metadata only** (README, plugin.json) → `PATCH` bump

### Smart Version Bumping

The system follows semantic versioning:

- **MAJOR** (x.0.0) - Breaking changes (removed functionality)
- **MINOR** (0.x.0) - New functionality (backward compatible)
- **PATCH** (0.0.x) - Bug fixes, improvements (backward compatible)

## Usage

### Quick Start: Update Everything

The simplest workflow:

```bash
make update
```

This command:
1. Checks all plugins for changes since last version
2. Auto-bumps versions as needed
3. Updates all installed plugins via Claude CLI

### Check What Would Change (Dry Run)

See what version bumps would happen without making changes:

```bash
make version-check
```

Example output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Version Check & Bump
  Mode: DRY RUN (no changes will be made)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checking: noteplan-manager
  ⚠ Changes detected:
    • 4 new skill(s)
  Current version: 1.0.0
  Suggested bump:  minor
  Would update to: 1.1.0

Checking: claude-manager
  ✓ Up to date (no changes since last version)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1 plugin(s) would be updated
  5 plugin(s) unchanged

💡 Run without --dry-run to apply version bumps
```

### Manually Bump a Specific Plugin

Override the automatic detection and manually bump a plugin:

```bash
# Minor bump (add features)
make version-bump PLUGIN=claude-manager TYPE=minor

# Patch bump (fixes)
make version-bump PLUGIN=claude-manager TYPE=patch

# Major bump (breaking changes)
make version-bump PLUGIN=claude-manager TYPE=major
```

This will:
- Update the version in plugin.json
- Set versionCommit to current Git SHA
- Auto-commit the change

### Force Update Without Version Check

If you just want to update installed plugins without checking versions:

```bash
make update-force
```

### One-Time Setup: Initialize Version Tracking

If you're setting up the system for the first time:

```bash
make version-init
```

This adds `versionCommit` fields to all plugin.json files using the current Git commit.

## The Scripts

The Makefile is a lite wrapper around helper scripts in `scripts/`:

### `scripts/detect-plugin-changes.sh`

Detects changes in a plugin since last version bump.

```bash
./scripts/detect-plugin-changes.sh <plugin-name> [since-commit]
```

Returns JSON with:
- Change summary (new/modified/removed skills)
- Suggested version bump type
- List of changed files

### `scripts/version-bump.sh`

Bumps a plugin version and updates versionCommit.

```bash
./scripts/version-bump.sh <plugin-name> <major|minor|patch> [--commit]
```

Updates plugin.json with:
- New semantic version
- Current Git commit SHA in versionCommit
- Optional auto-commit

### `scripts/version-check-all.sh`

Checks all plugins for changes and bumps versions as needed.

```bash
./scripts/version-check-all.sh [--dry-run] [--auto-commit]
```

Options:
- `--dry-run` - Show what would change without making changes
- `--auto-commit` - Auto-commit each version bump

### `scripts/plugin-update-all.sh`

Updates all installed plugins via Claude CLI.

```bash
./scripts/plugin-update-all.sh
```

Runs `claude plugin update` for each plugin in the marketplace.

### `scripts/init-version-tracking.sh`

One-time setup to add versionCommit fields to all plugins.

```bash
./scripts/init-version-tracking.sh
```

## Workflow Examples

### Adding a New Skill to a Plugin

1. **Add the skill:**
   ```bash
   mkdir -p plugins/claude-manager/skills/new-skill
   # Create SKILL.md...
   ```

2. **Check what version bump is needed:**
   ```bash
   make version-check
   # Output: "noteplan-manager: 1 new skill → minor bump to 1.2.0"
   ```

3. **Commit the new skill:**
   ```bash
   git add plugins/claude-manager/skills/new-skill
   git commit -m "Add new-skill to claude-manager"
   ```

4. **Update (auto-bumps version):**
   ```bash
   make update
   # Bumps version to 1.2.0 and updates installed plugin
   ```

### Fixing a Bug in an Existing Skill

1. **Fix the bug** in the SKILL.md file

2. **Commit the fix:**
   ```bash
   git add plugins/*/skills/*/SKILL.md
   git commit -m "Fix bug in skill"
   ```

3. **Update:**
   ```bash
   make update
   # Detects modified skill → patch bump (1.2.0 → 1.2.1)
   ```

### Removing a Skill (Breaking Change)

1. **Remove the skill:**
   ```bash
   git rm -r plugins/claude-manager/skills/old-skill
   git commit -m "Remove old-skill (breaking change)"
   ```

2. **Update:**
   ```bash
   make update
   # Detects removed skill → major bump (1.2.1 → 2.0.0) ⚠️
   ```

## Version History Mapping

The system maintains a mapping between versions and Git commits:

```
Version History for claude-manager:
  1.0.0 @ c6553a0  (Initial version)
  1.1.0 @ 16e0a03  (Added fix-plugins skill)
  1.2.0 @ ab12cd3  (Added new-skill)
  1.2.1 @ cd34ef5  (Fixed bug in new-skill)
```

This is tracked in plugin.json's `versionCommit` field. You can see the full history:

```bash
git log --oneline --all -- plugins/claude-manager/.claude-plugin/plugin.json
```

## Best Practices

### 1. Commit Before Updating

Always commit your changes before running `make update`:

```bash
git add .
git commit -m "Add new skills"
make update
```

This ensures the version bump is based on committed changes.

### 2. Use Dry Run First

Check what will change before actually updating:

```bash
make version-check  # See what would happen
make update         # Apply the changes
```

### 3. Let the System Handle Versions

Don't manually edit version numbers in plugin.json. Use:

```bash
make version-bump PLUGIN=name TYPE=minor
```

This ensures the versionCommit is properly updated.

### 4. Commit Version Bumps Separately

The system updates plugin.json files. Commit these separately:

```bash
git add plugins/*/.claude-plugin/plugin.json
git commit -m "Bump plugin versions"
```

### 5. Update Regularly

Run `make update` regularly to keep plugins in sync:

```bash
# After making changes
git commit -m "Your changes"
make update
```

## Troubleshooting

### Plugin shows as "up to date" but has uncommitted changes

The system only detects **committed** changes. Commit your work first:

```bash
git add .
git commit -m "Your changes"
make version-check  # Now it will detect the changes
```

### "No versionCommit found" warning

Your plugin needs initialization:

```bash
make version-init
```

Or manually add to plugin.json:
```json
{
  "version": "1.0.0",
  "versionCommit": "current-git-sha"
}
```

### Version bump suggestions seem wrong

You can override with a manual bump:

```bash
make version-bump PLUGIN=name TYPE=major
```

### Plugin update fails

Check if the plugin is installed:

```bash
make doctor  # Diagnose installation issues
```

## Integration with CI/CD

You can integrate version management into your CI/CD pipeline:

```yaml
# .github/workflows/publish.yml
name: Publish Plugins

on:
  push:
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Check for version updates
        run: make version-check

      - name: Bump versions if needed
        run: ./scripts/version-check-all.sh --auto-commit

      - name: Push version bumps
        run: git push origin main

      - name: Update plugins
        run: make update-force
```

## Summary

The version management system provides:

- ✅ **Automatic version bumping** based on detected changes
- ✅ **Semantic versioning** following best practices
- ✅ **Git-based tracking** of version history
- ✅ **Smart change detection** (new/modified/removed skills)
- ✅ **Dry-run capability** to preview changes
- ✅ **Manual override** when needed
- ✅ **Makefile wrapper** for simple commands

Just use `make update` and let the system handle the rest! 🚀
