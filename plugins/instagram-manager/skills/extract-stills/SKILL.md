---
name: extract-stills
description: Cut a still picture and a 3-second looping clip for each place a saved Instagram reel names, from the reel's video, at the moment that place's name is on screen, so the hub's place pages, post pages and map popups show the place itself instead of the reel's cover. Use when reels have videos and spots and someone wants a picture per spot, when a reel names many places and every one shows the same cover, or after new videos or spots land.
---

# Extract Stills

A reel that names four cafés has one cover, so all four cafés' pages show the same picture. This
skill gives each spot its own: a still from the moment the spot's name is on screen, and a short
clip that starts there. No model is called; it is ffmpeg plus the words read-frames already read.

For travel, the "items" a post names are its spots in `data/pins.yaml`, so this skill cuts per
spot. A splitter for other topics (recipes, ideas) is not built yet.

Track the run with `TaskCreate`: one task per step below, each marked done as it finishes.

## Before you start

- **Videos.** Only reels with `video:` in `data/media.yaml` get stills (**fetch-media** `--video`).
  Each Instagram run needs the user's go-ahead: ask with `AskUserQuestion`, saying how many reels,
  how long the run takes at the pacing caps, and what waiting would mean.
- **Spots.** The reel needs pins in `data/pins.yaml` (**resolve-post-location**, **read-frames**).
- **Tools.** ffmpeg, ffprobe and img2webp (`brew install ffmpeg webp`). This ffmpeg has no WebP
  encoder, so ffmpeg writes the clip's frames and img2webp joins them.

## Steps

1. **Cut.** `extract_stills.py --pilot <name>` (`make stills` in the data repo). For each spot of
   each reel with a video:
   - it finds the first frame where the spot's caption words (`said`), its OpenStreetMap name or
     its `lookup` are on screen, in either text reader's words from read-frames' `text.json`
     (letters and digits in order, so odd OCR spacing still matches). A reel with no `text.json`
     gets one made with read-frames' own code;
   - it cuts `$INSTAGRAM_MEDIA_DIR/<code>/spots/still-<slug>.jpg` (600 px wide) and
     `clip-<slug>.webp` (3 s, 320 px wide, 10 frames a second, silent, looping). A moment within
     3 s of the end starts the clip earlier, so every clip runs its full 3 s;
   - it writes one entry per spot to `data/stills.yaml`: the frame, the time, how it was found
     (`on_screen`, `hand`, `not_on_screen` or `cut_failed`) and the two file paths. The files stay
     in iCloud; git keeps only the pointers.

   A rerun cuts only spots that are new or whose time changed. `--redo` cuts every one again.
2. **Look with your own eyes.** Open every still (or a sample of ten on a big run) and check that it
   shows its spot: the name on a sign, a title card, a profile card. Play a few clips in the hub.
   Write down any that show the wrong place.
3. **Fix by hand.** A spot whose name never shows (`not_on_screen`), or a still from the wrong
   moment: watch the video, then set `t:` (seconds) on its entry in `data/stills.yaml` and add
   `by: hand`. The next run cuts it there and keeps that time on every run after.
4. **Build the hub** (**build-hub**, `make hub`). Each spot with a still shows it on its place page
   card and in its map popup, and the post page gets "The places in the video": one picture per
   spot in the order they show in the video, each with a Play button. The pointer playing the clip
   on hover is turned off when the viewer asks for reduced motion.
5. **Commit `data/stills.yaml`** in the data repo. Never a still or a clip.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/extract_stills.py` | A still and a 3 s clip per spot, cut where its name is on screen; writes `data/stills.yaml` | After new videos or spots land, or after a hand-set `t:` | `python3 scripts/extract_stills.py --pilot <name>` (`--all`, `--redo`) |
| `scripts/test_extract_stills.py` | Offline tests on an invented data folder and an ffmpeg-made video: the moment picked, a spot never on screen, a rerun cutting nothing, a hand time kept, a clip near the end | After any change to the script | `python3 scripts/test_extract_stills.py` |

In the data repo: `make stills` (`STILLS_REDO=1` to cut again).

## What it can't do yet

- **Spots said out loud only.** A name that is spoken but never shown needs speech-to-text.
- **Picking the best-looking frame.** The still is the first frame showing the name, which is
  usually a sign or a caption over the place, not the prettiest shot.
