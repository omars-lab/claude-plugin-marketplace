#!/usr/bin/env bash
# Detect changes in a plugin since last version bump
# Usage: ./detect-plugin-changes.sh <plugin-name> [since-commit]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PLUGIN_NAME="${1:-}"
SINCE_COMMIT="${2:-}"

if [ -z "$PLUGIN_NAME" ]; then
    echo -e "${RED}✗ Usage: $0 <plugin-name> [since-commit]${NC}" >&2
    exit 1
fi

PLUGIN_DIR="plugins/$PLUGIN_NAME"

if [ ! -d "$PLUGIN_DIR" ]; then
    echo -e "${RED}✗ Plugin directory not found: $PLUGIN_DIR${NC}" >&2
    exit 1
fi

PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"

if [ ! -f "$PLUGIN_JSON" ]; then
    echo -e "${RED}✗ plugin.json not found: $PLUGIN_JSON${NC}" >&2
    exit 1
fi

# Get version and versionCommit from plugin.json
CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])" 2>/dev/null || echo "unknown")
VERSION_COMMIT=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON')).get('versionCommit', ''))" 2>/dev/null || echo "")

# Use provided commit or fall back to versionCommit
SINCE="${SINCE_COMMIT:-$VERSION_COMMIT}"

if [ -z "$SINCE" ]; then
    echo -e "${YELLOW}⚠ No versionCommit found in plugin.json, checking all history${NC}" >&2
    SINCE=$(git rev-list --max-parents=0 HEAD)  # Get initial commit
fi

# Check if there are any changes since the commit
CHANGED_FILES=$(git diff --name-only "$SINCE" HEAD -- "$PLUGIN_DIR" 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
    # No changes
    echo "UP_TO_DATE"
    exit 0
fi

# Analyze what changed
NEW_SKILLS=0
MODIFIED_SKILLS=0
REMOVED_SKILLS=0
MODIFIED_PLUGIN_JSON=0
MODIFIED_README=0
OTHER_CHANGES=0

# Categorize changes
while IFS= read -r file; do
    case "$file" in
        */skills/*/SKILL.md)
            skill_name=$(basename "$(dirname "$file")")
            # Check if this is a new skill
            if ! git cat-file -e "$SINCE:$file" 2>/dev/null; then
                NEW_SKILLS=$((NEW_SKILLS + 1))
            else
                MODIFIED_SKILLS=$((MODIFIED_SKILLS + 1))
            fi
            ;;
        */skills/*)
            # Other skill files (assets, etc.)
            if ! git cat-file -e "$SINCE:$file" 2>/dev/null; then
                : # New skill file, already counted
            else
                : # Modified skill file, already counted
            fi
            ;;
        */.claude-plugin/plugin.json)
            MODIFIED_PLUGIN_JSON=1
            ;;
        */README.md)
            MODIFIED_README=1
            ;;
        *)
            OTHER_CHANGES=$((OTHER_CHANGES + 1))
            ;;
    esac
done <<< "$CHANGED_FILES"

# Check for removed skills
REMOVED_SKILLS_LIST=$(git diff --name-status "$SINCE" HEAD -- "$PLUGIN_DIR/skills" | grep "^D.*SKILL.md$" | wc -l | tr -d ' ')
REMOVED_SKILLS=${REMOVED_SKILLS_LIST:-0}

# Determine suggested version bump
BUMP_TYPE="patch"

if [ "$REMOVED_SKILLS" -gt 0 ]; then
    # Removing skills is a breaking change
    BUMP_TYPE="major"
elif [ "$NEW_SKILLS" -gt 0 ]; then
    # New skills = new functionality
    BUMP_TYPE="minor"
elif [ "$MODIFIED_SKILLS" -gt 0 ]; then
    # Modified skills could be fixes or improvements
    BUMP_TYPE="patch"
elif [ "$MODIFIED_PLUGIN_JSON" -eq 1 ] || [ "$MODIFIED_README" -eq 1 ]; then
    # Metadata changes only
    BUMP_TYPE="patch"
elif [ "$OTHER_CHANGES" -gt 0 ]; then
    # Other changes
    BUMP_TYPE="patch"
fi

# Output results as JSON for easy parsing
cat <<EOF
{
  "status": "NEEDS_UPDATE",
  "currentVersion": "$CURRENT_VERSION",
  "versionCommit": "$VERSION_COMMIT",
  "sinceCommit": "$SINCE",
  "changes": {
    "newSkills": $NEW_SKILLS,
    "modifiedSkills": $MODIFIED_SKILLS,
    "removedSkills": $REMOVED_SKILLS,
    "modifiedPluginJson": $MODIFIED_PLUGIN_JSON,
    "modifiedReadme": $MODIFIED_README,
    "otherChanges": $OTHER_CHANGES
  },
  "suggestedBump": "$BUMP_TYPE",
  "changedFiles": $(echo "$CHANGED_FILES" | python3 -c "import sys, json; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))")
}
EOF
