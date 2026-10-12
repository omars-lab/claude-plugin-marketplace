# Page comments: the watcher starts with every session

**Status:** resolved in development-manager 1.0.0
**Affects:** `plugins/development-manager/monitors/monitors.json`,
`docs/design/localhost-comments/design.md` section 7

## What the design called for

The monitor entry used `"when": "on-skill-invoke:answer-page-comments"`. The watcher would start
the first time the answering skill ran in a session.

## Why that did not work

Nothing runs `answer-page-comments` until a comment has already been noticed. In a new session,
Omar leaves a comment on the page, and the watcher that would print its line has not started,
because the skill that starts it is waiting for that line. The loop never closes unless Omar types
"answer the comments" in the chat. That defeats the point of commenting on the page.

## What we did instead

The monitor runs with `"when": "always"`. The design had already made this safe: the watcher's
first step is to look for `.page-comments/` from the working folder up to the git root. Where it
finds none, it exits at once, prints nothing and writes no log. So in every repo without comments
turned on, the always-on monitor costs one short process and no lines.

Two gaps remain, and the skills cover them:

- **The session that ran enable.** Its monitors started before `.page-comments/` existed, so its
  watcher has already exited. `enable-page-comments` tells Claude to start
  `page-comments watch --exclude-author claude --replay` with the Monitor tool in that session.
- **A session working from another repo.** `answer-page-comments` starts the watcher with
  `--repo <path>` under the Monitor tool, as before.

Checked on a throwaway adventures worktree: the watcher printed `ev=thread_new` for a comment left
in the browser, and exited with code 0 by itself once `--undo` removed `.page-comments/`.
