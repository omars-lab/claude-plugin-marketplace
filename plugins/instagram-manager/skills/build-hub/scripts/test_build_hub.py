#!/usr/bin/env python3
"""Offline checks for build_hub.py, on an invented data repo in a temp folder. No network.

    python3 skills/build-hub/scripts/test_build_hub.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_hub  # noqa: E402
import yaml  # noqa: E402

TOPICS = {"topics": {"travel": {"label": "Travel"}, "parenting-kids": {"label": "Kids"}}}
COLLECTIONS = {"collections": {"Fixture Trips": {"topics": ["travel"], "cities": ["Fixture State"]}},
               "pilots": {"fixture": {"collections": ["Fixture Trips"], "cities": ["Fixture State"]}}}
PLACES = {
    "places": {
        "Fixture State": {"kind": "state", "lat": 10.0, "lon": 20.0, "map": "https://maps.example/state"},
        "Fixture Town": {"kind": "city", "in": "Fixture State", "lat": 10.5, "lon": 20.5},
        "Fixture Park": {"kind": "park", "in": "Fixture State", "lat": 11.0, "lon": 21.0},
        "Fixture Village": {"kind": "city", "in": "Fixture State"},          # never looked up: no pin
        "Faraway Land": {"kind": "country", "lat": -40.0, "lon": 100.0},
    },
    "aliases": {"The Town": "Fixture Town"},
}


def save(code, caption, collections=(), user="example_creator", saved="2026-01-02T03:04"):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "reel", "caption": caption,
            "hashtags": [], "owner": {"username": user, "name": "Example Person"}, "saved_at": saved,
            "collections": list(collections)}


SAVES = [
    save("TOWN1", "Tacos in Fixture Town today </script><img src=x onerror=alert(1)>", ["Fixture Trips"]),
    save("PARK1", "Hiked the Example Falls trail at sunrise", saved="2026-01-05T00:00"),
    save("PARK2", "Example Falls again, colder this time", user="another_creator"),
    save("STATE1", "A road trip with no towns named", ["Fixture Trips"]),
    save("VILL1", "Quiet weekend", ["Fixture Trips"]),
    save("AWAY1", "Islands of Faraway Land"),
    save("NOTAG", "Nothing tagged yet", ["Fixture Trips"]),
    save("CaseA", "One code", ["Fixture Trips"]),
    save("casea", "Same code but lower case", ["Fixture Trips"]),
    {**save("OLDFMT", "Stored the old way"), "collections": "['Fixture Trips']", "owner": "{'username': 'old_creator'}"},
]
TAGS = {
    "TOWN1": {"topics": ["travel"], "cities": ["Fixture State", "Fixture Town"]},
    "PARK1": {"topics": ["travel", "parenting-kids"], "cities": ["Fixture Park", "Fixture State"]},
    "PARK2": {"topics": ["travel"], "cities": ["Fixture Park", "Fixture State"]},
    "STATE1": {"topics": ["travel"], "cities": ["Fixture State"]},
    "VILL1": {"topics": ["travel"], "cities": ["Fixture State", "Fixture Village"]},
    "AWAY1": {"topics": ["travel"], "cities": ["Faraway Land"]},
}
SPOT = {"name": "Example Falls", "said": "Example Falls trail", "near": "Fixture Park", "kind": "waterfall",
        "lat": 11.1, "lon": 21.1, "osm": "node/101", "wikidata": "Q101"}
PINS = {"PARK1": [SPOT], "PARK2": [{**SPOT, "said": "Example Falls"}]}
MEDIA = {"TOWN1": {"thumb": "TOWN1/thumb.jpg", "kind": "reel"}, "STATE1": {"thumb": "STATE1/thumb.jpg"},
         "PARK1": {"error": "login_wall"}}


class Hub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "home")
        self.media = os.path.join(self.tmp.name, "media")
        for rel, data in (("config/topics.yaml", TOPICS), ("config/collections.yaml", COLLECTIONS),
                          ("data/places.yaml", PLACES), ("data/tags.yaml", TAGS), ("data/pins.yaml", PINS),
                          ("data/media.yaml", MEDIA)):
            self.write(rel, data)
        self.write(".cache/saves.json", {"saves": SAVES})
        os.makedirs(os.path.join(self.media, "TOWN1"))
        with open(os.path.join(self.media, "TOWN1", "thumb.jpg"), "wb") as fh:
            fh.write(b"\xff\xd8 not really a jpeg")
        self.env = {k: os.environ.get(k) for k in ("INSTAGRAM_HOME", "INSTAGRAM_MEDIA_DIR")}
        os.environ["INSTAGRAM_HOME"] = self.root
        os.environ["INSTAGRAM_MEDIA_DIR"] = self.media
        self.out = os.path.join(self.root, ".cache", "hub")

    def tearDown(self):
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
            if rel.endswith(".json"):
                json.dump(data, fh)
            else:
                yaml.safe_dump(data, fh)

    def build(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(build_hub.main(list(argv)), 0)
        return out.getvalue()

    def page(self, rel):
        with open(os.path.join(self.out, rel), encoding="utf-8") as fh:
            return fh.read()

    def data(self):
        """The data the map page carries."""
        m = re.search(r"var D=(\{.*?\}), map", self.page("index.html"), re.S)
        return json.loads(m.group(1))

    def test_pilot_holds_its_collections_and_its_places(self):
        self.build("--pilot", "fixture")
        posts = sorted(os.listdir(os.path.join(self.out, "posts")))
        self.assertIn("PARK1.html", posts)      # outside the collection, tagged with the pilot's place
        self.assertIn("NOTAG.html", posts)      # in the collection, tagged with nothing
        self.assertIn("OLDFMT.html", posts)     # collections stored as text are read back
        self.assertNotIn("AWAY1.html", posts)   # neither
        self.assertNotIn("faraway-land.html", os.listdir(os.path.join(self.out, "places")))
        self.build("--all")
        self.assertIn("AWAY1.html", os.listdir(os.path.join(self.out, "posts")))

    def test_pins_go_on_the_most_exact_place(self):
        self.build("--pilot", "fixture")
        d = self.data()
        names = [p["n"] for p in d["places"]]
        pins = {}
        for lat, lon, post, place, style, home in d["pins"]:
            pins.setdefault(d["posts"][post]["c"], []).append((names[place], style, home))
        self.assertEqual(pins["TOWN1"], [("Fixture Town", "area", 1)])         # the town, not the state
        self.assertEqual(pins["STATE1"], [("Fixture State", "wide", 1)])       # only the state: its middle
        self.assertEqual(pins["PARK1"], [("Example Falls", "spot", 1)])        # the spot replaces the park
        self.assertEqual(pins["VILL1"], [("Fixture State", "wide", 1)])        # no pin for the village: go up
        self.assertNotIn("NOTAG", pins)

    def test_a_cafe_openstreetmap_does_not_list_is_pinned_at_its_town_and_searched_by_name(self):
        self.write("data/tags.yaml", {**TAGS, "TOWN1": {**TAGS["TOWN1"], "purposes": ["eat"]}})
        self.write("data/pins-review.yaml", {
            "TOWN1": [{"said": "@examplecafe", "name": "Example Cafe", "asked": "Example Cafe", "near": "Fixture Town",
                       "why": "not found near Fixture Town"},
                      # a doubtful match: its name and lat/lon are the other place's, so neither is used
                      {"said": "Example Bakery", "asked": "Example Bakery", "near": "Fixture Town",
                       "why": "found Example Baguette, a different name", "name": "Example Baguette",
                       "lat": 50.0, "lon": 50.0},
                      {"said": "Gone Diner", "near": "Fixture Town", "why": "not found near Fixture Town", "drop": True},
                      {"said": "Made Up", "near": "Fixture Town", "why": "quote not in caption"}]})
        out = self.build("--pilot", "fixture")
        d = self.data()
        names = [p["n"] for p in d["places"]]
        town1 = [(names[pl], style, lat, lon) for lat, lon, post, pl, style, _ in d["pins"]
                 if d["posts"][post]["c"] == "TOWN1"]
        self.assertEqual(town1, [("Example Cafe", "placed", 10.5, 20.5),         # at the town, not the town itself
                                 ("Example Bakery", "placed", 10.5, 20.5)])
        cafe = self.page("places/example-cafe.html")
        self.assertIn("google.com/maps/search/?api=1&amp;query=Example+Cafe%2C+Fixture+Town", cafe)
        self.assertIn("OpenStreetMap does not list it", cafe)
        self.assertNotIn("Example Baguette", self.page("posts/TOWN1.html"))
        self.assertIn("eat or stay posts: 0 open a spot OpenStreetMap placed, 1 one it doesn't list", out)

    def test_spot_page_groups_posts_by_osm_id_and_marks_the_words(self):
        self.build("--pilot", "fixture")
        spot = self.page("places/example-falls.html")
        self.assertIn("../posts/PARK1.html", spot)
        self.assertIn("../posts/PARK2.html", spot)
        self.assertIn("<mark>Example Falls trail</mark>", spot)
        self.assertIn('href="../places/fixture-park.html"', spot)       # up to the area it sits in
        self.assertIn("https://www.openstreetmap.org/node/101", spot)
        self.assertIn("https://www.wikidata.org/wiki/Q101", spot)
        park = self.page("places/fixture-park.html")
        self.assertIn('href="../places/example-falls.html"', park)      # down to the spot

    def test_place_pages_link_up_and_down(self):
        self.build("--pilot", "fixture")
        state = self.page("places/fixture-state.html")
        for slug in ("fixture-town", "fixture-park", "fixture-village"):
            self.assertIn(f'href="../places/{slug}.html"', state)
        self.assertIn("https://maps.example/state", state)
        self.assertIn("not looked up yet", self.page("places/fixture-village.html"))
        town = self.page("places/fixture-town.html")
        self.assertIn('href="../places/fixture-state.html"', town)
        self.assertIn("<mark>Fixture Town</mark>", town)
        self.assertIn("google.com/maps/search/?api=1&amp;query=Fixture+Town%2C+Fixture+State", town)

    def test_post_page_names_every_place(self):
        self.build("--pilot", "fixture")
        post = self.page("posts/PARK1.html")
        for slug in ("example-falls", "fixture-park", "fixture-state"):
            self.assertIn(f'href="../places/{slug}.html"', post)
        self.assertIn("Kids", post)
        self.assertIn("https://www.instagram.com/p/PARK1/", post)
        self.assertIn("5 Jan 2026", post)

    def test_thumbnails_are_copied_when_present(self):
        self.build("--pilot", "fixture")
        self.assertEqual(os.listdir(os.path.join(self.out, "thumbs")), ["TOWN1.jpg"])
        self.assertIn('src="../thumbs/TOWN1.jpg"', self.page("posts/TOWN1.html"))
        self.assertIn('class="post solo"', self.page("posts/STATE1.html"))   # no thumbnail: one column
        thumbs = {p["c"]: p["th"] for p in self.data()["posts"]}
        self.assertEqual(thumbs["TOWN1"], "thumbs/TOWN1.jpg")
        self.assertIsNone(thumbs["STATE1"])     # listed, but the file is not there

    def test_builds_without_pins_or_media(self):
        os.remove(os.path.join(self.root, "data", "pins.yaml"))
        os.remove(os.path.join(self.root, "data", "media.yaml"))
        self.build("--pilot", "fixture")
        self.assertFalse(os.path.exists(os.path.join(self.out, "places", "example-falls.html")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "thumbs")))
        self.assertIn('class="thumb ph"', self.page("places/fixture-town.html"))

    def test_keeps_other_pages_and_clears_old_ones(self):
        os.makedirs(os.path.join(self.out, "places"))
        for rel in ("moves.html", "places/gone-place.html"):
            with open(os.path.join(self.out, rel), "w") as fh:
                fh.write("x")
        self.build("--pilot", "fixture")
        self.assertTrue(os.path.exists(os.path.join(self.out, "moves.html")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "places", "gone-place.html")))
        self.assertIn('href="moves.html"', self.page("index.html"))

    def test_captions_cannot_break_the_page(self):
        self.build("--pilot", "fixture")
        index = self.page("index.html")
        self.assertNotIn("</script><img", index)
        self.assertNotIn("<img src=x", self.page("posts/TOWN1.html"))
        self.assertIn("&lt;/script&gt;", self.page("posts/TOWN1.html"))

    def test_codes_that_differ_by_case_get_their_own_files(self):
        self.build("--pilot", "fixture")
        posts = os.listdir(os.path.join(self.out, "posts"))
        self.assertIn("CaseA.html", posts)
        self.assertIn("casea-2.html", posts)

    def test_menus_sort_by_posts_and_tell_each_post_its_options(self):
        places = {"places": {**PLACES["places"],
                             # the name OpenStreetMap found says National Park; the tagged name does not
                             "Fixture Park": {**PLACES["places"]["Fixture Park"],
                                              "found": "Fixture National Park, Fixture State"},
                             "Other National Park": {"kind": "park", "in": "Fixture State", "lat": 12.0, "lon": 22.0},
                             "Other State Park": {"kind": "park", "in": "Fixture State", "lat": 12.5, "lon": 22.5}},
                  "aliases": PLACES["aliases"]}
        tags = {**TAGS, "STATE1": {"topics": ["travel"], "cities": ["Other National Park", "Other State Park"]},
                "TOWN1": {**TAGS["TOWN1"], "purposes": ["eat", "not-a-purpose"]}}
        self.write("data/places.yaml", places)
        self.write("data/tags.yaml", tags)
        self.build("--pilot", "fixture")
        d = self.data()
        menus = {m["k"]: m for m in d["facets"]}
        self.assertEqual([o[1:] for o in menus["np"]["o"]],
                         [["Fixture Park", 2], ["Other National Park", 1]])   # most posts first; no state park
        self.assertEqual(menus["st"]["o"][0][:2], ["fixture-state", "Fixture State"])
        pu = menus["pu"]
        self.assertEqual(pu["o"][pu["none"]][1], "Not worked out yet")
        self.assertEqual(pu["none"], len(pu["o"]) - 1)                         # always last
        posts = {p["c"]: p for p in d["posts"]}

        def opts(code, key):
            return sorted(menus[key]["o"][j][1] for j in posts[code]["g"][key])
        self.assertEqual(opts("PARK1", "np"), ["Fixture Park"])
        self.assertEqual(opts("PARK1", "pu"), ["Adventure & outdoors"])         # a waterfall in a park
        self.assertEqual(opts("TOWN1", "pu"), ["Eat & drink"])                  # from the tagger; unknown dropped
        self.assertEqual(opts("VILL1", "pu"), ["Not worked out yet"])           # only a village
        self.assertEqual(opts("PARK1", "tp"), ["Kids", "Travel"])
        self.assertEqual(opts("NOTAG", "st"), [])
        inside = {pl["n"]: [menus["np"]["o"][j][1] for j in pl["g"]["np"]] for pl in d["places"]}
        self.assertEqual(inside["Example Falls"], ["Fixture Park"])             # a spot sits in its park
        self.assertEqual(inside["Fixture Town"], [])
        self.assertTrue(all(p["m"] for p in d["places"]))                      # every pin's Google Maps link
        self.assertIn("Open in Google Maps", self.page("posts/TOWN1.html"))    # names one place: a button

    def test_unknown_pilot_stops(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            build_hub.main(["--pilot", "nowhere"])

    def test_excerpt_marks_whole_words_only(self):
        text, found = build_hub.excerpt("Fixture Townsend is not Fixture Town", ["Fixture Town"])
        self.assertTrue(found)
        self.assertIn("is not <mark>Fixture Town</mark>", text)
        text, found = build_hub.excerpt("nothing here", ["Fixture Town"])
        self.assertEqual((text, found), ("nothing here", False))


if __name__ == "__main__":
    unittest.main(verbosity=1)
