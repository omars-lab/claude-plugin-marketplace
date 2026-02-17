---
name: fix-plugins
description: Analyze both Claude plugin marketplaces (oeid and ceg) to determine which plugins need updates and run proper update targets
---

# Fix Plugins

You are a Claude plugin marketplace analyzer and updater. When this skill is invoked, you'll analyze both the oeid-claude-plugins and ceg-claude-plugins marketplaces to determine which plugins need updates, then run the appropriate Makefile targets to update them.

## What This Skill Does

This skill:
1. **Analyzes both marketplaces** (oeid and ceg)
2. **Compares source vs installed versions** for each plugin
3. **Detects plugins that need updates**
4. **Runs appropriate Makefile update commands**
5. **Reports update results**

## Marketplaces to Monitor

### 1. OEID Claude Plugins Marketplace
**Source:** `/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace`
**Marketplace name:** `oeid-claude-plugins`
**Update command:** `make update` (uses Claude CLI)

**Plugins:**
- discover-oeid-plugins
- claude-manager
- noteplan-manager
- noteplan-templates
- noteplan-daily-organizer
- noteplan-structure-analyzer
- noteplan-note-creator

### 2. CEG Claude Plugins Marketplace
**Source:** `/Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/ceg-claude-plugin-marketplace`
**Marketplace name:** `ceg-claude-plugins`
**Update command:** `make update` (uses Claude CLI)

**Plugins:**
- discover-ceg-plugins
- ceg-mcp-plugin
- doc-manager
- version-manager
- note-manager

## How It Works

### Step 1: Check Marketplace Registration

Verify both marketplaces are registered with Claude:

```bash
cat ~/.claude/plugins/known_marketplaces.json | python3 -m json.tool
```

Expected:
```json
{
  "oeid-claude-plugins": {
    "source": {...},
    "installLocation": "/Users/omar.eid/workspace/oeid-claude-plugin-marketplace"
  },
  "ceg-claude-plugins": {
    "source": {...},
    "installLocation": "/Users/omar.eid/workspace/ceg-claude-plugin-marketplace"
  }
}
```

### Step 2: Compare Source vs Installed

For each marketplace, compare:

**Source plugins:**
```bash
# OEID marketplace
ls -1 /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace/plugins/

# CEG marketplace
ls -1 /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/ceg-claude-plugin-marketplace/plugins/
```

**Installed plugins:**
```bash
# Check installed plugins
cat ~/.claude/plugins/installed_plugins.json | python3 -m json.tool | grep -E "(oeid-claude-plugins|ceg-claude-plugins)"
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

CEG Marketplace (ceg-claude-plugins):
✅ discover-ceg-plugins - Up to date
✅ ceg-mcp-plugin - Up to date
✅ doc-manager - Up to date
✅ version-manager - Up to date
✅ note-manager - Up to date

Plugins needing updates: 1
- noteplan-manager@oeid-claude-plugins
```

### Step 5: Run Update Commands

For each marketplace with plugins needing updates:

**OEID Marketplace:**
```bash
cd /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/oeid-claude-plugin-marketplace
make update
```

**CEG Marketplace:**
```bash
cd /Users/omar.eid/Library/CloudStorage/OneDrive-ServiceNow/workspace/ceg-claude-plugin-marketplace
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

1. **Check prerequisites:**
   ```
   Checking Claude plugin marketplaces...

   ✅ OEID marketplace registered
   ✅ CEG marketplace registered
   ```

2. **Analyze both marketplaces:**
   ```
   Analyzing OEID marketplace...
   - Checking 7 plugins
   - Comparing source vs installed

   Analyzing CEG marketplace...
   - Checking 5 plugins
   - Comparing source vs installed
   ```

3. **Report findings:**
   ```
   📊 Analysis Complete

   OEID Marketplace (oeid-claude-plugins):
   ⚠️  noteplan-manager
       Source: /workspace/oeid-claude-plugin-marketplace/plugins/noteplan-manager
       Installed: ~/.claude/plugins/cache/oeid-claude-plugins/noteplan-manager/1.0.0
       Issue: Source has 4 new skills not in cache
       New skills:
         - fix-work-emojis
         - fix-personal-emojis
         - sync-header-emojis
         - sync-plan-templates

   CEG Marketplace (ceg-claude-plugins):
   ✅ All plugins up to date

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

   Running: cd /workspace/oeid-claude-plugin-marketplace && make update

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
Found updates needed in 2 marketplaces:
- oeid-claude-plugins (1 plugin)
- ceg-claude-plugins (2 plugins)

Run batch update? (yes/no)

If yes:
  cd /workspace/oeid-claude-plugin-marketplace && make update
  cd /workspace/ceg-claude-plugin-marketplace && make update
```

### 4. Selective Updates

Allow updating specific plugins:

```
Which plugins should I update?

1. All plugins (recommended)
2. Only oeid-claude-plugins
3. Only ceg-claude-plugins
4. Specific plugins:
   - noteplan-manager@oeid-claude-plugins
   - doc-manager@ceg-claude-plugins

Choose option (1-4):
```

## Example Run

```bash
/claude-manager:fix-plugins

# Analysis starts
Analyzing Claude plugin marketplaces...

📂 OEID Marketplace: /workspace/oeid-claude-plugin-marketplace
   Registered: ✅
   Plugins: 7

📂 CEG Marketplace: /workspace/ceg-claude-plugin-marketplace
   Registered: ✅
   Plugins: 5

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
Running: cd /workspace/oeid-claude-plugin-marketplace && make update

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
   /plugin marketplace add /workspace/oeid-claude-plugin-marketplace

2. Re-run this skill
```

### Issue: Plugin not installed

```
⚠️  noteplan-manager is in source but not installed

Fix:
1. Install plugin:
   cd /workspace/oeid-claude-plugin-marketplace && make install

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
# Update both marketplaces
cd /workspace/oeid-claude-plugin-marketplace && make update && \
cd /workspace/ceg-claude-plugin-marketplace && make update
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
   cd /workspace/oeid-claude-plugin-marketplace && make update

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

## 🎯 Skill Naming Consistency Detection

### The Problem

Skills can be invoked with or without plugin prefix:
```
/noteplan-manager:fix-work-emojis  ← Explicit (recommended)
/fix-work-emojis                   ← Shorthand (confusing)
```

This causes inconsistency when some skills use prefixes and others don't.

### Detection Logic

**Step 1: List All Available Skills**
```bash
# Get all skills across all plugins
env -u CLAUDECODE claude --help | grep "^  /"
```

**Step 2: Analyze Naming Patterns**
```python
def analyze_skill_naming(skills):
    prefixed = []
    unprefixed = []
    
    for skill in skills:
        if ':' in skill:
            # Has prefix like /plugin:skill
            prefixed.append(skill)
        else:
            # No prefix like /skill
            unprefixed.append(skill)
    
    return prefixed, unprefixed
```

**Step 3: Check for Inconsistencies Within Plugin**
```python
def check_plugin_consistency(plugin_name, skills):
    plugin_skills = [s for s in skills if s.startswith(f"/{plugin_name}:") or is_from_plugin(s, plugin_name)]
    
    has_prefix = []
    no_prefix = []
    
    for skill in plugin_skills:
        if f"{plugin_name}:" in skill:
            has_prefix.append(skill)
        else:
            no_prefix.append(skill)
    
    if has_prefix and no_prefix:
        return {
            'inconsistent': True,
            'plugin': plugin_name,
            'with_prefix': has_prefix,
            'without_prefix': no_prefix,
            'issue': 'Mixed naming style within same plugin'
        }
    
    return {'inconsistent': False}
```

### Example Detection Output

```
═══════════════════════════════════════════════════════════════════════════════
                    Skill Naming Consistency Check
═══════════════════════════════════════════════════════════════════════════════

Analyzing skill naming patterns across 12 plugins...

⚠️  INCONSISTENCY DETECTED: noteplan-manager

Skills WITH prefix:
  ✓ /noteplan-manager:fix-reference
  ✓ /noteplan-manager:analyze-structure
  ✓ /noteplan-manager:create-note

Skills WITHOUT prefix (from same plugin):
  ❌ /fix-work-emojis
  ❌ /fix-personal-emojis
  ❌ /sync-header-emojis
  ❌ /sync-plan-templates

Problem: Mixed naming style creates confusion
Recommendation: Use consistent prefix for all skills

─────────────────────────────────────────────────────────────────────────────

⚠️  INCONSISTENCY DETECTED: claude-manager

Skills WITHOUT prefix:
  ❌ /fix-plugins

Skills WITH prefix:
  ✓ /claude-manager:create-skill
  ✓ /claude-manager:update-skill

Problem: New skill doesn't follow existing convention
Recommendation: Add prefix to match other skills

═══════════════════════════════════════════════════════════════════════════════
```

### Recommended Convention

**Option 1: Always Use Prefix (Recommended)**
```
✅ /noteplan-manager:fix-work-emojis
✅ /noteplan-manager:fix-personal-emojis
✅ /claude-manager:fix-plugins
```

**Benefits:**
- Clear which plugin provides each skill
- No ambiguity
- Consistent across all skills

**Option 2: Never Use Prefix**
```
⚠️  /fix-work-emojis
⚠️  /fix-personal-emojis
⚠️  /fix-plugins
```

**Risks:**
- Name conflicts if two plugins have same skill name
- Unclear which plugin provides the skill
- Harder to debug

### Auto-Fix Suggestions

When inconsistencies detected:

```
Fix naming inconsistencies? (yes/no/details)

If yes, I can:

1. Update skill documentation to recommend prefixed usage
2. Create aliases for backward compatibility
3. Update examples in SKILL.md files to show prefixed usage
4. Add note about preferred invocation style

Choose fix approach:
  [1] Document preferred style (no code changes)
  [2] Update all examples to use prefix
  [3] Show migration guide
```

### Detection Rules

```python
NAMING_RULES = {
    'consistent_within_plugin': {
        'level': 'ERROR',
        'message': 'All skills in a plugin should use same style (all prefixed or all unprefixed)'
    },
    'prefer_prefix': {
        'level': 'WARNING',
        'message': 'Using prefix is recommended for clarity'
    },
    'generic_name_without_prefix': {
        'level': 'ERROR',
        'message': 'Generic names like "fix" should always have prefix to avoid conflicts'
    }
}
```

### Full Check Example

```
Running skill naming consistency check...

📊 Skill Inventory:
   Total skills: 47
   With prefix: 32 (68%)
   Without prefix: 15 (32%)

🔍 Per-Plugin Analysis:

noteplan-manager (16 skills):
  ❌ INCONSISTENT
  - 12 skills use prefix: /noteplan-manager:*
  - 4 skills no prefix: /fix-work-emojis, /fix-personal-emojis, /sync-header-emojis, /sync-plan-templates
  
  Impact: Confusing which skills belong to noteplan-manager
  Fix: Add prefix to 4 skills for consistency

claude-manager (5 skills):
  ❌ INCONSISTENT
  - 4 skills use prefix: /claude-manager:*
  - 1 skill no prefix: /fix-plugins
  
  Impact: New skill doesn't match existing convention
  Fix: Use /claude-manager:fix-plugins instead

doc-manager (2 skills):
  ✅ CONSISTENT
  - All 2 skills use prefix: /doc-manager:*

version-manager (1 skill):
  ✅ CONSISTENT
  - All 1 skills use prefix: /version-manager:*

─────────────────────────────────────────────────────────────────────────────

Summary:
  ✅ 8 plugins with consistent naming
  ❌ 2 plugins with inconsistent naming
  ⚠️  2 plugins with generic names needing prefix

Recommendation: Add prefix to 5 skills for consistency
```

### Implementation in fix-plugins

Add this check to the main workflow:

```python
def check_naming_consistency():
    """Check for skill naming inconsistencies across all plugins"""
    
    # Get all available skills
    skills = get_all_skills()
    
    # Group by plugin
    plugin_skills = group_skills_by_plugin(skills)
    
    issues = []
    
    for plugin, skills in plugin_skills.items():
        prefixed = [s for s in skills if f"{plugin}:" in s]
        unprefixed = [s for s in skills if f"{plugin}:" not in s]
        
        if prefixed and unprefixed:
            issues.append({
                'type': 'INCONSISTENT_NAMING',
                'plugin': plugin,
                'severity': 'WARNING',
                'prefixed_count': len(prefixed),
                'unprefixed_count': len(unprefixed),
                'prefixed_skills': prefixed,
                'unprefixed_skills': unprefixed,
                'fix': f'Add prefix {plugin}: to all unprefixed skills'
            })

    return issues
```


---

## Plugin Health Audit

Beyond version and naming checks, this skill audits plugins for compliance with the framework's mandatory patterns.

### Health Check Categories

When analyzing plugins, check each one for these requirements:

#### 1. Missing `introduce` Skill

Every plugin MUST have an `introduce` skill that explains its capabilities.

**Detection:**
```bash
# For each plugin, check if introduce skill exists
ls /path/to/marketplace/plugins/{plugin-name}/skills/introduce/SKILL.md
```

**Report format:**
```
MISSING_INTRODUCE: noteplan-manager
  Plugin has 16 skills but no introduce skill.
  Users have no way to discover capabilities.
  Fix: Create skills/introduce/SKILL.md

MISSING_INTRODUCE: script-manager
  Plugin has 1 skill but no introduce skill.
  Fix: Create skills/introduce/SKILL.md
```

**Auto-fix:** Offer to scaffold an `introduce` skill by reading all existing skills in the plugin and generating an introduction that lists them by category.

#### 2. Skills Missing Task Management

Skills that perform multi-step work MUST use `TaskCreate`/`TaskUpdate`.

**Detection:**
```bash
# Check each SKILL.md for TaskCreate/TaskUpdate references
grep -rL "TaskCreate\|TaskUpdate\|Task Management" /path/to/plugin/skills/*/SKILL.md
```

**Report format:**
```
MISSING_TASKS: noteplan-manager:quick-note
  Skill has 4 workflow phases but no TaskCreate/TaskUpdate usage.
  Fix: Add task management section with task creation and dependency setup.

MISSING_TASKS: script-manager:tampermonkey-create
  Skill has 6 phases but no task tracking.
  Fix: Add mandatory task management pattern.
```

**Severity levels:**
- Skills with 3+ phases and no task management: ERROR
- Skills with 1-2 phases and no task management: WARNING (may be too simple to need it)

#### 3. Skills Missing AskUserQuestion

Skills that make decisions or modify files MUST use `AskUserQuestion`.

**Detection:**
```bash
# Check each SKILL.md for AskUserQuestion references
grep -rL "AskUserQuestion\|Ask.*question\|User Interaction" /path/to/plugin/skills/*/SKILL.md
```

**Report format:**
```
MISSING_ASK: noteplan-manager:organize-daily
  Skill modifies files but never asks for user confirmation.
  Fix: Add AskUserQuestion before destructive operations.

OK: noteplan-manager:fix-filenames
  Skill uses AskUserQuestion for conflict resolution.
```

#### 4. Skills Missing Git Safety

Skills that modify files in git repos MUST follow the git safety pattern.

**Detection:**
```bash
# Check for git safety patterns
grep -rL "git status\|git diff\|CHECKPOINT\|pre-commit\|Git Safety" /path/to/plugin/skills/*/SKILL.md
```

**Report format:**
```
MISSING_GIT_SAFETY: knowledge-manager:extract-knowledge
  Skill writes files but has no git safety checks.
  Fix: Add pre-commit, checkpoint, and diff validation.
```

**Applies to:** Only skills that modify files. Read-only skills (analyze, list, query) are exempt.

#### 5. README Bloat

Plugins should have minimal READMEs. The substantive documentation belongs in the `introduce` skill.

**Detection:**
```bash
# Check README line count
wc -l /path/to/plugin/README.md
# If >50 lines and no introduce skill: README_BLOAT
```

**Report format:**
```
README_BLOAT: config-manager
  README.md is 180 lines. Content should be in introduce skill.
  Fix: Create introduce skill, slim README to <50 lines.

OK: noteplan-manager
  README.md is 44 lines. Minimal and appropriate.
```

### Complete Health Audit Workflow

When running the health audit (added to the main fix-plugins workflow):

```
═══════════════════════════════════════════════════════════════════════════════
                         Plugin Health Audit
═══════════════════════════════════════════════════════════════════════════════

Scanning 8 plugins across oeid-claude-plugins...

noteplan-manager (16 skills):
  ✅ Has introduce skill
  ✅ README is minimal (44 lines)
  ⚠️  3 skills missing TaskCreate/TaskUpdate:
      - quick-note (2 phases - WARNING)
      - list-templates (1 phase - OK, too simple)
      - suggest-improvements (3 phases - ERROR)
  ⚠️  2 skills missing AskUserQuestion:
      - organize-daily (modifies files - ERROR)
      - list-templates (read-only - OK)
  ✅ Git safety present in all file-modifying skills

claude-manager (4 skills):
  ❌ Missing introduce skill
  ⚠️  README is 120 lines (should be <50)
  ✅ All skills use TaskCreate/TaskUpdate
  ✅ All skills use AskUserQuestion

config-manager (5 skills):
  ❌ Missing introduce skill
  ⚠️  README is 180 lines (should be <50)
  ⚠️  2 skills missing TaskCreate/TaskUpdate
  ✅ All skills use AskUserQuestion

script-manager (1 skill):
  ❌ Missing introduce skill
  ⚠️  README is 90 lines (should be <50)
  ✅ tampermonkey-create uses task management
  ✅ tampermonkey-create uses AskUserQuestion

spirituality-manager (3 skills):
  ❌ Missing introduce skill
  ⚠️  No skills use TaskCreate/TaskUpdate
  ⚠️  No skills use AskUserQuestion

knowledge-manager (3 skills):
  ❌ Missing introduce skill
  ⚠️  No skills use TaskCreate/TaskUpdate
  ⚠️  1 skill missing git safety (extract-knowledge)

discover-oeid-plugins (1 skill):
  ❌ Missing introduce skill
  ✅ Single-skill plugin, explore-plugins serves as introduction

documentation-manager (1 skill):
  ❌ Missing introduce skill
  ⚠️  Not registered in marketplace.json

═══════════════════════════════════════════════════════════════════════════════

Summary:
  Plugins missing introduce skill: 7/8
  Skills missing task management: 8/33 (5 are errors, 3 are warnings)
  Skills missing AskUserQuestion: 6/33 (4 are errors, 2 are OK)
  Skills missing git safety: 1/33
  READMEs needing slimming: 4/8

Priority fixes:
  1. Create introduce skills for all plugins (7 plugins)
  2. Add task management to 5 skills with 3+ phases
  3. Add AskUserQuestion to 4 file-modifying skills
  4. Add git safety to extract-knowledge
  5. Slim 4 READMEs and move content to introduce skills

═══════════════════════════════════════════════════════════════════════════════
```

### Auto-Fix Options

After presenting the audit, offer fixes via `AskUserQuestion`:

```
What would you like to fix?

Options:
- Fix all (create introduce skills, update skill patterns, slim READMEs)
- Introduce skills only (create introduce skill for each plugin)
- Specific plugin (choose which plugin to fix)
- Skip (just the report, no changes)
```

For each fix category, use `claude-manager:skill-create` patterns to generate the missing skills or update existing ones.

### Integration with Main Workflow

The health audit runs as an additional step in the fix-plugins workflow:

```
Step 1: Version/update detection (existing)
Step 2: Skill naming consistency (existing)
Step 3: Plugin health audit - mandatory checks (NEW)
Step 4: Plugin maturity suggestions - optional enhancements (NEW)
Step 5: Present all findings
Step 6: Apply approved fixes
Step 7: Run make update if versions changed
```

---

## Plugin Maturity Suggestions (Optional Enhancements)

Beyond mandatory compliance, the audit should suggest optional patterns that make skills smarter over time. These are reported separately from errors - they are opportunities, not failures.

Present these after the mandatory health audit under a distinct heading:

```
═══════════════════════════════════════════════════════════════════════════════
                     Maturity Suggestions (Optional)
═══════════════════════════════════════════════════════════════════════════════

These are opportunities to make your skills smarter, not compliance failures.
```

### 1. Skill Usage Tracking

Skills that run repeatedly produce valuable data about what they encounter. A "Key Learnings" or execution log section captures this.

**What to look for:**
- Does the skill record what it found and fixed?
- Does the SKILL.md have a "Key Learnings" or "Execution Insights" section that grows over time?
- Is there a pattern for appending real-world findings back into the skill?

**The pattern:**

The `fix-reference` skill already does this well - it has a "Key Learnings & Examples" section (added after a real execution on 2026-02-15) documenting:
- Actual files processed and results
- Edge cases encountered (emoji paths, empty video metadata)
- Performance metrics (14 videos in ~30 seconds)
- Tool-specific insights (use Glob over bash cd for emoji paths)

**Detection:**
```bash
# Check for learnings/insights sections
grep -rl "Key Learnings\|Execution Insights\|Usage History\|Known Edge Cases" /path/to/plugin/skills/*/SKILL.md
```

**Suggestion format:**
```
SUGGEST_TRACKING: noteplan-manager:fix-filenames
  This skill processes files repeatedly but has no learnings section.
  Opportunity: After each execution, append a "Key Learnings" entry with:
    - Date, files processed, issues found, fixes applied
    - Edge cases encountered
    - Patterns that keep recurring (suggests preventive action)
  Reference: See fix-reference skill for the pattern.

ALREADY_TRACKING: noteplan-manager:fix-reference
  Has "Key Learnings & Examples" section with real execution data.
```

**What a learnings section looks like:**
```markdown
## Key Learnings & Execution History

### Execution: 2026-02-17
**Scope:** 5 files with pending changes
**Results:** 3 renamed, 1 merged, 1 skipped
**Edge cases:**
- NotePlan created 3 duplicates of Benefits.md during sync conflict
- Target filename had emoji that required NFD normalization on macOS
**Recurring pattern:** Benefits.md duplicates appear weekly - consider
  suggesting user check NotePlan sync settings
```

### 2. Knowledge Artifact Growth

Some skills naturally produce or refine knowledge artifacts as a byproduct of their work. The audit should identify skills that could grow shared knowledge but don't.

**What to look for:**
- Does the skill produce insights that would benefit other skills?
- Is there a shared knowledge file that multiple skills contribute to?
- Does the skill build up a reference, index, or conventions document over time?

**Concrete examples:**

| Skill | Byproduct Knowledge | Where It Could Live |
|---|---|---|
| `fix-filenames` | Naming conventions, edge cases, folder-to-pattern mappings | A conventions reference that `create-note` and `quick-note` also read |
| `fix-reference` | Topic taxonomy, duplicate detection rules, metadata extraction patterns | A reference index that grows across invocations |
| `fix-work-emojis` | Canonical emoji list, encoding gotchas, workstream-to-emoji mapping | A shared emoji reference for all emoji-related skills |
| `analyze-structure` | Folder hierarchy, file counts, convention patterns | A structure snapshot other skills use for context |
| `extract-knowledge` | Knowledge graph, topic connections, note relationships | A growing knowledge map that `knowledge-query` reads |

**Detection:**

Look for skills that:
1. Read many files and extract patterns → could maintain a patterns/conventions file
2. Process the same domain repeatedly → could maintain domain-specific reference
3. Share conventions with sibling skills → could centralize those conventions

```bash
# Check if skill references shared knowledge files
grep -rl "conventions\|reference\|shared\|canonical\|growing\|accumulate" /path/to/plugin/skills/*/SKILL.md
```

**Suggestion format:**
```
SUGGEST_KNOWLEDGE: noteplan-manager:fix-filenames
  This skill defines naming conventions that create-note also needs.
  Opportunity: Maintain a shared conventions artifact that both skills
  read and fix-filenames updates when new patterns are discovered.
  Currently the conventions are duplicated / could drift between skills.

SUGGEST_KNOWLEDGE: noteplan-manager:fix-work-emojis + fix-personal-emojis
  Both skills maintain independent emoji lists.
  Opportunity: Shared emoji reference that both read, either updates
  when new emojis are discovered.
```

**The pattern - how skills grow knowledge:**

```markdown
## Knowledge Artifacts

This skill maintains the following shared artifacts:

### Naming Conventions Reference
**Location:** `skills/fix-filenames/conventions.md` (or section in SKILL.md)
**Updated by:** fix-filenames (when new patterns discovered)
**Read by:** create-note, quick-note, introduce

After each execution, if a new naming pattern or edge case is discovered
that isn't already documented, append it to the conventions reference.

### Growth triggers:
- New folder type encountered → add to conventions table
- New emoji prefix pattern → add to allowed characters
- Edge case in conflict resolution → add to known edge cases
```

### 3. Feedback Loops and Self-Healing

Skills that run repeatedly on the same data should get smarter about preventing recurring issues, not just fixing them each time.

**What to look for:**
- Does the skill keep fixing the same problem? (suggests a preventive action)
- Can the skill detect root causes, not just symptoms?
- Does the skill suggest upstream fixes when patterns recur?

**Three levels of feedback:**

#### Level 1: Detect Recurrence

The skill notices it keeps fixing the same issue:

```markdown
## Recurrence Detection

After each execution, check if the same issues were found as last time:
- If Benefits.md duplicates appear 3+ times → suggest NotePlan sync settings check
- If the same file keeps getting wrong emoji → suggest template fix
- If the same folder keeps having misplaced files → suggest folder restructure

Report recurring issues distinctly from new issues:
  "RECURRING: Benefits.md duplicates (seen 3 times in last month)"
  "NEW: First time seeing this naming pattern in Research folder"
```

#### Level 2: Suggest Root Cause Fixes

The skill proposes fixes beyond its own scope:

```markdown
## Root Cause Suggestions

When patterns recur, suggest fixes at the source:

- "Fix-filenames keeps finding Plans-named files in Lists. Consider:
    - Adding a folder validation to create-note
    - Updating the template to enforce correct folder placement"

- "Fix-work-emojis keeps finding wrong workstream emojis. Consider:
    - Template is out of sync (run sync-plan-templates)
    - NotePlan template picker is showing stale options"

- "Fix-reference keeps finding duplicate YouTube links. Consider:
    - Adding dedup check to quick-note when saving links
    - Maintaining a seen-URLs index"
```

#### Level 3: Self-Updating Skill (Advanced)

The skill modifies its own SKILL.md to incorporate learnings:

```markdown
## Self-Healing Updates

After execution, if new patterns warrant it, offer to update the SKILL.md:

- "Discovered new folder type '📊 Dashboards/' not in conventions table.
   Add to naming conventions? (yes/no)"

- "Edge case: file with emoji in square brackets [🏢] breaks git mv.
   Add to known issues section? (yes/no)"

- "Conflict resolution for Benefits.md has been 'Merge' every time.
   Set 'Merge' as default for NotePlan duplicates? (yes/no)"
```

Use `AskUserQuestion` before any self-modification. The skill should never silently edit itself.

**Detection:**
```bash
# Check for feedback/recurrence patterns
grep -rl "recur\|recurring\|root cause\|self-heal\|self-update\|feedback\|pattern.*detect" /path/to/plugin/skills/*/SKILL.md
```

**Suggestion format:**
```
SUGGEST_FEEDBACK: noteplan-manager:fix-filenames
  Maturity: Level 0 (no feedback loop)
  This skill fixes naming issues but doesn't track recurrence.
  Opportunity:
    Level 1: Add recurrence detection (track issues seen before)
    Level 2: Suggest root cause fixes (e.g., template updates)
    Level 3: Offer to update its own conventions when new patterns found

SUGGEST_FEEDBACK: noteplan-manager:fix-reference
  Maturity: Level 1 (has Key Learnings section)
  Already tracks execution insights.
  Opportunity:
    Level 2: Suggest upstream dedup (e.g., check before saving links)
    Level 3: Grow topic taxonomy automatically from processed references
```

### Complete Maturity Report

After the mandatory health audit, present optional suggestions:

```
═══════════════════════════════════════════════════════════════════════════════
                     Maturity Suggestions (Optional)
═══════════════════════════════════════════════════════════════════════════════

These are opportunities, not requirements. Implementing any of these makes
your skills smarter over time.

noteplan-manager:
  📊 Usage Tracking:
    - fix-reference: Has learnings section ✅
    - fix-filenames: No learnings section (SUGGEST)
    - fix-work-emojis: No learnings section (SUGGEST)
    - fix-personal-emojis: No learnings section (SUGGEST)

  📚 Knowledge Artifacts:
    - fix-filenames defines naming conventions that create-note also needs
      → Opportunity: shared conventions reference
    - fix-work-emojis and fix-personal-emojis maintain separate emoji lists
      → Opportunity: shared emoji reference

  🔄 Feedback Loops:
    - fix-filenames: Level 0 → could detect recurring issues
    - fix-reference: Level 1 → could suggest upstream dedup
    - fix-work-emojis: Level 0 → could suggest template fixes on recurrence

claude-manager:
  📊 Usage Tracking:
    - fix-plugins: No execution history (SUGGEST)
    - skill-create: No learnings (SUGGEST)

  📚 Knowledge Artifacts:
    - skill-create defines framework standards that fix-plugins audits
      → Currently in sync, but could drift
      → Opportunity: shared standards reference

  🔄 Feedback Loops:
    - fix-plugins: Could track which plugins repeatedly fail audits
      → Suggest focused attention on chronically non-compliant plugins

═══════════════════════════════════════════════════════════════════════════════

Want to implement any of these suggestions?

Options:
- Add learnings sections (scaffold template in selected skills)
- Set up knowledge sharing (create shared reference files)
- Add feedback detection (recurrence tracking)
- Show me more details on a specific suggestion
- Skip (noted for future)
```

### Maturity Scoring (Optional)

For a quick overview, score each skill on a 0-3 maturity scale:

```
Maturity Levels:
  Level 0: Skill works correctly (mandatory patterns met)
  Level 1: Skill tracks what it does (usage/learnings section)
  Level 2: Skill grows knowledge (maintains shared artifacts)
  Level 3: Skill self-improves (detects recurrence, suggests root causes)

Plugin Maturity Summary:
  noteplan-manager: avg 0.6 / 3.0
    fix-reference: 1 (has learnings)
    fix-filenames: 0
    fix-work-emojis: 0
    ...

  claude-manager: avg 0.0 / 3.0
    All skills at Level 0
```

This gives a quick signal for which plugins would benefit most from maturity investment.

