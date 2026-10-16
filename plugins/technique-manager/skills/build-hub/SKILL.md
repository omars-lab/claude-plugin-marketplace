---
name: build-hub
description: Set up and build the technique hub, a private git repo and local site where every recreated technique has a gallery card with its status, a page to comment on (page comments on every terminal block), and a front page to work from on the way to a post. Migrates the techniques folder into the hub, archives each linked Claude Code session before it is deleted, and serves the site with comments. Use when someone wants a hub or content gallery for their techniques, wants to comment on them, or asks to rebuild or serve it.
---

# Build the Technique Hub

The hub is where techniques become posts. It is a **private git repo**: comment threads are saved as files in git, and the threads, specs and context hold real names. It is never this public marketplace repo, and its pre-push hook refuses any remote not listed in `hub.json`.

Design: `docs/design/technique-hub/design.md` in the marketplace repo.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
BH="<base directory of this skill>"
HUB=~/workspace/technique-hub          # or the hub the user names
```

Once a hub exists, `~/.config/technique-manager/settings.json` names it (`{"root": …}`), and every technique-manager script uses it by default: render, gallery, zip, validate and sync.

## Tasks

Create with `TaskCreate`: `Create the repo`, `Migrate and archive`, `Build the hub`, `Turn on comments`, `First commit`, `First backup`.

## Step 1: Create the repo, with its upstream on the user's own machine

Use `AskUserQuestion` to ask where the upstream lives. The recommended answer is a bare repo on another Mac the user owns, over SSH. Never suggest a hosted remote, because the content is private.

```bash
ssh <host> 'git init -q --bare -b main ~/git/technique-hub.git'
git clone <host>:git/technique-hub.git "$HUB" && git -C "$HUB" checkout -q -b main
```

## Step 2: Migrate and archive

```bash
python3 "$BH/scripts/migrate_to_hub.py" --hub "$HUB" --allow-remote <host>:git/technique-hub.git
make -C "$HUB" archive
```

`migrate_to_hub.py`:
- copies the specs, `_redactions.json` and `techniques.json`;
- writes `hub.json` (where the screenshots are, which remotes are allowed, the port), the `Makefile`, `CLAUDE.md` (the comment routing table) and `.gitignore`;
- installs the pre-push hook;
- points the settings at the hub.

It never deletes anything and refuses if the hub already has specs. The screenshots stay in the Techniques folder.

`make archive` copies every linked session into `archive/sessions/` (git-ignored) and records `source.session.archived` in the spec. **Do this first, and early:** Claude Code deletes session files after `cleanupPeriodDays` (30 by default). Several techniques can share one session, so the file count can be lower than the number of linked techniques. `missing` lists sessions already gone.

## Step 3: Build

```bash
make -C "$HUB" hub              # archive, render every view, build the site
make -C "$HUB" hub SLUG=<slug>  # after editing one spec
```

`.cache/hub/` gets:
- `index.html`: the hub gallery, with status chips and the confirmed focus line on each card;
- `internal/`: the faithful pages;
- `post/`: the shareable pages.

- **`waiting.html`, "Waiting on you":** comment replies waiting on the user, suggestions to confirm, sessions not archived yet (with the date Claude Code will delete them), techniques with no focus, techniques with no context, and comments Claude hasn't answered. The gallery links to it with a count. Open threads are read through `.page-comments/run list --open --json`, never by parsing thread files.
- **The Post plan panel** at the top of each internal page shows:
  - the status;
  - the confirmed focus, or how to set one;
  - Claude's suggestions, marked "not confirmed";
  - the fetched context;
  - a link to the post preview.
- **The post view** marks the focus blocks with a bar in the gutter, and shows "The point" above the terminal once the focus is confirmed. With `post.trim`, it shows only the focus blocks, with `⋯` where blocks were cut. The post view never carries the status, the context or unconfirmed suggestions (`lib.INTERNAL_ONLY`).

Every card and every terminal block has a stable `data-comment-id` (`<slug>`, `<slug>:b<i>`), so a comment thread stays on its block across re-renders. Each block is wrapped in one `.cu-block`, which carries the spacing.

## Step 4: Turn on comments

Follow `development-manager:enable-page-comments`, with these hub specifics:
- **Mode:** `--root .cache/hub --port <hub.json port>`. `--detect` misreads the hub's `serve` target as a dev server, because that target *is* the comment server; ignore its `--target` advice.
- **One command:** the template's `make serve` already runs `.page-comments/run serve`, so enable adds no separate target.
- **Check:** run `--check`. Every line must be `ok`.

Then `make serve` and open `http://127.0.0.1:<port>/`. Press C on a card or any terminal line to comment. Add `--phone` to comment from the phone.

## Step 5: First commit

Commit everything except `.cache/` and `archive/`, which are ignored, and push to the upstream. The pre-push hook checks the remote against `hub.json`.

## Backup and the session hook

Git holds the specs and threads. Two private folders it doesn't hold are copied to the upstream machine by rsync instead:
- `archive/`, the session copies;
- the comment screenshots: `<shotsDir>/page-comments/<hub>/`, or `.page-comments/shots/` when that is the fallback.

```bash
make backup      # → <host>:<dest>/archive and /shots, from hub.json "backup"
```

**It only adds and updates.** There is no `--delete`, so a file removed here stays in the backup.

**The session hook drives it.** `migrate_to_hub.py` installs `.claude/hooks/sync-hub.sh` and wires it to `SessionStart` and `SessionEnd` in the hub's `.claude/settings.json`. Each Claude session in the hub then starts and ends with `make backup` and `make sync`.
- **Never waits:** it runs in the background, so the session doesn't wait for it.
- **Lock:** an atomic `mkdir` lock at `/tmp/technique-hub-sync.lock/`. Two runs at once would render into the same `.cache/hub` and break each other, so a run that starts while another is going is skipped.
- **Log:** `~/Library/Logs/technique-hub-sync.log`.
- **On failure:** a macOS notification.
- **Turn it off for one session:** set `TECHNIQUE_HUB_SYNC=0`.

## Background responder (answers comments while no session is open)

An open Claude session in the hub hears comments through development-manager's watcher. When none is open, a comment from the phone would wait until the next session. The responder covers that gap. **It runs on macOS only**, because it uses launchd, so run these in a Mac terminal:

```bash
make responder-on       # writes ~/Library/LaunchAgents/com.technique-hub.responder.plist and loads it
make responder-status   # on or off, what's waiting on Claude, the last log lines
make responder-off      # unloads it and removes the plist
```

**When launchd runs `.claude/hooks/respond-comments.sh`:**
- when a thread file is added or removed;
- every 5 minutes, because appending a message to an existing thread doesn't change the folder.

**What each run does:**
1. **Nothing waiting on Claude:** it exits at once, without starting Claude.
2. **Settles:** it waits `settle` seconds (45 by default) so a burst of comments is answered in one run.
3. **A session is open:** it skips if a session in the hub is open, meaning a `page-comments.mjs watch` process is running from the hub folder.
4. **Answers:** it runs `claude -p` with `.claude/hooks/respond-prompt.md`. Tools are limited to reading and editing, `make hub`/`make context`, `python3`, the page-comments tools and read-only git. The session hook is turned off for that run.
5. **Never asks:** it can't ask, so an unclear comment gets its question as a reply and stays open for the user. It never confirms a suggestion, commits or pushes.
6. **Finishes:** it runs one studio sync and shows a notification. A failure also shows a notification, and the run never waits.

**Settings:** `hub.json` `"responder": {"model": "…", "settle": 45}`. The model defaults to the background-job model.

**Details:**
- **Lock:** `/tmp/technique-hub-responder.lock/`.
- **Log:** `~/Library/Logs/technique-hub-responder.log`.
- **Desktop access:** a launchd job can't read `~/Desktop`, so rendering reuses the screenshot copy already in `.cache/hub/internal/img/`.

## Answering comments

The hub's `CLAUDE.md` has the routing table: which edit each comment asks for. Examples:
- "this is the point" on a block sets the focus;
- "fetch the PR" fetches pre-context;
- "don't show this" adds a replacement;
- "posted at <url>" sets the status.

Follow it together with `development-manager:answer-page-comments`, and run `make hub SLUG=…` before replying.

## Notes

- **Status** (`idea` → `focused` → `drafting` → `ready` → `posted`) defaults to `idea` and shows on each card. The focus line shows only once it is confirmed.
- **Screenshots of comments** go to iCloud Drive when it is available, and to `.page-comments/shots/` (ignored) when it isn't.
- **Sync and zip** keep working from the hub: `make sync` sends only the post view and post-safe JSON.

## Output

```
Hub: ~/workspace/technique-hub   upstream <host>:git/technique-hub.git
Techniques: N   sessions archived: K (M missing)
Serve: make serve → http://127.0.0.1:8790/   comments: check passed
```
