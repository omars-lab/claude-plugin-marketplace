---
name: improve-hub
description: Review one of Omar's hubs (a local web page listed in the hubs catalog through its repo's hub.yaml) and make it better - score it against a rubric, fix the changes worth the most for the effort, look again, and log the rest in that repo's backlog. Use when asked to "improve this hub", "review the hub", "what's wrong with this hub", "make the hub better", "polish the dashboard", or to check a hub before sharing it on the phone or publishing it.
---

# Improve a hub

A **hub** is one of Omar's local web pages, listed on the hubs page because its repo has a
`hub.yaml`. This skill takes one hub through a single pass:

1. look at it;
2. score it against [RUBRIC.md](RUBRIC.md);
3. fix the few changes worth the most;
4. look again;
5. log the rest.

It builds on other tools rather than repeating them:

- the hubs repo's `make check`, `make router-check` and `make sitemap`;
- `visual-site-review`, for the screenshot critique;
- `frontend-design`, for design fixes;
- `answer-page-comments`, for comments Omar left on the page.

Read RUBRIC.md now, every time. It can change without this skill changing.

## Rules, because this edits another repo

- **Work in a worktree of the hub's repo** (`git worktree add ../<repo>-improve -b improve-hub/<date> origin/<main>`). Other sessions often have that checkout open.
- Run `git branch --show-current` before each commit, stage files by name, and never touch files you didn't change, including another session's untracked ones.
- **Fixes land on a branch for Omar to review.** Never push to main, publish, deploy or open a pull request without his OK in the chat.
- **Never put a hub on the tailnet or the internet yourself.** That means no `tailscale serve`, no `make phone-on` and no binding wider than `127.0.0.1`. Hand Omar the `! <command>` line to run.
- Site-map shots show the hub's real contents. They stay in the hubs repo's `.cache/`, and they are never committed or sent anywhere.
- A finding that touches something you didn't start, such as a server another session runs or a file another session owns, is reported, not fixed.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/audit_hub.py` | Checks the rubric's script rows: in the catalog, the catalog check, port written in config, Vite `strictPort`, listening on this Mac only (any worktree of the repo), running on the `hub.yaml` port, write requests and whether they are exposed, page comments, site-map age and failed pages. Reads only. Exit 1 on any FAIL | Step 1 of every pass, and again at the end to show the change | `uv run "${CLAUDE_PLUGIN_ROOT}/skills/improve-hub/scripts/audit_hub.py" --repo <repo> [--hub <id>] [--hubs <hubs repo>] [--json]` |

The hubs catalog repo is found from `--hubs`, then `$HUBS_REPO`, then `~/Workspace/git/hubs`.
Without it, the catalog and site-map rows say SKIP and the rest still run.

## Task management

```javascript
TaskCreate({ subject: "Audit the hub", description: "audit_hub.py, a site map, and a look at the pages", activeForm: "Auditing the hub" })
TaskCreate({ subject: "Score and rank", description: "Every rubric row: pass, fail or not checked; failures ranked by ROI", activeForm: "Scoring the hub" })
TaskCreate({ subject: "Fix the top items", description: "In a worktree, one commit per fix", activeForm: "Fixing the top items" })
TaskCreate({ subject: "Look again", description: "Re-run the audit and the site map; compare before and after", activeForm: "Checking the fixes" })
TaskCreate({ subject: "Log the rest and report", description: "Backlog lines in the hub's repo; report to Omar", activeForm: "Logging and reporting" })
```

## Steps

1. **Audit.**
   - Find the repo and the hub id: the `id:` under `hubs:` in its `hub.yaml`. `make list` in the hubs repo shows them all.
   - Run `audit_hub.py`.
   - If the hub's server is running, make a site map (`make -C <hubs repo> sitemap HUB=<id>`). Open `index.html` and look at every shot. If the server isn't running, start it from the hubs page or its make target, or ask Omar; don't start a server another session owns.
   - Then go through the rubric's look rows, using the shots and the browser tools at desktop and phone width. Read the console.
   - Run `answer-page-comments` first if the repo has open comments: Omar's own notes outrank the rubric.
2. **Score.** Write one table: every rubric row with PASS, FAIL or NOT CHECKED, and a one-line reason. Keep it in the session's scratch folder.
3. **Rank.** Sort the failures by ROI, highest first. Raise any row that exposes data or blocks Omar. A failure that needs Omar's decision (anything that reaches the tailnet, a design direction, a published copy) goes to the report as a question, not into the fix list.
4. **Fix the top items.**
   - In the worktree, take failures from the top until the next one is large, risky or needs a decision. That is usually three to five.
   - Use one commit per fix, and name the rubric id in the message.
   - Keep each fix to what the row asks.
5. **Look again.**
   - Re-run `audit_hub.py` and make the site map again. Put the before and after shots side by side and read them.
   - A fix that doesn't show in the after shot isn't done.
   - Run the repo's own tests if it has them.
6. **Log the rest.**
   - Add one line per remaining failure to the hub repo's backlog (`docs/tasks/backlog.md` or whatever task file that repo uses), with the rubric id and the fix.
   - If the same problem keeps coming back across hubs, add or sharpen a rubric row instead of logging it again.
7. **Report** in plain words:
   - the score before and after;
   - what was fixed, with commits;
   - what is waiting on Omar, and why. Ask each of these with `AskUserQuestion`: two to four options, the recommended one first, each saying what it buys, what it costs, and what it commits him to;
   - what was logged;
   - the branch to review.

## Output

```
<hub>: 9 of 15 rows passing before, 13 after (2 not checked)
Fixed:   P1 port written in vite config (abc1234), P2 strictPort (abc1234), L3 phone width on /posts (def5678)
For you: P3 the server listens on a tailnet address; run `! <command>` to move it behind tailscale serve
Logged:  L5, A2 in docs/tasks/backlog.md
Branch:  improve-hub/<date> in <repo>-improve, ready for review
```

## When to add to the rubric

At the end of a pass, ask: did this hub have a problem the rubric didn't name? If the same problem
could show up in another hub, add a row (RUBRIC.md, "Adding a row") in the same branch as this skill
lives on, and bump the plugin version.
