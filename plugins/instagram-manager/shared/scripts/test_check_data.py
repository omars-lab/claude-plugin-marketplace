#!/usr/bin/env python3
"""Offline tests for check_data.py: two different spots on one map point, and split-saves' items and their files."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_data import item_problems, shared_spots  # noqa: E402
import items_store  # noqa: E402


def spot(name, lat=10.0, lon=20.0, osm=None, found=None, **kw):
    return {"name": name, "lat": lat, "lon": lon, "osm": osm, "found": found or f"{name}, Example Town", **kw}


class SharedSpots(unittest.TestCase):
    def test_two_different_spots_on_one_point_are_caught(self):
        pins = {"A1": [spot("Example Grill")], "B2": [spot("Sample Noodles")]}
        self.assertEqual([names for _, names in shared_spots(pins)], [["Example Grill", "Sample Noodles"]])

    def test_the_same_openstreetmap_thing_counts_even_a_little_apart(self):
        pins = {"A1": [spot("Example Grill", osm="node/1")],
                "B2": [spot("Sample Noodles", lat=10.001, osm="node/1", found="Example Grill, Example Town")]}
        self.assertEqual(len(shared_spots(pins)), 1)

    def test_names_starting_with_the_found_name_are_one_place(self):
        found = "Example Roastery, 1, Example Street"
        pins = {"A1": [spot("Example Roastery USA", found=found)], "B2": [spot("Example Roastery Uptown", found=found)]}
        self.assertEqual(shared_spots(pins), [])

    def test_names_given_one_overture_row_are_one_place(self):
        found = "Example Wings Uptown, 1, Example Street"
        pins = {"A1": [spot("Example Wings", found=found, overture="row-1"),
                       spot("Example Wings Uptown", found=found, overture="row-1")],
                "B2": [spot("Sample Noodles", overture="row-2")]}
        self.assertEqual([names for _, names in shared_spots(pins)], [["Example Wings", "Sample Noodles"]])
        # and the place an OpenStreetMap pin found there, under a caption's spelling
        pins = {"A1": [spot("Example Wings", found=found, overture="row-1")],
                "B2": [spot("Example Wings Uptown", osm="node/1", found=found)]}
        self.assertEqual(shared_spots(pins), [])
        # a row an agent picked counts only for names that start like the row's
        hall = "Example Food Hall, 1, Example Street"
        pins = {"A1": [spot("Example Grill", found=hall, overture="row-1", checked="agent")],
                "B2": [spot("Sample Noodles", found=hall, overture="row-1", checked="agent")]}
        self.assertEqual(len(shared_spots(pins)), 1)
        cafe = "Example Cafe, 1, Example Street"
        pins = {"A1": [spot("Example", found=cafe, overture="row-1", checked="agent")],
                "B2": [spot("Example DC", found=cafe, overture="row-1", checked="agent")]}
        self.assertEqual(shared_spots(pins), [])
        # the same spot, once by the rules and once by an agent, where the row spaces the name its own way
        spaced = "Ex Ample Grill & Bar, 1, Example Street"
        pins = {"A1": [spot("Example Grill", found=spaced, overture="row-1")],
                "B2": [spot("Example Grill", found=spaced, overture="row-1", checked="agent")]}
        self.assertEqual(shared_spots(pins), [])
        # an accent in the row's name, and one name twice where the row's name is not the caption's
        accented = "Exámple Coffee, 1, Example Street"
        pins = {"A1": [spot("Example Coffee", found=accented, overture="row-1")],
                "B2": [spot("Example", found=accented, overture="row-1", checked="agent")]}
        self.assertEqual(shared_spots(pins), [])
        other = "Sample Kitchen, 1, Example Street"
        pins = {"A1": [spot("Example Atx", found=other, overture="row-1")],
                "B2": [spot("Example Atx", found=other, overture="row-1", checked="agent")]}
        self.assertEqual(shared_spots(pins), [])

    def test_shops_in_one_building_pass_when_marked(self):
        pins = {"A1": [spot("Example Grill", building="Example Food Hall")],
                "B2": [spot("Sample Noodles", building="Example Food Hall")]}
        self.assertEqual(shared_spots(pins), [])
        pins["B2"][0].pop("building")
        self.assertEqual(len(shared_spots(pins)), 1)

    def test_spots_apart_and_spots_with_no_pin_pass(self):
        pins = {"A1": [spot("Example Grill")], "B2": [spot("Sample Noodles", lat=10.01)],
                "C3": [{"name": "Unplaced Cafe"}]}
        self.assertEqual(shared_spots(pins), [])


class Items(unittest.TestCase):
    KNOWN = {"travel", "recipes", "crafts"}
    CAPTIONS = {"SOUP1": "My “lentil soup”   and a quick flatbread", "EMPTY1": ""}

    def why(self, items):
        return [w["msg"] for _, w in item_problems(items, self.KNOWN, self.CAPTIONS)]

    def test_good_items_pass(self):
        items = {"SOUP1": {"topics": ["recipes"], "items": [
                     {"topic": "recipes", "kind": "dish", "name": "Lentil soup", "quote": 'my "lentil soup" and'}]},
                 "EMPTY1": {"topics": ["recipes"], "items": []}}
        self.assertEqual(self.why(items), [])

    def test_bad_quote_topic_shape_and_code(self):
        items = {"SOUP1": {"topics": ["recipes"], "items": [
                     {"topic": "recipes", "kind": "dish", "name": "Lentil stew", "quote": "lentil stew"},
                     {"topic": "travel", "kind": "dish", "name": "Soup", "quote": "lentil soup"},
                     {"topic": "recipes", "kind": "dish", "name": "", "quote": "lentil soup"}]},
                 "NOPE1": {"topics": [], "items": []},
                 "EMPTY1": ["not", "a", "map"]}
        self.assertEqual(sorted(self.why(items)), sorted([
            "quote is not in the caption", "not a known topic other than travel",
            "an item needs topic, kind, name and quote", "not a save in the export",
            "needs {topics: [...], items: [...]}"]))

    def test_without_the_export_quotes_are_not_checked(self):
        items = {"SOUP1": {"items": [{"topic": "recipes", "kind": "dish", "name": "X", "quote": "not there"}]}}
        self.assertEqual(item_problems(items, self.KNOWN, None), [])


class ItemFiles(unittest.TestCase):
    def test_a_save_in_two_topic_files_is_found(self):
        import tempfile
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, items_store.DIR))
        for slug in ("crafts", "recipes"):
            with open(os.path.join(root, items_store.DIR, f"{slug}.yaml"), "w") as fh:
                fh.write("SOUP1: {topics: [recipes], items: []}\n")
        self.assertEqual(items_store.duplicates(root),
                         {"SOUP1": [os.path.join(items_store.DIR, "crafts.yaml"), os.path.join(items_store.DIR, "recipes.yaml")]})
        self.assertEqual(items_store.file_for({"topics": ["recipes", "crafts"]}), os.path.join(items_store.DIR, "crafts.yaml"))
        self.assertEqual(items_store.file_for({"topics": []}), os.path.join(items_store.DIR, "other.yaml"))


if __name__ == "__main__":
    unittest.main()
