---
name: introduce
description: Introduce the development-manager plugin - what it does, its skills, and how they fit together. Use when someone asks what development-manager is or what it can do.
---

# Introduce development-manager

When this skill runs, explain the plugin in plain words, then ask what the person wants to do.

## What the plugin does

development-manager helps with work on a repo's own web pages while they run on this machine.
Its first feature is **page comments**.

Omar opens a local page, presses C, and leaves a comment on an element or on selected text.
The comment is saved as a file in the repo, so git tracks it.
The page also takes a picture of the element and saves it outside the repo, by default in iCloud Drive so it shows in the Files app on the phone.
Claude hears about it, looks at the picture, fixes or answers it at the source, commits, and replies on the page.
After a fix that changes the page, Claude adds an after picture to the thread, so the two can be compared.
Claude closes the thread only once the fix is in.

Comments keep up with the page as it changes.
A comment finds its element again after an edit, even when the words changed a little, and shows "changed since this comment" when they did.
A comment whose element is gone is never pinned to a guess; it is listed under "Not found on this page", and Claude is told.
A comment made on uncommitted work notes, after the next commit, which commit took that work in.
When a session starts in a repo with comments waiting, Claude says how many.

Omar can also comment from his phone, through his own Tailscale network.
`enable-page-comments --phone` sets it up: the phone opens the Mac's tailnet address, and on a touch screen a tap picks a part of the page and **Comment here** opens the box.
Only his own Tailscale login may comment, and nothing is ever put on the public internet.

## Skills

| Skill | What it does | When to use it |
|---|---|---|
| `manage-development` | Sends a request to the right skill below | Not sure which skill fits |
| `enable-page-comments` | Turns comments on in a repo in one run: the Comment button, the repo setting that lets every session hear comments, a note in `CLAUDE.md`, and where screenshots go. Proves the loop with a test comment. `--phone` adds commenting from the phone through Tailscale. `--undo` takes it all out, but never deletes a screenshot | Once per repo, or to check or remove it; `--phone` when Omar wants the phone too |
| `answer-page-comments` | The routine Claude follows for each comment: read the comment's picture, find the source, fix or answer, check, commit, attach an after picture, reply, close when fixed | Whenever the watcher prints a comment, or to go through open comments |
| `improve-hub` | One pass over a hub (a local page listed in the hubs catalog): audit it, score it against a rubric, fix the changes worth the most, look again, log the rest | To make a hub better, or to check one before it is shared or published |
| `design-engaging-ui` | Designs or reworks a page: a short brief, two or three rendered directions to pick from, a small written design system, then build and check in the browser at desktop and phone width | When a page works but looks plain or templated, or improve-hub hands over its look rows |
| `find-design-references` | Finds two or three sites and open-source GitHub repos the page should look like, keeps them in a shared list (`references.yaml` in the hubs repo), screenshots them at desktop and phone width, and lays each of our pages beside them with a ranked list of what to change | First step of design-engaging-ui, or whenever a page "doesn't feel premium" and nobody can say why |

## How they fit together

```text
enable-page-comments   once per repo  ->  comments on, Claude listening
(Omar comments on the page)
plugin watcher         prints a line  ->  answer-page-comments runs
answer-page-comments   fix, commit, reply on the page, close when fixed
```

`improve-hub` stands on its own: it reads a hub's repo and pages, checks them against `RUBRIC.md`, and fixes on a branch for review.
It uses page comments when they are on, since Omar's own notes come before the rubric.
When the look needs real design work, it hands over to `design-engaging-ui`, which checks the page against `PRINCIPLES.md`.
`design-engaging-ui` starts with `find-design-references`, so every round is compared with real sites and repos, not only a checklist.

The plugin's watcher starts with every session.
In a repo without comments turned on, it stops at once and prints nothing.

## Task management

```javascript
TaskCreate({ subject: "Introduce the plugin", description: "Explain page comments, improve-hub, design-engaging-ui and the other skills", activeForm: "Introducing development-manager" })
TaskCreate({ subject: "Route to a skill", description: "Ask what they want and hand off", activeForm: "Routing" })
```

## Ask what they want

Use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do?",
    header: "Next step",
    options: [
      { label: "Turn on page comments here", description: "Runs enable-page-comments in this repo. Changes a few files you then review and commit." },
      { label: "Answer open comments", description: "Runs answer-page-comments on this repo's open threads. Fixes are committed one per thread." },
      { label: "Improve a hub or page", description: "Runs improve-hub to review it and fix the small things, then design-engaging-ui if the look needs real design work. Changes land on a branch you review; anything that reaches the tailnet or the internet is left for you." },
      { label: "Just learning", description: "Nothing changes. Stop here." }
    ],
    multiSelect: false
  }]
})
```
