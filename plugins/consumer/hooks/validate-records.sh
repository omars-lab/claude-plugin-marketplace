#!/usr/bin/env bash
#
# validate-records.sh -- PostToolUse guard for consumer research records.
#
# record.sh validates on the way in. This catches the other path: an agent that
# writes evidence.csv or listings.csv directly with Write or Edit, skipping the
# writer entirely. Without this, the enforcement is a convention, and a hurried
# agent producing a hundred ungraded rows would look exactly like a careful one.
#
# Reads the PostToolUse payload on stdin, ignores everything that is not one of
# our record files, and exits 2 with the problems on stderr so the agent gets
# them back as actionable feedback rather than a silent pass.
#
# Silent on success by design -- a hook that chatters on every unrelated write
# gets disabled within a day.

set -uo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENGINE="$HERE/../shared/scripts/records.py"

command -v python3 >/dev/null 2>&1 || exit 0
[ -f "$ENGINE" ] || exit 0

payload=$(cat)

# Pull the path out of the tool payload without assuming jq is installed.
target=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get("tool_input") or {}
print(ti.get("file_path") or ti.get("notebook_path") or "")
' 2>/dev/null) || exit 0

[ -n "$target" ] || exit 0

case "$(basename -- "$target")" in
    evidence.csv|listings.csv) ;;
    *) exit 0 ;;
esac

[ -f "$target" ] || exit 0

if ! out=$(python3 "$ENGINE" check --file "$target" 2>&1); then
    {
        echo "$out"
        echo
        echo "These rows were written directly instead of through record.sh, so they"
        echo "skipped validation. Fix them, or append with:"
        echo "  \${CLAUDE_PLUGIN_ROOT}/shared/scripts/record.sh evidence $target --candidate ... --grade A --source-url ..."
    } >&2
    exit 2
fi

exit 0
