#!/usr/bin/env python3
"""Offline tests for unsaved.py, on invented codes."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import unsaved  # noqa: E402

TAGS = """FXa1Keep001:
  cities: []
  topics: [other]
FXb2Gone002:
  hints: [Nice]
  topics:
  - business
FXc3Back003:
  topics: [other]
"""


class Unsaved(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".cache"))
        os.makedirs(os.path.join(self.root, "data", "items"))
        self.write(".cache/import-diff.json", json.dumps({"gone": ["FXb2Gone002", "FXc3Back003", "FXd4None004"]}))
        self.write(".cache/saves.json", json.dumps({"exported": "export-b.zip", "saves": [   # FXc3 was saved again
            {"code": "FXa1Keep001"}, {"code": "FXc3Back003"}]}))
        self.write(".cache/saves-previous.json", json.dumps({"saves": [
            {"code": "FXb2Gone002", "owner": {"username": "someone"}, "collections": ["Ideas"],
             "saved_at": "2026-01-02T03:04", "caption": "A long  caption " + "x" * 300}]}))
        self.tags = os.path.join(self.root, "data", "tags.yaml")
        self.write("data/tags.yaml", TAGS)
        p = mock.patch.dict(os.environ, {"INSTAGRAM_HOME": self.root})
        p.start()
        self.addCleanup(p.stop)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w") as fh:
            fh.write(text)

    def flagged(self):
        return yaml.safe_load(open(os.path.join(self.root, "data", "unsaved.yaml")))

    def test_flags_without_removing_anything(self):
        self.assertEqual(unsaved.main(["--flag"]), 0)
        self.assertEqual(open(self.tags).read(), TAGS)
        f = self.flagged()
        self.assertEqual(list(f), ["FXb2Gone002"])   # saved again and no-data codes are left out
        e = f["FXb2Gone002"]
        self.assertEqual((e["since"], e["owner"], e["collections"]), ("export-b.zip", "someone", ["Ideas"]))
        self.assertTrue(e["caption"].startswith("A long caption x") and len(e["caption"]) == unsaved.SNIPPET + 1)

    def test_a_save_saved_again_comes_off_the_list(self):
        self.write("data/unsaved.yaml", "FXa1Keep001:\n  since: export-a.zip\n")
        unsaved.main(["--flag"])
        self.assertEqual(list(self.flagged()), ["FXb2Gone002"])

    def test_forget_removes_only_the_named_block_and_keeps_the_layout(self):
        unsaved.main(["--flag"])
        self.assertEqual(unsaved.main(["--forget", "FXb2Gone002"]), 0)
        self.assertEqual(open(self.tags).read(),
                         "FXa1Keep001:\n  cities: []\n  topics: [other]\nFXc3Back003:\n  topics: [other]\n")
        self.assertIsNone(yaml.safe_load(open(os.path.join(self.root, "data", "unsaved.yaml"))))

    def test_a_dry_run_changes_nothing(self):
        self.assertEqual(unsaved.main(["--forget", "FXb2Gone002", "--dry-run"]), 0)
        self.assertEqual(open(self.tags).read(), TAGS)

    def test_the_page_lists_each_flagged_save_and_what_we_hold(self):
        unsaved.main(["--flag"])
        out = os.path.join(self.root, "page.html")
        self.assertEqual(unsaved.main(["--page", "--make", "--out", out]), 0)
        text = open(out).read()
        self.assertIn("instagram.com/p/FXb2Gone002/", text)
        self.assertIn("We hold: tags.yaml", text)
        self.assertIn("make forget-unsaved CODES=", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
