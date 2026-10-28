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
        kept[cafe] = {"verdict": "chain", "query": gp.query_for(CAFE)}            # marked a chain since
        self.assertEqual(dp.google_rows(to_pick, kept, self.spots), [])
        del kept[cafe]
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

    def test_a_spot_filed_under_another_town_is_to_check(self):
        far = {"said": "Example Coaster", "near": "Fixture Town", "why": "not found near Fixture Town",
               "really_in": "Other State"}
        same = {**far, "said": "Example Cafe", "really_in": "Fixture Town, Fixture State"}
        check, town = dp.open_review({"A1": [far, same]})
        self.assertEqual([e["said"] for _, e in check], ["Example Coaster"])   # needs its real town
        self.assertEqual([e["said"] for _, e in town], ["Example Cafe"])       # the same town: a map miss
        self.assertIn("The caption puts it in <b>Other State</b>", dp.review_card("A1", far, {}, {}))


class Waiting(unittest.TestCase):
    def test_answers_videos_and_links(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "tag"))
            for name in ("batch-001.answers.json", "batch-002.answers.json", "batch-003.answers.merged.json",
                         "batch-004.json"):
                open(os.path.join(d, "tag", name), "w").close()
            self.assertEqual(dp.waiting_answers(d), {"tag": 2, "locate": 0, "frames": 0, "split": 0})

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
        page, counts = dp.build(rows, check, [], {"M1": {}}, {"tag": 3, "locate": 0, "frames": 0, "split": 0}, 2,
                                [{"label": "Example link", "url": "https://example.com", "note": ""}],
                                {"CAFE1": save("CAFE1")}, {})
        self.assertEqual(counts, {"google": 1, "check": 1, "tags": 0, "items": 0, "moves": 1, "merge": 3,
                                  "fetch": 1, "links": 1})
        self.assertIn("8 things wait on you.", page)
        self.assertIn('data-key="%s" data-id="idA"' % k, page)
        self.assertIn('value="chain" data-key="%s"> A chain: any branch near here' % k, page)
        self.assertIn('" CHAIN=" + q(chains.join(" "))', page)
        self.assertIn(gp.maps_link(gp.query_for(CAFE), "idB").replace("&", "&amp;"), page)
        self.assertIn("Example &lt;Hall&gt;", page)          # escaped
        self.assertNotIn("<Hall>", page)
        self.assertIn("tag_saves.py --merge", page)            # the plugin's own command, not a make line
        self.assertNotIn("make tag-merge", page)
        self.assertIn('data-mode="plugin"', page)
        self.assertIn("2 reels still need their video", page)
        self.assertIn("https://www.instagram.com/p/CAFE1/", page)   # no post page in the hub: Instagram

    def test_make_prints_the_data_repos_lines(self):
        page, _ = dp.build([], [], [], {}, {"tag": 1}, 0, [], {}, {}, make=True)
        self.assertIn("make tag-merge", page)
        self.assertNotIn("tag_saves.py --merge", page)
        self.assertIn("make locate-merge", page)
        self.assertIn('data-mode="make"', page)
        self.assertIn("Run it in the data repo", page)

    def test_tags_and_items_review_count_as_waiting(self):
        tags = dp.tag_review({
            "T1": {"other_places": ["Example Cove, Fixture State"], "other_topics": ["kites"]},
            "T2": {"other_topics": ["kites", "origami"]},
            "T3": {"error": "no answer for this save"},
            "T4": {"misfiled": {"error": "misfiled, but its quote is not in the caption", "not": ["Fixture State"]}},
            "T5": "not a dict"})
        errors, places, topics = tags
        self.assertEqual([c for c, _ in errors], ["T3", "T4"])
        self.assertEqual(places, {"Example Cove, Fixture State": ["T1"]})
        self.assertEqual(topics, {"kites": ["T1", "T2"], "origami": ["T2"]})
        items = dp.items_review({"I1": [{"why": "quote is not in the caption", "topic": "recipes", "kind": "dish",
                                         "name": "Example Stew", "quote": "made up words"}], "I2": "not a list"})
        self.assertEqual([c for c, _ in items], ["I1"])
        page, counts = dp.build([], [], [], {}, {}, 0, [], {}, {}, tags, items)
        # 2 errors, 1 place, 1 topic two saves suggested; origami (one save) is shown but not counted
        self.assertEqual((counts["tags"], counts["items"]), (4, 1))
        self.assertIn("5 things wait on you.", page)
        self.assertIn("Example Cove, Fixture State", page)
        self.assertIn("1 topic suggested by one save only (not counted)", page)
        self.assertIn("add_places.py", page)
        self.assertIn("Example Stew", page)

    def test_town_only_spots_are_named_in_the_lede(self):
        town = [("P1", {"said": "Example Bakery", "near": "Fixture Town", "why": "not found near Fixture Town"})]
        page, counts = dp.build([], [], town, {}, {}, 0, [], {}, {})
        self.assertEqual(sum(counts.values()), 0)
        self.assertIn("Nothing needs a decision right now. 1 more spot is shown at its town only", page)
        self.assertNotIn("Nothing waits on you", page)

    def test_post_links_use_the_hub_page_names(self):
        a, b, out = save("abcDEF", "first_creator"), save("ABCdef", "second_creator"), save("OUT1")
        a["collections"] = b["collections"] = ["Example Trip"]
        pages = dp.hub_pages([a, b, out], {}, {"collections": ["Example Trip"]})
        self.assertEqual(pages, {"ABCdef": "ABCdef", "abcDEF": "abcDEF-2"})   # same as build_hub names them
        saves = {s["code"]: s for s in (a, b, out)}
        self.assertIn('href="posts/abcDEF-2.html">@first_creator</a>', dp.post_links("abcDEF", saves, pages))
        self.assertNotIn('href="posts/', dp.post_links("OUT1", saves, pages))   # not in this hub: Instagram
        self.assertEqual(len(dp.hub_pages([a, b, out], {}, None)), 3)          # --all

    def test_main_writes_the_page_from_a_data_folder(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            os.makedirs(os.path.join(d, ".cache"))   # no hub built yet: the post still gets its page link
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
                    self.assertEqual(dp.main(["--all"]), 0)
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
