---
name: fix-plugins
description: Detect version drift between source and installed plugins, auto-bump versions if needed, run make update, and verify
---

# Fix Plugins

You are a Claude plugin marketplace updater. When this skill is invoked, you'll analyze one or more Claude plugin marketplaces to detect version drift, auto-bump versions if needed, and run the appropriate Makefile targets to update them.

## What This Skill Does

This skill:
1. **Confirms marketplace paths** (via AskUserQuestion — Step 0)
2. **Analyzes each marketplace** for plugins needing updates
3. **Compares source vs installed versions** for each plugin
4. **Detects plugins that need updates**
5. **Runs appropriate Makefile update commands**
6. **Reports update results**

## Task Management (MANDATORY)

```javascript
TaskCreate({ subject: "Confirm marketplace paths", description: "Ask user which marketplace(s) to update", activeForm: "Confirming scope" })
TaskCreate({ subject: "Check versions", description: "Compare source vs installed versions for each plugin", activeForm: "Checking versions" })
TaskCreate({ subject: "Auto-bump and update", description: "Bump versions for plugins with new skills, run make update", activeForm: "Running updates" })
TaskCreate({ subject: "Verify updates", description: "Check new skills are now in cache", activeForm: "Verifying updates" })
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
TaskUpdate({ taskId: "3", addBlockedBy: ["2"] })
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })
```

## Step 0: Confirm Marketplace Paths (MANDATORY FIRST STEP)

Before doing any analysis, use `AskUserQuestion` to confirm the marketplace path and ask if additional marketplaces should be analyzed.

**Determine the default OEID marketplace path:**
```bash
# Resolve from git root of the current repo
git rev-parse --show-toplevel
```

Then ask:

```
Which marketplace(s) should I analyze?

Default: <git-root-path> (oeid-claude-plugins)

Options:
- Just the default OEID marketplace
- Add another marketplace (provide path)
- I'll specify all paths
```

Only proceed once the user confirms the marketplace path(s).

## Marketplaces to Monitor

### Default: OEID Claude Plugins Marketplace
**Source:** Resolved dynamically from `git rev-parse --show-toplevel`
**Marketplace name:** Read from `.claude-plugin/marketplace.json` → `name` field
**Update command:** `make update` (uses `./scripts/cli` under the hood)

## How It Works

### Step 1: Check Marketplace Registration

Verify each confirmed marketplace is registered with Claude:

```bash
cat ~/.claude/plugins/known_marketplaces.json | python3 -m json.tool
```

Expected (example):
```json
{
  "oeid-claude-plugins": {
    "source": {...},
    "installLocation": "/path/to/oeid-claude-plugin-marketplace"
  }
}
```

### Step 2: Compare Source vs Installed

For each marketplace, compare:

**Source plugins:**
```bash
# List source plugins (use confirmed marketplace path)
ls -1 /path/to/marketplace/plugins/
```

**Installed plugins:**
```bash
# Check installed plugins
cat ~/.claude/plugins/installed_plugins.json | python3 -m json.tool
```

### Step 3: Check for Source Changes

For each installed plugin, check if source has been modified:

**Method 1: Compare modification times**
```bash
# Get source last modified time
find /path/to/marketplace/plugins/plugin-name -type f -name "*.md" -newer ~/.claude/plugins/cache/marketplace/plugin-name

# If files found → plugin needs update
```

**Method 2: Compare file counts**
```bash
# Count skills in source
ls -1 /path/to/marketplace/plugins/plugin-name/skills/ | wc -l

# Count skills in cache
ls -1 ~/.claude/plugins/cache/marketplace/plugin-name/*/skills/ | wc -l

# If different → plugin needs update
```

**Method 3: Check specific files**
```bash
# For plugins with new skills, check if they exist in cache
ls ~/.claude/plugins/cache/oeid-claude-plugins/noteplan-manager/1.0.0/skills/fix-plugins/

# If missing → plugin needs update
```

### Step 4: Detect Which Plugins Need Updates

Build a list of plugins that need updates:

```
Analysis Results:

OEID Marketplace (oeid-claude-plugins):
✅ discover-oeid-plugins - Up to date
⚠️  noteplan-manager - Needs update (4 new skills)
✅ claude-manager - Up to date
✅ noteplan-templates - Up to date

Additional marketplaces (if any were specified):
✅ plugin-a - Up to date
✅ plugin-b - Up to date
✅ note-manager - Up to date

Plugins needing updates: 1
- noteplan-manager@oeid-claude-plugins
```

### Step 5: Run Update Commands

For each marketplace with plugins needing updates, run `make update` from the confirmed marketplace directory:

```bash
cd /path/to/marketplace
make update
```

### Step 6: Verify Updates

After running updates, verify:

```bash
# Check if new skills are now in cache
ls -la ~/.claude/plugins/cache/oeid-claude-plugins/noteplan-manager/*/skills/

# Expected: New skills should now be present
```

## Workflow

When invoked:

1. **Step 0: Confirm marketplace paths** (AskUserQuestion — see above)

2. **Check prerequisites:**
   ```
   Checking Claude plugin marketplaces...

   ✅ OEID marketplace registered
   ```

3. **Analyze marketplaces:**
   ```
   Analyzing OEID marketplace...
   - Checking N plugins
   - Comparing source vs installed
   ```

3. **Report findings:**
   ```
   📊 Analysis Complete

   OEID Marketplace (oeid-claude-plugins):
   ⚠️  noteplan-manager
       Source: /path/to/oeid-claude-plugin-marketplace/plugins/noteplan-manager
       Installed: ~/.claude/plugins/cache/oeid-claude-plugins/noteplan-manager/1.0.0
       Issue: Source has 4 new skills not in cache
       New skills:
         - fix-work-emojis
         - fix-personal-emojis
         - sync-header-emojis
         - sync-plan-templates

   Additional marketplaces:
   ✅ All plugins up to date (if applicable)

   Total plugins needing updates: 1
   ```

4. **Ask for confirmation:**
   ```
   Update plugins? (yes/no/specific)

   Options:
   - yes: Update all plugins that need it
   - no: Cancel
   - specific: Choose which to update
   ```

5. **Run updates:**
   ```
   Updating OEID marketplace plugins...

   Running: cd /path/to/oeid-claude-plugin-marketplace && make update

   [Shows make output...]

   ✅ OEID marketplace updated
   ```

6. **Verify results:**
   ```
   Verifying updates...

   ✅ noteplan-manager@oeid-claude-plugins
      - fix-work-emojis now available
      - fix-personal-emojis now available
      - sync-header-emojis now available
      - sync-plan-templates now available

   Update complete! Restart Claude to use new skills.
   ```

## Detection Logic

### How to Detect Updates Needed

**Priority 1: Check for new skills**
```bash
# Compare skill counts
source_skills=$(ls -1 /path/to/source/plugin/skills/ | wc -l)
installed_skills=$(ls -1 ~/.claude/plugins/cache/marketplace/plugin/*/skills/ | wc -l)

if [ $source_skills -gt $installed_skills ]; then
    echo "Plugin needs update: new skills added"
fi
```

**Priority 2: Check modification times**
```bash
# Find files in source newer than installed version
newer_files=$(find /path/to/source/plugin -type f -newer ~/.claude/plugins/cache/marketplace/plugin -print)

if [ -n "$newer_files" ]; then
    echo "Plugin needs update: files modified"
fi
```

**Priority 3: Check version numbers**
```bash
# Compare version in plugin.json
source_version=$(jq -r '.version' /path/to/source/plugin/.claude-plugin/plugin.json)
installed_version=$(jq -r '.version' ~/.claude/plugins/cache/marketplace/plugin/*/plugin.json)

if [ "$source_version" != "$installed_version" ]; then
    echo "Plugin needs update: version mismatch"
fi
```

## Smart Features

### 1. Auto-detect New Skills

Automatically detect when new skills are added:

```
Scanning noteplan-manager...

Source skills (16):
- analyze-structure
- create-note
- create-template
- fix-personal-emojis    ⭐ NEW
- fix-reference
- fix-work-emojis        ⭐ NEW
- list-templates
- manage-templates
- move-content
- organize-daily
- quick-note
- suggest-improvements
- sync-header-emojis     ⭐ NEW
- sync-plan-templates    ⭐ NEW

Installed skills (12):
- analyze-structure
- create-note
- create-template
- fix-reference
- list-templates
- manage-templates
- move-content
- organize-daily
- quick-note
- suggest-improvements

Missing 4 new skills → Update needed
```

### 2. Detect Modified Skills

Check if existing skills have been modified:

```
Checking for modified skills...

fix-reference/SKILL.md
  Source modified: 2025-02-16 21:40
  Installed: 2025-02-15 23:40
  ⚠️  Source is newer → Update needed
```

### 3. Batch Updates

If multiple marketplaces need updates, batch them:

```
Found updates needed in N marketplaces:
- oeid-claude-plugins (1 plugin)
- additional-marketplace (2 plugins)  [if applicable]

Run batch update? (yes/no)

If yes:
  cd /path/to/oeid-marketplace && make update
  cd /path/to/additional-marketplace && make update  [if applicable]
```

### 4. Selective Updates

Allow updating specific plugins:

```
Which plugins should I update?

1. All plugins (recommended)
2. Only the default marketplace
3. Only additional marketplaces (if applicable)
4. Specific plugins by name

Choose option (1-4):
```

## Example Run

```bash
/claude-manager:fix-plugins

# Analysis starts
Analyzing Claude plugin marketplaces...

📂 OEID Marketplace: /path/to/oeid-claude-plugin-marketplace
   Registered: ✅
   Plugins: 7

📂 Additional Marketplace: /path/to/additional-marketplace (if specified)
   Registered: ✅
   Plugins: N

Checking for updates...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 OEID Marketplace Analysis:

✅ discover-oeid-plugins - Up to date
⚠️  noteplan-manager - UPDATE NEEDED
    Reason: 4 new skills found
    New skills:
      • fix-work-emojis
      • fix-personal-emojis
      • sync-header-emojis
      • sync-plan-templates

✅ claude-manager - Up to date (analyzing with this skill!)
✅ noteplan-templates - Up to date
✅ noteplan-daily-organizer - Up to date
✅ noteplan-structure-analyzer - Up to date
✅ noteplan-note-creator - Up to date

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 CEG Marketplace Analysis:

✅ All plugins up to date

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
- 12 plugins total
- 11 up to date
- 1 needs update

Update noteplan-manager@oeid-claude-plugins? (yes/no)

# User types: yes

Updating OEID marketplace...
Running: cd /path/to/oeid-claude-plugin-marketplace && make update

[Make output shows...]
Updating noteplan-manager@oeid-claude-plugins...
✓ noteplan-manager updated successfully

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verifying updates...

Checking noteplan-manager skills...
✅ fix-work-emojis - Now available
✅ fix-personal-emojis - Now available
✅ sync-header-emojis - Now available
✅ sync-plan-templates - Now available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 Update complete!

All plugins are now up to date.
New skills are available in noteplan-manager.

💡 Tip: Restart Claude to ensure all changes take effect.
```

## Safety Features

- ✅ **Check before updating** - Always ask for confirmation
- ✅ **Show what will change** - List new/modified skills
- ✅ **Dry run option** - Preview updates without applying
- ✅ **Rollback info** - Show how to revert if needed
- ✅ **Marketplace verification** - Ensure marketplaces are registered

## Advanced Options

```bash
# Dry run (show what would update, don't apply)
/claude-manager:fix-plugins --dry-run

# Update specific marketplace
/claude-manager:fix-plugins --marketplace oeid-claude-plugins

# Force update all
/claude-manager:fix-plugins --force

# Quiet mode (less output)
/claude-manager:fix-plugins --quiet
```

## Troubleshooting

### Issue: Marketplace not registered

```
❌ oeid-claude-plugins marketplace not registered

Fix:
1. Register marketplace:
   /plugin marketplace add /path/to/oeid-claude-plugin-marketplace

2. Re-run this skill
```

### Issue: Plugin not installed

```
⚠️  noteplan-manager is in source but not installed

Fix:
1. Install plugin:
   cd /path/to/oeid-claude-plugin-marketplace && make install

2. Re-run this skill
```

### Issue: Update command fails

```
❌ make update failed for oeid-claude-plugins

Trying alternative: Direct CLI update
Running: claude plugin update noteplan-manager@oeid-claude-plugins

[Shows CLI output...]
```

## Integration with Makefiles

This skill uses the existing Makefile commands:

**OEID Makefile (`make update`):**
```bash
update: ## Update all installed plugins using Claude CLI (non-interactive)
	@echo "Updating all plugins from $(MARKETPLACE_NAME) using Claude CLI..."
	@plugins=$$(python3 -c "import json; data=json.load(open('.claude-plugin/marketplace.json')); print(' '.join([p['name'] for p in data['plugins']]))"); \
	for plugin in $$plugins; do \
		echo "Updating $$plugin@$(MARKETPLACE_NAME)..."; \
		env -u CLAUDECODE claude plugin update "$$plugin@$(MARKETPLACE_NAME)" --scope user; \
	done
```

**CEG Makefile (`make update`):**
```bash
update: ## Update all installed plugins using Claude CLI (non-interactive)
	@echo "Updating all plugins from $(MARKETPLACE_NAME) using Claude CLI..."
	[Similar implementation]
```

## Related Skills

- **claude-manager:doctor** - Diagnose Claude plugin issues
- **noteplan-manager:fix-*-emojis** - The skills that triggered this need
- **discover-*-plugins:explore-plugins** - See what's installed

## Maintenance Schedule

Run this skill:
- **After adding new skills** to any plugin
- **Weekly** to catch any updates
- **Before important work** to ensure all tools available
- **After marketplace changes** to sync updates

## Quick Command

For quick updates without analysis:

```bash
# Update each confirmed marketplace
cd /path/to/oeid-claude-plugin-marketplace && make update
```

But use this skill for **smart analysis** of what actually needs updating!

---

## 🔍 CRITICAL: Version Bump Detection

**THE PROBLEM:** Claude's `plugin update` command checks version numbers. If the version hasn't changed, it won't reinstall even if you added new skills!

### Detection Strategy

**Step 1: List Actually Installed Plugins**
```bash
# Use env -u to avoid nested session error
env -u CLAUDECODE claude plugin list
```

**Step 2: Compare Source vs Installed Versions**
```bash
# Source version
source_version=$(cat /path/to/plugin/.claude-plugin/plugin.json | jq -r '.version')

# Installed version
installed_version=$(cat ~/.claude/plugins/cache/marketplace/plugin/*/plugin.json | jq -r '.version')

if [ "$source_version" == "$installed_version" ]; then
    echo "⚠️  VERSION NOT BUMPED - update will skip this plugin!"
fi
```

**Step 3: Check Skill Counts**
```bash
# Count skills in source
source_skills=$(ls -1 /path/to/source/plugin/skills/ | wc -l)

# Count skills in installed
installed_skills=$(ls -1 ~/.claude/plugins/cache/marketplace/plugin/*/skills/ | wc -l)

if [ $source_skills -gt $installed_skills ] && [ "$source_version" == "$installed_version" ]; then
    echo "❌ CRITICAL: New skills added but version not bumped!"
    echo "   Claude update will NOT install new skills"
    echo "   Must bump version from $source_version to next version"
fi
```

### Auto-Fix Version Bumps

When new skills detected but version unchanged:

```
⚠️  CRITICAL ISSUE DETECTED:

noteplan-manager has 4 new skills but version not bumped!

Source: 16 skills, version 1.0.0
Installed: 12 skills, version 1.0.0

Claude update command will skip because version is same.

Fix options:
1. Auto-bump to 1.1.0 (recommended - minor version for new features)
2. Auto-bump to 2.0.0 (if breaking changes)
3. Force reinstall (uninstall + install)
4. Manual fix

Choose fix (1-4):
```

### Version Bump Rules

Following semantic versioning:

- **Patch (1.0.0 → 1.0.1):** Bug fixes only
- **Minor (1.0.0 → 1.1.0):** New skills added (backwards compatible)
- **Major (1.0.0 → 2.0.0):** Breaking changes to skill APIs

### Auto-Bump Implementation

```bash
auto_bump_version() {
    local plugin_json="$1"
    local current_version=$(jq -r '.version' "$plugin_json")
    
    # Parse version
    IFS='.' read -r major minor patch <<< "$current_version"
    
    # Bump minor version for new skills
    new_minor=$((minor + 1))
    new_version="$major.$new_minor.0"
    
    # Update plugin.json
    jq --arg ver "$new_version" '.version = $ver' "$plugin_json" > tmp.json
    mv tmp.json "$plugin_json"
    
    echo "✅ Bumped version: $current_version → $new_version"
}
```

### Complete Check Workflow

```
Running enhanced version detection...

1. Listing installed plugins...
   env -u CLAUDECODE claude plugin list

2. Comparing versions for each plugin...

   noteplan-manager@oeid-claude-plugins:
   ├─ Source version: 1.0.0
   ├─ Installed version: 1.0.0
   ├─ Source skills: 16
   ├─ Installed skills: 12
   └─ ❌ VERSION BUMP NEEDED!

   claude-manager@oeid-claude-plugins:
   ├─ Source version: 1.0.0
   ├─ Installed version: 1.0.0
   ├─ Source skills: 5
   ├─ Installed skills: 4
   └─ ❌ VERSION BUMP NEEDED!

3. Auto-fixing version issues...

   Bumping noteplan-manager: 1.0.0 → 1.1.0
   Reason: Added 4 new skills (minor version bump)
   ✅ Updated plugin.json

   Bumping claude-manager: 1.0.0 → 1.1.0
   Reason: Added 1 new skill (minor version bump)
   ✅ Updated plugin.json

4. Now running update with correct versions...
   cd /path/to/oeid-claude-plugin-marketplace && make update

5. Verifying new skills are installed...
   ✅ All new skills now available!
```

### Enhanced Detection Logic

```python
def detect_version_issues(marketplace_path, marketplace_name):
    issues = []
    
    # Get all plugins from source
    source_plugins = get_source_plugins(marketplace_path)
    
    # Get installed plugins
    installed_plugins = get_installed_plugins(marketplace_name)
    
    for plugin_name in source_plugins:
        source = source_plugins[plugin_name]
        installed = installed_plugins.get(plugin_name)
        
        if not installed:
            issues.append({
                'type': 'NOT_INSTALLED',
                'plugin': plugin_name,
                'fix': 'Run make install or install plugin'
            })
            continue
        
        # Compare versions
        if source['version'] == installed['version']:
            # Check if skills changed
            if source['skill_count'] != installed['skill_count']:
                issues.append({
                    'type': 'VERSION_NOT_BUMPED',
                    'plugin': plugin_name,
                    'current_version': source['version'],
                    'source_skills': source['skill_count'],
                    'installed_skills': installed['skill_count'],
                    'fix': 'Bump version to trigger update',
                    'suggested_version': bump_minor(source['version'])
                })
            
            # Check if files modified
            if source['last_modified'] > installed['install_time']:
                issues.append({
                    'type': 'FILES_MODIFIED_VERSION_SAME',
                    'plugin': plugin_name,
                    'fix': 'Bump version or force reinstall'
                })
        
        elif version_compare(source['version'], installed['version']) < 0:
            issues.append({
                'type': 'SOURCE_OLDER_THAN_INSTALLED',
                'plugin': plugin_name,
                'warning': 'Source version older than installed!',
                'source_version': source['version'],
                'installed_version': installed['version']
            })
    
    return issues
```

### Force Reinstall Option

If version bumping is not desired, offer force reinstall:

```bash
# Uninstall plugin
env -u CLAUDECODE claude plugin uninstall noteplan-manager@oeid-claude-plugins --scope user

# Install plugin (fresh)
env -u CLAUDECODE claude plugin install noteplan-manager@oeid-claude-plugins --scope user

# This forces a complete reinstall regardless of version
```

### Summary Output

```
═══════════════════════════════════════════════════════════════════════════════
                         Version Check Complete
═══════════════════════════════════════════════════════════════════════════════

Issues Found: 2

1. noteplan-manager@oeid-claude-plugins
   Problem: New skills added but version not bumped
   Current: 1.0.0 (12 skills installed)
   Source: 1.0.0 (16 skills available)
   Fix Applied: Bumped to 1.1.0
   New Skills:
     • fix-work-emojis
     • fix-personal-emojis
     • sync-header-emojis
     • sync-plan-templates

2. claude-manager@oeid-claude-plugins
   Problem: New skill added but version not bumped
   Current: 1.0.0 (4 skills installed)
   Source: 1.0.0 (5 skills available)
   Fix Applied: Bumped to 1.1.0
   New Skill:
     • fix-plugins

═══════════════════════════════════════════════════════════════════════════════

Next: Running make update with corrected versions...
```


---

## Related Skills

- **evaluate-skill** — Compliance audit + quality scoring (run this to find what needs fixing before or after updating)
- **suggest-plugin-maturity** — Optional suggestions for usage tracking, knowledge artifacts, feedback loops

