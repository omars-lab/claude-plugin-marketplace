# Page comments: enabling also sets up the answering

**Status:** resolved in development-manager 1.0.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/`,
`docs/design/localhost-comments/design.md` sections 8 and 17

## What the design called for

`enable-page-comments` set up the button and the comment server: `.page-comments/`, a make target
and `install.json`. Answering was left to whoever had the plugin turned on. The check posted a
test comment and confirmed `watch` printed it.

## Why that was not enough

A repo with comments on, opened in a session where `development-manager` is not turned on, has a
Comment button that nobody listens to. Comments pile up as files and Claude never hears of them.
Nothing in the repo told a new session the comments exist or which skill answers them.

## What we did instead

One enable run now also makes the repo answerable:

- **The plugin is turned on in the repo's committed `.claude/settings.json`,** under
  `enabledPlugins`, as `development-manager@<marketplace>`. The marketplace name is read from the
  plugin's own marketplace file. Every session opened in that repo then loads the plugin, its
  watcher and its skills.
- **A short block in the repo's `CLAUDE.md`,** between `<!-- page-comments:begin -->` and
  `<!-- page-comments:end -->`, says comments live in `.page-comments/threads/` and that
  `development-manager:answer-page-comments` is the routine for them.
- **The skill is not copied into the repo's `.claude/skills/`.** A copy would go stale with each
  plugin update, and the plugin setting already makes the skill visible. No strong reason to copy
  it turned up.

`install.json` records each change with what was there before: whether the file existed, whether
the `enabledPlugins` object existed, and whether the key was already set. `--undo` reverses only
what enable added. A key Omar had set himself stays. A `CLAUDE.md` that enable created is deleted;
one that already existed loses only the marked block.

## How the check proves it

`enable.mjs --check` runs from the repo's folder:

1. The settings key is present, and the `CLAUDE.md` block names the skill.
2. `claude plugin list --json`, run in that folder, shows the plugin. On a machine where the
   plugin is not installed yet, this prints a note, not a failure. `enabledPlugins` turns a
   plugin on; it does not install it on a machine that does not know the marketplace.
3. The plugin's monitor is set to start in every session (`when: always`).
4. A throwaway server (`serve --port 0 --throwaway`, which leaves the real server's record alone)
   takes a test comment starting `[enable check]`. `watch --once` must print its `ev=thread_new`
   line. The thread file is then deleted and the server stopped.

`answer-page-comments` dismisses any `[enable check]` thread a failed check leaves behind.

Checked on a throwaway adventures worktree: every line of the check was ok, the settings diff
added one key, and `--undo` left `git status` clean.
