---
name: enable-page-comments
description: Turn on comments for a repo's local web pages, in one step. Adds the Comment button to pages served on localhost, sets the repo up so Claude hears each comment and answers it, and proves the loop with a test comment. With --phone, also lets them comment from their phone through their own Tailscale network. Also takes it all out again with --undo. Use when someone wants to comment on, mark up or give feedback on localhost pages, from the Mac or the phone, or asks to set up, check or remove page comments.
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
| `.page-comments/` | `threads/` (one file per comment thread), `config.json`, `.gitattributes`, `.gitignore`, and the `run` launcher | Comments are saved here and tracked in git like any other file. `config.json` also says where screenshots go (`shotsDir`). |
| `Makefile` | A `comments` target between `# page-comments:begin` and `# page-comments:end` | One command starts the comment server. If the repo has no Makefile, none is made; the report gives the command instead. If one of the repo's own targets (like `serve`) already runs `.page-comments/run serve`, no `comments` target is added, and an old one is taken out: that target is the one command. |
| `.claude/settings.json` | `"development-manager@<marketplace>": true` under `enabledPlugins`, merged into what is there | Every session opened in this repo, on any machine with the plugin installed, gets the answering skill and the watcher. The skill is not copied into the repo, so there is only one version of it. |
| `CLAUDE.md` | A short "Page comments" section between `<!-- page-comments:begin -->` and `<!-- page-comments:end -->` | It tells Claude: when the watcher prints a comment, follow `development-manager:answer-page-comments`. |
| `post-commit` git hook | A small hook in the repo's own hooks folder (`.git/hooks/`, or the `core.hooksPath` folder when that is inside `.git/` or ignored by git). A post-commit hook that was already there is renamed to `post-commit.page-comments-prev` and still runs first, with its exit status kept | After each commit it notes which commit took in the uncommitted work a comment was made on, by adding one line to that comment's thread file. It never changes the commit and never stops it. When the hooks folder is committed to the repo (like `.githooks/`), shared with other repos, or hooks are off, it is skipped and the report says why |

## Where screenshots go

When Omar saves a comment, the page takes a picture of the element and saves it as a PNG.
Pictures are not kept in the repo, so they never reach git.
They go to one folder per repo and thread: `<shotsDir>/page-comments/<repo>/<thread>/`. A git worktree uses its main checkout's name, so all of a repo's pictures stay in one folder.

`shotsDir` is chosen in this order:
1. `--shots-dir <path>`, when given;
2. what the repo's `config.json` already says;
3. `shotsDir` in the global config, `~/.config/development-manager/config.json`;
4. the default, `CloudDesktop/data` in iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/data`), so the pictures show up in the Files app on the phone.

If iCloud Drive is not on this Mac, or the folder is not inside it, pictures go to `.page-comments/shots/` instead, which git ignores.
The report says which.

When the pictures go to iCloud Drive and the setting is new or changed, enable prints a privacy line: Apple keeps a copy of everything in iCloud Drive and can read it unless Advanced Data Protection is on.
Pass that line on to Omar in the report, word for word.

The plugin's watcher starts with every Claude Code session.
In a repo without `.page-comments/` it stops at once and prints nothing, so it costs nothing where comments are off.
When a session starts or resumes in a repo with comments waiting on Claude, the plugin also prints one line: how many are waiting, how many could not be found on their page, and the command to list them. In any other folder it prints nothing.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/enable.mjs --detect` | Finds how the repo serves its pages, and the mode that fits | First, before enabling | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --detect --repo <repo>` |
| `scripts/enable.mjs --behind '<cmd>'` | Enables, with the comment server starting the repo's own server behind it on a spare port, and stopping it on exit. `{port}` in the command (or `$PORT`) is that port. The command is kept in `config.json`, so `.page-comments/run serve` with no mode runs it | The repo has a dev server and Omar wants one command and one address: the pages, with comments, where he always opens them. Then change the repo's `serve` recipe to `.page-comments/run serve --port <its port> --behind '<its command, with {port}>'` and re-run enable so it drops the separate `comments` target | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --repo <repo> --behind '<cmd with {port}>' --port <port>` |
| `scripts/enable.mjs --target <url>` | Enables, with the comment server in front of the repo's own server | The repo has a dev server (make target, npm script, Python server) | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --repo <repo> --target http://127.0.0.1:<port>` |
| `scripts/enable.mjs --root <dir>` | Enables, with the comment server serving a folder of pages itself | Plain HTML, no server | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --repo <repo> --root <dir>` |
| `scripts/enable.mjs --check` | Proves the loop: the setting, the CLAUDE.md note, the watcher, and a test comment it can see; with `--vite`, a test comment on the Vite dev server's own port too | Right after enabling, and whenever comments seem not to arrive | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --check --repo <repo>` |
| `scripts/enable.mjs --shots-dir <path>` | Enables, with screenshots saved under that folder instead of the default | Omar wants the pictures somewhere else | add `--shots-dir <path>` to the enable command |
| `scripts/enable.mjs --phone` | Lets Omar comment from his phone through Tailscale: serves the comment server on the Mac's tailnet name at its own HTTPS port, and writes the phone setting (name, port, allowed login) to `config.json` | Omar wants to comment from his phone in this repo. Comments must already be on, or add `--target`/`--root` to the same run | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --phone --repo <repo>` |
| `scripts/enable.mjs --phone --undo` | Turns off only the phone: the serve entry enable added, and the phone setting. Comments on the Mac keep working | Omar wants the phone off but comments on | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --phone --undo --repo <repo>` |
| `scripts/enable.mjs --vite` | Adds the Comment button through the repo's own Vite dev server instead of a second port: copies the loader to `.page-comments/vite.mjs` (with its types, `vite.d.mts`) and adds one import and one `pageComments()` call to `vite.config` (or makes one). Dev only; a `vite build` has none of it. Refuses a CommonJS config or one without a single `plugins: [`, and says what to add by hand | The repo runs on Vite. Comments must already be on, or add `--target`/`--root` to the same run | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --vite --repo <repo> [--vite-config <file>]` |
| `scripts/enable.mjs --vite --undo` | Takes out exactly the import and the call it added, or the config it made if unchanged, and the loader | Omar wants the Vite way off but comments on | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --vite --undo --repo <repo>` |
| `scripts/enable.mjs --userscript --origin <url>` | Lists those exact page origins in `config.json`, makes the repo's own token in `.page-comments/.state/token` (ignored by git), and writes the Tampermonkey script `.page-comments/.state/page-comments.user.js` for Omar to import. The server must then run with `serve --api-only`. The script holds the token: never paste it into chat or commit it | The page's server cannot be proxied or changed. Repeat `--origin` for more pages | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --userscript --origin http://127.0.0.1:8765 --repo <repo>` |
| `scripts/enable.mjs --userscript --undo` | Removes the listed origins, the token and the script | Omar wants the userscript way off | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --userscript --undo --repo <repo>` |
| `scripts/enable.mjs --undo` | Removes everything enable added, the phone included; keeps comment threads and every screenshot | Someone wants comments off | `node "${CLAUDE_PLUGIN_ROOT}/skills/enable-page-comments/scripts/enable.mjs" --undo --repo <repo>` |
| `scripts/enable.mjs --undo --purge` | Also deletes the threads; screenshots still stay | Only after asking, and `--force` too if any thread is open | add `--purge` (and `--force`) |
| `scripts/run.template` | The launcher copied to `.page-comments/run`. It finds the installed plugin, so the make target keeps working after plugin updates | Not run by hand | — |
| `scripts/vite.template` | The loader copied to `.page-comments/vite.mjs`. It finds the installed plugin and hands Vite its `pageComments()` plugin | Not run by hand | — |
| `scripts/vite-types.template` | The loader's types, copied to `.page-comments/vite.d.mts`. Without them a `vite.config.ts` that is type-checked (`tsc --noEmit`) stops on TS7016, "Could not find a declaration file". They name no Vite types, so they need nothing installed | Not run by hand | — |
| `scripts/post-commit.template` | The post-commit hook enable installs. It runs the earlier hook first, then `.page-comments/run restamp`, and never fails a commit | Not run by hand | — |

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
   It reads the port from the serve command, including `PORT ?= 8765` set above it, and then looks at what is really listening there.
   Several repos on one Mac often share the same default port, so the port may belong to another repo's server.
   When this repo's own server is running on a different port, detect points at that one instead.
   When it is not, detect's output says `Careful:`, because pointing the comment server at another repo's site would put comments on the wrong pages.
   Start this repo's server on a free port, then run `--detect` again or pass `--target` yourself.
   If it finds nothing, or the result looks wrong, use `AskUserQuestion`:

   ```javascript
   AskUserQuestion({
     questions: [{
       question: "How are this repo's pages served?",
       header: "Pages",
       options: [
         { label: "The repo's serve starts both (recommended when there is a dev server)", description: "make serve starts the comment server, and the comment server starts the site's own server behind it (--behind). One command, one address, comments always there. Changes the repo's serve recipe." },
         { label: "A dev server already runs, in front of it", description: "The comment server sits in front of a running server on its own port (--target). The site's API and live reload keep working. You start both, and open the comment port." },
         { label: "A plain folder of HTML", description: "The comment server serves the folder itself. Simplest, but no site API." }
       ],
       multiSelect: false
     }]
   })
   ```

3. **Enable.** Run enable with `--behind '<cmd>'`, `--target <url>` or `--root <dir>`.
   With `--behind`, the comment server takes the port Omar already opens (the repo's own `serve` port), and the site's server moves to a spare one behind it.
   A server that listens on the network for a phone (like `--lan`) cannot go behind it, since the comment server only listens on `127.0.0.1`; keep that case on the plain command.
   The comment server takes the first free port from 8766 up, unless `--port` says otherwise; a re-run keeps the port it saved.
   When a port it was given is already in use, or the target is another repo's server, the report has a `careful:` line saying which process holds it and what to run instead.
   If the comment server later finds its port taken, it says who holds it and names a free port, with no stack trace.
   The author name for page comments defaults to the first word of the git user name; pass `--author` to change it.

4. **Check.** Run `--check`.
   It confirms the plugin is on in `.claude/settings.json` and the `CLAUDE.md` note is there.
   It asks Claude Code, from the repo's folder, whether the plugin is installed and on.
   If the plugin is not installed on this machine, that line is a note, not a failure: the repo setting takes effect once it is installed.
   Then it starts a short-lived comment server on a spare port, loads a page, posts a test comment, confirms the watcher prints it, and removes the test thread.
   It also checks the ports: that the comment server's port is free (or held by this repo's own comment server), and, for a local `--target`, that the server answering there is this repo's.
   A port held by another repo's server is a `FAIL` that names the process and the fix.
   With `--target`, the repo's own server must be running for the page to load.
   With `--vite` too, it also posts a test comment on the Vite dev server's own port, the one Omar opens; if that server is not running, or has not been restarted since enable, that line is a note saying so.
   Every line must read `ok` or `note`. Fix any `FAIL` before reporting.

5. **Start listening in this session.** The plugin's watcher starts with each new session, so the next session hears comments by itself.
   This session started before comments were on, so start the watcher now with the Monitor tool:

   ```text
   node "${CLAUDE_PLUGIN_ROOT}/shared/scripts/page-comments.mjs" watch --exclude-author claude --replay --repo <repo>
   ```

   When it prints a line, follow `development-manager:answer-page-comments`.

6. **Report in plain words.** Say:
   - which mode was used and why;
   - the command to start the comment server (`make serve` when the repo's serve runs it, `make comments`, or the printed command);
   - the URL to open, and that C starts a comment;
   - what the check showed, including the install note if there was one;
   - where screenshots go, and the privacy line if enable printed one;
   - whether the post-commit hook went in, and if it was skipped, the reason enable gave;
   - that `.page-comments/`, `.claude/settings.json`, `CLAUDE.md` and the Makefile changes are ready to commit, and that this skill did not commit them;
   - how to undo.

## From the phone

Only when Omar asks to comment from his phone. Enabling does not ask, and does not turn it on.

The comment server still listens only on `127.0.0.1`.
Tailscale Serve, on the Mac, takes HTTPS on the Mac's tailnet name and passes it on, so only devices in Omar's own tailnet can reach it.
Tailscale tells the server who is on the other end, and only logins on the repo's allow list may comment.

1. **Turn it on.** Run `--phone`.
   It needs Tailscale installed, running and signed in, with MagicDNS and HTTPS certificates on for the tailnet.
   If one is missing, it stops and says which, and changes nothing.
   It serves the comment server's port (8766 unless `--port` said otherwise) as its own HTTPS port, so any other `tailscale serve` entry on the Mac is left alone.
   If that port already serves something else, it stops and changes nothing.
   The allow list starts with the login signed in on this Mac, and comments from it carry the repo's author name.
2. **The comment server must be running** on the Mac (`make serve` or `make comments`, whichever the report named) for the phone to load the page.
   A server that was already running picks up the phone setting by itself.
3. **Report in plain words.** Say:
   - the address to open on the phone, `https://<mac>.<tailnet>.ts.net:<port>/`, as enable printed it;
   - on the phone, **Comment** turns comment mode on, a tap picks a part of the page, and **Comment here** opens the box; selected text gets **Comment on selection**;
   - the privacy line enable printed about `config.json` and `install.json` naming the Mac's tailnet and the login, word for word;
   - how to turn the phone off: `--phone --undo`, or `tailscale serve --https=<port> off`.

**Never Tailscale Funnel.** Funnel puts a local port on the public internet.
enable refuses any Funnel flag and never runs a Funnel command, and it never runs `tailscale serve reset`, which would remove every entry on the Mac.

## Undo

Run `--undo`.
It stops a running comment server, but only if that process really is the comment server.
If the phone was on, it turns off the `tailscale serve` entry, but only if enable added it and it still points at the comment server.
It removes the make target, the `CLAUDE.md` section and the settings entry, exactly as `install.json` recorded them.
It removes the post-commit hook only if it is still the one enable wrote, and puts back the hook that was there before, byte for byte and with its old permissions.
A file or folder that enable created is removed only if it is now empty of anything else.
If the plugin was already on in the settings before enable ran, that setting stays.
Comment threads stay, with `config.json` and `.gitattributes`, because they are Omar's comments.
Screenshots always stay, even with `--purge`: in iCloud Drive they are never touched, and in `.page-comments/shots/` the folder stays with the `.gitignore` that keeps it out of git.
Delete them by hand if they are no longer wanted.

Delete the threads only when asked.
If any thread is still open, use `AskUserQuestion` first, then run `--undo --purge --force`.

## Don't

- Don't copy the answering skill into the repo's `.claude/skills/`. A second copy would drift from the plugin's.
- Don't commit for the person. Enabling changes files that are theirs to review.
- Don't edit the marked blocks by hand. Re-run enable or undo instead.
- Don't start the comment server on anything but `127.0.0.1`. The phone reaches it through `tailscale serve`, never by listening on the network.
- Don't use Tailscale Funnel, and don't run `tailscale serve reset`.
