#!/usr/bin/env python3
"""Offline checks for batch_review.py, on invented agent transcripts and merge logs.

    python3 skills/tag-saves/scripts/test_batch_review.py

Every path, batch and number here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batch_review  # noqa: E402


def transcript(folder, name, batch_file, peak, start, end, error=None, wrote=True, agent="save-tagger",
               read_chars=1000, prompt="Follow /plugin/agents/{agent}.md exactly. Batch: {batch_file}"):
    """An agent's transcript in Claude Code's shape: prompt, a read of the batch, answers, usage."""
    lines = [
        {"type": "user", "timestamp": start,
         "message": {"role": "user", "content": prompt.format(agent=agent, batch_file=batch_file)}},
        {"type": "assistant", "timestamp": start, "requestId": "r1",
         "message": {"model": "example-model", "content": [
             {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": batch_file}}],
             "usage": {"input_tokens": 10, "cache_creation_input_tokens": peak // 2, "cache_read_input_tokens": 0,
                       "output_tokens": 50}}},
        # the same request again for a second content block: counted once
        {"type": "assistant", "timestamp": start, "requestId": "r1",
         "message": {"model": "example-model", "content": [{"type": "text", "text": "reading"}],
                     "usage": {"input_tokens": 10, "cache_creation_input_tokens": peak // 2,
                               "cache_read_input_tokens": 0, "output_tokens": 50}}},
        {"type": "user", "timestamp": start, "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "x" * read_chars}]}},
        {"type": "assistant", "timestamp": end, "requestId": "r2",
         "message": {"model": "example-model", "content": [
             {"type": "tool_use", "id": "t2", "name": "Write" if wrote else "Bash",
              "input": {"file_path": batch_file.replace(".json", ".answers.json")}}],
             "usage": {"input_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": peak - 10,
                       "output_tokens": 500}}},
    ]
    if error:
        lines.append({"type": "assistant", "timestamp": end, "isApiErrorMessage": True, "error": error,
                      "message": {"content": [{"type": "text", "text": "an invented error"}]}})
    path = os.path.join(folder, "session-1", "subagents", f"agent-{name}.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json\n")
        for line in lines:
            fh.write(json.dumps(line) + "\n")


class BatchReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "repo")
        self.tx = os.path.join(self.tmp.name, "transcripts")
        os.environ["INSTAGRAM_HOME"] = self.home
        self.tag = os.path.join(self.home, ".cache", "batches", "tag")
        os.makedirs(self.tag)
        # two sizes, peaks on the line 40,000 + 1 per char
        transcript(self.tx, "a1", f"{self.tag}/batch-001.json", 60000, "2026-01-01T10:00:00.000Z",
                   "2026-01-01T10:01:00.500Z")
        transcript(self.tx, "a2", f"{self.tag}/batch-002.json", 50000, "2026-01-01T10:00:00.000Z",
                   "2026-01-01T10:00:30.000Z")
        # a later round reuses the name batch-001
        transcript(self.tx, "a3", f"{self.tag}/batch-001.json", 70000, "2026-01-02T09:00:00.000Z",
                   "2026-01-02T09:02:00.000Z", error="rate_limit", wrote=False)
        # not a batch agent: ignored
        transcript(self.tx, "a4", "/somewhere/else.json", 1, "2026-01-01T10:00:00.000Z", "2026-01-01T10:00:00.000Z")
        rows = [
            {"at": "2026-01-01T10:02:00Z", "batch": "batch-001", "saves": 40, "answered": 38, "missing": 2,
             "chars": 20000},
            {"at": "2026-01-01T10:02:00Z", "batch": "batch-002", "saves": 20, "answered": 20, "missing": 0,
             "chars": 10000},
            {"at": "2026-01-02T09:05:00Z", "batch": "batch-001", "saves": 40, "answered": 0, "missing": 40,
             "chars": 30000},
        ]
        with open(os.path.join(self.tag, "merged.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def runs(self):
        runs = batch_review.find_runs(self.tx)
        return batch_review.join(runs, {"tag": batch_review.load_merges("tag")})

    def test_parse_counts_numbers_once_per_request(self):
        runs = self.runs()
        self.assertEqual(len(runs), 3)  # the non-batch transcript is left out
        first = runs[1]  # sorted by end: a2, a1, a3
        self.assertEqual((first["kind"], first["batch"], first["agent"]), ("tag", "batch-001", "save-tagger"))
        self.assertEqual(first["peak"], 60000)
        self.assertEqual(first["out"], 550)  # r1 counted once, not twice
        self.assertEqual(first["turns"], 2)
        self.assertEqual(first["read_chars"], 1000)
        self.assertTrue(first["wrote"])
        self.assertEqual(first["errors"], [])

    def test_runs_join_their_own_round(self):
        runs = self.runs()
        by_name = {r["transcript"]: r for r in runs}
        self.assertEqual(by_name["agent-a1.jsonl"]["merge"]["missing"], 2)
        self.assertEqual(by_name["agent-a2.jsonl"]["merge"]["saves"], 20)
        later = by_name["agent-a3.jsonl"]
        self.assertEqual(later["merge"]["missing"], 40)  # the next day's merge, not the first one
        self.assertEqual(later["errors"], ["rate_limit"])
        self.assertFalse(later["wrote"])

    def test_merge_too_late_is_not_joined(self):
        with open(os.path.join(self.tag, "merged.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": "2026-01-05T00:00:00Z", "batch": "batch-002", "saves": 1}) + "\n")
        by_name = {r["transcript"]: r for r in self.runs()}
        self.assertIsNone(by_name["agent-a2.jsonl"]["merge"])

    def test_suggestion_fits_and_skips_error_runs(self):
        text, best = batch_review.suggest("tag", self.runs(), 120000)
        # 50,000 at 10,000 chars and 60,000 at 20,000: base 40,000, 1 a char → 80,000 chars fit
        self.assertEqual(best, 80000)
        self.assertIn("bigger", text)
        self.assertIn("Missed saves: 42 of 100", text)
        self.assertIn("--batch-saves", text)

    def test_one_size_says_too_few(self):
        runs = [r for r in self.runs() if r["batch"] == "batch-001"]
        text, best = batch_review.suggest("tag", runs, 120000)
        self.assertIsNone(best)
        self.assertIn("Too few sizes", text)

    def test_main_prints_table_and_flags(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            batch_review.main(["--transcripts", self.tx, "--kind", "tag", "--budget", "65000"])
        text = out.getvalue()
        self.assertIn("rate_limit", text)
        self.assertIn("look at: 2 runs", text)  # a1 missed saves; a3 hit a limit and went over budget
        self.assertNotIn("an invented error", text)  # no message text is printed

    def test_split_runs_and_a_bare_path_prompt(self):
        split = os.path.join(self.home, ".cache", "batches", "split")
        os.makedirs(split)
        transcript(self.tx, "s1", f"{split}/batch-001.json", 90000, "2026-01-03T10:00:00.000Z",
                   "2026-01-03T10:01:00.000Z", agent="save-splitter",
                   prompt="Read /plugin/agents/{agent}.md and follow it on this batch file: {batch_file}. Reply.")
        transcript(self.tx, "l1", f"{self.home}/.cache/batches/locate/batch-001.json", 80000,
                   "2026-01-03T10:00:00.000Z", "2026-01-03T10:01:00.000Z", prompt="{batch_file}")
        with open(os.path.join(split, "merged.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": "2026-01-03T10:02:00Z", "batch": "batch-001", "saves": 80, "answered": 80,
                                 "missing": 0, "chars": 40000}) + "\n")
        runs = batch_review.join(batch_review.find_runs(self.tx), {"split": batch_review.load_merges("split")})
        by_name = {r["transcript"]: r for r in runs}
        s1 = by_name["agent-s1.jsonl"]
        self.assertEqual((s1["kind"], s1["batch"], s1["agent"]), ("split", "batch-001", "save-splitter"))
        self.assertEqual(s1["batch_file"], f"{split}/batch-001.json")  # the trailing "." is not the path's
        self.assertEqual(s1["merge"]["saves"], 80)
        self.assertEqual(by_name["agent-l1.jsonl"]["kind"], "locate")

    def test_no_runs(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            batch_review.main(["--transcripts", os.path.join(self.tmp.name, "empty")])
        self.assertIn("no batch agent runs", out.getvalue())


if __name__ == "__main__":
    unittest.main()
