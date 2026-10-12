# Page comments: the session-start notice is a shell script that starts Node only when needed

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/hooks/hooks.json`, `hooks/session-start.sh`,
`shared/scripts/page-comments.mjs` (`notice`)

## What the design said

Section 7: a session-start notice, as a plugin hook, in any repo with open threads. "Does nothing
in repos without `.page-comments/`."

## What was built

`hooks.json` runs `hooks/session-start.sh` on `startup` and `resume` (not after `/clear` or a
compaction, which would repeat it inside one session). The shell script walks up from the session's
folder to the git root looking for `.page-comments/threads/` with at least one thread file, the
same way the command line finds a repo. Only then does it start Node to count threads waiting on
Claude.

It prints one line, or nothing:

```text
Page comments: 3 comment threads are waiting on Claude in this repo (1 not found on its page). List them with: .page-comments/run list --open --waiting claude
```

## Why a shell script first

Starting Node costs 40 to 50 ms on this Mac. Every session in every repo runs the hook, and most
repos have no comments, so the shell check keeps those at about 10 ms with no output. Measured:
about 45 ms in a repo with waiting threads, about 9 ms in a repo without page comments.

## Limits

- It needs `node` on the PATH that Claude Code gives hooks; without it, the hook prints nothing.
- The list command it prints uses the `.page-comments/run` launcher, which enable writes. A repo
  whose launcher was removed by `--undo` but whose threads were kept still gets the notice.
