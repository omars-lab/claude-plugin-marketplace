#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

MARKETPLACE_NAME="oeid-claude-plugins"
MARKETPLACE_PATH="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_BASE="$HOME/.claude/plugins/marketplaces/$MARKETPLACE_NAME/plugins"

echo "Verifying plugin installations..."
echo ""

failed=0
total=0

for plugin_dir in "$MARKETPLACE_PATH"/plugins/*/; do
    plugin_name=$(basename "$plugin_dir")
    total=$((total + 1))

    if [ -d "$INSTALL_BASE/$plugin_name" ]; then
        # Check if it has plugin.json
        if [ -f "$INSTALL_BASE/$plugin_name/.claude-plugin/plugin.json" ]; then
            echo -e "${GREEN}✓${NC} $plugin_name - installed"
        else
            echo -e "${RED}✗${NC} $plugin_name - directory exists but plugin.json missing"
            failed=$((failed + 1))
        fi
    else
        echo -e "${RED}✗${NC} $plugin_name - not installed"
        failed=$((failed + 1))
    fi
done

echo ""
if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All $total plugins verified successfully${NC}"
    exit 0
else
    echo -e "${RED}$failed of $total plugins failed verification${NC}"
    exit 1
fi
