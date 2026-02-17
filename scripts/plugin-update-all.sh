#!/usr/bin/env bash
# Update all installed plugins via Claude CLI
# Usage: ./plugin-update-all.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

MARKETPLACE_NAME="oeid-claude-plugins"

echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Updating Plugins via Claude CLI${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

PLUGINS_UPDATED=0
PLUGINS_FAILED=0
PLUGINS_SKIPPED=0

# Get list of plugins from marketplace.json
plugins=$(python3 -c "import json; data=json.load(open('.claude-plugin/marketplace.json')); print(' '.join([p['name'] for p in data['plugins']]))" 2>/dev/null || echo "")

if [ -z "$plugins" ]; then
    echo -e "${RED}✗ Failed to read plugins from marketplace.json${NC}"
    exit 1
fi

# Update each plugin
for plugin in $plugins; do
    echo -e "${CYAN}Updating: ${BOLD}$plugin@$MARKETPLACE_NAME${NC}"

    # Check if plugin is installed
    if ! grep -q "\"$plugin@$MARKETPLACE_NAME\"" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ Not installed (skipping)${NC}"
        PLUGINS_SKIPPED=$((PLUGINS_SKIPPED + 1))
        echo ""
        continue
    fi

    # Run update command
    if env -u CLAUDECODE claude plugin update "$plugin@$MARKETPLACE_NAME" --scope user 2>&1 | grep -v "^$"; then
        echo -e "  ${GREEN}✓ Updated successfully${NC}"
        PLUGINS_UPDATED=$((PLUGINS_UPDATED + 1))
    else
        status=$?
        if [ $status -eq 0 ]; then
            # Command succeeded but no output (already up to date)
            echo -e "  ${GREEN}✓ Already up to date${NC}"
            PLUGINS_UPDATED=$((PLUGINS_UPDATED + 1))
        else
            echo -e "  ${RED}✗ Update failed${NC}"
            PLUGINS_FAILED=$((PLUGINS_FAILED + 1))
        fi
    fi

    echo ""
done

# Summary
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Update Summary${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}$PLUGINS_UPDATED plugin(s) updated${NC}"
[ "$PLUGINS_SKIPPED" -gt 0 ] && echo -e "  ${YELLOW}$PLUGINS_SKIPPED plugin(s) skipped (not installed)${NC}"
[ "$PLUGINS_FAILED" -gt 0 ] && echo -e "  ${RED}$PLUGINS_FAILED plugin(s) failed${NC}"
echo ""

if [ "$PLUGINS_FAILED" -gt 0 ]; then
    echo -e "${RED}Some plugins failed to update${NC}"
    echo -e "${YELLOW}Try running 'make doctor' to diagnose issues${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ All plugins updated successfully${NC}"
echo ""
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit 0
