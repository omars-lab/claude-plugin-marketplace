# A checkout's git settings got flipped, and nothing said so

## What happened

In 2026-10, a repo's main checkout was found with `core.bare = true` in its `.git/config`.
`core.hooksPath` was also set to an absolute path. Several Claude sessions were working in that
checkout and in worktrees made from it at the time.

- With `core.bare = true`, git no longer treats the folder as a checkout. Status, commit and
  merge fail with "must be run in a work tree".
- With an absolute `core.hooksPath`, every worktree runs the main checkout's hooks instead of its
  own. Those hooks may be on a different branch, or gone once the folder moves.

Setting `core.bare false` and `core.hooksPath .githooks` (relative) fixed it.
We never found the cause. git keeps no history of its settings, and the timing only matched
another session's activity.

## Why a hook

The repo's `make init-hooks` sets `core.hooksPath` when it runs, but nothing checked it
afterwards. Nothing checked `core.bare` at all. The breakage showed up only as confusing git
errors, so each session that hit them had to work the cause out again.

## What replaced it

`guardrail-manager`'s `git-settings-guard.py`, on by default in every repo:

- **At session start**, it reads both settings for the checkout. When one is wrong, it says
  which and prints the exact fix command. It never changes the setting itself, so the person
  decides.
- **Before git commands**, it repeats that report, at most once every ten minutes per problem
  per session.
- **It denies** a `git config` that would set `core.bare true`. It also denies setting a
  repo's `core.hooksPath` to an absolute, `~`, `$VAR` or `../` path. A `--global` or
  `--system` hooks folder is allowed, because a machine-wide hooks folder is a normal setup.

The hook can't catch a script or a tool outside Claude that changes the settings. The
session-start report is what catches those afterwards.

## 2026-10-31: the absolute `core.hooksPath` came from Claude Code itself

It happened again in another repo's main checkout. Its Makefile and its own session-start script
both set the relative `.githooks`, yet the checkout ended up with
`core.hooksPath = <repo root>/.githooks`.

**The cause.** Claude Code's own worktree setup (version 2.1.316, read from the installed binary)
does this right after it makes a worktree for EnterWorktree, an Agent call with
`isolation: "worktree"`, or `claude --worktree`:

1. It reads the main checkout's `core.hooksPath`.
2. When that value is relative, it turns it into an absolute path under the main checkout.
3. It runs `git config core.hooksPath <absolute path>` inside the new worktree, and logs
   "Configured worktree to use hooks from main repository".

A plain `git config` run in a linked worktree writes to the config every worktree shares (unless
the repo turned on `extensions.worktreeConfig`). So each new Claude worktree flips the main
checkout to the absolute path. A probe confirmed it: in a throwaway repo with `core.hooksPath =
.githooks`, one `claude --worktree probe -p ...` run left the shared config at
`<repo>/.githooks`. The guard's deny can't stop it, because Claude Code runs that
`git config` itself, not through the Bash tool. A plain Bash `git worktree add` does not do this.

**What changed in the guard (guardrail-manager 1.9.0).**

- It now fixes this one case by itself: an absolute `core.hooksPath` that points at the repo's own
  hooks folder is set back to the relative path, and it says what it changed. The relative path
  names the same committed hooks in every worktree, so the fix is safe. It makes the fix only
  when that folder exists in the checkout being checked. It never makes it when `core.bare` is
  true, or for `.git/hooks`. Everything else is still only reported. `AUTO_FIX=0` turns the fix
  off.
- It runs right after a worktree is made: PostToolUse on Bash (only for `git worktree add`),
  EnterWorktree, and Agent (only with `isolation: "worktree"`).
- It does not use the WorktreeCreate hook event. A WorktreeCreate hook replaces Claude Code's own
  worktree creation and has to print the new worktree's path, so a guard there would break every
  worktree.
