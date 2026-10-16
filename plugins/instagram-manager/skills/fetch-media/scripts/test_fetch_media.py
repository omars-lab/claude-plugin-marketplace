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


class FakeYDL:
    """Answers extract_info from a script: code → info dict, or an exception. Logs like yt-dlp does."""

    made = []

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

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
        log.debug(f"[Instagram] {code}: Checking post accessibility")
        log.debug(f"[Instagram] {code}: Downloading webpage")
        a = self.answers.get(code, reel(code))
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

    def run_main(self, answers=None, args=("--pilot", "fixture", "--limit", "5")):
        self.ydl = FakeYDL(answers or {})
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return fetch_media.main(list(args), ydl_factory=self.ydl.factory, sleep=self.sleeps.append)

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
        self.assertFalse(os.path.exists(path))         # it worked, so the cooldown is cleared

    def test_two_empty_answers_stop(self):
        empty = FakeError("ERROR: [Instagram] X: Instagram sent an empty media response. Check if this post ...")
        rc = self.run_main({"REELA": empty, "REELB": empty})
        self.assertEqual(rc, 1)
        self.assertIn("kind=empty_streak", self.log_lines("rate_limited")[0])
        self.assertEqual(self.media(), {})

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

    def test_at_most_100_posts(self):
        self.run_main(args=("--pilot", "fixture", "--limit", "500"))
        self.assertIn("cap=100 ", self.log_lines("run_start")[0])


class Pick(unittest.TestCase):
    def test_narrow_image_kept_as_is(self):
        url, width, kind = fetch_media.pick_image({"formats": [], "thumbnails": [{"url": "u", "width": 480}]})
        self.assertEqual((url, width, kind), ("u", 480, "photo"))

    def test_stop_signals(self):
        self.assertEqual(fetch_media.stop_signal("error: [instagram] x: http error 403: forbidden"), "http_403")
        self.assertIsNone(fetch_media.stop_signal("error: unable to download video data: http error 403"))
        self.assertIsNone(fetch_media.stop_signal("there is no video in this post"))


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

    def test_pick_video(self):
        url, w, h = fetch_media.pick_video({"formats": [{"url": "a", "width": 360, "height": 640}]})
        self.assertEqual((url, w, h), ("a", 360, 640))   # nothing big enough: the largest there is
        self.assertIsNone(fetch_media.pick_video({"formats": []}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
