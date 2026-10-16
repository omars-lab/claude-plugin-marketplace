#!/usr/bin/env python3
"""Offline checks for google_ids.py and shared/scripts/google_places.py. Google is stubbed: no
network, no key.

    python3 skills/find-google-ids/scripts/test_google_ids.py

Every code, name, place and id here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import google_ids  # noqa: E402
import google_places as gp  # noqa: E402
import yaml  # noqa: E402

COLLECTIONS = {"collections": {"Fixture Trips": {"topics": ["travel"], "cities": ["Fixture State"]}},
               "pilots": {"fixture": {"collections": ["Fixture Trips"], "cities": ["Fixture State"]}}}
PLACES = {"places": {
    "Fixture State": {"kind": "state", "lat": 10.0, "lon": 20.0},
    "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 10.5, "lon": 20.5},
    "Fixture Park": {"kind": "park", "in": "Fixture State", "lat": 11.0, "lon": 21.0},
}}


def save(code):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "reel", "caption": "",
            "hashtags": [], "owner": {"username": "example_creator"}, "saved_at": "2026-01-02T03:04",
            "collections": ["Fixture Trips"]}


SAVES = [save("EAT1"), save("EAT2"), save("HIKE1")]
TAGS = {c: {"topics": ["travel"], "cities": ["Fixture State", "Fixture Town"]} for c in ("EAT1", "EAT2", "HIKE1")}
PINS = {
    "EAT1": [{"name": "Example Tacos", "near": "Fixture Town", "lat": 10.51, "lon": 20.51, "osm": "node/1"},
             {"name": "Example Grill", "near": "Fixture Town", "lat": 10.52, "lon": 20.52, "osm": "node/2"},
             {"name": "Pho", "near": "Fixture Town", "lat": 10.53, "lon": 20.53, "osm": "node/3"}],
    "EAT2": [{"name": "Example Tacos", "near": "Fixture Town", "lat": 10.51, "lon": 20.51, "osm": "node/1"}],
    "HIKE1": [{"name": "Example Falls", "near": "Fixture Park", "lat": 11.1, "lon": 21.1, "osm": "node/4"}],
}
REVIEW = {"EAT2": [{"said": "Example Bakery", "asked": "Example Bakery", "near": "Fixture Town",
                    "why": "not found near Fixture Town"}],
          "HIKE1": [{"said": "Example Lookout", "asked": "Example Lookout", "near": "Fixture State",   # no pin,
                     "why": "not found near Fixture State"}]}                                           # area a state


def place(pid, name, address="1 Google Way", status="OPERATIONAL"):
    return {"id": pid, "displayName": {"text": name}, "formattedAddress": address,
            "types": ["restaurant"], "businessStatus": status}


ANSWERS = {   # our search text → Google's answer
    "Example Tacos, Fixture Town": [place("ID_TACOS", "Example Tacos Downtown", "9 Secret Google St"),
                                    place("ID_OTHER", "Another Place")],
    "Example Grill, Fixture Town": [place("ID_GRILL_A", "Example Grill"), place("ID_GRILL_B", "Example Grill & Bar")],
    "Pho, Fixture Town": [place("ID_PHO", "Pho")],
    "Example Falls, Fixture Park": [],
    "Example Bakery, Fixture Town": [place("ID_BAKERY", "Example Bakery", status="CLOSED_PERMANENTLY")],
}


class Ids(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for rel, data in (("config/collections.yaml", COLLECTIONS), ("data/places.yaml", PLACES),
                          ("data/tags.yaml", TAGS), ("data/pins.yaml", PINS), ("data/pins-review.yaml", REVIEW)):
            self.write(rel, data)
        self.write(".cache/saves.json", {"saves": SAVES})
        self.env = {k: os.environ.get(k) for k in ("INSTAGRAM_HOME", "GOOGLE_MAPS_API_KEY")}
        os.environ["INSTAGRAM_HOME"] = self.root
        os.environ["GOOGLE_MAPS_API_KEY"] = "test-key-not-real"
        self.calls = []
        self.real = gp.search, gp.current_id

        def search(query, pin, half_km, key, on_retry=None):
            self.calls.append((query, pin, half_km))
            return gp.candidates({"places": ANSWERS.get(query, [])})
        gp.search = search
        gp.current_id = lambda pid, key, on_retry=None: {"ID_OLD": "ID_NEW"}.get(pid, pid)

    def tearDown(self):
        gp.search, gp.current_id = self.real
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write(self, rel, data):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh) if rel.endswith(".json") else yaml.safe_dump(data, fh)

    def run_ids(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()) as out:
            google_ids.main(list(argv))
        return out.getvalue(), err.getvalue()

    def kept(self):
        with open(os.path.join(self.root, "data", "google.yaml")) as fh:
            return fh.read(), yaml.safe_load(fh.seek(0) or fh)

    def test_box_is_half_km_each_way(self):
        r = gp.box({"lat": 0.0, "lon": 0.0}, 2.0)["rectangle"]
        self.assertAlmostEqual(r["high"]["latitude"] - r["low"]["latitude"], 4.0 / gp.KM_PER_DEG)
        self.assertAlmostEqual(r["high"]["longitude"], 2.0 / gp.KM_PER_DEG)
        far_north = gp.box({"lat": 60.0, "lon": 0.0}, 2.0)["rectangle"]
        self.assertAlmostEqual(far_north["high"]["longitude"], 4.0 / gp.KM_PER_DEG, places=6)   # cos 60° = 0.5

    def test_name_rule(self):
        self.assertTrue(gp.same_name("Example Tacos", "Example Tacos Downtown"))
        self.assertTrue(gp.same_name("Café Example", "Cafe Example"))
        self.assertFalse(gp.same_name("Example Tacos", "Example Burritos"))
        self.assertFalse(gp.same_name("Pho", "Pho"))                    # too short to tell one from another
        self.assertTrue(gp.same_name("Exemplar", "Exemplar Coffee"))    # one word of 5+ letters
        found = gp.candidates({"places": ANSWERS["Example Grill, Fixture Town"]})
        self.assertIsNone(gp.auto_pick("Example Grill", found))         # two carry the name: a person picks
        self.assertTrue(gp.same_name("Example Falls Vista Point", "Example Fall Vista Point"))   # plural s
        beach = {"id": "B", "name": "Example Beach", "types": ["beach", "natural_feature"]}
        area = {"id": "A", "name": "Example Beach", "types": ["neighborhood", "political"]}
        stop = {"id": "S", "name": "Example Beach", "types": ["bus_stop", "transit_station"]}
        peak = {"id": "P", "name": "Example Beach", "types": ["mountain_peak"]}
        self.assertEqual(gp.auto_pick("Example Beach", [area, beach, stop])["id"], "B")   # the place, not the area
        self.assertIsNone(gp.auto_pick("Example Beach", [beach, peak]))                     # two places: a person
        self.assertEqual(gp.auto_pick("Example Beach", [area])["id"], "A")                 # the area is all there is

    def test_run_keeps_only_ids(self):
        out, err = self.run_ids("--pilot", "fixture")
        text, kept = self.kept()
        self.assertEqual(kept["osm:node/1"], {"query": "Example Tacos, Fixture Town", "verdict": "match",
                                              "id": "ID_TACOS", "by": "auto", "date": kept["osm:node/1"]["date"]})
        self.assertNotIn("osm:node/2", kept)                 # two Example Grills: left for a person
        self.assertNotIn("osm:node/3", kept)                 # "Pho": too short to keep by name
        self.assertEqual(kept["osm:node/4"]["verdict"], "none")
        self.assertNotIn("id", kept["osm:node/4"])
        self.assertEqual(kept["spot:example-bakery@fixture-town"]["id"], "ID_BAKERY")
        for google_words in ("Downtown", "Secret Google", "Another Place", "restaurant", "CLOSED", "Bar"):
            self.assertNotIn(google_words, text)             # nothing of Google's but the id
        self.assertIn("PICK='osm:node/2=ID_GRILL_B'", out)   # what a person copies
        self.assertIn("CLOSED FOR GOOD", out)                # shown, never written
        self.assertIn("1 kept places Google says are closed for good", out)
        self.assertIn("ev=google_no_box key=spot:example-lookout@fixture-state", err)   # no pin, area a state

    def test_each_spot_searched_once_in_the_right_box(self):
        self.run_ids("--pilot", "fixture")
        queries = [q for q, _, _ in self.calls]
        self.assertEqual(queries.count("Example Tacos, Fixture Town"), 1)   # in two posts, one search
        bakery = [c for c in self.calls if c[0] == "Example Bakery, Fixture Town"][0]
        self.assertEqual((bakery[1], bakery[2]), ({"lat": 10.5, "lon": 20.5}, gp.TOWN_BOX_KM["city"]))
        tacos = [c for c in self.calls if c[0] == "Example Tacos, Fixture Town"][0]
        self.assertEqual((tacos[1], tacos[2]), ({"lat": 10.51, "lon": 20.51}, gp.BOX_KM))

    def test_rerun_skips_what_is_kept(self):
        self.run_ids("--pilot", "fixture")
        self.calls.clear()
        self.run_ids("--pilot", "fixture")
        self.assertEqual(sorted(q for q, _, _ in self.calls), ["Example Grill, Fixture Town", "Pho, Fixture Town"])
        self.calls.clear()
        self.run_ids("--pilot", "fixture", "--refresh", "--only", "osm:node/1")
        self.assertEqual([q for q, _, _ in self.calls], ["Example Tacos, Fixture Town"])

    def test_pick_and_none_by_hand(self):
        self.run_ids("--pilot", "fixture")
        self.run_ids("--pilot", "fixture", "--pick", "osm:node/2=ID_OLD", "--none", "osm:node/3")
        _, kept = self.kept()
        self.assertEqual((kept["osm:node/2"]["id"], kept["osm:node/2"]["by"]), ("ID_NEW", "hand"))   # Google's current id
        self.assertEqual((kept["osm:node/3"]["verdict"], kept["osm:node/3"]["by"]), ("none", "hand"))
        self.run_ids("--pilot", "fixture", "--pick", "osm:node/2=ID_GRILL_A", "--by", "claude")
        self.assertEqual(self.kept()[1]["osm:node/2"]["by"], "claude")     # not passed off as a person's
        self.calls.clear()
        self.run_ids("--pilot", "fixture")
        self.assertEqual(self.calls, [])                     # nothing left to search

    def test_a_spot_in_the_wrong_area_is_not_searched(self):
        review = {**REVIEW, "EAT1": [{"said": "Other Diner", "asked": "Other Diner", "near": "Fixture Town",
                                      "why": "not found near Fixture Town", "really_in": "Other Town"}]}
        self.write("data/pins-review.yaml", review)
        out, _ = self.run_ids("--pilot", "fixture")
        self.assertNotIn("Other Diner, Fixture Town", [q for q, _, _ in self.calls])
        self.assertIn("1 not searched: filed under the wrong area, fix its area first", out)
        self.assertIn("spot:other-diner@fixture-town: 'Other Diner' under Fixture Town, really in Other Town", out)

    def test_ids_no_spot_uses_are_listed_then_pruned(self):
        self.run_ids("--pilot", "fixture")
        self.run_ids("--pilot", "fixture", "--pick", "osm:node/2=ID_GRILL_A")
        pins = {**PINS, "EAT1": [p for p in PINS["EAT1"] if p["osm"] != "node/2"]}   # the grill moved
        self.write("data/pins.yaml", pins)
        out, _ = self.run_ids("--pilot", "fixture", "--dry-run")
        self.assertIn("1 kept ids no spot uses any more (its spot moved or was dropped); --prune drops them: "
                      "osm:node/2", out)
        self.assertIn("osm:node/2", self.kept()[1])          # a dry run drops nothing
        out, _ = self.run_ids("--pilot", "fixture", "--prune")
        self.assertIn("dropping osm:node/2, picked by hand", out)   # a person's pick is printed first
        self.assertIn("dropped 1 kept ids", out)
        kept = self.kept()[1]
        self.assertNotIn("osm:node/2", kept)
        self.assertIn("osm:node/1", kept)

    def test_another_pilots_ids_are_not_stale(self):
        kept = {"osm:node/9": {"query": "Far Cafe, Far Town", "verdict": "match", "id": "ID_FAR"}}
        far = {**save("FAR1"), "collections": ["Far Trips"]}
        stale = google_ids.stale_keys(kept, SAVES + [far], TAGS,
                                      {**PINS, "FAR1": [{"name": "Far Cafe", "near": "Far Town", "osm": "node/9"}]}, {})
        self.assertEqual(stale, [])

    def test_pick_needs_a_known_spot(self):
        with self.assertRaises(SystemExit):
            self.run_ids("--pilot", "fixture", "--pick", "osm:node/999=ID_X")

    def test_dry_run_needs_no_key_and_calls_nothing(self):
        os.environ.pop("GOOGLE_MAPS_API_KEY")
        out, _ = self.run_ids("--pilot", "fixture", "--dry-run")
        self.assertEqual(self.calls, [])
        self.assertIn("5 to search, 1 with no box", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "data", "google.yaml")))

    def test_encrypted_key_is_refused(self):
        os.environ["GOOGLE_MAPS_API_KEY"] = "encrypted:abc"
        with self.assertRaises(SystemExit):
            self.run_ids("--pilot", "fixture")

    def test_daily_cap_stops_and_keeps_what_was_found(self):
        def capped(query, pin, half_km, key, on_retry=None):
            if self.calls:
                raise urllib.error.HTTPError("u", 429, "x", {}, io.BytesIO(b"Quota exceeded per day"))
            self.calls.append(query)
            return gp.candidates({"places": ANSWERS.get(query, [])})
        gp.search = capped
        _, err = self.run_ids("--pilot", "fixture")
        self.assertIn("ev=google_cap", err)
        _, kept = self.kept()
        self.assertEqual(len(kept), 1)

    def test_backoff_retries_then_gives_up_on_the_cap(self):
        warnings.simplefilter("ignore", ResourceWarning)   # the made-up errors' bodies are never closed
        waits, tries = [], []

        def flaky():
            tries.append(1)
            if len(tries) < 3:
                raise urllib.error.HTTPError("u", 503, "x", {}, io.BytesIO(b""))
            return "ok"
        self.assertEqual(gp.with_backoff(flaky, sleep=waits.append), "ok")
        self.assertEqual(waits, [1.0, 2.0])

        def cap():
            raise urllib.error.HTTPError("u", 429, "x", {}, io.BytesIO(b"per day"))
        with self.assertRaises(urllib.error.HTTPError):
            gp.with_backoff(cap, sleep=waits.append)
        self.assertEqual(waits, [1.0, 2.0])                  # no wait for a daily cap

    def test_link_opens_the_place(self):
        link = gp.maps_link("Example Tacos, Fixture Town", "ID_TACOS")
        self.assertIn("query=Example+Tacos%2C+Fixture+Town", link)
        self.assertIn("query_place_id=ID_TACOS", link)


if __name__ == "__main__":
    unittest.main()
