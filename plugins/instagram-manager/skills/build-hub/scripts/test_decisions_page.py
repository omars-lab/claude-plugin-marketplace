#!/usr/bin/env python3
"""Offline checks for decisions_page.py, on an invented data repo in a temp folder. No network.

    python3 skills/build-hub/scripts/test_decisions_page.py

Every code, handle and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_page as dp  # noqa: E402
import google_places as gp  # noqa: E402
import yaml  # noqa: E402

CAFE = {"name": "Example Cafe", "near": "Fixture Town", "said": "@examplecafe"}
DINER = {"name": "Example Diner", "near": "Fixture Town", "osm": "node/1"}
INN = {"name": "Example Inn", "near": "Fixture Park"}


def save(code, user="example_creator"):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "reel", "caption": "",
            "hashtags": [], "owner": {"username": user}, "saved_at": "2026-01-02T03:04", "collections": []}


class Rows(unittest.TestCase):
    def setUp(self):
        self.spots = dp.spot_index([save("CAFE1"), save("CAFE2"), save("DINER1"), save("INN1")],
                                   {"CAFE1": [CAFE], "CAFE2": [CAFE], "DINER1": [DINER], "INN1": [INN]}, {})

    def test_spot_index_keys_like_find_google_ids(self):
        self.assertEqual(self.spots[gp.spot_key(CAFE)][1], ["CAFE1", "CAFE2"])
        self.assertIn("osm:node/1", self.spots)

    def test_google_rows_keep_only_spots_still_to_pick(self):
        cafe, diner, inn = gp.spot_key(CAFE), gp.spot_key(DINER), gp.spot_key(INN)
        to_pick = {cafe: {"query": gp.query_for(CAFE), "ids": ["idA", "idB", ""]},
                   diner: {"query": gp.query_for(DINER), "ids": ["idC"]},          # picked since
                   inn: {"query": "Example Inn, somewhere else", "ids": ["idD"]},  # search text changed
                   "spot:gone@nowhere": {"query": "Gone", "ids": ["idE"]}}        # no longer a spot
        kept = {diner: {"verdict": "match", "id": "idC", "query": gp.query_for(DINER)}}
        rows = dp.google_rows(to_pick, kept, self.spots)
        self.assertEqual([r["key"] for r in rows], [cafe])
        self.assertEqual(rows[0]["ids"], ["idA", "idB"])
        self.assertEqual(rows[0]["codes"], ["CAFE1", "CAFE2"])

    def test_a_pick_for_an_older_search_does_not_hide_the_spot(self):
        cafe = gp.spot_key(CAFE)
        to_pick = {cafe: {"query": gp.query_for(CAFE), "ids": ["idA"]}}
        kept = {cafe: {"verdict": "none", "query": "Example Cafe, an older search"}}
        self.assertEqual(len(dp.google_rows(to_pick, kept, self.spots)), 1)


class Review(unittest.TestCase):
    def test_open_review_splits_check_from_town_only(self):
        review = {"A1": [{"said": "Example Hall", "near": "Fixture Town", "why": "near Far City, which is not one of"
                          " the save's areas"},
                         {"said": "Example Bar", "near": "Fixture Town", "why": "not found near Fixture Town"},
                         {"said": "Settled", "ok": True}, {"said": "Gone", "drop": True},
                         {"said": "Renamed", "lookup": "Other Name"}],
                  "A2": "not a list"}
        check, town = dp.open_review(review)
        self.assertEqual([e["said"] for _, e in check], ["Example Hall"])
        self.assertEqual([e["said"] for _, e in town], ["Example Bar"])


class Waiting(unittest.TestCase):
    def test_answers_videos_and_links(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tag"))
            for name in ("batch-001.answers.json", "batch-002.answers.json", "batch-003.answers.merged.json",
                         "batch-004.json"):
                open(os.path.join(d, "tag", name), "w").close()
            self.assertEqual(dp.waiting_answers(d), {"tag": 2, "locate": 0, "frames": 0})

            stuck = os.path.join(d, "stuck.txt")
            with open(stuck, "w") as fh:
                fh.write("REEL1  # no spot\nREEL2 # state only\n\n# a note\n")
            self.assertEqual(dp.videos_waiting(stuck, {"REEL1": {"video": "x.mp4"}}), 1)
            self.assertEqual(dp.videos_waiting(os.path.join(d, "missing.txt"), {}), 0)

            links = os.path.join(d, "links.yaml")
            with open(links, "w") as fh:
                yaml.safe_dump([{"label": "Merge the example pull request", "url": "https://example.com/pr/1"},
                                {"label": "Decided already", "done": True},
                                {"label": "Say in chat", "note": "No link"}, {"url": "https://example.com"}], fh)
            self.assertEqual([x["label"] for x in dp.load_links(links)], ["Merge the example pull request", "Say in chat"])
            with open(links, "w") as fh:
                yaml.safe_dump([{"label": "Bad", "url": "javascript:alert(1)"}], fh)
            with self.assertRaises(SystemExit):
                dp.load_links(links)


class Page(unittest.TestCase):
    def test_page_holds_only_our_names_and_ids(self):
        spots = dp.spot_index([save("CAFE1")], {"CAFE1": [CAFE]}, {})
        k = gp.spot_key(CAFE)
        rows = dp.google_rows({k: {"query": gp.query_for(CAFE), "ids": ["idA", "idB"]}}, {}, spots)
        check = [("H1", {"said": "Example <Hall>", "near": "Fixture Town", "why": "near Far City"})]
        with tempfile.TemporaryDirectory() as d:
            page, counts = dp.build(rows, check, [], {"M1": {}}, {"tag": 3, "locate": 0, "frames": 0}, 2,
                                    [{"label": "Example link", "url": "https://example.com", "note": ""}],
                                    {"CAFE1": save("CAFE1")}, d)
        self.assertEqual(counts, {"google": 1, "check": 1, "moves": 1, "merge": 3, "fetch": 1, "links": 1})
        self.assertIn("8 things wait on you.", page)
        self.assertIn('data-key="%s" data-id="idA"' % k, page)
        self.assertIn(gp.maps_link(gp.query_for(CAFE), "idB").replace("&", "&amp;"), page)
        self.assertIn("Example &lt;Hall&gt;", page)          # escaped
        self.assertNotIn("<Hall>", page)
        self.assertIn("make tag-merge", page)
        self.assertIn("2 reels still need their video", page)
        self.assertIn("https://www.instagram.com/p/CAFE1/", page)   # no post page in the hub: Instagram

    def test_main_writes_the_page_from_a_data_folder(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            os.makedirs(os.path.join(d, ".cache", "hub", "posts"))
            open(os.path.join(d, ".cache", "hub", "posts", "CAFE1.html"), "w").close()
            with open(os.path.join(d, ".cache", "saves.json"), "w") as fh:
                json.dump({"saves": [save("CAFE1")]}, fh)
            with open(os.path.join(d, "data", "pins.yaml"), "w") as fh:
                yaml.safe_dump({"CAFE1": [CAFE]}, fh)
            with open(os.path.join(d, ".cache", dp.TO_PICK), "w") as fh:
                json.dump({gp.spot_key(CAFE): {"query": gp.query_for(CAFE), "ids": ["idA"]}}, fh)
            old_cwd, old_home = os.getcwd(), os.environ.get("INSTAGRAM_HOME")
            os.environ["INSTAGRAM_HOME"] = d
            os.chdir(d)
            try:
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(dp.main([]), 0)
            finally:
                os.chdir(old_cwd)
                if old_home is None:
                    os.environ.pop("INSTAGRAM_HOME", None)
                else:
                    os.environ["INSTAGRAM_HOME"] = old_home
            self.assertIn("1 Google pick, 0 spots to check", out.getvalue())
            with open(os.path.join(d, ".cache", "hub", "decisions.html"), encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn('href="posts/CAFE1.html">@example_creator</a>', page)


if __name__ == "__main__":
    unittest.main()
