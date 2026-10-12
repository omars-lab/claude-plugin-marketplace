# Page comments: the post-commit hook adds the landing commit instead of swapping the stamp

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/shared/scripts/lib/restamp.mjs`, `lib/store.mjs`
(`addLanded`, the `landed` event), `schema/thread.schema.json` (`rev.landed`),
`skills/enable-page-comments/scripts/post-commit.template`

## What the design said

Section 5, item 4: "a post-commit hook swaps a 'made against uncommitted work' stamp for the
commit that landed the work". Thread files are append-only, so a swap cannot mean rewriting the
first line.

## What was built

After each commit, the hook runs `page-comments restamp`. For each thread stamped
`rev.git = {commit: <parent>, dirty: true}` with no landing commit yet, it appends one line:

```json
{"v":1,"ts":"…","ev":"landed","author":"git","commit":"7257ce4","from":"41ab3fb"}
```

The fold adds `rev.landed = {commit, ts}`; the first `landed` event wins. `rev.git` stays as it
was, so the thread still says where the comment was made, and `rev.landed` says where that work
went. `pc show` prints both: `Made at: commit 41ab3fb, with uncommitted changes` and
`Landed in: commit 7257ce4`.

`rev.landed` is a new, optional field in the shared thread shape (section 12). Readers that do not
know it ignore it, which section 12 already requires.

## Why not swap

- Rewriting the first line breaks the rule that thread files are only ever appended to, which is
  what makes merges of thread files across branches safe.
- Keeping both answers two questions: "what was on screen when this was written" (`rev.git`)
  and "which commit has that code" (`rev.landed`).

## It is a guess, so it is kept narrow

The hook cannot know which uncommitted changes the comment was about. It stamps only when all of
these hold:

- the thread was made on uncommitted work on the commit that is now the new commit's parent;
- the new commit has exactly one parent (not a merge, not the first commit);
- no rebase, cherry-pick, revert, merge or sequencer run is in progress;
- the commit changes something outside `.page-comments/` (a commit of only thread files did not
  land page work).

Not handled: an `--amend` or a later rebase leaves `rev.landed` pointing at the old commit. The
comment's anchors and text still say what it was about, and the old commit stays reachable through
the reflog for a while. A comment made on uncommitted work that lands over several commits points
at the first one.

The hook never fails or slows a commit: errors are swallowed, it prints one line only when it
stamped something, and the hook that was there before runs first with its exit status kept.
