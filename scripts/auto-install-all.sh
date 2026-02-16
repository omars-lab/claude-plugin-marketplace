#!/bin/bash

# Auto-install all plugins to ~/.claude/plugins/cache and register them
# This mimics what happens when you run /plugin install <plugin>@<marketplace>

set -e

MARKETPLACE_NAME="oeid-claude-plugins"
MARKETPLACE_PATH="/Users/omar.eid/workspace/oeid-claude-plugin-marketplace"
CACHE_BASE="$HOME/.claude/plugins/cache/$MARKETPLACE_NAME"
INSTALLED_PLUGINS_JSON="$HOME/.claude/plugins/installed_plugins.json"

echo "🚀 Auto-installing all plugins from $MARKETPLACE_NAME..."
echo ""

# Get current git commit SHA
GIT_SHA=$(git -C "$MARKETPLACE_PATH" rev-parse HEAD 2>/dev/null || echo "unknown")

# Backup installed_plugins.json
if [ -f "$INSTALLED_PLUGINS_JSON" ]; then
    cp "$INSTALLED_PLUGINS_JSON" "$INSTALLED_PLUGINS_JSON.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Backed up installed_plugins.json"
fi

# Get current timestamp in ISO format with milliseconds
TIMESTAMP=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')")

# Process each plugin
installed_count=0
failed_count=0

for plugin_dir in "$MARKETPLACE_PATH/plugins"/*; do
    if [ ! -d "$plugin_dir" ]; then
        continue
    fi

    plugin_name=$(basename "$plugin_dir")
    plugin_json="$plugin_dir/.claude-plugin/plugin.json"

    echo "📦 Installing $plugin_name..."

    # Check if plugin.json exists
    if [ ! -f "$plugin_json" ]; then
        echo "   ⚠️  Skipping - no plugin.json found"
        failed_count=$((failed_count + 1))
        continue
    fi

    # Get version from plugin.json
    version=$(python3 -c "import json; print(json.load(open('$plugin_json'))['version'])" 2>/dev/null || echo "1.0.0")

    # Create cache directory
    cache_dir="$CACHE_BASE/$plugin_name/$version"
    mkdir -p "$cache_dir"

    # Copy plugin files to cache
    rsync -a --delete "$plugin_dir/" "$cache_dir/"

    if [ $? -eq 0 ]; then
        echo "   ✓ Copied to cache: $cache_dir"
        installed_count=$((installed_count + 1))

        # Add to installed_plugins.json
        python3 <<EOF
import json
from pathlib import Path

installed_plugins_path = Path("$INSTALLED_PLUGINS_JSON")

# Load existing data
if installed_plugins_path.exists():
    with open(installed_plugins_path, 'r') as f:
        data = json.load(f)
else:
    data = {"version": 2, "plugins": {}}

# Ensure version 2 format
if "version" not in data:
    data["version"] = 2
if "plugins" not in data:
    data["plugins"] = {}

# Plugin key format: plugin_name@marketplace_name
plugin_key = "$plugin_name@$MARKETPLACE_NAME"

# Create plugin entry
plugin_entry = {
    "scope": "user",
    "installPath": "$cache_dir",
    "version": "$version",
    "installedAt": "$TIMESTAMP",
    "lastUpdated": "$TIMESTAMP",
    "gitCommitSha": "$GIT_SHA"
}

# Add or update plugin entry
data["plugins"][plugin_key] = [plugin_entry]

# Write back
with open(installed_plugins_path, 'w') as f:
    json.dump(data, f, indent=2)

print(f"   ✓ Registered in installed_plugins.json")
EOF

    else
        echo "   ✗ Failed to copy"
        failed_count=$((failed_count + 1))
    fi
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary:"
echo "   ✓ Installed: $installed_count plugins"
if [ $failed_count -gt 0 ]; then
    echo "   ✗ Failed: $failed_count plugins"
fi
echo ""
echo "Next steps:"
echo "  1. Run: make doctor"
echo "  2. Restart Claude (if currently running)"
echo "  3. Test with: /discover-oeid-plugins:explore-plugins"
echo ""
