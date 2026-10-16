#!/bin/bash
# technique-hub session hook: when a Claude session in the hub starts or ends, copy the hub's
# private files to the upstream machine (make backup: add-only, never deletes) and send the
# post-safe content to the studio (make sync). Runs in the background, so the session never
# waits; a second run while one is going is skipped.
#   Log:    ~/Library/Logs/technique-hub-sync.log
#   Lock:   /tmp/technique-hub-sync.lock/ (a folder, made atomically; holds the PID)
#   Failure: a macOS notification; the session is never blocked.
# Wired from .claude/settings.json (SessionStart, SessionEnd). Set TECHNIQUE_HUB_SYNC=0 to skip.
[ "${TECHNIQUE_HUB_SYNC:-1}" = 0 ] && exit 0
cat >/dev/null 2>&1   # the hook's JSON on stdin; not needed

hub="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
log="$HOME/Library/Logs/technique-hub-sync.log"
lock="/tmp/technique-hub-sync.lock"
mkdir -p "$(dirname "$log")"

run() {
  echo "$BASHPID" > "$lock/pid"
  trap 'rm -rf "$lock"' EXIT
  echo "=== $(date '+%F %T') $1" >> "$log"
  failed=""
  make -s -C "$hub" backup >> "$log" 2>&1 || failed="backup"
  make -s -C "$hub" sync   >> "$log" 2>&1 || failed="${failed:+$failed, }studio sync"
  if [ -n "$failed" ]; then
    echo "FAILED: $failed" >> "$log"
    command -v osascript >/dev/null && osascript -e "display notification \"$failed failed; see ~/Library/Logs/technique-hub-sync.log\" with title \"Technique hub ⚠️\" sound name \"Basso\""
  else
    echo "ok" >> "$log"
  fi
}

# mkdir is atomic: of two hooks firing at once, exactly one gets the lock. Two runs at once would
# render into the same .cache/hub and break each other. A lock left by a run that died is cleared.
if ! mkdir "$lock" 2>/dev/null; then
  pid=$(cat "$lock/pid" 2>/dev/null)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "=== $(date '+%F %T') ${1:-run}: skipped, run $pid still going" >> "$log"
    exit 0
  fi
  rm -rf "$lock" && mkdir "$lock" 2>/dev/null || exit 0
fi
( run "${1:-run}" ) </dev/null >/dev/null 2>&1 &
disown 2>/dev/null
exit 0
