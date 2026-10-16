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

1. **import-saves** — how to ask Instagram for the export, a folder set up with three starter
   config files (`setup_home.py`), then the saved posts and collections read from the export zip,
   in memory. Only the `saved/` files are opened; messages and the rest are never unpacked.
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
7. **find-google-ids** — Google's place id for each spot, found by one search near its pin and
   kept when only one result carries the spot's name (the rest are listed for a person to pick).
   Only the id is kept, so each Google Maps link opens that exact place.
8. **build-hub** — the private hub: a map, a page per place, a page per post.
9. **send-topics** — the files other repos read: one per state or country for travel, each save
   with its spots, and one per other topic. **serve-api** serves the same data as a local web
   API (Swagger, JSON Schema) for other hubs, and takes the hub's decisions as writes.
10. **split-saves** — the items a non-travel post names (a dish, a technique, an idea, a tip),
   each with its quote, from `save-splitter` agents. Run it after tag-saves, before send-topics.
   For travel, the items are the spots step 3 finds.

Every step above is ready to use, with **introduce** (this skill) and **manage-saves** (the
router: works out which step comes next). **new-user-trial** has a newcomer try the whole thing
in a sandbox and a reviewer rank what got in their way.

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

- Get started: export, set up, import       (import-saves)
- Import a new export                       (import-saves)
- See what step comes next for my saves     (manage-saves)
- List my collections and their sizes       (import-saves --list)
- Sort my saves by topic and place         (tag-saves)
- Show my saves on a map                    (build-hub)
- Send a topic to the project that uses it  (send-topics)
- Just explain more
```

For a multi-step run, track each step with `TaskCreate` and mark it done as it finishes.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| I'm new: how do I get my saves out of Instagram? | import-saves | `/instagram-manager:import-saves` |
| I downloaded a new Instagram export | import-saves | `/instagram-manager:import-saves` |
| Which collections do I have? | import-saves | `/instagram-manager:import-saves` |
| Sort my saves by topic or city | tag-saves | `/instagram-manager:tag-saves` |
| Split my recipes into dishes, my design posts into ideas | split-saves | `/instagram-manager:split-saves` |
| Pin the restaurants and beaches a post names | resolve-post-location | `/instagram-manager:resolve-post-location` |
| The place is only in the video | read-frames | `/instagram-manager:read-frames` |
| Download thumbnails or videos | fetch-media | `/instagram-manager:fetch-media` |
| A picture of each place a reel names | extract-stills | `/instagram-manager:extract-stills` |
| A Google Maps link opens a city or a list, not the place | find-google-ids | `/instagram-manager:find-google-ids` |
| Show my saves on a map | build-hub | `/instagram-manager:build-hub` |
| Send travel saves to my trip planner | send-topics | `/instagram-manager:send-topics` |
| Let another app read my saved places over HTTP | serve-api | `/instagram-manager:serve-api` |
| What should I run next? | manage-saves | `/instagram-manager:manage-saves` |
| How easy is this for someone else? Where are the gaps? | new-user-trial | `/instagram-manager:new-user-trial` |

## Plugin Map

```
instagram-manager
  ├── introduce              — this skill
  ├── manage-saves           — router across the pipeline
  ├── import-saves           — setup_home.py → config/; export zip → <data repo>/.cache/saves.json
  ├── tag-saves              — saves.json → save-tagger agents → data/tags.yaml; add_places.py → data/places.yaml
  ├── split-saves            — non-travel saves → save-splitter agents → data/items/<topic>.yaml
  ├── resolve-post-location  — tagged saves → post-locator agents → data/pins.yaml, data/pins-review.yaml
  ├── fetch-media            — thumbnails and videos → $INSTAGRAM_MEDIA_DIR, data/media.yaml
  ├── read-frames            — videos → frames and their words → frame-reader agents → data/pins.yaml
  ├── extract-stills         — videos + spots → a still and a clip per spot → data/stills.yaml
  ├── find-google-ids        — spots → one Google search each → data/google.yaml (place ids only)
  ├── build-hub              — data/ → <data repo>/.cache/hub/ (map, place pages, post pages)
  ├── send-topics            — data/ → <data repo>/out/travel/<area>.yaml, out/<topic>.yaml for other repos
  ├── serve-api              — data/ → a local API in Docker on 127.0.0.1 (read, schema, the hub's writes)
  └── new-user-trial         — a sandbox + invented export → new-user-tester diary → trial-reviewer review

  agents/ (Haiku, one batch file in, one answers file out)
    ├── save-tagger    — topics, purposes and places
    ├── save-splitter  — the dishes, ideas and tips a non-travel caption names
    ├── post-locator   — the spots a caption names
    ├── frame-reader   — the spots a video shows
    ├── new-user-tester — (Sonnet) plays a newcomer in a sandbox, writes a diary
    └── trial-reviewer  — (Opus) re-checks the diary, ranks the fixes

  shared/scripts/
    ├── home.py        — finds the data repo (INSTAGRAM_HOME)
    ├── log.py         — one greppable ev= line per event
    ├── quote.py       — the word-for-word quote check
    ├── geocode.py     — OpenStreetMap lookups, cached, one a second
    ├── google_places.py — Google place search in a box, the name rule, links that carry a place id
    ├── places.py, pilot.py, purposes.py — the place list, pilot sets, purposes
    ├── items_store.py — the split step's items, one file per topic under data/items/
    └── check_data.py  — the data repo's config and data fit together, and no two spots share a map point by mistake (its make check)
```

No script calls a model: scripts prepare batches and check answers, and the session starts the
agents on the plan Claude Code is logged in with.

## Requirements

- Python 3, plus PyYAML (the tagger and the data check).
- Claude Code, for the agents.
- For fetch-media videos: yt-dlp (`brew install yt-dlp`). Thumbnails need nothing extra.
- For read-frames: ffmpeg and tesseract; on a Mac, Apple Vision reads the frames as well.
- For extract-stills: ffmpeg and img2webp (`brew install ffmpeg webp`).
- For find-google-ids: a Google Maps Platform key with Places API (New), in `GOOGLE_MAPS_API_KEY`
  for the one run (find-google-ids says how to keep it out of files; dotenvx works too).
- For serve-api: Docker.
- Nothing else to look at the hub: `make serve` is Python's own web server.
- An Instagram data export, HTML or JSON.
