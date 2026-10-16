#!/usr/bin/env python3
"""Offline checks for send_topics.py, on an invented data repo in a temp folder. No network.

    python3 skills/send-topics/scripts/test_send_topics.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import send_topics  # noqa: E402
import yaml  # noqa: E402

TOPICS = {"topics": {"travel": {"feeds": ["example-trips"]}, "recipes": {"feeds": ["example-kitchen"]},
                     "crafts": {"feeds": []}}}
COLLECTIONS = {"collections": {"Fixture Trips": {"topics": ["travel"], "cities": ["Fixture State"]},
                               "Fixture Kitchen": {"topics": ["recipes"]}},
               "pilots": {"fixture": {"collections": ["Fixture Trips"], "cities": ["Fixture State"]},
                          "kitchen": {"collections": ["Fixture Kitchen"], "cities": []}}}
PLACES = {"places": {
    "Fixture State": {"kind": "state", "lat": 10.0, "lon": 20.0},
    "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 10.5, "lon": 20.5},
    "Fixture Coast": {"kind": "region", "in": "Fixture State", "lat": 10.8, "lon": 20.8},
    "Other State": {"kind": "state", "lat": 30.0, "lon": 40.0},
    "Other Town": {"kind": "city", "in": "Other State", "lat": 30.5, "lon": 40.5},
}}


def save(code, collections=(), user="example_creator"):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "reel",
            "caption": "A long caption that must never be copied out", "hashtags": [],
            "owner": {"username": user, "name": "Example Person"}, "saved_at": "2026-01-02T03:04",
            "collections": list(collections)}


SAVES = [save("TRIP1", ["Fixture Trips"]), save("ROAD1"), save("CAFE1"), save("BOTH1"), save("NONE1", ["Fixture Trips"]),
         save("SOUP1", ["Fixture Kitchen"]), save("SOUP2", ["Fixture Kitchen", "Fixture Trips"])]
TAGS = {
    "TRIP1": {"topics": ["travel"], "cities": ["Fixture State", "Fixture Town"], "purposes": ["eat"]},
    "ROAD1": {"topics": ["travel"], "cities": ["Fixture State", "Fixture Coast", "Other State", "Other Town"]},   # crosses into another state
    "CAFE1": {"topics": ["recipes"], "cities": ["Fixture Town"]},                  # names a place, not travel
    "BOTH1": {"topics": ["travel", "recipes"], "cities": ["Fixture State", "Fixture Town"]},
    "NONE1": {"topics": ["travel"], "cities": []},
    "SOUP1": {"topics": ["recipes"], "cities": []},
    "SOUP2": {"topics": ["recipes"], "cities": []},
}
PINS = {
    "TRIP1": [{"name": "Example Cove Beach", "said": "the cove beach", "near": "Fixture Town", "kind": "beach",
               "lat": 10.51, "lon": 20.51, "osm": "way/7", "wikidata": "Q7", "map": "https://maps.example/cove"}],
    "ROAD1": [{"name": "Example Point", "said": "Example Point", "near": "Fixture Coast", "kind": "viewpoint",
               "lat": 10.81, "lon": 20.81, "osm": "node/8"},
              {"name": "Example Bluff", "said": "the bluff", "near": "Fixture Coast", "kind": "cliff",
               "lat": 10.82, "lon": 20.82, "osm": "node/9"},
              {"name": "Example Pier", "said": "Example Pier", "near": "Other Town", "kind": "pier",
               "lat": 30.51, "lon": 40.51, "osm": "node/10"}],
    "CAFE1": [{"name": "Example Roasters", "said": "Example Roasters", "near": "Fixture Town", "lat": 10.5, "lon": 20.5}],
}
REVIEW = {"TRIP1": [{"name": "Somewhere Else", "said": "Example Tiny Cafe", "asked": "Example Tiny Cafe",
                     "near": "Fixture Town", "lat": 1.0, "lon": 1.0, "why": "not found near Fixture Town"},
                    {"name": "Dropped", "said": "x", "near": "Fixture Town", "why": "not found near Fixture Town",
                     "drop": True}]}
MEDIA = {"TRIP1": {"thumb": "TRIP1/thumb.jpg", "kind": "reel"}, "ROAD1": {"error": "login_wall"}}
STILLS = {
    "TRIP1": [{"name": "Example Cove Beach", "said": "the cove beach", "frame": 2, "t": 3.1, "how": "on_screen",
               "still": "TRIP1/spots/still-example-cove-beach.jpg", "clip": "TRIP1/spots/clip-example-cove-beach.webp"}],
    "ROAD1": [{"name": n, "said": n, "frame": 4, "t": 8.0, "how": "area", "area": "Fixture Coast",
               "still": "ROAD1/spots/still-area-fixture-coast.jpg", "clip": "ROAD1/spots/clip-area-fixture-coast.webp"}
              for n in ("Example Point", "Example Bluff")]
             + [{"name": "Example Pier", "said": "Example Pier", "how": "not_on_screen"}],
}
ITEMS = {  # from split-saves
    "SOUP1": {"topics": ["recipes"], "items": [
        {"topic": "recipes", "kind": "dish", "name": "Example lentil soup", "quote": "my lentil soup"},
        {"topic": "recipes", "kind": "dish", "name": "Example flatbread", "quote": "quick flatbread"},
        {"topic": "crafts", "kind": "note", "name": "Not this save's topic", "quote": "words"}]},
    "BOTH1": {"topics": ["recipes"], "items": [
        {"topic": "recipes", "kind": "dish", "name": "Example picnic salad", "quote": "picnic salad"}]},
    "SOUP2": {"topics": ["recipes"], "items": []},
}


class Send(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for rel, data in (("config/topics.yaml", TOPICS), ("config/collections.yaml", COLLECTIONS),
                          ("data/places.yaml", PLACES), ("data/tags.yaml", TAGS), ("data/pins.yaml", PINS),
                          ("data/pins-review.yaml", REVIEW), ("data/media.yaml", MEDIA),
                          ("data/stills.yaml", STILLS), ("data/items/recipes.yaml", ITEMS)):
            self.write(rel, data)
        self.write(".cache/saves.json", {"saves": SAVES})
        self.env = os.environ.get("INSTAGRAM_HOME")
        os.environ["INSTAGRAM_HOME"] = self.root

    def tearDown(self):
        if self.env is None:
            os.environ.pop("INSTAGRAM_HOME", None)
        else:
            os.environ["INSTAGRAM_HOME"] = self.env
        self.tmp.cleanup()

    def write(self, rel, data):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh) if rel.endswith(".json") else yaml.safe_dump(data, fh)

    def send(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
            send_topics.main(list(argv))
        return err.getvalue()

    def read(self, rel):
        with open(os.path.join(self.root, "out", rel)) as fh:
            return fh.read()

    def doc(self, rel):
        return yaml.safe_load(self.read(rel))

    def saves(self, rel):
        return {s["code"]: s for s in self.doc(rel)["saves"]}

    def test_travel_file_per_state(self):
        self.send("--all")
        here, there = self.saves("travel/fixture-state.yaml"), self.saves("travel/other-state.yaml")
        self.assertEqual(sorted(here), ["BOTH1", "ROAD1", "TRIP1"])
        self.assertEqual(sorted(there), ["ROAD1"])
        self.assertEqual([i["name"] for i in here["ROAD1"]["items"]], ["Example Point", "Example Bluff"])
        self.assertEqual([i["name"] for i in there["ROAD1"]["items"]], ["Example Pier"])
        doc = self.doc("travel/fixture-state.yaml")
        self.assertEqual((doc["topic"], doc["area"], doc["feeds"], doc["count"]),
                         ("travel", "Fixture State", ["example-trips"], 3))

    def test_save_fields_and_no_caption(self):
        self.send("--all")
        trip = self.saves("travel/fixture-state.yaml")["TRIP1"]
        self.assertEqual((trip["creator"], trip["saved_at"], trip["places"], trip["purposes"], trip["thumb"]),
                         ("example_creator", "2026-01-02T03:04", ["Fixture Town"], ["eat"], "TRIP1/thumb.jpg"))
        self.assertNotIn("caption must never", self.read("travel/fixture-state.yaml"))
        self.assertNotIn("collections", trip)

    def test_spot_with_still_and_exact_pin(self):
        self.send("--all")
        cove = self.saves("travel/fixture-state.yaml")["TRIP1"]["items"][0]
        self.assertEqual((cove["name"], cove["said"], cove["lat"], cove["osm"], cove["wikidata"], cove["exact"]),
                         ("Example Cove Beach", "the cove beach", 10.51, "way/7", "Q7", True))
        self.assertEqual((cove["still"], cove["t"], cove["still_from"]),
                         ("TRIP1/spots/still-example-cove-beach.jpg", 3.1, "name"))

    def test_unplaced_spot_kept_without_coordinates(self):
        self.send("--all")
        items = self.saves("travel/fixture-state.yaml")["TRIP1"]["items"]
        tiny = [i for i in items if i["name"] == "Example Tiny Cafe"]
        self.assertEqual(len(tiny), 1)
        self.assertFalse(tiny[0]["exact"])
        self.assertNotIn("lat", tiny[0])
        self.assertIn("Example+Tiny+Cafe", tiny[0]["map"])
        self.assertNotIn("Dropped", [i["name"] for i in items])

    def test_area_still_points_at_the_shared_file(self):
        self.send("--all")
        point, bluff = self.saves("travel/fixture-state.yaml")["ROAD1"]["items"]
        self.assertEqual(point["still"], bluff["still"])
        self.assertEqual((point["still_from"], point["area"]), ("area", "Fixture Coast"))
        pier = self.saves("travel/other-state.yaml")["ROAD1"]["items"][0]
        self.assertNotIn("still", pier)   # not on screen: no still

    def test_also_in(self):
        self.send("--all")
        self.assertEqual(self.saves("travel/fixture-state.yaml")["BOTH1"]["also_in"], ["recipes"])
        self.assertEqual(self.saves("travel/fixture-state.yaml")["ROAD1"]["also_in"], ["travel/other-state"])
        self.assertEqual(self.saves("recipes.yaml")["BOTH1"]["also_in"], ["travel/fixture-state"])

    def test_place_but_not_travel_is_left_out_and_logged(self):
        err = self.send("--all")
        self.assertNotIn("CAFE1", self.saves("travel/fixture-state.yaml"))
        self.assertIn("ev=send_place_not_travel code=CAFE1", err)
        cafe = self.saves("recipes.yaml")["CAFE1"]
        self.assertEqual(cafe["items"], [])
        self.assertIn("ev=send_travel_no_place code=NONE1", err)

    def test_non_travel_items_from_split_saves(self):
        self.send("--all")
        recipes = self.saves("recipes.yaml")
        self.assertEqual(recipes["SOUP1"]["items"],
                         [{"topic": "recipes", "kind": "dish", "name": "Example lentil soup", "quote": "my lentil soup"},
                          {"topic": "recipes", "kind": "dish", "name": "Example flatbread", "quote": "quick flatbread"}])
        self.assertEqual([i["name"] for i in recipes["BOTH1"]["items"]], ["Example picnic salad"])
        self.assertEqual(recipes["SOUP2"]["items"], [])
        self.assertNotIn("Example picnic salad",
                         [i["name"] for i in self.saves("travel/fixture-state.yaml")["BOTH1"]["items"]])
        self.assertEqual(self.doc("crafts.yaml")["saves"], [])  # an item never brings a save into another topic

    def test_every_topic_gets_a_file(self):
        self.send("--all")
        crafts = self.doc("crafts.yaml")
        self.assertEqual((crafts["count"], crafts["saves"], crafts["feeds"]), (0, [], []))

    def test_pilot_writes_only_its_areas(self):
        self.send("--pilot", "fixture")
        self.assertTrue(os.path.exists(os.path.join(self.root, "out", "travel", "fixture-state.yaml")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "out", "travel", "other-state.yaml")))
        self.assertIn("pilot fixture", self.doc("travel/fixture-state.yaml")["scope"])
        self.assertEqual(sorted(self.saves("travel/fixture-state.yaml")), ["BOTH1", "ROAD1", "TRIP1"])

    def test_pilots_add_up_in_a_shared_topic_file(self):
        self.send("--pilot", "fixture")
        self.assertEqual(sorted(self.saves("recipes.yaml")), ["BOTH1", "SOUP2"])
        self.send("--pilot", "kitchen")
        self.assertEqual(sorted(self.saves("recipes.yaml")), ["BOTH1", "SOUP1", "SOUP2"])   # fixture's kept
        self.assertTrue(self.doc("recipes.yaml")["scope"].startswith("pilots fixture, kitchen:"))
        self.assertEqual(self.doc("recipes.yaml")["count"], 3)
        tags = {**TAGS, "SOUP2": {"topics": ["crafts"], "cities": []}}
        self.write("data/tags.yaml", tags)
        self.send("--pilot", "kitchen")
        self.assertEqual(sorted(self.saves("recipes.yaml")), ["BOTH1", "SOUP1"])   # its own save that left goes
        self.assertEqual(sorted(self.saves("crafts.yaml")), ["SOUP2"])

    def test_pilot_leaves_an_all_file_alone(self):
        self.send("--all")
        before = self.read("recipes.yaml")
        self.send("--pilot", "kitchen")
        self.assertEqual(self.read("recipes.yaml"), before)

    def test_rerun_gives_the_same_bytes(self):
        self.send("--all")
        first = {rel: self.read(rel) for rel in ("travel/fixture-state.yaml", "recipes.yaml", "crafts.yaml")}
        self.send("--all")
        self.assertEqual(first, {rel: self.read(rel) for rel in first})

    def test_kept_google_id_goes_into_the_spot(self):
        self.write("data/google.yaml", {
            "osm:node/8": {"query": "Example Point, Fixture Coast", "verdict": "match", "id": "ChIJexamplePoint",
                           "by": "auto", "date": "2026-01-02"},
            "spot:example-tiny-cafe@fixture-town": {"query": "Example Tiny Cafe, Fixture Town", "verdict": "match",
                                                    "id": "ChIJexampleCafe", "by": "hand", "date": "2026-01-02"},
            "osm:node/9": {"query": "an older search text", "verdict": "match", "id": "ChIJstale", "by": "auto",
                           "date": "2026-01-02"},
            "osm:way/7": {"query": "Example Cove Beach, Fixture Town", "verdict": "none", "by": "auto",
                          "date": "2026-01-02"}})
        self.send("--all")
        state = self.saves("travel/fixture-state.yaml")
        point, bluff = state["ROAD1"]["items"]
        self.assertEqual(point["google_id"], "ChIJexamplePoint")
        self.assertIn("query_place_id=ChIJexamplePoint", point["map"])
        self.assertNotIn("google_id", bluff)          # its search text changed since: not used
        tiny = [i for i in state["TRIP1"]["items"] if i["name"] == "Example Tiny Cafe"][0]
        self.assertEqual(tiny["google_id"], "ChIJexampleCafe")
        cove = state["TRIP1"]["items"][0]
        self.assertNotIn("google_id", cove)           # nothing found: keeps its own link
        self.assertEqual(cove["map"], "https://maps.example/cove")

    def test_all_removes_files_no_longer_written(self):
        stale = os.path.join(self.root, "out", "travel", "gone-state.yaml")
        os.makedirs(os.path.dirname(stale))
        open(stale, "w").close()
        self.send("--all")
        self.assertFalse(os.path.exists(stale))


if __name__ == "__main__":
    unittest.main()
