# Marketplace Management Scripts

This directory contains helper scripts for managing the Claude plugin marketplace. The Makefile in the parent directory serves as a lite wrapper around these scripts.

## Version Management Scripts

### `detect-plugin-changes.sh`

Detects changes in a plugin since the last version bump.

**Usage:**
```bash
./detect-plugin-changes.sh <plugin-name> [since-commit]
```

**Output:** JSON with change summary and suggested version bump

**Called by:** `version-check-all.sh`

---

### `version-bump.sh`

Bumps a plugin version following semantic versioning.

**Usage:**
```bash
./version-bump.sh <plugin-name> <major|minor|patch> [--commit]
```

**Actions:**
- Updates version in plugin.json
- Records current Git commit in versionCommit field
- Optionally auto-commits the change

**Called by:** `version-check-all.sh`, Makefile `version-bump` target

---

### `version-check-all.sh`

Checks all plugins for changes and bumps versions as needed.

**Usage:**
```bash
./version-check-all.sh [--dry-run] [--auto-commit]
```

**Options:**
- `--dry-run` - Preview changes without applying
- `--auto-commit` - Auto-commit each version bump

**Called by:** Makefile `update` and `version-check` targets

---

### `plugin-update-all.sh`

Updates all installed plugins via Claude CLI.

**Usage:**
```bash
./plugin-update-all.sh
```

**Actions:**
- Runs `claude plugin update` for each plugin
- Shows progress and summary
- Handles errors gracefully

**Called by:** Makefile `update` and `update-force` targets

---

### `init-version-tracking.sh`

One-time setup to initialize version tracking.

**Usage:**
```bash
./init-version-tracking.sh
```

**Actions:**
- Adds `versionCommit` field to all plugin.json files
- Uses current Git commit SHA
- Skips plugins already initialized

**Called by:** Makefile `version-init` target (one-time setup)

---

## Plugin Management Scripts

### `register-marketplace.sh`

Registers the marketplace with Claude.

**Usage:**
```bash
./register-marketplace.sh
```

**Called by:** Makefile `register` target

---

### `install-plugin.sh`

Installs a single plugin (legacy symlink method).

**Usage:**
```bash
./install-plugin.sh <plugin-name>
```

**Called by:** Makefile `install-symlinks` target

---

### `auto-install-all.sh`

Auto-installs all plugins to ~/.claude.

**Usage:**
```bash
./auto-install-all.sh
```

**Called by:** Makefile `install-all` target

---

### `cli-install-all.sh`

Installs all plugins via Claude CLI (recommended).

**Usage:**
```bash
./cli-install-all.sh
```

**Called by:** Referenced in Makefile `install-cli` target

---

### `verify-installs.sh`

Verifies all plugins are correctly installed.

**Usage:**
```bash
./verify-installs.sh
```

**Called by:** Makefile `verify-installs` target

---

## Design Principles

All scripts follow CEG standards:

1. **Actionable Output** - Clear status indicators (✓ ✗ ⚠)
2. **Colored Output** - Uses ANSI colors for readability
3. **Error Handling** - Uses `set -euo pipefail` for safety
4. **Informative** - Shows what's happening and why
5. **Composable** - Can be called standalone or from Makefile
6. **Exit Codes** - Return meaningful exit codes

## Makefile Integration

The Makefile provides a simple interface to these scripts:

```makefile
update: ## Check for changes, bump versions, then update plugins
	@./scripts/version-check-all.sh
	@./scripts/plugin-update-all.sh

version-check: ## Check which plugins need version bumps (dry run)
	@./scripts/version-check-all.sh --dry-run

version-bump: ## Manually bump a plugin version
	@./scripts/version-bump.sh $(PLUGIN) $(TYPE) --commit
```

Users interact with `make` commands, which call these scripts.

## Adding New Scripts

When adding new scripts:

1. **Use bash** with proper shebang: `#!/usr/bin/env bash`
2. **Set safety flags:** `set -euo pipefail`
3. **Define colors** at the top
4. **Add help text** in comments
5. **Make executable:** `chmod +x script.sh`
6. **Add Makefile target** if user-facing
7. **Document here** in this README
8. **Follow naming** conventions: `noun-verb.sh` (e.g., `plugin-update.sh`)

## Testing

Test scripts individually before integrating:

```bash
# Test change detection
./scripts/detect-plugin-changes.sh claude-manager

# Test version bump (dry)
./scripts/version-check-all.sh --dry-run

# Test actual version bump
./scripts/version-bump.sh claude-manager patch

# Test plugin update
./scripts/plugin-update-all.sh
```

## Version Management Flow

```
User runs: make update
           ↓
Makefile calls: version-check-all.sh
                ↓
                For each plugin:
                  detect-plugin-changes.sh
                  ↓
                  If changes detected:
                    version-bump.sh
                ↓
Makefile calls: plugin-update-all.sh
                ↓
                For each plugin:
                  claude plugin update
```

## Maintenance

These scripts are designed to be:
- **Self-contained** - Minimal dependencies (bash, python3, git)
- **Portable** - Work on macOS and Linux
- **Maintainable** - Clear, commented, following consistent patterns
- **Extensible** - Easy to add new functionality

Keep the Makefile as a lite wrapper - put complex logic in scripts!
