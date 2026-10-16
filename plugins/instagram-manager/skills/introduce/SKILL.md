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
2. **tag-saves** — topics, purposes and places per save: collection rules and hashtags first,
   then `save-tagger` agents, each reading one batch of saves. `add_places.py` looks up places
   that have no pin yet on OpenStreetMap; `moves_page.py` lists saves filed in the wrong
   collection.
3. **resolve-post-location** — the spots a caption names (a beach, a café, a trailhead), found
   on OpenStreetMap near the save's town or park, as map pins. `post-locator` agents read the
   captions.
4. **fetch-media** — one thumbnail per post, or with `--video` a reel's video, slowly and logged
   out.
5. **read-frames** — for reels whose place is only on screen: frames at each scene change, the
   words on them, and `frame-reader` agents naming the spots, checked like caption spots.
6. **extract-stills** — for reels with a video: a still and a 3-second clip for each spot, cut
   where its name is on screen, so each place shows its own picture instead of the reel's cover.
7. **build-hub** — the private hub: a map, a page per place, a page per post.
8. **split-saves** *(coming)* — the items a non-travel post names (a recipe, an idea), each with
   its quote. For travel, the items are the spots step 3 already finds.

Skills available today: **introduce** (this skill), **manage-saves** (the router: works out which
step comes next), and steps 1 to 7.

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
- Show my saves on a map                    (build-hub)
- Just explain more
```

For a multi-step run, track each step with `TaskCreate` and mark it done as it finishes.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| I downloaded a new Instagram export | import-saves | `/instagram-manager:import-saves` |
| Which collections do I have? | import-saves | `/instagram-manager:import-saves` |
| Sort my saves by topic or city | tag-saves | `/instagram-manager:tag-saves` |
| Pin the restaurants and beaches a post names | resolve-post-location | `/instagram-manager:resolve-post-location` |
| The place is only in the video | read-frames | `/instagram-manager:read-frames` |
| Download thumbnails or videos | fetch-media | `/instagram-manager:fetch-media` |
| A picture of each place a reel names | extract-stills | `/instagram-manager:extract-stills` |
| Show my saves on a map | build-hub | `/instagram-manager:build-hub` |
| What should I run next? | manage-saves | `/instagram-manager:manage-saves` |

## Plugin Map

```
instagram-manager
  ├── introduce              — this skill
  ├── manage-saves           — router across the pipeline
  ├── import-saves           — export zip → <data repo>/.cache/saves.json
  ├── tag-saves              — saves.json → save-tagger agents → data/tags.yaml; add_places.py → data/places.yaml
  ├── resolve-post-location  — tagged saves → post-locator agents → data/pins.yaml, data/pins-review.yaml
  ├── fetch-media            — thumbnails and videos → $INSTAGRAM_MEDIA_DIR, data/media.yaml
  ├── read-frames            — videos → frames and their words → frame-reader agents → data/pins.yaml
  ├── extract-stills         — videos + spots → a still and a clip per spot → data/stills.yaml
  └── build-hub              — data/ → <data repo>/.cache/hub/ (map, place pages, post pages)

  agents/ (Haiku, one batch file in, one answers file out)
    ├── save-tagger    — topics, purposes and places
    ├── post-locator   — the spots a caption names
    └── frame-reader   — the spots a video shows

  shared/scripts/
    ├── home.py        — finds the data repo (INSTAGRAM_HOME)
    ├── log.py         — one greppable ev= line per event
    ├── quote.py       — the word-for-word quote check
    ├── geocode.py     — OpenStreetMap lookups, cached, one a second
    ├── places.py, pilot.py, purposes.py — the place list, pilot sets, purposes
    └── check_data.py  — the data repo's config and data fit together (its make check)
```

No script calls a model: scripts prepare batches and check answers, and the session starts the
agents on the plan Claude Code is logged in with.

## Requirements

- Python 3, plus PyYAML (the tagger and the data check).
- Claude Code, for the agents.
- For read-frames: ffmpeg and tesseract; on a Mac, Apple Vision reads the frames as well.
- For extract-stills: ffmpeg and img2webp (`brew install ffmpeg webp`).
- An Instagram data export, HTML or JSON.
