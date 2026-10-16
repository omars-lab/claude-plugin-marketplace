---
name: manage-hub
description: Entry point for working the technique hub day to day. Sends a request to the right place - what's waiting, answering page comments, fetching a technique's back story, rebuilding or serving the hub, backup and studio sync, or turning the background comment responder on or off. Does no work itself. Use when someone asks "what's waiting in the hub", "answer my comments", "work the hub", or about the responder.
---

# Manage the Technique Hub

This skill only routes. It reads the request, picks a row below, and follows that skill's SKILL.md or runs that target. Run everything from the hub (`~/workspace/technique-hub`, or the root in `~/.config/technique-manager/settings.json`).

| The request | Where it goes |
|---|---|
| "what's waiting", "what needs me", "where are we" | `make hub`, then summarize `.cache/hub/waiting.html`'s sections (the build prints their counts) and `make status` |
| A watcher line (`ev=thread_new`), the session-start "comments waiting" line, "answer the comments", "go through my notes on the pages" | `development-manager:answer-page-comments`, using the routing table in the hub's `CLAUDE.md` for which edit each comment asks for |
| "fetch what led here", "get the PR", "find the back story", a technique with no context | `research-backstory` |
| "this is the point", "trim the post", "posted at <url>" said in the terminal, not on a page | The hub `CLAUDE.md` routing table, then `make hub SLUG=<slug>` |
| "rebuild", "serve the hub", "open the hub", "comment on the pages" | `make hub` or `make serve` (see `build-hub` Step 3 and 4) |
| "back up", "sync to the studio" | `make backup`, `make sync` (`build-hub`: Backup and the session hook) |
| "answer comments while I'm away", "turn the responder on/off", "is the responder running" | `make responder-on`, `responder-off` or `responder-status` (`build-hub`: Background responder). These need a Mac terminal, because they use launchd |
| "set up a hub", "migrate", "turn on comments" | `build-hub` |
| A new screenshot to add | `recreate-technique`, then `make hub` |
| "what is this plugin" | `introduce` |

## Task management

```javascript
TaskCreate({ subject: "Pick the route", description: "Match the request to the table", activeForm: "Picking the route" })
TaskCreate({ subject: "Follow it", description: "Read that skill's SKILL.md or run that target", activeForm: "Following the route" })
```

## Steps

1. Match the request to the table. A hub with no `.page-comments/` folder has comments off, so "answer comments" there means `build-hub` Step 4 first.
2. If the request fits more than one row, or none, use `AskUserQuestion` with the rows that could fit as options, each saying what happens if picked.
3. Follow the chosen skill or target. Before replying on any comment, run `make hub SLUG=<slug>`, so the page shows the change the reply describes.
4. **"What's waiting":** answer in this order: replies waiting on the user, suggestions to confirm, sessions not archived yet, then no focus and no context. Give a count for each, and 2–3 titles for the first non-empty one. End with the single most useful next action.

## Output

```
Waiting: 2 replies for you · 1 suggestion to confirm · 0 sessions at risk · 11 no focus · 10 no context
Next: confirm the suggested focus on "<title>" (reply "yes" on its Post plan)
```
