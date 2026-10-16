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
  `extract_stills.py --need-video --pilot <name>` lists the reels that name 2 or more spots and have
  no video yet, in `.cache/stills/need-video.txt`. Those are the reels whose spots all share one
  cover. Posts Instagram already answered with an error are left off. Each Instagram run needs the
  user's go-ahead: ask with `AskUserQuestion`, saying how many reels and spots, how long the run
  takes at the pacing caps, and what waiting would mean.
- **Spots.** The reel needs pins in `data/pins.yaml` (**resolve-post-location**, **read-frames**).
- **Tools.** ffmpeg, ffprobe and img2webp (`brew install ffmpeg webp`). This ffmpeg has no WebP
  encoder, so ffmpeg writes the clip's frames and img2webp joins them.

## Steps

1. **Cut.** `extract_stills.py --pilot <name>` (`make stills` from your saves folder). For each spot of
   each reel with a video:
   - it finds the first frame where the spot's caption words (`said`), its OpenStreetMap name or
     its `lookup` are on screen, in either text reader's words from read-frames' `text.json`
     (letters and digits in order, so odd OCR spacing still matches). A reel with no `text.json`
     gets one made with read-frames' own code;
   - read-frames keeps at most 12 frames, so a fast reel (a new stop every second) loses whole
     stops. When a spot is on none of those frames, the script reads one frame every half second
     and looks again. It saves that reading in `<code>/frames/dense.json` with each frame's real
     time in the video (not its half-second slot, which can be up to 0.25 s off and land on the
     scene before) and reuses it until the video changes;
   - only then does it match loosely: the name without the end words that only say what kind of place
     it is ("State Park", "Trail", "Overlook"), or a name of 12 or more letters with one letter
     misread ("Monferey Bay Aquarium"), on either set of frames;
   - a spot whose own name never shows takes the moment its area (`near`) is on screen, as road-trip
     reels do ("Stop 2. Big Sur", then its viewpoints only in the caption). It gets `how: area` and
     shares one `still-area-<slug>.jpg` with the area's other spots. Only when the reel shows two or
     more of its areas at different times, never from a frame naming several (a title card, a map),
     and never for a whole state or country: one area on screen is the whole reel, not a part of it;
   - it cuts `$INSTAGRAM_MEDIA_DIR/<code>/spots/still-<slug>.jpg` (600 px wide) and
     `clip-<slug>.webp` (3 s, 320 px wide, 10 frames a second, silent, looping). A moment within
     3 s of the end starts the clip earlier, so every clip runs its full 3 s;
   - it writes one entry per spot to `data/stills.yaml`: the frame, the time, how it was found
     (`on_screen`, `area` with the `area:` it used, `hand`, `not_on_screen` or `cut_failed`) and the
     two file paths. The files stay
     in iCloud; git keeps only the pointers.

   A rerun cuts only spots that are new or whose time changed. `--redo` cuts every one again.
2. **Look with your own eyes.** Open every still (or a sample of ten on a big run) and check that it
   shows its spot: the name on a sign, a title card, a profile card. Play a few clips in the hub.
   Write down any that show the wrong place.
3. **Fix by hand.** A spot whose name never shows (`not_on_screen`), or a still from the wrong
   moment: watch the video, then set `t:` (seconds) on its entry in `data/stills.yaml` and add
   `by: hand`. The next run cuts it there and keeps that time on every run after. Several spots
   seen in one shot (a park's trails on one title card) can share one picture: give each the same
   `t:` and an `area:` naming the park, and they get one `still-area-<slug>.jpg` and sit under that
   area on the post page. Leave a spot on the cover when no moment clearly shows it: a wrong
   still is worse than the cover.
4. **Build the hub** (**build-hub**, `make hub`). Each spot with a still shows it on its place page
   card and in its map popup, and the post page gets "The places in the video": one picture per
   spot (one per area for spots shown by their area) in the order they show in the video, each with
   a Play button. The pointer playing the clip
   on hover is turned off when the viewer asks for reduced motion.
5. **Commit `data/stills.yaml`** in the data repo. Never a still or a clip.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/extract_stills.py` | A still and a 3 s clip per spot, cut where its name is on screen; writes `data/stills.yaml` | After new videos or spots land, or after a hand-set `t:` | `python3 scripts/extract_stills.py --pilot <name>` (`--all`, `--redo`) |
| `scripts/extract_stills.py --need-video` | Lists the reels naming 2 or more spots with no video yet; cuts nothing | Before asking to fetch videos for stills | `python3 scripts/extract_stills.py --need-video --pilot <name>` |
| `scripts/previews.py` | A small picture (144 × 192, about 5 KB) per post, and for a post with a video a looping flipbook of 12 frames from the whole reel (about 50 KB), in `.cache/hub/previews/`; remade only when the source is newer | For pages that list many posts at once: the pins page and the hub call it themselves (and share its flipbook player, `player_js()`), so run it by hand only to try a post | `python3 scripts/previews.py CODE ...` (`--out DIR`, `--redo`) |
| `scripts/heard.py` | A check, not a step: turns each reel's sound into words on this Mac (whisper.cpp) and looks for its spots' names among them; writes only to `.cache/whisper/` | Before counting on speech for a new set of reels. In the first trial, 18 of 19 reels were music or silent, and the one voice never said a name | `python3 scripts/heard.py [CODE ...]` (`--prompt`, `--model PATH`); needs `brew install whisper.cpp` and a model |
| `scripts/test_extract_stills.py` | Offline tests on an invented data folder and an ffmpeg-made video: the moment picked, a spot never on screen, a road-trip spot taking its area's moment (and a title card, one area or a state not counting), a rerun cutting nothing, a hand time kept, a clip near the end, a spot found only on the half-second frames (and those read once, then reused; none read when every spot is found), a hand time shared by an area, two spots with one name not cut again, the need-video list; previews: a picture per post, a flipbook only with a video, nothing remade unless newer, codes differing by case | After any change to either script | `python3 scripts/test_extract_stills.py` |

From your saves folder: `make stills` (`STILLS_REDO=1` to cut again), `make stills-need-video`, then
`make media-video VIDEO_LIST=.cache/stills/need-video.txt MEDIA_LIMIT=<n>`.

## What it can't do yet

- **Spots named only in the caption.** Their still is the reel's cover. Speech doesn't help:
  `heard.py` found these reels are mostly music, with no names said out loud.
- **Picking the best-looking frame.** The still is the first frame showing the name, which is
  usually a small label over the place. That is fine for most reels. Where it isn't (an interview
  with a profile card over the middle), the card stays for the whole scene and the place is
  never shown, so no other frame would be better. For a reel where a better frame does exist,
  set `t:` by hand.
