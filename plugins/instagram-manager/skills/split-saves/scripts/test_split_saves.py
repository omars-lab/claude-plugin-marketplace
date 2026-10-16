#!/usr/bin/env python3
"""Offline checks for split_saves.py, on an invented data repo. No model: a fake agent answers the
batch files with canned replies.

    python3 skills/split-saves/scripts/test_split_saves.py

Every code, handle, collection, caption and place name here is made up (this plugin is public).
"""

import contextlib
import glob
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_saves  # noqa: E402
import items_store  # noqa: E402  (on the path once split_saves is in)
import yaml  # noqa: E402

TOPICS = """topics:
  travel: {label: Travel, about: places to go}
  recipes-coffee: {label: Recipes, about: cooking}
  islamic-design: {label: Design, about: patterns}
  business: {label: Business, about: running a business}
  parenting-kids: {label: Kids, about: children}
  other: {label: Other, about: anything else}
"""
COLLECTIONS = """collections:
  Fixture Recipes: {topics: [recipes-coffee], cities: []}
  Fixture Town:    {topics: [travel], cities: [Fixture State]}
pilots:
  fixture: {collections: [Fixture Recipes], cities: []}
"""


def save(code, caption, collections=()):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "post", "caption": caption,
            "hashtags": ["examplefood"], "owner": {"username": "example_baker", "name": "Example"},
            "saved_at": None, "collections": list(collections)}


SAVES = [
    save("BAKE1", "Two bakes this week: my lemon drizzle loaf and a brown butter blondie.", ["Fixture Recipes"]),
    save("STAR1", "How to draw an eight point star from one circle, then fill it with tiles."),
    save("TRIP1", "Sunset walk along Fixture Bay", ["Fixture Town"]),
    save("MIX1", "Road trip snacks the kids love: frozen yogurt bark.", ["Fixture Town"]),
    save("EMPTY1", "wait for the end 😍", ["Fixture Recipes"]),
    save("SKIP1", "no answer comes back for this one", ["Fixture Recipes"]),
]
TAGS = {
    "BAKE1": {"topics": ["recipes-coffee"], "cities": [], "source": "model"},
    "STAR1": {"topics": ["islamic-design"], "cities": [], "source": "model"},
    "TRIP1": {"topics": ["travel"], "cities": ["Fixture State"], "source": "model"},
    "MIX1": {"topics": ["travel", "recipes-coffee", "parenting-kids"], "cities": ["Fixture State"], "source": "model"},
    "EMPTY1": {"topics": ["recipes-coffee"], "cities": [], "source": "rules"},
    "SKIP1": {"topics": ["recipes-coffee"], "cities": [], "source": "rules"},
}

# Canned agent answers per code. SKIP1 gets none.
REPLIES = {
    "BAKE1": [
        {"topic": "recipes-coffee", "kind": "dish", "name": "Lemon drizzle loaf", "quote": "my lemon drizzle loaf"},
        {"topic": "recipes-coffee", "kind": "dish", "name": "Brown butter blondie", "quote": "a brown butter blondie"},
        {"topic": "recipes-coffee", "kind": "dish", "name": "Lemon drizzle cake", "quote": "lemon drizzle cake"},
        {"topic": "recipes-coffee", "kind": "dish", "name": "lemon  drizzle LOAF", "quote": "lemon drizzle loaf"},
    ],
    "STAR1": [
        {"topic": "islamic-design", "kind": "technique", "name": "Eight point star from a circle",
         "quote": "draw an eight point star from one circle"},
        {"topic": "islamic-design", "kind": "pattern", "name": "Tile fill", "quote": "fill it with tiles"},
    ],
    "MIX1": [
        {"topic": "recipes-coffee", "kind": "dish", "name": "Frozen yogurt bark", "quote": "frozen yogurt bark"},
        {"topic": "travel", "kind": "dish", "name": "Road trip", "quote": "Road trip"},
        {"topic": "business", "kind": "idea", "name": "Sell snacks", "quote": "snacks the kids love"},
        {"topic": "parenting-kids", "kind": "note", "name": "A snack kids like on the road",
         "quote": "Road trip snacks the kids love"},
    ],
    "EMPTY1": [],
}


class Home(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.write("config/topics.yaml", TOPICS)
        self.write("config/collections.yaml", COLLECTIONS)
        self.write("data/tags.yaml", yaml.safe_dump(TAGS))
        os.makedirs(os.path.join(root, ".cache"))
        with open(os.path.join(root, ".cache", "saves.json"), "w") as fh:
            json.dump({"saves": SAVES}, fh)
        self.env = os.environ.get("INSTAGRAM_HOME")
        os.environ["INSTAGRAM_HOME"] = root

    def tearDown(self):
        if self.env is None:
            os.environ.pop("INSTAGRAM_HOME", None)
        else:
            os.environ["INSTAGRAM_HOME"] = self.env
        self.tmp.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def read(self, rel):
        path = os.path.join(self.tmp.name, rel)
        if not os.path.exists(path):
            return {}
        with open(path) as fh:
            return yaml.safe_load(fh) or {}

    def items(self):
        return items_store.load_items(self.tmp.name)

    def item_files(self):
        out = {}
        for rel in items_store.files(self.tmp.name):
            with open(os.path.join(self.tmp.name, rel)) as fh:
                out[rel] = fh.read()
        return out

    def run_split(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()) as out:
            split_saves.main(list(argv))
        self.log = err.getvalue()
        return out.getvalue()

    def batches(self):
        return sorted(glob.glob(os.path.join(self.tmp.name, ".cache", "batches", "split", "batch-[0-9][0-9][0-9].json")))

    def agent(self, replies=None):
        """The fake save-splitter: answers every save in every batch it has a reply for."""
        replies = REPLIES if replies is None else replies
        for path in self.batches():
            with open(path) as fh:
                batch = json.load(fh)
            answers = {r["code"]: replies[r["code"]] for r in batch["saves"] if r["code"] in replies}
            with open(batch["answers"], "w") as fh:
                json.dump({"answers": answers}, fh)

    def batched_codes(self):
        codes = []
        for path in self.batches():
            with open(path) as fh:
                codes += [r["code"] for r in json.load(fh)["saves"]]
        return codes


class Prepare(Home):

    def test_batches_only_non_travel_saves_with_their_own_topics(self):
        self.run_split("--prepare", "--all")
        self.assertEqual(sorted(self.batched_codes()), ["BAKE1", "EMPTY1", "MIX1", "SKIP1", "STAR1"])
        with open(self.batches()[0]) as fh:
            batch = json.load(fh)
        recs = {r["code"]: r for r in batch["saves"]}
        self.assertEqual(recs["MIX1"]["topics"], ["parenting-kids", "recipes-coffee"])  # travel left out
        self.assertNotIn("travel", batch["topics"])
        self.assertEqual(batch["topics"]["recipes-coffee"]["kinds"], {"dish": split_saves.KINDS["recipes-coffee"]["dish"]})
        self.assertIn("technique", batch["topics"]["islamic-design"]["kinds"])
        self.assertIn("note", batch["topics"]["parenting-kids"]["kinds"])
        self.assertIn("waiting=5", self.log)
        self.assertEqual(self.items(), {})  # prepare writes no data

    def test_pilot_limit_and_batch_size(self):
        self.run_split("--prepare", "--pilot", "fixture")
        self.assertEqual(sorted(self.batched_codes()), ["BAKE1", "EMPTY1", "SKIP1"])
        self.run_split("--prepare", "--all", "--limit", "2")
        self.assertEqual(len(self.batched_codes()), 2)
        self.assertIn("waiting=5", self.log)
        self.run_split("--prepare", "--all", "--batch-saves", "2")
        self.assertEqual(len(self.batches()), 3)
        self.assertEqual(len(set(self.batched_codes())), 5)  # no save in two batches

    def test_refuses_while_answers_wait(self):
        self.run_split("--prepare", "--all")
        self.agent()
        with self.assertRaises(SystemExit) as stop:
            self.run_split("--prepare", "--all")
        self.assertIn("make split-merge", str(stop.exception))

    def test_kinds_for_unknown_topics(self):
        self.assertEqual(list(split_saves.kinds_for("home-cooking")), ["dish"])
        self.assertEqual(list(split_saves.kinds_for("garden-design")), ["subject", "technique"])
        self.assertEqual(list(split_saves.kinds_for("gardening")), ["note"])
        self.assertEqual(split_saves.kinds_for("gardening", {"item_kinds": {"plant": "a plant"}}), {"plant": "a plant"})


class Merge(Home):

    def merge_round(self, replies=None):
        self.run_split("--prepare", "--all")
        self.agent(replies)
        return self.run_split("--merge")

    def test_merge_keeps_checked_items(self):
        out = self.merge_round()
        items = self.items()
        self.assertEqual(items["BAKE1"]["topics"], ["recipes-coffee"])
        self.assertEqual([i["name"] for i in items["BAKE1"]["items"]], ["Lemon drizzle loaf", "Brown butter blondie"])
        self.assertEqual(list(items["BAKE1"]["items"][0]), ["topic", "kind", "name", "quote"])
        self.assertEqual(items["EMPTY1"], {"topics": ["recipes-coffee"], "items": []})  # nothing named: recorded
        self.assertNotIn("SKIP1", items)  # no answer: no entry, so batched again
        self.assertNotIn("TRIP1", items)
        self.assertIn("merged 4 answers (1 unusable)", out)

    def test_bad_quote_goes_to_review_not_data(self):
        self.merge_round()
        items, review = self.items(), self.read("data/items-review.yaml")
        self.assertNotIn("Lemon drizzle cake", [i["name"] for i in items["BAKE1"]["items"]])
        self.assertEqual(review["BAKE1"], [{"topic": "recipes-coffee", "kind": "dish", "name": "Lemon drizzle cake",
                                            "quote": "lemon drizzle cake", "why": "quote is not in the caption"}])
        self.assertEqual(review["SKIP1"], [{"why": "no answer for this save"}])

    def test_items_only_under_the_saves_own_topics(self):
        self.merge_round()
        items, review = self.items(), self.read("data/items-review.yaml")
        self.assertEqual(sorted(i["topic"] for i in items["MIX1"]["items"]), ["parenting-kids", "recipes-coffee"])
        self.assertEqual(sorted(r["topic"] for r in review["MIX1"]), ["business", "travel"])

    def test_unknown_kind_becomes_the_topics_first_kind(self):
        self.merge_round()
        star = self.items()["STAR1"]["items"]
        self.assertEqual([i["kind"] for i in star], ["technique", "subject"])

    def test_no_second_prepare_after_merge(self):
        self.merge_round()
        self.run_split("--prepare", "--all")
        self.assertEqual(self.batched_codes(), ["SKIP1"])  # only the save with no answer
        self.assertIn("already_split=4", self.log)
        self.run_split("--prepare", "--all", "--redo")
        self.assertEqual(len(self.batched_codes()), 5)

    def test_changed_topics_and_hand_fixes(self):
        self.merge_round()
        tags = dict(TAGS, BAKE1={"topics": ["recipes-coffee", "business"], "cities": [], "source": "model"})
        self.write("data/tags.yaml", yaml.safe_dump(tags))
        star = self.read("data/items/islamic-design.yaml")
        star["STAR1"]["by"] = "hand"
        self.write("data/items/islamic-design.yaml", yaml.safe_dump(star))
        self.run_split("--prepare", "--all", "--redo")
        self.assertNotIn("STAR1", self.batched_codes())
        self.run_split("--merge")  # no answers: nothing changes
        self.run_split("--prepare", "--all")
        self.assertEqual(sorted(self.batched_codes()), ["BAKE1", "SKIP1"])  # BAKE1 gained a topic

    def test_rerun_merge_changes_nothing(self):
        self.merge_round()
        before = self.item_files()
        out = self.run_split("--merge")
        self.assertEqual(self.item_files(), before)
        self.assertIn("merged 0 answers", out)

    def test_unparsable_answers_file(self):
        self.run_split("--prepare", "--all")
        with open(self.batches()[0]) as fh:
            ans = json.load(fh)["answers"]
        with open(ans, "w") as fh:
            fh.write("not json")
        self.run_split("--merge")
        review = self.read("data/items-review.yaml")
        self.assertTrue(all(r[0]["why"].startswith("the answers file is not JSON") for r in review.values()))
        self.assertEqual(self.items(), {})

    def test_one_file_per_topic(self):
        self.merge_round()
        self.assertEqual(items_store.files(self.tmp.name), ["data/items/islamic-design.yaml",
                                                            "data/items/parenting-kids.yaml",
                                                            "data/items/recipes-coffee.yaml"])
        self.assertIn("MIX1", self.read("data/items/parenting-kids.yaml"))  # the first of its topics
        self.assertNotIn("MIX1", self.read("data/items/recipes-coffee.yaml"))  # and only there
        self.assertEqual(sorted(self.read("data/items/recipes-coffee.yaml")), ["BAKE1", "EMPTY1"])

    def test_old_single_file_moves_into_the_folder(self):
        self.write("data/items.yaml", yaml.safe_dump({"OLD1": {"topics": ["business"], "items": []}}))
        self.assertIn("OLD1", self.items())  # still read before the move
        self.merge_round()
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "data", "items.yaml")))
        self.assertEqual(self.read("data/items/business.yaml"), {"OLD1": {"topics": ["business"], "items": []}})
        self.assertIn("BAKE1", self.items())

    def test_a_save_that_changes_topic_moves_file(self):
        self.merge_round()
        tags = dict(TAGS, BAKE1={"topics": ["recipes-coffee", "business"], "cities": [], "source": "model"})
        self.write("data/tags.yaml", yaml.safe_dump(tags))
        self.merge_round({"BAKE1": REPLIES["BAKE1"]})
        self.assertIn("BAKE1", self.read("data/items/business.yaml"))
        self.assertNotIn("BAKE1", self.read("data/items/recipes-coffee.yaml"))
        self.assertEqual(items_store.duplicates(self.tmp.name), {})

    def test_answers_as_items_dicts(self):
        self.merge_round({code: {"items": items} for code, items in REPLIES.items()})
        self.assertEqual(len(self.items()["BAKE1"]["items"]), 2)


if __name__ == "__main__":
    unittest.main()
