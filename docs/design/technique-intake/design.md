# Technique intake from the Share menu: the design to build

This is the one design to act on. It answers one question: what is the simplest way on macOS to
share a screenshot, from the screenshot thumbnail, Finder or Photos, and have a Claude Code
pipeline run on that file with nothing else to do?

The pipeline already exists as four skills across two plugins (section 1). This design adds a
way in, and says what replaces each question those skills ask when nobody is at the keyboard.
Nothing here is built yet. Section 9 lists the sources and which claims still need a test on a
real Mac.

## Summary

- **What we build.** A shortcut in Shortcuts.app named "Make technique page". It shows in the
  Share menu (screenshot Markup window, Photos, Finder) and as a Finder Quick Action. It hands
  the files to `technique-intake.sh`, which copies them into a queue and returns in under a
  second. A background run of the same script then drains the queue, one screenshot at a time,
  with `claude -p`.
- **What the user gets.** One share gives an internal technique page, ready to review, within a
  few minutes. A notification says so, and the page opens in the browser in the background.
- **What waits for the user.** The redactions. The headless run proposes them but never applies
  them. The post view, the gallery zip and the sync to the other Mac happen only after the user
  reviews them in an ordinary interactive session (section 5).
- **Why a shortcut.** One shortcut covers all three share points. It needs no Xcode, no signing
  and no app. And it runs the script as a child of Shortcuts, so the Desktop permission is
  granted to Shortcuts once instead of Full Disk Access for `/bin/bash` (section 3).
- **Model.** Sonnet, not Haiku, for the Vision transcription. A missed identifier in a dense
  terminal screenshot is the costly error, and the redaction step depends on Claude listing
  every one (section 4.4).
- **The one code change v1 needs.** A review gate in the spec (`"review": "pending"`) that
  `render_page.py` honours, so a headless run can render the internal view without writing a
  post page. Because `sync_studio.py` sends only techniques that have a post page, the same gate
  also holds back the sync.

## 1. The problem and the goal

**Today.** A good technique screenshot lands on the Desktop. Turning it into a page takes an
interactive session: `/screenshot-manager:suggest-techniques` to approve and move it, then
`/technique-manager:recreate-technique` to transcribe it, then `validate-pages`,
`package-gallery` and `sync-studio`. The user has to remember to do it, and soon: Claude Code
deletes session transcripts after `cleanupPeriodDays` (30 by default), and `find_session.py`
needs the transcript to link the session the screenshot came from.

**Goal.** One share is the whole action. The moment the user shares a screenshot, the pipeline
starts. A few minutes later there is a page ready to review, with the session already linked.

| Step today | Skill and scripts | Asks the user |
|---|---|---|
| 1. Move into the Techniques folder, record in `techniques.json` | `screenshot-manager:suggest-techniques`: `list_candidates.py`, `build_moves.py`, `move_files.py`, `update_manifest.py` | Which candidates to move (`AskUserQuestion`, multi-select) |
| 2. Transcribe to a spec, link the session, redact, render | `technique-manager:recreate-technique`: Vision, `find_session.py`, `scan_privacy.py`, `render_page.py` | How to treat identifiers; which replacements to use; whether to add a component |
| 3. Check in a browser, build the gallery and zip | `technique-manager:validate-pages`, `package-gallery`: `validate_pages.py`, `build_gallery.py`, `zip_gallery.py` | Whether to zip without unfinished techniques |
| 4. Send the post view to the other Mac | `technique-manager:sync-studio`: `sync_studio.py` | `--prune` only; setup if `studio.json` is missing |

**Not goals.** Classifying the whole Desktop (that stays the interactive `suggest-techniques`
sweep). Publishing anything without a human look at the redactions. An iPhone share target
(section 7, later).

## 2. The ways in

Four ways for a share or a file to start a script on macOS:

| Option | Setup effort | Share points covered | Long-running OK | Failure visibility |
|---|---|---|---|---|
| **A. Shortcut in the Share Sheet, running a shell script** (chosen) | Low. Build one shortcut by hand (about 6 actions), turn on Allow Running Scripts once. No code signing | Share button in the screenshot Markup window, Photos, Finder's Share menu, any app that shares images or files. The same shortcut can also be a Finder Quick Action and a Services item | Only if the script detaches and returns. Shortcuts shows a spinner until the script ends, and Apple documents no time limit. The design detaches, so the shortcut finishes in about a second | Good. The shortcut can show an error. The script logs and sends a notification |
| B. Finder Quick Action (Automator, or a shortcut marked "Use as Quick Action") | Low | Finder only: Control-click > Quick Actions, and the Preview pane. Not Photos, not the Markup window | Same as A. Automator's Run Shell Script also waits on the child's output pipes unless you redirect them | Same as A |
| C. A watched drop folder: launchd `WatchPaths` / `QueueDirectories`, or Folder Actions | Medium. A LaunchAgent plist, `launchctl bootstrap`, and a TCC grant | None directly. The user drags into the folder or uses "Save to" from the thumbnail's menu | Yes. launchd runs the job as long as it takes, and `QueueDirectories` restarts it while the folder is not empty | Poor. A TCC denial shows only as "Operation not permitted" in the log. Folder Actions fail silently, and reports say they do not fire on cloud-synced folders |
| D. A native app with a Share Extension | High. Xcode, an app target plus an extension target, signing, an App Group to hand files over, and a helper to run the job (a sandboxed extension cannot start `claude`) | Every Share menu, the same as A, with a custom sheet UI | Yes, through the helper | Best: real UI, progress, and a review button |

**What each one costs in permissions.** This is what decides between A and C.

- A launchd job runs `/bin/bash` (or `/bin/sh`) on its own. TCC holds that binary responsible
  for every file it opens, so reading `~/Desktop` (where the Techniques folder lives) needs Full
  Disk Access for the shell itself. That is a broad grant, and Apple gives no way to script it.
- A Run Shell Script action runs as a child of Shortcuts. The folder grant belongs to Shortcuts,
  which asks once per folder. To be tested: whether a detached grandchild keeps that grant
  (section 6, question 1). If it does not, the fallback is C, with the Techniques folder grant
  given to a small runner app rather than to `/bin/bash` (section 7, phase 2).

**When a native app is worth it.** Only when the share sheet itself should do something: show
the proposed title before starting, offer "skip redaction review" for a private page, or show
progress. None of that is needed for v1. It is the last phase in section 7.

### Decision

**A, with B for free.** One shortcut, with "Show in Share Sheet" and "Use as Quick Action >
Finder" both on, receiving Images and Files. It covers all three share points named in the goal:

- **The screenshot thumbnail.** Clicking the floating thumbnail opens the Markup window, which
  has a Share button. The thumbnail's right-click menu has Save to, Open with and Show in Finder,
  but no Share.
- **Finder.** Share > Make technique page, or Control-click > Quick Actions > Make technique page.
- **Photos.** Share > Make technique page. Photos hands Shortcuts an image, which Shortcuts
  writes to a temporary file before the script sees it. The script copies it at once (section
  3.3).

## 3. The build

### 3.1 The shortcut

Name: **Make technique page**. Icon: any. In the details panel (Shortcut Details):

- **Show in Share Sheet:** on.
- **Use as Quick Action:** on, with **Finder** ticked. Then turn it on under System Settings >
  General > Login Items & Extensions > Finder (Extensions).
- **Receive:** Images and Files. **If there's no input:** Stop and respond, "Share a screenshot
  to make a technique page."

The actions, top to bottom:

1. **Receive** *Images and Files* input from *Share Sheet, Quick Actions*. (This is the shortcut's
   first row, set by the details panel.)
2. **Run Shell Script.**
   - Shell: `bash`. Input: *Shortcut Input*. Pass input: **as arguments**.
   - Script:
     ```bash
     exec "$HOME/.local/bin/technique-intake" enqueue "$@"
     ```
   - Run as administrator: off.
3. **If** *Shell Script Result* contains `ERROR` → **Show Alert** with *Shell Script Result*.
   Otherwise → **Show Notification** "Queued: *Shell Script Result*".

Why each choice:

- **As arguments, not stdin.** Each file is its own `"$@"` element, so names with spaces and the
  U+202F narrow no-break space before AM/PM arrive intact. With stdin, every path comes as one
  newline-joined block that the script would have to split.
- **One line that `exec`s an installed script.** The real logic lives in a file under version
  control, not in a text box inside Shortcuts. Changing it never means editing the shortcut.
- **A stable path, `~/.local/bin/technique-intake`.** The plugin cache path changes with every
  version. The setup step copies the script there (section 7, phase 1) and re-copies it on
  update.
- **One-time setting:** Shortcuts > Settings > Advanced > **Allow Running Scripts**. Without it,
  the action fails with a scripting-security error.

### 3.2 What the script does

`technique-intake.sh` has two modes:

- **`enqueue <files…>`** runs inside the shortcut. It copies each file into the queue, starts the
  drain in the background (fully detached), prints a one-line summary and exits. It takes well
  under a second, so Shortcuts never sits with a spinner.
- **`drain`** runs detached. It takes the lock, then processes the queue oldest first: move the
  file into the Techniques folder, run `claude -p`, record it in `techniques.json`, notify. When
  the queue is empty it releases the lock, looks once more, and exits.

The queue lives in `~/Library/Application Support/technique-intake/`, which TCC does not
protect, so a copy into it never prompts:

```
technique-intake/
├── inbox/<id>/<original file name>   one folder per share, oldest id first
├── inbox/<id>/meta.json              source path, sha256, time shared
├── done/<id>/                        result.json (Claude's structured output), the run log
├── failed/<id>/                      the same, plus the reason
└── seen.tsv                          sha256 → slug, so a re-share is not redone
```

### 3.3 The files it accepts

- **Names.** `list_candidates.py` only lists files whose name starts with "Screenshot" or
  "Screen Shot", and reads the capture time from the name. A file shared from Photos may be
  called `IMG_0412.png` or `Screenshot 2026-…`. If the name doesn't match, the script renames
  the copy to `Screenshot YYYY-MM-DD at H.MM.SS AM.png`, from Spotlight's
  `kMDItemContentCreationDate` (falling back to the file's modification time). It keeps the
  original name in `meta.json`. It uses a plain space before AM/PM, never U+202F.
- **Time stamps.** `cp -p` keeps the modification time, which is the fallback for `taken`.
- **Where it came from.** If the shared file is already in `~/Desktop`, it is **moved** (the
  share is the approval). If it came from somewhere else (Photos, or a temporary file from the
  Markup window), it is copied. Then, when the drain runs, a file of the same name and hash on
  the Desktop is moved to the Trash, so the later `suggest-techniques` sweep doesn't offer the
  same shot twice.
- **Duplicates.** Same sha256 already in `seen.tsv` with a spec on disk: no Claude run. The drain
  re-opens the internal page and notifies "Already a page: `<slug>`".
- **Several files in one share.** They become one queue item, so that `list_candidates.py` can
  group them the way it already does (shots within 2 minutes form one group and one page).

### 3.4 The full `technique-intake.sh`

```bash
#!/bin/bash
# technique-intake: a shared screenshot becomes a technique page to review.
#   technique-intake enqueue <file>...   called by the "Make technique page" shortcut
#   technique-intake drain               runs detached; one Claude run per queue item
# House rules: log to ~/Library/Logs, notify with osascript, never block,
# PID lockfile in /tmp, env -u CLAUDECODE, tools scoped with --allowedTools.
set -u
JOB=technique-intake
LOG="$HOME/Library/Logs/$JOB.log"
LOCK="/tmp/$JOB.lock"
STATE="$HOME/Library/Application Support/$JOB"
INBOX="$STATE/inbox"; DONE="$STATE/done"; FAILED="$STATE/failed"; SEEN="$STATE/seen.tsv"
TECH="$HOME/Desktop/📸 Screenshots of Techniques"
CONF="$HOME/.config/technique-manager/intake.env"

# Shortcuts and launchd start with PATH=/usr/bin:/bin:/usr/sbin:/sbin and read no shell profile.
# Everything else comes from the env file, written once by the setup step:
#   MARKETPLACE=~/<path to this marketplace repo>        (local marketplace loads from the repo)
#   CLAUDE=~/.local/bin/claude
#   PYTHON=/opt/homebrew/bin/python3                     (3.10+; find_session.py uses "str | None")
#   CONDA=/opt/homebrew/Caskroom/miniconda/base/bin/conda (optional; for validate-pages)
#   INTAKE_MODEL=sonnet  INTAKE_BUDGET_USD=3  INTAKE_TIMEOUT_MIN=20  INTAKE_OPEN=1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
[ -f "$CONF" ] && . "$CONF"
: "${MARKETPLACE:?}" "${CLAUDE:=claude}" "${PYTHON:=python3}"
: "${INTAKE_MODEL:=sonnet}" "${INTAKE_BUDGET_USD:=3}" "${INTAKE_TIMEOUT_MIN:=20}" "${INTAKE_OPEN:=1}"
SM="$MARKETPLACE/plugins/screenshot-manager/skills"
TM="$MARKETPLACE/plugins/technique-manager/skills"
INTAKE="$TM/setup-share-intake"          # headless.md, result.schema.json live here

mkdir -p "$INBOX" "$DONE" "$FAILED" "$(dirname "$LOG")"; touch "$SEEN"

log()    { printf '%s [%s] %s\n' "$(date '+%F %T')" "$$" "$*" >>"$LOG"; }
notify() { # notify <title> <message> [sound]
  local t="${1//\"/\'}" m="${2//\"/\'}"
  osascript -e "display notification \"$m\" with title \"$t\"${3:+ sound name \"$3\"}" 2>/dev/null
}
fail()   { log "FAIL: $*"; notify "Technique intake ⚠️" "$*" Basso; }

# ---------------------------------------------------------------- enqueue
enqueue() {
  [ $# -gt 0 ] || { echo "ERROR: nothing was shared"; exit 0; }
  local id dir f n=0
  id="$(date +%Y%m%d-%H%M%S)-$$"; dir="$INBOX/$id"; mkdir -p "$dir"
  for f in "$@"; do
    [ -f "$f" ] || { log "skip (not a file): $f"; continue; }
    case "$(printf '%s' "${f##*.}" | tr '[:upper:]' '[:lower:]')" in
      png|jpg|jpeg|heic) ;; *) log "skip (not an image): $f"; continue ;;
    esac
    if [ "$(dirname "$f")" = "$HOME/Desktop" ]; then mv "$f" "$dir/"; else cp -p "$f" "$dir/"; fi
    n=$((n+1))
  done
  if [ "$n" -eq 0 ]; then rmdir "$dir"; echo "ERROR: no screenshot in what was shared"; exit 0; fi
  "$PYTHON" - "$dir" "$@" <<'PY'
import json, sys, hashlib, pathlib, datetime
d = pathlib.Path(sys.argv[1])
files = [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in sorted(d.iterdir()) if p.name != "meta.json"]
json.dump({"shared_from": sys.argv[2:], "files": files,
           "queued": datetime.datetime.now().isoformat(timespec="seconds")},
          open(d / "meta.json", "w"), ensure_ascii=False, indent=2)
PY
  log "queued $id ($n file(s))"
  # Detach fully: new session, no inherited pipes, so Shortcuts returns at once.
  nohup "$0" drain </dev/null >>"$LOG" 2>&1 &
  disown 2>/dev/null
  echo "$n screenshot(s); a page will be ready to review in a few minutes"
}

# ---------------------------------------------------------------- one item
normalize_names() { # rename non-screenshot names to the pattern list_candidates.py reads
  local dir="$1" f base ts
  for f in "$dir"/*; do
    base="$(basename "$f")"; [ "$base" = meta.json ] && continue
    case "$base" in Screenshot*|"Screen Shot"*) continue ;; esac
    ts="$(mdls -raw -name kMDItemContentCreationDate "$f" 2>/dev/null)"
    ts="$("$PYTHON" - "$ts" "$f" <<'PY'
import sys, os, datetime as dt
raw, path = sys.argv[1], sys.argv[2]
try:    t = dt.datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone()
except ValueError: t = dt.datetime.fromtimestamp(os.path.getmtime(path))
h = t.hour % 12 or 12
print(f"Screenshot {t:%Y-%m-%d} at {h}.{t:%M}.{t:%S} {'AM' if t.hour < 12 else 'PM'}")
PY
)"
    mv -n "$f" "$dir/$ts.${base##*.}"
  done
}

run_claude() { # run_claude <item dir> <work dir>; writes <work>/result.json
  local item="$1" work="$2" names
  names="$(cd "$item" && ls | grep -v '^meta.json$' | sed 's/^/  - /')"
  local prompt="/technique-manager:recreate-technique --headless
These screenshots were just shared by the user and are already in the Techniques folder:
$names
Write one spec for them (one page if there are several), then follow the headless rules."
  ( cd "$TECH" && env -u CLAUDECODE "$CLAUDE" -p "$prompt" \
      --model "$INTAKE_MODEL" --effort medium \
      --append-system-prompt-file "$INTAKE/headless.md" \
      --permission-mode dontAsk --permission-prompts none \
      --add-dir "$TECH" \
      --allowedTools \
        "Read" \
        "Edit(~/Desktop/📸 Screenshots of Techniques/pages/specs/**)" \
        "Write(~/Desktop/📸 Screenshots of Techniques/pages/specs/**)" \
        "Bash($PYTHON $TM/recreate-technique/scripts/find_session.py *)" \
        "Bash($PYTHON $TM/recreate-technique/scripts/scan_privacy.py *)" \
        "Bash($PYTHON $TM/recreate-technique/scripts/render_page.py *)" \
        "Bash($CONDA run -n technique-check python $TM/validate-pages/scripts/validate_pages.py *)" \
      --disallowedTools "AskUserQuestion" "WebFetch" "WebSearch" "Agent" "mcp__*" \
      --strict-mcp-config --setting-sources user --no-session-persistence \
      --max-turns 60 --max-budget-usd "$INTAKE_BUDGET_USD" \
      --output-format json --json-schema "$(cat "$INTAKE/result.schema.json")" \
      >"$work/result.json" 2>"$work/claude.err" ) &
  local pid=$! waited=0 limit=$((INTAKE_TIMEOUT_MIN * 60))
  while kill -0 "$pid" 2>/dev/null; do      # macOS has no timeout(1); a small watchdog
    sleep 5; waited=$((waited + 5))
    if [ "$waited" -ge "$limit" ]; then kill -INT "$pid"; sleep 10; kill "$pid" 2>/dev/null; break; fi
  done
  wait "$pid"
}

record_manifest() { # verdict from Claude's structured output → techniques.json, via existing scripts
  local item="$1" work="$2"
  "$PYTHON" "$SM/suggest-techniques/scripts/list_candidates.py" --dir "$item" >"$work/candidates.json" || return 1
  "$PYTHON" - "$work" <<'PY' || return 1
import json, sys, pathlib
w = pathlib.Path(sys.argv[1])
r = json.load(open(w / "result.json"))["structured_output"]
cands = json.load(open(w / "candidates.json"))
with open(w / "verdicts.tsv", "w") as f:
    for c in cands:   # one shared item = one technique, so every shot gets the same verdict
        f.write("\t".join(str(x) for x in (c["n"], r["label"], r["score"], r["mechanism"],
                                            r["title"], r["reason"])) + "\n")
print(",".join(str(c["n"]) for c in cands), file=open(w / "pick", "w"))
PY
  "$PYTHON" "$SM/suggest-techniques/scripts/build_moves.py" --candidates "$work/candidates.json" \
      --verdicts "$work/verdicts.tsv" --pick "$(cat "$work/pick")" --dest "$TECH" --out-dir "$work" >/dev/null || return 1
  "$PYTHON" "$SM/suggest-techniques/scripts/update_manifest.py" --root "$TECH" --entries "$work/entries.json" >>"$LOG"
}

process() { # process <item dir>
  local item="$1" id work f sha slug status page
  id="$(basename "$item")"; work="$STATE/work/$id"; mkdir -p "$work"
  log "start $id"
  normalize_names "$item"

  # A re-share of a screenshot that already has a page: no Claude run.
  sha="$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["files"][0]["sha256"])' "$item/meta.json")"
  slug="$(awk -F'\t' -v s="$sha" '$1==s{print $2}' "$SEEN" | tail -1)"
  if [ -n "$slug" ] && [ -f "$TECH/pages/specs/$slug.json" ]; then
    notify "Technique intake" "Already a page: $slug"
    [ "$INTAKE_OPEN" = 1 ] && open -g "$TECH/pages/internal/$slug.html"
    mv "$item" "$DONE/$id"; return 0
  fi

  # Pre-approved: the share was the approval. Copy into the Techniques folder (the queue keeps
  # its copy so list_candidates.py can read the names and times for the manifest).
  for f in "$item"/*; do
    [ "$(basename "$f")" = meta.json ] && continue
    cp -p "$f" "$TECH/" || { fail "Could not write to the Techniques folder (Desktop permission?)"; return 1; }
    # The Markup window's share leaves its own copy on the Desktop; don't offer it twice.
    [ -f "$HOME/Desktop/$(basename "$f")" ] && cmp -s "$f" "$HOME/Desktop/$(basename "$f")" \
      && mv "$HOME/Desktop/$(basename "$f")" "$HOME/.Trash/"
  done

  run_claude "$item" "$work"
  status="$("$PYTHON" -c 'import json,sys
try: r=json.load(open(sys.argv[1])); print("ok" if not r.get("is_error") and r.get("structured_output") else "error")
except Exception: print("error")' "$work/result.json")"
  if [ "$status" != ok ]; then
    cp "$work"/* "$item/" 2>/dev/null; mv "$item" "$FAILED/$id"
    fail "Claude run failed for $id. See ~/Library/Logs/$JOB.log"; return 1
  fi

  record_manifest "$item" "$work" || log "manifest update failed for $id (page still made)"
  slug="$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["structured_output"]["slug"])' "$work/result.json")"
  printf '%s\t%s\n' "$sha" "$slug" >>"$SEEN"
  cp "$work"/* "$item/" 2>/dev/null; mv "$item" "$DONE/$id"

  page="$TECH/pages/internal/$slug.html"
  notify "Technique page ready to review" "$slug: check the proposed redactions, then run the review."
  [ "$INTAKE_OPEN" = 1 ] && [ -f "$page" ] && open -g "$page"
  log "done $id → $slug"
}

# ---------------------------------------------------------------- drain
drain() {
  # shlock(1) ships with macOS: writes our PID, and breaks a lock whose PID is dead.
  shlock -p $$ -f "$LOCK" || { log "another drain is running; it will pick this item up"; exit 0; }
  trap 'rm -f "$LOCK"' EXIT

  "$CLAUDE" --version >/dev/null 2>&1 || { fail "claude not found at $CLAUDE"; exit 0; }
  "$CLAUDE" auth status >/dev/null 2>&1 || { fail "Claude Code is not logged in"; exit 0; }
  [ -d "$TECH" ] || { fail "Techniques folder missing"; exit 0; }

  local item
  while :; do
    item="$(ls -1d "$INBOX"/*/ 2>/dev/null | sort | head -1)"
    [ -n "$item" ] || break
    process "${item%/}" || true                 # one bad item never stops the queue
  done
  rm -f "$LOCK"; trap - EXIT
  # A share that landed between the last look and the unlock: start again.
  [ -n "$(ls -A "$INBOX" 2>/dev/null)" ] && exec "$0" drain
  exit 0
}

case "${1:-}" in
  enqueue) shift; enqueue "$@" ;;
  drain)   drain ;;
  *) echo "usage: technique-intake enqueue <file>... | drain" >&2; exit 2 ;;
esac
```

Notes on the script:

- **Never blocks.** Every failure path notifies and returns. A global failure (no `claude`, not
  logged in, no folder) exits and leaves the queue as it is, so the next share retries it.
- **The queue is the inbox folder; the lock is `/tmp/technique-intake.lock`.** A share that
  arrives mid-run only adds a folder. Its own `drain` sees the lock and exits, and the running
  drain picks the item up. The last check after unlocking closes the gap between "queue empty"
  and "lock released".
- **`nohup … </dev/null >>log 2>&1 &`.** All three standard streams are redirected, because the
  host (Shortcuts, like Automator) waits on the child's inherited pipes, not only on the child.
  If tests show Shortcuts still kills the drain when the shortcut ends, the fallback is to start
  it through launchd instead (`launchctl kickstart gui/$UID/<label>` on a LaunchAgent that runs
  `technique-intake drain`). That puts it back under the TCC question in section 2.
- **`open -g`** opens the internal page without stealing focus. osascript notifications can't
  carry a link (clicking one opens Script Editor), so the page itself is the link. Set
  `INTAKE_OPEN=0` to rely on the notification alone.
- **The watchdog** sends SIGINT first, which ends the turn cleanly, then SIGTERM.

### 3.5 The `claude -p` command, flag by flag

| Flag | Why |
|---|---|
| `-p "/technique-manager:recreate-technique --headless …"` | In `-p` mode, a user-invoked skill named in the prompt is expanded before the run, so the skill is loaded exactly as in a session. The `--headless` argument tells it to follow the rules in `headless.md` |
| No `--bare` | Bare mode skips installed plugins and the subscription login (it needs `ANTHROPIC_API_KEY`). This run needs both. `--plugin-dir "$MARKETPLACE/plugins/technique-manager"` is the alternative if loading every installed plugin turns out slow |
| `--model sonnet --effort medium` | Section 4.4 |
| `--append-system-prompt-file headless.md` | The headless rules (section 4), kept in the plugin next to the script so they version with it |
| `--permission-mode dontAsk` | Anything not pre-approved is denied rather than prompted. Reads in the working directory and `--add-dir` need no rule |
| `--permission-prompts none` | Removes `AskUserQuestion` and tells Claude nobody can approve, so it doesn't retry a denied call. Needs v2.1.259 or later |
| `--allowedTools` | Read; Edit/Write only under `pages/specs/`; Bash only for the four scripts it needs, by full path. `render_page.py` writes the pages itself, so Claude never writes HTML |
| `--disallowedTools AskUserQuestion WebFetch WebSearch Agent "mcp__*"` | Belt and braces. One screenshot never needs subagents |
| `--strict-mcp-config` | No MCP servers start. Faster, and nothing in the user's config is touched |
| `--setting-sources user` | Only the user's own settings load. The working directory is the Techniques folder, so no project settings or project hooks apply |
| `--no-session-persistence` | **Required.** See risk 1 in section 6: otherwise the intake run's own transcript, which contains the transcribed text, sits in `~/.claude/projects` within 30 minutes of the screenshot, and `find_session.py` can match it instead of the real session |
| `--max-turns 60 --max-budget-usd 3` | A stuck run ends on its own. Both values are settings |
| `--output-format json --json-schema result.schema.json` | The script reads `structured_output` instead of parsing prose. Exit code and `is_error` say whether it worked |

`result.schema.json`, what Claude returns:

```json
{
  "type": "object",
  "required": ["slug", "title", "mechanism", "reason", "label", "score",
               "session_linked", "proposed_redactions", "uncovered_ui", "internal_rendered"],
  "properties": {
    "slug":   { "type": "string" },
    "title":  { "type": "string" },
    "mechanism": { "type": "string" },
    "reason": { "type": "string" },
    "label":  { "enum": ["technique", "claude-not-technique", "other"] },
    "score":  { "type": "integer", "minimum": 0, "maximum": 5 },
    "session_linked": { "type": "boolean" },
    "proposed_redactions": { "type": "integer" },
    "uncovered_ui": { "type": "array", "items": { "type": "string" } },
    "internal_rendered": { "type": "boolean" },
    "notes": { "type": "string" }
  }
}
```

## 4. Each decision, made without asking

A headless run has nobody to ask. Each `AskUserQuestion` gets a fixed answer, chosen so the run
can never publish or send anything the user hasn't seen.

| Where | The question today | Headless answer | Why it is safe |
|---|---|---|---|
| suggest-techniques, Step 4 | Which candidates to move | **The shared files, all of them.** No Desktop sweep, no classification gate | The share is an explicit choice of these files. Claude still labels and scores them, and a `claude-not-technique` label shows in the notification |
| suggest-techniques, setup | Create the Techniques folder? | **No.** Notify and exit | A missing folder means the setup is wrong. Don't guess |
| recreate-technique, Step 1 | Which screenshots (no manifest) | **The files named in the prompt** | Same as above |
| recreate-technique, component rule | Add a component for UI no block covers? | **No.** Use the closest block (often a `note`) and list the UI in `uncovered_ui` | Adding a component edits the plugin repo, bumps a version and runs `make update`. That belongs in a session |
| recreate-technique, Step 2b | (none; `find_session.py --write`) | **Run it right away**, with `--spec` for the new spec | This is the main reason to trigger at share time: the transcript is minutes old, not weeks |
| recreate-technique, Step 3 | How to treat identifiers; which replacements | **Propose, never apply.** Claude writes its proposed rules to the spec's `proposed_redactions` and sets `"review": "pending"`. It does not touch `specs/_redactions.json` | The post view is the only thing that can leave the machine, and it can't be written while review is pending |
| recreate-technique, Step 4 | (none; render) | **Internal view only.** `render_page.py --spec <slug> --view internal` | The internal view is never shared |
| validate-pages | Install Playwright if conda is missing? | **No.** Run `validate_pages.py --view internal --only <slug> --no-shots` if the env exists; otherwise skip and say so in `notes` | Installing software is not part of a share |
| package-gallery | Zip without unfinished techniques? | **Not run headless** | Nothing new is shareable until review |
| sync-studio | Setup; `--prune` | **Not run headless** | Same |

### 4.1 The review gate (the one code change)

Two small changes to `render_page.py`, and nothing else in the pipeline:

1. **`--view internal|post`**, the same choice `build_gallery.py` and `validate_pages.py` already
   have. Default: both, as today.
2. **A spec field, `"review": "pending" | "approved"`.** While it is `pending`, `render_page.py`
   never writes the post page, even with a clean scan, and deletes any stale one. It says so in
   its output (`"post": "held: review pending"`). A spec with no `review` field behaves as today,
   so every existing spec keeps working.

Because `sync_studio.py` only sends techniques that have a post page, and `zip_gallery.py` only
zips the post view, this single gate holds back all three: the post page, the zip and the sync.
The scanner can't recognise names of people, companies or products, so a clean scan alone was
never enough to publish. Today a person is in the loop by construction. Headless, the gate puts
them back.

The spec carries the proposals next to the real rules:

```json
"review": "pending",
"proposed_redactions": [
  { "find": "acme-billing", "replace": "example-app", "why": "repo name in the statusline" },
  { "find": "Jordan",       "replace": "Alex",        "why": "person named in the prompt" }
],
"redactions": []
```

The internal view shows `proposed_redactions` in its replacement table, marked "proposed", so
the user reviews them on the same page as the screenshot.

### 4.2 `headless.md`, the rules appended to the system prompt

```markdown
# Headless run (technique intake)

You are running with `claude -p`. Nobody can answer a question. Never call AskUserQuestion.

1. The screenshots named in the prompt are already in the Techniques folder. Do not move,
   rename or classify any other file. Do not run the suggest-techniques sweep.
2. Write one spec at pages/specs/<slug>.json, following recreate-technique Step 2. Several
   files mean one page, blocks in shot order.
3. Run find_session.py --spec <that spec> --write now.
4. Redactions: run scan_privacy.py --spec <spec> --post. List every identifier you transcribed
   (people, employers, products, repos, internal tools, paths), plus the scanner hits. Write
   them as "proposed_redactions" in the spec, each with a "why". Set "review": "pending".
   Never edit specs/_redactions.json, never fill "redactions".
5. If the screenshot shows UI no block covers, use the closest existing block and list the
   UI in uncovered_ui. Never edit claude-ui.js or anything outside pages/specs/.
6. Render the internal view only: render_page.py --spec <spec> --view internal.
   Then validate it if the technique-check env exists.
7. Return the structured result. label/score/mechanism/title/reason follow the
   suggest-techniques verdict rules; titles and reasons name the move, never a person or project.
```

### 4.3 How the user finishes later

The notification and the page that opened in the background are the prompt to come back. The
review is an ordinary interactive session, so every question is a real `AskUserQuestion` again:

```
/technique-manager:recreate-technique --review            # every spec with "review": "pending"
/technique-manager:recreate-technique --review <slug>     # one
```

What `--review` does, as a short new section in the recreate-technique SKILL.md:

1. List the pending specs, newest first, with their `uncovered_ui` and whether the session was
   linked.
2. For each, show the proposed rules and ask once: **accept all (Recommended)**, edit, or keep
   private (no post page ever: `"review": "private"`).
3. Move accepted rules into `redactions` (or `specs/_redactions.json` for names that recur), set
   `"review": "approved"`, and re-run the scan until it is empty, as Step 3 does today.
4. Render both views, run `validate-pages`, then `package-gallery`.
5. **Sync runs here, at the end of the review**: `sync_studio.py`, without `--prune`. It is
   idempotent and sends only what changed, so running it after every review is cheap and safe.
   If any `uncovered_ui` was listed, offer to add the component first (the existing rule).

So the sync to the other Mac happens only from a session the user is in, right after they
approved what it sends.

### 4.4 Which model

The house rule suggests Haiku for background jobs, which suits mechanical tasks. This one isn't.
The heavy part is reading a dense terminal screenshot with Vision: small monospace text, glyphs
(`›` `●` `⎿` `✻` `※`), task states, a statusline packed with paths and branch names. Two kinds of
error matter:

- **A misread line** costs review time, and makes the page less faithful.
- **A missed identifier** is worse. The scanner can't recognise people, employers, products or
  internal tools. Claude's list of what it transcribed is the only way they reach the proposed
  redactions. The review gate catches what the user notices, but the list is what draws their
  eye to it.

**Recommendation: `sonnet` by default, `--effort medium`.** It is the smallest model the doc
trusts with both. `opus` is a setting away (`INTAKE_MODEL=opus`) for screenshots the user knows
are very dense. Haiku is not recommended for this run. No `--fallback-model`: a silent fall to a
weaker model would hide the reason a page came out worse, so a failed run should notify and
stay in `failed/` instead. Each run is one screenshot and a few script calls, and
`--max-budget-usd` caps it. Phase 1 should log `total_cost_usd` from the JSON output so the
real cost per page is known before anyone revisits the choice.

## 5. What runs where, end to end

```
Share ▸ Make technique page                       (Markup window, Photos, Finder, Quick Action)
  └─ Run Shell Script: technique-intake enqueue "$@"           < 1 s, Shortcuts done
       └─ inbox/<id>/  +  nohup technique-intake drain &
            ├─ lock /tmp/technique-intake.lock (shlock)
            ├─ copy into 📸 Screenshots of Techniques/          pre-approved
            ├─ claude -p  /technique-manager:recreate-technique --headless
            │     spec → find_session --write → proposed redactions, review: pending
            │     → render internal view → validate internal view
            ├─ techniques.json via build_moves.py + update_manifest.py
            └─ notification + open -g internal/<slug>.html
Later, in a session:
  /technique-manager:recreate-technique --review
      approve redactions → render post → validate → package-gallery → sync-studio
```

## 6. Risks and open questions

**Risks, with the mitigation in this design:**

1. **The intake run matches itself as the source session.** `find_session.py` searches every
   transcript in `~/.claude/projects` within 30 minutes of the screenshot, and falls back to
   Claude's own text (such as the recap line) when there's no typed prompt. A share comes
   minutes after the screenshot, and the intake run's transcript contains that exact text.
   *Mitigation:* `--no-session-persistence`, so the run writes no transcript. The debug record
   is the JSON result and the log instead.
2. **A detached drain may lose Shortcuts' folder grant, or be killed when the shortcut ends.**
   Unverified either way (question 1). *Mitigation:* test first (phase 0). The fallback is a
   LaunchAgent started by `launchctl kickstart`, with the Desktop grant given to a runner app.
3. **PATH.** Shortcuts' shell reads no profile. `claude`, conda and a modern `python3` won't be
   found. *Mitigation:* absolute paths from `intake.env`. `find_session.py` uses `str | None`
   annotations, so the macOS system `python3` (3.9) fails on it; `PYTHON` must point at 3.10+.
4. **File names.** U+202F before AM/PM, emoji in the Techniques folder name, spaces everywhere.
   *Mitigation:* paths travel as `"$@"` and quoted variables only. Non-screenshot names are
   renamed to the pattern `list_candidates.py` reads, with a plain space.
5. **Permission rules with paths.** The `Edit(...)`/`Write(...)` rules name a path with an emoji
   and spaces. If the rule syntax doesn't match it, the run fails closed (writes denied), which
   is safe but useless. *Mitigation:* phase 0 tests one run. Fallback: `--add-dir` plus
   `acceptEdits` limited to the specs folder as the working directory.
6. **The Desktop twin.** Sharing from the Markup window may hand over a temporary copy while
   the real file still lands on the Desktop. *Mitigation:* the drain trashes a Desktop file with
   the same name and identical bytes. If the temporary copy has a different name, the twin
   survives and `suggest-techniques` offers it later (question 3).
7. **Cost and runaway runs.** *Mitigation:* `--max-turns`, `--max-budget-usd`, the watchdog, one
   item at a time.
8. **Hooks in the user's config run headless.** Without `--bare`, user-level hooks fire.
   *Mitigation:* `--setting-sources user` keeps project and local settings out. User-level
   hooks still run, so check they are safe without a terminal (none should wait for input).
9. **Logged in or not.** A subscription login can expire. *Mitigation:* `claude auth status`
   before each drain; notify and leave the queue.

**Open questions:**

1. Does a process started with `nohup … &` from Run Shell Script survive the shortcut ending,
   and does it keep the Desktop access granted to Shortcuts? (Phase 0 test: a script that
   sleeps 120 s, then lists `~/Desktop` and writes a file there.)
2. What exactly does each share point hand the script: a real path to the Desktop file, or a
   temporary copy, and under what name? Test the Markup window, Photos and Finder separately.
3. Should a re-shared screenshot whose spec is still `pending` just re-open the page (this
   design), or re-run with a fresh transcription?
4. Is opening the internal page in the background welcome, or should the notification be the
   only signal? (`INTAKE_OPEN`.)
5. Sonnet as the default: confirm after ten real pages, using the logged cost and the number of
   review edits per page.
6. Should `--review` also be reachable from the internal page itself, with a "looks good"
   comment through development-manager's page comments? (Phase 3.)
7. Several files in one share become one page. Is that always right, or should shots more than
   2 minutes apart split into separate pages, as `list_candidates.py` groups them?

## 7. Phased plan

**Phase 0: prove the two unknowns (an hour, no code in the repo).** A throwaway shortcut whose
script is `nohup sh -c 'sleep 120; ls ~/Desktop > ~/Desktop/intake-test.txt' >/dev/null 2>&1 &`.
Share from the Markup window, Photos and Finder, log `"$@"` each time. Answers questions 1 and 2,
and risk 5 with one `claude -p` call that writes into the specs folder.

**Phase 1: v1, the simplest thing that works.**
- A new technique-manager skill, **`setup-share-intake`** (one-time configuration), holding
  `scripts/technique-intake.sh`, `headless.md` and `result.schema.json`. Its SKILL.md walks the
  user through building the shortcut (section 3.1), writes `~/.config/technique-manager/intake.env`
  with the paths it finds, copies the script to `~/.local/bin/technique-intake`, turns on Allow
  Running Scripts (by telling the user where), and runs one test share. `--undo` removes the
  copy and the env file and tells the user to delete the shortcut.
- `render_page.py`: `--view` and the `review` gate (section 4.1). The internal template shows
  `proposed_redactions`.
- recreate-technique SKILL.md: a short "Headless runs" note pointing at `headless.md`, and the
  `--review` mode (section 4.3).
- Update `introduce`, bump the plugin version (minor), `make update`, `make validate-plugin
  PLUGIN=technique-manager`.

**Phase 2: if phase 0 says detaching from Shortcuts doesn't hold.** A LaunchAgent with
`QueueDirectories` on the inbox runs `technique-intake drain`. The shortcut only copies into the
inbox. The Desktop grant goes to a tiny runner app (an AppleScript applet or a signed command
line tool) instead of `/bin/bash`. Also: ship the shortcut as a signed `.shortcut` file
(`shortcuts sign`) so setup is one double-click instead of six actions by hand.

**Phase 3: review without a terminal.** Comments on the internal page through
development-manager's page comments: "approve" or "replace X with Y" becomes the review, and a
resolved thread triggers the post render and the sync.

**Phase 4: a native Share Extension, only if wanted.** A sheet that shows the proposed title
and lets the user mark a page private before it runs, plus progress. It reuses the same queue
and drain, so it replaces only the shortcut.

**Later, separately:** the same shortcut on iPhone, saving into an iCloud Drive inbox that the
Mac drains. Needs the iCloud folder watched, which brings back the TCC question for
`~/Library/Mobile Documents`.

## 8. What changes, and what stays

| Stays as it is | Changes |
|---|---|
| `list_candidates.py`, `build_moves.py`, `move_files.py`, `update_manifest.py` | — (called by the script with a one-line verdict) |
| `find_session.py`, `scan_privacy.py` | — |
| `render_page.py` | `--view`, the `review` gate |
| internal page template | shows `proposed_redactions` as "proposed" |
| `validate_pages.py`, `build_gallery.py`, `zip_gallery.py`, `sync_studio.py` | — (the gate on the post page is enough) |
| recreate-technique SKILL.md | headless note, `--review` mode |
| — | new skill `setup-share-intake` with the script, rules and schema |

## 9. Sources, and what was checked

Claude Code (read 2026-10-15):

- [Run Claude Code programmatically](https://code.claude.com/docs/en/headless): `-p`; skills named
  in the prompt are expanded in `-p` mode; `--bare` skips plugins and the subscription login;
  `--permission-mode dontAsk`; `--permission-prompts none` removes `AskUserQuestion` (v2.1.259+);
  `--output-format json` with `--json-schema` returns `structured_output`; SIGTERM exits 143 and
  leaves the turn unfinished.
- [CLI reference](https://code.claude.com/docs/en/cli-reference): `--allowedTools`,
  `--disallowedTools`, `--model`, `--effort`, `--max-turns`, `--max-budget-usd`,
  `--no-session-persistence`, `--plugin-dir`, `--strict-mcp-config`, `--setting-sources`,
  `--append-system-prompt-file`.
- Transcript retention: `cleanupPeriodDays`, 30 by default, deleted at startup.
  ([claude-directory docs](https://code.claude.com/docs/en/claude-directory),
  [a write-up of the setting](https://dev.classmethod.jp/en/articles/claude-code-conversation-history-retention/))

Shortcuts and Finder:

- [Apple: input types for shortcuts](https://support.apple.com/guide/shortcuts-mac/apd7644168e1/mac):
  Images covers photos shared from Photos; Files covers any file.
- [Apple: run shortcuts from Finder](https://support.apple.com/guide/shortcuts-mac/apd163eb9f95):
  Quick Action and Services.
- [Apple: Advanced settings](https://support.apple.com/guide/shortcuts-mac/apdfeb05586f/mac):
  Allow Running Scripts; and a [forum thread](https://developer.apple.com/forums/thread/689436)
  where it failed on a managed Mac even when on.
- Passing files "as arguments" with `"$@"`:
  [Apple Developer Forums](https://developer.apple.com/forums/thread/742419),
  [TechEarl](https://techearl.com/mac-finder-context-menu-quick-action).
- Detaching from Automator's Run Shell Script needs all output redirected, not just `nohup`:
  [Apple Community](https://discussions.apple.com/thread/6474971). **Not verified for
  Shortcuts.** Phase 0 tests it.
- Screenshot thumbnail: clicking opens Markup with a Share button; right-click has no Share:
  [MacMost](https://macmost.com/how-to-take-mark-up-and-share-screenshots-on-a-mac.html),
  [OWC](https://eshop.macsales.com/blog/45371-a-guide-to-macos-mojaves-new-screenshot-tool/).
  Both sources date from macOS 10.14; check on the current macOS.

launchd, Folder Actions, TCC:

- [launchd.plist(5)](https://opensource.apple.com/source/launchd/launchd-258.1/launchd/src/launchd.plist.5.auto.html):
  `WatchPaths` vs `QueueDirectories` (runs while the folder is not empty).
- [MacScripter: QueueDirectories re-runs on removal](https://www.macscripter.net/t/queuedirectories-launchd-runs-again-when-folder-items-removed/66255).
- [MacScripter: Folder Actions reliability](https://macscripter.net/t/folder-actions-reliability-issues/76954):
  silent failures; may not fire on cloud-synced folders.
- [Apple Developer Forums: daemon can't read the Desktop](https://developer.apple.com/forums/thread/132851)
  and [thread 118508](https://developer.apple.com/forums/thread/118508): the launched binary
  needs the grant; giving `/bin/sh` Full Disk Access worked.
- Share Extension sandbox limits:
  [Apple Developer Forums](https://developer.apple.com/forums/thread/803642).

Read in this repo: the SKILL.md of `screenshot-manager:suggest-techniques` and of
technique-manager's `recreate-technique`, `validate-pages`, `package-gallery` and `sync-studio`,
and the argument lists of every script they call. `list_candidates.py` only lists names starting
with "Screenshot"/"Screen Shot" and falls back to the modification time; `render_page.py` has no
`--view` today; `find_session.py` uses `str | None`.

**Still to test on a real Mac** (none of these could be run here): questions 1 and 2, risk 5,
and the screenshot thumbnail's menus on the current macOS.
