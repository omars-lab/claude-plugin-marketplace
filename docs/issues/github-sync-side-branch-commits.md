# GitHub sync: commits from side branches didn't apply

## What happened

On 2026-10-16, `make sync-remote` had 149 commits to send to the public GitHub copy. It replayed
about 120 of them, then stopped:

```
error: patch failed: plugins/development-manager/skills/enable-page-comments/SKILL.md:111
    ✗ f9d5f36 - apply failed
Conflict detected. Aborting.
```

Nothing was pushed. The script cleaned up and left `main` as it was.

## Why

Since the last sync, eight branches had been merged into `main`. The script replayed each commit
as a patch against its own parent, in date order. A commit made on a side branch
(f9d5f36, "Page comments: handle ports that another repo already uses") was written against a
version of that file from before another branch's edit to it had landed. By the time the
replay reached it, the GitHub copy already held that other edit, so the plain patch didn't fit.

Date order also doesn't promise that a commit comes after its parents.

## What changed in `scripts/sync-to-github.sh`

- **Parents first.** Commits are listed with `--topo-order`, so a merge comes after everything it
  brings in.
- **Three-way fallback.** When a plain patch doesn't fit, it is applied with `git apply --3way`,
  which merges it using both versions of the file. A real clash still stops the sync.
- **The end result must match `main`.** Before pushing, the GitHub copy's files are compared with
  `main`'s (leaving out the private paths). Any difference blocks the push, so a three-way merge
  that went wrong can't reach GitHub.
- **Runs from a copy of itself.** The script switches to the GitHub branch partway through, which
  rewrites the script file on disk while bash is still reading it. That was harmless only while
  both branches held the same version of the script. It now copies itself to a temp file and runs
  that.

## What was ruled out

- **Squashing all 149 commits into one.** It would have worked, but GitHub would lose the history
  of each change.
- **Keeping `main` linear.** Several sessions work on this repo at once, each on its own branch,
  so merges will keep happening. The sync has to handle them.
