---
name: manage-saves
description: Route Instagram saved-post work to the right step — import a new export, tag saves by topic and place, look up missing places, pin the spots a caption names, read places off reels' videos, fetch thumbnails or videos, or build the hub map. Use when someone asks to "do something with my Instagram saves" without naming a step, or asks what to run next.
---

# Manage Saves

The router for instagram-manager. Work out where the user's saves are in the pipeline, then hand
off to the skill for the next step.

## Step 1: Look at the data repo

The data repo is `$INSTAGRAM_HOME` (default `~/Workspace/git/instagram`). Media lives outside git
in `$INSTAGRAM_MEDIA_DIR`, one folder per post. Check what exists, top to bottom; the first row
that is missing is the next step:

| If this is missing... | The next step is |
|---|---|
| `.cache/saves.json` | **import-saves** |
| `data/tags.yaml` | **tag-saves** |
| a pin in `data/places.yaml` for each tagged place | **tag-saves**, `add_places.py` (`make places`) |
| `data/pins.yaml` | **resolve-post-location** |
| `data/media.yaml` (thumbnails) | **fetch-media** |
| the hub build in `.cache/hub/` | **build-hub** |
| reels in `data/no-spot.yaml` or placed only at their town, with no `from: video` pins | **read-frames** (videos through **fetch-media** `--video`) |
| `data/items/` | split-saves *(coming)* |
| stills and clips per item | extract-stills *(coming)* |
| `out/<topic>.yaml` | sending a topic to another repo *(coming)* |

A newer export zip than the one `saves.json` came from also means: run **import-saves** again,
then tag the new saves.

Open review lists are work too: `data/tags-review.yaml` (tag-saves) and `data/pins-review.yaml`
(resolve-post-location) each say why an entry is there and how to fix it by hand.

## Step 2: Ask only when it forks

If the next step is clear, say it and run it. Use `AskUserQuestion` only when the user has to
pick a scope — all saves, or one set of collections first (for example a pilot on one city's
collections before the rest). Each option says what it covers and roughly how long it takes.

Every fetch from instagram.com (thumbnails or videos) needs the user's go-ahead for that run.

## Step 3: Track the run

For more than one step, add a task per step with `TaskCreate` and mark each done as it finishes.

## Routing table

| They say... | Skill |
|---|---|
| "I have a new export" / "import my saves" | `import-saves` |
| "which collections do I have?" | `import-saves` (`--list`) |
| "sort my saves" / "tag the pilot" | `tag-saves` |
| "this place has no pin" / "look up the missing towns" | `tag-saves` (`add_places.py`) |
| "which saves are in the wrong collection?" | `tag-saves` (`moves_page.py`) |
| "pin the restaurants" / "which spots does this post name?" | `resolve-post-location` |
| "this pin is wrong" / "fix the review list" | `resolve-post-location` ("Fixing by hand") |
| "the place is only in the video" | `read-frames` |
| "download the thumbnails" / "get the videos" | `fetch-media` |
| "show me the map" / "rebuild the hub" | `build-hub` |
| "what's next?" | this skill, Step 1 |

## Rules every step keeps

- Read only the `saved/` files of the export. Never unpack messages or the rest.
- Never log in to Instagram or use cookies.
- No script calls a model. Scripts prepare batches and check answers; the session starts the
  agents, at most 4 at a time.
- A person's fixes are marked, not deleted, so a re-read keeps them.
- Nothing personal (handles, collection names, post codes) goes into this public plugin; it all
  stays in the data repo.
