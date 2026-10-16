#!/bin/bash
# Incremental sync to GitHub with rewritten author
# Usage: ./scripts/sync-to-github.sh <remote_url> <remote_name> <author_name> <author_email>
#
# This script:
#   1. Reads sync state from .git/github-sync-state
#   2. Identifies NEW commits since last sync
#   3. Applies each one's changes onto the GitHub branch with rewritten author, leaving out
#      PRIVATE_PATHS (Claude's plans, memory and the never-public list: committed here,
#      never published)
#   4. If any of those commits adds text that must stay private (check-never-public.sh), they
#      go up as one commit instead, and the end state must pass that check before the push
#   5. Pushes incrementally (preserving GitHub commit IDs)
#
# For initial setup, run 'make sync-remote-init' first.

set -e

# The run switches to the mirror branch, which rewrites this file on disk while bash is still
# reading it. Run from a copy, so a mirror holding an older version can't change it mid-run.
if [ -z "$SYNC_TO_GITHUB_COPY" ]; then
    SYNC_TO_GITHUB_COPY=$(mktemp)
    cp "$0" "$SYNC_TO_GITHUB_COPY"
    export SYNC_TO_GITHUB_COPY
    exec bash "$SYNC_TO_GITHUB_COPY" "$@"
fi
trap 'rm -f "$SYNC_TO_GITHUB_COPY"' EXIT

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
cd "$REPO_ROOT"
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Committed on the internal remote, never pushed to the public mirror.
# Keep in step with sync-to-github-init.sh and EXCLUDES in check-never-public.sh.
PRIVATE_PATHS=(.claude/plans .claude/memory .claude/never-public.txt)
NEVER_PUBLIC_CHECK="$REPO_ROOT/scripts/check-never-public.sh"
EXCLUDES=()
for p in "${PRIVATE_PATHS[@]}"; do EXCLUDES+=(":(exclude)$p"); done
# The shared .git folder: in a linked worktree .git is a file, so ask git where it is.
GIT_COMMON_DIR=$(git rev-parse --path-format=absolute --git-common-dir)
STATE_FILE="$GIT_COMMON_DIR/github-sync-state"
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
# Parents before children, so a merge comes after every commit it brings in.
NEW_COMMITS=$(git rev-list --reverse --topo-order "$LAST_LOCAL_SHA..$CURRENT_LOCAL_SHA")
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

# Never-public check. The mirror branch has no private list, so take the check and both
# pattern lists out of $BRANCH before switching to it.
NP_DIR=$(mktemp -d)
NP_LIST="$NP_DIR/patterns.txt"
git show "$BRANCH:scripts/check-never-public.sh" > "$NP_DIR/check.sh" 2>/dev/null || true
git show "$BRANCH:scripts/never-public.patterns" > "$NP_LIST" 2>/dev/null || true
if [ ! -s "$NP_DIR/check.sh" ] || ! git show "$BRANCH:.claude/never-public.txt" >> "$NP_LIST" 2>/dev/null; then
    echo -e "${RED}BLOCKED: scripts/check-never-public.sh or .claude/never-public.txt is missing on $BRANCH.${NC}"
    echo -e "${YELLOW}The sync will not publish without the never-public check.${NC}"
    rm -rf "$NP_DIR"
    exit 1
fi
never_public() { bash "$NP_DIR/check.sh" --list "$NP_LIST" "$@"; }

# Each commit is published as-is unless one of them adds private text (even text a later
# commit removes): then the whole range goes up as ONE commit, so the in-between states
# never reach GitHub. The final check further down still has to pass.
SQUASH=0
if ! never_public --commits "$LAST_LOCAL_SHA..$CURRENT_LOCAL_SHA" 2>"$NP_DIR/commits.log"; then
    SQUASH=1
    echo -e "  ${YELLOW}Some of these commits add text that stays private (see 'make check-never-public-range').${NC}"
    echo -e "  ${YELLOW}Publishing them as one commit, so only the end state reaches GitHub.${NC}"
fi

# Clean up any existing sync branch
git branch -D "$SYNC_BRANCH" 2>/dev/null || true

# Create sync branch from GitHub HEAD
echo -e "  ${BLUE}Creating sync branch from GitHub HEAD...${NC}"
git checkout -b "$SYNC_BRANCH" "$GITHUB_REMOTE_NAME/$BRANCH"

# Prepare to track new mappings
MAPPING_FILE="$GIT_COMMON_DIR/github-sync-mapping"
NEW_MAPPINGS=""

# Apply each new commit's changes (minus PRIVATE_PATHS) with rewritten author.
# A plain cherry-pick can't leave paths out, and would conflict on a private file
# the mirror never had.
echo -e "  ${BLUE}Applying $NEW_COMMIT_COUNT commits with rewritten author...${NC}"
PATCH_FILE=$(mktemp)
for COMMIT in $NEW_COMMITS; do
    SHORT_SHA="${COMMIT:0:7}"
    COMMIT_SUBJECT=$(git log -1 --format="%s" "$COMMIT" | head -c 50)

    if [ -n "$(git rev-parse -q --verify "$COMMIT^2")" ]; then
        # A merge. Its diff from the first parent repeats the other side's commits, which are
        # already on the mirror, so the patch would not apply. Bring the mirror to the merge's
        # own files instead.
        git diff --binary HEAD "$COMMIT" -- . "${EXCLUDES[@]}" > "$PATCH_FILE"
    else
        git diff --binary "$COMMIT^" "$COMMIT" -- . "${EXCLUDES[@]}" > "$PATCH_FILE"
    fi
    # A commit from a side branch was made before the other side's edits to the same file,
    # so its plain patch may not fit the mirror; --3way merges it using both file versions.
    if [ -s "$PATCH_FILE" ] && ! git apply --index "$PATCH_FILE" 2>/dev/null && ! git apply --3way --index "$PATCH_FILE"; then
        echo -e "    ${RED}✗${NC} $SHORT_SHA - apply failed"
        echo -e "${RED}Conflict detected. Aborting.${NC}"
        rm -rf "$NP_DIR"
        rm -f "$PATCH_FILE"
        git reset -q --hard
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
rm -f "$PATCH_FILE"

if [ "$SQUASH" = 1 ]; then
    git reset -q --soft "$GITHUB_REMOTE_NAME/$BRANCH"
    # List the subjects of the squashed commits, leaving out any that name something private.
    SQUASH_MSG="Sync $NEW_COMMIT_COUNT internal commits as one"$'\n\n'
    SQUASH_MSG+="Published together because some of them carried text that stays private."$'\n'
    # Comments and blank lines out first: a blank pattern matches every subject.
    SUBJECT_PATTERNS="$NP_DIR/subject-patterns.txt"
    grep -vE '^[[:space:]]*(#|$)' "$NP_LIST" > "$SUBJECT_PATTERNS" || true
    for COMMIT in $NEW_COMMITS; do
        SUBJECT=$(git log -1 --format="%s" "$COMMIT")
        if printf '%s\n' "$SUBJECT" | grep -qiE -f "$SUBJECT_PATTERNS"; then
            SQUASH_MSG+=$'\n'"- (subject withheld)"
        else
            SQUASH_MSG+=$'\n'"- $SUBJECT"
        fi
    done
    GIT_AUTHOR_NAME="$GITHUB_AUTHOR_NAME" \
    GIT_AUTHOR_EMAIL="$GITHUB_AUTHOR_EMAIL" \
    GIT_COMMITTER_NAME="$GITHUB_AUTHOR_NAME" \
    GIT_COMMITTER_EMAIL="$GITHUB_AUTHOR_EMAIL" \
    git commit -q -m "$SQUASH_MSG" --allow-empty
    GITHUB_SHA=$(git rev-parse HEAD)
    NEW_MAPPINGS=""
    for COMMIT in $NEW_COMMITS; do NEW_MAPPINGS="$NEW_MAPPINGS$COMMIT $GITHUB_SHA\n"; done
    echo -e "    ${GREEN}✓${NC} $NEW_COMMIT_COUNT commits -> ${GITHUB_SHA:0:7} (one commit)"
fi

# Last guards before anything leaves this machine.
# The mirror must end up with exactly $BRANCH's files (minus PRIVATE_PATHS), however the
# commits were replayed. A three-way merge that went wrong shows up here.
if ! git diff --quiet HEAD "$CURRENT_LOCAL_SHA" -- . "${EXCLUDES[@]}"; then
    echo -e "${RED}BLOCKED: the mirror's files don't match $BRANCH after replaying the commits. Not pushing.${NC}"
    git diff --stat HEAD "$CURRENT_LOCAL_SHA" -- . "${EXCLUDES[@]}"
    rm -rf "$NP_DIR"
    git checkout "$BRANCH"
    git branch -D "$SYNC_BRANCH" 2>/dev/null || true
    exit 1
fi
if [ -n "$(git ls-tree -r --name-only HEAD -- "${PRIVATE_PATHS[@]}")" ]; then
    echo -e "${RED}BLOCKED: a private path (${PRIVATE_PATHS[*]}) is in the mirror tree. Not pushing.${NC}"
    rm -rf "$NP_DIR"
    git checkout "$BRANCH"
    git branch -D "$SYNC_BRANCH" 2>/dev/null || true
    exit 1
fi
if ! never_public --diff "$GITHUB_REMOTE_NAME/$BRANCH" HEAD || ! never_public --messages "$GITHUB_REMOTE_NAME/$BRANCH..HEAD"; then
    echo -e "${RED}BLOCKED: what would be published still holds private text (listed above). Not pushing.${NC}"
    echo -e "${YELLOW}Remove it in a new commit on $BRANCH, then run 'make sync-remote' again.${NC}"
    rm -rf "$NP_DIR"
    git checkout "$BRANCH"
    git branch -D "$SYNC_BRANCH" 2>/dev/null || true
    exit 1
fi
rm -rf "$NP_DIR"

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
