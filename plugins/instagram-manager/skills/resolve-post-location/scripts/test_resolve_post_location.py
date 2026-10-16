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
import urllib.error
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
    "VENUA": {"topics": ["travel"], "cities": ["Fixture Town"], "source": "model"},
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
    {**save("VENUA", "Lunch at Example Diner 📍12 Example St, Fixture Town FS 00000. Tea at Example Nook: "
                     "40.01234, -120.01234. And thanks to our pastry chef!"),
     "owner": {"username": "examplebakery", "name": "Example Bakery"}},
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
    "VENUA": [{"said": "Example Diner", "near": "Fixture Town", "address": "12 Example St, Fixture Town FS 00000"},
              {"said": "Example Nook", "near": "Fixture Town", "lat": 40.01234, "lon": -120.01234},
              {"said": "@examplebakery", "near": "Fixture Town", "name": "Example Bakery"},   # the creator itself
              {"said": "@otherbakery", "near": "Fixture Town"}],                            # nowhere in the post
    "LISTA": [{"said": "Example Pier", "near": "Fixture Town"},
              {"said": "Example Gardens", "near": "Fixture Town"},
              {"said": "Example Museum", "near": "Fixture Town"}],
}


def hit(name, lat, lon, typ, osm_id, box=None, wikidata=None, osm_type="node"):
    h = {"name": name, "display_name": f"{name}, Fixture County, Fixture State", "lat": str(lat), "lon": str(lon),
         "type": typ, "category": "tourism", "osm_type": osm_type, "osm_id": osm_id, "importance": 0.3,
         "boundingbox": [str(x) for x in (box or (lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001))]}
    if wikidata:
        h["extratags"] = {"wikidata": wikidata}
    return h


# The fake OpenStreetMap, by the text searched for. Not listed: not found.
OSM = {
    "Example Cove Beach": [hit("Example Cove Beach", 40.045, -120.0, "beach", 11, wikidata="Q100001")],  # 5 km
    "Example Cafe": [hit("Example Cafe", 40.01, -120.01, "cafe", 12)],
    "Far Away Tower": [hit("Far Away Tower", 40.36, -120.0, "tower", 13)],                              # 40 km
    "Fixture Park": [hit("Fixture Park", 41.0, -121.0, "national_park", 14, box=(40.7, 41.3, -121.4, -120.6),
                         osm_type="relation")],
    "Example Falls Trail": [hit("Example Falls Trail", 41.28, -121.0, "path", 15)],    # 31 km, inside the box
    "Distant Ridge Loop": [hit("Distant Ridge Loop", 41.5, -121.0, "path", 16)],      # 56 km, outside it
    "Example Pier": [hit("Example Pier", 40.002, -120.002, "pier", 17)],
    "Example Gardens": [hit("Example Gardens", 40.003, -119.99, "garden", 18)],
    "Example Museum": [hit("Example Museum", 39.99, -120.004, "museum", 19)],
    "Far Away Tower, Fixture Town": [hit("Near Tower", 40.02, -120.0, "tower", 20)],
    "12 Example St, Fixture Town FS 00000": [hit("12", 40.004, -120.003, "house", 22)],    # the name is not listed
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
        self.assertEqual(sorted(codes), ["LISTA", "NONEA", "PARKA", "TOWNA", "VENUA"])   # WIDEA has only a state
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

    def test_a_sprawling_city_reaches_as_far_as_its_own_width(self):
        """A city's suburbs sit past a town's 25 km. config/places.yaml's `box_km` says how far the city
        reaches, and a spot held back for its distance is tried again once that covers it."""
        self.locate()
        self.assertEqual(self.spot("data/pins-review.yaml", "TOWNA", "Far Away Tower")["why"],
                         "40 km from Fixture Town")
        self.write("config/places.yaml", {"places": {"Fixture Town": {"names": ["Fixture Town"], "box_km": 45}}})
        self.run_script("--merge")
        tower = self.spot("data/pins.yaml", "TOWNA", "Far Away Tower")
        self.assertEqual((tower["name"], tower["osm"]), ("Far Away Tower", "node/13"))
        self.assertNotIn("Far Away Tower", [e["said"] for e in self.read("data/pins-review.yaml").get("TOWNA", [])])
        self.write("config/places.yaml", {"places": {"Fixture Town": {"names": ["Fixture Town"], "box_km": 30}}})
        self.assertFalse(rpl.now_in_reach({"why": "40 km from Fixture Town", "near": "Fixture Town", "km": 40.2},
                                          rpl.load_places()))   # not wide enough: not searched again each merge

    def test_a_region_stored_as_a_point_reaches_50_km_not_its_made_up_box(self):
        """OpenStreetMap gives a region it keeps as one point a box a degree either side. That box
        is not the region's edge: a lodge 62 km off, inside it, goes to review."""
        places = {"places": {**PLACES["places"], "Fixture Coast": {
            "kind": "region", "in": "Fixture State", "lat": 42.0, "lon": -122.0, "found": "Fixture Coast"}}}
        self.write("data/places.yaml", places)
        self.write("data/tags.yaml", {"COASTA": {"topics": ["travel"], "cities": ["Fixture Coast"], "source": "model"}})
        self.write(".cache/saves.json", {"saves": [save("COASTA", "Slept at Example Coast Inn, then Example Lodge")]})
        osm = {"Fixture Coast": [hit("Fixture Coast", 42.0, -122.0, "region", 30, box=(41.0, 43.0, -123.0, -121.0))],
               "Example Coast Inn": [hit("Example Coast Inn", 42.27, -122.0, "hotel", 31)],     # 30 km
               "Example Lodge": [hit("Example Lodge", 42.56, -122.0, "motel", 32)]}              # 62 km
        with mock.patch.dict(OSM, osm):
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"COASTA": [{"said": "Example Coast Inn", "near": "Fixture Coast"},
                                          {"said": "Example Lodge", "near": "Fixture Coast"}]})
            self.run_script("--merge")
        self.assertGreater(self.spot("data/pins.yaml", "COASTA", "Example Coast Inn")["km"], 25)
        self.assertEqual(self.spot("data/pins-review.yaml", "COASTA", "Example Lodge")["why"],
                         "62 km from Fixture Coast")

    def test_a_spot_out_of_its_areas_reach_is_pinned_for_another_of_the_saves_areas(self):
        places = {"places": {**PLACES["places"], "Fixture Village": {
            "kind": "city", "in": "Fixture State", "lat": 40.3, "lon": -120.0, "found": "Fixture Village"}}}
        self.write("data/places.yaml", places)
        self.write("data/tags.yaml", {"TWOA": {"topics": ["travel"], "cities": ["Fixture Town", "Fixture Village"],
                                               "source": "model"}})
        self.write(".cache/saves.json", {"saves": [save("TWOA", "A night at Village Inn")]})
        with mock.patch.dict(OSM, {"Village Inn": [hit("Village Inn", 40.32, -120.0, "hotel", 33)]}):  # 36 km
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"TWOA": [{"said": "Village Inn", "near": "Fixture Town"}]})
            self.run_script("--merge")
        p = self.spot("data/pins.yaml", "TWOA", "Village Inn")
        self.assertEqual((p["near"], p["osm"]), ("Fixture Village", "node/33"))
        self.assertLess(p["km"], 3)

    def test_the_name_check(self):
        with mock.patch.dict(OSM, {"Example Museum": [hit("Example Baguette", 39.99, -120.004, "bakery", 21)],
                                   "Example Gardens": [hit("The Example Gardens (East)", 40.003, -119.99,
                                                           "garden", 18)]}):
            self.locate()
        wrong = self.spot("data/pins-review.yaml", "LISTA", "Example Museum")
        self.assertEqual(wrong["why"], "found Example Baguette, a different name")
        self.assertEqual(wrong["osm"], "node/21")                               # kept, for a person to judge
        self.assertEqual(self.spot("data/pins.yaml", "LISTA", "Example Gardens")["osm"], "node/18")
        self.assertTrue(rpl.same_name("Example Point", "Example Point State Park"))
        self.assertTrue(rpl.same_name("Example's Diner", "Examples Diner"))
        self.assertTrue(rpl.same_name("Example Pier", "Example Pier Fixture Town", "Fixture Town"))
        self.assertTrue(rpl.same_name("Exampleo FT", "Exampleo", "Fixture Town"))     # the area's initials
        self.assertTrue(rpl.same_name("Example Meadows", "Example Meadow"))
        self.assertTrue(rpl.same_name("Á Exámple", "A Example"))
        self.assertTrue(rpl.same_name("Example Lighthouse", "Example Light Station"))
        self.assertTrue(rpl.same_name("Exampleo", "Exampleo Coffee Co."))
        self.assertTrue(rpl.same_name("Example Trail", "Example Trail #1X01"))
        self.assertTrue(rpl.same_name("Fixture Beach", "Fixture Beach", "Fixture"))    # a match, named for its area
        self.assertTrue(rpl.same_name("Fixture Creamery", "Fixture County Creamery", "Fixture"))
        self.assertFalse(rpl.same_name("Example Mission", "Mission Ranch Example"))   # "ranch" is not a place word
        self.assertFalse(rpl.same_name("Example Bakery", "Example Baguette"))
        self.assertFalse(rpl.same_name("Exampleo Cafe", "Exampleo Bakery"))         # two kinds of business
        self.assertFalse(rpl.same_name("State Park", "Example State Park"))         # no word of its own shared
        self.assertFalse(rpl.same_name("The", "Example"))                       # no words left on one side

    def test_a_street_of_the_same_name_is_not_the_venue(self):
        road = {**hit("Example Museum", 39.99, -120.004, "residential", 23, osm_type="way"), "category": "highway"}
        with mock.patch.dict(OSM, {"Example Museum": [road]}):
            self.locate()
        entry = self.spot("data/pins-review.yaml", "LISTA", "Example Museum")
        self.assertTrue(entry["why"].startswith("not found near "))         # the hub still opens it by name
        self.assertTrue(entry["why"].endswith(" (only a street of that name)"))
        road = {"category": "highway", "type": "residential"}
        self.assertTrue(rpl.a_street(road, "Example Moro"))
        self.assertFalse(rpl.a_street(road, "Example Street"))                 # the post means the street
        self.assertFalse(rpl.a_street(road, "Example Blvd"))
        self.assertFalse(rpl.a_street({"category": "highway", "type": "primary"}, "Example Bridge"))   # stored as the road over it
        self.assertFalse(rpl.a_street({"category": "highway", "type": "path"}, "Example Falls"))   # a trail
        self.assertFalse(rpl.a_street({"category": "amenity", "type": "restaurant"}, "Example Moro"))

    def test_a_venue_openstreetmap_does_not_list_is_pinned_at_the_address_or_coordinates_the_caption_gives(self):
        self.locate()
        diner = self.spot("data/pins.yaml", "VENUA", "Example Diner")
        self.assertEqual((diner["name"], diner["kind"], diner["lat"]), ("Example Diner", "address", 40.004))
        self.assertNotIn("osm", diner)                       # the building's id is not the diner's
        self.assertIn("query=Example+Diner%2C+12+Example+St", diner["map"])
        nook = self.spot("data/pins.yaml", "VENUA", "Example Nook")
        self.assertEqual((nook["lat"], nook["found"]), (40.01234, "the caption's coordinates"))
        self.assertNotIn("Example Nook", [p["q"] for p in self.asked])   # no lookup needed
        bakery = self.spot("data/pins-review.yaml", "VENUA", "@examplebakery")
        self.assertEqual(bakery["why"], "not found near Fixture Town")   # the creator passes the quote check
        other = self.spot("data/pins-review.yaml", "VENUA", "@otherbakery")
        self.assertEqual(other["why"], "quote not in caption")
        self.assertTrue(rpl.quote_ok("Example Trail", "📍 𝐄𝐱𝐚𝐦𝐩𝐥𝐞 𝐓𝐫𝐚𝐢𝐥"))   # bold letters are still letters
        self.assertEqual(rpl.search_text({"said": "𝐄𝐱𝐚𝐦𝐩𝐥𝐞 𝐓𝐫𝐚𝐢𝐥"}), "Example Trail")
        self.assertTrue(rpl.address_in("12 Example St, Fixture Town", "📍12 Example St\nFixture Town FS"))
        self.assertFalse(rpl.address_in("14 Example St, Fixture Town", "📍12 Example St\nFixture Town FS"))
        self.assertFalse(rpl.coords_in("at 40.01234, -120.01234", 40.0123, -120.01234))
        self.assertTrue(rpl.coords_in("at 40.012340,-120.01234", 40.01234, -120.01234))

    def test_an_address_with_a_suite_is_looked_up_without_it(self):
        """OpenStreetMap knows the building, not the unit: "Suite 4" or a trailing "B" finds nothing."""
        self.write(".cache/saves.json", {"saves": [save("VENUA", "Example Grill 📍12 Example St Suite 4, Fixture Town")]})
        with mock.patch.dict(OSM, {"12 Example St, Fixture Town": [hit("12", 40.004, -120.003, "house", 22)]}):
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"VENUA": [{"said": "Example Grill", "near": "Fixture Town",
                                          "address": "12 Example St Suite 4, Fixture Town"}]})
            self.run_script("--merge")
        grill = self.spot("data/pins.yaml", "VENUA", "Example Grill")
        self.assertEqual((grill["kind"], grill["address"]), ("address", "12 Example St Suite 4, Fixture Town"))
        self.assertIn("12 Example St, Fixture Town", [p["q"] for p in self.asked])
        # one sent to review before the unit was dropped is tried again, once
        self.write("data/pins.yaml", {})
        self.write("data/pins-review.yaml", {"VENUA": [
            {"said": "Example Grill", "near": "Fixture Town", "why": "not found near Fixture Town",
             "address": "12 Example St Suite 4, Fixture Town"},
            {"said": "Example Grill", "near": "Fixture Town", "why": "not found near Fixture Town",
             "address": "99 Example St Suite 4, Fixture Town"}]})
        with mock.patch.dict(OSM, {"12 Example St, Fixture Town": [hit("12", 40.004, -120.003, "house", 22)]}):
            self.run_script("--merge")
        self.assertEqual(self.spot("data/pins.yaml", "VENUA", "Example Grill")["kind"], "address")
        left = self.read("data/pins-review.yaml")["VENUA"]
        self.assertEqual([e.get("street_tried") for e in left], [True])   # not found: not tried again
        self.assertEqual(rpl.street_only("1 Example Dr B, Fixture Town"), "1 Example Dr, Fixture Town")
        self.assertEqual(rpl.street_only("1 Example Cir #74, Fixture Town"), "1 Example Cir, Fixture Town")
        self.assertEqual(rpl.street_only("1 Example Rd Unit 9 Fixture Town"), "1 Example Rd Fixture Town")
        self.assertEqual(rpl.street_only("1 Example Blvd, Ste 11"), "1 Example Blvd")
        self.assertEqual(rpl.street_only("4 1/2 Example St"), "4 1/2 Example St")   # no unit to drop

    def test_an_address_found_only_as_its_street_is_not_pinned(self):
        """OpenStreetMap may know the road but not the house: its point can be kilometres from the venue."""
        self.write(".cache/saves.json", {"saves": [save("VENUA", "Example Grill 📍12 Example St, Fixture Town")]})
        with mock.patch.dict(OSM, {"12 Example St, Fixture Town": [hit("Example Street", 40.03, -120.0, "primary", 23)]}):
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"VENUA": [{"said": "Example Grill", "near": "Fixture Town",
                                          "address": "12 Example St, Fixture Town"}]})
            self.run_script("--merge")
        self.assertEqual(self.spot("data/pins-review.yaml", "VENUA", "Example Grill")["why"], "not found near Fixture Town")
        # one pinned that way before the check moves to review; a person's pin stays
        self.write("data/pins-review.yaml", {})
        self.write("data/pins.yaml", {"VENUA": [
            {"name": "Example Grill", "said": "Example Grill", "near": "Fixture Town", "kind": "address",
             "lat": 40.03, "lon": -120.0, "address": "12 Example St, Fixture Town", "found": "Example Street, Fixture Town"},
            {"name": "Example Nook", "said": "Example Nook", "near": "Fixture Town", "kind": "address", "by": "hand",
             "lat": 40.03, "lon": -120.0, "address": "14 Example St, Fixture Town", "found": "Example Street, Fixture Town"}]})
        out = self.run_script("--merge")
        self.assertIn("1 address pins moved to review", out)
        self.assertEqual([p["said"] for p in self.read("data/pins.yaml")["VENUA"]], ["Example Nook"])
        moved = self.spot("data/pins-review.yaml", "VENUA", "Example Grill")
        self.assertEqual((moved["street_tried"], "lat" in moved), (True, False))
        self.assertIn("OpenStreetMap found only the street at 12 Example St, Fixture Town",
                      pins_page.spot_row(0, moved, True))
        self.assertTrue(rpl.at_the_house("12, Example Street, Fixture Town", "12 Example St"))
        self.assertFalse(rpl.at_the_house("Example Street, 12345, Fixture Town", "12 Example St"))   # a postcode
        self.assertTrue(rpl.at_the_house("Example Street", "Example St"))   # no house number to match

    def test_an_address_found_only_as_its_street_is_searched_again_once_its_city_is_wider(self):
        """The house sat outside the city's old search box. Once `box_km` widens it, the address is
        searched again, once per box. A reel's pin at the same house is not doubled."""
        self.write(".cache/saves.json", {"saves": [save("VENUA", "Example Grill 📍12 Example St, Fixture Town")]})
        self.write("data/pins.yaml", {"VENUA": [
            {"name": "Grill", "said": "GRILL", "near": "Fixture Town", "kind": "address", "lat": 40.6, "lon": -120.0,
             "address": "12 Example St, Fixture Town", "found": "12, Fixture County, Fixture State", "from": "video"}]})
        self.write("data/pins-review.yaml", {"VENUA": [
            {"said": "Example Grill", "near": "Fixture Town", "name": "Example Grill",
             "address": "12 Example St, Fixture Town", "street_tried": True,
             "why": "only the street was found near Fixture Town, not the house"}]})
        with mock.patch.dict(OSM, {"12 Example St, Fixture Town": [hit("12", 40.6, -120.0, "house", 24)]}):   # 67 km
            self.run_script("--merge")
            held = self.spot("data/pins-review.yaml", "VENUA", "Example Grill")
            self.assertTrue(held["searched_in"])
            asked = len(self.asked)
            self.run_script("--merge")
            self.assertEqual(len(self.asked), asked)   # the same box: not searched again
            self.write("config/places.yaml", {"places": {"Fixture Town": {"names": ["Fixture Town"], "box_km": 70}}})
            self.run_script("--merge")
        self.assertEqual([p["said"] for p in self.read("data/pins.yaml")["VENUA"]], ["GRILL"])
        self.assertNotIn("VENUA", self.read("data/pins-review.yaml"))

    def test_a_name_found_away_from_the_captions_address_is_another_branch(self):
        """A name like a chain's finds a branch across town: the caption's address wins, and with no
        address found the spot goes to review rather than sit on the other branch."""
        deli = hit("Example Deli", 40.006, -120.0, "restaurant", 41)
        deli["display_name"] = "Example Deli, 5, Main Street, Fixture County, Fixture State"   # at the house
        self.write(".cache/saves.json", {"saves": [save("VENUA", "Example Grill 📍12 Example St, Fixture Town. "
                                                            "Example Wok 📍30 Other Rd, Fixture Town. "
                                                            "Example Deli 📍5 Main St, Fixture Town")]})
        osm = {"Example Grill": [hit("Example Grill", 40.02, -120.0, "restaurant", 40)],    # another branch
               "12 Example St, Fixture Town": [hit("12", 40.004, -120.003, "house", 22)],
               "Example Wok": [hit("Example Wok", 40.03, -120.0, "restaurant", 42)],
               "Example Deli": [deli]}
        with mock.patch.dict(OSM, osm):
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"VENUA": [{"said": "Example Grill", "near": "Fixture Town", "address": "12 Example St, Fixture Town"},
                                         {"said": "Example Wok", "near": "Fixture Town", "address": "30 Other Rd, Fixture Town"},
                                         {"said": "Example Deli", "near": "Fixture Town", "address": "5 Main St, Fixture Town"}]})
            self.run_script("--merge")
        grill = self.spot("data/pins.yaml", "VENUA", "Example Grill")
        self.assertEqual((grill["kind"], grill["lat"]), ("address", 40.004))   # the address, not the branch
        self.assertEqual(self.spot("data/pins.yaml", "VENUA", "Example Deli")["osm"], "node/41")   # at the house
        wok = self.spot("data/pins-review.yaml", "VENUA", "Example Wok")
        self.assertEqual((wok["why"], wok["address_tried"], "lat" in wok),
                         ("found Example Wok by name, but not at the caption's address", True, False))
        # one pinned that way before the check moves to review and has its address looked up once
        self.write("data/pins-review.yaml", {})
        self.write("data/pins.yaml", {"VENUA": [
            {"name": "Example Wok", "said": "Example Wok", "near": "Fixture Town", "kind": "restaurant", "osm": "node/42",
             "lat": 40.03, "lon": -120.0, "address": "30 Other Rd, Fixture Town", "found": "Example Wok, Fixture County"},
            {"name": "Example Grill", "said": "Example Grill", "near": "Fixture Town", "kind": "restaurant",
             "osm": "node/40", "by": "hand", "lat": 40.02, "lon": -120.0, "address": "12 Example St, Fixture Town",
             "found": "Example Grill, Fixture County"}]})
        with mock.patch.dict(OSM, osm):
            out = self.run_script("--merge")
        self.assertIn("1 pins found by name moved to review", out)
        self.assertEqual([p["said"] for p in self.read("data/pins.yaml")["VENUA"]], ["Example Grill"])   # a person's
        wok = self.spot("data/pins-review.yaml", "VENUA", "Example Wok")
        self.assertEqual((wok["address_tried"], "lat" in wok), (True, False))
        self.assertIn("OpenStreetMap found one by that name elsewhere, not at 30 Other Rd, Fixture Town",
                      pins_page.spot_row(0, wok, True))

    def test_a_spot_outside_the_saves_areas_goes_to_review(self):
        self.locate()
        e = self.spot("data/pins-review.yaml", "TOWNA", "Made Up Spot")
        self.assertEqual(e["why"], "near Fixture Park, which is not one of the save's areas")

    def test_a_road_trip_stop_in_the_wrong_area_is_listed_and_fixed_with_near_and_lookup(self):
        """A stop the save is not tagged near is filed under the nearest area, so the merge lists it;
        a person adds its town and gives it `near:` and `lookup:`, and the next merge pins it there."""
        self.write(".cache/saves.json", {"saves": [save("TOWNA", "Day 1 Example Cove Beach. Day 3 Other Arch")]})
        with mock.patch.dict(OSM, {"Other Arch": [hit("Other Arch", 41.5, -120.0, "arch", 40)]}):   # 167 km off
            paths = self.run_script("--prepare", "--all").split()
            self.agent(paths, {"TOWNA": [{"said": "Example Cove Beach", "near": "Fixture Town"},
                                         {"said": "Other Arch", "near": "Fixture Town",
                                          "really_in": "Other Town, Other State"}]})
            out = self.run_script("--merge")
            self.assertIn("1 spots in review look filed under the wrong area", out)
            self.assertIn("'Other Arch' under Fixture Town: really in Other Town, Other State", out)
            self.assertEqual(self.spot("data/pins-review.yaml", "TOWNA", "Other Arch")["really_in"],
                             "Other Town, Other State")
            self.assertEqual([w[1] for w in rpl.wrong_area({"X": [{"said": "Far", "near": "T", "km": 61.0},
                                                                 {"said": "Close", "near": "T", "km": 40.0},
                                                                 {"said": "Gone", "near": "T", "km": 99.0,
                                                                  "drop": True}]})], ["Far"])
            places = {"places": {**PLACES["places"], "Other Town": {
                "kind": "city", "in": "Fixture State", "lat": 41.49, "lon": -120.0, "found": "Other Town"}}}
            self.write("data/places.yaml", places)
            review = self.read("data/pins-review.yaml")
            for e in review["TOWNA"]:
                if e["said"] == "Other Arch":
                    e.update(near="Other Town", lookup="Other Arch")
            self.write("data/pins-review.yaml", review)
            out = self.run_script("--merge")
        p = self.spot("data/pins.yaml", "TOWNA", "Other Arch")
        self.assertEqual((p["near"], p["osm"], p["lookup"]), ("Other Town", "node/40", "Other Arch"))
        self.assertNotIn("wrong area", out)

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
        self.assertIn("1 review entries moved to the pins", out)
        p = self.spot("data/pins.yaml", "TOWNA", "Far Away Tower")
        self.assertEqual((p["name"], p["asked"]), ("Near Tower", "Far Away Tower, Fixture Town"))
        self.assertNotIn("Far Away Tower", [e["said"] for e in self.read("data/pins-review.yaml")["TOWNA"]])

    def test_a_review_entry_marked_ok_is_pinned_as_found_and_kept(self):
        with mock.patch.dict(OSM, {"Example Museum": [hit("Example Baguette", 39.99, -120.004, "bakery", 21)]}):
            self.locate()
            review = self.read("data/pins-review.yaml")
            for e in review["LISTA"]:
                if e["said"] == "Example Museum":
                    e["ok"] = True                                     # a person says the find is right
            self.write("data/pins-review.yaml", review)
            self.assertIn("1 review entries moved to the pins", self.run_script("--merge"))
            p = self.spot("data/pins.yaml", "LISTA", "Example Museum")
            self.assertEqual((p["name"], p["osm"], p["by"]), ("Example Baguette", "node/21", "hand"))
            self.assertNotIn("why", p)
            self.assertNotIn("ok", p)
            self.agent(self.run_script("--prepare", "--pilot", "fixture", "--redo").split())
            self.run_script("--merge")                                 # the agent reads every save again
        self.assertEqual([p.get("by") for p in self.read("data/pins.yaml")["LISTA"] if p["said"] == "Example Museum"],
                         ["hand"])
        self.assertNotIn("Example Museum", [e["said"] for e in self.read("data/pins-review.yaml").get("LISTA") or []])

    def test_hand_fixes_survive_a_re_read(self):
        self.locate()
        review = self.read("data/pins-review.yaml")
        for e in review["TOWNA"]:
            if e["said"] == "Far Away Tower":
                e["lookup"] = "Far Away Tower, Fixture Town"          # a person's lookup
        review["TOWNA"] = [e for e in review["TOWNA"] if e["said"] != "Invented Lighthouse"]
        self.write("data/pins-review.yaml", review)
        pins = self.read("data/pins.yaml")
        for p in pins["LISTA"]:
            if p["said"] == "Example Pier":
                p["drop"] = True                                       # a wrong pin, dropped where it is
        pins["TOWNA"].append({"name": "Invented Lighthouse", "said": "Invented Lighthouse", "near": "Fixture Town",
                              "lat": 40.01, "lon": -120.01, "by": "hand"})   # a pin a person placed
        self.write("data/pins.yaml", pins)
        self.assertIn("1 pins marked drop: true", self.run_script("--merge"))

        self.agent(self.run_script("--prepare", "--pilot", "fixture", "--redo").split())
        self.run_script("--merge")                                     # the agent reads every save again
        pins, review = self.read("data/pins.yaml"), self.read("data/pins-review.yaml")
        tower = [p for p in pins["TOWNA"] if p["said"] == "Far Away Tower"]
        self.assertEqual([(p["name"], p["lookup"]) for p in tower], [("Near Tower", "Far Away Tower, Fixture Town")])
        self.assertEqual([p.get("by") for p in pins["TOWNA"] if p["said"] == "Invented Lighthouse"], ["hand"])
        self.assertNotIn("Example Pier", [p["said"] for p in pins["LISTA"]])
        self.assertEqual([e.get("drop") for e in review["LISTA"] if e["said"] == "Example Pier"], [True])
        self.assertEqual([e["said"] for e in review.get("TOWNA") or []
                          if e["said"] in ("Far Away Tower", "Invented Lighthouse")], [])

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

    def test_openstreetmap_refusing_stops_the_merge_and_files_nothing_as_not_found(self):
        paths = self.run_script("--prepare", "--pilot", "fixture", "--batch-saves", "3").split()
        self.assertEqual(len(paths), 2)
        self.agent(paths)
        with open(paths[0]) as fh:
            first = [r["code"] for r in json.load(fh)["saves"]]
        refused = "Example Pier" if "LISTA" not in first else "Example Diner"   # a spot in the second batch

        tries = []

        def osm(params):
            if params["q"] == refused:
                tries.append(params["q"])
                raise urllib.error.HTTPError("https://example.invalid", 429, "Too Many Requests", {}, None)
            return self.osm(params)

        with mock.patch.object(geocode, "COOL", 0), contextlib.redirect_stderr(io.StringIO()), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = rpl.main(["--merge"], fetcher=osm)
        self.assertEqual(code, 3)
        self.assertIn("STOPPED: OpenStreetMap refused", out.getvalue())
        self.assertEqual(len(tries), 2)                                          # asked once more, then stopped
        self.assertTrue(os.path.exists(paths[0].replace(".json", ".answers.merged.json")))   # the first is kept
        self.assertTrue(os.path.exists(paths[1].replace(".json", ".answers.json")))          # the second waits
        review = self.read("data/pins-review.yaml")
        self.assertEqual([e for es in review.values() for e in es if e["said"] == refused], [])
        self.assertNotIn(refused, json.loads(self.text(".cache/geocode.json")))  # a refusal is not cached
        self.assertIn("0 batches still waiting", self.run_script("--merge"))    # accepted again: all merged
        self.assertTrue(os.path.exists(paths[1].replace(".json", ".answers.merged.json")))

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
            pins_page.main(["--out", out, "--no-previews"])
        page = self.text(".cache/hub/pins.html")
        self.assertNotIn('class="save has-pv"', page)
        self.assertIn("cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", page)
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", page)
        self.assertIn("openstreetmap.org/copyright", page)
        self.assertIn("@example_creator", page)
        self.assertIn("<q>Example Cove Beach</q>", page)
        self.assertIn("5 km from Fixture Town", page)
        self.assertIn("https://www.instagram.com/p/TOWNA/", page)
        self.assertIn("40 km from Fixture Town", page)                         # a review reason
        self.assertIn("quote not in caption", page)
        # The list comes first and the map second, as on the hub's own pages.
        self.assertLess(page.index('<div class="list">'), page.index('<div id="map"'))

    def test_a_save_with_a_preview_shows_its_picture_and_names_its_flipbook(self):
        self.locate()
        pins, review = self.read("data/pins.yaml"), self.read("data/pins-review.yaml")
        shown = pins_page.codes_shown(pins, review)
        self.assertIn("TOWNA", shown)
        pv = {"TOWNA": {"poster": "TOWNA.jpg", "anim": "TOWNA.webp"}, "PARKA": {"poster": "PARKA.jpg", "anim": None},
              "VENUA": {"poster": None, "anim": None}}
        page, _ = pins_page.build(pins, review, {}, {}, pv)
        self.assertIn('<img src="previews/TOWNA.jpg" data-poster="previews/TOWNA.jpg" '
                      'data-anim="previews/TOWNA.webp" width="72" height="96" alt="" loading="lazy"', page)
        self.assertIn('<img src="previews/PARKA.jpg" data-poster="previews/PARKA.jpg" width="72"', page)  # a still only
        self.assertNotIn("previews/VENUA", page)
        self.assertEqual(page.count('class="save has-pv"'), sum(
            1 for group in (pins, review) for c in group if c in ("TOWNA", "PARKA")))
        self.assertIn("IntersectionObserver", page)
        self.assertIn(f"MAX={pins_page.previews.MAX_PLAYING},", page)
        page, _ = pins_page.build(pins, review, {}, {}, {"PARKA": pv["PARKA"]})
        self.assertNotIn("IntersectionObserver", page)   # no flipbook, so no player
        self.assertEqual(pins_page.preview_html("X", {}, None), "")


if __name__ == "__main__":
    unittest.main()
