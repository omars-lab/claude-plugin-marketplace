---
name: design-engaging-ui
description: Design or rework a local web page or hub so it looks appealing and is engaging to use - a short brief, two or three rendered directions to choose from, a small written design system, then build and check it in the browser at desktop and phone width until it matches. Use when asked to "make this page look good", "make it more engaging", "redesign the dashboard", "give the hub a proper look", "it looks like a default AI page", "design the UI for this", or when improve-hub logs look rows (L1 to L6) that need design work rather than a one-line fix.
---

# Design an engaging UI

This skill takes one page, or a whole hub, from "it works" to "it looks good and people want to
use it". It is the design half of the work. `improve-hub` is the review half: it scores a hub and
fixes small things, and it hands the look rows that need real design work to this skill.

Read [PRINCIPLES.md](PRINCIPLES.md) now, every time. It holds what "appealing" and "engaging"
mean here, as checks you can see on the page, and it can change without this skill changing.

It builds on other skills rather than repeating them. Use each when it is installed, and go on
without it when it isn't:

| Skill | Use it for |
|---|---|
| `frontend-design` (Anthropic's official plugin) | Picking a direction that is the page's own, not the templated default |
| `ui-ux-pro-max` / its `design-system` skill | Palettes, font pairings, token layers, component specs |
| `visual-site-review` | The screenshot critique, and checking a fix by looking again |
| `development-manager:improve-hub` | The catalog side of a hub (ports, privacy, site map) and the score before and after |
| `development-manager:answer-page-comments` | Omar's notes on the page, which come before anything here |

## Rules

- **Render before choosing.** A direction is chosen from rendered pages side by side, never from
  a description. Show the options, then ask.
- **Work in a worktree of the page's repo,** on a branch for Omar to review. Run
  `git branch --show-current` before each commit, and stage files by name.
- **Keep the data real.** Shots are taken with the page's real data, so they stay in the session's
  scratch folder or the repo's ignored cache. They are never committed or sent anywhere.
- **Change the look, not what the page does.** If a design idea needs a new feature or a change to
  what is stored, write it down as a question for Omar instead.
- **Keep the repo's tests green.** Tests that find elements by text or role break when labels move.
  Run them after each round.

## Task management

```javascript
TaskCreate({ subject: "Write the brief", description: "Who uses it, its one job, the first action, three words for how it should feel", activeForm: "Writing the brief" })
TaskCreate({ subject: "Render directions", description: "Two or three directions on the real page, side by side; Omar picks", activeForm: "Rendering directions" })
TaskCreate({ subject: "Write the design system", description: "Tokens in one file plus docs/design.md", activeForm: "Writing the design system" })
TaskCreate({ subject: "Build and check", description: "Structure, states, feedback, motion; screenshot at 1280 and 390, fix, repeat", activeForm: "Building and checking" })
TaskCreate({ subject: "Score and report", description: "PRINCIPLES.md before and after; what changed; what is left", activeForm: "Scoring and reporting" })
```

## Steps

1. **Look first.**
   - Open the page at 1280 and 390 px wide and screenshot every main view, or use the hubs repo's
     `make sitemap HUB=<id>` when it is a hub.
   - Read the console.
   - Score it against PRINCIPLES.md, and keep that table as the "before".
   - If the repo has open page comments, answer them first with `answer-page-comments`.
2. **Write the brief.** Write five lines at the top of `docs/design.md` in the repo:
   - who opens this page;
   - the one job it does for them;
   - the first thing they should do;
   - why they would come back tomorrow;
   - three words for how it should feel (for example "calm, exact, warm").

   Take these from the repo's README, the page itself and the chat. Ask Omar only for what none of
   those answer.
3. **Render two or three directions.**
   - Each direction is a real restyle of the page's main view, not a mockup: a palette, a type
     pairing, a spacing and corner style, and one signature detail.
   - Build each behind a query flag or a class on `<body>`, so all of them run on the same data.
   - Screenshot each at 1280 and 390, and put them side by side in one artifact or image.
   - Then ask with `AskUserQuestion`: one option per direction, the recommended one first. Each
     option says what it does well, what it gives up, and what it commits the page to (for
     example "dark only" or "needs a web font").
   - Use `frontend-design` to push each direction away from the default. Use `ui-ux-pro-max` for
     palettes and pairings when it is installed.
4. **Write the design system** for the chosen direction.
   - Put the tokens in one file the whole page reads, such as CSS variables in `:root` or a theme
     file: colours (neutrals plus one accent, with light and dark values), the type scale, the
     spacing scale, radius, shadow and motion timing.
   - Write the same values in `docs/design.md` under the brief, with one line on why each was
     picked.
   - Delete the directions that were not chosen.
5. **Build, then check, two to four rounds.**
   - Apply the system everywhere, replacing values written inline with the tokens.
   - Then go through PRINCIPLES.md group by group: hierarchy, design system, states, feedback,
     motion, engagement, accessibility.
   - After each round, screenshot at 1280 and 390, compare with the chosen direction and the
     brief, and list what is off. Fix it and go again. Stop when a round finds nothing worth
     fixing. It is not done because the build passes.
   - Run the repo's tests and a Lighthouse or axe scan. Then read the labels and headings
     yourself, since the scanners pass an image described as "image".
6. **Score and report.**
   - Score the page against PRINCIPLES.md again.
   - If it is a hub, run `improve-hub`'s audit too, so the catalog checks didn't regress.
   - Commit one change per group, naming the principle ids.
   - Report the before and after shots side by side, the score, the commits, and the questions
     for Omar.

## Output

```
<page>: 11 of 24 principles before, 21 after (3 not checked)
Direction: "Ledger" (warm paper, one rust accent, serif headings), picked over "Console" and "Studio"
System:    tokens in src/theme.css, written up in docs/design.md
Commits:   H1-H3 hierarchy (abc1234), S1-S4 states (def5678), F1-F3 feedback (0a1b2c3)
For you:   E2 a "since your last visit" strip needs a last-seen timestamp stored; worth adding?
Branch:    design/<date> in <repo>-design, ready for review
```

## When to add a principle

At the end, ask: did this page have a problem PRINCIPLES.md didn't name, and could it come up
on another page? If so, add a principle (PRINCIPLES.md, "Adding a principle") on the branch this
skill lives on, and bump the plugin version.
