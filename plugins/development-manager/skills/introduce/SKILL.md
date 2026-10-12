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
Claude hears about it, fixes or answers it at the source, commits, and replies on the page.
Claude closes the thread only once the fix is in.

## Skills

| Skill | What it does | When to use it |
|---|---|---|
| `manage-development` | Sends a request to the right skill below | Not sure which skill fits |
| `enable-page-comments` | Turns comments on in a repo in one run: the Comment button, the repo setting that lets every session hear comments, and a note in `CLAUDE.md`. Proves the loop with a test comment. `--undo` takes it all out | Once per repo, or to check or remove it |
| `answer-page-comments` | The routine Claude follows for each comment: look, find the source, fix or answer, check, commit, reply, close when fixed | Whenever the watcher prints a comment, or to go through open comments |

## How they fit together

```text
enable-page-comments   once per repo  ->  comments on, Claude listening
(Omar comments on the page)
plugin watcher         prints a line  ->  answer-page-comments runs
answer-page-comments   fix, commit, reply on the page, close when fixed
```

The plugin's watcher starts with every session.
In a repo without comments turned on, it stops at once and prints nothing.

## Task management

```javascript
TaskCreate({ subject: "Introduce the plugin", description: "Explain page comments and the three skills", activeForm: "Introducing development-manager" })
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
      { label: "Just learning", description: "Nothing changes. Stop here." }
    ],
    multiSelect: false
  }]
})
```
