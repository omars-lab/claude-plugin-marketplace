#!/usr/bin/env bash
# Check all plugins for changes and bump versions as needed
# Usage: ./version-check-all.sh [--dry-run] [--auto-commit]

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

DRY_RUN=false
AUTO_COMMIT=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --auto-commit)
            AUTO_COMMIT=true
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Version Check & Bump${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}  Mode: DRY RUN (no changes will be made)${NC}"
else
    echo -e "${GREEN}  Mode: Active (versions will be updated)${NC}"
fi
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

PLUGINS_UPDATED=0
PLUGINS_UNCHANGED=0
PLUGINS_FAILED=0

# Find all plugins
for plugin_dir in plugins/*/; do
    plugin_name=$(basename "$plugin_dir")

    echo -e "${CYAN}Checking: ${BOLD}$plugin_name${NC}"

    # Detect changes
    if ! result=$("$SCRIPT_DIR/detect-plugin-changes.sh" "$plugin_name" 2>/dev/null); then
        echo -e "  ${RED}✗ Failed to detect changes${NC}"
        PLUGINS_FAILED=$((PLUGINS_FAILED + 1))
        echo ""
        continue
    fi

    # Check if up to date
    if [ "$result" = "UP_TO_DATE" ]; then
        echo -e "  ${GREEN}✓ Up to date (no changes since last version)${NC}"
        PLUGINS_UNCHANGED=$((PLUGINS_UNCHANGED + 1))
        echo ""
        continue
    fi

    # Parse JSON result
    current_version=$(echo "$result" | python3 -c "import sys, json; print(json.load(sys.stdin)['currentVersion'])")
    bump_type=$(echo "$result" | python3 -c "import sys, json; print(json.load(sys.stdin)['suggestedBump'])")
    new_skills=$(echo "$result" | python3 -c "import sys, json; print(json.load(sys.stdin)['changes']['newSkills'])")
    modified_skills=$(echo "$result" | python3 -c "import sys, json; print(json.load(sys.stdin)['changes']['modifiedSkills'])")
    removed_skills=$(echo "$result" | python3 -c "import sys, json; print(json.load(sys.stdin)['changes']['removedSkills'])")

    echo -e "  ${YELLOW}⚠ Changes detected:${NC}"
    [ "$new_skills" -gt 0 ] && echo -e "    • ${GREEN}$new_skills new skill(s)${NC}"
    [ "$modified_skills" -gt 0 ] && echo -e "    • ${BLUE}$modified_skills modified skill(s)${NC}"
    [ "$removed_skills" -gt 0 ] && echo -e "    • ${RED}$removed_skills removed skill(s)${NC}"

    echo -e "  ${BLUE}Current version:${NC} $current_version"
    echo -e "  ${BLUE}Suggested bump:${NC}  ${YELLOW}$bump_type${NC}"

    if [ "$DRY_RUN" = true ]; then
        # Calculate what the new version would be
        IFS='.' read -r major minor patch <<< "$current_version"
        case "$bump_type" in
            major) new_version="$((major + 1)).0.0" ;;
            minor) new_version="$major.$((minor + 1)).0" ;;
            patch) new_version="$major.$minor.$((patch + 1))" ;;
        esac
        echo -e "  ${CYAN}Would update to:${NC} $new_version"
    else
        # Actually bump the version
        commit_flag=""
        [ "$AUTO_COMMIT" = true ] && commit_flag="--commit"

        if new_version=$("$SCRIPT_DIR/version-bump.sh" "$plugin_name" "$bump_type" $commit_flag 2>&1); then
            echo -e "  ${GREEN}✓ Updated to:${NC} $(echo "$new_version" | tail -1)"
            PLUGINS_UPDATED=$((PLUGINS_UPDATED + 1))
        else
            echo -e "  ${RED}✗ Failed to update version${NC}"
            PLUGINS_FAILED=$((PLUGINS_FAILED + 1))
        fi
    fi

    echo ""
done

# Summary
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${BLUE}  Summary${NC}"
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "  ${YELLOW}$PLUGINS_UPDATED plugin(s) would be updated${NC}"
else
    echo -e "  ${GREEN}$PLUGINS_UPDATED plugin(s) updated${NC}"
fi
echo -e "  ${BLUE}$PLUGINS_UNCHANGED plugin(s) unchanged${NC}"
[ "$PLUGINS_FAILED" -gt 0 ] && echo -e "  ${RED}$PLUGINS_FAILED plugin(s) failed${NC}"
echo ""

if [ "$DRY_RUN" = true ] && [ "$PLUGINS_UPDATED" -gt 0 ]; then
    echo -e "${YELLOW}💡 Run without --dry-run to apply version bumps${NC}"
    echo ""
elif [ "$PLUGINS_UPDATED" -gt 0 ] && [ "$AUTO_COMMIT" = false ]; then
    echo -e "${YELLOW}💡 Don't forget to commit the version changes:${NC}"
    echo -e "   ${BLUE}git add plugins/*/. claude-plugin/plugin.json${NC}"
    echo -e "   ${BLUE}git commit -m \"Bump plugin versions\"${NC}"
    echo ""
fi

echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit 0
