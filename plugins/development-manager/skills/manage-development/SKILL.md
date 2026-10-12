---
name: manage-development
description: Entry point for development-manager. Sends a request about local web pages to the right skill - turning page comments on, checking or removing them, or answering the comments left on a page. Does no work itself.
---

# Manage development

This skill only routes.
It reads the request, picks the skill below, and follows that skill's SKILL.md.

| The request | Skill |
|---|---|
| "turn on comments", "let me comment on the page", "set up page comments", "check comments work", "remove page comments", "undo" | `enable-page-comments` (with `--check` or `--undo` as asked) |
| "comment from my phone", "use it on the phone", "Tailscale", "turn the phone off" | `enable-page-comments` with `--phone` (or `--phone --undo`) |
| A watcher line such as `ev=thread_new`; "answer the comments", "go through the page comments", "fix what I marked" | `answer-page-comments` |
| "what is this plugin", "what can you do" | `introduce` |

## Task management

```javascript
TaskCreate({ subject: "Pick the skill", description: "Match the request to the table", activeForm: "Picking the skill" })
TaskCreate({ subject: "Follow that skill", description: "Read its SKILL.md and do what it says", activeForm: "Following the skill" })
```

## Steps

1. Match the request to the table.
   A repo with no `.page-comments/` folder has comments off, so "answer comments" there means enabling first.
2. If the request fits more than one row, or none, use `AskUserQuestion` with the rows that could fit as options, each saying what happens if picked.
3. Read the chosen skill's SKILL.md and follow it.
