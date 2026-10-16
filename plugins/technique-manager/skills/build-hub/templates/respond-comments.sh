#!/bin/bash
# technique-hub comment responder: answers page comments that are waiting on Claude while no
# Claude session in the hub is open to hear them (an open session's watcher hears them itself).
# launchd runs it when a thread file changes and every few minutes (make responder-on). It runs
# a headless `claude -p` with this folder's CLAUDE.md routing, scoped tools, and no questions.
#   Log:     ~/Library/Logs/technique-hub-responder.log
#   Lock:    /tmp/technique-hub-responder.lock/ (a folder, made atomically; holds the PID)
#   Failure: a macOS notification, then exit. It never waits for input.
#   Settings: hub.json "responder": {"model": …, "settle": seconds}
#   Off:     make responder-off, or TECHNIQUE_HUB_RESPONDER=0 in the agent's environment.
[ "${TECHNIQUE_HUB_RESPONDER:-1}" = 0 ] && exit 0
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
hub="$(cd "$(dirname "$0")/../.." && pwd)"
log="$HOME/Library/Logs/technique-hub-responder.log"
lock="/tmp/technique-hub-responder.lock"
mkdir -p "$(dirname "$log")"
say()    { echo "$(date '+%F %T') $*" >> "$log"; }
notify() { command -v osascript >/dev/null && osascript -e "display notification \"$1\" with title \"Technique hub$2\"${3:+ sound name \"$3\"}" >/dev/null 2>&1; }
fail()   { say "FAILED: $1"; notify "$1; see ~/Library/Logs/technique-hub-responder.log" " ⚠️" Basso; exit 0; }

# A run that is still going covers this trigger too. A lock left by a run that died is cleared.
if ! mkdir "$lock" 2>/dev/null; then
  pid=$(cat "$lock/pid" 2>/dev/null)
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && exit 0
  rm -rf "$lock" && mkdir "$lock" 2>/dev/null || exit 0
fi
echo $$ > "$lock/pid"
trap 'rm -rf "$lock"' EXIT
cd "$hub" || exit 0

setting() { python3 -c 'import json,sys; print((json.load(open("hub.json")).get("responder") or {}).get(sys.argv[1], sys.argv[2]))' "$1" "$2" 2>/dev/null || echo "$2"; }
waiting() { .page-comments/run list --open --waiting claude --json 2>/dev/null \
  | python3 -c 'import json,sys; print(sum(len(f["threads"]) for f in json.load(sys.stdin)["files"]))' 2>/dev/null || echo 0; }
# An open session runs development-manager's watcher (page-comments.mjs watch) from the hub.
session_open() {
  for pid in $(pgrep -f 'node .*page-comments\.mjs watch' 2>/dev/null); do
    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep -qx "n$hub" && return 0
  done
  return 1
}

[ "$(waiting)" -gt 0 ] || exit 0
# Let a burst of comments land, so they are answered in one run.
sleep "$(setting settle 45)"
n=$(waiting)
[ "$n" -gt 0 ] || exit 0
if session_open; then say "skip: a Claude session in the hub is open ($n waiting)"; exit 0; fi
command -v claude >/dev/null || fail "claude is not on PATH"
[ -f .claude/hooks/respond-prompt.md ] || fail "respond-prompt.md is missing"

model=$(setting model claude-haiku-4-5-20251001)
say "=== answering $n comment(s) with $model"
tools=(Read Edit Write Glob Grep Skill "Bash(make hub:*)" "Bash(make context:*)" "Bash(python3:*)"
  "Bash(.page-comments/run:*)" "Bash(git status:*)" "Bash(git diff:*)")
for t in list show reply resolve dismiss stats; do tools+=("mcp__plugin_development-manager_page-comments__$t"); done
# TECHNIQUE_HUB_SYNC=0: the session hook would render into .cache/hub while this run does.
# The sync runs once at the end instead.
TECHNIQUE_HUB_SYNC=0 env -u CLAUDECODE claude -p "$(cat .claude/hooks/respond-prompt.md)" \
  --model "$model" --allowedTools "${tools[@]}" </dev/null >> "$log" 2>&1 || fail "the responder's Claude run failed"

left=$(waiting)
say "done: $((n - left)) answered, $left still waiting on Claude"
"$hub/.claude/hooks/sync-hub.sh" responder </dev/null >/dev/null 2>&1
[ "$left" -gt 0 ] && msg="; $left left" || msg=""
notify "Answered $((n - left)) comment(s)$msg" ""
exit 0
