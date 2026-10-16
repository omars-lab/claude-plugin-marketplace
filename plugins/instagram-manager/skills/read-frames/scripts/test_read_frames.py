#!/usr/bin/env python3
"""Offline checks for read_frames.py and resolve_post_location.py --merge --frames, on an invented data
repo. No model and no network: a fake agent writes canned answers, a fake OpenStreetMap answers the
lookups, and the video is three coloured scenes ffmpeg makes on the spot.

    python3 skills/read-frames/scripts/test_read_frames.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import read_frames as rf  # noqa: E402
import resolve_post_location as rpl  # noqa: E402
import yaml  # noqa: E402

HAVE_TOOLS = all(shutil.which(t) for t in ("ffmpeg", "ffprobe", "tesseract"))

COLLECTIONS = """collections:
  Fixture Trips: {topics: [travel], cities: [Fixture State]}
pilots:
  fixture: {collections: [Fixture Trips], cities: [Fixture State]}
"""
PLACES = {"places": {
    "Fixture State": {"kind": "state", "lat": 39.0, "lon": -119.0},
    "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 40.0, "lon": -120.0},
    "Other Town": {"kind": "city", "in": "Fixture State", "lat": 38.0, "lon": -118.0},
    "Elsewhere Town": {"kind": "city", "in": "Other State", "lat": 30.0, "lon": -100.0},
}}
TAGS = {
    "NOSPOT": {"cities": ["Fixture Town"], "purposes": ["see"]},
    "STATEO": {"cities": ["Fixture State"], "purposes": ["eat"]},
    "EATTWN": {"cities": ["Fixture Town"], "purposes": ["eat"]},
    "EATVEN": {"cities": ["Fixture Town"], "purposes": ["eat"]},   # its venue is a dashed pin already
    "PHOTOA": {"cities": ["Fixture State"], "purposes": ["eat"]},  # a photo post: no video to read
    "SEEALL": {"cities": ["Fixture Town"], "purposes": ["see"]},   # has pins: not stuck
}
MEDIA = {c: {"kind": "reel", "thumb": f"{c}/thumb.jpg"} for c in TAGS}
MEDIA["PHOTOA"]["kind"] = "photo"


def save(code, caption):
    return {"code": code, "url": f"https://www.instagram.com/reel/{code}/", "kind": "reel", "caption": caption,
            "hashtags": [], "owner": {"username": "example_creator", "name": "Example"},
            "collections": ["Fixture Trips"]}


SAVES = [save("NOSPOT", "Golden hour, no words needed"), save("STATEO", "Best tacos in the state!"),
         save("EATTWN", "Lunch was unreal"), save("EATVEN", "Lunch at Example Diner"),
         save("PHOTOA", "A plate"), save("SEEALL", "Example Cove Beach at dawn")]
PINS = {"SEEALL": [{"name": "Example Cove Beach", "said": "Example Cove Beach", "near": "Fixture Town",
                    "kind": "beach", "lat": 40.01, "lon": -120.0}],
        "EATTWN": [{"name": "Example Pier", "said": "Example Pier", "near": "Fixture Town", "kind": "pier",
                    "lat": 40.002, "lon": -120.002}]}
REVIEW = {"EATVEN": [{"said": "Example Diner", "near": "Fixture Town", "why": "not found near Fixture Town"}]}
NO_SPOT = {"NOSPOT": {"areas": ["Fixture Town"]}}
# Not "eat" posts with pins, so EATTWN is stuck only because it is for eating and opens no venue.
PINS_FOR_STUCK = {"SEEALL": PINS["SEEALL"]}


def hit(name, lat, lon, typ, osm_id):
    return {"name": name, "display_name": f"{name}, Fixture County, Fixture State", "lat": str(lat),
            "lon": str(lon), "type": typ, "category": "amenity", "osm_type": "node", "osm_id": osm_id,
            "importance": 0.3, "boundingbox": [str(lat - 0.001), str(lat + 0.001), str(lon - 0.001), str(lon + 0.001)]}


OSM = {"Example Taco Shop": [hit("Example Taco Shop", 38.01, -118.0, "restaurant", 31)],
       "Example Grill": [hit("Example Grill", 40.003, -120.001, "restaurant", 32)],
       "Example Point Lookout": [hit("Example Point Lookout", 40.02, -120.01, "viewpoint", 33)]}


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("INSTAGRAM_HOME", "INSTAGRAM_MEDIA_DIR")}
        os.environ["INSTAGRAM_HOME"] = os.path.join(self.tmp.name, "home")
        os.environ["INSTAGRAM_MEDIA_DIR"] = os.path.join(self.tmp.name, "media")
        self.write("config/collections.yaml", COLLECTIONS)
        self.write("data/places.yaml", PLACES)
        self.write("data/tags.yaml", TAGS)
        self.write("data/media.yaml", MEDIA)
        self.write("data/pins.yaml", PINS_FOR_STUCK)
        self.write("data/pins-review.yaml", REVIEW)
        self.write("data/no-spot.yaml", NO_SPOT)
        self.write(".cache/saves.json", {"saves": SAVES})

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

    def frames(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            rf.main(list(argv))
        return out.getvalue()

    def merge(self):
        def osm(params):
            w, n, e, s = (float(x) for x in params["viewbox"].split(","))
            return [h for h in OSM.get(params["q"], []) if s <= float(h["lat"]) <= n and w <= float(h["lon"]) <= e]
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            rpl.main(["--merge", "--frames"], fetcher=osm)
        return out.getvalue()

    def make_video(self, code):
        """Three scenes of 2 s each: black, white, navy (far apart in brightness, so ffmpeg sees each cut)."""
        os.makedirs(self.media(code), exist_ok=True)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for colour in ("black", "white", "navy"):
            cmd += ["-f", "lavfi", "-i", f"color=c={colour}:s=360x640:d=2:r=10"]
        cmd += ["-filter_complex", "concat=n=3:v=1:a=0", "-pix_fmt", "yuv420p", self.media(code, "video.mp4")]
        subprocess.run(cmd, check=True, timeout=60)
        MEDIA[code]["video"] = f"{code}/video.mp4"

    def fake_frames(self, code, texts):
        """text.json as read_frames.py writes it, with invented words on screen."""
        info = {"video": f"{code}/video.mp4", "seconds": 6.0,
                "frames": [{"n": i + 1, "t": float(i), "file": f"frame-{i + 1:02d}.jpg", "text": t}
                           for i, t in enumerate(texts)],
                "sheets": [{"file": "sheet-1.jpg", "frames": list(range(1, len(texts) + 1))}]}
        self.write("text.json", info, base=self.media(code, "frames"))


class Stuck(Home):
    def test_lists_reels_the_caption_cannot_place(self):
        out = self.frames("--stuck", "--pilot", "fixture")
        with open(self.path(".cache/frames/stuck.txt")) as fh:
            lines = [ln.strip() for ln in fh if not ln.startswith("#")]
        self.assertEqual(lines, ["NOSPOT  # the caption names no spot", "STATEO  # tagged with a state only",
                                 "EATTWN  # for eating or staying, but opens only its town"])
        self.assertIn("3 reels to read", out)

    def test_pick_times(self):
        self.assertEqual(rf.pick_times([0.0, 2.0, 4.0], 6.0), [0.0, 0.86, 2.0, 2.57, 3.43, 4.0])  # not 1.71: by 2.0
        many = rf.pick_times([float(i) for i in range(30)], 30.0)
        self.assertEqual(len(many), rf.MAX_FRAMES)
        self.assertEqual((many[0], many[-1]), (0.0, 29.0))
        self.assertEqual(rf.pick_times([], None), [0.0])


@unittest.skipUnless(HAVE_TOOLS, "needs ffmpeg and tesseract")
class Prepare(Home):
    def setUp(self):
        super().setUp()
        for code in ("NOSPOT", "STATEO"):
            self.make_video(code)
        self.write("data/media.yaml", MEDIA)
        self.frames("--stuck", "--pilot", "fixture")

    def tearDown(self):
        for code in ("NOSPOT", "STATEO"):
            MEDIA[code].pop("video", None)
        super().tearDown()

    def test_frames_sheets_and_batches(self):
        with mock.patch.object(rf, "ocr", lambda path: "EXAMPLE TACO SHOP" if path.endswith("01.jpg") else ""):
            out = self.frames("--prepare")
        self.assertIn("2 reels in 1 batches", out)
        self.assertIn("1 listed reels have no video yet", out)       # EATTWN
        folder = self.media("STATEO", "frames")
        self.assertEqual(sorted(os.listdir(folder)),
                         [f"frame-{i:02d}.jpg" for i in range(1, 7)] + ["sheet-1.jpg", "text.json"])
        with open(os.path.join(folder, "text.json")) as fh:
            info = json.load(fh)
        self.assertEqual([f["t"] for f in info["frames"]], [0.0, 0.86, 2.0, 2.57, 3.43, 4.0])  # scenes at 2 and 4 s
        self.assertEqual(info["sheets"], [{"file": "sheet-1.jpg", "frames": [1, 2, 3, 4, 5, 6]}])
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                "stream=width", "-of", "csv=p=0", os.path.join(folder, "frame-01.jpg")],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(probe.stdout.strip(), str(rf.FRAME_WIDTH))
        with open(self.path(".cache/batches/frames/batch-001.json")) as fh:
            batch = json.load(fh)
        recs = {r["code"]: r for r in batch["saves"]}
        self.assertEqual(sorted(recs), ["NOSPOT", "STATEO"])
        state = recs["STATEO"]
        self.assertTrue(state["state_only"])
        self.assertEqual([a["name"] for a in state["areas"]], ["Fixture Town", "Other Town"])   # not Elsewhere
        self.assertEqual(state["frame_text"], {"1": "EXAMPLE TACO SHOP"})
        self.assertEqual(state["sheets"][0]["frames"], [1, 2, 3, 4, 5, 6])
        self.assertTrue(os.path.exists(state["sheets"][0]["path"]))
        self.assertFalse(recs["NOSPOT"]["state_only"])

    def test_ocr_of_a_missing_file_is_empty(self):
        self.assertEqual(rf.ocr(self.media("NOSPOT", "video.mp4") + ".missing"), "")

    def test_waits_for_unmerged_answers(self):
        self.write(".cache/batches/frames/batch-001.answers.json", {"answers": {}})
        with self.assertRaises(SystemExit):
            self.frames("--prepare")


class MergeFrames(Home):
    def setUp(self):
        super().setUp()
        self.write("data/pins.yaml", PINS)
        self.fake_frames("STATEO", ["EXAMPLE TACO\nSHOP", ""])
        self.fake_frames("EATTWN", ["Example  Grill", "", "lunch"])
        self.fake_frames("NOSPOT", ["", ""])

    def batch(self, number, answers):
        out = os.path.join(rf.batch_dir())
        os.makedirs(out, exist_ok=True)
        name = f"batch-{number:03d}"
        recs = [{"code": c, "areas": [{"name": a, "kind": "city", "lat": 0, "lon": 0} for a in areas]}
                for c, areas in (("STATEO", ["Fixture Town", "Other Town"]), ("EATTWN", ["Fixture Town"]),
                                 ("NOSPOT", ["Fixture Town"])) if c in answers]
        self.write(f"{name}.json", {"batch": name, "answers": os.path.join(out, name + ".answers.json"),
                                    "saves": recs}, base=out)
        self.write(f"{name}.answers.json", {"answers": answers}, base=out)

    def test_video_spots_add_to_the_caption_pins(self):
        self.batch(1, {
            "STATEO": [{"said": "Example Taco Shop", "near": "Other Town", "frame": 1}],
            "EATTWN": [{"said": "Example Grill", "near": "Fixture Town", "frame": 1},
                       {"said": "Example Pier", "near": "Fixture Town", "frame": 3},        # the caption's own
                       {"said": "Fancy Script Bar", "near": "Fixture Town", "frame": 2}],   # tesseract missed it
            "NOSPOT": [{"said": "Example Point Lookout", "near": "Fixture Town", "frame": 2}],  # nowhere in text
        })
        out = self.merge()
        self.assertIn("2 spots pinned, 2 for review", out)
        pins, review = self.read("data/pins.yaml"), self.read("data/pins-review.yaml")
        taco = pins["STATEO"][0]
        self.assertEqual((taco["name"], taco["near"], taco["from"]), ("Example Taco Shop", "Other Town", "video"))
        self.assertEqual([p["said"] for p in pins["EATTWN"]], ["Example Pier", "Example Grill"])
        self.assertNotIn("from", pins["EATTWN"][0])
        self.assertEqual(review["EATTWN"], [{"said": "Fancy Script Bar", "near": "Fixture Town",
                                             "why": "not in the caption or the video's text", "from": "video"}])
        self.assertEqual(review["NOSPOT"][0]["why"], "not in the caption or the video's text")
        self.assertEqual(review["EATVEN"], REVIEW["EATVEN"])                   # untouched
        self.assertNotIn("NOSPOT", self.read("data/no-spot.yaml"))              # it names a spot now, in review
        self.assertEqual(pins["SEEALL"], PINS["SEEALL"])

    def test_a_person_fix_on_a_video_spot_pins_it(self):
        self.batch(1, {"NOSPOT": [{"said": "Example Point Lookout", "near": "Fixture Town"}]})
        self.merge()
        review = self.read("data/pins-review.yaml")
        review["NOSPOT"][0]["lookup"] = "Example Point Lookout"
        self.write("data/pins-review.yaml", review)
        self.merge()
        pin = self.read("data/pins.yaml")["NOSPOT"][0]
        self.assertEqual((pin["name"], pin["from"]), ("Example Point Lookout", "video"))
        self.assertNotIn("NOSPOT", self.read("data/pins-review.yaml"))

    def test_reading_the_caption_again_keeps_the_videos_spots(self):
        self.batch(1, {"EATTWN": [{"said": "Example Grill", "near": "Fixture Town"},
                                  {"said": "Fancy Script Bar", "near": "Fixture Town"}]})
        self.merge()
        out = rpl.batch_dir()
        os.makedirs(out, exist_ok=True)
        self.write("batch-001.json", {"batch": "batch-001", "answers": os.path.join(out, "batch-001.answers.json"),
                                      "saves": [{"code": "EATTWN", "areas": [{"name": "Fixture Town"}]}]}, base=out)
        self.write("batch-001.answers.json", {"answers": {"EATTWN": []}}, base=out)   # the pier is gone now
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            rpl.main(["--merge"], fetcher=lambda params: [])
        self.assertEqual([p["said"] for p in self.read("data/pins.yaml")["EATTWN"]], ["Example Grill"])
        self.assertEqual([e["said"] for e in self.read("data/pins-review.yaml")["EATTWN"]], ["Fancy Script Bar"])
        self.assertNotIn("EATTWN", self.read("data/no-spot.yaml"))

    def test_a_new_round_never_reuses_a_merged_name(self):
        self.batch(1, {"NOSPOT": []})
        self.merge()
        self.assertEqual(rf.read_done(), {"NOSPOT"})
        self.assertEqual(rf.last_number(), 1)


class CaptionMergeUnchanged(unittest.TestCase):
    def test_a_caption_quote_miss_says_so(self):
        where, entry = rpl.resolve({"said": "Nowhere Cafe", "near": "Fixture Town"}, "A caption", ["Fixture Town"],
                                   PLACES["places"], {})
        self.assertEqual((where, entry["why"]), ("review", "quote not in caption"))

    def test_on_screen(self):
        self.assertTrue(rpl.on_screen("Example Taco Shop", "EXAMPLE TACO\nSHOP"))
        self.assertTrue(rpl.on_screen("@exampletacos", "follow EXAMPLETACOS"))
        self.assertFalse(rpl.on_screen("Example Taco Shop", "EXAMPLE TACO"))
        self.assertFalse(rpl.on_screen("Bar", "a bar"))                         # too short to trust
        self.assertFalse(rpl.on_screen("Example", None))


if __name__ == "__main__":
    unittest.main()
