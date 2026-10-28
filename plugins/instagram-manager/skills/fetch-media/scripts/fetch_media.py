#!/usr/bin/env python3
"""fetch_media.py — one small JPEG thumbnail per saved post, fetched logged out and slowly.

    fetch_media.py --pilot NAME --limit 5     the pilot's saves, at most 5 this run
    fetch_media.py --all --limit 117          every save, at most 117 this run
    fetch_media.py --video CODES.txt          the reels listed (one code a line): their video and full
                                              cover too, for reading names off the screen
    fetch_media.py --all --one-request        1 instagram.com request a post instead of 2 (off by default;
                                              see "With --one-request" below)
    fetch_media.py --all --recheck CODES.txt  ask for these posts first even if media.yaml has them, and
                                              write nothing for them (to try a known limited post)

Reads   $INSTAGRAM_HOME/.cache/saves.json           (from import-saves)
        $INSTAGRAM_HOME/config/collections.yaml     the pilots
        $INSTAGRAM_HOME/data/tags.yaml              places, so a pilot also takes saves tagged with its places
Writes  $INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg       about 600 px wide (iCloud; never in git)
        $INSTAGRAM_MEDIA_DIR/<code>/video.mp4       with --video: a reel's video, the smallest at least 540 px
                                                    on its short side (on-screen text stays readable)
        $INSTAGRAM_MEDIA_DIR/<code>/cover.jpg       with --video: the cover at full size, not cut square
        $INSTAGRAM_HOME/data/media.yaml             <code>: {thumb: <code>/thumb.jpg, kind, fetched: <date>}
                                                    or <code>: {error: private|login_wall|not_found|no_image};
                                                    --video adds video, cover, video_size, sound, video_fetched
                                                    (or video_error: no_video|not_a_reel|not_found|...,
                                                    beside the thumbnail it already had)
        $INSTAGRAM_HOME/.cache/logs/fetch-media.log one ev= line per event
        $INSTAGRAM_HOME/.cache/fetch-media.lock     held while a run goes; a second run refuses
        $INSTAGRAM_HOME/.cache/fetch-media.cooldown.json   written on a stop; runs refuse until it ends
        $INSTAGRAM_HOME/.cache/fetch-media.state.json      the "watch" warnings seen in the first 10 posts

How a post is fetched
  One yt_dlp.YoutubeDL object for the whole run, one extract_info(url, download=False) per post.
  That is 2 requests to instagram.com per post (the "is this post viewable?" check and the post's
  page), plus 1 at the start of the run. The answer lists the post's images with their widths; the
  script takes the smallest one at least 600 px wide (a reel's cover, a photo post's image, a
  carousel's first slide) and downloads it from Instagram's image servers, not instagram.com. macOS
  `sips` turns it into a JPEG 600 px wide. No video is downloaded, except with --video.

With --video
  The same read of the post, so the same 2 instagram.com requests. Then the video file and the
  widest cover come from Instagram's file servers, like the thumbnail. The video picked is a plain
  mp4 (one that may carry sound, not a separate video or audio stream), the smallest whose short
  side is at least 540 px, else the largest. ffprobe records whether it has sound. Three file
  downloads failing in a row is a stop, as the research says. A post's thumbnail is kept.

With --one-request (docs/research/instagram-media-alternatives/consolidated.md in the data repo)
  yt-dlp's "is this post viewable?" check is answered "ok" without asking instagram.com; the post's
  page alone has the images. So 1 request a post, and that check's 6 s wait goes too. Three things
  follow from skipping it:
  - The "watch" warnings come from that check, so they mean nothing here: they are logged
    (acted=no), never paused or stopped on, and never feed the baseline.
  - The words that name a post limited by age or audience ("isn't available to everyone") come
    from that check too. So the first login redirect or empty answer in a run asks that post
    again the 2-request way: a limited post is written down as login_wall, anything else is
    handled as today (a login redirect stops the run). Once a run only.
  - It leans on yt-dlp's code, so it refuses any yt-dlp but ONE_REQUEST_YTDLP.
  A run may hold more posts in this mode (MAX_POSTS), since the limit is counted in requests.

Never logged in
  No cookies, no login, no netrc, ever. yt-dlp gets ignoreconfig, so no config file can add them,
  and the script refuses to start if any login or cookie option is set.

Pacing (docs/research/instagram-fetch-pacing/consolidated.md in the data repo)
  - yt-dlp waits 6 s before each instagram.com request (sleep_interval_requests).
  - The script waits a fresh random 25-55 s between posts, and 3-6 minutes every 25 posts.
  - Hourly brake: before a post, if the last hour already holds 150 instagram.com requests, wait.
  - Stop at once, and write a cooldown, on a login wall ("redirected to the login page" or
    "rate-limit"), an HTTP 429, an Instagram 401/403, two empty answers in a row, or too many
    "watch" warnings. The log line is ev=rate_limited. A stop is never retried inside a run.
  - Cooldown: 24 h after the first stop, 48 h after a second in a row, 3 days after a third. The
    first run after a cooldown fetches one test post only. Once that works, the next 2 days are
    gentle: half the posts a run and twice the pauses between posts. A stop in those days counts
    as the next stop in a row; 2 clean days clear the cooldown file, so a later stop is a first.
  - Runs: at most 117 posts each (150 with --one-request), at least 2 hours from the end of one
    to the start of the next,
    and at most 3 started in any 24 hours. The script reads its own log for the past runs and
    refuses to start early (ev=refused reason=run_gap or day_cap, with the time it may start).

Every call that can hang has a timeout: the network (30 s per read, and a hard limit on each post
and each image), and sips.

Needs yt_dlp and PyYAML (a python3 that has both), and macOS for sips.
"""

import argparse
import collections
import contextlib
import datetime as dt
import errno
import fcntl
import json
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
import yaml  # noqa: E402

from home import cache, home, offline, read_saves  # noqa: E402
from log import log, log_to  # noqa: E402
from pilot import in_pilot  # noqa: E402

MEDIA = os.path.join("data", "media.yaml")
DEFAULT_MEDIA_DIR = os.path.join("~", "Library", "Mobile Documents", "com~apple~CloudDocs", "CloudDesktop",
                                 "data", "instagram")

SLEEP_REQUESTS = 6           # s before each instagram.com request (yt-dlp waits)
GAP = (25, 55)               # s between posts
LONG_EVERY = 25              # posts
LONG_PAUSE = (180, 360)      # s
HOUR_BRAKE = 150             # instagram.com requests in the last 60 minutes
EMPTY_WAIT = 300             # s after one empty answer
WATCH_PAUSE = (60, 120)      # s after a watch warning
WATCH_STOP = 3               # watch warnings in the last 10 posts
WATCH_WINDOW = 10
SOCKET_TIMEOUT = 30          # s per network read
POST_DEADLINE = 180          # s for the whole extract_info of one post
IMAGE_DEADLINE = 60          # s for one image download
SIPS_TIMEOUT = 60
THUMB_WIDTH = 600
VIDEO_SHORT = 540            # px on the video's short side: enough to read on-screen text
VIDEO_DEADLINE = 300         # s for one video download
VIDEO_FAIL_STOP = 3          # file downloads failing in a row
PROBE_TIMEOUT = 30
COOLDOWN_HOURS = {1: 24, 2: 48, 3: 72}
GENTLE = dt.timedelta(days=2)   # after a test post works: half the posts a run, twice the pauses
# Posts in one run, by instagram.com requests a post. 2: today's way, 117 after the first 7 days with
# no stop. 1: --one-request, 150 for its first runs, then 200 (the daily limit is counted in requests).
MAX_POSTS = {2: 117, 1: 150}
ONE_REQUEST_YTDLP = "2026.08.19"   # the yt-dlp whose code --one-request was read against
RULING = "/web/get_ruling_for_content/"   # yt-dlp's "is this post viewable?" address
RUN_GAP = dt.timedelta(hours=2)   # from the end of one run to the start of the next
RUNS_PER_DAY = 3             # runs started in any 24 hours

# Options that would log in or send cookies. Any of them set means the script will not start.
LOGIN_KEYS = ("cookiefile", "cookiesfrombrowser", "username", "password", "usenetrc", "netrc_location",
              "netrc_cmd", "twofactor", "videopassword", "ap_username", "ap_password")

# yt-dlp's own lines → what they mean (lower case substrings).
IG_STEPS = (("setting up session", "session"), ("checking post accessibility", "ruling"),
            ("downloading json metadata", "graphql"), ("downloading webpage", "page"))
WATCH = (("no csrf token set by instagram api", "no_csrf"), ("instagram api is not granting access", "not_granting"))


class Stop(Exception):
    """A stop signal: the connection is walled or close to it. kind is for ev=rate_limited."""

    def __init__(self, kind, msg=""):
        super().__init__(msg)
        self.kind = kind


class Deadline(Exception):
    pass


# ---------------------------------------------------------------- files

def media_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("INSTAGRAM_MEDIA_DIR") or DEFAULT_MEDIA_DIR))


def load_yaml(rel):
    path = os.path.join(home(), rel)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_yaml(rel, data):
    path = os.path.join(home(), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=True, allow_unicode=True, default_flow_style=None, width=1000)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, path)


def now():
    return dt.datetime.now(dt.timezone.utc)


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------- which saves

def pick(saves, pilot, tags, media, limit, first=()):
    """Saves still to fetch, in export order, the codes in `first` (the saves on the hub's map)
    ahead of the rest: (todo, already recorded in media.yaml)."""
    todo, done = [], 0
    for s in saves:
        if pilot is not None and not in_pilot(s, tags.get(s["code"]), pilot):
            continue
        if s["code"] in media:
            done += 1
            continue
        todo.append(s)
    first = set(first)
    todo.sort(key=lambda s: s["code"] not in first)   # stable, so export order holds within each
    return (todo[:limit] if limit else todo), done


def pick_codes(saves, codes, media, limit):
    """With --video: the listed codes, in the list's order, whose video is not fetched yet."""
    by_code = {s["code"]: s for s in saves}
    todo, done = [], 0
    for c in codes:
        entry = media.get(c) or {}
        if c not in by_code or "error" in entry:
            continue
        if "video" in entry or "video_error" in entry:
            done += 1
            continue
        todo.append(by_code[c])
    return (todo[:limit] if limit else todo), done


def read_codes(path):
    """Post codes from a text file, one a line; # starts a comment."""
    with open(path, encoding="utf-8") as fh:
        return [w for line in fh for w in line.split("#")[0].split()[:1]]


def pick_recheck(saves, codes):
    """--recheck: the listed codes, in the list's order, whatever media.yaml says about them."""
    by_code = {s["code"]: s for s in saves}
    return [by_code[c] for c in codes if c in by_code]


# ---------------------------------------------------------------- the lock and the cooldown

@contextlib.contextmanager
def run_lock(path=None):
    """Only one run at a time. Yields False (and holds nothing) if another run has the lock."""
    path = path or cache("fetch-media.lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                fh.seek(0)
                yield fh.read().strip() or "?"   # the other run's pid
                return
            raise
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        try:
            yield False
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    finally:
        fh.close()


def cooldown_path():
    return cache("fetch-media.cooldown.json")


def write_cooldown(kind):
    prev = read_json(cooldown_path(), {}) or {}
    level = min(int(prev.get("level") or 0) + 1, 3)
    until = now() + dt.timedelta(hours=COOLDOWN_HOURS[level])
    write_json(cooldown_path(), {"until": stamp(until), "level": level, "kind": kind, "at": stamp(now())})
    log("cooldown", until=stamp(until), level=level, kind=kind)


def past_runs(path):
    """[start, end] of each run in the log, oldest first; end is None for a run that was cut off."""
    runs, open_by_pid = [], {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"(\S+) pid=(\d+) ev=(run_start|run_end)\b", line)
                if not m:
                    continue
                t = dt.datetime.strptime(m[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                if m[3] == "run_start":
                    open_by_pid[m[2]] = [t, None]
                    runs.append(open_by_pid[m[2]])
                elif m[2] in open_by_pid:
                    open_by_pid.pop(m[2])[1] = t
    except OSError:
        return []
    return runs


def too_soon(runs, t):
    """(reason, when it may start) if a run may not start at t, else None."""
    if runs:
        start, end = runs[-1]
        last = end or start
        if t - last < RUN_GAP:
            return "run_gap", last + RUN_GAP
    day = [start for start, _ in runs if t - start < dt.timedelta(hours=24)]
    if len(day) >= RUNS_PER_DAY:
        return "day_cap", min(day) + dt.timedelta(hours=24)
    return None


# ---------------------------------------------------------------- yt-dlp

def ydl_options(logger):
    """The only options yt-dlp gets. No cookies, no login, no config files."""
    return {
        "ignoreconfig": True,
        "logger": logger,
        "quiet": True,
        "noprogress": True,
        "sleep_interval_requests": SLEEP_REQUESTS,
        "socket_timeout": SOCKET_TIMEOUT,
        "ignore_no_formats_error": True,   # a photo post has no video; its images still come back
        "playlist_items": "1",             # a carousel: only its first slide
        "skip_download": True,
    }


def refuse_login(opts):
    """The names of any login or cookie options that are set (the run must not start if any are)."""
    return [k for k in LOGIN_KEYS if opts.get(k)]


class SkipRuling:
    """--one-request: yt-dlp's "is this post viewable?" check gets {"status": "ok"} with no request.
    Every other call goes through. `on` is set False to ask one post the 2-request way."""

    def __init__(self, ydl):
        self.on = True
        ie = ydl.get_info_extractor("Instagram")   # the one the run's extract_info uses
        real = ie._download_json

        def download_json(url_or_request, *args, **kwargs):
            if self.on and RULING in str(url_or_request):
                return {"status": "ok"}
            return real(url_or_request, *args, **kwargs)

        ie._download_json = download_json


class Watcher:
    """yt-dlp's logger: turns its lines into ev= lines and remembers what matters for this post."""

    def __init__(self, requests):
        self.requests = requests   # deque of instagram.com request times (shared with the run)
        self.total = 0             # instagram.com requests this run
        self.code = None
        self.reset()

    def reset(self, code=None):
        self.code = code
        self.watch = []        # watch-warning kinds seen on this post
        self.stop = None       # (kind, msg) if a warning was itself a stop signal
        self.ig = 0

    def retry(self):
        """Asking the same post again: forget its warnings, keep counting its requests."""
        self.watch = []
        self.stop = None

    def debug(self, msg):
        low = msg.lower()
        m = re.search(r"sleeping ([\d.]+) seconds", low)
        if m:
            log("sleep", reason="sleep_requests", secs=m.group(1), shortcode=self.code)
            return
        for text, step in IG_STEPS:
            if text in low:
                self.requests.append(time.time())
                self.ig += 1
                self.total += 1
                log("ig_request", step=step, shortcode=self.code)
                return

    info = debug

    def warning(self, msg):
        low = msg.lower()
        for text, kind in WATCH:
            if text in low:
                self.watch.append(kind)
                log("warn_seen", kind=kind, shortcode=self.code)
                return
        sig = stop_signal(low)
        if sig:
            self.stop = (sig, msg[:200])
        log("ytdlp_warning", shortcode=self.code, msg=msg[:200])

    def error(self, msg):
        log("ytdlp_error", shortcode=self.code, msg=msg[:200])


def stop_signal(low):
    """The stop kind for an error or warning text (lower case), or None."""
    if "redirected to the login page" in low or "rate-limit" in low:
        return "login_wall"
    if "http error 429" in low:
        return "http_429"
    if "[instagram]" in low and "unable to download video data" not in low:
        if "http error 401" in low:
            return "http_401"
        if "http error 403" in low:
            return "http_403"
    return None


def post_error(low):
    """A problem with this one post (not the connection): the media.yaml error, or None."""
    if "only available for registered users who follow this account" in low:
        return "private"
    if "restricted video" in low or "isn't available to everyone" in low:
        return "login_wall"   # age- or audience-limited: needs a login, which we never use
    return None


def pick_image(info):
    """(url, width, kind) of the image to keep: the smallest at least THUMB_WIDTH wide, else the widest."""
    kind = "reel"
    if info.get("_type") == "playlist":
        kind = "carousel"
        entries = [e for e in (info.get("entries") or []) if e]
        info = entries[0] if entries else {}
    elif not info.get("formats"):
        kind = "photo"
    thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url")]
    if not thumbs and info.get("thumbnail"):
        thumbs = [{"url": info["thumbnail"]}]
    if not thumbs:
        return None, None, kind
    wide = [t for t in thumbs if (t.get("width") or 0) >= THUMB_WIDTH]
    best = min(wide, key=lambda t: t["width"]) if wide else max(thumbs, key=lambda t: t.get("width") or 0)
    return best["url"], best.get("width"), kind


def pick_video(info):
    """(url, width, height) of the video to keep, or None: a plain mp4 (not a separate video-only or
    audio-only stream), the smallest whose short side is at least VIDEO_SHORT, else the largest."""
    plain = [f for f in info.get("formats") or [] if f.get("url") and f.get("vcodec") != "none"
             and f.get("acodec") != "none" and (f.get("ext") in (None, "mp4"))]
    if not plain:
        plain = [f for f in info.get("formats") or [] if f.get("url") and f.get("vcodec") != "none"]
    if not plain:
        return None
    short = lambda f: min(f.get("width") or 0, f.get("height") or 0)  # noqa: E731
    big = [f for f in plain if short(f) >= VIDEO_SHORT]
    best = min(big, key=short) if big else max(plain, key=short)
    return best["url"], best.get("width"), best.get("height")


def pick_cover(info):
    """(url, width) of the widest image: the cover at full size, before any square crop."""
    if info.get("_type") == "playlist":
        info = next((e for e in info.get("entries") or [] if e), {})
    thumbs = [t for t in info.get("thumbnails") or [] if t.get("url")] or (
        [{"url": info["thumbnail"]}] if info.get("thumbnail") else [])
    if not thumbs:
        return None, None
    best = max(thumbs, key=lambda t: (t.get("width") or 0) * (t.get("height") or 1))
    return best["url"], best.get("width")


def has_sound(path):
    """True if the file has an audio stream, False if not, None if ffprobe is missing or fails."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                              "-of", "csv=p=0", path], capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(out.stdout.strip()) if out.returncode == 0 else None


@contextlib.contextmanager
def deadline(secs):
    """Raise Deadline if the block runs longer than secs (main thread only)."""
    def on_alarm(_sig, _frame):
        raise Deadline()
    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(int(secs))
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def download_image(ydl, url, path, secs=IMAGE_DEADLINE):
    """The file's bytes into path, through the run's yt-dlp (same headers, no cookies of ours)."""
    from yt_dlp.networking import Request
    req = Request(url, headers={"Referer": "https://www.instagram.com/"}, extensions={"timeout": SOCKET_TIMEOUT})
    size = 0
    with deadline(secs):
        resp = ydl.urlopen(req)
        with open(path, "wb") as fh:
            while True:
                block = resp.read(1 << 20)
                if not block:
                    break
                fh.write(block)
                size += len(block)
    return size


def to_jpeg(src, dst, width, max_width=THUMB_WIDTH):
    """src → a JPEG max_width wide at dst (narrower images are kept at their size; max_width None
    keeps every size). macOS sips."""
    cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80"]
    if max_width and (not width or width > max_width):
        cmd += ["--resampleWidth", str(max_width)]
    subprocess.run(cmd + [src, "--out", dst], check=True, capture_output=True, timeout=SIPS_TIMEOUT)


# ---------------------------------------------------------------- the run

class Run:
    def __init__(self, ydl, watcher, requests, media, sleep=time.sleep, video=False, one_request=None):
        self.ydl, self.watcher, self.requests, self.media = ydl, watcher, requests, media
        self.sleep = sleep
        self.video = video
        self.one_request = one_request   # the SkipRuling with --one-request, else None
        self.rechecked = False           # --one-request: a post was asked again the 2-request way
        self.keep = set()                # --recheck codes: media.yaml is never written for them
        self.file_fails = 0    # video downloads failing in a row
        self.started = time.time()
        self.ok = self.bad = 0
        self.empty_streak = 0
        self.pending_empty = None
        self.window = collections.deque(maxlen=WATCH_WINDOW)   # watch warnings per post, last 10
        self.state = read_json(cache("fetch-media.state.json"), {}) or {}

    def pause(self, reason, lo, hi=None):
        secs = round(random.uniform(lo, hi) if hi is not None else lo)
        log("sleep", reason=reason, secs=secs)
        self.sleep(secs)

    def last_hour(self):
        cut = time.time() - 3600
        while self.requests and self.requests[0] < cut:
            self.requests.popleft()
        return len(self.requests)

    def brake(self):
        while self.last_hour() >= HOUR_BRAKE:
            wait = max(1, int(self.requests[0] + 3600 - time.time()) + 1)
            log("sleep", reason="budget", secs=wait, requests_last_hour=len(self.requests))
            self.sleep(wait)

    def watch_rules(self, code, kinds):
        """Count this post's watch warnings; pause or stop as the research says."""
        if self.one_request:   # they come from the check that was skipped: log them, never act on them
            for kind in kinds:
                log("warn", kind=kind, shortcode=code, acted="no")
            return
        self.window.append(len(kinds))
        first = self.state.setdefault("first_posts", [])
        if "baseline" not in self.state:
            first.append(len(kinds))
            if len(first) >= WATCH_WINDOW:
                self.state["baseline"] = sum(1 for n in first if n)
                log("baseline", count=self.state["baseline"])
            write_json(cache("fetch-media.state.json"), self.state)
        recent = sum(1 for n in self.window if n)
        for kind in kinds:
            log("warn", kind=kind, shortcode=code, count_last10=recent)
        base = self.state.get("baseline")
        if base is None:                       # still learning the normal rate: never stop on these yet
            if kinds:
                self.pause("watch", *WATCH_PAUSE)
            return
        if base >= WATCH_STOP:                 # warnings are normal on this path
            if recent >= base + WATCH_STOP:
                raise Stop("warn_streak", f"{recent} watch warnings in the last {WATCH_WINDOW} posts")
            return
        if recent >= WATCH_STOP:
            raise Stop("warn_streak", f"{recent} watch warnings in the last {WATCH_WINDOW} posts")
        if kinds:
            self.pause("watch", *WATCH_PAUSE)

    def fetch(self, n, save):
        """One post. Returns its media.yaml entry, or None to leave it for a later run."""
        code = save["code"]
        url = save.get("url") or f"https://www.instagram.com/p/{code}/"
        self.watcher.reset(code)
        if self.one_request:
            self.one_request.on = True
        t0 = time.time()
        log("post_start", n=n, shortcode=code)
        for attempt in (1, 2):
            try:
                with deadline(POST_DEADLINE):
                    info = self.ydl.extract_info(url, download=False)
                break
            except Deadline:
                log("extract_timeout", shortcode=code, secs=POST_DEADLINE)
                return None
            except Exception as e:  # noqa: BLE001 — yt-dlp's DownloadError; read by its text, as the research says
                msg = str(e)
                low = msg.lower()
                if attempt == 1 and self.may_recheck(code, low):
                    continue
                sig = stop_signal(low) or (self.watcher.stop and self.watcher.stop[0])
                if sig:
                    raise Stop(sig, msg[:200])
                if "instagram sent an empty media response" in low:
                    self.empty_streak += 1
                    log("empty_media", shortcode=code, streak=self.empty_streak)
                    if self.empty_streak >= 2:
                        raise Stop("empty_streak", msg[:200])
                    self.pending_empty = code
                    self.pause("empty", EMPTY_WAIT)
                    return None
                err = post_error(low)
                log("post_bad", shortcode=code, reason=err or "unknown", msg=msg[:200])
                self.bad += 1
                self.empty_streak = 0
                return self.failed(code, err) if err else None
        if self.watcher.stop:
            raise Stop(*self.watcher.stop)
        if self.pending_empty:   # the empty answer before this one was that post, not a block
            if self.pending_empty not in self.keep:
                self.media[self.pending_empty] = self.failed(self.pending_empty, "not_found")
            self.pending_empty = None
        self.empty_streak = 0
        self.watch_rules(code, self.watcher.watch)

        if self.video:
            return self.fetch_video(code, info or {}, t0)
        img, width, kind = pick_image(info or {})
        if not img:
            log("post_bad", shortcode=code, reason="no_image", kind=kind)
            self.bad += 1
            return {"error": "no_image"}
        folder = os.path.join(media_dir(), code)
        os.makedirs(folder, exist_ok=True)
        dst = os.path.join(folder, "thumb.jpg")
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "image")
            log("image_start", shortcode=code, width=width or "?")
            try:
                size = download_image(self.ydl, img, raw)
            except Deadline:
                log("image_timeout", shortcode=code, secs=IMAGE_DEADLINE)
                return None
            except Exception as e:  # noqa: BLE001 — any failure here is the image server's, not instagram.com's
                log("image_fail", shortcode=code, msg=str(e)[:200])
                return None
            log("image_done", shortcode=code, bytes=size)
            try:
                to_jpeg(raw, dst, width)
            except (subprocess.SubprocessError, OSError) as e:
                log("sips_fail", shortcode=code, msg=str(e)[:200])
                return None
        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            log("post_bad", shortcode=code, reason="no_file")
            return None
        self.ok += 1
        log("post_ok", shortcode=code, kind=kind, bytes=os.path.getsize(dst), secs=round(time.time() - t0, 1),
            ig_requests=self.watcher.ig, path="page")
        return {"thumb": f"{code}/thumb.jpg", "kind": kind, "fetched": now().date().isoformat()}

    def may_recheck(self, code, low):
        """--one-request: a login redirect or an empty answer may be a post limited by age or audience,
        which only the skipped check names. True (and set up) to ask this post again the 2-request
        way; once a run, so a real block costs at most 2 more requests."""
        if not self.one_request or self.rechecked:
            return False
        if self.watcher.stop and self.watcher.stop[0] != "login_wall":   # a 429 or the like: a block
            return False
        if "redirected to the login page" in low:
            why = "login_redirect"
        elif "instagram sent an empty media response" in low:
            why = "empty"
        else:
            return False
        self.rechecked = True
        self.one_request.on = False
        self.watcher.retry()
        log("recheck", shortcode=code, why=why)
        self.pause("recheck", *GAP)
        return True

    def failed(self, code, err):
        """The entry for a post Instagram would not serve. A --video run keeps what media.yaml already has
        (the thumbnail stays on its pages) and notes the error beside it, so the reel is not asked for again."""
        if self.video:
            return {**(self.media.get(code) or {}), "video_error": err}
        return {"error": err}

    def fetch_video(self, code, info, t0):
        """--video: the reel's video and its full cover, added to its media.yaml entry."""
        entry = dict(self.media.get(code) or {})
        _, _, kind = pick_image(info)
        if kind != "reel":
            log("post_bad", shortcode=code, reason="not_a_reel", kind=kind)
            self.bad += 1
            return {**entry, "video_error": "not_a_reel"}
        picked = pick_video(info)
        if not picked:
            log("post_bad", shortcode=code, reason="no_video")
            self.bad += 1
            return {**entry, "video_error": "no_video"}
        url, w, h = picked
        folder = os.path.join(media_dir(), code)
        os.makedirs(folder, exist_ok=True)
        dst = os.path.join(folder, "video.mp4")
        log("video_start", shortcode=code, size=f"{w or '?'}x{h or '?'}")
        try:
            size = download_image(self.ydl, url, dst + ".part", VIDEO_DEADLINE)
        except Deadline:
            log("video_timeout", shortcode=code, secs=VIDEO_DEADLINE)
            return self.file_failed(code)
        except Exception as e:  # noqa: BLE001 — the file server's failure, not instagram.com's
            log("video_fail", shortcode=code, msg=str(e)[:200])
            return self.file_failed(code)
        if not size:
            log("video_fail", shortcode=code, msg="empty file")
            return self.file_failed(code)
        os.replace(dst + ".part", dst)
        self.file_fails = 0
        sound = has_sound(dst)
        log("video_done", shortcode=code, bytes=size, sound={True: "yes", False: "no"}.get(sound, "unknown"))
        out = {**entry, "video": f"{code}/video.mp4", "video_fetched": now().date().isoformat()}
        if w and h:
            out["video_size"] = f"{w}x{h}"
        if sound is not None:
            out["sound"] = sound
        cover, cw = pick_cover(info)
        if cover:
            with tempfile.TemporaryDirectory() as tmp:
                raw = os.path.join(tmp, "image")
                try:
                    download_image(self.ydl, cover, raw)
                    to_jpeg(raw, os.path.join(folder, "cover.jpg"), cw, max_width=None)
                    out["cover"] = f"{code}/cover.jpg"
                    log("cover_done", shortcode=code, width=cw or "?")
                except Deadline:
                    log("image_timeout", shortcode=code, secs=IMAGE_DEADLINE)
                except Exception as e:  # noqa: BLE001 — the cover is a nice-to-have; the video is kept
                    log("cover_fail", shortcode=code, msg=str(e)[:200])
        self.ok += 1
        log("post_ok", shortcode=code, kind="reel", bytes=size, secs=round(time.time() - t0, 1),
            ig_requests=self.watcher.ig, path="video")
        return out

    def file_failed(self, code):
        """A video download failed: leave the post for a later run; three in a row is a stop."""
        self.file_fails += 1
        if self.file_fails >= VIDEO_FAIL_STOP:
            raise Stop("file_streak", f"{self.file_fails} video downloads failed in a row")
        return None


def main(argv=None, ydl_factory=None, sleep=time.sleep, version="fake"):
    """version: what a test's ydl_factory stands in for (the real one reads yt-dlp's own)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    scope.add_argument("--video", metavar="CODES.txt",
                       help="a file of reel codes, one a line: fetch their video and full cover")
    ap.add_argument("--limit", type=int, default=5, help="at most this many posts this run (default 5)")
    ap.add_argument("--one-request", action="store_true",
                    help="skip yt-dlp's \"is this post viewable?\" check: 1 instagram.com request a post")
    ap.add_argument("--recheck", metavar="CODES.txt",
                    help="ask for these posts first even if media.yaml has them; nothing is written for them")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.recheck and args.video:
        ap.error("--recheck is for thumbnail runs, not --video")
    per_post = 1 if args.one_request else 2

    log_path = cache("logs", "fetch-media.log")
    log_to(log_path)
    if offline():
        log("refused", reason="offline")
        print("fetch_media: INSTAGRAM_OFFLINE is set, so nothing is fetched from Instagram", file=sys.stderr)
        return 2
    requests = collections.deque()
    watcher = Watcher(requests)
    opts = ydl_options(watcher)
    bad_keys = refuse_login(opts)
    if bad_keys:
        log("refused", reason="login_option", keys=",".join(bad_keys))
        return 2

    with run_lock() as other:
        if other:
            log("refused", reason="locked", other_pid=other)
            return 3
        cd = read_json(cooldown_path(), None)
        test_only = gentle = False
        if cd and cd.get("until"):
            if now() < parse_stamp(cd["until"]):
                log("refused", reason="cooldown", until=cd["until"], level=cd.get("level"))
                return 4
            test_only = True   # the first run after a cooldown tries one post
        elif cd and cd.get("gentle_until"):
            gentle = now() < parse_stamp(cd["gentle_until"])
            if not gentle:
                os.remove(cooldown_path())   # 2 clean days: a later stop is a first stop again
                cd = None
        early = too_soon(past_runs(log_path), now())
        if early:
            log("refused", reason=early[0], may_start=stamp(early[1]))
            return 5

        saves = read_saves(args.saved)["saves"]
        pilot = None
        if args.pilot:
            pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
            if args.pilot not in pilots:
                sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
            pilot = pilots[args.pilot]
        media = load_yaml(MEDIA)
        limit = 1 if test_only else min(args.limit, MAX_POSTS[per_post] // (2 if gentle else 1))
        slow = 2 if gentle else 1
        gap, long_pause = (GAP[0] * slow, GAP[1] * slow), (LONG_PAUSE[0] * slow, LONG_PAUSE[1] * slow)
        again = []
        if args.video:
            todo, done = pick_codes(saves, read_codes(args.video), media, limit)
        else:
            todo, done = pick(saves, pilot, load_yaml(os.path.join("data", "tags.yaml")), media, limit,
                              first=load_yaml(os.path.join("data", "pins.yaml")))
            if args.recheck:
                again = pick_recheck(saves, read_codes(args.recheck))
                todo = (again + [s for s in todo if s not in again])[:limit]
        again = {s["code"] for s in again}

        if ydl_factory is None:
            try:
                import yt_dlp
            except ImportError:
                log("refused", reason="no_ytdlp", python=sys.executable)
                sys.exit(f"{sys.executable} has no yt_dlp: run this with a python3 that has it")
            ydl_factory, version = yt_dlp.YoutubeDL, yt_dlp.version.__version__
        if args.one_request and version != ONE_REQUEST_YTDLP:
            log("refused", reason="ytdlp_version", ytdlp=version, needs=ONE_REQUEST_YTDLP)
            print(f"fetch_media: --one-request was checked against yt-dlp {ONE_REQUEST_YTDLP}, not {version}",
                  file=sys.stderr)
            return 6
        log("run_start", ytdlp=version, impersonate="no", sleep_req=SLEEP_REQUESTS, gap_min=gap[0], gap_max=gap[1],
            cap=limit, scope=args.pilot or ("video" if args.video else "all"), todo=len(todo), skipped=done, test_only=test_only,
            requests_per_post=per_post, watch="off" if args.one_request else "on", recheck=len(again),
            cooldown_until=(cd or {}).get("until") or "none", gentle_until=(cd or {}).get("gentle_until") or "none",
            media_dir=media_dir())

        stopped, reason = "no", ""
        with ydl_factory(opts) as ydl:
            skip = SkipRuling(ydl) if args.one_request else None
            run = Run(ydl, watcher, requests, media, sleep=sleep, video=bool(args.video), one_request=skip)
            run.keep = again
            for n, s in enumerate(todo, 1):
                if n > 1:
                    if (n - 1) % LONG_EVERY == 0:
                        run.pause("long_pause", *long_pause)
                    else:
                        run.pause("gap", *gap)
                run.brake()
                if n % 10 == 0:
                    log("budget", requests_last_hour=run.last_hour())
                try:
                    entry = run.fetch(n, s)
                except Stop as e:
                    stopped, reason = "yes", e.kind
                    log("rate_limited", kind=e.kind, shortcode=s["code"], posts_since_start=n,
                        ig_requests_since_start=watcher.total,
                        minutes_since_start=round((time.time() - run.started) / 60, 1),
                        requests_last_hour=run.last_hour(), msg=str(e))
                    write_cooldown(e.kind)
                    break
                if s["code"] in again:   # asked only to see what it answers now; media.yaml keeps what it had
                    log("recheck_result", shortcode=s["code"],
                        result=(entry or {}).get("error") or ("ok" if entry else "none"))
                elif entry is not None:
                    media[s["code"]] = entry
                    write_yaml(MEDIA, media)   # after every post, so a stop loses nothing
                    if test_only and ("video" in entry if args.video else "thumb" in entry):
                        gentle_until = stamp(now() + GENTLE)
                        log("recovered", shortcode=s["code"], gentle_until=gentle_until)
                        write_json(cooldown_path(), {"gentle_until": gentle_until, "level": cd.get("level"),
                                                     "kind": cd.get("kind"), "at": cd.get("at")})
            write_yaml(MEDIA, media)
        log("run_end", ok=run.ok, bad=run.bad, skipped=done, stopped=stopped, reason=reason or "none",
            ig_requests=watcher.total, minutes=round((time.time() - run.started) / 60, 1))
        print(f"fetched {run.ok}, bad {run.bad}, already done {done}" + (f"; stopped: {reason}" if reason else ""))
        return 1 if stopped == "yes" else 0


if __name__ == "__main__":
    sys.exit(main())
