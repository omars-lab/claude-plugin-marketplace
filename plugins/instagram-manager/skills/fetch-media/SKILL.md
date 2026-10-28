---
name: fetch-media
description: Fetch one small JPEG thumbnail per saved Instagram post, or with --video a listed reel's smallest clear video and its full-size cover, logged out and slowly (a 6 s wait before each instagram.com request, 25-55 s between posts, a stop at the first 429 or login wall), into the iCloud media folder, with data/media.yaml pointing at each one. Use when the hub needs thumbnails, when someone asks to download images, covers or videos for their saves, or to get the videos read-frames reads.
---

# Fetch Media

Gets one thumbnail per save: a reel's cover, a photo post's image, or a carousel's first slide. Each
is a JPEG about 600 px wide at `$INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg` (an iCloud folder, never
git). `data/media.yaml` in the data repo (your data folder, `$INSTAGRAM_HOME`, the one
`setup_home.py` made) points at it:

```yaml
EXAMPLE123: {thumb: EXAMPLE123/thumb.jpg, kind: reel, fetched: 2026-01-01}
EXAMPLE456: {error: private}
```

**How long it takes.** A run of 117 posts takes about 2 hours, and the rules below allow 3 runs a
day, so about 350 thumbnails a day: a library of 1,000 saves takes about three days of runs, 8,000
about three weeks. With `--one-request` (below) a post takes about 52 s instead of 61 s (the gap
between posts stays), but a run may hold 150 posts (about 2 h 10 min), then 200 (about 3 h), so a
day of runs fetches 450-600 thumbnails instead of 350. The map works without thumbnails; they only
add pictures.

A post already in `media.yaml`, fetched or not, is skipped next time. The errors are `private`
(only followers can see it), `login_wall` (a post limited by age or audience, "isn't available to
everyone", that needs a login), `not_found`
(Instagram sent nothing for it) and `no_image`. A run that stops on a block writes nothing for the
post it stopped on, so that post is tried again later.

## Videos, for reels whose place is only on screen (`--video`)

`--video CODES.txt` fetches the reels listed in a file (one code a line, `#` starts a comment;
**read-frames** writes it as `.cache/frames/stuck.txt`). It is a separate run under the same pacing
and the same caps. For each listed reel it saves:

- `<code>/video.mp4`: the smallest video that is at least 540 px on its short side, with sound, as
  one file (Instagram's plain mp4 versions; split video-only streams only if there is no other).
  A 30 s reel at that size is a few megabytes. 540 px is enough for a text reader to read a sign.
- `<code>/cover.jpg`: the reel's cover at full size. The 600 px square thumbnail cuts off the
  title band that often names the place; this one keeps it.

`media.yaml` keeps the post's entry and adds `video`, `cover`, `video_size` (`720x1280`), `sound`
(`yes`, `no` or `unknown`, from ffprobe) and `video_fetched`. A listed post that is not a reel gets
`video_error: not_a_reel`; a reel with no video version gets `video_error: no_video`. Either one, or
a `video`, means the post is done and is skipped next time.

The file comes from Instagram's video servers, not instagram.com, so the requests to
instagram.com are still 2 per post. The download has a 300 s deadline. A failed download from the
video servers ("unable to download video data") is not a block on its own, but **3 in a row stop
the run** (`ev=rate_limited kind=file_streak`), as the research says.

```bash
python3 <plugin>/skills/fetch-media/scripts/fetch_media.py --video .cache/frames/stuck.txt --limit 100
```

Log lines added: `ev=video_start`, `ev=video_done bytes=... size=... sound=...`, `ev=cover_done` /
`ev=cover_fail`, and `ev=post_ok path=video`.

## One request a post (`--one-request`, off by default)

yt-dlp asks instagram.com twice for each post: "is this post viewable?", then the post's page. The
page alone has the images. `--one-request` answers the first question "ok" inside the script,
without asking, so each post costs 1 request and that request's 6 s wait goes too. Every other
wait and stop rule is the same. The research behind it is in the plugin author's data repo
(`docs/research/instagram-media-alternatives/consolidated.md`); what follows is what it settled on.

Skipping the question changes three things:

- **Watch warnings mean nothing.** They come from the skipped question. They are still logged
  (`ev=warn ... acted=no`), but never pause or stop the run, and never set the normal rate.
- **A post limited by age or audience can't be named from its page.** Only the skipped question
  says "isn't available to everyone"; the page alone gives a login redirect or an empty answer. So
  the first login redirect or empty answer in a run asks that post again the 2-request way
  (`ev=recheck`). If it is limited, it is written down as `login_wall` and the run goes on;
  anything else is handled as without the option, so a real login redirect still stops the run.
  Only once a run: a real block costs at most 2 more requests.
- **It leans on yt-dlp's own code**, so it refuses any yt-dlp but the version it was checked
  against (`ev=refused reason=ytdlp_version`). After a yt-dlp update, read its Instagram code
  again before changing `ONE_REQUEST_YTDLP`.

**Try it on 20 posts first**, in one normal run slot. Include a post already marked `login_wall`
through `--recheck FILE` (one code a line): those posts are asked for first even though
`media.yaml` has them, and nothing is written for them (`ev=recheck_result result=...`). The trial
passes when 19 or 20 of the 20 give a thumbnail or a known error, no normal post stops the run, the
limited post comes back `login_wall`, and `ig_requests` on `ev=run_end` is about 21-23. Go back to
2 requests a post on a login redirect from a post that isn't limited, or two empty answers.

```bash
python3 <plugin>/skills/fetch-media/scripts/fetch_media.py --all --limit 20 --one-request --recheck .cache/recheck.txt
```

## How a thumbnail is fetched, and why this way

The pacing research (`docs/research/instagram-fetch-pacing/consolidated.md`, in the plugin
author's own data repo; the rules below are what it settled on, so you do not need it) plans for downloading each post's smallest video. The hub only needs one image per post, so this
skill asks yt-dlp to **read** the post without downloading anything:
`extract_info(url, download=False)`.

That answer already lists the post's images with their widths (Instagram's `image_versions2`).
The script takes the smallest one at least 600 px wide and downloads it with the same yt-dlp
object. macOS `sips` turns it into a 600 px JPEG. No image library is needed.

- **No video download** (except with `--video`). A reel's video is megabytes; its cover image is tens of kilobytes.
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
- **At most 117 posts a run (150 with `--one-request`), 3 runs a day, 2 hours apart.** The trial
  is 5 posts. The script holds to this itself: a `--limit` above the cap is cut to it
  (`MAX_POSTS`), and it reads its own log for past runs,
  refusing to start less than 2 hours after the last one ended (`ev=refused reason=run_gap`) or a
  4th time in 24 hours (`reason=day_cap`). The refusal line says when it may start (`may_start=`).
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
ev=run_start ytdlp=... sleep_req=6 gap_min=25 gap_max=55 cap=5 todo=5 skipped=0 requests_per_post=2 watch=on recheck=0
ev=post_start n=1 shortcode=EXAMPLE123
ev=ig_request step=session|ruling|page shortcode=EXAMPLE123
ev=sleep reason=sleep_requests|gap|long_pause|watch|empty|budget secs=...
ev=image_start / ev=image_done bytes=...
ev=post_ok shortcode=EXAMPLE123 kind=reel bytes=... secs=... ig_requests=2   (1 with --one-request)
ev=recheck shortcode=... why=login_redirect|empty          (--one-request: asked again the 2-request way)
ev=recheck_result shortcode=... result=ok|login_wall|...   (--recheck: nothing written)
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
2. **Use a python3 that has yt-dlp and PyYAML.** `python3 -c "import yt_dlp, yaml"`. If that
   fails, install both for that python3: `python3 -m pip install --user yt-dlp pyyaml` (a
   `brew install yt-dlp` gives the command only, which this script cannot import).
3. **Run the pilot first,** 5 posts, in the background, and watch the log:
   ```bash
   python3 <plugin>/skills/fetch-media/scripts/fetch_media.py --pilot <name> --limit 5
   grep ev= <data repo>/.cache/logs/fetch-media.log | tail
   ```
4. **Look at two thumbnails** (open the JPEGs) against their posts.
5. **On a stop, stop.** Do not retry. Report what `ev=rate_limited` says.
6. **Commit `data/media.yaml`** in the data repo. Never a thumbnail: they stay in iCloud.
7. **Go wider** only after the user has seen the trial. That is a change of scope, so ask with
   `AskUserQuestion`. The options: the rest of the pilot in one run (up to 117 posts, about 2 hours, and the log
   shows whether the pace holds), or another short trial first (slower, but less exposed if the
   first one showed warnings).

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/fetch_media.py` | Fetches one 600 px JPEG thumbnail per save not yet in `media.yaml`, logged out and paced; stops at the first block. Saves with a pin in `data/pins.yaml` (the ones on the hub's map) come first | The thumbnail trial on a pilot, then runs of up to 117 posts | `python3 scripts/fetch_media.py --pilot <name> --limit 5` (or `--all --limit 117`) |
| `scripts/fetch_media.py --one-request` | The same, at 1 instagram.com request a post: the "is this post viewable?" check is skipped, watch warnings are only logged, and the first login redirect or empty answer in a run is asked again the 2-request way | After a clean 20-post trial (above); runs of up to 150 posts | `python3 scripts/fetch_media.py --all --limit 150 --one-request` |
| `scripts/fetch_media.py --recheck <codes.txt>` | Asks for the listed posts first even if `media.yaml` has them, and writes nothing for them | The 20-post trial, to see what a known limited post answers now | `python3 scripts/fetch_media.py --all --limit 20 --one-request --recheck <codes.txt>` |
| `scripts/fetch_media.py --video` | Fetches a listed reel's video (smallest at least 540 px) and full-size cover, same pacing | Reels whose place is only on screen, for **read-frames** | `python3 scripts/fetch_media.py --video <codes.txt> --limit 100` |
| `scripts/test_fetch_media.py` | Offline tests with a fake yt-dlp: skipping done posts, the stop on a 429, the cookie refusal, the lock, the `media.yaml` shape, the video pick, the stop after 3 failed video downloads, and `--one-request` (1 request a post, warnings only logged, asking again once a run, the yt-dlp version check, `--recheck`) | After any change to the fetcher | `python3 scripts/test_fetch_media.py` |
