#!/usr/bin/env bash
# Initialize version tracking by adding versionCommit to all plugin.json files
# Usage: ./init-version-tracking.sh

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Initialize Version Tracking${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

CURRENT_COMMIT=$(git rev-parse HEAD)
echo -e "${BLUE}Current commit:${NC} ${CURRENT_COMMIT:0:7}"
echo ""

PLUGINS_UPDATED=0
PLUGINS_SKIPPED=0

for plugin_dir in plugins/*/; do
    plugin_name=$(basename "$plugin_dir")
    plugin_json="$plugin_dir/.claude-plugin/plugin.json"

    if [ ! -f "$plugin_json" ]; then
        echo -e "${YELLOW}⚠ Skipping $plugin_name (no plugin.json)${NC}"
        PLUGINS_SKIPPED=$((PLUGINS_SKIPPED + 1))
        continue
    fi

    # Check if versionCommit already exists
    has_version_commit=$(python3 -c "import json; data=json.load(open('$plugin_json')); print('yes' if 'versionCommit' in data else 'no')")

    if [ "$has_version_commit" = "yes" ]; then
        existing_commit=$(python3 -c "import json; print(json.load(open('$plugin_json'))['versionCommit'])")
        echo -e "${GREEN}✓ $plugin_name${NC} - Already has versionCommit (${existing_commit:0:7})"
        PLUGINS_SKIPPED=$((PLUGINS_SKIPPED + 1))
        continue
    fi

    # Add versionCommit field
    python3 <<EOF
import json

with open('$plugin_json', 'r') as f:
    data = json.load(f)

data['versionCommit'] = '$CURRENT_COMMIT'

with open('$plugin_json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
EOF

    version=$(python3 -c "import json; print(json.load(open('$plugin_json'))['version'])")
    echo -e "${GREEN}✓ $plugin_name${NC} - Added versionCommit (v$version @ ${CURRENT_COMMIT:0:7})"
    PLUGINS_UPDATED=$((PLUGINS_UPDATED + 1))
done

echo ""
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Summary${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}$PLUGINS_UPDATED plugin(s) initialized${NC}"
echo -e "  ${BLUE}$PLUGINS_SKIPPED plugin(s) skipped (already initialized)${NC}"
echo ""

if [ "$PLUGINS_UPDATED" -gt 0 ]; then
    echo -e "${YELLOW}💡 Don't forget to commit the changes:${NC}"
    echo -e "   ${BLUE}git add plugins/*/.claude-plugin/plugin.json${NC}"
    echo -e "   ${BLUE}git commit -m \"Initialize version tracking for all plugins\"${NC}"
    echo ""
fi

echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
