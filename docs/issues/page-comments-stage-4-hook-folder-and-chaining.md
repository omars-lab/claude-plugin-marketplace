# Page comments: where the post-commit hook goes, and when it is skipped

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/scripts/enable.mjs`
(`hookPlace`, step 5 of `enable`, `--undo`, `--check`), `scripts/post-commit.template`

## What the design said

Section 5, item 4: the hook "is added alongside any hooks already there, never replacing them".

## What was built

Git runs exactly one `post-commit` file, so "alongside" is done by chaining:

1. enable asks git where hooks live (`git rev-parse --git-path hooks`), which follows
   `core.hooksPath` and is shared by every worktree of the repo.
2. If a `post-commit` is already there, it is renamed to `post-commit.page-comments-prev`, and
   ours runs it first with the same arguments, keeping its exit status.
3. `install.json` records the hook, whether there was one before, and its permissions. `--undo`
   removes ours only if it still carries our marker line, and renames the earlier one back, byte
   for byte and with its old permissions.
4. Re-running enable is a no-op when our hook is in place. If a `.page-comments-prev` file is
   already there next to someone else's hook, enable skips the hook rather than overwrite it.

## When the hook is skipped (a departure)

enable skips the hook, and says why in its report and in `--check`, when the hooks folder is:

- **committed to the repo** (for example `core.hooksPath = .githooks`). A hook file written there
  would be an untracked file in the working tree: every later comment would be stamped
  "uncommitted work", and the file would show in `git status` until someone committed it to a
  shared folder by mistake. A hooks folder inside the work tree is used only when git ignores it.
- **outside the repo** (a `core.hooksPath` shared by many repos). Changing it would change every
  repo that uses it.
- **turned off** (`core.hooksPath = /dev/null`).

In those repos everything else works; only the "landed in" note after a commit is missing. Someone
who wants it can call `.page-comments/run restamp` from their own committed post-commit hook.
