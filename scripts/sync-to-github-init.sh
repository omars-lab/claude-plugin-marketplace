#!/bin/bash
# ONE-TIME: Initialize GitHub sync with full history rewrite
# Usage: ./scripts/sync-to-github-init.sh <remote_url> <remote_name> <author_name> <author_email>
#
# This script:
#   1. Clones the current repo to a temp directory
#   2. Rewrites ALL commits to use the specified author
#   3. Force pushes to the github remote (DESTRUCTIVE to existing history)
#   4. Saves sync state for incremental syncs
#
# Run this ONCE to initialize, then use sync-to-github.sh for incremental updates.

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

GITHUB_REMOTE="$1"
GITHUB_REMOTE_NAME="$2"
GITHUB_AUTHOR_NAME="$3"
GITHUB_AUTHOR_EMAIL="$4"

if [ -z "$GITHUB_REMOTE" ] || [ -z "$GITHUB_REMOTE_NAME" ] || [ -z "$GITHUB_AUTHOR_NAME" ] || [ -z "$GITHUB_AUTHOR_EMAIL" ]; then
    echo -e "${RED}Usage: $0 <remote_url> <remote_name> <author_name> <author_email>${NC}"
    exit 1
fi

echo -e "${BLUE}=== ONE-TIME GitHub Sync Initialization ===${NC}"
echo -e "${RED}WARNING: This will FORCE PUSH and rewrite all GitHub history!${NC}"
echo -e "${RED}         All existing GitHub commit IDs will be invalidated.${NC}"
echo ""

# Check if already initialized
REPO_ROOT=$(git rev-parse --show-toplevel)
STATE_FILE="$REPO_ROOT/.git/github-sync-state"

if [ -f "$STATE_FILE" ]; then
    echo -e "${YELLOW}Sync state already exists:${NC}"
    grep -v "^#" "$STATE_FILE" | grep -v "^$" | while read line; do
        echo -e "  $line"
    done
    echo ""
    echo -e "${RED}Running this will DESTROY the existing sync state and GitHub history.${NC}"
fi

# Safety check: remote name
if [ "$GITHUB_REMOTE_NAME" != "github" ]; then
    echo -e "${RED}Safety check failed: remote name must be 'github', not '$GITHUB_REMOTE_NAME'${NC}"
    exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Ensure github remote exists
if ! git remote get-url "$GITHUB_REMOTE_NAME" > /dev/null 2>&1; then
    echo -e "  ${YELLOW}Adding remote '$GITHUB_REMOTE_NAME': $GITHUB_REMOTE${NC}"
    git remote add "$GITHUB_REMOTE_NAME" "$GITHUB_REMOTE"
fi

# Safety check: ensure GitHub doesn't have commits we don't have locally
echo -e "${BLUE}Checking for commits on GitHub not in local...${NC}"
git fetch "$GITHUB_REMOTE_NAME" "$BRANCH" 2>/dev/null || true

if git rev-parse "$GITHUB_REMOTE_NAME/$BRANCH" > /dev/null 2>&1; then
    # Compare commit counts - if GitHub has more commits than local, something is wrong
    LOCAL_COUNT=$(git rev-list --count "$BRANCH")
    GITHUB_COUNT=$(git rev-list --count "$GITHUB_REMOTE_NAME/$BRANCH")

    if [ "$GITHUB_COUNT" -gt "$LOCAL_COUNT" ]; then
        DIFF=$((GITHUB_COUNT - LOCAL_COUNT))
        echo -e "${RED}BLOCKED: GitHub has $DIFF more commit(s) than local.${NC}"
        echo ""
        echo -e "  Local commits:  $LOCAL_COUNT"
        echo -e "  GitHub commits: $GITHUB_COUNT"
        echo ""
        echo -e "${YELLOW}GitHub may have commits that don't exist locally.${NC}"
        echo -e "${YELLOW}If this is from a previous author-rewrite sync (same content, different SHAs),${NC}"
        echo -e "${YELLOW}you can bypass by deleting the state file: rm .git/github-sync-state${NC}"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} Local has >= GitHub commits ($LOCAL_COUNT >= $GITHUB_COUNT)"
else
    echo -e "  ${YELLOW}GitHub branch doesn't exist yet (first push)${NC}"
fi

# Require explicit confirmation
echo ""
echo -e "Type ${GREEN}RESET${NC} to confirm and proceed (anything else will abort):"
read -r CONFIRM

if [ "$CONFIRM" != "RESET" ]; then
    echo -e "${YELLOW}Aborted.${NC}"
    exit 1
fi

echo ""

# Get current state
LOCAL_HEAD=$(git rev-parse HEAD)
TEMP_DIR=$(mktemp -d)

echo -e "  ${BLUE}Branch: $BRANCH${NC}"
echo -e "  ${BLUE}Local HEAD: ${LOCAL_HEAD:0:7}${NC}"
echo -e "  ${BLUE}Temp directory: $TEMP_DIR${NC}"

# Clone to temp directory
echo -e "  ${BLUE}Creating temporary clone...${NC}"
git clone --mirror "$REPO_ROOT" "$TEMP_DIR/repo.git"

cd "$TEMP_DIR/repo.git"

# Count commits
COMMIT_COUNT=$(git rev-list --count "$BRANCH")
echo -e "  ${BLUE}Rewriting $COMMIT_COUNT commits with author: $GITHUB_AUTHOR_NAME <$GITHUB_AUTHOR_EMAIL>${NC}"

# Rewrite all commits
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --env-filter "
    export GIT_AUTHOR_NAME='$GITHUB_AUTHOR_NAME'
    export GIT_AUTHOR_EMAIL='$GITHUB_AUTHOR_EMAIL'
    export GIT_COMMITTER_NAME='$GITHUB_AUTHOR_NAME'
    export GIT_COMMITTER_EMAIL='$GITHUB_AUTHOR_EMAIL'
" --tag-name-filter cat -- --all

# Verify rewrite
REWRITTEN_EMAIL=$(git log -1 --format="%ae" "$BRANCH")
if [ "$REWRITTEN_EMAIL" != "$GITHUB_AUTHOR_EMAIL" ]; then
    echo -e "${RED}Rewrite failed: commits still show $REWRITTEN_EMAIL${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Get the new GitHub HEAD (after rewrite)
GITHUB_HEAD=$(git rev-parse "$BRANCH")
echo -e "  ${GREEN}✓${NC} Rewrite complete. New GitHub HEAD: ${GITHUB_HEAD:0:7}"

# Force push
echo -e "  ${BLUE}Force pushing to $GITHUB_REMOTE_NAME...${NC}"
git push -f "$GITHUB_REMOTE" "$BRANCH:$BRANCH"

# Cleanup temp
cd "$REPO_ROOT"
rm -rf "$TEMP_DIR"

# Fetch to update local tracking
git fetch "$GITHUB_REMOTE_NAME" "$BRANCH"

# Save sync state
echo -e "  ${BLUE}Saving sync state...${NC}"
cat > "$STATE_FILE" << EOF
# GitHub sync state - DO NOT EDIT MANUALLY
# Tracks the mapping between local and GitHub commits
#
# local:  Last local commit that has been synced
# github: Corresponding commit on GitHub (after author rewrite)
# synced: Timestamp of last sync

local:$LOCAL_HEAD
github:$(git rev-parse "$GITHUB_REMOTE_NAME/$BRANCH")
synced:$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

# Build 1:1 commit mapping
MAPPING_FILE="$REPO_ROOT/.git/github-sync-mapping"
echo -e "  ${BLUE}Building commit mapping...${NC}"
echo "# Commit mapping: local_sha -> github_sha" > "$MAPPING_FILE"
echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MAPPING_FILE"
echo "" >> "$MAPPING_FILE"

# Get all local commits and their corresponding GitHub commits (by position)
LOCAL_COMMITS=$(git rev-list --reverse "$BRANCH")
GITHUB_COMMITS=$(git rev-list --reverse "$GITHUB_REMOTE_NAME/$BRANCH")

# Paste them together
paste <(echo "$LOCAL_COMMITS") <(echo "$GITHUB_COMMITS") | while read local_sha github_sha; do
    echo "$local_sha $github_sha" >> "$MAPPING_FILE"
done

MAPPING_COUNT=$(wc -l < "$MAPPING_FILE" | tr -d ' ')
echo -e "  ${GREEN}✓${NC} Saved $((MAPPING_COUNT - 3)) commit mappings to .git/github-sync-mapping"

echo -e ""
echo -e "  ${GREEN}✓${NC} Initialized GitHub sync"
echo -e "  ${GREEN}✓${NC} Synced $COMMIT_COUNT commits with author $GITHUB_AUTHOR_EMAIL"
echo -e "  ${GREEN}✓${NC} Saved state to .git/github-sync-state"
echo -e ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "    - Use ${GREEN}make sync-remote${NC} for incremental syncs"
echo -e "    - Origin (mac-studio) remains unchanged"
