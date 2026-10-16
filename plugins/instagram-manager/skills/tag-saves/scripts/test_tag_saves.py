#!/usr/bin/env python3
"""Offline checks for tag_saves.py, on an invented data repo. No model: a fake agent answers the
batch files with canned replies.

    python3 skills/tag-saves/scripts/test_tag_saves.py

Every code, handle, collection and place name here is made up (this plugin is public).
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
import add_places  # noqa: E402
import moves_page  # noqa: E402
import tag_saves  # noqa: E402
from places import Places  # noqa: E402
import yaml  # noqa: E402

TOPICS = """topics:
  travel: {label: Travel, about: places to go}
  recipes-coffee: {label: Recipes, about: cooking}
  parenting-kids: {label: Kids, about: children}
  other: {label: Other, about: anything else}
"""
COLLECTIONS = """collections:
  Fixture Town:    {topics: [travel], cities: [Fixture State]}
  Fixture Recipes: {topics: [recipes-coffee], cities: []}
  Fixture Abroad:  {topics: [travel], cities: [Faraway Land]}
pilots:
  fixture: {collections: [Fixture Town], cities: [Fixture State]}
"""
PLACES = """places:
  Fixture State: {names: [Fixture Bay], hashtags: [fixturebay]}
"""


def save(code, caption, collections=(), hashtags=()):
    return {"code": code, "url": f"https://www.instagram.com/p/{code}/", "kind": "post", "caption": caption,
            "hashtags": list(hashtags), "owner": {"username": "example_creator", "name": "Example"},
            "saved_at": None, "collections": list(collections)}


SAVES = [
    save("TOWN1", "Kid friendly picnic spots around town", ["Fixture Town"]),
    save("BAY", "A weekend in Fixture Bay, best views"),
    save("SOUR", "Sourdough loaf, step by step", ["Fixture Recipes"], ["fixturebay"]),
    save("FAR", "Mountain cabins near Fixture Bayou"),     # "Fixture Bay" must not match inside "Bayou"
    save("BAD", "BADREPLY", ["Fixture Town"]),
]

# Canned agent answers, picked by a word in the caption. BADREPLY gets none.
REPLIES = {
    "picnic": {"topics": ["travel", "parenting-kids"], "cities": ["Fixture State"]},
    "weekend": {"topics": ["travel"], "cities": ["Fixture State"], "purposes": ["adventure", "made-up"]},
    "Sourdough": {"topics": ["recipes-coffee", "baking-tools"], "cities": [], "other_places": ["Elsewhere"]},
    "cabins": {"topics": [], "cities": []},
    "Brunch": {"topics": ["travel"], "cities": ["Fixture City"]},
    "Faraway": {"topics": ["travel"], "cities": ["Faraway Land"], "purposes": ["stay"],
                "misfiled": {"not": ["Fixture State"], "quote": "road trip through Faraway Land"}},
    "Elsewhere": {"topics": ["travel"], "cities": [],
                  "misfiled": {"not": ["Fixture State"], "quote": "words that are not in the caption"}},
}
NESTED = {"places": {"Fixture City": {"kind": "city", "in": "Fixture State"}}}


class Home(unittest.TestCase):
    """An invented data repo in a temp folder; no tests of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        for rel, text in (("config/topics.yaml", TOPICS), ("config/collections.yaml", COLLECTIONS),
                          ("config/places.yaml", PLACES)):
            os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(root, rel), "w") as fh:
                fh.write(text)
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

    def run_tag(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
            tag_saves.main(list(argv))
        return out.getvalue()

    def text(self, rel):
        with open(os.path.join(self.tmp.name, rel)) as fh:
            return fh.read()

    def read(self, rel):
        return yaml.safe_load(self.text(rel))

    def write(self, rel, data):
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            if rel.endswith(".json"):
                json.dump(data, fh)
            else:
                yaml.safe_dump(data, fh)

    def batches(self):
        return sorted(glob.glob(os.path.join(self.tmp.name, ".cache", "batches", "tag", "batch-[0-9][0-9][0-9].json")))

    def agent(self, paths):
        """What the save-tagger agent does: read each batch, write its answers file."""
        seen = []
        for path in paths:
            with open(path) as fh:
                batch = json.load(fh)
            answers = {}
            for rec in batch["saves"]:
                seen.append(rec["code"])
                for word, reply in REPLIES.items():
                    if word in rec["caption"]:
                        answers[rec["code"]] = reply
            with open(batch["answers"], "w") as fh:
                json.dump({"answers": answers}, fh)
        return seen

    def tag(self, *scope):
        out = self.run_tag("--prepare", *scope)
        seen = self.agent(out.split())
        self.run_tag("--merge")
        return seen


class TagSaves(Home):
    def test_rules_only_tags_the_pilot_without_batches(self):
        self.run_tag("--rules-only", "--pilot", "fixture")
        tags = self.read("data/tags.yaml")
        self.assertEqual(self.batches(), [])
        self.assertEqual(sorted(tags), ["BAD", "BAY", "SOUR", "TOWN1"])   # FAR is outside the pilot
        self.assertEqual(tags["TOWN1"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "rules"})
        self.assertEqual(tags["BAY"], {"topics": [], "cities": [], "source": "rules", "hints": ["Fixture State"]})
        self.assertEqual(tags["SOUR"]["hints"], ["Fixture State"])          # from the hashtag

    def test_prepare_prints_the_batches_and_they_hold_what_the_agent_needs(self):
        out = self.run_tag("--prepare", "--pilot", "fixture")
        self.assertEqual(out.split(), self.batches())
        with open(self.batches()[0]) as fh:
            batch = json.load(fh)
        self.assertEqual(batch["topics"]["travel"], "places to go")
        self.assertEqual(sorted(batch["purposes"]), ["adventure", "eat", "see-do", "stay"])
        self.assertIn("Fixture State", batch["places"])
        self.assertTrue(batch["answers"].endswith("batch-001.answers.json"))
        town = next(r for r in batch["saves"] if r["code"] == "TOWN1")
        self.assertEqual(town["already"], {"topics": ["travel"], "cities": ["Fixture State"]})
        bay = next(r for r in batch["saves"] if r["code"] == "BAY")
        self.assertEqual(bay["hints"], ["Fixture State"])

    def test_merge_adds_the_answers_and_off_list_names_go_to_review(self):
        self.tag("--pilot", "fixture")
        tags, review = self.read("data/tags.yaml"), self.read("data/tags-review.yaml")
        self.assertEqual(tags["TOWN1"]["topics"], ["parenting-kids", "travel"])
        self.assertEqual(tags["BAY"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "model",
                                       "hints": ["Fixture State"], "purposes": ["adventure"]})  # made-up dropped
        self.assertEqual(tags["TOWN1"]["purposes"], [])                    # asked, none given
        self.assertEqual(tags["SOUR"]["topics"], ["recipes-coffee"])       # the made-up topic stays out
        self.assertEqual(tags["SOUR"]["cities"], [])
        self.assertEqual(review["SOUR"], {"other_topics": ["baking-tools"], "other_places": ["Elsewhere"]})

    def test_a_missing_answer_keeps_the_rule_tags_and_is_batched_again(self):
        self.tag("--pilot", "fixture")
        tags, review = self.read("data/tags.yaml"), self.read("data/tags-review.yaml")
        self.assertEqual(tags["BAD"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "rules"})
        self.assertEqual(review["BAD"], {"error": "no answer for this save"})
        before = self.text("data/tags.yaml")
        self.assertEqual(self.tag("--pilot", "fixture"), ["BAD"])          # only BAD is read again
        self.assertEqual(self.text("data/tags.yaml"), before)  # no churn

    def test_a_save_tagged_before_purposes_is_read_again_and_keeps_its_places(self):
        self.tag("--pilot", "fixture")
        tags = self.read("data/tags.yaml")
        del tags["BAY"]["purposes"]                                         # as tagged before purposes
        tags["BAY"]["cities"] = ["Faraway Land", "Fixture State"]
        self.write("data/tags.yaml", tags)
        self.assertEqual(sorted(self.tag("--pilot", "fixture")), ["BAD", "BAY"])
        bay = self.read("data/tags.yaml")["BAY"]
        self.assertEqual(bay["purposes"], ["adventure"])
        self.assertEqual(bay["cities"], ["Faraway Land", "Fixture State"])  # kept though the answer left it out
        self.assertEqual(sorted(self.tag("--pilot", "fixture")), ["BAD"])  # asked once
        self.tag("--pilot", "fixture", "--retag")
        self.assertEqual(self.read("data/tags.yaml")["BAY"]["cities"], ["Fixture State"])  # a retag can drop it

    def test_a_listed_place_written_as_a_hashtag_is_a_hint_and_a_new_hint_is_read_once(self):
        self.write(".cache/saves.json", {"saves": SAVES + [save("TAG", "A weekend away", ["Fixture Town"],
                                                                ["fixturecity"])]})
        self.tag("--pilot", "fixture")
        self.assertNotIn("hints", self.read("data/tags.yaml")["TAG"])        # Fixture City is not listed yet
        self.write("data/places.yaml", NESTED)
        out = self.run_tag("--prepare", "--pilot", "fixture")
        recs = {}
        for path in out.split():
            with open(path) as fh:
                recs.update({r["code"]: r for r in json.load(fh)["saves"]})
        self.assertEqual(sorted(recs), ["BAD", "TAG"])                       # only the save with a new hint
        self.assertEqual(recs["TAG"]["hints"], ["Fixture City"])
        self.agent(out.split())
        self.run_tag("--merge")
        self.assertEqual(self.read("data/tags.yaml")["TAG"]["hints"], ["Fixture City"])
        self.assertEqual(sorted(self.tag("--pilot", "fixture")), ["BAD"])    # read once

    def test_a_one_word_looked_up_name_in_the_caption_is_not_a_hint(self):
        self.write("data/places.yaml", {"places": {"Fixture City": {"in": "Fixture State"},
                                                   "Orchard": {"in": "Fixture State"}}})
        compiled = tag_saves.compile_places(Places.load())
        hints = tag_saves.place_hints(save("X", "Orchard pie, then lunch in fixture city"), compiled)
        self.assertEqual(hints, {"Fixture City"})

    def test_answers_from_a_batch_that_did_not_ask_for_purposes_add_none(self):
        paths = self.run_tag("--prepare", "--pilot", "fixture").split()
        with open(paths[0]) as fh:
            batch = json.load(fh)
        del batch["purposes"]
        self.write(paths[0], batch)
        self.agent(paths)
        self.run_tag("--merge")
        self.assertNotIn("purposes", self.read("data/tags.yaml")["BAY"])

    def test_a_batch_whose_agent_has_not_run_is_left_waiting(self):
        self.run_tag("--prepare", "--pilot", "fixture")
        out = self.run_tag("--merge")
        self.assertIn("1 batches still waiting", out)
        self.assertEqual({t["source"] for t in self.read("data/tags.yaml").values()}, {"rules"})
        self.assertEqual(self.read("data/tags-review.yaml"), {})          # no save blamed for it

    def test_merging_after_each_wave_counts_each_batch_once(self):
        paths = self.run_tag("--prepare", "--all", "--batch-saves", "2").split()
        self.agent(paths[:2])                                               # wave 1
        self.assertIn("1 batches still waiting", self.run_tag("--merge"))
        self.agent(paths[2:])                                               # wave 2
        self.assertIn("0 batches still waiting", self.run_tag("--merge"))
        self.run_tag("--merge")                                             # nothing new
        lines = self.text(".cache/batches/tag/merged.jsonl").splitlines()
        self.assertEqual([json.loads(x)["batch"] for x in lines], ["batch-001", "batch-002", "batch-003"])
        self.assertEqual(self.read("data/tags.yaml")["FAR"]["source"], "model")

    def test_an_answer_of_the_wrong_shape_goes_to_review(self):
        out = self.run_tag("--prepare", "--pilot", "fixture")
        with open(out.split()[0]) as fh:
            batch = json.load(fh)
        with open(batch["answers"], "w") as fh:
            json.dump({"answers": {"BAY": {"topics": "travel"}}}, fh)
        self.run_tag("--merge")
        self.assertIn("answer is not", self.read("data/tags-review.yaml")["BAY"]["error"])
        self.assertEqual(self.read("data/tags.yaml")["BAY"]["source"], "rules")

    def test_no_topic_from_the_agent_means_other(self):
        self.tag("--all")
        self.assertEqual(self.read("data/tags.yaml")["FAR"]["topics"], ["other"])
        self.assertNotIn("hints", self.read("data/tags.yaml")["FAR"])

    def test_limit_caps_the_saves_in_a_round(self):
        self.assertEqual(len(self.tag("--pilot", "fixture", "--limit", "1")), 1)

    def test_merge_logs_one_line_per_batch_for_the_retro(self):
        self.tag("--all", "--batch-saves", "2")
        lines = [json.loads(x) for x in self.text(".cache/batches/tag/merged.jsonl").splitlines()]
        self.assertEqual([x["batch"] for x in lines], ["batch-001", "batch-002", "batch-003"])
        self.assertEqual(sum(x["saves"] for x in lines), 5)
        self.assertEqual(sum(x["missing"] for x in lines), 1)              # BAD

    def test_a_new_round_replaces_the_last_rounds_batches(self):
        self.run_tag("--prepare", "--all", "--batch-saves", "1")
        self.assertEqual(len(self.batches()), 5)
        self.run_tag("--prepare", "--all")
        self.assertEqual(len(self.batches()), 1)

    def test_a_new_round_waits_for_answers_not_merged_yet(self):
        out = self.run_tag("--prepare", "--all")
        self.agent(out.split())
        with self.assertRaises(SystemExit) as stop:
            self.run_tag("--prepare", "--all")
        self.assertIn("make tag-merge", str(stop.exception))
        self.assertEqual(len(glob.glob(os.path.join(self.tmp.name, ".cache", "batches", "tag", "*.answers.json"))), 1)
        self.run_tag("--merge")
        self.run_tag("--prepare", "--all")  # once merged, a new round starts


class PlacesAndMoves(Home):
    def test_a_city_brings_the_state_it_sits_in(self):
        self.write("data/places.yaml", NESTED)
        self.write(".cache/saves.json", {"saves": SAVES + [save("CITY", "Brunch spots in Fixture City")]})
        out = self.run_tag("--prepare", "--all")
        with open(out.split()[0]) as fh:
            self.assertEqual(json.load(fh)["places"]["Fixture City"], "Fixture State")  # the agent sees nesting
        self.agent(out.split())
        self.run_tag("--merge")
        self.assertEqual(self.read("data/tags.yaml")["CITY"]["cities"], ["Fixture City", "Fixture State"])

    def test_a_suggested_place_moves_into_the_tags_once_it_is_listed(self):
        self.tag("--all")
        self.assertEqual(self.read("data/tags-review.yaml")["SOUR"]["other_places"], ["Elsewhere"])
        self.write("data/places.yaml", {**NESTED, "aliases": {"Elsewhere": "Fixture City"}})
        self.assertIn("1 saves got a place from the review list", self.run_tag("--merge"))
        self.assertEqual(self.read("data/tags.yaml")["SOUR"]["cities"], ["Fixture City", "Fixture State"])
        self.assertEqual(self.read("data/tags-review.yaml")["SOUR"], {"other_topics": ["baking-tools"]})

    def test_a_misfiled_save_goes_on_the_moves_list_and_comes_off_once_moved(self):
        mis = save("MIS", "A road trip through Faraway Land", ["Fixture Town"])
        self.write(".cache/saves.json", {"saves": SAVES + [mis]})
        self.tag("--all")
        move = self.read("data/moves.yaml")["MIS"]
        self.assertEqual(move["not"], ["Fixture State"])
        self.assertEqual(move["to"], ["Fixture Abroad"])
        self.assertEqual(move["fits"]["cities"], ["Faraway Land"])
        self.assertIn("Fixture State", self.read("data/tags.yaml")["MIS"]["cities"])  # kept until moved
        self.assertIn("MIS", self.run_tag("--moves"))
        mis["collections"] = ["Fixture Abroad"]                             # moved in the app, new export
        self.write(".cache/saves.json", {"saves": SAVES + [mis]})
        self.assertIn("(1 moved since the last run)", self.run_tag("--merge"))
        self.assertEqual(self.read("data/moves.yaml"), {})
        self.assertEqual(self.read("data/tags.yaml")["MIS"]["cities"], ["Faraway Land"])
        self.assertEqual(self.read("data/tags.yaml")["MIS"]["purposes"], ["stay"])  # kept through the move

    def test_tags_fixed_by_hand_survive_a_retag_and_a_move(self):
        mis = save("MIS", "A road trip through Faraway Land", ["Fixture Town"])
        self.write(".cache/saves.json", {"saves": SAVES + [mis]})
        self.tag("--all")
        tags = self.read("data/tags.yaml")
        self.assertIn("Fixture State", tags["MIS"]["cities"])               # the collection's, kept until moved
        fixed = {"topics": ["travel"], "cities": ["Faraway Land"], "purposes": ["stay"], "source": "model",
                 "by": "hand"}
        tags["MIS"] = fixed                                                 # a person drops the wrong place now
        self.write("data/tags.yaml", tags)
        out = self.run_tag("--prepare", "--all", "--retag")
        self.agent(out.split())
        batched = []
        for p in self.batches():
            with open(p) as fh:
                batched += [r["code"] for r in json.load(fh)["saves"]]
        self.assertNotIn("MIS", batched)
        self.run_tag("--merge")
        self.assertEqual(self.read("data/tags.yaml")["MIS"], fixed)
        self.write(".cache/batches/tag/batch-009.json",                     # a batch made before the fix
                   {"batch": "batch-009", "answers": os.path.join(self.tmp.name, ".cache/batches/tag/batch-009.answers.json"),
                    "saves": [{"code": "MIS", "caption": mis["caption"]}]})
        self.write(".cache/batches/tag/batch-009.answers.json",
                   {"answers": {"MIS": {"topics": ["other"], "cities": ["Fixture State"]}}})
        self.assertIn("1 answers left out", self.run_tag("--merge"))
        mis["collections"] = ["Fixture Abroad"]                             # then moved in the app
        self.write(".cache/saves.json", {"saves": SAVES + [mis]})
        self.run_tag("--merge")
        self.assertEqual(self.read("data/tags.yaml")["MIS"], fixed)
        self.assertEqual(self.read("data/moves.yaml"), {})

    def test_the_moves_page_shows_each_move_with_its_quote_marked(self):
        mis = save("MIS", "A road trip through Faraway Land <b>soon</b>", ["Fixture Town"])
        self.write(".cache/saves.json", {"saves": SAVES + [mis]})
        self.tag("--all")
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            moves_page.main([])
        page = self.text(".cache/hub/moves.html")
        self.assertIn('data-code="MIS"', page)
        self.assertIn('<span class="chip to">Fixture Abroad</span>', page)
        self.assertIn("<mark>road trip through Faraway Land</mark>", page)
        self.assertIn("1 saved post sits in", page)
        self.assertIn("&lt;b&gt;soon", page)                               # captions are escaped
        self.assertEqual(moves_page.excerpt("x" * 1000, "")[-1], "…")

    def test_a_misfiled_flag_without_a_real_quote_is_not_a_move(self):
        self.write(".cache/saves.json", {"saves": SAVES + [save("ELSE", "Elsewhere for a week", ["Fixture Town"])]})
        self.tag("--all")
        self.assertEqual(self.read("data/moves.yaml"), {})
        self.assertIn("quote is not in the caption", self.read("data/tags-review.yaml")["ELSE"]["misfiled"]["error"])

    def test_a_tag_not_from_the_collection_cannot_be_called_misfiled(self):
        self.write(".cache/saves.json", {"saves": SAVES + [save("MIS", "A road trip through Faraway Land")]})
        self.tag("--all")
        self.assertEqual(self.read("data/moves.yaml"), {})

    def test_a_move_suggests_the_collection_for_the_most_specific_place(self):
        places = Places({"A": {"cities": ["Fixture State"]}, "B": {"cities": ["Fixture City"]}},
                        {}, NESTED)
        colls = {"Here": {"topics": ["travel"], "cities": ["Fixture State"]},
                 "City": {"topics": ["travel"], "cities": ["Fixture City"]},
                 "Food": {"topics": ["recipes-coffee"], "cities": []}}
        move = {"fits": {"topics": ["travel"], "cities": ["Fixture City", "Fixture State"]}}
        self.assertEqual(tag_saves.suggest(move, colls, places, ["Elsewhere"])[0], "City")
        self.assertEqual(places.resolve("fixture city, Fixture State"), "Fixture City")
        food = {"fits":{"topics": ["recipes-coffee"], "cities": []}}
        self.assertEqual(tag_saves.suggest(food, colls, places, []), ["Food"])


def hit(name, addresstype, lat=1.0, **address):
    return [{"name": name, "addresstype": addresstype, "lat": lat, "lon": 2.0,
             "display_name": f"{name}, somewhere", "address": address}]


class AddPlaces(Home):
    """add_places.py with a fake OpenStreetMap: no network."""

    ANSWERS = {
        "Fixture State": hit("Fixture State", "state", country="Exampleland", country_code="us"),
        "Faraway Land": hit("Faraway Land", "country", country="Faraway Land", country_code="fl"),
        "Fixture Village": hit("Fixture Village", "town", state="Fixture State", country_code="us",
                               country="Exampleland"),
        "Fixture Quarter": hit("Fixture Quarter", "suburb", city="Fixture City", state="Fixture State",
                               country_code="us", country="Exampleland"),
        "Fixture City, Fixture State": hit("Fixture City", "city", state="Fixture State",
                                           country_code="us", country="Exampleland"),
        "Fixture Road": hit("Fixture Road", "road", state="Fixture State", country_code="us"),
    }

    def fetch(self, query):
        self.asked.append(query)
        return self.ANSWERS.get(query, [])

    def run_add(self, *argv):
        self.asked = []
        real = add_places.geocode.fetch
        add_places.geocode.fetch = self.fetch
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
                add_places.main(list(argv))
        finally:
            add_places.geocode.fetch = real
        return out.getvalue()

    def test_places_from_review_are_added_with_the_place_they_sit_in(self):
        self.write("data/tags-review.yaml", {
            "A": {"other_places": ["Fixture Village", "Fixture Quarter"]},
            "B": {"other_places": ["Fixture Road", "Nowhere At All"]}})
        out = self.run_add()
        data = self.read("data/places.yaml")
        self.assertEqual(data["places"]["Fixture Village"]["in"], "Fixture State")
        self.assertIn("google.com/maps", data["places"]["Fixture Village"]["map"])
        self.assertEqual(data["aliases"], {"Fixture Quarter": "Fixture City"})  # a part of a city is the city
        self.assertEqual(data["places"]["Fixture City"]["in"], "Fixture State")
        self.assertNotIn("Fixture Road", data["places"])                        # a road stays in review
        self.assertIn("| Fixture Road |", out)
        self.assertIn("not found", out)

    def test_a_name_is_asked_once(self):
        self.write("data/tags-review.yaml", {"A": {"other_places": ["Nowhere At All"]}})
        self.run_add("--dry-run")
        self.assertIn("Nowhere At All", self.asked)
        self.run_add("--dry-run")
        self.assertNotIn("Nowhere At All", self.asked)                         # cached, misses too
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "data", "places.yaml")))

    def test_then_merge_moves_the_suggestions_into_the_tags(self):
        self.tag("--all")
        self.write("data/tags-review.yaml", {"SOUR": {"other_places": ["Fixture Village"]}})
        self.run_add()
        self.run_tag("--merge")
        self.assertEqual(self.read("data/tags.yaml")["SOUR"]["cities"], ["Fixture State", "Fixture Village"])


class Chunker(unittest.TestCase):
    def rec(self, code, chars):
        return {"code": code, "caption": "x" * chars}

    def test_cut_by_count(self):
        out = tag_saves.chunk([self.rec(str(i), 10) for i in range(7)], max_saves=3, max_chars=10 ** 6)
        self.assertEqual([len(b) for b in out], [3, 3, 1])

    def test_cut_by_size_and_never_split_a_save(self):
        recs = [self.rec("a", 400), self.rec("b", 400), self.rec("big", 2000), self.rec("c", 100)]
        out = tag_saves.chunk(recs, max_saves=40, max_chars=1000)
        self.assertEqual([[r["code"] for r in b] for b in out], [["a", "b"], ["big"], ["c"]])

    def test_order_is_kept(self):
        recs = [self.rec(str(i), 50) for i in range(10)]
        out = tag_saves.chunk(recs, max_saves=4, max_chars=10 ** 6)
        self.assertEqual([r["code"] for b in out for r in b], [str(i) for i in range(10)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
