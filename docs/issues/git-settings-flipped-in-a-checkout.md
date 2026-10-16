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
