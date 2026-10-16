---
name: read-frames
description: Find where a saved Instagram reel was filmed from its video, for the reels whose caption names no spot, is tagged with only a state, or is a food or stay post that opens only its town. Lists those reels for fetch-media --video, takes frames at each scene change with ffmpeg, reads the words on them with tesseract and, on a Mac, Apple Vision, makes contact sheets, and runs frame-reader agents in batches whose spots go through the same checks as caption spots. Use when posts can't be placed from the caption, when someone asks to read venue names, signs or title cards off the videos, or to place reels tagged only with a state.
---

# Read Frames

Some saved reels name their place only on screen: a sign over the door, a title card, a menu. The
caption says "lunch was unreal", or the post is tagged only "California", so the caption step
(**resolve-post-location**) has nothing to search for. This skill looks at the video instead.

Every step runs in batches, and none of it calls a model from a script: the reading is done by
`frame-reader` agents, one per batch, at most 4 at a time.

Track the run with `TaskCreate`: one task per step below, and one per wave of agents, each marked
done as it finishes.

## Steps

1. **List the stuck reels.** `read_frames.py --stuck --pilot <name>` writes
   `.cache/frames/stuck.txt`, one code a line with why. A reel goes in when it is in the pilot and:
   - its caption names no spot (it is in `data/no-spot.yaml`);
   - it is tagged with only a state, so there is no town to search near;
   - it is for eating or staying and its map link opens only its town (no pin, and no venue the
     caption named that OpenStreetMap just doesn't list).
2. **Fetch their videos.** `fetch_media.py --video .cache/frames/stuck.txt` (see **fetch-media**).
   Each Instagram run needs the user's go-ahead, and the pacing caps hold: at most 100 posts a
   run, 3 runs a day, 2 hours apart. Ask with `AskUserQuestion` before each run: say how many
   reels, how long the run takes at the pacing, and what waiting instead would mean.
3. **Take the frames and batch them.** `read_frames.py --prepare`. For each listed reel with a
   video, in `$INSTAGRAM_MEDIA_DIR/<code>/frames/`:
   - `frame-NN.jpg`, 720 px wide: the first frame (where a title card usually is), then one at each
     scene change (ffmpeg's scene score above 0.3). At most 12, spread evenly when there are more;
     a reel with fewer than 6 gets frames at even times to make up 6, none within half a second of
     another.
   - `text.json`: what each text reader read on each frame, and when each frame shows. `text` is
     tesseract's (sparse-text mode, which suits words laid over a picture). `vision` is Apple
     Vision's, macOS's own text reader (`scripts/vision_ocr.swift`, compiled on first use into
     `.cache/bin/vision_ocr`). tesseract misses styled subtitles (outlined, yellow, bold over a
     busy picture) and the names on an Instagram profile card; Apple Vision reads them. Off a Mac
     only tesseract runs.
   - `sheet-N.jpg`: 6 frames to a sheet, 3 across and 2 down, in reading order, 360 px a frame.
     This ffmpeg has no text filter, so the frames are not numbered on the sheet; the batch says
     which frames each sheet holds.

   Then batch files of 6 reels in `.cache/batches/frames/` (each reel brings about 2 sheets, so an
   agent looks at about 12 images). A reel tagged with only a state gets every town and park listed
   in that state as its areas, marked `state_only`. A reel whose answers were merged before is
   skipped unless `--redo`, and new batches are numbered after the merged ones.
4. **Run the agents.** One `frame-reader` agent per batch, at most 4 at a time:
   `Follow <plugin>/agents/frame-reader.md exactly. Batch: <path>`.
5. **Merge.** `resolve_post_location.py --merge --frames`. Each spot goes through the caption
   checks, with two changes:
   - its words may be in the caption **or** in what either text reader read on the frames (letters and
     digits in order, so odd OCR spacing still matches). The text comes from `text.json`, never
     from the batch;
   - the spots **add** to the post's pins and review entries, marked `from: video`; a spot the
     caption already gave is left as it is.

   A name the agent read that both readers missed (a script font) goes to review as "not in the caption
   or the video's text". Open the frame, and if the name is there, add `lookup: "<name>"` to the
   entry; the next merge searches it.
6. **Look with your own eyes.** Open some frames and compare them to `text.json`, including the
   hard ones: script fonts, words over busy pictures, small text in a corner. Write down what
   each reader got wrong. Then open the pins on the hub.

   When a text reader changes, `read_frames.py --text` reads the words again on the frames already
   made (no new frames, no batches). To re-check answers merged before, rename their
   `batch-NNN.answers.merged.json` back to `batch-NNN.answers.json` and merge again: a spot already
   pinned is skipped, and a review entry is checked again.
7. **Commit `data/pins.yaml`, `pins-review.yaml`, `no-spot.yaml` and `media.yaml`** in the data
   repo. Never a frame or a video: they stay in iCloud.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/read_frames.py --stuck` | Lists the pilot's reels the caption can't place, with why | Before fetching videos | `python3 scripts/read_frames.py --stuck --pilot <name>` |
| `scripts/read_frames.py --prepare` | Frames, both readers' text and contact sheets for each listed reel with a video, then batch files | After the videos land; again after more land | `python3 scripts/read_frames.py --prepare` (`--redo` to take frames again) |
| `scripts/read_frames.py --text` | Reads the words again on frames already made, with both readers; rewrites `text.json` | After a text reader changes, before merging again | `python3 scripts/read_frames.py --text` (`make frames-text`) |
| `scripts/vision_ocr.swift` | Apple Vision's text on each image, one JSON line each; `read_frames.py` compiles and calls it | Never by hand, except to try it on one frame | `xcrun --sdk macosx swiftc -O -o vision_ocr scripts/vision_ocr.swift && ./vision_ocr <frame.jpg>` |
| `../resolve-post-location/scripts/resolve_post_location.py --merge --frames` | Checks the agents' answers against the caption and the frame text, looks the spots up, adds them to the pins | After each wave of agents | `python3 ../resolve-post-location/scripts/resolve_post_location.py --merge --frames` |
| `scripts/test_read_frames.py` | Offline tests on an invented data folder and an ffmpeg-made video: the stuck list, frame times, sheets, batches, both readers' text, `--text`, and the merge adding video spots | After any change to either script | `python3 scripts/test_read_frames.py` |

In the data repo: `make frames-stuck`, `make media-video`, `make frames`, `make frames-merge`.

## What it can't do yet

- **Speech.** A reel that says the place out loud but never shows it needs a speech-to-text step
  (whisper is not installed).
- **Places known only by how they look.** The agent reads names; it never guesses a place from
  the view.
