#!/usr/bin/env python3
"""Offline checks for overture_positions.py, on an invented data repo. No network: Overture's rows
are made up and handed straight to the matcher, and a full run reads a box already in the cache.

    python3 skills/resolve-post-location/scripts/test_overture_positions.py

Every code, handle, name and place here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overture_positions as op  # noqa: E402
import resolve_post_location as rpl  # noqa: E402
import yaml  # noqa: E402

TOWN = {"name": "Fixture Town", "kind": "city", "lat": 40.0, "lon": -120.0}
PARK = {"name": "Fixture Park", "kind": "park", "lat": 40.0, "lon": -120.0}


def row(name, lat=40.001, lon=-120.001, **kw):
    out = {"id": "row-" + name.lower().replace(" ", "-"), "name": name, "basic": "restaurant",
           "hierarchy": ["food_and_drink", "restaurant"], "status": None, "street": "12 Example St",
           "town": "Fixture Town", "websites": None, "socials": None, "datasets": ["meta", "Overture"],
           "licences": ["CDLA-Permissive-2.0", "CDLA-Permissive-2.0"], "lat": lat, "lon": lon}
    out.update(kw)
    return out


def spot(name, said=None, address=None):
    return {"name": name, "said": said or name, "address": address}


class Reach:
    def ok(self, lat, lon):
        return rpl.km_between(40.0, -120.0, lat, lon) <= 25


def judge(s, rows, area=TOWN, caption="Lunch was great"):
    return op.judge(s, rows, area, Reach(), caption)


class Match(unittest.TestCase):
    def test_name_handle_website_and_looser(self):
        self.assertEqual(op.matches(row("Example Diner"), "Example Diner", "Example Diner", "Fixture Town"), "name")
        # business kinds and the area's own words don't count
        self.assertEqual(op.matches(row("Example Restaurant and Bar"), "Example FT", "@example_ft", "Fixture Town"),
                         "name")
        self.assertEqual(op.matches(row("Something Else", socials=["https://www.instagram.com/example_ft"]),
                                    "Example FT", "@example_ft", "Fixture Town"), "handle")
        self.assertEqual(op.matches(row("Something Else", websites=["https://www.examplediner.com/menu"]),
                                    "Example Diner", "@examplediner", "Fixture Town"), "handle")
        self.assertEqual(op.matches(row("Example Fish"), "Example Fish N Chips", "Example Fish N Chips",
                                    "Fixture Town"), "close")
        self.assertIsNone(op.matches(row("Other Bakery"), "Example Diner", "Example Diner", "Fixture Town"))
        # one word left on both sides, but the names start differently: another place
        self.assertEqual(op.matches(row("Tacos Example"), "Examples Tacos FT", "@examplestacos", "Fixture Town"),
                         "close")
        self.assertEqual(op.matches(row("The Example Cafe"), "Example Cafe", "Example Cafe", "Fixture Town"), "name")


class Rule(unittest.TestCase):
    def test_passes(self):
        best, why = judge(spot("Example Diner"), [row("Example Diner")])
        self.assertIsNone(why)
        self.assertEqual(best["name"], "Example Diner")

    def test_each_rule_holds(self):
        cases = [
            ([row("Other Place")], {}, "no row by that name"),
            ([row("Example Fish")], {"name": "Example Fish N Chips"}, "only a looser name"),
            ([row("Example Diner"), row("Example Diner", lat=40.02)], {}, "branches"),
            ([row("Example Diner", basic="hair_salon", hierarchy=["lifestyle_services"])], {}, "not a food"),
            ([row("Example Diner", street=None)], {}, "no street address"),
            ([row("Example Diner", town="Other Town")], {}, "the row's town is Other Town"),
            ([row("Example Diner"), row("Next Door", lat=40.01)], {}, "from the other rows at its address"),
            ([row("Example Diner")] + [row(f"Pile {i}", street=f"{i} Other St") for i in range(5)], {},
             "other rows on the same point"),
            ([row("Example Diner")], {"address": "99 Example St"}, "not at the caption's address"),
        ]
        for rows, change, want in cases:
            s = {**spot("Example Diner"), **change}
            with self.subTest(want=want):
                self.assertIn(want, judge(s, rows)[1] or "PIN")

    def test_a_closed_row_is_not_a_match(self):
        self.assertIn("only a looser name", judge(spot("Example Diner"), [row("Example Diner", status="closed")])[1])

    def test_the_caption_warns(self):
        for caption in ("Their new spot downtown", "Now open!", "a pop-up this weekend", "inside the food hall",
                        "the coolest design hotels", "the biggest grocery store"):
            with self.subTest(caption=caption):
                self.assertIn("the caption says", judge(spot("Example Diner"), [row("Example Diner")],
                                                        caption=caption)[1])

    def test_a_park_has_no_town_to_compare(self):
        self.assertIn("not a town", judge(spot("Example Diner"), [row("Example Diner")], area=PARK)[1])

    def test_the_caption_address_agrees(self):
        self.assertIsNone(judge(spot("Example Diner", address="12 Example Street"), [row("Example Diner")])[1])


class Pin(unittest.TestCase):
    def test_fields(self):
        entry = {"said": "@examplediner", "near": "Fixture Town", "why": "not found near Fixture Town",
                 "asked": "Example Diner"}
        r = row("Example Diner", datasets=["Foursquare", "Overture"], licences=["Apache-2.0", "CDLA-Permissive-2.0"])
        pin = op.pin_for(spot("Example Diner", "@examplediner"), entry, r, TOWN, "2099-01-01.0")
        self.assertEqual(pin["by"], "overture")
        self.assertEqual(pin["overture"], "row-example-diner")
        self.assertEqual(pin["overture_release"], "2099-01-01.0")
        self.assertEqual(pin["licence"], "Apache-2.0, CDLA-Permissive-2.0")
        self.assertEqual(pin["found"], "Example Diner, 12 Example St, Fixture Town")
        self.assertEqual((pin["name"], pin["kind"], pin["asked"]), ("Example Diner", "restaurant", "Example Diner"))
        self.assertNotIn("why", pin)

    def test_a_reread_keeps_it(self):
        self.assertTrue(rpl.kept({"by": "overture"}))
        self.assertTrue(rpl.kept({"by": "hand"}))
        self.assertFalse(rpl.kept({"osm": "node/1"}))


class FakeCon:
    """Answers fetch()'s read of a cached box, and nothing else."""

    def __init__(self, rows):
        self.rows = rows
        self.description = [(k,) for k in rows[0]]

    def execute(self, sql):
        assert sql.startswith("SELECT * FROM read_parquet("), sql
        return self

    def fetchall(self):
        return [tuple(r.values()) for r in self.rows]


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        os.environ["INSTAGRAM_HOME"] = self.home
        os.makedirs(os.path.join(self.home, "data"))
        os.makedirs(os.path.join(self.home, "config"))
        os.makedirs(os.path.join(self.home, ".cache"))
        self.write("config/collections.yaml", {"pilots": {"fixture": {"cities": ["Fixture Town"]}}})
        self.write("data/places.yaml", {"places": {"Fixture Town": {"kind": "city", "lat": 40.0, "lon": -120.0}}})
        self.write("data/tags.yaml", {"AAA": {"cities": ["Fixture Town"]}, "BBB": {"cities": ["Fixture Town"]}})
        self.write("data/pins.yaml", {})
        self.write("data/pins-review.yaml", {
            "AAA": [{"said": "@examplediner", "near": "Fixture Town", "why": "not found near Fixture Town",
                     "asked": "Example Diner", "name": "Example Diner"}],
            "BBB": [{"said": "Made Up Spot", "near": "Fixture Town", "why": "not found near Fixture Town",
                     "asked": "Made Up Spot"}]})
        with open(os.path.join(self.home, ".cache", "saves.json"), "w") as fh:
            json.dump({"saves": [{"code": "AAA", "caption": "Dinner at @examplediner"},
                                 {"code": "BBB", "caption": "Made Up Spot was fun"}]}, fh)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "INSTAGRAM_HOME", None)

    def write(self, rel, data):
        with open(os.path.join(self.home, rel), "w") as fh:
            yaml.safe_dump(data, fh)

    def read(self, rel):
        with open(os.path.join(self.home, rel)) as fh:
            return yaml.safe_load(fh) or {}

    def go(self, *argv):
        con = FakeCon([row("Example Diner")])
        box = rpl.box_around(40.0, -120.0, rpl.TOWN_KM)
        path = op.box_path("2099-01-01.0", "Fixture Town", box)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()   # in the cache, so nothing is fetched
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = op.main(["--pilot", "fixture", "--release", "2099-01-01.0", *argv], con=con)
        return code, out.getvalue()

    def test_dry_run_writes_nothing(self):
        code, out = self.go("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("2 spots not found on OpenStreetMap; 1 pass every rule (dry run", out)
        self.assertEqual(self.read("data/pins.yaml"), {})

    def test_run_moves_the_pin(self):
        self.go()
        pins, review = self.read("data/pins.yaml"), self.read("data/pins-review.yaml")
        self.assertEqual(pins["AAA"][0]["by"], "overture")
        self.assertNotIn("AAA", review)
        self.assertEqual(review["BBB"][0]["said"], "Made Up Spot")
        self.go()   # a second run finds nothing new
        self.assertEqual(len(self.read("data/pins.yaml")["AAA"]), 1)


if __name__ == "__main__":
    unittest.main()
