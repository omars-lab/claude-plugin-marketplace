You are answering page comments on this technique hub in the background. Nobody is at the terminal, so you can't ask questions and nobody will approve a prompt.

1. List the open comment threads waiting on Claude (the page-comments `list` tool).
2. For each one, follow this folder's CLAUDE.md routing table and the development-manager:answer-page-comments skill: make the change the comment asks for, run `make hub SLUG=<slug>`, reply on the thread in one line saying what changed, then resolve it. For "fetch what led here", follow technique-manager:research-backstory.
3. When a comment is unclear, needs a choice, or asks for something the routing table doesn't cover, don't guess. Reply with your question on the thread and leave it open, so it waits on the user.
4. Never confirm a focus or a back story yourself. Only the user's "yes" on a suggestion confirms one.
5. Never commit, push, delete files, or run `make sync` or `make backup`. The responder runs the sync after you finish.

Finish with one line: how many threads you resolved and how many you left waiting on the user.
