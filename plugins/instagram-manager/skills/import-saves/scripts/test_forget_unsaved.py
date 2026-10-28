#!/usr/bin/env python3
"""Offline tests for forget_unsaved.py, on invented codes."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forget_unsaved  # noqa: E402

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


class Forget(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".cache"))
        os.makedirs(os.path.join(self.root, "data", "items"))
        with open(os.path.join(self.root, ".cache", "import-diff.json"), "w") as fh:
            json.dump({"gone": ["FXb2Gone002", "FXc3Back003"]}, fh)
        with open(os.path.join(self.root, ".cache", "saves.json"), "w") as fh:   # FXc3 was saved again
            json.dump({"saves": [{"code": "FXa1Keep001"}, {"code": "FXc3Back003"}]}, fh)
        self.tags = os.path.join(self.root, "data", "tags.yaml")
        with open(self.tags, "w") as fh:
            fh.write(TAGS)
        p = mock.patch.dict(os.environ, {"INSTAGRAM_HOME": self.root})
        p.start()
        self.addCleanup(p.stop)

    def test_removes_only_the_gone_block_and_keeps_the_layout(self):
        self.assertEqual(forget_unsaved.main([]), 0)
        self.assertEqual(open(self.tags).read(),
                         "FXa1Keep001:\n  cities: []\n  topics: [other]\nFXc3Back003:\n  topics: [other]\n")

    def test_a_dry_run_changes_nothing(self):
        self.assertEqual(forget_unsaved.main(["--dry-run"]), 0)
        self.assertEqual(open(self.tags).read(), TAGS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
