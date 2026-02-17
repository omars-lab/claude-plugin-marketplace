#!/usr/bin/env bash
# Bump version for a specific plugin
# Usage: ./version-bump.sh <plugin-name> <major|minor|patch> [--commit]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PLUGIN_NAME="${1:-}"
BUMP_TYPE="${2:-}"
AUTO_COMMIT="${3:-}"

if [ -z "$PLUGIN_NAME" ] || [ -z "$BUMP_TYPE" ]; then
    echo -e "${RED}✗ Usage: $0 <plugin-name> <major|minor|patch> [--commit]${NC}" >&2
    exit 1
fi

if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo -e "${RED}✗ Bump type must be: major, minor, or patch${NC}" >&2
    exit 1
fi

PLUGIN_DIR="plugins/$PLUGIN_NAME"
PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"

if [ ! -f "$PLUGIN_JSON" ]; then
    echo -e "${RED}✗ Plugin not found: $PLUGIN_JSON${NC}" >&2
    exit 1
fi

# Read current version
CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])")

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump version
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
CURRENT_COMMIT=$(git rev-parse HEAD)

echo -e "${BLUE}Bumping version for $PLUGIN_NAME${NC}"
echo -e "${YELLOW}  Current:${NC} $CURRENT_VERSION"
echo -e "${GREEN}  New:${NC}     $NEW_VERSION"
echo -e "${BLUE}  Commit:${NC}  ${CURRENT_COMMIT:0:7}"

# Update plugin.json with new version and versionCommit
python3 <<EOF
import json
import sys

with open('$PLUGIN_JSON', 'r') as f:
    data = json.load(f)

data['version'] = '$NEW_VERSION'
data['versionCommit'] = '$CURRENT_COMMIT'

with open('$PLUGIN_JSON', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

print(f"✓ Updated $PLUGIN_JSON", file=sys.stderr)
EOF

if [ "$AUTO_COMMIT" = "--commit" ]; then
    # Stage and commit the change
    git add "$PLUGIN_JSON"
    git commit -m "Bump $PLUGIN_NAME version: $CURRENT_VERSION → $NEW_VERSION" -m "Version bump: $BUMP_TYPE" > /dev/null
    echo -e "${GREEN}✓ Committed version bump${NC}"
fi

# Output new version for scripting
echo "$NEW_VERSION"
