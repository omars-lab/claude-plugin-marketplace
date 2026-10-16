# Instagram Manager

Turn your Instagram saved posts into something you use: import them from your data export, tag
them by topic and city, pull out the places and ideas each post names, and build a private hub
that feeds your other projects.

## Getting Started

```bash
/plugin install instagram-manager@oeid-claude-plugins   # install
/instagram-manager:introduce                            # what it can do
```

## Skills (12)

| Category | Skill | What it does |
|---|---|---|
| **Intro** | `introduce` | Explain the plugin and route to the right skill |
| **Route** | `manage-saves` | Pick the next step: import, tag, spots, media, stills, hub, send |
| **Import** | `import-saves` | Read the saved posts and collections out of your export zip, in memory |
| **Tag** | `tag-saves` | Topics, purposes and places per save: collection rules, then `save-tagger` agents on batches |
| **Items** | `split-saves` | The dishes, techniques, ideas and tips a non-travel caption names, each with its exact words, from `save-splitter` agents |
| **Spots** | `resolve-post-location` | The beaches, cafés and trailheads a caption names, looked up on OpenStreetMap near their town |
| **Media** | `fetch-media` | A thumbnail per post, or a reel's video, slowly and logged out |
| **Spots** | `read-frames` | Frames from a reel's video and the words on them, for places shown only on screen |
| **Media** | `extract-stills` | A still and a 3 s clip per spot, cut where its name is on screen |
| **Links** | `find-google-ids` | Google's place id per spot, so its Google Maps link opens that exact place; only the id is kept |
| **Hub** | `build-hub` | A private local site: a map, a page per place, a page per post |
| **Send** | `send-topics` | The files other repos read: one per state or country for travel, one per other topic |
| **Send** | `serve-api` | The same data as a local web API in Docker, with Swagger and JSON Schema, and the hub's decisions as writes |

## Agents (4)

`save-tagger` (topics, purposes, places), `save-splitter` (the things a non-travel caption names),
`post-locator` (the spots a caption names) and `frame-reader` (the spots a video shows) each read one batch file and write its answers (Haiku).
No script calls a model: the Claude Code session starts the agents, on the plan it is logged in
with. No API key.

## Where your data lives

The plugin holds code only. Your saves and tags live in a private data repo, found through
`INSTAGRAM_HOME` (default `~/Workspace/git/instagram`). Media goes to a folder of your choosing,
`INSTAGRAM_MEDIA_DIR`, outside git. Nothing personal goes in this public repo.

## Requirements

Python 3 with PyYAML, Claude Code, an Instagram data export (HTML or JSON), and ffmpeg for videos.

---

**Part of**: [OEID Claude Plugin Marketplace](../../README.md)
