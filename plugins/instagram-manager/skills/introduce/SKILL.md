---
name: introduce
description: Introduce the instagram-manager plugin — what it does with your Instagram saved posts, its skills in pipeline order, and where your private data lives. Use when someone asks what this plugin can do or how to get started with their saves.
---

# Introduce Instagram Manager

You are the instagram-manager plugin. When this skill is invoked, explain what you do, then
route the user to the right skill.

## What This Plugin Does

Thousands of saved posts sit in Instagram, out of reach of anything else. This plugin reads them
from your official data export (no login, no scraping your account), sorts them by topic and
city, pulls out the places and ideas each post names (each one backed by a word-for-word quote
from the caption), and builds a private hub. Other projects take the topics they care about from
files the plugin writes.

The pipeline, in order:

1. **import-saves** — read saved posts and collections from the export zip, in memory. Only the
   `saved/` files are opened; messages and the rest of the export are never unpacked.
2. **tag-saves** — topics and places per save: collection rules first, then `save-tagger`
   agents, each reading one batch of saves.
3. **split-saves** *(coming)* — the items a post names, each with its quote.
4. **fetch-media** *(coming)* — the post's video or image, slowly, logged out.
5. **extract-stills** *(coming)* — the best still and a short clip per item.
6. **build-hub** *(coming)* — the private interests hub.

Skills available today:
- **introduce** — this skill.
- **manage-saves** — the router: works out which step comes next.
- **import-saves** — step 1.
- **tag-saves** — step 2.

## Where data lives

Code lives here, in a public plugin. Your data lives in a private repo found through
`INSTAGRAM_HOME` (default `~/Workspace/git/instagram`): the export copy, `saves.json` and the
agents' batch files under its gitignored `.cache/`, and the tags and items it commits. Videos,
stills and clips go to `INSTAGRAM_MEDIA_DIR`, a folder outside git; the data repo keeps pointers
to them.

## How to Introduce Yourself

### Step 1: Explain

```
Instagram Manager — your saved posts, sorted and usable.

- Import every save and collection from your data export (read in memory, nothing unpacked)
- Tag by topic and city, and pull out the places and ideas with a quote for each
- Build a private hub, and hand each topic to the project that uses it
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What would you like to do?

- Import a new export                       (import-saves)
- See what step comes next for my saves     (manage-saves)
- List my collections and their sizes       (import-saves --list)
- Sort my saves by topic and place         (tag-saves)
- Just explain more
```

For a multi-step run, track each step with `TaskCreate` and mark it done as it finishes.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| I downloaded a new Instagram export | import-saves | `/instagram-manager:import-saves` |
| Which collections do I have? | import-saves | `/instagram-manager:import-saves` |
| Sort my saves by topic or city | tag-saves | `/instagram-manager:tag-saves` |
| What should I run next? | manage-saves | `/instagram-manager:manage-saves` |

## Plugin Map

```
instagram-manager
  ├── introduce      — this skill
  ├── manage-saves   — router across the pipeline
  ├── import-saves   — export zip → <data repo>/.cache/saves.json
  └── tag-saves      — saves.json → batches → save-tagger agents → <data repo>/data/tags.yaml

  agents/
    └── save-tagger  — one batch file in, one answers file out (Haiku)

  shared/scripts/
    ├── home.py      — finds the data repo (INSTAGRAM_HOME)
    ├── log.py       — one greppable ev= line per event
    ├── quote.py     — the word-for-word quote check
    └── check_data.py — the data repo's config and data fit together (its make check)
```

No script calls a model: scripts prepare batches and check answers, and the session starts the
agents on the plan Claude Code is logged in with.

## Requirements

- Python 3, plus PyYAML (the tagger and the data check).
- Claude Code, for the agents.
- An Instagram data export, HTML or JSON.
