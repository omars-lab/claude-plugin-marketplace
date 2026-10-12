# Publishing to GitHub stopped at a merge commit

**Status:** fixed in `scripts/sync-to-github.sh`, with a case in `scripts/test-never-public.sh`
**Affects:** `make sync-remote`

## What happened

On 2026-10-12, `make sync-remote` stopped with "apply failed" at a20d275 and pushed nothing. That
commit merges main into the instagram-manager branch, and main had been published to GitHub an
hour earlier.

The sync replays each new commit onto the GitHub copy as a patch, taken from the commit's
first parent. For an ordinary commit that is the commit's own change. For this merge, the first
parent is the instagram branch, so the patch held all of main's page-comments work. GitHub
already had those files, so the patch would not apply ("already exists in index").

## What changed

A merge now brings the GitHub copy to the merge's own files: the patch is taken from the GitHub
copy's current state to the merge, minus the private paths. Ordinary commits are replayed as
before. When both sides were already published, the merge's patch is empty or holds only what the
merge itself resolved.

`make test-never-public` now builds that case: main work published first, then a side branch
that merges main and lands on main. It failed before the change and passes after it.
