#!/usr/bin/env python3
"""Offline tests for check_data.py's spot check: two different spots on one map point."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_data import shared_spots  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
