#!/usr/bin/env python3
"""Offline checks for fetch_media.py, on an invented data repo. No network and no yt-dlp: a fake
YoutubeDL answers with canned posts, and the image step writes a stand-in file.

    python3 skills/fetch-media/scripts/test_fetch_media.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import warnings
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_media  # noqa: E402
import yaml  # noqa: E402

REAL_RUN_GAP, REAL_RUNS_PER_DAY = fetch_media.RUN_GAP, fetch_media.RUNS_PER_DAY

COLLECTIONS = """collections:
  Fixture Town: {topics: [travel], cities: [Fixture State]}
pilots:
  fixture: {collections: [Fixture Town], cities: [Fixture State]}
"""


def save(code, collections=("Fixture Town",), kind="reel"):
    return {"code": code, "url": f"https://www.instagram.com/{kind}/{code}/", "kind": kind, "caption": "x",
            "hashtags": [], "owner": {"username": "example_creator"}, "collections": list(collections)}


SAVES = [save("REELA"), save("REELB"), save("PHOTOC", kind="p"), save("OUTSIDE", ["Fixture Recipes"]),
         save("TAGGED", ["Fixture Recipes"])]
TAGS = {"TAGGED": {"topics": ["travel"], "cities": ["Fixture State"]}}


def reel(code):
    return {"id": code, "formats": [{"url": "https://video.example/v.mp4"},
                                    {"url": f"https://video.example/{code}-360.mp4", "ext": "mp4", "width": 360,
                                     "height": 640},
                                    {"url": f"https://video.example/{code}-720.mp4", "ext": "mp4", "width": 720,
                                     "height": 1280},
                                    {"url": f"https://video.example/{code}-1080.mp4", "ext": "mp4", "width": 1080,
                                     "height": 1920},
                                    {"url": f"https://video.example/{code}-dash.mp4", "ext": "mp4", "width": 540,
                                     "height": 960, "acodec": "none"}],
            "thumbnails": [{"url": f"https://img.example/{code}-1080.jpg", "width": 1080},
                           {"url": f"https://img.example/{code}-640.jpg", "width": 640},
                           {"url": f"https://img.example/{code}-320.jpg", "width": 320}]}


def photo(code):
    return {"id": code, "formats": [], "thumbnails": [{"url": f"https://img.example/{code}.jpg", "width": 1080}]}


class FakeError(Exception):
    """Stands in for yt_dlp.utils.DownloadError."""


class FakeIE:
    """Stands in for yt-dlp's Instagram extractor: its _download_json is what --one-request wraps."""

    def __init__(self, ydl):
        self.ydl = ydl

    def _download_json(self, url, code, *_a, **_kw):
        self.ydl.opts["logger"].debug(f"[Instagram] {code}: Checking post accessibility")
        self.ydl.asked_ruling = True
        return {}


class FakeYDL:
    """Answers extract_info from a script: code → info dict, an exception, or a function of whether
    the "is this post viewable?" check was asked (for --one-request). Logs like yt-dlp does."""

    made = []

    def __init__(self, answers, warn=()):
        self.answers = answers
        self.warn = warn   # codes that get a watch warning
        self.calls = []
        self.ie = FakeIE(self)

    def get_info_extractor(self, key):
        assert key == "Instagram"
        return self.ie

    def factory(self, opts):
        self.opts = opts
        FakeYDL.made.append(opts)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        assert download is False, "the fetcher must never download video"
        code = url.rstrip("/").split("/")[-1]
        self.calls.append(code)
        log = self.opts["logger"]
        if len(self.calls) == 1:
            log.debug("[Instagram] Setting up session")
        else:
            log.debug("[Instagram] Sleeping 6.0 seconds ...")
        self.asked_ruling = False
        self.ie._download_json(f"https://i.instagram.com/api/v1{fetch_media.RULING}", code)
        if code in self.warn:
            log.warning(f"[Instagram] {code}: Instagram API is not granting access")
        log.debug(f"[Instagram] {code}: Downloading webpage")
        a = self.answers.get(code, reel(code))
        if callable(a):
            a = a(self.asked_ruling)
        if isinstance(a, Exception):
            raise a
        return a


def fake_image(_ydl, url, path, _secs=None):
    if "fail" in url:
        raise FakeError("unable to download video data: HTTP Error 403")
    with open(path, "wb") as fh:
        fh.write(url.encode())
    return len(url)


def fake_jpeg(src, dst, _width, max_width=None):
    with open(src, "rb") as a, open(dst, "wb") as b:
        b.write(a.read())


class Home(unittest.TestCase):
    """An invented data repo and media folder in temp folders."""

    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)   # log.log_to keeps its file open per run
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        self.media_dir = os.path.join(self.tmp.name, "media")
        os.makedirs(os.path.join(self.root, "config"))
        os.makedirs(os.path.join(self.root, "data"))
        os.makedirs(os.path.join(self.root, ".cache"))
        with open(os.path.join(self.root, "config", "collections.yaml"), "w") as fh:
            fh.write(COLLECTIONS)
        with open(os.path.join(self.root, "data", "tags.yaml"), "w") as fh:
            yaml.safe_dump(TAGS, fh)
        with open(os.path.join(self.root, ".cache", "saves.json"), "w") as fh:
            json.dump({"saves": SAVES}, fh)
        self.env = mock.patch.dict(os.environ, {"INSTAGRAM_HOME": self.root, "INSTAGRAM_MEDIA_DIR": self.media_dir})
        self.env.start()
        # Downloads are stubbed here, so a shell with INSTAGRAM_OFFLINE=1 (a trial sandbox) must not
        # make fetch refuse; patch.dict puts it back on stop.
        os.environ.pop("INSTAGRAM_OFFLINE", None)
        self.patches = [mock.patch.object(fetch_media, "download_image", fake_image),
                        mock.patch.object(fetch_media, "to_jpeg", fake_jpeg),
                        # most tests run several times in a row; RunRules checks the real rules
                        mock.patch.object(fetch_media, "RUN_GAP", dt.timedelta(0)),
                        mock.patch.object(fetch_media, "RUNS_PER_DAY", 99)]
        for p in self.patches:
            p.start()
        self.sleeps = []
        FakeYDL.made = []

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def run_main(self, answers=None, args=("--pilot", "fixture", "--limit", "5"), warn=(),
                 version=fetch_media.ONE_REQUEST_YTDLP):
        self.ydl = FakeYDL(answers or {}, warn)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return fetch_media.main(list(args), ydl_factory=self.ydl.factory, sleep=self.sleeps.append,
                                    version=version)

    def media(self):
        path = os.path.join(self.root, "data", "media.yaml")
        if not os.path.exists(path):
            return {}
        with open(path) as fh:
            return yaml.safe_load(fh) or {}

    def log_lines(self, ev):
        with open(os.path.join(self.root, ".cache", "logs", "fetch-media.log")) as fh:
            return [line for line in fh if f" ev={ev} " in line or line.rstrip().endswith(f" ev={ev}")]


class Fetch(Home):
    def test_media_yaml_shape_and_files(self):
        rc = self.run_main({"PHOTOC": photo("PHOTOC")})
        self.assertEqual(rc, 0)
        m = self.media()
        # the pilot's collection plus the save tagged with the pilot's place; not the other one
        self.assertEqual(sorted(m), ["PHOTOC", "REELA", "REELB", "TAGGED"])
        today = fetch_media.now().date().isoformat()
        self.assertEqual(m["REELA"], {"thumb": "REELA/thumb.jpg", "kind": "reel", "fetched": today})
        self.assertEqual(m["PHOTOC"]["kind"], "photo")
        with open(os.path.join(self.media_dir, "REELA", "thumb.jpg"), "rb") as fh:
            self.assertIn(b"REELA-640", fh.read())   # the smallest image at least 600 px wide

    def test_one_ytdlp_for_the_run_and_no_login(self):
        self.run_main()
        self.assertEqual(len(FakeYDL.made), 1)
        opts = FakeYDL.made[0]
        self.assertTrue(opts["ignoreconfig"])
        self.assertEqual(opts["sleep_interval_requests"], 6)
        self.assertEqual(fetch_media.refuse_login(opts), [])

    def test_waits_between_posts(self):
        self.run_main()
        gaps = [line for line in self.log_lines("sleep") if "reason=gap" in line]
        self.assertEqual(len(gaps), 3)   # 4 posts, a gap before each but the first
        self.assertTrue(all(25 <= s <= 55 for s in self.sleeps))

    def test_skip_if_done(self):
        self.run_main(args=("--pilot", "fixture", "--limit", "2"))
        self.assertEqual(self.ydl.calls, ["REELA", "REELB"])
        self.run_main()
        self.assertEqual(self.ydl.calls, ["PHOTOC", "TAGGED"])   # the first two are not asked for again

    def test_error_recorded_and_not_tried_again(self):
        err = FakeError("ERROR: [Instagram] REELB: This content is only available for registered users who "
                        "follow this account")
        self.run_main({"REELB": err})
        self.assertEqual(self.media()["REELB"], {"error": "private"})
        self.run_main()
        self.assertNotIn("REELB", self.ydl.calls)

    def test_audience_limited_recorded_and_not_tried_again(self):
        err = FakeError("ERROR: [Instagram] REELB: This content isn't available to everyone: It can't be seen "
                        "by certain audiences.")
        self.run_main({"REELB": err})
        self.assertEqual(self.media()["REELB"], {"error": "login_wall"})
        self.run_main()
        self.assertNotIn("REELB", self.ydl.calls)

    def test_carousel_takes_first_slide(self):
        carousel = {"_type": "playlist", "entries": [photo("SLIDE1"), photo("SLIDE2")]}
        self.run_main({"REELA": carousel}, args=("--pilot", "fixture", "--limit", "1"))
        self.assertEqual(self.media()["REELA"]["kind"], "carousel")
        with open(os.path.join(self.media_dir, "REELA", "thumb.jpg"), "rb") as fh:
            self.assertIn(b"SLIDE1", fh.read())


class Stops(Home):
    def test_stop_on_429(self):
        err = FakeError("ERROR: [Instagram] REELB: Unable to download webpage: HTTP Error 429: Too Many Requests")
        rc = self.run_main({"REELB": err})
        self.assertEqual(rc, 1)
        self.assertEqual(self.ydl.calls, ["REELA", "REELB"])   # nothing after the 429, no retry
        self.assertEqual(sorted(self.media()), ["REELA"])        # the walled post is not marked as bad
        stop = self.log_lines("rate_limited")
        self.assertEqual(len(stop), 1)
        self.assertIn("kind=http_429", stop[0])
        with open(os.path.join(self.root, ".cache", "fetch-media.cooldown.json")) as fh:
            self.assertEqual(json.load(fh)["level"], 1)

    def test_stop_on_login_wall(self):
        err = FakeError("ERROR: [Instagram] REELA: The webpage request was redirected to the login page. You have "
                        "exceeded the rate-limit for accessing posts anonymously")
        self.assertEqual(self.run_main({"REELA": err}), 1)
        self.assertIn("kind=login_wall", self.log_lines("rate_limited")[0])

    def test_cooldown_refuses_then_one_test_post(self):
        self.run_main({"REELA": FakeError("HTTP Error 429: Too Many Requests")})
        self.assertEqual(self.run_main(), 4)
        self.assertEqual(self.ydl.calls, [])
        path = os.path.join(self.root, ".cache", "fetch-media.cooldown.json")
        with open(path) as fh:
            cd = json.load(fh)
        cd["until"] = "2000-01-01T00:00:00Z"   # the cooldown is over
        with open(path, "w") as fh:
            json.dump(cd, fh)
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.ydl.calls, ["REELA"])   # one test post only
        with open(path) as fh:
            cd = json.load(fh)
        self.assertNotIn("until", cd)                  # it worked, so the cooldown is over
        self.assertEqual(cd["level"], 1)               # but a stop in the next 2 days is a second in a row

    def test_two_gentle_days_after_a_test_post(self):
        path = os.path.join(self.root, ".cache", "fetch-media.cooldown.json")
        gentle = {"gentle_until": fetch_media.stamp(fetch_media.now() + dt.timedelta(days=1)), "level": 1}
        with open(path, "w") as fh:
            json.dump(gentle, fh)
        self.assertEqual(self.run_main(args=("--pilot", "fixture", "--limit", "500")), 0)
        self.assertTrue(all(50 <= s <= 110 for s in self.sleeps))   # twice the 25-55 s pauses
        self.assertIn("cap=58", self.log_lines("run_start")[0])     # half of 117
        os.remove(os.path.join(self.root, "data", "media.yaml"))   # so the posts are asked for again
        self.run_main({"PHOTOC": FakeError("HTTP Error 429: Too Many Requests")},
                      args=("--pilot", "fixture", "--limit", "500"))
        with open(path) as fh:
            self.assertEqual(json.load(fh)["level"], 2)              # the next stop in a row
        gentle["gentle_until"] = "2000-01-01T00:00:00Z"              # 2 clean days have passed
        with open(path, "w") as fh:
            json.dump(gentle, fh)
        self.sleeps.clear()
        self.assertEqual(self.run_main(), 0)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(all(25 <= s <= 55 for s in self.sleeps))

    def test_two_empty_answers_stop(self):
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        rc = self.run_main({"REELA": empty, "REELB": empty})
        self.assertEqual(rc, 1)
        self.assertIn("kind=empty_streak", self.log_lines("rate_limited")[0])
        self.assertEqual(self.media(), {})

    def known_post(self):
        with open(os.path.join(self.root, "data", "media.yaml"), "w") as fh:
            yaml.safe_dump({"KNOWN": {"thumb": "KNOWN/thumb.jpg", "kind": "image"}}, fh)

    def test_two_deleted_posts_side_by_side_are_not_a_block(self):
        self.known_post()
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        self.assertEqual(self.run_main({"REELA": empty, "REELB": empty}), 0)
        self.assertEqual(self.ydl.calls[:3], ["REELA", "REELB", "KNOWN"])   # a post we have, asked once
        self.assertEqual(self.media()["REELA"], {"error": "not_found"})
        self.assertEqual(self.media()["REELB"], {"error": "not_found"})
        self.assertIn("thumb", self.media()["PHOTOC"])                       # and the run carried on

    def test_a_known_post_empty_too_is_a_block(self):
        self.known_post()
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        self.assertEqual(self.run_main({"REELA": empty, "REELB": empty, "KNOWN": empty}), 1)
        self.assertIn("kind=empty_streak", self.log_lines("rate_limited")[0])
        self.assertNotIn("REELA", self.media())

    def test_an_empty_test_post_is_checked_against_a_known_post(self):
        self.known_post()
        path = os.path.join(self.root, ".cache", "fetch-media.cooldown.json")
        with open(path, "w") as fh:
            json.dump({"until": "2000-01-01T00:00:00Z", "level": 2}, fh)
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        self.assertEqual(self.run_main({"REELA": empty}), 0)
        self.assertEqual(self.ydl.calls, ["KNOWN", "REELA"])   # a post we have first, then the test post
        self.assertEqual(self.media()["REELA"], {"error": "not_found"})
        with open(path) as fh:
            cd = json.load(fh)
        self.assertIn("gentle_until", cd)   # not blocked: the gentle days start
        self.assertEqual(cd["level"], 1)    # and the stop was that deleted post, so it doesn't count

    def test_a_test_run_stops_when_a_known_post_is_empty(self):
        self.known_post()
        path = os.path.join(self.root, ".cache", "fetch-media.cooldown.json")
        with open(path, "w") as fh:
            json.dump({"until": "2000-01-01T00:00:00Z", "level": 1}, fh)
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        self.assertEqual(self.run_main({"KNOWN": empty}), 1)
        self.assertEqual(self.ydl.calls, ["KNOWN"])   # 1 request, and the post still missing isn't asked
        with open(path) as fh:
            self.assertEqual(json.load(fh)["level"], 2)

    def test_an_empty_post_is_not_asked_again_before_a_known_post_answers(self):
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        args = ("--pilot", "fixture", "--limit", "5", "--one-request")
        self.assertEqual(self.run_main({"REELA": empty}, args=args), 0)
        self.assertEqual(self.ydl.calls[:2], ["REELA", "REELB"])   # no 2-request re-ask of REELA
        self.assertEqual(self.log_lines("recheck"), [])

    def test_one_empty_answer_is_a_missing_post(self):
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        self.run_main({"REELA": empty})
        self.assertEqual(self.media()["REELA"], {"error": "not_found"})
        self.assertIn(300, self.sleeps)   # the 5 minute wait after it


class Refusals(Home):
    def test_refuses_a_cookie_option(self):
        real = fetch_media.ydl_options
        with mock.patch.object(fetch_media, "ydl_options", lambda lg: {**real(lg), "cookiefile": "cookies.txt"}):
            rc = self.run_main()
        self.assertEqual(rc, 2)
        self.assertEqual(FakeYDL.made, [])   # yt-dlp was never even set up
        self.assertIn("keys=cookiefile", self.log_lines("refused")[0])

    def test_refuses_browser_cookies_too(self):
        self.assertEqual(fetch_media.refuse_login({"cookiesfrombrowser": ("example-browser",)}),
                         ["cookiesfrombrowser"])

    def test_lock(self):
        with fetch_media.run_lock() as other:
            self.assertFalse(other)
            rc = self.run_main()   # a second run while the first holds the lock
        self.assertEqual(rc, 3)
        self.assertEqual(FakeYDL.made, [])
        self.assertIn("reason=locked", self.log_lines("refused")[0])
        self.assertEqual(self.run_main(), 0)   # free again once the first run ends


class RunRules(Home):
    """At most 100 posts a run, 2 hours from one run's end to the next start, 3 runs a day."""

    def setUp(self):
        super().setUp()
        for p in [mock.patch.object(fetch_media, "RUN_GAP", REAL_RUN_GAP),
                  mock.patch.object(fetch_media, "RUNS_PER_DAY", REAL_RUNS_PER_DAY)]:
            p.start()
            self.patches.append(p)

    def past(self, *runs):
        """Write a log holding these runs, each (hours ago it started, hours ago it ended)."""
        t = fetch_media.now()
        lines = []
        for pid, (start, end) in enumerate(runs, 100):
            lines.append(f"{fetch_media.stamp(t - dt.timedelta(hours=start))} pid={pid} ev=run_start cap=5\n")
            lines.append(f"{fetch_media.stamp(t - dt.timedelta(hours=end))} pid={pid} ev=run_end ok=5\n")
        os.makedirs(os.path.join(self.root, ".cache", "logs"), exist_ok=True)
        with open(os.path.join(self.root, ".cache", "logs", "fetch-media.log"), "w") as fh:
            fh.writelines(lines)

    def test_two_hours_from_the_last_run_ending(self):
        self.past((3, 1))   # started 3 hours ago, ended 1 hour ago
        self.assertEqual(self.run_main(), 5)
        self.assertEqual(FakeYDL.made, [])
        self.assertIn("reason=run_gap", self.log_lines("refused")[0])
        self.past((4, 2.1))
        self.assertEqual(self.run_main(), 0)

    def test_three_runs_a_day(self):
        self.past((20, 19), (15, 14), (10, 9))
        self.assertEqual(self.run_main(), 5)
        refused = self.log_lines("refused")[0]
        self.assertIn("reason=day_cap", refused)
        may = fetch_media.now() + dt.timedelta(hours=4)   # 24 hours after the first of the three
        self.assertIn(f"may_start={fetch_media.stamp(may)[:13]}", refused)
        self.past((26, 25), (15, 14), (10, 9))   # the first now falls outside the 24 hours
        self.assertEqual(self.run_main(), 0)

    def test_two_runs_a_day_in_the_gentle_days(self):
        fetch_media.write_json(fetch_media.cooldown_path(), {
            "gentle_until": fetch_media.stamp(fetch_media.now() + dt.timedelta(days=1)), "level": 1})
        self.past((20, 19), (10, 9))
        self.assertEqual(self.run_main(), 5)
        refused = self.log_lines("refused")[0]
        self.assertIn("reason=day_cap", refused)
        may = fetch_media.now() + dt.timedelta(hours=4)   # 24 hours after the first of the two
        self.assertIn(f"may_start={fetch_media.stamp(may)[:13]}", refused)
        self.past((26, 25), (10, 9))
        self.assertEqual(self.run_main(), 0)

    def test_at_most_117_posts_or_150_with_one_request(self):
        self.run_main(args=("--pilot", "fixture", "--limit", "500"))
        self.assertIn("cap=117 ", self.log_lines("run_start")[0])
        self.past((5, 4))
        self.run_main(args=("--pilot", "fixture", "--limit", "500", "--one-request"))
        self.assertIn("cap=150 ", self.log_lines("run_start")[1])


LOGIN_REDIRECT = FakeError("ERROR: [Instagram] X: The webpage request was redirected to the login page. You "
                           "have exceeded the rate-limit for accessing posts anonymously")
LIMITED = FakeError("ERROR: [Instagram] X: This content isn't available to everyone: It can't be seen by "
                    "certain audiences.")


def limited_post(asked_ruling):
    """A post limited by age or audience: only the "is it viewable?" check names it; the page
    alone redirects to the login page."""
    return LIMITED if asked_ruling else LOGIN_REDIRECT


class OneRequest(Home):
    """--one-request: the "is this post viewable?" check is skipped, so 1 instagram.com request a post."""

    ONE = ("--pilot", "fixture", "--limit", "5", "--one-request")

    def test_one_request_a_post(self):
        self.assertEqual(self.run_main(args=self.ONE), 0)
        self.assertEqual(len(self.media()), 4)
        self.assertEqual([line for line in self.log_lines("ig_request") if "step=ruling" in line], [])
        oks = self.log_lines("post_ok")
        self.assertIn("ig_requests=2", oks[0])   # the run's home page visit, then the post's page
        self.assertTrue(all("ig_requests=1" in line for line in oks[1:]))
        start = self.log_lines("run_start")[0]
        self.assertIn("requests_per_post=1 ", start)
        self.assertIn("watch=off ", start)

    def test_today_still_asks_the_check(self):
        self.run_main()
        self.assertTrue(all("ig_requests=2" in line for line in self.log_lines("post_ok")[1:]))
        self.assertIn("requests_per_post=2 watch=on ", self.log_lines("run_start")[0])

    def test_watch_warnings_logged_not_acted_on(self):
        every = ("REELA", "REELB", "PHOTOC", "TAGGED")
        self.assertEqual(self.run_main(args=self.ONE, warn=every), 0)
        self.assertEqual(len(self.media()), 4)   # 4 warnings in 4 posts and no stop
        self.assertEqual([line for line in self.log_lines("sleep") if "reason=watch" in line], [])
        self.assertEqual(len([line for line in self.log_lines("warn") if "acted=no" in line]), 4)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".cache", "fetch-media.state.json")))

    def test_limited_post_found_by_asking_again(self):
        self.assertEqual(self.run_main({"REELB": limited_post}, args=self.ONE), 0)
        self.assertEqual(self.media()["REELB"], {"error": "login_wall"})
        self.assertEqual(self.ydl.calls, ["REELA", "REELB", "REELB", "PHOTOC", "TAGGED"])
        self.assertIn("why=login_redirect", self.log_lines("recheck")[0])
        self.assertEqual(self.log_lines("rate_limited"), [])

    def test_asking_again_once_a_run(self):
        rc = self.run_main({"REELA": limited_post, "REELB": limited_post}, args=self.ONE)
        self.assertEqual(rc, 1)   # the second redirect in the run is a stop, as today
        self.assertEqual(self.ydl.calls, ["REELA", "REELA", "REELB"])
        self.assertEqual(self.media(), {"REELA": {"error": "login_wall"}})
        self.assertIn("kind=login_wall", self.log_lines("rate_limited")[0])

    def test_a_real_block_still_stops_after_asking_again(self):
        rc = self.run_main({"REELA": LOGIN_REDIRECT}, args=self.ONE)
        self.assertEqual(rc, 1)
        self.assertEqual(self.ydl.calls, ["REELA", "REELA"])   # 2 more requests, then the stop
        self.assertEqual(self.media(), {})

    def test_refuses_another_ytdlp(self):
        rc = self.run_main(args=self.ONE, version="2099.01.01")
        self.assertEqual(rc, 6)
        self.assertEqual(FakeYDL.made, [])
        self.assertIn("reason=ytdlp_version", self.log_lines("refused")[0])
        self.assertEqual(self.log_lines("run_start"), [])   # not counted as a run
        self.assertEqual(self.run_main(version="2099.01.01"), 0)   # today's way works on any yt-dlp

    def test_recheck_asks_a_known_post_and_keeps_its_entry(self):
        with open(os.path.join(self.root, "data", "media.yaml"), "w") as fh:
            yaml.safe_dump({"REELB": {"error": "login_wall"}}, fh)
        codes = os.path.join(self.root, ".cache", "recheck.txt")
        with open(codes, "w") as fh:
            fh.write("REELB\n")
        self.run_main({"REELB": limited_post}, args=self.ONE + ("--recheck", codes))
        self.assertEqual(self.ydl.calls[:3], ["REELB", "REELB", "REELA"])   # first, and asked again
        self.assertIn("result=login_wall", self.log_lines("recheck_result")[0])
        self.assertEqual(self.media()["REELB"], {"error": "login_wall"})
        self.run_main(args=("--pilot", "fixture", "--limit", "5", "--recheck", codes))
        self.assertIn("result=ok", self.log_lines("recheck_result")[1])
        self.assertEqual(self.media()["REELB"], {"error": "login_wall"})   # never written over


class Pick(unittest.TestCase):
    def test_narrow_image_kept_as_is(self):
        url, width, kind = fetch_media.pick_image({"formats": [], "thumbnails": [{"url": "u", "width": 480}]})
        self.assertEqual((url, width, kind), ("u", 480, "photo"))

    def test_stop_signals(self):
        self.assertEqual(fetch_media.stop_signal("error: [instagram] x: http error 403: forbidden"), "http_403")
        self.assertIsNone(fetch_media.stop_signal("error: unable to download video data: http error 403"))
        self.assertIsNone(fetch_media.stop_signal("there is no video in this post"))

    def test_saves_on_the_map_go_first(self):
        saves = [{"code": c} for c in ("A1", "B2", "C3", "D4", "E5")]
        todo, done = fetch_media.pick(saves, None, {}, {"A1": {}}, 3, first={"D4": [], "C3": []})
        self.assertEqual([s["code"] for s in todo], ["C3", "D4", "B2"])   # export order within each
        self.assertEqual(done, 1)


class Video(Home):
    """--video: the listed reels' video and full cover, added to what media.yaml already has."""

    def setUp(self):
        super().setUp()
        self.patches.append(mock.patch.object(fetch_media, "has_sound", lambda _p: True))
        self.patches[-1].start()
        self.codes = os.path.join(self.root, ".cache", "codes.txt")
        with open(self.codes, "w") as fh:
            fh.write("REELB  # a comment\nPHOTOC\nNOSUCH\nREELA\n")

    def test_listed_reels_get_video_and_cover(self):
        self.run_main(args=("--pilot", "fixture", "--limit", "1"))   # REELA's thumbnail first
        rc = self.run_main({"PHOTOC": photo("PHOTOC")}, args=("--video", self.codes, "--limit", "5"))
        self.assertEqual(rc, 0)
        self.assertEqual(self.ydl.calls, ["REELB", "PHOTOC", "REELA"])   # the list's order; unknown codes skipped
        m = self.media()
        today = fetch_media.now().date().isoformat()
        self.assertEqual(m["REELA"], {"thumb": "REELA/thumb.jpg", "kind": "reel", "fetched": today,
                                      "video": "REELA/video.mp4", "cover": "REELA/cover.jpg", "video_size": "720x1280",
                                      "sound": True, "video_fetched": today})
        self.assertEqual(m["PHOTOC"], {"video_error": "not_a_reel"})
        with open(os.path.join(self.media_dir, "REELA", "video.mp4"), "rb") as fh:
            self.assertIn(b"REELA-720", fh.read())   # the smallest at least 540 px across, with sound
        with open(os.path.join(self.media_dir, "REELA", "cover.jpg"), "rb") as fh:
            self.assertIn(b"REELA-1080", fh.read())   # the widest cover
        self.run_main(args=("--video", self.codes))
        self.assertEqual(self.ydl.calls, [])   # done ones are not asked for again

    def test_three_failed_videos_stop(self):
        failing = {c: {**reel(c), "formats": [{"url": f"https://video.example/{c}-fail.mp4"}]}
                   for c in ("REELA", "REELB", "TAGGED")}
        with open(self.codes, "w") as fh:
            fh.write("REELA\nREELB\nTAGGED\n")
        rc = self.run_main(failing, args=("--video", self.codes))
        self.assertEqual(rc, 1)
        self.assertIn("kind=file_streak", self.log_lines("rate_limited")[0])
        self.assertNotIn("video", self.media().get("REELA", {}))

    def test_a_reel_instagram_will_not_serve_keeps_its_thumbnail(self):
        self.run_main(args=("--pilot", "fixture", "--limit", "1"))   # REELA's thumbnail first
        thumb = dict(self.media()["REELA"])
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        with open(self.codes, "w") as fh:
            fh.write("REELA\nREELB\n")
        self.run_main({"REELA": empty}, args=("--video", self.codes))
        self.assertEqual(self.media()["REELA"], {**thumb, "video_error": "not_found"})
        self.run_main(args=("--video", self.codes))
        self.assertEqual(self.ydl.calls, [])   # neither is asked for again

    def test_pick_video(self):
        url, w, h = fetch_media.pick_video({"formats": [{"url": "a", "width": 360, "height": 640}]})
        self.assertEqual((url, w, h), ("a", 360, 640))   # nothing big enough: the largest there is
        self.assertIsNone(fetch_media.pick_video({"formats": []}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
