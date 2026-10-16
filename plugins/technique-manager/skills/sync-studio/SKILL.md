---
name: sync-studio
description: Send the shareable technique content (the post view plus redacted JSON for each technique) over SSH with rsync to one dedicated folder on another Mac, where posts get written. Never sends the internal view, original screenshots or unredacted specs. Use after package-gallery, or whenever new techniques are ready.
---

# Sync Techniques to the Studio

You copy the **shareable** technique content to another Mac (the "studio") over SSH, into one folder that holds only this content. Posts and social drafts get written from there.

**Before this:** `/technique-manager:recreate-technique` renders the views, and `/technique-manager:package-gallery` builds the post gallery.

## What goes, what never goes

| Sent to `<dest>/` | Never sent |
|---|---|
| `pages/`: the post view (pages, gallery `index.html`, `_lib/`) | `pages/internal/`, the faithful view |
| `content/<slug>.json`: each technique's redacted spec (title, why, when, how, back story, blocks) | The original screenshots |
| `content/index.json`: one line per technique (slug, title, mechanism, why, taken, page, has_backstory) | `pages/specs/` (real names and values), session paths |

The script builds this from the post view and re-runs the privacy scan on every technique it sends. A technique without a post page (its redactions aren't finished) is left out, and any leftover finding stops the sync.

## Paths and settings

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
SS="<base directory of this skill>"
```

The host and folder live **outside the repo**, in `~/.config/technique-manager/studio.json`:

```json
{ "host": "<ssh host alias>", "dest": "<folder on that Mac; a relative path starts at its home>" }
```

If the file is missing, use `AskUserQuestion` to get the SSH host alias (check `~/.ssh/config` for candidates) and the destination folder, then save them:

```bash
python3 "$SS/scripts/sync_studio.py" --setup --host <alias> --dest "<folder>"
```

Prefer a **relative** `dest`, so the same setting works whatever the username is on the other Mac. A dedicated subfolder (e.g. `.../content/techniques`) keeps `--prune` from touching anything else.

## Tasks

Create with `TaskCreate`: `Check settings`, `Dry run`, `Sync`.

## Step 1: Dry run

```bash
python3 "$SS/scripts/sync_studio.py" --dry-run
```

It checks that the host is reachable over SSH without a password prompt (`BatchMode`), creates the folder if needed, and lists what would change.

- **Can't reach the host:** the sandbox may have no SSH keys or config. Ask the user to run the same command themselves with `! python3 …`, so it runs in their session with their keys.
- **Permission prompt on the other Mac:** writing under `~/Library/Mobile Documents/` from SSH can need Full Disk Access for `sshd-keygen-wrapper` (System Settings → Privacy & Security). Say so if `mkdir` fails with "Operation not permitted". Listing a *parent* iCloud folder can fail this way even when writing into the dedicated subfolder works, so judge by the sync result, not by an `ls` of the parent.
- **Which host alias:** try the aliases in `~/.ssh/config` with `ssh -o BatchMode=yes -o ConnectTimeout=6 <alias> true`. The first that answers is the one to save.
- **Re-runs send only what changed**, so a second run right after the first sends nothing. Use that to confirm a sync landed.

## Step 2: Sync

```bash
python3 "$SS/scripts/sync_studio.py"            # add only; nothing there is deleted
python3 "$SS/scripts/sync_studio.py" --prune    # also remove techniques deleted here
```

Use `--prune` only after `AskUserQuestion`, because it deletes files in the destination that no longer exist here.

The script handles both rsync flavors: rsync 3.2.4+ (e.g. Homebrew) protects remote paths itself, and macOS's built-in rsync and openrsync need them quoted for the remote shell.

## Output

```
Synced N techniques to <host>:<dest>
  new      content/<slug>.json, pages/<slug>.html
  updated  pages/index.html, content/index.json
Not sent: <slugs without a post page, if any>
```
