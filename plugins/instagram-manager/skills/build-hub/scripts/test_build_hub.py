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
                      {"said": "Example Deli", "near": "Fixture Town", "why": "not found near Fixture Town",
                       "asked": "Example Deli", "address": "1 Example Rd"},
                      {"said": "Gone Diner", "near": "Fixture Town", "why": "not found near Fixture Town", "drop": True},
                      {"said": "Made Up", "near": "Fixture Town", "why": "quote not in caption"}]})
        out = self.build("--pilot", "fixture")
        d = self.data()
        names = [p["n"] for p in d["places"]]
        town1 = [(names[pl], style, lat, lon) for lat, lon, post, pl, style, _ in d["pins"]
                 if d["posts"][post]["c"] == "TOWN1"]
        self.assertEqual(town1, [("Example Cafe", "placed", 10.5, 20.5),         # at the town, not the town itself
                                 ("Example Bakery", "placed", 10.5, 20.5),
                                 ("Example Deli", "placed", 10.5, 20.5)])
        cafe = self.page("places/example-cafe.html")
        self.assertIn("google.com/maps/search/?api=1&amp;query=Example+Cafe%2C+Fixture+Town", cafe)
        self.assertIn("OpenStreetMap does not list it", cafe)
        self.assertIn("query=Example+Deli%2C+1+Example+Rd", self.page("places/example-deli.html"))
        self.assertNotIn("Example Baguette", self.page("posts/TOWN1.html"))
        self.assertIn("eat or stay posts: 0 open a spot OpenStreetMap placed, 1 one it doesn't list", out)

    def test_a_spot_found_only_as_its_street_is_shown_at_its_town(self):
        self.write("data/pins-review.yaml", {
            "TOWN1": [{"said": "@examplegrill", "name": "Example Grill", "near": "Fixture Town",
                       "address": "12 Long Rd", "why": "only the street was found near Fixture Town, not the house",
                       "street_tried": True},
                      {"said": "Example Wok", "name": "Example Wok", "near": "Fixture Town", "address": "30 Other Rd",
                       "why": "found Example Wok by name, but not at the caption's address", "address_tried": True}]})
        self.build("--pilot", "fixture")
        d = self.data()
        names = [p["n"] for p in d["places"]]
        town1 = [(names[pl], style) for _, _, post, pl, style, _ in d["pins"] if d["posts"][post]["c"] == "TOWN1"]
        self.assertEqual(town1, [("Example Grill", "placed"), ("Example Wok", "placed")])
        grill = self.page("places/example-grill.html")
        self.assertIn("query=Example+Grill%2C+12+Long+Rd", grill)
        self.assertIn("OpenStreetMap found only its street", grill)
        wok = self.page("places/example-wok.html")
        self.assertIn("query=Example+Wok%2C+30+Other+Rd", wok)
        self.assertIn("found one by that name elsewhere, not at the caption&#x27;s address", wok)

    def test_a_kept_google_id_opens_that_exact_place(self):
        self.write("data/pins-review.yaml", {
            "TOWN1": [{"said": "Example Deli", "near": "Fixture Town", "why": "not found near Fixture Town",
                       "asked": "Example Deli", "address": "1 Example Rd"}]})
        self.write("data/google.yaml", {
            "osm:node/101": {"query": "Example Falls, Fixture Park", "verdict": "match", "id": "ChIJexampleFalls",
                             "by": "auto", "date": "2026-01-02"},
            "spot:example-deli@fixture-town": {"query": "Example Deli, 1 Example Rd", "verdict": "match",
                                               "id": "ChIJexampleDeli", "by": "hand", "date": "2026-01-02"}})
        self.build("--pilot", "fixture")
        falls = self.page("places/example-falls.html")
        self.assertIn("query_place_id=ChIJexampleFalls", falls)
        self.assertIn("matched by its name: check it", falls)           # chosen by the script, not a person
        deli = self.page("places/example-deli.html")
        self.assertIn("query_place_id=ChIJexampleDeli", deli)
        self.assertNotIn("matched by its name", deli)                   # a person chose it
        self.assertIn("query_place_id=ChIJexampleFalls", json.dumps(self.data()))   # the map's link too

    def test_a_google_id_found_at_the_captions_address_says_so(self):
        self.write("data/pins-review.yaml", {
            "TOWN1": [{"said": "Example Deli", "near": "Fixture Town", "why": "not found near Fixture Town",
                       "asked": "Example Deli", "address": "1 Example Rd"}]})
        self.write("data/google.yaml", {
            "spot:example-deli@fixture-town": {"query": "Example Deli, 1 Example Rd", "verdict": "match",
                                               "id": "ChIJexampleDeli", "by": "auto", "at_address": True,
                                               "date": "2026-01-02"}})
        self.build("--pilot", "fixture")
        deli = self.page("places/example-deli.html")
        self.assertIn("query_place_id=ChIJexampleDeli", deli)
        self.assertIn("its name and the caption's address both match", deli)
        self.assertNotIn("check it", deli)
        self.assertIn("the Google Maps link opens the place itself", deli)   # not "searches for it by name"
        self.assertNotIn("searches for it by name", deli)
        self.assertIn('"Example Deli","","placed"]', deli)        # its small map draws the at-the-town ring

    def test_a_chain_keeps_its_search_link_for_every_branch(self):
        self.write("data/pins-review.yaml", {
            "TOWN1": [{"said": "Example Deli", "near": "Fixture Town", "why": "not found near Fixture Town",
                       "asked": "Example Deli", "address": "1 Example Rd"}]})
        self.write("data/google.yaml", {
            "spot:example-deli@fixture-town": {"query": "Example Deli, 1 Example Rd", "verdict": "chain",
                                               "by": "hand", "date": "2026-01-02"}})
        self.build("--pilot", "fixture")
        deli = self.page("places/example-deli.html")
        self.assertIn("query=Example+Deli%2C+1+Example+Rd", deli)        # a search: every branch shows
        self.assertNotIn("query_place_id", deli)
        self.assertIn("a chain: every branch near Fixture Town, any will do", deli)

    def test_one_place_under_several_names_gets_one_page(self):
        found = "Example Roastery, 5, Long Road, Fixture Town, Fixture State"
        at = {"near": "Fixture Town", "lat": 10.51, "lon": 20.51, "kind": "address", "found": found}
        mall = "Example Mall, 9, Mall Road, Fixture Town, Fixture State"
        self.write("data/pins.yaml", {**PINS,
            "TOWN1": [{**at, "name": "Example Roastery", "kind": "cafe", "osm": "node/202"},
                      {"name": "Ice Shop", "near": "Fixture Town", "lat": 10.52, "lon": 20.52, "found": mall},
                      {"name": "Tea Shop", "near": "Fixture Town", "lat": 10.52, "lon": 20.52, "found": mall}],
            "STATE1": [{**at, "name": "Example Roastery USA"}],
            "VILL1": [{**at, "name": "Example Roastery Uptown"}]})
        self.write("data/pins-review.yaml", {
            "STATE1": [{"said": "@examplecafe.tx", "name": "Example Cafe TX", "asked": "Example Cafe TX", "near": "Fixture Town",
                        "why": "not found near Fixture Town"}],
            "VILL1": [{"said": "@examplecafefixturetown", "name": "Examplecafe Fixture Town", "asked": "Examplecafe Fixture Town",
                       "near": "Fixture Town", "why": "not found near Fixture Town"}]})
        self.build("--pilot", "fixture")
        slugs = os.listdir(os.path.join(self.out, "places"))
        roastery = [s for s in slugs if s.startswith("example-roastery")]
        self.assertEqual(roastery, ["example-roastery.html"])       # its own name and two longer ones
        page = self.page("places/example-roastery.html")
        for code in ("TOWN1", "STATE1", "VILL1"):
            self.assertIn(f"../posts/{code}.html", page)
        cafe = [s for s in slugs if s.startswith("example") and "cafe" in s]
        self.assertEqual(len(cafe), 1, cafe)                       # two handles, one cafe
        self.assertIn("../posts/VILL1.html", self.page(f"places/{cafe[0]}"))
        self.assertIn("../posts/STATE1.html", self.page(f"places/{cafe[0]}"))
        self.assertIn("ice-shop.html", slugs)                      # two shops at one mall stay two
        self.assertIn("tea-shop.html", slugs)

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

    def test_a_reel_saved_only_as_a_video_shows_its_cover(self):
        self.write("data/media.yaml", {**MEDIA, "STATE1": {"cover": "STATE1/cover.jpg", "video": "STATE1/video.mp4"}})
        os.makedirs(os.path.join(self.media, "STATE1"))
        with open(os.path.join(self.media, "STATE1", "cover.jpg"), "wb") as fh:
            fh.write(b"\xff\xd8 not really a jpeg")
        self.build("--pilot", "fixture", "--no-previews")
        self.assertIn('src="../thumbs/STATE1.jpg"', self.page("posts/STATE1.html"))
        self.assertEqual({p["c"]: p["th"] for p in self.data()["posts"]}["STATE1"], "thumbs/STATE1.jpg")

    def test_a_spot_with_a_still_shows_it_instead_of_the_cover(self):
        rows = {"PARK1": [{"name": "Example Falls", "said": "Example Falls trail", "frame": 2, "t": 67.3,
                           "how": "on_screen", "still": "PARK1/spots/still-example-falls.jpg",
                           "clip": "PARK1/spots/clip-example-falls.webp"}],
                # listed, but its files were never cut: the post keeps its cover
                "PARK2": [{"name": "Example Falls", "said": "Example Falls", "frame": 1, "t": 0.0, "how": "on_screen",
                           "still": "PARK2/spots/still-example-falls.jpg", "clip": "PARK2/spots/clip-example-falls.webp"}]}
        self.write("data/stills.yaml", rows)
        os.makedirs(os.path.join(self.media, "PARK1", "spots"))
        for f in ("still-example-falls.jpg", "clip-example-falls.webp"):
            with open(os.path.join(self.media, "PARK1", "spots", f), "wb") as fh:
                fh.write(b"not really an image")
        self.assertIn("1 spot stills", self.build("--pilot", "fixture"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "stills", "PARK1"))),
                         ["clip-example-falls.webp", "still-example-falls.jpg"])
        self.assertFalse(os.path.exists(os.path.join(self.out, "stills", "PARK2")))

        spot = self.page("places/example-falls.html")
        self.assertIn('src="../stills/PARK1/still-example-falls.jpg" data-clip="../stills/PARK1/clip-example-falls.webp"',
                      spot)
        self.assertIn('alt="Example Falls, 1:07 into the reel"', spot)
        self.assertIn('class="thumb ph"', spot)          # PARK2's card: no still, no cover
        self.assertIn("img[data-clip]", spot)            # the hover script is on the page

        post = self.page("posts/PARK1.html")
        self.assertIn("The places in the video (1)", post)
        self.assertIn("1:07 · from @example_creator's reel", post)
        self.assertIn('<button class="play" type="button" aria-pressed="false">Play 3 s</button>', post)
        self.assertNotIn("The places in the video", self.page("posts/PARK2.html"))
        self.assertNotIn("img[data-clip]", self.page("posts/PARK2.html"))

        d = self.data()
        posts = {p["c"]: p for p in d["posts"]}
        falls = next(i for i, pl in enumerate(d["places"]) if pl["n"] == "Example Falls")
        self.assertEqual(posts["PARK1"]["sp"], {str(falls): "stills/PARK1/still-example-falls.jpg"})   # the map popup
        self.assertNotIn("sp", posts["PARK2"])

    def test_spots_shown_by_their_area_share_one_picture(self):
        pool = {"name": "Example Pool", "said": "the pool", "near": "Fixture Park", "lat": 11.2, "lon": 21.2}
        cafe = {"name": "Example Cafe", "said": "a cafe", "near": "Fixture Town", "lat": 10.6, "lon": 20.6}
        self.write("data/pins.yaml", {**PINS, "PARK1": [SPOT, pool, cafe]})
        park = {"frame": 2, "t": 2.0, "how": "area", "area": "Fixture Park",
                "still": "PARK1/spots/still-area-fixture-park.jpg", "clip": "PARK1/spots/clip-area-fixture-park.webp"}
        town = {"frame": 3, "t": 5.0, "how": "area", "area": "The Town",   # an alias: the hub resolves it
                "still": "PARK1/spots/still-area-the-town.jpg", "clip": "PARK1/spots/clip-area-the-town.webp"}
        self.write("data/stills.yaml", {"PARK1": [{"name": "Example Falls", "said": "Example Falls trail", **park},
                                                  {"name": "Example Pool", "said": "the pool", **park},
                                                  {"name": "Example Cafe", "said": "a cafe", **town}]})
        os.makedirs(os.path.join(self.media, "PARK1", "spots"))
        for f in ("still-area-fixture-park.jpg", "clip-area-fixture-park.webp", "still-area-the-town.jpg",
                  "clip-area-the-town.webp"):
            with open(os.path.join(self.media, "PARK1", "spots", f), "wb") as fh:
                fh.write(b"not really an image")
        self.build("--pilot", "fixture")
        post = self.page("posts/PARK1.html")
        self.assertIn("The places in the video (2)", post)   # two pictures for three spots
        self.assertIn("or, for spots the video doesn't name, the moment their area is", post)
        self.assertIn('alt="The Fixture Park part of the reel, 0:02 into the reel"', post)
        self.assertIn('Spots here: <a href="../places/example-falls.html">Example Falls</a>, '
                      '<a href="../places/example-pool.html">Example Pool</a>', post)
        self.assertIn('<figcaption><a href="../places/fixture-town.html">Fixture Town</a>', post)
        self.assertIn('Spot here: <a href="../places/example-cafe.html">Example Cafe</a>', post)
        self.assertIn('src="../stills/PARK1/still-area-fixture-park.jpg"', self.page("places/example-pool.html"))

    def test_post_lists_show_a_small_picture_and_a_flipbook(self):
        asked = {}

        def fake(codes, out, redo=False, names=None):   # previews.py has its own tests; here only the pages
            asked.update(out=out, names=names)
            return {c: {"poster": names[c] + ".jpg", "anim": names[c] + ".webp" if c == "TOWN1" else None}
                    if c in ("TOWN1", "STATE1") else {"poster": None, "anim": None} for c in codes}

        real, build_hub.previews.make_all = build_hub.previews.make_all, fake
        try:
            self.assertIn("2 small pictures, 1 with a flipbook", self.build("--pilot", "fixture"))
        finally:
            build_hub.previews.make_all = real
        self.assertEqual(asked["out"], os.path.join(self.out, "previews"))
        self.assertEqual(asked["names"]["casea"], "casea-2")      # named as the post pages are

        town = self.page("places/fixture-town.html")
        self.assertIn('src="../previews/TOWN1.jpg" data-poster="../previews/TOWN1.jpg" '
                      'data-anim="../previews/TOWN1.webp"', town)
        self.assertIn("window.flipbooks", town)                    # the player is on the page
        self.assertIn(f"MAX={build_hub.previews.MAX_PLAYING},", town)
        self.assertIn('src="../thumbs/TOWN1.jpg"', self.page("posts/TOWN1.html"))   # the post page keeps the cover

        state = self.page("places/fixture-state.html")
        self.assertIn('src="../previews/STATE1.jpg" data-poster="../previews/STATE1.jpg" alt=""', state)
        posts = {p["c"]: p for p in self.data()["posts"]}
        self.assertEqual((posts["TOWN1"]["pv"], posts["TOWN1"]["pa"]), ("previews/TOWN1.jpg", "previews/TOWN1.webp"))
        self.assertNotIn("pa", posts["STATE1"])
        self.assertNotIn("pv", posts["PARK1"])
        index = self.page("index.html")
        self.assertLess(index.index("window.flipbooks=function"), index.index("var D="))   # ready before the list

    def test_no_previews_leaves_them_out(self):
        called = []
        real, build_hub.previews.make_all = build_hub.previews.make_all, lambda *a, **k: called.append(1)
        try:
            self.build("--pilot", "fixture", "--no-previews")
        finally:
            build_hub.previews.make_all = real
        self.assertEqual(called, [])
        self.assertNotIn("data-poster", self.page("places/fixture-town.html"))
        self.assertNotIn("window.flipbooks=function", self.page("index.html"))

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
                             "Other State Park": {"kind": "park", "in": "Fixture State", "lat": 12.5, "lon": 22.5},
                             "Faraway Port": {"kind": "city", "in": "Faraway Land", "lat": -40.5, "lon": 100.5}},
                  "aliases": PLACES["aliases"]}
        tags = {**TAGS, "STATE1": {"topics": ["travel"], "cities": ["Other National Park", "Other State Park"]},
                "CaseA": {"topics": ["travel"], "cities": ["Faraway Port"]},
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
        self.assertEqual(menus["st"]["n"], "State or country")
        self.assertEqual(opts("STATE1", "st"), ["Fixture State"])               # only its parks: their state
        self.assertEqual(opts("CaseA", "st"), ["Faraway Land"])                 # a town abroad: its country
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
