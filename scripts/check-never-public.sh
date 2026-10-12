#!/bin/bash
# Block text that must never reach the public GitHub copy of this repo.
#
# gitleaks catches secrets (keys, tokens). This catches what is private but not a secret:
# Tailscale addresses and the names of private employers. Only ADDED lines are checked, so
# text that is already in the repo does not block unrelated work.
#
# Two pattern lists, one extended regex per line, case-insensitive, '#' starts a comment:
#   scripts/never-public.patterns   public: generic shapes (Tailscale host names and IPs)
#   .claude/never-public.txt        private: the specific names. It is itself kept off the
#                                   public copy (PRIVATE_PATHS in sync-to-github.sh).
#
# Usage:
#   check-never-public.sh --staged                 lines staged for the next commit (pre-commit)
#   check-never-public.sh --commits A..B           each commit's added lines and its message
#   check-never-public.sh --diff A B               the net lines added between two trees
#   check-never-public.sh --messages A..B          commit messages only
#   -C DIR first runs it on the repo at DIR, as git -C does.
#   add --list FILE to read the private list from somewhere else (the sync copies it out of
#   main before it switches to the mirror branch, which does not have the file).
#
# Exit: 0 nothing found, 1 something found (each hit printed as file:line: text), 2 usage error.

set -euo pipefail
export LC_ALL=en_US.UTF-8

if [ "${1:-}" = "-C" ]; then cd "${2:?-C needs a directory}"; shift 2; fi
REPO_ROOT=$(git rev-parse --show-toplevel)
PUBLIC_PATTERNS="$REPO_ROOT/scripts/never-public.patterns"
PRIVATE_LIST="$REPO_ROOT/.claude/never-public.txt"
# Same list as PRIVATE_PATHS in sync-to-github.sh: never published, so never checked.
# The public patterns file and the self-test are skipped too: they hold the rules themselves
# and invented example addresses, which would otherwise match.
EXCLUDES=(":(exclude).claude/plans" ":(exclude).claude/memory" ":(exclude).claude/never-public.txt"
          ":(exclude)scripts/never-public.patterns" ":(exclude)scripts/test-never-public.sh")

MODE=""; ARG1=""; ARG2=""
while [ $# -gt 0 ]; do
    case "$1" in
        --staged)   MODE=staged; shift ;;
        --commits)  MODE=commits; ARG1="${2:?--commits needs A..B}"; shift 2 ;;
        --messages) MODE=messages; ARG1="${2:?--messages needs A..B}"; shift 2 ;;
        --diff)     MODE=diff; ARG1="${2:?--diff needs A B}"; ARG2="${3:?--diff needs A B}"; shift 3 ;;
        --list)     PRIVATE_LIST="${2:?--list needs a file}"; shift 2 ;;
        *) sed -n '2,21p' "$0"; exit 2 ;;
    esac
done
[ -n "$MODE" ] || { sed -n '2,21p' "$0"; exit 2; }

PATTERNS=$(mktemp)
HITS=$(mktemp)
trap 'rm -f "$PATTERNS" "$HITS"' EXIT
for f in "$PUBLIC_PATTERNS" "$PRIVATE_LIST"; do
    if [ -f "$f" ]; then
        grep -vE '^[[:space:]]*(#|$)' "$f" >> "$PATTERNS" || true
    else
        echo "never-public: warning: $f is missing, so its patterns are not checked" >&2
    fi
done
[ -s "$PATTERNS" ] || { echo "never-public: no patterns to check" >&2; exit 0; }

# Turn a unified diff into "path:line: text" for each added line. The path is kept in the
# line on purpose: a file NAME can leak as much as its contents.
added_lines() {
    awk '
        /^\+\+\+ / { f = substr($0, 5); sub(/^b\//, "", f); next }
        /^@@ /     { split($3, a, ","); n = substr(a[1], 2) + 0; next }
        /^\+/      { print f ":" n ": " substr($0, 2); n++ }
    '
}

scan() {  # stdin: lines to check; $1: label for the report
    local label="$1"
    if grep -iE -f "$PATTERNS" > "$HITS"; then
        echo "never-public: $label" >&2
        cut -c1-180 "$HITS" | sed 's/^/    /' >&2
        return 1
    fi
    return 0
}

diff_opts=(-U0 --no-color --no-ext-diff --no-renames)
found=0
case "$MODE" in
    staged)
        git diff --cached "${diff_opts[@]}" -- . "${EXCLUDES[@]}" | added_lines \
            | scan "staged lines that must not reach the public copy:" || found=1 ;;
    diff)
        git diff "${diff_opts[@]}" "$ARG1" "$ARG2" -- . "${EXCLUDES[@]}" | added_lines \
            | scan "lines added between ${ARG1:0:7} and ${ARG2:0:7} that must not reach the public copy:" || found=1 ;;
    commits|messages)
        for c in $(git rev-list --reverse "$ARG1"); do
            git log -1 --format=%B "$c" | sed 's/^/message: /' \
                | scan "commit ${c:0:7} message:" || found=1
            if [ "$MODE" = commits ]; then
                git diff "${diff_opts[@]}" "$c^" "$c" -- . "${EXCLUDES[@]}" | added_lines \
                    | scan "commit ${c:0:7} adds:" || found=1
            fi
        done ;;
esac

if [ "$found" = 1 ]; then
    echo "" >&2
    echo "never-public: blocked. Reword or remove the lines above. The lists are" >&2
    echo "    scripts/never-public.patterns and .claude/never-public.txt." >&2
    exit 1
fi
exit 0
