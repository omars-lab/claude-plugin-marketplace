---
name: sync-studio
description: Send the shareable technique content (the post view plus redacted JSON for each technique) to the studio folder where posts get written, adding to the techniques already there. On a Mac with iCloud Drive it writes into the shared iCloud folder directly; on any other Mac it rsyncs over SSH to the studio. Never sends the internal view, original screenshots or unredacted specs. Use after package-gallery or a hub rebuild, or whenever new techniques are ready.
---

# Sync Techniques to the Studio

You copy the **shareable** technique content into the studio folder: one folder that holds only this content, where posts and social drafts get written. More than one Mac feeds it, so every sync **adds** to what is there.

**Before this:** `/technique-manager:recreate-technique` renders the views, and `/technique-manager:package-gallery` builds the post gallery (or, in a hub, `make hub`).

## Two ways in: decided by the Mac you're on

| This Mac | What happens |
|---|---|
| Has iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs`) and `dest` is inside it | Writes straight into the folder. iCloud carries it to the studio. No SSH, no host needed. |
| No iCloud Drive, or `dest` is outside it | rsyncs over SSH to `host:dest`, as before. |

The script picks by itself; the output's `mode` says which (`local` or `ssh`). Because `dest` is relative to the home folder, **one `studio.json` works on every Mac**: copy it as is.

## Adding, never replacing

The folder holds techniques from several Macs, so a sync from here must not drop the others:

- **Each technique's own files** (`pages/<slug>.html`, `content/<slug>.json`) are added or updated. Nothing is deleted.
- **The two shared files**, `content/index.json` and the gallery `pages/index.html`, are rebuilt from the index already in the folder plus what this Mac sends. A technique from another Mac stays listed. A slug sent from here replaces the same slug there.
- The gallery keeps the title it was built with here (a hub's is "Technique hub"); `--title` overrides it.
- If iCloud has offloaded `content/index.json` (only a `.index.json.icloud` placeholder is there), the script stops instead of rebuilding from nothing. Run the `brctl download` command it prints, or open the folder in Finder, then sync again.
- Two Macs syncing at the same moment can leave iCloud with a conflicting copy (`index 2.json`). Sync from one Mac at a time. If a copy appears, delete it and re-sync from either Mac: the merge brings back every listed technique.

## What goes, what never goes

| Sent to `<dest>/` | Never sent |
|---|---|
| `pages/`: the post view (pages, gallery `index.html`, `_lib/`) | `pages/internal/`, the faithful view |
| `content/<slug>.json`: each technique's redacted spec (title, why, when, how, back story, blocks) | The original screenshots |
| `content/index.json`: one line per technique (slug, title, mechanism, why, taken, page, has_backstory, status, focus) | `pages/specs/` (real names and values), session paths |

The script builds this from the post view and re-runs the privacy scan on every technique it sends. A technique without a post page (its redactions aren't finished) is left out, and any leftover finding stops the sync.

## Paths and settings

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
SS="<base directory of this skill>"
```

The host and folder live **outside the repo**, in `~/.config/technique-manager/studio.json`:

```json
{ "host": "<ssh host alias>", "dest": "<folder; relative = from the home folder>" }
```

If the file is missing:

1. **Copy it from another Mac** that already syncs, if there is one (`ssh <alias> cat .config/technique-manager/studio.json`). That keeps both Macs on the same folder.
2. Otherwise, use `AskUserQuestion` for the folder, and for the SSH host alias (check `~/.ssh/config`) unless this Mac will only ever write locally. Then save them:

```bash
python3 "$SS/scripts/sync_studio.py" --setup --host <alias> --dest "<folder>"
python3 "$SS/scripts/sync_studio.py" --setup --dest "<folder in iCloud Drive>"   # no host: local only
```

Use a **relative** `dest` inside iCloud Drive (`Library/Mobile Documents/com~apple~CloudDocs/...`), so the same setting works on every Mac whatever the username. Point it at the dedicated subfolder that holds `content/` and `pages/`, not its parent.

## Tasks

Create with `TaskCreate`: `Check settings`, `Dry run`, `Sync`.

## Step 1: Dry run

```bash
python3 "$SS/scripts/sync_studio.py" --dry-run
```

Read three fields:
- `mode`: `local` or `ssh`.
- `kept`: the techniques already in the folder that this Mac doesn't send. They stay listed.
- `sent`: the files that would change.

In `ssh` mode it also checks that the host answers without a password prompt (`BatchMode`) and creates the folder if needed.

- **Can't reach the host:** the sandbox may have no SSH keys or config. Ask the user to run the same command themselves with `! python3 …`, so it runs in their session with their keys.
- **Permission prompt on the other Mac:** writing under `~/Library/Mobile Documents/` from SSH can need Full Disk Access for `sshd-keygen-wrapper` (System Settings → Privacy & Security). Say so if `mkdir` fails with "Operation not permitted". Listing a *parent* iCloud folder can fail this way even when writing into the dedicated subfolder works, so judge by the sync result, not by an `ls` of the parent.
- **Which host alias:** try the aliases in `~/.ssh/config` with `ssh -o BatchMode=yes -o ConnectTimeout=6 <alias> true`. The first that answers is the one to save.
- **Re-runs send only what changed**, so a second run right after the first sends nothing. Use that to confirm a sync landed.

## Step 2: Sync

```bash
python3 "$SS/scripts/sync_studio.py"            # add only; nothing there is deleted
python3 "$SS/scripts/sync_studio.py" --prune    # also remove techniques deleted here
```

`--prune` deletes files in the folder that this Mac doesn't have. The script **refuses it while the folder holds any technique this Mac never had**, because those came from another Mac, and pruning would delete them. When it does run, ask with `AskUserQuestion` first.

The script handles both rsync flavors: rsync 3.2.4+ (e.g. Homebrew) protects remote paths itself, and macOS's built-in rsync and openrsync need them quoted for the remote shell. A local folder is passed as is.

## Output

```
Synced N techniques to <dest> (local, via iCloud | ssh, <host>)
  kept     K techniques already there from other Macs (total T)
  new      content/<slug>.json, pages/<slug>.html
  updated  pages/index.html, content/index.json
Not sent: <slugs without a post page, if any>
```
