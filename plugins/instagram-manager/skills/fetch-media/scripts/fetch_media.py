#!/usr/bin/env python3
"""fetch_media.py — one small JPEG thumbnail per saved post, fetched logged out and slowly.

    fetch_media.py --pilot NAME --limit 5     the pilot's saves, at most 5 this run
    fetch_media.py --all --limit 100          every save, at most 100 this run

Reads   $INSTAGRAM_HOME/.cache/saves.json           (from import-saves)
        $INSTAGRAM_HOME/config/collections.yaml     the pilots
        $INSTAGRAM_HOME/data/tags.yaml              places, so a pilot also takes saves tagged with its places
Writes  $INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg       about 600 px wide (iCloud; never in git)
        $INSTAGRAM_HOME/data/media.yaml             <code>: {thumb: <code>/thumb.jpg, kind, fetched: <date>}
                                                    or <code>: {error: private|login_wall|not_found|no_image}
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
  `sips` turns it into a JPEG 600 px wide. No video is downloaded.

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
    first run after a cooldown fetches one test post only.

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

from home import cache, home  # noqa: E402
from log import log, log_to  # noqa: E402

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
COOLDOWN_HOURS = {1: 24, 2: 48, 3: 72}

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


# ---------------------------------------------------------------- which saves

def in_pilot(save, tag, pilot):
    if set(save.get("collections") or []) & set(pilot.get("collections") or []):
        return True
    places = set((tag or {}).get("cities") or []) | set((tag or {}).get("hints") or [])
    return bool(set(pilot.get("cities") or []) & places)


def pick(saves, pilot, tags, media, limit):
    """Saves still to fetch, in export order: (todo, already recorded in media.yaml)."""
    todo, done = [], 0
    for s in saves:
        if pilot is not None and not in_pilot(s, tags.get(s["code"]), pilot):
            continue
        if s["code"] in media:
            done += 1
            continue
        todo.append(s)
    return (todo[:limit] if limit else todo), done


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
    if "restricted video" in low:
        return "login_wall"   # age-limited: needs a login, which we never use
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


def download_image(ydl, url, path):
    """The image's bytes into path, through the run's yt-dlp (same headers, no cookies of ours)."""
    from yt_dlp.networking import Request
    req = Request(url, headers={"Referer": "https://www.instagram.com/"}, extensions={"timeout": SOCKET_TIMEOUT})
    with deadline(IMAGE_DEADLINE):
        resp = ydl.urlopen(req)
        data = resp.read()
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def to_jpeg(src, dst, width):
    """src → a JPEG THUMB_WIDTH wide at dst (narrower images are kept at their size). macOS sips."""
    cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80"]
    if not width or width > THUMB_WIDTH:
        cmd += ["--resampleWidth", str(THUMB_WIDTH)]
    subprocess.run(cmd + [src, "--out", dst], check=True, capture_output=True, timeout=SIPS_TIMEOUT)


# ---------------------------------------------------------------- the run

class Run:
    def __init__(self, ydl, watcher, requests, media, sleep=time.sleep):
        self.ydl, self.watcher, self.requests, self.media = ydl, watcher, requests, media
        self.sleep = sleep
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
        t0 = time.time()
        log("post_start", n=n, shortcode=code)
        try:
            with deadline(POST_DEADLINE):
                info = self.ydl.extract_info(url, download=False)
        except Deadline:
            log("extract_timeout", shortcode=code, secs=POST_DEADLINE)
            return None
        except Exception as e:  # noqa: BLE001 — yt-dlp's DownloadError; read by its text, as the research says
            msg = str(e)
            low = msg.lower()
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
            return {"error": err} if err else None
        if self.watcher.stop:
            raise Stop(*self.watcher.stop)
        if self.pending_empty:   # the empty answer before this one was that post, not a block
            self.media[self.pending_empty] = {"error": "not_found"}
            self.pending_empty = None
        self.empty_streak = 0
        self.watch_rules(code, self.watcher.watch)

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


def main(argv=None, ydl_factory=None, sleep=time.sleep):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--limit", type=int, default=5, help="at most this many posts this run (default 5)")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)

    log_to(cache("logs", "fetch-media.log"))
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
        test_only = False
        if cd:
            until = dt.datetime.strptime(cd["until"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
            if now() < until:
                log("refused", reason="cooldown", until=cd["until"], level=cd.get("level"))
                return 4
            test_only = True   # the first run after a cooldown tries one post

        with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
            saves = json.load(fh)["saves"]
        pilot = None
        if args.pilot:
            pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
            if args.pilot not in pilots:
                sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
            pilot = pilots[args.pilot]
        media = load_yaml(MEDIA)
        limit = 1 if test_only else args.limit
        todo, done = pick(saves, pilot, load_yaml(os.path.join("data", "tags.yaml")), media, limit)

        if ydl_factory is None:
            try:
                import yt_dlp
            except ImportError:
                log("refused", reason="no_ytdlp", python=sys.executable)
                sys.exit(f"{sys.executable} has no yt_dlp: run this with a python3 that has it")
            ydl_factory, version = yt_dlp.YoutubeDL, yt_dlp.version.__version__
        else:
            version = "fake"
        log("run_start", ytdlp=version, impersonate="no", sleep_req=SLEEP_REQUESTS, gap_min=GAP[0], gap_max=GAP[1],
            cap=limit, scope=args.pilot or "all", todo=len(todo), skipped=done, test_only=test_only,
            cooldown_until=(cd or {}).get("until") or "none", media_dir=media_dir())

        stopped, reason = "no", ""
        with ydl_factory(opts) as ydl:
            run = Run(ydl, watcher, requests, media, sleep=sleep)
            for n, s in enumerate(todo, 1):
                if n > 1:
                    if (n - 1) % LONG_EVERY == 0:
                        run.pause("long_pause", *LONG_PAUSE)
                    else:
                        run.pause("gap", *GAP)
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
                if entry is not None:
                    media[s["code"]] = entry
                    write_yaml(MEDIA, media)   # after every post, so a stop loses nothing
                    if test_only and "thumb" in entry:
                        log("recovered", shortcode=s["code"])
                        os.remove(cooldown_path())
            write_yaml(MEDIA, media)
        log("run_end", ok=run.ok, bad=run.bad, skipped=done, stopped=stopped, reason=reason or "none",
            ig_requests=watcher.total, minutes=round((time.time() - run.started) / 60, 1))
        print(f"fetched {run.ok}, bad {run.bad}, already done {done}" + (f"; stopped: {reason}" if reason else ""))
        return 1 if stopped == "yes" else 0


if __name__ == "__main__":
    sys.exit(main())
