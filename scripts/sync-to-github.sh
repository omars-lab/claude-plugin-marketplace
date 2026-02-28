#!/bin/bash
# Incremental sync to GitHub with rewritten author
# Usage: ./scripts/sync-to-github.sh <remote_url> <remote_name> <author_name> <author_email>
#
# This script:
#   1. Reads sync state from .git/github-sync-state
#   2. Identifies NEW commits since last sync
#   3. Cherry-picks them onto the GitHub branch with rewritten author
#   4. Pushes incrementally (preserving GitHub commit IDs)
#
# For initial setup, run 'make sync-remote-init' first.

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

# Safety check
if [ "$GITHUB_REMOTE_NAME" != "github" ]; then
    echo -e "${RED}Safety check failed: remote name must be 'github'${NC}"
    exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
STATE_FILE="$REPO_ROOT/.git/github-sync-state"
SYNC_BRANCH="__github_sync"

echo -e "${BLUE}Incremental sync to GitHub...${NC}"

# Check if state file exists
if [ ! -f "$STATE_FILE" ]; then
    echo -e "${RED}No sync state found.${NC}"
    echo -e "${YELLOW}Run 'make sync-remote-init' first to initialize.${NC}"
    exit 1
fi

# Read sync state
LAST_LOCAL_SHA=$(grep "^local:" "$STATE_FILE" | cut -d: -f2)
LAST_GITHUB_SHA=$(grep "^github:" "$STATE_FILE" | cut -d: -f2)
LAST_SYNCED=$(grep "^synced:" "$STATE_FILE" | cut -d: -f2-)

if [ -z "$LAST_LOCAL_SHA" ] || [ -z "$LAST_GITHUB_SHA" ]; then
    echo -e "${RED}Invalid sync state file.${NC}"
    echo -e "${YELLOW}Run 'make sync-remote-init' to reinitialize.${NC}"
    exit 1
fi

CURRENT_LOCAL_SHA=$(git rev-parse HEAD)

# Safety check: ensure GitHub doesn't have commits we don't have locally
git fetch "$GITHUB_REMOTE_NAME" "$BRANCH" 2>/dev/null || true

if git rev-parse "$GITHUB_REMOTE_NAME/$BRANCH" > /dev/null 2>&1; then
    LOCAL_COUNT=$(git rev-list --count "$BRANCH")
    GITHUB_COUNT=$(git rev-list --count "$GITHUB_REMOTE_NAME/$BRANCH")

    if [ "$GITHUB_COUNT" -gt "$LOCAL_COUNT" ]; then
        DIFF=$((GITHUB_COUNT - LOCAL_COUNT))
        echo -e "${RED}BLOCKED: GitHub has $DIFF more commit(s) than local.${NC}"
        echo ""
        echo -e "  Local commits:  $LOCAL_COUNT"
        echo -e "  GitHub commits: $GITHUB_COUNT"
        echo ""
        echo -e "${YELLOW}Someone may have pushed directly to GitHub.${NC}"
        echo -e "${YELLOW}Investigate before proceeding.${NC}"
        exit 1
    fi
fi

echo -e "  ${BLUE}Sync state:${NC}"
echo -e "    Last synced:     $LAST_SYNCED"
echo -e "    Last local:      ${LAST_LOCAL_SHA:0:7}"
echo -e "    Last GitHub:     ${LAST_GITHUB_SHA:0:7}"
echo -e "    Current local:   ${CURRENT_LOCAL_SHA:0:7}"

# Check if already up to date
if [ "$LAST_LOCAL_SHA" = "$CURRENT_LOCAL_SHA" ]; then
    echo -e "  ${GREEN}✓${NC} Already up to date. Nothing to sync."
    exit 0
fi

# Check if last synced commit still exists in history
if ! git rev-parse --verify "$LAST_LOCAL_SHA" > /dev/null 2>&1; then
    echo -e "${RED}Last synced commit $LAST_LOCAL_SHA not found in history.${NC}"
    echo -e "${YELLOW}History may have been rewritten. Run 'make sync-remote-init' to reset.${NC}"
    exit 1
fi

# Verify last synced commit is an ancestor of current HEAD
if ! git merge-base --is-ancestor "$LAST_LOCAL_SHA" "$CURRENT_LOCAL_SHA"; then
    echo -e "${RED}Last synced commit is not an ancestor of current HEAD.${NC}"
    echo -e "${YELLOW}History may have been rebased. Run 'make sync-remote-init' to reset.${NC}"
    exit 1
fi

# Count new commits
NEW_COMMITS=$(git rev-list --reverse "$LAST_LOCAL_SHA..$CURRENT_LOCAL_SHA")
NEW_COMMIT_COUNT=$(echo "$NEW_COMMITS" | wc -l | tr -d ' ')

if [ -z "$NEW_COMMITS" ]; then
    echo -e "  ${GREEN}✓${NC} No new commits to sync."
    exit 0
fi

echo -e "  ${BLUE}New commits to sync: $NEW_COMMIT_COUNT${NC}"

# Ensure github remote exists and fetch latest
if ! git remote get-url "$GITHUB_REMOTE_NAME" > /dev/null 2>&1; then
    echo -e "${RED}Remote '$GITHUB_REMOTE_NAME' not found.${NC}"
    echo -e "${YELLOW}Run 'make sync-remote-init' first.${NC}"
    exit 1
fi

git fetch "$GITHUB_REMOTE_NAME" "$BRANCH" 2>/dev/null || true

# Clean up any existing sync branch
git branch -D "$SYNC_BRANCH" 2>/dev/null || true

# Create sync branch from GitHub HEAD
echo -e "  ${BLUE}Creating sync branch from GitHub HEAD...${NC}"
git checkout -b "$SYNC_BRANCH" "$GITHUB_REMOTE_NAME/$BRANCH"

# Prepare to track new mappings
MAPPING_FILE="$REPO_ROOT/.git/github-sync-mapping"
NEW_MAPPINGS=""

# Cherry-pick each new commit with rewritten author
echo -e "  ${BLUE}Cherry-picking $NEW_COMMIT_COUNT commits with rewritten author...${NC}"
for COMMIT in $NEW_COMMITS; do
    SHORT_SHA="${COMMIT:0:7}"
    COMMIT_SUBJECT=$(git log -1 --format="%s" "$COMMIT" | head -c 50)

    # Cherry-pick without committing
    if ! git cherry-pick --no-commit "$COMMIT" 2>/dev/null; then
        echo -e "    ${RED}✗${NC} $SHORT_SHA - cherry-pick failed"
        echo -e "${RED}Conflict detected. Aborting.${NC}"
        git cherry-pick --abort 2>/dev/null || true
        git checkout "$BRANCH"
        git branch -D "$SYNC_BRANCH" 2>/dev/null || true
        exit 1
    fi

    # Get original commit message (full)
    COMMIT_MSG=$(git log -1 --format="%B" "$COMMIT")

    # Commit with rewritten author
    GIT_AUTHOR_NAME="$GITHUB_AUTHOR_NAME" \
    GIT_AUTHOR_EMAIL="$GITHUB_AUTHOR_EMAIL" \
    GIT_COMMITTER_NAME="$GITHUB_AUTHOR_NAME" \
    GIT_COMMITTER_EMAIL="$GITHUB_AUTHOR_EMAIL" \
    git commit -m "$COMMIT_MSG" --allow-empty

    # Track the mapping (local -> github)
    GITHUB_SHA=$(git rev-parse HEAD)
    NEW_MAPPINGS="$NEW_MAPPINGS$COMMIT $GITHUB_SHA\n"

    echo -e "    ${GREEN}✓${NC} $SHORT_SHA -> ${GITHUB_SHA:0:7} $COMMIT_SUBJECT"
done

# Push to GitHub (no force - clean append)
echo -e "  ${BLUE}Pushing to $GITHUB_REMOTE_NAME...${NC}"
if ! git push "$GITHUB_REMOTE_NAME" "$SYNC_BRANCH:$BRANCH"; then
    echo -e "${RED}Push failed. GitHub may have diverged.${NC}"
    echo -e "${YELLOW}Run 'make sync-remote-init' to force reset.${NC}"
    git checkout "$BRANCH"
    git branch -D "$SYNC_BRANCH" 2>/dev/null || true
    exit 1
fi

# Get new GitHub HEAD
NEW_GITHUB_SHA=$(git rev-parse HEAD)

# Switch back and clean up
git checkout "$BRANCH"
git branch -D "$SYNC_BRANCH"

# Update sync state
cat > "$STATE_FILE" << EOF
# GitHub sync state - DO NOT EDIT MANUALLY
# Tracks the mapping between local and GitHub commits
#
# local:  Last local commit that has been synced
# github: Corresponding commit on GitHub (after author rewrite)
# synced: Timestamp of last sync

local:$CURRENT_LOCAL_SHA
github:$NEW_GITHUB_SHA
synced:$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

# Append new mappings to mapping file
if [ -n "$NEW_MAPPINGS" ] && [ -f "$MAPPING_FILE" ]; then
    echo -e "$NEW_MAPPINGS" >> "$MAPPING_FILE"
fi

echo -e ""
echo -e "  ${GREEN}✓${NC} Synced $NEW_COMMIT_COUNT commits to $GITHUB_REMOTE_NAME"
echo -e "  ${BLUE}Local HEAD:  ${CURRENT_LOCAL_SHA:0:7}${NC}"
echo -e "  ${BLUE}GitHub HEAD: ${NEW_GITHUB_SHA:0:7}${NC}"
