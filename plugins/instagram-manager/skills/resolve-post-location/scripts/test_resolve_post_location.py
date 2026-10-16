#!/usr/bin/env python3
"""Offline checks for resolve_post_location.py and pins_page.py, on an invented data repo. No model
and no network: a fake agent writes canned answers, and a fake OpenStreetMap answers the lookups.

    python3 skills/resolve-post-location/scripts/test_resolve_post_location.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import glob
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pins_page  # noqa: E402
import resolve_post_location as rpl  # noqa: E402
import geocode  # noqa: E402
import yaml  # noqa: E402

COLLECTIONS = """collections:
  Fixture Trips: {topics: [travel], cities: [Fixture State]}
pilots:
  fixture: {collections: [Fixture Trips], cities: [Fixture State]}
"""
# Fixture Town is a town at 40.0, -120.0; Fixture Park a park at 41.0, -121.0 whose box is about
# 33 km either side of its pin.
PLACES = {"places": {
    "Fixture State": {"kind": "state", "lat": 39.0, "lon": -119.0, "found": "Fixture State"},
    "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 40.0, "lon": -120.0,
                     "found": "Fixture Town, Fixture County, Fixture State"},
    "Fixture Park": {"kind": "park", "in": "Fixture State", "lat": 41.0, "lon": -121.0,
                     "found": "Fixture Park, Fixture County, Fixture State"},
}}
TAGS = {
    "TOWNA": {"topics": ["travel"], "cities": ["Fixture State", "Fixture Town"], "source": "model"},
    "PARKA": {"topics": ["travel"], "cities": ["Fixture Park", "Fixture State"], "source": "model"},
    "WIDEA": {"topics": ["travel"], "cities": ["Fixture State"], "source": "model"},
    "NONEA": {"topics": ["travel"], "cities": ["Fixture Town"], "source": "model"},
    "LISTA": {"topics": ["travel"], "cities": ["Fixture Town"], "source": "model"},
}


def save(code, caption):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "reel", "caption": caption,
            "hashtags": [], "owner": {"username": "example_creator", "name": "Example"},
            "collections": ["Fixture Trips"]}


SAVES = [
    save("TOWNA", "📍Example Cove Beach then lunch at @examplecafe. Also the Far Away Tower and Made Up Spot!"),
    save("PARKA", "Hiked the Example Falls Trail, then the Distant Ridge Loop"),
    save("WIDEA", "A road trip across the whole state"),          # only a state: never batched
    save("NONEA", "Golden hour in town, no words needed"),
    save("LISTA", "Three spots: Example Pier, Example Gardens, Example Museum"),
]
ANSWERS = {
    "TOWNA": [{"said": "Example Cove Beach", "near": "Fixture Town"},
              {"said": "@examplecafe", "near": "Fixture Town", "name": "Example Cafe"},
              {"said": "Far Away Tower", "near": "Fixture Town"},
              {"said": "Invented Lighthouse", "near": "Fixture Town"},      # not in the caption
              {"said": "Made Up Spot", "near": "Fixture Park"}],            # not one of its areas
    "PARKA": [{"said": "Example Falls Trail", "near": "Fixture Park"},
              {"said": "Distant Ridge Loop", "near": "Fixture Park"}],
    "NONEA": [],
    "LISTA": [{"said": "Example Pier", "near": "Fixture Town"},
              {"said": "Example Gardens", "near": "Fixture Town"},
              {"said": "Example Museum", "near": "Fixture Town"}],
}


def hit(name, lat, lon, typ, osm_id, box=None, wikidata=None):
    h = {"name": name, "display_name": f"{name}, Fixture County, Fixture State", "lat": str(lat), "lon": str(lon),
         "type": typ, "category": "tourism", "osm_type": "node", "osm_id": osm_id, "importance": 0.3,
         "boundingbox": [str(x) for x in (box or (lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001))]}
    if wikidata:
        h["extratags"] = {"wikidata": wikidata}
    return h


# The fake OpenStreetMap, by the text searched for. Not listed: not found.
OSM = {
    "Example Cove Beach": [hit("Example Cove Beach", 40.045, -120.0, "beach", 11, wikidata="Q100001")],  # 5 km
    "Example Cafe": [hit("Example Cafe", 40.01, -120.01, "cafe", 12)],
    "Far Away Tower": [hit("Far Away Tower", 40.36, -120.0, "tower", 13)],                              # 40 km
    "Fixture Park": [hit("Fixture Park", 41.0, -121.0, "national_park", 14, box=(40.7, 41.3, -121.4, -120.6))],
    "Example Falls Trail": [hit("Example Falls Trail", 41.28, -121.0, "path", 15)],    # 31 km, inside the box
    "Distant Ridge Loop": [hit("Distant Ridge Loop", 41.5, -121.0, "path", 16)],      # 56 km, outside it
    "Example Pier": [hit("Example Pier", 40.002, -120.002, "pier", 17)],
    "Example Gardens": [hit("Example Gardens", 40.003, -119.99, "garden", 18)],
    "Example Museum": [hit("Example Museum", 39.99, -120.004, "museum", 19)],
    "Far Away Tower, Fixture Town": [hit("Near Tower", 40.02, -120.0, "tower", 20)],
}


class Home(unittest.TestCase):
    """An invented data repo in a temp folder, a fake agent and a fake OpenStreetMap."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.environ.get("INSTAGRAM_HOME")
        os.environ["INSTAGRAM_HOME"] = self.tmp.name
        self.write("config/collections.yaml", COLLECTIONS)
        self.write("data/places.yaml", PLACES)
        self.write("data/tags.yaml", TAGS)
        self.write(".cache/saves.json", {"saves": SAVES})
        self.asked = []

    def tearDown(self):
        if self.env is None:
            os.environ.pop("INSTAGRAM_HOME", None)
        else:
            os.environ["INSTAGRAM_HOME"] = self.env
        self.tmp.cleanup()

    def path(self, rel):
        return os.path.join(self.tmp.name, rel)

    def write(self, rel, data):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w") as fh:
            if isinstance(data, str):
                fh.write(data)
            elif rel.endswith(".json"):
                json.dump(data, fh)
            else:
                yaml.safe_dump(data, fh)

    def text(self, rel):
        with open(self.path(rel)) as fh:
            return fh.read()

    def read(self, rel):
        return yaml.safe_load(self.text(rel)) or {}

    def osm(self, params):
        """The fake OpenStreetMap: answers by the text, and only inside the box it was given."""
        self.asked.append(params)
        w, n, e, s = (float(x) for x in params["viewbox"].split(","))
        return [h for h in OSM.get(params["q"], []) if s <= float(h["lat"]) <= n and w <= float(h["lon"]) <= e]

    def run_script(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            rpl.main(list(argv), fetcher=self.osm)
        return out.getvalue()

    def agent(self, paths, answers=ANSWERS):
        """What the post-locator agent does: read each batch, write its answers file."""
        for path in paths:
            with open(path) as fh:
                batch = json.load(fh)
            with open(batch["answers"], "w") as fh:
                json.dump({"answers": {r["code"]: answers[r["code"]] for r in batch["saves"]
                                       if r["code"] in answers}}, fh)

    def locate(self, *scope):
        paths = self.run_script("--prepare", *(scope or ("--pilot", "fixture"))).split()
        self.agent(paths)
        return self.run_script("--merge")

    def spot(self, rel, code, said):
        return next(e for e in self.read(rel)[code] if e["said"] == said)


class Prepare(Home):
    def test_only_saves_with_an_exact_area_go_in_and_carry_what_the_agent_needs(self):
        paths = self.run_script("--prepare", "--pilot", "fixture").split()
        self.assertEqual(len(paths), 1)
        with open(paths[0]) as fh:
            batch = json.load(fh)
        self.assertTrue(batch["answers"].endswith("batch-001.answers.json"))
        codes = [r["code"] for r in batch["saves"]]
        self.assertEqual(sorted(codes), ["LISTA", "NONEA", "PARKA", "TOWNA"])   # WIDEA has only a state
        town = next(r for r in batch["saves"] if r["code"] == "TOWNA")
        self.assertEqual(town["areas"], [{"name": "Fixture Town", "kind": "city", "lat": 40.0, "lon": -120.0}])
        self.assertEqual(town["creator"], "@example_creator (Example)")
        self.assertIn("Example Cove Beach", town["caption"])

    def test_batch_size_limits(self):
        paths = self.run_script("--prepare", "--all", "--batch-saves", "3").split()
        self.assertEqual(len(paths), 2)
        self.assertEqual(rpl.BATCH_SAVES, 40)
        self.assertEqual(rpl.BATCH_CHARS, 60000)


class Merge(Home):
    def test_the_quote_check_sends_a_made_up_spot_to_review_without_a_lookup(self):
        self.locate()
        e = self.spot("data/pins-review.yaml", "TOWNA", "Invented Lighthouse")
        self.assertEqual(e["why"], "quote not in caption")
        self.assertNotIn("Invented Lighthouse", [p["q"] for p in self.asked])

    def test_a_spot_near_a_town_is_pinned_with_its_ids_and_distance(self):
        self.locate()
        p = self.spot("data/pins.yaml", "TOWNA", "Example Cove Beach")
        self.assertEqual((p["name"], p["near"], p["kind"]), ("Example Cove Beach", "Fixture Town", "beach"))
        self.assertEqual((p["osm"], p["wikidata"]), ("node/11", "Q100001"))
        self.assertAlmostEqual(p["km"], 5.0, delta=0.2)
        self.assertTrue(p["map"].startswith("https://www.google.com/maps/search/?api=1&query="))
        self.assertEqual(list(p)[:3], ["name", "said", "near"])                 # the shape in the design

    def test_the_distance_check(self):
        self.locate()
        far = self.spot("data/pins-review.yaml", "TOWNA", "Far Away Tower")
        self.assertEqual(far["why"], "40 km from Fixture Town")                  # past a town's 25 km
        self.assertEqual(far["osm"], "node/13")
        trail = self.spot("data/pins.yaml", "PARKA", "Example Falls Trail")      # 31 km, but inside the park
        self.assertGreater(trail["km"], 25)
        box = next(p["viewbox"] for p in self.asked if p["q"] == "Far Away Tower")
        w, n, e, s = (float(x) for x in box.split(","))
        self.assertAlmostEqual((n - s) * 111 / 2, 50, delta=0.5)                # a town's 25 km, plus 25 km
        ridge = self.spot("data/pins-review.yaml", "PARKA", "Distant Ridge Loop")
        self.assertEqual(ridge["why"], "56 km from Fixture Park")

    def test_a_spot_outside_the_saves_areas_goes_to_review(self):
        self.locate()
        e = self.spot("data/pins-review.yaml", "TOWNA", "Made Up Spot")
        self.assertEqual(e["why"], "near Fixture Park, which is not one of the save's areas")

    def test_a_handle_is_searched_by_its_plain_name(self):
        self.locate()
        p = self.spot("data/pins.yaml", "TOWNA", "@examplecafe")
        self.assertEqual((p["name"], p["asked"]), ("Example Cafe", "Example Cafe"))

    def test_a_list_post_gets_every_spot_and_a_post_with_none_goes_on_the_video_list(self):
        self.locate()
        self.assertEqual([p["said"] for p in self.read("data/pins.yaml")["LISTA"]],
                         ["Example Pier", "Example Gardens", "Example Museum"])
        self.assertEqual(self.read("data/no-spot.yaml"), {"NONEA": {"areas": ["Fixture Town"]}})

    def test_a_lookup_added_to_a_review_entry_is_searched_on_the_next_merge(self):
        self.locate()
        review = self.read("data/pins-review.yaml")
        for e in review["TOWNA"]:
            if e["said"] == "Far Away Tower":
                e["lookup"] = "Far Away Tower, Fixture Town"
        self.write("data/pins-review.yaml", review)
        out = self.run_script("--merge")
        self.assertIn("1 review entries found", out)
        p = self.spot("data/pins.yaml", "TOWNA", "Far Away Tower")
        self.assertEqual((p["name"], p["asked"]), ("Near Tower", "Far Away Tower, Fixture Town"))
        self.assertNotIn("Far Away Tower", [e["said"] for e in self.read("data/pins-review.yaml")["TOWNA"]])

    def test_rerunning_is_safe(self):
        self.locate()
        files = ("data/pins.yaml", "data/pins-review.yaml", "data/no-spot.yaml")
        before = [self.text(f) for f in files]
        asked = len(self.asked)
        self.run_script("--merge")                                              # nothing new
        self.assertEqual([self.text(f) for f in files], before)
        self.assertEqual(len(self.asked), asked)                                # all from the cache
        self.assertEqual(len(self.text(".cache/batches/locate/merged.jsonl").splitlines()), 1)
        self.assertEqual(self.run_script("--prepare", "--pilot", "fixture").split(), [])  # all answered
        self.assertEqual(len(self.run_script("--prepare", "--pilot", "fixture", "--redo").split()), 1)

    def test_a_missing_answer_is_batched_again_and_waiting_batches_are_left_alone(self):
        paths = self.run_script("--prepare", "--pilot", "fixture").split()
        self.assertIn("1 batches still waiting", self.run_script("--merge"))
        self.agent(paths, {k: v for k, v in ANSWERS.items() if k != "LISTA"})
        self.assertIn("1 saves with no usable answer", self.run_script("--merge"))
        again = self.run_script("--prepare", "--pilot", "fixture").split()
        with open(again[0]) as fh:
            self.assertEqual([r["code"] for r in json.load(fh)["saves"]], ["LISTA"])

    def test_prepare_will_not_delete_answers_that_are_not_merged(self):
        self.agent(self.run_script("--prepare", "--pilot", "fixture").split())
        with self.assertRaises(SystemExit):
            self.run_script("--prepare", "--pilot", "fixture")


class BoundedLookup(Home):
    def test_the_parameters(self):
        p = geocode.near_params(" Example Cove Beach ", (39.5, -120.5, 40.5, -119.5))
        self.assertEqual(p["q"], "Example Cove Beach")
        self.assertEqual(p["viewbox"], "-120.5,40.5,-119.5,39.5")                # west, north, east, south
        self.assertEqual((p["bounded"], p["extratags"], p["format"]), (1, 1, "jsonv2"))

    def test_the_request_names_the_app_waits_and_is_cached(self):
        reply = mock.MagicMock()
        reply.__enter__.return_value = io.BytesIO(json.dumps(OSM["Example Cove Beach"]).encode())
        with mock.patch.object(geocode.urllib.request, "urlopen", return_value=reply) as urlopen, \
                mock.patch.object(geocode.time, "sleep") as sleep, contextlib.redirect_stderr(io.StringIO()):
            box = (39.5, -120.5, 40.5, -119.5)
            first = geocode.lookup_near("Example Cove Beach", box)
            second = geocode.lookup_near("Example Cove Beach", box)
        self.assertEqual(urlopen.call_count, 1)                                 # the second is from the cache
        req = urlopen.call_args[0][0]
        self.assertEqual(req.get_header("User-agent"), geocode.UA)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        self.assertEqual((query["bounded"], query["viewbox"]), (["1"], ["-120.5,40.5,-119.5,39.5"]))
        sleep.assert_called_once_with(geocode.WAIT)
        self.assertEqual(first, second)
        self.assertEqual((first[0]["osm"], first[0]["wikidata"], first[0]["type"]), ("node/11", "Q100001", "beach"))

    def test_the_plain_lookup_is_unchanged(self):
        hits = [{"name": "Example Town", "display_name": "Example Town, Example State", "lat": "1", "lon": "2",
                 "addresstype": "town", "address": {"state": "Example State"}}]
        with contextlib.redirect_stderr(io.StringIO()):
            got = geocode.lookup("Example Town", lambda q: hits)
        self.assertEqual((got["kind"], got["lat"], got["state"]), ("city", 1.0, "Example State"))


class Page(Home):
    def test_the_page_shows_pins_and_review_on_a_leaflet_map(self):
        self.locate()
        out = self.path(".cache/hub/pins.html")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            pins_page.main(["--out", out])
        page = self.text(".cache/hub/pins.html")
        self.assertIn("cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", page)
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", page)
        self.assertIn("openstreetmap.org/copyright", page)
        self.assertIn("@example_creator", page)
        self.assertIn("<q>Example Cove Beach</q>", page)
        self.assertIn("5 km from Fixture Town", page)
        self.assertIn("https://www.instagram.com/p/TOWNA/", page)
        self.assertIn("40 km from Fixture Town", page)                         # a review reason
        self.assertIn("quote not in caption", page)


if __name__ == "__main__":
    unittest.main()
