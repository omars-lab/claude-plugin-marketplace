#!/usr/bin/env python3
"""Offline tests for check_locator.py's scoring, on invented spots. Run: python3 test_check_locator.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_locator as cl  # noqa: E402

PIN = ("pin", {"said": "@exampledeli", "name": "Example Deli", "near": "Fixture Town", "kind": "address"})
COORDS = ("pin", {"said": "Example Cottage", "name": "Example Cottage", "near": "Fixture Town", "kind": "spot",
                  "found": "the caption's coordinates"})
MISS = ("review", {"said": "Example Bistro", "near": "Fixture Town", "why": "not found near Fixture Town"})
FAR = ("review", {"said": "Example Tower", "near": "Fixture Town", "why": "41 km from Fixture Town"})
QUOTE = ("review", {"said": "Example Bar", "near": "Fixture Town", "why": "quote not in caption"})
DROPPED = ("review", {"said": "Example Inn", "near": "Fixture Town", "why": "not found near Fixture Town", "drop": True})
ELSEWHERE = ("review", {"said": "Faraway Grill", "near": "Fixture Town", "why": "not found near Fixture Town"})
UNLISTED = ("pin", {"said": "Example Pier", "near": "Fixture Town", "kind": "pier"})


class Score(unittest.TestCase):
    def test_each_listed_spot_is_pinned_at_its_town_or_lost(self):
        checks = {"CODE1": {"why": "", "spots": ["Example Deli", "Example Cottage", "Example Bistro", "Example Tower",
                                                  "Example Bar", "Example Inn", "Example Museum"],
                            "not": ["Faraway Grill"]}}
        got, wrong, extra = cl.score(checks, {"CODE1": [PIN, COORDS, MISS, FAR, QUOTE, DROPPED, ELSEWHERE, UNLISTED]})
        s = got["CODE1"]
        self.assertEqual(s["Example Deli"], ("pinned", "address"))
        self.assertEqual(s["Example Cottage"], ("pinned", "coordinates"))
        self.assertEqual(s["Example Bistro"][0], "at its town")
        self.assertEqual(s["Example Tower"][0], "at its town")      # the hub still shows it at its town
        self.assertEqual(s["Example Bar"], ("lost", "quote not in caption"))
        self.assertEqual(s["Example Inn"][0], "lost")                # a person dropped it
        self.assertEqual(s["Example Museum"], ("lost", "not named"))
        self.assertEqual(wrong, [("CODE1", "Faraway Grill")])
        self.assertEqual(extra, [("CODE1", "Example Pier")])
        self.assertEqual(cl.totals(got), {"pinned": 2, "at its town": 2, "lost": 3})

    def test_a_handle_run_together_matches_the_name_and_the_closest_name_wins(self):
        handle = ("review", {"said": "@examplecornerbakery", "near": "Fixture Town", "why": "not found near Fixture Town"})
        river = ("pin", {"said": "Example River State Beach", "near": "Fixture Town"})
        beach = ("pin", {"said": "Example Beach", "near": "Fixture Town"})
        checks = {"C": {"why": "", "spots": ["Example Beach", "Example River State Beach", "Example Corner Bakery"],
                        "not": []}}
        got, _, extra = cl.score(checks, {"C": [river, beach, handle]})
        self.assertEqual([got["C"][n][0] for n in checks["C"]["spots"]], ["pinned", "pinned", "at its town"])
        self.assertEqual(extra, [])
        # with only the river beach named, the plain beach still finds it, as a near match
        got, _, _ = cl.score({"C": {"why": "", "spots": ["Example Beach"], "not": []}}, {"C": [river]})
        self.assertEqual(got["C"]["Example Beach"][0], "pinned")

    def test_a_post_listed_with_no_spots_counts_what_the_agent_named_as_extra(self):
        got, wrong, extra = cl.score({"C": {"why": "", "spots": [], "not": []}}, {"C": [UNLISTED]})
        self.assertEqual((got["C"], wrong, extra), ({}, [], [("C", "Example Pier")]))


if __name__ == "__main__":
    unittest.main()
