#!/usr/bin/env python3
"""Offline checks for extract_stills.py, on an invented data repo. No model and no network: the video
is three coloured scenes ffmpeg makes on the spot, and the words on its frames are written by hand.

    python3 skills/extract-stills/scripts/test_extract_stills.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_stills as es  # noqa: E402
import yaml  # noqa: E402

HAVE_TOOLS = all(shutil.which(t) for t in ("ffmpeg", "ffprobe", "img2webp", "webpmux"))

COLLECTIONS = """collections:
  Fixture Trips: {topics: [travel], cities: [Fixture State]}
pilots:
  fixture: {collections: [Fixture Trips], cities: [Fixture State]}
"""
PLACES = {"places": {"Fixture State": {"kind": "state", "lat": 39.0, "lon": -119.0},
                     "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 40.0, "lon": -120.0}}}
TAGS = {"LISTED": {"cities": ["Fixture Town"]}, "NOVID": {"cities": ["Fixture Town"]}}
SPOTS = [{"name": "Example Cove Beach", "said": "Example Cove", "near": "Fixture Town", "lat": 40.01, "lon": -120.0},
         {"name": "Example Diner", "said": "the diner", "near": "Fixture Town", "lat": 40.0, "lon": -120.01},
         {"name": "Example Lookout", "said": "Example Lookout", "near": "Fixture Town", "lat": 40.02, "lon": -120.02}]
PINS = {"LISTED": SPOTS, "NOVID": SPOTS[:1]}
MEDIA = {"LISTED": {"kind": "reel", "thumb": "LISTED/thumb.jpg", "video": "LISTED/video.mp4"},
         "NOVID": {"kind": "reel", "thumb": "NOVID/thumb.jpg"}}


def save(code):
    return {"code": code, "url": f"https://www.instagram.com/reel/{code}/", "kind": "reel", "caption": "Three stops",
            "hashtags": [], "owner": {"username": "example_creator", "name": "Example"},
            "collections": ["Fixture Trips"]}


@unittest.skipUnless(HAVE_TOOLS, "needs ffmpeg and img2webp")
class Stills(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("INSTAGRAM_HOME", "INSTAGRAM_MEDIA_DIR")}
        os.environ["INSTAGRAM_HOME"] = os.path.join(self.tmp.name, "home")
        os.environ["INSTAGRAM_MEDIA_DIR"] = os.path.join(self.tmp.name, "media")
        self.write("config/collections.yaml", COLLECTIONS)
        self.write("data/places.yaml", PLACES)
        self.write("data/tags.yaml", TAGS)
        self.write("data/media.yaml", MEDIA)
        self.write("data/pins.yaml", PINS)
        self.write(".cache/saves.json", {"saves": [save("LISTED"), save("NOVID")]})
        self.make_video("LISTED")
        # The cove's name is on the white scene, the lookout's on the navy one (as "EXAMPLE  LOOKOUT",
        # spaced as OCR spaces it); the diner's never shows.
        frames = [{"n": 1, "t": 0.0, "file": "frame-01.jpg", "text": "Three stops"},
                  {"n": 2, "t": 2.0, "file": "frame-02.jpg", "text": "Example Cove!"},
                  {"n": 3, "t": 4.0, "file": "frame-03.jpg", "text": "", "vision": "EXAMPLE  LOOKOUT"}]
        self.write("text.json", {"video": "LISTED/video.mp4", "seconds": 6.0, "frames": frames, "sheets": []},
                   base=self.media("LISTED", "frames"))

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def path(self, rel):
        return os.path.join(os.environ["INSTAGRAM_HOME"], rel)

    def media(self, *rel):
        return os.path.join(os.environ["INSTAGRAM_MEDIA_DIR"], *rel)

    def write(self, rel, data, base=None):
        path = os.path.join(base, rel) if base else self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if isinstance(data, str):
                fh.write(data)
            elif path.endswith(".json"):
                json.dump(data, fh)
            else:
                yaml.safe_dump(data, fh)

    def read(self, rel):
        with open(self.path(rel)) as fh:
            return yaml.safe_load(fh) or {}

    def make_video(self, code):
        """Three scenes of 2 s each: black, white, navy."""
        os.makedirs(self.media(code), exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for colour in ("black", "white", "navy"):
            cmd += ["-f", "lavfi", "-i", f"color=c={colour}:s=360x640:d=2:r=10"]
        cmd += ["-filter_complex", "concat=n=3:v=1:a=0", "-pix_fmt", "yuv420p", self.media(code, "video.mp4")]
        subprocess.run(cmd, check=True, timeout=60)

    def run_stills(self, *extra):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            es.main(["--pilot", "fixture", *extra])
        return out.getvalue()

    def test_each_spot_is_cut_where_its_name_is_on_screen(self):
        out = self.run_stills()
        rows = self.read("data/stills.yaml")
        self.assertEqual(list(rows), ["LISTED"])   # NOVID has no video
        by = {r["name"]: r for r in rows["LISTED"]}
        self.assertEqual((by["Example Cove Beach"]["frame"], by["Example Cove Beach"]["t"]), (2, 2.0))
        self.assertEqual((by["Example Lookout"]["frame"], by["Example Lookout"]["t"]), (3, 4.0))
        self.assertEqual(by["Example Diner"], {"name": "Example Diner", "said": "the diner", "how": "not_on_screen"})
        self.assertIn("2 spots have a still and a clip (2 cut this run; 0 from the moment their area is on screen), "
                      "1 never show", out)

        cove = by["Example Cove Beach"]
        self.assertEqual(cove["still"], "LISTED/spots/still-example-cove-beach.jpg")
        still = self.media(cove["still"])
        width = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width", "-of", "csv=p=0", still], capture_output=True, text=True).stdout
        self.assertEqual(width.strip(), str(es.STILL_WIDTH))
        # The still is from the white scene, so it is bright.
        mean = subprocess.run(["ffmpeg", "-hide_banner", "-i", still, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                               "-f", "null", "-"], capture_output=True, text=True).stderr
        self.assertGreater(float(mean.split("lavfi.signalstats.YAVG=")[1].split()[0]), 200)
        with open(self.media(cove["clip"]), "rb") as fh:
            head = fh.read(64)
        self.assertEqual((head[:4], head[8:12]), (b"RIFF", b"WEBP"))
        self.assertIn(b"ANIM", head)   # an animated WebP, so it loops

    def test_a_rerun_cuts_nothing_new_and_a_hand_time_is_kept(self):
        self.run_stills()
        rows = self.read("data/stills.yaml")
        self.assertIn("(0 cut this run;", self.run_stills())
        diner = next(r for r in rows["LISTED"] if r["name"] == "Example Diner")
        diner.update({"t": 1.0, "by": "hand"})   # a person saw the diner at 1 s
        self.write("data/stills.yaml", rows)
        self.assertIn("(1 cut this run;", self.run_stills())
        diner = next(r for r in self.read("data/stills.yaml")["LISTED"] if r["name"] == "Example Diner")
        self.assertEqual((diner["t"], diner["how"], diner["by"]), (1.0, "hand", "hand"))
        self.assertTrue(os.path.isfile(self.media(diner["still"])))

    def test_a_clip_near_the_end_starts_earlier(self):
        self.write("text.json", {"video": "LISTED/video.mp4", "seconds": 6.0, "frames": [
            {"n": 1, "t": 5.5, "file": "frame-01.jpg", "text": "Example Cove"}], "sheets": []},
            base=self.media("LISTED", "frames"))
        self.run_stills()
        cove = next(r for r in self.read("data/stills.yaml")["LISTED"] if r["name"] == "Example Cove Beach")
        info = subprocess.run(["webpmux", "-info", self.media(cove["clip"])], capture_output=True, text=True).stdout
        # img2webp merges frames that look the same (this video is plain colour), so count the time,
        # not the frames: the clip starts at 3 s and runs the full 3 s (1 s white, then 2 s navy).
        rows = [line.split() for line in info.splitlines() if re.match(r"\s*\d+:", line)]
        self.assertEqual([int(r[6]) for r in rows], [1000, 2000])

    def road_trip(self, *texts):
        """The lookout moves to a second town, and each frame shows the given text."""
        self.write("data/pins.yaml", {"LISTED": SPOTS[:2] + [{**SPOTS[2], "said": "the lookout", "near": "Fixture Bay"}]})
        frames = [{"n": i + 1, "t": 2.0 * i, "file": f"frame-0{i + 1}.jpg", "text": t} for i, t in enumerate(texts)]
        self.write("text.json", {"video": "LISTED/video.mp4", "seconds": 6.0, "frames": frames, "sheets": []},
                   base=self.media("LISTED", "frames"))
        out = self.run_stills()
        return {r["name"]: r for r in self.read("data/stills.yaml")["LISTED"]}, out

    def test_a_road_trip_spot_gets_the_moment_its_area_is_on_screen(self):
        self.write("data/places.yaml", {"places": {**PLACES["places"], "Fixture Bay": {"kind": "city", "lat": 41, "lon": -121}}})
        # The title card names both towns, so it is nobody's moment.
        by, out = self.road_trip("Fixture Town to Fixture Bay", "Stop 1. Fixture Town", "Stop 2. Fixture Bay")
        for spot in ("Example Cove Beach", "Example Diner"):   # neither name is on screen; their town is
            self.assertEqual((by[spot]["how"], by[spot]["area"], by[spot]["t"]), ("area", "Fixture Town", 2.0))
            self.assertEqual(by[spot]["still"], "LISTED/spots/still-area-fixture-town.jpg")
        self.assertEqual((by["Example Lookout"]["area"], by["Example Lookout"]["t"]), ("Fixture Bay", 4.0))
        self.assertTrue(os.path.isfile(self.media("LISTED/spots/clip-area-fixture-town.webp")))
        self.assertIn("(2 cut this run; 3 from the moment their area is on screen)", out)

    def test_one_area_on_screen_is_the_whole_reel_not_a_part(self):
        self.write("data/places.yaml", {"places": {**PLACES["places"], "Fixture Bay": {"kind": "city", "lat": 41, "lon": -121}}})
        by, _ = self.road_trip("Free things to do in Fixture Town", "", "")
        self.assertEqual({r["how"] for r in by.values()}, {"not_on_screen"})

    def test_a_whole_state_on_screen_is_not_an_area(self):
        self.write("data/pins.yaml", {"LISTED": [{**SPOTS[1], "near": "Fixture State"}]})
        self.write("text.json", {"video": "LISTED/video.mp4", "seconds": 6.0, "frames": [
            {"n": 1, "t": 0.0, "file": "frame-01.jpg", "text": "Best of Fixture State"}], "sheets": []},
            base=self.media("LISTED", "frames"))
        self.run_stills()
        self.assertEqual(self.read("data/stills.yaml")["LISTED"][0]["how"], "not_on_screen")

    def test_need_video_lists_the_reels_with_two_spots_and_no_video(self):
        self.write("data/pins.yaml", {"LISTED": SPOTS, "NOVID": SPOTS[:2], "GONE": SPOTS[:2], "NOSHOW": SPOTS[:2]})
        self.write("data/media.yaml", {**MEDIA, "GONE": {"error": "not_found"},
                                       "NOSHOW": {"kind": "reel", "thumb": "NOSHOW/thumb.jpg", "video_error": "not_found"}})
        self.write("data/tags.yaml", {**TAGS, "GONE": {"cities": ["Fixture Town"]}, "NOSHOW": {"cities": ["Fixture Town"]}})
        self.write(".cache/saves.json", {"saves": [save(c) for c in ("LISTED", "NOVID", "GONE", "NOSHOW")]})
        self.assertIn("1 reels naming 2 spots have no video yet", self.run_stills("--need-video"))
        with open(self.path(".cache/stills/need-video.txt")) as fh:
            self.assertEqual(fh.read(), "NOVID\n")   # GONE and NOSHOW failed last time, so they are not asked for again
        self.write("data/pins.yaml", PINS)   # one spot: its cover is already its picture
        self.run_stills("--need-video")
        with open(self.path(".cache/stills/need-video.txt")) as fh:
            self.assertEqual(fh.read(), "")
        self.assertFalse(os.path.exists(self.path("data/stills.yaml")))   # nothing was cut

    def test_slug(self):
        self.assertEqual(es.slug("Café Example & Co."), "cafe-example-co")
        self.assertEqual(es.slug("!!!"), "spot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
