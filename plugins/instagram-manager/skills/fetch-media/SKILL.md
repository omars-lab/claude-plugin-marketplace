---
name: fetch-media
description: Fetch one small JPEG thumbnail per saved Instagram post, logged out and slowly (a 6 s wait before each instagram.com request, 25-55 s between posts, a stop at the first 429 or login wall), into the iCloud media folder, with data/media.yaml pointing at each one. Use when the hub needs thumbnails, when someone asks to download images or covers for their saves, or to run the thumbnail trial on a pilot.
---

# Fetch Media

Gets one thumbnail per save: a reel's cover, a photo post's image, or a carousel's first slide. Each
is a JPEG about 600 px wide at `$INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg` (an iCloud folder, never
git). `data/media.yaml` in the data repo points at it:

```yaml
EXAMPLE123: {thumb: EXAMPLE123/thumb.jpg, kind: reel, fetched: 2026-01-01}
EXAMPLE456: {error: private}
```

A post already in `media.yaml`, fetched or not, is skipped next time. The errors are `private`
(only followers can see it), `login_wall` (an age-limited post that needs a login), `not_found`
(Instagram sent nothing for it) and `no_image`. A run that stops on a block writes nothing for the
post it stopped on, so that post is tried again later.

## How a thumbnail is fetched, and why this way

The pacing research (`docs/research/instagram-fetch-pacing/consolidated.md` in the data repo)
plans for downloading each post's smallest video. The hub only needs one image per post, so this
skill asks yt-dlp to **read** the post without downloading anything:
`extract_info(url, download=False)`.

That answer already lists the post's images with their widths (Instagram's `image_versions2`).
The script takes the smallest one at least 600 px wide and downloads it with the same yt-dlp
object. macOS `sips` turns it into a 600 px JPEG. No image library is needed.

- **No video download.** A reel's video is megabytes; its cover image is tens of kilobytes.
- **The image comes from Instagram's image servers, not instagram.com.** The requests to
  instagram.com are the same 2 per post as a full download would make, and the image adds none.
- **Reels, photo posts and carousels go through one path.** `ignore_no_formats_error` lets a photo
  post with no video come back with its images. `playlist_items: "1"` keeps only a carousel's first
  slide.
- **Not used from the research:** the video format choice, download retries and the
  `download_archive` resume list. They only matter when a video is downloaded. `media.yaml` is the
  done list.

## Pacing, in plain words

Nobody publishes Instagram's limit for logged-out visitors, so these are careful guesses from
other tools' defaults. The run's log is what shows the real limit.

- **Never logged in.** No cookies, no login, no browser session, ever. yt-dlp gets `ignoreconfig`,
  so no config file can add cookies. The script refuses to start if any cookie or login option is
  set (`ev=refused reason=login_option`).
- **One yt-dlp object per run.** It sets up its session once, not once per post.
- **A 6 s wait before each instagram.com request.** yt-dlp does this itself (`sleep_interval_requests`).
- **A random 25-55 s pause between posts**, picked fresh each time, and **3-6 minutes every 25
  posts**.
- **An hourly brake.** Before each post, if the last hour already holds 150 instagram.com
  requests, it waits until it doesn't. At the pace above a run makes about 130 an hour, so this
  rarely fires.
- **One run at a time.** A lock file (`.cache/fetch-media.lock`). A second run refuses
  (`ev=refused reason=locked`).
- **At most 100 posts a run, 3 runs a day, 2 hours apart.** The trial is 5 posts.
- **The Mac's home connection.** No VPN, proxy or cloud machine: those get blocked sooner.

### When it stops

It stops at once, never retries inside the run, logs `ev=rate_limited kind=...` and writes a
cooldown file:

| Sign | `kind` |
|---|---|
| "redirected to the login page" or "rate-limit" in an error | `login_wall` |
| "HTTP Error 429" in an error or a warning | `http_429` |
| "HTTP Error 401" or "403" from the Instagram step | `http_401`, `http_403` |
| "Instagram sent an empty media response" on 2 posts in a row | `empty_streak` |
| 3 or more "watch" warnings in the last 10 posts (see below) | `warn_streak` |

One empty answer alone is probably a deleted post: the script waits 5 minutes. If the next post
works, the empty one is recorded as `not_found`.

**Watch warnings** ("No CSRF token set by Instagram API", "Instagram API is not granting access")
are the only trace of a quiet 429 on the "is this post viewable?" check. Each one adds a 60-120 s
pause. Nobody knows how often they show up on a good day, so the first 10 posts ever fetched set
the normal rate (`ev=baseline count=N`, kept in `.cache/fetch-media.state.json`). If that is 3 or
more, single warnings stop pausing and the stop level becomes N + 3 in 10 posts.

### After a stop

The cooldown is 24 hours after a first stop, 48 hours after a second in a row, and 3 days after a
third. Until it ends, every run refuses (`ev=refused reason=cooldown`). The first run after it
fetches **one test post**. If that works, the cooldown file is removed (`ev=recovered`).

Before trying again, open one of the failed posts in a private browser window on the same Wi-Fi.
If it asks you to log in, the connection is walled: wait. If it shows fine but yt-dlp still fails
after the cooldown, the tool is the problem, not the pace. The research says what to try first:
the `curl_cffi` browser library, then a yt-dlp update.

## The log

Every line goes to `$INSTAGRAM_HOME/.cache/logs/fetch-media.log`: a UTC time, `pid=`, `ev=` and
`key=value` pairs. Each network call has a line before and after it. Read it with `grep ev=`:

```
ev=run_start ytdlp=... sleep_req=6 gap_min=25 gap_max=55 cap=5 todo=5 skipped=0
ev=post_start n=1 shortcode=EXAMPLE123
ev=ig_request step=session|ruling|page shortcode=EXAMPLE123
ev=sleep reason=sleep_requests|gap|long_pause|watch|empty|budget secs=...
ev=image_start / ev=image_done bytes=...
ev=post_ok shortcode=EXAMPLE123 kind=reel bytes=... secs=... ig_requests=2
ev=post_bad shortcode=... reason=private|login_wall|no_image|unknown
ev=rate_limited kind=... posts_since_start=... ig_requests_since_start=... requests_last_hour=...
ev=run_end ok=... bad=... skipped=... stopped=yes|no ig_requests=... minutes=...
```

`grep ev=rate_limited` empty means the pace held. If not, its counts are the first measured limit
for this connection.

Every call that can hang has a timeout. Each network read has 30 s. The whole read of one post has
180 s (`ev=extract_timeout`), one image download has 60 s (`ev=image_timeout`), and `sips` has 60 s.
A timed-out post is left for a later run.

## Steps

1. **Check the inputs.** `.cache/saves.json` exists (else run **import-saves**). `data/tags.yaml`
   is used, if present, so a pilot also takes saves tagged with its places. Track the run with
   `TaskCreate`.
2. **Use a python3 that has yt-dlp and PyYAML.** `python3 -c "import yt_dlp, yaml"`.
3. **Run the pilot first,** 5 posts, in the background, and watch the log:
   ```bash
   python3 <plugin>/skills/fetch-media/scripts/fetch_media.py --pilot <name> --limit 5
   grep ev= <data repo>/.cache/logs/fetch-media.log | tail
   ```
4. **Look at two thumbnails** (open the JPEGs) against their posts.
5. **On a stop, stop.** Do not retry. Report what `ev=rate_limited` says.
6. **Commit `data/media.yaml`** in the data repo. Never a thumbnail: they stay in iCloud.
7. **Go wider** only after the user has seen the trial. That is a change of scope, so ask with
   `AskUserQuestion`. The options: the rest of the pilot in one run (about 80 minutes, and the log
   shows whether the pace holds), or another short trial first (slower, but less exposed if the
   first one showed warnings).

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/fetch_media.py` | Fetches one 600 px JPEG thumbnail per save not yet in `media.yaml`, logged out and paced; stops at the first block | The thumbnail trial on a pilot, then runs of up to 100 posts | `python3 scripts/fetch_media.py --pilot <name> --limit 5` (or `--all --limit 100`) |
| `scripts/test_fetch_media.py` | Offline tests with a fake yt-dlp: skipping done posts, the stop on a 429, the cookie refusal, the lock, the `media.yaml` shape | After any change to the fetcher | `python3 scripts/test_fetch_media.py` |
