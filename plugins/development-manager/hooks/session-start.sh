#!/bin/sh
# Session start: when this repo has page comments waiting on Claude, print one
# line with how many and the command that lists them. Prints nothing anywhere
# else, and is quick there: plain shell walks up to the git root looking for
# .page-comments/threads, and node only starts when that folder exists.
# The same walk as the page-comments command (lib/repo.mjs findStore).
dir=${CLAUDE_PROJECT_DIR:-$(pwd)}
[ -d "$dir" ] || exit 0
found=""
if [ -d "$dir/.page-comments/threads" ]; then
  found=$dir
else
  here=$dir
  while :; do
    if [ -d "$here/.page-comments/threads" ]; then found=$here; break; fi
    if [ -e "$here/.git" ] || [ "$here" = "/" ]; then break; fi
    here=$(dirname "$here")
  done
  # Outside a git repo only the folder itself counts.
  if [ -n "$found" ] && [ "$found" != "$dir" ] && [ ! -e "$found/.git" ]; then
    up=$found
    while [ "$up" != "/" ] && [ ! -e "$up/.git" ]; do up=$(dirname "$up"); done
    [ -e "$up/.git" ] || found=""
  fi
fi
[ -n "$found" ] || exit 0
ls "$found/.page-comments/threads/"*.jsonl >/dev/null 2>&1 || exit 0
command -v node >/dev/null 2>&1 || exit 0
exec node "$(dirname "$0")/../shared/scripts/page-comments.mjs" notice --repo "$found" 2>/dev/null
