---
name: manage-saves
description: Route Instagram saved-post work to the right step — import a new export, tag, split into items, fetch media, extract stills, build the hub, or send a topic to another repo. Use when someone asks to "do something with my Instagram saves" without naming a step, or asks what to run next.
---

# Manage Saves

The router for instagram-manager. Work out where the user's saves are in the pipeline, then hand
off to the skill for the next step.

## Step 1: Look at the data repo

The data repo is `$INSTAGRAM_HOME` (default `~/Workspace/git/instagram`). Check what exists:

| If this is missing... | The next step is |
|---|---|
| `.cache/saves.json` | **import-saves** |
| `data/tags.yaml` | tag-saves *(coming)* |
| `data/items/` | split-saves *(coming)* |
| `.cache/media/` | fetch-media *(coming)* |
| `.cache/stills/` | extract-stills *(coming)* |
| the hub build | build-hub *(coming)* |

A newer export zip than the one `saves.json` came from also means: run **import-saves** again.

## Step 2: Ask only when it forks

If the next step is clear, say it and run it. Use `AskUserQuestion` only when the user has to
pick a scope — all saves, or one set of collections first (for example a pilot on one city's
collections before the rest). Each option says what it covers and roughly how long it takes.

## Step 3: Track the run

For more than one step, add a task per step with `TaskCreate` and mark each done as it finishes.

## Routing table

| They say... | Skill |
|---|---|
| "I have a new export" / "import my saves" | `import-saves` |
| "which collections do I have?" | `import-saves` (`--list`) |
| "what's next?" | this skill, Step 1 |

## Rules every step keeps

- Read only the `saved/` files of the export. Never unpack messages or the rest.
- Never log in to Instagram or use cookies.
- Nothing personal (handles, collection names, post codes) goes into this public plugin; it all
  stays in the data repo.
