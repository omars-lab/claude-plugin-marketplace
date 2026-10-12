# The review-run scope guard is differential, not clean-tree

**Status:** resolved — shipped in wiki-manager 0.6.0
**Affects:** `plugins/wiki-manager/bin/review_scope.py`,
`plugins/wiki-manager/skills/review-as-newcomer/SKILL.md`

## What was asked for

The requirement, in the user's words: *"when verdicts run, we should be on latest and only
tolerate diffs on verdicts and accompanying wiki files (fixes, nothing else)."*

The plan turned that into: refuse to run unless the working tree is clean outside
`Notes/📚 Wiki/`, checked mechanically with `git status --porcelain`.

## Why the literal reading does not work

A NotePlan vault is never clean. The app rewrites notes on its own schedule — re-serializing
markdown tables, touching daily notes, leaving `.conflict_*` files from sync. At the moment the
guard was being written, `git status` in the vault listed **68 dirty paths**, none of them anyone's
edit: reformatted table separator rows (`|---|` → `| --- |`), calendar notes from 2017, an
unrelated in-flight change in another folder.

A clean-tree precondition would therefore have failed on every single run, forever, on day one.
The predictable result is not safety — it is that the check gets bypassed or deleted the first time
someone needs to review a page, and then the requirement is enforced by nothing at all. A gate that
never passes protects nothing.

The intent behind the requirement is still exactly right: a review run should not quietly smuggle
in unrelated edits. The failure was in the test, not the goal.

## What we did instead

The guard is **differential**. It compares against the run, not against an ideal.

1. `review_scope.py --snapshot <state file>` runs at the start of a review and records every path
   git currently reports as modified, staged or untracked. That is the pre-existing dirt, and the
   run is not responsible for it.
2. `review_scope.py --verify --state <file> --page <path>…` runs at the end. It takes the set of
   paths dirty *now*, subtracts the snapshot, and fails on anything left over that is not either a
   file under `@References/@Verdicts/` or one of the articles this run named as reviewed.

So the thing actually enforced is "this run touched only verdicts and the pages it reviewed" —
which is the requirement — while vault churn the run did not cause is ignored, because blocking on
it protects nothing and costs the whole check its credibility.

"Be on latest" stays a precondition in the skill (`git fetch` + compare against the tracked
upstream), since that one *is* satisfiable.

## Notes

- Renames and copies are handled: `git status --porcelain -z` emits both the destination and the
  source path for `R`/`C` entries, and both count.
- The state file is written **outside** the repository. The selftest caught this the hard way —
  first version wrote it into the test repo, where it promptly showed up as an in-run stray and
  failed the run it was meant to be checking.

## Takeaway

When a precondition would never hold in the real environment, the check is wrong even if the
requirement behind it is right. Measure the environment before encoding an assumption about it —
running `git status` once would have shown 68 reasons the first design could not ship.
