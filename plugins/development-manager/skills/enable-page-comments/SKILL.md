---
name: enable-page-comments
description: Turn on comments for a repo's local web pages, in one step. Adds the Comment button to pages served on localhost, sets the repo up so Claude hears each comment and answers it, and proves the loop with a test comment. Also takes it all out again with --undo. Use when someone wants to comment on, mark up or give feedback on localhost pages, or asks to set up, check or remove page comments.
---

# Enable page comments

This skill turns page comments on in one repo, and after one run the whole loop works.
Omar opens a local page, presses C, and leaves a comment on an element or on selected text.
The comment is saved in the repo, Claude hears about it, fixes or answers it, and replies on the page.

There is no second setup step.
Answering is part of enabling: this skill also sets the repo up so that any Claude session opened in it hears comments and knows to follow `development-manager:answer-page-comments`.

## What enabling changes in the repo

Every change is small and marked, and `--undo` removes exactly these and nothing else.
The list of changes is kept in `.page-comments/install.json`.

| Where | What | Why |
|---|---|---|
| `.page-comments/` | `threads/` (one file per comment thread), `config.json`, `.gitattributes`, `.gitignore`, and the `run` launcher | Comments are saved here and tracked in git like any other file. |
| `Makefile` | A `comments` target between `# page-comments:begin` and `# page-comments:end` | One command starts the comment server. If the repo has no Makefile, none is made; the report gives the command instead. |
| `.claude/settings.json` | `"development-manager@<marketplace>": true` under `enabledPlugins`, merged into what is there | Every session opened in this repo, on any machine with the plugin installed, gets the answering skill and the watcher. The skill is not copied into the repo, so there is only one version of it. |
| `CLAUDE.md` | A short "Page comments" section between `<!-- page-comments:begin -->` and `<!-- page-comments:end -->` | It tells Claude: when the watcher prints a comment, follow `development-manager:answer-page-comments`. |

The plugin's watcher starts with every Claude Code session.
In a repo without `.page-comments/` it stops at once and prints nothing, so it costs nothing where comments are off.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/enable.mjs --detect` | Finds how the repo serves its pages, and the mode that fits | First, before enabling | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --detect --repo <repo>` |
| `scripts/enable.mjs --target <url>` | Enables, with the comment server in front of the repo's own server | The repo has a dev server (make target, npm script, Python server) | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --repo <repo> --target http://127.0.0.1:<port>` |
| `scripts/enable.mjs --root <dir>` | Enables, with the comment server serving a folder of pages itself | Plain HTML, no server | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --repo <repo> --root <dir>` |
| `scripts/enable.mjs --check` | Proves the loop: the setting, the CLAUDE.md note, the watcher, and a test comment it can see | Right after enabling, and whenever comments seem not to arrive | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --check --repo <repo>` |
| `scripts/enable.mjs --undo` | Removes everything enable added; keeps comment threads | Someone wants comments off | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --undo --repo <repo>` |
| `scripts/enable.mjs --undo --purge` | Also deletes the threads | Only after asking, and `--force` too if any thread is open | add `--purge` (and `--force`) |
| `scripts/run.template` | The launcher copied to `.page-comments/run`. It finds the installed plugin, so the make target keeps working after plugin updates | Not run by hand | — |

Re-running enable is safe.
It refreshes the launcher and the plugin path, and leaves everything else as it is.

## Task management

```javascript
TaskCreate({ subject: "Find how pages are served", description: "Run --detect and pick --target or --root", activeForm: "Finding how pages are served" })
TaskCreate({ subject: "Enable page comments", description: "Run enable.mjs with the chosen mode", activeForm: "Enabling page comments" })
TaskCreate({ subject: "Check the loop", description: "Run enable.mjs --check; every line must be ok or note", activeForm: "Checking the loop" })
TaskCreate({ subject: "Start listening in this session", description: "Start the watcher with the Monitor tool, then report", activeForm: "Starting the watcher" })
```

## Steps

1. **Find the repo.** Use the git root of the current folder, unless the person names another repo.

2. **Find how pages are served.** Run `--detect`.
   It reads the Makefile, `package.json` and the usual page folders, and says which mode fits and why.
   If it finds nothing, or the result looks wrong, use `AskUserQuestion`:

   ```javascript
   AskUserQuestion({
     questions: [{
       question: "How are this repo's pages served?",
       header: "Pages",
       options: [
         { label: "A dev server already runs (recommended when there is one)", description: "The comment server sits in front of it, so the site's own API and live reload keep working. You start both." },
         { label: "A plain folder of HTML", description: "The comment server serves the folder itself. Simplest, but no site API." }
       ],
       multiSelect: false
     }]
   })
   ```

3. **Enable.** Run enable with `--target <url>` or `--root <dir>`.
   The comment server listens on port 8766 unless `--port` says otherwise.
   The author name for page comments defaults to the first word of the git user name; pass `--author` to change it.

4. **Check.** Run `--check`.
   It confirms the plugin is on in `.claude/settings.json` and the `CLAUDE.md` note is there.
   It asks Claude Code, from the repo's folder, whether the plugin is installed and on.
   If the plugin is not installed on this machine, that line is a note, not a failure: the repo setting takes effect once it is installed.
   Then it starts a short-lived comment server on a spare port, loads a page, posts a test comment, confirms the watcher prints it, and removes the test thread.
   With `--target`, the repo's own server must be running for the page to load.
   Every line must read `ok` or `note`. Fix any `FAIL` before reporting.

5. **Start listening in this session.** The plugin's watcher starts with each new session, so the next session hears comments by itself.
   This session started before comments were on, so start the watcher now with the Monitor tool:

   ```text
   node "${CLAUDE_PLUGIN_ROOT}/shared/scripts/page-comments.mjs" watch --exclude-author claude --replay --repo <repo>
   ```

   When it prints a line, follow `development-manager:answer-page-comments`.

6. **Report in plain words.** Say:
   - which mode was used and why;
   - the command to start the comment server (`make comments`, or the printed command);
   - the URL to open, and that C starts a comment;
   - what the check showed, including the install note if there was one;
   - that `.page-comments/`, `.claude/settings.json`, `CLAUDE.md` and the Makefile changes are ready to commit, and that this skill did not commit them;
   - how to undo.

## Undo

Run `--undo`.
It stops a running comment server, but only if that process really is the comment server.
It removes the make target, the `CLAUDE.md` section and the settings entry, exactly as `install.json` recorded them.
A file or folder that enable created is removed only if it is now empty of anything else.
If the plugin was already on in the settings before enable ran, that setting stays.
Comment threads stay, with `config.json` and `.gitattributes`, because they are Omar's comments.

Delete the threads only when asked.
If any thread is still open, use `AskUserQuestion` first, then run `--undo --purge --force`.

## Don't

- Don't copy the answering skill into the repo's `.claude/skills/`. A second copy would drift from the plugin's.
- Don't commit for the person. Enabling changes files that are theirs to review.
- Don't edit the marked blocks by hand. Re-run enable or undo instead.
- Don't start the comment server on anything but `127.0.0.1`.
