#!/bin/bash

# Script to manually register the oeid-claude-plugins marketplace

set -e

MARKETPLACE_NAME="oeid-claude-plugins"
MARKETPLACE_PATH="/Users/omar.eid/workspace/oeid-claude-plugin-marketplace"
KNOWN_MARKETPLACES="$HOME/.claude/plugins/known_marketplaces.json"

echo "🔧 Registering $MARKETPLACE_NAME marketplace..."
echo ""

# Check if marketplace path exists
if [ ! -d "$MARKETPLACE_PATH" ]; then
    echo "❌ Error: Marketplace path does not exist: $MARKETPLACE_PATH"
    exit 1
fi

# Check if marketplace.json exists
if [ ! -f "$MARKETPLACE_PATH/.claude-plugin/marketplace.json" ]; then
    echo "❌ Error: marketplace.json not found at $MARKETPLACE_PATH/.claude-plugin/"
    exit 1
fi

# Backup existing known_marketplaces.json
if [ -f "$KNOWN_MARKETPLACES" ]; then
    cp "$KNOWN_MARKETPLACES" "$KNOWN_MARKETPLACES.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Backed up existing known_marketplaces.json"
fi

# Create or update known_marketplaces.json
python3 <<EOF
import json
from datetime import datetime, timezone
from pathlib import Path

known_marketplaces_path = Path("$KNOWN_MARKETPLACES")
marketplace_name = "$MARKETPLACE_NAME"
marketplace_path = "$MARKETPLACE_PATH"

# Load existing marketplaces or create new structure
if known_marketplaces_path.exists():
    with open(known_marketplaces_path, 'r') as f:
        data = json.load(f)
else:
    data = {}

# Add or update the marketplace
data[marketplace_name] = {
    "source": {
        "source": "directory",
        "path": marketplace_path
    },
    "installLocation": marketplace_path,
    "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
}

# Write back
with open(known_marketplaces_path, 'w') as f:
    json.dump(data, f, indent=2)

print(f"✓ Registered {marketplace_name} in known_marketplaces.json")
EOF

echo ""
echo "✅ Marketplace registered successfully!"
echo ""
echo "Next steps:"
echo "  1. Restart your Claude session (if running)"
echo "  2. Run: make doctor"
echo "  3. Test with: /discover-oeid-plugins:explore-plugins"
