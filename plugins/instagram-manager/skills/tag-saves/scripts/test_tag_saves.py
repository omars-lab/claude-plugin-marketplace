#!/usr/bin/env python3
"""Offline checks for tag_saves.py, on an invented data repo. No key and no network: the model
call is replaced by canned replies.

    python3 skills/tag-saves/scripts/test_tag_saves.py

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tag_saves  # noqa: E402
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

# Canned model replies, picked by a word in the caption.
REPLIES = {
    "picnic": {"topics": ["travel", "parenting-kids"], "cities": ["Fixture State"]},
    "weekend": {"topics": ["travel"], "cities": ["Fixture State"]},
    "Sourdough": {"topics": ["recipes-coffee", "baking-tools"], "cities": [], "other_places": ["Elsewhere"]},
    "cabins": {"topics": [], "cities": []},
}


class FakeModel:
    def __init__(self):
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, key, system, user_msg, **kw):
        with self.lock:
            self.calls.append(user_msg)
        for word, reply in REPLIES.items():
            if word in user_msg:
                return json.dumps(reply)
        return "sorry, no JSON here"


class TagSaves(unittest.TestCase):
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
        self.model = FakeModel()
        self.real = tag_saves.claude.call_claude, tag_saves.claude.load_key
        tag_saves.claude.call_claude = self.model
        tag_saves.claude.load_key = lambda *a: "test-key"

    def tearDown(self):
        tag_saves.claude.call_claude, tag_saves.claude.load_key = self.real
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

    def test_rules_only_tags_the_pilot_without_the_model(self):
        self.run_tag("--pilot", "fixture", "--rules-only")
        tags = self.read("data/tags.yaml")
        self.assertEqual(self.model.calls, [])
        self.assertEqual(sorted(tags), ["BAD", "BAY", "SOUR", "TOWN1"])   # FAR is outside the pilot
        self.assertEqual(tags["TOWN1"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "rules"})
        self.assertEqual(tags["BAY"], {"topics": [], "cities": [], "source": "rules", "hints": ["Fixture State"]})
        self.assertEqual(tags["SOUR"]["hints"], ["Fixture State"])          # from the hashtag

    def test_model_adds_tags_and_off_list_names_go_to_review(self):
        self.run_tag("--pilot", "fixture")
        tags, review = self.read("data/tags.yaml"), self.read("data/tags-review.yaml")
        self.assertEqual(tags["TOWN1"]["topics"], ["parenting-kids", "travel"])
        self.assertEqual(tags["BAY"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "model",
                                       "hints": ["Fixture State"]})
        self.assertEqual(tags["SOUR"]["topics"], ["recipes-coffee"])       # the made-up topic stays out
        self.assertEqual(tags["SOUR"]["cities"], [])
        self.assertEqual(review["SOUR"], {"other_topics": ["baking-tools"], "other_places": ["Elsewhere"]})

    def test_a_bad_reply_does_not_stop_the_run_and_is_retried(self):
        self.run_tag("--pilot", "fixture")
        tags, review = self.read("data/tags.yaml"), self.read("data/tags-review.yaml")
        self.assertEqual(tags["BAD"], {"topics": ["travel"], "cities": ["Fixture State"], "source": "rules"})
        self.assertIn("error", review["BAD"])
        self.assertEqual(len(self.model.calls), 4)
        before = self.text("data/tags.yaml")
        self.run_tag("--pilot", "fixture")
        self.assertEqual(len(self.model.calls), 5)                          # only BAD is asked again
        self.assertEqual(self.text("data/tags.yaml"), before)  # no churn

    def test_no_topic_from_the_model_means_other(self):
        self.run_tag("--all")
        self.assertEqual(self.read("data/tags.yaml")["FAR"]["topics"], ["other"])
        self.assertNotIn("hints", self.read("data/tags.yaml")["FAR"])

    def test_limit_caps_the_calls(self):
        self.run_tag("--pilot", "fixture", "--limit", "1")
        self.assertEqual(len(self.model.calls), 1)

    def test_the_model_sees_the_rule_tags_and_hints(self):
        self.run_tag("--pilot", "fixture")
        msg = next(m for m in self.model.calls if "weekend" in m)
        self.assertIn("Place names found in the text: ['Fixture State']", msg)
        msg = next(m for m in self.model.calls if "picnic" in m)
        self.assertIn("Already tagged: topics ['travel'], places ['Fixture State']", msg)

    def test_report_calls_out_what_to_check(self):
        self.run_tag("--pilot", "fixture")
        out = self.run_tag("--report", "--pilot", "fixture")
        self.assertRegex(out, r"\| BAY \|.*found outside the collections")
        self.assertRegex(out, r"\| TOWN1 \|.*2\+ topics or places")
        self.assertIn("- SOUR hints Fixture State", out)                   # matched, but not a place
        self.assertNotIn("FAR", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
